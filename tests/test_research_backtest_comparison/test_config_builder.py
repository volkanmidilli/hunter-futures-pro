"""Tests for Freqtrade config builder (MVP-65 Stage 2)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from hunter.research_backtest_comparison.config_builder import (
    build_freqtrade_config,
    enforce_forbidden_exchange_fields,
    validate_exchange_identifier,
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
            assert cfg["stake_amount"] == 100.0
            assert cfg["dry_run"] is True
            assert "research_only" not in cfg
            assert "human_approval_required" not in cfg
            assert "no_live_trading" not in cfg
            assert "no_automatic_execution" not in cfg
            assert cfg["pairlists"][0]["method"] == "StaticPairList"
            assert cfg["exchange"]["name"] == config.exchange_identifier
            assert cfg["exchange"]["name"] == "binance"
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

    def test_forbidden_field_rejected(self, tmp_path: Path) -> None:
        config = self._make_config(tmp_path)
        ws = create_workspace(prefix="test_forbidden_")
        ws.create()
        try:
            arm = BacktestArmInput(
                pairlist=("BTC/USDT",),
                label=BacktestArmLabel.CANDIDATE,
                universe_fingerprint="fp",
            )
            cfg = build_freqtrade_config(config, arm, ws)
            cfg["api_server"] = {"enabled": True}
            with pytest.raises(ResearchBacktestComparisonConfigError):
                enforce_forbidden_exchange_fields(cfg)
        finally:
            ws.cleanup()

    def test_forbidden_credential_rejected(self, tmp_path: Path) -> None:
        config = self._make_config(tmp_path)
        ws = create_workspace(prefix="test_cred_")
        ws.create()
        try:
            arm = BacktestArmInput(
                pairlist=("BTC/USDT",),
                label=BacktestArmLabel.CANDIDATE,
                universe_fingerprint="fp",
            )
            cfg = build_freqtrade_config(config, arm, ws)
            cfg["exchange"]["secret"] = "leaked_secret"
            with pytest.raises(ResearchBacktestComparisonConfigError):
                enforce_forbidden_exchange_fields(cfg)
        finally:
            ws.cleanup()

    def test_no_hunter_safety_keys_in_config(self, tmp_path: Path) -> None:
        config = self._make_config(tmp_path)
        ws = create_workspace(prefix="test_safety_keys_")
        ws.create()
        try:
            arm = BacktestArmInput(
                pairlist=("BTC/USDT",),
                label=BacktestArmLabel.CANDIDATE,
                universe_fingerprint="fp",
            )
            cfg = build_freqtrade_config(config, arm, ws)
            for forbidden_key in (
                "research_only",
                "execution_approval_granted",
                "production_approval_granted",
                "live_trading_allowed",
                "automatic_execution_allowed",
                "human_approval_required",
            ):
                assert forbidden_key not in cfg
        finally:
            ws.cleanup()

    def test_manifest_exchange_identifier_used(self, tmp_path: Path) -> None:
        # Config must reflect the caller/manifest-supplied exchange, never a
        # hardcoded placeholder.
        strategy = tmp_path / "strategy.py"
        strategy.write_text("# strategy")
        data = tmp_path / "data"
        data.mkdir()
        exe = tmp_path / "freqtrade"
        exe.write_text("#!/bin/sh")
        config = BacktestComparisonConfig(
            strategy_name="TestStrategy",
            strategy_path=strategy,
            data_path=data,
            timeframe="5m",
            timerange="20240101-20240201",
            balance=Decimal("1000"),
            stake=Decimal("100"),
            max_open_trades=1,
            fee=Decimal("0.001"),
            executable_path=exe,
            exchange_identifier="kraken",
        )
        ws = create_workspace(prefix="test_exchange_")
        ws.create()
        try:
            arm = BacktestArmInput(
                pairlist=("BTC/USDT",),
                label=BacktestArmLabel.CANDIDATE,
                universe_fingerprint="fp",
            )
            cfg = build_freqtrade_config(config, arm, ws)
            assert cfg["exchange"]["name"] == "kraken"
        finally:
            ws.cleanup()

    def test_futures_trading_mode_and_margin_mode_set(self, tmp_path: Path) -> None:
        strategy = tmp_path / "strategy.py"
        strategy.write_text("# strategy")
        data = tmp_path / "data"
        data.mkdir()
        exe = tmp_path / "freqtrade"
        exe.write_text("#!/bin/sh")
        config = BacktestComparisonConfig(
            strategy_name="TestStrategy",
            strategy_path=strategy,
            data_path=data,
            timeframe="5m",
            timerange="20240101-20240201",
            balance=Decimal("1000"),
            stake=Decimal("100"),
            max_open_trades=1,
            fee=Decimal("0.001"),
            executable_path=exe,
            exchange_identifier="binance",
            trading_mode="futures",
        )
        ws = create_workspace(prefix="test_futures_")
        ws.create()
        try:
            arm = BacktestArmInput(
                pairlist=("BTC/USDT:USDT",),
                label=BacktestArmLabel.CANDIDATE,
                universe_fingerprint="fp",
            )
            cfg = build_freqtrade_config(config, arm, ws)
            assert cfg["trading_mode"] == "futures"
            assert cfg["margin_mode"] == "isolated"
            assert cfg["stake_currency"] == "USDT"
        finally:
            ws.cleanup()

    def test_datadir_passed_via_command_not_config(self, tmp_path: Path) -> None:
        # Freqtrade only honors --datadir on the CLI, not a "datadir" config
        # key, so the built config must not rely on a config-level datadir.
        config = self._make_config(tmp_path)
        ws = create_workspace(prefix="test_nodatadir_")
        ws.create()
        try:
            arm = BacktestArmInput(
                pairlist=("BTC/USDT",),
                label=BacktestArmLabel.CANDIDATE,
                universe_fingerprint="fp",
            )
            cfg = build_freqtrade_config(config, arm, ws)
            assert "datadir" not in cfg
        finally:
            ws.cleanup()


class TestValidateExchangeIdentifier:
    def test_valid_real_exchange_accepted(self) -> None:
        validate_exchange_identifier("binance")

    def test_empty_rejected(self) -> None:
        with pytest.raises(ResearchBacktestComparisonConfigError):
            validate_exchange_identifier("")

    def test_blank_rejected(self) -> None:
        with pytest.raises(ResearchBacktestComparisonConfigError):
            validate_exchange_identifier("   ")

    def test_unsupported_placeholder_rejected(self) -> None:
        # The old hardcoded placeholder must now be rejected as a fake exchange.
        with pytest.raises(ResearchBacktestComparisonConfigError):
            validate_exchange_identifier("research-only")

    def test_unknown_exchange_rejected(self) -> None:
        with pytest.raises(ResearchBacktestComparisonConfigError):
            validate_exchange_identifier("not-a-real-exchange")
