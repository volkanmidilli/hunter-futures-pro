"""Writer for the Freqtrade Universe Consumption Adapter (MVP-55).

Serializes `FreqtradeUniverseAdapterResult` to deterministic JSON, Markdown, and
dict forms. Output is local and audit-only. It never reads from `data/` or
`reports/`, and it never follows, traverses, validates, or executes any file
references.
"""

from __future__ import annotations

import json
import os
from dataclasses import is_dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from hunter.freqtrade_universe_adapter.models import (
    FreqtradeUniverseAdapterConfig,
    FreqtradeUniverseAdapterResult,
)


_SAFETY_NOTICE = (
    "This Freqtrade universe adapter output is a human-audit / research-only artifact. "
    "It is not a trading signal, not trade approval, not strategy approval, not execution approval, "
    "not portfolio approval, not universe approval, and not a Freqtrade input or configuration that enables any action. "
    "It does not emit action commands, suggest orders, or create execution instructions. "
    "All pair references are opaque identifiers and are never opened, followed, "
    "traversed, validated, fetched, or executed. "
    "Explicit human approval is required before any downstream use."
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
    return {field: _serialize_value(getattr(obj, field)) for field in obj.__dataclass_fields__}


# ---------------------------------------------------------------------------
# Dict / JSON serialization
# ---------------------------------------------------------------------------


def freqtrade_universe_adapter_result_to_dict(
    result: FreqtradeUniverseAdapterResult,
) -> dict[str, Any]:
    """Convert a FreqtradeUniverseAdapterResult to a deterministic dictionary."""
    return {
        "kind": "freqtrade_universe_adapter",
        "version": result.version,
        "safety_notice": _SAFETY_NOTICE,
        "report_id": result.report_id,
        "generated_at": _iso(result.generated_at),
        "research_only": result.research_only,
        "human_approval_required": result.human_approval_required,
        "whitelist": list(result.whitelist),
        "blacklist": list(result.blacklist),
        "pairlist": _serialize_value(result.pairlist),
        "strategy_contract_input": _serialize_value(result.strategy_contract_input),
        "per_pair_summary": [_dataclass_to_dict(s) for s in result.per_pair_summary],
        "reason_codes": list(result.reason_codes),
        "safety_flags": _serialize_value(result.safety_flags),
        "metadata": _serialize_value(result.metadata),
    }


def freqtrade_universe_adapter_result_to_json_text(
    result: FreqtradeUniverseAdapterResult,
    *,
    indent: int = 2,
) -> str:
    """Serialize a FreqtradeUniverseAdapterResult to deterministic JSON text."""
    data = freqtrade_universe_adapter_result_to_dict(result)
    return json.dumps(data, indent=indent, ensure_ascii=False, sort_keys=True) + "\n"


def _pairlist_to_json_text(
    result: FreqtradeUniverseAdapterResult,
    *,
    indent: int = 2,
) -> str:
    """Serialize the pairlist fragment to deterministic JSON text."""
    return (
        json.dumps(
            _serialize_value(result.pairlist),
            indent=indent,
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n"
    )


def _strategy_contract_input_to_json_text(
    result: FreqtradeUniverseAdapterResult,
    *,
    indent: int = 2,
) -> str:
    """Serialize the strategy-contract input to deterministic JSON text."""
    return (
        json.dumps(
            _serialize_value(result.strategy_contract_input),
            indent=indent,
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n"
    )


# ---------------------------------------------------------------------------
# Markdown serialization
# ---------------------------------------------------------------------------


def _md_value(value: Any) -> str:
    """Stringify a value for Markdown, escaping pipe characters."""
    if value is None:
        return ""
    return str(value).replace("|", "\\|")


def freqtrade_universe_adapter_result_to_markdown_text(
    result: FreqtradeUniverseAdapterResult,
) -> str:
    """Serialize a FreqtradeUniverseAdapterResult to deterministic Markdown text."""
    lines: list[str] = []
    lines.append("# Freqtrade Universe Adapter Output")
    lines.append("")
    lines.append(f"> {_SAFETY_NOTICE}")
    lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **version:** {result.version}")
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

    lines.append("## Pairlist Fragment")
    lines.append("")
    lines.append(f"```json")
    lines.append(json.dumps(_serialize_value(result.pairlist), indent=2, ensure_ascii=False, sort_keys=True))
    lines.append(f"```")
    lines.append("")

    lines.append("## Strategy Contract Input")
    lines.append("")
    lines.append(f"```json")
    lines.append(json.dumps(_serialize_value(result.strategy_contract_input), indent=2, ensure_ascii=False, sort_keys=True))
    lines.append(f"```")
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

    lines.append("## Artifact Paths")
    lines.append("")
    lines.append(f"- `{FreqtradeUniverseAdapterConfig.output_dir}/{FreqtradeUniverseAdapterConfig.json_filename}`")
    lines.append(f"- `{FreqtradeUniverseAdapterConfig.markdown_output_dir}/{FreqtradeUniverseAdapterConfig.markdown_filename}`")
    lines.append(f"- `{FreqtradeUniverseAdapterConfig.output_dir}/{FreqtradeUniverseAdapterConfig.pairlist_filename}`")
    lines.append(f"- `{FreqtradeUniverseAdapterConfig.output_dir}/{FreqtradeUniverseAdapterConfig.strategy_contract_input_filename}`")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Atomic writes
# ---------------------------------------------------------------------------


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


def atomic_write_json_freqtrade_universe_adapter_result(
    result: FreqtradeUniverseAdapterResult,
    path: str,
) -> None:
    """Atomically write a result as JSON to the given path."""
    _atomic_write(Path(path), freqtrade_universe_adapter_result_to_json_text(result))


def atomic_write_markdown_freqtrade_universe_adapter_result(
    result: FreqtradeUniverseAdapterResult,
    path: str,
) -> None:
    """Atomically write a result as Markdown to the given path."""
    _atomic_write(Path(path), freqtrade_universe_adapter_result_to_markdown_text(result))


# ---------------------------------------------------------------------------
# High-level write
# ---------------------------------------------------------------------------


def write_freqtrade_universe_adapter_result(
    result: FreqtradeUniverseAdapterResult,
    output_dir: str | None,
    config: FreqtradeUniverseAdapterConfig,
) -> dict[str, str]:
    """Write all enabled artifacts for the adapter result.

    Writes four artifacts: JSON packet, Markdown summary, pairlist fragment, and
    strategy-contract input. All data artifacts go to ``output_dir`` (if given)
    or ``config.output_dir``; Markdown goes to ``config.markdown_output_dir``.

    If ``output_dir`` is provided, it overrides ``config.output_dir`` for the
    JSON, pairlist, and strategy-contract artifacts; ``config.markdown_output_dir``
    is still used for Markdown. If a config filename is empty, that artifact is
    skipped.

    Returns a mapping of artifact key to written path.
    """
    data_dir = Path(output_dir) if output_dir else Path(config.output_dir)
    md_dir = Path(config.markdown_output_dir)
    written: dict[str, str] = {}

    if config.json_filename:
        json_path = data_dir / config.json_filename
        atomic_write_json_freqtrade_universe_adapter_result(result, str(json_path))
        written["json"] = str(json_path)

    if config.markdown_filename:
        md_path = md_dir / config.markdown_filename
        atomic_write_markdown_freqtrade_universe_adapter_result(result, str(md_path))
        written["markdown"] = str(md_path)

    if config.pairlist_filename:
        pairlist_path = data_dir / config.pairlist_filename
        _atomic_write(pairlist_path, _pairlist_to_json_text(result))
        written["pairlist"] = str(pairlist_path)

    if config.strategy_contract_input_filename:
        sci_path = data_dir / config.strategy_contract_input_filename
        _atomic_write(sci_path, _strategy_contract_input_to_json_text(result))
        written["strategy_contract_input"] = str(sci_path)

    return written
