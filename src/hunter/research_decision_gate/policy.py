"""Decision policy logic for the Research Decision Gate Engine (MVP-59).

Policy functions are pure, deterministic, and stateless. They classify reason
codes, apply strategy-contract policies, detect contradictions between required
inputs, and resolve the final decision.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Mapping

from hunter.controlled_universe.models import ControlledUniverseReport
from hunter.portfolio_risk_evaluator.models import ValidatedPortfolioRiskContext

from hunter.research_decision_gate.models import (
    ALLOW_WITH_REVIEW,
    BLOCKING_REASON_CODES,
    CONTRADICTORY_INPUTS,
    DECISION_GO,
    DECISION_NEEDS_REVIEW,
    DECISION_NO_GO,
    IGNORE,
    INCOMPLETE_PROVENANCE,
    INVALID_STRATEGY_CONTRACT,
    MISSING_STRATEGY_CONTRACT,
    OPTIONAL_STRATEGY_CONTRACT_MISSING,
    REQUIRE,
    REVIEW_REASON_CODES,
    STRATEGY_CONTRACT_MODE_MISMATCH,
    STRATEGY_CONTRACT_SCOPE_MISMATCH,
    UNSAFE_STRATEGY_CONTRACT,
    UNKNOWN_NON_BLOCKING_FIELD,
    UPSTREAM_REVIEW_REQUIRED,
    ResearchDecisionGateConfig,
)

if TYPE_CHECKING:
    from collections.abc import Sequence


def build_canonical_safety_flags() -> dict[str, bool]:
    """Return the canonical safety flags for every decision gate report."""
    return {
        "research_only": True,
        "human_approval_required": True,
        "automatic_execution_allowed": False,
        "runtime_config_mutation_allowed": False,
        "live_trading_allowed": False,
    }


def classify_reason_codes(reason_codes: Sequence[str]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Split ``reason_codes`` into (blocking, review) tuples in input order."""
    blocking: list[str] = []
    review: list[str] = []
    seen: set[str] = set()
    for code in reason_codes:
        if code in seen:
            continue
        seen.add(code)
        if code in BLOCKING_REASON_CODES:
            blocking.append(code)
        elif code in REVIEW_REASON_CODES:
            review.append(code)
    return tuple(blocking), tuple(review)


def evaluate_strategy_contract_policy(
    strategy_contract_input: Mapping[str, object] | None,
    config: ResearchDecisionGateConfig,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Apply the configured strategy-contract policy.

    Returns (blocking_reasons, review_reasons). Under ``IGNORE`` both are empty.
    """
    policy = config.strategy_contract_policy
    if policy == IGNORE:
        return (), ()

    if strategy_contract_input is None:
        if policy == REQUIRE:
            return (MISSING_STRATEGY_CONTRACT,), ()
        return (), (OPTIONAL_STRATEGY_CONTRACT_MISSING,)

    if not isinstance(strategy_contract_input, Mapping):
        return (INVALID_STRATEGY_CONTRACT,), ()

    research_only = strategy_contract_input.get("research_only")
    human_approval = strategy_contract_input.get("human_approval_required")
    if research_only is not True or human_approval is not True:
        return (UNSAFE_STRATEGY_CONTRACT,), ()

    review: list[str] = []
    contract_mode = strategy_contract_input.get("mode")
    if contract_mode is not None and contract_mode not in ("LONG", "SHORT", "BLOCK_ALL"):
        review.append(STRATEGY_CONTRACT_MODE_MISMATCH)
    contract_scope = strategy_contract_input.get("scope")
    if contract_scope is not None and contract_scope not in ("research", "read-only"):
        review.append(STRATEGY_CONTRACT_SCOPE_MISMATCH)

    # Surface unknown non-blocking fields as review reasons for transparency.
    known_keys = {
        "research_only",
        "human_approval_required",
        "mode",
        "scope",
        "version",
        "source_fingerprint",
        "whitelist",
        "blacklist",
    }
    for key in strategy_contract_input:
        if key not in known_keys:
            review.append(UNKNOWN_NON_BLOCKING_FIELD)
            break

    return (), tuple(review)


def detect_contradictions(
    risk_context: ValidatedPortfolioRiskContext | None,
    universe_report: ControlledUniverseReport | None,
) -> tuple[str, ...]:
    """Return blocking reason codes for contradictory required inputs."""
    reasons: list[str] = []
    if risk_context is None or universe_report is None:
        return tuple(reasons)

    risk_mode = getattr(risk_context, "mode", None)
    universe_mode = getattr(universe_report, "allowed_mode", None)
    if risk_mode is not None and universe_mode is not None:
        if risk_mode == "LONG" and universe_mode == "SHORT_ONLY":
            reasons.append(CONTRADICTORY_INPUTS)
        elif risk_mode == "SHORT" and universe_mode == "LONG_ONLY":
            reasons.append(CONTRADICTORY_INPUTS)

    blocked = set(getattr(universe_report, "blocked", ()))
    allocations = getattr(risk_context, "validated_allocations", ())
    for alloc in allocations:
        pair = getattr(alloc, "pair", None)
        if pair is not None and pair in blocked:
            reasons.append(CONTRADICTORY_INPUTS)
            break

    return tuple(reasons)


def detect_review_conditions(
    risk_context: ValidatedPortfolioRiskContext | None,
    universe_report: ControlledUniverseReport | None,
    strategy_contract_input: Mapping[str, object] | None,
) -> tuple[str, ...]:
    """Return review reason codes for non-blocking upstream ambiguity."""
    review: list[str] = []

    if risk_context is not None:
        if not getattr(risk_context, "accepted", True):
            review.append(UPSTREAM_REVIEW_REQUIRED)
        if getattr(risk_context, "mode", None) == "BLOCK_ALL":
            review.append(UPSTREAM_REVIEW_REQUIRED)

    if universe_report is not None:
        data_quality = getattr(universe_report, "data_quality", None)
        if data_quality is not None:
            if not getattr(data_quality, "all_counts_consistent", True):
                review.append(INCOMPLETE_PROVENANCE)
        watchlist = getattr(universe_report, "watchlist", ())
        if watchlist:
            review.append(UPSTREAM_REVIEW_REQUIRED)

    risk_fp = getattr(risk_context, "source_portfolio_fingerprint", "") or ""
    risk_eval_fp = getattr(risk_context, "risk_evaluation_fingerprint", "") or ""
    if risk_context is not None and (not risk_fp or not risk_eval_fp):
        review.append(INCOMPLETE_PROVENANCE)

    if strategy_contract_input is not None and not isinstance(strategy_contract_input, Mapping):
        review.append(UPSTREAM_REVIEW_REQUIRED)

    return tuple(dict.fromkeys(review))


def resolve_decision(
    blocking_reasons: Sequence[str],
    review_reasons: Sequence[str],
) -> str:
    """Resolve final decision from blocking and review reasons."""
    if blocking_reasons:
        return "NO_GO"
    if review_reasons:
        return "NEEDS_REVIEW"
    return "GO"


def decision_reason_code(decision: str) -> str:
    """Return the canonical decision reason code for a decision value."""
    if decision == "GO":
        return DECISION_GO
    if decision == "NO_GO":
        return DECISION_NO_GO
    if decision == "NEEDS_REVIEW":
        return DECISION_NEEDS_REVIEW
    raise ValueError(f"unsupported decision: {decision!r}")
