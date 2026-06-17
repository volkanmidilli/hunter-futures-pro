"""Tests for execution bridge models."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from hunter.decision.models import DecisionAction, DecisionState
from hunter.execution.models import (
    ExecutionBridgeConfig,
    ExecutionContext,
    ExecutionInputRefs,
    ExecutionMode,
    ExecutionSafetyFlags,
    ExecutionState,
)
from hunter.market_state.models import AllowedMode, DataQuality, OutputStatus


# ---------------------------------------------------------------------------
# ExecutionState enum
# ---------------------------------------------------------------------------

class TestExecutionState:
    def test_enabled_value(self) -> None:
        assert ExecutionState.ENABLED == "ENABLED"

    def test_blocked_value(self) -> None:
        assert ExecutionState.BLOCKED == "BLOCKED"

    def test_dry_run_only_value(self) -> None:
        assert ExecutionState.DRY_RUN_ONLY == "DRY_RUN_ONLY"

    def test_unknown_value(self) -> None:
        assert ExecutionState.UNKNOWN == "UNKNOWN"

    def test_all_members_present(self) -> None:
        members = {m.name for m in ExecutionState}
        assert members == {"ENABLED", "BLOCKED", "DRY_RUN_ONLY", "UNKNOWN"}


# ---------------------------------------------------------------------------
# ExecutionMode enum
# ---------------------------------------------------------------------------

class TestExecutionMode:
    def test_long_research_only_value(self) -> None:
        assert ExecutionMode.LONG_RESEARCH_ONLY == "LONG_RESEARCH_ONLY"

    def test_short_research_only_value(self) -> None:
        assert ExecutionMode.SHORT_RESEARCH_ONLY == "SHORT_RESEARCH_ONLY"

    def test_block_all_value(self) -> None:
        assert ExecutionMode.BLOCK_ALL == "BLOCK_ALL"

    def test_dry_run_only_value(self) -> None:
        assert ExecutionMode.DRY_RUN_ONLY == "DRY_RUN_ONLY"

    def test_all_members_present(self) -> None:
        members = {m.name for m in ExecutionMode}
        assert members == {"LONG_RESEARCH_ONLY", "SHORT_RESEARCH_ONLY", "BLOCK_ALL", "DRY_RUN_ONLY"}


# ---------------------------------------------------------------------------
# ExecutionBridgeConfig
# ---------------------------------------------------------------------------

class TestExecutionBridgeConfig:
    def test_default_values(self) -> None:
        config = ExecutionBridgeConfig()
        assert config.stale_decision_minutes == 120
        assert config.dry_run_required is True
        assert config.live_trading_enabled is False
        assert config.exchange_connection_enabled is False
        assert config.freqtrade_enabled is False
        assert config.allow_long_research is True
        assert config.allow_short_research is True
        assert config.manual_review_action == ExecutionMode.BLOCK_ALL
        assert config.unsupported_action == ExecutionMode.BLOCK_ALL

    def test_stale_decision_minutes_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="stale_decision_minutes must be positive"):
            ExecutionBridgeConfig(stale_decision_minutes=0)

    def test_stale_decision_minutes_negative_fails(self) -> None:
        with pytest.raises(ValueError, match="stale_decision_minutes must be positive"):
            ExecutionBridgeConfig(stale_decision_minutes=-1)

    def test_dry_run_required_false_fails(self) -> None:
        with pytest.raises(ValueError, match="dry_run_required must be True for MVP-4"):
            ExecutionBridgeConfig(dry_run_required=False)

    def test_live_trading_enabled_true_fails(self) -> None:
        with pytest.raises(ValueError, match="live_trading_enabled must be False for MVP-4"):
            ExecutionBridgeConfig(live_trading_enabled=True)

    def test_exchange_connection_enabled_true_fails(self) -> None:
        with pytest.raises(ValueError, match="exchange_connection_enabled must be False for MVP-4"):
            ExecutionBridgeConfig(exchange_connection_enabled=True)

    def test_freqtrade_enabled_true_fails(self) -> None:
        with pytest.raises(ValueError, match="freqtrade_enabled must be False for MVP-4"):
            ExecutionBridgeConfig(freqtrade_enabled=True)

    def test_custom_positive_stale_minutes(self) -> None:
        config = ExecutionBridgeConfig(stale_decision_minutes=60)
        assert config.stale_decision_minutes == 60

    def test_immutable(self) -> None:
        config = ExecutionBridgeConfig()
        with pytest.raises(AttributeError):
            config.stale_decision_minutes = 60


# ---------------------------------------------------------------------------
# ExecutionSafetyFlags
# ---------------------------------------------------------------------------

class TestExecutionSafetyFlags:
    def test_default_values(self) -> None:
        flags = ExecutionSafetyFlags()
        assert flags.dry_run is True
        assert flags.live_trading_enabled is False
        assert flags.exchange_connection_enabled is False
        assert flags.freqtrade_enabled is False
        assert flags.human_override_required is False
        assert flags.max_context_age_seconds == 300

    def test_max_context_age_seconds_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="max_context_age_seconds must be positive"):
            ExecutionSafetyFlags(max_context_age_seconds=0)

    def test_max_context_age_seconds_negative_fails(self) -> None:
        with pytest.raises(ValueError, match="max_context_age_seconds must be positive"):
            ExecutionSafetyFlags(max_context_age_seconds=-1)

    def test_dry_run_false_fails(self) -> None:
        with pytest.raises(ValueError, match="dry_run must be True for MVP-4"):
            ExecutionSafetyFlags(dry_run=False)

    def test_live_trading_enabled_true_fails(self) -> None:
        with pytest.raises(ValueError, match="live_trading_enabled must be False for MVP-4"):
            ExecutionSafetyFlags(live_trading_enabled=True)

    def test_exchange_connection_enabled_true_fails(self) -> None:
        with pytest.raises(ValueError, match="exchange_connection_enabled must be False for MVP-4"):
            ExecutionSafetyFlags(exchange_connection_enabled=True)

    def test_freqtrade_enabled_true_fails(self) -> None:
        with pytest.raises(ValueError, match="freqtrade_enabled must be False for MVP-4"):
            ExecutionSafetyFlags(freqtrade_enabled=True)

    def test_to_dict(self) -> None:
        flags = ExecutionSafetyFlags()
        d = flags.to_dict()
        assert d["dry_run"] is True
        assert d["live_trading_enabled"] is False
        assert d["exchange_connection_enabled"] is False
        assert d["freqtrade_enabled"] is False
        assert d["human_override_required"] is False
        assert d["max_context_age_seconds"] == 300

    def test_immutable(self) -> None:
        flags = ExecutionSafetyFlags()
        with pytest.raises(AttributeError):
            flags.dry_run = False


# ---------------------------------------------------------------------------
# ExecutionInputRefs
# ---------------------------------------------------------------------------

class TestExecutionInputRefs:
    def test_default_values(self) -> None:
        refs = ExecutionInputRefs()
        assert refs.decision_timestamp == ""
        assert refs.decision_source == ""

    def test_custom_values(self) -> None:
        refs = ExecutionInputRefs(decision_timestamp="2026-06-17T12:00:00Z", decision_source="decision_engine")
        assert refs.decision_timestamp == "2026-06-17T12:00:00Z"
        assert refs.decision_source == "decision_engine"

    def test_immutable(self) -> None:
        refs = ExecutionInputRefs()
        with pytest.raises(AttributeError):
            refs.decision_timestamp = "x"


# ---------------------------------------------------------------------------
# ExecutionContext
# ---------------------------------------------------------------------------

class TestExecutionContext:
    def test_valid_context_creation(self) -> None:
        ts = datetime.now(timezone.utc)
        ctx = ExecutionContext(
            timestamp=ts,
            status=OutputStatus.VALID,
            execution_state=ExecutionState.DRY_RUN_ONLY,
            execution_mode=ExecutionMode.LONG_RESEARCH_ONLY,
            decision_state=DecisionState.ALLOW,
            decision_action=DecisionAction.ENABLE_LONG_ONLY_RESEARCH,
            allowed_mode=AllowedMode.LONG_ONLY,
        )
        assert ctx.timestamp == ts
        assert ctx.status == OutputStatus.VALID
        assert ctx.execution_state == ExecutionState.DRY_RUN_ONLY
        assert ctx.execution_mode == ExecutionMode.LONG_RESEARCH_ONLY
        assert ctx.decision_state == DecisionState.ALLOW
        assert ctx.decision_action == DecisionAction.ENABLE_LONG_ONLY_RESEARCH
        assert ctx.allowed_mode == AllowedMode.LONG_ONLY
        assert ctx.dry_run is True
        assert ctx.live_trading_enabled is False
        assert ctx.exchange_connection_enabled is False
        assert ctx.freqtrade_enabled is False
        assert ctx.version == "1.0"
        assert ctx.reason_codes == []
        assert isinstance(ctx.input_refs, ExecutionInputRefs)
        assert isinstance(ctx.data_quality, DataQuality)
        assert isinstance(ctx.safety_flags, ExecutionSafetyFlags)

    def test_version_defaults_to_1_0(self) -> None:
        ctx = ExecutionContext(
            timestamp=datetime.now(timezone.utc),
            status=OutputStatus.VALID,
            execution_state=ExecutionState.BLOCKED,
            execution_mode=ExecutionMode.BLOCK_ALL,
            decision_state=DecisionState.BLOCK,
            decision_action=DecisionAction.BLOCK_ALL,
            allowed_mode=AllowedMode.NONE,
        )
        assert ctx.version == "1.0"

    def test_empty_version_fails(self) -> None:
        with pytest.raises(ValueError, match="version must be non-empty"):
            ExecutionContext(
                timestamp=datetime.now(timezone.utc),
                status=OutputStatus.VALID,
                execution_state=ExecutionState.BLOCKED,
                execution_mode=ExecutionMode.BLOCK_ALL,
                decision_state=DecisionState.BLOCK,
                decision_action=DecisionAction.BLOCK_ALL,
                allowed_mode=AllowedMode.NONE,
                version="",
            )

    def test_blocked_factory_defaults(self) -> None:
        ctx = ExecutionContext.blocked()
        assert ctx.execution_state == ExecutionState.BLOCKED
        assert ctx.execution_mode == ExecutionMode.BLOCK_ALL
        assert ctx.dry_run is True
        assert ctx.live_trading_enabled is False
        assert ctx.exchange_connection_enabled is False
        assert ctx.freqtrade_enabled is False
        assert ctx.status == OutputStatus.INVALID
        assert ctx.decision_state == DecisionState.BLOCK
        assert ctx.decision_action == DecisionAction.BLOCK_ALL
        assert ctx.allowed_mode == AllowedMode.NONE
        assert ctx.version == "1.0"
        assert ctx.reason_codes == ["EXECUTION_BLOCKED_BY_DEFAULT"]
        assert isinstance(ctx.data_quality, DataQuality)
        assert isinstance(ctx.safety_flags, ExecutionSafetyFlags)

    def test_blocked_factory_with_custom_reason(self) -> None:
        ctx = ExecutionContext.blocked(reason_codes=["MISSING_DECISION"])
        assert ctx.reason_codes == ["MISSING_DECISION"]

    def test_blocked_factory_with_custom_data_quality(self) -> None:
        dq = DataQuality(missing=True)
        ctx = ExecutionContext.blocked(data_quality=dq)
        assert ctx.data_quality.missing is True

    def test_blocked_factory_timestamp(self) -> None:
        ts = datetime(2026, 6, 17, 12, 0, 0, tzinfo=timezone.utc)
        ctx = ExecutionContext.blocked(timestamp=ts)
        assert ctx.timestamp == ts

    def test_is_blocking_true_for_blocked(self) -> None:
        ctx = ExecutionContext.blocked()
        assert ctx.is_blocking() is True

    def test_is_blocking_true_for_unknown(self) -> None:
        ctx = ExecutionContext(
            timestamp=datetime.now(timezone.utc),
            status=OutputStatus.INVALID,
            execution_state=ExecutionState.UNKNOWN,
            execution_mode=ExecutionMode.BLOCK_ALL,
            decision_state=DecisionState.UNKNOWN,
            decision_action=DecisionAction.BLOCK_ALL,
            allowed_mode=AllowedMode.NONE,
        )
        assert ctx.is_blocking() is True

    def test_is_blocking_true_for_invalid_status(self) -> None:
        ctx = ExecutionContext(
            timestamp=datetime.now(timezone.utc),
            status=OutputStatus.INVALID,
            execution_state=ExecutionState.DRY_RUN_ONLY,
            execution_mode=ExecutionMode.LONG_RESEARCH_ONLY,
            decision_state=DecisionState.ALLOW,
            decision_action=DecisionAction.ENABLE_LONG_ONLY_RESEARCH,
            allowed_mode=AllowedMode.LONG_ONLY,
        )
        assert ctx.is_blocking() is True

    def test_is_blocking_false_for_dry_run(self) -> None:
        ctx = ExecutionContext(
            timestamp=datetime.now(timezone.utc),
            status=OutputStatus.VALID,
            execution_state=ExecutionState.DRY_RUN_ONLY,
            execution_mode=ExecutionMode.LONG_RESEARCH_ONLY,
            decision_state=DecisionState.ALLOW,
            decision_action=DecisionAction.ENABLE_LONG_ONLY_RESEARCH,
            allowed_mode=AllowedMode.LONG_ONLY,
        )
        assert ctx.is_blocking() is False

    def test_immutable(self) -> None:
        ctx = ExecutionContext.blocked()
        with pytest.raises(AttributeError):
            ctx.dry_run = False

    def test_reason_codes_default_empty(self) -> None:
        ctx = ExecutionContext(
            timestamp=datetime.now(timezone.utc),
            status=OutputStatus.VALID,
            execution_state=ExecutionState.DRY_RUN_ONLY,
            execution_mode=ExecutionMode.LONG_RESEARCH_ONLY,
            decision_state=DecisionState.ALLOW,
            decision_action=DecisionAction.ENABLE_LONG_ONLY_RESEARCH,
            allowed_mode=AllowedMode.LONG_ONLY,
        )
        assert ctx.reason_codes == []

    def test_reason_codes_custom(self) -> None:
        ctx = ExecutionContext(
            timestamp=datetime.now(timezone.utc),
            status=OutputStatus.VALID,
            execution_state=ExecutionState.DRY_RUN_ONLY,
            execution_mode=ExecutionMode.LONG_RESEARCH_ONLY,
            decision_state=DecisionState.ALLOW,
            decision_action=DecisionAction.ENABLE_LONG_ONLY_RESEARCH,
            allowed_mode=AllowedMode.LONG_ONLY,
            reason_codes=["LONG_RESEARCH_ENABLED"],
        )
        assert ctx.reason_codes == ["LONG_RESEARCH_ENABLED"]

    def test_safety_flags_custom(self) -> None:
        flags = ExecutionSafetyFlags(human_override_required=True)
        ctx = ExecutionContext(
            timestamp=datetime.now(timezone.utc),
            status=OutputStatus.VALID,
            execution_state=ExecutionState.DRY_RUN_ONLY,
            execution_mode=ExecutionMode.LONG_RESEARCH_ONLY,
            decision_state=DecisionState.ALLOW,
            decision_action=DecisionAction.ENABLE_LONG_ONLY_RESEARCH,
            allowed_mode=AllowedMode.LONG_ONLY,
            safety_flags=flags,
        )
        assert ctx.safety_flags.human_override_required is True

    def test_data_quality_custom(self) -> None:
        dq = DataQuality(stale=True)
        ctx = ExecutionContext(
            timestamp=datetime.now(timezone.utc),
            status=OutputStatus.VALID,
            execution_state=ExecutionState.DRY_RUN_ONLY,
            execution_mode=ExecutionMode.LONG_RESEARCH_ONLY,
            decision_state=DecisionState.ALLOW,
            decision_action=DecisionAction.ENABLE_LONG_ONLY_RESEARCH,
            allowed_mode=AllowedMode.LONG_ONLY,
            data_quality=dq,
        )
        assert ctx.data_quality.stale is True

    def test_input_refs_custom(self) -> None:
        refs = ExecutionInputRefs(decision_timestamp="2026-06-17T12:00:00Z", decision_source="decision_engine")
        ctx = ExecutionContext(
            timestamp=datetime.now(timezone.utc),
            status=OutputStatus.VALID,
            execution_state=ExecutionState.DRY_RUN_ONLY,
            execution_mode=ExecutionMode.LONG_RESEARCH_ONLY,
            decision_state=DecisionState.ALLOW,
            decision_action=DecisionAction.ENABLE_LONG_ONLY_RESEARCH,
            allowed_mode=AllowedMode.LONG_ONLY,
            input_refs=refs,
        )
        assert ctx.input_refs.decision_timestamp == "2026-06-17T12:00:00Z"
        assert ctx.input_refs.decision_source == "decision_engine"

    def test_short_research_context(self) -> None:
        ctx = ExecutionContext(
            timestamp=datetime.now(timezone.utc),
            status=OutputStatus.VALID,
            execution_state=ExecutionState.DRY_RUN_ONLY,
            execution_mode=ExecutionMode.SHORT_RESEARCH_ONLY,
            decision_state=DecisionState.ALLOW,
            decision_action=DecisionAction.ENABLE_SHORT_ONLY_RESEARCH,
            allowed_mode=AllowedMode.SHORT_ONLY,
        )
        assert ctx.execution_mode == ExecutionMode.SHORT_RESEARCH_ONLY
        assert ctx.is_blocking() is False
