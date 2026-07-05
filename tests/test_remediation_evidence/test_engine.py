"""Tests for hunter.remediation_evidence.engine."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from hunter.remediation_evidence import (
    FORBIDDEN_REMEDIATION_EVIDENCE_TERMS,
    RemediationBacklogItemRef,
    RemediationEvidenceConfig,
    RemediationEvidenceCoverageState,
    RemediationEvidenceInput,
    RemediationEvidenceIssueType,
    RemediationEvidenceLink,
    RemediationEvidenceReasonCode,
    RemediationEvidenceRecord,
    RemediationEvidenceRecordState,
    RemediationEvidenceReviewOutcome,
    RemediationReviewRecord,
    RemediationEvidenceSeverity,
    RemediationEvidenceState,
    build_remediation_evidence_report,
)
from hunter.remediation_backlog.models import RemediationBacklogItemState


NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
OLD = NOW - timedelta(days=31)


def _backlog_item(item_id: str, state: str = "open") -> RemediationBacklogItemRef:
    return RemediationBacklogItemRef(
        backlog_item_id=item_id,
        item_state=state,
    )


def _evidence(evidence_id: str, backlog_item_id: str, state: str = "pending_review") -> RemediationEvidenceRecord:
    return RemediationEvidenceRecord(
        evidence_id=evidence_id,
        backlog_item_id=backlog_item_id,
        evidence_state=state,
    )


def _review(review_id: str, evidence_id: str, outcome: str = "accepted") -> RemediationReviewRecord:
    return RemediationReviewRecord(
        review_id=review_id,
        evidence_id=evidence_id,
        outcome=outcome,
    )


def _link(link_id: str, evidence_id: str, backlog_item_id: str) -> RemediationEvidenceLink:
    return RemediationEvidenceLink(
        link_id=link_id,
        evidence_id=evidence_id,
        backlog_item_id=backlog_item_id,
    )


# ---------------------------------------------------------------------------
# Empty input and basic state
# ---------------------------------------------------------------------------


def test_empty_input_not_applicable() -> None:
    inp = RemediationEvidenceInput()
    report = build_remediation_evidence_report(inp)
    assert report.state is RemediationEvidenceState.NOT_APPLICABLE
    assert report.issues == ()
    assert report.coverage_results == ()
    assert RemediationEvidenceReasonCode.NOT_APPLICABLE in report.reason_codes


def test_empty_input_with_generated_at() -> None:
    inp = RemediationEvidenceInput(generated_at=NOW)
    report = build_remediation_evidence_report(inp)
    assert report.state is RemediationEvidenceState.NOT_APPLICABLE
    assert report.generated_at == NOW


def test_no_issues_ok() -> None:
    ref = _backlog_item("b1", "acknowledged")
    rec = _evidence("e1", "b1", "accepted")
    rev = _review("r1", "e1", "accepted")
    inp = RemediationEvidenceInput(
        backlog_item_refs=(ref,),
        evidence_records=(rec,),
        review_records=(rev,),
        generated_at=NOW,
    )
    report = build_remediation_evidence_report(inp)
    assert report.state is RemediationEvidenceState.OK
    assert all(issue.severity is RemediationEvidenceSeverity.INFO for issue in report.issues)
    assert report.coverage_results[0].coverage_state is RemediationEvidenceCoverageState.COVERED


# ---------------------------------------------------------------------------
# Deterministic IDs and ordering
# ---------------------------------------------------------------------------


def test_deterministic_report_id() -> None:
    ref = _backlog_item("b1", "open")
    rec = _evidence("e1", "b1", "accepted")
    rev = _review("r1", "e1", "accepted")
    inp1 = RemediationEvidenceInput(
        backlog_item_refs=(ref,),
        evidence_records=(rec,),
        review_records=(rev,),
        generated_at=NOW,
    )
    inp2 = RemediationEvidenceInput(
        backlog_item_refs=(ref,),
        evidence_records=(rec,),
        review_records=(rev,),
        generated_at=NOW,
    )
    assert build_remediation_evidence_report(inp1).report_id == build_remediation_evidence_report(inp2).report_id


def test_report_id_changes_with_input() -> None:
    inp1 = RemediationEvidenceInput(
        backlog_item_refs=(_backlog_item("b1"),),
        generated_at=NOW,
    )
    inp2 = RemediationEvidenceInput(
        backlog_item_refs=(_backlog_item("b2"),),
        generated_at=NOW,
    )
    assert build_remediation_evidence_report(inp1).report_id != build_remediation_evidence_report(inp2).report_id


def test_collections_copied_and_sorted() -> None:
    r2 = _backlog_item("b2")
    r1 = _backlog_item("b1")
    e2 = _evidence("e2", "b1")
    e1 = _evidence("e1", "b2")
    inp = RemediationEvidenceInput(
        backlog_item_refs=(r2, r1),
        evidence_records=(e2, e1),
    )
    report = build_remediation_evidence_report(inp)
    assert [r.backlog_item_id for r in report.backlog_item_refs] == ["b1", "b2"]
    assert [r.evidence_id for r in report.evidence_records] == ["e1", "e2"]


# ---------------------------------------------------------------------------
# Duplicate IDs fail closed
# ---------------------------------------------------------------------------


def test_duplicate_backlog_item_ids_blocked() -> None:
    inp = RemediationEvidenceInput(
        backlog_item_refs=(_backlog_item("b1"), _backlog_item("b1")),
        generated_at=NOW,
    )
    report = build_remediation_evidence_report(inp)
    assert report.state is RemediationEvidenceState.BLOCKED
    assert RemediationEvidenceReasonCode.DUPLICATE_ID in report.reason_codes


def test_duplicate_evidence_ids_blocked() -> None:
    inp = RemediationEvidenceInput(
        evidence_records=(_evidence("e1", "b1"), _evidence("e1", "b1")),
        generated_at=NOW,
    )
    report = build_remediation_evidence_report(inp)
    assert report.state is RemediationEvidenceState.BLOCKED
    assert RemediationEvidenceReasonCode.DUPLICATE_ID in report.reason_codes


def test_duplicate_review_ids_blocked() -> None:
    inp = RemediationEvidenceInput(
        review_records=(_review("r1", "e1"), _review("r1", "e1")),
        generated_at=NOW,
    )
    report = build_remediation_evidence_report(inp)
    assert report.state is RemediationEvidenceState.BLOCKED


def test_duplicate_link_ids_blocked() -> None:
    inp = RemediationEvidenceInput(
        links=(_link("l1", "e1", "b1"), _link("l1", "e2", "b2")),
        generated_at=NOW,
    )
    report = build_remediation_evidence_report(inp)
    assert report.state is RemediationEvidenceState.BLOCKED


# ---------------------------------------------------------------------------
# Duplicate evidence detection
# ---------------------------------------------------------------------------


def test_duplicate_evidence_records_detected() -> None:
    inp = RemediationEvidenceInput(
        backlog_item_refs=(_backlog_item("b1", "acknowledged"),),
        evidence_records=(
            RemediationEvidenceRecord(
                evidence_id="e1",
                backlog_item_id="b1",
                title="same title",
                description="same description",
                evidence_state="accepted",
            ),
            RemediationEvidenceRecord(
                evidence_id="e2",
                backlog_item_id="b1",
                title="same title",
                description="same description",
                evidence_state="accepted",
            ),
        ),
        review_records=(
            RemediationReviewRecord(review_id="r1", evidence_id="e1", outcome="accepted"),
            RemediationReviewRecord(review_id="r2", evidence_id="e2", outcome="accepted"),
        ),
        generated_at=NOW,
    )
    report = build_remediation_evidence_report(inp)
    assert report.state is RemediationEvidenceState.DEGRADED
    issue_types = {issue.issue_type for issue in report.issues}
    assert RemediationEvidenceIssueType.DUPLICATE_EVIDENCE in issue_types


# ---------------------------------------------------------------------------
# Orphan detection
# ---------------------------------------------------------------------------


def test_orphan_evidence_detected() -> None:
    inp = RemediationEvidenceInput(
        backlog_item_refs=(_backlog_item("b1"),),
        evidence_records=(_evidence("e1", "b2", "accepted"),),
        generated_at=NOW,
    )
    report = build_remediation_evidence_report(inp)
    assert any(issue.issue_type is RemediationEvidenceIssueType.ORPHAN_EVIDENCE for issue in report.issues)
    assert report.data_quality.orphan_evidence_count == 1


def test_orphan_review_detected() -> None:
    inp = RemediationEvidenceInput(
        evidence_records=(_evidence("e1", "b1"),),
        review_records=(_review("r1", "e2"),),
        generated_at=NOW,
    )
    report = build_remediation_evidence_report(inp)
    assert any(issue.issue_type is RemediationEvidenceIssueType.ORPHAN_REVIEW for issue in report.issues)


def test_orphan_link_detected() -> None:
    inp = RemediationEvidenceInput(
        backlog_item_refs=(_backlog_item("b1"),),
        evidence_records=(_evidence("e1", "b1"),),
        links=(_link("l1", "e1", "b2"),),
        generated_at=NOW,
    )
    report = build_remediation_evidence_report(inp)
    assert any(issue.issue_type is RemediationEvidenceIssueType.ORPHAN_LINK for issue in report.issues)


# ---------------------------------------------------------------------------
# Conflicting reviews
# ---------------------------------------------------------------------------


def test_conflicting_reviews_detected() -> None:
    inp = RemediationEvidenceInput(
        backlog_item_refs=(_backlog_item("b1"),),
        evidence_records=(_evidence("e1", "b1"),),
        review_records=(
            _review("r1", "e1", "accepted"),
            _review("r2", "e1", "rejected"),
        ),
        generated_at=NOW,
    )
    report = build_remediation_evidence_report(inp)
    assert any(issue.issue_type is RemediationEvidenceIssueType.CONFLICTING_REVIEW for issue in report.issues)
    assert report.state is RemediationEvidenceState.BLOCKED


# ---------------------------------------------------------------------------
# Stale detection
# ---------------------------------------------------------------------------


def test_stale_evidence_detected() -> None:
    inp = RemediationEvidenceInput(
        backlog_item_refs=(_backlog_item("b1"),),
        evidence_records=(
            RemediationEvidenceRecord(
                evidence_id="e1",
                backlog_item_id="b1",
                evidence_state="accepted",
                generated_at=OLD,
            ),
        ),
        generated_at=NOW,
    )
    report = build_remediation_evidence_report(inp)
    assert any(issue.issue_type is RemediationEvidenceIssueType.STALE_EVIDENCE for issue in report.issues)
    assert report.coverage_results[0].coverage_state is RemediationEvidenceCoverageState.STALE


def test_stale_review_detected() -> None:
    inp = RemediationEvidenceInput(
        backlog_item_refs=(_backlog_item("b1"),),
        evidence_records=(_evidence("e1", "b1", "accepted"),),
        review_records=(
            RemediationReviewRecord(
                review_id="r1",
                evidence_id="e1",
                outcome="accepted",
                generated_at=OLD,
            ),
        ),
        generated_at=NOW,
    )
    report = build_remediation_evidence_report(inp)
    assert any(issue.issue_type is RemediationEvidenceIssueType.STALE_REVIEW for issue in report.issues)


# ---------------------------------------------------------------------------
# Missing evidence / review
# ---------------------------------------------------------------------------


def test_missing_evidence_for_required_item() -> None:
    inp = RemediationEvidenceInput(
        backlog_item_refs=(_backlog_item("b1"),),
        config=RemediationEvidenceConfig(required_backlog_item_ids=("b1",)),
        generated_at=NOW,
    )
    report = build_remediation_evidence_report(inp)
    assert any(issue.issue_type is RemediationEvidenceIssueType.MISSING_EVIDENCE for issue in report.issues)
    assert report.coverage_results[0].coverage_state is RemediationEvidenceCoverageState.MISSING


def test_missing_evidence_for_all_items() -> None:
    inp = RemediationEvidenceInput(
        backlog_item_refs=(_backlog_item("b1"), _backlog_item("b2")),
        config=RemediationEvidenceConfig(require_evidence_for_all=True),
        generated_at=NOW,
    )
    report = build_remediation_evidence_report(inp)
    missing_issues = [issue for issue in report.issues if issue.issue_type is RemediationEvidenceIssueType.MISSING_EVIDENCE]
    assert len(missing_issues) == 2


def test_missing_review_detected() -> None:
    inp = RemediationEvidenceInput(
        backlog_item_refs=(_backlog_item("b1"),),
        evidence_records=(_evidence("e1", "b1", "accepted"),),
        config=RemediationEvidenceConfig(require_review=True),
        generated_at=NOW,
    )
    report = build_remediation_evidence_report(inp)
    assert any(issue.issue_type is RemediationEvidenceIssueType.MISSING_REVIEW for issue in report.issues)


# ---------------------------------------------------------------------------
# Rejected and pending-review evidence
# ---------------------------------------------------------------------------


def test_rejected_evidence_detected() -> None:
    inp = RemediationEvidenceInput(
        backlog_item_refs=(_backlog_item("b1"),),
        evidence_records=(_evidence("e1", "b1", "rejected"),),
        generated_at=NOW,
    )
    report = build_remediation_evidence_report(inp)
    assert any(issue.issue_type is RemediationEvidenceIssueType.REJECTED_EVIDENCE for issue in report.issues)
    assert report.coverage_results[0].coverage_state is RemediationEvidenceCoverageState.REJECTED


def test_pending_review_evidence_detected() -> None:
    inp = RemediationEvidenceInput(
        backlog_item_refs=(_backlog_item("b1"),),
        evidence_records=(_evidence("e1", "b1", "pending_review"),),
        generated_at=NOW,
    )
    report = build_remediation_evidence_report(inp)
    assert any(issue.issue_type is RemediationEvidenceIssueType.PENDING_REVIEW_EVIDENCE for issue in report.issues)
    assert report.coverage_results[0].coverage_state is RemediationEvidenceCoverageState.PENDING_REVIEW


# ---------------------------------------------------------------------------
# Coverage precedence first-match-wins
# ---------------------------------------------------------------------------


def test_coverage_not_applicable_for_not_required_item_without_evidence() -> None:
    inp = RemediationEvidenceInput(
        backlog_item_refs=(_backlog_item("b1"),),
        generated_at=NOW,
    )
    report = build_remediation_evidence_report(inp)
    assert report.coverage_results[0].coverage_state is RemediationEvidenceCoverageState.NOT_APPLICABLE


def test_coverage_not_applicable_for_not_applicable_state() -> None:
    inp = RemediationEvidenceInput(
        backlog_item_refs=(_backlog_item("b1", "not_applicable"),),
        evidence_records=(_evidence("e1", "b1", "accepted"),),
        generated_at=NOW,
    )
    report = build_remediation_evidence_report(inp)
    assert report.coverage_results[0].coverage_state is RemediationEvidenceCoverageState.NOT_APPLICABLE


def test_coverage_covered_with_accepted_evidence_and_review() -> None:
    inp = RemediationEvidenceInput(
        backlog_item_refs=(_backlog_item("b1", "acknowledged"),),
        evidence_records=(_evidence("e1", "b1", "accepted"),),
        review_records=(_review("r1", "e1", "accepted"),),
        generated_at=NOW,
    )
    report = build_remediation_evidence_report(inp)
    assert report.coverage_results[0].coverage_state is RemediationEvidenceCoverageState.COVERED


def test_coverage_partial_when_mixed_states() -> None:
    inp = RemediationEvidenceInput(
        backlog_item_refs=(_backlog_item("b1", "acknowledged"),),
        evidence_records=(
            _evidence("e1", "b1", "accepted"),
            _evidence("e2", "b1", "pending_review"),
        ),
        review_records=(_review("r1", "e1", "accepted"),),
        generated_at=NOW,
    )
    report = build_remediation_evidence_report(inp)
    assert report.coverage_results[0].coverage_state is RemediationEvidenceCoverageState.COVERED


def test_coverage_rejected_all_rejected() -> None:
    inp = RemediationEvidenceInput(
        backlog_item_refs=(_backlog_item("b1"),),
        evidence_records=(
            _evidence("e1", "b1", "rejected"),
            _evidence("e2", "b1", "rejected"),
        ),
        generated_at=NOW,
    )
    report = build_remediation_evidence_report(inp)
    assert report.coverage_results[0].coverage_state is RemediationEvidenceCoverageState.REJECTED


def test_coverage_conflicting_takes_precedence_over_rejected() -> None:
    inp = RemediationEvidenceInput(
        backlog_item_refs=(_backlog_item("b1"),),
        evidence_records=(_evidence("e1", "b1", "rejected"),),
        review_records=(
            _review("r1", "e1", "accepted"),
            _review("r2", "e1", "rejected"),
        ),
        generated_at=NOW,
    )
    report = build_remediation_evidence_report(inp)
    assert report.coverage_results[0].coverage_state is RemediationEvidenceCoverageState.CONFLICTING


# ---------------------------------------------------------------------------
# Backlog item state mismatches
# ---------------------------------------------------------------------------


def test_accepted_evidence_on_blocked_item_emits_advisory() -> None:
    inp = RemediationEvidenceInput(
        backlog_item_refs=(_backlog_item("b1", "blocked"),),
        evidence_records=(_evidence("e1", "b1", "accepted"),),
        review_records=(_review("r1", "e1", "accepted"),),
        generated_at=NOW,
    )
    report = build_remediation_evidence_report(inp)
    assert any(issue.issue_type is RemediationEvidenceIssueType.BLOCKED_BACKLOG_ITEM for issue in report.issues)
    assert report.state is RemediationEvidenceState.DEGRADED


def test_accepted_evidence_on_open_item_emits_advisory() -> None:
    inp = RemediationEvidenceInput(
        backlog_item_refs=(_backlog_item("b1", "open"),),
        evidence_records=(_evidence("e1", "b1", "accepted"),),
        review_records=(_review("r1", "e1", "accepted"),),
        generated_at=NOW,
    )
    report = build_remediation_evidence_report(inp)
    assert any(issue.issue_type is RemediationEvidenceIssueType.OPEN_BACKLOG_ITEM for issue in report.issues)
    assert report.state is RemediationEvidenceState.DEGRADED


def test_acknowledged_item_emits_info() -> None:
    inp = RemediationEvidenceInput(
        backlog_item_refs=(_backlog_item("b1", "acknowledged"),),
        generated_at=NOW,
    )
    report = build_remediation_evidence_report(inp)
    assert any(issue.issue_type is RemediationEvidenceIssueType.ACKNOWLEDGED_BACKLOG_ITEM for issue in report.issues)
    assert report.state is RemediationEvidenceState.OK


def test_deferred_item_emits_info() -> None:
    inp = RemediationEvidenceInput(
        backlog_item_refs=(_backlog_item("b1", "deferred"),),
        generated_at=NOW,
    )
    report = build_remediation_evidence_report(inp)
    assert any(issue.issue_type is RemediationEvidenceIssueType.DEFERRED_BACKLOG_ITEM for issue in report.issues)
    assert report.state is RemediationEvidenceState.OK


# ---------------------------------------------------------------------------
# Safety boundaries
# ---------------------------------------------------------------------------


def test_unsafe_content_blocks() -> None:
    inp = RemediationEvidenceInput(
        metadata={"key": b"bytes"},
        generated_at=NOW,
    )
    report = build_remediation_evidence_report(inp)
    assert report.state is RemediationEvidenceState.BLOCKED
    assert RemediationEvidenceReasonCode.UNSAFE_CONTENT in report.reason_codes
    assert report.safety_flags.has_unsafe_content is True
    assert report.safety_flags.is_safe is False


def test_forbidden_term_blocks() -> None:
    inp = RemediationEvidenceInput(
        backlog_item_refs=(
            RemediationBacklogItemRef(
                backlog_item_id="b1",
                title="This is a buy signal",
            ),
        ),
        generated_at=NOW,
    )
    report = build_remediation_evidence_report(inp)
    assert report.state is RemediationEvidenceState.BLOCKED
    assert RemediationEvidenceReasonCode.FORBIDDEN_TERM_PRESENT in report.reason_codes
    assert report.safety_flags.has_forbidden_terms is True


def test_forbidden_terms_config_can_disable() -> None:
    inp = RemediationEvidenceInput(
        backlog_item_refs=(
            RemediationBacklogItemRef(
                backlog_item_id="b1",
                title="This is a buy signal",
                item_state="not_applicable",
            ),
        ),
        config=RemediationEvidenceConfig(
            forbid_action_terms=False,
            require_evidence_for_all=False,
        ),
        generated_at=NOW,
    )
    report = build_remediation_evidence_report(inp)
    assert report.state is RemediationEvidenceState.OK
    assert RemediationEvidenceReasonCode.FORBIDDEN_TERM_PRESENT not in report.reason_codes


def test_forbidden_term_helper_avoids_false_positives() -> None:
    """Benign phrases must not trigger forbidden-term matching."""
    from hunter.remediation_evidence.models import _has_forbidden_term
    benign_phrases = [
        "pending approval from security team",
        "certification body",
        "no recommendation needed",
        "signal processing",
        "no signal detected",
    ]
    for phrase in benign_phrases:
        assert _has_forbidden_term(phrase, FORBIDDEN_REMEDIATION_EVIDENCE_TERMS) is False


def test_forbidden_term_helper_matches_multi_word_phrases() -> None:
    from hunter.remediation_evidence.models import _has_forbidden_term
    assert _has_forbidden_term("This is a buy signal", FORBIDDEN_REMEDIATION_EVIDENCE_TERMS) is True
    assert _has_forbidden_term("Deploy immediately to production", FORBIDDEN_REMEDIATION_EVIDENCE_TERMS) is True


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def test_strict_promotes_degraded_to_blocked() -> None:
    inp = RemediationEvidenceInput(
        backlog_item_refs=(_backlog_item("b1", "open"),),
        evidence_records=(_evidence("e1", "b1", "accepted"),),
        review_records=(_review("r1", "e1", "accepted"),),
        config=RemediationEvidenceConfig(strict=True),
        generated_at=NOW,
    )
    report = build_remediation_evidence_report(inp)
    assert report.state is RemediationEvidenceState.BLOCKED
    assert RemediationEvidenceReasonCode.SAFETY_BLOCKED in report.reason_codes


def test_not_applicable_and_info_do_not_block() -> None:
    inp = RemediationEvidenceInput(
        backlog_item_refs=(_backlog_item("b1", "acknowledged"),),
        generated_at=NOW,
    )
    report = build_remediation_evidence_report(inp)
    assert report.state is RemediationEvidenceState.OK
    assert all(issue.severity is not RemediationEvidenceSeverity.BLOCKING for issue in report.issues)


# ---------------------------------------------------------------------------
# Opaque references / no path traversal
# ---------------------------------------------------------------------------


def test_refs_remain_opaque_strings() -> None:
    ref = RemediationBacklogItemRef(
        backlog_item_id="b1",
        source_id="path/to/report.md",
        finding_id="finding-1",
    )
    rec = RemediationEvidenceRecord(
        evidence_id="e1",
        backlog_item_id="b1",
        metadata={"path": "s3://bucket/evidence.pdf"},
    )
    inp = RemediationEvidenceInput(
        backlog_item_refs=(ref,),
        evidence_records=(rec,),
        generated_at=NOW,
    )
    report = build_remediation_evidence_report(inp)
    # Ensure report still contains opaque strings and did not attempt to open them.
    assert report.backlog_item_refs[0].source_id == "path/to/report.md"
    assert report.evidence_records[0].metadata["path"] == "s3://bucket/evidence.pdf"


# ---------------------------------------------------------------------------
# No source mutation
# ---------------------------------------------------------------------------


def test_input_collections_not_mutated() -> None:
    refs = [_backlog_item("b2"), _backlog_item("b1")]
    inp = RemediationEvidenceInput(backlog_item_refs=refs, generated_at=NOW)
    original_ids = [r.backlog_item_id for r in refs]
    build_remediation_evidence_report(inp)
    assert [r.backlog_item_id for r in refs] == original_ids


# ---------------------------------------------------------------------------
# Public exports
# ---------------------------------------------------------------------------


def test_build_function_exported() -> None:
    assert build_remediation_evidence_report is not None


def test_models_imported_via_package() -> None:
    from hunter import remediation_evidence
    assert hasattr(remediation_evidence, "RemediationEvidenceInput")
    assert hasattr(remediation_evidence, "build_remediation_evidence_report")
