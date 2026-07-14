"""Public API for the Research Decision Gate Engine (MVP-59).

The engine consumes a ``ValidatedPortfolioRiskContext`` (MVP-58), a
``ControlledUniverseReport`` (MVP-51/MVP-52), and an optional strategy-contract
mapping, and produces a deterministic, research-only, human-approval-required
``ResearchDecisionGateReport``.

All outputs are explicitly marked as research-only and require human approval
before any downstream use. The engine is fail-closed and never integrates with
Freqtrade runtime, exchanges, databases, schedulers, or live trading systems.
"""

from __future__ import annotations

from hunter.research_decision_gate.engine import build_research_decision_gate_report
from hunter.research_decision_gate.models import (
    ALLOW_WITH_REVIEW,
    BLOCKING_REASON_CODES,
    CONTRADICTORY_INPUTS,
    CONTRADICTORY_SAFETY_FLAGS,
    DECISION_GO,
    DECISION_NEEDS_REVIEW,
    DECISION_NO_GO,
    DECISION_REASON_CODES,
    GO,
    IGNORE,
    INVALID_STRATEGY_CONTRACT,
    INVALID_TIMESTAMP,
    MISSING_HUMAN_APPROVAL_FLAG,
    MISSING_REQUIRED_FINGERPRINT,
    MISSING_RISK_CONTEXT,
    MISSING_STRATEGY_CONTRACT,
    MISSING_UNIVERSE_REPORT,
    NEEDS_REVIEW,
    NO_GO,
    OPTIONAL_STRATEGY_CONTRACT_MISSING,
    REQUIRE,
    REJECTED_RISK_CONTEXT,
    REJECTED_UNIVERSE_REPORT,
    RESEARCH_DECISION_GATE_REASON_CODES,
    RESEARCH_DECISION_GATE_VERSION,
    REVIEW_REASON_CODES,
    RISK_GATE_CLOSED,
    STALE_RISK_CONTEXT,
    STALE_UNIVERSE_REPORT,
    UNSAFE_RESEARCH_FLAG,
    UNSAFE_STRATEGY_CONTRACT,
    UPSTREAM_REVIEW_REQUIRED,
    DecisionSourceSummary,
    ResearchDecisionGateConfig,
    ResearchDecisionGateError,
    ResearchDecisionGateReport,
)
from hunter.research_decision_gate.policy import (
    build_canonical_safety_flags,
    classify_reason_codes,
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
from hunter.research_decision_gate.writer import (
    atomic_write_json_research_decision_gate_report,
    atomic_write_markdown_research_decision_gate_report,
    research_decision_gate_report_to_dict,
    research_decision_gate_report_to_json_text,
    research_decision_gate_report_to_markdown_text,
    write_research_decision_gate_report,
)

__all__ = [
    # Version
    "RESEARCH_DECISION_GATE_VERSION",
    # Policies
    "ALLOW_WITH_REVIEW",
    "REQUIRE",
    "IGNORE",
    # Decision values
    "GO",
    "NO_GO",
    "NEEDS_REVIEW",
    # Decision reason codes
    "DECISION_GO",
    "DECISION_NO_GO",
    "DECISION_NEEDS_REVIEW",
    # Reason code sets
    "BLOCKING_REASON_CODES",
    "REVIEW_REASON_CODES",
    "DECISION_REASON_CODES",
    "RESEARCH_DECISION_GATE_REASON_CODES",
    # Individual reason codes
    "CONTRADICTORY_INPUTS",
    "CONTRADICTORY_SAFETY_FLAGS",
    "INVALID_STRATEGY_CONTRACT",
    "INVALID_TIMESTAMP",
    "MISSING_HUMAN_APPROVAL_FLAG",
    "MISSING_REQUIRED_FINGERPRINT",
    "MISSING_RISK_CONTEXT",
    "MISSING_STRATEGY_CONTRACT",
    "MISSING_UNIVERSE_REPORT",
    "OPTIONAL_STRATEGY_CONTRACT_MISSING",
    "REJECTED_RISK_CONTEXT",
    "REJECTED_UNIVERSE_REPORT",
    "RISK_GATE_CLOSED",
    "STALE_RISK_CONTEXT",
    "STALE_UNIVERSE_REPORT",
    "UNSAFE_RESEARCH_FLAG",
    "UNSAFE_STRATEGY_CONTRACT",
    "UPSTREAM_REVIEW_REQUIRED",
    # Models
    "ResearchDecisionGateConfig",
    "DecisionSourceSummary",
    "ResearchDecisionGateReport",
    "ResearchDecisionGateError",
    # Validator
    "validate_evaluated_at",
    "validate_risk_context",
    "validate_universe_report",
    "validate_strategy_contract_input",
    # Policy
    "classify_reason_codes",
    "evaluate_strategy_contract_policy",
    "resolve_decision",
    "detect_contradictions",
    "detect_review_conditions",
    "build_canonical_safety_flags",
    # Engine
    "build_research_decision_gate_report",
    # Writer
    "research_decision_gate_report_to_dict",
    "research_decision_gate_report_to_json_text",
    "research_decision_gate_report_to_markdown_text",
    "write_research_decision_gate_report",
    "atomic_write_json_research_decision_gate_report",
    "atomic_write_markdown_research_decision_gate_report",
]
