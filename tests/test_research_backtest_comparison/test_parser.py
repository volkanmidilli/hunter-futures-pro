"""Tests for backtest result parser (MVP-65 Stage 4)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from hunter.research_backtest_comparison.errors import (
    ResearchBacktestComparisonParserError,
)
from hunter.research_backtest_comparison.models import (
    RESEARCH_BACKTEST_COMPARISON_VERSION,
    BacktestMetrics,
)
from hunter.research_backtest_comparison.parser import parse_backtest_result


class TestParseBacktestResult:
    def test_structured_metrics(self, tmp_path: Path) -> None:
        result = tmp_path / "result.json"
        result.write_text(
            "{\n"
            '  "trades": [],\n'
            '  "total_return_pct": "10.5",\n'
            '  "absolute_profit": "105",\n'
            '  "final_balance": "1105",\n'
            '  "max_drawdown_pct": "5.2",\n'
            '  "sharpe_ratio": "1.2",\n'
            '  "sortino_ratio": "1.5",\n'
            '  "calmar_ratio": "2.0",\n'
            '  "profit_factor": "1.3",\n'
            '  "win_rate_pct": "55.5",\n'
            '  "trade_count": 10,\n'
            '  "avg_trade_duration": "120",\n'
            '  "fees_paid": "5"\n'
            "}\n"
        )
        metrics = parse_backtest_result(result)
        assert metrics.total_return_pct == Decimal("10.5")
        assert metrics.absolute_profit == Decimal("105")
        assert metrics.trade_count == 10

    def test_raw_trades_list(self, tmp_path: Path) -> None:
        result = tmp_path / "result.json"
        trades = [
            {"profit": 10, "duration": 60, "fee": 1},
            {"profit": -5, "duration": 30, "fee": 1},
        ]
        import json

        result.write_text(json.dumps(trades))
        metrics = parse_backtest_result(result)
        assert metrics.trade_count == 2
        assert metrics.absolute_profit == Decimal("5")
        assert metrics.win_rate_pct == Decimal("50")

    def test_zero_trades(self, tmp_path: Path) -> None:
        result = tmp_path / "result.json"
        result.write_text('{"trades": []}')
        metrics = parse_backtest_result(result)
        assert metrics.trade_count == 0
        assert metrics.total_return_pct == Decimal("0")

    def test_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(ResearchBacktestComparisonParserError):
            parse_backtest_result(tmp_path / "missing.json")

    def test_invalid_json(self, tmp_path: Path) -> None:
        result = tmp_path / "result.json"
        result.write_text("not json")
        with pytest.raises(ResearchBacktestComparisonParserError):
            parse_backtest_result(result)

    def test_unexpected_format(self, tmp_path: Path) -> None:
        result = tmp_path / "result.json"
        result.write_text('{"unknown": 1}')
        with pytest.raises(ResearchBacktestComparisonParserError):
            parse_backtest_result(result)

    def test_version_mismatch(self, tmp_path: Path) -> None:
        result = tmp_path / "result.json"
        result.write_text('{"parser_version": "0.1.0", "total_return_pct": "1"}')
        with pytest.raises(ResearchBacktestComparisonParserError):
            parse_backtest_result(result, expected_version="9.9.9")

    def test_unavailable_metrics(self, tmp_path: Path) -> None:
        result = tmp_path / "result.json"
        result.write_text('{"trades": [{"profit": 1}]}')
        metrics = parse_backtest_result(result)
        assert metrics.sharpe_ratio is None
        assert metrics.sortino_ratio is None
