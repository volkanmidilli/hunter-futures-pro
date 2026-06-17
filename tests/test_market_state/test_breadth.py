"""Tests for the Market Breadth Engine."""

from __future__ import annotations

import pytest

from hunter.market_state.breadth import (
    BreadthConfig,
    calculate_advancing_declining_pct,
    calculate_breadth,
    calculate_breadth_score,
    calculate_outperforming_btc_pct,
    calculate_percent_above_ema,
    calculate_percent_ema_rising,
    filter_valid_symbols,
)
from hunter.market_state.models import (
    BreadthOutput,
    DataQuality,
    OutputStatus,
    RiskState,
)


class TestBreadthConfig:
    """Tests for BreadthConfig frozen dataclass."""

    def test_default_values(self) -> None:
        config = BreadthConfig()
        assert config.min_universe_size == 20
        assert config.ema_fast_period == 20
        assert config.ema_slow_period == 50
        assert config.ema_long_period == 200
        assert config.recent_return_days == 7
        assert config.outperform_btc_short_days == 7
        assert config.outperform_btc_long_days == 30
        assert config.stale_threshold_candles == 2
        assert config.risk_on_threshold == 65
        assert config.risk_off_threshold == 35
        assert config.min_quote_volume == 1_000_000.0
        assert config.slope_lookback == 5
        assert config.slope_threshold_pct == 0.5

    def test_custom_values(self) -> None:
        config = BreadthConfig(min_universe_size=10, ema_fast_period=10)
        assert config.min_universe_size == 10
        assert config.ema_fast_period == 10
        assert config.ema_slow_period == 50  # default

    def test_frozen_cannot_modify(self) -> None:
        config = BreadthConfig()
        with pytest.raises(AttributeError):
            config.min_universe_size = 50


class TestFilterValidSymbols:
    """Tests for universe filtering and validation."""

    def test_all_valid_symbols(self) -> None:
        candles = {
            "BTCUSDT": [100.0] * 55,
            "ETHUSDT": [200.0] * 55,
        }
        valid, invalid_count, reasons = filter_valid_symbols(candles, BreadthConfig())
        assert len(valid) == 2
        assert invalid_count == 0
        assert reasons == []

    def test_missing_candles_excluded(self) -> None:
        candles = {
            "BTCUSDT": [100.0] * 55,
            "ETHUSDT": [],
        }
        valid, invalid_count, reasons = filter_valid_symbols(candles, BreadthConfig())
        assert len(valid) == 1
        assert invalid_count == 1
        assert "DATA_MISSING" in reasons

    def test_insufficient_history_excluded(self) -> None:
        candles = {
            "BTCUSDT": [100.0] * 55,
            "ETHUSDT": [200.0] * 10,
        }
        valid, invalid_count, reasons = filter_valid_symbols(candles, BreadthConfig())
        assert len(valid) == 1
        assert invalid_count == 1
        assert "INSUFFICIENT_HISTORY" in reasons

    def test_invalid_price_excluded(self) -> None:
        candles = {
            "BTCUSDT": [100.0] * 55,
            "ETHUSDT": [200.0] * 54 + [0.0],
        }
        valid, invalid_count, reasons = filter_valid_symbols(candles, BreadthConfig())
        assert len(valid) == 1
        assert invalid_count == 1
        assert "DATA_INVALID" in reasons

    def test_negative_price_excluded(self) -> None:
        candles = {
            "BTCUSDT": [100.0] * 55,
            "ETHUSDT": [200.0] * 54 + [-1.0],
        }
        valid, invalid_count, reasons = filter_valid_symbols(candles, BreadthConfig())
        assert len(valid) == 1
        assert invalid_count == 1
        assert "DATA_INVALID" in reasons


class TestCalculatePercentAboveEma:
    """Tests for percent above EMA calculation."""

    def test_all_above_ema20(self) -> None:
        # Rising prices - all above EMA20
        candles = {
            "SYM1": list(range(100, 155)),  # rising
            "SYM2": list(range(200, 255)),  # rising
        }
        pct = calculate_percent_above_ema(candles, 20)
        assert pct == 1.0

    def test_none_above_ema20(self) -> None:
        # Falling prices - all below EMA20
        candles = {
            "SYM1": list(range(155, 100, -1)),  # falling
            "SYM2": list(range(255, 200, -1)),  # falling
        }
        pct = calculate_percent_above_ema(candles, 20)
        assert pct == 0.0

    def test_half_above_ema20(self) -> None:
        candles = {
            "SYM1": list(range(100, 155)),  # rising - above EMA
            "SYM2": list(range(155, 100, -1)),  # falling - below EMA
        }
        pct = calculate_percent_above_ema(candles, 20)
        assert pct == 0.5

    def test_empty_universe(self) -> None:
        pct = calculate_percent_above_ema({}, 20)
        assert pct == 0.0


class TestCalculatePercentEmaRising:
    """Tests for percent EMA rising calculation."""

    def test_all_ema_rising(self) -> None:
        candles = {
            "SYM1": list(range(100, 155)),
            "SYM2": list(range(200, 255)),
        }
        pct = calculate_percent_ema_rising(candles, 20, 5, 0.5)
        assert pct == 1.0

    def test_none_ema_rising(self) -> None:
        candles = {
            "SYM1": list(range(155, 100, -1)),
            "SYM2": list(range(255, 200, -1)),
        }
        pct = calculate_percent_ema_rising(candles, 20, 5, 0.5)
        assert pct == 0.0

    def test_empty_universe(self) -> None:
        pct = calculate_percent_ema_rising({}, 20, 5, 0.5)
        assert pct == 0.0


class TestCalculateAdvancingDeclining:
    """Tests for advancing/declining percentage calculation."""

    def test_all_advancing(self) -> None:
        candles = {
            "SYM1": [100.0, 101.0],
            "SYM2": [200.0, 201.0],
        }
        adv, dec = calculate_advancing_declining_pct(candles)
        assert adv == 1.0
        assert dec == 0.0

    def test_all_declining(self) -> None:
        candles = {
            "SYM1": [101.0, 100.0],
            "SYM2": [201.0, 200.0],
        }
        adv, dec = calculate_advancing_declining_pct(candles)
        assert adv == 0.0
        assert dec == 1.0

    def test_mixed(self) -> None:
        candles = {
            "SYM1": [100.0, 101.0],  # advancing
            "SYM2": [201.0, 200.0],  # declining
        }
        adv, dec = calculate_advancing_declining_pct(candles)
        assert adv == 0.5
        assert dec == 0.5

    def test_empty_universe(self) -> None:
        adv, dec = calculate_advancing_declining_pct({})
        assert adv == 0.0
        assert dec == 0.0

    def test_flat_excluded(self) -> None:
        candles = {
            "SYM1": [100.0, 101.0],  # advancing
            "SYM2": [100.0, 100.0],  # flat - excluded from both counts
        }
        adv, dec = calculate_advancing_declining_pct(candles)
        # Flat symbols are excluded from both advancing and declining counts
        # So 1 advancing out of 2 total = 0.5 (flat is included in total but not counted)
        # Actually the function counts total as all symbols with len >= 2
        # and only increments advancing/declining when price changes
        # So flat is counted in total but not in either category
        assert adv == 0.5
        assert dec == 0.0


class TestCalculateOutperformingBtc:
    """Tests for outperforming BTC percentage calculation."""

    def test_all_outperform_btc(self) -> None:
        # BTC flat, altcoins rising
        btc = [100.0] * 8
        candles = {
            "SYM1": [100.0, 110.0],  # +10%
            "SYM2": [100.0, 110.0],  # +10%
        }
        pct = calculate_outperforming_btc_pct(candles, btc, 7)
        assert pct == 1.0

    def test_none_outperform_btc(self) -> None:
        # BTC rising, altcoins flat
        btc = [100.0, 110.0]
        candles = {
            "SYM1": [100.0] * 8,  # flat
            "SYM2": [100.0] * 8,  # flat
        }
        pct = calculate_outperforming_btc_pct(candles, btc, 7)
        assert pct == 0.0

    def test_half_outperform_btc(self) -> None:
        btc = [100.0, 105.0]  # +5%
        candles = {
            "SYM1": [100.0, 110.0],  # +10% - outperforms
            "SYM2": [100.0, 102.0],  # +2% - underperforms
        }
        pct = calculate_outperforming_btc_pct(candles, btc, 7)
        assert pct == 0.5

    def test_empty_universe(self) -> None:
        pct = calculate_outperforming_btc_pct({}, [100.0] * 8, 7)
        assert pct == 0.0

    def test_missing_btc(self) -> None:
        candles = {
            "SYM1": [100.0, 110.0],
        }
        pct = calculate_outperforming_btc_pct(candles, [], 7)
        assert pct == 0.0

    def test_insufficient_btc(self) -> None:
        candles = {
            "SYM1": [100.0, 110.0],
        }
        pct = calculate_outperforming_btc_pct(candles, [100.0], 7)
        assert pct == 0.0


class TestCalculateBreadthScore:
    """Tests for breadth score calculation."""

    def test_max_score(self) -> None:
        score = calculate_breadth_score(1.0, 1.0, 1.0, 1.0, 1.0, 1.0)
        assert score == 100

    def test_min_score(self) -> None:
        score = calculate_breadth_score(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        assert score == 0

    def test_mixed_score(self) -> None:
        # All at 50%
        score = calculate_breadth_score(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
        expected = int(0.5 * 25 + 0.5 * 20 + 0.5 * 20 + 0.5 * 15 + 0.5 * 10 + 0.5 * 10)
        assert score == expected

    def test_clamped_above_100(self) -> None:
        score = calculate_breadth_score(1.0, 1.0, 1.0, 1.0, 1.0, 1.0)
        assert score <= 100

    def test_clamped_below_0(self) -> None:
        score = calculate_breadth_score(-0.5, -0.5, -0.5, -0.5, -0.5, -0.5)
        assert score >= 0

    def test_deterministic(self) -> None:
        score1 = calculate_breadth_score(0.6, 0.5, 0.4, 0.3, 0.2, 0.1)
        score2 = calculate_breadth_score(0.6, 0.5, 0.4, 0.3, 0.2, 0.1)
        assert score1 == score2


class TestCalculateBreadth:
    """Tests for the main calculate_breadth function."""

    def test_missing_universe_returns_invalid(self) -> None:
        result = calculate_breadth({}, [100.0] * 55)
        assert result.status == OutputStatus.INVALID
        assert result.market_health == RiskState.UNKNOWN
        assert result.breadth_score == 0
        assert "DATA_MISSING" in result.reason_codes
        assert "INSUFFICIENT_UNIVERSE" in result.reason_codes
        assert result.data_quality.missing is True
        assert result.data_quality.insufficient_universe is True

    def test_missing_btc_returns_invalid(self) -> None:
        candles = {f"SYM{i}": [100.0] * 55 for i in range(25)}
        result = calculate_breadth(candles, [])
        assert result.status == OutputStatus.INVALID
        assert result.market_health == RiskState.UNKNOWN
        assert result.breadth_score == 0
        assert "DATA_MISSING" in result.reason_codes
        assert result.data_quality.missing is True

    def test_insufficient_universe_returns_invalid(self) -> None:
        candles = {f"SYM{i}": [100.0] * 55 for i in range(5)}
        result = calculate_breadth(candles, [100.0] * 55)
        assert result.status == OutputStatus.INVALID
        assert result.market_health == RiskState.UNKNOWN
        assert result.breadth_score == 0
        assert "INSUFFICIENT_UNIVERSE" in result.reason_codes
        assert result.data_quality.insufficient_universe is True

    def test_invalid_btc_values_returns_invalid(self) -> None:
        candles = {f"SYM{i}": [100.0] * 55 for i in range(25)}
        result = calculate_breadth(candles, [100.0] * 54 + [0.0])
        assert result.status == OutputStatus.INVALID
        assert result.market_health == RiskState.UNKNOWN
        assert result.breadth_score == 0
        assert "DATA_INVALID" in result.reason_codes
        assert result.data_quality.missing is False

    def test_valid_breadth_calculation(self) -> None:
        # Create a universe with rising prices (bullish breadth)
        candles = {}
        for i in range(25):
            # Each symbol has rising prices
            candles[f"SYM{i}"] = list(range(100 + i, 100 + i + 55))

        btc = list(range(100, 155))
        result = calculate_breadth(candles, btc)

        assert result.status == OutputStatus.VALID
        assert result.universe_size == 25
        assert result.valid_symbol_count == 25
        assert result.invalid_symbol_count == 0
        assert result.breadth_score > 50  # Rising prices should score well
        assert 0.0 <= result.above_ema20_pct <= 1.0
        assert 0.0 <= result.above_ema50_pct <= 1.0
        assert 0.0 <= result.ema20_rising_pct <= 1.0
        assert 0.0 <= result.advancing_pct <= 1.0
        assert 0.0 <= result.outperforming_btc_7d_pct <= 1.0
        assert result.reason_codes
        assert result.data_quality.is_valid() is True

    def test_breadth_score_range(self) -> None:
        candles = {f"SYM{i}": [100.0] * 55 for i in range(25)}
        btc = [100.0] * 55
        result = calculate_breadth(candles, btc)
        assert 0 <= result.breadth_score <= 100

    def test_reason_codes_included(self) -> None:
        candles = {}
        for i in range(25):
            candles[f"SYM{i}"] = list(range(100 + i, 100 + i + 55))

        btc = list(range(100, 155))
        result = calculate_breadth(candles, btc)
        assert len(result.reason_codes) > 0
        assert all(isinstance(r, str) for r in result.reason_codes)

    def test_risk_on_market(self) -> None:
        # Strong rising market
        candles = {}
        for i in range(25):
            candles[f"SYM{i}"] = list(range(100, 155))

        btc = list(range(100, 155))
        result = calculate_breadth(candles, btc)
        assert result.market_health == RiskState.RISK_ON

    def test_risk_off_market(self) -> None:
        # Strong falling market
        candles = {}
        for i in range(25):
            candles[f"SYM{i}"] = list(range(155, 100, -1))

        btc = list(range(155, 100, -1))
        result = calculate_breadth(candles, btc)
        assert result.market_health == RiskState.RISK_OFF

    def test_invalid_symbols_counted(self) -> None:
        candles = {
            "SYM1": [100.0] * 55,
            "SYM2": [100.0] * 54 + [0.0],  # invalid
            "SYM3": [],  # missing
        }
        # Add more valid symbols to meet minimum
        for i in range(25):
            candles[f"SYM{i+4}"] = [100.0] * 55

        btc = [100.0] * 55
        result = calculate_breadth(candles, btc)
        assert result.status == OutputStatus.VALID
        assert result.invalid_symbol_count >= 2
        assert result.universe_size == len(candles)

    def test_no_network_calls(self) -> None:
        """Verify no network imports exist in breadth module."""
        import inspect
        import hunter.market_state.breadth as breadth_module

        source = inspect.getsource(breadth_module)
        assert "requests" not in source
        assert "urllib" not in source
        assert "http" not in source
        assert "socket" not in source

    def test_no_trading_logic(self) -> None:
        """Verify no trading execution logic exists in breadth module."""
        import inspect
        import hunter.market_state.breadth as breadth_module

        source = inspect.getsource(breadth_module)
        # Trading terms to check for execution logic (not config field names)
        trading_terms = ["order", "position", "trade", "buy", "sell"]
        for term in trading_terms:
            assert term not in source.lower(), f"Found trading term: {term}"
        # Verify no trading function names exist
        assert "execute_trade" not in source.lower()
        assert "place_order" not in source.lower()
        assert "entry_price" not in source.lower()
        assert "stop_loss" not in source.lower()
        assert "take_profit" not in source.lower()
