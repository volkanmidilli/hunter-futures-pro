"""Dry-run strategy engine for Hunter Futures Pro."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Tuple

from hunter.dry_run_strategy.models import (
    ADAPTER_MODE_BLOCK_ALL,
    ADAPTER_NOT_DRY_RUN_READY,
    ADAPTER_SIGNAL_BLOCKED,
    CALCULATION_ERROR,
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


_REQUIRED_ADAPTER_ATTRS = (
    "timestamp",
    "status",
    "adapter_state",
    "adapter_mode",
    "signal_intent",
    "dry_run",
    "live_trading_enabled",
    "real_orders_enabled",
    "leverage_enabled",
    "shorting_enabled",
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_dry_run_strategy_runtime_context(
    adapter_decision_context: object | None,
    config: DryRunStrategyConfig | None = None,
    now: datetime | None = None,
) -> DryRunStrategyRuntimeContext:
    """Build a DryRunStrategyRuntimeContext from an AdapterDecisionContext.

    Implements all fail-closed dry-run strategy rules from SPEC-009 in priority order.
    Any exception returns a blocked context with CALCULATION_ERROR.
    """
    try:
        cfg = config or DryRunStrategyConfig()
        ts = now or datetime.now(timezone.utc)
        reason_codes = validate_dry_run_strategy_inputs(adapter_decision_context, cfg, ts)
        if reason_codes:
            return DryRunStrategyRuntimeContext.blocked(reason_codes=reason_codes, timestamp=ts)

        # At this point adapter_decision_context is guaranteed non-None and valid
        assert adapter_decision_context is not None
        strategy_mode = map_adapter_to_strategy_mode(adapter_decision_context)
        signal_action = map_adapter_to_signal_action(adapter_decision_context)

        if strategy_mode == DryRunStrategyMode.LONG_RESEARCH_ONLY:
            return DryRunStrategyRuntimeContext(
                timestamp=ts,
                status="DRY_RUN_READY",
                strategy_state=DryRunStrategyState.DRY_RUN_READY,
                strategy_mode=DryRunStrategyMode.LONG_RESEARCH_ONLY,
                signal_action=DryRunSignalAction.EXPOSE_LONG_RESEARCH_SIGNAL,
                adapter_state=str(adapter_decision_context.adapter_state),
                adapter_mode=str(adapter_decision_context.adapter_mode),
                adapter_signal_intent=str(adapter_decision_context.signal_intent),
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
                safety_flags=build_safety_flags(cfg),
                data_quality=DryRunStrategyDataQuality(
                    adapter_decision_present=True,
                    adapter_decision_valid=True,
                    adapter_decision_stale=False,
                    reason=LONG_RESEARCH_SIGNAL_EXPOSED,
                ),
                version="1.0",
            )

        if strategy_mode == DryRunStrategyMode.SHORT_RESEARCH_ONLY:
            return DryRunStrategyRuntimeContext(
                timestamp=ts,
                status="DRY_RUN_READY",
                strategy_state=DryRunStrategyState.DRY_RUN_READY,
                strategy_mode=DryRunStrategyMode.SHORT_RESEARCH_ONLY,
                signal_action=DryRunSignalAction.EXPOSE_SHORT_RESEARCH_SIGNAL,
                adapter_state=str(adapter_decision_context.adapter_state),
                adapter_mode=str(adapter_decision_context.adapter_mode),
                adapter_signal_intent=str(adapter_decision_context.signal_intent),
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
                reason_codes=(SHORT_RESEARCH_SIGNAL_EXPOSED,),
                input_refs=DryRunStrategyInputRefs(),
                safety_flags=build_safety_flags(cfg),
                data_quality=DryRunStrategyDataQuality(
                    adapter_decision_present=True,
                    adapter_decision_valid=True,
                    adapter_decision_stale=False,
                    reason=SHORT_RESEARCH_SIGNAL_EXPOSED,
                ),
                version="1.0",
            )

        # Fallback — unsupported mode produces BLOCK_ALL
        return DryRunStrategyRuntimeContext.blocked(
            reason_codes=(UNSUPPORTED_ADAPTER_MODE,), timestamp=ts
        )
    except Exception:
        return DryRunStrategyRuntimeContext.blocked(reason_codes=(CALCULATION_ERROR,))


def validate_dry_run_strategy_inputs(
    adapter_decision_context: object | None,
    config: DryRunStrategyConfig,
    now: datetime,
) -> Tuple[str, ...]:
    """Validate adapter decision context and return blocking reason codes.

    Returns empty tuple if valid. Otherwise returns a single reason code
    for the first blocking condition encountered (priority order).
    """
    # 1. Missing adapter decision context
    if adapter_decision_context is None:
        return (MISSING_ADAPTER_DECISION_CONTEXT,)

    # 2. Invalid adapter decision context — missing required attributes
    for attr in _REQUIRED_ADAPTER_ATTRS:
        if not hasattr(adapter_decision_context, attr):
            return (INVALID_ADAPTER_DECISION_CONTEXT,)

    # 3. Adapter state not DRY_RUN_READY
    if str(adapter_decision_context.adapter_state) != "DRY_RUN_READY":
        return (ADAPTER_NOT_DRY_RUN_READY,)

    # 4. Adapter mode BLOCK_ALL
    if str(adapter_decision_context.adapter_mode) == "BLOCK_ALL":
        return (ADAPTER_MODE_BLOCK_ALL,)

    # 5. Adapter signal intent BLOCK_SIGNAL
    if str(adapter_decision_context.signal_intent) == "BLOCK_SIGNAL":
        return (ADAPTER_SIGNAL_BLOCKED,)

    # 6. dry_run not True
    if not adapter_decision_context.dry_run:
        return (DRY_RUN_DISABLED,)

    # 7. live_trading_enabled not False
    if adapter_decision_context.live_trading_enabled:
        return (LIVE_TRADING_ENABLED,)

    # 8. real_orders_enabled not False
    if adapter_decision_context.real_orders_enabled:
        return (REAL_ORDERS_ENABLED,)

    # 9. leverage_enabled not False
    if adapter_decision_context.leverage_enabled:
        return (LEVERAGE_ENABLED,)

    # 10. shorting_enabled not False
    if adapter_decision_context.shorting_enabled:
        return (SHORTING_ENABLED,)

    # 11. Stale adapter decision context
    if is_stale_adapter_decision_context(adapter_decision_context, config, now):
        return (STALE_ADAPTER_DECISION_CONTEXT,)

    # 12. Unsupported adapter mode (anything other than LONG/SHORT_RESEARCH_ONLY)
    if str(adapter_decision_context.adapter_mode) not in (
        "LONG_RESEARCH_ONLY",
        "SHORT_RESEARCH_ONLY",
    ):
        return (UNSUPPORTED_ADAPTER_MODE,)

    # 13. Unsupported adapter signal intent (anything other than ALLOW_LONG/SHORT_RESEARCH_SIGNAL)
    if str(adapter_decision_context.signal_intent) not in (
        "ALLOW_LONG_RESEARCH_SIGNAL",
        "ALLOW_SHORT_RESEARCH_SIGNAL",
    ):
        return (UNSUPPORTED_ADAPTER_SIGNAL_INTENT,)

    return ()


def is_stale_adapter_decision_context(
    adapter_decision_context: object,
    config: DryRunStrategyConfig,
    now: datetime,
) -> bool:
    """Return True if the adapter decision context is stale or has an invalid timestamp."""
    # Missing or invalid timestamp → stale
    if not hasattr(adapter_decision_context, "timestamp"):
        return True
    ts = adapter_decision_context.timestamp
    if ts is None or not isinstance(ts, datetime):
        return True
    if ts.tzinfo is None:
        return True
    age_seconds = (now - ts).total_seconds()
    return age_seconds > config.stale_adapter_decision_seconds


def map_adapter_to_strategy_mode(
    adapter_decision_context: object,
) -> DryRunStrategyMode:
    """Map adapter mode to dry-run strategy mode."""
    mode = str(adapter_decision_context.adapter_mode)
    if mode == "LONG_RESEARCH_ONLY":
        return DryRunStrategyMode.LONG_RESEARCH_ONLY
    if mode == "SHORT_RESEARCH_ONLY":
        return DryRunStrategyMode.SHORT_RESEARCH_ONLY
    return DryRunStrategyMode.BLOCK_ALL


def map_adapter_to_signal_action(
    adapter_decision_context: object,
) -> DryRunSignalAction:
    """Map adapter signal intent to dry-run strategy signal action."""
    intent = str(adapter_decision_context.signal_intent)
    if intent == "ALLOW_LONG_RESEARCH_SIGNAL":
        return DryRunSignalAction.EXPOSE_LONG_RESEARCH_SIGNAL
    if intent == "ALLOW_SHORT_RESEARCH_SIGNAL":
        return DryRunSignalAction.EXPOSE_SHORT_RESEARCH_SIGNAL
    return DryRunSignalAction.BLOCK_SIGNAL


def build_safety_flags(config: DryRunStrategyConfig) -> DryRunStrategySafetyFlags:
    """Build safety flags from config, preserving safe defaults."""
    return DryRunStrategySafetyFlags(
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
        max_context_age_seconds=config.max_context_age_seconds,
    )
