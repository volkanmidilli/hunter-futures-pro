"""Integration tests for hunter.experiment_ledger.

End-to-end flows covering normalization, comparison, ranking, safety, and
writer output. All tests use in-memory inputs and tmp_path only. No network,
exchange, Freqtrade, database, Web UI, or real trading semantics are used.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from hunter.backtest import (
    BacktestAllocationMode,
    BacktestCandidateDecision,
    BacktestInput,
    BacktestPriceBar,
    BacktestRunConfig,
    build_backtest_report,
)
from hunter.experiment_ledger import (
    BASELINE_MISSING,
    BACKTEST_SOURCE_KIND,
    DUPLICATE_ID,
    EXPERIMENT_LEDGER_VERSION,
    INVALID_METRICS,
    METRIC_SNAPSHOT_SOURCE_KIND,
    MISSING_REQUIRED_FIELDS,
    RUN_SOURCE_KIND,
    UNSAFE_CONTENT,
    ExperimentComparisonConfig,
    ExperimentLedgerInput,
    ExperimentLedgerReport,
    ExperimentMetricSnapshot,
    ExperimentState,
    build_experiment_ledger_report,
    experiment_ledger_report_to_csv_text,
    experiment_ledger_report_to_dict,
    experiment_ledger_report_to_json_text,
    experiment_ledger_report_to_markdown_text,
    write_experiment_ledger_report,
)
from hunter.run_orchestrator import (
    ResearchRunConfig,
    ResearchRunPlan,
    ResearchRunStep,
    ResearchRunStepKind,
    build_research_run_result,
)


def ts(day: int = 1, hour: int = 0) -> datetime:
    return datetime(2024, 1, day, hour, tzinfo=timezone.utc)


def make_bar(pair: str, day: int, close: float) -> BacktestPriceBar:
    return BacktestPriceBar(
        pair=pair,
        timestamp=ts(day),
        close=close,
    )


def make_backtest_input(pair: str, closes: list[float]) -> BacktestInput:
    decision = BacktestCandidateDecision(
        pair=pair,
        state="INCLUDED",
        classification="CORE_RESEARCH_ALLOCATION",
        final_weight_pct=0.0,
    )
    bars = tuple(make_bar(pair, i + 1, close) for i, close in enumerate(closes))
    return BacktestInput(pair=pair, decision=decision, price_bars=bars)


def make_backtest_report(
    report_id: str = "bt-1",
    generated_at: datetime | None = None,
) -> Any:
    inputs = [
        make_backtest_input("A", [100.0, 110.0, 121.0]),
        make_backtest_input("B", [100.0, 90.0, 80.0]),
    ]
    cfg = BacktestRunConfig(allocation_mode=BacktestAllocationMode.EQUAL_WEIGHT)
    return build_backtest_report(inputs, cfg, report_id=report_id, generated_at=generated_at)


def make_run_result(
    run_id: str = "run-1",
    generated_at: datetime | None = None,
) -> Any:
    backtest_input = make_backtest_input("A", [100.0, 110.0])
    backtest_config = BacktestRunConfig(allocation_mode=BacktestAllocationMode.EQUAL_WEIGHT)
    step_inputs: dict[str, Any] = {"inputs": (backtest_input,), "config": backtest_config}
    step = ResearchRunStep(
        kind=ResearchRunStepKind.BACKTEST,
        step_id="b1",
        inputs=step_inputs,
    )
    plan = ResearchRunPlan(run_id=run_id, steps=(step,))
    config = ResearchRunConfig(generated_at=generated_at or ts(1), write_artifacts=False)
    return build_research_run_result(plan, config)


# ---------------------------------------------------------------------------
# End-to-end successful ledger
# ---------------------------------------------------------------------------


class TestEndToEndLedger:
    def test_successful_ledger_with_all_source_kinds(self) -> None:
        backtest = make_backtest_report(report_id="bt-alpha", generated_at=ts(1))
        run = make_run_result(run_id="run-alpha", generated_at=ts(1))
        snapshot = ExperimentMetricSnapshot(
            experiment_id="snap-alpha",
            run_id="snap-alpha",
            name="Snapshot Alpha",
            metrics={
                "total_return_pct": 5.0,
                "max_drawdown_pct": 2.0,
                "volatility_pct": 1.0,
                "win_rate_pct": 50.0,
                "observation_count": 30,
                "missing_data_count": 0,
                "blocked_count": 0,
                "insufficient_data_count": 0,
            },
            generated_at=ts(1),
        )
        inp = ExperimentLedgerInput(
            backtest_reports=(backtest,),
            run_results=(run,),
            metric_snapshots=(snapshot,),
            generated_at=ts(2),
            metadata={"ledger": "integration"},
        )
        config = ExperimentComparisonConfig(
            primary_metric="total_return_pct",
            generated_at=ts(2),
        )
        report = build_experiment_ledger_report(inp, config)

        assert isinstance(report, ExperimentLedgerReport)
        assert report.version == EXPERIMENT_LEDGER_VERSION
        assert report.generated_at == ts(2)
        # report_id is deterministic sha256(prefix)[:16].
        assert len(report.report_id) == 16
        assert all(c in "0123456789abcdef" for c in report.report_id)
        assert report.comparison.config.primary_metric == "total_return_pct"
        assert len(report.comparison.records) == 3
        assert report.data_quality.total_inputs == 3
        assert report.data_quality.normalized_records == 3
        assert report.data_quality.included_records >= 1
        assert report.safety_flags.is_safe is True
        assert any("human audit" in note.lower() for note in report.notes)
        assert any("not a trading signal" in note.lower() for note in report.notes)


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------


class TestNormalization:
    def test_backtest_report_maps_to_experiment_record(self) -> None:
        backtest = make_backtest_report(report_id="backtest-report-1", generated_at=ts(1))
        inp = ExperimentLedgerInput(backtest_reports=(backtest,), generated_at=ts(1))
        report = build_experiment_ledger_report(inp)
        record = report.comparison.records[0]
        assert record.source_kind == BACKTEST_SOURCE_KIND
        assert record.experiment_id == "backtest-report-1"
        assert record.run_id == "backtest-report-1"
        assert record.name == "backtest-report-1"
        assert record.state is ExperimentState.INCLUDED

    def test_run_result_maps_to_experiment_record(self) -> None:
        run = make_run_result(run_id="run-report-1", generated_at=ts(1))
        inp = ExperimentLedgerInput(run_results=(run,), generated_at=ts(1))
        report = build_experiment_ledger_report(inp)
        record = report.comparison.records[0]
        assert record.source_kind == RUN_SOURCE_KIND
        assert record.experiment_id == "run-report-1"
        assert record.run_id == "run-report-1"
        assert record.name == "run-report-1"
        assert record.state is ExperimentState.INCLUDED

    def test_metric_snapshot_uses_provided_fields(self) -> None:
        snapshot = ExperimentMetricSnapshot(
            experiment_id="exp-snap-1",
            run_id="run-snap-1",
            name="Snapshot One",
            metrics={"total_return_pct": 7.0},
            generated_at=ts(1),
        )
        inp = ExperimentLedgerInput(metric_snapshots=(snapshot,), generated_at=ts(1))
        report = build_experiment_ledger_report(inp)
        record = report.comparison.records[0]
        assert record.source_kind == METRIC_SNAPSHOT_SOURCE_KIND
        assert record.experiment_id == "exp-snap-1"
        assert record.run_id == "run-snap-1"
        assert record.name == "Snapshot One"
        assert record.state is ExperimentState.INCLUDED

    def test_metadata_display_name_override(self) -> None:
        backtest = make_backtest_report(report_id="bt-override", generated_at=ts(1))
        run = make_run_result(run_id="run-override", generated_at=ts(1))
        snapshot = ExperimentMetricSnapshot(
            experiment_id="snap-override",
            run_id="snap-override",
            name="Original Name",
            metrics={"total_return_pct": 3.0},
            generated_at=ts(1),
        )
        inp = ExperimentLedgerInput(
            backtest_reports=(backtest,),
            run_results=(run,),
            metric_snapshots=(snapshot,),
            generated_at=ts(1),
            metadata={
                "bt-override": "Backtest Display",
                "run-override": "Run Display",
                "snap-override": "Snapshot Display",
            },
        )
        report = build_experiment_ledger_report(inp)
        by_id = {r.experiment_id: r for r in report.comparison.records}
        assert by_id["bt-override"].name == "Backtest Display"
        assert by_id["run-override"].name == "Run Display"
        assert by_id["snap-override"].name == "Snapshot Display"


# ---------------------------------------------------------------------------
# Baseline and deltas
# ---------------------------------------------------------------------------


class TestBaselineAndDeltas:
    def test_omitted_baseline_no_baseline_missing(self) -> None:
        snapshot = ExperimentMetricSnapshot(
            experiment_id="only",
            run_id="only",
            name="Only",
            metrics={"total_return_pct": 5.0},
            generated_at=ts(1),
        )
        inp = ExperimentLedgerInput(metric_snapshots=(snapshot,), generated_at=ts(1))
        report = build_experiment_ledger_report(inp)
        assert BASELINE_MISSING not in report.comparison.reason_codes
        assert BASELINE_MISSING not in report.reason_codes
        assert report.comparison.baseline_record is None
        assert not report.comparison.deltas

    def test_provided_baseline_not_found_emits_degraded_success(self) -> None:
        snapshot = ExperimentMetricSnapshot(
            experiment_id="only",
            run_id="only",
            name="Only",
            metrics={"total_return_pct": 5.0},
            generated_at=ts(1),
        )
        inp = ExperimentLedgerInput(metric_snapshots=(snapshot,), generated_at=ts(1))
        config = ExperimentComparisonConfig(baseline_experiment_id="missing")
        report = build_experiment_ledger_report(inp, config)
        assert BASELINE_MISSING in report.comparison.reason_codes
        assert report.comparison.baseline_record is None
        assert not report.comparison.deltas
        assert report.safety_flags.has_missing_baseline is True
        assert report.safety_flags.is_safe is False

    def test_found_baseline_has_zero_deltas(self) -> None:
        base = ExperimentMetricSnapshot(
            experiment_id="base",
            run_id="base",
            name="Base",
            metrics={
                "total_return_pct": 10.0,
                "max_drawdown_pct": 5.0,
            },
            generated_at=ts(1),
        )
        other = ExperimentMetricSnapshot(
            experiment_id="other",
            run_id="other",
            name="Other",
            metrics={
                "total_return_pct": 15.0,
                "max_drawdown_pct": 4.0,
            },
            generated_at=ts(1),
        )
        inp = ExperimentLedgerInput(metric_snapshots=(base, other), generated_at=ts(1))
        config = ExperimentComparisonConfig(baseline_experiment_id="base")
        report = build_experiment_ledger_report(inp, config)
        assert report.comparison.baseline_record is not None
        assert report.comparison.baseline_record.experiment_id == "base"
        assert report.comparison.deltas["base"]["total_return_pct"] == 0.0
        assert report.comparison.deltas["base"]["max_drawdown_pct"] == 0.0
        assert report.comparison.deltas["other"]["total_return_pct"] == 5.0
        assert report.comparison.deltas["other"]["max_drawdown_pct"] == -1.0


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------


class TestRanking:
    def test_metric_present_ranks_before_metric_missing(self) -> None:
        with_metric = ExperimentMetricSnapshot(
            experiment_id="with-metric",
            run_id="with-metric",
            name="With Metric",
            metrics={"total_return_pct": -100.0},
            generated_at=ts(1),
        )
        without_metric = ExperimentMetricSnapshot(
            experiment_id="without-metric",
            run_id="without-metric",
            name="Without Metric",
            metrics={"observation_count": 10},
            generated_at=ts(1),
        )
        inp = ExperimentLedgerInput(
            metric_snapshots=(without_metric, with_metric),
            generated_at=ts(1),
        )
        config = ExperimentComparisonConfig(primary_metric="total_return_pct")
        report = build_experiment_ledger_report(inp, config)
        ids = [r.experiment_id for r in report.comparison.ranked_records]
        assert ids == ["with-metric", "without-metric"]

    def test_deterministic_tie_breakers(self) -> None:
        a = ExperimentMetricSnapshot(
            experiment_id="a",
            run_id="a",
            name="A",
            metrics={"total_return_pct": 5.0},
            generated_at=ts(1),
        )
        b = ExperimentMetricSnapshot(
            experiment_id="b",
            run_id="b",
            name="B",
            metrics={"total_return_pct": 5.0},
            generated_at=ts(1),
        )
        inp = ExperimentLedgerInput(metric_snapshots=(b, a), generated_at=ts(1))
        config = ExperimentComparisonConfig(primary_metric="total_return_pct")
        report1 = build_experiment_ledger_report(inp, config)
        report2 = build_experiment_ledger_report(inp, config)
        ids1 = [r.experiment_id for r in report1.comparison.ranked_records]
        ids2 = [r.experiment_id for r in report2.comparison.ranked_records]
        assert ids1 == ids2


# ---------------------------------------------------------------------------
# Visibility and counts
# ---------------------------------------------------------------------------


class TestVisibilityAndCounts:
    def test_include_blocked_false_omits_blocked_but_counts_them(self) -> None:
        safe = ExperimentMetricSnapshot(
            experiment_id="safe",
            run_id="safe",
            name="Safe",
            metrics={"total_return_pct": 1.0},
            generated_at=ts(1),
        )
        bad = ExperimentMetricSnapshot(
            experiment_id="bad",
            run_id="bad",
            name="Bad",
            metrics={"total_return_pct": float("nan")},
            generated_at=ts(1),
        )
        inp = ExperimentLedgerInput(
            metric_snapshots=(safe, bad),
            generated_at=ts(1),
        )
        config = ExperimentComparisonConfig(include_blocked=False)
        report = build_experiment_ledger_report(inp, config)
        assert len(report.comparison.ranked_records) == 1
        assert report.comparison.ranked_records[0].experiment_id == "safe"
        assert report.data_quality.total_inputs == 2
        assert report.data_quality.blocked_records == 1
        assert report.data_quality.included_records == 1

    def test_include_insufficient_false_omits_insufficient(self) -> None:
        full = ExperimentMetricSnapshot(
            experiment_id="full",
            run_id="full",
            name="Full",
            metrics={"total_return_pct": 1.0},
            generated_at=ts(1),
        )
        partial = ExperimentMetricSnapshot(
            experiment_id="partial",
            run_id="partial",
            name="Partial",
            metrics={},
            generated_at=ts(1),
        )
        inp = ExperimentLedgerInput(
            metric_snapshots=(full, partial),
            generated_at=ts(1),
        )
        config = ExperimentComparisonConfig(include_insufficient=False)
        report = build_experiment_ledger_report(inp, config)
        assert len(report.comparison.ranked_records) == 1
        assert report.comparison.ranked_records[0].experiment_id == "full"
        assert report.data_quality.total_inputs == 2
        assert report.data_quality.insufficient_records == 1
        assert report.data_quality.included_records == 1


# ---------------------------------------------------------------------------
# Unsafe / invalid / duplicate content
# ---------------------------------------------------------------------------


class TestUnsafeInvalidDuplicate:
    def test_unsafe_content_blocks_record(self) -> None:
        # "binance" is a forbidden term in the ledger safety scanner.
        snapshot = ExperimentMetricSnapshot(
            experiment_id="binance",
            run_id="binance",
            name="Unsafe Name",
            metrics={"total_return_pct": 1.0},
            generated_at=ts(1),
        )
        inp = ExperimentLedgerInput(metric_snapshots=(snapshot,), generated_at=ts(1))
        report = build_experiment_ledger_report(inp)
        record = report.comparison.records[0]
        assert record.state is ExperimentState.BLOCKED
        assert UNSAFE_CONTENT in record.reason_codes
        assert report.safety_flags.has_unsafe_content is True
        assert report.safety_flags.has_blocked_record is True

    def test_invalid_metric_blocks_record(self) -> None:
        snapshot = ExperimentMetricSnapshot(
            experiment_id="invalid",
            run_id="invalid",
            name="Invalid",
            metrics={"total_return_pct": float("nan")},
            generated_at=ts(1),
        )
        inp = ExperimentLedgerInput(metric_snapshots=(snapshot,), generated_at=ts(1))
        report = build_experiment_ledger_report(inp)
        record = report.comparison.records[0]
        assert record.state is ExperimentState.BLOCKED
        assert INVALID_METRICS in record.reason_codes
        assert report.safety_flags.has_invalid_record is True

    def test_duplicate_experiment_id_fail_closed(self) -> None:
        first = ExperimentMetricSnapshot(
            experiment_id="dup",
            run_id="dup-1",
            name="First",
            metrics={"total_return_pct": 1.0},
            generated_at=ts(1),
        )
        second = ExperimentMetricSnapshot(
            experiment_id="dup",
            run_id="dup-2",
            name="Second",
            metrics={"total_return_pct": 2.0},
            generated_at=ts(1),
        )
        inp = ExperimentLedgerInput(
            metric_snapshots=(first, second),
            generated_at=ts(1),
        )
        report = build_experiment_ledger_report(inp)
        states = {r.experiment_id: r.state for r in report.comparison.records}
        assert states["dup"] is ExperimentState.BLOCKED
        by_run = {r.run_id: r for r in report.comparison.records}
        assert DUPLICATE_ID in by_run["dup-2"].reason_codes
        assert report.data_quality.blocked_records == 1
        assert report.data_quality.included_records == 1

    def test_metadata_file_reference_remains_opaque(self) -> None:
        snapshot = ExperimentMetricSnapshot(
            experiment_id="opaque",
            run_id="opaque",
            name="Opaque",
            metrics={"total_return_pct": 1.0},
            metadata={"file": "/not/validated/path.csv"},
            generated_at=ts(1),
        )
        inp = ExperimentLedgerInput(
            metric_snapshots=(snapshot,),
            generated_at=ts(1),
            metadata={"ref": "/another/unvalidated/path"},
        )
        report = build_experiment_ledger_report(inp)
        json_text = experiment_ledger_report_to_json_text(report)
        md_text = experiment_ledger_report_to_markdown_text(report)
        assert "/not/validated/path.csv" in json_text
        assert "/another/unvalidated/path" in md_text
        # No file access is attempted; the writer only serializes strings.
        assert Path("/not/validated/path.csv").exists() is False


# ---------------------------------------------------------------------------
# Writer end-to-end
# ---------------------------------------------------------------------------


class TestWriterEndToEnd:
    def test_write_experiment_ledger_report_creates_all_artifacts(self, tmp_path: Path) -> None:
        base = ExperimentMetricSnapshot(
            experiment_id="base",
            run_id="base",
            name="Base",
            metrics={"total_return_pct": 10.0},
            generated_at=ts(1),
        )
        other = ExperimentMetricSnapshot(
            experiment_id="other",
            run_id="other",
            name="Other",
            metrics={"total_return_pct": 15.0},
            generated_at=ts(1),
        )
        inp = ExperimentLedgerInput(metric_snapshots=(base, other), generated_at=ts(1))
        config = ExperimentComparisonConfig(baseline_experiment_id="base")
        report = build_experiment_ledger_report(inp, config)

        json_path = tmp_path / "ledger.json"
        csv_path = tmp_path / "records.csv"
        md_path = tmp_path / "ledger.md"
        paths = write_experiment_ledger_report(report, json_path, csv_path, md_path)

        assert paths[0] == json_path
        assert paths[1] == csv_path
        assert paths[2] == md_path
        assert json_path.exists()
        assert csv_path.exists()
        assert md_path.exists()

        parsed = json.loads(json_path.read_text(encoding="utf-8"))
        assert parsed["report_id"] == report.report_id
        assert parsed["version"] == EXPERIMENT_LEDGER_VERSION

        reader = csv.DictReader(csv_path.read_text(encoding="utf-8").splitlines())
        rows = list(reader)
        assert len(rows) == 2
        ids = {row["experiment_id"] for row in rows}
        assert ids == {"base", "other"}
        assert any(row["delta_total_return_pct"] for row in rows)

        md_text = md_path.read_text(encoding="utf-8")
        lines = md_text.splitlines()
        assert lines[0] == "# Experiment Ledger Report"
        assert any(
            "Safety notice" in line and "human audit" in line for line in lines[:10]
        )


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_same_inputs_produce_identical_outputs(self) -> None:
        snapshot = ExperimentMetricSnapshot(
            experiment_id="det",
            run_id="det",
            name="Deterministic",
            metrics={"total_return_pct": 5.0},
            generated_at=ts(1),
        )
        inp = ExperimentLedgerInput(metric_snapshots=(snapshot,), generated_at=ts(1))
        config = ExperimentComparisonConfig(generated_at=ts(1))
        report1 = build_experiment_ledger_report(inp, config)
        report2 = build_experiment_ledger_report(inp, config)

        assert experiment_ledger_report_to_dict(report1) == experiment_ledger_report_to_dict(report2)
        assert experiment_ledger_report_to_json_text(report1) == experiment_ledger_report_to_json_text(report2)
        assert experiment_ledger_report_to_csv_text(report1) == experiment_ledger_report_to_csv_text(report2)
        assert experiment_ledger_report_to_markdown_text(report1) == experiment_ledger_report_to_markdown_text(report2)


# ---------------------------------------------------------------------------
# No mutation
# ---------------------------------------------------------------------------


class TestNoMutation:
    def test_inputs_unchanged_after_build(self) -> None:
        snapshot = ExperimentMetricSnapshot(
            experiment_id="no-mut",
            run_id="no-mut",
            name="No Mutation",
            metrics={"total_return_pct": 5.0},
            generated_at=ts(1),
        )
        meta = {"note": "preserve me"}
        inp = ExperimentLedgerInput(
            metric_snapshots=(snapshot,),
            generated_at=ts(1),
            metadata=meta,
        )
        original_input = inp
        build_experiment_ledger_report(inp)
        assert inp == original_input
        assert dict(inp.metadata) == {"note": "preserve me"}
        assert meta == {"note": "preserve me"}


# ---------------------------------------------------------------------------
# Public exports
# ---------------------------------------------------------------------------


class TestPublicExports:
    def test_public_api_exports(self) -> None:
        assert callable(build_experiment_ledger_report)
        assert callable(write_experiment_ledger_report)
        assert callable(experiment_ledger_report_to_dict)
        assert callable(experiment_ledger_report_to_json_text)
        assert callable(experiment_ledger_report_to_csv_text)
        assert callable(experiment_ledger_report_to_markdown_text)


# ---------------------------------------------------------------------------
# Safety boundaries
# ---------------------------------------------------------------------------


class TestSafetyBoundaries:
    def test_output_contains_research_only_language(self) -> None:
        snapshot = ExperimentMetricSnapshot(
            experiment_id="safe-lang",
            run_id="safe-lang",
            name="Safe Language",
            metrics={"total_return_pct": 5.0},
            generated_at=ts(1),
        )
        inp = ExperimentLedgerInput(metric_snapshots=(snapshot,), generated_at=ts(1))
        report = build_experiment_ledger_report(inp)
        md_text = experiment_ledger_report_to_markdown_text(report)
        lower = md_text.lower()
        assert "human audit" in lower
        assert "not a trading signal" in lower or "not trading signal" in lower
        assert "audit-review" in lower or "audit review" in lower

    def test_output_has_no_trading_action_language(self) -> None:
        snapshot = ExperimentMetricSnapshot(
            experiment_id="no-trading",
            run_id="no-trading",
            name="No Trading",
            metrics={"total_return_pct": 5.0},
            generated_at=ts(1),
        )
        inp = ExperimentLedgerInput(metric_snapshots=(snapshot,), generated_at=ts(1))
        report = build_experiment_ledger_report(inp)
        md_text = experiment_ledger_report_to_markdown_text(report)
        lower = md_text.lower()
        assert "buy" not in lower
        assert "sell" not in lower
        assert "order" not in lower
        assert "execute" not in lower
        assert "leverage" not in lower
        assert "freqtrade" not in lower
        assert "binance" not in lower
        assert "web ui" not in lower
