"""Deterministic bootstrap confidence intervals for metric deltas (MVP-67 / SPEC-068)."""

from __future__ import annotations

import math
import random
from decimal import Decimal

from hunter.research_statistical_confidence.descriptive import _median
from hunter.research_statistical_confidence.models import (
    BootstrapConfig,
    BootstrapInterval,
    StatisticalConfidenceConfig,
)


def _percentile_interval(
    values: list[Decimal],
    confidence_level: Decimal,
) -> tuple[Decimal, Decimal]:
    """Compute a percentile-based confidence interval using nearest-rank method.

    Args:
        values: Sorted list of bootstrap replicate statistics.
        confidence_level: Decimal between 0 and 1 (e.g., 0.95 for 95% CI).

    Returns:
        Tuple of (lower, upper) bounds using the nearest-rank method.
        lower_index = floor((1 - confidence_level) / 2 * len(values))
        upper_index = ceil((1 + confidence_level) / 2 * len(values)) - 1
        Both indices are clamped to valid range [0, len(values)-1].
    """
    n = len(values)
    if n == 0:
        return Decimal("0"), Decimal("0")

    alpha = (Decimal("1") - confidence_level) / Decimal("2")

    lower_index_f = float(alpha) * n
    upper_index_f = float(Decimal("1") - alpha) * n - 1

    # Nearest-rank: floor for lower, ceil for upper, then clamp
    lower_idx = max(0, min(n - 1, int(math.floor(lower_index_f))))
    upper_idx = max(0, min(n - 1, int(math.ceil(upper_index_f))))

    return values[lower_idx], values[upper_idx]


def compute_bootstrap_confidence_intervals(
    deltas: list[Decimal | None],
    config: StatisticalConfidenceConfig,
) -> tuple[BootstrapInterval | None, BootstrapInterval | None]:
    """Compute deterministic bootstrap confidence intervals for mean and median.

    Args:
        deltas: List of Decimal or None values across windows.
        config: Statistical confidence configuration with bootstrap settings.

    Returns:
        Tuple of (bootstrap_mean_ci, bootstrap_median_ci). Returns (None, None)
        if there are insufficient available windows.
    """
    available = [d for d in deltas if d is not None]
    n = len(available)

    # Need at least 3 available values for bootstrap to be meaningful
    minimum_for_bootstrap = max(3, config.minimum_available_window_count)
    if n < minimum_for_bootstrap:
        return None, None

    rng = random.Random(config.bootstrap.seed)

    means: list[Decimal] = []
    medians: list[Decimal] = []

    for _ in range(config.bootstrap.iterations):
        # Sample n values with replacement
        sample = [rng.choice(available) for _ in range(n)]
        sample_mean = sum(sample) / Decimal(str(n))
        sample_median = _median(sample)
        means.append(sample_mean)
        medians.append(sample_median)

    means.sort()
    medians.sort()

    cl = config.confidence_level
    lower_mean, upper_mean = _percentile_interval(means, cl)
    lower_median, upper_median = _percentile_interval(medians, cl)

    mean_ci = BootstrapInterval(lower=lower_mean, upper=upper_mean, confidence_level=cl)
    median_ci = BootstrapInterval(lower=lower_median, upper=upper_median, confidence_level=cl)

    return mean_ci, median_ci
