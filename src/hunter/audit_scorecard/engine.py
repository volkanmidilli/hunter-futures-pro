"""In-memory engine for hunter.audit_scorecard package."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from json import dumps
from typing import Any

from hunter.audit_scorecard.models import (
    FORBIDDEN_AUDIT_SCORECARD_TERMS,
    AuditScorecardConfig,
    AuditScorecardDataQuality,
    AuditScorecardDimension,
    AuditScorecardDimensionResult,
    AuditScorecardDimensionState,
    AuditScorecardEvidenceRef,
    AuditScorecardFinding,
    AuditScorecardInput,
    AuditScorecardLink,
    AuditScorecardLinkType,
    AuditScorecardReasonCode,
    AuditScorecardReport,
    AuditScorecardSafetyFlags,
    AuditScorecardSeverity,
    AuditScorecardState,
    _check_forbidden_mapping,
    _has_forbidden_term,
    _has_forbidden_terms_in_text_fields,
)


SUPPORTING_LINK_TYPES: frozenset[AuditScorecardLinkType] = frozenset({
    AuditScorecardLinkType.COVERS,
    AuditScorecardLinkType.SUPPORTS,
    AuditScorecardLinkType.DERIVED_FROM,
})

VALID_UPSTREAM_STATES: frozenset[str] = frozenset({
    "ok", "degraded", "blocked", "not_applicable", "unknown",
})


def has_unsafe_audit_scorecard_content(
    text: str | None = None,
    metadata: dict[str, Any] | None = None,
    tags: list[str] | None = None,
    forbidden_terms: frozenset[str] | None = None,
) -> bool:
    """Return True if text, tags, or metadata contain forbidden audit scorecard terms."""
    terms = forbidden_terms or FORBIDDEN_AUDIT_SCORECARD_TERMS
    if text is not None and _has_forbidden_term(text, terms):
        return True
    if tags is not None:
        for tag in tags:
            if isinstance(tag, str) and _has_forbidden_term(tag, terms):
                return True
    if metadata is not None and _check_forbidden_mapping(metadata, terms):
        return True
    return False


def build_audit_scorecard_report(
    input: AuditScorecardInput,
    config: AuditScorecardConfig | None = None,
    strict: bool | None = None,
) -> AuditScorecardReport:
    """Build a deterministic audit readiness scorecard report from in-memory declarations."""
    if config is None:
        config = input.config
    if strict is not None:
        config = AuditScorecardConfig(
            strict=strict,
            generated_at=config.generated_at,
            default_json_path=config.default_json_path,
            default_csv_path=config.default_csv_path,
            default_markdown_path=config.default_markdown_path,
            staleness_threshold_seconds=config.staleness_threshold_seconds,
        )

    generated_at = _resolve_generated_at(input, config)

    if has_unsafe_audit_scorecard_content(metadata=dict(input.metadata)):
        return AuditScorecardReport.blocked(
            input=input,
            reason_code=AuditScorecardReasonCode.UNSAFE_CONTENT,
            generated_at=generated_at,
            notes=(
                "Scorecard blocked due to unsafe content in input metadata.",
                "Scorecard output is for human audit only and is not a "
                "trading signal, recommendation, or certification of trading readiness.",
            ),
        )

    validation_result = _validate_input(input, generated_at)
    if validation_result is not None:
        return validation_result

    forbidden_offenders = _has_forbidden_terms_in_text_fields(
        dimensions=input.dimensions,
        evidence_refs=input.evidence_refs,
        findings=input.findings,
        links=input.links,
        forbidden_terms=FORBIDDEN_AUDIT_SCORECARD_TERMS,
    )
    if forbidden_offenders:
        return AuditScorecardReport.blocked(
            input=input,
            reason_code=AuditScorecardReasonCode.FORBIDDEN_TERM_PRESENT,
            generated_at=generated_at,
            notes=(
                "Scorecard blocked due to forbidden terms in caller-provided text fields.",
                "Scorecard output is for human audit only and is not a "
                "trading signal, recommendation, or certification of trading readiness.",
            ),
        )

    incoming_by_target = _build_incoming_links(input.links)
    outgoing_by_source = _build_outgoing_links(input.links)
    link_pairs = _build_link_pairs(input.links)
    dimension_ids = {dim.dimension_id for dim in input.dimensions}

    dimension_results = _build_dimension_results(input, incoming_by_target, dimension_ids, generated_at)
    findings = _build_findings(input, dimension_results, incoming_by_target, outgoing_by_source, link_pairs, dimension_ids, generated_at)
    dimension_results = _update_finding_counts(dimension_results, list(input.findings) + findings)
    all_findings = sorted(input.findings + tuple(findings), key=lambda f: (f.dimension_id, f.finding_id, f.reason_code.value, f.severity.value))

    dimensions = sorted(input.dimensions, key=lambda d: d.dimension_id)
    evidence_refs = sorted(input.evidence_refs, key=lambda r: r.evidence_id)
    links = sorted(input.links, key=lambda link: (link.source_id, link.target_id, link.link_type.value, link.link_id))

    data_quality = _build_data_quality(dimension_results, input, all_findings, generated_at)
    safety_flags = _build_safety_flags(dimension_results, all_findings)
    report_state, report_level_code = _aggregate_report_state(dimension_results, all_findings, config.strict)
    reason_codes = _aggregate_reason_codes(all_findings, report_level_code)

    return AuditScorecardReport(
        report_id=_build_report_id(input, generated_at),
        state=report_state,
        reason_codes=reason_codes,
        dimensions=tuple(dimensions),
        dimension_results=tuple(dimension_results),
        evidence_refs=tuple(evidence_refs),
        findings=tuple(all_findings),
        links=tuple(links),
        data_quality=data_quality,
        safety_flags=safety_flags,
        generated_at=generated_at,
        project_version=input.project_version,
        notes=(
            "Scorecard output is for human audit only.",
            "This is not a trading signal, recommendation, or certification of trading readiness.",
            "Completeness percentages are descriptive metrics, not approval scores.",
        ),
    )


def _resolve_generated_at(input: AuditScorecardInput, config: AuditScorecardConfig) -> datetime:
    if input.generated_at is not None:
        return input.generated_at
    if getattr(config, "generated_at", None) is not None:
        return config.generated_at
    return datetime.now(timezone.utc)


def _validate_input(input: AuditScorecardInput, generated_at: datetime) -> AuditScorecardReport | None:
    if not input.dimensions:
        return AuditScorecardReport.blocked(
            input=input,
            reason_code=AuditScorecardReasonCode.MISSING_REQUIRED_DIMENSION,
            generated_at=generated_at,
            notes=("Input validation failed: dimensions tuple is empty.",),
        )

    duplicate_reason = _find_duplicate_reason(input)
    if duplicate_reason is not None:
        return AuditScorecardReport.blocked(
            input=input,
            reason_code=duplicate_reason,
            generated_at=generated_at,
            notes=("Input validation failed: duplicate IDs detected.",),
        )
    return None


def _find_duplicate_reason(input: AuditScorecardInput) -> AuditScorecardReasonCode | None:
    checks = [
        (input.dimensions, "dimension_id", AuditScorecardReasonCode.DUPLICATE_DIMENSION_ID),
        (input.evidence_refs, "evidence_id", AuditScorecardReasonCode.DUPLICATE_EVIDENCE_ID),
        (input.findings, "finding_id", AuditScorecardReasonCode.DUPLICATE_FINDING_ID),
        (input.links, "link_id", AuditScorecardReasonCode.DUPLICATE_LINK_ID),
    ]
    for items, attr, reason_code in checks:
        seen: set[str] = set()
        for item in items:
            item_id = getattr(item, attr)
            if item_id in seen:
                return reason_code
            seen.add(item_id)
    return None


def _build_dimension_results(
    input: AuditScorecardInput,
    incoming_by_target: dict[str, list[AuditScorecardLink]],
    dimension_ids: set[str],
    generated_at: datetime,
) -> list[AuditScorecardDimensionResult]:
    results = [_classify_dimension(dim, input, incoming_by_target, dimension_ids, generated_at) for dim in input.dimensions]
    results.sort(key=lambda r: r.dimension_id)
    return results


def _classify_dimension(
    dim: AuditScorecardDimension,
    input: AuditScorecardInput,
    incoming_by_target: dict[str, list[AuditScorecardLink]],
    dimension_ids: set[str],
    generated_at: datetime,
) -> AuditScorecardDimensionResult:
    if dim.not_applicable:
        return AuditScorecardDimensionResult(
            dimension_id=dim.dimension_id,
            dimension_state=AuditScorecardDimensionState.NOT_APPLICABLE,
            severity=AuditScorecardSeverity.ADVISORY,
            completeness_percent=0,
            evidence_count=0,
            finding_count=0,
            reason_codes=(AuditScorecardReasonCode.NOT_APPLICABLE.value,),
            message=f"Dimension {dim.dimension_id} is not applicable.",
        )

    incoming = incoming_by_target.get(dim.dimension_id, [])
    supporting_links = [link for link in incoming if link.link_type in SUPPORTING_LINK_TYPES]
    evidence_count = len(supporting_links)

    required_link_types = {t.lower() for t in dim.required_link_types}
    present_link_types = {link.link_type.value for link in incoming if link.link_type in SUPPORTING_LINK_TYPES}
    missing_link_types = required_link_types - present_link_types

    expected = dim.expected_evidence_count
    required_total = (expected if expected is not None else 0) + len(required_link_types)
    present_total = evidence_count + len(required_link_types & present_link_types)
    completeness_percent = 100 if required_total == 0 else min(100, int(present_total / required_total * 100))

    upstream_states = _collect_upstream_states(dim, input.upstream_states)
    has_upstream_blocked = "blocked" in upstream_states
    has_upstream_degraded = "degraded" in upstream_states
    has_upstream_unknown = "unknown" in upstream_states

    blocking_finding_on_dim = any(
        finding.dimension_id == dim.dimension_id and finding.severity is AuditScorecardSeverity.BLOCKING
        for finding in input.findings
    )
    manual_review_missing = dim.requires_manual_review and not any(
        link.link_type is AuditScorecardLinkType.MANUALLY_REVIEWED and link.target_id == dim.dimension_id
        for link in incoming
    )

    if has_upstream_blocked or blocking_finding_on_dim:
        state = AuditScorecardDimensionState.BLOCKED
        reason_codes = [AuditScorecardReasonCode.UPSTREAM_BLOCKED.value]
        if blocking_finding_on_dim:
            reason_codes.append(AuditScorecardReasonCode.CONFLICTING_FINDING.value)
        message = f"Dimension {dim.dimension_id} is blocked."
        severity = AuditScorecardSeverity.BLOCKING
    elif has_upstream_degraded:
        state = AuditScorecardDimensionState.DEGRADED
        reason_codes = [AuditScorecardReasonCode.UPSTREAM_DEGRADED.value]
        message = f"Dimension {dim.dimension_id} has degraded upstream state."
        severity = AuditScorecardSeverity.ADVISORY
    elif dim.required and evidence_count == 0 and expected != 0:
        state = AuditScorecardDimensionState.MISSING
        reason_codes = [AuditScorecardReasonCode.MISSING_SUPPORTING_EVIDENCE.value]
        message = f"Dimension {dim.dimension_id} is missing supporting evidence."
        completeness_percent = 0
        severity = dim.severity
    elif missing_link_types or (expected is not None and evidence_count < expected):
        state = AuditScorecardDimensionState.PARTIAL
        reason_codes = [AuditScorecardReasonCode.MISSING_SUPPORTING_EVIDENCE.value]
        message = f"Dimension {dim.dimension_id} has partial coverage."
        severity = AuditScorecardSeverity.ADVISORY
    elif manual_review_missing:
        state = AuditScorecardDimensionState.DEGRADED
        reason_codes = [AuditScorecardReasonCode.MISSING_MANUAL_REVIEW.value]
        message = f"Dimension {dim.dimension_id} requires manual review."
        severity = AuditScorecardSeverity.ADVISORY
    else:
        state = AuditScorecardDimensionState.COMPLETE
        reason_codes = [AuditScorecardReasonCode.OK.value]
        message = f"Dimension {dim.dimension_id} is complete."
        completeness_percent = 100
        severity = AuditScorecardSeverity.ADVISORY

    if has_upstream_unknown and AuditScorecardReasonCode.UNKNOWN_UPSTREAM_STATE.value not in reason_codes:
        reason_codes.append(AuditScorecardReasonCode.UNKNOWN_UPSTREAM_STATE.value)

    return AuditScorecardDimensionResult(
        dimension_id=dim.dimension_id,
        dimension_state=state,
        severity=severity,
        completeness_percent=completeness_percent,
        evidence_count=evidence_count,
        finding_count=0,
        reason_codes=tuple(sorted(set(reason_codes))),
        message=message,
    )


def _collect_upstream_states(dim: AuditScorecardDimension, upstream_states: Mapping[str, str]) -> set[str]:
    states: set[str] = set()
    for uid in (*dim.upstream_package_ids, *dim.upstream_report_ids):
        raw = upstream_states.get(uid, "unknown")
        normalized = str(raw).strip().lower() if isinstance(raw, str) else "unknown"
        if normalized not in VALID_UPSTREAM_STATES:
            normalized = "unknown"
        states.add(normalized)
    return states


def _update_finding_counts(
    dimension_results: list[AuditScorecardDimensionResult],
    findings: list[AuditScorecardFinding],
) -> list[AuditScorecardDimensionResult]:
    """Recreate dimension results with per-dimension finding counts."""
    counts: dict[str, int] = {}
    for f in findings:
        counts[f.dimension_id] = counts.get(f.dimension_id, 0) + 1
    updated: list[AuditScorecardDimensionResult] = []
    for r in dimension_results:
        cnt = counts.get(r.dimension_id, 0)
        updated.append(
            AuditScorecardDimensionResult(
                dimension_id=r.dimension_id,
                dimension_state=r.dimension_state,
                severity=r.severity,
                completeness_percent=r.completeness_percent,
                evidence_count=r.evidence_count,
                finding_count=cnt,
                reason_codes=r.reason_codes,
                message=r.message,
            )
        )
    return updated


def _build_findings(
    input: AuditScorecardInput,
    dimension_results: list[AuditScorecardDimensionResult],
    incoming_by_target: dict[str, list[AuditScorecardLink]],
    outgoing_by_source: dict[str, list[AuditScorecardLink]],
    link_pairs: dict[tuple[str, str], set[AuditScorecardLinkType]],
    dimension_ids: set[str],
    generated_at: datetime,
) -> list[AuditScorecardFinding]:
    findings: list[AuditScorecardFinding] = []
    result_by_dim = {r.dimension_id: r for r in dimension_results}

    for dim in input.dimensions:
        result = result_by_dim[dim.dimension_id]
        if result.dimension_state is AuditScorecardDimensionState.MISSING:
            findings.append(AuditScorecardFinding(
                finding_id=f"{dim.dimension_id}_missing_evidence",
                dimension_id=dim.dimension_id,
                severity=dim.severity,
                reason_code=AuditScorecardReasonCode.MISSING_SUPPORTING_EVIDENCE,
                message=f"Dimension {dim.dimension_id} is missing supporting evidence.",
                evidence=(),
            ))
        elif result.dimension_state is AuditScorecardDimensionState.BLOCKED:
            findings.append(AuditScorecardFinding(
                finding_id=f"{dim.dimension_id}_upstream_blocked",
                dimension_id=dim.dimension_id,
                severity=AuditScorecardSeverity.BLOCKING,
                reason_code=AuditScorecardReasonCode.UPSTREAM_BLOCKED,
                message=f"Dimension {dim.dimension_id} has an upstream blocked state.",
                evidence=(),
            ))
        elif result.dimension_state is AuditScorecardDimensionState.DEGRADED:
            upstream_states = _collect_upstream_states(dim, input.upstream_states)
            if "degraded" in upstream_states:
                findings.append(AuditScorecardFinding(
                    finding_id=f"{dim.dimension_id}_upstream_degraded",
                    dimension_id=dim.dimension_id,
                    severity=AuditScorecardSeverity.ADVISORY,
                    reason_code=AuditScorecardReasonCode.UPSTREAM_DEGRADED,
                    message=f"Dimension {dim.dimension_id} has an upstream degraded state.",
                    evidence=(),
                ))
            if dim.requires_manual_review and not any(
                link.link_type is AuditScorecardLinkType.MANUALLY_REVIEWED and link.target_id == dim.dimension_id
                for link in incoming_by_target.get(dim.dimension_id, [])
            ):
                findings.append(AuditScorecardFinding(
                    finding_id=f"{dim.dimension_id}_missing_manual_review",
                    dimension_id=dim.dimension_id,
                    severity=AuditScorecardSeverity.ADVISORY,
                    reason_code=AuditScorecardReasonCode.MISSING_MANUAL_REVIEW,
                    message=f"Dimension {dim.dimension_id} requires manual review.",
                    evidence=(),
                ))

    for dim in input.dimensions:
        upstream_states = _collect_upstream_states(dim, input.upstream_states)
        if "unknown" in upstream_states:
            findings.append(AuditScorecardFinding(
                finding_id=f"{dim.dimension_id}_unknown_upstream",
                dimension_id=dim.dimension_id,
                severity=AuditScorecardSeverity.ADVISORY,
                reason_code=AuditScorecardReasonCode.UNKNOWN_UPSTREAM_STATE,
                message=f"Dimension {dim.dimension_id} has an unknown upstream state.",
                evidence=(),
            ))

    reviewed_targets = {link.target_id for link in input.links if link.link_type is AuditScorecardLinkType.MANUALLY_REVIEWED}
    for ref in input.evidence_refs:
        if ref.requires_manual_review and ref.evidence_id not in reviewed_targets:
            findings.append(AuditScorecardFinding(
                finding_id=f"{ref.evidence_id}_missing_manual_review",
                dimension_id="",
                severity=AuditScorecardSeverity.ADVISORY,
                reason_code=AuditScorecardReasonCode.MISSING_MANUAL_REVIEW,
                message=f"Evidence ref {ref.evidence_id} requires manual review.",
                evidence=(ref.reference,),
            ))

    if input.config.staleness_threshold_seconds is not None:
        threshold = timedelta(seconds=input.config.staleness_threshold_seconds)
        for ref in input.evidence_refs:
            if ref.generated_at is not None and ref.generated_at < generated_at - threshold:
                findings.append(AuditScorecardFinding(
                    finding_id=f"{ref.evidence_id}_stale",
                    dimension_id="",
                    severity=AuditScorecardSeverity.ADVISORY,
                    reason_code=AuditScorecardReasonCode.STALE_EVIDENCE,
                    message=f"Evidence ref {ref.evidence_id} is older than the staleness threshold.",
                    evidence=(str(ref.generated_at),),
                ))

    connected_evidence = set()
    for link in input.links:
        if link.source_id in dimension_ids or link.target_id in dimension_ids:
            connected_evidence.add(link.source_id)
            connected_evidence.add(link.target_id)
    for ref in input.evidence_refs:
        if ref.evidence_id not in connected_evidence:
            findings.append(AuditScorecardFinding(
                finding_id=f"{ref.evidence_id}_orphan",
                dimension_id="",
                severity=AuditScorecardSeverity.ADVISORY,
                reason_code=AuditScorecardReasonCode.ORPHAN_EVIDENCE,
                message=f"Evidence ref {ref.evidence_id} has no link to any dimension.",
                evidence=(ref.reference,),
            ))

    for link in input.links:
        if link.source_id not in dimension_ids and link.target_id not in dimension_ids:
            findings.append(AuditScorecardFinding(
                finding_id=f"{link.link_id}_orphan",
                dimension_id="",
                severity=AuditScorecardSeverity.ADVISORY,
                reason_code=AuditScorecardReasonCode.ORPHAN_LINK,
                message=f"Link {link.link_id} has no endpoint connected to a dimension.",
                evidence=(link.link_id,),
            ))

    for (source_id, target_id), types in link_pairs.items():
        if AuditScorecardLinkType.CONTRADICTS in types and (SUPPORTING_LINK_TYPES & types):
            dim_endpoint = source_id if source_id in dimension_ids else target_id if target_id in dimension_ids else ""
            findings.append(AuditScorecardFinding(
                finding_id=f"{source_id}_{target_id}_conflict",
                dimension_id=dim_endpoint,
                severity=AuditScorecardSeverity.BLOCKING,
                reason_code=AuditScorecardReasonCode.CONFLICTING_LINK,
                message=f"Conflicting link types between {source_id} and {target_id}: {sorted(t.value for t in types)}",
                evidence=tuple(sorted(t.value for t in types)),
            ))

    seen: dict[tuple[str, str], AuditScorecardFinding] = {}
    for finding in input.findings:
        key = (finding.dimension_id, finding.finding_id)
        if key in seen:
            findings.append(AuditScorecardFinding(
                finding_id=f"{finding.finding_id}_conflict",
                dimension_id=finding.dimension_id,
                severity=AuditScorecardSeverity.BLOCKING,
                reason_code=AuditScorecardReasonCode.CONFLICTING_FINDING,
                message=f"Conflicting finding_id {finding.finding_id!r} for dimension {finding.dimension_id}.",
                evidence=(finding.finding_id,),
            ))
        seen[key] = finding

    return findings


def _build_incoming_links(links: tuple[AuditScorecardLink, ...]) -> dict[str, list[AuditScorecardLink]]:
    incoming: dict[str, list[AuditScorecardLink]] = defaultdict(list)
    for link in links:
        incoming[link.target_id].append(link)
    return incoming


def _build_outgoing_links(links: tuple[AuditScorecardLink, ...]) -> dict[str, list[AuditScorecardLink]]:
    outgoing: dict[str, list[AuditScorecardLink]] = defaultdict(list)
    for link in links:
        outgoing[link.source_id].append(link)
    return outgoing


def _build_link_pairs(links: tuple[AuditScorecardLink, ...]) -> dict[tuple[str, str], set[AuditScorecardLinkType]]:
    pairs: dict[tuple[str, str], set[AuditScorecardLinkType]] = defaultdict(set)
    for link in links:
        pairs[(link.source_id, link.target_id)].add(link.link_type)
    return pairs


def _build_report_id(input: AuditScorecardInput, generated_at: datetime) -> str:
    """Return a deterministic report_id from sorted IDs. No path opening."""
    payload = {
        "dimension_ids": sorted(dim.dimension_id for dim in input.dimensions),
        "evidence_ids": sorted(ref.evidence_id for ref in input.evidence_refs),
        "finding_ids": sorted(finding.finding_id for finding in input.findings),
        "link_ids": sorted(link.link_id for link in input.links),
        "project_version": input.project_version or "",
        "generated_at": generated_at.isoformat(),
    }
    canonical = dumps(payload, sort_keys=True, separators=(",", ":"))
    return f"audit_scorecard_{sha256(canonical.encode('utf-8')).hexdigest()[:16]}"


def _build_data_quality(
    dimension_results: list[AuditScorecardDimensionResult],
    input: AuditScorecardInput,
    findings: list[AuditScorecardFinding],
    generated_at: datetime,
) -> AuditScorecardDataQuality:
    state_distribution: dict[str, int] = defaultdict(int)
    for result in dimension_results:
        state_distribution[result.dimension_state.value] += 1

    sections = 0
    if input.dimensions:
        sections += 1
    if dimension_results:
        sections += 1
    if input.evidence_refs:
        sections += 1
    if findings:
        sections += 1
    if input.links:
        sections += 1
    sections += 1  # data_quality
    sections += 1  # safety_flags
    if input.project_version:
        sections += 1
    if generated_at:
        sections += 1

    return AuditScorecardDataQuality(
        dimension_count=len(input.dimensions),
        evidence_count=len(input.evidence_refs),
        finding_count=len(findings),
        link_count=len(input.links),
        sections_present=sections,
        state_distribution=dict(state_distribution),
        notes=(
            "Data quality summary counts dimensions and findings by state.",
            "All values are derived from caller-provided in-memory declarations.",
        ),
    )


def _build_safety_flags(
    dimension_results: list[AuditScorecardDimensionResult],
    findings: list[AuditScorecardFinding],
) -> AuditScorecardSafetyFlags:
    non_ok_states = {
        AuditScorecardDimensionState.MISSING,
        AuditScorecardDimensionState.PARTIAL,
        AuditScorecardDimensionState.BLOCKED,
        AuditScorecardDimensionState.DEGRADED,
    }
    active_results = [r for r in dimension_results if r.dimension_state in non_ok_states]
    has_blocked = any(
        r.severity is AuditScorecardSeverity.BLOCKING for r in active_results
    ) or any(f.severity is AuditScorecardSeverity.BLOCKING for f in findings)
    has_degraded = any(
        r.severity is AuditScorecardSeverity.ADVISORY for r in active_results
    ) or any(f.severity is AuditScorecardSeverity.ADVISORY for f in findings)
    has_conflicting_findings = any(
        f.reason_code is AuditScorecardReasonCode.CONFLICTING_FINDING for f in findings
    )
    has_conflicting_links = any(
        f.reason_code is AuditScorecardReasonCode.CONFLICTING_LINK for f in findings
    )
    has_stale_evidence = any(
        f.reason_code is AuditScorecardReasonCode.STALE_EVIDENCE for f in findings
    )
    has_missing_manual_review = any(
        f.reason_code is AuditScorecardReasonCode.MISSING_MANUAL_REVIEW for f in findings
    )
    has_orphan_evidence = any(
        f.reason_code is AuditScorecardReasonCode.ORPHAN_EVIDENCE for f in findings
    )
    has_orphan_links = any(
        f.reason_code is AuditScorecardReasonCode.ORPHAN_LINK for f in findings
    )
    has_forbidden_terms = any(
        f.reason_code in {
            AuditScorecardReasonCode.FORBIDDEN_TERM_PRESENT,
            AuditScorecardReasonCode.UNSAFE_CONTENT,
        }
        for f in findings
    )
    return AuditScorecardSafetyFlags(
        has_blocked=has_blocked,
        has_degraded=has_degraded,
        has_conflicting_findings=has_conflicting_findings,
        has_conflicting_links=has_conflicting_links,
        has_stale_evidence=has_stale_evidence,
        has_missing_manual_review=has_missing_manual_review,
        has_orphan_evidence=has_orphan_evidence,
        has_orphan_links=has_orphan_links,
        has_forbidden_terms=has_forbidden_terms,
    )


def _aggregate_report_state(
    dimension_results: list[AuditScorecardDimensionResult],
    findings: list[AuditScorecardFinding],
    strict: bool,
) -> tuple[AuditScorecardState, AuditScorecardReasonCode]:
    non_ok_states = {
        AuditScorecardDimensionState.MISSING,
        AuditScorecardDimensionState.PARTIAL,
        AuditScorecardDimensionState.BLOCKED,
        AuditScorecardDimensionState.DEGRADED,
    }
    active_results = [r for r in dimension_results if r.dimension_state in non_ok_states]
    has_blocked = any(
        r.severity is AuditScorecardSeverity.BLOCKING for r in active_results
    ) or any(f.severity is AuditScorecardSeverity.BLOCKING for f in findings)
    has_degraded = any(
        r.severity is AuditScorecardSeverity.ADVISORY for r in active_results
    ) or any(f.severity is AuditScorecardSeverity.ADVISORY for f in findings)

    if has_blocked or (strict and has_degraded):
        return (AuditScorecardState.BLOCKED, AuditScorecardReasonCode.SAFETY_BLOCKED)
    if has_degraded:
        return (AuditScorecardState.DEGRADED, AuditScorecardReasonCode.CONSISTENCY_DEGRADED)
    return (AuditScorecardState.OK, AuditScorecardReasonCode.OK)


def _aggregate_reason_codes(
    findings: list[AuditScorecardFinding],
    report_level_code: AuditScorecardReasonCode,
) -> tuple[AuditScorecardReasonCode, ...]:
    codes: list[AuditScorecardReasonCode] = [report_level_code]
    for f in findings:
        if f.reason_code not in codes:
            codes.append(f.reason_code)
    for safety in (
        AuditScorecardReasonCode.NOT_TRADING_ADVICE,
        AuditScorecardReasonCode.HUMAN_RESEARCH_ONLY,
        AuditScorecardReasonCode.NO_PRODUCTION_READINESS,
        AuditScorecardReasonCode.NO_FILE_INGESTION,
        AuditScorecardReasonCode.NO_NETWORK_CONNECTION,
        AuditScorecardReasonCode.NO_EXCHANGE_CONNECTION,
        AuditScorecardReasonCode.NO_FREQTRADE_INPUT,
        AuditScorecardReasonCode.NO_SCHEDULER,
        AuditScorecardReasonCode.NO_DAEMON,
        AuditScorecardReasonCode.NO_WEB_UI,
        AuditScorecardReasonCode.NO_DATABASE,
        AuditScorecardReasonCode.NO_ACTION_COMMANDS_EMITTED,
    ):
        if safety not in codes:
            codes.append(safety)
    return tuple(codes)
