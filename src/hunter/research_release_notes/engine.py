"""In-memory engine for hunter.research_release_notes package.

MVP-20 — Local Research Release Notes / Audit Change Summary.

The engine consumes already-loaded artifact metadata, explicit change
descriptions, and explicit reference strings. It never reads, parses,
traverses, opens, follows, validates, or executes referenced artifact files.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from hunter.research_release_notes.models import (
    FORBIDDEN_RELEASE_NOTES_TERMS,
    RELEASE_NOTES_ARTIFACT_INFO,
    RELEASE_NOTES_BLOCKING_REASON_CODES,
    RELEASE_NOTES_REASON_CODES,
    RELEASE_NOTES_VERSION,
    ReleaseNotesChangeItem,
    ReleaseNotesChangeSeverity,
    ReleaseNotesConfig,
    ReleaseNotesDataQuality,
    ReleaseNotesKind,
    ReleaseNotesSafetyFlags,
    ReleaseNotesSection,
    ReleaseNotesSectionKind,
    ReleaseNotesState,
    ReleaseNotesSummary,
    ResearchReleaseNotes,
    _check_unsafe_mapping,
    _extract_mvp_number,
    _has_unsafe_release_notes_content,
    _severity_priority,
)


_SECTION_REASON_PREFIX = {
    ReleaseNotesSectionKind.OVERVIEW: "OVERVIEW",
    ReleaseNotesSectionKind.VERSION_AND_SCOPE: "VERSION_AND_SCOPE",
    ReleaseNotesSectionKind.ARTIFACT_CHAIN: "ARTIFACT_CHAIN",
    ReleaseNotesSectionKind.COMPLETED_MVPS: "COMPLETED_MVPS",
    ReleaseNotesSectionKind.KNOWN_GAPS: "KNOWN_GAPS",
    ReleaseNotesSectionKind.SAFETY_BOUNDARIES: "SAFETY_BOUNDARIES",
    ReleaseNotesSectionKind.HUMAN_REVIEW_GUIDE: "HUMAN_REVIEW_GUIDE",
    ReleaseNotesSectionKind.APPENDIX_REFERENCES: "APPENDIX_REFERENCES",
}


_DEFAULT_SECTION_NOTES = {
    ReleaseNotesSectionKind.OVERVIEW: (
        "This document summarizes changes across the local research/audit artifact chain. "
        "It is intended for human audit and contractor orientation only. "
        "It does not approve any release, publish, execution, strategy, or transaction."
    ),
    ReleaseNotesSectionKind.VERSION_AND_SCOPE: (
        "Documents the release/version scope covered by these notes. "
        "Version strings are local metadata only and do not allow any action."
    ),
    ReleaseNotesSectionKind.ARTIFACT_CHAIN: (
        "Lists the local research/audit artifact families produced by prior MVPs. "
        "Reference strings are local paths only and are not traversed, opened, followed, validated, or interpreted as commands."
    ),
    ReleaseNotesSectionKind.COMPLETED_MVPS: (
        "Summarizes MVPs completed in this cycle. Each item is an advisory note for human review."
    ),
    ReleaseNotesSectionKind.KNOWN_GAPS: (
        "Documents known gaps or open questions for human reviewers to inspect. "
        "These items do not block any action and do not constitute approval criteria."
    ),
    ReleaseNotesSectionKind.SAFETY_BOUNDARIES: (
        "Restates the safety boundaries that govern all local research/audit artifacts. "
        "No artifact in this chain is a trading signal, approval, or execution instruction."
    ),
    ReleaseNotesSectionKind.HUMAN_REVIEW_GUIDE: (
        "Advisory suggestions for human reviewers. These are orientation hints, not a gating checklist, "
        "not release criteria, and not publish criteria."
    ),
    ReleaseNotesSectionKind.APPENDIX_REFERENCES: (
        "Appendix of local reference strings for contractor orientation. "
        "These strings are local metadata only and are not traversed, opened, followed, validated, or interpreted as commands."
    ),
}


_HUMAN_REVIEW_GUIDE_ITEMS = (
    ReleaseNotesChangeItem(
        title="Verify all referenced artifact families are present",
        description="Confirm that the local paths listed in the artifact chain exist as expected output files. Do not open or invoke them; confirm only that the expected outputs were produced.",
        change_kind="review_suggestion",
        severity="INFO",
        related_mvp="MVP-19",
        spec_reference="SPEC-020",
    ),
    ReleaseNotesChangeItem(
        title="Review known gaps before relying on any artifact",
        description="Inspect the known gaps section to understand what is incomplete or outstanding. Gaps are advisory and do not allow any execution.",
        change_kind="review_suggestion",
        severity="INFO",
        related_mvp="MVP-20",
        spec_reference="SPEC-021",
    ),
    ReleaseNotesChangeItem(
        title="Confirm safety boundaries are understood",
        description="Ensure all consumers understand that research artifacts are human-audit only and must not feed execution, strategy, or trading paths.",
        change_kind="review_suggestion",
        severity="INFO",
        related_mvp="MVP-20",
        spec_reference="SPEC-021",
    ),
)


_SAFETY_BOUNDARY_ITEMS = (
    ReleaseNotesChangeItem(
        title="Research artifacts are human-audit only",
        description="Observation reports, review records, indices, search results, bundles, chronicles, digests, quality gates, handoff packets, archive manifests, and release notes are for human audit and contractor orientation only.",
        change_kind="safety_boundary",
        severity="INFO",
        related_mvp="MVP-10",
        spec_reference="SPEC-011",
    ),
    ReleaseNotesChangeItem(
        title="No trading or execution approval",
        description="No research artifact is a trading signal, trade approval, execution readiness verdict, strategy readiness verdict, release approval, publish approval, or transaction permission.",
        change_kind="safety_boundary",
        severity="INFO",
        related_mvp="MVP-20",
        spec_reference="SPEC-021",
    ),
    ReleaseNotesChangeItem(
        title="No feedback into execution paths",
        description="Research artifacts must not be consumed by execution, strategy, Freqtrade shell, exchange interaction, or any MVP execution path.",
        change_kind="safety_boundary",
        severity="INFO",
        related_mvp="MVP-20",
        spec_reference="SPEC-021",
    ),
    ReleaseNotesChangeItem(
        title="File references are local strings only",
        description="Reference strings in research artifacts are not traversed, opened, followed, validated, or interpreted as commands. Referenced files are not read by the release notes engine.",
        change_kind="safety_boundary",
        severity="INFO",
        related_mvp="MVP-20",
        spec_reference="SPEC-021",
    ),
)


def has_unsafe_release_notes_content(
    text: str | None,
    metadata: Mapping[str, Any] | None = None,
) -> bool:
    """Return True if text or metadata contain forbidden terms."""
    if text is not None and _has_unsafe_release_notes_content(text):
        return True
    if metadata is not None:
        return _check_unsafe_mapping(metadata)
    return False


def build_release_notes_safety_flags(
    config: ReleaseNotesConfig,
) -> ReleaseNotesSafetyFlags:
    """Build safety flags from a validated config."""
    return ReleaseNotesSafetyFlags(
        dry_run=config.dry_run,
        live_trading_enabled=config.live_trading_enabled,
        real_orders_enabled=config.real_orders_enabled,
        leverage_enabled=config.leverage_enabled,
        shorting_enabled=config.shorting_enabled,
    )


def build_release_notes_change_item(
    *,
    title: str,
    description: str = "",
    change_kind: str = "",
    severity: str | ReleaseNotesChangeSeverity = "INFO",
    related_mvp: str = "",
    spec_reference: str = "",
    related_references: tuple[str, ...] | list[str] = (),
    metadata: Mapping[str, Any] | None = None,
) -> ReleaseNotesChangeItem:
    """Build one ReleaseNotesChangeItem.

    Does not open, traverse, validate, follow, or execute file references.
    """
    if isinstance(severity, ReleaseNotesChangeSeverity):
        severity_str = severity.value
    else:
        severity_str = str(severity)
    return ReleaseNotesChangeItem(
        title=title,
        description=description,
        change_kind=change_kind,
        severity=severity_str,
        related_mvp=related_mvp,
        spec_reference=spec_reference,
        related_references=related_references,
        metadata=metadata,
    )


def _sort_change_items(
    items: tuple[ReleaseNotesChangeItem, ...],
) -> tuple[ReleaseNotesChangeItem, ...]:
    """Sort change items deterministically by severity, MVP number, insertion order."""
    return tuple(
        pair[1]
        for pair in sorted(
            enumerate(items),
            key=lambda pair: (
                _severity_priority(pair[1].severity),
                _extract_mvp_number(pair[1].related_mvp),
                pair[0],
            ),
        )
    )


def build_release_notes_section(
    section_kind: ReleaseNotesSectionKind,
    *,
    change_items: tuple[ReleaseNotesChangeItem, ...] | list[ReleaseNotesChangeItem] = (),
    section_notes: str = "",
    title: str = "",
    metadata: Mapping[str, Any] | None = None,
) -> ReleaseNotesSection:
    """Build one ReleaseNotesSection with deterministic change item ordering."""
    if isinstance(change_items, list):
        change_items = tuple(change_items)
    ordered_items = _sort_change_items(change_items)
    return ReleaseNotesSection(
        section_kind=section_kind,
        title=title,
        section_notes=section_notes,
        change_items=ordered_items,
        metadata=metadata,
    )


def _section_has_content(section: ReleaseNotesSection) -> bool:
    """Return True if section has change items or section notes."""
    return bool(section.change_items or section.section_notes)


def build_release_notes_summary(
    sections: tuple[ReleaseNotesSection, ...] | list[ReleaseNotesSection],
    config: ReleaseNotesConfig | None = None,
) -> ReleaseNotesSummary:
    """Aggregate sections into a ReleaseNotesSummary."""
    if config is None:
        config = ReleaseNotesConfig()

    if isinstance(sections, list):
        sections = tuple(sections)

    total_sections = len(sections)
    total_change_items = sum(len(s.change_items) for s in sections)
    critical = sum(
        1 for s in sections for item in s.change_items if item.severity == "CRITICAL"
    )
    high = sum(
        1 for s in sections for item in s.change_items if item.severity == "HIGH"
    )
    medium = sum(
        1 for s in sections for item in s.change_items if item.severity == "MEDIUM"
    )
    low = sum(
        1 for s in sections for item in s.change_items if item.severity == "LOW"
    )
    info = sum(
        1 for s in sections for item in s.change_items if item.severity == "INFO"
    )

    # Collect reason codes in canonical order.
    all_reason_codes: list[str] = []
    seen: set[str] = set()
    for section in sections:
        # Empty required section is a warning-level reason code.
        if section.section_kind in config.required_sections and not _section_has_content(section):
            rc = "EMPTY_SECTION"
            if rc not in seen:
                seen.add(rc)
                all_reason_codes.append(rc)

    ordered_reason_codes = [rc for rc in RELEASE_NOTES_REASON_CODES if rc in seen]

    # Determine release notes state.
    present_section_kinds = {s.section_kind for s in sections}
    missing_required = [
        kind for kind in config.required_sections if kind not in present_section_kinds
    ]

    if missing_required:
        release_notes_state = "BLOCK"
        notes = (
            "Release notes are incomplete. Missing required sections must be resolved. "
            "This is not release approval, not publish approval, not execution readiness, "
            "not strategy readiness, not trade approval, and not transaction permission."
        )
    elif any(
        s.section_kind in config.required_sections and not _section_has_content(s)
        for s in sections
    ):
        release_notes_state = "WARN"
        notes = (
            "Release notes are usable but some required sections are incomplete. "
            "Review empty sections before relying on this summary. "
            "This is not release approval, not publish approval, not execution readiness, "
            "not strategy readiness, not trade approval, and not transaction permission."
        )
    else:
        release_notes_state = "READY"
        notes = (
            "Release notes are complete for human audit and contractor orientation. "
            "All required sections are present. "
            "This is not release approval, not publish approval, not execution readiness, "
            "not strategy readiness, not trade approval, and not transaction permission."
        )

    reason_code_counts = {}
    for rc in ordered_reason_codes:
        reason_code_counts[rc] = sum(
            1
            for s in sections
            if s.section_kind in config.required_sections and not _section_has_content(s)
        )

    return ReleaseNotesSummary(
        total_sections=total_sections,
        total_change_items=total_change_items,
        critical_count=critical,
        high_count=high,
        medium_count=medium,
        low_count=low,
        info_count=info,
        release_notes_state=release_notes_state,
        reason_code_counts=reason_code_counts,
        release_notes=notes,
    )


def build_release_notes_data_quality(
    sections: tuple[ReleaseNotesSection, ...] | list[ReleaseNotesSection],
    config: ReleaseNotesConfig | None = None,
) -> ReleaseNotesDataQuality:
    """Compute data-quality metrics from sections."""
    if config is None:
        config = ReleaseNotesConfig()

    if isinstance(sections, list):
        sections = tuple(sections)

    total_required = len(config.required_sections)
    present_kinds = {s.section_kind for s in sections}
    sections_present = len(
        [kind for kind in config.required_sections if kind in present_kinds]
    )
    sections_missing = total_required - sections_present

    total_change_items = sum(len(s.change_items) for s in sections)
    with_specs = sum(
        1
        for s in sections
        for item in s.change_items
        if item.spec_reference
    )
    without_specs = total_change_items - with_specs

    completeness_pct = 0.0
    coverage_pct = 0.0
    if total_required > 0:
        completeness_pct = round((sections_present / total_required) * 100.0, 2)
    if total_change_items > 0:
        coverage_pct = round((with_specs / total_change_items) * 100.0, 2)

    reason = ""
    if sections_missing > 0:
        reason = f"{sections_missing} required section(s) missing."
    elif total_change_items > 0 and without_specs > 0:
        reason = f"{without_specs} change item(s) lack a spec reference."
    elif total_change_items == 0:
        reason = "No change items provided."
    else:
        reason = "All required sections present and all change items reference a spec."

    return ReleaseNotesDataQuality(
        completeness_pct=completeness_pct,
        coverage_pct=coverage_pct,
        sections_present=sections_present,
        sections_missing=sections_missing,
        total_sections=total_required,
        change_items_with_specs=with_specs,
        change_items_without_specs=without_specs,
        reason=reason,
    )


def _is_unsafe_safety_flags(flags: Any) -> bool:
    """Return True if artifact safety flags indicate any unsafe flag is True."""
    if flags is None:
        return False
    unsafe_attrs = (
        "live_trading_enabled",
        "real_orders_enabled",
        "leverage_enabled",
        "shorting_enabled",
        "archive_manifest_feedback_into_execution",
        "cross_layer_feedback_into_execution",
        "handoff_feedback_into_execution",
        "quality_gate_feedback_into_execution",
        "digest_feedback_into_execution",
        "chronicle_feedback_into_execution",
        "bundle_feedback_into_execution",
        "search_feedback_into_execution",
        "index_feedback_into_execution",
        "operator_feedback_into_execution",
        "report_feedback_into_execution",
        "release_notes_feedback_into_execution",
    )
    for attr in unsafe_attrs:
        if hasattr(flags, attr):
            if getattr(flags, attr) is True:
                return True
    return False


def _has_blocking_reason_codes(reason_codes: tuple[str, ...]) -> bool:
    """Return True if any reason code is blocking.

    For cross-MVP artifact inputs, any non-empty reason code is treated as
    blocking because the release notes engine cannot safely interpret the
    severity of another MVP's reason codes.
    """
    return any(bool(rc) for rc in reason_codes)


def _check_input_artifacts_for_blockers(
    input_artifacts: Mapping[str, Any] | None,
) -> tuple[bool, str]:
    """Check already-loaded artifact metadata for unsafe flags or blockers.

    Does not read, open, or traverse referenced files.
    """
    if input_artifacts is None:
        return False, ""
    for artifact in input_artifacts.values():
        if artifact is None:
            continue
        flags = getattr(artifact, "safety_flags", None)
        if flags is None and isinstance(artifact, dict):
            flags = artifact.get("safety_flags")
        if _is_unsafe_safety_flags(flags):
            return True, "UNSAFE_ARTIFACT_FLAGS"
        reason_codes = getattr(artifact, "reason_codes", None)
        if reason_codes is None and isinstance(artifact, dict):
            reason_codes = artifact.get("reason_codes")
        if isinstance(reason_codes, (tuple, list)):
            if _has_blocking_reason_codes(tuple(reason_codes)):
                return True, "UNRESOLVED_BLOCKERS"
    return False, ""


def _build_default_sections(
    release_version: str,
    release_title: str,
) -> dict[ReleaseNotesSectionKind, ReleaseNotesSection]:
    """Build default sections that require no caller input.

    Reference strings are local metadata only and are not traversed or executed.
    """
    # Artifact chain entries: one per artifact family.
    artifact_chain_items: list[ReleaseNotesChangeItem] = []
    appendix_items: list[ReleaseNotesChangeItem] = []
    for family, (local_reference, spec_reference) in RELEASE_NOTES_ARTIFACT_INFO.items():
        title = family.replace("_", " ").title()
        artifact_chain_items.append(
            ReleaseNotesChangeItem(
                title=f"{title} artifact family",
                description=f"Local {title.lower()} artifact family referenced by {spec_reference}.",
                change_kind="artifact_family",
                severity="INFO",
                related_mvp=spec_reference.replace("SPEC-0", "MVP-").replace("SPEC-", "MVP-"),
                spec_reference=spec_reference,
                related_references=(local_reference,),
            )
        )
        appendix_items.append(
            ReleaseNotesChangeItem(
                title=f"{title} reference",
                description=f"Local reference string for {title.lower()}.",
                change_kind="reference_string",
                severity="INFO",
                related_mvp=spec_reference.replace("SPEC-0", "MVP-").replace("SPEC-", "MVP-"),
                spec_reference=spec_reference,
                related_references=(local_reference,),
            )
        )

    overview_items = [
        ReleaseNotesChangeItem(
            title="Local research release notes generated",
            description="This document is a deterministic, human-audit change summary across the local research/audit artifact chain.",
            change_kind="summary",
            severity="INFO",
            related_mvp="MVP-20",
            spec_reference="SPEC-021",
        ),
    ]

    version_items: list[ReleaseNotesChangeItem] = []
    if release_version:
        version_items.append(
            ReleaseNotesChangeItem(
                title=f"Release version {release_version}",
                description="Version identifier for this set of release notes. This is a metadata label only.",
                change_kind="version_label",
                severity="INFO",
                related_mvp="MVP-20",
                spec_reference="SPEC-021",
            )
        )
    if release_title:
        version_items.append(
            ReleaseNotesChangeItem(
                title=release_title,
                description="Release title for this set of release notes. This is a metadata label only.",
                change_kind="title_label",
                severity="INFO",
                related_mvp="MVP-20",
                spec_reference="SPEC-021",
            )
        )

    return {
        ReleaseNotesSectionKind.OVERVIEW: build_release_notes_section(
            ReleaseNotesSectionKind.OVERVIEW,
            change_items=overview_items,
            section_notes=_DEFAULT_SECTION_NOTES[ReleaseNotesSectionKind.OVERVIEW],
        ),
        ReleaseNotesSectionKind.VERSION_AND_SCOPE: build_release_notes_section(
            ReleaseNotesSectionKind.VERSION_AND_SCOPE,
            change_items=version_items,
            section_notes=_DEFAULT_SECTION_NOTES[ReleaseNotesSectionKind.VERSION_AND_SCOPE],
        ),
        ReleaseNotesSectionKind.ARTIFACT_CHAIN: build_release_notes_section(
            ReleaseNotesSectionKind.ARTIFACT_CHAIN,
            change_items=artifact_chain_items,
            section_notes=_DEFAULT_SECTION_NOTES[ReleaseNotesSectionKind.ARTIFACT_CHAIN],
        ),
        ReleaseNotesSectionKind.SAFETY_BOUNDARIES: build_release_notes_section(
            ReleaseNotesSectionKind.SAFETY_BOUNDARIES,
            change_items=_SAFETY_BOUNDARY_ITEMS,
            section_notes=_DEFAULT_SECTION_NOTES[ReleaseNotesSectionKind.SAFETY_BOUNDARIES],
        ),
        ReleaseNotesSectionKind.HUMAN_REVIEW_GUIDE: build_release_notes_section(
            ReleaseNotesSectionKind.HUMAN_REVIEW_GUIDE,
            change_items=_HUMAN_REVIEW_GUIDE_ITEMS,
            section_notes=_DEFAULT_SECTION_NOTES[ReleaseNotesSectionKind.HUMAN_REVIEW_GUIDE],
        ),
        ReleaseNotesSectionKind.APPENDIX_REFERENCES: build_release_notes_section(
            ReleaseNotesSectionKind.APPENDIX_REFERENCES,
            change_items=appendix_items,
            section_notes=_DEFAULT_SECTION_NOTES[ReleaseNotesSectionKind.APPENDIX_REFERENCES],
        ),
    }


def build_research_release_notes(
    *,
    release_version: str = "",
    release_title: str = "",
    change_items_by_section: Mapping[
        ReleaseNotesSectionKind,
        tuple[ReleaseNotesChangeItem, ...] | list[ReleaseNotesChangeItem],
    ]
    | None = None,
    section_notes: Mapping[ReleaseNotesSectionKind, str] | None = None,
    input_artifacts: Mapping[str, Any] | None = None,
    config: ReleaseNotesConfig | None = None,
    reference_time: datetime | None = None,
) -> ResearchReleaseNotes:
    """Build a ResearchReleaseNotes from already-loaded metadata.

    The engine never reads, parses, traverses, opens, follows, validates, or
    executes referenced artifact files. Callers must provide already-loaded
    metadata or explicit reference strings.
    """
    if config is None:
        config = ReleaseNotesConfig()
    if reference_time is None:
        reference_time = (
            config.generated_at
            if config.generated_at is not None
            else datetime.now(timezone.utc)
        )

    # Validate config safety invariants.
    try:
        safety_flags = build_release_notes_safety_flags(config)
    except ValueError:
        return ResearchReleaseNotes.blocked(
            "UNSAFE_CONFIG", generated_at=reference_time, config=config
        )

    # Validate forbidden content in caller-provided strings.
    if has_unsafe_release_notes_content(release_version):
        return ResearchReleaseNotes.blocked(
            "UNSAFE_RELEASE_NOTES_CONTENT", generated_at=reference_time, config=config
        )
    if has_unsafe_release_notes_content(release_title):
        return ResearchReleaseNotes.blocked(
            "UNSAFE_RELEASE_NOTES_CONTENT", generated_at=reference_time, config=config
        )
    if section_notes is not None:
        for kind, note in section_notes.items():
            if has_unsafe_release_notes_content(note):
                return ResearchReleaseNotes.blocked(
                    "UNSAFE_SECTION_CONTENT", generated_at=reference_time, config=config
                )

    # Check already-loaded artifact metadata for unsafe flags or blockers.
    has_blocker, blocker_reason = _check_input_artifacts_for_blockers(input_artifacts)
    if has_blocker:
        return ResearchReleaseNotes.blocked(
            blocker_reason, generated_at=reference_time, config=config
        )

    # Normalize inputs.
    if change_items_by_section is None:
        change_items_by_section = {}
    if section_notes is None:
        section_notes = {}

    # If the caller provided nothing and required nothing, fail-closed.
    caller_provided_anything = bool(
        change_items_by_section or section_notes or release_version or release_title
    )
    if not caller_provided_anything and not config.required_sections:
        return ResearchReleaseNotes.blocked(
            "EMPTY_RELEASE_NOTES", generated_at=reference_time, config=config
        )

    # Build default sections.
    default_sections = _build_default_sections(release_version, release_title)

    # Merge caller-provided sections with defaults.
    merged_sections: dict[ReleaseNotesSectionKind, ReleaseNotesSection] = {}
    for kind in ReleaseNotesSectionKind:
        provided_items = change_items_by_section.get(kind, ())
        provided_notes = section_notes.get(kind, "")
        explicitly_provided = kind in change_items_by_section or kind in section_notes

        if kind in default_sections:
            default_section = default_sections[kind]
            # Combine default items with caller-provided items, preserving
            # caller insertion order for provided items appended after defaults.
            combined_items = tuple(default_section.change_items) + tuple(provided_items)
            notes = provided_notes or default_section.section_notes
        else:
            combined_items = tuple(provided_items)
            notes = provided_notes

        has_content = bool(combined_items or notes)
        # Default sections are always included (they carry safety content).
        # Non-default sections are included only when they have content or were
        # explicitly provided by the caller.
        is_default_section = kind in default_sections
        if has_content or is_default_section or explicitly_provided:
            merged_sections[kind] = build_release_notes_section(
                kind,
                change_items=combined_items,
                section_notes=notes,
            )

    # Determine missing required sections and attach reason codes.
    present_kinds = set(merged_sections.keys())
    missing_required = [
        kind for kind in config.required_sections if kind not in present_kinds
    ]

    # Order sections deterministically.
    ordered_sections = tuple(
        merged_sections[kind]
        for kind in ReleaseNotesSectionKind
        if kind in merged_sections
    )

    # Build summary and data quality.
    summary = build_release_notes_summary(ordered_sections, config=config)
    data_quality = build_release_notes_data_quality(ordered_sections, config=config)

    # Override summary state if required sections are missing.
    state = ReleaseNotesState[summary.release_notes_state]
    reason_codes: list[str] = []
    if missing_required:
        state = ReleaseNotesState.BLOCK
        for kind in missing_required:
            prefix = _SECTION_REASON_PREFIX[kind]
            reason_codes.append(f"MISSING_{prefix}")
        notes = (
            "Release notes are incomplete. Missing required sections must be resolved. "
            "This is not release approval, not publish approval, not execution readiness, "
            "not strategy readiness, not trade approval, and not transaction permission."
        )
        summary = ReleaseNotesSummary(
            total_sections=summary.total_sections,
            total_change_items=summary.total_change_items,
            critical_count=summary.critical_count,
            high_count=summary.high_count,
            medium_count=summary.medium_count,
            low_count=summary.low_count,
            info_count=summary.info_count,
            release_notes_state="BLOCK",
            reason_code_counts=summary.reason_code_counts,
            release_notes=notes,
        )
    else:
        notes = summary.release_notes

    # Attach empty-section reason codes for required sections that are empty.
    for section in ordered_sections:
        if section.section_kind in config.required_sections and not _section_has_content(section):
            if "EMPTY_SECTION" not in reason_codes:
                reason_codes.append("EMPTY_SECTION")

    # Canonicalize reason code order.
    all_reason_codes = reason_codes + [rc for rc in RELEASE_NOTES_REASON_CODES if rc in summary.reason_code_counts]
    seen: set[str] = set()
    canonical_reason_codes = []
    for rc in all_reason_codes:
        if rc not in seen:
            seen.add(rc)
            canonical_reason_codes.append(rc)
    ordered_reason_codes = [rc for rc in RELEASE_NOTES_REASON_CODES if rc in canonical_reason_codes]

    release_notes_id = f"release-notes:{config.version}:{reference_time.strftime('%Y-%m-%dT%H:%M:%S.%f')}"

    return ResearchReleaseNotes(
        release_notes_id=release_notes_id,
        generated_at=reference_time,
        version=config.version,
        release_version=release_version or config.release_version,
        release_title=release_title or config.release_title,
        kind=ReleaseNotesKind.RESEARCH_RELEASE_NOTES,
        release_notes_state=state,
        sections=ordered_sections,
        summary=summary,
        data_quality=data_quality,
        safety_flags=safety_flags,
        config=config,
        reason_codes=tuple(ordered_reason_codes),
        document_notes=notes,
    )
