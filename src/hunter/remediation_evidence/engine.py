"""In-memory engine for hunter.remediation_evidence package.

MVP-38 — Local Research Remediation Evidence Tracker.

The engine receives only caller-provided in-memory input. It never inspects the
filesystem, imports prior packages, or traverses any path or reference string.
It never emits executable remediation actions, shell commands, code patches, or
infrastructure changes.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from json import dumps
from typing import Any

from hunter.remediation_backlog.models import RemediationBacklogItemState
from hunter.remediation_evidence.models import (
    FORBIDDEN_REMEDIATION_EVIDENCE_TERMS,
    REMEDIATION_EVIDENCE_VERSION,
    RemediationBacklogItemRef,
    RemediationEvidenceConfig,
    RemediationEvidenceCoverageResult,
    RemediationEvidenceCoverageState,
    RemediationEvidenceDataQuality,
    RemediationEvidenceInput,
    RemediationEvidenceIssue,
    RemediationEvidenceIssueType,
    RemediationEvidenceLink,
    RemediationEvidenceLinkType,
    RemediationEvidenceReasonCode,
    RemediationEvidenceRecord,
    RemediationEvidenceRecordState,
    RemediationEvidenceReport,
    RemediationEvidenceReviewOutcome,
    RemediationReviewRecord,
    RemediationEvidenceSafetyFlags,
    RemediationEvidenceSeverity,
    RemediationEvidenceState,
    _check_forbidden_mapping,
    _has_forbidden_term,
    has_unsafe_remediation_evidence_content,
)


SAFETY_NOTICE = (
    "This report is a local, audit-only research artifact. "
    "Evidence coverage is for human-audit tracking only and does not imply "
    "approval, certification, production readiness, trading readiness, "
    "recommendation, suitability, or signal validity."
)


# Reason-code sets used for aggregation.
_BLOCKING_REASON_CODES: frozenset[str] = frozenset({
    RemediationEvidenceReasonCode.UNSAFE_CONTENT.value,
    RemediationEvidenceReasonCode.FORBIDDEN_TERM_PRESENT.value,
    RemediationEvidenceReasonCode.DUPLICATE_ID.value,
    RemediationEvidenceReasonCode.CONFLICTING_REVIEW.value,
    RemediationEvidenceReasonCode.SAFETY_BLOCKED.value,
})


_ADVISORY_REASON_CODES: frozenset[str] = frozenset({
    RemediationEvidenceReasonCode.ORPHAN_EVIDENCE.value,
    RemediationEvidenceReasonCode.ORPHAN_REVIEW.value,
    RemediationEvidenceReasonCode.ORPHAN_LINK.value,
    RemediationEvidenceReasonCode.STALE_EVIDENCE.value,
    RemediationEvidenceReasonCode.STALE_REVIEW.value,
    RemediationEvidenceReasonCode.MISSING_EVIDENCE.value,
    RemediationEvidenceReasonCode.MISSING_REVIEW.value,
    RemediationEvidenceReasonCode.REJECTED_EVIDENCE.value,
    RemediationEvidenceReasonCode.PENDING_REVIEW_EVIDENCE.value,
    RemediationEvidenceReasonCode.BLOCKED_BACKLOG_ITEM.value,
    RemediationEvidenceReasonCode.OPEN_BACKLOG_ITEM.value,
    RemediationEvidenceReasonCode.CONSISTENCY_DEGRADED.value,
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


def _resolve_generated_at(input: RemediationEvidenceInput) -> datetime:
    """Return the effective generated_at timestamp."""
    return input.generated_at if input.generated_at is not None else datetime.now(timezone.utc)


def _has_unsafe_content(input: RemediationEvidenceInput) -> bool:
    """Return True if any metadata field contains unsafe non-string values."""
    if has_unsafe_remediation_evidence_content(dict(input.metadata)):
        return True
    for ref in input.backlog_item_refs:
        if has_unsafe_remediation_evidence_content(dict(ref.metadata)):
            return True
    for rec in input.evidence_records:
        if has_unsafe_remediation_evidence_content(dict(rec.metadata)):
            return True
    for rev in input.review_records:
        if has_unsafe_remediation_evidence_content(dict(rev.metadata)):
            return True
    for link in input.links:
        if has_unsafe_remediation_evidence_content(dict(link.metadata)):
            return True
    return False


def _has_forbidden_terms(input: RemediationEvidenceInput) -> bool:
    """Return True if any text field or metadata contains forbidden terms."""
    for ref in input.backlog_item_refs:
        for text in (ref.title, ref.description):
            if text and _has_forbidden_term(text, FORBIDDEN_REMEDIATION_EVIDENCE_TERMS):
                return True
        if _check_forbidden_mapping(ref.metadata, FORBIDDEN_REMEDIATION_EVIDENCE_TERMS):
            return True
    for rec in input.evidence_records:
        for text in (rec.title, rec.description):
            if text and _has_forbidden_term(text, FORBIDDEN_REMEDIATION_EVIDENCE_TERMS):
                return True
        if _check_forbidden_mapping(rec.metadata, FORBIDDEN_REMEDIATION_EVIDENCE_TERMS):
            return True
    for rev in input.review_records:
        for text in (rev.note,):
            if text and _has_forbidden_term(text, FORBIDDEN_REMEDIATION_EVIDENCE_TERMS):
                return True
        if _check_forbidden_mapping(rev.metadata, FORBIDDEN_REMEDIATION_EVIDENCE_TERMS):
            return True
    for link in input.links:
        if _check_forbidden_mapping(link.metadata, FORBIDDEN_REMEDIATION_EVIDENCE_TERMS):
            return True
    if _check_forbidden_mapping(input.metadata, FORBIDDEN_REMEDIATION_EVIDENCE_TERMS):
        return True
    return False


def _find_duplicate_ids(
    items: tuple[Any, ...],
    id_attr: str,
) -> tuple[str, ...]:
    """Return normalized IDs that appear more than once."""
    seen: set[str] = set()
    duplicates: set[str] = set()
    for item in items:
        item_id = str(getattr(item, id_attr)).strip()
        if item_id in seen:
            duplicates.add(item_id)
        else:
            seen.add(item_id)
    return tuple(sorted(duplicates))


def _build_report_id(input: RemediationEvidenceInput, generated_at: datetime) -> str:
    """Build a deterministic report_id from sorted IDs and metadata."""
    payload = {
        "backlog_item_ids": sorted(set(ref.backlog_item_id for ref in input.backlog_item_refs)),
        "evidence_ids": sorted(set(rec.evidence_id for rec in input.evidence_records)),
        "review_ids": sorted(set(rev.review_id for rev in input.review_records)),
        "link_ids": sorted(set(link.link_id for link in input.links)),
        "project_version": input.project_version,
        "generated_at": generated_at.isoformat(),
    }
    return _sha256_hex(_canonical_json(payload))


def _build_coverage_id(backlog_item_id: str, evidence_ids: tuple[str, ...], review_ids: tuple[str, ...]) -> str:
    """Build a deterministic coverage_id for a backlog item."""
    payload = {
        "backlog_item_id": backlog_item_id,
        "evidence_ids": sorted(evidence_ids),
        "review_ids": sorted(review_ids),
    }
    return _sha256_hex_16(_canonical_json(payload))


def _build_issue_id(issue: RemediationEvidenceIssue) -> str:
    """Build a deterministic issue_id from issue content."""
    payload = {
        "issue_type": issue.issue_type.value,
        "severity": issue.severity.value,
        "reason_codes": sorted(issue.reason_codes),
        "title": issue.title,
        "description": issue.description,
        "evidence_id": issue.evidence_id,
        "backlog_item_id": issue.backlog_item_id,
        "review_id": issue.review_id,
        "link_id": issue.link_id,
    }
    return _sha256_hex_16(_canonical_json(payload))


def _evidence_content_hash(record: RemediationEvidenceRecord) -> str:
    """Build a deterministic content hash for duplicate evidence detection."""
    metadata = dict(record.metadata) if record.metadata else {}
    payload = {
        "backlog_item_id": record.backlog_item_id,
        "title": record.title,
        "description": record.description,
        "evidence_state": record.evidence_state.value,
        "metadata": sorted((str(k), str(v)) for k, v in metadata.items()),
    }
    return _sha256_hex_16(_canonical_json(payload))


def _make_issue(
    *,
    issue_type: RemediationEvidenceIssueType,
    severity: RemediationEvidenceSeverity,
    reason_codes: tuple[str, ...],
    title: str,
    description: str,
    evidence_id: str = "",
    backlog_item_id: str = "",
    review_id: str = "",
    link_id: str = "",
    generated_at: datetime,
) -> RemediationEvidenceIssue:
    """Create an issue with a deterministic ID."""
    issue = RemediationEvidenceIssue(
        issue_type=issue_type,
        severity=severity,
        reason_codes=reason_codes,
        title=title,
        description=description,
        evidence_id=evidence_id,
        backlog_item_id=backlog_item_id,
        review_id=review_id,
        link_id=link_id,
        generated_at=generated_at,
    )
    return replace(issue, issue_id=_build_issue_id(issue))

def build_remediation_evidence_report(
    input: RemediationEvidenceInput,
    config: RemediationEvidenceConfig | None = None,
    strict: bool | None = None,
) -> RemediationEvidenceReport:
    """Build a deterministic remediation evidence report from in-memory declarations."""
    if config is None:
        config = input.config
    if strict is not None:
        config = RemediationEvidenceConfig(
            strict=strict,
            require_review=config.require_review,
            require_evidence_for_all=config.require_evidence_for_all,
            required_backlog_item_ids=config.required_backlog_item_ids,
            staleness_threshold_seconds=config.staleness_threshold_seconds,
            forbid_action_terms=config.forbid_action_terms,
        )

    generated_at = _resolve_generated_at(input)

    if _has_unsafe_content(input):
        return RemediationEvidenceReport.blocked(
            input=input,
            reason_code=RemediationEvidenceReasonCode.UNSAFE_CONTENT,
            notes="Report blocked due to unsafe content in caller-provided input.",
        )

    if config.forbid_action_terms and _has_forbidden_terms(input):
        return RemediationEvidenceReport.blocked(
            input=input,
            reason_code=RemediationEvidenceReasonCode.FORBIDDEN_TERM_PRESENT,
            notes="Report blocked due to forbidden terms in caller-provided text fields or metadata.",
        )

    validation_report = _validate_input(input, config, generated_at)
    if validation_report is not None:
        return validation_report

    issues, dq_updates = _detect_issues(input, config, generated_at)
    coverage_results = _build_coverage_results(input, config, generated_at)
    report_state, state_reason_code = _aggregate_state(issues, len(input.backlog_item_refs), config.strict)
    reason_codes = _aggregate_reason_codes(issues, state_reason_code)
    data_quality = _build_data_quality(input, coverage_results, issues, dq_updates)
    safety_flags = _build_safety_flags(issues, config)

    sorted_backlog_item_refs = tuple(
        sorted(input.backlog_item_refs, key=lambda r: (r.backlog_item_id, r.source_id, r.finding_id))
    )
    sorted_evidence_records = tuple(
        sorted(input.evidence_records, key=lambda r: (r.evidence_id, r.backlog_item_id))
    )
    sorted_review_records = tuple(
        sorted(input.review_records, key=lambda r: (r.review_id, r.evidence_id))
    )
    sorted_links = tuple(
        sorted(input.links, key=lambda l: (l.link_id, l.evidence_id, l.backlog_item_id))
    )
    sorted_issues = tuple(
        sorted(issues, key=lambda i: (i.issue_id, i.issue_type.value, i.severity.value))
    )
    sorted_coverage_results = tuple(
        sorted(coverage_results, key=lambda c: (c.coverage_id, c.backlog_item_id))
    )

    return RemediationEvidenceReport(
        report_id=_build_report_id(input, generated_at),
        state=report_state,
        reason_codes=reason_codes,
        backlog_item_refs=sorted_backlog_item_refs,
        evidence_records=sorted_evidence_records,
        review_records=sorted_review_records,
        links=sorted_links,
        issues=sorted_issues,
        coverage_results=sorted_coverage_results,
        data_quality=data_quality,
        safety_flags=safety_flags,
        generated_at=generated_at,
        project_version=input.project_version,
        safety_notice=SAFETY_NOTICE,
        notes=(
            "Report output is for human audit only. "
            "Evidence coverage is for human-audit tracking only and does not imply approval, "
            "certification, production readiness, trading readiness, recommendation, suitability, "
            "or signal validity."
        ),
    )


def _validate_input(
    input: RemediationEvidenceInput,
    config: RemediationEvidenceConfig,
    generated_at: datetime,
) -> RemediationEvidenceReport | None:
    """Fail-closed validation for duplicate IDs."""
    duplicate_backlog_item_ids = _find_duplicate_ids(input.backlog_item_refs, "backlog_item_id")
    duplicate_evidence_ids = _find_duplicate_ids(input.evidence_records, "evidence_id")
    duplicate_review_ids = _find_duplicate_ids(input.review_records, "review_id")
    duplicate_link_ids = _find_duplicate_ids(input.links, "link_id")
    if any((duplicate_backlog_item_ids, duplicate_evidence_ids, duplicate_review_ids, duplicate_link_ids)):
        return RemediationEvidenceReport.blocked(
            input=input,
            reason_code=RemediationEvidenceReasonCode.DUPLICATE_ID,
            notes="Input validation failed: duplicate IDs detected.",
        )
    return None


def _detect_issues(
    input: RemediationEvidenceInput,
    config: RemediationEvidenceConfig,
    generated_at: datetime,
) -> tuple[tuple[RemediationEvidenceIssue, ...], dict[str, int]]:
    """Run all detection passes and return issues plus data-quality counters."""
    issues: list[RemediationEvidenceIssue] = []
    dq_updates: dict[str, int] = {}

    backlog_item_ids = {ref.backlog_item_id for ref in input.backlog_item_refs}
    evidence_ids = {rec.evidence_id for rec in input.evidence_records}
    evidence_by_id = {rec.evidence_id: rec for rec in input.evidence_records}
    review_by_id = {rev.review_id: rev for rev in input.review_records}
    evidence_reviews: defaultdict[str, list[RemediationReviewRecord]] = defaultdict(list)
    for rev in input.review_records:
        evidence_reviews[rev.evidence_id].append(rev)

    # Duplicate evidence by content hash.
    content_hash_to_ids: defaultdict[str, list[str]] = defaultdict(list)
    for rec in input.evidence_records:
        content_hash_to_ids[_evidence_content_hash(rec)].append(rec.evidence_id)
    duplicate_evidence_ids = {
        evidence_id
        for evidence_ids_group in content_hash_to_ids.values()
        for evidence_id in evidence_ids_group
        if len(evidence_ids_group) > 1
    }
    if duplicate_evidence_ids:
        dq_updates["duplicate_evidence_count"] = len(duplicate_evidence_ids)
        for evidence_id in sorted(duplicate_evidence_ids):
            issues.append(
                _make_issue(
                    issue_type=RemediationEvidenceIssueType.DUPLICATE_EVIDENCE,
                    severity=RemediationEvidenceSeverity.ADVISORY,
                    reason_codes=(RemediationEvidenceReasonCode.DUPLICATE_EVIDENCE.value,),
                    title="Duplicate evidence record",
                    description=f"Evidence record {evidence_id} has the same canonical content as another record.",
                    evidence_id=evidence_id,
                    generated_at=generated_at,
                )
            )

    # Orphan evidence records.
    orphan_evidence_ids = set()
    for rec in input.evidence_records:
        if rec.backlog_item_id and rec.backlog_item_id not in backlog_item_ids:
            orphan_evidence_ids.add(rec.evidence_id)
    dq_updates["orphan_evidence_count"] = len(orphan_evidence_ids)
    for evidence_id in sorted(orphan_evidence_ids):
        issues.append(
            _make_issue(
                issue_type=RemediationEvidenceIssueType.ORPHAN_EVIDENCE,
                severity=RemediationEvidenceSeverity.ADVISORY,
                reason_codes=(RemediationEvidenceReasonCode.ORPHAN_EVIDENCE.value,),
                title="Orphan evidence record",
                description=f"Evidence record {evidence_id} references an unknown backlog item.",
                evidence_id=evidence_id,
                generated_at=generated_at,
            )
        )

    # Orphan review records.
    orphan_review_ids = set()
    for rev in input.review_records:
        if rev.evidence_id not in evidence_ids:
            orphan_review_ids.add(rev.review_id)
    dq_updates["orphan_review_count"] = len(orphan_review_ids)
    for review_id in sorted(orphan_review_ids):
        issues.append(
            _make_issue(
                issue_type=RemediationEvidenceIssueType.ORPHAN_REVIEW,
                severity=RemediationEvidenceSeverity.ADVISORY,
                reason_codes=(RemediationEvidenceReasonCode.ORPHAN_REVIEW.value,),
                title="Orphan review record",
                description=f"Review record {review_id} references an unknown evidence record.",
                review_id=review_id,
                generated_at=generated_at,
            )
        )

    # Orphan links.
    orphan_link_ids = set()
    for link in input.links:
        if link.evidence_id not in evidence_ids or link.backlog_item_id not in backlog_item_ids:
            orphan_link_ids.add(link.link_id)
    dq_updates["orphan_link_count"] = len(orphan_link_ids)
    for link_id in sorted(orphan_link_ids):
        link = next(link for link in input.links if link.link_id == link_id)
        issues.append(
            _make_issue(
                issue_type=RemediationEvidenceIssueType.ORPHAN_LINK,
                severity=RemediationEvidenceSeverity.ADVISORY,
                reason_codes=(RemediationEvidenceReasonCode.ORPHAN_LINK.value,),
                title="Orphan evidence link",
                description=f"Link {link_id} references an unknown evidence or backlog item.",
                link_id=link_id,
                generated_at=generated_at,
            )
        )

    # Conflicting reviews.
    conflicting_evidence_ids = set()
    for evidence_id, reviews in evidence_reviews.items():
        outcomes = {rev.outcome for rev in reviews}
        if len(outcomes) > 1:
            conflicting_evidence_ids.add(evidence_id)
    dq_updates["conflicting_review_count"] = len(conflicting_evidence_ids)
    for evidence_id in sorted(conflicting_evidence_ids):
        issues.append(
            _make_issue(
                issue_type=RemediationEvidenceIssueType.CONFLICTING_REVIEW,
                severity=RemediationEvidenceSeverity.BLOCKING,
                reason_codes=(RemediationEvidenceReasonCode.CONFLICTING_REVIEW.value,),
                title="Conflicting review outcomes",
                description=f"Evidence record {evidence_id} has review records with conflicting outcomes.",
                evidence_id=evidence_id,
                generated_at=generated_at,
            )
        )

    # Stale evidence and reviews.
    staleness_threshold = timedelta(seconds=config.staleness_threshold_seconds)
    stale_evidence_ids = set()
    for rec in input.evidence_records:
        if rec.generated_at is not None and rec.generated_at < generated_at - staleness_threshold:
            stale_evidence_ids.add(rec.evidence_id)
    dq_updates["stale_evidence_count"] = len(stale_evidence_ids)
    for evidence_id in sorted(stale_evidence_ids):
        issues.append(
            _make_issue(
                issue_type=RemediationEvidenceIssueType.STALE_EVIDENCE,
                severity=RemediationEvidenceSeverity.ADVISORY,
                reason_codes=(RemediationEvidenceReasonCode.STALE_EVIDENCE.value,),
                title="Stale evidence record",
                description=f"Evidence record {evidence_id} is older than the staleness threshold.",
                evidence_id=evidence_id,
                generated_at=generated_at,
            )
        )

    stale_review_ids = set()
    for rev in input.review_records:
        if rev.generated_at is not None and rev.generated_at < generated_at - staleness_threshold:
            stale_review_ids.add(rev.review_id)
    dq_updates["stale_review_count"] = len(stale_review_ids)
    for review_id in sorted(stale_review_ids):
        issues.append(
            _make_issue(
                issue_type=RemediationEvidenceIssueType.STALE_REVIEW,
                severity=RemediationEvidenceSeverity.ADVISORY,
                reason_codes=(RemediationEvidenceReasonCode.STALE_REVIEW.value,),
                title="Stale review record",
                description=f"Review record {review_id} is older than the staleness threshold.",
                review_id=review_id,
                generated_at=generated_at,
            )
        )

    # Missing evidence for required backlog items.
    required_items = set(config.required_backlog_item_ids) if config.require_evidence_for_all or config.required_backlog_item_ids else set()
    if config.require_evidence_for_all:
        required_items.update(backlog_item_ids)
    linked_backlog_items = {
        rec.backlog_item_id for rec in input.evidence_records if rec.backlog_item_id in backlog_item_ids
    }
    linked_backlog_items.update(
        link.backlog_item_id for link in input.links if link.backlog_item_id in backlog_item_ids
    )
    missing_evidence_items = required_items - linked_backlog_items
    dq_updates["missing_evidence_count"] = len(missing_evidence_items)
    for backlog_item_id in sorted(missing_evidence_items):
        issues.append(
            _make_issue(
                issue_type=RemediationEvidenceIssueType.MISSING_EVIDENCE,
                severity=RemediationEvidenceSeverity.ADVISORY,
                reason_codes=(RemediationEvidenceReasonCode.MISSING_EVIDENCE.value,),
                title="Missing evidence",
                description=f"Backlog item {backlog_item_id} requires evidence but none is linked.",
                backlog_item_id=backlog_item_id,
                generated_at=generated_at,
            )
        )

    # Missing human review.
    if config.require_review:
        reviewed_evidence_ids = {
            rev.evidence_id for rev in input.review_records
            if rev.outcome is RemediationEvidenceReviewOutcome.ACCEPTED
        }
        missing_review_ids = {
            rec.evidence_id for rec in input.evidence_records
            if rec.evidence_id not in reviewed_evidence_ids
        }
    else:
        missing_review_ids = set()
    dq_updates["missing_review_count"] = len(missing_review_ids)
    for evidence_id in sorted(missing_review_ids):
        issues.append(
            _make_issue(
                issue_type=RemediationEvidenceIssueType.MISSING_REVIEW,
                severity=RemediationEvidenceSeverity.ADVISORY,
                reason_codes=(RemediationEvidenceReasonCode.MISSING_REVIEW.value,),
                title="Missing review",
                description=f"Evidence record {evidence_id} requires an accepted review.",
                evidence_id=evidence_id,
                generated_at=generated_at,
            )
        )

    # Rejected and pending-review evidence records.
    rejected_evidence_ids = {
        rec.evidence_id for rec in input.evidence_records
        if rec.evidence_state is RemediationEvidenceRecordState.REJECTED
    }
    dq_updates["rejected_evidence_count"] = len(rejected_evidence_ids)
    for evidence_id in sorted(rejected_evidence_ids):
        issues.append(
            _make_issue(
                issue_type=RemediationEvidenceIssueType.REJECTED_EVIDENCE,
                severity=RemediationEvidenceSeverity.ADVISORY,
                reason_codes=(RemediationEvidenceReasonCode.REJECTED_EVIDENCE.value,),
                title="Rejected evidence",
                description=f"Evidence record {evidence_id} is rejected.",
                evidence_id=evidence_id,
                generated_at=generated_at,
            )
        )

    pending_review_evidence_ids = {
        rec.evidence_id for rec in input.evidence_records
        if rec.evidence_state is RemediationEvidenceRecordState.PENDING_REVIEW
    }
    dq_updates["pending_review_evidence_count"] = len(pending_review_evidence_ids)
    for evidence_id in sorted(pending_review_evidence_ids):
        issues.append(
            _make_issue(
                issue_type=RemediationEvidenceIssueType.PENDING_REVIEW_EVIDENCE,
                severity=RemediationEvidenceSeverity.INFO,
                reason_codes=(RemediationEvidenceReasonCode.PENDING_REVIEW_EVIDENCE.value,),
                title="Pending-review evidence",
                description=f"Evidence record {evidence_id} is pending review.",
                evidence_id=evidence_id,
                generated_at=generated_at,
            )
        )

    # Backlog item state mismatches.
    blocked_backlog_item_count = 0
    open_backlog_item_count = 0
    for ref in input.backlog_item_refs:
        linked_evidence_ids = {
            rec.evidence_id for rec in input.evidence_records
            if rec.backlog_item_id == ref.backlog_item_id
        }
        linked_evidence_ids.update(
            link.evidence_id for link in input.links if link.backlog_item_id == ref.backlog_item_id
        )
        accepted_linked = any(
            evidence_by_id[eid].evidence_state is RemediationEvidenceRecordState.ACCEPTED
            for eid in linked_evidence_ids if eid in evidence_by_id
        )
        if ref.item_state is RemediationBacklogItemState.BLOCKED and accepted_linked:
            blocked_backlog_item_count += 1
            issues.append(
                _make_issue(
                    issue_type=RemediationEvidenceIssueType.BLOCKED_BACKLOG_ITEM,
                    severity=RemediationEvidenceSeverity.ADVISORY,
                    reason_codes=(RemediationEvidenceReasonCode.BLOCKED_BACKLOG_ITEM.value,),
                    title="Accepted evidence linked to blocked backlog item",
                    description=(
                        f"Backlog item {ref.backlog_item_id} is blocked but has accepted evidence. "
                        "Accepted evidence is accepted for audit tracking only and does not imply approval or readiness."
                    ),
                    backlog_item_id=ref.backlog_item_id,
                    generated_at=generated_at,
                )
            )
        elif ref.item_state is RemediationBacklogItemState.OPEN and accepted_linked:
            open_backlog_item_count += 1
            issues.append(
                _make_issue(
                    issue_type=RemediationEvidenceIssueType.OPEN_BACKLOG_ITEM,
                    severity=RemediationEvidenceSeverity.ADVISORY,
                    reason_codes=(RemediationEvidenceReasonCode.OPEN_BACKLOG_ITEM.value,),
                    title="Accepted evidence linked to open backlog item",
                    description=(
                        f"Backlog item {ref.backlog_item_id} is open but has accepted evidence. "
                        "Accepted evidence is accepted for audit tracking only and does not imply approval or readiness."
                    ),
                    backlog_item_id=ref.backlog_item_id,
                    generated_at=generated_at,
                )
            )
        elif ref.item_state is RemediationBacklogItemState.ACKNOWLEDGED:
            issues.append(
                _make_issue(
                    issue_type=RemediationEvidenceIssueType.ACKNOWLEDGED_BACKLOG_ITEM,
                    severity=RemediationEvidenceSeverity.INFO,
                    reason_codes=(RemediationEvidenceReasonCode.ACKNOWLEDGED_BACKLOG_ITEM.value,),
                    title="Acknowledged backlog item",
                    description=f"Backlog item {ref.backlog_item_id} is acknowledged.",
                    backlog_item_id=ref.backlog_item_id,
                    generated_at=generated_at,
                )
            )
        elif ref.item_state is RemediationBacklogItemState.DEFERRED:
            issues.append(
                _make_issue(
                    issue_type=RemediationEvidenceIssueType.DEFERRED_BACKLOG_ITEM,
                    severity=RemediationEvidenceSeverity.INFO,
                    reason_codes=(RemediationEvidenceReasonCode.DEFERRED_BACKLOG_ITEM.value,),
                    title="Deferred backlog item",
                    description=f"Backlog item {ref.backlog_item_id} is deferred.",
                    backlog_item_id=ref.backlog_item_id,
                    generated_at=generated_at,
                )
            )
        elif ref.item_state is RemediationBacklogItemState.NOT_APPLICABLE:
            issues.append(
                _make_issue(
                    issue_type=RemediationEvidenceIssueType.NOT_APPLICABLE_BACKLOG_ITEM,
                    severity=RemediationEvidenceSeverity.INFO,
                    reason_codes=(RemediationEvidenceReasonCode.NOT_APPLICABLE_BACKLOG_ITEM.value,),
                    title="Not-applicable backlog item",
                    description=f"Backlog item {ref.backlog_item_id} is not applicable.",
                    backlog_item_id=ref.backlog_item_id,
                    generated_at=generated_at,
                )
            )
    dq_updates["blocked_backlog_item_count"] = blocked_backlog_item_count
    dq_updates["open_backlog_item_count"] = open_backlog_item_count

    return tuple(issues), dq_updates


def _build_coverage_results(
    input: RemediationEvidenceInput,
    config: RemediationEvidenceConfig,
    generated_at: datetime,
) -> tuple[RemediationEvidenceCoverageResult, ...]:
    """Compute coverage state for every backlog item using first-match-wins precedence."""
    backlog_item_ids = {ref.backlog_item_id for ref in input.backlog_item_refs}
    evidence_by_id = {rec.evidence_id: rec for rec in input.evidence_records}

    # Build effective links from explicit links plus evidence-record backlog_item_id.
    effective_links: dict[tuple[str, str], RemediationEvidenceLinkType] = {}
    for link in input.links:
        if link.evidence_id in evidence_by_id and link.backlog_item_id in backlog_item_ids:
            effective_links[(link.evidence_id, link.backlog_item_id)] = link.link_type
    for rec in input.evidence_records:
        if rec.backlog_item_id in backlog_item_ids:
            effective_links.setdefault((rec.evidence_id, rec.backlog_item_id), RemediationEvidenceLinkType.SUPPORTS)

    links_by_backlog_item: defaultdict[str, set[str]] = defaultdict(set)
    for (evidence_id, backlog_item_id), link_type in effective_links.items():
        links_by_backlog_item[backlog_item_id].add(evidence_id)

    evidence_reviews: defaultdict[str, list[RemediationReviewRecord]] = defaultdict(list)
    for rev in input.review_records:
        evidence_reviews[rev.evidence_id].append(rev)

    staleness_threshold = timedelta(seconds=config.staleness_threshold_seconds)

    required_items = set(config.required_backlog_item_ids)
    if config.require_evidence_for_all:
        required_items.update(backlog_item_ids)

    results: list[RemediationEvidenceCoverageResult] = []
    for ref in sorted(input.backlog_item_refs, key=lambda r: r.backlog_item_id):
        backlog_item_id = ref.backlog_item_id
        linked_evidence_ids = sorted(links_by_backlog_item.get(backlog_item_id, set()))
        linked_review_ids = sorted(
            rev.review_id for eid in linked_evidence_ids for rev in evidence_reviews.get(eid, [])
        )

        non_orphan_evidence_ids = [
            eid for eid in linked_evidence_ids
            if evidence_by_id[eid].backlog_item_id in backlog_item_ids
        ]
        has_orphan_evidence = len(non_orphan_evidence_ids) < len(linked_evidence_ids)

        coverage_state = _classify_coverage(
            ref=ref,
            linked_evidence_ids=linked_evidence_ids,
            non_orphan_evidence_ids=non_orphan_evidence_ids,
            evidence_by_id=evidence_by_id,
            evidence_reviews=evidence_reviews,
            generated_at=generated_at,
            staleness_threshold=staleness_threshold,
            required=backlog_item_id in required_items,
            has_orphan_evidence=has_orphan_evidence,
        )

        severity = (
            RemediationEvidenceSeverity.INFO
            if coverage_state in (RemediationEvidenceCoverageState.COVERED, RemediationEvidenceCoverageState.NOT_APPLICABLE)
            else RemediationEvidenceSeverity.ADVISORY
        )
        reason_code = _coverage_state_to_reason_code(coverage_state)

        results.append(
            RemediationEvidenceCoverageResult(
                coverage_id=_build_coverage_id(backlog_item_id, tuple(linked_evidence_ids), tuple(linked_review_ids)),
                backlog_item_id=backlog_item_id,
                coverage_state=coverage_state,
                evidence_ids=tuple(linked_evidence_ids),
                review_ids=tuple(linked_review_ids),
                severity=severity,
                reason_codes=(reason_code,),
                title=f"Coverage for {backlog_item_id}",
                description=f"Coverage state is {coverage_state.value}.",
                generated_at=generated_at,
            )
        )

    return tuple(results)


def _classify_coverage(
    *,
    ref: RemediationBacklogItemRef,
    linked_evidence_ids: list[str],
    non_orphan_evidence_ids: list[str],
    evidence_by_id: dict[str, RemediationEvidenceRecord],
    evidence_reviews: defaultdict[str, list[RemediationReviewRecord]],
    generated_at: datetime,
    staleness_threshold: timedelta,
    required: bool,
    has_orphan_evidence: bool,
) -> RemediationEvidenceCoverageState:
    """Apply first-match-wins coverage precedence rules."""
    # 1. NOT_APPLICABLE
    if ref.item_state is RemediationBacklogItemState.NOT_APPLICABLE:
        return RemediationEvidenceCoverageState.NOT_APPLICABLE
    if not required and not non_orphan_evidence_ids:
        return RemediationEvidenceCoverageState.NOT_APPLICABLE

    # 2. MISSING
    if not non_orphan_evidence_ids:
        return RemediationEvidenceCoverageState.MISSING

    # 3. CONFLICTING
    for eid in non_orphan_evidence_ids:
        reviews = evidence_reviews.get(eid, [])
        outcomes = {rev.outcome for rev in reviews}
        if len(outcomes) > 1:
            return RemediationEvidenceCoverageState.CONFLICTING

    # 4. REJECTED
    all_rejected = all(
        evidence_by_id[eid].evidence_state is RemediationEvidenceRecordState.REJECTED
        for eid in non_orphan_evidence_ids
    )
    if all_rejected:
        return RemediationEvidenceCoverageState.REJECTED

    # 5. STALE
    all_stale = all(
        evidence_by_id[eid].generated_at is not None
        and evidence_by_id[eid].generated_at < generated_at - staleness_threshold
        for eid in non_orphan_evidence_ids
    )
    all_reviews_stale = all(
        rev.generated_at is not None and rev.generated_at < generated_at - staleness_threshold
        for eid in non_orphan_evidence_ids
        for rev in evidence_reviews.get(eid, [])
    )
    if all_stale and (not evidence_reviews or all_reviews_stale):
        return RemediationEvidenceCoverageState.STALE

    # 6. PENDING_REVIEW
    has_accepted_review = any(
        rev.outcome is RemediationEvidenceReviewOutcome.ACCEPTED
        for eid in non_orphan_evidence_ids
        for rev in evidence_reviews.get(eid, [])
    )
    if not has_accepted_review:
        return RemediationEvidenceCoverageState.PENDING_REVIEW

    # 7. COVERED
    has_accepted_evidence = any(
        evidence_by_id[eid].evidence_state is RemediationEvidenceRecordState.ACCEPTED
        for eid in non_orphan_evidence_ids
    )
    has_rejected_or_conflicting = any(
        evidence_by_id[eid].evidence_state is RemediationEvidenceRecordState.REJECTED
        for eid in non_orphan_evidence_ids
    )
    if has_accepted_evidence and not has_rejected_or_conflicting and not has_orphan_evidence:
        return RemediationEvidenceCoverageState.COVERED

    # 8. PARTIAL
    return RemediationEvidenceCoverageState.PARTIAL


def _coverage_state_to_reason_code(state: RemediationEvidenceCoverageState) -> str:
    mapping = {
        RemediationEvidenceCoverageState.COVERED: RemediationEvidenceReasonCode.OK.value,
        RemediationEvidenceCoverageState.PARTIAL: RemediationEvidenceReasonCode.CONSISTENCY_DEGRADED.value,
        RemediationEvidenceCoverageState.MISSING: RemediationEvidenceReasonCode.MISSING_EVIDENCE.value,
        RemediationEvidenceCoverageState.REJECTED: RemediationEvidenceReasonCode.REJECTED_EVIDENCE.value,
        RemediationEvidenceCoverageState.PENDING_REVIEW: RemediationEvidenceReasonCode.PENDING_REVIEW_EVIDENCE.value,
        RemediationEvidenceCoverageState.CONFLICTING: RemediationEvidenceReasonCode.CONFLICTING_REVIEW.value,
        RemediationEvidenceCoverageState.STALE: RemediationEvidenceReasonCode.STALE_EVIDENCE.value,
        RemediationEvidenceCoverageState.NOT_APPLICABLE: RemediationEvidenceReasonCode.NOT_APPLICABLE.value,
    }
    return mapping[state]


def _aggregate_state(
    issues: tuple[RemediationEvidenceIssue, ...],
    backlog_item_count: int,
    strict: bool,
) -> tuple[RemediationEvidenceState, RemediationEvidenceReasonCode]:
    """Determine report aggregate state from issue severities and reason codes."""
    has_blocking = any(
        issue.severity is RemediationEvidenceSeverity.BLOCKING
        or any(code in _BLOCKING_REASON_CODES for code in issue.reason_codes)
        for issue in issues
    )
    has_advisory = any(
        issue.severity is RemediationEvidenceSeverity.ADVISORY
        or any(code in _ADVISORY_REASON_CODES for code in issue.reason_codes)
        for issue in issues
    )

    if has_blocking:
        state = RemediationEvidenceState.BLOCKED
        reason_code = RemediationEvidenceReasonCode.SAFETY_BLOCKED
    elif has_advisory:
        state = RemediationEvidenceState.DEGRADED
        reason_code = RemediationEvidenceReasonCode.CONSISTENCY_DEGRADED
    elif backlog_item_count == 0:
        state = RemediationEvidenceState.NOT_APPLICABLE
        reason_code = RemediationEvidenceReasonCode.NOT_APPLICABLE
    else:
        state = RemediationEvidenceState.OK
        reason_code = RemediationEvidenceReasonCode.OK

    if strict and state in (RemediationEvidenceState.DEGRADED, RemediationEvidenceState.BLOCKED, RemediationEvidenceState.NOT_APPLICABLE):
        state = RemediationEvidenceState.BLOCKED
        reason_code = RemediationEvidenceReasonCode.SAFETY_BLOCKED

    return state, reason_code


def _aggregate_reason_codes(
    issues: tuple[RemediationEvidenceIssue, ...],
    state_reason_code: RemediationEvidenceReasonCode,
) -> tuple[RemediationEvidenceReasonCode, ...]:
    """Collect unique reason codes from issues plus the state-level code."""
    codes: set[str] = {state_reason_code.value}
    for issue in issues:
        for code in issue.reason_codes:
            codes.add(code)
    ordered = sorted(codes)
    if state_reason_code.value in ordered:
        ordered.remove(state_reason_code.value)
    return (state_reason_code,) + tuple(RemediationEvidenceReasonCode(code) for code in ordered)


def _build_data_quality(
    input: RemediationEvidenceInput,
    coverage_results: tuple[RemediationEvidenceCoverageResult, ...],
    issues: tuple[RemediationEvidenceIssue, ...],
    dq_updates: dict[str, int],
) -> RemediationEvidenceDataQuality:
    """Build the data quality summary from counts."""
    return RemediationEvidenceDataQuality(
        total_backlog_item_refs=len(input.backlog_item_refs),
        total_evidence_records=len(input.evidence_records),
        total_review_records=len(input.review_records),
        total_links=len(input.links),
        total_issues=len(issues),
        total_coverage_results=len(coverage_results),
        duplicate_id_count=0,
        duplicate_evidence_count=dq_updates.get("duplicate_evidence_count", 0),
        orphan_evidence_count=dq_updates.get("orphan_evidence_count", 0),
        orphan_review_count=dq_updates.get("orphan_review_count", 0),
        orphan_link_count=dq_updates.get("orphan_link_count", 0),
        conflicting_review_count=dq_updates.get("conflicting_review_count", 0),
        stale_evidence_count=dq_updates.get("stale_evidence_count", 0),
        stale_review_count=dq_updates.get("stale_review_count", 0),
        missing_evidence_count=dq_updates.get("missing_evidence_count", 0),
        missing_review_count=dq_updates.get("missing_review_count", 0),
        rejected_evidence_count=dq_updates.get("rejected_evidence_count", 0),
        pending_review_evidence_count=dq_updates.get("pending_review_evidence_count", 0),
        blocked_backlog_item_count=dq_updates.get("blocked_backlog_item_count", 0),
        open_backlog_item_count=dq_updates.get("open_backlog_item_count", 0),
        unsafe_content_count=0,
        forbidden_term_count=0,
        sections_present=0,
    )


def _build_safety_flags(
    issues: tuple[RemediationEvidenceIssue, ...],
    config: RemediationEvidenceConfig,
) -> RemediationEvidenceSafetyFlags:
    """Build safety flags from issue reason codes."""
    has_forbidden_terms = any(
        RemediationEvidenceReasonCode.FORBIDDEN_TERM_PRESENT.value in issue.reason_codes
        for issue in issues
    )
    has_unsafe_content = any(
        RemediationEvidenceReasonCode.UNSAFE_CONTENT.value in issue.reason_codes
        for issue in issues
    )
    return RemediationEvidenceSafetyFlags(
        has_forbidden_terms=has_forbidden_terms,
        has_unsafe_content=has_unsafe_content,
    )

