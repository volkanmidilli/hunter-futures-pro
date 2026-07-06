"""Writer for hunter.remediation_evidence package. MVP-38 Step 2.

Deterministic JSON, CSV, and Markdown serialization for RemediationEvidenceReport
with atomic writes. Output is a human-audit / research-only artifact. It is not an
approval, certification, production readiness assessment, trading readiness
assessment, recommendation, suitability assessment, or signal. It does not emit
action commands, shell commands, code patches, deployment steps, infrastructure
changes, or trading actions. File references, metadata, report paths, artifact
references, evidence references, and backlog references are serialized as opaque
strings only; they are never opened, traversed, validated, followed, fetched, or
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

from hunter.remediation_evidence.models import (
    REMEDIATION_EVIDENCE_VERSION,
    RemediationBacklogItemRef,
    RemediationEvidenceConfig,
    RemediationEvidenceCoverageResult,
    RemediationEvidenceCoverageState,
    RemediationEvidenceDataQuality,
    RemediationEvidenceInput,
    RemediationEvidenceIssue,
    RemediationEvidenceLink,
    RemediationEvidenceReasonCode,
    RemediationEvidenceRecord,
    RemediationEvidenceRecordState,
    RemediationEvidenceReport,
    RemediationReviewRecord,
    RemediationEvidenceSafetyFlags,
    RemediationEvidenceSeverity,
    RemediationEvidenceState,
)

# Default local artifact paths. These are explicit, local, and never remote.
DEFAULT_JSON_PATH: Path = Path("data/remediation_evidence/remediation_evidence.json")
DEFAULT_CSV_PATH: Path = Path(
    "data/remediation_evidence/remediation_evidence_records.csv"
)
DEFAULT_MD_PATH: Path = Path("reports/remediation_evidence/remediation_evidence.md")

_SAFETY_NOTICE = (
    "This report is a local, audit-only research artifact. Evidence coverage is "
    "for human-audit tracking only and does not imply approval, certification, "
    "production readiness, trading readiness, recommendation, suitability, or "
    "signal validity."
)

_EXPLICIT_COVERAGE_STATEMENT = (
    "Evidence coverage is not an approval, certification, production readiness "
    "assessment, trading readiness assessment, recommendation, suitability "
    "assessment, signal, or executable remediation plan."
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
    if isinstance(obj, RemediationEvidenceSafetyFlags):
        result["is_safe"] = obj.is_safe
    return result


# ---------------------------------------------------------------------------
# Dict / JSON serialization
# ---------------------------------------------------------------------------


def remediation_evidence_report_to_dict(
    report: RemediationEvidenceReport,
) -> dict[str, Any]:
    """Convert a RemediationEvidenceReport to a deterministic dictionary.

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


def remediation_evidence_report_to_json_text(
    report: RemediationEvidenceReport,
) -> str:
    """Serialize a RemediationEvidenceReport to deterministic JSON text."""
    data = remediation_evidence_report_to_dict(report)
    return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=False) + "\n"


# ---------------------------------------------------------------------------
# CSV serialization
# ---------------------------------------------------------------------------


_CSV_COLUMNS = (
    "report_id",
    "generated_at",
    "evidence_id",
    "backlog_item_id",
    "evidence_state",
    "coverage_state",
    "review_outcome",
    "severity",
    "reason_codes",
    "message",
)


def _format_reason_codes(codes: tuple[str, ...]) -> str:
    """Format reason codes for CSV using a deterministic join."""
    return "|".join(sorted(str(code) for code in codes))


def _coverage_map(
    report: RemediationEvidenceReport,
) -> dict[str, RemediationEvidenceCoverageResult]:
    """Map each evidence_id to the first coverage result that contains it.

    Coverage results are taken directly from the report without recomputation.
    """
    mapping: dict[str, RemediationEvidenceCoverageResult] = {}
    sorted_results = sorted(
        report.coverage_results, key=lambda c: (c.coverage_id, c.backlog_item_id)
    )
    for result in sorted_results:
        for evidence_id in result.evidence_ids:
            if evidence_id not in mapping:
                mapping[evidence_id] = result
    return mapping


def _review_outcome_for_evidence(
    evidence_id: str,
    review_records: tuple[RemediationReviewRecord, ...],
) -> str:
    """Return a deterministic review outcome string for the evidence record."""
    outcomes = sorted({rev.outcome.value for rev in review_records if rev.evidence_id == evidence_id})
    return "|".join(outcomes)


def _reason_codes_for_evidence(
    evidence_id: str,
    backlog_item_id: str,
    coverage_result: RemediationEvidenceCoverageResult | None,
    issues: tuple[RemediationEvidenceIssue, ...],
) -> str:
    """Collect reason codes from the coverage result and related issues."""
    codes: set[str] = set()
    if coverage_result is not None:
        codes.update(coverage_result.reason_codes)
    for issue in issues:
        if issue.evidence_id == evidence_id or issue.backlog_item_id == backlog_item_id:
            codes.update(issue.reason_codes)
    return _format_reason_codes(tuple(codes))


def _csv_sort_key(
    record: RemediationEvidenceRecord,
    coverage_map: dict[str, RemediationEvidenceCoverageResult],
) -> tuple[str, str, str, str]:
    """Return a deterministic sort key for CSV evidence rows."""
    coverage = coverage_map.get(record.evidence_id)
    coverage_state = coverage.coverage_state.value if coverage else ""
    severity = coverage.severity.value if coverage else "info"
    return (record.evidence_id, record.backlog_item_id, coverage_state, severity)


def remediation_evidence_report_to_csv_text(
    report: RemediationEvidenceReport,
) -> str:
    """Serialize evidence records to deterministic CSV rows.

    Each row corresponds to one RemediationEvidenceRecord in
    report.evidence_records. The writer reads the report's coverage results and
    issues directly and does not recompute engine classification.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(_CSV_COLUMNS)
    generated_at = _iso(report.generated_at)
    report_id = report.report_id
    coverage_map = _coverage_map(report)

    sorted_records = sorted(
        report.evidence_records,
        key=lambda r: _csv_sort_key(r, coverage_map),
    )
    for record in sorted_records:
        coverage = coverage_map.get(record.evidence_id)
        row = [
            report_id,
            generated_at,
            record.evidence_id,
            record.backlog_item_id,
            record.evidence_state.value,
            coverage.coverage_state.value if coverage else "",
            _review_outcome_for_evidence(record.evidence_id, report.review_records),
            coverage.severity.value if coverage else "info",
            _reason_codes_for_evidence(
                record.evidence_id,
                record.backlog_item_id,
                coverage,
                report.issues,
            ),
            record.description or record.title,
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


def _manual_review_items(
    report: RemediationEvidenceReport,
) -> list[str]:
    """Return human-readable notes for items that may require manual review."""
    lines: list[str] = []
    for record in report.evidence_records:
        if record.evidence_state is not RemediationEvidenceRecordState.ACCEPTED:
            lines.append(
                f"- Evidence `{record.evidence_id}` is in state "
                f"`{record.evidence_state.value}` and may require manual review."
            )
    for issue in report.issues:
        if issue.severity in {
            RemediationEvidenceSeverity.BLOCKING,
            RemediationEvidenceSeverity.ADVISORY,
        }:
            identifier = (
                issue.evidence_id
                or issue.backlog_item_id
                or issue.review_id
                or issue.link_id
                or issue.issue_id
            )
            lines.append(
                f"- Issue `{identifier}` ({issue.issue_type.value}): "
                f"{issue.description or issue.title}"
            )
    for result in report.coverage_results:
        if result.coverage_state not in {
            RemediationEvidenceCoverageState.COVERED,
            RemediationEvidenceCoverageState.NOT_APPLICABLE,
        }:
            lines.append(
                f"- Backlog item `{result.backlog_item_id}` coverage is "
                f"`{result.coverage_state.value}` and may require manual review."
            )
    return lines


def remediation_evidence_report_to_markdown_text(
    report: RemediationEvidenceReport,
) -> str:
    """Serialize a RemediationEvidenceReport to deterministic Markdown text.

    The output contains an immediate audit-only / research-only safety notice,
    an explicit statement that evidence coverage is not approval or readiness,
    summary, backlog item coverage results, evidence records, review records,
    links, issues, data quality, safety flags, and manual review notes. No shell
    commands, patch instructions, deployment steps, infrastructure changes,
    executable steps, or trading instructions are emitted.
    """
    lines: list[str] = []
    lines.append("# Local Research Remediation Evidence Tracker Report")
    lines.append("")
    lines.append(f"> {report.safety_notice or _SAFETY_NOTICE}")
    lines.append("")
    lines.append(f"> {_EXPLICIT_COVERAGE_STATEMENT}")
    lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **version:** {REMEDIATION_EVIDENCE_VERSION}")
    lines.append(f"- **report_id:** {report.report_id}")
    lines.append(f"- **state:** {report.state.value}")
    lines.append(f"- **generated_at:** {_iso(report.generated_at)}")
    if report.project_version:
        lines.append(f"- **project_version:** {report.project_version}")
    dq = report.data_quality
    lines.append(f"- **total_backlog_item_refs:** {dq.total_backlog_item_refs}")
    lines.append(f"- **total_evidence_records:** {dq.total_evidence_records}")
    lines.append(f"- **total_review_records:** {dq.total_review_records}")
    lines.append(f"- **total_links:** {dq.total_links}")
    lines.append(f"- **total_issues:** {dq.total_issues}")
    lines.append(f"- **total_coverage_results:** {dq.total_coverage_results}")
    lines.append("")
    lines.append(
        "Evidence coverage is for human-audit tracking only. It is not an "
        "approval, certification, production readiness assessment, trading "
        "readiness assessment, recommendation, suitability assessment, or "
        "signal."
    )
    lines.append("")

    # Coverage results
    lines.append("## Coverage Results")
    lines.append("")
    lines.append(
        "| coverage_id | backlog_item_id | coverage_state | severity | "
        "evidence_ids | review_ids | reason_codes | title |"
    )
    lines.append(
        "|-------------|-------------------|----------------|----------|"
        "---------------|--------------|--------------|-------|"
    )
    sorted_coverage = sorted(
        report.coverage_results, key=lambda c: (c.coverage_id, c.backlog_item_id)
    )
    for result in sorted_coverage:
        evidence_ids = ", ".join(result.evidence_ids)
        review_ids = ", ".join(result.review_ids)
        lines.append(
            f"| {_md_value(result.coverage_id)} | {_md_value(result.backlog_item_id)} | "
            f"{_md_value(result.coverage_state.value)} | {_md_value(result.severity.value)} | "
            f"{_md_value(evidence_ids)} | {_md_value(review_ids)} | "
            f"{_md_value(_format_reason_codes_md(result.reason_codes))} | {_md_value(result.title)} |"
        )
    if not report.coverage_results:
        lines.append("| _none_ | | | | | | | |")
    lines.append("")

    # Evidence records
    lines.append("## Evidence Records")
    lines.append("")
    lines.append(
        "| evidence_id | backlog_item_id | evidence_state | generated_at | title | description |"
    )
    lines.append(
        "|-------------|-------------------|------------------|--------------|-------|-------------|"
    )
    sorted_evidence = sorted(
        report.evidence_records, key=lambda r: (r.evidence_id, r.backlog_item_id)
    )
    for record in sorted_evidence:
        lines.append(
            f"| {_md_value(record.evidence_id)} | {_md_value(record.backlog_item_id)} | "
            f"{_md_value(record.evidence_state.value)} | {_md_value(_format_datetime(record.generated_at))} | "
            f"{_md_value(record.title)} | {_md_value(record.description)} |"
        )
    if not report.evidence_records:
        lines.append("| _none_ | | | | | |")
    lines.append("")

    # Review records
    lines.append("## Review Records")
    lines.append("")
    lines.append(
        "| review_id | evidence_id | outcome | reviewer | reviewed_at | generated_at | note |"
    )
    lines.append(
        "|-----------|-------------|---------|----------|-------------|--------------|------|"
    )
    sorted_reviews = sorted(
        report.review_records, key=lambda r: (r.review_id, r.evidence_id)
    )
    for review in sorted_reviews:
        lines.append(
            f"| {_md_value(review.review_id)} | {_md_value(review.evidence_id)} | "
            f"{_md_value(review.outcome.value)} | {_md_value(review.reviewer)} | "
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
        "| link_id | evidence_id | backlog_item_id | link_type | generated_at |"
    )
    lines.append(
        "|---------|-------------|-------------------|-----------|--------------|"
    )
    sorted_links = sorted(
        report.links, key=lambda l: (l.link_id, l.evidence_id, l.backlog_item_id)
    )
    for link in sorted_links:
        lines.append(
            f"| {_md_value(link.link_id)} | {_md_value(link.evidence_id)} | "
            f"{_md_value(link.backlog_item_id)} | {_md_value(link.link_type.value)} | "
            f"{_md_value(_format_datetime(link.generated_at))} |"
        )
    if not report.links:
        lines.append("| _none_ | | | | |")
    lines.append("")

    # Issues
    lines.append("## Issues")
    lines.append("")
    lines.append(
        "| issue_id | issue_type | severity | reason_codes | evidence_id | "
        "backlog_item_id | review_id | link_id | title |"
    )
    lines.append(
        "|----------|------------|----------|--------------|-------------|"
        "-------------------|-----------|---------|-------|"
    )
    sorted_issues = sorted(
        report.issues, key=lambda i: (i.issue_id, i.issue_type.value, i.severity.value)
    )
    for issue in sorted_issues:
        lines.append(
            f"| {_md_value(issue.issue_id)} | {_md_value(issue.issue_type.value)} | "
            f"{_md_value(issue.severity.value)} | {_md_value(_format_reason_codes_md(issue.reason_codes))} | "
            f"{_md_value(issue.evidence_id)} | {_md_value(issue.backlog_item_id)} | "
            f"{_md_value(issue.review_id)} | {_md_value(issue.link_id)} | {_md_value(issue.title)} |"
        )
    if not report.issues:
        lines.append("| _none_ | | | | | | | | |")
    lines.append("")

    # Data quality
    lines.append("## Data Quality")
    lines.append("")
    lines.append(f"- **total_backlog_item_refs:** {dq.total_backlog_item_refs}")
    lines.append(f"- **total_evidence_records:** {dq.total_evidence_records}")
    lines.append(f"- **total_review_records:** {dq.total_review_records}")
    lines.append(f"- **total_links:** {dq.total_links}")
    lines.append(f"- **total_issues:** {dq.total_issues}")
    lines.append(f"- **total_coverage_results:** {dq.total_coverage_results}")
    lines.append(f"- **duplicate_id_count:** {dq.duplicate_id_count}")
    lines.append(f"- **duplicate_evidence_count:** {dq.duplicate_evidence_count}")
    lines.append(f"- **orphan_evidence_count:** {dq.orphan_evidence_count}")
    lines.append(f"- **orphan_review_count:** {dq.orphan_review_count}")
    lines.append(f"- **orphan_link_count:** {dq.orphan_link_count}")
    lines.append(f"- **conflicting_review_count:** {dq.conflicting_review_count}")
    lines.append(f"- **stale_evidence_count:** {dq.stale_evidence_count}")
    lines.append(f"- **stale_review_count:** {dq.stale_review_count}")
    lines.append(f"- **missing_evidence_count:** {dq.missing_evidence_count}")
    lines.append(f"- **missing_review_count:** {dq.missing_review_count}")
    lines.append(f"- **rejected_evidence_count:** {dq.rejected_evidence_count}")
    lines.append(f"- **pending_review_evidence_count:** {dq.pending_review_evidence_count}")
    lines.append(f"- **blocked_backlog_item_count:** {dq.blocked_backlog_item_count}")
    lines.append(f"- **open_backlog_item_count:** {dq.open_backlog_item_count}")
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


def atomic_write_json_remediation_evidence_report(
    report: RemediationEvidenceReport,
    path: str | Path | None = None,
) -> Path:
    """Serialize RemediationEvidenceReport to JSON and write atomically."""
    target = _coerce_path(path, DEFAULT_JSON_PATH)
    _atomic_write(target, remediation_evidence_report_to_json_text(report))
    return target


def atomic_write_csv_remediation_evidence_report(
    report: RemediationEvidenceReport,
    path: str | Path | None = None,
) -> Path:
    """Serialize RemediationEvidenceReport evidence records to CSV and write atomically."""
    target = _coerce_path(path, DEFAULT_CSV_PATH)
    _atomic_write(target, remediation_evidence_report_to_csv_text(report))
    return target


def atomic_write_markdown_remediation_evidence_report(
    report: RemediationEvidenceReport,
    path: str | Path | None = None,
) -> Path:
    """Serialize RemediationEvidenceReport to Markdown and write atomically."""
    target = _coerce_path(path, DEFAULT_MD_PATH)
    _atomic_write(target, remediation_evidence_report_to_markdown_text(report) + "\n")
    return target


_DEFAULT_PATH = object()


def write_remediation_evidence_report(
    report: RemediationEvidenceReport,
    json_path: str | Path | None | object = _DEFAULT_PATH,
    csv_path: str | Path | None | object = _DEFAULT_PATH,
    markdown_path: str | Path | None | object = _DEFAULT_PATH,
) -> tuple[Path | None, Path | None, Path | None]:
    """Write RemediationEvidenceReport to JSON, CSV, and Markdown as requested.

    Pass None for a format to skip writing that artifact. Default paths are used
    when a path is omitted and the format is written.
    """
    json_out = (
        atomic_write_json_remediation_evidence_report(
            report, None if json_path is _DEFAULT_PATH else json_path
        )
        if json_path is not None
        else None
    )
    csv_out = (
        atomic_write_csv_remediation_evidence_report(
            report, None if csv_path is _DEFAULT_PATH else csv_path
        )
        if csv_path is not None
        else None
    )
    md_out = (
        atomic_write_markdown_remediation_evidence_report(
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
    "atomic_write_csv_remediation_evidence_report",
    "atomic_write_json_remediation_evidence_report",
    "atomic_write_markdown_remediation_evidence_report",
    "remediation_evidence_report_to_csv_text",
    "remediation_evidence_report_to_dict",
    "remediation_evidence_report_to_json_text",
    "remediation_evidence_report_to_markdown_text",
    "write_remediation_evidence_report",
]
