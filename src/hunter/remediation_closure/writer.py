"""Writer for hunter.remediation_closure package. MVP-39 Step 2.

Deterministic JSON, CSV, and Markdown serialization for RemediationClosureReport
with atomic writes. Output is a human-audit / research-only artifact. It is not an
approval, certification, production readiness assessment, trading readiness
assessment, recommendation, suitability assessment, or signal. It does not emit
action commands, shell commands, code patches, deployment steps, infrastructure
changes, or trading actions. File references, metadata, report paths, artifact
references, closure references, evidence references, and backlog references are
serialized as opaque strings only; they are never opened, traversed, validated,
followed, fetched, or executed here.
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

from hunter.remediation_closure.models import (
    REMEDIATION_CLOSURE_VERSION,
    RemediationClosureBacklogItemRef,
    RemediationClosureConfig,
    RemediationClosureDataQuality,
    RemediationClosureDeclaration,
    RemediationClosureEvidenceSummary,
    RemediationClosureInput,
    RemediationClosureIssue,
    RemediationClosureLink,
    RemediationClosureReasonCode,
    RemediationClosureRecordState,
    RemediationClosureReport,
    RemediationClosureResult,
    RemediationClosureReviewRecord,
    RemediationClosureSafetyFlags,
    RemediationClosureSeverity,
    RemediationClosureState,
)

# Default local artifact paths. These are explicit, local, and never remote.
DEFAULT_JSON_PATH: Path = Path("data/remediation_closure/remediation_closure.json")
DEFAULT_CSV_PATH: Path = Path(
    "data/remediation_closure/remediation_closure_records.csv"
)
DEFAULT_MD_PATH: Path = Path("reports/remediation_closure/remediation_closure.md")

_SAFETY_NOTICE = (
    "This report is a local, audit-only research artifact. Closure recorded is "
    "for human-audit tracking only and does not imply approval, certification, "
    "production readiness, trading readiness, recommendation, suitability, or "
    "signal validity."
)

_EXPLICIT_CLOSURE_STATEMENT = (
    "Closure recorded is not an approval, certification, production readiness "
    "assessment, deployment readiness assessment, trading readiness assessment, "
    "recommendation, suitability assessment, signal, or executable remediation plan."
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
    if isinstance(obj, RemediationClosureSafetyFlags):
        result["is_safe"] = obj.is_safe
    return result


# ---------------------------------------------------------------------------
# Dict / JSON serialization
# ---------------------------------------------------------------------------


def remediation_closure_report_to_dict(
    report: RemediationClosureReport,
) -> dict[str, Any]:
    """Convert a RemediationClosureReport to a deterministic dictionary.

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


def remediation_closure_report_to_json_text(
    report: RemediationClosureReport,
) -> str:
    """Serialize a RemediationClosureReport to deterministic JSON text."""
    data = remediation_closure_report_to_dict(report)
    return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=False) + "\n"


# ---------------------------------------------------------------------------
# CSV serialization
# ---------------------------------------------------------------------------

_CSV_COLUMNS = (
    "report_id",
    "generated_at",
    "closure_result_id",
    "backlog_item_id",
    "closure_id",
    "record_state",
    "eligibility_state",
    "review_outcome",
    "severity",
    "reason_codes",
    "message",
)


def _format_reason_codes(codes: tuple[str, ...]) -> str:
    """Format reason codes for CSV using a deterministic join."""
    return "|".join(sorted(str(code) for code in codes))


def remediation_closure_report_to_csv_text(
    report: RemediationClosureReport,
) -> str:
    """Serialize closure results to deterministic CSV rows.

    Each row corresponds to one RemediationClosureResult in
    report.closure_results. The writer reads the report's closure results and
    issues directly and does not recompute engine classification.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(_CSV_COLUMNS)
    generated_at = _iso(report.generated_at)
    report_id = report.report_id

    sorted_results = sorted(
        report.closure_results,
        key=lambda r: (r.closure_result_id, r.backlog_item_id),
    )
    for result in sorted_results:
        row = [
            report_id,
            generated_at,
            result.closure_result_id,
            result.backlog_item_id,
            result.closure_id,
            result.record_state.value,
            result.eligibility_state.value,
            result.review_outcome.value,
            result.severity.value,
            _format_reason_codes(result.reason_codes),
            result.description or result.title,
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


def _format_reason_codes_md(codes: tuple[str, ...]) -> str:
    """Format reason codes for Markdown using a deterministic join."""
    return ", ".join(sorted(str(code) for code in codes))


def _manual_review_items(report: RemediationClosureReport) -> list[str]:
    """Return human-readable notes for items that may require manual review."""
    lines: list[str] = []
    for decl in report.closure_declarations:
        lines.append(
            f"- Closure `{decl.closure_id}` for backlog item `{decl.backlog_item_id}` "
            f"is declared by `{decl.declared_by or 'unknown'}` and may require manual review."
        )
    for issue in report.issues:
        if issue.severity in {
            RemediationClosureSeverity.BLOCKING,
            RemediationClosureSeverity.ADVISORY,
        }:
            identifier = (
                issue.backlog_item_id
                or issue.closure_id
                or issue.evidence_summary_id
                or issue.review_id
                or issue.link_id
                or issue.issue_id
            )
            lines.append(
                f"- Issue `{identifier}` ({issue.issue_type.value}): "
                f"{issue.description or issue.title}"
            )
    for result in report.closure_results:
        if result.record_state not in {
            RemediationClosureRecordState.CLOSED_RECORDED,
            RemediationClosureRecordState.NOT_APPLICABLE,
        }:
            lines.append(
                f"- Backlog item `{result.backlog_item_id}` closure record is "
                f"`{result.record_state.value}` and may require manual review."
            )
    return lines


def remediation_closure_report_to_markdown_text(
    report: RemediationClosureReport,
) -> str:
    """Serialize a RemediationClosureReport to deterministic Markdown text.

    The output contains an immediate audit-only / research-only safety notice,
    an explicit statement that closure recorded is not approval or readiness,
    summary, backlog item closure results, evidence summaries, closure
    declarations, review records, links, issues, data quality, safety flags, and
    manual review notes. No shell commands, patch instructions, deployment
    steps, infrastructure changes, executable steps, or trading instructions are
    emitted.
    """
    lines: list[str] = []
    lines.append("# Remediation Closure Register")
    lines.append("")
    lines.append(f"> {report.safety_notice or _SAFETY_NOTICE}")
    lines.append("")
    lines.append(f"> {_EXPLICIT_CLOSURE_STATEMENT}")
    lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **version:** {REMEDIATION_CLOSURE_VERSION}")
    lines.append(f"- **report_id:** {report.report_id}")
    lines.append(f"- **state:** {report.state.value}")
    lines.append(f"- **generated_at:** {_iso(report.generated_at)}")
    if report.project_version:
        lines.append(f"- **project_version:** {report.project_version}")
    dq = report.data_quality
    lines.append(f"- **total_backlog_item_refs:** {dq.total_backlog_item_refs}")
    lines.append(f"- **total_evidence_summaries:** {dq.total_evidence_summaries}")
    lines.append(f"- **total_closure_declarations:** {dq.total_closure_declarations}")
    lines.append(f"- **total_review_records:** {dq.total_review_records}")
    lines.append(f"- **total_links:** {dq.total_links}")
    lines.append(f"- **total_issues:** {dq.total_issues}")
    lines.append(f"- **total_closure_results:** {dq.total_closure_results}")
    lines.append("")
    lines.append(
        "Closure recorded is for human-audit tracking only. It is not an "
        "approval, certification, production readiness assessment, deployment "
        "readiness assessment, trading readiness assessment, recommendation, "
        "suitability assessment, signal, or executable remediation plan."
    )
    lines.append("")

    # Closure results
    lines.append("## Closure Results")
    lines.append("")
    lines.append(
        "| closure_result_id | backlog_item_id | closure_id | record_state | "
        "eligibility_state | review_outcome | severity | reason_codes | title |"
    )
    lines.append(
        "|-------------------|-----------------|------------|--------------|"
        "-------------------|--------------|----------|--------------|-------|"
    )
    sorted_results = sorted(
        report.closure_results, key=lambda c: (c.closure_result_id, c.backlog_item_id)
    )
    for result in sorted_results:
        lines.append(
            f"| {_md_value(result.closure_result_id)} | {_md_value(result.backlog_item_id)} | "
            f"{_md_value(result.closure_id)} | {_md_value(result.record_state.value)} | "
            f"{_md_value(result.eligibility_state.value)} | {_md_value(result.review_outcome.value)} | "
            f"{_md_value(result.severity.value)} | {_md_value(_format_reason_codes_md(result.reason_codes))} | "
            f"{_md_value(result.title)} |"
        )
    if not report.closure_results:
        lines.append("| _none_ | | | | | | | | |")
    lines.append("")

    # Evidence summaries
    lines.append("## Evidence Summaries")
    lines.append("")
    lines.append(
        "| evidence_summary_id | backlog_item_id | coverage_state | evidence_ids | review_ids |"
    )
    lines.append(
        "|---------------------|-----------------|----------------|--------------|------------|"
    )
    sorted_evidence = sorted(
        report.evidence_summaries,
        key=lambda s: (s.evidence_summary_id, s.backlog_item_id),
    )
    for summary in sorted_evidence:
        evidence_ids = ", ".join(summary.evidence_ids)
        review_ids = ", ".join(summary.review_ids)
        lines.append(
            f"| {_md_value(summary.evidence_summary_id)} | {_md_value(summary.backlog_item_id)} | "
            f"{_md_value(summary.coverage_state)} | {_md_value(evidence_ids)} | {_md_value(review_ids)} |"
        )
    if not report.evidence_summaries:
        lines.append("| _none_ | | | | |")
    lines.append("")

    # Closure declarations
    lines.append("## Closure Declarations")
    lines.append("")
    lines.append(
        "| closure_id | backlog_item_id | evidence_summary_id | declared_by | reviewed_by | "
        "closed_at | evidence_link |"
    )
    lines.append(
        "|------------|-----------------|---------------------|-------------|-------------|"
        "-----------|---------------|"
    )
    sorted_declarations = sorted(
        report.closure_declarations, key=lambda d: (d.closure_id, d.backlog_item_id)
    )
    for decl in sorted_declarations:
        lines.append(
            f"| {_md_value(decl.closure_id)} | {_md_value(decl.backlog_item_id)} | "
            f"{_md_value(decl.evidence_summary_id)} | {_md_value(decl.declared_by)} | "
            f"{_md_value(decl.reviewed_by)} | {_md_value(_format_datetime(decl.closed_at))} | "
            f"{_md_value(decl.evidence_link)} |"
        )
    if not report.closure_declarations:
        lines.append("| _none_ | | | | | | | |")
    lines.append("")

    # Review records
    lines.append("## Review Records")
    lines.append("")
    lines.append(
        "| review_id | closure_id | outcome | reviewer | reviewed_at | generated_at | note |"
    )
    lines.append(
        "|-----------|------------|---------|----------|-------------|--------------|------|"
    )
    sorted_reviews = sorted(
        report.review_records, key=lambda r: (r.review_id, r.closure_id)
    )
    for review in sorted_reviews:
        lines.append(
            f"| {_md_value(review.review_id)} | {_md_value(review.closure_id)} | "
            f"{_md_value(review.outcome)} | {_md_value(review.reviewer)} | "
            f"{_md_value(_format_datetime(review.reviewed_at))} | "
            f"{_md_value(_format_datetime(review.generated_at))} | {_md_value(review.note)} |"
        )
    if not report.review_records:
        lines.append("| _none_ | | | | | | |")
    lines.append("")

    # Links
    lines.append("## Links")
    lines.append("")
    lines.append(
        "| link_id | closure_id | evidence_summary_id | backlog_item_id | link_type |"
    )
    lines.append(
        "|---------|------------|---------------------|-----------------|-----------|"
    )
    sorted_links = sorted(
        report.links, key=lambda l: (l.link_id, l.closure_id, l.evidence_summary_id, l.backlog_item_id)
    )
    for link in sorted_links:
        lines.append(
            f"| {_md_value(link.link_id)} | {_md_value(link.closure_id)} | "
            f"{_md_value(link.evidence_summary_id)} | {_md_value(link.backlog_item_id)} | "
            f"{_md_value(link.link_type)} |"
        )
    if not report.links:
        lines.append("| _none_ | | | | |")
    lines.append("")

    # Issues
    lines.append("## Issues")
    lines.append("")
    lines.append(
        "| issue_id | issue_type | severity | reason_codes | backlog_item_id | "
        "closure_id | evidence_summary_id | review_id | link_id | title |"
    )
    lines.append(
        "|----------|------------|----------|--------------|---------------|"
        "------------|---------------------|-----------|---------|-------|"
    )
    sorted_issues = sorted(
        report.issues, key=lambda i: (i.issue_id, i.issue_type.value, i.severity.value)
    )
    for issue in sorted_issues:
        lines.append(
            f"| {_md_value(issue.issue_id)} | {_md_value(issue.issue_type.value)} | "
            f"{_md_value(issue.severity.value)} | {_md_value(_format_reason_codes_md(issue.reason_codes))} | "
            f"{_md_value(issue.backlog_item_id)} | {_md_value(issue.closure_id)} | "
            f"{_md_value(issue.evidence_summary_id)} | {_md_value(issue.review_id)} | "
            f"{_md_value(issue.link_id)} | {_md_value(issue.title)} |"
        )
    if not report.issues:
        lines.append("| _none_ | | | | | | | | | |")
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

    # Opaque reference notice
    lines.append("## Opaque Reference Notice")
    lines.append("")
    lines.append(
        "All backlog_item_id, evidence_summary_id, closure_id, review_id, link_id, "
        "source_id, finding_id, evidence_link, artifact paths, report paths, and metadata "
        "values are opaque strings. They are serialized here for human audit only and are "
        "never opened, followed, traversed, validated, fetched, or executed."
    )
    lines.append("")

    # No automated remediation execution notice
    lines.append("## No Automated Remediation Execution")
    lines.append("")
    lines.append(
        "This report does not contain or emit shell commands, code patches, deployment "
        "instructions, infrastructure modifications, trading instructions, or any executable "
        "remediation actions. It is a research artifact for human review only."
    )
    lines.append("")

    # Manual review
    lines.append("## Manual Review Notes")
    lines.append("")
    manual_items = _manual_review_items(report)
    if manual_items:
        lines.extend(manual_items)
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


def atomic_write_json_remediation_closure_report(
    report: RemediationClosureReport,
    path: str | Path | None = None,
) -> Path:
    """Serialize RemediationClosureReport to JSON and write atomically."""
    target = _coerce_path(path, DEFAULT_JSON_PATH)
    _atomic_write(target, remediation_closure_report_to_json_text(report))
    return target


def atomic_write_csv_remediation_closure_report(
    report: RemediationClosureReport,
    path: str | Path | None = None,
) -> Path:
    """Serialize RemediationClosureReport closure results to CSV and write atomically."""
    target = _coerce_path(path, DEFAULT_CSV_PATH)
    _atomic_write(target, remediation_closure_report_to_csv_text(report))
    return target


def atomic_write_markdown_remediation_closure_report(
    report: RemediationClosureReport,
    path: str | Path | None = None,
) -> Path:
    """Serialize RemediationClosureReport to Markdown and write atomically."""
    target = _coerce_path(path, DEFAULT_MD_PATH)
    _atomic_write(target, remediation_closure_report_to_markdown_text(report) + "\n")
    return target


_DEFAULT_PATH = object()


def write_remediation_closure_report(
    report: RemediationClosureReport,
    json_path: str | Path | None | object = _DEFAULT_PATH,
    csv_path: str | Path | None | object = _DEFAULT_PATH,
    markdown_path: str | Path | None | object = _DEFAULT_PATH,
) -> tuple[Path | None, Path | None, Path | None]:
    """Write RemediationClosureReport to JSON, CSV, and Markdown as requested.

    Pass None for a format to skip writing that artifact. Default paths are used
    when a path is omitted and the format is written.
    """
    json_out = (
        atomic_write_json_remediation_closure_report(
            report, None if json_path is _DEFAULT_PATH else json_path
        )
        if json_path is not None
        else None
    )
    csv_out = (
        atomic_write_csv_remediation_closure_report(
            report, None if csv_path is _DEFAULT_PATH else csv_path
        )
        if csv_path is not None
        else None
    )
    md_out = (
        atomic_write_markdown_remediation_closure_report(
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
    "atomic_write_csv_remediation_closure_report",
    "atomic_write_json_remediation_closure_report",
    "atomic_write_markdown_remediation_closure_report",
    "remediation_closure_report_to_csv_text",
    "remediation_closure_report_to_dict",
    "remediation_closure_report_to_json_text",
    "remediation_closure_report_to_markdown_text",
    "write_remediation_closure_report",
]
