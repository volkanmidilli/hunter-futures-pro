"""In-memory engine for hunter.research_audit_snapshot package.

MVP-23 — Local Research Audit Snapshot.

The engine consumes already-loaded artifact summaries and explicit reference
strings. It never reads, parses, traverses, opens, follows, validates, or
executes referenced artifact files or metadata strings.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from hunter.research_audit_snapshot.models import (
    ARTIFACT_FILES_NOT_READ,
    AUDIT_SNAPSHOT_ADVISORY_REASON_CODES,
    AUDIT_SNAPSHOT_BLOCKING_REASON_CODES,
    AUDIT_SNAPSHOT_INCOMPLETE_REASON_CODES,
    AUDIT_SNAPSHOT_REASON_CODES,
    AUDIT_SNAPSHOT_STALE_REASON_CODES,
    BLOCKED_ARTIFACT_ITEM,
    CANONICAL_AUDIT_SNAPSHOT_SECTION_ORDER,
    FILE_REFS_NOT_TRAVERSED,
    HUMAN_AUDIT_GUIDE_NON_GATING,
    INCOMPLETE_ARTIFACT_ITEM,
    INVALID_SNAPSHOT_CONFIG,
    MISSING_ARTIFACT_SUMMARIES,
    MISSING_REQUIRED_SECTION,
    NO_ACTION_COMMANDS_EMITTED,
    OPEN_ITEMS_PRESENT,
    SNAPSHOT_VERSION,
    STALE_ARTIFACT_DETECTED,
    UNSAFE_SNAPSHOT_CONTENT,
    UNKNOWN_SNAPSHOT_STATE,
    AuditSnapshotConfig,
    AuditSnapshotDataQuality,
    AuditSnapshotItem,
    AuditSnapshotItemSeverity,
    AuditSnapshotKind,
    AuditSnapshotSafetyFlags,
    AuditSnapshotSection,
    AuditSnapshotSectionKind,
    AuditSnapshotState,
    AuditSnapshotSummary,
    ResearchAuditSnapshot,
    _check_forbidden_mapping,
    _extract_mvp_number,
    _has_forbidden_snapshot_term,
    _order_items,
)


def build_audit_snapshot_safety_flags() -> AuditSnapshotSafetyFlags:
    """Build default fail-closed safety flags."""
    return AuditSnapshotSafetyFlags()


def has_unsafe_audit_snapshot_content(
    value: str | Iterable[Any] | Mapping[str, Any] | None,
) -> bool:
    """Case-insensitive recursive check for forbidden terms in snapshot text."""
    if value is None:
        return False
    if isinstance(value, str):
        return _has_forbidden_snapshot_term(value)
    if isinstance(value, Mapping):
        return _check_forbidden_mapping(value)
    if isinstance(value, (tuple, list)):
        for item in value:
            if has_unsafe_audit_snapshot_content(item):
                return True
        return False
    return False


def build_audit_snapshot_item(
    item_id: str,
    title: str,
    *,
    artifact_kind: str = "",
    state: str = "UNKNOWN",
    severity: str = "INFO",
    related_mvp: str = "",
    spec_reference: str = "",
    local_reference: str = "",
    generated_at: datetime | None = None,
    reason_codes: Sequence[str] = (),
    tags: Sequence[str] = (),
    related_references: Sequence[str] = (),
    metadata: Mapping[str, Any] | None = None,
) -> AuditSnapshotItem:
    """Build a single AuditSnapshotItem.

    State and severity are normalized to uppercase enum names.
    """
    normalized_state = state.upper()
    normalized_severity = severity.upper()
    if normalized_state not in {s.name for s in AuditSnapshotState}:
        normalized_state = AuditSnapshotState.UNKNOWN.name
    if normalized_severity not in {s.name for s in AuditSnapshotItemSeverity}:
        normalized_severity = AuditSnapshotItemSeverity.INFO.name
    return AuditSnapshotItem(
        item_id=item_id,
        title=title,
        artifact_kind=artifact_kind,
        state=normalized_state,
        severity=normalized_severity,
        related_mvp=related_mvp,
        spec_reference=spec_reference,
        local_reference=local_reference,
        generated_at=generated_at,
        reason_codes=tuple(reason_codes),
        tags=tuple(tags),
        related_references=tuple(related_references),
        metadata=metadata,
    )


def build_audit_snapshot_section(
    section_kind: AuditSnapshotSectionKind,
    title: str,
    *,
    section_notes: str = "",
    items: Sequence[AuditSnapshotItem] = (),
    references: Sequence[str] = (),
    metadata: Mapping[str, Any] | None = None,
) -> AuditSnapshotSection:
    """Build a single AuditSnapshotSection with deterministically ordered items."""
    ordered_items = _order_items(items)
    return AuditSnapshotSection(
        section_kind=section_kind,
        title=title,
        section_notes=section_notes,
        items=ordered_items,
        references=tuple(references),
        metadata=metadata,
    )


def _is_item_open(item: AuditSnapshotItem) -> bool:
    """Return True if item severity > INFO or state != current."""
    if item.severity != AuditSnapshotItemSeverity.INFO.name:
        return True
    if item.state.upper() != AuditSnapshotState.CURRENT.name:
        return True
    return False


def build_audit_snapshot_data_quality(
    artifact_summaries: Sequence[Mapping[str, Any]],
    items: Sequence[AuditSnapshotItem],
    config: AuditSnapshotConfig,
) -> AuditSnapshotDataQuality:
    """Assess audit snapshot completeness and quality."""
    total_artifacts_expected = config.expected_artifact_count
    total_artifacts_present = len(artifact_summaries)
    total_artifacts_missing = max(0, total_artifacts_expected - total_artifacts_present)

    stale_count = 0
    open_count = 0
    blocked_count = 0
    unknown_count = 0
    incomplete_count = 0

    for item in items:
        state_upper = item.state.upper()
        if state_upper == AuditSnapshotState.STALE.name:
            stale_count += 1
        elif state_upper == AuditSnapshotState.BLOCK.name:
            blocked_count += 1
        elif state_upper == AuditSnapshotState.UNKNOWN.name:
            unknown_count += 1
        elif state_upper == AuditSnapshotState.INCOMPLETE.name:
            incomplete_count += 1
        if _is_item_open(item):
            open_count += 1

    return AuditSnapshotDataQuality(
        total_artifacts_expected=total_artifacts_expected,
        total_artifacts_present=total_artifacts_present,
        total_artifacts_missing=total_artifacts_missing,
        stale_artifact_count=stale_count,
        open_item_count=open_count,
        blocked_item_count=blocked_count,
        unknown_item_count=unknown_count,
        incomplete_item_count=incomplete_count,
        sections_expected=len(CANONICAL_AUDIT_SNAPSHOT_SECTION_ORDER),
        sections_present=0,
        sections_missing=len(CANONICAL_AUDIT_SNAPSHOT_SECTION_ORDER),
    )


def build_audit_snapshot_summary(
    *,
    sections: Sequence[AuditSnapshotSection],
    data_quality: AuditSnapshotDataQuality,
    snapshot_state: AuditSnapshotState,
    reason_codes: Sequence[str],
) -> AuditSnapshotSummary:
    """Aggregate counts and produce snapshot summary.

    Uses the supplied snapshot_state and reason_codes; does not re-resolve
    state and does not inspect referenced artifact files or paths.
    """
    total_sections = len(sections)
    total_items = 0
    critical_count = 0
    high_count = 0
    medium_count = 0
    low_count = 0
    info_count = 0
    current_count = 0
    stale_count = 0
    incomplete_count = 0
    blocked_count = 0
    unknown_count = 0
    open_item_count = 0

    for section in sections:
        for item in section.items:
            total_items += 1
            if item.severity == AuditSnapshotItemSeverity.CRITICAL.name:
                critical_count += 1
            elif item.severity == AuditSnapshotItemSeverity.HIGH.name:
                high_count += 1
            elif item.severity == AuditSnapshotItemSeverity.MEDIUM.name:
                medium_count += 1
            elif item.severity == AuditSnapshotItemSeverity.LOW.name:
                low_count += 1
            elif item.severity == AuditSnapshotItemSeverity.INFO.name:
                info_count += 1

            state_upper = item.state.upper()
            if state_upper == AuditSnapshotState.CURRENT.name:
                current_count += 1
            elif state_upper == AuditSnapshotState.STALE.name:
                stale_count += 1
            elif state_upper == AuditSnapshotState.INCOMPLETE.name:
                incomplete_count += 1
            elif state_upper == AuditSnapshotState.BLOCK.name:
                blocked_count += 1
            elif state_upper == AuditSnapshotState.UNKNOWN.name:
                unknown_count += 1

            if _is_item_open(item):
                open_item_count += 1

    reason_code_counts: dict[str, int] = {}
    for code in reason_codes:
        reason_code_counts[code] = reason_code_counts.get(code, 0) + 1

    narrative_parts = [
        f"Research audit snapshot state: {snapshot_state.value.upper()}.",
        (
            f"Artifacts: {data_quality.total_artifacts_present} present, "
            f"{data_quality.total_artifacts_missing} missing out of "
            f"{data_quality.total_artifacts_expected} expected."
        ),
    ]
    if data_quality.stale_artifact_count:
        narrative_parts.append(
            f"Stale artifacts: {data_quality.stale_artifact_count} exceed freshness threshold."
        )
    if open_item_count:
        narrative_parts.append(f"Open items: {open_item_count}.")
    if blocked_count:
        narrative_parts.append(f"Blocked items: {blocked_count}.")
    snapshot_narrative = " ".join(narrative_parts)

    return AuditSnapshotSummary(
        total_sections=total_sections,
        total_items=total_items,
        critical_count=critical_count,
        high_count=high_count,
        medium_count=medium_count,
        low_count=low_count,
        info_count=info_count,
        current_count=current_count,
        stale_count=stale_count,
        incomplete_count=incomplete_count,
        blocked_count=blocked_count,
        unknown_count=unknown_count,
        open_item_count=open_item_count,
        snapshot_state=snapshot_state.value.upper(),
        reason_code_counts=reason_code_counts,
        snapshot_narrative=snapshot_narrative,
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
                return False, INVALID_SNAPSHOT_CONFIG
            if value.tzinfo is None:
                return False, INVALID_SNAPSHOT_CONFIG
        elif not isinstance(value, str) or not value:
            return False, INVALID_SNAPSHOT_CONFIG
    return True, ""


def _resolve_artifact_state(
    summary: Mapping[str, Any],
    reference_time: datetime,
    freshness_threshold_seconds: int,
) -> str:
    """Resolve artifact item state from summary state and freshness."""
    raw_state = str(summary.get("state", "")).upper()
    if raw_state == AuditSnapshotState.BLOCK.name:
        return AuditSnapshotState.BLOCK.name
    if raw_state == AuditSnapshotState.INCOMPLETE.name:
        return AuditSnapshotState.INCOMPLETE.name
    if raw_state == AuditSnapshotState.UNKNOWN.name:
        return AuditSnapshotState.UNKNOWN.name

    generated_at = summary.get("generated_at")
    if isinstance(generated_at, datetime) and generated_at.tzinfo is not None:
        age_seconds = (reference_time - generated_at).total_seconds()
        if age_seconds > freshness_threshold_seconds:
            return AuditSnapshotState.STALE.name

    if raw_state == AuditSnapshotState.CURRENT.name or raw_state:
        return AuditSnapshotState.CURRENT.name

    return AuditSnapshotState.UNKNOWN.name


def _resolve_item_severity(state: str) -> str:
    """Map item state to a default severity for deterministic ordering."""
    state_upper = state.upper()
    if state_upper == AuditSnapshotState.BLOCK.name:
        return AuditSnapshotItemSeverity.CRITICAL.name
    if state_upper == AuditSnapshotState.STALE.name:
        return AuditSnapshotItemSeverity.HIGH.name
    if state_upper == AuditSnapshotState.INCOMPLETE.name:
        return AuditSnapshotItemSeverity.MEDIUM.name
    if state_upper == AuditSnapshotState.UNKNOWN.name:
        return AuditSnapshotItemSeverity.LOW.name
    return AuditSnapshotItemSeverity.INFO.name


def _build_overview_section(
    snapshot_id: str,
    generated_at: datetime,
    snapshot_state: AuditSnapshotState,
) -> AuditSnapshotSection:
    """Build OVERVIEW section."""
    notes = (
        f"Snapshot ID: {snapshot_id}\n"
        f"Generated at: {generated_at.isoformat()}\n"
        f"Snapshot state: {snapshot_state.value}\n"
        "This report summarizes the current research/audit state for human review."
    )
    return build_audit_snapshot_section(
        section_kind=AuditSnapshotSectionKind.OVERVIEW,
        title="Overview",
        section_notes=notes,
    )


def _build_version_state_section(
    config: AuditSnapshotConfig,
    project_version: str,
    source_spec: str,
) -> AuditSnapshotSection:
    """Build VERSION_STATE section."""
    notes = (
        f"Snapshot version: {SNAPSHOT_VERSION}\n"
        f"Project version: {project_version}\n"
        f"Source spec: {source_spec}\n"
        f"Config version: {config.version}\n"
        f"Freshness threshold: {config.freshness_threshold_seconds} seconds"
    )
    return build_audit_snapshot_section(
        section_kind=AuditSnapshotSectionKind.VERSION_STATE,
        title="Version State",
        section_notes=notes,
    )


def _build_artifact_state_section(items: Sequence[AuditSnapshotItem]) -> AuditSnapshotSection:
    """Build ARTIFACT_STATE section from resolved artifact items."""
    return build_audit_snapshot_section(
        section_kind=AuditSnapshotSectionKind.ARTIFACT_STATE,
        title="Artifact State",
        items=items,
        section_notes=(
            "One item per expected artifact family (MVP-10 through MVP-22). "
            "Items summarize already-loaded artifact metadata only."
        ),
    )


def _build_quality_state_section(
    data_quality: AuditSnapshotDataQuality,
) -> AuditSnapshotSection:
    """Build QUALITY_STATE section."""
    notes = (
        f"Expected artifacts: {data_quality.total_artifacts_expected}\n"
        f"Present artifacts: {data_quality.total_artifacts_present}\n"
        f"Missing artifacts: {data_quality.total_artifacts_missing}\n"
        f"Stale artifacts: {data_quality.stale_artifact_count}\n"
        f"Open items: {data_quality.open_item_count}\n"
        f"Blocked items: {data_quality.blocked_item_count}\n"
        f"Incomplete items: {data_quality.incomplete_item_count}\n"
        f"Unknown items: {data_quality.unknown_item_count}\n"
        f"Sections present: {data_quality.sections_present}\n"
        f"Sections missing: {data_quality.sections_missing}"
    )
    return build_audit_snapshot_section(
        section_kind=AuditSnapshotSectionKind.QUALITY_STATE,
        title="Quality State",
        section_notes=notes,
    )


def _build_open_items_section(items: Sequence[AuditSnapshotItem]) -> AuditSnapshotSection:
    """Build OPEN_ITEMS section from items flagged as open."""
    open_items = [item for item in items if _is_item_open(item)]
    return build_audit_snapshot_section(
        section_kind=AuditSnapshotSectionKind.OPEN_ITEMS,
        title="Open Items",
        items=open_items,
        section_notes="Items requiring human attention (severity > INFO or state != current).",
    )


def _build_safety_boundaries_section() -> AuditSnapshotSection:
    """Build SAFETY_BOUNDARIES section."""
    notes = (
        "This audit snapshot is a human-audit / contractor-handoff artifact only. "
        "It does not grant or imply any release, rollout, strategy, or transaction capacity. "
        "It is not for use by trading actors, exchange connectors, or any automated path. "
        "File references and metadata strings are local strings only; "
        "they are not traversed, opened, followed, checked, or carried out. "
        "The audit snapshot must not emit action commands."
    )
    return build_audit_snapshot_section(
        section_kind=AuditSnapshotSectionKind.SAFETY_BOUNDARIES,
        title="Safety Boundaries",
        section_notes=notes,
    )


def _build_human_audit_guide_section() -> AuditSnapshotSection:
    """Build HUMAN_AUDIT_GUIDE section."""
    notes = (
        "This section is advisory-only and non-gating. Review open items, stale artifacts, "
        "and missing artifact families before considering the audit state current. "
        "This snapshot is not a rollout checklist or execution readiness gate."
    )
    return build_audit_snapshot_section(
        section_kind=AuditSnapshotSectionKind.HUMAN_AUDIT_GUIDE,
        title="Human Audit Guide",
        section_notes=notes,
    )


def _build_appendix_references_section(
    references: Sequence[str],
) -> AuditSnapshotSection:
    """Build APPENDIX_REFERENCES section."""
    return build_audit_snapshot_section(
        section_kind=AuditSnapshotSectionKind.APPENDIX_REFERENCES,
        title="Appendix References",
        references=references,
        section_notes="Local reference strings for artifact outputs. These strings are not opened or validated.",
    )


def _resolve_snapshot_state(
    reason_codes: Sequence[str],
    config: AuditSnapshotConfig,
) -> AuditSnapshotState:
    """Resolve snapshot state from computed reason codes and config flags."""
    codes = set(reason_codes)

    if any(code in AUDIT_SNAPSHOT_BLOCKING_REASON_CODES for code in codes):
        return AuditSnapshotState.BLOCK

    if config.block_on_unknown and UNKNOWN_SNAPSHOT_STATE in codes:
        return AuditSnapshotState.BLOCK

    if config.block_on_stale and STALE_ARTIFACT_DETECTED in codes:
        return AuditSnapshotState.BLOCK

    if config.block_on_incomplete and any(
        code in AUDIT_SNAPSHOT_INCOMPLETE_REASON_CODES for code in codes
    ):
        return AuditSnapshotState.BLOCK

    if STALE_ARTIFACT_DETECTED in codes:
        return AuditSnapshotState.STALE

    if any(code in AUDIT_SNAPSHOT_INCOMPLETE_REASON_CODES for code in codes):
        return AuditSnapshotState.INCOMPLETE

    if UNKNOWN_SNAPSHOT_STATE in codes:
        return AuditSnapshotState.UNKNOWN

    return AuditSnapshotState.CURRENT


def build_research_audit_snapshot(
    artifact_summaries: Sequence[Mapping[str, Any]],
    *,
    snapshot_id: str = "",
    explicit_references: Sequence[str] = (),
    metadata: Mapping[str, Any] | None = None,
    generated_at: datetime | None = None,
    project_version: str = "0.23.0-dev",
    source_spec: str = "SPEC-024",
    config: AuditSnapshotConfig | None = None,
    safety_flags: AuditSnapshotSafetyFlags | None = None,
) -> ResearchAuditSnapshot:
    """Build full ResearchAuditSnapshot from artifact summaries.

    The engine never reads, parses, traverses, opens, follows, validates, or
    executes referenced artifact files. Callers must provide already-loaded
    metadata or explicit reference strings.
    """
    if config is None:
        config = AuditSnapshotConfig()
    if safety_flags is None:
        safety_flags = build_audit_snapshot_safety_flags()
    if generated_at is None:
        generated_at = datetime.now(timezone.utc)
    if not snapshot_id:
        snapshot_id = str(uuid4())

    # Validate config.
    try:
        config = AuditSnapshotConfig(
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
            block_on_stale=config.block_on_stale,
            freshness_threshold_seconds=config.freshness_threshold_seconds,
            expected_artifact_count=config.expected_artifact_count,
            required_sections=config.required_sections,
            include_snapshot_narrative=config.include_snapshot_narrative,
        )
    except ValueError:
        return ResearchAuditSnapshot.blocked(
            reason_code=INVALID_SNAPSHOT_CONFIG,
            snapshot_id=snapshot_id,
            generated_at=generated_at,
            metadata=metadata,
        )

    # Unsafe config content.
    if has_unsafe_audit_snapshot_content(
        {
            "version": config.version,
            "output_format": config.output_format,
        }
    ):
        return ResearchAuditSnapshot.blocked(
            reason_code=UNSAFE_SNAPSHOT_CONTENT,
            snapshot_id=snapshot_id,
            generated_at=generated_at,
            metadata=metadata,
        )

    # Unsafe explicit references / metadata.
    if has_unsafe_audit_snapshot_content(explicit_references):
        return ResearchAuditSnapshot.blocked(
            reason_code=UNSAFE_SNAPSHOT_CONTENT,
            snapshot_id=snapshot_id,
            generated_at=generated_at,
            metadata=metadata,
        )
    if has_unsafe_audit_snapshot_content(metadata):
        return ResearchAuditSnapshot.blocked(
            reason_code=UNSAFE_SNAPSHOT_CONTENT,
            snapshot_id=snapshot_id,
            generated_at=generated_at,
            metadata=metadata,
        )

    # Fail-closed rule: missing artifacts.
    if not artifact_summaries:
        return ResearchAuditSnapshot.blocked(
            reason_code=MISSING_ARTIFACT_SUMMARIES,
            snapshot_id=snapshot_id,
            generated_at=generated_at,
            metadata=metadata,
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
        return ResearchAuditSnapshot.blocked(
            reason_code=INVALID_SNAPSHOT_CONFIG,
            snapshot_id=snapshot_id,
            generated_at=generated_at,
            metadata=metadata,
        )

    # Unsafe artifact summary content.
    for summary in valid_summaries:
        if has_unsafe_audit_snapshot_content(summary):
            return ResearchAuditSnapshot.blocked(
                reason_code=UNSAFE_SNAPSHOT_CONTENT,
                snapshot_id=snapshot_id,
                generated_at=generated_at,
                metadata=metadata,
            )

    # Build artifact items from summaries.
    items: list[AuditSnapshotItem] = []
    for idx, summary in enumerate(valid_summaries):
        artifact_kind = str(summary.get("artifact_kind", ""))
        state = _resolve_artifact_state(
            summary,
            reference_time=generated_at,
            freshness_threshold_seconds=config.freshness_threshold_seconds,
        )
        severity = _resolve_item_severity(state)
        related_mvp = str(summary.get("related_mvp", ""))
        spec_reference = str(summary.get("spec_reference", ""))
        local_reference = str(summary.get("local_reference", ""))
        item_generated_at = summary.get("generated_at")
        item = build_audit_snapshot_item(
            item_id=f"{artifact_kind.lower()}-{idx}",
            title=f"{artifact_kind} artifact state",
            artifact_kind=artifact_kind,
            state=state,
            severity=severity,
            related_mvp=related_mvp,
            spec_reference=spec_reference,
            local_reference=local_reference,
            generated_at=item_generated_at if isinstance(item_generated_at, datetime) else None,
        )
        items.append(item)

    # Build sections in deterministic order.
    sections: list[AuditSnapshotSection] = [
        _build_overview_section(snapshot_id, generated_at, AuditSnapshotState.CURRENT),
        _build_version_state_section(config, project_version, source_spec),
        _build_artifact_state_section(items),
        _build_quality_state_section(
            AuditSnapshotDataQuality()
        ),  # placeholder until real data quality is computed
        _build_open_items_section(items),
        _build_safety_boundaries_section(),
        _build_human_audit_guide_section(),
        _build_appendix_references_section(explicit_references),
    ]

    # Determine reason codes.
    reason_codes: list[str] = []

    # Missing required sections.
    present_section_kinds = {s.section_kind for s in sections}
    missing_required = [
        kind for kind in config.required_sections if kind not in present_section_kinds
    ]
    if missing_required:
        reason_codes.append(MISSING_REQUIRED_SECTION)

    # Missing artifact summaries relative to expected count.
    if len(valid_summaries) < config.expected_artifact_count:
        reason_codes.append(MISSING_ARTIFACT_SUMMARIES)

    # Item-level conditions.
    for item in items:
        state_upper = item.state.upper()
        if state_upper == AuditSnapshotState.BLOCK.name:
            reason_codes.append(BLOCKED_ARTIFACT_ITEM)
        elif state_upper == AuditSnapshotState.STALE.name:
            reason_codes.append(STALE_ARTIFACT_DETECTED)
        elif state_upper == AuditSnapshotState.INCOMPLETE.name:
            reason_codes.append(INCOMPLETE_ARTIFACT_ITEM)
        elif state_upper == AuditSnapshotState.UNKNOWN.name:
            reason_codes.append(UNKNOWN_SNAPSHOT_STATE)

    if any(_is_item_open(item) for item in items):
        reason_codes.append(OPEN_ITEMS_PRESENT)

    # Advisory confirmations.
    reason_codes.append(FILE_REFS_NOT_TRAVERSED)
    reason_codes.append(ARTIFACT_FILES_NOT_READ)
    reason_codes.append(NO_ACTION_COMMANDS_EMITTED)
    reason_codes.append(HUMAN_AUDIT_GUIDE_NON_GATING)

    snapshot_state = _resolve_snapshot_state(reason_codes, config)

    # Rebuild overview section with resolved state.
    overview_section = _build_overview_section(snapshot_id, generated_at, snapshot_state)
    sections[0] = overview_section

    # Compute data quality from final sections.
    data_quality = build_audit_snapshot_data_quality(valid_summaries, items, config)
    sections[3] = _build_quality_state_section(data_quality)

    # Recompute open items section with final items.
    sections[4] = _build_open_items_section(items)

    summary = build_audit_snapshot_summary(
        sections=sections,
        data_quality=data_quality,
        snapshot_state=snapshot_state,
        reason_codes=reason_codes,
    )

    try:
        return ResearchAuditSnapshot(
            snapshot_id=snapshot_id,
            kind=AuditSnapshotKind.RESEARCH_AUDIT_SNAPSHOT,
            config=config,
            safety_flags=safety_flags,
            sections=tuple(sections),
            summary=summary,
            data_quality=data_quality,
            generated_at=generated_at,
            project_version=project_version,
            source_spec=source_spec,
            reason_codes=tuple(reason_codes),
            metadata=metadata,
        )
    except ValueError:
        return ResearchAuditSnapshot.blocked(
            reason_code=UNSAFE_SNAPSHOT_CONTENT,
            snapshot_id=snapshot_id,
            generated_at=generated_at,
            metadata=metadata,
        )
