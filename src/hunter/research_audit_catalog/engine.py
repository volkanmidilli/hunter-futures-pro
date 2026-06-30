"""In-memory engine for hunter.research_audit_catalog package.

MVP-21 — Local Research Audit Catalog.

The engine consumes already-loaded artifact metadata and explicit reference
strings. It never reads, parses, traverses, opens, follows, validates, or
executes referenced artifact files or metadata strings.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from hunter.research_audit_catalog.models import (
    CATALOG_ARTIFACT_KINDS,
    CATALOG_BLOCKING_REASON_CODES,
    CATALOG_NON_BLOCKING_REASON_CODES,
    CATALOG_REASON_CODES,
    DEFAULT_BLOCKED,
    DUPLICATE_ARTIFACT_ID,
    EMPTY_CATALOG,
    FORBIDDEN_CATALOG_TERMS,
    INVALID_ARTIFACT,
    MISSING_ARTIFACTS,
    STALE_ARTIFACT,
    UNSAFE_CATALOG_CONTENT,
    CatalogArtifactKind,
    CatalogConfig,
    CatalogDataQuality,
    CatalogEntry,
    CatalogSafetyFlags,
    CatalogState,
    CatalogSummary,
    ResearchCatalog,
    _check_forbidden_mapping,
    _has_forbidden_catalog_term,
)


def has_unsafe_audit_catalog_content(
    text: str | None,
    metadata: Mapping[str, Any] | None = None,
) -> bool:
    """Return True if text or metadata contain forbidden catalog terms."""
    if text is not None and _has_forbidden_catalog_term(text):
        return True
    if metadata is not None and _check_forbidden_mapping(metadata):
        return True
    return False


def build_audit_catalog_safety_flags() -> CatalogSafetyFlags:
    """Build default fail-closed safety flags."""
    return CatalogSafetyFlags()


def _derive_entry_id(artifact_id: str, artifact_kind: CatalogArtifactKind) -> str:
    """Deterministically derive a catalog entry_id."""
    return f"{artifact_kind.value}:{artifact_id}"


def build_audit_catalog_entry(
    artifact_id: str,
    artifact_kind: CatalogArtifactKind,
    catalog_state: CatalogState,
    source_version: str,
    generated_at: datetime,
    *,
    title: str = "",
    spec_reference: str = "",
    local_reference: str = "",
    reason_codes: tuple[str, ...] | list[str] = (),
    tags: tuple[str, ...] | list[str] = (),
    metadata: Mapping[str, Any] | None = None,
) -> CatalogEntry:
    """Build a single CatalogEntry from artifact properties.

    Does not open, traverse, validate, follow, or execute file references.
    """
    entry_id = _derive_entry_id(artifact_id, artifact_kind)
    return CatalogEntry(
        entry_id=entry_id,
        artifact_id=artifact_id,
        artifact_kind=artifact_kind,
        catalog_state=catalog_state,
        source_version=source_version,
        generated_at=generated_at,
        title=title,
        spec_reference=spec_reference,
        local_reference=local_reference,
        reason_codes=reason_codes,
        tags=tags,
        metadata=metadata,
    )


def build_audit_catalog_summary(
    entries: Sequence[CatalogEntry],
    *,
    stale_threshold_seconds: int = 86400,
    reference_time: datetime | None = None,
) -> CatalogSummary:
    """Aggregate counts across all catalog entries."""
    if reference_time is None:
        reference_time = datetime.now(timezone.utc)

    total_entries = len(entries)
    ready_count = 0
    blocked_count = 0
    unknown_count = 0
    disabled_count = 0
    kind_counts: dict[CatalogArtifactKind, int] = {}
    reason_counts: dict[str, int] = {}
    covered_kinds: set[CatalogArtifactKind] = set()
    stale_entry_count = 0
    entry_id_counts: dict[str, int] = {}

    threshold = timedelta(seconds=stale_threshold_seconds)

    for entry in entries:
        if entry.catalog_state is CatalogState.READY:
            ready_count += 1
        elif entry.catalog_state is CatalogState.BLOCKED:
            blocked_count += 1
        elif entry.catalog_state is CatalogState.UNKNOWN:
            unknown_count += 1
        elif entry.catalog_state is CatalogState.DISABLED:
            disabled_count += 1

        kind_counts[entry.artifact_kind] = kind_counts.get(entry.artifact_kind, 0) + 1
        covered_kinds.add(entry.artifact_kind)

        for code in entry.reason_codes:
            reason_counts[code] = reason_counts.get(code, 0) + 1

        entry_id_counts[entry.entry_id] = entry_id_counts.get(entry.entry_id, 0) + 1

        if reference_time - entry.generated_at > threshold:
            stale_entry_count += 1

    duplicate_id_count = sum(count for count in entry_id_counts.values() if count > 1)

    layers_covered = len(covered_kinds)
    layers_missing = len(CATALOG_ARTIFACT_KINDS) - layers_covered

    return CatalogSummary(
        total_entries=total_entries,
        ready_count=ready_count,
        blocked_count=blocked_count,
        unknown_count=unknown_count,
        disabled_count=disabled_count,
        kind_counts=kind_counts,
        reason_counts=reason_counts,
        layers_covered=layers_covered,
        layers_missing=layers_missing,
        duplicate_id_count=duplicate_id_count,
        stale_entry_count=stale_entry_count,
    )


def build_audit_catalog_data_quality(
    entries: Sequence[CatalogEntry],
    *,
    stale_threshold_seconds: int = 86400,
    reference_time: datetime | None = None,
    validation_errors: tuple[str, ...] | list[str] = (),
) -> CatalogDataQuality:
    """Assess catalog completeness and consistency."""
    if reference_time is None:
        reference_time = datetime.now(timezone.utc)

    total_artifacts = len(entries)
    valid_entries = 0
    blocked_entries = 0
    stale_entries = 0
    entry_id_counts: dict[str, int] = {}
    artifact_id_by_kind: dict[str, set[CatalogArtifactKind]] = {}
    covered_kinds: set[CatalogArtifactKind] = set()

    threshold = timedelta(seconds=stale_threshold_seconds)

    for entry in entries:
        if entry.catalog_state is CatalogState.READY:
            valid_entries += 1
        elif entry.catalog_state is CatalogState.BLOCKED:
            blocked_entries += 1

        entry_id_counts[entry.entry_id] = entry_id_counts.get(entry.entry_id, 0) + 1

        artifact_id_by_kind.setdefault(entry.artifact_id, set()).add(entry.artifact_kind)
        covered_kinds.add(entry.artifact_kind)

        if reference_time - entry.generated_at > threshold:
            stale_entries += 1

    duplicate_artifact_ids = sorted(
        entry_id for entry_id, count in entry_id_counts.items() if count > 1
    )
    cross_kind_overlap_ids = sorted(
        artifact_id
        for artifact_id, kinds in artifact_id_by_kind.items()
        if len(kinds) > 1
    )

    missing_layer_kinds = sorted(kind.value for kind in CATALOG_ARTIFACT_KINDS if kind not in covered_kinds)
    covered_layer_kinds = sorted(kind.value for kind in CATALOG_ARTIFACT_KINDS if kind in covered_kinds)

    return CatalogDataQuality(
        total_artifacts=total_artifacts,
        valid_entries=valid_entries,
        blocked_entries=blocked_entries,
        stale_entries=stale_entries,
        duplicate_artifact_ids=tuple(duplicate_artifact_ids),
        cross_kind_overlap_ids=tuple(cross_kind_overlap_ids),
        missing_layer_kinds=tuple(missing_layer_kinds),
        covered_layer_kinds=tuple(covered_layer_kinds),
        validation_errors=tuple(validation_errors),
        has_duplicates=len(duplicate_artifact_ids) > 0,
        has_cross_kind_overlap=len(cross_kind_overlap_ids) > 0,
        has_missing_layers=len(missing_layer_kinds) > 0,
        has_stale_entries=stale_entries > 0,
    )


def build_research_audit_catalog(
    entries: Sequence[CatalogEntry],
    *,
    catalog_id: str = "",
    generated_at: datetime | None = None,
    config: CatalogConfig | None = None,
    safety_flags: CatalogSafetyFlags | None = None,
    stale_threshold_seconds: int = 86400,
    reference_time: datetime | None = None,
) -> ResearchCatalog:
    """Build full ResearchCatalog from catalog entries.

    The engine never reads, parses, traverses, opens, follows, validates, or
    executes referenced artifact files. Callers must provide already-loaded
    metadata or explicit reference strings.
    """
    if config is None:
        config = CatalogConfig()
    if safety_flags is None:
        safety_flags = build_audit_catalog_safety_flags()
    if reference_time is None:
        reference_time = datetime.now(timezone.utc)
    if generated_at is None:
        generated_at = reference_time

    # Catalog ID generation: preserve explicit IDs for deterministic tests.
    if not catalog_id:
        catalog_id = str(uuid4())

    # Sort entries deterministically by (artifact_kind.value, artifact_id).
    ordered_entries = tuple(
        sorted(entries, key=lambda e: (e.artifact_kind.value, e.artifact_id))
    )

    validation_errors: list[str] = []
    valid_entries: list[CatalogEntry] = []

    for idx, entry in enumerate(ordered_entries):
        try:
            # Re-construct to trigger __post_init__ validation. This catches
            # any dataclass that was constructed with invalid fields.
            validated = CatalogEntry(
                entry_id=entry.entry_id,
                artifact_id=entry.artifact_id,
                artifact_kind=entry.artifact_kind,
                catalog_state=entry.catalog_state,
                source_version=entry.source_version,
                generated_at=entry.generated_at,
                title=entry.title,
                spec_reference=entry.spec_reference,
                local_reference=entry.local_reference,
                reason_codes=entry.reason_codes,
                tags=entry.tags,
                metadata=dict(entry.metadata),
            )
            valid_entries.append(validated)
        except ValueError as exc:
            validation_errors.append(f"entry {idx}: {exc}")

    # Fail-closed rule priority:
    # 1. MISSING_ARTIFACTS — no entries + block_on_empty
    if not ordered_entries and config.block_on_empty:
        return ResearchCatalog.blocked(
            catalog_id=catalog_id,
            generated_at=generated_at,
            reason_code=MISSING_ARTIFACTS,
            safety_flags=safety_flags,
        )

    # 2. INVALID_ARTIFACT — any entry failed validation
    if validation_errors and config.block_on_empty:
        # block_on_empty is reused as the general fail-closed gate; when False,
        # the caller opts into best-effort cataloging.
        return ResearchCatalog.blocked(
            catalog_id=catalog_id,
            generated_at=generated_at,
            reason_code=INVALID_ARTIFACT,
            safety_flags=safety_flags,
        )

    # Build summary and data quality for validation of duplicates/staleness.
    summary = build_audit_catalog_summary(
        valid_entries,
        stale_threshold_seconds=stale_threshold_seconds,
        reference_time=reference_time,
    )
    data_quality = build_audit_catalog_data_quality(
        valid_entries,
        stale_threshold_seconds=stale_threshold_seconds,
        reference_time=reference_time,
        validation_errors=tuple(validation_errors),
    )

    # 3. DUPLICATE_ARTIFACT_ID — duplicate entry_id + block_on_duplicate_ids
    if data_quality.has_duplicates and config.block_on_duplicate_ids:
        return ResearchCatalog.blocked(
            catalog_id=catalog_id,
            generated_at=generated_at,
            reason_code=DUPLICATE_ARTIFACT_ID,
            safety_flags=safety_flags,
        )

    # 4. UNSAFE_CATALOG_CONTENT — forbidden terms in tags/metadata
    has_unsafe = False
    for entry in valid_entries:
        if has_unsafe_audit_catalog_content(None, dict(entry.metadata)):
            has_unsafe = True
            break
        for tag in entry.tags:
            if has_unsafe_audit_catalog_content(tag):
                has_unsafe = True
                break
        if has_unsafe:
            break
    if has_unsafe and config.block_on_unsafe_content:
        return ResearchCatalog.blocked(
            catalog_id=catalog_id,
            generated_at=generated_at,
            reason_code=UNSAFE_CATALOG_CONTENT,
            safety_flags=safety_flags,
        )

    # Staleness is non-blocking (rule 5).
    reason_codes: tuple[str, ...] = ()
    catalog_state = CatalogState.READY

    # If entries were empty and block_on_empty is False, produce a READY empty
    # catalog. This keeps EMPTY_CATALOG available as a canonical reason code
    # without contradicting block_on_empty.
    if not ordered_entries and not config.block_on_empty:
        catalog_state = CatalogState.READY
        reason_codes = ()

    return ResearchCatalog(
        catalog_id=catalog_id,
        generated_at=generated_at,
        catalog_state=catalog_state,
        entries=tuple(valid_entries),
        summary=summary,
        data_quality=data_quality,
        safety_flags=safety_flags,
        reason_codes=reason_codes,
    )
