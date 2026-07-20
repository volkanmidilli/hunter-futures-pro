"""Real Freqtrade export parser (SPEC-072).

Supports nested strategy result containers, flat metric exports, and raw trade
lists. Locates the requested strategy class, validates the schema, preserves
unavailable metrics, and computes raw export fingerprints.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from decimal import Decimal
from pathlib import Path
from typing import Any

from hunter.research_backtest_comparison.errors import (
    ResearchBacktestComparisonParserError,
)
from hunter.research_backtest_comparison.models import (
    COMPATIBILITY_UNSUPPORTED_EXPORT_SCHEMA,
    MISSING_METRIC,
    NO_TRADES,
    PARSER_ERROR,
    PARSER_VERSION_MISMATCH,
    UNAVAILABLE,
    BacktestMetrics,
    RESEARCH_BACKTEST_COMPARISON_VERSION,
)


# Canonical metric keys emitted by Freqtrade nested strategy results.
# These are taken from Freqtrade backtest output structure.
_FREQTRADE_NESTED_METRIC_KEYS: frozenset[str] = frozenset(
    {
        "total_profit_abs",
        "total_profit_ratio",
        "profit_mean",
        "profit_mean_pct",
        "profit_sum",
        "profit_sum_pct",
        "winning_trades",
        "losing_trades",
        "total_trades",
        "trade_count",
        "max_drawdown_abs",
        "max_drawdown_account",
        "sharpe",
        "sortino",
        "calmar",
        "profit_factor",
        "win_rate",
        "avg_trade_duration_min",
        "avg_trade_duration",
        "trades",
    }
)

# Canonical metric keys used in Hunter structured JSON exports.
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

_SCHEMA_NAMES: tuple[str, ...] = (
    "freqtrade_nested_strategy",
    "freqtrade_flat_metrics",
    "freqtrade_trades_list",
    "hunter_structured_metrics",
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


def _read_export_json_text(result_path: Path) -> str:
    """Return the raw JSON stats text for a Freqtrade export.

    Modern Freqtrade backtesting writes a ``.zip`` archive (member named
    ``<archive-stem>.json``) rather than a flat JSON file. When *result_path*
    is a ``.zip``, extract and decode that member; otherwise read the file
    directly (back-compatible with flat-JSON exports and synthetic fixtures).
    """
    if result_path.suffix == ".zip":
        member_name = f"{result_path.stem}.json"
        try:
            with zipfile.ZipFile(result_path) as zf:
                if member_name not in zf.namelist():
                    raise ResearchBacktestComparisonParserError(
                        f"export zip does not contain expected member: {member_name}",
                        reason_code=COMPATIBILITY_UNSUPPORTED_EXPORT_SCHEMA,
                    )
                return zf.read(member_name).decode("utf-8")
        except zipfile.BadZipFile as exc:
            raise ResearchBacktestComparisonParserError(
                f"export file is not a valid zip archive: {exc}",
                reason_code=COMPATIBILITY_UNSUPPORTED_EXPORT_SCHEMA,
            ) from exc
    return result_path.read_text(encoding="utf-8")


def raw_export_fingerprint(path: str | Path) -> str:
    """Return the SHA-256 fingerprint of the raw export file."""
    result_path = Path(path)
    h = hashlib.sha256()
    with open(result_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _detect_export_schema(data: Any) -> str | None:
    """Detect the export container schema from the parsed JSON structure."""
    if not isinstance(data, dict):
        if isinstance(data, list):
            return "freqtrade_trades_list"
        return None

    if "strategy" in data:
        strategy_value = data["strategy"]
        if isinstance(strategy_value, dict):
            return "freqtrade_nested_strategy"
        if isinstance(strategy_value, str):
            return "freqtrade_nested_strategy"
    if any(k in data for k in _FREQTRADE_NESTED_METRIC_KEYS):
        return "freqtrade_flat_metrics"
    if any(k in data for k in _STRUCTURED_METRIC_KEYS):
        return "hunter_structured_metrics"
    if "trades" in data and isinstance(data["trades"], list):
        return "freqtrade_trades_list"
    return None


def detect_export_schema(path: str | Path) -> str:
    """Detect the schema of a JSON export file.

    Raises:
        ResearchBacktestComparisonParserError: if the schema is unsupported.
    """
    result_path = Path(path)
    if not result_path.exists() or not result_path.is_file():
        raise ResearchBacktestComparisonParserError(
            f"export file not found: {result_path}",
            reason_code=COMPATIBILITY_UNSUPPORTED_EXPORT_SCHEMA,
        )
    try:
        text = _read_export_json_text(result_path)
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ResearchBacktestComparisonParserError(
            f"export file is not valid JSON: {exc}",
            reason_code=COMPATIBILITY_UNSUPPORTED_EXPORT_SCHEMA,
        ) from exc
    except OSError as exc:
        raise ResearchBacktestComparisonParserError(
            f"failed to read export file: {exc}",
            reason_code=COMPATIBILITY_UNSUPPORTED_EXPORT_SCHEMA,
        ) from exc

    schema = _detect_export_schema(data)
    if schema is None:
        raise ResearchBacktestComparisonParserError(
            "unsupported export schema",
            reason_code=COMPATIBILITY_UNSUPPORTED_EXPORT_SCHEMA,
        )
    return schema


def _locate_strategy_result(
    data: dict[str, Any],
    strategy_name: str,
) -> dict[str, Any]:
    """Locate the requested strategy result inside a nested export container."""
    strategy_value = data.get("strategy")
    if isinstance(strategy_value, dict):
        if strategy_name in strategy_value:
            return strategy_value[strategy_name]
        # If only one strategy is present, it is ambiguous; reject.
        if len(strategy_value) == 1:
            raise ResearchBacktestComparisonParserError(
                f"requested strategy {strategy_name!r} not found in single-strategy export; "
                f"found {next(iter(strategy_value.keys()))!r}",
                reason_code=COMPATIBILITY_UNSUPPORTED_EXPORT_SCHEMA,
            )
        raise ResearchBacktestComparisonParserError(
            f"requested strategy {strategy_name!r} not found among {sorted(strategy_value.keys())}",
            reason_code=COMPATIBILITY_UNSUPPORTED_EXPORT_SCHEMA,
        )
    if isinstance(strategy_value, str):
        if strategy_value != strategy_name:
            raise ResearchBacktestComparisonParserError(
                f"requested strategy {strategy_name!r} does not match export strategy {strategy_value!r}",
                reason_code=COMPATIBILITY_UNSUPPORTED_EXPORT_SCHEMA,
            )
        return data
    return data


def _parse_flat_metrics(
    data: dict[str, Any],
    *,
    start_balance: Decimal,
    parser_version: str = RESEARCH_BACKTEST_COMPARISON_VERSION,
) -> BacktestMetrics:
    """Parse a flat Freqtrade metrics dict into canonical metrics."""
    total_profit_abs = _coerce_decimal(
        data.get("total_profit_abs", data.get("absolute_profit", data.get("profit_sum")))
    )
    total_profit_ratio = _coerce_decimal(
        data.get("total_profit_ratio", data.get("profit_sum_pct", data.get("total_return_pct")))
    )
    final_balance = _coerce_decimal(data.get("final_balance"))
    if final_balance is None and total_profit_abs is not None:
        final_balance = start_balance + total_profit_abs
    max_drawdown = _coerce_decimal(
        data.get("max_drawdown_account", data.get("max_drawdown_pct"))
    )
    sharpe = _coerce_decimal(data.get("sharpe", data.get("sharpe_ratio")))
    sortino = _coerce_decimal(data.get("sortino", data.get("sortino_ratio")))
    calmar = _coerce_decimal(data.get("calmar", data.get("calmar_ratio")))
    profit_factor = _coerce_decimal(data.get("profit_factor"))
    win_rate = _coerce_decimal(data.get("win_rate", data.get("win_rate_pct")))
    trade_count = data.get("total_trades", data.get("trade_count", 0))
    trade_count_explicit = "total_trades" in data or "trade_count" in data
    if not isinstance(trade_count, int):
        trade_count = 0
    avg_duration = _coerce_decimal(
        data.get("avg_trade_duration_min", data.get("avg_trade_duration"))
    )
    fees_paid = _coerce_decimal(data.get("fees_paid"))

    if trade_count == 0 and not trade_count_explicit:
        raise ResearchBacktestComparisonParserError(
            "flat metrics export contains no explicit trade count; cannot validate zero-trade result",
            reason_code=COMPATIBILITY_UNSUPPORTED_EXPORT_SCHEMA,
        )

    total_return_pct = total_profit_ratio
    if total_return_pct is not None:
        total_return_pct = total_return_pct * Decimal("100")
    elif total_profit_abs is not None and start_balance > 0:
        total_return_pct = (total_profit_abs / start_balance) * Decimal("100")

    absolute_profit = total_profit_abs

    reason_codes = (NO_TRADES,) if trade_count == 0 else ()

    return BacktestMetrics(
        total_return_pct=total_return_pct,
        absolute_profit=absolute_profit,
        final_balance=final_balance,
        max_drawdown_pct=max_drawdown,
        sharpe_ratio=sharpe,
        sortino_ratio=sortino,
        calmar_ratio=calmar,
        profit_factor=profit_factor,
        win_rate_pct=win_rate,
        trade_count=trade_count,
        avg_trade_duration=avg_duration,
        fees_paid=fees_paid,
        parser_version=parser_version,
        reason_codes=reason_codes,
    )


def _compute_metrics_from_trades(
    trades: list[dict[str, Any]],
    *,
    start_balance: Decimal,
    parser_version: str = RESEARCH_BACKTEST_COMPARISON_VERSION,
) -> BacktestMetrics:
    """Compute canonical metrics from a list of Freqtrade-style trade dicts."""
    if not trades:
        return BacktestMetrics(
            total_return_pct=None,
            absolute_profit=None,
            final_balance=None,
            max_drawdown_pct=None,
            sharpe_ratio=None,
            sortino_ratio=None,
            calmar_ratio=None,
            profit_factor=None,
            win_rate_pct=None,
            trade_count=0,
            avg_trade_duration=None,
            fees_paid=Decimal("0"),
            parser_version=parser_version,
            reason_codes=(NO_TRADES,),
        )

    profits: list[Decimal] = []
    wins = 0
    durations: list[Decimal] = []
    fees = Decimal("0")
    for trade in trades:
        profit = _coerce_decimal(trade.get("profit", trade.get("profit_abs", trade.get("profit_ratio"))))
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
        parser_version=parser_version,
        reason_codes=(MISSING_METRIC,) if None in (total_return_pct, profit_factor) else (),
    )


def parse_real_export(
    path: str | Path,
    *,
    strategy_name: str,
    expected_version: str | None = None,
    start_balance: Decimal = Decimal("1000"),
) -> tuple[BacktestMetrics, str, str]:
    """Parse a real Freqtrade backtest export into canonical metrics.

    Args:
        path: Path to the JSON export file.
        strategy_name: Name of the strategy class to locate in the export.
        expected_version: Optional parser version to enforce compatibility.
        start_balance: Starting balance for computing metrics from raw trades.

    Returns:
        Tuple of (BacktestMetrics, export_schema, raw_fingerprint).

    Raises:
        ResearchBacktestComparisonParserError: on parse/version/schema errors.
    """
    result_path = Path(path)
    if not result_path.exists() or not result_path.is_file():
        raise ResearchBacktestComparisonParserError(
            f"result file does not exist: {result_path}", reason_code="RESULT_NOT_FOUND"
        )

    raw_fingerprint = raw_export_fingerprint(result_path)

    try:
        raw_text = _read_export_json_text(result_path)
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ResearchBacktestComparisonParserError(
            f"failed to parse JSON result: {exc}", reason_code=PARSER_ERROR
        ) from exc
    except OSError as exc:
        raise ResearchBacktestComparisonParserError(
            f"failed to read result file: {exc}", reason_code="RESULT_NOT_FOUND"
        ) from exc

    schema = _detect_export_schema(data)
    if schema is None:
        raise ResearchBacktestComparisonParserError(
            "unsupported export schema: could not detect container type",
            reason_code=COMPATIBILITY_UNSUPPORTED_EXPORT_SCHEMA,
        )

    if schema == "freqtrade_nested_strategy":
        if not isinstance(data, dict):
            raise ResearchBacktestComparisonParserError(
                "unexpected nested strategy export format",
                reason_code=COMPATIBILITY_UNSUPPORTED_EXPORT_SCHEMA,
            )
        strategy_result = _locate_strategy_result(data, strategy_name)
        if not isinstance(strategy_result, dict):
            raise ResearchBacktestComparisonParserError(
                "strategy result is not a dict",
                reason_code=COMPATIBILITY_UNSUPPORTED_EXPORT_SCHEMA,
            )
        metrics = _parse_flat_metrics(strategy_result, start_balance=start_balance)
        return metrics, schema, raw_fingerprint

    if schema == "freqtrade_flat_metrics":
        if not isinstance(data, dict):
            raise ResearchBacktestComparisonParserError(
                "unexpected flat metrics export format",
                reason_code=COMPATIBILITY_UNSUPPORTED_EXPORT_SCHEMA,
            )
        metrics = _parse_flat_metrics(data, start_balance=start_balance)
        return metrics, schema, raw_fingerprint

    if schema == "hunter_structured_metrics":
        if not isinstance(data, dict):
            raise ResearchBacktestComparisonParserError(
                "unexpected structured metrics export format",
                reason_code=COMPATIBILITY_UNSUPPORTED_EXPORT_SCHEMA,
            )
        parser_version = data.get("parser_version", RESEARCH_BACKTEST_COMPARISON_VERSION)
        if expected_version is not None and parser_version != expected_version:
            raise ResearchBacktestComparisonParserError(
                f"parser version mismatch: {parser_version} != {expected_version}",
                reason_code=PARSER_VERSION_MISMATCH,
            )
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
        return metrics, schema, raw_fingerprint

    if schema == "freqtrade_trades_list":
        if isinstance(data, list):
            trades = data
        elif isinstance(data, dict):
            trades = data.get("trades", [])
            if not isinstance(trades, list):
                raise ResearchBacktestComparisonParserError(
                    "trades field is not a list",
                    reason_code=COMPATIBILITY_UNSUPPORTED_EXPORT_SCHEMA,
                )
        else:
            raise ResearchBacktestComparisonParserError(
                "unexpected trades list format",
                reason_code=COMPATIBILITY_UNSUPPORTED_EXPORT_SCHEMA,
            )
        metrics = _compute_metrics_from_trades(trades, start_balance=start_balance)
        return metrics, schema, raw_fingerprint

    raise ResearchBacktestComparisonParserError(
        "unsupported export schema",
        reason_code=COMPATIBILITY_UNSUPPORTED_EXPORT_SCHEMA,
    )
