"""JSON output writer for decision layer.

Serializes DecisionOutput to JSON files with atomic writes.
No network, no trading logic, no storage integration.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from hunter.decision.models import DecisionOutput, DecisionInputRefs
from hunter.market_state.models import DataQuality


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


def _serialize_input_refs(refs: DecisionInputRefs) -> Dict[str, str]:
    """Serialize DecisionInputRefs to dict."""
    return {
        "regime_timestamp": refs.regime_timestamp,
        "breadth_timestamp": refs.breadth_timestamp,
        "regime_source": refs.regime_source,
        "breadth_source": refs.breadth_source,
    }


def decision_to_dict(output: DecisionOutput) -> Dict[str, Any]:
    """Serialize DecisionOutput to JSON-compatible dict.

    Returns a dict matching SPEC-004 JSON contract.
    """
    return {
        "timestamp": _serialize_datetime(output.timestamp),
        "status": output.status.value,
        "decision_state": output.decision_state.value,
        "decision_action": output.decision_action.value,
        "allowed_mode": output.allowed_mode.value,
        "market_regime": output.market_regime.value,
        "risk_state": output.risk_state.value,
        "confidence": output.confidence,
        "regime_confidence": output.regime_confidence,
        "breadth_score": output.breadth_score,
        "market_health": output.market_health.value,
        "reason_codes": output.reason_codes,
        "input_refs": _serialize_input_refs(output.input_refs),
        "data_quality": _serialize_data_quality(output.data_quality),
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


def write_decision_output(
    output: DecisionOutput,
    target_path: Path | str = Path("data/decision/current_decision.json"),
) -> Path:
    """Write DecisionOutput to JSON file.

    Args:
        output: DecisionOutput to serialize.
        target_path: Destination path. Defaults to data/decision/current_decision.json.

    Returns:
        Path to written file.

    Raises:
        OSError: If write fails.
        TypeError: If serialization fails.
    """
    target_path = Path(target_path)
    data = decision_to_dict(output)
    atomic_write_json(data, target_path)
    return target_path
