"""Writer for the Portfolio Risk Constraint Evaluator (MVP-58).

Serializes ``ValidatedPortfolioRiskContext`` to JSON, Markdown, and dict forms.
Output is local and audit-only. It never reads from ``data/`` or ``reports/``,
and it never follows, traverses, validates, or executes any file references.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import is_dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any

from hunter.portfolio_risk_evaluator.models import (
    PORTFOLIO_RISK_EVALUATOR_VERSION,
    PortfolioRiskConfig,
    PortfolioRiskError,
    ValidatedPortfolioRiskContext,
)


DEFAULT_JSON_PATH: Path = Path("data/portfolio_risk/latest_risk_validation.json")
DEFAULT_MD_PATH: Path = Path("reports/portfolio_risk/latest_risk_validation.md")

_SAFETY_NOTICE = (
    "This portfolio risk validation context is a human-audit / research-only artifact. "
    "It is not a trading signal, not trade approval, not strategy approval, not execution approval, "
    "not portfolio approval, not universe approval, and not a Freqtrade input or configuration. "
    "It does not emit action commands, suggest orders, create leverage, or create execution instructions. "
    "All pair references are opaque identifiers and are never opened, followed, "
    "traversed, validated, fetched, or executed. "
    "Explicit human approval is required before any downstream use."
)


class PortfolioRiskWriterError(Exception):
    """Base exception for the portfolio risk writer."""


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
    if isinstance(value, Decimal):
        return str(value)
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


def portfolio_risk_context_to_dict(
    context: ValidatedPortfolioRiskContext,
) -> dict[str, Any]:
    """Serialize a ``ValidatedPortfolioRiskContext`` to a deterministic JSON-safe dict."""
    return {
        "version": context.version,
        "source_portfolio_fingerprint": context.source_portfolio_fingerprint,
        "risk_evaluation_fingerprint": context.risk_evaluation_fingerprint,
        "evaluated_at": _iso(context.evaluated_at),
        "accepted": context.accepted,
        "risk_gate_open": context.risk_gate_open,
        "mode": context.mode,
        "research_only": context.research_only,
        "human_approval_required": context.human_approval_required,
        "validated_allocations": [_dataclass_to_dict(a) for a in context.validated_allocations],
        "metrics": _dataclass_to_dict(context.metrics),
        "reason_codes": list(context.reason_codes),
        "metadata": _serialize_value(context.metadata),
        "safety_notice": _SAFETY_NOTICE,
    }


def portfolio_risk_context_to_json_text(
    context: ValidatedPortfolioRiskContext,
    *,
    indent: int | None = 2,
) -> str:
    """Serialize a ``ValidatedPortfolioRiskContext`` to a deterministic JSON string."""
    data = portfolio_risk_context_to_dict(context)
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


def portfolio_risk_context_to_markdown_text(
    context: ValidatedPortfolioRiskContext,
    *,
    json_path: Path | str | None = None,
    markdown_path: Path | str | None = None,
) -> str:
    """Serialize a ``ValidatedPortfolioRiskContext`` to a Markdown string."""
    lines: list[str] = [
        "# Portfolio Risk Validation Context",
        "",
        f"**Version:** {context.version}",
        f"**Evaluated at:** {_iso(context.evaluated_at)}",
        f"**Source portfolio fingerprint:** {context.source_portfolio_fingerprint}",
        f"**Risk evaluation fingerprint:** {context.risk_evaluation_fingerprint}",
        "",
        "## Safety Notice",
        "",
        _SAFETY_NOTICE,
        "",
        "## Summary",
        "",
        f"- **Accepted:** {context.accepted}",
        f"- **Risk gate open:** {context.risk_gate_open}",
        f"- **Mode:** {context.mode}",
        f"- **Research only:** {context.research_only}",
        f"- **Human approval required:** {context.human_approval_required}",
        f"- **Allocation count:** {len(context.validated_allocations)}",
        f"- **Total exposure:** {_format_decimal(context.metrics.total_exposure)}",
        f"- **Largest asset weight:** {_format_decimal(context.metrics.largest_asset_weight)}",
        f"- **Largest cluster exposure:** {_format_decimal(context.metrics.largest_cluster_exposure)}",
        f"- **HHI:** {_format_decimal(context.metrics.hhi)}",
        f"- **Effective asset count:** {_format_decimal(context.metrics.effective_asset_count)}",
        "",
        "## Validated Allocations",
        "",
        "| Pair | Weight | Cluster | Score | Reason |",
        "|------|--------|---------|-------|--------|",
    ]

    if context.validated_allocations:
        for allocation in context.validated_allocations:
            score = _format_decimal(allocation.score) if allocation.score is not None else "-"
            lines.append(
                f"| {allocation.pair} | {_format_decimal(allocation.weight)} | "
                f"{allocation.cluster} | {score} | {allocation.allocation_reason} |"
            )
    else:
        lines.append("_No validated allocations._")

    lines.extend(["", "## Cluster Exposure", ""])
    if context.metrics.cluster_exposure:
        lines.extend(["| Cluster | Exposure |", "|---------|----------|"])
        for cluster, exposure in sorted(context.metrics.cluster_exposure.items()):
            lines.append(f"| {cluster} | {_format_decimal(exposure)} |")
    else:
        lines.append("_No cluster exposure._")

    lines.extend(["", "## Configured Limits", ""])
    limits = context.metadata.get("limits", {})
    if limits:
        lines.append(f"- **Min asset count:** {limits.get('min_asset_count', 'N/A')}")
        lines.append(f"- **Min asset weight:** {limits.get('min_asset_weight', 'N/A')}")
        lines.append(f"- **Max single asset weight:** {limits.get('max_single_asset_weight', 'N/A')}")
        lines.append(f"- **Max total exposure:** {limits.get('max_total_exposure', 'N/A')}")
        lines.append(f"- **Max cluster exposure:** {limits.get('max_cluster_exposure', 'N/A')}")
        lines.append(f"- **Max HHI:** {limits.get('max_hhi', 'N/A')}")
        lines.append(f"- **Exposure tolerance:** {limits.get('exposure_tolerance', 'N/A')}")
    else:
        lines.append("_Limits not recorded._")

    lines.extend(["", "## Reason Codes", ""])
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


def _resolve_path(config: PortfolioRiskConfig, filename_attr: str) -> Path:
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
        raise PortfolioRiskWriterError(f"cannot create directory {path.parent}: {exc}") from exc
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
        raise PortfolioRiskWriterError(f"cannot write {path}: {exc}") from exc
    return path


def write_portfolio_risk_context(
    context: ValidatedPortfolioRiskContext,
    config: PortfolioRiskConfig,
) -> tuple[Path, Path]:
    """Write JSON and Markdown artifacts for ``context``.

    Returns ``(json_path, markdown_path)``.
    """
    json_path = _resolve_path(config, "json_filename")
    markdown_path = _resolve_path(config, "markdown_filename")
    json_text = portfolio_risk_context_to_json_text(context)
    markdown_text = portfolio_risk_context_to_markdown_text(
        context,
        json_path=json_path,
        markdown_path=markdown_path,
    )
    _atomic_write_text(json_path, json_text)
    _atomic_write_text(markdown_path, markdown_text)
    return json_path, markdown_path


def atomic_write_json_portfolio_risk_context(
    context: ValidatedPortfolioRiskContext,
    path: Path | str,
) -> Path:
    """Write the JSON representation of ``context`` to ``path``."""
    return _atomic_write_text(Path(path), portfolio_risk_context_to_json_text(context))


def atomic_write_markdown_portfolio_risk_context(
    context: ValidatedPortfolioRiskContext,
    path: Path | str,
) -> Path:
    """Write the Markdown representation of ``context`` to ``path``."""
    return _atomic_write_text(
        Path(path),
        portfolio_risk_context_to_markdown_text(context, json_path=path),
    )
