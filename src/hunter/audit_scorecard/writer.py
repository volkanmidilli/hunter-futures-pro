"""Writer for hunter.audit_scorecard package. MVP-35 — Local Research Audit Readiness Scorecard.

Deterministic JSON, CSV, and Markdown serialization for AuditScorecardReport with
atomic writes. Output is a human-audit / research-only artifact. It is not an
approval, certification, production readiness assessment, trading readiness
assessment, recommendation, suitability assessment, or signal. It does not emit
action commands, suggest orders, or create execution instructions. File
references, metadata, and artifact references are serialized as opaque strings
only; they are never opened, traversed, validated, followed, or executed here.
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

from hunter.audit_scorecard.models import (
    AUDIT_SCORECARD_VERSION,
    AuditScorecardDataQuality,
    AuditScorecardDimension,
    AuditScorecardDimensionResult,
    AuditScorecardDimensionState,
    AuditScorecardEvidenceRef,
    AuditScorecardFinding,
    AuditScorecardLink,
    AuditScorecardReasonCode,
    AuditScorecardReport,
    AuditScorecardSafetyFlags,
    AuditScorecardSeverity,
    AuditScorecardState,
)

# Default local artifact paths. These are explicit, local, and never remote.
DEFAULT_JSON_PATH: Path = Path("data/audit_scorecard/audit_scorecard.json")
DEFAULT_CSV_PATH: Path = Path(
    "data/audit_scorecard/audit_scorecard_dimensions.csv"
)
DEFAULT_MD_PATH: Path = Path("reports/audit_scorecard/audit_scorecard.md")

_SAFETY_NOTICE = (
    "This scorecard is a human-audit / research-only artifact. It is not an "
    "approval, certification, production readiness assessment, trading readiness "
    "assessment, recommendation, suitability assessment, or signal. Do not use it "
    "for execution, order placement, or strategy approval. Completeness "
    "percentages are descriptive metrics only and are not approval scores."
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
    if isinstance(obj, AuditScorecardSafetyFlags):
        result["is_safe"] = obj.is_safe
    return result


# ---------------------------------------------------------------------------
# Dict / JSON serialization
# ---------------------------------------------------------------------------


def audit_scorecard_report_to_dict(report: AuditScorecardReport) -> dict[str, Any]:
    """Convert an AuditScorecardReport to a deterministic dictionary.

    The returned dict begins with the safety notice and generated_at, followed
    by the remaining report fields in stable sorted order.
    """
    data: dict[str, Any] = {
        "safety_notice": _SAFETY_NOTICE,
        "generated_at": _iso(report.generated_at),
    }
    report_dict = _dataclass_to_dict(report)
    for key in sorted(report_dict.keys()):
        data[key] = report_dict[key]
    return data


def audit_scorecard_report_to_json_text(report: AuditScorecardReport) -> str:
    """Serialize an AuditScorecardReport to deterministic JSON text."""
    data = audit_scorecard_report_to_dict(report)
    return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=False) + "\n"


# ---------------------------------------------------------------------------
# CSV serialization
# ---------------------------------------------------------------------------


_CSV_COLUMNS = (
    "report_id",
    "generated_at",
    "dimension_id",
    "dimension_state",
    "severity",
    "completeness_percent",
    "evidence_count",
    "finding_count",
    "reason_codes",
    "message",
)


def _report_id(report: AuditScorecardReport) -> str:
    """Return the deterministic report identifier already produced by the engine."""
    return report.report_id


def _format_reason_codes(codes: tuple[str, ...]) -> str:
    """Format reason codes for CSV using a deterministic join."""
    return "|".join(sorted(codes))


def audit_scorecard_report_to_csv_text(report: AuditScorecardReport) -> str:
    """Serialize dimension results to deterministic CSV rows.

    Each row corresponds to one AuditScorecardDimensionResult in
    report.dimension_results. The writer reads the results directly and does not
    recompute classification.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(_CSV_COLUMNS)
    generated_at = _iso(report.generated_at)
    report_id = _report_id(report)

    for result in report.dimension_results:
        row = [
            report_id,
            generated_at,
            result.dimension_id,
            result.dimension_state.value,
            result.severity.value,
            result.completeness_percent,
            result.evidence_count,
            result.finding_count,
            _format_reason_codes(result.reason_codes),
            result.message,
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


def _dimension_manual_review_items(
    report: AuditScorecardReport,
) -> list[AuditScorecardDimensionResult]:
    """Return dimension results that require manual review attention."""
    return [
        r
        for r in report.dimension_results
        if r.dimension_state
        in {
            AuditScorecardDimensionState.MISSING,
            AuditScorecardDimensionState.BLOCKED,
            AuditScorecardDimensionState.DEGRADED,
        }
    ]


def _evidence_manual_review_items(
    report: AuditScorecardReport,
) -> list[AuditScorecardEvidenceRef]:
    """Return evidence refs flagged for manual review."""
    return [ref for ref in report.evidence_refs if ref.requires_manual_review]


def audit_scorecard_report_to_markdown_text(
    report: AuditScorecardReport,
) -> str:
    """Serialize an AuditScorecardReport to deterministic Markdown text.

    The output contains an immediate audit-only / research-only safety notice,
    summary, dimension results, findings, evidence references, links, data
    quality, safety flags, manual review items, reason codes, and notes. No
    trading or execution instructions are emitted.
    """
    lines: list[str] = []
    lines.append("# Local Research Audit Readiness Scorecard")
    lines.append("")
    lines.append(f"> {_SAFETY_NOTICE}")
    lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **version:** {AUDIT_SCORECARD_VERSION}")
    lines.append(f"- **report_id:** {report.report_id}")
    lines.append(f"- **state:** {report.state.value}")
    lines.append(f"- **generated_at:** {_iso(report.generated_at)}")
    if report.project_version:
        lines.append(f"- **project_version:** {report.project_version}")
    dq = report.data_quality
    lines.append(f"- **dimension_count:** {dq.dimension_count}")
    lines.append(f"- **evidence_count:** {dq.evidence_count}")
    lines.append(f"- **finding_count:** {dq.finding_count}")
    lines.append(f"- **link_count:** {dq.link_count}")
    lines.append(f"- **sections_present:** {dq.sections_present}")
    lines.append("")
    lines.append(
        "Completeness percentages are descriptive metrics only and are not "
        "approval, certification, or trading readiness scores."
    )
    lines.append("")

    # Dimension results
    lines.append("## Dimension Results")
    lines.append("")
    lines.append(
        "| dimension_id | dimension_state | severity | completeness_percent | "
        "evidence_count | finding_count | reason_codes | message |"
    )
    lines.append(
        "|--------------|-------------------|----------|----------------------|"
        "----------------|---------------|--------------|---------|"
    )
    for result in report.dimension_results:
        lines.append(
            f"| {_md_value(result.dimension_id)} | {_md_value(result.dimension_state.value)} | "
            f"{_md_value(result.severity.value)} | {_md_value(result.completeness_percent)} | "
            f"{_md_value(result.evidence_count)} | {_md_value(result.finding_count)} | "
            f"{_md_value(_format_reason_codes(result.reason_codes))} | {_md_value(result.message)} |"
        )
    if not report.dimension_results:
        lines.append("| _none_ | | | | | | | |")
    lines.append("")

    # Findings
    lines.append("## Findings")
    lines.append("")
    lines.append(
        "| finding_id | dimension_id | severity | reason_code | message | evidence |"
    )
    lines.append(
        "|------------|--------------|----------|-------------|---------|----------|"
    )
    for finding in report.findings:
        evidence = ", ".join(finding.evidence) if finding.evidence else ""
        lines.append(
            f"| {_md_value(finding.finding_id)} | {_md_value(finding.dimension_id)} | "
            f"{_md_value(finding.severity.value)} | {_md_value(finding.reason_code.value)} | "
            f"{_md_value(finding.message)} | {_md_value(evidence)} |"
        )
    if not report.findings:
        lines.append("| _none_ | | | | | |")
    lines.append("")

    # Evidence references
    lines.append("## Evidence References")
    lines.append("")
    lines.append(
        "| evidence_id | reference | label | message | generated_at | requires_manual_review |"
    )
    lines.append(
        "|-------------|-----------|-------|---------|--------------|------------------------|"
    )
    for ref in report.evidence_refs:
        lines.append(
            f"| {_md_value(ref.evidence_id)} | {_md_value(ref.reference)} | "
            f"{_md_value(ref.label)} | {_md_value(ref.message)} | "
            f"{_md_value(_format_datetime(ref.generated_at))} | {_md_value(ref.requires_manual_review)} |"
        )
    if not report.evidence_refs:
        lines.append("| _none_ | | | | | |")
    lines.append("")

    # Links
    lines.append("## Links")
    lines.append("")
    lines.append(
        "| link_id | source_id | target_id | link_type | label | message |"
    )
    lines.append(
        "|---------|-----------|-----------|-----------|-------|---------|"
    )
    for link in report.links:
        lines.append(
            f"| {_md_value(link.link_id)} | {_md_value(link.source_id)} | "
            f"{_md_value(link.target_id)} | {_md_value(link.link_type.value)} | "
            f"{_md_value(link.label)} | {_md_value(link.message)} |"
        )
    if not report.links:
        lines.append("| _none_ | | | | | |")
    lines.append("")

    # Data quality
    lines.append("## Data Quality")
    lines.append("")
    lines.append(f"- **dimension_count:** {dq.dimension_count}")
    lines.append(f"- **evidence_count:** {dq.evidence_count}")
    lines.append(f"- **finding_count:** {dq.finding_count}")
    lines.append(f"- **link_count:** {dq.link_count}")
    lines.append(f"- **sections_present:** {dq.sections_present}")
    lines.append("- **state_distribution:**")
    for state, count in sorted(dq.state_distribution.items()):
        lines.append(f"  - {state}: {count}")
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

    # Manual review
    lines.append("## Manual Review")
    lines.append("")
    manual_review_dims = _dimension_manual_review_items(report)
    manual_review_evs = _evidence_manual_review_items(report)
    if manual_review_dims or manual_review_evs:
        for result in manual_review_dims:
            lines.append(
                f"- Dimension `{result.dimension_id}` is in state "
                f"`{result.dimension_state.value}` and may require manual review."
            )
        for ref in manual_review_evs:
            lines.append(
                f"- Evidence ref `{ref.evidence_id}` is flagged for manual review."
            )
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


def atomic_write_json_audit_scorecard_report(
    report: AuditScorecardReport,
    path: str | Path | None = None,
) -> Path:
    """Serialize AuditScorecardReport to JSON and write atomically."""
    target = _coerce_path(path, DEFAULT_JSON_PATH)
    _atomic_write(target, audit_scorecard_report_to_json_text(report))
    return target


def atomic_write_csv_audit_scorecard_report(
    report: AuditScorecardReport,
    path: str | Path | None = None,
) -> Path:
    """Serialize AuditScorecardReport dimension results to CSV and write atomically."""
    target = _coerce_path(path, DEFAULT_CSV_PATH)
    _atomic_write(target, audit_scorecard_report_to_csv_text(report))
    return target


def atomic_write_markdown_audit_scorecard_report(
    report: AuditScorecardReport,
    path: str | Path | None = None,
) -> Path:
    """Serialize AuditScorecardReport to Markdown and write atomically."""
    target = _coerce_path(path, DEFAULT_MD_PATH)
    _atomic_write(target, audit_scorecard_report_to_markdown_text(report) + "\n")
    return target


_DEFAULT_PATH = object()


def write_audit_scorecard_report(
    report: AuditScorecardReport,
    json_path: str | Path | None | object = _DEFAULT_PATH,
    csv_path: str | Path | None | object = _DEFAULT_PATH,
    md_path: str | Path | None | object = _DEFAULT_PATH,
) -> tuple[Path | None, Path | None, Path | None]:
    """Write AuditScorecardReport to JSON, CSV, and Markdown as requested.

    Pass None for a format to skip writing that artifact. Default paths are used
    when a path is omitted and the format is written.
    """
    json_out = (
        atomic_write_json_audit_scorecard_report(
            report, None if json_path is _DEFAULT_PATH else json_path
        )
        if json_path is not None
        else None
    )
    csv_out = (
        atomic_write_csv_audit_scorecard_report(
            report, None if csv_path is _DEFAULT_PATH else csv_path
        )
        if csv_path is not None
        else None
    )
    md_out = (
        atomic_write_markdown_audit_scorecard_report(
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
    "atomic_write_csv_audit_scorecard_report",
    "atomic_write_json_audit_scorecard_report",
    "atomic_write_markdown_audit_scorecard_report",
    "audit_scorecard_report_to_csv_text",
    "audit_scorecard_report_to_dict",
    "audit_scorecard_report_to_json_text",
    "audit_scorecard_report_to_markdown_text",
    "write_audit_scorecard_report",
]
