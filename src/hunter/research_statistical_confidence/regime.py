"""Regime-stratified confidence evaluation (MVP-67 / SPEC-068)."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from hunter.research_statistical_confidence.bootstrap import (
    compute_bootstrap_confidence_intervals,
)
from hunter.research_statistical_confidence.classification import (
    classify_metric_confidence,
)
from hunter.research_statistical_confidence.descriptive import (
    compute_metric_descriptive,
)
from hunter.research_statistical_confidence.models import (
    INSUFFICIENT_DATA,
    MetricConfidenceResult,
    RegimeConfidenceResult,
    StatisticalConfidenceConfig,
)
from hunter.research_statistical_confidence.sensitivity import (
    compute_leave_one_out,
)
from hunter.research_walk_forward.models import (
    MarketRegimeLabel,
    MetricDirection,
    WalkForwardExperimentReport,
    WalkForwardWindowResult,
    WindowStatus,
)


def _status_counts(windows: tuple[WalkForwardWindowResult, ...]) -> dict[str, int]:
    """Count windows by status."""
    counts: dict[str, int] = {}
    for status in WindowStatus:
        counts[status.value] = 0
    for window in windows:
        counts[window.status.value] = counts.get(window.status.value, 0) + 1
    return counts


def _get_window_indices(
    windows: tuple[WalkForwardWindowResult, ...],
) -> list[int]:
    """Return the config-level window indices for the given windows."""
    return [w.window_index for w in windows]


def compute_regime_metric_results(
    windows: tuple[WalkForwardWindowResult, ...],
    metric_name: str,
    config: StatisticalConfidenceConfig,
) -> MetricConfidenceResult:
    """Compute MetricConfidenceResult for a single metric within a regime group."""
    deltas: list[Decimal | None] = []
    for w in windows:
        deltas.append(w.metric_deltas.get(metric_name))

    desc = compute_metric_descriptive(deltas)
    window_indices = _get_window_indices(windows)

    # Bootstrap
    mean_ci, median_ci = compute_bootstrap_confidence_intervals(deltas, config)

    # Leave-one-out
    loo = compute_leave_one_out(
        deltas,
        config_window_indices=window_indices,
        maximum_influence_ratio=config.robustness.maximum_influence_ratio,
    )

    # Stage 7 / SPEC-072: detect zero observed dispersion and
    # insufficient distinct values to block ROBUST_* classification
    # when the bootstrap CI is a non-zero point.
    if desc["available_count"] > 0:
        distinct_count = len({d for d in deltas if d is not None})
        zero_observed_dispersion = (
            desc["std_dev"] is not None
            and desc["std_dev"] == Decimal("0")
        )
        insufficient_distinct_values = (
            distinct_count < config.bootstrap.min_distinct_values_for_bootstrap
        )
    else:
        zero_observed_dispersion = False
        insufficient_distinct_values = False

    # Classification
    confidence_state, cls_reason_codes = classify_metric_confidence(
        available_count=desc["available_count"],
        positive_share=desc["positive_share"],
        negative_share=desc["negative_share"],
        loo=loo,
        mean_ci=mean_ci,
        median_ci=median_ci,  # noqa: ARG005 (used for zero-exclusion check)
        config=config,
        zero_observed_dispersion=zero_observed_dispersion,
        insufficient_distinct_values=insufficient_distinct_values,
    )

    reason_codes: list[str] = list(cls_reason_codes)
    if desc["available_count"] == 0:
        reason_codes.append(INSUFFICIENT_DATA)

    return MetricConfidenceResult(
        metric_name=metric_name,
        available_count=desc["available_count"],
        unavailable_count=desc["unavailable_count"],
        mean=desc["mean"],
        median=desc["median"],
        std_dev=desc["std_dev"],
        mad=desc["mad"],
        min=desc["min"],
        max=desc["max"],
        q1=desc["q1"],
        q3=desc["q3"],
        iqr=desc["iqr"],
        positive_share=desc["positive_share"],
        negative_share=desc["negative_share"],
        zero_share=desc["zero_share"],
        bootstrap_mean_ci=mean_ci,
        bootstrap_median_ci=median_ci,
        loo=loo,
        confidence_state=confidence_state,
        reason_codes=tuple(reason_codes),
    )


def compute_regime_results(
    report: WalkForwardExperimentReport,
    config: StatisticalConfidenceConfig,
) -> dict[str, RegimeConfidenceResult]:
    """Compute regime-stratified confidence results.

    Groups window results by regime_label and computes MetricConfidenceResult
    for each metric within each regime group.

    Returns:
        Dict mapping regime_label.value -> RegimeConfidenceResult.
    """
    # Group windows by regime label
    regime_groups: dict[MarketRegimeLabel, list[WalkForwardWindowResult]] = defaultdict(list)
    for window in report.window_results:
        regime_groups[window.window.regime_label].append(window)

    # Collect all metric names from all window results
    all_metric_names: set[str] = set()
    for w in report.window_results:
        all_metric_names.update(w.metric_deltas.keys())
    sorted_metric_names = sorted(all_metric_names)

    results: dict[str, RegimeConfidenceResult] = {}
    for regime_label in sorted(regime_groups.keys(), key=lambda x: x.value):
        windows = tuple(regime_groups[regime_label])
        status_counts = _status_counts(windows)

        metric_results: dict[str, MetricConfidenceResult] = {}
        for metric_name in sorted_metric_names:
            metric_results[metric_name] = compute_regime_metric_results(
                windows, metric_name, config
            )

        # Available count = completed windows in this regime
        available_count = status_counts.get(WindowStatus.COMPLETED.value, 0)

        reason_codes: list[str] = []
        regime_confidence = RegimeConfidenceResult(
            regime_label=regime_label,
            available_count=available_count,
            metric_results=metric_results,
            status_counts=status_counts,
            fingerprint="regime-confidence-placeholder",
            reason_codes=tuple(reason_codes),
        )
        results[regime_label.value] = regime_confidence

    return results
