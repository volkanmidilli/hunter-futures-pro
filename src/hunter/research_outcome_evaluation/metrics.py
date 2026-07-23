"""Per-pair and cohort metrics for SPEC-076 outcome evaluation (M3).

All metrics are descriptive point estimates.  Percent metrics are quantized
to 6 decimal places for deterministic serialization; Spearman correlations
are computed over all ``OUTCOME_AVAILABLE`` observations in the matured
cohort (never Top-N-only) and likewise quantized.

Realized volatility is the population standard deviation of valid
intra-window 1h log returns, expressed as a percentage and not annualized.
Invalid candles are excluded as missing; coverage is checked before
calculation by the resolver; fewer than two valid returns yields ``None``.
"""

from __future__ import annotations

import math
from datetime import timedelta
from decimal import Decimal
from statistics import pstdev

from hunter.research_outcome_evaluation.models import TOP_N_CUTS
from hunter.research_outcome_evaluation.resolution import PairEvaluation

PCT_QUANT = Decimal("0.000001")


def _q(value: float) -> Decimal:
    return Decimal(str(value)).quantize(PCT_QUANT)


def _mean_dec(values: list[Decimal]) -> Decimal | None:
    if not values:
        return None
    return (sum(values) / Decimal(len(values))).quantize(PCT_QUANT)


def compute_realized_return(reference_close: Decimal, endpoint_close: Decimal) -> Decimal:
    """Percentage return from reference close to endpoint close."""
    return ((endpoint_close - reference_close) / reference_close * Decimal(100)).quantize(PCT_QUANT)


def compute_mae_mfe(evaluation: PairEvaluation) -> tuple[Decimal | None, Decimal | None]:
    """MAE/MFE percentages vs entry (reference close) over valid window candles.

    MAE uses intra-window 1h lows; MFE uses intra-window 1h highs.  Invalid
    candles are excluded as missing.
    """
    assert evaluation.series is not None
    assert evaluation.reference_candle is not None
    entry = Decimal(str(evaluation.reference_candle.close))
    by_open = evaluation.series.by_open_time()

    lows: list[float] = []
    highs: list[float] = []
    for slot in range(1, evaluation.anchors.expected_slots + 1):
        open_time = evaluation.anchors.reference_open_time + timedelta(hours=slot)
        candle = by_open.get(open_time)
        if candle is not None and candle.valid:
            lows.append(candle.low)
            highs.append(candle.high)

    mae = _q((min(lows) - float(entry)) / float(entry) * 100.0) if lows else None
    mfe = _q((max(highs) - float(entry)) / float(entry) * 100.0) if highs else None
    return mae, mfe


def compute_realized_volatility_pct(evaluation: PairEvaluation) -> Decimal | None:
    """Population std dev of valid intra-window 1h log returns, in percent.

    Returns ``None`` when fewer than two valid adjacent returns exist.
    Not annualized.
    """
    assert evaluation.series is not None
    by_open = evaluation.series.by_open_time()

    closes: list[float | None] = []
    reference = by_open.get(evaluation.anchors.reference_open_time)
    closes.append(reference.close if reference is not None and reference.valid else None)
    for slot in range(1, evaluation.anchors.expected_slots + 1):
        open_time = evaluation.anchors.reference_open_time + timedelta(hours=slot)
        candle = by_open.get(open_time)
        closes.append(candle.close if candle is not None and candle.valid else None)

    returns: list[float] = []
    for previous, current in zip(closes, closes[1:]):
        if previous is not None and current is not None and previous > 0 and current > 0:
            returns.append(math.log(current / previous))

    if len(returns) < 2:
        return None
    return _q(pstdev(returns) * 100.0)


def _average_ranks(values: list[float]) -> list[float]:
    """Average ranks (1-based) with ties sharing the mean rank."""
    order = sorted(range(len(values)), key=lambda i: (values[i], i))
    ranks = [0.0] * len(values)
    i = 0
    n = len(values)
    while i < n:
        j = i
        while j + 1 < n and values[order[j + 1]] == values[order[i]]:
            j += 1
        mean_rank = (i + 1 + j + 1) / 2.0
        for k in range(i, j + 1):
            ranks[order[k]] = mean_rank
        i = j + 1
    return ranks


def spearman(xs: list[float], ys: list[float]) -> Decimal | None:
    """Spearman rank correlation with average ranks on ties.

    Returns ``None`` for fewer than two observations or zero variance in
    either rank vector.  Quantized to 6 decimal places.
    """
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    rx = _average_ranks(xs)
    ry = _average_ranks(ys)
    n = len(xs)
    mean_x = sum(rx) / n
    mean_y = sum(ry) / n
    cov = sum((a - mean_x) * (b - mean_y) for a, b in zip(rx, ry))
    var_x = sum((a - mean_x) ** 2 for a in rx)
    var_y = sum((b - mean_y) ** 2 for b in ry)
    if var_x == 0.0 or var_y == 0.0:
        return None
    return _q(cov / math.sqrt(var_x * var_y))


def top_n_return_pct(ranked_returns: list[tuple[int, Decimal]], n: int) -> Decimal | None:
    """Mean realized return over available pairs with ``rank <= n``."""
    selected = [ret for rank, ret in ranked_returns if rank <= n]
    return _mean_dec(selected)


def mean_pct(values: list[Decimal]) -> Decimal | None:
    """Quantized mean of Decimal percentages; ``None`` when empty."""
    return _mean_dec(values)


__all__ = [
    "PCT_QUANT",
    "TOP_N_CUTS",
    "compute_mae_mfe",
    "compute_realized_return",
    "compute_realized_volatility_pct",
    "mean_pct",
    "spearman",
    "top_n_return_pct",
]
