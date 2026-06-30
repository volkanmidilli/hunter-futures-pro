"""Writer for hunter.research_audit_snapshot package.

Serializes ResearchAuditSnapshot to JSON and Markdown with atomic writes.

Safety boundary:
- Local research audit snapshots are human-audit / contractor-handoff artifacts only.
- They are not trading signals, trade approvals, release approvals, deployment approvals,
  execution readiness, strategy readiness, or transaction permission.
- File references and metadata strings are serialized as strings only; they are never opened,
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

from hunter.research_audit_snapshot.models import (
    AuditSnapshotConfig,
    AuditSnapshotDataQuality,
    AuditSnapshotItem,
    AuditSnapshotSafetyFlags,
    AuditSnapshotSection,
    AuditSnapshotSectionKind,
    AuditSnapshotSummary,
    ResearchAuditSnapshot,
)


DEFAULT_AUDIT_SNAPSHOT_JSON_PATH = Path(
    "data/research_audit_snapshot/latest_research_audit_snapshot.json"
)
DEFAULT_AUDIT_SNAPSHOT_MARKDOWN_PATH = Path(
    "reports/research_audit_snapshot/latest_research_audit_snapshot.md"
)


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


def _coerce_path(value: str | Path | None, default: Path) -> Path:
    """Return a Path for the given value, falling back to the default."""
    if value is None:
        return default
    if isinstance(value, Path):
        return value
    return Path(value)


def _state_value(state: str) -> str:
    """Map a normalized state name to its enum value."""
    from hunter.research_audit_snapshot.models import AuditSnapshotState
    try:
        return AuditSnapshotState[state.upper()].value
    except KeyError:
        return AuditSnapshotState.UNKNOWN.value


def _severity_value(severity: str) -> str:
    """Map a normalized severity name to its enum value."""
    from hunter.research_audit_snapshot.models import AuditSnapshotItemSeverity
    try:
        return AuditSnapshotItemSeverity[severity.upper()].value
    except KeyError:
        return AuditSnapshotItemSeverity.INFO.value


# ---------------------------------------------------------------------------
# Dict serialization
# ---------------------------------------------------------------------------


def audit_snapshot_config_to_dict(config: AuditSnapshotConfig) -> dict[str, Any]:
    """Serialize AuditSnapshotConfig to a JSON-safe dict without mutating input."""
    return {
        "block_on_incomplete": config.block_on_incomplete,
        "block_on_stale": config.block_on_stale,
        "block_on_unknown": config.block_on_unknown,
        "dry_run": config.dry_run,
        "expected_artifact_count": config.expected_artifact_count,
        "freshness_threshold_seconds": config.freshness_threshold_seconds,
        "generated_at": _iso(config.generated_at),
        "include_snapshot_narrative": config.include_snapshot_narrative,
        "leverage_enabled": config.leverage_enabled,
        "live_trading_enabled": config.live_trading_enabled,
        "output_format": config.output_format,
        "real_orders_enabled": config.real_orders_enabled,
        "required_sections": [s.value for s in config.required_sections],
        "shorting_enabled": config.shorting_enabled,
        "version": config.version,
    }


def audit_snapshot_safety_flags_to_dict(
    flags: AuditSnapshotSafetyFlags,
) -> dict[str, Any]:
    """Serialize AuditSnapshotSafetyFlags to a JSON-safe dict without mutating input."""
    return {
        "artifact_files_not_read": flags.artifact_files_not_read,
        "cross_layer_feedback_into_execution": flags.cross_layer_feedback_into_execution,
        "dashboard_enabled": flags.dashboard_enabled,
        "database_persistence_enabled": flags.database_persistence_enabled,
        "dry_run": flags.dry_run,
        "event_store_enabled": flags.event_store_enabled,
        "file_reference_traversal_enabled": flags.file_reference_traversal_enabled,
        "file_refs_not_traversed": flags.file_refs_not_traversed,
        "human_audit_guide_is_non_gating": flags.human_audit_guide_is_non_gating,
        "indexer_crawler_enabled": flags.indexer_crawler_enabled,
        "leverage_enabled": flags.leverage_enabled,
        "live_trading_enabled": flags.live_trading_enabled,
        "no_action_commands_emitted": flags.no_action_commands_emitted,
        "real_orders_enabled": flags.real_orders_enabled,
        "runtime_registry_enabled": flags.runtime_registry_enabled,
        "shorting_enabled": flags.shorting_enabled,
        "snapshot_feedback_into_execution": flags.snapshot_feedback_into_execution,
        "snapshot_output_is_human_audit_only": flags.snapshot_output_is_human_audit_only,
        "snapshot_output_not_deployment_approval": flags.snapshot_output_not_deployment_approval,
        "snapshot_output_not_execution_readiness": flags.snapshot_output_not_execution_readiness,
        "snapshot_output_not_for_exchange": flags.snapshot_output_not_for_exchange,
        "snapshot_output_not_for_execution": flags.snapshot_output_not_for_execution,
        "snapshot_output_not_for_freqtrade": flags.snapshot_output_not_for_freqtrade,
        "snapshot_output_not_for_order": flags.snapshot_output_not_for_order,
        "snapshot_output_not_for_strategy": flags.snapshot_output_not_for_strategy,
        "snapshot_output_not_release_approval": flags.snapshot_output_not_release_approval,
        "snapshot_output_not_strategy_readiness": flags.snapshot_output_not_strategy_readiness,
        "snapshot_output_not_trade_approval": flags.snapshot_output_not_trade_approval,
        "snapshot_output_not_trading_signal": flags.snapshot_output_not_trading_signal,
        "snapshot_output_not_transaction_permission": flags.snapshot_output_not_transaction_permission,
        "task_runner_enabled": flags.task_runner_enabled,
        "web_ui_enabled": flags.web_ui_enabled,
    }


def audit_snapshot_item_to_dict(item: AuditSnapshotItem) -> dict[str, Any]:
    """Serialize AuditSnapshotItem to a JSON-safe dict without mutating input."""
    return {
        "artifact_kind": item.artifact_kind,
        "generated_at": _iso(item.generated_at),
        "item_id": item.item_id,
        "local_reference": item.local_reference,
        "metadata": _serialize_value(item.metadata) if item.metadata else {},
        "reason_codes": list(item.reason_codes),
        "related_mvp": item.related_mvp,
        "related_references": list(item.related_references),
        "severity": item.severity,
        "spec_reference": item.spec_reference,
        "state": item.state,
        "tags": list(item.tags),
        "title": item.title,
    }


def audit_snapshot_section_to_dict(section: AuditSnapshotSection) -> dict[str, Any]:
    """Serialize AuditSnapshotSection to a JSON-safe dict without mutating input."""
    return {
        "items": [audit_snapshot_item_to_dict(item) for item in section.items],
        "metadata": _serialize_value(section.metadata) if section.metadata else {},
        "references": list(section.references),
        "section_kind": section.section_kind.value,
        "section_notes": section.section_notes,
        "title": section.title,
    }


def audit_snapshot_summary_to_dict(summary: AuditSnapshotSummary) -> dict[str, Any]:
    """Serialize AuditSnapshotSummary to a JSON-safe dict without mutating input."""
    return {
        "blocked_count": summary.blocked_count,
        "critical_count": summary.critical_count,
        "current_count": summary.current_count,
        "high_count": summary.high_count,
        "incomplete_count": summary.incomplete_count,
        "info_count": summary.info_count,
        "low_count": summary.low_count,
        "medium_count": summary.medium_count,
        "open_item_count": summary.open_item_count,
        "reason_code_counts": dict(summary.reason_code_counts)
        if summary.reason_code_counts
        else {},
        "snapshot_narrative": summary.snapshot_narrative,
        "snapshot_state": summary.snapshot_state,
        "stale_count": summary.stale_count,
        "total_items": summary.total_items,
        "total_sections": summary.total_sections,
        "unknown_count": summary.unknown_count,
    }


def audit_snapshot_data_quality_to_dict(
    data_quality: AuditSnapshotDataQuality,
) -> dict[str, Any]:
    """Serialize AuditSnapshotDataQuality to a JSON-safe dict without mutating input."""
    return {
        "blocked_item_count": data_quality.blocked_item_count,
        "incomplete_item_count": data_quality.incomplete_item_count,
        "open_item_count": data_quality.open_item_count,
        "quality_narrative": data_quality.quality_narrative,
        "reason_codes": list(data_quality.reason_codes),
        "sections_expected": data_quality.sections_expected,
        "sections_missing": data_quality.sections_missing,
        "sections_present": data_quality.sections_present,
        "stale_artifact_count": data_quality.stale_artifact_count,
        "total_artifacts_expected": data_quality.total_artifacts_expected,
        "total_artifacts_missing": data_quality.total_artifacts_missing,
        "total_artifacts_present": data_quality.total_artifacts_present,
        "unknown_item_count": data_quality.unknown_item_count,
    }


def research_audit_snapshot_to_dict(snapshot: ResearchAuditSnapshot) -> dict[str, Any]:
    """Serialize ResearchAuditSnapshot to a JSON-safe dict without mutating input."""
    return {
        "config": audit_snapshot_config_to_dict(snapshot.config),
        "data_quality": audit_snapshot_data_quality_to_dict(snapshot.data_quality),
        "generated_at": _iso(snapshot.generated_at),
        "kind": snapshot.kind.value,
        "metadata": _serialize_value(snapshot.metadata) if snapshot.metadata else {},
        "project_version": snapshot.project_version,
        "reason_codes": list(snapshot.reason_codes),
        "safety_flags": audit_snapshot_safety_flags_to_dict(snapshot.safety_flags),
        "sections": [audit_snapshot_section_to_dict(section) for section in snapshot.sections],
        "snapshot_id": snapshot.snapshot_id,
        "source_spec": snapshot.source_spec,
        "summary": audit_snapshot_summary_to_dict(snapshot.summary),
    }


# ---------------------------------------------------------------------------
# Markdown serialization
# ---------------------------------------------------------------------------

_SAFETY_NOTICE = (
    "This local research audit snapshot is a human-audit / contractor-handoff artifact only. "
    "It is not a trading signal, not trade approval, not release approval, "
    "not deployment approval, not execution approval, not strategy approval, "
    "and not transaction permission. "
    "It must not be consumed by execution, strategy, Freqtrade shell, order, exchange, "
    "or any MVP execution path. "
    "File references and metadata strings are local strings only; they are not traversed, "
    "opened, followed, validated, or executed."
)


def _append_section_notes(lines: list[str], section_notes: str) -> None:
    """Append section notes to markdown lines, preserving paragraphs."""
    if section_notes:
        for note_line in section_notes.splitlines():
            lines.append(note_line)
        lines.append("")


def _append_item(lines: list[str], item: AuditSnapshotItem) -> None:
    """Append an AuditSnapshotItem to markdown lines."""
    lines.extend([f"### {item.item_id}: {item.title}", ""])
    if item.artifact_kind:
        lines.append(f"- **artifact_kind**: {item.artifact_kind}")
    lines.append(f"- **state**: {item.state}")
    lines.append(f"- **severity**: {item.severity}")
    if item.related_mvp:
        lines.append(f"- **related_mvp**: {item.related_mvp}")
    if item.spec_reference:
        lines.append(f"- **spec_reference**: {item.spec_reference}")
    if item.local_reference:
        lines.append(f"- **local_reference**: {item.local_reference}")
    if item.generated_at is not None:
        lines.append(f"- **generated_at**: {_iso(item.generated_at)}")
    if item.reason_codes:
        lines.append(f"- **reason_codes**: {', '.join(item.reason_codes)}")
    if item.tags:
        lines.append(f"- **tags**: {', '.join(item.tags)}")
    if item.related_references:
        lines.append(f"- **related_references**: {', '.join(item.related_references)}")
    if item.metadata:
        lines.append("- **metadata**:")
        for key, value in item.metadata.items():
            lines.append(f"  - {key}: {value}")
    lines.append("")


def _section_sort_key(section: AuditSnapshotSection) -> int:
    """Return canonical sort index for a section kind."""
    try:
        return list(AuditSnapshotSectionKind).index(section.section_kind)
    except ValueError:
        return len(AuditSnapshotSectionKind)


def research_audit_snapshot_to_markdown(snapshot: ResearchAuditSnapshot) -> str:
    """Render ResearchAuditSnapshot as deterministic Markdown.

    The safety notice appears immediately after the fixed H1 title and before
    any identity, section, item, reference, metadata, or detail.
    """
    lines: list[str] = [
        "# Local Research Audit Snapshot — Human Audit Only",
        "",
        f"> {_SAFETY_NOTICE}",
        "",
        "## Snapshot Identity",
        "",
        f"- **snapshot_id**: {snapshot.snapshot_id}",
        f"- **kind**: {snapshot.kind.value}",
        f"- **project_version**: {snapshot.project_version}",
        f"- **source_spec**: {snapshot.source_spec}",
        f"- **generated_at**: {_iso(snapshot.generated_at)}",
        f"- **snapshot_state**: {snapshot.summary.snapshot_state}",
        "",
    ]

    lines.extend(["## Reason Codes", ""])
    if snapshot.reason_codes:
        for code in snapshot.reason_codes:
            lines.append(f"- {code}")
    else:
        lines.append("- none")
    lines.append("")

    sorted_sections = sorted(snapshot.sections, key=_section_sort_key)
    for section in sorted_sections:
        lines.extend([f"## {section.title}", ""])
        _append_section_notes(lines, section.section_notes)

        if section.items:
            for item in section.items:
                _append_item(lines, item)
        elif section.references:
            lines.extend(["### References", ""])
            for ref in section.references:
                lines.append(f"- {ref}")
            lines.append("")
        elif not section.section_notes:
            lines.extend(["_No content._", ""])

        if section.metadata:
            lines.extend(["### Section Metadata", ""])
            for key, value in section.metadata.items():
                lines.append(f"- **{key}**: {value}")
            lines.append("")

    summary = snapshot.summary
    lines.extend([
        "## Snapshot Summary",
        "",
        f"- **total_sections**: {summary.total_sections}",
        f"- **total_items**: {summary.total_items}",
        f"- **critical_count**: {summary.critical_count}",
        f"- **high_count**: {summary.high_count}",
        f"- **medium_count**: {summary.medium_count}",
        f"- **low_count**: {summary.low_count}",
        f"- **info_count**: {summary.info_count}",
        f"- **open_item_count**: {summary.open_item_count}",
        f"- **snapshot_state**: {summary.snapshot_state}",
        "",
    ])

    if summary.reason_code_counts:
        lines.extend(["### Reason Code Counts", ""])
        for code, count in summary.reason_code_counts.items():
            lines.append(f"- {code}: {count}")
        lines.append("")

    lines.extend(["### Snapshot Narrative", ""])
    if summary.snapshot_narrative:
        lines.append(summary.snapshot_narrative)
    else:
        lines.append("_No narrative available._")
    lines.append("")

    dq = snapshot.data_quality
    lines.extend([
        "## Data Quality",
        "",
        f"- **total_artifacts_expected**: {dq.total_artifacts_expected}",
        f"- **total_artifacts_present**: {dq.total_artifacts_present}",
        f"- **total_artifacts_missing**: {dq.total_artifacts_missing}",
        f"- **stale_artifact_count**: {dq.stale_artifact_count}",
        f"- **open_item_count**: {dq.open_item_count}",
        f"- **blocked_item_count**: {dq.blocked_item_count}",
        f"- **incomplete_item_count**: {dq.incomplete_item_count}",
        f"- **unknown_item_count**: {dq.unknown_item_count}",
        f"- **sections_expected**: {dq.sections_expected}",
        f"- **sections_present**: {dq.sections_present}",
        f"- **sections_missing**: {dq.sections_missing}",
        "",
    ])
    if dq.reason_codes:
        lines.extend(["### Data Quality Reason Codes", ""])
        for code in dq.reason_codes:
            lines.append(f"- {code}")
        lines.append("")
    if dq.quality_narrative:
        lines.extend(["### Quality Narrative", "", dq.quality_narrative, ""])

    if snapshot.metadata:
        lines.extend(["## Metadata", ""])
        for key, value in snapshot.metadata.items():
            lines.append(f"- **{key}**: {value}")
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


def atomic_write_json_research_audit_snapshot(
    snapshot: ResearchAuditSnapshot,
    target_path: str | Path | None = None,
) -> Path:
    """Atomic JSON write with temp file, fsync, os.replace, cleanup."""
    path = _coerce_path(target_path, DEFAULT_AUDIT_SNAPSHOT_JSON_PATH)
    content = json.dumps(
        research_audit_snapshot_to_dict(snapshot),
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
    )
    return _atomic_write(path, content + "\n")


def atomic_write_markdown_research_audit_snapshot(
    snapshot: ResearchAuditSnapshot,
    target_path: str | Path | None = None,
) -> Path:
    """Atomic Markdown write with temp file, fsync, os.replace, cleanup."""
    path = _coerce_path(target_path, DEFAULT_AUDIT_SNAPSHOT_MARKDOWN_PATH)
    return _atomic_write(path, research_audit_snapshot_to_markdown(snapshot) + "\n")


def write_research_audit_snapshot(
    snapshot: ResearchAuditSnapshot,
    json_path: str | Path | None = None,
    markdown_path: str | Path | None = None,
) -> tuple[Path | None, Path | None]:
    """Write JSON and/or Markdown research audit snapshot files based on config.output_format."""
    output_format = snapshot.config.output_format
    json_out: Path | None = None
    md_out: Path | None = None

    if output_format in ("json", "both"):
        json_out = atomic_write_json_research_audit_snapshot(
            snapshot, _coerce_path(json_path, DEFAULT_AUDIT_SNAPSHOT_JSON_PATH)
        )
    if output_format in ("markdown", "both"):
        md_out = atomic_write_markdown_research_audit_snapshot(
            snapshot, _coerce_path(markdown_path, DEFAULT_AUDIT_SNAPSHOT_MARKDOWN_PATH)
        )

    return json_out, md_out
