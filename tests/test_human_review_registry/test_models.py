"""Tests for human review registry models."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from hunter.human_review_registry import (
    APPROVE_FOR_RESEARCH,
    GO,
    HUMAN_REVIEW_REGISTRY_VERSION,
    HumanReviewInput,
    HumanReviewRecord,
    HumanReviewRegistryConfig,
    HumanReviewRegistryError,
    MISSING_DECISION_REPORT,
    NO_GO,
    REJECT,
    REQUEST_CHANGES,
    REVIEW_APPROVED_FOR_RESEARCH,
    REVIEW_REJECTED,
    SOURCE_FINGERPRINT_MISSING,
)


def test_version_constant() -> None:
    assert HUMAN_REVIEW_REGISTRY_VERSION == "0.60.0-dev"


def test_default_config() -> None:
    cfg = HumanReviewRegistryConfig.default()
    assert cfg.min_review_note_length == 12
    assert str(cfg.output_dir) == "data/human_review_registry"
    assert str(cfg.report_output_dir) == "reports/human_review_registry"


def test_config_rejects_negative_min_note() -> None:
    with pytest.raises(ValueError):
        HumanReviewRegistryConfig(min_review_note_length=-1)


def test_config_rejects_empty_filename() -> None:
    with pytest.raises(ValueError):
        HumanReviewRegistryConfig(json_filename=" ")


def test_valid_human_review_input() -> None:
    inp = HumanReviewInput(
        reviewer_identity="alice",
        reviewer_decision=APPROVE_FOR_RESEARCH,
        review_note="Approved for research only.",
    )
    assert inp.reviewer_identity == "alice"
    assert inp.reviewer_decision == APPROVE_FOR_RESEARCH


def test_input_rejects_empty_identity() -> None:
    with pytest.raises(ValueError):
        HumanReviewInput(
            reviewer_identity="",
            reviewer_decision=APPROVE_FOR_RESEARCH,
            review_note="note",
        )


def test_input_rejects_invalid_decision() -> None:
    with pytest.raises(ValueError):
        HumanReviewInput(
            reviewer_identity="alice",
            reviewer_decision="EXECUTE",  # type: ignore[arg-type]
            review_note="note",
        )


def test_input_rejects_non_string_note() -> None:
    with pytest.raises(ValueError):
        HumanReviewInput(
            reviewer_identity="alice",
            reviewer_decision=APPROVE_FOR_RESEARCH,
            review_note=123,  # type: ignore[arg-type]
        )


def test_valid_human_review_record() -> None:
    record = HumanReviewRecord(
        version=HUMAN_REVIEW_REGISTRY_VERSION,
        source_decision_fingerprint="src-fp",
        source_decision=GO,
        reviewer_identity="alice",
        reviewer_decision=APPROVE_FOR_RESEARCH,
        review_note="Approved for research only.",
        created_at=datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc),
        previous_record_fingerprint=None,
        record_fingerprint="rec-fp",
        accepted=True,
        human_approval_recorded=True,
        execution_approval_granted=False,
        reason_codes=(REVIEW_APPROVED_FOR_RESEARCH,),
    )
    assert record.accepted is True
    assert record.execution_approval_granted is False


def test_record_rejects_naive_timestamp() -> None:
    with pytest.raises(ValueError):
        HumanReviewRecord(
            version=HUMAN_REVIEW_REGISTRY_VERSION,
            source_decision_fingerprint="src-fp",
            source_decision=GO,
            reviewer_identity="alice",
            reviewer_decision=APPROVE_FOR_RESEARCH,
            review_note="note",
            created_at=datetime(2026, 7, 14, 12, 0, 0),
            previous_record_fingerprint=None,
            record_fingerprint="rec-fp",
            accepted=True,
            human_approval_recorded=True,
            execution_approval_granted=False,
            reason_codes=(REVIEW_APPROVED_FOR_RESEARCH,),
        )


def test_record_rejects_execution_approval_true() -> None:
    with pytest.raises(ValueError):
        HumanReviewRecord(
            version=HUMAN_REVIEW_REGISTRY_VERSION,
            source_decision_fingerprint="src-fp",
            source_decision=GO,
            reviewer_identity="alice",
            reviewer_decision=APPROVE_FOR_RESEARCH,
            review_note="note",
            created_at=datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc),
            previous_record_fingerprint=None,
            record_fingerprint="rec-fp",
            accepted=True,
            human_approval_recorded=True,
            execution_approval_granted=True,
            reason_codes=(REVIEW_APPROVED_FOR_RESEARCH,),
        )


def test_record_rejects_unsupported_reason_code() -> None:
    with pytest.raises(ValueError):
        HumanReviewRecord(
            version=HUMAN_REVIEW_REGISTRY_VERSION,
            source_decision_fingerprint="src-fp",
            source_decision=GO,
            reviewer_identity="alice",
            reviewer_decision=APPROVE_FOR_RESEARCH,
            review_note="note",
            created_at=datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc),
            previous_record_fingerprint=None,
            record_fingerprint="rec-fp",
            accepted=True,
            human_approval_recorded=True,
            execution_approval_granted=False,
            reason_codes=("UNKNOWN_CODE",),
        )


def test_record_accepts_blocking_reason_code() -> None:
    record = HumanReviewRecord(
        version=HUMAN_REVIEW_REGISTRY_VERSION,
        source_decision_fingerprint="src-fp",
        source_decision=GO,
        reviewer_identity="alice",
        reviewer_decision=APPROVE_FOR_RESEARCH,
        review_note="note",
        created_at=datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc),
        previous_record_fingerprint=None,
        record_fingerprint="rec-fp",
        accepted=False,
        human_approval_recorded=False,
        execution_approval_granted=False,
        reason_codes=(SOURCE_FINGERPRINT_MISSING,),
    )
    assert record.accepted is False


def test_error_can_carry_reason_code() -> None:
    err = HumanReviewRegistryError("boom", reason_code=MISSING_DECISION_REPORT)
    assert err.reason_code == MISSING_DECISION_REPORT
