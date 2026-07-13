"""Engine for the Controlled Universe Export Adapter (MVP-53).

Deterministic, fail-closed transformation from ControlledUniverseReport to
research-only export artifacts. No external side effects.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from hunter.controlled_universe.models import (
    ControlledUniverseReport,
    ControlledUniverseState,
)
from hunter.run_orchestrator.models import (
    ResearchRunResult,
    ResearchRunState,
    ResearchRunStepKind,
)

from hunter.controlled_universe_export_adapter.models import (
    BLOCKED_EXPORT,
    CONTROLLED_UNIVERSE_EXPORT_VERSION,
    EXPORT_HUMAN_APPROVAL_REQUIRED,
    EXPORT_RESEARCH_ONLY,
    MISSING_REPORT_INPUT,
    NO_AUTOMATIC_CONFIG_MUTATION,
    NO_FREQTRADE_RUNTIME_CONNECTION,
    NO_INCLUDED_PAIRS,
    ControlledUniverseExportConfig,
    ControlledUniverseExportResult,
    ControlledUniversePairExportSummary,
)


def _format_pair(pair: str, config: ControlledUniverseExportConfig) -> str:
    """Format a pair string according to the configured convention."""
    if config.pair_format == "base_quote":
        return pair.replace("/", "_")
    return pair


_STATE_HUMAN_NOTES: dict[str, str] = {
    ControlledUniverseState.INCLUDED.value: "passed controlled universe filter",
    ControlledUniverseState.WATCHLIST.value: "watchlist for research review only",
    ControlledUniverseState.EXCLUDED.value: "excluded by controlled universe filter",
    ControlledUniverseState.BLOCKED.value: "blocked by controlled universe filter",
    ControlledUniverseState.INSUFFICIENT_DATA.value: "insufficient data for controlled universe inclusion",
}


def _is_report_blocked(report: ControlledUniverseReport | None) -> bool:
    """Return True if the report is missing, unsafe, or indicates blocked execution."""
    if report is None:
        return True
    if not report.safety_flags.is_safe:
        return True
    if report.safety_flags.has_blocked_execution:
        return True
    return False


def _build_safety_flags(report: ControlledUniverseReport | None) -> dict[str, bool]:
    """Build deterministic safety flags for the export result."""
    return {
        "no_freqtrade_runtime_connection": True,
        "no_automatic_config_mutation": True,
        "no_trading_signal": True,
        "no_execution_approval": True,
        "no_strategy_approval": True,
        "no_portfolio_approval": True,
        "no_universe_approval": True,
        "no_action_commands": True,
        "no_network_connection": True,
        "no_file_read_in_engine": True,
        "no_database": True,
        "no_exchange_connection": True,
        "input_report_is_safe": report.safety_flags.is_safe if report is not None else False,
        "input_report_has_blocked_execution": (
            report.safety_flags.has_blocked_execution if report is not None else False
        ),
    }


def _build_pair_summary(
    item: Any,
    config: ControlledUniverseExportConfig,
) -> ControlledUniversePairExportSummary:
    """Build a deterministic per-pair export summary."""
    state_value = item.state.value if hasattr(item.state, "value") else str(item.state)
    classification_value = (
        item.classification.value if hasattr(item.classification, "value") else str(item.classification)
    )
    reason_codes = tuple(sorted(set(item.reason_codes)))
    human_note = _STATE_HUMAN_NOTES.get(state_value, "unknown controlled universe state")
    return ControlledUniversePairExportSummary(
        pair=_format_pair(item.pair, config),
        state=state_value,
        classification=classification_value,
        reason_codes=reason_codes if config.include_reason_codes_in_summary else (),
        human_note=human_note,
    )


def _derive_whitelist(
    report: ControlledUniverseReport,
    config: ControlledUniverseExportConfig,
) -> tuple[str, ...]:
    """Derive the sorted whitelist from the report items."""
    states = {ControlledUniverseState.INCLUDED.value}
    if config.include_watchlist_in_whitelist:
        states.add(ControlledUniverseState.WATCHLIST.value)
    pairs = []
    for item in report.items:
        state_value = item.state.value if hasattr(item.state, "value") else str(item.state)
        if state_value in states:
            pairs.append(_format_pair(item.pair, config))
    return tuple(sorted(set(pairs)))


def _derive_blacklist(
    report: ControlledUniverseReport,
    config: ControlledUniverseExportConfig,
) -> tuple[str, ...]:
    """Derive the sorted blacklist from the report items."""
    states = {
        ControlledUniverseState.BLOCKED.value,
        ControlledUniverseState.EXCLUDED.value,
        ControlledUniverseState.INSUFFICIENT_DATA.value,
    }
    pairs = []
    for item in report.items:
        state_value = item.state.value if hasattr(item.state, "value") else str(item.state)
        if state_value in states:
            pairs.append(_format_pair(item.pair, config))
    return tuple(sorted(set(pairs)))


def _build_report_id(report: ControlledUniverseReport | None) -> str:
    """Return a deterministic report id for the export result."""
    if report is None:
        return "missing"
    report_id = report.metadata.get("report_id", "") if report.metadata else ""
    if report_id:
        return report_id
    return f"cue-{report.generated_at.strftime('%Y%m%d%H%M%S')}-{CONTROLLED_UNIVERSE_EXPORT_VERSION}"


def _build_reason_codes(
    report: ControlledUniverseReport | None,
    whitelist: tuple[str, ...],
    report_specific_code: str | None,
) -> tuple[str, ...]:
    """Build deterministic reason codes for the export result."""
    codes: set[str] = {
        EXPORT_RESEARCH_ONLY,
        EXPORT_HUMAN_APPROVAL_REQUIRED,
        NO_FREQTRADE_RUNTIME_CONNECTION,
        NO_AUTOMATIC_CONFIG_MUTATION,
    }
    if report_specific_code:
        codes.add(report_specific_code)
    if report is not None and not whitelist:
        if not report_specific_code:
            codes.add(NO_INCLUDED_PAIRS)
    return tuple(sorted(codes))


def build_controlled_universe_export(
    report: ControlledUniverseReport | None,
    config: ControlledUniverseExportConfig | None = None,
) -> ControlledUniverseExportResult:
    """Transform a ControlledUniverseReport into a deterministic research-only export.

    Args:
        report: The controlled universe report to export. If None, a fail-closed
            result with an empty whitelist is returned.
        config: Optional export configuration. Defaults to
            ControlledUniverseExportConfig.default().

    Returns:
        A ControlledUniverseExportResult with whitelist, blacklist, per-pair
        summary, and explicit safety flags.
    """
    effective_config = config or ControlledUniverseExportConfig.default()
    generated_at = datetime.now(timezone.utc)

    if report is None:
        return ControlledUniverseExportResult(
            report_id="missing",
            generated_at=generated_at,
            whitelist=(),
            blacklist=(),
            per_pair_summary=(),
            research_only=True,
            human_approval_required=True,
            reason_codes=_build_reason_codes(None, (), MISSING_REPORT_INPUT),
            safety_flags=_build_safety_flags(None),
            metadata={"version": CONTROLLED_UNIVERSE_EXPORT_VERSION},
        )

    generated_at = report.generated_at
    report_id = _build_report_id(report)
    blocked = _is_report_blocked(report)
    per_pair_summary = tuple(
        sorted(
            (_build_pair_summary(item, effective_config) for item in report.items),
            key=lambda summary: summary.pair,
        )
    )

    if blocked:
        whitelist: tuple[str, ...] = ()
        blacklist = _derive_blacklist(report, effective_config)
        report_specific_code = BLOCKED_EXPORT
    else:
        whitelist = _derive_whitelist(report, effective_config)
        blacklist = _derive_blacklist(report, effective_config)
        report_specific_code = None if whitelist else NO_INCLUDED_PAIRS

    return ControlledUniverseExportResult(
        report_id=report_id,
        generated_at=generated_at,
        whitelist=whitelist,
        blacklist=blacklist,
        per_pair_summary=per_pair_summary,
        research_only=True,
        human_approval_required=True,
        reason_codes=_build_reason_codes(report, whitelist, report_specific_code),
        safety_flags=_build_safety_flags(report),
        metadata={
            "version": CONTROLLED_UNIVERSE_EXPORT_VERSION,
            "source_report_version": report.version,
        },
    )


def build_controlled_universe_export_from_run_result(
    result: ResearchRunResult,
    config: ControlledUniverseExportConfig | None = None,
) -> ControlledUniverseExportResult:
    """Extract the controlled-universe report from a ResearchRunResult and export it.

    Args:
        result: The research run result to extract from.
        config: Optional export configuration.

    Returns:
        A ControlledUniverseExportResult derived from the first CONTROLLED_UNIVERSE
        step's report, or a fail-closed result if no such report exists.
    """
    if result is None:
        return build_controlled_universe_export(None, config)

    report = None
    for step in result.steps:
        if step.kind == ResearchRunStepKind.CONTROLLED_UNIVERSE:
            report = step.data.get("report")
            break

    if report is None:
        return build_controlled_universe_export(report, config)

    if result.state in (ResearchRunState.BLOCKED, ResearchRunState.FAILED):
        # Run result is blocked/failed: treat as fail-closed blocked input.
        base = build_controlled_universe_export(report, config)
        all_pairs = tuple(sorted({summary.pair for summary in base.per_pair_summary}))
        blocked_reason_codes = tuple(sorted(set(base.reason_codes) | {BLOCKED_EXPORT}))
        return ControlledUniverseExportResult(
            report_id=base.report_id,
            generated_at=base.generated_at,
            whitelist=(),
            blacklist=all_pairs,
            per_pair_summary=base.per_pair_summary,
            research_only=True,
            human_approval_required=True,
            reason_codes=blocked_reason_codes,
            safety_flags=base.safety_flags,
            metadata=base.metadata,
        )

    return build_controlled_universe_export(report, config)
