"""Writer for the Portfolio Research Adapter (MVP-57).

Serializes ``PortfolioResearchContext`` to JSON, Markdown, and dict forms. Output
is local and audit-only. It never reads from ``data/`` or ``reports/``, and it
never follows, traverses, validates, or executes any file references.
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

from hunter.portfolio_research_adapter.models import (
    PORTFOLIO_RESEARCH_ADAPTER_VERSION,
    PortfolioAllocation,
    PortfolioResearchConfig,
    PortfolioResearchContext,
    PortfolioResearchError,
)


DEFAULT_JSON_PATH: Path = Path("data/portfolio_research/latest_portfolio.json")
DEFAULT_MD_PATH: Path = Path("reports/portfolio_research/latest_portfolio.md")

_SAFETY_NOTICE = (
    "This portfolio research context is a human-audit / research-only artifact. "
    "It is not a trading signal, not trade approval, not strategy approval, not execution approval, "
    "not portfolio approval, not universe approval, and not a Freqtrade input or configuration. "
    "It does not emit action commands, suggest orders, create leverage, or create execution instructions. "
    "All pair references are opaque identifiers and are never opened, followed, "
    "traversed, validated, fetched, or executed. "
    "Explicit human approval is required before any downstream use."
)


class PortfolioResearchWriterError(Exception):
    """Base exception for the portfolio research writer."""


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


def portfolio_research_context_to_dict(
    context: PortfolioResearchContext,
) -> dict[str, Any]:
    """Serialize a ``PortfolioResearchContext`` to a deterministic JSON-safe dict."""
    return {
        "version": context.version,
        "source_context_fingerprint": context.source_context_fingerprint,
        "portfolio_fingerprint": context.portfolio_fingerprint,
        "generated_at": _iso(context.generated_at),
        "mode": context.mode,
        "allocation_method": context.allocation_method,
        "accepted": context.accepted,
        "research_only": context.research_only,
        "human_approval_required": context.human_approval_required,
        "allocations": [_dataclass_to_dict(a) for a in context.allocations],
        "exclusions": [_dataclass_to_dict(e) for e in context.exclusions],
        "cluster_exposure": _serialize_value(context.cluster_exposure),
        "total_exposure": _serialize_value(context.total_exposure),
        "reason_codes": list(context.reason_codes),
        "metadata": _serialize_value(context.metadata),
        "safety_notice": _SAFETY_NOTICE,
    }


def portfolio_research_context_to_json_text(
    context: PortfolioResearchContext,
    *,
    indent: int | None = 2,
) -> str:
    """Serialize a ``PortfolioResearchContext`` to a deterministic JSON string."""
    data = portfolio_research_context_to_dict(context)
    return json.dumps(
        data,
        indent=indent,
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ": ") if indent is None else None,
    )


# ---------------------------------------------------------------------------
# Markdown serialization
# ---------------------------------------------------------------------------


def _format_decimal(value: Any) -> str:
    """Format a Decimal value for Markdown."""
    return str(value)


def portfolio_research_context_to_markdown_text(
    context: PortfolioResearchContext,
    *,
    json_path: Path | str | None = None,
    markdown_path: Path | str | None = None,
) -> str:
    """Serialize a ``PortfolioResearchContext`` to a Markdown string."""
    lines: list[str] = [
        "# Portfolio Research Context",
        "",
        f"**Version:** {context.version}",
        f"**Generated at:** {_iso(context.generated_at)}",
        f"**Source context fingerprint:** {context.source_context_fingerprint}",
        f"**Portfolio fingerprint:** {context.portfolio_fingerprint}",
        "",
        "## Safety Notice",
        "",
        _SAFETY_NOTICE,
        "",
        "## Summary",
        "",
        f"- **Mode:** {context.mode}",
        f"- **Allocation method:** {context.allocation_method}",
        f"- **Accepted:** {context.accepted}",
        f"- **Research only:** {context.research_only}",
        f"- **Human approval required:** {context.human_approval_required}",
        f"- **Total exposure:** {_format_decimal(context.total_exposure)}",
        "",
        "## Allocations",
        "",
        "| Pair | Weight | Cluster | Score | Reason |",
        "|------|--------|---------|-------|--------|",
    ]

    if context.allocations:
        for allocation in context.allocations:
            score = _format_decimal(allocation.score) if allocation.score is not None else "-"
            lines.append(
                f"| {allocation.pair} | {_format_decimal(allocation.weight)} | "
                f"{allocation.cluster} | {score} | {allocation.allocation_reason} |"
            )
    else:
        lines.append("_No allocations._")

    lines.extend(["", "## Exclusions", ""])

    if context.exclusions:
        lines.extend(["| Pair | Reason | Details |", "|------|--------|---------|"])
        for exclusion in context.exclusions:
            lines.append(
                f"| {exclusion.pair} | {exclusion.reason_code} | {exclusion.details} |"
            )
    else:
        lines.append("_No exclusions._")

    lines.extend(["", "## Cluster Exposure", ""])
    if context.cluster_exposure:
        lines.extend(["| Cluster | Exposure |", "|---------|----------|"])
        for cluster, exposure in sorted(context.cluster_exposure.items()):
            lines.append(f"| {cluster} | {_format_decimal(exposure)} |")
    else:
        lines.append("_No cluster exposure._")

    lines.extend(
        [
            "",
            "## Reason Codes",
            "",
        ]
    )
    if context.reason_codes:
        for code in context.reason_codes:
            lines.append(f"- {code}")
    else:
        lines.append("_No reason codes._")

    lines.extend(["", "## Artifacts", ""])
    if json_path is not None:
        lines.append(f"- JSON: `{json_path}`")
    if markdown_path is not None:
        lines.append(f"- Markdown: `{markdown_path}`")

    lines.extend(["", "## Metadata", ""])
    metadata = _serialize_value(context.metadata)
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


def _resolve_path(config: PortfolioResearchConfig, filename_attr: str) -> Path:
    """Resolve a writer path from config attributes."""
    output_dir = config.output_dir
    if filename_attr == "markdown_filename":
        output_dir = config.report_output_dir
    return output_dir / getattr(config, filename_attr)


def _atomic_write_text(path: Path, content: str) -> Path:
    """Write ``content`` to ``path`` atomically via a temporary file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    temp_path.write_text(content, encoding="utf-8")
    os.replace(temp_path, path)
    return path


def write_portfolio_research_context(
    context: PortfolioResearchContext,
    config: PortfolioResearchConfig,
) -> tuple[Path, Path]:
    """Write JSON and Markdown artifacts for ``context``.

    Returns ``(json_path, markdown_path)``.
    """
    json_path = _resolve_path(config, "json_filename")
    markdown_path = _resolve_path(config, "markdown_filename")
    json_text = portfolio_research_context_to_json_text(context)
    markdown_text = portfolio_research_context_to_markdown_text(
        context,
        json_path=json_path,
        markdown_path=markdown_path,
    )
    _atomic_write_text(json_path, json_text)
    _atomic_write_text(markdown_path, markdown_text)
    return json_path, markdown_path


def atomic_write_json_portfolio_research_context(
    context: PortfolioResearchContext,
    path: Path | str,
) -> Path:
    """Write the JSON representation of ``context`` to ``path``."""
    return _atomic_write_text(Path(path), portfolio_research_context_to_json_text(context))


def atomic_write_markdown_portfolio_research_context(
    context: PortfolioResearchContext,
    path: Path | str,
) -> Path:
    """Write the Markdown representation of ``context`` to ``path``."""
    return _atomic_write_text(Path(path), portfolio_research_context_to_markdown_text(context, json_path=path))
