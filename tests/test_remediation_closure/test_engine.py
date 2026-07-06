"""Tests for hunter.remediation_closure.engine."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from hunter.remediation_closure import (
    FORBIDDEN_REMEDIATION_CLOSURE_TERMS,
    RemediationClosureBacklogItemRef,
    RemediationClosureConfig,
    RemediationClosureDeclaration,
    RemediationClosureEligibilityState,
    RemediationClosureEvidenceSummary,
    RemediationClosureInput,
    RemediationClosureIssueType,
    RemediationClosureLink,
    RemediationClosureReasonCode,
    RemediationClosureRecordState,
    RemediationClosureReviewOutcome,
    RemediationClosureReviewRecord,
    RemediationClosureSeverity,
    RemediationClosureState,
    build_remediation_closure_report,
)

NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
OLD = NOW - timedelta(days=31)


def _backlog_item(item_id: str, state: str = "open") -> RemediationClosureBacklogItemRef:
    return RemediationClosureBacklogItemRef(
        backlog_item_id=item_id,
        item_state=state,
    )


def _evidence_summary(
    evidence_summary_id: str,
    backlog_item_id: str,
    coverage_state: str = "missing",
    generated_at: datetime | None = None,
) -> RemediationClosureEvidenceSummary:
    return RemediationClosureEvidenceSummary(
        evidence_summary_id=evidence_summary_id,
        backlog_item_id=backlog_item_id,
        coverage_state=coverage_state,
        generated_at=generated_at,
    )


def _closure(
    closure_id: str,
    backlog_item_id: str,
    evidence_summary_id: str = "",
    declared_by: str = "",
    reviewed_by: str = "",
    closed_at: datetime | None = None,
    rationale: str = "",
    evidence_link: str = "",
    generated_at: datetime | None = None,
) -> RemediationClosureDeclaration:
    return RemediationClosureDeclaration(
        closure_id=closure_id,
        backlog_item_id=backlog_item_id,
        evidence_summary_id=evidence_summary_id,
        declared_by=declared_by,
        reviewed_by=reviewed_by,
        closed_at=closed_at,
        rationale=rationale,
        evidence_link=evidence_link,
        generated_at=generated_at,
    )


def _review(
    review_id: str,
    closure_id: str,
    outcome: str = "accepted",
    generated_at: datetime | None = None,
) -> RemediationClosureReviewRecord:
    return RemediationClosureReviewRecord(
        review_id=review_id,
        closure_id=closure_id,
        outcome=outcome,
        generated_at=generated_at,
    )


def _link(
    link_id: str,
    closure_id: str,
    evidence_summary_id: str,
    backlog_item_id: str,
) -> RemediationClosureLink:
    return RemediationClosureLink(
        link_id=link_id,
        closure_id=closure_id,
        evidence_summary_id=evidence_summary_id,
        backlog_item_id=backlog_item_id,
    )


# ---------------------------------------------------------------------------
# Empty input and basic state
# ---------------------------------------------------------------------------


def test_empty_input_not_applicable() -> None:
    inp = RemediationClosureInput()
    report = build_remediation_closure_report(inp)
    assert report.state is RemediationClosureState.NOT_APPLICABLE
    assert report.issues == ()
    assert report.closure_results == ()
    assert RemediationClosureReasonCode.NOT_APPLICABLE in report.reason_codes


def test_empty_input_with_generated_at() -> None:
    inp = RemediationClosureInput(generated_at=NOW)
    report = build_remediation_closure_report(inp)
    assert report.state is RemediationClosureState.NOT_APPLICABLE
    assert report.generated_at == NOW


def test_no_issues_closed_recorded() -> None:
    ref = _backlog_item("b1", "acknowledged")
    es = _evidence_summary("es1", "b1", "covered")
    closure = _closure("c1", "b1", "es1")
    review = _review("r1", "c1", "accepted")
    inp = RemediationClosureInput(
        backlog_item_refs=(ref,),
        evidence_summaries=(es,),
        closure_declarations=(closure,),
        review_records=(review,),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert report.state is RemediationClosureState.OK
    assert report.closure_results[0].record_state is RemediationClosureRecordState.CLOSED_RECORDED
    assert report.closure_results[0].eligibility_state is RemediationClosureEligibilityState.ELIGIBLE


# ---------------------------------------------------------------------------
# Deterministic IDs and ordering
# ---------------------------------------------------------------------------


def test_deterministic_report_id() -> None:
    ref = _backlog_item("b1", "open")
    es = _evidence_summary("es1", "b1", "covered")
    closure = _closure("c1", "b1", "es1")
    review = _review("r1", "c1", "accepted")
    inp1 = RemediationClosureInput(
        backlog_item_refs=(ref,),
        evidence_summaries=(es,),
        closure_declarations=(closure,),
        review_records=(review,),
        generated_at=NOW,
    )
    inp2 = RemediationClosureInput(
        backlog_item_refs=(ref,),
        evidence_summaries=(es,),
        closure_declarations=(closure,),
        review_records=(review,),
        generated_at=NOW,
    )
    assert build_remediation_closure_report(inp1).report_id == build_remediation_closure_report(inp2).report_id


def test_report_id_changes_with_input() -> None:
    inp1 = RemediationClosureInput(
        backlog_item_refs=(_backlog_item("b1"),),
        generated_at=NOW,
    )
    inp2 = RemediationClosureInput(
        backlog_item_refs=(_backlog_item("b2"),),
        generated_at=NOW,
    )
    assert build_remediation_closure_report(inp1).report_id != build_remediation_closure_report(inp2).report_id


def test_collections_copied_and_sorted() -> None:
    r2 = _backlog_item("b2")
    r1 = _backlog_item("b1")
    es2 = _evidence_summary("es2", "b1")
    es1 = _evidence_summary("es1", "b2")
    c2 = _closure("c2", "b1")
    c1 = _closure("c1", "b2")
    rev2 = _review("r2", "c2")
    rev1 = _review("r1", "c1")
    l2 = _link("l2", "c2", "es2", "b1")
    l1 = _link("l1", "c1", "es1", "b2")
    inp = RemediationClosureInput(
        backlog_item_refs=(r2, r1),
        evidence_summaries=(es2, es1),
        closure_declarations=(c2, c1),
        review_records=(rev2, rev1),
        links=(l2, l1),
    )
    report = build_remediation_closure_report(inp)
    assert [r.backlog_item_id for r in report.backlog_item_refs] == ["b1", "b2"]
    assert [s.evidence_summary_id for s in report.evidence_summaries] == ["es1", "es2"]
    assert [d.closure_id for d in report.closure_declarations] == ["c1", "c2"]
    assert [r.review_id for r in report.review_records] == ["r1", "r2"]
    assert [l.link_id for l in report.links] == ["l1", "l2"]


# ---------------------------------------------------------------------------
# Duplicate IDs fail closed
# ---------------------------------------------------------------------------


def test_duplicate_backlog_item_ids_blocked() -> None:
    inp = RemediationClosureInput(
        backlog_item_refs=(_backlog_item("b1"), _backlog_item("b1")),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert report.state is RemediationClosureState.BLOCKED
    assert RemediationClosureReasonCode.DUPLICATE_ID in report.reason_codes


def test_duplicate_evidence_summary_ids_blocked() -> None:
    inp = RemediationClosureInput(
        evidence_summaries=(_evidence_summary("es1", "b1"), _evidence_summary("es1", "b1")),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert report.state is RemediationClosureState.BLOCKED
    assert RemediationClosureReasonCode.DUPLICATE_ID in report.reason_codes


def test_duplicate_closure_ids_blocked() -> None:
    inp = RemediationClosureInput(
        closure_declarations=(_closure("c1", "b1"), _closure("c1", "b2")),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert report.state is RemediationClosureState.BLOCKED


def test_duplicate_review_ids_blocked() -> None:
    inp = RemediationClosureInput(
        closure_declarations=(_closure("c1", "b1"), _closure("c2", "b2")),
        review_records=(_review("r1", "c1"), _review("r1", "c2")),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert report.state is RemediationClosureState.BLOCKED


def test_duplicate_link_ids_blocked() -> None:
    inp = RemediationClosureInput(
        links=(_link("l1", "c1", "es1", "b1"), _link("l1", "c2", "es2", "b2")),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert report.state is RemediationClosureState.BLOCKED


# ---------------------------------------------------------------------------
# Orphan detection
# ---------------------------------------------------------------------------


def test_orphan_evidence_detected() -> None:
    inp = RemediationClosureInput(
        backlog_item_refs=(_backlog_item("b1"),),
        evidence_summaries=(_evidence_summary("es1", "b2"),),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert any(issue.issue_type is RemediationClosureIssueType.ORPHAN_EVIDENCE for issue in report.issues)
    assert report.data_quality.orphan_evidence_count == 1


def test_orphan_closure_detected() -> None:
    inp = RemediationClosureInput(
        backlog_item_refs=(_backlog_item("b1"),),
        closure_declarations=(_closure("c1", "b2"),),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert any(issue.issue_type is RemediationClosureIssueType.ORPHAN_CLOSURE for issue in report.issues)
    assert report.data_quality.orphan_closure_count == 1


def test_orphan_review_detected() -> None:
    inp = RemediationClosureInput(
        closure_declarations=(_closure("c1", "b1"),),
        review_records=(_review("r1", "c2"),),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert any(issue.issue_type is RemediationClosureIssueType.ORPHAN_REVIEW for issue in report.issues)


def test_orphan_link_detected() -> None:
    inp = RemediationClosureInput(
        backlog_item_refs=(_backlog_item("b1"),),
        evidence_summaries=(_evidence_summary("es1", "b1"),),
        closure_declarations=(_closure("c1", "b1"),),
        links=(_link("l1", "c1", "es1", "b2"),),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert any(issue.issue_type is RemediationClosureIssueType.ORPHAN_LINK for issue in report.issues)


# ---------------------------------------------------------------------------
# Conflicting closures and reviews
# ---------------------------------------------------------------------------


def test_conflicting_closures_detected() -> None:
    inp = RemediationClosureInput(
        backlog_item_refs=(_backlog_item("b1"),),
        closure_declarations=(
            _closure("c1", "b1", "es1"),
            _closure("c2", "b1", "es2"),
        ),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert any(issue.issue_type is RemediationClosureIssueType.CONFLICTING_CLOSURE for issue in report.issues)
    assert report.state is RemediationClosureState.BLOCKED


def test_conflicting_reviews_detected() -> None:
    inp = RemediationClosureInput(
        backlog_item_refs=(_backlog_item("b1"),),
        closure_declarations=(_closure("c1", "b1"),),
        review_records=(
            _review("r1", "c1", "accepted"),
            _review("r2", "c1", "rejected"),
        ),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert any(issue.issue_type is RemediationClosureIssueType.CONFLICTING_REVIEW for issue in report.issues)
    assert report.state is RemediationClosureState.BLOCKED


# ---------------------------------------------------------------------------
# Stale detection
# ---------------------------------------------------------------------------


def test_stale_evidence_detected() -> None:
    inp = RemediationClosureInput(
        backlog_item_refs=(_backlog_item("b1"),),
        evidence_summaries=(
            RemediationClosureEvidenceSummary(
                evidence_summary_id="es1",
                backlog_item_id="b1",
                coverage_state="covered",
                generated_at=OLD,
            ),
        ),
        closure_declarations=(_closure("c1", "b1", "es1"),),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert any(issue.issue_type is RemediationClosureIssueType.STALE_EVIDENCE for issue in report.issues)


def test_stale_closure_detected() -> None:
    inp = RemediationClosureInput(
        backlog_item_refs=(_backlog_item("b1"),),
        closure_declarations=(
            RemediationClosureDeclaration(
                closure_id="c1",
                backlog_item_id="b1",
                generated_at=OLD,
            ),
        ),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert any(issue.issue_type is RemediationClosureIssueType.STALE_CLOSURE for issue in report.issues)


def test_stale_review_detected() -> None:
    inp = RemediationClosureInput(
        backlog_item_refs=(_backlog_item("b1"),),
        closure_declarations=(_closure("c1", "b1"),),
        review_records=(
            RemediationClosureReviewRecord(
                review_id="r1",
                closure_id="c1",
                outcome="accepted",
                generated_at=OLD,
            ),
        ),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert any(issue.issue_type is RemediationClosureIssueType.STALE_REVIEW for issue in report.issues)


# ---------------------------------------------------------------------------
# Missing evidence / review / metadata
# ---------------------------------------------------------------------------


def test_missing_evidence_when_required() -> None:
    ref = _backlog_item("b1", "acknowledged")
    es = _evidence_summary("es1", "b1", "partial")
    closure = _closure("c1", "b1", "es1")
    inp = RemediationClosureInput(
        backlog_item_refs=(ref,),
        evidence_summaries=(es,),
        closure_declarations=(closure,),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    missing = [issue for issue in report.issues if issue.issue_type is RemediationClosureIssueType.MISSING_EVIDENCE]
    assert missing
    assert all(issue.severity is RemediationClosureSeverity.BLOCKING for issue in missing)
    assert report.state is RemediationClosureState.BLOCKED
    assert report.closure_results[0].record_state is RemediationClosureRecordState.BLOCKED


def test_missing_evidence_when_not_required_is_non_blocking() -> None:
    ref = _backlog_item("b1", "acknowledged")
    es = _evidence_summary("es1", "b1", "partial")
    closure = _closure("c1", "b1", "es1")
    inp = RemediationClosureInput(
        backlog_item_refs=(ref,),
        evidence_summaries=(es,),
        closure_declarations=(closure,),
        config=RemediationClosureConfig(require_evidence_for_closure=False),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    missing_issues = [issue for issue in report.issues if issue.issue_type is RemediationClosureIssueType.MISSING_EVIDENCE]
    assert all(issue.severity is RemediationClosureSeverity.INFO for issue in missing_issues)
    assert report.state is RemediationClosureState.OK


def test_missing_review_detected() -> None:
    ref = _backlog_item("b1", "acknowledged")
    es = _evidence_summary("es1", "b1", "covered")
    closure = _closure("c1", "b1", "es1")
    inp = RemediationClosureInput(
        backlog_item_refs=(ref,),
        evidence_summaries=(es,),
        closure_declarations=(closure,),
        config=RemediationClosureConfig(require_review=True),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert any(issue.issue_type is RemediationClosureIssueType.MISSING_REVIEW for issue in report.issues)


def test_missing_closure_metadata_detected() -> None:
    ref = _backlog_item("b1", "acknowledged")
    es = _evidence_summary("es1", "b1", "covered")
    closure = _closure("c1", "b1", "es1")
    inp = RemediationClosureInput(
        backlog_item_refs=(ref,),
        evidence_summaries=(es,),
        closure_declarations=(closure,),
        config=RemediationClosureConfig(require_closure_metadata=True),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert any(issue.issue_type is RemediationClosureIssueType.MISSING_CLOSURE_METADATA for issue in report.issues)


# ---------------------------------------------------------------------------
# Closure review outcomes
# ---------------------------------------------------------------------------


def test_rejected_review_detected() -> None:
    ref = _backlog_item("b1", "acknowledged")
    es = _evidence_summary("es1", "b1", "covered")
    closure = _closure("c1", "b1", "es1")
    review = _review("r1", "c1", "rejected")
    inp = RemediationClosureInput(
        backlog_item_refs=(ref,),
        evidence_summaries=(es,),
        closure_declarations=(closure,),
        review_records=(review,),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert any(issue.issue_type is RemediationClosureIssueType.REJECTED_REVIEW for issue in report.issues)
    assert report.closure_results[0].record_state is RemediationClosureRecordState.REJECTED


def test_pending_review_detected() -> None:
    ref = _backlog_item("b1", "acknowledged")
    es = _evidence_summary("es1", "b1", "covered")
    closure = _closure("c1", "b1", "es1")
    review = _review("r1", "c1", "pending")
    inp = RemediationClosureInput(
        backlog_item_refs=(ref,),
        evidence_summaries=(es,),
        closure_declarations=(closure,),
        review_records=(review,),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert any(issue.issue_type is RemediationClosureIssueType.PENDING_REVIEW for issue in report.issues)
    assert report.closure_results[0].record_state is RemediationClosureRecordState.PENDING_REVIEW


def test_disputed_review_detected() -> None:
    ref = _backlog_item("b1", "acknowledged")
    es = _evidence_summary("es1", "b1", "covered")
    closure = _closure("c1", "b1", "es1")
    review = _review("r1", "c1", "disputed")
    inp = RemediationClosureInput(
        backlog_item_refs=(ref,),
        evidence_summaries=(es,),
        closure_declarations=(closure,),
        review_records=(review,),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert any(issue.issue_type is RemediationClosureIssueType.DISPUTED_REVIEW for issue in report.issues)
    assert report.closure_results[0].record_state is RemediationClosureRecordState.DISPUTED


# ---------------------------------------------------------------------------
# Backlog item state with closure declarations
# ---------------------------------------------------------------------------


def test_blocked_backlog_item_with_closure_emits_blocking() -> None:
    ref = _backlog_item("b1", "blocked")
    es = _evidence_summary("es1", "b1", "covered")
    closure = _closure("c1", "b1", "es1")
    review = _review("r1", "c1", "accepted")
    inp = RemediationClosureInput(
        backlog_item_refs=(ref,),
        evidence_summaries=(es,),
        closure_declarations=(closure,),
        review_records=(review,),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    blocking = [issue for issue in report.issues if issue.issue_type is RemediationClosureIssueType.BLOCKED_BACKLOG_ITEM]
    assert blocking
    assert all(issue.severity is RemediationClosureSeverity.BLOCKING for issue in blocking)
    assert report.state is RemediationClosureState.BLOCKED


def test_open_backlog_item_with_closure_emits_blocking() -> None:
    ref = _backlog_item("b1", "open")
    es = _evidence_summary("es1", "b1", "covered")
    closure = _closure("c1", "b1", "es1")
    review = _review("r1", "c1", "accepted")
    inp = RemediationClosureInput(
        backlog_item_refs=(ref,),
        evidence_summaries=(es,),
        closure_declarations=(closure,),
        review_records=(review,),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    blocking = [issue for issue in report.issues if issue.issue_type is RemediationClosureIssueType.OPEN_BACKLOG_ITEM]
    assert blocking
    assert all(issue.severity is RemediationClosureSeverity.BLOCKING for issue in blocking)
    assert report.state is RemediationClosureState.BLOCKED


def test_conflicting_backlog_item_with_closure_emits_blocking() -> None:
    ref = _backlog_item("b1", "conflicting")
    es = _evidence_summary("es1", "b1", "covered")
    closure = _closure("c1", "b1", "es1")
    review = _review("r1", "c1", "accepted")
    inp = RemediationClosureInput(
        backlog_item_refs=(ref,),
        evidence_summaries=(es,),
        closure_declarations=(closure,),
        review_records=(review,),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    blocking = [issue for issue in report.issues if issue.issue_type is RemediationClosureIssueType.CONFLICTING_BACKLOG_ITEM]
    assert blocking
    assert all(issue.severity is RemediationClosureSeverity.BLOCKING for issue in blocking)
    assert report.state is RemediationClosureState.BLOCKED


def test_acknowledged_backlog_item_with_closure_emits_info() -> None:
    ref = _backlog_item("b1", "acknowledged")
    es = _evidence_summary("es1", "b1", "covered")
    closure = _closure("c1", "b1", "es1")
    review = _review("r1", "c1", "accepted")
    inp = RemediationClosureInput(
        backlog_item_refs=(ref,),
        evidence_summaries=(es,),
        closure_declarations=(closure,),
        review_records=(review,),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert any(issue.issue_type is RemediationClosureIssueType.ACKNOWLEDGED_BACKLOG_ITEM for issue in report.issues)
    assert report.state is RemediationClosureState.OK


def test_deferred_backlog_item_with_closure_emits_info() -> None:
    ref = _backlog_item("b1", "deferred")
    es = _evidence_summary("es1", "b1", "covered")
    closure = _closure("c1", "b1", "es1")
    review = _review("r1", "c1", "accepted")
    inp = RemediationClosureInput(
        backlog_item_refs=(ref,),
        evidence_summaries=(es,),
        closure_declarations=(closure,),
        review_records=(review,),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert any(issue.issue_type is RemediationClosureIssueType.DEFERRED_BACKLOG_ITEM for issue in report.issues)
    assert report.state is RemediationClosureState.OK


def test_not_applicable_backlog_item_with_closure_emits_info() -> None:
    ref = _backlog_item("b1", "not_applicable")
    es = _evidence_summary("es1", "b1", "covered")
    closure = _closure("c1", "b1", "es1")
    review = _review("r1", "c1", "accepted")
    inp = RemediationClosureInput(
        backlog_item_refs=(ref,),
        evidence_summaries=(es,),
        closure_declarations=(closure,),
        review_records=(review,),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert any(issue.issue_type is RemediationClosureIssueType.NOT_APPLICABLE_BACKLOG_ITEM for issue in report.issues)
    assert report.closure_results[0].record_state is RemediationClosureRecordState.NOT_APPLICABLE


def test_backlog_item_without_closure_does_not_emit_state_issue() -> None:
    ref = _backlog_item("b1", "blocked")
    inp = RemediationClosureInput(
        backlog_item_refs=(ref,),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert all(issue.issue_type is not RemediationClosureIssueType.BLOCKED_BACKLOG_ITEM for issue in report.issues)
    assert report.closure_results[0].record_state is RemediationClosureRecordState.NOT_APPLICABLE


# ---------------------------------------------------------------------------
# Closure precedence first-match-wins
# ---------------------------------------------------------------------------


def test_not_applicable_for_not_required_item_without_closure() -> None:
    inp = RemediationClosureInput(
        backlog_item_refs=(_backlog_item("b1"),),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert report.closure_results[0].record_state is RemediationClosureRecordState.NOT_APPLICABLE


def test_blocked_takes_precedence_over_rejected() -> None:
    ref = _backlog_item("b1", "blocked")
    es = _evidence_summary("es1", "b1", "covered")
    closure = _closure("c1", "b1", "es1")
    review = _review("r1", "c1", "rejected")
    inp = RemediationClosureInput(
        backlog_item_refs=(ref,),
        evidence_summaries=(es,),
        closure_declarations=(closure,),
        review_records=(review,),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert report.closure_results[0].record_state is RemediationClosureRecordState.BLOCKED


def test_disputed_takes_precedence_over_rejected() -> None:
    ref = _backlog_item("b1", "acknowledged")
    es = _evidence_summary("es1", "b1", "covered")
    closure = _closure("c1", "b1", "es1")
    review = _review("r1", "c1", "disputed")
    inp = RemediationClosureInput(
        backlog_item_refs=(ref,),
        evidence_summaries=(es,),
        closure_declarations=(closure,),
        review_records=(review,),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert report.closure_results[0].record_state is RemediationClosureRecordState.DISPUTED


def test_rejected_takes_precedence_over_stale() -> None:
    ref = _backlog_item("b1", "acknowledged")
    es = _evidence_summary("es1", "b1", "covered", generated_at=OLD)
    closure = _closure("c1", "b1", "es1", generated_at=OLD)
    review = _review("r1", "c1", "rejected", generated_at=OLD)
    inp = RemediationClosureInput(
        backlog_item_refs=(ref,),
        evidence_summaries=(es,),
        closure_declarations=(closure,),
        review_records=(review,),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert report.closure_results[0].record_state is RemediationClosureRecordState.REJECTED


def test_stale_result() -> None:
    ref = _backlog_item("b1", "acknowledged")
    es = _evidence_summary("es1", "b1", "covered", generated_at=OLD)
    closure = _closure("c1", "b1", "es1", generated_at=OLD)
    review = _review("r1", "c1", "accepted", generated_at=OLD)
    inp = RemediationClosureInput(
        backlog_item_refs=(ref,),
        evidence_summaries=(es,),
        closure_declarations=(closure,),
        review_records=(review,),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert report.closure_results[0].record_state is RemediationClosureRecordState.STALE


def test_partial_when_evidence_partial() -> None:
    ref = _backlog_item("b1", "acknowledged")
    es = _evidence_summary("es1", "b1", "partial")
    closure = _closure("c1", "b1", "es1")
    review = _review("r1", "c1", "accepted")
    inp = RemediationClosureInput(
        backlog_item_refs=(ref,),
        evidence_summaries=(es,),
        closure_declarations=(closure,),
        review_records=(review,),
        config=RemediationClosureConfig(require_evidence_for_closure=False),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert report.closure_results[0].record_state is RemediationClosureRecordState.PARTIAL


def test_closed_recorded_with_accepted_review() -> None:
    ref = _backlog_item("b1", "acknowledged")
    es = _evidence_summary("es1", "b1", "covered")
    closure = _closure("c1", "b1", "es1")
    review = _review("r1", "c1", "accepted")
    inp = RemediationClosureInput(
        backlog_item_refs=(ref,),
        evidence_summaries=(es,),
        closure_declarations=(closure,),
        review_records=(review,),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    result = report.closure_results[0]
    assert result.record_state is RemediationClosureRecordState.CLOSED_RECORDED
    assert result.review_outcome is RemediationClosureReviewOutcome.ACCEPTED


# ---------------------------------------------------------------------------
# Semantic duplicate closures
# ---------------------------------------------------------------------------


def test_duplicate_closure_content_produces_duplicate_result() -> None:
    ref = _backlog_item("b1", "acknowledged")
    es = _evidence_summary("es1", "b1", "covered")
    closure1 = _closure("c1", "b1", "es1", declared_by="alice", rationale="done")
    closure2 = _closure("c2", "b1", "es1", declared_by="alice", rationale="done")
    review1 = _review("r1", "c1", "accepted")
    review2 = _review("r2", "c2", "accepted")
    inp = RemediationClosureInput(
        backlog_item_refs=(ref,),
        evidence_summaries=(es,),
        closure_declarations=(closure1, closure2),
        review_records=(review1, review2),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert report.closure_results[0].record_state is RemediationClosureRecordState.DUPLICATE


def test_conflicting_closures_with_different_content_detected() -> None:
    ref = _backlog_item("b1", "acknowledged")
    es1 = _evidence_summary("es1", "b1", "covered")
    es2 = _evidence_summary("es2", "b1", "covered")
    closure1 = _closure("c1", "b1", "es1", declared_by="alice", rationale="done")
    closure2 = _closure("c2", "b1", "es2", declared_by="bob", rationale="done")
    review1 = _review("r1", "c1", "accepted")
    review2 = _review("r2", "c2", "accepted")
    inp = RemediationClosureInput(
        backlog_item_refs=(ref,),
        evidence_summaries=(es1, es2),
        closure_declarations=(closure1, closure2),
        review_records=(review1, review2),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert any(issue.issue_type is RemediationClosureIssueType.CONFLICTING_CLOSURE for issue in report.issues)
    assert report.closure_results[0].record_state is RemediationClosureRecordState.DISPUTED
    assert report.state is RemediationClosureState.BLOCKED


def test_duplicate_ids_still_fail_closed() -> None:
    ref = _backlog_item("b1", "acknowledged")
    es = _evidence_summary("es1", "b1", "covered")
    closure1 = _closure("c1", "b1", "es1")
    closure2 = _closure("c1", "b1", "es1")
    inp = RemediationClosureInput(
        backlog_item_refs=(ref,),
        evidence_summaries=(es,),
        closure_declarations=(closure1, closure2),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert report.state is RemediationClosureState.BLOCKED
    assert RemediationClosureReasonCode.DUPLICATE_ID in report.reason_codes


# ---------------------------------------------------------------------------
# Safety boundaries
# ---------------------------------------------------------------------------


def test_unsafe_content_blocks() -> None:
    inp = RemediationClosureInput(
        metadata={"key": b"bytes"},
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert report.state is RemediationClosureState.BLOCKED
    assert RemediationClosureReasonCode.UNSAFE_CONTENT in report.reason_codes
    assert report.safety_flags.has_unsafe_content is True
    assert report.safety_flags.is_safe is False


def test_forbidden_term_blocks() -> None:
    inp = RemediationClosureInput(
        backlog_item_refs=(
            RemediationClosureBacklogItemRef(
                backlog_item_id="b1",
                title="This is a buy signal",
            ),
        ),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert report.state is RemediationClosureState.BLOCKED
    assert RemediationClosureReasonCode.FORBIDDEN_TERM_PRESENT in report.reason_codes
    assert report.safety_flags.has_forbidden_terms is True


def test_forbidden_terms_config_can_disable() -> None:
    inp = RemediationClosureInput(
        backlog_item_refs=(
            RemediationClosureBacklogItemRef(
                backlog_item_id="b1",
                title="This is a buy signal",
                item_state="not_applicable",
            ),
        ),
        config=RemediationClosureConfig(
            forbid_action_terms=False,
            require_closure_for_all=False,
        ),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert report.state is RemediationClosureState.OK
    assert RemediationClosureReasonCode.FORBIDDEN_TERM_PRESENT not in report.reason_codes


def test_forbidden_term_helper_avoids_false_positives() -> None:
    """Benign phrases must not trigger forbidden-term matching."""
    from hunter.remediation_closure.models import _has_forbidden_term
    benign_phrases = [
        "pending approval from security team",
        "certification body",
        "no recommendation needed",
        "signal processing",
        "no signal detected",
    ]
    for phrase in benign_phrases:
        assert _has_forbidden_term(phrase, FORBIDDEN_REMEDIATION_CLOSURE_TERMS) is False


def test_forbidden_term_helper_matches_multi_word_phrases() -> None:
    from hunter.remediation_closure.models import _has_forbidden_term
    assert _has_forbidden_term("This is a buy signal", FORBIDDEN_REMEDIATION_CLOSURE_TERMS) is True
    assert _has_forbidden_term("Deploy immediately to production", FORBIDDEN_REMEDIATION_CLOSURE_TERMS) is True


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def test_strict_promotes_degraded_to_blocked() -> None:
    ref = _backlog_item("b1", "acknowledged")
    es = _evidence_summary("es1", "b1", "covered")
    closure = _closure("c1", "b1", "es1")
    base = RemediationClosureInput(
        backlog_item_refs=(ref,),
        evidence_summaries=(es,),
        closure_declarations=(closure,),
        config=RemediationClosureConfig(require_closure_metadata=True),
        generated_at=NOW,
    )
    strict = RemediationClosureInput(
        backlog_item_refs=(ref,),
        evidence_summaries=(es,),
        closure_declarations=(closure,),
        config=RemediationClosureConfig(strict=True, require_closure_metadata=True),
        generated_at=NOW,
    )
    non_strict_report = build_remediation_closure_report(base)
    strict_report = build_remediation_closure_report(strict)
    assert non_strict_report.state is RemediationClosureState.DEGRADED
    assert strict_report.state is RemediationClosureState.BLOCKED
    assert RemediationClosureReasonCode.SAFETY_BLOCKED in strict_report.reason_codes


def test_not_applicable_and_info_do_not_block() -> None:
    ref = _backlog_item("b1", "acknowledged")
    es = _evidence_summary("es1", "b1", "covered")
    closure = _closure("c1", "b1", "es1")
    review = _review("r1", "c1", "accepted")
    inp = RemediationClosureInput(
        backlog_item_refs=(ref,),
        evidence_summaries=(es,),
        closure_declarations=(closure,),
        review_records=(review,),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert report.state is RemediationClosureState.OK
    assert all(issue.severity is not RemediationClosureSeverity.BLOCKING for issue in report.issues)


# ---------------------------------------------------------------------------
# Opaque references / no path traversal
# ---------------------------------------------------------------------------


def test_refs_remain_opaque_strings() -> None:
    ref = RemediationClosureBacklogItemRef(
        backlog_item_id="b1",
        source_id="path/to/report.md",
        finding_id="finding-1",
    )
    closure = RemediationClosureDeclaration(
        closure_id="c1",
        backlog_item_id="b1",
        evidence_link="s3://bucket/evidence.pdf",
    )
    inp = RemediationClosureInput(
        backlog_item_refs=(ref,),
        closure_declarations=(closure,),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert report.backlog_item_refs[0].source_id == "path/to/report.md"
    assert report.closure_declarations[0].evidence_link == "s3://bucket/evidence.pdf"


# ---------------------------------------------------------------------------
# No source mutation
# ---------------------------------------------------------------------------


def test_input_collections_not_mutated() -> None:
    refs = [_backlog_item("b2"), _backlog_item("b1")]
    inp = RemediationClosureInput(backlog_item_refs=refs, generated_at=NOW)
    original_ids = [r.backlog_item_id for r in refs]
    build_remediation_closure_report(inp)
    assert [r.backlog_item_id for r in refs] == original_ids


# ---------------------------------------------------------------------------
# Public exports
# ---------------------------------------------------------------------------


def test_build_function_exported() -> None:
    assert build_remediation_closure_report is not None


def test_models_imported_via_package() -> None:
    from hunter import remediation_closure
    assert hasattr(remediation_closure, "RemediationClosureInput")
    assert hasattr(remediation_closure, "build_remediation_closure_report")
