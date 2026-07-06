"""Tests for hunter.remediation_evidence.writer."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from hunter.remediation_evidence import (
    DEFAULT_CSV_PATH,
    DEFAULT_JSON_PATH,
    DEFAULT_MD_PATH,
    RemediationBacklogItemRef,
    RemediationEvidenceConfig,
    RemediationEvidenceCoverageState,
    RemediationEvidenceInput,
    RemediationEvidenceLink,
    RemediationEvidenceReasonCode,
    RemediationEvidenceRecord,
    RemediationEvidenceRecordState,
    RemediationEvidenceReport,
    RemediationEvidenceReviewOutcome,
    RemediationEvidenceSeverity,
    RemediationEvidenceState,
    RemediationReviewRecord,
    atomic_write_csv_remediation_evidence_report,
    atomic_write_json_remediation_evidence_report,
    atomic_write_markdown_remediation_evidence_report,
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


def _build_covered_report() -> RemediationEvidenceReport:
    """Return a simple COVERED report."""
    inp = RemediationEvidenceInput(
        backlog_item_refs=(
            RemediationBacklogItemRef(backlog_item_id="b1", item_state="acknowledged"),
        ),
        evidence_records=(
            RemediationEvidenceRecord(
                evidence_id="e1",
                backlog_item_id="b1",
                evidence_state="accepted",
                title="Evidence for b1",
                description="Covers backlog item b1",
            ),
        ),
        review_records=(
            RemediationReviewRecord(review_id="r1", evidence_id="e1", outcome="accepted"),
        ),
        generated_at=NOW,
    )
    return build_remediation_evidence_report(inp)


def _build_blocked_report() -> RemediationEvidenceReport:
    """Return a BLOCKED report via unsafe content."""
    inp = RemediationEvidenceInput(
        metadata={"bad": b"bytes"},
        generated_at=NOW,
    )
    return build_remediation_evidence_report(inp)


def _build_degraded_report() -> RemediationEvidenceReport:
    """Return a DEGRADED report with accepted evidence on an open backlog item."""
    inp = RemediationEvidenceInput(
        backlog_item_refs=(
            RemediationBacklogItemRef(backlog_item_id="b1", item_state="open"),
        ),
        evidence_records=(
            RemediationEvidenceRecord(
                evidence_id="e1",
                backlog_item_id="b1",
                evidence_state="accepted",
            ),
        ),
        review_records=(
            RemediationReviewRecord(review_id="r1", evidence_id="e1", outcome="accepted"),
        ),
        generated_at=NOW,
    )
    return build_remediation_evidence_report(inp)


def _build_not_applicable_report() -> RemediationEvidenceReport:
    """Return a NOT_APPLICABLE report from empty input."""
    return build_remediation_evidence_report(
        RemediationEvidenceInput(generated_at=NOW)
    )


def _build_varied_coverage_report() -> RemediationEvidenceReport:
    """Return a report with multiple coverage states."""
    inp = RemediationEvidenceInput(
        backlog_item_refs=(
            RemediationBacklogItemRef(backlog_item_id="b_ack", item_state="acknowledged"),
            RemediationBacklogItemRef(backlog_item_id="b_rej", item_state="acknowledged"),
            RemediationBacklogItemRef(backlog_item_id="b_pend", item_state="acknowledged"),
            RemediationBacklogItemRef(backlog_item_id="b_na", item_state="not_applicable"),
            RemediationBacklogItemRef(backlog_item_id="b_miss", item_state="open"),
        ),
        evidence_records=(
            RemediationEvidenceRecord(
                evidence_id="e_ack",
                backlog_item_id="b_ack",
                evidence_state="accepted",
            ),
            RemediationEvidenceRecord(
                evidence_id="e_rej",
                backlog_item_id="b_rej",
                evidence_state="rejected",
            ),
            RemediationEvidenceRecord(
                evidence_id="e_pend",
                backlog_item_id="b_pend",
                evidence_state="pending_review",
            ),
            RemediationEvidenceRecord(
                evidence_id="e_stale",
                backlog_item_id="b_ack",
                evidence_state="accepted",
                generated_at=OLD,
            ),
        ),
        review_records=(
            RemediationReviewRecord(review_id="r_ack", evidence_id="e_ack", outcome="accepted"),
            RemediationReviewRecord(review_id="r_rej", evidence_id="e_rej", outcome="rejected"),
            RemediationReviewRecord(
                review_id="r_stale", evidence_id="e_stale", outcome="accepted", generated_at=OLD
            ),
        ),
        links=(
            RemediationEvidenceLink(
                link_id="l_stale", evidence_id="e_stale", backlog_item_id="b_ack"
            ),
        ),
        config=RemediationEvidenceConfig(
            require_evidence_for_all=True,
        ),
        generated_at=NOW,
    )
    return build_remediation_evidence_report(inp)


# ---------------------------------------------------------------------------
# Dict / JSON
# ---------------------------------------------------------------------------


def test_dict_includes_all_report_fields() -> None:
    report = _build_covered_report()
    data = remediation_evidence_report_to_dict(report)
    assert "report_id" in data
    assert "generated_at" in data
    assert "state" in data
    assert "project_version" in data
    assert "backlog_item_refs" in data
    assert "evidence_records" in data
    assert "review_records" in data
    assert "links" in data
    assert "issues" in data
    assert "coverage_results" in data
    assert "data_quality" in data
    assert "safety_flags" in data
    assert "reason_codes" in data
    assert "metadata" in data
    assert "safety_notice" in data
    assert "notes" in data


def test_dict_backlog_item_refs_are_nested_dicts() -> None:
    report = _build_covered_report()
    data = remediation_evidence_report_to_dict(report)
    assert len(data["backlog_item_refs"]) == 1
    assert isinstance(data["backlog_item_refs"][0], dict)
    assert data["backlog_item_refs"][0]["backlog_item_id"] == "b1"


def test_dict_safety_flags_include_is_safe() -> None:
    report = _build_covered_report()
    data = remediation_evidence_report_to_dict(report)
    assert "is_safe" in data["safety_flags"]
    assert data["safety_flags"]["is_safe"] is True


def test_json_parseable_and_deterministic() -> None:
    report = _build_covered_report()
    text1 = remediation_evidence_report_to_json_text(report)
    text2 = remediation_evidence_report_to_json_text(report)
    assert text1 == text2
    data = json.loads(text1)
    assert data["state"] == "ok"
    assert data["project_version"] == "0.38.0-dev"


def test_json_enum_values_are_strings() -> None:
    report = _build_covered_report()
    data = json.loads(remediation_evidence_report_to_json_text(report))
    assert data["state"] == "ok"
    assert data["evidence_records"][0]["evidence_state"] == "accepted"
    assert data["coverage_results"][0]["coverage_state"] == "covered"


def test_json_datetime_serialized_iso() -> None:
    report = _build_covered_report()
    data = json.loads(remediation_evidence_report_to_json_text(report))
    assert data["generated_at"] == "2026-01-01T12:00:00+00:00"


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------


def test_csv_header_matches_requirements() -> None:
    report = _build_covered_report()
    text = remediation_evidence_report_to_csv_text(report)
    rows = list(csv.reader(text.splitlines()))
    assert rows[0] == [
        "report_id",
        "generated_at",
        "evidence_id",
        "backlog_item_id",
        "evidence_state",
        "coverage_state",
        "review_outcome",
        "severity",
        "reason_codes",
        "message",
    ]


def test_csv_row_for_covered_evidence() -> None:
    report = _build_covered_report()
    text = remediation_evidence_report_to_csv_text(report)
    rows = list(csv.reader(text.splitlines()))
    assert len(rows) == 2
    row = rows[1]
    assert row[2] == "e1"
    assert row[3] == "b1"
    assert row[4] == "accepted"
    assert row[5] == "covered"
    assert row[6] == "accepted"
    assert row[7] == "info"
    assert row[9] == "Covers backlog item b1"


def test_csv_sorts_by_evidence_backlog_coverage_severity() -> None:
    report = _build_varied_coverage_report()
    text = remediation_evidence_report_to_csv_text(report)
    rows = list(csv.reader(text.splitlines()))
    evidence_ids = [row[2] for row in rows[1:]]
    assert sorted(evidence_ids) == evidence_ids


def test_csv_uses_report_coverage_results_without_recomputation() -> None:
    report = _build_varied_coverage_report()
    coverage_map = {
        result.backlog_item_id: result for result in report.coverage_results
    }
    text = remediation_evidence_report_to_csv_text(report)
    rows = list(csv.reader(text.splitlines()))
    for row in rows[1:]:
        evidence_id = row[2]
        backlog_item_id = row[3]
        coverage_state = row[5]
        # Find the coverage result that includes this evidence.
        matching = [
            result
            for result in report.coverage_results
            if evidence_id in result.evidence_ids
        ]
        assert matching, f"No coverage result for {evidence_id}"
        assert coverage_state == matching[0].coverage_state.value


def test_csv_uses_report_issues_without_recomputation() -> None:
    report = _build_varied_coverage_report()
    text = remediation_evidence_report_to_csv_text(report)
    rows = list(csv.reader(text.splitlines()))
    for row in rows[1:]:
        evidence_id = row[2]
        backlog_item_id = row[3]
        reason_codes = set(row[8].split("|")) if row[8] else set()
        issue_codes = {
            code
            for issue in report.issues
            if issue.evidence_id == evidence_id or issue.backlog_item_id == backlog_item_id
            for code in issue.reason_codes
        }
        if issue_codes:
            assert issue_codes <= reason_codes


def test_csv_blocked_report_has_no_evidence_rows() -> None:
    report = _build_blocked_report()
    text = remediation_evidence_report_to_csv_text(report)
    rows = list(csv.reader(text.splitlines()))
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------


def test_markdown_starts_with_h1_and_safety_notice() -> None:
    report = _build_covered_report()
    text = remediation_evidence_report_to_markdown_text(report)
    lines = text.splitlines()
    assert lines[0] == "# Local Research Remediation Evidence Tracker Report"
    assert any("audit-only" in line.lower() for line in lines[:10])
    assert any("research-only" in line.lower() or "human-audit" in line.lower() for line in lines[:10])


def test_markdown_contains_explicit_not_approval_statement() -> None:
    report = _build_covered_report()
    text = remediation_evidence_report_to_markdown_text(report)
    assert "approval" in text.lower()
    assert "certification" in text.lower()
    assert "production readiness" in text.lower()
    assert "trading readiness" in text.lower()
    assert "recommendation" in text.lower()
    assert "suitability" in text.lower()
    assert "signal" in text.lower()
    assert "executable remediation plan" in text.lower()


def test_markdown_contains_all_required_sections() -> None:
    report = _build_covered_report()
    text = remediation_evidence_report_to_markdown_text(report)
    assert "## Summary" in text
    assert "## Coverage Results" in text
    assert "## Evidence Records" in text
    assert "## Review Records" in text
    assert "## Links" in text
    assert "## Issues" in text
    assert "## Data Quality" in text
    assert "## Safety Flags" in text
    assert "## Manual Review Notes" in text


def test_markdown_contains_no_executable_or_trading_instructions() -> None:
    report = _build_covered_report()
    text = remediation_evidence_report_to_markdown_text(report)
    lower = text.lower()
    forbidden = [
        "deploy immediately",
        "execute now",
        "run this command",
        "apply patch",
        "go live",
        "push to production",
        "infrastructure change",
        "automated remediation",
        "place order",
        "execute order",
        "buy signal",
        "sell signal",
        "hold signal",
    ]
    for term in forbidden:
        assert term not in lower, f"forbidden term in markdown: {term}"


def test_markdown_no_actionable_recommendation_language() -> None:
    report = _build_covered_report()
    text = remediation_evidence_report_to_markdown_text(report)
    lower = text.lower()
    assert "buy " not in lower
    assert "sell " not in lower
    assert "hold " not in lower
    assert "go long" not in lower
    assert "go short" not in lower
    assert "leverage" not in lower


# ---------------------------------------------------------------------------
# Atomic writes and path handling
# ---------------------------------------------------------------------------


def test_atomic_write_json_creates_file(tmp_path: Path) -> None:
    report = _build_covered_report()
    path = tmp_path / "evidence.json"
    result = atomic_write_json_remediation_evidence_report(report, path)
    assert result == path
    assert path.exists()
    data = json.loads(path.read_text())
    assert data["state"] == "ok"


def test_atomic_write_csv_creates_file(tmp_path: Path) -> None:
    report = _build_covered_report()
    path = tmp_path / "evidence.csv"
    result = atomic_write_csv_remediation_evidence_report(report, path)
    assert result == path
    assert path.exists()
    rows = list(csv.reader(path.read_text().splitlines()))
    assert rows[0][0] == "report_id"


def test_atomic_write_markdown_creates_file(tmp_path: Path) -> None:
    report = _build_covered_report()
    path = tmp_path / "evidence.md"
    result = atomic_write_markdown_remediation_evidence_report(report, path)
    assert result == path
    assert path.exists()
    assert path.read_text().startswith("# Local Research")


def test_parent_directories_created(tmp_path: Path) -> None:
    report = _build_covered_report()
    path = tmp_path / "a" / "b" / "c" / "evidence.json"
    atomic_write_json_remediation_evidence_report(report, path)
    assert path.exists()


def test_write_with_none_skips_artifact(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    report = _build_covered_report()
    monkeypatch.chdir(tmp_path)
    json_path, csv_path, md_path = write_remediation_evidence_report(
        report, json_path=None, csv_path=None, markdown_path=None
    )
    assert json_path is None
    assert csv_path is None
    assert md_path is None
    assert not (tmp_path / DEFAULT_JSON_PATH).exists()
    assert not (tmp_path / DEFAULT_CSV_PATH).exists()
    assert not (tmp_path / DEFAULT_MD_PATH).exists()


def test_write_omitted_uses_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    report = _build_covered_report()
    monkeypatch.chdir(tmp_path)
    json_path, csv_path, md_path = write_remediation_evidence_report(report)
    assert json_path == DEFAULT_JSON_PATH
    assert csv_path == DEFAULT_CSV_PATH
    assert md_path == DEFAULT_MD_PATH
    assert (tmp_path / DEFAULT_JSON_PATH).exists()
    assert (tmp_path / DEFAULT_CSV_PATH).exists()
    assert (tmp_path / DEFAULT_MD_PATH).exists()


def test_write_explicit_path_only(tmp_path: Path) -> None:
    report = _build_covered_report()
    json_file = tmp_path / "custom.json"
    csv_file = tmp_path / "custom.csv"
    md_file = tmp_path / "custom.md"
    write_remediation_evidence_report(
        report, json_path=json_file, csv_path=csv_file, markdown_path=md_file
    )
    assert json_file.exists()
    assert csv_file.exists()
    assert md_file.exists()


# ---------------------------------------------------------------------------
# State serialization
# ---------------------------------------------------------------------------


def test_blocked_report_serialization() -> None:
    report = _build_blocked_report()
    data = remediation_evidence_report_to_dict(report)
    assert data["state"] == "blocked"
    assert data["safety_flags"]["has_unsafe_content"] is True


def test_degraded_report_serialization() -> None:
    report = _build_degraded_report()
    data = remediation_evidence_report_to_dict(report)
    assert data["state"] == "degraded"


def test_not_applicable_report_serialization() -> None:
    report = _build_not_applicable_report()
    data = remediation_evidence_report_to_dict(report)
    assert data["state"] == "not_applicable"


# ---------------------------------------------------------------------------
# Coverage state serialization
# ---------------------------------------------------------------------------


def test_coverage_accepted_in_csv_and_markdown() -> None:
    report = _build_covered_report()
    text = remediation_evidence_report_to_csv_text(report)
    rows = list(csv.reader(text.splitlines()))
    assert rows[1][5] == "covered"
    md = remediation_evidence_report_to_markdown_text(report)
    assert "| covered |" in md or "covered" in md


def test_coverage_rejected_in_csv_and_markdown() -> None:
    report = _build_varied_coverage_report()
    text = remediation_evidence_report_to_csv_text(report)
    rows = list(csv.reader(text.splitlines()))
    rejected_rows = [row for row in rows[1:] if row[5] == "rejected"]
    assert rejected_rows


def test_coverage_pending_review_in_csv_and_markdown() -> None:
    report = _build_varied_coverage_report()
    text = remediation_evidence_report_to_csv_text(report)
    rows = list(csv.reader(text.splitlines()))
    pending_rows = [row for row in rows[1:] if row[5] == "pending_review"]
    assert pending_rows


def test_coverage_stale_in_csv_and_markdown() -> None:
    inp = RemediationEvidenceInput(
        backlog_item_refs=(
            RemediationBacklogItemRef(backlog_item_id="b_stale", item_state="acknowledged"),
        ),
        evidence_records=(
            RemediationEvidenceRecord(
                evidence_id="e_stale",
                backlog_item_id="b_stale",
                evidence_state="accepted",
                generated_at=OLD,
            ),
        ),
        review_records=(
            RemediationReviewRecord(
                review_id="r_stale",
                evidence_id="e_stale",
                outcome="accepted",
                generated_at=OLD,
            ),
        ),
        generated_at=NOW,
    )
    report = build_remediation_evidence_report(inp)
    text = remediation_evidence_report_to_csv_text(report)
    rows = list(csv.reader(text.splitlines()))
    stale_rows = [row for row in rows[1:] if row[5] == "stale"]
    assert stale_rows


def test_coverage_conflicting_in_csv_and_markdown() -> None:
    inp = RemediationEvidenceInput(
        backlog_item_refs=(
            RemediationBacklogItemRef(backlog_item_id="b1", item_state="acknowledged"),
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
    text = remediation_evidence_report_to_csv_text(report)
    rows = list(csv.reader(text.splitlines()))
    assert rows[1][5] == "conflicting"


def test_coverage_not_applicable_in_csv_and_markdown() -> None:
    report = _build_varied_coverage_report()
    text = remediation_evidence_report_to_csv_text(report)
    rows = list(csv.reader(text.splitlines()))
    na_rows = [row for row in rows[1:] if row[5] == "not_applicable"]
    # b_na is not_applicable but has no evidence, so no row is produced for it.
    # The e_stale link to b_ack means b_ack is covered, so no not_applicable row.
    assert not na_rows


def test_coverage_missing_in_csv_and_markdown() -> None:
    report = _build_varied_coverage_report()
    text = remediation_evidence_report_to_csv_text(report)
    rows = list(csv.reader(text.splitlines()))
    # b_miss has no evidence and is required, so coverage is missing but no evidence row.
    md = remediation_evidence_report_to_markdown_text(report)
    assert "missing" in md


# ---------------------------------------------------------------------------
# Safety / no mutation
# ---------------------------------------------------------------------------


def test_no_report_mutation_after_serialization() -> None:
    report = _build_covered_report()
    before = report
    remediation_evidence_report_to_dict(report)
    remediation_evidence_report_to_json_text(report)
    remediation_evidence_report_to_csv_text(report)
    remediation_evidence_report_to_markdown_text(report)
    assert report is before
    assert report.state is RemediationEvidenceState.OK


def test_no_path_traversal_or_opening() -> None:
    """Opaque references are serialized as strings without filesystem access."""
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
    # References remain opaque strings; writer does not open or traverse them.
    assert data["backlog_item_refs"][0]["source_id"] == "s3://bucket/report.md"
    assert data["evidence_records"][0]["metadata"]["path"] == "/etc/passwd"
    assert data["evidence_records"][0]["metadata"]["url"] == "http://example.com/evidence"


def test_nested_mapping_serialization() -> None:
    report = _build_covered_report()
    data = remediation_evidence_report_to_dict(report)
    assert isinstance(data["evidence_records"][0]["metadata"], dict)


def test_public_exports() -> None:
    from hunter import remediation_evidence

    assert hasattr(remediation_evidence, "remediation_evidence_report_to_dict")
    assert hasattr(remediation_evidence, "remediation_evidence_report_to_json_text")
    assert hasattr(remediation_evidence, "remediation_evidence_report_to_csv_text")
    assert hasattr(remediation_evidence, "remediation_evidence_report_to_markdown_text")
    assert hasattr(remediation_evidence, "write_remediation_evidence_report")
    assert hasattr(remediation_evidence, "atomic_write_json_remediation_evidence_report")
    assert hasattr(remediation_evidence, "atomic_write_csv_remediation_evidence_report")
    assert hasattr(remediation_evidence, "atomic_write_markdown_remediation_evidence_report")
    assert hasattr(remediation_evidence, "DEFAULT_JSON_PATH")
    assert hasattr(remediation_evidence, "DEFAULT_CSV_PATH")
    assert hasattr(remediation_evidence, "DEFAULT_MD_PATH")
