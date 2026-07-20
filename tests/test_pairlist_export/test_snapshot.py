"""Focused tests for hunter.pairlist_export.snapshot (SPEC-074)."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from hunter.pairlist_export.models import PairlistPublishError, PairlistRankingConfig
from hunter.pairlist_export.ranking_adapter import rank_pairs
from hunter.pairlist_export.snapshot import snapshot_filenames, write_snapshot
from hunter.pairlist_export.validator import run_publish_gate


def _gate_output(as_of_date="2026-07-21", pairs=("BTC/USDT:USDT", "ETH/USDT:USDT")):
    config = PairlistRankingConfig(min_pairs=1, publish_candidates=5, max_pairs=5)
    ranked = rank_pairs(
        config,
        pairs,
        rs_scores={p: Decimal("80") - i for i, p in enumerate(pairs)},
        oi_scores={p: Decimal("50") for p in pairs},
    )
    result = run_publish_gate(config, as_of_date, 10, ranked)
    assert result.allow_publish is True
    return result.pairlist_output


def test_snapshot_filenames_are_compact_dated_and_paired() -> None:
    pairlist_name, audit_name = snapshot_filenames("2026-07-21")
    assert pairlist_name == "hunter-pairs-20260721.json"
    assert audit_name == "hunter-pairs-20260721-audit.json"


def test_write_snapshot_creates_dated_files(tmp_path: Path) -> None:
    output = _gate_output()
    pairlist_path, audit_path = write_snapshot(output, tmp_path)

    assert pairlist_path.name == "hunter-pairs-20260721.json"
    assert audit_path.name == "hunter-pairs-20260721-audit.json"
    assert json.loads(pairlist_path.read_text(encoding="utf-8"))["pairs"] == [
        "BTC/USDT:USDT",
        "ETH/USDT:USDT",
    ]


def test_write_snapshot_is_idempotent_for_identical_content(tmp_path: Path) -> None:
    output = _gate_output()
    first = write_snapshot(output, tmp_path)
    second = write_snapshot(output, tmp_path)
    assert first == second


def test_write_snapshot_rejects_conflicting_rewrite(tmp_path: Path) -> None:
    same_day_first = _gate_output(pairs=("BTC/USDT:USDT", "ETH/USDT:USDT"))
    write_snapshot(same_day_first, tmp_path)

    same_day_different_content = _gate_output(pairs=("SOL/USDT:USDT", "ADA/USDT:USDT"))
    with pytest.raises(PairlistPublishError):
        write_snapshot(same_day_different_content, tmp_path)
