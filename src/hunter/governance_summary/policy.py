"""Governance policy for the Governance Decision Summary Aggregator (MVP-61).

Policy functions are pure and deterministic. They classify reason codes,
select the latest accepted review, detect open change requests, and resolve
the final governance status.
"""

from __future__ import annotations

from datetime import datetime
from types import MappingProxyType
from typing import TYPE_CHECKING, Mapping, Sequence

from hunter.governance_summary.models import (
    BLOCKED,
    GATE_DECISION_NO_GO,
    GATE_REVIEW_REQUIRED,
    LATEST_REVIEW_REJECTED,
    LATEST_REVIEW_REQUESTS_CHANGES,
    NO_ACCEPTED_REVIEW,
    READY_FOR_RESEARCH_HANDOFF,
    REVIEW_REQUIRED,
)
from hunter.human_review_registry.models import (
    APPROVE_FOR_RESEARCH,
    REJECT,
    REQUEST_CHANGES,
)

if TYPE_CHECKING:
    from hunter.human_review_registry.models import HumanReviewRecord


def build_governance_safety_flags() -> Mapping[str, bool]:
    """Return the canonical safety flags for every governance summary."""
    return MappingProxyType(
        {
            "research_only": True,
            "human_review_required": True,
            "execution_approval_granted": False,
        }
    )


def select_latest_accepted_review(
    review_records: Sequence[HumanReviewRecord],
) -> HumanReviewRecord | None:
    """Return the latest accepted review record using deterministic tie-break.

    Sort key is ``(created_at, record_fingerprint)``; the greatest value wins.
    """
    accepted = [r for r in review_records if getattr(r, "accepted", False)]
    if not accepted:
        return None
    accepted_sorted = sorted(
        accepted,
        key=lambda r: (
            getattr(r, "created_at", datetime.min),
            getattr(r, "record_fingerprint", ""),
        ),
    )
    return accepted_sorted[-1]


def detect_open_change_request(latest_accepted: HumanReviewRecord | None) -> bool:
    """Return True if the latest accepted review is an open change request."""
    if latest_accepted is None:
        return False
    return getattr(latest_accepted, "reviewer_decision", None) == REQUEST_CHANGES


def classify_governance_reasons(
    gate_reasons: tuple[str, ...],
    chain_reasons: tuple[str, ...],
    latest_accepted: HumanReviewRecord | None,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Classify validation reasons into blocking and review-required lists.

    Gate reasons are split by type; chain reasons are already namespace-mapped.
    Latest accepted review state contributes additional review-required reasons.
    """
    from hunter.governance_summary.models import (
        GOVERNANCE_BLOCKING_REASON_CODES,
        GOVERNANCE_REVIEW_REQUIRED_REASON_CODES,
    )

    blocking: list[str] = []
    review: list[str] = []

    for code in gate_reasons:
        if code == GATE_REVIEW_REQUIRED:
            review.append(code)
        elif code in GOVERNANCE_BLOCKING_REASON_CODES:
            blocking.append(code)
        elif code in GOVERNANCE_REVIEW_REQUIRED_REASON_CODES:
            review.append(code)

    for code in chain_reasons:
        if code in GOVERNANCE_BLOCKING_REASON_CODES:
            blocking.append(code)
        elif code in GOVERNANCE_REVIEW_REQUIRED_REASON_CODES:
            review.append(code)

    if latest_accepted is None:
        review.append(NO_ACCEPTED_REVIEW)
    else:
        decision = getattr(latest_accepted, "reviewer_decision", None)
        if decision == REJECT:
            review.append(LATEST_REVIEW_REJECTED)
        elif decision == REQUEST_CHANGES:
            review.append(LATEST_REVIEW_REQUESTS_CHANGES)

    return tuple(sorted(set(blocking))), tuple(sorted(set(review)))


def resolve_governance_status(
    blocking_reason_codes: tuple[str, ...],
    review_reason_codes: tuple[str, ...],
) -> str:
    """Resolve the final governance status using the decision priority.

    Priority:
      1. blocking reason exists → BLOCKED
      2. no blocking, review-required reason exists → REVIEW_REQUIRED
      3. no reasons → READY_FOR_RESEARCH_HANDOFF
    """
    if blocking_reason_codes:
        return BLOCKED
    if review_reason_codes:
        return REVIEW_REQUIRED
    return READY_FOR_RESEARCH_HANDOFF


__all__ = [
    "build_governance_safety_flags",
    "select_latest_accepted_review",
    "detect_open_change_request",
    "classify_governance_reasons",
    "resolve_governance_status",
]
