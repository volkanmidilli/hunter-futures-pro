"""Atomic writer for daily pairlist export artifacts (SPEC-074).

Writes the RemotePairList JSON and the audit JSON via tempfile + flush +
fsync + ``os.replace``, preserving the previous-good pair of files first so
a failed publish never leaves a partial or inconsistent artifact live.
Hunter never inspects or modifies the repository's ``data/`` or ``reports/``
trees; :func:`reject_forbidden_output_dir` enforces that for every publish
and snapshot destination.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from hunter.pairlist_export.audit import audit_record_to_dict
from hunter.pairlist_export.models import PairlistOutput, PairlistPublishError

# src/hunter/pairlist_export/publisher.py -> src/hunter/pairlist_export -> src/hunter -> src -> repo root
_REPO_ROOT = Path(__file__).resolve().parents[3]
_FORBIDDEN_DIRS = (_REPO_ROOT / "data", _REPO_ROOT / "reports")

PAIRLIST_FILENAME = "hunter-pairs.json"
AUDIT_FILENAME = "hunter-pairs-audit.json"


def reject_forbidden_output_dir(output_dir: Path) -> None:
    """Raise :class:`PairlistPublishError` if ``output_dir`` targets a
    repository ``data/`` or ``reports/`` tree.

    SPEC-074 requires Hunter never inspect or modify those directories;
    publish output must always go to an operator-chosen deployment path
    (e.g. Freqtrade's ``user_data/pairlists``).
    """
    resolved = Path(output_dir).resolve()
    for forbidden in _FORBIDDEN_DIRS:
        forbidden_resolved = forbidden.resolve()
        if resolved == forbidden_resolved or forbidden_resolved in resolved.parents:
            raise PairlistPublishError(
                f"output-dir must not target the repository {forbidden.name}/ tree: {resolved}"
            )


def atomic_write_text(path: Path, content: str) -> None:
    """Write ``content`` to ``path`` atomically: tempfile, flush, fsync, replace.

    The temp file lives in the same directory as ``path`` so ``os.replace``
    is a same-filesystem rename (atomic on POSIX).  The parent directory is
    fsynced after the rename so the new directory entry survives a crash.
    """
    path = Path(path)
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(dir=str(parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, str(path))
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise

    dir_fd = os.open(str(parent), os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def _previous_good_path(path: Path) -> Path:
    return path.with_name(path.name + ".previous-good")


def pairlist_payload_dict(output: PairlistOutput) -> dict:
    """Build the native RemotePairList JSON payload from a PairlistOutput."""
    return {"pairs": list(output.pairs), "refresh_period": output.refresh_period}


def publish_pairlist(
    output: PairlistOutput,
    output_dir: Path,
    pairlist_filename: str = PAIRLIST_FILENAME,
    audit_filename: str = AUDIT_FILENAME,
) -> tuple[Path, Path]:
    """Atomically publish the pairlist and audit JSON files.

    Preserves the current live files as ``*.previous-good`` before
    overwriting.  If either write fails, both files are restored to their
    previous-good state (or removed, if this was the first-ever publish)
    so the pairlist/audit pair is never left inconsistent.

    Args:
        output: Gate-approved :class:`PairlistOutput` to publish.
        output_dir: Destination directory (must not be the repository
            ``data/`` or ``reports/`` tree).
        pairlist_filename: Live pairlist filename.
        audit_filename: Live audit filename.

    Returns:
        ``(pairlist_path, audit_path)`` of the newly published files.

    Raises:
        PairlistPublishError: On any I/O failure.  The previous-good state
            is restored (or the partial write rolled back) before the
            error propagates -- publish is fail-closed.
    """
    output_dir = Path(output_dir)
    reject_forbidden_output_dir(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    pairlist_path = output_dir / pairlist_filename
    audit_path = output_dir / audit_filename
    previous_good_pairlist = _previous_good_path(pairlist_path)
    previous_good_audit = _previous_good_path(audit_path)

    pairlist_text = json.dumps(pairlist_payload_dict(output), indent=2, sort_keys=True) + "\n"
    audit_text = json.dumps(audit_record_to_dict(output.audit), indent=2, sort_keys=True) + "\n"

    had_previous_pairlist = pairlist_path.exists()
    had_previous_audit = audit_path.exists()
    try:
        if had_previous_pairlist:
            atomic_write_text(previous_good_pairlist, pairlist_path.read_text(encoding="utf-8"))
        if had_previous_audit:
            atomic_write_text(previous_good_audit, audit_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise PairlistPublishError(f"failed to preserve previous-good snapshot: {exc}") from exc

    try:
        atomic_write_text(pairlist_path, pairlist_text)
        atomic_write_text(audit_path, audit_text)
    except Exception as exc:
        if had_previous_pairlist:
            atomic_write_text(pairlist_path, previous_good_pairlist.read_text(encoding="utf-8"))
        elif pairlist_path.exists():
            pairlist_path.unlink()
        if had_previous_audit:
            atomic_write_text(audit_path, previous_good_audit.read_text(encoding="utf-8"))
        elif audit_path.exists():
            audit_path.unlink()
        raise PairlistPublishError(f"publish failed, previous-good restored: {exc}") from exc

    return pairlist_path, audit_path
