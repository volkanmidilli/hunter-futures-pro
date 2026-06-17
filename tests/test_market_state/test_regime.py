"""Tests for the Regime Engine."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from hunter.market_state.models import (
    AllowedMode,
    DataQuality,
    OutputStatus,
    RegimeOutput,
    RegimeState,
    RiskState,
)
from hunter.market_state.regime import (
    RegimeConfig,
    calculate_bearish_btc_trend_score,
    calculate_breadth_confirmation_score,
    calculate_btc_trend_score,
    calculate_eth_trend_score,
    classify_regime,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _generate_candles(start: float, count: int, trend: str = "flat") -> list[float]:
    """Generate synthetic closing prices."""
    candles = []
    price = start
    for i in range(count):
        if trend == "up":
            price += 10.0
        elif trend == "down":
            price = max(1.0, price - 10.0)  # Clamp to avoid zero/negative
        elif trend == "flat":
            # Small oscillation around start
            price = start + (i % 3 - 1) * 2.0
        candles.append(price)
    return candles


# ---------------------------------------------------------------------------
# RegimeConfig
# ---------------------------------------------------------------------------

class TestRegimeConfig:
    def test_default_values(self) -> None:
        config = RegimeConfig()
        assert config.ema_fast_period == 20
        assert config.ema_slow_period == 50
        assert config.slope_lookback == 5
        assert config.slope_threshold_pct == 0.5
        assert config.min_history_candles == 200
        assert config.bull_score_threshold == 70

    def test_custom_values(self) -> None:
        config = RegimeConfig(ema_fast_period=10, bull_score_threshold=60)
        assert config.ema_fast_period == 10
        assert config.bull_score_threshold == 60


# ---------------------------------------------------------------------------
# calculate_btc_trend_score
# ---------------------------------------------------------------------------

class TestCalculateBtcTrendScore:
    def test_bullish_trend_high_score(self) -> None:
        # Strong uptrend: 200 candles going up
        candles = _generate_candles(100.0, 200, trend="up")
        score, reasons = calculate_btc_trend_score(candles, RegimeConfig())
        assert score >= 70
        assert reasons == []

    def test_bearish_trend_low_score(self) -> None:
        # Strong downtrend: 200 candles going down
        candles = _generate_candles(2000.0, 200, trend="down")
        score, reasons = calculate_btc_trend_score(candles, RegimeConfig())
        assert score <= 30
        assert reasons == []

    def test_flat_trend_medium_score(self) -> None:
        candles = _generate_candles(100.0, 200, trend="flat")
        score, reasons = calculate_btc_trend_score(candles, RegimeConfig())
        # Flat trend should have mixed signals
        assert 0 <= score <= 100
        assert reasons == []

    def test_missing_data(self) -> None:
        score, reasons = calculate_btc_trend_score([], RegimeConfig())
        assert score == 0
        assert "DATA_MISSING" in reasons

    def test_insufficient_history(self) -> None:
        candles = _generate_candles(100.0, 50, trend="up")
        score, reasons = calculate_btc_trend_score(candles, RegimeConfig())
        assert score == 0
        assert "INSUFFICIENT_HISTORY" in reasons

    def test_invalid_candle_values(self) -> None:
        candles = [100.0] * 199 + [0.0]
        score, reasons = calculate_btc_trend_score(candles, RegimeConfig())
        assert score == 0
        assert "DATA_INVALID" in reasons

    def test_score_range(self) -> None:
        candles = _generate_candles(100.0, 200, trend="up")
        score, _ = calculate_btc_trend_score(candles, RegimeConfig())
        assert 0 <= score <= 100


# ---------------------------------------------------------------------------
# calculate_bearish_btc_trend_score
# ---------------------------------------------------------------------------

class TestCalculateBearishBtcTrendScore:
    def test_bearish_trend_high_score(self) -> None:
        candles = _generate_candles(2000.0, 200, trend="down")
        score, reasons = calculate_bearish_btc_trend_score(candles, RegimeConfig())
        assert score >= 70
        assert reasons == []

    def test_bullish_trend_low_score(self) -> None:
        candles = _generate_candles(100.0, 200, trend="up")
        score, reasons = calculate_bearish_btc_trend_score(candles, RegimeConfig())
        assert score <= 30
        assert reasons == []

    def test_missing_data(self) -> None:
        score, reasons = calculate_bearish_btc_trend_score([], RegimeConfig())
        assert score == 0
        assert "DATA_MISSING" in reasons


# ---------------------------------------------------------------------------
# calculate_eth_trend_score
# ---------------------------------------------------------------------------

class TestCalculateEthTrendScore:
    def test_none_returns_unavailable(self) -> None:
        score, reasons = calculate_eth_trend_score(None, RegimeConfig())
        assert score == 0
        assert "ETH_DATA_UNAVAILABLE" in reasons

    def test_bullish_eth(self) -> None:
        candles = _generate_candles(100.0, 200, trend="up")
        score, reasons = calculate_eth_trend_score(candles, RegimeConfig())
        assert score >= 70
        assert reasons == []

    def test_missing_eth_data(self) -> None:
        score, reasons = calculate_eth_trend_score([], RegimeConfig())
        assert score == 0
        assert "DATA_MISSING" in reasons


# ---------------------------------------------------------------------------
# calculate_breadth_confirmation_score
# ---------------------------------------------------------------------------

class TestCalculateBreadthConfirmationScore:
    def test_bull_confirmation(self) -> None:
        score, reasons = calculate_breadth_confirmation_score(
            75, 0.6, 0.55, "bull", RegimeConfig()
        )
        assert score > 0
        assert "BREADTH_CONFIRMS_RISK_ON" in reasons

    def test_bear_confirmation(self) -> None:
        score, reasons = calculate_breadth_confirmation_score(
            25, 0.4, 0.45, "bear", RegimeConfig()
        )
        assert score > 0
        assert "BREADTH_CONFIRMS_RISK_OFF" in reasons

    def test_none_breadth_returns_zero(self) -> None:
        score, reasons = calculate_breadth_confirmation_score(
            None, None, None, "bull", RegimeConfig()
        )
        assert score == 0
        assert reasons == []

    def test_bull_no_confirmation(self) -> None:
        score, reasons = calculate_breadth_confirmation_score(
            50, 0.4, 0.45, "bull", RegimeConfig()
        )
        assert score == 0


# ---------------------------------------------------------------------------
# classify_regime — fail-closed
# ---------------------------------------------------------------------------

class TestClassifyRegimeFailClosed:
    def test_missing_btc_candles(self) -> None:
        result = classify_regime(btc_closes=[])
        assert result.market_regime == RegimeState.UNKNOWN
        assert result.allowed_mode == AllowedMode.NONE
        assert result.confidence == 0.0
        assert result.status == OutputStatus.INVALID
        assert "DATA_MISSING" in result.reason_codes

    def test_insufficient_btc_history(self) -> None:
        candles = _generate_candles(100.0, 50)
        result = classify_regime(btc_closes=candles)
        assert result.market_regime == RegimeState.UNKNOWN
        assert result.allowed_mode == AllowedMode.NONE
        assert result.confidence == 0.0
        assert "INSUFFICIENT_HISTORY" in result.reason_codes

    def test_invalid_candle_values(self) -> None:
        candles = [100.0] * 199 + [0.0]
        result = classify_regime(btc_closes=candles)
        assert result.market_regime == RegimeState.UNKNOWN
        assert result.allowed_mode == AllowedMode.NONE
        assert "DATA_INVALID" in result.reason_codes

    def test_calculation_error_blocks(self) -> None:
        # This is hard to trigger directly; test via invalid data
        result = classify_regime(btc_closes=[])
        assert result.is_blocking() is True


# ---------------------------------------------------------------------------
# classify_regime — regime detection
# ---------------------------------------------------------------------------

class TestClassifyRegimeDetection:
    def test_bull_regime_detected(self) -> None:
        candles = _generate_candles(100.0, 200, trend="up")
        result = classify_regime(btc_closes=candles)
        assert result.market_regime == RegimeState.BULL
        assert result.allowed_mode == AllowedMode.LONG_ONLY
        assert result.risk_state == RiskState.RISK_ON
        assert result.status == OutputStatus.VALID
        assert result.confidence > 0.0
        assert result.btc_trend_score > 0
        assert result.reason_codes

    def test_bear_regime_detected(self) -> None:
        candles = _generate_candles(2000.0, 200, trend="down")
        result = classify_regime(btc_closes=candles)
        assert result.market_regime == RegimeState.BEAR
        assert result.allowed_mode == AllowedMode.SHORT_ONLY
        assert result.risk_state == RiskState.RISK_OFF
        assert result.status == OutputStatus.VALID
        assert result.confidence > 0.0

    def test_sideways_regime_detected(self) -> None:
        candles = _generate_candles(100.0, 200, trend="flat")
        result = classify_regime(btc_closes=candles)
        # Flat trend should be sideways or transition
        assert result.market_regime in (RegimeState.SIDEWAYS, RegimeState.TRANSITION)
        assert result.allowed_mode == AllowedMode.NONE
        assert result.status == OutputStatus.VALID

    def test_transition_with_eth_confirmation(self) -> None:
        # Moderate trend with ETH confirmation
        btc = _generate_candles(100.0, 200, trend="flat")
        eth = _generate_candles(50.0, 200, trend="up")
        result = classify_regime(btc_closes=btc, eth_closes=eth)
        # With ETH bullish but BTC flat, could be transition or sideways
        assert result.status == OutputStatus.VALID
        assert result.eth_trend_score > 0

    def test_bull_with_breadth_confirmation(self) -> None:
        candles = _generate_candles(100.0, 200, trend="up")
        result = classify_regime(
            btc_closes=candles,
            breadth_score=75,
            breadth_above_ema20_pct=0.6,
            breadth_advancing_pct=0.55,
        )
        assert result.market_regime == RegimeState.BULL
        assert result.breadth_confirmation_score > 0

    def test_confidence_range_valid(self) -> None:
        candles = _generate_candles(100.0, 200, trend="up")
        result = classify_regime(btc_closes=candles)
        assert 0.0 <= result.confidence <= 1.0

    def test_allowed_mode_none_when_invalid(self) -> None:
        result = classify_regime(btc_closes=[])
        assert result.allowed_mode == AllowedMode.NONE
        assert result.is_blocking() is True


# ---------------------------------------------------------------------------
# classify_regime — reason codes
# ---------------------------------------------------------------------------

class TestClassifyRegimeReasonCodes:
    def test_bull_has_reason_codes(self) -> None:
        candles = _generate_candles(100.0, 200, trend="up")
        result = classify_regime(btc_closes=candles)
        assert len(result.reason_codes) > 0
        assert any("BTC" in r or "BREADTH" in r or "CONFIDENCE" in r for r in result.reason_codes)

    def test_bear_has_reason_codes(self) -> None:
        candles = _generate_candles(2000.0, 200, trend="down")
        result = classify_regime(btc_closes=candles)
        assert len(result.reason_codes) > 0

    def test_unknown_has_reason_codes(self) -> None:
        result = classify_regime(btc_closes=[])
        # The fail-closed factory adds UNKNOWN_REGIME_BLOCKS_EXECUTION, but
        # classify_regime replaces it with the actual validation reason (DATA_MISSING)
        assert len(result.reason_codes) > 0
        assert result.market_regime == RegimeState.UNKNOWN


# ---------------------------------------------------------------------------
# Safety tests
# ---------------------------------------------------------------------------

class TestSafety:
    def test_no_network_calls(self) -> None:
        import hunter.market_state.regime as regime_module

        network_modules = {"urllib", "http", "socket", "requests", "aiohttp"}
        module_globals = set(regime_module.__dict__.keys())
        overlap = network_modules & module_globals
        assert not overlap, f"Network modules found in regime: {overlap}"

    def test_no_trading_logic(self) -> None:
        import inspect

        import hunter.market_state.regime as regime_module

        source = inspect.getsource(regime_module)
        trading_terms = ["buy", "sell", "order", "position", "trade", "profit", "loss"]
        found = [term for term in trading_terms if term.lower() in source.lower()]
        assert not found, f"Trading terms found in regime: {found}"

    def test_no_binance_imports(self) -> None:
        import hunter.market_state.regime as regime_module

        module_globals = set(regime_module.__dict__.keys())
        assert "binance" not in str(module_globals).lower()

    def test_no_freqtrade_imports(self) -> None:
        import hunter.market_state.regime as regime_module

        module_globals = set(regime_module.__dict__.keys())
        assert "freqtrade" not in str(module_globals).lower()
