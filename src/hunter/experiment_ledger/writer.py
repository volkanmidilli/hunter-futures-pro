"""Writer for hunter.experiment_ledger package. MVP-31 — Local Research Experiment Ledger. Serializes ExperimentLedgerReport to deterministic local JSON, CSV, and Markdown artifacts. Does not read, follow, traverse, validate, fetch, or execute any file references or metadata strings. All paths are constructed explicitly and are local only."""

from __future__ import annotations

import csv
import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any

from hunter.experiment_ledger.models import (
    COMPARABLE_METRICS,
    EXPERIMENT_LEDGER_VERSION,
    RUN_RESULT_METRICS,
    ExperimentComparisonConfig,
    ExperimentComparisonResult,
    ExperimentLedgerDataQuality,
    ExperimentLedgerInput,
    ExperimentLedgerReport,
    ExperimentLedgerSafetyFlags,
    ExperimentMetricSnapshot,
    ExperimentRecord,
    ExperimentReasonCode,
    ExperimentState,
)

# Default local artifact paths. These are explicit, local, and never remote.
DEFAULT_JSON_PATH: Path = Path("data/experiment_ledger/experiment_ledger.json")
DEFAULT_CSV_PATH: Path = Path("data/experiment_ledger/experiment_records.csv")
DEFAULT_MD_PATH: Path = Path("reports/experiment_ledger/experiment_ledger.md")


# ---------------------------------------------------------------------------
# Dict / JSON serialization
# ---------------------------------------------------------------------------


def _serialize_value(value: Any) -> Any:
    """Recursively serialize a value to JSON-safe primitives."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (MappingProxyType, Mapping)):
        return {_serialize_value(k): _serialize_value(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [_serialize_value(v) for v in value]
    if isinstance(value, frozenset):
        return sorted(_serialize_value(v) for v in value)
    if isinstance(value, set):
        return sorted(_serialize_value(v) for v in value)
    if is_dataclass(value) and not isinstance(value, type):
        return _dataclass_to_dict(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    # Fallback for objects not handled above.
    return str(value)


def _dataclass_to_dict(obj: Any) -> dict[str, Any]:
    """Convert a frozen dataclass to a deterministic JSON-safe dict."""
    if not is_dataclass(obj) or isinstance(obj, type):
        raise TypeError(f"expected dataclass instance, got {type(obj)}")
    result: dict[str, Any] = {}
    for field in obj.__dataclass_fields__:
        value = getattr(obj, field)
        result[field] = _serialize_value(value)
    if isinstance(obj, ExperimentLedgerSafetyFlags):
        result["is_safe"] = obj.is_safe
    return result


def experiment_ledger_report_to_dict(report: ExperimentLedgerReport) -> dict[str, Any]:
    """Convert an ExperimentLedgerReport to a deterministic dictionary."""
    return _dataclass_to_dict(report)


def experiment_ledger_report_to_json_text(report: ExperimentLedgerReport) -> str:
    """Serialize an ExperimentLedgerReport to deterministic JSON text."""
    data = experiment_ledger_report_to_dict(report)
    return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


# ---------------------------------------------------------------------------
# CSV serialization
# ---------------------------------------------------------------------------


def _metric_value(value: float | int | None) -> str:
    """Serialize a metric value to a CSV cell."""
    if value is None:
        return ""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return str(value)


def _delta_columns(deltas: Mapping[str, Mapping[str, Any]]) -> tuple[str, ...]:
    """Return a deterministic tuple of delta_<metric> column names present."""
    names: set[str] = set()
    for record_deltas in deltas.values():
        for metric_name in record_deltas:
            if metric_name in COMPARABLE_METRICS:
                names.add(metric_name)
    return tuple(sorted(names))


def experiment_ledger_report_to_csv_text(report: ExperimentLedgerReport) -> str:
    """Serialize an ExperimentLedgerReport to deterministic CSV text.

    One row per ranked experiment record with exact deterministic columns.
    """
    delta_names = _delta_columns(report.comparison.deltas)
    header = [
        "report_id",
        "generated_at",
        "rank",
        "experiment_id",
        "source_kind",
        "run_id",
        "name",
        "state",
        "primary_metric",
    ]
    header.extend(COMPARABLE_METRICS)
    header.extend(RUN_RESULT_METRICS)
    header.extend(f"delta_{name}" for name in delta_names)
    header.extend([
        "reason_codes",
        "tags",
    ])

    rows: list[list[str]] = []
    primary_metric = report.comparison.config.primary_metric
    for rank, record in enumerate(report.comparison.ranked_records, start=1):
        row = [
            report.report_id,
            report.generated_at.isoformat(),
            str(rank),
            record.experiment_id,
            record.source_kind,
            record.run_id,
            record.name,
            record.state.value,
            primary_metric,
        ]
        for metric_name in COMPARABLE_METRICS:
            row.append(_metric_value(record.metrics.get(metric_name)))
        for metric_name in RUN_RESULT_METRICS:
            row.append(_metric_value(record.metrics.get(metric_name)))
        record_deltas = report.comparison.deltas.get(record.experiment_id, {})
        for metric_name in delta_names:
            row.append(_metric_value(record_deltas.get(metric_name)))
        row.append(";".join(str(rc) for rc in record.reason_codes))
        row.append(";".join(str(tag) for tag in record.tags))
        rows.append(row)

    lines: list[str] = []
    # Use csv.writer to handle escaping correctly.
    from io import StringIO
    buffer = StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Markdown serialization
# ---------------------------------------------------------------------------


def _escape_pipe(text: str) -> str:
    """Escape pipe characters in Markdown table cells."""
    return text.replace("|", "\\|")


def _format_value(value: Any) -> str:
    """Format a value for Markdown display."""
    if value is None:
        return ""
    if isinstance(value, Enum):
        return str(value.value)
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _metric_row(
    record: ExperimentRecord,
    primary_metric: str,
    delta_names: tuple[str, ...],
    deltas: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    """Build a Markdown table row for a record."""
    cells = [
        _escape_pipe(record.experiment_id),
        _escape_pipe(record.run_id),
        _escape_pipe(record.name),
        _escape_pipe(record.source_kind),
        _escape_pipe(record.state.value),
        _escape_pipe(_format_value(record.metrics.get(primary_metric))),
    ]
    for metric_name in COMPARABLE_METRICS:
        cells.append(_escape_pipe(_format_value(record.metrics.get(metric_name))))
    record_deltas = deltas.get(record.experiment_id, {})
    for metric_name in delta_names:
        cells.append(_escape_pipe(_format_value(record_deltas.get(metric_name))))
    cells.append(_escape_pipe(";".join(str(rc) for rc in record.reason_codes)))
    cells.append(_escape_pipe(";".join(str(tag) for tag in record.tags)))
    return cells


def experiment_ledger_report_to_markdown_text(report: ExperimentLedgerReport) -> str:
    """Serialize an ExperimentLedgerReport to deterministic Markdown text.

    The output contains a safety notice at the top, summary, ranked records,
    baseline deltas, data quality, and safety flags. No trading or execution
    instructions are emitted.
    """
    lines: list[str] = []
    lines.append("# Experiment Ledger Report")
    lines.append("")
    lines.append(
        "> **Safety notice:** This report is for human audit and research review only. "
        "It is not a recommendation or trading signal. "
        "Rankings are for audit-review only and do not constitute "
        "advice or a strategy decision."
    )
    lines.append("")

    # Report identity
    lines.append("## Report Identity")
    lines.append("")
    lines.append(f"- **report_id:** {report.report_id}")
    lines.append(f"- **version:** {report.version}")
    lines.append(f"- **generated_at:** {report.generated_at.isoformat()}")
    lines.append("")

    # Comparison summary
    comparison = report.comparison
    config = comparison.config
    primary_metric = config.primary_metric
    lines.append("## Comparison Summary")
    lines.append("")
    lines.append(f"- **baseline_experiment_id:** {_format_value(config.baseline_experiment_id)}")
    lines.append(f"- **primary_metric:** {primary_metric}")
    lines.append(f"- **ranked_records:** {len(comparison.ranked_records)}")
    lines.append(f"- **include_blocked:** {config.include_blocked}")
    lines.append(f"- **include_insufficient:** {config.include_insufficient}")
    if comparison.baseline_record is not None:
        lines.append(
            f"- **baseline_record:** {comparison.baseline_record.experiment_id}"
        )
    else:
        lines.append("- **baseline_record:** None")
    if comparison.reason_codes:
        lines.append(f"- **reason_codes:** {', '.join(str(rc) for rc in comparison.reason_codes)}")
    lines.append("")

    # Summary metrics
    if comparison.summary_metrics:
        lines.append("### Summary Metrics")
        lines.append("")
        lines.append("| metric | value |")
        lines.append("|--------|-------|")
        for metric_name in sorted(comparison.summary_metrics):
            value = comparison.summary_metrics[metric_name]
            lines.append(
                f"| {_escape_pipe(metric_name)} | {_escape_pipe(_format_value(value))} |"
            )
        lines.append("")

    # Ranked records
    lines.append("## Ranked Experiment Records")
    lines.append("")
    lines.append(
        "Records are ranked for audit-review only. Missing the configured "
        f"primary metric (`{primary_metric}`) places a record after all records "
        "that have the metric."
    )
    lines.append("")
    delta_names = _delta_columns(comparison.deltas)
    record_header = [
        "rank",
        "experiment_id",
        "run_id",
        "name",
        "source_kind",
        "state",
        primary_metric,
    ]
    record_header.extend(COMPARABLE_METRICS)
    record_header.extend(f"delta_{name}" for name in delta_names)
    record_header.extend(["reason_codes", "tags"])
    lines.append("| " + " | ".join(record_header) + " |")
    lines.append("| " + " | ".join("---" for _ in record_header) + " |")
    for rank, record in enumerate(comparison.ranked_records, start=1):
        cells = [str(rank)] + _metric_row(record, primary_metric, delta_names, comparison.deltas)
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")

    # Baseline / Deltas
    if comparison.baseline_record is not None or comparison.deltas:
        lines.append("## Baseline and Deltas")
        lines.append("")
        if comparison.baseline_record is not None:
            lines.append(
                f"Baseline: `{comparison.baseline_record.experiment_id}`"
            )
        else:
            lines.append("No baseline record found.")
        if comparison.deltas:
            lines.append("")
            lines.append("| experiment_id | metric | delta |")
            lines.append("|---------------|--------|-------|")
            for experiment_id in sorted(comparison.deltas):
                record_deltas = comparison.deltas[experiment_id]
                for metric_name in sorted(record_deltas):
                    value = record_deltas[metric_name]
                    lines.append(
                        f"| {_escape_pipe(experiment_id)} | {_escape_pipe(metric_name)} | "
                        f"{_escape_pipe(_format_value(value))} |"
                    )
        lines.append("")

    # Data quality
    dq = report.data_quality
    lines.append("## Data Quality")
    lines.append("")
    lines.append(f"- **total_inputs:** {dq.total_inputs}")
    lines.append(f"- **normalized_records:** {dq.normalized_records}")
    lines.append(f"- **included_records:** {dq.included_records}")
    lines.append(f"- **insufficient_records:** {dq.insufficient_records}")
    lines.append(f"- **excluded_records:** {dq.excluded_records}")
    lines.append(f"- **blocked_records:** {dq.blocked_records}")
    if dq.sections_present:
        lines.append(f"- **sections_present:** {', '.join(dq.sections_present)}")
    if dq.sections_expected:
        lines.append(f"- **sections_expected:** {', '.join(dq.sections_expected)}")
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
    lines.append(f"- **is_safe:** {report.safety_flags.is_safe}")
    lines.append(f"- **has_unsafe_content:** {report.safety_flags.has_unsafe_content}")
    lines.append(f"- **has_invalid_record:** {report.safety_flags.has_invalid_record}")
    lines.append(f"- **has_blocked_record:** {report.safety_flags.has_blocked_record}")
    lines.append(f"- **has_insufficient_data:** {report.safety_flags.has_insufficient_data}")
    lines.append(f"- **has_missing_baseline:** {report.safety_flags.has_missing_baseline}")
    lines.append("")

    # Report reason codes
    if report.reason_codes:
        lines.append("## Reason Codes")
        lines.append("")
        for code in report.reason_codes:
            lines.append(f"- {code}")
        lines.append("")

    # Metadata
    if report.metadata:
        lines.append("## Metadata")
        lines.append("")
        for key, value in sorted(report.metadata.items()):
            lines.append(f"- **{_escape_pipe(key)}:** {_escape_pipe(value)}")
        lines.append("")

    # Notes
    all_notes = list(report.notes) + list(comparison.notes)
    if all_notes:
        lines.append("## Notes")
        lines.append("")
        for note in all_notes:
            lines.append(f"- {note}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Atomic file writes
# ---------------------------------------------------------------------------


def _ensure_parent_dir(path: Path) -> None:
    """Create the parent directory for a path with restrictive permissions."""
    parent = path.parent
    if parent:
        parent.mkdir(parents=True, exist_ok=True)
        os.chmod(parent, 0o700)


def _atomic_write(path: Path, content: str) -> Path:
    """Write content to path atomically via a temporary file."""
    _ensure_parent_dir(path)
    tmp = path.with_suffix(f"{path.suffix}.tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.rename(path)
    os.chmod(path, 0o600)
    return path


def atomic_write_json_experiment_ledger_report(
    report: ExperimentLedgerReport, path: Path | None = None
) -> Path:
    """Write the report as JSON to the specified path."""
    target = path or DEFAULT_JSON_PATH
    content = experiment_ledger_report_to_json_text(report)
    return _atomic_write(target, content)


def atomic_write_csv_experiment_ledger_report(
    report: ExperimentLedgerReport, path: Path | None = None
) -> Path:
    """Write the ranked experiment records as CSV to the specified path."""
    target = path or DEFAULT_CSV_PATH
    content = experiment_ledger_report_to_csv_text(report)
    return _atomic_write(target, content)


def atomic_write_markdown_experiment_ledger_report(
    report: ExperimentLedgerReport, path: Path | None = None
) -> Path:
    """Write the report as Markdown to the specified path."""
    target = path or DEFAULT_MD_PATH
    content = experiment_ledger_report_to_markdown_text(report)
    return _atomic_write(target, content)


def write_experiment_ledger_report(
    report: ExperimentLedgerReport,
    json_path: Path | None = DEFAULT_JSON_PATH,
    csv_path: Path | None = DEFAULT_CSV_PATH,
    md_path: Path | None = DEFAULT_MD_PATH,
) -> tuple[Path | None, Path | None, Path | None]:
    """Write JSON, CSV, and Markdown artifacts for the report.

    Pass None for any artifact to skip writing it. Defaults are explicit local
    paths under data/ and reports/.
    """
    json_result = atomic_write_json_experiment_ledger_report(report, json_path) if json_path is not None else None
    csv_result = atomic_write_csv_experiment_ledger_report(report, csv_path) if csv_path is not None else None
    md_result = atomic_write_markdown_experiment_ledger_report(report, md_path) if md_path is not None else None
    return json_result, csv_result, md_result
