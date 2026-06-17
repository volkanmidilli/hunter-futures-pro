"""Tests for indicator utility functions."""

from __future__ import annotations

import pytest

from hunter.market_state.indicators import (
    ema_slope_pct,
    exponential_moving_average,
    is_falling,
    is_flat,
    is_rising,
    percent_change,
    safe_divide,
    simple_moving_average,
)


# ---------------------------------------------------------------------------
# safe_divide
# ---------------------------------------------------------------------------

class TestSafeDivide:
    def test_normal_division(self) -> None:
        assert safe_divide(10, 2) == 5.0

    def test_zero_denominator_returns_default(self) -> None:
        assert safe_divide(10, 0) == 0.0

    def test_zero_denominator_custom_default(self) -> None:
        assert safe_divide(10, 0, default=999.0) == 999.0

    def test_negative_values(self) -> None:
        assert safe_divide(-10, 2) == -5.0

    def test_float_division(self) -> None:
        assert safe_divide(7.5, 2.5) == 3.0


# ---------------------------------------------------------------------------
# percent_change
# ---------------------------------------------------------------------------

class TestPercentChange:
    def test_normal_change(self) -> None:
        assert percent_change(110, 100) == 10.0

    def test_negative_change(self) -> None:
        assert percent_change(90, 100) == -10.0

    def test_zero_previous_returns_default(self) -> None:
        assert percent_change(100, 0) == 0.0

    def test_zero_previous_custom_default(self) -> None:
        assert percent_change(100, 0, default=-1.0) == -1.0

    def test_no_change(self) -> None:
        assert percent_change(100, 100) == 0.0

    def test_double(self) -> None:
        assert percent_change(200, 100) == 100.0


# ---------------------------------------------------------------------------
# simple_moving_average
# ---------------------------------------------------------------------------

class TestSimpleMovingAverage:
    def test_basic_sma(self) -> None:
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = simple_moving_average(values, 3)
        assert result == [2.0, 3.0, 4.0]

    def test_period_1(self) -> None:
        values = [5.0, 10.0, 15.0]
        result = simple_moving_average(values, 1)
        assert result == [5.0, 10.0, 15.0]

    def test_insufficient_data_returns_empty(self) -> None:
        values = [1.0, 2.0]
        result = simple_moving_average(values, 3)
        assert result == []

    def test_exact_period(self) -> None:
        values = [1.0, 2.0, 3.0]
        result = simple_moving_average(values, 3)
        assert result == [2.0]

    def test_invalid_period_raises(self) -> None:
        with pytest.raises(ValueError, match="period must be >= 1"):
            simple_moving_average([1, 2, 3], 0)

    def test_negative_period_raises(self) -> None:
        with pytest.raises(ValueError, match="period must be >= 1"):
            simple_moving_average([1, 2, 3], -1)

    def test_empty_values(self) -> None:
        result = simple_moving_average([], 1)
        assert result == []

    def test_large_values(self) -> None:
        values = [100.0, 200.0, 300.0, 400.0]
        result = simple_moving_average(values, 2)
        assert result == [150.0, 250.0, 350.0]


# ---------------------------------------------------------------------------
# exponential_moving_average
# ---------------------------------------------------------------------------

class TestExponentialMovingAverage:
    def test_basic_ema(self) -> None:
        values = [10.0, 11.0, 12.0, 13.0, 14.0]
        result = exponential_moving_average(values, 3)
        # First EMA = SMA of first 3 = 11.0
        # multiplier = 2 / (3 + 1) = 0.5
        # values[3:] = [13.0, 14.0]
        # EMA_4 = (13 * 0.5) + (11 * 0.5) = 12.0
        # EMA_5 = (14 * 0.5) + (12.0 * 0.5) = 13.0
        assert len(result) == 3
        assert result[0] == 11.0
        assert result[1] == 12.0
        assert result[2] == 13.0

    def test_period_1(self) -> None:
        values = [5.0, 10.0, 15.0]
        result = exponential_moving_average(values, 1)
        # multiplier = 2 / (1 + 1) = 1.0
        # First EMA = 5.0
        # EMA_2 = (10 * 1.0) + (5.0 * 0.0) = 10.0
        # EMA_3 = (15 * 1.0) + (10.0 * 0.0) = 15.0
        assert result == [5.0, 10.0, 15.0]

    def test_insufficient_data_returns_empty(self) -> None:
        values = [1.0, 2.0]
        result = exponential_moving_average(values, 3)
        assert result == []

    def test_exact_period(self) -> None:
        values = [1.0, 2.0, 3.0]
        result = exponential_moving_average(values, 3)
        assert len(result) == 1
        assert result[0] == 2.0

    def test_invalid_period_raises(self) -> None:
        with pytest.raises(ValueError, match="period must be >= 1"):
            exponential_moving_average([1, 2, 3], 0)

    def test_empty_values(self) -> None:
        result = exponential_moving_average([], 1)
        assert result == []

    def test_known_values(self) -> None:
        # Known EMA(3) calculation:
        # values: [22.81, 23.09, 22.91, 23.23, 22.99, 23.10, 23.38, 23.26]
        # SMA(3) of first 3 = (22.81 + 23.09 + 22.91) / 3 = 22.9367
        # multiplier = 2 / (3 + 1) = 0.5
        values = [22.81, 23.09, 22.91, 23.23, 22.99]
        result = exponential_moving_average(values, 3)
        assert len(result) == 3
        assert round(result[0], 4) == 22.9367
        # EMA_4 = (23.23 * 0.5) + (22.9367 * 0.5) = 23.0833
        assert round(result[1], 4) == 23.0833
        # EMA_5 = (22.99 * 0.5) + (23.0833 * 0.5) = 23.0367
        assert round(result[2], 4) == 23.0367


# ---------------------------------------------------------------------------
# ema_slope_pct
# ---------------------------------------------------------------------------

class TestEmaSlopePct:
    def test_rising_slope(self) -> None:
        ema_values = [100.0, 101.0, 102.0, 103.0, 104.0]
        # lookback=2: compare ema[-1]=104 vs ema[-3]=102
        # ((104 - 102) / 102) * 100 = 1.9608
        result = ema_slope_pct(ema_values, 2)
        assert round(result, 4) == 1.9608

    def test_falling_slope(self) -> None:
        ema_values = [100.0, 99.0, 98.0, 97.0, 96.0]
        # lookback=2: compare ema[-1]=96 vs ema[-3]=98
        # ((96 - 98) / 98) * 100 = -2.0408
        result = ema_slope_pct(ema_values, 2)
        assert round(result, 4) == -2.0408

    def test_flat_slope(self) -> None:
        ema_values = [100.0, 100.0, 100.0, 100.0, 100.0]
        result = ema_slope_pct(ema_values, 2)
        assert result == 0.0

    def test_lookback_1(self) -> None:
        ema_values = [100.0, 101.0]
        result = ema_slope_pct(ema_values, 1)
        assert result == 1.0

    def test_lookback_5_matches_spec(self) -> None:
        # SPEC-003 default: slope_lookback = 5
        ema_values = [100.0, 101.0, 102.0, 103.0, 104.0, 105.0]
        # lookback=5: compare ema[-1]=105 vs ema[-6]=100
        # ((105 - 100) / 100) * 100 = 5.0
        result = ema_slope_pct(ema_values, 5)
        assert result == 5.0

    def test_zero_ema_n_candles_ago_returns_default(self) -> None:
        ema_values = [0.0, 0.0, 2.0]
        result = ema_slope_pct(ema_values, 1)
        # ema_n_candles_ago = ema_values[-2] = 0.0, division by zero -> default 0.0
        assert result == 0.0

    def test_insufficient_data_raises(self) -> None:
        with pytest.raises(ValueError, match="ema_values must have at least 3 elements"):
            ema_slope_pct([100.0, 101.0], 2)

    def test_lookback_too_large_raises(self) -> None:
        with pytest.raises(ValueError, match="ema_values must have at least 6 elements"):
            ema_slope_pct([100.0, 101.0, 102.0, 103.0, 104.0], 5)

    def test_invalid_lookback_raises(self) -> None:
        with pytest.raises(ValueError, match="lookback must be >= 1"):
            ema_slope_pct([100.0, 101.0, 102.0], 0)


# ---------------------------------------------------------------------------
# is_rising / is_falling / is_flat
# ---------------------------------------------------------------------------

class TestSlopeDirection:
    def test_is_rising_above_threshold(self) -> None:
        assert is_rising(1.0, 0.5) is True

    def test_is_rising_at_threshold(self) -> None:
        assert is_rising(0.5, 0.5) is False

    def test_is_rising_below_threshold(self) -> None:
        assert is_rising(0.4, 0.5) is False

    def test_is_falling_below_negative_threshold(self) -> None:
        assert is_falling(-1.0, 0.5) is True

    def test_is_falling_at_threshold(self) -> None:
        assert is_falling(-0.5, 0.5) is False

    def test_is_falling_above_negative_threshold(self) -> None:
        assert is_falling(-0.4, 0.5) is False

    def test_is_flat_within_threshold(self) -> None:
        assert is_flat(0.3, 0.5) is True

    def test_is_flat_at_threshold(self) -> None:
        assert is_flat(0.5, 0.5) is True

    def test_is_flat_above_threshold(self) -> None:
        assert is_flat(0.6, 0.5) is False

    def test_is_flat_below_negative_threshold(self) -> None:
        assert is_flat(-0.6, 0.5) is False

    def test_combined_rising_falling_flat(self) -> None:
        slope = 0.8
        threshold = 0.5
        assert is_rising(slope, threshold) is True
        assert is_falling(slope, threshold) is False
        assert is_flat(slope, threshold) is False

    def test_combined_falling(self) -> None:
        slope = -0.8
        threshold = 0.5
        assert is_rising(slope, threshold) is False
        assert is_falling(slope, threshold) is True
        assert is_flat(slope, threshold) is False

    def test_combined_flat(self) -> None:
        slope = 0.2
        threshold = 0.5
        assert is_rising(slope, threshold) is False
        assert is_falling(slope, threshold) is False
        assert is_flat(slope, threshold) is True


# ---------------------------------------------------------------------------
# Safety tests
# ---------------------------------------------------------------------------

class TestSafety:
    def test_no_network_calls(self) -> None:
        # All indicator functions are pure and stateless
        # Check that the module itself does not import network modules
        import hunter.market_state.indicators as indicators_module

        network_modules = {"urllib", "http", "socket", "requests", "aiohttp"}
        # Check module's globals for imports
        module_globals = set(indicators_module.__dict__.keys())
        overlap = network_modules & module_globals
        assert not overlap, f"Network modules found in indicators: {overlap}"

    def test_no_trading_logic(self) -> None:
        # Verify no trading-related terms exist in module source
        import inspect

        import hunter.market_state.indicators as indicators_module

        source = inspect.getsource(indicators_module)
        trading_terms = ["buy", "sell", "order", "position", "trade", "profit", "loss"]
        found = [term for term in trading_terms if term.lower() in source.lower()]
        assert not found, f"Trading terms found in indicators: {found}"
