"""Tests for the sequential window runner (MVP-66 Stage 4)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from hunter.research_backtest_comparison import (
    BacktestArmInput,
    BacktestArmLabel,
    BacktestComparisonConfig,
    BacktestComparisonReport,
    BacktestComparisonResult,
    BacktestFairnessManifest,
    BacktestMetrics,
    BacktestRunResult,
    MetricInterpretation,
    ResearchBacktestSafetyFlags,
)
from hunter.research_walk_forward.models import (
    INSUFFICIENT_TRADES,
    TIMEOUT,
    ExperimentExecutionPolicy,
    MetricDirection,
    WalkForwardCommonConfig,
    WalkForwardMode,
    WalkForwardWindow,
    WindowStatus,
)
from hunter.research_walk_forward.planner import build_rolling_plan
from hunter.research_walk_forward.runner import (
    run_walk_forward_window,
    run_walk_forward_windows,
)


def _make_common(tmp_path: Path) -> WalkForwardCommonConfig:
    return WalkForwardCommonConfig(
        strategy_name="TestStrategy",
        strategy_path=tmp_path / "strategy.py",
        data_path=tmp_path / "data",
        timeframe="1h",
        balance=Decimal("1000"),
        stake=Decimal("100"),
        max_open_trades=3,
        fee=Decimal("0.001"),
        executable_path=tmp_path / "freqtrade",
        timeout_seconds=60,
    )


def _fake_run_backtest_success(
    *,
    config: BacktestComparisonConfig,
    candidate: BacktestArmInput,
    baseline: BacktestArmInput,
) -> BacktestComparisonReport:
    candidate_result = BacktestRunResult(
        label=BacktestArmLabel.CANDIDATE,
        success=True,
        metrics=BacktestMetrics(
            total_return_pct=Decimal("10"),
            trade_count=5,
        ),
        stdout="",
        stderr="",
        exit_code=0,
        workspace=Path("/tmp/ws-c"),
        result_file=Path("/tmp/ws-c/result.json"),
        command=("freqtrade", "backtesting"),
        command_fingerprint="fp-c",
        strategy_sha_before="abc",
        strategy_sha_after="abc",
        fingerprint="fp-rc",
        pairlist=candidate.pairlist,
    )
    baseline_result = BacktestRunResult(
        label=BacktestArmLabel.BASELINE,
        success=True,
        metrics=BacktestMetrics(
            total_return_pct=Decimal("5"),
            trade_count=5,
        ),
        stdout="",
        stderr="",
        exit_code=0,
        workspace=Path("/tmp/ws-b"),
        result_file=Path("/tmp/ws-b/result.json"),
        command=("freqtrade", "backtesting"),
        command_fingerprint="fp-b",
        strategy_sha_before="abc",
        strategy_sha_after="abc",
        fingerprint="fp-rb",
        pairlist=baseline.pairlist,
    )
    comparison = BacktestComparisonResult(
        candidate=candidate_result,
        baseline=baseline_result,
        metric_deltas={"total_return_pct": Decimal("5")},
        interpretations={"total_return_pct": MetricInterpretation.CANDIDATE_HIGHER},
        comparison_fingerprint="fp-comp",
        trade_sufficiency=True,
    )
    fairness = BacktestFairnessManifest(
        strategy_name=config.strategy_name,
        strategy_fingerprint="fp-s",
        data_fingerprint="fp-d",
        timeframe=config.timeframe,
        timerange=config.timerange,
        balance=config.balance,
        stake=config.stake,
        max_open_trades=config.max_open_trades,
        fee=config.fee,
        protections=(),
        assumptions_equal=True,
        pairlist_only_difference=("overlap=0", (), ()),
        fairness_fingerprint="fp-f",
    )
    from datetime import datetime, timezone
    from hunter.research_backtest_comparison import BacktestComparisonManifest

    manifest = BacktestComparisonManifest(
        version="0.65.0-dev",
        spec_version="SPEC-066",
        research_backtest_comparison_version="0.65.0-dev",
        generated_at=datetime.now(timezone.utc),
        config_fingerprint="fp-cfg",
        strategy_fingerprint="fp-s",
        candidate_pairlist_fingerprint="fp-cp",
        baseline_pairlist_fingerprint="fp-bp",
        candidate_result_fingerprint="fp-cr",
        baseline_result_fingerprint="fp-br",
        comparison_fingerprint="fp-comp",
        safety_flags=ResearchBacktestSafetyFlags(),
        reason_codes=(),
    )
    return BacktestComparisonReport(
        version="0.65.0-dev",
        spec_version="SPEC-066",
        research_backtest_comparison_version="0.65.0-dev",
        config=config,
        manifest=manifest,
        candidate=candidate_result,
        baseline=baseline_result,
        comparison=comparison,
        fairness=fairness,
        safety_flags=ResearchBacktestSafetyFlags(),
        fingerprint="fp-report",
    )


def _fake_run_backtest_insufficient(
    *,
    config: BacktestComparisonConfig,
    candidate: BacktestArmInput,
    baseline: BacktestArmInput,
) -> BacktestComparisonReport:
    report = _fake_run_backtest_success(
        config=config, candidate=candidate, baseline=baseline
    )
    comparison = BacktestComparisonResult(
        candidate=report.candidate,
        baseline=report.baseline,
        metric_deltas=report.comparison.metric_deltas,
        interpretations=report.comparison.interpretations,
        comparison_fingerprint=report.comparison.comparison_fingerprint,
        trade_sufficiency=False,
        reason_codes=(INSUFFICIENT_TRADES,),
    )
    return _replace_comparison(report, comparison)


def _fake_run_backtest_timeout(
    *,
    config: BacktestComparisonConfig,
    candidate: BacktestArmInput,
    baseline: BacktestArmInput,
) -> BacktestComparisonReport:
    report = _fake_run_backtest_success(
        config=config, candidate=candidate, baseline=baseline
    )
    candidate = BacktestRunResult(
        label=report.candidate.label,
        success=False,
        metrics=BacktestMetrics(reason_codes=(TIMEOUT,)),
        stdout="",
        stderr="",
        exit_code=-1,
        workspace=report.candidate.workspace,
        result_file=None,
        command=report.candidate.command,
        command_fingerprint=report.candidate.command_fingerprint,
        strategy_sha_before=report.candidate.strategy_sha_before,
        strategy_sha_after=report.candidate.strategy_sha_after,
        fingerprint=report.candidate.fingerprint,
        reason_codes=(TIMEOUT,),
    )
    comparison = BacktestComparisonResult(
        candidate=candidate,
        baseline=report.baseline,
        metric_deltas={},
        interpretations={},
        comparison_fingerprint="fp-comp-timeout",
        trade_sufficiency=False,
        reason_codes=(TIMEOUT,),
    )
    return _replace_comparison(report, comparison)


def _replace_comparison(
    report: BacktestComparisonReport,
    comparison: BacktestComparisonResult,
) -> BacktestComparisonReport:
    from dataclasses import replace

    return replace(report, candidate=comparison.candidate, comparison=comparison)


class TestRunSingleWindow:
    def test_successful_window(self, tmp_path: Path) -> None:
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
        result = run_walk_forward_window(
            plan=plan,
            window=plan.windows[0],
            window_index=0,
            candidate_pairlist=("BTC/USDT",),
            baseline_pairlist=("BTC/USDT",),
            candidate_universe_fingerprint="fp-c",
            baseline_universe_fingerprint="fp-b",
            run_backtest_fn=_fake_run_backtest_success,
        )
        assert result.status == WindowStatus.COMPLETED
        assert result.candidate_metrics["total_return_pct"] == Decimal("10")
        assert result.baseline_metrics["total_return_pct"] == Decimal("5")
        assert result.metric_deltas["total_return_pct"] == Decimal("5")
        assert result.metric_directions["total_return_pct"] == MetricDirection.CANDIDATE_HIGHER

    def test_insufficient_window(self, tmp_path: Path) -> None:
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
        result = run_walk_forward_window(
            plan=plan,
            window=plan.windows[0],
            window_index=0,
            candidate_pairlist=("BTC/USDT",),
            baseline_pairlist=("BTC/USDT",),
            candidate_universe_fingerprint="fp-c",
            baseline_universe_fingerprint="fp-b",
            run_backtest_fn=_fake_run_backtest_insufficient,
        )
        assert result.status == WindowStatus.INSUFFICIENT
        assert INSUFFICIENT_TRADES in result.reason_codes

    def test_timed_out_window(self, tmp_path: Path) -> None:
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
        result = run_walk_forward_window(
            plan=plan,
            window=plan.windows[0],
            window_index=0,
            candidate_pairlist=("BTC/USDT",),
            baseline_pairlist=("BTC/USDT",),
            candidate_universe_fingerprint="fp-c",
            baseline_universe_fingerprint="fp-b",
            run_backtest_fn=_fake_run_backtest_timeout,
        )
        assert result.status == WindowStatus.TIMED_OUT
        assert TIMEOUT in result.reason_codes

    def test_failed_window_exception(self, tmp_path: Path) -> None:
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

        def fake_exception(*, config, candidate, baseline):
            raise RuntimeError("boom")

        result = run_walk_forward_window(
            plan=plan,
            window=plan.windows[0],
            window_index=0,
            candidate_pairlist=("BTC/USDT",),
            baseline_pairlist=("BTC/USDT",),
            candidate_universe_fingerprint="fp-c",
            baseline_universe_fingerprint="fp-b",
            run_backtest_fn=fake_exception,
        )
        assert result.status == WindowStatus.FAILED


class TestExecutionPolicies:
    def test_collect_all_policy(self, tmp_path: Path) -> None:
        common = _make_common(tmp_path)
        plan = build_rolling_plan(
            common,
            selection_start="20240101",
            selection_end="20240201",
            evaluation_start="20240301",
            evaluation_end="20240401",
            step_days=31,
            count=3,
        )
        results = run_walk_forward_windows(
            plan=plan,
            candidate_pairlist=("BTC/USDT",),
            baseline_pairlist=("BTC/USDT",),
            candidate_universe_fingerprint="fp-c",
            baseline_universe_fingerprint="fp-b",
            execution_policy=ExperimentExecutionPolicy.COLLECT_ALL,
            run_backtest_fn=_fake_run_backtest_success,
        )
        assert len(results) == 3
        assert all(r.status == WindowStatus.COMPLETED for r in results)

    def test_fail_fast_policy(self, tmp_path: Path) -> None:
        common = _make_common(tmp_path)
        plan = build_rolling_plan(
            common,
            selection_start="20240101",
            selection_end="20240201",
            evaluation_start="20240301",
            evaluation_end="20240401",
            step_days=31,
            count=3,
        )
        call_count = 0

        def fake_with_failure(*, config, candidate, baseline):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("fail")
            return _fake_run_backtest_success(
                config=config, candidate=candidate, baseline=baseline
            )

        results = run_walk_forward_windows(
            plan=plan,
            candidate_pairlist=("BTC/USDT",),
            baseline_pairlist=("BTC/USDT",),
            candidate_universe_fingerprint="fp-c",
            baseline_universe_fingerprint="fp-b",
            execution_policy=ExperimentExecutionPolicy.FAIL_FAST,
            run_backtest_fn=fake_with_failure,
        )
        assert len(results) == 2
        assert results[0].status == WindowStatus.COMPLETED
        assert results[1].status == WindowStatus.FAILED

    def test_windows_run_sequentially(self, tmp_path: Path) -> None:
        common = _make_common(tmp_path)
        plan = build_rolling_plan(
            common,
            selection_start="20240101",
            selection_end="20240201",
            evaluation_start="20240301",
            evaluation_end="20240401",
            step_days=31,
            count=3,
        )
        call_order: list[int] = []

        def fake_tracing(*, config, candidate, baseline):
            call_order.append(len(call_order))
            return _fake_run_backtest_success(
                config=config, candidate=candidate, baseline=baseline
            )

        run_walk_forward_windows(
            plan=plan,
            candidate_pairlist=("BTC/USDT",),
            baseline_pairlist=("BTC/USDT",),
            candidate_universe_fingerprint="fp-c",
            baseline_universe_fingerprint="fp-b",
            run_backtest_fn=fake_tracing,
        )
        assert call_order == [0, 1, 2]


class TestNoDirectSubprocess:
    def test_runner_does_not_import_subprocess(self, tmp_path: Path) -> None:
        import hunter.research_walk_forward.runner as runner_module

        assert "subprocess" not in runner_module.__dict__
