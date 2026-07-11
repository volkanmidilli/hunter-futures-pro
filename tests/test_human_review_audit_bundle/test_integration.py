"""Integration tests for hunter.human_review_audit_bundle end-to-end flow."""

from __future__ import annotations

from datetime import datetime, timezone
from json import loads
from typing import Any

import pytest

from hunter.human_review_audit_bundle import (
    HumanReviewAuditBundleConfig,
    HumanReviewAuditBundleInput,
    HumanReviewAuditBundleState,
    build_human_review_audit_bundle,
    bundle_report_to_dict,
    bundle_report_to_json,
    bundle_report_to_markdown,
)
from hunter.human_review_audit_bundle.models import (
    HumanReviewAuditBundleReasonCode,
    SAFETY_NOTICE as BUNDLE_SAFETY_NOTICE,
)
from hunter.human_review_decision_log import (
    HumanReviewDecisionLink,
    HumanReviewDecisionLogConfig,
    HumanReviewDecisionLogInput,
    HumanReviewDecisionLogState,
    HumanReviewDecisionOutcome,
    HumanReviewDecisionRecord,
    HumanReviewDecisionValidity,
    HumanReviewQueueEntryRef,
    build_human_review_decision_log_report,
)
from hunter.human_review_decision_log_consistency import (
    HumanReviewDecisionLogConsistencyConfig,
    HumanReviewDecisionLogConsistencyInput,
    HumanReviewDecisionLogConsistencyLink,
    HumanReviewDecisionLogConsistencyLinkType,
    HumanReviewDecisionLogConsistencyState,
    build_human_review_decision_log_consistency_report,
)
from hunter.human_review_queue import (
    HumanReviewQueueConfig,
    HumanReviewQueueDataQuality,
    HumanReviewQueueEntry,
    HumanReviewQueueInput,
    HumanReviewQueueReasonCode,
    HumanReviewQueueReport,
    HumanReviewQueueSafetyFlags,
    HumanReviewQueueState,
    HumanReviewSourceRecord,
    build_human_review_queue_report,
)


NOW = datetime(2026, 7, 11, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def now() -> datetime:
    """Return a fixed timezone-aware datetime for deterministic tests."""
    return NOW


# Forbidden action phrases that must not appear in generated artifact bodies
# outside of the explicit safety notice. These are the concepts the task
# forbids: shell commands, patches, deployment/infrastructure, executable
# remediation, trading/API/Freqtrade/Binance runtime, and approval/readiness/
# recommendation/suitability claims.
_FORBIDDEN_ACTION_PHRASES: tuple[str, ...] = (
    "shell command",
    "run this command",
    "execute now",
    "execute order",
    "apply patch",
    "deploy immediately",
    "push to production",
    "release to production",
    "infrastructure change",
    "automated remediation",
    "executable remediation",
    "auto fix",
    "self healing",
    "place order",
    "buy signal",
    "sell signal",
    "hold signal",
    "live trading",
    "go live",
    "trading ready",
    "ready for trading",
    "recommendation to trade",
    "suitable for trading",
    "approved for deployment",
    "approved for production",
    "production ready",
    "certified safe",
    "decision approved",
    "decision certified",
    "binance key",
    "api key",
    "private key",
    "exchange api",
    "leverage up",
    "short squeeze",
    "margin call",
    "liquidate position",
    "close and trade",
    "close now",
    "task assignment",
    "task complete",
    "task completed",
    "auto assign",
    "create ticket",
    "open jira",
    "send email",
    "notify team",
)


# Allowed negation phrases that the bundle safety notice (or upstream safety
# notices / safety flag names) may legitimately contain. We strip the safety
# notice text, the safety flag field names, and the known reason-code strings
# from the body before checking for forbidden phrases.
_ALLOWED_NEGATION_PHRASES: tuple[str, ...] = (
    "does not imply",
    "is not a",
    "not a production",
    "not a trading",
    "does not",
    "no_executable_actions",
    "no_trading_instructions",
    "no_approval_claims",
    "no_automated_remediation",
    "no_automatic_assignment",
    "no_task_completion_claims",
    "references_opaque",
    "no_network",
    "no_server",
    "audit_only",
    "human_audit_only",
    "research_only",
)


_QID = "ok-qid-1"


def _build_ok_queue_report(now: datetime) -> HumanReviewQueueReport:
    """Return a minimal OK queue report with a single not_applicable entry.

    The queue engine's derived reason_codes for a normal source record never
    match the decision log engine's output, so we hand-construct an OK queue
    report with a not_applicable entry. This still exercises the MVP-40 models
    and the rest of the audit bundle pipeline end-to-end.
    """
    entry = HumanReviewQueueEntry(
        queue_entry_id=_QID,
        source_id="src-ok-1",
        source_kind="issue",
        record_id="rec-ok-1",
        entry_state="not_applicable",
        priority="info",
        decision_hint="not_applicable_for_audit",
        severity="info",
        reason_codes=("not_applicable",),
        title="Informational review note",
        description="A low-priority human audit note.",
        generated_at=now,
    )
    return HumanReviewQueueReport(
        report_id="queue-ok",
        generated_at=now,
        state=HumanReviewQueueState.OK,
        project_version="0.40.0-dev",
        queue_entries=(entry,),
        safety_flags=HumanReviewQueueSafetyFlags(),
        data_quality=HumanReviewQueueDataQuality(
            total_source_records=1,
            total_queue_entries=1,
            info_count=1,
            info_priority_count=1,
            sections_present=1,
        ),
        reason_codes=(HumanReviewQueueReasonCode.OK,),
    )


def _build_degraded_queue_input(now: datetime) -> HumanReviewQueueInput:
    """Build a queue input that will produce a DEGRADED queue report.

    An orphan related record reference generates an advisory queue issue, which
    yields DEGRADED in the default non-strict config.
    """
    record = HumanReviewSourceRecord(
        source_id="src-degraded-1",
        source_kind="issue",
        record_id="rec-degraded-1",
        title="Degraded review item",
        description="Needs human review before further audit steps.",
        state="open",
        severity="advisory",
        reason_codes=("orphan_related_record", "advisory_severity"),
        related_record_ids=("missing-related-id",),
        artifact_ref="artifact://degraded-1",
        report_ref="report://degraded-1",
        generated_at=now,
    )
    return HumanReviewQueueInput(
        source_records=(record,),
        config=HumanReviewQueueConfig(),
        generated_at=now,
    )


def _build_blocked_queue_input(now: datetime) -> HumanReviewQueueInput:
    """Build a queue input that will produce a BLOCKED queue report."""
    record = HumanReviewSourceRecord(
        source_id="src-blocked-1",
        source_kind="issue",
        record_id="rec-blocked-1",
        title="Critical blocking issue",
        description="Blocking severity item.",
        state="blocked",
        severity="blocking",
        reason_codes=("blocking_severity",),
        artifact_ref="artifact://blocked-1",
        report_ref="report://blocked-1",
        generated_at=now,
    )
    return HumanReviewQueueInput(
        source_records=(record,),
        config=HumanReviewQueueConfig(),
        generated_at=now,
    )


def _build_orphaned_queue_input(now: datetime) -> HumanReviewQueueInput:
    """Build a queue input with an orphan related record reference.

    With the default non-strict config, the orphan issue stays DEGRADED rather
    than being promoted to BLOCKED.
    """
    record = HumanReviewSourceRecord(
        source_id="src-orphan-1",
        source_kind="issue",
        record_id="rec-orphan-1",
        title="Orphan reference item",
        description="References a missing related record.",
        state="open",
        severity="advisory",
        reason_codes=("orphan_related_record", "advisory_severity"),
        related_record_ids=("missing-related-id",),
        artifact_ref="artifact://orphan-1",
        report_ref="report://orphan-1",
        generated_at=now,
    )
    return HumanReviewQueueInput(
        source_records=(record,),
        config=HumanReviewQueueConfig(),
        generated_at=now,
    )


def _build_decision_log_input(
    queue_report: HumanReviewQueueReport,
    now: datetime,
    queue_entry_id: str | None = None,
    reason_codes: tuple[str, ...] | None = None,
    outcome: str | None = None,
) -> HumanReviewDecisionLogInput:
    """Build a decision log input matching the given queue report.

    The decision log ref mirrors the queue entry so that the consistency engine
    sees aligned state, priority, severity, and reason codes. When the queue
    entry is not_applicable, the decision outcome is not_applicable so the
    decision result state stays aligned; otherwise it falls back to
    accepted_for_audit_log.
    """
    queue_entry = queue_report.queue_entries[0] if queue_report.queue_entries else None
    qid = queue_entry_id if queue_entry_id is not None else (queue_entry.queue_entry_id if queue_entry else _QID)
    entry_state = queue_entry.entry_state if queue_entry else "queued"
    severity = queue_entry.severity if queue_entry else "info"
    priority = queue_entry.priority if queue_entry else "info"
    source_id = queue_entry.source_id if queue_entry else "src-1"
    source_kind = queue_entry.source_kind if queue_entry else "issue"
    record_id = queue_entry.record_id if queue_entry else "rec-1"
    entry_reason_codes = queue_entry.reason_codes if queue_entry else ("info_severity",)
    if outcome is None:
        outcome = (
            HumanReviewDecisionOutcome.NOT_APPLICABLE.value
            if entry_state.strip().lower() == "not_applicable"
            else HumanReviewDecisionOutcome.ACCEPTED_FOR_AUDIT_LOG.value
        )
    ref = HumanReviewQueueEntryRef(
        queue_entry_id=qid,
        source_id=source_id,
        source_kind=source_kind,
        record_id=record_id,
        entry_state=entry_state,
        priority=priority,
        severity=severity,
        reason_codes=entry_reason_codes if reason_codes is None else reason_codes,
        artifact_ref="artifact://decision-1",
        report_ref="report://decision-1",
        generated_at=now,
    )
    decision = HumanReviewDecisionRecord(
        decision_id="decision-ok-1",
        queue_entry_id=qid,
        reviewer="reviewer-1",
        decided_at=now,
        outcome=outcome,
        rationale="Accepted for audit log only."
        if outcome == HumanReviewDecisionOutcome.ACCEPTED_FOR_AUDIT_LOG.value
        else "Not applicable for audit log.",
        reason_codes=entry_reason_codes if reason_codes is None else reason_codes,
        artifact_ref="artifact://decision-1",
        report_ref="report://decision-1",
        generated_at=now,
    )
    return HumanReviewDecisionLogInput(
        queue_entry_refs=(ref,),
        decision_records=(decision,),
        config=HumanReviewDecisionLogConfig(),
        generated_at=now,
    )


def _build_degraded_decision_log_input(
    queue_report: HumanReviewQueueReport,
    now: datetime,
) -> HumanReviewDecisionLogInput:
    """Build a decision log input with an orphan decision to make it DEGRADED."""
    # Use a real queue entry that matches the queue report so that the valid
    # entry is LOGGED, while an extra orphan decision produces DEGRADED.
    valid_input = _build_decision_log_input(queue_report, now)
    ref = valid_input.queue_entry_refs[0]
    orphan_decision = HumanReviewDecisionRecord(
        decision_id="decision-orphan-1",
        queue_entry_id="unknown-queue-entry",
        reviewer="reviewer-1",
        decided_at=now,
        outcome=HumanReviewDecisionOutcome.ACCEPTED_FOR_AUDIT_LOG.value,
        rationale="Orphan decision.",
        reason_codes=("orphan_decision",),
        generated_at=now,
    )
    return HumanReviewDecisionLogInput(
        queue_entry_refs=(ref,),
        decision_records=(valid_input.decision_records[0], orphan_decision),
        config=HumanReviewDecisionLogConfig(),
        generated_at=now,
    )


def _build_blocked_decision_log_input(
    queue_report: HumanReviewQueueReport,
    now: datetime,
) -> HumanReviewDecisionLogInput:
    """Build a decision log input that produces a BLOCKED decision log report."""
    # Duplicate queue_entry_id triggers BLOCKED.
    ref1 = HumanReviewQueueEntryRef(
        queue_entry_id="duplicate-qid",
        source_id="src-1",
        source_kind="issue",
        record_id="rec-1",
        entry_state="open",
        priority="info",
        severity="info",
        reason_codes=("info_severity",),
        generated_at=now,
    )
    ref2 = HumanReviewQueueEntryRef(
        queue_entry_id="duplicate-qid",
        source_id="src-2",
        source_kind="issue",
        record_id="rec-2",
        entry_state="open",
        priority="info",
        severity="info",
        reason_codes=("info_severity",),
        generated_at=now,
    )
    return HumanReviewDecisionLogInput(
        queue_entry_refs=(ref1, ref2),
        decision_records=(),
        config=HumanReviewDecisionLogConfig(),
        generated_at=now,
    )


def _build_consistency_input(
    queue_report: HumanReviewQueueReport,
    decision_log_report: Any,
    now: datetime,
) -> HumanReviewDecisionLogConsistencyInput:
    """Build a consistency input from the two upstream reports."""
    return HumanReviewDecisionLogConsistencyInput(
        queue_report=queue_report,
        decision_log_report=decision_log_report,
        config=HumanReviewDecisionLogConsistencyConfig(),
        generated_at=now,
    )


def _build_bundle_input(
    queue_report: HumanReviewQueueReport,
    decision_log_report: Any,
    consistency_report: Any,
    now: datetime,
    strict: bool = False,
) -> HumanReviewAuditBundleInput:
    """Build the audit bundle input from the three upstream reports."""
    return HumanReviewAuditBundleInput(
        queue_report=queue_report,
        decision_log_report=decision_log_report,
        consistency_report=consistency_report,
        config=HumanReviewAuditBundleConfig(strict=strict),
        generated_at=now,
    )


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------


def _reason_code_values(obj: Any) -> tuple[str, ...]:
    """Return enum values as strings for comparison.

    Accepts an object with `reason_codes` or `upstream_reason_codes`, or a
    tuple of codes directly.
    """
    if isinstance(obj, tuple):
        codes = obj
    else:
        codes = getattr(obj, "upstream_reason_codes", None) or getattr(obj, "reason_codes", obj)
    return tuple(rc.value if hasattr(rc, "value") else str(rc) for rc in codes)


def _has_reason_code(obj: Any, code: HumanReviewAuditBundleReasonCode) -> bool:
    """Return True if the object's reason codes contain the given code value.

    Sections carry upstream reason codes in `upstream_reason_codes` while the
    report and issues use `reason_codes`.
    """
    codes = getattr(obj, "upstream_reason_codes", None) or getattr(obj, "reason_codes", ())
    return code.value in _reason_code_values(codes)


def _has_section_with_state(
    bundle: Any,
    kind: str,
    state: str,
) -> bool:
    """Return True if any section of kind has upstream_state == state."""
    return any(s.section_kind == kind and s.upstream_state == state for s in bundle.sections)


def test_ok_path(now: datetime) -> None:
    """OK path: queue, decision log, and consistency reports align."""
    queue_report = _build_ok_queue_report(now)
    assert queue_report.state == HumanReviewQueueState.OK

    decision_log_input = _build_decision_log_input(queue_report, now)
    decision_log_report = build_human_review_decision_log_report(decision_log_input)
    assert decision_log_report.state == HumanReviewDecisionLogState.OK

    consistency_input = _build_consistency_input(queue_report, decision_log_report, now)
    consistency_report = build_human_review_decision_log_consistency_report(consistency_input)
    assert consistency_report.state == HumanReviewDecisionLogConsistencyState.OK

    bundle_input = _build_bundle_input(queue_report, decision_log_report, consistency_report, now)
    bundle_report = build_human_review_audit_bundle(bundle_input)

    assert bundle_report.state == HumanReviewAuditBundleState.OK
    assert bundle_report.sections
    assert bundle_report.safety_flags.is_safe
    assert bundle_report.safety_flags.references_opaque
    assert bundle_report.safety_flags.no_trading_instructions
    assert bundle_report.safety_flags.no_executable_actions
    assert bundle_report.data_quality.section_count == 3
    assert any(s.section_kind == "queue" for s in bundle_report.sections)
    assert any(s.section_kind == "decision_log" for s in bundle_report.sections)
    assert any(s.section_kind == "consistency" for s in bundle_report.sections)
    assert _has_reason_code(bundle_report, HumanReviewAuditBundleReasonCode.OK)
    assert not any(
        _has_reason_code(bundle_report, code)
        for code in (
            HumanReviewAuditBundleReasonCode.UPSTREAM_DEGRADED,
            HumanReviewAuditBundleReasonCode.UPSTREAM_BLOCKED,
            HumanReviewAuditBundleReasonCode.UPSTREAM_NOT_APPLICABLE,
        )
    )

def test_degraded_path(now: datetime) -> None:
    """DEGRADED path: upstream consistency DEGRADED carries into audit bundle."""
    queue_input = _build_degraded_queue_input(now)
    queue_report = build_human_review_queue_report(queue_input)
    assert queue_report.state == HumanReviewQueueState.DEGRADED

    decision_log_input = _build_decision_log_input(queue_report, now)
    decision_log_report = build_human_review_decision_log_report(decision_log_input)
    assert decision_log_report.state == HumanReviewDecisionLogState.OK

    consistency_input = _build_consistency_input(queue_report, decision_log_report, now)
    consistency_report = build_human_review_decision_log_consistency_report(consistency_input)
    assert consistency_report.state == HumanReviewDecisionLogConsistencyState.DEGRADED

    bundle_input = _build_bundle_input(queue_report, decision_log_report, consistency_report, now)
    bundle_report = build_human_review_audit_bundle(bundle_input)

    assert bundle_report.state == HumanReviewAuditBundleState.DEGRADED
    assert _has_reason_code(
        bundle_report, HumanReviewAuditBundleReasonCode.UPSTREAM_DEGRADED
    )
    assert _has_reason_code(
        bundle_report, HumanReviewAuditBundleReasonCode.BUNDLE_DEGRADED
    )


def test_blocked_path_from_queue(now: datetime) -> None:
    """BLOCKED path: upstream queue BLOCKED carries into audit bundle."""
    queue_input = _build_blocked_queue_input(now)
    queue_report = build_human_review_queue_report(queue_input)
    assert queue_report.state == HumanReviewQueueState.BLOCKED

    qid = queue_report.queue_entries[0].queue_entry_id
    decision_log_input = _build_decision_log_input(queue_report, now, queue_entry_id=qid)
    decision_log_report = build_human_review_decision_log_report(decision_log_input)

    consistency_input = _build_consistency_input(queue_report, decision_log_report, now)
    consistency_report = build_human_review_decision_log_consistency_report(consistency_input)
    assert consistency_report.state == HumanReviewDecisionLogConsistencyState.BLOCKED

    bundle_input = _build_bundle_input(queue_report, decision_log_report, consistency_report, now)
    bundle_report = build_human_review_audit_bundle(bundle_input)

    assert bundle_report.state == HumanReviewAuditBundleState.BLOCKED
    assert _has_section_with_state(bundle_report, "queue", "blocked")
    assert _has_reason_code(bundle_report, HumanReviewAuditBundleReasonCode.UPSTREAM_BLOCKED)


def test_blocked_path_from_decision_log(now: datetime) -> None:
    """BLOCKED path: upstream decision log BLOCKED carries into audit bundle."""
    queue_report = _build_ok_queue_report(now)
    assert queue_report.state == HumanReviewQueueState.OK

    decision_log_input = _build_blocked_decision_log_input(queue_report, now)
    decision_log_report = build_human_review_decision_log_report(decision_log_input)
    assert decision_log_report.state == HumanReviewDecisionLogState.BLOCKED

    consistency_input = _build_consistency_input(queue_report, decision_log_report, now)
    consistency_report = build_human_review_decision_log_consistency_report(consistency_input)
    assert consistency_report.state == HumanReviewDecisionLogConsistencyState.BLOCKED

    bundle_input = _build_bundle_input(queue_report, decision_log_report, consistency_report, now)
    bundle_report = build_human_review_audit_bundle(bundle_input)

    assert bundle_report.state == HumanReviewAuditBundleState.BLOCKED


def test_not_applicable_path(now: datetime) -> None:
    """NOT_APPLICABLE path: all empty upstream inputs produce NOT_APPLICABLE bundle."""
    queue_input = HumanReviewQueueInput(source_records=(), generated_at=now)
    queue_report = build_human_review_queue_report(queue_input)
    assert queue_report.state == HumanReviewQueueState.NOT_APPLICABLE

    decision_log_input = HumanReviewDecisionLogInput(generated_at=now)
    decision_log_report = build_human_review_decision_log_report(decision_log_input)
    assert decision_log_report.state == HumanReviewDecisionLogState.NOT_APPLICABLE

    consistency_input = _build_consistency_input(queue_report, decision_log_report, now)
    consistency_report = build_human_review_decision_log_consistency_report(consistency_input)
    assert consistency_report.state == HumanReviewDecisionLogConsistencyState.NOT_APPLICABLE

    bundle_input = _build_bundle_input(queue_report, decision_log_report, consistency_report, now)
    bundle_report = build_human_review_audit_bundle(bundle_input)

    assert bundle_report.state == HumanReviewAuditBundleState.NOT_APPLICABLE
    assert bundle_report.sections == ()
    assert bundle_report.issues == ()


def test_orphaned_preservation(now: datetime) -> None:
    """ORPHANED preservation: upstream orphan behavior is carried into sections/issues."""
    queue_input = _build_orphaned_queue_input(now)
    queue_report = build_human_review_queue_report(queue_input)
    assert queue_report.state == HumanReviewQueueState.DEGRADED
    assert any(i.issue_type == "orphan_related_record" for i in queue_report.issues)

    decision_log_input = _build_decision_log_input(queue_report, now)
    decision_log_report = build_human_review_decision_log_report(decision_log_input)

    consistency_input = _build_consistency_input(queue_report, decision_log_report, now)
    consistency_report = build_human_review_decision_log_consistency_report(consistency_input)

    bundle_input = _build_bundle_input(queue_report, decision_log_report, consistency_report, now)
    bundle_report = build_human_review_audit_bundle(bundle_input)

    assert bundle_report.state == HumanReviewAuditBundleState.DEGRADED
    queue_section = next(s for s in bundle_report.sections if s.section_kind == "queue")
    assert any(i.issue_type == "orphan_related_record" for i in bundle_report.issues)
    # Verify the upstream queue report itself carried the orphan reason code; the
    # bundle section surfaces it via upstream_reason_codes.
    assert any(
        code.value == "orphan_related_record"
        for code in queue_report.reason_codes
    )
    assert queue_section.upstream_state == "degraded"


def test_strict_mode_promotion(now: datetime) -> None:
    """Strict bundle config promotes a DEGRADED upstream queue to BLOCKED."""
    # Build a non-strict queue so the queue engine itself reports DEGRADED.
    queue_input = _build_degraded_queue_input(now)
    queue_report = build_human_review_queue_report(queue_input)
    assert queue_report.state == HumanReviewQueueState.DEGRADED

    decision_log_input = _build_decision_log_input(
        queue_report, now, reason_codes=queue_report.queue_entries[0].reason_codes
    )
    decision_log_report = build_human_review_decision_log_report(decision_log_input)

    consistency_input = _build_consistency_input(queue_report, decision_log_report, now)
    consistency_report = build_human_review_decision_log_consistency_report(consistency_input)

    # Use strict bundle config to promote the DEGRADED upstream to BLOCKED.
    bundle_input = _build_bundle_input(
        queue_report, decision_log_report, consistency_report, now, strict=True
    )
    bundle_report = build_human_review_audit_bundle(bundle_input)

    assert bundle_report.state == HumanReviewAuditBundleState.BLOCKED
    # The upstream consistency report is still DEGRADED; strict mode elevates the
    # bundle aggregate state to BLOCKED while keeping the upstream reason code.
    assert _has_reason_code(
        bundle_report, HumanReviewAuditBundleReasonCode.UPSTREAM_DEGRADED
    )
    assert _has_reason_code(
        bundle_report, HumanReviewAuditBundleReasonCode.BUNDLE_DEGRADED
    )


# ---------------------------------------------------------------------------
# Writer safety / determinism / opaque refs
# ---------------------------------------------------------------------------


def _artifact_body_without_safety(output: str, safety_notice: str) -> str:
    """Return the artifact body with the safety notice removed."""
    body = output.replace(safety_notice, "")
    # Also remove upstream safety notices that appear in string values.
    from hunter.human_review_queue.models import SAFETY_NOTICE as QUEUE_SAFETY_NOTICE
    from hunter.human_review_decision_log.models import SAFETY_NOTICE as DECISION_SAFETY_NOTICE
    from hunter.human_review_decision_log_consistency.models import SAFETY_NOTICE as CONSISTENCY_SAFETY_NOTICE

    body = body.replace(QUEUE_SAFETY_NOTICE, "")
    body = body.replace(DECISION_SAFETY_NOTICE, "")
    body = body.replace(CONSISTENCY_SAFETY_NOTICE, "")
    return body


def _forbidden_phrases_found(output: str) -> list[str]:
    """Return any forbidden action phrases found outside allowed negation contexts."""
    body = _artifact_body_without_safety(output, BUNDLE_SAFETY_NOTICE)
    # Remove allowed negation phrases/safety flag names so that field names and
    # safety notices do not trigger false positives.
    for allowed in _ALLOWED_NEGATION_PHRASES:
        body = body.replace(allowed, "")
    body = body.lower()
    found = [phrase for phrase in _FORBIDDEN_ACTION_PHRASES if phrase in body]
    return found


@pytest.fixture
def ok_bundle(now: datetime) -> Any:
    """Build a bundle report for the OK path."""
    queue_report = _build_ok_queue_report(now)
    decision_log_input = _build_decision_log_input(queue_report, now)
    decision_log_report = build_human_review_decision_log_report(decision_log_input)
    consistency_input = _build_consistency_input(queue_report, decision_log_report, now)
    consistency_report = build_human_review_decision_log_consistency_report(consistency_input)
    bundle_input = _build_bundle_input(queue_report, decision_log_report, consistency_report, now)
    return build_human_review_audit_bundle(bundle_input)


def test_dict_output_is_deterministic(ok_bundle: Any) -> None:
    """Dict output is deterministic for identical inputs."""
    d1 = bundle_report_to_dict(ok_bundle)
    d2 = bundle_report_to_dict(ok_bundle)
    assert d1 == d2
    assert list(d1.keys()) == list(d2.keys())


def test_json_output_is_deterministic(ok_bundle: Any) -> None:
    """JSON text output is deterministic and parses back."""
    j1 = bundle_report_to_json(ok_bundle)
    j2 = bundle_report_to_json(ok_bundle)
    assert j1 == j2
    parsed = loads(j1)
    assert parsed["state"] == "ok"
    assert parsed["safety_notice"] == BUNDLE_SAFETY_NOTICE


def test_markdown_output_is_deterministic(ok_bundle: Any) -> None:
    """Markdown output is deterministic and starts with the safety notice."""
    m1 = bundle_report_to_markdown(ok_bundle)
    m2 = bundle_report_to_markdown(ok_bundle)
    assert m1 == m2
    assert m1.startswith("This bundle is a local, audit-only, human-audit research artifact.")


def test_json_no_forbidden_action_phrases(ok_bundle: Any) -> None:
    """JSON body contains no forbidden action phrases outside the safety notice."""
    text = bundle_report_to_json(ok_bundle)
    found = _forbidden_phrases_found(text)
    assert not found, f"Found forbidden phrases in JSON: {found}"


def test_markdown_no_forbidden_action_phrases(ok_bundle: Any) -> None:
    """Markdown body contains no forbidden action phrases outside the safety notice."""
    text = bundle_report_to_markdown(ok_bundle)
    found = _forbidden_phrases_found(text)
    assert not found, f"Found forbidden phrases in Markdown: {found}"


def test_opaque_refs_not_opened(ok_bundle: Any) -> None:
    """Opaque refs are preserved upstream and never opened in bundle output."""
    text = bundle_report_to_json(ok_bundle)
    # The bundle writer serializes sections/summaries, not the upstream refs
    # themselves, so it must never emit opened/traversed protocols.
    assert "file://" not in text
    assert "http://" not in text
    assert "https://" not in text
    assert "ftp://" not in text

    # The Markdown writer also never opens refs.
    markdown = bundle_report_to_markdown(ok_bundle)
    assert "file://" not in markdown
    assert "http://" not in markdown
    assert "https://" not in markdown
    assert "ftp://" not in markdown

    # Verify the upstream source reports retain opaque refs unopened.
    queue_section = next(s for s in ok_bundle.sections if s.section_kind == "queue")
    assert "queue-ok" == queue_section.upstream_report_id
    decision_section = next(s for s in ok_bundle.sections if s.section_kind == "decision_log")
    assert decision_section.upstream_report_id


def test_no_filesystem_or_network_in_writer(ok_bundle: Any, tmp_path: Any, monkeypatch: Any) -> None:
    """Writer uses no filesystem or network calls."""
    import builtins

    original_open = builtins.open
    open_calls: list[tuple[Any, ...]] = []

    def patched_open(*args: Any, **kwargs: Any) -> Any:
        open_calls.append((args, kwargs))
        return original_open(*args, **kwargs)

    monkeypatch.setattr(builtins, "open", patched_open)

    # These pure functions must not touch the filesystem.
    bundle_report_to_dict(ok_bundle)
    bundle_report_to_json(ok_bundle)
    bundle_report_to_markdown(ok_bundle)

    assert open_calls == [], f"Writer unexpectedly opened files: {open_calls}"


def test_section_and_issue_ordering_deterministic(now: datetime) -> None:
    """Repeated end-to-end calls produce identical section/issue ordering."""
    def build() -> Any:
        queue_report = _build_ok_queue_report(now)
        decision_log_input = _build_decision_log_input(queue_report, now)
        decision_log_report = build_human_review_decision_log_report(decision_log_input)
        consistency_input = _build_consistency_input(queue_report, decision_log_report, now)
        consistency_report = build_human_review_decision_log_consistency_report(consistency_input)
        bundle_input = _build_bundle_input(queue_report, decision_log_report, consistency_report, now)
        return build_human_review_audit_bundle(bundle_input)

    bundle1 = build()
    bundle2 = build()
    d1 = bundle_report_to_dict(bundle1)
    d2 = bundle_report_to_dict(bundle2)
    assert d1 == d2


def test_bundle_data_quality_counters_populated(now: datetime) -> None:
    """Bundle-level data quality counters are populated from upstream reports."""
    queue_report = _build_ok_queue_report(now)
    decision_log_input = _build_decision_log_input(queue_report, now)
    decision_log_report = build_human_review_decision_log_report(decision_log_input)
    consistency_input = _build_consistency_input(queue_report, decision_log_report, now)
    consistency_report = build_human_review_decision_log_consistency_report(consistency_input)
    bundle_input = _build_bundle_input(queue_report, decision_log_report, consistency_report, now)
    bundle_report = build_human_review_audit_bundle(bundle_input)

    dq = bundle_report_to_dict(bundle_report)["data_quality"]
    assert dq["section_count"] == 3
    assert dq["queue_entry_count"] >= 1
    assert dq["decision_result_count"] >= 1
    assert dq["consistency_cross_reference_count"] >= 1


def test_inputs_not_mutated_by_end_to_end(now: datetime) -> None:
    """Upstream inputs are not mutated by the engines or writer."""
    queue_input = _build_degraded_queue_input(now)
    original_queue_input_ids = [id(r) for r in queue_input.source_records]
    queue_report = build_human_review_queue_report(queue_input)
    assert [id(r) for r in queue_input.source_records] == original_queue_input_ids

    decision_log_input = _build_degraded_decision_log_input(queue_report, now)
    original_decision_log_ids = [id(r) for r in decision_log_input.decision_records]
    decision_log_report = build_human_review_decision_log_report(decision_log_input)
    assert [id(r) for r in decision_log_input.decision_records] == original_decision_log_ids

    consistency_input = _build_consistency_input(queue_report, decision_log_report, now)
    consistency_report = build_human_review_decision_log_consistency_report(consistency_input)
    bundle_input = _build_bundle_input(queue_report, decision_log_report, consistency_report, now)
    bundle_report = build_human_review_audit_bundle(bundle_input)

    bundle_report_to_dict(bundle_report)
    bundle_report_to_json(bundle_report)
    bundle_report_to_markdown(bundle_report)

    assert [id(r) for r in queue_input.source_records] == original_queue_input_ids
    assert [id(r) for r in decision_log_input.decision_records] == original_decision_log_ids
