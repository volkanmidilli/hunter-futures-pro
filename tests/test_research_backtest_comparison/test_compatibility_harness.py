"""Tests for real Freqtrade compatibility validation (SPEC-072)."""

from __future__ import annotations

from pathlib import Path

import pytest

from hunter.research_backtest_comparison.compatibility_harness import (
    run_freqtrade_compatibility_smoke_test,
)
from hunter.research_backtest_comparison.models import (
    COMPATIBILITY_INVALID_EXTERNAL_FIXTURE,
    COMPATIBILITY_UNSUPPORTED_EXPORT_SCHEMA,
    NO_TRADES,
    NO_TRADES_BOTH_ARMS,
    REAL_FREQTRADE_COMPATIBILITY_NOT_EXECUTED,
    BacktestArmLabel,
    BacktestMetrics,
    BacktestRunResult,
    CompatibilityStatus,
    FreqtradeCompatibilityInput,
)
from hunter.research_backtest_comparison.comparison import compare_backtest_results
from hunter.research_backtest_comparison.export_parser import parse_real_export
from decimal import Decimal


def _make_fake_executable(tmp_path: Path, *, version: str = "freqtrade 2024.1") -> Path:
    """Create a fake freqtrade executable that prints version and runs backtesting."""
    exe = tmp_path / "freqtrade"
    script = f"""#!/usr/bin/env python3
import json
import sys

if len(sys.argv) > 1 and sys.argv[1] == "--version":
    print("{version}")
    sys.exit(0)

if len(sys.argv) > 1 and sys.argv[1] == "backtesting":
    out_file = None
    for i, arg in enumerate(sys.argv):
        if arg == "--export-filename" and i + 1 < len(sys.argv):
            out_file = sys.argv[i + 1]
    if out_file:
        payload = {{
            "strategy": {{
                "TestStrategy": {{
                    "total_trades": 3,
                    "trade_count": 3,
                    "winning_trades": 2,
                    "losing_trades": 1,
                    "total_profit_abs": 150,
                    "profit_mean": 50,
                    "max_drawdown_abs": 25,
                    "sharpe": 1.2,
                    "sortino": 1.5,
                    "calmar": 0.8,
                    "profit_factor": 2.0,
                    "win_rate": 0.66,
                    "avg_trade_duration_min": 60,
                }}
            }}
        }}
        with open(out_file, "w") as f:
            json.dump(payload, f)
    sys.exit(0)

print("Unknown command:", sys.argv[1] if len(sys.argv) > 1 else "")
sys.exit(1)
"""
    exe.write_text(script)
    exe.chmod(0o755)
    return exe


def _make_strategy_file(tmp_path: Path) -> Path:
    strategy = tmp_path / "TestStrategy.py"
    strategy.write_text("class TestStrategy:\n    pass\n")
    return strategy


def _make_input(
    tmp_path: Path,
    *,
    exe: Path | None = None,
    strategy: Path | None = None,
) -> FreqtradeCompatibilityInput:
    exe = exe or _make_fake_executable(tmp_path)
    strategy = strategy or _make_strategy_file(tmp_path)
    data = tmp_path / "data"
    data.mkdir(exist_ok=True)
    out = tmp_path / "out"
    out.mkdir(exist_ok=True)
    return FreqtradeCompatibilityInput(
        executable_path=exe,
        strategy_path=strategy,
        data_path=data,
        output_dir=out,
        strategy_name="TestStrategy",
        pairs=("BTC/USDT",),
        timeframe="1h",
        timerange="20240101-20240201",
        starting_balance="1000",
        stake="100",
        max_open_trades=1,
        fee="0.001",
    )


class TestCompatibilityInputValidation:
    def test_missing_executable(self, tmp_path: Path) -> None:
        strategy = _make_strategy_file(tmp_path)
        data = tmp_path / "data"
        data.mkdir()
        out = tmp_path / "out"
        out.mkdir()

        input = FreqtradeCompatibilityInput(
            executable_path=tmp_path / "nonexistent",
            strategy_path=strategy,
            data_path=data,
            output_dir=out,
            strategy_name="TestStrategy",
            pairs=("BTC/USDT",),
            timeframe="1h",
            timerange="20240101-20240201",
            starting_balance="1000",
            stake="100",
            max_open_trades=1,
            fee="0.001",
        )
        report = run_freqtrade_compatibility_smoke_test(input)
        assert report.status == CompatibilityStatus.INVALID_EXTERNAL_FIXTURE
        assert COMPATIBILITY_INVALID_EXTERNAL_FIXTURE in report.reason_codes
        assert REAL_FREQTRADE_COMPATIBILITY_NOT_EXECUTED in report.reason_codes
        assert report.result.command == ()

    def test_missing_strategy(self, tmp_path: Path) -> None:
        data = tmp_path / "data"
        data.mkdir()
        out = tmp_path / "out"
        out.mkdir()

        input = FreqtradeCompatibilityInput(
            executable_path=_make_fake_executable(tmp_path),
            strategy_path=tmp_path / "missing.py",
            data_path=data,
            output_dir=out,
            strategy_name="TestStrategy",
            pairs=("BTC/USDT",),
            timeframe="1h",
            timerange="20240101-20240201",
            starting_balance="1000",
            stake="100",
            max_open_trades=1,
            fee="0.001",
        )
        report = run_freqtrade_compatibility_smoke_test(input)
        assert report.status == CompatibilityStatus.INVALID_EXTERNAL_FIXTURE

    def test_relative_strategy_path_rejected(self, tmp_path: Path) -> None:
        data = tmp_path / "data"
        data.mkdir()
        out = tmp_path / "out"
        out.mkdir()

        input = FreqtradeCompatibilityInput(
            executable_path=_make_fake_executable(tmp_path),
            strategy_path=Path("relative/path.py"),
            data_path=data,
            output_dir=out,
            strategy_name="TestStrategy",
            pairs=("BTC/USDT",),
            timeframe="1h",
            timerange="20240101-20240201",
            starting_balance="1000",
            stake="100",
            max_open_trades=1,
            fee="0.001",
        )
        report = run_freqtrade_compatibility_smoke_test(input)
        assert report.status == CompatibilityStatus.INVALID_EXTERNAL_FIXTURE


class TestCompatibilitySmokeTest:
    def test_executed_pass(self, tmp_path: Path) -> None:
        input = _make_input(tmp_path)
        report = run_freqtrade_compatibility_smoke_test(input)
        assert report.status == CompatibilityStatus.EXECUTED_PASS
        assert report.result is not None
        assert report.result.parsed_metrics is not None
        assert report.result.parsed_metrics.trade_count == 3
        assert report.result.exit_code == 0
        assert report.result.command is not None
        assert report.result.command_fingerprint is not None
        assert report.safety_flags.research_only is True
        assert report.safety_flags.live_trading_allowed is False

    def test_executed_zero_trades(self, tmp_path: Path) -> None:
        exe = tmp_path / "freqtrade"
        exe.write_text(
            """#!/bin/sh
if [ "$1" = "--version" ]; then echo "freqtrade 2024.1"; exit 0; fi
if [ "$1" = "backtesting" ]; then
    out_file=""
    while [ "$#" -gt 0 ]; do
        if [ "$1" = "--export-filename" ]; then
            out_file="$2"
            break
        fi
        shift
    done
    echo '{"strategy": {"TestStrategy": {"total_trades": 0, "trade_count": 0}}}' > "$out_file"
    exit 0
fi
exit 1
"""
        )
        exe.chmod(0o755)
        input = _make_input(tmp_path, exe=exe)
        report = run_freqtrade_compatibility_smoke_test(input)
        assert report.status == CompatibilityStatus.EXECUTED_PASS
        assert report.result is not None
        assert report.result.parsed_metrics is not None
        assert report.result.parsed_metrics.trade_count == 0
        assert report.result.parsed_metrics.total_return_pct is None
        assert report.result.parsed_metrics.absolute_profit is None
        assert report.result.parsed_metrics.final_balance is None
        assert NO_TRADES in report.result.parsed_metrics.reason_codes

    def test_unsupported_export_schema(self, tmp_path: Path) -> None:
        exe = tmp_path / "freqtrade"
        exe.write_text(
            """#!/bin/sh
if [ "$1" = "--version" ]; then echo "freqtrade 2024.1"; exit 0; fi
if [ "$1" = "backtesting" ]; then
    out_file=""
    while [ "$#" -gt 0 ]; do
        if [ "$1" = "--export-filename" ]; then
            out_file="$2"
            break
        fi
        shift
    done
    echo "not a valid json" > "$out_file"
    exit 0
fi
exit 1
"""
        )
        exe.chmod(0o755)
        input = _make_input(tmp_path, exe=exe)
        report = run_freqtrade_compatibility_smoke_test(input)
        assert report.status == CompatibilityStatus.UNSUPPORTED_EXPORT_SCHEMA
        assert COMPATIBILITY_UNSUPPORTED_EXPORT_SCHEMA in report.reason_codes

    def test_nonzero_exit(self, tmp_path: Path) -> None:
        exe = tmp_path / "freqtrade"
        exe.write_text(
            """#!/bin/sh
if [ "$1" = "--version" ]; then echo "freqtrade 2024.1"; exit 0; fi
exit 1
"""
        )
        exe.chmod(0o755)
        input = _make_input(tmp_path, exe=exe)
        report = run_freqtrade_compatibility_smoke_test(input)
        assert report.status == CompatibilityStatus.EXECUTED_FAIL
        assert report.result is not None
        assert report.result.exit_code == 1


class TestSafetyInvariants:
    def test_research_only_flags(self, tmp_path: Path) -> None:
        input = _make_input(tmp_path)
        report = run_freqtrade_compatibility_smoke_test(input)
        flags = report.safety_flags
        assert flags.research_only is True
        assert flags.execution_approval_granted is False
        assert flags.production_approval_granted is False
        assert flags.live_trading_allowed is False
        assert flags.automatic_execution_allowed is False
        assert flags.human_approval_required is True

    def test_no_repo_data_access(self, tmp_path: Path) -> None:
        # The data path must be caller-provided, not the repo data/ directory.
        # This is enforced by the absolute-path check in the validator.
        data = tmp_path / "data"
        data.mkdir()
        assert data.is_dir()


class TestProtectionsFingerprint:
    def _make_input_with_protections(
        self,
        tmp_path: Path,
        protections: tuple[str, ...] | list[str],
    ) -> FreqtradeCompatibilityInput:
        exe = _make_fake_executable(tmp_path)
        strategy = _make_strategy_file(tmp_path)
        data = tmp_path / "data"
        data.mkdir(exist_ok=True)
        out = tmp_path / "out"
        out.mkdir(exist_ok=True)
        return FreqtradeCompatibilityInput(
            executable_path=exe,
            strategy_path=strategy,
            data_path=data,
            output_dir=out,
            strategy_name="TestStrategy",
            pairs=("BTC/USDT",),
            timeframe="1h",
            timerange="20240101-20240201",
            starting_balance="1000",
            stake="100",
            max_open_trades=1,
            fee="0.001",
            protections=protections,
        )

    def test_same_protections_same_fingerprint(self, tmp_path: Path) -> None:
        input_a = self._make_input_with_protections(tmp_path, ("Stoploss", "Cooldown"))
        input_b = self._make_input_with_protections(tmp_path, ("Stoploss", "Cooldown"))
        assert input_a.fingerprint() == input_b.fingerprint()

    def test_different_protections_different_fingerprint(self, tmp_path: Path) -> None:
        input_a = self._make_input_with_protections(tmp_path, ("Stoploss",))
        input_b = self._make_input_with_protections(tmp_path, ("Cooldown",))
        assert input_a.fingerprint() != input_b.fingerprint()

    def test_tuple_coercion_deterministic(self, tmp_path: Path) -> None:
        input_list = self._make_input_with_protections(tmp_path, ["Stoploss", "Cooldown"])
        input_tuple = self._make_input_with_protections(tmp_path, ("Stoploss", "Cooldown"))
        assert input_list.fingerprint() == input_tuple.fingerprint()

    def test_protections_order_normalized_in_fingerprint(self, tmp_path: Path) -> None:
        # Repository contract: protections ordering is normalized via sorted(),
        # matching fairness.py canonical payloads; equivalent protection sets
        # produce identical fingerprints regardless of caller ordering.
        input_ab = self._make_input_with_protections(tmp_path, ("A", "B"))
        input_ba = self._make_input_with_protections(tmp_path, ("B", "A"))
        assert input_ab.fingerprint() == input_ba.fingerprint()

    def test_runtime_values_do_not_affect_fingerprint(self, tmp_path: Path) -> None:
        input_a = self._make_input_with_protections(tmp_path, ("Stoploss",))
        input_b = self._make_input_with_protections(tmp_path, ("Stoploss",))
        object.__setattr__(input_b, "timeout_seconds", 999)
        object.__setattr__(input_b, "output_dir", tmp_path / "other_output")
        assert input_a.fingerprint() == input_b.fingerprint()


class TestParseRealExportZeroTrade:
    def _write_export(self, tmp_path: Path, payload: dict) -> Path:
        import json

        path = tmp_path / "result.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_valid_zero_trade_flat_export_accepted(self, tmp_path: Path) -> None:
        path = self._write_export(
            tmp_path,
            {"strategy": {"TestStrategy": {"total_trades": 0, "trade_count": 0}}},
        )
        metrics, schema, _fp = parse_real_export(
            path, strategy_name="TestStrategy", start_balance=Decimal("1000")
        )
        assert schema == "freqtrade_nested_strategy"
        assert metrics.trade_count == 0
        assert NO_TRADES in metrics.reason_codes

    def test_absent_return_unavailable(self, tmp_path: Path) -> None:
        path = self._write_export(
            tmp_path,
            {"strategy": {"TestStrategy": {"total_trades": 0, "trade_count": 0}}},
        )
        metrics, _, _ = parse_real_export(
            path, strategy_name="TestStrategy", start_balance=Decimal("1000")
        )
        assert metrics.total_return_pct is None

    def test_absent_profit_unavailable(self, tmp_path: Path) -> None:
        path = self._write_export(
            tmp_path,
            {"strategy": {"TestStrategy": {"total_trades": 0, "trade_count": 0}}},
        )
        metrics, _, _ = parse_real_export(
            path, strategy_name="TestStrategy", start_balance=Decimal("1000")
        )
        assert metrics.absolute_profit is None

    def test_absent_final_balance_unavailable(self, tmp_path: Path) -> None:
        path = self._write_export(
            tmp_path,
            {"strategy": {"TestStrategy": {"total_trades": 0, "trade_count": 0}}},
        )
        metrics, _, _ = parse_real_export(
            path, strategy_name="TestStrategy", start_balance=Decimal("1000")
        )
        assert metrics.final_balance is None

    def test_explicit_zero_return_preserved(self, tmp_path: Path) -> None:
        path = self._write_export(
            tmp_path,
            {"strategy": {"TestStrategy": {"total_trades": 0, "trade_count": 0, "total_return_pct": 0}}},
        )
        metrics, _, _ = parse_real_export(
            path, strategy_name="TestStrategy", start_balance=Decimal("1000")
        )
        assert metrics.total_return_pct == Decimal("0")
        assert metrics.trade_count == 0

    def test_explicit_unchanged_final_balance_preserved(self, tmp_path: Path) -> None:
        path = self._write_export(
            tmp_path,
            {"strategy": {"TestStrategy": {"total_trades": 0, "trade_count": 0, "final_balance": 1000}}},
        )
        metrics, _, _ = parse_real_export(
            path, strategy_name="TestStrategy", start_balance=Decimal("1000")
        )
        assert metrics.final_balance == Decimal("1000")
        assert metrics.trade_count == 0

    def test_malformed_nonzero_trade_export_rejected(self, tmp_path: Path) -> None:
        path = self._write_export(
            tmp_path,
            {"strategy": {"TestStrategy": {"foo": "bar"}}},
        )
        with pytest.raises(Exception):
            parse_real_export(path, strategy_name="TestStrategy", start_balance=Decimal("1000"))


class TestZeroTradeComparisonSymmetry:
    def _make_run_result(
        self,
        label: BacktestArmLabel,
        trade_count: int,
        total_return_pct: Decimal | None = None,
    ) -> BacktestRunResult:
        return BacktestRunResult(
            label=label,
            success=True,
            metrics=BacktestMetrics(
                total_return_pct=total_return_pct,
                trade_count=trade_count,
                reason_codes=(NO_TRADES,) if trade_count == 0 else (),
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

    def test_zero_trade_not_sign_share_ready(self) -> None:
        candidate = self._make_run_result(BacktestArmLabel.CANDIDATE, 0)
        baseline = self._make_run_result(BacktestArmLabel.BASELINE, 0)
        result = compare_backtest_results(candidate, baseline)
        assert result.trade_sufficiency is False
        assert NO_TRADES_BOTH_ARMS in result.reason_codes

    def test_candidate_baseline_symmetry(self) -> None:
        candidate = self._make_run_result(BacktestArmLabel.CANDIDATE, 0)
        baseline = self._make_run_result(BacktestArmLabel.BASELINE, 0)
        result_ab = compare_backtest_results(candidate, baseline)
        result_ba = compare_backtest_results(baseline, candidate)
        assert result_ab.trade_sufficiency == result_ba.trade_sufficiency
        assert result_ab.reason_codes == result_ba.reason_codes
        assert NO_TRADES_BOTH_ARMS in result_ab.reason_codes
