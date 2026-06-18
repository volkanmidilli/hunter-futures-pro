"""Strategy contract engine for Hunter Futures Pro."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Tuple

from hunter.freqtrade_bridge.models import (
    FreqtradeBridgeContext,
    FreqtradeBridgeMode,
    FreqtradeBridgeState,
)
from hunter.strategy_contract.models import (
    BRIDGE_MODE_BLOCK_ALL,
    BRIDGE_NOT_DRY_RUN_READY,
    CALCULATION_ERROR,
    DRY_RUN_DISABLED,
    INVALID_BRIDGE_CONTEXT,
    LEVERAGE_ENABLED,
    LIVE_TRADING_ENABLED,
    LONG_RESEARCH_ALLOWED,
    MISSING_BRIDGE_CONTEXT,
    REAL_ORDERS_ENABLED,
    SHORTING_ENABLED,
    SHORT_RESEARCH_ALLOWED,
    STALE_BRIDGE_CONTEXT,
    UNSUPPORTED_BRIDGE_MODE,
    StrategyContractConfig,
    StrategyContractDataQuality,
    StrategyContractInputRefs,
    StrategyContractMode,
    StrategyContractSafetyFlags,
    StrategyContractState,
    StrategyContext,
)


_REQUIRED_BRIDGE_ATTRS = (
    "timestamp",
    "status",
    "bridge_state",
    "bridge_mode",
    "dry_run",
    "live_trading_enabled",
    "real_orders_enabled",
    "leverage_enabled",
    "shorting_enabled",
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_strategy_context(
    bridge_context: FreqtradeBridgeContext | None,
    config: StrategyContractConfig | None = None,
    now: datetime | None = None,
) -> StrategyContext:
    """Build a StrategyContext from a FreqtradeBridgeContext.

    Implements all 14 fail-closed rules from SPEC-007 in priority order.
    Any exception returns a blocked context with CALCULATION_ERROR.
    """
    try:
        cfg = config or StrategyContractConfig()
        ts = now or datetime.now(timezone.utc)
        reason_codes = validate_strategy_contract_inputs(bridge_context, cfg, ts)
        if reason_codes:
            return StrategyContext.blocked(reason_codes=reason_codes, timestamp=ts)

        # At this point bridge_context is guaranteed non-None and valid
        assert bridge_context is not None
        contract_mode = map_bridge_to_strategy_mode(bridge_context)

        if contract_mode == StrategyContractMode.LONG_RESEARCH_ONLY:
            return StrategyContext(
                timestamp=ts,
                status="DRY_RUN_READY",
                contract_state=StrategyContractState.DRY_RUN_READY,
                contract_mode=StrategyContractMode.LONG_RESEARCH_ONLY,
                bridge_state=bridge_context.bridge_state.value,
                bridge_mode=bridge_context.bridge_mode.value,
                dry_run=True,
                live_trading_enabled=False,
                real_orders_enabled=False,
                leverage_enabled=False,
                shorting_enabled=False,
                strategy_runtime_allowed=False,
                entry_signals_allowed=False,
                exit_signals_allowed=False,
                reason_codes=(LONG_RESEARCH_ALLOWED,),
                input_refs=StrategyContractInputRefs(),
                safety_flags=build_safety_flags(cfg),
                data_quality=StrategyContractDataQuality(
                    bridge_context_present=True,
                    bridge_context_valid=True,
                    bridge_context_stale=False,
                    reason=LONG_RESEARCH_ALLOWED,
                ),
                version="1.0",
            )

        if contract_mode == StrategyContractMode.SHORT_RESEARCH_ONLY:
            return StrategyContext(
                timestamp=ts,
                status="DRY_RUN_READY",
                contract_state=StrategyContractState.DRY_RUN_READY,
                contract_mode=StrategyContractMode.SHORT_RESEARCH_ONLY,
                bridge_state=bridge_context.bridge_state.value,
                bridge_mode=bridge_context.bridge_mode.value,
                dry_run=True,
                live_trading_enabled=False,
                real_orders_enabled=False,
                leverage_enabled=False,
                shorting_enabled=False,
                strategy_runtime_allowed=False,
                entry_signals_allowed=False,
                exit_signals_allowed=False,
                reason_codes=(SHORT_RESEARCH_ALLOWED,),
                input_refs=StrategyContractInputRefs(),
                safety_flags=build_safety_flags(cfg),
                data_quality=StrategyContractDataQuality(
                    bridge_context_present=True,
                    bridge_context_valid=True,
                    bridge_context_stale=False,
                    reason=SHORT_RESEARCH_ALLOWED,
                ),
                version="1.0",
            )

        # Fallback — unsupported mode produces BLOCK_ALL
        return StrategyContext.blocked(
            reason_codes=(UNSUPPORTED_BRIDGE_MODE,), timestamp=ts
        )
    except Exception:
        return StrategyContext.blocked(reason_codes=(CALCULATION_ERROR,))


def validate_strategy_contract_inputs(
    bridge_context: FreqtradeBridgeContext | None,
    config: StrategyContractConfig,
    now: datetime,
) -> Tuple[str, ...]:
    """Validate bridge context and return blocking reason codes.

    Returns empty tuple if valid.  Otherwise returns a single reason code
    for the first blocking condition encountered (priority order).
    """
    # 1. Missing bridge context
    if bridge_context is None:
        return (MISSING_BRIDGE_CONTEXT,)

    # 2. Invalid bridge context — missing required attributes
    for attr in _REQUIRED_BRIDGE_ATTRS:
        if not hasattr(bridge_context, attr):
            return (INVALID_BRIDGE_CONTEXT,)

    # 3. Bridge state not DRY_RUN_READY
    if bridge_context.bridge_state != FreqtradeBridgeState.DRY_RUN_READY:
        return (BRIDGE_NOT_DRY_RUN_READY,)

    # 4. Bridge mode BLOCK_ALL
    if bridge_context.bridge_mode == FreqtradeBridgeMode.BLOCK_ALL:
        return (BRIDGE_MODE_BLOCK_ALL,)

    # 5. dry_run not True
    if not bridge_context.dry_run:
        return (DRY_RUN_DISABLED,)

    # 6. live_trading_enabled not False
    if bridge_context.live_trading_enabled:
        return (LIVE_TRADING_ENABLED,)

    # 7. real_orders_enabled not False
    if bridge_context.real_orders_enabled:
        return (REAL_ORDERS_ENABLED,)

    # 8. leverage_enabled not False
    if bridge_context.leverage_enabled:
        return (LEVERAGE_ENABLED,)

    # 9. shorting_enabled not False
    if bridge_context.shorting_enabled:
        return (SHORTING_ENABLED,)

    # 10. Stale bridge context
    if is_stale_bridge_context(bridge_context, config, now):
        return (STALE_BRIDGE_CONTEXT,)

    # 11. Unsupported bridge mode (anything other than LONG/SHORT_RESEARCH_ONLY)
    if bridge_context.bridge_mode not in (
        FreqtradeBridgeMode.LONG_RESEARCH_ONLY,
        FreqtradeBridgeMode.SHORT_RESEARCH_ONLY,
    ):
        return (UNSUPPORTED_BRIDGE_MODE,)

    return ()


def is_stale_bridge_context(
    bridge_context: FreqtradeBridgeContext,
    config: StrategyContractConfig,
    now: datetime,
) -> bool:
    """Return True if the bridge context is stale or has an invalid timestamp."""
    # Missing or invalid timestamp → stale
    if not hasattr(bridge_context, "timestamp"):
        return True
    ts = bridge_context.timestamp
    if ts is None or not isinstance(ts, datetime):
        return True
    if ts.tzinfo is None:
        return True
    age_seconds = (now - ts).total_seconds()
    return age_seconds > config.stale_bridge_context_seconds


def map_bridge_to_strategy_mode(
    bridge_context: FreqtradeBridgeContext,
) -> StrategyContractMode:
    """Map bridge mode to strategy contract mode."""
    if bridge_context.bridge_mode == FreqtradeBridgeMode.LONG_RESEARCH_ONLY:
        return StrategyContractMode.LONG_RESEARCH_ONLY
    if bridge_context.bridge_mode == FreqtradeBridgeMode.SHORT_RESEARCH_ONLY:
        return StrategyContractMode.SHORT_RESEARCH_ONLY
    return StrategyContractMode.BLOCK_ALL


def build_safety_flags(config: StrategyContractConfig) -> StrategyContractSafetyFlags:
    """Build safety flags from config, preserving safe defaults."""
    return StrategyContractSafetyFlags(
        dry_run=True,
        live_trading_enabled=False,
        real_orders_enabled=False,
        leverage_enabled=False,
        shorting_enabled=False,
        strategy_runtime_allowed=False,
        entry_signals_allowed=False,
        exit_signals_allowed=False,
        max_context_age_seconds=config.max_context_age_seconds,
    )
