"""Integration tests for hunter.backtest package.

These tests exercise the public API end-to-end with in-memory fixtures only.
File writes use tmp_path. No network, exchange, Freqtrade, database, or live
trading semantics are used.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hunter.backtest import (
    BacktestAllocationMode,
    BacktestCandidateDecision,
    BacktestCandidateResult,
    BacktestInput,
    BacktestPortfolioSnapshot,
    BacktestPriceBar,
    BacktestReport,
    BacktestRunConfig,
    BacktestState,
    UNSAFE_BACKTEST_CONTENT,
    atomic_write_json_backtest_report,
    backtest_report_to_csv_text,
    backtest_report_to_dict,
    backtest_report_to_json_text,
    backtest_report_to_markdown,
    build_backtest_report,
    write_backtest_report,
)


def ts(day: int, hour: int = 0) -> datetime:
    return datetime(2024, 1, day, hour, tzinfo=timezone.utc)


def price_bar(pair: str, day: int, close: float, hour: int = 0) -> BacktestPriceBar:
    return BacktestPriceBar(pair=pair, timestamp=ts(day, hour), close=close)


def decision(pair: str, state: str, final_weight_pct: float = 0.0) -> BacktestCandidateDecision:
    return BacktestCandidateDecision(
        pair=pair,
        state=state,
        classification="CORE_RESEARCH_ALLOCATION",
        final_weight_pct=final_weight_pct,
    )


def make_inputs() -> tuple[BacktestInput, ...]:
    return (
        BacktestInput(
            pair="SOL/USDT:USDT",
            decision=decision("SOL/USDT:USDT", "INCLUDED", 60.0),
            price_bars=(
                price_bar("SOL/USDT:USDT", 1, 100.0),
                price_bar("SOL/USDT:USDT", 2, 110.0),
                price_bar("SOL/USDT:USDT", 3, 121.0),
            ),
            tags=("core",),
        ),
        BacktestInput(
            pair="ETH/USDT:USDT",
            decision=decision("ETH/USDT:USDT", "INCLUDED", 40.0),
            price_bars=(
                price_bar("ETH/USDT:USDT", 1, 200.0),
                price_bar("ETH/USDT:USDT", 2, 190.0),
                price_bar("ETH/USDT:USDT", 3, 180.0),
            ),
            tags=("core",),
        ),
    )


def make_report() -> BacktestReport:
    return build_backtest_report(
        make_inputs(),
        BacktestRunConfig(allocation_mode=BacktestAllocationMode.RESEARCH_WEIGHT),
        report_id="integration-test",
        generated_at=ts(1),
    )


class TestEndToEnd:
    def test_successful_local_backtest(self) -> None:
        report = make_report()
        assert report.version == "0.28.0-dev"
        assert report.report_id == "integration-test"
        assert report.generated_at == ts(1)
        assert report.data_quality.safety_flags_ok is True
        assert report.data_quality.total_inputs == 2
        states = {r.state for r in report.candidate_results}
        assert BacktestState.INCLUDED in states or BacktestState.CAPPED in states
        assert report.portfolio_result.candidate_count == 2

    def test_candidate_level_metrics(self) -> None:
        report = make_report()
        sol = next(r for r in report.candidate_results if r.pair == "SOL/USDT:USDT")
        eth = next(r for r in report.candidate_results if r.pair == "ETH/USDT:USDT")
        assert sol.total_return_pct == pytest.approx(21.0, abs=0.01)
        assert eth.total_return_pct == pytest.approx(-10.0, abs=0.01)
        assert sol.observation_count == 3
        assert eth.observation_count == 3
        assert sol.volatility_pct >= 0.0
        assert eth.volatility_pct >= 0.0
        assert sol.win_rate_pct == 100.0
        assert eth.win_rate_pct == 0.0

    def test_deterministic_candidate_ordering(self) -> None:
        report = make_report()
        sorted_results = sorted(
            report.candidate_results,
            key=lambda r: (
                {
                    BacktestState.INCLUDED: 0,
                    BacktestState.CAPPED: 1,
                    BacktestState.WATCHLIST: 2,
                    BacktestState.EXCLUDED: 3,
                    BacktestState.INSUFFICIENT_DATA: 4,
                    BacktestState.BLOCKED: 5,
                }[r.state],
                -r.total_return_pct,
                r.max_drawdown_pct,
                r.pair,
            ),
        )
        assert list(report.candidate_results) == sorted_results
        for i, result in enumerate(report.candidate_results, start=1):
            assert result.rank == i


class TestPortfolioMetrics:
    def test_equity_curve_from_snapshots(self) -> None:
        report = make_report()
        curve = report.portfolio_result.equity_curve
        assert len(curve) == 3
        assert all(isinstance(s, BacktestPortfolioSnapshot) for s in curve)
        assert curve[0].equity == pytest.approx(1.0, abs=1e-6)
        assert curve[-1].equity > 0.0

    def test_portfolio_metrics_from_equity_curve(self) -> None:
        report = make_report()
        portfolio = report.portfolio_result
        # 60% weight on SOL (+21% over two periods) + 40% weight on ETH (-10%)
        # compounded: period1 = 4%, period2 ~= 3.895%, total ~= 8.05%
        assert portfolio.total_return_pct == pytest.approx(8.05, abs=0.05)
        assert portfolio.max_drawdown_pct >= 0.0
        assert portfolio.volatility_pct >= 0.0
        assert portfolio.win_rate_pct >= 0.0
        assert portfolio.win_rate_pct <= 100.0
        assert portfolio.observation_count == len(portfolio.equity_curve)
        assert portfolio.candidate_count == 2


class TestTimestampAlignment:
    def test_union_timestamps_no_carry_forward(self) -> None:
        inputs = (
            BacktestInput(
                pair="A",
                decision=decision("A", "INCLUDED"),
                price_bars=(
                    price_bar("A", 1, 100.0),
                    price_bar("A", 3, 110.0),
                ),
            ),
            BacktestInput(
                pair="B",
                decision=decision("B", "INCLUDED"),
                price_bars=(
                    price_bar("B", 1, 100.0),
                    price_bar("B", 2, 105.0),
                    price_bar("B", 3, 110.0),
                ),
            ),
        )
        report = build_backtest_report(
            inputs,
            BacktestRunConfig(allocation_mode=BacktestAllocationMode.EQUAL_WEIGHT),
            generated_at=ts(1),
        )
        assert report.portfolio_result.observation_count == 3
        a_result = next(r for r in report.candidate_results if r.pair == "A")
        assert a_result.missing_data_count == 1
        b_result = next(r for r in report.candidate_results if r.pair == "B")
        assert b_result.missing_data_count == 0

    def test_snapshot_observation_count(self) -> None:
        inputs = (
            BacktestInput(
                pair="A",
                decision=decision("A", "INCLUDED"),
                price_bars=(price_bar("A", 1, 100.0), price_bar("A", 3, 110.0)),
            ),
            BacktestInput(
                pair="B",
                decision=decision("B", "INCLUDED"),
                price_bars=(price_bar("B", 1, 100.0), price_bar("B", 2, 105.0)),
            ),
        )
        report = build_backtest_report(
            inputs,
            BacktestRunConfig(allocation_mode=BacktestAllocationMode.EQUAL_WEIGHT),
            generated_at=ts(1),
        )
        by_day = {s.timestamp.day: s for s in report.portfolio_result.equity_curve}
        assert by_day[1].observation_count == 2
        assert by_day[2].observation_count == 1
        assert by_day[3].observation_count == 1


class TestMissingInvalidHistory:
    def test_missing_price_history_insufficient_data(self) -> None:
        inputs = (
            BacktestInput(
                pair="A",
                decision=decision("A", "INCLUDED"),
                price_bars=(),
            ),
        )
        report = build_backtest_report(
            inputs,
            BacktestRunConfig(),
            generated_at=ts(1),
        )
        result = report.candidate_results[0]
        assert result.state == BacktestState.INSUFFICIENT_DATA
        assert result.observation_count == 0

    def test_insufficient_observation_count(self) -> None:
        inputs = (
            BacktestInput(
                pair="A",
                decision=decision("A", "INCLUDED"),
                price_bars=(price_bar("A", 1, 100.0),),
            ),
        )
        report = build_backtest_report(
            inputs,
            BacktestRunConfig(min_observation_count=2),
            generated_at=ts(1),
        )
        result = report.candidate_results[0]
        assert result.state == BacktestState.INSUFFICIENT_DATA

    def test_invalid_close_rejected_at_model(self) -> None:
        # BacktestPriceBar validates strictly positive close; invalid close is
        # fail-closed at construction time.
        with pytest.raises(ValueError, match="close must be a strictly positive"):
            BacktestPriceBar(
                pair="A",
                timestamp=ts(1),
                close=0.0,
            )


class TestSafety:
    def test_unsafe_content_blocks_report(self) -> None:
        inputs = (
            BacktestInput(
                pair="A",
                decision=decision("A", "INCLUDED"),
                price_bars=(price_bar("A", 1, 100.0), price_bar("A", 2, 110.0)),
                metadata={"note": "this is a live_trading signal"},
            ),
        )
        report = build_backtest_report(
            inputs,
            BacktestRunConfig(),
            generated_at=ts(1),
        )
        assert report.data_quality.safety_flags_ok is False
        assert report.data_quality.has_unsafe_content is True
        assert UNSAFE_BACKTEST_CONTENT in report.reason_codes
        assert report.portfolio_result.candidate_count == 0

    def test_metadata_file_reference_is_opaque(self, tmp_path: Path) -> None:
        inputs = (
            BacktestInput(
                pair="A",
                decision=decision("A", "INCLUDED"),
                price_bars=(price_bar("A", 1, 100.0), price_bar("A", 2, 110.0)),
                metadata={"file_ref": "/etc/sensitive.txt"},
            ),
        )
        report = build_backtest_report(
            inputs,
            BacktestRunConfig(),
            generated_at=ts(1),
        )
        path = tmp_path / "report.json"
        atomic_write_json_backtest_report(report, path)
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["inputs"][0]["metadata"]["file_ref"] == "/etc/sensitive.txt"


class TestConfigBehavior:
    def test_volatility_scale_factor_affects_volatility(self) -> None:
        inputs = (
            BacktestInput(
                pair="A",
                decision=decision("A", "INCLUDED"),
                price_bars=(
                    price_bar("A", 1, 100.0),
                    price_bar("A", 2, 110.0),
                    price_bar("A", 3, 121.0),
                    price_bar("A", 4, 133.1),
                ),
            ),
        )
        cfg1 = BacktestRunConfig(volatility_scale_factor=1.0)
        cfg4 = BacktestRunConfig(volatility_scale_factor=4.0)
        r1 = build_backtest_report(inputs, cfg1, generated_at=ts(1))
        r4 = build_backtest_report(inputs, cfg4, generated_at=ts(1))
        v1 = r1.portfolio_result.volatility_pct
        v4 = r4.portfolio_result.volatility_pct
        assert v4 == pytest.approx(v1 * 2.0, abs=0.01)

    def test_start_end_timestamp_inclusive_filtering(self) -> None:
        inputs = (
            BacktestInput(
                pair="A",
                decision=decision("A", "INCLUDED"),
                price_bars=(
                    price_bar("A", 1, 100.0),
                    price_bar("A", 2, 110.0),
                    price_bar("A", 3, 120.0),
                    price_bar("A", 4, 130.0),
                ),
            ),
        )
        cfg = BacktestRunConfig(
            start_timestamp=ts(2),
            end_timestamp=ts(3),
        )
        report = build_backtest_report(inputs, cfg, generated_at=ts(1))
        result = report.candidate_results[0]
        assert result.observation_count == 2
        assert result.total_return_pct == pytest.approx(
            (120.0 / 110.0 - 1.0) * 100.0, abs=0.01
        )


class TestWriterEndToEnd:
    def test_write_backtest_report_all_formats(self, tmp_path: Path) -> None:
        report = make_report()
        json_path = tmp_path / "report.json"
        csv_path = tmp_path / "report.csv"
        md_path = tmp_path / "report.md"
        write_backtest_report(report, json_path=json_path, csv_path=csv_path, md_path=md_path)
        assert json_path.exists()
        assert csv_path.exists()
        assert md_path.exists()
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data["report_id"] == "integration-test"
        csv_text = csv_path.read_text(encoding="utf-8")
        assert csv_text.splitlines()[0].startswith("report_id,generated_at")
        assert len(csv_text.splitlines()) == 3  # header + 2 candidates
        md_text = md_path.read_text(encoding="utf-8")
        assert md_text.startswith("# Backtest Report")
        assert "> This local backtest report is a human-audit" in md_text


class TestDeterminism:
    def test_same_inputs_produce_identical_outputs(self) -> None:
        inputs = make_inputs()
        cfg = BacktestRunConfig(allocation_mode=BacktestAllocationMode.RESEARCH_WEIGHT)
        generated_at = ts(1)
        r1 = build_backtest_report(inputs, cfg, report_id="r1", generated_at=generated_at)
        r2 = build_backtest_report(inputs, cfg, report_id="r1", generated_at=generated_at)
        assert backtest_report_to_dict(r1) == backtest_report_to_dict(r2)
        assert backtest_report_to_json_text(r1) == backtest_report_to_json_text(r2)
        assert backtest_report_to_csv_text(r1) == backtest_report_to_csv_text(r2)
        assert backtest_report_to_markdown(r1) == backtest_report_to_markdown(r2)


class TestNoMutation:
    def test_inputs_not_mutated(self) -> None:
        inputs = list(make_inputs())
        original_pairs = [inp.pair for inp in inputs]
        original_bars = [inp.price_bars for inp in inputs]
        build_backtest_report(
            inputs,
            BacktestRunConfig(allocation_mode=BacktestAllocationMode.RESEARCH_WEIGHT),
            generated_at=ts(1),
        )
        for i, inp in enumerate(inputs):
            assert inp.pair == original_pairs[i]
            assert inp.price_bars is original_bars[i]


class TestPublicExports:
    def test_build_backtest_report_exported(self) -> None:
        assert callable(build_backtest_report)

    def test_writer_functions_exported(self) -> None:
        assert callable(backtest_report_to_dict)
        assert callable(backtest_report_to_json_text)
        assert callable(backtest_report_to_csv_text)
        assert callable(backtest_report_to_markdown)
        assert callable(write_backtest_report)
