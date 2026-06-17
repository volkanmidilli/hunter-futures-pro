"""Pure indicator utility functions for market state analysis.

All functions are deterministic, stateless, and use only the Python standard library.
No network calls, no storage access, no trading logic.
"""

from __future__ import annotations

from typing import List, Sequence


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Return numerator / denominator, or default if denominator is zero."""
    if denominator == 0:
        return default
    return numerator / denominator


def percent_change(current: float, previous: float, default: float = 0.0) -> float:
    """Return percentage change from previous to current.

    Formula: ((current - previous) / previous) * 100
    Returns default if previous is zero.
    """
    return safe_divide((current - previous) * 100, previous, default)


def simple_moving_average(values: Sequence[float], period: int) -> List[float]:
    """Calculate simple moving average over a sliding window.

    Args:
        values: Sequence of numeric values (e.g., closing prices).
        period: Window size. Must be >= 1.

    Returns:
        List of SMA values. Length = len(values) - period + 1.
        Returns empty list if len(values) < period.

    Raises:
        ValueError: If period < 1.
    """
    if period < 1:
        raise ValueError(f"period must be >= 1, got {period}")
    if len(values) < period:
        return []
    result: List[float] = []
    for i in range(period - 1, len(values)):
        window = values[i - period + 1 : i + 1]
        result.append(sum(window) / period)
    return result


def exponential_moving_average(values: Sequence[float], period: int) -> List[float]:
    """Calculate exponential moving average.

    Uses the standard EMA formula:
    - First EMA = SMA of first `period` values
    - multiplier = 2 / (period + 1)
    - EMA_today = (value_today * multiplier) + (EMA_yesterday * (1 - multiplier))

    Args:
        values: Sequence of numeric values.
        period: EMA period. Must be >= 1.

    Returns:
        List of EMA values. Length = len(values) - period + 1.
        Returns empty list if len(values) < period.

    Raises:
        ValueError: If period < 1.
    """
    if period < 1:
        raise ValueError(f"period must be >= 1, got {period}")
    if len(values) < period:
        return []
    multiplier = 2 / (period + 1)
    # First EMA is SMA of first `period` values
    ema = sum(values[:period]) / period
    result: List[float] = [ema]
    for value in values[period:]:
        ema = (value * multiplier) + (ema * (1 - multiplier))
        result.append(ema)
    return result


def ema_slope_pct(ema_values: Sequence[float], lookback: int) -> float:
    """Calculate EMA slope percentage over a lookback period.

    Formula from SPEC-003:
        ((ema_current - ema_n_candles_ago) / ema_n_candles_ago) * 100

    Args:
        ema_values: Sequence of EMA values (oldest first).
        lookback: Number of candles back to compare. Must be >= 1.

    Returns:
        Slope percentage. Returns 0.0 if ema_n_candles_ago is zero.

    Raises:
        ValueError: If lookback < 1 or len(ema_values) < lookback + 1.
    """
    if lookback < 1:
        raise ValueError(f"lookback must be >= 1, got {lookback}")
    if len(ema_values) < lookback + 1:
        raise ValueError(
            f"ema_values must have at least {lookback + 1} elements, got {len(ema_values)}"
        )
    ema_current = ema_values[-1]
    ema_n_candles_ago = ema_values[-(lookback + 1)]
    return safe_divide(
        (ema_current - ema_n_candles_ago) * 100, ema_n_candles_ago, default=0.0
    )


def is_rising(slope_pct: float, threshold_pct: float) -> bool:
    """Return True if slope_pct > threshold_pct."""
    return slope_pct > threshold_pct


def is_falling(slope_pct: float, threshold_pct: float) -> bool:
    """Return True if slope_pct < -threshold_pct."""
    return slope_pct < -threshold_pct


def is_flat(slope_pct: float, threshold_pct: float) -> bool:
    """Return True if abs(slope_pct) <= threshold_pct."""
    return abs(slope_pct) <= threshold_pct
