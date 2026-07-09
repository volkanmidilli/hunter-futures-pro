"""In-memory engine for hunter.human_review_decision_log_consistency package.

MVP-42 — Local Research Human Review Decision Log Cross-Artifact Consistency.

The engine receives only caller-provided in-memory reports. It never inspects the
filesystem, imports prior package engines, or traverses any path or reference
string. It never emits executable remediation actions, shell commands, code
patches, infrastructure changes, or task assignments.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from hashlib import sha256
from json import dumps
from typing import Any

from hunter.human_review_decision_log.models import HumanReviewDecisionLogReport
from hunter.human_review_queue.models import HumanReviewQueueReport

from hunter.human_review_decision_log_consistency.models import (
    FORBIDDEN_HUMAN_REVIEW_DECISION_LOG_CONSISTENCY_TERMS,
    HumanReviewDecisionLogConsistencyConfig,
    HumanReviewDecisionLogConsistencyCrossReference,
    HumanReviewDecisionLogConsistencyDataQuality,
    HumanReviewDecisionLogConsistencyIssue,
    HumanReviewDecisionLogConsistencyIssueType,
    HumanReviewDecisionLogConsistencyReasonCode,
    HumanReviewDecisionLogConsistencyReport,
    HumanReviewDecisionLogConsistencySafetyFlags,
    HumanReviewDecisionLogConsistencySeverity,
    HumanReviewDecisionLogConsistencyState,
    SAFETY_NOTICE,
    _check_forbidden_mapping,
    _has_forbidden_term,
    has_unsafe_human_review_decision_log_consistency_content,
)


# ---------------------------------------------------------------------------
# Hashing helpers
# ---------------------------------------------------------------------------

def _canonical_json(value: Any) -> str:
    """Return a deterministic canonical JSON representation."""
    return dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_hex(value: str) -> str:
    """Return the full SHA-256 hex digest of a string."""
    return sha256(value.encode("utf-8")).hexdigest()


def _sha256_hex_16(value: str) -> str:
    """Return the first 16 characters of a SHA-256 hex digest."""
    return _sha256_hex(value)[:16]


def _resolve_generated_at(input: "HumanReviewDecisionLogConsistencyInput") -> datetime:
    """Return the effective generated_at timestamp."""
    return input.generated_at if input.generated_at is not None else datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Report ID helpers
# ---------------------------------------------------------------------------

def _build_report_id(
    input: "HumanReviewDecisionLogConsistencyInput",
    generated_at: datetime,
    matched_queue_entry_ids: tuple[str, ...],
) -> str:
    """Build a deterministic report_id from sorted IDs and metadata."""
    payload = {
        "queue_report_id": str(input.queue_report.report_id),
        "decision_log_report_id": str(input.decision_log_report.report_id),
        "matched_queue_entry_ids": sorted(set(str(qid).strip() for qid in matched_queue_entry_ids if qid)),
        "project_version": input.project_version,
        "generated_at": generated_at.isoformat(),
    }
    return _sha256_hex(_canonical_json(payload))


def _build_blocked_report_id(
    input: "HumanReviewDecisionLogConsistencyInput",
    generated_at: datetime,
    reason_code: HumanReviewDecisionLogConsistencyReasonCode,
    notes: str,
) -> str:
    """Build a deterministic blocked report_id."""
    payload = {
        "state": HumanReviewDecisionLogConsistencyState.BLOCKED.value,
        "queue_report_id": str(input.queue_report.report_id),
        "decision_log_report_id": str(input.decision_log_report.report_id),
        "project_version": input.project_version,
        "generated_at": generated_at.isoformat(),
        "reason_code": reason_code.value,
        "notes": notes,
    }
    return _sha256_hex(_canonical_json(payload))


def _build_cross_reference_id(
    queue_entry_id: str,
    decision_log_queue_entry_id: str,
    match_status: str,
    generated_at: datetime,
) -> str:
    """Build a deterministic cross_reference_id."""
    payload = {
        "queue_entry_id": str(queue_entry_id).strip(),
        "decision_log_queue_entry_id": str(decision_log_queue_entry_id).strip(),
        "match_status": str(match_status).strip(),
        "generated_at": generated_at.isoformat(),
    }
    return _sha256_hex_16(_canonical_json(payload))


def _build_issue_id(issue: HumanReviewDecisionLogConsistencyIssue) -> str:
    """Build a deterministic issue_id from issue content."""
    payload = {
        "issue_type": issue.issue_type,
        "severity": issue.severity,
        "reason_codes": sorted(issue.reason_codes),
        "source_id": issue.source_id,
        "target_id": issue.target_id,
        "queue_entry_id": issue.queue_entry_id,
        "decision_log_queue_entry_id": issue.decision_log_queue_entry_id,
        "title": issue.title,
        "description": issue.description,
    }
    return _sha256_hex_16(_canonical_json(payload))


# ---------------------------------------------------------------------------
# Issue factory
# ---------------------------------------------------------------------------

def _make_issue(
    *,
    issue_type: HumanReviewDecisionLogConsistencyIssueType,
    severity: HumanReviewDecisionLogConsistencySeverity,
    reason_codes: tuple[str, ...],
    title: str,
    description: str,
    source_id: str = "",
    target_id: str = "",
    queue_entry_id: str = "",
    decision_log_queue_entry_id: str = "",
    generated_at: datetime,
) -> HumanReviewDecisionLogConsistencyIssue:
    """Create an issue with a deterministic ID."""
    issue = HumanReviewDecisionLogConsistencyIssue(
        issue_type=issue_type.value,
        severity=severity.value,
        reason_codes=reason_codes,
        title=title,
        description=description,
        source_id=source_id,
        target_id=target_id,
        queue_entry_id=queue_entry_id,
        decision_log_queue_entry_id=decision_log_queue_entry_id,
        generated_at=generated_at,
    )
    return replace(issue, issue_id=_build_issue_id(issue))


# ---------------------------------------------------------------------------
# Safety detection
# ---------------------------------------------------------------------------

def _is_input_blocked(
    queue_report: HumanReviewQueueReport,
    decision_log_report: HumanReviewDecisionLogReport,
) -> tuple[bool, HumanReviewDecisionLogConsistencyReasonCode, str]:
    """Check if either input report is already blocked or unsafe."""
    from hunter.human_review_decision_log.models import HumanReviewDecisionLogState
    from hunter.human_review_queue.models import HumanReviewQueueState

    if queue_report.state == HumanReviewQueueState.BLOCKED:
        return True, HumanReviewDecisionLogConsistencyReasonCode.INPUT_BLOCKED, "Queue report is BLOCKED."
    if decision_log_report.state == HumanReviewDecisionLogState.BLOCKED:
        return True, HumanReviewDecisionLogConsistencyReasonCode.INPUT_BLOCKED, "Decision log report is BLOCKED."
    if not queue_report.safety_flags.is_safe:
        if queue_report.safety_flags.has_unsafe_content:
            return True, HumanReviewDecisionLogConsistencyReasonCode.UNSAFE_CONTENT, "Queue report has unsafe content."
        return True, HumanReviewDecisionLogConsistencyReasonCode.FORBIDDEN_TERM_PRESENT, "Queue report has forbidden terms."
    if not decision_log_report.safety_flags.is_safe:
        if decision_log_report.safety_flags.has_unsafe_content:
            return True, HumanReviewDecisionLogConsistencyReasonCode.UNSAFE_CONTENT, "Decision log report has unsafe content."
        return True, HumanReviewDecisionLogConsistencyReasonCode.FORBIDDEN_TERM_PRESENT, "Decision log report has forbidden terms."
    return False, HumanReviewDecisionLogConsistencyReasonCode.OK, ""


def _has_unsafe_consistency_content(input: "HumanReviewDecisionLogConsistencyInput") -> bool:
    """Return True if any metadata field contains unsafe non-string values."""
    if has_unsafe_human_review_decision_log_consistency_content(dict(input.metadata)):
        return True
    for link in input.links:
        if has_unsafe_human_review_decision_log_consistency_content(dict(link.metadata)):
            return True
        for text in (link.link_id, link.queue_entry_id, link.decision_log_queue_entry_id, link.link_type):
            if has_unsafe_human_review_decision_log_consistency_content(text):
                return True
    return False


def _has_forbidden_consistency_terms(input: "HumanReviewDecisionLogConsistencyInput") -> bool:
    """Return True if any text field or metadata contains forbidden terms."""
    if _check_forbidden_mapping(input.metadata, FORBIDDEN_HUMAN_REVIEW_DECISION_LOG_CONSISTENCY_TERMS):
        return True
    for link in input.links:
        for text in (link.link_id, link.queue_entry_id, link.decision_log_queue_entry_id, link.link_type):
            if text and _has_forbidden_term(text, FORBIDDEN_HUMAN_REVIEW_DECISION_LOG_CONSISTENCY_TERMS):
                return True
        if _check_forbidden_mapping(link.metadata, FORBIDDEN_HUMAN_REVIEW_DECISION_LOG_CONSISTENCY_TERMS):
            return True
    return False


# ---------------------------------------------------------------------------
# Cross-reference building
# ---------------------------------------------------------------------------

def _build_cross_references(
    queue_report: HumanReviewQueueReport,
    decision_log_report: HumanReviewDecisionLogReport,
    generated_at: datetime,
) -> tuple[HumanReviewDecisionLogConsistencyCrossReference, ...]:
    """Build cross-references between queue entries and decision log refs."""
    queue_entries_by_id = {entry.queue_entry_id.strip(): entry for entry in queue_report.queue_entries}
    decision_refs_by_id = {ref.queue_entry_id.strip(): ref for ref in decision_log_report.queue_entry_refs}
    decision_results_by_id = {
        result.queue_entry_id.strip(): result for result in decision_log_report.decision_results
    }

    queue_ids = set(queue_entries_by_id.keys())
    decision_ids = set(decision_refs_by_id.keys())
    all_ids = sorted(queue_ids | decision_ids)

    cross_references: list[HumanReviewDecisionLogConsistencyCrossReference] = []
    for qid in all_ids:
        queue_entry = queue_entries_by_id.get(qid)
        decision_ref = decision_refs_by_id.get(qid)
        decision_result = decision_results_by_id.get(qid)

        if queue_entry and decision_ref:
            match_status = "matched"
            decision_state = decision_result.decision_state if decision_result else decision_ref.entry_state
            severity = decision_result.severity if decision_result else decision_ref.severity
            reason_codes = decision_result.reason_codes if decision_result else decision_ref.reason_codes
            rationale = "Queue entry and decision log ref are matched."
        elif queue_entry:
            match_status = "orphan_queue"
            decision_state = ""
            severity = "info"
            reason_codes = ()
            rationale = "Queue entry has no corresponding decision log ref."
        else:
            match_status = "orphan_decision_log"
            decision_state = decision_result.decision_state if decision_result else ""
            severity = decision_result.severity if decision_result else "info"
            reason_codes = decision_result.reason_codes if decision_result else ()
            rationale = "Decision log ref has no corresponding queue entry."

        cross_ref = HumanReviewDecisionLogConsistencyCrossReference(
            cross_reference_id="",
            queue_entry_id=qid if queue_entry else "",
            decision_log_queue_entry_id=qid if decision_ref else "",
            queue_entry_state=queue_entry.entry_state if queue_entry else "",
            decision_log_result_state=decision_state,
            match_status=match_status,
            severity=severity,
            reason_codes=reason_codes,
            rationale=rationale,
            generated_at=generated_at,
        )
        cross_references.append(
            replace(
                cross_ref,
                cross_reference_id=_build_cross_reference_id(
                    cross_ref.queue_entry_id,
                    cross_ref.decision_log_queue_entry_id,
                    cross_ref.match_status,
                    generated_at,
                ),
            )
        )

    return tuple(sorted(cross_references, key=lambda cr: cr.cross_reference_id))


# ---------------------------------------------------------------------------
# Issue detection
# ---------------------------------------------------------------------------

def _detect_missing_decision_log_refs(
    cross_references: tuple[HumanReviewDecisionLogConsistencyCrossReference, ...],
    config: HumanReviewDecisionLogConsistencyConfig,
    generated_at: datetime,
) -> tuple[HumanReviewDecisionLogConsistencyIssue, ...]:
    """Detect queue entries that expect a decision but have no decision log ref."""
    issues: list[HumanReviewDecisionLogConsistencyIssue] = []
    for cr in cross_references:
        if cr.match_status != "orphan_queue":
            continue
        if not config.expects_decision(cr.queue_entry_state):
            continue
        issues.append(
            _make_issue(
                issue_type=HumanReviewDecisionLogConsistencyIssueType.MISSING_DECISION_LOG_REF,
                severity=HumanReviewDecisionLogConsistencySeverity.ADVISORY,
                reason_codes=(HumanReviewDecisionLogConsistencyReasonCode.MISSING_DECISION_LOG_REF.value,),
                title="Missing decision log ref",
                description=(
                    f"Queue entry {cr.queue_entry_id!r} expects a decision but has no "
                    f"corresponding decision log ref."
                ),
                queue_entry_id=cr.queue_entry_id,
                generated_at=generated_at,
            )
        )
    return tuple(issues)


def _detect_orphan_decision_log_refs(
    cross_references: tuple[HumanReviewDecisionLogConsistencyCrossReference, ...],
    generated_at: datetime,
) -> tuple[HumanReviewDecisionLogConsistencyIssue, ...]:
    """Detect decision log refs with no matching queue entry."""
    issues: list[HumanReviewDecisionLogConsistencyIssue] = []
    for cr in cross_references:
        if cr.match_status != "orphan_decision_log":
            continue
        issues.append(
            _make_issue(
                issue_type=HumanReviewDecisionLogConsistencyIssueType.ORPHAN_DECISION_LOG_REF,
                severity=HumanReviewDecisionLogConsistencySeverity.ADVISORY,
                reason_codes=(HumanReviewDecisionLogConsistencyReasonCode.ORPHAN_DECISION_LOG_REF.value,),
                title="Orphan decision log ref",
                description=(
                    f"Decision log ref {cr.decision_log_queue_entry_id!r} has no corresponding "
                    f"queue entry."
                ),
                decision_log_queue_entry_id=cr.decision_log_queue_entry_id,
                generated_at=generated_at,
            )
        )
    return tuple(issues)


def _detect_mismatched_fields(
    cross_references: tuple[HumanReviewDecisionLogConsistencyCrossReference, ...],
    queue_report: HumanReviewQueueReport,
    decision_log_report: HumanReviewDecisionLogReport,
    generated_at: datetime,
) -> tuple[HumanReviewDecisionLogConsistencyIssue, ...]:
    """Detect mismatched state, priority, severity, and reason codes."""
    queue_entries_by_id = {entry.queue_entry_id.strip(): entry for entry in queue_report.queue_entries}
    decision_results_by_id = {
        result.queue_entry_id.strip(): result for result in decision_log_report.decision_results
    }

    issues: list[HumanReviewDecisionLogConsistencyIssue] = []
    for cr in cross_references:
        if cr.match_status != "matched":
            continue
        queue_entry = queue_entries_by_id.get(cr.queue_entry_id)
        decision_result = decision_results_by_id.get(cr.queue_entry_id)
        if queue_entry is None or decision_result is None:
            continue

        # State mismatch
        if queue_entry.entry_state.strip().lower() != decision_result.decision_state.strip().lower():
            issues.append(
                _make_issue(
                    issue_type=HumanReviewDecisionLogConsistencyIssueType.MISMATCHED_QUEUE_STATE,
                    severity=HumanReviewDecisionLogConsistencySeverity.ADVISORY,
                    reason_codes=(HumanReviewDecisionLogConsistencyReasonCode.MISMATCHED_QUEUE_STATE.value,),
                    title="Mismatched queue state",
                    description=(
                        f"Queue entry {cr.queue_entry_id!r} state {queue_entry.entry_state!r} "
                        f"does not match decision log result state {decision_result.decision_state!r}."
                    ),
                    queue_entry_id=cr.queue_entry_id,
                    generated_at=generated_at,
                )
            )

        # Priority mismatch (queue priority vs decision log result severity)
        if queue_entry.priority.strip().lower() != decision_result.severity.strip().lower():
            issues.append(
                _make_issue(
                    issue_type=HumanReviewDecisionLogConsistencyIssueType.MISMATCHED_QUEUE_PRIORITY,
                    severity=HumanReviewDecisionLogConsistencySeverity.ADVISORY,
                    reason_codes=(HumanReviewDecisionLogConsistencyReasonCode.MISMATCHED_QUEUE_PRIORITY.value,),
                    title="Mismatched queue priority",
                    description=(
                        f"Queue entry {cr.queue_entry_id!r} priority {queue_entry.priority!r} "
                        f"does not match decision log result severity {decision_result.severity!r}."
                    ),
                    queue_entry_id=cr.queue_entry_id,
                    generated_at=generated_at,
                )
            )

        # Severity mismatch (queue severity vs decision log result severity)
        if queue_entry.severity.strip().lower() != decision_result.severity.strip().lower():
            issues.append(
                _make_issue(
                    issue_type=HumanReviewDecisionLogConsistencyIssueType.MISMATCHED_QUEUE_SEVERITY,
                    severity=HumanReviewDecisionLogConsistencySeverity.ADVISORY,
                    reason_codes=(HumanReviewDecisionLogConsistencyReasonCode.MISMATCHED_QUEUE_SEVERITY.value,),
                    title="Mismatched queue severity",
                    description=(
                        f"Queue entry {cr.queue_entry_id!r} severity {queue_entry.severity!r} "
                        f"does not match decision log result severity {decision_result.severity!r}."
                    ),
                    queue_entry_id=cr.queue_entry_id,
                    generated_at=generated_at,
                )
            )

        # Reason codes mismatch
        queue_reasons = {r.strip().lower() for r in queue_entry.reason_codes if r.strip()}
        decision_reasons = {r.strip().lower() for r in decision_result.reason_codes if r.strip()}
        if queue_reasons and queue_reasons != decision_reasons:
            issues.append(
                _make_issue(
                    issue_type=HumanReviewDecisionLogConsistencyIssueType.MISMATCHED_QUEUE_REASON_CODES,
                    severity=HumanReviewDecisionLogConsistencySeverity.ADVISORY,
                    reason_codes=(HumanReviewDecisionLogConsistencyReasonCode.MISMATCHED_QUEUE_REASON_CODES.value,),
                    title="Mismatched queue reason codes",
                    description=(
                        f"Queue entry {cr.queue_entry_id!r} reason codes {sorted(queue_reasons)} "
                        f"do not match decision log result reason codes {sorted(decision_reasons)}."
                    ),
                    queue_entry_id=cr.queue_entry_id,
                    generated_at=generated_at,
                )
            )

    return tuple(issues)


def _detect_inconsistent_result_states(
    cross_references: tuple[HumanReviewDecisionLogConsistencyCrossReference, ...],
    queue_report: HumanReviewQueueReport,
    decision_log_report: HumanReviewDecisionLogReport,
    config: HumanReviewDecisionLogConsistencyConfig,
    generated_at: datetime,
) -> tuple[HumanReviewDecisionLogConsistencyIssue, ...]:
    """Detect inconsistent ORPHANED, MISSING, and BLOCKED result states."""
    queue_entries_by_id = {entry.queue_entry_id.strip(): entry for entry in queue_report.queue_entries}
    decision_results_by_id = {
        result.queue_entry_id.strip(): result for result in decision_log_report.decision_results
    }

    issues: list[HumanReviewDecisionLogConsistencyIssue] = []
    for cr in cross_references:
        if cr.match_status != "matched":
            continue
        queue_entry = queue_entries_by_id.get(cr.queue_entry_id)
        decision_result = decision_results_by_id.get(cr.queue_entry_id)
        if queue_entry is None or decision_result is None:
            continue

        decision_state = decision_result.decision_state.strip().lower()
        queue_state = queue_entry.entry_state.strip().lower()

        # INCONSISTENT_ORPHAN_STATUS: ORPHANED result but queue entry exists
        if decision_state == "orphaned":
            issues.append(
                _make_issue(
                    issue_type=HumanReviewDecisionLogConsistencyIssueType.INCONSISTENT_ORPHAN_STATUS,
                    severity=HumanReviewDecisionLogConsistencySeverity.ADVISORY,
                    reason_codes=(HumanReviewDecisionLogConsistencyReasonCode.INCONSISTENT_ORPHAN_STATUS.value,),
                    title="Inconsistent orphan status",
                    description=(
                        f"Decision log result for queue entry {cr.queue_entry_id!r} is ORPHANED "
                        f"but the queue entry exists."
                    ),
                    queue_entry_id=cr.queue_entry_id,
                    generated_at=generated_at,
                )
            )

        # INCONSISTENT_MISSING_STATUS: MISSING result but queue entry expects a decision
        if decision_state == "missing" and config.expects_decision(queue_entry.entry_state):
            issues.append(
                _make_issue(
                    issue_type=HumanReviewDecisionLogConsistencyIssueType.INCONSISTENT_MISSING_STATUS,
                    severity=HumanReviewDecisionLogConsistencySeverity.ADVISORY,
                    reason_codes=(HumanReviewDecisionLogConsistencyReasonCode.INCONSISTENT_MISSING_STATUS.value,),
                    title="Inconsistent missing status",
                    description=(
                        f"Decision log result for queue entry {cr.queue_entry_id!r} is MISSING "
                        f"but the queue entry state {queue_entry.entry_state!r} expects a decision."
                    ),
                    queue_entry_id=cr.queue_entry_id,
                    generated_at=generated_at,
                )
            )

        # INCONSISTENT_BLOCKED_STATUS: BLOCKED result but queue not blocked
        if decision_state == "blocked" and queue_state != "blocked":
            issues.append(
                _make_issue(
                    issue_type=HumanReviewDecisionLogConsistencyIssueType.INCONSISTENT_BLOCKED_STATUS,
                    severity=HumanReviewDecisionLogConsistencySeverity.ADVISORY,
                    reason_codes=(HumanReviewDecisionLogConsistencyReasonCode.INCONSISTENT_BLOCKED_STATUS.value,),
                    title="Inconsistent blocked status",
                    description=(
                        f"Decision log result for queue entry {cr.queue_entry_id!r} is BLOCKED "
                        f"but the queue entry state is {queue_entry.entry_state!r}."
                    ),
                    queue_entry_id=cr.queue_entry_id,
                    generated_at=generated_at,
                )
            )

    return tuple(issues)


# ---------------------------------------------------------------------------
# Aggregate state
# ---------------------------------------------------------------------------

def _compute_aggregate_state(
    issues: tuple[HumanReviewDecisionLogConsistencyIssue, ...],
    config: HumanReviewDecisionLogConsistencyConfig,
) -> HumanReviewDecisionLogConsistencyState:
    """Compute the aggregate report state from issues."""
    has_blocking = any(
        issue.severity == HumanReviewDecisionLogConsistencySeverity.BLOCKING.value for issue in issues
    )
    has_advisory = any(
        issue.severity == HumanReviewDecisionLogConsistencySeverity.ADVISORY.value for issue in issues
    )

    if has_blocking:
        return HumanReviewDecisionLogConsistencyState.BLOCKED
    if has_advisory:
        if config.strict:
            return HumanReviewDecisionLogConsistencyState.BLOCKED
        return HumanReviewDecisionLogConsistencyState.DEGRADED
    return HumanReviewDecisionLogConsistencyState.OK


# ---------------------------------------------------------------------------
# Data quality
# ---------------------------------------------------------------------------

def _build_data_quality(
    cross_references: tuple[HumanReviewDecisionLogConsistencyCrossReference, ...],
    issues: tuple[HumanReviewDecisionLogConsistencyIssue, ...],
    queue_report: HumanReviewQueueReport,
    decision_log_report: HumanReviewDecisionLogReport,
    unsafe: bool,
    forbidden: bool,
) -> HumanReviewDecisionLogConsistencyDataQuality:
    """Build the data quality summary."""
    matched = sum(1 for cr in cross_references if cr.match_status == "matched")
    orphan_queue = sum(1 for cr in cross_references if cr.match_status == "orphan_queue")
    orphan_decision_log = sum(1 for cr in cross_references if cr.match_status == "orphan_decision_log")
    mismatched = sum(1 for cr in cross_references if cr.match_status == "mismatched")

    blocking = sum(1 for i in issues if i.severity == HumanReviewDecisionLogConsistencySeverity.BLOCKING.value)
    advisory = sum(1 for i in issues if i.severity == HumanReviewDecisionLogConsistencySeverity.ADVISORY.value)
    info = sum(1 for i in issues if i.severity == HumanReviewDecisionLogConsistencySeverity.INFO.value)

    return HumanReviewDecisionLogConsistencyDataQuality(
        total_queue_entries=len(queue_report.queue_entries),
        total_decision_log_refs=len(decision_log_report.queue_entry_refs),
        matched_refs=matched,
        orphan_queue_entries=orphan_queue,
        orphan_decision_log_refs=orphan_decision_log,
        mismatched_refs=mismatched,
        blocking_issues=blocking,
        advisory_issues=advisory,
        info_findings=info,
        unsafe_content_count=1 if unsafe else 0,
        forbidden_term_count=1 if forbidden else 0,
    )


# ---------------------------------------------------------------------------
# Reason codes
# ---------------------------------------------------------------------------

def _build_reason_codes(
    state: HumanReviewDecisionLogConsistencyState,
    issues: tuple[HumanReviewDecisionLogConsistencyIssue, ...],
) -> tuple[HumanReviewDecisionLogConsistencyReasonCode, ...]:
    """Build deterministic report-level reason codes."""
    codes: set[str] = set()

    if state == HumanReviewDecisionLogConsistencyState.NOT_APPLICABLE:
        codes.add(HumanReviewDecisionLogConsistencyReasonCode.NOT_APPLICABLE.value)
    elif state == HumanReviewDecisionLogConsistencyState.OK:
        codes.add(HumanReviewDecisionLogConsistencyReasonCode.OK.value)
    elif state == HumanReviewDecisionLogConsistencyState.DEGRADED:
        codes.add(HumanReviewDecisionLogConsistencyReasonCode.CONSISTENCY_DEGRADED.value)
    elif state == HumanReviewDecisionLogConsistencyState.BLOCKED:
        codes.add(HumanReviewDecisionLogConsistencyReasonCode.SAFETY_BLOCKED.value)

    for issue in issues:
        for code in issue.reason_codes:
            codes.add(code)

    ordered = [code for code in HumanReviewDecisionLogConsistencyReasonCode if code.value in codes]
    return tuple(ordered)


# ---------------------------------------------------------------------------
# Blocked report constructor
# ---------------------------------------------------------------------------

def _blocked_report(
    input: "HumanReviewDecisionLogConsistencyInput",
    generated_at: datetime,
    reason_code: HumanReviewDecisionLogConsistencyReasonCode,
    notes: str,
) -> HumanReviewDecisionLogConsistencyReport:
    """Return a minimal blocked consistency report."""
    unsafe = reason_code == HumanReviewDecisionLogConsistencyReasonCode.UNSAFE_CONTENT
    forbidden = reason_code == HumanReviewDecisionLogConsistencyReasonCode.FORBIDDEN_TERM_PRESENT
    safety_flags = HumanReviewDecisionLogConsistencySafetyFlags(
        is_safe=not (unsafe or forbidden),
        has_unsafe_content=unsafe,
        has_forbidden_terms=forbidden,
    )
    return HumanReviewDecisionLogConsistencyReport(
        report_id=_build_blocked_report_id(input, generated_at, reason_code, notes),
        generated_at=generated_at,
        state=HumanReviewDecisionLogConsistencyState.BLOCKED,
        project_version=input.project_version,
        queue_report_id=input.queue_report.report_id,
        decision_log_report_id=input.decision_log_report.report_id,
        cross_references=(),
        issues=(),
        data_quality=HumanReviewDecisionLogConsistencyDataQuality(
            unsafe_content_count=1 if unsafe else 0,
            forbidden_term_count=1 if forbidden else 0,
        ),
        safety_flags=safety_flags,
        reason_codes=(reason_code,),
        safety_notice=SAFETY_NOTICE,
        metadata=input.metadata,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Public engine function
# ---------------------------------------------------------------------------

def build_human_review_decision_log_consistency_report(
    input: HumanReviewDecisionLogConsistencyInput,
    config: HumanReviewDecisionLogConsistencyConfig | None = None,
) -> HumanReviewDecisionLogConsistencyReport:
    """Build a deterministic cross-artifact consistency report."""
    if config is None:
        config = input.config

    generated_at = _resolve_generated_at(input)

    # Safety scan (fail-closed): carry forward blocked inputs before empty check.
    input_blocked, reason_code, notes = _is_input_blocked(
        input.queue_report, input.decision_log_report
    )
    if input_blocked:
        return _blocked_report(input, generated_at, reason_code, notes)

    unsafe = _has_unsafe_consistency_content(input)
    if unsafe:
        return _blocked_report(
            input,
            generated_at,
            HumanReviewDecisionLogConsistencyReasonCode.UNSAFE_CONTENT,
            "Report blocked due to unsafe content in caller-provided consistency input.",
        )

    forbidden = _has_forbidden_consistency_terms(input)
    if forbidden:
        return _blocked_report(
            input,
            generated_at,
            HumanReviewDecisionLogConsistencyReasonCode.FORBIDDEN_TERM_PRESENT,
            "Report blocked due to forbidden action terms in caller-provided consistency input.",
        )

    # Empty input -> deterministic NOT_APPLICABLE report.
    if not input.queue_report.queue_entries and not input.decision_log_report.queue_entry_refs:
        if config.empty_input_is_not_applicable:
            report_id = _build_report_id(input, generated_at, ())
            return HumanReviewDecisionLogConsistencyReport(
                report_id=report_id,
                generated_at=generated_at,
                state=HumanReviewDecisionLogConsistencyState.NOT_APPLICABLE,
                project_version=input.project_version,
                queue_report_id=input.queue_report.report_id,
                decision_log_report_id=input.decision_log_report.report_id,
                cross_references=(),
                issues=(),
                data_quality=HumanReviewDecisionLogConsistencyDataQuality(),
                safety_flags=HumanReviewDecisionLogConsistencySafetyFlags(),
                reason_codes=(HumanReviewDecisionLogConsistencyReasonCode.NOT_APPLICABLE,),
                safety_notice=SAFETY_NOTICE,
                metadata=input.metadata,
                notes="No queue entries or decision log refs provided; consistency check is not applicable.",
            )

    # Build cross-references.
    cross_references = _build_cross_references(
        input.queue_report, input.decision_log_report, generated_at
    )

    # Detect issues.
    all_issues: list[HumanReviewDecisionLogConsistencyIssue] = []
    all_issues.extend(_detect_missing_decision_log_refs(cross_references, config, generated_at))
    all_issues.extend(_detect_orphan_decision_log_refs(cross_references, generated_at))
    all_issues.extend(_detect_mismatched_fields(cross_references, input.queue_report, input.decision_log_report, generated_at))
    all_issues.extend(
        _detect_inconsistent_result_states(
            cross_references, input.queue_report, input.decision_log_report, config, generated_at
        )
    )

    # Mark matched cross-references with mismatch issues as mismatched.
    mismatch_issue_types = {
        HumanReviewDecisionLogConsistencyIssueType.MISMATCHED_QUEUE_STATE.value,
        HumanReviewDecisionLogConsistencyIssueType.MISMATCHED_QUEUE_PRIORITY.value,
        HumanReviewDecisionLogConsistencyIssueType.MISMATCHED_QUEUE_SEVERITY.value,
        HumanReviewDecisionLogConsistencyIssueType.MISMATCHED_QUEUE_REASON_CODES.value,
    }
    mismatched_queue_ids = {
        issue.queue_entry_id for issue in all_issues if issue.issue_type in mismatch_issue_types
    }
    updated_cross_references: list[HumanReviewDecisionLogConsistencyCrossReference] = []
    for cr in cross_references:
        if cr.match_status == "matched" and cr.queue_entry_id in mismatched_queue_ids:
            updated_cr = replace(
                cr,
                match_status="mismatched",
                cross_reference_id=_build_cross_reference_id(
                    cr.queue_entry_id, cr.decision_log_queue_entry_id, "mismatched", generated_at
                ),
            )
            updated_cross_references.append(updated_cr)
        else:
            updated_cross_references.append(cr)

    # Sort deterministically.
    sorted_cross_references = tuple(
        sorted(
            updated_cross_references,
            key=lambda cr: (cr.queue_entry_id or "", cr.match_status, cr.decision_log_queue_entry_id),
        )
    )
    sorted_issues = tuple(
        sorted(
            all_issues,
            key=lambda i: (i.severity, i.issue_type, i.queue_entry_id, i.decision_log_queue_entry_id, i.issue_id),
        )
    )

    # Aggregate state.
    state = _compute_aggregate_state(sorted_issues, config)

    # Data quality.
    data_quality = _build_data_quality(
        sorted_cross_references, sorted_issues, input.queue_report, input.decision_log_report, unsafe, forbidden
    )

    # Reason codes.
    reason_codes = _build_reason_codes(state, sorted_issues)

    # Safety flags.
    safety_flags = HumanReviewDecisionLogConsistencySafetyFlags(
        has_unsafe_content=unsafe,
        has_forbidden_terms=forbidden,
    )

    # Report ID: based on matched queue entry IDs.
    matched_ids = tuple(cr.queue_entry_id for cr in sorted_cross_references if cr.match_status == "matched")
    report_id = _build_report_id(input, generated_at, matched_ids)

    notes = ""
    if state == HumanReviewDecisionLogConsistencyState.NOT_APPLICABLE:
        notes = "Consistency check is not applicable for the given input."
    elif state == HumanReviewDecisionLogConsistencyState.OK:
        notes = "No cross-artifact consistency issues detected."
    elif state == HumanReviewDecisionLogConsistencyState.DEGRADED:
        notes = "Advisory consistency issues detected; review recommended."
    elif state == HumanReviewDecisionLogConsistencyState.BLOCKED:
        notes = "Blocking consistency issues detected or input is blocked."

    return HumanReviewDecisionLogConsistencyReport(
        report_id=report_id,
        generated_at=generated_at,
        state=state,
        project_version=input.project_version,
        queue_report_id=input.queue_report.report_id,
        decision_log_report_id=input.decision_log_report.report_id,
        cross_references=sorted_cross_references,
        issues=sorted_issues,
        data_quality=data_quality,
        safety_flags=safety_flags,
        reason_codes=reason_codes,
        safety_notice=SAFETY_NOTICE,
        metadata=input.metadata,
        notes=notes,
    )
