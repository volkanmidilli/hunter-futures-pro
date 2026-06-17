"""Tests for decision engine."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from hunter.decision.engine import (
    calculate_decision_confidence,
    detect_regime_breadth_conflict,
    is_stale_output,
    make_decision,
    validate_decision_inputs,
)
from hunter.decision.models import (
    DecisionAction,
    DecisionConfig,
    DecisionInputRefs,
    DecisionOutput,
    DecisionState,
)
from hunter.market_state.models import (
    AllowedMode,
    BreadthOutput,
    DataQuality,
    OutputStatus,
    RegimeOutput,
    RegimeState,
    RiskState,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_regime(
    regime: RegimeState = RegimeState.BULL,
    allowed_mode: AllowedMode = AllowedMode.LONG_ONLY,
    confidence: float = 0.82,
    status: OutputStatus = OutputStatus.VALID,
    timestamp: datetime | None = None,
    risk_state: RiskState = RiskState.RISK_ON,
    data_quality: DataQuality | None = None,
) -> RegimeOutput:
    return RegimeOutput(
        timestamp=timestamp or datetime.now(timezone.utc),
        status=status,
        market_regime=regime,
        allowed_mode=allowed_mode,
        confidence=confidence,
        risk_state=risk_state,
        btc_trend_score=85,
        eth_trend_score=74,
        breadth_confirmation_score=68,
        data_quality=data_quality or DataQuality(),
    )


def _make_breadth(
        breadth_score: int = 72,
        market_health: RiskState = RiskState.RISK_ON,
        status: OutputStatus = OutputStatus.VALID,
        timestamp: datetime | None = None,
        data_quality: DataQuality | None = None,
) -> BreadthOutput:
    return BreadthOutput(
        timestamp=timestamp or datetime.now(timezone.utc),
        status=status,
        breadth_score=breadth_score,
        market_health=market_health,
        universe_size=120,
        valid_symbol_count=115,
        invalid_symbol_count=5,
        above_ema20_pct=0.68,
        above_ema50_pct=0.55,
        above_ema200_pct=0.41,
        ema20_rising_pct=0.63,
        ema50_rising_pct=0.52,
        advancing_pct=0.61,
        declining_pct=0.39,
        outperforming_btc_7d_pct=0.46,
        outperforming_btc_30d_pct=0.34,
        data_quality=data_quality or DataQuality(),
    )


# ---------------------------------------------------------------------------
# validate_decision_inputs
# ---------------------------------------------------------------------------

class TestValidateInputs:
    def test_missing_regime_fails(self) -> None:
        config = DecisionConfig()
        is_valid, reasons, dq = validate_decision_inputs(None, _make_breadth(), config)
        assert is_valid is False
        assert "MISSING_REGIME" in reasons
        assert dq.missing is True

    def test_missing_breadth_fails(self) -> None:
        config = DecisionConfig()
        is_valid, reasons, dq = validate_decision_inputs(_make_regime(), None, config)
        assert is_valid is False
        assert "MISSING_BREADTH" in reasons
        assert dq.missing is True

    def test_invalid_regime_status_fails(self) -> None:
        config = DecisionConfig()
        regime = _make_regime(status=OutputStatus.INVALID)
        is_valid, reasons, dq = validate_decision_inputs(regime, _make_breadth(), config)
        assert is_valid is False
        assert "INVALID_REGIME" in reasons

    def test_invalid_breadth_status_fails(self) -> None:
        config = DecisionConfig()
        breadth = _make_breadth(status=OutputStatus.INVALID)
        is_valid, reasons, dq = validate_decision_inputs(_make_regime(), breadth, config)
        assert is_valid is False
        assert "INVALID_BREADTH" in reasons

    def test_unknown_regime_fails(self) -> None:
        config = DecisionConfig()
        regime = _make_regime(regime=RegimeState.UNKNOWN)
        is_valid, reasons, dq = validate_decision_inputs(regime, _make_breadth(), config)
        assert is_valid is False
        assert "UNKNOWN_REGIME" in reasons

    def test_allowed_mode_none_fails(self) -> None:
        config = DecisionConfig()
        regime = _make_regime(allowed_mode=AllowedMode.NONE)
        is_valid, reasons, dq = validate_decision_inputs(regime, _make_breadth(), config)
        assert is_valid is False
        assert "ALLOWED_MODE_NONE" in reasons

    def test_low_confidence_fails(self) -> None:
        config = DecisionConfig(min_regime_confidence=0.70)
        regime = _make_regime(confidence=0.50)
        is_valid, reasons, dq = validate_decision_inputs(regime, _make_breadth(), config)
        assert is_valid is False
        assert "LOW_REGIME_CONFIDENCE" in reasons

    def test_stale_input_fails(self) -> None:
        config = DecisionConfig(stale_input_minutes=30)
        old = datetime.now(timezone.utc) - timedelta(minutes=60)
        regime = _make_regime(timestamp=old)
        breadth = _make_breadth(timestamp=old)
        is_valid, reasons, dq = validate_decision_inputs(regime, breadth, config)
        assert is_valid is False
        assert "STALE_INPUT" in reasons
        assert dq.stale is True

    def test_valid_inputs_pass(self) -> None:
        config = DecisionConfig()
        is_valid, reasons, dq = validate_decision_inputs(
            _make_regime(), _make_breadth(), config
        )
        assert is_valid is True
        assert reasons == []
        assert dq.is_valid() is True

    def test_data_quality_aggregation(self) -> None:
        config = DecisionConfig()
        regime = _make_regime(
            data_quality=DataQuality(missing=True, insufficient_history=True)
        )
        breadth = _make_breadth(
            data_quality=DataQuality(stale=True, insufficient_universe=True)
        )
        is_valid, reasons, dq = validate_decision_inputs(regime, breadth, config)
        # Should still pass validation (not a fail-closed condition)
        assert is_valid is True
        assert dq.missing is True
        assert dq.stale is True
        assert dq.insufficient_history is True
        assert dq.insufficient_universe is True


# ---------------------------------------------------------------------------
# is_stale_output
# ---------------------------------------------------------------------------

class TestIsStaleOutput:
    def test_fresh_inputs_not_stale(self) -> None:
        now = datetime.now(timezone.utc)
        regime = _make_regime(timestamp=now)
        breadth = _make_breadth(timestamp=now)
        assert is_stale_output(regime, breadth, 120) is False

    def test_old_regime_is_stale(self) -> None:
        now = datetime.now(timezone.utc)
        old = now - timedelta(minutes=60)
        regime = _make_regime(timestamp=old)
        breadth = _make_breadth(timestamp=now)
        assert is_stale_output(regime, breadth, 30) is True

    def test_old_breadth_is_stale(self) -> None:
        now = datetime.now(timezone.utc)
        old = now - timedelta(minutes=60)
        regime = _make_regime(timestamp=now)
        breadth = _make_breadth(timestamp=old)
        assert is_stale_output(regime, breadth, 30) is True

    def test_uses_oldest_timestamp(self) -> None:
        now = datetime.now(timezone.utc)
        old = now - timedelta(minutes=60)
        regime = _make_regime(timestamp=old)
        breadth = _make_breadth(timestamp=now)
        # Oldest is 60 min old, threshold is 120 → not stale
        assert is_stale_output(regime, breadth, 120) is False
        # Oldest is 60 min old, threshold is 30 → stale
        assert is_stale_output(regime, breadth, 30) is True


# ---------------------------------------------------------------------------
# detect_regime_breadth_conflict
# ---------------------------------------------------------------------------

class TestDetectConflict:
    def test_bull_with_risk_off_is_conflict(self) -> None:
        regime = _make_regime(regime=RegimeState.BULL)
        breadth = _make_breadth(market_health=RiskState.RISK_OFF)
        assert detect_regime_breadth_conflict(regime, breadth) is True

    def test_bear_with_risk_on_is_conflict(self) -> None:
        regime = _make_regime(regime=RegimeState.BEAR, allowed_mode=AllowedMode.SHORT_ONLY)
        breadth = _make_breadth(market_health=RiskState.RISK_ON)
        assert detect_regime_breadth_conflict(regime, breadth) is True

    def test_bull_with_low_score_is_conflict(self) -> None:
        regime = _make_regime(regime=RegimeState.BULL)
        breadth = _make_breadth(breadth_score=40)
        assert detect_regime_breadth_conflict(regime, breadth) is True

    def test_bear_with_high_score_is_conflict(self) -> None:
        regime = _make_regime(regime=RegimeState.BEAR, allowed_mode=AllowedMode.SHORT_ONLY)
        breadth = _make_breadth(breadth_score=60)
        assert detect_regime_breadth_conflict(regime, breadth) is True

    def test_bull_with_risk_on_no_conflict(self) -> None:
        regime = _make_regime(regime=RegimeState.BULL)
        breadth = _make_breadth(market_health=RiskState.RISK_ON, breadth_score=72)
        assert detect_regime_breadth_conflict(regime, breadth) is False

    def test_bear_with_risk_off_no_conflict(self) -> None:
        regime = _make_regime(regime=RegimeState.BEAR, allowed_mode=AllowedMode.SHORT_ONLY)
        breadth = _make_breadth(market_health=RiskState.RISK_OFF, breadth_score=30)
        assert detect_regime_breadth_conflict(regime, breadth) is False

    def test_sideways_no_conflict(self) -> None:
        regime = _make_regime(regime=RegimeState.SIDEWAYS, allowed_mode=AllowedMode.NONE)
        breadth = _make_breadth(market_health=RiskState.RISK_ON)
        assert detect_regime_breadth_conflict(regime, breadth) is False


# ---------------------------------------------------------------------------
# calculate_decision_confidence
# ---------------------------------------------------------------------------

class TestCalculateConfidence:
    def test_high_regime_high_breadth(self) -> None:
        regime = _make_regime(confidence=0.90)
        breadth = _make_breadth(breadth_score=80)
        assert calculate_decision_confidence(regime, breadth) == 0.80

    def test_low_regime_high_breadth(self) -> None:
        regime = _make_regime(confidence=0.50)
        breadth = _make_breadth(breadth_score=80)
        assert calculate_decision_confidence(regime, breadth) == 0.50

    def test_high_regime_low_breadth(self) -> None:
        regime = _make_regime(confidence=0.90)
        breadth = _make_breadth(breadth_score=30)
        assert calculate_decision_confidence(regime, breadth) == 0.30

    def test_perfect_confidence(self) -> None:
        regime = _make_regime(confidence=1.0)
        breadth = _make_breadth(breadth_score=100)
        assert calculate_decision_confidence(regime, breadth) == 1.0

    def test_zero_confidence(self) -> None:
        regime = _make_regime(confidence=0.0)
        breadth = _make_breadth(breadth_score=0)
        assert calculate_decision_confidence(regime, breadth) == 0.0


# ---------------------------------------------------------------------------
# make_decision — fail-closed cases
# ---------------------------------------------------------------------------

class TestMakeDecisionFailClosed:
    def test_missing_regime_blocks(self) -> None:
        result = make_decision(None, _make_breadth())
        assert result.decision_state == DecisionState.BLOCK
        assert result.decision_action == DecisionAction.BLOCK_ALL
        assert result.is_blocking() is True
        assert "MISSING_REGIME" in result.reason_codes

    def test_missing_breadth_blocks(self) -> None:
        result = make_decision(_make_regime(), None)
        assert result.decision_state == DecisionState.BLOCK
        assert result.decision_action == DecisionAction.BLOCK_ALL
        assert result.is_blocking() is True
        assert "MISSING_BREADTH" in result.reason_codes

    def test_invalid_regime_blocks(self) -> None:
        regime = _make_regime(status=OutputStatus.INVALID)
        result = make_decision(regime, _make_breadth())
        assert result.decision_state == DecisionState.BLOCK
        assert result.decision_action == DecisionAction.BLOCK_ALL
        assert "INVALID_REGIME" in result.reason_codes

    def test_invalid_breadth_blocks(self) -> None:
        breadth = _make_breadth(status=OutputStatus.INVALID)
        result = make_decision(_make_regime(), breadth)
        assert result.decision_state == DecisionState.BLOCK
        assert result.decision_action == DecisionAction.BLOCK_ALL
        assert "INVALID_BREADTH" in result.reason_codes

    def test_unknown_regime_blocks(self) -> None:
        regime = _make_regime(regime=RegimeState.UNKNOWN, allowed_mode=AllowedMode.NONE)
        result = make_decision(regime, _make_breadth())
        assert result.decision_state == DecisionState.BLOCK
        assert result.decision_action == DecisionAction.BLOCK_ALL
        assert "UNKNOWN_REGIME" in result.reason_codes

    def test_allowed_mode_none_blocks(self) -> None:
        regime = _make_regime(allowed_mode=AllowedMode.NONE)
        result = make_decision(regime, _make_breadth())
        assert result.decision_state == DecisionState.BLOCK
        assert result.decision_action == DecisionAction.BLOCK_ALL
        assert "ALLOWED_MODE_NONE" in result.reason_codes

    def test_low_confidence_blocks(self) -> None:
        config = DecisionConfig(min_regime_confidence=0.70)
        regime = _make_regime(confidence=0.50)
        result = make_decision(regime, _make_breadth(), config)
        assert result.decision_state == DecisionState.BLOCK
        assert result.decision_action == DecisionAction.BLOCK_ALL
        assert "LOW_REGIME_CONFIDENCE" in result.reason_codes

    def test_stale_regime_blocks(self) -> None:
        config = DecisionConfig(stale_input_minutes=30)
        old = datetime.now(timezone.utc) - timedelta(minutes=60)
        regime = _make_regime(timestamp=old)
        breadth = _make_breadth(timestamp=datetime.now(timezone.utc))
        result = make_decision(regime, breadth, config)
        assert result.decision_state == DecisionState.BLOCK
        assert result.decision_action == DecisionAction.BLOCK_ALL
        assert "STALE_INPUT" in result.reason_codes

    def test_stale_breadth_blocks(self) -> None:
        config = DecisionConfig(stale_input_minutes=30)
        old = datetime.now(timezone.utc) - timedelta(minutes=60)
        regime = _make_regime(timestamp=datetime.now(timezone.utc))
        breadth = _make_breadth(timestamp=old)
        result = make_decision(regime, breadth, config)
        assert result.decision_state == DecisionState.BLOCK
        assert result.decision_action == DecisionAction.BLOCK_ALL
        assert "STALE_INPUT" in result.reason_codes


# ---------------------------------------------------------------------------
# make_decision — allow cases
# ---------------------------------------------------------------------------

class TestMakeDecisionAllow:
    def test_bull_long_healthy_allows_long(self) -> None:
        regime = _make_regime(
            regime=RegimeState.BULL,
            allowed_mode=AllowedMode.LONG_ONLY,
            confidence=0.82,
        )
        breadth = _make_breadth(breadth_score=72, market_health=RiskState.RISK_ON)
        result = make_decision(regime, breadth)
        assert result.decision_state == DecisionState.ALLOW
        assert result.decision_action == DecisionAction.ENABLE_LONG_ONLY_RESEARCH
        assert result.allowed_mode == AllowedMode.LONG_ONLY
        assert result.market_regime == RegimeState.BULL
        assert result.breadth_score == 72
        assert result.reason_codes == ["BULL_HEALTHY_BREADTH"]
        assert result.is_blocking() is False
        assert result.status == OutputStatus.VALID

    def test_bear_short_weak_allows_short(self) -> None:
        regime = _make_regime(
            regime=RegimeState.BEAR,
            allowed_mode=AllowedMode.SHORT_ONLY,
            confidence=0.82,
            risk_state=RiskState.RISK_OFF,
        )
        breadth = _make_breadth(breadth_score=30, market_health=RiskState.RISK_OFF)
        result = make_decision(regime, breadth)
        assert result.decision_state == DecisionState.ALLOW
        assert result.decision_action == DecisionAction.ENABLE_SHORT_ONLY_RESEARCH
        assert result.allowed_mode == AllowedMode.SHORT_ONLY
        assert result.market_regime == RegimeState.BEAR
        assert result.breadth_score == 30
        assert result.reason_codes == ["BEAR_WEAK_BREADTH"]
        assert result.is_blocking() is False
        assert result.status == OutputStatus.VALID

    def test_bull_with_low_breadth_blocks(self) -> None:
        regime = _make_regime(
            regime=RegimeState.BULL,
            allowed_mode=AllowedMode.LONG_ONLY,
            confidence=0.82,
        )
        breadth = _make_breadth(breadth_score=50, market_health=RiskState.RISK_ON)
        result = make_decision(regime, breadth)
        # Default block because breadth_score < min_breadth_score_for_long (60)
        assert result.decision_state == DecisionState.BLOCK
        assert result.decision_action == DecisionAction.BLOCK_ALL
        assert result.reason_codes == ["DEFAULT_BLOCK"]

    def test_bear_with_high_breadth_blocks(self) -> None:
        regime = _make_regime(
            regime=RegimeState.BEAR,
            allowed_mode=AllowedMode.SHORT_ONLY,
            confidence=0.82,
            risk_state=RiskState.RISK_OFF,
        )
        breadth = _make_breadth(breadth_score=50, market_health=RiskState.RISK_OFF)
        result = make_decision(regime, breadth)
        # Default block because breadth_score > max_breadth_score_for_short (40)
        assert result.decision_state == DecisionState.BLOCK
        assert result.decision_action == DecisionAction.BLOCK_ALL
        assert result.reason_codes == ["DEFAULT_BLOCK"]


# ---------------------------------------------------------------------------
# make_decision — special cases
# ---------------------------------------------------------------------------

class TestMakeDecisionSpecialCases:
    def test_sideways_blocks(self) -> None:
        regime = _make_regime(
            regime=RegimeState.SIDEWAYS,
            allowed_mode=AllowedMode.LONG_ONLY,  # Use non-NONE to test sideways rule
            confidence=0.82,
        )
        breadth = _make_breadth()
        result = make_decision(regime, breadth)
        assert result.decision_state == DecisionState.BLOCK
        assert result.decision_action == DecisionAction.BLOCK_ALL
        assert result.reason_codes == ["SIDEWAYS_NO_DIRECTION"]

    def test_transition_blocks(self) -> None:
        regime = _make_regime(
            regime=RegimeState.TRANSITION,
            allowed_mode=AllowedMode.LONG_ONLY,  # Use non-NONE to test transition rule
            confidence=0.82,
        )
        breadth = _make_breadth()
        result = make_decision(regime, breadth)
        assert result.decision_state == DecisionState.BLOCK
        assert result.decision_action == DecisionAction.BLOCK_ALL
        assert result.reason_codes == ["TRANSITION_UNCERTAIN"]

    def test_transition_with_custom_action(self) -> None:
        config = DecisionConfig(transition_action=DecisionAction.MANUAL_REVIEW)
        regime = _make_regime(
            regime=RegimeState.TRANSITION,
            allowed_mode=AllowedMode.LONG_ONLY,  # Use non-NONE to test transition rule
            confidence=0.82,
        )
        breadth = _make_breadth()
        result = make_decision(regime, breadth, config)
        assert result.decision_state == DecisionState.BLOCK
        assert result.decision_action == DecisionAction.MANUAL_REVIEW
        assert result.reason_codes == ["TRANSITION_UNCERTAIN"]

    def test_conflict_blocks(self) -> None:
        regime = _make_regime(
            regime=RegimeState.BULL,
            allowed_mode=AllowedMode.LONG_ONLY,
            confidence=0.82,
        )
        breadth = _make_breadth(
            breadth_score=30, market_health=RiskState.RISK_OFF
        )
        result = make_decision(regime, breadth)
        assert result.decision_state == DecisionState.BLOCK
        assert result.decision_action == DecisionAction.BLOCK_ALL
        assert result.reason_codes == ["CONFLICTING_SIGNALS"]

    def test_conflict_with_custom_action(self) -> None:
        config = DecisionConfig(conflict_action=DecisionAction.MANUAL_REVIEW)
        regime = _make_regime(
            regime=RegimeState.BULL,
            allowed_mode=AllowedMode.LONG_ONLY,
            confidence=0.82,
        )
        breadth = _make_breadth(
            breadth_score=30, market_health=RiskState.RISK_OFF
        )
        result = make_decision(regime, breadth, config)
        assert result.decision_state == DecisionState.BLOCK
        assert result.decision_action == DecisionAction.MANUAL_REVIEW
        assert result.reason_codes == ["CONFLICTING_SIGNALS"]

    def test_default_block(self) -> None:
        # BULL but allowed_mode is SHORT_ONLY (mismatched) → default block
        regime = _make_regime(
            regime=RegimeState.BULL,
            allowed_mode=AllowedMode.SHORT_ONLY,
            confidence=0.82,
        )
        breadth = _make_breadth()
        result = make_decision(regime, breadth)
        assert result.decision_state == DecisionState.BLOCK
        assert result.decision_action == DecisionAction.BLOCK_ALL
        assert result.reason_codes == ["DEFAULT_BLOCK"]

    def test_input_refs_populated(self) -> None:
        regime = _make_regime(regime=RegimeState.BULL, allowed_mode=AllowedMode.LONG_ONLY)
        breadth = _make_breadth(breadth_score=72)
        result = make_decision(regime, breadth)
        assert result.input_refs.regime_source == "regime_engine"
        assert result.input_refs.breadth_source == "breadth_engine"
        assert result.input_refs.regime_timestamp != ""
        assert result.input_refs.breadth_timestamp != ""

    def test_confidence_calculation(self) -> None:
        regime = _make_regime(
            regime=RegimeState.BULL,
            allowed_mode=AllowedMode.LONG_ONLY,
            confidence=0.80,
        )
        breadth = _make_breadth(breadth_score=60)
        result = make_decision(regime, breadth)
        # min(0.80, 60/100) = 0.60
        assert result.confidence == 0.60
        assert result.regime_confidence == 0.80

    def test_data_quality_passed_through(self) -> None:
        regime = _make_regime(
            data_quality=DataQuality(missing=True)
        )
        breadth = _make_breadth()
        result = make_decision(regime, breadth)
        # Should still be ALLOW because missing is not a fail-closed condition
        # when the inputs are otherwise valid
        assert result.data_quality.missing is True


# ---------------------------------------------------------------------------
# Safety tests
# ---------------------------------------------------------------------------

class TestSafety:
    def test_no_network_calls(self) -> None:
        import inspect
        source = inspect.getsource(make_decision)
        assert "requests" not in source
        assert "urllib" not in source
        assert "http" not in source
        assert "socket" not in source

    def test_no_trading_execution_logic(self) -> None:
        import inspect
        source = inspect.getsource(make_decision)
        # Check for actual trading terms, not "order" as in "priority order"
        assert "buy(" not in source.lower()
        assert "sell(" not in source.lower()
        assert "position(" not in source.lower()
        assert "trade(" not in source.lower()
        assert "execute(" not in source.lower()
        assert "place_order" not in source.lower()
