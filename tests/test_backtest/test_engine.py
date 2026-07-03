"""Tests for hunter.backtest.engine.

All tests use in-memory fixtures only. No filesystem, network, exchange, or
Freqtrade references are used.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from hunter.backtest import (
    FORBIDDEN_BACKTEST_TERMS,
    UNSAFE_BACKTEST_CONTENT,
    BacktestAllocationMode,
    BacktestCandidateDecision,
    BacktestDataQuality,
    BacktestInput,
    BacktestPortfolioSnapshot,
    BacktestPriceBar,
    BacktestReport,
    BacktestRunConfig,
    BacktestSafetyFlags,
    BacktestState,
    MISSING_DECISION_CONTEXT,
    MISSING_PRICE_HISTORY,
    build_backtest_report,
    build_backtest_safety_flags,
)


def ts(day: int, hour: int = 0) -> datetime:
    return datetime(2024, 1, day, hour, tzinfo=timezone.utc)


def bar(
    pair: str,
    day: int,
    close: float,
    hour: int = 0,
) -> BacktestPriceBar:
    return BacktestPriceBar(
        pair=pair,
        timestamp=ts(day, hour),
        close=close,
    )


def decision(pair: str, state: str, final_weight_pct: float = 0.0) -> BacktestCandidateDecision:
    return BacktestCandidateDecision(
        pair=pair,
        state=state,
        classification="CORE_RESEARCH_ALLOCATION",
        final_weight_pct=final_weight_pct,
    )


def input_with_bars(
    pair: str,
    state: str,
    closes: list[float],
    days: list[int] | None = None,
    final_weight_pct: float = 0.0,
) -> BacktestInput:
    if days is None:
        days = list(range(1, len(closes) + 1))
    bars = tuple(bar(pair, day, close) for day, close in zip(days, closes))
    return BacktestInput(
        pair=pair,
        decision=decision(pair, state, final_weight_pct=final_weight_pct),
        price_bars=bars,
    )


class TestPublicExports:
    def test_build_backtest_report_exported(self) -> None:
        assert callable(build_backtest_report)

    def test_build_backtest_safety_flags_exported(self) -> None:
        assert callable(build_backtest_safety_flags)

    def test_forbidden_terms_exported(self) -> None:
        assert isinstance(FORBIDDEN_BACKTEST_TERMS, frozenset)
        assert "binance" in FORBIDDEN_BACKTEST_TERMS


class TestDeterminism:
    def test_same_inputs_produce_same_report(self) -> None:
        inputs = [
            input_with_bars("A", "INCLUDED", [100.0, 110.0, 121.0]),
            input_with_bars("B", "INCLUDED", [200.0, 190.0, 180.0]),
        ]
        cfg = BacktestRunConfig(allocation_mode=BacktestAllocationMode.EQUAL_WEIGHT)
        generated_at = ts(1)
        report1 = build_backtest_report(inputs, cfg, report_id="r1", generated_at=generated_at)
        report2 = build_backtest_report(inputs, cfg, report_id="r1", generated_at=generated_at)
        assert report1 == report2
        assert report1.portfolio_result.total_return_pct == report2.portfolio_result.total_return_pct

    def test_candidate_results_sorted_deterministically(self) -> None:
        inputs = [
            input_with_bars("A", "INCLUDED", [100.0, 110.0]),
            input_with_bars("B", "CAPPED", [100.0, 105.0]),
            input_with_bars("C", "WATCHLIST", [100.0, 120.0]),
        ]
        cfg = BacktestRunConfig(allocation_mode=BacktestAllocationMode.EQUAL_WEIGHT)
        report = build_backtest_report(inputs, cfg)
        states = [r.state for r in report.candidate_results]
        assert states[:2] == [BacktestState.INCLUDED, BacktestState.CAPPED]
        assert BacktestState.WATCHLIST in states


class TestCandidateMetrics:
    def test_total_return_pct(self) -> None:
        inp = input_with_bars("A", "INCLUDED", [100.0, 110.0])
        cfg = BacktestRunConfig(allocation_mode=BacktestAllocationMode.EQUAL_WEIGHT)
        report = build_backtest_report([inp], cfg)
        result = report.candidate_results[0]
        assert result.total_return_pct == 10.0

    def test_win_rate_and_volatility(self) -> None:
        inp = input_with_bars("A", "INCLUDED", [100.0, 110.0, 121.0])
        cfg = BacktestRunConfig(allocation_mode=BacktestAllocationMode.EQUAL_WEIGHT)
        report = build_backtest_report([inp], cfg)
        result = report.candidate_results[0]
        assert result.win_rate_pct == 100.0
        assert result.volatility_pct >= 0.0
        assert result.observation_count == 3

    def test_max_drawdown(self) -> None:
        inp = input_with_bars("A", "INCLUDED", [100.0, 80.0, 90.0])
        cfg = BacktestRunConfig(allocation_mode=BacktestAllocationMode.EQUAL_WEIGHT)
        report = build_backtest_report([inp], cfg)
        result = report.candidate_results[0]
        assert result.max_drawdown_pct == 20.0
        assert result.total_return_pct == -10.0

    def test_insufficient_price_history(self) -> None:
        inp = input_with_bars("A", "INCLUDED", [100.0])
        cfg = BacktestRunConfig(min_observation_count=2)
        report = build_backtest_report([inp], cfg)
        result = report.candidate_results[0]
        assert result.state == BacktestState.INSUFFICIENT_DATA
        assert result.insufficient_data_count == 1

    def test_missing_price_history(self) -> None:
        inp = BacktestInput(
            pair="A",
            decision=decision("A", "INCLUDED"),
            price_bars=(),
        )
        cfg = BacktestRunConfig()
        report = build_backtest_report([inp], cfg)
        result = report.candidate_results[0]
        assert result.state == BacktestState.INSUFFICIENT_DATA
        assert MISSING_PRICE_HISTORY in result.reason_codes

    def test_invalid_close_zero_blocked(self) -> None:
        with pytest.raises(ValueError, match="close must be a strictly positive"):
            input_with_bars("A", "INCLUDED", [100.0, 0.0])

    def test_invalid_close_negative_blocked(self) -> None:
        with pytest.raises(ValueError, match="close must be a strictly positive"):
            input_with_bars("A", "INCLUDED", [100.0, -10.0])

    def test_volatility_scale_factor_affects_volatility(self) -> None:
        closes = [100.0, 110.0, 121.0, 133.1]
        inp = input_with_bars("A", "INCLUDED", closes)
        cfg1 = BacktestRunConfig(
            allocation_mode=BacktestAllocationMode.EQUAL_WEIGHT,
            volatility_scale_factor=1.0,
        )
        cfg2 = BacktestRunConfig(
            allocation_mode=BacktestAllocationMode.EQUAL_WEIGHT,
            volatility_scale_factor=4.0,
        )
        r1 = build_backtest_report([inp], cfg1).candidate_results[0]
        r2 = build_backtest_report([inp], cfg2).candidate_results[0]
        assert r2.volatility_pct == pytest.approx(r1.volatility_pct * 2.0)


class TestPortfolioMetrics:
    def test_portfolio_from_equity_curve(self) -> None:
        # A goes up 10%, B goes down 5%, equal weights -> 2.5% return
        inputs = [
            input_with_bars("A", "INCLUDED", [100.0, 110.0]),
            input_with_bars("B", "INCLUDED", [100.0, 95.0]),
        ]
        cfg = BacktestRunConfig(allocation_mode=BacktestAllocationMode.EQUAL_WEIGHT)
        report = build_backtest_report(inputs, cfg)
        portfolio = report.portfolio_result
        assert portfolio.total_return_pct == 2.5
        assert portfolio.observation_count == 2
        assert portfolio.candidate_count == 2

    def test_research_weight_allocation(self) -> None:
        inputs = [
            input_with_bars("A", "INCLUDED", [100.0, 110.0], final_weight_pct=60.0),
            input_with_bars("B", "INCLUDED", [100.0, 90.0], final_weight_pct=40.0),
        ]
        cfg = BacktestRunConfig(allocation_mode=BacktestAllocationMode.RESEARCH_WEIGHT)
        report = build_backtest_report(inputs, cfg)
        result_by_pair = {r.pair: r for r in report.candidate_results}
        assert result_by_pair["A"].simulated_weight == 60.0
        assert result_by_pair["B"].simulated_weight == 40.0
        # 60% * 10% + 40% * (-10%) = 2.0%
        assert report.portfolio_result.total_return_pct == 2.0

    def test_custom_weight_allocation(self) -> None:
        inputs = [
            input_with_bars("A", "INCLUDED", [100.0, 110.0]),
            input_with_bars("B", "INCLUDED", [100.0, 90.0]),
        ]
        cfg = BacktestRunConfig(
            allocation_mode=BacktestAllocationMode.CUSTOM_WEIGHT,
            custom_weights={"A": 3.0, "B": 1.0},
        )
        report = build_backtest_report(inputs, cfg)
        result_by_pair = {r.pair: r for r in report.candidate_results}
        assert result_by_pair["A"].simulated_weight == 75.0
        assert result_by_pair["B"].simulated_weight == 25.0


class TestTimestampAlignment:
    def test_union_timestamps_no_carry_forward(self) -> None:
        # A has bars on day 1, 3, 5; B has bars on day 1, 2, 3, 4, 5
        inputs = [
            input_with_bars("A", "INCLUDED", [100.0, 110.0, 120.0], days=[1, 3, 5]),
            input_with_bars("B", "INCLUDED", [100.0, 101.0, 102.0, 103.0, 104.0], days=[1, 2, 3, 4, 5]),
        ]
        cfg = BacktestRunConfig(allocation_mode=BacktestAllocationMode.EQUAL_WEIGHT)
        report = build_backtest_report(inputs, cfg)
        # Union should be 5 timestamps
        assert report.portfolio_result.observation_count == 5
        # A missing at day 2 and 4 -> missing_data_count = 2
        a_result = next(r for r in report.candidate_results if r.pair == "A")
        assert a_result.missing_data_count == 2
        b_result = next(r for r in report.candidate_results if r.pair == "B")
        assert b_result.missing_data_count == 0

    def test_snapshot_observation_count(self) -> None:
        inputs = [
            input_with_bars("A", "INCLUDED", [100.0, 110.0], days=[1, 3]),
            input_with_bars("B", "INCLUDED", [100.0, 105.0], days=[1, 2]),
        ]
        cfg = BacktestRunConfig(allocation_mode=BacktestAllocationMode.EQUAL_WEIGHT)
        report = build_backtest_report(inputs, cfg)
        # Union is day 1, 2, 3
        assert report.portfolio_result.observation_count == 3
        snaps = report.portfolio_result.equity_curve
        by_day = {s.timestamp.day: s for s in snaps}
        assert by_day[1].observation_count == 2
        assert by_day[2].observation_count == 1
        assert by_day[3].observation_count == 1


class TestNoMutation:
    def test_input_price_bars_not_mutated(self) -> None:
        inputs = [
            input_with_bars("A", "INCLUDED", [100.0, 110.0]),
        ]
        original_bars = inputs[0].price_bars
        cfg = BacktestRunConfig()
        build_backtest_report(inputs, cfg)
        assert inputs[0].price_bars is original_bars
        assert inputs[0].pair == "A"

    def test_config_not_mutated(self) -> None:
        cfg = BacktestRunConfig(custom_weights={"A": 1.0})
        build_backtest_report([], cfg)
        assert dict(cfg.custom_weights) == {"A": 1.0}


class TestConfigValidation:
    def test_invalid_config_returns_blocked_report(self) -> None:
        cfg = BacktestRunConfig(volatility_scale_factor=-1.0)
        inputs = [input_with_bars("A", "INCLUDED", [100.0, 110.0])]
        report = build_backtest_report(inputs, cfg)
        assert report.portfolio_result.candidate_count == 0
        assert report.data_quality.safety_flags_ok is False

    def test_empty_inputs_returns_blocked_report(self) -> None:
        cfg = BacktestRunConfig()
        report = build_backtest_report([], cfg)
        assert report.portfolio_result.candidate_count == 0
        assert report.data_quality.safety_flags_ok is False


class TestTimestampWindow:
    def test_start_end_inclusive_filtering(self) -> None:
        inputs = [
            input_with_bars(
                "A", "INCLUDED", [100.0, 110.0, 120.0, 130.0], days=[1, 2, 3, 4]
            ),
        ]
        cfg = BacktestRunConfig(
            start_timestamp=ts(2),
            end_timestamp=ts(3),
            allocation_mode=BacktestAllocationMode.EQUAL_WEIGHT,
        )
        report = build_backtest_report(inputs, cfg)
        result = report.candidate_results[0]
        assert result.observation_count == 2
        assert result.total_return_pct == pytest.approx(
            (120.0 / 110.0 - 1.0) * 100.0, rel=1e-4
        )

    def test_start_after_last_bar_results_in_insufficient_data(self) -> None:
        inputs = [
            input_with_bars("A", "INCLUDED", [100.0, 110.0], days=[1, 2]),
        ]
        cfg = BacktestRunConfig(
            start_timestamp=ts(5),
            end_timestamp=ts(6),
        )
        report = build_backtest_report(inputs, cfg)
        result = report.candidate_results[0]
        assert result.state == BacktestState.INSUFFICIENT_DATA


class TestUnsafeContentFailClosed:
    def test_unsafe_pair_blocks_report(self) -> None:
        inp = BacktestInput(
            pair="buy_signal",
            decision=decision("buy_signal", "INCLUDED"),
            price_bars=(bar("buy_signal", 1, 100.0), bar("buy_signal", 2, 110.0)),
        )
        cfg = BacktestRunConfig()
        report = build_backtest_report([inp], cfg)
        assert report.data_quality.safety_flags_ok is False
        assert report.portfolio_result.candidate_count == 0
        assert UNSAFE_BACKTEST_CONTENT in report.reason_codes

    def test_unsafe_metadata_blocks_pair(self) -> None:
        inp = BacktestInput(
            pair="A",
            decision=decision("A", "INCLUDED"),
            price_bars=(bar("A", 1, 100.0), bar("A", 2, 110.0)),
            metadata={"note": "this is a live_trading signal"},
        )
        cfg = BacktestRunConfig()
        report = build_backtest_report([inp], cfg)
        assert report.data_quality.safety_flags_ok is False
        assert report.portfolio_result.candidate_count == 0


class TestMissingDecision:
    def test_allow_missing_decision_equal_weight(self) -> None:
        inp = BacktestInput(
            pair="A",
            price_bars=(bar("A", 1, 100.0), bar("A", 2, 110.0)),
        )
        cfg = BacktestRunConfig(
            allow_missing_decision=True,
            allocation_mode=BacktestAllocationMode.EQUAL_WEIGHT,
        )
        report = build_backtest_report([inp], cfg)
        result = report.candidate_results[0]
        assert result.state == BacktestState.INCLUDED
        assert result.simulated_weight == 100.0

    def test_missing_decision_without_flag_is_insufficient_data(self) -> None:
        inp = BacktestInput(
            pair="A",
            price_bars=(bar("A", 1, 100.0), bar("A", 2, 110.0)),
        )
        cfg = BacktestRunConfig()
        report = build_backtest_report([inp], cfg)
        result = report.candidate_results[0]
        assert result.state == BacktestState.INSUFFICIENT_DATA
        assert MISSING_DECISION_CONTEXT in result.reason_codes

    def test_missing_decision_with_block_on_missing_context(self) -> None:
        inp = BacktestInput(
            pair="A",
            price_bars=(bar("A", 1, 100.0), bar("A", 2, 110.0)),
        )
        cfg = BacktestRunConfig(block_on_missing_context=True)
        report = build_backtest_report([inp], cfg)
        result = report.candidate_results[0]
        assert result.state == BacktestState.BLOCKED


class TestSafetyFlags:
    def test_build_safety_flags_safe_inputs(self) -> None:
        inp = input_with_bars("A", "INCLUDED", [100.0, 110.0])
        cfg = BacktestRunConfig()
        flags = build_backtest_safety_flags([inp], cfg)
        assert flags.is_safe is True

    def test_build_safety_flags_detects_unsafe(self) -> None:
        inp = BacktestInput(
            pair="A",
            decision=decision("A", "INCLUDED"),
            price_bars=(bar("A", 1, 100.0), bar("A", 2, 110.0)),
            metadata={"note": "binance api key"},
        )
        cfg = BacktestRunConfig()
        flags = build_backtest_safety_flags([inp], cfg)
        assert flags.is_safe is False
        assert flags.has_unsafe_content is True


class TestBlockedReportFactory:
    def test_build_backtest_report_blocked_with_unsafe_reason(self) -> None:
        report = BacktestReport.blocked(reason_code=UNSAFE_BACKTEST_CONTENT)
        assert isinstance(report.safety_flags, BacktestSafetyFlags)
        assert report.data_quality.has_unsafe_content is True
        assert report.candidate_results == ()
        assert report.portfolio_result.equity_curve == ()

    def test_report_notes_contain_research_only(self) -> None:
        inputs = [
            input_with_bars("A", "INCLUDED", [100.0, 110.0]),
        ]
        cfg = BacktestRunConfig()
        report = build_backtest_report(inputs, cfg)
        notes = "\n".join(report.notes)
        assert "human research" in notes.lower()
        assert "not orders" in notes.lower() or "not" in notes.lower()
