"""Deterministic writers for research market data (MVP-63 / SPEC-064)."""

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

from hunter.research_market_data.errors import ResearchMarketDataWriterError
from hunter.research_market_data.models import (
    ResearchMarketDataBundle,
    ResearchMarketDataConfig,
    ResearchMarketDataManifest,
)

DEFAULT_JSON_PATH: Path = Path("data/research_market_data/latest_bundle.json")
DEFAULT_MD_PATH: Path = Path("reports/research_market_data/latest_bundle.md")

_SAFETY_NOTICE = (
    "This research market data bundle is a human-audit / research-only artifact. "
    "It is not a trading signal, not trade approval, not strategy approval, not execution approval, "
    "not portfolio approval, not universe approval, and not a Freqtrade input or configuration. "
    "It does not emit action commands, suggest orders, create leverage, or create execution instructions. "
    "All market data inputs are caller-provided and read-only; this writer does not access ``data/`` "
    "or ``reports/`` as input sources. "
    "Explicit human approval is required before any downstream use."
)


class ResearchMarketDataBundleWriterError(ResearchMarketDataWriterError):
    """Base exception for the research market data writer."""


def _iso(value: datetime) -> str:
    """Serialize a timezone-aware datetime to ISO-8601 with UTC suffix."""
    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def _canonical_decimal(value: Decimal) -> str:
    """Return a deterministic string representation of a Decimal."""
    return format(value, "f")


def _serialize_value(value: Any) -> Any:
    """Recursively serialize a value to JSON-safe deterministic types."""
    if value is None:
        return None
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return round(value, 12) if value == value else None  # type: ignore[comparison-overlap]
    if isinstance(value, Decimal):
        return _canonical_decimal(value)
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
    if isinstance(value, Path):
        return value.name
    return str(value)


def _dataclass_to_dict(obj: Any) -> dict[str, Any]:
    """Convert a frozen dataclass instance to a deterministic JSON-safe dict."""
    if not is_dataclass(obj) or isinstance(obj, type):
        raise TypeError(f"expected dataclass instance, got {type(obj)}")
    return {
        field: _serialize_value(getattr(obj, field))
        for field in obj.__dataclass_fields__
    }


def _config_to_dict(config: ResearchMarketDataConfig) -> dict[str, Any]:
    """Serialize a ``ResearchMarketDataConfig`` to a deterministic dict."""
    return {
        "coverage_threshold": _canonical_decimal(config.coverage_threshold),
        "min_required_rows": config.min_required_rows,
        "lookback_days": list(config.lookback_days),
        "required_quote_currency": config.required_quote_currency,
        "safety_flags": _serialize_value(config.safety_flags),
        "metadata": _serialize_value(config.metadata),
    }


def _manifest_to_dict(manifest: ResearchMarketDataManifest) -> dict[str, Any]:
    """Serialize a ``ResearchMarketDataManifest`` to a deterministic dict."""
    return {
        "schema_version": manifest.schema_version,
        "generated_at": _iso(manifest.generated_at),
        "sources": [_dataclass_to_dict(s) for s in manifest.sources],
        "series_fingerprints": _serialize_value(manifest.series_fingerprints),
        "btc_fingerprint": manifest.btc_fingerprint,
        "eth_fingerprint": manifest.eth_fingerprint,
        "policy_fingerprint": manifest.policy_fingerprint,
        "bundle_fingerprint": manifest.bundle_fingerprint,
        "safety_flags": _serialize_value(manifest.safety_flags),
        "metadata": _serialize_value(manifest.metadata),
        "reason_codes": list(manifest.reason_codes),
    }


def research_market_data_bundle_to_dict(
    bundle: ResearchMarketDataBundle,
) -> dict[str, Any]:
    """Serialize a ``ResearchMarketDataBundle`` to a deterministic JSON-safe dict."""
    return {
        "version": bundle.config.__class__.__module__.split(".")[-2],
        "schema_version": bundle.manifest.schema_version,
        "generated_at": _iso(bundle.manifest.generated_at),
        "research_only": bundle.safety_flags.research_only,
        "execution_approval_granted": bundle.safety_flags.execution_approval_granted,
        "production_approval_granted": bundle.safety_flags.production_approval_granted,
        "live_trading_allowed": bundle.safety_flags.live_trading_allowed,
        "automatic_execution_allowed": bundle.safety_flags.automatic_execution_allowed,
        "safety_notice": _SAFETY_NOTICE,
        "config": _config_to_dict(bundle.config),
        "manifest": _manifest_to_dict(bundle.manifest),
        "candidates": [_dataclass_to_dict(s) for s in bundle.candidates],
        "btc_series": _dataclass_to_dict(bundle.btc_series),
        "eth_series": _dataclass_to_dict(bundle.eth_series) if bundle.eth_series is not None else None,
        "exclusions": [_dataclass_to_dict(e) for e in bundle.exclusions],
        "reason_codes": list(bundle.reason_codes),
        "metadata": _serialize_value(bundle.metadata),
    }


def research_market_data_bundle_to_json_text(
    bundle: ResearchMarketDataBundle,
    *,
    indent: int | None = 2,
) -> str:
    """Serialize a ``ResearchMarketDataBundle`` to a deterministic JSON string."""
    data = research_market_data_bundle_to_dict(bundle)
    return json.dumps(
        data,
        indent=indent,
        sort_keys=True,
        ensure_ascii=True,
        separators=(",", ":") if indent is None else None,
    )


def _format_missing_interval(interval: Any) -> str:
    return (
        f"{interval.start} -> {interval.end} "
        f"(expected {interval.expected_count}, actual {interval.actual_count})"
    )


def research_market_data_bundle_to_markdown_text(
    bundle: ResearchMarketDataBundle,
) -> str:
    """Serialize a ``ResearchMarketDataBundle`` to a Markdown string."""
    lines = [
        "# Research Market Data Bundle",
        "",
        f"**Schema version:** {bundle.manifest.schema_version}",
        f"**Generated at:** {_iso(bundle.manifest.generated_at)}",
        f"**Bundle fingerprint:** `{bundle.manifest.bundle_fingerprint}`",
        "",
        "## Safety Notice",
        "",
        _SAFETY_NOTICE,
        "",
        "## Safety Invariants",
        "",
        f"- research_only: {bundle.safety_flags.research_only}",
        f"- execution_approval_granted: {bundle.safety_flags.execution_approval_granted}",
        f"- production_approval_granted: {bundle.safety_flags.production_approval_granted}",
        f"- live_trading_allowed: {bundle.safety_flags.live_trading_allowed}",
        f"- automatic_execution_allowed: {bundle.safety_flags.automatic_execution_allowed}",
        "",
        "## Candidates",
        "",
    ]
    for series in bundle.candidates:
        lines.append(f"### {series.pair}")
        lines.append(f"- Timeframe: {series.timeframe}")
        lines.append(f"- Candles: {len(series.candles)}")
        lines.append(f"- Coverage: {series.coverage}")
        lines.append(f"- Source: {series.source.path.name}")
        lines.append(f"- Fingerprint: `{bundle.manifest.series_fingerprints.get(series.pair, '_none_')}`")
        if series.missing_intervals:
            lines.append("- Missing intervals:")
            for interval in series.missing_intervals:
                lines.append(f"  - {_format_missing_interval(interval)}")
        lines.append("")
    lines.append("## Benchmarks")
    lines.append("")
    lines.append(f"- BTC: {bundle.btc_series.pair} ({len(bundle.btc_series.candles)} candles)")
    if bundle.eth_series is not None:
        lines.append(f"- ETH: {bundle.eth_series.pair} ({len(bundle.eth_series.candles)} candles)")
    else:
        lines.append("- ETH: not provided (BTC-only mode)")
    lines.append("")
    lines.append("## Exclusions")
    lines.append("")
    if bundle.exclusions:
        for exclusion in bundle.exclusions:
            lines.append(
                f"- {exclusion.source.path.name}: {', '.join(exclusion.reason_codes)} — {exclusion.message}"
            )
    else:
        lines.append("_none_")
    lines.append("")
    lines.append("## Reason Codes")
    lines.append("")
    lines.append(", ".join(bundle.reason_codes) or "_none_")
    lines.append("")
    return "\n".join(lines)


def _atomic_write(path: Path, content: str) -> None:
    """Write ``content`` to ``path`` atomically via a temporary file."""
    path = path.resolve()
    if not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        temp_path.write_text(content, encoding="utf-8")
        os.replace(temp_path, path)
    except Exception as exc:
        if temp_path.exists():
            temp_path.unlink()
        raise ResearchMarketDataBundleWriterError(
            "WRITE_FAILED", f"failed to write {path}: {exc}"
        ) from exc


def write_research_market_data_bundle(
    bundle: ResearchMarketDataBundle,
    *,
    json_path: Path | str | None = None,
    markdown_path: Path | str | None = None,
    overwrite: bool = False,
) -> tuple[Path, Path]:
    """Write a ``ResearchMarketDataBundle`` to JSON and Markdown artifacts.

    Raises ``ResearchMarketDataBundleWriterError`` if the target exists and
    ``overwrite`` is not True, or if the write fails.
    """
    json_path = Path(json_path or DEFAULT_JSON_PATH)
    markdown_path = Path(markdown_path or DEFAULT_MD_PATH)

    if not overwrite:
        for target in (json_path, markdown_path):
            if target.exists():
                raise ResearchMarketDataBundleWriterError(
                    "FILE_EXISTS",
                    f"refusing to overwrite existing file: {target}",
                )

    json_text = research_market_data_bundle_to_json_text(bundle)
    markdown_text = research_market_data_bundle_to_markdown_text(bundle)

    _atomic_write(json_path, json_text)
    _atomic_write(markdown_path, markdown_text)

    return json_path, markdown_path


def atomic_write_json_research_market_data_bundle(
    bundle: ResearchMarketDataBundle,
    path: Path | str,
    *,
    overwrite: bool = False,
) -> Path:
    """Write only the JSON artifact atomically."""
    path = Path(path)
    if not overwrite and path.exists():
        raise ResearchMarketDataBundleWriterError(
            "FILE_EXISTS", f"refusing to overwrite existing file: {path}"
        )
    _atomic_write(path, research_market_data_bundle_to_json_text(bundle))
    return path


def atomic_write_markdown_research_market_data_bundle(
    bundle: ResearchMarketDataBundle,
    path: Path | str,
    *,
    overwrite: bool = False,
) -> Path:
    """Write only the Markdown artifact atomically."""
    path = Path(path)
    if not overwrite and path.exists():
        raise ResearchMarketDataBundleWriterError(
            "FILE_EXISTS", f"refusing to overwrite existing file: {path}"
        )
    _atomic_write(path, research_market_data_bundle_to_markdown_text(bundle))
    return path
