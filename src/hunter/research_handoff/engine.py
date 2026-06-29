"""Engine for hunter.research_handoff package.

MVP-18 — Local Research Handoff Packet.

All functions are pure: no file I/O, no network, no database, no side effects.
File references and metadata strings are local strings only and are never
traversed, opened, followed, validated, or executed.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from hunter.research_handoff.models import (
    HANDOFF_BLOCKING_REASON_CODES,
    HANDOFF_REASON_CODES,
    HANDOFF_VERSION,
    FORBIDDEN_HANDOFF_TERMS,
    HandoffConfig,
    HandoffDataQuality,
    HandoffPacketKind,
    HandoffSafetyFlags,
    HandoffSection,
    HandoffState,
    HandoffSummary,
    ResearchHandoffPacket,
    _check_unsafe_mapping,
    _has_unsafe_handoff_content,
)


_VALID_OUTPUT_FORMATS = ("json", "markdown", "both")
_VALID_ARTIFACT_STATES = ("DISABLED", "READY", "BLOCKED", "UNKNOWN")

# Default local references for contractor orientation. These strings are never
# opened, traversed, followed, validated, or executed.
_DEFAULT_LOCAL_REFERENCES: dict[HandoffPacketKind, str] = {
    HandoffPacketKind.OBSERVATION: "data/observation/latest_observation_report.json",
    HandoffPacketKind.REVIEW: "data/review/latest_review_audit_record.json",
    HandoffPacketKind.INDEX: "data/review_index/latest_review_index.json",
    HandoffPacketKind.SEARCH: "data/review_search/latest_search_result.json",
    HandoffPacketKind.BUNDLE: "data/research_bundle/latest_research_bundle.json",
    HandoffPacketKind.CHRONICLE: "data/chronicle/latest_research_chronicle.json",
    HandoffPacketKind.DIGEST: "data/research_digest/latest_research_digest.json",
    HandoffPacketKind.QUALITY_GATE: "data/research_quality_gate/latest_research_quality_gate.json",
}

# Map section kinds to the attribute/key names used by the corresponding MVP artifact.
_STATE_ATTR_NAMES: dict[HandoffPacketKind, tuple[str, ...]] = {
    HandoffPacketKind.OBSERVATION: ("state",),
    HandoffPacketKind.REVIEW: ("state",),
    HandoffPacketKind.INDEX: ("index_state", "state"),
    HandoffPacketKind.SEARCH: ("search_state", "state"),
    HandoffPacketKind.BUNDLE: ("state",),
    HandoffPacketKind.CHRONICLE: ("state",),
    HandoffPacketKind.DIGEST: ("state",),
    HandoffPacketKind.QUALITY_GATE: ("state",),
}


# Title for each section kind.
def _section_title(section_kind: HandoffPacketKind) -> str:
    return section_kind.value.replace("_", " ").title()


def has_unsafe_handoff_content(
    text: str | None, metadata: Mapping[str, Any] | None = None
) -> bool:
    """Return True if text or metadata contain forbidden handoff terms.

    Does not open, traverse, validate, follow, or execute file references.
    """
    if text is not None and _has_unsafe_handoff_content(text):
        return True
    if metadata is not None and _check_unsafe_mapping(metadata):
        return True
    return False


def build_handoff_safety_flags(
    config: HandoffConfig | None = None,
) -> HandoffSafetyFlags:
    """Build safety flags from config.

    If config is unsafe, raises ValueError (fail-closed).
    """
    if config is None:
        return HandoffSafetyFlags()

    return HandoffSafetyFlags(
        dry_run=config.dry_run,
        live_trading_enabled=config.live_trading_enabled,
        real_orders_enabled=config.real_orders_enabled,
        leverage_enabled=config.leverage_enabled,
        shorting_enabled=config.shorting_enabled,
    )


def _normalize_state(raw: str | None) -> str:
    """Normalize artifact state string to a valid artifact state."""
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
    return upper in HANDOFF_BLOCKING_REASON_CODES


def _get_attr_or_item(obj: Any, names: tuple[str, ...], default: Any = None) -> Any:
    """Get a value from an object or mapping, trying names in order."""
    if isinstance(obj, Mapping):
        for name in names:
            if name in obj:
                return obj[name]
        return default
    for name in names:
        if hasattr(obj, name):
            return getattr(obj, name)
    return default


def _artifact_state(artifact: Any, section_kind: HandoffPacketKind) -> str | None:
    """Extract normalized artifact state, supporting objects and dicts."""
    if artifact is None:
        return None
    names = _STATE_ATTR_NAMES.get(section_kind, ("state",))
    raw = _get_attr_or_item(artifact, names)
    if raw is None:
        return None
    normalized = _normalize_state(raw)
    return normalized if _is_recognized_state(raw) else normalized


def _artifact_safety_flags(artifact: Any) -> Any:
    """Extract safety_flags from artifact, supporting objects and dicts."""
    return _get_attr_or_item(artifact, ("safety_flags",))


def _artifact_reason_codes(artifact: Any) -> tuple[str, ...]:
    """Extract reason_codes from artifact, supporting objects and dicts."""
    value = _get_attr_or_item(artifact, ("reason_codes",))
    if value is None:
        return ()
    if isinstance(value, (tuple, list)):
        return tuple(str(x) for x in value if x)
    return ()


def _artifact_generated_at(artifact: Any) -> datetime | None:
    """Extract generated_at from artifact, supporting objects and dicts."""
    value = _get_attr_or_item(artifact, ("generated_at",))
    if isinstance(value, datetime):
        return value
    return None


def _artifact_summary_text(artifact: Any) -> str | None:
    """Extract a short summary text from artifact, supporting objects and dicts."""
    value = _get_attr_or_item(artifact, ("summary_text", "summary", "handoff_notes", "notes"))
    if isinstance(value, str):
        return value
    return None


def _is_unsafe_safety_flags(safety_flags: Any) -> bool:
    """Return True if artifact safety flags indicate any unsafe flag is enabled."""
    if safety_flags is None:
        return False
    unsafe_attrs = (
        "live_trading_enabled",
        "real_orders_enabled",
        "leverage_enabled",
        "shorting_enabled",
        "digest_feedback_into_execution",
        "cross_layer_feedback_into_execution",
        "quality_gate_feedback_into_execution",
        "report_feedback_into_execution",
        "operator_feedback_into_execution",
        "index_feedback_into_execution",
        "search_feedback_into_execution",
        "bundle_feedback_into_execution",
        "chronicle_feedback_into_execution",
        "handoff_feedback_into_execution",
    )
    for attr in unsafe_attrs:
        raw = _get_attr_or_item(safety_flags, (attr,))
        if raw is True:
            return True
    raw_dry_run = _get_attr_or_item(safety_flags, ("dry_run",))
    if raw_dry_run is False:
        return True
    return False


def _has_unresolved_blockers(reason_codes: tuple[str, ...]) -> bool:
    """Return True if reason_codes contain any blocking reason."""
    return any(_is_blocking_reason(rc) for rc in reason_codes)


def _missing_reason_code(section_kind: HandoffPacketKind) -> str:
    """Return MISSING_* reason code for a section kind."""
    return f"MISSING_{section_kind.name}"


def _blocked_reason_code(section_kind: HandoffPacketKind) -> str:
    """Return BLOCKED_* reason code for a section kind."""
    return f"BLOCKED_{section_kind.name}"


def _unknown_reason_code(section_kind: HandoffPacketKind) -> str:
    """Return UNKNOWN_* reason code for a section kind."""
    return f"UNKNOWN_{section_kind.name}"


def _is_stale(
    generated_at: datetime | None,
    reference_time: datetime,
    max_staleness_minutes: int,
) -> bool:
    """Return True if generated_at is older than max_staleness_minutes."""
    if generated_at is None:
        return False
    if generated_at.tzinfo is None or reference_time.tzinfo is None:
        return False
    try:
        delta = reference_time - generated_at
        return delta.total_seconds() > max_staleness_minutes * 60
    except Exception:
        return False


def _section_summary_text(
    section_kind: HandoffPacketKind,
    state: HandoffState,
    artifact: Any | None,
    reason_codes: tuple[str, ...],
) -> str:
    """Generate a short human-readable summary for a section."""
    title = _section_title(section_kind)
    artifact_summary = _artifact_summary_text(artifact)
    if artifact_summary:
        return f"{title}: {state.value.upper()}. {artifact_summary}"
    if reason_codes:
        return f"{title}: {state.value.upper()}. Reasons: {', '.join(reason_codes)}."
    return f"{title}: {state.value.upper()}."


def build_handoff_section(
    section_kind: HandoffPacketKind,
    artifact: Any | None = None,
    config: HandoffConfig | None = None,
    reference_time: datetime | None = None,
) -> HandoffSection:
    """Build a HandoffSection for a single artifact category.

    Supports duck-typed objects and Mapping[str, Any] dicts.
    """
    if config is None:
        config = HandoffConfig()

    required = section_kind in config.required_sections
    local_reference = _DEFAULT_LOCAL_REFERENCES.get(section_kind, "")
    title = _section_title(section_kind)

    if artifact is None:
        if required:
            return HandoffSection(
                section_kind=section_kind,
                title=title,
                state=HandoffState.BLOCK.value,
                summary_text=f"{title}: Required section is missing.",
                local_reference=local_reference,
                reason_codes=(_missing_reason_code(section_kind),),
            )
        return HandoffSection(
            section_kind=section_kind,
            title=title,
            state=HandoffState.READY.value,
            summary_text=f"{title}: Section not required and not provided.",
            local_reference=local_reference,
        )

    state = _artifact_state(artifact, section_kind)
    reason_codes: list[str] = []
    notes: list[str] = []
    section_state = HandoffState.UNKNOWN

    if state == "READY":
        section_state = HandoffState.READY
        notes.append(f"{title} artifact is READY.")
    elif state == "BLOCKED":
        section_state = HandoffState.BLOCK
        reason_codes.append(_blocked_reason_code(section_kind))
        notes.append(f"{title} artifact is BLOCKED.")
    elif state in ("UNKNOWN", "DISABLED"):
        if config.block_on_unknown:
            section_state = HandoffState.BLOCK
        else:
            section_state = HandoffState.WARN
        reason_codes.append(_unknown_reason_code(section_kind))
        notes.append(f"{title} artifact is {state}.")
    else:
        section_state = HandoffState.UNKNOWN
        reason_codes.append(_unknown_reason_code(section_kind))
        notes.append(f"{title} artifact state is unrecognized.")

    safety_flags = _artifact_safety_flags(artifact)
    if _is_unsafe_safety_flags(safety_flags):
        section_state = HandoffState.BLOCK
        if "UNSAFE_ARTIFACT_FLAGS" not in reason_codes:
            reason_codes.append("UNSAFE_ARTIFACT_FLAGS")
        notes.append("Artifact safety flags indicate unsafe configuration.")

    artifact_reason_codes = _artifact_reason_codes(artifact)
    if _has_unresolved_blockers(artifact_reason_codes):
        section_state = HandoffState.BLOCK
        if "UNRESOLVED_BLOCKERS" not in reason_codes:
            reason_codes.append("UNRESOLVED_BLOCKERS")
        notes.append("Artifact contains unresolved blocking reason codes.")

    generated_at = _artifact_generated_at(artifact)
    if reference_time is None:
        reference_time = datetime.now(timezone.utc)
    if _is_stale(generated_at, reference_time, config.max_staleness_minutes):
        if section_state == HandoffState.READY:
            section_state = HandoffState.WARN
        if "STALE_ARTIFACT" not in reason_codes:
            reason_codes.append("STALE_ARTIFACT")
        notes.append("Artifact is older than configured staleness threshold.")

    summary_text = _section_summary_text(
        section_kind,
        section_state,
        artifact,
        tuple(reason_codes),
    )

    return HandoffSection(
        section_kind=section_kind,
        title=title,
        state=section_state.value,
        summary_text=summary_text,
        local_reference=local_reference,
        reason_codes=tuple(reason_codes),
        metadata={"notes": " ".join(notes)} if notes else {},
    )


def _generate_handoff_notes(summary: HandoffSummary) -> str:
    """Generate human-readable handoff notes from summary."""
    state = summary.handoff_state
    if state == "READY":
        return (
            "All required artifact categories are present and ready. Handoff packet "
            "is complete for human audit and contractor handoff. This is not trade "
            "approval, not execution readiness, not strategy readiness, not "
            "release approval, and not transaction permission."
        )
    if state == "WARN":
        return (
            "Handoff packet is usable for human audit but has non-blocking issues. "
            "Review warnings before handoff. This is not trade approval, not "
            "execution readiness, not strategy readiness, not release "
            "approval, and not transaction permission."
        )
    if state == "BLOCK":
        return (
            "Handoff packet is not ready for human handoff. Resolve blockers before "
            "handoff. This is not trade approval, not execution readiness, not "
            "strategy readiness, not release approval, and not "
            "transaction permission."
        )
    return (
        "Insufficient or invalid information to build handoff packet. Provide "
        "required artifact inputs."
    )


def _quality_gate_verdict(quality_gate_artifact: Any | None) -> str:
    """Extract quality gate verdict from artifact, supporting objects and dicts."""
    if quality_gate_artifact is None:
        return "UNKNOWN"
    value = _get_attr_or_item(quality_gate_artifact, ("verdict",))
    if value is None:
        return "UNKNOWN"
    if hasattr(value, "value"):
        value = value.value
    if not isinstance(value, str):
        return "UNKNOWN"
    upper = value.strip().upper()
    if upper in ("PASS", "WARN", "BLOCK", "UNKNOWN"):
        return upper
    return "UNKNOWN"


def build_handoff_summary(
    sections: Sequence[HandoffSection],
    quality_gate_artifact: Any | None = None,
    *,
    include_handoff_notes: bool = True,
) -> HandoffSummary:
    """Build a HandoffSummary from a sequence of sections."""
    total_sections = len(sections)
    ready_sections = sum(1 for s in sections if s.state == "READY")
    warn_sections = sum(1 for s in sections if s.state == "WARN")
    block_sections = sum(1 for s in sections if s.state == "BLOCK")
    unknown_sections = sum(1 for s in sections if s.state == "UNKNOWN")

    reason_code_counts = Counter[str]()
    for section in sections:
        for rc in section.reason_codes:
            reason_code_counts[rc] += 1

    if block_sections > 0:
        handoff_state = HandoffState.BLOCK.value
    elif unknown_sections > 0:
        handoff_state = HandoffState.UNKNOWN.value
    elif warn_sections > 0:
        handoff_state = HandoffState.WARN.value
    elif total_sections > 0:
        handoff_state = HandoffState.READY.value
    else:
        handoff_state = HandoffState.UNKNOWN.value

    quality_gate_verdict = _quality_gate_verdict(quality_gate_artifact)

    handoff_notes = ""
    if include_handoff_notes:
        handoff_notes = _generate_handoff_notes(
            HandoffSummary(
                total_sections=total_sections,
                ready_sections=ready_sections,
                warn_sections=warn_sections,
                block_sections=block_sections,
                unknown_sections=unknown_sections,
                quality_gate_verdict=quality_gate_verdict,
                handoff_state=handoff_state,
            )
        )

    return HandoffSummary(
        total_sections=total_sections,
        ready_sections=ready_sections,
        warn_sections=warn_sections,
        block_sections=block_sections,
        unknown_sections=unknown_sections,
        quality_gate_verdict=quality_gate_verdict,
        handoff_state=handoff_state,
        reason_code_counts=dict(sorted(reason_code_counts.items())),
        handoff_notes=handoff_notes,
    )


def build_handoff_data_quality(sections: Sequence[HandoffSection]) -> HandoffDataQuality:
    """Build HandoffDataQuality from a sequence of sections."""
    total_sections = len(sections)
    ready_sections = sum(1 for s in sections if s.state == "READY")
    missing_count = sum(
        1 for s in sections
        if any(rc.startswith("MISSING_") for rc in s.reason_codes)
    )
    stale_count = sum(
        1 for s in sections
        if any(rc == "STALE_ARTIFACT" for rc in s.reason_codes)
    )
    blocked_count = sum(1 for s in sections if s.state == "BLOCK")
    unknown_count = sum(1 for s in sections if s.state == "UNKNOWN")

    completeness_pct = (ready_sections / total_sections * 100.0) if total_sections > 0 else 0.0
    ready_pct = completeness_pct

    reason = ""
    if blocked_count > 0:
        for section in sections:
            if section.reason_codes:
                reason = section.reason_codes[0]
                break

    return HandoffDataQuality(
        completeness_pct=completeness_pct,
        ready_pct=ready_pct,
        missing_count=missing_count,
        stale_count=stale_count,
        blocked_count=blocked_count,
        unknown_count=unknown_count,
        total_sections=total_sections,
        reason=reason,
    )


def _sort_sections(sections: Sequence[HandoffSection]) -> tuple[HandoffSection, ...]:
    """Sort sections by deterministic HandoffPacketKind order."""
    order = {kind.value: idx for idx, kind in enumerate(HandoffPacketKind)}
    return tuple(sorted(sections, key=lambda s: order.get(s.section_kind.value, 999)))


def _iso_str(dt: datetime) -> str:
    """ISO format string for a datetime."""
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")


def build_research_handoff_packet(
    config: HandoffConfig | None = None,
    observation_artifact: Any | None = None,
    review_artifact: Any | None = None,
    index_artifact: Any | None = None,
    search_artifact: Any | None = None,
    bundle_artifact: Any | None = None,
    chronicle_artifact: Any | None = None,
    digest_artifact: Any | None = None,
    quality_gate_artifact: Any | None = None,
    reference_time: datetime | None = None,
) -> ResearchHandoffPacket:
    """Build a ResearchHandoffPacket from MVP-10–MVP-17 artifact objects or dicts.

    Fail-closed priority order (from SPEC-019):
    1. EMPTY_PACKET
    2. INVALID_CONFIG
    3. UNSAFE_CONFIG
    4–11. MISSING_* per required section kind
    12–19. BLOCKED_* per artifact state
    20–27. UNKNOWN_* per artifact state
    28. UNSAFE_ARTIFACT_FLAGS
    29. UNRESOLVED_BLOCKERS
    30. STALE_ARTIFACT
    31. UNSAFE_PACKET_CONTENT
    32. HANDOFF_ERROR
    """
    if config is None:
        config = HandoffConfig()

    generated_at = config.generated_at
    if generated_at is None:
        generated_at = datetime.now(timezone.utc)
    elif generated_at.tzinfo is None:
        raise ValueError("config.generated_at must be timezone-aware")

    packet_id = f"handoff:{config.version}:{_iso_str(generated_at)}"

    # 2. INVALID_CONFIG
    if not isinstance(config, HandoffConfig):
        packet = ResearchHandoffPacket.blocked("INVALID_CONFIG", generated_at=generated_at)
        object.__setattr__(packet, "packet_id", packet_id)
        object.__setattr__(packet, "config", config)
        return packet

    # 3. UNSAFE_CONFIG
    unsafe_attrs = (
        "live_trading_enabled",
        "real_orders_enabled",
        "leverage_enabled",
        "shorting_enabled",
    )
    if config.dry_run is not True or any(getattr(config, attr, False) for attr in unsafe_attrs):
        packet = ResearchHandoffPacket.blocked("UNSAFE_CONFIG", generated_at=generated_at)
        object.__setattr__(packet, "packet_id", packet_id)
        object.__setattr__(packet, "config", config)
        return packet

    # Additional config validation
    if (
        not isinstance(config.version, str)
        or not config.version.strip()
        or config.output_format not in _VALID_OUTPUT_FORMATS
        or not isinstance(config.max_staleness_minutes, int)
        or config.max_staleness_minutes < 1
    ):
        packet = ResearchHandoffPacket.blocked("INVALID_CONFIG", generated_at=generated_at)
        object.__setattr__(packet, "packet_id", packet_id)
        object.__setattr__(packet, "config", config)
        return packet

    safety_flags = build_handoff_safety_flags(config)

    artifacts: dict[HandoffPacketKind, Any] = {
        HandoffPacketKind.OBSERVATION: observation_artifact,
        HandoffPacketKind.REVIEW: review_artifact,
        HandoffPacketKind.INDEX: index_artifact,
        HandoffPacketKind.SEARCH: search_artifact,
        HandoffPacketKind.BUNDLE: bundle_artifact,
        HandoffPacketKind.CHRONICLE: chronicle_artifact,
        HandoffPacketKind.DIGEST: digest_artifact,
        HandoffPacketKind.QUALITY_GATE: quality_gate_artifact,
    }

    provided_artifacts = {k: v for k, v in artifacts.items() if v is not None}

    # 1. EMPTY_PACKET
    if not provided_artifacts and not config.required_sections:
        packet = ResearchHandoffPacket.blocked("EMPTY_PACKET", generated_at=generated_at)
        object.__setattr__(packet, "packet_id", packet_id)
        object.__setattr__(packet, "config", config)
        object.__setattr__(packet, "safety_flags", safety_flags)
        return packet

    if reference_time is None:
        reference_time = generated_at

    # Build per-artifact sections.
    sections: list[HandoffSection] = []
    for section_kind in HandoffPacketKind:
        artifact = artifacts.get(section_kind)
        section = build_handoff_section(
            section_kind=section_kind,
            artifact=artifact,
            config=config,
            reference_time=reference_time,
        )
        sections.append(section)

    sorted_sections = _sort_sections(sections)

    # Build summary and data quality.
    summary = build_handoff_summary(
        sorted_sections,
        quality_gate_artifact=quality_gate_artifact,
        include_handoff_notes=config.include_handoff_notes,
    )
    data_quality = build_handoff_data_quality(sorted_sections)

    # Overall handoff state.
    handoff_state = HandoffState(summary.handoff_state.lower())

    # Collect unique blocking reason codes from sections, sorted for determinism.
    unique_reasons: set[str] = set()
    for section in sorted_sections:
        for rc in section.reason_codes:
            if _is_blocking_reason(rc):
                unique_reasons.add(rc)
    reason_codes = tuple(sorted(unique_reasons))

    handoff_notes = summary.handoff_notes

    # 31. UNSAFE_PACKET_CONTENT
    if has_unsafe_handoff_content(handoff_notes, None):
        packet = ResearchHandoffPacket.blocked("UNSAFE_PACKET_CONTENT", generated_at=generated_at)
        object.__setattr__(packet, "packet_id", packet_id)
        object.__setattr__(packet, "config", config)
        object.__setattr__(packet, "safety_flags", safety_flags)
        return packet

    return ResearchHandoffPacket(
        packet_id=packet_id,
        generated_at=generated_at,
        version=HANDOFF_VERSION,
        handoff_state=handoff_state,
        sections=sorted_sections,
        summary=summary,
        data_quality=data_quality,
        safety_flags=safety_flags,
        config=config,
        reason_codes=reason_codes,
        handoff_notes=handoff_notes,
    )
