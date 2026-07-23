"""Immutable JSON snapshot audit artifact reader (SPEC-076).

Discovers and validates ``hunter-pairs-YYYYMMDD-audit.json`` artifacts under
an operator-supplied ``--snapshot-dir``.  Field names are verified against
the SPEC-074/075 writer contract (``audit_record_to_dict``): ``as_of_date``,
``ranking_profile``, ``selected[].pair``, ``selected[].rank``,
``selected[].rs_score``, ``selected[].liquidity_score``.

Snapshots are the only cohort-membership source; historical rankings are
never recomputed.  Read-only: snapshot files are never modified.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from hunter.research_outcome_evaluation.errors import SnapshotValidationError
from hunter.research_outcome_evaluation.models import parse_decimal

SNAPSHOT_AUDIT_FILENAME_RE = re.compile(r"^hunter-pairs-(?P<day>\d{8})-audit\.json$")


@dataclass(frozen=True)
class SnapshotPairEntry:
    """One selected pair from an immutable snapshot audit artifact."""

    pair: str
    rank: int
    relative_strength_score: Decimal | None
    liquidity_score: Decimal | None


@dataclass(frozen=True)
class SnapshotCohort:
    """A validated immutable snapshot: the cohort-membership source."""

    snapshot_date: str
    ranking_profile: str
    entries: tuple[SnapshotPairEntry, ...]
    source_path: Path
    source_fingerprint: str


def discover_snapshot_audits(snapshot_dir: Path) -> tuple[Path, ...]:
    """Return sorted ``hunter-pairs-YYYYMMDD-audit.json`` paths under ``snapshot_dir``.

    Non-recursive; hidden/temp files are ignored.
    """
    snapshot_dir = Path(snapshot_dir)
    if not snapshot_dir.is_dir():
        raise SnapshotValidationError(
            f"snapshot-dir does not exist or is not a directory: {snapshot_dir}"
        )
    matched = [
        entry
        for entry in snapshot_dir.iterdir()
        if entry.is_file()
        and not entry.name.startswith(".")
        and SNAPSHOT_AUDIT_FILENAME_RE.match(entry.name)
    ]
    return tuple(sorted(matched, key=lambda p: p.name))


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SnapshotValidationError(message)


def _parse_entry(raw: object, path: Path) -> SnapshotPairEntry:
    _require(isinstance(raw, dict), f"snapshot {path}: selected entry is not an object")
    assert isinstance(raw, dict)
    pair = raw.get("pair")
    rank = raw.get("rank")
    _require(isinstance(pair, str) and bool(pair), f"snapshot {path}: entry missing 'pair'")
    _require(
        isinstance(rank, int) and not isinstance(rank, bool) and rank >= 1,
        f"snapshot {path}: entry for {pair!r} has invalid 'rank'",
    )
    try:
        rs_score = parse_decimal(raw.get("rs_score"))
        liquidity_score = parse_decimal(raw.get("liquidity_score"))
    except ValueError as exc:
        raise SnapshotValidationError(
            f"snapshot {path}: entry for {pair!r} has invalid score: {exc}"
        ) from exc
    return SnapshotPairEntry(
        pair=pair,
        rank=rank,
        relative_strength_score=rs_score,
        liquidity_score=liquidity_score,
    )


def load_snapshot_audit(path: Path) -> SnapshotCohort:
    """Load and validate one immutable snapshot audit artifact.

    Raises :class:`SnapshotValidationError` on any structural failure; the
    caller maps this to ``SNAPSHOT_INVALID`` for every cohort member.
    """
    path = Path(path)
    name_match = SNAPSHOT_AUDIT_FILENAME_RE.match(path.name)
    _require(name_match is not None, f"snapshot filename not recognized: {path.name}")

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SnapshotValidationError(f"snapshot {path}: unreadable JSON: {exc}") from exc

    _require(isinstance(raw, dict), f"snapshot {path}: top level is not an object")
    assert isinstance(raw, dict)

    as_of_date = raw.get("as_of_date")
    _require(
        isinstance(as_of_date, str),
        f"snapshot {path}: missing 'as_of_date'",
    )
    try:
        parsed_date = date.fromisoformat(as_of_date)
    except ValueError as exc:
        raise SnapshotValidationError(
            f"snapshot {path}: invalid 'as_of_date': {as_of_date!r}"
        ) from exc

    filename_day = name_match.group("day")
    _require(
        parsed_date.strftime("%Y%m%d") == filename_day,
        f"snapshot {path}: as_of_date {as_of_date!r} does not match filename date",
    )

    ranking_profile = raw.get("ranking_profile")
    _require(
        isinstance(ranking_profile, str) and bool(ranking_profile),
        f"snapshot {path}: missing 'ranking_profile'",
    )

    selected = raw.get("selected")
    _require(
        isinstance(selected, list),
        f"snapshot {path}: 'selected' is not a list",
    )

    entries = tuple(_parse_entry(item, path) for item in selected)
    pairs = [entry.pair for entry in entries]
    _require(
        len(set(pairs)) == len(pairs),
        f"snapshot {path}: duplicate pairs in 'selected'",
    )

    fingerprint = raw.get("fingerprint")
    _require(
        isinstance(fingerprint, str),
        f"snapshot {path}: missing 'fingerprint'",
    )

    return SnapshotCohort(
        snapshot_date=as_of_date,
        ranking_profile=ranking_profile,
        entries=entries,
        source_path=path,
        source_fingerprint=fingerprint,
    )
