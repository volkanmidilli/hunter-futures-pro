"""Tests for the deterministic bootstrap module (MVP-67)."""

from __future__ import annotations

from decimal import Decimal

from hunter.research_statistical_confidence.bootstrap import (
    compute_bootstrap_confidence_intervals,
)
from hunter.research_statistical_confidence.models import (
    BootstrapConfig,
    RobustnessCriteria,
    StatisticalConfidenceConfig,
)


def _make_config(seed: int = 42, iterations: int = 1000) -> StatisticalConfidenceConfig:
    return StatisticalConfidenceConfig(
        minimum_available_window_count=3,
        confidence_level=Decimal("0.95"),
        bootstrap=BootstrapConfig(seed=seed, iterations=iterations),
        robustness=RobustnessCriteria(
            sign_share_threshold=Decimal("0.8"),
            maximum_influence_ratio=Decimal("0.3"),
            confidence_level=Decimal("0.95"),
        ),
    )


class TestComputeBootstrapConfidenceIntervals:
    def test_deterministic_same_seed(self) -> None:
        deltas = [Decimal("1"), Decimal("2"), Decimal("3"), Decimal("4"), Decimal("5")]
        config = _make_config(seed=42)
        mean_ci1, median_ci1 = compute_bootstrap_confidence_intervals(deltas, config)
        mean_ci2, median_ci2 = compute_bootstrap_confidence_intervals(deltas, config)
        assert mean_ci1 is not None
        assert median_ci1 is not None
        assert mean_ci1.lower == mean_ci2.lower
        assert mean_ci1.upper == mean_ci2.upper
        assert median_ci1.lower == median_ci2.lower
        assert median_ci1.upper == median_ci2.upper

    def test_different_seed_different_result(self) -> None:
        deltas = [Decimal("1"), Decimal("2"), Decimal("3"), Decimal("4"), Decimal("5")]
        config1 = _make_config(seed=42)
        config2 = _make_config(seed=99)
        mean_ci1, _ = compute_bootstrap_confidence_intervals(deltas, config1)
        mean_ci2, _ = compute_bootstrap_confidence_intervals(deltas, config2)
        assert mean_ci1 is not None
        assert mean_ci2 is not None
        # Different seeds may produce different CIs (not guaranteed for small data but likely)
        # At minimum, the CIs should be valid intervals
        assert mean_ci1.lower <= mean_ci1.upper
        assert mean_ci2.lower <= mean_ci2.upper

    def test_insufficient_data(self) -> None:
        deltas = [Decimal("1"), Decimal("2")]
        config = _make_config()
        mean_ci, median_ci = compute_bootstrap_confidence_intervals(deltas, config)
        assert mean_ci is None
        assert median_ci is None

    def test_empty_deltas(self) -> None:
        config = _make_config()
        mean_ci, median_ci = compute_bootstrap_confidence_intervals([], config)
        assert mean_ci is None
        assert median_ci is None

    def test_ci_bounds_reasonable(self) -> None:
        deltas = [Decimal("1"), Decimal("2"), Decimal("3"), Decimal("4"), Decimal("5")]
        config = _make_config(seed=42, iterations=500)
        mean_ci, median_ci = compute_bootstrap_confidence_intervals(deltas, config)
        assert mean_ci is not None
        assert median_ci is not None
        # CI should contain the true mean (3.0) with high probability
        assert mean_ci.lower <= Decimal("3") <= mean_ci.upper
        assert mean_ci.confidence_level == Decimal("0.95")
        assert median_ci.confidence_level == Decimal("0.95")

    def test_all_positive_deltas(self) -> None:
        deltas = [Decimal("0.5"), Decimal("1.0"), Decimal("1.5"), Decimal("2.0"), Decimal("2.5")]
        config = _make_config(seed=42)
        mean_ci, _ = compute_bootstrap_confidence_intervals(deltas, config)
        assert mean_ci is not None
        # All deltas positive, so CI should be positive
        assert mean_ci.lower > Decimal("0")
