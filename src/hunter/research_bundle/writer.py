"""Writer for hunter.research_bundle package. JSON and Markdown serialization with atomic writes.

Deterministic, safe output for human audit. No file reference traversal, no network, no database.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import (
    BUNDLE_ERROR,
    BundleConfig,
    BundleDataQuality,
    BundleItem,
    BundleItemKind,
    BundleSafetyFlags,
    BundleState,
    BundleSummary,
    ResearchBundle,
)


DEFAULT_BUNDLE_JSON_PATH = Path("data/research_bundle/latest_research_bundle.json")
DEFAULT_BUNDLE_MARKDOWN_PATH = Path("reports/research_bundle/latest_research_bundle.md")


# ---------------------------------------------------------------------------
# Value helpers
# ---------------------------------------------------------------------------


def _iso(value: datetime) -> str:
    """Return ISO-8601 string for a timezone-aware datetime."""
    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def _serialize_value(value: Any) -> Any:
    """Serialize a value to JSON-safe form."""
    if isinstance(value, datetime):
        return _iso(value)
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, dict):
        return {
            _serialize_value(k): _serialize_value(v)
            for k, v in sorted(value.items())
        }
    return value


# ---------------------------------------------------------------------------
# Dict serialization
# ---------------------------------------------------------------------------


def bundle_safety_flags_to_dict(flags: BundleSafetyFlags) -> dict[str, Any]:
    """Serialize BundleSafetyFlags to a JSON-safe dict."""
    return dict(sorted({
        "bundle_feedback_into_execution": flags.bundle_feedback_into_execution,
        "bundle_output_is_human_audit_only": flags.bundle_output_is_human_audit_only,
        "bundle_output_not_for_execution": flags.bundle_output_not_for_execution,
        "bundle_output_not_for_exchange": flags.bundle_output_not_for_exchange,
        "bundle_output_not_for_freqtrade": flags.bundle_output_not_for_freqtrade,
        "bundle_output_not_for_order": flags.bundle_output_not_for_order,
        "bundle_output_not_for_strategy": flags.bundle_output_not_for_strategy,
        "bundle_output_not_trade_approval": flags.bundle_output_not_trade_approval,
        "bundle_output_not_trading_signal": flags.bundle_output_not_trading_signal,
        "dashboard_enabled": flags.dashboard_enabled,
        "database_persistence_enabled": flags.database_persistence_enabled,
        "dry_run": flags.dry_run,
        "file_reference_traversal_enabled": flags.file_reference_traversal_enabled,
        "index_feedback_into_execution": flags.index_feedback_into_execution,
        "leverage_enabled": flags.leverage_enabled,
        "live_trading_enabled": flags.live_trading_enabled,
        "operator_feedback_into_execution": flags.operator_feedback_into_execution,
        "real_orders_enabled": flags.real_orders_enabled,
        "report_feedback_into_execution": flags.report_feedback_into_execution,
        "search_feedback_into_execution": flags.search_feedback_into_execution,
        "shorting_enabled": flags.shorting_enabled,
        "web_ui_enabled": flags.web_ui_enabled,
    }.items()))


def bundle_item_to_dict(item: BundleItem) -> dict[str, Any]:
    """Serialize BundleItem to a JSON-safe dict."""
    return {
        "item_id": item.item_id,
        "kind": item.kind.value,
        "reference": item.reference,
        "label": item.label,
        "note": item.note,
        "sort_order": item.sort_order,
        "metadata": _serialize_value(item.metadata),
    }


def bundle_summary_to_dict(summary: BundleSummary) -> dict[str, Any]:
    """Serialize BundleSummary to a JSON-safe dict."""
    return {
        "total_items": summary.total_items,
        "observation_report_count": summary.observation_report_count,
        "review_audit_count": summary.review_audit_count,
        "review_index_count": summary.review_index_count,
        "search_result_count": summary.search_result_count,
        "human_note_count": summary.human_note_count,
        "blocked_items": summary.blocked_items,
        "unknown_items": summary.unknown_items,
    }


def bundle_data_quality_to_dict(data_quality: BundleDataQuality) -> dict[str, Any]:
    """Serialize BundleDataQuality to a JSON-safe dict."""
    return {
        "total_items": data_quality.total_items,
        "missing_references": data_quality.missing_references,
        "invalid_references": data_quality.invalid_references,
        "blocked_items": data_quality.blocked_items,
        "has_observation_report": data_quality.has_observation_report,
        "has_review_audit": data_quality.has_review_audit,
        "has_review_index": data_quality.has_review_index,
        "has_search_result": data_quality.has_search_result,
        "has_human_note": data_quality.has_human_note,
    }


def research_bundle_to_dict(bundle: ResearchBundle) -> dict[str, Any]:
    """Serialize ResearchBundle to a JSON-safe dict."""
    return {
        "bundle_id": bundle.bundle_id,
        "generated_at": _iso(bundle.generated_at),
        "bundle_state": bundle.bundle_state.value,
        "items": [bundle_item_to_dict(item) for item in bundle.items],
        "summary": bundle_summary_to_dict(bundle.summary),
        "data_quality": bundle_data_quality_to_dict(bundle.data_quality),
        "safety_flags": bundle_safety_flags_to_dict(bundle.safety_flags),
        "reason_codes": list(bundle.reason_codes),
    }


# ---------------------------------------------------------------------------
# Markdown serialization
# ---------------------------------------------------------------------------


def _markdown_header(bundle: ResearchBundle) -> str:
    """Generate Markdown header with safety notice."""
    header = f"""# Research Bundle

**Bundle ID:** {bundle.bundle_id}

**Generated:** {_iso(bundle.generated_at)}

**State:** {bundle.bundle_state.value}

---

## Safety Notice

This research bundle is a **human-audit artifact only**.

- It is **not a trading signal**.
- It is **not trade approval**.
- It **must not be consumed by execution, strategy, Freqtrade shell, order, exchange, or any MVP execution path**.
- File references in this bundle are **local strings only** and are **not traversed, opened, followed, validated, or executed**.

---

## Summary

| Metric | Value |
|---|---|
| Total Items | {bundle.summary.total_items} |
| Observation Reports | {bundle.summary.observation_report_count} |
| Review Audits | {bundle.summary.review_audit_count} |
| Review Index References | {bundle.summary.review_index_count} |
| Search Result References | {bundle.summary.search_result_count} |
| Items with Notes | {bundle.summary.human_note_count} |
| Blocked Items | {bundle.summary.blocked_items} |
| Unknown Items | {bundle.summary.unknown_items} |

---

## Data Quality

| Metric | Value |
|---|---|
| Total Items | {bundle.data_quality.total_items} |
| Missing References | {bundle.data_quality.missing_references} |
| Invalid References | {bundle.data_quality.invalid_references} |
| Blocked Items | {bundle.data_quality.blocked_items} |
| Has Observation Report | {bundle.data_quality.has_observation_report} |
| Has Review Audit | {bundle.data_quality.has_review_audit} |
| Has Review Index | {bundle.data_quality.has_review_index} |
| Has Search Result | {bundle.data_quality.has_search_result} |
| Has Human Note | {bundle.data_quality.has_human_note} |

---

## Safety Flags

| Flag | Value |
|---|---|
| Dry Run | {bundle.safety_flags.dry_run} |
| Live Trading | {bundle.safety_flags.live_trading_enabled} |
| Real Orders | {bundle.safety_flags.real_orders_enabled} |
| Leverage | {bundle.safety_flags.leverage_enabled} |
| Shorting | {bundle.safety_flags.shorting_enabled} |
| Bundle Feedback → Execution | {bundle.safety_flags.bundle_feedback_into_execution} |
| Report Feedback → Execution | {bundle.safety_flags.report_feedback_into_execution} |
| Operator Feedback → Execution | {bundle.safety_flags.operator_feedback_into_execution} |
| Index Feedback → Execution | {bundle.safety_flags.index_feedback_into_execution} |
| Search Feedback → Execution | {bundle.safety_flags.search_feedback_into_execution} |
| File Reference Traversal | {bundle.safety_flags.file_reference_traversal_enabled} |
| Database Persistence | {bundle.safety_flags.database_persistence_enabled} |
| Web UI | {bundle.safety_flags.web_ui_enabled} |
| Dashboard | {bundle.safety_flags.dashboard_enabled} |
| Human-Audit Only | {bundle.safety_flags.bundle_output_is_human_audit_only} |
| Not Trading Signal | {bundle.safety_flags.bundle_output_not_trading_signal} |
| Not Trade Approval | {bundle.safety_flags.bundle_output_not_trade_approval} |
| Not for Execution | {bundle.safety_flags.bundle_output_not_for_execution} |
| Not for Strategy | {bundle.safety_flags.bundle_output_not_for_strategy} |
| Not for Freqtrade | {bundle.safety_flags.bundle_output_not_for_freqtrade} |
| Not for Order | {bundle.safety_flags.bundle_output_not_for_order} |
| Not for Exchange | {bundle.safety_flags.bundle_output_not_for_exchange} |

---

## Reason Codes

{', '.join(bundle.reason_codes) if bundle.reason_codes else 'None'}

---

## Items

"""
    return header


def _markdown_items(items: tuple[BundleItem, ...]) -> str:
    """Generate Markdown list of bundle items."""
    lines = []
    for item in items:
        lines.append(f"### {item.item_id} ({item.kind.value})")
        lines.append(f"- **Reference:** {item.reference}")
        if item.label:
            lines.append(f"- **Label:** {item.label}")
        if item.note:
            lines.append(f"- **Note:** {item.note}")
        lines.append(f"- **Sort Order:** {item.sort_order}")
        if item.metadata:
            lines.append("- **Metadata:**")
            for key, value in sorted(item.metadata.items()):
                lines.append(f"  - {key}: {value}")
        lines.append("")
    return "\n".join(lines)


def research_bundle_to_markdown(bundle: ResearchBundle) -> str:
    """Serialize ResearchBundle to human-readable Markdown with safety notice."""
    return _markdown_header(bundle) + _markdown_items(bundle.items)


# ---------------------------------------------------------------------------
# Atomic write helpers
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


# ---------------------------------------------------------------------------
# Atomic public writers
# ---------------------------------------------------------------------------


def atomic_write_json_research_bundle(
    bundle: ResearchBundle,
    path: Path = DEFAULT_BUNDLE_JSON_PATH,
) -> None:
    """Serialize ResearchBundle to JSON and write atomically.

    Does not read, traverse, validate, follow, or execute any file references.
    """
    data = research_bundle_to_dict(bundle)
    text = json.dumps(data, indent=2, ensure_ascii=False, sort_keys=False)
    text += "\n"
    _atomic_write(path, text)


def atomic_write_markdown_research_bundle(
    bundle: ResearchBundle,
    path: Path = DEFAULT_BUNDLE_MARKDOWN_PATH,
) -> None:
    """Serialize ResearchBundle to Markdown and write atomically.

    Does not read, traverse, validate, follow, or execute any file references.
    """
    _atomic_write(path, research_bundle_to_markdown(bundle))


# ---------------------------------------------------------------------------
# Convenience write (both formats)
# ---------------------------------------------------------------------------


def write_research_bundle(
    bundle: ResearchBundle,
    json_path: Path = DEFAULT_BUNDLE_JSON_PATH,
    markdown_path: Path = DEFAULT_BUNDLE_MARKDOWN_PATH,
) -> tuple[Path, Path]:
    """Write ResearchBundle to both JSON and Markdown.

    Does not read, traverse, validate, follow, or execute any file references.
    """
    atomic_write_json_research_bundle(bundle, json_path)
    atomic_write_markdown_research_bundle(bundle, markdown_path)
    return json_path, markdown_path
