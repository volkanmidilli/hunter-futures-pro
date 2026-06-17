"""Decision engine for Hunter Futures Pro.

Implements the deterministic fail-closed decision rules from SPEC-004.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Tuple

from hunter.decision.models import (
    DecisionAction,
    DecisionConfig,
    DecisionInputRefs,
    DecisionOutput,
    DecisionState,
)
from hunter.market_state.models import (
    AllowedMode,
    BreadthOutput,
    DataQuality,
    OutputStatus,
    RegimeOutput,
    RegimeState,
    RiskState,
)


def validate_decision_inputs(
    regime_output: RegimeOutput | None,
    breadth_output: BreadthOutput | None,
    config: DecisionConfig,
) -> Tuple[bool, List[str], DataQuality]:
    """Validate inputs and return (is_valid, reason_codes, aggregated_data_quality).

    Checks all fail-closed conditions in priority order.
    Returns immediately on first failure with the appropriate reason code.
    """
    reasons: List[str] = []
    dq = DataQuality()

    # Priority 1: Missing RegimeOutput
    if regime_output is None:
        reasons.append("MISSING_REGIME")
        dq = DataQuality(missing=True)
        return False, reasons, dq

    # Priority 2: Missing BreadthOutput
    if breadth_output is None:
        reasons.append("MISSING_BREADTH")
        dq = DataQuality(missing=True)
        return False, reasons, dq

    # Aggregate data quality from both inputs
    dq = DataQuality(
        missing=regime_output.data_quality.missing or breadth_output.data_quality.missing,
        stale=regime_output.data_quality.stale or breadth_output.data_quality.stale,
        insufficient_history=regime_output.data_quality.insufficient_history
        or breadth_output.data_quality.insufficient_history,
        insufficient_universe=regime_output.data_quality.insufficient_universe
        or breadth_output.data_quality.insufficient_universe,
    )

    # Priority 3: Invalid RegimeOutput status
    if regime_output.status == OutputStatus.INVALID:
        reasons.append("INVALID_REGIME")
        return False, reasons, dq

    # Priority 4: Invalid BreadthOutput status
    if breadth_output.status == OutputStatus.INVALID:
        reasons.append("INVALID_BREADTH")
        return False, reasons, dq

    # Priority 5: UNKNOWN regime
    if regime_output.market_regime == RegimeState.UNKNOWN:
        reasons.append("UNKNOWN_REGIME")
        return False, reasons, dq

    # Priority 6: allowed_mode NONE
    if regime_output.allowed_mode == AllowedMode.NONE:
        reasons.append("ALLOWED_MODE_NONE")
        return False, reasons, dq

    # Priority 7: Low regime confidence
    if regime_output.confidence < config.min_regime_confidence:
        reasons.append("LOW_REGIME_CONFIDENCE")
        return False, reasons, dq

    # Priority 8: Stale inputs
    if is_stale_output(regime_output, breadth_output, config.stale_input_minutes):
        reasons.append("STALE_INPUT")
        dq = DataQuality(
            missing=dq.missing,
            stale=True,
            insufficient_history=dq.insufficient_history,
            insufficient_universe=dq.insufficient_universe,
        )
        return False, reasons, dq

    return True, reasons, dq


def is_stale_output(
    regime_output: RegimeOutput,
    breadth_output: BreadthOutput,
    stale_input_minutes: int,
) -> bool:
    """Check if either input is older than stale_input_minutes.

    Uses the older of the two timestamps for the check.
    """
    now = datetime.now(timezone.utc)
    # Use the older timestamp for staleness check
    oldest_timestamp = min(regime_output.timestamp, breadth_output.timestamp)
    age_minutes = (now - oldest_timestamp).total_seconds() / 60.0
    return age_minutes > stale_input_minutes


def detect_regime_breadth_conflict(
    regime_output: RegimeOutput,
    breadth_output: BreadthOutput,
) -> bool:
    """Detect conflicting signals between regime and breadth.

    Conflicts:
    - BULL + RISK_OFF breadth
    - BEAR + RISK_ON breadth
    - BULL + breadth_score < 50
    - BEAR + breadth_score > 50
    """
    regime = regime_output.market_regime
    health = breadth_output.market_health
    score = breadth_output.breadth_score

    if regime == RegimeState.BULL:
        if health == RiskState.RISK_OFF:
            return True
        if score < 50:
            return True

    if regime == RegimeState.BEAR:
        if health == RiskState.RISK_ON:
            return True
        if score > 50:
            return True

    return False


def calculate_decision_confidence(
    regime_output: RegimeOutput,
    breadth_output: BreadthOutput,
) -> float:
    """Calculate overall decision confidence.

    Uses minimum of regime confidence and normalized breadth score.
    """
    regime_conf = regime_output.confidence
    # Normalize breadth score to 0.0-1.0
    breadth_conf = breadth_output.breadth_score / 100.0
    return min(regime_conf, breadth_conf)


def make_decision(
    regime_output: RegimeOutput | None,
    breadth_output: BreadthOutput | None,
    config: DecisionConfig | None = None,
) -> DecisionOutput:
    """Make a deterministic decision based on regime and breadth outputs.

    Evaluates fail-closed rules in priority order, then decision rules.
    """
    cfg = config or DecisionConfig()
    now = datetime.now(timezone.utc)

    # Validate inputs (fail-closed checks)
    is_valid, reasons, dq = validate_decision_inputs(
        regime_output, breadth_output, cfg
    )

    if not is_valid:
        return DecisionOutput.block_all(
            timestamp=now,
            reason_codes=reasons,
            data_quality=dq,
        )

    # At this point both inputs are valid and non-None
    assert regime_output is not None
    assert breadth_output is not None

    # Build input refs
    input_refs = DecisionInputRefs(
        regime_timestamp=regime_output.timestamp.isoformat(),
        breadth_timestamp=breadth_output.timestamp.isoformat(),
        regime_source="regime_engine",
        breadth_source="breadth_engine",
    )

    # Priority 11: SIDEWAYS
    if regime_output.market_regime == RegimeState.SIDEWAYS:
        return DecisionOutput(
            timestamp=now,
            status=OutputStatus.VALID,
            decision_state=DecisionState.BLOCK,
            decision_action=DecisionAction.BLOCK_ALL,
            allowed_mode=AllowedMode.NONE,
            market_regime=RegimeState.SIDEWAYS,
            risk_state=regime_output.risk_state,
            confidence=regime_output.confidence,
            regime_confidence=regime_output.confidence,
            breadth_score=breadth_output.breadth_score,
            market_health=breadth_output.market_health,
            reason_codes=["SIDEWAYS_NO_DIRECTION"],
            input_refs=input_refs,
            data_quality=dq,
        )

    # Priority 12: TRANSITION
    if regime_output.market_regime == RegimeState.TRANSITION:
        return DecisionOutput(
            timestamp=now,
            status=OutputStatus.VALID,
            decision_state=DecisionState.BLOCK,
            decision_action=cfg.transition_action,
            allowed_mode=AllowedMode.NONE,
            market_regime=RegimeState.TRANSITION,
            risk_state=regime_output.risk_state,
            confidence=regime_output.confidence,
            regime_confidence=regime_output.confidence,
            breadth_score=breadth_output.breadth_score,
            market_health=breadth_output.market_health,
            reason_codes=["TRANSITION_UNCERTAIN"],
            input_refs=input_refs,
            data_quality=dq,
        )

    # Priority 13: Conflicting signals
    if detect_regime_breadth_conflict(regime_output, breadth_output):
        return DecisionOutput(
            timestamp=now,
            status=OutputStatus.VALID,
            decision_state=DecisionState.BLOCK,
            decision_action=cfg.conflict_action,
            allowed_mode=AllowedMode.NONE,
            market_regime=regime_output.market_regime,
            risk_state=regime_output.risk_state,
            confidence=regime_output.confidence,
            regime_confidence=regime_output.confidence,
            breadth_score=breadth_output.breadth_score,
            market_health=breadth_output.market_health,
            reason_codes=["CONFLICTING_SIGNALS"],
            input_refs=input_refs,
            data_quality=dq,
        )

    # Priority 9: BULL + LONG_ONLY + healthy breadth
    if (
        regime_output.market_regime == RegimeState.BULL
        and regime_output.allowed_mode == AllowedMode.LONG_ONLY
        and breadth_output.breadth_score >= cfg.min_breadth_score_for_long
    ):
        confidence = calculate_decision_confidence(regime_output, breadth_output)
        return DecisionOutput(
            timestamp=now,
            status=OutputStatus.VALID,
            decision_state=DecisionState.ALLOW,
            decision_action=DecisionAction.ENABLE_LONG_ONLY_RESEARCH,
            allowed_mode=AllowedMode.LONG_ONLY,
            market_regime=RegimeState.BULL,
            risk_state=regime_output.risk_state,
            confidence=confidence,
            regime_confidence=regime_output.confidence,
            breadth_score=breadth_output.breadth_score,
            market_health=breadth_output.market_health,
            reason_codes=["BULL_HEALTHY_BREADTH"],
            input_refs=input_refs,
            data_quality=dq,
        )

    # Priority 10: BEAR + SHORT_ONLY + weak breadth
    if (
        regime_output.market_regime == RegimeState.BEAR
        and regime_output.allowed_mode == AllowedMode.SHORT_ONLY
        and breadth_output.breadth_score <= cfg.max_breadth_score_for_short
    ):
        confidence = calculate_decision_confidence(regime_output, breadth_output)
        return DecisionOutput(
            timestamp=now,
            status=OutputStatus.VALID,
            decision_state=DecisionState.ALLOW,
            decision_action=DecisionAction.ENABLE_SHORT_ONLY_RESEARCH,
            allowed_mode=AllowedMode.SHORT_ONLY,
            market_regime=RegimeState.BEAR,
            risk_state=regime_output.risk_state,
            confidence=confidence,
            regime_confidence=regime_output.confidence,
            breadth_score=breadth_output.breadth_score,
            market_health=breadth_output.market_health,
            reason_codes=["BEAR_WEAK_BREADTH"],
            input_refs=input_refs,
            data_quality=dq,
        )

    # Priority 14: Default block (no rule matched)
    return DecisionOutput(
        timestamp=now,
        status=OutputStatus.VALID,
        decision_state=DecisionState.BLOCK,
        decision_action=DecisionAction.BLOCK_ALL,
        allowed_mode=AllowedMode.NONE,
        market_regime=regime_output.market_regime,
        risk_state=regime_output.risk_state,
        confidence=regime_output.confidence,
        regime_confidence=regime_output.confidence,
        breadth_score=breadth_output.breadth_score,
        market_health=breadth_output.market_health,
        reason_codes=["DEFAULT_BLOCK"],
        input_refs=input_refs,
        data_quality=dq,
    )
