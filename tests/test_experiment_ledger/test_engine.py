"""Tests for hunter.experiment_ledger.engine.

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
from hunter.experiment_ledger import (
    BASELINE_MISSING,
    BACKTEST_SOURCE_KIND,
    DUPLICATE_ID,
    EXPERIMENT_LEDGER_VERSION,
    INVALID_METRICS,
    METRIC_SNAPSHOT_SOURCE_KIND,
    OK,
    RUN_SOURCE_KIND,
    UNSAFE_CONTENT,
    build_experiment_ledger_report,
    ExperimentComparisonConfig,
    ExperimentLedgerInput,
    ExperimentLedgerReport,
    ExperimentMetricSnapshot,
    ExperimentReasonCode,
    ExperimentRecord,
    ExperimentState,
    has_unsafe_experiment_ledger_content,
)
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
        make_backtest_input("B", [100.0, 90.0, 80.0]),
    ]
    cfg = BacktestRunConfig(allocation_mode=BacktestAllocationMode.EQUAL_WEIGHT)
    return build_backtest_report(inputs, cfg, report_id=report_id, generated_at=generated_at)


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


# ---------------------------------------------------------------------------
# Public exports
# ---------------------------------------------------------------------------


class TestPublicExports:
    def test_build_experiment_ledger_report_exported(self) -> None:
        assert callable(build_experiment_ledger_report)

    def test_has_unsafe_experiment_ledger_content_exported(self) -> None:
        assert callable(has_unsafe_experiment_ledger_content)


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    def test_same_inputs_produce_same_report(self) -> None:
        report1 = make_backtest_report(report_id="bt-1")
        snapshot = ExperimentMetricSnapshot(
            experiment_id="snap-1",
            run_id="snap-1",
            name="Snapshot 1",
            metrics={"total_return_pct": 5.0},
        )
        inp = ExperimentLedgerInput(
            backtest_reports=(report1,),
            metric_snapshots=(snapshot,),
            generated_at=ts(1),
        )
        config = ExperimentComparisonConfig(generated_at=ts(1))
        ledger1 = build_experiment_ledger_report(inp, config)
        ledger2 = build_experiment_ledger_report(inp, config)
        assert ledger1 == ledger2

    def test_report_version_is_constant(self) -> None:
        report = make_backtest_report()
        inp = ExperimentLedgerInput(backtest_reports=(report,), generated_at=ts(1))
        ledger = build_experiment_ledger_report(inp)
        assert ledger.version == EXPERIMENT_LEDGER_VERSION


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------


class TestBacktestReportNormalization:
    def test_experiment_id_run_id_name_from_report_id(self) -> None:
        report = make_backtest_report(report_id="backtest-report-1")
        inp = ExperimentLedgerInput(backtest_reports=(report,), generated_at=ts(1))
        ledger = build_experiment_ledger_report(inp)
        record = ledger.comparison.records[0]
        assert record.source_kind == BACKTEST_SOURCE_KIND
        assert record.experiment_id == "backtest-report-1"
        assert record.run_id == "backtest-report-1"
        assert record.name == "backtest-report-1"

    def test_metrics_extracted_from_portfolio(self) -> None:
        report = make_backtest_report()
        inp = ExperimentLedgerInput(backtest_reports=(report,), generated_at=ts(1))
        ledger = build_experiment_ledger_report(inp)
        record = ledger.comparison.records[0]
        assert "total_return_pct" in record.metrics
        assert "max_drawdown_pct" in record.metrics
        assert "volatility_pct" in record.metrics
        assert "win_rate_pct" in record.metrics
        assert "observation_count" in record.metrics
        assert "missing_data_count" in record.metrics
        assert "blocked_count" in record.metrics
        assert "insufficient_data_count" in record.metrics

    def test_state_is_included_for_valid_backtest(self) -> None:
        report = make_backtest_report()
        inp = ExperimentLedgerInput(backtest_reports=(report,), generated_at=ts(1))
        ledger = build_experiment_ledger_report(inp)
        record = ledger.comparison.records[0]
        assert record.state is ExperimentState.INCLUDED


class TestRunResultNormalization:
    def test_experiment_id_run_id_name_from_run_id(self) -> None:
        result = make_run_result(run_id="research-run-1")
        inp = ExperimentLedgerInput(run_results=(result,), generated_at=ts(1))
        ledger = build_experiment_ledger_report(inp)
        record = ledger.comparison.records[0]
        assert record.source_kind == RUN_SOURCE_KIND
        assert record.experiment_id == "research-run-1"
        assert record.run_id == "research-run-1"
        assert record.name == "research-run-1"

    def test_metrics_extracted_from_data_quality(self) -> None:
        result = make_run_result()
        inp = ExperimentLedgerInput(run_results=(result,), generated_at=ts(1))
        ledger = build_experiment_ledger_report(inp)
        record = ledger.comparison.records[0]
        assert "total_steps" in record.metrics
        assert "successful_steps" in record.metrics
        assert "failed_steps" in record.metrics
        assert "blocked_steps" in record.metrics
        assert "skipped_steps" in record.metrics

    def test_run_result_state_is_included(self) -> None:
        result = make_run_result()
        inp = ExperimentLedgerInput(run_results=(result,), generated_at=ts(1))
        ledger = build_experiment_ledger_report(inp)
        record = ledger.comparison.records[0]
        assert record.state is ExperimentState.INCLUDED


class TestMetricSnapshotNormalization:
    def test_experiment_id_run_id_name_from_snapshot(self) -> None:
        snapshot = ExperimentMetricSnapshot(
            experiment_id="snap-1",
            run_id="snap-run-1",
            name="Snapshot 1",
            metrics={"total_return_pct": 5.0},
        )
        inp = ExperimentLedgerInput(metric_snapshots=(snapshot,), generated_at=ts(1))
        ledger = build_experiment_ledger_report(inp)
        record = ledger.comparison.records[0]
        assert record.source_kind == METRIC_SNAPSHOT_SOURCE_KIND
        assert record.experiment_id == "snap-1"
        assert record.run_id == "snap-run-1"
        assert record.name == "Snapshot 1"

    def test_run_id_defaults_to_experiment_id(self) -> None:
        snapshot = ExperimentMetricSnapshot(
            experiment_id="snap-2",
            run_id="",
            name="Snapshot 2",
            metrics={"total_return_pct": 5.0},
        )
        inp = ExperimentLedgerInput(metric_snapshots=(snapshot,), generated_at=ts(1))
        ledger = build_experiment_ledger_report(inp)
        record = ledger.comparison.records[0]
        assert record.run_id == "snap-2"

    def test_snapshot_metrics_copied(self) -> None:
        snapshot = ExperimentMetricSnapshot(
            experiment_id="snap-3",
            run_id="snap-3",
            name="Snapshot 3",
            metrics={"total_return_pct": 7.5, "observation_count": 42},
        )
        inp = ExperimentLedgerInput(metric_snapshots=(snapshot,), generated_at=ts(1))
        ledger = build_experiment_ledger_report(inp)
        record = ledger.comparison.records[0]
        assert record.metrics["total_return_pct"] == 7.5
        assert record.metrics["observation_count"] == 42


class TestDisplayNameOverride:
    def test_metadata_override_for_backtest(self) -> None:
        report = make_backtest_report(report_id="bt-1")
        inp = ExperimentLedgerInput(
            backtest_reports=(report,),
            metadata={"bt-1": "My Custom Name"},
            generated_at=ts(1),
        )
        ledger = build_experiment_ledger_report(inp)
        record = ledger.comparison.records[0]
        assert record.name == "My Custom Name"

    def test_metadata_override_for_run_result(self) -> None:
        result = make_run_result(run_id="run-1")
        inp = ExperimentLedgerInput(
            run_results=(result,),
            metadata={"run-1": "Custom Run Name"},
            generated_at=ts(1),
        )
        ledger = build_experiment_ledger_report(inp)
        record = ledger.comparison.records[0]
        assert record.name == "Custom Run Name"

    def test_empty_metadata_override_falls_back(self) -> None:
        report = make_backtest_report(report_id="bt-1")
        inp = ExperimentLedgerInput(
            backtest_reports=(report,),
            metadata={"bt-1": ""},
            generated_at=ts(1),
        )
        ledger = build_experiment_ledger_report(inp)
        record = ledger.comparison.records[0]
        assert record.name == "bt-1"


# ---------------------------------------------------------------------------
# Fail-closed behavior
# ---------------------------------------------------------------------------


class TestDuplicateExperimentId:
    def test_duplicate_ids_mark_second_blocked(self) -> None:
        report1 = make_backtest_report(report_id="shared-id")
        report2 = make_backtest_report(report_id="shared-id")
        inp = ExperimentLedgerInput(
            backtest_reports=(report1, report2),
            generated_at=ts(1),
        )
        ledger = build_experiment_ledger_report(inp)
        states = [r.state for r in ledger.comparison.records]
        assert states[0] is ExperimentState.INCLUDED
        assert states[1] is ExperimentState.BLOCKED
        assert DUPLICATE_ID in ledger.comparison.records[1].reason_codes

    def test_first_occurrence_retains_state(self) -> None:
        report1 = make_backtest_report(report_id="shared-id")
        report2 = make_backtest_report(report_id="shared-id")
        inp = ExperimentLedgerInput(
            backtest_reports=(report1, report2),
            generated_at=ts(1),
        )
        ledger = build_experiment_ledger_report(inp)
        assert ledger.comparison.records[0].state is ExperimentState.INCLUDED


class TestInvalidMetrics:
    def test_nan_metric_blocks_record(self) -> None:
        snapshot = ExperimentMetricSnapshot(
            experiment_id="bad",
            run_id="bad",
            name="Bad",
            metrics={"total_return_pct": float("nan")},
        )
        inp = ExperimentLedgerInput(metric_snapshots=(snapshot,), generated_at=ts(1))
        ledger = build_experiment_ledger_report(inp)
        record = ledger.comparison.records[0]
        assert record.state is ExperimentState.BLOCKED
        assert INVALID_METRICS in record.reason_codes

    def test_non_numeric_metric_blocks_record(self) -> None:
        snapshot = ExperimentMetricSnapshot(
            experiment_id="bad",
            run_id="bad",
            name="Bad",
            metrics={"total_return_pct": "high"},
        )
        inp = ExperimentLedgerInput(metric_snapshots=(snapshot,), generated_at=ts(1))
        ledger = build_experiment_ledger_report(inp)
        record = ledger.comparison.records[0]
        assert record.state is ExperimentState.BLOCKED
        assert INVALID_METRICS in record.reason_codes

    def test_missing_required_metric_is_insufficient_data(self) -> None:
        snapshot = ExperimentMetricSnapshot(
            experiment_id="partial",
            run_id="partial",
            name="Partial",
            metrics={},
        )
        inp = ExperimentLedgerInput(metric_snapshots=(snapshot,), generated_at=ts(1))
        ledger = build_experiment_ledger_report(inp)
        record = ledger.comparison.records[0]
        assert record.state is ExperimentState.INSUFFICIENT_DATA

    def test_partial_metric_snapshot_is_included(self) -> None:
        snapshot = ExperimentMetricSnapshot(
            experiment_id="partial",
            run_id="partial",
            name="Partial",
            metrics={"observation_count": 10},
        )
        inp = ExperimentLedgerInput(metric_snapshots=(snapshot,), generated_at=ts(1))
        ledger = build_experiment_ledger_report(inp)
        record = ledger.comparison.records[0]
        assert record.state is ExperimentState.INCLUDED


class TestMissingRequiredFields:
    def test_empty_experiment_id_blocks_record(self) -> None:
        # Empty experiment_id is rejected at the model boundary.
        with pytest.raises(ValueError, match="experiment_id"):
            ExperimentMetricSnapshot(
                experiment_id="",
                run_id="",
                name="Name",
                metrics={"total_return_pct": 1.0},
            )


class TestUnsafeContent:
    def test_unsafe_metadata_blocks_whole_report(self) -> None:
        report = make_backtest_report(report_id="bt-1")
        inp = ExperimentLedgerInput(
            backtest_reports=(report,),
            metadata={"note": "place order now"},
            generated_at=ts(1),
        )
        ledger = build_experiment_ledger_report(inp)
        assert ledger.comparison.records == ()
        assert UNSAFE_CONTENT in ledger.reason_codes

    def test_unsafe_record_id_blocks_record(self) -> None:
        snapshot = ExperimentMetricSnapshot(
            experiment_id="safe",
            run_id="safe",
            name="Safe",
            metrics={"total_return_pct": 1.0},
            metadata={"note": "leverage 10x"},
        )
        inp = ExperimentLedgerInput(metric_snapshots=(snapshot,), generated_at=ts(1))
        ledger = build_experiment_ledger_report(inp)
        record = ledger.comparison.records[0]
        assert record.state is ExperimentState.BLOCKED
        assert UNSAFE_CONTENT in record.reason_codes


# ---------------------------------------------------------------------------
# Baseline behavior
# ---------------------------------------------------------------------------


class TestBaselineBehavior:
    def test_omitted_baseline_no_code(self) -> None:
        report = make_backtest_report(report_id="bt-1")
        inp = ExperimentLedgerInput(backtest_reports=(report,), generated_at=ts(1))
        config = ExperimentComparisonConfig()
        ledger = build_experiment_ledger_report(inp, config)
        assert ledger.comparison.baseline_record is None
        assert BASELINE_MISSING not in ledger.reason_codes

    def test_provided_not_found_baseline_emits_code(self) -> None:
        report = make_backtest_report(report_id="bt-1")
        inp = ExperimentLedgerInput(backtest_reports=(report,), generated_at=ts(1))
        config = ExperimentComparisonConfig(baseline_experiment_id="missing")
        ledger = build_experiment_ledger_report(inp, config)
        assert ledger.comparison.baseline_record is None
        assert BASELINE_MISSING in ledger.reason_codes
        assert ledger.safety_flags.has_missing_baseline is True

    def test_found_baseline_used_for_deltas(self) -> None:
        report1 = make_backtest_report(report_id="base")
        report2 = make_backtest_report(report_id="exp")
        inp = ExperimentLedgerInput(
            backtest_reports=(report1, report2),
            generated_at=ts(1),
        )
        config = ExperimentComparisonConfig(baseline_experiment_id="base")
        ledger = build_experiment_ledger_report(inp, config)
        assert ledger.comparison.baseline_record is not None
        assert ledger.comparison.baseline_record.experiment_id == "base"
        assert "base" in ledger.comparison.deltas
        assert "exp" in ledger.comparison.deltas
        assert BASELINE_MISSING not in ledger.reason_codes

    def test_baseline_included_with_zero_deltas(self) -> None:
        report = make_backtest_report(report_id="base")
        inp = ExperimentLedgerInput(backtest_reports=(report,), generated_at=ts(1))
        config = ExperimentComparisonConfig(baseline_experiment_id="base")
        ledger = build_experiment_ledger_report(inp, config)
        deltas = ledger.comparison.deltas["base"]
        for metric_name in ("total_return_pct", "max_drawdown_pct", "volatility_pct", "win_rate_pct"):
            assert deltas[metric_name] == 0.0


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------


class TestRanking:
    def test_metric_present_before_metric_missing(self) -> None:
        snap_with = ExperimentMetricSnapshot(
            experiment_id="with",
            run_id="with",
            name="With",
            metrics={"total_return_pct": 10.0},
        )
        snap_without = ExperimentMetricSnapshot(
            experiment_id="without",
            run_id="without",
            name="Without",
            metrics={"observation_count": 10},
        )
        inp = ExperimentLedgerInput(
            metric_snapshots=(snap_without, snap_with),
            generated_at=ts(1),
        )
        config = ExperimentComparisonConfig(primary_metric="total_return_pct")
        ledger = build_experiment_ledger_report(inp, config)
        ids = [r.experiment_id for r in ledger.comparison.ranked_records]
        assert ids == ["with", "without"]

    def test_metric_present_sorted_descending(self) -> None:
        snap_low = ExperimentMetricSnapshot(
            experiment_id="low",
            run_id="low",
            name="Low",
            metrics={"total_return_pct": 5.0},
        )
        snap_high = ExperimentMetricSnapshot(
            experiment_id="high",
            run_id="high",
            name="High",
            metrics={"total_return_pct": 15.0},
        )
        inp = ExperimentLedgerInput(
            metric_snapshots=(snap_low, snap_high),
            generated_at=ts(1),
        )
        config = ExperimentComparisonConfig(primary_metric="total_return_pct")
        ledger = build_experiment_ledger_report(inp, config)
        ids = [r.experiment_id for r in ledger.comparison.ranked_records]
        assert ids == ["high", "low"]

    def test_missing_metric_not_treated_as_zero(self) -> None:
        snap_with = ExperimentMetricSnapshot(
            experiment_id="with",
            run_id="with",
            name="With",
            metrics={"total_return_pct": -100.0},
        )
        snap_without = ExperimentMetricSnapshot(
            experiment_id="without",
            run_id="without",
            name="Without",
            metrics={"observation_count": 10},
        )
        inp = ExperimentLedgerInput(
            metric_snapshots=(snap_without, snap_with),
            generated_at=ts(1),
        )
        config = ExperimentComparisonConfig(primary_metric="total_return_pct")
        ledger = build_experiment_ledger_report(inp, config)
        ids = [r.experiment_id for r in ledger.comparison.ranked_records]
        assert ids == ["with", "without"]

    def test_include_blocked_false_omits_blocked(self) -> None:
        snap_safe = ExperimentMetricSnapshot(
            experiment_id="safe",
            run_id="safe",
            name="Safe",
            metrics={"total_return_pct": 1.0},
        )
        snap_bad = ExperimentMetricSnapshot(
            experiment_id="bad",
            run_id="bad",
            name="Bad",
            metrics={"total_return_pct": float("nan")},
        )
        inp = ExperimentLedgerInput(
            metric_snapshots=(snap_safe, snap_bad),
            generated_at=ts(1),
        )
        config = ExperimentComparisonConfig(include_blocked=False)
        ledger = build_experiment_ledger_report(inp, config)
        ids = [r.experiment_id for r in ledger.comparison.ranked_records]
        assert ids == ["safe"]

    def test_include_insufficient_false_omits_insufficient(self) -> None:
        snap_full = ExperimentMetricSnapshot(
            experiment_id="full",
            run_id="full",
            name="Full",
            metrics={"total_return_pct": 1.0},
        )
        snap_partial = ExperimentMetricSnapshot(
            experiment_id="partial",
            run_id="partial",
            name="Partial",
            metrics={},
        )
        inp = ExperimentLedgerInput(
            metric_snapshots=(snap_full, snap_partial),
            generated_at=ts(1),
        )
        config = ExperimentComparisonConfig(include_insufficient=False)
        ledger = build_experiment_ledger_report(inp, config)
        ids = [r.experiment_id for r in ledger.comparison.ranked_records]
        assert ids == ["full"]


# ---------------------------------------------------------------------------
# Data quality and summary
# ---------------------------------------------------------------------------


class TestDataQuality:
    def test_summary_counts_all_inputs(self) -> None:
        report = make_backtest_report(report_id="bt-1")
        snap_bad = ExperimentMetricSnapshot(
            experiment_id="bad",
            run_id="bad",
            name="Bad",
            metrics={"total_return_pct": float("nan")},
        )
        inp = ExperimentLedgerInput(
            backtest_reports=(report,),
            metric_snapshots=(snap_bad,),
            generated_at=ts(1),
        )
        ledger = build_experiment_ledger_report(inp)
        assert ledger.data_quality.total_inputs == 2
        assert ledger.data_quality.normalized_records == 2
        assert ledger.data_quality.blocked_records == 1
        assert ledger.data_quality.included_records == 1

    def test_ranked_omitted_but_counts_preserved(self) -> None:
        snap_bad = ExperimentMetricSnapshot(
            experiment_id="bad",
            run_id="bad",
            name="Bad",
            metrics={"total_return_pct": float("nan")},
        )
        inp = ExperimentLedgerInput(metric_snapshots=(snap_bad,), generated_at=ts(1))
        config = ExperimentComparisonConfig(include_blocked=False)
        ledger = build_experiment_ledger_report(inp, config)
        assert ledger.comparison.ranked_records == ()
        assert ledger.data_quality.blocked_records == 1
        assert ledger.data_quality.total_inputs == 1


# ---------------------------------------------------------------------------
# No mutation of inputs
# ---------------------------------------------------------------------------


class TestNoMutation:
    def test_input_backtest_reports_tuple_unchanged(self) -> None:
        report = make_backtest_report()
        reports = [report]
        inp = ExperimentLedgerInput(backtest_reports=reports, generated_at=ts(1))
        build_experiment_ledger_report(inp)
        assert isinstance(inp.backtest_reports, tuple)
        assert inp.backtest_reports == tuple(reports)

    def test_input_metadata_unchanged(self) -> None:
        inp = ExperimentLedgerInput(
            metadata={"note": "hello"},
            generated_at=ts(1),
        )
        build_experiment_ledger_report(inp)
        assert dict(inp.metadata) == {"note": "hello"}


# ---------------------------------------------------------------------------
# Safety
# ---------------------------------------------------------------------------


class TestSafety:
    def test_report_contains_safety_notice(self) -> None:
        report = make_backtest_report()
        inp = ExperimentLedgerInput(backtest_reports=(report,), generated_at=ts(1))
        ledger = build_experiment_ledger_report(inp)
        assert any("human audit" in note.lower() for note in ledger.notes)
        assert any("not a trading signal" in note.lower() for note in ledger.notes)

    def test_safety_flags_are_safe_by_default(self) -> None:
        report = make_backtest_report()
        inp = ExperimentLedgerInput(backtest_reports=(report,), generated_at=ts(1))
        ledger = build_experiment_ledger_report(inp)
        assert ledger.safety_flags.is_safe is True

    def test_no_trading_terms_in_notes(self) -> None:
        report = make_backtest_report()
        inp = ExperimentLedgerInput(backtest_reports=(report,), generated_at=ts(1))
        ledger = build_experiment_ledger_report(inp)
        for note in ledger.notes:
            assert not has_unsafe_experiment_ledger_content(text=note)
