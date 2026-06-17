"""Market Breadth Engine for measuring crypto market strength.

Deterministic breadth analysis using EMA-based metrics across a universe of symbols.
No ML, no optimization, no curve fitting.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Sequence, Tuple

from hunter.market_state.indicators import (
    ema_slope_pct,
    exponential_moving_average,
    is_rising,
    percent_change,
)
from hunter.market_state.models import (
    BreadthOutput,
    DataQuality,
    OutputStatus,
    RiskState,
)


@dataclass(frozen=True)
class BreadthConfig:
    """Configuration for the Market Breadth Engine.

    Defaults match SPEC-003 recommendations.
    """

    min_universe_size: int = 20
    ema_fast_period: int = 20
    ema_slow_period: int = 50
    ema_long_period: int = 200
    recent_return_days: int = 7
    outperform_btc_short_days: int = 7
    outperform_btc_long_days: int = 30
    stale_threshold_candles: int = 2
    risk_on_threshold: int = 65
    risk_off_threshold: int = 35
    min_quote_volume: float = 1_000_000.0
    slope_lookback: int = 5
    slope_threshold_pct: float = 0.5


def _validate_candles(candles: Sequence[float], min_count: int) -> Tuple[bool, List[str]]:
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


def filter_valid_symbols(
    universe_candles: Dict[str, Sequence[float]],
    config: BreadthConfig,
) -> Tuple[Dict[str, Sequence[float]], int, List[str]]:
    """Filter universe symbols based on validity rules.

    Returns (valid_symbols, invalid_count, reason_codes).

    Validity rules per SPEC-003:
    - Exclude symbols with missing candles
    - Exclude symbols with insufficient history
    - Exclude symbols with close price <= 0
    - Exclude symbols with volume < 0 (not applicable here, checked via validation)
    - Exclude symbols that fail calculation
    """
    valid: Dict[str, Sequence[float]] = {}
    invalid_count = 0
    reasons: List[str] = []
    min_candles = config.ema_slow_period + config.slope_lookback

    for symbol, closes in universe_candles.items():
        is_valid, symbol_reasons = _validate_candles(closes, min_candles)
        if is_valid:
            valid[symbol] = closes
        else:
            invalid_count += 1
            reasons.extend(symbol_reasons)

    return valid, invalid_count, list(set(reasons))


def calculate_percent_above_ema(
    valid_candles: Dict[str, Sequence[float]],
    ema_period: int,
) -> float:
    """Calculate percentage of symbols with close > EMA(period).

    Returns 0.0 if no valid symbols or calculation fails.
    """
    if not valid_candles:
        return 0.0

    above_count = 0
    total_count = 0

    for closes in valid_candles.values():
        ema = exponential_moving_average(closes, ema_period)
        if not ema:
            continue
        total_count += 1
        if closes[-1] > ema[-1]:
            above_count += 1

    if total_count == 0:
        return 0.0
    return above_count / total_count


def calculate_percent_ema_rising(
    valid_candles: Dict[str, Sequence[float]],
    ema_period: int,
    lookback: int,
    threshold_pct: float,
) -> float:
    """Calculate percentage of symbols with EMA(period) rising.

    Returns 0.0 if no valid symbols or calculation fails.
    """
    if not valid_candles:
        return 0.0

    rising_count = 0
    total_count = 0

    for closes in valid_candles.values():
        ema = exponential_moving_average(closes, ema_period)
        if not ema or len(ema) < lookback + 1:
            continue
        total_count += 1
        try:
            slope = ema_slope_pct(ema, lookback)
            if is_rising(slope, threshold_pct):
                rising_count += 1
        except ValueError:
            continue

    if total_count == 0:
        return 0.0
    return rising_count / total_count


def calculate_advancing_declining_pct(
    valid_candles: Dict[str, Sequence[float]],
) -> Tuple[float, float]:
    """Calculate advancing and declining percentages.

    Advancing: close[-1] > close[-2]
    Declining: close[-1] < close[-2]
    Flat symbols are excluded from both counts.

    Returns (advancing_pct, declining_pct).
    """
    if not valid_candles:
        return 0.0, 0.0

    advancing = 0
    declining = 0
    total = 0

    for closes in valid_candles.values():
        if len(closes) < 2:
            continue
        total += 1
        if closes[-1] > closes[-2]:
            advancing += 1
        elif closes[-1] < closes[-2]:
            declining += 1

    if total == 0:
        return 0.0, 0.0

    return advancing / total, declining / total


def calculate_outperforming_btc_pct(
    valid_candles: Dict[str, Sequence[float]],
    btc_closes: Sequence[float],
    lookback_days: int,
) -> float:
    """Calculate percentage of symbols outperforming BTC over lookback.

    Returns 0.0 if no valid symbols or calculation fails.
    """
    if not valid_candles or not btc_closes or len(btc_closes) < 2:
        return 0.0

    # Use minimum of lookback_days and available data
    btc_lookback = min(lookback_days, len(btc_closes) - 1)
    if btc_lookback < 1:
        return 0.0

    btc_return = percent_change(btc_closes[-1], btc_closes[-btc_lookback - 1])

    outperform_count = 0
    total_count = 0

    for closes in valid_candles.values():
        symbol_lookback = min(lookback_days, len(closes) - 1)
        if symbol_lookback < 1:
            continue
        total_count += 1
        symbol_return = percent_change(closes[-1], closes[-symbol_lookback - 1])
        if symbol_return > btc_return:
            outperform_count += 1

    if total_count == 0:
        return 0.0
    return outperform_count / total_count


def calculate_breadth_score(
    above_ema20_pct: float,
    above_ema50_pct: float,
    ema20_rising_pct: float,
    ema50_rising_pct: float,
    advancing_pct: float,
    outperforming_btc_7d_pct: float,
) -> int:
    """Calculate breadth score from 0 to 100.

    Formula from SPEC-003:
        above_ema20_pct       * 25
        + above_ema50_pct     * 20
        + ema20_rising_pct    * 20
        + ema50_rising_pct    * 15
        + advancing_pct       * 10
        + outperforming_btc_7d_pct * 10

    All percentages are 0.0–1.0. Result is clamped to 0–100.
    """
    score = (
        above_ema20_pct * 25
        + above_ema50_pct * 20
        + ema20_rising_pct * 20
        + ema50_rising_pct * 15
        + advancing_pct * 10
        + outperforming_btc_7d_pct * 10
    )
    return max(0, min(100, int(score)))


def calculate_breadth(
    universe_candles: Dict[str, Sequence[float]],
    btc_closes: Sequence[float],
    config: BreadthConfig | None = None,
    timestamp: datetime | None = None,
) -> BreadthOutput:
    """Calculate market breadth from universe candles and BTC reference.

    Args:
        universe_candles: Dict mapping symbol -> closing prices (oldest first).
        btc_closes: Sequence of BTC closing prices (oldest first).
        config: BreadthConfig instance. Uses defaults if None.
        timestamp: Output timestamp. Uses UTC now if None.

    Returns:
        BreadthOutput with deterministic breadth metrics.
        Returns BreadthOutput.invalid() on missing/insufficient/invalid data.
    """
    config = config or BreadthConfig()
    now = timestamp or datetime.now(timezone.utc)

    # Validate required inputs
    if not universe_candles:
        return BreadthOutput.invalid(
            timestamp=now,
            reason_codes=["DATA_MISSING", "INSUFFICIENT_UNIVERSE"],
            data_quality=DataQuality(
                missing=True,
                stale=False,
                insufficient_history=False,
                insufficient_universe=True,
            ),
        )

    # Validate BTC candles (required for outperforming BTC calculation)
    btc_valid, btc_reasons = _validate_candles(btc_closes, 2)
    if not btc_valid:
        return BreadthOutput.invalid(
            timestamp=now,
            reason_codes=btc_reasons,
            data_quality=DataQuality(
                missing="DATA_MISSING" in btc_reasons,
                stale=False,
                insufficient_history="INSUFFICIENT_HISTORY" in btc_reasons,
                insufficient_universe=False,
            ),
        )

    # Filter valid symbols
    valid_candles, invalid_count, filter_reasons = filter_valid_symbols(
        universe_candles, config
    )

    universe_size = len(universe_candles)
    valid_count = len(valid_candles)

    # Check minimum universe size
    if valid_count < config.min_universe_size:
        return BreadthOutput.invalid(
            timestamp=now,
            reason_codes=["INSUFFICIENT_UNIVERSE"],
            data_quality=DataQuality(
                missing=False,
                stale=False,
                insufficient_history=False,
                insufficient_universe=True,
            ),
        )

    # Calculate breadth metrics
    above_ema20_pct = calculate_percent_above_ema(valid_candles, config.ema_fast_period)
    above_ema50_pct = calculate_percent_above_ema(valid_candles, config.ema_slow_period)
    ema20_rising_pct = calculate_percent_ema_rising(
        valid_candles, config.ema_fast_period, config.slope_lookback, config.slope_threshold_pct
    )
    ema50_rising_pct = calculate_percent_ema_rising(
        valid_candles, config.ema_slow_period, config.slope_lookback, config.slope_threshold_pct
    )
    advancing_pct, declining_pct = calculate_advancing_declining_pct(valid_candles)
    outperforming_btc_7d_pct = calculate_outperforming_btc_pct(
        valid_candles, btc_closes, config.outperform_btc_short_days
    )

    # Calculate breadth score
    breadth_score = calculate_breadth_score(
        above_ema20_pct,
        above_ema50_pct,
        ema20_rising_pct,
        ema50_rising_pct,
        advancing_pct,
        outperforming_btc_7d_pct,
    )

    # Determine market health
    if breadth_score >= config.risk_on_threshold:
        market_health = RiskState.RISK_ON
    elif breadth_score <= config.risk_off_threshold:
        market_health = RiskState.RISK_OFF
    else:
        market_health = RiskState.NEUTRAL

    # Build reason codes
    reason_codes: List[str] = []
    if above_ema20_pct > 0.5:
        reason_codes.append("MAJORITY_ABOVE_EMA20")
    else:
        reason_codes.append("MAJORITY_BELOW_EMA20")

    if ema20_rising_pct > 0.5:
        reason_codes.append("EMA20_RISING_BREADTH_POSITIVE")
    else:
        reason_codes.append("EMA20_FALLING_BREADTH_NEGATIVE")

    if advancing_pct > 0.5:
        reason_codes.append("ALT_PARTICIPATION_STRONG")
    elif advancing_pct > 0.3:
        reason_codes.append("ALT_PARTICIPATION_MODERATE")
    else:
        reason_codes.append("ALT_PARTICIPATION_WEAK")

    return BreadthOutput(
        timestamp=now,
        status=OutputStatus.VALID,
        breadth_score=breadth_score,
        market_health=market_health,
        universe_size=universe_size,
        valid_symbol_count=valid_count,
        invalid_symbol_count=invalid_count,
        above_ema20_pct=round(above_ema20_pct, 4),
        above_ema50_pct=round(above_ema50_pct, 4),
        above_ema200_pct=0.0,  # Placeholder for future implementation
        ema20_rising_pct=round(ema20_rising_pct, 4),
        ema50_rising_pct=round(ema50_rising_pct, 4),
        advancing_pct=round(advancing_pct, 4),
        declining_pct=round(declining_pct, 4),
        outperforming_btc_7d_pct=round(outperforming_btc_7d_pct, 4),
        outperforming_btc_30d_pct=0.0,  # Placeholder for future implementation
        reason_codes=reason_codes,
        data_quality=DataQuality(
            missing=False,
            stale=False,
            insufficient_history=False,
            insufficient_universe=False,
        ),
    )
