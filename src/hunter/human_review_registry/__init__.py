"""Public API for the Human Review Decision Registry (MVP-60).

The registry consumes a ``ResearchDecisionGateReport`` (MVP-59) and a human
review input, and produces an immutable, append-only ``HumanReviewRecord``.
All records are research-only; ``execution_approval_granted`` is always False.
"""

from __future__ import annotations

from hunter.human_review_registry.models import (
    ACCEPTED_REASON_CODES,
    APPROVE_FOR_RESEARCH,
    BLOCKING_REASON_CODES,
    BROKEN_REVIEW_CHAIN,
    CONTRADICTORY_REVIEW,
    DEFAULT_JSON_FILENAME,
    DEFAULT_MARKDOWN_FILENAME,
    DEFAULT_MIN_REVIEW_NOTE_LENGTH,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_REPORT_OUTPUT_DIR,
    DUPLICATE_REVIEW,
    GO,
    HUMAN_REVIEW_REGISTRY_REASON_CODES,
    HUMAN_REVIEW_REGISTRY_VERSION,
    HumanReviewInput,
    HumanReviewRecord,
    HumanReviewRegistryConfig,
    HumanReviewRegistryError,
    INVALID_REVIEW_DECISION,
    INVALID_REVIEWER_IDENTITY,
    INVALID_TIMESTAMP,
    MISSING_DECISION_REPORT,
    MISSING_REQUIRED_REVIEW_NOTE,
    MISSING_REVIEW_INPUT,
    NEEDS_REVIEW,
    NO_GO,
    NO_GO_APPROVAL_FORBIDDEN,
    PREVIOUS_RECORD_MISMATCH,
    REJECT,
    REQUEST_CHANGES,
    REVIEW_APPROVED_FOR_RESEARCH,
    REVIEW_CHANGES_REQUESTED,
    REVIEW_REJECTED,
    REVIEW_NOTE_TOO_SHORT,
    REVIEWER_DECISIONS,
    SOURCE_DECISIONS,
    SOURCE_FINGERPRINT_MISSING,
)
from hunter.human_review_registry.validator import (
    validate_created_at,
    validate_decision_report,
    validate_reason_codes,
    validate_review_input,
)

__all__ = [
    # Version
    "HUMAN_REVIEW_REGISTRY_VERSION",
    # Decisions
    "APPROVE_FOR_RESEARCH",
    "REJECT",
    "REQUEST_CHANGES",
    "REVIEWER_DECISIONS",
    "GO",
    "NO_GO",
    "NEEDS_REVIEW",
    "SOURCE_DECISIONS",
    # Reason code sets
    "BLOCKING_REASON_CODES",
    "ACCEPTED_REASON_CODES",
    "HUMAN_REVIEW_REGISTRY_REASON_CODES",
    # Individual reason codes
    "MISSING_DECISION_REPORT",
    "MISSING_REVIEW_INPUT",
    "INVALID_REVIEWER_IDENTITY",
    "INVALID_REVIEW_DECISION",
    "REVIEW_NOTE_TOO_SHORT",
    "MISSING_REQUIRED_REVIEW_NOTE",
    "SOURCE_FINGERPRINT_MISSING",
    "NO_GO_APPROVAL_FORBIDDEN",
    "BROKEN_REVIEW_CHAIN",
    "PREVIOUS_RECORD_MISMATCH",
    "DUPLICATE_REVIEW",
    "INVALID_TIMESTAMP",
    "CONTRADICTORY_REVIEW",
    "REVIEW_APPROVED_FOR_RESEARCH",
    "REVIEW_REJECTED",
    "REVIEW_CHANGES_REQUESTED",
    # Defaults
    "DEFAULT_MIN_REVIEW_NOTE_LENGTH",
    "DEFAULT_OUTPUT_DIR",
    "DEFAULT_REPORT_OUTPUT_DIR",
    "DEFAULT_JSON_FILENAME",
    "DEFAULT_MARKDOWN_FILENAME",
    # Models
    "HumanReviewRegistryConfig",
    "HumanReviewInput",
    "HumanReviewRecord",
    "HumanReviewRegistryError",
    # Validator
    "validate_decision_report",
    "validate_review_input",
    "validate_created_at",
    "validate_reason_codes",
]
