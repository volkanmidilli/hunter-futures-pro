"""Freqtrade bridge engine for Hunter Futures Pro."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Tuple

from hunter.execution.models import (
    ExecutionContext,
    ExecutionMode,
    ExecutionState,
)
from hunter.freqtrade_bridge.models import (
    FreqtradeBridgeConfig,
    FreqtradeBridgeContext,
    FreqtradeBridgeDataQuality,
    FreqtradeBridgeInputRefs,
    FreqtradeBridgeMode,
    FreqtradeBridgeSafetyFlags,
    FreqtradeBridgeState,
)


def validate_freqtrade_bridge_inputs(
    execution_context: ExecutionContext | None,
    config: FreqtradeBridgeConfig | None = None,
) -> Tuple[FreqtradeBridgeState, FreqtradeBridgeMode, List[str]]:
    """Validate ExecutionContext against fail-closed rules.

    Returns (bridge_state, bridge_mode, reason_codes).
    Rules are applied in strict priority order — the first matching rule wins.
    """
    # Priority 1: Missing ExecutionContext
    if execution_context is None:
        return FreqtradeBridgeState.BLOCKED, FreqtradeBridgeMode.BLOCK_ALL, [
            "missing_execution_context"
        ]

    # Priority 2: Invalid type
    if not isinstance(execution_context, ExecutionContext):
        return FreqtradeBridgeState.BLOCKED, FreqtradeBridgeMode.BLOCK_ALL, [
            "invalid_execution_context_type"
        ]

    # Priority 3: ExecutionState not DRY_RUN_ONLY
    if execution_context.execution_state != ExecutionState.DRY_RUN_ONLY:
        return (
            FreqtradeBridgeState.BLOCKED,
            FreqtradeBridgeMode.BLOCK_ALL,
            [
                f"execution_state_not_dry_run_only:{execution_context.execution_state.value.lower()}"
            ],
        )

    # Priority 4: ExecutionMode BLOCK_ALL
    if execution_context.execution_mode == ExecutionMode.BLOCK_ALL:
        return FreqtradeBridgeState.BLOCKED, FreqtradeBridgeMode.BLOCK_ALL, [
            "execution_mode_is_block_all"
        ]

    # Priority 5-11: Safety flags from ExecutionContext
    safety = execution_context.safety_flags
    flag_checks = [
        ("dry_run", False, "dry_run_disabled"),
        ("live_trading_enabled", True, "live_trading_enabled"),
        ("exchange_connection_enabled", True, "exchange_connection_enabled"),
        ("freqtrade_enabled", True, "freqtrade_enabled"),
    ]
    for flag, dangerous_value, reason in flag_checks:
        if getattr(safety, flag, not dangerous_value) == dangerous_value:
            return FreqtradeBridgeState.BLOCKED, FreqtradeBridgeMode.BLOCK_ALL, [reason]

    # Also check direct ExecutionContext fields for safety
    if not execution_context.dry_run:
        return FreqtradeBridgeState.BLOCKED, FreqtradeBridgeMode.BLOCK_ALL, [
            "dry_run_disabled"
        ]
    if execution_context.live_trading_enabled:
        return FreqtradeBridgeState.BLOCKED, FreqtradeBridgeMode.BLOCK_ALL, [
            "live_trading_enabled"
        ]
    if execution_context.exchange_connection_enabled:
        return FreqtradeBridgeState.BLOCKED, FreqtradeBridgeMode.BLOCK_ALL, [
            "exchange_connection_enabled"
        ]
    if execution_context.freqtrade_enabled:
        return FreqtradeBridgeState.BLOCKED, FreqtradeBridgeMode.BLOCK_ALL, [
            "freqtrade_enabled"
        ]

    # Priority 12: Stale ExecutionContext
    if is_stale_execution_context(execution_context, config):
        return FreqtradeBridgeState.BLOCKED, FreqtradeBridgeMode.BLOCK_ALL, [
            "stale_execution_context"
        ]

    # Priority 13-17: Mode mapping
    return map_execution_to_bridge_mode(execution_context, config)


def is_stale_execution_context(
    execution_context: ExecutionContext,
    config: FreqtradeBridgeConfig | None = None,
) -> bool:
    """Check if ExecutionContext is older than the stale threshold."""
    if config is None:
        stale_seconds = 300
    else:
        stale_seconds = config.stale_execution_context_seconds

    age = datetime.now(timezone.utc) - execution_context.timestamp
    return age.total_seconds() > stale_seconds


def map_execution_to_bridge_mode(
    execution_context: ExecutionContext,
    config: FreqtradeBridgeConfig | None = None,
) -> Tuple[FreqtradeBridgeState, FreqtradeBridgeMode, List[str]]:
    """Map ExecutionContext mode to FreqtradeBridgeState and FreqtradeBridgeMode.

    Returns (bridge_state, bridge_mode, reason_codes).
    """
    mode = execution_context.execution_mode

    if mode == ExecutionMode.LONG_RESEARCH_ONLY:
        return (
            FreqtradeBridgeState.DRY_RUN_READY,
            FreqtradeBridgeMode.LONG_RESEARCH_ONLY,
            ["dry_run_long_research_only"],
        )
    elif mode == ExecutionMode.SHORT_RESEARCH_ONLY:
        return (
            FreqtradeBridgeState.DRY_RUN_READY,
            FreqtradeBridgeMode.SHORT_RESEARCH_ONLY,
            ["dry_run_short_research_only"],
        )
    elif mode == ExecutionMode.BLOCK_ALL:
        return (
            FreqtradeBridgeState.BLOCKED,
            FreqtradeBridgeMode.BLOCK_ALL,
            ["execution_mode_is_block_all"],
        )
    elif mode == ExecutionMode.DRY_RUN_ONLY:
        # DRY_RUN_ONLY without a research direction is treated as unsupported
        return (
            FreqtradeBridgeState.BLOCKED,
            FreqtradeBridgeMode.BLOCK_ALL,
            ["unsupported_execution_mode:dry_run_only"],
        )
    else:
        return (
            FreqtradeBridgeState.BLOCKED,
            FreqtradeBridgeMode.BLOCK_ALL,
            [f"unsupported_execution_mode:{mode.value.lower()}"],
        )


def build_safety_flags(
    execution_context: ExecutionContext | None,
) -> FreqtradeBridgeSafetyFlags:
    """Build FreqtradeBridgeSafetyFlags from ExecutionContext safety flags."""
    if execution_context is None:
        return FreqtradeBridgeSafetyFlags()

    # Map ExecutionContext safety flags to FreqtradeBridgeSafetyFlags
    # ExecutionContext has: dry_run, live_trading_enabled, exchange_connection_enabled,
    # freqtrade_enabled, human_override_required, max_context_age_seconds
    safety = execution_context.safety_flags

    return FreqtradeBridgeSafetyFlags(
        dry_run=safety.dry_run,
        live_trading_enabled=safety.live_trading_enabled,
        exchange_connection_enabled=safety.exchange_connection_enabled,
        freqtrade_runtime_enabled=safety.freqtrade_enabled,
        strategy_enabled=False,  # Always False in MVP-5
        real_orders_enabled=False,  # Always False in MVP-5
        leverage_enabled=False,  # Always False in MVP-5
        shorting_enabled=False,  # Always False in MVP-5
        human_override_required=safety.human_override_required,
        max_context_age_seconds=safety.max_context_age_seconds,
    )


def build_freqtrade_bridge_context(
    execution_context: ExecutionContext | None,
    config: FreqtradeBridgeConfig | None = None,
) -> FreqtradeBridgeContext:
    """Build FreqtradeBridgeContext from ExecutionContext.

    This is the main entry point for the Freqtrade Bridge Engine.
    """
    bridge_state, bridge_mode, reason_codes = validate_freqtrade_bridge_inputs(
        execution_context, config
    )

    status = "success" if bridge_state == FreqtradeBridgeState.DRY_RUN_READY else "blocked"

    # Build safety flags
    safety_flags = build_safety_flags(execution_context)

    # Build input refs
    if execution_context is not None:
        input_refs = FreqtradeBridgeInputRefs(
            execution_context_timestamp=execution_context.timestamp.isoformat(),
            execution_context_version=execution_context.version,
        )
    else:
        input_refs = FreqtradeBridgeInputRefs()

    # Build data quality
    is_valid = execution_context is not None and isinstance(
        execution_context, ExecutionContext
    )
    is_fresh = bridge_state != FreqtradeBridgeState.BLOCKED or "stale" not in reason_codes[0]
    data_quality = FreqtradeBridgeDataQuality(
        execution_context_fresh=is_fresh,
        execution_context_valid=is_valid,
        validation_errors=[] if bridge_state == FreqtradeBridgeState.DRY_RUN_READY else reason_codes,
    )

    return FreqtradeBridgeContext(
        timestamp=datetime.now(timezone.utc),
        status=status,
        bridge_state=bridge_state,
        bridge_mode=bridge_mode,
        execution_state=execution_context.execution_state.value.lower()
        if execution_context is not None
        else "unknown",
        execution_mode=execution_context.execution_mode.value.lower()
        if execution_context is not None
        else "unknown",
        dry_run=safety_flags.dry_run,
        live_trading_enabled=safety_flags.live_trading_enabled,
        exchange_connection_enabled=safety_flags.exchange_connection_enabled,
        freqtrade_runtime_enabled=safety_flags.freqtrade_runtime_enabled,
        strategy_enabled=safety_flags.strategy_enabled,
        real_orders_enabled=safety_flags.real_orders_enabled,
        leverage_enabled=safety_flags.leverage_enabled,
        shorting_enabled=safety_flags.shorting_enabled,
        reason_codes=reason_codes,
        input_refs=input_refs,
        data_quality=data_quality,
        safety_flags=safety_flags,
        version="1.0",
    )
