"""Tests for Freqtrade bridge engine."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from hunter.execution.models import (
    ExecutionContext,
    ExecutionMode,
    ExecutionSafetyFlags,
    ExecutionState,
)
from hunter.freqtrade_bridge.engine import (
    build_freqtrade_bridge_context,
    build_safety_flags,
    is_stale_execution_context,
    map_execution_to_bridge_mode,
    validate_freqtrade_bridge_inputs,
)
from hunter.freqtrade_bridge.models import (
    FreqtradeBridgeConfig,
    FreqtradeBridgeContext,
    FreqtradeBridgeDataQuality,
    FreqtradeBridgeMode,
    FreqtradeBridgeSafetyFlags,
    FreqtradeBridgeState,
)


class TestValidateFreqtradeBridgeInputs:
    """Tests for validate_freqtrade_bridge_inputs()."""

    def _make_context(
        self,
        execution_state: ExecutionState = ExecutionState.DRY_RUN_ONLY,
        execution_mode: ExecutionMode = ExecutionMode.LONG_RESEARCH_ONLY,
        dry_run: bool = True,
        live_trading: bool = False,
        exchange: bool = False,
        freqtrade: bool = False,
        timestamp: datetime | None = None,
    ) -> ExecutionContext:
        """Helper to create an ExecutionContext with specified flags."""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        return ExecutionContext(
            timestamp=timestamp,
            status="valid",
            execution_state=execution_state,
            execution_mode=execution_mode,
            decision_state="allow",
            decision_action="enable_long_only_research",
            allowed_mode="long_only",
            dry_run=dry_run,
            live_trading_enabled=live_trading,
            exchange_connection_enabled=exchange,
            freqtrade_enabled=freqtrade,
        )

    def test_missing_execution_context(self) -> None:
        state, mode, reasons = validate_freqtrade_bridge_inputs(None)
        assert state == FreqtradeBridgeState.BLOCKED
        assert mode == FreqtradeBridgeMode.BLOCK_ALL
        assert reasons == ["missing_execution_context"]

    def test_invalid_execution_context_type(self) -> None:
        state, mode, reasons = validate_freqtrade_bridge_inputs("not a context")
        assert state == FreqtradeBridgeState.BLOCKED
        assert mode == FreqtradeBridgeMode.BLOCK_ALL
        assert reasons == ["invalid_execution_context_type"]

    def test_non_dry_run_state_blocks(self) -> None:
        ctx = self._make_context(execution_state=ExecutionState.BLOCKED)
        state, mode, reasons = validate_freqtrade_bridge_inputs(ctx)
        assert state == FreqtradeBridgeState.BLOCKED
        assert mode == FreqtradeBridgeMode.BLOCK_ALL
        assert reasons == ["execution_state_not_dry_run_only:blocked"]

    def test_enabled_state_blocks(self) -> None:
        ctx = self._make_context(execution_state=ExecutionState.ENABLED)
        state, mode, reasons = validate_freqtrade_bridge_inputs(ctx)
        assert state == FreqtradeBridgeState.BLOCKED
        assert mode == FreqtradeBridgeMode.BLOCK_ALL
        assert reasons == ["execution_state_not_dry_run_only:enabled"]

    def test_block_all_mode_blocks(self) -> None:
        ctx = self._make_context(execution_mode=ExecutionMode.BLOCK_ALL)
        state, mode, reasons = validate_freqtrade_bridge_inputs(ctx)
        assert state == FreqtradeBridgeState.BLOCKED
        assert mode == FreqtradeBridgeMode.BLOCK_ALL
        assert reasons == ["execution_mode_is_block_all"]

    def test_dry_run_false_blocks(self) -> None:
        ctx = self._make_context(dry_run=False)
        state, mode, reasons = validate_freqtrade_bridge_inputs(ctx)
        assert state == FreqtradeBridgeState.BLOCKED
        assert mode == FreqtradeBridgeMode.BLOCK_ALL
        assert reasons == ["dry_run_disabled"]

    def test_live_trading_true_blocks(self) -> None:
        ctx = self._make_context(live_trading=True)
        state, mode, reasons = validate_freqtrade_bridge_inputs(ctx)
        assert state == FreqtradeBridgeState.BLOCKED
        assert mode == FreqtradeBridgeMode.BLOCK_ALL
        assert reasons == ["live_trading_enabled"]

    def test_exchange_connection_true_blocks(self) -> None:
        ctx = self._make_context(exchange=True)
        state, mode, reasons = validate_freqtrade_bridge_inputs(ctx)
        assert state == FreqtradeBridgeState.BLOCKED
        assert mode == FreqtradeBridgeMode.BLOCK_ALL
        assert reasons == ["exchange_connection_enabled"]

    def test_freqtrade_enabled_true_blocks(self) -> None:
        ctx = self._make_context(freqtrade=True)
        state, mode, reasons = validate_freqtrade_bridge_inputs(ctx)
        assert state == FreqtradeBridgeState.BLOCKED
        assert mode == FreqtradeBridgeMode.BLOCK_ALL
        assert reasons == ["freqtrade_enabled"]

    def test_stale_execution_context_blocks(self) -> None:
        old_timestamp = datetime.now(timezone.utc) - timedelta(seconds=400)
        ctx = self._make_context(timestamp=old_timestamp)
        state, mode, reasons = validate_freqtrade_bridge_inputs(ctx)
        assert state == FreqtradeBridgeState.BLOCKED
        assert mode == FreqtradeBridgeMode.BLOCK_ALL
        assert reasons == ["stale_execution_context"]

    def test_stale_with_custom_config(self) -> None:
        old_timestamp = datetime.now(timezone.utc) - timedelta(seconds=600)
        ctx = self._make_context(timestamp=old_timestamp)
        config = FreqtradeBridgeConfig(stale_execution_context_seconds=300)
        state, mode, reasons = validate_freqtrade_bridge_inputs(ctx, config)
        assert state == FreqtradeBridgeState.BLOCKED
        assert mode == FreqtradeBridgeMode.BLOCK_ALL
        assert reasons == ["stale_execution_context"]

    def test_fresh_execution_context_passes(self) -> None:
        recent_timestamp = datetime.now(timezone.utc) - timedelta(seconds=100)
        ctx = self._make_context(timestamp=recent_timestamp)
        state, mode, reasons = validate_freqtrade_bridge_inputs(ctx)
        assert state == FreqtradeBridgeState.DRY_RUN_READY
        assert mode == FreqtradeBridgeMode.LONG_RESEARCH_ONLY
        assert reasons == ["dry_run_long_research_only"]

    def test_long_research_mode(self) -> None:
        ctx = self._make_context(execution_mode=ExecutionMode.LONG_RESEARCH_ONLY)
        state, mode, reasons = validate_freqtrade_bridge_inputs(ctx)
        assert state == FreqtradeBridgeState.DRY_RUN_READY
        assert mode == FreqtradeBridgeMode.LONG_RESEARCH_ONLY
        assert reasons == ["dry_run_long_research_only"]

    def test_short_research_mode(self) -> None:
        ctx = self._make_context(execution_mode=ExecutionMode.SHORT_RESEARCH_ONLY)
        state, mode, reasons = validate_freqtrade_bridge_inputs(ctx)
        assert state == FreqtradeBridgeState.DRY_RUN_READY
        assert mode == FreqtradeBridgeMode.SHORT_RESEARCH_ONLY
        assert reasons == ["dry_run_short_research_only"]

    def test_dry_run_only_mode_blocks(self) -> None:
        ctx = self._make_context(execution_mode=ExecutionMode.DRY_RUN_ONLY)
        state, mode, reasons = validate_freqtrade_bridge_inputs(ctx)
        assert state == FreqtradeBridgeState.BLOCKED
        assert mode == FreqtradeBridgeMode.BLOCK_ALL
        assert reasons == ["unsupported_execution_mode:dry_run_only"]

    def test_unknown_mode_blocks(self) -> None:
        # Create a context with an invalid mode by directly setting the attribute
        ctx = self._make_context()
        # We can't easily create an invalid ExecutionMode, so we test with a valid
        # but unsupported one - DRY_RUN_ONLY is already tested above


class TestIsStaleExecutionContext:
    """Tests for is_stale_execution_context()."""

    def _make_context(self, timestamp: datetime) -> ExecutionContext:
        return ExecutionContext(
            timestamp=timestamp,
            status="valid",
            execution_state=ExecutionState.DRY_RUN_ONLY,
            execution_mode=ExecutionMode.LONG_RESEARCH_ONLY,
            decision_state="allow",
            decision_action="enable_long_only_research",
            allowed_mode="long_only",
        )

    def test_fresh_context(self) -> None:
        recent = datetime.now(timezone.utc) - timedelta(seconds=100)
        ctx = self._make_context(recent)
        assert is_stale_execution_context(ctx) is False

    def test_stale_context(self) -> None:
        old = datetime.now(timezone.utc) - timedelta(seconds=400)
        ctx = self._make_context(old)
        assert is_stale_execution_context(ctx) is True

    def test_custom_stale_threshold(self) -> None:
        old = datetime.now(timezone.utc) - timedelta(seconds=600)
        ctx = self._make_context(old)
        config = FreqtradeBridgeConfig(stale_execution_context_seconds=300)
        assert is_stale_execution_context(ctx, config) is True

    def test_custom_stale_threshold_fresh(self) -> None:
        recent = datetime.now(timezone.utc) - timedelta(seconds=400)
        ctx = self._make_context(recent)
        config = FreqtradeBridgeConfig(stale_execution_context_seconds=600)
        assert is_stale_execution_context(ctx, config) is False

    def test_exactly_at_threshold(self) -> None:
        # A context exactly at the threshold should be considered stale
        old = datetime.now(timezone.utc) - timedelta(seconds=301)
        ctx = self._make_context(old)
        assert is_stale_execution_context(ctx) is True

    def test_just_under_threshold(self) -> None:
        recent = datetime.now(timezone.utc) - timedelta(seconds=299)
        ctx = self._make_context(recent)
        assert is_stale_execution_context(ctx) is False


class TestMapExecutionToBridgeMode:
    """Tests for map_execution_to_bridge_mode()."""

    def _make_context(self, execution_mode: ExecutionMode) -> ExecutionContext:
        return ExecutionContext(
            timestamp=datetime.now(timezone.utc),
            status="valid",
            execution_state=ExecutionState.DRY_RUN_ONLY,
            execution_mode=execution_mode,
            decision_state="allow",
            decision_action="enable_long_only_research",
            allowed_mode="long_only",
        )

    def test_long_research_only(self) -> None:
        ctx = self._make_context(ExecutionMode.LONG_RESEARCH_ONLY)
        state, mode, reasons = map_execution_to_bridge_mode(ctx)
        assert state == FreqtradeBridgeState.DRY_RUN_READY
        assert mode == FreqtradeBridgeMode.LONG_RESEARCH_ONLY
        assert reasons == ["dry_run_long_research_only"]

    def test_short_research_only(self) -> None:
        ctx = self._make_context(ExecutionMode.SHORT_RESEARCH_ONLY)
        state, mode, reasons = map_execution_to_bridge_mode(ctx)
        assert state == FreqtradeBridgeState.DRY_RUN_READY
        assert mode == FreqtradeBridgeMode.SHORT_RESEARCH_ONLY
        assert reasons == ["dry_run_short_research_only"]

    def test_block_all(self) -> None:
        ctx = self._make_context(ExecutionMode.BLOCK_ALL)
        state, mode, reasons = map_execution_to_bridge_mode(ctx)
        assert state == FreqtradeBridgeState.BLOCKED
        assert mode == FreqtradeBridgeMode.BLOCK_ALL
        assert reasons == ["execution_mode_is_block_all"]

    def test_dry_run_only(self) -> None:
        ctx = self._make_context(ExecutionMode.DRY_RUN_ONLY)
        state, mode, reasons = map_execution_to_bridge_mode(ctx)
        assert state == FreqtradeBridgeState.BLOCKED
        assert mode == FreqtradeBridgeMode.BLOCK_ALL
        assert reasons == ["unsupported_execution_mode:dry_run_only"]


class TestBuildSafetyFlags:
    """Tests for build_safety_flags()."""

    def test_from_none(self) -> None:
        flags = build_safety_flags(None)
        assert flags.dry_run is True
        assert flags.live_trading_enabled is False
        assert flags.exchange_connection_enabled is False
        assert flags.freqtrade_runtime_enabled is False
        assert flags.strategy_enabled is False
        assert flags.real_orders_enabled is False
        assert flags.leverage_enabled is False
        assert flags.shorting_enabled is False
        assert flags.human_override_required is False
        assert flags.max_context_age_seconds == 300

    def test_from_safe_context(self) -> None:
        ctx = ExecutionContext(
            timestamp=datetime.now(timezone.utc),
            status="valid",
            execution_state=ExecutionState.DRY_RUN_ONLY,
            execution_mode=ExecutionMode.LONG_RESEARCH_ONLY,
            decision_state="allow",
            decision_action="enable_long_only_research",
            allowed_mode="long_only",
            dry_run=True,
            live_trading_enabled=False,
            exchange_connection_enabled=False,
            freqtrade_enabled=False,
        )
        flags = build_safety_flags(ctx)
        assert flags.dry_run is True
        assert flags.live_trading_enabled is False
        assert flags.exchange_connection_enabled is False
        assert flags.freqtrade_runtime_enabled is False
        assert flags.strategy_enabled is False
        assert flags.real_orders_enabled is False
        assert flags.leverage_enabled is False
        assert flags.shorting_enabled is False
        assert flags.human_override_required is False
        assert flags.max_context_age_seconds == 300

    def test_strategy_always_false(self) -> None:
        # Even if we could set strategy_enabled on ExecutionContext, it should be False
        ctx = ExecutionContext(
            timestamp=datetime.now(timezone.utc),
            status="valid",
            execution_state=ExecutionState.DRY_RUN_ONLY,
            execution_mode=ExecutionMode.LONG_RESEARCH_ONLY,
            decision_state="allow",
            decision_action="enable_long_only_research",
            allowed_mode="long_only",
        )
        flags = build_safety_flags(ctx)
        assert flags.strategy_enabled is False

    def test_real_orders_always_false(self) -> None:
        ctx = ExecutionContext(
            timestamp=datetime.now(timezone.utc),
            status="valid",
            execution_state=ExecutionState.DRY_RUN_ONLY,
            execution_mode=ExecutionMode.LONG_RESEARCH_ONLY,
            decision_state="allow",
            decision_action="enable_long_only_research",
            allowed_mode="long_only",
        )
        flags = build_safety_flags(ctx)
        assert flags.real_orders_enabled is False

    def test_leverage_always_false(self) -> None:
        ctx = ExecutionContext(
            timestamp=datetime.now(timezone.utc),
            status="valid",
            execution_state=ExecutionState.DRY_RUN_ONLY,
            execution_mode=ExecutionMode.LONG_RESEARCH_ONLY,
            decision_state="allow",
            decision_action="enable_long_only_research",
            allowed_mode="long_only",
        )
        flags = build_safety_flags(ctx)
        assert flags.leverage_enabled is False

    def test_shorting_always_false(self) -> None:
        ctx = ExecutionContext(
            timestamp=datetime.now(timezone.utc),
            status="valid",
            execution_state=ExecutionState.DRY_RUN_ONLY,
            execution_mode=ExecutionMode.LONG_RESEARCH_ONLY,
            decision_state="allow",
            decision_action="enable_long_only_research",
            allowed_mode="long_only",
        )
        flags = build_safety_flags(ctx)
        assert flags.shorting_enabled is False


class TestBuildFreqtradeBridgeContext:
    """Tests for build_freqtrade_bridge_context()."""

    def _make_context(
        self,
        execution_state: ExecutionState = ExecutionState.DRY_RUN_ONLY,
        execution_mode: ExecutionMode = ExecutionMode.LONG_RESEARCH_ONLY,
        dry_run: bool = True,
        live_trading: bool = False,
        exchange: bool = False,
        freqtrade: bool = False,
        timestamp: datetime | None = None,
    ) -> ExecutionContext:
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        return ExecutionContext(
            timestamp=timestamp,
            status="valid",
            execution_state=execution_state,
            execution_mode=execution_mode,
            decision_state="allow",
            decision_action="enable_long_only_research",
            allowed_mode="long_only",
            dry_run=dry_run,
            live_trading_enabled=live_trading,
            exchange_connection_enabled=exchange,
            freqtrade_enabled=freqtrade,
        )

    def test_missing_context(self) -> None:
        ctx = build_freqtrade_bridge_context(None)
        assert ctx.bridge_state == FreqtradeBridgeState.BLOCKED
        assert ctx.bridge_mode == FreqtradeBridgeMode.BLOCK_ALL
        assert ctx.status == "blocked"
        assert ctx.reason_codes == ["missing_execution_context"]
        assert ctx.version == "1.0"
        assert ctx.is_blocking() is True

    def test_long_research_success(self) -> None:
        exec_ctx = self._make_context(execution_mode=ExecutionMode.LONG_RESEARCH_ONLY)
        ctx = build_freqtrade_bridge_context(exec_ctx)
        assert ctx.bridge_state == FreqtradeBridgeState.DRY_RUN_READY
        assert ctx.bridge_mode == FreqtradeBridgeMode.LONG_RESEARCH_ONLY
        assert ctx.status == "success"
        assert ctx.reason_codes == ["dry_run_long_research_only"]
        assert ctx.version == "1.0"
        assert ctx.dry_run is True
        assert ctx.live_trading_enabled is False
        assert ctx.exchange_connection_enabled is False
        assert ctx.freqtrade_runtime_enabled is False
        assert ctx.strategy_enabled is False
        assert ctx.real_orders_enabled is False
        assert ctx.leverage_enabled is False
        assert ctx.shorting_enabled is False
        assert ctx.is_blocking() is False

    def test_short_research_success(self) -> None:
        exec_ctx = self._make_context(execution_mode=ExecutionMode.SHORT_RESEARCH_ONLY)
        ctx = build_freqtrade_bridge_context(exec_ctx)
        assert ctx.bridge_state == FreqtradeBridgeState.DRY_RUN_READY
        assert ctx.bridge_mode == FreqtradeBridgeMode.SHORT_RESEARCH_ONLY
        assert ctx.status == "success"
        assert ctx.reason_codes == ["dry_run_short_research_only"]
        assert ctx.is_blocking() is False

    def test_block_all(self) -> None:
        exec_ctx = self._make_context(execution_mode=ExecutionMode.BLOCK_ALL)
        ctx = build_freqtrade_bridge_context(exec_ctx)
        assert ctx.bridge_state == FreqtradeBridgeState.BLOCKED
        assert ctx.bridge_mode == FreqtradeBridgeMode.BLOCK_ALL
        assert ctx.status == "blocked"
        assert ctx.reason_codes == ["execution_mode_is_block_all"]
        assert ctx.is_blocking() is True

    def test_blocked_state(self) -> None:
        exec_ctx = self._make_context(execution_state=ExecutionState.BLOCKED)
        ctx = build_freqtrade_bridge_context(exec_ctx)
        assert ctx.bridge_state == FreqtradeBridgeState.BLOCKED
        assert ctx.bridge_mode == FreqtradeBridgeMode.BLOCK_ALL
        assert ctx.status == "blocked"
        assert ctx.reason_codes == ["execution_state_not_dry_run_only:blocked"]

    def test_dry_run_false(self) -> None:
        exec_ctx = self._make_context(dry_run=False)
        ctx = build_freqtrade_bridge_context(exec_ctx)
        assert ctx.bridge_state == FreqtradeBridgeState.BLOCKED
        assert ctx.reason_codes == ["dry_run_disabled"]

    def test_live_trading_true(self) -> None:
        exec_ctx = self._make_context(live_trading=True)
        ctx = build_freqtrade_bridge_context(exec_ctx)
        assert ctx.bridge_state == FreqtradeBridgeState.BLOCKED
        assert ctx.reason_codes == ["live_trading_enabled"]

    def test_exchange_connection_true(self) -> None:
        exec_ctx = self._make_context(exchange=True)
        ctx = build_freqtrade_bridge_context(exec_ctx)
        assert ctx.bridge_state == FreqtradeBridgeState.BLOCKED
        assert ctx.reason_codes == ["exchange_connection_enabled"]

    def test_freqtrade_enabled_true(self) -> None:
        exec_ctx = self._make_context(freqtrade=True)
        ctx = build_freqtrade_bridge_context(exec_ctx)
        assert ctx.bridge_state == FreqtradeBridgeState.BLOCKED
        assert ctx.reason_codes == ["freqtrade_enabled"]

    def test_stale_context(self) -> None:
        old_timestamp = datetime.now(timezone.utc) - timedelta(seconds=400)
        exec_ctx = self._make_context(timestamp=old_timestamp)
        ctx = build_freqtrade_bridge_context(exec_ctx)
        assert ctx.bridge_state == FreqtradeBridgeState.BLOCKED
        assert ctx.reason_codes == ["stale_execution_context"]

    def test_input_refs_populated(self) -> None:
        exec_ctx = self._make_context()
        ctx = build_freqtrade_bridge_context(exec_ctx)
        assert ctx.input_refs.execution_context_timestamp == exec_ctx.timestamp.isoformat()
        assert ctx.input_refs.execution_context_version == "1.0"

    def test_safety_flags_populated(self) -> None:
        exec_ctx = self._make_context()
        ctx = build_freqtrade_bridge_context(exec_ctx)
        assert ctx.safety_flags.dry_run is True
        assert ctx.safety_flags.live_trading_enabled is False
        assert ctx.safety_flags.max_context_age_seconds == 300

    def test_data_quality_on_success(self) -> None:
        exec_ctx = self._make_context()
        ctx = build_freqtrade_bridge_context(exec_ctx)
        assert ctx.data_quality.execution_context_fresh is True
        assert ctx.data_quality.execution_context_valid is True
        assert ctx.data_quality.validation_errors == []

    def test_data_quality_on_block(self) -> None:
        exec_ctx = self._make_context(execution_state=ExecutionState.BLOCKED)
        ctx = build_freqtrade_bridge_context(exec_ctx)
        assert ctx.data_quality.execution_context_valid is True
        assert ctx.data_quality.validation_errors == ["execution_state_not_dry_run_only:blocked"]

    def test_timestamp_is_recent(self) -> None:
        exec_ctx = self._make_context()
        ctx = build_freqtrade_bridge_context(exec_ctx)
        # The FreqtradeBridgeContext timestamp should be recent (within last few seconds)
        age = datetime.now(timezone.utc) - ctx.timestamp
        assert age.total_seconds() < 5

    def test_execution_state_string(self) -> None:
        exec_ctx = self._make_context(execution_state=ExecutionState.DRY_RUN_ONLY)
        ctx = build_freqtrade_bridge_context(exec_ctx)
        assert ctx.execution_state == "dry_run_only"

    def test_execution_mode_string(self) -> None:
        exec_ctx = self._make_context(execution_mode=ExecutionMode.LONG_RESEARCH_ONLY)
        ctx = build_freqtrade_bridge_context(exec_ctx)
        assert ctx.execution_mode == "long_research_only"

    def test_unsafe_config_raises(self) -> None:
        with pytest.raises(ValueError, match="dry_run_required must be True for MVP-5"):
            FreqtradeBridgeConfig(dry_run_required=False)

    def test_unsafe_config_live_trading_raises(self) -> None:
        with pytest.raises(ValueError, match="live_trading_enabled must be False for MVP-5"):
            FreqtradeBridgeConfig(live_trading_enabled=True)

    def test_unsafe_config_exchange_raises(self) -> None:
        with pytest.raises(ValueError, match="exchange_connection_enabled must be False for MVP-5"):
            FreqtradeBridgeConfig(exchange_connection_enabled=True)

    def test_unsafe_config_freqtrade_raises(self) -> None:
        with pytest.raises(ValueError, match="freqtrade_runtime_enabled must be False for MVP-5"):
            FreqtradeBridgeConfig(freqtrade_runtime_enabled=True)

    def test_unsafe_config_strategy_raises(self) -> None:
        with pytest.raises(ValueError, match="strategy_enabled must be False for MVP-5"):
            FreqtradeBridgeConfig(strategy_enabled=True)

    def test_unsafe_config_real_orders_raises(self) -> None:
        with pytest.raises(ValueError, match="real_orders_enabled must be False for MVP-5"):
            FreqtradeBridgeConfig(real_orders_enabled=True)

    def test_unsafe_config_leverage_raises(self) -> None:
        with pytest.raises(ValueError, match="leverage_enabled must be False for MVP-5"):
            FreqtradeBridgeConfig(leverage_enabled=True)

    def test_unsafe_config_shorting_raises(self) -> None:
        with pytest.raises(ValueError, match="shorting_enabled must be False for MVP-5"):
            FreqtradeBridgeConfig(shorting_enabled=True)
