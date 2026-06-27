"""JSON output writer for Dry-Run Strategy Runtime.

Serializes DryRunStrategyRuntimeContext to JSON files with atomic writes.
No network, no trading logic, no storage integration.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from hunter.dry_run_strategy.models import (
    DryRunStrategyRuntimeContext,
)


DEFAULT_DRY_RUN_STRATEGY_RUNTIME_PATH = Path(
    "data/freqtrade_strategy/current_dry_run_strategy_runtime.json"
)


def _serialize_datetime(dt: datetime) -> str:
    """Serialize datetime to ISO-8601 format with UTC suffix."""
    if dt.tzinfo is None:
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def dry_run_strategy_runtime_context_to_dict(
    context: DryRunStrategyRuntimeContext,
) -> dict[str, Any]:
    """Serialize DryRunStrategyRuntimeContext to JSON-compatible dict.

    Returns a dict matching SPEC-009 JSON contract.
    """
    return {
        "timestamp": _serialize_datetime(context.timestamp),
        "status": context.status,
        "strategy_state": context.strategy_state.value,
        "strategy_mode": context.strategy_mode.value,
        "signal_action": context.signal_action.value,
        "adapter_state": context.adapter_state,
        "adapter_mode": context.adapter_mode,
        "adapter_signal_intent": context.adapter_signal_intent,
        "dry_run": context.dry_run,
        "live_trading_enabled": context.live_trading_enabled,
        "real_orders_enabled": context.real_orders_enabled,
        "leverage_enabled": context.leverage_enabled,
        "shorting_enabled": context.shorting_enabled,
        "freqtrade_runtime_allowed": context.freqtrade_runtime_allowed,
        "strategy_class_allowed": context.strategy_class_allowed,
        "populate_indicators_allowed": context.populate_indicators_allowed,
        "populate_entry_trend_allowed": context.populate_entry_trend_allowed,
        "populate_exit_trend_allowed": context.populate_exit_trend_allowed,
        "order_execution_allowed": context.order_execution_allowed,
        "reason_codes": list(context.reason_codes),
        "input_refs": {
            "adapter_decision": context.input_refs.adapter_decision,
            "dry_run_strategy_runtime": context.input_refs.dry_run_strategy_runtime,
        },
        "safety_flags": context.safety_flags.to_dict(),
        "data_quality": context.data_quality.to_dict(),
        "version": context.version,
    }


def atomic_write_json(
    payload: dict[str, Any],
    output_path: str | Path,
) -> Path:
    """Atomically write JSON payload to output_path.

    Writes to a temp file in the same directory first, then renames.
    This ensures no partial output exists at output_path on failure.
    Creates parent directories if missing.

    Args:
        payload: JSON-serializable dict.
        output_path: Destination path.

    Returns:
        Path to written file.

    Raises:
        OSError: If directory creation or write fails.
        TypeError: If payload is not JSON-serializable.
    """
    target_path = Path(output_path)
    parent = target_path.parent

    # Create parent directories if missing
    parent.mkdir(parents=True, exist_ok=True)

    # Write to temp file in same directory for atomic rename
    fd, temp_path = tempfile.mkstemp(dir=parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, sort_keys=True, ensure_ascii=False)
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


def write_dry_run_strategy_runtime_context(
    context: DryRunStrategyRuntimeContext,
    output_path: str | Path | None = None,
) -> Path:
    """Write DryRunStrategyRuntimeContext to JSON file.

    Args:
        context: DryRunStrategyRuntimeContext to serialize.
        output_path: Destination path. Defaults to
            data/freqtrade_strategy/current_dry_run_strategy_runtime.json.

    Returns:
        Path to written file.

    Raises:
        OSError: If write fails.
        TypeError: If serialization fails.
    """
    target_path = output_path or DEFAULT_DRY_RUN_STRATEGY_RUNTIME_PATH
    data = dry_run_strategy_runtime_context_to_dict(context)
    atomic_write_json(data, target_path)
    return Path(target_path)
