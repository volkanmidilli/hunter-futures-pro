"""JSON/Markdown writer for hunter.research_release_notes package.

MVP-20 — Local Research Release Notes / Audit Change Summary.

Writes deterministic, human-audit release notes artifacts. All file I/O is
explicit and atomic. File references, metadata strings, and reference strings
are written as plain text only and are never traversed, opened, followed,
validated, or executed.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Any

from hunter.research_release_notes.models import (
    RELEASE_NOTES_VERSION,
    ReleaseNotesChangeItem,
    ReleaseNotesConfig,
    ReleaseNotesDataQuality,
    ReleaseNotesSafetyFlags,
    ReleaseNotesSection,
    ReleaseNotesSectionKind,
    ReleaseNotesState,
    ReleaseNotesSummary,
    ResearchReleaseNotes,
)


DEFAULT_RESEARCH_RELEASE_NOTES_JSON_PATH = (
    "data/research_release_notes/latest_research_release_notes.json"
)
DEFAULT_RESEARCH_RELEASE_NOTES_MARKDOWN_PATH = (
    "reports/research_release_notes/latest_research_release_notes.md"
)


_SAFETY_NOTICE = """\
## Safety Notice

This local research release notes / audit change summary is a human-audit and contractor-handoff artifact only. It is not release approval. It is not deployment approval. It is not a trading signal, not trade approval, not execution approval, not strategy approval, and not transaction permission. It must not be consumed by execution, strategy, Freqtrade shell, order, exchange, or any MVP execution path. File references, metadata strings, and reference strings in this document are local strings only and are not traversed, opened, followed, validated, or interpreted as commands. This document does not read referenced artifact files. Human review guide entries are advisory suggestions only and are not gating criteria for any release, deployment, execution, strategy, or transaction.
"""


def _serialize_value(value: Any) -> Any:
    """Recursively convert release notes values into JSON-safe primitives."""
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
    if isinstance(value, ReleaseNotesState):
        return value.value
    # Fallback for enums / dataclass-like objects with a value attribute.
    if hasattr(value, "value"):
        return str(value.value)
    return str(value)


def release_notes_config_to_dict(config: ReleaseNotesConfig) -> dict[str, Any]:
    """Serialize ReleaseNotesConfig to a JSON-safe dict."""
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
        "release_version": config.release_version,
        "release_title": config.release_title,
        "required_sections": [section.value for section in config.required_sections],
        "include_release_notes": config.include_release_notes,
    }


def release_notes_safety_flags_to_dict(flags: ReleaseNotesSafetyFlags) -> dict[str, Any]:
    """Serialize ReleaseNotesSafetyFlags to a JSON-safe dict."""
    return {
        "dry_run": flags.dry_run,
        "live_trading_enabled": flags.live_trading_enabled,
        "real_orders_enabled": flags.real_orders_enabled,
        "leverage_enabled": flags.leverage_enabled,
        "shorting_enabled": flags.shorting_enabled,
        "release_notes_output_is_human_audit_only": flags.release_notes_output_is_human_audit_only,
        "release_notes_output_not_trading_signal": flags.release_notes_output_not_trading_signal,
        "release_notes_output_not_trade_approval": flags.release_notes_output_not_trade_approval,
        "release_notes_output_not_execution_readiness": flags.release_notes_output_not_execution_readiness,
        "release_notes_output_not_strategy_readiness": flags.release_notes_output_not_strategy_readiness,
        "release_notes_output_not_release_approval": flags.release_notes_output_not_release_approval,
        "release_notes_output_not_deployment_approval": flags.release_notes_output_not_deployment_approval,
        "release_notes_output_not_transaction_permission": flags.release_notes_output_not_transaction_permission,
        "release_notes_output_not_for_execution": flags.release_notes_output_not_for_execution,
        "release_notes_output_not_for_strategy": flags.release_notes_output_not_for_strategy,
        "release_notes_output_not_for_freqtrade": flags.release_notes_output_not_for_freqtrade,
        "release_notes_output_not_for_order": flags.release_notes_output_not_for_order,
        "release_notes_output_not_for_exchange": flags.release_notes_output_not_for_exchange,
        "release_notes_feedback_into_execution": flags.release_notes_feedback_into_execution,
        "cross_layer_feedback_into_execution": flags.cross_layer_feedback_into_execution,
        "no_action_commands_emitted": flags.no_action_commands_emitted,
        "file_refs_not_traversed": flags.file_refs_not_traversed,
        "artifact_files_not_read": flags.artifact_files_not_read,
    }


def release_notes_change_item_to_dict(item: ReleaseNotesChangeItem) -> dict[str, Any]:
    """Serialize ReleaseNotesChangeItem to a JSON-safe dict."""
    return {
        "title": item.title,
        "description": item.description,
        "change_kind": item.change_kind,
        "severity": item.severity,
        "related_mvp": item.related_mvp,
        "spec_reference": item.spec_reference,
        "related_references": list(item.related_references),
        "metadata": _serialize_value(item.metadata),
    }


def release_notes_section_to_dict(section: ReleaseNotesSection) -> dict[str, Any]:
    """Serialize ReleaseNotesSection to a JSON-safe dict."""
    return {
        "section_kind": section.section_kind.value,
        "title": section.title,
        "section_notes": section.section_notes,
        "change_items": [release_notes_change_item_to_dict(item) for item in section.change_items],
        "metadata": _serialize_value(section.metadata),
    }


def release_notes_summary_to_dict(summary: ReleaseNotesSummary) -> dict[str, Any]:
    """Serialize ReleaseNotesSummary to a JSON-safe dict."""
    return {
        "total_sections": summary.total_sections,
        "total_change_items": summary.total_change_items,
        "critical_count": summary.critical_count,
        "high_count": summary.high_count,
        "medium_count": summary.medium_count,
        "low_count": summary.low_count,
        "info_count": summary.info_count,
        "release_notes_state": summary.release_notes_state,
        "reason_code_counts": _serialize_value(summary.reason_code_counts),
        "release_notes": summary.release_notes,
    }


def release_notes_data_quality_to_dict(data_quality: ReleaseNotesDataQuality) -> dict[str, Any]:
    """Serialize ReleaseNotesDataQuality to a JSON-safe dict."""
    return {
        "completeness_pct": data_quality.completeness_pct,
        "coverage_pct": data_quality.coverage_pct,
        "sections_present": data_quality.sections_present,
        "sections_missing": data_quality.sections_missing,
        "total_sections": data_quality.total_sections,
        "change_items_with_specs": data_quality.change_items_with_specs,
        "change_items_without_specs": data_quality.change_items_without_specs,
        "reason": data_quality.reason,
    }


def research_release_notes_to_dict(release_notes: ResearchReleaseNotes) -> dict[str, Any]:
    """Serialize ResearchReleaseNotes to a deterministic JSON-safe dict."""
    return {
        "release_notes_id": release_notes.release_notes_id,
        "generated_at": release_notes.generated_at.isoformat(),
        "version": release_notes.version,
        "kind": release_notes.kind.value,
        "release_notes_state": release_notes.release_notes_state.value,
        "release_version": release_notes.release_version,
        "release_title": release_notes.release_title,
        "sections": [release_notes_section_to_dict(s) for s in release_notes.sections],
        "summary": release_notes_summary_to_dict(release_notes.summary),
        "data_quality": release_notes_data_quality_to_dict(release_notes.data_quality),
        "safety_flags": release_notes_safety_flags_to_dict(release_notes.safety_flags),
        "config": release_notes_config_to_dict(release_notes.config),
        "reason_codes": list(release_notes.reason_codes),
        "document_notes": release_notes.document_notes,
    }


def _section_kind_title(section_kind: ReleaseNotesSectionKind) -> str:
    """Return a human-readable Markdown title for a section kind."""
    mapping = {
        ReleaseNotesSectionKind.OVERVIEW: "Overview",
        ReleaseNotesSectionKind.VERSION_AND_SCOPE: "Version and Scope",
        ReleaseNotesSectionKind.ARTIFACT_CHAIN: "Artifact Chain",
        ReleaseNotesSectionKind.COMPLETED_MVPS: "Completed MVPs",
        ReleaseNotesSectionKind.KNOWN_GAPS: "Known Gaps",
        ReleaseNotesSectionKind.SAFETY_BOUNDARIES: "Safety Boundaries",
        ReleaseNotesSectionKind.HUMAN_REVIEW_GUIDE: "Human Review Guide",
        ReleaseNotesSectionKind.APPENDIX_REFERENCES: "Appendix References",
    }
    return mapping.get(section_kind, section_kind.value)


def research_release_notes_to_markdown(release_notes: ResearchReleaseNotes) -> str:
    """Render ResearchReleaseNotes as deterministic Markdown."""
    lines: list[str] = [
        "# Local Research Release Notes / Audit Change Summary",
        "",
        _SAFETY_NOTICE,
        "",
        "## Release Notes Identity",
        "",
        f"- **release_notes_id:** `{release_notes.release_notes_id}`",
        f"- **version:** {release_notes.version}",
        f"- **kind:** {release_notes.kind.value}",
        f"- **release_notes_state:** {release_notes.release_notes_state.value}",
        f"- **generated_at:** {release_notes.generated_at.isoformat()}",
        "",
    ]

    if release_notes.release_version or release_notes.release_title:
        lines.extend([
            "## Version and Scope",
            "",
        ])
        if release_notes.release_version:
            lines.append(f"- **release_version:** {release_notes.release_version}")
        if release_notes.release_title:
            lines.append(f"- **release_title:** {release_notes.release_title}")
        lines.append("")

    lines.extend([
        "## Summary",
        "",
        f"- **total_sections:** {release_notes.summary.total_sections}",
        f"- **total_change_items:** {release_notes.summary.total_change_items}",
        f"- **critical_count:** {release_notes.summary.critical_count}",
        f"- **high_count:** {release_notes.summary.high_count}",
        f"- **medium_count:** {release_notes.summary.medium_count}",
        f"- **low_count:** {release_notes.summary.low_count}",
        f"- **info_count:** {release_notes.summary.info_count}",
        f"- **release_notes_state:** {release_notes.summary.release_notes_state}",
        "",
        "## Data Quality",
        "",
        f"- **completeness_pct:** {release_notes.data_quality.completeness_pct}",
        f"- **coverage_pct:** {release_notes.data_quality.coverage_pct}",
        f"- **sections_present:** {release_notes.data_quality.sections_present}",
        f"- **sections_missing:** {release_notes.data_quality.sections_missing}",
        f"- **total_sections:** {release_notes.data_quality.total_sections}",
        f"- **change_items_with_specs:** {release_notes.data_quality.change_items_with_specs}",
        f"- **change_items_without_specs:** {release_notes.data_quality.change_items_without_specs}",
        f"- **reason:** {release_notes.data_quality.reason}",
        "",
    ])

    lines.extend([
        "## Sections",
        "",
    ])

    if not release_notes.sections:
        lines.append("_No sections._")
        lines.append("")
    else:
        for section in release_notes.sections:
            lines.append(f"### {_section_kind_title(section.section_kind)}")
            lines.append("")
            if section.section_notes:
                lines.append(section.section_notes)
                lines.append("")
            if section.change_items:
                lines.append("#### Change Items")
                lines.append("")
                for item in section.change_items:
                    lines.append(f"- **{item.title}** (`{item.severity}`)")
                    if item.change_kind:
                        lines.append(f"  - **change_kind:** {item.change_kind}")
                    if item.description:
                        lines.append(f"  - **description:** {item.description}")
                    if item.related_mvp:
                        lines.append(f"  - **related_mvp:** {item.related_mvp}")
                    if item.spec_reference:
                        lines.append(f"  - **spec_reference:** {item.spec_reference}")
                    if item.related_references:
                        lines.append(f"  - **related_references:** {', '.join(item.related_references)}")
                    if item.metadata:
                        lines.append("  - **metadata:**")
                        for key, value in item.metadata.items():
                            lines.append(f"    - **{key}:** {_serialize_value(value)}")
                lines.append("")
            else:
                lines.append("_No change items._")
                lines.append("")

    lines.extend([
        "## Reason Codes",
        "",
    ])
    if release_notes.reason_codes:
        for rc in release_notes.reason_codes:
            lines.append(f"- {rc}")
    else:
        lines.append("_No reason codes._")
    lines.append("")

    lines.extend([
        "## Document Notes",
        "",
        release_notes.document_notes,
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


def atomic_write_json_research_release_notes(
    release_notes: ResearchReleaseNotes,
    target_path: str | Path | None = None,
) -> Path:
    """Write a ResearchReleaseNotes to JSON atomically."""
    if target_path is None:
        target_path = DEFAULT_RESEARCH_RELEASE_NOTES_JSON_PATH
    target = Path(target_path)
    data = research_release_notes_to_dict(release_notes)
    text = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False)
    return _atomic_write_text(target, text + "\n")


def atomic_write_markdown_research_release_notes(
    release_notes: ResearchReleaseNotes,
    target_path: str | Path | None = None,
) -> Path:
    """Write a ResearchReleaseNotes to Markdown atomically."""
    if target_path is None:
        target_path = DEFAULT_RESEARCH_RELEASE_NOTES_MARKDOWN_PATH
    target = Path(target_path)
    text = research_release_notes_to_markdown(release_notes)
    return _atomic_write_text(target, text)


def write_research_release_notes(
    release_notes: ResearchReleaseNotes,
    json_path: str | Path | None = None,
    markdown_path: str | Path | None = None,
) -> tuple[Path, Path]:
    """Write both JSON and Markdown representations of the release notes."""
    json_out = atomic_write_json_research_release_notes(release_notes, target_path=json_path)
    md_out = atomic_write_markdown_research_release_notes(release_notes, target_path=markdown_path)
    return json_out, md_out
