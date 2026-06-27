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
