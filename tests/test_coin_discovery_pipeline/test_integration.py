"""Integration tests for the one-call coin-discovery pipeline runner (MVP-54 Step 4)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

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
    write_coin_discovery_pipeline_result,
)
from hunter.coin_discovery_pipeline import engine as pipeline_engine
from hunter.controlled_universe_export_adapter import write_controlled_universe_export
from hunter.decision.models import DecisionAction, DecisionState
from hunter.discovery.models import DiscoveryInput
from hunter.execution.models import (
    ExecutionContext,
    ExecutionMode,
    ExecutionSafetyFlags,
    ExecutionState,
)
from hunter.market_state.models import AllowedMode, DataQuality, OutputStatus
from hunter.run_orchestrator.models import (
    ResearchRunConfig,
    ResearchRunDataQuality,
    ResearchRunPlan,
    ResearchRunResult,
    ResearchRunSafetyFlags,
    ResearchRunState,
    ResearchRunStepResult,
)


def _dt() -> datetime:
    return datetime(2026, 7, 13, 12, 0, 0, tzinfo=timezone.utc)


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
    """Return a config using the default relative output_dir.

    Tests should change into tmp_path so these relative paths are isolated.
    """
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
    """Create a minimal ResearchRunResult for integration tests."""
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


class TestFullPipelineFlow:
    def test_pipeline_result_is_returned(
        self,
        base_config: CoinDiscoveryPipelineConfig,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        result = run_coin_discovery_pipeline(base_config)
        assert isinstance(result, CoinDiscoveryPipelineResult)
        assert result.run_id == "run-001"
        assert result.state == PipelineState.COMPLETED
        assert result.run_result is not None
        assert result.export_result is not None

    def test_pipeline_artifacts_are_written(
        self,
        base_config: CoinDiscoveryPipelineConfig,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        result = run_coin_discovery_pipeline(base_config)
        paths = write_coin_discovery_pipeline_result(result, base_config)
        assert len(paths) == 2
        json_path = Path(paths[0])
        md_path = Path(paths[1])
        assert json_path.exists()
        assert md_path.exists()
        assert json_path.name == "pipeline.json"
        assert md_path.name == "pipeline.md"
        assert "data/coin_discovery_pipeline/run-001" in str(json_path)
        assert "reports/coin_discovery_pipeline/run-001" in str(md_path)

    def test_json_packet_structure(
        self,
        base_config: CoinDiscoveryPipelineConfig,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        result = run_coin_discovery_pipeline(base_config)
        paths = write_coin_discovery_pipeline_result(result, base_config)
        data = json.loads(Path(paths[0]).read_text(encoding="utf-8"))
        assert data["kind"] == "coin_discovery_pipeline_result"
        assert data["run_id"] == "run-001"
        assert data["version"] == result.version
        assert "state" in data
        assert "run_summary" in data
        assert "export_summary" in data
        assert "safety_flags" in data
        assert "reason_codes" in data
        assert "safety_notice" in data
        assert "metadata" in data
        assert data["safety_flags"]["research_only"] is True
        assert data["safety_flags"]["human_approval_required"] is True

    def test_markdown_safety_notice(
        self,
        base_config: CoinDiscoveryPipelineConfig,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        result = run_coin_discovery_pipeline(base_config)
        paths = write_coin_discovery_pipeline_result(result, base_config)
        text = Path(paths[1]).read_text(encoding="utf-8")
        assert "human-audit / research-only" in text
        assert "not a trading signal" in text
        assert "not trade approval" in text
        assert "not execution approval" in text
        assert "Explicit human approval is required" in text

    def test_whitelist_blacklist_consistency(
        self,
        base_config: CoinDiscoveryPipelineConfig,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        result = run_coin_discovery_pipeline(base_config)
        export = result.export_result
        assert export is not None
        assert "BTC/USDT" in export.whitelist or "BTC/USDT" in export.blacklist
        assert "ETH/USDT" in export.whitelist or "ETH/USDT" in export.blacklist
        # Pipeline packet export summary matches export whitelist/blacklist
        paths = write_coin_discovery_pipeline_result(result, base_config)
        data = json.loads(Path(paths[0]).read_text(encoding="utf-8"))
        assert data["export_summary"]["whitelist"] == list(export.whitelist)
        assert data["export_summary"]["blacklist"] == list(export.blacklist)

    def test_export_artifacts_are_written(
        self,
        base_config: CoinDiscoveryPipelineConfig,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        result = run_coin_discovery_pipeline(base_config)
        assert result.export_result is not None
        export_paths = write_controlled_universe_export(result.export_result)
        assert export_paths[0] is not None
        assert export_paths[1] is not None
        assert Path(export_paths[0]).exists()
        assert Path(export_paths[1]).exists()
        export_data = json.loads(Path(export_paths[0]).read_text(encoding="utf-8"))
        assert export_data["kind"] == "controlled_universe_export"
        assert export_data["whitelist"] == list(result.export_result.whitelist)

    def test_safety_flags_are_all_true(
        self,
        base_config: CoinDiscoveryPipelineConfig,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        result = run_coin_discovery_pipeline(base_config)
        flags = result.safety_flags
        assert flags.research_only is True
        assert flags.human_approval_required is True
        assert flags.no_freqtrade_runtime_connection is True
        assert flags.no_automatic_config_mutation is True
        assert flags.no_network_connection is True
        assert flags.no_exchange_connection is True
        assert flags.no_database is True
        assert flags.no_scheduler is True
        assert flags.no_action_commands_emitted is True


class TestFailClosedStates:
    def test_blocked_execution_context_is_fail_closed(
        self,
        base_config: CoinDiscoveryPipelineConfig,
        execution_context_blocked: ExecutionContext,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        config = CoinDiscoveryPipelineConfig(
            run_id=base_config.run_id,
            output_dir=base_config.output_dir,
            write_artifacts=False,
            discovery_inputs=base_config.discovery_inputs,
            execution_context=execution_context_blocked,
            generated_at=base_config.generated_at,
        )
        result = run_coin_discovery_pipeline(config)
        assert result.state == PipelineState.BLOCKED
        assert PIPELINE_RUN_BLOCKED in result.reason_codes
        assert result.export_result is not None
        assert len(result.export_result.whitelist) == 0
        # Artifacts are still written
        paths = write_coin_discovery_pipeline_result(result, config)
        assert Path(paths[0]).exists()
        assert Path(paths[1]).exists()
        data = json.loads(Path(paths[0]).read_text(encoding="utf-8"))
        assert data["state"] == PipelineState.BLOCKED.value

    def test_failed_run_is_fail_closed(
        self,
        base_config: CoinDiscoveryPipelineConfig,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        original_fn = pipeline_engine.build_research_run_result

        def _failed_fn(plan: ResearchRunPlan, config: ResearchRunConfig | None = None) -> ResearchRunResult:
            return _make_run_result(
                plan=plan,
                state=ResearchRunState.FAILED,
                reason_codes=("STEP_FAILED",),
            )

        monkeypatch.setattr(pipeline_engine, "build_research_run_result", _failed_fn)
        result = run_coin_discovery_pipeline(base_config)
        monkeypatch.setattr(pipeline_engine, "build_research_run_result", original_fn)
        assert result.state == PipelineState.FAILED
        assert PIPELINE_RUN_FAILED in result.reason_codes
        assert result.export_result is not None
        assert len(result.export_result.whitelist) == 0
        paths = write_coin_discovery_pipeline_result(result, base_config)
        assert Path(paths[0]).exists()
        data = json.loads(Path(paths[0]).read_text(encoding="utf-8"))
        assert data["state"] == PipelineState.FAILED.value

    def test_partial_run_is_fail_closed(
        self,
        base_config: CoinDiscoveryPipelineConfig,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        original_fn = pipeline_engine.build_research_run_result

        def _partial_fn(plan: ResearchRunPlan, config: ResearchRunConfig | None = None) -> ResearchRunResult:
            return _make_run_result(
                plan=plan,
                state=ResearchRunState.PARTIAL,
                reason_codes=("PARTIAL_DATA",),
            )

        monkeypatch.setattr(pipeline_engine, "build_research_run_result", _partial_fn)
        result = run_coin_discovery_pipeline(base_config)
        monkeypatch.setattr(pipeline_engine, "build_research_run_result", original_fn)
        assert result.state == PipelineState.PARTIAL
        assert PIPELINE_RUN_PARTIAL in result.reason_codes
        assert result.export_result is not None
        assert len(result.export_result.whitelist) == 0

    def test_export_disabled_skips_export(
        self,
        base_config: CoinDiscoveryPipelineConfig,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        config = CoinDiscoveryPipelineConfig(
            run_id=base_config.run_id,
            output_dir=base_config.output_dir,
            write_artifacts=False,
            discovery_inputs=base_config.discovery_inputs,
            execution_context=base_config.execution_context,
            export_enabled=False,
            generated_at=base_config.generated_at,
        )
        result = run_coin_discovery_pipeline(config)
        assert result.state == PipelineState.COMPLETED
        assert result.export_result is None
        assert EXPORT_SKIPPED in result.reason_codes


class TestDeterminism:
    def test_repeated_runs_produce_equivalent_results(
        self,
        base_config: CoinDiscoveryPipelineConfig,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        result1 = run_coin_discovery_pipeline(base_config)
        result2 = run_coin_discovery_pipeline(base_config)
        assert result1.run_id == result2.run_id
        assert result1.state == result2.state
        assert result1.reason_codes == result2.reason_codes
        assert result1.safety_flags == result2.safety_flags
        assert result1.export_result is not None
        assert result2.export_result is not None
        assert result1.export_result.whitelist == result2.export_result.whitelist
        assert result1.export_result.blacklist == result2.export_result.blacklist
        assert result1.export_result.reason_codes == result2.export_result.reason_codes
        assert result1.export_result.research_only == result2.export_result.research_only
        assert result1.export_result.human_approval_required == result2.export_result.human_approval_required
        assert result1.export_result.safety_flags == result2.export_result.safety_flags
        assert result1.export_result.metadata == result2.export_result.metadata

    def test_repeated_writes_produce_identical_artifacts(
        self,
        base_config: CoinDiscoveryPipelineConfig,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        result = run_coin_discovery_pipeline(base_config)
        paths1 = write_coin_discovery_pipeline_result(result, base_config)
        paths2 = write_coin_discovery_pipeline_result(result, base_config)
        assert Path(paths1[0]).read_text(encoding="utf-8") == Path(paths2[0]).read_text(encoding="utf-8")
        assert Path(paths1[1]).read_text(encoding="utf-8") == Path(paths2[1]).read_text(encoding="utf-8")


class TestNoDirectFileReads:
    def test_run_pipeline_does_not_read_files(
        self,
        base_config: CoinDiscoveryPipelineConfig,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        reads: list[str] = []

        original_open = open
        def _raising_open(*args: Any, **kwargs: Any) -> Any:
            if len(args) > 1 and isinstance(args[1], str) and ("r" in args[1] or args[1] == "rb"):
                reads.append(str(args[0]))
                raise AssertionError(f"open() called for read: {args[0]}")
            return original_open(*args, **kwargs)

        def _raising_read_text(self: Path, *args: Any, **kwargs: Any) -> Any:
            reads.append(str(self))
            raise AssertionError(f"Path.read_text() called: {self}")

        monkeypatch.setattr("builtins.open", _raising_open)
        monkeypatch.setattr("pathlib.Path.read_text", _raising_read_text)
        result = run_coin_discovery_pipeline(base_config)
        monkeypatch.undo()
        # Writer is allowed to read/write; run engine should not have read any file.
        assert len(reads) == 0, f"Unexpected file reads during pipeline run: {reads}"
        # Now write artifacts normally
        paths = write_coin_discovery_pipeline_result(result, base_config)
        assert Path(paths[0]).exists()
        assert Path(paths[1]).exists()


class TestNoRuntimeMutation:
    def test_no_freqtrade_config_files_created(
        self,
        base_config: CoinDiscoveryPipelineConfig,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.chdir(tmp_path)
        run_coin_discovery_pipeline(base_config)
        # Check no freqtrade config or strategy files were created in the temp tree
        for path in tmp_path.rglob("*.json"):
            # The pipeline may write its own artifacts; this test is just a sanity
            # check that no Freqtrade-style config files appear outside the pipeline
            # directory. Integration artifacts are allowed under data/ or reports/.
            assert "config.json" not in str(path) or "coin_discovery_pipeline" in str(path)


class TestPublicAPI:
    def test_all_public_symbols_are_available(self) -> None:
        from hunter.coin_discovery_pipeline import (
            COIN_DISCOVERY_PIPELINE_REASON_CODES,
            COIN_DISCOVERY_PIPELINE_VERSION,
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
            write_coin_discovery_pipeline_result,
        )

        assert PipelineState.COMPLETED is not None
        assert CoinDiscoveryPipelineConfig.__name__ == "CoinDiscoveryPipelineConfig"
        assert CoinDiscoveryPipelineResult.__name__ == "CoinDiscoveryPipelineResult"
        assert run_coin_discovery_pipeline is not None
        assert write_coin_discovery_pipeline_result is not None

    def test_writer_symbols_exported(self) -> None:
        from hunter.coin_discovery_pipeline import (
            atomic_write_json_coin_discovery_pipeline_result,
            atomic_write_markdown_coin_discovery_pipeline_result,
            coin_discovery_pipeline_result_to_dict,
            coin_discovery_pipeline_result_to_json_text,
            coin_discovery_pipeline_result_to_markdown_text,
        )

        assert callable(coin_discovery_pipeline_result_to_dict)
        assert callable(coin_discovery_pipeline_result_to_json_text)
        assert callable(coin_discovery_pipeline_result_to_markdown_text)
        assert callable(atomic_write_json_coin_discovery_pipeline_result)
        assert callable(atomic_write_markdown_coin_discovery_pipeline_result)
