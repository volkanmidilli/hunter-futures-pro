"""Baseline volume universe builder (MVP-64 / SPEC-065 Stage 3)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from hunter.research_market_data.models import CandleSeries, ResearchMarketDataBundle
from hunter.research_universe.eligibility import assess_pair_eligibility
from hunter.research_universe.errors import ResearchUniverseConfigError
from hunter.research_universe.models import (
    EMPTY_BASELINE_UNIVERSE,
    INELIGIBLE_PAIR,
    BaselineUniverseResult,
    PairEligibilityResult,
    ResearchUniverseConfig,
    ResearchUniverseSafetyFlags,
    UniversePairDecision,
    UniversePairDecisionKind,
    UniversePairState,
)
from hunter.research_universe.fingerprint import baseline_universe_fingerprint


def _average_quote_volume(
    series: CandleSeries,
    window: Any,
) -> Decimal:
    """Compute average quote volume over candles inside the selection window."""
    total = Decimal("0")
    count = 0
    for candle in series.candles:
        if candle.timestamp < window.start or candle.timestamp > window.end:
            continue
        quote_volume = candle.quote_volume
        if quote_volume is None or quote_volume <= 0:
            quote_volume = candle.volume * candle.close
        total += quote_volume
        count += 1
    if count == 0:
        return Decimal("0")
    return total / Decimal(count)


def _classify_baseline(pair: str) -> str:
    """Baseline pairs are always classified as volume-ranked."""
    return "BASELINE_VOLUME"


def build_baseline_universe(
    bundle: ResearchMarketDataBundle,
    config: ResearchUniverseConfig,
) -> BaselineUniverseResult:
    """Build the baseline universe from the top-N volume pairs over the selection window.

    The baseline excludes benchmark pairs, stablecoins, leveraged tokens, and pairs
    that fail coverage/window requirements. It is research-only and deterministic.
    """
    if config.max_baseline_pairs < 1:
        raise ResearchUniverseConfigError(
            f"max_baseline_pairs must be >= 1, got {config.max_baseline_pairs}"
        )

    eligibility_map: dict[str, PairEligibilityResult] = {}
    volume_map: dict[str, Decimal] = {}

    for series in bundle.candidates:
        pair = series.pair
        if pair in eligibility_map:
            continue
        eligibility = assess_pair_eligibility(pair, series, config)
        eligibility_map[pair] = eligibility
        if eligibility.is_eligible:
            volume_map[pair] = _average_quote_volume(series, config.selection_window)

    ranked = sorted(volume_map.items(), key=lambda item: (-item[1], item[0]))
    selected = ranked[: config.max_baseline_pairs]

    decisions: list[UniversePairDecision] = []
    pairlist: dict[str, Any] = {}
    for rank, (pair, avg_volume) in enumerate(selected, start=1):
        decisions.append(
            UniversePairDecision(
                pair=pair,
                decision=UniversePairDecisionKind.INCLUDED,
                state=UniversePairState.BASELINE,
                classification=_classify_baseline(pair),
                rank=rank,
                estimated_quote_volume=avg_volume,
                source_fingerprint=eligibility_map[pair].source_fingerprint,
                reason_codes=(),
            )
        )
        pairlist[pair] = {
            "rank": rank,
            "estimated_quote_volume": str(avg_volume),
            "state": UniversePairState.BASELINE.value,
            "decision": UniversePairDecisionKind.INCLUDED.value,
        }

    for pair, eligibility in eligibility_map.items():
        if pair in volume_map:
            continue
        decisions.append(
            UniversePairDecision(
                pair=pair,
                decision=UniversePairDecisionKind.EXCLUDED,
                state=UniversePairState.EXCLUDED,
                classification=_classify_baseline(pair),
                rank=0,
                estimated_quote_volume=None,
                source_fingerprint=eligibility.source_fingerprint,
                reason_codes=eligibility.reason_codes
                if eligibility.reason_codes
                else (INELIGIBLE_PAIR,),
            )
        )
        pairlist[pair] = {
            "rank": 0,
            "estimated_quote_volume": None,
            "state": UniversePairState.EXCLUDED.value,
            "decision": UniversePairDecisionKind.EXCLUDED.value,
            "reason_codes": list(eligibility.reason_codes),
        }

    reason_codes: tuple[str, ...] = ()
    if not selected:
        reason_codes = (EMPTY_BASELINE_UNIVERSE,)

    safety_flags = ResearchUniverseSafetyFlags()
    fingerprint = baseline_universe_fingerprint(
        BaselineUniverseResult(
            decisions=tuple(decisions),
            pairlist=pairlist,
            fingerprint="PENDING",
            safety_flags=safety_flags,
            reason_codes=reason_codes,
        )
    )

    return BaselineUniverseResult(
        decisions=tuple(decisions),
        pairlist=pairlist,
        fingerprint=fingerprint,
        safety_flags=safety_flags,
        reason_codes=reason_codes,
    )
