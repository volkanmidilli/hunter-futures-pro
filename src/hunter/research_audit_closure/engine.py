"""In-memory engine for hunter.research_audit_closure package.

MVP-22 — Local Research Audit Closure Report.

The engine consumes already-loaded artifact summaries and explicit reference
strings. It never reads, parses, traverses, opens, follows, validates, or
executes referenced artifact files or metadata strings.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from hunter.research_audit_closure.models import (
    AUDIT_CLOSURE_BLOCKING_REASON_CODES,
    AUDIT_CLOSURE_INCOMPLETE_REASON_CODES,
    AUDIT_CLOSURE_REASON_CODES,
    AUDIT_CLOSURE_SECTION_KINDS,
    DEFAULT_BLOCKED,
    EMPTY_COMPLETED_ARTIFACTS,
    INCOMPLETE_ARTIFACT_CHAIN,
    INVALID_ARTIFACT_SUMMARY,
    INVALID_CLOSURE_CONFIG,
    MISSING_ARTIFACTS,
    MISSING_REQUIRED_SECTION,
    OPEN_FINDINGS_REMAIN,
    BACKLOG_NOTES_REMAIN,
    SECTION_BUILD_ERROR,
    SUMMARY_BUILD_ERROR,
    UNSAFE_CLOSURE_CONFIG,
    UNSAFE_CLOSURE_CONTENT,
    UNRESOLVED_BLOCKERS,
    UNKNOWN_CLOSURE_STATE,
    AuditClosureConfig,
    AuditClosureDataQuality,
    AuditClosureFinding,
    AuditClosureFindingSeverity,
    AuditClosureSafetyFlags,
    AuditClosureSection,
    AuditClosureSectionKind,
    AuditClosureState,
    AuditClosureSummary,
    ResearchAuditClosureReport,
    _check_forbidden_mapping,
    _ensure_tuple_of_str,
    _extract_mvp_number,
    _has_forbidden_closure_term,
)


def build_audit_closure_safety_flags() -> AuditClosureSafetyFlags:
    """Build default fail-closed safety flags."""
    return AuditClosureSafetyFlags()


def has_unsafe_audit_closure_content(value: str | Mapping[str, Any] | Iterable[Any] | None) -> bool:
    """Case-insensitive recursive check for forbidden terms in closure text."""
    if value is None:
        return False
    if isinstance(value, str):
        return _has_forbidden_closure_term(value)
    if isinstance(value, Mapping):
        return _check_forbidden_mapping(value)
    if isinstance(value, (tuple, list)):
        for item in value:
            if has_unsafe_audit_closure_content(item):
                return True
        return False
    return False


def build_audit_closure_finding(
    finding_id: str,
    title: str,
    severity: str,
    *,
    description: str = "",
    related_mvp: str = "",
    spec_reference: str = "",
    related_references: tuple[str, ...] | list[str] = (),
    metadata: Mapping[str, Any] | None = None,
) -> AuditClosureFinding:
    """Build a single AuditClosureFinding."""
    return AuditClosureFinding(
        finding_id=finding_id,
        title=title,
        severity=severity,
        description=description,
        related_mvp=related_mvp,
        spec_reference=spec_reference,
        related_references=related_references,
        metadata=metadata,
    )


def _order_findings(findings: Sequence[AuditClosureFinding]) -> tuple[AuditClosureFinding, ...]:
    """Order findings by (severity_priority, mvp_number, insertion_order)."""
    from hunter.research_audit_closure.models import (
        _AUDIT_CLOSURE_FINDING_SEVERITY_PRIORITY,
    )
    enumerated = list(enumerate(findings))
    enumerated.sort(key=lambda item: (
        _AUDIT_CLOSURE_FINDING_SEVERITY_PRIORITY.get(item[1].severity, 999),
        _extract_mvp_number(item[1].related_mvp),
        item[0],
    ))
    return tuple(item[1] for item in enumerated)


def build_audit_closure_section(
    section_kind: AuditClosureSectionKind,
    title: str,
    *,
    section_notes: str = "",
    findings: Sequence[AuditClosureFinding] = (),
    completed_artifacts: Sequence[Mapping[str, Any]] = (),
    backlog_notes: Sequence[str] = (),
    references: Sequence[str] = (),
    metadata: Mapping[str, Any] | None = None,
) -> AuditClosureSection:
    """Build a single AuditClosureSection with deterministically ordered findings."""
    ordered_findings = _order_findings(findings)
    return AuditClosureSection(
        section_kind=section_kind,
        title=title,
        section_notes=section_notes,
        findings=ordered_findings,
        completed_artifacts=tuple(completed_artifacts),
        backlog_notes=backlog_notes,
        references=references,
        metadata=metadata,
    )


def build_audit_closure_summary(
    sections: Sequence[AuditClosureSection],
    *,
    closure_state: AuditClosureState | None = None,
    reason_codes: Sequence[str] = (),
    closure_narrative: str = "",
) -> AuditClosureSummary:
    """Aggregate counts and produce closure summary."""
    total_sections = len(sections)
    total_findings = 0
    critical_count = 0
    high_count = 0
    medium_count = 0
    low_count = 0
    info_count = 0
    completed_artifact_count = 0
    open_finding_count = 0
    backlog_note_count = 0
    reason_code_counts: dict[str, int] = {}

    for section in sections:
        section_finding_count = len(section.findings)
        total_findings += section_finding_count

        for finding in section.findings:
            if finding.severity == AuditClosureFindingSeverity.CRITICAL.name:
                critical_count += 1
            elif finding.severity == AuditClosureFindingSeverity.HIGH.name:
                high_count += 1
            elif finding.severity == AuditClosureFindingSeverity.MEDIUM.name:
                medium_count += 1
            elif finding.severity == AuditClosureFindingSeverity.LOW.name:
                low_count += 1
            elif finding.severity == AuditClosureFindingSeverity.INFO.name:
                info_count += 1

        if section.section_kind is AuditClosureSectionKind.COMPLETED_ARTIFACTS:
            completed_artifact_count += len(section.completed_artifacts)
        if section.section_kind is AuditClosureSectionKind.OPEN_FINDINGS:
            open_finding_count += section_finding_count
        if section.section_kind is AuditClosureSectionKind.BACKLOG_NOTES:
            backlog_note_count += len(section.backlog_notes)

    for code in reason_codes:
        reason_code_counts[code] = reason_code_counts.get(code, 0) + 1

    if closure_state is None:
        closure_state = AuditClosureState.UNKNOWN

    return AuditClosureSummary(
        total_sections=total_sections,
        total_findings=total_findings,
        critical_count=critical_count,
        high_count=high_count,
        medium_count=medium_count,
        low_count=low_count,
        info_count=info_count,
        completed_artifact_count=completed_artifact_count,
        open_finding_count=open_finding_count,
        backlog_note_count=backlog_note_count,
        closure_state=closure_state.value.upper(),
        reason_code_counts=reason_code_counts,
        closure_narrative=closure_narrative,
    )


def build_audit_closure_data_quality(
    sections: Sequence[AuditClosureSection],
    *,
    expected_artifact_count: int = 12,
    reason: str = "",
) -> AuditClosureDataQuality:
    """Assess closure report completeness and quality."""
    present_section_kinds: set[AuditClosureSectionKind] = set()
    artifacts_present: set[str] = set()
    total_findings = 0
    unresolved_blocker_count = 0
    unresolved_warning_count = 0
    backlog_note_count = 0

    for section in sections:
        present_section_kinds.add(section.section_kind)
        if section.section_kind is AuditClosureSectionKind.COMPLETED_ARTIFACTS:
            for artifact in section.completed_artifacts:
                if isinstance(artifact, Mapping):
                    kind = artifact.get("artifact_kind")
                    if isinstance(kind, str) and kind:
                        artifacts_present.add(kind)
        if section.section_kind is AuditClosureSectionKind.OPEN_FINDINGS:
            total_findings += len(section.findings)
            for finding in section.findings:
                if finding.severity in (
                    AuditClosureFindingSeverity.CRITICAL.name,
                    AuditClosureFindingSeverity.HIGH.name,
                ):
                    unresolved_blocker_count += 1
                elif finding.severity in (
                    AuditClosureFindingSeverity.MEDIUM.name,
                    AuditClosureFindingSeverity.LOW.name,
                ):
                    unresolved_warning_count += 1
        if section.section_kind is AuditClosureSectionKind.BACKLOG_NOTES:
            backlog_note_count += len(section.backlog_notes)

    sections_present = len(present_section_kinds)
    sections_missing = len(AUDIT_CLOSURE_SECTION_KINDS) - sections_present
    artifacts_missing = expected_artifact_count - len(artifacts_present)
    if artifacts_missing < 0:
        artifacts_missing = 0

    completeness_pct = 0.0
    if expected_artifact_count > 0:
        completeness_pct = (len(artifacts_present) / expected_artifact_count) * 100.0

    coverage_pct = 0.0
    if len(AUDIT_CLOSURE_SECTION_KINDS) > 0:
        coverage_pct = (sections_present / len(AUDIT_CLOSURE_SECTION_KINDS)) * 100.0

    return AuditClosureDataQuality(
        total_artifacts_expected=expected_artifact_count,
        artifacts_present=len(artifacts_present),
        artifacts_missing=artifacts_missing,
        sections_present=sections_present,
        sections_missing=sections_missing,
        total_findings=total_findings,
        unresolved_blocker_count=unresolved_blocker_count,
        unresolved_warning_count=unresolved_warning_count,
        backlog_note_count=backlog_note_count,
        completeness_pct=completeness_pct,
        coverage_pct=coverage_pct,
        reason=reason,
    )


def _validate_artifact_summary(summary: Mapping[str, Any]) -> tuple[bool, str]:
    """Validate a caller-provided artifact summary.

    Returns (is_valid, reason_code_or_empty).
    """
    required_fields = ("artifact_id", "artifact_kind", "state", "source_version", "generated_at")
    for field in required_fields:
        value = summary.get(field)
        if field == "generated_at":
            if not isinstance(value, datetime):
                return False, INVALID_ARTIFACT_SUMMARY
            if value.tzinfo is None:
                return False, INVALID_ARTIFACT_SUMMARY
        elif not isinstance(value, str) or not value:
            return False, INVALID_ARTIFACT_SUMMARY
    return True, ""


def _build_cycle_scope_section(
    artifact_summaries: Sequence[Mapping[str, Any]],
) -> AuditClosureSection:
    """Build CYCLE_SCOPE section."""
    mvp_lines: list[str] = []
    for summary in artifact_summaries:
        kind = summary.get("artifact_kind", "")
        spec = summary.get("spec_reference", "")
        mvp_lines.append(f"- {kind} ({spec})")
    notes = "Closure cycle covers MVP-10 through MVP-21 research/audit artifacts."
    if mvp_lines:
        notes += "\n" + "\n".join(mvp_lines)
    return build_audit_closure_section(
        section_kind=AuditClosureSectionKind.CYCLE_SCOPE,
        title="Cycle Scope",
        section_notes=notes,
    )


def _build_completed_artifacts_section(
    artifact_summaries: Sequence[Mapping[str, Any]],
) -> AuditClosureSection:
    """Build COMPLETED_ARTIFACTS section."""
    return build_audit_closure_section(
        section_kind=AuditClosureSectionKind.COMPLETED_ARTIFACTS,
        title="Completed Artifacts",
        completed_artifacts=tuple(dict(s) for s in artifact_summaries),
    )


def _build_open_findings_section(
    findings: Sequence[AuditClosureFinding],
) -> AuditClosureSection:
    """Build OPEN_FINDINGS section."""
    return build_audit_closure_section(
        section_kind=AuditClosureSectionKind.OPEN_FINDINGS,
        title="Open Findings",
        findings=findings,
    )


def _build_backlog_notes_section(
    backlog_notes: Sequence[str],
) -> AuditClosureSection:
    """Build BACKLOG_NOTES section."""
    return build_audit_closure_section(
        section_kind=AuditClosureSectionKind.BACKLOG_NOTES,
        title="Backlog Notes",
        backlog_notes=backlog_notes,
    )


def _build_safety_boundaries_section() -> AuditClosureSection:
    """Build SAFETY_BOUNDARIES section."""
    notes = (
        "This closure report is a human-audit / contractor-handoff artifact only. "
        "It does not grant or imply any release, rollout, strategy, or transaction capacity. "
        "It is not for use by trading actors, exchange connectors, or any automated path. "
        "File references and metadata strings are local strings only; "
        "they are not traversed, opened, followed, checked, or carried out. "
        "The closure report must not emit action commands."
    )
    return build_audit_closure_section(
        section_kind=AuditClosureSectionKind.SAFETY_BOUNDARIES,
        title="Safety Boundaries",
        section_notes=notes,
    )


def _build_human_archival_guide_section() -> AuditClosureSection:
    """Build HUMAN_ARCHIVAL_GUIDE section."""
    notes = (
        "This section is advisory-only and non-gating. Store the JSON and Markdown closure "
        "report outputs alongside the MVP-10 through MVP-21 artifact outputs for human archival "
        "review. Review open findings and backlog notes before considering the cycle complete."
    )
    return build_audit_closure_section(
        section_kind=AuditClosureSectionKind.HUMAN_ARCHIVAL_GUIDE,
        title="Human Archival Guide",
        section_notes=notes,
    )


def _build_appendix_references_section(
    references: Sequence[str],
) -> AuditClosureSection:
    """Build APPENDIX_REFERENCES section."""
    return build_audit_closure_section(
        section_kind=AuditClosureSectionKind.APPENDIX_REFERENCES,
        title="Appendix References",
        references=references,
    )


def _build_overview_section(
    closure_id: str,
    generated_at: datetime,
    closure_state: AuditClosureState,
) -> AuditClosureSection:
    """Build OVERVIEW section."""
    notes = (
        f"Closure ID: {closure_id}\n"
        f"Generated at: {generated_at.isoformat()}\n"
        f"Closure state: {closure_state.value}\n"
        "This report summarizes whether the research/audit cycle is document-complete "
        "for human archival review."
    )
    return build_audit_closure_section(
        section_kind=AuditClosureSectionKind.OVERVIEW,
        title="Overview",
        section_notes=notes,
    )


def build_research_audit_closure_report(
    artifact_summaries: Sequence[Mapping[str, Any]],
    *,
    findings: Sequence[AuditClosureFinding] = (),
    backlog_notes: Sequence[str] = (),
    references: Sequence[str] = (),
    closure_id: str = "",
    generated_at: datetime | None = None,
    config: AuditClosureConfig | None = None,
    safety_flags: AuditClosureSafetyFlags | None = None,
) -> ResearchAuditClosureReport:
    """Build full ResearchAuditClosureReport from artifact summaries.

    The engine never reads, parses, traverses, opens, follows, validates, or
    executes referenced artifact files. Callers must provide already-loaded
    metadata or explicit reference strings.
    """
    if config is None:
        config = AuditClosureConfig()
    if safety_flags is None:
        safety_flags = build_audit_closure_safety_flags()
    if generated_at is None:
        generated_at = datetime.now(timezone.utc)
    if not closure_id:
        closure_id = str(uuid4())

    # Validate config.
    try:
        config = AuditClosureConfig(
            version=config.version,
            generated_at=config.generated_at,
            output_format=config.output_format,
            dry_run=config.dry_run,
            live_trading_enabled=config.live_trading_enabled,
            real_orders_enabled=config.real_orders_enabled,
            leverage_enabled=config.leverage_enabled,
            shorting_enabled=config.shorting_enabled,
            block_on_unknown=config.block_on_unknown,
            block_on_incomplete=config.block_on_incomplete,
            expected_artifact_count=config.expected_artifact_count,
            required_sections=config.required_sections,
            include_closure_narrative=config.include_closure_narrative,
        )
    except ValueError as exc:
        return ResearchAuditClosureReport.blocked(
            closure_id=closure_id,
            generated_at=generated_at,
            reason_code=INVALID_CLOSURE_CONFIG,
            safety_flags=safety_flags,
        )

    # Unsafe config content.
    if has_unsafe_audit_closure_content(
        {
            "version": config.version,
            "output_format": config.output_format,
        }
    ):
        return ResearchAuditClosureReport.blocked(
            closure_id=closure_id,
            generated_at=generated_at,
            reason_code=UNSAFE_CLOSURE_CONFIG,
            safety_flags=safety_flags,
        )

    # Fail-closed rule 1: missing artifacts.
    if not artifact_summaries:
        return ResearchAuditClosureReport.blocked(
            closure_id=closure_id,
            generated_at=generated_at,
            reason_code=MISSING_ARTIFACTS,
            safety_flags=safety_flags,
        )

    # Validate artifact summaries.
    validation_errors: list[str] = []
    valid_summaries: list[Mapping[str, Any]] = []
    for idx, summary in enumerate(artifact_summaries):
        is_valid, reason = _validate_artifact_summary(summary)
        if not is_valid:
            validation_errors.append(f"summary {idx}: {reason}")
        else:
            valid_summaries.append(summary)

    if validation_errors:
        return ResearchAuditClosureReport.blocked(
            closure_id=closure_id,
            generated_at=generated_at,
            reason_code=INVALID_ARTIFACT_SUMMARY,
            safety_flags=safety_flags,
        )

    # Unsafe artifact summary content.
    for summary in valid_summaries:
        if has_unsafe_audit_closure_content(summary):
            return ResearchAuditClosureReport.blocked(
                closure_id=closure_id,
                generated_at=generated_at,
                reason_code=UNSAFE_CLOSURE_CONTENT,
                safety_flags=safety_flags,
            )

    # Unsafe findings/backlog/references.
    for finding in findings:
        if has_unsafe_audit_closure_content(
            {
                "title": finding.title,
                "description": finding.description,
                "spec_reference": finding.spec_reference,
                "metadata": dict(finding.metadata),
            }
        ):
            return ResearchAuditClosureReport.blocked(
                closure_id=closure_id,
                generated_at=generated_at,
                reason_code=UNSAFE_CLOSURE_CONTENT,
                safety_flags=safety_flags,
            )
    for note in backlog_notes:
        if has_unsafe_audit_closure_content(note):
            return ResearchAuditClosureReport.blocked(
                closure_id=closure_id,
                generated_at=generated_at,
                reason_code=UNSAFE_CLOSURE_CONTENT,
                safety_flags=safety_flags,
            )
    for ref in references:
        if has_unsafe_audit_closure_content(ref):
            return ResearchAuditClosureReport.blocked(
                closure_id=closure_id,
                generated_at=generated_at,
                reason_code=UNSAFE_CLOSURE_CONTENT,
                safety_flags=safety_flags,
            )

    # Build sections in deterministic order.
    sections: list[AuditClosureSection] = [
        _build_overview_section(closure_id, generated_at, AuditClosureState.READY),
        _build_cycle_scope_section(valid_summaries),
        _build_completed_artifacts_section(valid_summaries),
        _build_open_findings_section(findings),
        _build_backlog_notes_section(backlog_notes),
        _build_safety_boundaries_section(),
        _build_human_archival_guide_section(),
        _build_appendix_references_section(references),
    ]

    # Determine reason codes.
    reason_codes: list[str] = []

    # Rule 5: missing required sections.
    present_section_kinds = {s.section_kind for s in sections}
    missing_required = [
        kind for kind in config.required_sections if kind not in present_section_kinds
    ]
    if missing_required:
        reason_codes.append(MISSING_REQUIRED_SECTION)

    # Rule 6: empty completed artifacts.
    completed_section = next(
        (s for s in sections if s.section_kind is AuditClosureSectionKind.COMPLETED_ARTIFACTS),
        None,
    )
    if completed_section is not None and not completed_section.completed_artifacts:
        reason_codes.append(EMPTY_COMPLETED_ARTIFACTS)

    # Rule 7: unresolved blockers.
    has_blocker = any(
        finding.severity in (
            AuditClosureFindingSeverity.CRITICAL.name,
            AuditClosureFindingSeverity.HIGH.name,
        )
        for finding in findings
    )
    if has_blocker:
        reason_codes.append(UNRESOLVED_BLOCKERS)

    # Rule 8: unsafe closure content already handled above.

    # Rule 9: incomplete artifact chain.
    data_quality = build_audit_closure_data_quality(
        sections,
        expected_artifact_count=config.expected_artifact_count,
    )
    if data_quality.artifacts_missing > 0:
        reason_codes.append(INCOMPLETE_ARTIFACT_CHAIN)

    # Advisory reason codes.
    if findings:
        reason_codes.append(OPEN_FINDINGS_REMAIN)
    if backlog_notes:
        reason_codes.append(BACKLOG_NOTES_REMAIN)

    # Resolve closure state.
    closure_state = AuditClosureState.READY
    if any(code in AUDIT_CLOSURE_BLOCKING_REASON_CODES for code in reason_codes):
        closure_state = AuditClosureState.BLOCK
    elif config.block_on_unknown and any(code == UNKNOWN_CLOSURE_STATE for code in reason_codes):
        closure_state = AuditClosureState.BLOCK
    elif config.block_on_incomplete and any(
        code in AUDIT_CLOSURE_INCOMPLETE_REASON_CODES for code in reason_codes
    ):
        closure_state = AuditClosureState.INCOMPLETE
    elif any(code in AUDIT_CLOSURE_INCOMPLETE_REASON_CODES for code in reason_codes):
        closure_state = AuditClosureState.READY
    elif any(code == UNKNOWN_CLOSURE_STATE for code in reason_codes):
        closure_state = AuditClosureState.UNKNOWN

    summary = build_audit_closure_summary(
        sections,
        closure_state=closure_state,
        reason_codes=reason_codes,
        closure_narrative="Research audit closure report generated for human archival review.",
    )

    # If state is BLOCK or UNKNOWN, summary closure_state string must match.
    if closure_state in (AuditClosureState.BLOCK, AuditClosureState.UNKNOWN):
        summary = AuditClosureSummary(
            total_sections=summary.total_sections,
            total_findings=summary.total_findings,
            critical_count=summary.critical_count,
            high_count=summary.high_count,
            medium_count=summary.medium_count,
            low_count=summary.low_count,
            info_count=summary.info_count,
            completed_artifact_count=summary.completed_artifact_count,
            open_finding_count=summary.open_finding_count,
            backlog_note_count=summary.backlog_note_count,
            closure_state=closure_state.value.upper(),
            reason_code_counts=dict(summary.reason_code_counts),
            closure_narrative=summary.closure_narrative,
        )

    try:
        return ResearchAuditClosureReport(
            closure_id=closure_id,
            generated_at=generated_at,
            closure_state=closure_state,
            sections=tuple(sections),
            summary=summary,
            data_quality=data_quality,
            safety_flags=safety_flags,
            config=config,
            reason_codes=tuple(reason_codes),
            closure_narrative="Research audit closure report generated for human archival review.",
        )
    except ValueError as exc:
        return ResearchAuditClosureReport.blocked(
            closure_id=closure_id,
            generated_at=generated_at,
            reason_code=SECTION_BUILD_ERROR,
            safety_flags=safety_flags,
        )
