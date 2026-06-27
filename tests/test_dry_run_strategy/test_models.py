"""Tests for dry-run strategy models."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from typing import Any

import pytest

from hunter.dry_run_strategy.models import (
    ADAPTER_MODE_BLOCK_ALL,
    ADAPTER_NOT_DRY_RUN_READY,
    ADAPTER_SIGNAL_BLOCKED,
    CALCULATION_ERROR,
    DEFAULT_BLOCK_SIGNAL,
    DRY_RUN_DISABLED,
    DryRunSignalAction,
    DryRunStrategyConfig,
    DryRunStrategyDataQuality,
    DryRunStrategyInputRefs,
    DryRunStrategyMode,
    DryRunStrategyRuntimeContext,
    DryRunStrategySafetyFlags,
    DryRunStrategyState,
    INVALID_ADAPTER_DECISION_CONTEXT,
    LIVE_TRADING_ENABLED,
    LONG_RESEARCH_SIGNAL_EXPOSED,
    LEVERAGE_ENABLED,
    MISSING_ADAPTER_DECISION_CONTEXT,
    REAL_ORDERS_ENABLED,
    REASON_CODES,
    SHORTING_ENABLED,
    SHORT_RESEARCH_SIGNAL_EXPOSED,
    STALE_ADAPTER_DECISION_CONTEXT,
    UNSUPPORTED_ADAPTER_MODE,
    UNSUPPORTED_ADAPTER_SIGNAL_INTENT,
)


class TestDryRunStrategyState:
    def test_disabled(self) -> None:
        assert DryRunStrategyState.DISABLED == "DISABLED"
        assert DryRunStrategyState.DISABLED.value == "DISABLED"

    def test_dry_run_ready(self) -> None:
        assert DryRunStrategyState.DRY_RUN_READY == "DRY_RUN_READY"
        assert DryRunStrategyState.DRY_RUN_READY.value == "DRY_RUN_READY"

    def test_blocked(self) -> None:
        assert DryRunStrategyState.BLOCKED == "BLOCKED"
        assert DryRunStrategyState.BLOCKED.value == "BLOCKED"

    def test_unknown(self) -> None:
        assert DryRunStrategyState.UNKNOWN == "UNKNOWN"
        assert DryRunStrategyState.UNKNOWN.value == "UNKNOWN"

    def test_members(self) -> None:
        assert list(DryRunStrategyState) == [
            DryRunStrategyState.DISABLED,
            DryRunStrategyState.DRY_RUN_READY,
            DryRunStrategyState.BLOCKED,
            DryRunStrategyState.UNKNOWN,
        ]


class TestDryRunStrategyMode:
    def test_long_research_only(self) -> None:
        assert DryRunStrategyMode.LONG_RESEARCH_ONLY == "LONG_RESEARCH_ONLY"
        assert DryRunStrategyMode.LONG_RESEARCH_ONLY.value == "LONG_RESEARCH_ONLY"

    def test_short_research_only(self) -> None:
        assert DryRunStrategyMode.SHORT_RESEARCH_ONLY == "SHORT_RESEARCH_ONLY"
        assert DryRunStrategyMode.SHORT_RESEARCH_ONLY.value == "SHORT_RESEARCH_ONLY"

    def test_block_all(self) -> None:
        assert DryRunStrategyMode.BLOCK_ALL == "BLOCK_ALL"
        assert DryRunStrategyMode.BLOCK_ALL.value == "BLOCK_ALL"

    def test_members(self) -> None:
        assert list(DryRunStrategyMode) == [
            DryRunStrategyMode.LONG_RESEARCH_ONLY,
            DryRunStrategyMode.SHORT_RESEARCH_ONLY,
            DryRunStrategyMode.BLOCK_ALL,
        ]


class TestDryRunSignalAction:
    def test_expose_long_research_signal(self) -> None:
        assert DryRunSignalAction.EXPOSE_LONG_RESEARCH_SIGNAL == "EXPOSE_LONG_RESEARCH_SIGNAL"
        assert DryRunSignalAction.EXPOSE_LONG_RESEARCH_SIGNAL.value == "EXPOSE_LONG_RESEARCH_SIGNAL"

    def test_expose_short_research_signal(self) -> None:
        assert DryRunSignalAction.EXPOSE_SHORT_RESEARCH_SIGNAL == "EXPOSE_SHORT_RESEARCH_SIGNAL"
        assert DryRunSignalAction.EXPOSE_SHORT_RESEARCH_SIGNAL.value == "EXPOSE_SHORT_RESEARCH_SIGNAL"

    def test_block_signal(self) -> None:
        assert DryRunSignalAction.BLOCK_SIGNAL == "BLOCK_SIGNAL"
        assert DryRunSignalAction.BLOCK_SIGNAL.value == "BLOCK_SIGNAL"

    def test_no_signal(self) -> None:
        assert DryRunSignalAction.NO_SIGNAL == "NO_SIGNAL"
        assert DryRunSignalAction.NO_SIGNAL.value == "NO_SIGNAL"

    def test_members(self) -> None:
        assert list(DryRunSignalAction) == [
            DryRunSignalAction.EXPOSE_LONG_RESEARCH_SIGNAL,
            DryRunSignalAction.EXPOSE_SHORT_RESEARCH_SIGNAL,
            DryRunSignalAction.BLOCK_SIGNAL,
            DryRunSignalAction.NO_SIGNAL,
        ]


class TestDryRunStrategyConfig:
    def test_defaults(self) -> None:
        config = DryRunStrategyConfig()
        assert config.stale_adapter_decision_seconds == 300
        assert config.max_context_age_seconds == 300
        assert config.dry_run_required is True
        assert config.live_trading_enabled is False
        assert config.real_orders_enabled is False
        assert config.leverage_enabled is False
        assert config.shorting_enabled is False
        assert config.freqtrade_runtime_allowed is False
        assert config.strategy_class_allowed is False
        assert config.populate_indicators_allowed is False
        assert config.populate_entry_trend_allowed is False
        assert config.populate_exit_trend_allowed is False
        assert config.order_execution_allowed is False
        assert config.expose_long_research_signal is True
        assert config.expose_short_research_signal is True
        assert config.unsupported_signal_action == DryRunSignalAction.BLOCK_SIGNAL

    def test_custom_thresholds(self) -> None:
        config = DryRunStrategyConfig(stale_adapter_decision_seconds=60, max_context_age_seconds=120)
        assert config.stale_adapter_decision_seconds == 60
        assert config.max_context_age_seconds == 120

    def test_stale_threshold_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="stale_adapter_decision_seconds must be positive"):
            DryRunStrategyConfig(stale_adapter_decision_seconds=0)
        with pytest.raises(ValueError, match="stale_adapter_decision_seconds must be positive"):
            DryRunStrategyConfig(stale_adapter_decision_seconds=-1)

    def test_max_context_age_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="max_context_age_seconds must be positive"):
            DryRunStrategyConfig(max_context_age_seconds=0)
        with pytest.raises(ValueError, match="max_context_age_seconds must be positive"):
            DryRunStrategyConfig(max_context_age_seconds=-1)

    def test_dry_run_required_must_be_true(self) -> None:
        with pytest.raises(ValueError, match="dry_run_required must be True for MVP-8"):
            DryRunStrategyConfig(dry_run_required=False)

    def test_live_trading_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="live_trading_enabled must be False for MVP-8"):
            DryRunStrategyConfig(live_trading_enabled=True)

    def test_real_orders_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="real_orders_enabled must be False for MVP-8"):
            DryRunStrategyConfig(real_orders_enabled=True)

    def test_leverage_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="leverage_enabled must be False for MVP-8"):
            DryRunStrategyConfig(leverage_enabled=True)

    def test_shorting_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="shorting_enabled must be False for MVP-8"):
            DryRunStrategyConfig(shorting_enabled=True)

    def test_freqtrade_runtime_allowed_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="freqtrade_runtime_allowed must be False for MVP-8"):
            DryRunStrategyConfig(freqtrade_runtime_allowed=True)

    def test_strategy_class_allowed_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="strategy_class_allowed must be False for MVP-8"):
            DryRunStrategyConfig(strategy_class_allowed=True)

    def test_populate_indicators_allowed_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="populate_indicators_allowed must be False for MVP-8"):
            DryRunStrategyConfig(populate_indicators_allowed=True)

    def test_populate_entry_trend_allowed_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="populate_entry_trend_allowed must be False for MVP-8"):
            DryRunStrategyConfig(populate_entry_trend_allowed=True)

    def test_populate_exit_trend_allowed_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="populate_exit_trend_allowed must be False for MVP-8"):
            DryRunStrategyConfig(populate_exit_trend_allowed=True)

    def test_order_execution_allowed_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="order_execution_allowed must be False for MVP-8"):
            DryRunStrategyConfig(order_execution_allowed=True)

    def test_unsupported_signal_action_must_be_block_signal(self) -> None:
        with pytest.raises(ValueError, match="unsupported_signal_action must be BLOCK_SIGNAL for MVP-8"):
            DryRunStrategyConfig(unsupported_signal_action=DryRunSignalAction.NO_SIGNAL)

    def test_immutable(self) -> None:
        config = DryRunStrategyConfig()
        with pytest.raises(FrozenInstanceError):
            config.dry_run_required = False  # type: ignore[misc]


class TestDryRunStrategyInputRefs:
    def test_defaults(self) -> None:
        refs = DryRunStrategyInputRefs()
        assert refs.adapter_decision == "data/strategy_adapter/current_adapter_decision.json"
        assert refs.dry_run_strategy_runtime == "data/freqtrade_strategy/current_dry_run_strategy_runtime.json"

    def test_custom_paths(self) -> None:
        refs = DryRunStrategyInputRefs(
            adapter_decision="custom/adapter.json",
            dry_run_strategy_runtime="custom/runtime.json",
        )
        assert refs.adapter_decision == "custom/adapter.json"
        assert refs.dry_run_strategy_runtime == "custom/runtime.json"

    def test_adapter_decision_must_be_non_empty(self) -> None:
        with pytest.raises(ValueError, match="adapter_decision must be a non-empty string"):
            DryRunStrategyInputRefs(adapter_decision="")

    def test_dry_run_strategy_runtime_must_be_non_empty(self) -> None:
        with pytest.raises(ValueError, match="dry_run_strategy_runtime must be a non-empty string"):
            DryRunStrategyInputRefs(dry_run_strategy_runtime="")

    def test_adapter_decision_must_be_string(self) -> None:
        with pytest.raises(ValueError, match="adapter_decision must be a non-empty string"):
            DryRunStrategyInputRefs(adapter_decision=123)  # type: ignore[arg-type]

    def test_dry_run_strategy_runtime_must_be_string(self) -> None:
        with pytest.raises(ValueError, match="dry_run_strategy_runtime must be a non-empty string"):
            DryRunStrategyInputRefs(dry_run_strategy_runtime=456)  # type: ignore[arg-type]

    def test_immutable(self) -> None:
        refs = DryRunStrategyInputRefs()
        with pytest.raises(FrozenInstanceError):
            refs.adapter_decision = "x"  # type: ignore[misc]


class TestDryRunStrategySafetyFlags:
    def test_defaults(self) -> None:
        flags = DryRunStrategySafetyFlags()
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

    def test_to_dict(self) -> None:
        flags = DryRunStrategySafetyFlags()
        d = flags.to_dict()
        assert d["dry_run"] is True
        assert d["live_trading_enabled"] is False
        assert d["real_orders_enabled"] is False
        assert d["leverage_enabled"] is False
        assert d["shorting_enabled"] is False
        assert d["freqtrade_runtime_allowed"] is False
        assert d["strategy_class_allowed"] is False
        assert d["populate_indicators_allowed"] is False
        assert d["populate_entry_trend_allowed"] is False
        assert d["populate_exit_trend_allowed"] is False
        assert d["order_execution_allowed"] is False
        assert d["max_context_age_seconds"] == 300

    def test_max_context_age_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="max_context_age_seconds must be positive"):
            DryRunStrategySafetyFlags(max_context_age_seconds=0)
        with pytest.raises(ValueError, match="max_context_age_seconds must be positive"):
            DryRunStrategySafetyFlags(max_context_age_seconds=-1)

    def test_dry_run_must_be_true(self) -> None:
        with pytest.raises(ValueError, match="dry_run must be True for MVP-8"):
            DryRunStrategySafetyFlags(dry_run=False)

    def test_live_trading_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="live_trading_enabled must be False for MVP-8"):
            DryRunStrategySafetyFlags(live_trading_enabled=True)

    def test_real_orders_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="real_orders_enabled must be False for MVP-8"):
            DryRunStrategySafetyFlags(real_orders_enabled=True)

    def test_leverage_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="leverage_enabled must be False for MVP-8"):
            DryRunStrategySafetyFlags(leverage_enabled=True)

    def test_shorting_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="shorting_enabled must be False for MVP-8"):
            DryRunStrategySafetyFlags(shorting_enabled=True)

    def test_freqtrade_runtime_allowed_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="freqtrade_runtime_allowed must be False for MVP-8"):
            DryRunStrategySafetyFlags(freqtrade_runtime_allowed=True)

    def test_strategy_class_allowed_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="strategy_class_allowed must be False for MVP-8"):
            DryRunStrategySafetyFlags(strategy_class_allowed=True)

    def test_populate_indicators_allowed_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="populate_indicators_allowed must be False for MVP-8"):
            DryRunStrategySafetyFlags(populate_indicators_allowed=True)

    def test_populate_entry_trend_allowed_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="populate_entry_trend_allowed must be False for MVP-8"):
            DryRunStrategySafetyFlags(populate_entry_trend_allowed=True)

    def test_populate_exit_trend_allowed_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="populate_exit_trend_allowed must be False for MVP-8"):
            DryRunStrategySafetyFlags(populate_exit_trend_allowed=True)

    def test_order_execution_allowed_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="order_execution_allowed must be False for MVP-8"):
            DryRunStrategySafetyFlags(order_execution_allowed=True)

    def test_immutable(self) -> None:
        flags = DryRunStrategySafetyFlags()
        with pytest.raises(FrozenInstanceError):
            flags.dry_run = False  # type: ignore[misc]


class TestDryRunStrategyDataQuality:
    def test_defaults(self) -> None:
        dq = DryRunStrategyDataQuality()
        assert dq.adapter_decision_present is False
        assert dq.adapter_decision_valid is False
        assert dq.adapter_decision_stale is True
        assert dq.reason == "NOT_EVALUATED"

    def test_to_dict(self) -> None:
        dq = DryRunStrategyDataQuality(
            adapter_decision_present=True,
            adapter_decision_valid=True,
            adapter_decision_stale=False,
            reason="VALID",
        )
        d = dq.to_dict()
        assert d["adapter_decision_present"] is True
        assert d["adapter_decision_valid"] is True
        assert d["adapter_decision_stale"] is False
        assert d["reason"] == "VALID"

    def test_reason_must_be_non_empty(self) -> None:
        with pytest.raises(ValueError, match="reason must be a non-empty string"):
            DryRunStrategyDataQuality(reason="")

    def test_reason_must_be_string(self) -> None:
        with pytest.raises(ValueError, match="reason must be a non-empty string"):
            DryRunStrategyDataQuality(reason=123)  # type: ignore[arg-type]

    def test_immutable(self) -> None:
        dq = DryRunStrategyDataQuality()
        with pytest.raises(FrozenInstanceError):
            dq.reason = "x"  # type: ignore[misc]


class TestDryRunStrategyRuntimeContext:
    def _valid_context(self, **kwargs: Any) -> DryRunStrategyRuntimeContext:
        defaults: dict[str, Any] = dict(
            timestamp=datetime.now(timezone.utc),
            status="DRY_RUN_READY",
            strategy_state=DryRunStrategyState.DRY_RUN_READY,
            strategy_mode=DryRunStrategyMode.LONG_RESEARCH_ONLY,
            signal_action=DryRunSignalAction.EXPOSE_LONG_RESEARCH_SIGNAL,
            adapter_state="DRY_RUN_READY",
            adapter_mode="LONG_RESEARCH_ONLY",
            adapter_signal_intent="ALLOW_LONG_RESEARCH_SIGNAL",
            dry_run=True,
            live_trading_enabled=False,
            real_orders_enabled=False,
            leverage_enabled=False,
            shorting_enabled=False,
            freqtrade_runtime_allowed=False,
            strategy_class_allowed=False,
            populate_indicators_allowed=False,
            populate_entry_trend_allowed=False,
            populate_exit_trend_allowed=False,
            order_execution_allowed=False,
            reason_codes=(LONG_RESEARCH_SIGNAL_EXPOSED,),
        )
        defaults.update(kwargs)
        return DryRunStrategyRuntimeContext(**defaults)

    def test_defaults(self) -> None:
        ctx = self._valid_context()
        assert ctx.version == "1.0"
        assert ctx.input_refs.adapter_decision == "data/strategy_adapter/current_adapter_decision.json"
        assert ctx.safety_flags.dry_run is True
        assert ctx.data_quality.reason == "NOT_EVALUATED"

    def test_all_fields(self) -> None:
        ts = datetime.now(timezone.utc)
        ctx = DryRunStrategyRuntimeContext(
            timestamp=ts,
            status="DRY_RUN_READY",
            strategy_state=DryRunStrategyState.DRY_RUN_READY,
            strategy_mode=DryRunStrategyMode.LONG_RESEARCH_ONLY,
            signal_action=DryRunSignalAction.EXPOSE_LONG_RESEARCH_SIGNAL,
            adapter_state="DRY_RUN_READY",
            adapter_mode="LONG_RESEARCH_ONLY",
            adapter_signal_intent="ALLOW_LONG_RESEARCH_SIGNAL",
            dry_run=True,
            live_trading_enabled=False,
            real_orders_enabled=False,
            leverage_enabled=False,
            shorting_enabled=False,
            freqtrade_runtime_allowed=False,
            strategy_class_allowed=False,
            populate_indicators_allowed=False,
            populate_entry_trend_allowed=False,
            populate_exit_trend_allowed=False,
            order_execution_allowed=False,
            reason_codes=(LONG_RESEARCH_SIGNAL_EXPOSED,),
            input_refs=DryRunStrategyInputRefs(),
            safety_flags=DryRunStrategySafetyFlags(),
            data_quality=DryRunStrategyDataQuality(),
            version="1.0",
        )
        assert ctx.timestamp == ts
        assert ctx.status == "DRY_RUN_READY"
        assert ctx.strategy_state == DryRunStrategyState.DRY_RUN_READY
        assert ctx.strategy_mode == DryRunStrategyMode.LONG_RESEARCH_ONLY
        assert ctx.signal_action == DryRunSignalAction.EXPOSE_LONG_RESEARCH_SIGNAL
        assert ctx.adapter_state == "DRY_RUN_READY"
        assert ctx.adapter_mode == "LONG_RESEARCH_ONLY"
        assert ctx.adapter_signal_intent == "ALLOW_LONG_RESEARCH_SIGNAL"
        assert ctx.dry_run is True
        assert ctx.live_trading_enabled is False
        assert ctx.real_orders_enabled is False
        assert ctx.leverage_enabled is False
        assert ctx.shorting_enabled is False
        assert ctx.freqtrade_runtime_allowed is False
        assert ctx.strategy_class_allowed is False
        assert ctx.populate_indicators_allowed is False
        assert ctx.populate_entry_trend_allowed is False
        assert ctx.populate_exit_trend_allowed is False
        assert ctx.order_execution_allowed is False
        assert ctx.reason_codes == (LONG_RESEARCH_SIGNAL_EXPOSED,)
        assert ctx.version == "1.0"

    def test_timestamp_must_be_timezone_aware(self) -> None:
        with pytest.raises(ValueError, match="timestamp must be timezone-aware"):
            self._valid_context(timestamp=datetime(2024, 1, 1, 12, 0, 0))

    def test_status_must_be_non_empty(self) -> None:
        with pytest.raises(ValueError, match="status must be a non-empty string"):
            self._valid_context(status="")
        with pytest.raises(ValueError, match="status must be a non-empty string"):
            self._valid_context(status=123)  # type: ignore[arg-type]

    def test_dry_run_must_be_true(self) -> None:
        with pytest.raises(ValueError, match="dry_run must be True for MVP-8"):
            self._valid_context(dry_run=False)

    def test_live_trading_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="live_trading_enabled must be False for MVP-8"):
            self._valid_context(live_trading_enabled=True)

    def test_real_orders_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="real_orders_enabled must be False for MVP-8"):
            self._valid_context(real_orders_enabled=True)

    def test_leverage_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="leverage_enabled must be False for MVP-8"):
            self._valid_context(leverage_enabled=True)

    def test_shorting_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="shorting_enabled must be False for MVP-8"):
            self._valid_context(shorting_enabled=True)

    def test_freqtrade_runtime_allowed_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="freqtrade_runtime_allowed must be False for MVP-8"):
            self._valid_context(freqtrade_runtime_allowed=True)

    def test_strategy_class_allowed_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="strategy_class_allowed must be False for MVP-8"):
            self._valid_context(strategy_class_allowed=True)

    def test_populate_indicators_allowed_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="populate_indicators_allowed must be False for MVP-8"):
            self._valid_context(populate_indicators_allowed=True)

    def test_populate_entry_trend_allowed_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="populate_entry_trend_allowed must be False for MVP-8"):
            self._valid_context(populate_entry_trend_allowed=True)

    def test_populate_exit_trend_allowed_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="populate_exit_trend_allowed must be False for MVP-8"):
            self._valid_context(populate_exit_trend_allowed=True)

    def test_order_execution_allowed_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="order_execution_allowed must be False for MVP-8"):
            self._valid_context(order_execution_allowed=True)

    def test_reason_codes_must_be_non_empty(self) -> None:
        with pytest.raises(ValueError, match="reason_codes must be non-empty"):
            self._valid_context(reason_codes=())

    def test_version_must_be_non_empty(self) -> None:
        with pytest.raises(ValueError, match="version must be a non-empty string"):
            self._valid_context(version="")
        with pytest.raises(ValueError, match="version must be a non-empty string"):
            self._valid_context(version=123)  # type: ignore[arg-type]

    def test_blocked_factory(self) -> None:
        ctx = DryRunStrategyRuntimeContext.blocked(reason_codes=(MISSING_ADAPTER_DECISION_CONTEXT,))
        assert ctx.strategy_state == DryRunStrategyState.BLOCKED
        assert ctx.strategy_mode == DryRunStrategyMode.BLOCK_ALL
        assert ctx.signal_action == DryRunSignalAction.BLOCK_SIGNAL
        assert ctx.adapter_state == "UNKNOWN"
        assert ctx.adapter_mode == "BLOCK_ALL"
        assert ctx.adapter_signal_intent == "BLOCK_SIGNAL"
        assert ctx.dry_run is True
        assert ctx.live_trading_enabled is False
        assert ctx.real_orders_enabled is False
        assert ctx.leverage_enabled is False
        assert ctx.shorting_enabled is False
        assert ctx.freqtrade_runtime_allowed is False
        assert ctx.strategy_class_allowed is False
        assert ctx.populate_indicators_allowed is False
        assert ctx.populate_entry_trend_allowed is False
        assert ctx.populate_exit_trend_allowed is False
        assert ctx.order_execution_allowed is False
        assert ctx.reason_codes == (MISSING_ADAPTER_DECISION_CONTEXT,)
        assert ctx.status == "BLOCKED"
        assert ctx.version == "1.0"
        assert ctx.timestamp.tzinfo is not None
        assert ctx.data_quality.reason == MISSING_ADAPTER_DECISION_CONTEXT

    def test_blocked_factory_with_custom_status(self) -> None:
        ctx = DryRunStrategyRuntimeContext.blocked(
            reason_codes=(STALE_ADAPTER_DECISION_CONTEXT,), status="STALE"
        )
        assert ctx.status == "STALE"
        assert ctx.reason_codes == (STALE_ADAPTER_DECISION_CONTEXT,)
        assert ctx.data_quality.reason == STALE_ADAPTER_DECISION_CONTEXT

    def test_blocked_factory_with_custom_timestamp(self) -> None:
        ts = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        ctx = DryRunStrategyRuntimeContext.blocked(reason_codes=(DEFAULT_BLOCK_SIGNAL,), timestamp=ts)
        assert ctx.timestamp == ts

    def test_blocked_factory_requires_non_empty_reason_codes(self) -> None:
        with pytest.raises(ValueError, match="reason_codes must be non-empty"):
            DryRunStrategyRuntimeContext.blocked(reason_codes=())

    def test_is_blocking_true_for_blocked(self) -> None:
        ctx = DryRunStrategyRuntimeContext.blocked(reason_codes=(MISSING_ADAPTER_DECISION_CONTEXT,))
        assert ctx.is_blocking() is True

    def test_is_blocking_true_for_unknown_state(self) -> None:
        ctx = self._valid_context(strategy_state=DryRunStrategyState.UNKNOWN)
        assert ctx.is_blocking() is True

    def test_is_blocking_true_for_block_all_mode(self) -> None:
        ctx = self._valid_context(strategy_mode=DryRunStrategyMode.BLOCK_ALL)
        assert ctx.is_blocking() is True

    def test_is_blocking_true_for_block_signal(self) -> None:
        ctx = self._valid_context(signal_action=DryRunSignalAction.BLOCK_SIGNAL)
        assert ctx.is_blocking() is True

    def test_is_blocking_true_for_no_signal(self) -> None:
        ctx = self._valid_context(signal_action=DryRunSignalAction.NO_SIGNAL)
        assert ctx.is_blocking() is True

    def test_is_blocking_true_for_blocked_status(self) -> None:
        ctx = self._valid_context(status="BLOCKED")
        assert ctx.is_blocking() is True

    def test_is_blocking_false_for_allowed(self) -> None:
        ctx = self._valid_context(
            strategy_state=DryRunStrategyState.DRY_RUN_READY,
            strategy_mode=DryRunStrategyMode.LONG_RESEARCH_ONLY,
            signal_action=DryRunSignalAction.EXPOSE_LONG_RESEARCH_SIGNAL,
            status="DRY_RUN_READY",
        )
        assert ctx.is_blocking() is False

    def test_is_blocking_false_for_short_allowed(self) -> None:
        ctx = self._valid_context(
            strategy_state=DryRunStrategyState.DRY_RUN_READY,
            strategy_mode=DryRunStrategyMode.SHORT_RESEARCH_ONLY,
            signal_action=DryRunSignalAction.EXPOSE_SHORT_RESEARCH_SIGNAL,
            status="DRY_RUN_READY",
        )
        assert ctx.is_blocking() is False

    def test_immutable(self) -> None:
        ctx = self._valid_context()
        with pytest.raises(FrozenInstanceError):
            ctx.status = "BLOCKED"  # type: ignore[misc]


class TestReasonCodes:
    def test_all_reason_codes_present(self) -> None:
        assert len(REASON_CODES) == 17
        assert MISSING_ADAPTER_DECISION_CONTEXT in REASON_CODES
        assert INVALID_ADAPTER_DECISION_CONTEXT in REASON_CODES
        assert ADAPTER_NOT_DRY_RUN_READY in REASON_CODES
        assert ADAPTER_MODE_BLOCK_ALL in REASON_CODES
        assert ADAPTER_SIGNAL_BLOCKED in REASON_CODES
        assert DRY_RUN_DISABLED in REASON_CODES
        assert LIVE_TRADING_ENABLED in REASON_CODES
        assert REAL_ORDERS_ENABLED in REASON_CODES
        assert LEVERAGE_ENABLED in REASON_CODES
        assert SHORTING_ENABLED in REASON_CODES
        assert STALE_ADAPTER_DECISION_CONTEXT in REASON_CODES
        assert UNSUPPORTED_ADAPTER_MODE in REASON_CODES
        assert UNSUPPORTED_ADAPTER_SIGNAL_INTENT in REASON_CODES
        assert LONG_RESEARCH_SIGNAL_EXPOSED in REASON_CODES
        assert SHORT_RESEARCH_SIGNAL_EXPOSED in REASON_CODES
        assert DEFAULT_BLOCK_SIGNAL in REASON_CODES
        assert CALCULATION_ERROR in REASON_CODES

    def test_reason_codes_are_strings(self) -> None:
        for code in REASON_CODES:
            assert isinstance(code, str)
            assert len(code) > 0


class TestFailClosedDefaults:
    def test_config_defaults_blocked(self) -> None:
        config = DryRunStrategyConfig()
        assert config.dry_run_required is True
        assert config.live_trading_enabled is False
        assert config.real_orders_enabled is False
        assert config.leverage_enabled is False
        assert config.shorting_enabled is False
        assert config.freqtrade_runtime_allowed is False
        assert config.strategy_class_allowed is False
        assert config.populate_indicators_allowed is False
        assert config.populate_entry_trend_allowed is False
        assert config.populate_exit_trend_allowed is False
        assert config.order_execution_allowed is False
        assert config.unsupported_signal_action == DryRunSignalAction.BLOCK_SIGNAL

    def test_safety_flags_defaults_blocked(self) -> None:
        flags = DryRunStrategySafetyFlags()
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

    def test_runtime_context_blocked_factory(self) -> None:
        ctx = DryRunStrategyRuntimeContext.blocked(reason_codes=(DEFAULT_BLOCK_SIGNAL,))
        assert ctx.strategy_state == DryRunStrategyState.BLOCKED
        assert ctx.strategy_mode == DryRunStrategyMode.BLOCK_ALL
        assert ctx.signal_action == DryRunSignalAction.BLOCK_SIGNAL
        assert ctx.dry_run is True
        assert ctx.live_trading_enabled is False
        assert ctx.real_orders_enabled is False
        assert ctx.leverage_enabled is False
        assert ctx.shorting_enabled is False
        assert ctx.freqtrade_runtime_allowed is False
        assert ctx.strategy_class_allowed is False
        assert ctx.populate_indicators_allowed is False
        assert ctx.populate_entry_trend_allowed is False
        assert ctx.populate_exit_trend_allowed is False
        assert ctx.order_execution_allowed is False

    def test_no_execution_flags_enabled_by_default(self) -> None:
        ctx = DryRunStrategyRuntimeContext.blocked(reason_codes=(MISSING_ADAPTER_DECISION_CONTEXT,))
        assert ctx.populate_indicators_allowed is False
        assert ctx.populate_entry_trend_allowed is False
        assert ctx.populate_exit_trend_allowed is False
        assert ctx.order_execution_allowed is False
        assert ctx.freqtrade_runtime_allowed is False
        assert ctx.strategy_class_allowed is False
