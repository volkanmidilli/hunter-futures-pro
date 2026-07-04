"""Writer for hunter.release_hardening package.

MVP-33 — Local Research Release Hardening / Consistency Audit.

Deterministic JSON, CSV, and Markdown serialization for ReleaseHardeningReport
with atomic writes. Output is a human-audit / research-only artifact. It is not
a trading signal, not trade approval, not strategy approval, not execution
approval, not portfolio approval, not universe approval, and not a certification
of trading readiness. It does not emit action commands, suggest orders, or create
execution instructions. File references and metadata strings are serialized as
opaque strings only; they are never opened, traversed, validated, followed, or
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

from hunter.release_hardening.models import (
    RELEASE_HARDENING_VERSION,
    ReleaseHardeningConfig,
    ReleaseHardeningReport,
    ReleaseHardeningSafetyFlags,
    ReleaseHardeningState,
)

# Default local artifact paths. These are explicit, local, and never remote.
DEFAULT_JSON_PATH: Path = Path("data/release_hardening/release_hardening.json")
DEFAULT_CSV_PATH: Path = Path("data/release_hardening/release_hardening_checks.csv")
DEFAULT_MD_PATH: Path = Path("reports/release_hardening/release_hardening.md")

_SAFETY_NOTICE = (
    "This report is a human-audit research artifact. It is not trading advice, "
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
    if isinstance(obj, ReleaseHardeningSafetyFlags):
        result["is_safe"] = obj.is_safe
    return result


# ---------------------------------------------------------------------------
# Dict / JSON serialization
# ---------------------------------------------------------------------------


def release_hardening_report_to_dict(report: ReleaseHardeningReport) -> dict[str, Any]:
    """Convert a ReleaseHardeningReport to a deterministic dictionary.

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


def release_hardening_report_to_json_text(report: ReleaseHardeningReport) -> str:
    """Serialize a ReleaseHardeningReport to deterministic JSON text."""
    data = release_hardening_report_to_dict(report)
    return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=False) + "\n"


# ---------------------------------------------------------------------------
# CSV serialization
# ---------------------------------------------------------------------------


_CSV_COLUMNS = (
    "report_id",
    "generated_at",
    "check_id",
    "package_id",
    "category",
    "state",
    "severity",
    "reason_codes",
    "message",
)


def _report_id(report: ReleaseHardeningReport) -> str:
    """Return a deterministic report identifier derived from generated_at."""
    return f"release-hardening-{_iso(report.generated_at)}"


def _derive_severity(state: ReleaseHardeningState) -> str:
    """Derive a severity label from the check result state."""
    if state is ReleaseHardeningState.BLOCKED:
        return "blocking"
    if state is ReleaseHardeningState.DEGRADED:
        return "advisory"
    if state is ReleaseHardeningState.NOT_APPLICABLE:
        return "not_applicable"
    return "advisory"


def release_hardening_report_to_csv_text(report: ReleaseHardeningReport) -> str:
    """Serialize check results to deterministic CSV text.

    One row per ReleaseHardeningCheckResult. Report-level metadata is repeated
    on each row so the CSV is a self-contained denormalized view.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(_CSV_COLUMNS)
    generated_at = _iso(report.generated_at)
    report_id = _report_id(report)
    for result in report.checks:
        row = [
            report_id,
            generated_at,
            result.check_id,
            result.package_id or "",
            result.category,
            result.state.value,
            _derive_severity(result.state),
            result.reason_code.value,
            result.message,
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


def release_hardening_report_to_markdown_text(
    report: ReleaseHardeningReport,
) -> str:
    """Serialize a ReleaseHardeningReport to deterministic Markdown text.

    The output contains a safety notice at the top, summary, data quality,
    checks by category, safety flags, reason codes, and notes. No trading or
    execution instructions are emitted.
    """
    lines: list[str] = []
    lines.append("# Release Hardening Report")
    lines.append("")
    lines.append(f"> {_SAFETY_NOTICE}")
    lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **version:** {RELEASE_HARDENING_VERSION}")
    lines.append(f"- **state:** {report.state.value}")
    lines.append(f"- **generated_at:** {_iso(report.generated_at)}")
    if report.project_version:
        lines.append(f"- **project_version:** {report.project_version}")
    dq = report.data_quality
    lines.append(f"- **total_checks:** {dq.total_checks}")
    lines.append(f"- **pass_count:** {dq.pass_count}")
    lines.append(f"- **degraded_count:** {dq.degraded_count}")
    lines.append(f"- **blocked_count:** {dq.blocked_count}")
    lines.append(f"- **not_applicable_count:** {dq.not_applicable_count}")
    lines.append("")

    # Data quality
    lines.append("## Data Quality")
    lines.append("")
    lines.append(f"- **total_checks:** {dq.total_checks}")
    lines.append(f"- **pass_count:** {dq.pass_count}")
    lines.append(f"- **degraded_count:** {dq.degraded_count}")
    lines.append(f"- **blocked_count:** {dq.blocked_count}")
    lines.append(f"- **not_applicable_count:** {dq.not_applicable_count}")
    lines.append(f"- **package_count:** {dq.package_count}")
    lines.append(f"- **completed_package_count:** {dq.completed_package_count}")
    if dq.notes:
        lines.append("")
        lines.append("### Notes")
        lines.append("")
        for note in dq.notes:
            lines.append(f"- {note}")
    lines.append("")

    # Checks by category
    lines.append("## Checks by Category")
    lines.append("")
    lines.append(
        "| check_id | category | package_id | state | severity | reason_code | message |"
    )
    lines.append(
        "|----------|----------|------------|-------|----------|-------------|---------|"
    )
    for result in report.checks:
        lines.append(
            f"| {_md_value(result.check_id)} | {_md_value(result.category)} | "
            f"{_md_value(result.package_id)} | {_md_value(result.state.value)} | "
            f"{_md_value(_derive_severity(result.state))} | "
            f"{_md_value(result.reason_code.value)} | {_md_value(result.message)} |"
        )
    if not report.checks:
        lines.append("| _none_ | | | | | | |")
    lines.append("")

    # Safety flags
    lines.append("## Safety Flags")
    lines.append("")
    lines.append("| Flag | Value |")
    lines.append("|------|-------|")
    for key, value in sorted(_dataclass_to_dict(report.safety_flags).items()):
        lines.append(f"| {_md_value(key)} | {_md_value(value)} |")
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


def atomic_write_json_release_hardening_report(
    report: ReleaseHardeningReport,
    path: str | Path | None = None,
) -> Path:
    """Serialize ReleaseHardeningReport to JSON and write atomically."""
    target = _coerce_path(path, DEFAULT_JSON_PATH)
    _atomic_write(target, release_hardening_report_to_json_text(report))
    return target


def atomic_write_csv_release_hardening_report(
    report: ReleaseHardeningReport,
    path: str | Path | None = None,
) -> Path:
    """Serialize ReleaseHardeningReport check results to CSV and write atomically."""
    target = _coerce_path(path, DEFAULT_CSV_PATH)
    _atomic_write(target, release_hardening_report_to_csv_text(report))
    return target


def atomic_write_markdown_release_hardening_report(
    report: ReleaseHardeningReport,
    path: str | Path | None = None,
) -> Path:
    """Serialize ReleaseHardeningReport to Markdown and write atomically."""
    target = _coerce_path(path, DEFAULT_MD_PATH)
    _atomic_write(target, release_hardening_report_to_markdown_text(report) + "\n")
    return target


_DEFAULT_PATH = object()


def write_release_hardening_report(
    report: ReleaseHardeningReport,
    json_path: str | Path | None | object = _DEFAULT_PATH,
    csv_path: str | Path | None | object = _DEFAULT_PATH,
    md_path: str | Path | None | object = _DEFAULT_PATH,
) -> tuple[Path | None, Path | None, Path | None]:
    """Write ReleaseHardeningReport to JSON, CSV, and Markdown as requested.

    Pass None for a format to skip writing that artifact. Default paths are used
    when a path is omitted and the format is written.
    """
    json_out = (
        atomic_write_json_release_hardening_report(
            report, None if json_path is _DEFAULT_PATH else json_path
        )
        if json_path is not None
        else None
    )
    csv_out = (
        atomic_write_csv_release_hardening_report(
            report, None if csv_path is _DEFAULT_PATH else csv_path
        )
        if csv_path is not None
        else None
    )
    md_out = (
        atomic_write_markdown_release_hardening_report(
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
    "atomic_write_csv_release_hardening_report",
    "atomic_write_json_release_hardening_report",
    "atomic_write_markdown_release_hardening_report",
    "release_hardening_report_to_csv_text",
    "release_hardening_report_to_dict",
    "release_hardening_report_to_json_text",
    "release_hardening_report_to_markdown_text",
    "write_release_hardening_report",
]
