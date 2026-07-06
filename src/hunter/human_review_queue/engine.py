"""In-memory engine for hunter.human_review_queue package.

MVP-40 — Local Research Human Review Queue.

The engine receives only caller-provided in-memory input. It never inspects the
filesystem, imports prior packages, or traverses any path or reference string.
It never emits executable remediation actions, shell commands, code patches,
 infrastructure changes, or task assignments.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from json import dumps
from typing import Any

from hunter.human_review_queue.models import (
    FORBIDDEN_HUMAN_REVIEW_QUEUE_TERMS,
    HumanReviewQueueConfig,
    HumanReviewQueueDataQuality,
    HumanReviewQueueDecisionHint,
    HumanReviewQueueEntry,
    HumanReviewQueueEntryState,
    HumanReviewQueueInput,
    HumanReviewQueueIssue,
    HumanReviewQueueIssueType,
    HumanReviewQueuePriority,
    HumanReviewQueueReasonCode,
    HumanReviewQueueReport,
    HumanReviewQueueSafetyFlags,
    HumanReviewQueueSeverity,
    HumanReviewQueueState,
    HumanReviewSourceRecord,
    _check_forbidden_mapping,
    _has_forbidden_term,
    has_unsafe_human_review_queue_content,
)

SAFETY_NOTICE = (
    "This report is a local, audit-only research artifact. "
    "Queued-for-review is for human-audit tracking only and does not imply "
    "approval, certification, production readiness, trading readiness, "
    "recommendation, suitability, signal validity, task assignment, or "
    "executable remediation plan."
)


# Reason-code sets used for aggregation.
_BLOCKING_REASON_CODES: frozenset[str] = frozenset({
    HumanReviewQueueReasonCode.UNSAFE_CONTENT.value,
    HumanReviewQueueReasonCode.FORBIDDEN_TERM_PRESENT.value,
    HumanReviewQueueReasonCode.DUPLICATE_SOURCE_ID.value,
    HumanReviewQueueReasonCode.BLOCKING_SEVERITY.value,
    HumanReviewQueueReasonCode.SAFETY_BLOCKED.value,
})


_ADVISORY_REASON_CODES: frozenset[str] = frozenset({
    HumanReviewQueueReasonCode.CONSISTENCY_DEGRADED.value,
    HumanReviewQueueReasonCode.DUPLICATE_QUEUE_ENTRY.value,
    HumanReviewQueueReasonCode.ORPHAN_RELATED_RECORD.value,
    HumanReviewQueueReasonCode.STALE_SOURCE_RECORD.value,
    HumanReviewQueueReasonCode.ADVISORY_SEVERITY.value,
    HumanReviewQueueReasonCode.DISPUTED_STATE.value,
    HumanReviewQueueReasonCode.PENDING_REVIEW_STATE.value,
    HumanReviewQueueReasonCode.MISSING_EVIDENCE.value,
    HumanReviewQueueReasonCode.MISSING_REVIEW.value,
    HumanReviewQueueReasonCode.MISSING_CLOSURE_METADATA.value,
    HumanReviewQueueReasonCode.MANUAL_REVIEW_REQUIRED.value,
})


def _canonical_json(value: Any) -> str:
    """Return a deterministic canonical JSON representation."""
    return dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_hex(value: str) -> str:
    """Return the full SHA-256 hex digest of a string."""
    return sha256(value.encode("utf-8")).hexdigest()


def _sha256_hex_16(value: str) -> str:
    """Return the first 16 characters of a SHA-256 hex digest."""
    return _sha256_hex(value)[:16]


def _resolve_generated_at(input: HumanReviewQueueInput) -> datetime:
    """Return the effective generated_at timestamp."""
    return input.generated_at if input.generated_at is not None else datetime.now(timezone.utc)


def _has_unsafe_content(input: HumanReviewQueueInput) -> bool:
    """Return True if any metadata field contains unsafe non-string values."""
    if has_unsafe_human_review_queue_content(dict(input.metadata)):
        return True
    for record in input.source_records:
        if has_unsafe_human_review_queue_content(dict(record.metadata)):
            return True
        for text in (record.title, record.description, record.state, record.severity, record.owner, record.reviewer):
            if has_unsafe_human_review_queue_content(text):
                return True
        for text in record.reason_codes:
            if has_unsafe_human_review_queue_content(text):
                return True
        for text in record.related_record_ids:
            if has_unsafe_human_review_queue_content(text):
                return True
        for text in (record.artifact_ref, record.report_ref):
            if has_unsafe_human_review_queue_content(text):
                return True
    return False


def _has_forbidden_terms(input: HumanReviewQueueInput) -> bool:
    """Return True if any text field or metadata contains forbidden terms."""
    if _check_forbidden_mapping(input.metadata, FORBIDDEN_HUMAN_REVIEW_QUEUE_TERMS):
        return True
    for record in input.source_records:
        for text in (record.title, record.description, record.state, record.severity, record.owner, record.reviewer):
            if text and _has_forbidden_term(text, FORBIDDEN_HUMAN_REVIEW_QUEUE_TERMS):
                return True
        for text in record.reason_codes:
            if text and _has_forbidden_term(text, FORBIDDEN_HUMAN_REVIEW_QUEUE_TERMS):
                return True
        if _check_forbidden_mapping(record.metadata, FORBIDDEN_HUMAN_REVIEW_QUEUE_TERMS):
            return True
    return False


def _find_duplicate_source_ids(source_records: tuple[HumanReviewSourceRecord, ...]) -> tuple[str, ...]:
    """Return normalized source_id values that appear more than once."""
    seen: set[str] = set()
    duplicates: set[str] = set()
    for record in source_records:
        sid = str(record.source_id).strip()
        if sid in seen:
            duplicates.add(sid)
        else:
            seen.add(sid)
    return tuple(sorted(duplicates))


def _build_report_id(input: HumanReviewQueueInput, generated_at: datetime) -> str:
    """Build a deterministic report_id from sorted source IDs and metadata."""
    payload = {
        "source_ids": sorted(set(str(record.source_id) for record in input.source_records)),
        "project_version": input.project_version,
        "generated_at": generated_at.isoformat(),
    }
    return _sha256_hex(_canonical_json(payload))


def _build_queue_entry_id(
    source_id: str,
    source_kind: str,
    record_id: str,
    reason_codes: tuple[str, ...],
    priority: str,
    generated_at: datetime,
) -> str:
    """Build a deterministic queue_entry_id."""
    payload = {
        "source_id": source_id,
        "source_kind": source_kind,
        "record_id": record_id,
        "reason_codes": sorted(reason_codes),
        "priority": priority,
        "generated_at": generated_at.isoformat(),
    }
    return _sha256_hex_16(_canonical_json(payload))


def _build_issue_id(issue: HumanReviewQueueIssue) -> str:
    """Build a deterministic issue_id from issue content."""
    payload = {
        "issue_type": issue.issue_type,
        "severity": issue.severity,
        "reason_codes": sorted(issue.reason_codes),
        "title": issue.title,
        "description": issue.description,
        "source_id": issue.source_id,
        "record_id": issue.record_id,
    }
    return _sha256_hex_16(_canonical_json(payload))


def _make_issue(
    *,
    issue_type: HumanReviewQueueIssueType,
    severity: HumanReviewQueueSeverity,
    reason_codes: tuple[str, ...],
    title: str,
    description: str,
    source_id: str = "",
    record_id: str = "",
    generated_at: datetime,
) -> HumanReviewQueueIssue:
    """Create an issue with a deterministic ID."""
    issue = HumanReviewQueueIssue(
        issue_type=issue_type.value,
        severity=severity.value,
        reason_codes=reason_codes,
        title=title,
        description=description,
        source_id=source_id,
        record_id=record_id,
        generated_at=generated_at,
    )
    return replace(issue, issue_id=_build_issue_id(issue))


def _make_queue_entry(
    *,
    source_id: str,
    source_kind: str,
    record_id: str,
    entry_state: HumanReviewQueueEntryState,
    priority: HumanReviewQueuePriority,
    decision_hint: HumanReviewQueueDecisionHint,
    severity: HumanReviewQueueSeverity,
    reason_codes: tuple[str, ...],
    title: str,
    description: str,
    generated_at: datetime,
    metadata: dict[str, str] | None = None,
) -> HumanReviewQueueEntry:
    """Create a queue entry with a deterministic ID."""
    entry = HumanReviewQueueEntry(
        source_id=source_id,
        source_kind=source_kind,
        record_id=record_id,
        entry_state=entry_state.value,
        priority=priority.value,
        decision_hint=decision_hint.value,
        severity=severity.value,
        reason_codes=reason_codes,
        title=title,
        description=description,
        generated_at=generated_at,
        metadata=metadata if metadata is not None else {},
    )
    entry_id = _build_queue_entry_id(
        source_id=source_id,
        source_kind=source_kind,
        record_id=record_id,
        reason_codes=reason_codes,
        priority=priority.value,
        generated_at=generated_at,
    )
    return replace(entry, queue_entry_id=entry_id)


def _source_state_to_entry_state(
    state: str,
    severity: str,
    source_kind: str,
    config: HumanReviewQueueConfig,
) -> HumanReviewQueueEntryState:
    """Map a source record state to a queue entry state."""
    normalized_state = state.strip().lower()
    normalized_severity = severity.strip().lower()

    if normalized_state == "blocked":
        return HumanReviewQueueEntryState.BLOCKED
    if normalized_state == "pending_review":
        return HumanReviewQueueEntryState.PENDING_REVIEW
    if normalized_state == "disputed":
        return HumanReviewQueueEntryState.DISPUTED
    if normalized_state == "acknowledged":
        return HumanReviewQueueEntryState.SUPPRESSED if config.suppress_acknowledged else HumanReviewQueueEntryState.ACKNOWLEDGED
    if normalized_state == "deferred":
        return HumanReviewQueueEntryState.DEFERRED
    if normalized_state == "not_applicable":
        return HumanReviewQueueEntryState.NOT_APPLICABLE
    if normalized_state == "conflicting":
        return HumanReviewQueueEntryState.BLOCKED if normalized_severity == "blocking" else HumanReviewQueueEntryState.DISPUTED

    if source_kind == "manual_note":
        return HumanReviewQueueEntryState.QUEUED if config.include_manual_notes else HumanReviewQueueEntryState.SUPPRESSED

    return HumanReviewQueueEntryState.BLOCKED if normalized_severity == "blocking" else HumanReviewQueueEntryState.QUEUED


def _source_severity_to_queue_severity(
    severity: str,
    config: HumanReviewQueueConfig,
    entry_state: HumanReviewQueueEntryState,
) -> HumanReviewQueueSeverity:
    """Map a source record severity to a queue entry severity."""
    normalized = severity.strip().lower()
    if normalized == "blocking":
        return HumanReviewQueueSeverity.BLOCKING
    if normalized == "advisory":
        if config.include_advisory:
            return HumanReviewQueueSeverity.ADVISORY
        return HumanReviewQueueSeverity.INFO
    if entry_state == HumanReviewQueueEntryState.NOT_APPLICABLE:
        return HumanReviewQueueSeverity.INFO
    return HumanReviewQueueSeverity.INFO


def _assign_priority(
    entry_state: HumanReviewQueueEntryState,
    severity: HumanReviewQueueSeverity,
    reason_codes: tuple[str, ...],
    source_state: str,
    source_kind: str,
    unsafe: bool,
    forbidden: bool,
    duplicate_source_id: bool,
) -> HumanReviewQueuePriority:
    """Assign priority using first-match-wins precedence."""
    normalized_state = source_state.strip().lower()
    reason_set = set(code.lower() for code in reason_codes)

    # CRITICAL: unsafe content, forbidden terms, blocking severity, fail-closed duplicate source ID.
    if unsafe or forbidden or duplicate_source_id or severity == HumanReviewQueueSeverity.BLOCKING:
        return HumanReviewQueuePriority.CRITICAL
    if "blocking_severity" in reason_set:
        return HumanReviewQueuePriority.CRITICAL

    # HIGH: disputed, rejected/missing review, missing evidence, conflicting.
    if entry_state in (HumanReviewQueueEntryState.DISPUTED, HumanReviewQueueEntryState.BLOCKED):
        return HumanReviewQueuePriority.HIGH
    if normalized_state in ("disputed", "conflicting", "rejected"):
        return HumanReviewQueuePriority.HIGH
    if reason_set & {"missing_evidence", "missing_review", "missing_closure_metadata", "disputed_state"}:
        return HumanReviewQueuePriority.HIGH

    # MEDIUM: pending review, stale, partial/incomplete metadata, advisory.
    if entry_state == HumanReviewQueueEntryState.PENDING_REVIEW or normalized_state == "pending_review":
        return HumanReviewQueuePriority.MEDIUM
    if entry_state == HumanReviewQueueEntryState.STALE or "stale_source_record" in reason_set:
        return HumanReviewQueuePriority.MEDIUM
    if "manual_review_required" in reason_set or severity == HumanReviewQueueSeverity.ADVISORY:
        return HumanReviewQueuePriority.MEDIUM

    # LOW: manual notes, deferred, acknowledged, advisory tracking.
    if entry_state in (HumanReviewQueueEntryState.DEFERRED, HumanReviewQueueEntryState.ACKNOWLEDGED):
        return HumanReviewQueuePriority.LOW
    if source_kind == "manual_note":
        return HumanReviewQueuePriority.LOW

    # INFO: not-applicable, informational.
    return HumanReviewQueuePriority.INFO


def _assign_decision_hint(entry_state: HumanReviewQueueEntryState) -> HumanReviewQueueDecisionHint:
    """Assign a non-executable decision hint from entry state."""
    if entry_state in (HumanReviewQueueEntryState.QUEUED, HumanReviewQueueEntryState.BLOCKED, HumanReviewQueueEntryState.PENDING_REVIEW, HumanReviewQueueEntryState.DISPUTED, HumanReviewQueueEntryState.ORPHANED):
        return HumanReviewQueueDecisionHint.REVIEW_REQUIRED
    if entry_state == HumanReviewQueueEntryState.STALE:
        return HumanReviewQueueDecisionHint.REVIEW_OPTIONAL
    if entry_state == HumanReviewQueueEntryState.ACKNOWLEDGED:
        return HumanReviewQueueDecisionHint.ALREADY_ACKNOWLEDGED
    if entry_state == HumanReviewQueueEntryState.DEFERRED:
        return HumanReviewQueueDecisionHint.DEFERRED_FOR_LATER_AUDIT
    if entry_state in (HumanReviewQueueEntryState.NOT_APPLICABLE, HumanReviewQueueEntryState.DUPLICATE, HumanReviewQueueEntryState.SUPPRESSED):
        return HumanReviewQueueDecisionHint.NOT_APPLICABLE_FOR_AUDIT
    return HumanReviewQueueDecisionHint.REVIEW_REQUIRED


def _is_stale(
    record: HumanReviewSourceRecord,
    generated_at: datetime,
    threshold_seconds: int,
) -> bool:
    """Return True if the record is older than the staleness threshold."""
    if record.generated_at is None or threshold_seconds <= 0:
        return False
    cutoff = generated_at - timedelta(seconds=threshold_seconds)
    return record.generated_at < cutoff


def _detect_orphan_related_records(
    source_records: tuple[HumanReviewSourceRecord, ...],
    generated_at: datetime,
) -> tuple[HumanReviewQueueIssue, ...]:
    """Detect related record IDs that appear in neither source_id nor record_id sets."""
    source_ids = {str(record.source_id).strip() for record in source_records}
    record_ids = {str(record.record_id).strip() for record in source_records}
    issues: list[HumanReviewQueueIssue] = []
    for record in source_records:
        for related_id in record.related_record_ids:
            normalized = str(related_id).strip()
            if not normalized:
                continue
            if normalized not in source_ids and normalized not in record_ids:
                issues.append(
                    _make_issue(
                        issue_type=HumanReviewQueueIssueType.ORPHAN_RELATED_RECORD,
                        severity=HumanReviewQueueSeverity.ADVISORY,
                        reason_codes=(HumanReviewQueueReasonCode.ORPHAN_RELATED_RECORD.value,),
                        title="Orphan related record reference",
                        description=f"Related record ID {normalized!r} is not present in the input source_id or record_id sets.",
                        source_id=record.source_id,
                        record_id=record.record_id,
                        generated_at=generated_at,
                    )
                )
    return tuple(issues)


def _detect_stale_source_records(
    source_records: tuple[HumanReviewSourceRecord, ...],
    generated_at: datetime,
    threshold_seconds: int,
) -> tuple[HumanReviewQueueIssue, ...]:
    """Detect source records older than the staleness threshold."""
    issues: list[HumanReviewQueueIssue] = []
    for record in source_records:
        if _is_stale(record, generated_at, threshold_seconds):
            issues.append(
                _make_issue(
                    issue_type=HumanReviewQueueIssueType.STALE_SOURCE_RECORD,
                    severity=HumanReviewQueueSeverity.ADVISORY,
                    reason_codes=(HumanReviewQueueReasonCode.STALE_SOURCE_RECORD.value,),
                    title="Stale source record",
                    description="Source record is older than the configured staleness threshold.",
                    source_id=record.source_id,
                    record_id=record.record_id,
                    generated_at=generated_at,
                )
            )
    return tuple(issues)


def _build_queue_entries_from_record(
    record: HumanReviewSourceRecord,
    config: HumanReviewQueueConfig,
    generated_at: datetime,
    duplicate_source_ids: tuple[str, ...],
) -> list[HumanReviewQueueEntry]:
    """Build queue entries from a single source record."""
    entries: list[HumanReviewQueueEntry] = []
    source_id = record.source_id
    record_id = record.record_id
    source_kind = record.source_kind
    source_state = record.state
    source_severity = record.severity

    entry_state = _source_state_to_entry_state(source_state, source_severity, source_kind, config)
    severity = _source_severity_to_queue_severity(source_severity, config, entry_state)

    duplicate_source_id = source_id in duplicate_source_ids and source_id != ""

    base_reason_codes: list[str] = []
    if source_severity.strip().lower() == "blocking":
        base_reason_codes.append(HumanReviewQueueReasonCode.BLOCKING_SEVERITY.value)
    elif source_severity.strip().lower() == "advisory":
        base_reason_codes.append(HumanReviewQueueReasonCode.ADVISORY_SEVERITY.value)
    elif source_severity.strip().lower() == "info":
        base_reason_codes.append(HumanReviewQueueReasonCode.INFO_SEVERITY.value)

    normalized_state = source_state.strip().lower()
    if normalized_state == "disputed":
        base_reason_codes.append(HumanReviewQueueReasonCode.DISPUTED_STATE.value)
    if normalized_state == "pending_review":
        base_reason_codes.append(HumanReviewQueueReasonCode.PENDING_REVIEW_STATE.value)

    for code in record.reason_codes:
        if code and code not in base_reason_codes:
            base_reason_codes.append(code)

    if duplicate_source_id:
        base_reason_codes.append(HumanReviewQueueReasonCode.DUPLICATE_SOURCE_ID.value)

    if entry_state == HumanReviewQueueEntryState.NOT_APPLICABLE:
        base_reason_codes.append(HumanReviewQueueReasonCode.NOT_APPLICABLE.value)

    if source_kind == "manual_note" and not config.include_manual_notes:
        base_reason_codes.append(HumanReviewQueueReasonCode.NOT_APPLICABLE.value)

    reason_codes = tuple(base_reason_codes)
    priority = _assign_priority(
        entry_state=entry_state,
        severity=severity,
        reason_codes=reason_codes,
        source_state=source_state,
        source_kind=source_kind,
        unsafe=False,
        forbidden=False,
        duplicate_source_id=duplicate_source_id,
    )
    decision_hint = _assign_decision_hint(entry_state)

    entries.append(
        _make_queue_entry(
            source_id=source_id,
            source_kind=source_kind,
            record_id=record_id,
            entry_state=entry_state,
            priority=priority,
            decision_hint=decision_hint,
            severity=severity,
            reason_codes=reason_codes,
            title=record.title,
            description=record.description,
            generated_at=generated_at,
            metadata=dict(record.metadata),
        )
    )

    return entries


def _deduplicate_queue_entries(
    entries: tuple[HumanReviewQueueEntry, ...],
    generated_at: datetime,
) -> tuple[HumanReviewQueueEntry, ...]:
    """Remove duplicate queue entries and emit info issues for duplicates."""
    seen: dict[tuple[str, ...], HumanReviewQueueEntry] = {}
    duplicates: list[HumanReviewQueueEntry] = []
    for entry in entries:
        key = (entry.source_id, entry.source_kind, entry.record_id, entry.priority, tuple(sorted(entry.reason_codes)))
        if key in seen:
            duplicates.append(entry)
        else:
            seen[key] = entry
    unique = tuple(seen.values())
    return unique, tuple(duplicates)


def _detect_duplicate_queue_entries(
    duplicates: tuple[HumanReviewQueueEntry, ...],
    generated_at: datetime,
) -> tuple[HumanReviewQueueIssue, ...]:
    """Emit info issues for duplicate queue entries."""
    issues: list[HumanReviewQueueIssue] = []
    for entry in duplicates:
        issues.append(
            _make_issue(
                issue_type=HumanReviewQueueIssueType.DUPLICATE_QUEUE_ENTRY,
                severity=HumanReviewQueueSeverity.INFO,
                reason_codes=(HumanReviewQueueReasonCode.DUPLICATE_QUEUE_ENTRY.value,),
                title="Duplicate queue entry",
                description="The same source record produced a duplicate queue entry and is counted only once.",
                source_id=entry.source_id,
                record_id=entry.record_id,
                generated_at=generated_at,
            )
        )
    return tuple(issues)


def _compute_aggregate_state(
    queue_entries: tuple[HumanReviewQueueEntry, ...],
    issues: tuple[HumanReviewQueueIssue, ...],
    config: HumanReviewQueueConfig,
    empty_input: bool,
) -> HumanReviewQueueState:
    """Compute the aggregate report state from entries and issues."""
    if empty_input:
        return HumanReviewQueueState.NOT_APPLICABLE

    has_blocking = False
    has_degrading = False

    for issue in issues:
        if issue.severity == HumanReviewQueueSeverity.BLOCKING.value:
            has_blocking = True
            break
        if issue.severity == HumanReviewQueueSeverity.ADVISORY.value:
            has_degrading = True

    for entry in queue_entries:
        if entry.severity == HumanReviewQueueSeverity.BLOCKING.value or entry.entry_state == HumanReviewQueueEntryState.BLOCKED.value:
            has_blocking = True
            break
        if entry.priority in (HumanReviewQueuePriority.CRITICAL.value, HumanReviewQueuePriority.HIGH.value):
            has_degrading = True
        if entry.severity == HumanReviewQueueSeverity.ADVISORY.value and config.strict:
            has_degrading = True

    if has_blocking:
        return HumanReviewQueueState.BLOCKED
    if has_degrading:
        if config.strict:
            return HumanReviewQueueState.BLOCKED
        return HumanReviewQueueState.DEGRADED
    return HumanReviewQueueState.OK


def _build_data_quality(
    source_records: tuple[HumanReviewSourceRecord, ...],
    queue_entries: tuple[HumanReviewQueueEntry, ...],
    issues: tuple[HumanReviewQueueIssue, ...],
    duplicate_source_ids: tuple[str, ...],
    duplicate_entries: tuple[HumanReviewQueueEntry, ...],
) -> HumanReviewQueueDataQuality:
    """Build the data quality summary."""
    blocking = sum(1 for e in queue_entries if e.severity == HumanReviewQueueSeverity.BLOCKING.value)
    advisory = sum(1 for e in queue_entries if e.severity == HumanReviewQueueSeverity.ADVISORY.value)
    info = sum(1 for e in queue_entries if e.severity == HumanReviewQueueSeverity.INFO.value)
    critical = sum(1 for e in queue_entries if e.priority == HumanReviewQueuePriority.CRITICAL.value)
    high = sum(1 for e in queue_entries if e.priority == HumanReviewQueuePriority.HIGH.value)
    medium = sum(1 for e in queue_entries if e.priority == HumanReviewQueuePriority.MEDIUM.value)
    low = sum(1 for e in queue_entries if e.priority == HumanReviewQueuePriority.LOW.value)
    info_priority = sum(1 for e in queue_entries if e.priority == HumanReviewQueuePriority.INFO.value)

    unsafe = sum(1 for issue in issues if issue.issue_type == HumanReviewQueueIssueType.UNSAFE_CONTENT.value)
    forbidden = sum(1 for issue in issues if issue.issue_type == HumanReviewQueueIssueType.FORBIDDEN_TERM.value)

    return HumanReviewQueueDataQuality(
        total_source_records=len(source_records),
        total_queue_entries=len(queue_entries),
        total_issues=len(issues),
        duplicate_source_id_count=len(duplicate_source_ids),
        duplicate_queue_entry_count=len(duplicate_entries),
        orphan_related_record_count=sum(
            1 for issue in issues if issue.issue_type == HumanReviewQueueIssueType.ORPHAN_RELATED_RECORD.value
        ),
        stale_source_record_count=sum(
            1 for issue in issues if issue.issue_type == HumanReviewQueueIssueType.STALE_SOURCE_RECORD.value
        ),
        unsafe_content_count=unsafe,
        forbidden_term_count=forbidden,
        blocking_count=blocking,
        advisory_count=advisory,
        info_count=info,
        critical_count=critical,
        high_count=high,
        medium_count=medium,
        low_count=low,
        info_priority_count=info_priority,
        sections_present=5,
    )


def build_human_review_queue_report(
    input: HumanReviewQueueInput,
    config: HumanReviewQueueConfig | None = None,
) -> HumanReviewQueueReport:
    """Build a deterministic human review queue report from in-memory records."""
    if config is None:
        config = input.config

    generated_at = _resolve_generated_at(input)

    # Empty input -> deterministic NOT_APPLICABLE report.
    if not input.source_records:
        return HumanReviewQueueReport(
            report_id=_build_report_id(input, generated_at),
            generated_at=generated_at,
            state=HumanReviewQueueState.NOT_APPLICABLE,
            project_version=input.project_version,
            source_records=(),
            queue_entries=(),
            issues=(),
            data_quality=HumanReviewQueueDataQuality(
                total_source_records=0,
                total_queue_entries=0,
                total_issues=0,
                sections_present=0,
            ),
            safety_flags=HumanReviewQueueSafetyFlags(),
            reason_codes=(HumanReviewQueueReasonCode.NOT_APPLICABLE,),
            metadata=input.metadata,
            safety_notice=SAFETY_NOTICE,
            notes="No source records provided; queue is not applicable.",
        )

    # Safety scan (fail-closed).
    unsafe = _has_unsafe_content(input)
    if unsafe:
        return HumanReviewQueueReport.blocked(
            input=input,
            reason_code=HumanReviewQueueReasonCode.UNSAFE_CONTENT,
            notes="Report blocked due to unsafe content in caller-provided input.",
        )

    forbidden = False
    if config.forbid_action_terms:
        forbidden = _has_forbidden_terms(input)
        if forbidden:
            return HumanReviewQueueReport.blocked(
                input=input,
                reason_code=HumanReviewQueueReasonCode.FORBIDDEN_TERM_PRESENT,
                notes="Report blocked due to forbidden action terms in caller-provided input.",
            )

    duplicate_source_ids = _find_duplicate_source_ids(input.source_records)
    if duplicate_source_ids:
        return HumanReviewQueueReport.blocked(
            input=input,
            reason_code=HumanReviewQueueReasonCode.DUPLICATE_SOURCE_ID,
            notes="Report blocked due to duplicate source IDs in caller-provided input.",
        )

    # Build queue entries.
    all_entries: list[HumanReviewQueueEntry] = []
    for record in input.source_records:
        all_entries.extend(_build_queue_entries_from_record(record, config, generated_at, duplicate_source_ids))

    # Stale detection issues (not blocking, but may add queue entries if enabled).
    stale_issues = _detect_stale_source_records(
        input.source_records, generated_at, config.staleness_threshold_seconds
    )

    # Orphan detection issues.
    orphan_issues = _detect_orphan_related_records(input.source_records, generated_at)

    # Deduplicate queue entries.
    unique_entries, duplicate_entries = _deduplicate_queue_entries(tuple(all_entries), generated_at)
    duplicate_issues = _detect_duplicate_queue_entries(duplicate_entries, generated_at)

    # Add stale queue entries if enabled.
    if config.include_stale:
        for issue in stale_issues:
            record = next(
                (r for r in input.source_records if r.source_id == issue.source_id and r.record_id == issue.record_id),
                None,
            )
            if record is not None:
                entry = _make_queue_entry(
                    source_id=record.source_id,
                    source_kind=record.source_kind,
                    record_id=record.record_id,
                    entry_state=HumanReviewQueueEntryState.STALE,
                    priority=HumanReviewQueuePriority.MEDIUM,
                    decision_hint=HumanReviewQueueDecisionHint.REVIEW_OPTIONAL,
                    severity=HumanReviewQueueSeverity.ADVISORY,
                    reason_codes=(HumanReviewQueueReasonCode.STALE_SOURCE_RECORD.value,),
                    title=record.title,
                    description=record.description,
                    generated_at=generated_at,
                    metadata=dict(record.metadata),
                )
                unique_entries = unique_entries + (entry,)

    # Sort deterministically by ID and generated_at.
    sorted_entries = tuple(sorted(unique_entries, key=lambda e: (e.queue_entry_id, e.generated_at or datetime.min.replace(tzinfo=timezone.utc))))
    sorted_issues = tuple(
        sorted(
            stale_issues + orphan_issues + duplicate_issues,
            key=lambda i: (i.issue_id, i.generated_at or datetime.min.replace(tzinfo=timezone.utc)),
        )
    )

    state = _compute_aggregate_state(
        sorted_entries,
        sorted_issues,
        config,
        empty_input=False,
    )

    reason_codes = _build_reason_codes(state, sorted_issues, sorted_entries)

    data_quality = _build_data_quality(
        input.source_records,
        sorted_entries,
        sorted_issues,
        duplicate_source_ids,
        duplicate_entries,
    )

    safety_flags = HumanReviewQueueSafetyFlags(
        has_unsafe_content=unsafe,
        has_forbidden_terms=forbidden,
    )

    return HumanReviewQueueReport(
        report_id=_build_report_id(input, generated_at),
        generated_at=generated_at,
        state=state,
        project_version=input.project_version,
        source_records=input.source_records,
        queue_entries=sorted_entries,
        issues=sorted_issues,
        data_quality=data_quality,
        safety_flags=safety_flags,
        reason_codes=reason_codes,
        metadata=input.metadata,
        safety_notice=SAFETY_NOTICE,
        notes="",
    )


def _build_reason_codes(
    state: HumanReviewQueueState,
    issues: tuple[HumanReviewQueueIssue, ...],
    entries: tuple[HumanReviewQueueEntry, ...],
) -> tuple[HumanReviewQueueReasonCode, ...]:
    """Build deterministic report-level reason codes."""
    codes: set[str] = set()

    if state == HumanReviewQueueState.NOT_APPLICABLE:
        codes.add(HumanReviewQueueReasonCode.NOT_APPLICABLE.value)
    elif state == HumanReviewQueueState.OK:
        codes.add(HumanReviewQueueReasonCode.OK.value)
    elif state == HumanReviewQueueState.DEGRADED:
        codes.add(HumanReviewQueueReasonCode.CONSISTENCY_DEGRADED.value)

    for issue in issues:
        for code in issue.reason_codes:
            codes.add(code)
    for entry in entries:
        for code in entry.reason_codes:
            codes.add(code)

    if state == HumanReviewQueueState.BLOCKED:
        codes.add(HumanReviewQueueReasonCode.SAFETY_BLOCKED.value)

    # Preserve deterministic order using enum definition order.
    ordered = [code for code in HumanReviewQueueReasonCode if code.value in codes]
    return tuple(ordered)
