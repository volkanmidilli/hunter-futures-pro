"""Writer for hunter.human_review_decision_log_consistency package. MVP-42 Step 2.

Deterministic JSON and Markdown serialization for
HumanReviewDecisionLogConsistencyReport. Output is a human-audit / research-only
artifact. It is not an approval, certification, production readiness assessment,
deployment readiness assessment, trading readiness assessment, recommendation,
suitability assessment, or signal. It does not emit action commands, shell
commands, code patches, deployment steps, infrastructure changes, or trading
actions. File references, metadata, report paths, artifact references, queue
references, decision references, and link references are serialized as opaque
strings only; they are never opened, traversed, validated, followed, fetched,
or executed here.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import is_dataclass
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any

from hunter.human_review_decision_log_consistency.models import (
    HUMAN_REVIEW_DECISION_LOG_CONSISTENCY_VERSION,
    HumanReviewDecisionLogConsistencyReport,
    HumanReviewDecisionLogConsistencySafetyFlags,
    SAFETY_NOTICE,
)

_EXPLICIT_CONSISTENCY_STATEMENT = (
    "Cross-artifact consistency checks are for human-audit review only and do "
    "not imply approval, certification, production readiness, deployment readiness, "
    "trading readiness, recommendation, suitability assessment, signal validity, "
    "or any executable plan."
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
    if isinstance(obj, HumanReviewDecisionLogConsistencySafetyFlags):
        result["is_safe"] = obj.is_safe
    return result


# ---------------------------------------------------------------------------
# Dict / JSON serialization
# ---------------------------------------------------------------------------


def human_review_decision_log_consistency_report_to_dict(
    report: HumanReviewDecisionLogConsistencyReport,
) -> dict[str, Any]:
    """Convert a HumanReviewDecisionLogConsistencyReport to a deterministic dictionary.

    The returned dict begins with the safety notice and generated_at, followed
    by the remaining report fields in stable sorted order.
    """
    data: dict[str, Any] = {
        "safety_notice": report.safety_notice or SAFETY_NOTICE,
        "generated_at": _iso(report.generated_at) if report.generated_at else "",
    }
    report_dict = _dataclass_to_dict(report)
    for key in sorted(report_dict.keys()):
        data[key] = report_dict[key]
    return data


def human_review_decision_log_consistency_report_to_json_text(
    report: HumanReviewDecisionLogConsistencyReport,
) -> str:
    """Serialize a HumanReviewDecisionLogConsistencyReport to deterministic JSON text."""
    data = human_review_decision_log_consistency_report_to_dict(report)
    return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=False) + "\n"


# ---------------------------------------------------------------------------
# Markdown serialization
# ---------------------------------------------------------------------------


def _md_value(value: Any) -> str:
    """Stringify a value for Markdown, escaping pipe characters."""
    if value is None:
        return ""
    return str(value).replace("|", "\\|")


def _format_datetime(value: datetime | None) -> str:
    """Format a datetime for Markdown, or return empty string if None."""
    if value is None:
        return ""
    return _iso(value)


def _format_reason_codes(codes: tuple[str, ...]) -> str:
    """Format reason codes for Markdown using a deterministic join."""
    return ", ".join(sorted(str(code) for code in codes))


def human_review_decision_log_consistency_report_to_markdown_text(
    report: HumanReviewDecisionLogConsistencyReport,
) -> str:
    """Serialize a HumanReviewDecisionLogConsistencyReport to deterministic Markdown text.

    The output contains an immediate audit-only / research-only safety notice,
    an explicit statement that consistency checks are not approval or readiness,
    summary, cross-references, issues, data quality, safety flags, reason codes,
    opaque reference notice, and notes. No shell commands, patch instructions,
    deployment steps, infrastructure changes, executable steps, or trading
    instructions are emitted.
    """
    lines: list[str] = []
    lines.append("# Human Review Decision Log Cross-Artifact Consistency")
    lines.append("")
    lines.append(f"> {SAFETY_NOTICE}")
    lines.append("")
    lines.append(f"> {_EXPLICIT_CONSISTENCY_STATEMENT}")
    lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **version:** {HUMAN_REVIEW_DECISION_LOG_CONSISTENCY_VERSION}")
    lines.append(f"- **report_id:** {report.report_id}")
    lines.append(f"- **state:** {report.state.value}")
    lines.append(
        f"- **generated_at:** {_format_datetime(report.generated_at)}"
    )
    lines.append(f"- **project_version:** {report.project_version}")
    lines.append(f"- **queue_report_id:** {report.queue_report_id}")
    lines.append(f"- **decision_log_report_id:** {report.decision_log_report_id}")
    if report.notes:
        lines.append(f"- **notes:** {report.notes}")
    lines.append("")
    lines.append(
        "Cross-artifact consistency checks are for human-audit review only. They are not an "
        "approval, certification, production readiness assessment, deployment readiness assessment, "
        "trading readiness assessment, recommendation, suitability assessment, signal, or "
        "executable plan."
    )
    lines.append("")

    # Cross References
    lines.append("## Cross References")
    lines.append("")
    lines.append(
        "| cross_reference_id | queue_entry_id | decision_log_queue_entry_id | "
        "queue_entry_state | decision_log_result_state | match_status | severity | "
        "reason_codes | rationale |"
    )
    lines.append(
        "|--------------------|----------------|-----------------------------|"
        "-------------------|----------------------------|--------------|----------|"
        "--------------|-----------|"
    )
    sorted_cross_refs = sorted(
        report.cross_references,
        key=lambda cr: (
            cr.queue_entry_id,
            cr.decision_log_queue_entry_id,
            cr.match_status,
            cr.cross_reference_id,
        ),
    )
    for cr in sorted_cross_refs:
        lines.append(
            f"| {_md_value(cr.cross_reference_id)} | {_md_value(cr.queue_entry_id)} | "
            f"{_md_value(cr.decision_log_queue_entry_id)} | {_md_value(cr.queue_entry_state)} | "
            f"{_md_value(cr.decision_log_result_state)} | {_md_value(cr.match_status)} | "
            f"{_md_value(cr.severity)} | {_md_value(_format_reason_codes(cr.reason_codes))} | "
            f"{_md_value(cr.rationale)} |"
        )
    if not report.cross_references:
        lines.append("| _none_ | | | | | | | | |")
    lines.append("")

    # Issues
    lines.append("## Issues")
    lines.append("")
    lines.append(
        "| issue_id | issue_type | severity | reason_codes | source_id | target_id | "
        "queue_entry_id | decision_log_queue_entry_id | title |"
    )
    lines.append(
        "|----------|------------|----------|--------------|-----------|-----------|"
        "----------------|-----------------------------|-------|"
    )
    sorted_issues = sorted(
        report.issues,
        key=lambda i: (
            i.severity,
            i.issue_type,
            i.queue_entry_id,
            i.decision_log_queue_entry_id,
            i.issue_id,
        ),
    )
    for issue in sorted_issues:
        lines.append(
            f"| {_md_value(issue.issue_id)} | {_md_value(issue.issue_type)} | "
            f"{_md_value(issue.severity)} | {_md_value(_format_reason_codes(issue.reason_codes))} | "
            f"{_md_value(issue.source_id)} | {_md_value(issue.target_id)} | "
            f"{_md_value(issue.queue_entry_id)} | {_md_value(issue.decision_log_queue_entry_id)} | "
            f"{_md_value(issue.title)} |"
        )
    if not report.issues:
        lines.append("| _none_ | | | | | | | | |")
    lines.append("")

    # Data Quality
    lines.append("## Data Quality")
    lines.append("")
    dq = report.data_quality
    for attr in dq.__dataclass_fields__:
        value = getattr(dq, attr)
        lines.append(f"- **{attr}:** {value}")
    if report.metadata:
        lines.append("")
        lines.append("### Metadata")
        lines.append("")
        for key, value in sorted(report.metadata.items()):
            lines.append(f"- **{key}:** {value}")
    lines.append("")

    # Safety Flags
    lines.append("## Safety Flags")
    lines.append("")
    lines.append("| Flag | Value |")
    lines.append("|------|-------|")
    for key, value in sorted(_dataclass_to_dict(report.safety_flags).items()):
        lines.append(f"| {_md_value(key)} | {_md_value(value)} |")
    lines.append("")

    # Opaque Reference Notice
    lines.append("## Opaque Reference Notice")
    lines.append("")
    lines.append(
        "All report_id, queue_report_id, decision_log_report_id, queue_entry_id, "
        "decision_log_queue_entry_id, cross_reference_id, issue_id, source_id, target_id, "
        "link_id, artifact_ref, report_ref, and metadata values are opaque strings. They are "
        "serialized here for human audit only and are never opened, followed, traversed, "
        "validated, fetched, or executed."
    )
    lines.append("")

    # Research artifact notice
    lines.append("## Research Artifact Notice")
    lines.append("")
    lines.append(
        "This report does not contain or emit actionable remediation, executable "
        "instructions, operational directives, or trading actions. It is a research artifact "
        "for human review only."
    )
    lines.append("")

    # Reason Codes
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


__all__ = [
    "human_review_decision_log_consistency_report_to_dict",
    "human_review_decision_log_consistency_report_to_json_text",
    "human_review_decision_log_consistency_report_to_markdown_text",
]
