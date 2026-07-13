"""Integration tests for controlled_universe_export_adapter.

End-to-end tests from ResearchRunResult through export artifact writing.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

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
    build_controlled_universe_export_from_run_result,
    write_controlled_universe_export,
)
from hunter.market_state.models import AllowedMode
from hunter.run_orchestrator.models import (
    ResearchRunConfig,
    ResearchRunDataQuality,
    ResearchRunPlan,
    ResearchRunResult,
    ResearchRunSafetyFlags,
    ResearchRunState,
    ResearchRunStepKind,
    ResearchRunStepResult,
    ResearchRunStepState,
)


def _dt() -> datetime:
    return datetime(2026, 7, 13, 12, 0, 0, tzinfo=timezone.utc)


def _make_report(
    *,
    items: tuple[ControlledUniverseItem, ...] = (),
    safe: bool = True,
) -> ControlledUniverseReport:
    universe = tuple(item.pair for item in items if item.state == ControlledUniverseState.INCLUDED)
    watchlist = tuple(item.pair for item in items if item.state == ControlledUniverseState.WATCHLIST)
    blocked = tuple(item.pair for item in items if item.state == ControlledUniverseState.BLOCKED)
    excluded = tuple(item.pair for item in items if item.state == ControlledUniverseState.EXCLUDED)
    insufficient = tuple(
        item.pair for item in items if item.state == ControlledUniverseState.INSUFFICIENT_DATA
    )
    all_blocked = blocked + excluded + insufficient
    return ControlledUniverseReport(
        version=CONTROLLED_UNIVERSE_VERSION,
        generated_at=_dt(),
        config=ControlledUniverseConfig(),
        execution_state="STABLE",
        allowed_mode=AllowedMode.LONG_ONLY.value if safe else AllowedMode.NONE.value,
        universe=universe,
        watchlist=watchlist,
        blocked=all_blocked,
        items=items,
        data_quality=ControlledUniverseDataQuality(
            total_inputs=len(items),
            universe_count=len(universe),
            watchlist_count=len(watchlist),
            blocked_count=len(blocked),
            excluded_count=len(excluded),
            insufficient_data_count=len(insufficient),
        ),
        safety_flags=ControlledUniverseSafetyFlags(
            has_unsafe_content=False,
            has_blocked_execution=not safe,
        ),
        reason_codes=("PASSED_UNIVERSE_FILTER",) if safe and universe else ("MACRO_MODE_NONE",),
        metadata={"report_id": "cu-report-1"},
        notes=(),
    )


def _make_run_result(
    report: ControlledUniverseReport | None,
    *,
    blocked: bool = False,
) -> ResearchRunResult:
    step_data = {"report": report} if report is not None else {}
    step_state = ResearchRunStepState.BLOCKED if blocked else ResearchRunStepState.SUCCESS
    step = ResearchRunStepResult(
        step_index=0,
        step_id="cu-1",
        kind=ResearchRunStepKind.CONTROLLED_UNIVERSE,
        state=step_state,
        reason_codes=(),
        data=step_data,
        output_paths=(),
        notes=(),
    )
    return ResearchRunResult(
        run_id="run-1",
        config=ResearchRunConfig(),
        plan=ResearchRunPlan(run_id="run-1", steps=()),
        steps=(step,),
        artifacts=(),
        data_quality=ResearchRunDataQuality(),
        safety_flags=ResearchRunSafetyFlags(),
        reason_codes=(),
        generated_at=_dt(),
        state=ResearchRunState.BLOCKED if blocked else ResearchRunState.COMPLETED,
        metadata={},
        notes=(),
    )


class TestEndToEndExport:
    def test_run_result_to_written_files(self, tmp_path: Path) -> None:
        items = (
            ControlledUniverseItem(
                pair="BTC/USDT",
                state=ControlledUniverseState.INCLUDED,
                classification=ControlledUniverseClassification.LONG_RESEARCH,
                reason_codes=("PASSED_UNIVERSE_FILTER",),
            ),
            ControlledUniverseItem(
                pair="SOL/USDT",
                state=ControlledUniverseState.BLOCKED,
                classification=ControlledUniverseClassification.BLOCKED_BY_MACRO,
                reason_codes=("MACRO_MODE_NONE",),
            ),
        )
        report = _make_report(items=items)
        run_result = _make_run_result(report)
        export = build_controlled_universe_export_from_run_result(
            run_result, ControlledUniverseExportConfig()
        )
        config = ControlledUniverseExportConfig(
            output_dir=str(tmp_path / "data"),
            markdown_output_dir=str(tmp_path / "reports"),
        )
        json_path, md_path = write_controlled_universe_export(export, config=config)
        assert json_path is not None
        assert md_path is not None

        data = json.loads(json_path.read_text())
        assert data["whitelist"] == ["BTC/USDT"]
        assert data["blacklist"] == ["SOL/USDT"]
        assert data["research_only"] is True
        assert data["human_approval_required"] is True

        text = md_path.read_text()
        assert "## Whitelist" in text
        assert "BTC/USDT" in text
        assert "## Blacklist" in text
        assert "SOL/USDT" in text

    def test_blocked_run_result_empty_whitelist(self, tmp_path: Path) -> None:
        items = (
            ControlledUniverseItem(
                pair="BTC/USDT",
                state=ControlledUniverseState.INCLUDED,
                classification=ControlledUniverseClassification.LONG_RESEARCH,
                reason_codes=("PASSED_UNIVERSE_FILTER",),
            ),
        )
        report = _make_report(items=items, safe=True)
        run_result = _make_run_result(report, blocked=True)
        export = build_controlled_universe_export_from_run_result(
            run_result, ControlledUniverseExportConfig()
        )
        assert export.whitelist == ()
        assert export.blacklist == ("BTC/USDT",)
        assert BLOCKED_EXPORT in export.reason_codes

    def test_no_controlled_universe_step_fail_closed(self, tmp_path: Path) -> None:
        run_result = ResearchRunResult(
            run_id="run-1",
            config=ResearchRunConfig(),
            plan=ResearchRunPlan(run_id="run-1", steps=()),
            steps=(),
            artifacts=(),
            data_quality=ResearchRunDataQuality(),
            safety_flags=ResearchRunSafetyFlags(),
            reason_codes=(),
            generated_at=_dt(),
            state=ResearchRunState.COMPLETED,
            metadata={},
            notes=(),
        )
        export = build_controlled_universe_export_from_run_result(
            run_result, ControlledUniverseExportConfig()
        )
        assert export.whitelist == ()
        assert MISSING_REPORT_INPUT in export.reason_codes
        assert EXPORT_RESEARCH_ONLY in export.reason_codes
        assert EXPORT_HUMAN_APPROVAL_REQUIRED in export.reason_codes
        assert NO_FREQTRADE_RUNTIME_CONNECTION in export.reason_codes
        assert NO_AUTOMATIC_CONFIG_MUTATION in export.reason_codes
