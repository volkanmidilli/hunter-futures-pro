"""Tests for deterministic fingerprints (MVP-65 Stage 4)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from hunter.research_backtest_comparison.fingerprint import (
    config_fingerprint,
    metrics_fingerprint,
    pairlist_fingerprint,
    run_result_fingerprint,
    strategy_fingerprint,
)
from hunter.research_backtest_comparison.models import (
    BacktestArmInput,
    BacktestArmLabel,
    BacktestMetrics,
    BacktestRunResult,
)


class TestStrategyFingerprint:
    def test_deterministic(self, tmp_path: Path) -> None:
        strategy = tmp_path / "strategy.py"
        strategy.write_text("hello")
        assert strategy_fingerprint(strategy) == strategy_fingerprint(strategy)

    def test_different_content(self, tmp_path: Path) -> None:
        s1 = tmp_path / "s1.py"
        s1.write_text("a")
        s2 = tmp_path / "s2.py"
        s2.write_text("b")
        assert strategy_fingerprint(s1) != strategy_fingerprint(s2)


class TestPairlistFingerprint:
    def test_deterministic(self) -> None:
        arm = BacktestArmInput(
            pairlist=("BTC/USDT", "ETH/USDT"),
            label=BacktestArmLabel.CANDIDATE,
            universe_fingerprint="fp",
        )
        assert pairlist_fingerprint(arm) == pairlist_fingerprint(arm)

    def test_order_independent(self) -> None:
        arm1 = BacktestArmInput(
            pairlist=("BTC/USDT", "ETH/USDT"),
            label=BacktestArmLabel.CANDIDATE,
            universe_fingerprint="fp",
        )
        arm2 = BacktestArmInput(
            pairlist=("ETH/USDT", "BTC/USDT"),
            label=BacktestArmLabel.CANDIDATE,
            universe_fingerprint="fp",
        )
        assert pairlist_fingerprint(arm1) == pairlist_fingerprint(arm2)


class TestMetricsFingerprint:
    def test_deterministic(self) -> None:
        m = BacktestMetrics(total_return_pct=Decimal("10"), trade_count=5)
        assert metrics_fingerprint(m) == metrics_fingerprint(m)

    def test_different_values(self) -> None:
        m1 = BacktestMetrics(total_return_pct=Decimal("10"))
        m2 = BacktestMetrics(total_return_pct=Decimal("11"))
        assert metrics_fingerprint(m1) != metrics_fingerprint(m2)


class TestRunResultFingerprint:
    def test_excludes_workspace(self) -> None:
        result1 = BacktestRunResult(
            label=BacktestArmLabel.CANDIDATE,
            success=True,
            metrics=BacktestMetrics(total_return_pct=Decimal("10"), trade_count=5),
            stdout="",
            stderr="",
            exit_code=0,
            workspace="/tmp/ws1",
            result_file="/tmp/ws1/result.json",
            command=("freqtrade", "backtesting"),
            command_fingerprint="fp",
            strategy_sha_before="abc",
            strategy_sha_after="abc",
            fingerprint="fp",
        )
        result2 = BacktestRunResult(
            label=BacktestArmLabel.CANDIDATE,
            success=True,
            metrics=BacktestMetrics(total_return_pct=Decimal("10"), trade_count=5),
            stdout="different",
            stderr="",
            exit_code=0,
            workspace="/tmp/ws2",
            result_file="/tmp/ws2/result.json",
            command=("freqtrade", "backtesting"),
            command_fingerprint="fp",
            strategy_sha_before="abc",
            strategy_sha_after="abc",
            fingerprint="fp",
        )
        assert run_result_fingerprint(result1) == run_result_fingerprint(result2)
