"""Tests for hunter.human_review_decision_log.writer."""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hunter.human_review_decision_log import (
    DEFAULT_CSV_PATH,
    DEFAULT_JSON_PATH,
    DEFAULT_MD_PATH,
    HumanReviewDecisionLink,
    HumanReviewDecisionLogConfig,
    HumanReviewDecisionLogInput,
    HumanReviewDecisionLogReport,
    HumanReviewDecisionLogState,
    HumanReviewDecisionRecord,
    HumanReviewDecisionResult,
    HumanReviewQueueEntryRef,
    _DEFAULT_PATH,
    build_human_review_decision_log_report,
    human_review_decision_log_report_to_csv_text,
    human_review_decision_log_report_to_dict,
    human_review_decision_log_report_to_json_text,
    human_review_decision_log_report_to_markdown_text,
    write_human_review_decision_log_report,
)

NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sample_report() -> HumanReviewDecisionLogReport:
    ref = HumanReviewQueueEntryRef(
        queue_entry_id="qe-1",
        source_id="src-1",
        source_kind="backlog_item",
        record_id="rec-1",
        entry_state="open",
        priority="medium",
        severity="advisory",
        reason_codes=("advisory_severity",),
        generated_at=NOW,
        artifact_ref="artifact.json",
        report_ref="report.md",
    )
    decision = HumanReviewDecisionRecord(
        decision_id="dec-1",
        queue_entry_id="qe-1",
        reviewer="reviewer-a",
        decided_at=NOW,
        outcome="accepted_for_audit_log",
        rationale="Accepted for audit log",
        reason_codes=("decision_logged",),
        generated_at=NOW,
        artifact_ref="decision.json",
        report_ref="decision_report.md",
    )
    link = HumanReviewDecisionLink(
        link_id="link-1",
        source_id="dec-1",
        target_id="qe-1",
        link_type="references",
        generated_at=NOW,
    )
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(ref,),
        decision_records=(decision,),
        links=(link,),
        generated_at=NOW,
    )
    return build_human_review_decision_log_report(inp)


# ---------------------------------------------------------------------------
# Public exports
# ---------------------------------------------------------------------------


def test_writer_functions_exported() -> None:
    assert human_review_decision_log_report_to_dict is not None
    assert human_review_decision_log_report_to_json_text is not None
    assert human_review_decision_log_report_to_csv_text is not None
    assert human_review_decision_log_report_to_markdown_text is not None
    assert write_human_review_decision_log_report is not None
    assert _DEFAULT_PATH is not None


def test_default_path_constants_exported() -> None:
    assert "human_review_decision_log.json" in str(DEFAULT_JSON_PATH)
    assert "human_review_decisions.csv" in str(DEFAULT_CSV_PATH)
    assert "human_review_decision_log.md" in str(DEFAULT_MD_PATH)


# ---------------------------------------------------------------------------
# Dict shape
# ---------------------------------------------------------------------------


def test_dict_includes_all_required_top_level_keys() -> None:
    report = _sample_report()
    data = human_review_decision_log_report_to_dict(report)
    required = {
        "report_id",
        "generated_at",
        "project_version",
        "state",
        "safety_notice",
        "notes",
        "queue_entry_refs",
        "decision_records",
        "links",
        "issues",
        "decision_results",
        "data_quality",
        "safety_flags",
        "metadata",
        "reason_codes",
    }
    assert required <= data.keys()


def test_dict_serializes_enums_as_values() -> None:
    report = _sample_report()
    data = human_review_decision_log_report_to_dict(report)
    assert data["state"] == report.state.value
    assert isinstance(data["state"], str)
    assert data["reason_codes"] == [rc.value for rc in report.reason_codes]


def test_dict_metadata_sorted_and_stable() -> None:
    report = _sample_report()
    data = human_review_decision_log_report_to_dict(report)
    assert isinstance(data["metadata"], dict)
    assert list(data["metadata"].keys()) == sorted(data["metadata"].keys())


def test_dict_no_mutation() -> None:
    report = _sample_report()
    original = report
    _ = human_review_decision_log_report_to_dict(report)
    assert report == original


# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------


def test_json_text_deterministic_and_parseable() -> None:
    report = _sample_report()
    text1 = human_review_decision_log_report_to_json_text(report)
    text2 = human_review_decision_log_report_to_json_text(report)
    assert text1 == text2
    parsed = json.loads(text1)
    assert parsed["report_id"] == report.report_id


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------


def test_csv_header_exact_columns() -> None:
    report = _sample_report()
    csv_text = human_review_decision_log_report_to_csv_text(report)
    rows = list(csv.reader(csv_text.splitlines()))
    assert rows[0] == [
        "report_id",
        "generated_at",
        "decision_result_id",
        "queue_entry_id",
        "decision_id",
        "decision_state",
        "decision_outcome",
        "decision_validity",
        "severity",
        "reason_codes",
        "message",
    ]


def test_csv_decision_id_semicolon_joins_sorted_decision_ids() -> None:
    ref = HumanReviewQueueEntryRef(queue_entry_id="qe-1", generated_at=NOW)
    d1 = HumanReviewDecisionRecord(
        decision_id="dec-b",
        queue_entry_id="qe-1",
        reviewer="reviewer-a",
        decided_at=NOW,
        outcome="accepted_for_audit_log",
        rationale="Rationale",
        generated_at=NOW,
    )
    d2 = HumanReviewDecisionRecord(
        decision_id="dec-a",
        queue_entry_id="qe-1",
        reviewer="reviewer-b",
        decided_at=NOW,
        outcome="rejected_for_audit_log",
        rationale="Rationale",
        generated_at=NOW,
    )
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(ref,),
        decision_records=(d1, d2),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    csv_text = human_review_decision_log_report_to_csv_text(report)
    rows = list(csv.reader(csv_text.splitlines()))
    assert rows[1][4] == "dec-a;dec-b"


def test_csv_empty_decision_ids_serializes_empty_string() -> None:
    result = HumanReviewDecisionResult(
        decision_result_id="dr-1",
        queue_entry_id="qe-1",
        decision_ids=(),
        decision_state="missing",
        decision_outcome="unknown",
        decision_validity="invalid_for_audit_log",
        severity="info",
        reason_codes=(),
    )
    report = HumanReviewDecisionLogReport(
        report_id="r-1",
        generated_at=NOW,
        state=HumanReviewDecisionLogState.NOT_APPLICABLE,
        decision_results=(result,),
    )
    csv_text = human_review_decision_log_report_to_csv_text(report)
    rows = list(csv.reader(csv_text.splitlines()))
    assert rows[1][4] == ""


def test_csv_rows_preserve_required_fields() -> None:
    report = _sample_report()
    csv_text = human_review_decision_log_report_to_csv_text(report)
    rows = list(csv.reader(csv_text.splitlines()))
    result = report.decision_results[0]
    row = rows[1]
    assert row[0] == report.report_id
    assert row[1] == "2026-01-01T12:00:00+00:00"
    assert row[2] == result.decision_result_id
    assert row[3] == result.queue_entry_id
    assert row[5] == result.decision_state
    assert row[6] == result.decision_outcome
    assert row[7] == result.decision_validity
    assert row[8] == result.severity
    assert row[9] == "|".join(sorted(result.reason_codes))
    assert row[10] == (result.rationale or "")


def test_csv_deterministic() -> None:
    report = _sample_report()
    csv1 = human_review_decision_log_report_to_csv_text(report)
    csv2 = human_review_decision_log_report_to_csv_text(report)
    assert csv1 == csv2


def test_csv_empty_decision_results_has_header_only() -> None:
    report = HumanReviewDecisionLogReport(
        report_id="r-1",
        generated_at=NOW,
        state=HumanReviewDecisionLogState.NOT_APPLICABLE,
        decision_results=(),
    )
    csv_text = human_review_decision_log_report_to_csv_text(report)
    rows = csv_text.strip().split("\n")
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------


def test_markdown_starts_with_h1() -> None:
    report = _sample_report()
    text = human_review_decision_log_report_to_markdown_text(report)
    assert text.startswith("# Human Review Decision Log")


def test_markdown_has_immediate_safety_notice() -> None:
    report = _sample_report()
    text = human_review_decision_log_report_to_markdown_text(report)
    first_lines = "\n".join(text.split("\n")[:10]).lower()
    assert "audit-only" in first_lines or "research-only" in first_lines or "human-audit" in first_lines


def test_markdown_contains_required_disclaimers() -> None:
    report = _sample_report()
    text = human_review_decision_log_report_to_markdown_text(report).lower()
    assert "approval" in text
    assert "certification" in text
    assert "production readiness" in text
    assert "deployment readiness" in text
    assert "trading readiness" in text
    assert "recommendation" in text
    assert "suitability assessment" in text
    assert "signal" in text
    assert "task assignment" in text
    assert "task completion" in text
    assert "executable remediation plan" in text


def test_markdown_includes_required_sections() -> None:
    report = _sample_report()
    text = human_review_decision_log_report_to_markdown_text(report)
    assert "## Summary" in text
    assert "## Data Quality" in text
    assert "## Safety Flags" in text
    assert "## Decision Results" in text
    assert "## Issues" in text
    assert "## Opaque Reference Notice" in text
    assert "## No Automated Remediation Execution" in text
    assert "## Reviewer Attribution" in text


def test_markdown_no_executable_or_assignment_language() -> None:
    report = _sample_report()
    text = human_review_decision_log_report_to_markdown_text(report).lower()
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
        "assign to @",
        "create ticket",
        "open jira",
    ]
    for term in forbidden:
        assert term not in text, f"forbidden term in markdown: {term}"


def test_markdown_empty_issues_remains_valid() -> None:
    report = HumanReviewDecisionLogReport(
        report_id="r-1",
        generated_at=NOW,
        state=HumanReviewDecisionLogState.NOT_APPLICABLE,
        issues=(),
        decision_results=(),
    )
    text = human_review_decision_log_report_to_markdown_text(report)
    assert text.startswith("# Human Review Decision Log")
    assert "## Issues" in text


# ---------------------------------------------------------------------------
# File writes
# ---------------------------------------------------------------------------


def test_write_default_paths_use_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = _sample_report()
    json_path = tmp_path / "data" / "human_review_decision_log" / "human_review_decision_log.json"
    csv_path = tmp_path / "data" / "human_review_decision_log" / "human_review_decisions.csv"
    md_path = tmp_path / "reports" / "human_review_decision_log" / "human_review_decision_log.md"
    monkeypatch.setattr(
        "hunter.human_review_decision_log.writer.DEFAULT_JSON_PATH", json_path
    )
    monkeypatch.setattr(
        "hunter.human_review_decision_log.writer.DEFAULT_CSV_PATH", csv_path
    )
    monkeypatch.setattr(
        "hunter.human_review_decision_log.writer.DEFAULT_MD_PATH", md_path
    )

    write_human_review_decision_log_report(report)
    assert json_path.exists()
    assert csv_path.exists()
    assert md_path.exists()


def test_write_none_skips_artifact(tmp_path: Path) -> None:
    report = _sample_report()
    json_path = tmp_path / "out.json"
    csv_path = tmp_path / "out.csv"
    md_path = tmp_path / "out.md"
    write_human_review_decision_log_report(
        report,
        json_path=json_path,
        csv_path=None,
        markdown_path=md_path,
    )
    assert json_path.exists()
    assert not csv_path.exists()
    assert md_path.exists()


def test_write_explicit_path_only(tmp_path: Path) -> None:
    report = _sample_report()
    json_path = tmp_path / "only.json"
    csv_path = tmp_path / "only.csv"
    md_path = tmp_path / "only.md"
    write_human_review_decision_log_report(
        report,
        json_path=json_path,
        csv_path=None,
        markdown_path=None,
    )
    assert json_path.exists()
    assert not csv_path.exists()
    assert not md_path.exists()


def test_write_creates_parent_directories(tmp_path: Path) -> None:
    report = _sample_report()
    deep = tmp_path / "deep" / "nested" / "out.json"
    write_human_review_decision_log_report(
        report,
        json_path=deep,
        csv_path=None,
        markdown_path=None,
    )
    assert deep.exists()


def test_write_json_content_matches_conversion(tmp_path: Path) -> None:
    report = _sample_report()
    json_path = tmp_path / "out.json"
    write_human_review_decision_log_report(
        report,
        json_path=json_path,
        csv_path=None,
        markdown_path=None,
    )
    expected = human_review_decision_log_report_to_json_text(report)
    assert json_path.read_text(encoding="utf-8") == expected


def test_write_csv_content_matches_conversion(tmp_path: Path) -> None:
    report = _sample_report()
    csv_path = tmp_path / "out.csv"
    write_human_review_decision_log_report(
        report,
        json_path=None,
        csv_path=csv_path,
        markdown_path=None,
    )
    expected = human_review_decision_log_report_to_csv_text(report)
    assert csv_path.read_text(encoding="utf-8") == expected


def test_write_markdown_content_matches_conversion(tmp_path: Path) -> None:
    report = _sample_report()
    md_path = tmp_path / "out.md"
    write_human_review_decision_log_report(
        report,
        json_path=None,
        csv_path=None,
        markdown_path=md_path,
    )
    expected = human_review_decision_log_report_to_markdown_text(report) + "\n"
    assert md_path.read_text(encoding="utf-8") == expected


# ---------------------------------------------------------------------------
# Opaque refs and no mutation
# ---------------------------------------------------------------------------


def test_opaque_refs_serialized_not_opened() -> None:
    report = _sample_report()
    text = human_review_decision_log_report_to_markdown_text(report)
    assert "artifact.json" in text
    assert "report.md" in text


def test_write_does_not_mutate_report(tmp_path: Path) -> None:
    report = _sample_report()
    original = report
    write_human_review_decision_log_report(
        report,
        json_path=tmp_path / "out.json",
        csv_path=None,
        markdown_path=None,
    )
    assert report == original


def test_deterministic_outputs_from_same_report() -> None:
    report = _sample_report()
    assert human_review_decision_log_report_to_json_text(report) == human_review_decision_log_report_to_json_text(report)
    assert human_review_decision_log_report_to_csv_text(report) == human_review_decision_log_report_to_csv_text(report)
    assert human_review_decision_log_report_to_markdown_text(report) == human_review_decision_log_report_to_markdown_text(report)


# ---------------------------------------------------------------------------
# Blocked / minimal report
# ---------------------------------------------------------------------------


def test_blocked_minimal_report_serializes_safely() -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(
            HumanReviewQueueEntryRef(queue_entry_id="qe-1", generated_at=NOW),
        ),
        decision_records=(
            HumanReviewDecisionRecord(
                decision_id="dec-1",
                queue_entry_id="qe-1",
                reviewer="reviewer-a",
                decided_at=NOW,
                outcome="accepted_for_audit_log",
                rationale="Deploy immediately",
                generated_at=NOW,
            ),
        ),
        generated_at=NOW,
    )
    report = HumanReviewDecisionLogReport.blocked(input=inp)
    data = human_review_decision_log_report_to_dict(report)
    assert data["state"] == "blocked"
    text = human_review_decision_log_report_to_markdown_text(report)
    assert text.startswith("# Human Review Decision Log")
    assert "audit-only" in text.lower()


# ---------------------------------------------------------------------------
# End-to-end engine + writer
# ---------------------------------------------------------------------------


def test_end_to_end_writes_to_tmp_path(tmp_path: Path) -> None:
    report = _sample_report()
    json_path = tmp_path / "e2e.json"
    csv_path = tmp_path / "e2e.csv"
    md_path = tmp_path / "e2e.md"
    write_human_review_decision_log_report(
        report,
        json_path=json_path,
        csv_path=csv_path,
        markdown_path=md_path,
    )
    assert json_path.exists()
    assert csv_path.exists()
    assert md_path.exists()
    md_text = md_path.read_text(encoding="utf-8")
    assert "audit-only" in md_text.lower()
