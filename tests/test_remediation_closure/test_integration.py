"""Integration tests for hunter.remediation_closure package. MVP-39 Step 3."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

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
    remediation_closure_report_to_csv_text,
    remediation_closure_report_to_dict,
    remediation_closure_report_to_json_text,
    remediation_closure_report_to_markdown_text,
    write_remediation_closure_report,
)

NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
OLD = NOW - timedelta(days=31)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_full_input() -> RemediationClosureInput:
    """Return a representative input with all collection types populated."""
    return RemediationClosureInput(
        backlog_item_refs=(
            RemediationClosureBacklogItemRef(
                backlog_item_id="b1",
                item_state="acknowledged",
                title="Backlog item one",
                description="First backlog item",
                generated_at=NOW,
                metadata={"owner": "alice"},
            ),
        ),
        evidence_summaries=(
            RemediationClosureEvidenceSummary(
                evidence_summary_id="es1",
                backlog_item_id="b1",
                coverage_state="covered",
                evidence_ids=("ev1",),
                generated_at=NOW,
                metadata={"reviewer": "bob"},
            ),
        ),
        closure_declarations=(
            RemediationClosureDeclaration(
                closure_id="c1",
                backlog_item_id="b1",
                evidence_summary_id="es1",
                declared_by="alice",
                reviewed_by="bob",
                closed_at=NOW,
                rationale="Issue resolved",
                evidence_link="audit-report.md",
                generated_at=NOW,
                metadata={"approved": "no"},
            ),
        ),
        review_records=(
            RemediationClosureReviewRecord(
                review_id="r1",
                closure_id="c1",
                outcome="accepted",
                reviewer="bob",
                reviewed_at=NOW,
                generated_at=NOW,
                note="Looks good",
            ),
        ),
        links=(
            RemediationClosureLink(
                link_id="l1",
                closure_id="c1",
                evidence_summary_id="es1",
                backlog_item_id="b1",
                link_type="closure_evidence",
                generated_at=NOW,
            ),
        ),
        config=RemediationClosureConfig(
            require_review=False,
            require_evidence_for_closure=True,
        ),
        project_version="0.39.0-dev",
        metadata={"env": "test"},
        generated_at=NOW,
    )


# ---------------------------------------------------------------------------
# End-to-end successful remediation closure register
# ---------------------------------------------------------------------------


def test_end_to_end_report_structure() -> None:
    inp = _build_full_input()
    report = build_remediation_closure_report(inp)

    assert report.report_id
    assert len(report.report_id) == 64  # SHA-256 hex
    assert report.generated_at == NOW
    assert report.project_version == "0.39.0-dev"
    assert report.state is RemediationClosureState.OK
    assert report.safety_notice
    assert report.backlog_item_refs
    assert report.evidence_summaries
    assert report.closure_declarations
    assert report.review_records
    assert report.links
    assert report.closure_results
    assert isinstance(report.data_quality, object)
    assert isinstance(report.safety_flags, object)


def test_end_to_end_closure_result_recorded() -> None:
    inp = _build_full_input()
    report = build_remediation_closure_report(inp)

    result = report.closure_results[0]
    assert result.backlog_item_id == "b1"
    assert result.closure_id == "c1"
    assert result.record_state is RemediationClosureRecordState.CLOSED_RECORDED
    assert result.eligibility_state is RemediationClosureEligibilityState.ELIGIBLE
    assert result.review_outcome is RemediationClosureReviewOutcome.ACCEPTED


def test_end_to_end_reason_codes_and_issues() -> None:
    inp = _build_full_input()
    report = build_remediation_closure_report(inp)

    assert RemediationClosureReasonCode.OK in report.reason_codes
    assert all(issue.severity is not RemediationClosureSeverity.BLOCKING for issue in report.issues)


# ---------------------------------------------------------------------------
# Writer end-to-end
# ---------------------------------------------------------------------------


def test_writer_end_to_end_creates_all_files(tmp_path: Path) -> None:
    report = build_remediation_closure_report(_build_full_input())
    json_path = tmp_path / "closure.json"
    csv_path = tmp_path / "closure.csv"
    md_path = tmp_path / "closure.md"

    write_remediation_closure_report(
        report,
        json_path=json_path,
        csv_path=csv_path,
        markdown_path=md_path,
    )

    assert json_path.exists()
    assert csv_path.exists()
    assert md_path.exists()


def test_writer_json_parses_and_includes_all_collections(tmp_path: Path) -> None:
    report = build_remediation_closure_report(_build_full_input())
    json_path = tmp_path / "closure.json"
    write_remediation_closure_report(report, json_path=json_path, csv_path=None, markdown_path=None)

    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["report_id"] == report.report_id
    assert "backlog_item_refs" in data
    assert "evidence_summaries" in data
    assert "closure_declarations" in data
    assert "review_records" in data
    assert "links" in data
    assert "issues" in data
    assert "closure_results" in data
    assert "data_quality" in data
    assert "safety_flags" in data


def test_writer_csv_preserves_closure_result_fields(tmp_path: Path) -> None:
    report = build_remediation_closure_report(_build_full_input())
    csv_path = tmp_path / "closure.csv"
    write_remediation_closure_report(report, json_path=None, csv_path=csv_path, markdown_path=None)

    text = csv_path.read_text(encoding="utf-8")
    rows = list(csv.DictReader(text.splitlines()))
    assert rows
    assert rows[0]["report_id"] == report.report_id
    assert rows[0]["backlog_item_id"] == "b1"
    assert rows[0]["closure_id"] == "c1"
    assert rows[0]["record_state"] == "closed_recorded"
    assert rows[0]["eligibility_state"] == "eligible"
    assert rows[0]["review_outcome"] == "accepted"


def test_writer_markdown_starts_with_h1_and_safety_notice(tmp_path: Path) -> None:
    report = build_remediation_closure_report(_build_full_input())
    md_path = tmp_path / "closure.md"
    write_remediation_closure_report(report, json_path=None, csv_path=None, markdown_path=md_path)

    text = md_path.read_text(encoding="utf-8")
    assert text.startswith("# Remediation Closure Register")
    assert "audit-only" in text.lower() or "human-audit" in text.lower()
    assert "research" in text.lower()


# ---------------------------------------------------------------------------
# Empty / non-empty behavior
# ---------------------------------------------------------------------------


def test_empty_input_returns_not_applicable() -> None:
    inp = RemediationClosureInput(generated_at=NOW)
    report = build_remediation_closure_report(inp)
    assert report.state is RemediationClosureState.NOT_APPLICABLE


def test_non_empty_input_with_no_advisory_issues_returns_ok() -> None:
    report = build_remediation_closure_report(_build_full_input())
    assert report.state is RemediationClosureState.OK
    assert not any(issue.severity is RemediationClosureSeverity.BLOCKING for issue in report.issues)
    assert not any(issue.severity is RemediationClosureSeverity.ADVISORY for issue in report.issues)


def test_info_and_not_applicable_do_not_block() -> None:
    inp = RemediationClosureInput(
        backlog_item_refs=(
            RemediationClosureBacklogItemRef(backlog_item_id="b1", item_state="acknowledged"),
        ),
        closure_declarations=(
            RemediationClosureDeclaration(
                closure_id="c1",
                backlog_item_id="b1",
                evidence_summary_id="",
                declared_by="alice",
                reviewed_by="bob",
                closed_at=NOW,
                rationale="Done",
                generated_at=NOW,
            ),
        ),
        config=RemediationClosureConfig(
            require_evidence_for_closure=False,
            require_review=False,
        ),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert report.state is RemediationClosureState.OK
    assert all(issue.severity is RemediationClosureSeverity.INFO for issue in report.issues)


# ---------------------------------------------------------------------------
# Closure states and precedence
# ---------------------------------------------------------------------------


def test_closure_not_applicable_by_state() -> None:
    inp = RemediationClosureInput(
        backlog_item_refs=(
            RemediationClosureBacklogItemRef(backlog_item_id="b1", item_state="not_applicable"),
        ),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert report.closure_results[0].record_state is RemediationClosureRecordState.NOT_APPLICABLE


def test_closure_blocked_no_accepted_evidence() -> None:
    inp = RemediationClosureInput(
        backlog_item_refs=(
            RemediationClosureBacklogItemRef(backlog_item_id="b1", item_state="acknowledged"),
        ),
        closure_declarations=(
            RemediationClosureDeclaration(
                closure_id="c1", backlog_item_id="b1", evidence_summary_id="es1",
                declared_by="alice", reviewed_by="bob", closed_at=NOW, rationale="Done", generated_at=NOW,
            ),
        ),
        config=RemediationClosureConfig(require_evidence_for_closure=True),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert report.closure_results[0].record_state is RemediationClosureRecordState.BLOCKED
    missing = [issue for issue in report.issues if issue.issue_type is RemediationClosureIssueType.MISSING_EVIDENCE]
    assert missing
    assert all(issue.severity is RemediationClosureSeverity.BLOCKING for issue in missing)
    assert report.state is RemediationClosureState.BLOCKED


def test_closure_disputed_conflicting_declarations() -> None:
    inp = RemediationClosureInput(
        backlog_item_refs=(
            RemediationClosureBacklogItemRef(backlog_item_id="b1", item_state="acknowledged"),
        ),
        evidence_summaries=(
            RemediationClosureEvidenceSummary(evidence_summary_id="es1", backlog_item_id="b1", coverage_state="covered"),
            RemediationClosureEvidenceSummary(evidence_summary_id="es2", backlog_item_id="b1", coverage_state="covered"),
        ),
        closure_declarations=(
            RemediationClosureDeclaration(
                closure_id="c1", backlog_item_id="b1", evidence_summary_id="es1",
                declared_by="alice", reviewed_by="bob", closed_at=NOW, rationale="Done", generated_at=NOW,
            ),
            RemediationClosureDeclaration(
                closure_id="c2", backlog_item_id="b1", evidence_summary_id="es2",
                declared_by="bob", reviewed_by="alice", closed_at=NOW, rationale="Done differently", generated_at=NOW,
            ),
        ),
        review_records=(
            RemediationClosureReviewRecord(review_id="r1", closure_id="c1", outcome="accepted", reviewer="bob", generated_at=NOW),
            RemediationClosureReviewRecord(review_id="r2", closure_id="c2", outcome="accepted", reviewer="alice", generated_at=NOW),
        ),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert report.closure_results[0].record_state is RemediationClosureRecordState.DISPUTED


def test_closure_duplicate_semantic_declarations() -> None:
    inp = RemediationClosureInput(
        backlog_item_refs=(
            RemediationClosureBacklogItemRef(backlog_item_id="b1", item_state="acknowledged"),
        ),
        evidence_summaries=(
            RemediationClosureEvidenceSummary(evidence_summary_id="es1", backlog_item_id="b1", coverage_state="covered"),
        ),
        closure_declarations=(
            RemediationClosureDeclaration(
                closure_id="c1", backlog_item_id="b1", evidence_summary_id="es1",
                declared_by="alice", reviewed_by="bob", closed_at=NOW, rationale="Done", generated_at=NOW,
            ),
            RemediationClosureDeclaration(
                closure_id="c2", backlog_item_id="b1", evidence_summary_id="es1",
                declared_by="alice", reviewed_by="bob", closed_at=NOW, rationale="Done", generated_at=NOW,
            ),
        ),
        review_records=(
            RemediationClosureReviewRecord(review_id="r1", closure_id="c1", outcome="accepted", reviewer="bob", generated_at=NOW),
            RemediationClosureReviewRecord(review_id="r2", closure_id="c2", outcome="accepted", reviewer="bob", generated_at=NOW),
        ),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert report.closure_results[0].record_state is RemediationClosureRecordState.DUPLICATE


def test_closure_rejected_review() -> None:
    inp = RemediationClosureInput(
        backlog_item_refs=(
            RemediationClosureBacklogItemRef(backlog_item_id="b1", item_state="acknowledged"),
        ),
        evidence_summaries=(
            RemediationClosureEvidenceSummary(evidence_summary_id="es1", backlog_item_id="b1", coverage_state="covered"),
        ),
        closure_declarations=(
            RemediationClosureDeclaration(
                closure_id="c1", backlog_item_id="b1", evidence_summary_id="es1",
                declared_by="alice", reviewed_by="bob", closed_at=NOW, rationale="Done", generated_at=NOW,
            ),
        ),
        review_records=(
            RemediationClosureReviewRecord(review_id="r1", closure_id="c1", outcome="rejected", reviewer="bob", generated_at=NOW),
        ),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert report.closure_results[0].record_state is RemediationClosureRecordState.REJECTED


def test_closure_stale_records() -> None:
    inp = RemediationClosureInput(
        backlog_item_refs=(
            RemediationClosureBacklogItemRef(backlog_item_id="b1", item_state="acknowledged"),
        ),
        evidence_summaries=(
            RemediationClosureEvidenceSummary(evidence_summary_id="es1", backlog_item_id="b1", coverage_state="covered", generated_at=OLD),
        ),
        closure_declarations=(
            RemediationClosureDeclaration(
                closure_id="c1", backlog_item_id="b1", evidence_summary_id="es1",
                declared_by="alice", reviewed_by="bob", closed_at=OLD, rationale="Done", generated_at=OLD,
            ),
        ),
        review_records=(
            RemediationClosureReviewRecord(review_id="r1", closure_id="c1", outcome="accepted", reviewer="bob", generated_at=OLD),
        ),
        config=RemediationClosureConfig(staleness_threshold_seconds=60),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert report.closure_results[0].record_state is RemediationClosureRecordState.STALE


def test_closure_pending_review() -> None:
    inp = RemediationClosureInput(
        backlog_item_refs=(
            RemediationClosureBacklogItemRef(backlog_item_id="b1", item_state="acknowledged"),
        ),
        evidence_summaries=(
            RemediationClosureEvidenceSummary(evidence_summary_id="es1", backlog_item_id="b1", coverage_state="covered"),
        ),
        closure_declarations=(
            RemediationClosureDeclaration(
                closure_id="c1", backlog_item_id="b1", evidence_summary_id="es1",
                declared_by="alice", reviewed_by="bob", closed_at=NOW, rationale="Done", generated_at=NOW,
            ),
        ),
        review_records=(
            RemediationClosureReviewRecord(review_id="r1", closure_id="c1", outcome="pending", reviewer="bob", generated_at=NOW),
        ),
        config=RemediationClosureConfig(require_review=True),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert report.closure_results[0].record_state is RemediationClosureRecordState.PENDING_REVIEW


def test_closure_partial_missing_required_metadata() -> None:
    inp = RemediationClosureInput(
        backlog_item_refs=(
            RemediationClosureBacklogItemRef(backlog_item_id="b1", item_state="acknowledged"),
        ),
        evidence_summaries=(
            RemediationClosureEvidenceSummary(evidence_summary_id="es1", backlog_item_id="b1", coverage_state="covered"),
        ),
        closure_declarations=(
            RemediationClosureDeclaration(
                closure_id="c1", backlog_item_id="b1", evidence_summary_id="es1",
                declared_by="", reviewed_by="", closed_at=NOW, rationale="", generated_at=NOW,
            ),
        ),
        config=RemediationClosureConfig(require_closure_metadata=True),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert report.closure_results[0].record_state is RemediationClosureRecordState.PARTIAL


def test_closure_precedence_first_match_wins() -> None:
    inp = RemediationClosureInput(
        backlog_item_refs=(
            RemediationClosureBacklogItemRef(backlog_item_id="b1", item_state="blocked"),
        ),
        evidence_summaries=(
            RemediationClosureEvidenceSummary(evidence_summary_id="es1", backlog_item_id="b1", coverage_state="covered"),
        ),
        closure_declarations=(
            RemediationClosureDeclaration(
                closure_id="c1", backlog_item_id="b1", evidence_summary_id="es1",
                declared_by="alice", reviewed_by="bob", closed_at=NOW, rationale="Done", generated_at=NOW,
            ),
        ),
        review_records=(
            RemediationClosureReviewRecord(review_id="r1", closure_id="c1", outcome="rejected", reviewer="bob", generated_at=NOW),
        ),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert report.closure_results[0].record_state is RemediationClosureRecordState.BLOCKED


# ---------------------------------------------------------------------------
# Built-in detections
# ---------------------------------------------------------------------------


def test_duplicate_backlog_item_ids_fail_closed() -> None:
    inp = RemediationClosureInput(
        backlog_item_refs=(
            RemediationClosureBacklogItemRef(backlog_item_id="b1"),
            RemediationClosureBacklogItemRef(backlog_item_id="b1"),
        ),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert report.state is RemediationClosureState.BLOCKED
    assert RemediationClosureReasonCode.DUPLICATE_ID in report.reason_codes


def test_duplicate_evidence_ids_fail_closed() -> None:
    inp = RemediationClosureInput(
        backlog_item_refs=(
            RemediationClosureBacklogItemRef(backlog_item_id="b1", item_state="acknowledged"),
        ),
        evidence_summaries=(
            RemediationClosureEvidenceSummary(evidence_summary_id="es1", backlog_item_id="b1"),
            RemediationClosureEvidenceSummary(evidence_summary_id="es1", backlog_item_id="b1"),
        ),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert report.state is RemediationClosureState.BLOCKED


def test_duplicate_closure_ids_fail_closed() -> None:
    inp = RemediationClosureInput(
        backlog_item_refs=(
            RemediationClosureBacklogItemRef(backlog_item_id="b1", item_state="acknowledged"),
        ),
        closure_declarations=(
            RemediationClosureDeclaration(closure_id="c1", backlog_item_id="b1", generated_at=NOW),
            RemediationClosureDeclaration(closure_id="c1", backlog_item_id="b1", generated_at=NOW),
        ),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert report.state is RemediationClosureState.BLOCKED


def test_duplicate_review_ids_fail_closed() -> None:
    inp = RemediationClosureInput(
        backlog_item_refs=(
            RemediationClosureBacklogItemRef(backlog_item_id="b1", item_state="acknowledged"),
        ),
        closure_declarations=(
            RemediationClosureDeclaration(closure_id="c1", backlog_item_id="b1", generated_at=NOW),
        ),
        review_records=(
            RemediationClosureReviewRecord(review_id="r1", closure_id="c1", generated_at=NOW),
            RemediationClosureReviewRecord(review_id="r1", closure_id="c1", generated_at=NOW),
        ),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert report.state is RemediationClosureState.BLOCKED


def test_duplicate_link_ids_fail_closed() -> None:
    inp = RemediationClosureInput(
        backlog_item_refs=(
            RemediationClosureBacklogItemRef(backlog_item_id="b1", item_state="acknowledged"),
        ),
        closure_declarations=(
            RemediationClosureDeclaration(closure_id="c1", backlog_item_id="b1", generated_at=NOW),
        ),
        links=(
            RemediationClosureLink(link_id="l1", closure_id="c1", backlog_item_id="b1", generated_at=NOW),
            RemediationClosureLink(link_id="l1", closure_id="c1", backlog_item_id="b1", generated_at=NOW),
        ),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert report.state is RemediationClosureState.BLOCKED


def test_orphan_evidence_summary() -> None:
    inp = RemediationClosureInput(
        backlog_item_refs=(
            RemediationClosureBacklogItemRef(backlog_item_id="b1", item_state="acknowledged"),
        ),
        evidence_summaries=(
            RemediationClosureEvidenceSummary(evidence_summary_id="es1", backlog_item_id="b2"),
        ),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert any(issue.issue_type is RemediationClosureIssueType.ORPHAN_EVIDENCE for issue in report.issues)


def test_orphan_closure_declaration() -> None:
    inp = RemediationClosureInput(
        backlog_item_refs=(
            RemediationClosureBacklogItemRef(backlog_item_id="b1", item_state="acknowledged"),
        ),
        closure_declarations=(
            RemediationClosureDeclaration(closure_id="c1", backlog_item_id="b2", generated_at=NOW),
        ),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert any(issue.issue_type is RemediationClosureIssueType.ORPHAN_CLOSURE for issue in report.issues)


def test_orphan_review_record() -> None:
    inp = RemediationClosureInput(
        backlog_item_refs=(
            RemediationClosureBacklogItemRef(backlog_item_id="b1", item_state="acknowledged"),
        ),
        closure_declarations=(
            RemediationClosureDeclaration(closure_id="c1", backlog_item_id="b1", generated_at=NOW),
        ),
        review_records=(
            RemediationClosureReviewRecord(review_id="r1", closure_id="c2", generated_at=NOW),
        ),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert any(issue.issue_type is RemediationClosureIssueType.ORPHAN_REVIEW for issue in report.issues)


def test_orphan_link() -> None:
    inp = RemediationClosureInput(
        backlog_item_refs=(
            RemediationClosureBacklogItemRef(backlog_item_id="b1", item_state="acknowledged"),
        ),
        closure_declarations=(
            RemediationClosureDeclaration(closure_id="c1", backlog_item_id="b1", generated_at=NOW),
        ),
        links=(
            RemediationClosureLink(link_id="l1", closure_id="c2", backlog_item_id="b1", generated_at=NOW),
        ),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert any(issue.issue_type is RemediationClosureIssueType.ORPHAN_LINK for issue in report.issues)


def test_conflicting_review_outcomes() -> None:
    inp = RemediationClosureInput(
        backlog_item_refs=(
            RemediationClosureBacklogItemRef(backlog_item_id="b1", item_state="acknowledged"),
        ),
        evidence_summaries=(
            RemediationClosureEvidenceSummary(evidence_summary_id="es1", backlog_item_id="b1", coverage_state="covered"),
        ),
        closure_declarations=(
            RemediationClosureDeclaration(
                closure_id="c1", backlog_item_id="b1", evidence_summary_id="es1",
                declared_by="alice", reviewed_by="bob", closed_at=NOW, rationale="Done", generated_at=NOW,
            ),
        ),
        review_records=(
            RemediationClosureReviewRecord(review_id="r1", closure_id="c1", outcome="accepted", reviewer="bob", generated_at=NOW),
            RemediationClosureReviewRecord(review_id="r2", closure_id="c1", outcome="rejected", reviewer="alice", generated_at=NOW),
        ),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert any(issue.issue_type is RemediationClosureIssueType.CONFLICTING_REVIEW for issue in report.issues)
    # Precedence: rejected review wins over disputed/conflicting review because a rejected review exists.
    assert report.closure_results[0].record_state is RemediationClosureRecordState.REJECTED


def test_missing_evidence_when_required_blocks() -> None:
    inp = RemediationClosureInput(
        backlog_item_refs=(
            RemediationClosureBacklogItemRef(backlog_item_id="b1", item_state="acknowledged"),
        ),
        closure_declarations=(
            RemediationClosureDeclaration(
                closure_id="c1", backlog_item_id="b1", evidence_summary_id="",
                declared_by="alice", reviewed_by="bob", closed_at=NOW, rationale="Done", generated_at=NOW,
            ),
        ),
        config=RemediationClosureConfig(require_evidence_for_closure=True),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    missing = [issue for issue in report.issues if issue.issue_type is RemediationClosureIssueType.MISSING_EVIDENCE]
    assert missing
    assert all(issue.severity is RemediationClosureSeverity.BLOCKING for issue in missing)
    assert report.closure_results[0].record_state is RemediationClosureRecordState.BLOCKED
    assert report.state is RemediationClosureState.BLOCKED


def test_missing_evidence_when_not_required_is_non_blocking() -> None:
    inp = RemediationClosureInput(
        backlog_item_refs=(
            RemediationClosureBacklogItemRef(backlog_item_id="b1", item_state="acknowledged"),
        ),
        closure_declarations=(
            RemediationClosureDeclaration(
                closure_id="c1", backlog_item_id="b1", evidence_summary_id="",
                declared_by="alice", reviewed_by="bob", closed_at=NOW, rationale="Done", generated_at=NOW,
            ),
        ),
        config=RemediationClosureConfig(require_evidence_for_closure=False, require_review=False),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    assert report.state is RemediationClosureState.OK
    missing_issues = [issue for issue in report.issues if issue.issue_type is RemediationClosureIssueType.MISSING_EVIDENCE]
    assert all(issue.severity is RemediationClosureSeverity.INFO for issue in missing_issues)


def test_rejected_and_pending_review_detected() -> None:
    rejected = build_remediation_closure_report(
        RemediationClosureInput(
            backlog_item_refs=(
                RemediationClosureBacklogItemRef(backlog_item_id="b1", item_state="acknowledged"),
            ),
            evidence_summaries=(
                RemediationClosureEvidenceSummary(evidence_summary_id="es1", backlog_item_id="b1", coverage_state="covered"),
            ),
            closure_declarations=(
                RemediationClosureDeclaration(
                    closure_id="c1", backlog_item_id="b1", evidence_summary_id="es1",
                    declared_by="alice", reviewed_by="bob", closed_at=NOW, rationale="Done", generated_at=NOW,
                ),
            ),
            review_records=(
                RemediationClosureReviewRecord(review_id="r1", closure_id="c1", outcome="rejected", reviewer="bob", generated_at=NOW),
            ),
            generated_at=NOW,
        )
    )
    pending = build_remediation_closure_report(
        RemediationClosureInput(
            backlog_item_refs=(
                RemediationClosureBacklogItemRef(backlog_item_id="b1", item_state="acknowledged"),
            ),
            evidence_summaries=(
                RemediationClosureEvidenceSummary(evidence_summary_id="es1", backlog_item_id="b1", coverage_state="covered"),
            ),
            closure_declarations=(
                RemediationClosureDeclaration(
                    closure_id="c1", backlog_item_id="b1", evidence_summary_id="es1",
                    declared_by="alice", reviewed_by="bob", closed_at=NOW, rationale="Done", generated_at=NOW,
                ),
            ),
            review_records=(
                RemediationClosureReviewRecord(review_id="r1", closure_id="c1", outcome="pending", reviewer="bob", generated_at=NOW),
            ),
            config=RemediationClosureConfig(require_review=True),
            generated_at=NOW,
        )
    )
    assert rejected.closure_results[0].record_state is RemediationClosureRecordState.REJECTED
    assert pending.closure_results[0].record_state is RemediationClosureRecordState.PENDING_REVIEW


# ---------------------------------------------------------------------------
# Backlog item state interactions
# ---------------------------------------------------------------------------


def test_closure_on_blocked_item_emits_blocking_issue() -> None:
    inp = RemediationClosureInput(
        backlog_item_refs=(
            RemediationClosureBacklogItemRef(backlog_item_id="b1", item_state="blocked"),
        ),
        closure_declarations=(
            RemediationClosureDeclaration(closure_id="c1", backlog_item_id="b1", generated_at=NOW),
        ),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    blocking = [issue for issue in report.issues if issue.issue_type is RemediationClosureIssueType.BLOCKED_BACKLOG_ITEM]
    assert blocking
    assert all(issue.severity is RemediationClosureSeverity.BLOCKING for issue in blocking)
    assert report.closure_results[0].record_state is RemediationClosureRecordState.BLOCKED
    assert report.state is RemediationClosureState.BLOCKED


def test_closure_on_open_item_emits_blocking_issue() -> None:
    inp = RemediationClosureInput(
        backlog_item_refs=(
            RemediationClosureBacklogItemRef(backlog_item_id="b1", item_state="open"),
        ),
        closure_declarations=(
            RemediationClosureDeclaration(closure_id="c1", backlog_item_id="b1", generated_at=NOW),
        ),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    blocking = [issue for issue in report.issues if issue.issue_type is RemediationClosureIssueType.OPEN_BACKLOG_ITEM]
    assert blocking
    assert all(issue.severity is RemediationClosureSeverity.BLOCKING for issue in blocking)
    assert report.closure_results[0].record_state is RemediationClosureRecordState.BLOCKED
    assert report.state is RemediationClosureState.BLOCKED


def test_closure_on_conflicting_item_emits_blocking_issue() -> None:
    inp = RemediationClosureInput(
        backlog_item_refs=(
            RemediationClosureBacklogItemRef(backlog_item_id="b1", item_state="conflicting"),
        ),
        closure_declarations=(
            RemediationClosureDeclaration(closure_id="c1", backlog_item_id="b1", generated_at=NOW),
        ),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    blocking = [issue for issue in report.issues if issue.issue_type is RemediationClosureIssueType.CONFLICTING_BACKLOG_ITEM]
    assert blocking
    assert all(issue.severity is RemediationClosureSeverity.BLOCKING for issue in blocking)
    assert report.closure_results[0].record_state is RemediationClosureRecordState.BLOCKED
    assert report.state is RemediationClosureState.BLOCKED


def test_closure_for_acknowledged_deferred_not_applicable_is_safe() -> None:
    for state in ("acknowledged", "deferred", "not_applicable"):
        inp = RemediationClosureInput(
            backlog_item_refs=(
                RemediationClosureBacklogItemRef(backlog_item_id="b1", item_state=state),
            ),
            generated_at=NOW,
        )
        report = build_remediation_closure_report(inp)
        assert report.state is not RemediationClosureState.BLOCKED
        assert report.state is not RemediationClosureState.DEGRADED


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def test_aggregation_non_strict_blocked_degraded_ok() -> None:
    # Unsafe content forces report-level BLOCKED.
    blocked = build_remediation_closure_report(
        RemediationClosureInput(
            backlog_item_refs=(
                RemediationClosureBacklogItemRef(backlog_item_id="b1", item_state="acknowledged"),
            ),
            closure_declarations=(
                RemediationClosureDeclaration(
                    closure_id="c1", backlog_item_id="b1", evidence_summary_id="es1",
                    declared_by="alice", reviewed_by="bob", closed_at=NOW, rationale="Done", generated_at=NOW,
                ),
            ),
            metadata={"close now": "yes"},
            generated_at=NOW,
        )
    )
    assert blocked.state is RemediationClosureState.BLOCKED

    # An orphan evidence summary produces an advisory-only issue and DEGRADED report state.
    degraded = build_remediation_closure_report(
        RemediationClosureInput(
            backlog_item_refs=(
                RemediationClosureBacklogItemRef(backlog_item_id="b1", item_state="acknowledged"),
            ),
            evidence_summaries=(
                RemediationClosureEvidenceSummary(evidence_summary_id="es1", backlog_item_id="b2", coverage_state="covered"),
            ),
            generated_at=NOW,
        )
    )
    assert degraded.state is RemediationClosureState.DEGRADED

    # Clean input with no blocking or advisory issues produces OK.
    ok = build_remediation_closure_report(_build_full_input())
    assert ok.state is RemediationClosureState.OK


def test_aggregation_strict_degraded_becomes_blocked() -> None:
    degraded = build_remediation_closure_report(
        RemediationClosureInput(
            backlog_item_refs=(
                RemediationClosureBacklogItemRef(backlog_item_id="b1", item_state="acknowledged"),
            ),
            closure_declarations=(
                RemediationClosureDeclaration(
                    closure_id="c1", backlog_item_id="b1", evidence_summary_id="",
                    declared_by="", reviewed_by="", closed_at=NOW, rationale="", generated_at=NOW,
                ),
            ),
            config=RemediationClosureConfig(strict=True, require_closure_metadata=True, require_evidence_for_closure=False),
            generated_at=NOW,
        )
    )
    assert degraded.state is RemediationClosureState.BLOCKED


# ---------------------------------------------------------------------------
# Unsafe content
# ---------------------------------------------------------------------------


def test_unsafe_content_blocks_fail_closed() -> None:
    inp = _build_full_input()
    unsafe = RemediationClosureInput(
        backlog_item_refs=inp.backlog_item_refs,
        evidence_summaries=inp.evidence_summaries,
        closure_declarations=inp.closure_declarations,
        review_records=inp.review_records,
        links=inp.links,
        metadata={"close now": "yes"},
        generated_at=NOW,
    )
    report = build_remediation_closure_report(unsafe)
    assert report.state is RemediationClosureState.BLOCKED


def test_forbidden_terms_are_multi_word_phrases() -> None:
    for term in FORBIDDEN_REMEDIATION_CLOSURE_TERMS:
        assert " " in term, f"forbidden term must be multi-word: {term}"


def test_false_positive_phrases_do_not_block() -> None:
    examples = [
        "pending approval from security team",
        "certification body",
        "no recommendation needed",
        "signal processing",
        "no signal detected",
    ]
    for phrase in examples:
        inp = RemediationClosureInput(
            backlog_item_refs=(
                RemediationClosureBacklogItemRef(backlog_item_id="b1", item_state="acknowledged"),
            ),
            closure_declarations=(
                RemediationClosureDeclaration(
                    closure_id="c1", backlog_item_id="b1", evidence_summary_id="",
                    declared_by="alice", reviewed_by="bob", closed_at=NOW, rationale=phrase, generated_at=NOW,
                ),
            ),
            config=RemediationClosureConfig(require_evidence_for_closure=False, require_review=False),
            generated_at=NOW,
        )
        report = build_remediation_closure_report(inp)
        assert report.state is RemediationClosureState.OK, f"phrase blocked unexpectedly: {phrase}"


# ---------------------------------------------------------------------------
# Determinism and mutation
# ---------------------------------------------------------------------------


def test_deterministic_dict_and_json_text() -> None:
    inp = _build_full_input()
    r1 = build_remediation_closure_report(inp)
    r2 = build_remediation_closure_report(inp)
    assert remediation_closure_report_to_dict(r1) == remediation_closure_report_to_dict(r2)
    assert remediation_closure_report_to_json_text(r1) == remediation_closure_report_to_json_text(r2)


def test_deterministic_csv_and_markdown_text() -> None:
    inp = _build_full_input()
    r1 = build_remediation_closure_report(inp)
    r2 = build_remediation_closure_report(inp)
    assert remediation_closure_report_to_csv_text(r1) == remediation_closure_report_to_csv_text(r2)
    assert remediation_closure_report_to_markdown_text(r1) == remediation_closure_report_to_markdown_text(r2)


def test_issue_and_closure_result_ids_are_stable() -> None:
    inp = _build_full_input()
    r1 = build_remediation_closure_report(inp)
    r2 = build_remediation_closure_report(inp)
    assert [r.closure_result_id for r in r1.closure_results] == [r.closure_result_id for r in r2.closure_results]
    assert [i.issue_id for i in r1.issues] == [i.issue_id for i in r2.issues]


def test_input_collections_not_mutated() -> None:
    inp = _build_full_input()
    original = {
        "backlog": list(inp.backlog_item_refs),
        "evidence": list(inp.evidence_summaries),
        "closures": list(inp.closure_declarations),
        "reviews": list(inp.review_records),
        "links": list(inp.links),
    }
    build_remediation_closure_report(inp)
    assert list(inp.backlog_item_refs) == original["backlog"]
    assert list(inp.evidence_summaries) == original["evidence"]
    assert list(inp.closure_declarations) == original["closures"]
    assert list(inp.review_records) == original["reviews"]
    assert list(inp.links) == original["links"]


# ---------------------------------------------------------------------------
# Public exports and safety boundaries
# ---------------------------------------------------------------------------


def test_public_exports_available() -> None:
    from hunter import remediation_closure as rc

    assert hasattr(rc, "build_remediation_closure_report")
    assert hasattr(rc, "remediation_closure_report_to_dict")
    assert hasattr(rc, "remediation_closure_report_to_json_text")
    assert hasattr(rc, "remediation_closure_report_to_csv_text")
    assert hasattr(rc, "remediation_closure_report_to_markdown_text")
    assert hasattr(rc, "write_remediation_closure_report")


def test_markdown_safety_boundaries() -> None:
    report = build_remediation_closure_report(_build_full_input())
    text = remediation_closure_report_to_markdown_text(report)
    lower = text.lower()
    assert "audit-only" in lower or "human-audit" in lower
    assert "research" in lower
    assert "not approval" in lower or "not an approval" in lower
    assert "certification" in lower or "production readiness" in lower


def test_markdown_no_executable_instructions() -> None:
    report = build_remediation_closure_report(_build_full_input())
    text = remediation_closure_report_to_markdown_text(report)
    lower = text.lower()
    for term in (
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
    ):
        assert term not in lower, f"forbidden executable/trading term in markdown: {term}"


def test_markdown_no_live_trading_or_exchange_semantics() -> None:
    report = build_remediation_closure_report(_build_full_input())
    text = remediation_closure_report_to_markdown_text(report)
    lower = text.lower()
    assert "binance" not in lower
    assert "freqtrade" not in lower
    assert "exchange" not in lower


# ---------------------------------------------------------------------------
# Opaque references
# ---------------------------------------------------------------------------


def test_opaque_refs_serialized_as_strings_not_validated() -> None:
    report = build_remediation_closure_report(
        RemediationClosureInput(
            backlog_item_refs=(
                RemediationClosureBacklogItemRef(
                    backlog_item_id="b1",
                    item_state="acknowledged",
                    description="references /bucket/report.md and s3://audit-bucket/closures/",
                ),
            ),
            closure_declarations=(
                RemediationClosureDeclaration(
                    closure_id="c1",
                    backlog_item_id="b1",
                    evidence_summary_id="",
                    declared_by="alice",
                    reviewed_by="bob",
                    closed_at=NOW,
                    rationale="Done",
                    evidence_link="s3://audit-bucket/evidence.pdf",
                    generated_at=NOW,
                ),
            ),
            config=RemediationClosureConfig(require_evidence_for_closure=False, require_review=False),
            generated_at=NOW,
        )
    )
    data = remediation_closure_report_to_dict(report)
    assert data["closure_declarations"][0]["evidence_link"] == "s3://audit-bucket/evidence.pdf"
    assert "s3://audit-bucket/evidence.pdf" in remediation_closure_report_to_json_text(report)
    assert "s3://audit-bucket/evidence.pdf" in remediation_closure_report_to_markdown_text(report)


def test_no_filesystem_scan_or_import_required() -> None:
    # The whole API is in-memory; no path from input is opened or traversed.
    report = build_remediation_closure_report(
        RemediationClosureInput(
            backlog_item_refs=(
                RemediationClosureBacklogItemRef(backlog_item_id="b1", item_state="acknowledged"),
            ),
            closure_declarations=(
                RemediationClosureDeclaration(
                    closure_id="c1", backlog_item_id="b1", evidence_summary_id="",
                    declared_by="alice", reviewed_by="bob", closed_at=NOW, rationale="Done", generated_at=NOW,
                ),
            ),
            config=RemediationClosureConfig(require_evidence_for_closure=False, require_review=False),
            generated_at=NOW,
        )
    )
    assert report.report_id
    assert not any(path in report.report_id for path in ("/tmp", "data", "reports"))
