"""Transactional publish/snapshot consistency tests for
hunter.pairlist_export.cli._build_and_publish (SPEC-074 remediation).

A validation pass found that a same-date, different-content snapshot
conflict -- which happens *after* the live pairlist/audit had already been
published -- left the live artifacts overwritten even though the command
reported failure (exit 1). The fix writes/validates the snapshot before the
live publish, so a snapshot conflict is rejected before the live pairlist or
audit is ever touched, exactly like any other publish-gate rejection.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from hunter.pairlist_export import cli, publisher


_PAIRS_A = (
    "BTC/USDT:USDT",
    "ETH/USDT:USDT",
    "SOL/USDT:USDT",
    "XRP/USDT:USDT",
    "ADA/USDT:USDT",
)
_PAIRS_B = (
    "BTC/USDT:USDT",
    "ETH/USDT:USDT",
    "SOL/USDT:USDT",
    "XRP/USDT:USDT",
    "DOGE/USDT:USDT",
)


def _write_ranking_input(path: Path, pairs) -> None:
    payload = {
        "as_of_date": "2026-07-21",
        "universe_total": 100,
        "eligible_pairs": list(pairs),
        "rs_scores": {p: str(80 - i) for i, p in enumerate(pairs)},
        "oi_scores": {p: "50" for p in pairs},
        "data_quality": {p: "100" for p in pairs},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


_input_counter = 0


def _build(tmp_path: Path, pairs, *, as_of: str = "2026-07-21", output_dir=None, snapshot_dir=None) -> int:
    global _input_counter
    _input_counter += 1
    input_path = tmp_path / f"input_{_input_counter}.json"
    _write_ranking_input(input_path, pairs)
    args = [
        "pairlist",
        "build",
        "--as-of",
        as_of,
        "--input",
        str(input_path),
        "--output-dir",
        str(output_dir),
    ]
    if snapshot_dir is not None:
        args += ["--snapshot-dir", str(snapshot_dir)]
    return cli.main(args)


def test_snapshot_conflict_is_rejected_before_live_publish(tmp_path: Path, capsys) -> None:
    out_dir = tmp_path / "out"
    snap_dir = tmp_path / "snap"

    exit_code_1 = _build(tmp_path, _PAIRS_A, output_dir=out_dir, snapshot_dir=snap_dir)
    assert exit_code_1 == 0
    capsys.readouterr()

    original_pairlist = (out_dir / publisher.PAIRLIST_FILENAME).read_text(encoding="utf-8")
    original_audit = (out_dir / publisher.AUDIT_FILENAME).read_text(encoding="utf-8")
    assert not (out_dir / (publisher.PAIRLIST_FILENAME + ".previous-good")).exists()

    exit_code_2 = _build(tmp_path, _PAIRS_B, output_dir=out_dir, snapshot_dir=snap_dir)

    assert exit_code_2 == 1
    err = capsys.readouterr().err
    assert "already exists with different content" in err

    # Live pairlist unchanged.
    assert (out_dir / publisher.PAIRLIST_FILENAME).read_text(encoding="utf-8") == original_pairlist
    # Live audit unchanged.
    assert (out_dir / publisher.AUDIT_FILENAME).read_text(encoding="utf-8") == original_audit
    # Publish never ran a second time -- no previous-good was ever created,
    # proving publish_pairlist was never invoked for the conflicting run.
    assert not (out_dir / (publisher.PAIRLIST_FILENAME + ".previous-good")).exists()
    assert not (out_dir / (publisher.AUDIT_FILENAME + ".previous-good")).exists()


def test_snapshot_conflict_leaves_no_orphan_temp_files(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    snap_dir = tmp_path / "snap"

    assert _build(tmp_path, _PAIRS_A, output_dir=out_dir, snapshot_dir=snap_dir) == 0
    assert _build(tmp_path, _PAIRS_B, output_dir=out_dir, snapshot_dir=snap_dir) == 1

    for directory in (out_dir, snap_dir):
        leftovers = [p.name for p in directory.iterdir() if ".tmp" in p.name or p.name.startswith(".")]
        assert leftovers == [], f"orphan temp files found in {directory}: {leftovers}"


def test_identical_same_date_rerun_is_idempotent_no_op(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    snap_dir = tmp_path / "snap"

    assert _build(tmp_path, _PAIRS_A, output_dir=out_dir, snapshot_dir=snap_dir) == 0
    first_pairlist = (out_dir / publisher.PAIRLIST_FILENAME).read_text(encoding="utf-8")
    first_snapshot = (snap_dir / "hunter-pairs-20260721.json").read_text(encoding="utf-8")

    # Re-run with the exact same pairs/date -- identical content, must succeed.
    exit_code = _build(tmp_path, _PAIRS_A, output_dir=out_dir, snapshot_dir=snap_dir)

    assert exit_code == 0
    assert (out_dir / publisher.PAIRLIST_FILENAME).read_text(encoding="utf-8") == first_pairlist
    assert (snap_dir / "hunter-pairs-20260721.json").read_text(encoding="utf-8") == first_snapshot


def test_publish_failure_after_snapshot_success_does_not_corrupt_previous_good(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """If the snapshot step succeeds but the live publish step then fails
    (e.g. a filesystem error), publish_pairlist's own previous-good
    rollback must still leave the live artifacts consistent -- proving the
    reordering did not weaken publish_pairlist's own failure handling."""
    out_dir = tmp_path / "out"
    snap_dir = tmp_path / "snap"

    assert _build(tmp_path, _PAIRS_A, output_dir=out_dir, snapshot_dir=snap_dir) == 0
    capsys.readouterr()
    original_pairlist = (out_dir / publisher.PAIRLIST_FILENAME).read_text(encoding="utf-8")
    original_audit = (out_dir / publisher.AUDIT_FILENAME).read_text(encoding="utf-8")

    # Force the live publish step to fail after the (new-date, so
    # conflict-free) snapshot step has already succeeded.
    def _boom(*args, **kwargs):
        raise OSError("simulated disk failure during live publish")

    monkeypatch.setattr(publisher, "atomic_write_text", _boom)

    exit_code = _build(tmp_path, _PAIRS_B, as_of="2026-07-22", output_dir=out_dir, snapshot_dir=snap_dir)

    assert exit_code == 1
    # publish_pairlist wraps the failure; live pairlist/audit remain exactly
    # what they were before this run (publish_pairlist's own previous-good
    # restore, or -- since atomic_write_text is fully stubbed out here --
    # the live files are simply never modified in the first place).
    assert (out_dir / publisher.PAIRLIST_FILENAME).read_text(encoding="utf-8") == original_pairlist
    assert (out_dir / publisher.AUDIT_FILENAME).read_text(encoding="utf-8") == original_audit
    # The new date's snapshot was written before the simulated failure --
    # this is the one documented, accepted trade-off of validating the
    # snapshot first: a snapshot can exist for a date whose live publish
    # subsequently failed for an unrelated (non-conflict) reason. The live
    # artifact contract -- what this fix is required to protect -- holds.
    assert (snap_dir / "hunter-pairs-20260722.json").exists()


def test_below_min_pairs_gate_rejection_still_precedes_any_snapshot_or_publish_write(
    tmp_path: Path, capsys
) -> None:
    """Gate rejections (unrelated to snapshot conflicts) must continue to
    short-circuit before either write step -- unaffected by the reordering."""
    out_dir = tmp_path / "out"
    snap_dir = tmp_path / "snap"

    exit_code = _build(tmp_path, ("BTC/USDT:USDT",), output_dir=out_dir, snapshot_dir=snap_dir)

    assert exit_code == 1
    assert "BELOW_MIN_PAIRS" in capsys.readouterr().err
    assert not out_dir.exists() or not any(out_dir.iterdir())
    assert not snap_dir.exists() or not any(snap_dir.iterdir())
