"""M2 tests: immutable JSON snapshot audit reader."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from hunter.research_outcome_evaluation.errors import SnapshotValidationError
from hunter.research_outcome_evaluation.snapshot_reader import (
    discover_snapshot_audits,
    load_snapshot_audit,
)


def _audit_payload(**overrides: object) -> dict:
    payload: dict = {
        "as_of_date": "2026-01-10",
        "ranking_profile": "V2_RS_LIQUIDITY",
        "schema_version": "hunter-ranking-input-v2",
        "selected": [
            {
                "pair": "SOL/USDT:USDT",
                "rank": 1,
                "selected": True,
                "rs_score": "55.5",
                "liquidity_score": "77.7",
                "reason_codes": ["RS_SCORE"],
                "fingerprint": "abc",
            },
            {
                "pair": "AVAX/USDT:USDT",
                "rank": 2,
                "selected": True,
                "rs_score": None,
                "reason_codes": [],
                "fingerprint": "def",
            },
        ],
        "fingerprint": "topfp",
    }
    payload.update(overrides)
    return payload


def _write_snapshot(directory: Path, name: str = "hunter-pairs-20260110-audit.json", **overrides: object) -> Path:
    path = directory / name
    path.write_text(json.dumps(_audit_payload(**overrides)), encoding="utf-8")
    return path


def test_discover_snapshot_audits_sorted(tmp_path: Path) -> None:
    _write_snapshot(tmp_path, "hunter-pairs-20260111-audit.json", as_of_date="2026-01-11")
    _write_snapshot(tmp_path)
    (tmp_path / "other.json").write_text("{}", encoding="utf-8")
    (tmp_path / ".hidden-audit.json").write_text("{}", encoding="utf-8")
    found = discover_snapshot_audits(tmp_path)
    assert [p.name for p in found] == [
        "hunter-pairs-20260110-audit.json",
        "hunter-pairs-20260111-audit.json",
    ]


def test_discover_missing_dir(tmp_path: Path) -> None:
    with pytest.raises(SnapshotValidationError):
        discover_snapshot_audits(tmp_path / "nope")


def test_load_valid_snapshot(tmp_path: Path) -> None:
    path = _write_snapshot(tmp_path)
    cohort = load_snapshot_audit(path)
    assert cohort.snapshot_date == "2026-01-10"
    assert cohort.ranking_profile == "V2_RS_LIQUIDITY"
    assert len(cohort.entries) == 2
    first, second = cohort.entries
    assert first.pair == "SOL/USDT:USDT"
    assert first.rank == 1
    assert first.relative_strength_score == Decimal("55.5")
    assert first.liquidity_score == Decimal("77.7")
    assert second.relative_strength_score is None
    assert second.liquidity_score is None
    assert cohort.source_fingerprint == "topfp"


def test_liquidity_score_absent_key_is_none(tmp_path: Path) -> None:
    payload = _audit_payload()
    del payload["selected"][0]["liquidity_score"]
    path = tmp_path / "hunter-pairs-20260110-audit.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    cohort = load_snapshot_audit(path)
    assert cohort.entries[0].liquidity_score is None


def test_rejects_unreadable_json(tmp_path: Path) -> None:
    path = tmp_path / "hunter-pairs-20260110-audit.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(SnapshotValidationError):
        load_snapshot_audit(path)


def test_rejects_date_filename_mismatch(tmp_path: Path) -> None:
    path = _write_snapshot(tmp_path, as_of_date="2026-01-09")
    with pytest.raises(SnapshotValidationError, match="does not match"):
        load_snapshot_audit(path)


def test_rejects_missing_ranking_profile(tmp_path: Path) -> None:
    path = _write_snapshot(tmp_path, ranking_profile=None)
    with pytest.raises(SnapshotValidationError, match="ranking_profile"):
        load_snapshot_audit(path)


def test_rejects_missing_rank(tmp_path: Path) -> None:
    payload = _audit_payload()
    del payload["selected"][0]["rank"]
    path = tmp_path / "hunter-pairs-20260110-audit.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(SnapshotValidationError, match="rank"):
        load_snapshot_audit(path)


def test_rejects_bool_rank(tmp_path: Path) -> None:
    payload = _audit_payload()
    payload["selected"][0]["rank"] = True
    path = tmp_path / "hunter-pairs-20260110-audit.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(SnapshotValidationError):
        load_snapshot_audit(path)


def test_rejects_duplicate_pairs(tmp_path: Path) -> None:
    payload = _audit_payload()
    payload["selected"].append(dict(payload["selected"][0]))
    path = tmp_path / "hunter-pairs-20260110-audit.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(SnapshotValidationError, match="duplicate"):
        load_snapshot_audit(path)


def test_rejects_invalid_score(tmp_path: Path) -> None:
    payload = _audit_payload()
    payload["selected"][0]["rs_score"] = "not-a-number"
    path = tmp_path / "hunter-pairs-20260110-audit.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(SnapshotValidationError, match="score"):
        load_snapshot_audit(path)


def test_rejects_selected_not_list(tmp_path: Path) -> None:
    path = _write_snapshot(tmp_path, selected={"pair": "X"})
    with pytest.raises(SnapshotValidationError):
        load_snapshot_audit(path)
