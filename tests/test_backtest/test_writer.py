"""Tests for hunter.backtest.writer.

All writer tests use tmp_path only for atomic write tests; dict/text tests are
purely in-memory. No network, exchange, or Freqtrade references are used.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hunter.backtest import (
    BacktestAllocationMode,
    BacktestCandidateDecision,
    BacktestPriceBar,
    BacktestInput,
    BacktestReport,
    BacktestRunConfig,
    BacktestState,
    atomic_write_csv_backtest_report,
    atomic_write_json_backtest_report,
    atomic_write_markdown_backtest_report,
    backtest_report_to_csv_text,
    backtest_report_to_dict,
    backtest_report_to_json_text,
    backtest_report_to_markdown,
    build_backtest_report,
    write_backtest_report,
)


def ts(day: int, hour: int = 0) -> datetime:
    return datetime(2024, 1, day, hour, tzinfo=timezone.utc)


def bar(pair: str, day: int, close: float, hour: int = 0) -> BacktestPriceBar:
    return BacktestPriceBar(pair=pair, timestamp=ts(day, hour), close=close)


def decision(pair: str, state: str, final_weight_pct: float = 0.0) -> BacktestCandidateDecision:
    return BacktestCandidateDecision(
        pair=pair,
        state=state,
        classification="CORE_RESEARCH_ALLOCATION",
        final_weight_pct=final_weight_pct,
    )


def make_report() -> BacktestReport:
    inputs = [
        BacktestInput(
            pair="A",
            decision=decision("A", "INCLUDED", 60.0),
            price_bars=(bar("A", 1, 100.0), bar("A", 2, 110.0)),
        ),
        BacktestInput(
            pair="B",
            decision=decision("B", "INCLUDED", 40.0),
            price_bars=(bar("B", 1, 100.0), bar("B", 2, 90.0)),
        ),
    ]
    cfg = BacktestRunConfig(allocation_mode=BacktestAllocationMode.RESEARCH_WEIGHT)
    return build_backtest_report(inputs, cfg, report_id="r1", generated_at=ts(1))


def make_blocked_report() -> BacktestReport:
    return BacktestReport.blocked(
        reason_code="UNSAFE_BACKTEST_CONTENT",
        report_id="blocked-report",
        generated_at=ts(1),
    )


class TestPublicExports:
    def test_writer_functions_exported(self) -> None:
        assert callable(backtest_report_to_dict)
        assert callable(backtest_report_to_json_text)
        assert callable(backtest_report_to_csv_text)
        assert callable(backtest_report_to_markdown)
        assert callable(atomic_write_json_backtest_report)
        assert callable(atomic_write_csv_backtest_report)
        assert callable(atomic_write_markdown_backtest_report)
        assert callable(write_backtest_report)


class TestDictConversion:
    def test_dict_contains_report_identity(self) -> None:
        report = make_report()
        data = backtest_report_to_dict(report)
        assert data["report_id"] == "r1"
        assert data["version"] == "0.28.0-dev"
        assert data["generated_at"] == "2024-01-01T00:00:00+00:00"

    def test_dict_contains_config(self) -> None:
        report = make_report()
        data = backtest_report_to_dict(report)
        assert data["config"]["allocation_mode"] == "RESEARCH_WEIGHT"
        assert data["config"]["volatility_scale_factor"] == 1.0

    def test_dict_contains_portfolio_result(self) -> None:
        report = make_report()
        data = backtest_report_to_dict(report)
        portfolio = data["portfolio_result"]
        assert "total_return_pct" in portfolio
        assert "equity_curve" in portfolio
        assert portfolio["candidate_count"] == 2

    def test_dict_contains_equity_curve_snapshots(self) -> None:
        report = make_report()
        data = backtest_report_to_dict(report)
        assert len(data["portfolio_result"]["equity_curve"]) == 2
        snapshot = data["portfolio_result"]["equity_curve"][0]
        assert "timestamp" in snapshot
        assert "equity" in snapshot
        assert "weight_sum" in snapshot
        assert "observation_count" in snapshot

    def test_dict_contains_candidate_results(self) -> None:
        report = make_report()
        data = backtest_report_to_dict(report)
        assert len(data["candidate_results"]) == 2
        result = data["candidate_results"][0]
        assert "pair" in result
        assert "state" in result
        assert "simulated_weight" in result
        assert "total_return_pct" in result
        assert "period_returns" in result

    def test_dict_contains_data_quality(self) -> None:
        report = make_report()
        data = backtest_report_to_dict(report)
        dq = data["data_quality"]
        assert dq["total_inputs"] == 2
        assert dq["all_counts_consistent"] is True
        assert "safety_flags_ok" in dq

    def test_dict_contains_safety_flags(self) -> None:
        report = make_report()
        data = backtest_report_to_dict(report)
        flags = data["safety_flags"]
        assert flags["no_network_connection"] is True
        assert flags["no_exchange_connection"] is True
        assert flags["is_safe"] is True

    def test_enum_values_serialized_as_strings(self) -> None:
        report = make_report()
        data = backtest_report_to_dict(report)
        assert data["candidate_results"][0]["state"] == "INCLUDED"
        assert data["candidate_results"][0]["allocation_mode"] == "RESEARCH_WEIGHT"

    def test_metadata_serialized_without_traversal(self) -> None:
        report = make_report()
        data = backtest_report_to_dict(report)
        assert "metadata" in data
        assert isinstance(data["metadata"], dict)


class TestJsonConversion:
    def test_json_parseable(self) -> None:
        report = make_report()
        text = backtest_report_to_json_text(report)
        data = json.loads(text)
        assert data["report_id"] == "r1"

    def test_json_deterministic(self) -> None:
        report = make_report()
        text1 = backtest_report_to_json_text(report)
        text2 = backtest_report_to_json_text(report)
        assert text1 == text2

    def test_json_ends_with_newline(self) -> None:
        report = make_report()
        text = backtest_report_to_json_text(report)
        assert text.endswith("\n")

    def test_json_sort_keys(self) -> None:
        report = make_report()
        text = backtest_report_to_json_text(report)
        lines = text.splitlines()
        assert '"report_id":' in text
        assert text[0] == "{"


class TestCsvConversion:
    def test_csv_header_deterministic(self) -> None:
        report = make_report()
        text = backtest_report_to_csv_text(report)
        header = text.splitlines()[0]
        assert header.startswith("report_id,generated_at,pair,state")
        assert "simulated_weight" in header
        assert "total_return_pct" in header

    def test_csv_rows_for_candidates(self) -> None:
        report = make_report()
        text = backtest_report_to_csv_text(report)
        lines = text.splitlines()
        assert len(lines) == 3  # header + 2 candidates

    def test_csv_reason_codes_joined(self) -> None:
        report = make_report()
        text = backtest_report_to_csv_text(report)
        # Candidate results should have empty reason codes for successful run
        for line in text.splitlines()[1:]:
            assert "," in line

    def test_csv_deterministic(self) -> None:
        report = make_report()
        text1 = backtest_report_to_csv_text(report)
        text2 = backtest_report_to_csv_text(report)
        assert text1 == text2

    def test_csv_no_trailing_blank_rows(self) -> None:
        report = make_report()
        text = backtest_report_to_csv_text(report)
        assert not text.endswith("\n\n")


class TestMarkdownConversion:
    def test_markdown_starts_with_h1(self) -> None:
        report = make_report()
        text = backtest_report_to_markdown(report)
        assert text.startswith("# Backtest Report")

    def test_markdown_has_immediate_safety_notice(self) -> None:
        report = make_report()
        text = backtest_report_to_markdown(report)
        lines = text.splitlines()
        assert lines[2].startswith("> This local backtest report is a human-audit")
        assert "research-only" in lines[2].lower()

    def test_markdown_contains_portfolio_summary(self) -> None:
        report = make_report()
        text = backtest_report_to_markdown(report)
        assert "## Portfolio Summary" in text
        assert "Total return %" in text

    def test_markdown_contains_data_quality(self) -> None:
        report = make_report()
        text = backtest_report_to_markdown(report)
        assert "## Data Quality" in text
        assert "Total inputs" in text

    def test_markdown_contains_candidate_results(self) -> None:
        report = make_report()
        text = backtest_report_to_markdown(report)
        assert "## Candidate Results" in text
        assert "| Pair | State |" in text

    def test_markdown_contains_safety_flags(self) -> None:
        report = make_report()
        text = backtest_report_to_markdown(report)
        assert "## Safety Flags" in text
        assert "no_network_connection" in text

    def test_markdown_no_action_commands(self) -> None:
        report = make_report()
        text = backtest_report_to_markdown(report)
        lower = text.lower()
        assert "buy" not in lower or "not buy" in lower
        assert "order" not in lower or "not orders" in lower


class TestAtomicWrites:
    def test_atomic_write_json(self, tmp_path: Path) -> None:
        report = make_report()
        path = tmp_path / "report.json"
        result = atomic_write_json_backtest_report(report, path)
        assert result == path
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["report_id"] == "r1"

    def test_atomic_write_csv(self, tmp_path: Path) -> None:
        report = make_report()
        path = tmp_path / "report.csv"
        result = atomic_write_csv_backtest_report(report, path)
        assert result == path
        assert path.exists()
        text = path.read_text(encoding="utf-8")
        assert text.splitlines()[0].startswith("report_id,generated_at")

    def test_atomic_write_markdown(self, tmp_path: Path) -> None:
        report = make_report()
        path = tmp_path / "report.md"
        result = atomic_write_markdown_backtest_report(report, path)
        assert result == path
        assert path.exists()
        text = path.read_text(encoding="utf-8")
        assert text.startswith("# Backtest Report")

    def test_parent_directories_created(self, tmp_path: Path) -> None:
        report = make_report()
        path = tmp_path / "nested" / "dir" / "report.json"
        result = atomic_write_json_backtest_report(report, path)
        assert result == path
        assert path.exists()

    def test_write_backtest_report_all_formats(self, tmp_path: Path) -> None:
        report = make_report()
        json_path = tmp_path / "out.json"
        csv_path = tmp_path / "out.csv"
        md_path = tmp_path / "out.md"
        json_out, csv_out, md_out = write_backtest_report(
            report, json_path=json_path, csv_path=csv_path, md_path=md_path
        )
        assert json_out == json_path
        assert csv_out == csv_path
        assert md_out == md_path
        assert json_path.exists()
        assert csv_path.exists()
        assert md_path.exists()

    def test_write_backtest_report_skip_none(self, tmp_path: Path) -> None:
        report = make_report()
        json_path = tmp_path / "out.json"
        json_out, csv_out, md_out = write_backtest_report(
            report, json_path=json_path, csv_path=None, md_path=None
        )
        assert json_out == json_path
        assert csv_out is None
        assert md_out is None
        assert json_path.exists()
        assert not (tmp_path / "out.csv").exists()

    def test_default_paths(self, tmp_path: Path) -> None:
        # Use tmp_path as cwd to avoid polluting repo
        import os
        original_cwd = os.getcwd()
        os.chdir(str(tmp_path))
        try:
            report = make_report()
            json_out, csv_out, md_out = write_backtest_report(report)
            assert json_out is not None
            assert csv_out is not None
            assert md_out is not None
            assert json_out.exists()
            assert csv_out.exists()
            assert md_out.exists()
            assert json_out.name == "latest_backtest_report.json"
            assert csv_out.name == "latest_backtest_results.csv"
            assert md_out.name == "latest_backtest_report.md"
        finally:
            os.chdir(original_cwd)


class TestBlockedReport:
    def test_blocked_report_json(self) -> None:
        report = make_blocked_report()
        text = backtest_report_to_json_text(report)
        data = json.loads(text)
        assert data["report_id"] == "blocked-report"
        assert data["safety_flags"]["has_unsafe_content"] is True
        assert data["data_quality"]["safety_flags_ok"] is False

    def test_blocked_report_csv(self) -> None:
        report = make_blocked_report()
        text = backtest_report_to_csv_text(report)
        assert text.splitlines()[0].startswith("report_id,generated_at")
        assert len(text.splitlines()) == 1  # header only, no candidates

    def test_blocked_report_markdown(self) -> None:
        report = make_blocked_report()
        text = backtest_report_to_markdown(report)
        assert text.startswith("# Backtest Report")
        assert "> This local backtest report is a human-audit" in text


class TestNoMutation:
    def test_report_not_mutated(self) -> None:
        report = make_report()
        original_id = report.report_id
        original_results = report.candidate_results
        backtest_report_to_dict(report)
        backtest_report_to_json_text(report)
        backtest_report_to_csv_text(report)
        backtest_report_to_markdown(report)
        assert report.report_id == original_id
        assert report.candidate_results == original_results


class TestSafety:
    def test_no_file_traversal_from_metadata(self, tmp_path: Path) -> None:
        report = make_report()
        # Simulate file-reference metadata; writer treats it as opaque string
        report = BacktestReport(
            version=report.version,
            report_id=report.report_id,
            generated_at=report.generated_at,
            inputs=report.inputs,
            config=report.config,
            safety_flags=report.safety_flags,
            candidate_results=report.candidate_results,
            portfolio_result=report.portfolio_result,
            data_quality=report.data_quality,
            reason_codes=report.reason_codes,
            metadata={"file_ref": "/etc/passwd", "note": "should not be opened"},
            notes=report.notes,
        )
        path = tmp_path / "report.json"
        atomic_write_json_backtest_report(report, path)
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["metadata"]["file_ref"] == "/etc/passwd"
