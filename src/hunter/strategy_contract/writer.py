"""JSON output writer for Strategy Contract.

Serializes StrategyContext to JSON files with atomic writes.
No network, no trading logic, no storage integration.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from hunter.strategy_contract.models import (
    StrategyContext,
    StrategyContractDataQuality,
    StrategyContractInputRefs,
    StrategyContractSafetyFlags,
)


_SAFETY_NOTICE = """\
This artifact is produced for observability, audit, and human review only. It is not an
action command, not an authorization, and does not modify external state. Any downstream
use requires explicit human review and approval."""


DEFAULT_STRATEGY_CONTEXT_PATH = Path("data/strategy/current_strategy_context.json")


def _serialize_datetime(dt: datetime) -> str:
    """Serialize datetime to ISO-8601 format with UTC suffix."""
    if dt.tzinfo is None:
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def strategy_context_to_dict(context: StrategyContext) -> Dict[str, Any]:
    """Serialize StrategyContext to JSON-compatible dict.

    Returns a dict matching SPEC-007 JSON contract.
    """
    return {
        "timestamp": _serialize_datetime(context.timestamp),
        "status": context.status,
        "contract_state": context.contract_state.value,
        "contract_mode": context.contract_mode.value,
        "bridge_state": context.bridge_state,
        "bridge_mode": context.bridge_mode,
        "dry_run": context.dry_run,
        "live_trading_enabled": context.live_trading_enabled,
        "real_orders_enabled": context.real_orders_enabled,
        "leverage_enabled": context.leverage_enabled,
        "shorting_enabled": context.shorting_enabled,
        "strategy_runtime_allowed": context.strategy_runtime_allowed,
        "entry_signals_allowed": context.entry_signals_allowed,
        "exit_signals_allowed": context.exit_signals_allowed,
        "reason_codes": list(context.reason_codes),
        "input_refs": {
            "freqtrade_bridge_context": context.input_refs.freqtrade_bridge_context,
            "strategy_context": context.input_refs.strategy_context,
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


def write_strategy_context(
    context: StrategyContext,
    target_path: Path | None = None,
) -> Path:
    """Write StrategyContext to JSON file.

    Args:
        context: StrategyContext to serialize.
        target_path: Destination path. Defaults to data/strategy/current_strategy_context.json.

    Returns:
        Path to written file.

    Raises:
        OSError: If write fails.
        TypeError: If serialization fails.
    """
    target_path = target_path or DEFAULT_STRATEGY_CONTEXT_PATH
    data = strategy_context_to_dict(context)
    atomic_write_json(data, target_path)
    return target_path
