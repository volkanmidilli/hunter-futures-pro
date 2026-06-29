"""In-memory engine for hunter.research_archive_manifest package.

MVP-19 — Local Research Archive Manifest.

The engine consumes already-loaded artifact metadata or explicit reference
strings. It never reads, parses, traverses, opens, follows, validates, or
executes referenced artifact files.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from hunter.research_archive_manifest.models import (
    ARCHIVE_BLOCKING_REASON_CODES,
    ARCHIVE_FAMILY_INFO,
    ARCHIVE_REASON_CODES,
    ArchiveArtifactEntry,
    ArchiveArtifactFamily,
    ArchiveManifestConfig,
    ArchiveManifestDataQuality,
    ArchiveManifestSafetyFlags,
    ArchiveManifestState,
    ArchiveManifestSummary,
    ResearchArchiveManifest,
    _check_unsafe_mapping,
    _has_unsafe_archive_manifest_content,
)


_ARTIFACT_FAMILY_NAMES = {
    "observation_artifact": ArchiveArtifactFamily.OBSERVATION_REPORT,
    "review_artifact": ArchiveArtifactFamily.OPERATOR_REVIEW,
    "index_artifact": ArchiveArtifactFamily.REVIEW_INDEX,
    "search_artifact": ArchiveArtifactFamily.REVIEW_SEARCH,
    "bundle_artifact": ArchiveArtifactFamily.RESEARCH_BUNDLE,
    "chronicle_artifact": ArchiveArtifactFamily.RESEARCH_CHRONICLE,
    "digest_artifact": ArchiveArtifactFamily.RESEARCH_DIGEST,
    "quality_gate_artifact": ArchiveArtifactFamily.RESEARCH_QUALITY_GATE,
    "handoff_artifact": ArchiveArtifactFamily.RESEARCH_HANDOFF,
}

_FAMILY_REASON_PREFIX = {
    ArchiveArtifactFamily.OBSERVATION_REPORT: "OBSERVATION_REPORT",
    ArchiveArtifactFamily.OPERATOR_REVIEW: "OPERATOR_REVIEW",
    ArchiveArtifactFamily.REVIEW_INDEX: "REVIEW_INDEX",
    ArchiveArtifactFamily.REVIEW_SEARCH: "REVIEW_SEARCH",
    ArchiveArtifactFamily.RESEARCH_BUNDLE: "RESEARCH_BUNDLE",
    ArchiveArtifactFamily.RESEARCH_CHRONICLE: "RESEARCH_CHRONICLE",
    ArchiveArtifactFamily.RESEARCH_DIGEST: "RESEARCH_DIGEST",
    ArchiveArtifactFamily.RESEARCH_QUALITY_GATE: "RESEARCH_QUALITY_GATE",
    ArchiveArtifactFamily.RESEARCH_HANDOFF: "RESEARCH_HANDOFF",
}

_VALID_ARTIFACT_STATES = {"READY", "PASS", "PRESENT", "WARN"}


def has_unsafe_archive_manifest_content(
    text: str | None,
    metadata: Mapping[str, Any] | None = None,
) -> bool:
    """Return True if text or metadata contain forbidden terms."""
    if text is not None and _has_unsafe_archive_manifest_content(text):
        return True
    if metadata is not None:
        return _check_unsafe_mapping(metadata)
    return False


def _get_attr_or_item(obj: Any, names: tuple[str, ...]) -> Any:
    """Return the first available attribute or dict item from names."""
    for name in names:
        if isinstance(obj, dict):
            if name in obj:
                return obj[name]
        elif hasattr(obj, name):
            return getattr(obj, name)
    return None


def _artifact_state(artifact: Any) -> str | None:
    """Extract normalized state from artifact if available."""
    if artifact is None:
        return None
    raw = _get_attr_or_item(artifact, ("state", "index_state", "search_state"))
    if raw is None:
        return None
    normalized = str(raw).strip().upper()
    return normalized


def _artifact_generated_at(artifact: Any) -> datetime | None:
    """Extract generated_at from artifact if available."""
    if artifact is None:
        return None
    value = _get_attr_or_item(artifact, ("generated_at",))
    if isinstance(value, datetime):
        return value
    return None


def _artifact_safety_flags(artifact: Any) -> Any:
    """Extract safety_flags from artifact if available."""
    if artifact is None:
        return None
    return _get_attr_or_item(artifact, ("safety_flags",))


def _artifact_reason_codes(artifact: Any) -> tuple[str, ...]:
    """Extract reason_codes from artifact if available."""
    if artifact is None:
        return ()
    value = _get_attr_or_item(artifact, ("reason_codes",))
    if isinstance(value, (tuple, list)):
        return tuple(str(x) for x in value if x)
    return ()


def _artifact_version(artifact: Any) -> str:
    """Extract version from artifact if available."""
    if artifact is None:
        return ""
    value = _get_attr_or_item(artifact, ("version",))
    if value is None:
        return ""
    return str(value)


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
    )
    for attr in unsafe_attrs:
        if hasattr(flags, attr):
            if getattr(flags, attr) is True:
                return True
    return False


def _has_blocking_reason_codes(reason_codes: tuple[str, ...]) -> bool:
    """Return True if any reason code is blocking."""
    return any(rc in ARCHIVE_BLOCKING_REASON_CODES for rc in reason_codes)


def build_archive_manifest_safety_flags(
    config: ArchiveManifestConfig,
) -> ArchiveManifestSafetyFlags:
    """Build safety flags from a validated config."""
    return ArchiveManifestSafetyFlags(
        dry_run=config.dry_run,
        live_trading_enabled=config.live_trading_enabled,
        real_orders_enabled=config.real_orders_enabled,
        leverage_enabled=config.leverage_enabled,
        shorting_enabled=config.shorting_enabled,
    )


def build_archive_artifact_entry(
    artifact_family: ArchiveArtifactFamily,
    artifact: Any | None = None,
    config: ArchiveManifestConfig | None = None,
    reference_time: datetime | None = None,
) -> ArchiveArtifactEntry:
    """Build one ArchiveArtifactEntry from already-loaded artifact metadata.

    Does not read, open, traverse, or execute any referenced file.
    """
    if config is None:
        config = ArchiveManifestConfig()
    if reference_time is None:
        reference_time = config.generated_at if config.generated_at is not None else datetime.now(timezone.utc)

    local_reference, spec_reference = ARCHIVE_FAMILY_INFO[artifact_family]
    title = artifact_family.name.replace("_", " ").title()
    family_prefix = _FAMILY_REASON_PREFIX[artifact_family]

    if artifact is None:
        if artifact_family in config.required_families:
            return ArchiveArtifactEntry(
                artifact_family=artifact_family,
                title=title,
                state="MISSING",
                spec_reference=spec_reference,
                local_reference=local_reference,
                version="",
                reason_codes=(f"MISSING_{family_prefix}",),
            )
        return ArchiveArtifactEntry(
            artifact_family=artifact_family,
            title=title,
            state="PRESENT",
            spec_reference=spec_reference,
            local_reference=local_reference,
            version="",
        )

    version = _artifact_version(artifact)
    generated_at = _artifact_generated_at(artifact)
    state = _artifact_state(artifact)
    reason_codes: tuple[str, ...] = ()

    safety_flags = _artifact_safety_flags(artifact)
    if _is_unsafe_safety_flags(safety_flags):
        return ArchiveArtifactEntry(
            artifact_family=artifact_family,
            title=title,
            state="MISSING",
            spec_reference=spec_reference,
            local_reference=local_reference,
            version=version,
            generated_at=generated_at,
            reason_codes=("UNSAFE_ARTIFACT_FLAGS",),
        )

    artifact_reason_codes = _artifact_reason_codes(artifact)
    if _has_blocking_reason_codes(artifact_reason_codes):
        return ArchiveArtifactEntry(
            artifact_family=artifact_family,
            title=title,
            state="MISSING",
            spec_reference=spec_reference,
            local_reference=local_reference,
            version=version,
            generated_at=generated_at,
            reason_codes=("UNRESOLVED_BLOCKERS",),
        )

    if state is None:
        return ArchiveArtifactEntry(
            artifact_family=artifact_family,
            title=title,
            state="UNKNOWN",
            spec_reference=spec_reference,
            local_reference=local_reference,
            version=version,
            generated_at=generated_at,
            reason_codes=(f"UNKNOWN_{family_prefix}",),
        )

    normalized_state = state if state in _VALID_ARTIFACT_STATES else None

    if normalized_state in _VALID_ARTIFACT_STATES:
        if generated_at is not None and config.max_staleness_minutes > 0:
            age = reference_time - generated_at
            if age.total_seconds() > config.max_staleness_minutes * 60:
                return ArchiveArtifactEntry(
                    artifact_family=artifact_family,
                    title=title,
                    state="STALE",
                    spec_reference=spec_reference,
                    local_reference=local_reference,
                    version=version,
                    generated_at=generated_at,
                    reason_codes=(f"STALE_{family_prefix}",),
                )
        return ArchiveArtifactEntry(
            artifact_family=artifact_family,
            title=title,
            state="PRESENT",
            spec_reference=spec_reference,
            local_reference=local_reference,
            version=version,
            generated_at=generated_at,
        )

    return ArchiveArtifactEntry(
        artifact_family=artifact_family,
        title=title,
        state="UNKNOWN",
        spec_reference=spec_reference,
        local_reference=local_reference,
        version=version,
        generated_at=generated_at,
        reason_codes=(f"UNKNOWN_{family_prefix}",),
    )


def build_archive_manifest_summary(
    entries: tuple[ArchiveArtifactEntry, ...] | list[ArchiveArtifactEntry],
    config: ArchiveManifestConfig | None = None,
) -> ArchiveManifestSummary:
    """Aggregate entries into an ArchiveManifestSummary."""
    if config is None:
        config = ArchiveManifestConfig()

    total = len(entries)
    present = sum(1 for e in entries if e.state == "PRESENT")
    stale = sum(1 for e in entries if e.state == "STALE")
    missing = sum(1 for e in entries if e.state == "MISSING")
    unknown = sum(1 for e in entries if e.state == "UNKNOWN")

    # Collect reason codes in canonical order.
    all_reason_codes: list[str] = []
    seen: set[str] = set()
    for entry in entries:
        for rc in entry.reason_codes:
            if rc not in seen:
                seen.add(rc)
                all_reason_codes.append(rc)

    ordered_reason_codes = [rc for rc in ARCHIVE_REASON_CODES if rc in seen]

    # Determine manifest state.
    if total == 0:
        manifest_state = "UNKNOWN"
        notes = "Archive manifest contains no artifact family entries."
    elif any(e.state == "MISSING" and e.artifact_family in config.required_families for e in entries):
        manifest_state = "BLOCK"
        notes = (
            "Archive manifest inventory is incomplete. Missing required artifact families "
            "must be resolved. This is not trade approval, not execution readiness, "
            "not strategy readiness, not release/deployment approval, and not transaction permission."
        )
    elif any(e.state == "UNKNOWN" for e in entries):
        if config.block_on_unknown:
            manifest_state = "BLOCK"
            notes = (
                "Archive manifest inventory contains unrecognized artifact states. "
                "This is not trade approval, not execution readiness, not strategy readiness, "
                "not release/deployment approval, and not transaction permission."
            )
        else:
            manifest_state = "WARN"
            notes = (
                "Archive manifest inventory is usable but contains unrecognized artifact states. "
                "This is not trade approval, not execution readiness, not strategy readiness, "
                "not release/deployment approval, and not transaction permission."
            )
    elif any(e.state == "STALE" for e in entries):
        manifest_state = "WARN"
        notes = (
            "Archive manifest inventory is usable but some artifacts are stale. "
            "Review stale entries before relying on inventory. "
            "This is not trade approval, not execution readiness, not strategy readiness, "
            "not release/deployment approval, and not transaction permission."
        )
    else:
        manifest_state = "READY"
        notes = (
            "All required artifact families are present and current. "
            "Archive manifest inventory is complete for human audit and contractor orientation. "
            "This is not trade approval, not execution readiness, not strategy readiness, "
            "not release/deployment approval, and not transaction permission."
        )

    reason_code_counts = {}
    for rc in ordered_reason_codes:
        reason_code_counts[rc] = sum(1 for e in entries if rc in e.reason_codes)

    return ArchiveManifestSummary(
        total_families=total,
        present_count=present,
        stale_count=stale,
        missing_count=missing,
        unknown_count=unknown,
        manifest_state=manifest_state,
        reason_code_counts=reason_code_counts,
        manifest_notes=notes,
    )


def build_archive_manifest_data_quality(
    entries: tuple[ArchiveArtifactEntry, ...] | list[ArchiveArtifactEntry],
) -> ArchiveManifestDataQuality:
    """Compute data-quality metrics from entries."""
    total = len(entries)
    if total == 0:
        return ArchiveManifestDataQuality(total_families=0)

    present = sum(1 for e in entries if e.state == "PRESENT")
    stale = sum(1 for e in entries if e.state == "STALE")
    missing = sum(1 for e in entries if e.state == "MISSING")
    unknown = sum(1 for e in entries if e.state == "UNKNOWN")

    completeness_pct = round((present / total) * 100.0, 2)
    coverage_pct = round(((present + stale) / total) * 100.0, 2)
    present_pct = completeness_pct

    reason = ""
    if missing > 0:
        reason = f"{missing} artifact family(s) missing."
    elif unknown > 0:
        reason = f"{unknown} artifact family(s) in unknown state."
    elif stale > 0:
        reason = f"{stale} artifact family(s) stale."
    else:
        reason = "All artifact families present and current."

    return ArchiveManifestDataQuality(
        completeness_pct=completeness_pct,
        coverage_pct=coverage_pct,
        present_pct=present_pct,
        missing_count=missing,
        stale_count=stale,
        unknown_count=unknown,
        total_families=total,
        reason=reason,
    )


def build_research_archive_manifest(
    *,
    config: ArchiveManifestConfig | None = None,
    reference_time: datetime | None = None,
    observation_artifact: Any | None = None,
    review_artifact: Any | None = None,
    index_artifact: Any | None = None,
    search_artifact: Any | None = None,
    bundle_artifact: Any | None = None,
    chronicle_artifact: Any | None = None,
    digest_artifact: Any | None = None,
    quality_gate_artifact: Any | None = None,
    handoff_artifact: Any | None = None,
) -> ResearchArchiveManifest:
    """Build a ResearchArchiveManifest from already-loaded artifact metadata.

    The engine never reads, parses, traverses, opens, follows, validates, or
    executes referenced artifact files. Callers must provide already-loaded
    metadata or explicit reference strings.
    """
    if config is None:
        config = ArchiveManifestConfig()
    if reference_time is None:
        reference_time = config.generated_at if config.generated_at is not None else datetime.now(timezone.utc)

    # Validate config safety invariants.
    try:
        safety_flags = build_archive_manifest_safety_flags(config)
    except ValueError as exc:
        return ResearchArchiveManifest.blocked(
            "UNSAFE_CONFIG", generated_at=reference_time, config=config
        )

    # Validate forbidden content in config fields.
    if has_unsafe_archive_manifest_content(config.version):
        return ResearchArchiveManifest.blocked(
            "UNSAFE_MANIFEST_CONTENT", generated_at=reference_time, config=config
        )

    artifact_inputs = {
        "observation_artifact": observation_artifact,
        "review_artifact": review_artifact,
        "index_artifact": index_artifact,
        "search_artifact": search_artifact,
        "bundle_artifact": bundle_artifact,
        "chronicle_artifact": chronicle_artifact,
        "digest_artifact": digest_artifact,
        "quality_gate_artifact": quality_gate_artifact,
        "handoff_artifact": handoff_artifact,
    }

    any_artifact_provided = any(v is not None for v in artifact_inputs.values())
    if not any_artifact_provided and not config.required_families:
        return ResearchArchiveManifest.blocked(
            "EMPTY_MANIFEST", generated_at=reference_time, config=config
        )

    entries: list[ArchiveArtifactEntry] = []
    for kwarg_name, family in _ARTIFACT_FAMILY_NAMES.items():
        artifact = artifact_inputs[kwarg_name]
        entry = build_archive_artifact_entry(
            family,
            artifact=artifact,
            config=config,
            reference_time=reference_time,
        )
        entries.append(entry)

    summary = build_archive_manifest_summary(tuple(entries), config=config)
    data_quality = build_archive_manifest_data_quality(tuple(entries))

    manifest_state = ArchiveManifestState[summary.manifest_state]

    all_reason_codes = summary.reason_code_counts.keys()

    manifest_id = f"archive:{config.version}:{reference_time.strftime('%Y-%m-%dT%H:%M:%S.%f')}"

    return ResearchArchiveManifest(
        manifest_id=manifest_id,
        generated_at=reference_time,
        version=config.version,
        manifest_state=manifest_state,
        entries=tuple(entries),
        summary=summary,
        data_quality=data_quality,
        safety_flags=safety_flags,
        config=config,
        reason_codes=tuple(all_reason_codes),
        manifest_notes=summary.manifest_notes,
    )
