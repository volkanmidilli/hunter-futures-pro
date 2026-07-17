"""Tests for the walk-forward engine (MVP-66 Stage 8)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from hunter.research_walk_forward.engine import (
    build_walk_forward_report,
    run_walk_forward_experiment,
)
from hunter.research_walk_forward.models import (
    MarketRegimeLabel,
    WalkForwardCommonConfig,
    WalkForwardMode,
)
from hunter.research_walk_forward.planner import build_rolling_plan
from tests.test_research_walk_forward.test_runner import (
    _fake_run_backtest_success,
    _make_common,
)


class TestEngineOrchestration:
    def test_run_full_experiment(self, tmp_path: Path) -> None:
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
            candidate_pairlist=("BTC/USDT", "ETH/USDT"),
            baseline_pairlist=("BTC/USDT",),
            candidate_universe_fingerprint="fp-c",
            baseline_universe_fingerprint="fp-b",
            run_backtest_fn=_fake_run_backtest_success,
        )
        assert report.plan.fingerprint != ""
        assert report.fingerprint != ""
        assert len(report.window_results) == 2
        assert len(report.metric_aggregates) == 12
        assert len(report.regime_aggregates) == 1
        assert report.regime_aggregates[0].regime_label == MarketRegimeLabel.UNKNOWN
        assert report.human_approval_required is True
        assert report.research_only is True

    def test_build_walk_forward_report_alias(self, tmp_path: Path) -> None:
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
        report = build_walk_forward_report(
            plan=plan,
            candidate_pairlist=("BTC/USDT",),
            baseline_pairlist=("BTC/USDT",),
            candidate_universe_fingerprint="fp-c",
            baseline_universe_fingerprint="fp-b",
            run_backtest_fn=_fake_run_backtest_success,
        )
        assert report.fingerprint != ""


class TestSafetyInvariant:
    def test_safety_invariant_violation(self, tmp_path: Path) -> None:
        from hunter.research_walk_forward.models import (
            WalkForwardExperimentPlan,
            WalkForwardSafetyFlags,
        )

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
        with pytest.raises(ValueError):
            unsafe_flags = WalkForwardSafetyFlags(research_only=False)
            unsafe_plan = WalkForwardExperimentPlan(
                mode=plan.mode,
                windows=plan.windows,
                common=plan.common,
                safety_flags=unsafe_flags,
            )
            run_walk_forward_experiment(
                plan=unsafe_plan,
                candidate_pairlist=("BTC/USDT",),
                baseline_pairlist=("BTC/USDT",),
                candidate_universe_fingerprint="fp-c",
                baseline_universe_fingerprint="fp-b",
                run_backtest_fn=_fake_run_backtest_success,
            )


class TestRegimeGroupingInEngine:
    def test_caller_provided_regime_grouping(self, tmp_path: Path) -> None:
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
            candidate_pairlist=("BTC/USDT",),
            baseline_pairlist=("BTC/USDT",),
            candidate_universe_fingerprint="fp-c",
            baseline_universe_fingerprint="fp-b",
            run_backtest_fn=_fake_run_backtest_success,
        )
        labels = {agg.regime_label for agg in report.regime_aggregates}
        assert MarketRegimeLabel.BULL in labels
        assert MarketRegimeLabel.BEAR in labels

    def test_unknown_regime_preserved(self, tmp_path: Path) -> None:
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
        assert report.regime_aggregates[0].regime_label == MarketRegimeLabel.UNKNOWN
