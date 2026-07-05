"""Tests for hunter.remediation_evidence.models."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from hunter.remediation_evidence import (
    FORBIDDEN_REMEDIATION_EVIDENCE_TERMS,
    REMEDIATION_EVIDENCE_VERSION,
    RemediationBacklogItemRef,
    RemediationEvidenceConfig,
    RemediationEvidenceCoverageResult,
    RemediationEvidenceCoverageState,
    RemediationEvidenceDataQuality,
    RemediationEvidenceInput,
    RemediationEvidenceIssue,
    RemediationEvidenceIssueType,
    RemediationEvidenceLink,
    RemediationEvidenceLinkType,
    RemediationEvidenceReasonCode,
    RemediationEvidenceRecord,
    RemediationEvidenceRecordState,
    RemediationEvidenceReport,
    RemediationEvidenceReviewOutcome,
    RemediationReviewRecord,
    RemediationEvidenceSafetyFlags,
    RemediationEvidenceSeverity,
    RemediationEvidenceState,
    has_unsafe_remediation_evidence_content,
)
from hunter.remediation_backlog.models import RemediationBacklogItemState


NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Enums and constants
# ---------------------------------------------------------------------------


def test_state_enum_values() -> None:
    assert RemediationEvidenceState.OK.value == "ok"
    assert RemediationEvidenceState.DEGRADED.value == "degraded"
    assert RemediationEvidenceState.BLOCKED.value == "blocked"
    assert RemediationEvidenceState.NOT_APPLICABLE.value == "not_applicable"


def test_severity_enum_values() -> None:
    assert RemediationEvidenceSeverity.BLOCKING.value == "blocking"
    assert RemediationEvidenceSeverity.ADVISORY.value == "advisory"
    assert RemediationEvidenceSeverity.INFO.value == "info"


def test_reason_code_enum_values() -> None:
    expected = {
        "ok",
        "not_applicable",
        "consistency_degraded",
        "safety_blocked",
        "unsafe_content",
        "forbidden_term_present",
        "duplicate_id",
        "duplicate_evidence",
        "orphan_evidence",
        "orphan_review",
        "orphan_link",
        "conflicting_review",
        "stale_evidence",
        "stale_review",
        "missing_evidence",
        "missing_review",
        "rejected_evidence",
        "pending_review_evidence",
        "blocked_backlog_item",
        "open_backlog_item",
        "acknowledged_backlog_item",
        "deferred_backlog_item",
        "not_applicable_backlog_item",
    }
    assert {code.value for code in RemediationEvidenceReasonCode} == expected


def test_record_state_enum_values() -> None:
    expected = {
        "accepted",
        "rejected",
        "pending_review",
        "stale",
        "duplicate",
        "orphaned",
        "conflicting",
        "not_applicable",
    }
    assert {state.value for state in RemediationEvidenceRecordState} == expected


def test_coverage_state_enum_values() -> None:
    expected = {
        "covered",
        "partial",
        "missing",
        "rejected",
        "pending_review",
        "conflicting",
        "stale",
        "not_applicable",
    }
    assert {state.value for state in RemediationEvidenceCoverageState} == expected


def test_review_outcome_enum_values() -> None:
    expected = {"accepted", "rejected", "pending_review", "not_applicable"}
    assert {outcome.value for outcome in RemediationEvidenceReviewOutcome} == expected


def test_link_type_enum_values() -> None:
    expected = {"supports", "contradicts", "observes"}
    assert {lt.value for lt in RemediationEvidenceLinkType} == expected


def test_issue_type_enum_values() -> None:
    expected = {
        "unsafe_content",
        "duplicate_id",
        "duplicate_evidence",
        "orphan_evidence",
        "orphan_review",
        "orphan_link",
        "conflicting_review",
        "stale_evidence",
        "stale_review",
        "missing_evidence",
        "missing_review",
        "rejected_evidence",
        "pending_review_evidence",
        "blocked_backlog_item",
        "open_backlog_item",
        "acknowledged_backlog_item",
        "deferred_backlog_item",
        "not_applicable_backlog_item",
    }
    assert {it.value for it in RemediationEvidenceIssueType} == expected


def test_forbidden_terms_are_multi_word_phrases() -> None:
    for term in FORBIDDEN_REMEDIATION_EVIDENCE_TERMS:
        assert " " in term, f"forbidden term must be multi-word phrase: {term!r}"
    # Benign single-word terms must not be present.
    assert "approval" not in FORBIDDEN_REMEDIATION_EVIDENCE_TERMS
    assert "certification" not in FORBIDDEN_REMEDIATION_EVIDENCE_TERMS
    assert "recommendation" not in FORBIDDEN_REMEDIATION_EVIDENCE_TERMS
    assert "signal" not in FORBIDDEN_REMEDIATION_EVIDENCE_TERMS


def test_version_constant() -> None:
    assert REMEDIATION_EVIDENCE_VERSION == "0.38.0-dev"


# ---------------------------------------------------------------------------
# Safety flags
# ---------------------------------------------------------------------------


def test_safety_flags_baseline_invariants() -> None:
    with pytest.raises(ValueError, match="baseline safety invariants"):
        RemediationEvidenceSafetyFlags(no_executable_actions=False)


def test_safety_flags_is_safe_baseline() -> None:
    flags = RemediationEvidenceSafetyFlags()
    assert flags.is_safe is True


def test_safety_flags_is_safe_forbidden_terms() -> None:
    flags = RemediationEvidenceSafetyFlags(has_forbidden_terms=True)
    assert flags.is_safe is False


def test_safety_flags_is_safe_unsafe_content() -> None:
    flags = RemediationEvidenceSafetyFlags(has_unsafe_content=True)
    assert flags.is_safe is False


# ---------------------------------------------------------------------------
# Model defaults and validation
# ---------------------------------------------------------------------------


def test_backlog_item_ref_defaults() -> None:
    ref = RemediationBacklogItemRef(backlog_item_id="b1")
    assert ref.source_id == ""
    assert ref.finding_id == ""
    assert ref.item_state is RemediationBacklogItemState.OPEN
    assert ref.severity == "advisory"
    assert ref.priority == "none"
    assert ref.title == ""


def test_backlog_item_ref_accepts_string_state() -> None:
    ref = RemediationBacklogItemRef(backlog_item_id="b1", item_state="blocked")
    assert ref.item_state is RemediationBacklogItemState.BLOCKED


def test_backlog_item_ref_rejects_invalid_state() -> None:
    with pytest.raises(ValueError, match="item_state"):
        RemediationBacklogItemRef(backlog_item_id="b1", item_state="invalid")


def test_evidence_record_defaults() -> None:
    rec = RemediationEvidenceRecord(evidence_id="e1")
    assert rec.backlog_item_id == ""
    assert rec.title == ""
    assert rec.description == ""
    assert rec.evidence_state is RemediationEvidenceRecordState.PENDING_REVIEW


def test_evidence_record_accepts_string_state() -> None:
    rec = RemediationEvidenceRecord(evidence_id="e1", evidence_state="accepted")
    assert rec.evidence_state is RemediationEvidenceRecordState.ACCEPTED


def test_evidence_record_rejects_invalid_state() -> None:
    with pytest.raises(ValueError, match="evidence_state"):
        RemediationEvidenceRecord(evidence_id="e1", evidence_state="invalid")


def test_review_record_defaults() -> None:
    rev = RemediationReviewRecord(review_id="r1", evidence_id="e1")
    assert rev.outcome is RemediationEvidenceReviewOutcome.PENDING_REVIEW
    assert rev.reviewer == ""
    assert rev.note == ""


def test_review_record_accepts_string_outcome() -> None:
    rev = RemediationReviewRecord(review_id="r1", evidence_id="e1", outcome="accepted")
    assert rev.outcome is RemediationEvidenceReviewOutcome.ACCEPTED


def test_link_defaults() -> None:
    link = RemediationEvidenceLink(link_id="l1", evidence_id="e1", backlog_item_id="b1")
    assert link.link_type is RemediationEvidenceLinkType.SUPPORTS


def test_link_accepts_string_type() -> None:
    link = RemediationEvidenceLink(link_id="l1", evidence_id="e1", backlog_item_id="b1", link_type="contradicts")
    assert link.link_type is RemediationEvidenceLinkType.CONTRADICTS


def test_issue_defaults() -> None:
    issue = RemediationEvidenceIssue(issue_id="i1")
    assert issue.issue_type is RemediationEvidenceIssueType.UNSAFE_CONTENT
    assert issue.severity is RemediationEvidenceSeverity.INFO


def test_coverage_result_defaults() -> None:
    result = RemediationEvidenceCoverageResult(coverage_id="c1", backlog_item_id="b1")
    assert result.coverage_state is RemediationEvidenceCoverageState.MISSING
    assert result.evidence_ids == ()
    assert result.review_ids == ()


def test_config_defaults() -> None:
    config = RemediationEvidenceConfig()
    assert config.strict is False
    assert config.require_review is False
    assert config.require_evidence_for_all is False
    assert config.staleness_threshold_seconds == 2_592_000
    assert config.forbid_action_terms is True


def test_config_rejects_negative_staleness() -> None:
    with pytest.raises(ValueError, match="staleness_threshold_seconds"):
        RemediationEvidenceConfig(staleness_threshold_seconds=-1)


def test_data_quality_rejects_negative_counter() -> None:
    with pytest.raises(ValueError, match="total_backlog_item_refs"):
        RemediationEvidenceDataQuality(total_backlog_item_refs=-1)


# ---------------------------------------------------------------------------
# Input and metadata
# ---------------------------------------------------------------------------


def test_input_metadata_coerced() -> None:
    inp = RemediationEvidenceInput(metadata={"key": "value"})
    assert dict(inp.metadata) == {"key": "value"}


def test_input_metadata_rejects_non_string_keys() -> None:
    with pytest.raises(ValueError, match="metadata keys"):
        RemediationEvidenceInput(metadata={1: "value"})


def test_input_metadata_allows_non_string_values() -> None:
    # Values are not rejected at construction time so the engine can detect unsafe content.
    inp = RemediationEvidenceInput(metadata={"key": 123})
    assert dict(inp.metadata) == {"key": 123}


def test_input_coerces_lists_to_tuples() -> None:
    ref = RemediationBacklogItemRef(backlog_item_id="b1")
    rec = RemediationEvidenceRecord(evidence_id="e1")
    inp = RemediationEvidenceInput(
        backlog_item_refs=[ref],
        evidence_records=[rec],
    )
    assert isinstance(inp.backlog_item_refs, tuple)
    assert isinstance(inp.evidence_records, tuple)


def test_report_includes_all_collections() -> None:
    ref = RemediationBacklogItemRef(backlog_item_id="b1")
    rec = RemediationEvidenceRecord(evidence_id="e1")
    rev = RemediationReviewRecord(review_id="r1", evidence_id="e1")
    link = RemediationEvidenceLink(link_id="l1", evidence_id="e1", backlog_item_id="b1")
    report = RemediationEvidenceReport(
        report_id="rep1",
        generated_at=NOW,
        state=RemediationEvidenceState.OK,
        project_version="0.38.0-dev",
        backlog_item_refs=(ref,),
        evidence_records=(rec,),
        review_records=(rev,),
        links=(link,),
        issues=(),
        coverage_results=(),
        data_quality=RemediationEvidenceDataQuality(),
        safety_flags=RemediationEvidenceSafetyFlags(),
    )
    assert len(report.backlog_item_refs) == 1
    assert len(report.evidence_records) == 1
    assert len(report.review_records) == 1
    assert len(report.links) == 1


def test_report_blocked_classmethod() -> None:
    inp = RemediationEvidenceInput()
    report = RemediationEvidenceReport.blocked(
        input=inp,
        reason_code=RemediationEvidenceReasonCode.UNSAFE_CONTENT,
    )
    assert report.state is RemediationEvidenceState.BLOCKED
    assert RemediationEvidenceReasonCode.SAFETY_BLOCKED in report.reason_codes
    assert RemediationEvidenceReasonCode.UNSAFE_CONTENT in report.reason_codes
    assert "audit-only" in report.safety_notice


# ---------------------------------------------------------------------------
# Unsafe content helper
# ---------------------------------------------------------------------------


def test_has_unsafe_content_string_is_safe() -> None:
    assert has_unsafe_remediation_evidence_content("hello") is False


def test_has_unsafe_content_bytes_is_unsafe() -> None:
    assert has_unsafe_remediation_evidence_content(b"hello") is True


def test_has_unsafe_content_object_is_unsafe() -> None:
    assert has_unsafe_remediation_evidence_content(object()) is True


def test_has_unsafe_content_nested_non_string() -> None:
    assert has_unsafe_remediation_evidence_content({"key": b"value"}) is True


# ---------------------------------------------------------------------------
# Frozen/slot behavior
# ---------------------------------------------------------------------------


def test_models_are_frozen() -> None:
    rec = RemediationEvidenceRecord(evidence_id="e1")
    with pytest.raises(AttributeError):
        rec.evidence_id = "e2"


def test_models_use_slots() -> None:
    rec = RemediationEvidenceRecord(evidence_id="e1")
    with pytest.raises(AttributeError):
        rec.unknown_attr = 1  # type: ignore[attr-defined]


def test_no_mutable_defaults() -> None:
    # Ensure repeated construction does not share mutable state.
    inp1 = RemediationEvidenceInput(metadata={"a": "1"})
    inp2 = RemediationEvidenceInput(metadata={"b": "2"})
    assert dict(inp1.metadata) != dict(inp2.metadata)
