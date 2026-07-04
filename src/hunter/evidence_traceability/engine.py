"""In-memory engine for hunter.evidence_traceability package."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from hunter.evidence_traceability.models import (
    FORBIDDEN_EVIDENCE_TRACEABILITY_TERMS,
    EvidenceArtifactRef,
    EvidenceCheck,
    EvidenceLink,
    EvidenceRequirement,
    EvidenceSectionRef,
    EvidenceTraceabilityConfig,
    EvidenceTraceabilityCoverageState,
    EvidenceTraceabilityDataQuality,
    EvidenceTraceabilityInput,
    EvidenceTraceabilityLinkType,
    EvidenceTraceabilityReasonCode,
    EvidenceTraceabilityReport,
    EvidenceTraceabilityResult,
    EvidenceTraceabilitySafetyFlags,
    EvidenceTraceabilitySeverity,
    EvidenceTraceabilityState,
    _check_forbidden_mapping,
    _has_forbidden_term,
    _has_forbidden_terms_in_text_fields,
)


def has_unsafe_evidence_traceability_content(
    text: str | None = None,
    metadata: dict[str, Any] | None = None,
    tags: list[str] | None = None,
    forbidden_terms: frozenset[str] | None = None,
) -> bool:
    """Return True if text, tags, or metadata contain forbidden traceability terms."""
    terms = forbidden_terms or FORBIDDEN_EVIDENCE_TRACEABILITY_TERMS
    if text is not None and _has_forbidden_term(text, terms):
        return True
    if tags is not None:
        for tag in tags:
            if isinstance(tag, str) and _has_forbidden_term(tag, terms):
                return True
    if metadata is not None:
        if _check_forbidden_mapping(metadata, terms):
            return True
    return False


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


def build_evidence_traceability_report(
    input: EvidenceTraceabilityInput,
    config: EvidenceTraceabilityConfig | None = None,
    strict: bool | None = None,
) -> EvidenceTraceabilityReport:
    """Build a deterministic evidence traceability matrix report from in-memory declarations."""
    if config is None:
        config = input.config
    if strict is not None:
        config = EvidenceTraceabilityConfig(
            strict=strict,
            default_json_path=config.default_json_path,
            default_csv_path=config.default_csv_path,
            default_markdown_path=config.default_markdown_path,
            staleness_threshold_seconds=config.staleness_threshold_seconds,
        )

    generated_at = _resolve_generated_at(input, config)

    if has_unsafe_evidence_traceability_content(metadata=dict(input.metadata)):
        return EvidenceTraceabilityReport.blocked(
            input=input,
            reason_code=EvidenceTraceabilityReasonCode.UNSAFE_CONTENT,
            generated_at=generated_at,
            notes=(
                "Traceability matrix blocked due to unsafe content in input metadata.",
                "Traceability output is for human audit only and is not a "
                "trading signal, recommendation, or certification of trading readiness.",
            ),
        )

    validation_result = _validate_input(input, generated_at)
    if validation_result is not None:
        return validation_result

    forbidden_offenders = _has_forbidden_terms_in_text_fields(
        requirements=input.requirements,
        checks=input.checks,
        artifacts=input.artifacts,
        sections=input.sections,
        links=input.links,
        forbidden_terms=FORBIDDEN_EVIDENCE_TRACEABILITY_TERMS,
    )
    if forbidden_offenders:
        return EvidenceTraceabilityReport.blocked(
            input=input,
            reason_code=EvidenceTraceabilityReasonCode.FORBIDDEN_TERM_PRESENT,
            generated_at=generated_at,
            notes=(
                "Traceability matrix blocked due to forbidden terms in caller-provided text fields.",
                "Traceability output is for human audit only and is not a "
                "trading signal, recommendation, or certification of trading readiness.",
            ),
        )

    results = _run_traceability_checks(input, generated_at, config)
    results = sorted(
        results,
        key=lambda r: (r.category, r.item_id, r.reason_code.value, r.state.value),
    )

    links = sorted(input.links, key=lambda link: (link.source_id, link.target_id, link.link_type.value, link.link_id))
    data_quality = _build_data_quality(results, input)
    safety_flags = _build_safety_flags(results)
    report_state, report_level_code = _aggregate_report_state(results, config.strict)
    reason_codes = _aggregate_reason_codes(results, report_level_code)

    notes = (
        "Traceability output is for human audit only.",
        "This is not a trading signal, recommendation, or certification of trading readiness.",
    )

    return EvidenceTraceabilityReport(
        state=report_state,
        reason_codes=reason_codes,
        results=tuple(results),
        links=tuple(links),
        data_quality=data_quality,
        safety_flags=safety_flags,
        generated_at=generated_at,
        project_version=input.project_version,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Validation and resolution
# ---------------------------------------------------------------------------


def _resolve_generated_at(
    input: EvidenceTraceabilityInput, config: EvidenceTraceabilityConfig
) -> datetime:
    if input.generated_at is not None:
        return input.generated_at
    if getattr(config, "generated_at", None) is not None:
        return config.generated_at
    return datetime.now(timezone.utc)


def _validate_input(
    input: EvidenceTraceabilityInput, generated_at: datetime
) -> EvidenceTraceabilityReport | None:
    if not input.requirements:
        return EvidenceTraceabilityReport.blocked(
            input=input,
            reason_code=EvidenceTraceabilityReasonCode.MISSING_REQUIRED_DECLARATION,
            generated_at=generated_at,
            notes=("Input validation failed: requirements tuple is empty.",),
        )

    duplicate_reason = _find_duplicate_reason(input)
    if duplicate_reason is not None:
        return EvidenceTraceabilityReport.blocked(
            input=input,
            reason_code=duplicate_reason,
            generated_at=generated_at,
            notes=("Input validation failed: duplicate IDs detected.",),
        )

    return None


def _find_duplicate_reason(
    input: EvidenceTraceabilityInput,
) -> EvidenceTraceabilityReasonCode | None:
    checks = [
        (input.requirements, "requirement_id", EvidenceTraceabilityReasonCode.DUPLICATE_REQUIREMENT_ID),
        (input.checks, "check_id", EvidenceTraceabilityReasonCode.DUPLICATE_CHECK_ID),
        (input.artifacts, "artifact_id", EvidenceTraceabilityReasonCode.DUPLICATE_ARTIFACT_ID),
        (input.sections, "section_id", EvidenceTraceabilityReasonCode.DUPLICATE_SECTION_ID),
        (input.links, "link_id", EvidenceTraceabilityReasonCode.DUPLICATE_LINK_ID),
    ]
    for items, attr, reason_code in checks:
        seen: set[str] = set()
        for item in items:
            item_id = getattr(item, attr)
            if item_id in seen:
                return reason_code
            seen.add(item_id)
    return None


# ---------------------------------------------------------------------------
# Traceability checks
# ---------------------------------------------------------------------------


def _run_traceability_checks(
    input: EvidenceTraceabilityInput,
    generated_at: datetime,
    config: EvidenceTraceabilityConfig,
) -> list[EvidenceTraceabilityResult]:
    results: list[EvidenceTraceabilityResult] = []

    incoming_by_target = _build_incoming_links(input.links)
    outgoing_by_source = _build_outgoing_links(input.links)
    link_pairs = _build_link_pairs(input.links)
    all_linked_ids = set(incoming_by_target.keys()) | set(outgoing_by_source.keys())

    # Requirement coverage
    for req in input.requirements:
        results.append(_check_requirement_coverage(req, incoming_by_target))

    # Orphan checks, artifacts, sections
    for check in input.checks:
        if check.check_id not in all_linked_ids:
            results.append(
                EvidenceTraceabilityResult(
                    item_id=check.check_id,
                    category="check",
                    state=EvidenceTraceabilityState.DEGRADED,
                    reason_code=EvidenceTraceabilityReasonCode.ORPHAN_CHECK,
                    coverage_state=EvidenceTraceabilityCoverageState.NOT_APPLICABLE,
                    message="Check has no incoming or outgoing links.",
                    evidence=(),
                )
            )

    for art in input.artifacts:
        if art.artifact_id not in all_linked_ids:
            results.append(
                EvidenceTraceabilityResult(
                    item_id=art.artifact_id,
                    category="artifact",
                    state=EvidenceTraceabilityState.DEGRADED,
                    reason_code=EvidenceTraceabilityReasonCode.ORPHAN_ARTIFACT,
                    coverage_state=EvidenceTraceabilityCoverageState.NOT_APPLICABLE,
                    message="Artifact has no incoming or outgoing links.",
                    evidence=(art.reference,),
                )
            )

    for sec in input.sections:
        if sec.section_id not in all_linked_ids:
            results.append(
                EvidenceTraceabilityResult(
                    item_id=sec.section_id,
                    category="section",
                    state=EvidenceTraceabilityState.DEGRADED,
                    reason_code=EvidenceTraceabilityReasonCode.ORPHAN_SECTION,
                    coverage_state=EvidenceTraceabilityCoverageState.NOT_APPLICABLE,
                    message="Section has no incoming or outgoing links.",
                    evidence=(sec.reference,),
                )
            )

    # Conflicting links
    for (source_id, target_id), link_types in link_pairs.items():
        if (
            EvidenceTraceabilityLinkType.CONTRADICTS in link_types
            and (
                EvidenceTraceabilityLinkType.COVERED_BY in link_types
                or EvidenceTraceabilityLinkType.SUPPORTS in link_types
            )
        ):
            results.append(
                EvidenceTraceabilityResult(
                    item_id=f"{source_id}->{target_id}",
                    category="link",
                    state=EvidenceTraceabilityState.BLOCKED,
                    reason_code=EvidenceTraceabilityReasonCode.CONFLICTING_LINK,
                    coverage_state=EvidenceTraceabilityCoverageState.NOT_APPLICABLE,
                    message=f"Conflicting link types between {source_id} and {target_id}: {sorted(lt.value for lt in link_types)}",
                    evidence=tuple(sorted(lt.value for lt in link_types)),
                )
            )

    # Stale evidence
    if config.staleness_threshold_seconds is not None:
        threshold = timedelta(seconds=config.staleness_threshold_seconds)
        for art in input.artifacts:
            if art.generated_at is not None and art.generated_at < generated_at - threshold:
                results.append(
                    EvidenceTraceabilityResult(
                        item_id=art.artifact_id,
                        category="artifact",
                        state=EvidenceTraceabilityState.DEGRADED,
                        reason_code=EvidenceTraceabilityReasonCode.STALE_EVIDENCE,
                        coverage_state=EvidenceTraceabilityCoverageState.NOT_APPLICABLE,
                        message=f"Artifact generated_at {art.generated_at} is older than threshold.",
                        evidence=(str(art.generated_at),),
                    )
                )
        for sec in input.sections:
            if sec.generated_at is not None and sec.generated_at < generated_at - threshold:
                results.append(
                    EvidenceTraceabilityResult(
                        item_id=sec.section_id,
                        category="section",
                        state=EvidenceTraceabilityState.DEGRADED,
                        reason_code=EvidenceTraceabilityReasonCode.STALE_EVIDENCE,
                        coverage_state=EvidenceTraceabilityCoverageState.NOT_APPLICABLE,
                        message=f"Section generated_at {sec.generated_at} is older than threshold.",
                        evidence=(str(sec.generated_at),),
                    )
                )

    # Missing manual review
    manually_reviewed_targets = {
        link.target_id
        for link in input.links
        if link.link_type is EvidenceTraceabilityLinkType.MANUALLY_REVIEWED
    }
    for art in input.artifacts:
        if art.requires_manual_review and art.artifact_id not in manually_reviewed_targets:
            results.append(
                EvidenceTraceabilityResult(
                    item_id=art.artifact_id,
                    category="artifact",
                    state=EvidenceTraceabilityState.DEGRADED,
                    reason_code=EvidenceTraceabilityReasonCode.MISSING_MANUAL_REVIEW,
                    coverage_state=EvidenceTraceabilityCoverageState.NOT_APPLICABLE,
                    message="Artifact requires manual review but no MANUALLY_REVIEWED link present.",
                    evidence=(),
                )
            )
    for sec in input.sections:
        if sec.requires_manual_review and sec.section_id not in manually_reviewed_targets:
            results.append(
                EvidenceTraceabilityResult(
                    item_id=sec.section_id,
                    category="section",
                    state=EvidenceTraceabilityState.DEGRADED,
                    reason_code=EvidenceTraceabilityReasonCode.MISSING_MANUAL_REVIEW,
                    coverage_state=EvidenceTraceabilityCoverageState.NOT_APPLICABLE,
                    message="Section requires manual review but no MANUALLY_REVIEWED link present.",
                    evidence=(),
                )
            )

    return results


def _build_incoming_links(
    links: tuple[EvidenceLink, ...]
) -> dict[str, list[EvidenceLink]]:
    incoming: dict[str, list[EvidenceLink]] = defaultdict(list)
    for link in links:
        incoming[link.target_id].append(link)
    return incoming


def _build_outgoing_links(
    links: tuple[EvidenceLink, ...]
) -> dict[str, list[EvidenceLink]]:
    outgoing: dict[str, list[EvidenceLink]] = defaultdict(list)
    for link in links:
        outgoing[link.source_id].append(link)
    return outgoing


def _build_link_pairs(
    links: tuple[EvidenceLink, ...]
) -> dict[tuple[str, str], set[EvidenceTraceabilityLinkType]]:
    pairs: dict[tuple[str, str], set[EvidenceTraceabilityLinkType]] = defaultdict(set)
    for link in links:
        pairs[(link.source_id, link.target_id)].add(link.link_type)
    return pairs


def _check_requirement_coverage(
    req: EvidenceRequirement,
    incoming_by_target: dict[str, list[EvidenceLink]],
) -> EvidenceTraceabilityResult:
    incoming = incoming_by_target.get(req.requirement_id, [])
    incoming_types = {link.link_type for link in incoming}

    if not incoming:
        state = (
            EvidenceTraceabilityState.BLOCKED
            if req.severity is EvidenceTraceabilitySeverity.BLOCKING
            else EvidenceTraceabilityState.DEGRADED
        )
        return EvidenceTraceabilityResult(
            item_id=req.requirement_id,
            category="requirement",
            state=state,
            reason_code=EvidenceTraceabilityReasonCode.MISSING_COVERAGE,
            coverage_state=EvidenceTraceabilityCoverageState.MISSING,
            message=f"Requirement {req.requirement_id} has no incoming coverage links.",
            evidence=(),
        )

    required_types = {EvidenceTraceabilityLinkType(t) for t in req.required_link_types}
    if required_types:
        missing_types = required_types - incoming_types
        if missing_types:
            partial = bool(incoming_types & required_types)
            if partial:
                return EvidenceTraceabilityResult(
                    item_id=req.requirement_id,
                    category="requirement",
                    state=EvidenceTraceabilityState.DEGRADED,
                    reason_code=EvidenceTraceabilityReasonCode.PARTIAL_COVERAGE,
                    coverage_state=EvidenceTraceabilityCoverageState.PARTIAL,
                    message=f"Requirement {req.requirement_id} is missing required link types: {sorted(t.value for t in missing_types)}",
                    evidence=tuple(sorted(t.value for t in missing_types)),
                )
            else:
                state = (
                    EvidenceTraceabilityState.BLOCKED
                    if req.severity is EvidenceTraceabilitySeverity.BLOCKING
                    else EvidenceTraceabilityState.DEGRADED
                )
                return EvidenceTraceabilityResult(
                    item_id=req.requirement_id,
                    category="requirement",
                    state=state,
                    reason_code=EvidenceTraceabilityReasonCode.MISSING_COVERAGE,
                    coverage_state=EvidenceTraceabilityCoverageState.MISSING,
                    message=f"Requirement {req.requirement_id} has no required link types: {sorted(t.value for t in required_types)}",
                    evidence=tuple(sorted(t.value for t in required_types)),
                )

    return EvidenceTraceabilityResult(
        item_id=req.requirement_id,
        category="requirement",
        state=EvidenceTraceabilityState.OK,
        reason_code=EvidenceTraceabilityReasonCode.OK,
        coverage_state=EvidenceTraceabilityCoverageState.COVERED,
        message=f"Requirement {req.requirement_id} is covered.",
        evidence=(),
    )


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------


def _build_data_quality(
    results: list[EvidenceTraceabilityResult], input: EvidenceTraceabilityInput
) -> EvidenceTraceabilityDataQuality:
    total = len(results)
    ok_count = sum(1 for r in results if r.state is EvidenceTraceabilityState.OK)
    degraded_count = sum(1 for r in results if r.state is EvidenceTraceabilityState.DEGRADED)
    blocked_count = sum(1 for r in results if r.state is EvidenceTraceabilityState.BLOCKED)
    not_applicable_count = sum(
        1 for r in results if r.state is EvidenceTraceabilityState.NOT_APPLICABLE
    )
    return EvidenceTraceabilityDataQuality(
        total_items=total,
        ok_count=ok_count,
        degraded_count=degraded_count,
        blocked_count=blocked_count,
        not_applicable_count=not_applicable_count,
        requirement_count=len(input.requirements),
        check_count=len(input.checks),
        artifact_count=len(input.artifacts),
        section_count=len(input.sections),
        link_count=len(input.links),
        notes=(
            "Data quality summary counts traceability results by state.",
            "All values are derived from caller-provided in-memory declarations.",
        ),
    )


def _build_safety_flags(
    results: list[EvidenceTraceabilityResult],
) -> EvidenceTraceabilitySafetyFlags:
    has_blocked = any(r.state is EvidenceTraceabilityState.BLOCKED for r in results)
    has_degraded = any(r.state is EvidenceTraceabilityState.DEGRADED for r in results)
    has_conflicting_links = any(
        r.reason_code is EvidenceTraceabilityReasonCode.CONFLICTING_LINK for r in results
    )
    has_missing_coverage = any(
        r.reason_code is EvidenceTraceabilityReasonCode.MISSING_COVERAGE for r in results
    )
    has_stale_evidence = any(
        r.reason_code is EvidenceTraceabilityReasonCode.STALE_EVIDENCE for r in results
    )
    has_missing_manual_review = any(
        r.reason_code is EvidenceTraceabilityReasonCode.MISSING_MANUAL_REVIEW for r in results
    )
    has_orphan_items = any(
        r.reason_code
        in {
            EvidenceTraceabilityReasonCode.ORPHAN_CHECK,
            EvidenceTraceabilityReasonCode.ORPHAN_ARTIFACT,
            EvidenceTraceabilityReasonCode.ORPHAN_SECTION,
        }
        for r in results
    )
    has_forbidden_terms = any(
        r.reason_code
        in {
            EvidenceTraceabilityReasonCode.FORBIDDEN_TERM_PRESENT,
            EvidenceTraceabilityReasonCode.UNSAFE_CONTENT,
        }
        for r in results
    )
    return EvidenceTraceabilitySafetyFlags(
        has_blocked=has_blocked,
        has_degraded=has_degraded,
        has_conflicting_links=has_conflicting_links,
        has_missing_coverage=has_missing_coverage,
        has_stale_evidence=has_stale_evidence,
        has_missing_manual_review=has_missing_manual_review,
        has_orphan_items=has_orphan_items,
        has_forbidden_terms=has_forbidden_terms,
    )


def _aggregate_report_state(
    results: list[EvidenceTraceabilityResult], strict: bool
) -> tuple[EvidenceTraceabilityState, EvidenceTraceabilityReasonCode]:
    has_blocked = any(r.state is EvidenceTraceabilityState.BLOCKED for r in results)
    has_degraded = any(r.state is EvidenceTraceabilityState.DEGRADED for r in results)

    if has_blocked or (strict and has_degraded):
        return (EvidenceTraceabilityState.BLOCKED, EvidenceTraceabilityReasonCode.SAFETY_BLOCKED)
    if has_degraded:
        return (EvidenceTraceabilityState.DEGRADED, EvidenceTraceabilityReasonCode.CONSISTENCY_DEGRADED)
    return (EvidenceTraceabilityState.OK, EvidenceTraceabilityReasonCode.OK)


def _aggregate_reason_codes(
    results: list[EvidenceTraceabilityResult],
    report_level_code: EvidenceTraceabilityReasonCode,
) -> tuple[EvidenceTraceabilityReasonCode, ...]:
    codes: list[EvidenceTraceabilityReasonCode] = [report_level_code]
    for r in results:
        if r.reason_code not in codes:
            codes.append(r.reason_code)
    for safety in (
        EvidenceTraceabilityReasonCode.NOT_TRADING_ADVICE,
    ):
        if safety not in codes:
            codes.append(safety)
    return tuple(codes)
