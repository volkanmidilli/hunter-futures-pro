"""Writer for hunter.review_search package.

Serializes SearchResult to JSON and Markdown with atomic writes.

Safety boundary:
- Local search result artifacts are human-audit catalog artifacts only.
- They are not trading signals or trade approvals.
- File references are serialized as strings only; they are never opened,
  traversed, followed, validated, or executed here.
- This module performs local writes only to caller-provided paths.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from hunter.review_search.models import (
    SearchResult,
    SearchResultEntry,
    SearchResultSummary,
    SearchSafetyFlags,
    SearchState,
)


DEFAULT_SEARCH_JSON_PATH = Path("data/review_search/latest_search_result.json")
DEFAULT_SEARCH_MARKDOWN_PATH = Path("reports/review_search/latest_search_result.md")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _iso(dt: datetime | None) -> str | None:
    """Serialize datetime to ISO-8601 with Z suffix when UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    if dt.utcoffset() == timezone.utc.utcoffset(dt):
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return dt.isoformat()


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
        return {str(k): _serialize_value(v) for k, v in value.items()}
    return value


# ---------------------------------------------------------------------------
# Dict serialization
# ---------------------------------------------------------------------------

def search_safety_flags_to_dict(flags: SearchSafetyFlags) -> dict[str, Any]:
    """Serialize SearchSafetyFlags to a JSON-safe dict without mutating input."""
    return {
        "dashboard_enabled": flags.dashboard_enabled,
        "database_persistence_enabled": flags.database_persistence_enabled,
        "dry_run": flags.dry_run,
        "file_reference_traversal_enabled": flags.file_reference_traversal_enabled,
        "index_feedback_into_execution": flags.index_feedback_into_execution,
        "leverage_enabled": flags.leverage_enabled,
        "live_trading_enabled": flags.live_trading_enabled,
        "operator_feedback_into_execution": flags.operator_feedback_into_execution,
        "real_orders_enabled": flags.real_orders_enabled,
        "report_feedback_into_execution": flags.report_feedback_into_execution,
        "search_feedback_into_execution": flags.search_feedback_into_execution,
        "search_output_is_human_audit_only": flags.search_output_is_human_audit_only,
        "search_output_not_for_execution": flags.search_output_not_for_execution,
        "search_output_not_for_exchange": flags.search_output_not_for_exchange,
        "search_output_not_for_freqtrade": flags.search_output_not_for_freqtrade,
        "search_output_not_for_order": flags.search_output_not_for_order,
        "search_output_not_for_strategy": flags.search_output_not_for_strategy,
        "search_output_not_trade_approval": flags.search_output_not_trade_approval,
        "search_output_not_trading_signal": flags.search_output_not_trading_signal,
        "shorting_enabled": flags.shorting_enabled,
        "web_ui_enabled": flags.web_ui_enabled,
    }


def search_result_entry_to_dict(entry: SearchResultEntry) -> dict[str, Any]:
    """Serialize SearchResultEntry to a JSON-safe dict without mutating input."""
    return {
        "audit_id": entry.audit_id,
        "audit_generated_at": _iso(entry.audit_generated_at),
        "entry_id": entry.entry_id,
        "entry_kind": entry.entry_kind.value,
        "index_state": entry.index_state.value,
        "local_report_reference": entry.local_report_reference,
        "local_review_reference": entry.local_review_reference,
        "metadata": _serialize_value(entry.metadata) if entry.metadata else {},
        "reason_codes": list(entry.reason_codes),
        "report_generated_at": _iso(entry.report_generated_at),
        "report_id": entry.report_id,
        "review_status": entry.review_status,
        "reviewer": entry.reviewer,
        "reviewed_at": _iso(entry.reviewed_at),
        "score": entry.score,
        "tags": list(entry.tags),
    }


def search_result_summary_to_dict(summary: SearchResultSummary) -> dict[str, Any]:
    """Serialize SearchResultSummary to a JSON-safe dict without mutating input."""
    return {
        "blocked_count": summary.blocked_count,
        "matched_entries": summary.matched_entries,
        "ready_count": summary.ready_count,
        "reason_counts": dict(summary.reason_counts) if summary.reason_counts else {},
        "returned_entries": summary.returned_entries,
        "total_entries": summary.total_entries,
        "unknown_count": summary.unknown_count,
    }


def search_result_to_dict(result: SearchResult) -> dict[str, Any]:
    """Serialize SearchResult to a JSON-safe dict without mutating input."""
    return {
        "entries": [search_result_entry_to_dict(entry) for entry in result.entries],
        "generated_at": _iso(result.generated_at),
        "metadata": _serialize_value(result.metadata) if result.metadata else {},
        "query": {
            "filters": {
                "audit_ids": list(result.query.filters.audit_ids),
                "entry_kinds": [k.value for k in result.query.filters.entry_kinds],
                "generated_at_from": _iso(result.query.filters.generated_at_from),
                "generated_at_to": _iso(result.query.filters.generated_at_to),
                "index_states": [s.value for s in result.query.filters.index_states],
                "local_reference_contains": list(result.query.filters.local_reference_contains),
                "metadata_text": list(result.query.filters.metadata_text),
                "reason_codes": list(result.query.filters.reason_codes),
                "report_ids": list(result.query.filters.report_ids),
                "reviewers": list(result.query.filters.reviewers),
                "reviewed_at_from": _iso(result.query.filters.reviewed_at_from),
                "reviewed_at_to": _iso(result.query.filters.reviewed_at_to),
                "tags": list(result.query.filters.tags),
            },
            "include_blocked_entries": result.query.include_blocked_entries,
            "limit": result.query.limit,
            "match_mode": result.query.match_mode.value,
            "query_text": result.query.query_text,
            "sort": result.query.sort.value,
        },
        "reason_codes": list(result.reason_codes),
        "safety_flags": search_safety_flags_to_dict(result.safety_flags),
        "search_id": result.search_id,
        "search_state": result.search_state.value,
        "summary": search_result_summary_to_dict(result.summary),
    }


# ---------------------------------------------------------------------------
# Markdown serialization
# ---------------------------------------------------------------------------

_SAFETY_NOTICE = (
    "This local search result is a human-audit catalog artifact only. "
    "It is not a trading signal, not trade approval, and must not be "
    "consumed by execution, strategy, Freqtrade shell, order, exchange, "
    "or any MVP execution path."
)


def search_result_to_markdown(result: SearchResult) -> str:
    """Render SearchResult as human-readable Markdown."""
    lines: list[str] = [
        "# Review Search Result — Human Audit Only",
        "",
        f"> {_SAFETY_NOTICE}",
        "",
        "## Search Info",
        "",
        f"- **search_id**: {result.search_id}",
        f"- **generated_at**: {_iso(result.generated_at)}",
        f"- **search_state**: {result.search_state.value}",
        f"- **entry_count**: {len(result.entries)}",
        "",
        "## Query",
        "",
        f"- **query_text**: {result.query.query_text!r}",
        f"- **match_mode**: {result.query.match_mode.value}",
        f"- **sort**: {result.query.sort.value}",
        f"- **limit**: {result.query.limit}",
        f"- **include_blocked_entries**: {result.query.include_blocked_entries}",
        "",
    ]

    # Filter description
    filters = result.query.filters
    lines.append("### Filters")
    lines.append("")
    if filters.index_states:
        lines.append(f"- **index_states**: {', '.join(s.value for s in filters.index_states)}")
    if filters.entry_kinds:
        lines.append(f"- **entry_kinds**: {', '.join(k.value for k in filters.entry_kinds)}")
    if filters.reason_codes:
        lines.append(f"- **reason_codes**: {', '.join(filters.reason_codes)}")
    if filters.reviewers:
        lines.append(f"- **reviewers**: {', '.join(filters.reviewers)}")
    if filters.tags:
        lines.append(f"- **tags**: {', '.join(filters.tags)}")
    if filters.report_ids:
        lines.append(f"- **report_ids**: {', '.join(filters.report_ids)}")
    if filters.audit_ids:
        lines.append(f"- **audit_ids**: {', '.join(filters.audit_ids)}")
    if filters.local_reference_contains:
        lines.append(f"- **local_reference_contains**: {', '.join(filters.local_reference_contains)}")
    if filters.metadata_text:
        lines.append(f"- **metadata_text**: {', '.join(filters.metadata_text)}")
    if filters.generated_at_from is not None:
        lines.append(f"- **generated_at_from**: {_iso(filters.generated_at_from)}")
    if filters.generated_at_to is not None:
        lines.append(f"- **generated_at_to**: {_iso(filters.generated_at_to)}")
    if filters.reviewed_at_from is not None:
        lines.append(f"- **reviewed_at_from**: {_iso(filters.reviewed_at_from)}")
    if filters.reviewed_at_to is not None:
        lines.append(f"- **reviewed_at_to**: {_iso(filters.reviewed_at_to)}")
    if not any([
        filters.index_states, filters.entry_kinds, filters.reason_codes,
        filters.reviewers, filters.tags, filters.report_ids, filters.audit_ids,
        filters.local_reference_contains, filters.metadata_text,
        filters.generated_at_from, filters.generated_at_to,
        filters.reviewed_at_from, filters.reviewed_at_to,
    ]):
        lines.append("- _No filters applied._")
    lines.append("")

    # Summary
    summary = result.summary
    lines.extend([
        "## Summary",
        "",
        f"- **total_entries**: {summary.total_entries}",
        f"- **matched_entries**: {summary.matched_entries}",
        f"- **returned_entries**: {summary.returned_entries}",
        f"- **ready_count**: {summary.ready_count}",
        f"- **blocked_count**: {summary.blocked_count}",
        f"- **unknown_count**: {summary.unknown_count}",
        "",
    ])

    lines.append("### Reason Counts")
    lines.append("")
    if summary.reason_counts:
        for code, count in summary.reason_counts.items():
            lines.append(f"- {code}: {count}")
    else:
        lines.append("- none")
    lines.append("")

    # Safety flags
    lines.extend([
        "## Safety Flags",
        "",
    ])
    for key, value in search_safety_flags_to_dict(result.safety_flags).items():
        lines.append(f"- **{key}**: {value}")
    lines.append("")

    # Reason codes
    lines.extend([
        "## Reason Codes",
        "",
    ])
    if result.reason_codes:
        for code in result.reason_codes:
            lines.append(f"- {code}")
    else:
        lines.append("- none")
    lines.append("")

    # Metadata
    if result.metadata:
        lines.extend([
            "## Metadata",
            "",
        ])
        for key, value in result.metadata.items():
            lines.append(f"- **{key}**: {value}")
        lines.append("")

    # Entries
    lines.extend([
        "## Matched Entries",
        "",
    ])
    if not result.entries:
        lines.append("_No entries matched._")
        lines.append("")
    else:
        for entry in result.entries:
            lines.extend([
                f"### {entry.entry_id}",
                "",
                f"- **entry_kind**: {entry.entry_kind.value}",
                f"- **index_state**: {entry.index_state.value}",
                f"- **report_id**: {entry.report_id}",
                f"- **score**: {entry.score}",
            ])
            if entry.audit_id:
                lines.append(f"- **audit_id**: {entry.audit_id}")
            if entry.review_status:
                lines.append(f"- **review_status**: {entry.review_status}")
            if entry.reason_codes:
                lines.append(f"- **reason_codes**: {', '.join(entry.reason_codes)}")
            if entry.tags:
                lines.append(f"- **tags**: {', '.join(entry.tags)}")
            if entry.reviewer:
                lines.append(f"- **reviewer**: {entry.reviewer}")
            if entry.local_report_reference:
                lines.append(f"- **local_report_reference**: {entry.local_report_reference}")
            if entry.local_review_reference:
                lines.append(f"- **local_review_reference**: {entry.local_review_reference}")
            if entry.report_generated_at is not None:
                lines.append(f"- **report_generated_at**: {_iso(entry.report_generated_at)}")
            if entry.reviewed_at is not None:
                lines.append(f"- **reviewed_at**: {_iso(entry.reviewed_at)}")
            if entry.metadata:
                lines.append("- **metadata**:")
                for key, value in entry.metadata.items():
                    lines.append(f"  - {key}: {value}")
            lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Atomic writes
# ---------------------------------------------------------------------------

def _atomic_write(path: Path, content: str) -> Path:
    """Write content to path atomically using temp file + fsync + os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f".{path.name}.tmp"

    try:
        tmp.write_text(content, encoding="utf-8")
        with tmp.open("rb") as handle:
            os.fsync(handle.fileno())
        os.replace(str(tmp), str(path))

        parent_fd = os.open(str(path.parent), os.O_RDONLY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    except Exception:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
        raise

    return path


def atomic_write_json_search_result(
    result: SearchResult,
    target_path: Path | None = None,
) -> Path:
    """Atomic JSON write with temp file, fsync, os.replace, cleanup."""
    path = target_path if target_path is not None else DEFAULT_SEARCH_JSON_PATH
    content = json.dumps(
        search_result_to_dict(result),
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
    )
    return _atomic_write(path, content + "\n")


def atomic_write_markdown_search_result(
    result: SearchResult,
    target_path: Path | None = None,
) -> Path:
    """Atomic Markdown write with temp file, fsync, os.replace, cleanup."""
    path = target_path if target_path is not None else DEFAULT_SEARCH_MARKDOWN_PATH
    return _atomic_write(path, search_result_to_markdown(result) + "\n")


def write_search_result(
    result: SearchResult,
    json_path: Path | None = None,
    markdown_path: Path | None = None,
) -> tuple[Path, Path]:
    """Write both JSON and Markdown search result files."""
    json_out = atomic_write_json_search_result(result, json_path)
    markdown_out = atomic_write_markdown_search_result(result, markdown_path)
    return json_out, markdown_out
