"""JSON/Markdown writer for hunter.research_audit_closure package.

MVP-22 — Local Research Audit Closure Report.

Writes deterministic, human-audit closure report artifacts. All file I/O is
explicit and atomic. File references, metadata strings, and reference strings
are written as plain text only and are never traversed, opened, followed,
validated, or executed.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any

from hunter.research_audit_closure.models import (
    AUDIT_CLOSURE_SECTION_KINDS,
    AuditClosureConfig,
    AuditClosureDataQuality,
    AuditClosureFinding,
    AuditClosureFindingSeverity,
    AuditClosureKind,
    AuditClosureSafetyFlags,
    AuditClosureSection,
    AuditClosureSectionKind,
    AuditClosureState,
    AuditClosureSummary,
    ResearchAuditClosureReport,
)


DEFAULT_RESEARCH_AUDIT_CLOSURE_JSON_PATH = Path(
    "data/research_audit_closure/latest_research_audit_closure_report.json"
)
DEFAULT_RESEARCH_AUDIT_CLOSURE_MARKDOWN_PATH = Path(
    "reports/research_audit_closure/latest_research_audit_closure_report.md"
)


_SAFETY_NOTICE = """\
## Safety Notice

This research audit closure report is a human-audit / contractor-handoff artifact only. It is not release approval. It is not deployment approval. It is not a trading signal, not trade approval, not execution approval, not strategy approval, and not transaction permission. It is not a runtime registry, indexer, crawler, scheduler, routing layer, dashboard, database, API, event store, or task runner. It must not be consumed by execution, strategy, Freqtrade shell, order, exchange, or any MVP execution path.

File references, metadata strings, and reference strings in this document are local strings only and are not traversed, opened, followed, validated, or executed. Referenced artifact files are not read. Human archival guide entries are advisory only and are not gating criteria for any release, deployment, execution, strategy, or transaction.
"""


_CLOSURE_NOTES = """\
This closure report is a static snapshot built from in-memory objects. It does not scan directories or read referenced files. Each section records artifact identities, open findings, backlog notes, and local reference strings for human archival review. The closure report is advisory metadata only.
"""


def _iso(dt: datetime | None) -> str | None:
    """Serialize datetime to ISO-8601 with Z suffix when UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    if dt.utcoffset() == timezone.utc.utcoffset(dt):
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return dt.isoformat()


def _serialize_value(value: Any) -> Any:
    """Recursively serialize closure values to JSON-safe deterministic types."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return _iso(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (MappingProxyType, Mapping)):
        return {str(k): _serialize_value(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_serialize_value(v) for v in value]
    return str(value)


def audit_closure_config_to_dict(config: AuditClosureConfig) -> dict[str, Any]:
    """Serialize AuditClosureConfig to a JSON-safe dict."""
    return {
        "version": config.version,
        "generated_at": _iso(config.generated_at),
        "output_format": config.output_format,
        "dry_run": config.dry_run,
        "live_trading_enabled": config.live_trading_enabled,
        "real_orders_enabled": config.real_orders_enabled,
        "leverage_enabled": config.leverage_enabled,
        "shorting_enabled": config.shorting_enabled,
        "block_on_unknown": config.block_on_unknown,
        "block_on_incomplete": config.block_on_incomplete,
        "expected_artifact_count": config.expected_artifact_count,
        "required_sections": [s.value for s in config.required_sections],
        "include_closure_narrative": config.include_closure_narrative,
    }


def audit_closure_safety_flags_to_dict(flags: AuditClosureSafetyFlags) -> dict[str, Any]:
    """Serialize AuditClosureSafetyFlags to a JSON-safe dict."""
    return {
        "dry_run": flags.dry_run,
        "live_trading_enabled": flags.live_trading_enabled,
        "real_orders_enabled": flags.real_orders_enabled,
        "leverage_enabled": flags.leverage_enabled,
        "shorting_enabled": flags.shorting_enabled,
        "closure_output_is_human_audit_only": flags.closure_output_is_human_audit_only,
        "closure_output_not_trading_signal": flags.closure_output_not_trading_signal,
        "closure_output_not_trade_approval": flags.closure_output_not_trade_approval,
        "closure_output_not_execution_readiness": flags.closure_output_not_execution_readiness,
        "closure_output_not_strategy_readiness": flags.closure_output_not_strategy_readiness,
        "closure_output_not_release_approval": flags.closure_output_not_release_approval,
        "closure_output_not_deployment_approval": flags.closure_output_not_deployment_approval,
        "closure_output_not_transaction_permission": flags.closure_output_not_transaction_permission,
        "closure_output_not_for_execution": flags.closure_output_not_for_execution,
        "closure_output_not_for_strategy": flags.closure_output_not_for_strategy,
        "closure_output_not_for_freqtrade": flags.closure_output_not_for_freqtrade,
        "closure_output_not_for_order": flags.closure_output_not_for_order,
        "closure_output_not_for_exchange": flags.closure_output_not_for_exchange,
        "closure_feedback_into_execution": flags.closure_feedback_into_execution,
        "cross_layer_feedback_into_execution": flags.cross_layer_feedback_into_execution,
        "file_reference_traversal_enabled": flags.file_reference_traversal_enabled,
        "database_persistence_enabled": flags.database_persistence_enabled,
        "web_ui_enabled": flags.web_ui_enabled,
        "dashboard_enabled": flags.dashboard_enabled,
        "runtime_registry_enabled": flags.runtime_registry_enabled,
        "indexer_crawler_enabled": flags.indexer_crawler_enabled,
        "event_store_enabled": flags.event_store_enabled,
        "task_runner_enabled": flags.task_runner_enabled,
        "file_refs_not_traversed": flags.file_refs_not_traversed,
        "artifact_files_not_read": flags.artifact_files_not_read,
        "no_action_commands_emitted": flags.no_action_commands_emitted,
        "human_archival_guide_is_non_gating": flags.human_archival_guide_is_non_gating,
    }


def audit_closure_finding_to_dict(finding: AuditClosureFinding) -> dict[str, Any]:
    """Serialize AuditClosureFinding to a JSON-safe dict without mutating input."""
    return {
        "finding_id": finding.finding_id,
        "title": finding.title,
        "severity": finding.severity,
        "description": finding.description,
        "related_mvp": finding.related_mvp,
        "spec_reference": finding.spec_reference,
        "related_references": list(finding.related_references),
        "metadata": _serialize_value(finding.metadata),
    }


def audit_closure_section_to_dict(section: AuditClosureSection) -> dict[str, Any]:
    """Serialize AuditClosureSection to a JSON-safe dict without mutating input."""
    return {
        "section_kind": section.section_kind.value,
        "title": section.title,
        "section_notes": section.section_notes,
        "findings": [audit_closure_finding_to_dict(f) for f in section.findings],
        "completed_artifacts": [
            _serialize_value(artifact) for artifact in section.completed_artifacts
        ],
        "backlog_notes": list(section.backlog_notes),
        "references": list(section.references),
        "metadata": _serialize_value(section.metadata),
    }


def audit_closure_summary_to_dict(summary: AuditClosureSummary) -> dict[str, Any]:
    """Serialize AuditClosureSummary to a JSON-safe dict without mutating input."""
    return {
        "total_sections": summary.total_sections,
        "total_findings": summary.total_findings,
        "critical_count": summary.critical_count,
        "high_count": summary.high_count,
        "medium_count": summary.medium_count,
        "low_count": summary.low_count,
        "info_count": summary.info_count,
        "completed_artifact_count": summary.completed_artifact_count,
        "open_finding_count": summary.open_finding_count,
        "backlog_note_count": summary.backlog_note_count,
        "closure_state": summary.closure_state,
        "reason_code_counts": _serialize_value(summary.reason_code_counts),
        "closure_narrative": summary.closure_narrative,
    }


def audit_closure_data_quality_to_dict(data_quality: AuditClosureDataQuality) -> dict[str, Any]:
    """Serialize AuditClosureDataQuality to a JSON-safe dict without mutating input."""
    return {
        "total_artifacts_expected": data_quality.total_artifacts_expected,
        "artifacts_present": data_quality.artifacts_present,
        "artifacts_missing": data_quality.artifacts_missing,
        "sections_present": data_quality.sections_present,
        "sections_missing": data_quality.sections_missing,
        "total_findings": data_quality.total_findings,
        "unresolved_blocker_count": data_quality.unresolved_blocker_count,
        "unresolved_warning_count": data_quality.unresolved_warning_count,
        "backlog_note_count": data_quality.backlog_note_count,
        "completeness_pct": data_quality.completeness_pct,
        "coverage_pct": data_quality.coverage_pct,
        "reason": data_quality.reason,
    }


def research_audit_closure_report_to_dict(
    report: ResearchAuditClosureReport,
) -> dict[str, Any]:
    """Serialize ResearchAuditClosureReport to a deterministic JSON-safe dict."""
    return {
        "closure_id": report.closure_id,
        "generated_at": _iso(report.generated_at),
        "version": report.version,
        "closure_kind": report.closure_kind.value,
        "closure_state": report.closure_state.value,
        "sections": [audit_closure_section_to_dict(s) for s in report.sections],
        "summary": audit_closure_summary_to_dict(report.summary),
        "data_quality": audit_closure_data_quality_to_dict(report.data_quality),
        "safety_flags": audit_closure_safety_flags_to_dict(report.safety_flags),
        "config": audit_closure_config_to_dict(report.config),
        "reason_codes": list(report.reason_codes),
        "closure_narrative": report.closure_narrative,
        "document_notes": _CLOSURE_NOTES,
    }


def _section_title(kind: AuditClosureSectionKind) -> str:
    """Return a human-readable title for a section kind."""
    return kind.value.replace("_", " ").title()


def _render_metadata(metadata: Mapping[str, Any]) -> str:
    """Render metadata mapping as plain Markdown text.

    Values remain strings only; they are not traversed as paths.
    """
    if not metadata:
        return "_No metadata._"
    lines: list[str] = []
    for key, value in _serialize_value(metadata).items():
        lines.append(f"- **{key}**: {_serialize_value(value)}")
    return "\n".join(lines)


def _render_completed_artifacts(artifacts: tuple[Mapping[str, Any], ...]) -> list[str]:
    """Render completed artifact mappings as plain Markdown text."""
    lines: list[str] = []
    if not artifacts:
        lines.append("_No completed artifacts._")
        lines.append("")
        return lines
    for idx, artifact in enumerate(artifacts, start=1):
        lines.append(f"### Artifact {idx}")
        lines.append("")
        serialized = _serialize_value(artifact)
        for key, value in serialized.items():
            lines.append(f"- **{key}**: {_serialize_value(value)}")
        lines.append("")
    return lines


def research_audit_closure_report_to_markdown(
    report: ResearchAuditClosureReport,
) -> str:
    """Render ResearchAuditClosureReport as deterministic Markdown.

    Safety notice appears before any section, finding, artifact reference,
    metadata, or detail. All references and metadata strings are rendered as
    plain text only.
    """
    lines: list[str] = [
        "# Local Research Audit Closure Report",
        "",
        _SAFETY_NOTICE,
        "",
        "## Closure Identity",
        "",
        f"- **closure_id:** `{report.closure_id}`",
        f"- **closure_kind:** {report.closure_kind.value}",
        f"- **closure_state:** {report.closure_state.value}",
        f"- **version:** {report.version}",
        f"- **generated_at:** {_iso(report.generated_at)}",
        "",
        "## Summary",
        "",
        f"- **total_sections:** {report.summary.total_sections}",
        f"- **total_findings:** {report.summary.total_findings}",
        f"- **critical_count:** {report.summary.critical_count}",
        f"- **high_count:** {report.summary.high_count}",
        f"- **medium_count:** {report.summary.medium_count}",
        f"- **low_count:** {report.summary.low_count}",
        f"- **info_count:** {report.summary.info_count}",
        f"- **completed_artifact_count:** {report.summary.completed_artifact_count}",
        f"- **open_finding_count:** {report.summary.open_finding_count}",
        f"- **backlog_note_count:** {report.summary.backlog_note_count}",
        f"- **closure_state:** {report.summary.closure_state}",
        "",
    ]

    reason_counts = _serialize_value(report.summary.reason_code_counts)
    if reason_counts:
        lines.extend(["### Reason Code Counts", ""])
        for code, count in reason_counts.items():
            lines.append(f"- {code}: {count}")
        lines.append("")

    if report.summary.closure_narrative:
        lines.extend([
            "### Closure Narrative",
            "",
            report.summary.closure_narrative,
            "",
        ])

    lines.extend([
        "## Data Quality",
        "",
        f"- **total_artifacts_expected:** {report.data_quality.total_artifacts_expected}",
        f"- **artifacts_present:** {report.data_quality.artifacts_present}",
        f"- **artifacts_missing:** {report.data_quality.artifacts_missing}",
        f"- **sections_present:** {report.data_quality.sections_present}",
        f"- **sections_missing:** {report.data_quality.sections_missing}",
        f"- **total_findings:** {report.data_quality.total_findings}",
        f"- **unresolved_blocker_count:** {report.data_quality.unresolved_blocker_count}",
        f"- **unresolved_warning_count:** {report.data_quality.unresolved_warning_count}",
        f"- **backlog_note_count:** {report.data_quality.backlog_note_count}",
        f"- **completeness_pct:** {report.data_quality.completeness_pct}",
        f"- **coverage_pct:** {report.data_quality.coverage_pct}",
        "",
    ])
    if report.data_quality.reason:
        lines.extend(["### Data Quality Reason", "", report.data_quality.reason, ""])

    lines.extend([
        "## Reason Codes",
        "",
    ])
    if report.reason_codes:
        for code in report.reason_codes:
            lines.append(f"- {code}")
    else:
        lines.append("_No reason codes._")
    lines.append("")

    lines.extend([
        "## Safety Flags",
        "",
    ])
    for key, value in audit_closure_safety_flags_to_dict(report.safety_flags).items():
        lines.append(f"- **{key}:** {value}")
    lines.append("")

    lines.extend([
        "## Sections",
        "",
    ])
    sections_by_kind = {s.section_kind: s for s in report.sections}
    if not report.sections:
        lines.append("_No sections._")
        lines.append("")
    for kind in AUDIT_CLOSURE_SECTION_KINDS:
        section = sections_by_kind.get(kind)
        if section is None:
            continue
        lines.extend([
            f"### {_section_title(kind)}",
            "",
        ])
        if section.title:
            lines.append(f"- **title:** {section.title}")
        if section.section_notes:
            lines.extend([
                "- **section_notes:**",
                "",
            ])
            for note_line in section.section_notes.splitlines():
                lines.append(f"  {note_line}")
            lines.append("")

        if kind is AuditClosureSectionKind.COMPLETED_ARTIFACTS:
            lines.extend([
                "- **completed_artifacts:**",
                "",
            ])
            lines.extend(_render_completed_artifacts(section.completed_artifacts))

        if kind is AuditClosureSectionKind.OPEN_FINDINGS:
            lines.extend([
                "- **findings:**",
                "",
            ])
            if not section.findings:
                lines.append("_No findings._")
                lines.append("")
            for finding in section.findings:
                lines.extend([
                    f"#### {finding.finding_id}",
                    "",
                    f"- **title:** {finding.title}",
                    f"- **severity:** {finding.severity}",
                ])
                if finding.description:
                    lines.append(f"- **description:** {finding.description}")
                if finding.related_mvp:
                    lines.append(f"- **related_mvp:** {finding.related_mvp}")
                if finding.spec_reference:
                    lines.append(f"- **spec_reference:** {finding.spec_reference}")
                if finding.related_references:
                    lines.append(
                        f"- **related_references:** {', '.join(finding.related_references)}"
                    )
                if finding.metadata:
                    lines.extend([
                        "- **metadata:**",
                        "",
                    ])
                    for meta_line in _render_metadata(finding.metadata).splitlines():
                        lines.append(f"  {meta_line}")
                    lines.append("")
                lines.append("")

        if kind is AuditClosureSectionKind.BACKLOG_NOTES:
            lines.extend([
                "- **backlog_notes:**",
                "",
            ])
            if not section.backlog_notes:
                lines.append("_No backlog notes._")
                lines.append("")
            for note in section.backlog_notes:
                lines.append(f"- {note}")
            lines.append("")

        if kind in (
            AuditClosureSectionKind.CYCLE_SCOPE,
            AuditClosureSectionKind.APPENDIX_REFERENCES,
        ):
            if section.references:
                lines.extend([
                    "- **references:**",
                    "",
                ])
                for ref in section.references:
                    lines.append(f"- {ref}")
                lines.append("")

        if section.metadata:
            lines.extend([
                "- **metadata:**",
                "",
            ])
            for meta_line in _render_metadata(section.metadata).splitlines():
                lines.append(f"  {meta_line}")
            lines.append("")

    lines.extend([
        "## Closure Notes",
        "",
        _CLOSURE_NOTES,
        "",
    ])

    return "\n".join(lines)


def _atomic_write_text(target: Path, content: str) -> Path:
    """Atomically write text content to target path.

    Uses temp file + flush + fsync + os.replace. Parent directories are
    created for explicit output target paths.
    """
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.parent / f".{target.name}.{os.getpid()}.tmp"
    try:
        with tmp.open("w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, target)
    except Exception:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
        raise
    return target


def atomic_write_json_research_audit_closure_report(
    report: ResearchAuditClosureReport,
    target_path: str | Path | None = None,
) -> Path:
    """Write a ResearchAuditClosureReport to JSON atomically."""
    if target_path is None:
        target_path = DEFAULT_RESEARCH_AUDIT_CLOSURE_JSON_PATH
    target = Path(target_path)
    data = research_audit_closure_report_to_dict(report)
    text = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False)
    return _atomic_write_text(target, text + "\n")


def atomic_write_markdown_research_audit_closure_report(
    report: ResearchAuditClosureReport,
    target_path: str | Path | None = None,
) -> Path:
    """Write a ResearchAuditClosureReport to Markdown atomically."""
    if target_path is None:
        target_path = DEFAULT_RESEARCH_AUDIT_CLOSURE_MARKDOWN_PATH
    target = Path(target_path)
    text = research_audit_closure_report_to_markdown(report)
    return _atomic_write_text(target, text)


def write_research_audit_closure_report(
    report: ResearchAuditClosureReport,
    json_path: str | Path | None = None,
    markdown_path: str | Path | None = None,
) -> tuple[Path, Path]:
    """Write both JSON and Markdown representations of the closure report."""
    json_out = atomic_write_json_research_audit_closure_report(report, target_path=json_path)
    md_out = atomic_write_markdown_research_audit_closure_report(report, target_path=markdown_path)
    return json_out, md_out
