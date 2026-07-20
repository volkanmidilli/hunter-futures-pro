"""Dated static snapshot writer for daily pairlist publishes (SPEC-074).

Every successful publish preserves an immutable, dated snapshot pair:
``hunter-pairs-YYYYMMDD.json`` and ``hunter-pairs-YYYYMMDD-audit.json``.
Historical backtests must replay these static snapshots rather than
retrospectively rerunning dynamic filters.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from hunter.pairlist_export.audit import audit_record_to_dict
from hunter.pairlist_export.models import PairlistOutput, PairlistPublishError
from hunter.pairlist_export.publisher import (
    atomic_write_text,
    pairlist_payload_dict,
    reject_forbidden_output_dir,
)


def _compact_date(as_of_date: str) -> str:
    parsed = date.fromisoformat(as_of_date)
    return parsed.strftime("%Y%m%d")


def snapshot_filenames(as_of_date: str) -> tuple[str, str]:
    """Return ``(pairlist_filename, audit_filename)`` for ``as_of_date``."""
    compact = _compact_date(as_of_date)
    return f"hunter-pairs-{compact}.json", f"hunter-pairs-{compact}-audit.json"


def write_snapshot(output: PairlistOutput, snapshot_dir: Path) -> tuple[Path, Path]:
    """Write the dated static snapshot pair for ``output``.

    Snapshots are immutable: if a snapshot already exists for this
    as-of-date with *different* content, this raises
    :class:`PairlistPublishError` rather than silently overwriting a
    historical artifact that backtests may depend on.  Re-running with
    identical content is a no-op success (idempotent reruns).

    Args:
        output: Gate-approved :class:`PairlistOutput` to snapshot.
        snapshot_dir: Destination directory (must not be the repository
            ``data/`` or ``reports/`` tree).

    Returns:
        ``(pairlist_path, audit_path)`` of the snapshot files.
    """
    snapshot_dir = Path(snapshot_dir)
    reject_forbidden_output_dir(snapshot_dir)

    pairlist_name, audit_name = snapshot_filenames(output.audit.as_of_date)
    pairlist_path = snapshot_dir / pairlist_name
    audit_path = snapshot_dir / audit_name

    pairlist_text = json.dumps(pairlist_payload_dict(output), indent=2, sort_keys=True) + "\n"
    audit_text = json.dumps(audit_record_to_dict(output.audit), indent=2, sort_keys=True) + "\n"

    for path, text, label in (
        (pairlist_path, pairlist_text, "pairlist"),
        (audit_path, audit_text, "audit"),
    ):
        if path.exists():
            existing = path.read_text(encoding="utf-8")
            if existing != text:
                raise PairlistPublishError(
                    f"snapshot {label} for {output.audit.as_of_date} already exists "
                    f"with different content: {path}"
                )
            continue
        atomic_write_text(path, text)

    return pairlist_path, audit_path
