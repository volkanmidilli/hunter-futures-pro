"""Focused tests for hunter.pairlist_export.ranking_input_v2 (SPEC-075)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from hunter.pairlist_export.ranking_input_v2 import (
    SCHEMA_V1,
    SCHEMA_V2,
    ProfileFieldMismatchError,
    RankingInputV2,
    RankingInputV2Error,
    RankingProfile,
    compute_universe_fingerprint,
    ranking_input_v2_to_dict,
    ranking_input_v2_to_json_text,
    resolve_ranking_profile,
    validate_profile_fields,
)


def _v2_input(**overrides) -> RankingInputV2:
    defaults = dict(
        schema_version=SCHEMA_V2,
        ranking_profile=RankingProfile.V2_RS_LIQUIDITY.value,
        as_of_date="2026-07-21",
        universe_total=1,
        eligible_pairs=("BTC/USDT:USDT",),
        rs_scores={"BTC/USDT:USDT": Decimal("80")},
        liquidity_scores={"BTC/USDT:USDT": Decimal("70")},
        oi_scores={},
        data_quality={"BTC/USDT:USDT": Decimal("100")},
    )
    defaults.update(overrides)
    return RankingInputV2(**defaults)


# ---------------------------------------------------------------------------
# Schema-less v1 resolution.
# ---------------------------------------------------------------------------


def test_resolve_ranking_profile_missing_schema_version_is_v1() -> None:
    assert resolve_ranking_profile(None) == RankingProfile.V1_RS_OI
    assert resolve_ranking_profile({}) == RankingProfile.V1_RS_OI
    assert resolve_ranking_profile({"eligible_pairs": ["BTC/USDT:USDT"]}) == RankingProfile.V1_RS_OI


def test_resolve_ranking_profile_explicit_v1_schema() -> None:
    assert resolve_ranking_profile({"schema_version": SCHEMA_V1}) == RankingProfile.V1_RS_OI


def test_resolve_ranking_profile_v2_requires_profile() -> None:
    with pytest.raises(RankingInputV2Error):
        resolve_ranking_profile({"schema_version": SCHEMA_V2})


def test_resolve_ranking_profile_v2_reads_profile() -> None:
    payload = {"schema_version": SCHEMA_V2, "ranking_profile": "V2_RS_LIQUIDITY"}
    assert resolve_ranking_profile(payload) == RankingProfile.V2_RS_LIQUIDITY


def test_resolve_ranking_profile_rejects_unknown_profile() -> None:
    payload = {"schema_version": SCHEMA_V2, "ranking_profile": "NOT_A_PROFILE"}
    with pytest.raises(RankingInputV2Error):
        resolve_ranking_profile(payload)


# ---------------------------------------------------------------------------
# Model construction and serialization.
# ---------------------------------------------------------------------------


def test_ranking_input_v2_rejects_unknown_schema_version() -> None:
    with pytest.raises(RankingInputV2Error):
        _v2_input(schema_version="bogus")


def test_ranking_input_v2_rejects_unknown_profile() -> None:
    with pytest.raises(RankingInputV2Error):
        _v2_input(ranking_profile="bogus")


def test_ranking_input_v2_to_dict_shape() -> None:
    payload = ranking_input_v2_to_dict(_v2_input())
    assert payload["schema_version"] == SCHEMA_V2
    assert payload["ranking_profile"] == "V2_RS_LIQUIDITY"
    assert payload["rs_scores"] == {"BTC/USDT:USDT": "80"}
    assert payload["oi_scores"] == {}


def test_ranking_input_v2_json_text_is_deterministic() -> None:
    a = ranking_input_v2_to_json_text(_v2_input())
    b = ranking_input_v2_to_json_text(_v2_input())
    assert a == b


def test_ranking_input_v2_json_text_has_no_wallclock_fields() -> None:
    text = ranking_input_v2_to_json_text(_v2_input())
    for forbidden in ("generated_at", "pid", "hostname", "tmp"):
        assert forbidden not in text.lower()


# ---------------------------------------------------------------------------
# Universe fingerprint.
# ---------------------------------------------------------------------------


def test_universe_fingerprint_is_order_independent() -> None:
    a = compute_universe_fingerprint(("BTC/USDT:USDT", "ETH/USDT:USDT"))
    b = compute_universe_fingerprint(("ETH/USDT:USDT", "BTC/USDT:USDT"))
    assert a == b


def test_universe_fingerprint_changes_with_content() -> None:
    a = compute_universe_fingerprint(("BTC/USDT:USDT",))
    b = compute_universe_fingerprint(("BTC/USDT:USDT", "ETH/USDT:USDT"))
    assert a != b


# ---------------------------------------------------------------------------
# Profile-field-mismatch validation -- all profiles.
# ---------------------------------------------------------------------------


def test_v2_rs_liquidity_rejects_populated_oi() -> None:
    with pytest.raises(ProfileFieldMismatchError):
        validate_profile_fields(
            ranking_profile=RankingProfile.V2_RS_LIQUIDITY,
            eligible_pairs=("BTC/USDT:USDT",),
            rs_scores={"BTC/USDT:USDT": Decimal("80")},
            liquidity_scores={"BTC/USDT:USDT": Decimal("70")},
            oi_scores={"BTC/USDT:USDT": Decimal("60")},
            oi_available=True,
            data_quality={"BTC/USDT:USDT": Decimal("100")},
        )


def test_v2_rs_liquidity_rejects_oi_available_true() -> None:
    with pytest.raises(ProfileFieldMismatchError):
        validate_profile_fields(
            ranking_profile=RankingProfile.V2_RS_LIQUIDITY,
            eligible_pairs=("BTC/USDT:USDT",),
            rs_scores={"BTC/USDT:USDT": Decimal("80")},
            liquidity_scores={"BTC/USDT:USDT": Decimal("70")},
            oi_scores={},
            oi_available=True,
            data_quality={"BTC/USDT:USDT": Decimal("100")},
        )


def test_oi_available_true_requires_populated_oi() -> None:
    with pytest.raises(ProfileFieldMismatchError):
        validate_profile_fields(
            ranking_profile=RankingProfile.V2_RS_OI_LIQUIDITY,
            eligible_pairs=("BTC/USDT:USDT",),
            rs_scores={"BTC/USDT:USDT": Decimal("80")},
            liquidity_scores={"BTC/USDT:USDT": Decimal("70")},
            oi_scores={},
            oi_available=True,
            data_quality={"BTC/USDT:USDT": Decimal("100")},
        )


def test_populated_oi_requires_oi_available_true() -> None:
    with pytest.raises(ProfileFieldMismatchError):
        validate_profile_fields(
            ranking_profile=RankingProfile.V2_RS_OI_LIQUIDITY,
            eligible_pairs=("BTC/USDT:USDT",),
            rs_scores={"BTC/USDT:USDT": Decimal("80")},
            liquidity_scores={"BTC/USDT:USDT": Decimal("70")},
            oi_scores={"BTC/USDT:USDT": Decimal("60")},
            oi_available=False,
            data_quality={"BTC/USDT:USDT": Decimal("100")},
        )


def test_v2_rs_oi_liquidity_requires_oi_for_every_eligible_pair() -> None:
    with pytest.raises(ProfileFieldMismatchError):
        validate_profile_fields(
            ranking_profile=RankingProfile.V2_RS_OI_LIQUIDITY,
            eligible_pairs=("BTC/USDT:USDT", "ETH/USDT:USDT"),
            rs_scores={"BTC/USDT:USDT": Decimal("80"), "ETH/USDT:USDT": Decimal("60")},
            liquidity_scores={"BTC/USDT:USDT": Decimal("70"), "ETH/USDT:USDT": Decimal("50")},
            oi_scores={"BTC/USDT:USDT": Decimal("60")},  # missing ETH
            oi_available=True,
            data_quality={"BTC/USDT:USDT": Decimal("100"), "ETH/USDT:USDT": Decimal("90")},
        )


def test_v2_profiles_require_liquidity_for_every_eligible_pair() -> None:
    with pytest.raises(ProfileFieldMismatchError):
        validate_profile_fields(
            ranking_profile=RankingProfile.V2_RS_LIQUIDITY,
            eligible_pairs=("BTC/USDT:USDT", "ETH/USDT:USDT"),
            rs_scores={"BTC/USDT:USDT": Decimal("80"), "ETH/USDT:USDT": Decimal("60")},
            liquidity_scores={"BTC/USDT:USDT": Decimal("70")},  # missing ETH
            oi_scores={},
            oi_available=False,
            data_quality={"BTC/USDT:USDT": Decimal("100"), "ETH/USDT:USDT": Decimal("90")},
        )


def test_v2_profiles_require_rs_for_every_eligible_pair() -> None:
    with pytest.raises(ProfileFieldMismatchError):
        validate_profile_fields(
            ranking_profile=RankingProfile.V2_RS_LIQUIDITY,
            eligible_pairs=("BTC/USDT:USDT", "ETH/USDT:USDT"),
            rs_scores={"BTC/USDT:USDT": Decimal("80")},  # missing ETH
            liquidity_scores={"BTC/USDT:USDT": Decimal("70"), "ETH/USDT:USDT": Decimal("50")},
            oi_scores={},
            oi_available=False,
            data_quality={"BTC/USDT:USDT": Decimal("100"), "ETH/USDT:USDT": Decimal("90")},
        )


def test_v1_rejects_populated_liquidity() -> None:
    with pytest.raises(ProfileFieldMismatchError):
        validate_profile_fields(
            ranking_profile=RankingProfile.V1_RS_OI,
            eligible_pairs=("BTC/USDT:USDT",),
            rs_scores={"BTC/USDT:USDT": Decimal("80")},
            liquidity_scores={"BTC/USDT:USDT": Decimal("70")},
            oi_scores={"BTC/USDT:USDT": Decimal("60")},
            oi_available=True,
            data_quality={"BTC/USDT:USDT": Decimal("100")},
        )


@pytest.mark.parametrize(
    "profile",
    [RankingProfile.V1_RS_OI, RankingProfile.V2_RS_LIQUIDITY, RankingProfile.V2_RS_OI_LIQUIDITY],
)
def test_all_profiles_accept_their_own_well_formed_payload(profile: RankingProfile) -> None:
    if profile is RankingProfile.V1_RS_OI:
        validate_profile_fields(
            ranking_profile=profile,
            eligible_pairs=("BTC/USDT:USDT",),
            rs_scores={"BTC/USDT:USDT": Decimal("80")},
            liquidity_scores={},
            oi_scores={"BTC/USDT:USDT": Decimal("60")},
            oi_available=True,
            data_quality={"BTC/USDT:USDT": Decimal("100")},
        )
    elif profile is RankingProfile.V2_RS_LIQUIDITY:
        validate_profile_fields(
            ranking_profile=profile,
            eligible_pairs=("BTC/USDT:USDT",),
            rs_scores={"BTC/USDT:USDT": Decimal("80")},
            liquidity_scores={"BTC/USDT:USDT": Decimal("70")},
            oi_scores={},
            oi_available=False,
            data_quality={"BTC/USDT:USDT": Decimal("100")},
        )
    else:
        validate_profile_fields(
            ranking_profile=profile,
            eligible_pairs=("BTC/USDT:USDT",),
            rs_scores={"BTC/USDT:USDT": Decimal("80")},
            liquidity_scores={"BTC/USDT:USDT": Decimal("70")},
            oi_scores={"BTC/USDT:USDT": Decimal("60")},
            oi_available=True,
            data_quality={"BTC/USDT:USDT": Decimal("100")},
        )
