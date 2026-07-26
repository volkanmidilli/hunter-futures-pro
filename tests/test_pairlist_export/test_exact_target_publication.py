"""Tests for the exact-target publication policy (supersedes SPEC-074 surplus).

Policy under test: Hunter is the single authority for the published pair
count.  The selection cutoff is the canonical ``target_final_pairs``
(default 20); ``max_pairs`` (50) remains an independent fail-closed
safety gate.  Freqtrade may apply eligibility filters but must not perform
an independent ranking cutoff.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from hunter.pairlist_export.models import (
    REASON_ABOVE_MAX_PAIRS,
    PairlistRankingConfig,
    RankedPair,
)
from hunter.pairlist_export.ranking_adapter import rank_pairs
from hunter.pairlist_export.validator import run_publish_gate


def _inputs(n: int):
    """Build ``n`` eligible pairs with strictly decreasing RS scores."""
    eligible = tuple(f"COIN{i:03d}/USDT:USDT" for i in range(n))
    rs_scores = {pair: Decimal(1000 - i) for i, pair in enumerate(eligible)}
    oi_scores = {pair: Decimal("50") for pair in eligible}
    return eligible, rs_scores, oi_scores


def test_more_than_20_eligible_publish_exactly_top_20() -> None:
    config = PairlistRankingConfig()
    eligible, rs_scores, oi_scores = _inputs(26)
    ranked = rank_pairs(config, eligible, rs_scores, oi_scores)

    result = run_publish_gate(config, "2026-07-26", 26, ranked)
    assert result.allow_publish is True
    output = result.pairlist_output
    assert output is not None
    assert len(output.pairs) == 20
    # Exactly the top 20 by deterministic rank, in rank order.
    assert output.pairs == tuple(f"COIN{i:03d}/USDT:USDT" for i in range(20))
    # Ranks 21+ are ranked but not selected.
    assert [p.rank for p in ranked if not p.selected] == [21, 22, 23, 24, 25, 26]


def test_exactly_20_eligible_publish_20() -> None:
    config = PairlistRankingConfig()
    eligible, rs_scores, oi_scores = _inputs(20)
    ranked = rank_pairs(config, eligible, rs_scores, oi_scores)

    result = run_publish_gate(config, "2026-07-26", 20, ranked)
    assert result.allow_publish is True
    output = result.pairlist_output
    assert output is not None
    assert len(output.pairs) == 20
    assert all(p.selected for p in ranked)


def test_fewer_than_20_eligible_publish_underfilled_without_padding() -> None:
    """Underfilled publication policy is unchanged: publish what exists."""
    config = PairlistRankingConfig()
    eligible, rs_scores, oi_scores = _inputs(12)
    ranked = rank_pairs(config, eligible, rs_scores, oi_scores)

    result = run_publish_gate(config, "2026-07-26", 12, ranked)
    assert result.allow_publish is True
    output = result.pairlist_output
    assert output is not None
    assert len(output.pairs) == 12
    assert output.pairs == tuple(f"COIN{i:03d}/USDT:USDT" for i in range(12))


def test_ordering_is_deterministic_across_reruns() -> None:
    config = PairlistRankingConfig()
    eligible, rs_scores, oi_scores = _inputs(26)

    first = rank_pairs(config, eligible, rs_scores, oi_scores)
    second = rank_pairs(config, tuple(reversed(eligible)), rs_scores, oi_scores)

    assert [p.pair for p in first] == [p.pair for p in second]
    assert [p.fingerprint for p in first] == [p.fingerprint for p in second]

    out1 = run_publish_gate(config, "2026-07-26", 26, first).pairlist_output
    out2 = run_publish_gate(config, "2026-07-26", 26, second).pairlist_output
    assert out1 is not None and out2 is not None
    assert out1.pairs == out2.pairs
    assert out1.fingerprint == out2.fingerprint


def test_target_above_50_cannot_be_constructed() -> None:
    """The fail-closed invariant: no config may target beyond max_pairs."""
    with pytest.raises(ValueError):
        PairlistRankingConfig(target_final_pairs=51, max_pairs=50)


def test_gate_rejects_more_than_50_selected_even_if_hand_built() -> None:
    """max_pairs=50 remains an independent fail-closed safety gate: even a
    selection that bypasses the ranking adapter cannot publish >50 pairs."""
    config = PairlistRankingConfig()
    assert config.max_pairs == 50
    ranked = tuple(
        RankedPair(pair=f"COIN{i:03d}/USDT:USDT", rank=i + 1, selected=True)
        for i in range(51)
    )
    result = run_publish_gate(config, "2026-07-26", 51, ranked)
    assert result.allow_publish is False
    assert REASON_ABOVE_MAX_PAIRS in result.reason_codes
    assert result.pairlist_output is None


def test_snapshot_and_audit_behavior_unchanged_for_exact_target() -> None:
    """Audit record still accounts for every ranked pair (selected and
    rejected); only the selection cutoff changed."""
    config = PairlistRankingConfig()
    eligible, rs_scores, oi_scores = _inputs(26)
    ranked = rank_pairs(config, eligible, rs_scores, oi_scores)

    result = run_publish_gate(config, "2026-07-26", 26, ranked)
    assert result.allow_publish is True
    audit = result.pairlist_output.audit  # type: ignore[union-attr]
    assert audit.universe_total == 26
    assert audit.eligible_count == 26
    assert audit.selected_count == 20
    assert audit.rejected_count == 6
    assert len(audit.selected) + len(audit.rejected) == 26
    assert audit.fingerprint
