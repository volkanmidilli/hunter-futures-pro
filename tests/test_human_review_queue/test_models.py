"""Tests for hunter.human_review_queue.models."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from hunter.human_review_queue import (
    FORBIDDEN_HUMAN_REVIEW_QUEUE_TERMS,
    HUMAN_REVIEW_QUEUE_VERSION,
    HumanReviewQueueConfig,
    HumanReviewQueueDataQuality,
    HumanReviewQueueDecisionHint,
    HumanReviewQueueEntry,
    HumanReviewQueueEntryState,
    HumanReviewQueueInput,
    HumanReviewQueueIssue,
    HumanReviewQueueIssueType,
    HumanReviewQueuePriority,
    HumanReviewQueueReasonCode,
    HumanReviewQueueReport,
    HumanReviewQueueSafetyFlags,
    HumanReviewQueueSeverity,
    HumanReviewQueueSourceKind,
    HumanReviewQueueState,
    HumanReviewSourceRecord,
    has_unsafe_human_review_queue_content,
)

NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Enums and constants
# ---------------------------------------------------------------------------


def test_state_enum_values() -> None:
    assert HumanReviewQueueState.OK.value == "ok"
    assert HumanReviewQueueState.DEGRADED.value == "degraded"
    assert HumanReviewQueueState.BLOCKED.value == "blocked"
    assert HumanReviewQueueState.NOT_APPLICABLE.value == "not_applicable"


def test_severity_enum_values() -> None:
    assert HumanReviewQueueSeverity.BLOCKING.value == "blocking"
    assert HumanReviewQueueSeverity.ADVISORY.value == "advisory"
    assert HumanReviewQueueSeverity.INFO.value == "info"


def test_reason_code_enum_values() -> None:
    expected = {
        "ok",
        "not_applicable",
        "consistency_degraded",
        "safety_blocked",
        "unsafe_content",
        "forbidden_term_present",
        "duplicate_source_id",
        "duplicate_queue_entry",
        "orphan_related_record",
        "stale_source_record",
        "blocking_severity",
        "advisory_severity",
        "info_severity",
        "disputed_state",
        "pending_review_state",
        "missing_evidence",
        "missing_review",
        "missing_closure_metadata",
        "manual_review_required",
    }
    assert {code.value for code in HumanReviewQueueReasonCode} == expected


def test_entry_state_enum_values() -> None:
    expected = {
        "queued",
        "blocked",
        "pending_review",
        "stale",
        "disputed",
        "duplicate",
        "orphaned",
        "acknowledged",
        "deferred",
        "not_applicable",
        "suppressed",
    }
    assert {state.value for state in HumanReviewQueueEntryState} == expected


def test_priority_enum_values() -> None:
    expected = {"critical", "high", "medium", "low", "info"}
    assert {priority.value for priority in HumanReviewQueuePriority} == expected


def test_source_kind_enum_values() -> None:
    expected = {
        "backlog_item",
        "evidence_record",
        "closure_record",
        "issue",
        "report_summary",
        "manual_note",
    }
    assert {kind.value for kind in HumanReviewQueueSourceKind} == expected


def test_decision_hint_enum_values() -> None:
    expected = {
        "review_required",
        "review_optional",
        "already_acknowledged",
        "deferred_for_later_audit",
        "not_applicable_for_audit",
        "suppressed_by_config",
    }
    assert {hint.value for hint in HumanReviewQueueDecisionHint} == expected


def test_issue_type_enum_values() -> None:
    expected = {
        "unsafe_content",
        "forbidden_term",
        "duplicate_source_id",
        "duplicate_queue_entry",
        "orphan_related_record",
        "stale_source_record",
        "blocking_severity",
        "advisory_severity",
        "info_severity",
        "disputed_state",
        "pending_review_state",
        "missing_evidence",
        "missing_review",
        "missing_closure_metadata",
    }
    assert {it.value for it in HumanReviewQueueIssueType} == expected


def test_version_constant() -> None:
    assert HUMAN_REVIEW_QUEUE_VERSION == "0.40.0-dev"


# ---------------------------------------------------------------------------
# Safety helpers
# ---------------------------------------------------------------------------


def test_forbidden_terms_are_multi_word_phrases() -> None:
    for term in FORBIDDEN_HUMAN_REVIEW_QUEUE_TERMS:
        assert " " in term, f"forbidden term must be multi-word phrase: {term!r}"
    assert "approval" not in FORBIDDEN_HUMAN_REVIEW_QUEUE_TERMS
    assert "certification" not in FORBIDDEN_HUMAN_REVIEW_QUEUE_TERMS
    assert "recommendation" not in FORBIDDEN_HUMAN_REVIEW_QUEUE_TERMS
    assert "signal" not in FORBIDDEN_HUMAN_REVIEW_QUEUE_TERMS


def test_forbidden_terms_include_queue_specific_phrases() -> None:
    assert "auto assign" in FORBIDDEN_HUMAN_REVIEW_QUEUE_TERMS
    assert "task assignment" in FORBIDDEN_HUMAN_REVIEW_QUEUE_TERMS
    assert "send email" in FORBIDDEN_HUMAN_REVIEW_QUEUE_TERMS


def test_has_unsafe_content_safe_strings() -> None:
    assert has_unsafe_human_review_queue_content("safe string") is False
    assert has_unsafe_human_review_queue_content(None) is False
    assert has_unsafe_human_review_queue_content(("a", "b")) is False
    assert has_unsafe_human_review_queue_content({"key": "value"}) is False


def test_has_unsafe_content_detects_non_strings() -> None:
    assert has_unsafe_human_review_queue_content(123) is True
    assert has_unsafe_human_review_queue_content([1, 2, 3]) is True
    assert has_unsafe_human_review_queue_content({"key": 123}) is True


# ---------------------------------------------------------------------------
# Model defaults
# ---------------------------------------------------------------------------


def test_config_defaults() -> None:
    config = HumanReviewQueueConfig()
    assert config.strict is False
    assert config.include_advisory is True
    assert config.include_stale is True
    assert config.include_manual_notes is True
    assert config.suppress_acknowledged is False
    assert config.staleness_threshold_seconds == 2_592_000
    assert config.forbid_action_terms is True


def test_safety_flags_defaults() -> None:
    flags = HumanReviewQueueSafetyFlags()
    assert flags.is_safe is True
    assert flags.no_executable_actions is True
    assert flags.no_trading_instructions is True
    assert flags.no_approval_claims is True
    assert flags.no_automated_remediation is True
    assert flags.no_automatic_assignment is True
    assert flags.references_opaque is True
    assert flags.audit_only is True
    assert flags.queued_not_approval is True


def test_safety_flags_invariant_enforcement() -> None:
    with pytest.raises(ValueError, match="baseline safety invariants"):
        HumanReviewQueueSafetyFlags(no_executable_actions=False)


def test_source_record_defaults() -> None:
    record = HumanReviewSourceRecord()
    assert record.source_id == ""
    assert record.source_kind == ""
    assert record.record_id == ""
    assert record.related_record_ids == ()
    assert record.title == ""
    assert record.description == ""
    assert record.state == ""
    assert record.severity == ""
    assert record.reason_codes == ()
    assert record.owner == ""
    assert record.reviewer == ""
    assert record.generated_at is None
    assert record.artifact_ref == ""
    assert record.report_ref == ""
    assert dict(record.metadata) == {}


def test_queue_entry_defaults() -> None:
    entry = HumanReviewQueueEntry()
    assert entry.entry_state == "queued"
    assert entry.priority == "info"
    assert entry.decision_hint == "review_required"
    assert entry.severity == "info"


def test_issue_defaults() -> None:
    issue = HumanReviewQueueIssue()
    assert issue.severity == "info"
    assert issue.issue_type == ""


def test_data_quality_defaults() -> None:
    dq = HumanReviewQueueDataQuality()
    assert dq.total_source_records == 0
    assert dq.total_queue_entries == 0
    assert dq.total_issues == 0


def test_input_defaults() -> None:
    inp = HumanReviewQueueInput()
    assert inp.source_records == ()
    assert inp.project_version == HUMAN_REVIEW_QUEUE_VERSION
    assert dict(inp.metadata) == {}
    assert inp.generated_at is None


def test_report_defaults() -> None:
    report = HumanReviewQueueReport()
    assert report.state == HumanReviewQueueState.NOT_APPLICABLE
    assert report.project_version == HUMAN_REVIEW_QUEUE_VERSION
    assert report.queue_entries == ()
    assert report.issues == ()


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_naive_datetime_rejected() -> None:
    naive = datetime(2026, 1, 1, 12, 0, 0)
    with pytest.raises(ValueError, match="timezone-aware"):
        HumanReviewSourceRecord(generated_at=naive)
    with pytest.raises(ValueError, match="timezone-aware"):
        HumanReviewQueueInput(generated_at=naive)


def test_config_non_negative_int_enforced() -> None:
    with pytest.raises(ValueError, match="non-negative integer"):
        HumanReviewQueueConfig(staleness_threshold_seconds=-1)


def test_config_bool_enforced() -> None:
    with pytest.raises(ValueError, match="must be a bool"):
        HumanReviewQueueConfig(strict="yes")


def test_source_records_must_be_objects() -> None:
    with pytest.raises(ValueError, match="HumanReviewSourceRecord"):
        HumanReviewQueueInput(source_records=(["not a record"]))


def test_input_metadata_mapping() -> None:
    inp = HumanReviewQueueInput(metadata={"a": "1", "b": "2"})
    assert dict(inp.metadata) == {"a": "1", "b": "2"}


# ---------------------------------------------------------------------------
# Safety flags
# ---------------------------------------------------------------------------


def test_safety_flags_mark_unsafe() -> None:
    flags = HumanReviewQueueSafetyFlags(has_unsafe_content=True)
    assert flags.is_safe is False


def test_safety_flags_mark_forbidden() -> None:
    flags = HumanReviewQueueSafetyFlags(has_forbidden_terms=True)
    assert flags.is_safe is False


# ---------------------------------------------------------------------------
# Opaque references
# ---------------------------------------------------------------------------


def test_opaque_refs_not_validated() -> None:
    record = HumanReviewSourceRecord(
        artifact_ref="/path/that/does/not/exist.json",
        report_ref="s3://bucket/object",
        metadata={"path": "/another/opaque/path", "url": "https://example.com"},
    )
    assert record.artifact_ref == "/path/that/does/not/exist.json"
    assert record.report_ref == "s3://bucket/object"
    assert dict(record.metadata) == {"path": "/another/opaque/path", "url": "https://example.com"}
