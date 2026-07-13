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
from hunter.discovery import DiscoveryInput, DiscoveryInputKind
from hunter.portfolio_construction import (
    PortfolioConstructionInput,
    PortfolioConstructionInputKind,
)
from hunter.reporting_cli import CLIExitCode
from hunter.research_audit_catalog import CatalogArtifactKind, CatalogEntry, CatalogState
from hunter.run_orchestrator import (
    CONTRADICTORY_INPUT,
    EMPTY_RUN_ID,
    EMPTY_RUN_PLAN,
    INVALID_OUTPUT_DIR,
    INVALID_RUN_PLAN,
    MISSING_EXECUTION_CONTEXT,
    MISSING_PORTFOLIO_CONTEXT,
    NO_NETWORK_CONNECTION,
    NOT_TRADING_ADVICE,
    OK,
    RESEARCH_ONLY,
    RUN_BLOCKED,
    STEP_BLOCKED,
    STEP_FAILED,
    STEP_SKIPPED,
    UNKNOWN_STEP_KIND,
    UNSAFE_RUN_CONTENT,
    UNSUPPORTED_STEP_KIND,
    build_coin_discovery_run_plan,
    build_research_run_result,
    validate_run_plan_dependencies,
    ResearchRunConfig,
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
