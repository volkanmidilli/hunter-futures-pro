"""Integration tests for hunter.remediation_evidence package. MVP-38 Step 3.

These tests exercise the full public API from in-memory input through engine
report construction to writer artifact serialization. They use only the public
exports from hunter.remediation_evidence and do not modify source internals.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

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
    RemediationEvidenceSeverity,
    RemediationEvidenceState,
    RemediationReviewRecord,
    build_remediation_evidence_report,
    remediation_evidence_report_to_csv_text,
    remediation_evidence_report_to_dict,
    remediation_evidence_report_to_json_text,
    remediation_evidence_report_to_markdown_text,
    write_remediation_evidence_report,
)
from hunter.remediation_backlog.models import RemediationBacklogItemState


NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
OLD = NOW - timedelta(days=31)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_full_input() -> RemediationEvidenceInput:
    """Return a representative input with all collection types populated."""
    return RemediationEvidenceInput(
        backlog_item_refs=(
            RemediationBacklogItemRef(
                backlog_item_id="b1",
                source_id="src-a",
                finding_id="f1",
                item_state="acknowledged",
                severity="advisory",
                priority="p1",
                title="Backlog item one",
                description="First backlog item",
                generated_at=NOW,
                metadata={"owner": "alice"},
            ),
        ),
        evidence_records=(
            RemediationEvidenceRecord(
                evidence_id="e1",
                backlog_item_id="b1",
                title="Evidence one",
                description="Supports b1",
                evidence_state="accepted",
                generated_at=NOW,
                metadata={"reviewer": "bob"},
            ),
        ),
        review_records=(
            RemediationReviewRecord(
                review_id="r1",
                evidence_id="e1",
                outcome="accepted",
                reviewer="bob",
                reviewed_at=NOW,
                generated_at=NOW,
                note="Looks good",
            ),
        ),
        links=(
            RemediationEvidenceLink(
                link_id="l1",
                evidence_id="e1",
                backlog_item_id="b1",
                link_type="supports",
                generated_at=NOW,
            ),
        ),
        config=RemediationEvidenceConfig(
            require_review=False,
            require_evidence_for_all=False,
        ),
        project_version="0.38.0-dev",
        metadata={"env": "test"},
        generated_at=NOW,
    )


# ---------------------------------------------------------------------------
# End-to-end successful report
# ---------------------------------------------------------------------------


def test_end_to_end_report_structure() -> None:
    inp = _build_full_input()
    report = build_remediation_evidence_report(inp)
    assert report.report_id
    assert report.generated_at == NOW
    assert report.state is RemediationEvidenceState.OK
    assert report.project_version == "0.38.0-dev"
    assert len(report.backlog_item_refs) == 1
    assert len(report.evidence_records) == 1
    assert len(report.review_records) == 1
    assert len(report.links) == 1
    assert report.coverage_results
    assert report.data_quality.total_backlog_item_refs == 1
    assert report.data_quality.total_evidence_records == 1
    assert report.data_quality.total_review_records == 1
    assert report.data_quality.total_links == 1
    assert report.safety_flags.is_safe is True


def test_end_to_end_coverage_is_covered() -> None:
    inp = _build_full_input()
    report = build_remediation_evidence_report(inp)
    assert len(report.coverage_results) == 1
    assert report.coverage_results[0].coverage_state is RemediationEvidenceCoverageState.COVERED
    assert report.coverage_results[0].backlog_item_id == "b1"


def test_end_to_end_reason_codes_and_issues() -> None:
    inp = _build_full_input()
    report = build_remediation_evidence_report(inp)
    # Acknowledged backlog item emits an INFO issue.
    assert any(issue.issue_type is RemediationEvidenceIssueType.ACKNOWLEDGED_BACKLOG_ITEM for issue in report.issues)
    assert all(issue.severity is RemediationEvidenceSeverity.INFO for issue in report.issues)
    assert RemediationEvidenceReasonCode.OK in report.reason_codes


# ---------------------------------------------------------------------------
# Writer end-to-end
# ---------------------------------------------------------------------------


def test_writer_end_to_end_creates_all_files(tmp_path: Path) -> None:
    report = build_remediation_evidence_report(_build_full_input())
    json_path = tmp_path / "report.json"
    csv_path = tmp_path / "report.csv"
    md_path = tmp_path / "report.md"
    write_remediation_evidence_report(
        report, json_path=json_path, csv_path=csv_path, markdown_path=md_path
    )
    assert json_path.exists()
    assert csv_path.exists()
    assert md_path.exists()


def test_writer_json_parses_and_includes_all_collections(tmp_path: Path) -> None:
    report = build_remediation_evidence_report(_build_full_input())
    json_path = tmp_path / "report.json"
    write_remediation_evidence_report(report, json_path=json_path, csv_path=None, markdown_path=None)
    data = json.loads(json_path.read_text())
    assert data["state"] == "ok"
    assert len(data["backlog_item_refs"]) == 1
    assert len(data["evidence_records"]) == 1
    assert len(data["review_records"]) == 1
    assert len(data["links"]) == 1
    assert "data_quality" in data
    assert "safety_flags" in data
    assert "issues" in data
    assert "coverage_results" in data


def test_writer_csv_preserves_evidence_and_backlog_ids(tmp_path: Path) -> None:
    report = build_remediation_evidence_report(_build_full_input())
    csv_path = tmp_path / "report.csv"
    write_remediation_evidence_report(report, json_path=None, csv_path=csv_path, markdown_path=None)
    rows = list(csv.reader(csv_path.read_text().splitlines()))
    assert rows[0][0] == "report_id"
    assert any(row[2] == "e1" and row[3] == "b1" for row in rows[1:])


def test_writer_markdown_starts_with_h1_and_safety_notice(tmp_path: Path) -> None:
    report = build_remediation_evidence_report(_build_full_input())
    md_path = tmp_path / "report.md"
    write_remediation_evidence_report(report, json_path=None, csv_path=None, markdown_path=md_path)
    text = md_path.read_text()
    assert text.startswith("# Local Research Remediation Evidence Tracker Report")
    assert "audit-only" in text.lower() or "research-only" in text.lower()


# ---------------------------------------------------------------------------
# Empty / non-empty behavior
# ---------------------------------------------------------------------------


def test_empty_input_returns_not_applicable() -> None:
    inp = RemediationEvidenceInput(generated_at=NOW)
    report = build_remediation_evidence_report(inp)
    assert report.state is RemediationEvidenceState.NOT_APPLICABLE
    assert not report.issues
    assert not report.coverage_results


def test_non_empty_input_with_no_advisory_issues_returns_ok() -> None:
    inp = _build_full_input()
    report = build_remediation_evidence_report(inp)
    assert report.state is RemediationEvidenceState.OK


def test_info_and_not_applicable_do_not_block() -> None:
    inp = RemediationEvidenceInput(
        backlog_item_refs=(
            RemediationBacklogItemRef(backlog_item_id="b1", item_state="acknowledged"),
        ),
        generated_at=NOW,
    )
    report = build_remediation_evidence_report(inp)
    assert report.state is RemediationEvidenceState.OK
    assert all(issue.severity is RemediationEvidenceSeverity.INFO for issue in report.issues)


# ---------------------------------------------------------------------------
# Coverage states and precedence
# ---------------------------------------------------------------------------


def test_coverage_not_applicable_by_state() -> None:
    inp = RemediationEvidenceInput(
        backlog_item_refs=(
            RemediationBacklogItemRef(backlog_item_id="b1", item_state="not_applicable"),
        ),
        evidence_records=(
            RemediationEvidenceRecord(evidence_id="e1", backlog_item_id="b1", evidence_state="accepted"),
        ),
        generated_at=NOW,
    )
    report = build_remediation_evidence_report(inp)
    assert report.coverage_results[0].coverage_state is RemediationEvidenceCoverageState.NOT_APPLICABLE


def test_coverage_missing_for_required_item() -> None:
    inp = RemediationEvidenceInput(
        backlog_item_refs=(
            RemediationBacklogItemRef(backlog_item_id="b1", item_state="open"),
        ),
        config=RemediationEvidenceConfig(required_backlog_item_ids=("b1",)),
        generated_at=NOW,
    )
    report = build_remediation_evidence_report(inp)
    assert report.coverage_results[0].coverage_state is RemediationEvidenceCoverageState.MISSING


def test_coverage_conflicting_takes_precedence() -> None:
    inp = RemediationEvidenceInput(
        backlog_item_refs=(
            RemediationBacklogItemRef(backlog_item_id="b1", item_state="acknowledged"),
        ),
        evidence_records=(
            RemediationEvidenceRecord(evidence_id="e1", backlog_item_id="b1", evidence_state="rejected"),
        ),
        review_records=(
            RemediationReviewRecord(review_id="r1", evidence_id="e1", outcome="accepted"),
            RemediationReviewRecord(review_id="r2", evidence_id="e1", outcome="rejected"),
        ),
        generated_at=NOW,
    )
    report = build_remediation_evidence_report(inp)
    assert report.coverage_results[0].coverage_state is RemediationEvidenceCoverageState.CONFLICTING


def test_coverage_rejected_when_all_rejected() -> None:
    inp = RemediationEvidenceInput(
        backlog_item_refs=(
            RemediationBacklogItemRef(backlog_item_id="b1", item_state="acknowledged"),
        ),
        evidence_records=(
            RemediationEvidenceRecord(evidence_id="e1", backlog_item_id="b1", evidence_state="rejected"),
        ),
        generated_at=NOW,
    )
    report = build_remediation_evidence_report(inp)
    assert report.coverage_results[0].coverage_state is RemediationEvidenceCoverageState.REJECTED


def test_coverage_stale() -> None:
    inp = RemediationEvidenceInput(
        backlog_item_refs=(
            RemediationBacklogItemRef(backlog_item_id="b1", item_state="acknowledged"),
        ),
        evidence_records=(
            RemediationEvidenceRecord(
                evidence_id="e1",
                backlog_item_id="b1",
                evidence_state="accepted",
                generated_at=OLD,
            ),
        ),
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
    assert report.coverage_results[0].coverage_state is RemediationEvidenceCoverageState.STALE


def test_coverage_pending_review_without_accepted_review() -> None:
    inp = RemediationEvidenceInput(
        backlog_item_refs=(
            RemediationBacklogItemRef(backlog_item_id="b1", item_state="acknowledged"),
        ),
        evidence_records=(
            RemediationEvidenceRecord(evidence_id="e1", backlog_item_id="b1", evidence_state="accepted"),
        ),
        generated_at=NOW,
    )
    report = build_remediation_evidence_report(inp)
    assert report.coverage_results[0].coverage_state is RemediationEvidenceCoverageState.PENDING_REVIEW


def test_coverage_partial_fallback() -> None:
    inp = RemediationEvidenceInput(
        backlog_item_refs=(
            RemediationBacklogItemRef(backlog_item_id="b1", item_state="acknowledged"),
        ),
        evidence_records=(
            RemediationEvidenceRecord(evidence_id="e1", backlog_item_id="b1", evidence_state="accepted"),
            RemediationEvidenceRecord(evidence_id="e2", backlog_item_id="b1", evidence_state="pending_review"),
        ),
        review_records=(
            RemediationReviewRecord(review_id="r1", evidence_id="e1", outcome="accepted"),
        ),
        generated_at=NOW,
    )
    report = build_remediation_evidence_report(inp)
    # Accepted evidence exists, no rejected/conflicting/orphan, so COVERED wins.
    assert report.coverage_results[0].coverage_state is RemediationEvidenceCoverageState.COVERED


# ---------------------------------------------------------------------------
# Built-in detections
# ---------------------------------------------------------------------------


def test_duplicate_backlog_ids_blocked() -> None:
    inp = RemediationEvidenceInput(
        backlog_item_refs=(
            RemediationBacklogItemRef(backlog_item_id="b1"),
            RemediationBacklogItemRef(backlog_item_id="b1"),
        ),
        generated_at=NOW,
    )
    report = build_remediation_evidence_report(inp)
    assert report.state is RemediationEvidenceState.BLOCKED
    assert RemediationEvidenceReasonCode.DUPLICATE_ID in report.reason_codes


def test_duplicate_evidence_by_content_hash_detected() -> None:
    inp = RemediationEvidenceInput(
        backlog_item_refs=(
            RemediationBacklogItemRef(backlog_item_id="b1", item_state="acknowledged"),
        ),
        evidence_records=(
            RemediationEvidenceRecord(
                evidence_id="e1",
                backlog_item_id="b1",
                title="same",
                description="same",
                evidence_state="accepted",
            ),
            RemediationEvidenceRecord(
                evidence_id="e2",
                backlog_item_id="b1",
                title="same",
                description="same",
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
    assert any(issue.issue_type is RemediationEvidenceIssueType.DUPLICATE_EVIDENCE for issue in report.issues)


def test_orphan_evidence_review_and_link_detected() -> None:
    inp = RemediationEvidenceInput(
        backlog_item_refs=(
            RemediationBacklogItemRef(backlog_item_id="b1"),
        ),
        evidence_records=(
            RemediationEvidenceRecord(evidence_id="e1", backlog_item_id="b2", evidence_state="accepted"),
        ),
        review_records=(
            RemediationReviewRecord(review_id="r1", evidence_id="e2", outcome="accepted"),
        ),
        links=(
            RemediationEvidenceLink(link_id="l1", evidence_id="e_unknown", backlog_item_id="b1"),
        ),
        generated_at=NOW,
    )
    report = build_remediation_evidence_report(inp)
    issue_types = {issue.issue_type for issue in report.issues}
    assert RemediationEvidenceIssueType.ORPHAN_EVIDENCE in issue_types
    assert RemediationEvidenceIssueType.ORPHAN_REVIEW in issue_types
    assert RemediationEvidenceIssueType.ORPHAN_LINK in issue_types


def test_conflicting_reviews_blocked() -> None:
    inp = RemediationEvidenceInput(
        backlog_item_refs=(
            RemediationBacklogItemRef(backlog_item_id="b1"),
        ),
        evidence_records=(
            RemediationEvidenceRecord(evidence_id="e1", backlog_item_id="b1"),
        ),
        review_records=(
            RemediationReviewRecord(review_id="r1", evidence_id="e1", outcome="accepted"),
            RemediationReviewRecord(review_id="r2", evidence_id="e1", outcome="rejected"),
        ),
        generated_at=NOW,
    )
    report = build_remediation_evidence_report(inp)
    assert report.state is RemediationEvidenceState.BLOCKED
    assert any(issue.issue_type is RemediationEvidenceIssueType.CONFLICTING_REVIEW for issue in report.issues)


def test_stale_evidence_and_review_detected() -> None:
    inp = RemediationEvidenceInput(
        backlog_item_refs=(
            RemediationBacklogItemRef(backlog_item_id="b1", item_state="acknowledged"),
        ),
        evidence_records=(
            RemediationEvidenceRecord(
                evidence_id="e1",
                backlog_item_id="b1",
                evidence_state="accepted",
                generated_at=OLD,
            ),
        ),
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
    issue_types = {issue.issue_type for issue in report.issues}
    assert RemediationEvidenceIssueType.STALE_EVIDENCE in issue_types
    assert RemediationEvidenceIssueType.STALE_REVIEW in issue_types


def test_missing_evidence_for_required_item_detected() -> None:
    inp = RemediationEvidenceInput(
        backlog_item_refs=(
            RemediationBacklogItemRef(backlog_item_id="b1"),
        ),
        config=RemediationEvidenceConfig(
            require_evidence_for_all=True,
        ),
        generated_at=NOW,
    )
    report = build_remediation_evidence_report(inp)
    issue_types = {issue.issue_type for issue in report.issues}
    assert RemediationEvidenceIssueType.MISSING_EVIDENCE in issue_types


def test_missing_review_when_required_detected() -> None:
    inp = RemediationEvidenceInput(
        backlog_item_refs=(
            RemediationBacklogItemRef(backlog_item_id="b1"),
        ),
        evidence_records=(
            RemediationEvidenceRecord(evidence_id="e1", backlog_item_id="b1", evidence_state="accepted"),
        ),
        config=RemediationEvidenceConfig(
            require_review=True,
        ),
        generated_at=NOW,
    )
    report = build_remediation_evidence_report(inp)
    issue_types = {issue.issue_type for issue in report.issues}
    assert RemediationEvidenceIssueType.MISSING_REVIEW in issue_types


def test_rejected_and_pending_evidence_detected() -> None:
    inp = RemediationEvidenceInput(
        backlog_item_refs=(
            RemediationBacklogItemRef(backlog_item_id="b1", item_state="acknowledged"),
        ),
        evidence_records=(
            RemediationEvidenceRecord(evidence_id="e1", backlog_item_id="b1", evidence_state="rejected"),
            RemediationEvidenceRecord(evidence_id="e2", backlog_item_id="b1", evidence_state="pending_review"),
        ),
        generated_at=NOW,
    )
    report = build_remediation_evidence_report(inp)
    issue_types = {issue.issue_type for issue in report.issues}
    assert RemediationEvidenceIssueType.REJECTED_EVIDENCE in issue_types
    assert RemediationEvidenceIssueType.PENDING_REVIEW_EVIDENCE in issue_types


# ---------------------------------------------------------------------------
# Backlog item state interactions
# ---------------------------------------------------------------------------


def test_accepted_evidence_on_blocked_item_emits_advisory() -> None:
    inp = RemediationEvidenceInput(
        backlog_item_refs=(
            RemediationBacklogItemRef(backlog_item_id="b1", item_state="blocked"),
        ),
        evidence_records=(
            RemediationEvidenceRecord(evidence_id="e1", backlog_item_id="b1", evidence_state="accepted"),
        ),
        review_records=(
            RemediationReviewRecord(review_id="r1", evidence_id="e1", outcome="accepted"),
        ),
        generated_at=NOW,
    )
    report = build_remediation_evidence_report(inp)
    assert any(issue.issue_type is RemediationEvidenceIssueType.BLOCKED_BACKLOG_ITEM for issue in report.issues)
    assert report.state is RemediationEvidenceState.DEGRADED


def test_accepted_evidence_on_open_item_emits_advisory() -> None:
    inp = RemediationEvidenceInput(
        backlog_item_refs=(
            RemediationBacklogItemRef(backlog_item_id="b1", item_state="open"),
        ),
        evidence_records=(
            RemediationEvidenceRecord(evidence_id="e1", backlog_item_id="b1", evidence_state="accepted"),
        ),
        review_records=(
            RemediationReviewRecord(review_id="r1", evidence_id="e1", outcome="accepted"),
        ),
        generated_at=NOW,
    )
    report = build_remediation_evidence_report(inp)
    assert any(issue.issue_type is RemediationEvidenceIssueType.OPEN_BACKLOG_ITEM for issue in report.issues)
    assert report.state is RemediationEvidenceState.DEGRADED


def test_acknowledged_deferred_items_classified_safely() -> None:
    inp = RemediationEvidenceInput(
        backlog_item_refs=(
            RemediationBacklogItemRef(backlog_item_id="b1", item_state="acknowledged"),
            RemediationBacklogItemRef(backlog_item_id="b2", item_state="deferred"),
        ),
        generated_at=NOW,
    )
    report = build_remediation_evidence_report(inp)
    assert all(issue.severity is RemediationEvidenceSeverity.INFO for issue in report.issues)
    assert report.state is RemediationEvidenceState.OK


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def test_non_strict_blocked_over_degraded_over_ok() -> None:
    blocked = build_remediation_evidence_report(
        RemediationEvidenceInput(
            backlog_item_refs=(
                RemediationBacklogItemRef(backlog_item_id="b1"),
                RemediationBacklogItemRef(backlog_item_id="b1"),
            ),
            generated_at=NOW,
        )
    )
    degraded = build_remediation_evidence_report(
        RemediationEvidenceInput(
            backlog_item_refs=(
                RemediationBacklogItemRef(backlog_item_id="b1", item_state="open"),
            ),
            evidence_records=(
                RemediationEvidenceRecord(evidence_id="e1", backlog_item_id="b1", evidence_state="accepted"),
            ),
            review_records=(
                RemediationReviewRecord(review_id="r1", evidence_id="e1", outcome="accepted"),
            ),
            generated_at=NOW,
        )
    )
    ok = build_remediation_evidence_report(_build_full_input())
    assert blocked.state is RemediationEvidenceState.BLOCKED
    assert degraded.state is RemediationEvidenceState.DEGRADED
    assert ok.state is RemediationEvidenceState.OK


def test_strict_promotes_degraded_to_blocked() -> None:
    inp = RemediationEvidenceInput(
        backlog_item_refs=(
            RemediationBacklogItemRef(backlog_item_id="b1", item_state="open"),
        ),
        evidence_records=(
            RemediationEvidenceRecord(evidence_id="e1", backlog_item_id="b1", evidence_state="accepted"),
        ),
        review_records=(
            RemediationReviewRecord(review_id="r1", evidence_id="e1", outcome="accepted"),
        ),
        config=RemediationEvidenceConfig(strict=True),
        generated_at=NOW,
    )
    report = build_remediation_evidence_report(inp)
    assert report.state is RemediationEvidenceState.BLOCKED


# ---------------------------------------------------------------------------
# Unsafe content and forbidden terms
# ---------------------------------------------------------------------------


def test_unsafe_content_blocks_fail_closed() -> None:
    inp = RemediationEvidenceInput(
        metadata={"bad": b"bytes"},
        generated_at=NOW,
    )
    report = build_remediation_evidence_report(inp)
    assert report.state is RemediationEvidenceState.BLOCKED
    assert report.safety_flags.has_unsafe_content is True
    assert report.safety_flags.is_safe is False


def test_forbidden_term_blocks_fail_closed() -> None:
    inp = RemediationEvidenceInput(
        backlog_item_refs=(
            RemediationBacklogItemRef(backlog_item_id="b1", title="This is a buy signal"),
        ),
        generated_at=NOW,
    )
    report = build_remediation_evidence_report(inp)
    assert report.state is RemediationEvidenceState.BLOCKED
    assert report.safety_flags.has_forbidden_terms is True


@pytest.mark.parametrize(
    "phrase",
    [
        "pending approval from security team",
        "certification body",
        "no recommendation needed",
        "signal processing",
        "no signal detected",
    ],
)
def test_benign_phrases_do_not_block(phrase: str) -> None:
    inp = RemediationEvidenceInput(
        backlog_item_refs=(
            RemediationBacklogItemRef(backlog_item_id="b1", title=phrase),
        ),
        generated_at=NOW,
    )
    report = build_remediation_evidence_report(inp)
    assert report.state is not RemediationEvidenceState.BLOCKED


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_deterministic_text_outputs() -> None:
    inp = _build_full_input()
    report1 = build_remediation_evidence_report(inp)
    report2 = build_remediation_evidence_report(inp)
    assert report1.report_id == report2.report_id
    assert remediation_evidence_report_to_json_text(report1) == remediation_evidence_report_to_json_text(report2)
    assert remediation_evidence_report_to_csv_text(report1) == remediation_evidence_report_to_csv_text(report2)
    assert remediation_evidence_report_to_markdown_text(report1) == remediation_evidence_report_to_markdown_text(report2)


def test_deterministic_issue_and_coverage_ids() -> None:
    inp = _build_full_input()
    report1 = build_remediation_evidence_report(inp)
    report2 = build_remediation_evidence_report(inp)
    ids1 = {(issue.issue_id, issue.issue_type.value) for issue in report1.issues}
    ids2 = {(issue.issue_id, issue.issue_type.value) for issue in report2.issues}
    assert ids1 == ids2
    cov_ids1 = {result.coverage_id for result in report1.coverage_results}
    cov_ids2 = {result.coverage_id for result in report2.coverage_results}
    assert cov_ids1 == cov_ids2


# ---------------------------------------------------------------------------
# No mutation
# ---------------------------------------------------------------------------


def test_input_collections_not_mutated() -> None:
    refs = [
        RemediationBacklogItemRef(backlog_item_id="b2"),
        RemediationBacklogItemRef(backlog_item_id="b1"),
    ]
    inp = RemediationEvidenceInput(backlog_item_refs=refs, generated_at=NOW)
    original_ids = [r.backlog_item_id for r in refs]
    build_remediation_evidence_report(inp)
    write_remediation_evidence_report(
        build_remediation_evidence_report(inp),
        json_path=None,
        csv_path=None,
        markdown_path=None,
    )
    assert [r.backlog_item_id for r in refs] == original_ids


# ---------------------------------------------------------------------------
# Public exports and safety boundaries
# ---------------------------------------------------------------------------


def test_public_exports() -> None:
    from hunter import remediation_evidence

    assert hasattr(remediation_evidence, "build_remediation_evidence_report")
    assert hasattr(remediation_evidence, "write_remediation_evidence_report")
    assert hasattr(remediation_evidence, "remediation_evidence_report_to_json_text")
    assert hasattr(remediation_evidence, "remediation_evidence_report_to_csv_text")
    assert hasattr(remediation_evidence, "remediation_evidence_report_to_markdown_text")


def test_markdown_contains_safety_disclaimers() -> None:
    report = build_remediation_evidence_report(_build_full_input())
    text = remediation_evidence_report_to_markdown_text(report)
    assert "audit-only" in text.lower() or "research-only" in text.lower()
    assert "approval" in text.lower()
    assert "certification" in text.lower()
    assert "production readiness" in text.lower()
    assert "trading readiness" in text.lower()
    assert "recommendation" in text.lower()
    assert "suitability" in text.lower()
    assert "signal" in text.lower()
    assert "executable remediation plan" in text.lower()


def test_markdown_no_forbidden_action_terms() -> None:
    report = build_remediation_evidence_report(_build_full_input())
    text = remediation_evidence_report_to_markdown_text(report)
    lower = text.lower()
    for term in FORBIDDEN_REMEDIATION_EVIDENCE_TERMS:
        assert term not in lower, f"forbidden term in markdown: {term}"


# ---------------------------------------------------------------------------
# Opaque references
# ---------------------------------------------------------------------------


def test_opaque_refs_preserved_end_to_end() -> None:
    ref = RemediationBacklogItemRef(
        backlog_item_id="b1",
        source_id="s3://bucket/report.md",
        finding_id="finding-1",
        item_state="acknowledged",
    )
    rec = RemediationEvidenceRecord(
        evidence_id="e1",
        backlog_item_id="b1",
        metadata={"path": "/etc/passwd", "url": "http://example.com/evidence"},
    )
    inp = RemediationEvidenceInput(
        backlog_item_refs=(ref,),
        evidence_records=(rec,),
        review_records=(
            RemediationReviewRecord(review_id="r1", evidence_id="e1", outcome="accepted"),
        ),
        generated_at=NOW,
    )
    report = build_remediation_evidence_report(inp)
    data = remediation_evidence_report_to_dict(report)
    assert data["backlog_item_refs"][0]["source_id"] == "s3://bucket/report.md"
    assert data["evidence_records"][0]["metadata"]["path"] == "/etc/passwd"
    assert data["evidence_records"][0]["metadata"]["url"] == "http://example.com/evidence"
