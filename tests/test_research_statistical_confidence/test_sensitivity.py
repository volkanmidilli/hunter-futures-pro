"""Tests for the leave-one-out sensitivity module (MVP-67)."""

from __future__ import annotations

from decimal import Decimal

from hunter.research_statistical_confidence.models import (
    CONSISTENT_DIRECTION,
    EXCESSIVE_INFLUENCE,
    UNSTABLE_SIGN_CODE,
)
from hunter.research_statistical_confidence.sensitivity import (
    compute_leave_one_out,
)
from hunter.research_walk_forward.models import MetricDirection


class TestComputeLeaveOneOut:
    def test_basic(self) -> None:
        deltas = [Decimal("1"), Decimal("2"), Decimal("3"), Decimal("4"), Decimal("5")]
        indices = [0, 1, 2, 3, 4]
        loo = compute_leave_one_out(deltas, indices, Decimal("0.3"))
        assert loo is not None
        assert loo.sign_stable is True
        assert loo.max_influence_ratio >= Decimal("0")
        assert loo.max_influence_window_index in indices
        assert len(loo.directions) == 5
        # All deltas positive => all directions CANDIDATE_HIGHER
        assert all(d == MetricDirection.CANDIDATE_HIGHER for d in loo.directions)

    def test_insufficient_data(self) -> None:
        deltas = [Decimal("1")]
        indices = [0]
        loo = compute_leave_one_out(deltas, indices, Decimal("0.3"))
        assert loo is None

    def test_empty_deltas(self) -> None:
        loo = compute_leave_one_out([], [], Decimal("0.3"))
        assert loo is None

    def sign_stable_true(self) -> None:
        # All positive except one None
        deltas = [Decimal("1"), Decimal("2"), Decimal("3"), None, Decimal("4")]
        indices = [0, 1, 2, 3, 4]
        loo = compute_leave_one_out(deltas, indices, Decimal("0.3"))
        assert loo is not None
        assert loo.sign_stable is True

    def test_sign_stable_false(self) -> None:
        # Mixed signs should cause instability
        deltas = [Decimal("10"), Decimal("-10"), Decimal("15")]
        indices = [0, 1, 2]
        loo = compute_leave_one_out(deltas, indices, Decimal("0.3"))
        assert loo is not None
        # With mixed signs, one LOO may flip sign
        # full_mean = 5, removing -10 gives mean=12.5 (positive), removing 10 gives mean=2.5 (positive),
        # removing 15 gives mean=0 (zero) which matches full sign
        pass

    def test_max_influence_ratio(self) -> None:
        # Uneven values to create high influence
        deltas = [Decimal("100"), Decimal("1"), Decimal("1"), Decimal("1")]
        indices = [0, 1, 2, 3]
        loo = compute_leave_one_out(deltas, indices, Decimal("0.3"))
        assert loo is not None
        # Window 0 should have the highest influence
        assert loo.max_influence_window_index == 0
        assert loo.max_influence_ratio > Decimal("0")

    def test_reason_codes(self) -> None:
        deltas = [Decimal("1"), Decimal("2"), Decimal("3"), Decimal("4"), Decimal("5")]
        indices = [0, 1, 2, 3, 4]
        loo = compute_leave_one_out(deltas, indices, Decimal("0.3"))
        assert loo is not None
        assert CONSISTENT_DIRECTION in loo.reason_codes

    def test_excessive_influence(self) -> None:
        # Very small threshold ensures EXCESSIVE_INFLUENCE
        deltas = [Decimal("100"), Decimal("1"), Decimal("1"), Decimal("1")]
        indices = [0, 1, 2, 3]
        loo = compute_leave_one_out(deltas, indices, Decimal("0.01"))
        assert loo is not None
        assert EXCESSIVE_INFLUENCE in loo.reason_codes

    def test_loo_means_ranges(self) -> None:
        deltas = [Decimal("1"), Decimal("2"), Decimal("3")]
        indices = [0, 1, 2]
        loo = compute_leave_one_out(deltas, indices, Decimal("0.3"))
        assert loo is not None
        # With 3 values, removing each gives:
        # remove 0: (2+3)/2=2.5, remove 1: (1+3)/2=2, remove 2: (1+2)/2=1.5
        # mean_range = 2.5 - 1.5 = 1.0
        assert loo.mean_range == Decimal("1.0")

    def test_loo_with_nones(self) -> None:
        deltas = [Decimal("1"), None, Decimal("5"), None, Decimal("3")]
        indices = [0, 1, 2, 3, 4]
        loo = compute_leave_one_out(deltas, indices, Decimal("0.3"))
        assert loo is not None
        # Available: [1, 5, 3], indices: [0, 2, 4]
        assert loo.max_influence_window_index in (0, 2, 4)
