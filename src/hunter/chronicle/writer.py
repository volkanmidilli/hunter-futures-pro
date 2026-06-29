"""Writer for hunter.chronicle package.

Deterministic JSON and Markdown serialization for ResearchChronicle with atomic
writes. Output is human-audit only; no file references are traversed, opened,
followed, validated, or executed here.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from hunter.chronicle.models import (
    CHRONICLE_VERSION,
    ArtifactType,
    ChronicleDataQuality,
    ChronicleEntry,
    ChronicleSafetyFlags,
    ChronicleSummary,
    ResearchChronicle,
)


DEFAULT_CHRONICLE_JSON_PATH = Path("data/chronicle/latest_research_chronicle.json")
DEFAULT_CHRONICLE_MARKDOWN_PATH = Path("reports/chronicle/latest_research_chronicle.md")


# ---------------------------------------------------------------------------
# Value helpers
# ---------------------------------------------------------------------------


def _iso(value: datetime) -> str:
    """Return ISO-8601 string for a timezone-aware datetime."""
    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def _serialize_value(value: Any) -> Any:
    """Serialize a value to JSON-safe deterministic types."""
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


def chronicle_safety_flags_to_dict(flags: ChronicleSafetyFlags) -> dict[str, Any]:
    """Serialize ChronicleSafetyFlags to a JSON-safe dict."""
    return {
        "dry_run": flags.dry_run,
        "live_trading_enabled": flags.live_trading_enabled,
        "real_orders_enabled": flags.real_orders_enabled,
        "leverage_enabled": flags.leverage_enabled,
        "shorting_enabled": flags.shorting_enabled,
        "chronicle_output_is_human_audit_only": flags.chronicle_output_is_human_audit_only,
        "chronicle_output_not_trading_signal": flags.chronicle_output_not_trading_signal,
        "chronicle_output_not_trade_approval": flags.chronicle_output_not_trade_approval,
        "chronicle_output_not_for_execution": flags.chronicle_output_not_for_execution,
        "chronicle_output_not_for_strategy": flags.chronicle_output_not_for_strategy,
        "chronicle_output_not_for_freqtrade": flags.chronicle_output_not_for_freqtrade,
        "chronicle_output_not_for_order": flags.chronicle_output_not_for_order,
        "chronicle_output_not_for_exchange": flags.chronicle_output_not_for_exchange,
        "chronicle_feedback_into_execution": flags.chronicle_feedback_into_execution,
    }


def chronicle_entry_to_dict(entry: ChronicleEntry) -> dict[str, Any]:
    """Serialize ChronicleEntry to a JSON-safe dict."""
    return {
        "entry_id": entry.entry_id,
        "timestamp": _iso(entry.timestamp),
        "artifact_type": entry.artifact_type.value,
        "trace_id": entry.trace_id,
        "state": entry.state,
        "version": entry.version,
        "entry_count": entry.entry_count,
        "reason_codes": list(entry.reason_codes),
        "actor": entry.actor,
        "notes": entry.notes,
        "tags": list(entry.tags),
        "metadata": _serialize_value(entry.metadata) if entry.metadata else {},
        "related_trace_ids": list(entry.related_trace_ids),
    }


def chronicle_summary_to_dict(summary: ChronicleSummary) -> dict[str, Any]:
    """Serialize ChronicleSummary to a JSON-safe dict."""
    return {
        "total_entries": summary.total_entries,
        "observation_count": summary.observation_count,
        "review_count": summary.review_count,
        "index_count": summary.index_count,
        "search_count": summary.search_count,
        "bundle_count": summary.bundle_count,
        "blocked_count": summary.blocked_count,
        "ready_count": summary.ready_count,
        "accepted_count": summary.accepted_count,
        "rejected_count": summary.rejected_count,
        "unknown_count": summary.unknown_count,
        "reason_code_counts": dict(summary.reason_code_counts) if summary.reason_code_counts else {},
        "tag_counts": dict(summary.tag_counts) if summary.tag_counts else {},
        "actor_counts": dict(summary.actor_counts) if summary.actor_counts else {},
        "timestamp_range": summary.timestamp_range,
        "daily_counts": _serialize_value(summary.daily_counts) if summary.daily_counts else {},
    }


def chronicle_data_quality_to_dict(data_quality: ChronicleDataQuality) -> dict[str, Any]:
    """Serialize ChronicleDataQuality to a JSON-safe dict."""
    return {
        "has_observations": data_quality.has_observations,
        "has_reviews": data_quality.has_reviews,
        "has_index": data_quality.has_index,
        "has_search": data_quality.has_search,
        "has_bundle": data_quality.has_bundle,
        "orphan_observation_count": data_quality.orphan_observation_count,
        "orphan_review_count": data_quality.orphan_review_count,
        "trace_completeness_pct": data_quality.trace_completeness_pct,
        "gap_count": data_quality.gap_count,
        "stale_entry_count": data_quality.stale_entry_count,
        "validation_errors": list(data_quality.validation_errors),
    }


def research_chronicle_to_dict(chronicle: ResearchChronicle) -> dict[str, Any]:
    """Serialize ResearchChronicle to a JSON-safe dict deterministically."""
    return {
        "chronicle_id": chronicle.chronicle_id,
        "generated_at": _iso(chronicle.generated_at),
        "version": chronicle.version,
        "entries": [chronicle_entry_to_dict(entry) for entry in chronicle.entries],
        "summary": chronicle_summary_to_dict(chronicle.summary),
        "data_quality": chronicle_data_quality_to_dict(chronicle.data_quality),
        "safety_flags": chronicle_safety_flags_to_dict(chronicle.safety_flags),
        "reason_codes": list(chronicle.reason_codes),
    }


# ---------------------------------------------------------------------------
# Markdown serialization
# ---------------------------------------------------------------------------


_SAFETY_NOTICE = (
    "This local research chronicle is a human-audit timeline artifact only. "
    "It is not a trading signal, not trade approval, and must not be "
    "consumed by execution, strategy, Freqtrade shell, order, exchange, "
    "or any MVP execution path."
)


def research_chronicle_to_markdown(chronicle: ResearchChronicle) -> str:
    """Render ResearchChronicle as human-readable Markdown with safety notice."""
    summary = chronicle.summary
    data_quality = chronicle.data_quality
    flags = chronicle.safety_flags

    lines: list[str] = [
        "# Research Chronicle — Human Audit Only",
        "",
        f"> {_SAFETY_NOTICE}",
        "",
        "## Chronicle Info",
        "",
        f"- **chronicle_id**: {chronicle.chronicle_id}",
        f"- **generated_at**: {_iso(chronicle.generated_at)}",
        f"- **version**: {chronicle.version}",
        f"- **entry_count**: {len(chronicle.entries)}",
        "",
        "## Safety Notice",
        "",
        "This research chronicle is a **human-audit artifact only**.",
        "",
        "- It is **not a trading signal**.",
        "- It is **not trade approval**.",
        "- It **must not be consumed by execution, strategy, Freqtrade shell, order, exchange, or any MVP execution path**.",
        "- Trace linkage is **advisory only** and does not imply causality or automated action.",
        "- File references in this chronicle are **local strings only** and are **not traversed, opened, followed, validated, or executed**.",
        "",
        "## Summary",
        "",
        f"- **total_entries**: {summary.total_entries}",
        f"- **observation_count**: {summary.observation_count}",
        f"- **review_count**: {summary.review_count}",
        f"- **index_count**: {summary.index_count}",
        f"- **search_count**: {summary.search_count}",
        f"- **bundle_count**: {summary.bundle_count}",
        f"- **blocked_count**: {summary.blocked_count}",
        f"- **ready_count**: {summary.ready_count}",
        f"- **accepted_count**: {summary.accepted_count}",
        f"- **rejected_count**: {summary.rejected_count}",
        f"- **unknown_count**: {summary.unknown_count}",
        "",
    ]

    lines.extend(["### Reason Code Counts", ""])
    if summary.reason_code_counts:
        for code, count in summary.reason_code_counts.items():
            lines.append(f"- {code}: {count}")
    else:
        lines.append("- none")
    lines.append("")

    lines.extend(["### Tag Counts", ""])
    if summary.tag_counts:
        for tag, count in summary.tag_counts.items():
            lines.append(f"- {tag}: {count}")
    else:
        lines.append("- none")
    lines.append("")

    lines.extend(["### Actor Counts", ""])
    if summary.actor_counts:
        for actor, count in summary.actor_counts.items():
            lines.append(f"- {actor}: {count}")
    else:
        lines.append("- none")
    lines.append("")

    if summary.timestamp_range is not None:
        lines.extend([
            f"- **timestamp_range**: {summary.timestamp_range[0]} to {summary.timestamp_range[1]}",
            "",
        ])

    lines.extend(["### Daily Counts", ""])
    if summary.daily_counts:
        for day, day_counts in summary.daily_counts.items():
            lines.append(f"- **{day}**:")
            for k, v in day_counts.items():
                lines.append(f"  - {k}: {v}")
    else:
        lines.append("- none")
    lines.append("")

    lines.extend([
        "## Data Quality",
        "",
        f"- **has_observations**: {data_quality.has_observations}",
        f"- **has_reviews**: {data_quality.has_reviews}",
        f"- **has_index**: {data_quality.has_index}",
        f"- **has_search**: {data_quality.has_search}",
        f"- **has_bundle**: {data_quality.has_bundle}",
        f"- **orphan_observation_count**: {data_quality.orphan_observation_count}",
        f"- **orphan_review_count**: {data_quality.orphan_review_count}",
        f"- **trace_completeness_pct**: {data_quality.trace_completeness_pct}",
        f"- **gap_count**: {data_quality.gap_count}",
        f"- **stale_entry_count**: {data_quality.stale_entry_count}",
        f"- **validation_errors**: {', '.join(data_quality.validation_errors) if data_quality.validation_errors else 'none'}",
        "",
    ])

    lines.extend(["## Safety Flags", ""])
    for key, value in chronicle_safety_flags_to_dict(flags).items():
        lines.append(f"- **{key}**: {value}")
    lines.append("")

    lines.extend(["## Reason Codes", ""])
    if chronicle.reason_codes:
        for code in chronicle.reason_codes:
            lines.append(f"- {code}")
    else:
        lines.append("- none")
    lines.append("")

    lines.extend(["## Entries", ""])
    if not chronicle.entries:
        lines.append("_No chronicle entries._")
        lines.append("")
    else:
        for entry in chronicle.entries:
            lines.extend([
                f"### {entry.entry_id}",
                "",
                f"- **timestamp**: {_iso(entry.timestamp)}",
                f"- **artifact_type**: {entry.artifact_type.value}",
                f"- **trace_id**: {entry.trace_id}",
                f"- **state**: {entry.state}",
                f"- **version**: {entry.version}",
                f"- **entry_count**: {entry.entry_count}",
            ])
            if entry.actor:
                lines.append(f"- **actor**: {entry.actor}")
            if entry.notes:
                lines.append(f"- **notes**: {entry.notes}")
            if entry.tags:
                lines.append(f"- **tags**: {', '.join(entry.tags)}")
            if entry.reason_codes:
                lines.append(f"- **reason_codes**: {', '.join(entry.reason_codes)}")
            if entry.related_trace_ids:
                lines.append(f"- **related_trace_ids**: {', '.join(entry.related_trace_ids)}")
            if entry.metadata:
                lines.append("- **metadata**:")
                for key, value in entry.metadata.items():
                    lines.append(f"  - {key}: {value}")
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


def atomic_write_json_research_chronicle(
    chronicle: ResearchChronicle,
    target_path: Path | None = None,
) -> Path:
    """Serialize ResearchChronicle to JSON and write atomically."""
    path = target_path if target_path is not None else DEFAULT_CHRONICLE_JSON_PATH
    data = research_chronicle_to_dict(chronicle)
    text = json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True)
    text += "\n"
    _atomic_write(path, text)
    return path


def atomic_write_markdown_research_chronicle(
    chronicle: ResearchChronicle,
    target_path: Path | None = None,
) -> Path:
    """Serialize ResearchChronicle to Markdown and write atomically."""
    path = target_path if target_path is not None else DEFAULT_CHRONICLE_MARKDOWN_PATH
    _atomic_write(path, research_chronicle_to_markdown(chronicle) + "\n")
    return path


def write_research_chronicle(
    chronicle: ResearchChronicle,
    json_path: Path | None = None,
    markdown_path: Path | None = None,
) -> tuple[Path, Path]:
    """Write ResearchChronicle to both JSON and Markdown."""
    json_out = atomic_write_json_research_chronicle(chronicle, json_path)
    markdown_out = atomic_write_markdown_research_chronicle(chronicle, markdown_path)
    return json_out, markdown_out
