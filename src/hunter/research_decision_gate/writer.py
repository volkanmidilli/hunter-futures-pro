"""Writer for the Research Decision Gate Engine (MVP-59).

Serializes ``ResearchDecisionGateReport`` to JSON, Markdown, and dict forms.
Output is local and audit-only. It never reads from ``data/`` or ``reports/``,
and it never follows, traverses, validates, or executes any file references.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import is_dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any

from hunter.research_decision_gate.models import (
    ResearchDecisionGateConfig,
    ResearchDecisionGateReport,
)

DEFAULT_JSON_PATH: Path = Path("data/research_decision_gate/latest_decision.json")
DEFAULT_MD_PATH: Path = Path("reports/research_decision_gate/latest_decision.md")

_SAFETY_NOTICE = (
    "This research decision gate report is a human-audit / research-only artifact. "
    "It is not a trading signal, not trade approval, not strategy approval, not execution approval, "
    "not portfolio approval, not universe approval, and not a Freqtrade input or configuration. "
    "It does not emit action commands, suggest orders, create leverage, or create execution instructions. "
    "All pair references are opaque identifiers and are never opened, followed, "
    "traversed, validated, fetched, or executed. "
    "Explicit human approval is required before any downstream use."
)


class ResearchDecisionGateWriterError(Exception):
    """Base exception for the research decision gate writer."""


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
    if value is None:
        return None
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (str, bool, int, float)):
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
    return {
        field: _serialize_value(getattr(obj, field))
        for field in obj.__dataclass_fields__
    }


# ---------------------------------------------------------------------------
# Dict / JSON serialization
# ---------------------------------------------------------------------------


def research_decision_gate_report_to_dict(
    report: ResearchDecisionGateReport,
) -> dict[str, Any]:
    """Serialize a ``ResearchDecisionGateReport`` to a deterministic JSON-safe dict."""
    return {
        "version": report.version,
        "decision": report.decision,
        "decision_fingerprint": report.decision_fingerprint,
        "evaluated_at": _iso(report.evaluated_at),
        "research_only": report.research_only,
        "human_approval_required": report.human_approval_required,
        "risk_context_summary": _dataclass_to_dict(report.risk_context_summary),
        "universe_summary": _dataclass_to_dict(report.universe_summary),
        "strategy_contract_summary": _dataclass_to_dict(report.strategy_contract_summary),
        "blocking_reason_codes": list(report.blocking_reason_codes),
        "review_reason_codes": list(report.review_reason_codes),
        "safety_flags": _serialize_value(report.safety_flags),
        "metadata": _serialize_value(report.metadata),
        "safety_notice": _SAFETY_NOTICE,
    }


def research_decision_gate_report_to_json_text(
    report: ResearchDecisionGateReport,
    *,
    indent: int | None = 2,
) -> str:
    """Serialize a ``ResearchDecisionGateReport`` to a deterministic JSON string."""
    data = research_decision_gate_report_to_dict(report)
    return json.dumps(
        data,
        indent=indent,
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":") if indent is None else None,
    )


# ---------------------------------------------------------------------------
# Markdown serialization
# ---------------------------------------------------------------------------


def _format_summary(summary: Any) -> list[str]:
    """Format a ``DecisionSourceSummary`` as Markdown lines."""
    return [
        f"- **Present:** {summary.present}",
        f"- **Accepted:** {summary.accepted}",
        f"- **Fresh:** {summary.fresh}",
        f"- **Fingerprint:** {summary.fingerprint or '_none_'}",
        f"- **Reason codes:** {', '.join(summary.reason_codes) or '_none_'}",
    ]


def research_decision_gate_report_to_markdown_text(
    report: ResearchDecisionGateReport,
    *,
    json_path: Path | str | None = None,
    markdown_path: Path | str | None = None,
) -> str:
    """Serialize a ``ResearchDecisionGateReport`` to a Markdown string."""
    lines: list[str] = [
        "# Research Decision Gate Report",
        "",
        f"**Version:** {report.version}",
        f"**Evaluated at:** {_iso(report.evaluated_at)}",
        f"**Decision:** {report.decision}",
        f"**Decision fingerprint:** `{report.decision_fingerprint}`",
        f"**Research only:** {report.research_only}",
        f"**Human approval required:** {report.human_approval_required}",
        "",
        "## Safety Notice",
        "",
        _SAFETY_NOTICE,
        "",
        "## Source Summaries",
        "",
        "### Risk Context",
    ]
    lines.extend(_format_summary(report.risk_context_summary))
    lines.extend(["", "### Controlled Universe"])
    lines.extend(_format_summary(report.universe_summary))
    lines.extend(["", "### Strategy Contract"])
    lines.extend(_format_summary(report.strategy_contract_summary))

    lines.extend(["", "## Blocking Reason Codes"])
    if report.blocking_reason_codes:
        for code in report.blocking_reason_codes:
            lines.append(f"- {code}")
    else:
        lines.append("_None._")

    lines.extend(["", "## Review Reason Codes"])
    if report.review_reason_codes:
        for code in report.review_reason_codes:
            lines.append(f"- {code}")
    else:
        lines.append("_None._")

    lines.extend(["", "## Safety Flags"])
    for key, value in sorted(report.safety_flags.items()):
        lines.append(f"- {key}: {value}")

    lines.extend(["", "## Artifacts"])
    if json_path is not None:
        lines.append(f"- JSON: `{json_path}`")
    if markdown_path is not None:
        lines.append(f"- Markdown: `{markdown_path}`")

    lines.extend(["", "## Metadata"])
    metadata = _serialize_value(report.metadata)
    if metadata:
        for key, value in sorted(metadata.items()):
            lines.append(f"- {key}: {value}")
    else:
        lines.append("_No metadata._")

    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Atomic file writers
# ---------------------------------------------------------------------------


def _resolve_path(config: ResearchDecisionGateConfig, filename_attr: str) -> Path:
    """Resolve a writer path from config attributes."""
    output_dir = config.output_dir
    if filename_attr == "markdown_filename":
        output_dir = config.report_output_dir
    return output_dir / getattr(config, filename_attr)


def _atomic_write_text(path: Path, content: str) -> Path:
    """Write ``content`` to ``path`` atomically via a temporary file."""
    path = Path(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ResearchDecisionGateWriterError(
            f"cannot create directory {path.parent}: {exc}"
        ) from exc
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    try:
        temp_path.write_text(content, encoding="utf-8")
        os.replace(temp_path, path)
    except OSError as exc:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
        raise ResearchDecisionGateWriterError(f"cannot write {path}: {exc}") from exc
    return path


def write_research_decision_gate_report(
    report: ResearchDecisionGateReport,
    config: ResearchDecisionGateConfig,
) -> tuple[Path, Path]:
    """Write JSON and Markdown artifacts for ``report``.

    Returns ``(json_path, markdown_path)``.
    """
    json_path = _resolve_path(config, "json_filename")
    markdown_path = _resolve_path(config, "markdown_filename")
    json_text = research_decision_gate_report_to_json_text(report)
    markdown_text = research_decision_gate_report_to_markdown_text(
        report,
        json_path=json_path,
        markdown_path=markdown_path,
    )
    _atomic_write_text(json_path, json_text)
    _atomic_write_text(markdown_path, markdown_text)
    return json_path, markdown_path


def atomic_write_json_research_decision_gate_report(
    report: ResearchDecisionGateReport,
    path: Path | str,
) -> Path:
    """Write the JSON representation of ``report`` to ``path``."""
    return _atomic_write_text(
        Path(path), research_decision_gate_report_to_json_text(report)
    )


def atomic_write_markdown_research_decision_gate_report(
    report: ResearchDecisionGateReport,
    path: Path | str,
) -> Path:
    """Write the Markdown representation of ``report`` to ``path``."""
    return _atomic_write_text(
        Path(path),
        research_decision_gate_report_to_markdown_text(report, json_path=path),
    )
