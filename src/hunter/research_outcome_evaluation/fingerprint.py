"""Deterministic identifiers and fingerprints for SPEC-076 records.

Fingerprints are SHA-256 over canonical JSON (sorted keys) of semantic
fields only: paths, wall-clock timestamps, hostnames, insertion order,
``fingerprint``, ``metadata``, ``safety_flags``, and ``_safety_notice``
are excluded.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

_EXCLUDED_KEYS = frozenset({"fingerprint", "metadata", "safety_flags", "_safety_notice"})


def _canonical(payload: Mapping[str, Any]) -> str:
    filtered = {k: v for k, v in payload.items() if k not in _EXCLUDED_KEYS}
    return json.dumps(filtered, sort_keys=True, separators=(",", ":"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def compute_snapshot_id(snapshot_date: str, ranking_profile: str) -> str:
    """Deterministic snapshot identifier."""
    return sha256_text(f"{snapshot_date}|{ranking_profile}")


def compute_observation_id(snapshot_id: str, pair: str, outcome_horizon: str) -> str:
    """Deterministic observation identifier."""
    return sha256_text(f"{snapshot_id}|{pair}|{outcome_horizon}")


def compute_summary_id(snapshot_date: str, ranking_profile: str, outcome_horizon: str) -> str:
    """Deterministic summary identifier."""
    return sha256_text(f"{snapshot_date}|{ranking_profile}|{outcome_horizon}")


def compute_record_fingerprint(payload: Mapping[str, Any]) -> str:
    """Fingerprint of a serialized record payload (semantic fields only)."""
    return sha256_text(_canonical(payload))
