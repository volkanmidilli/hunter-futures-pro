"""M3 tests: per-pair and cohort metrics."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from hunter.research_outcome_evaluation.metrics import (
    compute_mae_mfe,
    compute_realized_return,
    compute_realized_volatility_pct,
    mean_pct,
    spearman,
    top_n_return_pct,
)
from hunter.research_outcome_evaluation.price_source import Candle, PriceSeries
from hunter.research_outcome_evaluation.resolution import compute_window_anchors, resolve_series

START = datetime(2026, 1, 8, tzinfo=timezone.utc)


def _candle(i: int, close: float, *, low: float | None = None, high: float | None = None, valid: bool = True) -> Candle:
    return Candle(
        timestamp=START + timedelta(hours=i),
        open=close,
        high=high if high is not None else close + 1.0,
        low=low if low is not None else close - 1.0,
        close=close,
        volume=10.0,
        valid=valid,
    )


def _evaluation(closes: list[float], horizon: str = "1d"):
    """Build a resolved PairEvaluation over ``closes`` indexed hourly from START."""
    invalid = {i for i, c in enumerate(closes) if c <= 0}
    candles = tuple(
        _candle(i, abs(c) if c != 0 else 1.0, valid=(i not in invalid))
        for i, c in enumerate(closes)
    )
    series = PriceSeries(pair="SOL/USDT:USDT", candles=candles)
    anchors = compute_window_anchors("2026-01-10", horizon)
    return resolve_series(
        series=series,
        anchors=anchors,
        min_window_coverage_num=95,
        min_window_coverage_den=100,
    )


# Reference candle open = 2026-01-10 07:00 -> index 55 from 2026-01-08 00:00.
REF_INDEX = 55


def test_compute_realized_return() -> None:
    result = compute_realized_return(Decimal("100"), Decimal("101.5"))
    assert result == Decimal("1.500000")
    negative = compute_realized_return(Decimal("100"), Decimal("97"))
    assert negative == Decimal("-3.000000")


def test_mae_mfe_over_valid_window() -> None:
    closes = [100.0] * 200
    closes[REF_INDEX] = 100.0  # reference close = 100
    # Window slots 1..24 -> indices 56..79.
    for i in range(56, 80):
        closes[i] = 100.0
    evaluation = _evaluation(closes)
    mae, mfe = compute_mae_mfe(evaluation)
    # lows = close-1 = 99 -> (99-100)/100 = -1%; highs = close+1 = 101 -> +1%
    assert mae == Decimal("-1.000000")
    assert mfe == Decimal("1.000000")


def test_mae_mfe_skips_invalid_candles() -> None:
    closes = [100.0] * 200
    evaluation = _evaluation(closes)
    # Corrupt one window candle via direct series replacement.
    candles = list(evaluation.series.candles)
    idx = 56 + 3
    bad = candles[idx]
    candles[idx] = Candle(
        timestamp=bad.timestamp, open=-1.0, high=1000.0, low=0.0001,
        close=-1.0, volume=-5.0, valid=False,
    )
    series = PriceSeries(pair="SOL/USDT:USDT", candles=tuple(candles))
    evaluation2 = resolve_series(
        series=series,
        anchors=evaluation.anchors,
        min_window_coverage_num=95,
        min_window_coverage_den=100,
    )
    mae, mfe = compute_mae_mfe(evaluation2)
    assert mae == Decimal("-1.000000")
    assert mfe == Decimal("1.000000")


def test_volatility_flat_series_is_zero() -> None:
    closes = [100.0] * 200
    evaluation = _evaluation(closes)
    vol = compute_realized_volatility_pct(evaluation)
    assert vol == Decimal("0.000000")


def test_volatility_alternating_series() -> None:
    closes = [100.0] * 200
    for i in range(REF_INDEX + 1, REF_INDEX + 25):
        closes[i] = 100.0 if i % 2 == 0 else 101.0
    evaluation = _evaluation(closes)
    vol = compute_realized_volatility_pct(evaluation)
    assert vol is not None
    returns = []
    seq = [100.0] + [100.0 if i % 2 == 0 else 101.0 for i in range(REF_INDEX + 1, REF_INDEX + 25)]
    for a, b in zip(seq, seq[1:]):
        returns.append(math.log(b / a))
    from statistics import pstdev as _pstdev

    expected = Decimal(str(_pstdev(returns) * 100.0)).quantize(Decimal("0.000001"))
    assert vol == expected


def test_volatility_fewer_than_two_returns_is_none() -> None:
    closes = [100.0] * 200
    # Invalidate every window candle except the endpoint: only one valid
    # return possible (reference->endpoint not adjacent) -> actually zero
    # adjacent valid pairs -> None.
    for i in range(56, 79):
        closes[i] = -1.0  # invalid
    closes[REF_INDEX] = 100.0
    closes[79] = 100.0
    # Coverage: only endpoint valid -> 1/24 < 0.95 -> GAP, so build manually.
    anchors = compute_window_anchors("2026-01-10", "1d")
    invalid = {i for i in range(56, 79)}
    candles = tuple(
        _candle(i, 100.0, valid=(i not in invalid)) for i in range(200)
    )
    series = PriceSeries(pair="SOL/USDT:USDT", candles=candles)
    evaluation = resolve_series(
        series=series,
        anchors=anchors,
        min_window_coverage_num=1,
        min_window_coverage_den=100,
    )
    assert evaluation.coverage_ratio_num >= 1
    vol = compute_realized_volatility_pct(evaluation)
    assert vol is None


def test_spearman_perfect_monotonic() -> None:
    result = spearman([1.0, 2.0, 3.0, 4.0], [10.0, 20.0, 30.0, 40.0])
    assert result == Decimal("1.000000")


def test_spearman_perfect_negative() -> None:
    result = spearman([1.0, 2.0, 3.0, 4.0], [40.0, 30.0, 20.0, 10.0])
    assert result == Decimal("-1.000000")


def test_spearman_with_ties_average_ranks() -> None:
    # xs ties at ranks 1.5/1.5; ys strict.
    result = spearman([1.0, 1.0, 2.0], [1.0, 2.0, 3.0])
    assert result is not None
    assert Decimal("-1") < result < Decimal("1")


def test_spearman_zero_variance_is_none() -> None:
    assert spearman([1.0, 1.0, 1.0], [1.0, 2.0, 3.0]) is None


def test_spearman_too_few_observations() -> None:
    assert spearman([1.0], [1.0]) is None
    assert spearman([], []) is None


def test_top_n_return_pct() -> None:
    ranked = [(1, Decimal("2")), (2, Decimal("4")), (3, Decimal("6")), (10, Decimal("100"))]
    assert top_n_return_pct(ranked, 1) == Decimal("2.000000")
    assert top_n_return_pct(ranked, 2) == Decimal("3.000000")
    assert top_n_return_pct(ranked, 3) == Decimal("4.000000")
    assert top_n_return_pct(ranked, 5) == Decimal("4.000000")
    assert top_n_return_pct(ranked, 30) == Decimal("28.000000")


def test_top_n_return_pct_empty() -> None:
    assert top_n_return_pct([], 5) is None


def test_mean_pct() -> None:
    assert mean_pct([Decimal("1"), Decimal("3")]) == Decimal("2.000000")
    assert mean_pct([]) is None
