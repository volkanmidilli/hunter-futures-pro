"""JSON output writer for Strategy Adapter.

Serializes AdapterDecisionContext to JSON files with atomic writes.
No network, no trading logic, no storage integration.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from hunter.strategy_adapter.models import (
    AdapterDataQuality,
    AdapterDecisionContext,
    AdapterInputRefs,
    AdapterSafetyFlags,
)


_SAFETY_NOTICE = """\
This artifact is produced for observability, audit, and human review only. It is not an
action command, not an authorization, and does not modify external state. Any downstream
use requires explicit human review and approval."""


DEFAULT_ADAPTER_DECISION_PATH = Path(
    "data/strategy_adapter/current_adapter_decision.json"
)


def _serialize_datetime(dt: datetime) -> str:
    """Serialize datetime to ISO-8601 format with UTC suffix."""
    if dt.tzinfo is None:
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def adapter_decision_context_to_dict(
    context: AdapterDecisionContext,
) -> Dict[str, Any]:
    """Serialize AdapterDecisionContext to JSON-compatible dict.

    Returns a dict matching SPEC-008 JSON contract.
    """
    return {
        "timestamp": _serialize_datetime(context.timestamp),
        "status": context.status,
        "adapter_state": context.adapter_state.value,
        "adapter_mode": context.adapter_mode.value,
        "signal_intent": context.signal_intent.value,
        "strategy_contract_state": context.strategy_contract_state,
        "strategy_contract_mode": context.strategy_contract_mode,
        "dry_run": context.dry_run,
        "live_trading_enabled": context.live_trading_enabled,
        "real_orders_enabled": context.real_orders_enabled,
        "leverage_enabled": context.leverage_enabled,
        "shorting_enabled": context.shorting_enabled,
        "adapter_runtime_allowed": context.adapter_runtime_allowed,
        "freqtrade_runtime_allowed": context.freqtrade_runtime_allowed,
        "strategy_class_allowed": context.strategy_class_allowed,
        "entry_signal_allowed": context.entry_signal_allowed,
        "exit_signal_allowed": context.exit_signal_allowed,
        "order_execution_allowed": context.order_execution_allowed,
        "reason_codes": list(context.reason_codes),
        "input_refs": {
            "strategy_context": context.input_refs.strategy_context,
            "adapter_decision": context.input_refs.adapter_decision,
        },
        "safety_flags": context.safety_flags.to_dict(),
        "data_quality": context.data_quality.to_dict(),
        "version": context.version,
    }


def atomic_write_json(data: Dict[str, Any], target_path: Path) -> Path:
    """Atomically write JSON data to target_path.

    Writes to a temp file in the same directory first, then renames.
    This ensures no partial output exists at target_path on failure.
    Creates parent directories if missing.

    Args:
        data: JSON-serializable dict.
        target_path: Destination path.

    Returns:
        Path to written file.

    Raises:
        OSError: If directory creation or write fails.
        TypeError: If data is not JSON-serializable.
    """
    target_path = Path(target_path)
    parent = target_path.parent

    # Create parent directories if missing
    parent.mkdir(parents=True, exist_ok=True)

    # Write to temp file in same directory for atomic rename
    fd, temp_path = tempfile.mkstemp(dir=parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True, ensure_ascii=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        # Atomic rename
        os.replace(temp_path, target_path)
    except Exception:
        # Clean up temp file on failure
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise

    return target_path


def write_adapter_decision_context(
    context: AdapterDecisionContext,
    target_path: Path | None = None,
) -> Path:
    """Write AdapterDecisionContext to JSON file.

    Args:
        context: AdapterDecisionContext to serialize.
        target_path: Destination path. Defaults to
            data/strategy_adapter/current_adapter_decision.json.

    Returns:
        Path to written file.

    Raises:
        OSError: If write fails.
        TypeError: If serialization fails.
    """
    target_path = target_path or DEFAULT_ADAPTER_DECISION_PATH
    data = adapter_decision_context_to_dict(context)
    atomic_write_json(data, target_path)
    return target_path
