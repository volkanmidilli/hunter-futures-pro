"""Deterministic SHA-256 fingerprints for research universe artifacts (MVP-64 / SPEC-065)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import is_dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from hunter.research_universe.models import (
    BaselineUniverseResult,
    CandidateUniverseResult,
    ResearchUniverseComparison,
    ResearchUniverseConfig,
)


def _serialize_value(value: Any) -> Any:
    """Serialize a value into a deterministic JSON-safe structure."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):  # noqa: F821
        if value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value.astimezone().isoformat()
    if isinstance(value, tuple):
        return [_serialize_value(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _serialize_value(v) for k, v in sorted(value.items())}
    if isinstance(value, list):
        return [_serialize_value(v) for v in value]
    if is_dataclass(value) and not isinstance(value, type):
        return _serialize_value(value.__dict__)
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def policy_fingerprint(config: ResearchUniverseConfig) -> str:
    """Deterministic SHA-256 fingerprint of the eligibility policy."""
    payload = _serialize_value(config)
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def candidate_universe_fingerprint(result: CandidateUniverseResult) -> str:
    """Deterministic SHA-256 fingerprint of the candidate universe."""
    payload = {
        "decisions": _serialize_value(result.decisions),
        "pairlist": _serialize_value(result.pairlist),
        "reason_codes": sorted(result.reason_codes),
    }
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def baseline_universe_fingerprint(result: BaselineUniverseResult) -> str:
    """Deterministic SHA-256 fingerprint of the baseline universe."""
    payload = {
        "decisions": _serialize_value(result.decisions),
        "pairlist": _serialize_value(result.pairlist),
        "reason_codes": sorted(result.reason_codes),
    }
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def universe_comparison_fingerprint(comparison: ResearchUniverseComparison) -> str:
    """Deterministic SHA-256 fingerprint of the universe comparison."""
    payload = {
        "overlap": sorted(comparison.overlap),
        "candidate_only": sorted(comparison.candidate_only),
        "baseline_only": sorted(comparison.baseline_only),
        "union_count": comparison.union_count,
        "jaccard_similarity": _serialize_value(comparison.jaccard_similarity),
        "reason_codes": sorted(comparison.reason_codes),
    }
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def report_fingerprint(payload: dict[str, Any]) -> str:
    """Deterministic SHA-256 fingerprint of a top-level report."""
    text = json.dumps(_serialize_value(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# Import datetime for _serialize_value runtime guard (already imported via typing if needed)
