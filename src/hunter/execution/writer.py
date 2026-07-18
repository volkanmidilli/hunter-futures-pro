"""JSON output writer for execution bridge.

Serializes ExecutionContext to JSON files with atomic writes.
No network, no trading logic, no storage integration.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from hunter.execution.models import ExecutionContext, ExecutionInputRefs, ExecutionSafetyFlags
from hunter.market_state.models import DataQuality


_SAFETY_NOTICE = """\
This artifact is produced for observability, audit, and human review only. It is not an
action command, not an authorization, and does not modify external state. Any downstream
use requires explicit human review and approval."""


def _serialize_datetime(dt: datetime) -> str:
    """Serialize datetime to ISO-8601 format with UTC suffix."""
    if dt.tzinfo is None:
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _serialize_data_quality(dq: DataQuality) -> Dict[str, Any]:
    """Serialize DataQuality to dict."""
    return {
        "missing": dq.missing,
        "stale": dq.stale,
        "insufficient_history": dq.insufficient_history,
        "insufficient_universe": dq.insufficient_universe,
    }


def _serialize_input_refs(refs: ExecutionInputRefs) -> Dict[str, str]:
    """Serialize ExecutionInputRefs to dict."""
    return {
        "decision_timestamp": refs.decision_timestamp,
        "decision_source": refs.decision_source,
    }


def _serialize_safety_flags(flags: ExecutionSafetyFlags) -> Dict[str, Any]:
    """Serialize ExecutionSafetyFlags to dict."""
    return {
        "dry_run": flags.dry_run,
        "live_trading_enabled": flags.live_trading_enabled,
        "exchange_connection_enabled": flags.exchange_connection_enabled,
        "freqtrade_enabled": flags.freqtrade_enabled,
        "human_override_required": flags.human_override_required,
        "max_context_age_seconds": flags.max_context_age_seconds,
    }


def execution_context_to_dict(context: ExecutionContext) -> Dict[str, Any]:
    """Serialize ExecutionContext to JSON-compatible dict.

    Returns a dict matching SPEC-005 JSON contract.
    """
    return {
        "timestamp": _serialize_datetime(context.timestamp),
        "status": context.status.value,
        "execution_state": context.execution_state.value,
        "execution_mode": context.execution_mode.value,
        "decision_state": context.decision_state.value,
        "decision_action": context.decision_action.value,
        "allowed_mode": context.allowed_mode.value,
        "dry_run": context.dry_run,
        "live_trading_enabled": context.live_trading_enabled,
        "exchange_connection_enabled": context.exchange_connection_enabled,
        "freqtrade_enabled": context.freqtrade_enabled,
        "reason_codes": context.reason_codes,
        "input_refs": _serialize_input_refs(context.input_refs),
        "data_quality": _serialize_data_quality(context.data_quality),
        "safety_flags": _serialize_safety_flags(context.safety_flags),
        "version": context.version,
    }


def atomic_write_json(data: Dict[str, Any], target_path: Path, overwrite: bool = False) -> None:
    """Atomically write JSON data to target_path.

    Writes to a temp file in the same directory first, then renames.
    This ensures no partial output exists at target_path on failure.
    Creates parent directories if missing.

    Args:
        data: JSON-serializable dict.
        target_path: Destination path.
        overwrite: If False, refuse to overwrite an existing file.

    Raises:
        OSError: If directory creation or write fails.
        TypeError: If data is not JSON-serializable.
        FileExistsError: If target exists and overwrite is False.
    """
    target_path = Path(target_path)
    parent = target_path.parent

    if target_path.exists() and not overwrite:
        raise FileExistsError(f'Refusing to overwrite existing file: {target_path}')

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


def write_execution_context(
    context: ExecutionContext,
    target_path: Path | str = Path("data/execution/current_execution_context.json"),
    overwrite: bool = False,
) -> Path:
    """Write ExecutionContext to JSON file.

    Args:
        context: ExecutionContext to serialize.
        target_path: Destination path. Defaults to data/execution/current_execution_context.json.
        overwrite: If False, refuse to overwrite an existing file.

    Returns:
        Path to written file.

    Raises:
        OSError: If write fails.
        TypeError: If serialization fails.
        FileExistsError: If target exists and overwrite is False.
    """
    target_path = Path(target_path)
    data = execution_context_to_dict(context)
    data["_safety_notice"] = _SAFETY_NOTICE
    atomic_write_json(data, target_path, overwrite=overwrite)
    return target_path
