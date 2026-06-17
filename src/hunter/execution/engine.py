"""Execution bridge engine for Hunter Futures Pro."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from hunter.decision.models import DecisionAction, DecisionOutput, DecisionState
from hunter.market_state.models import AllowedMode, DataQuality, OutputStatus

from hunter.execution.models import (
    ExecutionBridgeConfig,
    ExecutionContext,
    ExecutionInputRefs,
    ExecutionMode,
    ExecutionSafetyFlags,
    ExecutionState,
)


def is_stale_decision(decision_output: DecisionOutput, config: ExecutionBridgeConfig) -> bool:
    """Check if the DecisionOutput is older than the stale threshold."""
    now = datetime.now(timezone.utc)
    age_minutes = (now - decision_output.timestamp).total_seconds() / 60.0
    return age_minutes > config.stale_decision_minutes


def build_safety_flags(
    decision_output: DecisionOutput,
    config: ExecutionBridgeConfig,
    is_stale: bool,
    is_invalid: bool,
    is_blocked: bool,
    is_unsupported: bool,
) -> ExecutionSafetyFlags:
    """Build safety flags dict for external inspection."""
    return ExecutionSafetyFlags(
        dry_run=True,
        live_trading_enabled=False,
        exchange_connection_enabled=False,
        freqtrade_enabled=False,
        human_override_required=False,
        max_context_age_seconds=300,
    )


def map_decision_to_execution_mode(
    decision_action: DecisionAction,
    config: ExecutionBridgeConfig,
) -> ExecutionMode:
    """Map a DecisionAction to the corresponding ExecutionMode."""
    if decision_action == DecisionAction.ENABLE_LONG_ONLY_RESEARCH:
        return ExecutionMode.LONG_RESEARCH_ONLY
    if decision_action == DecisionAction.ENABLE_SHORT_ONLY_RESEARCH:
        return ExecutionMode.SHORT_RESEARCH_ONLY
    if decision_action == DecisionAction.BLOCK_ALL:
        return ExecutionMode.BLOCK_ALL
    if decision_action == DecisionAction.MANUAL_REVIEW:
        return config.manual_review_action
    return config.unsupported_action


def validate_execution_inputs(
    decision_output: DecisionOutput | None,
    config: ExecutionBridgeConfig,
) -> tuple[bool, List[str]]:
    """Validate inputs and return (is_valid, reason_codes).

    Checks all MVP-4 safety constraints in priority order.
    """
    reasons: List[str] = []

    # Priority 1: Missing DecisionOutput
    if decision_output is None:
        reasons.append("MISSING_DECISION")
        return False, reasons

    # Priority 2: Invalid DecisionOutput status
    if decision_output.status == OutputStatus.INVALID:
        reasons.append("INVALID_DECISION")
        return False, reasons

    # Priority 3-4: DecisionState not ALLOW
    if decision_output.decision_state == DecisionState.BLOCK:
        reasons.append("DECISION_BLOCKED")
        return False, reasons
    if decision_output.decision_state == DecisionState.UNKNOWN:
        reasons.append("UNKNOWN_DECISION")
        return False, reasons

    # Priority 5-6: DecisionAction blocks or requires review
    if decision_output.decision_action == DecisionAction.BLOCK_ALL:
        reasons.append("ACTION_BLOCKED_ALL")
        return False, reasons
    if decision_output.decision_action == DecisionAction.MANUAL_REVIEW:
        reasons.append("MANUAL_REVIEW_REQUIRED")
        return False, reasons

    # Priority 7: Stale decision
    if is_stale_decision(decision_output, config):
        reasons.append("STALE_DECISION")
        return False, reasons

    # Priority 8-11: Safety config violations (MVP-4 enforces these)
    if not config.dry_run_required:
        reasons.append("DRY_RUN_REQUIRED")
        return False, reasons
    if config.live_trading_enabled:
        reasons.append("LIVE_TRADING_BLOCKED")
        return False, reasons
    if config.exchange_connection_enabled:
        reasons.append("EXCHANGE_BLOCKED")
        return False, reasons
    if config.freqtrade_enabled:
        reasons.append("FREQTRADE_BLOCKED")
        return False, reasons

    # Priority 12: Unsupported action
    supported_actions = {
        DecisionAction.ENABLE_LONG_ONLY_RESEARCH,
        DecisionAction.ENABLE_SHORT_ONLY_RESEARCH,
    }
    if decision_output.decision_action not in supported_actions:
        reasons.append("UNSUPPORTED_ACTION")
        return False, reasons

    return True, reasons


def build_execution_context(
    decision_output: DecisionOutput | None,
    config: ExecutionBridgeConfig | None = None,
) -> ExecutionContext:
    """Build an ExecutionContext from a DecisionOutput.

    Implements all 15 fail-closed rules from SPEC-005 in priority order.
    All successful paths produce DRY_RUN_ONLY (ENABLED is reserved for future).
    """
    config = config or ExecutionBridgeConfig()
    now = datetime.now(timezone.utc)

    is_valid, reasons = validate_execution_inputs(decision_output, config)

    if not is_valid or decision_output is None:
        # Build data quality from available info
        dq = DataQuality()
        if decision_output is not None:
            dq = decision_output.data_quality
        return ExecutionContext.blocked(
            timestamp=now,
            reason_codes=reasons,
            data_quality=dq,
        )

    # Map decision action to execution mode
    execution_mode = map_decision_to_execution_mode(decision_output.decision_action, config)

    # Determine execution state: DRY_RUN_ONLY for all successful paths in MVP-4
    if execution_mode == ExecutionMode.BLOCK_ALL:
        execution_state = ExecutionState.BLOCKED
    else:
        execution_state = ExecutionState.DRY_RUN_ONLY

    # Build safety flags
    safety_flags = build_safety_flags(
        decision_output=decision_output,
        config=config,
        is_stale=False,
        is_invalid=False,
        is_blocked=False,
        is_unsupported=False,
    )

    # Build input refs
    ts_str = decision_output.timestamp.isoformat()
    if ts_str.endswith("+00:00"):
        ts_str = ts_str[:-6] + "Z"
    input_refs = ExecutionInputRefs(
        decision_timestamp=ts_str,
        decision_source="decision_engine",
    )

    # Build reason codes for successful paths
    if execution_mode == ExecutionMode.LONG_RESEARCH_ONLY:
        reason_codes = ["LONG_RESEARCH_ENABLED"]
    elif execution_mode == ExecutionMode.SHORT_RESEARCH_ONLY:
        reason_codes = ["SHORT_RESEARCH_ENABLED"]
    else:
        reason_codes = ["DEFAULT_BLOCK"]

    return ExecutionContext(
        timestamp=now,
        status=OutputStatus.VALID,
        execution_state=execution_state,
        execution_mode=execution_mode,
        decision_state=decision_output.decision_state,
        decision_action=decision_output.decision_action,
        allowed_mode=decision_output.allowed_mode,
        dry_run=True,
        live_trading_enabled=False,
        exchange_connection_enabled=False,
        freqtrade_enabled=False,
        reason_codes=reason_codes,
        input_refs=input_refs,
        data_quality=decision_output.data_quality,
        safety_flags=safety_flags,
        version="1.0",
    )
