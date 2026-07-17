"""Leave-one-window-out sensitivity analysis (MVP-67 / SPEC-068)."""

from __future__ import annotations

from decimal import Decimal

from hunter.research_statistical_confidence.descriptive import _median
from hunter.research_statistical_confidence.models import (
    CONSISTENT_DIRECTION,
    EXCESSIVE_INFLUENCE,
    UNSTABLE_SIGN_CODE,
    LeaveOneOutResult,
)
from hunter.research_walk_forward.models import MetricDirection


def compute_leave_one_out(
    deltas: list[Decimal | None],
    config_window_indices: list[int],
    maximum_influence_ratio: Decimal,
) -> LeaveOneOutResult | None:
    """Compute leave-one-window-out sensitivity analysis.

    For each available window, removes it, recomputes mean and median,
    records direction, calculates influence, and identifies the most
    influential window.

    Args:
        deltas: List of Decimal or None values across windows (ordered
            the same as config_window_indices).
        config_window_indices: The window_index values corresponding to
            each position in deltas (for identifying the most influential).
        maximum_influence_ratio: Threshold for excessive influence.

    Returns:
        LeaveOneOutResult, or None if fewer than 2 available values.
    """
    available_with_indices = [
        (d, idx) for d, idx in zip(deltas, config_window_indices) if d is not None
    ]
    available = [d for d, _ in available_with_indices]
    indices = [idx for _, idx in available_with_indices]
    n = len(available)

    if n < 2:
        return None

    full_mean = sum(available) / Decimal(str(n))
    full_median = _median(available)

    max_delta = max(available)
    min_delta = min(available)
    delta_range = max_delta - min_delta

    # Leave-one-out
    loo_means: list[Decimal] = []
    loo_medians: list[Decimal] = []
    loo_directions: list[MetricDirection] = []
    influences: list[Decimal] = []

    for i in range(n):
        loo_sample = available[:i] + available[i + 1 :]
        m = len(loo_sample)
        if m == 0:
            loo_mean = Decimal("0")
            loo_median = Decimal("0")
        else:
            loo_mean = sum(loo_sample) / Decimal(str(m))
            loo_median = _median(loo_sample)

        loo_means.append(loo_mean)
        loo_medians.append(loo_median)

        # Direction
        if loo_mean > Decimal("0"):
            loo_directions.append(MetricDirection.CANDIDATE_HIGHER)
        elif loo_mean < Decimal("0"):
            loo_directions.append(MetricDirection.BASELINE_HIGHER)
        else:
            loo_directions.append(MetricDirection.EQUAL)

        # Influence: |loo_mean - full_mean| / delta_range
        if delta_range > Decimal("0"):
            influence = abs(loo_mean - full_mean) / delta_range
        else:
            influence = Decimal("0")
        influences.append(influence)

    mean_range = max(loo_means) - min(loo_means)
    median_range = max(loo_medians) - min(loo_medians)

    # Max influence
    max_influence = max(influences)
    max_influence_idx = influences.index(max_influence)
    max_influence_window_index = indices[max_influence_idx]

    # Sign stability
    full_sign = full_mean > Decimal("0")
    signs_same = True
    for loo_mean in loo_means:
        if (loo_mean > Decimal("0")) != full_sign and loo_mean != Decimal("0"):
            signs_same = False
            break
    # If full_mean is zero, all loo means must be zero for sign stability
    if full_mean == Decimal("0"):
        signs_same = all(loo_mean == Decimal("0") for loo_mean in loo_means)

    sign_stable = signs_same

    # Reason codes
    reason_codes: list[str] = []
    if sign_stable:
        reason_codes.append(CONSISTENT_DIRECTION)
    else:
        reason_codes.append(UNSTABLE_SIGN_CODE)
    if max_influence > maximum_influence_ratio:
        reason_codes.append(EXCESSIVE_INFLUENCE)

    return LeaveOneOutResult(
        mean_range=mean_range,
        median_range=median_range,
        max_influence_window_index=max_influence_window_index,
        max_influence_ratio=max_influence,
        directions=tuple(loo_directions),
        sign_stable=sign_stable,
        reason_codes=tuple(reason_codes),
    )
