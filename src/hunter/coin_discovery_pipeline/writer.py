"""Writer for the one-call coin-discovery pipeline runner (MVP-54 Step 3).

Serializes `CoinDiscoveryPipelineResult` to deterministic JSON, Markdown, and dict
forms. All output is local and audit-only. It never reads from `data/` or `reports/`,
and it never follows, traverses, validates, or executes any file references.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from hunter.coin_discovery_pipeline.models import (
    CoinDiscoveryPipelineConfig,
    CoinDiscoveryPipelineError,
    CoinDiscoveryPipelineResult,
    CoinDiscoveryPipelineSafetyFlags,
    PipelineState,
)
from hunter.controlled_universe_export_adapter.models import (
    ControlledUniverseExportResult,
)
from hunter.run_orchestrator.models import ResearchRunResult


DEFAULT_JSON_PATH = Path("data/coin_discovery_pipeline/latest/pipeline.json")
DEFAULT_MD_PATH = Path("reports/coin_discovery_pipeline/latest/pipeline.md")

_SAFETY_NOTICE = (
    "This coin-discovery pipeline result is a human-audit / research-only artifact. "
    "It is not a trading signal, not trade approval, not strategy approval, not execution approval, "
    "not portfolio approval, not universe approval, and not a Freqtrade input or configuration. "
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
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, datetime):
        return _iso(value)
    if isinstance(value, (list, tuple)):
        return [_serialize_value(v) for v in value]
    if isinstance(value, (dict, Mapping)):
        return {str(k): _serialize_value(v) for k, v in sorted(value.items())}
    return str(value)


# ---------------------------------------------------------------------------
# Dict serialization
# ---------------------------------------------------------------------------


def _safety_flags_to_dict(flags: CoinDiscoveryPipelineSafetyFlags) -> dict[str, Any]:
    """Serialize pipeline safety flags to a JSON-safe dict."""
    return {
        "research_only": flags.research_only,
        "human_approval_required": flags.human_approval_required,
        "no_freqtrade_runtime_connection": flags.no_freqtrade_runtime_connection,
        "no_automatic_config_mutation": flags.no_automatic_config_mutation,
        "no_network_connection": flags.no_network_connection,
        "no_exchange_connection": flags.no_exchange_connection,
        "no_database": flags.no_database,
        "no_scheduler": flags.no_scheduler,
        "no_action_commands_emitted": flags.no_action_commands_emitted,
    }


def _run_result_summary_to_dict(run_result: ResearchRunResult | None) -> dict[str, Any] | None:
    """Serialize a concise summary of a ResearchRunResult."""
    if run_result is None:
        return None
    return {
        "run_id": run_result.run_id,
        "state": run_result.state.value,
        "version": run_result.config.project_version,
        "generated_at": _iso(run_result.generated_at),
        "step_count": len(run_result.steps),
        "reason_codes": list(run_result.reason_codes),
        "notes": list(run_result.notes),
    }


def _export_result_summary_to_dict(
    export_result: ControlledUniverseExportResult | None,
) -> dict[str, Any] | None:
    """Serialize a concise summary of a ControlledUniverseExportResult."""
    if export_result is None:
        return None
    return {
        "report_id": export_result.report_id,
        "generated_at": _iso(export_result.generated_at),
        "whitelist": list(export_result.whitelist),
        "blacklist": list(export_result.blacklist),
        "per_pair_summary_count": len(export_result.per_pair_summary),
        "research_only": export_result.research_only,
        "human_approval_required": export_result.human_approval_required,
        "reason_codes": list(export_result.reason_codes),
    }


def coin_discovery_pipeline_result_to_dict(
    result: CoinDiscoveryPipelineResult,
) -> dict[str, Any]:
    """Convert a CoinDiscoveryPipelineResult to a deterministic dictionary."""
    if not isinstance(result, CoinDiscoveryPipelineResult):
        raise CoinDiscoveryPipelineError(
            f"result must be a CoinDiscoveryPipelineResult, got {result!r}"
        )
    data: dict[str, Any] = {
        "kind": "coin_discovery_pipeline_result",
        "version": result.version,
        "safety_notice": _SAFETY_NOTICE,
        "run_id": result.run_id,
        "state": result.state.value,
        "safety_flags": _safety_flags_to_dict(result.safety_flags),
        "reason_codes": list(result.reason_codes),
        "export_paths": list(result.export_paths),
        "pipeline_paths": list(result.pipeline_paths),
        "run_summary": _run_result_summary_to_dict(result.run_result),
        "export_summary": _export_result_summary_to_dict(result.export_result),
        "metadata": _serialize_value(result.metadata),
    }
    return data


def coin_discovery_pipeline_result_to_json_text(
    result: CoinDiscoveryPipelineResult,
    *,
    indent: int = 2,
) -> str:
    """Serialize a CoinDiscoveryPipelineResult to deterministic JSON text."""
    data = coin_discovery_pipeline_result_to_dict(result)
    return json.dumps(data, indent=indent, ensure_ascii=False, sort_keys=True) + "\n"


# ---------------------------------------------------------------------------
# Markdown serialization
# ---------------------------------------------------------------------------


def _md_value(value: Any) -> str:
    """Stringify a value for Markdown, escaping pipe characters."""
    if value is None:
        return ""
    return str(value).replace("|", "\\|")


def coin_discovery_pipeline_result_to_markdown_text(
    result: CoinDiscoveryPipelineResult,
) -> str:
    """Serialize a CoinDiscoveryPipelineResult to deterministic Markdown text."""
    lines: list[str] = []
    lines.append("# Coin Discovery Pipeline Result")
    lines.append("")
    lines.append(f"> {_SAFETY_NOTICE}")
    lines.append("")

    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **version:** {result.version}")
    lines.append(f"- **run_id:** {_md_value(result.run_id)}")
    lines.append(f"- **state:** {_md_value(result.state.value)}")
    lines.append("")

    if result.run_result is not None:
        run = result.run_result
        lines.append("## Run Summary")
        lines.append("")
        lines.append(f"- **run_id:** {_md_value(run.run_id)}")
        lines.append(f"- **state:** {_md_value(run.state.value)}")
        lines.append(f"- **version:** {_md_value(run.config.project_version)}")
        lines.append(f"- **generated_at:** {_iso(run.generated_at)}")
        lines.append(f"- **step_count:** {len(run.steps)}")
        lines.append("")

    if result.export_result is not None:
        exp = result.export_result
        lines.append("## Export Summary")
        lines.append("")
        lines.append(f"- **report_id:** {_md_value(exp.report_id)}")
        lines.append(f"- **generated_at:** {_iso(exp.generated_at)}")
        lines.append(f"- **whitelist_count:** {len(exp.whitelist)}")
        lines.append(f"- **blacklist_count:** {len(exp.blacklist)}")
        lines.append(f"- **per_pair_summary_count:** {len(exp.per_pair_summary)}")
        lines.append(f"- **research_only:** {exp.research_only}")
        lines.append(f"- **human_approval_required:** {exp.human_approval_required}")
        lines.append("")
        lines.append("### Whitelist")
        lines.append("")
        if exp.whitelist:
            for pair in exp.whitelist:
                lines.append(f"- {pair}")
        else:
            lines.append("- _empty_")
        lines.append("")
        lines.append("### Blacklist")
        lines.append("")
        if exp.blacklist:
            for pair in exp.blacklist:
                lines.append(f"- {pair}")
        else:
            lines.append("- _empty_")
        lines.append("")

    lines.append("## Safety Flags")
    lines.append("")
    for key, value in sorted(_safety_flags_to_dict(result.safety_flags).items()):
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

    if result.export_paths or result.pipeline_paths:
        lines.append("## Artifact Paths")
        lines.append("")
        if result.export_paths:
            lines.append("### Export Paths")
            lines.append("")
            for path in result.export_paths:
                lines.append(f"- {_md_value(path)}")
            lines.append("")
        if result.pipeline_paths:
            lines.append("### Pipeline Paths")
            lines.append("")
            for path in result.pipeline_paths:
                lines.append(f"- {_md_value(path)}")
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


def _validate_result_type(result: Any) -> None:
    """Raise CoinDiscoveryPipelineError if result is not the expected type."""
    if not isinstance(result, CoinDiscoveryPipelineResult):
        raise CoinDiscoveryPipelineError(
            f"result must be a CoinDiscoveryPipelineResult, got {result!r}"
        )


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


def atomic_write_json_coin_discovery_pipeline_result(
    result: CoinDiscoveryPipelineResult,
    path: str | Path | None = None,
) -> Path:
    """Write a CoinDiscoveryPipelineResult JSON packet atomically."""
    _validate_result_type(result)
    target = _coerce_path(path, DEFAULT_JSON_PATH)
    _atomic_write(target, coin_discovery_pipeline_result_to_json_text(result))
    return target


def atomic_write_markdown_coin_discovery_pipeline_result(
    result: CoinDiscoveryPipelineResult,
    path: str | Path | None = None,
) -> Path:
    """Write a CoinDiscoveryPipelineResult Markdown packet atomically."""
    _validate_result_type(result)
    target = _coerce_path(path, DEFAULT_MD_PATH)
    _atomic_write(target, coin_discovery_pipeline_result_to_markdown_text(result))
    return target


def write_coin_discovery_pipeline_result(
    result: CoinDiscoveryPipelineResult,
    config: CoinDiscoveryPipelineConfig,
) -> tuple[str, ...]:
    """Write pipeline result artifacts to local paths derived from config.

    Writes JSON to ``<config.output_dir>/<run_id>/pipeline.json`` and Markdown to
    ``reports/<pkg_name>/<run_id>/pipeline.md`` where ``pkg_name`` is the last
    path component of ``config.output_dir`` (defaulting to
    ``coin_discovery_pipeline``).  Returns the written paths as strings.
    """
    if not isinstance(config, CoinDiscoveryPipelineConfig):
        raise CoinDiscoveryPipelineError(
            f"config must be a CoinDiscoveryPipelineConfig, got {config!r}"
        )
    _validate_result_type(result)
    base = Path(config.output_dir)
    run_id = result.run_id
    pkg_name = base.name or "coin_discovery_pipeline"
    json_path = base / run_id / "pipeline.json"
    md_path = Path("reports") / pkg_name / run_id / "pipeline.md"
    atomic_write_json_coin_discovery_pipeline_result(result, json_path)
    atomic_write_markdown_coin_discovery_pipeline_result(result, md_path)
    return (str(json_path), str(md_path))
