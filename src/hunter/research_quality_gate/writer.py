"""Writer for hunter.research_quality_gate package.

Deterministic JSON and Markdown serialization for ResearchQualityGate with
atomic writes. Output is human-audit only; no file references are traversed,
opened, followed, validated, or executed here.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from hunter.research_quality_gate.models import (
    QUALITY_GATE_VERSION,
    QualityGateCheck,
    QualityGateCheckKind,
    QualityGateConfig,
    QualityGateDataQuality,
    QualityGateSafetyFlags,
    QualityGateState,
    QualityGateSummary,
    QualityGateVerdict,
    ResearchQualityGate,
)


DEFAULT_QUALITY_GATE_JSON_PATH = Path(
    "data/research_quality_gate/latest_research_quality_gate.json"
)
DEFAULT_QUALITY_GATE_MARKDOWN_PATH = Path(
    "reports/research_quality_gate/latest_research_quality_gate.md"
)


# ---------------------------------------------------------------------------
# Value helpers
# ---------------------------------------------------------------------------


def _iso(value: datetime) -> str:
    """Return ISO-8601 string for a timezone-aware datetime."""
    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def _serialize_value(value: Any) -> Any:
    """Serialize a value to JSON-safe deterministic types."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return _iso(value)
    if isinstance(value, tuple):
        return [_serialize_value(v) for v in value]
    if isinstance(value, list):
        return [_serialize_value(v) for v in value]
    if isinstance(value, Mapping):
        return {str(k): _serialize_value(v) for k, v in value.items()}
    return value


# ---------------------------------------------------------------------------
# Dict serialization
# ---------------------------------------------------------------------------


def quality_gate_safety_flags_to_dict(flags: QualityGateSafetyFlags) -> dict[str, Any]:
    """Serialize QualityGateSafetyFlags to a JSON-safe dict."""
    return {
        "dry_run": flags.dry_run,
        "live_trading_enabled": flags.live_trading_enabled,
        "real_orders_enabled": flags.real_orders_enabled,
        "leverage_enabled": flags.leverage_enabled,
        "shorting_enabled": flags.shorting_enabled,
        "quality_gate_output_is_human_audit_only": flags.quality_gate_output_is_human_audit_only,
        "quality_gate_output_not_trading_signal": flags.quality_gate_output_not_trading_signal,
        "quality_gate_output_not_trade_approval": flags.quality_gate_output_not_trade_approval,
        "quality_gate_output_not_execution_readiness": flags.quality_gate_output_not_execution_readiness,
        "quality_gate_output_not_strategy_readiness": flags.quality_gate_output_not_strategy_readiness,
        "quality_gate_output_not_for_execution": flags.quality_gate_output_not_for_execution,
        "quality_gate_output_not_for_strategy": flags.quality_gate_output_not_for_strategy,
        "quality_gate_output_not_for_freqtrade": flags.quality_gate_output_not_for_freqtrade,
        "quality_gate_output_not_for_order": flags.quality_gate_output_not_for_order,
        "quality_gate_output_not_for_exchange": flags.quality_gate_output_not_for_exchange,
        "quality_gate_feedback_into_execution": flags.quality_gate_feedback_into_execution,
        "cross_layer_feedback_into_execution": flags.cross_layer_feedback_into_execution,
        "file_refs_not_traversed": flags.file_refs_not_traversed,
    }


def quality_gate_config_to_dict(config: QualityGateConfig) -> dict[str, Any]:
    """Serialize QualityGateConfig to a JSON-safe dict."""
    return {
        "version": config.version,
        "generated_at": _iso(config.generated_at) if config.generated_at is not None else None,
        "output_format": config.output_format,
        "dry_run": config.dry_run,
        "live_trading_enabled": config.live_trading_enabled,
        "real_orders_enabled": config.real_orders_enabled,
        "leverage_enabled": config.leverage_enabled,
        "shorting_enabled": config.shorting_enabled,
        "block_on_unknown": config.block_on_unknown,
        "required_artifact_kinds": [kind.value for kind in config.required_artifact_kinds],
        "max_staleness_minutes": config.max_staleness_minutes,
        "include_handoff_notes": config.include_handoff_notes,
    }


def quality_gate_check_to_dict(check: QualityGateCheck) -> dict[str, Any]:
    """Serialize QualityGateCheck to a JSON-safe dict."""
    return {
        "check_kind": check.check_kind.value,
        "state": check.state,
        "reason_codes": list(check.reason_codes),
        "notes": check.notes,
        "metadata": _serialize_value(check.metadata) if check.metadata else {},
    }


def quality_gate_summary_to_dict(summary: QualityGateSummary) -> dict[str, Any]:
    """Serialize QualityGateSummary to a JSON-safe dict."""
    return {
        "total_checks": summary.total_checks,
        "pass_checks": summary.pass_checks,
        "warn_checks": summary.warn_checks,
        "block_checks": summary.block_checks,
        "unknown_checks": summary.unknown_checks,
        "total_artifacts": summary.total_artifacts,
        "total_blockers": summary.total_blockers,
        "unresolved_blockers": summary.unresolved_blockers,
        "verdict": summary.verdict,
        "reason_code_counts": dict(summary.reason_code_counts) if summary.reason_code_counts else {},
        "handoff_notes": summary.handoff_notes,
    }


def quality_gate_data_quality_to_dict(
    data_quality: QualityGateDataQuality,
) -> dict[str, Any]:
    """Serialize QualityGateDataQuality to a JSON-safe dict."""
    return {
        "completeness_pct": data_quality.completeness_pct,
        "ready_pct": data_quality.ready_pct,
        "missing_count": data_quality.missing_count,
        "stale_count": data_quality.stale_count,
        "blocked_count": data_quality.blocked_count,
        "unknown_count": data_quality.unknown_count,
        "total_checks": data_quality.total_checks,
        "reason": data_quality.reason,
    }


def research_quality_gate_to_dict(gate: ResearchQualityGate) -> dict[str, Any]:
    """Serialize ResearchQualityGate to a JSON-safe dict deterministically."""
    return {
        "gate_id": gate.gate_id,
        "generated_at": _iso(gate.generated_at),
        "version": gate.version,
        "verdict": gate.verdict.value,
        "checks": [quality_gate_check_to_dict(check) for check in gate.checks],
        "summary": quality_gate_summary_to_dict(gate.summary),
        "data_quality": quality_gate_data_quality_to_dict(gate.data_quality),
        "safety_flags": quality_gate_safety_flags_to_dict(gate.safety_flags),
        "config": quality_gate_config_to_dict(gate.config),
        "reason_codes": list(gate.reason_codes),
        "handoff_notes": gate.handoff_notes,
    }


# ---------------------------------------------------------------------------
# Markdown serialization
# ---------------------------------------------------------------------------


_SAFETY_NOTICE = (
    "This local research quality gate is a human-audit artifact only. "
    "It is not a trading signal, not trade approval, not execution readiness, "
    "not strategy readiness, and must not be consumed by execution, strategy, "
    "Freqtrade shell, transaction placement, exchange, or any MVP execution path."
)


def research_quality_gate_to_markdown(gate: ResearchQualityGate) -> str:
    """Render ResearchQualityGate as human-readable Markdown with safety notice."""
    summary = gate.summary
    data_quality = gate.data_quality
    flags = gate.safety_flags

    lines: list[str] = [
        "# Research Quality Gate — Audit Readiness",
        "",
        f"> {_SAFETY_NOTICE}",
        "",
        "## Gate Info",
        "",
        f"- **gate_id**: {gate.gate_id}",
        f"- **generated_at**: {_iso(gate.generated_at)}",
        f"- **version**: {gate.version}",
        f"- **verdict**: {gate.verdict.value}",
        f"- **check_count**: {len(gate.checks)}",
        "",
        "## Safety Notice",
        "",
        "This research quality gate is a **human-audit artifact only**.",
        "",
        "- It is **not a trading signal**.",
        "- It is **not trade approval**.",
        "- It is **not execution readiness**.",
        "- It is **not strategy readiness**.",
        "- It is **not for execution**, **not for strategy**, **not for Freqtrade shell**, **not for transaction placement**, **not for exchange**, and **must not be consumed by any MVP execution path**.",
        "- File references and metadata strings in this gate are **local strings only** and are **not traversed, opened, followed, validated, or executed**.",
        "",
        "## Verdict Interpretation",
        "",
        f"**{gate.verdict.value}**: {summary.handoff_notes}",
        "",
        "## Summary",
        "",
        f"- **total_checks**: {summary.total_checks}",
        f"- **pass_checks**: {summary.pass_checks}",
        f"- **warn_checks**: {summary.warn_checks}",
        f"- **block_checks**: {summary.block_checks}",
        f"- **unknown_checks**: {summary.unknown_checks}",
        f"- **total_artifacts**: {summary.total_artifacts}",
        f"- **total_blockers**: {summary.total_blockers}",
        f"- **unresolved_blockers**: {summary.unresolved_blockers}",
        "",
    ]

    lines.extend(["### Reason Code Counts", ""])
    if summary.reason_code_counts:
        for code, count in summary.reason_code_counts.items():
            lines.append(f"- {code}: {count}")
    else:
        lines.append("- none")
    lines.append("")

    lines.extend(["## Checks", ""])
    if not gate.checks:
        lines.append("_No checks._")
        lines.append("")
    else:
        lines.append("| kind | state | reason_codes | notes |")
        lines.append("|------|-------|--------------|-------|")
        for check in gate.checks:
            notes_snippet = (check.notes or "").replace("|", "\\|")[:80]
            reason_codes_str = ", ".join(check.reason_codes) if check.reason_codes else "none"
            lines.append(
                f"| {check.check_kind.value} | {check.state} | {reason_codes_str} | {notes_snippet} |"
            )
        lines.append("")

        for check in gate.checks:
            if check.reason_codes or check.metadata:
                lines.append(f"### {check.check_kind.value}")
                lines.append("")
                if check.reason_codes:
                    lines.append(f"- **reason_codes**: {', '.join(check.reason_codes)}")
                if check.metadata:
                    lines.append("- **metadata**:")
                    for key, value in quality_gate_check_to_dict(check)["metadata"].items():
                        lines.append(f"  - {key}: {value}")
                lines.append("")

    lines.extend([
        "## Data Quality",
        "",
        f"- **completeness_pct**: {data_quality.completeness_pct}",
        f"- **ready_pct**: {data_quality.ready_pct}",
        f"- **missing_count**: {data_quality.missing_count}",
        f"- **stale_count**: {data_quality.stale_count}",
        f"- **blocked_count**: {data_quality.blocked_count}",
        f"- **unknown_count**: {data_quality.unknown_count}",
        f"- **total_checks**: {data_quality.total_checks}",
        f"- **reason**: {data_quality.reason}",
        "",
    ])

    lines.extend(["## Safety Flags", ""])
    for key, value in quality_gate_safety_flags_to_dict(flags).items():
        lines.append(f"- **{key}**: {value}")
    lines.append("")

    lines.extend(["## Reason Codes", ""])
    if gate.reason_codes:
        for code in gate.reason_codes:
            lines.append(f"- {code}")
    else:
        lines.append("- none")
    lines.append("")

    lines.extend([
        "## Configuration",
        "",
        f"- **version**: {gate.config.version}",
        f"- **output_format**: {gate.config.output_format}",
        f"- **dry_run**: {gate.config.dry_run}",
        f"- **block_on_unknown**: {gate.config.block_on_unknown}",
        f"- **max_staleness_minutes**: {gate.config.max_staleness_minutes}",
        f"- **required_artifact_kinds**: {', '.join(kind.value for kind in gate.config.required_artifact_kinds)}",
        "",
    ])

    lines.extend([
        "## Handoff Notes",
        "",
        summary.handoff_notes if summary.handoff_notes else "_No handoff notes._",
        "",
    ])

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Atomic writes
# ---------------------------------------------------------------------------


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


def atomic_write_json_research_quality_gate(
    gate: ResearchQualityGate,
    target_path: Path | None = None,
) -> Path:
    """Serialize ResearchQualityGate to JSON and write atomically."""
    path = target_path if target_path is not None else DEFAULT_QUALITY_GATE_JSON_PATH
    data = research_quality_gate_to_dict(gate)
    text = json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True)
    text += "\n"
    _atomic_write(path, text)
    return path


def atomic_write_markdown_research_quality_gate(
    gate: ResearchQualityGate,
    target_path: Path | None = None,
) -> Path:
    """Serialize ResearchQualityGate to Markdown and write atomically."""
    path = target_path if target_path is not None else DEFAULT_QUALITY_GATE_MARKDOWN_PATH
    _atomic_write(path, research_quality_gate_to_markdown(gate) + "\n")
    return path


def write_research_quality_gate(
    gate: ResearchQualityGate,
    json_path: Path | None = None,
    markdown_path: Path | None = None,
) -> tuple[Path, Path]:
    """Write ResearchQualityGate to both JSON and Markdown."""
    json_out = atomic_write_json_research_quality_gate(gate, json_path)
    markdown_out = atomic_write_markdown_research_quality_gate(gate, markdown_path)
    return json_out, markdown_out
