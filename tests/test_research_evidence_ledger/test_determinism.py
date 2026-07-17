"""Determinism tests for evidence ledger (MVP-68).

Verifies that fingerprints are deterministic across runs with the same inputs,
and that excluded fields (notes, timestamps, etc.) do not affect fingerprints.
"""

from __future__ import annotations

from decimal import Decimal

from hunter.research_evidence_ledger.fingerprint import (
    adjusted_evidence_fingerprint,
    evidence_fingerprint,
    experiment_family_fingerprint,
    hypothesis_family_fingerprint,
    metric_family_fingerprint,
    registration_fingerprint,
    replication_fingerprint,
    snapshot_fingerprint,
)
from hunter.research_evidence_ledger.models import (
    AdjustedEvidence,
    AdjustmentMethod,
    ExperimentEvidence,
    ExperimentFamily,
    ExperimentRegistration,
    HypothesisFamily,
    IndependenceClass,
    LedgerSnapshot,
    MetricFamily,
    ReplicationResult,
    ReplicationState,
)
from hunter.research_walk_forward.models import MetricDirection


class TestDeterministicFingerprints:
    def test_registration_excludes_notes(self) -> None:
        reg1 = ExperimentRegistration(
            experiment_id="e1",
            hypothesis="test",
            strategy_name="s1",
            universe_plan="u1",
            timeframe="1h",
            walk_forward_plan_fingerprint="fp",
            metric_family=("m1",),
            independence=IndependenceClass.INDEPENDENT,
            notes="abc",
        )
        reg2 = ExperimentRegistration(
            experiment_id="e1",
            hypothesis="test",
            strategy_name="s1",
            universe_plan="u1",
            timeframe="1h",
            walk_forward_plan_fingerprint="fp",
            metric_family=("m1",),
            independence=IndependenceClass.INDEPENDENT,
            notes="xyz",
        )
        assert registration_fingerprint(reg1) == registration_fingerprint(reg2)

    def test_registration_deterministic_order(self) -> None:
        reg1 = ExperimentRegistration(
            experiment_id="e1",
            hypothesis="test",
            strategy_name="s1",
            universe_plan="u1",
            timeframe="1h",
            walk_forward_plan_fingerprint="fp",
            metric_family=("m1", "m2"),
            independence=IndependenceClass.INDEPENDENT,
        )
        reg2 = ExperimentRegistration(
            experiment_id="e1",
            hypothesis="test",
            strategy_name="s1",
            universe_plan="u1",
            timeframe="1h",
            walk_forward_plan_fingerprint="fp",
            metric_family=("m2", "m1"),  # Different order
            independence=IndependenceClass.INDEPENDENT,
        )
        # metric_family is sorted during __post_init__, so order doesn't matter
        assert registration_fingerprint(reg1) == registration_fingerprint(reg2)

    def test_evidence_fingerprint_excludes_none(self) -> None:
        ev1 = ExperimentEvidence(experiment_id="e1")
        ev2 = ExperimentEvidence(experiment_id="e1")
        assert evidence_fingerprint(ev1) == evidence_fingerprint(ev2)

    def test_hypothesis_family_sorted_experiments(self) -> None:
        f1 = HypothesisFamily(
            hypothesis_family_id="hf_001",
            hypothesis="test",
            experiment_ids=("e2", "e1"),
            metric_names=("m1",),
        )
        f2 = HypothesisFamily(
            hypothesis_family_id="hf_001",
            hypothesis="test",
            experiment_ids=("e1", "e2"),
            metric_names=("m1",),
        )
        # Fingerprint uses sorted experiment_ids
        assert hypothesis_family_fingerprint(f1) == hypothesis_family_fingerprint(f2)

    def test_experiment_family_sorted_experiments(self) -> None:
        f1 = ExperimentFamily(
            experiment_family_id="ef_001",
            strategy_name="s1",
            universe_plan="u1",
            timeframe="1h",
            walk_forward_plan_fingerprint="fp",
            experiment_ids=("e2", "e1"),
            metric_names=("m1",),
        )
        f2 = ExperimentFamily(
            experiment_family_id="ef_001",
            strategy_name="s1",
            universe_plan="u1",
            timeframe="1h",
            walk_forward_plan_fingerprint="fp",
            experiment_ids=("e1", "e2"),
            metric_names=("m1",),
        )
        assert experiment_family_fingerprint(f1) == experiment_family_fingerprint(f2)

    def test_metric_family_sorted_names(self) -> None:
        f1 = MetricFamily(metric_names=("m2", "m1"))
        f2 = MetricFamily(metric_names=("m1", "m2"))
        assert metric_family_fingerprint(f1) == metric_family_fingerprint(f2)

    def test_adjusted_evidence_deterministic(self) -> None:
        a1 = AdjustedEvidence(
            experiment_id="e1",
            metric_name="m1",
            raw_value=Decimal("0.03"),
            adjusted_value=Decimal("0.06"),
            family_id="f1",
            family_type="hypothesis",
            method=AdjustmentMethod.BENJAMINI_HOCHBERG,
            rank=1,
            family_size=5,
            alpha=Decimal("0.05"),
        )
        a2 = AdjustedEvidence(
            experiment_id="e1",
            metric_name="m1",
            raw_value=Decimal("0.03"),
            adjusted_value=Decimal("0.06"),
            family_id="f1",
            family_type="hypothesis",
            method=AdjustmentMethod.BENJAMINI_HOCHBERG,
            rank=1,
            family_size=5,
            alpha=Decimal("0.05"),
        )
        assert adjusted_evidence_fingerprint(a1) == adjusted_evidence_fingerprint(a2)

    def test_replication_deterministic(self) -> None:
        r1 = ReplicationResult(
            experiment_id="e1",
            metric_name="m1",
            family_id="f1",
            family_type="hypothesis",
            state=ReplicationState.NOT_REPLICATED,
            candidate_count=0,
            baseline_count=0,
            independent_count=1,
            direction=None,
        )
        r2 = ReplicationResult(
            experiment_id="e1",
            metric_name="m1",
            family_id="f1",
            family_type="hypothesis",
            state=ReplicationState.NOT_REPLICATED,
            candidate_count=0,
            baseline_count=0,
            independent_count=1,
            direction=None,
        )
        assert replication_fingerprint(r1) == replication_fingerprint(r2)

    def test_snapshot_deterministic(self) -> None:
        s1 = LedgerSnapshot(
            version="0.68.0-dev",
            spec_version="SPEC-069",
            snapshot_id="snap_001",
            previous_snapshot_fingerprint="prev",
            entry_fingerprints=("e1", "e2"),
            family_fingerprints=("f1",),
            adjustment_fingerprints=("a1",),
            replication_fingerprints=("r1",),
        )
        s2 = LedgerSnapshot(
            version="0.68.0-dev",
            spec_version="SPEC-069",
            snapshot_id="snap_001",
            previous_snapshot_fingerprint="prev",
            entry_fingerprints=("e2", "e1"),
            family_fingerprints=("f1",),
            adjustment_fingerprints=("a1",),
            replication_fingerprints=("r1",),
        )
        # Snapshot fingerprint uses list() for entry_fingerprints
        fp1 = snapshot_fingerprint(s1)
        fp2 = snapshot_fingerprint(s2)
        # Since we convert tuple to list, order matters for fingerprinting
        # The snapshot fingerprint uses list() preserving input order
        # Different input order produces different fingerprint
        assert fp1 != fp2

    def test_excluded_fields_do_not_affect(self) -> None:
        """Verify that fingerprint, notes, metadata don't affect fingerprints."""
        reg1 = ExperimentRegistration(
            experiment_id="e1",
            hypothesis="test",
            strategy_name="s1",
            universe_plan="u1",
            timeframe="1h",
            walk_forward_plan_fingerprint="fp",
            metric_family=("m1",),
            independence=IndependenceClass.INDEPENDENT,
            fingerprint="fp1",
            notes="note1",
        )
        reg2 = ExperimentRegistration(
            experiment_id="e1",
            hypothesis="test",
            strategy_name="s1",
            universe_plan="u1",
            timeframe="1h",
            walk_forward_plan_fingerprint="fp",
            metric_family=("m1",),
            independence=IndependenceClass.INDEPENDENT,
            fingerprint="fp2",
            notes="note2",
        )
        assert registration_fingerprint(reg1) == registration_fingerprint(reg2)
