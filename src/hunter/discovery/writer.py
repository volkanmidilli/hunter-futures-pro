"""Writer for hunter.discovery package. MVP-26 — Discovery Engine.

Deterministic JSON, CSV, and Markdown serialization for DiscoveryReport with
atomic writes. Output is a human-audit / research-only artifact. It is not a
trading signal, not trade approval, not strategy approval, not execution
approval, not portfolio/universe approval, and not Freqtrade input. It does not
emit action commands, suggest orders, or create execution instructions. File
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

from hunter.discovery.models import (
    DISCOVERY_VERSION,
    DiscoveryCandidate,
    DiscoveryConfig,
    DiscoveryDataQuality,
    DiscoveryInput,
    DiscoveryInputKind,
    DiscoveryOpenInterestSummary,
    DiscoveryRelativeStrengthSummary,
    DiscoveryReport,
    DiscoverySafetyFlags,
    DiscoveryScore,
    DiscoveryUniverseSummary,
)

DEFAULT_JSON_PATH = Path("data/discovery/latest_discovery_report.json")
DEFAULT_CSV_PATH = Path("data/discovery/latest_discovery_candidates.csv")
DEFAULT_MD_PATH = Path("reports/discovery/latest_discovery_report.md")

_SAFETY_NOTICE = (
    "This local discovery report is a human-audit / research-only artifact. "
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


def _config_to_dict(config: DiscoveryConfig) -> dict[str, Any]:
    """Serialize DiscoveryConfig to a JSON-safe dict."""
    return {
        "require_relative_strength": config.require_relative_strength,
        "require_open_interest": config.require_open_interest,
        "block_on_blocked_context": config.block_on_blocked_context,
        "block_on_missing_context": config.block_on_missing_context,
        "include_excluded_candidates": config.include_excluded_candidates,
        "min_relative_strength_score": config.min_relative_strength_score,
        "min_open_interest_score": config.min_open_interest_score,
        "strong_candidate_score": config.strong_candidate_score,
        "moderate_candidate_score": config.moderate_candidate_score,
        "watchlist_score": config.watchlist_score,
        "score_weights": {k: v for k, v in sorted(config.score_weights.items())},
    }


def _safety_flags_to_dict(flags: DiscoverySafetyFlags) -> dict[str, Any]:
    """Serialize DiscoverySafetyFlags to a JSON-safe dict."""
    return {
        "has_unsafe_content": flags.has_unsafe_content,
        "has_invalid_pair": flags.has_invalid_pair,
        "has_invalid_score": flags.has_invalid_score,
        "has_blocked_context": flags.has_blocked_context,
        "has_missing_required_context": flags.has_missing_required_context,
        "has_inconsistent_state": flags.has_inconsistent_state,
        "no_action_commands_emitted": flags.no_action_commands_emitted,
        "no_network_connection": flags.no_network_connection,
        "no_file_read_in_engine": flags.no_file_read_in_engine,
        "is_safe": flags.is_safe,
    }


def _data_quality_to_dict(data_quality: DiscoveryDataQuality) -> dict[str, Any]:
    """Serialize DiscoveryDataQuality to a JSON-safe dict."""
    return {
        "total_inputs": data_quality.total_inputs,
        "pairs_with_both_contexts": data_quality.pairs_with_both_contexts,
        "pairs_with_missing_relative_strength": data_quality.pairs_with_missing_relative_strength,
        "pairs_with_missing_open_interest": data_quality.pairs_with_missing_open_interest,
        "pairs_with_blocked_context": data_quality.pairs_with_blocked_context,
        "pairs_with_insufficient_context": data_quality.pairs_with_insufficient_context,
        "reason_codes": list(data_quality.reason_codes),
    }


def _universe_summary_to_dict(summary: DiscoveryUniverseSummary) -> dict[str, Any]:
    """Serialize DiscoveryUniverseSummary to a JSON-safe dict."""
    return {
        "total_inputs": summary.total_inputs,
        "candidate_count": summary.candidate_count,
        "watchlist_count": summary.watchlist_count,
        "excluded_count": summary.excluded_count,
        "insufficient_data_count": summary.insufficient_data_count,
        "blocked_count": summary.blocked_count,
        "ready_context_count": summary.ready_context_count,
        "missing_context_count": summary.missing_context_count,
        "blocked_context_count": summary.blocked_context_count,
    }


def _rs_summary_to_dict(rs: DiscoveryRelativeStrengthSummary | None) -> Any:
    """Serialize DiscoveryRelativeStrengthSummary to a JSON-safe dict."""
    if rs is None:
        return None
    return {
        "pair": rs.pair,
        "state": rs.state,
        "decision": rs.decision,
        "total_score": _round_value(rs.total_score, 2) if rs.total_score is not None else None,
        "rank_percentile_30d": _round_value(rs.rank_percentile_30d, 2)
        if rs.rank_percentile_30d is not None
        else None,
        "reason_codes": list(rs.reason_codes),
        "metadata": _serialize_value(rs.metadata),
    }


def _oi_summary_to_dict(oi: DiscoveryOpenInterestSummary | None) -> Any:
    """Serialize DiscoveryOpenInterestSummary to a JSON-safe dict."""
    if oi is None:
        return None
    return {
        "pair": oi.pair,
        "state": oi.state,
        "positioning": oi.positioning,
        "trend": oi.trend,
        "funding_context": oi.funding_context,
        "total_score": _round_value(oi.total_score, 2) if oi.total_score is not None else None,
        "reason_codes": list(oi.reason_codes),
        "metadata": _serialize_value(oi.metadata),
    }


def _input_to_dict(inp: DiscoveryInput) -> dict[str, Any]:
    """Serialize DiscoveryInput to a JSON-safe dict."""
    return {
        "pair": inp.pair,
        "input_kind": inp.input_kind.value,
        "relative_strength": _rs_summary_to_dict(inp.relative_strength),
        "open_interest": _oi_summary_to_dict(inp.open_interest),
        "tags": list(inp.tags),
        "metadata": _serialize_value(inp.metadata),
    }


def _score_to_dict(score: DiscoveryScore) -> dict[str, Any]:
    """Serialize DiscoveryScore to a JSON-safe dict."""
    return {
        "relative_strength_score": _round_value(score.relative_strength_score, 4),
        "open_interest_score": _round_value(score.open_interest_score, 4),
        "alignment_score": _round_value(score.alignment_score, 4),
        "data_quality_score": _round_value(score.data_quality_score, 4),
        "filter_bonus_score": _round_value(score.filter_bonus_score, 4),
        "total_score": _round_value(score.total_score, 2),
        "reason_codes": list(score.reason_codes),
    }


def _candidate_to_dict(candidate: DiscoveryCandidate) -> dict[str, Any]:
    """Serialize DiscoveryCandidate to a JSON-safe dict."""
    return {
        "pair": candidate.pair,
        "state": candidate.state.value,
        "classification": candidate.classification.value,
        "score": _score_to_dict(candidate.score),
        "relative_strength": _rs_summary_to_dict(candidate.relative_strength),
        "open_interest": _oi_summary_to_dict(candidate.open_interest),
        "reason_codes": list(candidate.reason_codes),
        "tags": list(candidate.tags),
        "metadata": _serialize_value(candidate.metadata),
    }


def discovery_report_to_dict(report: DiscoveryReport) -> dict[str, Any]:
    """Serialize DiscoveryReport to a JSON-safe dict deterministically."""
    return {
        "report_id": report.report_id,
        "version": report.version,
        "generated_at": _iso(report.generated_at),
        "config": _config_to_dict(report.config),
        "inputs": [_input_to_dict(inp) for inp in report.inputs],
        "candidates": [_candidate_to_dict(c) for c in report.candidates],
        "universe_summary": _universe_summary_to_dict(report.universe_summary),
        "data_quality": _data_quality_to_dict(report.data_quality),
        "safety_flags": _safety_flags_to_dict(report.safety_flags),
        "reason_codes": list(report.reason_codes),
        "metadata": _serialize_value(report.metadata),
    }


# ---------------------------------------------------------------------------
# Text serializers
# ---------------------------------------------------------------------------


def discovery_report_to_json_text(report: DiscoveryReport) -> str:
    """Return a deterministic JSON text representation of the report."""
    data = discovery_report_to_dict(report)
    return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


_CSV_COLUMNS = (
    "report_id",
    "generated_at",
    "pair",
    "state",
    "classification",
    "total_score",
    "relative_strength_score",
    "open_interest_score",
    "alignment_score",
    "data_quality_score",
    "filter_bonus_score",
    "reason_codes",
    "human_note",
    "tags",
    "input_kind",
)


def _input_kind_by_pair(report: DiscoveryReport) -> dict[str, str]:
    """Return a mapping from pair to input_kind value."""
    return {inp.pair: inp.input_kind.value for inp in report.inputs}


def discovery_report_to_csv_text(report: DiscoveryReport) -> str:
    """Return a deterministic CSV text representation of the report."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(_CSV_COLUMNS)

    input_kinds = _input_kind_by_pair(report)
    generated_at = _iso(report.generated_at)

    for candidate in report.candidates:
        score = candidate.score
        row: list[Any] = [
            report.report_id,
            generated_at,
            candidate.pair,
            candidate.state.value,
            candidate.classification.value,
            _round_value(score.total_score, 2),
            _round_value(score.relative_strength_score, 4),
            _round_value(score.open_interest_score, 4),
            _round_value(score.alignment_score, 4),
            _round_value(score.data_quality_score, 4),
            _round_value(score.filter_bonus_score, 4),
            "|".join(candidate.reason_codes),
            "",
            "|".join(candidate.tags),
            input_kinds.get(candidate.pair, ""),
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


def discovery_report_to_markdown(report: DiscoveryReport) -> str:
    """Render DiscoveryReport as Markdown with a safety notice."""
    summary = report.universe_summary
    dq = report.data_quality
    config = report.config

    lines: list[str] = [
        "# Discovery Report",
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
        f"| Total inputs | {_md_value(summary.total_inputs)} |",
        f"| Candidates | {_md_value(summary.candidate_count)} |",
        f"| Watchlist | {_md_value(summary.watchlist_count)} |",
        f"| Excluded | {_md_value(summary.excluded_count)} |",
        f"| Insufficient data | {_md_value(summary.insufficient_data_count)} |",
        f"| Blocked | {_md_value(summary.blocked_count)} |",
        f"| Ready context | {_md_value(summary.ready_context_count)} |",
        f"| Missing context | {_md_value(summary.missing_context_count)} |",
        f"| Blocked context | {_md_value(summary.blocked_context_count)} |",
        "",
        "## Data Quality",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total inputs | {_md_value(dq.total_inputs)} |",
        f"| Pairs with both contexts | {_md_value(dq.pairs_with_both_contexts)} |",
        f"| Pairs with missing relative strength | {_md_value(dq.pairs_with_missing_relative_strength)} |",
        f"| Pairs with missing open interest | {_md_value(dq.pairs_with_missing_open_interest)} |",
        f"| Pairs with blocked context | {_md_value(dq.pairs_with_blocked_context)} |",
        f"| Pairs with insufficient context | {_md_value(dq.pairs_with_insufficient_context)} |",
        f"| Reason codes | {_md_value(', '.join(dq.reason_codes) if dq.reason_codes else '_none_')} |",
        "",
        "## Candidate Table",
        "",
        "| Pair | State | Classification | Total Score | RS Score | OI Score | Alignment | Data Quality | Filter Bonus | Reason Codes | Tags |",
        "|------|-------|----------------|-------------|----------|----------|-----------|--------------|--------------|--------------|------|",
    ]

    input_kinds = _input_kind_by_pair(report)
    for candidate in report.candidates:
        score = candidate.score
        lines.append(
            f"| {_md_value(candidate.pair)} | {_md_value(candidate.state.value)} | "
            f"{_md_value(candidate.classification.value)} | {_md_score(score.total_score)} | "
            f"{_md_score(score.relative_strength_score)} | {_md_score(score.open_interest_score)} | "
            f"{_md_score(score.alignment_score)} | {_md_score(score.data_quality_score)} | "
            f"{_md_score(score.filter_bonus_score)} | {_md_value('|'.join(candidate.reason_codes))} | "
            f"{_md_value('|'.join(candidate.tags))} |"
        )
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
    for candidate in report.candidates:
        for code in candidate.reason_codes:
            if code in {
                "LOW_RELATIVE_STRENGTH_SCORE",
                "LOW_OPEN_INTEREST_SCORE",
                "MISALIGNED_CONTEXT",
                "PASSED_DISCOVERY_FILTERS",
            }:
                filter_reason_counts[code] = filter_reason_counts.get(code, 0) + 1
    lines.extend([
        "## Filter Diagnostics",
        "",
        "| Filter | Threshold |",
        "|--------|-----------|",
        f"| min_relative_strength_score | {_md_value(config.min_relative_strength_score)} |",
        f"| min_open_interest_score | {_md_value(config.min_open_interest_score)} |",
        f"| strong_candidate_score | {_md_value(config.strong_candidate_score)} |",
        f"| moderate_candidate_score | {_md_value(config.moderate_candidate_score)} |",
        f"| watchlist_score | {_md_value(config.watchlist_score)} |",
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


def atomic_write_json_discovery_report(
    report: DiscoveryReport,
    path: str | Path | None = None,
) -> Path:
    """Serialize DiscoveryReport to JSON and write atomically."""
    target = _coerce_path(path, DEFAULT_JSON_PATH)
    _atomic_write(target, discovery_report_to_json_text(report))
    return target


def atomic_write_csv_discovery_report(
    report: DiscoveryReport,
    path: str | Path | None = None,
) -> Path:
    """Serialize DiscoveryReport to CSV and write atomically."""
    target = _coerce_path(path, DEFAULT_CSV_PATH)
    _atomic_write(target, discovery_report_to_csv_text(report))
    return target


def atomic_write_markdown_discovery_report(
    report: DiscoveryReport,
    path: str | Path | None = None,
) -> Path:
    """Serialize DiscoveryReport to Markdown and write atomically."""
    target = _coerce_path(path, DEFAULT_MD_PATH)
    _atomic_write(target, discovery_report_to_markdown(report) + "\n")
    return target


_DEFAULT_PATH = object()


def write_discovery_report(
    report: DiscoveryReport,
    json_path: str | Path | None | object = _DEFAULT_PATH,
    csv_path: str | Path | None | object = _DEFAULT_PATH,
    md_path: str | Path | None | object = _DEFAULT_PATH,
) -> tuple[Path | None, Path | None, Path | None]:
    """Write DiscoveryReport to JSON, CSV, and Markdown as requested.

    Pass None for a format to skip writing that artifact. Default paths are used
    when a path is omitted and the format is written.
    """
    json_out = (
        atomic_write_json_discovery_report(
            report, None if json_path is _DEFAULT_PATH else json_path
        )
        if json_path is not None
        else None
    )
    csv_out = (
        atomic_write_csv_discovery_report(
            report, None if csv_path is _DEFAULT_PATH else csv_path
        )
        if csv_path is not None
        else None
    )
    md_out = (
        atomic_write_markdown_discovery_report(
            report, None if md_path is _DEFAULT_PATH else md_path
        )
        if md_path is not None
        else None
    )
    return json_out, csv_out, md_out
