"""Writer for hunter.relative_strength package. MVP-24 — Relative Strength Engine.

Deterministic JSON, CSV, and Markdown serialization for RelativeStrengthReport
with atomic writes. Output is a human-audit / research-only artifact. It is not
a trading signal, not trade approval, not execution approval, and not Freqtrade
input. File references and metadata strings are serialized as opaque strings only;
they are never opened, traversed, followed, validated, or executed here.
"""

from __future__ import annotations

import csv
import io
import json
import os
from collections.abc import Mapping
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any

from hunter.relative_strength.models import (
    RELATIVE_STRENGTH_VERSION,
    OhlcvRow,
    RelativeStrengthConfig,
    RelativeStrengthDataQuality,
    RelativeStrengthDecision,
    RelativeStrengthPeriodReturn,
    RelativeStrengthRatioTrend,
    RelativeStrengthReport,
    RelativeStrengthSafetyFlags,
    RelativeStrengthScore,
    RelativeStrengthState,
    RelativeStrengthUniverseSummary,
)


DEFAULT_JSON_PATH = Path("data/relative_strength/latest_relative_strength_scores.json")
DEFAULT_CSV_PATH = Path("data/relative_strength/latest_relative_strength_scores.csv")
DEFAULT_MD_PATH = Path("reports/relative_strength/latest_relative_strength_report.md")


_SAFETY_NOTICE = (
    "This local relative strength report is a human-audit / research-only artifact. "
    "It is not a trading signal, not trade approval, not strategy approval, not execution approval, "
    "not portfolio/universe approval, and not Freqtrade input. It must not be consumed by execution, "
    "strategy, Freqtrade shell, order, exchange, or any MVP execution path. "
    "No action commands, trading instructions, or order suggestions are emitted."
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
    if isinstance(value, Decimal):
        return float(value)
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


def _ohlcv_row_to_dict(row: OhlcvRow) -> dict[str, Any]:
    """Serialize OhlcvRow to a JSON-safe dict."""
    return {
        "timestamp": _serialize_value(row.timestamp),
        "open": _serialize_value(row.open),
        "high": _serialize_value(row.high),
        "low": _serialize_value(row.low),
        "close": _serialize_value(row.close),
        "volume": _serialize_value(row.volume),
    }


def _config_to_dict(config: RelativeStrengthConfig) -> dict[str, Any]:
    """Serialize RelativeStrengthConfig to a JSON-safe dict."""
    return {
        "block_on_missing_data": config.block_on_missing_data,
        "block_on_missing_eth": config.block_on_missing_eth,
        "lookback_days": list(config.lookback_days),
        "min_required_rows": config.min_required_rows,
        "outperformer_threshold": config.outperformer_threshold,
        "rank_percentile_window": config.rank_percentile_window,
        "ratio_trend_lookback": config.ratio_trend_lookback,
        "ratio_trend_ma_window": config.ratio_trend_ma_window,
        "rounding_policy": config.rounding_policy,
        "score_weights": dict(sorted(config.score_weights.items())),
        "underperformer_threshold": config.underperformer_threshold,
        "version": config.version,
    }


def _safety_flags_to_dict(flags: RelativeStrengthSafetyFlags) -> dict[str, Any]:
    """Serialize RelativeStrengthSafetyFlags to a JSON-safe dict."""
    return {
        "benchmarks_provided_by_caller": flags.benchmarks_provided_by_caller,
        "database_enabled": flags.database_enabled,
        "event_store_enabled": flags.event_store_enabled,
        "feedback_into_execution": flags.feedback_into_execution,
        "feedback_into_freqtrade": flags.feedback_into_freqtrade,
        "feedback_into_portfolio": flags.feedback_into_portfolio,
        "feedback_into_strategy": flags.feedback_into_strategy,
        "file_read_enabled": flags.file_read_enabled,
        "file_write_enabled": flags.file_write_enabled,
        "human_research_only": flags.human_research_only,
        "indexer_crawler_enabled": flags.indexer_crawler_enabled,
        "inputs_already_loaded": flags.inputs_already_loaded,
        "leverage_enabled": flags.leverage_enabled,
        "network_enabled": flags.network_enabled,
        "no_action_commands_emitted": flags.no_action_commands_emitted,
        "output_is_human_research_only": flags.output_is_human_research_only,
        "output_not_exchange_input": flags.output_not_exchange_input,
        "output_not_freqtrade_input": flags.output_not_freqtrade_input,
        "output_not_order_input": flags.output_not_order_input,
        "output_not_portfolio_approval": flags.output_not_portfolio_approval,
        "output_not_strategy_approval": flags.output_not_strategy_approval,
        "output_not_trade_approval": flags.output_not_trade_approval,
        "output_not_trading_signal": flags.output_not_trading_signal,
        "output_not_universe_approval": flags.output_not_universe_approval,
        "real_orders_enabled": flags.real_orders_enabled,
        "runtime_registry_enabled": flags.runtime_registry_enabled,
        "shorting_enabled": flags.shorting_enabled,
        "task_runner_enabled": flags.task_runner_enabled,
    }


def _period_return_to_dict(pr: RelativeStrengthPeriodReturn) -> dict[str, Any]:
    """Serialize RelativeStrengthPeriodReturn to a JSON-safe dict."""
    return {
        "period_days": pr.period_days,
        "coin_return": _round_value(pr.coin_return) if pr.coin_return is not None else None,
        "btc_return": _round_value(pr.btc_return) if pr.btc_return is not None else None,
        "eth_return": _round_value(pr.eth_return) if pr.eth_return is not None else None,
        "coin_minus_btc": _round_value(pr.coin_minus_btc) if pr.coin_minus_btc is not None else None,
        "coin_minus_eth": _round_value(pr.coin_minus_eth) if pr.coin_minus_eth is not None else None,
        "has_data": pr.has_data,
        "reason_codes": list(pr.reason_codes),
    }


def _ratio_trend_to_dict(rt: RelativeStrengthRatioTrend) -> dict[str, Any]:
    """Serialize RelativeStrengthRatioTrend to a JSON-safe dict."""
    return {
        "last_ratio": _round_value(rt.last_ratio),
        "ma_ratio": _round_value(rt.ma_ratio),
        "slope": _round_value(rt.slope),
        "trend_score": _round_value(rt.trend_score, 2),
        "lookback": rt.lookback,
        "has_data": rt.has_data,
        "reason_codes": list(rt.reason_codes),
    }


def _data_quality_to_dict(data_quality: RelativeStrengthDataQuality) -> dict[str, Any]:
    """Serialize RelativeStrengthDataQuality to a JSON-safe dict."""
    return {
        "expected_rows": data_quality.expected_rows,
        "actual_rows": data_quality.actual_rows,
        "missing_rows": data_quality.missing_rows,
        "missing_periods": list(data_quality.missing_periods),
        "min_required_rows_met": data_quality.min_required_rows_met,
        "btc_benchmark_rows": data_quality.btc_benchmark_rows,
        "eth_benchmark_rows": data_quality.eth_benchmark_rows,
        "stale_input_count": data_quality.stale_input_count,
        "reason_codes": list(data_quality.reason_codes),
    }


def _score_to_dict(score: RelativeStrengthScore) -> dict[str, Any]:
    """Serialize RelativeStrengthScore to a JSON-safe dict."""
    return {
        "symbol": score.symbol,
        "base_benchmark": score.base_benchmark.value,
        "state": score.state.value,
        "decision": score.decision.value,
        "total_score": _round_value(score.total_score, 2),
        "period_returns": [_period_return_to_dict(pr) for pr in score.period_returns],
        "ratio_trend": _ratio_trend_to_dict(score.ratio_trend),
        "rank_percentile_30d": _round_value(score.rank_percentile_30d, 2) if score.rank_percentile_30d is not None else None,
        "sub_scores": {k: _round_value(v, 4) for k, v in sorted(score.sub_scores.items())},
        "data_quality": _data_quality_to_dict(score.data_quality),
        "human_note": score.human_note,
        "reason_codes": list(score.reason_codes),
    }


def _universe_summary_to_dict(summary: RelativeStrengthUniverseSummary) -> dict[str, Any]:
    """Serialize RelativeStrengthUniverseSummary to a JSON-safe dict."""
    return {
        "total_coins": summary.total_coins,
        "outperformer_count": summary.outperformer_count,
        "neutral_count": summary.neutral_count,
        "underperformer_count": summary.underperformer_count,
        "insufficient_data_count": summary.insufficient_data_count,
        "blocked_count": summary.blocked_count,
        "top_outperformer": summary.top_outperformer,
        "top_underperformer": summary.top_underperformer,
        "average_total_score": _round_value(summary.average_total_score, 2),
        "data_quality": _data_quality_to_dict(summary.data_quality),
        "summary_narrative": summary.summary_narrative,
    }


def relative_strength_report_to_dict(report: RelativeStrengthReport) -> dict[str, Any]:
    """Serialize RelativeStrengthReport to a JSON-safe dict deterministically."""
    return {
        "report_id": report.report_id,
        "kind": report.kind,
        "version": report.version,
        "source_spec": report.source_spec,
        "generated_at": _iso(report.generated_at),
        "config": _config_to_dict(report.config),
        "safety_flags": _safety_flags_to_dict(report.safety_flags),
        "scores": [_score_to_dict(score) for score in report.scores],
        "universe_summary": _universe_summary_to_dict(report.universe_summary),
        "btc_series_head": [_ohlcv_row_to_dict(row) for row in report.btc_series_head],
        "eth_series_head": [_ohlcv_row_to_dict(row) for row in report.eth_series_head] if report.eth_series_head is not None else None,
        "reason_codes": list(report.reason_codes),
        "metadata": _serialize_value(report.metadata),
    }


# ---------------------------------------------------------------------------
# Text serializers
# ---------------------------------------------------------------------------


def relative_strength_report_to_json_text(report: RelativeStrengthReport) -> str:
    """Return a deterministic JSON text representation of the report."""
    data = relative_strength_report_to_dict(report)
    return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


_CSV_COLUMNS = (
    "report_id",
    "generated_at",
    "pair",
    "state",
    "decision",
    "total_score",
    "rank_percentile_30d",
    "coin_minus_btc_7d",
    "coin_minus_btc_14d",
    "coin_minus_btc_30d",
    "coin_minus_eth_30d",
    "ratio_trend_score",
    "ratio_trend_last_ratio",
    "ratio_trend_ma_ratio",
    "ratio_trend_slope",
    "reason_codes",
    "human_note",
)


def _period_return_value(
    period_returns: tuple[RelativeStrengthPeriodReturn, ...],
    period_days: int,
    field: str,
) -> float | None:
    """Return a field from a RelativeStrengthPeriodReturn with the given period_days."""
    for pr in period_returns:
        if pr.period_days == period_days:
            value = getattr(pr, field)
            return _round_value(value, 4) if value is not None else None
    return None


def relative_strength_report_to_csv_text(report: RelativeStrengthReport) -> str:
    """Return a deterministic CSV text representation of the report."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(_CSV_COLUMNS)

    for score in report.scores:
        rt = score.ratio_trend
        row = [
            report.report_id,
            _iso(report.generated_at),
            score.symbol,
            score.state.value,
            score.decision.value,
            _round_value(score.total_score, 2),
            _round_value(score.rank_percentile_30d, 2) if score.rank_percentile_30d is not None else "",
            _period_return_value(score.period_returns, 7, "coin_minus_btc"),
            _period_return_value(score.period_returns, 14, "coin_minus_btc"),
            _period_return_value(score.period_returns, 30, "coin_minus_btc"),
            _period_return_value(score.period_returns, 30, "coin_minus_eth"),
            _round_value(rt.trend_score, 2) if rt.has_data else "",
            _round_value(rt.last_ratio, 4),
            _round_value(rt.ma_ratio, 4),
            _round_value(rt.slope, 4),
            "|".join(score.reason_codes),
            score.human_note,
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


def relative_strength_report_to_markdown(report: RelativeStrengthReport) -> str:
    """Render RelativeStrengthReport as Markdown with a safety notice."""
    summary = report.universe_summary
    dq = summary.data_quality

    lines: list[str] = [
        "# Relative Strength Report",
        "",
        f"> {_SAFETY_NOTICE}",
        "",
        "## Report Info",
        "",
        f"- **report_id**: {report.report_id}",
        f"- **generated_at**: {_iso(report.generated_at)}",
        f"- **version**: {report.version}",
        f"- **source_spec**: {report.source_spec}",
        f"- **kind**: {report.kind}",
        "",
        "## Universe Summary",
        "",
        f"- **total_coins**: {summary.total_coins}",
        f"- **outperformers**: {summary.outperformer_count}",
        f"- **neutral**: {summary.neutral_count}",
        f"- **underperformers**: {summary.underperformer_count}",
        f"- **insufficient_data**: {summary.insufficient_data_count}",
        f"- **blocked**: {summary.blocked_count}",
        f"- **top_outperformer**: {summary.top_outperformer or '_none_'}",
        f"- **top_underperformer**: {summary.top_underperformer or '_none_'}",
        f"- **average_total_score**: {_round_value(summary.average_total_score, 2)}",
        f"- **summary_narrative**: {summary.summary_narrative}",
        "",
        "## Data Quality",
        "",
        f"- **expected_rows**: {dq.expected_rows}",
        f"- **actual_rows**: {dq.actual_rows}",
        f"- **missing_rows**: {dq.missing_rows}",
        f"- **missing_periods**: {', '.join(dq.missing_periods) if dq.missing_periods else '_none_'}",
        f"- **min_required_rows_met**: {dq.min_required_rows_met}",
        f"- **btc_benchmark_rows**: {dq.btc_benchmark_rows}",
        f"- **eth_benchmark_rows**: {dq.eth_benchmark_rows or '_none_'}",
        f"- **stale_input_count**: {dq.stale_input_count}",
        f"- **reason_codes**: {', '.join(dq.reason_codes) if dq.reason_codes else '_none_'}",
        "",
    ]

    lines.extend([
        "## Scores",
        "",
        "| pair | state | decision | total_score | rank_pct | btc_7d | btc_14d | btc_30d | eth_30d | trend_score | reason_codes | human_note |",
        "|------|-------|----------|-------------|----------|--------|---------|---------|---------|-------------|--------------|------------|",
    ])
    for score in report.scores:
        rt = score.ratio_trend
        pr_7 = _period_return_value(score.period_returns, 7, "coin_minus_btc")
        pr_14 = _period_return_value(score.period_returns, 14, "coin_minus_btc")
        pr_30 = _period_return_value(score.period_returns, 30, "coin_minus_btc")
        pr_30_eth = _period_return_value(score.period_returns, 30, "coin_minus_eth")
        lines.append(
            f"| {_md_value(score.symbol)} | {_md_value(score.state.value)} | "
            f"{_md_value(score.decision.value)} | {_md_value(_round_value(score.total_score, 2))} | "
            f"{_md_value(_round_value(score.rank_percentile_30d, 2) if score.rank_percentile_30d is not None else '')} | "
            f"{_md_value(pr_7)} | {_md_value(pr_14)} | {_md_value(pr_30)} | "
            f"{_md_value(pr_30_eth)} | {_md_value(_round_value(rt.trend_score, 2) if rt.has_data else '')} | "
            f"{_md_value('|'.join(score.reason_codes))} | {_md_value(score.human_note)} |"
        )
    lines.append("")

    lines.extend([
        "## Ratio Trend Summary",
        "",
        "| pair | last_ratio | ma_ratio | slope | trend_score | has_data |",
        "|------|------------|----------|-------|-------------|----------|",
    ])
    for score in report.scores:
        rt = score.ratio_trend
        lines.append(
            f"| {_md_value(score.symbol)} | {_md_value(_round_value(rt.last_ratio, 4))} | "
            f"{_md_value(_round_value(rt.ma_ratio, 4))} | {_md_value(_round_value(rt.slope, 4))} | "
            f"{_md_value(_round_value(rt.trend_score, 2))} | {_md_value(rt.has_data)} |"
        )
    lines.append("")

    lines.extend([
        "## Safety Flags",
        "",
    ])
    for key, value in sorted(_safety_flags_to_dict(report.safety_flags).items()):
        lines.append(f"- **{key}**: {value}")
    lines.append("")

    lines.extend([
        "## Report Reason Codes",
        "",
    ])
    if report.reason_codes:
        for code in report.reason_codes:
            lines.append(f"- {code}")
    else:
        lines.append("- _none_")
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


def atomic_write_json_relative_strength_report(
    report: RelativeStrengthReport,
    path: str | Path | None = None,
) -> Path:
    """Serialize RelativeStrengthReport to JSON and write atomically."""
    target = _coerce_path(path, DEFAULT_JSON_PATH)
    _atomic_write(target, relative_strength_report_to_json_text(report))
    return target


def atomic_write_csv_relative_strength_report(
    report: RelativeStrengthReport,
    path: str | Path | None = None,
) -> Path:
    """Serialize RelativeStrengthReport to CSV and write atomically."""
    target = _coerce_path(path, DEFAULT_CSV_PATH)
    _atomic_write(target, relative_strength_report_to_csv_text(report))
    return target


def atomic_write_markdown_relative_strength_report(
    report: RelativeStrengthReport,
    path: str | Path | None = None,
) -> Path:
    """Serialize RelativeStrengthReport to Markdown and write atomically."""
    target = _coerce_path(path, DEFAULT_MD_PATH)
    _atomic_write(target, relative_strength_report_to_markdown(report) + "\n")
    return target


def write_relative_strength_report(
    report: RelativeStrengthReport,
    json_path: str | Path | None = None,
    csv_path: str | Path | None = None,
    md_path: str | Path | None = None,
) -> tuple[Path | None, Path | None, Path | None]:
    """Write RelativeStrengthReport to JSON, CSV, and Markdown as requested.

    Pass None for a format to skip writing that artifact. Default paths are used
    when a path is omitted and the format is written.
    """
    json_out = atomic_write_json_relative_strength_report(report, json_path) if json_path is not None else None
    csv_out = atomic_write_csv_relative_strength_report(report, csv_path) if csv_path is not None else None
    md_out = atomic_write_markdown_relative_strength_report(report, md_path) if md_path is not None else None
    return json_out, csv_out, md_out
