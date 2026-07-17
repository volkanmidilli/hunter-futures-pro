"""Tests for multiple-testing adjustment (MVP-68)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from hunter.research_evidence_ledger.adjustment import (
    adjust,
    adjust_benjamini_hochberg,
    adjust_bonferroni,
)
from hunter.research_evidence_ledger.models import (
    AdjustmentConfig,
    AdjustmentMethod,
    EvidenceLedgerAdjustmentError,
)


class TestBenjaminiHochberg:
    def test_single_value(self) -> None:
        config = AdjustmentConfig(
            method=AdjustmentMethod.BENJAMINI_HOCHBERG,
            alpha=Decimal("0.05"),
            family_id="fam_001",
            family_type="hypothesis",
        )
        raw = [("exp_001", "sharpe_ratio", Decimal("0.03"))]
        results = adjust_benjamini_hochberg(raw, config)
        assert len(results) == 1
        assert results[0].raw_value == Decimal("0.03")
        assert results[0].family_size == 1
        assert results[0].rank == 1

    def test_two_values(self) -> None:
        config = AdjustmentConfig(
            method=AdjustmentMethod.BENJAMINI_HOCHBERG,
            alpha=Decimal("0.05"),
            family_id="fam_001",
            family_type="hypothesis",
        )
        raw = [
            ("exp_001", "sharpe_ratio", Decimal("0.01")),
            ("exp_002", "sharpe_ratio", Decimal("0.05")),
        ]
        results = adjust_benjamini_hochberg(raw, config)
        assert len(results) == 2

    def test_tie_handling(self) -> None:
        """Ties are sorted by canonical ID within same raw value."""
        config = AdjustmentConfig(
            method=AdjustmentMethod.BENJAMINI_HOCHBERG,
            alpha=Decimal("0.05"),
            family_id="fam_001",
            family_type="hypothesis",
        )
        raw = [
            ("exp_b", "m1", Decimal("0.03")),
            ("exp_a", "m1", Decimal("0.03")),
        ]
        results = adjust_benjamini_hochberg(raw, config)
        assert len(results) == 2
        # Order should be preserved (original input order)
        assert results[0].experiment_id == "exp_b"
        assert results[1].experiment_id == "exp_a"

    def test_negative_value_rejected(self) -> None:
        config = AdjustmentConfig(
            method=AdjustmentMethod.BENJAMINI_HOCHBERG,
            alpha=Decimal("0.05"),
            family_id="fam_001",
            family_type="hypothesis",
        )
        raw = [("exp_001", "m1", Decimal("-0.01"))]
        with pytest.raises(EvidenceLedgerAdjustmentError):
            adjust_benjamini_hochberg(raw, config)

    def test_value_above_one_rejected(self) -> None:
        config = AdjustmentConfig(
            method=AdjustmentMethod.BENJAMINI_HOCHBERG,
            alpha=Decimal("0.05"),
            family_id="fam_001",
            family_type="hypothesis",
        )
        raw = [("exp_001", "m1", Decimal("1.5"))]
        with pytest.raises(EvidenceLedgerAdjustmentError):
            adjust_benjamini_hochberg(raw, config)

    def test_empty_input(self) -> None:
        config = AdjustmentConfig(
            method=AdjustmentMethod.BENJAMINI_HOCHBERG,
            alpha=Decimal("0.05"),
            family_id="fam_001",
            family_type="hypothesis",
        )
        results = adjust_benjamini_hochberg([], config)
        assert results == []

    def test_fingerprint_present(self) -> None:
        config = AdjustmentConfig(
            method=AdjustmentMethod.BENJAMINI_HOCHBERG,
            alpha=Decimal("0.05"),
            family_id="fam_001",
            family_type="hypothesis",
        )
        raw = [("exp_001", "m1", Decimal("0.03"))]
        results = adjust_benjamini_hochberg(raw, config)
        assert len(results) == 1
        assert isinstance(results[0].fingerprint, str)
        assert len(results[0].fingerprint) > 0

    def test_deterministic(self) -> None:
        config = AdjustmentConfig(
            method=AdjustmentMethod.BENJAMINI_HOCHBERG,
            alpha=Decimal("0.05"),
            family_id="fam_001",
            family_type="hypothesis",
        )
        raw = [
            ("exp_001", "m1", Decimal("0.03")),
            ("exp_002", "m1", Decimal("0.01")),
        ]
        r1 = adjust_benjamini_hochberg(raw, config)
        r2 = adjust_benjamini_hochberg(raw, config)
        for a, b in zip(r1, r2):
            assert a.adjusted_value == b.adjusted_value
            assert a.fingerprint == b.fingerprint

    def test_monotonicity_enforced(self) -> None:
        """Test that monotonicity is enforced from largest rank backward."""
        config = AdjustmentConfig(
            method=AdjustmentMethod.BENJAMINI_HOCHBERG,
            alpha=Decimal("0.05"),
            family_id="fam_001",
            family_type="hypothesis",
        )
        raw = [
            ("exp_001", "m1", Decimal("0.001")),
            ("exp_002", "m1", Decimal("0.01")),
            ("exp_003", "m1", Decimal("0.10")),
        ]
        results = adjust_benjamini_hochberg(raw, config)
        assert len(results) == 3
        # After monotonicity, adjusted values should be non-decreasing
        # (they were sorted ascending by raw, so adj should also be ascending)
        adj_values = [r.adjusted_value for r in results]
        for i in range(1, len(adj_values)):
            assert adj_values[i] >= adj_values[i - 1]


class TestBonferroni:
    def test_single_value(self) -> None:
        config = AdjustmentConfig(
            method=AdjustmentMethod.BONFERRONI,
            alpha=Decimal("0.05"),
            family_id="fam_001",
            family_type="hypothesis",
        )
        raw = [("exp_001", "m1", Decimal("0.03"))]
        results = adjust_bonferroni(raw, config)
        assert len(results) == 1
        assert results[0].adjusted_value == Decimal("0.03")

    def test_two_values(self) -> None:
        config = AdjustmentConfig(
            method=AdjustmentMethod.BONFERRONI,
            alpha=Decimal("0.05"),
            family_id="fam_001",
            family_type="hypothesis",
        )
        raw = [
            ("exp_001", "m1", Decimal("0.01")),
            ("exp_002", "m1", Decimal("0.05")),
        ]
        results = adjust_bonferroni(raw, config)
        assert len(results) == 2

    def test_adjusted_formula(self) -> None:
        config = AdjustmentConfig(
            method=AdjustmentMethod.BONFERRONI,
            alpha=Decimal("0.05"),
            family_id="fam_001",
            family_type="hypothesis",
        )
        # For Bonferroni: adj = min(raw * 2, 1) when 2 values
        raw = [
            ("exp_001", "m1", Decimal("0.01")),
            ("exp_002", "m1", Decimal("0.02")),
        ]
        results = adjust_bonferroni(raw, config)
        assert results[0].adjusted_value == Decimal("0.02")  # 0.01 * 2 = 0.02
        assert results[1].adjusted_value == Decimal("0.04")  # 0.02 * 2 = 0.04

    def test_clamping_to_one(self) -> None:
        config = AdjustmentConfig(
            method=AdjustmentMethod.BONFERRONI,
            alpha=Decimal("0.05"),
            family_id="fam_001",
            family_type="hypothesis",
        )
        raw = [
            ("exp_001", "m1", Decimal("0.6")),
            ("exp_002", "m1", Decimal("0.7")),
        ]
        results = adjust_bonferroni(raw, config)
        assert results[0].adjusted_value == Decimal("1")  # 0.6 * 2 = 1.2 clamped to 1
        assert results[1].adjusted_value == Decimal("1")  # 0.7 * 2 = 1.4 clamped to 1

    def test_empty_input(self) -> None:
        config = AdjustmentConfig(
            method=AdjustmentMethod.BONFERRONI,
            alpha=Decimal("0.05"),
            family_id="fam_001",
            family_type="hypothesis",
        )
        results = adjust_bonferroni([], config)
        assert results == []

    def test_fingerprint_present(self) -> None:
        config = AdjustmentConfig(
            method=AdjustmentMethod.BONFERRONI,
            alpha=Decimal("0.05"),
            family_id="fam_001",
            family_type="hypothesis",
        )
        raw = [("exp_001", "m1", Decimal("0.03"))]
        results = adjust_bonferroni(raw, config)
        assert isinstance(results[0].fingerprint, str)
        assert len(results[0].fingerprint) > 0


class TestAdjust:
    def test_dispatches_to_benjamini_hochberg(self) -> None:
        config = AdjustmentConfig(
            method=AdjustmentMethod.BENJAMINI_HOCHBERG,
            alpha=Decimal("0.05"),
            family_id="fam_001",
            family_type="hypothesis",
        )
        raw = [("exp_001", "m1", Decimal("0.03"))]
        results = adjust(raw, config)
        assert len(results) == 1
        assert results[0].method == AdjustmentMethod.BENJAMINI_HOCHBERG

    def test_dispatches_to_bonferroni(self) -> None:
        config = AdjustmentConfig(
            method=AdjustmentMethod.BONFERRONI,
            alpha=Decimal("0.05"),
            family_id="fam_001",
            family_type="hypothesis",
        )
        raw = [("exp_001", "m1", Decimal("0.03"))]
        results = adjust(raw, config)
        assert len(results) == 1
        assert results[0].method == AdjustmentMethod.BONFERRONI
