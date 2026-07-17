"""Tests for evidence ledger registration (MVP-68)."""

from __future__ import annotations

import pytest

from hunter.research_evidence_ledger.models import (
    EvidenceLedgerSafetyFlags,
    ExperimentRegistration,
    ExperimentStatus,
    IndependenceClass,
)
from hunter.research_evidence_ledger.registration import (
    create_registration,
    update_registration_status,
)


class TestCreateRegistration:
    def test_basic(self) -> None:
        reg = create_registration(
            experiment_id="exp_001",
            hypothesis="Strategy X outperforms",
            strategy_name="strategy_x",
            universe_plan="top_100",
            timeframe="1h",
            walk_forward_plan_fingerprint="wf_fp_123",
            metric_family=("sharpe_ratio",),
            independence=IndependenceClass.INDEPENDENT,
        )
        assert reg.experiment_id == "exp_001"
        assert reg.status == ExperimentStatus.REGISTERED
        assert isinstance(reg.fingerprint, str) and len(reg.fingerprint) > 0
        assert reg.safety_flags.research_only is True

    def test_with_explicit_safety_flags(self) -> None:
        flags = EvidenceLedgerSafetyFlags()
        reg = create_registration(
            experiment_id="exp_002",
            hypothesis="Test hypothesis",
            strategy_name="s1",
            universe_plan="u1",
            timeframe="1h",
            walk_forward_plan_fingerprint="fp",
            metric_family=("m1",),
            independence=IndependenceClass.INDEPENDENT,
            safety_flags=flags,
        )
        assert reg.safety_flags is flags

    def test_with_family_ids(self) -> None:
        reg = create_registration(
            experiment_id="exp_003",
            hypothesis="Test",
            strategy_name="s1",
            universe_plan="u1",
            timeframe="1h",
            walk_forward_plan_fingerprint="fp",
            metric_family=("m1",),
            independence=IndependenceClass.INDEPENDENT,
            hypothesis_family_id="hf_001",
            experiment_family_id="ef_001",
        )
        assert reg.hypothesis_family_id == "hf_001"
        assert reg.experiment_family_id == "ef_001"

    def test_deterministic_fingerprint(self) -> None:
        reg1 = create_registration(
            experiment_id="exp_det",
            hypothesis="Same hypothesis",
            strategy_name="s1",
            universe_plan="u1",
            timeframe="1h",
            walk_forward_plan_fingerprint="fp",
            metric_family=("m1",),
            independence=IndependenceClass.INDEPENDENT,
        )
        reg2 = create_registration(
            experiment_id="exp_det",
            hypothesis="Same hypothesis",
            strategy_name="s1",
            universe_plan="u1",
            timeframe="1h",
            walk_forward_plan_fingerprint="fp",
            metric_family=("m1",),
            independence=IndependenceClass.INDEPENDENT,
        )
        assert reg1.fingerprint == reg2.fingerprint

    def test_invalid_registration_rejected(self) -> None:
        with pytest.raises(Exception):
            create_registration(
                experiment_id="",
                hypothesis="test",
                strategy_name="s1",
                universe_plan="u1",
                timeframe="1h",
                walk_forward_plan_fingerprint="fp",
                metric_family=("m1",),
                independence=IndependenceClass.INDEPENDENT,
            )


class TestUpdateRegistrationStatus:
    def test_update(self) -> None:
        reg = create_registration(
            experiment_id="exp_upd",
            hypothesis="Test",
            strategy_name="s1",
            universe_plan="u1",
            timeframe="1h",
            walk_forward_plan_fingerprint="fp",
            metric_family=("m1",),
            independence=IndependenceClass.INDEPENDENT,
        )
        original_fp = reg.fingerprint
        updated = update_registration_status(reg, ExperimentStatus.COMPLETED)
        assert updated.status == ExperimentStatus.COMPLETED
        assert updated.experiment_id == reg.experiment_id
        # Fingerprint should differ due to status change
        assert updated.fingerprint != original_fp

    def test_immutability_preserved(self) -> None:
        reg = create_registration(
            experiment_id="exp_imm",
            hypothesis="Test",
            strategy_name="s1",
            universe_plan="u1",
            timeframe="1h",
            walk_forward_plan_fingerprint="fp",
            metric_family=("m1",),
            independence=IndependenceClass.INDEPENDENT,
        )
        update_registration_status(reg, ExperimentStatus.COMPLETED)
        # Original should be unchanged
        assert reg.status == ExperimentStatus.REGISTERED
