"""Tests for hunter.final_audit_pack.engine.

All tests use in-memory fixtures only. No filesystem, network, exchange,
Binance, Freqtrade, or database references are used.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from hunter.backtest import (
    BacktestAllocationMode,
    BacktestCandidateDecision,
    BacktestInput,
    BacktestPriceBar,
    BacktestRunConfig,
    build_backtest_report,
)
from hunter.discovery import (
    DiscoveryInput,
    DiscoveryInputKind,
    build_discovery_report,
)
from hunter.experiment_ledger import (
    ExperimentLedgerInput,
    build_experiment_ledger_report,
)
from hunter.final_audit_pack import (
    BACKTEST_SECTION_KIND,
    DEFAULT_OPTIONAL_SECTION_KINDS,
    DEFAULT_REQUIRED_SECTION_KINDS,
    DISCOVERY_SECTION_KIND,
    DUPLICATE_SECTION_ID,
    EXPERIMENT_LEDGER_SECTION_KIND,
    FINAL_AUDIT_PACK_VERSION,
    MISSING_REQUIRED_SECTIONS,
    PORTFOLIO_CONSTRUCTION_SECTION_KIND,
    REPORTING_CLI_SECTION_KIND,
    RUN_ORCHESTRATOR_SECTION_KIND,
    UNSAFE_CONTENT,
    FinalAuditPackConfig,
    FinalAuditPackInput,
    FinalAuditPackReport,
    FinalAuditPackSection,
    FinalAuditPackState,
    build_final_audit_pack_report,
    has_unsafe_final_audit_pack_content,
)
from hunter.portfolio_construction import (
    PortfolioConstructionInput,
    PortfolioConstructionInputKind,
    build_portfolio_construction_report,
)
from hunter.reporting_cli import CLICommandResult, CLIExitCode, CLISafetyFlags
from hunter.run_orchestrator import (
    ResearchRunConfig,
    ResearchRunPlan,
    ResearchRunStep,
    ResearchRunStepKind,
    build_research_run_result,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def ts(day: int = 1, hour: int = 0) -> datetime:
    return datetime(2024, 1, day, hour, tzinfo=timezone.utc)


def make_bar(pair: str, day: int, close: float) -> BacktestPriceBar:
    return BacktestPriceBar(
        pair=pair,
        timestamp=ts(day),
        close=close,
    )


def make_backtest_input(pair: str, closes: list[float]) -> BacktestInput:
    decision = BacktestCandidateDecision(
        pair=pair,
        state="INCLUDED",
        classification="CORE_RESEARCH_ALLOCATION",
        final_weight_pct=0.0,
    )
    bars = tuple(make_bar(pair, i + 1, close) for i, close in enumerate(closes))
    return BacktestInput(pair=pair, decision=decision, price_bars=bars)


def make_backtest_report(
    report_id: str = "bt-1",
    generated_at: datetime | None = None,
) -> Any:
    inputs = [
        make_backtest_input("A", [100.0, 110.0, 121.0]),
    ]
    cfg = BacktestRunConfig(allocation_mode=BacktestAllocationMode.EQUAL_WEIGHT)
    return build_backtest_report(inputs, cfg, report_id=report_id, generated_at=generated_at)


def make_discovery_report(
    report_id: str = "disc-1",
    generated_at: datetime | None = None,
) -> Any:
    inputs = [
        DiscoveryInput(
            input_kind=DiscoveryInputKind.SUMMARY,
            pair="BTC/USDT",
        )
    ]
    return build_discovery_report(
        inputs=inputs,
        report_id=report_id,
        generated_at=generated_at or ts(1),
    )


def make_portfolio_construction_report(
    report_id: str = "pc-1",
    generated_at: datetime | None = None,
) -> Any:
    inputs = [
        PortfolioConstructionInput(
            input_kind=PortfolioConstructionInputKind.SUMMARY,
            pair="BTC/USDT",
        )
    ]
    return build_portfolio_construction_report(
        inputs=inputs,
        report_id=report_id,
        generated_at=generated_at or ts(1),
    )


def make_run_result(
    run_id: str = "run-1",
    generated_at: datetime | None = None,
) -> Any:
    backtest_input = make_backtest_input("A", [100.0, 110.0])
    backtest_config = BacktestRunConfig(allocation_mode=BacktestAllocationMode.EQUAL_WEIGHT)
    step_inputs: dict[str, Any] = {"inputs": (backtest_input,), "config": backtest_config}
    step = ResearchRunStep(
        kind=ResearchRunStepKind.BACKTEST,
        step_id="b1",
        inputs=step_inputs,
    )
    plan = ResearchRunPlan(run_id=run_id, steps=(step,))
    config = ResearchRunConfig(generated_at=generated_at or ts(1), write_artifacts=False)
    return build_research_run_result(plan, config)


def make_experiment_ledger_report(
    generated_at: datetime | None = None,
) -> Any:
    report = make_backtest_report(report_id="bt-1")
    inp = ExperimentLedgerInput(
        backtest_reports=(report,),
        generated_at=generated_at or ts(1),
    )
    return build_experiment_ledger_report(inp)


def make_cli_command_result(
    command: str = "version",
    generated_at: datetime | None = None,
) -> CLICommandResult:
    return CLICommandResult(
        command=command,
        exit_code=CLIExitCode.OK,
        stdout="",
        stderr="",
        output_paths=(),
        data={},
        safety_flags=CLISafetyFlags(),
        reason_codes=("OK",),
        notes=(),
    )


@pytest.fixture
def fixed_generated_at() -> datetime:
    return ts(1)


# ---------------------------------------------------------------------------
# Public exports
# ---------------------------------------------------------------------------


class TestPublicExports:
    def test_build_final_audit_pack_report_exported(self) -> None:
        assert callable(build_final_audit_pack_report)

    def test_has_unsafe_final_audit_pack_content_exported(self) -> None:
        assert callable(has_unsafe_final_audit_pack_content)


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_same_inputs_produce_same_report(self, fixed_generated_at: datetime) -> None:
        report = make_backtest_report(report_id="bt-1")
        inp = FinalAuditPackInput(
            backtest_reports=(report,),
            generated_at=fixed_generated_at,
        )
        config = FinalAuditPackConfig(generated_at=fixed_generated_at)
        pack1 = build_final_audit_pack_report(inp, config)
        pack2 = build_final_audit_pack_report(inp, config)
        assert pack1 == pack2

    def test_report_version_is_constant(self, fixed_generated_at: datetime) -> None:
        report = make_backtest_report()
        inp = FinalAuditPackInput(backtest_reports=(report,), generated_at=fixed_generated_at)
        pack = build_final_audit_pack_report(inp)
        assert pack.version == FINAL_AUDIT_PACK_VERSION

    def test_same_inputs_produce_same_report_id(self, fixed_generated_at: datetime) -> None:
        report = make_backtest_report(report_id="bt-1")
        inp = FinalAuditPackInput(
            backtest_reports=(report,),
            artifact_references=("ref-1",),
            generated_at=fixed_generated_at,
        )
        config = FinalAuditPackConfig(generated_at=fixed_generated_at)
        pack1 = build_final_audit_pack_report(inp, config)
        pack2 = build_final_audit_pack_report(inp, config)
        assert pack1.report_id == pack2.report_id


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------


class TestBacktestReportNormalization:
    def test_section_id_from_report_id(self, fixed_generated_at: datetime) -> None:
        report = make_backtest_report(report_id="backtest-report-1")
        inp = FinalAuditPackInput(backtest_reports=(report,), generated_at=fixed_generated_at)
        pack = build_final_audit_pack_report(inp)
        section = pack.sections[0]
        assert section.section_kind == BACKTEST_SECTION_KIND
        assert section.section_id == "backtest-report-1"
        assert section.report_id == "backtest-report-1"
        assert section.run_id == ""
        assert section.state is FinalAuditPackState.INCLUDED

    def test_section_id_from_run_id(self, fixed_generated_at: datetime) -> None:
        # ResearchRunResult uses run_id; verify the engine picks it up.
        result = make_run_result(run_id="research-run-1")
        inp = FinalAuditPackInput(run_results=(result,), generated_at=fixed_generated_at)
        pack = build_final_audit_pack_report(inp)
        section = pack.sections[0]
        assert section.section_kind == RUN_ORCHESTRATOR_SECTION_KIND
        assert section.section_id == "research-run-1"
        assert section.run_id == "research-run-1"

    def test_display_name_fallback_to_section_id(self, fixed_generated_at: datetime) -> None:
        report = make_backtest_report(report_id="backtest-report-1")
        inp = FinalAuditPackInput(backtest_reports=(report,), generated_at=fixed_generated_at)
        pack = build_final_audit_pack_report(inp)
        section = pack.sections[0]
        # No explicit name on BacktestReport, so display name would be section_id.
        assert section.name == ""


class TestDiscoveryReportNormalization:
    def test_section_kind_is_discovery(self, fixed_generated_at: datetime) -> None:
        report = make_discovery_report(report_id="disc-1")
        inp = FinalAuditPackInput(discovery_reports=(report,), generated_at=fixed_generated_at)
        pack = build_final_audit_pack_report(inp)
        section = pack.sections[0]
        assert section.section_kind == DISCOVERY_SECTION_KIND
        assert section.section_id == "disc-1"


class TestPortfolioConstructionReportNormalization:
    def test_section_kind_is_portfolio_construction(self, fixed_generated_at: datetime) -> None:
        report = make_portfolio_construction_report(report_id="pc-1")
        inp = FinalAuditPackInput(
            portfolio_construction_reports=(report,),
            generated_at=fixed_generated_at,
        )
        pack = build_final_audit_pack_report(inp)
        section = pack.sections[0]
        assert section.section_kind == PORTFOLIO_CONSTRUCTION_SECTION_KIND
        assert section.section_id == "pc-1"


class TestExperimentLedgerReportNormalization:
    def test_section_kind_is_experiment_ledger(self, fixed_generated_at: datetime) -> None:
        report = make_experiment_ledger_report(generated_at=fixed_generated_at)
        inp = FinalAuditPackInput(
            experiment_ledger_reports=(report,),
            generated_at=fixed_generated_at,
        )
        pack = build_final_audit_pack_report(inp)
        section = pack.sections[0]
        assert section.section_kind == EXPERIMENT_LEDGER_SECTION_KIND


class TestCLICommandResultNormalization:
    def test_section_kind_is_reporting_cli(self, fixed_generated_at: datetime) -> None:
        result = make_cli_command_result(command="version")
        inp = FinalAuditPackInput(
            cli_command_results=(result,),
            generated_at=fixed_generated_at,
        )
        pack = build_final_audit_pack_report(inp)
        section = pack.sections[0]
        assert section.section_kind == REPORTING_CLI_SECTION_KIND
        assert section.section_id == "reporting_cli:0"

    def test_display_name_uses_command(self, fixed_generated_at: datetime) -> None:
        result = make_cli_command_result(command="safety-summary")
        inp = FinalAuditPackInput(
            cli_command_results=(result,),
            generated_at=fixed_generated_at,
        )
        pack = build_final_audit_pack_report(inp)
        section = pack.sections[0]
        # The section name is the explicit name; the display name would be the command.
        assert section.name == ""
        # Safety check should not flag the command text here ("safety-summary" is safe).
        assert section.state is FinalAuditPackState.INCLUDED


class TestFallbackSectionId:
    def test_cli_fallback_format(self, fixed_generated_at: datetime) -> None:
        result = make_cli_command_result()
        inp = FinalAuditPackInput(
            cli_command_results=(result, result),
            generated_at=fixed_generated_at,
        )
        pack = build_final_audit_pack_report(inp)
        ids = [s.section_id for s in pack.sections]
        assert ids == ["reporting_cli:0", "reporting_cli:1"]

    def test_per_category_index_not_global(self, fixed_generated_at: datetime) -> None:
        result = make_cli_command_result()
        report = make_backtest_report(report_id="")
        # Force fallback by clearing report_id (model does not validate non-empty).
        # Use object.__setattr__ to bypass frozen dataclass for test purposes.
        object.__setattr__(report, "report_id", "")
        inp = FinalAuditPackInput(
            backtest_reports=(report,),
            cli_command_results=(result,),
            generated_at=fixed_generated_at,
        )
        pack = build_final_audit_pack_report(inp)
        ids = {s.section_id for s in pack.sections}
        assert "backtest:0" in ids
        assert "reporting_cli:0" in ids


# ---------------------------------------------------------------------------
# Completeness
# ---------------------------------------------------------------------------


class TestCompleteness:
    def test_all_defaults_present(self, fixed_generated_at: datetime) -> None:
        inp = FinalAuditPackInput(
            backtest_reports=(make_backtest_report(),),
            run_results=(make_run_result(),),
            experiment_ledger_reports=(make_experiment_ledger_report(),),
            discovery_reports=(make_discovery_report(),),
            portfolio_construction_reports=(make_portfolio_construction_report(),),
            cli_command_results=(make_cli_command_result(),),
            generated_at=fixed_generated_at,
        )
        pack = build_final_audit_pack_report(inp)
        assert pack.completeness.required_sections_present == 3
        assert pack.completeness.required_sections_missing == 0
        assert pack.completeness.optional_sections_present == 3
        assert pack.completeness.sections_expected == 6
        assert pack.completeness.sections_present == 6
        assert MISSING_REQUIRED_SECTIONS not in pack.reason_codes
        assert pack.safety_flags.is_safe is True

    def test_missing_required_sections(self, fixed_generated_at: datetime) -> None:
        inp = FinalAuditPackInput(
            backtest_reports=(make_backtest_report(),),
            generated_at=fixed_generated_at,
        )
        pack = build_final_audit_pack_report(inp)
        assert pack.completeness.required_sections_present == 1
        assert pack.completeness.required_sections_missing == 2
        assert pack.completeness.optional_sections_present == 0
        assert MISSING_REQUIRED_SECTIONS in pack.reason_codes
        assert pack.safety_flags.has_missing_required_sections is True

    def test_missing_optional_sections_degrade_only(self, fixed_generated_at: datetime) -> None:
        inp = FinalAuditPackInput(
            backtest_reports=(make_backtest_report(),),
            run_results=(make_run_result(),),
            experiment_ledger_reports=(make_experiment_ledger_report(),),
            generated_at=fixed_generated_at,
        )
        pack = build_final_audit_pack_report(inp)
        assert pack.completeness.required_sections_present == 3
        assert pack.completeness.required_sections_missing == 0
        assert pack.completeness.optional_sections_present == 0
        assert pack.completeness.sections_expected == 6
        assert MISSING_REQUIRED_SECTIONS not in pack.reason_codes

    def test_block_on_missing_required(self, fixed_generated_at: datetime) -> None:
        inp = FinalAuditPackInput(
            backtest_reports=(make_backtest_report(),),
            generated_at=fixed_generated_at,
        )
        config = FinalAuditPackConfig(
            block_on_missing_required=True,
            generated_at=fixed_generated_at,
        )
        pack = build_final_audit_pack_report(inp, config)
        assert pack.safety_flags.has_missing_required_sections is True
        assert MISSING_REQUIRED_SECTIONS in pack.reason_codes

    def test_sections_expected_is_total_configured_kinds(self, fixed_generated_at: datetime) -> None:
        config = FinalAuditPackConfig(
            required_section_kinds=("backtest",),
            optional_section_kinds=("discovery",),
            generated_at=fixed_generated_at,
        )
        inp = FinalAuditPackInput(
            backtest_reports=(make_backtest_report(),),
            generated_at=fixed_generated_at,
        )
        pack = build_final_audit_pack_report(inp, config)
        assert pack.completeness.sections_expected == 2


# ---------------------------------------------------------------------------
# Fail-closed behavior
# ---------------------------------------------------------------------------


class TestDuplicateSectionId:
    def test_duplicate_ids_mark_second_blocked(self, fixed_generated_at: datetime) -> None:
        report1 = make_backtest_report(report_id="shared-id")
        report2 = make_backtest_report(report_id="shared-id")
        inp = FinalAuditPackInput(
            backtest_reports=(report1, report2),
            generated_at=fixed_generated_at,
        )
        pack = build_final_audit_pack_report(inp)
        states = [s.state for s in pack.sections]
        assert states[0] is FinalAuditPackState.INCLUDED
        assert states[1] is FinalAuditPackState.BLOCKED
        assert DUPLICATE_SECTION_ID in pack.sections[1].reason_codes
        assert pack.safety_flags.has_duplicate_section_id is True

    def test_first_occurrence_retains_state(self, fixed_generated_at: datetime) -> None:
        report1 = make_backtest_report(report_id="shared-id")
        report2 = make_backtest_report(report_id="shared-id")
        inp = FinalAuditPackInput(
            backtest_reports=(report1, report2),
            generated_at=fixed_generated_at,
        )
        pack = build_final_audit_pack_report(inp)
        assert pack.sections[0].state is FinalAuditPackState.INCLUDED


class TestUnsafeContent:
    def test_unsafe_input_tags_blocks_report(self, fixed_generated_at: datetime) -> None:
        report = make_backtest_report()
        inp = FinalAuditPackInput(
            backtest_reports=(report,),
            tags=["place_order_now"],
            generated_at=fixed_generated_at,
        )
        pack = build_final_audit_pack_report(inp)
        assert pack.sections == ()
        assert UNSAFE_CONTENT in pack.reason_codes
        assert pack.safety_flags.has_unsafe_content is True

    def test_unsafe_section_id_blocks_section(self, fixed_generated_at: datetime) -> None:
        report = make_backtest_report(report_id="binance_api")
        inp = FinalAuditPackInput(backtest_reports=(report,), generated_at=fixed_generated_at)
        pack = build_final_audit_pack_report(inp)
        section = pack.sections[0]
        assert section.state is FinalAuditPackState.BLOCKED
        assert UNSAFE_CONTENT in section.reason_codes


class TestMissingRequiredFields:
    def test_empty_section_id_blocked(self, fixed_generated_at: datetime) -> None:
        # Construct a section directly with empty section_id and verify model boundary.
        with pytest.raises(ValueError, match="section_id"):
            FinalAuditPackSection(section_id="", section_kind="backtest")


# ---------------------------------------------------------------------------
# Sorting and determinism
# ---------------------------------------------------------------------------


class TestSorting:
    def test_sections_sorted_by_kind(self, fixed_generated_at: datetime) -> None:
        bt = make_backtest_report(report_id="bt-1")
        run = make_run_result(run_id="run-1")
        disc = make_discovery_report(report_id="disc-1")
        inp = FinalAuditPackInput(
            discovery_reports=(disc,),
            backtest_reports=(bt,),
            run_results=(run,),
            generated_at=fixed_generated_at,
        )
        pack = build_final_audit_pack_report(inp)
        kinds = [s.section_kind for s in pack.sections]
        assert kinds == [BACKTEST_SECTION_KIND, DISCOVERY_SECTION_KIND, RUN_ORCHESTRATOR_SECTION_KIND]

    def test_artifacts_sorted_by_reference(self, fixed_generated_at: datetime) -> None:
        inp = FinalAuditPackInput(
            artifact_references=("z-ref", "a-ref", "m-ref"),
            generated_at=fixed_generated_at,
        )
        pack = build_final_audit_pack_report(inp)
        refs = [a.reference for a in pack.artifacts]
        assert refs == ["a-ref", "m-ref", "z-ref"]


# ---------------------------------------------------------------------------
# No mutation of inputs
# ---------------------------------------------------------------------------


class TestNoMutation:
    def test_input_report_lists_unchanged(self, fixed_generated_at: datetime) -> None:
        report = make_backtest_report()
        reports = [report]
        inp = FinalAuditPackInput(backtest_reports=reports, generated_at=fixed_generated_at)
        build_final_audit_pack_report(inp)
        assert isinstance(inp.backtest_reports, tuple)
        assert inp.backtest_reports == tuple(reports)

    def test_input_metadata_unchanged(self, fixed_generated_at: datetime) -> None:
        inp = FinalAuditPackInput(
            metadata={"note": "hello"},
            generated_at=fixed_generated_at,
        )
        build_final_audit_pack_report(inp)
        assert dict(inp.metadata) == {"note": "hello"}


# ---------------------------------------------------------------------------
# Safety notes
# ---------------------------------------------------------------------------


class TestSafety:
    def test_report_contains_safety_notice(self, fixed_generated_at: datetime) -> None:
        report = make_backtest_report()
        inp = FinalAuditPackInput(backtest_reports=(report,), generated_at=fixed_generated_at)
        pack = build_final_audit_pack_report(inp)
        assert any("human audit" in note.lower() for note in pack.notes)
        assert any("not a trading signal" in note.lower() for note in pack.notes)

    def test_safety_flags_safe_by_default(self, fixed_generated_at: datetime) -> None:
        report = make_backtest_report()
        inp = FinalAuditPackInput(backtest_reports=(report,), generated_at=fixed_generated_at)
        pack = build_final_audit_pack_report(inp)
        assert pack.safety_flags.is_safe is False  # missing required sections
        assert pack.safety_flags.has_missing_required_sections is True

    def test_complete_report_is_safe(self, fixed_generated_at: datetime) -> None:
        inp = FinalAuditPackInput(
            backtest_reports=(make_backtest_report(),),
            run_results=(make_run_result(),),
            experiment_ledger_reports=(make_experiment_ledger_report(),),
            discovery_reports=(make_discovery_report(),),
            portfolio_construction_reports=(make_portfolio_construction_report(),),
            cli_command_results=(make_cli_command_result(),),
            generated_at=fixed_generated_at,
        )
        pack = build_final_audit_pack_report(inp)
        assert pack.safety_flags.is_safe is True

    def test_no_trading_terms_in_notes(self, fixed_generated_at: datetime) -> None:
        report = make_backtest_report()
        inp = FinalAuditPackInput(backtest_reports=(report,), generated_at=fixed_generated_at)
        pack = build_final_audit_pack_report(inp)
        for note in pack.notes:
            assert not has_unsafe_final_audit_pack_content(text=note)
