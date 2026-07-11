"""Pure writer serialization for hunter.human_review_audit_bundle reports.

MVP-43 Step 2 — Local Research Human Review Audit Bundle Export.

The writer is deterministic, produces only in-memory strings/dicts, and never
touches the filesystem, network, or any reference string. All output ordering
is stable and JSON-compatible.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from enum import Enum
from json import dumps
from types import MappingProxyType
from typing import Any

from .models import (
    HumanReviewAuditBundleIssue,
    HumanReviewAuditBundleReport,
    HumanReviewAuditBundleSafetyFlags,
    HumanReviewAuditBundleSection,
)


# ---------------------------------------------------------------------------
# Public writer API
# ---------------------------------------------------------------------------

def bundle_report_to_dict(report: HumanReviewAuditBundleReport) -> dict[str, Any]:
    """Return a deterministic, JSON-compatible dict for the bundle report."""
    data_quality = report.data_quality
    safety_flags = report.safety_flags

    output: dict[str, Any] = {}
    output["safety_notice"] = report.safety_notice
    output["bundle_id"] = report.bundle_id
    output["report_id"] = report.report_id
    output["generated_at"] = _iso_datetime(report.generated_at)
    output["state"] = _enum_value(report.state)
    output["project_version"] = report.project_version
    output["sections"] = [_section_to_dict(s) for s in report.sections]
    output["issues"] = [_issue_to_dict(i) for i in report.issues]
    output["data_quality"] = _data_quality_to_dict(data_quality)
    output["safety_flags"] = _safety_flags_to_dict(safety_flags)
    output["reason_codes"] = [_enum_value(rc) for rc in report.reason_codes]
    output["metadata"] = _sorted_str_dict(report.metadata)
    output["notes"] = report.notes
    return output


def bundle_report_to_json(
    report: HumanReviewAuditBundleReport,
    *,
    indent: int | None = 2,
    ensure_ascii: bool = False,
) -> str:
    """Return deterministic JSON text for the bundle report."""
    return dumps(
        bundle_report_to_dict(report),
        indent=indent,
        ensure_ascii=ensure_ascii,
        sort_keys=False,
        default=str,
    )


def bundle_report_to_markdown(report: HumanReviewAuditBundleReport) -> str:
    """Return deterministic Markdown text for the bundle report."""
    lines: list[str] = []
    lines.append(
        f"This bundle is a local, audit-only, human-audit research artifact. "
        f"{report.safety_notice}"
    )
    lines.append("")
    lines.append("# Human Review Audit Bundle Report")
    lines.append("")
    lines.append("## Report identity")
    lines.append("")
    lines.append(f"- **bundle_id**: `{report.bundle_id}`")
    lines.append(f"- **report_id**: `{report.report_id}`")
    lines.append(f"- **generated_at**: `{_iso_datetime(report.generated_at)}`")
    lines.append(f"- **state**: `{_enum_value(report.state)}`")
    lines.append(f"- **project_version**: `{report.project_version}`")
    lines.append("")
    lines.append("## Safety flags")
    lines.append("")
    lines.extend(_safety_flags_markdown(report.safety_flags))
    lines.append("")
    lines.append("## Data quality")
    lines.append("")
    lines.extend(_data_quality_markdown(report.data_quality))
    lines.append("")
    lines.append("## Reason codes")
    lines.append("")
    for rc in report.reason_codes:
        lines.append(f"- `{_enum_value(rc)}`")
    if not report.reason_codes:
        lines.append("_None_")
    lines.append("")
    lines.append("## Sections")
    lines.append("")
    if report.sections:
        for section in report.sections:
            lines.extend(_section_markdown(section))
    else:
        lines.append("_No sections._")
    lines.append("")
    lines.append("## Issues")
    lines.append("")
    if report.issues:
        for issue in report.issues:
            lines.extend(_issue_markdown(issue))
    else:
        lines.append("_No issues._")
    lines.append("")
    lines.append("## Metadata")
    lines.append("")
    if report.metadata:
        lines.append("| Key | Value |")
        lines.append("|---|---|")
        for key in sorted(report.metadata):
            lines.append(f"| {key} | {_md_escape(report.metadata[key])} |")
    else:
        lines.append("_No metadata._")
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    if report.notes:
        lines.append(_md_escape(report.notes))
    else:
        lines.append("_No notes._")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Dict builders
# ---------------------------------------------------------------------------

def _section_to_dict(section: HumanReviewAuditBundleSection) -> dict[str, Any]:
    return {
        "section_id": section.section_id,
        "section_kind": section.section_kind,
        "upstream_report_id": section.upstream_report_id,
        "upstream_state": section.upstream_state,
        "upstream_reason_codes": list(section.upstream_reason_codes),
        "generated_at": _iso_datetime(section.generated_at),
        "summary": _sorted_any_dict(section.summary),
        "metadata": _sorted_str_dict(section.metadata),
        "notes": section.notes,
    }


def _issue_to_dict(issue: HumanReviewAuditBundleIssue) -> dict[str, Any]:
    return {
        "issue_id": issue.issue_id,
        "issue_type": issue.issue_type,
        "severity": issue.severity,
        "reason_codes": list(issue.reason_codes),
        "source_section_kind": issue.source_section_kind,
        "source_id": issue.source_id,
        "title": issue.title,
        "description": issue.description,
        "generated_at": _iso_datetime(issue.generated_at),
    }


def _data_quality_to_dict(data_quality: Any) -> dict[str, Any]:
    # Intentionally duck-typed so upstream model changes are tolerated.
    keys = [
        "section_count",
        "upstream_issue_count",
        "blocking_issues",
        "advisory_issues",
        "info_findings",
        "queue_entry_count",
        "decision_result_count",
        "consistency_cross_reference_count",
        "unsafe_content_count",
        "forbidden_term_count",
    ]
    result: dict[str, Any] = {}
    for key in keys:
        result[key] = int(getattr(data_quality, key, 0))
    return result


def _safety_flags_to_dict(flags: HumanReviewAuditBundleSafetyFlags) -> dict[str, bool]:
    return {
        "is_safe": flags.is_safe,
        "audit_only": flags.audit_only,
        "no_executable_actions": flags.no_executable_actions,
        "no_trading_instructions": flags.no_trading_instructions,
        "no_approval_claims": flags.no_approval_claims,
        "references_opaque": flags.references_opaque,
        "no_network": flags.no_network,
        "no_server": flags.no_server,
    }


# ---------------------------------------------------------------------------
# Markdown builders
# ---------------------------------------------------------------------------

def _safety_flags_markdown(flags: HumanReviewAuditBundleSafetyFlags) -> list[str]:
    lines = ["| Flag | Value |", "|---|---|"]
    for key, value in _safety_flags_to_dict(flags).items():
        lines.append(f"| {key} | {value} |")
    return lines


def _data_quality_markdown(data_quality: Any) -> list[str]:
    lines = ["| Counter | Value |", "|---|---|"]
    for key, value in _data_quality_to_dict(data_quality).items():
        lines.append(f"| {key} | {value} |")
    return lines


def _section_markdown(section: HumanReviewAuditBundleSection) -> list[str]:
    lines: list[str] = []
    lines.append(f"### {section.section_id} ({section.section_kind})")
    lines.append("")
    lines.append(f"- **section_id**: `{section.section_id}`")
    lines.append(f"- **section_kind**: `{section.section_kind}`")
    lines.append(f"- **upstream_report_id**: `{section.upstream_report_id}`")
    lines.append(f"- **upstream_state**: `{section.upstream_state}`")
    lines.append(
        f"- **upstream_reason_codes**: `{', '.join(section.upstream_reason_codes) or 'none'}`"
    )
    lines.append(f"- **generated_at**: `{_iso_datetime(section.generated_at)}`")
    lines.append("")
    lines.append("#### Summary")
    lines.append("")
    if section.summary:
        lines.append("| Key | Value |")
        lines.append("|---|---|")
        for key in sorted(section.summary):
            lines.append(f"| {key} | {_md_escape(section.summary[key])} |")
    else:
        lines.append("_No summary._")
    lines.append("")
    lines.append("#### Metadata")
    lines.append("")
    if section.metadata:
        lines.append("| Key | Value |")
        lines.append("|---|---|")
        for key in sorted(section.metadata):
            lines.append(f"| {key} | {_md_escape(section.metadata[key])} |")
    else:
        lines.append("_No metadata._")
    lines.append("")
    lines.append("#### Notes")
    lines.append("")
    if section.notes:
        lines.append(_md_escape(section.notes))
    else:
        lines.append("_No notes._")
    return lines


def _issue_markdown(issue: HumanReviewAuditBundleIssue) -> list[str]:
    lines: list[str] = []
    lines.append(f"### {issue.issue_id} ({issue.source_section_kind})")
    lines.append("")
    lines.append(f"- **issue_id**: `{issue.issue_id}`")
    lines.append(f"- **issue_type**: `{issue.issue_type}`")
    lines.append(f"- **severity**: `{issue.severity}`")
    lines.append(
        f"- **reason_codes**: `{', '.join(issue.reason_codes) or 'none'}`"
    )
    lines.append(f"- **source_section_kind**: `{issue.source_section_kind}`")
    lines.append(f"- **source_id**: `{issue.source_id}`")
    lines.append(f"- **title**: {_md_escape(issue.title)}")
    lines.append(f"- **description**: {_md_escape(issue.description)}")
    lines.append(f"- **generated_at**: `{_iso_datetime(issue.generated_at)}`")
    return lines


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _enum_value(value: Any) -> str:
    if isinstance(value, Enum):
        return value.value
    return str(value)


def _iso_datetime(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.astimezone(timezone.utc).isoformat()


def _sorted_str_dict(value: Mapping[str, str]) -> dict[str, str]:
    data = dict(value) if isinstance(value, MappingProxyType) else value
    return {str(k): str(v) for k, v in sorted(data.items())}


def _sorted_any_dict(value: Mapping[str, Any]) -> dict[str, Any]:
    data = dict(value) if isinstance(value, MappingProxyType) else value
    return {str(k): v for k, v in sorted(data.items())}


def _md_escape(value: Any) -> str:
    text = str(value)
    # Escape characters that would break Markdown tables or inline code.
    for old, new in (
        ("\\", "\\\\"),
        ("|", "\\|"),
    ):
        text = text.replace(old, new)
    return text
