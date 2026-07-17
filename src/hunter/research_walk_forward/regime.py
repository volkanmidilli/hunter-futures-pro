"""Regime aggregation for walk-forward window results (MVP-66 / SPEC-067)."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any

from hunter.research_walk_forward.aggregation import _CANONICAL_METRIC_NAMES, _aggregate_metric
from hunter.research_walk_forward.models import (
    MarketRegimeLabel,
    RegimeAggregate,
    WindowStatus,
    WalkForwardWindowResult,
)


def _status_counts(windows: tuple[WalkForwardWindowResult, ...]) -> dict[str, int]:
    """Count windows by status."""
    counts = {
        "completed": 0,
        "failed": 0,
        "blocked": 0,
        "timed_out": 0,
        "unsupported": 0,
        "insufficient": 0,
    }
    for window in windows:
        if window.status == WindowStatus.COMPLETED:
            counts["completed"] += 1
        elif window.status == WindowStatus.FAILED:
            counts["failed"] += 1
        elif window.status == WindowStatus.BLOCKED:
            counts["blocked"] += 1
        elif window.status == WindowStatus.TIMED_OUT:
            counts["timed_out"] += 1
        elif window.status == WindowStatus.UNSUPPORTED:
            counts["unsupported"] += 1
        elif window.status == WindowStatus.INSUFFICIENT:
            counts["insufficient"] += 1
    return counts


def group_results_by_regime(
    windows: tuple[WalkForwardWindowResult, ...],
) -> dict[MarketRegimeLabel, tuple[WalkForwardWindowResult, ...]]:
    """Group window results by caller-provided regime label."""
    groups: dict[MarketRegimeLabel, list[WalkForwardWindowResult]] = defaultdict(list)
    for window in windows:
        groups[window.window.regime_label].append(window)
    return {label: tuple(items) for label, items in groups.items()}


def build_regime_aggregate(
    regime_label: MarketRegimeLabel,
    windows: tuple[WalkForwardWindowResult, ...],
    fingerprint: str,
) -> RegimeAggregate:
    """Build a regime aggregate from a group of window results."""
    counts = _status_counts(windows)
    metric_aggregates = {
        name: _aggregate_metric(name, windows) for name in _CANONICAL_METRIC_NAMES
    }
    return RegimeAggregate(
        regime_label=regime_label,
        window_count=len(windows),
        completed_count=counts["completed"],
        failed_count=counts["failed"],
        blocked_count=counts["blocked"],
        timed_out_count=counts["timed_out"],
        unsupported_count=counts["unsupported"],
        insufficient_count=counts["insufficient"],
        metric_aggregates=metric_aggregates,
        fingerprint=fingerprint,
    )
