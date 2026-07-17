"""Tests for evidence ledger drift detection (MVP-68)."""

from __future__ import annotations

import pytest

from hunter.research_evidence_ledger.drift import DriftDetector
from hunter.research_evidence_ledger.models import (
    DRIFT_DETECTED,
    DRIFT_IN_STRATEGY,
    DRIFT_IN_TIMEFRAME,
    DRIFT_IN_UNIVERSE_PLAN,
    DRIFT_IN_WALK_FORWARD_PLAN,
    EvidenceLedgerDriftError,
    ExperimentRegistration,
    IndependenceClass,
)


def _make_reg(
    experiment_id: str,
    strategy_name: str = "strat_a",
    universe_plan: str = "top_100",
    timeframe: str = "1h",
    walk_forward_plan_fingerprint: str = "wf_fp_1",
    metric_family: tuple[str, ...] = ("sharpe_ratio",),
    confidence_config_fingerprint: str = "cc_fp_1",
    regime_policy: str = "all_regimes",
    direction_policy: str = "candidate_higher",
    experiment_family_id: str = "ef_001",
    hypothesis: str = "test",
) -> ExperimentRegistration:
    return ExperimentRegistration(
        experiment_id=experiment_id,
        hypothesis=hypothesis,
        strategy_name=strategy_name,
        universe_plan=universe_plan,
        timeframe=timeframe,
        walk_forward_plan_fingerprint=walk_forward_plan_fingerprint,
        metric_family=metric_family,
        independence=IndependenceClass.INDEPENDENT,
        experiment_family_id=experiment_family_id,
        confidence_config_fingerprint=confidence_config_fingerprint,
        regime_policy=regime_policy,
        direction_policy=direction_policy,
    )


class TestDriftDetector:
    def test_no_drift_on_first_registration(self) -> None:
        detector = DriftDetector()
        reg = _make_reg("exp_001")
        detector.check_drift(reg)
        detector.set_baseline(reg)

    def test_no_drift_on_identical_registration(self) -> None:
        detector = DriftDetector()
        reg1 = _make_reg("exp_001")
        detector.check_drift(reg1)
        detector.set_baseline(reg1)

        reg2 = _make_reg("exp_002")
        detector.check_drift(reg2)
        detector.set_baseline(reg2)

    def test_drift_in_strategy_detected(self) -> None:
        detector = DriftDetector()
        reg1 = _make_reg("exp_001")
        detector.check_drift(reg1)
        detector.set_baseline(reg1)

        reg2 = _make_reg("exp_002", strategy_name="strat_b")
        with pytest.raises(EvidenceLedgerDriftError) as exc:
            detector.check_drift(reg2)
        assert exc.value.reason_code == DRIFT_DETECTED

    def test_drift_in_universe_plan_detected(self) -> None:
        detector = DriftDetector()
        reg1 = _make_reg("exp_001")
        detector.check_drift(reg1)
        detector.set_baseline(reg1)

        reg2 = _make_reg("exp_002", universe_plan="top_50")
        with pytest.raises(EvidenceLedgerDriftError):
            detector.check_drift(reg2)

    def test_drift_in_timeframe_detected(self) -> None:
        detector = DriftDetector()
        reg1 = _make_reg("exp_001")
        detector.check_drift(reg1)
        detector.set_baseline(reg1)

        reg2 = _make_reg("exp_002", timeframe="4h")
        with pytest.raises(EvidenceLedgerDriftError):
            detector.check_drift(reg2)

    def test_drift_in_walk_forward_plan_detected(self) -> None:
        detector = DriftDetector()
        reg1 = _make_reg("exp_001")
        detector.check_drift(reg1)
        detector.set_baseline(reg1)

        reg2 = _make_reg("exp_002", walk_forward_plan_fingerprint="wf_fp_2")
        with pytest.raises(EvidenceLedgerDriftError):
            detector.check_drift(reg2)

    def test_drift_in_metric_family_detected(self) -> None:
        detector = DriftDetector()
        reg1 = _make_reg("exp_001")
        detector.check_drift(reg1)
        detector.set_baseline(reg1)

        reg2 = _make_reg("exp_002", metric_family=("sortino_ratio",))
        with pytest.raises(EvidenceLedgerDriftError):
            detector.check_drift(reg2)

    def test_different_family_key_no_drift(self) -> None:
        detector = DriftDetector()
        reg1 = _make_reg("exp_001", experiment_family_id="ef_001")
        detector.check_drift(reg1)
        detector.set_baseline(reg1)

        # Different family
        reg2 = _make_reg("exp_002", experiment_family_id="ef_002")
        # No drift since it's a different family
        detector.check_drift(reg2)
        detector.set_baseline(reg2)

    def test_set_baseline_twice_same_family(self) -> None:
        detector = DriftDetector()
        reg1 = _make_reg("exp_001")
        detector.set_baseline(reg1)

        reg2 = _make_reg("exp_002")
        detector.set_baseline(reg2)  # Second set_baseline should be a no-op
        # Check drift against reg1's baseline
        with pytest.raises(EvidenceLedgerDriftError):
            detector.check_drift(_make_reg("exp_003", strategy_name="strat_b"))
