"""Dry-run strategy public API exports."""

from __future__ import annotations

from hunter.dry_run_strategy.models import (
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
    ADAPTER_NOT_DRY_RUN_READY,
    ADAPTER_MODE_BLOCK_ALL,
    ADAPTER_SIGNAL_BLOCKED,
    UNSUPPORTED_ADAPTER_MODE,
    UNSUPPORTED_ADAPTER_SIGNAL_INTENT,
)

from hunter.dry_run_strategy.engine import (
    build_dry_run_strategy_runtime_context,
    build_safety_flags,
    is_stale_adapter_decision_context,
    map_adapter_to_signal_action,
    map_adapter_to_strategy_mode,
    validate_dry_run_strategy_inputs,
)

__all__ = [
    # Enums
    "DryRunStrategyState",
    "DryRunStrategyMode",
    "DryRunSignalAction",
    # Models
    "DryRunStrategyConfig",
    "DryRunStrategyInputRefs",
    "DryRunStrategySafetyFlags",
    "DryRunStrategyDataQuality",
    "DryRunStrategyRuntimeContext",
    # Engine
    "build_dry_run_strategy_runtime_context",
    "validate_dry_run_strategy_inputs",
    "is_stale_adapter_decision_context",
    "map_adapter_to_strategy_mode",
    "map_adapter_to_signal_action",
    "build_safety_flags",
    # Reason codes
    "MISSING_ADAPTER_DECISION_CONTEXT",
    "INVALID_ADAPTER_DECISION_CONTEXT",
    "ADAPTER_NOT_DRY_RUN_READY",
    "ADAPTER_MODE_BLOCK_ALL",
    "ADAPTER_SIGNAL_BLOCKED",
    "DRY_RUN_DISABLED",
    "LIVE_TRADING_ENABLED",
    "REAL_ORDERS_ENABLED",
    "LEVERAGE_ENABLED",
    "SHORTING_ENABLED",
    "STALE_ADAPTER_DECISION_CONTEXT",
    "UNSUPPORTED_ADAPTER_MODE",
    "UNSUPPORTED_ADAPTER_SIGNAL_INTENT",
    "LONG_RESEARCH_SIGNAL_EXPOSED",
    "SHORT_RESEARCH_SIGNAL_EXPOSED",
    "DEFAULT_BLOCK_SIGNAL",
    "CALCULATION_ERROR",
    "REASON_CODES",
]
