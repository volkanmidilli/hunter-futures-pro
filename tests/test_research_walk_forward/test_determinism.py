"""Determinism tests for the walk-forward harness (MVP-66 Stage 9)."""

from __future__ import annotations

from pathlib import Path

import pytest

from hunter.research_walk_forward.engine import run_walk_forward_experiment
from hunter.research_walk_forward.writer import (
    WalkForwardWriter,
    write_all_walk_forward_artifacts,
)
from hunter.research_walk_forward.planner import build_rolling_plan
from tests.test_research_walk_forward.test_runner import (
    _fake_run_backtest_success,
    _make_common,
)


class TestDeterminism:
    def test_same_inputs_same_report_fingerprint(self, tmp_path: Path) -> None:
        common = _make_common(tmp_path)
        plan = build_rolling_plan(
            common,
            selection_start="20240101",
            selection_end="20240201",
            evaluation_start="20240301",
            evaluation_end="20240401",
            step_days=31,
            count=2,
        )
        report1 = run_walk_forward_experiment(
            plan=plan,
            candidate_pairlist=("BTC/USDT", "ETH/USDT"),
            baseline_pairlist=("BTC/USDT",),
            candidate_universe_fingerprint="fp-c",
            baseline_universe_fingerprint="fp-b",
            run_backtest_fn=_fake_run_backtest_success,
        )
        report2 = run_walk_forward_experiment(
            plan=plan,
            candidate_pairlist=("BTC/USDT", "ETH/USDT"),
            baseline_pairlist=("BTC/USDT",),
            candidate_universe_fingerprint="fp-c",
            baseline_universe_fingerprint="fp-b",
            run_backtest_fn=_fake_run_backtest_success,
        )
        assert report1.fingerprint == report2.fingerprint
        assert report1.plan.fingerprint == report2.plan.fingerprint

    def test_same_inputs_same_artifacts(self, tmp_path: Path) -> None:
        common = _make_common(tmp_path)
        plan = build_rolling_plan(
            common,
            selection_start="20240101",
            selection_end="20240201",
            evaluation_start="20240301",
            evaluation_end="20240401",
            step_days=31,
            count=1,
        )
        report1 = run_walk_forward_experiment(
            plan=plan,
            candidate_pairlist=("BTC/USDT",),
            baseline_pairlist=("BTC/USDT",),
            candidate_universe_fingerprint="fp-c",
            baseline_universe_fingerprint="fp-b",
            run_backtest_fn=_fake_run_backtest_success,
        )
        report2 = run_walk_forward_experiment(
            plan=plan,
            candidate_pairlist=("BTC/USDT",),
            baseline_pairlist=("BTC/USDT",),
            candidate_universe_fingerprint="fp-c",
            baseline_universe_fingerprint="fp-b",
            run_backtest_fn=_fake_run_backtest_success,
        )
        out1 = tmp_path / "out1"
        out2 = tmp_path / "out2"
        paths1 = write_all_walk_forward_artifacts(report1, output_dir=out1)
        paths2 = write_all_walk_forward_artifacts(report2, output_dir=out2)
        for key in ("plan", "window_results", "metric_aggregates", "regime_aggregates"):
            text1 = paths1[key].read_text()
            text2 = paths2[key].read_text()
            assert text1 == text2, f"{key} differs"
        assert report1.fingerprint == report2.fingerprint

    def test_different_windows_different_fingerprint(self, tmp_path: Path) -> None:
        common = _make_common(tmp_path)
        plan1 = build_rolling_plan(
            common,
            selection_start="20240101",
            selection_end="20240201",
            evaluation_start="20240301",
            evaluation_end="20240401",
            step_days=31,
            count=1,
        )
        plan2 = build_rolling_plan(
            common,
            selection_start="20240101",
            selection_end="20240215",
            evaluation_start="20240301",
            evaluation_end="20240401",
            step_days=31,
            count=1,
        )
        report1 = run_walk_forward_experiment(
            plan=plan1,
            candidate_pairlist=("BTC/USDT",),
            baseline_pairlist=("BTC/USDT",),
            candidate_universe_fingerprint="fp-c",
            baseline_universe_fingerprint="fp-b",
            run_backtest_fn=_fake_run_backtest_success,
        )
        report2 = run_walk_forward_experiment(
            plan=plan2,
            candidate_pairlist=("BTC/USDT",),
            baseline_pairlist=("BTC/USDT",),
            candidate_universe_fingerprint="fp-c",
            baseline_universe_fingerprint="fp-b",
            run_backtest_fn=_fake_run_backtest_success,
        )
        assert report1.plan.fingerprint != report2.plan.fingerprint


class TestArtifactDeterminism:
    def test_json_output_sorted(self, tmp_path: Path) -> None:
        from hunter.research_walk_forward.models import (
            ConsistencyState,
            MetricAggregate,
        )
        from decimal import Decimal

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
        from hunter.research_walk_forward.writer import _metric_aggregate_payload

        payload = _metric_aggregate_payload(agg)
        text = str(payload)
        assert "available_count" in text
        assert "candidate_higher_count" in text
