"""Writer for hunter.human_review_queue package. MVP-40 Step 2.

Deterministic JSON, CSV, and Markdown serialization for HumanReviewQueueReport
with atomic writes. Output is a human-audit / research-only artifact. It is not an
approval, certification, production readiness assessment, trading readiness
assessment, recommendation, suitability assessment, or signal. It does not emit
action commands, shell commands, code patches, deployment steps, infrastructure
changes, or trading actions. File references, metadata, report paths, artifact
references, and queue references are serialized as opaque strings only; they are
never opened, traversed, validated, followed, fetched, or executed here.
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

from hunter.human_review_queue.models import (
    HUMAN_REVIEW_QUEUE_VERSION,
    HumanReviewQueueEntry,
    HumanReviewQueueReport,
    HumanReviewQueueSafetyFlags,
)

# Default local artifact paths. These are explicit, local, and never remote.
DEFAULT_JSON_PATH: Path = Path("data/human_review_queue/human_review_queue.json")
DEFAULT_CSV_PATH: Path = Path("data/human_review_queue/human_review_queue.csv")
DEFAULT_MD_PATH: Path = Path("reports/human_review_queue/human_review_queue.md")

_DEFAULT_PATH = object()

_SAFETY_NOTICE = (
    "This report is a local, audit-only research artifact. "
    "Queued-for-review is for human-audit tracking only and does not imply "
    "approval, certification, production readiness, trading readiness, "
    "recommendation, suitability, signal validity, task assignment, or "
    "executable remediation plan."
)

_EXPLICIT_QUEUE_STATEMENT = (
    "Queued-for-review is not an approval, certification, production readiness "
    "assessment, deployment readiness assessment, trading readiness assessment, "
    "recommendation, suitability assessment, signal, task assignment, or "
    "executable remediation plan."
)

_CSV_COLUMNS = (
    "report_id",
    "generated_at",
    "queue_entry_id",
    "source_id",
    "source_kind",
    "record_id",
    "entry_state",
    "priority",
    "decision_hint",
    "severity",
    "reason_codes",
    "message",
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
    if isinstance(obj, HumanReviewQueueSafetyFlags):
        result["is_safe"] = obj.is_safe
    return result


# ---------------------------------------------------------------------------
# Dict / JSON serialization
# ---------------------------------------------------------------------------


def human_review_queue_report_to_dict(report: HumanReviewQueueReport) -> dict[str, Any]:
    """Convert a HumanReviewQueueReport to a deterministic dictionary.

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


def human_review_queue_report_to_json_text(report: HumanReviewQueueReport) -> str:
    """Serialize a HumanReviewQueueReport to deterministic JSON text."""
    data = human_review_queue_report_to_dict(report)
    return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=False) + "\n"


# ---------------------------------------------------------------------------
# CSV serialization
# ---------------------------------------------------------------------------


def _format_reason_codes(codes: tuple[str, ...]) -> str:
    """Format reason codes for CSV using a deterministic join."""
    return "|".join(sorted(str(code) for code in codes))


def _csv_message(entry: HumanReviewQueueEntry) -> str:
    """Derive CSV message from description, then title, then empty string."""
    if entry.description:
        return entry.description
    if entry.title:
        return entry.title
    return ""


def human_review_queue_report_to_csv_text(report: HumanReviewQueueReport) -> str:
    """Serialize queue entries to deterministic CSV rows.

    Each row corresponds to one HumanReviewQueueEntry in report.queue_entries.
    The writer reads the report's queue entries directly and does not recompute
    engine classification.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(_CSV_COLUMNS)
    generated_at = _iso(report.generated_at)
    report_id = report.report_id

    sorted_entries = sorted(
        report.queue_entries,
        key=lambda e: (e.queue_entry_id, e.source_id, e.record_id),
    )
    for entry in sorted_entries:
        row = [
            report_id,
            generated_at,
            entry.queue_entry_id,
            entry.source_id,
            entry.source_kind,
            entry.record_id,
            entry.entry_state,
            entry.priority,
            entry.decision_hint,
            entry.severity,
            _format_reason_codes(entry.reason_codes),
            _csv_message(entry),
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


def _format_reason_codes_md(codes: tuple[str, ...]) -> str:
    """Format reason codes for Markdown using a deterministic join."""
    return ", ".join(sorted(str(code) for code in codes))


def _format_datetime(value: datetime | None) -> str:
    """Format a datetime for Markdown, or return empty string if None."""
    if value is None:
        return ""
    return _iso(value)


def human_review_queue_report_to_markdown_text(report: HumanReviewQueueReport) -> str:
    """Serialize a HumanReviewQueueReport to deterministic Markdown text.

    The output contains an immediate audit-only / research-only safety notice,
    an explicit statement that queued-for-review is not approval or readiness,
    summary, queue entries, source records, issues, data quality, safety flags,
    and reason codes. No shell commands, patch instructions, deployment steps,
    infrastructure changes, executable steps, or trading instructions are emitted.
    """
    lines: list[str] = []
    lines.append("# Local Research Human Review Queue")
    lines.append("")
    lines.append(f"> {_SAFETY_NOTICE}")
    lines.append("")
    lines.append(f"> {_EXPLICIT_QUEUE_STATEMENT}")
    lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **version:** {HUMAN_REVIEW_QUEUE_VERSION}")
    lines.append(f"- **report_id:** {report.report_id}")
    lines.append(f"- **state:** {report.state.value}")
    lines.append(f"- **generated_at:** {_iso(report.generated_at)}")
    if report.project_version:
        lines.append(f"- **project_version:** {report.project_version}")
    dq = report.data_quality
    lines.append(f"- **total_source_records:** {dq.total_source_records}")
    lines.append(f"- **total_queue_entries:** {dq.total_queue_entries}")
    lines.append(f"- **total_issues:** {dq.total_issues}")
    lines.append(f"- **critical_count:** {dq.critical_count}")
    lines.append(f"- **high_count:** {dq.high_count}")
    lines.append(f"- **medium_count:** {dq.medium_count}")
    lines.append(f"- **low_count:** {dq.low_count}")
    lines.append(f"- **duplicate_source_id_count:** {dq.duplicate_source_id_count}")
    lines.append(f"- **duplicate_queue_entry_count:** {dq.duplicate_queue_entry_count}")
    lines.append(f"- **orphan_related_record_count:** {dq.orphan_related_record_count}")
    lines.append(f"- **stale_source_record_count:** {dq.stale_source_record_count}")
    lines.append("")
    lines.append(
        "Queued-for-review is for human-audit tracking only. It is not an "
        "approval, certification, production readiness assessment, deployment "
        "readiness assessment, trading readiness assessment, recommendation, "
        "suitability assessment, signal, task assignment, or executable "
        "remediation plan."
    )
    lines.append("")

    # Queue entries
    lines.append("## Queue Entries")
    lines.append("")
    lines.append(
        "| queue_entry_id | source_id | source_kind | record_id | entry_state | "
        "priority | decision_hint | severity | reason_codes | title |"
    )
    lines.append(
        "|------------------|-----------|-------------|-----------|-------------|"
        "----------|---------------|----------|--------------|-------|"
    )
    sorted_entries = sorted(
        report.queue_entries,
        key=lambda e: (e.queue_entry_id, e.source_id, e.record_id),
    )
    for entry in sorted_entries:
        lines.append(
            f"| {_md_value(entry.queue_entry_id)} | {_md_value(entry.source_id)} | "
            f"{_md_value(entry.source_kind)} | {_md_value(entry.record_id)} | "
            f"{_md_value(entry.entry_state)} | {_md_value(entry.priority)} | "
            f"{_md_value(entry.decision_hint)} | {_md_value(entry.severity)} | "
            f"{_md_value(_format_reason_codes_md(entry.reason_codes))} | "
            f"{_md_value(entry.title)} |"
        )
    if not report.queue_entries:
        lines.append("| _none_ | | | | | | | | | |")
    lines.append("")

    # Source records
    lines.append("## Source Records")
    lines.append("")
    lines.append(
        "| source_id | source_kind | record_id | state | severity | related_record_ids | "
        "artifact_ref | report_ref | title |"
    )
    lines.append(
        "|-----------|-------------|-----------|-------|----------|--------------------|"
        "--------------|------------|-------|"
    )
    sorted_sources = sorted(
        report.source_records,
        key=lambda s: (s.source_id, s.source_kind, s.record_id),
    )
    for source in sorted_sources:
        related = ", ".join(source.related_record_ids)
        lines.append(
            f"| {_md_value(source.source_id)} | {_md_value(source.source_kind)} | "
            f"{_md_value(source.record_id)} | {_md_value(source.state)} | "
            f"{_md_value(source.severity)} | {_md_value(related)} | "
            f"{_md_value(source.artifact_ref)} | {_md_value(source.report_ref)} | "
            f"{_md_value(source.title)} |"
        )
    if not report.source_records:
        lines.append("| _none_ | | | | | | | | | |")
    lines.append("")

    # Issues
    lines.append("## Issues")
    lines.append("")
    lines.append(
        "| issue_id | issue_type | severity | reason_codes | source_id | record_id | title |"
    )
    lines.append(
        "|----------|------------|----------|--------------|-----------|-----------|-------|"
    )
    sorted_issues = sorted(
        report.issues,
        key=lambda i: (i.issue_id, i.issue_type, i.severity),
    )
    for issue in sorted_issues:
        lines.append(
            f"| {_md_value(issue.issue_id)} | {_md_value(issue.issue_type)} | "
            f"{_md_value(issue.severity)} | {_md_value(_format_reason_codes_md(issue.reason_codes))} | "
            f"{_md_value(issue.source_id)} | {_md_value(issue.record_id)} | "
            f"{_md_value(issue.title)} |"
        )
    if not report.issues:
        lines.append("| _none_ | | | | | | |")
    lines.append("")

    # Data quality
    lines.append("## Data Quality")
    lines.append("")
    for attr in sorted(dq.__dataclass_fields__):
        value = getattr(dq, attr)
        lines.append(f"- **{attr}:** {value}")
    if report.metadata:
        lines.append("")
        lines.append("### Metadata")
        lines.append("")
        for key, value in sorted(report.metadata.items()):
            lines.append(f"- **{key}:** {value}")
    lines.append("")

    # Safety flags
    lines.append("## Safety Flags")
    lines.append("")
    lines.append("| Flag | Value |")
    lines.append("|------|-------|")
    for key, value in sorted(_dataclass_to_dict(report.safety_flags).items()):
        lines.append(f"| {_md_value(key)} | {_md_value(value)} |")
    lines.append("")

    # Opaque reference notice
    lines.append("## Opaque Reference Notice")
    lines.append("")
    lines.append(
        "All source_id, record_id, related_record_ids, artifact_ref, report_ref, "
        "and metadata values are opaque strings. They are serialized here for "
        "human audit only and are never opened, followed, traversed, validated, "
        "fetched, or executed."
    )
    lines.append("")

    # No automated remediation execution notice
    lines.append("## No Automated Remediation Execution")
    lines.append("")
    lines.append(
        "This report does not contain or emit shell commands, code patches, deployment "
        "instructions, infrastructure modifications, trading instructions, task "
        "assignment instructions, or any executable remediation actions. It is a "
        "research artifact for human review only."
    )
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


def _write_json(report: HumanReviewQueueReport, path: str | Path | None) -> Path:
    """Write JSON artifact atomically."""
    target = _coerce_path(path, DEFAULT_JSON_PATH)
    _atomic_write(target, human_review_queue_report_to_json_text(report))
    return target


def _write_csv(report: HumanReviewQueueReport, path: str | Path | None) -> Path:
    """Write CSV artifact atomically."""
    target = _coerce_path(path, DEFAULT_CSV_PATH)
    _atomic_write(target, human_review_queue_report_to_csv_text(report))
    return target


def _write_markdown(report: HumanReviewQueueReport, path: str | Path | None) -> Path:
    """Write Markdown artifact atomically."""
    target = _coerce_path(path, DEFAULT_MD_PATH)
    _atomic_write(target, human_review_queue_report_to_markdown_text(report) + "\n")
    return target


def write_human_review_queue_report(
    report: HumanReviewQueueReport,
    json_path: str | Path | None | object = _DEFAULT_PATH,
    csv_path: str | Path | None | object = _DEFAULT_PATH,
    markdown_path: str | Path | None | object = _DEFAULT_PATH,
) -> tuple[Path | None, Path | None, Path | None]:
    """Write HumanReviewQueueReport to JSON, CSV, and Markdown as requested.

    Pass None for a format to skip writing that artifact. Default paths are used
    when a path is omitted and the format is written.
    """
    json_out = (
        _write_json(report, None if json_path is _DEFAULT_PATH else json_path)
        if json_path is not None
        else None
    )
    csv_out = (
        _write_csv(report, None if csv_path is _DEFAULT_PATH else csv_path)
        if csv_path is not None
        else None
    )
    md_out = (
        _write_markdown(report, None if markdown_path is _DEFAULT_PATH else markdown_path)
        if markdown_path is not None
        else None
    )
    return json_out, csv_out, md_out


__all__ = [
    "DEFAULT_CSV_PATH",
    "DEFAULT_JSON_PATH",
    "DEFAULT_MD_PATH",
    "_DEFAULT_PATH",
    "human_review_queue_report_to_csv_text",
    "human_review_queue_report_to_dict",
    "human_review_queue_report_to_json_text",
    "human_review_queue_report_to_markdown_text",
    "write_human_review_queue_report",
]
