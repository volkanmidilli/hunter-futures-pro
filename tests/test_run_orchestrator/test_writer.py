"""Tests for hunter.run_orchestrator.writer.

All tests use in-memory fixtures and tmp_path only. No network, exchange,
Binance, Freqtrade, or database references are used.
"""

from __future__ import annotations

import csv
import json
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
from hunter.run_orchestrator import (
    DEFAULT_CSV_PATH,
    DEFAULT_JSON_PATH,
    DEFAULT_MD_PATH,
    NOT_TRADING_ADVICE,
    OK,
    RESEARCH_ONLY,
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
    RUN_BLOCKED,
    RUN_ORCHESTRATOR_VERSION,
    STEP_BLOCKED,
    STEP_FAILED,
    UNSAFE_RUN_CONTENT,
    atomic_write_csv_research_run_result,
    atomic_write_json_research_run_result,
    atomic_write_markdown_research_run_result,
    research_run_result_to_csv_text,
    research_run_result_to_dict,
    research_run_result_to_json_text,
    research_run_result_to_markdown_text,
    write_research_run_result,
)


@pytest.fixture
def fixed_generated_at() -> datetime:
    return datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def backtest_dataclass_step() -> ResearchRunStep:
    """A backtest step whose inputs contain nested engine dataclasses."""
    decision = BacktestCandidateDecision(
        pair="BTC/USDT",
        state="INCLUDED",
        classification="CORE_RESEARCH_ALLOCATION",
        final_weight_pct=50.0,
    )
    bars = (
        BacktestPriceBar(
            pair="BTC/USDT",
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            close=100.0,
        ),
    )
    inp = BacktestInput(pair="BTC/USDT", decision=decision, price_bars=bars)
    config = BacktestRunConfig(allocation_mode=BacktestAllocationMode.EQUAL_WEIGHT)
    return ResearchRunStep(
        kind=ResearchRunStepKind.BACKTEST,
        step_id="bt-dc",
        inputs={"inputs": (inp,), "config": config},
    )


@pytest.fixture
def sample_step() -> ResearchRunStep:
    return ResearchRunStep(
        kind=ResearchRunStepKind.BACKTEST,
        step_id="s1",
        inputs={"inputs": []},
        metadata={"note": "sample"},
    )


@pytest.fixture
def sample_plan(sample_step: ResearchRunStep) -> ResearchRunPlan:
    return ResearchRunPlan(run_id="r1", steps=(sample_step,), metadata={"env": "test"})


@pytest.fixture
def sample_config(fixed_generated_at: datetime) -> ResearchRunConfig:
    return ResearchRunConfig(
        output_dir="data/run_orchestrator/latest_run",
        generated_at=fixed_generated_at,
        metadata={"author": "test"},
    )


@pytest.fixture
def sample_step_result(fixed_generated_at: datetime) -> ResearchRunStepResult:
    return ResearchRunStepResult(
        step_index=0,
        step_id="s1",
        kind=ResearchRunStepKind.BACKTEST,
        state=ResearchRunStepState.SUCCESS,
        reason_codes=(OK,),
        data={"report_id": "backtest-s1"},
        output_paths=("data/run_orchestrator/latest_run/0_backtest/backtest_report.json",),
        notes=("completed",),
        error_message="",
    )


@pytest.fixture
def sample_artifact() -> ResearchRunArtifact:
    return ResearchRunArtifact(
        step_index=0,
        step_id="s1",
        kind="json_report",
        path="data/run_orchestrator/latest_run/0_backtest/backtest_report.json",
        metadata={"format": "json"},
    )


@pytest.fixture
def sample_data_quality() -> ResearchRunDataQuality:
    return ResearchRunDataQuality(
        total_steps=1,
        successful_steps=1,
        failed_steps=0,
        blocked_steps=0,
        skipped_steps=0,
        sections_present=("RUN_ID", "STEPS", "DATA_QUALITY", "SAFETY_FLAGS"),
        sections_expected=("RUN_ID", "STEPS", "DATA_QUALITY", "SAFETY_FLAGS"),
        notes=("Run executed 1 step(s): 1 success, 0 failed, 0 blocked, 0 skipped.",),
    )


@pytest.fixture
def sample_result(
    sample_plan: ResearchRunPlan,
    sample_config: ResearchRunConfig,
    sample_step_result: ResearchRunStepResult,
    sample_artifact: ResearchRunArtifact,
    sample_data_quality: ResearchRunDataQuality,
    fixed_generated_at: datetime,
) -> ResearchRunResult:
    return ResearchRunResult(
        run_id=sample_plan.run_id,
        config=sample_config,
        plan=sample_plan,
        steps=(sample_step_result,),
        artifacts=(sample_artifact,),
        data_quality=sample_data_quality,
        safety_flags=ResearchRunSafetyFlags(),
        reason_codes=(RESEARCH_ONLY, NOT_TRADING_ADVICE, OK),
        generated_at=fixed_generated_at,
        state=ResearchRunState.COMPLETED,
        metadata={"mode": "test"},
        notes=("completed run",),
    )


def _make_result_for_step(
    step: ResearchRunStep, generated_at: datetime, run_id: str
) -> ResearchRunResult:
    """Build a minimal ResearchRunResult wrapping the given step."""
    config = ResearchRunConfig(generated_at=generated_at)
    plan = ResearchRunPlan(run_id=run_id, steps=(step,))
    return ResearchRunResult(
        run_id=run_id,
        config=config,
        plan=plan,
        steps=(),
        artifacts=(),
        data_quality=ResearchRunDataQuality(),
        safety_flags=ResearchRunSafetyFlags(),
        reason_codes=(RESEARCH_ONLY,),
        generated_at=generated_at,
        state=ResearchRunState.COMPLETED,
        metadata={},
        notes=(),
    )


# ---------------------------------------------------------------------------
# Public exports
# ---------------------------------------------------------------------------


class TestPublicExports:
    def test_writer_functions_exported(self) -> None:
        assert callable(research_run_result_to_dict)
        assert callable(research_run_result_to_json_text)
        assert callable(research_run_result_to_csv_text)
        assert callable(research_run_result_to_markdown_text)
        assert callable(write_research_run_result)
        assert callable(atomic_write_json_research_run_result)
        assert callable(atomic_write_csv_research_run_result)
        assert callable(atomic_write_markdown_research_run_result)

    def test_default_paths_exported(self) -> None:
        assert DEFAULT_JSON_PATH == Path("data/run_orchestrator/run_summary.json")
        assert DEFAULT_CSV_PATH == Path("data/run_orchestrator/run_steps.csv")
        assert DEFAULT_MD_PATH == Path("reports/run_orchestrator/run_summary.md")


# ---------------------------------------------------------------------------
# Dict conversion
# ---------------------------------------------------------------------------


class TestDictConversion:
    def test_dict_includes_run_steps_artifacts_data_quality_and_safety(
        self, sample_result: ResearchRunResult
    ) -> None:
        data = research_run_result_to_dict(sample_result)
        assert data["run_id"] == "r1"
        assert data["version"] == RUN_ORCHESTRATOR_VERSION
        assert data["state"] == "COMPLETED"
        assert "config" in data
        assert "plan" in data
        assert "steps" in data and len(data["steps"]) == 1
        assert "artifacts" in data and len(data["artifacts"]) == 1
        assert "data_quality" in data
        assert "safety_flags" in data
        assert data["safety_flags"]["is_safe"] is True
        assert set(data["reason_codes"]) == {OK, RESEARCH_ONLY, NOT_TRADING_ADVICE}

    def test_dict_includes_controlled_universe_data_quality_fields(
        self, fixed_generated_at: datetime
    ) -> None:
        data_quality = ResearchRunDataQuality(
            total_steps=3,
            successful_steps=2,
            failed_steps=0,
            blocked_steps=1,
            skipped_steps=0,
            controlled_universe_steps=1,
            controlled_universe_blocked=1,
            controlled_universe_universe_count=2,
            controlled_universe_watchlist_count=1,
            controlled_universe_blocked_count=1,
            sections_present=("RUN_ID", "STEPS", "DATA_QUALITY", "SAFETY_FLAGS"),
            sections_expected=("RUN_ID", "STEPS", "DATA_QUALITY", "SAFETY_FLAGS"),
            notes=("Run executed 3 step(s): 2 success, 0 failed, 1 blocked, 0 skipped.",),
        )
        result = ResearchRunResult(
            run_id="r-cu",
            config=ResearchRunConfig(generated_at=fixed_generated_at),
            plan=ResearchRunPlan(run_id="r-cu", steps=()),
            steps=(),
            artifacts=(),
            data_quality=data_quality,
            safety_flags=ResearchRunSafetyFlags(),
            reason_codes=(RESEARCH_ONLY,),
            generated_at=fixed_generated_at,
            state=ResearchRunState.COMPLETED,
            metadata={},
            notes=(),
        )
        data = research_run_result_to_dict(result)["data_quality"]
        assert data["controlled_universe_steps"] == 1
        assert data["controlled_universe_blocked"] == 1
        assert data["controlled_universe_universe_count"] == 2
        assert data["controlled_universe_watchlist_count"] == 1
        assert data["controlled_universe_blocked_count"] == 1
        # Existing fields remain present.
        assert data["total_steps"] == 3
        assert data["blocked_steps"] == 1

    def test_dict_defaults_controlled_universe_data_quality_fields_to_zero(
        self, fixed_generated_at: datetime
    ) -> None:
        result = ResearchRunResult(
            run_id="r-default",
            config=ResearchRunConfig(generated_at=fixed_generated_at),
            plan=ResearchRunPlan(run_id="r-default", steps=()),
            steps=(),
            artifacts=(),
            data_quality=ResearchRunDataQuality(),
            safety_flags=ResearchRunSafetyFlags(),
            reason_codes=(RESEARCH_ONLY,),
            generated_at=fixed_generated_at,
            state=ResearchRunState.COMPLETED,
            metadata={},
            notes=(),
        )
        data = research_run_result_to_dict(result)["data_quality"]
        assert data["controlled_universe_steps"] == 0
        assert data["controlled_universe_blocked"] == 0
        assert data["controlled_universe_universe_count"] == 0
        assert data["controlled_universe_watchlist_count"] == 0
        assert data["controlled_universe_blocked_count"] == 0

    def test_dict_serializes_enums_and_datetimes(self, sample_result: ResearchRunResult) -> None:
        data = research_run_result_to_dict(sample_result)
        assert data["state"] == ResearchRunState.COMPLETED.value
        assert data["generated_at"] == "2024-01-01T12:00:00+00:00"
        assert data["steps"][0]["kind"] == ResearchRunStepKind.BACKTEST.value


# ---------------------------------------------------------------------------
# JSON text
# ---------------------------------------------------------------------------


class TestJsonText:
    def test_json_is_parseable(self, sample_result: ResearchRunResult) -> None:
        text = research_run_result_to_json_text(sample_result)
        parsed = json.loads(text)
        assert parsed["run_id"] == "r1"
        assert parsed["state"] == "COMPLETED"

    def test_json_is_deterministic(self, sample_result: ResearchRunResult) -> None:
        text1 = research_run_result_to_json_text(sample_result)
        text2 = research_run_result_to_json_text(sample_result)
        assert text1 == text2

    def test_json_sorts_keys(self, sample_result: ResearchRunResult) -> None:
        text = research_run_result_to_json_text(sample_result)
        lines = text.splitlines()
        assert lines[0] == "{"
        # With sort_keys=True, keys appear in sorted order.
        assert '"artifacts"' in text
        assert '"data_quality"' in text


# ---------------------------------------------------------------------------
# CSV text
# ---------------------------------------------------------------------------


class TestCsvText:
    def test_csv_header(self, sample_result: ResearchRunResult) -> None:
        text = research_run_result_to_csv_text(sample_result)
        lines = text.strip().split("\n")
        assert lines[0] == "run_id,generated_at,step_index,step_id,step_kind,step_state,reason_codes,artifact_count,error_message"

    def test_csv_step_rows(self, sample_result: ResearchRunResult) -> None:
        text = research_run_result_to_csv_text(sample_result)
        reader = csv.DictReader(text.splitlines())
        rows = list(reader)
        assert len(rows) == 1
        row = rows[0]
        assert row["run_id"] == "r1"
        assert row["step_id"] == "s1"
        assert row["step_kind"] == "backtest"
        assert row["step_state"] == "SUCCESS"
        assert row["reason_codes"] == "OK"
        assert row["artifact_count"] == "1"

    def test_csv_is_deterministic(self, sample_result: ResearchRunResult) -> None:
        assert research_run_result_to_csv_text(sample_result) == research_run_result_to_csv_text(sample_result)


# ---------------------------------------------------------------------------
# Markdown text
# ---------------------------------------------------------------------------


class TestMarkdownText:
    def test_markdown_starts_with_h1(self, sample_result: ResearchRunResult) -> None:
        text = research_run_result_to_markdown_text(sample_result)
        lines = [line for line in text.splitlines() if line.strip()]
        assert lines[0] == "# Research Run Summary"

    def test_markdown_includes_safety_notice(self, sample_result: ResearchRunResult) -> None:
        text = research_run_result_to_markdown_text(sample_result)
        lines = text.splitlines()
        assert any(line.startswith("> ") and "human-audit" in line and "research-only" in line for line in lines)

    def test_markdown_contains_required_sections(self, sample_result: ResearchRunResult) -> None:
        text = research_run_result_to_markdown_text(sample_result)
        assert "## Run Summary" in text
        assert "## Step Results" in text
        assert "## Artifacts" in text
        assert "## Data Quality" in text
        assert "## Safety Flags" in text

    def test_markdown_includes_controlled_universe_data_quality_fields(self) -> None:
        data_quality = ResearchRunDataQuality(
            controlled_universe_steps=1,
            controlled_universe_blocked=1,
            controlled_universe_universe_count=2,
            controlled_universe_watchlist_count=3,
            controlled_universe_blocked_count=4,
        )
        result = _make_result_for_step(
            ResearchRunStep(kind=ResearchRunStepKind.CONTROLLED_UNIVERSE, step_id="cu1", inputs={}),
            generated_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            run_id="r-cu",
        )
        result = ResearchRunResult(
            run_id=result.run_id,
            config=result.config,
            plan=result.plan,
            steps=result.steps,
            artifacts=result.artifacts,
            data_quality=data_quality,
            safety_flags=result.safety_flags,
            reason_codes=result.reason_codes,
            generated_at=result.generated_at,
            state=result.state,
            metadata=result.metadata,
            notes=result.notes,
        )
        text = research_run_result_to_markdown_text(result)
        assert "controlled_universe_steps" in text
        assert "controlled_universe_blocked" in text
        assert "controlled_universe_universe_count" in text
        assert "controlled_universe_watchlist_count" in text
        assert "controlled_universe_blocked_count" in text

    def test_markdown_no_action_commands(self, sample_result: ResearchRunResult) -> None:
        text = research_run_result_to_markdown_text(sample_result).lower()
        # The safety notice itself may mention disallowed terms to disclaim them.
        # We ensure there are no actionable instruction headers or trading commands.
        assert "buy" not in text
        assert "sell" not in text
        assert "# place order" not in text
        assert "# execute trade" not in text


# ---------------------------------------------------------------------------
# Atomic writes
# ---------------------------------------------------------------------------


class TestAtomicWrites:
    def test_write_research_run_result_creates_all_files(
        self, sample_result: ResearchRunResult, tmp_path: Path
    ) -> None:
        json_path = tmp_path / "run_summary.json"
        csv_path = tmp_path / "run_steps.csv"
        md_path = tmp_path / "run_summary.md"
        write_research_run_result(
            sample_result,
            json_path=json_path,
            csv_path=csv_path,
            md_path=md_path,
        )
        assert json_path.exists()
        assert csv_path.exists()
        assert md_path.exists()
        assert json.loads(json_path.read_text(encoding="utf-8"))["run_id"] == "r1"
        assert md_path.read_text(encoding="utf-8").startswith("# Research Run Summary")

    def test_atomic_write_creates_parent_directories(
        self, sample_result: ResearchRunResult, tmp_path: Path
    ) -> None:
        target = tmp_path / "nested" / "deep" / "run_summary.json"
        atomic_write_json_research_run_result(sample_result, target)
        assert target.exists()

    def test_csv_atomic_write(self, sample_result: ResearchRunResult, tmp_path: Path) -> None:
        target = tmp_path / "steps.csv"
        atomic_write_csv_research_run_result(sample_result, target)
        assert target.exists()
        assert "step_id" in target.read_text(encoding="utf-8")

    def test_markdown_atomic_write(self, sample_result: ResearchRunResult, tmp_path: Path) -> None:
        target = tmp_path / "summary.md"
        atomic_write_markdown_research_run_result(sample_result, target)
        assert target.exists()


# ---------------------------------------------------------------------------
# Nested dataclass serialization (defect fix)
# ---------------------------------------------------------------------------


class TestNestedDataclassSerialization:
    def test_json_serializes_backtest_step_inputs(
        self,
        backtest_dataclass_step: ResearchRunStep,
        fixed_generated_at: datetime,
    ) -> None:
        result = _make_result_for_step(backtest_dataclass_step, fixed_generated_at, "r-dc")
        text = research_run_result_to_json_text(result)
        parsed = json.loads(text)
        step_inputs = parsed["plan"]["steps"][0]["inputs"]
        assert step_inputs["config"]["allocation_mode"] == "EQUAL_WEIGHT"
        assert len(step_inputs["inputs"]) == 1
        assert step_inputs["inputs"][0]["pair"] == "BTC/USDT"
        assert step_inputs["inputs"][0]["decision"]["state"] == "INCLUDED"

    def test_atomic_write_backtest_step_inputs(
        self,
        backtest_dataclass_step: ResearchRunStep,
        fixed_generated_at: datetime,
        tmp_path: Path,
    ) -> None:
        result = _make_result_for_step(backtest_dataclass_step, fixed_generated_at, "r-write")
        target = tmp_path / "run_summary.json"
        atomic_write_json_research_run_result(result, target)
        assert target.exists()
        parsed = json.loads(target.read_text(encoding="utf-8"))
        assert parsed["plan"]["steps"][0]["kind"] == "backtest"

    def test_no_file_reference_traversal(
        self,
        backtest_dataclass_step: ResearchRunStep,
        fixed_generated_at: datetime,
        tmp_path: Path,
    ) -> None:
        # The writer must treat the path-like string in inputs as opaque.
        result = _make_result_for_step(backtest_dataclass_step, fixed_generated_at, "r-opaque")
        write_research_run_result(
            result, json_path=tmp_path / "out.json", csv_path=None, md_path=None
        )


# ---------------------------------------------------------------------------
# Blocked / failed serialization
# ---------------------------------------------------------------------------


class TestBlockedAndFailedSerialization:
    def test_blocked_run(self, fixed_generated_at: datetime) -> None:
        plan = ResearchRunPlan(run_id="blocked", steps=())
        config = ResearchRunConfig(generated_at=fixed_generated_at)
        result = ResearchRunResult(
            run_id="blocked",
            config=config,
            plan=plan,
            steps=(),
            artifacts=(),
            data_quality=ResearchRunDataQuality(),
            safety_flags=ResearchRunSafetyFlags(has_unsafe_content=True),
            reason_codes=(RUN_BLOCKED, UNSAFE_RUN_CONTENT),
            generated_at=fixed_generated_at,
            state=ResearchRunState.BLOCKED,
            metadata={},
            notes=(),
        )
        data = research_run_result_to_dict(result)
        assert data["state"] == "BLOCKED"
        assert data["safety_flags"]["has_unsafe_content"] is True
        assert data["safety_flags"]["is_safe"] is False

    def test_failed_step(self, sample_result: ResearchRunResult) -> None:
        failed_step = ResearchRunStepResult(
            step_index=0,
            step_id="s1",
            kind=ResearchRunStepKind.BACKTEST,
            state=ResearchRunStepState.FAILED,
            reason_codes=(STEP_FAILED,),
            data={},
            output_paths=(),
            notes=("engine error",),
            error_message="backtest engine failed",
        )
        result = sample_result
        # Dataclasses are frozen; build a new result with the failed step.
        result = ResearchRunResult(
            run_id=result.run_id,
            config=result.config,
            plan=result.plan,
            steps=(failed_step,),
            artifacts=(),
            data_quality=ResearchRunDataQuality(
                total_steps=1,
                successful_steps=0,
                failed_steps=1,
                blocked_steps=0,
                skipped_steps=0,
                notes=("Run executed 1 step(s): 0 success, 1 failed, 0 blocked, 0 skipped.",),
            ),
            safety_flags=ResearchRunSafetyFlags(has_failed_step=True),
            reason_codes=(RESEARCH_ONLY, NOT_TRADING_ADVICE, STEP_FAILED),
            generated_at=result.generated_at,
            state=ResearchRunState.FAILED,
            metadata=result.metadata,
            notes=result.notes,
        )
        text = research_run_result_to_csv_text(result)
        rows = list(csv.DictReader(text.splitlines()))
        assert rows[0]["step_state"] == "FAILED"
        assert rows[0]["error_message"] == "backtest engine failed"


# ---------------------------------------------------------------------------
# No mutation
# ---------------------------------------------------------------------------


class TestNoMutation:
    def test_no_mutation_of_result(self, sample_result: ResearchRunResult) -> None:
        before = research_run_result_to_dict(sample_result)
        research_run_result_to_json_text(sample_result)
        research_run_result_to_csv_text(sample_result)
        research_run_result_to_markdown_text(sample_result)
        after = research_run_result_to_dict(sample_result)
        assert before == after

    def test_no_file_reference_traversal(
        self, sample_result: ResearchRunResult, tmp_path: Path
    ) -> None:
        # Artifact path does not need to exist; writer must not open it.
        nonexistent_path = tmp_path / "does_not_exist" / "report.json"
        artifact = ResearchRunArtifact(
            step_index=0,
            step_id="s1",
            kind="json_report",
            path=str(nonexistent_path),
            metadata={"path": str(nonexistent_path)},
        )
        result = ResearchRunResult(
            run_id=sample_result.run_id,
            config=sample_result.config,
            plan=sample_result.plan,
            steps=sample_result.steps,
            artifacts=(artifact,),
            data_quality=sample_result.data_quality,
            safety_flags=sample_result.safety_flags,
            reason_codes=sample_result.reason_codes,
            generated_at=sample_result.generated_at,
            state=sample_result.state,
            metadata=sample_result.metadata,
            notes=sample_result.notes,
        )
        # Writer serializes the path as an opaque string.
        text = research_run_result_to_markdown_text(result)
        assert str(nonexistent_path) in text
        # No attempt to read the nonexistent file means this completes without error.
        write_research_run_result(
            result, json_path=tmp_path / "out.json", csv_path=None, md_path=None
        )
