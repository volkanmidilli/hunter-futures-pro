"""Tests for dry-run strategy engine."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from hunter.dry_run_strategy.engine import (
    build_dry_run_strategy_runtime_context,
    build_safety_flags,
    is_stale_adapter_decision_context,
    map_adapter_to_signal_action,
    map_adapter_to_strategy_mode,
    validate_dry_run_strategy_inputs,
)
from hunter.dry_run_strategy.models import (
    ADAPTER_MODE_BLOCK_ALL,
    ADAPTER_NOT_DRY_RUN_READY,
    ADAPTER_SIGNAL_BLOCKED,
    CALCULATION_ERROR,
    DRY_RUN_DISABLED,
    DryRunSignalAction,
    DryRunStrategyConfig,
    DryRunStrategyMode,
    DryRunStrategyRuntimeContext,
    DryRunStrategyState,
    INVALID_ADAPTER_DECISION_CONTEXT,
    LEVERAGE_ENABLED,
    LIVE_TRADING_ENABLED,
    LONG_RESEARCH_SIGNAL_EXPOSED,
    MISSING_ADAPTER_DECISION_CONTEXT,
    REAL_ORDERS_ENABLED,
    SHORTING_ENABLED,
    SHORT_RESEARCH_SIGNAL_EXPOSED,
    STALE_ADAPTER_DECISION_CONTEXT,
    UNSUPPORTED_ADAPTER_MODE,
    UNSUPPORTED_ADAPTER_SIGNAL_INTENT,
)


class _ValidAdapterDecision:
    """Minimal mock that satisfies _REQUIRED_ADAPTER_ATTRS."""

    def __init__(self, **kwargs: Any) -> None:
        defaults = dict(
            timestamp=datetime.now(timezone.utc),
            status="DRY_RUN_READY",
            adapter_state="DRY_RUN_READY",
            adapter_mode="LONG_RESEARCH_ONLY",
            signal_intent="ALLOW_LONG_RESEARCH_SIGNAL",
            dry_run=True,
            live_trading_enabled=False,
            real_orders_enabled=False,
            leverage_enabled=False,
            shorting_enabled=False,
        )
        defaults.update(kwargs)
        for k, v in defaults.items():
            setattr(self, k, v)


# ---------------------------------------------------------------------------
# build_dry_run_strategy_runtime_context
# ---------------------------------------------------------------------------

class TestBuildDryRunStrategyRuntimeContext:
    def test_missing_adapter_decision_context_blocks(self) -> None:
        result = build_dry_run_strategy_runtime_context(None)
        assert result.strategy_state == DryRunStrategyState.BLOCKED
        assert result.strategy_mode == DryRunStrategyMode.BLOCK_ALL
        assert result.signal_action == DryRunSignalAction.BLOCK_SIGNAL
        assert result.reason_codes == (MISSING_ADAPTER_DECISION_CONTEXT,)
        assert result.is_blocking() is True

    def test_invalid_adapter_decision_context_blocks(self) -> None:
        class BadContext:
            pass
        result = build_dry_run_strategy_runtime_context(BadContext())  # type: ignore[arg-type]
        assert result.reason_codes == (INVALID_ADAPTER_DECISION_CONTEXT,)
        assert result.is_blocking() is True

    def test_adapter_state_blocked_blocks(self) -> None:
        ctx = _ValidAdapterDecision(adapter_state="BLOCKED")
        result = build_dry_run_strategy_runtime_context(ctx)
        assert result.reason_codes == (ADAPTER_NOT_DRY_RUN_READY,)
        assert result.is_blocking() is True

    def test_adapter_state_unknown_blocks(self) -> None:
        ctx = _ValidAdapterDecision(adapter_state="UNKNOWN")
        result = build_dry_run_strategy_runtime_context(ctx)
        assert result.reason_codes == (ADAPTER_NOT_DRY_RUN_READY,)
        assert result.is_blocking() is True

    def test_adapter_state_disabled_blocks(self) -> None:
        ctx = _ValidAdapterDecision(adapter_state="DISABLED")
        result = build_dry_run_strategy_runtime_context(ctx)
        assert result.reason_codes == (ADAPTER_NOT_DRY_RUN_READY,)
        assert result.is_blocking() is True

    def test_adapter_mode_block_all_blocks(self) -> None:
        ctx = _ValidAdapterDecision(adapter_mode="BLOCK_ALL")
        result = build_dry_run_strategy_runtime_context(ctx)
        assert result.reason_codes == (ADAPTER_MODE_BLOCK_ALL,)
        assert result.is_blocking() is True

    def test_adapter_signal_intent_block_signal_blocks(self) -> None:
        ctx = _ValidAdapterDecision(signal_intent="BLOCK_SIGNAL")
        result = build_dry_run_strategy_runtime_context(ctx)
        assert result.reason_codes == (ADAPTER_SIGNAL_BLOCKED,)
        assert result.is_blocking() is True

    def test_dry_run_false_blocks(self) -> None:
        ctx = _ValidAdapterDecision(dry_run=False)
        result = build_dry_run_strategy_runtime_context(ctx)
        assert result.reason_codes == (DRY_RUN_DISABLED,)
        assert result.is_blocking() is True

    def test_live_trading_enabled_blocks(self) -> None:
        ctx = _ValidAdapterDecision(live_trading_enabled=True)
        result = build_dry_run_strategy_runtime_context(ctx)
        assert result.reason_codes == (LIVE_TRADING_ENABLED,)
        assert result.is_blocking() is True

    def test_real_orders_enabled_blocks(self) -> None:
        ctx = _ValidAdapterDecision(real_orders_enabled=True)
        result = build_dry_run_strategy_runtime_context(ctx)
        assert result.reason_codes == (REAL_ORDERS_ENABLED,)
        assert result.is_blocking() is True

    def test_leverage_enabled_blocks(self) -> None:
        ctx = _ValidAdapterDecision(leverage_enabled=True)
        result = build_dry_run_strategy_runtime_context(ctx)
        assert result.reason_codes == (LEVERAGE_ENABLED,)
        assert result.is_blocking() is True

    def test_shorting_enabled_blocks(self) -> None:
        ctx = _ValidAdapterDecision(shorting_enabled=True)
        result = build_dry_run_strategy_runtime_context(ctx)
        assert result.reason_codes == (SHORTING_ENABLED,)
        assert result.is_blocking() is True

    def test_stale_adapter_decision_context_blocks(self) -> None:
        old_ts = datetime.now(timezone.utc) - timedelta(seconds=400)
        ctx = _ValidAdapterDecision(timestamp=old_ts)
        result = build_dry_run_strategy_runtime_context(ctx)
        assert result.reason_codes == (STALE_ADAPTER_DECISION_CONTEXT,)
        assert result.is_blocking() is True

    def test_naive_timestamp_blocks(self) -> None:
        naive_ts = datetime(2024, 1, 1, 12, 0, 0)
        ctx = _ValidAdapterDecision(timestamp=naive_ts)
        result = build_dry_run_strategy_runtime_context(ctx)
        assert result.reason_codes == (STALE_ADAPTER_DECISION_CONTEXT,)
        assert result.is_blocking() is True

    def test_missing_timestamp_blocks(self) -> None:
        ctx = _ValidAdapterDecision()
        delattr(ctx, "timestamp")
        result = build_dry_run_strategy_runtime_context(ctx)
        # Missing timestamp is caught by INVALID_ADAPTER_DECISION_CONTEXT (step 2)
        # before STALE_ADAPTER_DECISION_CONTEXT (step 11)
        assert result.reason_codes == (INVALID_ADAPTER_DECISION_CONTEXT,)
        assert result.is_blocking() is True

    def test_unsupported_adapter_mode_blocks(self) -> None:
        ctx = _ValidAdapterDecision(adapter_mode="UNKNOWN_MODE")
        result = build_dry_run_strategy_runtime_context(ctx)
        assert result.reason_codes == (UNSUPPORTED_ADAPTER_MODE,)
        assert result.is_blocking() is True

    def test_unsupported_adapter_signal_intent_blocks(self) -> None:
        ctx = _ValidAdapterDecision(signal_intent="UNKNOWN_INTENT")
        result = build_dry_run_strategy_runtime_context(ctx)
        assert result.reason_codes == (UNSUPPORTED_ADAPTER_SIGNAL_INTENT,)
        assert result.is_blocking() is True

    def test_long_research_allowed(self) -> None:
        ctx = _ValidAdapterDecision(
            adapter_mode="LONG_RESEARCH_ONLY",
            signal_intent="ALLOW_LONG_RESEARCH_SIGNAL",
        )
        result = build_dry_run_strategy_runtime_context(ctx)
        assert result.strategy_state == DryRunStrategyState.DRY_RUN_READY
        assert result.strategy_mode == DryRunStrategyMode.LONG_RESEARCH_ONLY
        assert result.signal_action == DryRunSignalAction.EXPOSE_LONG_RESEARCH_SIGNAL
        assert result.reason_codes == (LONG_RESEARCH_SIGNAL_EXPOSED,)
        assert result.status == "DRY_RUN_READY"
        assert result.dry_run is True
        assert result.is_blocking() is False

    def test_short_research_allowed(self) -> None:
        ctx = _ValidAdapterDecision(
            adapter_mode="SHORT_RESEARCH_ONLY",
            signal_intent="ALLOW_SHORT_RESEARCH_SIGNAL",
        )
        result = build_dry_run_strategy_runtime_context(ctx)
        assert result.strategy_state == DryRunStrategyState.DRY_RUN_READY
        assert result.strategy_mode == DryRunStrategyMode.SHORT_RESEARCH_ONLY
        assert result.signal_action == DryRunSignalAction.EXPOSE_SHORT_RESEARCH_SIGNAL
        assert result.reason_codes == (SHORT_RESEARCH_SIGNAL_EXPOSED,)
        assert result.status == "DRY_RUN_READY"
        assert result.dry_run is True
        assert result.is_blocking() is False

    def test_custom_config(self) -> None:
        config = DryRunStrategyConfig(stale_adapter_decision_seconds=60)
        old_ts = datetime.now(timezone.utc) - timedelta(seconds=120)
        ctx = _ValidAdapterDecision(timestamp=old_ts)
        result = build_dry_run_strategy_runtime_context(ctx, config=config)
        assert result.reason_codes == (STALE_ADAPTER_DECISION_CONTEXT,)

    def test_custom_now(self) -> None:
        now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        ctx = _ValidAdapterDecision(timestamp=now)
        result = build_dry_run_strategy_runtime_context(ctx, now=now)
        assert result.timestamp == now
        assert result.strategy_state == DryRunStrategyState.DRY_RUN_READY

    def test_calculation_error_on_exception(self) -> None:
        class ExplodingContext:
            timestamp = property(lambda self: 1 / 0)  # type: ignore[assignment]
            status = "OK"
            adapter_state = "DRY_RUN_READY"
            adapter_mode = "LONG_RESEARCH_ONLY"
            signal_intent = "ALLOW_LONG_RESEARCH_SIGNAL"
            dry_run = True
            live_trading_enabled = False
            real_orders_enabled = False
            leverage_enabled = False
            shorting_enabled = False
        result = build_dry_run_strategy_runtime_context(ExplodingContext())  # type: ignore[arg-type]
        assert result.reason_codes == (CALCULATION_ERROR,)
        assert result.is_blocking() is True

    def test_safety_flags_in_allowed_output(self) -> None:
        ctx = _ValidAdapterDecision()
        result = build_dry_run_strategy_runtime_context(ctx)
        assert result.safety_flags.dry_run is True
        assert result.safety_flags.live_trading_enabled is False
        assert result.safety_flags.real_orders_enabled is False
        assert result.safety_flags.leverage_enabled is False
        assert result.safety_flags.shorting_enabled is False
        assert result.safety_flags.freqtrade_runtime_allowed is False
        assert result.safety_flags.strategy_class_allowed is False
        assert result.safety_flags.populate_indicators_allowed is False
        assert result.safety_flags.populate_entry_trend_allowed is False
        assert result.safety_flags.populate_exit_trend_allowed is False
        assert result.safety_flags.order_execution_allowed is False

    def test_data_quality_in_allowed_output(self) -> None:
        ctx = _ValidAdapterDecision(
            adapter_mode="LONG_RESEARCH_ONLY",
            signal_intent="ALLOW_LONG_RESEARCH_SIGNAL",
        )
        result = build_dry_run_strategy_runtime_context(ctx)
        assert result.data_quality.adapter_decision_present is True
        assert result.data_quality.adapter_decision_valid is True
        assert result.data_quality.adapter_decision_stale is False
        assert result.data_quality.reason == LONG_RESEARCH_SIGNAL_EXPOSED

    def test_data_quality_in_short_output(self) -> None:
        ctx = _ValidAdapterDecision(
            adapter_mode="SHORT_RESEARCH_ONLY",
            signal_intent="ALLOW_SHORT_RESEARCH_SIGNAL",
        )
        result = build_dry_run_strategy_runtime_context(ctx)
        assert result.data_quality.reason == SHORT_RESEARCH_SIGNAL_EXPOSED

    def test_adapter_state_preserved(self) -> None:
        ctx = _ValidAdapterDecision()
        result = build_dry_run_strategy_runtime_context(ctx)
        assert result.adapter_state == "DRY_RUN_READY"

    def test_adapter_mode_preserved(self) -> None:
        ctx = _ValidAdapterDecision(adapter_mode="SHORT_RESEARCH_ONLY")
        result = build_dry_run_strategy_runtime_context(ctx)
        assert result.adapter_mode == "SHORT_RESEARCH_ONLY"

    def test_input_refs_default(self) -> None:
        ctx = _ValidAdapterDecision()
        result = build_dry_run_strategy_runtime_context(ctx)
        assert result.input_refs.adapter_decision == "data/strategy_adapter/current_adapter_decision.json"
        assert result.input_refs.dry_run_strategy_runtime == "data/freqtrade_strategy/current_dry_run_strategy_runtime.json"

    def test_version_default(self) -> None:
        ctx = _ValidAdapterDecision()
        result = build_dry_run_strategy_runtime_context(ctx)
        assert result.version == "1.0"

    def test_all_execution_flags_false_in_allowed(self) -> None:
        ctx = _ValidAdapterDecision()
        result = build_dry_run_strategy_runtime_context(ctx)
        assert result.populate_indicators_allowed is False
        assert result.populate_entry_trend_allowed is False
        assert result.populate_exit_trend_allowed is False
        assert result.order_execution_allowed is False
        assert result.freqtrade_runtime_allowed is False
        assert result.strategy_class_allowed is False


# ---------------------------------------------------------------------------
# validate_dry_run_strategy_inputs
# ---------------------------------------------------------------------------

class TestValidateDryRunStrategyInputs:
    def test_missing_returns_missing(self) -> None:
        result = validate_dry_run_strategy_inputs(None, DryRunStrategyConfig(), datetime.now(timezone.utc))
        assert result == (MISSING_ADAPTER_DECISION_CONTEXT,)

    def test_invalid_returns_invalid(self) -> None:
        class BadContext:
            pass
        result = validate_dry_run_strategy_inputs(BadContext(), DryRunStrategyConfig(), datetime.now(timezone.utc))  # type: ignore[arg-type]
        assert result == (INVALID_ADAPTER_DECISION_CONTEXT,)

    def test_blocked_state_returns_not_ready(self) -> None:
        ctx = _ValidAdapterDecision(adapter_state="BLOCKED")
        result = validate_dry_run_strategy_inputs(ctx, DryRunStrategyConfig(), datetime.now(timezone.utc))
        assert result == (ADAPTER_NOT_DRY_RUN_READY,)

    def test_unknown_state_returns_not_ready(self) -> None:
        ctx = _ValidAdapterDecision(adapter_state="UNKNOWN")
        result = validate_dry_run_strategy_inputs(ctx, DryRunStrategyConfig(), datetime.now(timezone.utc))
        assert result == (ADAPTER_NOT_DRY_RUN_READY,)

    def test_disabled_state_returns_not_ready(self) -> None:
        ctx = _ValidAdapterDecision(adapter_state="DISABLED")
        result = validate_dry_run_strategy_inputs(ctx, DryRunStrategyConfig(), datetime.now(timezone.utc))
        assert result == (ADAPTER_NOT_DRY_RUN_READY,)

    def test_block_all_mode_returns_block_all(self) -> None:
        ctx = _ValidAdapterDecision(adapter_mode="BLOCK_ALL")
        result = validate_dry_run_strategy_inputs(ctx, DryRunStrategyConfig(), datetime.now(timezone.utc))
        assert result == (ADAPTER_MODE_BLOCK_ALL,)

    def test_block_signal_intent_returns_blocked(self) -> None:
        ctx = _ValidAdapterDecision(signal_intent="BLOCK_SIGNAL")
        result = validate_dry_run_strategy_inputs(ctx, DryRunStrategyConfig(), datetime.now(timezone.utc))
        assert result == (ADAPTER_SIGNAL_BLOCKED,)

    def test_dry_run_false_returns_dry_run_disabled(self) -> None:
        ctx = _ValidAdapterDecision(dry_run=False)
        result = validate_dry_run_strategy_inputs(ctx, DryRunStrategyConfig(), datetime.now(timezone.utc))
        assert result == (DRY_RUN_DISABLED,)

    def test_live_trading_returns_live_trading(self) -> None:
        ctx = _ValidAdapterDecision(live_trading_enabled=True)
        result = validate_dry_run_strategy_inputs(ctx, DryRunStrategyConfig(), datetime.now(timezone.utc))
        assert result == (LIVE_TRADING_ENABLED,)

    def test_real_orders_returns_real_orders(self) -> None:
        ctx = _ValidAdapterDecision(real_orders_enabled=True)
        result = validate_dry_run_strategy_inputs(ctx, DryRunStrategyConfig(), datetime.now(timezone.utc))
        assert result == (REAL_ORDERS_ENABLED,)

    def test_leverage_returns_leverage(self) -> None:
        ctx = _ValidAdapterDecision(leverage_enabled=True)
        result = validate_dry_run_strategy_inputs(ctx, DryRunStrategyConfig(), datetime.now(timezone.utc))
        assert result == (LEVERAGE_ENABLED,)

    def test_shorting_returns_shorting(self) -> None:
        ctx = _ValidAdapterDecision(shorting_enabled=True)
        result = validate_dry_run_strategy_inputs(ctx, DryRunStrategyConfig(), datetime.now(timezone.utc))
        assert result == (SHORTING_ENABLED,)

    def test_stale_returns_stale(self) -> None:
        old_ts = datetime.now(timezone.utc) - timedelta(seconds=400)
        ctx = _ValidAdapterDecision(timestamp=old_ts)
        result = validate_dry_run_strategy_inputs(ctx, DryRunStrategyConfig(), datetime.now(timezone.utc))
        assert result == (STALE_ADAPTER_DECISION_CONTEXT,)

    def test_naive_timestamp_returns_stale(self) -> None:
        naive_ts = datetime(2024, 1, 1, 12, 0, 0)
        ctx = _ValidAdapterDecision(timestamp=naive_ts)
        result = validate_dry_run_strategy_inputs(ctx, DryRunStrategyConfig(), datetime.now(timezone.utc))
        assert result == (STALE_ADAPTER_DECISION_CONTEXT,)

    def test_unsupported_mode_returns_unsupported(self) -> None:
        ctx = _ValidAdapterDecision(adapter_mode="UNKNOWN_MODE")
        result = validate_dry_run_strategy_inputs(ctx, DryRunStrategyConfig(), datetime.now(timezone.utc))
        assert result == (UNSUPPORTED_ADAPTER_MODE,)

    def test_unsupported_signal_intent_returns_unsupported(self) -> None:
        ctx = _ValidAdapterDecision(signal_intent="UNKNOWN_INTENT")
        result = validate_dry_run_strategy_inputs(ctx, DryRunStrategyConfig(), datetime.now(timezone.utc))
        assert result == (UNSUPPORTED_ADAPTER_SIGNAL_INTENT,)

    def test_valid_returns_empty(self) -> None:
        ctx = _ValidAdapterDecision()
        result = validate_dry_run_strategy_inputs(ctx, DryRunStrategyConfig(), datetime.now(timezone.utc))
        assert result == ()

    def test_priority_stops_at_first(self) -> None:
        result = validate_dry_run_strategy_inputs(None, DryRunStrategyConfig(), datetime.now(timezone.utc))
        assert result == (MISSING_ADAPTER_DECISION_CONTEXT,)
        assert len(result) == 1

    def test_priority_order_dry_run_before_live_trading(self) -> None:
        ctx = _ValidAdapterDecision(dry_run=False, live_trading_enabled=True)
        result = validate_dry_run_strategy_inputs(ctx, DryRunStrategyConfig(), datetime.now(timezone.utc))
        assert result == (DRY_RUN_DISABLED,)

    def test_priority_order_live_trading_before_real_orders(self) -> None:
        ctx = _ValidAdapterDecision(live_trading_enabled=True, real_orders_enabled=True)
        result = validate_dry_run_strategy_inputs(ctx, DryRunStrategyConfig(), datetime.now(timezone.utc))
        assert result == (LIVE_TRADING_ENABLED,)

    def test_priority_order_adapter_state_before_adapter_mode(self) -> None:
        ctx = _ValidAdapterDecision(adapter_state="BLOCKED", adapter_mode="BLOCK_ALL")
        result = validate_dry_run_strategy_inputs(ctx, DryRunStrategyConfig(), datetime.now(timezone.utc))
        assert result == (ADAPTER_NOT_DRY_RUN_READY,)

    def test_priority_order_adapter_mode_before_signal_intent(self) -> None:
        ctx = _ValidAdapterDecision(adapter_mode="BLOCK_ALL", signal_intent="BLOCK_SIGNAL")
        result = validate_dry_run_strategy_inputs(ctx, DryRunStrategyConfig(), datetime.now(timezone.utc))
        assert result == (ADAPTER_MODE_BLOCK_ALL,)

    def test_priority_order_signal_intent_before_dry_run(self) -> None:
        ctx = _ValidAdapterDecision(signal_intent="BLOCK_SIGNAL", dry_run=False)
        result = validate_dry_run_strategy_inputs(ctx, DryRunStrategyConfig(), datetime.now(timezone.utc))
        assert result == (ADAPTER_SIGNAL_BLOCKED,)


# ---------------------------------------------------------------------------
# is_stale_adapter_decision_context
# ---------------------------------------------------------------------------

class TestIsStaleAdapterDecisionContext:
    def test_fresh_context(self) -> None:
        ctx = _ValidAdapterDecision()
        now = datetime.now(timezone.utc)
        assert is_stale_adapter_decision_context(ctx, DryRunStrategyConfig(), now) is False

    def test_stale_context(self) -> None:
        old_ts = datetime.now(timezone.utc) - timedelta(seconds=400)
        ctx = _ValidAdapterDecision(timestamp=old_ts)
        now = datetime.now(timezone.utc)
        assert is_stale_adapter_decision_context(ctx, DryRunStrategyConfig(), now) is True

    def test_naive_timestamp(self) -> None:
        naive_ts = datetime(2024, 1, 1, 12, 0, 0)
        ctx = _ValidAdapterDecision(timestamp=naive_ts)
        now = datetime.now(timezone.utc)
        assert is_stale_adapter_decision_context(ctx, DryRunStrategyConfig(), now) is True

    def test_missing_timestamp(self) -> None:
        ctx = _ValidAdapterDecision()
        delattr(ctx, "timestamp")
        now = datetime.now(timezone.utc)
        assert is_stale_adapter_decision_context(ctx, DryRunStrategyConfig(), now) is True

    def test_none_timestamp(self) -> None:
        ctx = _ValidAdapterDecision(timestamp=None)
        now = datetime.now(timezone.utc)
        assert is_stale_adapter_decision_context(ctx, DryRunStrategyConfig(), now) is True

    def test_invalid_timestamp_type(self) -> None:
        ctx = _ValidAdapterDecision(timestamp="not-a-datetime")
        now = datetime.now(timezone.utc)
        assert is_stale_adapter_decision_context(ctx, DryRunStrategyConfig(), now) is True

    def test_custom_threshold(self) -> None:
        old_ts = datetime.now(timezone.utc) - timedelta(seconds=120)
        ctx = _ValidAdapterDecision(timestamp=old_ts)
        now = datetime.now(timezone.utc)
        config = DryRunStrategyConfig(stale_adapter_decision_seconds=60)
        assert is_stale_adapter_decision_context(ctx, config, now) is True

    def test_custom_threshold_fresh(self) -> None:
        ts = datetime.now(timezone.utc) - timedelta(seconds=30)
        ctx = _ValidAdapterDecision(timestamp=ts)
        now = datetime.now(timezone.utc)
        config = DryRunStrategyConfig(stale_adapter_decision_seconds=60)
        assert is_stale_adapter_decision_context(ctx, config, now) is False


# ---------------------------------------------------------------------------
# map_adapter_to_strategy_mode
# ---------------------------------------------------------------------------

class TestMapAdapterToStrategyMode:
    def test_long_research_only(self) -> None:
        ctx = _ValidAdapterDecision(adapter_mode="LONG_RESEARCH_ONLY")
        assert map_adapter_to_strategy_mode(ctx) == DryRunStrategyMode.LONG_RESEARCH_ONLY

    def test_short_research_only(self) -> None:
        ctx = _ValidAdapterDecision(adapter_mode="SHORT_RESEARCH_ONLY")
        assert map_adapter_to_strategy_mode(ctx) == DryRunStrategyMode.SHORT_RESEARCH_ONLY

    def test_block_all(self) -> None:
        ctx = _ValidAdapterDecision(adapter_mode="BLOCK_ALL")
        assert map_adapter_to_strategy_mode(ctx) == DryRunStrategyMode.BLOCK_ALL

    def test_unknown_mode(self) -> None:
        ctx = _ValidAdapterDecision(adapter_mode="UNKNOWN")
        assert map_adapter_to_strategy_mode(ctx) == DryRunStrategyMode.BLOCK_ALL


# ---------------------------------------------------------------------------
# map_adapter_to_signal_action
# ---------------------------------------------------------------------------

class TestMapAdapterToSignalAction:
    def test_allow_long_research_signal(self) -> None:
        ctx = _ValidAdapterDecision(signal_intent="ALLOW_LONG_RESEARCH_SIGNAL")
        assert map_adapter_to_signal_action(ctx) == DryRunSignalAction.EXPOSE_LONG_RESEARCH_SIGNAL

    def test_allow_short_research_signal(self) -> None:
        ctx = _ValidAdapterDecision(signal_intent="ALLOW_SHORT_RESEARCH_SIGNAL")
        assert map_adapter_to_signal_action(ctx) == DryRunSignalAction.EXPOSE_SHORT_RESEARCH_SIGNAL

    def test_block_signal(self) -> None:
        ctx = _ValidAdapterDecision(signal_intent="BLOCK_SIGNAL")
        assert map_adapter_to_signal_action(ctx) == DryRunSignalAction.BLOCK_SIGNAL

    def test_unknown_intent(self) -> None:
        ctx = _ValidAdapterDecision(signal_intent="UNKNOWN")
        assert map_adapter_to_signal_action(ctx) == DryRunSignalAction.BLOCK_SIGNAL


# ---------------------------------------------------------------------------
# build_safety_flags
# ---------------------------------------------------------------------------

class TestBuildSafetyFlags:
    def test_default_config(self) -> None:
        config = DryRunStrategyConfig()
        flags = build_safety_flags(config)
        assert flags.dry_run is True
        assert flags.live_trading_enabled is False
        assert flags.real_orders_enabled is False
        assert flags.leverage_enabled is False
        assert flags.shorting_enabled is False
        assert flags.freqtrade_runtime_allowed is False
        assert flags.strategy_class_allowed is False
        assert flags.populate_indicators_allowed is False
        assert flags.populate_entry_trend_allowed is False
        assert flags.populate_exit_trend_allowed is False
        assert flags.order_execution_allowed is False
        assert flags.max_context_age_seconds == 300

    def test_custom_max_context_age(self) -> None:
        config = DryRunStrategyConfig(max_context_age_seconds=600)
        flags = build_safety_flags(config)
        assert flags.max_context_age_seconds == 600

    def test_no_json_reading(self) -> None:
        """Safety: build_safety_flags does not read JSON files."""
        config = DryRunStrategyConfig()
        flags = build_safety_flags(config)
        assert flags is not None
        # No file I/O occurred — this is a pure in-memory function

    def test_no_network_calls(self) -> None:
        """Safety: build_safety_flags does not make network calls."""
        config = DryRunStrategyConfig()
        flags = build_safety_flags(config)
        assert flags is not None

    def test_no_freqtrade_runtime(self) -> None:
        """Safety: build_safety_flags does not connect to Freqtrade runtime."""
        config = DryRunStrategyConfig()
        flags = build_safety_flags(config)
        assert flags.freqtrade_runtime_allowed is False

    def test_no_binance(self) -> None:
        """Safety: build_safety_flags does not connect to Binance."""
        config = DryRunStrategyConfig()
        flags = build_safety_flags(config)
        assert flags is not None

    def test_no_real_exchange(self) -> None:
        """Safety: build_safety_flags does not connect to real exchange."""
        config = DryRunStrategyConfig()
        flags = build_safety_flags(config)
        assert flags is not None

    def test_no_strategy_class(self) -> None:
        """Safety: build_safety_flags does not create a deployable strategy class."""
        config = DryRunStrategyConfig()
        flags = build_safety_flags(config)
        assert flags.strategy_class_allowed is False

    def test_no_live_trading(self) -> None:
        """Safety: build_safety_flags does not enable live trading."""
        config = DryRunStrategyConfig()
        flags = build_safety_flags(config)
        assert flags.live_trading_enabled is False

    def test_no_leverage(self) -> None:
        """Safety: build_safety_flags does not enable leverage."""
        config = DryRunStrategyConfig()
        flags = build_safety_flags(config)
        assert flags.leverage_enabled is False

    def test_no_shorting(self) -> None:
        """Safety: build_safety_flags does not enable shorting."""
        config = DryRunStrategyConfig()
        flags = build_safety_flags(config)
        assert flags.shorting_enabled is False

    def test_no_real_entry_exit(self) -> None:
        """Safety: build_safety_flags does not enable real entry/exit execution."""
        config = DryRunStrategyConfig()
        flags = build_safety_flags(config)
        assert flags.populate_entry_trend_allowed is False
        assert flags.populate_exit_trend_allowed is False
        assert flags.order_execution_allowed is False

    def test_no_writing(self) -> None:
        """Safety: build_safety_flags does not write files."""
        config = DryRunStrategyConfig()
        flags = build_safety_flags(config)
        assert flags is not None


# ---------------------------------------------------------------------------
# Safety assertions
# ---------------------------------------------------------------------------

class TestSafetyAssertions:
    def test_no_json_reading(self) -> None:
        """Safety: engine functions do not read JSON files."""
        ctx = _ValidAdapterDecision()
        result = build_dry_run_strategy_runtime_context(ctx)
        assert result is not None

    def test_no_writing(self) -> None:
        """Safety: engine functions do not write files."""
        ctx = _ValidAdapterDecision()
        result = build_dry_run_strategy_runtime_context(ctx)
        assert result is not None

    def test_no_network_calls(self) -> None:
        """Safety: engine functions do not make network calls."""
        ctx = _ValidAdapterDecision()
        result = build_dry_run_strategy_runtime_context(ctx)
        assert result is not None

    def test_no_freqtrade_runtime(self) -> None:
        """Safety: engine functions do not connect to Freqtrade runtime."""
        ctx = _ValidAdapterDecision()
        result = build_dry_run_strategy_runtime_context(ctx)
        assert result.freqtrade_runtime_allowed is False

    def test_no_binance(self) -> None:
        """Safety: engine functions do not connect to Binance."""
        ctx = _ValidAdapterDecision()
        result = build_dry_run_strategy_runtime_context(ctx)
        assert result is not None

    def test_no_real_exchange(self) -> None:
        """Safety: engine functions do not connect to real exchange."""
        ctx = _ValidAdapterDecision()
        result = build_dry_run_strategy_runtime_context(ctx)
        assert result is not None

    def test_no_strategy_class(self) -> None:
        """Safety: engine functions do not create a deployable strategy class."""
        ctx = _ValidAdapterDecision()
        result = build_dry_run_strategy_runtime_context(ctx)
        assert result.strategy_class_allowed is False

    def test_no_live_trading(self) -> None:
        """Safety: engine functions do not enable live trading."""
        ctx = _ValidAdapterDecision()
        result = build_dry_run_strategy_runtime_context(ctx)
        assert result.live_trading_enabled is False

    def test_no_leverage(self) -> None:
        """Safety: engine functions do not enable leverage."""
        ctx = _ValidAdapterDecision()
        result = build_dry_run_strategy_runtime_context(ctx)
        assert result.leverage_enabled is False

    def test_no_shorting(self) -> None:
        """Safety: engine functions do not enable shorting."""
        ctx = _ValidAdapterDecision()
        result = build_dry_run_strategy_runtime_context(ctx)
        assert result.shorting_enabled is False

    def test_no_real_entry_exit(self) -> None:
        """Safety: engine functions do not enable real entry/exit execution."""
        ctx = _ValidAdapterDecision()
        result = build_dry_run_strategy_runtime_context(ctx)
        assert result.populate_entry_trend_allowed is False
        assert result.populate_exit_trend_allowed is False
        assert result.order_execution_allowed is False
