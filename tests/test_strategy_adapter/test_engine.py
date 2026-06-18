"""Tests for strategy adapter engine."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from hunter.strategy_adapter.engine import (
    build_adapter_decision_context,
    build_safety_flags,
    is_stale_strategy_context,
    map_strategy_to_adapter_mode,
    map_strategy_to_signal_intent,
    validate_adapter_inputs,
)
from hunter.strategy_adapter.models import (
    AdapterConfig,
    AdapterMode,
    AdapterSignalIntent,
    AdapterState,
    CALCULATION_ERROR,
    DRY_RUN_DISABLED,
    INVALID_STRATEGY_CONTEXT,
    LEVERAGE_ENABLED,
    LIVE_TRADING_ENABLED,
    LONG_RESEARCH_SIGNAL_ALLOWED,
    MISSING_STRATEGY_CONTEXT,
    REAL_ORDERS_ENABLED,
    SHORTING_ENABLED,
    SHORT_RESEARCH_SIGNAL_ALLOWED,
    STALE_STRATEGY_CONTEXT,
    STRATEGY_CONTRACT_MODE_BLOCK_ALL,
    STRATEGY_CONTRACT_NOT_DRY_RUN_READY,
    UNSUPPORTED_STRATEGY_MODE,
)
from hunter.strategy_contract.models import (
    StrategyContractConfig,
    StrategyContractDataQuality,
    StrategyContractInputRefs,
    StrategyContractMode,
    StrategyContractSafetyFlags,
    StrategyContractState,
    StrategyContext,
)


class _ValidStrategyContext:
    """Minimal mock that satisfies _REQUIRED_STRATEGY_ATTRS."""

    def __init__(self, **kwargs: Any) -> None:
        defaults = dict(
            timestamp=datetime.now(timezone.utc),
            status="DRY_RUN_READY",
            contract_state=StrategyContractState.DRY_RUN_READY,
            contract_mode=StrategyContractMode.LONG_RESEARCH_ONLY,
            dry_run=True,
            live_trading_enabled=False,
            real_orders_enabled=False,
            leverage_enabled=False,
            shorting_enabled=False,
        )
        defaults.update(kwargs)
        for k, v in defaults.items():
            setattr(self, k, v)


def _make_strategy_context(**kwargs: Any) -> StrategyContext:
    """Build a real StrategyContext with safe overrides."""
    ts = kwargs.pop("timestamp", datetime.now(timezone.utc))
    return StrategyContext(
        timestamp=ts,
        status=kwargs.pop("status", "DRY_RUN_READY"),
        contract_state=kwargs.pop("contract_state", StrategyContractState.DRY_RUN_READY),
        contract_mode=kwargs.pop("contract_mode", StrategyContractMode.LONG_RESEARCH_ONLY),
        bridge_state=kwargs.pop("bridge_state", "DRY_RUN_READY"),
        bridge_mode=kwargs.pop("bridge_mode", "LONG_RESEARCH_ONLY"),
        dry_run=kwargs.pop("dry_run", True),
        live_trading_enabled=kwargs.pop("live_trading_enabled", False),
        real_orders_enabled=kwargs.pop("real_orders_enabled", False),
        leverage_enabled=kwargs.pop("leverage_enabled", False),
        shorting_enabled=kwargs.pop("shorting_enabled", False),
        reason_codes=kwargs.pop("reason_codes", (LONG_RESEARCH_SIGNAL_ALLOWED,)),
        input_refs=kwargs.pop("input_refs", StrategyContractInputRefs()),
        safety_flags=kwargs.pop("safety_flags", StrategyContractSafetyFlags()),
        data_quality=kwargs.pop("data_quality", StrategyContractDataQuality()),
        version=kwargs.pop("version", "1.0"),
        **kwargs,
    )


class TestBuildAdapterDecision:
    def test_missing_strategy_context_blocks(self) -> None:
        result = build_adapter_decision_context(None)
        assert result.adapter_state == AdapterState.BLOCKED
        assert result.adapter_mode == AdapterMode.BLOCK_ALL
        assert result.signal_intent == AdapterSignalIntent.BLOCK_SIGNAL
        assert result.reason_codes == (MISSING_STRATEGY_CONTEXT,)
        assert result.is_blocking() is True

    def test_invalid_strategy_context_blocks(self) -> None:
        class BadContext:
            pass
        result = build_adapter_decision_context(BadContext())  # type: ignore[arg-type]
        assert result.reason_codes == (INVALID_STRATEGY_CONTEXT,)
        assert result.is_blocking() is True

    def test_contract_state_blocked_blocks(self) -> None:
        ctx = _make_strategy_context(contract_state=StrategyContractState.BLOCKED)
        result = build_adapter_decision_context(ctx)
        assert result.reason_codes == (STRATEGY_CONTRACT_NOT_DRY_RUN_READY,)
        assert result.is_blocking() is True

    def test_contract_state_unknown_blocks(self) -> None:
        ctx = _make_strategy_context(contract_state=StrategyContractState.UNKNOWN)
        result = build_adapter_decision_context(ctx)
        assert result.reason_codes == (STRATEGY_CONTRACT_NOT_DRY_RUN_READY,)
        assert result.is_blocking() is True

    def test_contract_state_disabled_blocks(self) -> None:
        ctx = _make_strategy_context(contract_state=StrategyContractState.DISABLED)
        result = build_adapter_decision_context(ctx)
        assert result.reason_codes == (STRATEGY_CONTRACT_NOT_DRY_RUN_READY,)
        assert result.is_blocking() is True

    def test_contract_mode_block_all_blocks(self) -> None:
        ctx = _make_strategy_context(contract_mode=StrategyContractMode.BLOCK_ALL)
        result = build_adapter_decision_context(ctx)
        assert result.reason_codes == (STRATEGY_CONTRACT_MODE_BLOCK_ALL,)
        assert result.is_blocking() is True

    def test_dry_run_false_blocks(self) -> None:
        ctx = _ValidStrategyContext(dry_run=False)
        result = build_adapter_decision_context(ctx)  # type: ignore[arg-type]
        assert result.reason_codes == (DRY_RUN_DISABLED,)
        assert result.is_blocking() is True

    def test_live_trading_enabled_blocks(self) -> None:
        ctx = _ValidStrategyContext(live_trading_enabled=True)
        result = build_adapter_decision_context(ctx)  # type: ignore[arg-type]
        assert result.reason_codes == (LIVE_TRADING_ENABLED,)
        assert result.is_blocking() is True

    def test_real_orders_enabled_blocks(self) -> None:
        ctx = _ValidStrategyContext(real_orders_enabled=True)
        result = build_adapter_decision_context(ctx)  # type: ignore[arg-type]
        assert result.reason_codes == (REAL_ORDERS_ENABLED,)
        assert result.is_blocking() is True

    def test_leverage_enabled_blocks(self) -> None:
        ctx = _ValidStrategyContext(leverage_enabled=True)
        result = build_adapter_decision_context(ctx)  # type: ignore[arg-type]
        assert result.reason_codes == (LEVERAGE_ENABLED,)
        assert result.is_blocking() is True

    def test_shorting_enabled_blocks(self) -> None:
        ctx = _ValidStrategyContext(shorting_enabled=True)
        result = build_adapter_decision_context(ctx)  # type: ignore[arg-type]
        assert result.reason_codes == (SHORTING_ENABLED,)
        assert result.is_blocking() is True

    def test_stale_strategy_context_blocks(self) -> None:
        old_ts = datetime.now(timezone.utc) - timedelta(seconds=400)
        ctx = _make_strategy_context(timestamp=old_ts)
        result = build_adapter_decision_context(ctx)
        assert result.reason_codes == (STALE_STRATEGY_CONTEXT,)
        assert result.is_blocking() is True

    def test_naive_timestamp_blocks(self) -> None:
        naive_ts = datetime(2024, 1, 1, 12, 0, 0)
        ctx = _ValidStrategyContext(timestamp=naive_ts)
        result = build_adapter_decision_context(ctx)  # type: ignore[arg-type]
        assert result.reason_codes == (STALE_STRATEGY_CONTEXT,)
        assert result.is_blocking() is True

    def test_missing_timestamp_blocks(self) -> None:
        ctx = _ValidStrategyContext()
        delattr(ctx, "timestamp")
        result = build_adapter_decision_context(ctx)  # type: ignore[arg-type]
        assert result.reason_codes == (INVALID_STRATEGY_CONTEXT,)
        assert result.is_blocking() is True

    def test_long_research_allowed(self) -> None:
        ctx = _make_strategy_context(contract_mode=StrategyContractMode.LONG_RESEARCH_ONLY)
        result = build_adapter_decision_context(ctx)
        assert result.adapter_state == AdapterState.DRY_RUN_READY
        assert result.adapter_mode == AdapterMode.LONG_RESEARCH_ONLY
        assert result.signal_intent == AdapterSignalIntent.ALLOW_LONG_RESEARCH_SIGNAL
        assert result.reason_codes == (LONG_RESEARCH_SIGNAL_ALLOWED,)
        assert result.status == "DRY_RUN_READY"
        assert result.dry_run is True
        assert result.is_blocking() is False

    def test_short_research_allowed(self) -> None:
        ctx = _make_strategy_context(contract_mode=StrategyContractMode.SHORT_RESEARCH_ONLY)
        result = build_adapter_decision_context(ctx)
        assert result.adapter_state == AdapterState.DRY_RUN_READY
        assert result.adapter_mode == AdapterMode.SHORT_RESEARCH_ONLY
        assert result.signal_intent == AdapterSignalIntent.ALLOW_SHORT_RESEARCH_SIGNAL
        assert result.reason_codes == (SHORT_RESEARCH_SIGNAL_ALLOWED,)
        assert result.status == "DRY_RUN_READY"
        assert result.dry_run is True
        assert result.is_blocking() is False

    def test_custom_config(self) -> None:
        config = AdapterConfig(stale_strategy_context_seconds=60)
        old_ts = datetime.now(timezone.utc) - timedelta(seconds=120)
        ctx = _make_strategy_context(timestamp=old_ts)
        result = build_adapter_decision_context(ctx, config=config)
        assert result.reason_codes == (STALE_STRATEGY_CONTEXT,)

    def test_custom_now(self) -> None:
        now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        ctx = _make_strategy_context(timestamp=now)
        result = build_adapter_decision_context(ctx, now=now)
        assert result.timestamp == now
        assert result.adapter_state == AdapterState.DRY_RUN_READY

    def test_calculation_error_on_exception(self) -> None:
        class ExplodingContext:
            timestamp = property(lambda self: 1 / 0)  # type: ignore[assignment]
            status = "OK"
            contract_state = StrategyContractState.DRY_RUN_READY
            contract_mode = StrategyContractMode.LONG_RESEARCH_ONLY
            dry_run = True
            live_trading_enabled = False
            real_orders_enabled = False
            leverage_enabled = False
            shorting_enabled = False
        result = build_adapter_decision_context(ExplodingContext())  # type: ignore[arg-type]
        assert result.reason_codes == (CALCULATION_ERROR,)
        assert result.is_blocking() is True

    def test_safety_flags_in_allowed_output(self) -> None:
        ctx = _make_strategy_context()
        result = build_adapter_decision_context(ctx)
        assert result.safety_flags.dry_run is True
        assert result.safety_flags.live_trading_enabled is False
        assert result.safety_flags.real_orders_enabled is False
        assert result.safety_flags.leverage_enabled is False
        assert result.safety_flags.shorting_enabled is False
        assert result.safety_flags.adapter_runtime_allowed is False
        assert result.safety_flags.freqtrade_runtime_allowed is False
        assert result.safety_flags.strategy_class_allowed is False
        assert result.safety_flags.entry_signal_allowed is False
        assert result.safety_flags.exit_signal_allowed is False
        assert result.safety_flags.order_execution_allowed is False

    def test_data_quality_in_allowed_output(self) -> None:
        ctx = _make_strategy_context(contract_mode=StrategyContractMode.LONG_RESEARCH_ONLY)
        result = build_adapter_decision_context(ctx)
        assert result.data_quality.strategy_context_present is True
        assert result.data_quality.strategy_context_valid is True
        assert result.data_quality.strategy_context_stale is False
        assert result.data_quality.reason == LONG_RESEARCH_SIGNAL_ALLOWED

    def test_data_quality_in_short_output(self) -> None:
        ctx = _make_strategy_context(contract_mode=StrategyContractMode.SHORT_RESEARCH_ONLY)
        result = build_adapter_decision_context(ctx)
        assert result.data_quality.reason == SHORT_RESEARCH_SIGNAL_ALLOWED

    def test_strategy_contract_state_preserved(self) -> None:
        ctx = _make_strategy_context()
        result = build_adapter_decision_context(ctx)
        assert result.strategy_contract_state == "DRY_RUN_READY"

    def test_strategy_contract_mode_preserved(self) -> None:
        ctx = _make_strategy_context(contract_mode=StrategyContractMode.SHORT_RESEARCH_ONLY)
        result = build_adapter_decision_context(ctx)
        assert result.strategy_contract_mode == "SHORT_RESEARCH_ONLY"

    def test_input_refs_default(self) -> None:
        ctx = _make_strategy_context()
        result = build_adapter_decision_context(ctx)
        assert result.input_refs.strategy_context == "data/strategy/current_strategy_context.json"
        assert result.input_refs.adapter_decision == "data/strategy_adapter/current_adapter_decision.json"

    def test_version_default(self) -> None:
        ctx = _make_strategy_context()
        result = build_adapter_decision_context(ctx)
        assert result.version == "1.0"

    def test_all_execution_flags_false_in_allowed(self) -> None:
        ctx = _make_strategy_context()
        result = build_adapter_decision_context(ctx)
        assert result.entry_signal_allowed is False
        assert result.exit_signal_allowed is False
        assert result.order_execution_allowed is False
        assert result.adapter_runtime_allowed is False
        assert result.freqtrade_runtime_allowed is False
        assert result.strategy_class_allowed is False


class TestValidateAdapterInputs:
    def test_missing_returns_missing(self) -> None:
        result = validate_adapter_inputs(None, AdapterConfig(), datetime.now(timezone.utc))
        assert result == (MISSING_STRATEGY_CONTEXT,)

    def test_invalid_returns_invalid(self) -> None:
        class BadContext:
            pass
        result = validate_adapter_inputs(BadContext(), AdapterConfig(), datetime.now(timezone.utc))  # type: ignore[arg-type]
        assert result == (INVALID_STRATEGY_CONTEXT,)

    def test_blocked_state_returns_not_ready(self) -> None:
        ctx = _make_strategy_context(contract_state=StrategyContractState.BLOCKED)
        result = validate_adapter_inputs(ctx, AdapterConfig(), datetime.now(timezone.utc))
        assert result == (STRATEGY_CONTRACT_NOT_DRY_RUN_READY,)

    def test_unknown_state_returns_not_ready(self) -> None:
        ctx = _make_strategy_context(contract_state=StrategyContractState.UNKNOWN)
        result = validate_adapter_inputs(ctx, AdapterConfig(), datetime.now(timezone.utc))
        assert result == (STRATEGY_CONTRACT_NOT_DRY_RUN_READY,)

    def test_disabled_state_returns_not_ready(self) -> None:
        ctx = _make_strategy_context(contract_state=StrategyContractState.DISABLED)
        result = validate_adapter_inputs(ctx, AdapterConfig(), datetime.now(timezone.utc))
        assert result == (STRATEGY_CONTRACT_NOT_DRY_RUN_READY,)

    def test_block_all_mode_returns_block_all(self) -> None:
        ctx = _make_strategy_context(contract_mode=StrategyContractMode.BLOCK_ALL)
        result = validate_adapter_inputs(ctx, AdapterConfig(), datetime.now(timezone.utc))
        assert result == (STRATEGY_CONTRACT_MODE_BLOCK_ALL,)

    def test_dry_run_false_returns_dry_run_disabled(self) -> None:
        ctx = _ValidStrategyContext(dry_run=False)
        result = validate_adapter_inputs(ctx, AdapterConfig(), datetime.now(timezone.utc))  # type: ignore[arg-type]
        assert result == (DRY_RUN_DISABLED,)

    def test_live_trading_returns_live_trading(self) -> None:
        ctx = _ValidStrategyContext(live_trading_enabled=True)
        result = validate_adapter_inputs(ctx, AdapterConfig(), datetime.now(timezone.utc))  # type: ignore[arg-type]
        assert result == (LIVE_TRADING_ENABLED,)

    def test_real_orders_returns_real_orders(self) -> None:
        ctx = _ValidStrategyContext(real_orders_enabled=True)
        result = validate_adapter_inputs(ctx, AdapterConfig(), datetime.now(timezone.utc))  # type: ignore[arg-type]
        assert result == (REAL_ORDERS_ENABLED,)

    def test_leverage_returns_leverage(self) -> None:
        ctx = _ValidStrategyContext(leverage_enabled=True)
        result = validate_adapter_inputs(ctx, AdapterConfig(), datetime.now(timezone.utc))  # type: ignore[arg-type]
        assert result == (LEVERAGE_ENABLED,)

    def test_shorting_returns_shorting(self) -> None:
        ctx = _ValidStrategyContext(shorting_enabled=True)
        result = validate_adapter_inputs(ctx, AdapterConfig(), datetime.now(timezone.utc))  # type: ignore[arg-type]
        assert result == (SHORTING_ENABLED,)

    def test_stale_returns_stale(self) -> None:
        old_ts = datetime.now(timezone.utc) - timedelta(seconds=400)
        ctx = _make_strategy_context(timestamp=old_ts)
        result = validate_adapter_inputs(ctx, AdapterConfig(), datetime.now(timezone.utc))
        assert result == (STALE_STRATEGY_CONTEXT,)

    def test_naive_timestamp_returns_stale(self) -> None:
        naive_ts = datetime(2024, 1, 1, 12, 0, 0)
        ctx = _ValidStrategyContext(timestamp=naive_ts)
        result = validate_adapter_inputs(ctx, AdapterConfig(), datetime.now(timezone.utc))  # type: ignore[arg-type]
        assert result == (STALE_STRATEGY_CONTEXT,)

    def test_unsupported_mode_returns_unsupported(self) -> None:
        # Create a mock context with an unsupported mode
        ctx = _ValidStrategyContext(
            contract_state=StrategyContractState.DRY_RUN_READY,
            contract_mode="UNKNOWN_MODE",
        )
        result = validate_adapter_inputs(ctx, AdapterConfig(), datetime.now(timezone.utc))  # type: ignore[arg-type]
        assert result == (UNSUPPORTED_STRATEGY_MODE,)

    def test_valid_returns_empty(self) -> None:
        ctx = _make_strategy_context()
        result = validate_adapter_inputs(ctx, AdapterConfig(), datetime.now(timezone.utc))
        assert result == ()

    def test_priority_stops_at_first(self) -> None:
        # Multiple issues: missing context is first priority
        result = validate_adapter_inputs(None, AdapterConfig(), datetime.now(timezone.utc))
        assert result == (MISSING_STRATEGY_CONTEXT,)
        # Only one reason code returned
        assert len(result) == 1

    def test_priority_order_dry_run_before_live_trading(self) -> None:
        ctx = _ValidStrategyContext(dry_run=False, live_trading_enabled=True)
        result = validate_adapter_inputs(ctx, AdapterConfig(), datetime.now(timezone.utc))  # type: ignore[arg-type]
        # dry_run check comes before live_trading check
        assert result == (DRY_RUN_DISABLED,)

    def test_priority_order_live_trading_before_real_orders(self) -> None:
        ctx = _ValidStrategyContext(live_trading_enabled=True, real_orders_enabled=True)
        result = validate_adapter_inputs(ctx, AdapterConfig(), datetime.now(timezone.utc))  # type: ignore[arg-type]
        assert result == (LIVE_TRADING_ENABLED,)


class TestIsStaleStrategyContext:
    def test_fresh_context(self) -> None:
        ctx = _make_strategy_context()
        now = datetime.now(timezone.utc)
        assert is_stale_strategy_context(ctx, AdapterConfig(), now) is False

    def test_stale_context(self) -> None:
        old_ts = datetime.now(timezone.utc) - timedelta(seconds=400)
        ctx = _make_strategy_context(timestamp=old_ts)
        now = datetime.now(timezone.utc)
        assert is_stale_strategy_context(ctx, AdapterConfig(), now) is True

    def test_naive_timestamp(self) -> None:
        naive_ts = datetime(2024, 1, 1, 12, 0, 0)
        ctx = _ValidStrategyContext(timestamp=naive_ts)
        now = datetime.now(timezone.utc)
        assert is_stale_strategy_context(ctx, AdapterConfig(), now) is True  # type: ignore[arg-type]

    def test_none_timestamp(self) -> None:
        ctx = _ValidStrategyContext(timestamp=None)
        now = datetime.now(timezone.utc)
        assert is_stale_strategy_context(ctx, AdapterConfig(), now) is True  # type: ignore[arg-type]

    def test_missing_timestamp_attribute(self) -> None:
        ctx = _ValidStrategyContext()
        delattr(ctx, "timestamp")
        now = datetime.now(timezone.utc)
        assert is_stale_strategy_context(ctx, AdapterConfig(), now) is True  # type: ignore[arg-type]

    def test_custom_threshold(self) -> None:
        old_ts = datetime.now(timezone.utc) - timedelta(seconds=120)
        ctx = _make_strategy_context(timestamp=old_ts)
        now = datetime.now(timezone.utc)
        config = AdapterConfig(stale_strategy_context_seconds=60)
        assert is_stale_strategy_context(ctx, config, now) is True

    def test_custom_threshold_fresh(self) -> None:
        ts = datetime.now(timezone.utc) - timedelta(seconds=30)
        ctx = _make_strategy_context(timestamp=ts)
        now = datetime.now(timezone.utc)
        config = AdapterConfig(stale_strategy_context_seconds=60)
        assert is_stale_strategy_context(ctx, config, now) is False

    def test_exact_threshold_not_stale(self) -> None:
        now = datetime.now(timezone.utc)
        ts = now - timedelta(seconds=300)
        ctx = _make_strategy_context(timestamp=ts)
        config = AdapterConfig(stale_strategy_context_seconds=300)
        # age == threshold, not stale
        assert is_stale_strategy_context(ctx, config, now) is False


class TestMapStrategyToAdapterMode:
    def test_long_research(self) -> None:
        ctx = _make_strategy_context(contract_mode=StrategyContractMode.LONG_RESEARCH_ONLY)
        assert map_strategy_to_adapter_mode(ctx) == AdapterMode.LONG_RESEARCH_ONLY

    def test_short_research(self) -> None:
        ctx = _make_strategy_context(contract_mode=StrategyContractMode.SHORT_RESEARCH_ONLY)
        assert map_strategy_to_adapter_mode(ctx) == AdapterMode.SHORT_RESEARCH_ONLY

    def test_block_all(self) -> None:
        ctx = _make_strategy_context(contract_mode=StrategyContractMode.BLOCK_ALL)
        assert map_strategy_to_adapter_mode(ctx) == AdapterMode.BLOCK_ALL

    def test_unknown_mode(self) -> None:
        ctx = _ValidStrategyContext(contract_mode="UNKNOWN")
        assert map_strategy_to_adapter_mode(ctx) == AdapterMode.BLOCK_ALL  # type: ignore[arg-type]


class TestMapStrategyToSignalIntent:
    def test_long_research(self) -> None:
        ctx = _make_strategy_context(contract_mode=StrategyContractMode.LONG_RESEARCH_ONLY)
        assert map_strategy_to_signal_intent(ctx) == AdapterSignalIntent.ALLOW_LONG_RESEARCH_SIGNAL

    def test_short_research(self) -> None:
        ctx = _make_strategy_context(contract_mode=StrategyContractMode.SHORT_RESEARCH_ONLY)
        assert map_strategy_to_signal_intent(ctx) == AdapterSignalIntent.ALLOW_SHORT_RESEARCH_SIGNAL

    def test_block_all(self) -> None:
        ctx = _make_strategy_context(contract_mode=StrategyContractMode.BLOCK_ALL)
        assert map_strategy_to_signal_intent(ctx) == AdapterSignalIntent.BLOCK_SIGNAL

    def test_unknown_mode(self) -> None:
        ctx = _ValidStrategyContext(contract_mode="UNKNOWN")
        assert map_strategy_to_signal_intent(ctx) == AdapterSignalIntent.BLOCK_SIGNAL  # type: ignore[arg-type]


class TestBuildSafetyFlags:
    def test_defaults(self) -> None:
        config = AdapterConfig()
        flags = build_safety_flags(config)
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

    def test_custom_max_context_age(self) -> None:
        config = AdapterConfig(max_context_age_seconds=120)
        flags = build_safety_flags(config)
        assert flags.max_context_age_seconds == 120

    def test_all_unsafe_flags_false(self) -> None:
        config = AdapterConfig()
        flags = build_safety_flags(config)
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


class TestSafetyAbsence:
    def test_no_json_reading(self) -> None:
        import hunter.strategy_adapter.engine as engine_module
        source = engine_module.__loader__.get_source(engine_module.__name__)  # type: ignore[union-attr]
        assert "json" not in source or "import json" not in source

    def test_no_network_calls(self) -> None:
        import hunter.strategy_adapter.engine as engine_module
        source = engine_module.__loader__.get_source(engine_module.__name__)  # type: ignore[union-attr]
        assert "requests" not in source
        assert "urllib" not in source
        assert "socket" not in source

    def test_no_binance_import(self) -> None:
        import hunter.strategy_adapter.engine as engine_module
        source = engine_module.__loader__.get_source(engine_module.__name__)  # type: ignore[union-attr]
        assert "binance" not in source.lower()

    def test_no_freqtrade_runtime(self) -> None:
        import hunter.strategy_adapter.engine as engine_module
        source = engine_module.__loader__.get_source(engine_module.__name__)  # type: ignore[union-attr]
        assert "freqtrade" not in source.lower() or "strategy_contract" in source.lower()

    def test_no_strategy_class(self) -> None:
        import hunter.strategy_adapter.engine as engine_module
        source = engine_module.__loader__.get_source(engine_module.__name__)  # type: ignore[union-attr]
        assert "IStrategy" not in source
        assert "freqtrade.strategy" not in source

    def test_no_live_trading_enablement(self) -> None:
        import hunter.strategy_adapter.engine as engine_module
        source = engine_module.__loader__.get_source(engine_module.__name__)  # type: ignore[union-attr]
        assert "live_trading_enabled = True" not in source

    def test_no_leverage_enablement(self) -> None:
        import hunter.strategy_adapter.engine as engine_module
        source = engine_module.__loader__.get_source(engine_module.__name__)  # type: ignore[union-attr]
        assert "leverage_enabled = True" not in source

    def test_no_shorting_enablement(self) -> None:
        import hunter.strategy_adapter.engine as engine_module
        source = engine_module.__loader__.get_source(engine_module.__name__)  # type: ignore[union-attr]
        assert "shorting_enabled = True" not in source

    def test_no_entry_exit_logic(self) -> None:
        import hunter.strategy_adapter.engine as engine_module
        source = engine_module.__loader__.get_source(engine_module.__name__)  # type: ignore[union-attr]
        assert "entry" not in source.lower() or "signal" in source.lower()
        assert "exit" not in source.lower() or "signal" in source.lower()
        assert "stoploss" not in source.lower()
        assert "roi" not in source.lower()
        assert "pairlist" not in source.lower()
        assert "stake" not in source.lower()

    def test_no_order_execution(self) -> None:
        import hunter.strategy_adapter.engine as engine_module
        source = engine_module.__loader__.get_source(engine_module.__name__)  # type: ignore[union-attr]
        assert "order" not in source.lower() or "allowed" in source.lower()
        assert "execute" not in source.lower()

    def test_no_api_keys(self) -> None:
        import hunter.strategy_adapter.engine as engine_module
        source = engine_module.__loader__.get_source(engine_module.__name__)  # type: ignore[union-attr]
        assert "api_key" not in source.lower()
        assert "secret" not in source.lower()
        assert "token" not in source.lower() or "intent" in source.lower()
