"""Writer for hunter.human_review_decision_log package. MVP-41 Step 2.

Deterministic JSON, CSV, and Markdown serialization for
HumanReviewDecisionLogReport with atomic writes. Output is a human-audit /
research-only artifact. It is not an approval, certification, production
readiness assessment, deployment readiness assessment, trading readiness
assessment, recommendation, suitability assessment, or signal. It does not
emit action commands, shell commands, code patches, deployment steps,
infrastructure changes, or trading actions. File references, metadata, report
paths, artifact references, queue references, decision references, and link
references are serialized as opaque strings only; they are never opened,
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

from hunter.human_review_decision_log.models import (
    HUMAN_REVIEW_DECISION_LOG_VERSION,
    HumanReviewDecisionLogDataQuality,
    HumanReviewDecisionLogReport,
    HumanReviewDecisionLogSafetyFlags,
    HumanReviewDecisionResult,
)

# Default local artifact paths. These are explicit, local, and never remote.
DEFAULT_JSON_PATH: Path = Path(
    "data/human_review_decision_log/human_review_decision_log.json"
)
DEFAULT_CSV_PATH: Path = Path(
    "data/human_review_decision_log/human_review_decisions.csv"
)
DEFAULT_MD_PATH: Path = Path(
    "reports/human_review_decision_log/human_review_decision_log.md"
)

_DEFAULT_PATH = object()

_SAFETY_NOTICE = (
    "This report is a local, audit-only research artifact. Decision logged is "
    "for human-audit tracking only and does not imply approval, certification, "
    "production readiness, deployment readiness, trading readiness, "
    "recommendation, suitability assessment, signal validity, task assignment, "
    "task completion, or executable remediation plan."
)

_EXPLICIT_DECISION_STATEMENT = (
    "Decision logged is not an approval, certification, production readiness "
    "assessment, deployment readiness assessment, trading readiness assessment, "
    "recommendation, suitability assessment, signal, task assignment, task "
    "completion, or executable remediation plan."
)

_CSV_COLUMNS = (
    "report_id",
    "generated_at",
    "decision_result_id",
    "queue_entry_id",
    "decision_id",
    "decision_state",
    "decision_outcome",
    "decision_validity",
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
    if isinstance(obj, HumanReviewDecisionLogSafetyFlags):
        result["is_safe"] = obj.is_safe
    return result


# ---------------------------------------------------------------------------
# Dict / JSON serialization
# ---------------------------------------------------------------------------


def human_review_decision_log_report_to_dict(
    report: HumanReviewDecisionLogReport,
) -> dict[str, Any]:
    """Convert a HumanReviewDecisionLogReport to a deterministic dictionary.

    The returned dict begins with the safety notice and generated_at, followed
    by the remaining report fields in stable sorted order.
    """
    data: dict[str, Any] = {
        "safety_notice": report.safety_notice or _SAFETY_NOTICE,
        "generated_at": _iso(report.generated_at) if report.generated_at else "",
    }
    report_dict = _dataclass_to_dict(report)
    for key in sorted(report_dict.keys()):
        data[key] = report_dict[key]
    return data


def human_review_decision_log_report_to_json_text(
    report: HumanReviewDecisionLogReport,
) -> str:
    """Serialize a HumanReviewDecisionLogReport to deterministic JSON text."""
    data = human_review_decision_log_report_to_dict(report)
    return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=False) + "\n"


# ---------------------------------------------------------------------------
# CSV serialization
# ---------------------------------------------------------------------------


def _format_reason_codes(codes: tuple[str, ...]) -> str:
    """Format reason codes for CSV using a deterministic join."""
    return "|".join(sorted(str(code) for code in codes))


def _format_decision_ids(decision_ids: tuple[str, ...]) -> str:
    """Format decision_ids for CSV as a deterministic semicolon-joined string."""
    return ";".join(sorted(str(did) for did in decision_ids))


def human_review_decision_log_report_to_csv_text(
    report: HumanReviewDecisionLogReport,
) -> str:
    """Serialize decision results to deterministic CSV rows.

    Each row corresponds to one HumanReviewDecisionResult in
    report.decision_results. The writer reads the report's decision results
    directly and does not recompute engine classification.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(_CSV_COLUMNS)
    generated_at = _iso(report.generated_at) if report.generated_at else ""
    report_id = report.report_id

    sorted_results = sorted(
        report.decision_results,
        key=lambda r: (r.queue_entry_id, r.decision_result_id),
    )
    for result in sorted_results:
        row = [
            report_id,
            generated_at,
            result.decision_result_id,
            result.queue_entry_id,
            _format_decision_ids(result.decision_ids),
            result.decision_state,
            result.decision_outcome,
            result.decision_validity,
            result.severity,
            _format_reason_codes(result.reason_codes),
            result.rationale or "",
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


def human_review_decision_log_report_to_markdown_text(
    report: HumanReviewDecisionLogReport,
) -> str:
    """Serialize a HumanReviewDecisionLogReport to deterministic Markdown text.

    The output contains an immediate audit-only / research-only safety notice,
    an explicit statement that decision logged is not approval or readiness,
    summary, queue entry refs, decision records, links, issues, decision
    results, data quality, safety flags, and reason codes. No shell commands,
    patch instructions, deployment steps, infrastructure changes, executable
    steps, or trading instructions are emitted.
    """
    lines: list[str] = []
    lines.append("# Human Review Decision Log")
    lines.append("")
    lines.append(f"> {_SAFETY_NOTICE}")
    lines.append("")
    lines.append(f"> {_EXPLICIT_DECISION_STATEMENT}")
    lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **version:** {HUMAN_REVIEW_DECISION_LOG_VERSION}")
    lines.append(f"- **report_id:** {report.report_id}")
    lines.append(f"- **state:** {report.state.value}")
    lines.append(
        f"- **generated_at:** {_format_datetime(report.generated_at)}"
    )
    if report.project_version:
        lines.append(f"- **project_version:** {report.project_version}")
    if report.notes:
        lines.append(f"- **notes:** {report.notes}")
    lines.append("")
    lines.append(
        "Decision logged is for human-audit tracking only. It is not an "
        "approval, certification, production readiness assessment, deployment "
        "readiness assessment, trading readiness assessment, recommendation, "
        "suitability assessment, signal, task assignment, task completion, or "
        "executable remediation plan."
    )
    lines.append("")

    # Queue entry refs
    lines.append("## Queue Entry References")
    lines.append("")
    lines.append(
        "| queue_entry_id | source_id | source_kind | record_id | entry_state | "
        "priority | severity | reason_codes | artifact_ref | report_ref |"
    )
    lines.append(
        "|------------------|-----------|-------------|-----------|-------------|"
        "----------|----------|--------------|--------------|------------|"
    )
    sorted_refs = sorted(
        report.queue_entry_refs, key=lambda r: (r.queue_entry_id, r.source_id, r.record_id)
    )
    for ref in sorted_refs:
        lines.append(
            f"| {_md_value(ref.queue_entry_id)} | {_md_value(ref.source_id)} | "
            f"{_md_value(ref.source_kind)} | {_md_value(ref.record_id)} | "
            f"{_md_value(ref.entry_state)} | {_md_value(ref.priority)} | "
            f"{_md_value(ref.severity)} | "
            f"{_md_value(_format_reason_codes_md(ref.reason_codes))} | "
            f"{_md_value(ref.artifact_ref)} | {_md_value(ref.report_ref)} |"
        )
    if not report.queue_entry_refs:
        lines.append("| _none_ | | | | | | | | | |")
    lines.append("")

    # Decision records
    lines.append("## Decision Records")
    lines.append("")
    lines.append(
        "| decision_id | queue_entry_id | reviewer | decided_at | outcome | "
        "rationale | reason_codes | artifact_ref | report_ref |"
    )
    lines.append(
        "|-------------|----------------|----------|------------|--------|"
        "-----------|--------------|--------------|------------|"
    )
    sorted_records = sorted(
        report.decision_records, key=lambda r: (r.decision_id, r.queue_entry_id)
    )
    for record in sorted_records:
        lines.append(
            f"| {_md_value(record.decision_id)} | {_md_value(record.queue_entry_id)} | "
            f"{_md_value(record.reviewer)} | {_md_value(_format_datetime(record.decided_at))} | "
            f"{_md_value(record.outcome)} | {_md_value(record.rationale)} | "
            f"{_md_value(_format_reason_codes_md(record.reason_codes))} | "
            f"{_md_value(record.artifact_ref)} | {_md_value(record.report_ref)} |"
        )
    if not report.decision_records:
        lines.append("| _none_ | | | | | | | | |")
    lines.append("")

    # Links
    lines.append("## Links")
    lines.append("")
    lines.append(
        "| link_id | source_id | target_id | link_type | generated_at |"
    )
    lines.append(
        "|---------|-----------|-----------|-----------|--------------|"
    )
    sorted_links = sorted(
        report.links, key=lambda l: (l.source_id, l.target_id, l.link_type, l.link_id)
    )
    for link in sorted_links:
        lines.append(
            f"| {_md_value(link.link_id)} | {_md_value(link.source_id)} | "
            f"{_md_value(link.target_id)} | {_md_value(link.link_type)} | "
            f"{_md_value(_format_datetime(link.generated_at))} |"
        )
    if not report.links:
        lines.append("| _none_ | | | | |")
    lines.append("")

    # Decision results
    lines.append("## Decision Results")
    lines.append("")
    lines.append(
        "| decision_result_id | queue_entry_id | decision_ids | decision_state | "
        "decision_outcome | decision_validity | severity | reason_codes | rationale |"
    )
    lines.append(
        "|--------------------|----------------|--------------|----------------|"
        "-------------------|-------------------|----------|--------------|-----------|"
    )
    sorted_results = sorted(
        report.decision_results,
        key=lambda r: (r.queue_entry_id, r.decision_result_id),
    )
    for result in sorted_results:
        decision_ids = "; ".join(sorted(result.decision_ids))
        lines.append(
            f"| {_md_value(result.decision_result_id)} | {_md_value(result.queue_entry_id)} | "
            f"{_md_value(decision_ids)} | {_md_value(result.decision_state)} | "
            f"{_md_value(result.decision_outcome)} | {_md_value(result.decision_validity)} | "
            f"{_md_value(result.severity)} | "
            f"{_md_value(_format_reason_codes_md(result.reason_codes))} | "
            f"{_md_value(result.rationale)} |"
        )
    if not report.decision_results:
        lines.append("| _none_ | | | | | | | | |")
    lines.append("")

    # Issues
    lines.append("## Issues")
    lines.append("")
    lines.append(
        "| issue_id | issue_type | severity | reason_codes | source_id | "
        "target_id | decision_id | queue_entry_id | title |"
    )
    lines.append(
        "|----------|------------|----------|--------------|-----------|"
        "-----------|-------------|------------------|-------|"
    )
    sorted_issues = sorted(
        report.issues,
        key=lambda i: (i.severity, i.issue_type, i.source_id, i.title),
    )
    for issue in sorted_issues:
        lines.append(
            f"| {_md_value(issue.issue_id)} | {_md_value(issue.issue_type)} | "
            f"{_md_value(issue.severity)} | "
            f"{_md_value(_format_reason_codes_md(issue.reason_codes))} | "
            f"{_md_value(issue.source_id)} | {_md_value(issue.target_id)} | "
            f"{_md_value(issue.decision_id)} | {_md_value(issue.queue_entry_id)} | "
            f"{_md_value(issue.title)} |"
        )
    if not report.issues:
        lines.append("| _none_ | | | | | | | | |")
    lines.append("")

    # Data quality
    lines.append("## Data Quality")
    lines.append("")
    dq = report.data_quality
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
        "All queue_entry_id, decision_id, link_id, source_id, target_id, "
        "artifact_ref, report_ref, and metadata values are opaque strings. They "
        "are serialized here for human audit only and are never opened, followed, "
        "traversed, validated, fetched, or executed."
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

    # Reviewer attribution is opaque metadata only
    lines.append("## Reviewer Attribution")
    lines.append("")
    lines.append(
        "Reviewer values are caller-provided opaque strings. They are metadata "
        "for the human auditor's convenience and carry no operational, assignment, "
        "routing, or identity-system semantics."
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


def _write_json(
    report: HumanReviewDecisionLogReport, path: str | Path | None
) -> Path:
    """Write JSON artifact atomically."""
    target = _coerce_path(path, DEFAULT_JSON_PATH)
    _atomic_write(target, human_review_decision_log_report_to_json_text(report))
    return target


def _write_csv(
    report: HumanReviewDecisionLogReport, path: str | Path | None
) -> Path:
    """Write CSV artifact atomically."""
    target = _coerce_path(path, DEFAULT_CSV_PATH)
    _atomic_write(target, human_review_decision_log_report_to_csv_text(report))
    return target


def _write_markdown(
    report: HumanReviewDecisionLogReport, path: str | Path | None
) -> Path:
    """Write Markdown artifact atomically."""
    target = _coerce_path(path, DEFAULT_MD_PATH)
    _atomic_write(target, human_review_decision_log_report_to_markdown_text(report) + "\n")
    return target


def write_human_review_decision_log_report(
    report: HumanReviewDecisionLogReport,
    json_path: str | Path | None | object = _DEFAULT_PATH,
    csv_path: str | Path | None | object = _DEFAULT_PATH,
    markdown_path: str | Path | None | object = _DEFAULT_PATH,
) -> tuple[Path | None, Path | None, Path | None]:
    """Write HumanReviewDecisionLogReport to JSON, CSV, and Markdown as requested.

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
        _write_markdown(
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
    "_DEFAULT_PATH",
    "human_review_decision_log_report_to_csv_text",
    "human_review_decision_log_report_to_dict",
    "human_review_decision_log_report_to_json_text",
    "human_review_decision_log_report_to_markdown_text",
    "write_human_review_decision_log_report",
]
