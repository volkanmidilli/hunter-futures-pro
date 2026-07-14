"""Public API for the Governance Decision Summary Aggregator (MVP-61).

MVP-61 combines the gate result from ``ResearchDecisionGateReport`` (MVP-59),
the review chain from ``HumanReviewRecord`` (MVP-60), and chain verification
state into one deterministic governance summary.

All outputs are explicitly marked as research-only and require human review
before any downstream use. The aggregator is fail-closed and never integrates
with Freqtrade runtime, exchanges, databases, schedulers, or live trading
systems.
"""

from __future__ import annotations

from hunter.governance_summary.models import (
    BLOCKED,
    BROKEN_REVIEW_CHAIN,
    CONTRADICTORY_GOVERNANCE_STATE,
    DEFAULT_JSON_FILENAME,
    DEFAULT_MARKDOWN_FILENAME,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_REPORT_OUTPUT_DIR,
    DEFAULT_REQUIRE_REVIEW_CHAIN,
    DUPLICATE_REVIEW_RECORD,
    GATE_DECISION_NO_GO,
    GATE_REVIEW_REQUIRED,
    GOVERNANCE_BLOCKING_REASON_CODES,
    GOVERNANCE_REASON_CODES,
    GOVERNANCE_REVIEW_REQUIRED_REASON_CODES,
    GOVERNANCE_STATUSES,
    GOVERNANCE_SUMMARY_VERSION,
    GovernanceDecisionSummary,
    GovernanceReviewSummary,
    GovernanceSummaryConfig,
    GovernanceSummaryError,
    INCOMPLETE_PROVENANCE,
    INVALID_GATE_REPORT,
    INVALID_TIMESTAMP,
    LATEST_REVIEW_REJECTED,
    LATEST_REVIEW_REQUESTS_CHANGES,
    MISSING_GATE_REPORT,
    MISSING_REQUIRED_FINGERPRINT,
    MISSING_REVIEW_CHAIN,
    NO_ACCEPTED_REVIEW,
    OPEN_CHANGE_REQUEST,
    READY_FOR_RESEARCH_HANDOFF,
    REVIEW_REQUIRED,
    TAMPERED_REVIEW_RECORD,
    UNKNOWN_NON_BLOCKING_FIELD,
    UNSAFE_GOVERNANCE_FLAG,
)
from hunter.governance_summary.engine import (
    build_governance_decision_summary,
    compute_governance_fingerprint,
)
from hunter.governance_summary.policy import (
    build_governance_safety_flags,
    classify_governance_reasons,
    detect_open_change_request,
    resolve_governance_status,
    select_latest_accepted_review,
)
from hunter.governance_summary.validator import (
    build_review_chain_facts,
    validate_evaluated_at,
    validate_gate_report,
    validate_review_records,
)
from hunter.governance_summary.writer import (
    atomic_write_json_governance_decision_summary,
    atomic_write_markdown_governance_decision_summary,
    governance_decision_summary_to_dict,
    governance_decision_summary_to_json_text,
    governance_decision_summary_to_markdown_text,
    write_governance_decision_summary,
)

__all__ = [
    # Version
    "GOVERNANCE_SUMMARY_VERSION",
    # Statuses
    "READY_FOR_RESEARCH_HANDOFF",
    "REVIEW_REQUIRED",
    "BLOCKED",
    "GOVERNANCE_STATUSES",
    # Reason code sets
    "GOVERNANCE_BLOCKING_REASON_CODES",
    "GOVERNANCE_REVIEW_REQUIRED_REASON_CODES",
    "GOVERNANCE_REASON_CODES",
    # Individual reason codes
    "MISSING_GATE_REPORT",
    "INVALID_GATE_REPORT",
    "GATE_DECISION_NO_GO",
    "MISSING_REVIEW_CHAIN",
    "BROKEN_REVIEW_CHAIN",
    "TAMPERED_REVIEW_RECORD",
    "DUPLICATE_REVIEW_RECORD",
    "CONTRADICTORY_GOVERNANCE_STATE",
    "MISSING_REQUIRED_FINGERPRINT",
    "UNSAFE_GOVERNANCE_FLAG",
    "INVALID_TIMESTAMP",
    "NO_ACCEPTED_REVIEW",
    "GATE_REVIEW_REQUIRED",
    "OPEN_CHANGE_REQUEST",
    "LATEST_REVIEW_REJECTED",
    "LATEST_REVIEW_REQUESTS_CHANGES",
    "INCOMPLETE_PROVENANCE",
    "UNKNOWN_NON_BLOCKING_FIELD",
    # Defaults
    "DEFAULT_REQUIRE_REVIEW_CHAIN",
    "DEFAULT_OUTPUT_DIR",
    "DEFAULT_REPORT_OUTPUT_DIR",
    "DEFAULT_JSON_FILENAME",
    "DEFAULT_MARKDOWN_FILENAME",
    # Models
    "GovernanceSummaryConfig",
    "GovernanceReviewSummary",
    "GovernanceDecisionSummary",
    "GovernanceSummaryError",
    # Validator
    "validate_gate_report",
    "validate_review_records",
    "validate_evaluated_at",
    "build_review_chain_facts",
    # Policy
    "build_governance_safety_flags",
    "select_latest_accepted_review",
    "detect_open_change_request",
    "classify_governance_reasons",
    "resolve_governance_status",
    # Engine
    "build_governance_decision_summary",
    "compute_governance_fingerprint",
    # Writer
    "governance_decision_summary_to_dict",
    "governance_decision_summary_to_json_text",
    "governance_decision_summary_to_markdown_text",
    "write_governance_decision_summary",
    "atomic_write_json_governance_decision_summary",
    "atomic_write_markdown_governance_decision_summary",
]
