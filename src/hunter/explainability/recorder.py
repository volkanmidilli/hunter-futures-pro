"""Recorder for SPEC-078 Hunter Candidate Explainability.

Builds per-candidate :class:`CandidateExplanationRecord` objects from the
*actual outputs* of the real selection pipeline (the ranked pairs emitted
by ``hunter.pairlist_export.ranking_adapter``, the publish-gate result
emitted by ``hunter.pairlist_export.validator``, and the ranking config
that owns the thresholds).  Nothing here recomputes eligibility, scores,
ranking, or selection: every stage status, metric, threshold, and reason
code is taken from the pipeline component that owns that criterion.

Stage order mirrors the real selection flow:

1. ``universe``           -- the pair was in the ranked candidate universe.
2. ``data_quality``       -- data-quality evidence (required under v2
                             profiles; tie-break/positive evidence under v1).
3. ``liquidity``          -- OI/liquidity evidence per the ranking profile.
4. ``relative_strength``  -- RS evidence (primary ranking dimension).
5. ``ranking``            -- rank vs. the ``target_final_pairs`` cutoff.
6. ``publish``            -- publish-gate outcome for selected pairs.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Mapping

from hunter.explainability.models import (
    EXPLAINABILITY_SCHEMA_VERSION,
    REASON_OUTSIDE_TARGET_FINAL_PAIRS,
    REASON_PUBLISH_BLOCKED,
    STAGE_FAIL,
    STAGE_PASS,
    STAGE_SKIP,
    CandidateExplanationRecord,
    CandidateStageDecision,
    ExplainabilityRunManifest,
)
from hunter.pairlist_export.models import (
    REASON_DATA_SUFFICIENCY,
    REASON_INSUFFICIENT_EVIDENCE,
    REASON_LIQUIDITY_SCORE,
    REASON_OI_LIQUIDITY,
    REASON_PROFILE_EVIDENCE_INCOMPLETE,
    REASON_RS_SCORE,
    RankedPair,
)
from hunter.pairlist_export.ranking_input_v2 import PROFILE_ACTIVE_DIMENSIONS, RankingProfile

STAGE_UNIVERSE = "universe"
STAGE_DATA_QUALITY = "data_quality"
STAGE_LIQUIDITY = "liquidity"
STAGE_RELATIVE_STRENGTH = "relative_strength"
STAGE_RANKING = "ranking"
STAGE_PUBLISH = "publish"

# Reason codes that mean "excluded from selection for lack of evidence",
# owned by the ranking adapter / ranking-input contract.
_INSUFFICIENCY_CODES: frozenset[str] = frozenset(
    {REASON_INSUFFICIENT_EVIDENCE, REASON_PROFILE_EVIDENCE_INCOMPLETE}
)

GATE_OK = "OK"


@dataclass(frozen=True)
class PairlistRunObservation:
    """The real pipeline outputs captured at the end of one selection run.

    This is the recorder's only input: the ranked pairs exactly as the
    ranking adapter emitted them, the gate outcome exactly as the publish
    gate emitted it, the thresholds from the ranking config, and whether
    the publish actually completed.
    """

    as_of_date: str
    ranking_profile: str
    universe_total: int
    eligible_pairs: tuple[str, ...]
    ranked_pairs: tuple[RankedPair, ...]
    target_final_pairs: int
    min_pairs: int
    max_pairs: int
    gate_allowed: bool
    gate_reason_codes: tuple[str, ...]
    published: bool
    # The real observed data-quality scores supplied to the ranker.  v1
    # ``RankedPair`` does not carry ``data_quality_pct`` (the pipeline
    # itself drops it), so this map is the fallback source for the genuine
    # metric the ranking actually consumed.  Never synthesized.
    data_quality_scores: Mapping[str, Decimal | None] | None = None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _decimal_str(value: Decimal | None) -> str | None:
    return None if value is None else str(value)


def build_run_id(observation: PairlistRunObservation) -> str:
    """Deterministic, content-bound run id.

    Derived from the as-of date, ranking profile, and a digest over the
    ranked-pair fingerprints the pipeline itself computed -- identical
    pipeline output always yields the same run id, and different output
    never collides with an already-recorded run.
    """
    canonical = json.dumps(
        [
            [p.pair, p.rank, p.selected, p.fingerprint]
            for p in observation.ranked_pairs
        ]
        + [[observation.gate_allowed, list(observation.gate_reason_codes)]],
        separators=(",", ":"),
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]
    return f"{observation.as_of_date}__{observation.ranking_profile}__{digest}"


def _insufficiency_codes(pair: RankedPair) -> tuple[str, ...]:
    return tuple(c for c in pair.reason_codes if c in _INSUFFICIENCY_CODES)


def _evidence_status(present: bool, *, required: bool, insufficient: bool) -> str:
    """Map recorded evidence presence to a stage status.

    ``required``/``insufficient`` come from the owning components (the
    ranking profile's active dimensions and the adapter-emitted reason
    codes); they are never re-derived here from raw scores.
    """
    if present:
        return STAGE_PASS
    if required or insufficient:
        return STAGE_FAIL
    return STAGE_SKIP


def _build_stages(
    pair: RankedPair,
    observation: PairlistRunObservation,
) -> tuple[CandidateStageDecision, ...]:
    profile = RankingProfile(observation.ranking_profile)
    active_dims = PROFILE_ACTIVE_DIMENSIONS[profile]
    insufficient = bool(_insufficiency_codes(pair))
    insufficiency = _insufficiency_codes(pair)

    # 1 -- universe: a recorded candidate was in the ranked universe by
    # construction; the metrics are the real run-level counts.
    universe_stage = CandidateStageDecision(
        stage_id=STAGE_UNIVERSE,
        stage_order=1,
        status=STAGE_PASS,
        metrics={
            "universe_total": observation.universe_total,
            "eligible_count": len(observation.eligible_pairs),
        },
    )

    # 2 -- data quality: always an active dimension; required (gating) under
    # v2 profiles, positive/tie-break evidence only under v1.
    dq = pair.data_quality_pct
    if dq is None and observation.data_quality_scores is not None:
        dq = observation.data_quality_scores.get(pair.pair)
    dq_required = profile is not RankingProfile.V1_RS_OI
    dq_codes: list[str] = []
    if dq is not None and REASON_DATA_SUFFICIENCY in pair.reason_codes:
        dq_codes.append(REASON_DATA_SUFFICIENCY)
    dq_codes.extend(insufficiency)
    data_quality_stage = CandidateStageDecision(
        stage_id=STAGE_DATA_QUALITY,
        stage_order=2,
        status=_evidence_status(dq is not None, required=dq_required, insufficient=insufficient),
        metrics={"data_quality_pct": _decimal_str(dq)},
        thresholds={"required": dq_required},
        reason_codes=tuple(dq_codes),
    )

    # 3 -- liquidity: OI and/or liquidity evidence per the profile's active
    # dimensions.  Under v1 the any-of-rs-or-oi rule makes a missing OI
    # non-fatal when RS is present (SKIP); under v2 every active liquidity
    # dimension is required.
    liquidity_dims = tuple(d for d in active_dims if d in ("oi", "liquidity"))
    liq_values: dict[str, Any] = {}
    if "oi" in liquidity_dims:
        liq_values["oi_score"] = _decimal_str(pair.oi_score)
    if "liquidity" in liquidity_dims:
        liq_values["liquidity_score"] = _decimal_str(pair.liquidity_score)
    liq_present = bool(liquidity_dims) and all(
        liq_values[f"{dim}_score"] is not None for dim in liquidity_dims
    )
    liq_required = profile is not RankingProfile.V1_RS_OI and bool(liquidity_dims)
    liq_codes: list[str] = []
    if pair.oi_score is not None and REASON_OI_LIQUIDITY in pair.reason_codes:
        liq_codes.append(REASON_OI_LIQUIDITY)
    if pair.liquidity_score is not None and REASON_LIQUIDITY_SCORE in pair.reason_codes:
        liq_codes.append(REASON_LIQUIDITY_SCORE)
    liq_codes.extend(insufficiency)
    liquidity_stage = CandidateStageDecision(
        stage_id=STAGE_LIQUIDITY,
        stage_order=3,
        status=_evidence_status(liq_present, required=liq_required, insufficient=insufficient),
        metrics=liq_values,
        thresholds={"required": liq_required, "active_dimensions": list(liquidity_dims)},
        reason_codes=tuple(liq_codes),
    )

    # 4 -- relative strength: the primary ranking dimension.  Under v1 the
    # any-of rule makes a missing RS non-fatal when OI is present (SKIP).
    rs = pair.rs_score
    rs_required = profile is not RankingProfile.V1_RS_OI
    rs_codes: list[str] = []
    if rs is not None and REASON_RS_SCORE in pair.reason_codes:
        rs_codes.append(REASON_RS_SCORE)
    rs_codes.extend(insufficiency)
    rs_stage = CandidateStageDecision(
        stage_id=STAGE_RELATIVE_STRENGTH,
        stage_order=4,
        status=_evidence_status(rs is not None, required=rs_required, insufficient=insufficient),
        metrics={"rs_score": _decimal_str(rs)},
        thresholds={"required": rs_required},
        reason_codes=tuple(rs_codes),
    )

    # 5 -- ranking: rank vs. the config-owned target_final_pairs cutoff.
    # The adapter's own `selected` flag is the recorded decision; the reason
    # code distinguishes exclusion-for-insufficient-evidence (real pipeline
    # code, emitted by the adapter) from exclusion by the cutoff.
    if pair.selected:
        ranking_status = STAGE_PASS
        ranking_codes: tuple[str, ...] = ()
    elif insufficiency:
        ranking_status = STAGE_FAIL
        ranking_codes = insufficiency
    else:
        ranking_status = STAGE_FAIL
        ranking_codes = (REASON_OUTSIDE_TARGET_FINAL_PAIRS,)
    ranking_stage = CandidateStageDecision(
        stage_id=STAGE_RANKING,
        stage_order=5,
        status=ranking_status,
        metrics={"rank": pair.rank},
        thresholds={"target_final_pairs": observation.target_final_pairs},
        reason_codes=ranking_codes,
        metadata={"selected": pair.selected},
    )

    # 6 -- publish: the gate's own outcome for selected pairs.
    if not pair.selected:
        publish_stage = CandidateStageDecision(
            stage_id=STAGE_PUBLISH,
            stage_order=6,
            status=STAGE_SKIP,
            metadata={"selected": False},
        )
    elif observation.gate_allowed and observation.published:
        publish_stage = CandidateStageDecision(
            stage_id=STAGE_PUBLISH,
            stage_order=6,
            status=STAGE_PASS,
            reason_codes=(GATE_OK,),
            metadata={"selected": True, "published": True},
        )
    else:
        publish_stage = CandidateStageDecision(
            stage_id=STAGE_PUBLISH,
            stage_order=6,
            status=STAGE_FAIL,
            reason_codes=(REASON_PUBLISH_BLOCKED, *observation.gate_reason_codes),
            metadata={"selected": True, "published": False},
        )

    return (
        universe_stage,
        data_quality_stage,
        liquidity_stage,
        rs_stage,
        ranking_stage,
        publish_stage,
    )


def _final_reason_codes(pair: RankedPair, observation: PairlistRunObservation) -> tuple[str, ...]:
    if pair.selected:
        if observation.gate_allowed and observation.published:
            return (GATE_OK,)
        return (REASON_PUBLISH_BLOCKED, *observation.gate_reason_codes)
    insufficiency = _insufficiency_codes(pair)
    if insufficiency:
        return insufficiency
    return (REASON_OUTSIDE_TARGET_FINAL_PAIRS,)


def build_candidate_record(
    pair: RankedPair,
    observation: PairlistRunObservation,
    *,
    run_id: str,
    completed_at: str,
) -> CandidateExplanationRecord:
    """Build the canonical explanation record for one ranked pair."""
    dq = pair.data_quality_pct
    if dq is None and observation.data_quality_scores is not None:
        dq = observation.data_quality_scores.get(pair.pair)
    return CandidateExplanationRecord(
        schema_version=EXPLAINABILITY_SCHEMA_VERSION,
        run_id=run_id,
        completed_at=completed_at,
        pair=pair.pair,
        stages=_build_stages(pair, observation),
        score_components={
            "rs_score": _decimal_str(pair.rs_score),
            "oi_score": _decimal_str(pair.oi_score),
            "liquidity_score": _decimal_str(pair.liquidity_score),
            "data_quality_pct": _decimal_str(dq),
        },
        final_score=None,
        final_rank=pair.rank,
        eligible_candidate_count=len(observation.eligible_pairs),
        target_final_pairs=observation.target_final_pairs,
        selected=pair.selected,
        published=pair.selected and observation.gate_allowed and observation.published,
        final_reason_codes=_final_reason_codes(pair, observation),
    )


def build_run_records(
    observation: PairlistRunObservation,
    *,
    completed_at: str | None = None,
) -> tuple[ExplainabilityRunManifest, tuple[CandidateExplanationRecord, ...]]:
    """Build the manifest and one record per ranked pair for a run.

    Pure: no I/O.  ``completed_at`` defaults to the current UTC time; tests
    inject a fixed value for determinism.
    """
    completed_at = completed_at or _utc_now_iso()
    run_id = build_run_id(observation)
    records = tuple(
        build_candidate_record(pair, observation, run_id=run_id, completed_at=completed_at)
        for pair in observation.ranked_pairs
    )
    selected_count = sum(1 for p in observation.ranked_pairs if p.selected)
    manifest = ExplainabilityRunManifest(
        schema_version=EXPLAINABILITY_SCHEMA_VERSION,
        run_id=run_id,
        completed_at=completed_at,
        as_of_date=observation.as_of_date,
        ranking_profile=observation.ranking_profile,
        universe_total=observation.universe_total,
        eligible_count=len(observation.eligible_pairs),
        selected_count=selected_count,
        target_final_pairs=observation.target_final_pairs,
        min_pairs=observation.min_pairs,
        max_pairs=observation.max_pairs,
        gate_allowed=observation.gate_allowed,
        gate_reason_codes=tuple(observation.gate_reason_codes),
        published=observation.published,
        eligible_pairs=tuple(sorted(observation.eligible_pairs)),
    )
    return manifest, records
