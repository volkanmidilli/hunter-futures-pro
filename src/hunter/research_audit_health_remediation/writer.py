"""Deterministic writer for the Research Audit Health Remediation Bridge (MVP-49).

The writer serializes `RemediationBridgeReport` to JSON, CSV, and Markdown.
Output is local and audit-only. It never reads from `data/` or `reports/`, and it
guards generated text against forbidden readiness/trading phrases.
"""

from __future__ import annotations

import csv
import io
import json
import os
from collections.abc import Mapping
from dataclasses import is_dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any

from hunter.remediation_backlog.models import RemediationBacklogItem, RemediationBacklogSafetyFlags

from .models import RemediationBridgeReport


DEFAULT_JSON_PATH: Path = Path(
    "data/research_audit_health_remediation/remediation_bridge_report.json"
)
DEFAULT_CSV_PATH: Path = Path(
    "data/research_audit_health_remediation/remediation_bridge_items.csv"
)
DEFAULT_MD_PATH: Path = Path(
    "reports/research_audit_health_remediation/remediation_bridge_report.md"
)

_SAFETY_NOTICE = (
    "This Research Audit Health Remediation Bridge report is a human-audit / "
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


class RemediationBridgeWriterError(Exception):
    """Base exception for the bridge writer."""


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


def remediation_bridge_report_to_dict(report: RemediationBridgeReport) -> dict[str, Any]:
    """Convert a RemediationBridgeReport to a deterministic dictionary."""
    data: dict[str, Any] = {
        "kind": "research_audit_health_remediation_bridge_report",
        "version": "1.0",
        "safety_notice": _SAFETY_NOTICE,
        "priority_notice": _PRIORITY_NOTICE,
        "report_id": report.report_id,
        "source_report_id": report.source_report_id,
        "generated_at": report.generated_at,
        "items": [_serialize_value(item) for item in report.items],
        "data_quality": _serialize_value(report.data_quality),
        "safety_flags": _serialize_value(report.safety_flags),
    }
    return data


def remediation_bridge_report_to_json(report: RemediationBridgeReport, *, indent: int = 2) -> str:
    """Serialize a RemediationBridgeReport to deterministic JSON text."""
    data = remediation_bridge_report_to_dict(report)
    return json.dumps(data, indent=indent, ensure_ascii=False, sort_keys=False) + "\n"


# ---------------------------------------------------------------------------
# CSV serialization
# ---------------------------------------------------------------------------


_CSV_COLUMNS = (
    "report_id",
    "source_report_id",
    "generated_at",
    "item_id",
    "source_id",
    "finding_id",
    "item_type",
    "item_state",
    "severity",
    "priority",
    "owner",
    "reviewer",
    "reason_codes",
    "title",
    "description",
)


def _format_reason_codes(codes: tuple[Any, ...]) -> str:
    """Format reason codes for CSV using a deterministic semicolon join."""
    return ";".join(sorted(str(code.value if isinstance(code, Enum) else code) for code in codes))


def _csv_sort_key(item: RemediationBacklogItem) -> tuple[int, int, str, str, str]:
    """Return a deterministic sort key for CSV rows."""
    priority_order = {
        "p0": 0,
        "p1": 1,
        "p2": 2,
        "p3": 3,
        "none": 4,
    }
    severity_order = {
        "blocking": 0,
        "advisory": 1,
        "info": 2,
    }
    return (
        priority_order.get(item.priority.value if item.priority else "none", 4),
        severity_order.get(item.severity.value if item.severity else "advisory", 2),
        item.item_id or "",
        item.source_id or "",
        item.finding_id or "",
    )


def remediation_bridge_report_to_csv_text(report: RemediationBridgeReport) -> str:
    """Serialize bridge items to deterministic CSV rows."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(_CSV_COLUMNS)
    sorted_items = sorted(report.items, key=_csv_sort_key)
    for item in sorted_items:
        row = [
            report.report_id,
            report.source_report_id,
            report.generated_at,
            item.item_id or "",
            item.source_id or "",
            item.finding_id or "",
            item.item_type.value if item.item_type else "",
            item.item_state.value if item.item_state else "",
            item.severity.value if item.severity else "",
            item.priority.value if item.priority else "",
            item.owner or "",
            item.reviewer or "",
            _format_reason_codes(item.reason_codes),
            item.title or "",
            item.description or "",
        ]
        writer.writerow(row)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Markdown serialization
# ---------------------------------------------------------------------------


def _escape_pipe(text: str) -> str:
    """Escape pipe characters in Markdown table cells."""
    return text.replace("|", "\\|")


def _md_value(value: Any) -> str:
    """Stringify a value for Markdown, escaping pipe characters."""
    if value is None:
        return ""
    return _escape_pipe(str(value))


def remediation_bridge_report_to_markdown(report: RemediationBridgeReport) -> str:
    """Serialize a RemediationBridgeReport to deterministic Markdown text."""
    lines: list[str] = []
    lines.append("# Research Audit Health Remediation Bridge Report")
    lines.append("")
    lines.append(f"> {_SAFETY_NOTICE}")
    lines.append("")
    lines.append(f"> {_PRIORITY_NOTICE}")
    lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **report_id:** {report.report_id}")
    lines.append(f"- **source_report_id:** {report.source_report_id}")
    lines.append(f"- **generated_at:** {report.generated_at}")
    dq = report.data_quality
    lines.append(f"- **input_findings:** {dq.input_findings}")
    lines.append(f"- **produced_items:** {dq.produced_items}")
    lines.append(f"- **dropped_info:** {dq.dropped_info}")
    lines.append(f"- **duplicates_collapsed:** {dq.duplicates_collapsed}")
    lines.append(f"- **safety_flagged_items:** {dq.safety_flagged_items}")
    lines.append("")
    lines.append(
        "Backlog items are descriptive observations for human review only. "
        "They are not approval, certification, or trading readiness scores."
    )
    lines.append("")

    # Items
    lines.append("## Backlog Items")
    lines.append("")
    lines.append(
        "| item_id | priority | severity | item_type | item_state | source_id | "
        "finding_id | owner | reviewer | reason_codes | title |"
    )
    lines.append(
        "|---------|----------|----------|-----------|------------|-----------|"
        "------------|-------|----------|--------------|-------|"
    )
    sorted_items = sorted(report.items, key=_csv_sort_key)
    for item in sorted_items:
        lines.append(
            f"| {_md_value(item.item_id)} | {_md_value(item.priority.value if item.priority else '')} | "
            f"{_md_value(item.severity.value if item.severity else '')} | "
            f"{_md_value(item.item_type.value if item.item_type else '')} | "
            f"{_md_value(item.item_state.value if item.item_state else '')} | "
            f"{_md_value(item.source_id)} | {_md_value(item.finding_id)} | "
            f"{_md_value(item.owner)} | {_md_value(item.reviewer)} | "
            f"{_md_value(_format_reason_codes(item.reason_codes))} | {_md_value(item.title)} |"
        )
    if not report.items:
        lines.append("| _none_ | | | | | | | | | | |")
    lines.append("")

    # Data quality
    lines.append("## Data Quality")
    lines.append("")
    lines.append(f"- **input_findings:** {dq.input_findings}")
    lines.append(f"- **produced_items:** {dq.produced_items}")
    lines.append(f"- **dropped_info:** {dq.dropped_info}")
    lines.append(f"- **duplicates_collapsed:** {dq.duplicates_collapsed}")
    lines.append(f"- **safety_flagged_items:** {dq.safety_flagged_items}")
    lines.append("")

    # Safety flags
    lines.append("## Safety Flags")
    lines.append("")
    flags = report.safety_flags
    for field in flags.__dataclass_fields__:
        lines.append(f"- **{field}:** {_serialize_value(getattr(flags, field))}")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Atomic file writers
# ---------------------------------------------------------------------------


def atomic_write_json_remediation_bridge_report(
    report: RemediationBridgeReport,
    path: str | Path | None = None,
) -> Path:
    """Write a JSON bridge report atomically."""
    target = Path(path) if path is not None else DEFAULT_JSON_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(target.suffix + ".tmp")
    text = remediation_bridge_report_to_json(report)
    temp.write_text(text, encoding="utf-8")
    os.replace(temp, target)
    return target


def atomic_write_csv_remediation_bridge_report(
    report: RemediationBridgeReport,
    path: str | Path | None = None,
) -> Path:
    """Write a CSV bridge report atomically."""
    target = Path(path) if path is not None else DEFAULT_CSV_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(target.suffix + ".tmp")
    text = remediation_bridge_report_to_csv_text(report)
    temp.write_text(text, encoding="utf-8")
    os.replace(temp, target)
    return target


def atomic_write_markdown_remediation_bridge_report(
    report: RemediationBridgeReport,
    path: str | Path | None = None,
) -> Path:
    """Write a Markdown bridge report atomically."""
    target = Path(path) if path is not None else DEFAULT_MD_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_suffix(target.suffix + ".tmp")
    text = remediation_bridge_report_to_markdown(report)
    temp.write_text(text, encoding="utf-8")
    os.replace(temp, target)
    return target


def write_remediation_bridge_report(
    report: RemediationBridgeReport,
    json_path: str | Path | None = None,
    csv_path: str | Path | None = None,
    markdown_path: str | Path | None = None,
) -> tuple[Path, Path, Path]:
    """Write JSON, CSV, and Markdown bridge reports atomically."""
    return (
        atomic_write_json_remediation_bridge_report(report, json_path),
        atomic_write_csv_remediation_bridge_report(report, csv_path),
        atomic_write_markdown_remediation_bridge_report(report, markdown_path),
    )
