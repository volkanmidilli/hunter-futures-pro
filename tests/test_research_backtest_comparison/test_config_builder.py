"""Tests for Freqtrade config builder (MVP-65 Stage 2)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from hunter.research_backtest_comparison.config_builder import (
    build_freqtrade_config,
    write_freqtrade_config,
)
from hunter.research_backtest_comparison.errors import (
    ResearchBacktestComparisonConfigError,
)
from hunter.research_backtest_comparison.models import (
    BacktestArmInput,
    BacktestArmLabel,
    BacktestComparisonConfig,
)
from hunter.research_backtest_comparison.workspace import create_workspace


class TestBuildFreqtradeConfig:
    def _make_config(self, tmp_path: Path) -> BacktestComparisonConfig:
        strategy = tmp_path / "strategy.py"
        strategy.write_text("# strategy")
        data = tmp_path / "data"
        data.mkdir()
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

    def test_config_structure(self, tmp_path: Path) -> None:
        config = self._make_config(tmp_path)
        ws = create_workspace(prefix="test_cfg_")
        ws.create()
        try:
            arm = BacktestArmInput(
                pairlist=("BTC/USDT", "ETH/USDT"),
                label=BacktestArmLabel.CANDIDATE,
                universe_fingerprint="fp",
            )
            cfg = build_freqtrade_config(config, arm, ws)
            assert cfg["max_open_trades"] == 3
            assert cfg["stake_currency"] == "USDT"
            assert cfg["stake_amount"] == "100"
            assert cfg["dry_run"] is True
            assert cfg["research_only"] is True
            assert cfg["pairlists"][0]["method"] == "StaticPairList"
            assert cfg["exchange"]["name"] == "research-only"
            assert cfg["exchange"]["key"] == ""
            assert cfg["exchange"]["secret"] == ""
        finally:
            ws.cleanup()

    def test_empty_pairlist_rejected(self, tmp_path: Path) -> None:
        config = self._make_config(tmp_path)
        ws = create_workspace(prefix="test_empty_")
        ws.create()
        try:
            with pytest.raises(ValueError):
                BacktestArmInput(
                    pairlist=(),
                    label=BacktestArmLabel.CANDIDATE,
                    universe_fingerprint="fp",
                )
        finally:
            ws.cleanup()

    def test_write_config(self, tmp_path: Path) -> None:
        config = self._make_config(tmp_path)
        ws = create_workspace(prefix="test_write_")
        ws.create()
        try:
            arm = BacktestArmInput(
                pairlist=("BTC/USDT",),
                label=BacktestArmLabel.CANDIDATE,
                universe_fingerprint="fp",
            )
            path = write_freqtrade_config(config, arm, ws)
            assert path.exists()
            assert "max_open_trades" in path.read_text()
        finally:
            ws.cleanup()
