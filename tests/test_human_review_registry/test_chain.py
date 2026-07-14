"""Tests for the human review registry chain validator."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from hunter.human_review_registry import (
    APPROVE_FOR_RESEARCH,
    BROKEN_REVIEW_CHAIN,
    DUPLICATE_REVIEW,
    GO,
    HUMAN_REVIEW_REGISTRY_VERSION,
    HumanReviewInput,
    HumanReviewRecord,
    NO_GO,
    PREVIOUS_RECORD_MISMATCH,
    REJECT,
    compute_record_fingerprint,
    detect_duplicate_review,
    duplicate_review_key,
    verify_chain,
    verify_record_fingerprint,
)


def _record(
    *,
    source_fp: str = "src-fp",
    previous_fp: str | None = None,
    reviewer_decision: str = APPROVE_FOR_RESEARCH,
    accepted: bool = True,
    created_at: datetime | None = None,
) -> HumanReviewRecord:
    created = created_at or datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)
    fp = compute_record_fingerprint(
        source_decision_fingerprint=source_fp,
        source_decision=GO,
        reviewer_identity="alice",
        reviewer_decision=reviewer_decision,
        review_note="Approved for research only.",
        created_at=created,
        previous_record_fingerprint=previous_fp,
        accepted=accepted,
        human_approval_recorded=accepted,
        execution_approval_granted=False,
    )
    return HumanReviewRecord(
        version=HUMAN_REVIEW_REGISTRY_VERSION,
        source_decision_fingerprint=source_fp,
        source_decision=GO,
        reviewer_identity="alice",
        reviewer_decision=reviewer_decision,
        review_note="Approved for research only.",
        created_at=created,
        previous_record_fingerprint=previous_fp,
        record_fingerprint=fp,
        accepted=accepted,
        human_approval_recorded=accepted,
        execution_approval_granted=False,
        reason_codes=(),
    )


def test_compute_fingerprint_is_deterministic() -> None:
    created = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)
    fp1 = compute_record_fingerprint(
        "src", GO, "alice", APPROVE_FOR_RESEARCH, "note", created, None, True, True, False
    )
    fp2 = compute_record_fingerprint(
        "src", GO, "alice", APPROVE_FOR_RESEARCH, "note", created, None, True, True, False
    )
    assert fp1 == fp2
    assert len(fp1) == 64


def test_verify_valid_single_record() -> None:
    record = _record()
    assert verify_record_fingerprint(record) == ()
    assert verify_chain((record,)) == ()


def test_verify_first_record_must_have_none_previous() -> None:
    record = _record(previous_fp="something")
    reasons = verify_chain((record,))
    assert BROKEN_REVIEW_CHAIN in reasons


def test_verify_chain_links_records() -> None:
    first = _record()
    second = _record(previous_fp=first.record_fingerprint)
    assert verify_chain((first, second)) == ()


def test_verify_chain_detects_broken_link() -> None:
    first = _record()
    second = _record(previous_fp="wrong")
    reasons = verify_chain((first, second))
    assert PREVIOUS_RECORD_MISMATCH in reasons


def test_verify_chain_detects_duplicate_fingerprints() -> None:
    first = _record()
    second = _record(previous_fp=first.record_fingerprint)
    second = HumanReviewRecord(
        version=second.version,
        source_decision_fingerprint=second.source_decision_fingerprint,
        source_decision=second.source_decision,
        reviewer_identity=second.reviewer_identity,
        reviewer_decision=second.reviewer_decision,
        review_note=second.review_note,
        created_at=second.created_at,
        previous_record_fingerprint=second.previous_record_fingerprint,
        record_fingerprint=first.record_fingerprint,
        accepted=second.accepted,
        human_approval_recorded=second.human_approval_recorded,
        execution_approval_granted=second.execution_approval_granted,
        reason_codes=second.reason_codes,
    )
    reasons = verify_chain((first, second))
    assert DUPLICATE_REVIEW in reasons


def test_detect_duplicate_review() -> None:
    record = _record()
    inp = HumanReviewInput(
        reviewer_identity="alice",
        reviewer_decision=APPROVE_FOR_RESEARCH,
        review_note="Approved for research only.",
    )
    assert detect_duplicate_review("src-fp", inp, (record,)) is True
    assert detect_duplicate_review("other-src", inp, (record,)) is False


def test_duplicate_key_changes_with_note() -> None:
    inp1 = HumanReviewInput(
        reviewer_identity="alice",
        reviewer_decision=APPROVE_FOR_RESEARCH,
        review_note="note one",
    )
    inp2 = HumanReviewInput(
        reviewer_identity="alice",
        reviewer_decision=APPROVE_FOR_RESEARCH,
        review_note="note two",
    )
    assert duplicate_review_key("src", inp1) != duplicate_review_key("src", inp2)


def test_tampered_record_fails_verification() -> None:
    record = _record()
    tampered = HumanReviewRecord(
        version=record.version,
        source_decision_fingerprint=record.source_decision_fingerprint,
        source_decision=NO_GO,
        reviewer_identity=record.reviewer_identity,
        reviewer_decision=REJECT,
        review_note=record.review_note,
        created_at=record.created_at,
        previous_record_fingerprint=record.previous_record_fingerprint,
        record_fingerprint=record.record_fingerprint,
        accepted=False,
        human_approval_recorded=False,
        execution_approval_granted=False,
        reason_codes=(),
    )
    assert verify_record_fingerprint(tampered) == (BROKEN_REVIEW_CHAIN,)
