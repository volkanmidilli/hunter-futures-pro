"""Atomic artifact storage for SPEC-078 explainability records.

Layout (runtime artifacts, never Git-tracked source)::

    <explainability_dir>/
      runs/
        <run_id>/
          manifest.json
          candidates/
            BTC_USDT_USDT.json
            ETH_USDT_USDT.json
      latest.json          # atomic pointer to the latest *successful* run

Write discipline reuses the existing SPEC-074 infrastructure
(``atomic_write_text`` -- tempfile, flush, fsync, ``os.replace`` -- and
``reject_forbidden_output_dir``).  Run artifacts follow snapshot
immutability semantics (identical re-run content is a no-op; differing
content for the same run id is rejected).  The ``latest.json`` pointer is
updated only when the caller confirms a successful run, so a failed or
incomplete run never replaces the latest successful run.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from hunter.explainability.models import (
    CandidateExplanationRecord,
    ExplainabilityModelError,
    ExplainabilityRunManifest,
    ExplainabilityStorageError,
)
from hunter.pairlist_export.publisher import atomic_write_text, reject_forbidden_output_dir

RUNS_DIRNAME = "runs"
CANDIDATES_DIRNAME = "candidates"
MANIFEST_FILENAME = "manifest.json"
LATEST_FILENAME = "latest.json"

_REPO_ROOT = Path(__file__).resolve().parents[3]

_SAFE_RUN_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


def default_explainability_dir() -> Path:
    """Default runtime artifact root: ``<repo-root>/explainability/``."""
    return _REPO_ROOT / "explainability"


def candidate_filename(pair: str) -> str:
    """Deterministic candidate artifact filename, e.g. ``BTC_USDT_USDT.json``."""
    return pair.replace("/", "_").replace(":", "_") + ".json"


def _canonical(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _comparison_text(payload: dict[str, Any]) -> str:
    """Canonical text used for the immutability comparison.

    ``completed_at`` is wall-clock run metadata, not pipeline output, so it
    is excluded: an identical re-run of the pipeline must be a no-op even
    though its timestamp differs.
    """
    comparable = {k: v for k, v in payload.items() if k != "completed_at"}
    return _canonical(comparable)


def _write_immutable(path: Path, payload: dict[str, Any]) -> None:
    """Write atomically unless an equivalent artifact already exists.

    Raises :class:`ExplainabilityStorageError` when existing content
    differs beyond ``completed_at`` (snapshot immutability semantics,
    matching the SPEC-074/076 stores).
    """
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ExplainabilityStorageError(
                f"existing artifact is unreadable, refusing to overwrite: {path}"
            ) from exc
        if isinstance(existing, dict) and _comparison_text(existing) == _comparison_text(payload):
            return
        raise ExplainabilityStorageError(
            f"artifact already exists with different content: {path}"
        )
    atomic_write_text(path, _canonical(payload))


def _validate_run_id(run_id: str) -> None:
    if not _SAFE_RUN_ID_RE.match(run_id):
        raise ExplainabilityStorageError(f"unsafe run_id: {run_id!r}")


def run_dir(explainability_dir: Path, run_id: str) -> Path:
    _validate_run_id(run_id)
    return Path(explainability_dir) / RUNS_DIRNAME / run_id


def write_run(
    explainability_dir: Path,
    manifest: ExplainabilityRunManifest,
    records: tuple[CandidateExplanationRecord, ...],
    *,
    update_latest: bool,
) -> Path:
    """Atomically persist one run's manifest and candidate records.

    Every candidate record and the manifest are written (or confirmed
    identical) first; only then, and only when ``update_latest`` is true
    (a successful run: gate allowed and publish completed), is the
    ``latest.json`` pointer advanced.  A failed or incomplete run
    (``update_latest=False``) still persists its artifacts for forensics
    but never replaces the latest-successful-run pointer.

    Returns the run directory.
    """
    explainability_dir = Path(explainability_dir)
    reject_forbidden_output_dir(explainability_dir)
    target = run_dir(explainability_dir, manifest.run_id)
    candidates_dir = target / CANDIDATES_DIRNAME

    for record in records:
        if record.run_id != manifest.run_id:
            raise ExplainabilityStorageError(
                f"candidate record run_id {record.run_id!r} does not match "
                f"manifest run_id {manifest.run_id!r}"
            )
        _write_immutable(candidates_dir / candidate_filename(record.pair), record.to_dict())
    _write_immutable(target / MANIFEST_FILENAME, manifest.to_dict())

    if update_latest:
        pointer = {
            "schema_version": manifest.schema_version,
            "run_id": manifest.run_id,
            "completed_at": manifest.completed_at,
        }
        atomic_write_text(explainability_dir / LATEST_FILENAME, _canonical(pointer))

    return target


# ---------------------------------------------------------------------------
# Read path (used by the explain service)
# ---------------------------------------------------------------------------


def read_latest_pointer(explainability_dir: Path) -> dict[str, Any] | None:
    """Return the latest-run pointer, or None when no successful run exists.

    Raises :class:`ExplainabilityStorageError` when the pointer exists but
    is unreadable or malformed (handled as ``ARTIFACT_INVALID`` upstream).
    """
    path = Path(explainability_dir) / LATEST_FILENAME
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExplainabilityStorageError(f"latest pointer is unreadable: {path}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("run_id"), str):
        raise ExplainabilityStorageError(f"latest pointer is malformed: {path}")
    return payload


def read_manifest(explainability_dir: Path, run_id: str) -> ExplainabilityRunManifest:
    """Load and validate a run manifest.

    Raises :class:`ExplainabilityStorageError` when the manifest is missing
    or invalid (mapped to ``ARTIFACT_INVALID`` upstream).
    """
    path = run_dir(explainability_dir, run_id) / MANIFEST_FILENAME
    if not path.exists():
        raise ExplainabilityStorageError(f"run manifest missing: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return ExplainabilityRunManifest.from_dict(payload)
    except (OSError, json.JSONDecodeError, ExplainabilityModelError) as exc:
        raise ExplainabilityStorageError(f"run manifest invalid: {path}") from exc


def read_candidate(
    explainability_dir: Path, run_id: str, pair: str
) -> CandidateExplanationRecord | None:
    """Load and validate one candidate record, or None when not recorded.

    Raises :class:`ExplainabilityStorageError` when the artifact exists but
    is corrupt (mapped to ``ARTIFACT_INVALID`` upstream).
    """
    path = run_dir(explainability_dir, run_id) / CANDIDATES_DIRNAME / candidate_filename(pair)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return CandidateExplanationRecord.from_dict(payload)
    except (OSError, json.JSONDecodeError, ExplainabilityModelError) as exc:
        raise ExplainabilityStorageError(f"candidate artifact invalid: {path}") from exc
