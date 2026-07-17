"""Tests for paired backtest comparison (MVP-65 Stage 4)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from hunter.research_backtest_comparison.comparison import (
    compare_backtest_metrics,
    compare_backtest_results,
)
from hunter.research_backtest_comparison.models import (
    BacktestArmLabel,
    BacktestMetrics,
    BacktestRunResult,
    MetricInterpretation,
)


class TestCompareBacktestMetrics:
    def test_candidate_higher(self) -> None:
        candidate = BacktestMetrics(total_return_pct=Decimal("10"))
        baseline = BacktestMetrics(total_return_pct=Decimal("5"))
        deltas, interpretations = compare_backtest_metrics(candidate, baseline)
        assert deltas["total_return_pct"] == Decimal("5")
        assert interpretations["total_return_pct"] == MetricInterpretation.CANDIDATE_HIGHER

    def test_baseline_higher(self) -> None:
        candidate = BacktestMetrics(total_return_pct=Decimal("5"))
        baseline = BacktestMetrics(total_return_pct=Decimal("10"))
        deltas, interpretations = compare_backtest_metrics(candidate, baseline)
        assert deltas["total_return_pct"] == Decimal("-5")
        assert interpretations["total_return_pct"] == MetricInterpretation.BASELINE_HIGHER

    def test_equal(self) -> None:
        candidate = BacktestMetrics(total_return_pct=Decimal("5"))
        baseline = BacktestMetrics(total_return_pct=Decimal("5"))
        deltas, interpretations = compare_backtest_metrics(candidate, baseline)
        assert deltas["total_return_pct"] == Decimal("0")
        assert interpretations["total_return_pct"] == MetricInterpretation.EQUAL

    def test_unavailable(self) -> None:
        candidate = BacktestMetrics(total_return_pct=Decimal("5"))
        baseline = BacktestMetrics(total_return_pct=None)
        deltas, interpretations = compare_backtest_metrics(candidate, baseline)
        assert deltas["total_return_pct"] is None
        assert interpretations["total_return_pct"] == MetricInterpretation.UNAVAILABLE


class TestCompareBacktestResults:
    def _make_result(
        self,
        label: BacktestArmLabel,
        total_return_pct: Decimal | None,
        trade_count: int,
    ) -> BacktestRunResult:
        return BacktestRunResult(
            label=label,
            success=True,
            metrics=BacktestMetrics(
                total_return_pct=total_return_pct,
                trade_count=trade_count,
            ),
            stdout="",
            stderr="",
            exit_code=0,
            workspace="/tmp/ws",
            result_file="/tmp/ws/result.json",
            command=("freqtrade", "backtesting"),
            command_fingerprint="fp",
            strategy_sha_before="abc",
            strategy_sha_after="abc",
            fingerprint="fp",
        )

    def test_trade_sufficiency(self) -> None:
        candidate = self._make_result(BacktestArmLabel.CANDIDATE, Decimal("10"), 10)
        baseline = self._make_result(BacktestArmLabel.BASELINE, Decimal("5"), 10)
        result = compare_backtest_results(candidate, baseline)
        assert result.trade_sufficiency is True
        assert result.metric_deltas["total_return_pct"] == Decimal("5")

    def test_insufficient_trades(self) -> None:
        candidate = self._make_result(BacktestArmLabel.CANDIDATE, Decimal("10"), 0)
        baseline = self._make_result(BacktestArmLabel.BASELINE, Decimal("5"), 0)
        result = compare_backtest_results(candidate, baseline)
        assert result.trade_sufficiency is False

    def test_fingerprint_present(self) -> None:
        candidate = self._make_result(BacktestArmLabel.CANDIDATE, Decimal("10"), 10)
        baseline = self._make_result(BacktestArmLabel.BASELINE, Decimal("5"), 10)
        result = compare_backtest_results(candidate, baseline)
        assert len(result.comparison_fingerprint) == 64
