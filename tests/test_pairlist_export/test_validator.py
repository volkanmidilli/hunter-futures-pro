"""Focused tests for hunter.pairlist_export.validator (SPEC-074)."""

from __future__ import annotations

from decimal import Decimal

from hunter.pairlist_export.models import (
    REASON_ABOVE_MAX_PAIRS,
    REASON_BELOW_MIN_PAIRS,
    REASON_DUPLICATE_PAIR,
    REASON_EMPTY_UNIVERSE,
    REASON_INSUFFICIENT_EVIDENCE,
    REASON_INVALID_PAIR_FORMAT,
    PairlistRankingConfig,
    RankedPair,
)
from hunter.pairlist_export.ranking_adapter import rank_pairs
from hunter.pairlist_export.validator import (
    find_duplicate_pairs,
    run_publish_gate,
    validate_pair_format,
    validate_published_pairlist,
)


def test_validate_pair_format_accepts_usdt_m_futures_shape() -> None:
    assert validate_pair_format("BTC/USDT:USDT") is True
    assert validate_pair_format("BTC/USDT") is False
    assert validate_pair_format("btc/usdt:usdt") is False
    assert validate_pair_format("BTC/USD:USD") is False


def test_find_duplicate_pairs() -> None:
    assert find_duplicate_pairs(("BTC/USDT:USDT", "ETH/USDT:USDT", "BTC/USDT:USDT")) == (
        "BTC/USDT:USDT",
    )
    assert find_duplicate_pairs(("BTC/USDT:USDT", "ETH/USDT:USDT")) == ()


def _config(**overrides) -> PairlistRankingConfig:
    base = dict(min_pairs=2, publish_candidates=5, max_pairs=5)
    base.update(overrides)
    return PairlistRankingConfig(**base)


def test_gate_rejects_empty_selection() -> None:
    config = _config()
    result = run_publish_gate(config, "2026-07-21", 10, ranked_pairs=())
    assert result.allow_publish is False
    assert REASON_EMPTY_UNIVERSE in result.reason_codes
    assert result.pairlist_output is None


def test_gate_rejects_below_min_pairs() -> None:
    config = _config(min_pairs=3, publish_candidates=5, max_pairs=5)
    ranked = rank_pairs(
        config,
        ("BTC/USDT:USDT", "ETH/USDT:USDT"),
        rs_scores={"BTC/USDT:USDT": Decimal("80"), "ETH/USDT:USDT": Decimal("70")},
        oi_scores={"BTC/USDT:USDT": Decimal("50"), "ETH/USDT:USDT": Decimal("40")},
    )
    result = run_publish_gate(config, "2026-07-21", 10, ranked)
    assert result.allow_publish is False
    assert REASON_BELOW_MIN_PAIRS in result.reason_codes


def test_gate_rejects_above_max_pairs_even_if_ranking_adapter_selected_them() -> None:
    # Hand-build ranked pairs bypassing the ranking adapter's own
    # publish_candidates cap, so the gate's own max_pairs check is exercised
    # independently as the safety-net it's meant to be.
    config = PairlistRankingConfig(min_pairs=1, publish_candidates=3, max_pairs=3)
    ranked = tuple(
        RankedPair(pair=f"COIN{i}/USDT:USDT", rank=i + 1, selected=True)
        for i in range(4)
    )
    result = run_publish_gate(config, "2026-07-21", 10, ranked)
    assert result.allow_publish is False
    assert REASON_ABOVE_MAX_PAIRS in result.reason_codes


def test_gate_rejects_duplicate_pairs() -> None:
    config = _config()
    ranked = (
        RankedPair(pair="BTC/USDT:USDT", rank=1, selected=True),
        RankedPair(pair="BTC/USDT:USDT", rank=2, selected=True),
    )
    result = run_publish_gate(config, "2026-07-21", 10, ranked)
    assert result.allow_publish is False
    assert REASON_DUPLICATE_PAIR in result.reason_codes


def test_gate_rejects_invalid_pair_format() -> None:
    config = _config(min_pairs=1)
    ranked = (RankedPair(pair="BTC-USDT", rank=1, selected=True),)
    result = run_publish_gate(config, "2026-07-21", 10, ranked)
    assert result.allow_publish is False
    assert REASON_INVALID_PAIR_FORMAT in result.reason_codes


def test_gate_independently_rejects_selected_pair_with_incomplete_evidence() -> None:
    # The gate must not merely trust the ranking adapter's `selected` flag:
    # a hand-built RankedPair marked selected=True but still carrying
    # INSUFFICIENT_EVIDENCE must be caught by the gate itself.
    config = _config(min_pairs=1)
    ranked = (
        RankedPair(
            pair="BTC/USDT:USDT",
            rank=1,
            selected=True,
            reason_codes=(REASON_INSUFFICIENT_EVIDENCE,),
        ),
    )
    result = run_publish_gate(config, "2026-07-21", 10, ranked)
    assert result.allow_publish is False
    assert REASON_INSUFFICIENT_EVIDENCE in result.reason_codes


def test_gate_success_builds_pairlist_output_with_fingerprints() -> None:
    config = _config(min_pairs=1, publish_candidates=5, max_pairs=5)
    ranked = rank_pairs(
        config,
        ("BTC/USDT:USDT", "ETH/USDT:USDT"),
        rs_scores={"BTC/USDT:USDT": Decimal("80"), "ETH/USDT:USDT": Decimal("70")},
        oi_scores={"BTC/USDT:USDT": Decimal("50"), "ETH/USDT:USDT": Decimal("40")},
    )
    result = run_publish_gate(config, "2026-07-21", 10, ranked)
    assert result.allow_publish is True
    output = result.pairlist_output
    assert output is not None
    assert output.pairs == ("BTC/USDT:USDT", "ETH/USDT:USDT")
    assert output.refresh_period == config.refresh_period
    assert output.fingerprint
    assert output.audit_fingerprint == output.audit.fingerprint


def test_validate_published_pairlist_accepts_well_formed_payload() -> None:
    payload = {"pairs": ["BTC/USDT:USDT", "ETH/USDT:USDT"], "refresh_period": 3600}
    is_valid, reason_codes = validate_published_pairlist(payload)
    assert is_valid is True
    assert reason_codes == ()


def test_validate_published_pairlist_rejects_bad_schema() -> None:
    is_valid, reason_codes = validate_published_pairlist({"pairs": "not-a-list"})
    assert is_valid is False
    assert reason_codes == ("VALIDATION_FAILED",)


def test_validate_published_pairlist_enforces_config_thresholds() -> None:
    payload = {"pairs": ["BTC/USDT:USDT"], "refresh_period": 3600}
    config = PairlistRankingConfig(min_pairs=5, publish_candidates=30, max_pairs=50)
    is_valid, reason_codes = validate_published_pairlist(payload, config=config)
    assert is_valid is False
    assert REASON_BELOW_MIN_PAIRS in reason_codes
