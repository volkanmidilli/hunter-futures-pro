"""Tests for top-level engine (MVP-65 Stage 5)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from hunter.research_backtest_comparison.engine import run_research_backtest_comparison
from hunter.research_backtest_comparison.models import (
    BacktestArmInput,
    BacktestArmLabel,
    BacktestComparisonConfig,
)


def _make_config(tmp_path: Path) -> BacktestComparisonConfig:
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
        "    'total_return_pct': '5.0',\n"
        "    'absolute_profit': '50',\n"
        "    'final_balance': '1050',\n"
        "    'max_drawdown_pct': '2.0',\n"
        "    'sharpe_ratio': '1.5',\n"
        "    'sortino_ratio': '2.0',\n"
        "    'calmar_ratio': '2.5',\n"
        "    'profit_factor': '1.2',\n"
        "    'win_rate_pct': '60',\n"
        "    'trade_count': 10,\n"
        "    'avg_trade_duration': '120',\n"
        "    'fees_paid': '5'\n"
        "}\n"
        "with open(out, 'w') as f:\n"
        "    json.dump(payload, f)\n"
        "sys.exit(0)\n"
    )
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
        retain_workspace_on_failure=False,
    )


class TestRunResearchBacktestComparison:
    def test_end_to_end(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path)
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
        assert report.research_only is True
        assert report.human_approval_required is True
        assert report.candidate.success is True
        assert report.baseline.success is True
        assert report.comparison.candidate.metrics.trade_count == 10
        assert report.fairness.assumptions_equal is True
        assert len(report.fingerprint) == 64
