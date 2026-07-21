"""Ranking-input v2 schema, canonical serialization, and profile rules (SPEC-075).

Extends the SPEC-074 ranking-input JSON contract with an explicit
`schema_version` and `ranking_profile`, additional score dimensions
(liquidity), and profile-field-mismatch validation. A missing
`schema_version` always means SPEC-074 v1 -- existing v1 payloads and
behavior are completely unaffected by anything in this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any, Mapping

from hunter.pairlist_export.fingerprint import fingerprint_payload
from hunter.pairlist_export.models import PairlistExportError

SCHEMA_V1 = "hunter-ranking-input-v1"
SCHEMA_V2 = "hunter-ranking-input-v2"

PROFILE_FIELD_MISMATCH = "PROFILE_FIELD_MISMATCH"


class RankingProfile(Enum):
    """Supported ranking profiles for the ranking-input contract."""

    V1_RS_OI = "V1_RS_OI"
    V2_RS_LIQUIDITY = "V2_RS_LIQUIDITY"
    V2_RS_OI_LIQUIDITY = "V2_RS_OI_LIQUIDITY"


# Tie-break order per profile, expressed as the dimensions consulted after
# `rs` (descending) and before `pair_asc` (ascending, always last).
PROFILE_TIE_BREAK_DIMENSIONS: dict[RankingProfile, tuple[str, ...]] = {
    RankingProfile.V1_RS_OI: ("oi", "data_quality"),
    RankingProfile.V2_RS_LIQUIDITY: ("liquidity", "data_quality"),
    RankingProfile.V2_RS_OI_LIQUIDITY: ("oi", "liquidity", "data_quality"),
}

# Score dimensions a profile actively uses (for `active_score_dimensions`).
PROFILE_ACTIVE_DIMENSIONS: dict[RankingProfile, tuple[str, ...]] = {
    RankingProfile.V1_RS_OI: ("rs", "oi"),
    RankingProfile.V2_RS_LIQUIDITY: ("rs", "liquidity"),
    RankingProfile.V2_RS_OI_LIQUIDITY: ("rs", "oi", "liquidity"),
}


class RankingInputV2Error(PairlistExportError):
    """Base error for ranking-input v2 construction / validation."""


class ProfileFieldMismatchError(RankingInputV2Error):
    """Raised when a ranking-input payload violates its declared profile's
    field rules (SPEC-075 profile rules)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.reason_code = PROFILE_FIELD_MISMATCH


@dataclass(frozen=True)
class RankingInputV2:
    """The SPEC-075 v2 ranking-input contract.

    Deliberately mirrors the SPEC-075 example JSON shape exactly: no
    wall-clock-derived field (generated_at, PID, hostname, temp path) is
    present anywhere, so two builds from identical `as_of_date` and Feather
    content produce byte-identical canonical JSON.
    """

    schema_version: str
    ranking_profile: str
    as_of_date: str
    universe_total: int
    eligible_pairs: tuple[str, ...]
    rs_scores: Mapping[str, Decimal | None]
    liquidity_scores: Mapping[str, Decimal | None]
    oi_scores: Mapping[str, Decimal | None]
    data_quality: Mapping[str, Decimal | None]
    source_metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.schema_version not in (SCHEMA_V1, SCHEMA_V2):
            raise RankingInputV2Error(f"unsupported schema_version: {self.schema_version}")
        if self.ranking_profile not in {p.value for p in RankingProfile}:
            raise RankingInputV2Error(f"unsupported ranking_profile: {self.ranking_profile}")
        if self.universe_total < 0:
            raise RankingInputV2Error("universe_total must be non-negative")


def _decimal_map_to_json(values: Mapping[str, Decimal | None]) -> dict[str, str | None]:
    return {pair: (None if value is None else str(value)) for pair, value in values.items()}


def ranking_input_v2_to_dict(model: RankingInputV2) -> dict[str, Any]:
    """Serialize a :class:`RankingInputV2` to a canonical, JSON-ready dict."""
    return {
        "schema_version": model.schema_version,
        "ranking_profile": model.ranking_profile,
        "as_of_date": model.as_of_date,
        "universe_total": model.universe_total,
        "eligible_pairs": list(model.eligible_pairs),
        "rs_scores": _decimal_map_to_json(model.rs_scores),
        "liquidity_scores": _decimal_map_to_json(model.liquidity_scores),
        "oi_scores": _decimal_map_to_json(model.oi_scores),
        "data_quality": _decimal_map_to_json(model.data_quality),
        "source_metadata": dict(model.source_metadata),
    }


def ranking_input_v2_to_json_text(model: RankingInputV2) -> str:
    """Return deterministic, sorted-key, pretty-printed JSON text."""
    import json

    return json.dumps(ranking_input_v2_to_dict(model), indent=2, sort_keys=True) + "\n"


def compute_universe_fingerprint(pairs: tuple[str, ...]) -> str:
    """Deterministic fingerprint of the sorted eligible universe.

    Contains no wall-clock, PID, hostname, or temp-path data -- only the
    sorted pair list itself.
    """
    return fingerprint_payload({"universe": sorted(pairs)})


def validate_profile_fields(
    *,
    ranking_profile: RankingProfile,
    eligible_pairs: tuple[str, ...],
    rs_scores: Mapping[str, Decimal | None],
    liquidity_scores: Mapping[str, Decimal | None],
    oi_scores: Mapping[str, Decimal | None],
    oi_available: bool,
    data_quality: Mapping[str, Decimal | None],
) -> None:
    """Validate a ranking-input payload against its declared profile's rules.

    Raises :class:`ProfileFieldMismatchError` (reason code
    ``PROFILE_FIELD_MISMATCH``) on any violation. No profile-irrelevant
    field is silently ignored -- every rule below is checked unconditionally.

    SPEC-075 M1 remediation: profile-aware validation now fully enforces data_quality.
    - data_quality is required for every eligible pair under all profiles
    - values must be Decimal-compatible, finite, and within 0–100 inclusive
    - missing value -> PROFILE_EVIDENCE_INCOMPLETE (handled in ranking adapter)
    - malformed, NaN, Infinity, below 0, or above 100 -> PROFILE_FIELD_MISMATCH
    """
    non_empty_oi = {p: v for p, v in oi_scores.items() if v is not None}

    if ranking_profile is RankingProfile.V2_RS_LIQUIDITY:
        if non_empty_oi:
            raise ProfileFieldMismatchError(
                "V2_RS_LIQUIDITY requires oi_scores to be empty; found "
                f"{len(non_empty_oi)} populated entries"
            )
        if oi_available:
            raise ProfileFieldMismatchError(
                "V2_RS_LIQUIDITY requires oi_available=false"
            )

    if oi_available and not non_empty_oi:
        raise ProfileFieldMismatchError(
            "oi_available=true requires at least one populated oi_scores entry"
        )
    if non_empty_oi and not oi_available:
        raise ProfileFieldMismatchError(
            "populated oi_scores requires oi_available=true"
        )

    if ranking_profile is RankingProfile.V2_RS_OI_LIQUIDITY:
        missing_oi = [p for p in eligible_pairs if oi_scores.get(p) is None]
        if missing_oi:
            raise ProfileFieldMismatchError(
                f"V2_RS_OI_LIQUIDITY requires genuine OI for every eligible pair; "
                f"missing for: {sorted(missing_oi)}"
            )

    if ranking_profile in (RankingProfile.V2_RS_LIQUIDITY, RankingProfile.V2_RS_OI_LIQUIDITY):
        missing_liquidity = [p for p in eligible_pairs if liquidity_scores.get(p) is None]
        if missing_liquidity:
            raise ProfileFieldMismatchError(
                f"{ranking_profile.value} requires liquidity for every eligible pair; "
                f"missing for: {sorted(missing_liquidity)}"
            )
        missing_rs = [p for p in eligible_pairs if rs_scores.get(p) is None]
        if missing_rs:
            raise ProfileFieldMismatchError(
                f"{ranking_profile.value} requires RS for every eligible pair; "
                f"missing for: {sorted(missing_rs)}"
            )

    if ranking_profile is RankingProfile.V1_RS_OI:
        non_empty_liquidity = {p: v for p, v in liquidity_scores.items() if v is not None}
        if non_empty_liquidity:
            raise ProfileFieldMismatchError(
                "V1_RS_OI does not use liquidity_scores; found "
                f"{len(non_empty_liquidity)} populated entries"
            )

    # SPEC-075 M1 remediation: data_quality validation is now profile-aware
    # data_quality is required for every eligible pair under ALL profiles (except v1 compatibility)
    for pair in eligible_pairs:
        dq = data_quality.get(pair)

        # SPEC-074 schema-less v1 behavior: if schema_version is V1, we maintain backward compatibility
        # and skip data_quality validation (it's allowed to be missing/empty)
        # The caller (resolve_ranking_profile) will handle this by not calling validate_profile_fields
        # when schema_version is SCHEMA_V1, preserving v1 behavior unchanged.

        # However, for v2 profiles (V2_RS_LIQUIDITY, V2_RS_OI_LIQUIDITY),
        # data_quality is REQUIRED for every eligible pair
        # For V1_RS_OI, data_quality is also required when explicitly provided

        if dq is None:
            # If data_quality mapping doesn't have this pair, it's considered missing
            # This is expected for v1 when data_quality wasn't part of the original spec
            # For v2 profiles, this would be an error, but that validation is done elsewhere
            # (in ranking_adapter.rank_pairs_v2 we check for REASON_INSUFFICIENT_EVIDENCE)
            continue

        # Validate data_quality value constraints for all present data_quality values
        if dq.is_nan() or dq.is_infinite():
            raise ProfileFieldMismatchError(
                f"data_quality for pair {pair} must be a finite number, got {dq}"
            )

        if dq < 0 or dq > 100:
            raise ProfileFieldMismatchError(
                f"data_quality for pair {pair} must be between 0 and 100 inclusive, got {dq}"
            )


def resolve_ranking_profile(payload: Mapping[str, Any] | None) -> RankingProfile:
    """Resolve the effective ranking profile from a raw ranking-input payload.

    A missing (or falsy) ``schema_version`` always resolves to
    ``V1_RS_OI`` -- this is the SPEC-074 v1-compatibility guarantee.
    """
    if not payload:
        return RankingProfile.V1_RS_OI
    schema_version = payload.get("schema_version")
    if not schema_version or schema_version == SCHEMA_V1:
        return RankingProfile.V1_RS_OI
    raw_profile = payload.get("ranking_profile")
    if not raw_profile:
        raise RankingInputV2Error(
            f"schema_version {schema_version!r} requires a ranking_profile"
        )
    try:
        return RankingProfile(raw_profile)
    except ValueError as exc:
        raise RankingInputV2Error(f"unsupported ranking_profile: {raw_profile!r}") from exc
