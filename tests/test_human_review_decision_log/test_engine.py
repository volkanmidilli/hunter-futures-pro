"""Tests for hunter.human_review_decision_log.engine."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from hunter.human_review_decision_log import (
    HumanReviewDecisionLink,
    HumanReviewDecisionLogConfig,
    HumanReviewDecisionLogInput,
    HumanReviewDecisionLogState,
    HumanReviewDecisionOutcome,
    HumanReviewDecisionReasonCode,
    HumanReviewDecisionRecord,
    HumanReviewDecisionState,
    HumanReviewQueueEntryRef,
    build_human_review_decision_log_report,
)

NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
OLD = NOW - timedelta(days=60)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ref(
    queue_entry_id: str = "q1",
    entry_state: str = "",
    priority: str = "",
    severity: str = "",
    generated_at: datetime | None = NOW,
) -> HumanReviewQueueEntryRef:
    return HumanReviewQueueEntryRef(
        queue_entry_id=queue_entry_id,
        entry_state=entry_state,
        priority=priority,
        severity=severity,
        generated_at=generated_at,
    )

def _decision(
    decision_id: str = "d1",
    queue_entry_id: str = "q1",
    reviewer: str = "reviewer_a",
    decided_at: datetime | None = NOW,
    outcome: str = HumanReviewDecisionOutcome.ACCEPTED_FOR_AUDIT_LOG.value,
    rationale: str = "looks ok",
    generated_at: datetime | None = NOW,
) -> HumanReviewDecisionRecord:
    return HumanReviewDecisionRecord(
        decision_id=decision_id,
        queue_entry_id=queue_entry_id,
        reviewer=reviewer,
        decided_at=decided_at,
        outcome=outcome,
        rationale=rationale,
        generated_at=generated_at,
    )


# ---------------------------------------------------------------------------
# Empty input
# ---------------------------------------------------------------------------

def test_empty_input_not_applicable() -> None:
    inp = HumanReviewDecisionLogInput(generated_at=NOW)
    report = build_human_review_decision_log_report(inp)
    assert report.state == HumanReviewDecisionLogState.NOT_APPLICABLE
    assert report.decision_results == ()
    assert HumanReviewDecisionReasonCode.NOT_APPLICABLE in report.reason_codes

def test_empty_input_when_not_applicable_disabled() -> None:
    config = HumanReviewDecisionLogConfig(empty_input_is_not_applicable=False)
    inp = HumanReviewDecisionLogInput(config=config, generated_at=NOW)
    report = build_human_review_decision_log_report(inp)
    assert report.state == HumanReviewDecisionLogState.OK
    assert len(report.decision_results) == 0

# ---------------------------------------------------------------------------
# Happy path: logged decision
# ---------------------------------------------------------------------------

def test_decision_logged_happy_path() -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref(),),
        decision_records=(_decision(),),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    assert report.state == HumanReviewDecisionLogState.OK
    assert len(report.decision_results) == 1
    assert report.decision_results[0].decision_state == HumanReviewDecisionState.LOGGED.value
    assert report.decision_results[0].decision_outcome == HumanReviewDecisionOutcome.ACCEPTED_FOR_AUDIT_LOG.value
    assert report.decision_results[0].decision_validity == "valid_for_audit_log"

# ---------------------------------------------------------------------------
# Deterministic IDs and order
# ---------------------------------------------------------------------------

def test_deterministic_report_id() -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref(),),
        decision_records=(_decision(),),
        generated_at=NOW,
    )
    r1 = build_human_review_decision_log_report(inp)
    r2 = build_human_review_decision_log_report(inp)
    assert r1.report_id == r2.report_id
    assert len(r1.report_id) == 64

def test_deterministic_decision_result_id() -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref(),),
        decision_records=(_decision(),),
        generated_at=NOW,
    )
    r1 = build_human_review_decision_log_report(inp)
    r2 = build_human_review_decision_log_report(inp)
    assert r1.decision_results[0].decision_result_id == r2.decision_results[0].decision_result_id

def test_deterministic_issue_id() -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref(),),
        decision_records=(_decision(queue_entry_id="q_unknown"),),
        generated_at=NOW,
    )
    r1 = build_human_review_decision_log_report(inp)
    r2 = build_human_review_decision_log_report(inp)
    ids1 = [i.issue_id for i in r1.issues]
    ids2 = [i.issue_id for i in r2.issues]
    assert ids1 == ids2

def test_sorted_queue_entry_refs_in_report() -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q3"), _ref("q1"), _ref("q2")),
        decision_records=(),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    ref_ids = [r.queue_entry_id for r in report.queue_entry_refs]
    assert ref_ids == ["q1", "q2", "q3"]

def test_sorted_decision_records_in_report() -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref(),),
        decision_records=(_decision("d3"), _decision("d1"), _decision("d2")),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    rec_ids = [r.decision_id for r in report.decision_records]
    assert rec_ids == ["d1", "d2", "d3"]

# ---------------------------------------------------------------------------
# Duplicate ID detection (fail-closed)
# ---------------------------------------------------------------------------

def test_duplicate_queue_entry_ids_fail_closed() -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"), _ref("q1")),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    assert report.state == HumanReviewDecisionLogState.BLOCKED
    assert HumanReviewDecisionReasonCode.DUPLICATE_QUEUE_ENTRY_ID in report.reason_codes

def test_duplicate_decision_ids_fail_closed() -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref(),),
        decision_records=(_decision("d1"), _decision("d1")),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    assert report.state == HumanReviewDecisionLogState.BLOCKED
    assert HumanReviewDecisionReasonCode.DUPLICATE_DECISION_ID in report.reason_codes

def test_duplicate_link_ids_fail_closed() -> None:
    link = HumanReviewDecisionLink(link_id="l1", source_id="s", target_id="t")
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref(),),
        links=(link, link),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    assert report.state == HumanReviewDecisionLogState.BLOCKED
    assert HumanReviewDecisionReasonCode.DUPLICATE_LINK_ID in report.reason_codes

# ---------------------------------------------------------------------------
# Semantic duplicate detection
# ---------------------------------------------------------------------------

def test_semantic_duplicate_detection() -> None:
    d1 = _decision("d1", reviewer="r1", outcome="accepted_for_audit_log", rationale="ok")
    d2 = _decision("d2", reviewer="r1", outcome="accepted_for_audit_log", rationale="ok")
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(d1, d2),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    issue_types = [i.issue_type for i in report.issues]
    assert "semantic_duplicate_decision" in issue_types

# ---------------------------------------------------------------------------
# Orphan detection
# ---------------------------------------------------------------------------

def test_orphan_decision_detection() -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(_decision("d1", queue_entry_id="q_orphan"),),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    issue_types = [i.issue_type for i in report.issues]
    assert "orphan_decision" in issue_types

def test_orphan_link_detection() -> None:
    link = HumanReviewDecisionLink(link_id="l1", source_id="unknown_src", target_id="unknown_tgt")
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        links=(link,),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    issue_types = [i.issue_type for i in report.issues]
    assert "orphan_link" in issue_types

# ---------------------------------------------------------------------------
# Missing decision detection
# ---------------------------------------------------------------------------

def test_missing_decision_when_required() -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    issue_types = [i.issue_type for i in report.issues]
    assert "missing_decision" in issue_types
    assert report.decision_results[0].decision_state == "missing"
    assert report.state == HumanReviewDecisionLogState.DEGRADED

def test_missing_decision_not_required_is_not_applicable() -> None:
    config = HumanReviewDecisionLogConfig(require_decision_for_all=False)
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(),
        config=config,
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    assert report.state == HumanReviewDecisionLogState.OK
    assert report.decision_results[0].decision_state == "not_applicable"

# ---------------------------------------------------------------------------
# Missing metadata detection
# ---------------------------------------------------------------------------

def test_missing_reviewer() -> None:
    d = _decision(reviewer="")
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref(),),
        decision_records=(d,),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    issue_types = [i.issue_type for i in report.issues]
    assert "missing_reviewer" in issue_types

def test_missing_decided_at() -> None:
    d = _decision(decided_at=None)
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref(),),
        decision_records=(d,),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    issue_types = [i.issue_type for i in report.issues]
    assert "missing_decided_at" in issue_types

def test_missing_rationale() -> None:
    d = _decision(rationale="")
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref(),),
        decision_records=(d,),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    issue_types = [i.issue_type for i in report.issues]
    assert "missing_rationale" in issue_types

def test_missing_outcome_unknown() -> None:
    d = _decision(outcome="unknown")
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref(),),
        decision_records=(d,),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    issue_types = [i.issue_type for i in report.issues]
    assert "missing_outcome" in issue_types

def test_missing_queue_entry_id() -> None:
    d = _decision(queue_entry_id="")
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(d,),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    issue_types = [i.issue_type for i in report.issues]
    assert "missing_queue_entry_id" in issue_types

# ---------------------------------------------------------------------------
# Conflicting decisions
# ---------------------------------------------------------------------------

def test_conflicting_outcomes() -> None:
    d1 = _decision("d1", outcome="accepted_for_audit_log")
    d2 = _decision("d2", outcome="rejected_for_audit_log")
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(d1, d2),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    issue_types = [i.issue_type for i in report.issues]
    assert "conflicting_decision" in issue_types

def test_conflicting_outcome_from_same_reviewer() -> None:
    d1 = _decision("d1", reviewer="r1", outcome="accepted_for_audit_log")
    d2 = _decision("d2", reviewer="r1", outcome="rejected_for_audit_log")
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(d1, d2),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    issue_types = [i.issue_type for i in report.issues]
    assert "conflicting_outcome" in issue_types

# ---------------------------------------------------------------------------
# Stale detection
# ---------------------------------------------------------------------------

def test_stale_queue_entry() -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1", generated_at=OLD),),
        decision_records=(_decision("d1", queue_entry_id="q1"),),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    issue_types = [i.issue_type for i in report.issues]
    assert "stale_queue_entry" in issue_types

def test_stale_decision() -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(_decision("d1", queue_entry_id="q1", generated_at=OLD),),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    issue_types = [i.issue_type for i in report.issues]
    assert "stale_decision" in issue_types

# ---------------------------------------------------------------------------
# Outcome mismatch
# ---------------------------------------------------------------------------

def test_outcome_mismatch_blocking() -> None:
    ref = _ref("q1", entry_state="blocked", severity="blocking")
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(ref,),
        decision_records=(_decision("d1", queue_entry_id="q1", outcome="accepted_for_audit_log"),),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    issue_types = [i.issue_type for i in report.issues]
    assert "outcome_mismatch" in issue_types

# ---------------------------------------------------------------------------
# All decision outcomes
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("outcome", [
    HumanReviewDecisionOutcome.ACCEPTED_FOR_AUDIT_LOG.value,
    HumanReviewDecisionOutcome.REJECTED_FOR_AUDIT_LOG.value,
    HumanReviewDecisionOutcome.NEEDS_MORE_REVIEW.value,
    HumanReviewDecisionOutcome.DISPUTED.value,
    HumanReviewDecisionOutcome.DEFERRED.value,
    HumanReviewDecisionOutcome.NOT_APPLICABLE.value,
    HumanReviewDecisionOutcome.SUPERSEDED.value,
    HumanReviewDecisionOutcome.UNKNOWN.value,
])
def test_all_decision_outcomes(outcome: str) -> None:
    d = _decision(outcome=outcome)
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1", entry_state="ok"),),
        decision_records=(d,),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    assert len(report.decision_results) == 1
    assert report.decision_results[0].decision_outcome == outcome

# ---------------------------------------------------------------------------
# All decision states (via precedence)
# ---------------------------------------------------------------------------

def test_decision_state_not_applicable() -> None:
    ref = _ref("q1", entry_state="not_applicable")
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(ref,),
        decision_records=(),
        config=HumanReviewDecisionLogConfig(require_decision_for_all=True),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    assert report.decision_results[0].decision_state == "not_applicable"

def test_decision_state_missing() -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    assert report.decision_results[0].decision_state == "missing"

def test_decision_state_rejected() -> None:
    d = _decision(outcome="rejected_for_audit_log")
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(d,),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    assert report.decision_results[0].decision_state == "rejected"

def test_decision_state_pending_review() -> None:
    d = _decision(outcome="needs_more_review")
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(d,),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    assert report.decision_results[0].decision_state == "pending_review"

def test_decision_state_superseded() -> None:
    d1 = _decision("d1", decided_at=NOW - timedelta(days=1), outcome="accepted_for_audit_log", rationale="first review")
    d2 = _decision("d2", decided_at=NOW, outcome="accepted_for_audit_log", rationale="second review")
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(d1, d2),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    assert report.decision_results[0].decision_state == "superseded"

# ---------------------------------------------------------------------------
# Decision precedence first-match-wins
# ---------------------------------------------------------------------------

def test_not_applicable_outranks_missing() -> None:
    ref = _ref("q1", entry_state="not_applicable")
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(ref,),
        decision_records=(),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    assert report.decision_results[0].decision_state == "not_applicable"

def test_blocked_outranks_disputed() -> None:
    """Unsafe content should produce BLOCKED before DISPUTED."""
    d1 = _decision("d1", rationale="production ready")
    d2 = _decision("d2", rationale="ok", outcome="rejected_for_audit_log")
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(d1, d2),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    assert report.state == HumanReviewDecisionLogState.BLOCKED

def test_disputed_outranks_duplicate() -> None:
    """Conflicting outcomes should produce DISPUTED before DUPLICATE."""
    d1 = _decision("d1", reviewer="r1", outcome="accepted_for_audit_log", rationale="ok")
    d2 = _decision("d2", reviewer="r1", outcome="rejected_for_audit_log", rationale="ok")
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(d1, d2),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    assert report.decision_results[0].decision_state == "disputed"

def test_rejected_outranks_stale() -> None:
    d = _decision(outcome="rejected_for_audit_log", generated_at=OLD)
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(d,),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    assert report.decision_results[0].decision_state == "rejected"

def test_logged_is_last_precedence() -> None:
    """LOGGED is only reached when no other rule matches."""
    d = _decision(outcome="accepted_for_audit_log")
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(d,),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    assert report.decision_results[0].decision_state == "logged"

# ---------------------------------------------------------------------------
# Unsafe content detection
# ---------------------------------------------------------------------------

def test_unsafe_metadata_blocks() -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref(),),
        decision_records=(_decision(),),
        metadata={"bad": 42},
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    assert report.state == HumanReviewDecisionLogState.BLOCKED
    assert report.safety_flags.has_unsafe_content is True

def test_forbidden_term_in_rationale_blocks() -> None:
    d = _decision(rationale="deploy immediately to production")
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref(),),
        decision_records=(d,),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    assert report.state == HumanReviewDecisionLogState.BLOCKED
    assert report.safety_flags.has_forbidden_terms is True

def test_forbidden_term_in_decision_id_blocks() -> None:
    d = _decision(decision_id="live trading signal")
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref(),),
        decision_records=(d,),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    assert report.state == HumanReviewDecisionLogState.BLOCKED

def test_forbidden_term_in_metadata_blocks() -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref(),),
        metadata={"note": "approved for production"},
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    assert report.state == HumanReviewDecisionLogState.BLOCKED

def test_forbidden_term_task_completed_blocks() -> None:
    d = _decision(rationale="task completed successfully")
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref(),),
        decision_records=(d,),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    assert report.state == HumanReviewDecisionLogState.BLOCKED

# ---------------------------------------------------------------------------
# Forbidden term false-positive avoidance
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("benign", [
    "pending approval from security team",
    "certification body",
    "no recommendation needed",
    "signal processing",
    "no signal detected",
    "assign a reviewer",
    "manual note for audit",
    "task queue",
    "task note",
    "completed checklist",
])
def test_benign_terms_not_blocked(benign: str) -> None:
    d = _decision(rationale=benign)
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(d,),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    assert report.state != HumanReviewDecisionLogState.BLOCKED

# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def test_blocking_issue_produces_blocked() -> None:
    d = _decision(rationale="production ready")
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref(),),
        decision_records=(d,),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    assert report.state == HumanReviewDecisionLogState.BLOCKED

def test_advisory_issue_produces_degraded() -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    assert report.state == HumanReviewDecisionLogState.DEGRADED

def test_no_issues_produces_ok() -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(_decision("d1", queue_entry_id="q1"),),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    assert report.state == HumanReviewDecisionLogState.OK

def test_not_applicable_does_not_block() -> None:
    ref = _ref("q1", entry_state="not_applicable")
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(ref,),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    assert report.state == HumanReviewDecisionLogState.OK

def test_strict_mode_promotes_degraded_to_blocked() -> None:
    config = HumanReviewDecisionLogConfig(strict=True)
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(),
        config=config,
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    assert report.state == HumanReviewDecisionLogState.BLOCKED

def test_strict_mode_promotes_blocked_stays_blocked() -> None:
    config = HumanReviewDecisionLogConfig(strict=True)
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(_decision(rationale="production ready"),),
        config=config,
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    assert report.state == HumanReviewDecisionLogState.BLOCKED

def test_forbid_action_terms_false_still_catches_unsafe() -> None:
    """When forbid_action_terms is False, unsafe non-string content still blocks."""
    config = HumanReviewDecisionLogConfig(forbid_action_terms=False)
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(_decision(),),
        metadata={"bad": 42},
        config=config,
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    assert report.state == HumanReviewDecisionLogState.BLOCKED

# ---------------------------------------------------------------------------
# Opaque refs
# ---------------------------------------------------------------------------

def test_artifact_refs_remain_strings() -> None:
    ref = _ref("q1")
    ref = HumanReviewQueueEntryRef(
        queue_entry_id="q1",
        artifact_ref="/some/opaque/path/to/artifact.json",
        report_ref="/another/opaque/report.md",
        generated_at=NOW,
    )
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(ref,),
        decision_records=(_decision("d1", queue_entry_id="q1"),),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    assert report.queue_entry_refs[0].artifact_ref == "/some/opaque/path/to/artifact.json"
    assert report.queue_entry_refs[0].report_ref == "/another/opaque/report.md"

# ---------------------------------------------------------------------------
# Safety notice
# ---------------------------------------------------------------------------

def test_safety_notice_contains_audit_only() -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref(),),
        decision_records=(_decision(),),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    assert "audit-only" in report.safety_notice.lower()
    assert "decision logged" in report.safety_notice.lower()

def test_safety_notice_disclaims_approval() -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref(),),
        decision_records=(_decision(),),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    assert "approval" in report.safety_notice.lower()
    assert "certification" in report.safety_notice.lower()
    assert "task completion" in report.safety_notice.lower()

def test_no_executable_remediation_in_output() -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref(),),
        decision_records=(_decision(),),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    text = report.safety_notice.lower()
    assert "deploy immediately" not in text
    assert "apply patch" not in text
    assert "run this command" not in text

def test_no_automatic_assignment_in_output() -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref(),),
        decision_records=(_decision(),),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    text = report.safety_notice.lower()
    assert "assign to" not in text
    assert "create ticket" not in text

# ---------------------------------------------------------------------------
# Input immutability
# ---------------------------------------------------------------------------

def test_input_not_mutated() -> None:
    ref = _ref("q1")
    rec = _decision("d1", queue_entry_id="q1")
    original_ref_id = ref.queue_entry_id
    original_rec_id = rec.decision_id
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(ref,),
        decision_records=(rec,),
        generated_at=NOW,
    )
    _ = build_human_review_decision_log_report(inp)
    assert ref.queue_entry_id == original_ref_id
    assert rec.decision_id == original_rec_id

def test_input_metadata_not_mutated() -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref(),),
        decision_records=(_decision(),),
        metadata={"key": "value"},
        generated_at=NOW,
    )
    original = dict(inp.metadata)
    _ = build_human_review_decision_log_report(inp)
    assert dict(inp.metadata) == original

# ---------------------------------------------------------------------------
# Every queue entry gets exactly one result
# ---------------------------------------------------------------------------

def test_every_queue_entry_gets_one_result() -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"), _ref("q2"), _ref("q3")),
        decision_records=(
            _decision("d1", queue_entry_id="q1"),
            _decision("d2", queue_entry_id="q3"),
        ),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    assert len(report.decision_results) == 3
    states = {r.queue_entry_id: r.decision_state for r in report.decision_results}
    assert states["q1"] == "logged"
    assert states["q2"] == "missing"
    assert states["q3"] == "logged"

# ---------------------------------------------------------------------------
# Data quality
# ---------------------------------------------------------------------------

def test_data_quality_counts() -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"), _ref("q2")),
        decision_records=(_decision("d1", queue_entry_id="q1"),),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    assert report.data_quality.total_queue_entry_refs == 2
    assert report.data_quality.total_decision_records == 1
    assert report.data_quality.total_decision_results == 2
    assert report.data_quality.missing_decision_count == 1
    assert report.data_quality.logged_count == 1
    assert report.data_quality.missing_count == 1

# ---------------------------------------------------------------------------
# Decision validity states
# ---------------------------------------------------------------------------

def test_validity_valid_for_logged() -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(_decision("d1", queue_entry_id="q1"),),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    assert report.decision_results[0].decision_validity == "valid_for_audit_log"

def test_validity_invalid_for_missing() -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    assert report.decision_results[0].decision_validity == "invalid_for_audit_log"

def test_validity_partial_for_incomplete() -> None:
    d = _decision(reviewer="")
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(d,),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    assert report.decision_results[0].decision_validity == "partial"

def test_validity_not_applicable() -> None:
    ref = _ref("q1", entry_state="not_applicable")
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(ref,),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    assert report.decision_results[0].decision_validity == "not_applicable"

# ---------------------------------------------------------------------------
# Decision log is not approval/readiness
# ---------------------------------------------------------------------------

def test_decision_logged_does_not_imply_approval() -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(_decision(outcome="accepted_for_audit_log"),),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    assert report.decision_results[0].decision_state == "logged"
    assert "does not imply" in report.safety_notice.lower()
    assert "approval" in report.safety_notice.lower()
    assert "task completion" in report.safety_notice.lower()

def test_accepted_not_trading_readiness() -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(_decision(outcome="accepted_for_audit_log"),),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    assert "trading readiness" in report.safety_notice.lower()

def test_no_approval_readiness_signal_output() -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(_decision(),),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    # The safety notice disclaims these, it does not claim them
    assert "buy signal" not in report.safety_notice.lower()
    assert "sell signal" not in report.safety_notice.lower()

# ---------------------------------------------------------------------------
# Report includes all required fields
# ---------------------------------------------------------------------------

def test_report_includes_queue_entry_refs() -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    assert len(report.queue_entry_refs) == 1

def test_report_includes_decision_records() -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(_decision("d1", queue_entry_id="q1"),),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    assert len(report.decision_records) == 1

def test_report_includes_links() -> None:
    link = HumanReviewDecisionLink(link_id="l1", source_id="q1", target_id="d1")
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(_decision("d1", queue_entry_id="q1"),),
        links=(link,),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    assert len(report.links) == 1

def test_report_includes_issues() -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    assert len(report.issues) > 0  # missing_decision

def test_report_includes_decision_results() -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(_decision("d1", queue_entry_id="q1"),),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    assert len(report.decision_results) == 1

def test_report_includes_data_quality() -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(_decision("d1", queue_entry_id="q1"),),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    assert report.data_quality.total_queue_entry_refs == 1

def test_report_includes_safety_flags() -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(_decision("d1", queue_entry_id="q1"),),
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    assert report.safety_flags.is_safe is True

def test_report_includes_metadata() -> None:
    inp = HumanReviewDecisionLogInput(
        queue_entry_refs=(_ref("q1"),),
        decision_records=(_decision("d1", queue_entry_id="q1"),),
        metadata={"caller": "test"},
        generated_at=NOW,
    )
    report = build_human_review_decision_log_report(inp)
    assert report.metadata["caller"] == "test"
