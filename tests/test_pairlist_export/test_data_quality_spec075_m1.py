"""SPEC-075 M1 remediation: profile-aware data_quality validation tests."""

from __future__ import annotations

from decimal import Decimal

import pytest

from hunter.pairlist_export.models import (
    REASON_DATA_SUFFICIENCY,
    REASON_PROFILE_EVIDENCE_INCOMPLETE,
    REASON_PROFILE_FIELD_MISMATCH,
    PairlistRankingConfig,
    RankedPair,
)
from hunter.pairlist_export.ranking_adapter import rank_pairs_v2
from hunter.pairlist_export.ranking_input_v2 import (
    ProfileEvidenceIncompleteError,
    ProfileFieldMismatchError,
    RankingProfile,
    validate_profile_fields,
)
from hunter.pairlist_export.validator import run_publish_gate_v2


def _v2_common(profile: RankingProfile) -> dict:
    """Return a well-formed v2 payload for the given profile."""
    base = {
        "eligible_pairs": ("BTC/USDT:USDT", "ETH/USDT:USDT"),
        "rs_scores": {"BTC/USDT:USDT": Decimal("80"), "ETH/USDT:USDT": Decimal("60")},
        "liquidity_scores": {"BTC/USDT:USDT": Decimal("70"), "ETH/USDT:USDT": Decimal("50")},
        "data_quality": {"BTC/USDT:USDT": Decimal("100"), "ETH/USDT:USDT": Decimal("90")},
    }
    if profile is RankingProfile.V2_RS_LIQUIDITY:
        base.update({"oi_scores": {}, "oi_available": False})
    else:
        base.update(
            {
                "oi_scores": {"BTC/USDT:USDT": Decimal("60"), "ETH/USDT:USDT": Decimal("40")},
                "oi_available": True,
            }
        )
    return base


class TestValidateProfileFieldsDataQuality:
    """Direct tests for validate_profile_fields data_quality rules."""

    @pytest.mark.parametrize("profile", [RankingProfile.V2_RS_LIQUIDITY, RankingProfile.V2_RS_OI_LIQUIDITY])
    def test_missing_data_quality_raises_profile_evidence_incomplete(self, profile: RankingProfile) -> None:
        """Missing data_quality for an eligible v2 pair -> PROFILE_EVIDENCE_INCOMPLETE."""
        payload = _v2_common(profile)
        payload["data_quality"] = {"BTC/USDT:USDT": Decimal("100")}  # ETH missing
        with pytest.raises(ProfileEvidenceIncompleteError) as exc_info:
            validate_profile_fields(ranking_profile=profile, **payload)
        assert exc_info.value.reason_code == REASON_PROFILE_EVIDENCE_INCOMPLETE
        assert "ETH/USDT:USDT" in str(exc_info.value)

    @pytest.mark.parametrize("profile", [RankingProfile.V2_RS_LIQUIDITY, RankingProfile.V2_RS_OI_LIQUIDITY])
    def test_empty_data_quality_map_raises_profile_evidence_incomplete(self, profile: RankingProfile) -> None:
        """Completely missing data_quality map -> PROFILE_EVIDENCE_INCOMPLETE."""
        payload = _v2_common(profile)
        payload["data_quality"] = {}
        with pytest.raises(ProfileEvidenceIncompleteError) as exc_info:
            validate_profile_fields(ranking_profile=profile, **payload)
        assert exc_info.value.reason_code == REASON_PROFILE_EVIDENCE_INCOMPLETE

    @pytest.mark.parametrize("bad_value", ["not-a-decimal", 100.5, 42, Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
    @pytest.mark.parametrize("profile", [RankingProfile.V2_RS_LIQUIDITY, RankingProfile.V2_RS_OI_LIQUIDITY])
    def test_malformed_or_non_finite_data_quality_raises_profile_field_mismatch(
        self, profile: RankingProfile, bad_value: object
    ) -> None:
        """Malformed, NaN, or Infinity data_quality -> PROFILE_FIELD_MISMATCH."""
        payload = _v2_common(profile)
        payload["data_quality"] = {"BTC/USDT:USDT": bad_value, "ETH/USDT:USDT": Decimal("90")}
        with pytest.raises(ProfileFieldMismatchError) as exc_info:
            validate_profile_fields(ranking_profile=profile, **payload)
        assert exc_info.value.reason_code == REASON_PROFILE_FIELD_MISMATCH

    @pytest.mark.parametrize("bad_value", [Decimal("-1"), Decimal("101")])
    @pytest.mark.parametrize("profile", [RankingProfile.V2_RS_LIQUIDITY, RankingProfile.V2_RS_OI_LIQUIDITY])
    def test_out_of_range_data_quality_raises_profile_field_mismatch(
        self, profile: RankingProfile, bad_value: Decimal
    ) -> None:
        """data_quality below 0 or above 100 -> PROFILE_FIELD_MISMATCH."""
        payload = _v2_common(profile)
        payload["data_quality"] = {"BTC/USDT:USDT": bad_value, "ETH/USDT:USDT": Decimal("90")}
        with pytest.raises(ProfileFieldMismatchError) as exc_info:
            validate_profile_fields(ranking_profile=profile, **payload)
        assert exc_info.value.reason_code == REASON_PROFILE_FIELD_MISMATCH

    @pytest.mark.parametrize("boundary", [Decimal("0"), Decimal("100")])
    @pytest.mark.parametrize("profile", [RankingProfile.V2_RS_LIQUIDITY, RankingProfile.V2_RS_OI_LIQUIDITY])
    def test_data_quality_boundaries_accepted(self, profile: RankingProfile, boundary: Decimal) -> None:
        """Boundary values 0 and 100 are accepted."""
        payload = _v2_common(profile)
        payload["data_quality"] = {"BTC/USDT:USDT": boundary, "ETH/USDT:USDT": boundary}
        validate_profile_fields(ranking_profile=profile, **payload)

    @pytest.mark.parametrize("profile", [RankingProfile.V2_RS_LIQUIDITY, RankingProfile.V2_RS_OI_LIQUIDITY])
    def test_valid_complete_map_accepted(self, profile: RankingProfile) -> None:
        """Valid complete data_quality maps pass for both v2 profiles."""
        payload = _v2_common(profile)
        validate_profile_fields(ranking_profile=profile, **payload)

    def test_v1_missing_data_quality_is_allowed(self) -> None:
        """V1_RS_OI accepts missing data_quality for SPEC-074 backward compatibility."""
        validate_profile_fields(
            ranking_profile=RankingProfile.V1_RS_OI,
            eligible_pairs=("BTC/USDT:USDT",),
            rs_scores={"BTC/USDT:USDT": Decimal("80")},
            liquidity_scores={},
            oi_scores={"BTC/USDT:USDT": Decimal("60")},
            oi_available=True,
            data_quality={},
        )


class TestRankPairsV2DataQuality:
    """rank_pairs_v2 must enforce data_quality via validate_profile_fields."""

    @pytest.mark.parametrize("profile", [RankingProfile.V2_RS_LIQUIDITY, RankingProfile.V2_RS_OI_LIQUIDITY])
    def test_missing_data_quality_rejects_with_profile_evidence_incomplete(self, profile: RankingProfile) -> None:
        """Missing data_quality causes rank_pairs_v2 to raise with the exact reason."""
        config = PairlistRankingConfig(min_pairs=1)
        payload = _v2_common(profile)
        payload["data_quality"] = {"BTC/USDT:USDT": Decimal("100")}  # ETH missing
        with pytest.raises(ProfileEvidenceIncompleteError) as exc_info:
            rank_pairs_v2(config, profile, **payload)
        assert exc_info.value.reason_code == REASON_PROFILE_EVIDENCE_INCOMPLETE

    @pytest.mark.parametrize("bad_value", [Decimal("NaN"), Decimal("Infinity"), Decimal("-1"), Decimal("101")])
    @pytest.mark.parametrize("profile", [RankingProfile.V2_RS_LIQUIDITY, RankingProfile.V2_RS_OI_LIQUIDITY])
    def test_invalid_data_quality_rejects_with_profile_field_mismatch(
        self, profile: RankingProfile, bad_value: Decimal
    ) -> None:
        """Malformed/non-finite/out-of-range data_quality fails with PROFILE_FIELD_MISMATCH."""
        config = PairlistRankingConfig(min_pairs=1)
        payload = _v2_common(profile)
        payload["data_quality"] = {"BTC/USDT:USDT": bad_value, "ETH/USDT:USDT": Decimal("90")}
        with pytest.raises(ProfileFieldMismatchError) as exc_info:
            rank_pairs_v2(config, profile, **payload)
        assert exc_info.value.reason_code == REASON_PROFILE_FIELD_MISMATCH

    @pytest.mark.parametrize("profile", [RankingProfile.V2_RS_LIQUIDITY, RankingProfile.V2_RS_OI_LIQUIDITY])
    def test_valid_complete_payload_ranks_successfully(self, profile: RankingProfile) -> None:
        """A valid complete payload produces deterministic ranking."""
        config = PairlistRankingConfig(min_pairs=1)
        payload = _v2_common(profile)
        ranked = rank_pairs_v2(config, profile, **payload)
        assert len(ranked) == 2
        assert all(p.data_quality_pct is not None for p in ranked)
        assert all(REASON_DATA_SUFFICIENCY in p.reason_codes for p in ranked)

    def test_v2_rs_liquidity_tie_break_order_preserved(self) -> None:
        """Tie-break: -rs, -liquidity, -data_quality, pair_asc."""
        config = PairlistRankingConfig(min_pairs=1, publish_candidates=10)
        ranked = rank_pairs_v2(
            config,
            RankingProfile.V2_RS_LIQUIDITY,
            ("AAA/USDT:USDT", "BBB/USDT:USDT", "CCC/USDT:USDT"),
            {"AAA/USDT:USDT": Decimal("80"), "BBB/USDT:USDT": Decimal("80"), "CCC/USDT:USDT": Decimal("80")},
            {"AAA/USDT:USDT": Decimal("70"), "BBB/USDT:USDT": Decimal("70"), "CCC/USDT:USDT": Decimal("60")},
            {},
            {"AAA/USDT:USDT": Decimal("100"), "BBB/USDT:USDT": Decimal("90"), "CCC/USDT:USDT": Decimal("100")},
        )
        # AAA beats BBB on data_quality; both beat CCC on liquidity
        assert [p.pair for p in ranked] == ["AAA/USDT:USDT", "BBB/USDT:USDT", "CCC/USDT:USDT"]

    def test_v2_rs_oi_liquidity_tie_break_order_preserved(self) -> None:
        """Tie-break: -rs, -oi, -liquidity, -data_quality, pair_asc."""
        config = PairlistRankingConfig(min_pairs=1, publish_candidates=10)
        ranked = rank_pairs_v2(
            config,
            RankingProfile.V2_RS_OI_LIQUIDITY,
            ("AAA/USDT:USDT", "BBB/USDT:USDT", "CCC/USDT:USDT", "DDD/USDT:USDT"),
            {p: Decimal("80") for p in ("AAA/USDT:USDT", "BBB/USDT:USDT", "CCC/USDT:USDT", "DDD/USDT:USDT")},
            {p: Decimal("70") for p in ("AAA/USDT:USDT", "BBB/USDT:USDT", "CCC/USDT:USDT", "DDD/USDT:USDT")},
            {"AAA/USDT:USDT": Decimal("60"), "BBB/USDT:USDT": Decimal("60"), "CCC/USDT:USDT": Decimal("50"), "DDD/USDT:USDT": Decimal("60")},
            {"AAA/USDT:USDT": Decimal("100"), "BBB/USDT:USDT": Decimal("90"), "CCC/USDT:USDT": Decimal("100"), "DDD/USDT:USDT": Decimal("100")},
            oi_available=True,
        )
        # AAA/BBB/DDD tie on rs/oi/liquidity -> data_quality decides BBB vs {AAA,DDD};
        # AAA/DDD tie on every dimension -> pair_asc decides. CCC loses on oi.
        assert [p.pair for p in ranked] == ["AAA/USDT:USDT", "DDD/USDT:USDT", "BBB/USDT:USDT", "CCC/USDT:USDT"]


class TestPublishGateV2DataQuality:
    """run_publish_gate_v2 independently validates data_quality_pct on selected pairs."""

    def _gate_args(self, ranked: tuple[RankedPair, ...], profile: RankingProfile) -> dict:
        return {
            "config": PairlistRankingConfig(min_pairs=1, publish_candidates=10),
            "as_of_date": "2026-07-21",
            "universe_total": len(ranked),
            "ranked_pairs": ranked,
            "ranking_profile": profile,
            "universe_size_at_scoring": len(ranked),
            "universe_fingerprint": "fp",
            "oi_available": profile is RankingProfile.V2_RS_OI_LIQUIDITY,
        }

    @pytest.mark.parametrize("profile", [RankingProfile.V2_RS_LIQUIDITY, RankingProfile.V2_RS_OI_LIQUIDITY])
    def test_missing_data_quality_pct_is_rejected(self, profile: RankingProfile) -> None:
        """Externally constructed selected pair with data_quality_pct=None -> PROFILE_EVIDENCE_INCOMPLETE."""
        ranked = (
            RankedPair(
                pair="BTC/USDT:USDT",
                rank=1,
                selected=True,
                rs_score=Decimal("80"),
                oi_score=Decimal("60") if profile is RankingProfile.V2_RS_OI_LIQUIDITY else None,
                liquidity_score=Decimal("70"),
                data_quality_pct=None,
                reason_codes=(),
            ),
        )
        result = run_publish_gate_v2(**self._gate_args(ranked, profile))
        assert result.allow_publish is False
        assert REASON_PROFILE_EVIDENCE_INCOMPLETE in result.reason_codes

    @pytest.mark.parametrize("bad_value", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity"), Decimal("-1"), Decimal("101")])
    @pytest.mark.parametrize("profile", [RankingProfile.V2_RS_LIQUIDITY, RankingProfile.V2_RS_OI_LIQUIDITY])
    def test_invalid_data_quality_pct_is_rejected(self, profile: RankingProfile, bad_value: Decimal) -> None:
        """Externally constructed selected pair with invalid data_quality_pct -> PROFILE_FIELD_MISMATCH."""
        ranked = (
            RankedPair(
                pair="BTC/USDT:USDT",
                rank=1,
                selected=True,
                rs_score=Decimal("80"),
                oi_score=Decimal("60") if profile is RankingProfile.V2_RS_OI_LIQUIDITY else None,
                liquidity_score=Decimal("70"),
                data_quality_pct=bad_value,
                reason_codes=(),  # no mismatch reason -- gate must not rely on reason_codes
            ),
        )
        result = run_publish_gate_v2(**self._gate_args(ranked, profile))
        assert result.allow_publish is False
        assert REASON_PROFILE_FIELD_MISMATCH in result.reason_codes

    @pytest.mark.parametrize("boundary", [Decimal("0"), Decimal("100")])
    @pytest.mark.parametrize("profile", [RankingProfile.V2_RS_LIQUIDITY, RankingProfile.V2_RS_OI_LIQUIDITY])
    def test_data_quality_boundaries_pass(self, profile: RankingProfile, boundary: Decimal) -> None:
        """Boundary values 0 and 100 pass the gate."""
        ranked = (
            RankedPair(
                pair="BTC/USDT:USDT",
                rank=1,
                selected=True,
                rs_score=Decimal("80"),
                oi_score=Decimal("60") if profile is RankingProfile.V2_RS_OI_LIQUIDITY else None,
                liquidity_score=Decimal("70"),
                data_quality_pct=boundary,
                reason_codes=(REASON_DATA_SUFFICIENCY,),
            ),
        )
        result = run_publish_gate_v2(**self._gate_args(ranked, profile))
        assert result.allow_publish is True
        assert result.pairlist_output is not None

    @pytest.mark.parametrize("profile", [RankingProfile.V2_RS_LIQUIDITY, RankingProfile.V2_RS_OI_LIQUIDITY])
    def test_gate_does_not_rely_on_reason_codes_alone(self, profile: RankingProfile) -> None:
        """A selected pair with clean reason_codes but NaN data_quality_pct is still rejected."""
        ranked = (
            RankedPair(
                pair="BTC/USDT:USDT",
                rank=1,
                selected=True,
                rs_score=Decimal("80"),
                oi_score=Decimal("60") if profile is RankingProfile.V2_RS_OI_LIQUIDITY else None,
                liquidity_score=Decimal("70"),
                data_quality_pct=Decimal("NaN"),
                reason_codes=(),  # gate must validate the value, not trust reason_codes
            ),
        )
        result = run_publish_gate_v2(**self._gate_args(ranked, profile))
        assert result.allow_publish is False
        assert REASON_PROFILE_FIELD_MISMATCH in result.reason_codes


class TestAuditDimensions:
    """Audit active_score_dimensions must reflect every ranking/evidence dimension."""

    def test_v2_rs_liquidity_active_dimensions_exact(self) -> None:
        config = PairlistRankingConfig(min_pairs=1, publish_candidates=1, max_pairs=10)
        ranked = rank_pairs_v2(
            config,
            RankingProfile.V2_RS_LIQUIDITY,
            ("BTC/USDT:USDT",),
            {"BTC/USDT:USDT": Decimal("80")},
            {"BTC/USDT:USDT": Decimal("70")},
            {},
            {"BTC/USDT:USDT": Decimal("100")},
        )
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
        assert result.allow_publish is True
        assert result.pairlist_output.audit.active_score_dimensions == ("rs", "liquidity", "data_quality")
        assert result.pairlist_output.audit.ignored_score_dimensions == ()

    def test_v2_rs_oi_liquidity_active_dimensions_exact(self) -> None:
        config = PairlistRankingConfig(min_pairs=1, publish_candidates=1, max_pairs=10)
        ranked = rank_pairs_v2(
            config,
            RankingProfile.V2_RS_OI_LIQUIDITY,
            ("BTC/USDT:USDT",),
            {"BTC/USDT:USDT": Decimal("80")},
            {"BTC/USDT:USDT": Decimal("70")},
            {"BTC/USDT:USDT": Decimal("60")},
            {"BTC/USDT:USDT": Decimal("100")},
            oi_available=True,
        )
        result = run_publish_gate_v2(
            config=config,
            as_of_date="2026-07-21",
            universe_total=1,
            ranked_pairs=ranked,
            ranking_profile=RankingProfile.V2_RS_OI_LIQUIDITY,
            universe_size_at_scoring=1,
            universe_fingerprint="fp",
            oi_available=True,
        )
        assert result.allow_publish is True
        assert result.pairlist_output.audit.active_score_dimensions == ("rs", "oi", "liquidity", "data_quality")
        assert result.pairlist_output.audit.ignored_score_dimensions == ()
