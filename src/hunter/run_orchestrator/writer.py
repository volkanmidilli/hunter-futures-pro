"""Writer for hunter.run_orchestrator package.

MVP-30 — Local Research Run Orchestrator.

Deterministic JSON, CSV, and Markdown serialization for ResearchRunResult with
atomic writes. Output is a human-audit / research-only artifact. It is not a
trading signal, not trade approval, not strategy approval, not execution
approval, not portfolio/universe approval, and not Freqtrade input. It does not
emit action commands, suggest orders, or create execution instructions. File
references and metadata strings are serialized as opaque strings only; they are
never opened, traversed, validated, followed, or executed here.
"""

from __future__ import annotations

import csv
import io
import json
import os
from collections.abc import Mapping
from dataclasses import is_dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from hunter.run_orchestrator.models import (
    ResearchRunArtifact,
    ResearchRunConfig,
    ResearchRunDataQuality,
    ResearchRunPlan,
    ResearchRunResult,
    ResearchRunSafetyFlags,
    ResearchRunState,
    ResearchRunStep,
    ResearchRunStepKind,
    ResearchRunStepResult,
    ResearchRunStepState,
)

DEFAULT_JSON_PATH = Path("data/run_orchestrator/run_summary.json")
DEFAULT_CSV_PATH = Path("data/run_orchestrator/run_steps.csv")
DEFAULT_MD_PATH = Path("reports/run_orchestrator/run_summary.md")

_SAFETY_NOTICE = (
    "This local research run summary is a human-audit / research-only artifact. "
    "It is not a trading signal, not trade approval, not strategy approval, not execution approval, "
    "not portfolio/universe approval, and not Freqtrade input. It must not be consumed by execution, "
    "strategy, Freqtrade shell, order, exchange, or any MVP execution path. "
    "No action commands, trading instructions, or order suggestions are emitted. "
    "All step results and artifact references below are research-only; they are not position sizes, "
    "not trade sizes, and not orders."
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
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return _iso(value)
    if isinstance(value, tuple):
        return [_serialize_value(v) for v in value]
    if isinstance(value, list):
        return [_serialize_value(v) for v in value]
    if isinstance(value, (set, frozenset)):
        return [_serialize_value(v) for v in sorted(value, key=str)]
    if isinstance(value, Mapping):
        return {str(k): _serialize_value(v) for k, v in sorted(value.items())}
    if is_dataclass(value):
        return {
            name: _serialize_value(getattr(value, name))
            for name in value.__dataclass_fields__
        }
    return value


def _coerce_path(value: str | Path | None, default: Path) -> Path:
    """Return a Path for the given value, falling back to the default."""
    if value is None:
        return default
    if isinstance(value, Path):
        return value
    return Path(value)


# ---------------------------------------------------------------------------
# Dict serialization
# ---------------------------------------------------------------------------


def _config_to_dict(config: ResearchRunConfig) -> dict[str, Any]:
    """Serialize ResearchRunConfig to a JSON-safe dict."""
    return {
        "output_dir": config.output_dir,
        "fail_fast": config.fail_fast,
        "write_artifacts": config.write_artifacts,
        "generated_at": _iso(config.generated_at) if config.generated_at is not None else None,
        "metadata": _serialize_value(config.metadata),
        "project_version": config.project_version,
    }


def _plan_to_dict(plan: ResearchRunPlan) -> dict[str, Any]:
    """Serialize ResearchRunPlan to a JSON-safe dict."""
    return {
        "run_id": plan.run_id,
        "steps": [_step_to_dict(s) for s in plan.steps],
        "metadata": _serialize_value(plan.metadata),
    }


def _step_to_dict(step: ResearchRunStep) -> dict[str, Any]:
    """Serialize ResearchRunStep to a JSON-safe dict."""
    return {
        "kind": step.kind.value,
        "step_id": step.step_id,
        "inputs": _serialize_value(step.inputs),
        "metadata": _serialize_value(step.metadata),
    }


def _step_result_to_dict(step_result: ResearchRunStepResult) -> dict[str, Any]:
    """Serialize ResearchRunStepResult to a JSON-safe dict."""
    return {
        "step_index": step_result.step_index,
        "step_id": step_result.step_id,
        "kind": step_result.kind.value,
        "state": step_result.state.value,
        "reason_codes": list(step_result.reason_codes),
        "data": _serialize_value(step_result.data),
        "output_paths": list(step_result.output_paths),
        "notes": list(step_result.notes),
        "error_message": step_result.error_message,
    }


def _artifact_to_dict(artifact: ResearchRunArtifact) -> dict[str, Any]:
    """Serialize ResearchRunArtifact to a JSON-safe dict."""
    return {
        "step_index": artifact.step_index,
        "step_id": artifact.step_id,
        "kind": artifact.kind,
        "path": artifact.path,
        "metadata": _serialize_value(artifact.metadata),
    }


def _data_quality_to_dict(data_quality: ResearchRunDataQuality) -> dict[str, Any]:
    """Serialize ResearchRunDataQuality to a JSON-safe dict."""
    return {
        "total_steps": data_quality.total_steps,
        "successful_steps": data_quality.successful_steps,
        "failed_steps": data_quality.failed_steps,
        "blocked_steps": data_quality.blocked_steps,
        "skipped_steps": data_quality.skipped_steps,
        "sections_present": list(data_quality.sections_present),
        "sections_expected": list(data_quality.sections_expected),
        "notes": list(data_quality.notes),
    }


def _safety_flags_to_dict(flags: ResearchRunSafetyFlags) -> dict[str, Any]:
    """Serialize ResearchRunSafetyFlags to a JSON-safe dict."""
    fields = flags.__dataclass_fields__
    data: dict[str, Any] = {name: getattr(flags, name) for name in fields}
    data["is_safe"] = flags.is_safe
    return data


def research_run_result_to_dict(result: ResearchRunResult) -> dict[str, Any]:
    """Serialize ResearchRunResult to a JSON-safe dict deterministically."""
    return {
        "run_id": result.run_id,
        "version": result.config.project_version,
        "generated_at": _iso(result.generated_at),
        "state": result.state.value,
        "config": _config_to_dict(result.config),
        "plan": _plan_to_dict(result.plan),
        "steps": [_step_result_to_dict(s) for s in result.steps],
        "artifacts": [_artifact_to_dict(a) for a in result.artifacts],
        "data_quality": _data_quality_to_dict(result.data_quality),
        "safety_flags": _safety_flags_to_dict(result.safety_flags),
        "reason_codes": list(result.reason_codes),
        "metadata": _serialize_value(result.metadata),
        "notes": list(result.notes),
    }


# ---------------------------------------------------------------------------
# Text serializers
# ---------------------------------------------------------------------------


def research_run_result_to_json_text(result: ResearchRunResult) -> str:
    """Return a deterministic JSON text representation of a ResearchRunResult."""
    data = research_run_result_to_dict(result)
    return json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


_CSV_COLUMNS = (
    "run_id",
    "generated_at",
    "step_index",
    "step_id",
    "step_kind",
    "step_state",
    "reason_codes",
    "artifact_count",
    "error_message",
)


def research_run_result_to_csv_text(result: ResearchRunResult) -> str:
    """Return a deterministic CSV text representation of the step results."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(_CSV_COLUMNS)
    generated_at = _iso(result.generated_at)
    for step in result.steps:
        artifact_count = sum(1 for a in result.artifacts if a.step_index == step.step_index)
        row: list[Any] = [
            result.run_id,
            generated_at,
            step.step_index,
            step.step_id,
            step.kind.value,
            step.state.value,
            "|".join(step.reason_codes),
            artifact_count,
            step.error_message,
        ]
        writer.writerow(row)
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# Markdown serialization
# ---------------------------------------------------------------------------


def _md_value(value: Any) -> str:
    """Stringify a value for Markdown, escaping pipe characters."""
    if value is None:
        return ""
    text = str(value).replace("|", "\\|")
    return text


def research_run_result_to_markdown_text(result: ResearchRunResult) -> str:
    """Render ResearchRunResult as Markdown with a safety notice."""
    dq = result.data_quality
    lines: list[str] = [
        "# Research Run Summary",
        "",
        f"> {_SAFETY_NOTICE}",
        "",
        "## Run Summary",
        "",
        f"- **run_id**: {result.run_id}",
        f"- **version**: {result.config.project_version}",
        f"- **state**: {result.state.value}",
        f"- **generated_at**: {_iso(result.generated_at)}",
        "",
        "## Data Quality",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| total_steps | {_md_value(dq.total_steps)} |",
        f"| successful_steps | {_md_value(dq.successful_steps)} |",
        f"| failed_steps | {_md_value(dq.failed_steps)} |",
        f"| blocked_steps | {_md_value(dq.blocked_steps)} |",
        f"| skipped_steps | {_md_value(dq.skipped_steps)} |",
        f"| sections_present | {_md_value('|'.join(dq.sections_present))} |",
        f"| sections_expected | {_md_value('|'.join(dq.sections_expected))} |",
        "",
        "## Step Results",
        "",
        "| step_index | step_id | kind | state | reason_codes | output_paths | error_message |",
        "|------------|---------|------|-------|--------------|--------------|---------------|",
    ]
    for step in result.steps:
        lines.append(
            f"| {_md_value(step.step_index)} | {_md_value(step.step_id)} | "
            f"{_md_value(step.kind.value)} | {_md_value(step.state.value)} | "
            f"{_md_value('|'.join(step.reason_codes))} | "
            f"{_md_value('|'.join(step.output_paths))} | "
            f"{_md_value(step.error_message)} |"
        )
    lines.append("")

    lines.extend([
        "## Artifacts",
        "",
        "| step_index | step_id | kind | path |",
        "|------------|---------|------|------|",
    ])
    for artifact in result.artifacts:
        lines.append(
            f"| {_md_value(artifact.step_index)} | {_md_value(artifact.step_id)} | "
            f"{_md_value(artifact.kind)} | {_md_value(artifact.path)} |"
        )
    if not result.artifacts:
        lines.append("| _none_ | | | |")
    lines.append("")

    lines.extend([
        "## Safety Flags",
        "",
        "| Flag | Value |",
        "|------|-------|",
    ])
    for key, value in sorted(_safety_flags_to_dict(result.safety_flags).items()):
        lines.append(f"| {_md_value(key)} | {_md_value(value)} |")
    lines.append("")

    if result.reason_codes:
        lines.extend([
            "## Reason Codes",
            "",
        ])
        for code in result.reason_codes:
            lines.append(f"- {code}")
        lines.append("")

    if result.metadata:
        lines.extend([
            "## Metadata",
            "",
        ])
        for key, value in sorted(result.metadata.items()):
            lines.append(f"- **{key}**: {value}")
        lines.append("")

    if result.notes:
        lines.extend([
            "## Notes",
            "",
        ])
        for note in result.notes:
            lines.append(f"- {note}")
        lines.append("")

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


def atomic_write_json_research_run_result(
    result: ResearchRunResult,
    path: str | Path | None = None,
) -> Path:
    """Serialize ResearchRunResult to JSON and write atomically."""
    target = _coerce_path(path, DEFAULT_JSON_PATH)
    _atomic_write(target, research_run_result_to_json_text(result))
    return target


def atomic_write_csv_research_run_result(
    result: ResearchRunResult,
    path: str | Path | None = None,
) -> Path:
    """Serialize ResearchRunResult step rows to CSV and write atomically."""
    target = _coerce_path(path, DEFAULT_CSV_PATH)
    _atomic_write(target, research_run_result_to_csv_text(result))
    return target


def atomic_write_markdown_research_run_result(
    result: ResearchRunResult,
    path: str | Path | None = None,
) -> Path:
    """Serialize ResearchRunResult to Markdown and write atomically."""
    target = _coerce_path(path, DEFAULT_MD_PATH)
    _atomic_write(target, research_run_result_to_markdown_text(result) + "\n")
    return target


_DEFAULT_PATH = object()


def write_research_run_result(
    result: ResearchRunResult,
    json_path: str | Path | None | object = _DEFAULT_PATH,
    csv_path: str | Path | None | object = _DEFAULT_PATH,
    md_path: str | Path | None | object = _DEFAULT_PATH,
) -> tuple[Path | None, Path | None, Path | None]:
    """Write ResearchRunResult to JSON, CSV, and Markdown as requested.

    Pass None for a format to skip writing that artifact. Default paths are used
    when a path is omitted and the format is written.
    """
    json_out = (
        atomic_write_json_research_run_result(
            result, None if json_path is _DEFAULT_PATH else json_path
        )
        if json_path is not None
        else None
    )
    csv_out = (
        atomic_write_csv_research_run_result(
            result, None if csv_path is _DEFAULT_PATH else csv_path
        )
        if csv_path is not None
        else None
    )
    md_out = (
        atomic_write_markdown_research_run_result(
            result, None if md_path is _DEFAULT_PATH else md_path
        )
        if md_path is not None
        else None
    )
    return json_out, csv_out, md_out
