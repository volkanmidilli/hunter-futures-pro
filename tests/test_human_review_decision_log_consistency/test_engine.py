"""Tests for hunter.human_review_decision_log_consistency engine."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from hunter.human_review_decision_log import (
    HumanReviewDecisionLogConfig,
    HumanReviewDecisionLogInput,
    HumanReviewDecisionLogReport,
    HumanReviewDecisionLogSafetyFlags,
    HumanReviewDecisionLogState,
    HumanReviewDecisionRecord,
    HumanReviewDecisionResult,
    HumanReviewDecisionState,
    HumanReviewQueueEntryRef,
    build_human_review_decision_log_report,
)
from hunter.human_review_queue import (
    HumanReviewQueueEntry,
    HumanReviewQueueReport,
    HumanReviewQueueSafetyFlags,
    HumanReviewQueueState,
)
from hunter.human_review_decision_log_consistency import (
    HumanReviewDecisionLogConsistencyConfig,
    HumanReviewDecisionLogConsistencyInput,
    HumanReviewDecisionLogConsistencyIssueType,
    HumanReviewDecisionLogConsistencyLink,
    HumanReviewDecisionLogConsistencyReasonCode,
    HumanReviewDecisionLogConsistencySafetyFlags,
    HumanReviewDecisionLogConsistencySeverity,
    HumanReviewDecisionLogConsistencyState,
    build_human_review_decision_log_consistency_report,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ts() -> datetime:
    return datetime(2026, 7, 9, 12, 0, 0, tzinfo=timezone.utc)


def _queue_entry(
    queue_entry_id: str = "qe-1",
    entry_state: str = "blocked",
    priority: str = "advisory",
    severity: str = "advisory",
    reason_codes: tuple[str, ...] = (),
) -> HumanReviewQueueEntry:
    return HumanReviewQueueEntry(
        queue_entry_id=queue_entry_id,
        entry_state=entry_state,
        priority=priority,
        severity=severity,
        reason_codes=reason_codes,
    )


def _queue_report(
    entries: tuple[HumanReviewQueueEntry, ...] = (),
    state: HumanReviewQueueState = HumanReviewQueueState.NOT_APPLICABLE,
    report_id: str = "queue-1",
    blocked: bool = False,
    unsafe: bool = False,
    forbidden: bool = False,
) -> HumanReviewQueueReport:
    safety_flags = HumanReviewQueueSafetyFlags(
        has_unsafe_content=unsafe,
        has_forbidden_terms=forbidden,
    )
    return HumanReviewQueueReport(
        report_id=report_id,
        generated_at=_ts(),
        state=state,
        project_version="0.40.0-dev",
        queue_entries=entries,
        safety_flags=safety_flags,
    )


def _decision_log_ref(
    queue_entry_id: str = "qe-1",
    entry_state: str = "blocked",
    priority: str = "advisory",
    severity: str = "advisory",
) -> HumanReviewQueueEntryRef:
    return HumanReviewQueueEntryRef(
        queue_entry_id=queue_entry_id,
        entry_state=entry_state,
        priority=priority,
        severity=severity,
    )


def _decision_result(
    queue_entry_id: str = "qe-1",
    decision_state: str = "blocked",
    severity: str = "advisory",
    reason_codes: tuple[str, ...] = (),
) -> HumanReviewDecisionResult:
    return HumanReviewDecisionResult(
        decision_result_id=f"dr-{queue_entry_id}",
        queue_entry_id=queue_entry_id,
        decision_state=decision_state,
        severity=severity,
        reason_codes=reason_codes,
    )


def _decision_log_report(
    refs: tuple[HumanReviewQueueEntryRef, ...] = (),
    results: tuple[HumanReviewDecisionResult, ...] = (),
    state: HumanReviewDecisionLogState = HumanReviewDecisionLogState.NOT_APPLICABLE,
    report_id: str = "dlog-1",
    blocked: bool = False,
    unsafe: bool = False,
    forbidden: bool = False,
) -> HumanReviewDecisionLogReport:
    safety_flags = HumanReviewDecisionLogSafetyFlags(
        has_unsafe_content=unsafe,
        has_forbidden_terms=forbidden,
    )
    return HumanReviewDecisionLogReport(
        report_id=report_id,
        generated_at=_ts(),
        state=state,
        project_version="0.41.0-dev",
        queue_entry_refs=refs,
        decision_results=results,
        safety_flags=safety_flags,
    )


def _build_queue_report_from_entries(entries: tuple[HumanReviewQueueEntry, ...]) -> HumanReviewQueueReport:
    return build_human_review_queue_report(
        HumanReviewQueueInput(source_records=(), generated_at=_ts())
    ) if not entries else HumanReviewQueueReport(
        report_id="queue-1",
        generated_at=_ts(),
        queue_entries=entries,
        safety_flags=HumanReviewQueueSafetyFlags(),
    )


# ---------------------------------------------------------------------------
# Empty input and basic boundary
# ---------------------------------------------------------------------------

class TestEmptyInput:
    def test_empty_input_returns_not_applicable(self) -> None:
        input = HumanReviewDecisionLogConsistencyInput(
            queue_report=_queue_report(),
            decision_log_report=_decision_log_report(),
            generated_at=_ts(),
        )
        report = build_human_review_decision_log_consistency_report(input)
        assert report.state == HumanReviewDecisionLogConsistencyState.NOT_APPLICABLE
        assert report.report_id
        assert report.data_quality.total_queue_entries == 0
        assert report.data_quality.total_decision_log_refs == 0
        assert report.reason_codes == (HumanReviewDecisionLogConsistencyReasonCode.NOT_APPLICABLE,)

    def test_empty_input_with_flag_false_returns_ok(self) -> None:
        config = HumanReviewDecisionLogConsistencyConfig(empty_input_is_not_applicable=False)
        input = HumanReviewDecisionLogConsistencyInput(
            queue_report=_queue_report(),
            decision_log_report=_decision_log_report(),
            config=config,
            generated_at=_ts(),
        )
        report = build_human_review_decision_log_consistency_report(input)
        assert report.state == HumanReviewDecisionLogConsistencyState.OK

    def test_empty_input_deterministic_id(self) -> None:
        input = HumanReviewDecisionLogConsistencyInput(
            queue_report=_queue_report(report_id="q1"),
            decision_log_report=_decision_log_report(report_id="d1"),
            generated_at=_ts(),
        )
        r1 = build_human_review_decision_log_consistency_report(input)
        r2 = build_human_review_decision_log_consistency_report(input)
        assert r1.report_id == r2.report_id


# ---------------------------------------------------------------------------
# Blocked/unsafe input carry-forward
# ---------------------------------------------------------------------------

class TestBlockedInput:
    def test_blocked_queue_report_propagates_blocked(self) -> None:
        input = HumanReviewDecisionLogConsistencyInput(
            queue_report=_queue_report(state=HumanReviewQueueState.BLOCKED),
            decision_log_report=_decision_log_report(),
            generated_at=_ts(),
        )
        report = build_human_review_decision_log_consistency_report(input)
        assert report.state == HumanReviewDecisionLogConsistencyState.BLOCKED
        assert report.reason_codes == (HumanReviewDecisionLogConsistencyReasonCode.INPUT_BLOCKED,)

    def test_blocked_decision_log_report_propagates_blocked(self) -> None:
        input = HumanReviewDecisionLogConsistencyInput(
            queue_report=_queue_report(),
            decision_log_report=_decision_log_report(state=HumanReviewDecisionLogState.BLOCKED),
            generated_at=_ts(),
        )
        report = build_human_review_decision_log_consistency_report(input)
        assert report.state == HumanReviewDecisionLogConsistencyState.BLOCKED

    def test_unsafe_queue_report_propagates_blocked(self) -> None:
        input = HumanReviewDecisionLogConsistencyInput(
            queue_report=_queue_report(unsafe=True),
            decision_log_report=_decision_log_report(),
            generated_at=_ts(),
        )
        report = build_human_review_decision_log_consistency_report(input)
        assert report.state == HumanReviewDecisionLogConsistencyState.BLOCKED
        assert report.safety_flags.has_unsafe_content is True

    def test_forbidden_decision_log_report_propagates_blocked(self) -> None:
        input = HumanReviewDecisionLogConsistencyInput(
            queue_report=_queue_report(),
            decision_log_report=_decision_log_report(forbidden=True),
            generated_at=_ts(),
        )
        report = build_human_review_decision_log_consistency_report(input)
        assert report.state == HumanReviewDecisionLogConsistencyState.BLOCKED
        assert report.safety_flags.has_forbidden_terms is True

    def test_blocked_report_deterministic_id(self) -> None:
        input = HumanReviewDecisionLogConsistencyInput(
            queue_report=_queue_report(state=HumanReviewQueueState.BLOCKED),
            decision_log_report=_decision_log_report(),
            generated_at=_ts(),
        )
        r1 = build_human_review_decision_log_consistency_report(input)
        r2 = build_human_review_decision_log_consistency_report(input)
        assert r1.report_id == r2.report_id
        assert r1.report_id.startswith("blocked-") is False


class TestConsistencyInputSafety:
    def test_unsafe_consistency_metadata_blocks(self) -> None:
        input = HumanReviewDecisionLogConsistencyInput(
            queue_report=_queue_report(entries=(_queue_entry(),)),
            decision_log_report=_decision_log_report(
                refs=(_decision_log_ref(),),
                results=(_decision_result(),),
            ),
            metadata={"key": 123},
            generated_at=_ts(),
        )
        report = build_human_review_decision_log_consistency_report(input)
        assert report.state == HumanReviewDecisionLogConsistencyState.BLOCKED

    def test_forbidden_consistency_link_blocks(self) -> None:
        link = HumanReviewDecisionLogConsistencyLink(
            link_id="link-1",
            queue_entry_id="qe-1",
            decision_log_queue_entry_id="qe-1",
            link_type="execute now",
        )
        input = HumanReviewDecisionLogConsistencyInput(
            queue_report=_queue_report(entries=(_queue_entry(),)),
            decision_log_report=_decision_log_report(
                refs=(_decision_log_ref(),),
                results=(_decision_result(),),
            ),
            links=(link,),
            generated_at=_ts(),
        )
        report = build_human_review_decision_log_consistency_report(input)
        assert report.state == HumanReviewDecisionLogConsistencyState.BLOCKED


# ---------------------------------------------------------------------------
# Matched pairs
# ---------------------------------------------------------------------------

class TestMatchedPairs:
    def test_matched_pair_returns_ok(self) -> None:
        input = HumanReviewDecisionLogConsistencyInput(
            queue_report=_queue_report(entries=(_queue_entry(),)),
            decision_log_report=_decision_log_report(
                refs=(_decision_log_ref(),),
                results=(_decision_result(),),
            ),
            generated_at=_ts(),
        )
        report = build_human_review_decision_log_consistency_report(input)
        assert report.state == HumanReviewDecisionLogConsistencyState.OK
        assert report.data_quality.matched_refs == 1
        assert report.data_quality.total_queue_entries == 1
        assert report.data_quality.total_decision_log_refs == 1

    def test_cross_reference_derived_views(self) -> None:
        input = HumanReviewDecisionLogConsistencyInput(
            queue_report=_queue_report(entries=(_queue_entry(),)),
            decision_log_report=_decision_log_report(
                refs=(_decision_log_ref(),),
                results=(_decision_result(),),
            ),
            generated_at=_ts(),
        )
        report = build_human_review_decision_log_consistency_report(input)
        assert len(report.queue_entry_to_decision_log_refs) == 1
        assert len(report.orphan_queue_entries) == 0
        assert len(report.orphan_decision_log_refs) == 0
        assert len(report.mismatched_refs) == 0


# ---------------------------------------------------------------------------
# Orphans
# ---------------------------------------------------------------------------

class TestOrphanDetection:
    def test_orphan_queue_entry_expecting_decision(self) -> None:
        input = HumanReviewDecisionLogConsistencyInput(
            queue_report=_queue_report(entries=(_queue_entry(entry_state="open"),)),
            decision_log_report=_decision_log_report(),
            generated_at=_ts(),
        )
        report = build_human_review_decision_log_consistency_report(input)
        assert report.state == HumanReviewDecisionLogConsistencyState.DEGRADED
        assert report.data_quality.orphan_queue_entries == 1
        assert any(
            issue.issue_type == HumanReviewDecisionLogConsistencyIssueType.MISSING_DECISION_LOG_REF.value
            for issue in report.issues
        )

    def test_orphan_queue_entry_not_expecting_decision(self) -> None:
        input = HumanReviewDecisionLogConsistencyInput(
            queue_report=_queue_report(entries=(_queue_entry(entry_state="closed"),)),
            decision_log_report=_decision_log_report(),
            generated_at=_ts(),
        )
        report = build_human_review_decision_log_consistency_report(input)
        assert report.state == HumanReviewDecisionLogConsistencyState.OK
        assert report.data_quality.orphan_queue_entries == 1
        assert report.data_quality.matched_refs == 0
        assert not any(
            issue.issue_type == HumanReviewDecisionLogConsistencyIssueType.MISSING_DECISION_LOG_REF.value
            for issue in report.issues
        )

    def test_orphan_decision_log_ref(self) -> None:
        input = HumanReviewDecisionLogConsistencyInput(
            queue_report=_queue_report(),
            decision_log_report=_decision_log_report(
                refs=(_decision_log_ref(),),
                results=(_decision_result(decision_state="orphaned"),),
            ),
            generated_at=_ts(),
        )
        report = build_human_review_decision_log_consistency_report(input)
        assert report.state == HumanReviewDecisionLogConsistencyState.DEGRADED
        assert report.data_quality.orphan_decision_log_refs == 1
        assert any(
            issue.issue_type == HumanReviewDecisionLogConsistencyIssueType.ORPHAN_DECISION_LOG_REF.value
            for issue in report.issues
        )


# ---------------------------------------------------------------------------
# Mismatched fields
# ---------------------------------------------------------------------------

class TestMismatchedFields:
    def test_mismatched_state(self) -> None:
        input = HumanReviewDecisionLogConsistencyInput(
            queue_report=_queue_report(entries=(_queue_entry(entry_state="open"),)),
            decision_log_report=_decision_log_report(
                refs=(_decision_log_ref(entry_state="open"),),
                results=(_decision_result(decision_state="blocked"),),
            ),
            generated_at=_ts(),
        )
        report = build_human_review_decision_log_consistency_report(input)
        assert report.state == HumanReviewDecisionLogConsistencyState.DEGRADED
        assert any(
            issue.issue_type == HumanReviewDecisionLogConsistencyIssueType.MISMATCHED_QUEUE_STATE.value
            for issue in report.issues
        )
        assert len(report.mismatched_refs) == 1

    def test_mismatched_priority(self) -> None:
        input = HumanReviewDecisionLogConsistencyInput(
            queue_report=_queue_report(entries=(_queue_entry(priority="high"),)),
            decision_log_report=_decision_log_report(
                refs=(_decision_log_ref(priority="high"),),
                results=(_decision_result(severity="low"),),
            ),
            generated_at=_ts(),
        )
        report = build_human_review_decision_log_consistency_report(input)
        assert any(
            issue.issue_type == HumanReviewDecisionLogConsistencyIssueType.MISMATCHED_QUEUE_PRIORITY.value
            for issue in report.issues
        )

    def test_mismatched_severity(self) -> None:
        input = HumanReviewDecisionLogConsistencyInput(
            queue_report=_queue_report(entries=(_queue_entry(severity="advisory"),)),
            decision_log_report=_decision_log_report(
                refs=(_decision_log_ref(severity="advisory"),),
                results=(_decision_result(severity="blocking"),),
            ),
            generated_at=_ts(),
        )
        report = build_human_review_decision_log_consistency_report(input)
        assert any(
            issue.issue_type == HumanReviewDecisionLogConsistencyIssueType.MISMATCHED_QUEUE_SEVERITY.value
            for issue in report.issues
        )

    def test_mismatched_reason_codes(self) -> None:
        input = HumanReviewDecisionLogConsistencyInput(
            queue_report=_queue_report(
                entries=(_queue_entry(reason_codes=("missing_evidence",)),)
            ),
            decision_log_report=_decision_log_report(
                refs=(_decision_log_ref(),),
                results=(_decision_result(reason_codes=("decision_logged",)),),
            ),
            generated_at=_ts(),
        )
        report = build_human_review_decision_log_consistency_report(input)
        assert any(
            issue.issue_type == HumanReviewDecisionLogConsistencyIssueType.MISMATCHED_QUEUE_REASON_CODES.value
            for issue in report.issues
        )

    def test_no_mismatch_when_reason_codes_empty(self) -> None:
        input = HumanReviewDecisionLogConsistencyInput(
            queue_report=_queue_report(entries=(_queue_entry(reason_codes=()),)),
            decision_log_report=_decision_log_report(
                refs=(_decision_log_ref(),),
                results=(_decision_result(reason_codes=("decision_logged",)),),
            ),
            generated_at=_ts(),
        )
        report = build_human_review_decision_log_consistency_report(input)
        assert not any(
            issue.issue_type == HumanReviewDecisionLogConsistencyIssueType.MISMATCHED_QUEUE_REASON_CODES.value
            for issue in report.issues
        )


# ---------------------------------------------------------------------------
# Inconsistent result states
# ---------------------------------------------------------------------------

class TestInconsistentResultStates:
    def test_inconsistent_orphan_status(self) -> None:
        input = HumanReviewDecisionLogConsistencyInput(
            queue_report=_queue_report(entries=(_queue_entry(),)),
            decision_log_report=_decision_log_report(
                refs=(_decision_log_ref(),),
                results=(_decision_result(decision_state="orphaned"),),
            ),
            generated_at=_ts(),
        )
        report = build_human_review_decision_log_consistency_report(input)
        assert any(
            issue.issue_type == HumanReviewDecisionLogConsistencyIssueType.INCONSISTENT_ORPHAN_STATUS.value
            for issue in report.issues
        )

    def test_inconsistent_missing_status(self) -> None:
        input = HumanReviewDecisionLogConsistencyInput(
            queue_report=_queue_report(entries=(_queue_entry(entry_state="open"),)),
            decision_log_report=_decision_log_report(
                refs=(_decision_log_ref(),),
                results=(_decision_result(decision_state="missing"),),
            ),
            generated_at=_ts(),
        )
        report = build_human_review_decision_log_consistency_report(input)
        assert any(
            issue.issue_type == HumanReviewDecisionLogConsistencyIssueType.INCONSISTENT_MISSING_STATUS.value
            for issue in report.issues
        )

    def test_missing_status_ok_when_not_expecting_decision(self) -> None:
        input = HumanReviewDecisionLogConsistencyInput(
            queue_report=_queue_report(entries=(_queue_entry(entry_state="closed"),)),
            decision_log_report=_decision_log_report(
                refs=(_decision_log_ref(),),
                results=(_decision_result(decision_state="missing"),),
            ),
            generated_at=_ts(),
        )
        report = build_human_review_decision_log_consistency_report(input)
        assert not any(
            issue.issue_type == HumanReviewDecisionLogConsistencyIssueType.INCONSISTENT_MISSING_STATUS.value
            for issue in report.issues
        )

    def test_inconsistent_blocked_status(self) -> None:
        input = HumanReviewDecisionLogConsistencyInput(
            queue_report=_queue_report(entries=(_queue_entry(entry_state="open"),)),
            decision_log_report=_decision_log_report(
                refs=(_decision_log_ref(),),
                results=(_decision_result(decision_state="blocked"),),
            ),
            generated_at=_ts(),
        )
        report = build_human_review_decision_log_consistency_report(input)
        assert any(
            issue.issue_type == HumanReviewDecisionLogConsistencyIssueType.INCONSISTENT_BLOCKED_STATUS.value
            for issue in report.issues
        )

    def test_blocked_status_ok_when_queue_blocked(self) -> None:
        input = HumanReviewDecisionLogConsistencyInput(
            queue_report=_queue_report(entries=(_queue_entry(entry_state="blocked"),)),
            decision_log_report=_decision_log_report(
                refs=(_decision_log_ref(),),
                results=(_decision_result(decision_state="blocked"),),
            ),
            generated_at=_ts(),
        )
        report = build_human_review_decision_log_consistency_report(input)
        assert not any(
            issue.issue_type == HumanReviewDecisionLogConsistencyIssueType.INCONSISTENT_BLOCKED_STATUS.value
            for issue in report.issues
        )


# ---------------------------------------------------------------------------
# Strict mode
# ---------------------------------------------------------------------------

class TestStrictMode:
    def test_strict_promotes_degraded_to_blocked(self) -> None:
        config = HumanReviewDecisionLogConsistencyConfig(strict=True)
        input = HumanReviewDecisionLogConsistencyInput(
            queue_report=_queue_report(entries=(_queue_entry(entry_state="open"),)),
            decision_log_report=_decision_log_report(
                refs=(_decision_log_ref(),),
                results=(_decision_result(decision_state="blocked"),),
            ),
            config=config,
            generated_at=_ts(),
        )
        report = build_human_review_decision_log_consistency_report(input)
        assert report.state == HumanReviewDecisionLogConsistencyState.BLOCKED


# ---------------------------------------------------------------------------
# Determinism and ordering
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_deterministic_report_id(self) -> None:
        input = HumanReviewDecisionLogConsistencyInput(
            queue_report=_queue_report(entries=(_queue_entry(),)),
            decision_log_report=_decision_log_report(
                refs=(_decision_log_ref(),),
                results=(_decision_result(),),
            ),
            generated_at=_ts(),
        )
        r1 = build_human_review_decision_log_consistency_report(input)
        r2 = build_human_review_decision_log_consistency_report(input)
        assert r1.report_id == r2.report_id

    def test_deterministic_cross_reference_ids(self) -> None:
        input = HumanReviewDecisionLogConsistencyInput(
            queue_report=_queue_report(entries=(_queue_entry(),)),
            decision_log_report=_decision_log_report(
                refs=(_decision_log_ref(),),
                results=(_decision_result(),),
            ),
            generated_at=_ts(),
        )
        r1 = build_human_review_decision_log_consistency_report(input)
        r2 = build_human_review_decision_log_consistency_report(input)
        assert len(r1.cross_references) == len(r2.cross_references)
        for cr1, cr2 in zip(r1.cross_references, r2.cross_references):
            assert cr1.cross_reference_id == cr2.cross_reference_id

    def test_deterministic_issue_ids(self) -> None:
        input = HumanReviewDecisionLogConsistencyInput(
            queue_report=_queue_report(entries=(_queue_entry(entry_state="open"),)),
            decision_log_report=_decision_log_report(),
            generated_at=_ts(),
        )
        r1 = build_human_review_decision_log_consistency_report(input)
        r2 = build_human_review_decision_log_consistency_report(input)
        assert len(r1.issues) == len(r2.issues)
        for i1, i2 in zip(r1.issues, r2.issues):
            assert i1.issue_id == i2.issue_id

    def test_deterministic_ordering(self) -> None:
        input = HumanReviewDecisionLogConsistencyInput(
            queue_report=_queue_report(
                entries=(
                    _queue_entry(queue_entry_id="c"),
                    _queue_entry(queue_entry_id="a"),
                    _queue_entry(queue_entry_id="b"),
                )
            ),
            decision_log_report=_decision_log_report(
                refs=(
                    _decision_log_ref(queue_entry_id="c"),
                    _decision_log_ref(queue_entry_id="a"),
                ),
                results=(
                    _decision_result(queue_entry_id="c"),
                    _decision_result(queue_entry_id="a"),
                ),
            ),
            generated_at=_ts(),
        )
        report = build_human_review_decision_log_consistency_report(input)
        ids = [cr.queue_entry_id for cr in report.cross_references]
        assert ids == sorted(ids)


# ---------------------------------------------------------------------------
# No mutation
# ---------------------------------------------------------------------------

class TestNoMutation:
    def test_input_reports_unchanged(self) -> None:
        queue_report = _queue_report(entries=(_queue_entry(),))
        decision_log_report = _decision_log_report(
            refs=(_decision_log_ref(),),
            results=(_decision_result(),),
        )
        queue_before_entries = queue_report.queue_entries
        dlog_before_refs = decision_log_report.queue_entry_refs
        dlog_before_results = decision_log_report.decision_results
        input = HumanReviewDecisionLogConsistencyInput(
            queue_report=queue_report,
            decision_log_report=decision_log_report,
            generated_at=_ts(),
        )
        build_human_review_decision_log_consistency_report(input)
        assert queue_report.queue_entries == queue_before_entries
        assert decision_log_report.queue_entry_refs == dlog_before_refs
        assert decision_log_report.decision_results == dlog_before_results
        assert queue_report.report_id == "queue-1"
        assert decision_log_report.report_id == "dlog-1"


# ---------------------------------------------------------------------------
# Opaque refs
# ---------------------------------------------------------------------------

class TestOpaqueRefs:
    def test_refs_treated_as_strings(self) -> None:
        input = HumanReviewDecisionLogConsistencyInput(
            queue_report=_queue_report(
                entries=(
                    _queue_entry(queue_entry_id="path/to/report.md"),
                )
            ),
            decision_log_report=_decision_log_report(
                refs=(_decision_log_ref(queue_entry_id="path/to/report.md"),),
                results=(_decision_result(queue_entry_id="path/to/report.md"),),
            ),
            generated_at=_ts(),
        )
        report = build_human_review_decision_log_consistency_report(input)
        assert report.state == HumanReviewDecisionLogConsistencyState.OK


# ---------------------------------------------------------------------------
# Duplicate-ID fail-closed (MVP-41 semantic preservation)
# ---------------------------------------------------------------------------

class TestDuplicateIdFailClosed:
    def test_decision_log_duplicate_ids_propagate_blocked(self) -> None:
        dlog_input = HumanReviewDecisionLogInput(
            queue_entry_refs=(
                HumanReviewQueueEntryRef(queue_entry_id="qe-1"),
                HumanReviewQueueEntryRef(queue_entry_id="qe-1"),
            ),
            decision_records=(),
            generated_at=_ts(),
        )
        decision_log_report = build_human_review_decision_log_report(dlog_input)
        assert decision_log_report.state == HumanReviewDecisionLogState.BLOCKED

        input = HumanReviewDecisionLogConsistencyInput(
            queue_report=_queue_report(entries=(_queue_entry(),)),
            decision_log_report=decision_log_report,
            generated_at=_ts(),
        )
        report = build_human_review_decision_log_consistency_report(input)
        assert report.state == HumanReviewDecisionLogConsistencyState.BLOCKED


# ---------------------------------------------------------------------------
# MVP-41 semantic preservation
# ---------------------------------------------------------------------------

class TestMVP41SemanticsPreservation:
    def test_orphaned_decision_result_preserved(self) -> None:
        dlog_input = HumanReviewDecisionLogInput(
            queue_entry_refs=(),
            decision_records=(
                HumanReviewDecisionRecord(
                    decision_id="d-1",
                    queue_entry_id="unknown-qe",
                    outcome="accepted_for_audit_log",
                ),
            ),
            generated_at=_ts(),
        )
        decision_log_report = build_human_review_decision_log_report(dlog_input)
        assert decision_log_report.state == HumanReviewDecisionLogState.DEGRADED
        assert any(
            result.decision_state == HumanReviewDecisionState.ORPHANED.value
            for result in decision_log_report.decision_results
        )

        # When a caller-provided decision log report contains an ORPHANED result
        # for a queue entry that does exist in the queue, the consistency layer
        # reports an inconsistent orphan status.
        manual_dlog_report = HumanReviewDecisionLogReport(
            report_id="dlog-orphan",
            generated_at=_ts(),
            state=HumanReviewDecisionLogState.OK,
            project_version="0.41.0-dev",
            queue_entry_refs=(
                HumanReviewQueueEntryRef(queue_entry_id="unknown-qe"),
            ),
            decision_results=(
                HumanReviewDecisionResult(
                    queue_entry_id="unknown-qe",
                    decision_state=HumanReviewDecisionState.ORPHANED.value,
                ),
            ),
            safety_flags=HumanReviewDecisionLogSafetyFlags(),
        )
        input = HumanReviewDecisionLogConsistencyInput(
            queue_report=_queue_report(entries=(_queue_entry(queue_entry_id="unknown-qe"),)),
            decision_log_report=manual_dlog_report,
            generated_at=_ts(),
        )
        report = build_human_review_decision_log_consistency_report(input)
        assert report.state == HumanReviewDecisionLogConsistencyState.DEGRADED
        assert any(
            issue.issue_type == HumanReviewDecisionLogConsistencyIssueType.INCONSISTENT_ORPHAN_STATUS.value
            for issue in report.issues
        )

    def test_orphaned_decision_result_without_queue_is_not_applicable(self) -> None:
        dlog_input = HumanReviewDecisionLogInput(
            queue_entry_refs=(),
            decision_records=(
                HumanReviewDecisionRecord(
                    decision_id="d-1",
                    queue_entry_id="unknown-qe",
                    outcome="accepted_for_audit_log",
                ),
            ),
            generated_at=_ts(),
        )
        decision_log_report = build_human_review_decision_log_report(dlog_input)
        input = HumanReviewDecisionLogConsistencyInput(
            queue_report=_queue_report(),
            decision_log_report=decision_log_report,
            generated_at=_ts(),
        )
        report = build_human_review_decision_log_consistency_report(input)
        assert report.state == HumanReviewDecisionLogConsistencyState.NOT_APPLICABLE

    def test_not_applicable_missing_decision_skip_preserved(self) -> None:
        dlog_input = HumanReviewDecisionLogInput(
            queue_entry_refs=(
                HumanReviewQueueEntryRef(queue_entry_id="qe-1", entry_state="not_applicable"),
            ),
            decision_records=(),
            generated_at=_ts(),
        )
        decision_log_report = build_human_review_decision_log_report(dlog_input)
        assert any(
            result.decision_state == HumanReviewDecisionState.NOT_APPLICABLE.value
            for result in decision_log_report.decision_results
        )

        input = HumanReviewDecisionLogConsistencyInput(
            queue_report=_queue_report(
                entries=(_queue_entry(queue_entry_id="qe-1", entry_state="not_applicable", priority="info", severity="info"),)
            ),
            decision_log_report=decision_log_report,
            generated_at=_ts(),
        )
        report = build_human_review_decision_log_consistency_report(input)
        assert report.state == HumanReviewDecisionLogConsistencyState.OK
        assert not any(
            issue.issue_type == HumanReviewDecisionLogConsistencyIssueType.MISSING_DECISION_LOG_REF.value
            for issue in report.issues
        )


# ---------------------------------------------------------------------------
# Safety notice
# ---------------------------------------------------------------------------

class TestSafetyNotice:
    def test_safety_notice_present(self) -> None:
        input = HumanReviewDecisionLogConsistencyInput(
            queue_report=_queue_report(),
            decision_log_report=_decision_log_report(),
            generated_at=_ts(),
        )
        report = build_human_review_decision_log_consistency_report(input)
        notice = report.safety_notice.lower()
        assert "audit-only" in notice
        assert "do not imply" in notice
        assert "approval" in notice
        assert "trading readiness" in notice
        assert "executable remediation" in notice
