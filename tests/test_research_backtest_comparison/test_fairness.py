"""Tests for fairness manifest (MVP-65 Stage 3)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from hunter.research_backtest_comparison.fairness import (
    build_fairness_manifest,
    verify_fairness,
)
from hunter.research_backtest_comparison.models import (
    BacktestArmInput,
    BacktestArmLabel,
    BacktestComparisonConfig,
)


class TestBuildFairnessManifest:
    def _make_config(self, tmp_path: Path) -> BacktestComparisonConfig:
        strategy = tmp_path / "strategy.py"
        strategy.write_text("# strategy content")
        data = tmp_path / "data"
        data.mkdir()
        (data / "BTC_USDT-1h.json").write_text("[]")
        exe = tmp_path / "freqtrade"
        exe.write_text("#!/bin/sh")
        return BacktestComparisonConfig(
            strategy_name="TestStrategy",
            strategy_path=strategy,
            data_path=data,
            timeframe="1h",
            timerange="20240101-20240201",
            balance=Decimal("1000"),
            stake=Decimal("100"),
            max_open_trades=3,
            fee=Decimal("0.001"),
            executable_path=exe,
        )

    def test_equal_assumptions_different_pairlists(self, tmp_path: Path) -> None:
        config = self._make_config(tmp_path)
        candidate = BacktestArmInput(
            pairlist=("BTC/USDT", "ETH/USDT"),
            label=BacktestArmLabel.CANDIDATE,
            universe_fingerprint="fp-c",
        )
        baseline = BacktestArmInput(
            pairlist=("BTC/USDT", "SOL/USDT"),
            label=BacktestArmLabel.BASELINE,
            universe_fingerprint="fp-b",
        )
        manifest = build_fairness_manifest(config, candidate, baseline)
        assert manifest.assumptions_equal is True
        assert manifest.strategy_name == "TestStrategy"
        assert len(manifest.strategy_fingerprint) == 64
        assert len(manifest.data_fingerprint) == 64
        verify_fairness(manifest)

    def test_pairlist_only_difference(self, tmp_path: Path) -> None:
        config = self._make_config(tmp_path)
        candidate = BacktestArmInput(
            pairlist=("BTC/USDT", "ETH/USDT"),
            label=BacktestArmLabel.CANDIDATE,
            universe_fingerprint="fp-c",
        )
        baseline = BacktestArmInput(
            pairlist=("BTC/USDT", "SOL/USDT"),
            label=BacktestArmLabel.BASELINE,
            universe_fingerprint="fp-b",
        )
        manifest = build_fairness_manifest(config, candidate, baseline)
        assert manifest.pairlist_only_difference[1] == ("ETH/USDT",)
        assert manifest.pairlist_only_difference[2] == ("SOL/USDT",)

    def test_fairness_fingerprint_deterministic(self, tmp_path: Path) -> None:
        config = self._make_config(tmp_path)
        candidate = BacktestArmInput(
            pairlist=("BTC/USDT", "ETH/USDT"),
            label=BacktestArmLabel.CANDIDATE,
            universe_fingerprint="fp-c",
        )
        baseline = BacktestArmInput(
            pairlist=("BTC/USDT", "SOL/USDT"),
            label=BacktestArmLabel.BASELINE,
            universe_fingerprint="fp-b",
        )
        m1 = build_fairness_manifest(config, candidate, baseline)
        m2 = build_fairness_manifest(config, candidate, baseline)
        assert m1.fairness_fingerprint == m2.fairness_fingerprint
