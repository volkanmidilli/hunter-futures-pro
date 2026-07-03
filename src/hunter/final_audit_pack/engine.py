"""In-memory engine for hunter.final_audit_pack package.

MVP-32 — Local Research Final Audit Pack Export.

The engine consumes already-loaded in-memory research artifacts and opaque
artifact reference strings, and produces a deterministic, local, human-audit
final audit pack report. It never reads files, follows paths, calls networks,
accesses exchanges, starts servers, schedulers, daemons, or databases, and never
emits trading or execution commands.

All metadata and artifact reference strings are opaque local strings. The
engine never opens, follows, traverses, validates, fetches, or executes them.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from hashlib import sha256
from types import MappingProxyType
from typing import Any

from hunter.backtest import BacktestReport
from hunter.discovery import DiscoveryReport
from hunter.experiment_ledger import ExperimentLedgerReport
from hunter.portfolio_construction import PortfolioConstructionReport
from hunter.reporting_cli import CLICommandResult
from hunter.run_orchestrator import ResearchRunResult
from hunter.final_audit_pack.models import (
    BACKTEST_SECTION_KIND,
    DEFAULT_OPTIONAL_SECTION_KINDS,
    DEFAULT_REQUIRED_SECTION_KINDS,
    DISCOVERY_SECTION_KIND,
    DUPLICATE_SECTION_ID,
    EXPERIMENT_LEDGER_SECTION_KIND,
    FINAL_AUDIT_PACK_ADVISORY_REASON_CODES,
    FINAL_AUDIT_PACK_BLOCKING_REASON_CODES,
    FINAL_AUDIT_PACK_VERSION,
    FinalAuditPackArtifact,
    FinalAuditPackConfig,
    FinalAuditPackCompleteness,
    FinalAuditPackDataQuality,
    FinalAuditPackInput,
    FinalAuditPackReport,
    FinalAuditPackSafetyFlags,
    FinalAuditPackSection,
    FinalAuditPackState,
    INVALID_SECTION,
    MISSING_REQUIRED_FIELDS,
    MISSING_REQUIRED_SECTIONS,
    NO_ACTION_COMMANDS_EMITTED,
    NO_DATABASE,
    NO_DAEMON,
    NO_EXCHANGE_CONNECTION,
    NO_FILE_INGESTION,
    NO_FREQTRADE_INPUT,
    NO_NETWORK_CONNECTION,
    NO_SCHEDULER,
    NO_WEB_UI,
    NOT_TRADING_ADVICE,
    OK,
    PORTFOLIO_CONSTRUCTION_SECTION_KIND,
    REPORTING_CLI_SECTION_KIND,
    RESEARCH_ONLY,
    RUN_ORCHESTRATOR_SECTION_KIND,
    UNSAFE_CONTENT,
    has_unsafe_final_audit_pack_content,
)


# ---------------------------------------------------------------------------
# Safety helpers
# ---------------------------------------------------------------------------


def build_final_audit_pack_safety_flags(
    *,
    has_unsafe_content: bool = False,
    has_duplicate_section_id: bool = False,
    has_invalid_section: bool = False,
    has_missing_required_sections: bool = False,
    has_blocked_section: bool = False,
    has_insufficient_section: bool = False,
) -> FinalAuditPackSafetyFlags:
    """Build final audit pack safety flags with observed negative states."""
    return FinalAuditPackSafetyFlags(
        has_unsafe_content=has_unsafe_content,
        has_duplicate_section_id=has_duplicate_section_id,
        has_invalid_section=has_invalid_section,
        has_missing_required_sections=has_missing_required_sections,
        has_blocked_section=has_blocked_section,
        has_insufficient_section=has_insufficient_section,
    )


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------


def build_final_audit_pack_report(
    input: FinalAuditPackInput,
    config: FinalAuditPackConfig | None = None,
) -> FinalAuditPackReport:
    """Build a deterministic final audit pack report from in-memory inputs.

    The engine never reads files, follows paths, calls networks, accesses
    exchanges, or emits trading/execution commands. All inputs are caller-
    provided in-memory objects or opaque local strings.
    """
    if config is None:
        config = FinalAuditPackConfig()

    generated_at = _resolve_generated_at(input, config)

    # Input-level unsafe content check on caller-provided tags only. Metadata
    # remains opaque and is not scanned.
    if has_unsafe_final_audit_pack_content(tags=input.tags):
        return FinalAuditPackReport.blocked(
            input=input,
            config=config,
            reason_code=UNSAFE_CONTENT,
            generated_at=generated_at,
            notes=(
                "Final audit pack report blocked due to unsafe content in input tags.",
                "Final audit pack output is for human audit only and is not a "
                "trading signal, recommendation, or approval.",
            ),
        )

    # Normalize each caller-provided report into a FinalAuditPackSection.
    sections: list[FinalAuditPackSection] = []
    for index, report in enumerate(input.backtest_reports):
        sections.append(_normalize_backtest_report(report, input, generated_at, index))
    for index, result in enumerate(input.run_results):
        sections.append(_normalize_run_result(result, input, generated_at, index))
    for index, report in enumerate(input.experiment_ledger_reports):
        sections.append(_normalize_experiment_ledger_report(report, input, generated_at, index))
    for index, report in enumerate(input.portfolio_construction_reports):
        sections.append(_normalize_portfolio_construction_report(report, input, generated_at, index))
    for index, report in enumerate(input.discovery_reports):
        sections.append(_normalize_discovery_report(report, input, generated_at, index))
    for index, result in enumerate(input.cli_command_results):
        sections.append(_normalize_cli_command_result(result, input, generated_at, index))

    # Build opaque artifact references.
    artifacts = _build_artifacts(input.artifact_references)

    # Detect duplicate section IDs deterministically.
    sections = _detect_duplicate_sections(sections)

    # Sort deterministically.
    sections = _sort_sections(sections)
    artifacts = _sort_artifacts(artifacts)

    # Build completeness, data quality, safety flags, and reason codes.
    completeness = _build_completeness(sections, artifacts, config)
    data_quality = _build_data_quality(sections, artifacts, input)
    safety_flags = _build_safety_flags(sections, config, completeness)
    reason_codes = _aggregate_reason_codes(sections, completeness, config, safety_flags)

    report_id = _deterministic_report_id(sections, artifacts, generated_at)

    notes = (
        "Final audit pack output is for human audit only.",
        "This is not a trading signal, recommendation, or certification of trading readiness.",
    )

    return FinalAuditPackReport(
        report_id=report_id,
        version=FINAL_AUDIT_PACK_VERSION,
        generated_at=generated_at,
        sections=tuple(sections),
        artifacts=tuple(artifacts),
        completeness=completeness,
        data_quality=data_quality,
        safety_flags=safety_flags,
        reason_codes=tuple(reason_codes),
        metadata=input.metadata,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------


def _resolve_generated_at(
    input: FinalAuditPackInput,
    config: FinalAuditPackConfig,
) -> datetime:
    """Resolve the final audit pack timestamp deterministically."""
    if config.generated_at is not None:
        return config.generated_at
    if input.generated_at is not None:
        return input.generated_at
    return datetime.now(timezone.utc)


def _deterministic_report_id(
    sections: Sequence[FinalAuditPackSection],
    artifacts: Sequence[FinalAuditPackArtifact],
    generated_at: datetime,
) -> str:
    """Generate a deterministic report identifier from sorted section/artifact ids."""
    section_ids = sorted(s.section_id for s in sections)
    artifact_refs = sorted(a.reference for a in artifacts)
    parts = ["final_audit_pack", generated_at.isoformat()] + section_ids + artifact_refs
    data = ":".join(parts)
    return sha256(data.encode("utf-8")).hexdigest()[:16]


def _get_str_attr(obj: Any, attr: str, default: str = "") -> str:
    """Return a string attribute value, defaulting to empty string if missing/invalid."""
    value = getattr(obj, attr, default)
    if isinstance(value, str):
        return value
    return default


def _get_datetime_attr(obj: Any, attr: str, default: datetime | None = None) -> datetime | None:
    """Return a datetime attribute if it is timezone-aware, otherwise default."""
    value = getattr(obj, attr, default)
    if isinstance(value, datetime) and value.tzinfo is not None:
        return value
    return default


def _get_tuple_attr(obj: Any, attr: str, default: tuple[str, ...] = ()) -> tuple[str, ...]:
    """Return a string-tuple attribute, coercing lists/tuples."""
    value = getattr(obj, attr, default)
    if value is None:
        return default
    if isinstance(value, (tuple, list)):
        return tuple(str(item) for item in value)
    return default


def _get_metadata_attr(obj: Any, attr: str = "metadata") -> Mapping[str, Any]:
    """Return a metadata mapping from an object, or empty if missing/invalid."""
    value = getattr(obj, attr, None)
    if value is None:
        return MappingProxyType({})
    if isinstance(value, Mapping):
        return MappingProxyType(dict(value))
    return MappingProxyType({})


def _resolve_display_name(
    section_kind: str,
    name: str,
    section_id: str,
    obj: Any,
) -> str:
    """Return the display name for a section.

    Explicit name takes precedence. For CLICommandResult, use the command
    attribute if exposed. Otherwise fall back to section_id.
    """
    if name:
        return name
    if section_kind == REPORTING_CLI_SECTION_KIND:
        command = _get_str_attr(obj, "command", "")
        if command:
            return command
    return section_id


def _build_section_id(
    report_id: str,
    run_id: str,
    section_kind: str,
    index: int,
) -> str:
    """Build a stable section id: report_id, run_id, or kind:index fallback."""
    if report_id:
        return report_id
    if run_id:
        return run_id
    return f"{section_kind}:{index}"


def _normalize_backtest_report(
    report: BacktestReport,
    input: FinalAuditPackInput,
    default_generated_at: datetime,
    index: int,
) -> FinalAuditPackSection:
    """Normalize a BacktestReport into a FinalAuditPackSection."""
    return _normalize_generic_report(
        report,
        BACKTEST_SECTION_KIND,
        input,
        default_generated_at,
        index,
    )


def _normalize_run_result(
    result: ResearchRunResult,
    input: FinalAuditPackInput,
    default_generated_at: datetime,
    index: int,
) -> FinalAuditPackSection:
    """Normalize a ResearchRunResult into a FinalAuditPackSection."""
    return _normalize_generic_report(
        result,
        RUN_ORCHESTRATOR_SECTION_KIND,
        input,
        default_generated_at,
        index,
    )


def _normalize_experiment_ledger_report(
    report: ExperimentLedgerReport,
    input: FinalAuditPackInput,
    default_generated_at: datetime,
    index: int,
) -> FinalAuditPackSection:
    """Normalize an ExperimentLedgerReport into a FinalAuditPackSection."""
    return _normalize_generic_report(
        report,
        EXPERIMENT_LEDGER_SECTION_KIND,
        input,
        default_generated_at,
        index,
    )


def _normalize_portfolio_construction_report(
    report: PortfolioConstructionReport,
    input: FinalAuditPackInput,
    default_generated_at: datetime,
    index: int,
) -> FinalAuditPackSection:
    """Normalize a PortfolioConstructionReport into a FinalAuditPackSection."""
    return _normalize_generic_report(
        report,
        PORTFOLIO_CONSTRUCTION_SECTION_KIND,
        input,
        default_generated_at,
        index,
    )


def _normalize_discovery_report(
    report: DiscoveryReport,
    input: FinalAuditPackInput,
    default_generated_at: datetime,
    index: int,
) -> FinalAuditPackSection:
    """Normalize a DiscoveryReport into a FinalAuditPackSection."""
    return _normalize_generic_report(
        report,
        DISCOVERY_SECTION_KIND,
        input,
        default_generated_at,
        index,
    )


def _normalize_cli_command_result(
    result: CLICommandResult,
    input: FinalAuditPackInput,
    default_generated_at: datetime,
    index: int,
) -> FinalAuditPackSection:
    """Normalize a CLICommandResult into a FinalAuditPackSection."""
    section_kind = REPORTING_CLI_SECTION_KIND
    report_id = _get_str_attr(result, "report_id", "")
    run_id = _get_str_attr(result, "run_id", "")
    name = _get_str_attr(result, "name", "")
    section_id = _build_section_id(report_id, run_id, section_kind, index)
    generated_at = _get_datetime_attr(result, "generated_at") or default_generated_at
    tags = _get_tuple_attr(result, "tags")
    metadata = _get_metadata_attr(result)
    display_name = _resolve_display_name(section_kind, name, section_id, result)

    return _finalize_section(
        section_id=section_id,
        section_kind=section_kind,
        report_id=report_id,
        run_id=run_id,
        name=name,
        display_name=display_name,
        generated_at=generated_at,
        tags=tags,
        metadata=metadata,
    )


def _normalize_generic_report(
    report: Any,
    section_kind: str,
    input: FinalAuditPackInput,
    default_generated_at: datetime,
    index: int,
) -> FinalAuditPackSection:
    """Normalize a report object with report_id/run_id/name attributes."""
    report_id = _get_str_attr(report, "report_id", "")
    run_id = _get_str_attr(report, "run_id", "")
    name = _get_str_attr(report, "name", "")
    section_id = _build_section_id(report_id, run_id, section_kind, index)
    generated_at = _get_datetime_attr(report, "generated_at") or default_generated_at
    tags = _get_tuple_attr(report, "tags")
    metadata = _get_metadata_attr(report)
    display_name = _resolve_display_name(section_kind, name, section_id, report)

    return _finalize_section(
        section_id=section_id,
        section_kind=section_kind,
        report_id=report_id,
        run_id=run_id,
        name=name,
        display_name=display_name,
        generated_at=generated_at,
        tags=tags,
        metadata=metadata,
    )


def _finalize_section(
    *,
    section_id: str,
    section_kind: str,
    report_id: str,
    run_id: str,
    name: str,
    display_name: str,
    generated_at: datetime,
    tags: tuple[str, ...],
    metadata: Mapping[str, Any],
) -> FinalAuditPackSection:
    """Apply safety and validation checks to a normalized section."""
    # Validate required fields.
    if not section_id or not section_kind:
        return FinalAuditPackSection.blocked(
            section_id=section_id or "blocked",
            section_kind=section_kind or "blocked",
            report_id=report_id,
            run_id=run_id,
            name=name,
            reason_codes=(MISSING_REQUIRED_FIELDS,),
            generated_at=generated_at,
            tags=tags,
            metadata=metadata,
        )

    # Safety check on section_id, display name, and tags. Metadata remains opaque.
    if has_unsafe_final_audit_pack_content(text=section_id, tags=tags) or \
       has_unsafe_final_audit_pack_content(text=display_name):
        return FinalAuditPackSection.blocked(
            section_id=section_id,
            section_kind=section_kind,
            report_id=report_id,
            run_id=run_id,
            name=name,
            reason_codes=(UNSAFE_CONTENT,),
            generated_at=generated_at,
            tags=tags,
            metadata=metadata,
        )

    return FinalAuditPackSection(
        section_id=section_id,
        section_kind=section_kind,
        report_id=report_id,
        run_id=run_id,
        name=name,
        state=FinalAuditPackState.INCLUDED,
        reason_codes=(OK,),
        generated_at=generated_at,
        tags=tags,
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# Artifacts
# ---------------------------------------------------------------------------


def _build_artifacts(
    artifact_references: tuple[str, ...],
) -> list[FinalAuditPackArtifact]:
    """Build opaque artifact references without opening or validating paths."""
    artifacts: list[FinalAuditPackArtifact] = []
    for reference in artifact_references:
        if not isinstance(reference, str):
            continue
        artifacts.append(
            FinalAuditPackArtifact(
                kind="artifact",
                reference=reference,
                display_name=reference,
            )
        )
    return artifacts


# ---------------------------------------------------------------------------
# Duplicate detection and sorting
# ---------------------------------------------------------------------------


def _detect_duplicate_sections(
    sections: list[FinalAuditPackSection],
) -> list[FinalAuditPackSection]:
    """Mark all duplicate section IDs after the first as BLOCKED."""
    seen: set[str] = set()
    result: list[FinalAuditPackSection] = []
    for section in sections:
        if section.section_id in seen:
            result.append(
                FinalAuditPackSection(
                    section_id=section.section_id,
                    section_kind=section.section_kind,
                    report_id=section.report_id,
                    run_id=section.run_id,
                    name=section.name,
                    state=FinalAuditPackState.BLOCKED,
                    reason_codes=(DUPLICATE_SECTION_ID,) + section.reason_codes,
                    generated_at=section.generated_at,
                    tags=section.tags,
                    metadata=section.metadata,
                )
            )
        else:
            seen.add(section.section_id)
            result.append(section)
    return result


def _sort_sections(
    sections: list[FinalAuditPackSection],
) -> list[FinalAuditPackSection]:
    """Sort sections deterministically."""
    return sorted(
        sections,
        key=lambda s: (
            s.section_kind,
            (s.generated_at or datetime.max.replace(tzinfo=timezone.utc)),
            s.report_id,
            s.run_id,
            s.name,
            s.section_id,
        ),
    )


def _sort_artifacts(
    artifacts: list[FinalAuditPackArtifact],
) -> list[FinalAuditPackArtifact]:
    """Sort artifacts deterministically."""
    return sorted(
        artifacts,
        key=lambda a: (a.kind, a.reference, a.display_name),
    )


# ---------------------------------------------------------------------------
# Completeness and data quality
# ---------------------------------------------------------------------------


def _present_kinds(
    sections: Sequence[FinalAuditPackSection],
) -> set[str]:
    """Return kinds with at least one INCLUDED or INSUFFICIENT_DATA section."""
    return {
        section.section_kind
        for section in sections
        if section.state in (FinalAuditPackState.INCLUDED, FinalAuditPackState.INSUFFICIENT_DATA)
    }


def _build_completeness(
    sections: Sequence[FinalAuditPackSection],
    artifacts: Sequence[FinalAuditPackArtifact],
    config: FinalAuditPackConfig,
) -> FinalAuditPackCompleteness:
    """Compute the completeness summary."""
    present = _present_kinds(sections)
    required_present = present & set(config.required_section_kinds)
    optional_present = present & set(config.optional_section_kinds)
    required_missing = set(config.required_section_kinds) - required_present
    sections_expected = len(config.required_section_kinds) + len(config.optional_section_kinds)

    blocked = sum(1 for s in sections if s.state is FinalAuditPackState.BLOCKED)
    insufficient = sum(1 for s in sections if s.state is FinalAuditPackState.INSUFFICIENT_DATA)
    sections_present = sum(1 for s in sections if s.state is not FinalAuditPackState.BLOCKED)

    notes: list[str] = []
    if required_missing:
        notes.append(
            f"Missing required section kinds: {sorted(required_missing)}"
        )
    optional_missing = set(config.optional_section_kinds) - optional_present
    if optional_missing:
        notes.append(
            f"Missing optional section kinds: {sorted(optional_missing)}"
        )

    return FinalAuditPackCompleteness(
        required_sections_present=len(required_present),
        required_sections_missing=len(required_missing),
        optional_sections_present=len(optional_present),
        artifact_reference_count=len(artifacts),
        blocked_section_count=blocked,
        insufficient_section_count=insufficient,
        safety_notice_present=True,
        total_sections=len(sections),
        sections_expected=sections_expected,
        sections_present=sections_present,
        notes=tuple(notes),
    )


def _build_data_quality(
    sections: Sequence[FinalAuditPackSection],
    artifacts: Sequence[FinalAuditPackArtifact],
    input: FinalAuditPackInput,
) -> FinalAuditPackDataQuality:
    """Compute the data quality summary."""
    total_inputs = (
        len(input.backtest_reports)
        + len(input.run_results)
        + len(input.experiment_ledger_reports)
        + len(input.portfolio_construction_reports)
        + len(input.discovery_reports)
        + len(input.cli_command_results)
        + len(input.artifact_references)
    )
    blocked = sum(1 for s in sections if s.state is FinalAuditPackState.BLOCKED)
    insufficient = sum(1 for s in sections if s.state is FinalAuditPackState.INSUFFICIENT_DATA)
    excluded = sum(1 for s in sections if s.state is FinalAuditPackState.EXCLUDED)
    included = sum(1 for s in sections if s.state is FinalAuditPackState.INCLUDED)
    sections_present = sum(1 for s in sections if s.state is not FinalAuditPackState.BLOCKED)

    notes: list[str] = []
    if blocked:
        notes.append(f"Blocked sections: {blocked}")
    if insufficient:
        notes.append(f"Insufficient sections: {insufficient}")

    return FinalAuditPackDataQuality(
        total_inputs=total_inputs,
        normalized_sections=len(sections),
        blocked_sections=blocked,
        insufficient_sections=insufficient,
        excluded_sections=excluded,
        included_sections=included,
        sections_present=sections_present,
        sections_expected=sections_present,  # Will be updated below if needed.
        artifact_references=len(artifacts),
        notes=tuple(notes),
    )


# ---------------------------------------------------------------------------
# Safety flags and reason codes
# ---------------------------------------------------------------------------


def _build_safety_flags(
    sections: Sequence[FinalAuditPackSection],
    config: FinalAuditPackConfig,
    completeness: FinalAuditPackCompleteness,
) -> FinalAuditPackSafetyFlags:
    """Build safety flags from observed section/completeness state."""
    has_unsafe = any(
        UNSAFE_CONTENT in section.reason_codes for section in sections
    )
    has_duplicate = any(
        DUPLICATE_SECTION_ID in section.reason_codes for section in sections
    )
    has_invalid = any(
        INVALID_SECTION in section.reason_codes or MISSING_REQUIRED_FIELDS in section.reason_codes
        for section in sections
    )
    has_blocked = any(
        section.state is FinalAuditPackState.BLOCKED for section in sections
    )
    has_insufficient = any(
        section.state is FinalAuditPackState.INSUFFICIENT_DATA for section in sections
    )
    has_missing_required = completeness.required_sections_missing > 0
    return FinalAuditPackSafetyFlags(
        has_unsafe_content=has_unsafe,
        has_duplicate_section_id=has_duplicate,
        has_invalid_section=has_invalid,
        has_missing_required_sections=has_missing_required,
        has_blocked_section=has_blocked,
        has_insufficient_section=has_insufficient,
    )


def _aggregate_reason_codes(
    sections: Sequence[FinalAuditPackSection],
    completeness: FinalAuditPackCompleteness,
    config: FinalAuditPackConfig,
    safety_flags: FinalAuditPackSafetyFlags,
) -> list[str]:
    """Aggregate advisory and blocking reason codes from sections and report."""
    reason_codes: list[str] = []

    # Advisory codes are always present for valid exports.
    for code in FINAL_AUDIT_PACK_ADVISORY_REASON_CODES:
        if code not in reason_codes:
            reason_codes.append(code)

    # Section-level blocking codes.
    for section in sections:
        for code in section.reason_codes:
            if code in FINAL_AUDIT_PACK_BLOCKING_REASON_CODES and code not in reason_codes:
                reason_codes.append(code)

    # Missing required sections.
    if completeness.required_sections_missing > 0:
        if MISSING_REQUIRED_SECTIONS not in reason_codes:
            reason_codes.append(MISSING_REQUIRED_SECTIONS)

    # Blocked or degraded state from missing required sections when configured.
    if safety_flags.has_blocked_section or (
        completeness.required_sections_missing > 0 and config.block_on_missing_required
    ):
        if MISSING_REQUIRED_SECTIONS not in reason_codes:
            reason_codes.append(MISSING_REQUIRED_SECTIONS)

    return reason_codes


def _build_notes() -> tuple[str, ...]:
    """Return standard human-audit notes."""
    return (
        "Final audit pack output is for human audit only.",
        "This is not a trading signal, recommendation, or certification of trading readiness.",
    )
