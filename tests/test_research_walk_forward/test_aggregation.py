"""Tests for metric aggregation (MVP-66 Stage 5)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from hunter.research_walk_forward.aggregation import (
    _mean,
    _median,
    _quartiles,
    aggregate_metrics,
)
from hunter.research_walk_forward.models import (
    ConsistencyState,
    MetricDirection,
    WalkForwardWindow,
    WalkForwardWindowResult,
    WindowStatus,
)


def _make_window(
    index: int,
    candidate_total: Decimal | None,
    baseline_total: Decimal | None,
    regime_label: Any = None,
) -> WalkForwardWindowResult:
    from hunter.research_walk_forward.models import MarketRegimeLabel

    if regime_label is None:
        regime_label = MarketRegimeLabel.UNKNOWN
    window = WalkForwardWindow(
        selection_start="20240101",
        selection_end="20240201",
        evaluation_start="20240301",
        evaluation_end="20240401",
        regime_label=regime_label,
    )
    delta = None
    direction = MetricDirection.UNAVAILABLE
    if candidate_total is not None and baseline_total is not None:
        delta = candidate_total - baseline_total
        direction = _interpret_delta("total_return_pct", delta, candidate_total, baseline_total)
    return WalkForwardWindowResult(
        window=window,
        window_index=index,
        status=WindowStatus.COMPLETED,
        candidate_metrics={"total_return_pct": candidate_total},
        baseline_metrics={"total_return_pct": baseline_total},
        metric_deltas={"total_return_pct": delta},
        metric_directions={"total_return_pct": direction},
        comparison_fingerprint="fp",
        candidate_fingerprint="fp",
        baseline_fingerprint="fp",
        fingerprint="fp",
    )


def _interpret_delta(
    name: str,
    delta: Decimal | None,
    candidate: Decimal | None,
    baseline: Decimal | None,
) -> MetricDirection:
    if delta is None or candidate is None or baseline is None:
        return MetricDirection.UNAVAILABLE
    if delta == 0:
        return MetricDirection.EQUAL
    if delta > 0:
        return MetricDirection.CANDIDATE_HIGHER
    return MetricDirection.BASELINE_HIGHER


class TestDecimalMean:
    def test_mean(self) -> None:
        values = [Decimal("1"), Decimal("2"), Decimal("3"), Decimal("4")]
        assert _mean(values) == Decimal("2.5")

    def test_mean_empty(self) -> None:
        assert _mean([]) is None


class TestDecimalMedian:
    def test_median_odd(self) -> None:
        values = [Decimal("1"), Decimal("2"), Decimal("3"), Decimal("4"), Decimal("5")]
        assert _median(values) == Decimal("3")

    def test_median_even(self) -> None:
        values = [Decimal("1"), Decimal("2"), Decimal("3"), Decimal("4")]
        assert _median(values) == Decimal("2.5")

    def test_median_empty(self) -> None:
        assert _median([]) is None


class TestQuartiles:
    def test_q1_q3_iqr(self) -> None:
        values = [Decimal("1"), Decimal("2"), Decimal("3"), Decimal("4"), Decimal("5"), Decimal("6"), Decimal("7"), Decimal("8")]
        q1, q3, iqr = _quartiles(values)
        assert q1 == Decimal("2.5")
        assert q3 == Decimal("6.5")
        assert iqr == Decimal("4")

    def test_quartiles_odd(self) -> None:
        values = [Decimal("1"), Decimal("2"), Decimal("3"), Decimal("4"), Decimal("5")]
        q1, q3, iqr = _quartiles(values)
        assert q1 == Decimal("1.5")
        assert q3 == Decimal("4.5")
        assert iqr == Decimal("3")

    def test_quartiles_empty(self) -> None:
        q1, q3, iqr = _quartiles([])
        assert q1 is None
        assert q3 is None
        assert iqr is None


class TestMetricAggregation:
    def test_consistent_candidate_higher(self) -> None:
        windows = (
            _make_window(0, Decimal("10"), Decimal("5")),
            _make_window(1, Decimal("12"), Decimal("6")),
            _make_window(2, Decimal("8"), Decimal("4")),
        )
        aggregates = aggregate_metrics(windows)
        agg = aggregates["total_return_pct"]
        assert agg.available_count == 3
        assert agg.unavailable_count == 0
        assert agg.candidate_higher_count == 3
        assert agg.baseline_higher_count == 0
        assert agg.equal_count == 0
        assert agg.consistency_state == ConsistencyState.CONSISTENT_CANDIDATE_HIGHER
        assert agg.positive_delta_share == Decimal("1")
        assert agg.negative_delta_share == Decimal("0")
        assert agg.zero_delta_share == Decimal("0")

    def test_mostly_candidate_higher(self) -> None:
        windows = (
            _make_window(0, Decimal("10"), Decimal("5")),
            _make_window(1, Decimal("10"), Decimal("5")),
            _make_window(2, Decimal("10"), Decimal("5")),
            _make_window(3, Decimal("5"), Decimal("10")),
        )
        aggregates = aggregate_metrics(windows)
        agg = aggregates["total_return_pct"]
        assert agg.consistency_state == ConsistencyState.MOSTLY_CANDIDATE_HIGHER

    def test_mixed(self) -> None:
        windows = (
            _make_window(0, Decimal("10"), Decimal("5")),
            _make_window(1, Decimal("5"), Decimal("10")),
            _make_window(2, Decimal("10"), Decimal("5")),
        )
        aggregates = aggregate_metrics(windows)
        agg = aggregates["total_return_pct"]
        assert agg.consistency_state == ConsistencyState.MIXED

    def test_consistent_baseline_higher(self) -> None:
        windows = (
            _make_window(0, Decimal("5"), Decimal("10")),
            _make_window(1, Decimal("4"), Decimal("8")),
        )
        aggregates = aggregate_metrics(windows)
        agg = aggregates["total_return_pct"]
        assert agg.consistency_state == ConsistencyState.CONSISTENT_BASELINE_HIGHER

    def test_equal_or_unavailable(self) -> None:
        windows = (_make_window(0, None, None),)
        aggregates = aggregate_metrics(windows)
        agg = aggregates["total_return_pct"]
        assert agg.available_count == 0
        assert agg.unavailable_count == 1
        assert agg.consistency_state == ConsistencyState.EQUAL_OR_UNAVAILABLE

    def test_zero_delta_share(self) -> None:
        windows = (
            _make_window(0, Decimal("10"), Decimal("10")),
            _make_window(1, Decimal("5"), Decimal("5")),
        )
        aggregates = aggregate_metrics(windows)
        agg = aggregates["total_return_pct"]
        assert agg.equal_count == 2
        assert agg.zero_delta_share == Decimal("1")
        assert agg.positive_delta_share == Decimal("0")
        assert agg.negative_delta_share == Decimal("0")

    def test_min_max(self) -> None:
        windows = (
            _make_window(0, Decimal("10"), Decimal("5")),  # delta 5
            _make_window(1, Decimal("12"), Decimal("6")),  # delta 6
            _make_window(2, Decimal("8"), Decimal("4")),  # delta 4
        )
        aggregates = aggregate_metrics(windows)
        agg = aggregates["total_return_pct"]
        assert agg.min == Decimal("4")
        assert agg.max == Decimal("6")
