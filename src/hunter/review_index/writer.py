"""Writer for hunter.review_index package.

Serializes ReviewIndex to JSON and Markdown with atomic writes.

Safety boundary:
- Local review index artifacts are human-audit catalog artifacts only.
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

from hunter.review_index.models import (
    IndexDataQuality,
    IndexEntry,
    IndexSafetyFlags,
    IndexSummary,
    ReviewIndex,
)


DEFAULT_REVIEW_INDEX_JSON_PATH = Path("data/review_index/latest_review_index.json")
DEFAULT_REVIEW_INDEX_MARKDOWN_PATH = Path("reports/review_index/latest_review_index.md")


def _iso(dt: datetime | None) -> str | None:
    """Serialize datetime to ISO-8601 with Z suffix when UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        # Models normally prevent this. Keep serializer fail-closed rather than
        # producing ambiguous output if called directly with invalid data.
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


def index_safety_flags_to_dict(flags: IndexSafetyFlags) -> dict[str, Any]:
    """Serialize IndexSafetyFlags to a JSON-safe dict without mutating input."""
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
        "shorting_enabled": flags.shorting_enabled,
        "web_ui_enabled": flags.web_ui_enabled,
    }


def index_entry_to_dict(entry: IndexEntry) -> dict[str, Any]:
    """Serialize IndexEntry to a JSON-safe dict without mutating input."""
    return {
        "audit_generated_at": _iso(entry.audit_generated_at),
        "audit_id": entry.audit_id,
        "entry_id": entry.entry_id,
        "entry_kind": entry.entry_kind.value,
        "index_state": entry.index_state.value,
        "local_report_reference": entry.local_report_reference,
        "local_review_reference": entry.local_review_reference,
        "metadata": _serialize_value(entry.metadata) if entry.metadata else {},
        "reason_codes": list(entry.reason_codes),
        "report_generated_at": _iso(entry.report_generated_at),
        "report_id": entry.report_id,
        "review_state": entry.review_state,
        "review_status": entry.review_status,
        "reviewed_at": _iso(entry.reviewed_at),
        "reviewer": entry.reviewer,
        "safety_flags": index_safety_flags_to_dict(entry.safety_flags),
        "source_report_version": entry.source_report_version,
        "source_review_version": entry.source_review_version,
        "tags": list(entry.tags),
    }


def index_summary_to_dict(summary: IndexSummary) -> dict[str, Any]:
    """Serialize IndexSummary to a JSON-safe dict without mutating input."""
    return {
        "accepted_count": summary.accepted_count,
        "blocked_count": summary.blocked_count,
        "linked_entry_count": summary.linked_entry_count,
        "needs_investigation_count": summary.needs_investigation_count,
        "not_reviewed_count": summary.not_reviewed_count,
        "observation_report_count": summary.observation_report_count,
        "ready_count": summary.ready_count,
        "reason_counts": dict(summary.reason_counts) if summary.reason_counts else {},
        "rejected_count": summary.rejected_count,
        "review_audit_count": summary.review_audit_count,
        "total_entries": summary.total_entries,
        "unknown_count": summary.unknown_count,
    }


def index_data_quality_to_dict(data_quality: IndexDataQuality) -> dict[str, Any]:
    """Serialize IndexDataQuality to a JSON-safe dict without mutating input."""
    return {
        "invalid_reports": data_quality.invalid_reports,
        "invalid_reviews": data_quality.invalid_reviews,
        "linked_records": data_quality.linked_records,
        "total_reports": data_quality.total_reports,
        "total_reviews": data_quality.total_reviews,
        "unsafe_reports": data_quality.unsafe_reports,
        "unsafe_reviews": data_quality.unsafe_reviews,
        "unlinked_reports": data_quality.unlinked_reports,
        "unlinked_reviews": data_quality.unlinked_reviews,
        "valid_reports": data_quality.valid_reports,
        "valid_reviews": data_quality.valid_reviews,
    }


def review_index_to_dict(index: ReviewIndex) -> dict[str, Any]:
    """Serialize ReviewIndex to a JSON-safe dict without mutating input."""
    return {
        "data_quality": index_data_quality_to_dict(index.data_quality),
        "entries": [index_entry_to_dict(entry) for entry in index.entries],
        "generated_at": _iso(index.generated_at),
        "index_id": index.index_id,
        "index_state": index.index_state.value,
        "reason_codes": list(index.reason_codes),
        "safety_flags": index_safety_flags_to_dict(index.safety_flags),
        "summary": index_summary_to_dict(index.summary),
    }


_SAFETY_NOTICE = (
    "This local review index is a human-audit catalog artifact only. "
    "It is not a trading signal, not trade approval, and must not be "
    "consumed by execution, strategy, Freqtrade shell, order, exchange, "
    "or any MVP execution path."
)


def review_index_to_markdown(index: ReviewIndex) -> str:
    """Render ReviewIndex as human-readable Markdown."""
    lines: list[str] = [
        "# Review Index",
        "",
        f"> {_SAFETY_NOTICE}",
        "",
        "## Index Info",
        "",
        f"- **index_id**: {index.index_id}",
        f"- **generated_at**: {_iso(index.generated_at)}",
        f"- **index_state**: {index.index_state.value}",
        f"- **entry_count**: {len(index.entries)}",
        "",
        "## Summary",
        "",
    ]

    summary = index.summary
    lines.extend(
        [
            f"- **total_entries**: {summary.total_entries}",
            f"- **observation_report_count**: {summary.observation_report_count}",
            f"- **review_audit_count**: {summary.review_audit_count}",
            f"- **linked_entry_count**: {summary.linked_entry_count}",
            f"- **ready_count**: {summary.ready_count}",
            f"- **blocked_count**: {summary.blocked_count}",
            f"- **unknown_count**: {summary.unknown_count}",
            f"- **accepted_count**: {summary.accepted_count}",
            f"- **rejected_count**: {summary.rejected_count}",
            f"- **needs_investigation_count**: {summary.needs_investigation_count}",
            f"- **not_reviewed_count**: {summary.not_reviewed_count}",
            "",
        ]
    )

    lines.append("### Reason Counts")
    lines.append("")
    if summary.reason_counts:
        for code, count in summary.reason_counts.items():
            lines.append(f"- {code}: {count}")
    else:
        lines.append("- none")
    lines.append("")

    data_quality = index.data_quality
    lines.extend(
        [
            "## Data Quality",
            "",
            f"- **total_reports**: {data_quality.total_reports}",
            f"- **valid_reports**: {data_quality.valid_reports}",
            f"- **invalid_reports**: {data_quality.invalid_reports}",
            f"- **unsafe_reports**: {data_quality.unsafe_reports}",
            f"- **total_reviews**: {data_quality.total_reviews}",
            f"- **valid_reviews**: {data_quality.valid_reviews}",
            f"- **invalid_reviews**: {data_quality.invalid_reviews}",
            f"- **unsafe_reviews**: {data_quality.unsafe_reviews}",
            f"- **linked_records**: {data_quality.linked_records}",
            f"- **unlinked_reports**: {data_quality.unlinked_reports}",
            f"- **unlinked_reviews**: {data_quality.unlinked_reviews}",
            "",
            "## Safety Flags",
            "",
        ]
    )

    for key, value in index_safety_flags_to_dict(index.safety_flags).items():
        lines.append(f"- **{key}**: {value}")
    lines.append("")

    lines.append("## Reason Codes")
    lines.append("")
    if index.reason_codes:
        for code in index.reason_codes:
            lines.append(f"- {code}")
    else:
        lines.append("- none")
    lines.append("")

    lines.append("## Entries")
    lines.append("")
    if not index.entries:
        lines.append("_No entries._")
        lines.append("")
    else:
        for entry in index.entries:
            lines.extend(
                [
                    f"### {entry.entry_id}",
                    "",
                    f"- **entry_kind**: {entry.entry_kind.value}",
                    f"- **index_state**: {entry.index_state.value}",
                    f"- **report_id**: {entry.report_id}",
                ]
            )
            if entry.audit_id:
                lines.append(f"- **audit_id**: {entry.audit_id}")
            lines.extend(
                [
                    f"- **review_status**: {entry.review_status}",
                    f"- **review_state**: {entry.review_state}",
                ]
            )
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
            lines.append("")

    return "\n".join(lines)


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


def atomic_write_json_review_index(index: ReviewIndex, path: Path) -> Path:
    """Write ReviewIndex JSON atomically with indent=2, sort_keys=True, newline."""
    content = json.dumps(
        review_index_to_dict(index),
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
    )
    return _atomic_write(path, content + "\n")


def atomic_write_markdown_review_index(index: ReviewIndex, path: Path) -> Path:
    """Write ReviewIndex Markdown atomically with trailing newline."""
    return _atomic_write(path, review_index_to_markdown(index) + "\n")


def write_review_index(
    index: ReviewIndex,
    json_path: Path = DEFAULT_REVIEW_INDEX_JSON_PATH,
    markdown_path: Path = DEFAULT_REVIEW_INDEX_MARKDOWN_PATH,
) -> tuple[Path, Path]:
    """Write ReviewIndex JSON and Markdown artifacts."""
    json_out = atomic_write_json_review_index(index, json_path)
    markdown_out = atomic_write_markdown_review_index(index, markdown_path)
    return json_out, markdown_out
