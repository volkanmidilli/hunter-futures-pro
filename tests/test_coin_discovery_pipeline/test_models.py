"""Tests for the coin_discovery_pipeline models (MVP-54 Step 1)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

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
)
from hunter.coin_discovery_pipeline.models import (
    _coerce_mapping_strs,
    _coerce_tuple_strs,
    _utc_now,
)
from hunter.discovery.models import DiscoveryInput
from hunter.execution.models import ExecutionContext


@pytest.fixture
def discovery_input() -> DiscoveryInput:
    return DiscoveryInput(pair="BTC/USDT")


@pytest.fixture
def execution_context() -> ExecutionContext:
    return ExecutionContext.blocked()


class TestVersionAndReasonCodes:
    def test_version_constant(self) -> None:
        assert COIN_DISCOVERY_PIPELINE_VERSION == "0.54.0-dev"

    def test_all_reason_codes_present(self) -> None:
        expected = {
            INVALID_PIPELINE_CONFIG,
            PIPELINE_RESEARCH_ONLY,
            PIPELINE_HUMAN_APPROVAL_REQUIRED,
            NO_FREQTRADE_RUNTIME_CONNECTION,
            NO_AUTOMATIC_CONFIG_MUTATION,
            EXPORT_SKIPPED,
            PIPELINE_RUN_FAILED,
            PIPELINE_RUN_BLOCKED,
            PIPELINE_RUN_PARTIAL,
        }
        assert COIN_DISCOVERY_PIPELINE_REASON_CODES == expected


class TestPipelineState:
    def test_enum_values(self) -> None:
        assert PipelineState.COMPLETED.value == "COMPLETED"
        assert PipelineState.FAILED.value == "FAILED"
        assert PipelineState.BLOCKED.value == "BLOCKED"
        assert PipelineState.PARTIAL.value == "PARTIAL"


class TestCoinDiscoveryPipelineSafetyFlags:
    def test_defaults(self) -> None:
        flags = CoinDiscoveryPipelineSafetyFlags()
        assert flags.research_only is True
        assert flags.human_approval_required is True
        assert flags.no_freqtrade_runtime_connection is True
        assert flags.no_automatic_config_mutation is True
        assert flags.no_network_connection is True
        assert flags.no_exchange_connection is True
        assert flags.no_database is True
        assert flags.no_scheduler is True
        assert flags.no_action_commands_emitted is True

    def test_non_bool_flag_raises(self) -> None:
        with pytest.raises(ValueError, match="research_only must be a bool"):
            CoinDiscoveryPipelineSafetyFlags(research_only="yes")  # type: ignore[arg-type]


class TestCoinDiscoveryPipelineConfig:
    def test_valid_config(self, discovery_input: DiscoveryInput, execution_context: ExecutionContext) -> None:
        config = CoinDiscoveryPipelineConfig(
            run_id="test-run",
            output_dir="data/test",
            discovery_inputs=(discovery_input,),
            execution_context=execution_context,
        )
        assert config.run_id == "test-run"
        assert config.output_dir == "data/test"
        assert config.write_artifacts is True
        assert config.fail_fast is True
        assert config.export_enabled is True
        assert config.export_config is None
        assert config.run_config is None
        assert config.discovery_inputs == (discovery_input,)
        assert config.portfolio_construction_inputs is None
        assert config.discovery_config is None
        assert config.portfolio_construction_config is None
        assert config.controlled_universe_config is None
        assert config.execution_context is execution_context
        assert dict(config.metadata) == {}

    def test_default_classmethod(
        self, discovery_input: DiscoveryInput, execution_context: ExecutionContext
    ) -> None:
        config = CoinDiscoveryPipelineConfig.default(
            discovery_inputs=(discovery_input,),
            execution_context=execution_context,
        )
        assert config.run_id.startswith("run-")
        assert config.output_dir == "data/coin_discovery_pipeline"
        assert config.discovery_inputs == (discovery_input,)
        assert config.execution_context is execution_context

    def test_default_with_custom_run_id(
        self, discovery_input: DiscoveryInput, execution_context: ExecutionContext
    ) -> None:
        config = CoinDiscoveryPipelineConfig.default(
            run_id="custom-run",
            output_dir="custom/output",
            discovery_inputs=(discovery_input,),
            execution_context=execution_context,
        )
        assert config.run_id == "custom-run"
        assert config.output_dir == "custom/output"

    def test_empty_run_id_is_allowed_at_init(self, discovery_input: DiscoveryInput, execution_context: ExecutionContext) -> None:
        # Empty run_id is allowed by the model; the runner will supply a default.
        config = CoinDiscoveryPipelineConfig(
            run_id="",
            output_dir="data/test",
            discovery_inputs=(discovery_input,),
            execution_context=execution_context,
        )
        assert config.run_id == ""

    def test_missing_discovery_inputs(self, execution_context: ExecutionContext) -> None:
        with pytest.raises(ValueError, match="discovery_inputs must contain at least one"):
            CoinDiscoveryPipelineConfig(
                run_id="test",
                output_dir="data/test",
                discovery_inputs=(),
                execution_context=execution_context,
            )

    def test_invalid_discovery_input_type(self, execution_context: ExecutionContext) -> None:
        with pytest.raises(ValueError, match=r"discovery_inputs\[0\] must be a DiscoveryInput"):
            CoinDiscoveryPipelineConfig(
                run_id="test",
                output_dir="data/test",
                discovery_inputs=("not-a-discovery-input",),  # type: ignore[arg-type]
                execution_context=execution_context,
            )

    def test_empty_output_dir(self, discovery_input: DiscoveryInput, execution_context: ExecutionContext) -> None:
        with pytest.raises(ValueError, match="output_dir must be a non-empty string"):
            CoinDiscoveryPipelineConfig(
                run_id="test",
                output_dir="  ",
                discovery_inputs=(discovery_input,),
                execution_context=execution_context,
            )

    def test_invalid_write_artifacts(self, discovery_input: DiscoveryInput, execution_context: ExecutionContext) -> None:
        with pytest.raises(ValueError, match="write_artifacts must be a bool"):
            CoinDiscoveryPipelineConfig(
                run_id="test",
                write_artifacts="yes",  # type: ignore[arg-type]
                discovery_inputs=(discovery_input,),
                execution_context=execution_context,
            )

    def test_invalid_fail_fast(self, discovery_input: DiscoveryInput, execution_context: ExecutionContext) -> None:
        with pytest.raises(ValueError, match="fail_fast must be a bool"):
            CoinDiscoveryPipelineConfig(
                run_id="test",
                fail_fast="yes",  # type: ignore[arg-type]
                discovery_inputs=(discovery_input,),
                execution_context=execution_context,
            )

    def test_invalid_export_enabled(self, discovery_input: DiscoveryInput, execution_context: ExecutionContext) -> None:
        with pytest.raises(ValueError, match="export_enabled must be a bool"):
            CoinDiscoveryPipelineConfig(
                run_id="test",
                export_enabled="yes",  # type: ignore[arg-type]
                discovery_inputs=(discovery_input,),
                execution_context=execution_context,
            )

    def test_invalid_export_config(self, discovery_input: DiscoveryInput, execution_context: ExecutionContext) -> None:
        with pytest.raises(ValueError, match="export_config must be a ControlledUniverseExportConfig"):
            CoinDiscoveryPipelineConfig(
                run_id="test",
                export_config={"invalid": "config"},  # type: ignore[arg-type]
                discovery_inputs=(discovery_input,),
                execution_context=execution_context,
            )

    def test_invalid_run_config(self, discovery_input: DiscoveryInput, execution_context: ExecutionContext) -> None:
        with pytest.raises(ValueError, match="run_config must be a ResearchRunConfig"):
            CoinDiscoveryPipelineConfig(
                run_id="test",
                run_config={"invalid": "config"},  # type: ignore[arg-type]
                discovery_inputs=(discovery_input,),
                execution_context=execution_context,
            )

    def test_invalid_execution_context(self, discovery_input: DiscoveryInput) -> None:
        with pytest.raises(ValueError, match="execution_context must be an ExecutionContext"):
            CoinDiscoveryPipelineConfig(
                run_id="test",
                discovery_inputs=(discovery_input,),
                execution_context={"invalid": "context"},  # type: ignore[arg-type]
            )

    def test_metadata_coerced(self, discovery_input: DiscoveryInput, execution_context: ExecutionContext) -> None:
        config = CoinDiscoveryPipelineConfig(
            run_id="test",
            discovery_inputs=(discovery_input,),
            execution_context=execution_context,
            metadata={"key": "value"},
        )
        assert dict(config.metadata) == {"key": "value"}

    def test_generated_at_naive(self, discovery_input: DiscoveryInput, execution_context: ExecutionContext) -> None:
        with pytest.raises(ValueError, match="generated_at must be timezone-aware"):
            CoinDiscoveryPipelineConfig(
                run_id="test",
                discovery_inputs=(discovery_input,),
                execution_context=execution_context,
                generated_at=datetime.now(),  # type: ignore[arg-type]
            )

    def test_generated_at_invalid_type(self, discovery_input: DiscoveryInput, execution_context: ExecutionContext) -> None:
        with pytest.raises(ValueError, match="generated_at must be a datetime"):
            CoinDiscoveryPipelineConfig(
                run_id="test",
                discovery_inputs=(discovery_input,),
                execution_context=execution_context,
                generated_at="not-a-datetime",  # type: ignore[arg-type]
            )


class TestCoinDiscoveryPipelineResult:
    def test_valid_result(self) -> None:
        result = CoinDiscoveryPipelineResult(
            run_id="test-run",
            state=PipelineState.COMPLETED,
            run_result=None,
            export_result=None,
            export_paths=(),
            pipeline_paths=(),
            safety_flags=CoinDiscoveryPipelineSafetyFlags(),
            reason_codes=(PIPELINE_RESEARCH_ONLY,),
            metadata={"note": "test"},
        )
        assert result.run_id == "test-run"
        assert result.state == PipelineState.COMPLETED
        assert result.version == COIN_DISCOVERY_PIPELINE_VERSION

    def test_empty_run_id(self) -> None:
        with pytest.raises(ValueError, match="run_id must be a non-empty string"):
            CoinDiscoveryPipelineResult(
                run_id="",
                state=PipelineState.COMPLETED,
                run_result=None,
                export_result=None,
                export_paths=(),
                pipeline_paths=(),
                safety_flags=CoinDiscoveryPipelineSafetyFlags(),
                reason_codes=(),
                metadata={},
            )

    def test_invalid_state(self) -> None:
        with pytest.raises(ValueError, match="state must be a PipelineState"):
            CoinDiscoveryPipelineResult(
                run_id="test-run",
                state="COMPLETED",  # type: ignore[arg-type]
                run_result=None,
                export_result=None,
                export_paths=(),
                pipeline_paths=(),
                safety_flags=CoinDiscoveryPipelineSafetyFlags(),
                reason_codes=(),
                metadata={},
            )

    def test_invalid_safety_flags(self) -> None:
        with pytest.raises(ValueError, match="safety_flags must be a CoinDiscoveryPipelineSafetyFlags"):
            CoinDiscoveryPipelineResult(
                run_id="test-run",
                state=PipelineState.COMPLETED,
                run_result=None,
                export_result=None,
                export_paths=(),
                pipeline_paths=(),
                safety_flags={"research_only": True},  # type: ignore[arg-type]
                reason_codes=(),
                metadata={},
            )

    def test_empty_reason_code(self) -> None:
        with pytest.raises(ValueError, match="reason_codes must contain non-empty strings"):
            CoinDiscoveryPipelineResult(
                run_id="test-run",
                state=PipelineState.COMPLETED,
                run_result=None,
                export_result=None,
                export_paths=(),
                pipeline_paths=(),
                safety_flags=CoinDiscoveryPipelineSafetyFlags(),
                reason_codes=("",),
                metadata={},
            )

    def test_lists_coerced_to_tuples(self) -> None:
        result = CoinDiscoveryPipelineResult(
            run_id="test-run",
            state=PipelineState.COMPLETED,
            run_result=None,
            export_result=None,
            export_paths=["a"],
            pipeline_paths=["b"],
            safety_flags=CoinDiscoveryPipelineSafetyFlags(),
            reason_codes=[PIPELINE_RESEARCH_ONLY],
            metadata={},
        )
        assert isinstance(result.export_paths, tuple)
        assert isinstance(result.pipeline_paths, tuple)
        assert isinstance(result.reason_codes, tuple)

    def test_metadata_coerced(self) -> None:
        result = CoinDiscoveryPipelineResult(
            run_id="test-run",
            state=PipelineState.COMPLETED,
            run_result=None,
            export_result=None,
            export_paths=(),
            pipeline_paths=(),
            safety_flags=CoinDiscoveryPipelineSafetyFlags(),
            reason_codes=(),
            metadata={"key": "value"},
        )
        assert dict(result.metadata) == {"key": "value"}


class TestCoinDiscoveryPipelineError:
    def test_exception_subclass(self) -> None:
        assert issubclass(CoinDiscoveryPipelineError, Exception)

    def test_exception_message(self) -> None:
        with pytest.raises(CoinDiscoveryPipelineError, match="stub error"):
            raise CoinDiscoveryPipelineError("stub error")


class TestEngineStubs:
    def test_run_coin_discovery_pipeline_rejects_invalid_config(self) -> None:
        result = run_coin_discovery_pipeline(None)  # type: ignore[arg-type]
        assert result.state == PipelineState.BLOCKED
        assert INVALID_PIPELINE_CONFIG in result.reason_codes

    def test_run_coin_discovery_pipeline_runs_with_valid_config(
        self,
        discovery_input: DiscoveryInput,
        execution_context: ExecutionContext,
        tmp_path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Contain the engine's relative default output paths (data/, reports/)
        # inside tmp_path rather than the real repository tree.
        monkeypatch.chdir(tmp_path)
        config = CoinDiscoveryPipelineConfig(
            run_id="test",
            discovery_inputs=(discovery_input,),
            execution_context=execution_context,
        )
        result = run_coin_discovery_pipeline(config)
        assert isinstance(result, CoinDiscoveryPipelineResult)
        assert result.run_id == "test"
        assert result.state in {state for state in PipelineState}


class TestCoerceHelpers:
    def test_coerce_tuple_strs_deduplicates(self) -> None:
        assert _coerce_tuple_strs(["a", "a", "b"]) == ("a", "b")

    def test_coerce_tuple_strs_none(self) -> None:
        assert _coerce_tuple_strs(None) == ()

    def test_coerce_mapping_strs(self) -> None:
        mapping = _coerce_mapping_strs({"a": 1, "b": 2})
        assert dict(mapping) == {"a": "1", "b": "2"}

    def test_coerce_mapping_strs_none(self) -> None:
        mapping = _coerce_mapping_strs(None)
        assert dict(mapping) == {}

    def test_utc_now(self) -> None:
        now = _utc_now()
        assert now.tzinfo is not None


class TestPublicAPI:
    def test_all_expected_symbols_importable(self) -> None:
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
            atomic_write_json_coin_discovery_pipeline_result,
            atomic_write_markdown_coin_discovery_pipeline_result,
            coin_discovery_pipeline_result_to_dict,
            coin_discovery_pipeline_result_to_json_text,
            coin_discovery_pipeline_result_to_markdown_text,
            run_coin_discovery_pipeline,
            write_coin_discovery_pipeline_result,
        )

        assert CoinDiscoveryPipelineConfig.__name__ == "CoinDiscoveryPipelineConfig"
        assert CoinDiscoveryPipelineResult.__name__ == "CoinDiscoveryPipelineResult"
        assert PipelineState.__name__ == "PipelineState"
