"""Tests for hunter.remediation_closure.writer."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from hunter.remediation_closure import (
    DEFAULT_CSV_PATH,
    DEFAULT_JSON_PATH,
    DEFAULT_MD_PATH,
    RemediationClosureBacklogItemRef,
    RemediationClosureConfig,
    RemediationClosureDeclaration,
    RemediationClosureEvidenceSummary,
    RemediationClosureInput,
    RemediationClosureLink,
    RemediationClosureReasonCode,
    RemediationClosureRecordState,
    RemediationClosureReviewRecord,
    RemediationClosureSeverity,
    RemediationClosureState,
    atomic_write_csv_remediation_closure_report,
    atomic_write_json_remediation_closure_report,
    atomic_write_markdown_remediation_closure_report,
    build_remediation_closure_report,
    remediation_closure_report_to_csv_text,
    remediation_closure_report_to_dict,
    remediation_closure_report_to_json_text,
    remediation_closure_report_to_markdown_text,
    write_remediation_closure_report,
)

NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _build_closed_recorded_report() -> object:
    """Return a simple CLOSED_RECORDED report."""
    inp = RemediationClosureInput(
        backlog_item_refs=(
            RemediationClosureBacklogItemRef(backlog_item_id="b1", item_state="acknowledged"),
        ),
        evidence_summaries=(
            RemediationClosureEvidenceSummary(
                evidence_summary_id="es1",
                backlog_item_id="b1",
                coverage_state="covered",
            ),
        ),
        closure_declarations=(
            RemediationClosureDeclaration(
                closure_id="c1",
                backlog_item_id="b1",
                evidence_summary_id="es1",
                declared_by="alice",
                reviewed_by="bob",
            ),
        ),
        review_records=(
            RemediationClosureReviewRecord(review_id="r1", closure_id="c1", outcome="accepted"),
        ),
        generated_at=NOW,
    )
    return build_remediation_closure_report(inp)


def _build_blocked_report() -> object:
    """Return a BLOCKED report via unsafe content."""
    inp = RemediationClosureInput(
        metadata={"bad": b"bytes"},
        generated_at=NOW,
    )
    return build_remediation_closure_report(inp)


def _build_varied_report() -> object:
    """Return a report with multiple closure states."""
    inp = RemediationClosureInput(
        backlog_item_refs=(
            RemediationClosureBacklogItemRef(backlog_item_id="b_ack", item_state="acknowledged"),
            RemediationClosureBacklogItemRef(backlog_item_id="b_rej", item_state="acknowledged"),
            RemediationClosureBacklogItemRef(backlog_item_id="b_pend", item_state="acknowledged"),
            RemediationClosureBacklogItemRef(backlog_item_id="b_na", item_state="not_applicable"),
        ),
        evidence_summaries=(
            RemediationClosureEvidenceSummary(
                evidence_summary_id="es_ack",
                backlog_item_id="b_ack",
                coverage_state="covered",
            ),
            RemediationClosureEvidenceSummary(
                evidence_summary_id="es_rej",
                backlog_item_id="b_rej",
                coverage_state="covered",
            ),
            RemediationClosureEvidenceSummary(
                evidence_summary_id="es_pend",
                backlog_item_id="b_pend",
                coverage_state="covered",
            ),
        ),
        closure_declarations=(
            RemediationClosureDeclaration(
                closure_id="c_ack",
                backlog_item_id="b_ack",
                evidence_summary_id="es_ack",
            ),
            RemediationClosureDeclaration(
                closure_id="c_rej",
                backlog_item_id="b_rej",
                evidence_summary_id="es_rej",
            ),
            RemediationClosureDeclaration(
                closure_id="c_pend",
                backlog_item_id="b_pend",
                evidence_summary_id="es_pend",
            ),
        ),
        review_records=(
            RemediationClosureReviewRecord(review_id="r_ack", closure_id="c_ack", outcome="accepted"),
            RemediationClosureReviewRecord(review_id="r_rej", closure_id="c_rej", outcome="rejected"),
            RemediationClosureReviewRecord(review_id="r_pend", closure_id="c_pend", outcome="pending"),
        ),
        generated_at=NOW,
    )
    return build_remediation_closure_report(inp)


# ---------------------------------------------------------------------------
# Dict / JSON
# ---------------------------------------------------------------------------


def test_dict_includes_all_report_fields() -> None:
    report = _build_closed_recorded_report()
    data = remediation_closure_report_to_dict(report)
    assert "report_id" in data
    assert "generated_at" in data
    assert "state" in data
    assert "project_version" in data
    assert "backlog_item_refs" in data
    assert "evidence_summaries" in data
    assert "closure_declarations" in data
    assert "review_records" in data
    assert "links" in data
    assert "issues" in data
    assert "closure_results" in data
    assert "data_quality" in data
    assert "safety_flags" in data
    assert "metadata" in data


def test_dict_safety_flags_include_is_safe() -> None:
    report = _build_closed_recorded_report()
    data = remediation_closure_report_to_dict(report)
    assert data["safety_flags"]["is_safe"] is True


def test_dict_serializes_enums_as_values() -> None:
    report = _build_closed_recorded_report()
    data = remediation_closure_report_to_dict(report)
    assert data["state"] == "ok"
    assert data["closure_results"][0]["record_state"] == "closed_recorded"
    assert data["closure_results"][0]["review_outcome"] == "accepted"


def test_dict_metadata_sorted() -> None:
    report = _build_closed_recorded_report()
    data = remediation_closure_report_to_dict(report)
    assert isinstance(data["metadata"], dict)


def test_json_parseable_and_deterministic() -> None:
    report = _build_closed_recorded_report()
    text1 = remediation_closure_report_to_json_text(report)
    text2 = remediation_closure_report_to_json_text(report)
    assert text1 == text2
    data = json.loads(text1)
    assert data["state"] == "ok"
    assert data["project_version"] == "0.39.0-dev"


def test_json_datetime_serialized_iso() -> None:
    report = _build_closed_recorded_report()
    data = json.loads(remediation_closure_report_to_json_text(report))
    assert data["generated_at"] == "2026-01-01T12:00:00+00:00"


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------


def test_csv_header_matches_requirements() -> None:
    report = _build_closed_recorded_report()
    text = remediation_closure_report_to_csv_text(report)
    rows = list(csv.reader(text.splitlines()))
    assert rows[0] == [
        "report_id",
        "generated_at",
        "closure_result_id",
        "backlog_item_id",
        "closure_id",
        "record_state",
        "eligibility_state",
        "review_outcome",
        "severity",
        "reason_codes",
        "message",
    ]


def test_csv_row_for_closed_recorded() -> None:
    report = _build_closed_recorded_report()
    text = remediation_closure_report_to_csv_text(report)
    rows = list(csv.reader(text.splitlines()))
    assert len(rows) == 2
    row = rows[1]
    assert row[3] == "b1"
    assert row[4] == "c1"
    assert row[5] == "closed_recorded"
    assert row[6] == "eligible"
    assert row[7] == "accepted"
    assert row[8] == "info"


def test_csv_sorts_by_closure_result_id() -> None:
    report = _build_varied_report()
    text = remediation_closure_report_to_csv_text(report)
    rows = list(csv.reader(text.splitlines()))
    result_ids = [row[2] for row in rows[1:]]
    assert sorted(result_ids) == result_ids


def test_csv_blocked_report_has_no_result_rows() -> None:
    report = _build_blocked_report()
    text = remediation_closure_report_to_csv_text(report)
    rows = list(csv.reader(text.splitlines()))
    assert len(rows) == 1


def test_csv_empty_closure_results_has_header_only() -> None:
    report = _build_blocked_report()
    text = remediation_closure_report_to_csv_text(report)
    rows = list(csv.reader(text.splitlines()))
    assert rows[0][0] == "report_id"
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------


def test_markdown_starts_with_h1_and_safety_notice() -> None:
    report = _build_closed_recorded_report()
    text = remediation_closure_report_to_markdown_text(report)
    lines = text.splitlines()
    assert lines[0] == "# Remediation Closure Register"
    assert any("audit-only" in line.lower() for line in lines[:10])
    assert any("human-audit" in line.lower() or "research-only" in line.lower() for line in lines[:10])


def test_markdown_contains_explicit_not_approval_statement() -> None:
    report = _build_closed_recorded_report()
    text = remediation_closure_report_to_markdown_text(report)
    lower = text.lower()
    assert "approval" in lower
    assert "certification" in lower
    assert "production readiness" in lower
    assert "deployment readiness" in lower
    assert "trading readiness" in lower
    assert "recommendation" in lower
    assert "suitability" in lower
    assert "signal" in lower
    assert "executable remediation plan" in lower


def test_markdown_contains_all_required_sections() -> None:
    report = _build_closed_recorded_report()
    text = remediation_closure_report_to_markdown_text(report)
    assert "## Summary" in text
    assert "## Closure Results" in text
    assert "## Evidence Summaries" in text
    assert "## Closure Declarations" in text
    assert "## Review Records" in text
    assert "## Links" in text
    assert "## Issues" in text
    assert "## Data Quality" in text
    assert "## Safety Flags" in text
    assert "## Opaque Reference Notice" in text
    assert "## No Automated Remediation Execution" in text
    assert "## Manual Review Notes" in text


def test_markdown_empty_issues_valid() -> None:
    report = _build_closed_recorded_report()
    text = remediation_closure_report_to_markdown_text(report)
    assert "## Issues" in text
    assert "_none_" in text or "|" in text


def test_markdown_contains_no_executable_or_trading_instructions() -> None:
    report = _build_closed_recorded_report()
    text = remediation_closure_report_to_markdown_text(report)
    lower = text.lower()
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
    ]
    for term in forbidden:
        assert term not in lower, f"forbidden term in markdown: {term}"


# ---------------------------------------------------------------------------
# Atomic writes and path handling
# ---------------------------------------------------------------------------


def test_atomic_write_json_creates_file(tmp_path: Path) -> None:
    report = _build_closed_recorded_report()
    path = tmp_path / "closure.json"
    result = atomic_write_json_remediation_closure_report(report, path)
    assert result == path
    assert path.exists()
    data = json.loads(path.read_text())
    assert data["state"] == "ok"


def test_atomic_write_csv_creates_file(tmp_path: Path) -> None:
    report = _build_closed_recorded_report()
    path = tmp_path / "closure.csv"
    result = atomic_write_csv_remediation_closure_report(report, path)
    assert result == path
    assert path.exists()
    rows = list(csv.reader(path.read_text().splitlines()))
    assert rows[0][0] == "report_id"


def test_atomic_write_markdown_creates_file(tmp_path: Path) -> None:
    report = _build_closed_recorded_report()
    path = tmp_path / "closure.md"
    result = atomic_write_markdown_remediation_closure_report(report, path)
    assert result == path
    assert path.exists()
    assert path.read_text().startswith("# Remediation Closure Register")


def test_parent_directories_created(tmp_path: Path) -> None:
    report = _build_closed_recorded_report()
    path = tmp_path / "a" / "b" / "c" / "closure.json"
    atomic_write_json_remediation_closure_report(report, path)
    assert path.exists()


def test_write_with_none_skips_artifact(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    report = _build_closed_recorded_report()
    monkeypatch.chdir(tmp_path)
    json_path, csv_path, md_path = write_remediation_closure_report(
        report, json_path=None, csv_path=None, markdown_path=None
    )
    assert json_path is None
    assert csv_path is None
    assert md_path is None
    assert not (tmp_path / DEFAULT_JSON_PATH).exists()
    assert not (tmp_path / DEFAULT_CSV_PATH).exists()
    assert not (tmp_path / DEFAULT_MD_PATH).exists()


def test_write_omitted_uses_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    report = _build_closed_recorded_report()
    monkeypatch.chdir(tmp_path)
    json_path, csv_path, md_path = write_remediation_closure_report(report)
    assert json_path == DEFAULT_JSON_PATH
    assert csv_path == DEFAULT_CSV_PATH
    assert md_path == DEFAULT_MD_PATH
    assert (tmp_path / DEFAULT_JSON_PATH).exists()
    assert (tmp_path / DEFAULT_CSV_PATH).exists()
    assert (tmp_path / DEFAULT_MD_PATH).exists()


def test_write_explicit_path_only(tmp_path: Path) -> None:
    report = _build_closed_recorded_report()
    json_file = tmp_path / "custom.json"
    csv_file = tmp_path / "custom.csv"
    md_file = tmp_path / "custom.md"
    write_remediation_closure_report(
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
    data = remediation_closure_report_to_dict(report)
    assert data["state"] == "blocked"
    assert data["safety_flags"]["has_unsafe_content"] is True


def test_degraded_report_serialization() -> None:
    inp = RemediationClosureInput(
        backlog_item_refs=(
            RemediationClosureBacklogItemRef(backlog_item_id="b1", item_state="acknowledged"),
        ),
        evidence_summaries=(
            RemediationClosureEvidenceSummary(
                evidence_summary_id="es1",
                backlog_item_id="b2",  # orphan: references unknown backlog item
                coverage_state="covered",
            ),
        ),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    data = remediation_closure_report_to_dict(report)
    assert data["state"] == "degraded"


def test_not_applicable_report_serialization() -> None:
    report = _build_blocked_report()
    data = remediation_closure_report_to_dict(report)
    assert data["state"] == "blocked"


# ---------------------------------------------------------------------------
# Safety / no mutation
# ---------------------------------------------------------------------------


def test_no_report_mutation_after_serialization() -> None:
    report = _build_closed_recorded_report()
    before = report
    remediation_closure_report_to_dict(report)
    remediation_closure_report_to_json_text(report)
    remediation_closure_report_to_csv_text(report)
    remediation_closure_report_to_markdown_text(report)
    assert report is before
    assert report.state is RemediationClosureState.OK


def test_no_path_traversal_or_opening() -> None:
    """Opaque references are serialized as strings without filesystem access."""
    ref = RemediationClosureBacklogItemRef(
        backlog_item_id="b1",
        source_id="s3://bucket/report.md",
        finding_id="finding-1",
        item_state="acknowledged",
    )
    closure = RemediationClosureDeclaration(
        closure_id="c1",
        backlog_item_id="b1",
        evidence_link="/etc/passwd",
    )
    inp = RemediationClosureInput(
        backlog_item_refs=(ref,),
        closure_declarations=(closure,),
        generated_at=NOW,
    )
    report = build_remediation_closure_report(inp)
    data = remediation_closure_report_to_dict(report)
    assert data["backlog_item_refs"][0]["source_id"] == "s3://bucket/report.md"
    assert data["closure_declarations"][0]["evidence_link"] == "/etc/passwd"


def test_nested_mapping_serialization() -> None:
    report = _build_closed_recorded_report()
    data = remediation_closure_report_to_dict(report)
    assert isinstance(data["closure_declarations"][0]["metadata"], dict)


def test_deterministic_outputs_from_same_report() -> None:
    report = _build_closed_recorded_report()
    assert remediation_closure_report_to_json_text(report) == remediation_closure_report_to_json_text(report)
    assert remediation_closure_report_to_csv_text(report) == remediation_closure_report_to_csv_text(report)
    assert remediation_closure_report_to_markdown_text(report) == remediation_closure_report_to_markdown_text(report)


def test_public_exports() -> None:
    from hunter import remediation_closure
    assert hasattr(remediation_closure, "remediation_closure_report_to_dict")
    assert hasattr(remediation_closure, "remediation_closure_report_to_json_text")
    assert hasattr(remediation_closure, "remediation_closure_report_to_csv_text")
    assert hasattr(remediation_closure, "remediation_closure_report_to_markdown_text")
    assert hasattr(remediation_closure, "write_remediation_closure_report")
    assert hasattr(remediation_closure, "atomic_write_json_remediation_closure_report")
    assert hasattr(remediation_closure, "atomic_write_csv_remediation_closure_report")
    assert hasattr(remediation_closure, "atomic_write_markdown_remediation_closure_report")
    assert hasattr(remediation_closure, "DEFAULT_JSON_PATH")
    assert hasattr(remediation_closure, "DEFAULT_CSV_PATH")
    assert hasattr(remediation_closure, "DEFAULT_MD_PATH")
