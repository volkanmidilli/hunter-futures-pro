"""Tests for research_backtest_comparison validator (MVP-65 Stage 1)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from hunter.research_backtest_comparison.errors import (
    ResearchBacktestComparisonConfigError,
    ResearchBacktestComparisonValidationError,
)
from hunter.research_backtest_comparison.models import (
    BacktestArmInput,
    BacktestArmLabel,
    BacktestComparisonConfig,
)
from hunter.research_backtest_comparison.validator import (
    validate_command_args,
    validate_config,
    validate_pairlist,
)


class TestValidateConfig:
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

    def test_valid(self, tmp_path: Path) -> None:
        config = self._make_config(tmp_path)
        validate_config(config)

    def test_none_config(self) -> None:
        with pytest.raises(ResearchBacktestComparisonConfigError):
            validate_config(None)

    def test_strategy_not_file(self, tmp_path: Path) -> None:
        config = self._make_config(tmp_path)
        config = BacktestComparisonConfig(
            strategy_name=config.strategy_name,
            strategy_path=tmp_path / "missing.py",
            data_path=config.data_path,
            timeframe=config.timeframe,
            timerange=config.timerange,
            balance=config.balance,
            stake=config.stake,
            max_open_trades=config.max_open_trades,
            fee=config.fee,
            executable_path=config.executable_path,
        )
        with pytest.raises(ResearchBacktestComparisonConfigError):
            validate_config(config)

    def test_data_not_directory(self, tmp_path: Path) -> None:
        config = self._make_config(tmp_path)
        data_file = tmp_path / "data.txt"
        data_file.write_text("x")
        config = BacktestComparisonConfig(
            strategy_name=config.strategy_name,
            strategy_path=config.strategy_path,
            data_path=data_file,
            timeframe=config.timeframe,
            timerange=config.timerange,
            balance=config.balance,
            stake=config.stake,
            max_open_trades=config.max_open_trades,
            fee=config.fee,
            executable_path=config.executable_path,
        )
        with pytest.raises(ResearchBacktestComparisonConfigError):
            validate_config(config)

    def test_executable_missing(self, tmp_path: Path) -> None:
        config = self._make_config(tmp_path)
        config = BacktestComparisonConfig(
            strategy_name=config.strategy_name,
            strategy_path=config.strategy_path,
            data_path=config.data_path,
            timeframe=config.timeframe,
            timerange=config.timerange,
            balance=config.balance,
            stake=config.stake,
            max_open_trades=config.max_open_trades,
            fee=config.fee,
            executable_path=tmp_path / "missing",
        )
        with pytest.raises(ResearchBacktestComparisonConfigError):
            validate_config(config)

    def test_relative_strategy_path(self, tmp_path: Path) -> None:
        strategy = tmp_path / "strategy.py"
        strategy.write_text("# strategy")
        data = tmp_path / "data"
        data.mkdir()
        exe = tmp_path / "freqtrade"
        exe.write_text("#!/bin/sh")
        config = BacktestComparisonConfig(
            strategy_name="TestStrategy",
            strategy_path="strategy.py",
            data_path=data,
            timeframe="1h",
            timerange="20240101-20240201",
            balance=Decimal("1000"),
            stake=Decimal("100"),
            max_open_trades=3,
            fee=Decimal("0.001"),
            executable_path=exe,
        )
        with pytest.raises(ResearchBacktestComparisonConfigError):
            validate_config(config)

    def test_path_traversal_rejected(self, tmp_path: Path) -> None:
        config = self._make_config(tmp_path)
        outside = tmp_path / ".." / "outside.py"
        config = BacktestComparisonConfig(
            strategy_name=config.strategy_name,
            strategy_path=outside,
            data_path=config.data_path,
            timeframe=config.timeframe,
            timerange=config.timerange,
            balance=config.balance,
            stake=config.stake,
            max_open_trades=config.max_open_trades,
            fee=config.fee,
            executable_path=config.executable_path,
        )
        with pytest.raises(ResearchBacktestComparisonConfigError):
            validate_config(config)

    def test_permitted_parent(self, tmp_path: Path) -> None:
        config = self._make_config(tmp_path)
        validate_config(config, permitted_strategy_parent=tmp_path, permitted_data_parent=tmp_path)

    def test_outside_permitted_parent(self, tmp_path: Path) -> None:
        config = self._make_config(tmp_path)
        other = tmp_path / "other"
        other.mkdir()
        with pytest.raises(ResearchBacktestComparisonConfigError):
            validate_config(config, permitted_strategy_parent=other)


class TestValidatePairlist:
    def test_valid(self) -> None:
        arm = BacktestArmInput(
            pairlist=("BTC/USDT", "ETH/USDT"),
            label=BacktestArmLabel.CANDIDATE,
            universe_fingerprint="fp",
        )
        validate_pairlist(arm)

    def test_empty(self) -> None:
        with pytest.raises(ValueError):
            BacktestArmInput(
                pairlist=(),
                label=BacktestArmLabel.CANDIDATE,
                universe_fingerprint="fp",
            )

    def test_unsafe_pair(self) -> None:
        arm = BacktestArmInput(
            pairlist=("BTC/USDT;rm -rf /",),
            label=BacktestArmLabel.CANDIDATE,
            universe_fingerprint="fp",
        )
        with pytest.raises(ResearchBacktestComparisonValidationError):
            validate_pairlist(arm)

    def test_none(self) -> None:
        with pytest.raises(ResearchBacktestComparisonValidationError):
            validate_pairlist(None)


class TestValidateCommandArgs:
    def test_valid_backtesting(self) -> None:
        validate_command_args(["freqtrade", "backtesting", "--config", "x.json"])

    def test_forbidden_trade(self) -> None:
        with pytest.raises(ResearchBacktestComparisonValidationError):
            validate_command_args(["freqtrade", "trade"])

    def test_forbidden_subcommand_in_arg(self) -> None:
        with pytest.raises(ResearchBacktestComparisonValidationError):
            validate_command_args(["freqtrade", "backtesting", "hyperopt"])

    def test_not_backtesting(self) -> None:
        with pytest.raises(ResearchBacktestComparisonValidationError):
            validate_command_args(["freqtrade", "download-data"])

    def test_empty(self) -> None:
        with pytest.raises(ResearchBacktestComparisonValidationError):
            validate_command_args([])

    def test_unsafe_character(self) -> None:
        with pytest.raises(ResearchBacktestComparisonValidationError):
            validate_command_args(["freqtrade", "backtesting", ";rm"])

    def test_non_string_arg(self) -> None:
        with pytest.raises(ResearchBacktestComparisonValidationError):
            validate_command_args(["freqtrade", "backtesting", 123])
