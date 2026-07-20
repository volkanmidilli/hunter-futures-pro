"""Deterministic, wall-clock-free fingerprinting for pairlist export artifacts.

Fingerprints are content-only hashes: two invocations built from identical
domain data always produce identical fingerprints, regardless of when they
run.  No field derived from ``datetime.now()`` or similar may enter any
hashed payload in this module.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Any


def _canonicalize(value: Any) -> Any:
    """Recursively convert ``value`` into a JSON-stable canonical form.

    ``Decimal`` values are rendered as strings (to avoid float rounding
    drift across platforms).  Mapping order is normalized by
    ``json.dumps(sort_keys=True)`` at the final encoding step; sequence
    order is preserved since ranking order is semantically meaningful.
    """
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _canonicalize(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonicalize(item) for item in value]
    if isinstance(value, frozenset):
        return sorted(_canonicalize(item) for item in value)
    return value


def canonical_json(payload: Any) -> str:
    """Encode ``payload`` as canonical, deterministic JSON text."""
    canonical = _canonicalize(payload)
    return json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_hex(text: str) -> str:
    """Return the hex-encoded SHA-256 digest of ``text``."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def fingerprint_payload(payload: Any) -> str:
    """Compute a deterministic SHA-256 fingerprint over ``payload``.

    ``payload`` must contain no wall-clock-derived values.
    """
    return sha256_hex(canonical_json(payload))


def compute_pair_fingerprint(
    pair: str,
    rank: int,
    rs_score: Decimal | None,
    oi_score: Decimal | None,
    data_quality_pct: Decimal | None,
    reason_codes: tuple[str, ...],
) -> str:
    """Fingerprint a single ranked pair's identity and evidence."""
    return fingerprint_payload(
        {
            "pair": pair,
            "rank": rank,
            "rs_score": rs_score,
            "oi_score": oi_score,
            "data_quality_pct": data_quality_pct,
            "reason_codes": list(reason_codes),
        }
    )


def compute_pairlist_fingerprint(pairs: tuple[str, ...], refresh_period: int) -> str:
    """Fingerprint the published RemotePairList content (pairs + refresh_period)."""
    return fingerprint_payload({"pairs": list(pairs), "refresh_period": refresh_period})


def compute_audit_fingerprint(
    as_of_date: str,
    universe_total: int,
    eligible_count: int,
    selected_count: int,
    rejected_count: int,
    selected_fingerprints: tuple[str, ...],
    rejected_fingerprints: tuple[str, ...],
    reason_code_summary: dict[str, int],
) -> str:
    """Fingerprint the audit record's semantic content (excludes itself)."""
    return fingerprint_payload(
        {
            "as_of_date": as_of_date,
            "universe_total": universe_total,
            "eligible_count": eligible_count,
            "selected_count": selected_count,
            "rejected_count": rejected_count,
            "selected_fingerprints": list(selected_fingerprints),
            "rejected_fingerprints": list(rejected_fingerprints),
            "reason_code_summary": dict(reason_code_summary),
        }
    )
