"""Engine for hunter.research_quality_gate package.

MVP-17 — Local Research Quality Gate / Audit Readiness.

All functions are pure: no file I/O, no network, no database, no side effects.
File references and metadata strings are local strings only and are never
traversed, opened, followed, validated, or executed.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from hunter.research_quality_gate.models import (
    QUALITY_GATE_BLOCKING_REASON_CODES,
    QUALITY_GATE_REASON_CODES,
    QUALITY_GATE_VERSION,
    FORBIDDEN_QUALITY_GATE_TERMS,
    QualityGateCheck,
    QualityGateCheckKind,
    QualityGateConfig,
    QualityGateDataQuality,
    QualityGateSafetyFlags,
    QualityGateState,
    QualityGateSummary,
    QualityGateVerdict,
    ResearchQualityGate,
    _check_unsafe_mapping,
    _has_unsafe_quality_gate_content,
)


_VALID_OUTPUT_FORMATS = ("json", "markdown", "both")
_VALID_ARTIFACT_STATES = ("DISABLED", "READY", "BLOCKED", "UNKNOWN")
_BLOCKING_REASON_PREFIXES = ("MISSING_", "BLOCKED_", "UNKNOWN_", "UNSAFE_")

# Map check kinds to the attribute/key names used by the corresponding MVP artifact.
_STATE_ATTR_NAMES: dict[QualityGateCheckKind, tuple[str, ...]] = {
    QualityGateCheckKind.OBSERVATION: ("state",),
    QualityGateCheckKind.REVIEW: ("state",),
    QualityGateCheckKind.INDEX: ("index_state", "state"),
    QualityGateCheckKind.SEARCH: ("search_state", "state"),
    QualityGateCheckKind.BUNDLE: ("state",),
    QualityGateCheckKind.CHRONICLE: ("state",),
    QualityGateCheckKind.DIGEST: ("state",),
}


def has_unsafe_quality_gate_content(
    notes: str | None, metadata: Mapping[str, Any] | None = None
) -> bool:
    """Return True if notes or metadata contain forbidden quality gate terms.

    Does not open, traverse, validate, follow, or execute file references.
    """
    if notes is not None and _has_unsafe_quality_gate_content(notes):
        return True
    if metadata is not None and _check_unsafe_mapping(metadata):
        return True
    return False


def build_quality_gate_safety_flags(
    config: QualityGateConfig | None = None,
) -> QualityGateSafetyFlags:
    """Build safety flags from config.

    If config is unsafe, raises ValueError (fail-closed).
    """
    if config is None:
        return QualityGateSafetyFlags()

    # Config validation already enforces dry_run=True and unsafe flags=False.
    # Safety flag construction validates the same invariants in __post_init__.
    return QualityGateSafetyFlags(
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
    if upper.startswith(_BLOCKING_REASON_PREFIXES):
        return True
    if upper in {
        "QUALITY_GATE_ERROR",
        "EMPTY_GATE",
        "INVALID_CONFIG",
        "UNSAFE_CONFIG",
    }:
        return True
    return False


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


def _artifact_state(artifact: Any, check_kind: QualityGateCheckKind) -> str | None:
    """Extract normalized artifact state, supporting objects and dicts."""
    if artifact is None:
        return None
    names = _STATE_ATTR_NAMES.get(check_kind, ("state",))
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


def _missing_reason_code(check_kind: QualityGateCheckKind) -> str:
    """Return MISSING_* reason code for a check kind."""
    return f"MISSING_{check_kind.name}"


def _blocked_reason_code(check_kind: QualityGateCheckKind) -> str:
    """Return BLOCKED_* reason code for a check kind."""
    return f"BLOCKED_{check_kind.name}"


def _unknown_reason_code(check_kind: QualityGateCheckKind) -> str:
    """Return UNKNOWN_* reason code for a check kind."""
    return f"UNKNOWN_{check_kind.name}"


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


def build_quality_gate_check(
    check_kind: QualityGateCheckKind,
    artifact: Any | None = None,
    config: QualityGateConfig | None = None,
    reference_time: datetime | None = None,
) -> QualityGateCheck:
    """Build a QualityGateCheck for a single artifact category.

    Supports duck-typed objects and Mapping[str, Any] dicts.
    """
    if config is None:
        config = QualityGateConfig()

    required = check_kind in config.required_artifact_kinds

    if artifact is None:
        if required:
            return QualityGateCheck(
                check_kind=check_kind,
                state=QualityGateState.BLOCK.value,
                reason_codes=(_missing_reason_code(check_kind),),
                notes=f"Required {check_kind.value} artifact is missing.",
            )
        return QualityGateCheck(
            check_kind=check_kind,
            state=QualityGateState.PASS.value,
            notes=f"{check_kind.value} artifact not required and not provided.",
        )

    state = _artifact_state(artifact, check_kind)
    reason_codes: list[str] = []
    notes: list[str] = []
    check_state = QualityGateState.UNKNOWN

    if state == "READY":
        check_state = QualityGateState.PASS
        notes.append(f"{check_kind.value} artifact is READY.")
    elif state == "BLOCKED":
        check_state = QualityGateState.BLOCK
        reason_codes.append(_blocked_reason_code(check_kind))
        notes.append(f"{check_kind.value} artifact is BLOCKED.")
    elif state in ("UNKNOWN", "DISABLED"):
        if config.block_on_unknown:
            check_state = QualityGateState.BLOCK
        else:
            check_state = QualityGateState.WARN
        reason_codes.append(_unknown_reason_code(check_kind))
        notes.append(f"{check_kind.value} artifact is {state}.")
    else:
        check_state = QualityGateState.UNKNOWN
        reason_codes.append(_unknown_reason_code(check_kind))
        notes.append(f"{check_kind.value} artifact state is unrecognized.")

    safety_flags = _artifact_safety_flags(artifact)
    if _is_unsafe_safety_flags(safety_flags):
        check_state = QualityGateState.BLOCK
        if "UNSAFE_ARTIFACT_FLAGS" not in reason_codes:
            reason_codes.append("UNSAFE_ARTIFACT_FLAGS")
        notes.append("Artifact safety flags indicate unsafe configuration.")

    artifact_reason_codes = _artifact_reason_codes(artifact)
    if _has_unresolved_blockers(artifact_reason_codes):
        check_state = QualityGateState.BLOCK
        if "UNRESOLVED_BLOCKERS" not in reason_codes:
            reason_codes.append("UNRESOLVED_BLOCKERS")
        notes.append("Artifact contains unresolved blocking reason codes.")

    generated_at = _artifact_generated_at(artifact)
    if reference_time is None:
        reference_time = datetime.now(timezone.utc)
    if _is_stale(generated_at, reference_time, config.max_staleness_minutes):
        if check_state == QualityGateState.PASS:
            check_state = QualityGateState.WARN
        if "STALE_ARTIFACT" not in reason_codes:
            reason_codes.append("STALE_ARTIFACT")
        notes.append("Artifact is older than configured staleness threshold.")

    return QualityGateCheck(
        check_kind=check_kind,
        state=check_state.value,
        reason_codes=tuple(reason_codes),
        notes=" ".join(notes) if notes else None,
    )


def _build_cross_cutting_check(
    artifacts: Mapping[QualityGateCheckKind, Any],
    config: QualityGateConfig,
) -> QualityGateCheck:
    """Build the cross-cutting safety check across all provided artifacts."""
    unsafe_flags_found = False
    unresolved_blockers_found = False
    notes: list[str] = []

    for check_kind, artifact in artifacts.items():
        if artifact is None:
            continue
        safety_flags = _artifact_safety_flags(artifact)
        if _is_unsafe_safety_flags(safety_flags):
            unsafe_flags_found = True
            notes.append(f"{check_kind.value} artifact has unsafe safety flags.")
        reason_codes = _artifact_reason_codes(artifact)
        if _has_unresolved_blockers(reason_codes):
            unresolved_blockers_found = True
            notes.append(f"{check_kind.value} artifact has unresolved blockers.")

    reason_codes: list[str] = []
    state = QualityGateState.PASS
    if unsafe_flags_found:
        state = QualityGateState.BLOCK
        reason_codes.append("UNSAFE_ARTIFACT_FLAGS")
    if unresolved_blockers_found:
        state = QualityGateState.BLOCK
        reason_codes.append("UNRESOLVED_BLOCKERS")

    if state == QualityGateState.PASS:
        notes.append("Cross-cutting safety check passed.")

    return QualityGateCheck(
        check_kind=QualityGateCheckKind.CROSS_CUTTING,
        state=state.value,
        reason_codes=tuple(reason_codes),
        notes=" ".join(notes) if notes else None,
    )


def _generate_handoff_notes(summary: QualityGateSummary) -> str:
    """Generate human-readable handoff notes from summary."""
    verdict = summary.verdict
    if verdict == "PASS":
        return (
            "All required artifact categories are ready. Package appears complete "
            "for human audit handoff. This is not trade approval, not execution approval, "
            "not strategy approval, not release permission, and not transaction permission."
        )
    if verdict == "WARN":
        return (
            "Package is usable for human audit but has non-blocking issues. "
            "Review warnings before handoff. This is not trade approval, not execution approval, "
            "not strategy approval, not release permission, and not transaction permission."
        )
    if verdict == "BLOCK":
        return (
            "Package is not ready for human audit handoff. Resolve blockers before handoff. "
            "This is not trade approval, not execution approval, not strategy approval, "
            "not release permission, and not transaction permission."
        )
    return (
        "Insufficient or invalid information to determine audit readiness. "
        "Provide required artifact inputs."
    )


def build_quality_gate_summary(
    checks: Sequence[QualityGateCheck],
    *,
    include_handoff_notes: bool = True,
) -> QualityGateSummary:
    """Build a QualityGateSummary from a sequence of checks."""
    total_checks = len(checks)
    pass_checks = sum(1 for c in checks if c.state == "PASS")
    warn_checks = sum(1 for c in checks if c.state == "WARN")
    block_checks = sum(1 for c in checks if c.state == "BLOCK")
    unknown_checks = sum(1 for c in checks if c.state == "UNKNOWN")
    total_artifacts = total_checks  # Each check corresponds to one artifact evaluation.
    total_blockers = block_checks + unknown_checks
    unresolved_blockers = sum(len(c.reason_codes) for c in checks if c.state == "BLOCK")

    reason_code_counts = Counter[str]()
    for check in checks:
        for rc in check.reason_codes:
            reason_code_counts[rc] += 1

    if block_checks > 0:
        verdict = QualityGateState.BLOCK.value
    elif unknown_checks > 0:
        verdict = QualityGateState.UNKNOWN.value
    elif warn_checks > 0:
        verdict = QualityGateState.WARN.value
    elif total_checks > 0:
        verdict = QualityGateState.PASS.value
    else:
        verdict = QualityGateState.UNKNOWN.value

    handoff_notes = ""
    if include_handoff_notes:
        handoff_notes = _generate_handoff_notes(
            QualityGateSummary(
                total_checks=total_checks,
                pass_checks=pass_checks,
                warn_checks=warn_checks,
                block_checks=block_checks,
                unknown_checks=unknown_checks,
                verdict=verdict,
            )
        )

    return QualityGateSummary(
        total_checks=total_checks,
        pass_checks=pass_checks,
        warn_checks=warn_checks,
        block_checks=block_checks,
        unknown_checks=unknown_checks,
        total_artifacts=total_artifacts,
        total_blockers=total_blockers,
        unresolved_blockers=unresolved_blockers,
        verdict=verdict,
        reason_code_counts=dict(sorted(reason_code_counts.items())),
        handoff_notes=handoff_notes,
    )


def build_quality_gate_data_quality(checks: Sequence[QualityGateCheck]) -> QualityGateDataQuality:
    """Build QualityGateDataQuality from a sequence of checks."""
    total_checks = len(checks)
    pass_checks = sum(1 for c in checks if c.state == "PASS")
    ready_count = pass_checks
    missing_count = sum(
        1 for c in checks
        if any(rc.startswith("MISSING_") for rc in c.reason_codes)
    )
    stale_count = sum(
        1 for c in checks
        if any(rc == "STALE_ARTIFACT" for rc in c.reason_codes)
    )
    blocked_count = sum(
        1 for c in checks if c.state == "BLOCK"
    )
    unknown_count = sum(
        1 for c in checks if c.state == "UNKNOWN"
    )

    completeness_pct = (ready_count / total_checks * 100.0) if total_checks > 0 else 0.0
    ready_pct = completeness_pct

    reason = ""
    if blocked_count > 0:
        for check in checks:
            if check.reason_codes:
                reason = check.reason_codes[0]
                break

    return QualityGateDataQuality(
        completeness_pct=completeness_pct,
        ready_pct=ready_pct,
        missing_count=missing_count,
        stale_count=stale_count,
        blocked_count=blocked_count,
        unknown_count=unknown_count,
        total_checks=total_checks,
        reason=reason,
    )


def _sort_checks(checks: Sequence[QualityGateCheck]) -> tuple[QualityGateCheck, ...]:
    """Sort checks by deterministic QualityGateCheckKind order."""
    order = {kind.value: idx for idx, kind in enumerate(QualityGateCheckKind)}
    return tuple(sorted(checks, key=lambda c: order.get(c.check_kind.value, 999)))


def _iso_str(dt: datetime) -> str:
    """ISO format string for a datetime."""
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")


def build_research_quality_gate(
    config: QualityGateConfig | None = None,
    observation_artifact: Any | None = None,
    review_artifact: Any | None = None,
    index_artifact: Any | None = None,
    search_artifact: Any | None = None,
    bundle_artifact: Any | None = None,
    chronicle_artifact: Any | None = None,
    digest_artifact: Any | None = None,
    reference_time: datetime | None = None,
) -> ResearchQualityGate:
    """Build a ResearchQualityGate from MVP-10–MVP-16 artifact objects or dicts.

    Fail-closed priority order (from SPEC-018):
    1. EMPTY_GATE
    2. INVALID_CONFIG
    3. UNSAFE_CONFIG
    4-10. MISSING_* per required artifact kind
    11-17. BLOCKED_* per artifact state
    18-24. UNKNOWN_* per artifact state
    25. UNSAFE_ARTIFACT_FLAGS
    26. UNRESOLVED_BLOCKERS
    27. STALE_ARTIFACT
    28. UNSAFE_GATE_CONTENT
    29. QUALITY_GATE_ERROR
    """
    if config is None:
        config = QualityGateConfig()

    generated_at = config.generated_at
    if generated_at is None:
        generated_at = datetime.now(timezone.utc)
    elif generated_at.tzinfo is None:
        raise ValueError("config.generated_at must be timezone-aware")

    gate_id = f"quality_gate:{config.version}:{_iso_str(generated_at)}"

    # 2. INVALID_CONFIG
    if not isinstance(config, QualityGateConfig):
        gate = ResearchQualityGate.blocked("INVALID_CONFIG", generated_at=generated_at)
        object.__setattr__(gate, "gate_id", gate_id)
        object.__setattr__(gate, "config", config)
        return gate

    # 3. UNSAFE_CONFIG
    unsafe_attrs = (
        "live_trading_enabled",
        "real_orders_enabled",
        "leverage_enabled",
        "shorting_enabled",
    )
    if config.dry_run is not True or any(getattr(config, attr, False) for attr in unsafe_attrs):
        gate = ResearchQualityGate.blocked("UNSAFE_CONFIG", generated_at=generated_at)
        object.__setattr__(gate, "gate_id", gate_id)
        object.__setattr__(gate, "config", config)
        return gate

    # Additional config validation
    if (
        not isinstance(config.version, str)
        or not config.version.strip()
        or config.output_format not in _VALID_OUTPUT_FORMATS
        or not isinstance(config.max_staleness_minutes, int)
        or config.max_staleness_minutes < 1
    ):
        gate = ResearchQualityGate.blocked("INVALID_CONFIG", generated_at=generated_at)
        object.__setattr__(gate, "gate_id", gate_id)
        object.__setattr__(gate, "config", config)
        return gate

    safety_flags = build_quality_gate_safety_flags(config)

    artifacts: dict[QualityGateCheckKind, Any] = {
        QualityGateCheckKind.OBSERVATION: observation_artifact,
        QualityGateCheckKind.REVIEW: review_artifact,
        QualityGateCheckKind.INDEX: index_artifact,
        QualityGateCheckKind.SEARCH: search_artifact,
        QualityGateCheckKind.BUNDLE: bundle_artifact,
        QualityGateCheckKind.CHRONICLE: chronicle_artifact,
        QualityGateCheckKind.DIGEST: digest_artifact,
    }

    provided_artifacts = {k: v for k, v in artifacts.items() if v is not None}

    # 1. EMPTY_GATE
    if not provided_artifacts and not config.required_artifact_kinds:
        gate = ResearchQualityGate.blocked("EMPTY_GATE", generated_at=generated_at)
        object.__setattr__(gate, "gate_id", gate_id)
        object.__setattr__(gate, "config", config)
        object.__setattr__(gate, "safety_flags", safety_flags)
        return gate

    if reference_time is None:
        reference_time = generated_at

    # Build per-artifact checks.
    checks: list[QualityGateCheck] = []
    for check_kind in QualityGateCheckKind:
        if check_kind is QualityGateCheckKind.CROSS_CUTTING:
            continue
        artifact = artifacts.get(check_kind)
        check = build_quality_gate_check(
            check_kind=check_kind,
            artifact=artifact,
            config=config,
            reference_time=reference_time,
        )
        checks.append(check)

    # Cross-cutting check.
    cross_cutting = _build_cross_cutting_check(artifacts, config)
    checks.append(cross_cutting)

    sorted_checks = _sort_checks(checks)

    # Build summary and data quality.
    summary = build_quality_gate_summary(
        sorted_checks,
        include_handoff_notes=config.include_handoff_notes,
    )
    data_quality = build_quality_gate_data_quality(sorted_checks)

    # Overall verdict.
    verdict_value = summary.verdict
    verdict = QualityGateVerdict(verdict_value.lower())

    # Collect unique blocking reason codes from checks, sorted for determinism.
    unique_reasons: set[str] = set()
    for check in sorted_checks:
        for rc in check.reason_codes:
            if _is_blocking_reason(rc):
                unique_reasons.add(rc)
    reason_codes = tuple(sorted(unique_reasons))

    handoff_notes = summary.handoff_notes

    # 28. UNSAFE_GATE_CONTENT
    if has_unsafe_quality_gate_content(handoff_notes, None):
        gate = ResearchQualityGate.blocked("UNSAFE_GATE_CONTENT", generated_at=generated_at)
        object.__setattr__(gate, "gate_id", gate_id)
        object.__setattr__(gate, "config", config)
        object.__setattr__(gate, "safety_flags", safety_flags)
        return gate

    return ResearchQualityGate(
        gate_id=gate_id,
        generated_at=generated_at,
        version=QUALITY_GATE_VERSION,
        verdict=verdict,
        checks=sorted_checks,
        summary=summary,
        data_quality=data_quality,
        safety_flags=safety_flags,
        config=config,
        reason_codes=reason_codes,
        handoff_notes=handoff_notes,
    )
