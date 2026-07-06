"""In-memory engine for hunter.remediation_closure package.

MVP-39 — Local Research Remediation Closure Register.

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

from hunter.remediation_closure.models import (
    FORBIDDEN_REMEDIATION_CLOSURE_TERMS,
    REMEDIATION_CLOSURE_VERSION,
    RemediationClosureBacklogItemRef,
    RemediationClosureConfig,
    RemediationClosureDataQuality,
    RemediationClosureDeclaration,
    RemediationClosureEligibilityState,
    RemediationClosureEvidenceSummary,
    RemediationClosureIssue,
    RemediationClosureIssueType,
    RemediationClosureLink,
    RemediationClosureReasonCode,
    RemediationClosureRecordState,
    RemediationClosureResult,
    RemediationClosureReviewOutcome,
    RemediationClosureReviewRecord,
    RemediationClosureSafetyFlags,
    RemediationClosureSeverity,
    RemediationClosureState,
    RemediationClosureInput,
    RemediationClosureReport,
    _check_forbidden_mapping,
    _has_forbidden_term,
    has_unsafe_remediation_closure_content,
)


SAFETY_NOTICE = (
    "This report is a local, audit-only research artifact. "
    "Closure recorded is for human-audit tracking only and does not imply "
    "approval, certification, production readiness, trading readiness, "
    "recommendation, suitability, or signal validity."
)


# Reason-code sets used for aggregation.
_BLOCKING_REASON_CODES: frozenset[str] = frozenset({
    RemediationClosureReasonCode.UNSAFE_CONTENT.value,
    RemediationClosureReasonCode.FORBIDDEN_TERM_PRESENT.value,
    RemediationClosureReasonCode.DUPLICATE_ID.value,
    RemediationClosureReasonCode.CONFLICTING_CLOSURE.value,
    RemediationClosureReasonCode.CONFLICTING_REVIEW.value,
    RemediationClosureReasonCode.MISSING_EVIDENCE.value,
    RemediationClosureReasonCode.BLOCKED_BACKLOG_ITEM.value,
    RemediationClosureReasonCode.OPEN_BACKLOG_ITEM.value,
    RemediationClosureReasonCode.CONFLICTING_BACKLOG_ITEM.value,
    RemediationClosureReasonCode.SAFETY_BLOCKED.value,
})


_ADVISORY_REASON_CODES: frozenset[str] = frozenset({
    RemediationClosureReasonCode.ORPHAN_EVIDENCE.value,
    RemediationClosureReasonCode.ORPHAN_CLOSURE.value,
    RemediationClosureReasonCode.ORPHAN_REVIEW.value,
    RemediationClosureReasonCode.ORPHAN_LINK.value,
    RemediationClosureReasonCode.STALE_EVIDENCE.value,
    RemediationClosureReasonCode.STALE_CLOSURE.value,
    RemediationClosureReasonCode.STALE_REVIEW.value,
    RemediationClosureReasonCode.MISSING_REVIEW.value,
    RemediationClosureReasonCode.MISSING_CLOSURE_METADATA.value,
    RemediationClosureReasonCode.REJECTED_REVIEW.value,
    RemediationClosureReasonCode.PENDING_REVIEW.value,
    RemediationClosureReasonCode.DISPUTED_REVIEW.value,
    RemediationClosureReasonCode.CONSISTENCY_DEGRADED.value,
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


def _resolve_generated_at(input: RemediationClosureInput) -> datetime:
    """Return the effective generated_at timestamp."""
    return input.generated_at if input.generated_at is not None else datetime.now(timezone.utc)


def _has_unsafe_content(input: RemediationClosureInput) -> bool:
    """Return True if any metadata field contains unsafe non-string values."""
    if has_unsafe_remediation_closure_content(dict(input.metadata)):
        return True
    for ref in input.backlog_item_refs:
        if has_unsafe_remediation_closure_content(dict(ref.metadata)):
            return True
    for summary in input.evidence_summaries:
        if has_unsafe_remediation_closure_content(dict(summary.metadata)):
            return True
    for decl in input.closure_declarations:
        if has_unsafe_remediation_closure_content(dict(decl.metadata)):
            return True
    for rev in input.review_records:
        if has_unsafe_remediation_closure_content(dict(rev.metadata)):
            return True
    for link in input.links:
        if has_unsafe_remediation_closure_content(dict(link.metadata)):
            return True
    return False


def _has_forbidden_terms(input: RemediationClosureInput) -> bool:
    """Return True if any text field or metadata contains forbidden terms."""
    for ref in input.backlog_item_refs:
        for text in (ref.title, ref.description):
            if text and _has_forbidden_term(text, FORBIDDEN_REMEDIATION_CLOSURE_TERMS):
                return True
        if _check_forbidden_mapping(ref.metadata, FORBIDDEN_REMEDIATION_CLOSURE_TERMS):
            return True
    for summary in input.evidence_summaries:
        if _check_forbidden_mapping(summary.metadata, FORBIDDEN_REMEDIATION_CLOSURE_TERMS):
            return True
    for decl in input.closure_declarations:
        for text in (decl.rationale,):
            if text and _has_forbidden_term(text, FORBIDDEN_REMEDIATION_CLOSURE_TERMS):
                return True
        if _check_forbidden_mapping(decl.metadata, FORBIDDEN_REMEDIATION_CLOSURE_TERMS):
            return True
    for rev in input.review_records:
        for text in (rev.note,):
            if text and _has_forbidden_term(text, FORBIDDEN_REMEDIATION_CLOSURE_TERMS):
                return True
        if _check_forbidden_mapping(rev.metadata, FORBIDDEN_REMEDIATION_CLOSURE_TERMS):
            return True
    for link in input.links:
        if _check_forbidden_mapping(link.metadata, FORBIDDEN_REMEDIATION_CLOSURE_TERMS):
            return True
    if _check_forbidden_mapping(input.metadata, FORBIDDEN_REMEDIATION_CLOSURE_TERMS):
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


def _build_report_id(input: RemediationClosureInput, generated_at: datetime) -> str:
    """Build a deterministic report_id from sorted IDs and metadata."""
    payload = {
        "backlog_item_ids": sorted(set(ref.backlog_item_id for ref in input.backlog_item_refs)),
        "evidence_summary_ids": sorted(set(es.evidence_summary_id for es in input.evidence_summaries)),
        "closure_ids": sorted(set(decl.closure_id for decl in input.closure_declarations)),
        "review_ids": sorted(set(rev.review_id for rev in input.review_records)),
        "link_ids": sorted(set(link.link_id for link in input.links)),
        "project_version": input.project_version,
        "generated_at": generated_at.isoformat(),
    }
    return _sha256_hex(_canonical_json(payload))


def _build_closure_result_id(
    backlog_item_id: str,
    closure_ids: tuple[str, ...],
    evidence_summary_ids: tuple[str, ...],
    review_ids: tuple[str, ...],
) -> str:
    """Build a deterministic closure_result_id for a backlog item."""
    payload = {
        "backlog_item_id": backlog_item_id,
        "closure_ids": sorted(closure_ids),
        "evidence_summary_ids": sorted(evidence_summary_ids),
        "review_ids": sorted(review_ids),
    }
    return _sha256_hex_16(_canonical_json(payload))


def _build_issue_id(issue: RemediationClosureIssue) -> str:
    """Build a deterministic issue_id from issue content."""
    payload = {
        "issue_type": issue.issue_type.value,
        "severity": issue.severity.value,
        "reason_codes": sorted(issue.reason_codes),
        "title": issue.title,
        "description": issue.description,
        "backlog_item_id": issue.backlog_item_id,
        "closure_id": issue.closure_id,
        "evidence_summary_id": issue.evidence_summary_id,
        "review_id": issue.review_id,
        "link_id": issue.link_id,
    }
    return _sha256_hex_16(_canonical_json(payload))


def _make_issue(
    *,
    issue_type: RemediationClosureIssueType,
    severity: RemediationClosureSeverity,
    reason_codes: tuple[str, ...],
    title: str,
    description: str,
    backlog_item_id: str = "",
    closure_id: str = "",
    evidence_summary_id: str = "",
    review_id: str = "",
    link_id: str = "",
    generated_at: datetime,
) -> RemediationClosureIssue:
    """Create an issue with a deterministic ID."""
    issue = RemediationClosureIssue(
        issue_type=issue_type,
        severity=severity,
        reason_codes=reason_codes,
        title=title,
        description=description,
        backlog_item_id=backlog_item_id,
        closure_id=closure_id,
        evidence_summary_id=evidence_summary_id,
        review_id=review_id,
        link_id=link_id,
        generated_at=generated_at,
    )
    return replace(issue, issue_id=_build_issue_id(issue))


def _closure_content_hash(decl: RemediationClosureDeclaration) -> str:
    """Build a deterministic content hash for duplicate closure detection."""
    metadata = dict(decl.metadata) if decl.metadata else {}
    payload = {
        "backlog_item_id": decl.backlog_item_id,
        "evidence_summary_id": decl.evidence_summary_id,
        "declared_by": decl.declared_by,
        "reviewed_by": decl.reviewed_by,
        "rationale": decl.rationale,
        "evidence_link": decl.evidence_link,
        "metadata": sorted((str(k), str(v)) for k, v in metadata.items()),
    }
    return _sha256_hex_16(_canonical_json(payload))


def build_remediation_closure_report(
    input: RemediationClosureInput,
    config: RemediationClosureConfig | None = None,
    strict: bool | None = None,
) -> RemediationClosureReport:
    """Build a deterministic remediation closure report from in-memory declarations."""
    if config is None:
        config = input.config
    if strict is not None:
        config = RemediationClosureConfig(
            strict=strict,
            require_review=config.require_review,
            require_closure_for_all=config.require_closure_for_all,
            require_evidence_for_closure=config.require_evidence_for_closure,
            required_backlog_item_ids=config.required_backlog_item_ids,
            staleness_threshold_seconds=config.staleness_threshold_seconds,
            forbid_action_terms=config.forbid_action_terms,
            require_closure_metadata=config.require_closure_metadata,
        )

    generated_at = _resolve_generated_at(input)

    if _has_unsafe_content(input):
        return RemediationClosureReport.blocked(
            input=input,
            reason_code=RemediationClosureReasonCode.UNSAFE_CONTENT,
            notes="Report blocked due to unsafe content in caller-provided input.",
        )

    if config.forbid_action_terms and _has_forbidden_terms(input):
        return RemediationClosureReport.blocked(
            input=input,
            reason_code=RemediationClosureReasonCode.FORBIDDEN_TERM_PRESENT,
            notes="Report blocked due to forbidden terms in caller-provided text fields or metadata.",
        )

    validation_report = _validate_input(input, config, generated_at)
    if validation_report is not None:
        return validation_report

    issues, dq_updates = _detect_issues(input, config, generated_at)
    closure_results = _build_closure_results(input, config, generated_at, issues)
    manual_review_issues = _emit_manual_review_issues(closure_results, generated_at)
    issues = tuple(list(issues) + list(manual_review_issues))
    dq_updates["manual_review_required_count"] = len(manual_review_issues)
    report_state, state_reason_code = _aggregate_state(issues, len(input.backlog_item_refs), config.strict)
    reason_codes = _aggregate_reason_codes(issues, state_reason_code)
    data_quality = _build_data_quality(input, closure_results, issues, dq_updates)
    safety_flags = _build_safety_flags(issues, config)

    sorted_backlog_item_refs = tuple(
        sorted(input.backlog_item_refs, key=lambda r: (r.backlog_item_id, r.source_id, r.finding_id))
    )
    sorted_evidence_summaries = tuple(
        sorted(input.evidence_summaries, key=lambda s: (s.evidence_summary_id, s.backlog_item_id))
    )
    sorted_closure_declarations = tuple(
        sorted(input.closure_declarations, key=lambda d: (d.closure_id, d.backlog_item_id))
    )
    sorted_review_records = tuple(
        sorted(input.review_records, key=lambda r: (r.review_id, r.closure_id))
    )
    sorted_links = tuple(
        sorted(input.links, key=lambda l: (l.link_id, l.closure_id, l.evidence_summary_id, l.backlog_item_id))
    )
    sorted_issues = tuple(
        sorted(issues, key=lambda i: (i.issue_id, i.issue_type.value, i.severity.value))
    )
    sorted_closure_results = tuple(
        sorted(closure_results, key=lambda c: (c.closure_result_id, c.backlog_item_id))
    )

    return RemediationClosureReport(
        report_id=_build_report_id(input, generated_at),
        state=report_state,
        reason_codes=reason_codes,
        backlog_item_refs=sorted_backlog_item_refs,
        evidence_summaries=sorted_evidence_summaries,
        closure_declarations=sorted_closure_declarations,
        review_records=sorted_review_records,
        links=sorted_links,
        issues=sorted_issues,
        closure_results=sorted_closure_results,
        data_quality=data_quality,
        safety_flags=safety_flags,
        generated_at=generated_at,
        project_version=input.project_version,
        safety_notice=SAFETY_NOTICE,
        notes=(
            "Report output is for human audit only. "
            "Closure recorded is for human-audit tracking only and does not imply approval, "
            "certification, production readiness, trading readiness, recommendation, suitability, "
            "or signal validity."
        ),
    )


def _validate_input(
    input: RemediationClosureInput,
    config: RemediationClosureConfig,
    generated_at: datetime,
) -> RemediationClosureReport | None:
    """Fail-closed validation for duplicate IDs."""
    duplicate_backlog_item_ids = _find_duplicate_ids(input.backlog_item_refs, "backlog_item_id")
    duplicate_evidence_summary_ids = _find_duplicate_ids(input.evidence_summaries, "evidence_summary_id")
    duplicate_closure_ids = _find_duplicate_ids(input.closure_declarations, "closure_id")
    duplicate_review_ids = _find_duplicate_ids(input.review_records, "review_id")
    duplicate_link_ids = _find_duplicate_ids(input.links, "link_id")
    if any((
        duplicate_backlog_item_ids,
        duplicate_evidence_summary_ids,
        duplicate_closure_ids,
        duplicate_review_ids,
        duplicate_link_ids,
    )):
        return RemediationClosureReport.blocked(
            input=input,
            reason_code=RemediationClosureReasonCode.DUPLICATE_ID,
            notes="Input validation failed: duplicate IDs detected.",
        )
    return None


def _detect_issues(
    input: RemediationClosureInput,
    config: RemediationClosureConfig,
    generated_at: datetime,
) -> tuple[tuple[RemediationClosureIssue, ...], dict[str, int]]:
    """Run all detection passes and return issues plus data-quality counters."""
    issues: list[RemediationClosureIssue] = []
    dq_updates: dict[str, int] = {}

    backlog_item_ids = {ref.backlog_item_id for ref in input.backlog_item_refs}
    evidence_summary_ids = {es.evidence_summary_id for es in input.evidence_summaries}
    closure_ids = {decl.closure_id for decl in input.closure_declarations}
    evidence_summary_by_id = {es.evidence_summary_id: es for es in input.evidence_summaries}
    closure_by_id = {decl.closure_id: decl for decl in input.closure_declarations}
    reviews_by_closure: defaultdict[str, list[RemediationClosureReviewRecord]] = defaultdict(list)
    for rev in input.review_records:
        reviews_by_closure[rev.closure_id].append(rev)

    staleness_threshold = timedelta(seconds=config.staleness_threshold_seconds)

    # Orphan detection.
    orphan_evidence_ids = set()
    for es in input.evidence_summaries:
        if es.backlog_item_id and es.backlog_item_id not in backlog_item_ids:
            orphan_evidence_ids.add(es.evidence_summary_id)
    dq_updates["orphan_evidence_count"] = len(orphan_evidence_ids)
    for evidence_summary_id in sorted(orphan_evidence_ids):
        es = evidence_summary_by_id[evidence_summary_id]
        issues.append(
            _make_issue(
                issue_type=RemediationClosureIssueType.ORPHAN_EVIDENCE,
                severity=RemediationClosureSeverity.ADVISORY,
                reason_codes=(RemediationClosureReasonCode.ORPHAN_EVIDENCE.value,),
                title="Orphan evidence summary",
                description=f"Evidence summary {evidence_summary_id} references an unknown backlog item.",
                evidence_summary_id=evidence_summary_id,
                backlog_item_id=es.backlog_item_id,
                generated_at=generated_at,
            )
        )

    orphan_closure_ids = set()
    for decl in input.closure_declarations:
        if decl.backlog_item_id and decl.backlog_item_id not in backlog_item_ids:
            orphan_closure_ids.add(decl.closure_id)
    dq_updates["orphan_closure_count"] = len(orphan_closure_ids)
    for closure_id in sorted(orphan_closure_ids):
        decl = closure_by_id[closure_id]
        issues.append(
            _make_issue(
                issue_type=RemediationClosureIssueType.ORPHAN_CLOSURE,
                severity=RemediationClosureSeverity.ADVISORY,
                reason_codes=(RemediationClosureReasonCode.ORPHAN_CLOSURE.value,),
                title="Orphan closure declaration",
                description=f"Closure declaration {closure_id} references an unknown backlog item.",
                closure_id=closure_id,
                backlog_item_id=decl.backlog_item_id,
                generated_at=generated_at,
            )
        )

    orphan_review_ids = set()
    for rev in input.review_records:
        if rev.closure_id not in closure_ids:
            orphan_review_ids.add(rev.review_id)
    dq_updates["orphan_review_count"] = len(orphan_review_ids)
    for review_id in sorted(orphan_review_ids):
        issues.append(
            _make_issue(
                issue_type=RemediationClosureIssueType.ORPHAN_REVIEW,
                severity=RemediationClosureSeverity.ADVISORY,
                reason_codes=(RemediationClosureReasonCode.ORPHAN_REVIEW.value,),
                title="Orphan review record",
                description=f"Review record {review_id} references an unknown closure declaration.",
                review_id=review_id,
                generated_at=generated_at,
            )
        )

    orphan_link_ids = set()
    for link in input.links:
        if (
            link.closure_id not in closure_ids
            or link.evidence_summary_id not in evidence_summary_ids
            or link.backlog_item_id not in backlog_item_ids
        ):
            orphan_link_ids.add(link.link_id)
    dq_updates["orphan_link_count"] = len(orphan_link_ids)
    for link_id in sorted(orphan_link_ids):
        issues.append(
            _make_issue(
                issue_type=RemediationClosureIssueType.ORPHAN_LINK,
                severity=RemediationClosureSeverity.ADVISORY,
                reason_codes=(RemediationClosureReasonCode.ORPHAN_LINK.value,),
                title="Orphan link",
                description=f"Link {link_id} references an unknown closure, evidence summary, or backlog item.",
                link_id=link_id,
                generated_at=generated_at,
            )
        )

    # Conflicting closure declarations (different content for the same backlog item).
    conflicting_closure_backlog_ids: set[str] = set()
    closures_by_backlog: defaultdict[str, list[RemediationClosureDeclaration]] = defaultdict(list)
    for decl in input.closure_declarations:
        closures_by_backlog[decl.backlog_item_id].append(decl)
    for backlog_item_id, decls in closures_by_backlog.items():
        if len(decls) < 2:
            continue
        content_hashes = {_closure_content_hash(d) for d in decls}
        if len(content_hashes) > 1:
            conflicting_closure_backlog_ids.add(backlog_item_id)
    dq_updates["conflicting_closure_count"] = len(conflicting_closure_backlog_ids)
    for backlog_item_id in sorted(conflicting_closure_backlog_ids):
        issues.append(
            _make_issue(
                issue_type=RemediationClosureIssueType.CONFLICTING_CLOSURE,
                severity=RemediationClosureSeverity.BLOCKING,
                reason_codes=(RemediationClosureReasonCode.CONFLICTING_CLOSURE.value,),
                title="Conflicting closure declarations",
                description=f"Backlog item {backlog_item_id} has conflicting closure declarations.",
                backlog_item_id=backlog_item_id,
                generated_at=generated_at,
            )
        )

    # Conflicting review outcomes.
    conflicting_closure_ids: set[str] = set()
    for closure_id, reviews in reviews_by_closure.items():
        outcomes = {rev.outcome for rev in reviews}
        if len(outcomes) > 1:
            conflicting_closure_ids.add(closure_id)
    dq_updates["conflicting_review_count"] = len(conflicting_closure_ids)
    for closure_id in sorted(conflicting_closure_ids):
        issues.append(
            _make_issue(
                issue_type=RemediationClosureIssueType.CONFLICTING_REVIEW,
                severity=RemediationClosureSeverity.BLOCKING,
                reason_codes=(RemediationClosureReasonCode.CONFLICTING_REVIEW.value,),
                title="Conflicting review outcomes",
                description=f"Closure {closure_id} has conflicting review outcomes.",
                closure_id=closure_id,
                generated_at=generated_at,
            )
        )

    # Stale records.
    stale_evidence_ids = set()
    for es in input.evidence_summaries:
        if es.generated_at is not None and es.generated_at < generated_at - staleness_threshold:
            stale_evidence_ids.add(es.evidence_summary_id)
    dq_updates["stale_evidence_count"] = len(stale_evidence_ids)
    for evidence_summary_id in sorted(stale_evidence_ids):
        issues.append(
            _make_issue(
                issue_type=RemediationClosureIssueType.STALE_EVIDENCE,
                severity=RemediationClosureSeverity.ADVISORY,
                reason_codes=(RemediationClosureReasonCode.STALE_EVIDENCE.value,),
                title="Stale evidence summary",
                description=f"Evidence summary {evidence_summary_id} is older than the staleness threshold.",
                evidence_summary_id=evidence_summary_id,
                generated_at=generated_at,
            )
        )

    stale_closure_ids = set()
    for decl in input.closure_declarations:
        if decl.generated_at is not None and decl.generated_at < generated_at - staleness_threshold:
            stale_closure_ids.add(decl.closure_id)
    dq_updates["stale_closure_count"] = len(stale_closure_ids)
    for closure_id in sorted(stale_closure_ids):
        issues.append(
            _make_issue(
                issue_type=RemediationClosureIssueType.STALE_CLOSURE,
                severity=RemediationClosureSeverity.ADVISORY,
                reason_codes=(RemediationClosureReasonCode.STALE_CLOSURE.value,),
                title="Stale closure declaration",
                description=f"Closure declaration {closure_id} is older than the staleness threshold.",
                closure_id=closure_id,
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
                issue_type=RemediationClosureIssueType.STALE_REVIEW,
                severity=RemediationClosureSeverity.ADVISORY,
                reason_codes=(RemediationClosureReasonCode.STALE_REVIEW.value,),
                title="Stale review record",
                description=f"Review record {review_id} is older than the staleness threshold.",
                review_id=review_id,
                generated_at=generated_at,
            )
        )

    # Missing evidence, missing review, missing metadata, review outcomes, backlog state.
    missing_evidence_count = 0
    missing_review_count = 0
    missing_metadata_count = 0
    rejected_review_count = 0
    pending_review_count = 0
    disputed_review_count = 0
    blocked_backlog_count = 0
    open_backlog_count = 0
    conflicting_backlog_count = 0
    acknowledged_backlog_count = 0
    deferred_backlog_count = 0
    not_applicable_backlog_count = 0

    for decl in input.closure_declarations:
        if decl.closure_id in orphan_closure_ids:
            continue

        # Missing evidence coverage.
        evidence_summary = evidence_summary_by_id.get(decl.evidence_summary_id)
        coverage_missing = (
            evidence_summary is None
            or evidence_summary.coverage_state.lower() != "covered"
        )
        if config.require_evidence_for_closure and coverage_missing:
            missing_evidence_count += 1
            issues.append(
                _make_issue(
                    issue_type=RemediationClosureIssueType.MISSING_EVIDENCE,
                    severity=RemediationClosureSeverity.BLOCKING,
                    reason_codes=(RemediationClosureReasonCode.MISSING_EVIDENCE.value,),
                    title="Missing evidence coverage",
                    description=f"Closure {decl.closure_id} lacks accepted evidence coverage.",
                    closure_id=decl.closure_id,
                    backlog_item_id=decl.backlog_item_id,
                    evidence_summary_id=decl.evidence_summary_id,
                    generated_at=generated_at,
                )
            )
        elif coverage_missing and not config.require_evidence_for_closure:
            issues.append(
                _make_issue(
                    issue_type=RemediationClosureIssueType.MISSING_EVIDENCE,
                    severity=RemediationClosureSeverity.INFO,
                    reason_codes=(RemediationClosureReasonCode.NOT_APPLICABLE.value,),
                    title="Evidence coverage not required",
                    description=f"Closure {decl.closure_id} evidence coverage is not required.",
                    closure_id=decl.closure_id,
                    backlog_item_id=decl.backlog_item_id,
                    evidence_summary_id=decl.evidence_summary_id,
                    generated_at=generated_at,
                )
            )

        # Missing review.
        reviews = reviews_by_closure.get(decl.closure_id, [])
        accepted_or_not_required = any(
            rev.outcome.lower() in ("accepted", "not_required")
            for rev in reviews
        )
        if config.require_review and not accepted_or_not_required:
            missing_review_count += 1
            issues.append(
                _make_issue(
                    issue_type=RemediationClosureIssueType.MISSING_REVIEW,
                    severity=RemediationClosureSeverity.ADVISORY,
                    reason_codes=(RemediationClosureReasonCode.MISSING_REVIEW.value,),
                    title="Missing review",
                    description=f"Closure {decl.closure_id} requires an accepted or not-required review.",
                    closure_id=decl.closure_id,
                    backlog_item_id=decl.backlog_item_id,
                    generated_at=generated_at,
                )
            )

        # Missing closure metadata.
        if config.require_closure_metadata:
            missing_any = (
                not decl.declared_by
                or not decl.reviewed_by
                or decl.closed_at is None
                or not decl.rationale
                or not decl.evidence_link
            )
            if missing_any:
                missing_metadata_count += 1
                issues.append(
                    _make_issue(
                        issue_type=RemediationClosureIssueType.MISSING_CLOSURE_METADATA,
                        severity=RemediationClosureSeverity.ADVISORY,
                        reason_codes=(RemediationClosureReasonCode.MISSING_CLOSURE_METADATA.value,),
                        title="Missing closure metadata",
                        description=f"Closure {decl.closure_id} is missing required closure metadata.",
                        closure_id=decl.closure_id,
                        backlog_item_id=decl.backlog_item_id,
                        generated_at=generated_at,
                    )
                )

    # Review outcome issues (for non-orphan reviews).
    for rev in input.review_records:
        if rev.review_id in orphan_review_ids:
            continue
        if rev.outcome.lower() == "rejected":
            rejected_review_count += 1
            issues.append(
                _make_issue(
                    issue_type=RemediationClosureIssueType.REJECTED_REVIEW,
                    severity=RemediationClosureSeverity.ADVISORY,
                    reason_codes=(RemediationClosureReasonCode.REJECTED_REVIEW.value,),
                    title="Rejected review",
                    description=f"Review {rev.review_id} rejected closure {rev.closure_id}.",
                    review_id=rev.review_id,
                    closure_id=rev.closure_id,
                    generated_at=generated_at,
                )
            )
        elif rev.outcome.lower() == "pending":
            pending_review_count += 1
            severity = (
                RemediationClosureSeverity.ADVISORY
                if config.require_review
                else RemediationClosureSeverity.INFO
            )
            issues.append(
                _make_issue(
                    issue_type=RemediationClosureIssueType.PENDING_REVIEW,
                    severity=severity,
                    reason_codes=(RemediationClosureReasonCode.PENDING_REVIEW.value,),
                    title="Pending review",
                    description=f"Review {rev.review_id} for closure {rev.closure_id} is pending.",
                    review_id=rev.review_id,
                    closure_id=rev.closure_id,
                    generated_at=generated_at,
                )
            )
        elif rev.outcome.lower() == "disputed":
            disputed_review_count += 1
            issues.append(
                _make_issue(
                    issue_type=RemediationClosureIssueType.DISPUTED_REVIEW,
                    severity=RemediationClosureSeverity.ADVISORY,
                    reason_codes=(RemediationClosureReasonCode.DISPUTED_REVIEW.value,),
                    title="Disputed review",
                    description=f"Review {rev.review_id} disputed closure {rev.closure_id}.",
                    review_id=rev.review_id,
                    closure_id=rev.closure_id,
                    generated_at=generated_at,
                )
            )

    # Backlog item state mismatches (only for backlog items with closure declarations).
    backlog_item_ids_with_closures = {decl.backlog_item_id for decl in input.closure_declarations}
    for ref in input.backlog_item_refs:
        if ref.backlog_item_id not in backlog_item_ids_with_closures:
            continue
        state = ref.item_state.lower()
        if state == "blocked":
            blocked_backlog_count += 1
            issues.append(
                _make_issue(
                    issue_type=RemediationClosureIssueType.BLOCKED_BACKLOG_ITEM,
                    severity=RemediationClosureSeverity.BLOCKING,
                    reason_codes=(RemediationClosureReasonCode.BLOCKED_BACKLOG_ITEM.value,),
                    title="Blocked backlog item",
                    description=f"Backlog item {ref.backlog_item_id} is blocked and has a closure declaration.",
                    backlog_item_id=ref.backlog_item_id,
                    generated_at=generated_at,
                )
            )
        elif state == "open":
            open_backlog_count += 1
            issues.append(
                _make_issue(
                    issue_type=RemediationClosureIssueType.OPEN_BACKLOG_ITEM,
                    severity=RemediationClosureSeverity.BLOCKING,
                    reason_codes=(RemediationClosureReasonCode.OPEN_BACKLOG_ITEM.value,),
                    title="Open backlog item",
                    description=f"Backlog item {ref.backlog_item_id} is open and has a closure declaration.",
                    backlog_item_id=ref.backlog_item_id,
                    generated_at=generated_at,
                )
            )
        elif state == "conflicting":
            conflicting_backlog_count += 1
            issues.append(
                _make_issue(
                    issue_type=RemediationClosureIssueType.CONFLICTING_BACKLOG_ITEM,
                    severity=RemediationClosureSeverity.BLOCKING,
                    reason_codes=(RemediationClosureReasonCode.CONFLICTING_BACKLOG_ITEM.value,),
                    title="Conflicting backlog item",
                    description=f"Backlog item {ref.backlog_item_id} is conflicting and has a closure declaration.",
                    backlog_item_id=ref.backlog_item_id,
                    generated_at=generated_at,
                )
            )
        elif state == "acknowledged":
            acknowledged_backlog_count += 1
            issues.append(
                _make_issue(
                    issue_type=RemediationClosureIssueType.ACKNOWLEDGED_BACKLOG_ITEM,
                    severity=RemediationClosureSeverity.INFO,
                    reason_codes=(RemediationClosureReasonCode.ACKNOWLEDGED_BACKLOG_ITEM.value,),
                    title="Acknowledged backlog item",
                    description=f"Backlog item {ref.backlog_item_id} is acknowledged and has a closure declaration.",
                    backlog_item_id=ref.backlog_item_id,
                    generated_at=generated_at,
                )
            )
        elif state == "deferred":
            deferred_backlog_count += 1
            issues.append(
                _make_issue(
                    issue_type=RemediationClosureIssueType.DEFERRED_BACKLOG_ITEM,
                    severity=RemediationClosureSeverity.INFO,
                    reason_codes=(RemediationClosureReasonCode.DEFERRED_BACKLOG_ITEM.value,),
                    title="Deferred backlog item",
                    description=f"Backlog item {ref.backlog_item_id} is deferred and has a closure declaration.",
                    backlog_item_id=ref.backlog_item_id,
                    generated_at=generated_at,
                )
            )
        elif state == "not_applicable":
            not_applicable_backlog_count += 1
            issues.append(
                _make_issue(
                    issue_type=RemediationClosureIssueType.NOT_APPLICABLE_BACKLOG_ITEM,
                    severity=RemediationClosureSeverity.INFO,
                    reason_codes=(RemediationClosureReasonCode.NOT_APPLICABLE_BACKLOG_ITEM.value,),
                    title="Not-applicable backlog item",
                    description=f"Backlog item {ref.backlog_item_id} is not applicable and has a closure declaration.",
                    backlog_item_id=ref.backlog_item_id,
                    generated_at=generated_at,
                )
            )

    dq_updates["missing_evidence_count"] = missing_evidence_count
    dq_updates["missing_review_count"] = missing_review_count
    dq_updates["missing_closure_metadata_count"] = missing_metadata_count
    dq_updates["rejected_review_count"] = rejected_review_count
    dq_updates["pending_review_count"] = pending_review_count
    dq_updates["disputed_review_count"] = disputed_review_count
    dq_updates["blocked_backlog_item_count"] = blocked_backlog_count
    dq_updates["open_backlog_item_count"] = open_backlog_count
    dq_updates["conflicting_backlog_item_count"] = conflicting_backlog_count
    dq_updates["acknowledged_backlog_item_count"] = acknowledged_backlog_count
    dq_updates["deferred_backlog_item_count"] = deferred_backlog_count
    dq_updates["not_applicable_backlog_item_count"] = not_applicable_backlog_count

    return tuple(issues), dq_updates


def _build_closure_results(
    input: RemediationClosureInput,
    config: RemediationClosureConfig,
    generated_at: datetime,
    issues: tuple[RemediationClosureIssue, ...],
) -> tuple[RemediationClosureResult, ...]:
    """Compute closure result for every backlog item using first-match-wins precedence."""
    backlog_item_ids = {ref.backlog_item_id for ref in input.backlog_item_refs}
    evidence_summary_by_id = {es.evidence_summary_id: es for es in input.evidence_summaries}
    closure_by_id = {decl.closure_id: decl for decl in input.closure_declarations}
    reviews_by_closure: defaultdict[str, list[RemediationClosureReviewRecord]] = defaultdict(list)
    for rev in input.review_records:
        reviews_by_closure[rev.closure_id].append(rev)

    closures_by_backlog: defaultdict[str, list[RemediationClosureDeclaration]] = defaultdict(list)
    for decl in input.closure_declarations:
        closures_by_backlog[decl.backlog_item_id].append(decl)

    # Compute semantic duplicate closures.
    content_hash_to_ids: defaultdict[str, list[str]] = defaultdict(list)
    for decl in input.closure_declarations:
        content_hash_to_ids[_closure_content_hash(decl)].append(decl.closure_id)
    duplicate_closure_ids = {
        closure_id
        for closure_ids in content_hash_to_ids.values()
        for closure_id in closure_ids
        if len(closure_ids) > 1
    }

    # Collect issues per backlog item for advisory/partial detection.
    issue_reasons_by_backlog: defaultdict[str, set[str]] = defaultdict(set)
    for issue in issues:
        if issue.backlog_item_id:
            issue_reasons_by_backlog[issue.backlog_item_id].update(issue.reason_codes)

    # Determine record state per backlog item using first-match-wins precedence.
    # NOT_APPLICABLE -> ORPHANED -> BLOCKED -> DISPUTED -> DUPLICATE -> REJECTED -> STALE -> PENDING_REVIEW -> PARTIAL -> CLOSED_RECORDED
    results: list[RemediationClosureResult] = []
    for ref in sorted(input.backlog_item_refs, key=lambda r: r.backlog_item_id):
        backlog_item_id = ref.backlog_item_id
        state = ref.item_state.lower()
        closures = closures_by_backlog.get(backlog_item_id, [])
        non_orphan_closures = [d for d in closures if d.closure_id not in {
            dd.closure_id for dd in input.closure_declarations if dd.backlog_item_id not in backlog_item_ids
        }]
        closure_ids = tuple(d.closure_id for d in closures)
        evidence_summary_ids = tuple(d.evidence_summary_id for d in closures)
        review_ids = tuple(
            rev.review_id for d in closures for rev in reviews_by_closure.get(d.closure_id, [])
        )
        all_reviews = [
            rev for d in closures for rev in reviews_by_closure.get(d.closure_id, [])
        ]

        record_state = _classify_record_state(
            ref=ref,
            closures=non_orphan_closures,
            all_reviews=all_reviews,
            evidence_summary_by_id=evidence_summary_by_id,
            issue_reasons=issue_reasons_by_backlog.get(backlog_item_id, set()),
            duplicate_closure_ids=duplicate_closure_ids,
            config=config,
            generated_at=generated_at,
            staleness_threshold=timedelta(seconds=config.staleness_threshold_seconds),
        )

        review_outcome = _derive_review_outcome(all_reviews, config)
        eligibility_state = _derive_eligibility_state(
            record_state, closures, all_reviews, evidence_summary_by_id, config
        )

        severity = (
            RemediationClosureSeverity.INFO
            if record_state in (RemediationClosureRecordState.CLOSED_RECORDED, RemediationClosureRecordState.NOT_APPLICABLE)
            else RemediationClosureSeverity.ADVISORY
        )
        reason_code = _record_state_to_reason_code(record_state)

        results.append(
            RemediationClosureResult(
                closure_result_id=_build_closure_result_id(
                    backlog_item_id, closure_ids, evidence_summary_ids, review_ids
                ),
                backlog_item_id=backlog_item_id,
                closure_id=closures[0].closure_id if closures else "",
                record_state=record_state,
                eligibility_state=eligibility_state,
                review_outcome=review_outcome,
                severity=severity,
                reason_codes=(reason_code,),
                title=f"Closure result for {backlog_item_id}",
                description=f"Closure record state is {record_state.value}.",
                generated_at=generated_at,
            )
        )

    return tuple(results)


def _classify_record_state(
    *,
    ref: RemediationClosureBacklogItemRef,
    closures: list[RemediationClosureDeclaration],
    all_reviews: list[RemediationClosureReviewRecord],
    evidence_summary_by_id: dict[str, RemediationClosureEvidenceSummary],
    issue_reasons: set[str],
    duplicate_closure_ids: set[str],
    config: RemediationClosureConfig,
    generated_at: datetime,
    staleness_threshold: timedelta,
) -> RemediationClosureRecordState:
    """Apply first-match-wins closure record precedence rules."""
    state = ref.item_state.lower()

    # 1. NOT_APPLICABLE
    if state == "not_applicable":
        return RemediationClosureRecordState.NOT_APPLICABLE
    required_ids = set(config.required_backlog_item_ids)
    if config.require_closure_for_all:
        required_ids.add(ref.backlog_item_id)
    if not closures and ref.backlog_item_id not in required_ids:
        return RemediationClosureRecordState.NOT_APPLICABLE

    # 2. ORPHANED - closure or evidence references unknown backlog item.
    if any(d.backlog_item_id and d.backlog_item_id not in {ref.backlog_item_id} for d in closures):
        return RemediationClosureRecordState.ORPHANED
    for d in closures:
        es = evidence_summary_by_id.get(d.evidence_summary_id)
        if es is not None and es.backlog_item_id and es.backlog_item_id != ref.backlog_item_id:
            return RemediationClosureRecordState.ORPHANED

    # 3. BLOCKED - backlog item blocked/open/conflicting or missing required evidence.
    if state in ("blocked", "open", "conflicting"):
        return RemediationClosureRecordState.BLOCKED
    if config.require_evidence_for_closure and closures:
        for d in closures:
            es = evidence_summary_by_id.get(d.evidence_summary_id)
            if es is None or es.coverage_state.lower() != "covered":
                return RemediationClosureRecordState.BLOCKED

    # 4. DISPUTED - conflicting declarations or any disputed review.
    if RemediationClosureReasonCode.CONFLICTING_CLOSURE.value in issue_reasons:
        return RemediationClosureRecordState.DISPUTED
    if any(rev.outcome.lower() == "disputed" for rev in all_reviews):
        return RemediationClosureRecordState.DISPUTED

    # 5. DUPLICATE - semantic duplicate closure declarations.
    if any(d.closure_id in duplicate_closure_ids for d in closures):
        return RemediationClosureRecordState.DUPLICATE

    # 6. REJECTED - any rejected review.
    if any(rev.outcome.lower() == "rejected" for rev in all_reviews):
        return RemediationClosureRecordState.REJECTED

    # 7. STALE - all linked closure, evidence, and review records are stale.
    if closures and all_reviews:
        all_stale = all(
            d.generated_at is not None and d.generated_at < generated_at - staleness_threshold
            for d in closures
        )
        all_evidence_stale = all(
            evidence_summary_by_id.get(d.evidence_summary_id) is not None
            and evidence_summary_by_id[d.evidence_summary_id].generated_at is not None
            and evidence_summary_by_id[d.evidence_summary_id].generated_at < generated_at - staleness_threshold
            for d in closures
        )
        all_reviews_stale = all(
            rev.generated_at is not None and rev.generated_at < generated_at - staleness_threshold
            for rev in all_reviews
        )
        if all_stale and all_evidence_stale and all_reviews_stale:
            return RemediationClosureRecordState.STALE

    # 8. PENDING_REVIEW - required review is pending or missing.
    if closures:
        has_accepted_or_not_required = any(
            rev.outcome.lower() in ("accepted", "not_required")
            for rev in all_reviews
        )
        if config.require_review and not has_accepted_or_not_required:
            return RemediationClosureRecordState.PENDING_REVIEW
        if any(rev.outcome.lower() == "pending" for rev in all_reviews):
            return RemediationClosureRecordState.PENDING_REVIEW

    # 9. PARTIAL - advisory issues exist, evidence partial, or metadata incomplete.
    if closures:
        advisory_reasons = {
            RemediationClosureReasonCode.MISSING_EVIDENCE.value,
            RemediationClosureReasonCode.MISSING_REVIEW.value,
            RemediationClosureReasonCode.MISSING_CLOSURE_METADATA.value,
            RemediationClosureReasonCode.STALE_EVIDENCE.value,
            RemediationClosureReasonCode.STALE_CLOSURE.value,
            RemediationClosureReasonCode.STALE_REVIEW.value,
            RemediationClosureReasonCode.BLOCKED_BACKLOG_ITEM.value,
            RemediationClosureReasonCode.OPEN_BACKLOG_ITEM.value,
            RemediationClosureReasonCode.CONFLICTING_BACKLOG_ITEM.value,
            RemediationClosureReasonCode.ORPHAN_EVIDENCE.value,
            RemediationClosureReasonCode.ORPHAN_CLOSURE.value,
            RemediationClosureReasonCode.ORPHAN_REVIEW.value,
            RemediationClosureReasonCode.ORPHAN_LINK.value,
            RemediationClosureReasonCode.REJECTED_REVIEW.value,
            RemediationClosureReasonCode.PENDING_REVIEW.value,
            RemediationClosureReasonCode.DISPUTED_REVIEW.value,
            RemediationClosureReasonCode.CONSISTENCY_DEGRADED.value,
        }
        if any(code in advisory_reasons for code in issue_reasons):
            return RemediationClosureRecordState.PARTIAL
        for d in closures:
            es = evidence_summary_by_id.get(d.evidence_summary_id)
            if es is not None and es.coverage_state.lower() == "partial":
                return RemediationClosureRecordState.PARTIAL

    # 10. CLOSED_RECORDED
    if closures:
        return RemediationClosureRecordState.CLOSED_RECORDED

    # Fallback for required items without closure.
    return RemediationClosureRecordState.NOT_APPLICABLE


def _derive_review_outcome(
    all_reviews: list[RemediationClosureReviewRecord],
    config: RemediationClosureConfig,
) -> RemediationClosureReviewOutcome:
    """Derive the effective review outcome for a backlog item."""
    if not all_reviews:
        if config.require_review:
            return RemediationClosureReviewOutcome.PENDING
        return RemediationClosureReviewOutcome.NOT_REQUIRED
    for rev in all_reviews:
        if rev.outcome.lower() == "accepted":
            return RemediationClosureReviewOutcome.ACCEPTED
    for rev in all_reviews:
        if rev.outcome.lower() == "disputed":
            return RemediationClosureReviewOutcome.DISPUTED
    for rev in all_reviews:
        if rev.outcome.lower() == "rejected":
            return RemediationClosureReviewOutcome.REJECTED
    for rev in all_reviews:
        if rev.outcome.lower() == "pending":
            return RemediationClosureReviewOutcome.PENDING
    for rev in all_reviews:
        if rev.outcome.lower() == "not_required":
            return RemediationClosureReviewOutcome.NOT_REQUIRED
    return RemediationClosureReviewOutcome.NOT_APPLICABLE


def _derive_eligibility_state(
    record_state: RemediationClosureRecordState,
    closures: list[RemediationClosureDeclaration],
    all_reviews: list[RemediationClosureReviewRecord],
    evidence_summary_by_id: dict[str, RemediationClosureEvidenceSummary],
    config: RemediationClosureConfig,
) -> RemediationClosureEligibilityState:
    """Derive eligibility state from record state and evidence coverage."""
    if record_state is RemediationClosureRecordState.NOT_APPLICABLE:
        return RemediationClosureEligibilityState.NOT_APPLICABLE
    if record_state is RemediationClosureRecordState.STALE:
        return RemediationClosureEligibilityState.STALE
    if record_state is RemediationClosureRecordState.DISPUTED:
        return RemediationClosureEligibilityState.DISPUTED
    if record_state is RemediationClosureRecordState.BLOCKED:
        return RemediationClosureEligibilityState.INELIGIBLE
    if record_state is RemediationClosureRecordState.REJECTED:
        return RemediationClosureEligibilityState.INELIGIBLE
    if record_state is RemediationClosureRecordState.PENDING_REVIEW:
        return RemediationClosureEligibilityState.PENDING_REVIEW
    if record_state is RemediationClosureRecordState.DUPLICATE:
        return RemediationClosureEligibilityState.INELIGIBLE

    # Check evidence coverage.
    has_partial = False
    for d in closures:
        es = evidence_summary_by_id.get(d.evidence_summary_id)
        if es is None or es.coverage_state.lower() == "missing":
            if config.require_evidence_for_closure:
                return RemediationClosureEligibilityState.INELIGIBLE
            has_partial = True
        elif es.coverage_state.lower() == "partial":
            has_partial = True

    if record_state is RemediationClosureRecordState.PARTIAL or has_partial:
        return RemediationClosureEligibilityState.PARTIAL

    if record_state is RemediationClosureRecordState.CLOSED_RECORDED:
        return RemediationClosureEligibilityState.ELIGIBLE

    return RemediationClosureEligibilityState.NOT_APPLICABLE


def _record_state_to_reason_code(state: RemediationClosureRecordState) -> str:
    """Map a closure record state to its primary reason code."""
    mapping = {
        RemediationClosureRecordState.CLOSED_RECORDED: RemediationClosureReasonCode.CLOSURE_RECORDED.value,
        RemediationClosureRecordState.PARTIAL: RemediationClosureReasonCode.CONSISTENCY_DEGRADED.value,
        RemediationClosureRecordState.BLOCKED: RemediationClosureReasonCode.SAFETY_BLOCKED.value,
        RemediationClosureRecordState.PENDING_REVIEW: RemediationClosureReasonCode.PENDING_REVIEW.value,
        RemediationClosureRecordState.REJECTED: RemediationClosureReasonCode.REJECTED_REVIEW.value,
        RemediationClosureRecordState.DISPUTED: RemediationClosureReasonCode.DISPUTED_REVIEW.value,
        RemediationClosureRecordState.STALE: RemediationClosureReasonCode.STALE_CLOSURE.value,
        RemediationClosureRecordState.DUPLICATE: RemediationClosureReasonCode.DUPLICATE_ID.value,
        RemediationClosureRecordState.ORPHANED: RemediationClosureReasonCode.ORPHAN_CLOSURE.value,
        RemediationClosureRecordState.NOT_APPLICABLE: RemediationClosureReasonCode.NOT_APPLICABLE.value,
    }
    return mapping[state]


def _aggregate_state(
    issues: tuple[RemediationClosureIssue, ...],
    backlog_item_count: int,
    strict: bool,
) -> tuple[RemediationClosureState, RemediationClosureReasonCode]:
    """Determine report aggregate state from issue severities and reason codes."""
    has_blocking = any(
        issue.severity is RemediationClosureSeverity.BLOCKING
        or any(code in _BLOCKING_REASON_CODES for code in issue.reason_codes)
        for issue in issues
    )
    has_advisory = any(
        issue.severity is RemediationClosureSeverity.ADVISORY
        or any(code in _ADVISORY_REASON_CODES for code in issue.reason_codes)
        for issue in issues
    )

    if has_blocking:
        state = RemediationClosureState.BLOCKED
        reason_code = RemediationClosureReasonCode.SAFETY_BLOCKED
    elif has_advisory:
        state = RemediationClosureState.DEGRADED
        reason_code = RemediationClosureReasonCode.CONSISTENCY_DEGRADED
    elif backlog_item_count == 0:
        state = RemediationClosureState.NOT_APPLICABLE
        reason_code = RemediationClosureReasonCode.NOT_APPLICABLE
    else:
        state = RemediationClosureState.OK
        reason_code = RemediationClosureReasonCode.OK

    if strict and state in (RemediationClosureState.DEGRADED, RemediationClosureState.BLOCKED):
        state = RemediationClosureState.BLOCKED
        reason_code = RemediationClosureReasonCode.SAFETY_BLOCKED

    return state, reason_code


def _aggregate_reason_codes(
    issues: tuple[RemediationClosureIssue, ...],
    state_reason_code: RemediationClosureReasonCode,
) -> tuple[RemediationClosureReasonCode, ...]:
    """Collect unique reason codes from issues plus the state-level code."""
    codes: set[str] = {state_reason_code.value}
    for issue in issues:
        for code in issue.reason_codes:
            codes.add(code)
    ordered = sorted(codes)
    if state_reason_code.value in ordered:
        ordered.remove(state_reason_code.value)
    return (state_reason_code,) + tuple(RemediationClosureReasonCode(code) for code in ordered)


def _build_data_quality(
    input: RemediationClosureInput,
    closure_results: tuple[RemediationClosureResult, ...],
    issues: tuple[RemediationClosureIssue, ...],
    dq_updates: dict[str, int],
) -> RemediationClosureDataQuality:
    """Build the data quality summary from counts."""
    sections_present = sum(
        1
        for collection in (
            input.backlog_item_refs,
            input.evidence_summaries,
            input.closure_declarations,
            input.review_records,
            input.links,
            issues,
            closure_results,
        )
        if len(collection) > 0
    )
    return RemediationClosureDataQuality(
        total_backlog_item_refs=len(input.backlog_item_refs),
        total_evidence_summaries=len(input.evidence_summaries),
        total_closure_declarations=len(input.closure_declarations),
        total_review_records=len(input.review_records),
        total_links=len(input.links),
        total_issues=len(issues),
        total_closure_results=len(closure_results),
        duplicate_id_count=0,
        orphan_evidence_count=dq_updates.get("orphan_evidence_count", 0),
        orphan_closure_count=dq_updates.get("orphan_closure_count", 0),
        orphan_review_count=dq_updates.get("orphan_review_count", 0),
        orphan_link_count=dq_updates.get("orphan_link_count", 0),
        conflicting_closure_count=dq_updates.get("conflicting_closure_count", 0),
        conflicting_review_count=dq_updates.get("conflicting_review_count", 0),
        stale_evidence_count=dq_updates.get("stale_evidence_count", 0),
        stale_closure_count=dq_updates.get("stale_closure_count", 0),
        stale_review_count=dq_updates.get("stale_review_count", 0),
        missing_evidence_count=dq_updates.get("missing_evidence_count", 0),
        missing_review_count=dq_updates.get("missing_review_count", 0),
        missing_closure_metadata_count=dq_updates.get("missing_closure_metadata_count", 0),
        rejected_review_count=dq_updates.get("rejected_review_count", 0),
        pending_review_count=dq_updates.get("pending_review_count", 0),
        disputed_review_count=dq_updates.get("disputed_review_count", 0),
        manual_review_required_count=dq_updates.get("manual_review_required_count", 0),
        blocked_backlog_item_count=dq_updates.get("blocked_backlog_item_count", 0),
        open_backlog_item_count=dq_updates.get("open_backlog_item_count", 0),
        conflicting_backlog_item_count=dq_updates.get("conflicting_backlog_item_count", 0),
        acknowledged_backlog_item_count=dq_updates.get("acknowledged_backlog_item_count", 0),
        deferred_backlog_item_count=dq_updates.get("deferred_backlog_item_count", 0),
        not_applicable_backlog_item_count=dq_updates.get("not_applicable_backlog_item_count", 0),
        unsafe_content_count=0,
        forbidden_term_count=0,
        sections_present=sections_present,
    )


def _build_safety_flags(
    issues: tuple[RemediationClosureIssue, ...],
    config: RemediationClosureConfig,
) -> RemediationClosureSafetyFlags:
    """Build safety flags from issue reason codes."""
    has_forbidden_terms = any(
        RemediationClosureReasonCode.FORBIDDEN_TERM_PRESENT.value in issue.reason_codes
        for issue in issues
    )
    has_unsafe_content = any(
        RemediationClosureReasonCode.UNSAFE_CONTENT.value in issue.reason_codes
        for issue in issues
    )
    return RemediationClosureSafetyFlags(
        has_forbidden_terms=has_forbidden_terms,
        has_unsafe_content=has_unsafe_content,
    )


def _emit_manual_review_issues(
    closure_results: tuple[RemediationClosureResult, ...],
    generated_at: datetime,
) -> tuple[RemediationClosureIssue, ...]:
    """Emit INFO-level manual-review-required issues for disputed/pending/partial results."""
    issues: list[RemediationClosureIssue] = []
    for result in closure_results:
        if result.record_state in (
            RemediationClosureRecordState.DISPUTED,
            RemediationClosureRecordState.PENDING_REVIEW,
            RemediationClosureRecordState.PARTIAL,
        ):
            issues.append(
                _make_issue(
                    issue_type=RemediationClosureIssueType.MANUAL_REVIEW_REQUIRED,
                    severity=RemediationClosureSeverity.INFO,
                    reason_codes=(RemediationClosureReasonCode.MANUAL_REVIEW_REQUIRED.value,),
                    title="Manual review required",
                    description=f"Closure result for {result.backlog_item_id} requires manual human review.",
                    backlog_item_id=result.backlog_item_id,
                    closure_id=result.closure_id,
                    generated_at=generated_at,
                )
            )
    return tuple(issues)
