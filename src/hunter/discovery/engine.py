from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from hunter.discovery.models import (
    ALIGNED_CONTEXT,
    DISCOVERY_VERSION,
    FORBIDDEN_DISCOVERY_TERMS,
    HUMAN_RESEARCH_ONLY,
    INVALID_DISCOVERY_SCORE,
    INVALID_PAIR,
    LOW_OPEN_INTEREST_SCORE,
    LOW_RELATIVE_STRENGTH_SCORE,
    MISALIGNED_CONTEXT,
    MISSING_OPEN_INTEREST_CONTEXT,
    MISSING_RELATIVE_STRENGTH_CONTEXT,
    MIXED_ALIGNMENT,
    NO_ACTION_COMMANDS_EMITTED,
    NO_FILE_READ_IN_ENGINE,
    NO_NETWORK_CONNECTION,
    OPEN_INTEREST_BLOCKED,
    OPEN_INTEREST_INSUFFICIENT_DATA,
    PASSED_DISCOVERY_FILTERS,
    RELATIVE_STRENGTH_BLOCKED,
    RELATIVE_STRENGTH_INSUFFICIENT_DATA,
    UNSAFE_DISCOVERY_CONTENT,
    DiscoveryCandidate,
    DiscoveryClassification,
    DiscoveryConfig,
    DiscoveryDataQuality,
    DiscoveryInput,
    DiscoveryOpenInterestSummary,
    DiscoveryRelativeStrengthSummary,
    DiscoveryReport,
    DiscoverySafetyFlags,
    DiscoveryScore,
    DiscoveryState,
    DiscoveryUniverseSummary,
    _coerce_mapping_strs,
)


_STATE_PRIORITY = {
    DiscoveryState.CANDIDATE: 0,
    DiscoveryState.WATCHLIST: 1,
    DiscoveryState.EXCLUDED: 2,
    DiscoveryState.INSUFFICIENT_DATA: 3,
    DiscoveryState.BLOCKED: 4,
}


_READY_LIKE_STATES = frozenset({"ready", "computed", "valid"})


_POSITIVE_DECISIONS = frozenset({"outperformer", "outperform", "strong", "leader", "bullish"})
_SUPPORTIVE_POSITIONINGS = frozenset(
    {
        "price_up_oi_up",
        "price_down_oi_down",
        "supportive",
        "accumulating",
        "positive",
        "rising",
    }
)
_SUPPORTIVE_TRENDS = frozenset(
    {
        "expanding",
        "rising",
        "strengthening",
        "up",
        "supportive",
        "positive",
    }
)
_NEGATIVE_DECISIONS = frozenset({"bearish", "weak", "laggard", "underperform", "underperformer"})
_NEGATIVE_POSITIONINGS = frozenset(
    {
        "price_up_oi_down",
        "price_down_oi_up",
        "negative",
        "weakening",
        "distributing",
    }
)
_NEGATIVE_TRENDS = frozenset({"contracting", "shrinking", "falling", "down", "weakening", "negative"})


def _round_value(value: float, decimals: int) -> float:
    return round(value, decimals)


def _state_str(value: str | None) -> str:
    return (value or "").strip().lower()


def _label_set(value: str | None) -> frozenset[str]:
    return frozenset((value or "").lower().replace("_", " ").split())


def _is_ready_like(state: str | None) -> bool:
    return _state_str(state) in _READY_LIKE_STATES


def _is_blocked_state(state: str | None) -> bool:
    return _state_str(state) == "blocked"


def _is_insufficient_state(state: str | None) -> bool:
    return _state_str(state) in {"insufficient", "insufficient_data"}


def _is_outperformer(decision: str | None) -> bool:
    return bool(_label_set(decision) & _POSITIVE_DECISIONS)


def _is_supportive_positioning(positioning: str | None) -> bool:
    return _state_str(positioning) in _SUPPORTIVE_POSITIONINGS


def _is_supportive_trend(trend: str | None) -> bool:
    return _state_str(trend) in _SUPPORTIVE_TRENDS


def _is_negative_positioning(positioning: str | None) -> bool:
    return _state_str(positioning) in _NEGATIVE_POSITIONINGS


def _is_negative_trend(trend: str | None) -> bool:
    return _state_str(trend) in _NEGATIVE_TRENDS


def _is_negative_decision(decision: str | None) -> bool:
    return bool(_label_set(decision) & _NEGATIVE_DECISIONS)


def _is_valid_score(value: float | None) -> bool:
    if value is None:
        return True
    return isinstance(value, (int, float)) and math.isfinite(value) and 0.0 <= value <= 100.0


def _is_per_candidate_safe(flags: DiscoverySafetyFlags) -> bool:
    """Return True if the candidate has no always-blocking safety issue.

    Missing required context is handled separately because it may either block
    or classify as INSUFFICIENT_DATA depending on config.block_on_missing_context.
    """
    return not any(
        [
            flags.has_unsafe_content,
            flags.has_invalid_pair,
            flags.has_invalid_score,
            flags.has_blocked_context,
            flags.has_inconsistent_state,
        ]
    )


def build_discovery_safety_flags(
    inputs: Sequence[DiscoveryInput],
    config: DiscoveryConfig,
) -> DiscoverySafetyFlags:
    """Return aggregate safety flags for the discovery run."""
    has_unsafe_content = False
    has_invalid_pair = False
    has_invalid_score = False
    has_blocked_context = False
    has_missing_required_context = False
    has_inconsistent_state = False

    for item in inputs:
        if not isinstance(item.pair, str) or not item.pair.strip():
            has_invalid_pair = True
        if has_unsafe_discovery_content(item.pair, item.tags, item.metadata):
            has_unsafe_content = True

        rs = item.relative_strength
        oi = item.open_interest

        if rs is not None:
            if rs.pair != item.pair:
                has_inconsistent_state = True
            if _is_blocked_state(rs.state):
                has_blocked_context = True
            if not _is_valid_score(rs.total_score):
                has_invalid_score = True

        if oi is not None:
            if oi.pair != item.pair:
                has_inconsistent_state = True
            if _is_blocked_state(oi.state):
                has_blocked_context = True
            if not _is_valid_score(oi.total_score):
                has_invalid_score = True

        if config.require_relative_strength and rs is None:
            has_missing_required_context = True
        if config.require_open_interest and oi is None:
            has_missing_required_context = True

    return DiscoverySafetyFlags(
        has_unsafe_content=has_unsafe_content,
        has_invalid_pair=has_invalid_pair,
        has_invalid_score=has_invalid_score,
        has_blocked_context=has_blocked_context,
        has_missing_required_context=has_missing_required_context,
        has_inconsistent_state=has_inconsistent_state,
        no_action_commands_emitted=True,
        no_network_connection=True,
        no_file_read_in_engine=True,
    )


def has_unsafe_discovery_content(
    pair: str,
    tags: Sequence[str],
    metadata: Mapping[str, str],
    forbidden_terms: frozenset[str] = FORBIDDEN_DISCOVERY_TERMS,
) -> bool:
    """Return True if any forbidden term appears in pair, tags, or metadata."""
    if not isinstance(pair, str) or not pair.strip():
        return True
    text = pair.lower()
    for tag in tags or ():
        text += " " + str(tag).lower()
    for key, value in (metadata or {}).items():
        text += " " + str(key).lower() + " " + str(value).lower()
    for term in forbidden_terms:
        if term in text:
            return True
    return False


def normalized_score(value: float | None) -> float:
    """Return a finite score in [0, 100] or 0.0 for None/invalid."""
    if value is None:
        return 0.0
    if not isinstance(value, (int, float)) or not math.isfinite(value):
        return 0.0
    if not 0.0 <= value <= 100.0:
        return 0.0
    return float(value)


def calculate_alignment_score(
    rs: DiscoveryRelativeStrengthSummary | None,
    oi: DiscoveryOpenInterestSummary | None,
) -> tuple[float, str]:
    """Return (alignment_score, reason_code) for the given contexts."""
    rs_blocked = rs is not None and _is_blocked_state(rs.state)
    oi_blocked = oi is not None and _is_blocked_state(oi.state)
    rs_insufficient = rs is not None and _is_insufficient_state(rs.state)
    oi_insufficient = oi is not None and _is_insufficient_state(oi.state)
    rs_missing = rs is None
    oi_missing = oi is None

    if rs_blocked or oi_blocked or rs_insufficient or oi_insufficient or rs_missing or oi_missing:
        return 0.0, MISALIGNED_CONTEXT

    rs_positive = _is_outperformer(rs.decision if rs is not None else None)
    rs_negative = _is_negative_decision(rs.decision if rs is not None else None)
    oi_positioning_supportive = _is_supportive_positioning(
        oi.positioning if oi is not None else None
    )
    oi_positioning_negative = _is_negative_positioning(
        oi.positioning if oi is not None else None
    )
    oi_trend_supportive = _is_supportive_trend(oi.trend if oi is not None else None)
    oi_trend_negative = _is_negative_trend(oi.trend if oi is not None else None)

    oi_supportive = oi_positioning_supportive or oi_trend_supportive
    oi_negative = oi_positioning_negative or oi_trend_negative
    oi_neutral = not oi_supportive and not oi_negative

    contradictory = (rs_positive and oi_negative) or (rs_negative and oi_supportive)
    if contradictory:
        return 0.0, MISALIGNED_CONTEXT

    if rs_positive and oi_supportive:
        return 100.0, ALIGNED_CONTEXT

    if (rs_positive and oi_neutral) or (oi_supportive and not rs_positive and not rs_negative):
        return 70.0, MIXED_ALIGNMENT

    return 40.0, MIXED_ALIGNMENT


def calculate_data_quality_score(
    rs: DiscoveryRelativeStrengthSummary | None,
    oi: DiscoveryOpenInterestSummary | None,
) -> float:
    """Return the data-quality sub-score for the given contexts."""
    rs_ready = rs is not None and _is_ready_like(rs.state)
    oi_ready = oi is not None and _is_ready_like(oi.state)
    rs_blocked = rs is not None and _is_blocked_state(rs.state)
    oi_blocked = oi is not None and _is_blocked_state(oi.state)
    rs_insufficient = rs is not None and _is_insufficient_state(rs.state)
    oi_insufficient = oi is not None and _is_insufficient_state(oi.state)
    rs_missing = rs is None
    oi_missing = oi is None

    if rs_blocked or oi_blocked:
        return 0.0
    if rs_missing and oi_missing:
        return 0.0
    if rs_ready and oi_ready:
        return 100.0
    if (rs_ready and oi_missing) or (rs_missing and oi_ready):
        return 60.0
    if (rs_ready and oi_insufficient) or (rs_insufficient and oi_ready):
        return 30.0
    return 0.0


def build_discovery_score(
    rs: DiscoveryRelativeStrengthSummary | None,
    oi: DiscoveryOpenInterestSummary | None,
    config: DiscoveryConfig,
) -> DiscoveryScore:
    """Return the composite discovery score for a single pair."""
    weights = dict(config.score_weights)
    reason_codes: list[str] = []

    rs_raw = normalized_score(rs.total_score if rs is not None else None)
    if rs is not None and _is_ready_like(rs.state):
        rs_score = _round_value(rs_raw, 4)
    else:
        rs_score = 0.0

    oi_raw = normalized_score(oi.total_score if oi is not None else None)
    if oi is not None and _is_ready_like(oi.state):
        oi_score = _round_value(oi_raw, 4)
    else:
        oi_score = 0.0

    alignment_score, alignment_reason = calculate_alignment_score(rs, oi)
    alignment_score = _round_value(alignment_score, 4)
    reason_codes.append(alignment_reason)

    data_quality_score = _round_value(calculate_data_quality_score(rs, oi), 4)

    rs_pass = rs_score >= config.min_relative_strength_score
    oi_pass = oi_score >= config.min_open_interest_score
    rs_blocked = rs is not None and _is_blocked_state(rs.state)
    oi_blocked = oi is not None and _is_blocked_state(oi.state)

    if rs_blocked or oi_blocked:
        filter_bonus_score = 0.0
    elif rs_pass and oi_pass:
        filter_bonus_score = 100.0
        reason_codes.append(PASSED_DISCOVERY_FILTERS)
    elif rs_pass or oi_pass:
        filter_bonus_score = 50.0
        if not rs_pass:
            reason_codes.append(LOW_RELATIVE_STRENGTH_SCORE)
        if not oi_pass:
            reason_codes.append(LOW_OPEN_INTEREST_SCORE)
    else:
        filter_bonus_score = 0.0
        reason_codes.append(LOW_RELATIVE_STRENGTH_SCORE)
        reason_codes.append(LOW_OPEN_INTEREST_SCORE)

    filter_bonus_score = _round_value(filter_bonus_score, 4)

    total_score = _round_value(
        rs_score * weights["relative_strength_score"]
        + oi_score * weights["open_interest_score"]
        + alignment_score * weights["alignment_score"]
        + data_quality_score * weights["data_quality_score"]
        + filter_bonus_score * weights["filter_bonus_score"],
        2,
    )

    total_score = max(0.0, min(100.0, total_score))

    return DiscoveryScore(
        relative_strength_score=rs_score,
        open_interest_score=oi_score,
        alignment_score=alignment_score,
        data_quality_score=data_quality_score,
        filter_bonus_score=filter_bonus_score,
        total_score=total_score,
        reason_codes=tuple(dict.fromkeys(reason_codes)),
    )


def classify_discovery_candidate(
    score: DiscoveryScore,
    config: DiscoveryConfig,
) -> tuple[DiscoveryState, DiscoveryClassification]:
    """Return (state, classification) for a scored candidate."""
    total_score = score.total_score

    if total_score >= config.strong_candidate_score:
        return DiscoveryState.CANDIDATE, DiscoveryClassification.STRONG_RESEARCH_CANDIDATE
    if total_score >= config.moderate_candidate_score:
        return DiscoveryState.CANDIDATE, DiscoveryClassification.MODERATE_RESEARCH_CANDIDATE
    if total_score >= config.watchlist_score:
        return DiscoveryState.WATCHLIST, DiscoveryClassification.WATCHLIST_ONLY

    return DiscoveryState.EXCLUDED, DiscoveryClassification.EXCLUDED_BY_FILTERS


def build_discovery_universe_summary(
    candidates: Sequence[DiscoveryCandidate],
) -> DiscoveryUniverseSummary:
    """Return summary counts for the given candidates."""
    total = len(candidates)
    candidate_count = sum(1 for c in candidates if c.state == DiscoveryState.CANDIDATE)
    watchlist_count = sum(1 for c in candidates if c.state == DiscoveryState.WATCHLIST)
    excluded_count = sum(1 for c in candidates if c.state == DiscoveryState.EXCLUDED)
    insufficient_data_count = sum(
        1 for c in candidates if c.state == DiscoveryState.INSUFFICIENT_DATA
    )
    blocked_count = sum(1 for c in candidates if c.state == DiscoveryState.BLOCKED)
    ready_context_count = sum(
        1
        for c in candidates
        if (
            c.relative_strength is not None and _is_ready_like(c.relative_strength.state)
        )
        or (
            c.open_interest is not None and _is_ready_like(c.open_interest.state)
        )
    )
    missing_context_count = sum(
        1
        for c in candidates
        if c.relative_strength is None and c.open_interest is None
    )
    blocked_context_count = sum(
        1
        for c in candidates
        if (
            c.relative_strength is not None and _is_blocked_state(c.relative_strength.state)
        )
        or (
            c.open_interest is not None and _is_blocked_state(c.open_interest.state)
        )
    )

    return DiscoveryUniverseSummary(
        total_inputs=total,
        candidate_count=candidate_count,
        watchlist_count=watchlist_count,
        excluded_count=excluded_count,
        insufficient_data_count=insufficient_data_count,
        blocked_count=blocked_count,
        ready_context_count=ready_context_count,
        missing_context_count=missing_context_count,
        blocked_context_count=blocked_context_count,
    )


def build_discovery_report(
    *,
    inputs: Sequence[DiscoveryInput],
    config: DiscoveryConfig | None = None,
    report_id: str = "latest-discovery",
    generated_at: datetime | None = None,
    metadata: Mapping[str, str] | None = None,
) -> DiscoveryReport:
    """Build a deterministic DiscoveryReport from already-loaded inputs."""
    config = config or DiscoveryConfig()
    generated_at = generated_at or datetime.now(timezone.utc)
    metadata = _coerce_mapping_strs(metadata)
    inputs = tuple(inputs)

    safety_flags = build_discovery_safety_flags(inputs, config)

    base_reason_codes: list[str] = [
        HUMAN_RESEARCH_ONLY,
        NO_NETWORK_CONNECTION,
        NO_FILE_READ_IN_ENGINE,
        NO_ACTION_COMMANDS_EMITTED,
    ]
    all_reason_codes: list[str] = list(base_reason_codes)
    candidates: list[DiscoveryCandidate] = []
    data_quality_reasons: list[str] = []
    pairs_with_both_contexts = 0
    pairs_with_missing_relative_strength = 0
    pairs_with_missing_open_interest = 0
    pairs_with_blocked_context = 0
    pairs_with_insufficient_context = 0

    for item in inputs:
        rs = item.relative_strength
        oi = item.open_interest

        rs_missing = rs is None
        oi_missing = oi is None
        rs_blocked = rs is not None and _is_blocked_state(rs.state)
        oi_blocked = oi is not None and _is_blocked_state(oi.state)
        rs_insufficient = rs is not None and _is_insufficient_state(rs.state)
        oi_insufficient = oi is not None and _is_insufficient_state(oi.state)
        rs_ready = rs is not None and _is_ready_like(rs.state)
        oi_ready = oi is not None and _is_ready_like(oi.state)

        if rs_ready and oi_ready:
            pairs_with_both_contexts += 1
        if rs_missing:
            pairs_with_missing_relative_strength += 1
        if oi_missing:
            pairs_with_missing_open_interest += 1
        if rs_blocked or oi_blocked:
            pairs_with_blocked_context += 1
        if rs_insufficient or oi_insufficient:
            pairs_with_insufficient_context += 1

        candidate_reasons = list(base_reason_codes)
        per_candidate_safety_flags = DiscoverySafetyFlags(
            has_unsafe_content=has_unsafe_discovery_content(
                item.pair, item.tags, item.metadata
            ),
            has_invalid_pair=not isinstance(item.pair, str) or not item.pair.strip(),
            has_invalid_score=(rs is not None and not _is_valid_score(rs.total_score))
            or (oi is not None and not _is_valid_score(oi.total_score)),
            has_blocked_context=rs_blocked or oi_blocked,
            has_missing_required_context=(
                (rs_missing and config.require_relative_strength)
                or (oi_missing and config.require_open_interest)
            ),
            has_inconsistent_state=(
                (rs is not None and rs.pair != item.pair)
                or (oi is not None and oi.pair != item.pair)
            ),
            no_action_commands_emitted=True,
            no_network_connection=True,
            no_file_read_in_engine=True,
        )

        if rs_blocked:
            candidate_reasons.append(RELATIVE_STRENGTH_BLOCKED)
        if oi_blocked:
            candidate_reasons.append(OPEN_INTEREST_BLOCKED)
        if rs_insufficient:
            candidate_reasons.append(RELATIVE_STRENGTH_INSUFFICIENT_DATA)
        if oi_insufficient:
            candidate_reasons.append(OPEN_INTEREST_INSUFFICIENT_DATA)
        if rs_missing and config.require_relative_strength:
            candidate_reasons.append(MISSING_RELATIVE_STRENGTH_CONTEXT)
        if oi_missing and config.require_open_interest:
            candidate_reasons.append(MISSING_OPEN_INTEREST_CONTEXT)

        if not _is_per_candidate_safe(per_candidate_safety_flags):
            if per_candidate_safety_flags.has_unsafe_content:
                candidate_reasons.append(UNSAFE_DISCOVERY_CONTENT)
            if per_candidate_safety_flags.has_invalid_pair:
                candidate_reasons.append(INVALID_PAIR)
            if per_candidate_safety_flags.has_invalid_score:
                candidate_reasons.append(INVALID_DISCOVERY_SCORE)
            if per_candidate_safety_flags.has_inconsistent_state:
                candidate_reasons.append(INVALID_PAIR)
            score = DiscoveryScore(
                relative_strength_score=0.0,
                open_interest_score=0.0,
                alignment_score=0.0,
                data_quality_score=0.0,
                filter_bonus_score=0.0,
                total_score=0.0,
                reason_codes=tuple(dict.fromkeys(candidate_reasons)),
            )
            state = DiscoveryState.BLOCKED
            classification = DiscoveryClassification.BLOCKED
        elif rs_blocked or oi_blocked:
            if config.block_on_blocked_context:
                score = DiscoveryScore(
                    relative_strength_score=0.0,
                    open_interest_score=0.0,
                    alignment_score=0.0,
                    data_quality_score=0.0,
                    filter_bonus_score=0.0,
                    total_score=0.0,
                    reason_codes=tuple(dict.fromkeys(candidate_reasons)),
                )
                state = DiscoveryState.BLOCKED
                classification = DiscoveryClassification.BLOCKED
            else:
                score = build_discovery_score(rs, oi, config)
                candidate_reasons.extend(score.reason_codes)
                state = DiscoveryState.INSUFFICIENT_DATA
                classification = DiscoveryClassification.INSUFFICIENT_DATA
                data_quality_reasons.extend(candidate_reasons)
        elif rs_insufficient or oi_insufficient:
            score = build_discovery_score(rs, oi, config)
            candidate_reasons.extend(score.reason_codes)
            state = DiscoveryState.INSUFFICIENT_DATA
            classification = DiscoveryClassification.INSUFFICIENT_DATA
            data_quality_reasons.extend(candidate_reasons)
        elif (rs_missing and config.require_relative_strength) or (
            oi_missing and config.require_open_interest
        ):
            if config.block_on_missing_context:
                score = DiscoveryScore(
                    relative_strength_score=0.0,
                    open_interest_score=0.0,
                    alignment_score=0.0,
                    data_quality_score=0.0,
                    filter_bonus_score=0.0,
                    total_score=0.0,
                    reason_codes=tuple(dict.fromkeys(candidate_reasons)),
                )
                state = DiscoveryState.BLOCKED
                classification = DiscoveryClassification.BLOCKED
            else:
                score = build_discovery_score(rs, oi, config)
                candidate_reasons.extend(score.reason_codes)
                state = DiscoveryState.INSUFFICIENT_DATA
                classification = DiscoveryClassification.INSUFFICIENT_DATA
                data_quality_reasons.extend(candidate_reasons)
        else:
            score = build_discovery_score(rs, oi, config)
            candidate_reasons.extend(score.reason_codes)
            state, classification = classify_discovery_candidate(score, config)

        candidate_reasons = list(dict.fromkeys(candidate_reasons))
        candidate = DiscoveryCandidate(
            pair=item.pair,
            state=state,
            classification=classification,
            score=score,
            relative_strength=rs,
            open_interest=oi,
            reason_codes=tuple(candidate_reasons),
            tags=item.tags,
            metadata=item.metadata,
        )
        candidates.append(candidate)
        all_reason_codes.extend(candidate_reasons)

    universe_summary = build_discovery_universe_summary(candidates)
    data_quality = DiscoveryDataQuality(
        total_inputs=len(inputs),
        pairs_with_both_contexts=pairs_with_both_contexts,
        pairs_with_missing_relative_strength=pairs_with_missing_relative_strength,
        pairs_with_missing_open_interest=pairs_with_missing_open_interest,
        pairs_with_blocked_context=pairs_with_blocked_context,
        pairs_with_insufficient_context=pairs_with_insufficient_context,
        reason_codes=tuple(dict.fromkeys(data_quality_reasons)),
    )

    if not config.include_excluded_candidates:
        candidates = [c for c in candidates if c.state != DiscoveryState.EXCLUDED]

    sorted_candidates = sorted(
        candidates,
        key=lambda c: (
            _STATE_PRIORITY[c.state],
            -c.score.total_score,
            c.pair,
        ),
    )

    all_reason_codes = list(dict.fromkeys(all_reason_codes))

    return DiscoveryReport(
        report_id=report_id,
        version=DISCOVERY_VERSION,
        generated_at=generated_at,
        config=config,
        inputs=tuple(inputs),
        candidates=tuple(sorted_candidates),
        universe_summary=universe_summary,
        data_quality=data_quality,
        safety_flags=safety_flags,
        reason_codes=tuple(all_reason_codes),
        metadata=metadata,
    )


