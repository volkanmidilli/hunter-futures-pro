"""Decision engine for the Research Decision Gate Engine (MVP-59).

The engine consumes upstream research artifacts and produces an immutable,
deterministic, research-only ``ResearchDecisionGateReport``. It never reads the
clock, accesses files, mutates caller input, or imports real Freqtrade runtime
modules.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Mapping

from hunter.controlled_universe.models import ControlledUniverseReport
from hunter.portfolio_risk_evaluator.models import ValidatedPortfolioRiskContext

from hunter.research_decision_gate.models import (
    RESEARCH_DECISION_GATE_VERSION,
    DecisionSourceSummary,
    ResearchDecisionGateConfig,
    ResearchDecisionGateReport,
)
from hunter.research_decision_gate.policy import (
    build_canonical_safety_flags,
    classify_reason_codes,
    decision_reason_code,
    detect_contradictions,
    detect_review_conditions,
    evaluate_strategy_contract_policy,
    resolve_decision,
)
from hunter.research_decision_gate.validator import (
    validate_evaluated_at,
    validate_risk_context,
    validate_strategy_contract_input,
    validate_universe_report,
)


def _build_risk_context_summary(
    risk_context: ValidatedPortfolioRiskContext | None,
    reason_codes: tuple[str, ...],
    config: ResearchDecisionGateConfig,
    evaluated_at: datetime,
) -> DecisionSourceSummary:
    """Build a deterministic summary for the risk context source."""
    if risk_context is None:
        return DecisionSourceSummary(
            source_name="risk_context",
            present=False,
            accepted=False,
            fresh=False,
            fingerprint=None,
            reason_codes=reason_codes,
        )
    fresh = len(validate_risk_context(risk_context, config, evaluated_at)) == 0
    return DecisionSourceSummary(
        source_name="risk_context",
        present=True,
        accepted=getattr(risk_context, "accepted", False),
        fresh=fresh,
        fingerprint=getattr(risk_context, "risk_evaluation_fingerprint", None),
        reason_codes=reason_codes,
    )


def _build_universe_summary(
    universe_report: ControlledUniverseReport | None,
    reason_codes: tuple[str, ...],
    config: ResearchDecisionGateConfig,
    evaluated_at: datetime,
) -> DecisionSourceSummary:
    """Build a deterministic summary for the controlled universe source."""
    if universe_report is None:
        return DecisionSourceSummary(
            source_name="controlled_universe",
            present=False,
            accepted=False,
            fresh=False,
            fingerprint=None,
            reason_codes=reason_codes,
        )
    fresh = len(validate_universe_report(universe_report, config, evaluated_at)) == 0
    version = getattr(universe_report, "version", "") or ""
    generated_at = getattr(universe_report, "generated_at", None)
    fingerprint = f"{version}:{generated_at.isoformat() if generated_at else ''}"
    return DecisionSourceSummary(
        source_name="controlled_universe",
        present=True,
        accepted=(len(reason_codes) == 0),
        fresh=fresh,
        fingerprint=fingerprint,
        reason_codes=reason_codes,
    )


def _build_strategy_contract_summary(
    strategy_contract_input: Mapping[str, object] | None,
    reason_codes: tuple[str, ...],
) -> DecisionSourceSummary:
    """Build a deterministic summary for the optional strategy contract source."""
    if strategy_contract_input is None:
        return DecisionSourceSummary(
            source_name="strategy_contract",
            present=False,
            accepted=False,
            fresh=True,
            fingerprint=None,
            reason_codes=reason_codes,
        )
    fingerprint = None
    if isinstance(strategy_contract_input, Mapping):
        fp = strategy_contract_input.get("source_fingerprint")
        if isinstance(fp, str) and fp.strip():
            fingerprint = fp
    accepted = len(reason_codes) == 0
    return DecisionSourceSummary(
        source_name="strategy_contract",
        present=True,
        accepted=accepted,
        fresh=True,
        fingerprint=fingerprint,
        reason_codes=reason_codes,
    )


def _canonical_json(value: Any) -> str:
    """Serialize ``value`` to canonical JSON with sorted keys."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _build_decision_fingerprint(
    decision: str,
    blocking_reasons: tuple[str, ...],
    review_reasons: tuple[str, ...],
    safety_flags: Mapping[str, bool],
    evaluated_at: datetime,
    config: ResearchDecisionGateConfig,
    risk_context: ValidatedPortfolioRiskContext | None,
    universe_report: ControlledUniverseReport | None,
    strategy_contract_input: Mapping[str, object] | None,
) -> str:
    """Return a deterministic SHA-256 fingerprint of the decision state."""
    risk_fp = getattr(risk_context, "risk_evaluation_fingerprint", "") or ""
    universe_version = getattr(universe_report, "version", "") or ""
    universe_generated = ""
    universe_generated_at = getattr(universe_report, "generated_at", None)
    if isinstance(universe_generated_at, datetime):
        universe_generated = universe_generated_at.isoformat()
    contract_fp = ""
    if isinstance(strategy_contract_input, Mapping):
        fp = strategy_contract_input.get("source_fingerprint")
        if isinstance(fp, str):
            contract_fp = fp

    payload = {
        "decision": decision,
        "blocking_reasons": list(blocking_reasons),
        "review_reasons": list(review_reasons),
        "safety_flags": dict(sorted(safety_flags.items())),
        "evaluated_at": evaluated_at.isoformat(),
        "config": {
            "strategy_contract_policy": config.strategy_contract_policy,
            "max_universe_age_seconds": config.max_universe_age_seconds,
            "max_risk_context_age_seconds": config.max_risk_context_age_seconds,
            "allowed_future_skew_seconds": config.allowed_future_skew_seconds,
        },
        "risk_context_fingerprint": risk_fp,
        "universe_fingerprint": f"{universe_version}:{universe_generated}",
        "strategy_contract_fingerprint": contract_fp,
    }
    canonical = _canonical_json(payload)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_research_decision_gate_report(
    risk_context: ValidatedPortfolioRiskContext | None,
    universe_report: ControlledUniverseReport | None,
    config: ResearchDecisionGateConfig,
    *,
    strategy_contract_input: Mapping[str, object] | None = None,
    evaluated_at: datetime,
    metadata: Mapping[str, object] | None = None,
) -> ResearchDecisionGateReport:
    """Build a deterministic research-only decision gate report.

    The report is fail-closed: any blocking issue yields ``NO_GO``, review-only
    issues yield ``NEEDS_REVIEW``, and only clean inputs produce ``GO``.
    """
    if not isinstance(evaluated_at, datetime) or evaluated_at.tzinfo is None:
        raise ValueError(
            f"evaluated_at must be a timezone-aware datetime, got {evaluated_at!r}"
        )
    timestamp_reasons = validate_evaluated_at(evaluated_at, config)
    risk_reasons = validate_risk_context(risk_context, config, evaluated_at)
    universe_reasons = validate_universe_report(universe_report, config, evaluated_at)
    contract_blocking, contract_review = evaluate_strategy_contract_policy(
        strategy_contract_input, config
    )
    contract_validation = validate_strategy_contract_input(strategy_contract_input, config)

    # Combine all raw reasons; classify into blocking/review.
    raw_reasons: list[str] = []
    raw_reasons.extend(timestamp_reasons)
    raw_reasons.extend(risk_reasons)
    raw_reasons.extend(universe_reasons)
    raw_reasons.extend(contract_validation)
    raw_reasons.extend(contract_blocking)
    raw_reasons.extend(contract_review)
    raw_reasons.extend(detect_contradictions(risk_context, universe_report))
    raw_reasons.extend(detect_review_conditions(risk_context, universe_report, strategy_contract_input))

    blocking_reasons, review_reasons = classify_reason_codes(raw_reasons)

    decision = resolve_decision(blocking_reasons, review_reasons)
    safety_flags = build_canonical_safety_flags()

    decision_fingerprint = _build_decision_fingerprint(
        decision,
        blocking_reasons,
        review_reasons,
        safety_flags,
        evaluated_at,
        config,
        risk_context,
        universe_report,
        strategy_contract_input,
    )

    risk_summary = _build_risk_context_summary(
        risk_context, risk_reasons, config, evaluated_at
    )
    universe_summary = _build_universe_summary(
        universe_report, universe_reasons, config, evaluated_at
    )
    contract_summary = _build_strategy_contract_summary(
        strategy_contract_input, tuple(list(contract_blocking) + list(contract_review))
    )

    return ResearchDecisionGateReport(
        version=RESEARCH_DECISION_GATE_VERSION,
        decision=decision,  # type: ignore[arg-type]
        decision_fingerprint=decision_fingerprint,
        evaluated_at=evaluated_at,
        risk_context_summary=risk_summary,
        universe_summary=universe_summary,
        strategy_contract_summary=contract_summary,
        blocking_reason_codes=blocking_reasons,
        review_reason_codes=review_reasons,
        safety_flags=safety_flags,
        research_only=True,
        human_approval_required=True,
        metadata=metadata,
    )
