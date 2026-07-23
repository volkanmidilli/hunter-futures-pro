"""Append-only evaluation store writer for SPEC-076 (SPEC-074 discipline).

Pair Observation Records persist under ``--store-dir/observations/`` and
Snapshot Summary Records under ``--store-dir/summaries/``, one deterministic
JSON artifact per (snapshot_date, ranking_profile, outcome_horizon).

Atomic persistence reuses the SPEC-074 discipline (temporary file, flush,
fsync, ``os.replace``) via ``atomic_write_text``.  Existing-file behavior
follows snapshot immutability semantics: identical content is a no-op,
differing content is rejected.  Records are written exactly once at
terminal resolution and are immutable after creation.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from hunter.pairlist_export.publisher import atomic_write_text, reject_forbidden_output_dir
from hunter.research_outcome_evaluation.errors import EvaluationStoreError
from hunter.research_outcome_evaluation.models import (
    PairObservationRecord,
    SnapshotSummaryRecord,
    pair_observation_to_dict,
    snapshot_summary_to_dict,
)

OBSERVATIONS_DIRNAME = "observations"
SUMMARIES_DIRNAME = "summaries"
STORE_SCHEMA_VERSION = "spec-076-store-v1"

_SAFE_TOKEN_RE = re.compile(r"[^A-Za-z0-9_.-]+")


def _safe_token(value: str) -> str:
    return _SAFE_TOKEN_RE.sub("_", value)


def artifact_stem(snapshot_date: str, ranking_profile: str, outcome_horizon: str) -> str:
    """Deterministic artifact stem for one cohort."""
    return f"{snapshot_date}__{_safe_token(ranking_profile)}__{_safe_token(outcome_horizon)}"


def _write_immutable(path: Path, payload: dict) -> bool:
    """Write ``payload`` atomically unless an identical artifact exists.

    Returns True when the file was written, False for an identical-content
    no-op.  Raises :class:`EvaluationStoreError` when existing content
    differs (snapshot immutability semantics).
    """
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if existing == text:
            return False
        raise EvaluationStoreError(
            f"artifact already exists with different content: {path}"
        )
    atomic_write_text(path, text)
    return True


def write_observations(
    *,
    store_dir: Path,
    snapshot_date: str,
    ranking_profile: str,
    outcome_horizon: str,
    records: tuple[PairObservationRecord, ...],
) -> Path:
    """Persist one cohort's Pair Observation Records exactly once."""
    store_dir = Path(store_dir)
    reject_forbidden_output_dir(store_dir)
    path = (
        store_dir
        / OBSERVATIONS_DIRNAME
        / f"{artifact_stem(snapshot_date, ranking_profile, outcome_horizon)}.json"
    )
    payload = {
        "schema_version": STORE_SCHEMA_VERSION,
        "snapshot_date": snapshot_date,
        "ranking_profile": ranking_profile,
        "outcome_horizon": outcome_horizon,
        "records": [pair_observation_to_dict(record) for record in records],
    }
    _write_immutable(path, payload)
    return path


def write_summary(
    *,
    store_dir: Path,
    summary: SnapshotSummaryRecord,
) -> Path:
    """Persist one Snapshot Summary Record exactly once."""
    store_dir = Path(store_dir)
    reject_forbidden_output_dir(store_dir)
    path = (
        store_dir
        / SUMMARIES_DIRNAME
        / f"{artifact_stem(summary.snapshot_date, summary.ranking_profile, summary.outcome_horizon)}.json"
    )
    _write_immutable(path, snapshot_summary_to_dict(summary))
    return path


def load_summary_artifacts(store_dir: Path) -> tuple[dict, ...]:
    """Read every persisted Snapshot Summary artifact (reporting path)."""
    store_dir = Path(store_dir)
    summaries_dir = store_dir / SUMMARIES_DIRNAME
    if not summaries_dir.is_dir():
        return ()
    payloads = []
    for path in sorted(summaries_dir.glob("*.json"), key=lambda p: p.name):
        payloads.append(json.loads(path.read_text(encoding="utf-8")))
    return tuple(payloads)
