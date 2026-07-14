"""Pure input validation for the Research Decision Gate Engine (MVP-59).

Validators are stateless, deterministic, and never read the clock, access files,
or mutate caller input. All timestamp checks use the injected ``evaluated_at``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Mapping

from hunter.controlled_universe.models import ControlledUniverseReport
from hunter.portfolio_risk_evaluator.models import ValidatedPortfolioRiskContext

from hunter.research_decision_gate.models import (
    IGNORE,
    INVALID_STRATEGY_CONTRACT,
    INVALID_TIMESTAMP,
    MISSING_HUMAN_APPROVAL_FLAG,
    MISSING_REQUIRED_FINGERPRINT,
    MISSING_RISK_CONTEXT,
    MISSING_UNIVERSE_REPORT,
    REJECTED_RISK_CONTEXT,
    REJECTED_UNIVERSE_REPORT,
    RISK_GATE_CLOSED,
    STALE_RISK_CONTEXT,
    STALE_UNIVERSE_REPORT,
    UNSAFE_RESEARCH_FLAG,
    UNSAFE_STRATEGY_CONTRACT,
    ResearchDecisionGateConfig,
)

if TYPE_CHECKING:
    from hunter.research_decision_gate.models import DecisionSourceSummary


def validate_evaluated_at(
    evaluated_at: datetime,
    config: ResearchDecisionGateConfig,
) -> tuple[str, ...]:
    """Return reason codes for an invalid or future ``evaluated_at`` timestamp."""
    reasons: list[str] = []
    if not isinstance(evaluated_at, datetime):
        reasons.append(INVALID_TIMESTAMP)
        return tuple(reasons)
    if evaluated_at.tzinfo is None:
        reasons.append(INVALID_TIMESTAMP)
        return tuple(reasons)
    now = datetime.now(timezone.utc)
    skew = config.allowed_future_skew_seconds
    if (evaluated_at - now).total_seconds() > skew:
        reasons.append(INVALID_TIMESTAMP)
    return tuple(reasons)


def _is_fresh(
    source_time: datetime,
    evaluated_at: datetime,
    max_age_seconds: int,
) -> bool:
    """Return True if ``source_time`` is not older than ``max_age_seconds`` from ``evaluated_at``."""
    if source_time.tzinfo is None:
        return False
    age = (evaluated_at - source_time).total_seconds()
    return age <= max_age_seconds


def validate_risk_context(
    risk_context: ValidatedPortfolioRiskContext | None,
    config: ResearchDecisionGateConfig,
    evaluated_at: datetime,
) -> tuple[str, ...]:
    """Return blocking reason codes for the risk context."""
    reasons: list[str] = []
    if risk_context is None:
        reasons.append(MISSING_RISK_CONTEXT)
        return tuple(reasons)
    if not getattr(risk_context, "accepted", False):
        reasons.append(REJECTED_RISK_CONTEXT)
    if not getattr(risk_context, "risk_gate_open", False):
        reasons.append(RISK_GATE_CLOSED)
    if getattr(risk_context, "mode", None) == "BLOCK_ALL":
        reasons.append(REJECTED_RISK_CONTEXT)
    if not getattr(risk_context, "research_only", True):
        reasons.append(UNSAFE_RESEARCH_FLAG)
    if not getattr(risk_context, "human_approval_required", True):
        reasons.append(MISSING_HUMAN_APPROVAL_FLAG)
    source_fp = getattr(risk_context, "source_portfolio_fingerprint", "") or ""
    eval_fp = getattr(risk_context, "risk_evaluation_fingerprint", "") or ""
    if not source_fp.strip() or not eval_fp.strip():
        reasons.append(MISSING_REQUIRED_FINGERPRINT)
    if not _is_fresh(
        getattr(risk_context, "evaluated_at", evaluated_at),
        evaluated_at,
        config.max_risk_context_age_seconds,
    ):
        reasons.append(STALE_RISK_CONTEXT)
    return tuple(reasons)


def validate_universe_report(
    universe_report: ControlledUniverseReport | None,
    config: ResearchDecisionGateConfig,
    evaluated_at: datetime,
) -> tuple[str, ...]:
    """Return blocking reason codes for the controlled universe report."""
    reasons: set[str] = set()
    if universe_report is None:
        return (MISSING_UNIVERSE_REPORT,)
    data_quality = getattr(universe_report, "data_quality", None)
    if data_quality is not None:
        if not getattr(data_quality, "safety_flags_ok", False):
            reasons.add(REJECTED_UNIVERSE_REPORT)
    safety_flags = getattr(universe_report, "safety_flags", None)
    if safety_flags is not None and getattr(safety_flags, "is_safe", True) is False:
        reasons.add(REJECTED_UNIVERSE_REPORT)
    if not _is_fresh(
        getattr(universe_report, "generated_at", evaluated_at),
        evaluated_at,
        config.max_universe_age_seconds,
    ):
        reasons.add(STALE_UNIVERSE_REPORT)
    return tuple(sorted(reasons))


_UNSAFE_CONTRACT_KEYS: frozenset[str] = frozenset(
    {
        "automatic_execution_allowed",
        "live_trading_allowed",
        "runtime_config_mutation_allowed",
        "real_orders_enabled",
        "leverage_enabled",
        "shorting_enabled",
        "entry_signals_allowed",
        "exit_signals_allowed",
        "strategy_runtime_allowed",
    }
)


def validate_strategy_contract_input(
    strategy_contract_input: Mapping[str, object] | None,
    config: ResearchDecisionGateConfig,
) -> tuple[str, ...]:
    """Return blocking reason codes for the strategy contract input.

    Under ``IGNORE`` policy the input is not validated. A missing input under
    any other policy is not a validation error here; policy applies the
    ``REQUIRE`` vs ``ALLOW_WITH_REVIEW`` semantics. Invalid or unsafe contracts
    are blocking regardless of policy.
    """
    if config.strategy_contract_policy == IGNORE:
        return ()

    if strategy_contract_input is None:
        return ()

    if not isinstance(strategy_contract_input, Mapping):
        return (INVALID_STRATEGY_CONTRACT,)

    research_only = strategy_contract_input.get("research_only")
    human_approval = strategy_contract_input.get("human_approval_required")
    if research_only is not True or human_approval is not True:
        return (UNSAFE_STRATEGY_CONTRACT,)

    for key, value in strategy_contract_input.items():
        if key in _UNSAFE_CONTRACT_KEYS and value is True:
            return (UNSAFE_STRATEGY_CONTRACT,)

    return ()


def validate_required_inputs(
    risk_context: ValidatedPortfolioRiskContext | None,
    universe_report: ControlledUniverseReport | None,
    config: ResearchDecisionGateConfig,
    evaluated_at: datetime,
) -> tuple[str, ...]:
    """Return all blocking reason codes for required inputs and timestamp."""
    reasons: list[str] = []
    reasons.extend(validate_evaluated_at(evaluated_at, config))
    reasons.extend(validate_risk_context(risk_context, config, evaluated_at))
    reasons.extend(validate_universe_report(universe_report, config, evaluated_at))
    return tuple(reasons)
