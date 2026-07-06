"""Tests for hunter.remediation_closure.models."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from hunter.remediation_closure import (
    FORBIDDEN_REMEDIATION_CLOSURE_TERMS,
    REMEDIATION_CLOSURE_VERSION,
    RemediationClosureBacklogItemRef,
    RemediationClosureConfig,
    RemediationClosureDataQuality,
    RemediationClosureDeclaration,
    RemediationClosureEligibilityState,
    RemediationClosureEvidenceSummary,
    RemediationClosureInput,
    RemediationClosureIssue,
    RemediationClosureIssueType,
    RemediationClosureLink,
    RemediationClosureLinkType,
    RemediationClosureReasonCode,
    RemediationClosureRecordState,
    RemediationClosureReport,
    RemediationClosureResult,
    RemediationClosureReviewOutcome,
    RemediationClosureReviewRecord,
    RemediationClosureSafetyFlags,
    RemediationClosureSeverity,
    RemediationClosureState,
    has_unsafe_remediation_closure_content,
)


NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Enums and constants
# ---------------------------------------------------------------------------


def test_state_enum_values() -> None:
    assert RemediationClosureState.OK.value == "ok"
    assert RemediationClosureState.DEGRADED.value == "degraded"
    assert RemediationClosureState.BLOCKED.value == "blocked"
    assert RemediationClosureState.NOT_APPLICABLE.value == "not_applicable"


def test_severity_enum_values() -> None:
    assert RemediationClosureSeverity.BLOCKING.value == "blocking"
    assert RemediationClosureSeverity.ADVISORY.value == "advisory"
    assert RemediationClosureSeverity.INFO.value == "info"


def test_reason_code_enum_values() -> None:
    expected = {
        "ok",
        "not_applicable",
        "consistency_degraded",
        "safety_blocked",
        "unsafe_content",
        "forbidden_term_present",
        "duplicate_id",
        "orphan_evidence",
        "orphan_closure",
        "orphan_review",
        "orphan_link",
        "conflicting_closure",
        "conflicting_review",
        "stale_evidence",
        "stale_closure",
        "stale_review",
        "missing_evidence",
        "missing_review",
        "missing_closure_metadata",
        "rejected_review",
        "pending_review",
        "disputed_review",
        "manual_review_required",
        "blocked_backlog_item",
        "open_backlog_item",
        "conflicting_backlog_item",
        "acknowledged_backlog_item",
        "deferred_backlog_item",
        "not_applicable_backlog_item",
        "closure_recorded",
    }
    assert {code.value for code in RemediationClosureReasonCode} == expected


def test_record_state_enum_values() -> None:
    expected = {
        "closed_recorded",
        "partial",
        "blocked",
        "pending_review",
        "rejected",
        "disputed",
        "stale",
        "duplicate",
        "orphaned",
        "not_applicable",
    }
    assert {state.value for state in RemediationClosureRecordState} == expected


def test_eligibility_state_enum_values() -> None:
    expected = {
        "eligible",
        "partial",
        "ineligible",
        "pending_review",
        "disputed",
        "stale",
        "not_applicable",
    }
    assert {state.value for state in RemediationClosureEligibilityState} == expected


def test_review_outcome_enum_values() -> None:
    expected = {"accepted", "rejected", "pending", "disputed", "not_required", "not_applicable"}
    assert {outcome.value for outcome in RemediationClosureReviewOutcome} == expected


def test_link_type_enum_values() -> None:
    expected = {"closure_evidence", "closure_backlog", "evidence_backlog"}
    assert {lt.value for lt in RemediationClosureLinkType} == expected


def test_issue_type_enum_values() -> None:
    expected = {
        "unsafe_content",
        "duplicate_id",
        "orphan_evidence",
        "orphan_closure",
        "orphan_review",
        "orphan_link",
        "conflicting_closure",
        "conflicting_review",
        "stale_evidence",
        "stale_closure",
        "stale_review",
        "missing_evidence",
        "missing_review",
        "missing_closure_metadata",
        "rejected_review",
        "pending_review",
        "disputed_review",
        "manual_review_required",
        "blocked_backlog_item",
        "open_backlog_item",
        "conflicting_backlog_item",
        "acknowledged_backlog_item",
        "deferred_backlog_item",
        "not_applicable_backlog_item",
    }
    assert {it.value for it in RemediationClosureIssueType} == expected


def test_forbidden_terms_are_multi_word_phrases() -> None:
    for term in FORBIDDEN_REMEDIATION_CLOSURE_TERMS:
        assert " " in term, f"forbidden term must be multi-word phrase: {term!r}"
    assert "approval" not in FORBIDDEN_REMEDIATION_CLOSURE_TERMS
    assert "certification" not in FORBIDDEN_REMEDIATION_CLOSURE_TERMS
    assert "recommendation" not in FORBIDDEN_REMEDIATION_CLOSURE_TERMS
    assert "signal" not in FORBIDDEN_REMEDIATION_CLOSURE_TERMS


def test_forbidden_terms_include_closure_specific_phrases() -> None:
    assert "close now" in FORBIDDEN_REMEDIATION_CLOSURE_TERMS
    assert "close and trade" in FORBIDDEN_REMEDIATION_CLOSURE_TERMS
    assert "release to production" in FORBIDDEN_REMEDIATION_CLOSURE_TERMS


def test_version_constant() -> None:
    assert REMEDIATION_CLOSURE_VERSION == "0.39.0-dev"


# ---------------------------------------------------------------------------
# Safety flags
# ---------------------------------------------------------------------------


def test_safety_flags_baseline_invariants() -> None:
    with pytest.raises(ValueError, match="baseline safety invariants"):
        RemediationClosureSafetyFlags(no_executable_actions=False)


def test_safety_flags_is_safe_baseline() -> None:
    flags = RemediationClosureSafetyFlags()
    assert flags.is_safe is True


def test_safety_flags_is_safe_forbidden_terms() -> None:
    flags = RemediationClosureSafetyFlags(has_forbidden_terms=True)
    assert flags.is_safe is False


def test_safety_flags_is_safe_unsafe_content() -> None:
    flags = RemediationClosureSafetyFlags(has_unsafe_content=True)
    assert flags.is_safe is False


# ---------------------------------------------------------------------------
# Model defaults and validation
# ---------------------------------------------------------------------------


def test_config_defaults() -> None:
    config = RemediationClosureConfig()
    assert config.strict is False
    assert config.require_review is False
    assert config.require_closure_for_all is False
    assert config.require_evidence_for_closure is True
    assert config.staleness_threshold_seconds == 2_592_000
    assert config.forbid_action_terms is True
    assert config.require_closure_metadata is False


def test_config_rejects_negative_staleness() -> None:
    with pytest.raises(ValueError, match="staleness_threshold_seconds"):
        RemediationClosureConfig(staleness_threshold_seconds=-1)


def test_config_rejects_non_bool() -> None:
    with pytest.raises(ValueError, match="strict"):
        RemediationClosureConfig(strict="false")  # type: ignore[arg-type]


def test_backlog_item_ref_defaults() -> None:
    ref = RemediationClosureBacklogItemRef(backlog_item_id="b1")
    assert ref.source_id == ""
    assert ref.finding_id == ""
    assert ref.item_state == "open"
    assert ref.severity == "advisory"
    assert ref.priority == "none"
    assert ref.title == ""


def test_backlog_item_ref_coerces_state_to_lowercase() -> None:
    ref = RemediationClosureBacklogItemRef(backlog_item_id="b1", item_state="BLOCKED")
    assert ref.item_state == "blocked"


def test_evidence_summary_defaults() -> None:
    summary = RemediationClosureEvidenceSummary(evidence_summary_id="es1")
    assert summary.backlog_item_id == ""
    assert summary.coverage_state == "missing"
    assert summary.evidence_ids == ()
    assert summary.review_ids == ()


def test_closure_declaration_defaults() -> None:
    decl = RemediationClosureDeclaration(closure_id="c1")
    assert decl.backlog_item_id == ""
    assert decl.evidence_summary_id == ""
    assert decl.declared_by == ""
    assert decl.reviewed_by == ""
    assert decl.closed_at is None
    assert decl.rationale == ""
    assert decl.evidence_link == ""


def test_review_record_defaults() -> None:
    rev = RemediationClosureReviewRecord(review_id="r1", closure_id="c1")
    assert rev.outcome == "pending"
    assert rev.reviewer == ""
    assert rev.note == ""


def test_link_defaults() -> None:
    link = RemediationClosureLink(link_id="l1", closure_id="c1")
    assert link.evidence_summary_id == ""
    assert link.backlog_item_id == ""
    assert link.link_type == "closure_evidence"


def test_issue_defaults() -> None:
    issue = RemediationClosureIssue(issue_id="i1")
    assert issue.issue_type is RemediationClosureIssueType.UNSAFE_CONTENT
    assert issue.severity is RemediationClosureSeverity.INFO


def test_closure_result_defaults() -> None:
    result = RemediationClosureResult(closure_result_id="cr1", backlog_item_id="b1")
    assert result.record_state is RemediationClosureRecordState.NOT_APPLICABLE
    assert result.eligibility_state is RemediationClosureEligibilityState.NOT_APPLICABLE
    assert result.review_outcome is RemediationClosureReviewOutcome.NOT_REQUIRED
    assert result.severity is RemediationClosureSeverity.INFO


def test_data_quality_rejects_negative_counter() -> None:
    with pytest.raises(ValueError, match="total_backlog_item_refs"):
        RemediationClosureDataQuality(total_backlog_item_refs=-1)


# ---------------------------------------------------------------------------
# Input and metadata
# ---------------------------------------------------------------------------


def test_input_metadata_coerced() -> None:
    inp = RemediationClosureInput(metadata={"key": "value"})
    assert dict(inp.metadata) == {"key": "value"}


def test_input_metadata_rejects_non_string_keys() -> None:
    with pytest.raises(ValueError, match="metadata keys"):
        RemediationClosureInput(metadata={1: "value"})


def test_input_metadata_allows_non_string_values() -> None:
    inp = RemediationClosureInput(metadata={"key": 123})
    assert dict(inp.metadata) == {"key": 123}


def test_input_coerces_lists_to_tuples() -> None:
    ref = RemediationClosureBacklogItemRef(backlog_item_id="b1")
    summary = RemediationClosureEvidenceSummary(evidence_summary_id="es1")
    inp = RemediationClosureInput(
        backlog_item_refs=[ref],
        evidence_summaries=[summary],
    )
    assert isinstance(inp.backlog_item_refs, tuple)
    assert isinstance(inp.evidence_summaries, tuple)


def test_report_includes_all_collections() -> None:
    ref = RemediationClosureBacklogItemRef(backlog_item_id="b1")
    summary = RemediationClosureEvidenceSummary(evidence_summary_id="es1")
    decl = RemediationClosureDeclaration(closure_id="c1")
    rev = RemediationClosureReviewRecord(review_id="r1", closure_id="c1")
    link = RemediationClosureLink(link_id="l1", closure_id="c1")
    report = RemediationClosureReport(
        report_id="rep1",
        generated_at=NOW,
        state=RemediationClosureState.OK,
        project_version="0.39.0-dev",
        backlog_item_refs=(ref,),
        evidence_summaries=(summary,),
        closure_declarations=(decl,),
        review_records=(rev,),
        links=(link,),
        issues=(),
        closure_results=(),
        data_quality=RemediationClosureDataQuality(),
        safety_flags=RemediationClosureSafetyFlags(),
    )
    assert len(report.backlog_item_refs) == 1
    assert len(report.evidence_summaries) == 1
    assert len(report.closure_declarations) == 1
    assert len(report.review_records) == 1
    assert len(report.links) == 1


def test_report_blocked_classmethod() -> None:
    inp = RemediationClosureInput()
    report = RemediationClosureReport.blocked(
        input=inp,
        reason_code=RemediationClosureReasonCode.UNSAFE_CONTENT,
    )
    assert report.state is RemediationClosureState.BLOCKED
    assert RemediationClosureReasonCode.SAFETY_BLOCKED in report.reason_codes
    assert RemediationClosureReasonCode.UNSAFE_CONTENT in report.reason_codes
    assert "audit-only" in report.safety_notice
    assert report.closure_results == ()


# ---------------------------------------------------------------------------
# Unsafe content helper
# ---------------------------------------------------------------------------


def test_has_unsafe_content_string_is_safe() -> None:
    assert has_unsafe_remediation_closure_content("hello") is False


def test_has_unsafe_content_bytes_is_unsafe() -> None:
    assert has_unsafe_remediation_closure_content(b"hello") is True


def test_has_unsafe_content_object_is_unsafe() -> None:
    assert has_unsafe_remediation_closure_content(object()) is True


def test_has_unsafe_content_nested_non_string() -> None:
    assert has_unsafe_remediation_closure_content({"key": b"value"}) is True


# ---------------------------------------------------------------------------
# Frozen/slot behavior
# ---------------------------------------------------------------------------


def test_models_are_frozen() -> None:
    decl = RemediationClosureDeclaration(closure_id="c1")
    with pytest.raises(AttributeError):
        decl.closure_id = "c2"


def test_models_use_slots() -> None:
    decl = RemediationClosureDeclaration(closure_id="c1")
    with pytest.raises(AttributeError):
        decl.unknown_attr = 1  # type: ignore[attr-defined]


def test_no_mutable_defaults() -> None:
    inp1 = RemediationClosureInput(metadata={"a": "1"})
    inp2 = RemediationClosureInput(metadata={"b": "2"})
    assert dict(inp1.metadata) != dict(inp2.metadata)
