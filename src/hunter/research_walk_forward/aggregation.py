"""Metric aggregation for walk-forward window results (MVP-66 / SPEC-067)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from hunter.research_walk_forward.models import (
    MISSING_METRIC,
    ConsistencyState,
    MetricAggregate,
    MetricDirection,
    WalkForwardWindowResult,
)


_CANONICAL_METRIC_NAMES: tuple[str, ...] = (
    "total_return_pct",
    "absolute_profit",
    "final_balance",
    "max_drawdown_pct",
    "sharpe_ratio",
    "sortino_ratio",
    "calmar_ratio",
    "profit_factor",
    "win_rate_pct",
    "trade_count",
    "average_trade_duration_seconds",
    "fees_paid",
)


def _median(values: list[Decimal]) -> Decimal | None:
    """Return the median of a sorted list of Decimal values."""
    if not values:
        return None
    sorted_values = sorted(values)
    n = len(sorted_values)
    if n % 2 == 1:
        return sorted_values[n // 2]
    mid = n // 2
    return (sorted_values[mid - 1] + sorted_values[mid]) / Decimal("2")


def _quartiles(values: list[Decimal]) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
    """Return (q1, q3, iqr) using the median-of-halves method (inclusive for odd n).

    This implementation aligns with research_statistical_confidence.descriptive._quartiles
    so that MVP-66 and MVP-67 produce identical quartiles for the same delta list.
    """
    if not values:
        return None, None, None
    sorted_values = sorted(values)
    n = len(sorted_values)

    if n == 1:
        q1 = sorted_values[0]
        q3 = sorted_values[0]
    else:
        # Include median in both halves for odd n (Tukey's hinges).
        if n % 2 == 0:
            lower = sorted_values[: n // 2]
            upper = sorted_values[n // 2 :]
        else:
            lower = sorted_values[: n // 2 + 1]
            upper = sorted_values[n // 2 :]
        q1 = _median(lower)
        q3 = _median(upper)

    iqr = None if q1 is None or q3 is None else q3 - q1
    return q1, q3, iqr


def _mean(values: list[Decimal]) -> Decimal | None:
    """Return the arithmetic mean of Decimal values."""
    if not values:
        return None
    return sum(values, Decimal("0")) / Decimal(str(len(values)))


def _aggregate_metric(
    metric_name: str,
    windows: tuple[WalkForwardWindowResult, ...],
) -> MetricAggregate:
    """Aggregate one metric across all windows."""
    deltas: list[Decimal] = []
    candidate_values: list[Decimal] = []
    baseline_values: list[Decimal] = []
    available_count = 0
    unavailable_count = 0
    candidate_higher_count = 0
    baseline_higher_count = 0
    equal_count = 0
    positive_count = 0
    negative_count = 0
    zero_count = 0
    reason_codes: list[str] = []

    for window in windows:
        direction = window.metric_directions.get(metric_name, MetricDirection.UNAVAILABLE)
        delta = window.metric_deltas.get(metric_name)
        cand = window.candidate_metrics.get(metric_name)
        base = window.baseline_metrics.get(metric_name)

        if delta is None or cand is None or base is None:
            unavailable_count += 1
            continue

        available_count += 1
        deltas.append(delta)
        candidate_values.append(cand)
        baseline_values.append(base)

        if direction == MetricDirection.CANDIDATE_HIGHER:
            candidate_higher_count += 1
        elif direction == MetricDirection.BASELINE_HIGHER:
            baseline_higher_count += 1
        elif direction == MetricDirection.EQUAL:
            equal_count += 1

        if delta > 0:
            positive_count += 1
        elif delta < 0:
            negative_count += 1
        else:
            zero_count += 1

    if available_count == 0:
        consistency_state = ConsistencyState.EQUAL_OR_UNAVAILABLE
        positive_share = Decimal("0")
        negative_share = Decimal("0")
        zero_share = Decimal("0")
    else:
        total = Decimal(str(available_count))
        cand_share = Decimal(str(candidate_higher_count)) / total
        base_share = Decimal(str(baseline_higher_count)) / total
        if available_count == candidate_higher_count:
            consistency_state = ConsistencyState.CONSISTENT_CANDIDATE_HIGHER
        elif cand_share >= Decimal("0.70"):
            consistency_state = ConsistencyState.MOSTLY_CANDIDATE_HIGHER
        elif available_count == baseline_higher_count:
            consistency_state = ConsistencyState.CONSISTENT_BASELINE_HIGHER
        elif base_share >= Decimal("0.70"):
            consistency_state = ConsistencyState.MOSTLY_BASELINE_HIGHER
        else:
            consistency_state = ConsistencyState.MIXED

        positive_share = Decimal(str(positive_count)) / total
        negative_share = Decimal(str(negative_count)) / total
        zero_share = Decimal(str(zero_count)) / total

    if unavailable_count > 0:
        reason_codes.append(MISSING_METRIC)

    return MetricAggregate(
        metric_name=metric_name,
        available_count=available_count,
        unavailable_count=unavailable_count,
        candidate_higher_count=candidate_higher_count,
        baseline_higher_count=baseline_higher_count,
        equal_count=equal_count,
        mean=_mean(deltas),
        median=_median(deltas),
        min=min(deltas) if deltas else None,
        max=max(deltas) if deltas else None,
        q1=_quartiles(deltas)[0],
        q3=_quartiles(deltas)[1],
        iqr=_quartiles(deltas)[2],
        positive_delta_share=positive_share,
        negative_delta_share=negative_share,
        zero_delta_share=zero_share,
        consistency_state=consistency_state,
        reason_codes=tuple(reason_codes),
    )


def aggregate_metrics(
    windows: tuple[WalkForwardWindowResult, ...],
) -> dict[str, MetricAggregate]:
    """Aggregate all canonical metrics across the provided windows."""
    return {name: _aggregate_metric(name, windows) for name in _CANONICAL_METRIC_NAMES}
