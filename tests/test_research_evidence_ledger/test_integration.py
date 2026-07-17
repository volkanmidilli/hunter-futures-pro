"""Integration tests for evidence ledger (MVP-68)."""

from __future__ import annotations

import tempfile
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
from hunter.research_evidence_ledger.writer import write_all_evidence_ledger_artifacts
from hunter.research_evidence_ledger.errors import (
    EvidenceLedgerDuplicateError,
    EvidenceLedgerDriftError,
)


class TestIntegration:
    def test_full_pipeline(self) -> None:
        """Test a complete pipeline: register, ingest, adjust, report, write."""
        engine = EvidenceLedgerEngine()

        # Register experiments
        reg1 = ExperimentRegistration(
            experiment_id="exp_001",
            hypothesis="Alpha strategy outperforms",
            strategy_name="alpha_strat",
            universe_plan="top_50",
            timeframe="1h",
            walk_forward_plan_fingerprint="wf_fp_1",
            metric_family=("sharpe_ratio", "sortino_ratio"),
            independence=IndependenceClass.INDEPENDENT,
            experiment_family_id="ef_alpha",
        )
        reg2 = ExperimentRegistration(
            experiment_id="exp_002",
            hypothesis="Beta strategy outperforms",
            strategy_name="beta_strat",
            universe_plan="top_50",
            timeframe="1h",
            walk_forward_plan_fingerprint="wf_fp_2",
            metric_family=("sharpe_ratio", "sortino_ratio"),
            independence=IndependenceClass.INDEPENDENT,
            experiment_family_id="ef_beta",
        )

        engine.register_experiment(reg1)
        engine.register_experiment(reg2)

        # Ingest evidence (empty - no actual WF reports in unit test)
        engine.ingest_evidence("exp_001")
        engine.ingest_evidence("exp_002")

        # Build entries
        engine.build_all_entries()

        # Build families
        engine.build_families()

        # Apply adjustment
        config = AdjustmentConfig(
            method=AdjustmentMethod.BENJAMINI_HOCHBERG,
            alpha=Decimal("0.05"),
            family_id="fam_001",
            family_type="hypothesis",
        )
        raw_values = [
            ("exp_001", "sharpe_ratio", Decimal("0.03")),
            ("exp_002", "sharpe_ratio", Decimal("0.01")),
        ]
        adjustments = engine.apply_adjustment(config, raw_values)
        assert len(adjustments) == 2

        # Take snapshot
        snapshot = engine.take_snapshot()
        assert snapshot.fingerprint != ""

        # Build report
        report = engine.build_report()
        assert report.fingerprint != ""
        assert len(report.registrations) == 2
        assert len(report.adjustments) == 2

        # Write artifacts
        with tempfile.TemporaryDirectory() as tmp:
            paths = write_all_evidence_ledger_artifacts(report, tmp)
            assert len(paths) > 0

    def test_duplicate_detection_in_pipeline(self) -> None:
        engine = EvidenceLedgerEngine()
        reg1 = ExperimentRegistration(
            experiment_id="exp_001",
            hypothesis="Test",
            strategy_name="s1",
            universe_plan="u1",
            timeframe="1h",
            walk_forward_plan_fingerprint="fp",
            metric_family=("m1",),
            independence=IndependenceClass.INDEPENDENT,
            experiment_family_id="ef_001",
        )
        engine.register_experiment(reg1)

        # Same ID should be rejected
        reg2 = ExperimentRegistration(
            experiment_id="exp_001",  # Duplicate ID
            hypothesis="Different",
            strategy_name="s1",
            universe_plan="u1",
            timeframe="1h",
            walk_forward_plan_fingerprint="fp",
            metric_family=("m1",),
            independence=IndependenceClass.INDEPENDENT,
            experiment_family_id="ef_001",
        )
        with pytest.raises(EvidenceLedgerDuplicateError):
            engine.register_experiment(reg2)

    def test_drift_detection_in_pipeline(self) -> None:
        engine = EvidenceLedgerEngine()
        reg1 = ExperimentRegistration(
            experiment_id="exp_001",
            hypothesis="Test",
            strategy_name="s1",
            universe_plan="u1",
            timeframe="1h",
            walk_forward_plan_fingerprint="fp",
            metric_family=("m1",),
            independence=IndependenceClass.INDEPENDENT,
            experiment_family_id="ef_001",
        )
        engine.register_experiment(reg1)

        # Different strategy in same family should trigger drift
        reg2 = ExperimentRegistration(
            experiment_id="exp_002",
            hypothesis="Test 2",
            strategy_name="s2",  # Different strategy
            universe_plan="u1",
            timeframe="1h",
            walk_forward_plan_fingerprint="fp",
            metric_family=("m1",),
            independence=IndependenceClass.INDEPENDENT,
            experiment_family_id="ef_001",
        )
        with pytest.raises(EvidenceLedgerDriftError):
            engine.register_experiment(reg2)

    def test_safety_flags_enforced(self) -> None:
        with pytest.raises(ValueError):
            EvidenceLedgerSafetyFlags(research_only=False)

    def test_deterministic_report_same_inputs(self) -> None:
        def _build_report():
            engine = EvidenceLedgerEngine()
            reg = ExperimentRegistration(
                experiment_id="exp_001",
                hypothesis="Test",
                strategy_name="s1",
                universe_plan="u1",
                timeframe="1h",
                walk_forward_plan_fingerprint="fp",
                metric_family=("m1",),
                independence=IndependenceClass.INDEPENDENT,
                experiment_family_id="ef_001",
            )
            engine.register_experiment(reg)
            engine.ingest_evidence("exp_001")
            engine.build_all_entries()
            engine.build_families()
            return engine.build_report()

        report1 = _build_report()
        report2 = _build_report()
        assert report1.fingerprint == report2.fingerprint
