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

from hunter.research_decision_gate.models import (
    ALLOW_WITH_REVIEW,
    BLOCKING_REASON_CODES,
    DECISION_GO,
    DECISION_NEEDS_REVIEW,
    DECISION_NO_GO,
    DECISION_REASON_CODES,
    IGNORE,
    REQUIRE,
    RESEARCH_DECISION_GATE_REASON_CODES,
    RESEARCH_DECISION_GATE_VERSION,
    REVIEW_REASON_CODES,
    DecisionSourceSummary,
    ResearchDecisionGateConfig,
    ResearchDecisionGateError,
    ResearchDecisionGateReport,
)

__all__ = [
    # Version
    "RESEARCH_DECISION_GATE_VERSION",
    # Policies
    "ALLOW_WITH_REVIEW",
    "REQUIRE",
    "IGNORE",
    # Reason codes
    "BLOCKING_REASON_CODES",
    "REVIEW_REASON_CODES",
    "DECISION_REASON_CODES",
    "RESEARCH_DECISION_GATE_REASON_CODES",
    "DECISION_GO",
    "DECISION_NO_GO",
    "DECISION_NEEDS_REVIEW",
    # Models
    "ResearchDecisionGateConfig",
    "DecisionSourceSummary",
    "ResearchDecisionGateReport",
    "ResearchDecisionGateError",
]
