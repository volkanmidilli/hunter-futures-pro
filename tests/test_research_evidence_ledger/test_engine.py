"""Tests for evidence ledger engine (MVP-68)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from hunter.research_evidence_ledger.engine import EvidenceLedgerEngine
from hunter.research_evidence_ledger.models import (
    AdjustmentConfig,
    AdjustmentMethod,
    EvidenceLedgerSafetyFlags,
    ExperimentRegistration,
    ExperimentStatus,
    IndependenceClass,
)
from hunter.research_evidence_ledger.errors import (
    EvidenceLedgerDuplicateError,
    EvidenceLedgerDriftError,
    EvidenceLedgerSnapshotError,
    EvidenceLedgerSafetyError,
)


def _make_reg(
    experiment_id: str = "exp_001",
    hypothesis: str = "test hypothesis",
    independence: IndependenceClass = IndependenceClass.INDEPENDENT,
    metric_family: tuple[str, ...] = ("sharpe_ratio",),
    strategy_name: str = "strat_a",
    universe_plan: str = "top_100",
    timeframe: str = "1h",
    walk_forward_plan_fingerprint: str = "wf_fp_1",
) -> ExperimentRegistration:
    return ExperimentRegistration(
        experiment_id=experiment_id,
        hypothesis=hypothesis,
        strategy_name=strategy_name,
        universe_plan=universe_plan,
        timeframe=timeframe,
        walk_forward_plan_fingerprint=walk_forward_plan_fingerprint,
        metric_family=metric_family,
        independence=independence,
        experiment_family_id="ef_001",
    )


class TestEvidenceLedgerEngine:
    def test_init(self) -> None:
        engine = EvidenceLedgerEngine()
        assert engine.safety_flags.research_only is True

    def test_init_with_custom_safety(self) -> None:
        engine = EvidenceLedgerEngine(EvidenceLedgerSafetyFlags())
        assert engine.safety_flags is not None

    def test_register_experiment(self) -> None:
        engine = EvidenceLedgerEngine()
        reg = _make_reg()
        result = engine.register_experiment(reg)
        assert result.fingerprint != ""
        assert result.experiment_id == "exp_001"

    def test_duplicate_id_rejected(self) -> None:
        engine = EvidenceLedgerEngine()
        reg1 = _make_reg("exp_001")
        engine.register_experiment(reg1)
        reg2 = _make_reg("exp_001")
        with pytest.raises(EvidenceLedgerDuplicateError):
            engine.register_experiment(reg2)

    def test_drift_detected(self) -> None:
        engine = EvidenceLedgerEngine()
        reg1 = _make_reg("exp_001", hypothesis="Hypothesis A", strategy_name="strat_a")
        engine.register_experiment(reg1)
        reg2 = _make_reg("exp_002", hypothesis="Hypothesis B", strategy_name="strat_b")
        # Drift because same family but different strategy
        with pytest.raises(EvidenceLedgerDriftError):
            engine.register_experiment(reg2)

    def test_ingest_evidence_unregistered_rejected(self) -> None:
        engine = EvidenceLedgerEngine()
        with pytest.raises(EvidenceLedgerSnapshotError):
            engine.ingest_evidence(experiment_id="unknown")

    def test_ingest_evidence_registered(self) -> None:
        engine = EvidenceLedgerEngine()
        reg = _make_reg("exp_001")
        engine.register_experiment(reg)
        ev = engine.ingest_evidence(experiment_id="exp_001")
        assert ev.experiment_id == "exp_001"
        assert ev.walk_forward_report is None
        assert ev.confidence_report is None

    def test_build_entry(self) -> None:
        engine = EvidenceLedgerEngine()
        reg = _make_reg("exp_001")
        engine.register_experiment(reg)
        entry = engine.build_entry("exp_001")
        assert entry.registration.experiment_id == "exp_001"
        assert entry.status == ExperimentStatus.REGISTERED
        assert entry.fingerprint != ""

    def test_build_entry_unregistered_rejected(self) -> None:
        engine = EvidenceLedgerEngine()
        with pytest.raises(EvidenceLedgerSnapshotError):
            engine.build_entry("unknown")

    def test_build_all_entries(self) -> None:
        engine = EvidenceLedgerEngine()
        engine.register_experiment(_make_reg("exp_001"))
        engine.register_experiment(_make_reg("exp_002", hypothesis="different hypothesis"))
        entries = engine.build_all_entries()
        assert len(entries) == 2

    def test_build_families(self) -> None:
        engine = EvidenceLedgerEngine()
        engine.register_experiment(_make_reg("exp_001"))
        engine.register_experiment(_make_reg("exp_002", hypothesis="different hypothesis"))
        engine.build_all_entries()
        engine.build_families()
        # After build_families, we can access by checking engine internals
        # The families are stored internally
        assert engine._hypothesis_families is not None

    def test_take_snapshot(self) -> None:
        engine = EvidenceLedgerEngine()
        reg = _make_reg("exp_001")
        engine.register_experiment(reg)
        engine.build_entry("exp_001")
        snap = engine.take_snapshot()
        assert snap.snapshot_id.startswith("snap_")
        assert snap.fingerprint != ""

    def test_build_report(self) -> None:
        engine = EvidenceLedgerEngine()
        reg = _make_reg("exp_001")
        engine.register_experiment(reg)
        engine.build_entry("exp_001")
        engine.build_families()
        report = engine.build_report()
        assert report.fingerprint != ""
        assert len(report.registrations) == 1
        assert report.research_only is True
        assert report.human_approval_required is True
