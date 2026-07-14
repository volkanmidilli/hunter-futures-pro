"""Tests for the human review registry engine."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from hunter.human_review_registry import (
    APPROVE_FOR_RESEARCH,
    BROKEN_REVIEW_CHAIN,
    DUPLICATE_REVIEW,
    GO,
    HUMAN_REVIEW_REGISTRY_VERSION,
    NEEDS_REVIEW,
    NO_GO,
    NO_GO_APPROVAL_FORBIDDEN,
    REJECT,
    REQUEST_CHANGES,
    REVIEW_APPROVED_FOR_RESEARCH,
    REVIEW_REJECTED,
    REVIEW_NOTE_TOO_SHORT,
    HumanReviewInput,
    HumanReviewRecord,
    HumanReviewRegistryConfig,
    HumanReviewRegistryError,
    MISSING_DECISION_REPORT,
    MISSING_REVIEW_INPUT,
    build_human_review_record,
    compute_record_fingerprint,
)


def _report(*, decision: str = GO, fingerprint: str = "src-fp") -> SimpleNamespace:
    return SimpleNamespace(
        decision=decision,
        decision_fingerprint=fingerprint,
    )


def _input(
    decision: str = APPROVE_FOR_RESEARCH,
    note: str = "Approved for research only.",
) -> HumanReviewInput:
    return HumanReviewInput(
        reviewer_identity="alice",
        reviewer_decision=decision,
        review_note=note,
    )


def _dt() -> datetime:
    return datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)


def test_build_record_accepts_go_approve() -> None:
    config = HumanReviewRegistryConfig.default()
    record = build_human_review_record(
        _report(), _input(), config, created_at=_dt()
    )
    assert record.accepted is True
    assert record.execution_approval_granted is False
    assert record.human_approval_recorded is True
    assert record.reason_codes == (REVIEW_APPROVED_FOR_RESEARCH,)
    assert record.previous_record_fingerprint is None


def test_build_record_rejects_no_go_approve() -> None:
    config = HumanReviewRegistryConfig.default()
    record = build_human_review_record(
        _report(decision=NO_GO), _input(), config, created_at=_dt()
    )
    assert record.accepted is False
    assert NO_GO_APPROVAL_FORBIDDEN in record.reason_codes
    assert record.human_approval_recorded is False


def test_build_record_rejects_missing_report() -> None:
    config = HumanReviewRegistryConfig.default()
    record = build_human_review_record(
        None, _input(), config, created_at=_dt()
    )
    assert record.accepted is False
    assert MISSING_DECISION_REPORT in record.reason_codes


def test_build_record_rejects_missing_input() -> None:
    config = HumanReviewRegistryConfig.default()
    record = build_human_review_record(
        _report(), None, config, created_at=_dt()
    )
    assert record.accepted is False
    assert MISSING_REVIEW_INPUT in record.reason_codes


def test_build_record_rejects_naive_timestamp() -> None:
    config = HumanReviewRegistryConfig.default()
    with pytest.raises(ValueError, match="created_at"):
        build_human_review_record(
            _report(), _input(), config, created_at=datetime(2026, 7, 14, 12, 0, 0)
        )


def test_build_record_rejects_invalid_config() -> None:
    with pytest.raises(HumanReviewRegistryError):
        build_human_review_record(
            _report(), _input(), object(), created_at=_dt()  # type: ignore[arg-type]
        )


def test_build_record_chains_to_previous() -> None:
    config = HumanReviewRegistryConfig.default()
    first = build_human_review_record(_report(), _input(), config, created_at=_dt())
    second = build_human_review_record(
        _report(),
        HumanReviewInput(
            reviewer_identity="bob",
            reviewer_decision=REJECT,
            review_note="Rejected for research.",
        ),
        config,
        previous_record=first,
        existing_records=(first,),
        created_at=_dt(),
    )
    assert second.previous_record_fingerprint == first.record_fingerprint
    assert second.accepted is True
    assert second.reason_codes == (REVIEW_REJECTED,)


def test_build_record_detects_duplicate() -> None:
    config = HumanReviewRegistryConfig.default()
    first = build_human_review_record(_report(), _input(), config, created_at=_dt())
    second = build_human_review_record(
        _report(), _input(), config, existing_records=(first,), created_at=_dt()
    )
    assert second.accepted is False
    assert DUPLICATE_REVIEW in second.reason_codes


def test_build_record_verifies_existing_chain() -> None:
    config = HumanReviewRegistryConfig.default()
    broken = HumanReviewRecord(
        version=HUMAN_REVIEW_REGISTRY_VERSION,
        source_decision_fingerprint="src",
        source_decision=GO,
        reviewer_identity="alice",
        reviewer_decision=APPROVE_FOR_RESEARCH,
        review_note="note",
        created_at=_dt(),
        previous_record_fingerprint="not-none",
        record_fingerprint="fp",
        accepted=True,
        human_approval_recorded=True,
        execution_approval_granted=False,
        reason_codes=(),
    )
    record = build_human_review_record(
        _report(), _input(), config, existing_records=(broken,), created_at=_dt()
    )
    assert record.accepted is False
    assert BROKEN_REVIEW_CHAIN in record.reason_codes


def test_needs_review_approve_requires_note() -> None:
    config = HumanReviewRegistryConfig.default()
    record = build_human_review_record(
        _report(decision=NEEDS_REVIEW),
        _input(note="short"),
        config,
        created_at=_dt(),
    )
    assert record.accepted is False
    assert REVIEW_NOTE_TOO_SHORT in record.reason_codes


def test_needs_review_request_changes_requires_note() -> None:
    config = HumanReviewRegistryConfig.default()
    record = build_human_review_record(
        _report(decision=NEEDS_REVIEW),
        _input(decision=REQUEST_CHANGES, note="short"),
        config,
        created_at=_dt(),
    )
    assert record.accepted is False
    assert REVIEW_NOTE_TOO_SHORT in record.reason_codes


def test_record_fingerprint_is_stable() -> None:
    config = HumanReviewRegistryConfig.default()
    record = build_human_review_record(_report(), _input(), config, created_at=_dt())
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
    assert record.record_fingerprint == expected
