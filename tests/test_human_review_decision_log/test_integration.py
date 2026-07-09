"""Integration tests for hunter.human_review_decision_log package.

MVP-41 Step 3 — SPEC-042 Local Research Human Review Decision Log.

End-to-end flows using only the public API. The engine builds reports from
caller-provided in-memory records; the writer serializes them to JSON, CSV, and
Markdown and writes atomically to ``tmp_path`` only. No network, no exchange,
no database, no source patching, no filesystem scanning.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from hunter.human_review_decision_log import (
    FORBIDDEN_HUMAN_REVIEW_DECISION_TERMS,
    HumanReviewDecisionIssueType,
    HumanReviewDecisionLink,
    HumanReviewDecisionLogConfig,
    HumanReviewDecisionLogInput,
    HumanReviewDecisionLogReport,
    HumanReviewDecisionLogState,
    HumanReviewDecisionOutcome,
    HumanReviewDecisionRecord,
    HumanReviewDecisionState,
    HumanReviewDecisionValidity,
    HumanReviewDecisionReasonCode,
    HumanReviewDecisionSeverity,
    HumanReviewQueueEntryRef,
    build_human_review_decision_log_report,
    human_review_decision_log_report_to_csv_text,
    human_review_decision_log_report_to_dict,
    human_review_decision_log_report_to_json_text,
    human_review_decision_log_report_to_markdown_text,
    write_human_review_decision_log_report,
)

NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
OLD = NOW - timedelta(days=60)
RECENT = NOW - timedelta(hours=1)


# ---------------------------------------------------------------------------
# Helpers (pure constructors on the public API)
# ---------------------------------------------------------------------------


def _ref(
    queue_entry_id: str = "q1",
    *,
    entry_state: str = "open",
    priority: str = "medium",
    severity: str = "advisory",
    reason_codes: tuple[str, ...] = (),
    generated_at: datetime | None = NOW,
    artifact_ref: str = "opaque-artifact-ref-1",
    report_ref: str = "opaque-report-ref-1",
    metadata: dict[str, str] | None = None,
) -> HumanReviewQueueEntryRef:
    return HumanReviewQueueEntryRef(
        queue_entry_id=queue_entry_id,
        source_id="src",
        source_kind="backlog_item",
        record_id="rec-1",
        entry_state=entry_state,
        priority=priority,
        severity=severity,
        reason_codes=reason_codes,
        generated_at=generated_at,
        artifact_ref=artifact_ref,
        report_ref=report_ref,
        metadata=metadata or {},
    )


def _decision(
    decision_id: str = "d1",
    *,
    queue_entry_id: str = "q1",
    reviewer: str = "reviewer-a",
    decided_at: datetime | None = NOW,
    outcome: str = HumanReviewDecisionOutcome.ACCEPTED_FOR_AUDIT_LOG.value,
    rationale: str = "Looks acceptable for the audit log.",
    reason_codes: tuple[str, ...] = (),
    generated_at: datetime | None = NOW,
    metadata: dict[str, str] | None = None,
) -> HumanReviewDecisionRecord:
    return HumanReviewDecisionRecord(
        decision_id=decision_id,
        queue_entry_id=queue_entry_id,
        reviewer=reviewer,
        decided_at=decided_at,
        outcome=outcome,
        rationale=rationale,
        reason_codes=reason_codes,
        generated_at=generated_at,
        metadata=metadata or {},
    )


def _link(
    link_id: str = "l1",
    *,
    source_id: str = "d1",
    target_id: str = "q1",
    link_type: str = "references",
) -> HumanReviewDecisionLink:
    return HumanReviewDecisionLink(
        link_id=link_id,
        source_id=source_id,
        target_id=target_id,
        link_type=link_type,
    )


def _happy_input() -> HumanReviewDecisionLogInput:
    return HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(_decision("d1", queue_entry_id="q1"),),
        links=(_link("l1", source_id="d1", target_id="q1"),),
        generated_at=NOW,
    )


def _build(
    inp: HumanReviewDecisionLogInput,
    *,
    config: HumanReviewDecisionLogConfig | None = None,
) -> HumanReviewDecisionLogReport:
    return build_human_review_decision_log_report(inp, config)


# ===========================================================================
# 1. End-to-end successful human review decision log
# ===========================================================================


def test_end_to_end_successful_decision_log_structure() -> None:
    """Caller provides in-memory refs/decisions/links; report is deterministic."""
    report = _build(_happy_input())
    assert isinstance(report, HumanReviewDecisionLogReport)
    assert report.report_id  # non-empty deterministic hash
    assert report.generated_at == NOW
    assert report.state == HumanReviewDecisionLogState.OK
    assert len(report.queue_entry_refs) == 1
    assert len(report.decision_records) == 1
    assert len(report.links) == 1
    assert len(report.decision_results) == 1
    # decision result reflects a logged decision.
    result = report.decision_results[0]
    assert result.decision_state == HumanReviewDecisionState.LOGGED.value
    assert result.decision_outcome == HumanReviewDecisionOutcome.ACCEPTED_FOR_AUDIT_LOG.value
    assert result.decision_validity == HumanReviewDecisionValidity.VALID_FOR_AUDIT_LOG.value
    # data quality populated.
    dq = report.data_quality
    assert dq.total_queue_entry_refs == 1
    assert dq.total_decision_records == 1
    assert dq.total_links == 1
    assert dq.total_decision_results == 1
    assert dq.logged_count == 1
    assert dq.total_issues == 0
    # safety flags safe.
    assert report.safety_flags.is_safe is True
    assert report.safety_flags.has_unsafe_content is False
    assert report.safety_flags.has_forbidden_terms is False


def test_end_to_end_issues_and_data_quality_reflect_findings() -> None:
    """A queue entry with a missing decision produces an issue + MISSING result."""
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1", entry_state="open"),),
        decision_records=(),
        generated_at=NOW,
    )
    report = _build(inp)
    assert report.state == HumanReviewDecisionLogState.DEGRADED
    assert report.data_quality.missing_decision_count == 1
    assert report.data_quality.missing_count == 1
    assert any(
        i.issue_type == HumanReviewDecisionIssueType.MISSING_DECISION.value
        for i in report.issues
    )
    assert report.decision_results[0].decision_state == HumanReviewDecisionState.MISSING.value


# ===========================================================================
# 2. Writer end-to-end
# ===========================================================================


def test_writer_writes_json_csv_markdown_to_tmp(tmp_path: Path) -> None:
    report = _build(_happy_input())
    j, c, m = write_human_review_decision_log_report(
        report,
        json_path=tmp_path / "report.json",
        csv_path=tmp_path / "decisions.csv",
        markdown_path=tmp_path / "report.md",
    )
    assert j is not None and c is not None and m is not None
    assert j.exists() and c.exists() and m.exists()


def test_writer_json_parses_and_contains_required_keys(tmp_path: Path) -> None:
    report = _build(_happy_input())
    target = tmp_path / "report.json"
    write_human_review_decision_log_report(report, json_path=target, csv_path=None, markdown_path=None)
    data = json.loads(target.read_text(encoding="utf-8"))
    for key in (
        "queue_entry_refs",
        "decision_records",
        "links",
        "issues",
        "decision_results",
        "data_quality",
        "safety_flags",
        "safety_notice",
        "generated_at",
        "report_id",
        "state",
    ):
        assert key in data, f"missing key {key!r} in JSON"


def test_writer_csv_rows_come_from_decision_results(tmp_path: Path) -> None:
    report = _build(_happy_input())
    target = tmp_path / "decisions.csv"
    write_human_review_decision_log_report(report, json_path=None, csv_path=target, markdown_path=None)
    reader = csv.DictReader(target.read_text(encoding="utf-8").splitlines())
    rows = list(reader)
    assert len(rows) == 1
    row = rows[0]
    assert row["queue_entry_id"] == "q1"
    assert row["decision_id"] == "d1"
    assert row["decision_state"] == HumanReviewDecisionState.LOGGED.value
    assert row["decision_outcome"] == HumanReviewDecisionOutcome.ACCEPTED_FOR_AUDIT_LOG.value
    assert row["decision_validity"] == HumanReviewDecisionValidity.VALID_FOR_AUDIT_LOG.value
    assert row["report_id"] == report.report_id


def test_writer_csv_semicolon_joined_decision_ids_for_multiple(tmp_path: Path) -> None:
    """Two distinct decisions on one queue entry yield a semicolon-joined cell."""
    d1 = _decision("d1", queue_entry_id="q1", rationale="first")
    d2 = _decision("d2", queue_entry_id="q1", rationale="second")
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(d1, d2),
        generated_at=NOW,
    )
    report = _build(inp)
    target = tmp_path / "decisions.csv"
    write_human_review_decision_log_report(report, json_path=None, csv_path=target, markdown_path=None)
    reader = csv.DictReader(target.read_text(encoding="utf-8").splitlines())
    rows = list(reader)
    assert len(rows) == 1
    assert set(rows[0]["decision_id"].split(";")) == {"d1", "d2"}


def test_writer_markdown_starts_with_h1_and_safety_notice() -> None:
    report = _build(_happy_input())
    md = human_review_decision_log_report_to_markdown_text(report)
    assert md.startswith("# ")
    # immediate research-only / audit-only / human-audit safety notice near top.
    head = md.splitlines()[:6]
    joined = " ".join(head).lower()
    assert "research" in joined
    assert "audit-only" in joined
    assert "human-audit" in joined


def test_writer_dict_and_json_text_roundtrip() -> None:
    report = _build(_happy_input())
    d = human_review_decision_log_report_to_dict(report)
    j = human_review_decision_log_report_to_json_text(report)
    assert json.loads(j) == d
    assert d["report_id"] == report.report_id


# ===========================================================================
# 3. Empty / non-empty behavior
# ===========================================================================


def test_empty_input_returns_not_applicable_by_default() -> None:
    inp = HumanReviewDecisionLogInput(generated_at=NOW)
    report = _build(inp)
    assert report.state == HumanReviewDecisionLogState.NOT_APPLICABLE
    assert report.decision_results == ()
    assert report.data_quality.total_decision_results == 0


def test_empty_input_returns_ok_when_not_applicable_disabled() -> None:
    config = HumanReviewDecisionLogConfig(empty_input_is_not_applicable=False)
    inp = HumanReviewDecisionLogInput(config=config, generated_at=NOW)
    report = _build(inp, config=config)
    assert report.state == HumanReviewDecisionLogState.OK
    assert len(report.decision_results) == 0


def test_non_empty_clean_input_returns_ok() -> None:
    report = _build(_happy_input())
    assert report.state == HumanReviewDecisionLogState.OK


def test_not_applicable_info_does_not_block() -> None:
    """A not_applicable queue entry classifies safely and does not block."""
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1", entry_state="not_applicable"),),
        decision_records=(_decision("d1", queue_entry_id="q1"),),
        generated_at=NOW,
    )
    report = _build(inp)
    assert report.state == HumanReviewDecisionLogState.OK
    assert report.decision_results[0].decision_state == HumanReviewDecisionState.NOT_APPLICABLE.value


# ===========================================================================
# 4. Decision states and precedence (first-match-wins)
# ===========================================================================


def test_decision_state_not_applicable() -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1", entry_state="suppressed"),),
        decision_records=(_decision("d1", queue_entry_id="q1"),),
        generated_at=NOW,
    )
    report = _build(inp)
    assert report.decision_results[0].decision_state == HumanReviewDecisionState.NOT_APPLICABLE.value


def test_decision_state_blocked_from_unsafe_content() -> None:
    """Unsafe content (non-string metadata value) fail-closes to BLOCKED report."""
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(_decision("d1", queue_entry_id="q1"),),
        metadata={"evil": 12345},  # int value is unsafe per has_unsafe_*
        generated_at=NOW,
    )
    report = _build(inp)
    assert report.state == HumanReviewDecisionLogState.BLOCKED


def test_decision_state_disputed_from_conflict() -> None:
    """Two different outcomes for one queue entry produce a DISPUTED result."""
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(
            _decision("d1", queue_entry_id="q1", outcome=HumanReviewDecisionOutcome.ACCEPTED_FOR_AUDIT_LOG.value, rationale="a"),
            _decision("d2", queue_entry_id="q1", outcome=HumanReviewDecisionOutcome.REJECTED_FOR_AUDIT_LOG.value, rationale="b"),
        ),
        generated_at=NOW,
    )
    report = _build(inp)
    assert report.decision_results[0].decision_state == HumanReviewDecisionState.DISPUTED.value


def test_decision_state_duplicate_from_semantic_dup() -> None:
    """Two semantically identical decisions produce DUPLICATE result."""
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(
            _decision("d1", queue_entry_id="q1", rationale="same"),
            _decision("d2", queue_entry_id="q1", rationale="same"),
        ),
        generated_at=NOW,
    )
    report = _build(inp)
    assert report.decision_results[0].decision_state == HumanReviewDecisionState.DUPLICATE.value


def test_decision_state_rejected() -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(
            _decision("d1", queue_entry_id="q1", outcome=HumanReviewDecisionOutcome.REJECTED_FOR_AUDIT_LOG.value),
        ),
        generated_at=NOW,
    )
    report = _build(inp)
    assert report.decision_results[0].decision_state == HumanReviewDecisionState.REJECTED.value


def test_decision_state_stale() -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1", generated_at=OLD),),
        decision_records=(_decision("d1", queue_entry_id="q1", generated_at=OLD),),
        generated_at=NOW,
    )
    report = _build(inp)
    assert report.decision_results[0].decision_state == HumanReviewDecisionState.STALE.value


def test_decision_state_missing() -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1", entry_state="open"),),
        decision_records=(),
        generated_at=NOW,
    )
    report = _build(inp)
    assert report.decision_results[0].decision_state == HumanReviewDecisionState.MISSING.value


def test_decision_state_incomplete() -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(_decision("d1", queue_entry_id="q1", reviewer=""),),
        generated_at=NOW,
    )
    report = _build(inp)
    assert report.decision_results[0].decision_state == HumanReviewDecisionState.INCOMPLETE.value


def test_decision_state_pending_review() -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(
            _decision("d1", queue_entry_id="q1", outcome=HumanReviewDecisionOutcome.NEEDS_MORE_REVIEW.value),
        ),
        generated_at=NOW,
    )
    report = _build(inp)
    assert report.decision_results[0].decision_state == HumanReviewDecisionState.PENDING_REVIEW.value


def test_decision_state_superseded() -> None:
    """Two decisions with different decided_at times yield SUPERSEDED."""
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(
            _decision("d1", queue_entry_id="q1", decided_at=NOW, rationale="initial rationale"),
            _decision("d2", queue_entry_id="q1", decided_at=RECENT, rationale="revised rationale"),
        ),
        generated_at=NOW,
    )
    report = _build(inp)
    assert report.decision_results[0].decision_state == HumanReviewDecisionState.SUPERSEDED.value


def test_decision_state_logged() -> None:
    report = _build(_happy_input())
    assert report.decision_results[0].decision_state == HumanReviewDecisionState.LOGGED.value


def test_precedence_not_applicable_outranks_missing() -> None:
    """A suppressed entry with no decision is NOT_APPLICABLE, not MISSING."""
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1", entry_state="suppressed"),),
        decision_records=(),
        generated_at=NOW,
    )
    report = _build(inp)
    assert report.decision_results[0].decision_state == HumanReviewDecisionState.NOT_APPLICABLE.value


def test_precedence_blocked_outranks_disputed() -> None:
    """Unsafe content fail-closes the whole report to BLOCKED before any result."""
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(
            _decision("d1", queue_entry_id="q1", outcome=HumanReviewDecisionOutcome.ACCEPTED_FOR_AUDIT_LOG.value, rationale="a"),
            _decision("d2", queue_entry_id="q1", outcome=HumanReviewDecisionOutcome.REJECTED_FOR_AUDIT_LOG.value, rationale="b"),
        ),
        metadata={"x": object()},  # unsafe
        generated_at=NOW,
    )
    report = _build(inp)
    assert report.state == HumanReviewDecisionLogState.BLOCKED


# ===========================================================================
# 5. Built-in detections
# ===========================================================================


def test_duplicate_queue_entry_ids_fail_closed() -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"), _ref("q1")),
        decision_records=(_decision("d1", queue_entry_id="q1"),),
        generated_at=NOW,
    )
    report = _build(inp)
    assert report.state == HumanReviewDecisionLogState.BLOCKED


def test_duplicate_decision_ids_fail_closed() -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(
            _decision("d1", queue_entry_id="q1"),
            _decision("d1", queue_entry_id="q1"),
        ),
        generated_at=NOW,
    )
    report = _build(inp)
    assert report.state == HumanReviewDecisionLogState.BLOCKED


def test_duplicate_link_ids_fail_closed() -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(_decision("d1", queue_entry_id="q1"),),
        links=(
            _link("l1", source_id="d1", target_id="q1"),
            _link("l1", source_id="d1", target_id="q1"),
        ),
        generated_at=NOW,
    )
    report = _build(inp)
    assert report.state == HumanReviewDecisionLogState.BLOCKED


def test_orphan_decision_record_detected() -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(_decision("d1", queue_entry_id="q-missing"),),
        generated_at=NOW,
    )
    report = _build(inp)
    assert report.data_quality.orphan_decision_count == 1
    assert any(i.issue_type == HumanReviewDecisionIssueType.ORPHAN_DECISION.value for i in report.issues)
    # Orphan decisions now produce an ORPHANED decision result row.
    orphan_results = [
        r for r in report.decision_results
        if r.decision_state == HumanReviewDecisionState.ORPHANED.value
    ]
    assert len(orphan_results) == 1
    orphan = orphan_results[0]
    assert orphan.queue_entry_id == "q-missing"
    assert orphan.decision_ids == ("d1",)
    assert orphan.decision_validity == HumanReviewDecisionValidity.INVALID_FOR_AUDIT_LOG.value
    assert orphan.severity == HumanReviewDecisionSeverity.ADVISORY.value
    assert HumanReviewDecisionReasonCode.ORPHAN_DECISION.value in orphan.reason_codes
    assert report.data_quality.orphaned_count == 1


def test_orphan_decision_result_is_audit_only_and_non_executable() -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(_decision("d1", queue_entry_id="q-missing"),),
        generated_at=NOW,
    )
    report = _build(inp)
    orphan = [r for r in report.decision_results if r.decision_state == HumanReviewDecisionState.ORPHANED.value][0]
    assert orphan.rationale
    assert "audit" in orphan.rationale.lower() or "unknown" in orphan.rationale.lower()
    assert "deploy" not in orphan.rationale.lower()
    assert "execute" not in orphan.rationale.lower()
    assert "order" not in orphan.rationale.lower()


def test_orphan_link_detected() -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(_decision("d1", queue_entry_id="q1"),),
        links=(_link("l1", source_id="d-unknown", target_id="q1"),),
        generated_at=NOW,
    )
    report = _build(inp)
    assert report.data_quality.orphan_link_count == 1
    assert any(i.issue_type == HumanReviewDecisionIssueType.ORPHAN_LINK.value for i in report.issues)


def test_missing_decision_when_required_for_all() -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1", entry_state="open"),),
        decision_records=(),
        generated_at=NOW,
    )
    report = _build(inp)
    assert report.data_quality.missing_decision_count == 1
    assert report.decision_results[0].decision_state == HumanReviewDecisionState.MISSING.value


def test_no_decision_for_not_applicable_entry_no_missing_issue() -> None:
    """A not_applicable queue entry with no decision does NOT emit MISSING_DECISION."""
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1", entry_state="not_applicable"),),
        decision_records=(),
        generated_at=NOW,
    )
    report = _build(inp)
    assert report.data_quality.missing_decision_count == 0


def test_missing_decision_not_required_is_non_blocking() -> None:
    config = HumanReviewDecisionLogConfig(require_decision_for_all=False)
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1", entry_state="open"),),
        decision_records=(),
        config=config,
        generated_at=NOW,
    )
    report = _build(inp, config=config)
    assert report.state == HumanReviewDecisionLogState.OK
    assert report.decision_results[0].decision_state == HumanReviewDecisionState.NOT_APPLICABLE.value


def test_conflicting_outcomes_across_reviewers() -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(
            _decision("d1", queue_entry_id="q1", reviewer="r1", outcome=HumanReviewDecisionOutcome.ACCEPTED_FOR_AUDIT_LOG.value, rationale="a"),
            _decision("d2", queue_entry_id="q1", reviewer="r2", outcome=HumanReviewDecisionOutcome.REJECTED_FOR_AUDIT_LOG.value, rationale="b"),
        ),
        generated_at=NOW,
    )
    report = _build(inp)
    assert report.data_quality.conflicting_decision_count == 1


def test_conflicting_outcome_from_same_reviewer() -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(
            _decision("d1", queue_entry_id="q1", reviewer="r1", outcome=HumanReviewDecisionOutcome.ACCEPTED_FOR_AUDIT_LOG.value, rationale="a"),
            _decision("d2", queue_entry_id="q1", reviewer="r1", outcome=HumanReviewDecisionOutcome.REJECTED_FOR_AUDIT_LOG.value, rationale="b"),
        ),
        generated_at=NOW,
    )
    report = _build(inp)
    assert report.data_quality.conflicting_outcome_count == 1


def test_stale_queue_entry_and_decision_detected() -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1", generated_at=OLD),),
        decision_records=(_decision("d1", queue_entry_id="q1", generated_at=OLD),),
        generated_at=NOW,
    )
    report = _build(inp)
    assert report.data_quality.stale_queue_entry_count == 1
    assert report.data_quality.stale_decision_count == 1


@pytest.mark.parametrize(
    "field,kwargs",
    [
        ("missing_reviewer_count", {"reviewer": ""}),
        ("missing_decided_at_count", {"decided_at": None}),
        ("missing_rationale_count", {"rationale": ""}),
        ("missing_outcome_count", {"outcome": "unknown"}),
    ],
)
def test_missing_required_metadata_fields(field: str, kwargs: dict[str, Any]) -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(_decision("d1", queue_entry_id="q1", **kwargs),),
        generated_at=NOW,
    )
    report = _build(inp)
    assert getattr(report.data_quality, field) == 1


def test_outcome_mismatch_with_blocking_severity() -> None:
    """ACCEPTED_FOR_AUDIT_LOG on a blocking-severity entry yields OUTCOME_MISMATCH."""
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1", severity="blocking"),),
        decision_records=(_decision("d1", queue_entry_id="q1", outcome=HumanReviewDecisionOutcome.ACCEPTED_FOR_AUDIT_LOG.value),),
        generated_at=NOW,
    )
    report = _build(inp)
    assert report.data_quality.outcome_mismatch_count == 1


# ===========================================================================
# 6. Queue entry interactions
# ===========================================================================


def test_decision_on_blocked_high_priority_entry_logged_for_audit_only() -> None:
    """A decision on a blocked entry is logged; the report is not an approval."""
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1", entry_state="blocked", priority="high"),),
        decision_records=(_decision("d1", queue_entry_id="q1"),),
        generated_at=NOW,
    )
    report = _build(inp)
    # Outcome mismatch is flagged (advisory), but a result is still produced.
    assert len(report.decision_results) == 1
    # safety boundary: explicitly not an approval.
    assert report.safety_flags.decision_logged_not_approval is True


def test_decision_on_suppressed_entry_classified_safely() -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1", entry_state="suppressed"),),
        decision_records=(_decision("d1", queue_entry_id="q1"),),
        generated_at=NOW,
    )
    report = _build(inp)
    assert report.decision_results[0].decision_state == HumanReviewDecisionState.NOT_APPLICABLE.value
    assert report.safety_flags.is_safe is True


def test_reviewer_attribution_is_opaque_metadata_only() -> None:
    """Reviewer strings pass through unchanged as opaque metadata."""
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(_decision("d1", queue_entry_id="q1", reviewer="opaque-reviewer-xyz"),),
        generated_at=NOW,
    )
    report = _build(inp)
    assert report.decision_records[0].reviewer == "opaque-reviewer-xyz"
    assert report.decision_results[0].reviewer == "opaque-reviewer-xyz"


# ===========================================================================
# 7. Aggregation
# ===========================================================================


def test_aggregation_non_strict_advisory_is_degraded() -> None:
    """An advisory-only issue (missing decision) yields DEGRADED in non-strict mode."""
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1", entry_state="open"),),
        decision_records=(),
        generated_at=NOW,
    )
    report = _build(inp)
    assert report.state == HumanReviewDecisionLogState.DEGRADED


def test_aggregation_strict_promotes_degraded_to_blocked() -> None:
    config = HumanReviewDecisionLogConfig(strict=True)
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1", entry_state="open"),),
        decision_records=(),
        config=config,
        generated_at=NOW,
    )
    report = _build(inp, config=config)
    assert report.state == HumanReviewDecisionLogState.BLOCKED


def test_aggregation_blocking_always_blocked() -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"), _ref("q1")),  # duplicate -> blocked
        decision_records=(),
        generated_at=NOW,
    )
    report = _build(inp)
    assert report.state == HumanReviewDecisionLogState.BLOCKED


# ===========================================================================
# 8. Unsafe content / forbidden terms
# ===========================================================================


def test_unsafe_metadata_blocks_report() -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(_decision("d1", queue_entry_id="q1"),),
        metadata={"bad": [1, 2, 3]},  # list of ints is unsafe
        generated_at=NOW,
    )
    report = _build(inp)
    assert report.state == HumanReviewDecisionLogState.BLOCKED
    assert report.safety_flags.has_unsafe_content is True


@pytest.mark.parametrize("term", sorted(FORBIDDEN_HUMAN_REVIEW_DECISION_TERMS)[:8])
def test_forbidden_multi_word_phrases_block(term: str) -> None:
    """A representative sample of forbidden multi-word phrases fail-closes."""
    assert " " in term  # all forbidden terms are multi-word phrases
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(_decision("d1", queue_entry_id="q1", rationale=term),),
        generated_at=NOW,
    )
    report = _build(inp)
    assert report.state == HumanReviewDecisionLogState.BLOCKED


@pytest.mark.parametrize(
    "benign",
    [
        "pending approval from security team",
        "certification body",
        "no recommendation needed",
        "signal processing",
        "no signal detected",
        "task queue",
        "task note",
    ],
)
def test_benign_phrases_do_not_block(benign: str) -> None:
    """False-positive-safe phrases must not trigger forbidden-term blocking."""
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(_decision("d1", queue_entry_id="q1", rationale=benign),),
        generated_at=NOW,
    )
    report = _build(inp)
    assert report.state != HumanReviewDecisionLogState.BLOCKED


# ===========================================================================
# 9. Determinism
# ===========================================================================


def test_deterministic_dict_json_csv_markdown_identical() -> None:
    inp = _happy_input()
    r1 = _build(inp)
    r2 = _build(inp)
    assert human_review_decision_log_report_to_dict(r1) == human_review_decision_log_report_to_dict(r2)
    assert human_review_decision_log_report_to_json_text(r1) == human_review_decision_log_report_to_json_text(r2)
    assert human_review_decision_log_report_to_csv_text(r1) == human_review_decision_log_report_to_csv_text(r2)
    assert human_review_decision_log_report_to_markdown_text(r1) == human_review_decision_log_report_to_markdown_text(r2)


def test_deterministic_issue_id_and_result_id_stable() -> None:
    inp = _happy_input()
    r1 = _build(inp)
    r2 = _build(inp)
    assert [i.issue_id for i in r1.issues] == [i.issue_id for i in r2.issues]
    assert (
        r1.decision_results[0].decision_result_id
        == r2.decision_results[0].decision_result_id
    )


def test_deterministic_report_id_stable() -> None:
    inp = _happy_input()
    assert _build(inp).report_id == _build(inp).report_id


def test_blocked_report_id_is_non_empty_deterministic_and_prefixed() -> None:
    inp = HumanReviewDecisionLogInput(
        decision_records=(
            _decision("d1", queue_entry_id="q1", rationale="decision approved for deployment"),
        ),
        generated_at=NOW,
    )
    r1 = _build(inp)
    r2 = _build(inp)
    assert r1.state == HumanReviewDecisionLogState.BLOCKED
    assert r1.report_id
    assert r1.report_id.startswith("blocked-human-review-decision-log-")
    assert r1.report_id == r2.report_id
    assert len(r1.report_id) < 70


def test_blocked_report_id_varies_with_input() -> None:
    a = HumanReviewDecisionLogInput(
        decision_records=(_decision("d1", queue_entry_id="q1", rationale="decision approved"),),
        generated_at=NOW,
    )
    b = HumanReviewDecisionLogInput(
        decision_records=(_decision("d2", queue_entry_id="q2", rationale="decision approved"),),
        generated_at=NOW,
    )
    assert _build(a).report_id != _build(b).report_id
# ===========================================================================
# 10. No mutation of inputs
# ===========================================================================


def test_engine_does_not_mutate_input_collections() -> None:
    refs = [_ref("q1"), _ref("q2")]
    decisions = [_decision("d1", queue_entry_id="q1"), _decision("d2", queue_entry_id="q2")]
    links = [_link("l1", source_id="d1", target_id="q1")]
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=tuple(refs),
        decision_records=tuple(decisions),
        links=tuple(links),
        generated_at=NOW,
    )
    _build(inp)
    # The input collections remain unchanged (same identity / length / content).
    assert len(inp.queue_entry_refs) == 2
    assert len(inp.decision_records) == 2
    assert len(inp.links) == 1
    assert inp.queue_entry_refs[0].queue_entry_id == "q1"
    assert inp.decision_records[0].decision_id == "d1"


# ===========================================================================
# 11. Public exports
# ===========================================================================


def test_package_exports_build_and_writer_functions() -> None:
    import hunter.human_review_decision_log as pkg

    assert hasattr(pkg, "build_human_review_decision_log_report")
    assert hasattr(pkg, "human_review_decision_log_report_to_dict")
    assert hasattr(pkg, "human_review_decision_log_report_to_json_text")
    assert hasattr(pkg, "human_review_decision_log_report_to_csv_text")
    assert hasattr(pkg, "human_review_decision_log_report_to_markdown_text")
    assert hasattr(pkg, "write_human_review_decision_log_report")


# ===========================================================================
# 12. Safety boundaries
# ===========================================================================


def test_outputs_contain_research_only_audit_only_language() -> None:
    report = _build(_happy_input())
    md = human_review_decision_log_report_to_markdown_text(report)
    low = md.lower()
    assert "research" in low
    assert "audit-only" in low or "audit only" in low
    assert "human-audit" in low or "human audit" in low


def test_outputs_disclaim_approval_certification_readiness_recommendation() -> None:
    report = _build(_happy_input())
    notice = report.safety_notice.lower()
    for phrase in (
        "approval",
        "certification",
        "production readiness",
        "deployment readiness",
        "trading readiness",
        "recommendation",
        "suitability assessment",
        "task assignment",
        "task completion",
        "executable remediation plan",
    ):
        assert phrase in notice, f"safety notice missing {phrase!r}"


def test_output_contains_no_shell_commands_or_deployment_actions() -> None:
    """Serialized outputs must not contain executable shell/deployment/trading
    instruction patterns. Safety disclaimers legitimately mention terms like
    'task assignment' to disclaim them, so those are excluded."""
    report = _build(_happy_input())
    # These are action-command patterns that should never appear anywhere.
    forbidden_patterns = (
        "sudo ",
        "npm install",
        "docker build",
        "kubectl apply",
        "git push",
        "pip install",
        "rm -rf",
        "chmod +x",
        "curl ",
        "wget ",
        "market order",
        "limit order",
        "buy now",
        "sell now",
    )
    for text in (
        human_review_decision_log_report_to_markdown_text(report),
        human_review_decision_log_report_to_json_text(report),
        human_review_decision_log_report_to_csv_text(report),
    ):
        low = text.lower()
        for pat in forbidden_patterns:
            assert pat not in low, f"output should not contain {pat!r}"


def test_output_has_no_binance_exchange_freqtrade_api_semantics() -> None:
    report = _build(_happy_input())
    md = human_review_decision_log_report_to_markdown_text(report)
    low = md.lower()
    for term in ("binance", "freqtrade", "api key", "place order", "leverage"):
        assert term not in low, f"output should not mention {term!r}"


# ===========================================================================
# 13. Opaque references
# ===========================================================================


def test_artifact_and_report_refs_remain_opaque_strings() -> None:
    """Refs pass through as opaque strings and are never resolved/opened."""
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1", artifact_ref="opaque://artifact/abc", report_ref="opaque://report/xyz"),),
        decision_records=(_decision("d1", queue_entry_id="q1"),),
        generated_at=NOW,
    )
    report = _build(inp)
    assert report.queue_entry_refs[0].artifact_ref == "opaque://artifact/abc"
    assert report.queue_entry_refs[0].report_ref == "opaque://report/xyz"
    # No filesystem scan/import/path traversal/open/fetch/execute required:
    # the refs are just strings carried through to the output.
    d = human_review_decision_log_report_to_dict(report)
    refs = d["queue_entry_refs"]
    assert refs[0]["artifact_ref"] == "opaque://artifact/abc"


def test_opaque_refs_require_no_filesystem_resolution(tmp_path: Path) -> None:
    """Writing the report does not require resolving any opaque ref to a path."""
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1", artifact_ref="does-not-exist://nope"),),
        decision_records=(_decision("d1", queue_entry_id="q1"),),
        generated_at=NOW,
    )
    report = _build(inp)
    target = tmp_path / "out.json"
    # This succeeds without touching the filesystem for the opaque ref.
    write_human_review_decision_log_report(report, json_path=target, csv_path=None, markdown_path=None)
    assert target.exists()