"""JSON/Markdown writer for hunter.research_archive_manifest package.

MVP-19 — Local Research Archive Manifest.

Writes deterministic, human-audit archive manifest artifacts. All file I/O is
explicit and atomic. File references and metadata strings are written as plain
text only and are never traversed, opened, followed, validated, or executed.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Any

from hunter.research_archive_manifest.models import (
    ARCHIVE_MANIFEST_VERSION,
    ArchiveArtifactEntry,
    ArchiveManifestConfig,
    ArchiveManifestDataQuality,
    ArchiveManifestSafetyFlags,
    ArchiveManifestState,
    ArchiveManifestSummary,
    ResearchArchiveManifest,
)


DEFAULT_ARCHIVE_MANIFEST_JSON_PATH = (
    "data/research_archive_manifest/latest_research_archive_manifest.json"
)
DEFAULT_ARCHIVE_MANIFEST_MARKDOWN_PATH = (
    "reports/research_archive_manifest/latest_research_archive_manifest.md"
)


_SAFETY_NOTICE = """\
## Safety Notice

This local research archive manifest is a human-audit / contractor-orientation
artifact only. It is not a trading signal, not trade approval, not execution
readiness, not strategy readiness, not release/deployment approval, not
transaction permission, and must not be consumed by execution, strategy,
Freqtrade shell, order, exchange, or any MVP execution path. File references,
metadata strings, and reference strings in this manifest are local strings only
and are not traversed, opened, followed, validated, or executed. This manifest
does not read referenced artifact files.
"""


def _serialize_value(value: Any) -> Any:
    """Recursively convert manifest values into JSON-safe primitives."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (MappingProxyType, Mapping)):
        return {str(k): _serialize_value(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_serialize_value(v) for v in value]
    if isinstance(value, ArchiveManifestState):
        return value.value
    # Fallback for enums / dataclass-like objects with a value attribute.
    if hasattr(value, "value"):
        return str(value.value)
    return str(value)


def archive_manifest_config_to_dict(config: ArchiveManifestConfig) -> dict[str, Any]:
    """Serialize ArchiveManifestConfig to a JSON-safe dict."""
    return {
        "version": config.version,
        "generated_at": config.generated_at.isoformat() if config.generated_at else None,
        "output_format": config.output_format,
        "dry_run": config.dry_run,
        "live_trading_enabled": config.live_trading_enabled,
        "real_orders_enabled": config.real_orders_enabled,
        "leverage_enabled": config.leverage_enabled,
        "shorting_enabled": config.shorting_enabled,
        "block_on_unknown": config.block_on_unknown,
        "required_families": [family.value for family in config.required_families],
        "max_staleness_minutes": config.max_staleness_minutes,
        "include_manifest_notes": config.include_manifest_notes,
    }


def archive_manifest_safety_flags_to_dict(
    flags: ArchiveManifestSafetyFlags,
) -> dict[str, Any]:
    """Serialize ArchiveManifestSafetyFlags to a JSON-safe dict."""
    return {
        "dry_run": flags.dry_run,
        "live_trading_enabled": flags.live_trading_enabled,
        "real_orders_enabled": flags.real_orders_enabled,
        "leverage_enabled": flags.leverage_enabled,
        "shorting_enabled": flags.shorting_enabled,
        "archive_output_is_human_audit_only": flags.archive_output_is_human_audit_only,
        "archive_output_not_trading_signal": flags.archive_output_not_trading_signal,
        "archive_output_not_trade_approval": flags.archive_output_not_trade_approval,
        "archive_output_not_execution_readiness": flags.archive_output_not_execution_readiness,
        "archive_output_not_strategy_readiness": flags.archive_output_not_strategy_readiness,
        "archive_output_not_release_approval": flags.archive_output_not_release_approval,
        "archive_output_not_deployment_approval": flags.archive_output_not_deployment_approval,
        "archive_output_not_transaction_permission": flags.archive_output_not_transaction_permission,
        "archive_output_not_for_execution": flags.archive_output_not_for_execution,
        "archive_output_not_for_strategy": flags.archive_output_not_for_strategy,
        "archive_output_not_for_freqtrade": flags.archive_output_not_for_freqtrade,
        "archive_output_not_for_order": flags.archive_output_not_for_order,
        "archive_output_not_for_exchange": flags.archive_output_not_for_exchange,
        "archive_manifest_feedback_into_execution": flags.archive_manifest_feedback_into_execution,
        "cross_layer_feedback_into_execution": flags.cross_layer_feedback_into_execution,
        "file_refs_not_traversed": flags.file_refs_not_traversed,
        "artifact_files_not_read": flags.artifact_files_not_read,
    }


def archive_artifact_entry_to_dict(entry: ArchiveArtifactEntry) -> dict[str, Any]:
    """Serialize ArchiveArtifactEntry to a JSON-safe dict."""
    return {
        "artifact_family": entry.artifact_family.value,
        "title": entry.title,
        "state": entry.state,
        "spec_reference": entry.spec_reference,
        "local_reference": entry.local_reference,
        "version": entry.version,
        "generated_at": entry.generated_at.isoformat() if entry.generated_at else None,
        "reason_codes": list(entry.reason_codes),
        "metadata": _serialize_value(entry.metadata),
    }


def archive_manifest_summary_to_dict(summary: ArchiveManifestSummary) -> dict[str, Any]:
    """Serialize ArchiveManifestSummary to a JSON-safe dict."""
    return {
        "total_families": summary.total_families,
        "present_count": summary.present_count,
        "stale_count": summary.stale_count,
        "missing_count": summary.missing_count,
        "unknown_count": summary.unknown_count,
        "manifest_state": summary.manifest_state,
        "reason_code_counts": _serialize_value(summary.reason_code_counts),
        "manifest_notes": summary.manifest_notes,
    }


def archive_manifest_data_quality_to_dict(
    data_quality: ArchiveManifestDataQuality,
) -> dict[str, Any]:
    """Serialize ArchiveManifestDataQuality to a JSON-safe dict."""
    return {
        "completeness_pct": data_quality.completeness_pct,
        "coverage_pct": data_quality.coverage_pct,
        "present_pct": data_quality.present_pct,
        "missing_count": data_quality.missing_count,
        "stale_count": data_quality.stale_count,
        "unknown_count": data_quality.unknown_count,
        "total_families": data_quality.total_families,
        "reason": data_quality.reason,
    }


def research_archive_manifest_to_dict(manifest: ResearchArchiveManifest) -> dict[str, Any]:
    """Serialize ResearchArchiveManifest to a deterministic JSON-safe dict."""
    return {
        "manifest_id": manifest.manifest_id,
        "generated_at": manifest.generated_at.isoformat(),
        "version": manifest.version,
        "manifest_state": manifest.manifest_state.value,
        "entries": [archive_artifact_entry_to_dict(e) for e in manifest.entries],
        "summary": archive_manifest_summary_to_dict(manifest.summary),
        "data_quality": archive_manifest_data_quality_to_dict(manifest.data_quality),
        "safety_flags": archive_manifest_safety_flags_to_dict(manifest.safety_flags),
        "config": archive_manifest_config_to_dict(manifest.config),
        "reason_codes": list(manifest.reason_codes),
        "manifest_notes": manifest.manifest_notes,
    }


def research_archive_manifest_to_markdown(manifest: ResearchArchiveManifest) -> str:
    """Render ResearchArchiveManifest as deterministic Markdown."""
    lines: list[str] = [
        "# Local Research Archive Manifest",
        "",
        _SAFETY_NOTICE,
        "",
        "## Manifest Identity",
        "",
        f"- **manifest_id:** `{manifest.manifest_id}`",
        f"- **version:** {manifest.version}",
        f"- **manifest_state:** {manifest.manifest_state.value}",
        f"- **generated_at:** {manifest.generated_at.isoformat()}",
        "",
        "## Summary",
        "",
        f"- **total_families:** {manifest.summary.total_families}",
        f"- **present_count:** {manifest.summary.present_count}",
        f"- **stale_count:** {manifest.summary.stale_count}",
        f"- **missing_count:** {manifest.summary.missing_count}",
        f"- **unknown_count:** {manifest.summary.unknown_count}",
        f"- **manifest_state:** {manifest.summary.manifest_state}",
        "",
        "## Data Quality",
        "",
        f"- **completeness_pct:** {manifest.data_quality.completeness_pct}",
        f"- **coverage_pct:** {manifest.data_quality.coverage_pct}",
        f"- **present_pct:** {manifest.data_quality.present_pct}",
        f"- **missing_count:** {manifest.data_quality.missing_count}",
        f"- **stale_count:** {manifest.data_quality.stale_count}",
        f"- **unknown_count:** {manifest.data_quality.unknown_count}",
        f"- **total_families:** {manifest.data_quality.total_families}",
        f"- **reason:** {manifest.data_quality.reason}",
        "",
        "## Artifact Families",
        "",
    ]

    if not manifest.entries:
        lines.append("_No artifact families listed._")
        lines.append("")
    else:
        for entry in manifest.entries:
            lines.append(f"### {entry.title}")
            lines.append("")
            lines.append(f"- **family:** {entry.artifact_family.value}")
            lines.append(f"- **state:** {entry.state}")
            lines.append(f"- **spec_reference:** {entry.spec_reference}")
            lines.append(f"- **local_reference:** `{entry.local_reference}`")
            if entry.version:
                lines.append(f"- **version:** {entry.version}")
            if entry.generated_at:
                lines.append(f"- **generated_at:** {entry.generated_at.isoformat()}")
            if entry.reason_codes:
                lines.append(f"- **reason_codes:** {', '.join(entry.reason_codes)}")
            if entry.metadata:
                lines.append("- **metadata:**")
                for key, value in entry.metadata.items():
                    lines.append(f"  - **{key}:** {_serialize_value(value)}")
            lines.append("")

    lines.extend([
        "## Reason Codes",
        "",
    ])
    if manifest.reason_codes:
        for rc in manifest.reason_codes:
            lines.append(f"- {rc}")
    else:
        lines.append("_No reason codes._")
    lines.append("")

    lines.extend([
        "## Manifest Notes",
        "",
        manifest.manifest_notes,
        "",
    ])

    return "\n".join(lines)


def _atomic_write_text(target: Path, content: str) -> Path:
    """Atomically write text content to target path."""
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
            tmp.unlink()
        raise
    return target


def atomic_write_json_research_archive_manifest(
    manifest: ResearchArchiveManifest,
    target_path: str | Path | None = None,
) -> Path:
    """Write a ResearchArchiveManifest to JSON atomically."""
    if target_path is None:
        target_path = DEFAULT_ARCHIVE_MANIFEST_JSON_PATH
    target = Path(target_path)
    data = research_archive_manifest_to_dict(manifest)
    text = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False)
    return _atomic_write_text(target, text + "\n")


def atomic_write_markdown_research_archive_manifest(
    manifest: ResearchArchiveManifest,
    target_path: str | Path | None = None,
) -> Path:
    """Write a ResearchArchiveManifest to Markdown atomically."""
    if target_path is None:
        target_path = DEFAULT_ARCHIVE_MANIFEST_MARKDOWN_PATH
    target = Path(target_path)
    text = research_archive_manifest_to_markdown(manifest)
    return _atomic_write_text(target, text)


def write_research_archive_manifest(
    manifest: ResearchArchiveManifest,
    json_path: str | Path | None = None,
    markdown_path: str | Path | None = None,
) -> tuple[Path, Path]:
    """Write both JSON and Markdown representations of the manifest."""
    json_out = atomic_write_json_research_archive_manifest(manifest, target_path=json_path)
    md_out = atomic_write_markdown_research_archive_manifest(manifest, target_path=markdown_path)
    return json_out, md_out
