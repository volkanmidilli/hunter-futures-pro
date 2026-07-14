"""Chain validation and fingerprinting for the Human Review Decision Registry (MVP-60)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import TYPE_CHECKING

from hunter.human_review_registry.models import (
    BROKEN_REVIEW_CHAIN,
    CONTRADICTORY_REVIEW,
    DUPLICATE_REVIEW,
    GO,
    HUMAN_REVIEW_REGISTRY_VERSION,
    NO_GO,
    PREVIOUS_RECORD_MISMATCH,
    SOURCE_FINGERPRINT_MISSING,
    HumanReviewRegistryError,
)

if TYPE_CHECKING:
    from hunter.human_review_registry.models import HumanReviewInput, HumanReviewRecord


def _canonical_json(payload: object) -> str:
    """Return deterministic compact JSON for hashing."""
    return json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
        default=str,
    )


def compute_record_fingerprint(
    source_decision_fingerprint: str,
    source_decision: str,
    reviewer_identity: str,
    reviewer_decision: str,
    review_note: str,
    created_at: datetime,
    previous_record_fingerprint: str | None,
    accepted: bool,
    human_approval_recorded: bool,
    execution_approval_granted: bool,
) -> str:
    """Compute a deterministic SHA-256 fingerprint for a review record."""
    payload = {
        "version": HUMAN_REVIEW_REGISTRY_VERSION,
        "source_decision_fingerprint": source_decision_fingerprint,
        "source_decision": source_decision,
        "reviewer_identity": reviewer_identity,
        "reviewer_decision": reviewer_decision,
        "review_note": review_note.strip(),
        "created_at": created_at.isoformat(),
        "previous_record_fingerprint": previous_record_fingerprint,
        "accepted": accepted,
        "human_approval_recorded": human_approval_recorded,
        "execution_approval_granted": execution_approval_granted,
    }
    canonical = _canonical_json(payload)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def duplicate_review_key(
    source_decision_fingerprint: str,
    review_input: HumanReviewInput,
) -> str:
    """Return a key used to detect duplicate reviews of the same source decision."""
    payload = {
        "source_decision_fingerprint": source_decision_fingerprint,
        "reviewer_identity": review_input.reviewer_identity.strip(),
        "reviewer_decision": review_input.reviewer_decision,
        "review_note": review_input.review_note.strip(),
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def verify_record_fingerprint(record: HumanReviewRecord) -> tuple[str, ...]:
    """Recompute and verify a record's fingerprint.

    Returns an empty tuple if the fingerprint is valid; otherwise returns
    blocking reason codes.
    """
    expected = compute_record_fingerprint(
        source_decision_fingerprint=record.source_decision_fingerprint,
        source_decision=record.source_decision,
        reviewer_identity=record.reviewer_identity,
        reviewer_decision=record.reviewer_decision,
        review_note=record.review_note,
        created_at=record.created_at,
        previous_record_fingerprint=record.previous_record_fingerprint,
        accepted=record.accepted,
        human_approval_recorded=record.human_approval_recorded,
        execution_approval_granted=record.execution_approval_granted,
    )
    if expected == record.record_fingerprint:
        return ()
    return (BROKEN_REVIEW_CHAIN,)


def verify_chain(
    existing_records: tuple[HumanReviewRecord, ...],
) -> tuple[str, ...]:
    """Verify an ordered chain of existing records.

    Checks:
      - first record has ``previous_record_fingerprint = None``
      - each subsequent record points to the previous record fingerprint
      - each record fingerprint recomputes identically
      - no duplicate record fingerprints
    """
    reasons: list[str] = []
    seen: set[str] = set()
    prev: HumanReviewRecord | None = None
    for idx, record in enumerate(existing_records):
        if record.record_fingerprint in seen:
            reasons.append(DUPLICATE_REVIEW)
        else:
            seen.add(record.record_fingerprint)

        fp_reasons = verify_record_fingerprint(record)
        if fp_reasons:
            reasons.extend(fp_reasons)

        if idx == 0:
            if record.previous_record_fingerprint is not None:
                reasons.append(BROKEN_REVIEW_CHAIN)
        else:
            expected_prev = prev.record_fingerprint if prev else None
            if record.previous_record_fingerprint != expected_prev:
                reasons.append(PREVIOUS_RECORD_MISMATCH)

        prev = record

    return tuple(reasons)


def detect_duplicate_review(
    source_decision_fingerprint: str,
    review_input: HumanReviewInput,
    existing_records: tuple[HumanReviewRecord, ...],
) -> bool:
    """Return True if an identical review already exists in the chain."""
    key = duplicate_review_key(source_decision_fingerprint, review_input)
    for record in existing_records:
        record_key = duplicate_review_key(
            record.source_decision_fingerprint,
            _input_from_record(record),
        )
        if record_key == key:
            return True
    return False


def _input_from_record(record: HumanReviewRecord) -> HumanReviewInput:
    """Reconstruct a review input from a record for duplicate detection."""
    from hunter.human_review_registry.models import HumanReviewInput

    return HumanReviewInput(
        reviewer_identity=record.reviewer_identity,
        reviewer_decision=record.reviewer_decision,
        review_note=record.review_note,
    )


__all__ = [
    "compute_record_fingerprint",
    "duplicate_review_key",
    "verify_record_fingerprint",
    "verify_chain",
    "detect_duplicate_review",
]
