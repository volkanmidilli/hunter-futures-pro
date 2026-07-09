"""In-memory engine for hunter.human_review_decision_log package.

MVP-41 — Local Research Human Review Decision Log.

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

from hunter.human_review_decision_log.models import (
    FORBIDDEN_HUMAN_REVIEW_DECISION_TERMS,
    HumanReviewDecisionIssue,
    HumanReviewDecisionIssueType,
    HumanReviewDecisionLink,
    HumanReviewDecisionLogConfig,
    HumanReviewDecisionLogDataQuality,
    HumanReviewDecisionLogInput,
    HumanReviewDecisionLogReport,
    HumanReviewDecisionLogSafetyFlags,
    HumanReviewDecisionLogState,
    HumanReviewDecisionOutcome,
    HumanReviewDecisionReasonCode,
    HumanReviewDecisionRecord,
    HumanReviewDecisionResult,
    HumanReviewDecisionSeverity,
    HumanReviewDecisionState,
    HumanReviewDecisionValidity,
    HumanReviewQueueEntryRef,
    SAFETY_NOTICE,
    _check_forbidden_mapping,
    _has_forbidden_term,
    has_unsafe_human_review_decision_content,
)

# Reason-code sets used for aggregation.
_BLOCKING_REASON_CODES: frozenset[str] = frozenset({
    HumanReviewDecisionReasonCode.UNSAFE_CONTENT.value,
    HumanReviewDecisionReasonCode.FORBIDDEN_TERM_PRESENT.value,
    HumanReviewDecisionReasonCode.INVALID_INPUT_DATA.value,
    HumanReviewDecisionReasonCode.DUPLICATE_QUEUE_ENTRY_ID.value,
    HumanReviewDecisionReasonCode.DUPLICATE_DECISION_ID.value,
    HumanReviewDecisionReasonCode.DUPLICATE_LINK_ID.value,
    HumanReviewDecisionReasonCode.SAFETY_BLOCKED.value,
})

_ADVISORY_REASON_CODES: frozenset[str] = frozenset({
    HumanReviewDecisionReasonCode.CONSISTENCY_DEGRADED.value,
    HumanReviewDecisionReasonCode.SEMANTIC_DUPLICATE_DECISION.value,
    HumanReviewDecisionReasonCode.ORPHAN_DECISION.value,
    HumanReviewDecisionReasonCode.ORPHAN_LINK.value,
    HumanReviewDecisionReasonCode.MISSING_DECISION.value,
    HumanReviewDecisionReasonCode.CONFLICTING_DECISION.value,
    HumanReviewDecisionReasonCode.CONFLICTING_OUTCOME.value,
    HumanReviewDecisionReasonCode.STALE_QUEUE_ENTRY.value,
    HumanReviewDecisionReasonCode.STALE_DECISION.value,
    HumanReviewDecisionReasonCode.MISSING_REVIEWER.value,
    HumanReviewDecisionReasonCode.MISSING_DECIDED_AT.value,
    HumanReviewDecisionReasonCode.MISSING_RATIONALE.value,
    HumanReviewDecisionReasonCode.MISSING_OUTCOME.value,
    HumanReviewDecisionReasonCode.MISSING_QUEUE_ENTRY_ID.value,
    HumanReviewDecisionReasonCode.OUTCOME_MISMATCH.value,
    HumanReviewDecisionReasonCode.ADVISORY_FINDING.value,
})


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

def _resolve_generated_at(input: HumanReviewDecisionLogInput) -> datetime:
    """Return the effective generated_at timestamp."""
    return input.generated_at if input.generated_at is not None else datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Report ID, decision_result_id, issue_id
# ---------------------------------------------------------------------------

def _build_report_id(input: HumanReviewDecisionLogInput, generated_at: datetime) -> str:
    """Build a deterministic report_id from sorted IDs and metadata."""
    queue_entry_ids = sorted(set(str(ref.queue_entry_id) for ref in input.queue_entry_refs))
    decision_ids = sorted(set(str(rec.decision_id) for rec in input.decision_records))
    link_ids = sorted(set(str(lnk.link_id) for lnk in input.links))
    payload = {
        "queue_entry_ids": queue_entry_ids,
        "decision_ids": decision_ids,
        "link_ids": link_ids,
        "project_version": input.project_version,
        "generated_at": generated_at.isoformat(),
    }
    return _sha256_hex(_canonical_json(payload))

def _build_decision_result_id(
    queue_entry_id: str,
    decision_ids: tuple[str, ...],
    decision_state: str,
    decision_outcome: str,
    decision_validity: str,
    generated_at: datetime,
) -> str:
    """Build a deterministic decision_result_id."""
    payload = {
        "queue_entry_id": queue_entry_id,
        "decision_ids": sorted(decision_ids),
        "decision_state": decision_state,
        "decision_outcome": decision_outcome,
        "decision_validity": decision_validity,
        "generated_at": generated_at.isoformat(),
    }
    return _sha256_hex_16(_canonical_json(payload))

def _build_issue_id(issue: HumanReviewDecisionIssue) -> str:
    """Build a deterministic issue_id from issue content."""
    payload = {
        "issue_type": issue.issue_type,
        "severity": issue.severity,
        "reason_codes": sorted(issue.reason_codes),
        "title": issue.title,
        "description": issue.description,
        "source_id": issue.source_id,
        "target_id": issue.target_id,
        "decision_id": issue.decision_id,
        "queue_entry_id": issue.queue_entry_id,
    }
    return _sha256_hex_16(_canonical_json(payload))


# ---------------------------------------------------------------------------
# Issue factory
# ---------------------------------------------------------------------------

def _make_issue(
    *,
    issue_type: HumanReviewDecisionIssueType,
    severity: HumanReviewDecisionSeverity,
    reason_codes: tuple[str, ...],
    title: str,
    description: str,
    source_id: str = "",
    target_id: str = "",
    decision_id: str = "",
    queue_entry_id: str = "",
    generated_at: datetime,
) -> HumanReviewDecisionIssue:
    """Create an issue with a deterministic ID."""
    issue = HumanReviewDecisionIssue(
        issue_type=issue_type.value,
        severity=severity.value,
        reason_codes=reason_codes,
        title=title,
        description=description,
        source_id=source_id,
        target_id=target_id,
        decision_id=decision_id,
        queue_entry_id=queue_entry_id,
        generated_at=generated_at,
    )
    return replace(issue, issue_id=_build_issue_id(issue))


# ---------------------------------------------------------------------------
# Safety detection
# ---------------------------------------------------------------------------

def _has_unsafe_content(input: HumanReviewDecisionLogInput) -> bool:
    """Return True if any metadata field contains unsafe non-string values."""
    if has_unsafe_human_review_decision_content(dict(input.metadata)):
        return True
    for ref in input.queue_entry_refs:
        if has_unsafe_human_review_decision_content(dict(ref.metadata)):
            return True
        for text in (ref.source_id, ref.source_kind, ref.record_id, ref.entry_state, ref.priority, ref.severity):
            if has_unsafe_human_review_decision_content(text):
                return True
        for text in (ref.artifact_ref, ref.report_ref):
            if has_unsafe_human_review_decision_content(text):
                return True
        for text in ref.reason_codes:
            if has_unsafe_human_review_decision_content(text):
                return True
    for rec in input.decision_records:
        if has_unsafe_human_review_decision_content(dict(rec.metadata)):
            return True
        for text in (rec.decision_id, rec.queue_entry_id, rec.reviewer, rec.outcome, rec.rationale):
            if has_unsafe_human_review_decision_content(text):
                return True
        for text in rec.reason_codes:
            if has_unsafe_human_review_decision_content(text):
                return True
        for text in (rec.artifact_ref, rec.report_ref):
            if has_unsafe_human_review_decision_content(text):
                return True
    for lnk in input.links:
        if has_unsafe_human_review_decision_content(dict(lnk.metadata)):
            return True
        for text in (lnk.link_id, lnk.source_id, lnk.target_id, lnk.link_type):
            if has_unsafe_human_review_decision_content(text):
                return True
    return False

def _has_forbidden_terms(input: HumanReviewDecisionLogInput) -> bool:
    """Return True if any text field or metadata contains forbidden terms."""
    if _check_forbidden_mapping(input.metadata, FORBIDDEN_HUMAN_REVIEW_DECISION_TERMS):
        return True
    for ref in input.queue_entry_refs:
        for text in (ref.source_id, ref.source_kind, ref.record_id, ref.entry_state, ref.priority, ref.severity):
            if text and _has_forbidden_term(text, FORBIDDEN_HUMAN_REVIEW_DECISION_TERMS):
                return True
        for text in ref.reason_codes:
            if text and _has_forbidden_term(text, FORBIDDEN_HUMAN_REVIEW_DECISION_TERMS):
                return True
        if _check_forbidden_mapping(ref.metadata, FORBIDDEN_HUMAN_REVIEW_DECISION_TERMS):
            return True
    for rec in input.decision_records:
        for text in (rec.decision_id, rec.queue_entry_id, rec.reviewer, rec.outcome, rec.rationale):
            if text and _has_forbidden_term(text, FORBIDDEN_HUMAN_REVIEW_DECISION_TERMS):
                return True
        for text in rec.reason_codes:
            if text and _has_forbidden_term(text, FORBIDDEN_HUMAN_REVIEW_DECISION_TERMS):
                return True
        if _check_forbidden_mapping(rec.metadata, FORBIDDEN_HUMAN_REVIEW_DECISION_TERMS):
            return True
    for lnk in input.links:
        for text in (lnk.link_id, lnk.source_id, lnk.target_id, lnk.link_type):
            if text and _has_forbidden_term(text, FORBIDDEN_HUMAN_REVIEW_DECISION_TERMS):
                return True
        if _check_forbidden_mapping(lnk.metadata, FORBIDDEN_HUMAN_REVIEW_DECISION_TERMS):
            return True
    return False


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------

def _find_duplicate_queue_entry_ids(refs: tuple[HumanReviewQueueEntryRef, ...]) -> tuple[str, ...]:
    """Return normalized queue_entry_id values that appear more than once."""
    seen: set[str] = set()
    duplicates: set[str] = set()
    for ref in refs:
        sid = str(ref.queue_entry_id).strip()
        if sid in seen:
            duplicates.add(sid)
        else:
            seen.add(sid)
    return tuple(sorted(duplicates))

def _find_duplicate_decision_ids(records: tuple[HumanReviewDecisionRecord, ...]) -> tuple[str, ...]:
    """Return normalized decision_id values that appear more than once."""
    seen: set[str] = set()
    duplicates: set[str] = set()
    for rec in records:
        sid = str(rec.decision_id).strip()
        if sid in seen:
            duplicates.add(sid)
        else:
            seen.add(sid)
    return tuple(sorted(duplicates))

def _find_duplicate_link_ids(links: tuple[HumanReviewDecisionLink, ...]) -> tuple[str, ...]:
    """Return normalized link_id values that appear more than once."""
    seen: set[str] = set()
    duplicates: set[str] = set()
    for lnk in links:
        sid = str(lnk.link_id).strip()
        if sid in seen:
            duplicates.add(sid)
        else:
            seen.add(sid)
    return tuple(sorted(duplicates))


# ---------------------------------------------------------------------------
# Semantic duplicate detection
# ---------------------------------------------------------------------------

def _detect_semantic_duplicate_decisions(
    records: tuple[HumanReviewDecisionRecord, ...],
    generated_at: datetime,
) -> tuple[HumanReviewDecisionIssue, ...]:
    """Detect decisions with same queue_entry_id, reviewer, outcome, rationale."""
    seen: dict[tuple[str, str, str, str], str] = {}
    issues: list[HumanReviewDecisionIssue] = []
    for rec in records:
        key = (
            rec.queue_entry_id.strip(),
            rec.reviewer.strip(),
            rec.outcome.strip(),
            rec.rationale.strip(),
        )
        if key in seen:
            issues.append(
                _make_issue(
                    issue_type=HumanReviewDecisionIssueType.SEMANTIC_DUPLICATE_DECISION,
                    severity=HumanReviewDecisionSeverity.INFO,
                    reason_codes=(HumanReviewDecisionReasonCode.SEMANTIC_DUPLICATE_DECISION.value,),
                    title="Semantic duplicate decision",
                    description=(
                        f"Decision {rec.decision_id!r} duplicates decision {seen[key]!r} "
                        f"for queue entry {rec.queue_entry_id!r}."
                    ),
                    source_id=seen[key],
                    target_id=rec.decision_id,
                    decision_id=rec.decision_id,
                    queue_entry_id=rec.queue_entry_id,
                    generated_at=generated_at,
                )
            )
        else:
            seen[key] = rec.decision_id
    return tuple(issues)


# ---------------------------------------------------------------------------
# Orphan detection
# ---------------------------------------------------------------------------

def _detect_orphan_decisions(
    records: tuple[HumanReviewDecisionRecord, ...],
    known_queue_entry_ids: frozenset[str],
    generated_at: datetime,
) -> tuple[HumanReviewDecisionIssue, ...]:
    """Detect decisions whose queue_entry_id is not in known queue entries."""
    issues: list[HumanReviewDecisionIssue] = []
    for rec in records:
        qid = rec.queue_entry_id.strip()
        if qid == "":
            continue
        if qid not in known_queue_entry_ids:
            issues.append(
                _make_issue(
                    issue_type=HumanReviewDecisionIssueType.ORPHAN_DECISION,
                    severity=HumanReviewDecisionSeverity.ADVISORY,
                    reason_codes=(HumanReviewDecisionReasonCode.ORPHAN_DECISION.value,),
                    title="Orphan decision record",
                    description=(
                        f"Decision {rec.decision_id!r} references queue entry {qid!r} "
                        f"which is not present in the input."
                    ),
                    source_id=rec.queue_entry_id,
                    decision_id=rec.decision_id,
                    queue_entry_id=rec.queue_entry_id,
                    generated_at=generated_at,
                )
            )
    return tuple(issues)

def _detect_orphan_links(
    links: tuple[HumanReviewDecisionLink, ...],
    known_ids: frozenset[str],
    generated_at: datetime,
) -> tuple[HumanReviewDecisionIssue, ...]:
    """Detect links whose source_id or target_id is not in known IDs."""
    issues: list[HumanReviewDecisionIssue] = []
    for lnk in links:
        src = lnk.source_id.strip()
        tgt = lnk.target_id.strip()
        if src and src not in known_ids:
            issues.append(
                _make_issue(
                    issue_type=HumanReviewDecisionIssueType.ORPHAN_LINK,
                    severity=HumanReviewDecisionSeverity.ADVISORY,
                    reason_codes=(HumanReviewDecisionReasonCode.ORPHAN_LINK.value,),
                    title="Orphan link",
                    description=(
                        f"Link {lnk.link_id!r} source {src!r} is not present in known IDs."
                    ),
                    source_id=lnk.source_id,
                    target_id=lnk.target_id,
                    generated_at=generated_at,
                )
            )
        if tgt and tgt not in known_ids:
            issues.append(
                _make_issue(
                    issue_type=HumanReviewDecisionIssueType.ORPHAN_LINK,
                    severity=HumanReviewDecisionSeverity.ADVISORY,
                    reason_codes=(HumanReviewDecisionReasonCode.ORPHAN_LINK.value,),
                    title="Orphan link",
                    description=(
                        f"Link {lnk.link_id!r} target {tgt!r} is not present in known IDs."
                    ),
                    source_id=lnk.source_id,
                    target_id=lnk.target_id,
                    generated_at=generated_at,
                )
            )
    return tuple(issues)


# ---------------------------------------------------------------------------
# Missing decision detection
# ---------------------------------------------------------------------------

def _detect_missing_decisions(
    refs: tuple[HumanReviewQueueEntryRef, ...],
    decisions_by_queue_entry: dict[str, list[HumanReviewDecisionRecord]],
    config: HumanReviewDecisionLogConfig,
    generated_at: datetime,
) -> tuple[HumanReviewDecisionIssue, ...]:
    """Detect queue entries with no decision when required."""
    issues: list[HumanReviewDecisionIssue] = []
    if not config.require_decision_for_all:
        return ()
    for ref in refs:
        qid = ref.queue_entry_id.strip()
        if qid == "":
            continue
        # Skip not_applicable/suppressed entries — they don't need decisions.
        if ref.entry_state.strip().lower() in ("not_applicable", "suppressed"):
            continue
        if qid not in decisions_by_queue_entry:
            issues.append(
                _make_issue(
                    issue_type=HumanReviewDecisionIssueType.MISSING_DECISION,
                    severity=HumanReviewDecisionSeverity.ADVISORY,
                    reason_codes=(HumanReviewDecisionReasonCode.MISSING_DECISION.value,),
                    title="Missing decision",
                    description=(
                        f"Queue entry {qid!r} has no decision record."
                    ),
                    queue_entry_id=qid,
                    generated_at=generated_at,
                )
            )
    return tuple(issues)


# ---------------------------------------------------------------------------
# Conflict detection
# ---------------------------------------------------------------------------

def _detect_conflicting_decisions(
    decisions_by_queue_entry: dict[str, list[HumanReviewDecisionRecord]],
    generated_at: datetime,
) -> tuple[HumanReviewDecisionIssue, ...]:
    """Detect conflicting decisions for the same queue_entry_id."""
    issues: list[HumanReviewDecisionIssue] = []
    for qid, recs in decisions_by_queue_entry.items():
        if len(recs) < 2:
            continue
        outcomes = {r.outcome.strip() for r in recs}
        if len(outcomes) > 1:
            issues.append(
                _make_issue(
                    issue_type=HumanReviewDecisionIssueType.CONFLICTING_DECISION,
                    severity=HumanReviewDecisionSeverity.ADVISORY,
                    reason_codes=(
                        HumanReviewDecisionReasonCode.CONFLICTING_DECISION.value,
                        HumanReviewDecisionReasonCode.CONFLICTING_OUTCOME.value,
                    ),
                    title="Conflicting decisions",
                    description=(
                        f"Queue entry {qid!r} has conflicting decision outcomes: "
                        f"{sorted(outcomes)}."
                    ),
                    queue_entry_id=qid,
                    generated_at=generated_at,
                )
            )
        reviewers_outcomes: dict[str, set[str]] = {}
        for r in recs:
            reviewer = r.reviewer.strip()
            if reviewer:
                reviewers_outcomes.setdefault(reviewer, set()).add(r.outcome.strip())
        for reviewer, rev_outcomes in reviewers_outcomes.items():
            if len(rev_outcomes) > 1:
                issues.append(
                    _make_issue(
                        issue_type=HumanReviewDecisionIssueType.CONFLICTING_OUTCOME,
                        severity=HumanReviewDecisionSeverity.ADVISORY,
                        reason_codes=(HumanReviewDecisionReasonCode.CONFLICTING_OUTCOME.value,),
                        title="Conflicting outcome from same reviewer",
                        description=(
                            f"Reviewer {reviewer!r} has conflicting outcomes for queue entry {qid!r}: "
                            f"{sorted(rev_outcomes)}."
                        ),
                        queue_entry_id=qid,
                        generated_at=generated_at,
                    )
                )
    return tuple(issues)


# ---------------------------------------------------------------------------
# Stale detection
# ---------------------------------------------------------------------------

def _is_stale(
    record_generated_at: datetime | None,
    report_generated_at: datetime,
    threshold_seconds: int,
) -> bool:
    """Return True if the record is older than the staleness threshold."""
    if record_generated_at is None or threshold_seconds <= 0:
        return False
    cutoff = report_generated_at - timedelta(seconds=threshold_seconds)
    return record_generated_at < cutoff

def _detect_stale_queue_entries(
    refs: tuple[HumanReviewQueueEntryRef, ...],
    generated_at: datetime,
    threshold_seconds: int,
) -> tuple[HumanReviewDecisionIssue, ...]:
    """Detect queue entries older than the staleness threshold."""
    issues: list[HumanReviewDecisionIssue] = []
    for ref in refs:
        if _is_stale(ref.generated_at, generated_at, threshold_seconds):
            issues.append(
                _make_issue(
                    issue_type=HumanReviewDecisionIssueType.STALE_QUEUE_ENTRY,
                    severity=HumanReviewDecisionSeverity.ADVISORY,
                    reason_codes=(HumanReviewDecisionReasonCode.STALE_QUEUE_ENTRY.value,),
                    title="Stale queue entry",
                    description=(
                        f"Queue entry {ref.queue_entry_id!r} is older than the configured staleness threshold."
                    ),
                    queue_entry_id=ref.queue_entry_id,
                    generated_at=generated_at,
                )
            )
    return tuple(issues)

def _detect_stale_decisions(
    records: tuple[HumanReviewDecisionRecord, ...],
    generated_at: datetime,
    threshold_seconds: int,
) -> tuple[HumanReviewDecisionIssue, ...]:
    """Detect decision records older than the staleness threshold."""
    issues: list[HumanReviewDecisionIssue] = []
    for rec in records:
        if _is_stale(rec.generated_at, generated_at, threshold_seconds):
            issues.append(
                _make_issue(
                    issue_type=HumanReviewDecisionIssueType.STALE_DECISION,
                    severity=HumanReviewDecisionSeverity.ADVISORY,
                    reason_codes=(HumanReviewDecisionReasonCode.STALE_DECISION.value,),
                    title="Stale decision",
                    description=(
                        f"Decision {rec.decision_id!r} is older than the configured staleness threshold."
                    ),
                    decision_id=rec.decision_id,
                    queue_entry_id=rec.queue_entry_id,
                    generated_at=generated_at,
                )
            )
    return tuple(issues)


# ---------------------------------------------------------------------------
# Missing metadata detection
# ---------------------------------------------------------------------------

def _detect_missing_metadata(
    records: tuple[HumanReviewDecisionRecord, ...],
    generated_at: datetime,
) -> tuple[HumanReviewDecisionIssue, ...]:
    """Detect decisions with missing required metadata."""
    issues: list[HumanReviewDecisionIssue] = []
    for rec in records:
        if not rec.queue_entry_id.strip():
            issues.append(
                _make_issue(
                    issue_type=HumanReviewDecisionIssueType.MISSING_QUEUE_ENTRY_ID,
                    severity=HumanReviewDecisionSeverity.ADVISORY,
                    reason_codes=(HumanReviewDecisionReasonCode.MISSING_QUEUE_ENTRY_ID.value,),
                    title="Missing queue_entry_id",
                    description=f"Decision {rec.decision_id!r} has no queue_entry_id.",
                    decision_id=rec.decision_id,
                    generated_at=generated_at,
                )
            )
        if not rec.reviewer.strip():
            issues.append(
                _make_issue(
                    issue_type=HumanReviewDecisionIssueType.MISSING_REVIEWER,
                    severity=HumanReviewDecisionSeverity.ADVISORY,
                    reason_codes=(HumanReviewDecisionReasonCode.MISSING_REVIEWER.value,),
                    title="Missing reviewer",
                    description=f"Decision {rec.decision_id!r} has no reviewer.",
                    decision_id=rec.decision_id,
                    queue_entry_id=rec.queue_entry_id,
                    generated_at=generated_at,
                )
            )
        if rec.decided_at is None:
            issues.append(
                _make_issue(
                    issue_type=HumanReviewDecisionIssueType.MISSING_DECIDED_AT,
                    severity=HumanReviewDecisionSeverity.ADVISORY,
                    reason_codes=(HumanReviewDecisionReasonCode.MISSING_DECIDED_AT.value,),
                    title="Missing decided_at",
                    description=f"Decision {rec.decision_id!r} has no decided_at timestamp.",
                    decision_id=rec.decision_id,
                    queue_entry_id=rec.queue_entry_id,
                    generated_at=generated_at,
                )
            )
        if not rec.rationale.strip():
            issues.append(
                _make_issue(
                    issue_type=HumanReviewDecisionIssueType.MISSING_RATIONALE,
                    severity=HumanReviewDecisionSeverity.ADVISORY,
                    reason_codes=(HumanReviewDecisionReasonCode.MISSING_RATIONALE.value,),
                    title="Missing rationale",
                    description=f"Decision {rec.decision_id!r} has no rationale.",
                    decision_id=rec.decision_id,
                    queue_entry_id=rec.queue_entry_id,
                    generated_at=generated_at,
                )
            )
        if not rec.outcome.strip() or rec.outcome.strip().lower() == "unknown":
            issues.append(
                _make_issue(
                    issue_type=HumanReviewDecisionIssueType.MISSING_OUTCOME,
                    severity=HumanReviewDecisionSeverity.ADVISORY,
                    reason_codes=(HumanReviewDecisionReasonCode.MISSING_OUTCOME.value,),
                    title="Missing outcome",
                    description=f"Decision {rec.decision_id!r} has no outcome or outcome is unknown.",
                    decision_id=rec.decision_id,
                    queue_entry_id=rec.queue_entry_id,
                    generated_at=generated_at,
                )
            )
    return tuple(issues)


# ---------------------------------------------------------------------------
# Outcome mismatch detection
# ---------------------------------------------------------------------------

def _detect_outcome_mismatch(
    refs_by_id: dict[str, HumanReviewQueueEntryRef],
    decisions_by_queue_entry: dict[str, list[HumanReviewDecisionRecord]],
    generated_at: datetime,
) -> tuple[HumanReviewDecisionIssue, ...]:
    """Detect decisions whose outcome conflicts with queue entry state/severity."""
    issues: list[HumanReviewDecisionIssue] = []
    for qid, ref in refs_by_id.items():
        recs = decisions_by_queue_entry.get(qid)
        if not recs:
            continue
        normalized_severity = ref.severity.strip().lower()
        normalized_state = ref.entry_state.strip().lower()
        for rec in recs:
            outcome = rec.outcome.strip().lower()
            if outcome == HumanReviewDecisionOutcome.ACCEPTED_FOR_AUDIT_LOG.value:
                if normalized_state == "blocked" or normalized_severity == "blocking":
                    issues.append(
                        _make_issue(
                            issue_type=HumanReviewDecisionIssueType.OUTCOME_MISMATCH,
                            severity=HumanReviewDecisionSeverity.ADVISORY,
                            reason_codes=(HumanReviewDecisionReasonCode.OUTCOME_MISMATCH.value,),
                            title="Outcome mismatch",
                            description=(
                                f"Decision {rec.decision_id!r} outcome ACCEPTED_FOR_AUDIT_LOG "
                                f"conflicts with queue entry {qid!r} state={ref.entry_state!r} "
                                f"severity={ref.severity!r}."
                            ),
                            decision_id=rec.decision_id,
                            queue_entry_id=qid,
                            generated_at=generated_at,
                        )
                    )
    return tuple(issues)


# ---------------------------------------------------------------------------
# Superseded detection
# ---------------------------------------------------------------------------

def _is_superseded(decisions: list[HumanReviewDecisionRecord]) -> bool:
    """Return True if there are multiple decisions with different decided_at times."""
    if len(decisions) < 2:
        return False
    decided_ats = {d.decided_at for d in decisions if d.decided_at is not None}
    return len(decided_ats) > 1


# ---------------------------------------------------------------------------
# Decision result assignment (first-match-wins precedence)
# ---------------------------------------------------------------------------

def _assign_decision_result(
    ref: HumanReviewQueueEntryRef,
    decisions_for_entry: list[HumanReviewDecisionRecord],
    issues_for_entry: list[HumanReviewDecisionIssue],
    config: HumanReviewDecisionLogConfig,
    generated_at: datetime,
    duplicate_id_blocked: bool,
) -> HumanReviewDecisionResult:
    """Assign exactly one decision result using first-match-wins precedence."""
    qid = ref.queue_entry_id.strip()

    has_unsafe = any(
        i.issue_type == HumanReviewDecisionIssueType.UNSAFE_CONTENT.value
        or i.issue_type == HumanReviewDecisionIssueType.FORBIDDEN_TERM.value
        for i in issues_for_entry
    )
    has_conflict = any(
        i.issue_type in (
            HumanReviewDecisionIssueType.CONFLICTING_DECISION.value,
            HumanReviewDecisionIssueType.CONFLICTING_OUTCOME.value,
        )
        for i in issues_for_entry
    )
    has_semantic_dup = any(
        i.issue_type == HumanReviewDecisionIssueType.SEMANTIC_DUPLICATE_DECISION.value
        for i in issues_for_entry
    )
    has_stale_queue = any(
        i.issue_type == HumanReviewDecisionIssueType.STALE_QUEUE_ENTRY.value
        for i in issues_for_entry
    )
    has_stale_decision = any(
        i.issue_type == HumanReviewDecisionIssueType.STALE_DECISION.value
        for i in issues_for_entry
    )
    has_missing_metadata = any(
        i.issue_type in (
            HumanReviewDecisionIssueType.MISSING_REVIEWER.value,
            HumanReviewDecisionIssueType.MISSING_DECIDED_AT.value,
            HumanReviewDecisionIssueType.MISSING_RATIONALE.value,
            HumanReviewDecisionIssueType.MISSING_OUTCOME.value,
            HumanReviewDecisionIssueType.MISSING_QUEUE_ENTRY_ID.value,
        )
        for i in issues_for_entry
    )
    has_outcome_mismatch = any(
        i.issue_type == HumanReviewDecisionIssueType.OUTCOME_MISMATCH.value
        for i in issues_for_entry
    )

    normalized_state = ref.entry_state.strip().lower()
    decision_ids = tuple(sorted(d.decision_id for d in decisions_for_entry))
    primary_decision = decisions_for_entry[0] if decisions_for_entry else None

    decision_state = HumanReviewDecisionState.MISSING.value
    decision_outcome = HumanReviewDecisionOutcome.UNKNOWN.value
    decision_validity = HumanReviewDecisionValidity.INVALID_FOR_AUDIT_LOG.value
    severity = HumanReviewDecisionSeverity.INFO.value
    reviewer = ""
    decided_at: datetime | None = None
    rationale = ""
    reason_codes: list[str] = []

    if primary_decision:
        decision_outcome = primary_decision.outcome.strip().lower() or HumanReviewDecisionOutcome.UNKNOWN.value
        reviewer = primary_decision.reviewer
        decided_at = primary_decision.decided_at
        rationale = primary_decision.rationale

    # 1. NOT_APPLICABLE
    if normalized_state in ("not_applicable", "suppressed"):
        decision_state = HumanReviewDecisionState.NOT_APPLICABLE.value
        decision_outcome = HumanReviewDecisionOutcome.NOT_APPLICABLE.value
        decision_validity = HumanReviewDecisionValidity.NOT_APPLICABLE.value
        severity = HumanReviewDecisionSeverity.INFO.value
        reason_codes.append(HumanReviewDecisionReasonCode.NOT_APPLICABLE.value)
    elif not config.require_decision_for_all and not decisions_for_entry:
        decision_state = HumanReviewDecisionState.NOT_APPLICABLE.value
        decision_outcome = HumanReviewDecisionOutcome.NOT_APPLICABLE.value
        decision_validity = HumanReviewDecisionValidity.NOT_APPLICABLE.value
        severity = HumanReviewDecisionSeverity.INFO.value
        reason_codes.append(HumanReviewDecisionReasonCode.NOT_APPLICABLE.value)
    # 3. BLOCKED
    elif has_unsafe or duplicate_id_blocked:
        decision_state = HumanReviewDecisionState.BLOCKED.value
        decision_validity = HumanReviewDecisionValidity.INVALID_FOR_AUDIT_LOG.value
        severity = HumanReviewDecisionSeverity.BLOCKING.value
        reason_codes.append(HumanReviewDecisionReasonCode.SAFETY_BLOCKED.value)
    # 4. DISPUTED
    elif has_conflict:
        decision_state = HumanReviewDecisionState.DISPUTED.value
        decision_outcome = HumanReviewDecisionOutcome.DISPUTED.value
        decision_validity = HumanReviewDecisionValidity.DISPUTED.value
        severity = HumanReviewDecisionSeverity.ADVISORY.value
        reason_codes.append(HumanReviewDecisionReasonCode.CONFLICTING_DECISION.value)
    # 5. DUPLICATE
    elif has_semantic_dup:
        decision_state = HumanReviewDecisionState.DUPLICATE.value
        decision_validity = HumanReviewDecisionValidity.PARTIAL.value
        severity = HumanReviewDecisionSeverity.INFO.value
        reason_codes.append(HumanReviewDecisionReasonCode.SEMANTIC_DUPLICATE_DECISION.value)
    # 6. REJECTED
    elif decision_outcome == HumanReviewDecisionOutcome.REJECTED_FOR_AUDIT_LOG.value:
        decision_state = HumanReviewDecisionState.REJECTED.value
        decision_validity = HumanReviewDecisionValidity.VALID_FOR_AUDIT_LOG.value
        severity = HumanReviewDecisionSeverity.INFO.value
        reason_codes.append(HumanReviewDecisionReasonCode.DECISION_LOGGED.value)
    # 7. STALE
    elif has_stale_queue or has_stale_decision:
        decision_state = HumanReviewDecisionState.STALE.value
        decision_validity = HumanReviewDecisionValidity.STALE.value
        severity = HumanReviewDecisionSeverity.ADVISORY.value
        reason_codes.append(HumanReviewDecisionReasonCode.STALE_DECISION.value)
    # 8. MISSING
    elif not decisions_for_entry and config.require_decision_for_all:
        decision_state = HumanReviewDecisionState.MISSING.value
        decision_outcome = HumanReviewDecisionOutcome.UNKNOWN.value
        decision_validity = HumanReviewDecisionValidity.INVALID_FOR_AUDIT_LOG.value
        severity = HumanReviewDecisionSeverity.ADVISORY.value
        reason_codes.append(HumanReviewDecisionReasonCode.MISSING_DECISION.value)
    # 9. INCOMPLETE
    elif has_missing_metadata:
        decision_state = HumanReviewDecisionState.INCOMPLETE.value
        decision_validity = HumanReviewDecisionValidity.PARTIAL.value
        severity = HumanReviewDecisionSeverity.ADVISORY.value
        reason_codes.append(HumanReviewDecisionReasonCode.MISSING_REVIEWER.value)
    # 10. PENDING_REVIEW
    elif decision_outcome in (
        HumanReviewDecisionOutcome.NEEDS_MORE_REVIEW.value,
        HumanReviewDecisionOutcome.UNKNOWN.value,
    ):
        decision_state = HumanReviewDecisionState.PENDING_REVIEW.value
        decision_validity = HumanReviewDecisionValidity.PENDING_REVIEW.value
        severity = HumanReviewDecisionSeverity.ADVISORY.value
        reason_codes.append(HumanReviewDecisionReasonCode.ADVISORY_FINDING.value)
    # 11. SUPERSEDED
    elif _is_superseded(decisions_for_entry):
        decision_state = HumanReviewDecisionState.SUPERSEDED.value
        decision_validity = HumanReviewDecisionValidity.VALID_FOR_AUDIT_LOG.value
        severity = HumanReviewDecisionSeverity.INFO.value
        reason_codes.append(HumanReviewDecisionReasonCode.INFO_FINDING.value)
    # 12. LOGGED
    else:
        decision_state = HumanReviewDecisionState.LOGGED.value
        decision_validity = HumanReviewDecisionValidity.VALID_FOR_AUDIT_LOG.value
        severity = HumanReviewDecisionSeverity.INFO.value
        reason_codes.append(HumanReviewDecisionReasonCode.DECISION_LOGGED.value)

    if has_outcome_mismatch and decision_state != HumanReviewDecisionState.BLOCKED.value:
        reason_codes.append(HumanReviewDecisionReasonCode.OUTCOME_MISMATCH.value)
        if severity == HumanReviewDecisionSeverity.INFO.value:
            severity = HumanReviewDecisionSeverity.ADVISORY.value

    result = HumanReviewDecisionResult(
        decision_result_id="",
        queue_entry_id=qid,
        decision_ids=decision_ids,
        decision_state=decision_state,
        decision_outcome=decision_outcome,
        decision_validity=decision_validity,
        severity=severity,
        reason_codes=tuple(reason_codes),
        reviewer=reviewer,
        decided_at=decided_at,
        rationale=rationale,
        generated_at=generated_at,
    )
    result_id = _build_decision_result_id(
        queue_entry_id=qid,
        decision_ids=decision_ids,
        decision_state=decision_state,
        decision_outcome=decision_outcome,
        decision_validity=decision_validity,
        generated_at=generated_at,
    )
    return replace(result, decision_result_id=result_id)


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def _compute_aggregate_state(
    issues: tuple[HumanReviewDecisionIssue, ...],
    config: HumanReviewDecisionLogConfig,
    empty_input: bool,
) -> HumanReviewDecisionLogState:
    """Compute the aggregate report state from issues."""
    if empty_input:
        return HumanReviewDecisionLogState.NOT_APPLICABLE

    has_blocking = False
    has_degrading = False

    for issue in issues:
        if issue.severity == HumanReviewDecisionSeverity.BLOCKING.value:
            has_blocking = True
            break
        if issue.severity == HumanReviewDecisionSeverity.ADVISORY.value:
            has_degrading = True

    if has_blocking:
        return HumanReviewDecisionLogState.BLOCKED
    if has_degrading:
        if config.strict:
            return HumanReviewDecisionLogState.BLOCKED
        return HumanReviewDecisionLogState.DEGRADED
    return HumanReviewDecisionLogState.OK


# ---------------------------------------------------------------------------
# Data quality
# ---------------------------------------------------------------------------

def _build_data_quality(
    refs: tuple[HumanReviewQueueEntryRef, ...],
    records: tuple[HumanReviewDecisionRecord, ...],
    links: tuple[HumanReviewDecisionLink, ...],
    issues: tuple[HumanReviewDecisionIssue, ...],
    results: tuple[HumanReviewDecisionResult, ...],
    duplicate_queue_entry_ids: tuple[str, ...],
    duplicate_decision_ids: tuple[str, ...],
    duplicate_link_ids: tuple[str, ...],
) -> HumanReviewDecisionLogDataQuality:
    """Build the data quality summary."""
    def _count_issue(issue_type: HumanReviewDecisionIssueType) -> int:
        return sum(1 for i in issues if i.issue_type == issue_type.value)

    def _count_state(state: HumanReviewDecisionState) -> int:
        return sum(1 for r in results if r.decision_state == state.value)

    blocking = sum(1 for i in issues if i.severity == HumanReviewDecisionSeverity.BLOCKING.value)
    advisory = sum(1 for i in issues if i.severity == HumanReviewDecisionSeverity.ADVISORY.value)
    info = sum(1 for i in issues if i.severity == HumanReviewDecisionSeverity.INFO.value)

    return HumanReviewDecisionLogDataQuality(
        total_queue_entry_refs=len(refs),
        total_decision_records=len(records),
        total_links=len(links),
        total_issues=len(issues),
        total_decision_results=len(results),
        duplicate_queue_entry_id_count=len(duplicate_queue_entry_ids),
        duplicate_decision_id_count=len(duplicate_decision_ids),
        duplicate_link_id_count=len(duplicate_link_ids),
        semantic_duplicate_decision_count=_count_issue(HumanReviewDecisionIssueType.SEMANTIC_DUPLICATE_DECISION),
        orphan_decision_count=_count_issue(HumanReviewDecisionIssueType.ORPHAN_DECISION),
        orphan_link_count=_count_issue(HumanReviewDecisionIssueType.ORPHAN_LINK),
        missing_decision_count=_count_issue(HumanReviewDecisionIssueType.MISSING_DECISION),
        conflicting_decision_count=_count_issue(HumanReviewDecisionIssueType.CONFLICTING_DECISION),
        conflicting_outcome_count=_count_issue(HumanReviewDecisionIssueType.CONFLICTING_OUTCOME),
        stale_queue_entry_count=_count_issue(HumanReviewDecisionIssueType.STALE_QUEUE_ENTRY),
        stale_decision_count=_count_issue(HumanReviewDecisionIssueType.STALE_DECISION),
        missing_reviewer_count=_count_issue(HumanReviewDecisionIssueType.MISSING_REVIEWER),
        missing_decided_at_count=_count_issue(HumanReviewDecisionIssueType.MISSING_DECIDED_AT),
        missing_rationale_count=_count_issue(HumanReviewDecisionIssueType.MISSING_RATIONALE),
        missing_outcome_count=_count_issue(HumanReviewDecisionIssueType.MISSING_OUTCOME),
        missing_queue_entry_id_count=_count_issue(HumanReviewDecisionIssueType.MISSING_QUEUE_ENTRY_ID),
        outcome_mismatch_count=_count_issue(HumanReviewDecisionIssueType.OUTCOME_MISMATCH),
        unsafe_content_count=_count_issue(HumanReviewDecisionIssueType.UNSAFE_CONTENT),
        forbidden_term_count=_count_issue(HumanReviewDecisionIssueType.FORBIDDEN_TERM),
        blocking_count=blocking,
        advisory_count=advisory,
        info_count=info,
        logged_count=_count_state(HumanReviewDecisionState.LOGGED),
        pending_review_count=_count_state(HumanReviewDecisionState.PENDING_REVIEW),
        rejected_count=_count_state(HumanReviewDecisionState.REJECTED),
        disputed_count=_count_state(HumanReviewDecisionState.DISPUTED),
        stale_count=_count_state(HumanReviewDecisionState.STALE),
        duplicate_count=_count_state(HumanReviewDecisionState.DUPLICATE),
        orphaned_count=_count_state(HumanReviewDecisionState.ORPHANED),
        superseded_count=_count_state(HumanReviewDecisionState.SUPERSEDED),
        not_applicable_count=_count_state(HumanReviewDecisionState.NOT_APPLICABLE),
        incomplete_count=_count_state(HumanReviewDecisionState.INCOMPLETE),
        missing_count=_count_state(HumanReviewDecisionState.MISSING),
        blocked_count=_count_state(HumanReviewDecisionState.BLOCKED),
    )


# ---------------------------------------------------------------------------
# Report-level reason codes
# ---------------------------------------------------------------------------

def _build_reason_codes(
    state: HumanReviewDecisionLogState,
    issues: tuple[HumanReviewDecisionIssue, ...],
    results: tuple[HumanReviewDecisionResult, ...],
) -> tuple[HumanReviewDecisionReasonCode, ...]:
    """Build deterministic report-level reason codes."""
    codes: set[str] = set()

    if state == HumanReviewDecisionLogState.NOT_APPLICABLE:
        codes.add(HumanReviewDecisionReasonCode.NOT_APPLICABLE.value)
    elif state == HumanReviewDecisionLogState.OK:
        codes.add(HumanReviewDecisionReasonCode.OK.value)
    elif state == HumanReviewDecisionLogState.DEGRADED:
        codes.add(HumanReviewDecisionReasonCode.CONSISTENCY_DEGRADED.value)

    for issue in issues:
        for code in issue.reason_codes:
            codes.add(code)
    for result in results:
        for code in result.reason_codes:
            codes.add(code)

    if state == HumanReviewDecisionLogState.BLOCKED:
        codes.add(HumanReviewDecisionReasonCode.SAFETY_BLOCKED.value)

    ordered = [code for code in HumanReviewDecisionReasonCode if code.value in codes]
    return tuple(ordered)


# ---------------------------------------------------------------------------
# Public engine function
# ---------------------------------------------------------------------------

def build_human_review_decision_log_report(
    input: HumanReviewDecisionLogInput,
    config: HumanReviewDecisionLogConfig | None = None,
) -> HumanReviewDecisionLogReport:
    """Build a deterministic human review decision log report from in-memory records."""
    if config is None:
        config = input.config

    generated_at = _resolve_generated_at(input)

    # Empty input -> deterministic NOT_APPLICABLE report.
    if not input.queue_entry_refs and not input.decision_records:
        if config.empty_input_is_not_applicable:
            return HumanReviewDecisionLogReport(
                report_id=_build_report_id(input, generated_at),
                generated_at=generated_at,
                state=HumanReviewDecisionLogState.NOT_APPLICABLE,
                project_version=input.project_version,
                queue_entry_refs=(),
                decision_records=(),
                links=(),
                issues=(),
                decision_results=(),
                data_quality=HumanReviewDecisionLogDataQuality(),
                safety_flags=HumanReviewDecisionLogSafetyFlags(),
                reason_codes=(HumanReviewDecisionReasonCode.NOT_APPLICABLE,),
                metadata=input.metadata,
                safety_notice=SAFETY_NOTICE,
                notes="No queue entry refs or decision records provided; decision log is not applicable.",
            )

    # Safety scan (fail-closed).
    unsafe = _has_unsafe_content(input)
    if unsafe:
        return HumanReviewDecisionLogReport.blocked(
            input=input,
            reason_code=HumanReviewDecisionReasonCode.UNSAFE_CONTENT,
            notes="Report blocked due to unsafe content in caller-provided input.",
        )

    forbidden = False
    if config.forbid_action_terms:
        forbidden = _has_forbidden_terms(input)
        if forbidden:
            return HumanReviewDecisionLogReport.blocked(
                input=input,
                reason_code=HumanReviewDecisionReasonCode.FORBIDDEN_TERM_PRESENT,
                notes="Report blocked due to forbidden action terms in caller-provided input.",
            )

    # Duplicate ID detection (fail-closed).
    duplicate_queue_entry_ids = _find_duplicate_queue_entry_ids(input.queue_entry_refs)
    if duplicate_queue_entry_ids:
        return HumanReviewDecisionLogReport.blocked(
            input=input,
            reason_code=HumanReviewDecisionReasonCode.DUPLICATE_QUEUE_ENTRY_ID,
            notes="Report blocked due to duplicate queue entry IDs in caller-provided input.",
        )

    duplicate_decision_ids = _find_duplicate_decision_ids(input.decision_records)
    if duplicate_decision_ids:
        return HumanReviewDecisionLogReport.blocked(
            input=input,
            reason_code=HumanReviewDecisionReasonCode.DUPLICATE_DECISION_ID,
            notes="Report blocked due to duplicate decision IDs in caller-provided input.",
        )

    duplicate_link_ids = _find_duplicate_link_ids(input.links)
    if duplicate_link_ids:
        return HumanReviewDecisionLogReport.blocked(
            input=input,
            reason_code=HumanReviewDecisionReasonCode.DUPLICATE_LINK_ID,
            notes="Report blocked due to duplicate link IDs in caller-provided input.",
        )

    # Build lookup maps.
    queue_entry_ids = frozenset(
        ref.queue_entry_id.strip() for ref in input.queue_entry_refs if ref.queue_entry_id.strip()
    )
    refs_by_id: dict[str, HumanReviewQueueEntryRef] = {
        ref.queue_entry_id.strip(): ref for ref in input.queue_entry_refs
    }
    all_known_ids = queue_entry_ids | frozenset(
        rec.decision_id.strip() for rec in input.decision_records if rec.decision_id.strip()
    )

    # Group decisions by queue_entry_id.
    decisions_by_queue_entry: dict[str, list[HumanReviewDecisionRecord]] = {}
    for rec in input.decision_records:
        qid = rec.queue_entry_id.strip()
        if qid:
            decisions_by_queue_entry.setdefault(qid, []).append(rec)

    # Sort decisions within each entry by decided_at (newest first) then decision_id.
    for qid in decisions_by_queue_entry:
        decisions_by_queue_entry[qid].sort(
            key=lambda d: (d.decided_at or datetime.min.replace(tzinfo=timezone.utc), d.decision_id),
            reverse=True,
        )

    # Detect issues.
    all_issues: list[HumanReviewDecisionIssue] = []

    # Semantic duplicate detection.
    all_issues.extend(_detect_semantic_duplicate_decisions(input.decision_records, generated_at))

    # Orphan detection.
    all_issues.extend(_detect_orphan_decisions(input.decision_records, queue_entry_ids, generated_at))
    all_issues.extend(_detect_orphan_links(input.links, all_known_ids, generated_at))

    # Missing decision detection.
    all_issues.extend(_detect_missing_decisions(
        input.queue_entry_refs, decisions_by_queue_entry, config, generated_at
    ))

    # Conflict detection.
    all_issues.extend(_detect_conflicting_decisions(decisions_by_queue_entry, generated_at))

    # Stale detection.
    all_issues.extend(_detect_stale_queue_entries(
        input.queue_entry_refs, generated_at, config.staleness_threshold_seconds
    ))
    all_issues.extend(_detect_stale_decisions(
        input.decision_records, generated_at, config.staleness_threshold_seconds
    ))

    # Missing metadata detection.
    all_issues.extend(_detect_missing_metadata(input.decision_records, generated_at))

    # Outcome mismatch detection.
    all_issues.extend(_detect_outcome_mismatch(refs_by_id, decisions_by_queue_entry, generated_at))

    # Group issues by queue_entry_id for decision result assignment.
    issues_by_queue_entry: dict[str, list[HumanReviewDecisionIssue]] = {}
    for issue in all_issues:
        qid = issue.queue_entry_id.strip()
        if qid:
            issues_by_queue_entry.setdefault(qid, []).append(issue)

    # Build decision results — one per queue entry.
    results: list[HumanReviewDecisionResult] = []
    for ref in input.queue_entry_refs:
        qid = ref.queue_entry_id.strip()
        if not qid:
            continue
        decisions_for_entry = decisions_by_queue_entry.get(qid, [])
        issues_for_entry = issues_by_queue_entry.get(qid, [])
        result = _assign_decision_result(
            ref=ref,
            decisions_for_entry=decisions_for_entry,
            issues_for_entry=issues_for_entry,
            config=config,
            generated_at=generated_at,
            duplicate_id_blocked=False,
        )
        results.append(result)

    # Build ORPHANED results for decision records referencing unknown queue entries.
    # Links are opaque; we only create results from decision records because only
    # decisions explicitly carry a queue_entry_id field.
    orphan_queue_entry_ids = {
        qid for qid in decisions_by_queue_entry if qid not in queue_entry_ids and qid
    }
    for qid in sorted(orphan_queue_entry_ids):
        orphan_decisions = decisions_by_queue_entry[qid]
        decision_ids = tuple(sorted(d.decision_id for d in orphan_decisions))
        primary_decision = orphan_decisions[0] if orphan_decisions else None
        decision_outcome = (
            primary_decision.outcome.strip().lower()
            if primary_decision and primary_decision.outcome.strip()
            else HumanReviewDecisionOutcome.UNKNOWN.value
        )
        rationale = (
            primary_decision.rationale
            if primary_decision and primary_decision.rationale.strip()
            else "Decision record(s) reference an unknown queue entry."
        )
        orphan_result = HumanReviewDecisionResult(
            decision_result_id="",
            queue_entry_id=qid,
            decision_ids=decision_ids,
            decision_state=HumanReviewDecisionState.ORPHANED.value,
            decision_outcome=decision_outcome,
            decision_validity=HumanReviewDecisionValidity.INVALID_FOR_AUDIT_LOG.value,
            severity=HumanReviewDecisionSeverity.ADVISORY.value,
            reason_codes=(HumanReviewDecisionReasonCode.ORPHAN_DECISION.value,),
            reviewer=primary_decision.reviewer if primary_decision else "",
            decided_at=primary_decision.decided_at if primary_decision else None,
            rationale=rationale,
            generated_at=generated_at,
        )
        result_id = _build_decision_result_id(
            queue_entry_id=qid,
            decision_ids=decision_ids,
            decision_state=HumanReviewDecisionState.ORPHANED.value,
            decision_outcome=decision_outcome,
            decision_validity=HumanReviewDecisionValidity.INVALID_FOR_AUDIT_LOG.value,
            generated_at=generated_at,
        )
        orphan_result = replace(orphan_result, decision_result_id=result_id)
        results.append(orphan_result)

    # Sort deterministically.
    sorted_refs = tuple(sorted(input.queue_entry_refs, key=lambda r: r.queue_entry_id))
    sorted_records = tuple(sorted(input.decision_records, key=lambda r: r.decision_id))
    sorted_links = tuple(sorted(
        input.links,
        key=lambda l: (l.source_id, l.target_id, l.link_type, l.link_id),
    ))
    sorted_issues = tuple(sorted(
        all_issues,
        key=lambda i: (
            i.severity,
            i.issue_type,
            i.source_id,
            i.title,
            i.issue_id,
        ),
    ))
    sorted_results = tuple(sorted(results, key=lambda r: r.queue_entry_id))

    # Aggregate state.
    empty_input = (
        not input.queue_entry_refs
        and not input.decision_records
        and config.empty_input_is_not_applicable
    )
    state = _compute_aggregate_state(sorted_issues, config, empty_input)

    # Build data quality.
    data_quality = _build_data_quality(
        sorted_refs,
        sorted_records,
        sorted_links,
        sorted_issues,
        sorted_results,
        duplicate_queue_entry_ids,
        duplicate_decision_ids,
        duplicate_link_ids,
    )

    # Build reason codes.
    reason_codes = _build_reason_codes(state, sorted_issues, sorted_results)

    safety_flags = HumanReviewDecisionLogSafetyFlags(
        has_unsafe_content=unsafe,
        has_forbidden_terms=forbidden,
    )

    return HumanReviewDecisionLogReport(
        report_id=_build_report_id(input, generated_at),
        generated_at=generated_at,
        state=state,
        project_version=input.project_version,
        queue_entry_refs=sorted_refs,
        decision_records=sorted_records,
        links=sorted_links,
        issues=sorted_issues,
        decision_results=sorted_results,
        data_quality=data_quality,
        safety_flags=safety_flags,
        reason_codes=reason_codes,
        metadata=input.metadata,
        safety_notice=SAFETY_NOTICE,
        notes="",
    )