"""Deterministic ranking adapter over existing Hunter research outputs (SPEC-074).

Consumes existing relative-strength, open-interest, and research-universe
data to produce an explainable, reproducible pair ranking without
duplicating any of those algorithms.

Tie-breaking order (SPEC-074):
  1. Primary research rank (RS composite score, descending)
  2. Liquidity rank (OI score, descending)
  3. Data sufficiency (better data = higher)
  4. Pair string ascending (deterministic fallback)
"""

from __future__ import annotations

from decimal import Decimal

from hunter.pairlist_export.fingerprint import compute_pair_fingerprint, compute_pair_fingerprint_v2
from hunter.pairlist_export.models import (
    REASON_DATA_SUFFICIENCY,
    REASON_INSUFFICIENT_EVIDENCE,
    REASON_LIQUIDITY_SCORE,
    REASON_OI_LIQUIDITY,
    REASON_RS_SCORE,
    PairScore,
    PairlistRankingConfig,
    RankedPair,
    PairlistRankingError,
)
from hunter.pairlist_export.ranking_input_v2 import (
    PROFILE_TIE_BREAK_DIMENSIONS,
    ProfileFieldMismatchError,
    RankingProfile,
    validate_profile_fields,
)


def rank_pairs(
    config: PairlistRankingConfig,
    eligible_pairs: tuple[str, ...],
    rs_scores: dict[str, Decimal | None],
    oi_scores: dict[str, Decimal | None],
    data_quality: dict[str, Decimal | None] | None = None,
) -> tuple[RankedPair, ...]:
    """Rank eligible pairs deterministically for the daily pairlist.

    Pairs with sufficient evidence receive a composite rank.  Pairs
    missing both RS and OI data are rejected with ``INSUFFICIENT_EVIDENCE``.
    Pairs present in only one of RS/OI score maps receive a partial score.

    The result is sorted by the SPEC-074 tie-breaking order:
    RS score (desc) → OI score (desc) → data quality (desc) → pair name (asc).

    Args:
        config: Ranking and publishing thresholds.
        eligible_pairs: Ordered tuple of eligible pair symbols
            (e.g. ``"BTC/USDT:USDT"``).
        rs_scores: Map of pair → RS score (or ``None`` for unavailable).
        oi_scores: Map of pair → OI score (or ``None`` for unavailable).
        data_quality: Optional map of pair → data quality percentage
            (0–100, or ``None`` for unavailable).

    Returns:
        Tuple of :class:`RankedPair` sorted by deterministic rank.
        Selected pairs have ``selected=True`` and appear first.

    Raises:
        PairlistRankingError: If no eligible pairs have sufficient evidence.
    """
    if not isinstance(config, PairlistRankingConfig):
        raise PairlistRankingError(
            f"config must be PairlistRankingConfig, got {type(config)}"
        )

    dq: dict[str, Decimal | None] = dict(data_quality or {})

    # Build candidate scores for all eligible pairs.
    candidates: list[PairScore] = []
    for pair in eligible_pairs:
        rs = rs_scores.get(pair)
        oi = oi_scores.get(pair)
        dq_val = dq.get(pair)

        reasons: list[str] = []

        if rs is not None:
            reasons.append(REASON_RS_SCORE)
        if oi is not None:
            reasons.append(REASON_OI_LIQUIDITY)
        if dq_val is not None:
            reasons.append(REASON_DATA_SUFFICIENCY)

        if rs is None and oi is None:
            reasons.append(REASON_INSUFFICIENT_EVIDENCE)

        candidates.append(
            PairScore(
                pair=pair,
                rs_score=rs,
                oi_score=oi,
                data_quality_pct=dq_val,
                reason_codes=tuple(reasons),
            )
        )

    if not candidates:
        raise PairlistRankingError("no eligible pairs provided for ranking")

    # Sort by SPEC-074 tie-breaking order: RS score (desc) → OI score (desc)
    # → data quality (desc) → pair name (asc).  Python's sort is ascending,
    # so descending fields are negated; pair name sorts ascending as-is.
    def _compound_key(c: PairScore) -> tuple:
        return (
            # Scores: higher → smaller negative → comes first.
            -(c.rs_score if c.rs_score is not None else Decimal("-Infinity")),
            -(c.oi_score if c.oi_score is not None else Decimal("-Infinity")),
            -(c.data_quality_pct if c.data_quality_pct is not None else Decimal("-Infinity")),
            c.pair,
        )

    sorted_candidates = sorted(candidates, key=_compound_key)

    have_sufficient = [
        c for c in sorted_candidates
        if REASON_INSUFFICIENT_EVIDENCE not in c.reason_codes
    ]
    if not have_sufficient:
        raise PairlistRankingError(
            "no eligible pairs have sufficient evidence (RS and/or OI data)"
        )

    # Assign ranks and mark selected up to publish_candidates.
    ranked: list[RankedPair] = []
    for idx, score in enumerate(sorted_candidates):
        rank = idx + 1
        selected = (
            rank <= config.publish_candidates
            and REASON_INSUFFICIENT_EVIDENCE not in score.reason_codes
        )

        fingerprint = compute_pair_fingerprint(
            pair=score.pair,
            rank=rank,
            rs_score=score.rs_score,
            oi_score=score.oi_score,
            data_quality_pct=score.data_quality_pct,
            reason_codes=score.reason_codes,
        )

        ranked.append(
            RankedPair(
                pair=score.pair,
                rank=rank,
                selected=selected,
                rs_score=score.rs_score,
                oi_score=score.oi_score,
                reason_codes=score.reason_codes,
                fingerprint=fingerprint,
            )
        )

    return tuple(ranked)


def rank_pairs_v2(
    config: PairlistRankingConfig,
    ranking_profile: RankingProfile,
    eligible_pairs: tuple[str, ...],
    rs_scores: dict[str, Decimal | None],
    liquidity_scores: dict[str, Decimal | None],
    oi_scores: dict[str, Decimal | None],
    data_quality: dict[str, Decimal | None] | None = None,
    oi_available: bool = False,
) -> tuple[RankedPair, ...]:
    """Rank eligible pairs under a SPEC-075 v2 ranking profile.

    Only ``V2_RS_LIQUIDITY`` and ``V2_RS_OI_LIQUIDITY`` are accepted here --
    ``V1_RS_OI`` must keep using :func:`rank_pairs` unchanged (SPEC-075
    requires exact v1-behavior preservation, including its any-of-rs-or-oi
    evidence rule, which differs from v2's all-required rule below).

    Both v2 profiles require RS, every tie-break dimension, and data
    quality to be present (non-``None``) for every eligible pair -- a pair
    missing any of them is marked ``INSUFFICIENT_EVIDENCE`` and excluded
    from selection, and the profile-field validation below independently
    rejects any payload where an *eligible* pair is missing a
    profile-required dimension (``PROFILE_FIELD_MISMATCH``).

    One profile applies to the whole artifact; the profile is never
    switched or downgraded per pair. Tie-break order is profile-specific
    (see :data:`hunter.pairlist_export.ranking_input_v2.PROFILE_TIE_BREAK_DIMENSIONS`).
    The surrounding shape (selection cutoff at ``publish_candidates``,
    fingerprinting per pair) mirrors :func:`rank_pairs`.

    Raises:
        ProfileFieldMismatchError: If the supplied score maps violate the
            declared profile's field rules (``PROFILE_FIELD_MISMATCH``).
        PairlistRankingError: If ``ranking_profile`` is ``V1_RS_OI``, or if
            no eligible pairs are supplied.
    """
    if not isinstance(config, PairlistRankingConfig):
        raise PairlistRankingError(f"config must be PairlistRankingConfig, got {type(config)}")
    if ranking_profile is RankingProfile.V1_RS_OI:
        raise PairlistRankingError("rank_pairs_v2 does not accept V1_RS_OI; use rank_pairs instead")

    validate_profile_fields(
        ranking_profile=ranking_profile,
        eligible_pairs=eligible_pairs,
        rs_scores=rs_scores,
        liquidity_scores=liquidity_scores,
        oi_scores=oi_scores,
        oi_available=oi_available,
        data_quality=data_quality,
    )

    dq: dict[str, Decimal | None] = dict(data_quality or {})
    tie_break_dims = PROFILE_TIE_BREAK_DIMENSIONS[ranking_profile]

    candidates: list[PairScore] = []
    for pair in eligible_pairs:
        rs = rs_scores.get(pair)
        oi = oi_scores.get(pair)
        liq = liquidity_scores.get(pair)
        dq_val = dq.get(pair)

        reasons: list[str] = []
        if rs is not None:
            reasons.append(REASON_RS_SCORE)
        if oi is not None:
            reasons.append(REASON_OI_LIQUIDITY)
        if liq is not None:
            reasons.append(REASON_LIQUIDITY_SCORE)
        if dq_val is not None:
            reasons.append(REASON_DATA_SUFFICIENCY)

        required = ("rs",) + tie_break_dims
        have_required = all(
            {"rs": rs, "oi": oi, "liquidity": liq, "data_quality": dq_val}[dim] is not None
            for dim in required
        )
        if not have_required:
            reasons.append(REASON_INSUFFICIENT_EVIDENCE)

        candidates.append(
            PairScore(
                pair=pair,
                rs_score=rs,
                oi_score=oi,
                liquidity_score=liq,
                data_quality_pct=dq_val,
                reason_codes=tuple(reasons),
            )
        )

    if not candidates:
        raise PairlistRankingError("no eligible pairs provided for ranking")

    neg_inf = Decimal("-Infinity")

    def _dim_value(score: PairScore, dim: str) -> Decimal:
        value = {"oi": score.oi_score, "liquidity": score.liquidity_score, "data_quality": score.data_quality_pct}[dim]
        return -(value if value is not None else neg_inf)

    def _compound_key(score: PairScore) -> tuple:
        key: tuple = (-(score.rs_score if score.rs_score is not None else neg_inf),)
        key += tuple(_dim_value(score, dim) for dim in tie_break_dims)
        key += (score.pair,)
        return key

    sorted_candidates = sorted(candidates, key=_compound_key)

    have_sufficient = [c for c in sorted_candidates if REASON_INSUFFICIENT_EVIDENCE not in c.reason_codes]
    if not have_sufficient:
        raise PairlistRankingError("no eligible pairs have sufficient evidence for this ranking profile")

    ranked: list[RankedPair] = []
    for idx, score in enumerate(sorted_candidates):
        rank = idx + 1
        selected = rank <= config.publish_candidates and REASON_INSUFFICIENT_EVIDENCE not in score.reason_codes

        fingerprint = compute_pair_fingerprint_v2(
            pair=score.pair,
            rank=rank,
            ranking_profile=ranking_profile.value,
            rs_score=score.rs_score,
            oi_score=score.oi_score,
            liquidity_score=score.liquidity_score,
            data_quality_pct=score.data_quality_pct,
            reason_codes=score.reason_codes,
        )

        ranked.append(
            RankedPair(
                pair=score.pair,
                rank=rank,
                selected=selected,
                rs_score=score.rs_score,
                oi_score=score.oi_score,
                liquidity_score=score.liquidity_score,
                reason_codes=score.reason_codes,
                fingerprint=fingerprint,
            )
        )

    return tuple(ranked)
