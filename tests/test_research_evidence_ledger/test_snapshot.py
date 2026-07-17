"""Tests for snapshot chaining (MVP-68)."""

from __future__ import annotations

import pytest

from hunter.research_evidence_ledger.models import (
    EvidenceLedgerEntry,
    ExperimentRegistration,
    ExperimentStatus,
    IndependenceClass,
    LedgerSnapshot,
)
from hunter.research_evidence_ledger.snapshot import (
    build_snapshot,
    verify_snapshot_chain,
)
from hunter.research_evidence_ledger.errors import EvidenceLedgerSnapshotError


def _make_reg(experiment_id: str = "exp_001") -> ExperimentRegistration:
    return ExperimentRegistration(
        experiment_id=experiment_id,
        hypothesis="test",
        strategy_name="s1",
        universe_plan="u1",
        timeframe="1h",
        walk_forward_plan_fingerprint="fp",
        metric_family=("m1",),
        independence=IndependenceClass.INDEPENDENT,
    )


def _make_entry(reg: ExperimentRegistration) -> EvidenceLedgerEntry:
    return EvidenceLedgerEntry(
        registration=reg,
        evidence=None,
        status=ExperimentStatus.REGISTERED,
    )


class TestBuildSnapshot:
    def test_first_snapshot(self) -> None:
        reg = _make_reg()
        entry = _make_entry(reg)
        snap = build_snapshot(
            entries=(entry,),
            hypothesis_families=(),
            experiment_families=(),
            metric_families=(),
            adjustments=(),
            replications=(),
        )
        assert snap.snapshot_id.startswith("snap_")
        assert snap.previous_snapshot_fingerprint == ""
        assert isinstance(snap.fingerprint, str)
        assert len(snap.fingerprint) > 0

    def test_chained_snapshot(self) -> None:
        reg = _make_reg()
        entry = _make_entry(reg)

        snap1 = build_snapshot(
            entries=(entry,),
            hypothesis_families=(),
            experiment_families=(),
            metric_families=(),
            adjustments=(),
            replications=(),
            snapshot_id="snap_001",
        )

        snap2 = build_snapshot(
            entries=(entry,),
            hypothesis_families=(),
            experiment_families=(),
            metric_families=(),
            adjustments=(),
            replications=(),
            previous_snapshot_fingerprint=snap1.fingerprint,
            snapshot_id="snap_002",
        )
        assert snap2.previous_snapshot_fingerprint == snap1.fingerprint

    def test_deterministic_fingerprint(self) -> None:
        reg = _make_reg()
        entry = _make_entry(reg)

        snap1 = build_snapshot(
            entries=(entry,),
            hypothesis_families=(),
            experiment_families=(),
            metric_families=(),
            adjustments=(),
            replications=(),
        )
        snap2 = build_snapshot(
            entries=(entry,),
            hypothesis_families=(),
            experiment_families=(),
            metric_families=(),
            adjustments=(),
            replications=(),
        )
        # Same inputs should give same snapshot content fingerprint
        assert snap1.fingerprint == snap2.fingerprint

    def test_explicit_snapshot_id(self) -> None:
        snap = build_snapshot(
            entries=(),
            hypothesis_families=(),
            experiment_families=(),
            metric_families=(),
            adjustments=(),
            replications=(),
            snapshot_id="my_custom_snap",
        )
        assert snap.snapshot_id == "my_custom_snap"

    def test_empty_entries(self) -> None:
        snap = build_snapshot(
            entries=(),
            hypothesis_families=(),
            experiment_families=(),
            metric_families=(),
            adjustments=(),
            replications=(),
        )
        assert snap.entry_fingerprints == ()
        assert snap.family_fingerprints == ()


class TestVerifySnapshotChain:
    def test_single_snapshot(self) -> None:
        snap = build_snapshot(
            entries=(),
            hypothesis_families=(),
            experiment_families=(),
            metric_families=(),
            adjustments=(),
            replications=(),
        )
        # Should not raise
        verify_snapshot_chain((snap,))

    def test_valid_chain(self) -> None:
        snap1 = build_snapshot(
            entries=(),
            hypothesis_families=(),
            experiment_families=(),
            metric_families=(),
            adjustments=(),
            replications=(),
            snapshot_id="snap_001",
        )
        snap2 = build_snapshot(
            entries=(),
            hypothesis_families=(),
            experiment_families=(),
            metric_families=(),
            adjustments=(),
            replications=(),
            previous_snapshot_fingerprint=snap1.fingerprint,
            snapshot_id="snap_002",
        )
        # Should not raise
        verify_snapshot_chain((snap1, snap2))

    def test_broken_chain_raises(self) -> None:
        snap1 = build_snapshot(
            entries=(),
            hypothesis_families=(),
            experiment_families=(),
            metric_families=(),
            adjustments=(),
            replications=(),
            snapshot_id="snap_001",
        )
        snap2 = LedgerSnapshot(
            version="0.68.0-dev",
            spec_version="SPEC-069",
            snapshot_id="snap_002",
            previous_snapshot_fingerprint="wrong_fingerprint",
            entry_fingerprints=(),
            family_fingerprints=(),
            adjustment_fingerprints=(),
            replication_fingerprints=(),
        )
        object.__setattr__(snap2, "fingerprint", "some_fp")
        with pytest.raises(EvidenceLedgerSnapshotError):
            verify_snapshot_chain((snap1, snap2))

    def test_first_snapshot_previous_may_be_empty(self) -> None:
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
        object.__setattr__(snap, "fingerprint", "fp")
        # Should not raise
        verify_snapshot_chain((snap,))
