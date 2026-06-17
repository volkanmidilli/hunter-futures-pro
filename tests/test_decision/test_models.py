"""Tests for decision layer models."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from hunter.decision.models import (
    DecisionAction,
    DecisionConfig,
    DecisionInputRefs,
    DecisionOutput,
    DecisionState,
)
from hunter.market_state.models import (
    AllowedMode,
    DataQuality,
    OutputStatus,
    RegimeState,
    RiskState,
)


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------

class TestEnums:
    def test_decision_state_values(self) -> None:
        assert DecisionState.ALLOW == "ALLOW"
        assert DecisionState.BLOCK == "BLOCK"
        assert DecisionState.REVIEW == "REVIEW"
        assert DecisionState.UNKNOWN == "UNKNOWN"

    def test_decision_action_values(self) -> None:
        assert DecisionAction.ENABLE_LONG_ONLY_RESEARCH == "ENABLE_LONG_ONLY_RESEARCH"
        assert DecisionAction.ENABLE_SHORT_ONLY_RESEARCH == "ENABLE_SHORT_ONLY_RESEARCH"
        assert DecisionAction.BLOCK_ALL == "BLOCK_ALL"
        assert DecisionAction.MANUAL_REVIEW == "MANUAL_REVIEW"


# ---------------------------------------------------------------------------
# DecisionConfig tests
# ---------------------------------------------------------------------------

class TestDecisionConfig:
    def test_default_values(self) -> None:
        config = DecisionConfig()
        assert config.min_regime_confidence == 0.60
        assert config.min_breadth_score_for_long == 60
        assert config.max_breadth_score_for_short == 40
        assert config.stale_input_minutes == 120
        assert config.transition_action == DecisionAction.BLOCK_ALL
        assert config.conflict_action == DecisionAction.BLOCK_ALL

    def test_custom_values(self) -> None:
        config = DecisionConfig(
            min_regime_confidence=0.75,
            min_breadth_score_for_long=70,
            max_breadth_score_for_short=30,
            stale_input_minutes=60,
            transition_action=DecisionAction.MANUAL_REVIEW,
            conflict_action=DecisionAction.MANUAL_REVIEW,
        )
        assert config.min_regime_confidence == 0.75
        assert config.min_breadth_score_for_long == 70
        assert config.max_breadth_score_for_short == 30
        assert config.stale_input_minutes == 60
        assert config.transition_action == DecisionAction.MANUAL_REVIEW
        assert config.conflict_action == DecisionAction.MANUAL_REVIEW

    def test_min_regime_confidence_at_boundaries(self) -> None:
        # 0.0 is valid
        DecisionConfig(min_regime_confidence=0.0)
        # 1.0 is valid
        DecisionConfig(min_regime_confidence=1.0)

    def test_min_regime_confidence_above_1_fails(self) -> None:
        with pytest.raises(
            ValueError, match="min_regime_confidence must be between 0.0 and 1.0"
        ):
            DecisionConfig(min_regime_confidence=1.5)

    def test_min_regime_confidence_below_0_fails(self) -> None:
        with pytest.raises(
            ValueError, match="min_regime_confidence must be between 0.0 and 1.0"
        ):
            DecisionConfig(min_regime_confidence=-0.1)

    def test_breadth_score_at_boundaries(self) -> None:
        # 0 and 100 are valid
        DecisionConfig(min_breadth_score_for_long=0)
        DecisionConfig(min_breadth_score_for_long=100)
        DecisionConfig(max_breadth_score_for_short=0)
        DecisionConfig(max_breadth_score_for_short=100)

    def test_breadth_score_above_100_fails(self) -> None:
        with pytest.raises(
            ValueError, match="min_breadth_score_for_long must be between 0 and 100"
        ):
            DecisionConfig(min_breadth_score_for_long=101)

    def test_breadth_score_below_0_fails(self) -> None:
        with pytest.raises(
            ValueError, match="max_breadth_score_for_short must be between 0 and 100"
        ):
            DecisionConfig(max_breadth_score_for_short=-1)

    def test_stale_input_minutes_positive(self) -> None:
        with pytest.raises(
            ValueError, match="stale_input_minutes must be positive"
        ):
            DecisionConfig(stale_input_minutes=0)
        with pytest.raises(
            ValueError, match="stale_input_minutes must be positive"
        ):
            DecisionConfig(stale_input_minutes=-1)


# ---------------------------------------------------------------------------
# DecisionOutput — valid creation
# ---------------------------------------------------------------------------

class TestDecisionOutputValid:
    def test_create_valid_decision(self) -> None:
        now = datetime.now(timezone.utc)
        output = DecisionOutput(
            timestamp=now,
            status=OutputStatus.VALID,
            decision_state=DecisionState.ALLOW,
            decision_action=DecisionAction.ENABLE_LONG_ONLY_RESEARCH,
            allowed_mode=AllowedMode.LONG_ONLY,
            market_regime=RegimeState.BULL,
            risk_state=RiskState.RISK_ON,
            confidence=0.82,
            regime_confidence=0.82,
            breadth_score=72,
            market_health=RiskState.RISK_ON,
            reason_codes=["BULL_HEALTHY_BREADTH"],
            input_refs=DecisionInputRefs(
                regime_timestamp=now.isoformat(),
                breadth_timestamp=now.isoformat(),
                regime_source="regime_engine",
                breadth_source="breadth_engine",
            ),
            data_quality=DataQuality(),
        )
        assert output.status == OutputStatus.VALID
        assert output.decision_state == DecisionState.ALLOW
        assert output.decision_action == DecisionAction.ENABLE_LONG_ONLY_RESEARCH
        assert output.allowed_mode == AllowedMode.LONG_ONLY
        assert output.market_regime == RegimeState.BULL
        assert output.confidence == 0.82
        assert output.regime_confidence == 0.82
        assert output.breadth_score == 72
        assert output.market_health == RiskState.RISK_ON
        assert output.is_blocking() is False

    def test_confidence_at_boundaries(self) -> None:
        now = datetime.now(timezone.utc)
        # 0.0 is valid
        DecisionOutput(
            timestamp=now,
            status=OutputStatus.INVALID,
            decision_state=DecisionState.BLOCK,
            decision_action=DecisionAction.BLOCK_ALL,
            allowed_mode=AllowedMode.NONE,
            market_regime=RegimeState.UNKNOWN,
            risk_state=RiskState.UNKNOWN,
            confidence=0.0,
            regime_confidence=0.0,
            breadth_score=0,
            market_health=RiskState.UNKNOWN,
        )
        # 1.0 is valid
        DecisionOutput(
            timestamp=now,
            status=OutputStatus.VALID,
            decision_state=DecisionState.ALLOW,
            decision_action=DecisionAction.ENABLE_LONG_ONLY_RESEARCH,
            allowed_mode=AllowedMode.LONG_ONLY,
            market_regime=RegimeState.BULL,
            risk_state=RiskState.RISK_ON,
            confidence=1.0,
            regime_confidence=1.0,
            breadth_score=100,
            market_health=RiskState.RISK_ON,
        )

    def test_breadth_score_at_boundaries(self) -> None:
        now = datetime.now(timezone.utc)
        # 0 is valid
        DecisionOutput(
            timestamp=now,
            status=OutputStatus.INVALID,
            decision_state=DecisionState.BLOCK,
            decision_action=DecisionAction.BLOCK_ALL,
            allowed_mode=AllowedMode.NONE,
            market_regime=RegimeState.UNKNOWN,
            risk_state=RiskState.UNKNOWN,
            confidence=0.0,
            regime_confidence=0.0,
            breadth_score=0,
            market_health=RiskState.UNKNOWN,
        )
        # 100 is valid
        DecisionOutput(
            timestamp=now,
            status=OutputStatus.VALID,
            decision_state=DecisionState.ALLOW,
            decision_action=DecisionAction.ENABLE_LONG_ONLY_RESEARCH,
            allowed_mode=AllowedMode.LONG_ONLY,
            market_regime=RegimeState.BULL,
            risk_state=RiskState.RISK_ON,
            confidence=1.0,
            regime_confidence=1.0,
            breadth_score=100,
            market_health=RiskState.RISK_ON,
        )

    def test_default_reason_codes_empty(self) -> None:
        now = datetime.now(timezone.utc)
        output = DecisionOutput(
            timestamp=now,
            status=OutputStatus.VALID,
            decision_state=DecisionState.ALLOW,
            decision_action=DecisionAction.ENABLE_LONG_ONLY_RESEARCH,
            allowed_mode=AllowedMode.LONG_ONLY,
            market_regime=RegimeState.BULL,
            risk_state=RiskState.RISK_ON,
            confidence=0.5,
            regime_confidence=0.5,
            breadth_score=50,
            market_health=RiskState.NEUTRAL,
        )
        assert output.reason_codes == []

    def test_default_data_quality(self) -> None:
        now = datetime.now(timezone.utc)
        output = DecisionOutput(
            timestamp=now,
            status=OutputStatus.VALID,
            decision_state=DecisionState.ALLOW,
            decision_action=DecisionAction.ENABLE_LONG_ONLY_RESEARCH,
            allowed_mode=AllowedMode.LONG_ONLY,
            market_regime=RegimeState.BULL,
            risk_state=RiskState.RISK_ON,
            confidence=0.5,
            regime_confidence=0.5,
            breadth_score=50,
            market_health=RiskState.NEUTRAL,
        )
        assert output.data_quality.is_valid() is True

    def test_default_input_refs(self) -> None:
        now = datetime.now(timezone.utc)
        output = DecisionOutput(
            timestamp=now,
            status=OutputStatus.VALID,
            decision_state=DecisionState.ALLOW,
            decision_action=DecisionAction.ENABLE_LONG_ONLY_RESEARCH,
            allowed_mode=AllowedMode.LONG_ONLY,
            market_regime=RegimeState.BULL,
            risk_state=RiskState.RISK_ON,
            confidence=0.5,
            regime_confidence=0.5,
            breadth_score=50,
            market_health=RiskState.NEUTRAL,
        )
        assert output.input_refs.regime_timestamp == ""
        assert output.input_refs.breadth_timestamp == ""
        assert output.input_refs.regime_source == ""
        assert output.input_refs.breadth_source == ""


# ---------------------------------------------------------------------------
# DecisionOutput — validation failures
# ---------------------------------------------------------------------------

class TestDecisionOutputValidation:
    def test_confidence_above_1_fails(self) -> None:
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="confidence must be between 0.0 and 1.0"):
            DecisionOutput(
                timestamp=now,
                status=OutputStatus.VALID,
                decision_state=DecisionState.ALLOW,
                decision_action=DecisionAction.ENABLE_LONG_ONLY_RESEARCH,
                allowed_mode=AllowedMode.LONG_ONLY,
                market_regime=RegimeState.BULL,
                risk_state=RiskState.RISK_ON,
                confidence=1.5,
                regime_confidence=0.5,
                breadth_score=50,
                market_health=RiskState.NEUTRAL,
            )

    def test_confidence_below_0_fails(self) -> None:
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="confidence must be between 0.0 and 1.0"):
            DecisionOutput(
                timestamp=now,
                status=OutputStatus.VALID,
                decision_state=DecisionState.ALLOW,
                decision_action=DecisionAction.ENABLE_LONG_ONLY_RESEARCH,
                allowed_mode=AllowedMode.LONG_ONLY,
                market_regime=RegimeState.BULL,
                risk_state=RiskState.RISK_ON,
                confidence=-0.1,
                regime_confidence=0.5,
                breadth_score=50,
                market_health=RiskState.NEUTRAL,
            )

    def test_regime_confidence_above_1_fails(self) -> None:
        now = datetime.now(timezone.utc)
        with pytest.raises(
            ValueError, match="regime_confidence must be between 0.0 and 1.0"
        ):
            DecisionOutput(
                timestamp=now,
                status=OutputStatus.VALID,
                decision_state=DecisionState.ALLOW,
                decision_action=DecisionAction.ENABLE_LONG_ONLY_RESEARCH,
                allowed_mode=AllowedMode.LONG_ONLY,
                market_regime=RegimeState.BULL,
                risk_state=RiskState.RISK_ON,
                confidence=0.5,
                regime_confidence=1.5,
                breadth_score=50,
                market_health=RiskState.NEUTRAL,
            )

    def test_regime_confidence_below_0_fails(self) -> None:
        now = datetime.now(timezone.utc)
        with pytest.raises(
            ValueError, match="regime_confidence must be between 0.0 and 1.0"
        ):
            DecisionOutput(
                timestamp=now,
                status=OutputStatus.VALID,
                decision_state=DecisionState.ALLOW,
                decision_action=DecisionAction.ENABLE_LONG_ONLY_RESEARCH,
                allowed_mode=AllowedMode.LONG_ONLY,
                market_regime=RegimeState.BULL,
                risk_state=RiskState.RISK_ON,
                confidence=0.5,
                regime_confidence=-0.1,
                breadth_score=50,
                market_health=RiskState.NEUTRAL,
            )

    def test_breadth_score_above_100_fails(self) -> None:
        now = datetime.now(timezone.utc)
        with pytest.raises(
            ValueError, match="breadth_score must be between 0 and 100"
        ):
            DecisionOutput(
                timestamp=now,
                status=OutputStatus.VALID,
                decision_state=DecisionState.ALLOW,
                decision_action=DecisionAction.ENABLE_LONG_ONLY_RESEARCH,
                allowed_mode=AllowedMode.LONG_ONLY,
                market_regime=RegimeState.BULL,
                risk_state=RiskState.RISK_ON,
                confidence=0.5,
                regime_confidence=0.5,
                breadth_score=101,
                market_health=RiskState.NEUTRAL,
            )

    def test_breadth_score_below_0_fails(self) -> None:
        now = datetime.now(timezone.utc)
        with pytest.raises(
            ValueError, match="breadth_score must be between 0 and 100"
        ):
            DecisionOutput(
                timestamp=now,
                status=OutputStatus.VALID,
                decision_state=DecisionState.ALLOW,
                decision_action=DecisionAction.ENABLE_LONG_ONLY_RESEARCH,
                allowed_mode=AllowedMode.LONG_ONLY,
                market_regime=RegimeState.BULL,
                risk_state=RiskState.RISK_ON,
                confidence=0.5,
                regime_confidence=0.5,
                breadth_score=-1,
                market_health=RiskState.NEUTRAL,
            )


# ---------------------------------------------------------------------------
# DecisionOutput — fail-closed factory
# ---------------------------------------------------------------------------

class TestDecisionOutputBlockAll:
    def test_block_all_defaults(self) -> None:
        output = DecisionOutput.block_all()
        assert output.decision_state == DecisionState.BLOCK
        assert output.decision_action == DecisionAction.BLOCK_ALL
        assert output.allowed_mode == AllowedMode.NONE
        assert output.market_regime == RegimeState.UNKNOWN
        assert output.risk_state == RiskState.UNKNOWN
        assert output.confidence == 0.0
        assert output.regime_confidence == 0.0
        assert output.breadth_score == 0
        assert output.market_health == RiskState.UNKNOWN
        assert output.status == OutputStatus.INVALID
        assert output.is_blocking() is True
        assert "DECISION_BLOCKED_BY_DEFAULT" in output.reason_codes

    def test_block_all_with_custom_reasons(self) -> None:
        output = DecisionOutput.block_all(
            reason_codes=["MISSING_REGIME", "MISSING_BREADTH"]
        )
        assert output.reason_codes == ["MISSING_REGIME", "MISSING_BREADTH"]

    def test_block_all_with_custom_data_quality(self) -> None:
        dq = DataQuality(missing=True, stale=True)
        output = DecisionOutput.block_all(data_quality=dq)
        assert output.data_quality.missing is True
        assert output.data_quality.stale is True

    def test_block_all_with_custom_timestamp(self) -> None:
        now = datetime.now(timezone.utc)
        output = DecisionOutput.block_all(timestamp=now)
        assert output.timestamp == now

    def test_block_all_is_blocking(self) -> None:
        output = DecisionOutput.block_all()
        assert output.is_blocking() is True


# ---------------------------------------------------------------------------
# Immutability tests
# ---------------------------------------------------------------------------

class TestImmutability:
    def test_decision_output_is_frozen(self) -> None:
        now = datetime.now(timezone.utc)
        output = DecisionOutput.block_all(timestamp=now)
        with pytest.raises(FrozenInstanceError):
            output.confidence = 0.5  # type: ignore[misc]

    def test_decision_config_is_frozen(self) -> None:
        config = DecisionConfig()
        with pytest.raises(FrozenInstanceError):
            config.min_regime_confidence = 0.9  # type: ignore[misc]

    def test_decision_input_refs_is_frozen(self) -> None:
        refs = DecisionInputRefs()
        with pytest.raises(FrozenInstanceError):
            refs.regime_timestamp = "test"  # type: ignore[misc]

    def test_data_quality_is_frozen(self) -> None:
        dq = DataQuality()
        with pytest.raises(FrozenInstanceError):
            dq.missing = True  # type: ignore[misc]
