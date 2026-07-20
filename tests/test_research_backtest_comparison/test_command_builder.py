"""Tests for command builder (MVP-65 Stage 3)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from hunter.research_backtest_comparison.command_builder import (
    build_backtest_command,
    command_fingerprint,
)
from hunter.research_backtest_comparison.errors import (
    ResearchBacktestComparisonValidationError,
)
from hunter.research_backtest_comparison.models import BacktestComparisonConfig
from hunter.research_backtest_comparison.workspace import create_workspace


class TestBuildBacktestCommand:
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

    def test_fixed_command_shape(self, tmp_path: Path) -> None:
        config = self._make_config(tmp_path)
        ws = create_workspace(prefix="test_cmd_")
        ws.create()
        try:
            args = build_backtest_command(config, ws)
            assert args[0] == str(config.executable_path)
            assert args[1] == "backtesting"
            assert "--config" in args
            assert "--userdir" in args
            assert "--strategy" in args
            assert "--timeframe" in args
            assert "--timerange" in args
            assert "--export" in args
            assert "trades" in args
            assert "--backtest-directory" in args
        finally:
            ws.cleanup()

    def test_datadir_passed_and_matches_config_data_path(self, tmp_path: Path) -> None:
        config = self._make_config(tmp_path)
        ws = create_workspace(prefix="test_cmd_datadir_")
        ws.create()
        try:
            args = build_backtest_command(config, ws)
            assert "--datadir" in args
            idx = args.index("--datadir")
            assert args[idx + 1] == str(config.data_path)
        finally:
            ws.cleanup()

    def test_forbidden_subcommand_rejected(self, tmp_path: Path) -> None:
        config = self._make_config(tmp_path)
        # Simulate injection by putting a forbidden subcommand in the strategy name.
        config = BacktestComparisonConfig(
            strategy_name="trade",
            strategy_path=config.strategy_path,
            data_path=config.data_path,
            timeframe=config.timeframe,
            timerange=config.timerange,
            balance=config.balance,
            stake=config.stake,
            max_open_trades=config.max_open_trades,
            fee=config.fee,
            executable_path=config.executable_path,
        )
        ws = create_workspace(prefix="test_forbidden_")
        ws.create()
        try:
            with pytest.raises(ResearchBacktestComparisonValidationError):
                build_backtest_command(config, ws)
        finally:
            ws.cleanup()

    def test_shell_metacharacter_rejected(self, tmp_path: Path) -> None:
        config = self._make_config(tmp_path)
        config = BacktestComparisonConfig(
            strategy_name="Test; rm -rf /",
            strategy_path=config.strategy_path,
            data_path=config.data_path,
            timeframe=config.timeframe,
            timerange=config.timerange,
            balance=config.balance,
            stake=config.stake,
            max_open_trades=config.max_open_trades,
            fee=config.fee,
            executable_path=config.executable_path,
        )
        ws = create_workspace(prefix="test_shell_")
        ws.create()
        try:
            with pytest.raises(ResearchBacktestComparisonValidationError):
                build_backtest_command(config, ws)
        finally:
            ws.cleanup()

    def test_command_fingerprint_deterministic(self) -> None:
        args = ["freqtrade", "backtesting", "--config", "x.json"]
        fp1 = command_fingerprint(args)
        fp2 = command_fingerprint(args)
        assert fp1 == fp2
        assert len(fp1) == 64

    def test_command_fingerprint_differs(self) -> None:
        fp1 = command_fingerprint(["freqtrade", "backtesting"])
        fp2 = command_fingerprint(["freqtrade", "trade"])
        assert fp1 != fp2
