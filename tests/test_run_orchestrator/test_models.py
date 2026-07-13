"""Tests for hunter.run_orchestrator.models."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from hunter.run_orchestrator import (
    CONTRADICTORY_INPUT,
    ControlledUniverseRunInput,
    EXECUTION_BLOCKED,
    FORBIDDEN_RUN_ORCHESTRATOR_TERMS,
    INVALID_CONTROLLED_UNIVERSE_INPUT,
    INVALID_PORTFOLIO_SUMMARY,
    MACRO_MODE_NONE,
    MISSING_EXECUTION_CONTEXT,
    MISSING_PORTFOLIO_CONTEXT,
    ResearchRunArtifact,
    ResearchRunConfig,
    ResearchRunDataQuality,
    ResearchRunPlan,
    ResearchRunResult,
    ResearchRunSafetyFlags,
    ResearchRunState,
    ResearchRunStep,
    ResearchRunStepKind,
    ResearchRunStepResult,
    ResearchRunStepState,
    RUN_ORCHESTRATOR_REASON_CODES,
    RUN_ORCHESTRATOR_VERSION,
    RunInputResolution,
    STALE_INPUT,
    UPSTREAM_STEP_BLOCKED,
    UPSTREAM_STEP_FAILED,
)


class TestPublicExports:
    def test_version_exported(self) -> None:
        assert RUN_ORCHESTRATOR_VERSION == "0.30.0-dev"

    def test_reason_codes_exported(self) -> None:
        assert isinstance(RUN_ORCHESTRATOR_REASON_CODES, frozenset)
        assert "OK" in RUN_ORCHESTRATOR_REASON_CODES

    def test_forbidden_terms_exported(self) -> None:
        assert isinstance(FORBIDDEN_RUN_ORCHESTRATOR_TERMS, frozenset)
        assert "binance" in FORBIDDEN_RUN_ORCHESTRATOR_TERMS
        assert "scheduler" in FORBIDDEN_RUN_ORCHESTRATOR_TERMS


class TestEnums:
    def test_step_kind_values(self) -> None:
        assert ResearchRunStepKind.BACKTEST.value == "backtest"
        assert ResearchRunStepKind.PORTFOLIO_CONSTRUCTION.value == "portfolio_construction"
        assert ResearchRunStepKind.DISCOVERY.value == "discovery"
        assert ResearchRunStepKind.REPORTING_CLI_SAMPLE.value == "reporting_cli_sample"
        assert ResearchRunStepKind.AUDIT_SNAPSHOT_SUMMARY.value == "audit_snapshot_summary"
        assert ResearchRunStepKind.AUDIT_CATALOG_SUMMARY.value == "audit_catalog_summary"
        assert ResearchRunStepKind.AUDIT_CLOSURE_SUMMARY.value == "audit_closure_summary"
        assert ResearchRunStepKind.CONTROLLED_UNIVERSE.value == "controlled_universe"

    def test_new_reason_codes_in_sets(self) -> None:
        assert MISSING_PORTFOLIO_CONTEXT in RUN_ORCHESTRATOR_REASON_CODES
        assert MISSING_EXECUTION_CONTEXT in RUN_ORCHESTRATOR_REASON_CODES
        assert STALE_INPUT in RUN_ORCHESTRATOR_REASON_CODES
        assert UPSTREAM_STEP_FAILED in RUN_ORCHESTRATOR_REASON_CODES
        assert UPSTREAM_STEP_BLOCKED in RUN_ORCHESTRATOR_REASON_CODES
        assert INVALID_PORTFOLIO_SUMMARY in RUN_ORCHESTRATOR_REASON_CODES
        assert EXECUTION_BLOCKED in RUN_ORCHESTRATOR_REASON_CODES
        assert MACRO_MODE_NONE in RUN_ORCHESTRATOR_REASON_CODES
        assert CONTRADICTORY_INPUT in RUN_ORCHESTRATOR_REASON_CODES
        assert INVALID_CONTROLLED_UNIVERSE_INPUT in RUN_ORCHESTRATOR_REASON_CODES

    def test_step_states(self) -> None:
        assert ResearchRunStepState.SUCCESS.value == "SUCCESS"
        assert ResearchRunStepState.FAILED.value == "FAILED"
        assert ResearchRunStepState.BLOCKED.value == "BLOCKED"
        assert ResearchRunStepState.SKIPPED.value == "SKIPPED"

    def test_run_states(self) -> None:
        assert ResearchRunState.COMPLETED.value == "COMPLETED"
        assert ResearchRunState.FAILED.value == "FAILED"
        assert ResearchRunState.BLOCKED.value == "BLOCKED"
        assert ResearchRunState.PARTIAL.value == "PARTIAL"


class TestModelValidation:
    def test_research_run_config_defaults(self) -> None:
        cfg = ResearchRunConfig()
        assert cfg.output_dir == "data/run_orchestrator/latest_run"
        assert cfg.fail_fast is True
        assert cfg.write_artifacts is True
        assert cfg.project_version == "0.30.0-dev"

    def test_research_run_config_rejects_empty_output_dir(self) -> None:
        with pytest.raises(ValueError, match="output_dir"):
            ResearchRunConfig(output_dir="")

    def test_research_run_step_requires_kind(self) -> None:
        with pytest.raises(ValueError, match="kind"):
            ResearchRunStep(kind="backtest")  # type: ignore[arg-type]

    def test_research_run_plan_requires_run_id(self) -> None:
        with pytest.raises(ValueError, match="run_id"):
            ResearchRunPlan(run_id="", steps=())

    def test_research_run_plan_requires_steps_tuple(self) -> None:
        step = ResearchRunStep(kind=ResearchRunStepKind.BACKTEST)
        plan = ResearchRunPlan(run_id="r1", steps=[step])
        assert isinstance(plan.steps, tuple)

    def test_research_run_step_result_normalizes_reason_codes(self) -> None:
        result = ResearchRunStepResult(
            step_index=0,
            step_id="s1",
            kind=ResearchRunStepKind.BACKTEST,
            state=ResearchRunStepState.SUCCESS,
            reason_codes=["OK", "OK"],
            data={},
            output_paths=["path/a"],
            notes=["note"],
        )
        assert result.reason_codes == ("OK",)
        assert result.output_paths == ("path/a",)
        assert result.notes == ("note",)

    def test_research_run_artifact_validation(self) -> None:
        with pytest.raises(ValueError, match="path"):
            ResearchRunArtifact(
                step_index=0,
                step_id="s1",
                kind="backtest",
                path="",
            )

    def test_research_run_result_normalizes_collections(self) -> None:
        step = ResearchRunStepResult(
            step_index=0,
            step_id="s1",
            kind=ResearchRunStepKind.BACKTEST,
            state=ResearchRunStepState.SUCCESS,
            reason_codes=("OK",),
            data={},
            output_paths=(),
            notes=(),
        )
        generated_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
        result = ResearchRunResult(
            run_id="r1",
            config=ResearchRunConfig(),
            plan=ResearchRunPlan(run_id="r1", steps=(step,)),
            steps=[step],
            artifacts=[],
            data_quality=ResearchRunDataQuality(),
            safety_flags=ResearchRunSafetyFlags(),
            reason_codes=["OK"],
            generated_at=generated_at,
            state=ResearchRunState.COMPLETED,
            metadata={},
            notes=["done"],
        )
        assert isinstance(result.steps, tuple)
        assert isinstance(result.artifacts, tuple)
        assert isinstance(result.reason_codes, tuple)
        assert isinstance(result.notes, tuple)


class TestSafetyFlags:
    def test_default_is_safe(self) -> None:
        flags = ResearchRunSafetyFlags()
        assert flags.is_safe is True

    def test_failed_step_breaks_is_safe(self) -> None:
        flags = ResearchRunSafetyFlags(has_failed_step=True)
        assert flags.is_safe is False

    def test_blocked_step_breaks_is_safe(self) -> None:
        flags = ResearchRunSafetyFlags(has_blocked_step=True)
        assert flags.is_safe is False

    def test_unsafe_content_breaks_is_safe(self) -> None:
        flags = ResearchRunSafetyFlags(has_unsafe_content=True)
        assert flags.is_safe is False

    def test_negative_no_flag_breaks_is_safe(self) -> None:
        flags = ResearchRunSafetyFlags(no_network_connection=False)
        assert flags.is_safe is False

    def test_not_research_only_breaks_is_safe(self) -> None:
        flags = ResearchRunSafetyFlags(research_only=False)
        assert flags.is_safe is False


class TestDataQuality:
    def test_data_quality_defaults(self) -> None:
        dq = ResearchRunDataQuality()
        assert dq.total_steps == 0
        assert dq.successful_steps == 0


class TestDataQuality:
    def test_data_quality_includes_controlled_universe_counts(self) -> None:
        dq = ResearchRunDataQuality(
            controlled_universe_steps=2,
            controlled_universe_blocked=1,
            controlled_universe_failed=0,
        )
        assert dq.controlled_universe_steps == 2
        assert dq.controlled_universe_blocked == 1
        assert dq.controlled_universe_failed == 0


class TestControlledUniverseRunInput:
    def test_default_construction(self) -> None:
        inp = ControlledUniverseRunInput()
        assert inp.execution_context is None
        assert inp.portfolio_report is None
        assert inp.config is None
        assert inp.portfolio_construction_step_id is None
        assert inp.portfolio_construction_step_index is None
        assert inp.execution_context_step_id is None

    def test_rejects_negative_step_index(self) -> None:
        with pytest.raises(ValueError, match='portfolio_construction_step_index'):
            ControlledUniverseRunInput(portfolio_construction_step_index=-1)

    def test_rejects_non_integer_step_index(self) -> None:
        with pytest.raises(ValueError, match='portfolio_construction_step_index'):
            ControlledUniverseRunInput(portfolio_construction_step_index='1')  # type: ignore[arg-type]

    def test_rejects_empty_step_id_strings(self) -> None:
        with pytest.raises(ValueError, match='portfolio_construction_step_id'):
            ControlledUniverseRunInput(portfolio_construction_step_id='')
        with pytest.raises(ValueError, match='execution_context_step_id'):
            ControlledUniverseRunInput(execution_context_step_id='   ')

    def test_accepts_valid_step_index(self) -> None:
        inp = ControlledUniverseRunInput(portfolio_construction_step_index=3)
        assert inp.portfolio_construction_step_index == 3

    def test_run_input_resolution_defaults(self) -> None:
        res = RunInputResolution()
        assert res.portfolio_report is None
        assert res.execution_context is None
