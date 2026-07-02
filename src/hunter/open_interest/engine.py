"""Pure open-interest calculation functions for hunter.open_interest.

MVP-25 — Open Interest Engine.

All functions are pure computations over already-loaded in-memory values. No file
I/O, network access, database access, or external resource access is performed.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from hunter.open_interest.models import (
    BLOCKED_BY_SAFETY_FLAGS,
    FORBIDDEN_OPEN_INTEREST_TERMS,
    FUNDING_CONTEXT_MISSING,
    HUMAN_RESEARCH_ONLY,
    INPUTS_ALREADY_LOADED,
    INSUFFICIENT_OI_DATA,
    INVALID_OPEN_INTEREST,
    INVALID_PAIR,
    INVALID_PRICE_DATA,
    INVALID_TIMESTAMP,
    NO_ACTION_COMMANDS_EMITTED,
    NO_DATABASE_CONNECTION,
    NO_FILE_READ_IN_ENGINE,
    NO_NETWORK_CONNECTION,
    PERIOD_DATA_MISSING,
    UNSAFE_OPEN_INTEREST_CONTENT,
    ZERO_DENOMINATOR,
    OpenInterestConfig,
    OpenInterestDataQuality,
    OpenInterestFundingContext,
    OpenInterestInput,
    OpenInterestObservation,
    OpenInterestPeriodChange,
    OpenInterestPositioning,
    OpenInterestReport,
    OpenInterestSafetyFlags,
    OpenInterestScore,
    OpenInterestState,
    OpenInterestTrend,
    OpenInterestUniverseSummary,
    _coerce_mapping,
)


# ---------------------------------------------------------------------------
# Constants and simple helpers.
# ---------------------------------------------------------------------------


_STATE_PRIORITY = {
    OpenInterestState.READY: 0,
    OpenInterestState.INSUFFICIENT_DATA: 1,
    OpenInterestState.BLOCKED: 2,
}


_POSITIONING_SCORES: dict[OpenInterestPositioning, float] = {
    OpenInterestPositioning.PRICE_UP_OI_UP: 80.0,
    OpenInterestPositioning.PRICE_DOWN_OI_DOWN: 80.0,
    OpenInterestPositioning.PRICE_UP_OI_DOWN: 60.0,
    OpenInterestPositioning.PRICE_DOWN_OI_UP: 60.0,
    OpenInterestPositioning.MIXED: 40.0,
    OpenInterestPositioning.INSUFFICIENT_DATA: 0.0,
    OpenInterestPositioning.BLOCKED: 0.0,
}


_TREND_SCORES: dict[OpenInterestTrend, float] = {
    OpenInterestTrend.EXPANDING: 80.0,
    OpenInterestTrend.CONTRACTING: 80.0,
    OpenInterestTrend.FLAT: 50.0,
    OpenInterestTrend.UNSTABLE: 30.0,
    OpenInterestTrend.INSUFFICIENT_DATA: 0.0,
    OpenInterestTrend.BLOCKED: 0.0,
}


_FUNDING_SCORES: dict[OpenInterestFundingContext, float] = {
    OpenInterestFundingContext.POSITIVE: 75.0,
    OpenInterestFundingContext.NEGATIVE: 75.0,
    OpenInterestFundingContext.NEUTRAL: 50.0,
    OpenInterestFundingContext.MISSING: 50.0,
    OpenInterestFundingContext.INSUFFICIENT_DATA: 0.0,
    OpenInterestFundingContext.BLOCKED: 0.0,
}


def _round_value(value: float | None, decimals: int) -> float | None:
    """Round a float to the specified decimal places, preserving None."""
    if value is None:
        return None
    return round(value, decimals)


def _sorted_rows(
    rows: Sequence[OpenInterestObservation],
) -> tuple[OpenInterestObservation, ...]:
    """Return a new tuple sorted by timestamp ascending, never mutating caller."""
    return tuple(sorted(rows, key=lambda row: row.timestamp))


def _latest_funding_rate(
    rows: Sequence[OpenInterestObservation],
) -> float | None:
    """Return the funding_rate from the latest row in sorted order."""
    if not rows:
        return None
    sorted_rows = _sorted_rows(rows)
    return sorted_rows[-1].funding_rate


# ---------------------------------------------------------------------------
# Safety and config helpers.
# ---------------------------------------------------------------------------


def build_open_interest_safety_flags() -> OpenInterestSafetyFlags:
    """Return the default fail-closed safety flags."""
    return OpenInterestSafetyFlags()


def has_unsafe_open_interest_content(value: Any) -> bool:
    """Return True if value contains forbidden trading/execution content.

    Only inspects opaque local strings and mappings. Performs no file or network
    access.
    """
    if value is None:
        return False

    if isinstance(value, str):
        lowered = value.lower()
        return any(term in lowered for term in FORBIDDEN_OPEN_INTEREST_TERMS)

    if isinstance(value, OpenInterestInput):
        if has_unsafe_open_interest_content(value.pair):
            return True
        for row in value.rows:
            if has_unsafe_open_interest_content(row):
                return True
        if has_unsafe_open_interest_content(value.metadata):
            return True
        return False

    if isinstance(value, OpenInterestObservation):
        if has_unsafe_open_interest_content(value.metadata):
            return True
        return False

    if isinstance(value, Mapping):
        for key, mapping_value in value.items():
            if has_unsafe_open_interest_content(key):
                return True
            if has_unsafe_open_interest_content(mapping_value):
                return True
        return False

    return False


# ---------------------------------------------------------------------------
# Calculation helpers.
# ---------------------------------------------------------------------------


def calculate_period_change(current: float, previous: float) -> float | None:
    """Compute fractional change: (current - previous) / previous.

    Returns None if previous is zero (emits ZERO_DENOMINATOR). Result rounded to
    8 decimal places.
    """
    if previous == 0:
        return None
    return _round_value((current - previous) / previous, 8)


def calculate_oi_change(
    rows: Sequence[OpenInterestObservation], period: int
) -> float | None:
    """Compute OI change over the last `period` rows.

    Returns None if fewer than `period + 1` rows are available.
    """
    if period <= 0:
        return None
    sorted_rows = _sorted_rows(rows)
    if len(sorted_rows) < period + 1:
        return None
    current = sorted_rows[-1].open_interest
    previous = sorted_rows[-(period + 1)].open_interest
    return calculate_period_change(current, previous)


def calculate_price_change(
    rows: Sequence[OpenInterestObservation], period: int
) -> float | None:
    """Compute price change over the last `period` rows.

    Returns None if fewer than `period + 1` rows are available.
    """
    if period <= 0:
        return None
    sorted_rows = _sorted_rows(rows)
    if len(sorted_rows) < period + 1:
        return None
    current = sorted_rows[-1].close
    previous = sorted_rows[-(period + 1)].close
    return calculate_period_change(current, previous)


def classify_oi_price_positioning(
    oi_change: float | None,
    price_change: float | None,
    threshold: float,
) -> OpenInterestPositioning:
    """Classify combined price/OI positioning.

    Uses the 7-period (or longest available) window. Returns INSUFFICIENT_DATA
    if either change is None.
    """
    if oi_change is None or price_change is None:
        return OpenInterestPositioning.INSUFFICIENT_DATA

    price_up = price_change > threshold
    price_down = price_change < -threshold
    oi_up = oi_change > threshold
    oi_down = oi_change < -threshold

    if price_up and oi_up:
        return OpenInterestPositioning.PRICE_UP_OI_UP
    if price_up and oi_down:
        return OpenInterestPositioning.PRICE_UP_OI_DOWN
    if price_down and oi_up:
        return OpenInterestPositioning.PRICE_DOWN_OI_UP
    if price_down and oi_down:
        return OpenInterestPositioning.PRICE_DOWN_OI_DOWN
    return OpenInterestPositioning.MIXED


def calculate_oi_trend(
    changes: Sequence[float | None],
    threshold: float,
) -> OpenInterestTrend:
    """Classify OI trend across available windows.

    - EXPANDING: majority (>50%) of available windows have oi_change > threshold
    - CONTRACTING: majority (>50%) of available windows have oi_change < -threshold
    - FLAT: all available windows are within [-threshold, threshold]
    - UNSTABLE: mixed signs beyond threshold (not majority in any direction, not all flat)
    - INSUFFICIENT_DATA: fewer than 2 available windows
    """
    available = [c for c in changes if c is not None]
    if len(available) < 2:
        return OpenInterestTrend.INSUFFICIENT_DATA

    up_count = sum(1 for c in available if c > threshold)
    down_count = sum(1 for c in available if c < -threshold)
    flat_count = sum(1 for c in available if -threshold <= c <= threshold)
    total = len(available)

    if up_count > total / 2:
        return OpenInterestTrend.EXPANDING
    if down_count > total / 2:
        return OpenInterestTrend.CONTRACTING
    if flat_count == total:
        return OpenInterestTrend.FLAT
    return OpenInterestTrend.UNSTABLE


def classify_funding_context(
    funding_rate: float | None,
    bounds: tuple[float, float],
) -> OpenInterestFundingContext:
    """Classify funding-like context from the latest observation's funding_rate."""
    if funding_rate is None:
        return OpenInterestFundingContext.MISSING

    lower_bound, upper_bound = bounds
    upper_third = upper_bound / 3
    lower_third = lower_bound / 3

    if funding_rate > upper_third:
        return OpenInterestFundingContext.POSITIVE
    if funding_rate < lower_third:
        return OpenInterestFundingContext.NEGATIVE
    return OpenInterestFundingContext.NEUTRAL


def normalized_score(
    value: float | None, lower_bound: float, upper_bound: float
) -> float:
    """Linearly clamp a value to [0, 100]."""
    if value is None:
        return 0.0
    if value <= lower_bound:
        return 0.0
    if value >= upper_bound:
        return 100.0
    return ((value - lower_bound) / (upper_bound - lower_bound)) * 100.0


# ---------------------------------------------------------------------------
# Score / report builders.
# ---------------------------------------------------------------------------


def _apply_weights(
    sub_scores: Mapping[str, float], weights: Mapping[str, float]
) -> float:
    """Apply weighted sum with proportional redistribution for missing scores."""
    available = {
        key: value
        for key, value in sub_scores.items()
        if key in weights and value is not None
    }
    missing_weight = sum(
        weight for key, weight in weights.items() if key not in available
    )
    available_weight = sum(
        weight for key, weight in weights.items() if key in available
    )

    if available_weight == 0:
        return 0.0

    total = 0.0
    for key, value in available.items():
        adjusted_weight = weights[key] + missing_weight * (weights[key] / available_weight)
        total += value * adjusted_weight
    return total


def _build_data_quality(
    input: OpenInterestInput,
    config: OpenInterestConfig,
    reason_codes: tuple[str, ...],
) -> OpenInterestDataQuality:
    """Build a data quality record for a pair."""
    expected_rows = config.min_required_rows
    actual_rows = len(input.rows)
    missing_rows = max(0, expected_rows - actual_rows)
    return OpenInterestDataQuality(
        expected_rows=expected_rows,
        actual_rows=actual_rows,
        missing_rows=missing_rows,
        min_required_rows_met=actual_rows >= expected_rows,
        stale_input_count=0,
        reason_codes=reason_codes,
    )


def _build_period_changes(
    input: OpenInterestInput,
    config: OpenInterestConfig,
) -> tuple[tuple[OpenInterestPeriodChange, ...], tuple[str, ...]]:
    """Compute period changes and accumulate reason codes."""
    sorted_rows = _sorted_rows(input.rows)
    period_changes = []
    reason_codes = []

    for period in config.lookback_periods:
        oi_change = calculate_oi_change(sorted_rows, period)
        price_change = calculate_price_change(sorted_rows, period)
        has_data = oi_change is not None and price_change is not None
        period_reason_codes = []
        if oi_change is None or price_change is None:
            period_reason_codes.append(PERIOD_DATA_MISSING)
            reason_codes.append(PERIOD_DATA_MISSING)

        period_changes.append(
            OpenInterestPeriodChange(
                period=period,
                oi_change=oi_change,
                price_change=price_change,
                has_data=has_data,
                reason_codes=tuple(period_reason_codes),
            )
        )

    return tuple(period_changes), tuple(reason_codes)


def _score_for_positioning(positioning: OpenInterestPositioning) -> float:
    """Return the price_oi_alignment sub-score for a positioning classification."""
    return _POSITIONING_SCORES[positioning]


def _score_for_trend(trend: OpenInterestTrend) -> float:
    """Return the oi_trend_stability sub-score for a trend classification."""
    return _TREND_SCORES[trend]


def _score_for_funding(funding: OpenInterestFundingContext) -> float:
    """Return the funding_context sub-score for a funding classification."""
    return _FUNDING_SCORES[funding]


def _positioning_window_period(
    period_changes: tuple[OpenInterestPeriodChange, ...],
    config: OpenInterestConfig,
) -> OpenInterestPeriodChange | None:
    """Select the 7-period change if available, else the longest available."""
    by_period = {pc.period: pc for pc in period_changes}
    if 7 in by_period and by_period[7].has_data:
        return by_period[7]
    # Longest available period with data
    longest = None
    for pc in period_changes:
        if pc.has_data and (longest is None or pc.period > longest.period):
            longest = pc
    return longest


def _build_sub_scores(
    period_changes: tuple[OpenInterestPeriodChange, ...],
    positioning: OpenInterestPositioning,
    trend: OpenInterestTrend,
    funding_context: OpenInterestFundingContext,
    data_quality: OpenInterestDataQuality,
    config: OpenInterestConfig,
) -> Mapping[str, float]:
    """Build sub-scores from raw components and classifications."""
    sub_scores: dict[str, float] = {}

    # 7d OI change
    oi_7d = next(
        (pc.oi_change for pc in period_changes if pc.period == 7),
        None,
    )
    if oi_7d is not None:
        sub_scores["oi_7d_change"] = round(
            normalized_score(oi_7d, *config.oi_change_bounds),
            4,
        )

    # 14d OI change
    oi_14d = next(
        (pc.oi_change for pc in period_changes if pc.period == 14),
        None,
    )
    if oi_14d is not None:
        sub_scores["oi_14d_change"] = round(
            normalized_score(oi_14d, *config.oi_change_bounds),
            4,
        )

    # Alignment, trend, funding context
    sub_scores["price_oi_alignment"] = round(_score_for_positioning(positioning), 4)
    sub_scores["oi_trend_stability"] = round(_score_for_trend(trend), 4)
    sub_scores["funding_context"] = round(_score_for_funding(funding_context), 4)

    # Data quality
    quality_score = (data_quality.actual_rows / max(data_quality.expected_rows, 1)) * 100.0
    sub_scores["data_quality"] = round(max(0.0, min(100.0, quality_score)), 4)

    return sub_scores


def _build_human_note(
    pair: str,
    state: OpenInterestState,
    positioning: OpenInterestPositioning,
    trend: OpenInterestTrend,
    total_score: float,
    data_quality: OpenInterestDataQuality,
) -> str:
    """Build a deterministic human-readable note for a score."""
    if state == OpenInterestState.READY:
        return (
            f"{pair} shows {trend.value} OI with {positioning.value} positioning; "
            f"total research score {total_score:.2f}."
        )
    if state == OpenInterestState.INSUFFICIENT_DATA:
        return (
            f"{pair} has insufficient data ({data_quality.actual_rows} rows provided, "
            f"{data_quality.expected_rows} required)."
        )
    # BLOCKED
    if data_quality.actual_rows < data_quality.expected_rows:
        return (
            f"{pair} is blocked due to insufficient data "
            f"({data_quality.actual_rows} rows provided, {data_quality.expected_rows} required)."
        )
    return f"{pair} is blocked due to unsafe or invalid input."


def _state_from_reason_codes(
    blocking_reasons: tuple[str, ...],
    insufficient_reasons: tuple[str, ...],
    config: OpenInterestConfig,
) -> OpenInterestState:
    """Determine state from reason codes and config.

    Only INSUFFICIENT_OI_DATA (overall row count below min_required_rows) changes
    state to INSUFFICIENT_DATA. PERIOD_DATA_MISSING and FUNDING_CONTEXT_MISSING are
    informational reason codes that may appear in READY scores.
    """
    if blocking_reasons:
        return OpenInterestState.BLOCKED
    if INSUFFICIENT_OI_DATA in insufficient_reasons:
        if config.block_on_missing_data:
            return OpenInterestState.BLOCKED
        return OpenInterestState.INSUFFICIENT_DATA
    return OpenInterestState.READY


def build_open_interest_score(
    input: OpenInterestInput,
    config: OpenInterestConfig,
) -> OpenInterestScore:
    """Build a single OpenInterestScore."""
    pair = input.pair
    sorted_rows = _sorted_rows(input.rows)

    # Validate input and collect reason codes.
    blocking_reasons: list[str] = []

    # Unsafe content check.
    if has_unsafe_open_interest_content(input):
        blocking_reasons.append(UNSAFE_OPEN_INTEREST_CONTENT)

    # Pair validation.
    if not pair:
        blocking_reasons.append(INVALID_PAIR)

    # Observation validation.
    for row in sorted_rows:
        if row.timestamp.tzinfo is None:
            blocking_reasons.append(INVALID_TIMESTAMP)
            break

    # Build period changes regardless of state so they can be reported.
    period_changes, period_reason_codes = _build_period_changes(input, config)

    insufficient_reasons: list[str] = list(period_reason_codes)

    if len(sorted_rows) < config.min_required_rows:
        insufficient_reasons.append(INSUFFICIENT_OI_DATA)

    # Determine state.
    state = _state_from_reason_codes(
        tuple(blocking_reasons), tuple(insufficient_reasons), config
    )

    # Classifications depend on state.
    if state == OpenInterestState.BLOCKED:
        positioning = OpenInterestPositioning.BLOCKED
        trend = OpenInterestTrend.BLOCKED
        funding_context = OpenInterestFundingContext.BLOCKED
    elif state == OpenInterestState.INSUFFICIENT_DATA:
        positioning = OpenInterestPositioning.INSUFFICIENT_DATA
        trend = OpenInterestTrend.INSUFFICIENT_DATA
        funding_context = OpenInterestFundingContext.INSUFFICIENT_DATA
    else:
        # READY: compute classifications
        positioning_window = _positioning_window_period(period_changes, config)
        if positioning_window is None:
            positioning = OpenInterestPositioning.INSUFFICIENT_DATA
        else:
            positioning = classify_oi_price_positioning(
                positioning_window.oi_change,
                positioning_window.price_change,
                config.positioning_threshold,
            )

        trend = calculate_oi_trend(
            [pc.oi_change for pc in period_changes],
            config.positioning_threshold,
        )

        latest_funding = _latest_funding_rate(sorted_rows)
        funding_context = classify_funding_context(
            latest_funding, config.funding_rate_bounds
        )
        if funding_context == OpenInterestFundingContext.MISSING:
            insufficient_reasons.append(FUNDING_CONTEXT_MISSING)

    # Data quality.
    data_quality = _build_data_quality(
        input, config, tuple(dict.fromkeys(blocking_reasons + insufficient_reasons).keys())
    )

    # Latest values.
    if state == OpenInterestState.BLOCKED:
        latest_oi = None
        latest_price = None
        latest_funding_rate = None
    else:
        latest_row = sorted_rows[-1] if sorted_rows else None
        latest_oi = latest_row.open_interest if latest_row else None
        latest_price = latest_row.close if latest_row else None
        latest_funding_rate = latest_row.funding_rate if latest_row else None

    # Sub-scores and total score.
    if state == OpenInterestState.READY:
        sub_scores = _build_sub_scores(
            period_changes, positioning, trend, funding_context, data_quality, config
        )
        total_score = round(_apply_weights(sub_scores, config.score_weights), 2)
        total_score = max(0.0, min(100.0, total_score))
    else:
        sub_scores = {}
        total_score = 0.0

    # Final reason codes: deduplicate preserving order.
    final_reason_codes = tuple(dict.fromkeys(blocking_reasons + insufficient_reasons).keys())

    human_note = _build_human_note(
        pair, state, positioning, trend, total_score, data_quality
    )

    metadata = _coerce_mapping(input.metadata)

    return OpenInterestScore(
        pair=pair,
        state=state,
        positioning=positioning,
        trend=trend,
        funding_context=funding_context,
        total_score=total_score,
        period_changes=period_changes,
        latest_oi=latest_oi,
        latest_price=latest_price,
        latest_funding_rate=latest_funding_rate,
        sub_scores=sub_scores,
        data_quality=data_quality,
        human_note=human_note,
        reason_codes=final_reason_codes,
        metadata=metadata,
    )


def build_open_interest_universe_summary(
    scores: Sequence[OpenInterestScore],
    config: OpenInterestConfig,
) -> OpenInterestUniverseSummary:
    """Aggregate scores into a universe summary."""
    total_pairs = len(scores)
    ready_count = 0
    insufficient_data_count = 0
    blocked_count = 0
    expanding_count = 0
    contracting_count = 0
    flat_count = 0
    unstable_count = 0
    price_up_oi_up_count = 0
    price_up_oi_down_count = 0
    price_down_oi_up_count = 0
    price_down_oi_down_count = 0
    mixed_count = 0

    ready_scores = []
    for score in scores:
        if score.state == OpenInterestState.READY:
            ready_count += 1
            ready_scores.append(score)
        elif score.state == OpenInterestState.INSUFFICIENT_DATA:
            insufficient_data_count += 1
        elif score.state == OpenInterestState.BLOCKED:
            blocked_count += 1

        if score.trend == OpenInterestTrend.EXPANDING:
            expanding_count += 1
        elif score.trend == OpenInterestTrend.CONTRACTING:
            contracting_count += 1
        elif score.trend == OpenInterestTrend.FLAT:
            flat_count += 1
        elif score.trend == OpenInterestTrend.UNSTABLE:
            unstable_count += 1

        if score.positioning == OpenInterestPositioning.PRICE_UP_OI_UP:
            price_up_oi_up_count += 1
        elif score.positioning == OpenInterestPositioning.PRICE_UP_OI_DOWN:
            price_up_oi_down_count += 1
        elif score.positioning == OpenInterestPositioning.PRICE_DOWN_OI_UP:
            price_down_oi_up_count += 1
        elif score.positioning == OpenInterestPositioning.PRICE_DOWN_OI_DOWN:
            price_down_oi_down_count += 1
        elif score.positioning == OpenInterestPositioning.MIXED:
            mixed_count += 1

    if ready_scores:
        average_total_score = round(
            sum(score.total_score for score in ready_scores) / len(ready_scores), 2
        )
    else:
        average_total_score = None

    # Top expanding/contracting by deterministic sort: score desc, pair asc.
    expanding_scores = sorted(
        [s for s in scores if s.trend == OpenInterestTrend.EXPANDING],
        key=lambda s: (-s.total_score, s.pair),
    )
    contracting_scores = sorted(
        [s for s in scores if s.trend == OpenInterestTrend.CONTRACTING],
        key=lambda s: (-s.total_score, s.pair),
    )
    top_expanding_pair = expanding_scores[0].pair if expanding_scores else None
    top_contracting_pair = contracting_scores[0].pair if contracting_scores else None

    # Worst data quality (highest missing rows).
    worst_data_quality = None
    for score in scores:
        if worst_data_quality is None or score.data_quality.missing_rows > worst_data_quality.missing_rows:
            worst_data_quality = score.data_quality
    if worst_data_quality is None:
        worst_data_quality = OpenInterestDataQuality(
            expected_rows=config.min_required_rows,
            actual_rows=0,
            missing_rows=config.min_required_rows,
            min_required_rows_met=False,
            stale_input_count=0,
            reason_codes=(),
        )

    summary_narrative = (
        f"Universe of {total_pairs} pairs: {ready_count} ready, "
        f"{insufficient_data_count} insufficient data, {blocked_count} blocked. "
        f"Average total score (READY only): "
        f"{average_total_score:.2f}."
        if average_total_score is not None
        else "N/A."
    )
    # Ensure narrative is always a string even when average is None.
    if average_total_score is None:
        summary_narrative = (
            f"Universe of {total_pairs} pairs: {ready_count} ready, "
            f"{insufficient_data_count} insufficient data, {blocked_count} blocked. "
            "Average total score (READY only): N/A."
        )

    reason_codes = tuple(dict.fromkeys(
        [code for score in scores for code in score.reason_codes]
    ).keys())

    return OpenInterestUniverseSummary(
        total_pairs=total_pairs,
        ready_count=ready_count,
        insufficient_data_count=insufficient_data_count,
        blocked_count=blocked_count,
        expanding_count=expanding_count,
        contracting_count=contracting_count,
        flat_count=flat_count,
        unstable_count=unstable_count,
        price_up_oi_up_count=price_up_oi_up_count,
        price_up_oi_down_count=price_up_oi_down_count,
        price_down_oi_up_count=price_down_oi_up_count,
        price_down_oi_down_count=price_down_oi_down_count,
        mixed_count=mixed_count,
        average_total_score=average_total_score,
        top_expanding_pair=top_expanding_pair,
        top_contracting_pair=top_contracting_pair,
        data_quality=worst_data_quality,
        summary_narrative=summary_narrative,
        reason_codes=reason_codes,
    )


def build_open_interest_report(
    *,
    universe: Sequence[OpenInterestInput],
    config: OpenInterestConfig | None = None,
    report_id: str = "latest-open-interest",
    generated_at: datetime | None = None,
    metadata: Mapping[str, str] | None = None,
) -> OpenInterestReport:
    """Build a full deterministic open interest report."""
    config = config or OpenInterestConfig()
    metadata = metadata or {}
    generated_at = generated_at or datetime.now(timezone.utc)

    report_reason_codes: list[str] = []

    # Top-level config validation.
    if not isinstance(config, OpenInterestConfig):
        return OpenInterestReport.blocked(
            reason_code=BLOCKED_BY_SAFETY_FLAGS,
            report_id=report_id,
            generated_at=generated_at,
            metadata=metadata,
        )

    # Build scores. Unsafe content per pair is handled by build_open_interest_score,
    # which produces a BLOCKED score for that pair without blocking the whole report.
    scores = [build_open_interest_score(item, config) for item in universe]

    # Sort deterministically: state priority asc, total score desc, pair asc.
    sorted_scores = sorted(
        scores,
        key=lambda s: (_STATE_PRIORITY[s.state], -s.total_score, s.pair),
    )
    sorted_scores = tuple(sorted_scores)

    universe_summary = build_open_interest_universe_summary(sorted_scores, config)

    # Advisory reason codes.
    report_reason_codes.extend([
        INPUTS_ALREADY_LOADED,
        NO_ACTION_COMMANDS_EMITTED,
        HUMAN_RESEARCH_ONLY,
        NO_NETWORK_CONNECTION,
        NO_DATABASE_CONNECTION,
        NO_FILE_READ_IN_ENGINE,
    ])
    # Include any score-level reason codes (deduplicated).
    report_reason_codes.extend(
        code for score in sorted_scores for code in score.reason_codes
    )
    report_reason_codes = tuple(dict.fromkeys(report_reason_codes).keys())

    return OpenInterestReport(
        report_id=report_id,
        kind="open_interest_report",
        version="0.25.0-dev",
        source_spec="SPEC-026",
        generated_at=generated_at,
        config=config,
        safety_flags=build_open_interest_safety_flags(),
        scores=sorted_scores,
        universe_summary=universe_summary,
        reason_codes=report_reason_codes,
        metadata=metadata,
    )
