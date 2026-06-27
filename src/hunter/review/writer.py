"""Review writer — JSON/Markdown audit record serialization and atomic file writing."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .models import (
    ReviewAuditRecord,
    ReviewAuditSummary,
    ReviewDataQuality,
    ReviewRecord,
    ReviewSafetyFlags,
    ReviewState,
    ReviewStatus,
)

DEFAULT_REVIEW_JSON_RECORD_PATH = Path("data/review/latest_review_audit_record.json")
DEFAULT_REVIEW_MARKDOWN_RECORD_PATH = Path("reports/review/latest_review_audit_record.md")


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def _serialize_datetime(dt: datetime) -> str:
    """Serialize datetime to ISO-8601 with Z suffix when UTC."""
    if dt.tzinfo is timezone.utc:
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return dt.isoformat()


def _serialize_value(value: Any) -> Any:
    """Recursively serialize a value to JSON-safe types."""
    if isinstance(value, datetime):
        return _serialize_datetime(value)
    if isinstance(value, (ReviewState, ReviewStatus)):
        return value.value
    if isinstance(value, tuple):
        return [_serialize_value(v) for v in value]
    if isinstance(value, Mapping):
        return {str(k): _serialize_value(v) for k, v in value.items()}
    return value


# ---------------------------------------------------------------------------
# Dict serialization functions
# ---------------------------------------------------------------------------

def review_record_to_dict(record: ReviewRecord) -> dict[str, Any]:
    """Serialize ReviewRecord to a JSON-safe dict."""
    return {
        "review_id": record.review_id,
        "source_report_id": record.source_report_id,
        "source_report_version": record.source_report_version,
        "review_state": record.review_state.value,
        "review_status": record.review_status.value,
        "reviewer": record.reviewer,
        "notes": record.notes,
        "tags": list(record.tags),
        "reason_codes": list(record.reason_codes),
        "reviewed_at": _serialize_datetime(record.reviewed_at),
        "safety_flags": review_safety_flags_to_dict(record.safety_flags),
        "metadata": dict(record.metadata),
    }


def review_safety_flags_to_dict(flags: ReviewSafetyFlags) -> dict[str, Any]:
    """Serialize ReviewSafetyFlags to a JSON-safe dict."""
    return {
        "dry_run": flags.dry_run,
        "live_trading_enabled": flags.live_trading_enabled,
        "real_orders_enabled": flags.real_orders_enabled,
        "leverage_enabled": flags.leverage_enabled,
        "shorting_enabled": flags.shorting_enabled,
        "report_feedback_into_execution": flags.report_feedback_into_execution,
        "operator_feedback_into_execution": flags.operator_feedback_into_execution,
        "network_calls_enabled": flags.network_calls_enabled,
        "database_persistence_enabled": flags.database_persistence_enabled,
    }


def review_audit_summary_to_dict(summary: ReviewAuditSummary) -> dict[str, Any]:
    """Serialize ReviewAuditSummary to a JSON-safe dict."""
    return {
        "total_reviews": summary.total_reviews,
        "accepted_count": summary.accepted_count,
        "rejected_count": summary.rejected_count,
        "needs_investigation_count": summary.needs_investigation_count,
        "not_reviewed_count": summary.not_reviewed_count,
        "blocked_count": summary.blocked_count,
        "unknown_count": summary.unknown_count,
        "reason_counts": dict(summary.reason_counts),
    }


def review_data_quality_to_dict(data_quality: ReviewDataQuality) -> dict[str, Any]:
    """Serialize ReviewDataQuality to a JSON-safe dict."""
    return {
        "total_reports": data_quality.total_reports,
        "valid_reports": data_quality.valid_reports,
        "blocked_reports": data_quality.blocked_reports,
        "unknown_reports": data_quality.unknown_reports,
        "unsafe_reports": data_quality.unsafe_reports,
        "missing_reports": data_quality.missing_reports,
        "invalid_reports": data_quality.invalid_reports,
    }


def review_audit_record_to_dict(audit: ReviewAuditRecord) -> dict[str, Any]:
    """Serialize ReviewAuditRecord to a JSON-safe dict."""
    return {
        "audit_id": audit.audit_id,
        "generated_at": _serialize_datetime(audit.generated_at),
        "audit_state": audit.audit_state.value,
        "records": [review_record_to_dict(r) for r in audit.records],
        "summary": review_audit_summary_to_dict(audit.summary),
        "data_quality": review_data_quality_to_dict(audit.data_quality),
        "reason_codes": list(audit.reason_codes),
        "safety_flags": review_safety_flags_to_dict(audit.safety_flags),
    }


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------

SAFETY_NOTICE = (
    "This review audit record is a human-audit artifact only. "
    "It is not a trading signal, not trade approval, and must not be consumed by "
    "execution, strategy, Freqtrade shell, order, exchange, or any MVP execution path."
)


def review_audit_record_to_markdown(audit: ReviewAuditRecord) -> str:
    """Render ReviewAuditRecord as human-readable Markdown with safety notice."""
    lines = [
        "# Review Audit Record",
        "",
        f"**Audit ID:** {audit.audit_id}",
        f"**Generated At:** {_serialize_datetime(audit.generated_at)}",
        f"**Audit State:** {audit.audit_state.value}",
        "",
        "## Safety Notice",
        "",
        f"> {SAFETY_NOTICE}",
        "",
        "## Summary",
        "",
        f"- Total Reviews: {audit.summary.total_reviews}",
        f"- Accepted: {audit.summary.accepted_count}",
        f"- Rejected: {audit.summary.rejected_count}",
        f"- Needs Investigation: {audit.summary.needs_investigation_count}",
        f"- Not Reviewed: {audit.summary.not_reviewed_count}",
        f"- Blocked: {audit.summary.blocked_count}",
        f"- Unknown: {audit.summary.unknown_count}",
        "",
        "## Reason Codes",
        "",
    ]

    if audit.reason_codes:
        for code in audit.reason_codes:
            lines.append(f"- {code}")
    else:
        lines.append("- None")

    lines.extend([
        "",
        "## Data Quality",
        "",
        f"- Total Reports: {audit.data_quality.total_reports}",
        f"- Valid Reports: {audit.data_quality.valid_reports}",
        f"- Blocked Reports: {audit.data_quality.blocked_reports}",
        f"- Unknown Reports: {audit.data_quality.unknown_reports}",
        f"- Unsafe Reports: {audit.data_quality.unsafe_reports}",
        f"- Missing Reports: {audit.data_quality.missing_reports}",
        f"- Invalid Reports: {audit.data_quality.invalid_reports}",
        "",
        "## Safety Flags",
        "",
        f"- dry_run: {audit.safety_flags.dry_run}",
        f"- live_trading_enabled: {audit.safety_flags.live_trading_enabled}",
        f"- real_orders_enabled: {audit.safety_flags.real_orders_enabled}",
        f"- leverage_enabled: {audit.safety_flags.leverage_enabled}",
        f"- shorting_enabled: {audit.safety_flags.shorting_enabled}",
        f"- report_feedback_into_execution: {audit.safety_flags.report_feedback_into_execution}",
        f"- operator_feedback_into_execution: {audit.safety_flags.operator_feedback_into_execution}",
        f"- network_calls_enabled: {audit.safety_flags.network_calls_enabled}",
        f"- database_persistence_enabled: {audit.safety_flags.database_persistence_enabled}",
        "",
        "## Review Records",
        "",
    ])

    if audit.records:
        for record in audit.records:
            lines.extend([
                f"### {record.review_id}",
                "",
                f"- Source Report: {record.source_report_id} (v{record.source_report_version})",
                f"- Review State: {record.review_state.value}",
                f"- Review Status: {record.review_status.value}",
                f"- Reviewer: {record.reviewer}",
                f"- Reviewed At: {_serialize_datetime(record.reviewed_at)}",
                f"- Reason Codes: {', '.join(record.reason_codes) or 'None'}",
                f"- Notes: {record.notes or 'None'}",
                f"- Tags: {', '.join(record.tags) or 'None'}",
                "",
            ])
    else:
        lines.extend([
            "No review records.",
            "",
        ])

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Atomic file writers
# ---------------------------------------------------------------------------

def atomic_write_json_review_audit_record(audit: ReviewAuditRecord, path: Path) -> Path:
    """Atomically write a ReviewAuditRecord as JSON."""
    data = review_audit_record_to_dict(audit)
    content = json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    return _atomic_write(path, content.encode("utf-8"))


def atomic_write_markdown_review_audit_record(audit: ReviewAuditRecord, path: Path) -> Path:
    """Atomically write a ReviewAuditRecord as Markdown."""
    content = review_audit_record_to_markdown(audit)
    return _atomic_write(path, content.encode("utf-8"))


def _atomic_write(path: Path, content: bytes) -> Path:
    """Atomic write helper: temp file, fsync, os.replace, cleanup."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f".{path.name}.tmp"
    try:
        with open(tmp, "wb") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        return path
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise


# ---------------------------------------------------------------------------
# Combined writer
# ---------------------------------------------------------------------------

def write_review_audit_records(
    audit: ReviewAuditRecord,
    json_path: Path = DEFAULT_REVIEW_JSON_RECORD_PATH,
    markdown_path: Path = DEFAULT_REVIEW_MARKDOWN_RECORD_PATH,
) -> tuple[Path, Path]:
    """Write both JSON and Markdown review audit records."""
    json_result = atomic_write_json_review_audit_record(audit, json_path)
    md_result = atomic_write_markdown_review_audit_record(audit, markdown_path)
    return json_result, md_result
