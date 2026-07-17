"""Tests for deterministic fingerprints (MVP-66 Stage 7)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from hunter.research_walk_forward.fingerprint import (
    overall_aggregate_fingerprint,
    plan_fingerprint,
    regime_aggregate_fingerprint,
    regime_overall_fingerprint,
    report_fingerprint,
    window_result_fingerprint,
    manifest_fingerprint,
)
from hunter.research_walk_forward.models import (
    ConsistencyState,
    MarketRegimeLabel,
    MetricAggregate,
    MetricDirection,
    RegimeAggregate,
    WalkForwardCommonConfig,
    WalkForwardExperimentPlan,
    WalkForwardExperimentReport,
    WalkForwardManifest,
    WalkForwardMode,
    WalkForwardSafetyFlags,
    WalkForwardWindow,
    WalkForwardWindowResult,
    WindowStatus,
)


def _make_plan(tmp_path: Path) -> WalkForwardExperimentPlan:
    common = WalkForwardCommonConfig(
        strategy_name="TestStrategy",
        strategy_path=tmp_path / "strategy.py",
        data_path=tmp_path / "data",
        timeframe="1h",
        balance=Decimal("1000"),
        stake=Decimal("100"),
        max_open_trades=3,
        fee=Decimal("0.001"),
        executable_path=tmp_path / "freqtrade",
    )
    window = WalkForwardWindow(
        selection_start="20240101",
        selection_end="20240201",
        evaluation_start="20240301",
        evaluation_end="20240401",
    )
    return WalkForwardExperimentPlan(
        mode=WalkForwardMode.ROLLING,
        windows=(window,),
        common=common,
    )


def _make_window_result() -> WalkForwardWindowResult:
    window = WalkForwardWindow(
        selection_start="20240101",
        selection_end="20240201",
        evaluation_start="20240301",
        evaluation_end="20240401",
    )
    return WalkForwardWindowResult(
        window=window,
        window_index=0,
        status=WindowStatus.COMPLETED,
        candidate_metrics={"total_return_pct": Decimal("10")},
        baseline_metrics={"total_return_pct": Decimal("5")},
        metric_deltas={"total_return_pct": Decimal("5")},
        metric_directions={"total_return_pct": MetricDirection.CANDIDATE_HIGHER},
        comparison_fingerprint="fp-comp",
        candidate_fingerprint="fp-cand",
        baseline_fingerprint="fp-base",
        fingerprint="fp-result",
    )


class TestPlanFingerprint:
    def test_plan_fingerprint_boundary_sensitivity(self, tmp_path: Path) -> None:
        plan1 = _make_plan(tmp_path)
        plan2 = WalkForwardExperimentPlan(
            mode=plan1.mode,
            windows=(
                WalkForwardWindow(
                    selection_start="20240101",
                    selection_end="20240215",
                    evaluation_start="20240301",
                    evaluation_end="20240401",
                ),
            ),
            common=plan1.common,
        )
        assert plan_fingerprint(plan1) != plan_fingerprint(plan2)

    def test_plan_fingerprint_path_independence(self, tmp_path: Path) -> None:
        plan1 = _make_plan(tmp_path)
        other_path = tmp_path / "other"
        other_path.mkdir()
        common2 = WalkForwardCommonConfig(
            strategy_name=plan1.common.strategy_name,
            strategy_path=other_path / "strategy.py",
            data_path=other_path / "data",
            timeframe=plan1.common.timeframe,
            balance=plan1.common.balance,
            stake=plan1.common.stake,
            max_open_trades=plan1.common.max_open_trades,
            fee=plan1.common.fee,
            executable_path=other_path / "freqtrade",
        )
        plan2 = WalkForwardExperimentPlan(
            mode=plan1.mode,
            windows=plan1.windows,
            common=common2,
        )
        assert plan_fingerprint(plan1) == plan_fingerprint(plan2)

    def test_plan_fingerprint_deterministic(self, tmp_path: Path) -> None:
        plan = _make_plan(tmp_path)
        assert plan_fingerprint(plan) == plan_fingerprint(plan)


class TestWindowResultFingerprint:
    def test_window_result_fingerprint_excludes_runtime(self) -> None:
        result1 = _make_window_result()
        result2 = WalkForwardWindowResult(
            window=result1.window,
            window_index=result1.window_index,
            status=result1.status,
            candidate_metrics=result1.candidate_metrics,
            baseline_metrics=result1.baseline_metrics,
            metric_deltas=result1.metric_deltas,
            metric_directions=result1.metric_directions,
            comparison_fingerprint=result1.comparison_fingerprint,
            candidate_fingerprint=result1.candidate_fingerprint,
            baseline_fingerprint=result1.baseline_fingerprint,
            fingerprint="different-runtime-fp",
            reason_codes=result1.reason_codes,
            metadata={"runtime_ms": 123},
        )
        assert window_result_fingerprint(result1) == window_result_fingerprint(result2)

    def test_window_result_fingerprint_metric_sensitivity(self) -> None:
        result1 = _make_window_result()
        result2 = WalkForwardWindowResult(
            window=result1.window,
            window_index=result1.window_index,
            status=result1.status,
            candidate_metrics={"total_return_pct": Decimal("20")},
            baseline_metrics=result1.baseline_metrics,
            metric_deltas={"total_return_pct": Decimal("15")},
            metric_directions=result1.metric_directions,
            comparison_fingerprint=result1.comparison_fingerprint,
            candidate_fingerprint=result1.candidate_fingerprint,
            baseline_fingerprint=result1.baseline_fingerprint,
            fingerprint=result1.fingerprint,
        )
        assert window_result_fingerprint(result1) != window_result_fingerprint(result2)


class TestRegimeFingerprint:
    def test_regime_fingerprint_deterministic(self) -> None:
        agg = RegimeAggregate(
            regime_label=MarketRegimeLabel.BULL,
            window_count=1,
            completed_count=1,
            failed_count=0,
            blocked_count=0,
            timed_out_count=0,
            unsupported_count=0,
            insufficient_count=0,
            metric_aggregates={},
            fingerprint="fp",
        )
        assert regime_aggregate_fingerprint(agg) == regime_aggregate_fingerprint(agg)


class TestReportFingerprint:
    def test_report_fingerprint_deterministic(self, tmp_path: Path) -> None:
        from datetime import datetime, timezone

        plan = _make_plan(tmp_path)
        result = _make_window_result()
        agg = MetricAggregate(
            metric_name="total_return_pct",
            available_count=1,
            unavailable_count=0,
            candidate_higher_count=1,
            baseline_higher_count=0,
            equal_count=0,
            mean=Decimal("5"),
            median=Decimal("5"),
            min=Decimal("5"),
            max=Decimal("5"),
            q1=Decimal("5"),
            q3=Decimal("5"),
            iqr=Decimal("0"),
            positive_delta_share=Decimal("1"),
            negative_delta_share=Decimal("0"),
            zero_delta_share=Decimal("0"),
            consistency_state=ConsistencyState.CONSISTENT_CANDIDATE_HIGHER,
        )
        regime = RegimeAggregate(
            regime_label=MarketRegimeLabel.UNKNOWN,
            window_count=1,
            completed_count=1,
            failed_count=0,
            blocked_count=0,
            timed_out_count=0,
            unsupported_count=0,
            insufficient_count=0,
            metric_aggregates={"total_return_pct": agg},
            fingerprint="fp-regime",
        )
        manifest = WalkForwardManifest(
            version="0.66.0-dev",
            spec_version="SPEC-067",
            walk_forward_version="0.66.0-dev",
            generated_at=datetime.now(timezone.utc),
            plan_fingerprint=plan_fingerprint(plan),
            overall_aggregate_fingerprint=overall_aggregate_fingerprint({"total_return_pct": agg}),
            regime_aggregate_fingerprint=regime_overall_fingerprint((regime,)),
            safety_flags=WalkForwardSafetyFlags(),
            reason_codes=(),
        )
        report = WalkForwardExperimentReport(
            version="0.66.0-dev",
            spec_version="SPEC-067",
            walk_forward_version="0.66.0-dev",
            plan=plan,
            window_results=(result,),
            metric_aggregates={"total_return_pct": agg},
            regime_aggregates=(regime,),
            manifest=manifest,
            safety_flags=WalkForwardSafetyFlags(),
            fingerprint="fp",
        )
        fp1 = report_fingerprint(report)
        fp2 = report_fingerprint(report)
        assert fp1 == fp2
        assert manifest_fingerprint(manifest) == manifest_fingerprint(manifest)
