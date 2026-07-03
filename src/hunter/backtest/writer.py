"""Writer for hunter.backtest package. MVP-28 — Local Research Backtesting Engine.

Deterministic JSON, CSV, and Markdown serialization for BacktestReport with
atomic writes. Output is a human-audit / research-only artifact. It is not a
trading signal, not trade approval, not strategy approval, not execution
approval, not portfolio approval, and not Freqtrade input. It does not emit
action commands, suggest orders, or create execution instructions. File
references and metadata strings are serialized as opaque strings only; they are
never opened, traversed, validated, followed, or executed here.
"""

from __future__ import annotations

import csv
import io
import json
import os
from collections.abc import Mapping
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from hunter.backtest.models import (
    BACKTEST_VERSION,
    BacktestCandidateDecision,
    BacktestCandidateResult,
    BacktestDataQuality,
    BacktestInput,
    BacktestPortfolioResult,
    BacktestPortfolioSnapshot,
    BacktestPriceBar,
    BacktestReport,
    BacktestRunConfig,
    BacktestSafetyFlags,
)

DEFAULT_JSON_PATH = Path("data/backtest/latest_backtest_report.json")
DEFAULT_CSV_PATH = Path("data/backtest/latest_backtest_results.csv")
DEFAULT_MD_PATH = Path("reports/backtest/latest_backtest_report.md")

_SAFETY_NOTICE = (
    "This local backtest report is a human-audit / research-only artifact. "
    "It is not a trading signal, not trade approval, not strategy approval, not execution approval, "
    "not portfolio approval, and not Freqtrade input. It must not be consumed by execution, "
    "strategy, Freqtrade shell, order, exchange, or any MVP execution path. "
    "No action commands, trading instructions, or order suggestions are emitted. "
    "Simulated weights and returns shown below are research-only; they are not position sizes, "
    "not trade sizes, not orders, and not real capital."
)


# ---------------------------------------------------------------------------
# Value helpers
# ---------------------------------------------------------------------------


def _iso(value: datetime) -> str:
    """Serialize a timezone-aware datetime to ISO-8601 with UTC suffix."""
    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def _serialize_value(value: Any) -> Any:
    """Recursively serialize a value to JSON-safe deterministic types."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return _iso(value)
    if isinstance(value, tuple):
        return [_serialize_value(v) for v in value]
    if isinstance(value, list):
        return [_serialize_value(v) for v in value]
    if isinstance(value, Mapping):
        return {str(k): _serialize_value(v) for k, v in sorted(value.items())}
    return value


def _coerce_path(value: str | Path | None, default: Path) -> Path:
    """Return a Path for the given value, falling back to the default."""
    if value is None:
        return default
    if isinstance(value, Path):
        return value
    return Path(value)


def _round_value(value: float | int, decimals: int = 4) -> float | int:
    """Round a numeric value when it is a float."""
    if isinstance(value, float):
        return round(value, decimals)
    return value


# ---------------------------------------------------------------------------
# Dict serialization
# ---------------------------------------------------------------------------


def _price_bar_to_dict(bar: BacktestPriceBar) -> dict[str, Any]:
    """Serialize BacktestPriceBar to a JSON-safe dict."""
    return {
        "pair": bar.pair,
        "timestamp": _iso(bar.timestamp),
        "close": _round_value(bar.close, 8),
        "open": _round_value(bar.open, 8) if bar.open is not None else None,
        "high": _round_value(bar.high, 8) if bar.high is not None else None,
        "low": _round_value(bar.low, 8) if bar.low is not None else None,
        "volume": _round_value(bar.volume, 8) if bar.volume is not None else None,
        "metadata": _serialize_value(bar.metadata),
    }


def _decision_to_dict(decision: BacktestCandidateDecision | None) -> Any:
    """Serialize BacktestCandidateDecision to a JSON-safe dict or None."""
    if decision is None:
        return None
    return {
        "pair": decision.pair,
        "state": decision.state,
        "classification": decision.classification,
        "research_weight_pct": _round_value(decision.research_weight_pct, 4),
        "final_weight_pct": _round_value(decision.final_weight_pct, 4),
        "tags": list(decision.tags),
        "metadata": _serialize_value(decision.metadata),
    }


def _input_to_dict(inp: BacktestInput) -> dict[str, Any]:
    """Serialize BacktestInput to a JSON-safe dict."""
    return {
        "pair": inp.pair,
        "input_kind": inp.input_kind.value,
        "decision": _decision_to_dict(inp.decision),
        "price_bars": [_price_bar_to_dict(b) for b in inp.price_bars],
        "tags": list(inp.tags),
        "metadata": _serialize_value(inp.metadata),
    }


def _config_to_dict(config: BacktestRunConfig) -> dict[str, Any]:
    """Serialize BacktestRunConfig to a JSON-safe dict."""
    return {
        "allocation_mode": config.allocation_mode.value,
        "include_excluded_candidates": config.include_excluded_candidates,
        "block_on_blocked_context": config.block_on_blocked_context,
        "block_on_missing_context": config.block_on_missing_context,
        "min_observation_count": config.min_observation_count,
        "allow_missing_decision": config.allow_missing_decision,
        "custom_weights": {k: _round_value(v, 4) for k, v in sorted(config.custom_weights.items())},
        "volatility_scale_factor": _round_value(config.volatility_scale_factor, 4),
        "start_timestamp": _iso(config.start_timestamp) if config.start_timestamp is not None else None,
        "end_timestamp": _iso(config.end_timestamp) if config.end_timestamp is not None else None,
    }


def _safety_flags_to_dict(flags: BacktestSafetyFlags) -> dict[str, Any]:
    """Serialize BacktestSafetyFlags to a JSON-safe dict."""
    return {
        "no_trading_signal": flags.no_trading_signal,
        "no_trade_approval": flags.no_trade_approval,
        "no_strategy_approval": flags.no_strategy_approval,
        "no_execution_approval": flags.no_execution_approval,
        "no_portfolio_approval": flags.no_portfolio_approval,
        "no_universe_approval": flags.no_universe_approval,
        "no_order_sizing": flags.no_order_sizing,
        "no_position_sizing": flags.no_position_sizing,
        "no_leverage": flags.no_leverage,
        "no_shorting": flags.no_shorting,
        "no_action_commands": flags.no_action_commands,
        "no_network_connection": flags.no_network_connection,
        "no_file_read_in_engine": flags.no_file_read_in_engine,
        "no_database": flags.no_database,
        "no_exchange_connection": flags.no_exchange_connection,
        "no_freqtrade_input": flags.no_freqtrade_input,
        "has_unsafe_content": flags.has_unsafe_content,
        "has_invalid_pair": flags.has_invalid_pair,
        "has_invalid_price": flags.has_invalid_price,
        "has_invalid_date": flags.has_invalid_date,
        "has_blocked_context": flags.has_blocked_context,
        "has_missing_required_context": flags.has_missing_required_context,
        "has_inconsistent_state": flags.has_inconsistent_state,
        "is_safe": flags.is_safe,
    }


def _data_quality_to_dict(data_quality: BacktestDataQuality) -> dict[str, Any]:
    """Serialize BacktestDataQuality to a JSON-safe dict."""
    return {
        "total_inputs": data_quality.total_inputs,
        "included_count": data_quality.included_count,
        "capped_count": data_quality.capped_count,
        "watchlist_count": data_quality.watchlist_count,
        "excluded_count": data_quality.excluded_count,
        "insufficient_data_count": data_quality.insufficient_data_count,
        "blocked_count": data_quality.blocked_count,
        "ready_price_history_count": data_quality.ready_price_history_count,
        "missing_price_history_count": data_quality.missing_price_history_count,
        "blocked_decision_count": data_quality.blocked_decision_count,
        "observation_count": data_quality.observation_count,
        "missing_data_count": data_quality.missing_data_count,
        "data_quality_score": _round_value(data_quality.data_quality_score, 4),
        "all_counts_consistent": data_quality.all_counts_consistent,
        "safety_flags_ok": data_quality.safety_flags_ok,
        "has_unsafe_content": data_quality.has_unsafe_content,
    }


def _portfolio_snapshot_to_dict(snapshot: BacktestPortfolioSnapshot) -> dict[str, Any]:
    """Serialize BacktestPortfolioSnapshot to a JSON-safe dict."""
    return {
        "timestamp": _iso(snapshot.timestamp),
        "equity": _round_value(snapshot.equity, 8),
        "weight_sum": _round_value(snapshot.weight_sum, 4),
        "observation_count": snapshot.observation_count,
        "metadata": _serialize_value(snapshot.metadata),
    }


def _portfolio_result_to_dict(portfolio: BacktestPortfolioResult) -> dict[str, Any]:
    """Serialize BacktestPortfolioResult to a JSON-safe dict."""
    return {
        "total_return_pct": _round_value(portfolio.total_return_pct, 4),
        "max_drawdown_pct": _round_value(portfolio.max_drawdown_pct, 4),
        "volatility_pct": _round_value(portfolio.volatility_pct, 4),
        "win_rate_pct": _round_value(portfolio.win_rate_pct, 4),
        "observation_count": portfolio.observation_count,
        "missing_data_count": portfolio.missing_data_count,
        "insufficient_data_count": portfolio.insufficient_data_count,
        "blocked_count": portfolio.blocked_count,
        "candidate_count": portfolio.candidate_count,
        "equity_curve": [_portfolio_snapshot_to_dict(s) for s in portfolio.equity_curve],
        "reason_codes": list(portfolio.reason_codes),
        "metadata": _serialize_value(portfolio.metadata),
    }


def _candidate_result_to_dict(result: BacktestCandidateResult) -> dict[str, Any]:
    """Serialize BacktestCandidateResult to a JSON-safe dict."""
    return {
        "pair": result.pair,
        "state": result.state.value,
        "classification": result.classification,
        "allocation_mode": result.allocation_mode.value,
        "simulated_weight": _round_value(result.simulated_weight, 4),
        "total_return_pct": _round_value(result.total_return_pct, 4),
        "max_drawdown_pct": _round_value(result.max_drawdown_pct, 4),
        "volatility_pct": _round_value(result.volatility_pct, 4),
        "win_rate_pct": _round_value(result.win_rate_pct, 4),
        "observation_count": result.observation_count,
        "missing_data_count": result.missing_data_count,
        "insufficient_data_count": result.insufficient_data_count,
        "period_returns": [_round_value(v, 8) for v in result.period_returns],
        "reason_codes": list(result.reason_codes),
        "tags": list(result.tags),
        "metadata": _serialize_value(result.metadata),
        "notes": list(result.notes),
        "rank": result.rank,
    }


def backtest_report_to_dict(report: BacktestReport) -> dict[str, Any]:
    """Serialize BacktestReport to a JSON-safe dict deterministically."""
    return {
        "report_id": report.report_id,
        "version": report.version,
        "generated_at": _iso(report.generated_at),
        "inputs": [_input_to_dict(inp) for inp in report.inputs],
        "config": _config_to_dict(report.config),
        "candidate_results": [_candidate_result_to_dict(r) for r in report.candidate_results],
        "portfolio_result": _portfolio_result_to_dict(report.portfolio_result),
        "data_quality": _data_quality_to_dict(report.data_quality),
        "safety_flags": _safety_flags_to_dict(report.safety_flags),
        "reason_codes": list(report.reason_codes),
        "metadata": _serialize_value(report.metadata),
        "notes": list(report.notes),
    }


# ---------------------------------------------------------------------------
# Text serializers
# ---------------------------------------------------------------------------


def backtest_report_to_json_text(report: BacktestReport) -> str:
    """Return a deterministic JSON text representation of the report."""
    data = backtest_report_to_dict(report)
    return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


_CSV_COLUMNS = (
    "report_id",
    "generated_at",
    "pair",
    "state",
    "classification",
    "allocation_mode",
    "simulated_weight",
    "total_return_pct",
    "max_drawdown_pct",
    "volatility_pct",
    "win_rate_pct",
    "observation_count",
    "missing_data_count",
    "insufficient_data_count",
    "reason_codes",
    "tags",
    "rank",
)


def backtest_report_to_csv_text(report: BacktestReport) -> str:
    """Return a deterministic CSV text representation of the report."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(_CSV_COLUMNS)

    generated_at = _iso(report.generated_at)

    for result in report.candidate_results:
        row: list[Any] = [
            report.report_id,
            generated_at,
            result.pair,
            result.state.value,
            result.classification,
            result.allocation_mode.value,
            _round_value(result.simulated_weight, 4),
            _round_value(result.total_return_pct, 2),
            _round_value(result.max_drawdown_pct, 2),
            _round_value(result.volatility_pct, 2),
            _round_value(result.win_rate_pct, 2),
            result.observation_count,
            result.missing_data_count,
            result.insufficient_data_count,
            "|".join(result.reason_codes),
            "|".join(result.tags),
            result.rank if result.rank is not None else "",
        ]
        writer.writerow(row)

    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Markdown serialization
# ---------------------------------------------------------------------------


def _md_value(value: Any) -> str:
    """Stringify a value for Markdown, escaping pipe characters."""
    if value is None:
        return ""
    text = str(value).replace("|", "\\|")
    return text


def _md_num(value: float | int | None) -> str:
    """Stringify a numeric value for Markdown."""
    if value is None:
        return ""
    return str(_round_value(value, 4))


def backtest_report_to_markdown(report: BacktestReport) -> str:
    """Render BacktestReport as Markdown with a safety notice."""
    portfolio = report.portfolio_result
    dq = report.data_quality
    config = report.config

    lines: list[str] = [
        "# Backtest Report",
        "",
        f"> {_SAFETY_NOTICE}",
        "",
        "## Report Identity",
        "",
        f"- **report_id**: {report.report_id}",
        f"- **version**: {report.version}",
        f"- **generated_at**: {_iso(report.generated_at)}",
        "",
        "## Portfolio Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total return % | {_md_num(portfolio.total_return_pct)} |",
        f"| Max drawdown % | {_md_num(portfolio.max_drawdown_pct)} |",
        f"| Volatility % | {_md_num(portfolio.volatility_pct)} |",
        f"| Win rate % | {_md_num(portfolio.win_rate_pct)} |",
        f"| Observations | {_md_value(portfolio.observation_count)} |",
        f"| Missing data points | {_md_value(portfolio.missing_data_count)} |",
        f"| Insufficient data candidates | {_md_value(portfolio.insufficient_data_count)} |",
        f"| Blocked candidates | {_md_value(portfolio.blocked_count)} |",
        f"| Total candidates | {_md_value(portfolio.candidate_count)} |",
        f"| Equity curve points | {_md_value(len(portfolio.equity_curve))} |",
        "",
        "## Data Quality",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total inputs | {_md_value(dq.total_inputs)} |",
        f"| Included | {_md_value(dq.included_count)} |",
        f"| Capped | {_md_value(dq.capped_count)} |",
        f"| Watchlist | {_md_value(dq.watchlist_count)} |",
        f"| Excluded | {_md_value(dq.excluded_count)} |",
        f"| Insufficient data | {_md_value(dq.insufficient_data_count)} |",
        f"| Blocked | {_md_value(dq.blocked_count)} |",
        f"| Ready price history | {_md_value(dq.ready_price_history_count)} |",
        f"| Missing price history | {_md_value(dq.missing_price_history_count)} |",
        f"| Blocked decisions | {_md_value(dq.blocked_decision_count)} |",
        f"| Data quality score | {_md_num(dq.data_quality_score)} |",
        f"| All counts consistent | {_md_value(dq.all_counts_consistent)} |",
        f"| Safety flags OK | {_md_value(dq.safety_flags_ok)} |",
        f"| Has unsafe content | {_md_value(dq.has_unsafe_content)} |",
        "",
        "## Candidate Results",
        "",
        "| Pair | State | Classification | Mode | Simulated Weight % | Total Return % | Max Drawdown % | Volatility % | Win Rate % | Observations | Missing | Rank | Reason Codes | Tags |",
        "|------|-------|----------------|------|-------------------:|---------------:|---------------:|-------------:|-----------:|-------------:|--------:|-----:|--------------|------|",
    ]

    for result in report.candidate_results:
        lines.append(
            f"| {_md_value(result.pair)} | {_md_value(result.state.value)} | "
            f"{_md_value(result.classification)} | {_md_value(result.allocation_mode.value)} | "
            f"{_md_num(result.simulated_weight)} | {_md_num(result.total_return_pct)} | "
            f"{_md_num(result.max_drawdown_pct)} | {_md_num(result.volatility_pct)} | "
            f"{_md_num(result.win_rate_pct)} | {_md_value(result.observation_count)} | "
            f"{_md_value(result.missing_data_count)} | "
            f"{_md_value(result.rank if result.rank is not None else '')} | "
            f"{_md_value('|'.join(result.reason_codes))} | {_md_value('|'.join(result.tags))} |"
        )
    lines.append("")

    lines.extend([
        "## Equity Curve Summary",
        "",
        "| Timestamp | Equity | Weight Sum % | Observations |",
        "|-----------|--------|-------------:|-------------:|",
    ])
    for snapshot in portfolio.equity_curve:
        lines.append(
            f"| {_md_value(_iso(snapshot.timestamp))} | {_md_num(snapshot.equity)} | "
            f"{_md_num(snapshot.weight_sum)} | {_md_value(snapshot.observation_count)} |"
        )
    if not portfolio.equity_curve:
        lines.append("| _none_ | | | |")
    lines.append("")

    lines.extend([
        "## Configuration",
        "",
        "| Setting | Value |",
        "|--------|-------|",
        f"| allocation_mode | {_md_value(config.allocation_mode.value)} |",
        f"| include_excluded_candidates | {_md_value(config.include_excluded_candidates)} |",
        f"| min_observation_count | {_md_value(config.min_observation_count)} |",
        f"| volatility_scale_factor | {_md_num(config.volatility_scale_factor)} |",
        f"| start_timestamp | {_md_value(_iso(config.start_timestamp) if config.start_timestamp is not None else 'None')} |",
        f"| end_timestamp | {_md_value(_iso(config.end_timestamp) if config.end_timestamp is not None else 'None')} |",
        "",
    ])

    lines.extend([
        "## Reason Codes",
        "",
    ])
    if report.reason_codes:
        for code in report.reason_codes:
            lines.append(f"- {code}")
    else:
        lines.append("- _none_")
    lines.append("")

    lines.extend([
        "## Safety Flags",
        "",
    ])
    for key, value in sorted(_safety_flags_to_dict(report.safety_flags).items()):
        lines.append(f"- **{key}**: {value}")
    lines.append("")

    if report.metadata:
        lines.extend([
            "## Metadata",
            "",
        ])
        for key, value in sorted(report.metadata.items()):
            lines.append(f"- **{key}**: {value}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Atomic writes
# ---------------------------------------------------------------------------


def _atomic_write(path: Path, content: str | bytes) -> None:
    """Write content atomically: temp file, fsync, os.replace.

    Does not read, traverse, validate, follow, or execute any file references.
    """
    path = Path(path)
    tmp = path.parent / (path.name + ".tmp")
    try:
        if isinstance(content, str):
            content = content.encode("utf-8")
        path.parent.mkdir(parents=True, exist_ok=True)
        with tmp.open("wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        parent_fd = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
        os.replace(str(tmp), str(path))
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise


def atomic_write_json_backtest_report(
    report: BacktestReport,
    path: str | Path | None = None,
) -> Path:
    """Serialize BacktestReport to JSON and write atomically."""
    target = _coerce_path(path, DEFAULT_JSON_PATH)
    _atomic_write(target, backtest_report_to_json_text(report))
    return target


def atomic_write_csv_backtest_report(
    report: BacktestReport,
    path: str | Path | None = None,
) -> Path:
    """Serialize BacktestReport to CSV and write atomically."""
    target = _coerce_path(path, DEFAULT_CSV_PATH)
    _atomic_write(target, backtest_report_to_csv_text(report))
    return target


def atomic_write_markdown_backtest_report(
    report: BacktestReport,
    path: str | Path | None = None,
) -> Path:
    """Serialize BacktestReport to Markdown and write atomically."""
    target = _coerce_path(path, DEFAULT_MD_PATH)
    _atomic_write(target, backtest_report_to_markdown(report) + "\n")
    return target


_DEFAULT_PATH = object()


def write_backtest_report(
    report: BacktestReport,
    json_path: str | Path | None | object = _DEFAULT_PATH,
    csv_path: str | Path | None | object = _DEFAULT_PATH,
    md_path: str | Path | None | object = _DEFAULT_PATH,
) -> tuple[Path | None, Path | None, Path | None]:
    """Write BacktestReport to JSON, CSV, and Markdown as requested.

    Pass None for a format to skip writing that artifact. Default paths are used
    when a path is omitted and the format is written.
    """
    json_out = (
        atomic_write_json_backtest_report(
            report, None if json_path is _DEFAULT_PATH else json_path
        )
        if json_path is not None
        else None
    )
    csv_out = (
        atomic_write_csv_backtest_report(
            report, None if csv_path is _DEFAULT_PATH else csv_path
        )
        if csv_path is not None
        else None
    )
    md_out = (
        atomic_write_markdown_backtest_report(
            report, None if md_path is _DEFAULT_PATH else md_path
        )
        if md_path is not None
        else None
    )
    return json_out, csv_out, md_out
