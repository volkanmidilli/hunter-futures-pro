"""Integration tests for hunter.final_audit_pack.

MVP-32 Step 3 — End-to-end final audit pack export flow.

These tests exercise the public API (engine + writer) with in-memory inputs
and tmp_path-only file I/O. They do not read external files, access the
network, or interact with exchanges.
"""

from __future__ import annotations

import csv
import json
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
from hunter.experiment_ledger import (
    ExperimentLedgerInput,
    build_experiment_ledger_report,
)
from hunter.final_audit_pack import (
    BACKTEST_SECTION_KIND,
    DUPLICATE_SECTION_ID,
    EXPERIMENT_LEDGER_SECTION_KIND,
    FINAL_AUDIT_PACK_VERSION,
    MISSING_REQUIRED_SECTIONS,
    REPORTING_CLI_SECTION_KIND,
    RUN_ORCHESTRATOR_SECTION_KIND,
    UNSAFE_CONTENT,
    FinalAuditPackConfig,
    FinalAuditPackInput,
    FinalAuditPackReport,
    FinalAuditPackState,
    atomic_write_csv_final_audit_pack_report,
    atomic_write_json_final_audit_pack_report,
    atomic_write_markdown_final_audit_pack_report,
    build_final_audit_pack_report,
    final_audit_pack_report_to_csv_text,
    final_audit_pack_report_to_dict,
    final_audit_pack_report_to_json_text,
    final_audit_pack_report_to_markdown_text,
    write_final_audit_pack_report,
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


@pytest.fixture
def fixed_generated_at() -> datetime:
    return datetime(2024, 1, 1, tzinfo=timezone.utc)


def _ts(day: int = 1) -> datetime:
    return datetime(2024, 1, day, tzinfo=timezone.utc)


def _make_backtest_input(pair: str, closes: list[float]) -> BacktestInput:
    decision = BacktestCandidateDecision(
        pair=pair,
        state="INCLUDED",
        classification="CORE_RESEARCH_ALLOCATION",
        final_weight_pct=0.0,
    )
    bars = tuple(
        BacktestPriceBar(pair=pair, timestamp=_ts(i + 1), close=close)
        for i, close in enumerate(closes)
    )
    return BacktestInput(pair=pair, decision=decision, price_bars=bars)


def _make_backtest_report(
    report_id: str = "bt-1",
    generated_at: datetime | None = None,
) -> Any:
    inputs = [_make_backtest_input("A", [100.0, 110.0, 121.0])]
    cfg = BacktestRunConfig(allocation_mode=BacktestAllocationMode.EQUAL_WEIGHT)
    return build_backtest_report(inputs, cfg, report_id=report_id, generated_at=generated_at)


def _make_run_result(
    run_id: str = "run-1",
    generated_at: datetime | None = None,
) -> Any:
    backtest_input = _make_backtest_input("A", [100.0, 110.0])
    backtest_config = BacktestRunConfig(allocation_mode=BacktestAllocationMode.EQUAL_WEIGHT)
    step_inputs: dict[str, Any] = {"inputs": (backtest_input,), "config": backtest_config}
    step = ResearchRunStep(
        kind=ResearchRunStepKind.BACKTEST,
        step_id="b1",
        inputs=step_inputs,
    )
    plan = ResearchRunPlan(run_id=run_id, steps=(step,))
    config = ResearchRunConfig(generated_at=generated_at or _ts(1), write_artifacts=False)
    return build_research_run_result(plan, config)


def _make_experiment_ledger_report(generated_at: datetime | None = None) -> Any:
    report = _make_backtest_report(report_id="bt-1")
    inp = ExperimentLedgerInput(
        backtest_reports=(report,),
        generated_at=generated_at or _ts(1),
    )
    return build_experiment_ledger_report(inp)


def _make_cli_command_result(command: str = "version") -> CLICommandResult:
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


# ---------------------------------------------------------------------------
# End-to-end successful pack
# ---------------------------------------------------------------------------


class TestEndToEndSuccess:
    def test_complete_pack_with_all_required_inputs_and_artifacts(
        self, fixed_generated_at: datetime
    ) -> None:
        inp = FinalAuditPackInput(
            backtest_reports=(_make_backtest_report(),),
            run_results=(_make_run_result(),),
            experiment_ledger_reports=(_make_experiment_ledger_report(),),
            artifact_references=("data/backtest/bt-1.json", "data/run/run-1.json"),
            generated_at=fixed_generated_at,
        )
        config = FinalAuditPackConfig(generated_at=fixed_generated_at)
        report = build_final_audit_pack_report(inp, config)

        assert report.version == FINAL_AUDIT_PACK_VERSION
        assert report.generated_at == fixed_generated_at
        assert len(report.sections) == 3
        assert len(report.artifacts) == 2
        assert report.completeness.sections_expected == 6
        assert report.completeness.required_sections_present == 3
        assert report.completeness.required_sections_missing == 0
        assert report.completeness.artifact_reference_count == 2
        assert report.safety_flags.has_missing_required_sections is False

        kinds = [s.section_kind for s in report.sections]
        assert kinds == sorted(kinds)
        assert BACKTEST_SECTION_KIND in kinds
        assert RUN_ORCHESTRATOR_SECTION_KIND in kinds
        assert EXPERIMENT_LEDGER_SECTION_KIND in kinds

    def test_dict_json_csv_markdown_round_trip(self, fixed_generated_at: datetime) -> None:
        inp = FinalAuditPackInput(
            backtest_reports=(_make_backtest_report(),),
            run_results=(_make_run_result(),),
            experiment_ledger_reports=(_make_experiment_ledger_report(),),
            artifact_references=("ref-1",),
            generated_at=fixed_generated_at,
        )
        config = FinalAuditPackConfig(generated_at=fixed_generated_at)
        report = build_final_audit_pack_report(inp, config)

        data = final_audit_pack_report_to_dict(report)
        assert data["version"] == FINAL_AUDIT_PACK_VERSION
        assert len(data["sections"]) == 3
        assert len(data["artifacts"]) == 1

        json_text = final_audit_pack_report_to_json_text(report)
        parsed = json.loads(json_text)
        assert parsed["report_id"] == report.report_id

        csv_text = final_audit_pack_report_to_csv_text(report)
        rows = list(csv.DictReader(csv_text.splitlines()))
        assert len(rows) == 3
        assert {row["section_kind"] for row in rows} == {
            BACKTEST_SECTION_KIND,
            RUN_ORCHESTRATOR_SECTION_KIND,
            EXPERIMENT_LEDGER_SECTION_KIND,
        }

        md_text = final_audit_pack_report_to_markdown_text(report)
        assert md_text.startswith("# Final Audit Pack Report")
        assert "## Sections" in md_text
        assert "## Artifacts" in md_text


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------


class TestNormalization:
    def test_backtest_report_maps_to_backtest_section(
        self, fixed_generated_at: datetime
    ) -> None:
        backtest_report = _make_backtest_report(report_id="backtest-1")
        inp = FinalAuditPackInput(
            backtest_reports=(backtest_report,),
            generated_at=fixed_generated_at,
        )
        report = build_final_audit_pack_report(inp)
        section = report.sections[0]
        assert section.section_kind == BACKTEST_SECTION_KIND
        assert section.section_id == "backtest-1"
        assert section.report_id == "backtest-1"
        assert section.run_id == ""
        assert section.state is FinalAuditPackState.INCLUDED

    def test_research_run_result_maps_to_run_orchestrator_section(
        self, fixed_generated_at: datetime
    ) -> None:
        run_result = _make_run_result(run_id="research-run-1")
        inp = FinalAuditPackInput(
            run_results=(run_result,),
            generated_at=fixed_generated_at,
        )
        report = build_final_audit_pack_report(inp)
        section = report.sections[0]
        assert section.section_kind == RUN_ORCHESTRATOR_SECTION_KIND
        assert section.section_id == "research-run-1"
        assert section.run_id == "research-run-1"

    def test_experiment_ledger_report_maps_to_experiment_ledger_section(
        self, fixed_generated_at: datetime
    ) -> None:
        exp_report = _make_experiment_ledger_report(generated_at=fixed_generated_at)
        inp = FinalAuditPackInput(
            experiment_ledger_reports=(exp_report,),
            generated_at=fixed_generated_at,
        )
        report = build_final_audit_pack_report(inp)
        section = report.sections[0]
        assert section.section_kind == EXPERIMENT_LEDGER_SECTION_KIND

    def test_cli_command_result_uses_zero_based_index_fallback(
        self, fixed_generated_at: datetime
    ) -> None:
        result = _make_cli_command_result(command="safety-summary")
        inp = FinalAuditPackInput(
            cli_command_results=(result,),
            generated_at=fixed_generated_at,
        )
        report = build_final_audit_pack_report(inp)
        section = report.sections[0]
        assert section.section_kind == REPORTING_CLI_SECTION_KIND
        assert section.section_id == "reporting_cli:0"
        assert section.name == ""


# ---------------------------------------------------------------------------
# Completeness
# ---------------------------------------------------------------------------


class TestCompleteness:
    def test_sections_expected_is_total_configured_kinds(
        self, fixed_generated_at: datetime
    ) -> None:
        config = FinalAuditPackConfig(
            required_section_kinds=("backtest",),
            optional_section_kinds=("discovery",),
            generated_at=fixed_generated_at,
        )
        inp = FinalAuditPackInput(
            backtest_reports=(_make_backtest_report(),),
            generated_at=fixed_generated_at,
        )
        report = build_final_audit_pack_report(inp, config)
        assert report.completeness.sections_expected == 2

    def test_missing_required_sections_produces_degraded_state(
        self, fixed_generated_at: datetime
    ) -> None:
        inp = FinalAuditPackInput(
            backtest_reports=(_make_backtest_report(),),
            generated_at=fixed_generated_at,
        )
        config = FinalAuditPackConfig(generated_at=fixed_generated_at)
        report = build_final_audit_pack_report(inp, config)
        assert report.completeness.required_sections_present == 1
        assert report.completeness.required_sections_missing == 2
        assert MISSING_REQUIRED_SECTIONS in report.reason_codes
        assert report.safety_flags.has_missing_required_sections is True

    def test_missing_optional_sections_degrade_only(
        self, fixed_generated_at: datetime
    ) -> None:
        inp = FinalAuditPackInput(
            backtest_reports=(_make_backtest_report(),),
            run_results=(_make_run_result(),),
            experiment_ledger_reports=(_make_experiment_ledger_report(),),
            generated_at=fixed_generated_at,
        )
        config = FinalAuditPackConfig(generated_at=fixed_generated_at)
        report = build_final_audit_pack_report(inp, config)
        assert report.completeness.optional_sections_present == 0
        assert report.completeness.required_sections_missing == 0
        assert MISSING_REQUIRED_SECTIONS not in report.reason_codes
        assert report.safety_flags.has_missing_required_sections is False

    def test_block_on_missing_required_config(self, fixed_generated_at: datetime) -> None:
        inp = FinalAuditPackInput(
            backtest_reports=(_make_backtest_report(),),
            generated_at=fixed_generated_at,
        )
        config = FinalAuditPackConfig(
            block_on_missing_required=True,
            generated_at=fixed_generated_at,
        )
        report = build_final_audit_pack_report(inp, config)
        assert MISSING_REQUIRED_SECTIONS in report.reason_codes
        assert report.safety_flags.has_missing_required_sections is True


# ---------------------------------------------------------------------------
# Artifact references
# ---------------------------------------------------------------------------


class TestArtifactReferences:
    def test_opaque_artifact_references_are_included_as_strings(
        self, fixed_generated_at: datetime
    ) -> None:
        refs = ("data/backtest/bt.json", "data/run/run.json")
        inp = FinalAuditPackInput(
            artifact_references=refs,
            generated_at=fixed_generated_at,
        )
        report = build_final_audit_pack_report(inp)
        assert len(report.artifacts) == 2
        assert report.artifacts[0].reference == refs[0]
        assert report.artifacts[1].reference == refs[1]
        assert report.completeness.artifact_reference_count == 2
        assert report.data_quality.artifact_references == 2

    def test_writer_does_not_open_artifact_references(
        self, tmp_path, fixed_generated_at: datetime
    ) -> None:
        inp = FinalAuditPackInput(
            artifact_references=("data/does_not_exist.json",),
            generated_at=fixed_generated_at,
        )
        report = build_final_audit_pack_report(inp)
        path = tmp_path / "pack.json"
        atomic_write_json_final_audit_pack_report(report, path)
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["artifacts"][0]["reference"] == "data/does_not_exist.json"


# ---------------------------------------------------------------------------
# Fail-closed behavior
# ---------------------------------------------------------------------------


class TestFailClosed:
    def test_duplicate_section_id_blocks_later_occurrence(
        self, fixed_generated_at: datetime
    ) -> None:
        report1 = _make_backtest_report(report_id="shared-id")
        report2 = _make_backtest_report(report_id="shared-id")
        inp = FinalAuditPackInput(
            backtest_reports=(report1, report2),
            generated_at=fixed_generated_at,
        )
        report = build_final_audit_pack_report(inp)
        assert report.sections[0].state is FinalAuditPackState.INCLUDED
        assert report.sections[1].state is FinalAuditPackState.BLOCKED
        assert DUPLICATE_SECTION_ID in report.sections[1].reason_codes
        assert report.safety_flags.has_duplicate_section_id is True

    def test_unsafe_content_blocks_section(self, fixed_generated_at: datetime) -> None:
        backtest_report = _make_backtest_report(report_id="binance_api_key")
        inp = FinalAuditPackInput(
            backtest_reports=(backtest_report,),
            generated_at=fixed_generated_at,
        )
        report = build_final_audit_pack_report(inp)
        section = report.sections[0]
        assert section.state is FinalAuditPackState.BLOCKED
        assert UNSAFE_CONTENT in section.reason_codes
        assert report.safety_flags.has_unsafe_content is True

    def test_unsafe_input_tags_block_report(self, fixed_generated_at: datetime) -> None:
        inp = FinalAuditPackInput(
            backtest_reports=(_make_backtest_report(),),
            tags=("place_order_now",),
            generated_at=fixed_generated_at,
        )
        report = build_final_audit_pack_report(inp)
        assert report.sections == ()
        assert UNSAFE_CONTENT in report.reason_codes
        assert report.safety_flags.has_unsafe_content is True


# ---------------------------------------------------------------------------
# Writer end-to-end
# ---------------------------------------------------------------------------


class TestWriterEndToEnd:
    def test_write_final_audit_pack_report_creates_all_artifacts(
        self, tmp_path, fixed_generated_at: datetime
    ) -> None:
        inp = FinalAuditPackInput(
            backtest_reports=(_make_backtest_report(),),
            run_results=(_make_run_result(),),
            experiment_ledger_reports=(_make_experiment_ledger_report(),),
            artifact_references=("ref-1", "ref-2"),
            generated_at=fixed_generated_at,
        )
        config = FinalAuditPackConfig(generated_at=fixed_generated_at)
        report = build_final_audit_pack_report(inp, config)

        json_path = tmp_path / "pack.json"
        csv_path = tmp_path / "pack.csv"
        md_path = tmp_path / "pack.md"
        write_final_audit_pack_report(
            report,
            json_path=json_path,
            csv_path=csv_path,
            md_path=md_path,
        )

        assert json_path.exists()
        assert csv_path.exists()
        assert md_path.exists()

        data = json.loads(json_path.read_text())
        assert data["report_id"] == report.report_id
        assert len(data["sections"]) == 3
        assert len(data["artifacts"]) == 2

        csv_text = csv_path.read_text()
        assert "backtest" in csv_text
        assert "run_orchestrator" in csv_text
        assert "experiment_ledger" in csv_text

        md_text = md_path.read_text()
        assert md_text.startswith("# Final Audit Pack Report")
        assert "> " in md_text
        assert "not a certification of trading readiness" in md_text.lower()
        assert "## Summary" in md_text
        assert "## Completeness Summary" in md_text
        assert "## Sections" in md_text
        assert "## Artifacts" in md_text
        assert "## Data Quality" in md_text
        assert "## Safety Flags" in md_text


# ---------------------------------------------------------------------------
# Determinism and no mutation
# ---------------------------------------------------------------------------


class TestDeterminismAndNoMutation:
    def test_same_inputs_produce_identical_outputs(
        self, fixed_generated_at: datetime
    ) -> None:
        inp = FinalAuditPackInput(
            backtest_reports=(_make_backtest_report(),),
            run_results=(_make_run_result(),),
            artifact_references=("ref-1",),
            generated_at=fixed_generated_at,
        )
        config = FinalAuditPackConfig(generated_at=fixed_generated_at)
        report1 = build_final_audit_pack_report(inp, config)
        report2 = build_final_audit_pack_report(inp, config)

        assert report1 == report2
        assert report1.report_id == report2.report_id
        assert (
            final_audit_pack_report_to_json_text(report1)
            == final_audit_pack_report_to_json_text(report2)
        )
        assert (
            final_audit_pack_report_to_csv_text(report1)
            == final_audit_pack_report_to_csv_text(report2)
        )
        assert (
            final_audit_pack_report_to_markdown_text(report1)
            == final_audit_pack_report_to_markdown_text(report2)
        )

    def test_inputs_are_not_mutated(self, fixed_generated_at: datetime) -> None:
        backtest = _make_backtest_report()
        run = _make_run_result()
        backtests = [backtest]
        runs = [run]
        inp = FinalAuditPackInput(
            backtest_reports=backtests,
            run_results=runs,
            generated_at=fixed_generated_at,
        )
        before_backtest = list(inp.backtest_reports)
        before_run = list(inp.run_results)
        build_final_audit_pack_report(inp)
        assert list(inp.backtest_reports) == before_backtest
        assert list(inp.run_results) == before_run
        assert isinstance(inp.backtest_reports, tuple)
        assert isinstance(inp.run_results, tuple)


# ---------------------------------------------------------------------------
# Public exports and safety boundaries
# ---------------------------------------------------------------------------


class TestPublicExports:
    def test_engine_and_writer_exports_are_callable(self) -> None:
        assert callable(build_final_audit_pack_report)
        assert callable(final_audit_pack_report_to_dict)
        assert callable(final_audit_pack_report_to_json_text)
        assert callable(final_audit_pack_report_to_csv_text)
        assert callable(final_audit_pack_report_to_markdown_text)
        assert callable(atomic_write_json_final_audit_pack_report)
        assert callable(atomic_write_csv_final_audit_pack_report)
        assert callable(atomic_write_markdown_final_audit_pack_report)
        assert callable(write_final_audit_pack_report)


class TestSafetyBoundaries:
    def test_markdown_contains_research_only_safety_notice(
        self, fixed_generated_at: datetime
    ) -> None:
        inp = FinalAuditPackInput(
            backtest_reports=(_make_backtest_report(),),
            generated_at=fixed_generated_at,
        )
        report = build_final_audit_pack_report(inp)
        text = final_audit_pack_report_to_markdown_text(report)
        notice_lines = [line for line in text.split("\n") if line.startswith("> ")]
        notice = " ".join(notice_lines).lower()
        assert "human-audit" in notice or "research-only" in notice
        assert "not a trading signal" in notice
        assert "not a certification of trading readiness" in notice

    def test_markdown_body_has_no_actionable_trading_language(
        self, fixed_generated_at: datetime
    ) -> None:
        inp = FinalAuditPackInput(
            backtest_reports=(_make_backtest_report(),),
            run_results=(_make_run_result(),),
            generated_at=fixed_generated_at,
        )
        report = build_final_audit_pack_report(inp)
        text = final_audit_pack_report_to_markdown_text(report)
        # Skip the safety notice; it legitimately mentions trading terms as disclaimers.
        body_lines = [line for line in text.split("\n") if not line.startswith("> ")]
        body = "\n".join(body_lines).lower()
        for bad in (
            "buy",
            "sell",
            "place order",
            "execute trade",
            "rebalance now",
            "go live",
            "deploy capital",
        ):
            assert bad not in body, f"found actionable term: {bad}"
