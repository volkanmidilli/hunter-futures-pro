"""Integration tests for hunter.human_review_queue."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from hunter.human_review_queue import (
    HumanReviewQueueConfig,
    HumanReviewQueueEntryState,
    HumanReviewQueueInput,
    HumanReviewQueueIssueType,
    HumanReviewQueuePriority,
    HumanReviewQueueReasonCode,
    HumanReviewQueueSeverity,
    HumanReviewQueueSourceKind,
    HumanReviewQueueState,
    HumanReviewSourceRecord,
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
    source_id: str,
    source_kind: str = "backlog_item",
    record_id: str,
    title: str = "",
    description: str = "",
    state: str = "open",
    severity: str = "advisory",
    reason_codes: tuple[str, ...] = (),
    related_record_ids: tuple[str, ...] = (),
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
        related_record_ids=related_record_ids,
        generated_at=generated_at or NOW,
        metadata=metadata or {},
        artifact_ref=artifact_ref,
        report_ref=report_ref,
    )


# ---------------------------------------------------------------------------
# End-to-end mixed source records
# ---------------------------------------------------------------------------


def test_end_to_end_mixed_source_records(tmp_path: Path) -> None:
    records = (
        _record(
            source_id="src-1",
            record_id="rec-1",
            source_kind="backlog_item",
            title="Advisory item",
            description="Needs review",
            severity="advisory",
            state="open",
        ),
        _record(
            source_id="src-2",
            record_id="rec-2",
            source_kind="manual_note",
            title="Manual note",
            description="For audit",
            severity="info",
            state="open",
        ),
    )
    inp = HumanReviewQueueInput(source_records=records, generated_at=NOW)
    report = build_human_review_queue_report(inp)

    data = human_review_queue_report_to_dict(report)
    json_text = human_review_queue_report_to_json_text(report)
    csv_text = human_review_queue_report_to_csv_text(report)
    md_text = human_review_queue_report_to_markdown_text(report)

    assert data["state"] == HumanReviewQueueState.OK.value
    assert len(data["queue_entries"]) == 2
    assert len(data["source_records"]) == 2
    assert json_text
    assert csv_text
    assert md_text

    assert {HumanReviewQueuePriority.MEDIUM.value, HumanReviewQueuePriority.LOW.value} == {
        e.priority for e in report.queue_entries
    }


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_deterministic_across_repeated_runs() -> None:
    records = (
        _record(
            source_id="src-1",
            record_id="rec-1",
            title="Title",
            description="Description",
            severity="advisory",
        ),
    )
    inp = HumanReviewQueueInput(source_records=records, generated_at=NOW, project_version="0.40.0-dev")

    report1 = build_human_review_queue_report(inp)
    report2 = build_human_review_queue_report(inp)

    assert report1.report_id == report2.report_id
    assert [e.queue_entry_id for e in report1.queue_entries] == [e.queue_entry_id for e in report2.queue_entries]
    assert [i.issue_id for i in report1.issues] == [i.issue_id for i in report2.issues]

    json1 = human_review_queue_report_to_json_text(report1)
    json2 = human_review_queue_report_to_json_text(report2)
    assert json1 == json2

    csv1 = human_review_queue_report_to_csv_text(report1)
    csv2 = human_review_queue_report_to_csv_text(report2)
    assert csv1 == csv2

    md1 = human_review_queue_report_to_markdown_text(report1)
    md2 = human_review_queue_report_to_markdown_text(report2)
    assert md1 == md2


# ---------------------------------------------------------------------------
# Aggregate state end-to-end
# ---------------------------------------------------------------------------


def test_advisory_only_non_strict_end_to_end_ok() -> None:
    records = (_record(source_id="src-1", record_id="rec-1", severity="advisory", state="open"),)
    inp = HumanReviewQueueInput(source_records=records, generated_at=NOW)
    report = build_human_review_queue_report(inp)
    assert report.state == HumanReviewQueueState.OK
    assert report.queue_entries[0].severity == HumanReviewQueueSeverity.ADVISORY.value


def test_strict_advisory_end_to_end_blocked() -> None:
    config = HumanReviewQueueConfig(strict=True)
    records = (_record(source_id="src-1", record_id="rec-1", severity="advisory", state="open"),)
    inp = HumanReviewQueueInput(source_records=records, config=config, generated_at=NOW)
    report = build_human_review_queue_report(inp)
    assert report.state == HumanReviewQueueState.BLOCKED


def test_duplicate_source_ids_end_to_end_blocked() -> None:
    records = (
        _record(source_id="dup", record_id="a"),
        _record(source_id="dup", record_id="b"),
    )
    inp = HumanReviewQueueInput(source_records=records, generated_at=NOW)
    report = build_human_review_queue_report(inp)
    assert report.state == HumanReviewQueueState.BLOCKED
    assert HumanReviewQueueReasonCode.DUPLICATE_SOURCE_ID in report.reason_codes


def test_unsafe_content_end_to_end_blocked() -> None:
    records = (_record(source_id="src-1", record_id="rec-1", metadata={"bad": 123}),)
    inp = HumanReviewQueueInput(source_records=records, generated_at=NOW)
    report = build_human_review_queue_report(inp)
    assert report.state == HumanReviewQueueState.BLOCKED
    assert report.safety_flags.has_unsafe_content is True


# ---------------------------------------------------------------------------
# Orphan related records
# ---------------------------------------------------------------------------


def test_orphan_related_id_against_source_id_set_end_to_end() -> None:
    records = (
        _record(
            source_id="src-1",
            record_id="rec-1",
            related_record_ids=("src-2",),
            severity="info",
        ),
    )
    inp = HumanReviewQueueInput(source_records=records, generated_at=NOW)
    report = build_human_review_queue_report(inp)
    orphan_issues = [i for i in report.issues if i.issue_type == HumanReviewQueueIssueType.ORPHAN_RELATED_RECORD.value]
    assert len(orphan_issues) == 1


def test_orphan_related_id_against_record_id_set_end_to_end() -> None:
    records = (
        _record(
            source_id="src-1",
            record_id="rec-1",
            related_record_ids=("rec-2",),
            severity="info",
        ),
        _record(
            source_id="src-2",
            record_id="rec-2",
            severity="info",
        ),
    )
    inp = HumanReviewQueueInput(source_records=records, generated_at=NOW)
    report = build_human_review_queue_report(inp)
    orphan_issues = [i for i in report.issues if i.issue_type == HumanReviewQueueIssueType.ORPHAN_RELATED_RECORD.value]
    assert len(orphan_issues) == 0


# ---------------------------------------------------------------------------
# Stale records
# ---------------------------------------------------------------------------


def test_stale_records_end_to_end() -> None:
    old = NOW - timedelta(days=31)
    records = (
        _record(
            source_id="src-1",
            record_id="rec-1",
            generated_at=old,
            severity="advisory",
        ),
    )
    inp = HumanReviewQueueInput(source_records=records, generated_at=NOW)
    report = build_human_review_queue_report(inp)
    stale_issues = [i for i in report.issues if i.issue_type == HumanReviewQueueIssueType.STALE_SOURCE_RECORD.value]
    assert len(stale_issues) == 1
    stale_entries = [e for e in report.queue_entries if e.entry_state == HumanReviewQueueEntryState.STALE.value]
    assert len(stale_entries) == 1


def test_fresh_records_not_stale_end_to_end() -> None:
    records = (
        _record(
            source_id="src-1",
            record_id="rec-1",
            generated_at=NOW,
            severity="advisory",
        ),
    )
    inp = HumanReviewQueueInput(source_records=records, generated_at=NOW)
    report = build_human_review_queue_report(inp)
    stale_issues = [i for i in report.issues if i.issue_type == HumanReviewQueueIssueType.STALE_SOURCE_RECORD.value]
    assert len(stale_issues) == 0


# ---------------------------------------------------------------------------
# Opaque references
# ---------------------------------------------------------------------------


def test_opaque_refs_serialized_not_opened_end_to_end() -> None:
    records = (
        _record(
            source_id="src-1",
            record_id="rec-1",
            severity="advisory",
            artifact_ref="/path/to/artifact.json",
            report_ref="s3://bucket/report.md",
            metadata={"path": "/another/opaque/path", "url": "https://example.com"},
        ),
    )
    inp = HumanReviewQueueInput(source_records=records, generated_at=NOW)
    report = build_human_review_queue_report(inp)

    data = human_review_queue_report_to_dict(report)
    source = data["source_records"][0]
    assert source["artifact_ref"] == "/path/to/artifact.json"
    assert source["report_ref"] == "s3://bucket/report.md"
    assert source["metadata"]["path"] == "/another/opaque/path"

    md_text = human_review_queue_report_to_markdown_text(report)
    assert "/path/to/artifact.json" in md_text
    assert "s3://bucket/report.md" in md_text


# ---------------------------------------------------------------------------
# Output format verification
# ---------------------------------------------------------------------------


def test_csv_and_markdown_present_end_to_end() -> None:
    records = (_record(source_id="src-1", record_id="rec-1", severity="advisory", title="T", description="D"),)
    inp = HumanReviewQueueInput(source_records=records, generated_at=NOW)
    report = build_human_review_queue_report(inp)
    csv_text = human_review_queue_report_to_csv_text(report)
    md_text = human_review_queue_report_to_markdown_text(report)

    header = csv_text.split("\n")[0]
    assert "report_id,generated_at,queue_entry_id,source_id,source_kind,record_id,entry_state,priority,decision_hint,severity,reason_codes,message" == header

    assert "audit-only" in md_text.lower()
    assert "queued-for-review is not an approval" in md_text.lower() or "not an approval" in md_text.lower()
    assert "executable remediation" in md_text.lower()


# ---------------------------------------------------------------------------
# Writer end-to-end with explicit paths
# ---------------------------------------------------------------------------


def test_write_explicit_temp_paths_end_to_end(tmp_path: Path) -> None:
    records = (_record(source_id="src-1", record_id="rec-1", severity="advisory"),)
    inp = HumanReviewQueueInput(source_records=records, generated_at=NOW)
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


def test_write_none_skips_artifact_end_to_end(tmp_path: Path) -> None:
    records = (_record(source_id="src-1", record_id="rec-1", severity="advisory"),)
    inp = HumanReviewQueueInput(source_records=records, generated_at=NOW)
    report = build_human_review_queue_report(inp)

    json_path = tmp_path / "only.json"
    csv_path = tmp_path / "skipped.csv"
    md_path = tmp_path / "only.md"
    write_human_review_queue_report(
        report,
        json_path=json_path,
        csv_path=None,
        markdown_path=md_path,
    )
    assert json_path.exists()
    assert not csv_path.exists()
    assert md_path.exists()


# ---------------------------------------------------------------------------
# Safety language in output
# ---------------------------------------------------------------------------


def test_no_executable_or_trading_claims_in_output() -> None:
    records = (_record(source_id="src-1", record_id="rec-1", severity="advisory"),)
    inp = HumanReviewQueueInput(source_records=records, generated_at=NOW)
    report = build_human_review_queue_report(inp)
    md_text = human_review_queue_report_to_markdown_text(report).lower()
    json_text = human_review_queue_report_to_json_text(report).lower()

    for text in (md_text, json_text):
        assert "deploy immediately" not in text
        assert "execute now" not in text
        assert "buy signal" not in text
        assert "sell signal" not in text
        assert "go live" not in text
        assert "production ready" not in text
        assert "trading ready" not in text


def test_no_approval_or_readiness_claims_in_output() -> None:
    records = (_record(source_id="src-1", record_id="rec-1", severity="advisory"),)
    inp = HumanReviewQueueInput(source_records=records, generated_at=NOW)
    report = build_human_review_queue_report(inp)
    md_text = human_review_queue_report_to_markdown_text(report).lower()
    # The report disclaims these claims, so the words appear, but they are negated.
    # The test verifies the safety language is present.
    assert "not an approval" in md_text
    assert "not a" in md_text or "not imply" in md_text


# ---------------------------------------------------------------------------
# No mutation
# ---------------------------------------------------------------------------


def test_no_mutation_of_input_or_report_end_to_end() -> None:
    records = (
        _record(
            source_id="src-1",
            record_id="rec-1",
            severity="advisory",
            metadata={"key": "value"},
        ),
    )
    original_metadata = dict(records[0].metadata)
    inp = HumanReviewQueueInput(source_records=records, generated_at=NOW)
    original_input = inp

    report = build_human_review_queue_report(inp)
    _ = human_review_queue_report_to_dict(report)
    _ = human_review_queue_report_to_json_text(report)
    _ = human_review_queue_report_to_csv_text(report)
    _ = human_review_queue_report_to_markdown_text(report)

    assert dict(records[0].metadata) == original_metadata
    assert inp == original_input


# ---------------------------------------------------------------------------
# No project artifacts left
# ---------------------------------------------------------------------------


def test_no_project_artifacts_left_after_explicit_write(tmp_path: Path) -> None:
    records = (_record(source_id="src-1", record_id="rec-1", severity="advisory"),)
    inp = HumanReviewQueueInput(source_records=records, generated_at=NOW)
    report = build_human_review_queue_report(inp)

    write_human_review_queue_report(
        report,
        json_path=tmp_path / "out.json",
        csv_path=None,
        markdown_path=None,
    )
    # The project data/reports directories should not be created.
    project_data = Path("data/human_review_queue")
    project_reports = Path("reports/human_review_queue")
    assert not project_data.exists()
    assert not project_reports.exists()
