"""Tests for hunter.relative_strength.engine."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from hunter.relative_strength.engine import (
    build_relative_strength_report,
    build_relative_strength_safety_flags,
    build_relative_strength_score,
    build_relative_strength_universe_summary,
    calculate_moving_average,
    calculate_period_return,
    calculate_rank_percentiles,
    calculate_ratio_series,
    calculate_relative_return,
    calculate_slope,
    calculate_ratio_trend,
    has_unsafe_relative_strength_content,
    normalized_score,
)
from hunter.relative_strength.models import (
    OhlcvRow,
    RelativeStrengthBenchmarkKind,
    RelativeStrengthConfig,
    RelativeStrengthDataQuality,
    RelativeStrengthDecision,
    RelativeStrengthInput,
    RelativeStrengthPeriodReturn,
    RelativeStrengthRatioTrend,
    RelativeStrengthState,
)


def make_rows(symbol: str, start: float, n: int, daily_return: float = 0.0) -> tuple[OhlcvRow, ...]:
    """Generate n OHLCV rows with deterministic prices."""
    rows = []
    price = start
    for i in range(n):
        rows.append(OhlcvRow(timestamp=i, close=round(price, 8)))
        price = price * (1 + daily_return)
    return tuple(rows)


def make_btc_rows(n: int) -> tuple[OhlcvRow, ...]:
    """Generate BTC benchmark rows with small positive drift."""
    return make_rows("BTC", 50000.0, n, daily_return=0.001)


def make_eth_rows(n: int) -> tuple[OhlcvRow, ...]:
    """Generate ETH benchmark rows with small positive drift."""
    return make_rows("ETH", 3000.0, n, daily_return=0.0015)


def make_outperformer_rows(symbol: str, n: int) -> tuple[OhlcvRow, ...]:
    """Generate rows that outperform BTC."""
    return make_rows(symbol, 100.0, n, daily_return=0.02)


def make_underperformer_rows(symbol: str, n: int) -> tuple[OhlcvRow, ...]:
    """Generate rows that underperform BTC."""
    return make_rows(symbol, 100.0, n, daily_return=-0.015)


class TestSafety:
    def test_safety_flags(self) -> None:
        flags = build_relative_strength_safety_flags()
        assert flags.live_trading_enabled is False

    def test_unsafe_content_symbol(self) -> None:
        inp = RelativeStrengthInput(symbol="binance_api_key", rows=[OhlcvRow(timestamp=1, close=1.0)])
        assert has_unsafe_relative_strength_content(inp) is True

    def test_unsafe_content_string(self) -> None:
        assert has_unsafe_relative_strength_content("place_order") is True

    def test_unsafe_content_mapping(self) -> None:
        assert has_unsafe_relative_strength_content({"note": "enter_long"}) is True

    def test_safe_content(self) -> None:
        inp = RelativeStrengthInput(symbol="SOL", rows=[OhlcvRow(timestamp=1, close=1.0)])
        assert has_unsafe_relative_strength_content(inp) is False


class TestPeriodReturn:
    def test_basic_return(self) -> None:
        rows = (
            OhlcvRow(timestamp=0, close=100.0),
            OhlcvRow(timestamp=1, close=110.0),
        )
        assert calculate_period_return(rows, 1) == pytest.approx(0.10)

    def test_insufficient_data(self) -> None:
        rows = (OhlcvRow(timestamp=0, close=100.0),)
        assert calculate_period_return(rows, 1) is None

    def test_zero_start_close(self) -> None:
        # OhlcvRow rejects a zero close at construction time.
        with pytest.raises(ValueError, match="non-zero"):
            OhlcvRow(timestamp=0, close=0.0)
        # Given a valid zero start close would not occur, test the engine handles
        # a very small start close via Decimal conversion.
        from decimal import Decimal
        rows = (
            OhlcvRow(timestamp=0, close=Decimal("1e-9")),
            OhlcvRow(timestamp=1, close=110.0),
        )
        assert calculate_period_return(rows, 1) is not None

    def test_negative_return(self) -> None:
        rows = (
            OhlcvRow(timestamp=0, close=100.0),
            OhlcvRow(timestamp=1, close=90.0),
        )
        assert calculate_period_return(rows, 1) == pytest.approx(-0.10)

    def test_unsorted_rows(self) -> None:
        rows = (
            OhlcvRow(timestamp=2, close=120.0),
            OhlcvRow(timestamp=0, close=100.0),
            OhlcvRow(timestamp=1, close=110.0),
        )
        assert calculate_period_return(rows, 2) == pytest.approx(0.20)


class TestRelativeReturn:
    def test_basic(self) -> None:
        result = calculate_relative_return(0.10, 0.05, 0.08)
        assert result[0] == pytest.approx(0.05)
        assert result[1] == pytest.approx(0.02)

    def test_missing_eth(self) -> None:
        assert calculate_relative_return(0.10, 0.05, None) == (pytest.approx(0.05), None)

    def test_missing_coin(self) -> None:
        assert calculate_relative_return(None, 0.05, 0.08) == (None, None)


class TestRatioSeries:
    def test_basic(self) -> None:
        coin = (
            OhlcvRow(timestamp=0, close=100.0),
            OhlcvRow(timestamp=1, close=110.0),
        )
        btc = (
            OhlcvRow(timestamp=0, close=50.0),
            OhlcvRow(timestamp=1, close=55.0),
        )
        ratios = calculate_ratio_series(coin, btc)
        assert len(ratios) == 2
        assert ratios[0] == pytest.approx(2.0)
        assert ratios[1] == pytest.approx(2.0)

    def test_zero_benchmark_close_excluded(self) -> None:
        # OhlcvRow rejects zero close, so test exclusion via missing timestamp alignment.
        coin = (
            OhlcvRow(timestamp=0, close=100.0),
            OhlcvRow(timestamp=1, close=110.0),
        )
        btc = (OhlcvRow(timestamp=1, close=55.0),)
        ratios = calculate_ratio_series(coin, btc)
        assert len(ratios) == 1
        assert ratios[0] == pytest.approx(2.0)

    def test_mismatched_timestamps(self) -> None:
        coin = (OhlcvRow(timestamp=0, close=100.0),)
        btc = (OhlcvRow(timestamp=1, close=50.0),)
        ratios = calculate_ratio_series(coin, btc)
        assert len(ratios) == 0

    def test_no_mutation(self) -> None:
        coin = [OhlcvRow(timestamp=0, close=100.0)]
        btc = [OhlcvRow(timestamp=0, close=50.0)]
        original_coin = list(coin)
        calculate_ratio_series(coin, btc)
        assert coin == original_coin


class TestMovingAverage:
    def test_basic(self) -> None:
        values = (1.0, 2.0, 3.0, 4.0, 5.0)
        ma = calculate_moving_average(values, 3)
        assert ma == (2.0, 3.0, 4.0)

    def test_insufficient_data(self) -> None:
        values = (1.0, 2.0)
        ma = calculate_moving_average(values, 3)
        assert ma == ()


class TestSlope:
    def test_increasing(self) -> None:
        values = (1.0, 2.0, 3.0, 4.0, 5.0)
        slope = calculate_slope(values)
        assert slope > 0

    def test_flat(self) -> None:
        values = (5.0, 5.0, 5.0)
        slope = calculate_slope(values)
        assert slope == 0.0

    def test_single_value(self) -> None:
        slope = calculate_slope((1.0,))
        assert slope == 0.0

    def test_decreasing(self) -> None:
        values = (5.0, 4.0, 3.0, 2.0, 1.0)
        slope = calculate_slope(values)
        assert slope < 0


class TestRatioTrend:
    def test_has_data(self) -> None:
        ratios = (1.0, 1.01, 1.02, 1.03, 1.04)
        trend = calculate_ratio_trend(ratios, ma_window=3, lookback=5)
        assert trend.has_data is True
        assert trend.trend_score > 0

    def test_insufficient_data(self) -> None:
        ratios = (1.0, 1.01)
        trend = calculate_ratio_trend(ratios, ma_window=3, lookback=5)
        assert trend.has_data is False
        assert trend.trend_score == 0.0


class TestNormalizedScore:
    def test_below_lower(self) -> None:
        assert normalized_score(-0.50, -0.30, 0.30) == 0.0

    def test_above_upper(self) -> None:
        assert normalized_score(0.50, -0.30, 0.30) == 100.0

    def test_midpoint(self) -> None:
        assert normalized_score(0.0, -0.30, 0.30) == 50.0

    def test_none(self) -> None:
        assert normalized_score(None, -0.30, 0.30) == 0.0


class TestRankPercentiles:
    def test_tie_breaking(self) -> None:
        from hunter.relative_strength.models import RelativeStrengthScore
        score_a = RelativeStrengthScore(
            symbol="A",
            base_benchmark=RelativeStrengthBenchmarkKind.BTC,
            state=RelativeStrengthState.READY,
            decision=RelativeStrengthDecision.NEUTRAL,
            total_score=50.0,
            period_returns=(
                RelativeStrengthPeriodReturn(
                    period_days=30,
                    coin_return=0.10,
                    btc_return=0.0,
                    eth_return=None,
                    coin_minus_btc=0.10,
                    coin_minus_eth=None,
                    has_data=True,
                    reason_codes=(),
                ),
            ),
            ratio_trend=RelativeStrengthRatioTrend(
                last_ratio=1.0,
                ma_ratio=1.0,
                slope=0.0,
                trend_score=50.0,
                lookback=30,
                has_data=True,
                reason_codes=(),
            ),
            rank_percentile_30d=None,
            sub_scores={},
            data_quality=RelativeStrengthDataQuality(
                expected_rows=30,
                actual_rows=35,
                missing_rows=0,
                missing_periods=(),
                min_required_rows_met=True,
                btc_benchmark_rows=35,
                eth_benchmark_rows=35,
                stale_input_count=0,
                reason_codes=(),
            ),
            human_note="",
            reason_codes=(),
        )
        score_b = RelativeStrengthScore(
            symbol="B",
            base_benchmark=RelativeStrengthBenchmarkKind.BTC,
            state=RelativeStrengthState.READY,
            decision=RelativeStrengthDecision.NEUTRAL,
            total_score=50.0,
            period_returns=(
                RelativeStrengthPeriodReturn(
                    period_days=30,
                    coin_return=0.05,
                    btc_return=0.0,
                    eth_return=None,
                    coin_minus_btc=0.05,
                    coin_minus_eth=None,
                    has_data=True,
                    reason_codes=(),
                ),
            ),
            ratio_trend=RelativeStrengthRatioTrend(
                last_ratio=1.0,
                ma_ratio=1.0,
                slope=0.0,
                trend_score=50.0,
                lookback=30,
                has_data=True,
                reason_codes=(),
            ),
            rank_percentile_30d=None,
            sub_scores={},
            data_quality=RelativeStrengthDataQuality(
                expected_rows=30,
                actual_rows=35,
                missing_rows=0,
                missing_periods=(),
                min_required_rows_met=True,
                btc_benchmark_rows=35,
                eth_benchmark_rows=35,
                stale_input_count=0,
                reason_codes=(),
            ),
            human_note="",
            reason_codes=(),
        )
        percentiles = calculate_rank_percentiles((score_a, score_b), "coin_minus_btc_30d")
        assert percentiles["A"] > percentiles["B"]

    def test_excludes_insufficient_data(self) -> None:
        from hunter.relative_strength.models import RelativeStrengthScore
        score = RelativeStrengthScore(
            symbol="A",
            base_benchmark=RelativeStrengthBenchmarkKind.BTC,
            state=RelativeStrengthState.INSUFFICIENT_DATA,
            decision=RelativeStrengthDecision.INSUFFICIENT_DATA,
            total_score=0.0,
            period_returns=(),
            ratio_trend=RelativeStrengthRatioTrend(
                last_ratio=0.0,
                ma_ratio=0.0,
                slope=0.0,
                trend_score=0.0,
                lookback=1,
                has_data=False,
                reason_codes=(),
            ),
            rank_percentile_30d=None,
            sub_scores={},
            data_quality=RelativeStrengthDataQuality(
                expected_rows=30,
                actual_rows=10,
                missing_rows=20,
                missing_periods=(),
                min_required_rows_met=False,
                btc_benchmark_rows=35,
                eth_benchmark_rows=35,
                stale_input_count=0,
                reason_codes=(),
            ),
            human_note="",
            reason_codes=(),
        )
        percentiles = calculate_rank_percentiles((score,), "coin_minus_btc_30d")
        assert percentiles["A"] is None

    def test_invalid_metric(self) -> None:
        from hunter.relative_strength.models import RelativeStrengthScore
        score = RelativeStrengthScore(
            symbol="A",
            base_benchmark=RelativeStrengthBenchmarkKind.BTC,
            state=RelativeStrengthState.READY,
            decision=RelativeStrengthDecision.NEUTRAL,
            total_score=50.0,
            period_returns=(),
            ratio_trend=RelativeStrengthRatioTrend(
                last_ratio=1.0,
                ma_ratio=1.0,
                slope=0.0,
                trend_score=50.0,
                lookback=30,
                has_data=True,
                reason_codes=(),
            ),
            rank_percentile_30d=None,
            sub_scores={},
            data_quality=RelativeStrengthDataQuality(
                expected_rows=30,
                actual_rows=35,
                missing_rows=0,
                missing_periods=(),
                min_required_rows_met=True,
                btc_benchmark_rows=35,
                eth_benchmark_rows=35,
                stale_input_count=0,
                reason_codes=(),
            ),
            human_note="",
            reason_codes=(),
        )
        with pytest.raises(ValueError, match="invalid metric"):
            calculate_rank_percentiles((score,), "bad_metric")


class TestBuildScore:
    def test_outperformer(self) -> None:
        n = 35
        sol = RelativeStrengthInput(symbol="SOL", rows=make_outperformer_rows("SOL", n))
        btc = make_btc_rows(n)
        eth = make_eth_rows(n)
        config = RelativeStrengthConfig()
        score = build_relative_strength_score(sol, btc, eth, config)
        assert score.decision == RelativeStrengthDecision.OUTPERFORMER
        assert score.state == RelativeStrengthState.READY
        assert 0.0 <= score.total_score <= 100.0

    def test_underperformer(self) -> None:
        n = 35
        doge = RelativeStrengthInput(symbol="DOGE", rows=make_underperformer_rows("DOGE", n))
        btc = make_btc_rows(n)
        eth = make_eth_rows(n)
        config = RelativeStrengthConfig()
        score = build_relative_strength_score(doge, btc, eth, config)
        assert score.decision == RelativeStrengthDecision.UNDERPERFORMER

    def test_neutral(self) -> None:
        n = 35
        # Use BTC-like drift to create neutral relative performance.
        rows = make_rows("NEUT", 100.0, n, daily_return=0.001)
        inp = RelativeStrengthInput(symbol="NEUT", rows=rows)
        btc = make_btc_rows(n)
        eth = make_eth_rows(n)
        config = RelativeStrengthConfig()
        score = build_relative_strength_score(inp, btc, eth, config)
        assert score.decision == RelativeStrengthDecision.NEUTRAL

    def test_insufficient_data(self) -> None:
        n = 10
        sol = RelativeStrengthInput(symbol="SOL", rows=make_outperformer_rows("SOL", n))
        btc = make_btc_rows(n)
        eth = make_eth_rows(n)
        config = RelativeStrengthConfig()
        score = build_relative_strength_score(sol, btc, eth, config)
        assert score.decision == RelativeStrengthDecision.INSUFFICIENT_DATA

    def test_btc_neutral(self) -> None:
        n = 35
        btc = RelativeStrengthInput(symbol="BTC", rows=make_btc_rows(n))
        btc_benchmark = make_btc_rows(n)
        eth = make_eth_rows(n)
        config = RelativeStrengthConfig()
        score = build_relative_strength_score(btc, btc_benchmark, eth, config)
        assert score.base_benchmark == RelativeStrengthBenchmarkKind.ETH
        assert score.decision == RelativeStrengthDecision.NEUTRAL

    def test_eth_btc_benchmark(self) -> None:
        n = 35
        eth = RelativeStrengthInput(symbol="ETH", rows=make_eth_rows(n))
        btc = make_btc_rows(n)
        eth_benchmark = make_eth_rows(n)
        config = RelativeStrengthConfig()
        score = build_relative_strength_score(eth, btc, eth_benchmark, config)
        assert score.base_benchmark == RelativeStrengthBenchmarkKind.BTC

    def test_missing_eth_redistribution(self) -> None:
        n = 35
        sol = RelativeStrengthInput(symbol="SOL", rows=make_outperformer_rows("SOL", n))
        btc = make_btc_rows(n)
        config = RelativeStrengthConfig()
        score = build_relative_strength_score(sol, btc, None, config)
        assert score.decision == RelativeStrengthDecision.OUTPERFORMER

    def test_block_on_missing_data(self) -> None:
        n = 10
        sol = RelativeStrengthInput(symbol="SOL", rows=make_outperformer_rows("SOL", n))
        btc = make_btc_rows(n)
        config = RelativeStrengthConfig(block_on_missing_data=True)
        score = build_relative_strength_score(sol, btc, None, config)
        assert score.decision == RelativeStrengthDecision.BLOCKED

    def test_unsafe_input_blocked(self) -> None:
        n = 35
        rows = make_outperformer_rows("SOL", n)
        inp = RelativeStrengthInput(symbol="place_order", rows=rows)
        btc = make_btc_rows(n)
        config = RelativeStrengthConfig()
        score = build_relative_strength_score(inp, btc, None, config)
        assert score.decision == RelativeStrengthDecision.BLOCKED

    def test_no_mutation(self) -> None:
        n = 35
        rows = list(make_outperformer_rows("SOL", n))
        original_rows = list(rows)
        inp = RelativeStrengthInput(symbol="SOL", rows=rows)
        btc = list(make_btc_rows(n))
        original_btc = list(btc)
        build_relative_strength_score(inp, btc, None, RelativeStrengthConfig())
        assert rows == original_rows
        assert btc == original_btc


class TestBuildReport:
    def test_full_report(self) -> None:
        n = 35
        sol = RelativeStrengthInput(symbol="SOL", rows=make_outperformer_rows("SOL", n))
        doge = RelativeStrengthInput(symbol="DOGE", rows=make_underperformer_rows("DOGE", n))
        btc = make_btc_rows(n)
        eth = make_eth_rows(n)
        config = RelativeStrengthConfig()
        generated_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        report = build_relative_strength_report(
            universe=(sol, doge),
            btc_benchmark=btc,
            eth_benchmark=eth,
            config=config,
            generated_at=generated_at,
        )
        assert report.kind == "relative_strength_report"
        assert len(report.scores) == 2
        assert report.universe_summary.total_coins == 2
        # Verify deterministic ordering.
        symbols = [score.symbol for score in report.scores]
        assert symbols == sorted(symbols, reverse=True)

    def test_missing_eth_block(self) -> None:
        n = 35
        sol = RelativeStrengthInput(symbol="SOL", rows=make_outperformer_rows("SOL", n))
        btc = make_btc_rows(n)
        config = RelativeStrengthConfig(block_on_missing_eth=True)
        report = build_relative_strength_report(
            universe=(sol,),
            btc_benchmark=btc,
            eth_benchmark=None,
            config=config,
        )
        assert report.scores == ()
        assert "ETH_BENCHMARK_MISSING" in report.reason_codes

    def test_missing_eth_redistribution(self) -> None:
        n = 35
        sol = RelativeStrengthInput(symbol="SOL", rows=make_outperformer_rows("SOL", n))
        btc = make_btc_rows(n)
        config = RelativeStrengthConfig(block_on_missing_eth=False)
        report = build_relative_strength_report(
            universe=(sol,),
            btc_benchmark=btc,
            eth_benchmark=None,
            config=config,
        )
        assert len(report.scores) == 1
        assert report.scores[0].decision == RelativeStrengthDecision.OUTPERFORMER

    def test_blocked_for_missing_btc(self) -> None:
        config = RelativeStrengthConfig()
        report = build_relative_strength_report(
            universe=(),
            btc_benchmark=(),
            config=config,
        )
        assert report.scores == ()
        assert "MISSING_BTC_BENCHMARK" in report.reason_codes

    def test_deterministic_output(self) -> None:
        n = 35
        sol = RelativeStrengthInput(symbol="SOL", rows=make_outperformer_rows("SOL", n))
        doge = RelativeStrengthInput(symbol="DOGE", rows=make_underperformer_rows("DOGE", n))
        btc = make_btc_rows(n)
        eth = make_eth_rows(n)
        config = RelativeStrengthConfig()
        generated_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        report1 = build_relative_strength_report(
            universe=(sol, doge),
            btc_benchmark=btc,
            eth_benchmark=eth,
            config=config,
            generated_at=generated_at,
        )
        report2 = build_relative_strength_report(
            universe=(sol, doge),
            btc_benchmark=btc,
            eth_benchmark=eth,
            config=config,
            generated_at=generated_at,
        )
        assert report1 == report2

    def test_rank_percentile_filled(self) -> None:
        n = 35
        sol = RelativeStrengthInput(symbol="SOL", rows=make_outperformer_rows("SOL", n))
        doge = RelativeStrengthInput(symbol="DOGE", rows=make_underperformer_rows("DOGE", n))
        btc = make_btc_rows(n)
        eth = make_eth_rows(n)
        report = build_relative_strength_report(
            universe=(sol, doge),
            btc_benchmark=btc,
            eth_benchmark=eth,
            config=RelativeStrengthConfig(),
        )
        for score in report.scores:
            if score.state == RelativeStrengthState.READY:
                assert score.rank_percentile_30d is not None

    def test_universe_summary_counts(self) -> None:
        n = 35
        sol = RelativeStrengthInput(symbol="SOL", rows=make_outperformer_rows("SOL", n))
        doge = RelativeStrengthInput(symbol="DOGE", rows=make_underperformer_rows("DOGE", n))
        btc = make_btc_rows(n)
        eth = make_eth_rows(n)
        report = build_relative_strength_report(
            universe=(sol, doge),
            btc_benchmark=btc,
            eth_benchmark=eth,
            config=RelativeStrengthConfig(),
        )
        summary = report.universe_summary
        assert (
            summary.outperformer_count
            + summary.neutral_count
            + summary.underperformer_count
            + summary.insufficient_data_count
            + summary.blocked_count
            == summary.total_coins
        )
