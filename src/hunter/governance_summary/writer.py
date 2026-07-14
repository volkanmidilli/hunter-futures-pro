"""Writer for the Governance Decision Summary Aggregator (MVP-61).

Serializes ``GovernanceDecisionSummary`` to JSON, Markdown, and dict forms.
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

from hunter.governance_summary.models import (
    GovernanceDecisionSummary,
    GovernanceSummaryConfig,
)

DEFAULT_JSON_PATH: Path = Path("data/governance_summary/latest_governance_summary.json")
DEFAULT_MD_PATH: Path = Path("reports/governance_summary/latest_governance_summary.md")

_SAFETY_NOTICE = (
    "This governance decision summary is a human-audit / research-only artifact. "
    "READY_FOR_RESEARCH_HANDOFF is not execution approval, not production readiness, "
    "not trade approval, not strategy approval, not portfolio approval, not universe approval, "
    "and not a Freqtrade input or configuration. "
    "It does not emit action commands, suggest orders, create leverage, or create execution instructions. "
    "All artifact references are opaque identifiers and are never opened, followed, "
    "traversed, validated, fetched, or executed. "
    "Explicit human review and approval are required before any downstream use."
)


class GovernanceSummaryWriterError(Exception):
    """Base exception for the governance summary writer."""


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


def governance_decision_summary_to_dict(
    summary: GovernanceDecisionSummary,
) -> dict[str, Any]:
    """Serialize a ``GovernanceDecisionSummary`` to a deterministic JSON-safe dict."""
    return {
        "version": summary.version,
        "governance_status": summary.governance_status,
        "governance_fingerprint": summary.governance_fingerprint,
        "evaluated_at": _iso(summary.evaluated_at),
        "gate_decision": summary.gate_decision,
        "gate_decision_fingerprint": summary.gate_decision_fingerprint,
        "review_summary": _dataclass_to_dict(summary.review_summary),
        "blocking_reason_codes": list(summary.blocking_reason_codes),
        "review_reason_codes": list(summary.review_reason_codes),
        "research_only": summary.research_only,
        "human_review_required": summary.human_review_required,
        "execution_approval_granted": summary.execution_approval_granted,
        "metadata": _serialize_value(summary.metadata),
        "safety_notice": _SAFETY_NOTICE,
    }


def governance_decision_summary_to_json_text(
    summary: GovernanceDecisionSummary,
    *,
    indent: int | None = 2,
) -> str:
    """Serialize a ``GovernanceDecisionSummary`` to a deterministic JSON string."""
    data = governance_decision_summary_to_dict(summary)
    return json.dumps(
        data,
        indent=indent,
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":") if indent is None else None,
    )


def governance_decision_summary_to_markdown_text(
    summary: GovernanceDecisionSummary,
    *,
    json_path: Path | str | None = None,
    markdown_path: Path | str | None = None,
) -> str:
    """Serialize a ``GovernanceDecisionSummary`` to a Markdown string."""
    review = summary.review_summary
    lines: list[str] = [
        "# Governance Decision Summary",
        "",
        f"**Version:** {summary.version}",
        f"**Evaluated at:** {_iso(summary.evaluated_at)}",
        f"**Governance status:** `{summary.governance_status}`",
        f"**Governance fingerprint:** `{summary.governance_fingerprint}`",
        f"**Gate decision:** {summary.gate_decision}",
        f"**Gate decision fingerprint:** `{summary.gate_decision_fingerprint}`",
        f"**Research only:** {summary.research_only}",
        f"**Human review required:** {summary.human_review_required}",
        f"**Execution approval granted:** {summary.execution_approval_granted}",
        "",
        "## Safety Notice",
        "",
        _SAFETY_NOTICE,
        "",
        "## Review Summary",
        "",
        f"- **Total records:** {review.total_records}",
        f"- **Accepted records:** {review.accepted_records}",
        f"- **Rejected attempts:** {review.rejected_attempts}",
        f"- **Chain valid:** {review.chain_valid}",
        f"- **Latest accepted record fingerprint:** {review.latest_accepted_record_fingerprint or '_none_'}",
        f"- **Latest reviewer identity:** {review.latest_reviewer_identity or '_none_'}",
        f"- **Latest reviewer decision:** {review.latest_reviewer_decision or '_none_'}",
        f"- **Latest review created at:** {_iso(review.latest_review_created_at) if review.latest_review_created_at else '_none_'}",
        f"- **Open change request count:** {review.open_change_request_count}",
        f"- **Source decision fingerprints:** {', '.join(review.source_decision_fingerprints) or '_none_'}",
        "",
        "## Blocking Reason Codes",
    ]
    if summary.blocking_reason_codes:
        for code in summary.blocking_reason_codes:
            lines.append(f"- {code}")
    else:
        lines.append("_None._")

    lines.extend(["", "## Review-Required Reason Codes"])
    if summary.review_reason_codes:
        for code in summary.review_reason_codes:
            lines.append(f"- {code}")
    else:
        lines.append("_None._")

    lines.extend(["", "## Artifacts"])
    if json_path is not None:
        lines.append(f"- JSON: `{json_path}`")
    if markdown_path is not None:
        lines.append(f"- Markdown: `{markdown_path}`")

    lines.extend(["", "## Metadata"])
    metadata = _serialize_value(summary.metadata)
    if metadata:
        for key, value in sorted(metadata.items()):
            lines.append(f"- {key}: {value}")
    else:
        lines.append("_No metadata._")

    lines.append("")
    return "\n".join(lines)


def _resolve_path(config: GovernanceSummaryConfig, filename_attr: str) -> Path:
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
        raise GovernanceSummaryWriterError(
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
        raise GovernanceSummaryWriterError(f"cannot write {path}: {exc}") from exc
    return path


def write_governance_decision_summary(
    summary: GovernanceDecisionSummary,
    config: GovernanceSummaryConfig,
) -> tuple[Path, Path]:
    """Write JSON and Markdown artifacts for ``summary``.

    Returns ``(json_path, markdown_path)``.
    """
    json_path = _resolve_path(config, "json_filename")
    markdown_path = _resolve_path(config, "markdown_filename")
    json_text = governance_decision_summary_to_json_text(summary)
    markdown_text = governance_decision_summary_to_markdown_text(
        summary,
        json_path=json_path,
        markdown_path=markdown_path,
    )
    _atomic_write_text(json_path, json_text)
    _atomic_write_text(markdown_path, markdown_text)
    return json_path, markdown_path


def atomic_write_json_governance_decision_summary(
    summary: GovernanceDecisionSummary,
    path: Path | str,
) -> Path:
    """Write the JSON representation of ``summary`` to ``path``."""
    return _atomic_write_text(
        Path(path), governance_decision_summary_to_json_text(summary)
    )


def atomic_write_markdown_governance_decision_summary(
    summary: GovernanceDecisionSummary,
    path: Path | str,
) -> Path:
    """Write the Markdown representation of ``summary`` to ``path``."""
    return _atomic_write_text(
        Path(path),
        governance_decision_summary_to_markdown_text(summary, json_path=path),
    )


__all__ = [
    "governance_decision_summary_to_dict",
    "governance_decision_summary_to_json_text",
    "governance_decision_summary_to_markdown_text",
    "write_governance_decision_summary",
    "atomic_write_json_governance_decision_summary",
    "atomic_write_markdown_governance_decision_summary",
]
