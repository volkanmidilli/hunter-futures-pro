"""Integration tests for the walk-forward harness (MVP-66 Stage 9)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from hunter.research_walk_forward.engine import run_walk_forward_experiment
from hunter.research_walk_forward.models import (
    MarketRegimeLabel,
    WindowStatus,
)
from hunter.research_walk_forward.planner import build_rolling_plan
from tests.test_research_walk_forward.test_runner import (
    _fake_run_backtest_success,
    _make_common,
)


class TestEndToEnd:
    def test_rolling_two_windows(self, tmp_path: Path) -> None:
        common = _make_common(tmp_path)
        plan = build_rolling_plan(
            common,
            selection_start="20240101",
            selection_end="20240201",
            evaluation_start="20240301",
            evaluation_end="20240401",
            step_days=31,
            count=2,
            regime_labels=[MarketRegimeLabel.BULL, MarketRegimeLabel.BEAR],
        )
        report = run_walk_forward_experiment(
            plan=plan,
            candidate_pairlist=("BTC/USDT", "ETH/USDT"),
            baseline_pairlist=("BTC/USDT",),
            candidate_universe_fingerprint="fp-candidate",
            baseline_universe_fingerprint="fp-baseline",
            run_backtest_fn=_fake_run_backtest_success,
        )
        assert len(report.window_results) == 2
        assert all(w.status == WindowStatus.COMPLETED for w in report.window_results)
        assert report.metric_aggregates["total_return_pct"].available_count == 2
        assert report.metric_aggregates["total_return_pct"].candidate_higher_count == 2
        assert len(report.regime_aggregates) == 2

    def test_insufficient_window_preserved(self, tmp_path: Path) -> None:
        from tests.test_research_walk_forward.test_runner import _fake_run_backtest_insufficient

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
        report = run_walk_forward_experiment(
            plan=plan,
            candidate_pairlist=("BTC/USDT",),
            baseline_pairlist=("BTC/USDT",),
            candidate_universe_fingerprint="fp-c",
            baseline_universe_fingerprint="fp-b",
            run_backtest_fn=_fake_run_backtest_insufficient,
        )
        assert report.window_results[0].status == WindowStatus.INSUFFICIENT

    def test_report_contains_all_required_fields(self, tmp_path: Path) -> None:
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
        report = run_walk_forward_experiment(
            plan=plan,
            candidate_pairlist=("BTC/USDT",),
            baseline_pairlist=("BTC/USDT",),
            candidate_universe_fingerprint="fp-c",
            baseline_universe_fingerprint="fp-b",
            run_backtest_fn=_fake_run_backtest_success,
        )
        assert report.version
        assert report.spec_version
        assert report.plan.fingerprint
        assert report.manifest.plan_fingerprint
        assert report.manifest.overall_aggregate_fingerprint
        assert report.manifest.regime_aggregate_fingerprint


class TestConsistencyStates:
    def test_consistency_state_in_report(self, tmp_path: Path) -> None:
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
        report = run_walk_forward_experiment(
            plan=plan,
            candidate_pairlist=("BTC/USDT",),
            baseline_pairlist=("BTC/USDT",),
            candidate_universe_fingerprint="fp-c",
            baseline_universe_fingerprint="fp-b",
            run_backtest_fn=_fake_run_backtest_success,
        )
        agg = report.metric_aggregates["total_return_pct"]
        assert agg.consistency_state.value in {
            "CONSISTENT_CANDIDATE_HIGHER",
            "MOSTLY_CANDIDATE_HIGHER",
            "MIXED",
            "MOSTLY_BASELINE_HIGHER",
            "CONSISTENT_BASELINE_HIGHER",
            "EQUAL_OR_UNAVAILABLE",
        }

    def test_no_forbidden_states(self, tmp_path: Path) -> None:
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
        report = run_walk_forward_experiment(
            plan=plan,
            candidate_pairlist=("BTC/USDT",),
            baseline_pairlist=("BTC/USDT",),
            candidate_universe_fingerprint="fp-c",
            baseline_universe_fingerprint="fp-b",
            run_backtest_fn=_fake_run_backtest_success,
        )
        for agg in report.metric_aggregates.values():
            assert agg.consistency_state.value not in {
                "BETTER",
                "PROFITABLE",
                "WINNER",
                "APPROVED",
                "READY_FOR_LIVE",
                "EXECUTION_ALLOWED",
                "PRODUCTION_READY",
            }
