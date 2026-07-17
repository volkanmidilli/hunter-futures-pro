"""Security and safety edge-case tests (MVP-65 Stage 7)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from hunter.research_backtest_comparison import (
    BacktestArmInput,
    BacktestArmLabel,
    BacktestComparisonConfig,
    run_research_backtest_comparison,
)
from hunter.research_backtest_comparison.command_builder import build_backtest_command
from hunter.research_backtest_comparison.errors import (
    ResearchBacktestComparisonValidationError,
)
from hunter.research_backtest_comparison.runner import _build_env
from hunter.research_backtest_comparison.workspace import create_workspace


def _write_fake_executable(tmp_path: Path) -> Path:
    exe = tmp_path / "freqtrade"
    exe.write_text(
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
        "    'fees_paid': '0'\n"
        "}\n"
        "with open(out, 'w') as f:\n"
        "    json.dump(payload, f)\n"
        "sys.exit(0)\n"
    )
    exe.chmod(0o755)
    return exe


class TestForbiddenSubcommands:
    def test_command_builder_rejects_trade(self, tmp_path: Path) -> None:
        (tmp_path / "strategy.py").write_text("# strategy")
        (tmp_path / "data").mkdir()
        config = BacktestComparisonConfig(
            strategy_name="trade",
            strategy_path=tmp_path / "strategy.py",
            data_path=tmp_path / "data",
            timeframe="1h",
            timerange="20240101-20240201",
            balance=Decimal("1000"),
            stake=Decimal("100"),
            max_open_trades=3,
            fee=Decimal("0.001"),
            executable_path=tmp_path / "freqtrade",
        )
        ws = create_workspace(prefix="test_forbidden_")
        ws.create()
        try:
            with pytest.raises(ResearchBacktestComparisonValidationError):
                build_backtest_command(config, ws)
        finally:
            ws.cleanup(force=True)

    def test_engine_command_is_backtesting(self, tmp_path: Path) -> None:
        exe = _write_fake_executable(tmp_path)
        (tmp_path / "strategy.py").write_text("# strategy")
        (tmp_path / "data").mkdir()
        config = BacktestComparisonConfig(
            strategy_name="TestStrategy",
            strategy_path=tmp_path / "strategy.py",
            data_path=tmp_path / "data",
            timeframe="1h",
            timerange="20240101-20240201",
            balance=Decimal("1000"),
            stake=Decimal("100"),
            max_open_trades=3,
            fee=Decimal("0.001"),
            executable_path=exe,
            timeout_seconds=5,
            retain_workspace_on_failure=False,
        )
        candidate = BacktestArmInput(
            pairlist=("BTC/USDT",),
            label=BacktestArmLabel.CANDIDATE,
            universe_fingerprint="fp-c",
        )
        baseline = BacktestArmInput(
            pairlist=("BTC/USDT",),
            label=BacktestArmLabel.BASELINE,
            universe_fingerprint="fp-b",
        )
        report = run_research_backtest_comparison(
            config=config,
            candidate=candidate,
            baseline=baseline,
        )
        assert "backtesting" in report.candidate.command
        assert "backtesting" in report.baseline.command


class TestShellInjection:
    def test_engine_rejects_shell_metacharacter(self, tmp_path: Path) -> None:
        exe = _write_fake_executable(tmp_path)
        (tmp_path / "strategy.py").write_text("# strategy")
        (tmp_path / "data").mkdir()
        config = BacktestComparisonConfig(
            strategy_name="Test; rm -rf /",
            strategy_path=tmp_path / "strategy.py",
            data_path=tmp_path / "data",
            timeframe="1h",
            timerange="20240101-20240201",
            balance=Decimal("1000"),
            stake=Decimal("100"),
            max_open_trades=3,
            fee=Decimal("0.001"),
            executable_path=exe,
            timeout_seconds=5,
        )
        candidate = BacktestArmInput(
            pairlist=("BTC/USDT",),
            label=BacktestArmLabel.CANDIDATE,
            universe_fingerprint="fp-c",
        )
        baseline = BacktestArmInput(
            pairlist=("BTC/USDT",),
            label=BacktestArmLabel.BASELINE,
            universe_fingerprint="fp-b",
        )
        with pytest.raises(ResearchBacktestComparisonValidationError):
            run_research_backtest_comparison(
                config=config,
                candidate=candidate,
                baseline=baseline,
            )


class TestSecretEnv:
    def test_secret_stripped(self, tmp_path: Path) -> None:
        config = BacktestComparisonConfig(
            strategy_name="TestStrategy",
            strategy_path=tmp_path / "strategy.py",
            data_path=tmp_path / "data",
            timeframe="1h",
            timerange="20240101-20240201",
            balance=Decimal("1000"),
            stake=Decimal("100"),
            max_open_trades=3,
            fee=Decimal("0.001"),
            executable_path=tmp_path / "freqtrade",
            extra_env={"MY_API_KEY": "secret123", "PATH": "/usr/bin"},
        )
        (tmp_path / "strategy.py").write_text("# strategy")
        (tmp_path / "data").mkdir()
        env = _build_env(config)
        assert "MY_API_KEY" not in env
        assert env.get("TZ") == "UTC"
        assert "PATH" in env


class TestStrategyMutation:
    def test_mutation_detected(self, tmp_path: Path) -> None:
        strategy = tmp_path / "strategy.py"
        strategy.write_text("# strategy")
        data = tmp_path / "data"
        data.mkdir()
        exe = tmp_path / "freqtrade"
        exe.write_text(
            "#!/usr/bin/env python3\n"
            "import sys, json\n"
            "if '--version' in sys.argv:\n"
            "    print('freqtrade 2024.1')\n"
            "    sys.exit(0)\n"
            f"with open({str(strategy)!r}, 'a') as f:\n"
            "    f.write('mutated')\n"
            "try:\n"
            "    idx = sys.argv.index('--export-filename')\n"
            "    out = sys.argv[idx + 1]\n"
            "except (ValueError, IndexError):\n"
            "    out = 'backtest_result.json'\n"
            "with open(out, 'w') as f: json.dump({'trades': []}, f)\n"
            "sys.exit(0)\n"
        )
        exe.chmod(0o755)
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
            timeout_seconds=5,
            retain_workspace_on_failure=False,
        )
        candidate = BacktestArmInput(
            pairlist=("BTC/USDT",),
            label=BacktestArmLabel.CANDIDATE,
            universe_fingerprint="fp-c",
        )
        baseline = BacktestArmInput(
            pairlist=("BTC/USDT",),
            label=BacktestArmLabel.BASELINE,
            universe_fingerprint="fp-b",
        )
        report = run_research_backtest_comparison(
            config=config,
            candidate=candidate,
            baseline=baseline,
        )
        assert not (report.candidate.success and report.baseline.success)


class TestDeterminism:
    def test_same_inputs_same_fingerprint(self, tmp_path: Path) -> None:
        exe = _write_fake_executable(tmp_path)
        strategy = tmp_path / "strategy.py"
        strategy.write_text("# strategy")
        data = tmp_path / "data"
        data.mkdir()
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
        report1 = run_research_backtest_comparison(
            config=config,
            candidate=candidate,
            baseline=baseline,
        )
        report2 = run_research_backtest_comparison(
            config=config,
            candidate=candidate,
            baseline=baseline,
        )
        assert report1.fingerprint == report2.fingerprint
