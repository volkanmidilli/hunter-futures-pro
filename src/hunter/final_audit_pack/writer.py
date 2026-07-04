"""Writer for hunter.final_audit_pack package. MVP-32 — Local Research Final Audit Pack Export.

Deterministic JSON, CSV, and Markdown serialization for FinalAuditPackReport with
atomic writes. Output is a human-audit / research-only artifact. It is not a
trading signal, not trade approval, not strategy approval, not execution
approval, not portfolio approval, not universe approval, and not a certification
of trading readiness. It does not emit action commands, suggest orders, or create
execution instructions. File references and metadata strings are serialized as
opaque strings only; they are never opened, traversed, validated, followed, or
executed here.
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

from hunter.final_audit_pack.models import (
    FINAL_AUDIT_PACK_VERSION,
    FinalAuditPackArtifact,
    FinalAuditPackCompleteness,
    FinalAuditPackDataQuality,
    FinalAuditPackReport,
    FinalAuditPackSafetyFlags,
    FinalAuditPackSection,
)

# Default local artifact paths. These are explicit, local, and never remote.
DEFAULT_JSON_PATH: Path = Path("data/final_audit_pack/final_audit_pack.json")
DEFAULT_CSV_PATH: Path = Path("data/final_audit_pack/final_audit_pack_sections.csv")
DEFAULT_MD_PATH: Path = Path("reports/final_audit_pack/final_audit_pack.md")

_SAFETY_NOTICE = (
    "This local final audit pack is a human-audit / research-only artifact. "
    "It is not a trading signal, not trade approval, not strategy approval, not execution approval, "
    "not portfolio approval, not universe approval, and not a certification of trading readiness. "
    "It must not be consumed by execution, strategy, Freqtrade, order, exchange, or any runtime path. "
    "No action commands, trading instructions, or order suggestions are emitted. "
    "All sections and artifact references below are opaque strings for human review only."
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
    if isinstance(obj, FinalAuditPackSafetyFlags):
        result["is_safe"] = obj.is_safe
    return result


# ---------------------------------------------------------------------------
# Dict / JSON serialization
# ---------------------------------------------------------------------------


def final_audit_pack_report_to_dict(report: FinalAuditPackReport) -> dict[str, Any]:
    """Convert a FinalAuditPackReport to a deterministic dictionary."""
    return _dataclass_to_dict(report)


def final_audit_pack_report_to_json_text(report: FinalAuditPackReport) -> str:
    """Serialize a FinalAuditPackReport to deterministic JSON text."""
    data = final_audit_pack_report_to_dict(report)
    return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


# ---------------------------------------------------------------------------
# CSV serialization
# ---------------------------------------------------------------------------


_CSV_COLUMNS = (
    "report_id",
    "generated_at",
    "section_id",
    "section_kind",
    "display_name",
    "state",
    "reason_codes",
    "artifact_count",
    "generated_at_section",
    "source_report_id",
    "source_run_id",
)


def final_audit_pack_report_to_csv_text(report: FinalAuditPackReport) -> str:
    """Serialize a FinalAuditPackReport to deterministic CSV text.

    One row per FinalAuditPackSection. Report-level metadata (report_id,
    generated_at, artifact_count) is repeated on each row so the CSV is a
    self-contained denormalized view. Sections do not own artifacts, so the
    artifact_count is the total number of artifacts in the report.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(_CSV_COLUMNS)
    generated_at = _iso(report.generated_at)
    artifact_count = len(report.artifacts)
    for section in report.sections:
        display_name = section.name or section.section_id
        generated_at_section = (
            _iso(section.generated_at) if section.generated_at is not None else ""
        )
        row = [
            report.report_id,
            generated_at,
            section.section_id,
            section.section_kind,
            display_name,
            section.state.value,
            "|".join(section.reason_codes),
            artifact_count,
            generated_at_section,
            section.report_id,
            section.run_id,
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


def final_audit_pack_report_to_markdown_text(report: FinalAuditPackReport) -> str:
    """Serialize a FinalAuditPackReport to deterministic Markdown text.

    The output contains a safety notice at the top, summary, completeness,
    sections table, artifacts, data quality, safety flags, reason codes, and
    notes. No trading or execution instructions are emitted.
    """
    lines: list[str] = []
    lines.append("# Final Audit Pack Report")
    lines.append("")
    lines.append(f"> {_SAFETY_NOTICE}")
    lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **report_id:** {report.report_id}")
    lines.append(f"- **version:** {report.version}")
    lines.append(f"- **generated_at:** {_iso(report.generated_at)}")
    lines.append(f"- **sections:** {len(report.sections)}")
    lines.append(f"- **artifacts:** {len(report.artifacts)}")
    lines.append("")

    # Completeness summary
    c = report.completeness
    lines.append("## Completeness Summary")
    lines.append("")
    lines.append(f"- **required_sections_present:** {c.required_sections_present}")
    lines.append(f"- **required_sections_missing:** {c.required_sections_missing}")
    lines.append(f"- **optional_sections_present:** {c.optional_sections_present}")
    lines.append(f"- **artifact_reference_count:** {c.artifact_reference_count}")
    lines.append(f"- **blocked_section_count:** {c.blocked_section_count}")
    lines.append(f"- **insufficient_section_count:** {c.insufficient_section_count}")
    lines.append(f"- **safety_notice_present:** {c.safety_notice_present}")
    lines.append(f"- **total_sections:** {c.total_sections}")
    lines.append(f"- **sections_expected:** {c.sections_expected}")
    lines.append(f"- **sections_present:** {c.sections_present}")
    if c.notes:
        lines.append("")
        lines.append("### Notes")
        lines.append("")
        for note in c.notes:
            lines.append(f"- {note}")
    lines.append("")

    # Sections table
    lines.append("## Sections")
    lines.append("")
    lines.append(
        "| section_id | section_kind | source_report_id | source_run_id | "
        "display_name | state | reason_codes | generated_at |"
    )
    lines.append(
        "|------------|--------------|------------------|---------------|"
        "--------------|-------|--------------|--------------|"
    )
    for section in report.sections:
        generated_at_section = (
            _iso(section.generated_at) if section.generated_at is not None else ""
        )
        display_name = section.name or section.section_id
        lines.append(
            f"| {_md_value(section.section_id)} | {_md_value(section.section_kind)} | "
            f"{_md_value(section.report_id)} | {_md_value(section.run_id)} | "
            f"{_md_value(display_name)} | {_md_value(section.state.value)} | "
            f"{_md_value('|'.join(section.reason_codes))} | "
            f"{_md_value(generated_at_section)} |"
        )
    if not report.sections:
        lines.append("| _none_ | | | | | | | |")
    lines.append("")

    # Artifacts
    lines.append("## Artifacts")
    lines.append("")
    lines.append("| kind | reference | display_name |")
    lines.append("|------|-----------|--------------|")
    for artifact in report.artifacts:
        lines.append(
            f"| {_md_value(artifact.kind)} | {_md_value(artifact.reference)} | "
            f"{_md_value(artifact.display_name)} |"
        )
    if not report.artifacts:
        lines.append("| _none_ | | |")
    lines.append("")

    # Data quality
    dq = report.data_quality
    lines.append("## Data Quality")
    lines.append("")
    lines.append(f"- **total_inputs:** {dq.total_inputs}")
    lines.append(f"- **normalized_sections:** {dq.normalized_sections}")
    lines.append(f"- **blocked_sections:** {dq.blocked_sections}")
    lines.append(f"- **insufficient_sections:** {dq.insufficient_sections}")
    lines.append(f"- **excluded_sections:** {dq.excluded_sections}")
    lines.append(f"- **included_sections:** {dq.included_sections}")
    lines.append(f"- **sections_present:** {dq.sections_present}")
    lines.append(f"- **sections_expected:** {dq.sections_expected}")
    lines.append(f"- **artifact_references:** {dq.artifact_references}")
    if dq.notes:
        lines.append("")
        lines.append("### Notes")
        lines.append("")
        for note in dq.notes:
            lines.append(f"- {note}")
    lines.append("")

    # Safety flags
    lines.append("## Safety Flags")
    lines.append("")
    lines.append("| Flag | Value |")
    lines.append("|------|-------|")
    for key, value in sorted(_dataclass_to_dict(report.safety_flags).items()):
        lines.append(f"| {_md_value(key)} | {_md_value(value)} |")
    lines.append("")

    # Reason codes
    if report.reason_codes:
        lines.append("## Reason Codes")
        lines.append("")
        for code in report.reason_codes:
            lines.append(f"- {code}")
        lines.append("")

    # Metadata
    if report.metadata:
        lines.append("## Metadata")
        lines.append("")
        for key, value in sorted(report.metadata.items()):
            lines.append(f"- **{_md_value(key)}:** {_md_value(value)}")
        lines.append("")

    # Notes
    if report.notes:
        lines.append("## Notes")
        lines.append("")
        for note in report.notes:
            lines.append(f"- {note}")
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


def atomic_write_json_final_audit_pack_report(
    report: FinalAuditPackReport,
    path: str | Path | None = None,
) -> Path:
    """Serialize FinalAuditPackReport to JSON and write atomically."""
    target = _coerce_path(path, DEFAULT_JSON_PATH)
    _atomic_write(target, final_audit_pack_report_to_json_text(report))
    return target


def atomic_write_csv_final_audit_pack_report(
    report: FinalAuditPackReport,
    path: str | Path | None = None,
) -> Path:
    """Serialize FinalAuditPackReport sections to CSV and write atomically."""
    target = _coerce_path(path, DEFAULT_CSV_PATH)
    _atomic_write(target, final_audit_pack_report_to_csv_text(report))
    return target


def atomic_write_markdown_final_audit_pack_report(
    report: FinalAuditPackReport,
    path: str | Path | None = None,
) -> Path:
    """Serialize FinalAuditPackReport to Markdown and write atomically."""
    target = _coerce_path(path, DEFAULT_MD_PATH)
    _atomic_write(target, final_audit_pack_report_to_markdown_text(report) + "\n")
    return target


_DEFAULT_PATH = object()


def write_final_audit_pack_report(
    report: FinalAuditPackReport,
    json_path: str | Path | None | object = _DEFAULT_PATH,
    csv_path: str | Path | None | object = _DEFAULT_PATH,
    md_path: str | Path | None | object = _DEFAULT_PATH,
) -> tuple[Path | None, Path | None, Path | None]:
    """Write FinalAuditPackReport to JSON, CSV, and Markdown as requested.

    Pass None for a format to skip writing that artifact. Default paths are used
    when a path is omitted and the format is written.
    """
    json_out = (
        atomic_write_json_final_audit_pack_report(
            report, None if json_path is _DEFAULT_PATH else json_path
        )
        if json_path is not None
        else None
    )
    csv_out = (
        atomic_write_csv_final_audit_pack_report(
            report, None if csv_path is _DEFAULT_PATH else csv_path
        )
        if csv_path is not None
        else None
    )
    md_out = (
        atomic_write_markdown_final_audit_pack_report(
            report, None if md_path is _DEFAULT_PATH else md_path
        )
        if md_path is not None
        else None
    )
    return json_out, csv_out, md_out


__all__ = [
    "DEFAULT_CSV_PATH",
    "DEFAULT_JSON_PATH",
    "DEFAULT_MD_PATH",
    "atomic_write_csv_final_audit_pack_report",
    "atomic_write_json_final_audit_pack_report",
    "atomic_write_markdown_final_audit_pack_report",
    "final_audit_pack_report_to_csv_text",
    "final_audit_pack_report_to_dict",
    "final_audit_pack_report_to_json_text",
    "final_audit_pack_report_to_markdown_text",
    "write_final_audit_pack_report",
]
