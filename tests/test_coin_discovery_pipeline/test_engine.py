"""Tests for the coin_discovery_pipeline engine (MVP-54 Step 2)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from hunter.coin_discovery_pipeline import engine as pipeline_engine
from hunter.coin_discovery_pipeline import (
    EXPORT_SKIPPED,
    INVALID_PIPELINE_CONFIG,
    NO_AUTOMATIC_CONFIG_MUTATION,
    NO_FREQTRADE_RUNTIME_CONNECTION,
    PIPELINE_HUMAN_APPROVAL_REQUIRED,
    PIPELINE_RESEARCH_ONLY,
    PIPELINE_RUN_BLOCKED,
    PIPELINE_RUN_FAILED,
    PIPELINE_RUN_PARTIAL,
    CoinDiscoveryPipelineConfig,
    CoinDiscoveryPipelineError,
    CoinDiscoveryPipelineResult,
    CoinDiscoveryPipelineSafetyFlags,
    PipelineState,
    run_coin_discovery_pipeline,
)
from hunter.controlled_universe_export_adapter import BLOCKED_EXPORT, MISSING_REPORT_INPUT
from hunter.controlled_universe_export_adapter.models import (
    ControlledUniverseExportConfig,
    ControlledUniverseExportResult,
)
from hunter.discovery.models import DiscoveryInput
from hunter.execution.models import ExecutionContext, ExecutionState, ExecutionMode, ExecutionSafetyFlags
from hunter.market_state.models import OutputStatus, AllowedMode, DataQuality
from hunter.decision.models import DecisionState, DecisionAction
from hunter.run_orchestrator.models import (
    ResearchRunArtifact,
    ResearchRunConfig,
    ResearchRunDataQuality,
    ResearchRunPlan,
    ResearchRunResult,
    ResearchRunSafetyFlags,
    ResearchRunState,
    ResearchRunStepResult,
    ResearchRunStepState,
)


@pytest.fixture(autouse=True)
def _isolate_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Contain relative default output paths (e.g. the export step's
    hardcoded ``data/``/``reports/`` defaults) inside an isolated tmp_path
    for every test in this module, regardless of write_artifacts/export_config.
    """
    monkeypatch.chdir(tmp_path)


def _dt() -> datetime:
    return datetime(2026, 7, 13, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def discovery_input() -> DiscoveryInput:
    return DiscoveryInput(pair="BTC/USDT")


@pytest.fixture
def discovery_inputs() -> tuple[DiscoveryInput, ...]:
    return (DiscoveryInput(pair="BTC/USDT"), DiscoveryInput(pair="ETH/USDT"))


@pytest.fixture
def execution_context_enabled() -> ExecutionContext:
    return ExecutionContext(
        timestamp=_dt(),
        status=OutputStatus.VALID,
        execution_state=ExecutionState.ENABLED,
        execution_mode=ExecutionMode.LONG_RESEARCH_ONLY,
        decision_state=DecisionState.ALLOW,
        decision_action=DecisionAction.ENABLE_LONG_ONLY_RESEARCH,
        allowed_mode=AllowedMode.LONG_ONLY,
        dry_run=True,
        live_trading_enabled=False,
        exchange_connection_enabled=False,
        freqtrade_enabled=False,
        reason_codes=[],
        data_quality=DataQuality(),
        safety_flags=ExecutionSafetyFlags(),
    )


@pytest.fixture
def execution_context_blocked() -> ExecutionContext:
    return ExecutionContext.blocked(timestamp=_dt())


@pytest.fixture
def base_config(
    discovery_inputs: tuple[DiscoveryInput, ...],
    execution_context_enabled: ExecutionContext,
) -> CoinDiscoveryPipelineConfig:
    return CoinDiscoveryPipelineConfig(
        run_id="run-001",
        output_dir="data/coin_discovery_pipeline",
        write_artifacts=False,
        discovery_inputs=discovery_inputs,
        execution_context=execution_context_enabled,
        generated_at=_dt(),
    )


def _make_run_result(
    *,
    plan: ResearchRunPlan,
    state: ResearchRunState,
    steps: tuple[ResearchRunStepResult, ...] = (),
    reason_codes: tuple[str, ...] = (),
    generated_at: datetime | None = None,
) -> ResearchRunResult:
    """Create a minimal ResearchRunResult for engine tests."""
    return ResearchRunResult(
        run_id=plan.run_id,
        config=ResearchRunConfig(output_dir="data/run", generated_at=generated_at or _dt()),
        plan=plan,
        steps=steps,
        artifacts=(),
        data_quality=ResearchRunDataQuality(),
        safety_flags=ResearchRunSafetyFlags(),
        reason_codes=reason_codes,
        generated_at=generated_at or _dt(),
        state=state,
        metadata={},
        notes=(),
    )


class TestSuccessfulRun:
    def test_state_is_completed(self, base_config: CoinDiscoveryPipelineConfig) -> None:
        result = run_coin_discovery_pipeline(base_config)
        assert isinstance(result, CoinDiscoveryPipelineResult)
        assert result.run_id == "run-001"
        assert result.state == PipelineState.COMPLETED

    def test_safety_flags_are_all_true(self, base_config: CoinDiscoveryPipelineConfig) -> None:
        result = run_coin_discovery_pipeline(base_config)
        assert result.safety_flags == CoinDiscoveryPipelineSafetyFlags()

    def test_reason_codes_include_pipeline_and_run_codes(
        self, base_config: CoinDiscoveryPipelineConfig
    ) -> None:
        result = run_coin_discovery_pipeline(base_config)
        assert PIPELINE_RESEARCH_ONLY in result.reason_codes
        assert PIPELINE_HUMAN_APPROVAL_REQUIRED in result.reason_codes
        assert NO_FREQTRADE_RUNTIME_CONNECTION in result.reason_codes
        assert NO_AUTOMATIC_CONFIG_MUTATION in result.reason_codes
        assert result.run_result is not None
        for code in result.run_result.reason_codes:
            assert code in result.reason_codes

    def test_export_result_is_present(self, base_config: CoinDiscoveryPipelineConfig) -> None:
        result = run_coin_discovery_pipeline(base_config)
        assert result.export_result is not None
        assert isinstance(result.export_result, ControlledUniverseExportResult)


class TestBlockedRun:
    def test_blocked_execution_context_returns_blocked_state(
        self,
        discovery_inputs: tuple[DiscoveryInput, ...],
        execution_context_blocked: ExecutionContext,
    ) -> None:
        config = CoinDiscoveryPipelineConfig(
            run_id="run-blocked",
            output_dir="data/coin_discovery_pipeline/run-blocked",
            discovery_inputs=discovery_inputs,
            execution_context=execution_context_blocked,
        )
        result = run_coin_discovery_pipeline(config)
        assert result.state == PipelineState.BLOCKED
        assert PIPELINE_RUN_BLOCKED in result.reason_codes
        assert result.export_result is not None


class TestFailedRun:
    def test_failed_run_returns_failed_state(
        self, base_config: CoinDiscoveryPipelineConfig, monkeypatch: Any
    ) -> None:
        original_fn = pipeline_engine.build_research_run_result

        def _failed_fn(plan: ResearchRunPlan, config: ResearchRunConfig | None = None) -> ResearchRunResult:
            return _make_run_result(plan=plan, state=ResearchRunState.FAILED, reason_codes=("STEP_FAILED",))

        monkeypatch.setattr(pipeline_engine, "build_research_run_result", _failed_fn)
        result = run_coin_discovery_pipeline(base_config)
        assert result.state == PipelineState.FAILED
        assert PIPELINE_RUN_FAILED in result.reason_codes
        assert result.export_result is not None
        # Export adapter is invoked for FAILED runs and returns fail-closed result.
        assert BLOCKED_EXPORT in result.export_result.reason_codes or MISSING_REPORT_INPUT in result.export_result.reason_codes

        monkeypatch.setattr(pipeline_engine, "build_research_run_result", original_fn)


class TestPartialRun:
    def test_partial_run_returns_partial_state(
        self, base_config: CoinDiscoveryPipelineConfig, monkeypatch: Any
    ) -> None:
        original_fn = pipeline_engine.build_research_run_result

        def _partial_fn(plan: ResearchRunPlan, config: ResearchRunConfig | None = None) -> ResearchRunResult:
            return _make_run_result(plan=plan, state=ResearchRunState.PARTIAL, reason_codes=("STEP_SKIPPED",))

        monkeypatch.setattr(pipeline_engine, "build_research_run_result", _partial_fn)
        result = run_coin_discovery_pipeline(base_config)
        assert result.state == PipelineState.PARTIAL
        assert PIPELINE_RUN_PARTIAL in result.reason_codes
        assert result.export_result is not None
        monkeypatch.setattr(pipeline_engine, "build_research_run_result", original_fn)


class TestExportDisabled:
    def test_export_result_is_none_when_export_disabled(
        self, base_config: CoinDiscoveryPipelineConfig
    ) -> None:
        config = CoinDiscoveryPipelineConfig(
            run_id=base_config.run_id,
            output_dir=base_config.output_dir,
            discovery_inputs=base_config.discovery_inputs,
            execution_context=base_config.execution_context,
            export_enabled=False,
        )
        result = run_coin_discovery_pipeline(config)
        assert result.state == PipelineState.COMPLETED
        assert result.export_result is None
        assert EXPORT_SKIPPED in result.reason_codes


class TestMissingControlledUniverseReport:
    def test_missing_cu_report_in_completed_run_returns_fail_closed_export(
        self, base_config: CoinDiscoveryPipelineConfig, monkeypatch: Any
    ) -> None:
        original_fn = pipeline_engine.build_research_run_result

        def _completed_fn(plan_arg: ResearchRunPlan, config: ResearchRunConfig | None = None) -> ResearchRunResult:
            return _make_run_result(plan=plan_arg, state=ResearchRunState.COMPLETED, steps=())

        monkeypatch.setattr(pipeline_engine, "build_research_run_result", _completed_fn)
        result = run_coin_discovery_pipeline(base_config)
        assert result.state == PipelineState.COMPLETED
        assert result.export_result is not None
        assert MISSING_REPORT_INPUT in result.export_result.reason_codes
        monkeypatch.setattr(pipeline_engine, "build_research_run_result", original_fn)


class TestUnsafeExportResult:
    def test_unsafe_export_result_flags_are_propagated(
        self, base_config: CoinDiscoveryPipelineConfig, monkeypatch: Any
    ) -> None:
        original_fn = pipeline_engine.build_controlled_universe_export_from_run_result

        def _unsafe_export_fn(
            result: ResearchRunResult,
            config: ControlledUniverseExportConfig | None = None,
        ) -> ControlledUniverseExportResult:
            return ControlledUniverseExportResult(
                report_id="unsafe-export",
                generated_at=_dt(),
                whitelist=(),
                blacklist=("BTC/USDT",),
                per_pair_summary=(),
                research_only=True,
                human_approval_required=True,
                reason_codes=(BLOCKED_EXPORT,),
                safety_flags={
                    "no_freqtrade_runtime_connection": True,
                    "no_automatic_config_mutation": True,
                },
                metadata={"version": "0.53.0-dev"},
            )

        monkeypatch.setattr(pipeline_engine, "build_controlled_universe_export_from_run_result", _unsafe_export_fn)
        result = run_coin_discovery_pipeline(base_config)
        assert result.state == PipelineState.COMPLETED
        assert result.export_result is not None
        assert BLOCKED_EXPORT in result.export_result.reason_codes
        assert result.export_result.blacklist == ("BTC/USDT",)
        monkeypatch.setattr(pipeline_engine, "build_controlled_universe_export_from_run_result", original_fn)


class TestUnexpectedEngineError:
    def test_unexpected_engine_error_is_wrapped_and_raised(
        self, base_config: CoinDiscoveryPipelineConfig, monkeypatch: Any
    ) -> None:
        original_fn = pipeline_engine.build_research_run_result

        def _explode_fn(plan: ResearchRunPlan, config: ResearchRunConfig | None = None) -> ResearchRunResult:
            raise RuntimeError("simulated orchestrator failure")

        monkeypatch.setattr(pipeline_engine, "build_research_run_result", _explode_fn)
        with pytest.raises(CoinDiscoveryPipelineError) as exc_info:
            run_coin_discovery_pipeline(base_config)
        assert "simulated orchestrator failure" in str(exc_info.value)
        assert isinstance(exc_info.value.__cause__, RuntimeError)
        monkeypatch.setattr(pipeline_engine, "build_research_run_result", original_fn)


class TestInvalidConfig:
    def test_none_config_returns_blocked_result(self) -> None:
        result = run_coin_discovery_pipeline(None)  # type: ignore[arg-type]
        assert result.state == PipelineState.BLOCKED
        assert INVALID_PIPELINE_CONFIG in result.reason_codes

    def test_non_config_object_returns_blocked_result(self) -> None:
        result = run_coin_discovery_pipeline("not-a-config")  # type: ignore[arg-type]
        assert result.state == PipelineState.BLOCKED
        assert INVALID_PIPELINE_CONFIG in result.reason_codes


class TestDeterminism:
    def test_run_id_is_preserved_in_result(self, base_config: CoinDiscoveryPipelineConfig) -> None:
        result = run_coin_discovery_pipeline(base_config)
        assert result.run_id == "run-001"

    def test_result_fields_are_ordered_and_deduplicated(
        self, base_config: CoinDiscoveryPipelineConfig
    ) -> None:
        result = run_coin_discovery_pipeline(base_config)
        assert result.reason_codes == tuple(dict.fromkeys(result.reason_codes))
        assert sorted(result.reason_codes) == list(result.reason_codes)

    def test_repeated_identical_input_produces_equivalent_result(
        self, base_config: CoinDiscoveryPipelineConfig
    ) -> None:
        result1 = run_coin_discovery_pipeline(base_config)
        result2 = run_coin_discovery_pipeline(base_config)
        assert result1.state == result2.state
        assert result1.run_id == result2.run_id
        assert result1.reason_codes == result2.reason_codes
        assert result1.safety_flags == result2.safety_flags
        assert result1.export_result is not None
        assert result2.export_result is not None
        assert result1.export_result.whitelist == result2.export_result.whitelist
        assert result1.export_result.blacklist == result2.export_result.blacklist


class TestRunConfigPropagation:
    def test_custom_run_config_is_passed_to_orchestrator(
        self,
        base_config: CoinDiscoveryPipelineConfig,
        monkeypatch: Any,
    ) -> None:
        captured: dict[str, Any] = {}

        original_fn = pipeline_engine.build_research_run_result

        def _capture_fn(plan: ResearchRunPlan, config: ResearchRunConfig | None = None) -> ResearchRunResult:
            captured["config"] = config
            return original_fn(plan, config)

        monkeypatch.setattr(pipeline_engine, "build_research_run_result", _capture_fn)
        custom_run_config = ResearchRunConfig(output_dir="data/custom_run", fail_fast=False, write_artifacts=False)
        config = CoinDiscoveryPipelineConfig(
            run_id=base_config.run_id,
            output_dir=base_config.output_dir,
            discovery_inputs=base_config.discovery_inputs,
            execution_context=base_config.execution_context,
            run_config=custom_run_config,
        )
        result = run_coin_discovery_pipeline(config)
        assert result.state == PipelineState.COMPLETED
        assert captured["config"] is custom_run_config
        monkeypatch.setattr(pipeline_engine, "build_research_run_result", original_fn)


class TestExportConfigPropagation:
    def test_custom_export_config_is_passed_to_adapter(
        self,
        base_config: CoinDiscoveryPipelineConfig,
        monkeypatch: Any,
    ) -> None:
        captured: dict[str, Any] = {}
        original_fn = pipeline_engine.build_controlled_universe_export_from_run_result

        def _capture_fn(
            result: ResearchRunResult,
            config: ControlledUniverseExportConfig | None = None,
        ) -> ControlledUniverseExportResult:
            captured["config"] = config
            return original_fn(result, config)

        monkeypatch.setattr(pipeline_engine, "build_controlled_universe_export_from_run_result", _capture_fn)
        custom_export_config = ControlledUniverseExportConfig(output_dir="data/custom_export")
        config = CoinDiscoveryPipelineConfig(
            run_id=base_config.run_id,
            output_dir=base_config.output_dir,
            discovery_inputs=base_config.discovery_inputs,
            execution_context=base_config.execution_context,
            export_config=custom_export_config,
        )
        result = run_coin_discovery_pipeline(config)
        assert result.state == PipelineState.COMPLETED
        assert captured["config"] is custom_export_config
        monkeypatch.setattr(pipeline_engine, "build_controlled_universe_export_from_run_result", original_fn)


class TestDefaultExportConfig:
    def test_default_export_config_uses_pipeline_output_dir(
        self,
        base_config: CoinDiscoveryPipelineConfig,
        monkeypatch: Any,
    ) -> None:
        captured: dict[str, Any] = {}
        original_fn = pipeline_engine.build_controlled_universe_export_from_run_result

        def _capture_fn(
            result: ResearchRunResult,
            config: ControlledUniverseExportConfig | None = None,
        ) -> ControlledUniverseExportResult:
            captured["config"] = config
            return original_fn(result, config)

        monkeypatch.setattr(pipeline_engine, "build_controlled_universe_export_from_run_result", _capture_fn)
        # Ensure export_config is None so default is applied
        config = CoinDiscoveryPipelineConfig(
            run_id=base_config.run_id,
            output_dir=base_config.output_dir,
            discovery_inputs=base_config.discovery_inputs,
            execution_context=base_config.execution_context,
            export_config=None,
        )
        result = run_coin_discovery_pipeline(config)
        assert result.state == PipelineState.COMPLETED
        assert captured["config"] is not None
        assert captured["config"].output_dir == "data/coin_discovery_pipeline/run-001/controlled_universe_export"
        assert captured["config"].markdown_output_dir == "reports/coin_discovery_pipeline/run-001/controlled_universe_export"
        monkeypatch.setattr(pipeline_engine, "build_controlled_universe_export_from_run_result", original_fn)
