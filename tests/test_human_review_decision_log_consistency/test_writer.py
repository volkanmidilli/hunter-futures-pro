"""Tests for hunter.human_review_decision_log_consistency.writer."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import pytest

from hunter.human_review_decision_log_consistency import (
    FORBIDDEN_HUMAN_REVIEW_DECISION_LOG_CONSISTENCY_TERMS,
    HumanReviewDecisionLogConsistencyCrossReference,
    HumanReviewDecisionLogConsistencyDataQuality,
    HumanReviewDecisionLogConsistencyIssue,
    HumanReviewDecisionLogConsistencyReasonCode,
    HumanReviewDecisionLogConsistencyReport,
    HumanReviewDecisionLogConsistencySafetyFlags,
    HumanReviewDecisionLogConsistencyState,
    SAFETY_NOTICE,
    human_review_decision_log_consistency_report_to_dict,
    human_review_decision_log_consistency_report_to_json_text,
    human_review_decision_log_consistency_report_to_markdown_text,
)

NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cross_reference(
    *,
    cross_reference_id: str = "cr-1",
    queue_entry_id: str = "qe-1",
    decision_log_queue_entry_id: str = "qe-1",
    queue_entry_state: str = "open",
    decision_log_result_state: str = "open",
    match_status: str = "matched",
    severity: str = "info",
    reason_codes: tuple[str, ...] = (),
    rationale: str = "Matched",
) -> HumanReviewDecisionLogConsistencyCrossReference:
    return HumanReviewDecisionLogConsistencyCrossReference(
        cross_reference_id=cross_reference_id,
        queue_entry_id=queue_entry_id,
        decision_log_queue_entry_id=decision_log_queue_entry_id,
        queue_entry_state=queue_entry_state,
        decision_log_result_state=decision_log_result_state,
        match_status=match_status,
        severity=severity,
        reason_codes=reason_codes,
        rationale=rationale,
        generated_at=NOW,
    )


def _issue(
    *,
    issue_id: str = "issue-1",
    issue_type: str = "missing_decision_log_ref",
    severity: str = "advisory",
    reason_codes: tuple[str, ...] = ("missing_decision_log_ref",),
    queue_entry_id: str = "qe-2",
    title: str = "Missing decision log ref",
    description: str = "Queue entry expects a decision.",
) -> HumanReviewDecisionLogConsistencyIssue:
    return HumanReviewDecisionLogConsistencyIssue(
        issue_id=issue_id,
        issue_type=issue_type,
        severity=severity,
        reason_codes=reason_codes,
        queue_entry_id=queue_entry_id,
        title=title,
        description=description,
        generated_at=NOW,
    )


def _sample_report() -> HumanReviewDecisionLogConsistencyReport:
    cr1 = _cross_reference(
        cross_reference_id="cr-1",
        queue_entry_id="qe-1",
        decision_log_queue_entry_id="qe-1",
        queue_entry_state="open",
        decision_log_result_state="open",
        match_status="matched",
        severity="info",
        rationale="Queue entry and decision log ref are matched.",
    )
    cr2 = _cross_reference(
        cross_reference_id="cr-2",
        queue_entry_id="qe-2",
        decision_log_queue_entry_id="",
        queue_entry_state="open",
        decision_log_result_state="",
        match_status="orphan_queue",
        severity="info",
        rationale="Queue entry has no corresponding decision log ref.",
    )
    issue = _issue(
        issue_id="issue-1",
        issue_type="missing_decision_log_ref",
        severity="advisory",
        reason_codes=("missing_decision_log_ref",),
        queue_entry_id="qe-2",
        title="Missing decision log ref",
        description="Queue entry 'qe-2' expects a decision but has no corresponding decision log ref.",
    )
    return HumanReviewDecisionLogConsistencyReport(
        report_id="r-degraded",
        generated_at=NOW,
        state=HumanReviewDecisionLogConsistencyState.DEGRADED,
        project_version="0.42.0-dev",
        queue_report_id="qr-1",
        decision_log_report_id="dlr-1",
        cross_references=(cr1, cr2),
        issues=(issue,),
        data_quality=HumanReviewDecisionLogConsistencyDataQuality(
            total_queue_entries=2,
            total_decision_log_refs=1,
            matched_refs=1,
            orphan_queue_entries=1,
            advisory_issues=1,
        ),
        safety_flags=HumanReviewDecisionLogConsistencySafetyFlags(),
        reason_codes=(
            HumanReviewDecisionLogConsistencyReasonCode.CONSISTENCY_DEGRADED,
            HumanReviewDecisionLogConsistencyReasonCode.MISSING_DECISION_LOG_REF,
        ),
        safety_notice=SAFETY_NOTICE,
        notes="Advisory consistency issues detected; review recommended.",
        metadata={"source": "unit-test", "run": "a"},
    )


def _ok_report() -> HumanReviewDecisionLogConsistencyReport:
    return HumanReviewDecisionLogConsistencyReport(
        report_id="r-ok",
        generated_at=NOW,
        state=HumanReviewDecisionLogConsistencyState.OK,
        project_version="0.42.0-dev",
        queue_report_id="qr-ok",
        decision_log_report_id="dlr-ok",
        cross_references=(
            _cross_reference(
                cross_reference_id="cr-ok",
                queue_entry_id="qe-ok",
                decision_log_queue_entry_id="qe-ok",
                match_status="matched",
                rationale="Queue entry and decision log ref are matched.",
            ),
        ),
        data_quality=HumanReviewDecisionLogConsistencyDataQuality(
            total_queue_entries=1,
            total_decision_log_refs=1,
            matched_refs=1,
        ),
        safety_flags=HumanReviewDecisionLogConsistencySafetyFlags(),
        reason_codes=(HumanReviewDecisionLogConsistencyReasonCode.OK,),
        safety_notice=SAFETY_NOTICE,
        notes="No cross-artifact consistency issues detected.",
    )


def _blocked_report() -> HumanReviewDecisionLogConsistencyReport:
    return HumanReviewDecisionLogConsistencyReport(
        report_id="r-blocked",
        generated_at=NOW,
        state=HumanReviewDecisionLogConsistencyState.BLOCKED,
        project_version="0.42.0-dev",
        queue_report_id="qr-blocked",
        decision_log_report_id="dlr-blocked",
        data_quality=HumanReviewDecisionLogConsistencyDataQuality(
            unsafe_content_count=1,
        ),
        safety_flags=HumanReviewDecisionLogConsistencySafetyFlags(
            is_safe=False,
            has_unsafe_content=True,
        ),
        reason_codes=(HumanReviewDecisionLogConsistencyReasonCode.SAFETY_BLOCKED,),
        safety_notice=SAFETY_NOTICE,
        notes="Report blocked due to unsafe content in caller-provided consistency input.",
    )


def _not_applicable_report() -> HumanReviewDecisionLogConsistencyReport:
    return HumanReviewDecisionLogConsistencyReport(
        report_id="r-na",
        generated_at=NOW,
        state=HumanReviewDecisionLogConsistencyState.NOT_APPLICABLE,
        project_version="0.42.0-dev",
        queue_report_id="qr-na",
        decision_log_report_id="dlr-na",
        data_quality=HumanReviewDecisionLogConsistencyDataQuality(),
        safety_flags=HumanReviewDecisionLogConsistencySafetyFlags(),
        reason_codes=(HumanReviewDecisionLogConsistencyReasonCode.NOT_APPLICABLE,),
        safety_notice=SAFETY_NOTICE,
        notes="No queue entries or decision log refs provided; consistency check is not applicable.",
    )


# ---------------------------------------------------------------------------
# Public exports
# ---------------------------------------------------------------------------


def test_writer_functions_exported() -> None:
    assert human_review_decision_log_consistency_report_to_dict is not None
    assert human_review_decision_log_consistency_report_to_json_text is not None
    assert human_review_decision_log_consistency_report_to_markdown_text is not None


# ---------------------------------------------------------------------------
# Dict shape
# ---------------------------------------------------------------------------


def test_dict_includes_all_required_top_level_keys() -> None:
    report = _sample_report()
    data = human_review_decision_log_consistency_report_to_dict(report)
    required = {
        "report_id",
        "generated_at",
        "project_version",
        "state",
        "safety_notice",
        "notes",
        "cross_references",
        "issues",
        "data_quality",
        "safety_flags",
        "metadata",
        "reason_codes",
        "queue_report_id",
        "decision_log_report_id",
    }
    assert required <= data.keys()


def test_dict_safety_notice_is_first_and_generated_at_is_second() -> None:
    report = _sample_report()
    data = human_review_decision_log_consistency_report_to_dict(report)
    keys = list(data.keys())
    assert keys[0] == "safety_notice"
    assert keys[1] == "generated_at"


def test_dict_serializes_enums_as_values() -> None:
    report = _sample_report()
    data = human_review_decision_log_consistency_report_to_dict(report)
    assert data["state"] == report.state.value
    assert isinstance(data["state"], str)
    assert data["reason_codes"] == [rc.value for rc in report.reason_codes]


def test_dict_metadata_sorted_and_stable() -> None:
    report = _sample_report()
    data = human_review_decision_log_consistency_report_to_dict(report)
    assert isinstance(data["metadata"], dict)
    assert list(data["metadata"].keys()) == sorted(data["metadata"].keys())


def test_dict_no_mutation() -> None:
    report = _sample_report()
    original = report
    _ = human_review_decision_log_consistency_report_to_dict(report)
    assert report == original


# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------


def test_json_text_deterministic_and_parseable() -> None:
    report = _sample_report()
    text1 = human_review_decision_log_consistency_report_to_json_text(report)
    text2 = human_review_decision_log_consistency_report_to_json_text(report)
    assert text1 == text2
    parsed = json.loads(text1)
    assert parsed["report_id"] == report.report_id


def test_json_text_ends_with_newline() -> None:
    report = _sample_report()
    text = human_review_decision_log_consistency_report_to_json_text(report)
    assert text.endswith("\n")


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------


def test_markdown_starts_with_h1() -> None:
    report = _sample_report()
    text = human_review_decision_log_consistency_report_to_markdown_text(report)
    assert text.startswith("# Human Review Decision Log Cross-Artifact Consistency")


def test_markdown_has_immediate_safety_notice() -> None:
    report = _sample_report()
    text = human_review_decision_log_consistency_report_to_markdown_text(report)
    first_lines = "\n".join(text.split("\n")[:10]).lower()
    assert "audit-only" in first_lines or "research-only" in first_lines or "human-audit" in first_lines


def test_markdown_contains_required_disclaimers() -> None:
    report = _sample_report()
    text = human_review_decision_log_consistency_report_to_markdown_text(report).lower()
    assert "approval" in text
    assert "certification" in text
    assert "production readiness" in text
    assert "deployment readiness" in text
    assert "trading readiness" in text
    assert "recommendation" in text
    assert "suitability assessment" in text
    assert "signal" in text
    assert "executable remediation plan" in text


def test_markdown_includes_required_sections() -> None:
    report = _sample_report()
    text = human_review_decision_log_consistency_report_to_markdown_text(report)
    assert "## Summary" in text
    assert "## Cross References" in text
    assert "## Issues" in text
    assert "## Data Quality" in text
    assert "## Safety Flags" in text
    assert "## Opaque Reference Notice" in text
    assert "## Research Artifact Notice" in text


def test_markdown_no_executable_or_assignment_language() -> None:
    report = _sample_report()
    text = human_review_decision_log_consistency_report_to_markdown_text(report).lower()
    # Subset of forbidden terms that do not appear in the required safety notice.
    forbidden = [
        "deploy immediately",
        "execute now",
        "run this command",
        "apply patch",
        "go live",
        "push to production",
        "place order",
        "execute order",
        "buy signal",
        "sell signal",
        "hold signal",
        "create ticket",
        "open jira",
        "automated remediation",
    ]
    for term in forbidden:
        assert term not in text, f"forbidden term in markdown: {term}"


def test_markdown_empty_collections_render_none() -> None:
    report = _not_applicable_report()
    text = human_review_decision_log_consistency_report_to_markdown_text(report)
    assert "## Cross References" in text
    assert "## Issues" in text
    assert "| _none_ |" in text


def test_markdown_empty_reason_codes_omits_section() -> None:
    report = HumanReviewDecisionLogConsistencyReport(
        report_id="r-empty-rc",
        generated_at=NOW,
        state=HumanReviewDecisionLogConsistencyState.NOT_APPLICABLE,
        reason_codes=(),
    )
    text = human_review_decision_log_consistency_report_to_markdown_text(report)
    assert "## Reason Codes" not in text


# ---------------------------------------------------------------------------
# State-specific serialization
# ---------------------------------------------------------------------------


def test_ok_report_serializes() -> None:
    report = _ok_report()
    data = human_review_decision_log_consistency_report_to_dict(report)
    assert data["state"] == "ok"
    text = human_review_decision_log_consistency_report_to_markdown_text(report)
    assert "- **state:** ok" in text


def test_degraded_report_serializes_with_orphan_and_mismatch() -> None:
    cr_mismatch = _cross_reference(
        cross_reference_id="cr-mismatch",
        queue_entry_id="qe-mismatch",
        decision_log_queue_entry_id="qe-mismatch",
        queue_entry_state="open",
        decision_log_result_state="closed",
        match_status="mismatched",
        severity="advisory",
        reason_codes=("mismatched_queue_state",),
        rationale="State mismatch.",
    )
    issue_mismatch = _issue(
        issue_id="issue-mismatch",
        issue_type="mismatched_queue_state",
        severity="advisory",
        reason_codes=("mismatched_queue_state",),
        queue_entry_id="qe-mismatch",
        title="Mismatched queue state",
        description="States do not match.",
    )
    report = HumanReviewDecisionLogConsistencyReport(
        report_id="r-mismatch",
        generated_at=NOW,
        state=HumanReviewDecisionLogConsistencyState.DEGRADED,
        project_version="0.42.0-dev",
        queue_report_id="qr-1",
        decision_log_report_id="dlr-1",
        cross_references=(cr_mismatch,),
        issues=(issue_mismatch,),
        data_quality=HumanReviewDecisionLogConsistencyDataQuality(
            mismatched_refs=1,
            advisory_issues=1,
        ),
        safety_flags=HumanReviewDecisionLogConsistencySafetyFlags(),
        reason_codes=(
            HumanReviewDecisionLogConsistencyReasonCode.CONSISTENCY_DEGRADED,
            HumanReviewDecisionLogConsistencyReasonCode.MISMATCHED_QUEUE_STATE,
        ),
        safety_notice=SAFETY_NOTICE,
        notes="Advisory consistency issues detected.",
    )
    data = human_review_decision_log_consistency_report_to_dict(report)
    assert data["state"] == "degraded"
    text = human_review_decision_log_consistency_report_to_markdown_text(report)
    assert "mismatched" in text.lower()


def test_blocked_report_serializes_safely() -> None:
    report = _blocked_report()
    data = human_review_decision_log_consistency_report_to_dict(report)
    assert data["state"] == "blocked"
    assert data["safety_flags"]["has_unsafe_content"] is True
    assert data["safety_flags"]["is_safe"] is False
    text = human_review_decision_log_consistency_report_to_markdown_text(report)
    assert text.startswith("# Human Review Decision Log Cross-Artifact Consistency")
    assert "audit-only" in text.lower()


def test_not_applicable_report_serializes() -> None:
    report = _not_applicable_report()
    data = human_review_decision_log_consistency_report_to_dict(report)
    assert data["state"] == "not_applicable"
    assert data["reason_codes"] == ["not_applicable"]
    text = human_review_decision_log_consistency_report_to_markdown_text(report)
    assert "- **state:** not_applicable" in text


# ---------------------------------------------------------------------------
# Opaque refs, determinism, no I/O
# ---------------------------------------------------------------------------


def test_opaque_refs_serialized_as_strings_only() -> None:
    report = _sample_report()
    text = human_review_decision_log_consistency_report_to_markdown_text(report)
    assert "qe-1" in text
    assert "dlr-1" in text
    assert "qr-1" in text
    data = human_review_decision_log_consistency_report_to_dict(report)
    assert isinstance(data["report_id"], str)
    assert isinstance(data["queue_report_id"], str)
    assert isinstance(data["decision_log_report_id"], str)


def test_deterministic_outputs_from_same_report() -> None:
    report = _sample_report()
    assert (
        human_review_decision_log_consistency_report_to_dict(report)
        == human_review_decision_log_consistency_report_to_dict(report)
    )
    assert (
        human_review_decision_log_consistency_report_to_json_text(report)
        == human_review_decision_log_consistency_report_to_json_text(report)
    )
    assert (
        human_review_decision_log_consistency_report_to_markdown_text(report)
        == human_review_decision_log_consistency_report_to_markdown_text(report)
    )


def test_no_filesystem_io(monkeypatch: pytest.MonkeyPatch) -> None:
    def _unexpected_open(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("unexpected open call")

    monkeypatch.setattr("builtins.open", _unexpected_open)
    report = _sample_report()
    human_review_decision_log_consistency_report_to_dict(report)
    human_review_decision_log_consistency_report_to_json_text(report)
    human_review_decision_log_consistency_report_to_markdown_text(report)


def test_no_network_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    def _unexpected_urlopen(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("unexpected network call")

    monkeypatch.setattr("urllib.request.urlopen", _unexpected_urlopen)
    report = _sample_report()
    human_review_decision_log_consistency_report_to_dict(report)
    human_review_decision_log_consistency_report_to_json_text(report)
    human_review_decision_log_consistency_report_to_markdown_text(report)


# ---------------------------------------------------------------------------
# Forbidden-term safety guard
# ---------------------------------------------------------------------------


def test_markdown_forbidden_terms_guarded() -> None:
    """Safety notice may contain required boilerplate; this test guards new text."""
    report = _sample_report()
    text = human_review_decision_log_consistency_report_to_markdown_text(report).lower()
    # Safety notice contains "task assignment", "task completion", and
    # "executable remediation plan"; exclude them from the guard.
    exclude = {
        "task assignment",
        "task completion",
        "executable remediation plan",
    }
    for term in FORBIDDEN_HUMAN_REVIEW_DECISION_LOG_CONSISTENCY_TERMS:
        if term in exclude:
            continue
        assert term not in text, f"forbidden term in markdown body: {term!r}"
