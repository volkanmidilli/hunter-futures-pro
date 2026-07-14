"""Tests for the human review registry policy."""

from __future__ import annotations

import pytest

from hunter.human_review_registry import (
    APPROVE_FOR_RESEARCH,
    GO,
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
    accepted_reason_code,
    evaluate_review_policy,
)


def _input(decision: str, note: str = "Adequate review note.") -> HumanReviewInput:
    return HumanReviewInput(
        reviewer_identity="alice",
        reviewer_decision=decision,
        review_note=note,
    )


def test_go_approve_accepted() -> None:
    accepted, blocking, accepted_reasons = evaluate_review_policy(
        GO, _input(APPROVE_FOR_RESEARCH), HumanReviewRegistryConfig.default()
    )
    assert accepted is True
    assert blocking == ()
    assert accepted_reasons == (REVIEW_APPROVED_FOR_RESEARCH,)


def test_go_reject_accepted() -> None:
    accepted, blocking, accepted_reasons = evaluate_review_policy(
        GO, _input(REJECT), HumanReviewRegistryConfig.default()
    )
    assert accepted is True
    assert blocking == ()
    assert accepted_reasons == (REVIEW_REJECTED,)


def test_go_request_changes_accepted() -> None:
    accepted, blocking, accepted_reasons = evaluate_review_policy(
        GO, _input(REQUEST_CHANGES), HumanReviewRegistryConfig.default()
    )
    assert accepted is True
    assert blocking == ()
    assert accepted_reasons == (REVIEW_CHANGES_REQUESTED,)


def test_no_go_approve_forbidden() -> None:
    accepted, blocking, accepted_reasons = evaluate_review_policy(
        NO_GO, _input(APPROVE_FOR_RESEARCH), HumanReviewRegistryConfig.default()
    )
    assert accepted is False
    assert blocking == (NO_GO_APPROVAL_FORBIDDEN,)
    assert accepted_reasons == ()


def test_no_go_reject_accepted() -> None:
    accepted, blocking, accepted_reasons = evaluate_review_policy(
        NO_GO, _input(REJECT), HumanReviewRegistryConfig.default()
    )
    assert accepted is True
    assert blocking == ()
    assert accepted_reasons == (REVIEW_REJECTED,)


def test_needs_review_approve_with_adequate_note() -> None:
    accepted, blocking, accepted_reasons = evaluate_review_policy(
        NEEDS_REVIEW,
        _input(APPROVE_FOR_RESEARCH, "This explains the review decision."),
        HumanReviewRegistryConfig.default(),
    )
    assert accepted is True
    assert accepted_reasons == (REVIEW_APPROVED_FOR_RESEARCH,)


def test_needs_review_approve_with_short_note_blocked() -> None:
    accepted, blocking, accepted_reasons = evaluate_review_policy(
        NEEDS_REVIEW,
        _input(APPROVE_FOR_RESEARCH, "short"),
        HumanReviewRegistryConfig.default(),
    )
    assert accepted is False
    assert "MISSING_REQUIRED_REVIEW_NOTE" in blocking
    assert accepted_reasons == ()


def test_needs_review_request_changes_with_short_note_blocked() -> None:
    accepted, blocking, accepted_reasons = evaluate_review_policy(
        NEEDS_REVIEW,
        _input(REQUEST_CHANGES, "short"),
        HumanReviewRegistryConfig.default(),
    )
    assert accepted is False
    assert "MISSING_REQUIRED_REVIEW_NOTE" in blocking


def test_needs_review_reject_accepted() -> None:
    accepted, blocking, accepted_reasons = evaluate_review_policy(
        NEEDS_REVIEW, _input(REJECT), HumanReviewRegistryConfig.default()
    )
    assert accepted is True
    assert accepted_reasons == (REVIEW_REJECTED,)


def test_accepted_reason_code() -> None:
    assert accepted_reason_code(APPROVE_FOR_RESEARCH) == REVIEW_APPROVED_FOR_RESEARCH
    assert accepted_reason_code(REJECT) == REVIEW_REJECTED
    assert accepted_reason_code(REQUEST_CHANGES) == REVIEW_CHANGES_REQUESTED
