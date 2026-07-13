"""Writer for the Controlled Universe Export Adapter (MVP-53).

Serializes `ControlledUniverseExportResult` to JSON, Markdown, and dict forms.
Output is local and audit-only. It never reads from `data/` or `reports/`, and it
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

from hunter.controlled_universe_export_adapter.models import (
    CONTROLLED_UNIVERSE_EXPORT_VERSION,
    ControlledUniverseExportConfig,
    ControlledUniverseExportResult,
    ControlledUniversePairExportSummary,
)


DEFAULT_JSON_PATH: Path = Path("data/controlled_universe_export/latest_export.json")
DEFAULT_MD_PATH: Path = Path("reports/controlled_universe_export/latest_export.md")

_SAFETY_NOTICE = (
    "This controlled universe export is a human-audit / research-only artifact. "
    "It is not a trading signal, not trade approval, not strategy approval, not execution approval, "
    "not portfolio approval, not universe approval, and not a Freqtrade input or configuration. "
    "It does not emit action commands, suggest orders, or create execution instructions. "
    "All pair references are opaque identifiers and are never opened, followed, "
    "traversed, validated, fetched, or executed. "
    "Explicit human approval is required before any downstream use."
)


class ControlledUniverseExportWriterError(Exception):
    """Base exception for the controlled universe export writer."""


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
# Dict / JSON serialization
# ---------------------------------------------------------------------------


def _pair_summary_to_dict(summary: ControlledUniversePairExportSummary) -> dict[str, Any]:
    """Serialize a per-pair summary to a JSON-safe dict."""
    return _dataclass_to_dict(summary)


def controlled_universe_export_to_dict(result: ControlledUniverseExportResult) -> dict[str, Any]:
    """Convert a ControlledUniverseExportResult to a deterministic dictionary."""
    data: dict[str, Any] = {
        "kind": "controlled_universe_export",
        "version": CONTROLLED_UNIVERSE_EXPORT_VERSION,
        "safety_notice": _SAFETY_NOTICE,
        "report_id": result.report_id,
        "generated_at": _iso(result.generated_at),
        "research_only": result.research_only,
        "human_approval_required": result.human_approval_required,
        "whitelist": list(result.whitelist),
        "blacklist": list(result.blacklist),
        "per_pair_summary": [_pair_summary_to_dict(s) for s in result.per_pair_summary],
        "reason_codes": list(result.reason_codes),
        "safety_flags": _serialize_value(result.safety_flags),
        "metadata": _serialize_value(result.metadata),
    }
    return data


def controlled_universe_export_to_json_text(
    result: ControlledUniverseExportResult,
    *,
    indent: int = 2,
) -> str:
    """Serialize a ControlledUniverseExportResult to deterministic JSON text."""
    data = controlled_universe_export_to_dict(result)
    return json.dumps(data, indent=indent, ensure_ascii=False, sort_keys=True) + "\n"


# ---------------------------------------------------------------------------
# Markdown serialization
# ---------------------------------------------------------------------------


def _md_value(value: Any) -> str:
    """Stringify a value for Markdown, escaping pipe characters."""
    if value is None:
        return ""
    return str(value).replace("|", "\\|")


def controlled_universe_export_to_markdown_text(
    result: ControlledUniverseExportResult,
) -> str:
    """Serialize a ControlledUniverseExportResult to deterministic Markdown text."""
    lines: list[str] = []
    lines.append("# Controlled Universe Export")
    lines.append("")
    lines.append(f"> {_SAFETY_NOTICE}")
    lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **version:** {CONTROLLED_UNIVERSE_EXPORT_VERSION}")
    lines.append(f"- **report_id:** {_md_value(result.report_id)}")
    lines.append(f"- **generated_at:** {_iso(result.generated_at)}")
    lines.append(f"- **research_only:** {result.research_only}")
    lines.append(f"- **human_approval_required:** {result.human_approval_required}")
    lines.append(f"- **whitelist_count:** {len(result.whitelist)}")
    lines.append(f"- **blacklist_count:** {len(result.blacklist)}")
    lines.append("")

    lines.append("## Whitelist")
    lines.append("")
    if result.whitelist:
        for pair in result.whitelist:
            lines.append(f"- {pair}")
    else:
        lines.append("- _empty_")
    lines.append("")

    lines.append("## Blacklist")
    lines.append("")
    if result.blacklist:
        for pair in result.blacklist:
            lines.append(f"- {pair}")
    else:
        lines.append("- _empty_")
    lines.append("")

    lines.append("## Per-Pair Summary")
    lines.append("")
    lines.append("| pair | state | classification | reason_codes | human_note |")
    lines.append("|------|-------|----------------|--------------|------------|")
    for summary in result.per_pair_summary:
        lines.append(
            f"| {_md_value(summary.pair)} | {_md_value(summary.state)} | "
            f"{_md_value(summary.classification)} | "
            f"{_md_value(';'.join(summary.reason_codes))} | "
            f"{_md_value(summary.human_note)} |"
        )
    if not result.per_pair_summary:
        lines.append("| _none_ | | | | |")
    lines.append("")

    lines.append("## Safety Flags")
    lines.append("")
    for key, value in sorted(result.safety_flags.items()):
        lines.append(f"- **{key}:** {value}")
    lines.append("")

    lines.append("## Reason Codes")
    lines.append("")
    if result.reason_codes:
        for code in result.reason_codes:
            lines.append(f"- {code}")
    else:
        lines.append("- _none_")
    lines.append("")

    if result.metadata:
        lines.append("## Metadata")
        lines.append("")
        for key, value in sorted(result.metadata.items()):
            lines.append(f"- **{key}:** {_md_value(value)}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Atomic writes
# ---------------------------------------------------------------------------


def _coerce_path(value: str | Path | None, default: Path) -> Path:
    """Return a Path for the given value, falling back to the default."""
    if value is None:
        return default
    if isinstance(value, Path):
        return value
    return Path(value)


def _atomic_write(path: Path, content: str) -> None:
    """Write content atomically via temp file and os.replace."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(content, encoding="utf-8")
        os.replace(tmp, path)
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise


def atomic_write_json_controlled_universe_export(
    result: ControlledUniverseExportResult,
    path: str | Path | None = None,
) -> Path:
    """Write a JSON controlled universe export atomically."""
    target = _coerce_path(path, DEFAULT_JSON_PATH)
    _atomic_write(target, controlled_universe_export_to_json_text(result))
    return target


def atomic_write_markdown_controlled_universe_export(
    result: ControlledUniverseExportResult,
    path: str | Path | None = None,
) -> Path:
    """Write a Markdown controlled universe export atomically."""
    target = _coerce_path(path, DEFAULT_MD_PATH)
    _atomic_write(target, controlled_universe_export_to_markdown_text(result))
    return target


def write_controlled_universe_export(
    result: ControlledUniverseExportResult,
    output_dir: str | Path | None = None,
    config: ControlledUniverseExportConfig | None = None,
) -> tuple[Path | None, Path | None]:
    """Write ControlledUniverseExportResult to JSON and Markdown as requested.

    The output directory is taken from the config if not provided explicitly.
    Both JSON and Markdown filenames are taken from the config. Returns the
    JSON path and Markdown path that were written. If a config filename is
    empty, that format is skipped.
    """
    cfg = config or ControlledUniverseExportConfig.default()
    out_dir = Path(output_dir) if output_dir else Path(cfg.output_dir)
    md_dir = Path(cfg.markdown_output_dir)

    json_path: Path | None = None
    if cfg.json_filename:
        json_path = out_dir / cfg.json_filename
        atomic_write_json_controlled_universe_export(result, json_path)

    md_path: Path | None = None
    if cfg.markdown_filename:
        md_path = md_dir / cfg.markdown_filename
        atomic_write_markdown_controlled_universe_export(result, md_path)

    return json_path, md_path
