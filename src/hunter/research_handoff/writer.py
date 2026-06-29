"""Writer for hunter.research_handoff package.

Deterministic JSON and Markdown serialization for ResearchHandoffPacket with
atomic writes. Output is human-audit only; no file references are traversed,
opened, followed, validated, or executed here.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from hunter.research_handoff.models import (
    HANDOFF_VERSION,
    HandoffConfig,
    HandoffDataQuality,
    HandoffPacketKind,
    HandoffSafetyFlags,
    HandoffSection,
    HandoffState,
    HandoffSummary,
    ResearchHandoffPacket,
)


DEFAULT_HANDOFF_JSON_PATH = Path(
    "data/research_handoff/latest_research_handoff_packet.json"
)
DEFAULT_HANDOFF_MARKDOWN_PATH = Path(
    "reports/research_handoff/latest_research_handoff_packet.md"
)


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


def handoff_safety_flags_to_dict(flags: HandoffSafetyFlags) -> dict[str, Any]:
    """Serialize HandoffSafetyFlags to a JSON-safe dict."""
    return {
        "dry_run": flags.dry_run,
        "live_trading_enabled": flags.live_trading_enabled,
        "real_orders_enabled": flags.real_orders_enabled,
        "leverage_enabled": flags.leverage_enabled,
        "shorting_enabled": flags.shorting_enabled,
        "handoff_output_is_human_audit_only": flags.handoff_output_is_human_audit_only,
        "handoff_output_not_trading_signal": flags.handoff_output_not_trading_signal,
        "handoff_output_not_trade_approval": flags.handoff_output_not_trade_approval,
        "handoff_output_not_execution_readiness": flags.handoff_output_not_execution_readiness,
        "handoff_output_not_strategy_readiness": flags.handoff_output_not_strategy_readiness,
        "handoff_output_not_for_execution": flags.handoff_output_not_for_execution,
        "handoff_output_not_for_strategy": flags.handoff_output_not_for_strategy,
        "handoff_output_not_for_freqtrade": flags.handoff_output_not_for_freqtrade,
        "handoff_output_not_for_order": flags.handoff_output_not_for_order,
        "handoff_output_not_for_exchange": flags.handoff_output_not_for_exchange,
        "handoff_feedback_into_execution": flags.handoff_feedback_into_execution,
        "cross_layer_feedback_into_execution": flags.cross_layer_feedback_into_execution,
        "file_refs_not_traversed": flags.file_refs_not_traversed,
    }


def handoff_config_to_dict(config: HandoffConfig) -> dict[str, Any]:
    """Serialize HandoffConfig to a JSON-safe dict."""
    return {
        "version": config.version,
        "generated_at": _iso(config.generated_at) if config.generated_at is not None else None,
        "output_format": config.output_format,
        "dry_run": config.dry_run,
        "live_trading_enabled": config.live_trading_enabled,
        "real_orders_enabled": config.real_orders_enabled,
        "leverage_enabled": config.leverage_enabled,
        "shorting_enabled": config.shorting_enabled,
        "block_on_unknown": config.block_on_unknown,
        "required_sections": [kind.value for kind in config.required_sections],
        "max_staleness_minutes": config.max_staleness_minutes,
        "include_handoff_notes": config.include_handoff_notes,
    }


def handoff_section_to_dict(section: HandoffSection) -> dict[str, Any]:
    """Serialize HandoffSection to a JSON-safe dict."""
    return {
        "section_kind": section.section_kind.value,
        "title": section.title,
        "state": section.state,
        "summary_text": section.summary_text,
        "local_reference": section.local_reference,
        "reason_codes": list(section.reason_codes),
        "metadata": _serialize_value(section.metadata) if section.metadata else {},
    }


def handoff_summary_to_dict(summary: HandoffSummary) -> dict[str, Any]:
    """Serialize HandoffSummary to a JSON-safe dict."""
    return {
        "total_sections": summary.total_sections,
        "ready_sections": summary.ready_sections,
        "warn_sections": summary.warn_sections,
        "block_sections": summary.block_sections,
        "unknown_sections": summary.unknown_sections,
        "quality_gate_verdict": summary.quality_gate_verdict,
        "handoff_state": summary.handoff_state,
        "reason_code_counts": dict(summary.reason_code_counts) if summary.reason_code_counts else {},
        "handoff_notes": summary.handoff_notes,
    }


def handoff_data_quality_to_dict(data_quality: HandoffDataQuality) -> dict[str, Any]:
    """Serialize HandoffDataQuality to a JSON-safe dict."""
    return {
        "completeness_pct": data_quality.completeness_pct,
        "ready_pct": data_quality.ready_pct,
        "missing_count": data_quality.missing_count,
        "stale_count": data_quality.stale_count,
        "blocked_count": data_quality.blocked_count,
        "unknown_count": data_quality.unknown_count,
        "total_sections": data_quality.total_sections,
        "reason": data_quality.reason,
    }


def research_handoff_packet_to_dict(packet: ResearchHandoffPacket) -> dict[str, Any]:
    """Serialize ResearchHandoffPacket to a JSON-safe dict deterministically."""
    return {
        "packet_id": packet.packet_id,
        "generated_at": _iso(packet.generated_at),
        "version": packet.version,
        "handoff_state": packet.handoff_state.value,
        "sections": [handoff_section_to_dict(section) for section in packet.sections],
        "summary": handoff_summary_to_dict(packet.summary),
        "data_quality": handoff_data_quality_to_dict(packet.data_quality),
        "safety_flags": handoff_safety_flags_to_dict(packet.safety_flags),
        "config": handoff_config_to_dict(packet.config),
        "reason_codes": list(packet.reason_codes),
        "handoff_notes": packet.handoff_notes,
    }


# ---------------------------------------------------------------------------
# Markdown serialization
# ---------------------------------------------------------------------------


_SAFETY_NOTICE = (
    "This local research handoff packet is a human-audit / contractor-handoff "
    "artifact only. It is not a trading signal, not trade approval, not execution "
    "approval, not strategy approval, not release approval, not transaction "
    "permission, and must not be consumed by execution, strategy, Freqtrade shell, "
    "transaction placement, exchange, or any MVP execution path."
)


def _section_title(section: HandoffSection) -> str:
    """Return section title, falling back to a human-readable kind title."""
    if section.title:
        return section.title
    return section.section_kind.value.replace("_", " ").title()


def research_handoff_packet_to_markdown(packet: ResearchHandoffPacket) -> str:
    """Render ResearchHandoffPacket as human-readable Markdown with safety notice."""
    summary = packet.summary
    data_quality = packet.data_quality
    flags = packet.safety_flags

    lines: list[str] = [
        "# Research Handoff Packet — Audit Readiness",
        "",
        f"> {_SAFETY_NOTICE}",
        "",
        "## Packet Info",
        "",
        f"- **packet_id**: {packet.packet_id}",
        f"- **generated_at**: {_iso(packet.generated_at)}",
        f"- **version**: {packet.version}",
        f"- **handoff_state**: {packet.handoff_state.value}",
        f"- **section_count**: {len(packet.sections)}",
        "",
        "## Safety Notice",
        "",
        "This research handoff packet is a **human-audit / contractor-handoff artifact only**.",
        "",
        "- It is **not a trading signal**.",
        "- It is **not trade approval**.",
        "- It is **not execution approval**.",
        "- It is **not strategy approval**.",
        "- It is **not release approval**.",
        "- It is **not transaction permission**.",
        "- It is **not for execution**, **not for strategy**, **not for Freqtrade shell**, **not for transaction placement**, **not for exchange**, and **must not be consumed by any MVP execution path**.",
        "- File references and metadata strings in this packet are **local strings only** and are **not traversed, opened, followed, validated, or executed**.",
        "",
        "## Handoff State Interpretation",
        "",
        f"**{packet.handoff_state.value}**: {summary.handoff_notes}",
        "",
        "## Summary",
        "",
        f"- **total_sections**: {summary.total_sections}",
        f"- **ready_sections**: {summary.ready_sections}",
        f"- **warn_sections**: {summary.warn_sections}",
        f"- **block_sections**: {summary.block_sections}",
        f"- **unknown_sections**: {summary.unknown_sections}",
        f"- **quality_gate_verdict**: {summary.quality_gate_verdict}",
        f"- **handoff_state**: {summary.handoff_state}",
        "",
    ]

    lines.extend(["### Reason Code Counts", ""])
    if summary.reason_code_counts:
        for code, count in summary.reason_code_counts.items():
            lines.append(f"- {code}: {count}")
    else:
        lines.append("- none")
    lines.append("")

    lines.extend(["## Sections", ""])
    if not packet.sections:
        lines.append("_No sections._")
        lines.append("")
    else:
        lines.append("| kind | state | local_reference | reason_codes | summary |")
        lines.append("|------|-------|-----------------|--------------|---------|")
        sorted_sections = sorted(packet.sections, key=lambda s: list(HandoffPacketKind).index(s.section_kind))
        for section in sorted_sections:
            summary_snippet = (section.summary_text or "").replace("|", "\\|")[:80]
            reason_codes_str = ", ".join(section.reason_codes) if section.reason_codes else "none"
            local_ref = (section.local_reference or "").replace("|", "\\|")
            lines.append(
                f"| {section.section_kind.value} | {section.state} | {local_ref} | "
                f"{reason_codes_str} | {summary_snippet} |"
            )
        lines.append("")

        for section in sorted_sections:
            lines.append(f"### {_section_title(section)}")
            lines.append("")
            lines.append(f"- **kind**: {section.section_kind.value}")
            lines.append(f"- **state**: {section.state}")
            lines.append(f"- **local_reference**: {section.local_reference}")
            if section.reason_codes:
                lines.append(f"- **reason_codes**: {', '.join(section.reason_codes)}")
            if section.summary_text:
                lines.append(f"- **summary**: {section.summary_text}")
            if section.metadata:
                lines.append("- **metadata**:")
                for key, value in handoff_section_to_dict(section)["metadata"].items():
                    lines.append(f"  - {key}: {value}")
            lines.append("")

    lines.extend([
        "## Data Quality",
        "",
        f"- **completeness_pct**: {data_quality.completeness_pct}",
        f"- **ready_pct**: {data_quality.ready_pct}",
        f"- **missing_count**: {data_quality.missing_count}",
        f"- **stale_count**: {data_quality.stale_count}",
        f"- **blocked_count**: {data_quality.blocked_count}",
        f"- **unknown_count**: {data_quality.unknown_count}",
        f"- **total_sections**: {data_quality.total_sections}",
        f"- **reason**: {data_quality.reason}",
        "",
    ])

    lines.extend(["## Safety Flags", ""])
    for key, value in handoff_safety_flags_to_dict(flags).items():
        lines.append(f"- **{key}**: {value}")
    lines.append("")

    lines.extend(["## Reason Codes", ""])
    if packet.reason_codes:
        for code in packet.reason_codes:
            lines.append(f"- {code}")
    else:
        lines.append("- none")
    lines.append("")

    lines.extend([
        "## Configuration",
        "",
        f"- **version**: {packet.config.version}",
        f"- **output_format**: {packet.config.output_format}",
        f"- **dry_run**: {packet.config.dry_run}",
        f"- **block_on_unknown**: {packet.config.block_on_unknown}",
        f"- **max_staleness_minutes**: {packet.config.max_staleness_minutes}",
        f"- **required_sections**: {', '.join(kind.value for kind in packet.config.required_sections)}",
        "",
    ])

    lines.extend([
        "## Handoff Notes",
        "",
        summary.handoff_notes if summary.handoff_notes else "_No handoff notes._",
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


def atomic_write_json_research_handoff_packet(
    packet: ResearchHandoffPacket,
    target_path: Path | None = None,
) -> Path:
    """Serialize ResearchHandoffPacket to JSON and write atomically."""
    path = target_path if target_path is not None else DEFAULT_HANDOFF_JSON_PATH
    data = research_handoff_packet_to_dict(packet)
    text = json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True)
    text += "\n"
    _atomic_write(path, text)
    return path


def atomic_write_markdown_research_handoff_packet(
    packet: ResearchHandoffPacket,
    target_path: Path | None = None,
) -> Path:
    """Serialize ResearchHandoffPacket to Markdown and write atomically."""
    path = target_path if target_path is not None else DEFAULT_HANDOFF_MARKDOWN_PATH
    _atomic_write(path, research_handoff_packet_to_markdown(packet) + "\n")
    return path


def write_research_handoff_packet(
    packet: ResearchHandoffPacket,
    json_path: Path | None = None,
    markdown_path: Path | None = None,
) -> tuple[Path, Path]:
    """Write ResearchHandoffPacket to both JSON and Markdown."""
    json_out = atomic_write_json_research_handoff_packet(packet, json_path)
    markdown_out = atomic_write_markdown_research_handoff_packet(packet, markdown_path)
    return json_out, markdown_out
