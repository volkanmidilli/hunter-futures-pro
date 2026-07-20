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

from hunter.pairlist_export.fingerprint import compute_pair_fingerprint
from hunter.pairlist_export.models import (
    REASON_DATA_SUFFICIENCY,
    REASON_INSUFFICIENT_EVIDENCE,
    REASON_OI_LIQUIDITY,
    REASON_RS_SCORE,
    PairScore,
    PairlistRankingConfig,
    RankedPair,
    PairlistRankingError,
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
