"""Tests for the controlled_universe writer module."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from hunter.controlled_universe import (
    AllowedMode,
    ControlledUniverseClassification,
    ControlledUniverseConfig,
    ControlledUniverseDataQuality,
    ControlledUniverseItem,
    ControlledUniverseReport,
    ControlledUniverseSafetyFlags,
    ControlledUniverseState,
    atomic_write_csv_controlled_universe_report,
    atomic_write_json_controlled_universe_report,
    atomic_write_markdown_controlled_universe_report,
    controlled_universe_report_to_csv_text,
    controlled_universe_report_to_json_text,
    controlled_universe_report_to_markdown,
    write_controlled_universe_report,
)
from hunter.controlled_universe.writer import ControlledUniverseWriterError, _iso


@pytest.fixture
def sample_config() -> ControlledUniverseConfig:
    return ControlledUniverseConfig(
        max_universe_pairs=5,
        min_portfolio_score=60.0,
        max_watchlist_pairs=3,
        include_capped=True,
        default_mode=AllowedMode.LONG_ONLY,
        require_dry_run=True,
    )


@pytest.fixture
def sample_report(sample_config: ControlledUniverseConfig) -> ControlledUniverseReport:
    item = ControlledUniverseItem(
        pair="BTC/USDT",
        state=ControlledUniverseState.INCLUDED,
        classification=ControlledUniverseClassification.LONG_RESEARCH,
        reason_codes=("PASSED_UNIVERSE_FILTER", "HUMAN_RESEARCH_ONLY"),
        portfolio_score=85.0,
        portfolio_state="INCLUDED",
        capped=False,
    )
    watchlist_item = ControlledUniverseItem(
        pair="ETH/USDT",
        state=ControlledUniverseState.WATCHLIST,
        classification=ControlledUniverseClassification.WATCHLIST_RESEARCH,
        reason_codes=("PORTFOLIO_STATE_WATCHLIST", "HUMAN_RESEARCH_ONLY"),
        portfolio_score=45.0,
        portfolio_state="WATCHLIST",
        capped=False,
    )
    blocked_item = ControlledUniverseItem(
        pair="DOGE/USDT",
        state=ControlledUniverseState.BLOCKED,
        classification=ControlledUniverseClassification.BLOCKED_BY_PORTFOLIO,
        reason_codes=("PORTFOLIO_STATE_BLOCKED", "HUMAN_RESEARCH_ONLY"),
        portfolio_score=10.0,
        portfolio_state="BLOCKED",
        capped=False,
    )
    return ControlledUniverseReport(
        version="1.0.0",
        generated_at=datetime(2026, 7, 13, 12, 0, 0, tzinfo=timezone.utc),
        config=sample_config,
        execution_state="READY",
        allowed_mode=AllowedMode.LONG_ONLY.value,
        universe=("BTC/USDT",),
        watchlist=("ETH/USDT",),
        blocked=("DOGE/USDT",),
        items=(item, watchlist_item, blocked_item),
        data_quality=ControlledUniverseDataQuality(
            total_inputs=3,
            universe_count=1,
            watchlist_count=1,
            blocked_count=1,
            excluded_count=0,
            insufficient_data_count=0,
            execution_context_valid=True,
            portfolio_context_valid=True,
            data_quality_score=50.0,
            all_counts_consistent=True,
            safety_flags_ok=True,
        ),
        safety_flags=ControlledUniverseSafetyFlags(
            no_trading_signal=True,
            no_trade_approval=True,
            no_strategy_approval=True,
            no_execution_approval=True,
            no_portfolio_approval=True,
            no_universe_approval=True,
            no_order_sizing=True,
            no_position_sizing=True,
            no_leverage=True,
            no_shorting=True,
            no_action_commands=True,
            no_network_connection=True,
            no_file_read_in_engine=True,
            no_database=True,
            no_exchange_connection=True,
            no_freqtrade_input=True,
            has_unsafe_content=False,
            has_invalid_pair=False,
            has_duplicate_pair=False,
            has_blocked_execution=False,
            has_missing_execution_context=False,
            has_missing_portfolio_context=False,
            has_invalid_portfolio_summary=False,
            has_stale_or_invalid_data=False,
        ),
        reason_codes=("HUMAN_RESEARCH_ONLY",),
        metadata={"source": "test"},
        notes=("research only",),
    )


class TestJsonSerialization:
    def test_to_json_text_returns_valid_json(self, sample_report: ControlledUniverseReport) -> None:
        text = controlled_universe_report_to_json_text(sample_report)
        data = json.loads(text)
        assert data["kind"] == "controlled_universe_report"
        assert data["version"] == "1.0.0"
        assert data["execution_state"] == "READY"
        assert data["allowed_mode"] == "LONG_ONLY"
        assert len(data["items"]) == 3

    def test_json_safety_notice_present(self, sample_report: ControlledUniverseReport) -> None:
        text = controlled_universe_report_to_json_text(sample_report)
        data = json.loads(text)
        assert "research-only" in data["safety_notice"]
        assert "not a trading signal" in data["safety_notice"]

    def test_json_items_have_expected_fields(
        self, sample_report: ControlledUniverseReport
    ) -> None:
        text = controlled_universe_report_to_json_text(sample_report)
        data = json.loads(text)
        item = data["items"][0]
        assert item["pair"] == "BTC/USDT"
        assert item["state"] == "INCLUDED"
        assert item["classification"] == "LONG_RESEARCH"
        assert "PASSED_UNIVERSE_FILTER" in item["reason_codes"]
        assert item["portfolio_score"] == 85.0
        assert item["capped"] is False

    def test_json_data_quality_and_safety_flags(self, sample_report: ControlledUniverseReport) -> None:
        text = controlled_universe_report_to_json_text(sample_report)
        data = json.loads(text)
        assert data["data_quality"]["universe_count"] == 1
        assert data["data_quality"]["all_counts_consistent"] is True
        assert data["safety_flags"]["is_safe"] is True
        assert data["safety_flags"]["no_trading_signal"] is True

    def test_json_sort_keys_deterministic(self, sample_report: ControlledUniverseReport) -> None:
        text1 = controlled_universe_report_to_json_text(sample_report)
        text2 = controlled_universe_report_to_json_text(sample_report)
        assert text1 == text2


class TestCsvSerialization:
    def test_to_csv_text_has_header_and_rows(self, sample_report: ControlledUniverseReport) -> None:
        text = controlled_universe_report_to_csv_text(sample_report)
        rows = list(csv.reader(text.splitlines()))
        assert rows[0] == [
            "pair",
            "state",
            "classification",
            "portfolio_score",
            "portfolio_state",
            "capped",
            "reason_codes",
        ]
        assert len(rows) == 4

    def test_csv_sorted_by_state_then_pair(self, sample_report: ControlledUniverseReport) -> None:
        text = controlled_universe_report_to_csv_text(sample_report)
        rows = list(csv.reader(text.splitlines()))[1:]
        pairs = [row[0] for row in rows]
        assert pairs == ["DOGE/USDT", "BTC/USDT", "ETH/USDT"]

    def test_csv_reason_codes_joined(self, sample_report: ControlledUniverseReport) -> None:
        text = controlled_universe_report_to_csv_text(sample_report)
        rows = list(csv.reader(text.splitlines()))[1:]
        btc_row = [row for row in rows if row[0] == "BTC/USDT"][0]
        assert "HUMAN_RESEARCH_ONLY" in btc_row[6]
        assert "PASSED_UNIVERSE_FILTER" in btc_row[6]


class TestMarkdownSerialization:
    def test_to_markdown_has_sections(self, sample_report: ControlledUniverseReport) -> None:
        text = controlled_universe_report_to_markdown(sample_report)
        assert text.startswith("# Controlled Universe Report")
        assert "## Summary" in text
        assert "## Universe" in text
        assert "## Watchlist" in text
        assert "## Blocked" in text
        assert "## Items" in text
        assert "## Data Quality" in text
        assert "## Safety Flags" in text
        assert "## Reason Codes" in text

    def test_markdown_safety_notice_present(self, sample_report: ControlledUniverseReport) -> None:
        text = controlled_universe_report_to_markdown(sample_report)
        assert "research-only" in text
        assert "not a trading signal" in text

    def test_markdown_escapes_pipe(self, sample_report: ControlledUniverseReport) -> None:
        item = ControlledUniverseItem(
            pair="A|B/USDT",
            state=ControlledUniverseState.INCLUDED,
            classification=ControlledUniverseClassification.LONG_RESEARCH,
            reason_codes=("HUMAN_RESEARCH_ONLY",),
            portfolio_score=80.0,
            portfolio_state="INCLUDED",
            capped=False,
        )
        report = ControlledUniverseReport(
            version="1.0.0",
            generated_at=datetime(2026, 7, 13, 12, 0, 0, tzinfo=timezone.utc),
            config=sample_report.config,
            execution_state=sample_report.execution_state,
            allowed_mode=sample_report.allowed_mode,
            universe=("A|B/USDT",),
            watchlist=(),
            blocked=(),
            items=(item,),
            data_quality=sample_report.data_quality,
            safety_flags=sample_report.safety_flags,
            reason_codes=(),
            metadata={},
            notes=(),
        )
        text = controlled_universe_report_to_markdown(report)
        assert "A\\|B/USDT" in text

    def test_markdown_empty_lists(self, sample_report: ControlledUniverseReport) -> None:
        report = ControlledUniverseReport(
            version="1.0.0",
            generated_at=datetime(2026, 7, 13, 12, 0, 0, tzinfo=timezone.utc),
            config=sample_report.config,
            execution_state=sample_report.execution_state,
            allowed_mode=sample_report.allowed_mode,
            universe=(),
            watchlist=(),
            blocked=(),
            items=(),
            data_quality=sample_report.data_quality,
            safety_flags=sample_report.safety_flags,
            reason_codes=(),
            metadata={},
            notes=(),
        )
        text = controlled_universe_report_to_markdown(report)
        assert "- _none_" in text


class TestAtomicWrites:
    def test_atomic_write_json(self, sample_report: ControlledUniverseReport, tmp_path: Path) -> None:
        target = tmp_path / "report.json"
        path = atomic_write_json_controlled_universe_report(sample_report, target)
        assert path == target
        assert target.exists()
        data = json.loads(target.read_text(encoding="utf-8"))
        assert data["kind"] == "controlled_universe_report"
        assert not (target.with_suffix(target.suffix + ".tmp")).exists()

    def test_atomic_write_csv(self, sample_report: ControlledUniverseReport, tmp_path: Path) -> None:
        target = tmp_path / "report.csv"
        path = atomic_write_csv_controlled_universe_report(sample_report, target)
        assert path == target
        assert target.exists()
        rows = list(csv.reader(target.read_text(encoding="utf-8").splitlines()))
        assert len(rows) == 4

    def test_atomic_write_markdown(self, sample_report: ControlledUniverseReport, tmp_path: Path) -> None:
        target = tmp_path / "report.md"
        path = atomic_write_markdown_controlled_universe_report(sample_report, target)
        assert path == target
        assert target.exists()
        text = target.read_text(encoding="utf-8")
        assert text.startswith("# Controlled Universe Report")

    def test_write_all_three(self, sample_report: ControlledUniverseReport, tmp_path: Path) -> None:
        json_path = tmp_path / "report.json"
        csv_path = tmp_path / "report.csv"
        md_path = tmp_path / "report.md"
        out_json, out_csv, out_md = write_controlled_universe_report(
            sample_report, json_path, csv_path, md_path
        )
        assert out_json == json_path
        assert out_csv == csv_path
        assert out_md == md_path
        assert json_path.exists()
        assert csv_path.exists()
        assert md_path.exists()

    def test_write_skip_format(self, sample_report: ControlledUniverseReport, tmp_path: Path) -> None:
        json_path = tmp_path / "report.json"
        csv_path = tmp_path / "report.csv"
        out_json, out_csv, out_md = write_controlled_universe_report(
            sample_report, json_path, csv_path, None
        )
        assert out_json == json_path
        assert out_csv == csv_path
        assert out_md is None
        assert not (tmp_path / "report.md").exists()

    def test_atomic_write_creates_parent_directories(
        self, sample_report: ControlledUniverseReport, tmp_path: Path
    ) -> None:
        target = tmp_path / "nested" / "report.json"
        path = atomic_write_json_controlled_universe_report(sample_report, target)
        assert path == target
        assert target.exists()


class TestIsoHelper:
    def test_iso_requires_timezone(self) -> None:
        with pytest.raises(ValueError, match="timezone-aware"):
            _iso(datetime.now())  # type: ignore[arg-type]

    def test_iso_outputs_utc_suffix(self) -> None:
        dt = datetime(2026, 7, 13, 12, 0, 0, tzinfo=timezone.utc)
        assert _iso(dt) == "2026-07-13T12:00:00+00:00"


class TestPublicApi:
    def test_writer_exports_from_package(self) -> None:
        from hunter import controlled_universe

        assert hasattr(controlled_universe, "write_controlled_universe_report")
        assert hasattr(controlled_universe, "atomic_write_json_controlled_universe_report")
        assert hasattr(controlled_universe, "controlled_universe_report_to_markdown")


def test_default_paths_are_under_package_defaults() -> None:
    from hunter.controlled_universe.writer import DEFAULT_CSV_PATH, DEFAULT_JSON_PATH, DEFAULT_MD_PATH

    assert str(DEFAULT_JSON_PATH).startswith("data/controlled_universe")
    assert str(DEFAULT_CSV_PATH).startswith("data/controlled_universe")
    assert str(DEFAULT_MD_PATH).startswith("reports/controlled_universe")
