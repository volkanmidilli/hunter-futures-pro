"""Tests for the human review registry validator."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from hunter.human_review_registry import (
    APPROVE_FOR_RESEARCH,
    INVALID_REVIEW_DECISION,
    INVALID_REVIEWER_IDENTITY,
    INVALID_TIMESTAMP,
    MISSING_DECISION_REPORT,
    MISSING_REQUIRED_REVIEW_NOTE,
    MISSING_REVIEW_INPUT,
    REVIEW_NOTE_TOO_SHORT,
    SOURCE_FINGERPRINT_MISSING,
    HumanReviewInput,
    HumanReviewRegistryConfig,
    validate_created_at,
    validate_decision_report,
    validate_review_input,
)


def test_validate_missing_report() -> None:
    reasons = validate_decision_report(None)
    assert reasons == (MISSING_DECISION_REPORT,)


def test_validate_report_without_fingerprint() -> None:
    report = SimpleNamespace(decision_fingerprint="")
    reasons = validate_decision_report(report)  # type: ignore[arg-type]
    assert reasons == (SOURCE_FINGERPRINT_MISSING,)


def test_validate_report_with_fingerprint() -> None:
    report = SimpleNamespace(decision_fingerprint="abc123")
    reasons = validate_decision_report(report)  # type: ignore[arg-type]
    assert reasons == ()


def test_validate_missing_review_input() -> None:
    config = HumanReviewRegistryConfig.default()
    reasons = validate_review_input(None, config)
    assert MISSING_REVIEW_INPUT in reasons


def test_validate_invalid_identity() -> None:
    config = HumanReviewRegistryConfig.default()
    inp = SimpleNamespace(
        reviewer_identity="  ",
        reviewer_decision=APPROVE_FOR_RESEARCH,
        review_note="Valid note here.",
    )
    reasons = validate_review_input(inp, config)
    assert INVALID_REVIEWER_IDENTITY in reasons


def test_validate_invalid_decision() -> None:
    config = HumanReviewRegistryConfig.default()
    inp = SimpleNamespace(
        reviewer_identity="alice",
        reviewer_decision="EXECUTE",
        review_note="Valid note here.",
    )
    reasons = validate_review_input(inp, config)
    assert INVALID_REVIEW_DECISION in reasons


def test_validate_missing_note() -> None:
    config = HumanReviewRegistryConfig.default()
    inp = SimpleNamespace(
        reviewer_identity="alice",
        reviewer_decision=APPROVE_FOR_RESEARCH,
        review_note="",
    )
    reasons = validate_review_input(inp, config)
    assert MISSING_REQUIRED_REVIEW_NOTE in reasons


def test_validate_short_note() -> None:
    config = HumanReviewRegistryConfig.default()
    inp = SimpleNamespace(
        reviewer_identity="alice",
        reviewer_decision=APPROVE_FOR_RESEARCH,
        review_note="short",
    )
    reasons = validate_review_input(inp, config)
    assert REVIEW_NOTE_TOO_SHORT in reasons


def test_validate_valid_input() -> None:
    config = HumanReviewRegistryConfig.default()
    inp = HumanReviewInput(
        reviewer_identity="alice",
        reviewer_decision=APPROVE_FOR_RESEARCH,
        review_note="This is a valid, adequate review note.",
    )
    reasons = validate_review_input(inp, config)
    assert reasons == ()


def test_validate_naive_created_at() -> None:
    config = HumanReviewRegistryConfig.default()
    reasons = validate_created_at(datetime(2026, 7, 14, 12, 0, 0), config)
    assert reasons == (INVALID_TIMESTAMP,)


def test_validate_future_created_at() -> None:
    config = HumanReviewRegistryConfig.default()
    future = datetime.now(timezone.utc) + timedelta(days=1)
    reasons = validate_created_at(future, config)
    assert reasons == (INVALID_TIMESTAMP,)


def test_validate_valid_created_at() -> None:
    config = HumanReviewRegistryConfig.default()
    now = datetime.now(timezone.utc)
    reasons = validate_created_at(now, config)
    assert reasons == ()
