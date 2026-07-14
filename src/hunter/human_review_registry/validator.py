"""Input validation for the Human Review Decision Registry (MVP-60)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from hunter.human_review_registry.models import (
    BLOCKING_REASON_CODES,
    HUMAN_REVIEW_REGISTRY_VERSION,
    INVALID_REVIEWER_IDENTITY,
    INVALID_REVIEW_DECISION,
    INVALID_TIMESTAMP,
    MISSING_DECISION_REPORT,
    MISSING_REQUIRED_REVIEW_NOTE,
    MISSING_REVIEW_INPUT,
    REVIEW_NOTE_TOO_SHORT,
    SOURCE_FINGERPRINT_MISSING,
    HumanReviewRegistryConfig,
    HumanReviewRegistryError,
)

if TYPE_CHECKING:
    from hunter.research_decision_gate.models import ResearchDecisionGateReport


def _is_nonempty_string(value: object) -> bool:
    return isinstance(value, str) and value.strip() != ""


def validate_decision_report(
    decision_report: ResearchDecisionGateReport | None,
) -> tuple[str, ...]:
    """Validate the upstream decision report reference.

    Returns blocking reason codes if the report is missing or lacks the
    decision fingerprint required for provenance.
    """
    reasons: list[str] = []
    if decision_report is None:
        reasons.append(MISSING_DECISION_REPORT)
        return tuple(reasons)
    fingerprint = getattr(decision_report, "decision_fingerprint", None)
    if not _is_nonempty_string(fingerprint):
        reasons.append(SOURCE_FINGERPRINT_MISSING)
    return tuple(reasons)


def validate_review_input(
    review_input: object,
    config: HumanReviewRegistryConfig,
) -> tuple[str, ...]:
    """Validate the human review input.

    Checks reviewer identity, reviewer decision, and review note length.
    Returns blocking reason codes.
    """
    from hunter.human_review_registry.models import REVIEWER_DECISIONS

    reasons: list[str] = []
    if review_input is None:
        reasons.append(MISSING_REVIEW_INPUT)
        return tuple(reasons)
    identity = getattr(review_input, "reviewer_identity", None)
    if not _is_nonempty_string(identity):
        reasons.append(INVALID_REVIEWER_IDENTITY)
    decision = getattr(review_input, "reviewer_decision", None)
    if decision not in REVIEWER_DECISIONS:
        reasons.append(INVALID_REVIEW_DECISION)
    note = getattr(review_input, "review_note", None)
    if not isinstance(note, str) or note.strip() == "":
        reasons.append(MISSING_REQUIRED_REVIEW_NOTE)
    elif len(note.strip()) < config.min_review_note_length:
        reasons.append(REVIEW_NOTE_TOO_SHORT)
    return tuple(reasons)


def validate_created_at(
    created_at: datetime,
    config: HumanReviewRegistryConfig | None = None,
) -> tuple[str, ...]:
    """Validate the record timestamp.

    The timestamp must be timezone-aware and not in the future beyond a small
    skew.  ``config`` is accepted for consistency but the skew is fixed by the
    registry version contract.
    """
    del config  # reserved for future configurability; not used today
    reasons: list[str] = []
    if not isinstance(created_at, datetime):
        reasons.append(INVALID_TIMESTAMP)
        return tuple(reasons)
    if created_at.tzinfo is None:
        reasons.append(INVALID_TIMESTAMP)
        return tuple(reasons)
    if created_at > datetime.now(timezone.utc):
        reasons.append(INVALID_TIMESTAMP)
    return tuple(reasons)


def validate_reason_codes(reason_codes: tuple[str, ...]) -> tuple[str, ...]:
    """Validate that every reason code is known.

    Unknown codes are replaced with a safe blocker.  This keeps the registry
    fail-closed if a caller fabricates reason codes.
    """
    validated: list[str] = []
    for code in reason_codes:
        if code in BLOCKING_REASON_CODES or code in _ACCEPTED_REASON_CODES:
            validated.append(code)
        else:
            validated.append("UNKNOWN_REASON_CODE")
    return tuple(validated)


_ACCEPTED_REASON_CODES: frozenset[str] = frozenset(
    {
        "REVIEW_APPROVED_FOR_RESEARCH",
        "REVIEW_REJECTED",
        "REVIEW_CHANGES_REQUESTED",
    }
)


__all__ = [
    "validate_decision_report",
    "validate_review_input",
    "validate_created_at",
    "validate_reason_codes",
]
