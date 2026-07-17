"""Tests for research_backtest_comparison models (MVP-65 Stage 1)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from hunter.research_backtest_comparison.models import (
    RESEARCH_BACKTEST_COMPARISON_VERSION,
    SPEC_VERSION,
    UNAVAILABLE,
    BacktestArmInput,
    BacktestArmLabel,
    BacktestComparisonConfig,
    BacktestComparisonManifest,
    BacktestComparisonReport,
    BacktestComparisonResult,
    BacktestFairnessManifest,
    BacktestMetrics,
    BacktestRunResult,
    FreqtradeExecutableInfo,
    MetricInterpretation,
    ResearchBacktestSafetyFlags,
    ResearchBacktestComparisonWriterError,
)


class TestVersionConstants:
    def test_version_constants(self) -> None:
        assert RESEARCH_BACKTEST_COMPARISON_VERSION == "0.65.0-dev"
        assert SPEC_VERSION == "SPEC-066"
        assert UNAVAILABLE == "UNAVAILABLE"


class TestResearchBacktestSafetyFlags:
    def test_defaults(self) -> None:
        flags = ResearchBacktestSafetyFlags()
        assert flags.research_only is True
        assert flags.execution_approval_granted is False
        assert flags.production_approval_granted is False
        assert flags.live_trading_allowed is False
        assert flags.automatic_execution_allowed is False
        assert flags.human_approval_required is True
        assert flags.no_freqtrade_runtime_connection is False

    def test_research_only_mutation_rejected(self) -> None:
        with pytest.raises(ValueError):
            ResearchBacktestSafetyFlags(research_only=False)

    def test_human_approval_required_mutation_rejected(self) -> None:
        with pytest.raises(ValueError):
            ResearchBacktestSafetyFlags(human_approval_required=False)

    def test_non_bool_rejected(self) -> None:
        with pytest.raises(ValueError):
            ResearchBacktestSafetyFlags(research_only="yes")


class TestBacktestComparisonConfig:
    def _make_config(self, tmp_path: Path) -> BacktestComparisonConfig:
        strategy = tmp_path / "strategy.py"
        strategy.write_text("# strategy")
        data = tmp_path / "data"
        data.mkdir()
        exe = tmp_path / "freqtrade"
        exe.write_text("#!/bin/sh\necho fake")
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
            timeout_seconds=60,
        )

    def test_valid_config(self, tmp_path: Path) -> None:
        config = self._make_config(tmp_path)
        assert config.strategy_name == "TestStrategy"
        assert config.balance == Decimal("1000")
        assert config.stake == Decimal("100")
        assert config.max_open_trades == 3
        assert isinstance(config.strategy_path, Path)

    def test_negative_balance_rejected(self, tmp_path: Path) -> None:
        strategy = tmp_path / "strategy.py"
        strategy.write_text("# strategy")
        data = tmp_path / "data"
        data.mkdir()
        exe = tmp_path / "freqtrade"
        exe.write_text("#!/bin/sh")
        with pytest.raises(ValueError):
            BacktestComparisonConfig(
                strategy_name="TestStrategy",
                strategy_path=strategy,
                data_path=data,
                timeframe="1h",
                timerange="20240101-20240201",
                balance=Decimal("-1"),
                stake=Decimal("100"),
                max_open_trades=3,
                fee=Decimal("0.001"),
                executable_path=exe,
            )

    def test_zero_stake_rejected(self, tmp_path: Path) -> None:
        strategy = tmp_path / "strategy.py"
        strategy.write_text("# strategy")
        data = tmp_path / "data"
        data.mkdir()
        exe = tmp_path / "freqtrade"
        exe.write_text("#!/bin/sh")
        with pytest.raises(ValueError):
            BacktestComparisonConfig(
                strategy_name="TestStrategy",
                strategy_path=strategy,
                data_path=data,
                timeframe="1h",
                timerange="20240101-20240201",
                balance=Decimal("1000"),
                stake=Decimal("0"),
                max_open_trades=3,
                fee=Decimal("0.001"),
                executable_path=exe,
            )

    def test_max_open_trades_zero_rejected(self, tmp_path: Path) -> None:
        strategy = tmp_path / "strategy.py"
        strategy.write_text("# strategy")
        data = tmp_path / "data"
        data.mkdir()
        exe = tmp_path / "freqtrade"
        exe.write_text("#!/bin/sh")
        with pytest.raises(ValueError):
            BacktestComparisonConfig(
                strategy_name="TestStrategy",
                strategy_path=strategy,
                data_path=data,
                timeframe="1h",
                timerange="20240101-20240201",
                balance=Decimal("1000"),
                stake=Decimal("100"),
                max_open_trades=0,
                fee=Decimal("0.001"),
                executable_path=exe,
            )


class TestBacktestArmInput:
    def test_valid(self) -> None:
        arm = BacktestArmInput(
            pairlist=("BTC/USDT", "ETH/USDT"),
            label=BacktestArmLabel.CANDIDATE,
            universe_fingerprint="fp-candidate",
        )
        assert arm.pairlist == ("BTC/USDT", "ETH/USDT")
        assert arm.label == BacktestArmLabel.CANDIDATE

    def test_empty_pairlist_rejected(self) -> None:
        with pytest.raises(ValueError):
            BacktestArmInput(
                pairlist=(),
                label=BacktestArmLabel.CANDIDATE,
                universe_fingerprint="fp",
            )

    def test_invalid_label_rejected(self) -> None:
        with pytest.raises(ValueError):
            BacktestArmInput(
                pairlist=("BTC/USDT",),
                label="CANDIDATE",
                universe_fingerprint="fp",
            )


class TestFreqtradeExecutableInfo:
    def test_valid(self) -> None:
        info = FreqtradeExecutableInfo(
            path="/tmp/freqtrade",
            version="2024.1",
            is_valid=True,
        )
        assert info.path == Path("/tmp/freqtrade")
        assert info.is_valid is True


class TestBacktestMetrics:
    def test_default_unavailable(self) -> None:
        metrics = BacktestMetrics()
        assert metrics.total_return_pct is None
        assert metrics.trade_count == 0

    def test_coerce_decimal(self) -> None:
        metrics = BacktestMetrics(total_return_pct="12.34")
        assert metrics.total_return_pct == Decimal("12.34")

    def test_invalid_trade_count(self) -> None:
        with pytest.raises(ValueError):
            BacktestMetrics(trade_count=-1)


class TestBacktestRunResult:
    def _make_result(self) -> BacktestRunResult:
        return BacktestRunResult(
            label=BacktestArmLabel.CANDIDATE,
            success=True,
            metrics=BacktestMetrics(),
            stdout="",
            stderr="",
            exit_code=0,
            workspace="/tmp/ws",
            result_file="/tmp/ws/result.json",
            command=("freqtrade", "backtesting"),
            command_fingerprint="fp-cmd",
            strategy_sha_before="abc",
            strategy_sha_after="abc",
            fingerprint="fp-run",
        )

    def test_valid(self) -> None:
        result = self._make_result()
        assert result.success is True
        assert result.workspace == Path("/tmp/ws")

    def test_mismatched_strategy_sha(self) -> None:
        # Mismatched SHA is allowed at the model layer; runner enforces it.
        result = BacktestRunResult(
            label=BacktestArmLabel.CANDIDATE,
            success=True,
            metrics=BacktestMetrics(),
            stdout="",
            stderr="",
            exit_code=0,
            workspace="/tmp/ws",
            result_file="/tmp/ws/result.json",
            command=("freqtrade", "backtesting"),
            command_fingerprint="fp-cmd",
            strategy_sha_before="abc",
            strategy_sha_after="def",
            fingerprint="fp-run",
        )
        assert result.strategy_sha_before != result.strategy_sha_after


class TestBacktestComparisonResult:
    def test_valid(self) -> None:
        candidate = BacktestRunResult(
            label=BacktestArmLabel.CANDIDATE,
            success=True,
            metrics=BacktestMetrics(total_return_pct=Decimal("10")),
            stdout="",
            stderr="",
            exit_code=0,
            workspace="/tmp/ws-c",
            result_file="/tmp/ws-c/result.json",
            command=("freqtrade", "backtesting"),
            command_fingerprint="fp-c",
            strategy_sha_before="abc",
            strategy_sha_after="abc",
            fingerprint="fp-rc",
        )
        baseline = BacktestRunResult(
            label=BacktestArmLabel.BASELINE,
            success=True,
            metrics=BacktestMetrics(total_return_pct=Decimal("5")),
            stdout="",
            stderr="",
            exit_code=0,
            workspace="/tmp/ws-b",
            result_file="/tmp/ws-b/result.json",
            command=("freqtrade", "backtesting"),
            command_fingerprint="fp-b",
            strategy_sha_before="abc",
            strategy_sha_after="abc",
            fingerprint="fp-rb",
        )
        comparison = BacktestComparisonResult(
            candidate=candidate,
            baseline=baseline,
            metric_deltas={"total_return_pct": Decimal("5")},
            interpretations={"total_return_pct": MetricInterpretation.CANDIDATE_HIGHER},
            comparison_fingerprint="fp-comp",
            trade_sufficiency=True,
        )
        assert comparison.metric_deltas["total_return_pct"] == Decimal("5")


class TestBacktestFairnessManifest:
    def test_valid(self) -> None:
        manifest = BacktestFairnessManifest(
            strategy_name="TestStrategy",
            strategy_fingerprint="fp-s",
            data_fingerprint="fp-d",
            timeframe="1h",
            timerange="20240101-20240201",
            balance=Decimal("1000"),
            stake=Decimal("100"),
            max_open_trades=3,
            fee=Decimal("0.001"),
            protections=(),
            assumptions_equal=True,
            pairlist_only_difference=("BTC/USDT", ("ETH/USDT",), ()),
            fairness_fingerprint="fp-f",
        )
        assert manifest.assumptions_equal is True


class TestBacktestComparisonManifest:
    def test_valid(self, tmp_path: Path) -> None:
        from datetime import datetime, timezone

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
        assert manifest.spec_version == "SPEC-066"


class TestBacktestComparisonReport:
    def test_valid(self, tmp_path: Path) -> None:
        from datetime import datetime, timezone

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
            timeframe="1h",
            timerange="20240101-20240201",
            balance=Decimal("1000"),
            stake=Decimal("100"),
            max_open_trades=3,
            fee=Decimal("0.001"),
            executable_path=exe,
        )
        candidate = BacktestRunResult(
            label=BacktestArmLabel.CANDIDATE,
            success=True,
            metrics=BacktestMetrics(),
            stdout="",
            stderr="",
            exit_code=0,
            workspace="/tmp/ws-c",
            result_file="/tmp/ws-c/result.json",
            command=("freqtrade", "backtesting"),
            command_fingerprint="fp-c",
            strategy_sha_before="abc",
            strategy_sha_after="abc",
            fingerprint="fp-rc",
        )
        baseline = BacktestRunResult(
            label=BacktestArmLabel.BASELINE,
            success=True,
            metrics=BacktestMetrics(),
            stdout="",
            stderr="",
            exit_code=0,
            workspace="/tmp/ws-b",
            result_file="/tmp/ws-b/result.json",
            command=("freqtrade", "backtesting"),
            command_fingerprint="fp-b",
            strategy_sha_before="abc",
            strategy_sha_after="abc",
            fingerprint="fp-rb",
        )
        comparison = BacktestComparisonResult(
            candidate=candidate,
            baseline=baseline,
            metric_deltas={},
            interpretations={},
            comparison_fingerprint="fp-comp",
            trade_sufficiency=False,
        )
        fairness = BacktestFairnessManifest(
            strategy_name="TestStrategy",
            strategy_fingerprint="fp-s",
            data_fingerprint="fp-d",
            timeframe="1h",
            timerange="20240101-20240201",
            balance=Decimal("1000"),
            stake=Decimal("100"),
            max_open_trades=3,
            fee=Decimal("0.001"),
            protections=(),
            assumptions_equal=True,
            pairlist_only_difference=("BTC/USDT", ("ETH/USDT",), ()),
            fairness_fingerprint="fp-f",
        )
        manifest = BacktestComparisonManifest(
            version="0.65.0-dev",
            spec_version="SPEC-066",
            research_backtest_comparison_version="0.65.0-dev",
            generated_at=datetime.now(timezone.utc),
            config_fingerprint="fp-cfg",
            strategy_fingerprint="fp-s",
            candidate_pairlist_fingerprint="fp-cp",
            baseline_pairlist_fingerprint="fp-bp",
            candidate_result_fingerprint="fp-rc",
            baseline_result_fingerprint="fp-rb",
            comparison_fingerprint="fp-comp",
            safety_flags=ResearchBacktestSafetyFlags(),
            reason_codes=(),
        )
        report = BacktestComparisonReport(
            version="0.65.0-dev",
            spec_version="SPEC-066",
            research_backtest_comparison_version="0.65.0-dev",
            config=config,
            manifest=manifest,
            candidate=candidate,
            baseline=baseline,
            comparison=comparison,
            fairness=fairness,
            safety_flags=ResearchBacktestSafetyFlags(),
            fingerprint="fp-report",
        )
        assert report.research_only is True
        assert report.human_approval_required is True


class TestResearchBacktestComparisonWriterError:
    def test_reason_code(self) -> None:
        err = ResearchBacktestComparisonWriterError("boom", reason_code="X")
        assert err.reason_code == "X"
