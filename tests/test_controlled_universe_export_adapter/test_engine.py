"""Tests for the controlled_universe_export_adapter engine."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from hunter.controlled_universe.models import (
    CONTROLLED_UNIVERSE_VERSION,
    ControlledUniverseClassification,
    ControlledUniverseConfig,
    ControlledUniverseDataQuality,
    ControlledUniverseItem,
    ControlledUniverseReport,
    ControlledUniverseSafetyFlags,
    ControlledUniverseState,
)
from hunter.controlled_universe_export_adapter import (
    BLOCKED_EXPORT,
    EXPORT_HUMAN_APPROVAL_REQUIRED,
    EXPORT_RESEARCH_ONLY,
    MISSING_REPORT_INPUT,
    NO_AUTOMATIC_CONFIG_MUTATION,
    NO_FREQTRADE_RUNTIME_CONNECTION,
    NO_INCLUDED_PAIRS,
    ControlledUniverseExportConfig,
    build_controlled_universe_export,
    build_controlled_universe_export_from_run_result,
)
from hunter.run_orchestrator.models import (
    ResearchRunResult,
    ResearchRunState,
)


def _dt() -> datetime:
    return datetime(2026, 7, 13, 12, 0, 0, tzinfo=timezone.utc)


def _make_report(
    *,
    items: tuple[ControlledUniverseItem, ...] = (),
    universe: tuple[str, ...] = (),
    watchlist: tuple[str, ...] = (),
    blocked: tuple[str, ...] = (),
    safety_flags: ControlledUniverseSafetyFlags | None = None,
    reason_codes: tuple[str, ...] = (),
    metadata: dict[str, str] | None = None,
) -> ControlledUniverseReport:
    return ControlledUniverseReport(
        version=CONTROLLED_UNIVERSE_VERSION,
        generated_at=_dt(),
        config=ControlledUniverseConfig(),
        execution_state="ALLOW",
        allowed_mode="LONG_ONLY",
        universe=universe,
        watchlist=watchlist,
        blocked=blocked,
        items=items,
        data_quality=ControlledUniverseDataQuality(),
        safety_flags=safety_flags or ControlledUniverseSafetyFlags(),
        reason_codes=reason_codes or (),
        metadata=metadata or {},
    )


def _make_item(
    pair: str,
    state: ControlledUniverseState,
    classification: ControlledUniverseClassification,
    reason_codes: tuple[str, ...] = (),
) -> ControlledUniverseItem:
    return ControlledUniverseItem(
        pair=pair,
        state=state,
        classification=classification,
        reason_codes=reason_codes,
    )


class TestBuildControlledUniverseExport:
    def test_none_report_returns_fail_closed(self) -> None:
        result = build_controlled_universe_export(None)
        assert result.whitelist == ()
        assert result.blacklist == ()
        assert result.per_pair_summary == ()
        assert result.research_only is True
        assert result.human_approval_required is True
        assert MISSING_REPORT_INPUT in result.reason_codes
        assert EXPORT_RESEARCH_ONLY in result.reason_codes
        assert EXPORT_HUMAN_APPROVAL_REQUIRED in result.reason_codes
        assert NO_FREQTRADE_RUNTIME_CONNECTION in result.reason_codes
        assert NO_AUTOMATIC_CONFIG_MUTATION in result.reason_codes

    def test_included_pairs_in_whitelist(self) -> None:
        items = (
            _make_item(
                "BTC/USDT",
                ControlledUniverseState.INCLUDED,
                ControlledUniverseClassification.LONG_RESEARCH,
                ("PASSED_UNIVERSE_FILTER",),
            ),
            _make_item(
                "ETH/USDT",
                ControlledUniverseState.INCLUDED,
                ControlledUniverseClassification.LONG_RESEARCH,
                ("PASSED_UNIVERSE_FILTER",),
            ),
        )
        report = _make_report(items=items, universe=("BTC/USDT", "ETH/USDT"))
        result = build_controlled_universe_export(report)
        assert result.whitelist == ("BTC/USDT", "ETH/USDT")
        assert result.blacklist == ()
        assert len(result.per_pair_summary) == 2

    def test_blocked_and_excluded_in_blacklist(self) -> None:
        items = (
            _make_item(
                "BTC/USDT",
                ControlledUniverseState.INCLUDED,
                ControlledUniverseClassification.LONG_RESEARCH,
            ),
            _make_item(
                "ETH/USDT",
                ControlledUniverseState.EXCLUDED,
                ControlledUniverseClassification.BLOCKED_BY_PORTFOLIO,
                ("PORTFOLIO_STATE_EXCLUDED",),
            ),
            _make_item(
                "SOL/USDT",
                ControlledUniverseState.BLOCKED,
                ControlledUniverseClassification.BLOCKED_BY_MACRO,
                ("EXECUTION_BLOCKED",),
            ),
            _make_item(
                "ADA/USDT",
                ControlledUniverseState.INSUFFICIENT_DATA,
                ControlledUniverseClassification.NEUTRAL_RESEARCH,
                ("PORTFOLIO_STATE_INSUFFICIENT_DATA",),
            ),
        )
        report = _make_report(
            items=items,
            universe=("BTC/USDT",),
            blocked=("ETH/USDT", "SOL/USDT", "ADA/USDT"),
        )
        result = build_controlled_universe_export(report)
        assert result.whitelist == ("BTC/USDT",)
        assert result.blacklist == ("ADA/USDT", "ETH/USDT", "SOL/USDT")

    def test_watchlist_not_in_whitelist_by_default(self) -> None:
        items = (
            _make_item(
                "BTC/USDT",
                ControlledUniverseState.INCLUDED,
                ControlledUniverseClassification.LONG_RESEARCH,
            ),
            _make_item(
                "ETH/USDT",
                ControlledUniverseState.WATCHLIST,
                ControlledUniverseClassification.WATCHLIST_RESEARCH,
                ("PORTFOLIO_STATE_WATCHLIST",),
            ),
        )
        report = _make_report(
            items=items,
            universe=("BTC/USDT",),
            watchlist=("ETH/USDT",),
        )
        result = build_controlled_universe_export(report)
        assert result.whitelist == ("BTC/USDT",)
        assert result.blacklist == ()
        assert len(result.per_pair_summary) == 2

    def test_include_watchlist_in_whitelist(self) -> None:
        items = (
            _make_item(
                "BTC/USDT",
                ControlledUniverseState.INCLUDED,
                ControlledUniverseClassification.LONG_RESEARCH,
            ),
            _make_item(
                "ETH/USDT",
                ControlledUniverseState.WATCHLIST,
                ControlledUniverseClassification.WATCHLIST_RESEARCH,
            ),
        )
        report = _make_report(
            items=items,
            universe=("BTC/USDT",),
            watchlist=("ETH/USDT",),
        )
        config = ControlledUniverseExportConfig(include_watchlist_in_whitelist=True)
        result = build_controlled_universe_export(report, config)
        assert result.whitelist == ("BTC/USDT", "ETH/USDT")

    def test_unsafe_report_empty_whitelist(self) -> None:
        flags = ControlledUniverseSafetyFlags(has_unsafe_content=True)
        items = (
            _make_item(
                "BTC/USDT",
                ControlledUniverseState.INCLUDED,
                ControlledUniverseClassification.LONG_RESEARCH,
            ),
        )
        report = _make_report(items=items, universe=("BTC/USDT",), safety_flags=flags)
        result = build_controlled_universe_export(report)
        assert result.whitelist == ()
        assert BLOCKED_EXPORT in result.reason_codes
        assert result.blacklist == ()
        assert len(result.per_pair_summary) == 1

    def test_blocked_execution_empty_whitelist(self) -> None:
        flags = ControlledUniverseSafetyFlags(has_blocked_execution=True)
        items = (
            _make_item(
                "BTC/USDT",
                ControlledUniverseState.INCLUDED,
                ControlledUniverseClassification.LONG_RESEARCH,
            ),
        )
        report = _make_report(items=items, universe=("BTC/USDT",), safety_flags=flags)
        result = build_controlled_universe_export(report)
        assert result.whitelist == ()
        assert BLOCKED_EXPORT in result.reason_codes

    def test_no_included_pairs_reason_code(self) -> None:
        items = (
            _make_item(
                "ETH/USDT",
                ControlledUniverseState.EXCLUDED,
                ControlledUniverseClassification.BLOCKED_BY_PORTFOLIO,
            ),
        )
        report = _make_report(items=items, blocked=("ETH/USDT",))
        result = build_controlled_universe_export(report)
        assert result.whitelist == ()
        assert NO_INCLUDED_PAIRS in result.reason_codes

    def test_pair_format_base_quote(self) -> None:
        items = (
            _make_item(
                "BTC/USDT",
                ControlledUniverseState.INCLUDED,
                ControlledUniverseClassification.LONG_RESEARCH,
            ),
        )
        report = _make_report(items=items, universe=("BTC/USDT",))
        config = ControlledUniverseExportConfig(pair_format="base_quote")
        result = build_controlled_universe_export(report, config)
        assert result.whitelist == ("BTC_USDT",)
        assert result.blacklist == ()

    def test_per_pair_summary_sorted(self) -> None:
        items = (
            _make_item(
                "BTC/USDT",
                ControlledUniverseState.INCLUDED,
                ControlledUniverseClassification.LONG_RESEARCH,
            ),
            _make_item(
                "ETH/USDT",
                ControlledUniverseState.INCLUDED,
                ControlledUniverseClassification.LONG_RESEARCH,
            ),
            _make_item(
                "ADA/USDT",
                ControlledUniverseState.INCLUDED,
                ControlledUniverseClassification.LONG_RESEARCH,
            ),
        )
        report = _make_report(
            items=items,
            universe=("ADA/USDT", "BTC/USDT", "ETH/USDT"),
        )
        result = build_controlled_universe_export(report)
        pairs = [summary.pair for summary in result.per_pair_summary]
        assert pairs == ["ADA/USDT", "BTC/USDT", "ETH/USDT"]

    def test_reason_codes_sorted(self) -> None:
        result = build_controlled_universe_export(None)
        assert result.reason_codes == tuple(sorted(result.reason_codes))

    def test_report_id_from_metadata(self) -> None:
        report = _make_report(metadata={"report_id": "custom-id"})
        result = build_controlled_universe_export(report)
        assert result.report_id == "custom-id"

    def test_safety_flags_in_result(self) -> None:
        result = build_controlled_universe_export(None)
        assert result.safety_flags["no_freqtrade_runtime_connection"] is True
        assert result.safety_flags["no_automatic_config_mutation"] is True
        assert result.safety_flags["input_report_is_safe"] is False

    def test_determinism(self) -> None:
        items = (
            _make_item(
                "BTC/USDT",
                ControlledUniverseState.INCLUDED,
                ControlledUniverseClassification.LONG_RESEARCH,
            ),
            _make_item(
                "ETH/USDT",
                ControlledUniverseState.EXCLUDED,
                ControlledUniverseClassification.BLOCKED_BY_PORTFOLIO,
            ),
        )
        report = _make_report(items=items, universe=("BTC/USDT",), blocked=("ETH/USDT",))
        result1 = build_controlled_universe_export(report)
        result2 = build_controlled_universe_export(report)
        assert result1 == result2

    def test_no_reason_codes_in_summary_when_disabled(self) -> None:
        items = (
            _make_item(
                "BTC/USDT",
                ControlledUniverseState.INCLUDED,
                ControlledUniverseClassification.LONG_RESEARCH,
                ("PASSED_UNIVERSE_FILTER",),
            ),
        )
        report = _make_report(items=items, universe=("BTC/USDT",))
        config = ControlledUniverseExportConfig(include_reason_codes_in_summary=False)
        result = build_controlled_universe_export(report, config)
        assert result.per_pair_summary[0].reason_codes == ()


class TestBuildFromRunResult:
    def test_extracts_from_controlled_universe_step(self) -> None:
        items = (
            _make_item(
                "BTC/USDT",
                ControlledUniverseState.INCLUDED,
                ControlledUniverseClassification.LONG_RESEARCH,
            ),
        )
        report = _make_report(items=items, universe=("BTC/USDT",))
        step = self._make_controlled_universe_step(report)
        run_result = self._make_run_result(steps=(step,))
        result = build_controlled_universe_export_from_run_result(run_result)
        assert result.whitelist == ("BTC/USDT",)

    def test_missing_controlled_universe_step(self) -> None:
        run_result = self._make_run_result(steps=())
        result = build_controlled_universe_export_from_run_result(run_result)
        assert result.whitelist == ()
        assert MISSING_REPORT_INPUT in result.reason_codes

    def test_none_run_result(self) -> None:
        result = build_controlled_universe_export_from_run_result(None)  # type: ignore[arg-type]
        assert result.whitelist == ()
        assert MISSING_REPORT_INPUT in result.reason_codes

    def _make_controlled_universe_step(self, report: ControlledUniverseReport) -> Any:
        from hunter.run_orchestrator.models import (
            ResearchRunStepKind,
            ResearchRunStepResult,
            ResearchRunStepState,
        )

        return ResearchRunStepResult(
            step_index=0,
            step_id="cu-1",
            kind=ResearchRunStepKind.CONTROLLED_UNIVERSE,
            state=ResearchRunStepState.SUCCESS,
            reason_codes=(),
            data={"report": report},
            output_paths=(),
            notes=(),
        )

    def _make_run_result(self, steps: tuple[Any, ...]) -> ResearchRunResult:
        from hunter.run_orchestrator.models import (
            ResearchRunConfig,
            ResearchRunDataQuality,
            ResearchRunPlan,
            ResearchRunSafetyFlags,
        )

        return ResearchRunResult(
            run_id="run-1",
            config=ResearchRunConfig(),
            plan=ResearchRunPlan(run_id="run-1", steps=()),
            steps=steps,
            artifacts=(),
            data_quality=ResearchRunDataQuality(),
            safety_flags=ResearchRunSafetyFlags(),
            reason_codes=(),
            generated_at=_dt(),
            state=ResearchRunState.COMPLETED,
            metadata={},
            notes=(),
        )
