"""JSON output writer for Freqtrade bridge.

Serializes FreqtradeBridgeContext to JSON files with atomic writes.
No network, no trading logic, no storage integration.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from hunter.freqtrade_bridge.models import (
    FreqtradeBridgeContext,
    FreqtradeBridgeDataQuality,
    FreqtradeBridgeInputRefs,
    FreqtradeBridgeSafetyFlags,
)


_SAFETY_NOTICE = """\
This artifact is produced for observability, audit, and human review only. It is not an
action command, not an authorization, and does not modify external state. Any downstream
use requires explicit human review and approval."""


def _serialize_datetime(dt: datetime) -> str:
    """Serialize datetime to ISO-8601 format with UTC suffix."""
    if dt.tzinfo is None:
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def freqtrade_bridge_context_to_dict(context: FreqtradeBridgeContext) -> Dict[str, Any]:
    """Serialize FreqtradeBridgeContext to JSON-compatible dict.

    Returns a dict matching SPEC-006 JSON contract.
    """
    return {
        "timestamp": _serialize_datetime(context.timestamp),
        "status": context.status,
        "bridge_state": context.bridge_state.value,
        "bridge_mode": context.bridge_mode.value,
        "execution_state": context.execution_state,
        "execution_mode": context.execution_mode,
        "dry_run": context.dry_run,
        "live_trading_enabled": context.live_trading_enabled,
        "exchange_connection_enabled": context.exchange_connection_enabled,
        "freqtrade_runtime_enabled": context.freqtrade_runtime_enabled,
        "strategy_enabled": context.strategy_enabled,
        "real_orders_enabled": context.real_orders_enabled,
        "leverage_enabled": context.leverage_enabled,
        "shorting_enabled": context.shorting_enabled,
        "reason_codes": context.reason_codes,
        "input_refs": {
            "execution_context_timestamp": context.input_refs.execution_context_timestamp,
            "execution_context_version": context.input_refs.execution_context_version,
        },
        "data_quality": context.data_quality.to_dict(),
        "safety_flags": context.safety_flags.to_dict(),
        "version": context.version,
    }


def atomic_write_json(data: Dict[str, Any], target_path: Path) -> None:
    """Atomically write JSON data to target_path.

    Writes to a temp file in the same directory first, then renames.
    This ensures no partial output exists at target_path on failure.
    Creates parent directories if missing.

    Args:
        data: JSON-serializable dict.
        target_path: Destination path.

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
            json.dump(data, f, indent=2, ensure_ascii=False)
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


def write_freqtrade_bridge_context(
    context: FreqtradeBridgeContext,
    target_path: Path | str = Path("data/freqtrade/current_freqtrade_context.json"),
) -> Path:
    """Write FreqtradeBridgeContext to JSON file.

    Args:
        context: FreqtradeBridgeContext to serialize.
        target_path: Destination path. Defaults to data/freqtrade/current_freqtrade_context.json.

    Returns:
        Path to written file.

    Raises:
        OSError: If write fails.
        TypeError: If serialization fails.
    """
    target_path = Path(target_path)
    data = freqtrade_bridge_context_to_dict(context)
    atomic_write_json(data, target_path)
    return target_path
