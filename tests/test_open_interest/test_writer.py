"""Tests for hunter.open_interest.writer."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hunter.open_interest.engine import build_open_interest_report
from hunter.open_interest.models import (
    OpenInterestInput,
    OpenInterestObservation,
    OpenInterestReport,
    OpenInterestState,
)
from hunter.open_interest.writer import (
    DEFAULT_CSV_PATH,
    DEFAULT_JSON_PATH,
    DEFAULT_MD_PATH,
    _SAFETY_NOTICE,
    atomic_write_csv_open_interest_report,
    atomic_write_json_open_interest_report,
    atomic_write_markdown_open_interest_report,
    open_interest_report_to_csv_text,
    open_interest_report_to_dict,
    open_interest_report_to_json_text,
    open_interest_report_to_markdown,
    write_open_interest_report,
)


class TestFixtures:
    @staticmethod
    def _obs(day: int, close: float = 100.0, oi: float = 1_000_000.0) -> OpenInterestObservation:
        return OpenInterestObservation(
            timestamp=datetime(2026, 7, day, tzinfo=timezone.utc),
            open_interest=oi,
            close=close,
        )

    @staticmethod
    def _report(**kwargs: object) -> OpenInterestReport:
        rows = [
            TestFixtures._obs(day, 100.0 + day, 1_000_000.0 + day * 10_000)
            for day in range(1, 16)
        ]
        universe = [OpenInterestInput(pair="BTCUSDT", rows=rows)]
        return build_open_interest_report(
            universe=universe,
            report_id="test-report",
            generated_at=datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc),
            metadata={"source": "test"},
        )

    @staticmethod
    def _blocked_pair_report() -> OpenInterestReport:
        ready_rows = [
            TestFixtures._obs(day, 100.0 + day, 1_000_000.0 + day * 10_000)
            for day in range(1, 16)
        ]
        blocked_rows = [
            TestFixtures._obs(day, 100.0 + day, 1_000_000.0 + day * 10_000)
            for day in range(1, 16)
        ]
        universe = [
            OpenInterestInput(pair="BTCUSDT", rows=ready_rows),
            OpenInterestInput(pair="BLOCKED", rows=blocked_rows, metadata={"action": "buy"}),
        ]
        return build_open_interest_report(
            universe=universe,
            report_id="blocked-pair-report",
            generated_at=datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc),
        )

    @staticmethod
    def _blocked_report() -> OpenInterestReport:
        return OpenInterestReport.blocked(
            reason_code="UNSAFE_OPEN_INTEREST_CONTENT",
            report_id="blocked-report",
            generated_at=datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc),
        )

    @staticmethod
    def _insufficient_report() -> OpenInterestReport:
        rows = [TestFixtures._obs(day) for day in range(1, 5)]
        universe = [OpenInterestInput(pair="BTCUSDT", rows=rows)]
        return build_open_interest_report(
            universe=universe,
            report_id="insufficient-report",
            generated_at=datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc),
        )


class TestDictSerialization:
    def test_dict_basic_structure(self) -> None:
        report = TestFixtures._report()
        data = open_interest_report_to_dict(report)
        assert data["report_id"] == "test-report"
        assert data["kind"] == "open_interest_report"
        assert data["version"] == "0.25.0-dev"
        assert data["source_spec"] == "SPEC-026"
        assert "config" in data
        assert "safety_flags" in data
        assert "scores" in data
        assert "universe_summary" in data

    def test_datetime_serialized_as_iso(self) -> None:
        report = TestFixtures._report()
        data = open_interest_report_to_dict(report)
        assert data["generated_at"] == "2026-07-01T12:00:00+00:00"

    def test_enum_serialized_as_string(self) -> None:
        report = TestFixtures._report()
        data = open_interest_report_to_dict(report)
        assert data["scores"][0]["state"] == "ready"
        assert data["scores"][0]["positioning"] in {
            "price_up_oi_up",
            "price_up_oi_down",
            "price_down_oi_up",
            "price_down_oi_down",
            "mixed",
        }

    def test_tuple_serialized_as_list(self) -> None:
        report = TestFixtures._report()
        data = open_interest_report_to_dict(report)
        assert isinstance(data["scores"], list)
        assert isinstance(data["scores"][0]["reason_codes"], list)
        assert isinstance(data["config"]["lookback_periods"], list)

    def test_mapping_serialized_as_sorted_dict(self) -> None:
        report = TestFixtures._report()
        data = open_interest_report_to_dict(report)
        assert data["metadata"] == {"source": "test"}
        assert list(data["scores"][0]["sub_scores"].keys()) == sorted(
            data["scores"][0]["sub_scores"].keys()
        )

    def test_float_rounding(self) -> None:
        report = TestFixtures._report()
        data = open_interest_report_to_dict(report)
        assert isinstance(data["scores"][0]["total_score"], float)
        # total_score should be rounded to 2 decimals
        assert round(data["scores"][0]["total_score"], 2) == data["scores"][0]["total_score"]


class TestJsonText:
    def test_json_text_deterministic(self) -> None:
        report = TestFixtures._report()
        text1 = open_interest_report_to_json_text(report)
        text2 = open_interest_report_to_json_text(report)
        assert text1 == text2
        assert text1.endswith("\n")

    def test_json_text_is_valid_json(self) -> None:
        report = TestFixtures._report()
        text = open_interest_report_to_json_text(report)
        parsed = json.loads(text)
        assert parsed["report_id"] == "test-report"

    def test_json_text_sort_keys(self) -> None:
        report = TestFixtures._report()
        text = open_interest_report_to_json_text(report)
        lines = text.splitlines()
        # Top-level keys should be sorted alphabetically.
        top_keys = [line.strip().strip('"').split(":")[0] for line in lines if line.startswith('  "')]
        assert top_keys == sorted(top_keys)

    def test_json_text_ensure_ascii_false(self) -> None:
        report = TestFixtures._report()
        text = open_interest_report_to_json_text(report)
        # No unicode escapes in ASCII-safe content.
        assert "\\u" not in text


class TestCsvText:
    def test_csv_header_exact_order(self) -> None:
        report = TestFixtures._report()
        text = open_interest_report_to_csv_text(report)
        reader = csv.reader(io.StringIO(text))
        header = next(reader)
        assert header == [
            "report_id",
            "generated_at",
            "pair",
            "state",
            "positioning",
            "trend",
            "funding_context",
            "total_score",
            "oi_change_1d",
            "oi_change_3d",
            "oi_change_7d",
            "oi_change_14d",
            "price_change_1d",
            "price_change_3d",
            "price_change_7d",
            "price_change_14d",
            "latest_oi",
            "latest_price",
            "latest_funding_rate",
            "reason_codes",
            "human_note",
        ]

    def test_csv_row_count(self) -> None:
        report = TestFixtures._report()
        text = open_interest_report_to_csv_text(report)
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
        assert len(rows) == 2  # header + 1 score

    def test_csv_none_values_empty(self) -> None:
        # Report with a blocked pair has None latest_* fields on the blocked score.
        report = TestFixtures._blocked_pair_report()
        text = open_interest_report_to_csv_text(report)
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
        assert len(rows) == 3  # header + 2 scores
        blocked_row = [r for r in rows[1:] if r[2] == "BLOCKED"][0]
        # latest_oi, latest_price, latest_funding_rate should be empty
        assert blocked_row[16] == ""
        assert blocked_row[17] == ""
        assert blocked_row[18] == ""

    def test_csv_reason_codes_pipe_delimited(self) -> None:
        report = TestFixtures._insufficient_report()
        text = open_interest_report_to_csv_text(report)
        reader = csv.reader(io.StringIO(text))
        rows = list(reader)
        data_row = rows[1]
        assert "|" in data_row[19]

    def test_csv_trailing_newline(self) -> None:
        report = TestFixtures._report()
        text = open_interest_report_to_csv_text(report)
        assert text.endswith("\n")


class TestMarkdown:
    def test_markdown_starts_with_h1(self) -> None:
        report = TestFixtures._report()
        text = open_interest_report_to_markdown(report)
        assert text.startswith("# Open Interest Report")

    def test_safety_notice_immediately_after_h1(self) -> None:
        report = TestFixtures._report()
        text = open_interest_report_to_markdown(report)
        lines = text.splitlines()
        assert lines[0] == "# Open Interest Report"
        assert lines[1] == ""
        assert lines[2].startswith("> ")
        assert _SAFETY_NOTICE in lines[2]

    def test_no_actionable_order_instructions(self) -> None:
        report = TestFixtures._report()
        text = open_interest_report_to_markdown(report).lower()
        forbidden = ["buy", "sell", "place order", "execute", "go live", "production ready"]
        for term in forbidden:
            assert term not in text

    def test_markdown_contains_report_info(self) -> None:
        report = TestFixtures._report()
        text = open_interest_report_to_markdown(report)
        assert "## Report Info" in text
        assert "test-report" in text
        assert "SPEC-026" in text

    def test_markdown_contains_universe_summary(self) -> None:
        report = TestFixtures._report()
        text = open_interest_report_to_markdown(report)
        assert "## Universe Summary" in text
        assert "total_pairs" in text

    def test_markdown_contains_data_quality(self) -> None:
        report = TestFixtures._report()
        text = open_interest_report_to_markdown(report)
        assert "## Data Quality" in text

    def test_markdown_contains_scores_table(self) -> None:
        report = TestFixtures._report()
        text = open_interest_report_to_markdown(report)
        assert "## Scores" in text
        assert "| pair | state | positioning | trend |" in text
        assert "BTCUSDT" in text

    def test_markdown_contains_period_changes(self) -> None:
        report = TestFixtures._report()
        text = open_interest_report_to_markdown(report)
        assert "## Period Changes" in text

    def test_markdown_contains_funding_context(self) -> None:
        report = TestFixtures._report()
        text = open_interest_report_to_markdown(report)
        assert "## Funding Context" in text

    def test_markdown_contains_safety_flags(self) -> None:
        report = TestFixtures._report()
        text = open_interest_report_to_markdown(report)
        assert "## Safety Flags" in text

    def test_markdown_contains_reason_codes(self) -> None:
        report = TestFixtures._report()
        text = open_interest_report_to_markdown(report)
        assert "## Report Reason Codes" in text

    def test_markdown_metadata_section(self) -> None:
        report = TestFixtures._report()
        text = open_interest_report_to_markdown(report)
        assert "## Metadata" in text
        assert "source" in text

    def test_markdown_trailing_newline(self) -> None:
        report = TestFixtures._report()
        text = open_interest_report_to_markdown(report)
        assert text.strip()


class TestAtomicWrites:
    def test_atomic_json_write_creates_parent_directory(self, tmp_path: Path) -> None:
        report = TestFixtures._report()
        target = tmp_path / "nested" / "report.json"
        result = atomic_write_json_open_interest_report(report, target)
        assert result == target
        assert target.exists()
        assert json.loads(target.read_text(encoding="utf-8"))["report_id"] == "test-report"

    def test_atomic_csv_write_creates_parent_directory(self, tmp_path: Path) -> None:
        report = TestFixtures._report()
        target = tmp_path / "nested" / "scores.csv"
        result = atomic_write_csv_open_interest_report(report, target)
        assert result == target
        assert target.exists()
        content = target.read_text(encoding="utf-8")
        assert "BTCUSDT" in content

    def test_atomic_markdown_write_creates_parent_directory(self, tmp_path: Path) -> None:
        report = TestFixtures._report()
        target = tmp_path / "nested" / "report.md"
        result = atomic_write_markdown_open_interest_report(report, target)
        assert result == target
        assert target.exists()
        content = target.read_text(encoding="utf-8")
        assert "# Open Interest Report" in content

    def test_no_temp_file_left_behind(self, tmp_path: Path) -> None:
        report = TestFixtures._report()
        target = tmp_path / "report.json"
        atomic_write_json_open_interest_report(report, target)
        assert not (tmp_path / "report.json.tmp").exists()

    def test_blocked_report_json_write(self, tmp_path: Path) -> None:
        report = TestFixtures._blocked_report()
        target = tmp_path / "blocked.json"
        atomic_write_json_open_interest_report(report, target)
        data = json.loads(target.read_text(encoding="utf-8"))
        assert data["scores"] == []
        assert data["universe_summary"]["total_pairs"] == 0

    def test_insufficient_report_csv_write(self, tmp_path: Path) -> None:
        report = TestFixtures._insufficient_report()
        target = tmp_path / "insufficient.csv"
        atomic_write_csv_open_interest_report(report, target)
        content = target.read_text(encoding="utf-8")
        assert "insufficient_data" in content


class TestWriteOpenInterestReport:
    def test_writes_all_artifacts(self, tmp_path: Path) -> None:
        report = TestFixtures._report()
        json_path = tmp_path / "out.json"
        csv_path = tmp_path / "out.csv"
        md_path = tmp_path / "out.md"
        json_out, csv_out, md_out = write_open_interest_report(
            report, json_path=json_path, csv_path=csv_path, md_path=md_path
        )
        assert json_out == json_path
        assert csv_out == csv_path
        assert md_out == md_path
        assert json_path.exists()
        assert csv_path.exists()
        assert md_path.exists()

    def test_can_skip_formats(self, tmp_path: Path) -> None:
        report = TestFixtures._report()
        json_out, csv_out, md_out = write_open_interest_report(
            report, json_path=tmp_path / "out.json", csv_path=None, md_path=None
        )
        assert json_out is not None
        assert csv_out is None
        assert md_out is None

    def test_default_paths(self, tmp_path: Path) -> None:
        # Monkey-patch defaults to use tmp_path for this test.
        import hunter.open_interest.writer as writer_module
        original_json = writer_module.DEFAULT_JSON_PATH
        original_csv = writer_module.DEFAULT_CSV_PATH
        original_md = writer_module.DEFAULT_MD_PATH
        try:
            writer_module.DEFAULT_JSON_PATH = tmp_path / "default.json"
            writer_module.DEFAULT_CSV_PATH = tmp_path / "default.csv"
            writer_module.DEFAULT_MD_PATH = tmp_path / "default.md"
            report = TestFixtures._report()
            json_out, csv_out, md_out = write_open_interest_report(report)
            assert json_out == tmp_path / "default.json"
            assert csv_out == tmp_path / "default.csv"
            assert md_out == tmp_path / "default.md"
            assert json_out.exists()
            assert csv_out.exists()
            assert md_out.exists()
        finally:
            writer_module.DEFAULT_JSON_PATH = original_json
            writer_module.DEFAULT_CSV_PATH = original_csv
            writer_module.DEFAULT_MD_PATH = original_md


class TestWriterSafety:
    def test_writer_does_not_mutate_report(self) -> None:
        report = TestFixtures._report()
        original_id = report.report_id
        open_interest_report_to_json_text(report)
        open_interest_report_to_csv_text(report)
        open_interest_report_to_markdown(report)
        assert report.report_id == original_id

    def test_default_paths_exported(self) -> None:
        from hunter.open_interest import DEFAULT_CSV_PATH, DEFAULT_JSON_PATH, DEFAULT_MD_PATH
        assert DEFAULT_JSON_PATH == Path("data/open_interest/latest_open_interest_report.json")
        assert DEFAULT_CSV_PATH == Path("data/open_interest/latest_open_interest_scores.csv")
        assert DEFAULT_MD_PATH == Path("reports/open_interest/latest_open_interest_report.md")
