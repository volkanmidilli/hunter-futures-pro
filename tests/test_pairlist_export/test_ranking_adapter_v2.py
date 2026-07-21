"""Focused tests for hunter.pairlist_export.ranking_adapter.rank_pairs_v2 (SPEC-075)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from hunter.pairlist_export.models import PairlistRankingConfig, PairlistRankingError
from hunter.pairlist_export.ranking_adapter import rank_pairs_v2
from hunter.pairlist_export.ranking_input_v2 import ProfileFieldMismatchError, RankingProfile


def test_v1_profile_rejected() -> None:
    config = PairlistRankingConfig()
    with pytest.raises(PairlistRankingError):
        rank_pairs_v2(
            config,
            RankingProfile.V1_RS_OI,
            ("BTC/USDT:USDT",),
            {"BTC/USDT:USDT": Decimal("80")},
            {},
            {"BTC/USDT:USDT": Decimal("60")},
        )


def test_v2_rs_liquidity_tie_break_order() -> None:
    config = PairlistRankingConfig(min_pairs=1, publish_candidates=3, max_pairs=10)
    eligible = ("A/USDT:USDT", "B/USDT:USDT", "C/USDT:USDT")
    rs = {"A/USDT:USDT": Decimal("80"), "B/USDT:USDT": Decimal("80"), "C/USDT:USDT": Decimal("60")}
    liquidity = {"A/USDT:USDT": Decimal("90"), "B/USDT:USDT": Decimal("70"), "C/USDT:USDT": Decimal("99")}
    dq = {"A/USDT:USDT": Decimal("100"), "B/USDT:USDT": Decimal("100"), "C/USDT:USDT": Decimal("100")}

    ranked = rank_pairs_v2(config, RankingProfile.V2_RS_LIQUIDITY, eligible, rs, liquidity, {}, dq)

    # rs desc first: A/B (80) before C (60); among the 80-tie, liquidity desc: A (90) before B (70).
    assert [p.pair for p in ranked] == ["A/USDT:USDT", "B/USDT:USDT", "C/USDT:USDT"]
    assert all(p.selected for p in ranked)


def test_v2_rs_oi_liquidity_tie_break_order() -> None:
    config = PairlistRankingConfig(min_pairs=1, publish_candidates=3, max_pairs=10)
    eligible = ("A/USDT:USDT", "B/USDT:USDT")
    rs = {"A/USDT:USDT": Decimal("80"), "B/USDT:USDT": Decimal("80")}
    liquidity = {"A/USDT:USDT": Decimal("50"), "B/USDT:USDT": Decimal("50")}
    oi = {"A/USDT:USDT": Decimal("90"), "B/USDT:USDT": Decimal("10")}
    dq = {"A/USDT:USDT": Decimal("100"), "B/USDT:USDT": Decimal("100")}

    ranked = rank_pairs_v2(
        config, RankingProfile.V2_RS_OI_LIQUIDITY, eligible, rs, liquidity, oi, dq, oi_available=True
    )

    # rs tied, liquidity tied -> oi breaks the tie: A (90) before B (10).
    assert [p.pair for p in ranked] == ["A/USDT:USDT", "B/USDT:USDT"]


def test_rank_pairs_v2_propagates_profile_field_mismatch() -> None:
    config = PairlistRankingConfig()
    with pytest.raises(ProfileFieldMismatchError):
        rank_pairs_v2(
            config,
            RankingProfile.V2_RS_LIQUIDITY,
            ("BTC/USDT:USDT",),
            {"BTC/USDT:USDT": Decimal("80")},
            {"BTC/USDT:USDT": Decimal("70")},
            {"BTC/USDT:USDT": Decimal("60")},  # populated oi under V2_RS_LIQUIDITY
            oi_available=True,
        )


def test_rank_pairs_v2_selection_cutoff_at_publish_candidates() -> None:
    config = PairlistRankingConfig(min_pairs=1, publish_candidates=1, max_pairs=10)
    eligible = ("A/USDT:USDT", "B/USDT:USDT")
    rs = {"A/USDT:USDT": Decimal("80"), "B/USDT:USDT": Decimal("60")}
    liquidity = {"A/USDT:USDT": Decimal("90"), "B/USDT:USDT": Decimal("70")}
    dq = {"A/USDT:USDT": Decimal("100"), "B/USDT:USDT": Decimal("100")}

    ranked = rank_pairs_v2(config, RankingProfile.V2_RS_LIQUIDITY, eligible, rs, liquidity, {}, dq)

    selected = [p for p in ranked if p.selected]
    assert [p.pair for p in selected] == ["A/USDT:USDT"]


def test_rank_pairs_v2_fingerprint_includes_liquidity() -> None:
    config = PairlistRankingConfig(min_pairs=1, publish_candidates=2, max_pairs=10)
    eligible = ("A/USDT:USDT",)
    rs = {"A/USDT:USDT": Decimal("80")}
    dq = {"A/USDT:USDT": Decimal("100")}
    liquidity_low = {"A/USDT:USDT": Decimal("10")}
    liquidity_high = {"A/USDT:USDT": Decimal("90")}

    ranked_low = rank_pairs_v2(config, RankingProfile.V2_RS_LIQUIDITY, eligible, rs, liquidity_low, {}, dq)
    ranked_high = rank_pairs_v2(config, RankingProfile.V2_RS_LIQUIDITY, eligible, rs, liquidity_high, {}, dq)

    assert ranked_low[0].fingerprint != ranked_high[0].fingerprint
