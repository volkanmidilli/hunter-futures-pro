"""Deterministic writer for the Controlled Universe Bridge Engine (MVP-51).

The writer serializes `ControlledUniverseReport` to JSON, CSV, and Markdown.
Output is local and audit-only. It never reads from `data/` or `reports/`, and it
never follows, traverses, validates, or executes any file references.
"""

from __future__ import annotations

import csv
import io
import json
import os
from collections.abc import Mapping
from dataclasses import is_dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any

from hunter.controlled_universe.models import (
    ControlledUniverseConfig,
    ControlledUniverseDataQuality,
    ControlledUniverseItem,
    ControlledUniverseReport,
    ControlledUniverseSafetyFlags,
)


DEFAULT_JSON_PATH: Path = Path("data/controlled_universe/latest_controlled_universe.json")
DEFAULT_CSV_PATH: Path = Path("data/controlled_universe/latest_controlled_universe.csv")
DEFAULT_MD_PATH: Path = Path("reports/controlled_universe/latest_controlled_universe.md")

_SAFETY_NOTICE = (
    "This controlled universe report is a human-audit / research-only artifact. "
    "It is not a trading signal, not trade approval, not strategy approval, not execution approval, "
    "not portfolio approval, not universe approval, and not Freqtrade input. "
    "It does not emit action commands, suggest orders, or create execution instructions. "
    "All pair references are opaque identifiers and are never opened, followed, "
    "traversed, validated, fetched, or executed."
)


class ControlledUniverseWriterError(Exception):
    """Base exception for the controlled universe writer."""


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
    if value is None:
        return None
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value
    if isinstance(value, datetime):
        return _iso(value)
    if isinstance(value, (list, tuple)):
        return [_serialize_value(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return sorted(_serialize_value(v) for v in value)
    if isinstance(value, (MappingProxyType, Mapping)):
        return {str(k): _serialize_value(v) for k, v in sorted(value.items())}
    if is_dataclass(value) and not isinstance(value, type):
        return _dataclass_to_dict(value)
    return str(value)


def _dataclass_to_dict(obj: Any) -> dict[str, Any]:
    """Convert a frozen dataclass instance to a deterministic JSON-safe dict."""
    if not is_dataclass(obj) or isinstance(obj, type):
        raise TypeError(f"expected dataclass instance, got {type(obj)}")
    return {field: _serialize_value(getattr(obj, field)) for field in obj.__dataclass_fields__}


# ---------------------------------------------------------------------------
# Dict / JSON serialization
# ---------------------------------------------------------------------------


def _config_to_dict(config: ControlledUniverseConfig) -> dict[str, Any]:
    """Serialize ControlledUniverseConfig to a JSON-safe dict."""
    return {
        "max_universe_pairs": config.max_universe_pairs,
        "min_portfolio_score": config.min_portfolio_score,
        "max_watchlist_pairs": config.max_watchlist_pairs,
        "include_capped": config.include_capped,
        "default_mode": config.default_mode.value,
        "require_dry_run": config.require_dry_run,
    }


def _safety_flags_to_dict(flags: ControlledUniverseSafetyFlags) -> dict[str, Any]:
    """Serialize ControlledUniverseSafetyFlags to a JSON-safe dict."""
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
        "has_blocked_execution": flags.has_blocked_execution,
        "has_missing_execution_context": flags.has_missing_execution_context,
        "has_missing_portfolio_context": flags.has_missing_portfolio_context,
        "has_invalid_portfolio_summary": flags.has_invalid_portfolio_summary,
        "has_stale_or_invalid_data": flags.has_stale_or_invalid_data,
        "has_unsafe_content": flags.has_unsafe_content,
        "is_safe": flags.is_safe,
    }


def _data_quality_to_dict(data_quality: ControlledUniverseDataQuality) -> dict[str, Any]:
    """Serialize ControlledUniverseDataQuality to a JSON-safe dict."""
    return {
        "total_inputs": data_quality.total_inputs,
        "universe_count": data_quality.universe_count,
        "watchlist_count": data_quality.watchlist_count,
        "blocked_count": data_quality.blocked_count,
        "excluded_count": data_quality.excluded_count,
        "insufficient_data_count": data_quality.insufficient_data_count,
        "execution_context_valid": data_quality.execution_context_valid,
        "portfolio_context_valid": data_quality.portfolio_context_valid,
        "data_quality_score": data_quality.data_quality_score,
        "all_counts_consistent": data_quality.all_counts_consistent,
        "safety_flags_ok": data_quality.safety_flags_ok,
    }


def _item_to_dict(item: ControlledUniverseItem) -> dict[str, Any]:
    """Serialize ControlledUniverseItem to a JSON-safe dict."""
    return {
        "pair": item.pair,
        "state": item.state.value,
        "classification": item.classification.value,
        "reason_codes": list(item.reason_codes),
        "portfolio_score": item.portfolio_score,
        "portfolio_state": item.portfolio_state,
        "capped": item.capped,
    }


def controlled_universe_report_to_dict(report: ControlledUniverseReport) -> dict[str, Any]:
    """Convert a ControlledUniverseReport to a deterministic dictionary."""
    data: dict[str, Any] = {
        "kind": "controlled_universe_report",
        "version": report.version,
        "safety_notice": _SAFETY_NOTICE,
        "generated_at": _iso(report.generated_at),
        "config": _config_to_dict(report.config),
        "execution_state": report.execution_state,
        "allowed_mode": report.allowed_mode,
        "universe": list(report.universe),
        "watchlist": list(report.watchlist),
        "blocked": list(report.blocked),
        "items": [_item_to_dict(item) for item in report.items],
        "data_quality": _data_quality_to_dict(report.data_quality),
        "safety_flags": _safety_flags_to_dict(report.safety_flags),
        "reason_codes": list(report.reason_codes),
        "metadata": _serialize_value(report.metadata),
        "notes": list(report.notes),
    }
    return data


def controlled_universe_report_to_json_text(report: ControlledUniverseReport, *, indent: int = 2) -> str:
    """Serialize a ControlledUniverseReport to deterministic JSON text."""
    data = controlled_universe_report_to_dict(report)
    return json.dumps(data, indent=indent, ensure_ascii=False, sort_keys=True) + "\n"


# ---------------------------------------------------------------------------
# CSV serialization
# ---------------------------------------------------------------------------


_CSV_COLUMNS = (
    "pair",
    "state",
    "classification",
    "portfolio_score",
    "portfolio_state",
    "capped",
    "reason_codes",
)


def _format_reason_codes(codes: tuple[str, ...]) -> str:
    """Format reason codes for CSV using a deterministic semicolon join."""
    return ";".join(sorted(str(code) for code in codes))


def controlled_universe_report_to_csv_text(report: ControlledUniverseReport) -> str:
    """Serialize controlled universe items to deterministic CSV rows."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(_CSV_COLUMNS)
    for item in sorted(report.items, key=lambda i: (i.state.value, i.pair)):
        row = [
            item.pair,
            item.state.value,
            item.classification.value,
            item.portfolio_score if item.portfolio_score is not None else "",
            item.portfolio_state if item.portfolio_state is not None else "",
            "1" if item.capped else "0",
            _format_reason_codes(item.reason_codes),
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
    return str(value).replace("|", "\\|")


def _md_bool(value: bool) -> str:
    """Stringify a boolean for Markdown."""
    return "yes" if value else "no"


def controlled_universe_report_to_markdown(report: ControlledUniverseReport) -> str:
    """Serialize a ControlledUniverseReport to deterministic Markdown text."""
    lines: list[str] = []
    lines.append("# Controlled Universe Report")
    lines.append("")
    lines.append(f"> {_SAFETY_NOTICE}")
    lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **version:** {report.version}")
    lines.append(f"- **generated_at:** {_iso(report.generated_at)}")
    lines.append(f"- **execution_state:** {report.execution_state or '_none_'}")
    lines.append(f"- **allowed_mode:** {report.allowed_mode or '_none_'}")
    lines.append(f"- **universe_pairs:** {len(report.universe)}")
    lines.append(f"- **watchlist_pairs:** {len(report.watchlist)}")
    lines.append(f"- **blocked_pairs:** {len(report.blocked)}")
    lines.append("")
    lines.append(
        "This report is a controlled universe bridge between a macro execution context "
        "and a per-coin portfolio construction report. It is descriptive research output only."
    )
    lines.append("")

    # Universe
    lines.append("## Universe")
    lines.append("")
    if report.universe:
        for pair in sorted(report.universe):
            lines.append(f"- {pair}")
    else:
        lines.append("- _none_")
    lines.append("")

    # Watchlist
    lines.append("## Watchlist")
    lines.append("")
    if report.watchlist:
        for pair in sorted(report.watchlist):
            lines.append(f"- {pair}")
    else:
        lines.append("- _none_")
    lines.append("")

    # Blocked
    lines.append("## Blocked")
    lines.append("")
    if report.blocked:
        for pair in sorted(report.blocked):
            lines.append(f"- {pair}")
    else:
        lines.append("- _none_")
    lines.append("")

    # Items table
    lines.append("## Items")
    lines.append("")
    lines.append(
        "| pair | state | classification | portfolio_score | portfolio_state | capped | reason_codes |"
    )
    lines.append(
        "|------|-------|----------------|-----------------|-----------------|--------|--------------|"
    )
    for item in sorted(report.items, key=lambda i: (i.state.value, i.pair)):
        lines.append(
            f"| {_md_value(item.pair)} | {_md_value(item.state.value)} | "
            f"{_md_value(item.classification.value)} | {_md_value(item.portfolio_score)} | "
            f"{_md_value(item.portfolio_state)} | {_md_value(_md_bool(item.capped))} | "
            f"{_md_value(_format_reason_codes(item.reason_codes))} |"
        )
    if not report.items:
        lines.append("| _none_ | | | | | | |")
    lines.append("")

    # Data quality
    dq = report.data_quality
    lines.append("## Data Quality")
    lines.append("")
    lines.append(f"- **total_inputs:** {dq.total_inputs}")
    lines.append(f"- **universe_count:** {dq.universe_count}")
    lines.append(f"- **watchlist_count:** {dq.watchlist_count}")
    lines.append(f"- **blocked_count:** {dq.blocked_count}")
    lines.append(f"- **excluded_count:** {dq.excluded_count}")
    lines.append(f"- **insufficient_data_count:** {dq.insufficient_data_count}")
    lines.append(f"- **execution_context_valid:** {dq.execution_context_valid}")
    lines.append(f"- **portfolio_context_valid:** {dq.portfolio_context_valid}")
    lines.append(f"- **data_quality_score:** {dq.data_quality_score}")
    lines.append(f"- **all_counts_consistent:** {dq.all_counts_consistent}")
    lines.append(f"- **safety_flags_ok:** {dq.safety_flags_ok}")
    lines.append("")

    # Safety flags
    lines.append("## Safety Flags")
    lines.append("")
    for key, value in sorted(_safety_flags_to_dict(report.safety_flags).items()):
        lines.append(f"- **{key}:** {value}")
    lines.append("")

    # Reason codes
    lines.append("## Reason Codes")
    lines.append("")
    if report.reason_codes:
        for code in report.reason_codes:
            lines.append(f"- {code}")
    else:
        lines.append("- _none_")
    lines.append("")

    if report.metadata:
        lines.append("## Metadata")
        lines.append("")
        for key, value in sorted(report.metadata.items()):
            lines.append(f"- **{key}:** {value}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Atomic writes
# ---------------------------------------------------------------------------


def _coerce_path(value: str | Path | None, default: Path) -> Path:
    """Return a Path for the given value, falling back to the default."""
    if value is None:
        return default
    if isinstance(value, Path):
        return value
    return Path(value)


def _atomic_write(path: Path, content: str) -> None:
    """Write content atomically via temp file and os.replace."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(content, encoding="utf-8")
        os.replace(tmp, path)
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise


def atomic_write_json_controlled_universe_report(
    report: ControlledUniverseReport,
    path: str | Path | None = None,
) -> Path:
    """Write a JSON controlled universe report atomically."""
    target = _coerce_path(path, DEFAULT_JSON_PATH)
    _atomic_write(target, controlled_universe_report_to_json_text(report))
    return target


def atomic_write_csv_controlled_universe_report(
    report: ControlledUniverseReport,
    path: str | Path | None = None,
) -> Path:
    """Write a CSV controlled universe report atomically."""
    target = _coerce_path(path, DEFAULT_CSV_PATH)
    _atomic_write(target, controlled_universe_report_to_csv_text(report))
    return target


def atomic_write_markdown_controlled_universe_report(
    report: ControlledUniverseReport,
    path: str | Path | None = None,
) -> Path:
    """Write a Markdown controlled universe report atomically."""
    target = _coerce_path(path, DEFAULT_MD_PATH)
    _atomic_write(target, controlled_universe_report_to_markdown(report))
    return target


_DEFAULT_PATH = object()


def write_controlled_universe_report(
    report: ControlledUniverseReport,
    json_path: str | Path | None | object = _DEFAULT_PATH,
    csv_path: str | Path | None | object = _DEFAULT_PATH,
    md_path: str | Path | None | object = _DEFAULT_PATH,
) -> tuple[Path | None, Path | None, Path | None]:
    """Write ControlledUniverseReport to JSON, CSV, and Markdown as requested.

    Pass None for a format to skip writing that artifact. Default paths are used
    when a path is omitted and the format is written.
    """
    json_out = (
        atomic_write_json_controlled_universe_report(
            report, None if json_path is _DEFAULT_PATH else json_path
        )
        if json_path is not None
        else None
    )
    csv_out = (
        atomic_write_csv_controlled_universe_report(
            report, None if csv_path is _DEFAULT_PATH else csv_path
        )
        if csv_path is not None
        else None
    )
    md_out = (
        atomic_write_markdown_controlled_universe_report(
            report, None if md_path is _DEFAULT_PATH else md_path
        )
        if md_path is not None
        else None
    )
    return json_out, csv_out, md_out
