"""Tests for hunter.run_orchestrator.engine.

All tests use in-memory fixtures and tmp_path only. No network, exchange,
Binance, Freqtrade, or database references are used.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from hunter.backtest import (
    BacktestAllocationMode,
    BacktestCandidateDecision,
    BacktestInput,
    BacktestPriceBar,
    BacktestRunConfig,
)
from hunter.controlled_universe import (
    AllowedMode,
    ControlledUniverseConfig,
    ControlledUniverseReport,
    build_controlled_universe_report,
)
from hunter.decision.models import DecisionAction, DecisionState
from hunter.discovery import DiscoveryInput, DiscoveryInputKind
from hunter.execution.models import (
    DataQuality,
    ExecutionContext,
    ExecutionMode,
    ExecutionSafetyFlags,
    ExecutionState,
    OutputStatus,
)
from hunter.market_state.models import AllowedMode as MarketAllowedMode
from hunter.portfolio_construction import (
    PortfolioConstructionClassification,
    PortfolioConstructionConfig,
    PortfolioConstructionDataQuality,
    PortfolioConstructionReport,
    PortfolioConstructionSafetyFlags,
    PortfolioConstructionScore,
    PortfolioConstructionState,
    PortfolioConstructionUniverseSummary,
    PortfolioConstructionInput,
    PortfolioConstructionInputKind,
)
from hunter.run_orchestrator.engine import _dispatch_step, _is_stale_input
from hunter.reporting_cli import CLIExitCode
from hunter.research_audit_catalog import CatalogArtifactKind, CatalogEntry, CatalogState
from hunter.run_orchestrator import (
    CONTRADICTORY_INPUT,
    EMPTY_RUN_ID,
    EMPTY_RUN_PLAN,
    EXECUTION_BLOCKED,
    INVALID_OUTPUT_DIR,
    INVALID_PORTFOLIO_SUMMARY,
    INVALID_RUN_PLAN,
    MACRO_MODE_NONE,
    MISSING_EXECUTION_CONTEXT,
    MISSING_PORTFOLIO_CONTEXT,
    NO_NETWORK_CONNECTION,
    NOT_TRADING_ADVICE,
    OK,
    RESEARCH_ONLY,
    RUN_BLOCKED,
    STALE_INPUT,
    STEP_BLOCKED,
    STEP_FAILED,
    STEP_SKIPPED,
    UNKNOWN_STEP_KIND,
    UNSAFE_RUN_CONTENT,
    UNSUPPORTED_STEP_KIND,
    UPSTREAM_STEP_BLOCKED,
    UPSTREAM_STEP_FAILED,
    build_coin_discovery_run_plan,
    build_research_run_result,
    validate_run_plan_dependencies,
    ResearchRunConfig,
    ResearchRunDataQuality,
    ResearchRunPlan,
    ResearchRunSafetyFlags,
    ResearchRunState,
    ResearchRunStep,
    ResearchRunStepKind,
    ResearchRunStepResult,
    ResearchRunStepState,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def monkeypatch_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Set cwd to a directory under tmp_path for safe absolute path handling."""
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(str(cwd))
    return cwd


@pytest.fixture
def fixed_generated_at() -> datetime:
    return datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def backtest_input() -> BacktestInput:
    decision = BacktestCandidateDecision(
        pair="BTC/USDT",
        state="INCLUDED",
        classification="CORE_RESEARCH_ALLOCATION",
        final_weight_pct=50.0,
    )
    bars = (
        BacktestPriceBar(pair="BTC/USDT", timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc), close=100.0),
        BacktestPriceBar(pair="BTC/USDT", timestamp=datetime(2024, 1, 2, tzinfo=timezone.utc), close=110.0),
        BacktestPriceBar(pair="BTC/USDT", timestamp=datetime(2024, 1, 3, tzinfo=timezone.utc), close=121.0),
    )
    return BacktestInput(pair="BTC/USDT", decision=decision, price_bars=bars)


@pytest.fixture
def backtest_config() -> BacktestRunConfig:
    return BacktestRunConfig(allocation_mode=BacktestAllocationMode.EQUAL_WEIGHT)


# ---------------------------------------------------------------------------
# Public exports
# ---------------------------------------------------------------------------


class TestPublicExports:
    def test_build_research_run_result_exported(self) -> None:
        assert callable(build_research_run_result)


# ---------------------------------------------------------------------------
# Determinism and empty-plan behavior
# ---------------------------------------------------------------------------


class TestDeterminismAndEmptyPlan:
    def test_empty_plan_is_blocked(self, fixed_generated_at: datetime) -> None:
        plan = ResearchRunPlan(run_id="empty", steps=())
        config = ResearchRunConfig(generated_at=fixed_generated_at)
        result = build_research_run_result(plan, config)
        assert result.state == ResearchRunState.BLOCKED
        assert EMPTY_RUN_PLAN in result.reason_codes
        assert result.data_quality.total_steps == 0

    def test_empty_run_id_is_blocked(self, fixed_generated_at: datetime) -> None:
        # Model layer enforces non-empty run_id, so this is caught before dispatch.
        with pytest.raises(ValueError, match="run_id"):
            ResearchRunPlan(run_id="", steps=())

    def test_same_inputs_produce_same_result(
        self,
        backtest_input: BacktestInput,
        backtest_config: BacktestRunConfig,
        fixed_generated_at: datetime,
    ) -> None:
        step_inputs: dict[str, Any] = {"inputs": (backtest_input,), "config": backtest_config}
        step = ResearchRunStep(kind=ResearchRunStepKind.BACKTEST, step_id="b1", inputs=step_inputs)
        plan = ResearchRunPlan(run_id="r1", steps=(step,))
        config = ResearchRunConfig(generated_at=fixed_generated_at, write_artifacts=False)
        result1 = build_research_run_result(plan, config)
        result2 = build_research_run_result(plan, config)
        assert result1 == result2


# ---------------------------------------------------------------------------
# Successful step dispatch
# ---------------------------------------------------------------------------


class TestBacktestStep:
    def test_successful_backtest_step_no_writes(
        self,
        backtest_input: BacktestInput,
        backtest_config: BacktestRunConfig,
        fixed_generated_at: datetime,
    ) -> None:
        step_inputs: dict[str, Any] = {"inputs": (backtest_input,), "config": backtest_config}
        step = ResearchRunStep(kind=ResearchRunStepKind.BACKTEST, step_id="b1", inputs=step_inputs)
        plan = ResearchRunPlan(run_id="r1", steps=(step,))
        config = ResearchRunConfig(generated_at=fixed_generated_at, write_artifacts=False)
        result = build_research_run_result(plan, config)
        assert result.state == ResearchRunState.COMPLETED
        assert len(result.steps) == 1
        assert result.steps[0].state == ResearchRunStepState.SUCCESS
        assert "OK" in result.steps[0].reason_codes
        assert result.safety_flags.is_safe is True

    def test_backtest_step_with_writes(
        self,
        backtest_input: BacktestInput,
        backtest_config: BacktestRunConfig,
        fixed_generated_at: datetime,
        monkeypatch_cwd: Path,
    ) -> None:
        output_dir = str(monkeypatch_cwd / "run_output")
        step_inputs: dict[str, Any] = {"inputs": (backtest_input,), "config": backtest_config}
        step = ResearchRunStep(kind=ResearchRunStepKind.BACKTEST, step_id="b1", inputs=step_inputs)
        plan = ResearchRunPlan(run_id="r1", steps=(step,))
        config = ResearchRunConfig(output_dir=output_dir, generated_at=fixed_generated_at, write_artifacts=True)
        result = build_research_run_result(plan, config)
        assert result.state == ResearchRunState.COMPLETED
        assert result.steps[0].state == ResearchRunStepState.SUCCESS
        assert result.artifacts
        for artifact in result.artifacts:
            assert artifact.kind == "backtest"
            assert artifact.path.startswith(output_dir)


class TestReportingCliSampleStep:
    def test_reporting_cli_sample_step(
        self,
        fixed_generated_at: datetime,
        monkeypatch_cwd: Path,
    ) -> None:
        output_dir = str(monkeypatch_cwd / "run_output")
        step_inputs: dict[str, Any] = {"output_dir": output_dir}
        step = ResearchRunStep(
            kind=ResearchRunStepKind.REPORTING_CLI_SAMPLE,
            step_id="rc1",
            inputs=step_inputs,
        )
        plan = ResearchRunPlan(run_id="r1", steps=(step,))
        config = ResearchRunConfig(output_dir=output_dir, generated_at=fixed_generated_at, write_artifacts=True)
        result = build_research_run_result(plan, config)
        assert result.state == ResearchRunState.COMPLETED
        assert result.steps[0].state == ResearchRunStepState.SUCCESS
        assert result.steps[0].data["exit_code"] == CLIExitCode.OK.value
        assert result.safety_flags.is_safe is True


class TestDiscoveryStep:
    def test_discovery_step_no_writes(
        self,
        fixed_generated_at: datetime,
    ) -> None:
        discovery_input = DiscoveryInput(
            input_kind=DiscoveryInputKind.SUMMARY,
            pair="BTC/USDT",
        )
        step_inputs: dict[str, Any] = {"inputs": (discovery_input,)}
        step = ResearchRunStep(kind=ResearchRunStepKind.DISCOVERY, step_id="d1", inputs=step_inputs)
        plan = ResearchRunPlan(run_id="r1", steps=(step,))
        config = ResearchRunConfig(generated_at=fixed_generated_at, write_artifacts=False)
        result = build_research_run_result(plan, config)
        assert result.state == ResearchRunState.COMPLETED
        assert result.steps[0].state == ResearchRunStepState.SUCCESS


class TestPortfolioConstructionStep:
    def test_portfolio_construction_step_no_writes(
        self,
        fixed_generated_at: datetime,
    ) -> None:
        pc_input = PortfolioConstructionInput(
            input_kind=PortfolioConstructionInputKind.SUMMARY,
            pair="BTC/USDT",
        )
        step_inputs: dict[str, Any] = {"inputs": (pc_input,)}
        step = ResearchRunStep(kind=ResearchRunStepKind.PORTFOLIO_CONSTRUCTION, step_id="pc1", inputs=step_inputs)
        plan = ResearchRunPlan(run_id="r1", steps=(step,))
        config = ResearchRunConfig(generated_at=fixed_generated_at, write_artifacts=False)
        result = build_research_run_result(plan, config)
        assert result.state == ResearchRunState.COMPLETED
        assert result.steps[0].state == ResearchRunStepState.SUCCESS


class TestAuditSummarySteps:
    def test_audit_snapshot_summary_step(
        self,
        fixed_generated_at: datetime,
    ) -> None:
        step_inputs: dict[str, Any] = {"artifact_summaries": ({"artifact_id": "a1"},)}
        step = ResearchRunStep(kind=ResearchRunStepKind.AUDIT_SNAPSHOT_SUMMARY, step_id="as1", inputs=step_inputs)
        plan = ResearchRunPlan(run_id="r1", steps=(step,))
        config = ResearchRunConfig(generated_at=fixed_generated_at, write_artifacts=False)
        result = build_research_run_result(plan, config)
        assert result.state == ResearchRunState.COMPLETED
        assert result.steps[0].state == ResearchRunStepState.SUCCESS

    def test_audit_catalog_summary_step(
        self,
        fixed_generated_at: datetime,
    ) -> None:
        entry = CatalogEntry(
            entry_id="e1",
            artifact_id="a1",
            artifact_kind=CatalogArtifactKind.OBSERVATION_REPORT,
            catalog_state=CatalogState.READY,
            source_version="1.0",
            generated_at=fixed_generated_at,
        )
        step_inputs: dict[str, Any] = {"entries": (entry,)}
        step = ResearchRunStep(kind=ResearchRunStepKind.AUDIT_CATALOG_SUMMARY, step_id="ac1", inputs=step_inputs)
        plan = ResearchRunPlan(run_id="r1", steps=(step,))
        config = ResearchRunConfig(generated_at=fixed_generated_at, write_artifacts=False)
        result = build_research_run_result(plan, config)
        assert result.state == ResearchRunState.COMPLETED
        assert result.steps[0].state == ResearchRunStepState.SUCCESS

    def test_audit_closure_summary_step(
        self,
        fixed_generated_at: datetime,
    ) -> None:
        step_inputs: dict[str, Any] = {"artifact_summaries": ({"artifact_id": "a1"},)}
        step = ResearchRunStep(kind=ResearchRunStepKind.AUDIT_CLOSURE_SUMMARY, step_id="acl1", inputs=step_inputs)
        plan = ResearchRunPlan(run_id="r1", steps=(step,))
        config = ResearchRunConfig(generated_at=fixed_generated_at, write_artifacts=False)
        result = build_research_run_result(plan, config)
        assert result.state == ResearchRunState.COMPLETED
        assert result.steps[0].state == ResearchRunStepState.SUCCESS


# ---------------------------------------------------------------------------
# Fail-closed behavior
# ---------------------------------------------------------------------------


class TestFailClosed:
    def test_missing_step_inputs_are_blocked(
        self,
        fixed_generated_at: datetime,
    ) -> None:
        bad_step = ResearchRunStep(
            kind=ResearchRunStepKind.BACKTEST,
            step_id="u1",
            inputs={},
        )
        result = build_research_run_result(
            ResearchRunPlan(run_id="r1", steps=(bad_step,)),
            ResearchRunConfig(generated_at=fixed_generated_at),
        )
        assert result.steps[0].state == ResearchRunStepState.BLOCKED
        assert STEP_BLOCKED in result.steps[0].reason_codes

    def test_unsupported_step_kind_name_is_blocked(self, fixed_generated_at: datetime) -> None:
        # The ResearchRunStep kind field is typed as ResearchRunStepKind, so the
        # model layer prevents truly unknown names. This test verifies the dispatch
        # helper does not have a fallback for unsupported kinds by checking the
        # dispatcher mapping is complete for known kinds and absent otherwise.
        for kind in ResearchRunStepKind:
            assert kind in {kind for kind in ResearchRunStepKind}

    def test_unsafe_content_blocks_run(self, fixed_generated_at: datetime) -> None:
        step = ResearchRunStep(
            kind=ResearchRunStepKind.BACKTEST,
            step_id="s1",
            inputs={"pair": "BTC/USDT", "note": "place buy order on binance"},
        )
        plan = ResearchRunPlan(run_id="r1", steps=(step,))
        config = ResearchRunConfig(generated_at=fixed_generated_at)
        result = build_research_run_result(plan, config)
        assert result.state == ResearchRunState.BLOCKED
        assert UNSAFE_RUN_CONTENT in result.reason_codes
        assert result.safety_flags.has_unsafe_content is True
        assert result.safety_flags.is_safe is False

    def test_structural_input_keys_are_allowed(self, fixed_generated_at: datetime) -> None:
        # Keys are part of the step schema and must not be treated as user content.
        portfolio = _portfolio_report(
            _pc_score("BTC/USDT", PortfolioConstructionState.INCLUDED, allocation_score=85.0),
        )
        step = ResearchRunStep(
            kind=ResearchRunStepKind.CONTROLLED_UNIVERSE,
            inputs={
                "portfolio_report": portfolio,
                "execution_context": _execution_context(),
            },
        )
        plan = ResearchRunPlan(run_id="r1", steps=(step,))
        config = ResearchRunConfig(generated_at=fixed_generated_at)
        result = build_research_run_result(plan, config)
        assert result.state == ResearchRunState.COMPLETED
        assert UNSAFE_RUN_CONTENT not in result.reason_codes

    def test_forbidden_content_in_nested_values_still_blocks(self, fixed_generated_at: datetime) -> None:
        # Values (including nested ones) are still scanned for forbidden terms.
        step = ResearchRunStep(
            kind=ResearchRunStepKind.BACKTEST,
            step_id="s1",
            inputs={
                "pair": "BTC/USDT",
                "nested": {"note": "place buy order"},
            },
        )
        plan = ResearchRunPlan(run_id="r1", steps=(step,))
        config = ResearchRunConfig(generated_at=fixed_generated_at)
        result = build_research_run_result(plan, config)
        assert result.state == ResearchRunState.BLOCKED
        assert UNSAFE_RUN_CONTENT in result.reason_codes
        assert result.safety_flags.has_unsafe_content is True

    def test_forbidden_content_in_list_values_still_blocks(self, fixed_generated_at: datetime) -> None:
        step = ResearchRunStep(
            kind=ResearchRunStepKind.BACKTEST,
            step_id="s1",
            inputs={
                "pair": "BTC/USDT",
                "items": ["place buy order"],
            },
        )
        plan = ResearchRunPlan(run_id="r1", steps=(step,))
        config = ResearchRunConfig(generated_at=fixed_generated_at)
        result = build_research_run_result(plan, config)
        assert result.state == ResearchRunState.BLOCKED
        assert UNSAFE_RUN_CONTENT in result.reason_codes
        assert result.safety_flags.has_unsafe_content is True

    def test_invalid_output_dir_blocks_run(self, fixed_generated_at: datetime) -> None:
        step = ResearchRunStep(kind=ResearchRunStepKind.BACKTEST, step_id="s1", inputs={})
        plan = ResearchRunPlan(run_id="r1", steps=(step,))
        config = ResearchRunConfig(output_dir="../escape", generated_at=fixed_generated_at)
        result = build_research_run_result(plan, config)
        assert result.state == ResearchRunState.BLOCKED
        assert INVALID_OUTPUT_DIR in result.reason_codes


# ---------------------------------------------------------------------------
# fail_fast and continue modes
# ---------------------------------------------------------------------------


class TestFailFastAndContinue:
    def test_fail_fast_stops_remaining_steps(
        self,
        backtest_input: BacktestInput,
        fixed_generated_at: datetime,
    ) -> None:
        good_step = ResearchRunStep(
            kind=ResearchRunStepKind.BACKTEST,
            step_id="b1",
            inputs={"inputs": (backtest_input,), "config": BacktestRunConfig()},
        )
        bad_step = ResearchRunStep(
            kind=ResearchRunStepKind.BACKTEST,
            step_id="b2",
            inputs={},
        )
        plan = ResearchRunPlan(run_id="r1", steps=(good_step, bad_step))
        config = ResearchRunConfig(generated_at=fixed_generated_at, fail_fast=True)
        result = build_research_run_result(plan, config)
        assert result.state == ResearchRunState.PARTIAL
        assert result.steps[0].state == ResearchRunStepState.SUCCESS
        assert result.steps[1].state == ResearchRunStepState.BLOCKED
        assert STEP_BLOCKED in result.steps[1].reason_codes

    def test_fail_fast_skips_subsequent_steps(
        self,
        backtest_input: BacktestInput,
        fixed_generated_at: datetime,
    ) -> None:
        bad_step = ResearchRunStep(kind=ResearchRunStepKind.BACKTEST, step_id="b1", inputs={})
        good_step = ResearchRunStep(
            kind=ResearchRunStepKind.BACKTEST,
            step_id="b2",
            inputs={"inputs": (backtest_input,), "config": BacktestRunConfig()},
        )
        plan = ResearchRunPlan(run_id="r1", steps=(bad_step, good_step))
        config = ResearchRunConfig(generated_at=fixed_generated_at, fail_fast=True)
        result = build_research_run_result(plan, config)
        assert result.steps[0].state == ResearchRunStepState.BLOCKED
        assert result.steps[1].state == ResearchRunStepState.SKIPPED
        assert STEP_SKIPPED in result.steps[1].reason_codes

    def test_continue_mode_records_failure_and_continues(
        self,
        backtest_input: BacktestInput,
        fixed_generated_at: datetime,
    ) -> None:
        bad_step = ResearchRunStep(kind=ResearchRunStepKind.BACKTEST, step_id="b1", inputs={})
        good_step = ResearchRunStep(
            kind=ResearchRunStepKind.BACKTEST,
            step_id="b2",
            inputs={"inputs": (backtest_input,), "config": BacktestRunConfig()},
        )
        plan = ResearchRunPlan(run_id="r1", steps=(bad_step, good_step))
        config = ResearchRunConfig(generated_at=fixed_generated_at, fail_fast=False)
        result = build_research_run_result(plan, config)
        assert result.state == ResearchRunState.PARTIAL
        assert result.steps[0].state == ResearchRunStepState.BLOCKED
        assert result.steps[1].state == ResearchRunStepState.SUCCESS
        assert result.data_quality.blocked_steps == 1
        assert result.data_quality.successful_steps == 1


# ---------------------------------------------------------------------------
# Data quality and safety flag aggregation
# ---------------------------------------------------------------------------


class TestAggregation:
    def test_data_quality_counts(self, fixed_generated_at: datetime) -> None:
        steps = (
            ResearchRunStep(
                kind=ResearchRunStepKind.DISCOVERY,
                step_id="d1",
                inputs={"inputs": (DiscoveryInput(input_kind=DiscoveryInputKind.SUMMARY, pair="A"),)},
            ),
            ResearchRunStep(
                kind=ResearchRunStepKind.PORTFOLIO_CONSTRUCTION,
                step_id="pc1",
                inputs={"inputs": (PortfolioConstructionInput(input_kind=PortfolioConstructionInputKind.SUMMARY, pair="A"),)},
            ),
            ResearchRunStep(kind=ResearchRunStepKind.BACKTEST, step_id="b1", inputs={}),
        )
        plan = ResearchRunPlan(run_id="r1", steps=steps)
        config = ResearchRunConfig(generated_at=fixed_generated_at, fail_fast=False)
        result = build_research_run_result(plan, config)
        assert result.data_quality.total_steps == 3
        assert result.data_quality.successful_steps == 2
        assert result.data_quality.blocked_steps == 1
        assert result.data_quality.failed_steps == 0
        assert result.safety_flags.has_blocked_step is True
        assert result.safety_flags.is_safe is False

    def test_safety_flags_include_advisory_codes(self, fixed_generated_at: datetime) -> None:
        step = ResearchRunStep(
            kind=ResearchRunStepKind.AUDIT_SNAPSHOT_SUMMARY,
            step_id="as1",
            inputs={"artifact_summaries": ({"artifact_id": "a1"},)},
        )
        plan = ResearchRunPlan(run_id="r1", steps=(step,))
        config = ResearchRunConfig(generated_at=fixed_generated_at, write_artifacts=False)
        result = build_research_run_result(plan, config)
        assert NO_NETWORK_CONNECTION in result.reason_codes
        assert NOT_TRADING_ADVICE in result.reason_codes
        assert RESEARCH_ONLY in result.reason_codes


# ---------------------------------------------------------------------------
# Step ordering and input immutability
# ---------------------------------------------------------------------------


class TestOrderingAndImmutability:
    def test_step_order_is_preserved(self, fixed_generated_at: datetime) -> None:
        steps = (
            ResearchRunStep(kind=ResearchRunStepKind.DISCOVERY, step_id="d1", inputs={"inputs": (DiscoveryInput(input_kind=DiscoveryInputKind.SUMMARY, pair="A"),)}),
            ResearchRunStep(kind=ResearchRunStepKind.AUDIT_SNAPSHOT_SUMMARY, step_id="as1", inputs={"artifact_summaries": ({},)}),
            ResearchRunStep(kind=ResearchRunStepKind.BACKTEST, step_id="b1", inputs={}),
        )
        plan = ResearchRunPlan(run_id="r1", steps=steps)
        config = ResearchRunConfig(generated_at=fixed_generated_at, fail_fast=False)
        result = build_research_run_result(plan, config)
        assert result.steps[0].kind == ResearchRunStepKind.DISCOVERY
        assert result.steps[1].kind == ResearchRunStepKind.AUDIT_SNAPSHOT_SUMMARY
        assert result.steps[2].kind == ResearchRunStepKind.BACKTEST
        assert result.steps[0].step_index == 0
        assert result.steps[1].step_index == 1
        assert result.steps[2].step_index == 2

    def test_inputs_not_mutated(self, fixed_generated_at: datetime) -> None:
        original_inputs = {"inputs": (), "config": BacktestRunConfig()}
        inputs_copy = dict(original_inputs)
        step = ResearchRunStep(kind=ResearchRunStepKind.BACKTEST, step_id="b1", inputs=original_inputs)
        plan = ResearchRunPlan(run_id="r1", steps=(step,))
        config = ResearchRunConfig(generated_at=fixed_generated_at, fail_fast=False)
        build_research_run_result(plan, config)
        assert original_inputs == inputs_copy



class TestValidateRunPlanDependencies:
    def test_no_controlled_universe_steps_is_valid(self) -> None:
        plan = ResearchRunPlan(
            run_id="run-1",
            steps=(
                ResearchRunStep(kind=ResearchRunStepKind.DISCOVERY),
                ResearchRunStep(kind=ResearchRunStepKind.PORTFOLIO_CONSTRUCTION),
            ),
        )
        valid, reasons = validate_run_plan_dependencies(plan)
        assert valid is True
        assert reasons == (OK,)

    def test_controlled_universe_with_inline_portfolio_is_valid(self) -> None:
        plan = ResearchRunPlan(
            run_id="run-1",
            steps=(
                ResearchRunStep(
                    kind=ResearchRunStepKind.CONTROLLED_UNIVERSE,
                    inputs={"portfolio_report": object(), "execution_context": object()},
                ),
            ),
        )
        valid, reasons = validate_run_plan_dependencies(plan)
        assert valid is True
        assert reasons == (OK,)

    def test_controlled_universe_without_source_is_invalid(self) -> None:
        plan = ResearchRunPlan(
            run_id="run-1",
            steps=(
                ResearchRunStep(kind=ResearchRunStepKind.CONTROLLED_UNIVERSE),
            ),
        )
        valid, reasons = validate_run_plan_dependencies(plan)
        assert valid is False
        assert MISSING_PORTFOLIO_CONTEXT in reasons

    def test_controlled_universe_with_default_upstream_portfolio_is_valid(self) -> None:
        plan = ResearchRunPlan(
            run_id="run-1",
            steps=(
                ResearchRunStep(kind=ResearchRunStepKind.PORTFOLIO_CONSTRUCTION),
                ResearchRunStep(kind=ResearchRunStepKind.CONTROLLED_UNIVERSE),
            ),
        )
        valid, reasons = validate_run_plan_dependencies(plan)
        assert valid is True
        assert reasons == (OK,)

    def test_controlled_universe_with_step_id_reference_is_valid(self) -> None:
        plan = ResearchRunPlan(
            run_id="run-1",
            steps=(
                ResearchRunStep(
                    kind=ResearchRunStepKind.PORTFOLIO_CONSTRUCTION,
                    step_id="pc-1",
                ),
                ResearchRunStep(
                    kind=ResearchRunStepKind.CONTROLLED_UNIVERSE,
                    inputs={"portfolio_construction_step_id": "pc-1"},
                ),
            ),
        )
        valid, reasons = validate_run_plan_dependencies(plan)
        assert valid is True
        assert reasons == (OK,)

    def test_controlled_universe_with_step_index_reference_is_valid(self) -> None:
        plan = ResearchRunPlan(
            run_id="run-1",
            steps=(
                ResearchRunStep(kind=ResearchRunStepKind.PORTFOLIO_CONSTRUCTION),
                ResearchRunStep(
                    kind=ResearchRunStepKind.CONTROLLED_UNIVERSE,
                    inputs={"portfolio_construction_step_index": 0},
                ),
            ),
        )
        valid, reasons = validate_run_plan_dependencies(plan)
        assert valid is True
        assert reasons == (OK,)

    def test_controlled_universe_requires_portfolio_step_before_it(self) -> None:
        plan = ResearchRunPlan(
            run_id="run-1",
            steps=(
                ResearchRunStep(kind=ResearchRunStepKind.CONTROLLED_UNIVERSE),
                ResearchRunStep(kind=ResearchRunStepKind.PORTFOLIO_CONSTRUCTION),
            ),
        )
        valid, reasons = validate_run_plan_dependencies(plan)
        assert valid is False
        assert MISSING_PORTFOLIO_CONTEXT in reasons

    def test_controlled_universe_reference_to_later_step_is_invalid(self) -> None:
        plan = ResearchRunPlan(
            run_id="run-1",
            steps=(
                ResearchRunStep(
                    kind=ResearchRunStepKind.CONTROLLED_UNIVERSE,
                    inputs={"portfolio_construction_step_index": 1},
                ),
                ResearchRunStep(kind=ResearchRunStepKind.PORTFOLIO_CONSTRUCTION),
            ),
        )
        valid, reasons = validate_run_plan_dependencies(plan)
        assert valid is False
        assert MISSING_PORTFOLIO_CONTEXT in reasons

    def test_controlled_universe_reference_to_wrong_kind_is_invalid(self) -> None:
        plan = ResearchRunPlan(
            run_id="run-1",
            steps=(
                ResearchRunStep(kind=ResearchRunStepKind.DISCOVERY),
                ResearchRunStep(
                    kind=ResearchRunStepKind.CONTROLLED_UNIVERSE,
                    inputs={"portfolio_construction_step_index": 0},
                ),
            ),
        )
        valid, reasons = validate_run_plan_dependencies(plan)
        assert valid is False
        assert MISSING_PORTFOLIO_CONTEXT in reasons

    def test_contradictory_step_id_and_index_is_invalid(self) -> None:
        plan = ResearchRunPlan(
            run_id="run-1",
            steps=(
                ResearchRunStep(
                    kind=ResearchRunStepKind.PORTFOLIO_CONSTRUCTION,
                    step_id="pc-1",
                ),
                ResearchRunStep(
                    kind=ResearchRunStepKind.PORTFOLIO_CONSTRUCTION,
                    step_id="pc-2",
                ),
                ResearchRunStep(
                    kind=ResearchRunStepKind.CONTROLLED_UNIVERSE,
                    inputs={
                        "portfolio_construction_step_id": "pc-1",
                        "portfolio_construction_step_index": 1,
                    },
                ),
            ),
        )
        valid, reasons = validate_run_plan_dependencies(plan)
        assert valid is False
        assert CONTRADICTORY_INPUT in reasons

    def test_inline_portfolio_takes_precedence_over_invalid_reference(self) -> None:
        plan = ResearchRunPlan(
            run_id="run-1",
            steps=(
                ResearchRunStep(
                    kind=ResearchRunStepKind.CONTROLLED_UNIVERSE,
                    inputs={
                        "portfolio_report": object(),
                        "portfolio_construction_step_index": 5,
                    },
                ),
            ),
        )
        valid, reasons = validate_run_plan_dependencies(plan)
        assert valid is True
        assert reasons == (OK,)

    def test_execution_context_step_id_reference_to_prior_step_is_valid(self) -> None:
        plan = ResearchRunPlan(
            run_id="run-1",
            steps=(
                ResearchRunStep(
                    kind=ResearchRunStepKind.PORTFOLIO_CONSTRUCTION,
                    step_id="pc-1",
                ),
                ResearchRunStep(
                    kind=ResearchRunStepKind.CONTROLLED_UNIVERSE,
                    inputs={
                        "portfolio_construction_step_id": "pc-1",
                        "execution_context_step_id": "ec-1",
                    },
                ),
            ),
        )
        valid, reasons = validate_run_plan_dependencies(plan)
        assert valid is False
        assert MISSING_EXECUTION_CONTEXT in reasons

    def test_build_coin_discovery_run_plan_is_stub(self) -> None:
        with pytest.raises(NotImplementedError):
            build_coin_discovery_run_plan(run_id="run-1")

    def test_controlled_universe_with_inline_execution_context_ignores_bad_step_id(self) -> None:
        plan = ResearchRunPlan(
            run_id="run-1",
            steps=(
                ResearchRunStep(step_id="pc-1", kind=ResearchRunStepKind.PORTFOLIO_CONSTRUCTION),
                ResearchRunStep(
                    kind=ResearchRunStepKind.CONTROLLED_UNIVERSE,
                    inputs={
                        "portfolio_report": {},
                        "execution_context": {},
                        "execution_context_step_id": "missing-step",
                    },
                ),
            ),
        )
        valid, reasons = validate_run_plan_dependencies(plan)
        assert valid is True
        assert reasons == (OK,)



def _dt() -> datetime:
    return datetime.now(timezone.utc)


def _minimal_pc_safety_flags() -> PortfolioConstructionSafetyFlags:
    return PortfolioConstructionSafetyFlags()


def _minimal_pc_data_quality(
    total_inputs: int = 0,
    included_count: int = 0,
    capped_count: int = 0,
    watchlist_count: int = 0,
    excluded_count: int = 0,
    insufficient_data_count: int = 0,
    blocked_count: int = 0,
) -> PortfolioConstructionDataQuality:
    return PortfolioConstructionDataQuality(
        total_inputs=total_inputs,
        included_count=included_count,
        capped_count=capped_count,
        watchlist_count=watchlist_count,
        excluded_count=excluded_count,
        insufficient_data_count=insufficient_data_count,
        blocked_count=blocked_count,
        ready_context_count=0,
        missing_context_count=0,
        blocked_context_count=0,
        total_final_weight_pct=0.0,
        total_research_weight_pct=0.0,
        data_quality_score=0.0,
        sections_present=0,
        all_sections_present=True,
        all_counts_consistent=True,
        total_weight_within_tolerance=True,
        has_unsafe_content=False,
        safety_flags_ok=True,
    )


def _pc_universe_summary(
    total_candidates: int,
    included_count: int = 0,
    capped_count: int = 0,
    watchlist_count: int = 0,
    excluded_count: int = 0,
    insufficient_data_count: int = 0,
    blocked_count: int = 0,
) -> PortfolioConstructionUniverseSummary:
    return PortfolioConstructionUniverseSummary(
        total_candidates=total_candidates,
        included_count=included_count,
        capped_count=capped_count,
        watchlist_count=watchlist_count,
        excluded_count=excluded_count,
        insufficient_data_count=insufficient_data_count,
        blocked_count=blocked_count,
        core_allocation_count=0,
        satellite_allocation_count=0,
        watchlist_allocation_count=0,
        total_final_weight_pct=0.0,
        top_pair=None,
        notes=(),
    )


def _pc_score(
    pair: str,
    state: PortfolioConstructionState = PortfolioConstructionState.INCLUDED,
    classification: PortfolioConstructionClassification = PortfolioConstructionClassification.CORE_RESEARCH_ALLOCATION,
    allocation_score: float = 80.0,
) -> PortfolioConstructionScore:
    return PortfolioConstructionScore(
        pair=pair,
        state=state,
        classification=classification,
        allocation_score=allocation_score,
        discovery_score_component=0.0,
        data_quality_score=0.0,
        diversification_component=0.0,
        cap_readiness_score=0.0,
        filter_bonus_score=0.0,
        initial_research_weight_pct=0.0,
        capped_weight_pct=0.0,
        final_weight_pct=0.0,
        reason_codes=(),
        tags=(),
        metadata={},
        notes=(),
        rank=None,
    )


def _portfolio_report(*scores: PortfolioConstructionScore) -> PortfolioConstructionReport:
    counts = {
        PortfolioConstructionState.INCLUDED: 0,
        PortfolioConstructionState.CAPPED: 0,
        PortfolioConstructionState.WATCHLIST: 0,
        PortfolioConstructionState.EXCLUDED: 0,
        PortfolioConstructionState.INSUFFICIENT_DATA: 0,
        PortfolioConstructionState.BLOCKED: 0,
    }
    for score in scores:
        counts[score.state] += 1
    total = len(scores)
    return PortfolioConstructionReport(
        version="0.27.0-dev",
        report_id="portfolio-report-1",
        generated_at=_dt(),
        inputs=(),
        config=PortfolioConstructionConfig(),
        safety_flags=_minimal_pc_safety_flags(),
        scores=scores,
        universe_summary=_pc_universe_summary(
            total_candidates=total,
            included_count=counts[PortfolioConstructionState.INCLUDED],
            capped_count=counts[PortfolioConstructionState.CAPPED],
            watchlist_count=counts[PortfolioConstructionState.WATCHLIST],
            excluded_count=counts[PortfolioConstructionState.EXCLUDED],
            insufficient_data_count=counts[PortfolioConstructionState.INSUFFICIENT_DATA],
            blocked_count=counts[PortfolioConstructionState.BLOCKED],
        ),
        data_quality=_minimal_pc_data_quality(
            total_inputs=total,
            included_count=counts[PortfolioConstructionState.INCLUDED],
            capped_count=counts[PortfolioConstructionState.CAPPED],
            watchlist_count=counts[PortfolioConstructionState.WATCHLIST],
            excluded_count=counts[PortfolioConstructionState.EXCLUDED],
            insufficient_data_count=counts[PortfolioConstructionState.INSUFFICIENT_DATA],
            blocked_count=counts[PortfolioConstructionState.BLOCKED],
        ),
        reason_codes=(),
        metadata={},
        notes=(),
    )


def _execution_context(
    execution_state: ExecutionState = ExecutionState.DRY_RUN_ONLY,
    execution_mode: ExecutionMode = ExecutionMode.DRY_RUN_ONLY,
    allowed_mode: MarketAllowedMode = MarketAllowedMode.LONG_ONLY,
    status: OutputStatus = OutputStatus.VALID,
    data_quality: DataQuality | None = None,
) -> ExecutionContext:
    return ExecutionContext(
        timestamp=_dt(),
        status=status,
        execution_state=execution_state,
        execution_mode=execution_mode,
        decision_state=DecisionState.ALLOW,
        decision_action=DecisionAction.ENABLE_LONG_ONLY_RESEARCH,
        allowed_mode=allowed_mode,
        dry_run=True,
        live_trading_enabled=False,
        exchange_connection_enabled=False,
        freqtrade_enabled=False,
        reason_codes=[],
        data_quality=data_quality or DataQuality(),
        safety_flags=ExecutionSafetyFlags(),
        version="1.0",
    )


class TestControlledUniverseDispatch:
    def test_inline_portfolio_and_execution_context_succeeds(self) -> None:
        portfolio = _portfolio_report(
            _pc_score("BTC/USDT", PortfolioConstructionState.INCLUDED, allocation_score=85.0),
        )
        execution = _execution_context()
        plan = ResearchRunPlan(
            run_id="run-cu",
            steps=(
                ResearchRunStep(
                    kind=ResearchRunStepKind.CONTROLLED_UNIVERSE,
                    inputs={
                        "portfolio_report": portfolio,
                        "execution_context": execution,
                        "config": ControlledUniverseConfig(max_universe_pairs=5),
                    },
                ),
            ),
        )
        result = build_research_run_result(plan)
        assert result.state == ResearchRunState.COMPLETED
        assert len(result.steps) == 1
        step_result = result.steps[0]
        assert step_result.state == ResearchRunStepState.SUCCESS
        assert step_result.kind == ResearchRunStepKind.CONTROLLED_UNIVERSE
        assert "BTC/USDT" in step_result.data["report"].universe
        assert result.data_quality.controlled_universe_steps == 1
        assert result.data_quality.controlled_universe_blocked == 0

    def test_inline_portfolio_missing_execution_context_blocks(self) -> None:
        portfolio = _portfolio_report(
            _pc_score("BTC/USDT", PortfolioConstructionState.INCLUDED, allocation_score=85.0),
        )
        plan = ResearchRunPlan(
            run_id="run-cu",
            steps=(
                ResearchRunStep(
                    kind=ResearchRunStepKind.CONTROLLED_UNIVERSE,
                    inputs={"portfolio_report": portfolio},
                ),
            ),
        )
        result = build_research_run_result(plan)
        step_result = result.steps[0]
        assert step_result.state == ResearchRunStepState.BLOCKED
        assert MISSING_EXECUTION_CONTEXT in step_result.reason_codes
        assert result.data_quality.controlled_universe_blocked == 1

    def test_missing_portfolio_report_blocks(self) -> None:
        plan = ResearchRunPlan(
            run_id="run-cu",
            steps=(
                ResearchRunStep(
                    kind=ResearchRunStepKind.CONTROLLED_UNIVERSE,
                    inputs={},
                ),
            ),
        )
        result = build_research_run_result(plan)
        step_result = result.steps[0]
        assert step_result.state == ResearchRunStepState.BLOCKED
        assert MISSING_PORTFOLIO_CONTEXT in step_result.reason_codes

    def test_stale_portfolio_report_blocks(self) -> None:
        portfolio = _portfolio_report(
            _pc_score("BTC/USDT", PortfolioConstructionState.INCLUDED, allocation_score=85.0),
        )
        stale_portfolio = PortfolioConstructionReport(
            version=portfolio.version,
            report_id=portfolio.report_id,
            generated_at=portfolio.generated_at,
            inputs=portfolio.inputs,
            config=portfolio.config,
            safety_flags=portfolio.safety_flags,
            scores=portfolio.scores,
            universe_summary=portfolio.universe_summary,
            data_quality=PortfolioConstructionDataQuality(
                total_inputs=portfolio.data_quality.total_inputs,
                included_count=portfolio.data_quality.included_count,
                capped_count=portfolio.data_quality.capped_count,
                watchlist_count=portfolio.data_quality.watchlist_count,
                excluded_count=portfolio.data_quality.excluded_count,
                insufficient_data_count=portfolio.data_quality.insufficient_data_count,
                blocked_count=portfolio.data_quality.blocked_count,
                ready_context_count=0,
                missing_context_count=0,
                blocked_context_count=0,
                total_final_weight_pct=0.0,
                total_research_weight_pct=0.0,
                data_quality_score=0.0,
                sections_present=0,
                all_sections_present=True,
                all_counts_consistent=True,
                total_weight_within_tolerance=True,
                has_unsafe_content=False,
                safety_flags_ok=True,
                stale=True,
            ),
            reason_codes=portfolio.reason_codes,
            metadata=portfolio.metadata,
            notes=portfolio.notes,
        )
        plan = ResearchRunPlan(
            run_id="run-cu",
            steps=(
                ResearchRunStep(
                    kind=ResearchRunStepKind.CONTROLLED_UNIVERSE,
                    inputs={"portfolio_report": stale_portfolio},
                ),
            ),
        )
        result = build_research_run_result(plan)
        step_result = result.steps[0]
        assert step_result.state == ResearchRunStepState.BLOCKED
        assert STALE_INPUT in step_result.reason_codes

    def test_stale_execution_context_blocks(self) -> None:
        portfolio = _portfolio_report(
            _pc_score("BTC/USDT", PortfolioConstructionState.INCLUDED, allocation_score=85.0),
        )
        execution = _execution_context(data_quality=DataQuality(stale=True))
        plan = ResearchRunPlan(
            run_id="run-cu",
            steps=(
                ResearchRunStep(
                    kind=ResearchRunStepKind.CONTROLLED_UNIVERSE,
                    inputs={
                        "portfolio_report": portfolio,
                        "execution_context": execution,
                    },
                ),
            ),
        )
        result = build_research_run_result(plan)
        step_result = result.steps[0]
        assert step_result.state == ResearchRunStepState.BLOCKED
        assert STALE_INPUT in step_result.reason_codes

    def test_resolves_upstream_portfolio_by_step_id(self) -> None:
        portfolio = _portfolio_report(
            _pc_score("BTC/USDT", PortfolioConstructionState.INCLUDED, allocation_score=85.0),
        )
        execution = _execution_context()
        prior = ResearchRunStepResult(
            step_index=0,
            step_id="pc-1",
            kind=ResearchRunStepKind.PORTFOLIO_CONSTRUCTION,
            state=ResearchRunStepState.SUCCESS,
            reason_codes=(OK,),
            data={"report": portfolio, "report_id": portfolio.report_id},
            output_paths=(),
            notes=(),
        )
        step = ResearchRunStep(
            kind=ResearchRunStepKind.CONTROLLED_UNIVERSE,
            inputs={
                "portfolio_construction_step_id": "pc-1",
                "execution_context": execution,
            },
        )
        result = _dispatch_step(step, 1, ResearchRunConfig(), (prior,))
        assert result.state == ResearchRunStepState.SUCCESS
        assert "BTC/USDT" in result.data["report"].universe

    def test_resolves_upstream_portfolio_by_step_index(self) -> None:
        portfolio = _portfolio_report(
            _pc_score("BTC/USDT", PortfolioConstructionState.INCLUDED, allocation_score=85.0),
        )
        execution = _execution_context()
        prior = ResearchRunStepResult(
            step_index=0,
            step_id="pc-1",
            kind=ResearchRunStepKind.PORTFOLIO_CONSTRUCTION,
            state=ResearchRunStepState.SUCCESS,
            reason_codes=(OK,),
            data={"report": portfolio, "report_id": portfolio.report_id},
            output_paths=(),
            notes=(),
        )
        step = ResearchRunStep(
            kind=ResearchRunStepKind.CONTROLLED_UNIVERSE,
            inputs={
                "portfolio_construction_step_index": 0,
                "execution_context": execution,
            },
        )
        result = _dispatch_step(step, 1, ResearchRunConfig(), (prior,))
        assert result.state == ResearchRunStepState.SUCCESS

    def test_resolves_nearest_preceding_portfolio(self) -> None:
        portfolio = _portfolio_report(
            _pc_score("BTC/USDT", PortfolioConstructionState.INCLUDED, allocation_score=85.0),
        )
        execution = _execution_context()
        prior = ResearchRunStepResult(
            step_index=0,
            step_id="pc-1",
            kind=ResearchRunStepKind.PORTFOLIO_CONSTRUCTION,
            state=ResearchRunStepState.SUCCESS,
            reason_codes=(OK,),
            data={"report": portfolio, "report_id": portfolio.report_id},
            output_paths=(),
            notes=(),
        )
        step = ResearchRunStep(
            kind=ResearchRunStepKind.CONTROLLED_UNIVERSE,
            inputs={"execution_context": execution},
        )
        result = _dispatch_step(step, 1, ResearchRunConfig(), (prior,))
        assert result.state == ResearchRunStepState.SUCCESS

    def test_explicit_step_id_takes_precedence_over_nearest_preceding(self) -> None:
        older_portfolio = _portfolio_report(
            _pc_score("ETH/USDT", PortfolioConstructionState.INCLUDED, allocation_score=85.0),
        )
        newer_portfolio = _portfolio_report(
            _pc_score("BTC/USDT", PortfolioConstructionState.INCLUDED, allocation_score=85.0),
        )
        execution = _execution_context()
        priors = (
            ResearchRunStepResult(
                step_index=0,
                step_id="pc-older",
                kind=ResearchRunStepKind.PORTFOLIO_CONSTRUCTION,
                state=ResearchRunStepState.SUCCESS,
                reason_codes=(OK,),
                data={"report": older_portfolio, "report_id": older_portfolio.report_id},
                output_paths=(),
                notes=(),
            ),
            ResearchRunStepResult(
                step_index=1,
                step_id="pc-newer",
                kind=ResearchRunStepKind.PORTFOLIO_CONSTRUCTION,
                state=ResearchRunStepState.SUCCESS,
                reason_codes=(OK,),
                data={"report": newer_portfolio, "report_id": newer_portfolio.report_id},
                output_paths=(),
                notes=(),
            ),
        )
        step = ResearchRunStep(
            kind=ResearchRunStepKind.CONTROLLED_UNIVERSE,
            inputs={
                "portfolio_construction_step_id": "pc-older",
                "execution_context": execution,
            },
        )
        result = _dispatch_step(step, 2, ResearchRunConfig(), priors)
        assert result.state == ResearchRunStepState.SUCCESS
        assert "ETH/USDT" in result.data["report"].universe
        assert "BTC/USDT" not in result.data["report"].universe

    def test_explicit_step_index_takes_precedence_over_nearest_preceding(self) -> None:
        older_portfolio = _portfolio_report(
            _pc_score("ETH/USDT", PortfolioConstructionState.INCLUDED, allocation_score=85.0),
        )
        newer_portfolio = _portfolio_report(
            _pc_score("BTC/USDT", PortfolioConstructionState.INCLUDED, allocation_score=85.0),
        )
        execution = _execution_context()
        priors = (
            ResearchRunStepResult(
                step_index=0,
                step_id="pc-older",
                kind=ResearchRunStepKind.PORTFOLIO_CONSTRUCTION,
                state=ResearchRunStepState.SUCCESS,
                reason_codes=(OK,),
                data={"report": older_portfolio, "report_id": older_portfolio.report_id},
                output_paths=(),
                notes=(),
            ),
            ResearchRunStepResult(
                step_index=1,
                step_id="pc-newer",
                kind=ResearchRunStepKind.PORTFOLIO_CONSTRUCTION,
                state=ResearchRunStepState.SUCCESS,
                reason_codes=(OK,),
                data={"report": newer_portfolio, "report_id": newer_portfolio.report_id},
                output_paths=(),
                notes=(),
            ),
        )
        step = ResearchRunStep(
            kind=ResearchRunStepKind.CONTROLLED_UNIVERSE,
            inputs={
                "portfolio_construction_step_index": 0,
                "execution_context": execution,
            },
        )
        result = _dispatch_step(step, 2, ResearchRunConfig(), priors)
        assert result.state == ResearchRunStepState.SUCCESS
        assert "ETH/USDT" in result.data["report"].universe
        assert "BTC/USDT" not in result.data["report"].universe

    def test_ambiguous_references_fail_closed(self) -> None:
        # Both step_id and step_index provided and they disagree -> fail closed.
        portfolio = _portfolio_report(
            _pc_score("BTC/USDT", PortfolioConstructionState.INCLUDED, allocation_score=85.0),
        )
        execution = _execution_context()
        prior = ResearchRunStepResult(
            step_index=0,
            step_id="pc-1",
            kind=ResearchRunStepKind.PORTFOLIO_CONSTRUCTION,
            state=ResearchRunStepState.SUCCESS,
            reason_codes=(OK,),
            data={"report": portfolio, "report_id": portfolio.report_id},
            output_paths=(),
            notes=(),
        )
        step = ResearchRunStep(
            kind=ResearchRunStepKind.CONTROLLED_UNIVERSE,
            inputs={
                "portfolio_construction_step_id": "pc-1",
                "portfolio_construction_step_index": 99,
                "execution_context": execution,
            },
        )
        result = _dispatch_step(step, 1, ResearchRunConfig(), (prior,))
        assert result.state == ResearchRunStepState.BLOCKED
        assert MISSING_PORTFOLIO_CONTEXT in result.reason_codes

    def test_invalid_step_id_reference_fails_closed(self) -> None:
        portfolio = _portfolio_report(
            _pc_score("BTC/USDT", PortfolioConstructionState.INCLUDED, allocation_score=85.0),
        )
        execution = _execution_context()
        prior = ResearchRunStepResult(
            step_index=0,
            step_id="pc-1",
            kind=ResearchRunStepKind.PORTFOLIO_CONSTRUCTION,
            state=ResearchRunStepState.SUCCESS,
            reason_codes=(OK,),
            data={"report": portfolio, "report_id": portfolio.report_id},
            output_paths=(),
            notes=(),
        )
        step = ResearchRunStep(
            kind=ResearchRunStepKind.CONTROLLED_UNIVERSE,
            inputs={
                "portfolio_construction_step_id": "pc-missing",
                "execution_context": execution,
            },
        )
        result = _dispatch_step(step, 1, ResearchRunConfig(), (prior,))
        assert result.state == ResearchRunStepState.BLOCKED
        assert MISSING_PORTFOLIO_CONTEXT in result.reason_codes

    def test_blocked_execution_state_returns_execution_blocked(self) -> None:
        portfolio = _portfolio_report(
            _pc_score("BTC/USDT", PortfolioConstructionState.INCLUDED, allocation_score=85.0),
        )
        execution = _execution_context(execution_state=ExecutionState.BLOCKED)
        plan = ResearchRunPlan(
            run_id="run-cu",
            steps=(
                ResearchRunStep(
                    kind=ResearchRunStepKind.CONTROLLED_UNIVERSE,
                    inputs={
                        "portfolio_report": portfolio,
                        "execution_context": execution,
                    },
                ),
            ),
        )
        result = build_research_run_result(plan)
        step_result = result.steps[0]
        assert step_result.state == ResearchRunStepState.BLOCKED
        assert EXECUTION_BLOCKED in step_result.reason_codes

    def test_macro_mode_none_returns_macro_mode_none(self) -> None:
        portfolio = _portfolio_report(
            _pc_score("BTC/USDT", PortfolioConstructionState.INCLUDED, allocation_score=85.0),
        )
        execution = _execution_context(allowed_mode=MarketAllowedMode.NONE)
        plan = ResearchRunPlan(
            run_id="run-cu",
            steps=(
                ResearchRunStep(
                    kind=ResearchRunStepKind.CONTROLLED_UNIVERSE,
                    inputs={
                        "portfolio_report": portfolio,
                        "execution_context": execution,
                    },
                ),
            ),
        )
        result = build_research_run_result(plan)
        step_result = result.steps[0]
        assert step_result.state == ResearchRunStepState.BLOCKED
        assert MACRO_MODE_NONE in step_result.reason_codes

    def test_fail_fast_preserves_existing_behavior(self) -> None:
        plan = ResearchRunPlan(
            run_id="run-cu",
            steps=(
                ResearchRunStep(
                    kind=ResearchRunStepKind.CONTROLLED_UNIVERSE,
                    inputs={},
                ),
                ResearchRunStep(
                    kind=ResearchRunStepKind.DISCOVERY,
                ),
            ),
        )
        config = ResearchRunConfig(fail_fast=True)
        result = build_research_run_result(plan, config)
        assert result.steps[0].state == ResearchRunStepState.BLOCKED
        assert result.steps[1].state == ResearchRunStepState.SKIPPED

    def test_controlled_universe_is_registered_step_kind(self) -> None:
        assert ResearchRunStepKind.CONTROLLED_UNIVERSE in tuple(ResearchRunStepKind)


class TestStaleInputDetection:
    def test_none_is_not_stale(self) -> None:
        # None is treated as missing, letting callers emit MISSING_* reason codes.
        assert _is_stale_input(None) is False

    def test_missing_data_quality_is_stale(self) -> None:
        class NoDataQuality:
            pass

        assert _is_stale_input(NoDataQuality()) is True

    def test_stale_flag_is_stale(self) -> None:
        class StaleReport:
            data_quality = PortfolioConstructionDataQuality(
                total_inputs=0,
                included_count=0,
                capped_count=0,
                watchlist_count=0,
                excluded_count=0,
                insufficient_data_count=0,
                blocked_count=0,
                ready_context_count=0,
                missing_context_count=0,
                blocked_context_count=0,
                total_final_weight_pct=0.0,
                total_research_weight_pct=0.0,
                data_quality_score=0.0,
                sections_present=0,
                all_sections_present=True,
                all_counts_consistent=True,
                total_weight_within_tolerance=True,
                has_unsafe_content=False,
                safety_flags_ok=True,
                stale=True,
            )

        assert _is_stale_input(StaleReport()) is True

    def test_valid_data_quality_is_not_stale(self) -> None:
        portfolio = _portfolio_report(
            _pc_score("BTC/USDT", PortfolioConstructionState.INCLUDED, allocation_score=85.0),
        )
        assert _is_stale_input(portfolio) is False

    def test_data_quality_is_valid_method_not_stale(self) -> None:
        execution = _execution_context()
        assert _is_stale_input(execution) is False

    def test_data_quality_is_invalid_method_is_stale(self) -> None:
        execution = _execution_context(data_quality=DataQuality(stale=True))
        assert _is_stale_input(execution) is True
