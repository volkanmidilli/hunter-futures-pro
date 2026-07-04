"""Writer for hunter.cross_pack_consistency package. MVP-36 Step 2.

Deterministic JSON, CSV, and Markdown serialization for CrossPackConsistencyReport
with atomic writes. Output is a human-audit / research-only artifact. It is not an
approval, certification, production readiness assessment, trading readiness
assessment, recommendation, suitability assessment, or signal. It does not emit
action commands, suggest orders, or create execution instructions. File references,
metadata, report paths, artifact references, section references, and requirement
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

from hunter.cross_pack_consistency.models import (
    CROSS_PACK_CONSISTENCY_VERSION,
    CrossPackArtifactRef,
    CrossPackConsistencyDataQuality,
    CrossPackConsistencyIssue,
    CrossPackConsistencyReasonCode,
    CrossPackConsistencyReport,
    CrossPackConsistencyRule,
    CrossPackConsistencySafetyFlags,
    CrossPackDeclaration,
    CrossPackRequirementRef,
    CrossPackSectionRef,
    CrossPackStateClaim,
)

# Default local artifact paths. These are explicit, local, and never remote.
DEFAULT_JSON_PATH: Path = Path("data/cross_pack_consistency/cross_pack_consistency.json")
DEFAULT_CSV_PATH: Path = Path(
    "data/cross_pack_consistency/cross_pack_consistency_issues.csv"
)
DEFAULT_MD_PATH: Path = Path(
    "reports/cross_pack_consistency/cross_pack_consistency.md"
)

_SAFETY_NOTICE = (
    "This report is a human-audit / research-only artifact. It is not an "
    "approval, certification, production readiness assessment, trading readiness "
    "assessment, recommendation, suitability assessment, or signal. Do not use it "
    "for execution, order placement, or strategy approval. Consistency findings are "
    "descriptive observations only and are not trading or execution instructions."
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
    if isinstance(obj, CrossPackConsistencySafetyFlags):
        result["is_safe"] = obj.is_safe
    return result


# ---------------------------------------------------------------------------
# Dict / JSON serialization
# ---------------------------------------------------------------------------


def cross_pack_consistency_report_to_dict(
    report: CrossPackConsistencyReport,
) -> dict[str, Any]:
    """Convert a CrossPackConsistencyReport to a deterministic dictionary.

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


def cross_pack_consistency_report_to_json_text(
    report: CrossPackConsistencyReport,
) -> str:
    """Serialize a CrossPackConsistencyReport to deterministic JSON text."""
    data = cross_pack_consistency_report_to_dict(report)
    return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=False) + "\n"


# ---------------------------------------------------------------------------
# CSV serialization
# ---------------------------------------------------------------------------

_CSV_COLUMNS = (
    "report_id",
    "generated_at",
    "issue_id",
    "issue_type",
    "severity",
    "subject_id",
    "source_pack_id",
    "target_pack_id",
    "reason_codes",
    "message",
)


def _report_id(report: CrossPackConsistencyReport) -> str:
    """Return the deterministic report identifier already produced by the engine."""
    return report.report_id


def _format_reason_codes(codes: tuple[str, ...]) -> str:
    """Format reason codes for CSV using a deterministic join."""
    return "|".join(sorted(codes))


def cross_pack_consistency_report_to_csv_text(
    report: CrossPackConsistencyReport,
) -> str:
    """Serialize consistency issues to deterministic CSV rows.

    Each row corresponds to one CrossPackConsistencyIssue in report.issues. The
    writer reads the issues directly and does not recompute classification.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(_CSV_COLUMNS)
    generated_at = _iso(report.generated_at)
    report_id = _report_id(report)

    sorted_issues = sorted(
        report.issues,
        key=lambda i: (i.issue_id, i.issue_type.value, i.subject_id, i.source_pack_id, i.target_pack_id),
    )

    for issue in sorted_issues:
        row = [
            report_id,
            generated_at,
            issue.issue_id,
            issue.issue_type.value,
            issue.severity.value,
            issue.subject_id,
            issue.source_pack_id,
            issue.target_pack_id,
            _format_reason_codes(tuple(code.value for code in issue.reason_codes)),
            issue.message,
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


def _format_reason_codes_enum(
    codes: tuple[CrossPackConsistencyReasonCode, ...],
) -> str:
    """Format reason codes for Markdown using a deterministic join."""
    return ", ".join(sorted(code.value for code in codes))


def _manual_review_items(
    report: CrossPackConsistencyReport,
) -> list[tuple[str, str, str]]:
    """Return items flagged for manual review attention.

    Each tuple is (kind, identifier, message).
    """
    items: list[tuple[str, str, str]] = []
    for declaration in report.declarations:
        if declaration.requires_manual_review:
            items.append((
                "pack declaration",
                declaration.pack_id,
                "Declaration requires manual review.",
            ))
    for ref in report.artifact_refs:
        if ref.requires_manual_review:
            items.append((
                "artifact ref",
                f"{ref.pack_id}/{ref.ref_id}",
                "Artifact reference requires manual review.",
            ))
    for ref in report.section_refs:
        if ref.requires_manual_review:
            items.append((
                "section ref",
                f"{ref.pack_id}/{ref.ref_id}",
                "Section reference requires manual review.",
            ))
    for ref in report.requirement_refs:
        if ref.requires_manual_review:
            items.append((
                "requirement ref",
                f"{ref.pack_id}/{ref.ref_id}",
                "Requirement reference requires manual review.",
            ))
    for issue in report.issues:
        if issue.issue_type.value in {
            "missing_manual_review",
            "conflicting_state",
            "incompatible_state_combination",
        }:
            items.append((
                "issue",
                issue.issue_id,
                issue.message or "Issue may require manual review.",
            ))
    return items


def cross_pack_consistency_report_to_markdown_text(
    report: CrossPackConsistencyReport,
) -> str:
    """Serialize a CrossPackConsistencyReport to deterministic Markdown text.

    The output contains an immediate audit-only / research-only safety notice,
    summary, consistency issues, pack declarations, references, state claims,
    rules, data quality, safety flags, and manual review items. No trading or
    execution instructions are emitted.
    """
    lines: list[str] = []
    lines.append("# Local Research Cross-Pack Consistency Validator Report")
    lines.append("")
    lines.append(f"> {_SAFETY_NOTICE}")
    lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **version:** {CROSS_PACK_CONSISTENCY_VERSION}")
    lines.append(f"- **report_id:** {report.report_id}")
    lines.append(f"- **state:** {report.state.value}")
    lines.append(f"- **generated_at:** {_iso(report.generated_at)}")
    if report.project_version:
        lines.append(f"- **project_version:** {report.project_version}")
    dq = report.data_quality
    lines.append(f"- **total_packs:** {dq.total_packs}")
    lines.append(f"- **total_artifact_refs:** {dq.total_artifact_refs}")
    lines.append(f"- **total_section_refs:** {dq.total_section_refs}")
    lines.append(f"- **total_requirement_refs:** {dq.total_requirement_refs}")
    lines.append(f"- **total_state_claims:** {dq.total_state_claims}")
    lines.append(f"- **total_rules:** {dq.total_rules}")
    lines.append(f"- **total_issues:** {dq.total_issues}")
    lines.append(f"- **blocking_issue_count:** {dq.blocking_issue_count}")
    lines.append(f"- **advisory_issue_count:** {dq.advisory_issue_count}")
    lines.append(f"- **info_issue_count:** {dq.info_issue_count}")
    lines.append(f"- **duplicate_id_count:** {dq.duplicate_id_count}")
    lines.append(f"- **orphan_ref_count:** {dq.orphan_ref_count}")
    lines.append(f"- **stale_declaration_count:** {dq.stale_declaration_count}")
    lines.append(f"- **sections_present:** {dq.sections_present}")
    lines.append("")
    lines.append(
        "Consistency findings are descriptive observations only and are not "
        "approval, certification, or trading readiness scores."
    )
    lines.append("")

    # Consistency issues
    lines.append("## Consistency Issues")
    lines.append("")
    lines.append(
        "| issue_id | issue_type | severity | subject_id | source_pack_id | "
        "target_pack_id | reason_codes | message |"
    )
    lines.append(
        "|----------|------------|----------|------------|----------------|"
        "----------------|--------------|---------|"
    )
    sorted_issues = sorted(
        report.issues,
        key=lambda i: (i.issue_id, i.issue_type.value, i.subject_id, i.source_pack_id, i.target_pack_id),
    )
    for issue in sorted_issues:
        lines.append(
            f"| {_md_value(issue.issue_id)} | {_md_value(issue.issue_type.value)} | "
            f"{_md_value(issue.severity.value)} | {_md_value(issue.subject_id)} | "
            f"{_md_value(issue.source_pack_id)} | {_md_value(issue.target_pack_id)} | "
            f"{_md_value(_format_reason_codes_enum(issue.reason_codes))} | {_md_value(issue.message)} |"
        )
    if not report.issues:
        lines.append("| _none_ | | | | | | | |")
    lines.append("")

    # Pack declarations
    lines.append("## Pack Declarations")
    lines.append("")
    lines.append(
        "| pack_id | version | title | description | declared_state | "
        "requires_manual_review | generated_at |"
    )
    lines.append(
        "|---------|---------|-------|-------------|----------------|"
        "------------------------|--------------|"
    )
    for declaration in report.declarations:
        lines.append(
            f"| {_md_value(declaration.pack_id)} | {_md_value(declaration.version)} | "
            f"{_md_value(declaration.title)} | {_md_value(declaration.description)} | "
            f"{_md_value(declaration.declared_state)} | "
            f"{_md_value(declaration.requires_manual_review)} | "
            f"{_md_value(_format_datetime(declaration.generated_at))} |"
        )
    if not report.declarations:
        lines.append("| _none_ | | | | | | |")
    lines.append("")

    # Artifact refs
    lines.append("## Artifact References")
    lines.append("")
    lines.append(
        "| ref_id | pack_id | reference | label | message | requires_manual_review | generated_at |"
    )
    lines.append(
        "|--------|---------|-----------|-------|---------|------------------------|--------------|"
    )
    for ref in report.artifact_refs:
        lines.append(
            f"| {_md_value(ref.ref_id)} | {_md_value(ref.pack_id)} | "
            f"{_md_value(ref.reference)} | {_md_value(ref.label)} | {_md_value(ref.message)} | "
            f"{_md_value(ref.requires_manual_review)} | {_md_value(_format_datetime(ref.generated_at))} |"
        )
    if not report.artifact_refs:
        lines.append("| _none_ | | | | | | |")
    lines.append("")

    # Section refs
    lines.append("## Section References")
    lines.append("")
    lines.append(
        "| ref_id | pack_id | reference | label | message | requires_manual_review | generated_at |"
    )
    lines.append(
        "|--------|---------|-----------|-------|---------|------------------------|--------------|"
    )
    for ref in report.section_refs:
        lines.append(
            f"| {_md_value(ref.ref_id)} | {_md_value(ref.pack_id)} | "
            f"{_md_value(ref.reference)} | {_md_value(ref.label)} | {_md_value(ref.message)} | "
            f"{_md_value(ref.requires_manual_review)} | {_md_value(_format_datetime(ref.generated_at))} |"
        )
    if not report.section_refs:
        lines.append("| _none_ | | | | | | |")
    lines.append("")

    # Requirement refs
    lines.append("## Requirement References")
    lines.append("")
    lines.append(
        "| ref_id | pack_id | reference | label | message | requires_manual_review | generated_at |"
    )
    lines.append(
        "|--------|---------|-----------|-------|---------|------------------------|--------------|"
    )
    for ref in report.requirement_refs:
        lines.append(
            f"| {_md_value(ref.ref_id)} | {_md_value(ref.pack_id)} | "
            f"{_md_value(ref.reference)} | {_md_value(ref.label)} | {_md_value(ref.message)} | "
            f"{_md_value(ref.requires_manual_review)} | {_md_value(_format_datetime(ref.generated_at))} |"
        )
    if not report.requirement_refs:
        lines.append("| _none_ | | | | | | |")
    lines.append("")

    # State claims
    lines.append("## State Claims")
    lines.append("")
    lines.append("| subject_id | state_label | pack_id | message |")
    lines.append("|------------|-------------|---------|---------|")
    for claim in report.state_claims:
        lines.append(
            f"| {_md_value(claim.subject_id)} | {_md_value(claim.state_label)} | "
            f"{_md_value(claim.pack_id)} | {_md_value(claim.message)} |"
        )
    if not report.state_claims:
        lines.append("| _none_ | | | |")
    lines.append("")

    # Rules
    lines.append("## Rules")
    lines.append("")
    lines.append(
        "| rule_type | source_pack_id | target_pack_id | subject_id | ref_kind | "
        "ref_id | expected_version | expected_state | forbidden_states | severity | message |"
    )
    lines.append(
        "|-----------|----------------|----------------|------------|----------|"
        "|--------|------------------|----------------|------------------|----------|---------|"
    )
    for rule in report.rules:
        forbidden_states = ", ".join(rule.forbidden_states) if rule.forbidden_states else ""
        lines.append(
            f"| {_md_value(rule.rule_type.value)} | {_md_value(rule.source_pack_id)} | "
            f"{_md_value(rule.target_pack_id)} | {_md_value(rule.subject_id)} | "
            f"{_md_value(rule.ref_kind)} | {_md_value(rule.ref_id)} | "
            f"{_md_value(rule.expected_version)} | {_md_value(rule.expected_state)} | "
            f"{_md_value(forbidden_states)} | {_md_value(rule.severity.value)} | {_md_value(rule.message)} |"
        )
    if not report.rules:
        lines.append("| _none_ | | | | | | | | | | |")
    lines.append("")

    # Data quality
    lines.append("## Data Quality")
    lines.append("")
    lines.append(f"- **total_packs:** {dq.total_packs}")
    lines.append(f"- **total_artifact_refs:** {dq.total_artifact_refs}")
    lines.append(f"- **total_section_refs:** {dq.total_section_refs}")
    lines.append(f"- **total_requirement_refs:** {dq.total_requirement_refs}")
    lines.append(f"- **total_state_claims:** {dq.total_state_claims}")
    lines.append(f"- **total_rules:** {dq.total_rules}")
    lines.append(f"- **total_issues:** {dq.total_issues}")
    lines.append(f"- **blocking_issue_count:** {dq.blocking_issue_count}")
    lines.append(f"- **advisory_issue_count:** {dq.advisory_issue_count}")
    lines.append(f"- **info_issue_count:** {dq.info_issue_count}")
    lines.append(f"- **duplicate_id_count:** {dq.duplicate_id_count}")
    lines.append(f"- **orphan_ref_count:** {dq.orphan_ref_count}")
    lines.append(f"- **stale_declaration_count:** {dq.stale_declaration_count}")
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
    lines.append("## Manual Review")
    lines.append("")
    manual_items = _manual_review_items(report)
    if manual_items:
        for kind, identifier, message in manual_items:
            lines.append(f"- {kind} `{identifier}`: {message}")
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


def atomic_write_json_cross_pack_consistency_report(
    report: CrossPackConsistencyReport,
    path: str | Path | None = None,
) -> Path:
    """Serialize CrossPackConsistencyReport to JSON and write atomically."""
    target = _coerce_path(path, DEFAULT_JSON_PATH)
    _atomic_write(target, cross_pack_consistency_report_to_json_text(report))
    return target


def atomic_write_csv_cross_pack_consistency_report(
    report: CrossPackConsistencyReport,
    path: str | Path | None = None,
) -> Path:
    """Serialize CrossPackConsistencyReport issues to CSV and write atomically."""
    target = _coerce_path(path, DEFAULT_CSV_PATH)
    _atomic_write(target, cross_pack_consistency_report_to_csv_text(report))
    return target


def atomic_write_markdown_cross_pack_consistency_report(
    report: CrossPackConsistencyReport,
    path: str | Path | None = None,
) -> Path:
    """Serialize CrossPackConsistencyReport to Markdown and write atomically."""
    target = _coerce_path(path, DEFAULT_MD_PATH)
    _atomic_write(target, cross_pack_consistency_report_to_markdown_text(report) + "\n")
    return target


_DEFAULT_PATH = object()


def write_cross_pack_consistency_report(
    report: CrossPackConsistencyReport,
    json_path: str | Path | None | object = _DEFAULT_PATH,
    csv_path: str | Path | None | object = _DEFAULT_PATH,
    markdown_path: str | Path | None | object = _DEFAULT_PATH,
) -> tuple[Path | None, Path | None, Path | None]:
    """Write CrossPackConsistencyReport to JSON, CSV, and Markdown as requested.

    Pass None for a format to skip writing that artifact. Default paths are used
    when a path is omitted and the format is written.
    """
    json_out = (
        atomic_write_json_cross_pack_consistency_report(
            report, None if json_path is _DEFAULT_PATH else json_path
        )
        if json_path is not None
        else None
    )
    csv_out = (
        atomic_write_csv_cross_pack_consistency_report(
            report, None if csv_path is _DEFAULT_PATH else csv_path
        )
        if csv_path is not None
        else None
    )
    md_out = (
        atomic_write_markdown_cross_pack_consistency_report(
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
    "atomic_write_csv_cross_pack_consistency_report",
    "atomic_write_json_cross_pack_consistency_report",
    "atomic_write_markdown_cross_pack_consistency_report",
    "cross_pack_consistency_report_to_csv_text",
    "cross_pack_consistency_report_to_dict",
    "cross_pack_consistency_report_to_json_text",
    "cross_pack_consistency_report_to_markdown_text",
    "write_cross_pack_consistency_report",
]
