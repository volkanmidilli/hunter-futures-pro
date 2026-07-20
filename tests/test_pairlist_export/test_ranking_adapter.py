"""Focused tests for hunter.pairlist_export.ranking_adapter (SPEC-074)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from hunter.pairlist_export.models import (
    REASON_INSUFFICIENT_EVIDENCE,
    PairlistRankingConfig,
    PairlistRankingError,
)
from hunter.pairlist_export.ranking_adapter import rank_pairs


def test_tie_break_order_rs_then_oi_then_dq_then_pair_asc() -> None:
    config = PairlistRankingConfig()
    eligible = ("ETH/USDT:USDT", "BTC/USDT:USDT", "SOL/USDT:USDT", "ADA/USDT:USDT")
    rs_scores = {
        "BTC/USDT:USDT": Decimal("80"),
        "ETH/USDT:USDT": Decimal("80"),
        "SOL/USDT:USDT": Decimal("60"),
        "ADA/USDT:USDT": Decimal("60"),
    }
    oi_scores = {
        "BTC/USDT:USDT": Decimal("50"),
        "ETH/USDT:USDT": Decimal("50"),
        "SOL/USDT:USDT": Decimal("70"),
        "ADA/USDT:USDT": Decimal("40"),
    }
    ranked = rank_pairs(config, eligible, rs_scores, oi_scores)

    # BTC/ETH tie on rs+oi -> pair string ascending breaks the tie.
    assert [p.pair for p in ranked] == [
        "BTC/USDT:USDT",
        "ETH/USDT:USDT",
        "SOL/USDT:USDT",
        "ADA/USDT:USDT",
    ]
    assert [p.rank for p in ranked] == [1, 2, 3, 4]


def test_insufficient_evidence_pairs_are_rejected_not_selected() -> None:
    config = PairlistRankingConfig()
    eligible = ("BTC/USDT:USDT", "XYZ/USDT:USDT")
    ranked = rank_pairs(
        config,
        eligible,
        rs_scores={"BTC/USDT:USDT": Decimal("80")},
        oi_scores={"BTC/USDT:USDT": Decimal("50")},
    )
    by_pair = {p.pair: p for p in ranked}
    assert by_pair["BTC/USDT:USDT"].selected is True
    assert by_pair["XYZ/USDT:USDT"].selected is False
    assert REASON_INSUFFICIENT_EVIDENCE in by_pair["XYZ/USDT:USDT"].reason_codes


def test_raises_when_every_pair_lacks_evidence() -> None:
    config = PairlistRankingConfig()
    with pytest.raises(PairlistRankingError):
        rank_pairs(config, ("BTC/USDT:USDT",), rs_scores={}, oi_scores={})


def test_raises_on_empty_eligible_pairs() -> None:
    config = PairlistRankingConfig()
    with pytest.raises(PairlistRankingError):
        rank_pairs(config, (), rs_scores={}, oi_scores={})


def test_raises_on_wrong_config_type() -> None:
    with pytest.raises(PairlistRankingError):
        rank_pairs(object(), ("BTC/USDT:USDT",), rs_scores={}, oi_scores={})  # type: ignore[arg-type]


def test_selection_capped_at_publish_candidates() -> None:
    config = PairlistRankingConfig(min_pairs=1, publish_candidates=2, max_pairs=10)
    eligible = tuple(f"COIN{i}/USDT:USDT" for i in range(5))
    rs_scores = {pair: Decimal(100 - i) for i, pair in enumerate(eligible)}
    oi_scores = {pair: Decimal("50") for pair in eligible}

    ranked = rank_pairs(config, eligible, rs_scores, oi_scores)
    selected = [p for p in ranked if p.selected]
    assert len(selected) == 2
    assert [p.pair for p in selected] == ["COIN0/USDT:USDT", "COIN1/USDT:USDT"]


def test_fingerprint_is_populated_and_deterministic() -> None:
    config = PairlistRankingConfig()
    eligible = ("BTC/USDT:USDT",)
    rs_scores = {"BTC/USDT:USDT": Decimal("80")}
    oi_scores = {"BTC/USDT:USDT": Decimal("50")}

    first = rank_pairs(config, eligible, rs_scores, oi_scores)
    second = rank_pairs(config, eligible, rs_scores, oi_scores)

    assert first[0].fingerprint
    assert first[0].fingerprint == second[0].fingerprint
