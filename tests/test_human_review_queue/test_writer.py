"""Tests for hunter.human_review_queue.writer."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from hunter.human_review_queue import (
    DEFAULT_CSV_PATH,
    DEFAULT_JSON_PATH,
    DEFAULT_MD_PATH,
    HumanReviewQueueConfig,
    HumanReviewQueueEntry,
    HumanReviewQueueInput,
    HumanReviewQueueIssue,
    HumanReviewQueueReasonCode,
    HumanReviewQueueReport,
    HumanReviewQueueSafetyFlags,
    HumanReviewQueueSeverity,
    HumanReviewQueueState,
    HumanReviewSourceRecord,
    _DEFAULT_PATH,
    build_human_review_queue_report,
    human_review_queue_report_to_csv_text,
    human_review_queue_report_to_dict,
    human_review_queue_report_to_json_text,
    human_review_queue_report_to_markdown_text,
    write_human_review_queue_report,
)

NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _record(
    *,
    source_id: str = "src-1",
    source_kind: str = "backlog_item",
    record_id: str = "rec-1",
    title: str = "Title",
    description: str = "Description",
    state: str = "open",
    severity: str = "advisory",
    reason_codes: tuple[str, ...] = (),
    generated_at: datetime | None = None,
    metadata: dict[str, str] | None = None,
    artifact_ref: str = "",
    report_ref: str = "",
) -> HumanReviewSourceRecord:
    return HumanReviewSourceRecord(
        source_id=source_id,
        source_kind=source_kind,
        record_id=record_id,
        title=title,
        description=description,
        state=state,
        severity=severity,
        reason_codes=reason_codes,
        generated_at=generated_at or NOW,
        metadata=metadata or {},
        artifact_ref=artifact_ref,
        report_ref=report_ref,
    )


def _sample_report() -> HumanReviewQueueReport:
    record = _record(
        source_id="src-1",
        source_kind="backlog_item",
        record_id="rec-1",
        title="Sample item",
        description="A sample description",
        state="open",
        severity="advisory",
        reason_codes=("advisory_severity",),
        metadata={"path": "/opaque/path"},
        artifact_ref="artifact.json",
        report_ref="report.md",
    )
    entry = HumanReviewQueueEntry(
        queue_entry_id="qe-1",
        source_id="src-1",
        source_kind="backlog_item",
        record_id="rec-1",
        entry_state="queued",
        priority="medium",
        decision_hint="review_required",
        severity="advisory",
        reason_codes=("advisory_severity",),
        title="Sample item",
        description="A sample description",
        generated_at=NOW,
        metadata={"path": "/opaque/path"},
    )
    issue = HumanReviewQueueIssue(
        issue_id="i-1",
        issue_type="advisory_severity",
        severity="advisory",
        reason_codes=("advisory_severity",),
        title="Sample issue",
        description="Issue description",
        source_id="src-1",
        record_id="rec-1",
        generated_at=NOW,
    )
    return HumanReviewQueueReport(
        report_id="report-1",
        generated_at=NOW,
        state=HumanReviewQueueState.OK,
        project_version="0.40.0-dev",
        source_records=(record,),
        queue_entries=(entry,),
        issues=(issue,),
        safety_flags=HumanReviewQueueSafetyFlags(),
        reason_codes=(HumanReviewQueueReasonCode.OK,),
        metadata={"audit": "true"},
        safety_notice="Custom safety notice",
        notes="Notes",
    )


# ---------------------------------------------------------------------------
# Dict shape
# ---------------------------------------------------------------------------


def test_report_to_dict_shape() -> None:
    report = _sample_report()
    data = human_review_queue_report_to_dict(report)
    assert "safety_notice" in data
    assert data["safety_notice"] == report.safety_notice
    assert "generated_at" in data
    assert data["report_id"] == report.report_id
    assert data["state"] == report.state.value
    assert "queue_entries" in data
    assert "issues" in data
    assert "data_quality" in data
    assert "safety_flags" in data
    assert "metadata" in data


def test_report_to_dict_deterministic_keys() -> None:
    report = _sample_report()
    data = human_review_queue_report_to_dict(report)
    # safety_notice and generated_at first, then sorted keys.
    keys = list(data.keys())
    assert keys[0] == "safety_notice"
    assert keys[1] == "generated_at"
    assert keys[2:] == sorted(keys[2:])


def test_report_to_dict_no_mutation() -> None:
    report = _sample_report()
    original = report
    _ = human_review_queue_report_to_dict(report)
    assert report == original


# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------


def test_report_to_json_text_is_parseable() -> None:
    report = _sample_report()
    text = human_review_queue_report_to_json_text(report)
    import json

    parsed = json.loads(text)
    assert parsed["report_id"] == report.report_id


def test_report_to_json_text_deterministic() -> None:
    report = _sample_report()
    text1 = human_review_queue_report_to_json_text(report)
    text2 = human_review_queue_report_to_json_text(report)
    assert text1 == text2


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------


def test_csv_exact_columns() -> None:
    report = _sample_report()
    csv_text = human_review_queue_report_to_csv_text(report)
    rows = csv_text.strip().split("\n")
    expected_columns = [
        "report_id",
        "generated_at",
        "queue_entry_id",
        "source_id",
        "source_kind",
        "record_id",
        "entry_state",
        "priority",
        "decision_hint",
        "severity",
        "reason_codes",
        "message",
    ]
    assert rows[0].split(",") == expected_columns


def test_csv_message_from_description() -> None:
    entry = HumanReviewQueueEntry(
        queue_entry_id="qe-1",
        source_id="src-1",
        source_kind="backlog_item",
        record_id="rec-1",
        title="Title",
        description="Description text",
        generated_at=NOW,
    )
    report = HumanReviewQueueReport(
        report_id="r",
        generated_at=NOW,
        queue_entries=(entry,),
    )
    csv_text = human_review_queue_report_to_csv_text(report)
    rows = csv_text.strip().split("\n")
    data_row = rows[1].split(",")
    assert data_row[-1] == "Description text"


def test_csv_message_from_title_when_description_empty() -> None:
    entry = HumanReviewQueueEntry(
        queue_entry_id="qe-1",
        source_id="src-1",
        source_kind="backlog_item",
        record_id="rec-1",
        title="Title text",
        description="",
        generated_at=NOW,
    )
    report = HumanReviewQueueReport(
        report_id="r",
        generated_at=NOW,
        queue_entries=(entry,),
    )
    csv_text = human_review_queue_report_to_csv_text(report)
    rows = csv_text.strip().split("\n")
    data_row = rows[1].split(",")
    assert data_row[-1] == "Title text"


def test_csv_message_empty_when_both_empty() -> None:
    entry = HumanReviewQueueEntry(
        queue_entry_id="qe-1",
        source_id="src-1",
        source_kind="backlog_item",
        record_id="rec-1",
        title="",
        description="",
        generated_at=NOW,
    )
    report = HumanReviewQueueReport(
        report_id="r",
        generated_at=NOW,
        queue_entries=(entry,),
    )
    csv_text = human_review_queue_report_to_csv_text(report)
    rows = csv_text.strip().split("\n")
    data_row = rows[1].split(",")
    assert data_row[-1] == ""


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------


def test_markdown_starts_with_safety_notice() -> None:
    report = _sample_report()
    text = human_review_queue_report_to_markdown_text(report)
    first_lines = text.split("\n")[:10]
    combined = " ".join(first_lines).lower()
    assert "audit-only" in combined or "research-only" in combined or "human-audit" in combined


def test_markdown_contains_required_disclaimers() -> None:
    report = _sample_report()
    text = human_review_queue_report_to_markdown_text(report).lower()
    assert "approval" in text
    assert "certification" in text
    assert "production readiness" in text
    assert "trading readiness" in text
    assert "recommendation" in text
    assert "suitability" in text
    assert "signal" in text
    assert "task assignment" in text
    assert "executable remediation" in text


def test_markdown_no_executable_remediation_language() -> None:
    report = _sample_report()
    text = human_review_queue_report_to_markdown_text(report).lower()
    assert "deploy immediately" not in text
    assert "execute now" not in text
    assert "run this command" not in text
    assert "apply patch" not in text
    assert "go live" not in text


def test_markdown_no_assignment_instructions() -> None:
    report = _sample_report()
    text = human_review_queue_report_to_markdown_text(report).lower()
    assert "assign to @" not in text
    assert "create ticket" not in text
    assert "open jira" not in text


# ---------------------------------------------------------------------------
# Write with sentinel behavior
# ---------------------------------------------------------------------------


def test_write_default_paths_use_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    report = _sample_report()
    json_path = tmp_path / "data" / "human_review_queue" / "human_review_queue.json"
    csv_path = tmp_path / "data" / "human_review_queue" / "human_review_queue.csv"
    md_path = tmp_path / "reports" / "human_review_queue" / "human_review_queue.md"
    monkeypatch.setattr("hunter.human_review_queue.writer.DEFAULT_JSON_PATH", json_path)
    monkeypatch.setattr("hunter.human_review_queue.writer.DEFAULT_CSV_PATH", csv_path)
    monkeypatch.setattr("hunter.human_review_queue.writer.DEFAULT_MD_PATH", md_path)

    write_human_review_queue_report(report)
    assert json_path.exists()
    assert csv_path.exists()
    assert md_path.exists()


def test_write_none_skips_artifact(tmp_path: Path) -> None:
    report = _sample_report()
    json_path = tmp_path / "out.json"
    csv_path = tmp_path / "out.csv"
    md_path = tmp_path / "out.md"
    write_human_review_queue_report(
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
    write_human_review_queue_report(
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
    write_human_review_queue_report(
        report,
        json_path=deep,
        csv_path=None,
        markdown_path=None,
    )
    assert deep.exists()


def test_write_json_content_matches_conversion(tmp_path: Path) -> None:
    report = _sample_report()
    json_path = tmp_path / "out.json"
    write_human_review_queue_report(
        report,
        json_path=json_path,
        csv_path=None,
        markdown_path=None,
    )
    expected = human_review_queue_report_to_json_text(report)
    assert json_path.read_text(encoding="utf-8") == expected


def test_write_csv_content_matches_conversion(tmp_path: Path) -> None:
    report = _sample_report()
    csv_path = tmp_path / "out.csv"
    write_human_review_queue_report(
        report,
        json_path=None,
        csv_path=csv_path,
        markdown_path=None,
    )
    expected = human_review_queue_report_to_csv_text(report)
    assert csv_path.read_text(encoding="utf-8") == expected


def test_write_markdown_content_matches_conversion(tmp_path: Path) -> None:
    report = _sample_report()
    md_path = tmp_path / "out.md"
    write_human_review_queue_report(
        report,
        json_path=None,
        csv_path=None,
        markdown_path=md_path,
    )
    expected = human_review_queue_report_to_markdown_text(report) + "\n"
    assert md_path.read_text(encoding="utf-8") == expected


# ---------------------------------------------------------------------------
# Opaque references
# ---------------------------------------------------------------------------


def test_opaque_refs_serialized_not_opened() -> None:
    report = _sample_report()
    text = human_review_queue_report_to_markdown_text(report)
    assert "artifact.json" in text
    assert "report.md" in text


def test_opaque_refs_in_json_serialization() -> None:
    report = _sample_report()
    data = human_review_queue_report_to_dict(report)
    source = data["source_records"][0]
    assert source["artifact_ref"] == "artifact.json"
    assert source["report_ref"] == "report.md"
    assert source["metadata"]["path"] == "/opaque/path"


# ---------------------------------------------------------------------------
# No mutation
# ---------------------------------------------------------------------------


def test_write_does_not_mutate_report(tmp_path: Path) -> None:
    report = _sample_report()
    original = report
    write_human_review_queue_report(
        report,
        json_path=tmp_path / "out.json",
        csv_path=None,
        markdown_path=None,
    )
    assert report == original


# ---------------------------------------------------------------------------
# Package exports
# ---------------------------------------------------------------------------


def test_writer_functions_exported() -> None:
    assert human_review_queue_report_to_dict is not None
    assert human_review_queue_report_to_json_text is not None
    assert human_review_queue_report_to_csv_text is not None
    assert human_review_queue_report_to_markdown_text is not None
    assert write_human_review_queue_report is not None
    assert _DEFAULT_PATH is not None


def test_default_path_constants_exported() -> None:
    assert "human_review_queue.json" in str(DEFAULT_JSON_PATH)
    assert "human_review_queue.csv" in str(DEFAULT_CSV_PATH)
    assert "human_review_queue.md" in str(DEFAULT_MD_PATH)


# ---------------------------------------------------------------------------
# Full engine + writer integration (no artifacts left in data/reports)
# ---------------------------------------------------------------------------


def test_end_to_end_writes_to_tmp_path(tmp_path: Path) -> None:
    record = _record(
        source_id="src-1",
        record_id="rec-1",
        title="End-to-end",
        description="E2E description",
        severity="advisory",
    )
    inp = HumanReviewQueueInput(source_records=(record,), generated_at=NOW)
    report = build_human_review_queue_report(inp)
    json_path = tmp_path / "e2e.json"
    csv_path = tmp_path / "e2e.csv"
    md_path = tmp_path / "e2e.md"
    write_human_review_queue_report(
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
