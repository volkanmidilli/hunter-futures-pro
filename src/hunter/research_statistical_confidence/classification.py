"""Confidence state classification for metric deltas (MVP-67 / SPEC-068)."""

from __future__ import annotations

from decimal import Decimal

from hunter.research_statistical_confidence.models import (
    BOOTSTRAP_CONFIDENCE_EXCLUDES_ZERO,
    BOOTSTRAP_CONFIDENCE_INCLUDES_ZERO,
    DIRECTION_CONFLICT_CODE,
    INSUFFICIENT_SIGN_SHARE,
    NO_BOOTSTRAP,
    ROBUSTNESS_FAILED,
    ROBUSTNESS_PASSED,
    BootstrapInterval,
    ConfidenceState,
    LeaveOneOutResult,
    StatisticalConfidenceConfig,
)


def _bootstrap_excludes_zero(ci: BootstrapInterval | None) -> bool:
    """Check if the bootstrap confidence interval excludes zero."""
    if ci is None:
        return False
    return ci.lower > Decimal("0") or ci.upper < Decimal("0")


def classify_metric_confidence(
    available_count: int,
    positive_share: Decimal,
    negative_share: Decimal,
    loo: LeaveOneOutResult | None,
    mean_ci: BootstrapInterval | None,
    median_ci: BootstrapInterval | None,  # noqa: ARG001
    config: StatisticalConfidenceConfig,
) -> tuple[ConfidenceState, tuple[str, ...]]:
    """Classify a metric into a ConfidenceState based on statistical evidence.

    Args:
        available_count: Number of windows with available data.
        positive_share: Share of deltas > 0 (Decimal 0-1).
        negative_share: Share of deltas < 0 (Decimal 0-1).
        loo: Leave-one-out sensitivity result (or None).
        mean_ci: Bootstrap confidence interval for the mean (or None).
        median_ci: Bootstrap confidence interval for the median (or None).
        config: Statistical confidence configuration.

    Returns:
        Tuple of (ConfidenceState, tuple of reason codes).
    """
    reason_codes: list[str] = []

    # 1. INSUFFICIENT_EVIDENCE
    if available_count < config.minimum_available_window_count:
        reason_codes.append("INSUFFICIENT_EVIDENCE")
        return ConfidenceState.INSUFFICIENT_EVIDENCE, tuple(reason_codes)

    sst = config.robustness.sign_share_threshold
    mir = config.robustness.maximum_influence_ratio

    # 2. Direction conflicts or weak sign share
    if positive_share > Decimal("0") and negative_share > Decimal("0"):
        # Both directions present
        if positive_share >= sst and negative_share == Decimal("0"):
            pass  # still directional candidate
        elif negative_share >= sst and positive_share == Decimal("0"):
            pass  # still directional baseline
        else:
            reason_codes.append(DIRECTION_CONFLICT_CODE)
            return ConfidenceState.MIXED, tuple(reason_codes)

    # Check for sufficient sign share
    has_candidate_direction = positive_share >= sst and negative_share == Decimal("0")
    has_baseline_direction = negative_share >= sst and positive_share == Decimal("0")

    if not has_candidate_direction and not has_baseline_direction:
        if positive_share > Decimal("0") and negative_share > Decimal("0"):
            reason_codes.append(DIRECTION_CONFLICT_CODE)
            return ConfidenceState.MIXED, tuple(reason_codes)
        reason_codes.append(INSUFFICIENT_SIGN_SHARE)
        return ConfidenceState.MIXED, tuple(reason_codes)

    # 3. Check LOO
    if loo is None:
        reason_codes.append(NO_BOOTSTRAP)
        return ConfidenceState.UNSTABLE, tuple(reason_codes)

    if not loo.sign_stable:
        reason_codes.append("UNSTABLE_SIGN")
        return ConfidenceState.UNSTABLE, tuple(reason_codes)

    # Check excessive influence
    if loo.max_influence_ratio > mir:
        reason_codes.append(ROBUSTNESS_FAILED)

    # 4. Direction assignment
    is_candidate = has_candidate_direction  # positive delta = candidate higher

    # 5. Check bootstrap CI and robustness
    bootstrap_excludes = _bootstrap_excludes_zero(mean_ci)

    if bootstrap_excludes and loo.max_influence_ratio <= mir:
        reason_codes.append(BOOTSTRAP_CONFIDENCE_EXCLUDES_ZERO)
        reason_codes.append(ROBUSTNESS_PASSED)
        if is_candidate:
            return ConfidenceState.ROBUST_CANDIDATE, tuple(reason_codes)
        return ConfidenceState.ROBUST_BASELINE, tuple(reason_codes)

    if loo.max_influence_ratio > mir:
        reason_codes.append("EXCESSIVE_INFLUENCE")

    if bootstrap_excludes:
        reason_codes.append(BOOTSTRAP_CONFIDENCE_EXCLUDES_ZERO)
    else:
        reason_codes.append(BOOTSTRAP_CONFIDENCE_INCLUDES_ZERO)

    # Directionally stable but not robust
    if is_candidate:
        return ConfidenceState.DIRECTIONALLY_STABLE_CANDIDATE, tuple(reason_codes)
    return ConfidenceState.DIRECTIONALLY_STABLE_BASELINE, tuple(reason_codes)
