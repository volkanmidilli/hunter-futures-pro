"""Strategy adapter engine for Hunter Futures Pro."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Tuple

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
    StrategyContractMode,
    StrategyContractState,
    StrategyContext,
)


_REQUIRED_STRATEGY_ATTRS = (
    "timestamp",
    "status",
    "contract_state",
    "contract_mode",
    "dry_run",
    "live_trading_enabled",
    "real_orders_enabled",
    "leverage_enabled",
    "shorting_enabled",
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_adapter_decision_context(
    strategy_context: StrategyContext | None,
    config: AdapterConfig | None = None,
    now: datetime | None = None,
) -> AdapterDecisionContext:
    """Build an AdapterDecisionContext from a StrategyContext.

    Implements all fail-closed adapter rules from SPEC-008 in priority order.
    Any exception returns a blocked decision with CALCULATION_ERROR.
    """
    try:
        cfg = config or AdapterConfig()
        ts = now or datetime.now(timezone.utc)
        reason_codes = validate_adapter_inputs(strategy_context, cfg, ts)
        if reason_codes:
            return AdapterDecisionContext.blocked(reason_codes=reason_codes, timestamp=ts)

        # At this point strategy_context is guaranteed non-None and valid
        assert strategy_context is not None
        adapter_mode = map_strategy_to_adapter_mode(strategy_context)
        signal_intent = map_strategy_to_signal_intent(strategy_context)

        if adapter_mode == AdapterMode.LONG_RESEARCH_ONLY:
            return AdapterDecisionContext(
                timestamp=ts,
                status="DRY_RUN_READY",
                adapter_state=AdapterState.DRY_RUN_READY,
                adapter_mode=AdapterMode.LONG_RESEARCH_ONLY,
                signal_intent=AdapterSignalIntent.ALLOW_LONG_RESEARCH_SIGNAL,
                strategy_contract_state=str(strategy_context.contract_state.value),
                strategy_contract_mode=str(strategy_context.contract_mode.value),
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
                safety_flags=build_safety_flags(cfg),
                data_quality=AdapterDataQuality(
                    strategy_context_present=True,
                    strategy_context_valid=True,
                    strategy_context_stale=False,
                    reason=LONG_RESEARCH_SIGNAL_ALLOWED,
                ),
                version="1.0",
            )

        if adapter_mode == AdapterMode.SHORT_RESEARCH_ONLY:
            return AdapterDecisionContext(
                timestamp=ts,
                status="DRY_RUN_READY",
                adapter_state=AdapterState.DRY_RUN_READY,
                adapter_mode=AdapterMode.SHORT_RESEARCH_ONLY,
                signal_intent=AdapterSignalIntent.ALLOW_SHORT_RESEARCH_SIGNAL,
                strategy_contract_state=str(strategy_context.contract_state.value),
                strategy_contract_mode=str(strategy_context.contract_mode.value),
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
                reason_codes=(SHORT_RESEARCH_SIGNAL_ALLOWED,),
                input_refs=AdapterInputRefs(),
                safety_flags=build_safety_flags(cfg),
                data_quality=AdapterDataQuality(
                    strategy_context_present=True,
                    strategy_context_valid=True,
                    strategy_context_stale=False,
                    reason=SHORT_RESEARCH_SIGNAL_ALLOWED,
                ),
                version="1.0",
            )

        # Fallback — unsupported mode produces BLOCK_ALL
        return AdapterDecisionContext.blocked(
            reason_codes=(UNSUPPORTED_STRATEGY_MODE,), timestamp=ts
        )
    except Exception:
        return AdapterDecisionContext.blocked(reason_codes=(CALCULATION_ERROR,))


def validate_adapter_inputs(
    strategy_context: StrategyContext | None,
    config: AdapterConfig,
    now: datetime,
) -> Tuple[str, ...]:
    """Validate strategy context and return blocking reason codes.

    Returns empty tuple if valid.  Otherwise returns a single reason code
    for the first blocking condition encountered (priority order).
    """
    # 1. Missing strategy context
    if strategy_context is None:
        return (MISSING_STRATEGY_CONTEXT,)

    # 2. Invalid strategy context — missing required attributes
    for attr in _REQUIRED_STRATEGY_ATTRS:
        if not hasattr(strategy_context, attr):
            return (INVALID_STRATEGY_CONTEXT,)

    # 3. Contract state not DRY_RUN_READY
    if strategy_context.contract_state != StrategyContractState.DRY_RUN_READY:
        return (STRATEGY_CONTRACT_NOT_DRY_RUN_READY,)

    # 4. Contract mode BLOCK_ALL
    if strategy_context.contract_mode == StrategyContractMode.BLOCK_ALL:
        return (STRATEGY_CONTRACT_MODE_BLOCK_ALL,)

    # 5. dry_run not True
    if not strategy_context.dry_run:
        return (DRY_RUN_DISABLED,)

    # 6. live_trading_enabled not False
    if strategy_context.live_trading_enabled:
        return (LIVE_TRADING_ENABLED,)

    # 7. real_orders_enabled not False
    if strategy_context.real_orders_enabled:
        return (REAL_ORDERS_ENABLED,)

    # 8. leverage_enabled not False
    if strategy_context.leverage_enabled:
        return (LEVERAGE_ENABLED,)

    # 9. shorting_enabled not False
    if strategy_context.shorting_enabled:
        return (SHORTING_ENABLED,)

    # 10. Stale strategy context
    if is_stale_strategy_context(strategy_context, config, now):
        return (STALE_STRATEGY_CONTEXT,)

    # 11. Unsupported strategy mode (anything other than LONG/SHORT_RESEARCH_ONLY)
    if strategy_context.contract_mode not in (
        StrategyContractMode.LONG_RESEARCH_ONLY,
        StrategyContractMode.SHORT_RESEARCH_ONLY,
    ):
        return (UNSUPPORTED_STRATEGY_MODE,)

    return ()


def is_stale_strategy_context(
    strategy_context: StrategyContext,
    config: AdapterConfig,
    now: datetime,
) -> bool:
    """Return True if the strategy context is stale or has an invalid timestamp."""
    # Missing or invalid timestamp → stale
    if not hasattr(strategy_context, "timestamp"):
        return True
    ts = strategy_context.timestamp
    if ts is None or not isinstance(ts, datetime):
        return True
    if ts.tzinfo is None:
        return True
    age_seconds = (now - ts).total_seconds()
    return age_seconds > config.stale_strategy_context_seconds


def map_strategy_to_adapter_mode(
    strategy_context: StrategyContext,
) -> AdapterMode:
    """Map strategy contract mode to adapter mode."""
    if strategy_context.contract_mode == StrategyContractMode.LONG_RESEARCH_ONLY:
        return AdapterMode.LONG_RESEARCH_ONLY
    if strategy_context.contract_mode == StrategyContractMode.SHORT_RESEARCH_ONLY:
        return AdapterMode.SHORT_RESEARCH_ONLY
    return AdapterMode.BLOCK_ALL


def map_strategy_to_signal_intent(
    strategy_context: StrategyContext,
) -> AdapterSignalIntent:
    """Map strategy contract mode to adapter signal intent."""
    if strategy_context.contract_mode == StrategyContractMode.LONG_RESEARCH_ONLY:
        return AdapterSignalIntent.ALLOW_LONG_RESEARCH_SIGNAL
    if strategy_context.contract_mode == StrategyContractMode.SHORT_RESEARCH_ONLY:
        return AdapterSignalIntent.ALLOW_SHORT_RESEARCH_SIGNAL
    return AdapterSignalIntent.BLOCK_SIGNAL


def build_safety_flags(config: AdapterConfig) -> AdapterSafetyFlags:
    """Build safety flags from config, preserving safe defaults."""
    return AdapterSafetyFlags(
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
        max_context_age_seconds=config.max_context_age_seconds,
    )
