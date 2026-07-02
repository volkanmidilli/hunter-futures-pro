"""Writer for hunter.open_interest package. MVP-25 — Open Interest Engine.

Deterministic JSON, CSV, and Markdown serialization for OpenInterestReport
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
from enum import Enum
from pathlib import Path
from typing import Any

from hunter.open_interest.models import (
    OpenInterestConfig,
    OpenInterestDataQuality,
    OpenInterestPeriodChange,
    OpenInterestReport,
    OpenInterestSafetyFlags,
    OpenInterestScore,
    OpenInterestUniverseSummary,
)

DEFAULT_JSON_PATH = Path("data/open_interest/latest_open_interest_report.json")
DEFAULT_CSV_PATH = Path("data/open_interest/latest_open_interest_scores.csv")
DEFAULT_MD_PATH = Path("reports/open_interest/latest_open_interest_report.md")

_SAFETY_NOTICE = (
    "This local open interest report is a human-audit / research-only artifact. "
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


def _config_to_dict(config: OpenInterestConfig) -> dict[str, Any]:
    """Serialize OpenInterestConfig to a JSON-safe dict."""
    return {
        "lookback_periods": list(config.lookback_periods),
        "positioning_threshold": config.positioning_threshold,
        "oi_change_bounds": list(config.oi_change_bounds),
        "price_change_bounds": list(config.price_change_bounds),
        "funding_rate_bounds": list(config.funding_rate_bounds),
        "min_required_rows": config.min_required_rows,
        "block_on_missing_data": config.block_on_missing_data,
        "score_weights": dict(sorted(config.score_weights.items())),
        "rounding_policy": config.rounding_policy,
        "version": config.version,
    }


def _safety_flags_to_dict(flags: OpenInterestSafetyFlags) -> dict[str, Any]:
    """Serialize OpenInterestSafetyFlags to a JSON-safe dict."""
    return {
        "human_research_only": flags.human_research_only,
        "output_is_human_research_only": flags.output_is_human_research_only,
        "output_not_trading_signal": flags.output_not_trading_signal,
        "output_not_trade_approval": flags.output_not_trade_approval,
        "output_not_strategy_approval": flags.output_not_strategy_approval,
        "output_not_execution_approval": flags.output_not_execution_approval,
        "output_not_portfolio_approval": flags.output_not_portfolio_approval,
        "output_not_universe_approval": flags.output_not_universe_approval,
        "output_not_freqtrade_input": flags.output_not_freqtrade_input,
        "output_not_order_input": flags.output_not_order_input,
        "output_not_exchange_input": flags.output_not_exchange_input,
        "no_action_commands_emitted": flags.no_action_commands_emitted,
        "inputs_already_loaded": flags.inputs_already_loaded,
        "benchmarks_provided_by_caller": flags.benchmarks_provided_by_caller,
        "file_write_enabled": flags.file_write_enabled,
        "file_read_enabled": flags.file_read_enabled,
        "network_enabled": flags.network_enabled,
        "database_enabled": flags.database_enabled,
        "event_store_enabled": flags.event_store_enabled,
        "runtime_registry_enabled": flags.runtime_registry_enabled,
        "task_runner_enabled": flags.task_runner_enabled,
        "indexer_crawler_enabled": flags.indexer_crawler_enabled,
        "feedback_into_execution": flags.feedback_into_execution,
        "feedback_into_strategy": flags.feedback_into_strategy,
        "feedback_into_portfolio": flags.feedback_into_portfolio,
        "feedback_into_freqtrade": flags.feedback_into_freqtrade,
        "leverage_enabled": flags.leverage_enabled,
        "shorting_enabled": flags.shorting_enabled,
        "real_orders_enabled": flags.real_orders_enabled,
        "live_trading_enabled": flags.live_trading_enabled,
    }


def _data_quality_to_dict(data_quality: OpenInterestDataQuality) -> dict[str, Any]:
    """Serialize OpenInterestDataQuality to a JSON-safe dict."""
    return {
        "expected_rows": data_quality.expected_rows,
        "actual_rows": data_quality.actual_rows,
        "missing_rows": data_quality.missing_rows,
        "min_required_rows_met": data_quality.min_required_rows_met,
        "stale_input_count": data_quality.stale_input_count,
        "reason_codes": list(data_quality.reason_codes),
    }


def _period_change_to_dict(pc: OpenInterestPeriodChange) -> dict[str, Any]:
    """Serialize OpenInterestPeriodChange to a JSON-safe dict."""
    return {
        "period": pc.period,
        "oi_change": _round_value(pc.oi_change) if pc.oi_change is not None else None,
        "price_change": _round_value(pc.price_change) if pc.price_change is not None else None,
        "has_data": pc.has_data,
        "reason_codes": list(pc.reason_codes),
    }


def _score_to_dict(score: OpenInterestScore) -> dict[str, Any]:
    """Serialize OpenInterestScore to a JSON-safe dict."""
    return {
        "pair": score.pair,
        "state": score.state.value,
        "positioning": score.positioning.value,
        "trend": score.trend.value,
        "funding_context": score.funding_context.value,
        "total_score": _round_value(score.total_score, 2),
        "period_changes": [_period_change_to_dict(pc) for pc in score.period_changes],
        "latest_oi": _round_value(score.latest_oi) if score.latest_oi is not None else None,
        "latest_price": _round_value(score.latest_price) if score.latest_price is not None else None,
        "latest_funding_rate": _round_value(score.latest_funding_rate) if score.latest_funding_rate is not None else None,
        "sub_scores": {k: _round_value(v, 4) for k, v in sorted(score.sub_scores.items())},
        "data_quality": _data_quality_to_dict(score.data_quality),
        "human_note": score.human_note,
        "reason_codes": list(score.reason_codes),
        "metadata": _serialize_value(score.metadata),
    }


def _universe_summary_to_dict(summary: OpenInterestUniverseSummary) -> dict[str, Any]:
    """Serialize OpenInterestUniverseSummary to a JSON-safe dict."""
    return {
        "total_pairs": summary.total_pairs,
        "ready_count": summary.ready_count,
        "insufficient_data_count": summary.insufficient_data_count,
        "blocked_count": summary.blocked_count,
        "expanding_count": summary.expanding_count,
        "contracting_count": summary.contracting_count,
        "flat_count": summary.flat_count,
        "unstable_count": summary.unstable_count,
        "price_up_oi_up_count": summary.price_up_oi_up_count,
        "price_up_oi_down_count": summary.price_up_oi_down_count,
        "price_down_oi_up_count": summary.price_down_oi_up_count,
        "price_down_oi_down_count": summary.price_down_oi_down_count,
        "mixed_count": summary.mixed_count,
        "average_total_score": _round_value(summary.average_total_score, 2) if summary.average_total_score is not None else None,
        "top_expanding_pair": summary.top_expanding_pair,
        "top_contracting_pair": summary.top_contracting_pair,
        "data_quality": _data_quality_to_dict(summary.data_quality),
        "summary_narrative": summary.summary_narrative,
        "reason_codes": list(summary.reason_codes),
    }


def open_interest_report_to_dict(report: OpenInterestReport) -> dict[str, Any]:
    """Serialize OpenInterestReport to a JSON-safe dict deterministically."""
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
        "reason_codes": list(report.reason_codes),
        "metadata": _serialize_value(report.metadata),
    }


# ---------------------------------------------------------------------------
# Text serializers
# ---------------------------------------------------------------------------


def open_interest_report_to_json_text(report: OpenInterestReport) -> str:
    """Return a deterministic JSON text representation of the report."""
    data = open_interest_report_to_dict(report)
    return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


_CSV_COLUMNS = (
    "report_id",
    "generated_at",
    "pair",
    "state",
    "positioning",
    "trend",
    "funding_context",
    "total_score",
    "oi_change_1d",
    "oi_change_3d",
    "oi_change_7d",
    "oi_change_14d",
    "price_change_1d",
    "price_change_3d",
    "price_change_7d",
    "price_change_14d",
    "latest_oi",
    "latest_price",
    "latest_funding_rate",
    "reason_codes",
    "human_note",
)


def _period_change_value(
    period_changes: tuple[OpenInterestPeriodChange, ...],
    period: int,
    field: str,
) -> float | None:
    """Return a field from an OpenInterestPeriodChange with the given period."""
    for pc in period_changes:
        if pc.period == period:
            value = getattr(pc, field)
            return _round_value(value, 8) if value is not None else None
    return None


def open_interest_report_to_csv_text(report: OpenInterestReport) -> str:
    """Return a deterministic CSV text representation of the report."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(_CSV_COLUMNS)

    for score in report.scores:
        row: list[Any] = [
            report.report_id,
            _iso(report.generated_at),
            score.pair,
            score.state.value,
            score.positioning.value,
            score.trend.value,
            score.funding_context.value,
            _round_value(score.total_score, 2),
            _period_change_value(score.period_changes, 1, "oi_change"),
            _period_change_value(score.period_changes, 3, "oi_change"),
            _period_change_value(score.period_changes, 7, "oi_change"),
            _period_change_value(score.period_changes, 14, "oi_change"),
            _period_change_value(score.period_changes, 1, "price_change"),
            _period_change_value(score.period_changes, 3, "price_change"),
            _period_change_value(score.period_changes, 7, "price_change"),
            _period_change_value(score.period_changes, 14, "price_change"),
            _round_value(score.latest_oi) if score.latest_oi is not None else "",
            _round_value(score.latest_price) if score.latest_price is not None else "",
            _round_value(score.latest_funding_rate) if score.latest_funding_rate is not None else "",
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


def open_interest_report_to_markdown(report: OpenInterestReport) -> str:
    """Render OpenInterestReport as Markdown with a safety notice."""
    summary = report.universe_summary
    dq = summary.data_quality

    lines: list[str] = [
        "# Open Interest Report",
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
        f"- **total_pairs**: {summary.total_pairs}",
        f"- **ready**: {summary.ready_count}",
        f"- **insufficient_data**: {summary.insufficient_data_count}",
        f"- **blocked**: {summary.blocked_count}",
        f"- **expanding**: {summary.expanding_count}",
        f"- **contracting**: {summary.contracting_count}",
        f"- **flat**: {summary.flat_count}",
        f"- **unstable**: {summary.unstable_count}",
        f"- **price_up_oi_up**: {summary.price_up_oi_up_count}",
        f"- **price_up_oi_down**: {summary.price_up_oi_down_count}",
        f"- **price_down_oi_up**: {summary.price_down_oi_up_count}",
        f"- **price_down_oi_down**: {summary.price_down_oi_down_count}",
        f"- **mixed**: {summary.mixed_count}",
        f"- **top_expanding_pair**: {summary.top_expanding_pair or '_none_'}",
        f"- **top_contracting_pair**: {summary.top_contracting_pair or '_none_'}",
        f"- **average_total_score**: {_round_value(summary.average_total_score, 2) if summary.average_total_score is not None else '_none_'}",
        f"- **summary_narrative**: {summary.summary_narrative}",
        "",
        "## Data Quality",
        "",
        f"- **expected_rows**: {dq.expected_rows}",
        f"- **actual_rows**: {dq.actual_rows}",
        f"- **missing_rows**: {dq.missing_rows}",
        f"- **min_required_rows_met**: {dq.min_required_rows_met}",
        f"- **stale_input_count**: {dq.stale_input_count}",
        f"- **reason_codes**: {', '.join(dq.reason_codes) if dq.reason_codes else '_none_'}",
        "",
    ]

    lines.extend([
        "## Scores",
        "",
        "| pair | state | positioning | trend | funding_context | total_score | oi_change_7d | price_change_7d | reason_codes | human_note |",
        "|------|-------|-------------|-------|-----------------|-------------|--------------|-----------------|--------------|------------|",
    ])
    for score in report.scores:
        oi_7d = _period_change_value(score.period_changes, 7, "oi_change")
        price_7d = _period_change_value(score.period_changes, 7, "price_change")
        lines.append(
            f"| {_md_value(score.pair)} | {_md_value(score.state.value)} | "
            f"{_md_value(score.positioning.value)} | {_md_value(score.trend.value)} | "
            f"{_md_value(score.funding_context.value)} | {_md_value(_round_value(score.total_score, 2))} | "
            f"{_md_value(oi_7d)} | {_md_value(price_7d)} | "
            f"{_md_value('|'.join(score.reason_codes))} | {_md_value(score.human_note)} |"
        )
    lines.append("")

    lines.extend([
        "## Period Changes",
        "",
        "| pair | period | oi_change | price_change | has_data |",
        "|------|--------|-----------|--------------|----------|",
    ])
    for score in report.scores:
        for pc in score.period_changes:
            lines.append(
                f"| {_md_value(score.pair)} | {_md_value(pc.period)} | "
                f"{_md_value(_round_value(pc.oi_change, 8) if pc.oi_change is not None else '')} | "
                f"{_md_value(_round_value(pc.price_change, 8) if pc.price_change is not None else '')} | "
                f"{_md_value(pc.has_data)} |"
            )
    lines.append("")

    lines.extend([
        "## Funding Context",
        "",
        "| pair | funding_context | latest_funding_rate |",
        "|------|-----------------|---------------------|",
    ])
    for score in report.scores:
        lines.append(
            f"| {_md_value(score.pair)} | {_md_value(score.funding_context.value)} | "
            f"{_md_value(_round_value(score.latest_funding_rate, 8) if score.latest_funding_rate is not None else '')} |"
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


def atomic_write_json_open_interest_report(
    report: OpenInterestReport,
    path: str | Path | None = None,
) -> Path:
    """Serialize OpenInterestReport to JSON and write atomically."""
    target = _coerce_path(path, DEFAULT_JSON_PATH)
    _atomic_write(target, open_interest_report_to_json_text(report))
    return target


def atomic_write_csv_open_interest_report(
    report: OpenInterestReport,
    path: str | Path | None = None,
) -> Path:
    """Serialize OpenInterestReport to CSV and write atomically."""
    target = _coerce_path(path, DEFAULT_CSV_PATH)
    _atomic_write(target, open_interest_report_to_csv_text(report))
    return target


def atomic_write_markdown_open_interest_report(
    report: OpenInterestReport,
    path: str | Path | None = None,
) -> Path:
    """Serialize OpenInterestReport to Markdown and write atomically."""
    target = _coerce_path(path, DEFAULT_MD_PATH)
    _atomic_write(target, open_interest_report_to_markdown(report) + "\n")
    return target


_DEFAULT_PATH = object()


def write_open_interest_report(
    report: OpenInterestReport,
    json_path: str | Path | None | object = _DEFAULT_PATH,
    csv_path: str | Path | None | object = _DEFAULT_PATH,
    md_path: str | Path | None | object = _DEFAULT_PATH,
) -> tuple[Path | None, Path | None, Path | None]:
    """Write OpenInterestReport to JSON, CSV, and Markdown as requested.

    Pass None for a format to skip writing that artifact. Default paths are used
    when a path is omitted and the format is written.
    """
    json_out = (
        atomic_write_json_open_interest_report(
            report, None if json_path is _DEFAULT_PATH else json_path
        )
        if json_path is not None
        else None
    )
    csv_out = (
        atomic_write_csv_open_interest_report(
            report, None if csv_path is _DEFAULT_PATH else csv_path
        )
        if csv_path is not None
        else None
    )
    md_out = (
        atomic_write_markdown_open_interest_report(
            report, None if md_path is _DEFAULT_PATH else md_path
        )
        if md_path is not None
        else None
    )
    return json_out, csv_out, md_out
