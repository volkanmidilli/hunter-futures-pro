"""Public API for the Governance Handoff Package Builder (MVP-62).

MVP-62 consumes a ``GovernanceDecisionSummary`` (MVP-61), a
``ResearchDecisionGateReport`` (MVP-59), and the latest accepted
``HumanReviewRecord`` (MVP-60) to produce one immutable, research-only
``ResearchGovernanceHandoffPackage`` with deterministic JSON/Markdown artifacts.

The package never authorizes execution, production deployment, or trading. It
does not integrate with Freqtrade runtime, exchanges, databases, schedulers, or
live trading systems.
"""

from __future__ import annotations

from hunter.governance_handoff.policy import (
    build_handoff_manifest,
    build_handoff_safety_flags,
    build_source_references,
    classify_handoff_reasons,
    resolve_handoff_allowed,
)
from hunter.governance_handoff.validator import (
    validate_all,
    validate_built_at,
    validate_gate_report,
    validate_governance_summary,
    validate_latest_review,
    validate_provenance_links,
    validate_safety_flags,
    validate_source_versions,
)
from hunter.governance_handoff.models import (
    BLOCKED,
    CANONICAL_SAFETY_FLAGS,
    CONTRADICTORY_HANDOFF_STATE,
    MISSING_REQUIRED_FINGERPRINT,
    DEFAULT_JSON_FILENAME,
    DEFAULT_MARKDOWN_FILENAME,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_REPORT_OUTPUT_DIR,
    DEFAULT_REQUIRE_LATEST_ACCEPTED_REVIEW,
    GATE_FINGERPRINT_MISMATCH,
    GOVERNANCE_FINGERPRINT_MISMATCH,
    GOVERNANCE_HANDOFF_VERSION,
    GOVERNANCE_REVIEW_REQUIRED,
    GOVERNANCE_STATUSES,
    GOVERNANCE_STATUSES as GOVERNANCE_HANDOFF_STATUSES,
    HANDOFF_BLOCKING_REASON_CODES,
    HANDOFF_PACKAGE_READY,
    HANDOFF_REASON_CODES,
    HANDOFF_REVIEW_REQUIRED_REASON_CODES,
    INCOMPLETE_PROVENANCE,
    INVALID_GATE_REPORT,
    INVALID_GOVERNANCE_SUMMARY,
    INVALID_REVIEW_RECORD,
    INVALID_TIMESTAMP,
    MISSING_GATE_REPORT,
    MISSING_GOVERNANCE_SUMMARY,
    MISSING_LATEST_ACCEPTED_REVIEW,
    MISSING_OPTIONAL_METADATA,
    READY_FOR_RESEARCH_HANDOFF,
    REVIEW_FINGERPRINT_MISMATCH,
    REVIEW_REQUIRED,
    SOURCE_VERSION_MISMATCH,
    UNSAFE_HANDOFF_FLAG,
    UNKNOWN_NON_BLOCKING_FIELD,
    GovernanceHandoffConfig,
    GovernanceHandoffError,
    HandoffSourceReference,
    ResearchGovernanceHandoffManifest,
    ResearchGovernanceHandoffPackage,
)

__all__ = [
    # Version
    "GOVERNANCE_HANDOFF_VERSION",
    # Statuses
    "READY_FOR_RESEARCH_HANDOFF",
    "REVIEW_REQUIRED",
    "BLOCKED",
    "GOVERNANCE_STATUSES",
    "GOVERNANCE_HANDOFF_STATUSES",
    # Reason code sets
    "HANDOFF_BLOCKING_REASON_CODES",
    "HANDOFF_REVIEW_REQUIRED_REASON_CODES",
    "HANDOFF_REASON_CODES",
    # Individual reason codes
    "MISSING_GOVERNANCE_SUMMARY",
    "MISSING_GATE_REPORT",
    "MISSING_LATEST_ACCEPTED_REVIEW",
    "INVALID_GOVERNANCE_SUMMARY",
    "INVALID_GATE_REPORT",
    "INVALID_REVIEW_RECORD",
    "GOVERNANCE_FINGERPRINT_MISMATCH",
    "GATE_FINGERPRINT_MISMATCH",
    "REVIEW_FINGERPRINT_MISMATCH",
    "SOURCE_VERSION_MISMATCH",
    "CONTRADICTORY_HANDOFF_STATE",
    "MISSING_REQUIRED_FINGERPRINT",
    "UNSAFE_HANDOFF_FLAG",
    "INVALID_TIMESTAMP",
    "GOVERNANCE_REVIEW_REQUIRED",
    "INCOMPLETE_PROVENANCE",
    "UNKNOWN_NON_BLOCKING_FIELD",
    "MISSING_OPTIONAL_METADATA",
    "HANDOFF_PACKAGE_READY",
    # Safety flags
    "CANONICAL_SAFETY_FLAGS",
    # Policy
    "build_handoff_safety_flags",
    "build_source_references",
    "classify_handoff_reasons",
    "resolve_handoff_allowed",
    "build_handoff_manifest",
    # Validator
    "validate_all",
    "validate_built_at",
    "validate_governance_summary",
    "validate_gate_report",
    "validate_latest_review",
    "validate_source_versions",
    "validate_provenance_links",
    "validate_safety_flags",
    # Defaults
    "DEFAULT_REQUIRE_LATEST_ACCEPTED_REVIEW",
    "DEFAULT_OUTPUT_DIR",
    "DEFAULT_REPORT_OUTPUT_DIR",
    "DEFAULT_JSON_FILENAME",
    "DEFAULT_MARKDOWN_FILENAME",
    # Errors
    "GovernanceHandoffError",
    # Models
    "GovernanceHandoffConfig",
    "HandoffSourceReference",
    "ResearchGovernanceHandoffManifest",
    "ResearchGovernanceHandoffPackage",
]
