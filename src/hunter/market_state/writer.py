"""JSON output writers for market state engines.

Serializes RegimeOutput and BreadthOutput to JSON files with atomic writes.
No network, no trading logic, no storage integration.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from hunter.market_state.models import (
    AllowedMode,
    BreadthOutput,
    DataQuality,
    OutputStatus,
    RegimeOutput,
    RegimeState,
    RiskState,
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


def _serialize_data_quality(dq: DataQuality) -> Dict[str, Any]:
    """Serialize DataQuality to dict."""
    return {
        "missing": dq.missing,
        "stale": dq.stale,
        "insufficient_history": dq.insufficient_history,
        "insufficient_universe": dq.insufficient_universe,
    }


def regime_to_dict(output: RegimeOutput) -> Dict[str, Any]:
    """Serialize RegimeOutput to JSON-compatible dict.

    Returns a dict matching SPEC-003 JSON contract.
    """
    return {
        "timestamp": _serialize_datetime(output.timestamp),
        "status": output.status.value,
        "market_regime": output.market_regime.value,
        "allowed_mode": output.allowed_mode.value,
        "confidence": output.confidence,
        "risk_state": output.risk_state.value,
        "btc_trend_score": output.btc_trend_score,
        "eth_trend_score": output.eth_trend_score,
        "breadth_confirmation_score": output.breadth_confirmation_score,
        "reason_codes": output.reason_codes,
        "data_quality": _serialize_data_quality(output.data_quality),
    }


def breadth_to_dict(output: BreadthOutput) -> Dict[str, Any]:
    """Serialize BreadthOutput to JSON-compatible dict.

    Returns a dict matching SPEC-003 JSON contract.
    """
    return {
        "timestamp": _serialize_datetime(output.timestamp),
        "status": output.status.value,
        "breadth_score": output.breadth_score,
        "market_health": output.market_health.value,
        "universe_size": output.universe_size,
        "valid_symbol_count": output.valid_symbol_count,
        "invalid_symbol_count": output.invalid_symbol_count,
        "above_ema20_pct": output.above_ema20_pct,
        "above_ema50_pct": output.above_ema50_pct,
        "above_ema200_pct": output.above_ema200_pct,
        "ema20_rising_pct": output.ema20_rising_pct,
        "ema50_rising_pct": output.ema50_rising_pct,
        "advancing_pct": output.advancing_pct,
        "declining_pct": output.declining_pct,
        "outperforming_btc_7d_pct": output.outperforming_btc_7d_pct,
        "outperforming_btc_30d_pct": output.outperforming_btc_30d_pct,
        "reason_codes": output.reason_codes,
        "data_quality": _serialize_data_quality(output.data_quality),
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


def write_regime_output(
    output: RegimeOutput,
    target_path: Path | str = Path("data/regime/current_regime.json"),
    overwrite: bool = False,
) -> Path:
    """Write RegimeOutput to JSON file.

    Args:
        output: RegimeOutput to serialize.
        target_path: Destination path. Defaults to data/regime/current_regime.json.
        overwrite: If False, refuse to overwrite an existing file.

    Returns:
        Path to written file.

    Raises:
        OSError: If write fails.
        TypeError: If serialization fails.
        FileExistsError: If target exists and overwrite is False.
    """
    target_path = Path(target_path)
    data = regime_to_dict(output)
    data["_safety_notice"] = _SAFETY_NOTICE
    atomic_write_json(data, target_path, overwrite=overwrite)
    return target_path


def write_breadth_output(
    output: BreadthOutput,
    target_path: Path | str = Path("data/breadth/current_breadth.json"),
    overwrite: bool = False,
) -> Path:
    """Write BreadthOutput to JSON file.

    Args:
        output: BreadthOutput to serialize.
        target_path: Destination path. Defaults to data/breadth/current_breadth.json.
        overwrite: If False, refuse to overwrite an existing file.

    Returns:
        Path to written file.

    Raises:
        OSError: If write fails.
        TypeError: If serialization fails.
        FileExistsError: If target exists and overwrite is False.
    """
    target_path = Path(target_path)
    data = breadth_to_dict(output)
    data["_safety_notice"] = _SAFETY_NOTICE
    atomic_write_json(data, target_path, overwrite=overwrite)
    return target_path
