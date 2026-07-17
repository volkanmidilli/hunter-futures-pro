"""Descriptive statistics for walk-forward metric deltas (MVP-67 / SPEC-068)."""

from __future__ import annotations

import statistics
from decimal import Decimal
from typing import Any


def _median(values: list[Decimal]) -> Decimal:
    """Compute the median of a sorted list of Decimals."""
    n = len(values)
    if n == 0:
        return Decimal("0")
    sorted_vals = sorted(values)
    if n % 2 == 1:
        return sorted_vals[n // 2]
    return (sorted_vals[n // 2 - 1] + sorted_vals[n // 2]) / Decimal("2")


def _quartiles(values: list[Decimal]) -> tuple[Decimal, Decimal]:
    """Compute Q1 and Q3 using the median-of-halves (inclusive) method.

    Returns (q1, q3). If fewer than 2 values, returns (min, max).
    """
    n = len(values)
    if n == 0:
        return Decimal("0"), Decimal("0")
    sorted_vals = sorted(values)
    if n == 1:
        return sorted_vals[0], sorted_vals[0]
    # Split into lower and upper halves (include median in both halves for odd n)
    if n % 2 == 0:
        lower = sorted_vals[: n // 2]
        upper = sorted_vals[n // 2 :]
    else:
        lower = sorted_vals[: n // 2 + 1]
        upper = sorted_vals[n // 2 :]
    q1 = _median(lower)
    q3 = _median(upper)
    return q1, q3


def _mad(values: list[Decimal]) -> Decimal:
    """Compute Median Absolute Deviation from the median."""
    n = len(values)
    if n == 0:
        return Decimal("0")
    med = _median(values)
    abs_devs = [abs(v - med) for v in values]
    return _median(abs_devs)


def _std_dev(values: list[Decimal]) -> Decimal:
    """Compute sample standard deviation (n-1) for n >= 2.

    Returns 0 for n < 2 or if all values are equal.
    """
    n = len(values)
    if n < 2:
        return Decimal("0")
    mean_val = sum(values) / Decimal(str(n))
    variance = sum((v - mean_val) ** 2 for v in values) / Decimal(str(n - 1))
    if variance <= Decimal("0"):
        return Decimal("0")
    return Decimal(str(statistics.sqrt(float(variance))))


def compute_metric_descriptive(deltas: list[Decimal | None]) -> dict[str, Any]:
    """Compute descriptive statistics for a list of metric deltas.

    Args:
        deltas: List of Decimal or None values across windows.

    Returns:
        Dict with keys: available_count, unavailable_count, mean, median,
        std_dev, mad, min, max, q1, q3, iqr, positive_share, negative_share,
        zero_share.
        Unavailable statistics are stored as None.
    """
    # Filter available values
    available = [d for d in deltas if d is not None]
    unavailable_count = sum(1 for d in deltas if d is None)
    available_count = len(available)

    result: dict[str, Any] = {
        "available_count": available_count,
        "unavailable_count": unavailable_count,
    }

    if available_count == 0:
        result.update({
            "mean": None,
            "median": None,
            "std_dev": None,
            "mad": None,
            "min": None,
            "max": None,
            "q1": None,
            "q3": None,
            "iqr": None,
            "positive_share": Decimal("0"),
            "negative_share": Decimal("0"),
            "zero_share": Decimal("0"),
        })
        return result

    sorted_vals = sorted(available)
    n = Decimal(str(available_count))
    mean_val = sum(available) / n
    median_val = _median(available)
    std_val = _std_dev(available)
    mad_val = _mad(available)
    min_val = sorted_vals[0]
    max_val = sorted_vals[-1]
    q1, q3 = _quartiles(available)
    iqr_val = q3 - q1

    # Positive/negative/zero shares
    positive = sum(1 for d in available if d > Decimal("0"))
    negative = sum(1 for d in available if d < Decimal("0"))
    zero = sum(1 for d in available if d == Decimal("0"))

    positive_share = Decimal(str(positive)) / n if n > 0 else Decimal("0")
    negative_share = Decimal(str(negative)) / n if n > 0 else Decimal("0")
    zero_share = Decimal(str(zero)) / n if n > 0 else Decimal("0")

    result.update({
        "mean": mean_val,
        "median": median_val,
        "std_dev": std_val,
        "mad": mad_val,
        "min": min_val,
        "max": max_val,
        "q1": q1,
        "q3": q3,
        "iqr": iqr_val,
        "positive_share": positive_share,
        "negative_share": negative_share,
        "zero_share": zero_share,
    })
    return result
