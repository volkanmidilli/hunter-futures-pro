"""Tests for strategy adapter models."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from typing import Any

import pytest

from hunter.strategy_adapter.models import (
    AdapterConfig,
    AdapterDataQuality,
    AdapterDecisionContext,
    AdapterInputRefs,
    AdapterMode,
    AdapterSafetyFlags,
    AdapterSignalIntent,
    AdapterState,
    CALCULATION_ERROR,
    DEFAULT_BLOCK_SIGNAL,
    DRY_RUN_DISABLED,
    INVALID_STRATEGY_CONTEXT,
    LEVERAGE_ENABLED,
    LIVE_TRADING_ENABLED,
    LONG_RESEARCH_SIGNAL_ALLOWED,
    MISSING_STRATEGY_CONTEXT,
    REAL_ORDERS_ENABLED,
    REASON_CODES,
    SHORTING_ENABLED,
    SHORT_RESEARCH_SIGNAL_ALLOWED,
    STALE_STRATEGY_CONTEXT,
    STRATEGY_CONTRACT_MODE_BLOCK_ALL,
    STRATEGY_CONTRACT_NOT_DRY_RUN_READY,
    UNSUPPORTED_STRATEGY_MODE,
)


class TestAdapterState:
    def test_disabled(self) -> None:
        assert AdapterState.DISABLED == "DISABLED"
        assert AdapterState.DISABLED.value == "DISABLED"

    def test_dry_run_ready(self) -> None:
        assert AdapterState.DRY_RUN_READY == "DRY_RUN_READY"
        assert AdapterState.DRY_RUN_READY.value == "DRY_RUN_READY"

    def test_blocked(self) -> None:
        assert AdapterState.BLOCKED == "BLOCKED"
        assert AdapterState.BLOCKED.value == "BLOCKED"

    def test_unknown(self) -> None:
        assert AdapterState.UNKNOWN == "UNKNOWN"
        assert AdapterState.UNKNOWN.value == "UNKNOWN"

    def test_members(self) -> None:
        assert list(AdapterState) == [
            AdapterState.DISABLED,
            AdapterState.DRY_RUN_READY,
            AdapterState.BLOCKED,
            AdapterState.UNKNOWN,
        ]


class TestAdapterMode:
    def test_long_research_only(self) -> None:
        assert AdapterMode.LONG_RESEARCH_ONLY == "LONG_RESEARCH_ONLY"
        assert AdapterMode.LONG_RESEARCH_ONLY.value == "LONG_RESEARCH_ONLY"

    def test_short_research_only(self) -> None:
        assert AdapterMode.SHORT_RESEARCH_ONLY == "SHORT_RESEARCH_ONLY"
        assert AdapterMode.SHORT_RESEARCH_ONLY.value == "SHORT_RESEARCH_ONLY"

    def test_block_all(self) -> None:
        assert AdapterMode.BLOCK_ALL == "BLOCK_ALL"
        assert AdapterMode.BLOCK_ALL.value == "BLOCK_ALL"

    def test_members(self) -> None:
        assert list(AdapterMode) == [
            AdapterMode.LONG_RESEARCH_ONLY,
            AdapterMode.SHORT_RESEARCH_ONLY,
            AdapterMode.BLOCK_ALL,
        ]


class TestAdapterSignalIntent:
    def test_allow_long_research_signal(self) -> None:
        assert AdapterSignalIntent.ALLOW_LONG_RESEARCH_SIGNAL == "ALLOW_LONG_RESEARCH_SIGNAL"
        assert AdapterSignalIntent.ALLOW_LONG_RESEARCH_SIGNAL.value == "ALLOW_LONG_RESEARCH_SIGNAL"

    def test_allow_short_research_signal(self) -> None:
        assert AdapterSignalIntent.ALLOW_SHORT_RESEARCH_SIGNAL == "ALLOW_SHORT_RESEARCH_SIGNAL"
        assert AdapterSignalIntent.ALLOW_SHORT_RESEARCH_SIGNAL.value == "ALLOW_SHORT_RESEARCH_SIGNAL"

    def test_block_signal(self) -> None:
        assert AdapterSignalIntent.BLOCK_SIGNAL == "BLOCK_SIGNAL"
        assert AdapterSignalIntent.BLOCK_SIGNAL.value == "BLOCK_SIGNAL"

    def test_no_signal(self) -> None:
        assert AdapterSignalIntent.NO_SIGNAL == "NO_SIGNAL"
        assert AdapterSignalIntent.NO_SIGNAL.value == "NO_SIGNAL"

    def test_members(self) -> None:
        assert list(AdapterSignalIntent) == [
            AdapterSignalIntent.ALLOW_LONG_RESEARCH_SIGNAL,
            AdapterSignalIntent.ALLOW_SHORT_RESEARCH_SIGNAL,
            AdapterSignalIntent.BLOCK_SIGNAL,
            AdapterSignalIntent.NO_SIGNAL,
        ]


class TestAdapterConfig:
    def test_defaults(self) -> None:
        config = AdapterConfig()
        assert config.stale_strategy_context_seconds == 300
        assert config.max_context_age_seconds == 300
        assert config.dry_run_required is True
        assert config.live_trading_enabled is False
        assert config.real_orders_enabled is False
        assert config.leverage_enabled is False
        assert config.shorting_enabled is False
        assert config.adapter_runtime_allowed is False
        assert config.freqtrade_runtime_allowed is False
        assert config.strategy_class_allowed is False
        assert config.entry_signal_allowed is False
        assert config.exit_signal_allowed is False
        assert config.order_execution_allowed is False
        assert config.allow_long_research_signal is True
        assert config.allow_short_research_signal is True
        assert config.unsupported_mode_action == AdapterSignalIntent.BLOCK_SIGNAL

    def test_custom_thresholds(self) -> None:
        config = AdapterConfig(stale_strategy_context_seconds=60, max_context_age_seconds=120)
        assert config.stale_strategy_context_seconds == 60
        assert config.max_context_age_seconds == 120

    def test_stale_threshold_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="stale_strategy_context_seconds must be positive"):
            AdapterConfig(stale_strategy_context_seconds=0)
        with pytest.raises(ValueError, match="stale_strategy_context_seconds must be positive"):
            AdapterConfig(stale_strategy_context_seconds=-1)

    def test_max_context_age_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="max_context_age_seconds must be positive"):
            AdapterConfig(max_context_age_seconds=0)
        with pytest.raises(ValueError, match="max_context_age_seconds must be positive"):
            AdapterConfig(max_context_age_seconds=-1)

    def test_dry_run_required_must_be_true(self) -> None:
        with pytest.raises(ValueError, match="dry_run_required must be True for MVP-7"):
            AdapterConfig(dry_run_required=False)

    def test_live_trading_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="live_trading_enabled must be False for MVP-7"):
            AdapterConfig(live_trading_enabled=True)

    def test_real_orders_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="real_orders_enabled must be False for MVP-7"):
            AdapterConfig(real_orders_enabled=True)

    def test_leverage_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="leverage_enabled must be False for MVP-7"):
            AdapterConfig(leverage_enabled=True)

    def test_shorting_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="shorting_enabled must be False for MVP-7"):
            AdapterConfig(shorting_enabled=True)

    def test_adapter_runtime_allowed_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="adapter_runtime_allowed must be False for MVP-7"):
            AdapterConfig(adapter_runtime_allowed=True)

    def test_freqtrade_runtime_allowed_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="freqtrade_runtime_allowed must be False for MVP-7"):
            AdapterConfig(freqtrade_runtime_allowed=True)

    def test_strategy_class_allowed_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="strategy_class_allowed must be False for MVP-7"):
            AdapterConfig(strategy_class_allowed=True)

    def test_entry_signal_allowed_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="entry_signal_allowed must be False for MVP-7"):
            AdapterConfig(entry_signal_allowed=True)

    def test_exit_signal_allowed_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="exit_signal_allowed must be False for MVP-7"):
            AdapterConfig(exit_signal_allowed=True)

    def test_order_execution_allowed_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="order_execution_allowed must be False for MVP-7"):
            AdapterConfig(order_execution_allowed=True)

    def test_unsupported_mode_action_must_be_block_signal(self) -> None:
        with pytest.raises(ValueError, match="unsupported_mode_action must be BLOCK_SIGNAL for MVP-7"):
            AdapterConfig(unsupported_mode_action=AdapterSignalIntent.NO_SIGNAL)

    def test_immutable(self) -> None:
        config = AdapterConfig()
        with pytest.raises(FrozenInstanceError):
            config.dry_run_required = False  # type: ignore[misc]


class TestAdapterInputRefs:
    def test_defaults(self) -> None:
        refs = AdapterInputRefs()
        assert refs.strategy_context == "data/strategy/current_strategy_context.json"
        assert refs.adapter_decision == "data/strategy_adapter/current_adapter_decision.json"

    def test_custom_paths(self) -> None:
        refs = AdapterInputRefs(
            strategy_context="custom/strategy.json",
            adapter_decision="custom/adapter.json",
        )
        assert refs.strategy_context == "custom/strategy.json"
        assert refs.adapter_decision == "custom/adapter.json"

    def test_strategy_context_must_be_non_empty(self) -> None:
        with pytest.raises(ValueError, match="strategy_context must be a non-empty string"):
            AdapterInputRefs(strategy_context="")

    def test_adapter_decision_must_be_non_empty(self) -> None:
        with pytest.raises(ValueError, match="adapter_decision must be a non-empty string"):
            AdapterInputRefs(adapter_decision="")

    def test_strategy_context_must_be_string(self) -> None:
        with pytest.raises(ValueError, match="strategy_context must be a non-empty string"):
            AdapterInputRefs(strategy_context=123)  # type: ignore[arg-type]

    def test_adapter_decision_must_be_string(self) -> None:
        with pytest.raises(ValueError, match="adapter_decision must be a non-empty string"):
            AdapterInputRefs(adapter_decision=456)  # type: ignore[arg-type]

    def test_immutable(self) -> None:
        refs = AdapterInputRefs()
        with pytest.raises(FrozenInstanceError):
            refs.strategy_context = "x"  # type: ignore[misc]


class TestAdapterSafetyFlags:
    def test_defaults(self) -> None:
        flags = AdapterSafetyFlags()
        assert flags.dry_run is True
        assert flags.live_trading_enabled is False
        assert flags.real_orders_enabled is False
        assert flags.leverage_enabled is False
        assert flags.shorting_enabled is False
        assert flags.adapter_runtime_allowed is False
        assert flags.freqtrade_runtime_allowed is False
        assert flags.strategy_class_allowed is False
        assert flags.entry_signal_allowed is False
        assert flags.exit_signal_allowed is False
        assert flags.order_execution_allowed is False
        assert flags.max_context_age_seconds == 300

    def test_to_dict(self) -> None:
        flags = AdapterSafetyFlags()
        d = flags.to_dict()
        assert d["dry_run"] is True
        assert d["live_trading_enabled"] is False
        assert d["real_orders_enabled"] is False
        assert d["leverage_enabled"] is False
        assert d["shorting_enabled"] is False
        assert d["adapter_runtime_allowed"] is False
        assert d["freqtrade_runtime_allowed"] is False
        assert d["strategy_class_allowed"] is False
        assert d["entry_signal_allowed"] is False
        assert d["exit_signal_allowed"] is False
        assert d["order_execution_allowed"] is False
        assert d["max_context_age_seconds"] == 300

    def test_max_context_age_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="max_context_age_seconds must be positive"):
            AdapterSafetyFlags(max_context_age_seconds=0)
        with pytest.raises(ValueError, match="max_context_age_seconds must be positive"):
            AdapterSafetyFlags(max_context_age_seconds=-1)

    def test_dry_run_must_be_true(self) -> None:
        with pytest.raises(ValueError, match="dry_run must be True for MVP-7"):
            AdapterSafetyFlags(dry_run=False)

    def test_live_trading_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="live_trading_enabled must be False for MVP-7"):
            AdapterSafetyFlags(live_trading_enabled=True)

    def test_real_orders_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="real_orders_enabled must be False for MVP-7"):
            AdapterSafetyFlags(real_orders_enabled=True)

    def test_leverage_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="leverage_enabled must be False for MVP-7"):
            AdapterSafetyFlags(leverage_enabled=True)

    def test_shorting_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="shorting_enabled must be False for MVP-7"):
            AdapterSafetyFlags(shorting_enabled=True)

    def test_adapter_runtime_allowed_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="adapter_runtime_allowed must be False for MVP-7"):
            AdapterSafetyFlags(adapter_runtime_allowed=True)

    def test_freqtrade_runtime_allowed_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="freqtrade_runtime_allowed must be False for MVP-7"):
            AdapterSafetyFlags(freqtrade_runtime_allowed=True)

    def test_strategy_class_allowed_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="strategy_class_allowed must be False for MVP-7"):
            AdapterSafetyFlags(strategy_class_allowed=True)

    def test_entry_signal_allowed_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="entry_signal_allowed must be False for MVP-7"):
            AdapterSafetyFlags(entry_signal_allowed=True)

    def test_exit_signal_allowed_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="exit_signal_allowed must be False for MVP-7"):
            AdapterSafetyFlags(exit_signal_allowed=True)

    def test_order_execution_allowed_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="order_execution_allowed must be False for MVP-7"):
            AdapterSafetyFlags(order_execution_allowed=True)

    def test_immutable(self) -> None:
        flags = AdapterSafetyFlags()
        with pytest.raises(FrozenInstanceError):
            flags.dry_run = False  # type: ignore[misc]


class TestAdapterDataQuality:
    def test_defaults(self) -> None:
        dq = AdapterDataQuality()
        assert dq.strategy_context_present is False
        assert dq.strategy_context_valid is False
        assert dq.strategy_context_stale is True
        assert dq.reason == "NOT_EVALUATED"

    def test_to_dict(self) -> None:
        dq = AdapterDataQuality(
            strategy_context_present=True,
            strategy_context_valid=True,
            strategy_context_stale=False,
            reason="VALID",
        )
        d = dq.to_dict()
        assert d["strategy_context_present"] is True
        assert d["strategy_context_valid"] is True
        assert d["strategy_context_stale"] is False
        assert d["reason"] == "VALID"

    def test_reason_must_be_non_empty(self) -> None:
        with pytest.raises(ValueError, match="reason must be a non-empty string"):
            AdapterDataQuality(reason="")

    def test_reason_must_be_string(self) -> None:
        with pytest.raises(ValueError, match="reason must be a non-empty string"):
            AdapterDataQuality(reason=123)  # type: ignore[arg-type]

    def test_immutable(self) -> None:
        dq = AdapterDataQuality()
        with pytest.raises(FrozenInstanceError):
            dq.reason = "x"  # type: ignore[misc]


class TestAdapterDecisionContext:
    def _valid_context(self, **kwargs: Any) -> AdapterDecisionContext:
        defaults: dict[str, Any] = dict(
            timestamp=datetime.now(timezone.utc),
            status="DRY_RUN_READY",
            adapter_state=AdapterState.DRY_RUN_READY,
            adapter_mode=AdapterMode.LONG_RESEARCH_ONLY,
            signal_intent=AdapterSignalIntent.ALLOW_LONG_RESEARCH_SIGNAL,
            strategy_contract_state="DRY_RUN_READY",
            strategy_contract_mode="LONG_RESEARCH_ONLY",
            dry_run=True,
            live_trading_enabled=False,
            real_orders_enabled=False,
            leverage_enabled=False,
            shorting_enabled=False,
            adapter_runtime_allowed=False,
            freqtrade_runtime_allowed=False,
            strategy_class_allowed=False,
            entry_signal_allowed=False,
            exit_signal_allowed=False,
            order_execution_allowed=False,
            reason_codes=(LONG_RESEARCH_SIGNAL_ALLOWED,),
        )
        defaults.update(kwargs)
        return AdapterDecisionContext(**defaults)

    def test_defaults(self) -> None:
        ctx = self._valid_context()
        assert ctx.version == "1.0"
        assert ctx.input_refs.strategy_context == "data/strategy/current_strategy_context.json"
        assert ctx.safety_flags.dry_run is True
        assert ctx.data_quality.reason == "NOT_EVALUATED"

    def test_all_fields(self) -> None:
        ts = datetime.now(timezone.utc)
        ctx = AdapterDecisionContext(
            timestamp=ts,
            status="DRY_RUN_READY",
            adapter_state=AdapterState.DRY_RUN_READY,
            adapter_mode=AdapterMode.LONG_RESEARCH_ONLY,
            signal_intent=AdapterSignalIntent.ALLOW_LONG_RESEARCH_SIGNAL,
            strategy_contract_state="DRY_RUN_READY",
            strategy_contract_mode="LONG_RESEARCH_ONLY",
            dry_run=True,
            live_trading_enabled=False,
            real_orders_enabled=False,
            leverage_enabled=False,
            shorting_enabled=False,
            adapter_runtime_allowed=False,
            freqtrade_runtime_allowed=False,
            strategy_class_allowed=False,
            entry_signal_allowed=False,
            exit_signal_allowed=False,
            order_execution_allowed=False,
            reason_codes=(LONG_RESEARCH_SIGNAL_ALLOWED,),
            input_refs=AdapterInputRefs(),
            safety_flags=AdapterSafetyFlags(),
            data_quality=AdapterDataQuality(),
            version="1.0",
        )
        assert ctx.timestamp == ts
        assert ctx.status == "DRY_RUN_READY"
        assert ctx.adapter_state == AdapterState.DRY_RUN_READY
        assert ctx.adapter_mode == AdapterMode.LONG_RESEARCH_ONLY
        assert ctx.signal_intent == AdapterSignalIntent.ALLOW_LONG_RESEARCH_SIGNAL
        assert ctx.strategy_contract_state == "DRY_RUN_READY"
        assert ctx.strategy_contract_mode == "LONG_RESEARCH_ONLY"
        assert ctx.dry_run is True
        assert ctx.live_trading_enabled is False
        assert ctx.real_orders_enabled is False
        assert ctx.leverage_enabled is False
        assert ctx.shorting_enabled is False
        assert ctx.adapter_runtime_allowed is False
        assert ctx.freqtrade_runtime_allowed is False
        assert ctx.strategy_class_allowed is False
        assert ctx.entry_signal_allowed is False
        assert ctx.exit_signal_allowed is False
        assert ctx.order_execution_allowed is False
        assert ctx.reason_codes == (LONG_RESEARCH_SIGNAL_ALLOWED,)
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
        with pytest.raises(ValueError, match="dry_run must be True for MVP-7"):
            self._valid_context(dry_run=False)

    def test_live_trading_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="live_trading_enabled must be False for MVP-7"):
            self._valid_context(live_trading_enabled=True)

    def test_real_orders_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="real_orders_enabled must be False for MVP-7"):
            self._valid_context(real_orders_enabled=True)

    def test_leverage_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="leverage_enabled must be False for MVP-7"):
            self._valid_context(leverage_enabled=True)

    def test_shorting_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="shorting_enabled must be False for MVP-7"):
            self._valid_context(shorting_enabled=True)

    def test_adapter_runtime_allowed_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="adapter_runtime_allowed must be False for MVP-7"):
            self._valid_context(adapter_runtime_allowed=True)

    def test_freqtrade_runtime_allowed_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="freqtrade_runtime_allowed must be False for MVP-7"):
            self._valid_context(freqtrade_runtime_allowed=True)

    def test_strategy_class_allowed_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="strategy_class_allowed must be False for MVP-7"):
            self._valid_context(strategy_class_allowed=True)

    def test_entry_signal_allowed_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="entry_signal_allowed must be False for MVP-7"):
            self._valid_context(entry_signal_allowed=True)

    def test_exit_signal_allowed_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="exit_signal_allowed must be False for MVP-7"):
            self._valid_context(exit_signal_allowed=True)

    def test_order_execution_allowed_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="order_execution_allowed must be False for MVP-7"):
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
        ctx = AdapterDecisionContext.blocked(reason_codes=(MISSING_STRATEGY_CONTEXT,))
        assert ctx.adapter_state == AdapterState.BLOCKED
        assert ctx.adapter_mode == AdapterMode.BLOCK_ALL
        assert ctx.signal_intent == AdapterSignalIntent.BLOCK_SIGNAL
        assert ctx.strategy_contract_state == "UNKNOWN"
        assert ctx.strategy_contract_mode == "BLOCK_ALL"
        assert ctx.dry_run is True
        assert ctx.live_trading_enabled is False
        assert ctx.real_orders_enabled is False
        assert ctx.leverage_enabled is False
        assert ctx.shorting_enabled is False
        assert ctx.adapter_runtime_allowed is False
        assert ctx.freqtrade_runtime_allowed is False
        assert ctx.strategy_class_allowed is False
        assert ctx.entry_signal_allowed is False
        assert ctx.exit_signal_allowed is False
        assert ctx.order_execution_allowed is False
        assert ctx.reason_codes == (MISSING_STRATEGY_CONTEXT,)
        assert ctx.status == "BLOCKED"
        assert ctx.version == "1.0"
        assert ctx.timestamp.tzinfo is not None
        assert ctx.data_quality.reason == MISSING_STRATEGY_CONTEXT

    def test_blocked_factory_with_custom_status(self) -> None:
        ctx = AdapterDecisionContext.blocked(
            reason_codes=(STALE_STRATEGY_CONTEXT,), status="STALE"
        )
        assert ctx.status == "STALE"
        assert ctx.reason_codes == (STALE_STRATEGY_CONTEXT,)
        assert ctx.data_quality.reason == STALE_STRATEGY_CONTEXT

    def test_blocked_factory_with_custom_timestamp(self) -> None:
        ts = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        ctx = AdapterDecisionContext.blocked(reason_codes=(DEFAULT_BLOCK_SIGNAL,), timestamp=ts)
        assert ctx.timestamp == ts

    def test_blocked_factory_requires_non_empty_reason_codes(self) -> None:
        with pytest.raises(ValueError, match="reason_codes must be non-empty"):
            AdapterDecisionContext.blocked(reason_codes=())

    def test_is_blocking_true_for_blocked(self) -> None:
        ctx = AdapterDecisionContext.blocked(reason_codes=(MISSING_STRATEGY_CONTEXT,))
        assert ctx.is_blocking() is True

    def test_is_blocking_true_for_unknown_state(self) -> None:
        ctx = self._valid_context(adapter_state=AdapterState.UNKNOWN)
        assert ctx.is_blocking() is True

    def test_is_blocking_true_for_block_all_mode(self) -> None:
        ctx = self._valid_context(adapter_mode=AdapterMode.BLOCK_ALL)
        assert ctx.is_blocking() is True

    def test_is_blocking_true_for_block_signal(self) -> None:
        ctx = self._valid_context(signal_intent=AdapterSignalIntent.BLOCK_SIGNAL)
        assert ctx.is_blocking() is True

    def test_is_blocking_true_for_no_signal(self) -> None:
        ctx = self._valid_context(signal_intent=AdapterSignalIntent.NO_SIGNAL)
        assert ctx.is_blocking() is True

    def test_is_blocking_true_for_blocked_status(self) -> None:
        ctx = self._valid_context(status="BLOCKED")
        assert ctx.is_blocking() is True

    def test_is_blocking_false_for_allowed(self) -> None:
        ctx = self._valid_context(
            adapter_state=AdapterState.DRY_RUN_READY,
            adapter_mode=AdapterMode.LONG_RESEARCH_ONLY,
            signal_intent=AdapterSignalIntent.ALLOW_LONG_RESEARCH_SIGNAL,
            status="DRY_RUN_READY",
        )
        assert ctx.is_blocking() is False

    def test_is_blocking_false_for_short_allowed(self) -> None:
        ctx = self._valid_context(
            adapter_state=AdapterState.DRY_RUN_READY,
            adapter_mode=AdapterMode.SHORT_RESEARCH_ONLY,
            signal_intent=AdapterSignalIntent.ALLOW_SHORT_RESEARCH_SIGNAL,
            status="DRY_RUN_READY",
        )
        assert ctx.is_blocking() is False

    def test_immutable(self) -> None:
        ctx = self._valid_context()
        with pytest.raises(FrozenInstanceError):
            ctx.status = "BLOCKED"  # type: ignore[misc]


class TestReasonCodes:
    def test_all_reason_codes_present(self) -> None:
        assert len(REASON_CODES) == 15
        assert MISSING_STRATEGY_CONTEXT in REASON_CODES
        assert INVALID_STRATEGY_CONTEXT in REASON_CODES
        assert STRATEGY_CONTRACT_NOT_DRY_RUN_READY in REASON_CODES
        assert STRATEGY_CONTRACT_MODE_BLOCK_ALL in REASON_CODES
        assert DRY_RUN_DISABLED in REASON_CODES
        assert LIVE_TRADING_ENABLED in REASON_CODES
        assert REAL_ORDERS_ENABLED in REASON_CODES
        assert LEVERAGE_ENABLED in REASON_CODES
        assert SHORTING_ENABLED in REASON_CODES
        assert STALE_STRATEGY_CONTEXT in REASON_CODES
        assert UNSUPPORTED_STRATEGY_MODE in REASON_CODES
        assert LONG_RESEARCH_SIGNAL_ALLOWED in REASON_CODES
        assert SHORT_RESEARCH_SIGNAL_ALLOWED in REASON_CODES
        assert DEFAULT_BLOCK_SIGNAL in REASON_CODES
        assert CALCULATION_ERROR in REASON_CODES

    def test_reason_codes_are_strings(self) -> None:
        for code in REASON_CODES:
            assert isinstance(code, str)
            assert len(code) > 0


class TestFailClosedDefaults:
    def test_adapter_config_defaults_blocked(self) -> None:
        config = AdapterConfig()
        # Config doesn't have adapter_state, but safety flags should be restrictive
        assert config.dry_run_required is True
        assert config.live_trading_enabled is False
        assert config.real_orders_enabled is False
        assert config.leverage_enabled is False
        assert config.shorting_enabled is False
        assert config.adapter_runtime_allowed is False
        assert config.freqtrade_runtime_allowed is False
        assert config.strategy_class_allowed is False
        assert config.entry_signal_allowed is False
        assert config.exit_signal_allowed is False
        assert config.order_execution_allowed is False
        assert config.unsupported_mode_action == AdapterSignalIntent.BLOCK_SIGNAL

    def test_adapter_safety_flags_defaults_blocked(self) -> None:
        flags = AdapterSafetyFlags()
        assert flags.dry_run is True
        assert flags.live_trading_enabled is False
        assert flags.real_orders_enabled is False
        assert flags.leverage_enabled is False
        assert flags.shorting_enabled is False
        assert flags.adapter_runtime_allowed is False
        assert flags.freqtrade_runtime_allowed is False
        assert flags.strategy_class_allowed is False
        assert flags.entry_signal_allowed is False
        assert flags.exit_signal_allowed is False
        assert flags.order_execution_allowed is False

    def test_adapter_decision_context_blocked_factory(self) -> None:
        ctx = AdapterDecisionContext.blocked(reason_codes=(DEFAULT_BLOCK_SIGNAL,))
        assert ctx.adapter_state == AdapterState.BLOCKED
        assert ctx.adapter_mode == AdapterMode.BLOCK_ALL
        assert ctx.signal_intent == AdapterSignalIntent.BLOCK_SIGNAL
        assert ctx.dry_run is True
        assert ctx.live_trading_enabled is False
        assert ctx.real_orders_enabled is False
        assert ctx.leverage_enabled is False
        assert ctx.shorting_enabled is False
        assert ctx.adapter_runtime_allowed is False
        assert ctx.freqtrade_runtime_allowed is False
        assert ctx.strategy_class_allowed is False
        assert ctx.entry_signal_allowed is False
        assert ctx.exit_signal_allowed is False
        assert ctx.order_execution_allowed is False

    def test_no_execution_flags_enabled_by_default(self) -> None:
        ctx = AdapterDecisionContext.blocked(reason_codes=(MISSING_STRATEGY_CONTEXT,))
        assert ctx.entry_signal_allowed is False
        assert ctx.exit_signal_allowed is False
        assert ctx.order_execution_allowed is False
        assert ctx.adapter_runtime_allowed is False
        assert ctx.freqtrade_runtime_allowed is False
        assert ctx.strategy_class_allowed is False
