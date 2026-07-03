"""Pure portfolio construction engine functions.

MVP-27 — Portfolio Construction Engine.

All functions are deterministic and do not mutate inputs. They never open files,
validate paths, connect to network, access databases, or interact with exchanges.

Research weights are not orders, position sizes, trade sizes, or execution
readiness indicators. Output is human research only.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import datetime, timezone

from hunter.portfolio_construction.models import (
    CAPPED_BY_RESEARCH_CONSTRAINTS,
    DISCOVERY_BLOCKED,
    DISCOVERY_INSUFFICIENT_DATA,
    EXCLUDED_BY_RESEARCH_CONSTRAINTS,
    FORBIDDEN_PORTFOLIO_CONSTRUCTION_TERMS,
    HUMAN_RESEARCH_ONLY,
    INCLUDED_BY_RESEARCH_CONSTRAINTS,
    INVALID_DISCOVERY_SCORE,
    INVALID_PAIR,
    INVALID_RESEARCH_WEIGHT,
    LOW_DISCOVERY_SCORE,
    MAX_CANDIDATE_COUNT_EXCEEDED,
    MAX_SINGLE_WEIGHT_CAPPED,
    MISSING_DISCOVERY_CONTEXT,
    NO_ACTION_COMMANDS_EMITTED,
    NO_FILE_READ_IN_ENGINE,
    NO_NETWORK_CONNECTION,
    NOT_PORTFOLIO_APPROVAL,
    NOT_POSITION_SIZING,
    PORTFOLIO_CONSTRUCTION_REASON_CODES,
    PORTFOLIO_CONSTRUCTION_VERSION,
    UNSAFE_PORTFOLIO_CONSTRUCTION_CONTENT,
    ZERO_TOTAL_ALLOCATION_SCORE,
    PortfolioConstructionClassification,
    PortfolioConstructionConfig,
    PortfolioConstructionDataQuality,
    PortfolioConstructionInput,
    PortfolioConstructionReport,
    PortfolioConstructionSafetyFlags,
    PortfolioConstructionScore,
    PortfolioConstructionState,
    PortfolioConstructionUniverseSummary,
    PortfolioDiscoverySummary,
    _coerce_mapping_strs,
    _coerce_tuple_strs,
    _is_valid_score,
    _round_value,
)


_STATE_PRIORITY = {
    PortfolioConstructionState.INCLUDED: 0,
    PortfolioConstructionState.CAPPED: 1,
    PortfolioConstructionState.WATCHLIST: 2,
    PortfolioConstructionState.EXCLUDED: 3,
    PortfolioConstructionState.INSUFFICIENT_DATA: 4,
    PortfolioConstructionState.BLOCKED: 5,
}


_CANDIDATE_LIKE_CLASSIFICATIONS = frozenset(
    {
        "strong_research_candidate",
        "moderate_research_candidate",
    }
)

_WATCHLIST_LIKE_CLASSIFICATIONS = frozenset(
    {
        "watchlist_only",
    }
)


def _state_str(value: str | None) -> str:
    return (value or "").strip().lower()


def _is_candidate_like(discovery: PortfolioDiscoverySummary | None) -> bool:
    if discovery is None:
        return False
    if _state_str(discovery.state) == "candidate":
        return True
    if _state_str(discovery.classification) in _CANDIDATE_LIKE_CLASSIFICATIONS:
        return True
    return False


def _is_watchlist_like(discovery: PortfolioDiscoverySummary | None) -> bool:
    if discovery is None:
        return False
    if _state_str(discovery.state) == "watchlist":
        return True
    if _state_str(discovery.classification) in _WATCHLIST_LIKE_CLASSIFICATIONS:
        return True
    return False


def _is_blocked(discovery: PortfolioDiscoverySummary | None) -> bool:
    if discovery is None:
        return False
    return _state_str(discovery.state) == "blocked"


def _is_insufficient_data(discovery: PortfolioDiscoverySummary | None) -> bool:
    if discovery is None:
        return False
    return _state_str(discovery.state) in {"insufficient_data", "insufficient"}


def _has_invalid_pair(input_item: PortfolioConstructionInput) -> bool:
    return not isinstance(input_item.pair, str) or not input_item.pair.strip()


def _has_invalid_score(input_item: PortfolioConstructionInput) -> bool:
    if input_item.discovery is None:
        return False
    score = input_item.discovery.discovery_score
    if score is None:
        return False
    return not isinstance(score, (int, float)) or math.isinf(score) or math.isnan(score) or not 0.0 <= score <= 100.0


def build_portfolio_construction_safety_flags(
    inputs: Sequence[PortfolioConstructionInput],
    config: PortfolioConstructionConfig,
) -> PortfolioConstructionSafetyFlags:
    """Return aggregate safety flags for the portfolio construction run."""
    has_unsafe_content = False
    has_invalid_pair = False
    has_invalid_score = False
    has_blocked_context = False
    has_missing_required_context = False
    has_inconsistent_state = False

    for item in inputs:
        if _has_invalid_pair(item):
            has_invalid_pair = True
        if has_unsafe_portfolio_construction_content(item.pair, item.tags, item.metadata):
            has_unsafe_content = True
        if _has_invalid_score(item):
            has_invalid_score = True

        discovery = item.discovery
        if discovery is not None:
            if discovery.pair != item.pair:
                has_inconsistent_state = True
            if _is_blocked(discovery):
                has_blocked_context = True
        if config.require_discovery_context and discovery is None:
            has_missing_required_context = True

    return PortfolioConstructionSafetyFlags(
        has_unsafe_content=has_unsafe_content,
        has_invalid_pair=has_invalid_pair,
        has_invalid_score=has_invalid_score,
        has_blocked_context=has_blocked_context,
        has_missing_required_context=has_missing_required_context,
        has_inconsistent_state=has_inconsistent_state,
    )


def has_unsafe_portfolio_construction_content(
    pair: str,
    tags: Sequence[str],
    metadata: Mapping[str, str],
    forbidden_terms: frozenset[str] | None = None,
) -> bool:
    """Return True if any local string contains a forbidden term."""
    terms = forbidden_terms or FORBIDDEN_PORTFOLIO_CONSTRUCTION_TERMS
    text_parts = [pair.lower()]
    text_parts.extend(t.lower() for t in tags)
    for k, v in metadata.items():
        text_parts.append(k.lower())
        text_parts.append(v.lower())
    for part in text_parts:
        for term in terms:
            if term in part:
                return True
    return False


def normalized_score(value: float, min_value: float = 0.0, max_value: float = 100.0) -> float:
    """Normalize value to a 0-100 scale and clamp to bounds."""
    if max_value == min_value:
        if value >= max_value:
            return 100.0
        return 0.0
    normalized = (value - min_value) / (max_value - min_value) * 100.0
    return max(0.0, min(100.0, normalized))


def calculate_discovery_sub_score(
    discovery: PortfolioDiscoverySummary | None,
    config: PortfolioConstructionConfig,
) -> float:
    """Discovery score component from discovery context alone."""
    if discovery is None:
        return 0.0
    state = _state_str(discovery.state)
    if state in {"blocked", "excluded", "insufficient_data", "insufficient"}:
        return 0.0
    if _is_candidate_like(discovery) or _is_watchlist_like(discovery):
        score = discovery.discovery_score
        if score is None:
            return 0.0
        return _round_value(float(score), 4)
    return 0.0


def calculate_data_quality_score(
    discovery: PortfolioDiscoverySummary | None,
    config: PortfolioConstructionConfig,
) -> float:
    """Data quality sub-score from discovery state."""
    if discovery is None:
        return 0.0
    state = _state_str(discovery.state)
    if state == "candidate":
        return 100.0
    if state == "watchlist":
        return 70.0
    if state in {"insufficient_data", "insufficient"}:
        return 30.0
    return 0.0


def calculate_diversification_penalty(
    pair: str,
    tags: Sequence[str],
    all_inputs: Sequence[PortfolioConstructionInput],
    config: PortfolioConstructionConfig,
) -> float:
    """Return diversification component for the given pair.

    100.0 default; 50.0 if a duplicate tag group exists; 0.0 when
    block_duplicate_tags=True and a duplicate exists (blocking is handled
    separately by the report builder).
    """
    if not tags:
        return 100.0

    tag_owners: dict[str, list[str]] = {}
    for item in all_inputs:
        for tag in item.tags:
            tag_owners.setdefault(tag, []).append(item.pair)

    duplicates = False
    for tag in tags:
        owners = tag_owners.get(tag, [])
        if len(owners) >= 2:
            duplicates = True
            break

    if not duplicates:
        return 100.0
    if config.block_duplicate_tags:
        return 0.0
    return 50.0


def calculate_cap_readiness_score(
    input_item: PortfolioConstructionInput,
    config: PortfolioConstructionConfig,
) -> float:
    """Cap readiness score from discovery context and config only."""
    discovery = input_item.discovery
    if discovery is None:
        return 0.0
    state = _state_str(discovery.state)
    if state in {"blocked", "excluded", "insufficient_data", "insufficient"}:
        return 0.0
    if _is_candidate_like(discovery):
        return 100.0
    if _is_watchlist_like(discovery):
        return 50.0
    return 0.0


def calculate_filter_bonus_score(
    discovery: PortfolioDiscoverySummary | None,
    config: PortfolioConstructionConfig,
) -> float:
    """Filter bonus score from discovery thresholds."""
    if discovery is None:
        return 0.0
    state = _state_str(discovery.state)
    if state in {"blocked", "excluded", "insufficient_data", "insufficient"}:
        return 0.0
    score = discovery.discovery_score
    if score is None:
        return 0.0
    score_value = float(score)
    if _is_candidate_like(discovery):
        if score_value >= config.min_discovery_score:
            return 100.0
    if _is_watchlist_like(discovery):
        if score_value >= config.watchlist_score:
            return 50.0
    return 0.0


def calculate_allocation_score(
    input_item: PortfolioConstructionInput,
    all_inputs: Sequence[PortfolioConstructionInput],
    config: PortfolioConstructionConfig,
) -> float:
    """Single-pass allocation score from sub-scores."""
    discovery = input_item.discovery
    discovery_component = calculate_discovery_sub_score(discovery, config)
    data_quality = calculate_data_quality_score(discovery, config)
    diversification = calculate_diversification_penalty(
        input_item.pair, input_item.tags, all_inputs, config
    )
    cap_readiness = calculate_cap_readiness_score(input_item, config)
    filter_bonus = calculate_filter_bonus_score(discovery, config)

    weights = config.score_weights
    total = (
        discovery_component * weights["discovery_score_component"]
        + data_quality * weights["data_quality_score"]
        + diversification * weights["diversification_component"]
        + cap_readiness * weights["cap_readiness_score"]
        + filter_bonus * weights["filter_bonus_score"]
    )
    return _round_value(max(0.0, min(100.0, total)), 2)


def calculate_initial_research_weights(
    scores: Sequence[PortfolioConstructionScore],
    config: PortfolioConstructionConfig,
) -> Sequence[PortfolioConstructionScore]:
    """Compute initial research weights for the pool."""
    scores = tuple(scores)
    pool_scores = [
        s
        for s in scores
        if s.state not in {PortfolioConstructionState.BLOCKED, PortfolioConstructionState.INSUFFICIENT_DATA}
        and s.allocation_score >= config.satellite_allocation_score
    ]

    total_allocation = sum(s.allocation_score for s in pool_scores)

    weight_map: dict[str, float] = {}
    if total_allocation <= 0.0:
        for s in pool_scores:
            weight_map[s.pair] = 0.0
    else:
        for s in pool_scores:
            weight = s.allocation_score / total_allocation * config.total_research_weight_pct
            weight_map[s.pair] = _round_value(weight, 4)

    updated: list[PortfolioConstructionScore] = []
    for s in scores:
        if s.pair in weight_map:
            updated.append(replace(s, initial_research_weight_pct=weight_map[s.pair]))
        else:
            updated.append(replace(s, initial_research_weight_pct=0.0))
    return tuple(updated)


def apply_research_weight_caps(
    scores: Sequence[PortfolioConstructionScore],
    config: PortfolioConstructionConfig,
) -> Sequence[PortfolioConstructionScore]:
    """Apply max_single_weight_pct cap and redistribute excess deterministically."""
    scores = tuple(scores)
    cap = config.max_single_weight_pct

    # Pool members are those with positive initial weights.
    pool_pairs = {
        s.pair
        for s in scores
        if s.state not in {PortfolioConstructionState.BLOCKED, PortfolioConstructionState.INSUFFICIENT_DATA}
        and s.initial_research_weight_pct > 0.0
    }

    if not pool_pairs:
        return tuple(replace(s, capped_weight_pct=0.0, final_weight_pct=0.0) for s in scores)

    weights: dict[str, float] = {}
    allocation_scores: dict[str, float] = {}
    for s in scores:
        if s.pair in pool_pairs:
            weights[s.pair] = s.initial_research_weight_pct
            allocation_scores[s.pair] = s.allocation_score

    total_research_weight_pct = config.total_research_weight_pct

    for _ in range(len(pool_pairs) + 1):
        capped_now: list[str] = []
        excess = 0.0
        for pair in pool_pairs:
            if weights[pair] > cap + 1e-9:
                excess += weights[pair] - cap
                weights[pair] = cap
                capped_now.append(pair)
        if not capped_now:
            break
        recipients = [
            p
            for p in pool_pairs
            if weights[p] < cap - 1e-9 and allocation_scores[p] > 0.0
        ]
        if not recipients:
            break
        recipient_total = sum(allocation_scores[p] for p in recipients)
        if recipient_total <= 0.0:
            break
        for p in recipients:
            share = allocation_scores[p] / recipient_total * excess
            weights[p] = _round_value(weights[p] + share, 4)

    final_weights: dict[str, float] = {}
    for pair in pool_pairs:
        final_weights[pair] = _round_value(weights[pair], 4)

    total = sum(final_weights.values())
    if total > total_research_weight_pct + 1e-9:
        scale = total_research_weight_pct / total
        for pair in final_weights:
            final_weights[pair] = _round_value(final_weights[pair] * scale, 4)

    updated: list[PortfolioConstructionScore] = []
    for s in scores:
        if s.pair in final_weights:
            final = final_weights[s.pair]
            capped = _round_value(s.initial_research_weight_pct - final, 4)
            updated.append(
                replace(
                    s,
                    capped_weight_pct=max(0.0, capped),
                    final_weight_pct=final,
                )
            )
        else:
            updated.append(replace(s, capped_weight_pct=0.0, final_weight_pct=0.0))
    return tuple(updated)


def classify_portfolio_construction_candidate(
    allocation_score: float,
    final_weight_pct: float,
    was_capped: bool,
    config: PortfolioConstructionConfig,
) -> tuple[PortfolioConstructionState, PortfolioConstructionClassification]:
    """Return (state, classification) based on scores and final weight."""
    if allocation_score < config.watchlist_score:
        return (
            PortfolioConstructionState.EXCLUDED,
            PortfolioConstructionClassification.EXCLUDED_BY_CONSTRAINTS,
        )
    if allocation_score < config.satellite_allocation_score:
        return (
            PortfolioConstructionState.WATCHLIST,
            PortfolioConstructionClassification.WATCHLIST_ALLOCATION,
        )

    if allocation_score >= config.core_allocation_score:
        classification = PortfolioConstructionClassification.CORE_RESEARCH_ALLOCATION
    else:
        classification = PortfolioConstructionClassification.SATELLITE_RESEARCH_ALLOCATION

    if was_capped:
        return PortfolioConstructionState.CAPPED, classification
    return PortfolioConstructionState.INCLUDED, classification


def _duplicate_tag_pairs(
    inputs: Sequence[PortfolioConstructionInput],
) -> frozenset[str]:
    """Return pairs that share a tag with at least one other pair."""
    tag_owners: dict[str, list[str]] = {}
    for item in inputs:
        for tag in item.tags:
            tag_owners.setdefault(tag, []).append(item.pair)
    duplicates: set[str] = set()
    for owners in tag_owners.values():
        if len(owners) >= 2:
            duplicates.update(owners)
    return frozenset(duplicates)


def _determine_base_state_and_reasons(
    input_item: PortfolioConstructionInput,
    config: PortfolioConstructionConfig,
    safety_flags: PortfolioConstructionSafetyFlags,
    duplicate_pairs: frozenset[str],
) -> tuple[PortfolioConstructionState, PortfolioConstructionClassification, list[str]]:
    """Determine pre-weight state and reason codes for a single input."""
    reasons: list[str] = [
        HUMAN_RESEARCH_ONLY,
        NO_NETWORK_CONNECTION,
        NO_FILE_READ_IN_ENGINE,
        NO_ACTION_COMMANDS_EMITTED,
        NOT_PORTFOLIO_APPROVAL,
        NOT_POSITION_SIZING,
    ]

    if _has_invalid_pair(input_item):
        reasons.append(INVALID_PAIR)
        return PortfolioConstructionState.BLOCKED, PortfolioConstructionClassification.BLOCKED, reasons
    if safety_flags.has_unsafe_content and has_unsafe_portfolio_construction_content(
        input_item.pair, input_item.tags, input_item.metadata
    ):
        reasons.append(UNSAFE_PORTFOLIO_CONSTRUCTION_CONTENT)
        return PortfolioConstructionState.BLOCKED, PortfolioConstructionClassification.BLOCKED, reasons
    if _has_invalid_score(input_item):
        reasons.append(INVALID_DISCOVERY_SCORE)
        return PortfolioConstructionState.BLOCKED, PortfolioConstructionClassification.BLOCKED, reasons
    if safety_flags.has_inconsistent_state and input_item.discovery is not None and input_item.discovery.pair != input_item.pair:
        reasons.append(INVALID_PAIR)
        return PortfolioConstructionState.BLOCKED, PortfolioConstructionClassification.BLOCKED, reasons

    discovery = input_item.discovery
    if discovery is not None and _is_blocked(discovery):
        reasons.append(DISCOVERY_BLOCKED)
        if config.block_on_blocked_context:
            return PortfolioConstructionState.BLOCKED, PortfolioConstructionClassification.BLOCKED, reasons

    if discovery is None or _is_insufficient_data(discovery):
        if discovery is None:
            reasons.append(MISSING_DISCOVERY_CONTEXT)
        else:
            reasons.append(DISCOVERY_INSUFFICIENT_DATA)
        if config.block_on_missing_context:
            return PortfolioConstructionState.BLOCKED, PortfolioConstructionClassification.BLOCKED, reasons
        return (
            PortfolioConstructionState.INSUFFICIENT_DATA,
            PortfolioConstructionClassification.INSUFFICIENT_DATA,
            reasons,
        )

    if input_item.pair in duplicate_pairs and config.block_duplicate_tags:
        reasons.append(EXCLUDED_BY_RESEARCH_CONSTRAINTS)
        return PortfolioConstructionState.BLOCKED, PortfolioConstructionClassification.BLOCKED, reasons

    return (
        PortfolioConstructionState.EXCLUDED,
        PortfolioConstructionClassification.EXCLUDED_BY_CONSTRAINTS,
        reasons,
    )


def build_portfolio_construction_score(
    input_item: PortfolioConstructionInput,
    all_inputs: Sequence[PortfolioConstructionInput],
    config: PortfolioConstructionConfig,
) -> PortfolioConstructionScore:
    """Build a single portfolio construction score with sub-scores and allocation score."""
    safety_flags = build_portfolio_construction_safety_flags(all_inputs, config)
    duplicate_pairs = _duplicate_tag_pairs(all_inputs)

    state, classification, reasons = _determine_base_state_and_reasons(
        input_item, config, safety_flags, duplicate_pairs
    )

    discovery_component = calculate_discovery_sub_score(input_item.discovery, config)
    data_quality = calculate_data_quality_score(input_item.discovery, config)
    diversification = calculate_diversification_penalty(
        input_item.pair, input_item.tags, all_inputs, config
    )
    cap_readiness = calculate_cap_readiness_score(input_item, config)
    filter_bonus = calculate_filter_bonus_score(input_item.discovery, config)
    allocation_score = calculate_allocation_score(input_item, all_inputs, config)

    notes: list[str] = []
    if state == PortfolioConstructionState.BLOCKED:
        notes.append("Candidate blocked by safety or config rule.")
    elif state == PortfolioConstructionState.INSUFFICIENT_DATA:
        notes.append("Insufficient discovery context for research allocation.")

    return PortfolioConstructionScore(
        pair=input_item.pair,
        state=state,
        classification=classification,
        allocation_score=allocation_score,
        discovery_score_component=discovery_component,
        data_quality_score=data_quality,
        diversification_component=diversification,
        cap_readiness_score=cap_readiness,
        filter_bonus_score=filter_bonus,
        initial_research_weight_pct=0.0,
        capped_weight_pct=0.0,
        final_weight_pct=0.0,
        reason_codes=tuple(dict.fromkeys(reasons)),
        tags=input_item.tags,
        metadata=input_item.metadata,
        notes=tuple(notes),
        rank=None,
    )


def build_portfolio_construction_universe_summary(
    scores: Sequence[PortfolioConstructionScore],
    config: PortfolioConstructionConfig,
) -> PortfolioConstructionUniverseSummary:
    """Build universe summary from final scores."""
    scores = tuple(scores)
    total = len(scores)
    included = sum(1 for s in scores if s.state == PortfolioConstructionState.INCLUDED)
    capped = sum(1 for s in scores if s.state == PortfolioConstructionState.CAPPED)
    watchlist = sum(1 for s in scores if s.state == PortfolioConstructionState.WATCHLIST)
    excluded = sum(1 for s in scores if s.state == PortfolioConstructionState.EXCLUDED)
    insufficient = sum(1 for s in scores if s.state == PortfolioConstructionState.INSUFFICIENT_DATA)
    blocked = sum(1 for s in scores if s.state == PortfolioConstructionState.BLOCKED)
    core = sum(1 for s in scores if s.classification == PortfolioConstructionClassification.CORE_RESEARCH_ALLOCATION)
    satellite = sum(1 for s in scores if s.classification == PortfolioConstructionClassification.SATELLITE_RESEARCH_ALLOCATION)
    watchlist_alloc = sum(1 for s in scores if s.classification == PortfolioConstructionClassification.WATCHLIST_ALLOCATION)
    total_weight = _round_value(sum(s.final_weight_pct for s in scores), 4)

    top_pair = None
    sorted_for_top = sorted(
        scores,
        key=lambda s: (
            -s.final_weight_pct,
            -s.allocation_score,
            s.pair,
        ),
    )
    if sorted_for_top:
        top_pair = sorted_for_top[0].pair

    return PortfolioConstructionUniverseSummary(
        total_candidates=total,
        included_count=included,
        capped_count=capped,
        watchlist_count=watchlist,
        excluded_count=excluded,
        insufficient_data_count=insufficient,
        blocked_count=blocked,
        core_allocation_count=core,
        satellite_allocation_count=satellite,
        watchlist_allocation_count=watchlist_alloc,
        total_final_weight_pct=total_weight,
        top_pair=top_pair,
        notes=(),
    )


def build_portfolio_construction_report(
    *,
    inputs: Sequence[PortfolioConstructionInput],
    config: PortfolioConstructionConfig | None = None,
    report_id: str = "latest-portfolio-construction",
    generated_at: datetime | None = None,
    metadata: Mapping[str, str] | None = None,
) -> PortfolioConstructionReport:
    """Build a deterministic PortfolioConstructionReport from already-loaded inputs."""
    config = config or PortfolioConstructionConfig()
    generated_at = generated_at or datetime.now(timezone.utc)
    metadata = _coerce_mapping_strs(metadata)
    inputs = tuple(inputs)

    safety_flags = build_portfolio_construction_safety_flags(inputs, config)

    duplicate_pairs = _duplicate_tag_pairs(inputs)

    # Build base scores with pre-weight states.
    base_scores: list[PortfolioConstructionScore] = []
    for item in inputs:
        score = build_portfolio_construction_score(item, inputs, config)
        base_scores.append(score)

    # Sort non-blocked, non-insufficient by allocation_score desc, pair asc.
    sortable = [
        s
        for s in base_scores
        if s.state not in {PortfolioConstructionState.BLOCKED, PortfolioConstructionState.INSUFFICIENT_DATA}
    ]
    sortable.sort(key=lambda s: (-s.allocation_score, s.pair))

    # Apply max_candidate_count: excess become EXCLUDED.
    max_count = config.max_candidate_count
    included_in_pool: set[str] = set()
    for idx, s in enumerate(sortable, start=1):
        if idx <= max_count:
            included_in_pool.add(s.pair)
        else:
            # Mark as excluded by max_candidate_count.
            for base in base_scores:
                if base.pair == s.pair:
                    reasons = list(base.reason_codes) + [MAX_CANDIDATE_COUNT_EXCEEDED]
                    base_scores = [
                        replace(
                            b,
                            state=PortfolioConstructionState.EXCLUDED,
                            classification=PortfolioConstructionClassification.EXCLUDED_BY_CONSTRAINTS,
                            reason_codes=tuple(dict.fromkeys(reasons)),
                        )
                        if b.pair == s.pair
                        else b
                        for b in base_scores
                    ]
                    break

    # Calculate initial weights and apply caps.
    base_scores = list(calculate_initial_research_weights(base_scores, config))
    base_scores = list(apply_research_weight_caps(base_scores, config))

    # Final classification and reason codes.
    final_scores: list[PortfolioConstructionScore] = []
    for s in base_scores:
        if s.state in {PortfolioConstructionState.BLOCKED, PortfolioConstructionState.INSUFFICIENT_DATA}:
            final_scores.append(s)
            continue
        if s.state == PortfolioConstructionState.EXCLUDED and MAX_CANDIDATE_COUNT_EXCEEDED in s.reason_codes:
            final_scores.append(s)
            continue
        if s.allocation_score < config.satellite_allocation_score:
            # WATCHLIST or EXCLUDED by score.
            state, classification = classify_portfolio_construction_candidate(
                s.allocation_score, s.final_weight_pct, False, config
            )
            reasons = list(s.reason_codes)
            if state == PortfolioConstructionState.EXCLUDED:
                reasons.append(EXCLUDED_BY_RESEARCH_CONSTRAINTS)
            elif state == PortfolioConstructionState.WATCHLIST:
                reasons.append(EXCLUDED_BY_RESEARCH_CONSTRAINTS)
            final_scores.append(
                replace(
                    s,
                    state=state,
                    classification=classification,
                    reason_codes=tuple(dict.fromkeys(reasons)),
                )
            )
            continue

        was_capped = s.final_weight_pct < s.initial_research_weight_pct - 1e-9 or s.capped_weight_pct > 0.0
        state, classification = classify_portfolio_construction_candidate(
            s.allocation_score, s.final_weight_pct, was_capped, config
        )
        reasons = list(s.reason_codes)
        if was_capped:
            reasons.append(MAX_SINGLE_WEIGHT_CAPPED)
            reasons.append(CAPPED_BY_RESEARCH_CONSTRAINTS)
        else:
            reasons.append(INCLUDED_BY_RESEARCH_CONSTRAINTS)
        final_scores.append(
            replace(
                s,
                state=state,
                classification=classification,
                reason_codes=tuple(dict.fromkeys(reasons)),
            )
        )

    # Sort final scores by state priority, final_weight desc, allocation_score desc, pair asc.
    final_scores.sort(
        key=lambda s: (
            _STATE_PRIORITY[s.state],
            -s.final_weight_pct,
            -s.allocation_score,
            s.pair,
        )
    )

    universe_summary = build_portfolio_construction_universe_summary(final_scores, config)

    # Omit EXCLUDED if include_excluded_candidates=False.
    if not config.include_excluded_candidates:
        final_scores = [
            s for s in final_scores if s.state != PortfolioConstructionState.EXCLUDED
        ]

    # Assign ranks to visible scores.
    ranked: list[PortfolioConstructionScore] = []
    for idx, s in enumerate(final_scores, start=1):
        ranked.append(replace(s, rank=idx))
    final_scores = ranked

    # Build data quality.
    total_inputs = len(inputs)
    ready_context = 0
    missing_context = 0
    blocked_context = 0
    for item in inputs:
        d = item.discovery
        if d is None:
            missing_context += 1
        elif _is_blocked(d):
            blocked_context += 1
        elif _is_insufficient_data(d):
            missing_context += 1
        else:
            ready_context += 1

    total_final_weight = sum(s.final_weight_pct for s in final_scores)
    data_quality_score = _round_value(
        (ready_context / max(total_inputs, 1)) * 100.0, 4
    )
    total_weight_within_tolerance = 0.0 <= total_final_weight <= config.total_research_weight_pct + 1e-9

    all_reason_codes: list[str] = [
        HUMAN_RESEARCH_ONLY,
        NO_NETWORK_CONNECTION,
        NO_FILE_READ_IN_ENGINE,
        NO_ACTION_COMMANDS_EMITTED,
        NOT_PORTFOLIO_APPROVAL,
        NOT_POSITION_SIZING,
    ]
    for s in final_scores:
        all_reason_codes.extend(s.reason_codes)

    data_quality = PortfolioConstructionDataQuality(
        total_inputs=total_inputs,
        included_count=universe_summary.included_count,
        capped_count=universe_summary.capped_count,
        watchlist_count=universe_summary.watchlist_count,
        excluded_count=universe_summary.excluded_count,
        insufficient_data_count=universe_summary.insufficient_data_count,
        blocked_count=universe_summary.blocked_count,
        ready_context_count=ready_context,
        missing_context_count=missing_context,
        blocked_context_count=blocked_context,
        total_final_weight_pct=_round_value(total_final_weight, 4),
        total_research_weight_pct=config.total_research_weight_pct,
        data_quality_score=data_quality_score,
        sections_present=5,
        all_sections_present=True,
        all_counts_consistent=True,
        total_weight_within_tolerance=total_weight_within_tolerance,
        has_unsafe_content=False,
        safety_flags_ok=safety_flags.is_safe,
    )

    return PortfolioConstructionReport(
        version=PORTFOLIO_CONSTRUCTION_VERSION,
        report_id=report_id,
        generated_at=generated_at,
        inputs=inputs,
        config=config,
        safety_flags=safety_flags,
        scores=tuple(final_scores),
        universe_summary=universe_summary,
        data_quality=data_quality,
        reason_codes=tuple(dict.fromkeys(all_reason_codes)),
        metadata=metadata,
        notes=(
            "Research-only allocation weights. Not orders, not position sizes, not trade sizes.",
        ),
    )
