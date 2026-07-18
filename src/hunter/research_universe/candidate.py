"""Candidate universe orchestration (MVP-64 / SPEC-065 Stage 4)."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Any

from hunter.controlled_universe.models import (
    ControlledUniverseClassification,
    ControlledUniverseReport,
)
from hunter.portfolio_construction.models import (
    PortfolioConstructionReport,
    PortfolioConstructionScore,
)
from hunter.research_universe.errors import ResearchUniverseConfigError
from hunter.research_universe.models import (
    CANDIDATE_CLASSIFICATION_INCLUDED,
    EMPTY_CANDIDATE_UNIVERSE,
    UNKNOWN_DISCOVERY_CLASSIFICATION,
    CandidateUniverseResult,
    ResearchUniverseConfig,
    ResearchUniverseSafetyFlags,
    UniversePairClassification,
    UniversePairDecision,
    UniversePairDecisionKind,
    UniversePairState,
)
from hunter.research_universe.fingerprint import candidate_universe_fingerprint


_VALID_CANDIDATE_CLASSIFICATIONS: frozenset[str] = frozenset(
    {
        ControlledUniverseClassification.LONG_RESEARCH.value,
        ControlledUniverseClassification.SHORT_RESEARCH.value,
        ControlledUniverseClassification.NEUTRAL_RESEARCH.value,
    }
)


def _source_fingerprint(report: ControlledUniverseReport) -> str:
    """Deterministic fingerprint of the controlled universe source universe."""
    payload = {
        "universe": sorted(report.universe),
        "version": report.version,
    }
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _map_classification(
    item_classification: ControlledUniverseClassification,
) -> str:
    """Map controlled universe classification into universe-pair classification."""
    value = item_classification.value
    if value == ControlledUniverseClassification.LONG_RESEARCH.value:
        return UniversePairClassification.LONG_RESEARCH.value
    if value == ControlledUniverseClassification.SHORT_RESEARCH.value:
        return UniversePairClassification.SHORT_RESEARCH.value
    if value == ControlledUniverseClassification.NEUTRAL_RESEARCH.value:
        return UniversePairClassification.NEUTRAL_RESEARCH.value
    return value


def _score_lookup(
    portfolio_report: PortfolioConstructionReport | None,
) -> dict[str, PortfolioConstructionScore]:
    """Index portfolio construction scores by pair."""
    if portfolio_report is None:
        return {}
    return {score.pair: score for score in portfolio_report.scores}


def _rank_included(
    pairs: tuple[str, ...],
    score_lookup: dict[str, PortfolioConstructionScore],
) -> tuple[tuple[int, str, PortfolioConstructionScore | None], ...]:
    """Return ranked tuples (rank, pair, score_or_none) for included pairs.

    Ranking prefers portfolio final_weight_pct descending, then alphabetical.
    """
    ranked = sorted(
        pairs,
        key=lambda p: (
            -(score_lookup[p].final_weight_pct if p in score_lookup else 0.0),
            p,
        ),
    )
    return tuple((i, pair, score_lookup.get(pair)) for i, pair in enumerate(ranked, start=1))


def build_candidate_universe(
    controlled_report: ControlledUniverseReport,
    portfolio_report: PortfolioConstructionReport | None,
    config: ResearchUniverseConfig,
) -> CandidateUniverseResult:
    """Build the candidate universe from controlled universe and portfolio outputs.

    Candidate universe = controlled universe items that are in the included universe
    and have a long/short/neutral research classification. Portfolio construction scores
    provide rank and weight; if absent, candidates are ranked alphabetically.
    """
    if controlled_report is None:
        raise ResearchUniverseConfigError("controlled_report is required")

    source_fingerprint = _source_fingerprint(controlled_report)
    score_lookup = _score_lookup(portfolio_report)

    item_lookup = {item.pair: item for item in controlled_report.items}
    included: list[str] = []
    for pair in controlled_report.universe:
        item = item_lookup.get(pair)
        if item is None:
            continue
        if item.classification.value in _VALID_CANDIDATE_CLASSIFICATIONS:
            included.append(pair)

    ranked = _rank_included(tuple(included), score_lookup)

    decisions: list[UniversePairDecision] = []
    pairlist: dict[str, Any] = {}

    for rank, pair, score in ranked:
        item = item_lookup[pair]
        classification = _map_classification(item.classification)
        weight = Decimal(str(score.final_weight_pct)) if score is not None else None
        score_value = score.allocation_score if score is not None else 0.0
        decisions.append(
            UniversePairDecision(
                pair=pair,
                decision=UniversePairDecisionKind.INCLUDED,
                state=UniversePairState.CANDIDATE,
                classification=classification,
                rank=rank,
                score=score_value,
                estimated_quote_volume=None,
                source_fingerprint=source_fingerprint,
                reason_codes=(CANDIDATE_CLASSIFICATION_INCLUDED,),
            )
        )
        pairlist[pair] = {
            "rank": rank,
            "classification": classification,
            "score": score_value,
            "weight": str(weight) if weight is not None else None,
            "state": UniversePairState.CANDIDATE.value,
            "decision": UniversePairDecisionKind.INCLUDED.value,
        }

    # Excluded items: watchlist, blocked, or universe items with non-research classification.
    excluded_pairs = sorted(
        set(item.pair for item in controlled_report.items) - set(included)
    )
    for pair in excluded_pairs:
        item = item_lookup[pair]
        classification = _map_classification(item.classification)
        score = score_lookup.get(pair)
        weight = Decimal(str(score.final_weight_pct)) if score is not None else None
        score_value = score.allocation_score if score is not None else 0.0
        decisions.append(
            UniversePairDecision(
                pair=pair,
                decision=UniversePairDecisionKind.EXCLUDED,
                state=UniversePairState.EXCLUDED,
                classification=classification,
                rank=0,
                score=score_value,
                estimated_quote_volume=None,
                source_fingerprint=source_fingerprint,
                reason_codes=tuple(item.reason_codes)
                if item.reason_codes
                else (UNKNOWN_DISCOVERY_CLASSIFICATION,),
            )
        )
        pairlist[pair] = {
            "rank": 0,
            "classification": classification,
            "score": score_value,
            "weight": str(weight) if weight is not None else None,
            "state": UniversePairState.EXCLUDED.value,
            "decision": UniversePairDecisionKind.EXCLUDED.value,
            "reason_codes": list(item.reason_codes),
        }

    reason_codes: tuple[str, ...] = ()
    if not included:
        reason_codes = (EMPTY_CANDIDATE_UNIVERSE,)

    safety_flags = ResearchUniverseSafetyFlags()
    fingerprint = candidate_universe_fingerprint(
        CandidateUniverseResult(
            decisions=tuple(decisions),
            pairlist=pairlist,
            fingerprint="PENDING",
            safety_flags=safety_flags,
            reason_codes=reason_codes,
        )
    )

    return CandidateUniverseResult(
        decisions=tuple(decisions),
        pairlist=pairlist,
        fingerprint=fingerprint,
        safety_flags=safety_flags,
        reason_codes=reason_codes,
    )
