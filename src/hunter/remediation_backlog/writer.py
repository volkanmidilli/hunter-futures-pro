"""Writer for hunter.remediation_backlog package. MVP-37 Step 2.

Deterministic JSON, CSV, and Markdown serialization for RemediationBacklogReport
with atomic writes. Output is a human-audit / research-only artifact. It is not an
approval, certification, production readiness assessment, trading readiness
assessment, recommendation, suitability assessment, or signal. It does not emit
action commands, shell commands, code patches, deployment steps, or trading
actions. File references, metadata, report paths, artifact references, and
finding references are serialized as opaque strings only; they are never opened,
traversed, validated, followed, fetched, or executed here.
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

from hunter.remediation_backlog.models import (
    REMEDIATION_BACKLOG_VERSION,
    RemediationAcknowledgement,
    RemediationBacklogDataQuality,
    RemediationBacklogInput,
    RemediationBacklogItem,
    RemediationBacklogReasonCode,
    RemediationBacklogReport,
    RemediationBacklogSafetyFlags,
    RemediationDependency,
    RemediationFindingRef,
    RemediationSourceRef,
)

# Default local artifact paths. These are explicit, local, and never remote.
DEFAULT_JSON_PATH: Path = Path("data/remediation_backlog/remediation_backlog.json")
DEFAULT_CSV_PATH: Path = Path(
    "data/remediation_backlog/remediation_backlog_items.csv"
)
DEFAULT_MD_PATH: Path = Path("reports/remediation_backlog/remediation_backlog.md")

_SAFETY_NOTICE = (
    "This remediation backlog is a human-audit / research-only artifact. It is not "
    "an approval, certification, production readiness assessment, trading readiness "
    "assessment, recommendation, suitability assessment, signal, or executable "
    "remediation plan. It does not emit shell commands, code patches, deployment "
    "steps, or trading actions. All references are opaque identifiers and are "
    "never opened, followed, traversed, validated, fetched, or executed."
)

_PRIORITY_NOTICE = (
    "Priority values are for human-review ordering only. They are not "
    "implementation instructions, deployment instructions, or execution "
    "schedules."
)


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
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return _iso(value)
    if isinstance(value, (tuple, list)):
        return [_serialize_value(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return sorted(_serialize_value(v) for v in value)
    if isinstance(value, (MappingProxyType, Mapping)):
        return {str(k): _serialize_value(v) for k, v in sorted(value.items())}
    if is_dataclass(value) and not isinstance(value, type):
        return _dataclass_to_dict(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _dataclass_to_dict(obj: Any) -> dict[str, Any]:
    """Convert a frozen dataclass to a deterministic JSON-safe dict."""
    if not is_dataclass(obj) or isinstance(obj, type):
        raise TypeError(f"expected dataclass instance, got {type(obj)}")
    result: dict[str, Any] = {}
    for field in obj.__dataclass_fields__:
        value = getattr(obj, field)
        result[field] = _serialize_value(value)
    if isinstance(obj, RemediationBacklogSafetyFlags):
        result["is_safe"] = obj.is_safe
    return result


# ---------------------------------------------------------------------------
# Dict / JSON serialization
# ---------------------------------------------------------------------------


def remediation_backlog_report_to_dict(
    report: RemediationBacklogReport,
) -> dict[str, Any]:
    """Convert a RemediationBacklogReport to a deterministic dictionary.

    The returned dict begins with the safety notice and generated_at, followed
    by the remaining report fields in stable sorted order.
    """
    data: dict[str, Any] = {
        "safety_notice": report.safety_notice or _SAFETY_NOTICE,
        "generated_at": _iso(report.generated_at),
    }
    report_dict = _dataclass_to_dict(report)
    for key in sorted(report_dict.keys()):
        data[key] = report_dict[key]
    return data


def remediation_backlog_report_to_json_text(
    report: RemediationBacklogReport,
) -> str:
    """Serialize a RemediationBacklogReport to deterministic JSON text."""
    data = remediation_backlog_report_to_dict(report)
    return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=False) + "\n"


# ---------------------------------------------------------------------------
# CSV serialization
# ---------------------------------------------------------------------------


_CSV_COLUMNS = (
    "report_id",
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
    "message",
)


def _format_reason_codes(codes: tuple[RemediationBacklogReasonCode, ...]) -> str:
    """Format reason codes for CSV using a deterministic semicolon join."""
    return ";".join(sorted(code.value for code in codes))


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
        priority_order.get(item.priority.value, 4),
        severity_order.get(item.severity.value, 2),
        item.item_id or "",
        item.source_id or "",
        item.finding_id or "",
    )


def remediation_backlog_report_to_csv_text(
    report: RemediationBacklogReport,
) -> str:
    """Serialize backlog items to deterministic CSV rows.

    Each row corresponds to one RemediationBacklogItem in report.backlog_items.
    The writer reads the items directly and does not recompute IDs or
    classification. Items are sorted deterministically by priority, severity,
    item_id, source_id, and finding_id.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(_CSV_COLUMNS)
    generated_at = _iso(report.generated_at)
    report_id = report.report_id

    sorted_items = sorted(report.backlog_items, key=_csv_sort_key)
    for item in sorted_items:
        row = [
            report_id,
            generated_at,
            item.item_id or "",
            item.source_id or "",
            item.finding_id or "",
            item.item_type.value,
            item.item_state.value,
            item.severity.value,
            item.priority.value,
            item.owner or "",
            item.reviewer or "",
            _format_reason_codes(item.reason_codes),
            item.description or item.title,
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


def _format_datetime(value: datetime | None) -> str:
    """Format a datetime for Markdown, or return empty string if None."""
    if value is None:
        return ""
    return _iso(value)


def _format_reason_codes_md(
    codes: tuple[RemediationBacklogReasonCode, ...],
) -> str:
    """Format reason codes for Markdown using a deterministic join."""
    return ", ".join(sorted(code.value for code in codes))


def _manual_review_items(
    report: RemediationBacklogReport,
) -> list[tuple[str, str, str]]:
    """Return backlog items flagged for manual review attention.

    Each tuple is (item_id, item_type, message).
    """
    items: list[tuple[str, str, str]] = []
    for item in report.backlog_items:
        if item.item_type.value in {
            "missing_manual_review",
            "conflicting_state",
            "manual_review",
        }:
            items.append((
                item.item_id or "",
                item.item_type.value,
                item.description or item.title or "Item may require manual review.",
            ))
    return items


def remediation_backlog_report_to_markdown_text(
    report: RemediationBacklogReport,
) -> str:
    """Serialize a RemediationBacklogReport to deterministic Markdown text.

    The output contains an immediate audit-only / research-only safety notice,
    summary, backlog items by priority, source refs, finding refs, dependencies,
    acknowledgements, data quality, safety flags, manual review items, and reason
    codes. No shell commands, patch instructions, deployment steps, or trading
    actions are emitted.
    """
    lines: list[str] = []
    lines.append("# Local Research Remediation Backlog")
    lines.append("")
    lines.append(f"> {report.safety_notice or _SAFETY_NOTICE}")
    lines.append("")
    lines.append(f"> {_PRIORITY_NOTICE}")
    lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **version:** {REMEDIATION_BACKLOG_VERSION}")
    lines.append(f"- **report_id:** {report.report_id}")
    lines.append(f"- **state:** {report.state.value}")
    lines.append(f"- **generated_at:** {_iso(report.generated_at)}")
    if report.project_version:
        lines.append(f"- **project_version:** {report.project_version}")
    dq = report.data_quality
    lines.append(f"- **total_sources:** {dq.total_sources}")
    lines.append(f"- **total_findings:** {dq.total_findings}")
    lines.append(f"- **total_backlog_items:** {dq.total_backlog_items}")
    lines.append(f"- **total_dependencies:** {dq.total_dependencies}")
    lines.append(f"- **total_acknowledgements:** {dq.total_acknowledgements}")
    lines.append(f"- **total_issues:** {dq.total_issues}")
    lines.append("")
    lines.append(
        "Backlog findings are descriptive observations for human review only. "
        "They are not approval, certification, or trading readiness scores."
    )
    lines.append("")

    # Backlog items by priority
    lines.append("## Backlog Items by Priority")
    lines.append("")
    lines.append(
        "| item_id | priority | severity | item_type | item_state | source_id | "
        "finding_id | owner | reviewer | reason_codes | message |"
    )
    lines.append(
        "|---------|----------|----------|-----------|------------|-----------|"
        "------------|-------|----------|--------------|---------|"
    )
    sorted_items = sorted(report.backlog_items, key=_csv_sort_key)
    for item in sorted_items:
        lines.append(
            f"| {_md_value(item.item_id)} | {_md_value(item.priority.value)} | "
            f"{_md_value(item.severity.value)} | {_md_value(item.item_type.value)} | "
            f"{_md_value(item.item_state.value)} | {_md_value(item.source_id)} | "
            f"{_md_value(item.finding_id)} | {_md_value(item.owner)} | "
            f"{_md_value(item.reviewer)} | {_md_value(_format_reason_codes_md(item.reason_codes))} | "
            f"{_md_value(item.description or item.title)} |"
        )
    if not report.backlog_items:
        lines.append("| _none_ | | | | | | | | | | |")
    lines.append("")

    # Source refs
    lines.append("## Source Refs")
    lines.append("")
    lines.append(
        "| source_id | source_type | reference | label | generated_at |"
    )
    lines.append(
        "|-----------|-------------|-----------|-------|--------------|"
    )
    sorted_sources = sorted(
        report.source_refs, key=lambda s: (s.source_id or "", s.source_type or "")
    )
    for ref in sorted_sources:
        lines.append(
            f"| {_md_value(ref.source_id)} | {_md_value(ref.source_type)} | "
            f"{_md_value(ref.reference)} | {_md_value(ref.label)} | "
            f"{_md_value(_format_datetime(ref.generated_at))} |"
        )
    if not report.source_refs:
        lines.append("| _none_ | | | | |")
    lines.append("")

    # Finding refs
    lines.append("## Finding Refs")
    lines.append("")
    lines.append(
        "| finding_id | source_id | reference | label | generated_at |"
    )
    lines.append(
        "|------------|-----------|-----------|-------|--------------|"
    )
    sorted_findings = sorted(
        report.finding_refs, key=lambda f: (f.finding_id or "", f.source_id or "")
    )
    for ref in sorted_findings:
        lines.append(
            f"| {_md_value(ref.finding_id)} | {_md_value(ref.source_id)} | "
            f"{_md_value(ref.reference)} | {_md_value(ref.label)} | "
            f"{_md_value(_format_datetime(ref.generated_at))} |"
        )
    if not report.finding_refs:
        lines.append("| _none_ | | | | |")
    lines.append("")

    # Dependencies
    lines.append("## Dependencies")
    lines.append("")
    lines.append(
        "| dependency_id | source_item_id | target_item_id | dependency_type | generated_at |"
    )
    lines.append(
        "|---------------|------------------|------------------|-----------------|--------------|"
    )
    sorted_deps = sorted(
        report.dependencies,
        key=lambda d: (d.dependency_id or "", d.source_item_id or "", d.target_item_id or ""),
    )
    for dep in sorted_deps:
        lines.append(
            f"| {_md_value(dep.dependency_id)} | {_md_value(dep.source_item_id)} | "
            f"{_md_value(dep.target_item_id)} | {_md_value(dep.dependency_type.value)} | "
            f"{_md_value(_format_datetime(dep.generated_at))} |"
        )
    if not report.dependencies:
        lines.append("| _none_ | | | | |")
    lines.append("")

    # Acknowledgements
    lines.append("## Acknowledgements")
    lines.append("")
    lines.append(
        "| acknowledgement_id | item_id | acknowledged_by | acknowledged_at | note |"
    )
    lines.append(
        "|--------------------|---------|-----------------|-------------------|------|"
    )
    sorted_acks = sorted(
        report.acknowledgements, key=lambda a: (a.acknowledgement_id or "", a.item_id or "")
    )
    for ack in sorted_acks:
        lines.append(
            f"| {_md_value(ack.acknowledgement_id)} | {_md_value(ack.item_id)} | "
            f"{_md_value(ack.acknowledged_by)} | {_md_value(_format_datetime(ack.acknowledged_at))} | "
            f"{_md_value(ack.note)} |"
        )
    if not report.acknowledgements:
        lines.append("| _none_ | | | | |")
    lines.append("")

    # Data quality
    lines.append("## Data Quality")
    lines.append("")
    lines.append(f"- **total_sources:** {dq.total_sources}")
    lines.append(f"- **total_findings:** {dq.total_findings}")
    lines.append(f"- **total_backlog_items:** {dq.total_backlog_items}")
    lines.append(f"- **total_dependencies:** {dq.total_dependencies}")
    lines.append(f"- **total_acknowledgements:** {dq.total_acknowledgements}")
    lines.append(f"- **total_issues:** {dq.total_issues}")
    lines.append(f"- **duplicate_id_count:** {dq.duplicate_id_count}")
    lines.append(f"- **duplicate_item_count:** {dq.duplicate_item_count}")
    lines.append(f"- **orphan_finding_count:** {dq.orphan_finding_count}")
    lines.append(f"- **orphan_dependency_count:** {dq.orphan_dependency_count}")
    lines.append(f"- **cycle_count:** {dq.cycle_count}")
    lines.append(f"- **conflicting_item_count:** {dq.conflicting_item_count}")
    lines.append(f"- **stale_source_count:** {dq.stale_source_count}")
    lines.append(f"- **stale_finding_count:** {dq.stale_finding_count}")
    lines.append(f"- **missing_owner_count:** {dq.missing_owner_count}")
    lines.append(f"- **missing_reviewer_count:** {dq.missing_reviewer_count}")
    lines.append(f"- **missing_manual_review_count:** {dq.missing_manual_review_count}")
    lines.append(f"- **unsafe_content_count:** {dq.unsafe_content_count}")
    lines.append(f"- **forbidden_term_count:** {dq.forbidden_term_count}")
    lines.append(f"- **sections_present:** {dq.sections_present}")
    if report.metadata:
        lines.append("")
        lines.append("### Metadata")
        lines.append("")
        for key, value in sorted(report.metadata.items()):
            lines.append(f"- **{key}:** {value}")
    if report.notes:
        lines.append("")
        lines.append("### Notes")
        lines.append("")
        lines.append(report.notes)
    lines.append("")

    # Safety flags
    lines.append("## Safety Flags")
    lines.append("")
    lines.append("| Flag | Value |")
    lines.append("|------|-------|")
    for key, value in sorted(_dataclass_to_dict(report.safety_flags).items()):
        lines.append(f"| {_md_value(key)} | {_md_value(value)} |")
    lines.append("")

    # Manual review
    lines.append("## Manual Review Notes")
    lines.append("")
    manual_items = _manual_review_items(report)
    if manual_items:
        for item_id, item_type, message in manual_items:
            lines.append(f"- `{item_id}` ({item_type}): {message}")
    else:
        lines.append("No manual review items flagged.")
    lines.append("")

    # Reason codes
    if report.reason_codes:
        lines.append("## Reason Codes")
        lines.append("")
        for code in report.reason_codes:
            lines.append(f"- {code.value}")
        lines.append("")

    # Notes
    if report.notes:
        lines.append("## Notes")
        lines.append("")
        lines.append(report.notes)
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Atomic file writes
# ---------------------------------------------------------------------------


def _coerce_path(value: str | Path | None, default: Path) -> Path:
    """Return a Path for the given value, falling back to the default."""
    if value is None:
        return default
    if isinstance(value, Path):
        return value
    return Path(value)


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


def atomic_write_json_remediation_backlog_report(
    report: RemediationBacklogReport,
    path: str | Path | None = None,
) -> Path:
    """Serialize RemediationBacklogReport to JSON and write atomically."""
    target = _coerce_path(path, DEFAULT_JSON_PATH)
    _atomic_write(target, remediation_backlog_report_to_json_text(report))
    return target


def atomic_write_csv_remediation_backlog_report(
    report: RemediationBacklogReport,
    path: str | Path | None = None,
) -> Path:
    """Serialize RemediationBacklogReport items to CSV and write atomically."""
    target = _coerce_path(path, DEFAULT_CSV_PATH)
    _atomic_write(target, remediation_backlog_report_to_csv_text(report))
    return target


def atomic_write_markdown_remediation_backlog_report(
    report: RemediationBacklogReport,
    path: str | Path | None = None,
) -> Path:
    """Serialize RemediationBacklogReport to Markdown and write atomically."""
    target = _coerce_path(path, DEFAULT_MD_PATH)
    _atomic_write(
        target, remediation_backlog_report_to_markdown_text(report) + "\n"
    )
    return target


_DEFAULT_PATH = object()


def write_remediation_backlog_report(
    report: RemediationBacklogReport,
    json_path: str | Path | None | object = _DEFAULT_PATH,
    csv_path: str | Path | None | object = _DEFAULT_PATH,
    markdown_path: str | Path | None | object = _DEFAULT_PATH,
) -> tuple[Path | None, Path | None, Path | None]:
    """Write RemediationBacklogReport to JSON, CSV, and Markdown as requested.

    Pass None for a format to skip writing that artifact. Default paths are used
    when a path is omitted and the format is written.
    """
    json_out = (
        atomic_write_json_remediation_backlog_report(
            report, None if json_path is _DEFAULT_PATH else json_path
        )
        if json_path is not None
        else None
    )
    csv_out = (
        atomic_write_csv_remediation_backlog_report(
            report, None if csv_path is _DEFAULT_PATH else csv_path
        )
        if csv_path is not None
        else None
    )
    md_out = (
        atomic_write_markdown_remediation_backlog_report(
            report, None if markdown_path is _DEFAULT_PATH else markdown_path
        )
        if markdown_path is not None
        else None
    )
    return json_out, csv_out, md_out


__all__ = [
    "DEFAULT_CSV_PATH",
    "DEFAULT_JSON_PATH",
    "DEFAULT_MD_PATH",
    "atomic_write_csv_remediation_backlog_report",
    "atomic_write_json_remediation_backlog_report",
    "atomic_write_markdown_remediation_backlog_report",
    "remediation_backlog_report_to_csv_text",
    "remediation_backlog_report_to_dict",
    "remediation_backlog_report_to_json_text",
    "remediation_backlog_report_to_markdown_text",
    "write_remediation_backlog_report",
]
