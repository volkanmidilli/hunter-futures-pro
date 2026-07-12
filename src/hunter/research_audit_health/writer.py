"""Deterministic writer for the Research Audit Aggregate Health Report.

MVP-48 Step 3 — Local Research Audit Aggregate Health Report Writer.

The writer is deterministic, produces only in-memory strings/dicts, and never
touches the filesystem, network, or any reference string unless explicitly asked
to write an artifact. All output ordering is stable and JSON-compatible. Generated
text is guarded against forbidden readiness/runtime phrases.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import is_dataclass
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any

from .models import (
    DEFAULT_FORBIDDEN_TERMS,
    HealthFamilyRollup,
    HealthFinding,
    HealthReport,
    HealthSafetyFlags,
    HealthScore,
    HealthSeverity,
)


class HealthWriterError(Exception):
    """Base exception for the research audit health report writer."""


class ForbiddenPhraseLeakageError(HealthWriterError):
    """Raised when generated text contains forbidden readiness/runtime phrases."""


_SAFETY_NOTICE = (
    "This report is a local, audit-only, human-audit research artifact. "
    "It is not a trading signal, not a trade approval, not an execution approval, "
    "not a strategy approval, not a portfolio approval, not a universe approval, "
    "not a release approval, not a certification, not a production readiness "
    "assessment, not a deployment readiness assessment, not a trading readiness "
    "assessment, not a recommendation, and not a suitability assessment. "
    "It does not emit action commands, shell commands, code patches, deployment "
    "steps, infrastructure changes, or executable remediation actions."
)


_NO_AUTHENTICITY_NOTICE = (
    "This report is generated from caller-provided in-memory data and carries no "
    "cryptographic authenticity. Artifact refs, paths, and opaque identifiers are "
    "serialized as strings only and are never opened, traversed, validated, "
    "followed, fetched, or executed."
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


# ---------------------------------------------------------------------------
# Value helpers
# ---------------------------------------------------------------------------


def _iso(value: datetime | None) -> str:
    """Serialize a timezone-aware datetime to ISO-8601 with UTC suffix."""
    if value is None:
        return ""
    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat()


def _serialize_value(value: Any) -> Any:
    """Recursively serialize a value to JSON-safe deterministic types."""
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
        return _iso(value)
    if isinstance(value, (list, tuple)):
        return [_serialize_value(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return sorted(_serialize_value(v) for v in value)
    if isinstance(value, (MappingProxyType, Mapping)):
        return {str(k): _serialize_value(v) for k, v in sorted(value.items())}
    if is_dataclass(value) and not isinstance(value, type):
        return _dataclass_to_dict(value)
    return str(value)


def _dataclass_to_dict(obj: Any) -> dict[str, Any]:
    """Convert a frozen dataclass instance to a deterministic JSON-safe dict."""
    if not is_dataclass(obj) or isinstance(obj, type):
        raise TypeError(f"expected dataclass instance, got {type(obj)}")
    return {field: _serialize_value(getattr(obj, field)) for field in obj.__dataclass_fields__}


# ---------------------------------------------------------------------------
# Forbidden phrase guard
# ---------------------------------------------------------------------------


_NEGATION_RE = re.compile(r"\b(not|no|never|none|neither|nor|denies|deny)\b", re.IGNORECASE)


def _is_negated(text: str, start: int) -> bool:
    """Return True if a negation word appears shortly before the given index."""
    window = text[max(0, start - 25):start]
    return bool(_NEGATION_RE.search(window))


def _raise_if_forbidden(text: str, terms: tuple[str, ...]) -> None:
    """Raise if any forbidden term appears in generated text without negation.

    The guard allows denial phrases such as "not a certification" because the
    safety notice uses them to reject prohibited claims. A standalone positive
    claim (e.g., "this is a recommendation") will still raise.
    """
    lower = text.lower()
    for term in terms:
        start = 0
        while True:
            idx = lower.find(term, start)
            if idx == -1:
                break
            if not _is_negated(lower, idx):
                raise ForbiddenPhraseLeakageError(
                    f"Forbidden phrase detected in generated text: {term!r}"
                )
            start = idx + len(term)


def _check_generated_text(text: str) -> None:
    """Guard generated text against forbidden readiness/runtime phrases."""
    _raise_if_forbidden(text, DEFAULT_FORBIDDEN_TERMS)


# ---------------------------------------------------------------------------
# Dict / JSON serialization
# ---------------------------------------------------------------------------


def health_report_to_dict(report: HealthReport) -> dict[str, Any]:
    """Return a deterministic, JSON-compatible dict for the health report."""
    data: dict[str, Any] = {
        "kind": "research_audit_health_report",
        "version": "1.0",
        "safety_notice": _SAFETY_NOTICE,
        "no_authenticity_notice": _NO_AUTHENTICITY_NOTICE,
        "report_id": report.report_id,
        "state": _serialize_value(report.state),
        "aggregate_score": _serialize_value(report.aggregate_score),
        "family_rollups": [_serialize_value(r) for r in report.family_rollups],
        "findings": [_serialize_value(f) for f in report.findings],
        "reason_code_counts": _serialize_value(report.reason_code_counts),
        "data_quality": _serialize_value(report.data_quality),
        "safety_flags": _serialize_value(report.safety_flags),
    }
    if report.metadata is not None:
        data["metadata"] = _serialize_value(report.metadata)

    text = json.dumps(data, ensure_ascii=True, sort_keys=True, default=str)
    _check_generated_text(text)
    return data


def health_report_to_json(report: HealthReport, *, indent: int = 2) -> str:
    """Return a deterministic JSON string representation of the health report."""
    data = health_report_to_dict(report)
    text = json.dumps(data, indent=indent, ensure_ascii=True, sort_keys=False, default=str)
    _check_generated_text(text)
    return text


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


def _format_score(score: HealthScore) -> str:
    """Format a HealthScore for Markdown display."""
    parts = [f"value={score.value:.4f}", f"weight={score.weight:.4f}"]
    if score.contributing_families:
        parts.append(f"families={', '.join(score.contributing_families)}")
    return "; ".join(parts)


def _format_safety_flags(flags: HealthSafetyFlags) -> list[str]:
    """Format safety flags as a Markdown table."""
    lines = ["| Flag | Value |", "|---|---|"]
    for key, value in sorted(_dataclass_to_dict(flags).items()):
        lines.append(f"| {_md_value(key)} | {_md_value(value)} |")
    return lines


def _format_family_rollups(rollups: tuple[HealthFamilyRollup, ...]) -> list[str]:
    """Format family rollups as a Markdown table."""
    lines: list[str] = []
    if not rollups:
        lines.append("_No family rollups._")
        return lines
    lines.append(
        "| family | state | score | finding_count | reason_code_counts | summary |"
    )
    lines.append(
        "|---|---|---|---|---|---|"
    )
    for r in rollups:
        reason_counts = _md_value(
            ", ".join(f"{k}={v}" for k, v in sorted(r.reason_code_counts.items()))
        )
        lines.append(
            f"| {_md_value(r.family)} | {_md_value(r.state.value)} | "
            f"{_md_value(_format_score(r.score))} | {_md_value(r.finding_count)} | "
            f"{reason_counts} | {_md_value(r.summary)} |"
        )
    return lines


def _format_findings(findings: tuple[HealthFinding, ...]) -> list[str]:
    """Format findings as a Markdown table."""
    lines: list[str] = []
    if not findings:
        lines.append("_No findings._")
        return lines
    lines.append(
        "| finding_id | rule_id | family | artifact_ids | severity | reason_code | "
        "title | description |"
    )
    lines.append(
        "|---|---|---|---|---|---|---|---|"
    )
    for f in findings:
        artifact_ids = _md_value(", ".join(f.artifact_ids))
        evidence = _md_value(
            ", ".join(f"{k}={v}" for k, v in sorted((f.evidence or {}).items()))
        )
        title = _md_value(f.title)
        description = _md_value(f.description)
        lines.append(
            f"| {_md_value(f.finding_id)} | {_md_value(f.rule_id)} | "
            f"{_md_value(f.family)} | {artifact_ids} | "
            f"{_md_value(f.severity.value)} | {_md_value(f.reason_code.value)} | "
            f"{title} | {description} |"
        )
        if evidence:
            lines.append(f"> Evidence: {evidence}")
    return lines


def health_report_to_markdown(report: HealthReport) -> str:
    """Return a deterministic Markdown representation of the health report."""
    lines: list[str] = []
    lines.append("# Research Audit Aggregate Health Report")
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
    lines.append(f"- **report_id**: `{report.report_id}`")
    lines.append(f"- **state**: `{_serialize_value(report.state)}`")
    score = report.aggregate_score
    lines.append(f"- **aggregate_score**: `{_format_score(score)}`")
    lines.append("")

    # Family rollups
    lines.append("## Family Rollups")
    lines.append("")
    lines.extend(_format_family_rollups(report.family_rollups))
    lines.append("")

    # Findings
    lines.append("## Findings")
    lines.append("")
    lines.extend(_format_findings(report.findings))
    lines.append("")

    # Data quality
    lines.append("## Data Quality")
    lines.append("")
    dq = report.data_quality
    dq_dict = _dataclass_to_dict(dq)
    for key, value in sorted(dq_dict.items()):
        lines.append(f"- **{key}**: {value}")
    lines.append("")

    # Reason code counts
    lines.append("## Reason Code Counts")
    lines.append("")
    if report.reason_code_counts:
        for code, count in sorted(report.reason_code_counts.items()):
            lines.append(f"- **{code}**: {count}")
    else:
        lines.append("_No reason codes._")
    lines.append("")

    # Safety flags
    lines.append("## Safety Flags")
    lines.append("")
    lines.extend(_format_safety_flags(report.safety_flags))
    lines.append("")

    # Metadata
    lines.append("## Metadata")
    lines.append("")
    if report.metadata:
        for key, value in sorted(report.metadata.items()):
            lines.append(f"- **{key}**: {_md_value(value)}")
    else:
        lines.append("_No metadata._")
    lines.append("")

    # Opaque ref notice
    lines.append("## Opaque Reference Notice")
    lines.append("")
    lines.append(
        "All report_id, family, artifact_id, ref, and metadata values are opaque "
        "strings. They are serialized here for human audit only and are never opened, "
        "followed, traversed, validated, fetched, or executed."
    )
    lines.append("")

    text = "\n".join(lines)
    _check_generated_text(text)
    return text


# ---------------------------------------------------------------------------
# Module validation
# ---------------------------------------------------------------------------


def validate_no_forbidden_modules() -> None:
    """Raise if the writer module imported any forbidden I/O or runtime modules."""
    from . import writer as writer_module

    imported = frozenset(writer_module.__dict__.keys())
    intersection = imported & _FORBIDDEN_MODULES
    if intersection:
        raise HealthWriterError(
            f"Forbidden modules imported in the writer scope: {sorted(intersection)}"
        )
