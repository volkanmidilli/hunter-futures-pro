"""Integration tests for hunter.relative_strength end-to-end workflows."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

import hunter.relative_strength as rs
from hunter.relative_strength.models import (
    OhlcvRow,
    RelativeStrengthConfig,
    RelativeStrengthDecision,
    RelativeStrengthInput,
    RelativeStrengthState,
)
from hunter.relative_strength.writer import (
    relative_strength_report_to_csv_text,
    relative_strength_report_to_dict,
    relative_strength_report_to_json_text,
    relative_strength_report_to_markdown,
    write_relative_strength_report,
)


def _make_rows(symbol: str, start: float, n: int, daily_return: float) -> tuple[OhlcvRow, ...]:
    """Generate deterministic OHLCV rows."""
    rows: list[OhlcvRow] = []
    price = start
    for i in range(n):
        rows.append(OhlcvRow(timestamp=i, close=round(price, 8)))
        price *= 1 + daily_return
    return tuple(rows)


def _make_btc_rows(n: int = 35) -> tuple[OhlcvRow, ...]:
    return _make_rows("BTC", 50000.0, n, 0.001)


def _make_eth_rows(n: int = 35) -> tuple[OhlcvRow, ...]:
    return _make_rows("ETH", 3000.0, n, 0.0015)


def _make_outperformer_rows(symbol: str, n: int = 35) -> tuple[OhlcvRow, ...]:
    return _make_rows(symbol, 100.0, n, 0.02)


def _make_underperformer_rows(symbol: str, n: int = 35) -> tuple[OhlcvRow, ...]:
    return _make_rows(symbol, 100.0, n, -0.015)


def _make_universe(n: int = 35) -> tuple[RelativeStrengthInput, ...]:
    return (
        RelativeStrengthInput(symbol="SOL", rows=_make_outperformer_rows("SOL", n)),
        RelativeStrengthInput(symbol="DOGE", rows=_make_underperformer_rows("DOGE", n)),
    )


def _make_generated_at() -> datetime:
    return datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


class TestEndToEndReport:
    def test_build_full_report(self) -> None:
        universe = _make_universe()
        btc = _make_btc_rows()
        eth = _make_eth_rows()
        config = RelativeStrengthConfig()
        generated_at = _make_generated_at()

        report = rs.build_relative_strength_report(
            universe=universe,
            btc_benchmark=btc,
            eth_benchmark=eth,
            config=config,
            generated_at=generated_at,
        )

        assert report.kind == "relative_strength_report"
        assert report.source_spec == "SPEC-025"
        assert report.report_id == "latest-relative-strength"
        assert len(report.scores) == 2
        assert report.universe_summary.total_coins == 2

        states = {score.state for score in report.scores}
        assert RelativeStrengthState.READY in states
        assert all(score.state != RelativeStrengthState.BLOCKED for score in report.scores)

        decisions = {score.decision for score in report.scores}
        assert RelativeStrengthDecision.OUTPERFORMER in decisions
        assert RelativeStrengthDecision.UNDERPERFORMER in decisions

        # Deterministic ordering: by total score desc, then decision priority, then symbol asc.
        scores = list(report.scores)
        assert scores[0].total_score >= scores[1].total_score

        summary = report.universe_summary
        assert summary.outperformer_count + summary.underperformer_count == 2
        assert summary.average_total_score is not None
        assert summary.top_outperformer is not None
        assert summary.top_underperformer is not None

        assert report.safety_flags.human_research_only is True
        assert report.safety_flags.no_action_commands_emitted is True
        assert report.safety_flags.output_not_trading_signal is True
        assert report.safety_flags.output_not_trade_approval is True

        dq = summary.data_quality
        assert dq.min_required_rows_met is True
        assert dq.btc_benchmark_rows > 0
        assert dq.eth_benchmark_rows > 0

    def test_btc_series_head_is_present(self) -> None:
        universe = _make_universe(35)
        report = rs.build_relative_strength_report(
            universe=universe,
            btc_benchmark=_make_btc_rows(35),
            eth_benchmark=_make_eth_rows(35),
            config=RelativeStrengthConfig(),
            generated_at=_make_generated_at(),
        )
        assert len(report.btc_series_head) > 0


class TestEndToEndWriter:
    def test_write_all_artifacts(self, tmp_path: Path) -> None:
        report = rs.build_relative_strength_report(
            universe=_make_universe(),
            btc_benchmark=_make_btc_rows(),
            eth_benchmark=_make_eth_rows(),
            config=RelativeStrengthConfig(),
            generated_at=_make_generated_at(),
        )
        json_out = tmp_path / "out.json"
        csv_out = tmp_path / "out.csv"
        md_out = tmp_path / "out.md"

        paths = write_relative_strength_report(report, json_out, csv_out, md_out)
        assert paths == (json_out, csv_out, md_out)

        assert json_out.exists()
        assert csv_out.exists()
        assert md_out.exists()

        data = json.loads(json_out.read_text())
        assert data["kind"] == "relative_strength_report"
        assert data["scores"]

        rows = list(csv.reader(csv_out.read_text().splitlines()))
        assert len(rows) == len(report.scores) + 1
        assert "pair" in rows[0]

        md = md_out.read_text()
        assert md.startswith("# Relative Strength Report")
        lines = md.splitlines()
        assert lines[2].startswith("> ")
        assert "research-only" in lines[2].lower() or "human-audit" in lines[2].lower()

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        report = rs.build_relative_strength_report(
            universe=_make_universe(),
            btc_benchmark=_make_btc_rows(),
            eth_benchmark=_make_eth_rows(),
            config=RelativeStrengthConfig(),
            generated_at=_make_generated_at(),
        )
        target = tmp_path / "nested" / "dir" / "report.json"
        paths = write_relative_strength_report(report, target, None, None)
        assert paths[0] == target
        assert target.exists()


class TestMissingEth:
    def test_missing_eth_redistributes_weight(self) -> None:
        config = RelativeStrengthConfig(block_on_missing_eth=False)
        report = rs.build_relative_strength_report(
            universe=(RelativeStrengthInput(symbol="SOL", rows=_make_outperformer_rows("SOL")),),
            btc_benchmark=_make_btc_rows(),
            eth_benchmark=None,
            config=config,
            generated_at=_make_generated_at(),
        )
        assert len(report.scores) == 1
        score = report.scores[0]
        assert score.decision == RelativeStrengthDecision.OUTPERFORMER
        assert score.state == RelativeStrengthState.READY
        assert "ETH_BENCHMARK_MISSING" in score.reason_codes or "ETH_BENCHMARK_MISSING" in report.reason_codes

    def test_missing_eth_blocks(self) -> None:
        config = RelativeStrengthConfig(block_on_missing_eth=True)
        report = rs.build_relative_strength_report(
            universe=(RelativeStrengthInput(symbol="SOL", rows=_make_outperformer_rows("SOL")),),
            btc_benchmark=_make_btc_rows(),
            eth_benchmark=None,
            config=config,
            generated_at=_make_generated_at(),
        )
        assert len(report.scores) == 0
        assert report.universe_summary.total_coins == 0
        assert "ETH_BENCHMARK_MISSING" in report.reason_codes


class TestInsufficientData:
    def test_insufficient_data_score(self) -> None:
        config = RelativeStrengthConfig(block_on_missing_data=False)
        report = rs.build_relative_strength_report(
            universe=(RelativeStrengthInput(symbol="SOL", rows=_make_outperformer_rows("SOL", n=10)),),
            btc_benchmark=_make_btc_rows(10),
            eth_benchmark=_make_eth_rows(10),
            config=config,
            generated_at=_make_generated_at(),
        )
        assert len(report.scores) == 1
        score = report.scores[0]
        assert score.decision == RelativeStrengthDecision.INSUFFICIENT_DATA
        assert score.state == RelativeStrengthState.INSUFFICIENT_DATA

    def test_block_on_missing_data(self) -> None:
        config = RelativeStrengthConfig(block_on_missing_data=True)
        report = rs.build_relative_strength_report(
            universe=(RelativeStrengthInput(symbol="SOL", rows=_make_outperformer_rows("SOL", n=10)),),
            btc_benchmark=_make_btc_rows(10),
            eth_benchmark=_make_eth_rows(10),
            config=config,
            generated_at=_make_generated_at(),
        )
        assert len(report.scores) == 1
        score = report.scores[0]
        assert score.state == RelativeStrengthState.BLOCKED
        assert score.decision == RelativeStrengthDecision.BLOCKED
        assert any(code in {"PERIOD_DATA_MISSING", "INSUFFICIENT_COIN_DATA"} for code in score.reason_codes)


class TestUnsafeContent:
    def test_unsafe_symbol_blocks(self) -> None:
        report = rs.build_relative_strength_report(
            universe=(RelativeStrengthInput(symbol="place_order", rows=_make_outperformer_rows("place_order")),),
            btc_benchmark=_make_btc_rows(),
            eth_benchmark=_make_eth_rows(),
            config=RelativeStrengthConfig(),
            generated_at=_make_generated_at(),
        )
        assert len(report.scores) == 0
        assert "UNSAFE_INPUT_CONTENT" in report.reason_codes

    def test_unsafe_metadata_is_not_followed(self, tmp_path: Path) -> None:
        """Unsafe metadata must be treated as opaque strings, not read or executed."""
        report = rs.build_relative_strength_report(
            universe=(RelativeStrengthInput(symbol="SOL", rows=_make_outperformer_rows("SOL")),),
            btc_benchmark=_make_btc_rows(),
            eth_benchmark=_make_eth_rows(),
            config=RelativeStrengthConfig(),
            generated_at=_make_generated_at(),
            metadata={"note": "enter_long immediately", "path": "/etc/passwd"},
        )
        # The report must not crash or read the path; the metadata is opaque.
        assert report.metadata == {"note": "enter_long immediately", "path": "/etc/passwd"}
        json_out = tmp_path / "meta.json"
        write_relative_strength_report(report, json_out, None, None)
        data = json.loads(json_out.read_text())
        assert data["metadata"]["note"] == "enter_long immediately"


class TestDeterminism:
    def test_report_is_deterministic(self) -> None:
        universe = _make_universe()
        btc = _make_btc_rows()
        eth = _make_eth_rows()
        config = RelativeStrengthConfig()
        generated_at = _make_generated_at()

        report1 = rs.build_relative_strength_report(
            universe=universe,
            btc_benchmark=btc,
            eth_benchmark=eth,
            config=config,
            generated_at=generated_at,
        )
        report2 = rs.build_relative_strength_report(
            universe=universe,
            btc_benchmark=btc,
            eth_benchmark=eth,
            config=config,
            generated_at=generated_at,
        )
        assert report1 == report2

    def test_serialization_text_is_deterministic(self) -> None:
        report = rs.build_relative_strength_report(
            universe=_make_universe(),
            btc_benchmark=_make_btc_rows(),
            eth_benchmark=_make_eth_rows(),
            config=RelativeStrengthConfig(),
            generated_at=_make_generated_at(),
        )
        assert relative_strength_report_to_json_text(report) == relative_strength_report_to_json_text(report)
        assert relative_strength_report_to_csv_text(report) == relative_strength_report_to_csv_text(report)
        assert relative_strength_report_to_markdown(report) == relative_strength_report_to_markdown(report)
        assert relative_strength_report_to_dict(report) == relative_strength_report_to_dict(report)


class TestNoMutation:
    def test_input_rows_not_mutated(self) -> None:
        rows = _make_outperformer_rows("SOL")
        original_rows = tuple(rows)
        inp = RelativeStrengthInput(symbol="SOL", rows=rows)
        btc = _make_btc_rows()
        eth = _make_eth_rows()
        report = rs.build_relative_strength_report(
            universe=(inp,),
            btc_benchmark=btc,
            eth_benchmark=eth,
            config=RelativeStrengthConfig(),
            generated_at=_make_generated_at(),
        )
        assert rows == original_rows
        assert btc == _make_btc_rows()
        assert report.scores[0].symbol == "SOL"

    def test_input_object_not_mutated(self) -> None:
        inp = RelativeStrengthInput(symbol="SOL", rows=_make_outperformer_rows("SOL"))
        original = RelativeStrengthInput(symbol="SOL", rows=inp.rows)
        rs.build_relative_strength_report(
            universe=(inp,),
            btc_benchmark=_make_btc_rows(),
            eth_benchmark=_make_eth_rows(),
            config=RelativeStrengthConfig(),
            generated_at=_make_generated_at(),
        )
        assert inp.symbol == original.symbol
        assert inp.rows == original.rows


class TestAtomicTmpPathWrites:
    def test_outputs_only_under_tmp_path(self, tmp_path: Path) -> None:
        report = rs.build_relative_strength_report(
            universe=_make_universe(),
            btc_benchmark=_make_btc_rows(),
            eth_benchmark=_make_eth_rows(),
            config=RelativeStrengthConfig(),
            generated_at=_make_generated_at(),
        )
        json_out = tmp_path / "data" / "out.json"
        csv_out = tmp_path / "data" / "out.csv"
        md_out = tmp_path / "reports" / "out.md"
        write_relative_strength_report(report, json_out, csv_out, md_out)

        for path in (json_out, csv_out, md_out):
            assert path.exists()
            assert tmp_path in path.parents

        # No stray files outside tmp_path.
        for path in tmp_path.rglob("*"):
            assert tmp_path in path.parents or path == tmp_path


class TestHumanResearchSafety:
    def test_markdown_contains_research_only_language(self) -> None:
        report = rs.build_relative_strength_report(
            universe=_make_universe(),
            btc_benchmark=_make_btc_rows(),
            eth_benchmark=_make_eth_rows(),
            config=RelativeStrengthConfig(),
            generated_at=_make_generated_at(),
        )
        md = relative_strength_report_to_markdown(report)
        assert "human-audit" in md.lower() or "research-only" in md.lower()
        assert "not a trading signal" in md.lower()

    def test_markdown_no_actionable_instructions(self) -> None:
        report = rs.build_relative_strength_report(
            universe=_make_universe(),
            btc_benchmark=_make_btc_rows(),
            eth_benchmark=_make_eth_rows(),
            config=RelativeStrengthConfig(),
            generated_at=_make_generated_at(),
        )
        md = relative_strength_report_to_markdown(report)
        lower = md.lower()
        assert "place order" not in lower
        assert "buy now" not in lower
        assert "sell now" not in lower
        assert "execute trade" not in lower
        assert "enter_long" not in lower


class TestPublicExports:
    def test_public_api_exports(self) -> None:
        assert callable(rs.build_relative_strength_report)
        assert callable(rs.relative_strength_report_to_dict)
        assert callable(rs.relative_strength_report_to_json_text)
        assert callable(rs.relative_strength_report_to_csv_text)
        assert callable(rs.relative_strength_report_to_markdown)
        assert callable(rs.atomic_write_json_relative_strength_report)
        assert callable(rs.atomic_write_csv_relative_strength_report)
        assert callable(rs.atomic_write_markdown_relative_strength_report)
        assert callable(rs.write_relative_strength_report)
        assert rs.DEFAULT_JSON_PATH is not None
        assert rs.DEFAULT_CSV_PATH is not None
        assert rs.DEFAULT_MD_PATH is not None
