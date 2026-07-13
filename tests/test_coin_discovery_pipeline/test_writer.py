"""Tests for the coin-discovery pipeline writer (MVP-54 Step 3)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hunter.coin_discovery_pipeline import (
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
    write_coin_discovery_pipeline_result,
)
from hunter.controlled_universe_export_adapter.models import (
    ControlledUniverseExportResult,
    ControlledUniversePairExportSummary,
)
from hunter.discovery.models import DiscoveryInput
from hunter.execution.models import ExecutionContext
from hunter.run_orchestrator.models import (
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
)


def _dt() -> datetime:
    return datetime(2026, 7, 13, 12, 0, 0, tzinfo=timezone.utc)


def _make_config(tmp_path: Path, *, output_dir: str | None = None) -> CoinDiscoveryPipelineConfig:
    """Return a minimal valid CoinDiscoveryPipelineConfig using temp directories."""
    return CoinDiscoveryPipelineConfig(
        run_id="run-001",
        output_dir=output_dir or str(tmp_path / "pipeline"),
        discovery_inputs=(DiscoveryInput(pair="BTC/USDT"),),
        execution_context=ExecutionContext.blocked(timestamp=_dt()),
        write_artifacts=False,
    )


def _make_run_result(
    *,
    run_id: str = "run-001",
    state: ResearchRunState = ResearchRunState.COMPLETED,
) -> ResearchRunResult:
    """Create a minimal ResearchRunResult for writer tests."""
    step = ResearchRunStep(
        kind=ResearchRunStepKind.DISCOVERY,
        step_id="discovery",
    )
    plan = ResearchRunPlan(run_id=run_id, steps=(step,))
    step_result = ResearchRunStepResult(
        step_index=0,
        step_id="discovery",
        kind=ResearchRunStepKind.DISCOVERY,
        state=ResearchRunStepState.SUCCESS,
        reason_codes=(),
        data={},
        output_paths=(),
        notes=(),
    )
    return ResearchRunResult(
        run_id=run_id,
        config=ResearchRunConfig(output_dir="data/run", generated_at=_dt()),
        plan=plan,
        steps=(step_result,),
        artifacts=(),
        data_quality=ResearchRunDataQuality(),
        safety_flags=ResearchRunSafetyFlags(),
        reason_codes=(),
        generated_at=_dt(),
        state=state,
        metadata={},
        notes=(),
    )


def _make_export_result(
    *,
    report_id: str = "export-001",
    whitelist: tuple[str, ...] = ("BTC/USDT",),
    blacklist: tuple[str, ...] = ("ETH/USDT",),
) -> ControlledUniverseExportResult:
    """Create a minimal ControlledUniverseExportResult for writer tests."""
    return ControlledUniverseExportResult(
        report_id=report_id,
        generated_at=_dt(),
        whitelist=whitelist,
        blacklist=blacklist,
        per_pair_summary=(
            ControlledUniversePairExportSummary(
                pair="BTC/USDT",
                state="INCLUDED",
                classification="LONG_RESEARCH",
                reason_codes=("PASSED_UNIVERSE_FILTER",),
                human_note="passed",
            ),
            ControlledUniversePairExportSummary(
                pair="ETH/USDT",
                state="BLOCKED",
                classification="BLOCKED_BY_MACRO",
                reason_codes=("MACRO_MODE_NONE",),
                human_note="blocked",
            ),
        ),
        research_only=True,
        human_approval_required=True,
        reason_codes=("EXPORT_RESEARCH_ONLY", "EXPORT_HUMAN_APPROVAL_REQUIRED"),
        safety_flags={"research_only": True},
        metadata={"source": "pipeline"},
    )


def _make_result(
    *,
    run_id: str = "run-001",
    state: PipelineState = PipelineState.COMPLETED,
    run_result: ResearchRunResult | None = None,
    export_result: ControlledUniverseExportResult | None = None,
    export_paths: tuple[str, ...] = (),
    pipeline_paths: tuple[str, ...] = (),
    reason_codes: tuple[str, ...] | None = None,
    metadata: dict[str, str] | None = None,
) -> CoinDiscoveryPipelineResult:
    """Create a minimal CoinDiscoveryPipelineResult for writer tests."""
    return CoinDiscoveryPipelineResult(
        run_id=run_id,
        state=state,
        run_result=run_result,
        export_result=export_result,
        export_paths=export_paths,
        pipeline_paths=pipeline_paths,
        safety_flags=CoinDiscoveryPipelineSafetyFlags(),
        reason_codes=reason_codes or (PIPELINE_RESEARCH_ONLY,),
        metadata=metadata or {},
    )


class TestCoinDiscoveryPipelineResultToDict:
    def test_includes_all_fields(self) -> None:
        run_result = _make_run_result()
        export_result = _make_export_result()
        result = _make_result(
            run_result=run_result,
            export_result=export_result,
            export_paths=("data/export.json",),
            pipeline_paths=("data/pipeline.json",),
            metadata={"source": "test"},
        )
        data = coin_discovery_pipeline_result_to_dict(result)

        assert data["kind"] == "coin_discovery_pipeline_result"
        assert data["version"] == result.version
        assert data["safety_notice"] is not None
        assert data["run_id"] == "run-001"
        assert data["state"] == "COMPLETED"
        assert data["safety_flags"] == {
            "research_only": True,
            "human_approval_required": True,
            "no_freqtrade_runtime_connection": True,
            "no_automatic_config_mutation": True,
            "no_network_connection": True,
            "no_exchange_connection": True,
            "no_database": True,
            "no_scheduler": True,
            "no_action_commands_emitted": True,
        }
        assert "PIPELINE_RESEARCH_ONLY" in data["reason_codes"]
        assert data["export_paths"] == ["data/export.json"]
        assert data["pipeline_paths"] == ["data/pipeline.json"]
        assert data["metadata"] == {"source": "test"}
        assert data["run_summary"] is not None
        assert data["run_summary"]["run_id"] == "run-001"
        assert data["run_summary"]["state"] == "COMPLETED"
        assert data["run_summary"]["step_count"] == 1
        assert data["export_summary"] is not None
        assert data["export_summary"]["report_id"] == "export-001"
        assert data["export_summary"]["whitelist"] == ["BTC/USDT"]
        assert data["export_summary"]["blacklist"] == ["ETH/USDT"]
        assert data["export_summary"]["per_pair_summary_count"] == 2

    def test_missing_run_and_export_results(self) -> None:
        result = _make_result()
        data = coin_discovery_pipeline_result_to_dict(result)
        assert data["run_summary"] is None
        assert data["export_summary"] is None

    def test_blocked_state(self) -> None:
        result = _make_result(state=PipelineState.BLOCKED)
        data = coin_discovery_pipeline_result_to_dict(result)
        assert data["state"] == "BLOCKED"

    def test_failed_state(self) -> None:
        result = _make_result(
            state=PipelineState.FAILED,
            run_result=_make_run_result(state=ResearchRunState.FAILED),
        )
        data = coin_discovery_pipeline_result_to_dict(result)
        assert data["state"] == "FAILED"
        assert data["run_summary"]["state"] == "FAILED"

    def test_partial_state(self) -> None:
        result = _make_result(
            state=PipelineState.PARTIAL,
            run_result=_make_run_result(state=ResearchRunState.PARTIAL),
        )
        data = coin_discovery_pipeline_result_to_dict(result)
        assert data["state"] == "PARTIAL"
        assert data["run_summary"]["state"] == "PARTIAL"

    def test_invalid_result_type_raises(self) -> None:
        with pytest.raises(CoinDiscoveryPipelineError, match="CoinDiscoveryPipelineResult"):
            coin_discovery_pipeline_result_to_dict("not-a-result")  # type: ignore[arg-type]


class TestCoinDiscoveryPipelineResultToJsonText:
    def test_valid_json(self) -> None:
        result = _make_result(
            run_result=_make_run_result(),
            export_result=_make_export_result(),
        )
        text = coin_discovery_pipeline_result_to_json_text(result)
        data = json.loads(text)
        assert data["run_id"] == "run-001"
        assert data["state"] == "COMPLETED"
        assert data["run_summary"]["run_id"] == "run-001"
        assert data["export_summary"]["report_id"] == "export-001"

    def test_deterministic_key_order(self) -> None:
        result = _make_result(
            run_result=_make_run_result(),
            export_result=_make_export_result(),
        )
        text = coin_discovery_pipeline_result_to_json_text(result)
        assert text.startswith('{\n  "export_paths":')

    def test_identical_input_produces_identical_output(self) -> None:
        result = _make_result(
            run_result=_make_run_result(),
            export_result=_make_export_result(),
        )
        text1 = coin_discovery_pipeline_result_to_json_text(result)
        text2 = coin_discovery_pipeline_result_to_json_text(result)
        assert text1 == text2


class TestCoinDiscoveryPipelineResultToMarkdownText:
    def test_contains_safety_notice(self) -> None:
        result = _make_result()
        text = coin_discovery_pipeline_result_to_markdown_text(result)
        assert "Coin Discovery Pipeline Result" in text
        assert "research-only" in text
        assert "human approval is required" in text

    def test_contains_run_and_export_summaries(self) -> None:
        result = _make_result(
            run_result=_make_run_result(),
            export_result=_make_export_result(),
        )
        text = coin_discovery_pipeline_result_to_markdown_text(result)
        assert "Run Summary" in text
        assert "Export Summary" in text
        assert "BTC/USDT" in text
        assert "ETH/USDT" in text

    def test_missing_run_and_export_results(self) -> None:
        result = _make_result()
        text = coin_discovery_pipeline_result_to_markdown_text(result)
        assert "Run Summary" not in text
        assert "Export Summary" not in text

    def test_contains_safety_flags_and_reason_codes(self) -> None:
        result = _make_result()
        text = coin_discovery_pipeline_result_to_markdown_text(result)
        assert "Safety Flags" in text
        assert "research_only" in text
        assert "Reason Codes" in text
        assert "PIPELINE_RESEARCH_ONLY" in text

    def test_no_disallowed_trading_wording(self) -> None:
        result = _make_result(
            run_result=_make_run_result(),
            export_result=_make_export_result(),
        )
        text = coin_discovery_pipeline_result_to_markdown_text(result).lower()
        disallowed_phrases = [
            "buy order",
            "sell order",
            "place order",
            "execute trade",
            "execute order",
            "take profit",
            "stop loss",
            "leverage",
            "position size",
            "entry price",
            "exit price",
        ]
        for phrase in disallowed_phrases:
            assert phrase not in text, f"disallowed phrase found: {phrase}"

    def test_identical_input_produces_identical_output(self) -> None:
        result = _make_result(
            run_result=_make_run_result(),
            export_result=_make_export_result(),
        )
        text1 = coin_discovery_pipeline_result_to_markdown_text(result)
        text2 = coin_discovery_pipeline_result_to_markdown_text(result)
        assert text1 == text2


class TestAtomicWriteJson:
    def test_writes_json_file(self, tmp_path: Path) -> None:
        result = _make_result(
            run_result=_make_run_result(),
            export_result=_make_export_result(),
        )
        path = tmp_path / "pipeline.json"
        written = atomic_write_json_coin_discovery_pipeline_result(result, path)
        assert written == path
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["run_id"] == "run-001"

    def test_no_tmp_file_left_behind(self, tmp_path: Path) -> None:
        result = _make_result()
        path = tmp_path / "pipeline.json"
        atomic_write_json_coin_discovery_pipeline_result(result, path)
        assert not (tmp_path / "pipeline.json.tmp").exists()

    def test_default_path(self, tmp_path: Path) -> None:
        result = _make_result()
        # Use monkeypatch or a different cwd if testing default path; here we use tmp_path
        from hunter.coin_discovery_pipeline import writer as writer_module

        default_path = writer_module.DEFAULT_JSON_PATH
        assert "data/coin_discovery_pipeline" in str(default_path)


class TestAtomicWriteMarkdown:
    def test_writes_markdown_file(self, tmp_path: Path) -> None:
        result = _make_result(
            run_result=_make_run_result(),
            export_result=_make_export_result(),
        )
        path = tmp_path / "pipeline.md"
        written = atomic_write_markdown_coin_discovery_pipeline_result(result, path)
        assert written == path
        assert path.exists()
        text = path.read_text(encoding="utf-8")
        assert "Coin Discovery Pipeline Result" in text

    def test_no_tmp_file_left_behind(self, tmp_path: Path) -> None:
        result = _make_result()
        path = tmp_path / "pipeline.md"
        atomic_write_markdown_coin_discovery_pipeline_result(result, path)
        assert not (tmp_path / "pipeline.md.tmp").exists()


class TestWriteCoinDiscoveryPipelineResult:
    def test_writes_both_artifacts(self, tmp_path: Path) -> None:
        result = _make_result(
            run_result=_make_run_result(),
            export_result=_make_export_result(),
        )
        config = _make_config(tmp_path)
        paths = write_coin_discovery_pipeline_result(result, config)
        assert len(paths) == 2
        json_path = Path(paths[0])
        md_path = Path(paths[1])
        assert json_path.exists()
        assert md_path.exists()
        assert json_path.name == "pipeline.json"
        assert md_path.name == "pipeline.md"
        assert "run-001" in str(json_path)
        assert "run-001" in str(md_path)
        assert str(md_path).startswith("reports")

    def test_invalid_config_raises(self) -> None:
        result = _make_result()
        with pytest.raises(CoinDiscoveryPipelineError, match="CoinDiscoveryPipelineConfig"):
            write_coin_discovery_pipeline_result(result, "not-a-config")  # type: ignore[arg-type]

    def test_invalid_result_raises(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        with pytest.raises(CoinDiscoveryPipelineError, match="CoinDiscoveryPipelineResult"):
            write_coin_discovery_pipeline_result("not-a-result", config)  # type: ignore[arg-type]


class TestWriteDeterminism:
    def test_repeated_identical_input_produces_identical_files(self, tmp_path: Path) -> None:
        result = _make_result(
            run_result=_make_run_result(),
            export_result=_make_export_result(),
        )
        config = _make_config(tmp_path)
        paths1 = write_coin_discovery_pipeline_result(result, config)
        json1 = Path(paths1[0]).read_text(encoding="utf-8")
        md1 = Path(paths1[1]).read_text(encoding="utf-8")
        # Remove written files to ensure second write produces identical content
        Path(paths1[0]).unlink()
        Path(paths1[1]).unlink()
        paths2 = write_coin_discovery_pipeline_result(result, config)
        json2 = Path(paths2[0]).read_text(encoding="utf-8")
        md2 = Path(paths2[1]).read_text(encoding="utf-8")
        assert json1 == json2
        assert md1 == md2


class TestBlockedFailedPartialSerialization:
    def test_blocked_result_serialization(self) -> None:
        result = _make_result(
            state=PipelineState.BLOCKED,
            reason_codes=(PIPELINE_RUN_BLOCKED,),
        )
        text = coin_discovery_pipeline_result_to_markdown_text(result)
        assert "state:** BLOCKED" in text or "state: BLOCKED" in text
        assert "PIPELINE_RUN_BLOCKED" in text

    def test_failed_result_serialization(self) -> None:
        result = _make_result(
            state=PipelineState.FAILED,
            run_result=_make_run_result(state=ResearchRunState.FAILED),
            reason_codes=(PIPELINE_RUN_FAILED,),
        )
        text = coin_discovery_pipeline_result_to_markdown_text(result)
        assert "FAILED" in text
        assert "PIPELINE_RUN_FAILED" in text

    def test_partial_result_serialization(self) -> None:
        result = _make_result(
            state=PipelineState.PARTIAL,
            run_result=_make_run_result(state=ResearchRunState.PARTIAL),
            reason_codes=(PIPELINE_RUN_PARTIAL,),
        )
        text = coin_discovery_pipeline_result_to_markdown_text(result)
        assert "PARTIAL" in text
        assert "PIPELINE_RUN_PARTIAL" in text
