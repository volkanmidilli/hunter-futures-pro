"""Regime Engine for market state classification.

Deterministic regime detection using EMA-based trend analysis.
No ML, no optimization, no curve fitting.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Sequence

from hunter.market_state.indicators import (
    ema_slope_pct,
    exponential_moving_average,
    is_falling,
    is_rising,
)
from hunter.market_state.models import (
    AllowedMode,
    DataQuality,
    OutputStatus,
    RegimeOutput,
    RegimeState,
    RiskState,
)


@dataclass(frozen=True)
class RegimeConfig:
    """Configuration for the Regime Engine.

    Defaults match SPEC-003 recommendations.
    """

    ema_fast_period: int = 20
    ema_slow_period: int = 50
    ema_long_period: int = 200
    slope_lookback: int = 5
    slope_threshold_pct: float = 0.5
    stale_threshold_candles: int = 2
    max_breadth_age_minutes: int = 120
    min_history_candles: int = 200
    bull_score_threshold: int = 70
    bear_score_threshold: int = 70
    transition_score_threshold: int = 50


def _validate_candles(candles: Sequence[float], min_count: int) -> tuple[bool, List[str]]:
    """Validate candle sequence and return (is_valid, reason_codes)."""
    reasons: List[str] = []
    if not candles:
        reasons.append("DATA_MISSING")
        return False, reasons
    if len(candles) < min_count:
        reasons.append("INSUFFICIENT_HISTORY")
        return False, reasons
    if any(c <= 0 for c in candles):
        reasons.append("DATA_INVALID")
        return False, reasons
    return True, reasons


def calculate_btc_trend_score(
    btc_closes: Sequence[float],
    config: RegimeConfig,
) -> tuple[int, List[str]]:
    """Calculate BTC trend score from 0 to 100.

    Returns (score, reason_codes).
    Score = bullish_conditions_met / total_conditions * 100.
    """
    valid, reasons = _validate_candles(btc_closes, config.ema_slow_period + config.slope_lookback)
    if not valid:
        return 0, reasons

    ema_fast = exponential_moving_average(btc_closes, config.ema_fast_period)
    ema_slow = exponential_moving_average(btc_closes, config.ema_slow_period)

    if not ema_fast or not ema_slow:
        return 0, ["CALCULATION_ERROR"]

    current_close = btc_closes[-1]
    current_ema_fast = ema_fast[-1]
    current_ema_slow = ema_slow[-1]

    fast_slope = ema_slope_pct(ema_fast, config.slope_lookback)
    slow_slope = ema_slope_pct(ema_slow, config.slope_lookback)

    bullish = 0
    total = 5

    if current_close > current_ema_fast:
        bullish += 1
    if current_close > current_ema_slow:
        bullish += 1
    if is_rising(fast_slope, config.slope_threshold_pct):
        bullish += 1
    if is_rising(slow_slope, config.slope_threshold_pct):
        bullish += 1
    # Recent return direction (last candle vs previous)
    if len(btc_closes) >= 2 and btc_closes[-1] > btc_closes[-2]:
        bullish += 1

    score = int((bullish / total) * 100)
    return score, []


def calculate_bearish_btc_trend_score(
    btc_closes: Sequence[float],
    config: RegimeConfig,
) -> tuple[int, List[str]]:
    """Calculate bearish BTC trend score from 0 to 100.

    Returns (score, reason_codes).
    Score = bearish_conditions_met / total_conditions * 100.
    """
    valid, reasons = _validate_candles(btc_closes, config.ema_slow_period + config.slope_lookback)
    if not valid:
        return 0, reasons

    ema_fast = exponential_moving_average(btc_closes, config.ema_fast_period)
    ema_slow = exponential_moving_average(btc_closes, config.ema_slow_period)

    if not ema_fast or not ema_slow:
        return 0, ["CALCULATION_ERROR"]

    current_close = btc_closes[-1]
    current_ema_fast = ema_fast[-1]
    current_ema_slow = ema_slow[-1]

    fast_slope = ema_slope_pct(ema_fast, config.slope_lookback)
    slow_slope = ema_slope_pct(ema_slow, config.slope_lookback)

    bearish = 0
    total = 5

    if current_close < current_ema_fast:
        bearish += 1
    if current_close < current_ema_slow:
        bearish += 1
    if is_falling(fast_slope, config.slope_threshold_pct):
        bearish += 1
    if is_falling(slow_slope, config.slope_threshold_pct):
        bearish += 1
    if len(btc_closes) >= 2 and btc_closes[-1] < btc_closes[-2]:
        bearish += 1

    score = int((bearish / total) * 100)
    return score, []


def calculate_eth_trend_score(
    eth_closes: Sequence[float] | None,
    config: RegimeConfig,
) -> tuple[int, List[str]]:
    """Calculate ETH trend score from 0 to 100.

    Returns (score, reason_codes).
    If ETH data is missing, returns (0, ["ETH_DATA_UNAVAILABLE"]).
    """
    if eth_closes is None:
        return 0, ["ETH_DATA_UNAVAILABLE"]

    valid, reasons = _validate_candles(eth_closes, config.ema_fast_period + config.slope_lookback)
    if not valid:
        return 0, reasons

    ema_fast = exponential_moving_average(eth_closes, config.ema_fast_period)
    if not ema_fast:
        return 0, ["CALCULATION_ERROR"]

    current_close = eth_closes[-1]
    current_ema_fast = ema_fast[-1]
    fast_slope = ema_slope_pct(ema_fast, config.slope_lookback)

    bullish = 0
    total = 3

    if current_close > current_ema_fast:
        bullish += 1
    if is_rising(fast_slope, config.slope_threshold_pct):
        bullish += 1
    if len(eth_closes) >= 2 and eth_closes[-1] > eth_closes[-2]:
        bullish += 1

    score = int((bullish / total) * 100)
    return score, []


def calculate_breadth_confirmation_score(
    breadth_score: int | None,
    above_ema20_pct: float | None,
    advancing_pct: float | None,
    regime_direction: str,  # "bull" or "bear"
    config: RegimeConfig,
) -> tuple[int, List[str]]:
    """Calculate breadth confirmation score from 0 to 100.

    Returns (score, reason_codes).
    If breadth data is missing or incomplete, returns (0, [])."""
    if breadth_score is None or above_ema20_pct is None or advancing_pct is None:
        return 0, []

    confirming = 0
    total = 3
    reasons: List[str] = []

    if regime_direction == "bull":
        if breadth_score > config.bull_score_threshold:
            confirming += 1
            reasons.append("BREADTH_CONFIRMS_RISK_ON")
        if above_ema20_pct > 0.5:
            confirming += 1
            reasons.append("MAJORITY_ABOVE_EMA20")
        if advancing_pct > 0.5:
            confirming += 1
            reasons.append("ADVANCING_MAJORITY")
    else:  # bear
        if breadth_score < config.bear_score_threshold:
            confirming += 1
            reasons.append("BREADTH_CONFIRMS_RISK_OFF")
        if above_ema20_pct < 0.5:
            confirming += 1
            reasons.append("MAJORITY_BELOW_EMA20")
        if advancing_pct < 0.5:
            confirming += 1
            reasons.append("DECLINING_MAJORITY")

    score = int((confirming / total) * 100)
    return score, reasons


def classify_regime(
    btc_closes: Sequence[float],
    eth_closes: Sequence[float] | None = None,
    breadth_score: int | None = None,
    breadth_above_ema20_pct: float | None = None,
    breadth_advancing_pct: float | None = None,
    config: RegimeConfig | None = None,
    timestamp: datetime | None = None,
) -> RegimeOutput:
    """Classify market regime from BTC candles and optional confirmation data.

    Args:
        btc_closes: Sequence of BTC closing prices (oldest first).
        eth_closes: Optional sequence of ETH closing prices.
        breadth_score: Optional breadth score (0-100) for confirmation.
        breadth_above_ema20_pct: Optional percentage above EMA20.
        breadth_advancing_pct: Optional advancing percentage.
        config: RegimeConfig instance. Uses defaults if None.
        timestamp: Output timestamp. Uses UTC now if None.

    Returns:
        RegimeOutput with deterministic classification.
    """
    config = config or RegimeConfig()
    now = timestamp or datetime.now(timezone.utc)

    # Validate BTC data (required)
    btc_valid, btc_reasons = _validate_candles(btc_closes, config.min_history_candles)
    if not btc_valid:
        return RegimeOutput.unknown(
            timestamp=now,
            reason_codes=btc_reasons,
            data_quality=DataQuality(
                missing="DATA_MISSING" in btc_reasons,
                stale=False,
                insufficient_history="INSUFFICIENT_HISTORY" in btc_reasons,
            ),
        )

    # Calculate BTC trend scores
    btc_bull_score, btc_bull_reasons = calculate_btc_trend_score(btc_closes, config)
    btc_bear_score, btc_bear_reasons = calculate_bearish_btc_trend_score(btc_closes, config)

    if btc_bull_reasons and btc_bull_reasons[0] in ("DATA_MISSING", "INSUFFICIENT_HISTORY", "DATA_INVALID"):
        return RegimeOutput.unknown(
            timestamp=now,
            reason_codes=btc_bull_reasons,
            data_quality=DataQuality(
                missing="DATA_MISSING" in btc_bull_reasons,
                stale=False,
                insufficient_history="INSUFFICIENT_HISTORY" in btc_bull_reasons,
            ),
        )

    # Calculate ETH confirmation (optional)
    eth_score, eth_reasons = calculate_eth_trend_score(eth_closes, config)

    # Determine primary direction and score
    if btc_bull_score >= btc_bear_score:
        primary_score = btc_bull_score
        primary_direction = "bull"
        bearish_score = btc_bear_score
    else:
        primary_score = btc_bear_score
        primary_direction = "bear"
        bearish_score = btc_bull_score

    # Calculate breadth confirmation (optional)
    breadth_conf_score, breadth_reasons = calculate_breadth_confirmation_score(
        breadth_score,
        breadth_above_ema20_pct,
        breadth_advancing_pct,
        primary_direction,
        config,
    )

    # Determine confirmation score and source
    confirmation_score = 0
    confirmation_reasons: List[str] = []

    if eth_closes is not None and eth_score > 0:
        confirmation_score = eth_score
        confirmation_reasons.extend(eth_reasons)
    elif breadth_conf_score > 0:
        confirmation_score = breadth_conf_score
        confirmation_reasons.extend(breadth_reasons)

    # Calculate confidence
    if confirmation_score > 0:
        confidence = min(primary_score, confirmation_score) / 100.0
    else:
        confidence = primary_score / 100.0

    # Classify regime
    reason_codes: List[str] = []
    regime: RegimeState
    allowed_mode: AllowedMode
    risk_state: RiskState

    if primary_direction == "bull":
        if primary_score >= config.bull_score_threshold:
            regime = RegimeState.BULL
            allowed_mode = AllowedMode.LONG_ONLY
            risk_state = RiskState.RISK_ON
            reason_codes.append("BTC_CLOSE_ABOVE_EMA20")
            reason_codes.append("BTC_CLOSE_ABOVE_EMA50")
            if btc_bull_score >= 60:
                reason_codes.append("BTC_EMA20_RISING")
        elif bearish_score >= config.bear_score_threshold:
            # Mixed signals — transition
            regime = RegimeState.TRANSITION
            allowed_mode = AllowedMode.NONE
            risk_state = RiskState.NEUTRAL
            reason_codes.append("MIXED_SIGNALS")
        else:
            regime = RegimeState.SIDEWAYS
            allowed_mode = AllowedMode.NONE
            risk_state = RiskState.NEUTRAL
            reason_codes.append("WEAK_TREND")
    else:  # bear primary
        if primary_score >= config.bear_score_threshold:
            regime = RegimeState.BEAR
            allowed_mode = AllowedMode.SHORT_ONLY
            risk_state = RiskState.RISK_OFF
            reason_codes.append("BTC_CLOSE_BELOW_EMA20")
            reason_codes.append("BTC_CLOSE_BELOW_EMA50")
            if btc_bear_score >= 60:
                reason_codes.append("BTC_EMA20_FALLING")
        elif bearish_score >= config.bull_score_threshold:
            # Mixed signals — transition
            regime = RegimeState.TRANSITION
            allowed_mode = AllowedMode.NONE
            risk_state = RiskState.NEUTRAL
            reason_codes.append("MIXED_SIGNALS")
        else:
            regime = RegimeState.SIDEWAYS
            allowed_mode = AllowedMode.NONE
            risk_state = RiskState.NEUTRAL
            reason_codes.append("WEAK_TREND")

    # Add confirmation reasons
    reason_codes.extend(confirmation_reasons)

    # Transition check: if confidence is medium but not high
    if regime in (RegimeState.BULL, RegimeState.BEAR) and confidence < 0.6:
        regime = RegimeState.TRANSITION
        allowed_mode = AllowedMode.NONE
        risk_state = RiskState.NEUTRAL
        reason_codes.append("LOW_CONFIDENCE_TRANSITION")

    return RegimeOutput(
        timestamp=now,
        status=OutputStatus.VALID,
        market_regime=regime,
        allowed_mode=allowed_mode,
        confidence=round(confidence, 4),
        risk_state=risk_state,
        btc_trend_score=primary_score if primary_direction == "bull" else bearish_score,
        eth_trend_score=eth_score,
        breadth_confirmation_score=breadth_conf_score,
        reason_codes=reason_codes,
        data_quality=DataQuality(),
    )
