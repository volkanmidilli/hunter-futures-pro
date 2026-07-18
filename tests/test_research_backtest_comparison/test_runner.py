"""Tests for sequential runner (MVP-65 Stage 3)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from hunter.research_backtest_comparison.models import (
    BacktestArmInput,
    BacktestArmLabel,
    BacktestComparisonConfig,
    NONZERO_EXIT,
    TIMEOUT,
)
from hunter.research_backtest_comparison.runner import (
    _file_sha256,
    run_backtest_arm,
    run_candidate_and_baseline,
)
from hunter.research_backtest_comparison.workspace import create_workspace


def _make_config(tmp_path: Path) -> BacktestComparisonConfig:
    strategy = tmp_path / "strategy.py"
    strategy.write_text("# strategy")
    data = tmp_path / "data"
    data.mkdir()
    exe = tmp_path / "freqtrade"
    exe.write_text("#!/usr/bin/env python3\nimport sys\nsys.exit(0)")
    exe.chmod(0o755)
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
        timeout_seconds=5,
    )


def _fake_freqtrade_script() -> str:
    return (
        "#!/usr/bin/env python3\n"
        "import sys, json\n"
        "if '--version' in sys.argv:\n"
        "    print('freqtrade 2024.1')\n"
        "    sys.exit(0)\n"
        "if sys.argv[1:2] != ['backtesting']:\n"
        "    print('forbidden', file=sys.stderr)\n"
        "    sys.exit(1)\n"
        "try:\n"
        "    idx = sys.argv.index('--export-filename')\n"
        "    out = sys.argv[idx + 1]\n"
        "except (ValueError, IndexError):\n"
        "    out = 'backtest_result.json'\n"
        "payload = {\n"
        "    'trades': [],\n"
        "    'total_return_pct': '0.0',\n"
        "    'absolute_profit': '0',\n"
        "    'final_balance': '1000',\n"
        "    'max_drawdown_pct': '0',\n"
        "    'sharpe_ratio': '0',\n"
        "    'sortino_ratio': '0',\n"
        "    'calmar_ratio': '0',\n"
        "    'profit_factor': '1',\n"
        "    'win_rate_pct': '0',\n"
        "    'trade_count': 0,\n"
        "    'avg_trade_duration': '0',\n"
        "    'fees_paid': '0',\n"
        "}\n"
        "with open(out, 'w') as f:\n"
        "    json.dump(payload, f)\n"
        "sys.exit(0)\n"
    )


def _write_fake_executable(
    tmp_path: Path,
    script: str | None = None,
    name: str = "freqtrade",
) -> Path:
    exe = tmp_path / name
    exe.write_text(script or _fake_freqtrade_script())
    exe.chmod(0o755)
    return exe


class TestFileSha256:
    def test_sha256(self, tmp_path: Path) -> None:
        strategy = tmp_path / "strategy.py"
        strategy.write_text("hello")
        h1 = _file_sha256(strategy)
        h2 = _file_sha256(strategy)
        assert h1 == h2
        assert len(h1) == 64


class TestRunBacktestArm:
    def test_success(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
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
            executable_path=_write_fake_executable(tmp_path),
            timeout_seconds=5,
        )
        arm = BacktestArmInput(
            pairlist=("BTC/USDT",),
            label=BacktestArmLabel.CANDIDATE,
            universe_fingerprint="fp",
        )
        ws = create_workspace(prefix="test_run_")
        ws.create()
        try:
            result = run_backtest_arm(config, arm, ws)
            assert result.success is True
            assert result.exit_code == 0
            assert result.strategy_sha_before == result.strategy_sha_after
            assert result.result_file is not None
            assert result.result_file.exists()
        finally:
            ws.cleanup(force=True)

    def test_nonzero_exit(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        script = "#!/usr/bin/env python3\nimport sys\nprint('error', file=sys.stderr)\nsys.exit(1)\n"
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
            executable_path=_write_fake_executable(tmp_path, script),
            timeout_seconds=5,
        )
        arm = BacktestArmInput(
            pairlist=("BTC/USDT",),
            label=BacktestArmLabel.CANDIDATE,
            universe_fingerprint="fp",
        )
        result = run_backtest_arm(config, arm)
        assert result.success is False
        assert result.exit_code == 1
        assert NONZERO_EXIT in result.reason_codes

    def test_timeout(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        script = "#!/usr/bin/env python3\nimport time, sys\ntime.sleep(10)\nsys.exit(0)\n"
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
            executable_path=_write_fake_executable(tmp_path, script),
            timeout_seconds=1,
        )
        arm = BacktestArmInput(
            pairlist=("BTC/USDT",),
            label=BacktestArmLabel.CANDIDATE,
            universe_fingerprint="fp",
        )
        result = run_backtest_arm(config, arm)
        assert result.success is False
        assert TIMEOUT in result.reason_codes

    def test_strategy_mutation(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
        strategy = tmp_path / "strategy.py"
        script = (
            "#!/usr/bin/env python3\n"
            "import sys\n"
            f"with open({str(strategy)!r}, 'a') as f:\n"
            "    f.write('mutated')\n"
            "sys.exit(0)\n"
        )
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
            executable_path=_write_fake_executable(tmp_path, script),
            timeout_seconds=5,
        )
        arm = BacktestArmInput(
            pairlist=("BTC/USDT",),
            label=BacktestArmLabel.CANDIDATE,
            universe_fingerprint="fp",
        )
        result = run_backtest_arm(config, arm)
        assert result.success is False


class TestRunCandidateAndBaseline:
    def test_sequential(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
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
            executable_path=_write_fake_executable(tmp_path),
            timeout_seconds=5,
            retain_workspace_on_failure=False,
        )
        candidate = BacktestArmInput(
            pairlist=("BTC/USDT", "ETH/USDT"),
            label=BacktestArmLabel.CANDIDATE,
            universe_fingerprint="fp-c",
        )
        baseline = BacktestArmInput(
            pairlist=("BTC/USDT",),
            label=BacktestArmLabel.BASELINE,
            universe_fingerprint="fp-b",
        )
        c_result, b_result = run_candidate_and_baseline(config, candidate, baseline)
        assert c_result.success is True
        assert b_result.success is True
        assert c_result.label == BacktestArmLabel.CANDIDATE
        assert b_result.label == BacktestArmLabel.BASELINE
        # Workspaces are retained on success so the caller can parse results.
        assert c_result.workspace.exists()
        assert b_result.workspace.exists()
        assert c_result.result_file is not None
        assert b_result.result_file is not None
        assert c_result.result_file.exists()
        assert b_result.result_file.exists()
