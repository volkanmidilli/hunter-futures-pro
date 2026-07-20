"""Integration tests for the research backtest comparison harness (MVP-65 Stage 6)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from hunter.research_backtest_comparison import (
    BacktestArmInput,
    BacktestArmLabel,
    BacktestComparisonConfig,
    run_research_backtest_comparison,
    write_all_backtest_comparison_artifacts,
)
from hunter.research_backtest_comparison.models import (
    ResearchBacktestComparisonValidationError,
)


def _write_fake_executable(tmp_path: Path, candidate_return: str, baseline_return: str) -> Path:
    """Write a Python fake Freqtrade that returns different metrics per pairlist."""
    exe = tmp_path / "freqtrade"
    script = (
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
        "# Read config to determine pairlist via simple heuristic: pair_whitelist\n"
        "try:\n"
        "    cidx = sys.argv.index('--config')\n"
        "    cfg_path = sys.argv[cidx + 1]\n"
        "    with open(cfg_path) as f:\n"
        "        cfg = json.load(f)\n"
        "    pairs = cfg.get('exchange', {}).get('pair_whitelist', ['BTC/USDT'])\n"
        "except Exception:\n"
        "    pairs = ['BTC/USDT']\n"
        "mode = 'candidate' if len(pairs) > 1 else 'baseline'\n"
        f"total_return = {candidate_return!r} if mode == 'candidate' else {baseline_return!r}\n"
        "payload = {\n"
        "    'trades': [{'profit': 1} for _ in range(10)],\n"
        "    'total_return_pct': total_return,\n"
        "    'absolute_profit': str(float(total_return) * 10),\n"
        "    'final_balance': str(1000 + float(total_return) * 10),\n"
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
        "with zipfile.ZipFile(os.path.join(out_dir, stem + '.zip'), 'w') as zf:\n"
        "    zf.writestr(stem + '.json', json.dumps(payload))\n"
        "with open(os.path.join(out_dir, '.last_result.json'), 'w') as f:\n"
        "    json.dump({'latest_backtest': stem + '.zip'}, f)\n"
        "sys.exit(0)\n"
    )
    exe.write_text(script)
    exe.chmod(0o755)
    return exe


class TestIntegration:
    def _make_config(self, tmp_path: Path, candidate_return: str, baseline_return: str) -> BacktestComparisonConfig:
        strategy = tmp_path / "strategy.py"
        strategy.write_text("# strategy")
        data = tmp_path / "data"
        data.mkdir()
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
            executable_path=_write_fake_executable(tmp_path, candidate_return, baseline_return),
            timeout_seconds=5,
            retain_workspace_on_failure=False,
        )

    def test_candidate_better(self, tmp_path: Path) -> None:
        config = self._make_config(tmp_path, "10.0", "5.0")
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
        assert report.comparison.candidate.metrics.total_return_pct == Decimal("10.0")
        assert report.comparison.baseline.metrics.total_return_pct == Decimal("5.0")
        delta = report.comparison.metric_deltas["total_return_pct"]
        assert delta == Decimal("5.0")
        from hunter.research_backtest_comparison.models import MetricInterpretation
        assert report.comparison.interpretations["total_return_pct"] == MetricInterpretation.CANDIDATE_HIGHER

    def test_baseline_better(self, tmp_path: Path) -> None:
        config = self._make_config(tmp_path, "3.0", "7.0")
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
        from hunter.research_backtest_comparison.models import MetricInterpretation
        assert report.comparison.interpretations["total_return_pct"] == MetricInterpretation.BASELINE_HIGHER

    def test_artifacts_written(self, tmp_path: Path) -> None:
        config = self._make_config(tmp_path, "10.0", "5.0")
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
        output_dir = tmp_path / "reports"
        data_dir = tmp_path / "data"
        paths = write_all_backtest_comparison_artifacts(
            report,
            output_dir=output_dir,
            data_dir=data_dir,
        )
        assert all(p.exists() for p in paths.values())
        assert paths["report"].exists()
        assert paths["manifest"].exists()

    def test_rejects_wrong_labels(self, tmp_path: Path) -> None:
        config = self._make_config(tmp_path, "10.0", "5.0")
        candidate = BacktestArmInput(
            pairlist=("BTC/USDT", "ETH/USDT"),
            label=BacktestArmLabel.BASELINE,
            universe_fingerprint="fp-c",
        )
        baseline = BacktestArmInput(
            pairlist=("BTC/USDT",),
            label=BacktestArmLabel.CANDIDATE,
            universe_fingerprint="fp-b",
        )
        with pytest.raises(ResearchBacktestComparisonValidationError):
            run_research_backtest_comparison(
                config=config,
                candidate=candidate,
                baseline=baseline,
            )

    def test_report_safety_flags(self, tmp_path: Path) -> None:
        config = self._make_config(tmp_path, "10.0", "5.0")
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
        assert report.safety_flags.research_only is True
        assert report.safety_flags.execution_approval_granted is False
        assert report.safety_flags.production_approval_granted is False
        assert report.safety_flags.live_trading_allowed is False
        assert report.safety_flags.automatic_execution_allowed is False
        assert report.safety_flags.human_approval_required is True
        assert report.safety_flags.no_freqtrade_runtime_connection is False
