"""Writer for hunter.portfolio_construction package. MVP-27 — Portfolio Construction Engine.

Deterministic JSON, CSV, and Markdown serialization for PortfolioConstructionReport
with atomic writes. Output is a human-audit / research-only artifact. It is not a
trading signal, not trade approval, not strategy approval, not execution approval,
not portfolio/universe approval, and not Freqtrade input. It does not emit action
commands, suggest orders, or create execution instructions. File references and
metadata strings are serialized as opaque strings only; they are never opened,
traversed, validated, followed, or executed here.
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

from hunter.portfolio_construction.models import (
    PORTFOLIO_CONSTRUCTION_VERSION,
    PortfolioConstructionConfig,
    PortfolioConstructionDataQuality,
    PortfolioConstructionInput,
    PortfolioConstructionInputKind,
    PortfolioConstructionReport,
    PortfolioConstructionSafetyFlags,
    PortfolioConstructionScore,
    PortfolioConstructionUniverseSummary,
    PortfolioDiscoverySummary,
)

DEFAULT_JSON_PATH = Path("data/portfolio_construction/latest_portfolio_construction_report.json")
DEFAULT_CSV_PATH = Path("data/portfolio_construction/latest_portfolio_construction_allocations.csv")
DEFAULT_MD_PATH = Path("reports/portfolio_construction/latest_portfolio_construction_report.md")

_SAFETY_NOTICE = (
    "This local portfolio construction report is a human-audit / research-only artifact. "
    "It is not a trading signal, not trade approval, not strategy approval, not execution approval, "
    "not portfolio/universe approval, and not Freqtrade input. It must not be consumed by execution, "
    "strategy, Freqtrade shell, order, exchange, or any MVP execution path. "
    "No action commands, trading instructions, or order suggestions are emitted. "
    "Research weights shown below are not position sizes, not trade sizes, and not orders."
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


def _config_to_dict(config: PortfolioConstructionConfig) -> dict[str, Any]:
    """Serialize PortfolioConstructionConfig to a JSON-safe dict."""
    return {
        "require_discovery_context": config.require_discovery_context,
        "block_on_blocked_context": config.block_on_blocked_context,
        "block_on_missing_context": config.block_on_missing_context,
        "include_excluded_candidates": config.include_excluded_candidates,
        "block_duplicate_tags": config.block_duplicate_tags,
        "min_discovery_score": config.min_discovery_score,
        "watchlist_score": config.watchlist_score,
        "core_allocation_score": config.core_allocation_score,
        "satellite_allocation_score": config.satellite_allocation_score,
        "max_candidate_count": config.max_candidate_count,
        "max_single_weight_pct": config.max_single_weight_pct,
        "total_research_weight_pct": config.total_research_weight_pct,
        "score_weights": {k: v for k, v in sorted(config.score_weights.items())},
    }


def _safety_flags_to_dict(flags: PortfolioConstructionSafetyFlags) -> dict[str, Any]:
    """Serialize PortfolioConstructionSafetyFlags to a JSON-safe dict."""
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
        "has_invalid_score": flags.has_invalid_score,
        "has_blocked_context": flags.has_blocked_context,
        "has_missing_required_context": flags.has_missing_required_context,
        "has_inconsistent_state": flags.has_inconsistent_state,
        "has_duplicate_tags": flags.has_duplicate_tags,
        "is_safe": flags.is_safe,
    }


def _data_quality_to_dict(data_quality: PortfolioConstructionDataQuality) -> dict[str, Any]:
    """Serialize PortfolioConstructionDataQuality to a JSON-safe dict."""
    return {
        "total_inputs": data_quality.total_inputs,
        "included_count": data_quality.included_count,
        "capped_count": data_quality.capped_count,
        "watchlist_count": data_quality.watchlist_count,
        "excluded_count": data_quality.excluded_count,
        "insufficient_data_count": data_quality.insufficient_data_count,
        "blocked_count": data_quality.blocked_count,
        "ready_context_count": data_quality.ready_context_count,
        "missing_context_count": data_quality.missing_context_count,
        "blocked_context_count": data_quality.blocked_context_count,
        "total_final_weight_pct": _round_value(data_quality.total_final_weight_pct, 4),
        "total_research_weight_pct": _round_value(data_quality.total_research_weight_pct, 4),
        "data_quality_score": _round_value(data_quality.data_quality_score, 4),
        "sections_present": data_quality.sections_present,
        "all_sections_present": data_quality.all_sections_present,
        "all_counts_consistent": data_quality.all_counts_consistent,
        "total_weight_within_tolerance": data_quality.total_weight_within_tolerance,
        "has_unsafe_content": data_quality.has_unsafe_content,
        "safety_flags_ok": data_quality.safety_flags_ok,
    }


def _universe_summary_to_dict(summary: PortfolioConstructionUniverseSummary) -> dict[str, Any]:
    """Serialize PortfolioConstructionUniverseSummary to a JSON-safe dict."""
    return {
        "total_candidates": summary.total_candidates,
        "included_count": summary.included_count,
        "capped_count": summary.capped_count,
        "watchlist_count": summary.watchlist_count,
        "excluded_count": summary.excluded_count,
        "insufficient_data_count": summary.insufficient_data_count,
        "blocked_count": summary.blocked_count,
        "core_allocation_count": summary.core_allocation_count,
        "satellite_allocation_count": summary.satellite_allocation_count,
        "watchlist_allocation_count": summary.watchlist_allocation_count,
        "total_final_weight_pct": _round_value(summary.total_final_weight_pct, 4),
        "top_pair": summary.top_pair,
        "notes": list(summary.notes),
    }


def _discovery_summary_to_dict(discovery: PortfolioDiscoverySummary | None) -> Any:
    """Serialize PortfolioDiscoverySummary to a JSON-safe dict."""
    if discovery is None:
        return None
    return {
        "pair": discovery.pair,
        "state": discovery.state,
        "classification": discovery.classification,
        "discovery_score": _round_value(discovery.discovery_score, 2) if discovery.discovery_score is not None else None,
        "reason_codes": list(discovery.reason_codes),
        "tags": list(discovery.tags),
        "metadata": _serialize_value(discovery.metadata),
    }


def _input_to_dict(inp: PortfolioConstructionInput) -> dict[str, Any]:
    """Serialize PortfolioConstructionInput to a JSON-safe dict."""
    return {
        "pair": inp.pair,
        "input_kind": inp.input_kind.value,
        "discovery": _discovery_summary_to_dict(inp.discovery),
        "tags": list(inp.tags),
        "metadata": _serialize_value(inp.metadata),
    }


def _score_to_dict(score: PortfolioConstructionScore) -> dict[str, Any]:
    """Serialize PortfolioConstructionScore to a JSON-safe dict."""
    return {
        "pair": score.pair,
        "state": score.state.value,
        "classification": score.classification.value,
        "allocation_score": _round_value(score.allocation_score, 2),
        "discovery_score_component": _round_value(score.discovery_score_component, 4),
        "data_quality_score": _round_value(score.data_quality_score, 4),
        "diversification_component": _round_value(score.diversification_component, 4),
        "cap_readiness_score": _round_value(score.cap_readiness_score, 4),
        "filter_bonus_score": _round_value(score.filter_bonus_score, 4),
        "initial_research_weight_pct": _round_value(score.initial_research_weight_pct, 4),
        "capped_weight_pct": _round_value(score.capped_weight_pct, 4),
        "final_weight_pct": _round_value(score.final_weight_pct, 4),
        "reason_codes": list(score.reason_codes),
        "tags": list(score.tags),
        "metadata": _serialize_value(score.metadata),
        "notes": list(score.notes),
        "rank": score.rank,
    }


def portfolio_construction_report_to_dict(report: PortfolioConstructionReport) -> dict[str, Any]:
    """Serialize PortfolioConstructionReport to a JSON-safe dict deterministically."""
    return {
        "report_id": report.report_id,
        "version": report.version,
        "generated_at": _iso(report.generated_at),
        "config": _config_to_dict(report.config),
        "inputs": [_input_to_dict(inp) for inp in report.inputs],
        "scores": [_score_to_dict(s) for s in report.scores],
        "universe_summary": _universe_summary_to_dict(report.universe_summary),
        "data_quality": _data_quality_to_dict(report.data_quality),
        "safety_flags": _safety_flags_to_dict(report.safety_flags),
        "reason_codes": list(report.reason_codes),
        "metadata": _serialize_value(report.metadata),
        "notes": list(report.notes),
    }


# ---------------------------------------------------------------------------
# Text serializers
# ---------------------------------------------------------------------------


def portfolio_construction_report_to_json_text(report: PortfolioConstructionReport) -> str:
    """Return a deterministic JSON text representation of the report."""
    data = portfolio_construction_report_to_dict(report)
    return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


_CSV_COLUMNS = (
    "report_id",
    "generated_at",
    "pair",
    "state",
    "classification",
    "allocation_score",
    "discovery_score_component",
    "data_quality_score",
    "diversification_component",
    "cap_readiness_score",
    "filter_bonus_score",
    "initial_research_weight_pct",
    "capped_weight_pct",
    "final_weight_pct",
    "reason_codes",
    "tags",
    "rank",
    "input_kind",
)


def _input_kind_by_pair(report: PortfolioConstructionReport) -> dict[str, str]:
    """Return a mapping from pair to input_kind value."""
    return {inp.pair: inp.input_kind.value for inp in report.inputs}


def portfolio_construction_report_to_csv_text(report: PortfolioConstructionReport) -> str:
    """Return a deterministic CSV text representation of the report."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(_CSV_COLUMNS)

    input_kinds = _input_kind_by_pair(report)
    generated_at = _iso(report.generated_at)

    for score in report.scores:
        row: list[Any] = [
            report.report_id,
            generated_at,
            score.pair,
            score.state.value,
            score.classification.value,
            _round_value(score.allocation_score, 2),
            _round_value(score.discovery_score_component, 4),
            _round_value(score.data_quality_score, 4),
            _round_value(score.diversification_component, 4),
            _round_value(score.cap_readiness_score, 4),
            _round_value(score.filter_bonus_score, 4),
            _round_value(score.initial_research_weight_pct, 4),
            _round_value(score.capped_weight_pct, 4),
            _round_value(score.final_weight_pct, 4),
            "|".join(score.reason_codes),
            "|".join(score.tags),
            score.rank if score.rank is not None else "",
            input_kinds.get(score.pair, ""),
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


def _md_score(value: float | int | None) -> str:
    """Stringify a numeric score for Markdown."""
    if value is None:
        return ""
    return str(_round_value(value, 4))


def portfolio_construction_report_to_markdown(report: PortfolioConstructionReport) -> str:
    """Render PortfolioConstructionReport as Markdown with a safety notice."""
    summary = report.universe_summary
    dq = report.data_quality
    config = report.config

    lines: list[str] = [
        "# Portfolio Construction Report",
        "",
        f"> {_SAFETY_NOTICE}",
        "",
        "## Report Identity",
        "",
        f"- **report_id**: {report.report_id}",
        f"- **version**: {report.version}",
        f"- **generated_at**: {_iso(report.generated_at)}",
        "",
        "## Universe Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total candidates | {_md_value(summary.total_candidates)} |",
        f"| Included | {_md_value(summary.included_count)} |",
        f"| Capped | {_md_value(summary.capped_count)} |",
        f"| Watchlist | {_md_value(summary.watchlist_count)} |",
        f"| Excluded | {_md_value(summary.excluded_count)} |",
        f"| Insufficient data | {_md_value(summary.insufficient_data_count)} |",
        f"| Blocked | {_md_value(summary.blocked_count)} |",
        f"| Core allocations | {_md_value(summary.core_allocation_count)} |",
        f"| Satellite allocations | {_md_value(summary.satellite_allocation_count)} |",
        f"| Watchlist allocations | {_md_value(summary.watchlist_allocation_count)} |",
        f"| Total final weight % | {_md_value(summary.total_final_weight_pct)} |",
        f"| Top pair | {_md_value(summary.top_pair or '_none_')} |",
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
        f"| Ready context | {_md_value(dq.ready_context_count)} |",
        f"| Missing context | {_md_value(dq.missing_context_count)} |",
        f"| Blocked context | {_md_value(dq.blocked_context_count)} |",
        f"| Total final weight % | {_md_value(dq.total_final_weight_pct)} |",
        f"| Total research weight % | {_md_value(dq.total_research_weight_pct)} |",
        f"| Data quality score | {_md_value(dq.data_quality_score)} |",
        f"| Sections present | {_md_value(dq.sections_present)} |",
        f"| All counts consistent | {_md_value(dq.all_counts_consistent)} |",
        f"| Total weight within tolerance | {_md_value(dq.total_weight_within_tolerance)} |",
        f"| Has unsafe content | {_md_value(dq.has_unsafe_content)} |",
        f"| Safety flags OK | {_md_value(dq.safety_flags_ok)} |",
        "",
        "## Allocation Table",
        "",
        "| Pair | State | Classification | Allocation Score | Discovery | Data Quality | Diversification | Cap Readiness | Filter Bonus | Initial Weight % | Capped Weight % | Final Weight % | Rank | Reason Codes | Tags |",
        "|------|-------|----------------|------------------|-----------|--------------|-----------------|---------------|--------------|------------------|-----------------|----------------|------|--------------|------|",
    ]

    for score in report.scores:
        lines.append(
            f"| {_md_value(score.pair)} | {_md_value(score.state.value)} | "
            f"{_md_value(score.classification.value)} | {_md_score(score.allocation_score)} | "
            f"{_md_score(score.discovery_score_component)} | {_md_score(score.data_quality_score)} | "
            f"{_md_score(score.diversification_component)} | {_md_score(score.cap_readiness_score)} | "
            f"{_md_score(score.filter_bonus_score)} | {_md_score(score.initial_research_weight_pct)} | "
            f"{_md_score(score.capped_weight_pct)} | {_md_score(score.final_weight_pct)} | "
            f"{_md_value(score.rank if score.rank is not None else '')} | "
            f"{_md_value('|'.join(score.reason_codes))} | {_md_value('|'.join(score.tags))} |"
        )
    lines.append("")

    lines.extend([
        "## Cap Diagnostics",
        "",
        "| Setting | Value |",
        "|--------|-------|",
        f"| max_single_weight_pct | {_md_value(config.max_single_weight_pct)} |",
        f"| total_research_weight_pct | {_md_value(config.total_research_weight_pct)} |",
        "",
    ])

    cap_counts: dict[str, int] = {}
    for score in report.scores:
        if score.capped_weight_pct > 0.0 or score.final_weight_pct < score.initial_research_weight_pct - 1e-9:
            cap_counts[score.pair] = cap_counts.get(score.pair, 0) + 1
    if cap_counts:
        lines.extend(["| Capped pair | |", "|-------------|---|"])
        for pair in sorted(cap_counts):
            lines.append(f"| {_md_value(pair)} | capped |")
    else:
        lines.append("| Capped pair | _none_ |")
    lines.append("")

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

    filter_reason_counts: dict[str, int] = {}
    for score in report.scores:
        for code in score.reason_codes:
            if code in {
                "LOW_DISCOVERY_SCORE",
                "INCLUDED_BY_RESEARCH_CONSTRAINTS",
                "EXCLUDED_BY_RESEARCH_CONSTRAINTS",
                "CAPPED_BY_RESEARCH_CONSTRAINTS",
                "MAX_CANDIDATE_COUNT_EXCEEDED",
                "MAX_SINGLE_WEIGHT_CAPPED",
            }:
                filter_reason_counts[code] = filter_reason_counts.get(code, 0) + 1
    lines.extend([
        "## Filter Diagnostics",
        "",
        "| Filter | Threshold |",
        "|--------|-----------|",
        f"| min_discovery_score | {_md_value(config.min_discovery_score)} |",
        f"| watchlist_score | {_md_value(config.watchlist_score)} |",
        f"| core_allocation_score | {_md_value(config.core_allocation_score)} |",
        f"| satellite_allocation_score | {_md_value(config.satellite_allocation_score)} |",
        f"| max_candidate_count | {_md_value(config.max_candidate_count)} |",
        f"| max_single_weight_pct | {_md_value(config.max_single_weight_pct)} |",
        "",
        "| Reason Code | Count |",
        "|-------------|-------|",
    ])
    if filter_reason_counts:
        for code in sorted(filter_reason_counts):
            lines.append(f"| {code} | {filter_reason_counts[code]} |")
    else:
        lines.append("| _none_ | 0 |")
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


def atomic_write_json_portfolio_construction_report(
    report: PortfolioConstructionReport,
    path: str | Path | None = None,
) -> Path:
    """Serialize PortfolioConstructionReport to JSON and write atomically."""
    target = _coerce_path(path, DEFAULT_JSON_PATH)
    _atomic_write(target, portfolio_construction_report_to_json_text(report))
    return target


def atomic_write_csv_portfolio_construction_report(
    report: PortfolioConstructionReport,
    path: str | Path | None = None,
) -> Path:
    """Serialize PortfolioConstructionReport to CSV and write atomically."""
    target = _coerce_path(path, DEFAULT_CSV_PATH)
    _atomic_write(target, portfolio_construction_report_to_csv_text(report))
    return target


def atomic_write_markdown_portfolio_construction_report(
    report: PortfolioConstructionReport,
    path: str | Path | None = None,
) -> Path:
    """Serialize PortfolioConstructionReport to Markdown and write atomically."""
    target = _coerce_path(path, DEFAULT_MD_PATH)
    _atomic_write(target, portfolio_construction_report_to_markdown(report) + "\n")
    return target


_DEFAULT_PATH = object()


def write_portfolio_construction_report(
    report: PortfolioConstructionReport,
    json_path: str | Path | None | object = _DEFAULT_PATH,
    csv_path: str | Path | None | object = _DEFAULT_PATH,
    md_path: str | Path | None | object = _DEFAULT_PATH,
) -> tuple[Path | None, Path | None, Path | None]:
    """Write PortfolioConstructionReport to JSON, CSV, and Markdown as requested.

    Pass None for a format to skip writing that artifact. Default paths are used
    when a path is omitted and the format is written.
    """
    json_out = (
        atomic_write_json_portfolio_construction_report(
            report, None if json_path is _DEFAULT_PATH else json_path
        )
        if json_path is not None
        else None
    )
    csv_out = (
        atomic_write_csv_portfolio_construction_report(
            report, None if csv_path is _DEFAULT_PATH else csv_path
        )
        if csv_path is not None
        else None
    )
    md_out = (
        atomic_write_markdown_portfolio_construction_report(
            report, None if md_path is _DEFAULT_PATH else md_path
        )
        if md_path is not None
        else None
    )
    return json_out, csv_out, md_out
