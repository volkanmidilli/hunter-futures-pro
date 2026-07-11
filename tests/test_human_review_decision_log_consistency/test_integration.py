"""Integration tests for hunter.human_review_decision_log_consistency package.

MVP-42 Step 3 — End-to-end local pure flow.

Tests build MVP-40 queue reports and MVP-41 decision-log reports from in-memory
source records, feed both into the MVP-42 consistency engine, and serialize the
consistency report with the MVP-42 writer. No filesystem writes, no network, no
runtime reports, no Freqtrade, no trading actions.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import pytest

from hunter.human_review_decision_log import (
    HumanReviewDecisionLogConfig,
    HumanReviewDecisionLogInput,
    HumanReviewDecisionLogReport,
    HumanReviewDecisionLogState,
    HumanReviewDecisionOutcome,
    HumanReviewDecisionReasonCode,
    HumanReviewDecisionRecord,
    HumanReviewDecisionResult,
    HumanReviewDecisionSeverity,
    HumanReviewDecisionState,
    HumanReviewQueueEntryRef,
    build_human_review_decision_log_report,
)
from hunter.human_review_decision_log_consistency import (
    FORBIDDEN_HUMAN_REVIEW_DECISION_LOG_CONSISTENCY_TERMS,
    HumanReviewDecisionLogConsistencyConfig,
    HumanReviewDecisionLogConsistencyInput,
    HumanReviewDecisionLogConsistencyIssueType,
    HumanReviewDecisionLogConsistencyReasonCode,
    HumanReviewDecisionLogConsistencyState,
    build_human_review_decision_log_consistency_report,
    human_review_decision_log_consistency_report_to_dict,
    human_review_decision_log_consistency_report_to_json_text,
    human_review_decision_log_consistency_report_to_markdown_text,
)
from hunter.human_review_queue import (
    HumanReviewQueueConfig,
    HumanReviewQueueEntry,
    HumanReviewQueueInput,
    HumanReviewQueueEntryState,
    HumanReviewQueueReport,
    HumanReviewQueueSafetyFlags,
    HumanReviewQueueState,
    HumanReviewSourceRecord,
    build_human_review_queue_report,
)

NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _queue_record(
    *,
    source_id: str,
    record_id: str,
    state: str = "open",
    severity: str = "advisory",
    source_kind: str = "backlog_item",
    artifact_ref: str = "",
    report_ref: str = "",
) -> HumanReviewSourceRecord:
    return HumanReviewSourceRecord(
        source_id=source_id,
        source_kind=source_kind,
        record_id=record_id,
        state=state,
        severity=severity,
        generated_at=NOW,
        artifact_ref=artifact_ref,
        report_ref=report_ref,
    )


def _build_queue_report(
    *records: HumanReviewSourceRecord,
    config: HumanReviewQueueConfig | None = None,
) -> HumanReviewQueueReport:
    return build_human_review_queue_report(
        HumanReviewQueueInput(
            source_records=records,
            config=config or HumanReviewQueueConfig(),
            generated_at=NOW,
        )
    )


def _build_manual_queue_report(
    queue_entry_id: str = "qe-ok",
    entry_state: str = "not_applicable",
    priority: str = "info",
    severity: str = "info",
    reason_codes: tuple[str, ...] = ("not_applicable",),
) -> HumanReviewQueueReport:
    """Return a minimal queue report with a single caller-constructed entry.

    Used when the queue engine's derived reason_codes would not match the
    decision log engine's output. This still exercises the MVP-40 models and
    keeps the integration test focused on the MVP-42 pipeline.
    """
    return HumanReviewQueueReport(
        report_id="queue-manual",
        generated_at=NOW,
        state=HumanReviewQueueState.OK,
        project_version="0.40.0-dev",
        queue_entries=(
            HumanReviewQueueEntry(
                queue_entry_id=queue_entry_id,
                source_id="src",
                source_kind="backlog_item",
                record_id="rec-1",
                entry_state=entry_state,
                priority=priority,
                severity=severity,
                reason_codes=reason_codes,
                generated_at=NOW,
            ),
        ),
        safety_flags=HumanReviewQueueSafetyFlags(),
    )


def _decision_log_ref(
    queue_entry_id: str,
    *,
    entry_state: str = "queued",
    priority: str = "medium",
    severity: str = "advisory",
) -> HumanReviewQueueEntryRef:
    return HumanReviewQueueEntryRef(
        queue_entry_id=queue_entry_id,
        source_id="src",
        source_kind="backlog_item",
        record_id="rec-1",
        entry_state=entry_state,
        priority=priority,
        severity=severity,
        generated_at=NOW,
    )


def _decision_record(
    decision_id: str,
    queue_entry_id: str,
    *,
    outcome: str = HumanReviewDecisionOutcome.ACCEPTED_FOR_AUDIT_LOG.value,
) -> HumanReviewDecisionRecord:
    return HumanReviewDecisionRecord(
        decision_id=decision_id,
        queue_entry_id=queue_entry_id,
        reviewer="reviewer-a",
        decided_at=NOW,
        outcome=outcome,
        rationale="Decision rationale for audit review.",
        generated_at=NOW,
    )


def _build_decision_log_report(
    *,
    refs: tuple[HumanReviewQueueEntryRef, ...] = (),
    records: tuple[HumanReviewDecisionRecord, ...] = (),
    config: HumanReviewDecisionLogConfig | None = None,
) -> HumanReviewDecisionLogReport:
    return build_human_review_decision_log_report(
        HumanReviewDecisionLogInput(
            queue_entry_refs=refs,
            decision_records=records,
            config=config or HumanReviewDecisionLogConfig(),
            generated_at=NOW,
        )
    )


def _build_consistency_report(
    queue_report: HumanReviewQueueReport,
    decision_log_report: HumanReviewDecisionLogReport,
) -> HumanReviewDecisionLogConsistencyReport:
    input = HumanReviewDecisionLogConsistencyInput(
        queue_report=queue_report,
        decision_log_report=decision_log_report,
        generated_at=NOW,
    )
    return build_human_review_decision_log_consistency_report(input)


def _serialize_all(
    report: HumanReviewDecisionLogConsistencyReport,
) -> tuple[dict[str, Any], str, str]:
    data = human_review_decision_log_consistency_report_to_dict(report)
    json_text = human_review_decision_log_consistency_report_to_json_text(report)
    markdown_text = human_review_decision_log_consistency_report_to_markdown_text(report)
    return data, json_text, markdown_text


# ---------------------------------------------------------------------------
# OK path
# ---------------------------------------------------------------------------


def test_ok_path_queue_and_decision_log_rows_match() -> None:
    queue_report = _build_manual_queue_report(queue_entry_id="qe-ok")
    qe = queue_report.queue_entries[0]
    assert qe.entry_state == HumanReviewQueueEntryState.NOT_APPLICABLE.value

    decision_log_report = _build_decision_log_report(
        refs=(_decision_log_ref(qe.queue_entry_id, entry_state="not_applicable", priority="info", severity="info"),),
        records=(_decision_record("d-ok", qe.queue_entry_id, outcome=HumanReviewDecisionOutcome.NOT_APPLICABLE.value),),
    )
    assert decision_log_report.state == HumanReviewDecisionLogState.OK

    consistency_report = _build_consistency_report(queue_report, decision_log_report)
    assert consistency_report.state == HumanReviewDecisionLogConsistencyState.OK
    assert consistency_report.data_quality.matched_refs == 1
    assert consistency_report.data_quality.orphan_queue_entries == 0
    assert consistency_report.data_quality.orphan_decision_log_refs == 0
    assert not consistency_report.issues

    data, json_text, markdown_text = _serialize_all(consistency_report)
    assert data["state"] == "ok"
    assert json.loads(json_text)["state"] == "ok"
    assert "## Cross References" in markdown_text


# ---------------------------------------------------------------------------
# DEGRADED path
# ---------------------------------------------------------------------------


def test_degraded_path_orphan_queue_entry_missing_decision_log_ref() -> None:
    # Source state "pending_review" maps to a queue entry state that expects a decision.
    queue_report = _build_queue_report(
        _queue_record(source_id="src-degraded", record_id="rec-degraded", state="pending_review", severity="advisory")
    )
    qe = queue_report.queue_entries[0]
    assert qe.entry_state == HumanReviewQueueEntryState.PENDING_REVIEW.value

    decision_log_report = _build_decision_log_report()
    assert decision_log_report.state == HumanReviewDecisionLogState.NOT_APPLICABLE

    consistency_report = _build_consistency_report(queue_report, decision_log_report)
    assert consistency_report.state == HumanReviewDecisionLogConsistencyState.DEGRADED
    assert consistency_report.data_quality.orphan_queue_entries == 1
    assert any(
        issue.issue_type == HumanReviewDecisionLogConsistencyIssueType.MISSING_DECISION_LOG_REF.value
        for issue in consistency_report.issues
    )

    data, _, markdown_text = _serialize_all(consistency_report)
    assert data["state"] == "degraded"
    assert "missing decision log ref" in markdown_text.lower()


# ---------------------------------------------------------------------------
# BLOCKED path
# ---------------------------------------------------------------------------


def test_blocked_path_upstream_blocked_queue_report_carry_forward() -> None:
    queue_report = _build_queue_report(
        _queue_record(source_id="dup", record_id="rec-a"),
        _queue_record(source_id="dup", record_id="rec-b"),
    )
    assert queue_report.state == HumanReviewQueueState.BLOCKED

    decision_log_report = _build_decision_log_report()
    consistency_report = _build_consistency_report(queue_report, decision_log_report)
    assert consistency_report.state == HumanReviewDecisionLogConsistencyState.BLOCKED
    assert consistency_report.reason_codes == (
        HumanReviewDecisionLogConsistencyReasonCode.INPUT_BLOCKED,
    )

    data, _, _ = _serialize_all(consistency_report)
    assert data["state"] == "blocked"


def test_blocked_path_duplicate_queue_entry_id_fail_closed() -> None:
    qe_id = "duplicate-qe"
    queue_report = _build_queue_report(
        _queue_record(source_id="src-dup", record_id="rec-dup", state="not_applicable", severity="info")
    )
    decision_log_report = _build_decision_log_report(
        refs=(
            _decision_log_ref(qe_id, entry_state="not_applicable", priority="info", severity="info"),
            _decision_log_ref(qe_id, entry_state="not_applicable", priority="info", severity="info"),
        ),
    )
    assert decision_log_report.state == HumanReviewDecisionLogState.BLOCKED

    consistency_report = _build_consistency_report(queue_report, decision_log_report)
    assert consistency_report.state == HumanReviewDecisionLogConsistencyState.BLOCKED


# ---------------------------------------------------------------------------
# NOT_APPLICABLE path
# ---------------------------------------------------------------------------


def test_not_applicable_path_empty_inputs() -> None:
    queue_report = _build_queue_report()
    decision_log_report = _build_decision_log_report()
    consistency_report = _build_consistency_report(queue_report, decision_log_report)

    assert queue_report.state == HumanReviewQueueState.NOT_APPLICABLE
    assert decision_log_report.state == HumanReviewDecisionLogState.NOT_APPLICABLE
    assert consistency_report.state == HumanReviewDecisionLogConsistencyState.NOT_APPLICABLE
    assert consistency_report.data_quality.total_queue_entries == 0
    assert consistency_report.data_quality.total_decision_log_refs == 0
    assert consistency_report.reason_codes == (
        HumanReviewDecisionLogConsistencyReasonCode.NOT_APPLICABLE,
    )

    data, _, markdown_text = _serialize_all(consistency_report)
    assert data["state"] == "not_applicable"
    assert "not applicable" in markdown_text.lower()


# ---------------------------------------------------------------------------
# ORPHANED preservation
# ---------------------------------------------------------------------------


def test_orphaned_decision_result_for_unknown_queue_entry() -> None:
    """Decision log engine produces ORPHANED results for unknown queue_entry_ids."""
    decision_log_report = _build_decision_log_report(
        records=(_decision_record("d-orphan", "unknown-qe"),),
    )
    assert decision_log_report.state == HumanReviewDecisionLogState.DEGRADED
    assert any(
        result.decision_state == HumanReviewDecisionState.ORPHANED.value
        for result in decision_log_report.decision_results
    )

    # Without a matching queue entry, the consistency layer has no cross-reference
    # to check and the empty-input rule makes the report NOT_APPLICABLE.
    queue_report = _build_queue_report()
    consistency_report = _build_consistency_report(queue_report, decision_log_report)
    assert consistency_report.state == HumanReviewDecisionLogConsistencyState.NOT_APPLICABLE


def test_orphaned_decision_log_ref_without_queue_entry_detected() -> None:
    """A decision log ref with no matching queue entry is detected as an orphan."""
    queue_report = _build_queue_report()
    decision_log_report = _build_decision_log_report(
        refs=(_decision_log_ref("unknown-qe", entry_state="not_applicable", priority="info", severity="info"),),
    )
    consistency_report = _build_consistency_report(queue_report, decision_log_report)
    assert consistency_report.state == HumanReviewDecisionLogConsistencyState.DEGRADED
    assert consistency_report.data_quality.orphan_decision_log_refs == 1
    assert any(
        issue.issue_type == HumanReviewDecisionLogConsistencyIssueType.ORPHAN_DECISION_LOG_REF.value
        for issue in consistency_report.issues
    )


def test_orphaned_status_inconsistent_when_queue_entry_exists() -> None:
    """A decision log result claiming ORPHANED for an existing queue entry is inconsistent."""
    queue_report = _build_queue_report(
        _queue_record(source_id="src-orphan", record_id="rec-orphan", state="not_applicable", severity="info")
    )
    qe_id = queue_report.queue_entries[0].queue_entry_id

    decision_log_report = HumanReviewDecisionLogReport(
        report_id="dlog-orphan-manual",
        generated_at=NOW,
        state=HumanReviewDecisionLogState.OK,
        project_version="0.41.0-dev",
        queue_entry_refs=(_decision_log_ref(qe_id, entry_state="not_applicable", priority="info", severity="info"),),
        decision_results=(
            HumanReviewDecisionResult(
                queue_entry_id=qe_id,
                decision_state=HumanReviewDecisionState.ORPHANED.value,
                severity=HumanReviewDecisionSeverity.ADVISORY.value,
                reason_codes=(HumanReviewDecisionReasonCode.ORPHAN_DECISION.value,),
                generated_at=NOW,
            ),
        ),
    )
    consistency_report = _build_consistency_report(queue_report, decision_log_report)
    assert consistency_report.state == HumanReviewDecisionLogConsistencyState.DEGRADED
    assert any(
        issue.issue_type == HumanReviewDecisionLogConsistencyIssueType.INCONSISTENT_ORPHAN_STATUS.value
        for issue in consistency_report.issues
    )


# ---------------------------------------------------------------------------
# Opaque ref boundary
# ---------------------------------------------------------------------------


def test_opaque_refs_preserved_as_strings_and_not_opened(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Artifact/report refs are opaque strings; the writer never opens them."""
    artifact_ref = "s3://bucket/artifact/alpha.bin"
    report_ref = "file:///data/reports/queue-2026-01-01.md"

    queue_report = _build_queue_report(
        _queue_record(
            source_id="src-opaque",
            record_id="rec-opaque",
            state="not_applicable",
            severity="info",
            artifact_ref=artifact_ref,
            report_ref=report_ref,
        )
    )
    qe_id = queue_report.queue_entries[0].queue_entry_id

    # Use a manually-built queue report with matching fields so the consistency
    # report is OK; the opaque-ref boundary still holds either way.
    manual_queue_report = _build_manual_queue_report(
        queue_entry_id=qe_id,
        entry_state=HumanReviewQueueEntryState.NOT_APPLICABLE.value,
        priority="info",
        severity="info",
        reason_codes=("not_applicable",),
    )

    decision_log_report = _build_decision_log_report(
        refs=(_decision_log_ref(qe_id, entry_state="not_applicable", priority="info", severity="info"),),
        records=(_decision_record("d-opaque", qe_id, outcome=HumanReviewDecisionOutcome.NOT_APPLICABLE.value),),
    )
    consistency_report = _build_consistency_report(manual_queue_report, decision_log_report)
    assert consistency_report.state == HumanReviewDecisionLogConsistencyState.OK

    def _unexpected_open(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("integration test must not open refs")

    monkeypatch.setattr("builtins.open", _unexpected_open)
    data, _, _ = _serialize_all(consistency_report)

    # The consistency report only carries upstream report IDs as opaque strings.
    assert isinstance(data["queue_report_id"], str)
    assert isinstance(data["decision_log_report_id"], str)
    assert data["queue_report_id"] == manual_queue_report.report_id
    assert data["decision_log_report_id"] == decision_log_report.report_id


# ---------------------------------------------------------------------------
# Writer safety
# ---------------------------------------------------------------------------


def _all_text_outputs(data: dict[str, Any], json_text: str, markdown_text: str) -> str:
    return " ".join([
        json.dumps(data, sort_keys=True, default=str),
        json_text,
        markdown_text,
    ]).lower()


def test_writer_outputs_contain_no_executable_or_trading_language() -> None:
    queue_report = _build_manual_queue_report(queue_entry_id="qe-safety")
    qe_id = queue_report.queue_entries[0].queue_entry_id
    decision_log_report = _build_decision_log_report(
        refs=(_decision_log_ref(qe_id, entry_state="not_applicable", priority="info", severity="info"),),
        records=(_decision_record("d-safety", qe_id, outcome=HumanReviewDecisionOutcome.NOT_APPLICABLE.value),),
    )
    consistency_report = _build_consistency_report(queue_report, decision_log_report)
    data, json_text, markdown_text = _serialize_all(consistency_report)
    combined = _all_text_outputs(data, json_text, markdown_text)

    # Safety notice contains required boilerplate; exclude it from the guard.
    exclude = {
        "task assignment",
        "task completion",
        "executable remediation plan",
    }
    for term in FORBIDDEN_HUMAN_REVIEW_DECISION_LOG_CONSISTENCY_TERMS:
        if term in exclude:
            continue
        assert term not in combined, f"forbidden term in serialized output: {term!r}"


def test_writer_outputs_have_audit_only_safety_notice() -> None:
    queue_report = _build_queue_report()
    decision_log_report = _build_decision_log_report()
    consistency_report = _build_consistency_report(queue_report, decision_log_report)
    data, json_text, markdown_text = _serialize_all(consistency_report)

    assert "audit-only" in data["safety_notice"].lower()
    assert "audit-only" in json_text.lower()
    assert "audit-only" in markdown_text.lower()
    assert "human-audit" in markdown_text.lower()


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_deterministic_end_to_end_ids_and_outputs() -> None:
    queue_report = _build_manual_queue_report(queue_entry_id="qe-det")
    qe_id = queue_report.queue_entries[0].queue_entry_id
    decision_log_report = _build_decision_log_report(
        refs=(_decision_log_ref(qe_id, entry_state="not_applicable", priority="info", severity="info"),),
        records=(_decision_record("d-det", qe_id, outcome=HumanReviewDecisionOutcome.NOT_APPLICABLE.value),),
    )

    r1 = _build_consistency_report(queue_report, decision_log_report)
    r2 = _build_consistency_report(queue_report, decision_log_report)
    assert r1.report_id == r2.report_id
    assert [cr.cross_reference_id for cr in r1.cross_references] == [
        cr.cross_reference_id for cr in r2.cross_references
    ]
    assert [issue.issue_id for issue in r1.issues] == [issue.issue_id for issue in r2.issues]

    d1, j1, m1 = _serialize_all(r1)
    d2, j2, m2 = _serialize_all(r2)
    assert d1 == d2
    assert j1 == j2
    assert m1 == m2


def test_deterministic_orphan_and_mismatch_paths() -> None:
    queue_report = _build_queue_report(
        _queue_record(source_id="src-det2", record_id="rec-det2", state="pending_review", severity="advisory")
    )
    qe_id = queue_report.queue_entries[0].queue_entry_id
    decision_log_report = _build_decision_log_report(
        records=(_decision_record("d-det2", f"not-{qe_id}"),),
    )

    r1 = _build_consistency_report(queue_report, decision_log_report)
    r2 = _build_consistency_report(queue_report, decision_log_report)
    assert r1.report_id == r2.report_id
    assert [cr.cross_reference_id for cr in r1.cross_references] == [
        cr.cross_reference_id for cr in r2.cross_references
    ]
    assert [issue.issue_id for issue in r1.issues] == [issue.issue_id for issue in r2.issues]

    d1, j1, m1 = _serialize_all(r1)
    d2, j2, m2 = _serialize_all(r2)
    assert d1 == d2
    assert j1 == j2
    assert m1 == m2
