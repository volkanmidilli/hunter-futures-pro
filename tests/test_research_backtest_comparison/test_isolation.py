"""Workspace isolation and edge-case tests (MVP-65 Stage 8)."""

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
from hunter.research_backtest_comparison.workspace import (
    BacktestWorkspace,
    create_workspace,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _write_fake_executable(tmp_path: Path) -> Path:
    exe = tmp_path / "freqtrade"
    exe.write_text(
        "#!/usr/bin/env python3\n"
        "import sys, json, os, zipfile\n"
        "if '--version' in sys.argv:\n"
        "    print('freqtrade 2024.1')\n"
        "    sys.exit(0)\n"
        "if sys.argv[1:2] != ['backtesting']:\n"
        "    print('forbidden', file=sys.stderr)\n"
        "    sys.exit(1)\n"
        "out_dir = sys.argv[sys.argv.index('--backtest-directory') + 1]\n"
        "os.makedirs(out_dir, exist_ok=True)\n"
        "stem = 'backtest-result-test'\n"
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
        "with zipfile.ZipFile(os.path.join(out_dir, stem + '.zip'), 'w') as zf:\n"
        "    zf.writestr(stem + '.json', json.dumps(payload))\n"
        "with open(os.path.join(out_dir, '.last_result.json'), 'w') as f:\n"
        "    json.dump({'latest_backtest': stem + '.zip'}, f)\n"
        "sys.exit(0)\n"
    )
    exe.chmod(0o755)
    return exe


class TestWorkspaceIsolation:
    def test_candidate_and_baseline_workspaces_different(self, tmp_path: Path) -> None:
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
            pairlist=("BTC/USDT", "ETH/USDT"),
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
        assert report.candidate.workspace != report.baseline.workspace

    def test_workspace_outside_repo(self) -> None:
        ws = create_workspace(prefix="test_outside_")
        ws.create()
        try:
            assert ws.path.is_absolute()
            # Project root is not a parent of the workspace.
            assert not str(ws.path).startswith(str(_REPO_ROOT))
        finally:
            ws.cleanup(force=True)

    def test_workspaces_not_reused(self) -> None:
        ws1 = create_workspace(prefix="test_reuse_")
        ws1.create()
        ws2 = create_workspace(prefix="test_reuse_")
        ws2.create()
        try:
            assert ws1.path != ws2.path
        finally:
            ws1.cleanup(force=True)
            ws2.cleanup(force=True)


class TestZeroTrades:
    def test_zero_trades_valid_insufficient(self, tmp_path: Path) -> None:
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
            pairlist=("BTC/USDT", "ETH/USDT"),
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
        assert report.candidate.success is True
        assert report.baseline.success is True
        assert report.comparison.trade_sufficiency is False


class TestLargePairlist:
    def test_many_pairs(self, tmp_path: Path) -> None:
        exe = _write_fake_executable(tmp_path)
        (tmp_path / "strategy.py").write_text("# strategy")
        (tmp_path / "data").mkdir()
        pairs = tuple(f"COIN{i}/USDT" for i in range(50))
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
            pairlist=pairs,
            label=BacktestArmLabel.CANDIDATE,
            universe_fingerprint="fp-c",
        )
        baseline = BacktestArmInput(
            pairlist=pairs[:25],
            label=BacktestArmLabel.BASELINE,
            universe_fingerprint="fp-b",
        )
        report = run_research_backtest_comparison(
            config=config,
            candidate=candidate,
            baseline=baseline,
        )
        assert report.candidate.success is True
        assert report.baseline.success is True
        assert report.comparison.candidate.metrics.trade_count >= 0


class TestWorkspaceCleanup:
    def test_cleanup_on_success(self, tmp_path: Path) -> None:
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
        assert not report.candidate.workspace.exists()
        assert not report.baseline.workspace.exists()
