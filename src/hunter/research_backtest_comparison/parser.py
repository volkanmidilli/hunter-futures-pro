"""Version-aware parser for Freqtrade backtest exports (MVP-65 / SPEC-066)."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from hunter.research_backtest_comparison.errors import (
    ResearchBacktestComparisonParserError,
)
from hunter.research_backtest_comparison.export_parser import _read_export_json_text
from hunter.research_backtest_comparison.models import (
    MISSING_METRIC,
    NO_TRADES,
    PARSER_ERROR,
    PARSER_VERSION_MISMATCH,
    BacktestMetrics,
    RESEARCH_BACKTEST_COMPARISON_VERSION,
)


# Canonical metric keys that may appear in a structured JSON export.
_STRUCTURED_METRIC_KEYS: frozenset[str] = frozenset(
    {
        "total_return_pct",
        "absolute_profit",
        "final_balance",
        "max_drawdown_pct",
        "sharpe_ratio",
        "sortino_ratio",
        "calmar_ratio",
        "profit_factor",
        "win_rate_pct",
        "trade_count",
        "avg_trade_duration",
        "fees_paid",
    }
)


def _coerce_decimal(value: Any) -> Decimal | None:
    """Coerce a JSON value to Decimal, returning None for missing/unparseable values."""
    if value is None:
        return None
    try:
        if isinstance(value, (int, float, str)):
            return Decimal(str(value))
    except Exception:
        return None
    return None


def _compute_metrics_from_trades(
    trades: list[dict[str, Any]],
    *,
    start_balance: Decimal = Decimal("1000"),
) -> BacktestMetrics:
    """Compute canonical metrics from a list of Freqtrade-style trade dicts.

    This is a fallback for raw Freqtrade exports that contain only trades.
    """
    if not trades:
        # Zero-trade exports are valid evidence; performance metrics
        # remain unavailable instead of being fabricated as zeros.
        return BacktestMetrics(
            trade_count=0,
            reason_codes=(NO_TRADES,),
        )

    profits: list[Decimal] = []
    wins = 0
    durations: list[Decimal] = []
    fees = Decimal("0")
    for trade in trades:
        profit = _coerce_decimal(trade.get("profit", trade.get("profit_abs", 0)))
        profit = profit or Decimal("0")
        profits.append(profit)
        if profit > 0:
            wins += 1
        duration = _coerce_decimal(trade.get("duration", trade.get("trade_duration", 0)))
        durations.append(duration or Decimal("0"))
        fee = _coerce_decimal(trade.get("fee", trade.get("fees", 0)))
        fees += fee or Decimal("0")

    absolute_profit = sum(profits, Decimal("0"))
    final_balance = start_balance + absolute_profit
    total_return_pct = (absolute_profit / start_balance) * Decimal("100") if start_balance else None
    trade_count = len(trades)
    win_rate_pct = (Decimal(wins) / Decimal(trade_count)) * Decimal("100") if trade_count else Decimal("0")
    avg_trade_duration = (sum(durations, Decimal("0")) / Decimal(trade_count)) if trade_count else Decimal("0")

    gross_profit = sum((p for p in profits if p > 0), Decimal("0"))
    gross_loss = sum((abs(p) for p in profits if p < 0), Decimal("0"))
    profit_factor = (gross_profit / gross_loss) if gross_loss else None

    # Drawdown approximation from running balance.
    peak = start_balance
    drawdowns: list[Decimal] = []
    running = start_balance
    for profit in profits:
        running += profit
        if running > peak:
            peak = running
        elif peak > Decimal("0"):
            drawdowns.append((peak - running) / peak * Decimal("100"))
    max_drawdown_pct = max(drawdowns) if drawdowns else Decimal("0")

    return BacktestMetrics(
        total_return_pct=total_return_pct,
        absolute_profit=absolute_profit,
        final_balance=final_balance,
        max_drawdown_pct=max_drawdown_pct,
        sharpe_ratio=None,
        sortino_ratio=None,
        calmar_ratio=None,
        profit_factor=profit_factor,
        win_rate_pct=win_rate_pct,
        trade_count=trade_count,
        avg_trade_duration=avg_trade_duration,
        fees_paid=fees,
        reason_codes=(MISSING_METRIC,) if None in (total_return_pct, profit_factor) else (),
    )


def parse_backtest_result(
    path: str | Path,
    *,
    expected_version: str | None = None,
    start_balance: Decimal = Decimal("1000"),
) -> BacktestMetrics:
    """Parse a Freqtrade backtest export file into canonical metrics.

    Args:
        path: Path to the JSON export file.
        expected_version: Optional parser version to enforce compatibility.
        start_balance: Starting balance for computing metrics from raw trades.

    Returns:
        BacktestMetrics with all available fields; missing fields are None.

    Raises:
        ResearchBacktestComparisonParserError: on parse/version errors.
    """
    result_path = Path(path)
    if not result_path.exists() or not result_path.is_file():
        raise ResearchBacktestComparisonParserError(
            f"result file does not exist: {result_path}", reason_code="RESULT_NOT_FOUND"
        )

    try:
        raw_text = _read_export_json_text(result_path)
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ResearchBacktestComparisonParserError(
            f"failed to parse JSON result: {exc}", reason_code="PARSER_ERROR"
        ) from exc
    except OSError as exc:
        raise ResearchBacktestComparisonParserError(
            f"failed to read result file: {exc}", reason_code="RESULT_NOT_FOUND"
        ) from exc

    if not isinstance(data, dict):
        # Raw Freqtrade export is a list of trades.
        if isinstance(data, list):
            return _compute_metrics_from_trades(data, start_balance=start_balance)
        raise ResearchBacktestComparisonParserError(
            f"unexpected result format: {type(data)}", reason_code="PARSER_ERROR"
        )

    # Version check for structured exports.
    parser_version = data.get("parser_version", RESEARCH_BACKTEST_COMPARISON_VERSION)
    if expected_version is not None and parser_version != expected_version:
        raise ResearchBacktestComparisonParserError(
            f"parser version mismatch: {parser_version} != {expected_version}",
            reason_code=PARSER_VERSION_MISMATCH,
        )

    # If the export contains structured metrics, use them directly.
    if any(k in data for k in _STRUCTURED_METRIC_KEYS):
        metrics = BacktestMetrics(
            total_return_pct=_coerce_decimal(data.get("total_return_pct")),
            absolute_profit=_coerce_decimal(data.get("absolute_profit")),
            final_balance=_coerce_decimal(data.get("final_balance")),
            max_drawdown_pct=_coerce_decimal(data.get("max_drawdown_pct")),
            sharpe_ratio=_coerce_decimal(data.get("sharpe_ratio")),
            sortino_ratio=_coerce_decimal(data.get("sortino_ratio")),
            calmar_ratio=_coerce_decimal(data.get("calmar_ratio")),
            profit_factor=_coerce_decimal(data.get("profit_factor")),
            win_rate_pct=_coerce_decimal(data.get("win_rate_pct")),
            trade_count=data.get("trade_count", 0),
            avg_trade_duration=_coerce_decimal(data.get("avg_trade_duration")),
            fees_paid=_coerce_decimal(data.get("fees_paid")),
            parser_version=parser_version,
        )
        return metrics

    # Otherwise, expect a "trades" list and compute metrics from it.
    trades = data.get("trades")
    if not isinstance(trades, list):
        raise ResearchBacktestComparisonParserError(
            "result contains neither structured metrics nor a trades list",
            reason_code=MISSING_METRIC,
        )
    return _compute_metrics_from_trades(trades, start_balance=start_balance)
