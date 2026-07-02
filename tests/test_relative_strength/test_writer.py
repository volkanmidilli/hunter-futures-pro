"""Tests for hunter.relative_strength.writer."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

import csv

from hunter.relative_strength.engine import build_relative_strength_report
from hunter.relative_strength.models import (
    OhlcvRow,
    RelativeStrengthConfig,
    RelativeStrengthDataQuality,
    RelativeStrengthDecision,
    RelativeStrengthInput,
    RelativeStrengthReport,
    RelativeStrengthScore,
    RelativeStrengthState,
)
from hunter.relative_strength.writer import (
    DEFAULT_CSV_PATH,
    DEFAULT_JSON_PATH,
    DEFAULT_MD_PATH,
    atomic_write_csv_relative_strength_report,
    atomic_write_json_relative_strength_report,
    atomic_write_markdown_relative_strength_report,
    relative_strength_report_to_csv_text,
    relative_strength_report_to_dict,
    relative_strength_report_to_json_text,
    relative_strength_report_to_markdown,
    write_relative_strength_report,
)


REPORT_ID = "test-report"


def _make_btc_rows(start_close: float = 100.0, count: int = 35) -> tuple[OhlcvRow, ...]:
    """Return deterministic BTC benchmark rows."""
    return tuple(
        OhlcvRow(timestamp=i, close=start_close + i * 0.1) for i in range(count)
    )


def _make_eth_rows(start_close: float = 50.0, count: int = 35) -> tuple[OhlcvRow, ...]:
    """Return deterministic ETH benchmark rows."""
    return tuple(
        OhlcvRow(timestamp=i, close=start_close + i * 0.05) for i in range(count)
    )


def _make_coin_rows(
    symbol: str,
    start_close: float,
    daily_return: float,
    count: int = 35,
) -> tuple[OhlcvRow, ...]:
    """Return deterministic coin rows with a constant daily return."""
    rows = []
    close = start_close
    for i in range(count):
        rows.append(OhlcvRow(timestamp=i, close=round(close, 6)))
        close *= 1 + daily_return
    return tuple(rows)


def _make_report() -> RelativeStrengthReport:
    """Build a small relative strength report for writer tests."""
    btc = _make_btc_rows()
    eth = _make_eth_rows()
    outperform = _make_coin_rows("SOL", 10.0, 0.02)
    underperform = _make_coin_rows("DOGE", 5.0, -0.015)
    universe = (
        RelativeStrengthInput(symbol="SOL", rows=outperform),
        RelativeStrengthInput(symbol="DOGE", rows=underperform),
    )
    config = RelativeStrengthConfig()
    return build_relative_strength_report(
        universe=universe,
        btc_benchmark=btc,
        eth_benchmark=eth,
        config=config,
        report_id=REPORT_ID,
        generated_at=datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
    )


def _make_blocked_report() -> RelativeStrengthReport:
    """Build a blocked relative strength report."""
    return RelativeStrengthReport.blocked(
        report_id=REPORT_ID,
        config=RelativeStrengthConfig(),
        reason_codes=("UNSAFE_INPUT_CONTENT",),
        generated_at=datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc),
    )


class TestDictSerialization:
    def test_round_trip_types(self) -> None:
        report = _make_report()
        data = relative_strength_report_to_dict(report)
        assert data["report_id"] == REPORT_ID
        assert data["kind"] == "relative_strength_report"
        assert data["version"] == "0.24.0-dev"
        assert data["source_spec"] == "SPEC-025"
        assert data["generated_at"] == "2026-01-15T12:00:00+00:00"
        assert isinstance(data["config"], dict)
        assert isinstance(data["safety_flags"], dict)
        assert isinstance(data["scores"], list)
        assert isinstance(data["universe_summary"], dict)
        assert isinstance(data["reason_codes"], list)
        assert isinstance(data["metadata"], dict)

    def test_enum_values_are_strings(self) -> None:
        report = _make_report()
        data = relative_strength_report_to_dict(report)
        score_data = data["scores"][0]
        assert isinstance(score_data["state"], str)
        assert isinstance(score_data["decision"], str)
        assert isinstance(score_data["base_benchmark"], str)
        assert score_data["state"] in {s.value for s in RelativeStrengthState}
        assert score_data["decision"] in {d.value for d in RelativeStrengthDecision}

    def test_tuples_are_lists(self) -> None:
        report = _make_report()
        data = relative_strength_report_to_dict(report)
        score_data = data["scores"][0]
        assert isinstance(score_data["period_returns"], list)
        assert isinstance(score_data["reason_codes"], list)
        assert isinstance(score_data["data_quality"]["missing_periods"], list)

    def test_metadata_is_plain_dict(self) -> None:
        report = _make_report()
        data = relative_strength_report_to_dict(report)
        assert isinstance(data["metadata"], dict)


class TestJsonText:
    def test_deterministic_output(self) -> None:
        report = _make_report()
        first = relative_strength_report_to_json_text(report)
        second = relative_strength_report_to_json_text(report)
        assert first == second
        assert first.endswith("\n")

    def test_is_valid_json(self) -> None:
        report = _make_report()
        text = relative_strength_report_to_json_text(report)
        data = json.loads(text)
        assert data["report_id"] == REPORT_ID


class TestCsvText:
    def test_header_and_rows(self) -> None:
        report = _make_report()
        text = relative_strength_report_to_csv_text(report)
        lines = text.strip().split("\n")
        assert lines[0].startswith("report_id")
        assert "pair" in lines[0]
        assert len(lines) == len(report.scores) + 1

    def test_none_values_empty(self) -> None:
        report = _make_report()
        score = report.scores[0]
        score_with_none = RelativeStrengthScore(
            symbol=score.symbol,
            base_benchmark=score.base_benchmark,
            state=score.state,
            decision=score.decision,
            total_score=score.total_score,
            period_returns=score.period_returns,
            ratio_trend=score.ratio_trend,
            rank_percentile_30d=None,
            sub_scores=score.sub_scores,
            data_quality=score.data_quality,
            human_note=score.human_note,
            reason_codes=score.reason_codes,
        )
        report_with_none = RelativeStrengthReport(
            report_id=report.report_id,
            kind=report.kind,
            version=report.version,
            source_spec=report.source_spec,
            generated_at=report.generated_at,
            config=report.config,
            safety_flags=report.safety_flags,
            scores=(score_with_none,),
            universe_summary=report.universe_summary,
            btc_series_head=report.btc_series_head,
            eth_series_head=report.eth_series_head,
            reason_codes=report.reason_codes,
            metadata=report.metadata,
        )
        text = relative_strength_report_to_csv_text(report_with_none)
        reader = csv.reader(text.splitlines())
        rows = list(reader)
        header = rows[0]
        data_row = rows[1]
        rank_idx = header.index("rank_percentile_30d")
        assert data_row[rank_idx] == ""

    def test_reason_codes_pipe_delimited(self) -> None:
        report = _make_report()
        # Add a score with explicit reason codes for deterministic verification.
        score = report.scores[0]
        score_with_reasons = RelativeStrengthScore(
            symbol=score.symbol,
            base_benchmark=score.base_benchmark,
            state=score.state,
            decision=score.decision,
            total_score=score.total_score,
            period_returns=score.period_returns,
            ratio_trend=score.ratio_trend,
            rank_percentile_30d=score.rank_percentile_30d,
            sub_scores=score.sub_scores,
            data_quality=score.data_quality,
            human_note=score.human_note,
            reason_codes=("NO_ACTION_COMMANDS_EMITTED", "HUMAN_RESEARCH_ONLY"),
        )
        report_with_reasons = RelativeStrengthReport(
            report_id=report.report_id,
            kind=report.kind,
            version=report.version,
            source_spec=report.source_spec,
            generated_at=report.generated_at,
            config=report.config,
            safety_flags=report.safety_flags,
            scores=(score_with_reasons,),
            universe_summary=report.universe_summary,
            btc_series_head=report.btc_series_head,
            eth_series_head=report.eth_series_head,
            reason_codes=report.reason_codes,
            metadata=report.metadata,
        )
        text = relative_strength_report_to_csv_text(report_with_reasons)
        reader = csv.reader(text.splitlines())
        rows = list(reader)
        data_row = rows[1]
        reason_idx = rows[0].index("reason_codes")
        assert "|" in data_row[reason_idx]


class TestMarkdown:
    def test_starts_with_h1_and_safety_notice(self) -> None:
        report = _make_report()
        text = relative_strength_report_to_markdown(report)
        lines = text.split("\n")
        assert lines[0] == "# Relative Strength Report"
        assert lines[2].startswith("> ")
        assert "human-audit" in lines[2].lower() or "research-only" in lines[2].lower()

    def test_contains_report_identity(self) -> None:
        report = _make_report()
        text = relative_strength_report_to_markdown(report)
        assert REPORT_ID in text
        assert "2026-01-15T12:00:00+00:00" in text
        assert "SPEC-025" in text

    def test_contains_scores_and_summary(self) -> None:
        report = _make_report()
        text = relative_strength_report_to_markdown(report)
        assert "## Universe Summary" in text
        assert "## Scores" in text
        assert "## Data Quality" in text

    def test_no_trading_approval_semantics(self) -> None:
        report = _make_report()
        text = relative_strength_report_to_markdown(report)
        lower = text.lower()
        # Safety disclaimers are allowed; executable instructions are not.
        assert "place order" not in lower
        assert "enter_long" not in lower
        assert "execute trade" not in lower
        assert "buy now" not in lower
        assert "sell now" not in lower


class TestAtomicWrites:
    def test_atomic_json_write(self, tmp_path: Path) -> None:
        report = _make_report()
        target = tmp_path / "out.json"
        path = atomic_write_json_relative_strength_report(report, target)
        assert path == target
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["report_id"] == REPORT_ID

    def test_atomic_csv_write(self, tmp_path: Path) -> None:
        report = _make_report()
        target = tmp_path / "out.csv"
        path = atomic_write_csv_relative_strength_report(report, target)
        assert path == target
        assert path.exists()
        assert "pair" in path.read_text()

    def test_atomic_markdown_write(self, tmp_path: Path) -> None:
        report = _make_report()
        target = tmp_path / "out.md"
        path = atomic_write_markdown_relative_strength_report(report, target)
        assert path == target
        assert path.exists()
        assert "# Relative Strength Report" in path.read_text()

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        report = _make_report()
        target = tmp_path / "nested" / "dir" / "out.json"
        path = atomic_write_json_relative_strength_report(report, target)
        assert path.exists()

    def test_write_relative_strength_report_all_formats(self, tmp_path: Path) -> None:
        report = _make_report()
        json_out = tmp_path / "out.json"
        csv_out = tmp_path / "out.csv"
        md_out = tmp_path / "out.md"
        paths = write_relative_strength_report(report, json_out, csv_out, md_out)
        assert paths == (json_out, csv_out, md_out)
        assert json_out.exists()
        assert csv_out.exists()
        assert md_out.exists()

    def test_write_relative_strength_report_skip_none(self, tmp_path: Path) -> None:
        report = _make_report()
        json_out = tmp_path / "out.json"
        paths = write_relative_strength_report(report, json_out, None, None)
        assert paths[0] == json_out
        assert paths[1] is None
        assert paths[2] is None


class TestSafety:
    def test_writer_does_not_mutate_report(self) -> None:
        report = _make_report()
        original = relative_strength_report_to_dict(report)
        relative_strength_report_to_json_text(report)
        relative_strength_report_to_csv_text(report)
        relative_strength_report_to_markdown(report)
        assert relative_strength_report_to_dict(report) == original

    def test_blocked_report_serialization(self) -> None:
        report = _make_blocked_report()
        data = relative_strength_report_to_dict(report)
        assert data["scores"] == []
        assert data["universe_summary"]["total_coins"] == 0
        assert "UNSAFE_INPUT_CONTENT" in data["reason_codes"]

    def test_default_paths(self) -> None:
        assert str(DEFAULT_JSON_PATH) == "data/relative_strength/latest_relative_strength_scores.json"
        assert str(DEFAULT_CSV_PATH) == "data/relative_strength/latest_relative_strength_scores.csv"
        assert str(DEFAULT_MD_PATH) == "reports/relative_strength/latest_relative_strength_report.md"
