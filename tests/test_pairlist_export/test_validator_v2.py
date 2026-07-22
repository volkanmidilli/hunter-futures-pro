"""Focused tests for hunter.pairlist_export.validator.run_publish_gate_v2 (SPEC-075)."""

from __future__ import annotations

from decimal import Decimal

from hunter.pairlist_export.models import (
    REASON_BELOW_MIN_PAIRS,
    PairlistRankingConfig,
)
from hunter.pairlist_export.ranking_adapter import rank_pairs_v2
from hunter.pairlist_export.ranking_input_v2 import RankingProfile
from hunter.pairlist_export.validator import run_publish_gate_v2


def _ranked_single_pair(config: PairlistRankingConfig):
    return rank_pairs_v2(
        config,
        RankingProfile.V2_RS_LIQUIDITY,
        ("BTC/USDT:USDT",),
        {"BTC/USDT:USDT": Decimal("80")},
        {"BTC/USDT:USDT": Decimal("70")},
        {},
        {"BTC/USDT:USDT": Decimal("100")},
    )


def test_single_pair_fails_below_min_pairs_with_default_config() -> None:
    config = PairlistRankingConfig()  # default min_pairs=5
    ranked = _ranked_single_pair(config)

    result = run_publish_gate_v2(
        config=config,
        as_of_date="2026-07-21",
        universe_total=1,
        ranked_pairs=ranked,
        ranking_profile=RankingProfile.V2_RS_LIQUIDITY,
        universe_size_at_scoring=1,
        universe_fingerprint="fp",
        oi_available=False,
    )

    assert result.allow_publish is False
    assert REASON_BELOW_MIN_PAIRS in result.reason_codes


def test_single_pair_passes_with_relaxed_min_pairs() -> None:
    config = PairlistRankingConfig(min_pairs=1, publish_candidates=1, max_pairs=10)
    ranked = _ranked_single_pair(config)

    result = run_publish_gate_v2(
        config=config,
        as_of_date="2026-07-21",
        universe_total=1,
        ranked_pairs=ranked,
        ranking_profile=RankingProfile.V2_RS_LIQUIDITY,
        universe_size_at_scoring=1,
        universe_fingerprint="fp",
        oi_available=False,
        source_metadata={"source": "freqtrade-feather"},
        per_pair_evidence={"BTC/USDT:USDT": ("DATA_COMPLETE",)},
    )

    assert result.allow_publish is True
    output = result.pairlist_output
    assert output is not None
    assert output.audit.schema_version == "hunter-ranking-input-v2"
    assert output.audit.ranking_profile == "V2_RS_LIQUIDITY"
    assert output.audit.active_score_dimensions == ("rs", "liquidity", "data_quality")
    assert output.audit.ignored_score_dimensions == ()
    assert output.audit.oi_available is False
    assert output.audit.universe_fingerprint == "fp"
    assert output.audit.per_pair_evidence["BTC/USDT:USDT"] == ("DATA_COMPLETE",)


def test_v2_audit_record_to_dict_includes_v2_fields() -> None:
    from hunter.pairlist_export.audit import audit_record_to_dict

    config = PairlistRankingConfig(min_pairs=1, publish_candidates=1, max_pairs=10)
    ranked = _ranked_single_pair(config)
    result = run_publish_gate_v2(
        config=config,
        as_of_date="2026-07-21",
        universe_total=1,
        ranked_pairs=ranked,
        ranking_profile=RankingProfile.V2_RS_LIQUIDITY,
        universe_size_at_scoring=1,
        universe_fingerprint="fp",
        oi_available=False,
    )
    payload = audit_record_to_dict(result.pairlist_output.audit)
    assert payload["schema_version"] == "hunter-ranking-input-v2"
    assert payload["selected"][0]["liquidity_score"] == "70"
