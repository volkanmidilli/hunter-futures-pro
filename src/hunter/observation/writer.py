"""Observation report writer for MVP-10 Dry-Run Research Observation & Reports.

Writes JSON and Markdown reports to local filesystem only.
Reports are human-review artifacts and must never be consumed by execution paths.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from hunter.observation.models import (
    ObservationDataQuality,
    ObservationReport,
    ObservationSafetyFlags,
    ObservationSignal,
    ObservationState,
    ReportFormat,
    SignalObservation,
    ObservationWindow,
)

# ---------------------------------------------------------------------------
# Default paths
# ---------------------------------------------------------------------------

DEFAULT_OBSERVATION_JSON_REPORT_PATH = Path("data/observation/latest_observation_report.json")
DEFAULT_OBSERVATION_MARKDOWN_REPORT_PATH = Path("reports/observation/latest_observation_report.md")


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def _iso(dt: Any) -> str:
    """Serialize a datetime to ISO-8601 with Z suffix."""
    from datetime import datetime
    if isinstance(dt, datetime):
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return str(dt)


def _serialize_enum(value: Any) -> str:
    """Serialize an enum to its .value string."""
    if hasattr(value, "value"):
        return str(value.value)
    return str(value)


def _serialize_tuple(value: Any) -> list[Any]:
    """Serialize a tuple to a list."""
    if isinstance(value, tuple):
        return [_serialize_enum(v) for v in value]
    return list(value)


def _serialize_safety_flags(flags: ObservationSafetyFlags) -> dict[str, Any]:
    """Serialize ObservationSafetyFlags to a dict."""
    return {
        "dry_run": flags.dry_run,
        "live_trading_enabled": flags.live_trading_enabled,
        "real_orders_enabled": flags.real_orders_enabled,
        "leverage_enabled": flags.leverage_enabled,
        "shorting_enabled": flags.shorting_enabled,
        "execution_feedback_allowed": flags.execution_feedback_allowed,
        "network_calls_allowed": flags.network_calls_allowed,
        "database_persistence_allowed": flags.database_persistence_allowed,
        "realtime_streaming_allowed": flags.realtime_streaming_allowed,
        "api_keys_allowed": flags.api_keys_allowed,
    }


def _serialize_data_quality(dq: ObservationDataQuality) -> dict[str, Any]:
    """Serialize ObservationDataQuality to a dict."""
    return {
        "input_present": dq.input_present,
        "input_valid": dq.input_valid,
        "input_version_supported": dq.input_version_supported,
        "observation_count": dq.observation_count,
        "blocked_count": dq.blocked_count,
        "unknown_count": dq.unknown_count,
        "reason": dq.reason,
    }


def _serialize_signal_observation(obs: SignalObservation) -> dict[str, Any]:
    """Serialize a SignalObservation to a dict."""
    return {
        "timestamp": _iso(obs.timestamp),
        "observation_state": _serialize_enum(obs.observation_state),
        "signal": _serialize_enum(obs.signal),
        "source_shell_state": obs.source_shell_state,
        "source_signal_exposure": obs.source_signal_exposure,
        "reason_codes": _serialize_tuple(obs.reason_codes),
        "metadata": dict(obs.metadata),
        "safety_flags": _serialize_safety_flags(obs.safety_flags),
        "version": obs.version,
    }


def _serialize_window(window: ObservationWindow) -> dict[str, Any]:
    """Serialize an ObservationWindow to a dict."""
    return {
        "started_at": _iso(window.started_at),
        "ended_at": _iso(window.ended_at),
        "observations": [_serialize_signal_observation(o) for o in window.observations],
        "window_id": window.window_id,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def observation_report_to_dict(
    report: ObservationReport,
) -> dict[str, Any]:
    """Convert an ObservationReport into a deterministic JSON-safe dict.

    Does not mutate the report. Does not include secrets, API keys,
    exchange credentials, or executable trading instructions.
    """
    return {
        "generated_at": _iso(report.generated_at),
        "report_state": _serialize_enum(report.report_state),
        "window": _serialize_window(report.window),
        "summary": dict(report.summary),
        "data_quality": _serialize_data_quality(report.data_quality),
        "safety_flags": _serialize_safety_flags(report.safety_flags),
        "report_formats": _serialize_tuple(report.report_formats),
        "reason_codes": _serialize_tuple(report.reason_codes),
        "version": report.version,
    }


def observation_report_to_markdown(
    report: ObservationReport,
) -> str:
    """Produce a human-review-only Markdown report.

    Does not include executable trading instructions or secrets.
    """
    lines: list[str] = []
    lines.append("# Observation Report")
    lines.append("")
    lines.append(f"**Generated at:** {_iso(report.generated_at)}")
    lines.append(f"**Report state:** {_serialize_enum(report.report_state)}")
    lines.append(f"**Window ID:** {report.window.window_id}")
    lines.append(f"**Window start:** {_iso(report.window.started_at)}")
    lines.append(f"**Window end:** {_iso(report.window.ended_at)}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    summary = report.summary
    lines.append(f"- **Total observations:** {summary.get('total_observations', 0)}")
    lines.append(f"- **Long research count:** {summary.get('long_research_count', 0)}")
    lines.append(f"- **Short research count:** {summary.get('short_research_count', 0)}")
    lines.append(f"- **None count:** {summary.get('none_count', 0)}")
    lines.append(f"- **Blocked count:** {summary.get('blocked_count', 0)}")
    lines.append(f"- **Unknown count:** {summary.get('unknown_count', 0)}")
    lines.append("")
    lines.append("## Reason Codes")
    lines.append("")
    for reason in report.reason_codes:
        lines.append(f"- {reason}")
    lines.append("")
    lines.append("## Data Quality")
    lines.append("")
    dq = report.data_quality
    lines.append(f"- **Input present:** {dq.input_present}")
    lines.append(f"- **Input valid:** {dq.input_valid}")
    lines.append(f"- **Input version supported:** {dq.input_version_supported}")
    lines.append(f"- **Observation count:** {dq.observation_count}")
    lines.append(f"- **Blocked count:** {dq.blocked_count}")
    lines.append(f"- **Unknown count:** {dq.unknown_count}")
    lines.append(f"- **Reason:** {dq.reason}")
    lines.append("")
    lines.append("## Safety Flags")
    lines.append("")
    sf = report.safety_flags
    lines.append(f"- **Dry run:** {sf.dry_run}")
    lines.append(f"- **Live trading enabled:** {sf.live_trading_enabled}")
    lines.append(f"- **Real orders enabled:** {sf.real_orders_enabled}")
    lines.append(f"- **Leverage enabled:** {sf.leverage_enabled}")
    lines.append(f"- **Shorting enabled:** {sf.shorting_enabled}")
    lines.append(f"- **Execution feedback allowed:** {sf.execution_feedback_allowed}")
    lines.append(f"- **Network calls allowed:** {sf.network_calls_allowed}")
    lines.append(f"- **Database persistence allowed:** {sf.database_persistence_allowed}")
    lines.append(f"- **Realtime streaming allowed:** {sf.realtime_streaming_allowed}")
    lines.append(f"- **API keys allowed:** {sf.api_keys_allowed}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(
        "> **Safety Notice:** This report is a human-review artifact only. "
        "It is not a trading signal and must not be consumed by execution, "
        "strategy, Freqtrade, order, or exchange layers."
    )
    lines.append("")
    return "\n".join(lines)


def atomic_write_json_report(
    payload: dict[str, Any],
    output_path: str | Path,
) -> Path:
    """Write a JSON report atomically.

    Creates parent directories if missing. Uses temp-file + os.replace
    for atomicity. Cleans up temp file on failure.
    """
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.parent / f"{target.name}.tmp"
    try:
        data = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)
        tmp.write_text(data + "\n", encoding="utf-8")
        fd = os.open(tmp, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(tmp, target)
        return target
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise


def atomic_write_markdown_report(
    content: str,
    output_path: str | Path,
) -> Path:
    """Write a Markdown report atomically.

    Creates parent directories if missing. Uses temp-file + os.replace
    for atomicity. Cleans up temp file on failure.
    """
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.parent / f"{target.name}.tmp"
    try:
        tmp.write_text(content + "\n", encoding="utf-8")
        fd = os.open(tmp, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(tmp, target)
        return target
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise


def write_observation_reports(
    report: ObservationReport,
    json_output_path: str | Path | None = None,
    markdown_output_path: str | Path | None = None,
) -> tuple[Path, Path]:
    """Write both JSON and Markdown reports for an ObservationReport.

    Uses default paths when None. Does not read production data.
    Does not feed reports into execution paths.
    """
    json_path = Path(json_output_path) if json_output_path is not None else DEFAULT_OBSERVATION_JSON_REPORT_PATH
    md_path = Path(markdown_output_path) if markdown_output_path is not None else DEFAULT_OBSERVATION_MARKDOWN_REPORT_PATH

    payload = observation_report_to_dict(report)
    md_content = observation_report_to_markdown(report)

    json_result = atomic_write_json_report(payload, json_path)
    md_result = atomic_write_markdown_report(md_content, md_path)

    return json_result, md_result
