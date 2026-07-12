"""Cross-Artifact Consistency Report writer.

This module provides pure, deterministic serialization from a
ConsistencyReport into dict, JSON, or Markdown. It performs no filesystem or
network I/O, does not inspect or follow opaque references, and emits only
audit-only disclaimers.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from enum import Enum
from typing import Any

from .models import (
    ConsistencyReport,
    DEFAULT_FORBIDDEN_TERMS,
)


class ConsistencyWriterError(Exception):
    """Base exception for the consistency report writer."""


class ForbiddenPhraseLeakageError(ConsistencyWriterError):
    """Raised when generated text contains forbidden readiness/runtime phrases."""


# Safety notices emitted by all serialization formats.
_SAFETY_NOTICE = (
    "This is a local audit-only consistency report. "
    "It does not authorize execution, runtime use, or any trading action. "
    "Opaque references are not opened or validated."
)

_NO_AUTHENTICITY_NOTICE = (
    "This report is generated from in-memory data and carries no cryptographic "
    "authenticity. It does not authorize execution, runtime use, or operational "
    "deployment. It is intended for human review and audit-trail documentation only."
)


_FORBIDDEN_MODULES = frozenset(
    {
        "pathlib",
        "os",
        "subprocess",
        "socket",
        "urllib",
        "requests",
    }
)


def _raise_if_forbidden(text: str, terms: tuple[str, ...]) -> None:
    """Raise if any forbidden term appears in generated text."""
    lower = text.lower()
    for term in terms:
        if term in lower:
            raise ForbiddenPhraseLeakageError(
                f"Forbidden phrase detected in generated text: {term!r}"
            )


def _serialize_value(value: Any) -> Any:
    """Recursively serialize a model value into a JSON-compatible primitive."""
    if value is None:
        return None
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (list, tuple)):
        return [_serialize_value(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _serialize_value(v) for k, v in sorted(value.items())}
    if hasattr(value, "__dict__"):
        return _serialize_value(asdict(value))
    return str(value)


def _serialize_dataclass(obj: Any) -> dict[str, object]:
    """Serialize a dataclass instance into a dict with deterministic keys."""
    return _serialize_value(asdict(obj))  # type: ignore[return-value]


def _check_generated_text(text: str) -> None:
    """Guard generated text against forbidden readiness/runtime phrases."""
    _raise_if_forbidden(text, DEFAULT_FORBIDDEN_TERMS)


def consistency_report_to_dict(report: ConsistencyReport) -> dict[str, object]:
    """Return a deterministic JSON-compatible dict representation of the report."""
    artifacts = [_serialize_dataclass(a) for a in report.artifacts]
    findings = [_serialize_dataclass(f) for f in report.findings]
    data_quality = _serialize_dataclass(report.data_quality)
    safety_flags = _serialize_dataclass(report.safety_flags)
    reason_codes = sorted(_serialize_value(rc) for rc in report.reason_codes)
    metadata: object
    if report.metadata is None:
        metadata = None
    else:
        metadata = {
            str(k): _serialize_value(v)
            for k, v in sorted(report.metadata.items())
        }

    summary = {
        "kind": "cross_artifact_consistency_report",
        "version": "1.0",
        "report_id": report.report_id,
        "state": _serialize_value(report.state),
        "reason_codes": reason_codes,
        "finding_counts": {
            "total": report.data_quality.finding_count,
            "blocking": report.data_quality.blocking_count,
            "warning": report.data_quality.warning_count,
            "info": report.data_quality.info_count,
        },
        "artifact_count": report.data_quality.artifact_count,
    }

    result = {
        "safety_notice": _SAFETY_NOTICE,
        "no_authenticity_notice": _NO_AUTHENTICITY_NOTICE,
        "summary": summary,
        "reason_codes": reason_codes,
        "data_quality": data_quality,
        "safety_flags": safety_flags,
        "artifacts": artifacts,
        "findings": findings,
        "metadata": metadata,
        "notes": [],
    }

    _check_generated_text(json.dumps(result, ensure_ascii=True, sort_keys=True, default=str))
    return result


def consistency_report_to_json(report: ConsistencyReport) -> str:
    """Return a deterministic JSON string representation of the report."""
    payload = consistency_report_to_dict(report)
    text = json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        indent=2,
    )
    _check_generated_text(text)
    return text


def _escape_md_table(value: str) -> str:
    """Escape pipes and line breaks inside a Markdown table cell."""
    return str(value).replace("|", "\\|").replace("\n", " ")


def _format_md_table(rows: list[tuple[str, ...]]) -> str:
    """Build a Markdown table with a header row and a separator."""
    if not rows:
        return ""
    widths = [max(len(str(row[i])) for row in rows) for i in range(len(rows[0]))]
    lines: list[str] = []
    for ridx, row in enumerate(rows):
        cells = [
            _escape_md_table(str(cell)).ljust(widths[i])
            for i, cell in enumerate(row)
        ]
        line = "| " + " | ".join(cells) + " |"
        lines.append(line)
        if ridx == 0:
            sep = "|" + "|".join("-" * (widths[i] + 2) for i in range(len(row))) + "|"
            lines.append(sep)
    return "\n".join(lines)


def _format_md_key_value(items: list[tuple[str, object]]) -> str:
    """Build a Markdown table with Key/Value columns."""
    rows = [("Key", "Value")] + [(k, _escape_md_table(str(v))) for k, v in items]
    return _format_md_table(rows)


def consistency_report_to_markdown(report: ConsistencyReport) -> str:
    """Return a deterministic Markdown representation of the report."""
    lines: list[str] = []
    lines.append("# Cross-Artifact Consistency Report")
    lines.append("")
    lines.append("## Safety Notice")
    lines.append("")
    lines.append(_SAFETY_NOTICE)
    lines.append("")
    lines.append("## No Authenticity Notice")
    lines.append("")
    lines.append(_NO_AUTHENTICITY_NOTICE)
    lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append("")
    summary_items = [
        ("kind", "cross_artifact_consistency_report"),
        ("version", "1.0"),
        ("report_id", report.report_id),
        ("state", _serialize_value(report.state)),
        ("reason_codes", ", ".join(_serialize_value(rc) for rc in report.reason_codes)),
        ("total_findings", report.data_quality.finding_count),
        ("blocking_findings", report.data_quality.blocking_count),
        ("warning_findings", report.data_quality.warning_count),
        ("info_findings", report.data_quality.info_count),
        ("artifact_count", report.data_quality.artifact_count),
    ]
    lines.append(_format_md_key_value(summary_items))
    lines.append("")

    # Reason Codes
    lines.append("## Reason Codes")
    lines.append("")
    if report.reason_codes:
        lines.append(", ".join(_serialize_value(rc) for rc in report.reason_codes))
    else:
        lines.append("No reason codes.")
    lines.append("")

    # Data Quality
    lines.append("## Data Quality")
    lines.append("")
    dq = report.data_quality
    dq_items = [
        ("artifact_count", dq.artifact_count),
        ("finding_count", dq.finding_count),
        ("blocking_count", dq.blocking_count),
        ("warning_count", dq.warning_count),
        ("info_count", dq.info_count),
        ("duplicate_id_count", dq.duplicate_id_count),
        ("missing_upstream_count", dq.missing_upstream_count),
        ("orphan_downstream_count", dq.orphan_downstream_count),
        ("malformed_metadata_count", dq.malformed_metadata_count),
        ("unsupported_kind_count", dq.unsupported_kind_count),
        ("checks_performed", dq.checks_performed),
    ]
    lines.append(_format_md_key_value(dq_items))
    lines.append("")

    # Safety Flags
    lines.append("## Safety Flags")
    lines.append("")
    sf = report.safety_flags
    sf_items = [
        ("audit_only", sf.audit_only),
        ("opaque_refs_only", sf.opaque_refs_only),
        ("filesystem_access", sf.filesystem_access),
        ("network_access", sf.network_access),
        ("runtime_execution", sf.runtime_execution),
        ("trading_signal", sf.trading_signal),
    ]
    lines.append(_format_md_key_value(sf_items))
    lines.append("")

    # Artifacts
    lines.append("## Artifacts")
    lines.append("")
    if report.artifacts:
        headers = ("artifact_id", "artifact_kind", "artifact_state", "mvp", "spec", "produced_by")
        rows = [headers]
        for a in report.artifacts:
            rows.append(
                (
                    a.artifact_id,
                    a.artifact_kind,
                    a.artifact_state,
                    a.mvp or "",
                    a.spec or "",
                    a.produced_by or "",
                )
            )
        lines.append(_format_md_table(rows))
    else:
        lines.append("No artifacts provided.")
    lines.append("")

    # Findings
    lines.append("## Findings")
    lines.append("")
    if report.findings:
        headers = (
            "finding_id",
            "rule_id",
            "artifact_ids",
            "severity",
            "reason_code",
            "title",
            "description",
        )
        rows = [headers]
        for f in report.findings:
            rows.append(
                (
                    f.finding_id,
                    f.rule_id,
                    ", ".join(f.artifact_ids),
                    _serialize_value(f.severity),
                    _serialize_value(f.reason_code),
                    f.title,
                    f.description,
                )
            )
        lines.append(_format_md_table(rows))
    else:
        lines.append("No findings found.")
    lines.append("")

    # Metadata
    lines.append("## Metadata")
    lines.append("")
    if report.metadata:
        md_items = sorted((str(k), v) for k, v in report.metadata.items())
        lines.append(_format_md_key_value(md_items))
    else:
        lines.append("No metadata provided.")
    lines.append("")

    # Notes
    lines.append("## Notes")
    lines.append("")
    lines.append(
        "This report is for audit purposes only. Opaque references are not opened or validated."
    )
    lines.append("")

    text = "\n".join(lines)
    _check_generated_text(text)
    return text


def validate_no_forbidden_modules() -> None:
    """Raise if the writer module imported any forbidden I/O or runtime modules."""
    from . import writer as writer_module

    imported = frozenset(writer_module.__dict__.keys())
    intersection = imported & _FORBIDDEN_MODULES
    if intersection:
        raise ConsistencyWriterError(
            f"Forbidden modules imported in the writer scope: {sorted(intersection)}"
        )
