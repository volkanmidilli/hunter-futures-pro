"""Engine for hunter.research_digest package.

MVP-16 — Local Research Digest / Executive Summary.

All functions are pure: no file I/O, no network, no database, no side effects.
File references and metadata strings are local strings only and are never
traversed, opened, followed, validated, or executed.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from hunter.research_digest.models import (
    DIGEST_VERSION,
    FORBIDDEN_DIGEST_TERMS,
    DigestConfig,
    DigestDataQuality,
    DigestSafetyFlags,
    DigestSection,
    DigestSectionKind,
    DigestState,
    DigestSummary,
    ResearchDigest,
    _check_unsafe_mapping,
    _has_unsafe_digest_content,
)


_VALID_OUTPUT_FORMATS = ("json", "markdown", "both")
_VALID_ARTIFACT_STATES = ("DISABLED", "READY", "BLOCKED", "UNKNOWN")
_BLOCKING_REASON_PREFIXES = ("MISSING_", "INVALID_", "UNSAFE_")


def has_unsafe_digest_content(notes: str | None, metadata: Mapping[str, Any] | None = None) -> bool:
    """Return True if notes or metadata contain forbidden digest terms.

    Does not open, traverse, validate, follow, or execute file references.
    """
    if notes is not None and _has_unsafe_digest_content(notes):
        return True
    if metadata is not None and _check_unsafe_mapping(metadata):
        return True
    return False


def build_digest_safety_flags(config: DigestConfig | None = None) -> DigestSafetyFlags:
    """Build safety flags from config.

    If config is unsafe, raises ValueError (fail-closed).
    """
    if config is None:
        return DigestSafetyFlags()

    # Config validation already enforces dry_run=True and unsafe flags=False.
    # Safety flag construction validates the same invariants in __post_init__.
    return DigestSafetyFlags(
        dry_run=config.dry_run,
        live_trading_enabled=config.live_trading_enabled,
        real_orders_enabled=config.real_orders_enabled,
        leverage_enabled=config.leverage_enabled,
        shorting_enabled=config.shorting_enabled,
    )


def _normalize_state(raw: str | None) -> str:
    """Normalize artifact state string to a valid section state."""
    if raw is None:
        return "UNKNOWN"
    if hasattr(raw, "value"):
        raw = raw.value
    if not isinstance(raw, str):
        return "UNKNOWN"
    upper = raw.strip().upper()
    if upper in _VALID_ARTIFACT_STATES:
        return upper
    return "UNKNOWN"


def _is_recognized_state(raw: str | None) -> bool:
    """Return True if raw state is one of the recognized values."""
    if raw is None:
        return False
    if hasattr(raw, "value"):
        raw = raw.value
    if not isinstance(raw, str):
        return False
    return raw.strip().upper() in _VALID_ARTIFACT_STATES


def _is_blocking_reason(reason: str) -> bool:
    """Return True if reason indicates a blocking condition."""
    upper = reason.upper()
    if upper.startswith(_BLOCKING_REASON_PREFIXES):
        return True
    if upper in {"DIGEST_ERROR", "EMPTY_DIGEST", "INVALID_CONFIG", "UNSAFE_CONFIG"}:
        return True
    return False


def build_digest_section(
    section_kind: DigestSectionKind,
    artifact_state: str | None = None,
    artifact_count: int = 0,
    blocked_count: int = 0,
    ready_count: int = 0,
    missing_count: int = 0,
    reason_codes: tuple[str, ...] = (),
    notes: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> DigestSection:
    """Build a DigestSection with deterministic counts.

    - If artifact_state is None or empty → state UNKNOWN, missing_count = 1.
    - If artifact_state in (BLOCKED, UNKNOWN, DISABLED) → state preserved,
      blockers_count = blocked_count + missing_count.
    - If artifact_state == READY and content unsafe → state BLOCKED,
      append UNSAFE_DIGEST_CONTENT.
    - Else → state READY, blockers_count = 0.
    """
    if not isinstance(section_kind, DigestSectionKind):
        raise ValueError("section_kind must be a DigestSectionKind enum instance")

    normalized = _normalize_state(artifact_state)

    if artifact_state is None or (isinstance(artifact_state, str) and not artifact_state.strip()):
        state = "UNKNOWN"
        effective_missing_count = max(missing_count, 1)
    else:
        state = normalized
        effective_missing_count = missing_count

    blockers_count = 0
    effective_reason_codes = list(reason_codes)

    if state in ("BLOCKED", "UNKNOWN", "DISABLED"):
        blockers_count = blocked_count + effective_missing_count
    elif state == "READY" and has_unsafe_digest_content(notes, metadata):
        state = "BLOCKED"
        blockers_count = blocked_count + effective_missing_count
        if "UNSAFE_DIGEST_CONTENT" not in effective_reason_codes:
            effective_reason_codes.append("UNSAFE_DIGEST_CONTENT")
    elif state == "READY":
        blockers_count = 0

    unresolved_blocker_reasons = tuple(
        rc for rc in effective_reason_codes if _is_blocking_reason(rc)
    )

    # Ensure blockers_count covers all unresolved blocker reasons.
    blockers_count = max(blockers_count, len(unresolved_blocker_reasons))

    return DigestSection(
        section_kind=section_kind,
        state=state,
        count=max(artifact_count, 0),
        blocked_count=max(blocked_count, 0),
        ready_count=max(ready_count, 0),
        missing_count=max(effective_missing_count, 0),
        reason_codes=tuple(effective_reason_codes),
        blockers_count=max(blockers_count, 0),
        unresolved_blocker_reasons=unresolved_blocker_reasons,
        notes=notes,
        metadata=metadata,
    )


def _generate_next_review_notes(
    sections: Sequence[DigestSection],
    include_unresolved_blockers: bool = True,
) -> str:
    """Generate human-readable next-review notes from sections."""
    total = len(sections)
    ready = sum(1 for s in sections if s.state == "READY")
    blocked_sections = [s.section_kind.value for s in sections if s.state == "BLOCKED"]
    missing_sections = [s.section_kind.value for s in sections if s.missing_count > 0]
    unknown_sections = [s.section_kind.value for s in sections if s.state == "UNKNOWN"]

    if total == 0:
        return "No sections available. Digest is empty."
    if ready == total:
        return "All layers ready. No blockers detected. Digest is ready for handoff."

    parts: list[str] = []
    if blocked_sections:
        parts.append(f"Blocked sections detected: {', '.join(blocked_sections)}. Review blockers before handoff.")
    if unknown_sections:
        parts.append(f"Unknown sections detected: {', '.join(unknown_sections)}. Provide valid artifact states.")
    if missing_sections:
        parts.append(f"Missing sections detected: {', '.join(missing_sections)}. Complete missing artifacts before handoff.")

    if include_unresolved_blockers:
        blocker_reasons: set[str] = set()
        for section in sections:
            blocker_reasons.update(section.unresolved_blocker_reasons)
        if blocker_reasons:
            parts.append(f"Unresolved blockers: {', '.join(sorted(blocker_reasons))}.")

    return " ".join(parts) if parts else "Digest contains unresolved issues. Review sections before handoff."


def build_digest_summary(
    sections: Sequence[DigestSection],
    *,
    include_next_review_notes: bool = True,
    include_unresolved_blockers: bool = True,
) -> DigestSummary:
    """Build a DigestSummary from a sequence of sections."""
    total_sections = len(sections)
    ready_sections = sum(1 for s in sections if s.state == "READY")
    blocked_sections = sum(1 for s in sections if s.state in ("BLOCKED", "UNKNOWN"))
    missing_sections = sum(1 for s in sections if s.missing_count > 0)
    total_artifacts = sum(s.count for s in sections)
    total_blockers = sum(s.blockers_count for s in sections)
    unresolved_blockers = sum(len(s.unresolved_blocker_reasons) for s in sections)

    reason_code_counts = Counter[str]()
    for section in sections:
        for rc in section.reason_codes:
            reason_code_counts[rc] += 1

    cross_layer_ready = ready_sections == total_sections and total_sections > 0

    next_review_notes = ""
    if include_next_review_notes:
        next_review_notes = _generate_next_review_notes(
            sections, include_unresolved_blockers=include_unresolved_blockers
        )

    return DigestSummary(
        total_sections=total_sections,
        ready_sections=ready_sections,
        blocked_sections=blocked_sections,
        missing_sections=missing_sections,
        total_artifacts=total_artifacts,
        total_blockers=total_blockers,
        unresolved_blockers=unresolved_blockers,
        reason_code_counts=dict(sorted(reason_code_counts.items())),
        cross_layer_ready=cross_layer_ready,
        next_review_notes=next_review_notes,
    )


def build_digest_data_quality(sections: Sequence[DigestSection]) -> DigestDataQuality:
    """Build DigestDataQuality from a sequence of sections."""
    total_sections = len(sections)
    ready_count = sum(1 for s in sections if s.state == "READY")
    completeness_pct = (ready_count / total_sections * 100.0) if total_sections > 0 else 0.0
    missing_count = sum(s.missing_count for s in sections)
    stale_count = sum(1 for s in sections if s.state == "UNKNOWN")
    invalid_count = sum(
        1 for s in sections
        if any("INVALID" in rc for rc in s.reason_codes)
    )
    blocked_count = sum(s.blocked_count for s in sections)

    reason = ""
    if blocked_count > 0:
        for section in sections:
            if section.reason_codes:
                reason = section.reason_codes[0]
                break

    return DigestDataQuality(
        completeness_pct=completeness_pct,
        missing_count=missing_count,
        stale_count=stale_count,
        invalid_count=invalid_count,
        blocked_count=blocked_count,
        total_sections=total_sections,
        reason=reason,
    )


def _sort_sections(sections: Sequence[DigestSection]) -> tuple[DigestSection, ...]:
    """Sort sections by deterministic DigestSectionKind order."""
    order = {kind.value: idx for idx, kind in enumerate(DigestSectionKind)}
    return tuple(sorted(sections, key=lambda s: order.get(s.section_kind.value, 999)))


def _iso_str(dt: datetime) -> str:
    """ISO format string for a datetime."""
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")


def build_research_digest(
    config: DigestConfig | None = None,
    observation_state: str | None = None,
    review_state: str | None = None,
    index_state: str | None = None,
    search_state: str | None = None,
    bundle_state: str | None = None,
    chronicle_state: str | None = None,
    observation_count: int = 0,
    review_count: int = 0,
    index_count: int = 0,
    search_count: int = 0,
    bundle_count: int = 0,
    chronicle_count: int = 0,
    observation_reason_codes: tuple[str, ...] = (),
    review_reason_codes: tuple[str, ...] = (),
    index_reason_codes: tuple[str, ...] = (),
    search_reason_codes: tuple[str, ...] = (),
    bundle_reason_codes: tuple[str, ...] = (),
    chronicle_reason_codes: tuple[str, ...] = (),
    next_review_notes: str = "",
) -> ResearchDigest:
    """Build a ResearchDigest from MVP-10–MVP-15 artifact states.

    Fail-closed priority order (from SPEC-017):
    1. EMPTY_DIGEST
    2. INVALID_CONFIG
    3. UNSAFE_CONFIG
    4–9. MISSING_* per artifact type
    10–15. INVALID_* per artifact type
    16. UNSAFE_DIGEST_CONTENT
    17. DIGEST_ERROR
    """
    if config is None:
        config = DigestConfig()

    generated_at = config.generated_at
    if generated_at is None:
        generated_at = datetime.now(timezone.utc)
    elif generated_at.tzinfo is None:
        raise ValueError("config.generated_at must be timezone-aware")

    digest_id = f"digest:{config.version}:{_iso_str(generated_at)}"

    # 1. EMPTY_DIGEST
    states = (
        observation_state,
        review_state,
        index_state,
        search_state,
        bundle_state,
        chronicle_state,
    )
    counts = (
        observation_count,
        review_count,
        index_count,
        search_count,
        bundle_count,
        chronicle_count,
    )
    if all(s is None for s in states) and all(c == 0 for c in counts):
        digest = ResearchDigest.blocked("EMPTY_DIGEST", generated_at=generated_at)
        # Override digest_id so empty digest is still deterministic
        object.__setattr__(digest, "digest_id", digest_id)
        object.__setattr__(digest, "config", config)
        return digest

    # 2. INVALID_CONFIG
    if not isinstance(config, DigestConfig):
        digest = ResearchDigest.blocked("INVALID_CONFIG", generated_at=generated_at)
        object.__setattr__(digest, "digest_id", digest_id)
        object.__setattr__(digest, "config", config)
        return digest

    # 3. UNSAFE_CONFIG — check before other validation so unsafe values are
    # reported as UNSAFE_CONFIG, not INVALID_CONFIG.
    unsafe_attrs = (
        "live_trading_enabled",
        "real_orders_enabled",
        "leverage_enabled",
        "shorting_enabled",
    )
    if config.dry_run is not True or any(
        getattr(config, attr, False) for attr in unsafe_attrs
    ):
        digest = ResearchDigest.blocked("UNSAFE_CONFIG", generated_at=generated_at)
        object.__setattr__(digest, "digest_id", digest_id)
        object.__setattr__(digest, "config", config)
        return digest

    # Additional config validation
    if (
        not isinstance(config.version, str)
        or not config.version.strip()
        or config.output_format not in _VALID_OUTPUT_FORMATS
        or not isinstance(config.stale_threshold_minutes, int)
        or config.stale_threshold_minutes < 1
    ):
        digest = ResearchDigest.blocked("INVALID_CONFIG", generated_at=generated_at)
        object.__setattr__(digest, "digest_id", digest_id)
        object.__setattr__(digest, "config", config)
        return digest

    safety_flags = build_digest_safety_flags(config)

    # 4–9. MISSING_* checks
    kind_state_map: list[tuple[DigestSectionKind, str | None, str]] = [
        (DigestSectionKind.OBSERVATION, observation_state, "MISSING_OBSERVATION"),
        (DigestSectionKind.REVIEW, review_state, "MISSING_REVIEW"),
        (DigestSectionKind.INDEX, index_state, "MISSING_INDEX"),
        (DigestSectionKind.SEARCH, search_state, "MISSING_SEARCH"),
        (DigestSectionKind.BUNDLE, bundle_state, "MISSING_BUNDLE"),
        (DigestSectionKind.CHRONICLE, chronicle_state, "MISSING_CHRONICLE"),
    ]

    for section_kind, raw_state, missing_reason in kind_state_map:
        if raw_state is None:
            digest = ResearchDigest.blocked(missing_reason, generated_at=generated_at)
            object.__setattr__(digest, "digest_id", digest_id)
            object.__setattr__(digest, "config", config)
            object.__setattr__(digest, "safety_flags", safety_flags)
            return digest

    # 10–15. INVALID_* checks
    kind_invalid_map: list[tuple[DigestSectionKind, str | None, str]] = [
        (DigestSectionKind.OBSERVATION, observation_state, "INVALID_OBSERVATION"),
        (DigestSectionKind.REVIEW, review_state, "INVALID_REVIEW"),
        (DigestSectionKind.INDEX, index_state, "INVALID_INDEX"),
        (DigestSectionKind.SEARCH, search_state, "INVALID_SEARCH"),
        (DigestSectionKind.BUNDLE, bundle_state, "INVALID_BUNDLE"),
        (DigestSectionKind.CHRONICLE, chronicle_state, "INVALID_CHRONICLE"),
    ]

    for section_kind, raw_state, invalid_reason in kind_invalid_map:
        if not _is_recognized_state(raw_state):
            digest = ResearchDigest.blocked(invalid_reason, generated_at=generated_at)
            object.__setattr__(digest, "digest_id", digest_id)
            object.__setattr__(digest, "config", config)
            object.__setattr__(digest, "safety_flags", safety_flags)
            return digest

    # 16. UNSAFE_DIGEST_CONTENT
    if has_unsafe_digest_content(next_review_notes, None):
        digest = ResearchDigest.blocked("UNSAFE_DIGEST_CONTENT", generated_at=generated_at)
        object.__setattr__(digest, "digest_id", digest_id)
        object.__setattr__(digest, "config", config)
        object.__setattr__(digest, "safety_flags", safety_flags)
        return digest

    # Build sections
    section_params: list[
        tuple[
            DigestSectionKind,
            str | None,
            int,
            tuple[str, ...],
        ]
    ] = [
        (
            DigestSectionKind.OBSERVATION,
            observation_state,
            observation_count,
            observation_reason_codes,
        ),
        (
            DigestSectionKind.REVIEW,
            review_state,
            review_count,
            review_reason_codes,
        ),
        (DigestSectionKind.INDEX, index_state, index_count, index_reason_codes),
        (DigestSectionKind.SEARCH, search_state, search_count, search_reason_codes),
        (DigestSectionKind.BUNDLE, bundle_state, bundle_count, bundle_reason_codes),
        (
            DigestSectionKind.CHRONICLE,
            chronicle_state,
            chronicle_count,
            chronicle_reason_codes,
        ),
    ]

    sections: list[DigestSection] = []
    for section_kind, raw_state, count, reason_codes in section_params:
        state_normalized = _normalize_state(raw_state)
        ready_count = 1 if state_normalized == "READY" else 0
        blocked_count = 1 if state_normalized in ("BLOCKED", "UNKNOWN", "DISABLED") else 0
        missing_count = 0 if raw_state is not None else 1
        section = build_digest_section(
            section_kind=section_kind,
            artifact_state=raw_state,
            artifact_count=count,
            blocked_count=blocked_count,
            ready_count=ready_count,
            missing_count=missing_count,
            reason_codes=reason_codes,
        )
        sections.append(section)

    sorted_sections = _sort_sections(sections)

    # Build summary and data quality
    summary = build_digest_summary(
        sorted_sections,
        include_next_review_notes=config.include_next_review_notes,
        include_unresolved_blockers=config.include_unresolved_blockers,
    )
    data_quality = build_digest_data_quality(sorted_sections)

    # Overall state
    if summary.cross_layer_ready:
        state = DigestState.READY
    elif summary.blocked_sections > 0:
        state = DigestState.BLOCKED
    elif summary.missing_sections > 0:
        state = DigestState.UNKNOWN
    else:
        state = DigestState.BLOCKED

    reason_codes: tuple[str, ...] = ()
    if state is DigestState.BLOCKED or state is DigestState.UNKNOWN:
        # Collect unique blocking reason codes from sections, sorted for determinism.
        unique_reasons = set()
        for section in sorted_sections:
            for rc in section.reason_codes:
                if _is_blocking_reason(rc):
                    unique_reasons.add(rc)
        reason_codes = tuple(sorted(unique_reasons))

    # Override next_review_notes if caller supplied one, after validating safety.
    final_next_review_notes = summary.next_review_notes
    if next_review_notes:
        if has_unsafe_digest_content(next_review_notes, None):
            digest = ResearchDigest.blocked("UNSAFE_DIGEST_CONTENT", generated_at=generated_at)
            object.__setattr__(digest, "digest_id", digest_id)
            object.__setattr__(digest, "config", config)
            object.__setattr__(digest, "safety_flags", safety_flags)
            return digest
        final_next_review_notes = next_review_notes

    return ResearchDigest(
        digest_id=digest_id,
        generated_at=generated_at,
        version=DIGEST_VERSION,
        state=state,
        sections=sorted_sections,
        summary=summary,
        data_quality=data_quality,
        safety_flags=safety_flags,
        config=config,
        reason_codes=reason_codes,
        next_review_notes=final_next_review_notes,
    )
