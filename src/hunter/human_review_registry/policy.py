"""Review policy for the Human Review Decision Registry (MVP-60)."""

from __future__ import annotations

from hunter.human_review_registry.models import (
    ACCEPTED_REASON_CODES,
    APPROVE_FOR_RESEARCH,
    BLOCKING_REASON_CODES,
    MISSING_REQUIRED_REVIEW_NOTE,
    NEEDS_REVIEW,
    NO_GO,
    NO_GO_APPROVAL_FORBIDDEN,
    REJECT,
    REQUEST_CHANGES,
    REVIEW_APPROVED_FOR_RESEARCH,
    REVIEW_CHANGES_REQUESTED,
    REVIEW_REJECTED,
    HumanReviewInput,
    HumanReviewRegistryConfig,
)


def _note_is_adequate(review_input: HumanReviewInput, config: HumanReviewRegistryConfig) -> bool:
    note = review_input.review_note.strip()
    return len(note) >= config.min_review_note_length


def evaluate_review_policy(
    source_decision: str,
    review_input: HumanReviewInput,
    config: HumanReviewRegistryConfig,
) -> tuple[bool, tuple[str, ...], tuple[str, ...]]:
    """Evaluate the human review decision against the upstream source decision.

    Returns ``(accepted, blocking_reasons, accepted_reasons)``.

    Rules:
      - ``NO_GO`` source + ``APPROVE_FOR_RESEARCH`` → blocked.
      - ``NEEDS_REVIEW`` source + ``APPROVE_FOR_RESEARCH`` or ``REQUEST_CHANGES``
        requires an adequate note.
      - ``REJECT`` always accepted.
      - ``APPROVE_FOR_RESEARCH`` on ``GO`` always accepted.
    """
    if source_decision == NO_GO and review_input.reviewer_decision == APPROVE_FOR_RESEARCH:
        return False, (NO_GO_APPROVAL_FORBIDDEN,), ()

    if review_input.reviewer_decision == REJECT:
        return True, (), (REVIEW_REJECTED,)

    if review_input.reviewer_decision == APPROVE_FOR_RESEARCH:
        if source_decision == NEEDS_REVIEW and not _note_is_adequate(review_input, config):
            return False, (MISSING_REQUIRED_REVIEW_NOTE,), ()
        return True, (), (REVIEW_APPROVED_FOR_RESEARCH,)

    if review_input.reviewer_decision == REQUEST_CHANGES:
        if source_decision == NEEDS_REVIEW and not _note_is_adequate(review_input, config):
            return False, (MISSING_REQUIRED_REVIEW_NOTE,), ()
        return True, (), (REVIEW_CHANGES_REQUESTED,)

    # Unknown reviewer decision should already be caught by the validator, but
    # we keep this branch fail-closed.
    return False, ("INVALID_REVIEW_DECISION",), ()


def accepted_reason_code(reviewer_decision: str) -> str:
    """Return the accepted reason code label for a reviewer decision."""
    return {
        APPROVE_FOR_RESEARCH: REVIEW_APPROVED_FOR_RESEARCH,
        REJECT: REVIEW_REJECTED,
        REQUEST_CHANGES: REVIEW_CHANGES_REQUESTED,
    }.get(reviewer_decision, REVIEW_REJECTED)


__all__ = [
    "evaluate_review_policy",
    "accepted_reason_code",
]
