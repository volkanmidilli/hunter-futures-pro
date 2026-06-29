"""Writer for hunter.research_digest package.

Deterministic JSON and Markdown serialization for ResearchDigest with atomic
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

from hunter.research_digest.models import (
    DIGEST_VERSION,
    DigestConfig,
    DigestDataQuality,
    DigestSafetyFlags,
    DigestSection,
    DigestSectionKind,
    DigestState,
    DigestSummary,
    ResearchDigest,
)


DEFAULT_DIGEST_JSON_PATH = Path("data/research_digest/latest_research_digest.json")
DEFAULT_DIGEST_MARKDOWN_PATH = Path("reports/research_digest/latest_research_digest.md")


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


def digest_safety_flags_to_dict(flags: DigestSafetyFlags) -> dict[str, Any]:
    """Serialize DigestSafetyFlags to a JSON-safe dict."""
    return {
        "dry_run": flags.dry_run,
        "live_trading_enabled": flags.live_trading_enabled,
        "real_orders_enabled": flags.real_orders_enabled,
        "leverage_enabled": flags.leverage_enabled,
        "shorting_enabled": flags.shorting_enabled,
        "digest_output_is_human_audit_only": flags.digest_output_is_human_audit_only,
        "digest_output_not_trading_signal": flags.digest_output_not_trading_signal,
        "digest_output_not_trade_approval": flags.digest_output_not_trade_approval,
        "digest_output_not_for_execution": flags.digest_output_not_for_execution,
        "digest_output_not_for_strategy": flags.digest_output_not_for_strategy,
        "digest_output_not_for_freqtrade": flags.digest_output_not_for_freqtrade,
        "digest_output_not_for_order": flags.digest_output_not_for_order,
        "digest_output_not_for_exchange": flags.digest_output_not_for_exchange,
        "digest_feedback_into_execution": flags.digest_feedback_into_execution,
        "cross_layer_feedback_into_execution": flags.cross_layer_feedback_into_execution,
        "trace_linkage_advisory_only": flags.trace_linkage_advisory_only,
        "file_refs_not_traversed": flags.file_refs_not_traversed,
    }


def digest_config_to_dict(config: DigestConfig) -> dict[str, Any]:
    """Serialize DigestConfig to a JSON-safe dict."""
    return {
        "version": config.version,
        "generated_at": _iso(config.generated_at) if config.generated_at is not None else None,
        "output_format": config.output_format,
        "dry_run": config.dry_run,
        "live_trading_enabled": config.live_trading_enabled,
        "real_orders_enabled": config.real_orders_enabled,
        "leverage_enabled": config.leverage_enabled,
        "shorting_enabled": config.shorting_enabled,
        "stale_threshold_minutes": config.stale_threshold_minutes,
        "include_next_review_notes": config.include_next_review_notes,
        "include_safety_flags": config.include_safety_flags,
        "include_unresolved_blockers": config.include_unresolved_blockers,
        "include_reason_code_summary": config.include_reason_code_summary,
    }


def digest_section_to_dict(section: DigestSection) -> dict[str, Any]:
    """Serialize DigestSection to a JSON-safe dict."""
    return {
        "section_kind": section.section_kind.value,
        "state": section.state,
        "count": section.count,
        "blocked_count": section.blocked_count,
        "ready_count": section.ready_count,
        "missing_count": section.missing_count,
        "reason_codes": list(section.reason_codes),
        "blockers_count": section.blockers_count,
        "unresolved_blocker_reasons": list(section.unresolved_blocker_reasons),
        "notes": section.notes,
        "metadata": _serialize_value(section.metadata) if section.metadata else {},
    }


def digest_summary_to_dict(summary: DigestSummary) -> dict[str, Any]:
    """Serialize DigestSummary to a JSON-safe dict."""
    return {
        "total_sections": summary.total_sections,
        "ready_sections": summary.ready_sections,
        "blocked_sections": summary.blocked_sections,
        "missing_sections": summary.missing_sections,
        "total_artifacts": summary.total_artifacts,
        "total_blockers": summary.total_blockers,
        "unresolved_blockers": summary.unresolved_blockers,
        "reason_code_counts": dict(summary.reason_code_counts) if summary.reason_code_counts else {},
        "cross_layer_ready": summary.cross_layer_ready,
        "next_review_notes": summary.next_review_notes,
    }


def digest_data_quality_to_dict(data_quality: DigestDataQuality) -> dict[str, Any]:
    """Serialize DigestDataQuality to a JSON-safe dict."""
    return {
        "completeness_pct": data_quality.completeness_pct,
        "missing_count": data_quality.missing_count,
        "stale_count": data_quality.stale_count,
        "invalid_count": data_quality.invalid_count,
        "blocked_count": data_quality.blocked_count,
        "total_sections": data_quality.total_sections,
        "reason": data_quality.reason,
    }


def research_digest_to_dict(digest: ResearchDigest) -> dict[str, Any]:
    """Serialize ResearchDigest to a JSON-safe dict deterministically."""
    return {
        "digest_id": digest.digest_id,
        "generated_at": _iso(digest.generated_at),
        "version": digest.version,
        "state": digest.state.value,
        "sections": [digest_section_to_dict(section) for section in digest.sections],
        "summary": digest_summary_to_dict(digest.summary),
        "data_quality": digest_data_quality_to_dict(digest.data_quality),
        "safety_flags": digest_safety_flags_to_dict(digest.safety_flags),
        "config": digest_config_to_dict(digest.config),
        "reason_codes": list(digest.reason_codes),
        "next_review_notes": digest.next_review_notes,
    }


# ---------------------------------------------------------------------------
# Markdown serialization
# ---------------------------------------------------------------------------


_SAFETY_NOTICE = (
    "This local research digest is a human-audit artifact only. "
    "It is not a trading signal, not trade approval, not a recommendation engine, "
    "not an action-command generator, and must not be consumed by execution, strategy, "
    "Freqtrade shell, order, exchange, or any MVP execution path."
)


def research_digest_to_markdown(digest: ResearchDigest) -> str:
    """Render ResearchDigest as human-readable Markdown with safety notice."""
    summary = digest.summary
    data_quality = digest.data_quality
    flags = digest.safety_flags

    lines: list[str] = [
        "# Research Digest — Executive Summary",
        "",
        f"> {_SAFETY_NOTICE}",
        "",
        "## Digest Info",
        "",
        f"- **digest_id**: {digest.digest_id}",
        f"- **generated_at**: {_iso(digest.generated_at)}",
        f"- **version**: {digest.version}",
        f"- **state**: {digest.state.value}",
        f"- **section_count**: {len(digest.sections)}",
        "",
        "## Safety Notice",
        "",
        "This research digest is a **human-audit artifact only**.",
        "",
        "- It is **not a trading signal**.",
        "- It is **not trade approval**.",
        "- It is **not a recommendation engine**.",
        "- It is **not an action-command generator**.",
        "- It **must not be consumed by execution, strategy, Freqtrade shell, order, exchange, or any MVP execution path**.",
        "- File references and metadata strings in this digest are **local strings only** and are **not traversed, opened, followed, validated, or executed**.",
        "",
        "## Summary",
        "",
        f"- **total_sections**: {summary.total_sections}",
        f"- **ready_sections**: {summary.ready_sections}",
        f"- **blocked_sections**: {summary.blocked_sections}",
        f"- **missing_sections**: {summary.missing_sections}",
        f"- **total_artifacts**: {summary.total_artifacts}",
        f"- **total_blockers**: {summary.total_blockers}",
        f"- **unresolved_blockers**: {summary.unresolved_blockers}",
        f"- **cross_layer_ready**: {summary.cross_layer_ready}",
        "",
    ]

    lines.extend(["### Reason Code Counts", ""])
    if summary.reason_code_counts:
        for code, count in summary.reason_code_counts.items():
            lines.append(f"- {code}: {count}")
    else:
        lines.append("- none")
    lines.append("")

    lines.extend([
        "## Sections",
        "",
    ])
    if not digest.sections:
        lines.append("_No sections._")
        lines.append("")
    else:
        lines.append("| kind | state | count | blockers | notes |")
        lines.append("|------|-------|-------|----------|-------|")
        for section in digest.sections:
            notes_snippet = (section.notes or "").replace("|", "\\|")[:80]
            lines.append(
                f"| {section.section_kind.value} | {section.state} | {section.count} | {section.blockers_count} | {notes_snippet} |"
            )
        lines.append("")

        for section in digest.sections:
            if section.reason_codes or section.unresolved_blocker_reasons:
                lines.append(f"### {section.section_kind.value}")
                lines.append("")
                if section.reason_codes:
                    lines.append(f"- **reason_codes**: {', '.join(section.reason_codes)}")
                if section.unresolved_blocker_reasons:
                    lines.append(f"- **unresolved_blocker_reasons**: {', '.join(section.unresolved_blocker_reasons)}")
                if section.metadata:
                    lines.append("- **metadata**:")
                    for key, value in section.metadata.items():
                        lines.append(f"  - {key}: {value}")
                lines.append("")

    lines.extend([
        "## Data Quality",
        "",
        f"- **completeness_pct**: {data_quality.completeness_pct}",
        f"- **missing_count**: {data_quality.missing_count}",
        f"- **stale_count**: {data_quality.stale_count}",
        f"- **invalid_count**: {data_quality.invalid_count}",
        f"- **blocked_count**: {data_quality.blocked_count}",
        f"- **total_sections**: {data_quality.total_sections}",
        f"- **reason**: {data_quality.reason}",
        "",
    ])

    lines.extend(["## Safety Flags", ""])
    for key, value in digest_safety_flags_to_dict(flags).items():
        lines.append(f"- **{key}**: {value}")
    lines.append("")

    lines.extend(["## Reason Codes", ""])
    if digest.reason_codes:
        for code in digest.reason_codes:
            lines.append(f"- {code}")
    else:
        lines.append("- none")
    lines.append("")

    lines.extend([
        "## Next Review Notes",
        "",
        summary.next_review_notes if summary.next_review_notes else "_No next review notes._",
        "",
    ])

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


def atomic_write_json_research_digest(
    digest: ResearchDigest,
    target_path: Path | None = None,
) -> Path:
    """Serialize ResearchDigest to JSON and write atomically."""
    path = target_path if target_path is not None else DEFAULT_DIGEST_JSON_PATH
    data = research_digest_to_dict(digest)
    text = json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True)
    text += "\n"
    _atomic_write(path, text)
    return path


def atomic_write_markdown_research_digest(
    digest: ResearchDigest,
    target_path: Path | None = None,
) -> Path:
    """Serialize ResearchDigest to Markdown and write atomically."""
    path = target_path if target_path is not None else DEFAULT_DIGEST_MARKDOWN_PATH
    _atomic_write(path, research_digest_to_markdown(digest) + "\n")
    return path


def write_research_digest(
    digest: ResearchDigest,
    json_path: Path | None = None,
    markdown_path: Path | None = None,
) -> tuple[Path, Path]:
    """Write ResearchDigest to both JSON and Markdown."""
    json_out = atomic_write_json_research_digest(digest, json_path)
    markdown_out = atomic_write_markdown_research_digest(digest, markdown_path)
    return json_out, markdown_out
