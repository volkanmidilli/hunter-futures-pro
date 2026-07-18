"""Tests for evidence ledger engine (MVP-68)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from hunter.research_evidence_ledger.engine import EvidenceLedgerEngine
from hunter.research_evidence_ledger.models import (
    AdjustmentConfig,
    AdjustmentMethod,
    DUPLICATE_EVIDENCE,
    EvidenceLedgerSafetyFlags,
    ExperimentRegistration,
    ExperimentStatus,
    IndependenceClass,
    MISSING_REGISTRATION,
    POST_REGISTRATION_MUTATION,
    RESULT_BEFORE_REGISTRATION,
)
from hunter.research_evidence_ledger.errors import (
    EvidenceLedgerDuplicateError,
    EvidenceLedgerDriftError,
    EvidenceLedgerSnapshotError,
    EvidenceLedgerSafetyError,
)
from hunter.research_walk_forward.models import (
    MarketRegimeLabel,
    WalkForwardCommonConfig,
    WalkForwardExperimentPlan,
    WalkForwardExperimentReport,
    WalkForwardManifest,
    WalkForwardMode,
    WalkForwardSafetyFlags,
    WalkForwardWindow,
)


def _make_walk_forward_report(
    fingerprint: str = "wf_report_fp_001",
    generated_at: datetime | None = None,
) -> WalkForwardExperimentReport:
    """Return a minimal valid WalkForwardExperimentReport for engine tests."""
    now = generated_at or datetime.now(timezone.utc)
    window = WalkForwardWindow(
        selection_start="2024-01-01",
        selection_end="2024-06-01",
        evaluation_start="2024-06-01",
        evaluation_end="2024-12-01",
        regime_label=MarketRegimeLabel.UNKNOWN,
    )
    common = WalkForwardCommonConfig(
        strategy_name="test_strategy",
        strategy_path="/tmp/strategies/test",
        data_path="/tmp/data/ohlcv_1h",
        timeframe="1h",
        balance=Decimal("10000"),
        stake=Decimal("100"),
        max_open_trades=5,
        fee=Decimal("0.001"),
        executable_path="/usr/bin/freqtrade",
    )
    plan = WalkForwardExperimentPlan(
        mode=WalkForwardMode.ROLLING,
        windows=(window,),
        common=common,
        contiguous=False,
        safety_flags=WalkForwardSafetyFlags(),
        fingerprint="wf_plan_fp_001",
    )
    manifest = WalkForwardManifest(
        version="0.66.0-dev",
        spec_version="SPEC-067",
        walk_forward_version="0.66.0-dev",
        generated_at=now,
        plan_fingerprint="wf_plan_fp_001",
        overall_aggregate_fingerprint="overall_fp_001",
        regime_aggregate_fingerprint="regime_fp_001",
        safety_flags=WalkForwardSafetyFlags(),
    )
    return WalkForwardExperimentReport(
        version="0.66.0-dev",
        spec_version="SPEC-067",
        walk_forward_version="0.66.0-dev",
        plan=plan,
        window_results=(),
        metric_aggregates={},
        regime_aggregates=(),
        manifest=manifest,
        safety_flags=WalkForwardSafetyFlags(),
        fingerprint=fingerprint,
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
    registered_at: datetime | None = None,
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
        registered_at=registered_at or datetime.now(timezone.utc),
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

    def test_ingest_unregistered_returns_missing_reason_code(self) -> None:
        engine = EvidenceLedgerEngine()
        with pytest.raises(EvidenceLedgerSnapshotError) as exc_info:
            engine.ingest_evidence(experiment_id="unknown")
        assert exc_info.value.reason_code == MISSING_REGISTRATION

    def test_result_before_registration_rejected(self) -> None:
        engine = EvidenceLedgerEngine()
        now = datetime.now(timezone.utc)
        reg = _make_reg("exp_001", registered_at=now + timedelta(hours=1))
        engine.register_experiment(reg)
        report = _make_walk_forward_report(generated_at=now)
        with pytest.raises(EvidenceLedgerSnapshotError) as exc_info:
            engine.ingest_evidence(experiment_id="exp_001", walk_forward_report=report)
        assert exc_info.value.reason_code == RESULT_BEFORE_REGISTRATION
        assert "exp_001" not in engine._evidence

    def test_post_registration_mutation_detected(self) -> None:
        engine = EvidenceLedgerEngine()
        reg = _make_reg("exp_001")
        engine.register_experiment(reg)
        engine.ingest_evidence(experiment_id="exp_001", walk_forward_report=_make_walk_forward_report())
        # Simulate a registration mutation that bypassed the duplicate detector.
        mutated = _make_reg(
            experiment_id="exp_001",
            hypothesis="mutated hypothesis",
        )
        engine._registrations["exp_001"] = mutated
        with pytest.raises(EvidenceLedgerSnapshotError) as exc_info:
            engine.build_entry("exp_001")
        assert exc_info.value.reason_code == POST_REGISTRATION_MUTATION

    def test_duplicate_walk_forward_fingerprint_rejected(self) -> None:
        engine = EvidenceLedgerEngine()
        reg1 = _make_reg("exp_001", hypothesis="hypothesis a")
        reg2 = _make_reg("exp_002", hypothesis="hypothesis b")
        engine.register_experiment(reg1)
        engine.register_experiment(reg2)
        report = _make_walk_forward_report(fingerprint="shared_fp")
        engine.ingest_evidence(experiment_id="exp_001", walk_forward_report=report)
        with pytest.raises(EvidenceLedgerDuplicateError) as exc_info:
            engine.ingest_evidence(experiment_id="exp_002", walk_forward_report=report)
        assert exc_info.value.reason_code == DUPLICATE_EVIDENCE
        assert "exp_002" not in engine._evidence
