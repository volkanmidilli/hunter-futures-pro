"""Tests for hunter.experiment_ledger.writer."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hunter.experiment_ledger import (
    DEFAULT_CSV_PATH,
    DEFAULT_JSON_PATH,
    DEFAULT_MD_PATH,
    ExperimentComparisonConfig,
    ExperimentLedgerInput,
    ExperimentLedgerReport,
    ExperimentMetricSnapshot,
    ExperimentRecord,
    ExperimentState,
    build_experiment_ledger_report,
    experiment_ledger_report_to_csv_text,
    experiment_ledger_report_to_dict,
    experiment_ledger_report_to_json_text,
    experiment_ledger_report_to_markdown_text,
    write_experiment_ledger_report,
    atomic_write_json_experiment_ledger_report,
    atomic_write_csv_experiment_ledger_report,
    atomic_write_markdown_experiment_ledger_report,
)


def ts(day: int, hour: int = 0) -> datetime:
    return datetime(2024, 1, day, hour, tzinfo=timezone.utc)


def make_report(
    *,
    baseline: str | None = None,
    include_blocked: bool = True,
    include_insufficient: bool = True,
    generated_at: datetime | None = None,
) -> ExperimentLedgerReport:
    snap_a = ExperimentMetricSnapshot(
        experiment_id="exp-a",
        run_id="run-a",
        name="Alpha",
        metrics={
            "total_return_pct": 10.0,
            "max_drawdown_pct": 5.0,
            "volatility_pct": 2.0,
            "win_rate_pct": 55.0,
            "observation_count": 100,
            "missing_data_count": 0,
            "blocked_count": 0,
            "insufficient_data_count": 0,
        },
        tags=("tag-a",),
        generated_at=ts(1),
    )
    snap_b = ExperimentMetricSnapshot(
        experiment_id="exp-b",
        run_id="run-b",
        name="Beta",
        metrics={
            "total_return_pct": 7.0,
            "max_drawdown_pct": 4.0,
            "volatility_pct": 1.5,
            "win_rate_pct": 60.0,
            "observation_count": 90,
            "missing_data_count": 1,
            "blocked_count": 0,
            "insufficient_data_count": 0,
        },
        tags=("tag-b",),
        generated_at=ts(1),
    )
    input_obj = ExperimentLedgerInput(
        metric_snapshots=(snap_a, snap_b),
        generated_at=generated_at or ts(1),
        metadata={"exp-a": "Override Alpha"},
    )
    config = ExperimentComparisonConfig(
        baseline_experiment_id=baseline,
        include_blocked=include_blocked,
        include_insufficient=include_insufficient,
        primary_metric="total_return_pct",
    )
    return build_experiment_ledger_report(input_obj, config)


class TestPublicExports:
    def test_writer_exports(self) -> None:
        assert callable(experiment_ledger_report_to_dict)
        assert callable(experiment_ledger_report_to_json_text)
        assert callable(experiment_ledger_report_to_csv_text)
        assert callable(experiment_ledger_report_to_markdown_text)
        assert callable(write_experiment_ledger_report)
        assert callable(atomic_write_json_experiment_ledger_report)
        assert callable(atomic_write_csv_experiment_ledger_report)
        assert callable(atomic_write_markdown_experiment_ledger_report)
        assert isinstance(DEFAULT_JSON_PATH, Path)
        assert isinstance(DEFAULT_CSV_PATH, Path)
        assert isinstance(DEFAULT_MD_PATH, Path)


class TestDictConversion:
    def test_includes_top_level_fields(self) -> None:
        report = make_report()
        d = experiment_ledger_report_to_dict(report)
        assert d["report_id"] == report.report_id
        assert d["version"] == report.version
        assert "generated_at" in d
        assert "input" in d
        assert "comparison" in d
        assert "data_quality" in d
        assert "safety_flags" in d
        assert "reason_codes" in d
        assert "metadata" in d
        assert "notes" in d

    def test_records_serialized(self) -> None:
        report = make_report()
        d = experiment_ledger_report_to_dict(report)
        records = d["comparison"]["records"]
        assert len(records) == 2
        assert records[0]["experiment_id"] == "exp-a"
        assert records[0]["state"] == "included"
        assert "total_return_pct" in records[0]["metrics"]

    def test_deltas_serialized(self) -> None:
        report = make_report(baseline="exp-a")
        d = experiment_ledger_report_to_dict(report)
        deltas = d["comparison"]["deltas"]
        assert "exp-a" in deltas
        assert "exp-b" in deltas
        assert deltas["exp-a"]["total_return_pct"] == 0.0
        assert deltas["exp-b"]["total_return_pct"] == pytest.approx(-3.0)

    def test_safety_flags_serialized(self) -> None:
        report = make_report()
        d = experiment_ledger_report_to_dict(report)
        flags = d["safety_flags"]
        assert flags["is_safe"] is True
        assert flags["no_exchange_connection"] is True
        assert flags["has_blocked_record"] is False

    def test_enum_values_are_strings(self) -> None:
        report = make_report()
        d = experiment_ledger_report_to_dict(report)
        assert d["comparison"]["records"][0]["state"] == "included"
        assert isinstance(d["comparison"]["records"][0]["state"], str)

    def test_datetime_isoformat(self) -> None:
        report = make_report()
        d = experiment_ledger_report_to_dict(report)
        assert isinstance(d["generated_at"], str)
        assert d["generated_at"].endswith("+00:00")


class TestJSONSerialization:
    def test_parseable(self) -> None:
        report = make_report(baseline="exp-a")
        text = experiment_ledger_report_to_json_text(report)
        parsed = json.loads(text)
        assert parsed["report_id"] == report.report_id
        assert len(parsed["comparison"]["records"]) == 2

    def test_deterministic(self) -> None:
        report = make_report(baseline="exp-a")
        t1 = experiment_ledger_report_to_json_text(report)
        t2 = experiment_ledger_report_to_json_text(report)
        assert t1 == t2

    def test_ends_with_newline(self) -> None:
        text = experiment_ledger_report_to_json_text(make_report())
        assert text.endswith("\n")

    def test_sort_keys(self) -> None:
        text = experiment_ledger_report_to_json_text(make_report())
        assert '"comparison"' in text
        assert '"data_quality"' in text


class TestCSVSerialization:
    def test_header_includes_expected_columns(self) -> None:
        report = make_report(baseline="exp-a")
        text = experiment_ledger_report_to_csv_text(report)
        reader = csv.reader(text.splitlines())
        header = next(reader)
        assert "report_id" in header
        assert "generated_at" in header
        assert "rank" in header
        assert "experiment_id" in header
        assert "source_kind" in header
        assert "run_id" in header
        assert "name" in header
        assert "state" in header
        assert "primary_metric" in header
        assert "total_return_pct" in header
        assert "delta_total_return_pct" in header
        assert "reason_codes" in header
        assert "tags" in header

    def test_rows_deterministic_and_ranked(self) -> None:
        report = make_report(baseline="exp-a")
        text = experiment_ledger_report_to_csv_text(report)
        reader = csv.DictReader(text.splitlines())
        rows = list(reader)
        assert len(rows) == 2
        assert rows[0]["experiment_id"] == "exp-a"
        assert rows[0]["rank"] == "1"
        assert rows[1]["experiment_id"] == "exp-b"
        assert rows[1]["rank"] == "2"
        assert rows[0]["delta_total_return_pct"] == "0.0"
        assert rows[1]["delta_total_return_pct"] == "-3.0"

    def test_display_name_override_in_csv(self) -> None:
        report = make_report()
        text = experiment_ledger_report_to_csv_text(report)
        reader = csv.DictReader(text.splitlines())
        rows = list(reader)
        assert rows[0]["name"] == "Override Alpha"

    def test_no_delta_columns_without_baseline(self) -> None:
        report = make_report()
        text = experiment_ledger_report_to_csv_text(report)
        header = text.splitlines()[0]
        assert "delta_" not in header

    def test_empty_metric_as_blank(self) -> None:
        snap = ExperimentMetricSnapshot(
            experiment_id="empty",
            run_id="empty",
            name="Empty",
            metrics={"total_return_pct": 5.0},
        )
        input_obj = ExperimentLedgerInput(metric_snapshots=(snap,), generated_at=ts(1))
        report = build_experiment_ledger_report(input_obj)
        text = experiment_ledger_report_to_csv_text(report)
        reader = csv.DictReader(text.splitlines())
        rows = list(reader)
        assert rows[0]["max_drawdown_pct"] == ""


class TestMarkdownSerialization:
    def test_starts_with_h1_and_safety_notice(self) -> None:
        report = make_report()
        text = experiment_ledger_report_to_markdown_text(report)
        lines = text.splitlines()
        assert lines[0] == "# Experiment Ledger Report"
        assert any(
            "Safety notice" in line and "human audit" in line for line in lines[:10]
        )

    def test_contains_required_sections(self) -> None:
        report = make_report(baseline="exp-a")
        text = experiment_ledger_report_to_markdown_text(report)
        assert "## Report Identity" in text
        assert "## Comparison Summary" in text
        assert "## Ranked Experiment Records" in text
        assert "## Baseline and Deltas" in text
        assert "## Data Quality" in text
        assert "## Safety Flags" in text

    def test_ranked_table_contains_records(self) -> None:
        report = make_report(baseline="exp-a")
        text = experiment_ledger_report_to_markdown_text(report)
        assert "exp-a" in text
        assert "exp-b" in text
        assert "Override Alpha" in text

    def test_no_trading_action_language(self) -> None:
        report = make_report(baseline="exp-a")
        text = experiment_ledger_report_to_markdown_text(report)
        lower = text.lower()
        assert "buy" not in lower
        assert "sell" not in lower
        assert "order" not in lower
        assert "execute" not in lower
        assert "leverage" not in lower
        assert "freqtrade" not in lower
        assert "binance" not in lower

    def test_audit_only_ranking_language(self) -> None:
        report = make_report()
        text = experiment_ledger_report_to_markdown_text(report)
        assert "audit-review" in text or "audit review" in text
        assert "not a recommendation" in text or "not recommendation" in text

    def test_escapes_pipes(self) -> None:
        snap = ExperimentMetricSnapshot(
            experiment_id="pipe|id",
            run_id="run",
            name="Pipe|Name",
            metrics={"total_return_pct": 1.0},
        )
        input_obj = ExperimentLedgerInput(metric_snapshots=(snap,), generated_at=ts(1))
        report = build_experiment_ledger_report(input_obj)
        text = experiment_ledger_report_to_markdown_text(report)
        assert "pipe\\|id" in text
        assert "Pipe\\|Name" in text


class TestAtomicWrites:
    def test_write_experiment_ledger_report_creates_all_files(self, tmp_path: Path) -> None:
        report = make_report(baseline="exp-a")
        json_path = tmp_path / "out.json"
        csv_path = tmp_path / "out.csv"
        md_path = tmp_path / "out.md"
        paths = write_experiment_ledger_report(report, json_path, csv_path, md_path)
        assert paths[0] == json_path
        assert paths[1] == csv_path
        assert paths[2] == md_path
        assert json_path.exists()
        assert csv_path.exists()
        assert md_path.exists()
        assert json.loads(json_path.read_text(encoding="utf-8"))["report_id"] == report.report_id
        assert csv_path.read_text(encoding="utf-8").startswith("report_id,")
        assert md_path.read_text(encoding="utf-8").startswith("# Experiment Ledger Report")

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        report = make_report()
        base = tmp_path / "nested" / "deep"
        json_path = base / "out.json"
        csv_path = base / "out.csv"
        md_path = base / "out.md"
        write_experiment_ledger_report(report, json_path, csv_path, md_path)
        assert json_path.exists()
        assert csv_path.exists()
        assert md_path.exists()

    def test_atomic_json_write(self, tmp_path: Path) -> None:
        report = make_report()
        path = tmp_path / "ledger.json"
        result = atomic_write_json_experiment_ledger_report(report, path)
        assert result == path
        assert path.exists()
        assert json.loads(path.read_text(encoding="utf-8"))["report_id"] == report.report_id

    def test_atomic_csv_write(self, tmp_path: Path) -> None:
        report = make_report()
        path = tmp_path / "records.csv"
        result = atomic_write_csv_experiment_ledger_report(report, path)
        assert result == path
        assert path.exists()
        assert path.read_text(encoding="utf-8").startswith("report_id,")

    def test_atomic_markdown_write(self, tmp_path: Path) -> None:
        report = make_report()
        path = tmp_path / "report.md"
        result = atomic_write_markdown_experiment_ledger_report(report, path)
        assert result == path
        assert path.exists()
        assert path.read_text(encoding="utf-8").startswith("# Experiment Ledger Report")

    def test_default_paths(self, tmp_path: Path) -> None:
        # Default paths are project-relative; override with tmp_path is not possible
        # without changing the cwd, so we only assert the constants are correct.
        assert DEFAULT_JSON_PATH == Path("data/experiment_ledger/experiment_ledger.json")
        assert DEFAULT_CSV_PATH == Path("data/experiment_ledger/experiment_records.csv")
        assert DEFAULT_MD_PATH == Path("reports/experiment_ledger/experiment_ledger.md")


class TestBlockedReportSerialization:
    def test_blocked_report_json(self) -> None:
        input_obj = ExperimentLedgerInput(generated_at=ts(1))
        report = ExperimentLedgerReport.blocked(input=input_obj, reason_code="UNSAFE_CONTENT")
        text = experiment_ledger_report_to_json_text(report)
        parsed = json.loads(text)
        assert parsed["reason_codes"] == ["UNSAFE_CONTENT"]
        assert parsed["comparison"]["records"] == []
        assert parsed["data_quality"]["total_inputs"] == 0

    def test_degraded_baseline_missing_markdown(self) -> None:
        report = make_report(baseline="missing")
        text = experiment_ledger_report_to_markdown_text(report)
        assert "BASELINE_MISSING" in text
        assert "baseline" in text.lower()


class TestNoMutation:
    def test_dict_does_not_mutate_report(self) -> None:
        report = make_report()
        original = experiment_ledger_report_to_json_text(report)
        experiment_ledger_report_to_dict(report)
        assert experiment_ledger_report_to_json_text(report) == original

    def test_csv_does_not_mutate_report(self) -> None:
        report = make_report()
        original = experiment_ledger_report_to_json_text(report)
        experiment_ledger_report_to_csv_text(report)
        assert experiment_ledger_report_to_json_text(report) == original

    def test_markdown_does_not_mutate_report(self) -> None:
        report = make_report()
        original = experiment_ledger_report_to_json_text(report)
        experiment_ledger_report_to_markdown_text(report)
        assert experiment_ledger_report_to_json_text(report) == original


class TestMetadataOpaque:
    def test_metadata_not_opened_or_validated(self) -> None:
        snap = ExperimentMetricSnapshot(
            experiment_id="meta",
            run_id="run",
            name="Meta",
            metrics={"total_return_pct": 1.0},
            metadata={"file": "/not/validated/path.csv", "url": "not.a.url.example"},
        )
        input_obj = ExperimentLedgerInput(
            metric_snapshots=(snap,),
            generated_at=ts(1),
            metadata={"ref": "/another/unvalidated/path"},
        )
        report = build_experiment_ledger_report(input_obj)
        json_text = experiment_ledger_report_to_json_text(report)
        md_text = experiment_ledger_report_to_markdown_text(report)
        # Record metadata is serialized in JSON as opaque strings.
        assert "/not/validated/path.csv" in json_text
        assert "not.a.url.example" in json_text
        # Input/report metadata appears in Markdown.
        assert "/another/unvalidated/path" in md_text
