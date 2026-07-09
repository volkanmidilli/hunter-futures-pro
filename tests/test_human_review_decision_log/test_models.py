"""Tests for hunter.human_review_decision_log.models."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from hunter.human_review_decision_log import (
    FORBIDDEN_HUMAN_REVIEW_DECISION_TERMS,
    HUMAN_REVIEW_DECISION_LOG_VERSION,
    OK,
    NOT_APPLICABLE_RC,
    DECISION_LOGGED,
    CONSISTENCY_DEGRADED,
    SAFETY_BLOCKED,
    UNSAFE_CONTENT,
    FORBIDDEN_TERM_PRESENT,
    DUPLICATE_QUEUE_ENTRY_ID,
    DUPLICATE_DECISION_ID,
    DUPLICATE_LINK_ID,
    HumanReviewDecisionIssue,
    HumanReviewDecisionIssueType,
    HumanReviewDecisionLink,
    HumanReviewDecisionLinkType,
    HumanReviewDecisionLogConfig,
    HumanReviewDecisionLogDataQuality,
    HumanReviewDecisionLogInput,
    HumanReviewDecisionLogReport,
    HumanReviewDecisionLogSafetyFlags,
    HumanReviewDecisionLogState,
    HumanReviewDecisionOutcome,
    HumanReviewDecisionReasonCode,
    HumanReviewDecisionRecord,
    HumanReviewDecisionResult,
    HumanReviewDecisionSeverity,
    HumanReviewDecisionState,
    HumanReviewDecisionValidity,
    HumanReviewQueueEntryRef,
    has_unsafe_human_review_decision_content,
)

NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------

def test_version() -> None:
    assert HUMAN_REVIEW_DECISION_LOG_VERSION == "0.41.0-dev"

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

def test_state_enum_values() -> None:
    assert HumanReviewDecisionLogState.OK.value == "ok"
    assert HumanReviewDecisionLogState.DEGRADED.value == "degraded"
    assert HumanReviewDecisionLogState.BLOCKED.value == "blocked"
    assert HumanReviewDecisionLogState.NOT_APPLICABLE.value == "not_applicable"

def test_severity_enum_values() -> None:
    assert HumanReviewDecisionSeverity.BLOCKING.value == "blocking"
    assert HumanReviewDecisionSeverity.ADVISORY.value == "advisory"
    assert HumanReviewDecisionSeverity.INFO.value == "info"

def test_decision_state_enum_values() -> None:
    expected = {
        "logged", "missing", "incomplete", "pending_review", "rejected",
        "disputed", "stale", "duplicate", "orphaned", "superseded",
        "not_applicable", "blocked",
    }
    assert {s.value for s in HumanReviewDecisionState} == expected

def test_decision_outcome_enum_values() -> None:
    expected = {
        "accepted_for_audit_log", "rejected_for_audit_log", "needs_more_review",
        "disputed", "deferred", "not_applicable", "superseded", "unknown",
    }
    assert {o.value for o in HumanReviewDecisionOutcome} == expected

def test_decision_validity_enum_values() -> None:
    expected = {
        "valid_for_audit_log", "invalid_for_audit_log", "partial",
        "pending_review", "disputed", "stale", "not_applicable",
    }
    assert {v.value for v in HumanReviewDecisionValidity} == expected

def test_link_type_enum_values() -> None:
    expected = {"references", "supersedes", "derived_from", "related_to", "unknown"}
    assert {l.value for l in HumanReviewDecisionLinkType} == expected

def test_issue_type_enum_values() -> None:
    expected = {
        "unsafe_content", "forbidden_term",
        "duplicate_queue_entry_id", "duplicate_decision_id", "duplicate_link_id",
        "semantic_duplicate_decision", "orphan_decision", "orphan_link",
        "missing_decision", "conflicting_decision", "conflicting_outcome",
        "stale_queue_entry", "stale_decision",
        "missing_reviewer", "missing_decided_at", "missing_rationale",
        "missing_outcome", "missing_queue_entry_id", "outcome_mismatch",
    }
    assert {t.value for t in HumanReviewDecisionIssueType} == expected

def test_reason_code_enum_values() -> None:
    expected = {
        "ok", "not_applicable", "decision_logged", "consistency_degraded",
        "safety_blocked", "unsafe_content", "forbidden_term_present",
        "invalid_input_data",
        "duplicate_queue_entry_id", "duplicate_decision_id", "duplicate_link_id",
        "semantic_duplicate_decision", "orphan_decision", "orphan_link",
        "missing_decision", "conflicting_decision", "conflicting_outcome",
        "stale_queue_entry", "stale_decision",
        "missing_reviewer", "missing_decided_at", "missing_rationale",
        "missing_outcome", "missing_queue_entry_id", "outcome_mismatch",
        "advisory_finding", "info_finding", "blocking_finding",
    }
    assert {c.value for c in HumanReviewDecisionReasonCode} == expected

# ---------------------------------------------------------------------------
# String constants
# ---------------------------------------------------------------------------

def test_string_constants() -> None:
    assert OK == "ok"
    assert NOT_APPLICABLE_RC == "not_applicable"
    assert DECISION_LOGGED == "decision_logged"
    assert CONSISTENCY_DEGRADED == "consistency_degraded"
    assert SAFETY_BLOCKED == "safety_blocked"
    assert UNSAFE_CONTENT == "unsafe_content"
    assert FORBIDDEN_TERM_PRESENT == "forbidden_term_present"
    assert DUPLICATE_QUEUE_ENTRY_ID == "duplicate_queue_entry_id"
    assert DUPLICATE_DECISION_ID == "duplicate_decision_id"
    assert DUPLICATE_LINK_ID == "duplicate_link_id"

# ---------------------------------------------------------------------------
# Forbidden terms — multi-word only
# ---------------------------------------------------------------------------

def test_forbidden_terms_are_multi_word() -> None:
    """All forbidden terms must be multi-word phrases."""
    for term in FORBIDDEN_HUMAN_REVIEW_DECISION_TERMS:
        assert " " in term, f"Single-word forbidden term found: {term!r}"

def test_forbidden_terms_no_false_positives() -> None:
    """Benign phrases must NOT match."""
    benign = [
        "pending approval from security team",
        "certification body",
        "no recommendation needed",
        "signal processing",
        "no signal detected",
        "assign a reviewer",
        "manual note for audit",
        "task queue",
        "task note",
        "completed checklist",
    ]
    lower_benign = [text.lower() for text in benign]
    for text in lower_benign:
        for term in FORBIDDEN_HUMAN_REVIEW_DECISION_TERMS:
            assert term not in text, f"False positive: {term!r} in {text!r}"

# ---------------------------------------------------------------------------
# Safety helpers
# ---------------------------------------------------------------------------

def test_has_unsafe_content_string_safe() -> None:
    assert has_unsafe_human_review_decision_content("hello") is False

def test_has_unsafe_content_none_safe() -> None:
    assert has_unsafe_human_review_decision_content(None) is False

def test_has_unsafe_content_int_unsafe() -> None:
    assert has_unsafe_human_review_decision_content(42) is True

def test_has_unsafe_content_bytes_unsafe() -> None:
    assert has_unsafe_human_review_decision_content(b"hello") is True

def test_has_unsafe_content_list_with_int() -> None:
    assert has_unsafe_human_review_decision_content(["ok", 42]) is True

def test_has_unsafe_content_dict_with_unsafe_value() -> None:
    assert has_unsafe_human_review_decision_content({"k": object()}) is True

def test_has_unsafe_content_nested_dict_safe() -> None:
    assert has_unsafe_human_review_decision_content({"k": {"v": "safe"}}) is False

# ---------------------------------------------------------------------------
# SafetyFlags
# ---------------------------------------------------------------------------

def test_safety_flags_defaults_safe() -> None:
    flags = HumanReviewDecisionLogSafetyFlags()
    assert flags.is_safe is True
    assert flags.no_executable_actions is True
    assert flags.no_trading_instructions is True
    assert flags.no_approval_claims is True
    assert flags.no_automated_remediation is True
    assert flags.no_automatic_assignment is True
    assert flags.no_task_completion_claims is True
    assert flags.references_opaque is True
    assert flags.audit_only is True
    assert flags.decision_logged_not_approval is True

def test_safety_flags_unsafe_content_not_safe() -> None:
    flags = HumanReviewDecisionLogSafetyFlags(has_unsafe_content=True)
    assert flags.is_safe is False

def test_safety_flags_forbidden_terms_not_safe() -> None:
    flags = HumanReviewDecisionLogSafetyFlags(has_forbidden_terms=True)
    assert flags.is_safe is False

def test_safety_flags_rejects_disabled_baseline() -> None:
    with pytest.raises(ValueError):
        HumanReviewDecisionLogSafetyFlags(no_executable_actions=False)

def test_safety_flags_rejects_disabled_audit_only() -> None:
    with pytest.raises(ValueError):
        HumanReviewDecisionLogSafetyFlags(audit_only=False)

def test_safety_flags_rejects_disabled_decision_logged() -> None:
    with pytest.raises(ValueError):
        HumanReviewDecisionLogSafetyFlags(decision_logged_not_approval=False)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def test_config_defaults() -> None:
    config = HumanReviewDecisionLogConfig()
    assert config.strict is False
    assert config.require_decision_for_all is True
    assert config.forbid_action_terms is True
    assert config.staleness_threshold_seconds == 2_592_000
    assert config.empty_input_is_not_applicable is True

def test_config_rejects_non_bool_strict() -> None:
    with pytest.raises(ValueError):
        HumanReviewDecisionLogConfig(strict="yes")  # type: ignore[arg-type]

def test_config_rejects_negative_threshold() -> None:
    with pytest.raises(ValueError):
        HumanReviewDecisionLogConfig(staleness_threshold_seconds=-1)

# ---------------------------------------------------------------------------
# HumanReviewQueueEntryRef
# ---------------------------------------------------------------------------

def test_queue_entry_ref_defaults() -> None:
    ref = HumanReviewQueueEntryRef()
    assert ref.queue_entry_id == ""
    assert ref.source_id == ""
    assert ref.reason_codes == ()
    assert ref.generated_at is None
    assert ref.artifact_ref == ""

def test_queue_entry_ref_frozen() -> None:
    ref = HumanReviewQueueEntryRef(queue_entry_id="q1")
    with pytest.raises(Exception):
        ref.queue_entry_id = "q2"  # type: ignore[misc]

def test_queue_entry_ref_metadata_immutable() -> None:
    ref = HumanReviewQueueEntryRef(metadata={"k": "v"})
    assert ref.metadata["k"] == "v"

def test_queue_entry_ref_normalizes_reason_codes() -> None:
    ref = HumanReviewQueueEntryRef(reason_codes=["a", "b"])
    assert ref.reason_codes == ("a", "b")
    assert isinstance(ref.reason_codes, tuple)

def test_queue_entry_ref_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError):
        HumanReviewQueueEntryRef(generated_at=datetime(2026, 1, 1))

# ---------------------------------------------------------------------------
# HumanReviewDecisionRecord
# ---------------------------------------------------------------------------

def test_decision_record_defaults() -> None:
    rec = HumanReviewDecisionRecord()
    assert rec.decision_id == ""
    assert rec.outcome == "unknown"
    assert rec.rationale == ""
    assert rec.reason_codes == ()

def test_decision_record_frozen() -> None:
    rec = HumanReviewDecisionRecord(decision_id="d1")
    with pytest.raises(Exception):
        rec.decision_id = "d2"  # type: ignore[misc]

def test_decision_record_normalizes_reason_codes() -> None:
    rec = HumanReviewDecisionRecord(reason_codes=["x"])
    assert rec.reason_codes == ("x",)

def test_decision_record_rejects_naive_decided_at() -> None:
    with pytest.raises(ValueError):
        HumanReviewDecisionRecord(decided_at=datetime(2026, 1, 1))

# ---------------------------------------------------------------------------
# HumanReviewDecisionLink
# ---------------------------------------------------------------------------

def test_decision_link_defaults() -> None:
    link = HumanReviewDecisionLink()
    assert link.link_id == ""
    assert link.link_type == "unknown"

def test_decision_link_frozen() -> None:
    link = HumanReviewDecisionLink(link_id="l1")
    with pytest.raises(Exception):
        link.link_id = "l2"  # type: ignore[misc]

# ---------------------------------------------------------------------------
# HumanReviewDecisionIssue
# ---------------------------------------------------------------------------

def test_issue_defaults() -> None:
    issue = HumanReviewDecisionIssue()
    assert issue.issue_id == ""
    assert issue.severity == "info"

def test_issue_frozen() -> None:
    issue = HumanReviewDecisionIssue(issue_id="i1")
    with pytest.raises(Exception):
        issue.issue_id = "i2"  # type: ignore[misc]

# ---------------------------------------------------------------------------
# HumanReviewDecisionResult
# ---------------------------------------------------------------------------

def test_result_defaults() -> None:
    result = HumanReviewDecisionResult()
    assert result.decision_result_id == ""
    assert result.decision_state == "missing"
    assert result.decision_outcome == "unknown"
    assert result.decision_validity == "invalid_for_audit_log"
    assert result.severity == "info"

def test_result_frozen() -> None:
    result = HumanReviewDecisionResult(decision_result_id="r1")
    with pytest.raises(Exception):
        result.decision_result_id = "r2"  # type: ignore[misc]

def test_result_normalizes_decision_ids() -> None:
    result = HumanReviewDecisionResult(decision_ids=["a", "b"])
    assert result.decision_ids == ("a", "b")

# ---------------------------------------------------------------------------
# DataQuality
# ---------------------------------------------------------------------------

def test_data_quality_defaults() -> None:
    dq = HumanReviewDecisionLogDataQuality()
    assert dq.total_queue_entry_refs == 0
    assert dq.total_decision_records == 0
    assert dq.total_issues == 0
    assert dq.total_decision_results == 0
    assert dq.logged_count == 0
    assert dq.missing_count == 0

def test_data_quality_rejects_negative() -> None:
    with pytest.raises(ValueError):
        HumanReviewDecisionLogDataQuality(total_queue_entry_refs=-1)

# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------

def test_input_defaults() -> None:
    inp = HumanReviewDecisionLogInput()
    assert inp.queue_entry_refs == ()
    assert inp.decision_records == ()
    assert inp.links == ()
    assert inp.metadata == {} or len(inp.metadata) == 0
    assert inp.project_version == HUMAN_REVIEW_DECISION_LOG_VERSION

def test_input_metadata_mapping() -> None:
    inp = HumanReviewDecisionLogInput(metadata={"key": "value"})
    assert inp.metadata["key"] == "value"

def test_input_metadata_defaults_to_empty() -> None:
    inp = HumanReviewDecisionLogInput()
    assert len(inp.metadata) == 0

def test_input_rejects_naive_generated_at() -> None:
    with pytest.raises(ValueError):
        HumanReviewDecisionLogInput(generated_at=datetime(2026, 1, 1))

def test_input_validates_queue_entry_refs_type() -> None:
    with pytest.raises(ValueError):
        HumanReviewDecisionLogInput(queue_entry_refs=("not_a_ref",))  # type: ignore[arg-type]

def test_input_validates_decision_records_type() -> None:
    with pytest.raises(ValueError):
        HumanReviewDecisionLogInput(decision_records=("not_a_record",))  # type: ignore[arg-type]

def test_input_validates_links_type() -> None:
    with pytest.raises(ValueError):
        HumanReviewDecisionLogInput(links=("not_a_link",))  # type: ignore[arg-type]

# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def test_report_defaults() -> None:
    report = HumanReviewDecisionLogReport()
    assert report.report_id == ""
    assert report.state == HumanReviewDecisionLogState.NOT_APPLICABLE
    assert report.queue_entry_refs == ()
    assert report.decision_records == ()
    assert report.links == ()
    assert report.issues == ()
    assert report.decision_results == ()
    assert report.project_version == HUMAN_REVIEW_DECISION_LOG_VERSION

def test_report_frozen() -> None:
    report = HumanReviewDecisionLogReport()
    with pytest.raises(Exception):
        report.report_id = "x"  # type: ignore[misc]

def test_report_blocked_classmethod() -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(HumanReviewQueueEntryRef(queue_entry_id="q1"),),
        generated_at=NOW,
    )
    report = HumanReviewDecisionLogReport.blocked(input=inp)
    assert report.state == HumanReviewDecisionLogState.BLOCKED
    assert report.safety_flags.has_unsafe_content is True
    assert HumanReviewDecisionReasonCode.UNSAFE_CONTENT in report.reason_codes

def test_report_blocked_with_forbidden_terms() -> None:
    inp = HumanReviewDecisionLogInput(generated_at=NOW)
    report = HumanReviewDecisionLogReport.blocked(
        input=inp,
        reason_code=HumanReviewDecisionReasonCode.FORBIDDEN_TERM_PRESENT,
    )
    assert report.state == HumanReviewDecisionLogState.BLOCKED
    assert report.safety_flags.has_forbidden_terms is True


def test_report_blocked_has_non_empty_deterministic_report_id() -> None:
    inp = HumanReviewDecisionLogInput(generated_at=NOW)
    report1 = HumanReviewDecisionLogReport.blocked(input=inp)
    report2 = HumanReviewDecisionLogReport.blocked(input=inp)
    assert report1.report_id
    assert report1.report_id.startswith("blocked-human-review-decision-log-")
    assert report1.report_id == report2.report_id
    assert len(report1.report_id) < 70


def test_report_blocked_id_varies_with_input() -> None:
    a = HumanReviewDecisionLogInput(generated_at=NOW)
    b = HumanReviewDecisionLogInput(
        queue_entry_refs=(HumanReviewQueueEntryRef(queue_entry_id="q1"),),
        generated_at=NOW,
    )
    report_a = HumanReviewDecisionLogReport.blocked(input=a)
    report_b = HumanReviewDecisionLogReport.blocked(input=b)
    assert report_a.report_id != report_b.report_id

def test_report_validates_state_enum() -> None:
    with pytest.raises(ValueError):
        HumanReviewDecisionLogReport(state="invalid")  # type: ignore[arg-type]

def test_report_validates_decision_results_type() -> None:
    with pytest.raises(ValueError):
        HumanReviewDecisionLogReport(decision_results=("not_a_result",))  # type: ignore[arg-type]

# ---------------------------------------------------------------------------
# Opaque refs
# ---------------------------------------------------------------------------

def test_artifact_ref_stored_as_string() -> None:
    ref = HumanReviewQueueEntryRef(artifact_ref="some/opaque/path")
    assert isinstance(ref.artifact_ref, str)
    assert ref.artifact_ref == "some/opaque/path"

def test_report_ref_stored_as_string() -> None:
    rec = HumanReviewDecisionRecord(report_ref="opaque/report/ref")
    assert isinstance(rec.report_ref, str)
