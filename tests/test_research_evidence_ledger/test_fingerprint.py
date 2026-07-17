"""Tests for deterministic fingerprints (MVP-68)."""

from __future__ import annotations

from decimal import Decimal

from hunter.research_evidence_ledger.fingerprint import (
    adjusted_evidence_fingerprint,
    entry_fingerprint,
    evidence_fingerprint,
    experiment_family_fingerprint,
    hypothesis_family_fingerprint,
    manifest_fingerprint,
    metric_family_fingerprint,
    registration_fingerprint,
    replication_fingerprint,
    report_fingerprint,
    snapshot_fingerprint,
)
from hunter.research_evidence_ledger.models import (
    EVIDENCE_LEDGER_VERSION,
    SPEC_VERSION,
    AdjustedEvidence,
    AdjustmentMethod,
    EvidenceLedgerEntry,
    EvidenceLedgerManifest,
    EvidenceLedgerReport,
    EvidenceLedgerSafetyFlags,
    ExperimentEvidence,
    ExperimentFamily,
    ExperimentRegistration,
    ExperimentStatus,
    HypothesisFamily,
    IndependenceClass,
    LedgerSnapshot,
    MetricFamily,
    ReplicationResult,
    ReplicationState,
)
from hunter.research_walk_forward.models import MetricDirection


class TestRegistrationFingerprint:
    def test_deterministic(self) -> None:
        reg1 = ExperimentRegistration(
            experiment_id="exp_001",
            hypothesis="test",
            strategy_name="s1",
            universe_plan="u1",
            timeframe="1h",
            walk_forward_plan_fingerprint="fp",
            metric_family=("m1", "m2"),
            independence=IndependenceClass.INDEPENDENT,
        )
        reg2 = ExperimentRegistration(
            experiment_id="exp_001",
            hypothesis="test",
            strategy_name="s1",
            universe_plan="u1",
            timeframe="1h",
            walk_forward_plan_fingerprint="fp",
            metric_family=("m1", "m2"),
            independence=IndependenceClass.INDEPENDENT,
        )
        fp1 = registration_fingerprint(reg1)
        fp2 = registration_fingerprint(reg2)
        assert fp1 == fp2
        assert len(fp1) == 64  # SHA-256 hex

    def test_excludes_notes(self) -> None:
        reg1 = ExperimentRegistration(
            experiment_id="exp_001",
            hypothesis="test",
            strategy_name="s1",
            universe_plan="u1",
            timeframe="1h",
            walk_forward_plan_fingerprint="fp",
            metric_family=("m1",),
            independence=IndependenceClass.INDEPENDENT,
            notes="some notes",
        )
        reg2 = ExperimentRegistration(
            experiment_id="exp_001",
            hypothesis="test",
            strategy_name="s1",
            universe_plan="u1",
            timeframe="1h",
            walk_forward_plan_fingerprint="fp",
            metric_family=("m1",),
            independence=IndependenceClass.INDEPENDENT,
            notes="different notes",
        )
        fp1 = registration_fingerprint(reg1)
        fp2 = registration_fingerprint(reg2)
        assert fp1 == fp2  # Notes excluded from fingerprint


class TestEvidenceFingerprint:
    def test_deterministic(self) -> None:
        ev1 = ExperimentEvidence(experiment_id="exp_001")
        ev2 = ExperimentEvidence(experiment_id="exp_001")
        assert evidence_fingerprint(ev1) == evidence_fingerprint(ev2)

    def test_different_ids(self) -> None:
        ev1 = ExperimentEvidence(experiment_id="exp_001")
        ev2 = ExperimentEvidence(experiment_id="exp_002")
        assert evidence_fingerprint(ev1) != evidence_fingerprint(ev2)


class TestEntryFingerprint:
    def test_deterministic(self) -> None:
        reg = ExperimentRegistration(
            experiment_id="exp_001",
            hypothesis="test",
            strategy_name="s1",
            universe_plan="u1",
            timeframe="1h",
            walk_forward_plan_fingerprint="fp",
            metric_family=("m1",),
            independence=IndependenceClass.INDEPENDENT,
            fingerprint="reg_fp",
        )
        e1 = EvidenceLedgerEntry(
            registration=reg, evidence=None, status=ExperimentStatus.REGISTERED, fingerprint=""
        )
        e2 = EvidenceLedgerEntry(
            registration=reg, evidence=None, status=ExperimentStatus.REGISTERED, fingerprint=""
        )
        assert entry_fingerprint(e1) == entry_fingerprint(e2)


class TestHypothesisFamilyFingerprint:
    def test_deterministic(self) -> None:
        f1 = HypothesisFamily(
            hypothesis_family_id="hf_001",
            hypothesis="test",
            experiment_ids=("e1", "e2"),
            metric_names=("m1",),
        )
        f2 = HypothesisFamily(
            hypothesis_family_id="hf_001",
            hypothesis="test",
            experiment_ids=("e2", "e1"),
            metric_names=("m1",),
        )
        assert hypothesis_family_fingerprint(f1) == hypothesis_family_fingerprint(f2)


class TestExperimentFamilyFingerprint:
    def test_deterministic(self) -> None:
        f1 = ExperimentFamily(
            experiment_family_id="ef_001",
            strategy_name="s1",
            universe_plan="u1",
            timeframe="1h",
            walk_forward_plan_fingerprint="fp",
            experiment_ids=("e1", "e2"),
            metric_names=("m1",),
        )
        f2 = ExperimentFamily(
            experiment_family_id="ef_001",
            strategy_name="s1",
            universe_plan="u1",
            timeframe="1h",
            walk_forward_plan_fingerprint="fp",
            experiment_ids=("e2", "e1"),
            metric_names=("m1",),
        )
        assert experiment_family_fingerprint(f1) == experiment_family_fingerprint(f2)


class TestMetricFamilyFingerprint:
    def test_deterministic(self) -> None:
        f1 = MetricFamily(metric_names=("m2", "m1"))
        f2 = MetricFamily(metric_names=("m1", "m2"))
        assert metric_family_fingerprint(f1) == metric_family_fingerprint(f2)


class TestAdjustedEvidenceFingerprint:
    def test_deterministic(self) -> None:
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


class TestReplicationFingerprint:
    def test_deterministic(self) -> None:
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


class TestSnapshotFingerprint:
    def test_deterministic(self) -> None:
        s1 = LedgerSnapshot(
            version="0.68.0-dev",
            spec_version="SPEC-069",
            snapshot_id="snap_001",
            previous_snapshot_fingerprint="prev_fp",
            entry_fingerprints=("e1",),
            family_fingerprints=("f1",),
            adjustment_fingerprints=("a1",),
            replication_fingerprints=("r1",),
        )
        s2 = LedgerSnapshot(
            version="0.68.0-dev",
            spec_version="SPEC-069",
            snapshot_id="snap_001",
            previous_snapshot_fingerprint="prev_fp",
            entry_fingerprints=("e1",),
            family_fingerprints=("f1",),
            adjustment_fingerprints=("a1",),
            replication_fingerprints=("r1",),
        )
        assert snapshot_fingerprint(s1) == snapshot_fingerprint(s2)


class TestManifestFingerprint:
    def test_deterministic(self) -> None:
        from datetime import datetime, timezone
        m1 = EvidenceLedgerManifest(
            version="1.0",
            spec_version="SPEC-069",
            evidence_ledger_version="0.68.0-dev",
            generated_at=datetime.now(timezone.utc),
            entry_count=5,
            family_count=3,
            adjustment_count=2,
            replication_count=2,
            snapshot_fingerprint="snap_fp",
            overall_fingerprint="overall_fp",
            safety_flags=EvidenceLedgerSafetyFlags(),
        )
        m2 = EvidenceLedgerManifest(
            version="1.0",
            spec_version="SPEC-069",
            evidence_ledger_version="0.68.0-dev",
            generated_at=datetime.now(timezone.utc),
            entry_count=5,
            family_count=3,
            adjustment_count=2,
            replication_count=2,
            snapshot_fingerprint="snap_fp",
            overall_fingerprint="overall_fp",
            safety_flags=EvidenceLedgerSafetyFlags(),
        )
        # Note: manifest_fingerprint excludes generated_at
        assert manifest_fingerprint(m1) == manifest_fingerprint(m2)


class TestReportFingerprint:
    def test_deterministic(self) -> None:
        from datetime import datetime, timezone

        flags = EvidenceLedgerSafetyFlags()
        reg = ExperimentRegistration(
            experiment_id="e1",
            hypothesis="test",
            strategy_name="s1",
            universe_plan="u1",
            timeframe="1h",
            walk_forward_plan_fingerprint="fp",
            metric_family=("m1",),
            independence=IndependenceClass.INDEPENDENT,
        )
        snap = LedgerSnapshot(
            version="0.68.0-dev",
            spec_version="SPEC-069",
            snapshot_id="snap_001",
            previous_snapshot_fingerprint="",
            entry_fingerprints=(),
            family_fingerprints=(),
            adjustment_fingerprints=(),
            replication_fingerprints=(),
        )
        object.__setattr__(snap, "fingerprint", "snap_fp")
        manifest = EvidenceLedgerManifest(
            version="1.0",
            spec_version="SPEC-069",
            evidence_ledger_version="0.68.0-dev",
            generated_at=datetime.now(timezone.utc),
            entry_count=0,
            family_count=0,
            adjustment_count=0,
            replication_count=0,
            snapshot_fingerprint="snap_fp",
            overall_fingerprint="overall_fp",
            safety_flags=flags,
        )
        r1 = EvidenceLedgerReport(
            version="1.0",
            spec_version="SPEC-069",
            evidence_ledger_version="0.68.0-dev",
            registrations=(reg,),
            entries=(),
            hypothesis_families=(),
            experiment_families=(),
            metric_families=(),
            adjustments=(),
            replications=(),
            snapshot=snap,
            manifest=manifest,
            safety_flags=flags,
            fingerprint="fp",
        )
        r2 = EvidenceLedgerReport(
            version="1.0",
            spec_version="SPEC-069",
            evidence_ledger_version="0.68.0-dev",
            registrations=(reg,),
            entries=(),
            hypothesis_families=(),
            experiment_families=(),
            metric_families=(),
            adjustments=(),
            replications=(),
            snapshot=snap,
            manifest=manifest,
            safety_flags=flags,
            fingerprint="fp",
        )
        fp1 = report_fingerprint(r1)
        fp2 = report_fingerprint(r2)
        assert fp1 == fp2
