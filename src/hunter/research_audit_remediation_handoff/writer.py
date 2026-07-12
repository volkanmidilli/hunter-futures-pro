"""Deterministic writer for the Research Audit Remediation Handoff Packet (MVP-50).

The writer serializes `HandoffPacket` to JSON and Markdown. Output is local
and audit-only. It never reads from `data/` or `reports/`, and guards generated
text against forbidden readiness/trading phrases.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping
from dataclasses import is_dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any

from hunter.remediation_backlog.models import (
    RemediationBacklogSafetyFlags,
)

from .models import HandoffPacket


DEFAULT_JSON_PATH: Path = Path(
    "data/research_audit_remediation_handoff/handoff_packet.json"
)
DEFAULT_MD_PATH: Path = Path(
    "reports/research_audit_remediation_handoff/handoff_packet.md"
)

_SAFETY_NOTICE = (
    "This Research Audit Remediation Handoff Packet is a human-audit / "
    "research-only artifact. It is not an approval, certification, production "
    "readiness assessment, trading readiness assessment, recommendation, "
    "suitability assessment, signal, or executable remediation plan. It does "
    "not emit shell commands, code patches, deployment steps, or trading actions. "
    "All references are opaque identifiers and are never opened, followed, "
    "traversed, validated, fetched, or executed."
)

_PRIORITY_NOTICE = (
    "Priority values are for human-review ordering only. They are not "
    "implementation instructions, deployment instructions, or execution schedules."
)


class HandoffPacketWriterError(Exception):
    """Base exception for the handoff packet writer."""


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
    if value is None:
        return None
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value
    if isinstance(value, datetime):
        return _iso(value)
    if isinstance(value, (list, tuple)):
        return [_serialize_value(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return sorted(_serialize_value(v) for v in value)
    if isinstance(value, (MappingProxyType, Mapping)):
        return {str(k): _serialize_value(v) for k, v in sorted(value.items())}
    if is_dataclass(value) and not isinstance(value, type):
        return _dataclass_to_dict(value)
    return str(value)


def _dataclass_to_dict(obj: Any) -> dict[str, Any]:
    """Convert a frozen dataclass instance to a deterministic JSON-safe dict."""
    if not is_dataclass(obj) or isinstance(obj, type):
        raise TypeError(f"expected dataclass instance, got {type(obj)}")
    result = {field: _serialize_value(getattr(obj, field)) for field in obj.__dataclass_fields__}
    if isinstance(obj, RemediationBacklogSafetyFlags):
        result["is_safe"] = obj.is_safe
    return result


# ---------------------------------------------------------------------------
# Dict / JSON serialization
# ---------------------------------------------------------------------------


def handoff_packet_to_dict(packet: HandoffPacket) -> dict[str, Any]:
    """Convert a HandoffPacket to a deterministic JSON-safe dictionary."""
    data: dict[str, Any] = {
        "kind": "research_audit_remediation_handoff_packet",
        "version": "1.0",
        "safety_notice": _SAFETY_NOTICE,
        "priority_notice": _PRIORITY_NOTICE,
        "packet_id": packet.packet_id,
        "source_report_id": packet.source_report_id,
        "generated_at": packet.generated_at,
        "project_version": packet.project_version,
        "owner": packet.owner,
        "reviewer": packet.reviewer,
        "notes": packet.notes,
        "state": packet.state,
        "total_items": packet.total_items,
        "total_blocking": packet.total_blocking,
        "total_advisory": packet.total_advisory,
        "total_info": packet.total_info,
        "group_count": packet.group_count,
        "safety_flags": _dataclass_to_dict(packet.safety_flags),
        "data_quality": _dataclass_to_dict(packet.data_quality),
        "groups": [_dataclass_to_dict(g) for g in packet.groups],
    }
    return data


def handoff_packet_to_json(packet: HandoffPacket, indent: int | None = 2) -> str:
    """Serialize a HandoffPacket to a JSON string."""
    data = handoff_packet_to_dict(packet)
    return json.dumps(data, indent=indent, sort_keys=True, ensure_ascii=True)


# ---------------------------------------------------------------------------
# Markdown serialization
# ---------------------------------------------------------------------------


def _escape_markdown(text: str) -> str:
    """Escape minimal Markdown characters to keep output text safe."""
    return text.replace("|", "\\|")


def handoff_packet_to_markdown(packet: HandoffPacket) -> str:
    """Serialize a HandoffPacket to a Markdown summary."""
    lines: list[str] = [
        "# Research Audit Remediation Handoff Packet",
        "",
        "## Safety Notice",
        "",
        _SAFETY_NOTICE,
        "",
        "## Priority Notice",
        "",
        _PRIORITY_NOTICE,
        "",
        "## Packet Metadata",
        "",
        f"- **packet_id:** {packet.packet_id}",
        f"- **source_report_id:** {packet.source_report_id}",
        f"- **generated_at:** {packet.generated_at}",
        f"- **project_version:** {packet.project_version}",
        f"- **state:** {packet.state}",
        f"- **owner:** {packet.owner or '—'}",
        f"- **reviewer:** {packet.reviewer or '—'}",
        f"- **notes:** {packet.notes or '—'}",
        "",
        "## Summary Counts",
        "",
        f"- **total_items:** {packet.total_items}",
        f"- **total_blocking:** {packet.total_blocking}",
        f"- **total_advisory:** {packet.total_advisory}",
        f"- **total_info:** {packet.total_info}",
        f"- **group_count:** {packet.group_count}",
        "",
    ]

    if packet.safety_flags.has_forbidden_terms:
        lines.extend([
            "## Safety Warning",
            "",
            "Forbidden readiness/trading terminology was detected in the handoff "
            "packet content. This packet must be reviewed by a human before use "
            "and must not be treated as an approval or recommendation.",
            "",
        ])

    lines.extend([
        "## Groups",
        "",
    ])

    for group in packet.groups:
        lines.extend([
            f"### Group `{group.group_id}`",
            "",
            f"- **severity:** {group.severity}",
            f"- **priority:** {group.priority}",
            f"- **item_type:** {group.item_type}",
            f"- **reason_code:** {group.reason_code}",
            f"- **family:** {group.family}",
            f"- **item_count:** {group.item_count}",
            f"- **blocking_count:** {group.blocking_count}",
            f"- **advisory_count:** {group.advisory_count}",
            f"- **info_count:** {group.info_count}",
            "",
            "#### Items",
            "",
            "| item_id | title | severity | priority | item_state |",
            "|--------|-------|----------|----------|------------|",
        ])
        for item in group.items:
            item_id = _escape_markdown(str(item.get("item_id", "—")))
            title = _escape_markdown(str(item.get("title", "—")))
            severity = _escape_markdown(str(item.get("severity", "—")))
            priority = _escape_markdown(str(item.get("priority", "—")))
            item_state = _escape_markdown(str(item.get("item_state", "—")))
            lines.append(f"| {item_id} | {title} | {severity} | {priority} | {item_state} |")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Atomic file writers
# ---------------------------------------------------------------------------


def _ensure_parent_dir(path: Path) -> None:
    """Create the parent directory if it does not exist."""
    if path.parent:
        path.parent.mkdir(parents=True, exist_ok=True)


def atomic_write_json_handoff_packet(
    packet: HandoffPacket,
    path: Path | str = DEFAULT_JSON_PATH,
) -> Path:
    """Write a HandoffPacket to a JSON file atomically.

    This function never reads from `data/` or `reports/`; it only writes.
    """
    target = Path(path)
    _ensure_parent_dir(target)
    content = handoff_packet_to_json(packet)
    fd, tmp_path = tempfile.mkstemp(dir=target.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, target)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
    return target


def atomic_write_markdown_handoff_packet(
    packet: HandoffPacket,
    path: Path | str = DEFAULT_MD_PATH,
) -> Path:
    """Write a HandoffPacket to a Markdown file atomically.

    This function never reads from `data/` or `reports/`; it only writes.
    """
    target = Path(path)
    _ensure_parent_dir(target)
    content = handoff_packet_to_markdown(packet)
    fd, tmp_path = tempfile.mkstemp(dir=target.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, target)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
    return target
