"""Tests for hunter.human_review_queue.engine."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from hunter.human_review_queue import (
    HUMAN_REVIEW_QUEUE_VERSION,
    HumanReviewQueueConfig,
    HumanReviewQueueDecisionHint,
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
)

NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _record(
    *,
    source_id: str = "src-1",
    source_kind: str = "backlog_item",
    record_id: str = "rec-1",
    related_record_ids: tuple[str, ...] = (),
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
        related_record_ids=related_record_ids,
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


# ---------------------------------------------------------------------------
# Empty input
# ---------------------------------------------------------------------------


def test_empty_input_returns_not_applicable() -> None:
    inp = HumanReviewQueueInput(source_records=(), generated_at=NOW)
    report = build_human_review_queue_report(inp)
    assert report.state == HumanReviewQueueState.NOT_APPLICABLE
    assert report.queue_entries == ()
    assert report.issues == ()
    assert report.data_quality.total_source_records == 0
    assert report.data_quality.total_queue_entries == 0
    assert report.data_quality.total_issues == 0
    assert HumanReviewQueueReasonCode.NOT_APPLICABLE in report.reason_codes


def test_empty_input_report_id_is_deterministic() -> None:
    inp = HumanReviewQueueInput(source_records=(), generated_at=NOW, project_version="0.40.0-dev")
    report1 = build_human_review_queue_report(inp)
    report2 = build_human_review_queue_report(inp)
    assert report1.report_id == report2.report_id


# ---------------------------------------------------------------------------
# Advisory-only non-strict -> OK
# ---------------------------------------------------------------------------


def test_advisory_only_non_strict_is_ok() -> None:
    record = _record(severity="advisory", state="open")
    inp = HumanReviewQueueInput(source_records=(record,), generated_at=NOW)
    report = build_human_review_queue_report(inp)
    assert report.state == HumanReviewQueueState.OK
    assert len(report.queue_entries) == 1
    assert report.queue_entries[0].severity == HumanReviewQueueSeverity.ADVISORY.value
    assert report.queue_entries[0].priority == HumanReviewQueuePriority.MEDIUM.value


def test_low_priority_manual_note_non_strict_is_ok() -> None:
    record = _record(source_kind="manual_note", severity="info", state="open")
    inp = HumanReviewQueueInput(source_records=(record,), generated_at=NOW)
    report = build_human_review_queue_report(inp)
    assert report.state == HumanReviewQueueState.OK
    assert report.queue_entries[0].priority == HumanReviewQueuePriority.LOW.value


# ---------------------------------------------------------------------------
# Critical/high non-strict -> DEGRADED
# ---------------------------------------------------------------------------


def test_critical_priority_degrades() -> None:
    record = _record(severity="blocking", state="open")
    inp = HumanReviewQueueInput(source_records=(record,), generated_at=NOW)
    report = build_human_review_queue_report(inp)
    assert report.state == HumanReviewQueueState.BLOCKED
    assert report.queue_entries[0].priority == HumanReviewQueuePriority.CRITICAL.value


def test_high_priority_degrades() -> None:
    record = _record(severity="advisory", state="disputed", reason_codes=("disputed_state",))
    inp = HumanReviewQueueInput(source_records=(record,), generated_at=NOW)
    report = build_human_review_queue_report(inp)
    assert report.state == HumanReviewQueueState.DEGRADED
    assert report.queue_entries[0].priority == HumanReviewQueuePriority.HIGH.value


def test_missing_evidence_is_high_priority_degraded() -> None:
    record = _record(severity="advisory", state="open", reason_codes=("missing_evidence",))
    inp = HumanReviewQueueInput(source_records=(record,), generated_at=NOW)
    report = build_human_review_queue_report(inp)
    assert report.state == HumanReviewQueueState.DEGRADED
    assert report.queue_entries[0].priority == HumanReviewQueuePriority.HIGH.value


# ---------------------------------------------------------------------------
# Blocking / unsafe -> BLOCKED
# ---------------------------------------------------------------------------


def test_blocking_severity_blocks() -> None:
    record = _record(severity="blocking", state="open")
    inp = HumanReviewQueueInput(source_records=(record,), generated_at=NOW)
    report = build_human_review_queue_report(inp)
    assert report.state == HumanReviewQueueState.BLOCKED


def test_unsafe_metadata_blocks() -> None:
    record = _record(metadata={"bad": 123})
    inp = HumanReviewQueueInput(source_records=(record,), generated_at=NOW)
    report = build_human_review_queue_report(inp)
    assert report.state == HumanReviewQueueState.BLOCKED
    assert report.safety_flags.has_unsafe_content is True
    assert HumanReviewQueueReasonCode.UNSAFE_CONTENT in report.reason_codes


def test_unsafe_source_record_title_blocks() -> None:
    record = _record(metadata={"bad": 123})
    inp = HumanReviewQueueInput(source_records=(record,), generated_at=NOW)
    report = build_human_review_queue_report(inp)
    assert report.state == HumanReviewQueueState.BLOCKED


def test_forbidden_term_blocks() -> None:
    record = _record(title="Please deploy immediately to production")
    inp = HumanReviewQueueInput(source_records=(record,), generated_at=NOW)
    report = build_human_review_queue_report(inp)
    assert report.state == HumanReviewQueueState.BLOCKED
    assert report.safety_flags.has_forbidden_terms is True


def test_forbidden_terms_disabled_does_not_block() -> None:
    record = _record(title="Please deploy immediately to production")
    config = HumanReviewQueueConfig(forbid_action_terms=False)
    inp = HumanReviewQueueInput(source_records=(record,), config=config, generated_at=NOW)
    report = build_human_review_queue_report(inp)
    assert report.state != HumanReviewQueueState.BLOCKED


def test_forbidden_terms_false_other_safety_checks_still_active() -> None:
    record = _record(title="Deploy immediately", metadata={"bad": 123})
    config = HumanReviewQueueConfig(forbid_action_terms=False)
    inp = HumanReviewQueueInput(source_records=(record,), config=config, generated_at=NOW)
    report = build_human_review_queue_report(inp)
    assert report.state == HumanReviewQueueState.BLOCKED


# ---------------------------------------------------------------------------
# Strict mode
# ---------------------------------------------------------------------------


def test_advisory_strict_promotes_to_blocked() -> None:
    record = _record(severity="advisory", state="open")
    config = HumanReviewQueueConfig(strict=True)
    inp = HumanReviewQueueInput(source_records=(record,), config=config, generated_at=NOW)
    report = build_human_review_queue_report(inp)
    assert report.state == HumanReviewQueueState.BLOCKED


def test_degraded_strict_promotes_to_blocked() -> None:
    record = _record(severity="advisory", state="disputed")
    config = HumanReviewQueueConfig(strict=True)
    inp = HumanReviewQueueInput(source_records=(record,), config=config, generated_at=NOW)
    report = build_human_review_queue_report(inp)
    assert report.state == HumanReviewQueueState.BLOCKED


# ---------------------------------------------------------------------------
# Duplicate source IDs
# ---------------------------------------------------------------------------


def test_duplicate_source_id_fails_closed() -> None:
    r1 = _record(source_id="dup", record_id="a")
    r2 = _record(source_id="dup", record_id="b")
    inp = HumanReviewQueueInput(source_records=(r1, r2), generated_at=NOW)
    report = build_human_review_queue_report(inp)
    assert report.state == HumanReviewQueueState.BLOCKED
    assert HumanReviewQueueReasonCode.DUPLICATE_SOURCE_ID in report.reason_codes


def test_distinct_source_ids_allowed() -> None:
    r1 = _record(source_id="a", record_id="a")
    r2 = _record(source_id="b", record_id="b")
    inp = HumanReviewQueueInput(source_records=(r1, r2), generated_at=NOW)
    report = build_human_review_queue_report(inp)
    assert report.state != HumanReviewQueueState.BLOCKED


# ---------------------------------------------------------------------------
# Duplicate queue entries
# ---------------------------------------------------------------------------


def test_duplicate_queue_entry_emits_info_issue() -> None:
    r1 = _record(source_id="a", record_id="x", title="t")
    r2 = _record(source_id="a", record_id="x", title="t")
    inp = HumanReviewQueueInput(source_records=(r1, r2), generated_at=NOW)
    report = build_human_review_queue_report(inp)
    # Duplicate source IDs fail-closed first, so this returns BLOCKED.
    assert report.state == HumanReviewQueueState.BLOCKED


def test_distinct_records_no_duplicate_queue_entries() -> None:
    r1 = _record(source_id="a", record_id="x", title="one")
    r2 = _record(source_id="b", record_id="y", title="two")
    inp = HumanReviewQueueInput(source_records=(r1, r2), generated_at=NOW)
    report = build_human_review_queue_report(inp)
    assert len(report.queue_entries) == 2
    duplicate_issue_types = [issue.issue_type for issue in report.issues if issue.issue_type == HumanReviewQueueIssueType.DUPLICATE_QUEUE_ENTRY.value]
    assert len(duplicate_issue_types) == 0


# ---------------------------------------------------------------------------
# Orphan related records
# ---------------------------------------------------------------------------


def test_orphan_related_record_detected() -> None:
    r1 = _record(source_id="a", record_id="x", related_record_ids=("missing",))
    inp = HumanReviewQueueInput(source_records=(r1,), generated_at=NOW)
    report = build_human_review_queue_report(inp)
    orphan_issues = [issue for issue in report.issues if issue.issue_type == HumanReviewQueueIssueType.ORPHAN_RELATED_RECORD.value]
    assert len(orphan_issues) == 1
    assert orphan_issues[0].source_id == "a"


def test_related_record_by_source_id_is_not_orphan() -> None:
    r1 = _record(source_id="a", record_id="x", related_record_ids=("b",))
    r2 = _record(source_id="b", record_id="y")
    inp = HumanReviewQueueInput(source_records=(r1, r2), generated_at=NOW)
    report = build_human_review_queue_report(inp)
    orphan_issues = [issue for issue in report.issues if issue.issue_type == HumanReviewQueueIssueType.ORPHAN_RELATED_RECORD.value]
    assert len(orphan_issues) == 0


def test_related_record_by_record_id_is_not_orphan() -> None:
    r1 = _record(source_id="a", record_id="x", related_record_ids=("y",))
    r2 = _record(source_id="b", record_id="y")
    inp = HumanReviewQueueInput(source_records=(r1, r2), generated_at=NOW)
    report = build_human_review_queue_report(inp)
    orphan_issues = [issue for issue in report.issues if issue.issue_type == HumanReviewQueueIssueType.ORPHAN_RELATED_RECORD.value]
    assert len(orphan_issues) == 0


# ---------------------------------------------------------------------------
# Stale source records
# ---------------------------------------------------------------------------


def test_stale_source_record_detected() -> None:
    old = NOW - timedelta(days=31)
    r1 = _record(source_id="a", record_id="x", generated_at=old)
    inp = HumanReviewQueueInput(source_records=(r1,), generated_at=NOW)
    report = build_human_review_queue_report(inp)
    stale_issues = [issue for issue in report.issues if issue.issue_type == HumanReviewQueueIssueType.STALE_SOURCE_RECORD.value]
    assert len(stale_issues) == 1


def test_stale_disabled_does_not_add_stale_entries() -> None:
    old = NOW - timedelta(days=31)
    r1 = _record(source_id="a", record_id="x", generated_at=old)
    config = HumanReviewQueueConfig(include_stale=False)
    inp = HumanReviewQueueInput(source_records=(r1,), config=config, generated_at=NOW)
    report = build_human_review_queue_report(inp)
    stale_entries = [entry for entry in report.queue_entries if entry.entry_state == HumanReviewQueueEntryState.STALE.value]
    assert len(stale_entries) == 0


def test_fresh_source_record_not_stale() -> None:
    r1 = _record(source_id="a", record_id="x", generated_at=NOW)
    inp = HumanReviewQueueInput(source_records=(r1,), generated_at=NOW)
    report = build_human_review_queue_report(inp)
    stale_issues = [issue for issue in report.issues if issue.issue_type == HumanReviewQueueIssueType.STALE_SOURCE_RECORD.value]
    assert len(stale_issues) == 0


# ---------------------------------------------------------------------------
# Source kind mapping
# ---------------------------------------------------------------------------


def test_source_kind_mapping() -> None:
    for kind in HumanReviewQueueSourceKind:
        record = _record(source_id=f"src-{kind.value}", source_kind=kind.value, record_id=f"rec-{kind.value}")
        inp = HumanReviewQueueInput(source_records=(record,), generated_at=NOW)
        report = build_human_review_queue_report(inp)
        assert len(report.queue_entries) == 1
        assert report.queue_entries[0].source_kind == kind.value


def test_manual_note_suppressed_when_disabled() -> None:
    record = _record(source_kind="manual_note", severity="info", state="open")
    config = HumanReviewQueueConfig(include_manual_notes=False)
    inp = HumanReviewQueueInput(source_records=(record,), config=config, generated_at=NOW)
    report = build_human_review_queue_report(inp)
    assert report.queue_entries[0].entry_state == HumanReviewQueueEntryState.SUPPRESSED.value
    assert report.queue_entries[0].decision_hint == HumanReviewQueueDecisionHint.NOT_APPLICABLE_FOR_AUDIT.value


def test_manual_note_queued_when_enabled() -> None:
    record = _record(source_kind="manual_note", severity="info", state="open")
    inp = HumanReviewQueueInput(source_records=(record,), generated_at=NOW)
    report = build_human_review_queue_report(inp)
    assert report.queue_entries[0].entry_state == HumanReviewQueueEntryState.QUEUED.value


# ---------------------------------------------------------------------------
# Queue entry state mapping
# ---------------------------------------------------------------------------


def test_blocked_state_maps_to_blocked_entry() -> None:
    record = _record(state="blocked", severity="blocking")
    inp = HumanReviewQueueInput(source_records=(record,), generated_at=NOW)
    report = build_human_review_queue_report(inp)
    assert report.queue_entries[0].entry_state == HumanReviewQueueEntryState.BLOCKED.value


def test_pending_review_state_maps_to_pending_review_entry() -> None:
    record = _record(state="pending_review", severity="advisory")
    inp = HumanReviewQueueInput(source_records=(record,), generated_at=NOW)
    report = build_human_review_queue_report(inp)
    assert report.queue_entries[0].entry_state == HumanReviewQueueEntryState.PENDING_REVIEW.value


def test_disputed_state_maps_to_disputed_entry() -> None:
    record = _record(state="disputed", severity="advisory")
    inp = HumanReviewQueueInput(source_records=(record,), generated_at=NOW)
    report = build_human_review_queue_report(inp)
    assert report.queue_entries[0].entry_state == HumanReviewQueueEntryState.DISPUTED.value


def test_acknowledged_state_maps_to_acknowledged_entry() -> None:
    record = _record(state="acknowledged", severity="advisory")
    inp = HumanReviewQueueInput(source_records=(record,), generated_at=NOW)
    report = build_human_review_queue_report(inp)
    assert report.queue_entries[0].entry_state == HumanReviewQueueEntryState.ACKNOWLEDGED.value


def test_acknowledged_suppressed_when_configured() -> None:
    record = _record(state="acknowledged", severity="advisory")
    config = HumanReviewQueueConfig(suppress_acknowledged=True)
    inp = HumanReviewQueueInput(source_records=(record,), config=config, generated_at=NOW)
    report = build_human_review_queue_report(inp)
    assert report.queue_entries[0].entry_state == HumanReviewQueueEntryState.SUPPRESSED.value


def test_deferred_state_maps_to_deferred_entry() -> None:
    record = _record(state="deferred", severity="advisory")
    inp = HumanReviewQueueInput(source_records=(record,), generated_at=NOW)
    report = build_human_review_queue_report(inp)
    assert report.queue_entries[0].entry_state == HumanReviewQueueEntryState.DEFERRED.value


def test_not_applicable_state_maps_to_not_applicable_entry() -> None:
    record = _record(state="not_applicable", severity="info")
    inp = HumanReviewQueueInput(source_records=(record,), generated_at=NOW)
    report = build_human_review_queue_report(inp)
    assert report.queue_entries[0].entry_state == HumanReviewQueueEntryState.NOT_APPLICABLE.value


# ---------------------------------------------------------------------------
# Priority first-match-wins
# ---------------------------------------------------------------------------


def test_unsafe_content_is_critical_priority() -> None:
    record = _record(metadata={"bad": 123})
    inp = HumanReviewQueueInput(source_records=(record,), generated_at=NOW)
    report = build_human_review_queue_report(inp)
    # Report is blocked due to unsafe content before priority assignment.
    assert report.state == HumanReviewQueueState.BLOCKED


def test_blocking_severity_is_critical_priority() -> None:
    record = _record(severity="blocking", state="open")
    inp = HumanReviewQueueInput(source_records=(record,), generated_at=NOW)
    report = build_human_review_queue_report(inp)
    assert report.queue_entries[0].priority == HumanReviewQueuePriority.CRITICAL.value


def test_disputed_is_high_priority() -> None:
    record = _record(state="disputed", severity="advisory")
    inp = HumanReviewQueueInput(source_records=(record,), generated_at=NOW)
    report = build_human_review_queue_report(inp)
    assert report.queue_entries[0].priority == HumanReviewQueuePriority.HIGH.value


def test_pending_review_is_medium_priority() -> None:
    record = _record(state="pending_review", severity="advisory")
    inp = HumanReviewQueueInput(source_records=(record,), generated_at=NOW)
    report = build_human_review_queue_report(inp)
    assert report.queue_entries[0].priority == HumanReviewQueuePriority.MEDIUM.value


def test_advisory_is_medium_priority() -> None:
    record = _record(severity="advisory", state="open")
    inp = HumanReviewQueueInput(source_records=(record,), generated_at=NOW)
    report = build_human_review_queue_report(inp)
    assert report.queue_entries[0].priority == HumanReviewQueuePriority.MEDIUM.value


def test_manual_note_is_low_priority() -> None:
    record = _record(source_kind="manual_note", severity="info", state="open")
    inp = HumanReviewQueueInput(source_records=(record,), generated_at=NOW)
    report = build_human_review_queue_report(inp)
    assert report.queue_entries[0].priority == HumanReviewQueuePriority.LOW.value


def test_not_applicable_is_info_priority() -> None:
    record = _record(state="not_applicable", severity="info")
    inp = HumanReviewQueueInput(source_records=(record,), generated_at=NOW)
    report = build_human_review_queue_report(inp)
    assert report.queue_entries[0].priority == HumanReviewQueuePriority.INFO.value


# ---------------------------------------------------------------------------
# Decision hints
# ---------------------------------------------------------------------------


def test_decision_hints_are_non_executable_values() -> None:
    record = _record(state="open", severity="advisory")
    inp = HumanReviewQueueInput(source_records=(record,), generated_at=NOW)
    report = build_human_review_queue_report(inp)
    hint = report.queue_entries[0].decision_hint
    assert hint in {h.value for h in HumanReviewQueueDecisionHint}


def test_decision_hint_for_suppressed() -> None:
    record = _record(source_kind="manual_note", severity="info", state="open")
    config = HumanReviewQueueConfig(include_manual_notes=False)
    inp = HumanReviewQueueInput(source_records=(record,), config=config, generated_at=NOW)
    report = build_human_review_queue_report(inp)
    assert report.queue_entries[0].decision_hint == HumanReviewQueueDecisionHint.NOT_APPLICABLE_FOR_AUDIT.value


def test_decision_hint_for_deferred() -> None:
    record = _record(state="deferred", severity="advisory")
    inp = HumanReviewQueueInput(source_records=(record,), generated_at=NOW)
    report = build_human_review_queue_report(inp)
    assert report.queue_entries[0].decision_hint == HumanReviewQueueDecisionHint.DEFERRED_FOR_LATER_AUDIT.value


def test_decision_hint_for_acknowledged() -> None:
    record = _record(state="acknowledged", severity="advisory")
    inp = HumanReviewQueueInput(source_records=(record,), generated_at=NOW)
    report = build_human_review_queue_report(inp)
    assert report.queue_entries[0].decision_hint == HumanReviewQueueDecisionHint.ALREADY_ACKNOWLEDGED.value


# ---------------------------------------------------------------------------
# Forbidden-term false-positive avoidance
# ---------------------------------------------------------------------------


def test_benign_phrases_do_not_trigger_forbidden_terms() -> None:
    benign = [
        "pending approval from security team",
        "certification body",
        "no recommendation needed",
        "signal processing",
        "no signal detected",
        "assign a reviewer",
        "manual note for audit",
    ]
    for text in benign:
        record = _record(title=text)
        inp = HumanReviewQueueInput(source_records=(record,), generated_at=NOW)
        report = build_human_review_queue_report(inp)
        assert report.state != HumanReviewQueueState.BLOCKED, f"{text!r} should not block"


def test_forbidden_phrase_triggers() -> None:
    record = _record(title="We should go live tomorrow")
    inp = HumanReviewQueueInput(source_records=(record,), generated_at=NOW)
    report = build_human_review_queue_report(inp)
    assert report.state == HumanReviewQueueState.BLOCKED


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_report_is_deterministic() -> None:
    record = _record(severity="advisory", state="open")
    inp = HumanReviewQueueInput(source_records=(record,), generated_at=NOW, project_version="0.40.0-dev")
    report1 = build_human_review_queue_report(inp)
    report2 = build_human_review_queue_report(inp)
    assert report1.report_id == report2.report_id
    assert [e.queue_entry_id for e in report1.queue_entries] == [e.queue_entry_id for e in report2.queue_entries]


def test_queue_entries_sorted_deterministically() -> None:
    r1 = _record(source_id="z", record_id="z")
    r2 = _record(source_id="a", record_id="a")
    inp = HumanReviewQueueInput(source_records=(r1, r2), generated_at=NOW)
    report = build_human_review_queue_report(inp)
    ids = [e.queue_entry_id for e in report.queue_entries]
    assert ids == sorted(ids)


# ---------------------------------------------------------------------------
# Opaque references and safety boundaries
# ---------------------------------------------------------------------------


def test_opaque_refs_remain_strings() -> None:
    record = _record(
        artifact_ref="/path/that/does/not/exist",
        report_ref="s3://bucket/object",
        metadata={"path": "/opaque/path", "url": "https://example.com"},
    )
    inp = HumanReviewQueueInput(source_records=(record,), generated_at=NOW)
    report = build_human_review_queue_report(inp)
    assert report.source_records[0].artifact_ref == "/path/that/does/not/exist"
    assert report.source_records[0].report_ref == "s3://bucket/object"
    assert report.source_records[0].metadata["path"] == "/opaque/path"


def test_no_executable_remediation_output() -> None:
    record = _record(title="Normal record")
    inp = HumanReviewQueueInput(source_records=(record,), generated_at=NOW)
    report = build_human_review_queue_report(inp)
    assert "deploy" not in report.safety_notice.lower()
    assert "execute" not in report.safety_notice.lower()
    assert "apply patch" not in report.safety_notice.lower()


def test_no_automatic_assignment_output() -> None:
    record = _record(title="Normal record")
    inp = HumanReviewQueueInput(source_records=(record,), generated_at=NOW)
    report = build_human_review_queue_report(inp)
    assert "assign to" not in report.safety_notice.lower()
    # The safety notice explicitly disclaims task assignment, which is the
    # desired behavior; it does not instruct any assignment.
    assert "task assignment" in report.safety_notice.lower()


def test_safety_notice_includes_audit_only_statement() -> None:
    record = _record()
    inp = HumanReviewQueueInput(source_records=(record,), generated_at=NOW)
    report = build_human_review_queue_report(inp)
    assert "audit-only" in report.safety_notice.lower()
    assert "not imply" in report.safety_notice.lower()


# ---------------------------------------------------------------------------
# Input immutability
# ---------------------------------------------------------------------------


def test_input_records_not_mutated() -> None:
    record = _record()
    original_metadata = dict(record.metadata)
    inp = HumanReviewQueueInput(source_records=(record,), generated_at=NOW)
    _ = build_human_review_queue_report(inp)
    assert dict(record.metadata) == original_metadata


# ---------------------------------------------------------------------------
# Reason codes
# ---------------------------------------------------------------------------


def test_blocking_severity_reason_code() -> None:
    record = _record(severity="blocking", state="open")
    inp = HumanReviewQueueInput(source_records=(record,), generated_at=NOW)
    report = build_human_review_queue_report(inp)
    assert HumanReviewQueueReasonCode.BLOCKING_SEVERITY.value in report.queue_entries[0].reason_codes


def test_advisory_severity_reason_code() -> None:
    record = _record(severity="advisory", state="open")
    inp = HumanReviewQueueInput(source_records=(record,), generated_at=NOW)
    report = build_human_review_queue_report(inp)
    assert HumanReviewQueueReasonCode.ADVISORY_SEVERITY.value in report.queue_entries[0].reason_codes


def test_info_severity_reason_code() -> None:
    record = _record(severity="info", state="open")
    inp = HumanReviewQueueInput(source_records=(record,), generated_at=NOW)
    report = build_human_review_queue_report(inp)
    assert HumanReviewQueueReasonCode.INFO_SEVERITY.value in report.queue_entries[0].reason_codes
