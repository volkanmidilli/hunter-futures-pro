"""Writer for hunter.evidence_traceability package. MVP-34 — Local Research Evidence Traceability Matrix.

Deterministic JSON, CSV, and Markdown serialization for EvidenceTraceabilityReport
with atomic writes. Output is a human-audit / research-only artifact. It is not a
trading signal, not trade approval, not strategy approval, not execution approval,
not portfolio approval, not universe approval, and not a certification of trading
readiness. It does not emit action commands, suggest orders, or create execution
instructions. File references, metadata, and artifact references are serialized
as opaque strings only; they are never opened, traversed, validated, followed, or
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

from hunter.evidence_traceability.models import (
    EVIDENCE_TRACEABILITY_VERSION,
    EvidenceTraceabilityConfig,
    EvidenceTraceabilityCoverageState,
    EvidenceTraceabilityLinkType,
    EvidenceTraceabilityReasonCode,
    EvidenceTraceabilityReport,
    EvidenceTraceabilityResult,
    EvidenceTraceabilitySafetyFlags,
    EvidenceTraceabilitySeverity,
    EvidenceTraceabilityState,
)

# Default local artifact paths. These are explicit, local, and never remote.
DEFAULT_JSON_PATH: Path = Path("data/evidence_traceability/evidence_traceability.json")
DEFAULT_CSV_PATH: Path = Path(
    "data/evidence_traceability/evidence_traceability_edges.csv"
)
DEFAULT_MD_PATH: Path = Path(
    "reports/evidence_traceability/evidence_traceability.md"
)

_SAFETY_NOTICE = (
    "This matrix is a human-audit research artifact. It is not trading advice, "
    "not a trading signal, and not a certification of trading readiness. Do not "
    "use it for execution, order placement, or strategy approval."
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
    if isinstance(obj, EvidenceTraceabilitySafetyFlags):
        result["is_safe"] = obj.is_safe
    return result


# ---------------------------------------------------------------------------
# Dict / JSON serialization
# ---------------------------------------------------------------------------


def evidence_traceability_report_to_dict(
    report: EvidenceTraceabilityReport,
) -> dict[str, Any]:
    """Convert an EvidenceTraceabilityReport to a deterministic dictionary.

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


def evidence_traceability_report_to_json_text(
    report: EvidenceTraceabilityReport,
) -> str:
    """Serialize an EvidenceTraceabilityReport to deterministic JSON text."""
    data = evidence_traceability_report_to_dict(report)
    return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=False) + "\n"


# ---------------------------------------------------------------------------
# CSV serialization
# ---------------------------------------------------------------------------


_CSV_COLUMNS = (
    "report_id",
    "generated_at",
    "source_id",
    "target_id",
    "link_type",
    "coverage_state",
    "severity",
    "reason_codes",
    "message",
)


def _report_id(report: EvidenceTraceabilityReport) -> str:
    """Return a deterministic report identifier derived from generated_at."""
    return f"evidence-traceability-{_iso(report.generated_at)}"


def _severity_str(result_state: EvidenceTraceabilityState | None) -> str:
    """Return a severity label for a result state."""
    if result_state is EvidenceTraceabilityState.BLOCKED:
        return EvidenceTraceabilitySeverity.BLOCKING.value
    return EvidenceTraceabilitySeverity.ADVISORY.value


def _coverage_for_link(
    link: Any,
    results_map: dict[str, list[EvidenceTraceabilityResult]],
) -> EvidenceTraceabilityCoverageState:
    """Derive coverage state for a link, preferring requirement coverage results."""
    target_id = str(link.target_id)
    if link.link_type is not EvidenceTraceabilityLinkType.COVERED_BY:
        return EvidenceTraceabilityCoverageState.NOT_APPLICABLE
    for result in results_map.get(target_id, []):
        if result.category != "requirement":
            continue
        if result.reason_code is EvidenceTraceabilityReasonCode.OK:
            return EvidenceTraceabilityCoverageState.COVERED
        if result.reason_code is EvidenceTraceabilityReasonCode.MISSING_COVERAGE:
            return EvidenceTraceabilityCoverageState.MISSING
        if result.reason_code is EvidenceTraceabilityReasonCode.PARTIAL_COVERAGE:
            return EvidenceTraceabilityCoverageState.PARTIAL
    return EvidenceTraceabilityCoverageState.NOT_APPLICABLE


def _matching_results(
    link: Any,
    results_map: dict[str, list[EvidenceTraceabilityResult]],
) -> list[EvidenceTraceabilityResult]:
    """Collect results relevant to a link without opening any references."""
    seen: set[int] = set()
    matched: list[EvidenceTraceabilityResult] = []
    for key in (
        link.link_id,
        link.source_id,
        link.target_id,
        f"{link.source_id}->{link.target_id}",
    ):
        for result in results_map.get(str(key), []):
            if id(result) in seen:
                continue
            seen.add(id(result))
            matched.append(result)
    return matched


def evidence_traceability_report_to_csv_text(
    report: EvidenceTraceabilityReport,
) -> str:
    """Serialize traceability links to deterministic CSV edge rows.

    Each row corresponds to one link in report.links. Rows are enriched from
    matching results by source_id, target_id, or link_id, but no referenced
    paths are ever opened or followed.
    """
    results_map: dict[str, list[EvidenceTraceabilityResult]] = {}
    for result in report.results:
        results_map.setdefault(result.item_id, []).append(result)

    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(_CSV_COLUMNS)
    generated_at = _iso(report.generated_at)
    report_id = _report_id(report)

    for link in report.links:
        matched = _matching_results(link, results_map)
        coverage_state = _coverage_for_link(link, results_map)
        state = EvidenceTraceabilityState.OK
        if matched:
            if any(r.state is EvidenceTraceabilityState.BLOCKED for r in matched):
                state = EvidenceTraceabilityState.BLOCKED
            elif any(r.state is EvidenceTraceabilityState.DEGRADED for r in matched):
                state = EvidenceTraceabilityState.DEGRADED
        severity = _severity_str(state)
        reason_codes = "|".join(
            sorted(
                {
                    r.reason_code.value
                    for r in matched
                    if r.reason_code is not EvidenceTraceabilityReasonCode.OK
                }
            )
        )
        messages = [r.message for r in matched if r.message]
        if not messages and link.message:
            messages.append(link.message)
        message = "; ".join(messages)

        row = [
            report_id,
            generated_at,
            link.source_id,
            link.target_id,
            link.link_type.value,
            coverage_state.value,
            severity,
            reason_codes,
            message,
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


def _format_reason_codes(codes: tuple[EvidenceTraceabilityReasonCode, ...]) -> str:
    """Format reason codes for Markdown."""
    return ", ".join(code.value for code in codes)


def evidence_traceability_report_to_markdown_text(
    report: EvidenceTraceabilityReport,
) -> str:
    """Serialize an EvidenceTraceabilityReport to deterministic Markdown text.

    The output contains an immediate safety notice, summary, coverage matrix,
    traceability edges, data quality, safety flags, manual review, and notes.
    No trading or execution instructions are emitted.
    """
    lines: list[str] = []
    lines.append("# Evidence Traceability Matrix")
    lines.append("")
    lines.append(f"> {_SAFETY_NOTICE}")
    lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **version:** {EVIDENCE_TRACEABILITY_VERSION}")
    lines.append(f"- **state:** {report.state.value}")
    lines.append(f"- **generated_at:** {_iso(report.generated_at)}")
    if report.project_version:
        lines.append(f"- **project_version:** {report.project_version}")
    dq = report.data_quality
    lines.append(f"- **total_items:** {dq.total_items}")
    lines.append(f"- **ok_count:** {dq.ok_count}")
    lines.append(f"- **degraded_count:** {dq.degraded_count}")
    lines.append(f"- **blocked_count:** {dq.blocked_count}")
    lines.append(f"- **not_applicable_count:** {dq.not_applicable_count}")
    lines.append("")

    # Coverage matrix
    lines.append("## Coverage Matrix")
    lines.append("")
    lines.append(
        "| item_id | category | state | coverage_state | reason_code | message |"
    )
    lines.append(
        "|---------|----------|-------|----------------|-------------|---------|"
    )
    coverage_results = [
        r for r in report.results if r.category == "requirement"
    ]
    for result in coverage_results:
        lines.append(
            f"| {_md_value(result.item_id)} | {_md_value(result.category)} | "
            f"{_md_value(result.state.value)} | {_md_value(result.coverage_state.value)} | "
            f"{_md_value(result.reason_code.value)} | {_md_value(result.message)} |"
        )
    if not coverage_results:
        lines.append("| _none_ | | | | | |")
    lines.append("")

    # Traceability edges
    lines.append("## Traceability Edges")
    lines.append("")
    lines.append(
        "| source_id | target_id | link_type | severity | reason_codes | message |"
    )
    lines.append(
        "|-----------|-----------|-----------|--------|--------------|---------|"
    )
    results_map: dict[str, list[EvidenceTraceabilityResult]] = {}
    for result in report.results:
        results_map.setdefault(result.item_id, []).append(result)
    for link in report.links:
        matched = _matching_results(link, results_map)
        state = EvidenceTraceabilityState.OK
        if matched:
            if any(r.state is EvidenceTraceabilityState.BLOCKED for r in matched):
                state = EvidenceTraceabilityState.BLOCKED
            elif any(r.state is EvidenceTraceabilityState.DEGRADED for r in matched):
                state = EvidenceTraceabilityState.DEGRADED
        severity = _severity_str(state)
        reason_codes = "|".join(
            sorted(
                {
                    r.reason_code.value
                    for r in matched
                    if r.reason_code is not EvidenceTraceabilityReasonCode.OK
                }
            )
        )
        messages = [r.message for r in matched if r.message]
        if not messages and link.message:
            messages.append(link.message)
        message = "; ".join(messages)
        lines.append(
            f"| {_md_value(link.source_id)} | {_md_value(link.target_id)} | "
            f"{_md_value(link.link_type.value)} | {_md_value(severity)} | "
            f"{_md_value(reason_codes)} | {_md_value(message)} |"
        )
    if not report.links:
        lines.append("| _none_ | | | | | |")
    lines.append("")

    # Data quality
    lines.append("## Data Quality")
    lines.append("")
    lines.append(f"- **total_items:** {dq.total_items}")
    lines.append(f"- **ok_count:** {dq.ok_count}")
    lines.append(f"- **degraded_count:** {dq.degraded_count}")
    lines.append(f"- **blocked_count:** {dq.blocked_count}")
    lines.append(f"- **not_applicable_count:** {dq.not_applicable_count}")
    lines.append(f"- **requirement_count:** {dq.requirement_count}")
    lines.append(f"- **check_count:** {dq.check_count}")
    lines.append(f"- **artifact_count:** {dq.artifact_count}")
    lines.append(f"- **section_count:** {dq.section_count}")
    lines.append(f"- **link_count:** {dq.link_count}")
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
    manual_review_results = [
        r
        for r in report.results
        if r.reason_code is EvidenceTraceabilityReasonCode.MISSING_MANUAL_REVIEW
    ]
    if manual_review_results:
        for result in manual_review_results:
            lines.append(f"- `{result.item_id}`: {result.message}")
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


def atomic_write_json_evidence_traceability_report(
    report: EvidenceTraceabilityReport,
    path: str | Path | None = None,
) -> Path:
    """Serialize EvidenceTraceabilityReport to JSON and write atomically."""
    target = _coerce_path(path, DEFAULT_JSON_PATH)
    _atomic_write(target, evidence_traceability_report_to_json_text(report))
    return target


def atomic_write_csv_evidence_traceability_report(
    report: EvidenceTraceabilityReport,
    path: str | Path | None = None,
) -> Path:
    """Serialize EvidenceTraceabilityReport links to CSV and write atomically."""
    target = _coerce_path(path, DEFAULT_CSV_PATH)
    _atomic_write(target, evidence_traceability_report_to_csv_text(report))
    return target


def atomic_write_markdown_evidence_traceability_report(
    report: EvidenceTraceabilityReport,
    path: str | Path | None = None,
) -> Path:
    """Serialize EvidenceTraceabilityReport to Markdown and write atomically."""
    target = _coerce_path(path, DEFAULT_MD_PATH)
    _atomic_write(
        target, evidence_traceability_report_to_markdown_text(report) + "\n"
    )
    return target


_DEFAULT_PATH = object()


def write_evidence_traceability_report(
    report: EvidenceTraceabilityReport,
    json_path: str | Path | None | object = _DEFAULT_PATH,
    csv_path: str | Path | None | object = _DEFAULT_PATH,
    md_path: str | Path | None | object = _DEFAULT_PATH,
) -> tuple[Path | None, Path | None, Path | None]:
    """Write EvidenceTraceabilityReport to JSON, CSV, and Markdown as requested.

    Pass None for a format to skip writing that artifact. Default paths are used
    when a path is omitted and the format is written.
    """
    json_out = (
        atomic_write_json_evidence_traceability_report(
            report, None if json_path is _DEFAULT_PATH else json_path
        )
        if json_path is not None
        else None
    )
    csv_out = (
        atomic_write_csv_evidence_traceability_report(
            report, None if csv_path is _DEFAULT_PATH else csv_path
        )
        if csv_path is not None
        else None
    )
    md_out = (
        atomic_write_markdown_evidence_traceability_report(
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
    "atomic_write_csv_evidence_traceability_report",
    "atomic_write_json_evidence_traceability_report",
    "atomic_write_markdown_evidence_traceability_report",
    "evidence_traceability_report_to_csv_text",
    "evidence_traceability_report_to_dict",
    "evidence_traceability_report_to_json_text",
    "evidence_traceability_report_to_markdown_text",
    "write_evidence_traceability_report",
]
