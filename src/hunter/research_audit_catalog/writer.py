"""JSON/Markdown writer for hunter.research_audit_catalog package.

MVP-21 — Local Research Audit Catalog.

Writes deterministic, human-audit catalog artifacts. All file I/O is explicit
and atomic. File references, metadata strings, and reference strings are
written as plain text only and are never traversed, opened, followed,
validated, or executed.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any

from hunter.research_audit_catalog.models import (
    CATALOG_VERSION,
    CatalogArtifactKind,
    CatalogConfig,
    CatalogDataQuality,
    CatalogEntry,
    CatalogSafetyFlags,
    CatalogState,
    CatalogSummary,
    ResearchCatalog,
)


DEFAULT_RESEARCH_AUDIT_CATALOG_JSON_PATH = Path(
    "data/research_audit_catalog/latest_research_audit_catalog.json"
)
DEFAULT_RESEARCH_AUDIT_CATALOG_MARKDOWN_PATH = Path(
    "reports/research_audit_catalog/latest_research_audit_catalog.md"
)


_SAFETY_NOTICE = """\
## Safety Notice

This local research audit catalog is a human-audit / contractor-handoff artifact only. It is not release approval. It is not deployment approval. It is not a trading signal, not trade approval, not execution approval, not strategy approval, and not transaction permission. It is not a runtime registry, indexer, crawler, scheduler, routing layer, dashboard, database, API, event store, or task runner. It must not be consumed by execution, strategy, Freqtrade shell, order, exchange, or any MVP execution path.

File references, metadata strings, and reference strings in this document are local strings only and are not traversed, opened, followed, validated, or executed. Referenced artifact files are not read. Human audit guide entries are advisory only and are not gating criteria for any release, deployment, execution, strategy, or transaction.
"""


_CATALOG_NOTES = """\
This catalog is a static snapshot built from in-memory objects. It does not scan directories or read referenced files. Each entry records an artifact identity, source layer, state, and local reference string for human audit. The catalog is advisory metadata only.
"""


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
    """Recursively serialize catalog values to JSON-safe deterministic types."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return _iso(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (MappingProxyType, Mapping)):
        return {str(k): _serialize_value(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_serialize_value(v) for v in value]
    return str(value)


def catalog_config_to_dict(config: CatalogConfig) -> dict[str, Any]:
    """Serialize CatalogConfig to a JSON-safe dict."""
    return {
        "catalog_version": config.catalog_version,
        "stale_threshold_seconds": config.stale_threshold_seconds,
        "block_on_empty": config.block_on_empty,
        "block_on_duplicate_ids": config.block_on_duplicate_ids,
        "block_on_unsafe_content": config.block_on_unsafe_content,
    }


def catalog_safety_flags_to_dict(flags: CatalogSafetyFlags) -> dict[str, Any]:
    """Serialize CatalogSafetyFlags to a JSON-safe dict."""
    return {
        "dry_run": flags.dry_run,
        "live_trading_enabled": flags.live_trading_enabled,
        "real_orders_enabled": flags.real_orders_enabled,
        "leverage_enabled": flags.leverage_enabled,
        "shorting_enabled": flags.shorting_enabled,
        "report_feedback_into_execution": flags.report_feedback_into_execution,
        "operator_feedback_into_execution": flags.operator_feedback_into_execution,
        "index_feedback_into_execution": flags.index_feedback_into_execution,
        "search_feedback_into_execution": flags.search_feedback_into_execution,
        "bundle_feedback_into_execution": flags.bundle_feedback_into_execution,
        "chronicle_feedback_into_execution": flags.chronicle_feedback_into_execution,
        "digest_feedback_into_execution": flags.digest_feedback_into_execution,
        "quality_gate_feedback_into_execution": flags.quality_gate_feedback_into_execution,
        "handoff_feedback_into_execution": flags.handoff_feedback_into_execution,
        "archive_manifest_feedback_into_execution": flags.archive_manifest_feedback_into_execution,
        "release_notes_feedback_into_execution": flags.release_notes_feedback_into_execution,
        "catalog_feedback_into_execution": flags.catalog_feedback_into_execution,
        "file_reference_traversal_enabled": flags.file_reference_traversal_enabled,
        "database_persistence_enabled": flags.database_persistence_enabled,
        "web_ui_enabled": flags.web_ui_enabled,
        "dashboard_enabled": flags.dashboard_enabled,
        "runtime_registry_enabled": flags.runtime_registry_enabled,
        "indexer_crawler_enabled": flags.indexer_crawler_enabled,
        "catalog_output_is_human_audit_only": flags.catalog_output_is_human_audit_only,
        "catalog_output_not_trading_signal": flags.catalog_output_not_trading_signal,
        "catalog_output_not_trade_approval": flags.catalog_output_not_trade_approval,
        "catalog_output_not_release_approval": flags.catalog_output_not_release_approval,
        "catalog_output_not_deployment_approval": flags.catalog_output_not_deployment_approval,
        "catalog_output_not_execution_approval": flags.catalog_output_not_execution_approval,
        "catalog_output_not_strategy_approval": flags.catalog_output_not_strategy_approval,
        "catalog_output_not_transaction_permission": flags.catalog_output_not_transaction_permission,
        "catalog_output_not_for_execution": flags.catalog_output_not_for_execution,
        "catalog_output_not_for_strategy": flags.catalog_output_not_for_strategy,
        "catalog_output_not_for_freqtrade": flags.catalog_output_not_for_freqtrade,
        "catalog_output_not_for_order": flags.catalog_output_not_for_order,
        "catalog_output_not_for_exchange": flags.catalog_output_not_for_exchange,
        "file_refs_not_traversed": flags.file_refs_not_traversed,
        "artifact_files_not_read": flags.artifact_files_not_read,
        "no_action_commands_emitted": flags.no_action_commands_emitted,
    }


def catalog_entry_to_dict(entry: CatalogEntry) -> dict[str, Any]:
    """Serialize CatalogEntry to a JSON-safe dict without mutating input."""
    return {
        "entry_id": entry.entry_id,
        "artifact_id": entry.artifact_id,
        "artifact_kind": entry.artifact_kind.value,
        "catalog_state": entry.catalog_state.value,
        "source_version": entry.source_version,
        "generated_at": _iso(entry.generated_at),
        "title": entry.title,
        "spec_reference": entry.spec_reference,
        "local_reference": entry.local_reference,
        "reason_codes": list(entry.reason_codes),
        "tags": list(entry.tags),
        "metadata": _serialize_value(entry.metadata),
    }


def catalog_summary_to_dict(summary: CatalogSummary) -> dict[str, Any]:
    """Serialize CatalogSummary to a JSON-safe dict without mutating input."""
    return {
        "total_entries": summary.total_entries,
        "ready_count": summary.ready_count,
        "blocked_count": summary.blocked_count,
        "unknown_count": summary.unknown_count,
        "disabled_count": summary.disabled_count,
        "kind_counts": {k.value: v for k, v in summary.kind_counts.items()},
        "reason_counts": _serialize_value(summary.reason_counts),
        "layers_covered": summary.layers_covered,
        "layers_missing": summary.layers_missing,
        "duplicate_id_count": summary.duplicate_id_count,
        "stale_entry_count": summary.stale_entry_count,
    }


def catalog_data_quality_to_dict(data_quality: CatalogDataQuality) -> dict[str, Any]:
    """Serialize CatalogDataQuality to a JSON-safe dict without mutating input."""
    return {
        "total_artifacts": data_quality.total_artifacts,
        "valid_entries": data_quality.valid_entries,
        "blocked_entries": data_quality.blocked_entries,
        "stale_entries": data_quality.stale_entries,
        "duplicate_artifact_ids": list(data_quality.duplicate_artifact_ids),
        "cross_kind_overlap_ids": list(data_quality.cross_kind_overlap_ids),
        "missing_layer_kinds": list(data_quality.missing_layer_kinds),
        "covered_layer_kinds": list(data_quality.covered_layer_kinds),
        "validation_errors": list(data_quality.validation_errors),
        "has_duplicates": data_quality.has_duplicates,
        "has_cross_kind_overlap": data_quality.has_cross_kind_overlap,
        "has_missing_layers": data_quality.has_missing_layers,
        "has_stale_entries": data_quality.has_stale_entries,
    }


def research_audit_catalog_to_dict(catalog: ResearchCatalog) -> dict[str, Any]:
    """Serialize ResearchCatalog to a deterministic JSON-safe dict."""
    return {
        "catalog_id": catalog.catalog_id,
        "generated_at": _iso(catalog.generated_at),
        "version": catalog.version,
        "catalog_state": catalog.catalog_state.value,
        "entries": [catalog_entry_to_dict(entry) for entry in catalog.entries],
        "summary": catalog_summary_to_dict(catalog.summary),
        "data_quality": catalog_data_quality_to_dict(catalog.data_quality),
        "safety_flags": catalog_safety_flags_to_dict(catalog.safety_flags),
        "reason_codes": list(catalog.reason_codes),
        "document_notes": _CATALOG_NOTES,
    }


def _kind_title(kind: CatalogArtifactKind) -> str:
    """Return a human-readable title for an artifact kind."""
    return kind.value.replace("_", " ").title()


def _render_metadata(metadata: Mapping[str, Any]) -> str:
    """Render metadata mapping as plain Markdown text.

    Values remain strings only; they are not traversed as paths.
    """
    if not metadata:
        return "_No metadata._"
    lines: list[str] = []
    for key, value in _serialize_value(metadata).items():
        lines.append(f"- **{key}**: {_serialize_value(value)}")
    return "\n".join(lines)


def research_audit_catalog_to_markdown(catalog: ResearchCatalog) -> str:
    """Render ResearchCatalog as deterministic Markdown.

    Safety notice appears before any entry, artifact reference, metadata, or
    detail. All references and metadata strings are rendered as plain text
    only.
    """
    lines: list[str] = [
        "# Local Research Audit Catalog",
        "",
        _SAFETY_NOTICE,
        "",
        "## Catalog Identity",
        "",
        f"- **catalog_id:** `{catalog.catalog_id}`",
        f"- **version:** {catalog.version}",
        f"- **catalog_state:** {catalog.catalog_state.value}",
        f"- **generated_at:** {_iso(catalog.generated_at)}",
        "",
        "## Summary",
        "",
        f"- **total_entries:** {catalog.summary.total_entries}",
        f"- **ready_count:** {catalog.summary.ready_count}",
        f"- **blocked_count:** {catalog.summary.blocked_count}",
        f"- **unknown_count:** {catalog.summary.unknown_count}",
        f"- **disabled_count:** {catalog.summary.disabled_count}",
        f"- **layers_covered:** {catalog.summary.layers_covered}",
        f"- **layers_missing:** {catalog.summary.layers_missing}",
        f"- **duplicate_id_count:** {catalog.summary.duplicate_id_count}",
        f"- **stale_entry_count:** {catalog.summary.stale_entry_count}",
        "",
        "### Kind Counts",
        "",
    ]

    if catalog.summary.kind_counts:
        for kind in CatalogArtifactKind:
            count = catalog.summary.kind_counts.get(kind, 0)
            lines.append(f"- **{kind.value}:** {count}")
    else:
        lines.append("_No entries._")
    lines.append("")

    if catalog.summary.reason_counts:
        lines.extend(["### Reason Counts", ""])
        for code, count in catalog.summary.reason_counts.items():
            lines.append(f"- {code}: {count}")
        lines.append("")

    data_quality = catalog.data_quality
    lines.extend([
        "## Data Quality",
        "",
        f"- **total_artifacts:** {data_quality.total_artifacts}",
        f"- **valid_entries:** {data_quality.valid_entries}",
        f"- **blocked_entries:** {data_quality.blocked_entries}",
        f"- **stale_entries:** {data_quality.stale_entries}",
        f"- **has_duplicates:** {data_quality.has_duplicates}",
        f"- **has_cross_kind_overlap:** {data_quality.has_cross_kind_overlap}",
        f"- **has_missing_layers:** {data_quality.has_missing_layers}",
        f"- **has_stale_entries:** {data_quality.has_stale_entries}",
        "",
    ])

    if data_quality.duplicate_artifact_ids:
        lines.extend(["### Duplicate entry_ids", ""])
        for entry_id in data_quality.duplicate_artifact_ids:
            lines.append(f"- `{entry_id}`")
        lines.append("")

    if data_quality.cross_kind_overlap_ids:
        lines.extend(["### Cross-kind artifact_id overlap", ""])
        for artifact_id in data_quality.cross_kind_overlap_ids:
            lines.append(f"- `{artifact_id}`")
        lines.append("")

    if data_quality.missing_layer_kinds:
        lines.extend(["### Missing layers", ""])
        for kind_value in data_quality.missing_layer_kinds:
            lines.append(f"- {kind_value}")
        lines.append("")

    lines.extend([
        "## Safety Flags",
        "",
    ])
    for key, value in catalog_safety_flags_to_dict(catalog.safety_flags).items():
        lines.append(f"- **{key}:** {value}")
    lines.append("")

    lines.extend([
        "## Reason Codes",
        "",
    ])
    if catalog.reason_codes:
        for code in catalog.reason_codes:
            lines.append(f"- {code}")
    else:
        lines.append("_No reason codes._")
    lines.append("")

    lines.extend([
        "## Entries",
        "",
    ])
    if not catalog.entries:
        lines.append("_No entries._")
        lines.append("")
    else:
        for entry in catalog.entries:
            lines.extend([
                f"### {entry.entry_id}",
                "",
                f"- **artifact_id:** {entry.artifact_id}",
                f"- **artifact_kind:** {entry.artifact_kind.value}",
                f"- **catalog_state:** {entry.catalog_state.value}",
                f"- **source_version:** {entry.source_version}",
                f"- **generated_at:** {_iso(entry.generated_at)}",
            ])
            if entry.title:
                lines.append(f"- **title:** {entry.title}")
            if entry.spec_reference:
                lines.append(f"- **spec_reference:** {entry.spec_reference}")
            if entry.local_reference:
                lines.append(f"- **local_reference:** {entry.local_reference}")
            if entry.reason_codes:
                lines.append(f"- **reason_codes:** {', '.join(entry.reason_codes)}")
            if entry.tags:
                lines.append(f"- **tags:** {', '.join(entry.tags)}")
            lines.extend([
                "- **metadata:**",
                "",
            ])
            for line in _render_metadata(entry.metadata).splitlines():
                lines.append(f"  {line}")
            lines.append("")

    lines.extend([
        "## Catalog Notes",
        "",
        _CATALOG_NOTES,
        "",
    ])

    return "\n".join(lines)


def _atomic_write_text(target: Path, content: str) -> Path:
    """Atomically write text content to target path.

    Uses temp file + flush + fsync + os.replace. Parent directories are
    created for explicit output target paths.
    """
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.parent / f".{target.name}.{os.getpid()}.tmp"
    try:
        with tmp.open("w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, target)
    except Exception:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
        raise
    return target


def atomic_write_json_research_audit_catalog(
    catalog: ResearchCatalog,
    target_path: str | Path | None = None,
) -> Path:
    """Write a ResearchCatalog to JSON atomically."""
    if target_path is None:
        target_path = DEFAULT_RESEARCH_AUDIT_CATALOG_JSON_PATH
    target = Path(target_path)
    data = research_audit_catalog_to_dict(catalog)
    text = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False)
    return _atomic_write_text(target, text + "\n")


def atomic_write_markdown_research_audit_catalog(
    catalog: ResearchCatalog,
    target_path: str | Path | None = None,
) -> Path:
    """Write a ResearchCatalog to Markdown atomically."""
    if target_path is None:
        target_path = DEFAULT_RESEARCH_AUDIT_CATALOG_MARKDOWN_PATH
    target = Path(target_path)
    text = research_audit_catalog_to_markdown(catalog)
    return _atomic_write_text(target, text)


def write_research_audit_catalog(
    catalog: ResearchCatalog,
    json_path: str | Path | None = None,
    markdown_path: str | Path | None = None,
) -> tuple[Path, Path]:
    """Write both JSON and Markdown representations of the catalog."""
    json_out = atomic_write_json_research_audit_catalog(catalog, target_path=json_path)
    md_out = atomic_write_markdown_research_audit_catalog(catalog, target_path=markdown_path)
    return json_out, md_out
