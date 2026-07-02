"""Pure relative-strength calculation functions for hunter.relative_strength.

MVP-24 — Relative Strength Engine.

All functions are pure computations over already-loaded in-memory values. No file
I/O, network access, database access, or external resource access is performed.
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from decimal import Decimal
from statistics import mean
from typing import Any

from hunter.relative_strength.models import (
    BENCHMARKS_PROVIDED_BY_CALLER,
    ETH_BENCHMARK_MISSING,
    FORBIDDEN_RELATIVE_STRENGTH_TERMS,
    HUMAN_RESEARCH_ONLY,
    INPUTS_ALREADY_LOADED,
    INSUFFICIENT_COIN_DATA,
    INVALID_CONFIG,
    INVALID_INPUT_DATA,
    MISSING_BTC_BENCHMARK,
    MIN_ROWS_NOT_MET,
    NO_ACTION_COMMANDS_EMITTED,
    NO_DATABASE_CONNECTION,
    NO_FILE_READ_IN_ENGINE,
    NO_NETWORK_CONNECTION,
    PERIOD_DATA_MISSING,
    RELATIVE_STRENGTH_REASON_CODES,
    UNSAFE_INPUT_CONTENT,
    RelativeStrengthBenchmarkKind,
    RelativeStrengthConfig,
    RelativeStrengthDataQuality,
    RelativeStrengthDecision,
    RelativeStrengthInput,
    RelativeStrengthPeriodReturn,
    RelativeStrengthRatioTrend,
    RelativeStrengthReport,
    RelativeStrengthSafetyFlags,
    RelativeStrengthScore,
    RelativeStrengthState,
    RelativeStrengthUniverseSummary,
)


# ---------------------------------------------------------------------------
# Constants and simple helpers.
# ---------------------------------------------------------------------------

_HEAD_ROWS = 5


def _round_value(value: float | None, decimals: int) -> float | None:
    """Round a float to the specified decimal places, preserving None."""
    if value is None:
        return None
    return round(value, decimals)


def _to_float(value: float | Decimal | None) -> float | None:
    """Convert Decimal or float to float, preserving None."""
    if value is None:
        return None
    return float(value)


def _sorted_rows(rows: Sequence[Any]) -> tuple[Any, ...]:
    """Return a new tuple sorted by timestamp, ascending."""
    return tuple(sorted(rows, key=lambda row: row.timestamp))


# ---------------------------------------------------------------------------
# Safety and config helpers.
# ---------------------------------------------------------------------------

def build_relative_strength_safety_flags() -> RelativeStrengthSafetyFlags:
    """Return the default fail-closed safety flags."""
    return RelativeStrengthSafetyFlags()


def has_unsafe_relative_strength_content(
    value: RelativeStrengthInput | str | Mapping[str, Any] | None,
) -> bool:
    """Return True if value contains forbidden trading/execution content.

    Only inspects opaque local strings and mappings. Performs no file or network
    access.
    """
    if value is None:
        return False

    if isinstance(value, str):
        lowered = value.lower()
        return any(term in lowered for term in FORBIDDEN_RELATIVE_STRENGTH_TERMS)

    if isinstance(value, RelativeStrengthInput):
        if has_unsafe_relative_strength_content(value.symbol):
            return True
        for row in value.rows:
            if has_unsafe_relative_strength_content(row.timestamp):
                return True
        return False

    if isinstance(value, Mapping):
        for key, mapping_value in value.items():
            if has_unsafe_relative_strength_content(key):
                return True
            if has_unsafe_relative_strength_content(mapping_value):
                return True
        return False

    return False


# ---------------------------------------------------------------------------
# Calculation helpers.
# ---------------------------------------------------------------------------

def calculate_period_return(
    rows: Sequence[Any], lookback: int
) -> float | None:
    """Compute period return for the given lookback.

    Returns None if data is insufficient or start close is zero/missing.
    """
    if lookback <= 0:
        return None
    sorted_rows = _sorted_rows(rows)
    if len(sorted_rows) < lookback + 1:
        return None
    start_close = _to_float(sorted_rows[-(lookback + 1)].close)
    end_close = _to_float(sorted_rows[-1].close)
    if start_close is None or start_close == 0 or end_close is None:
        return None
    return (end_close - start_close) / start_close


def calculate_relative_return(
    coin_return: float | None,
    btc_return: float | None,
    eth_return: float | None,
) -> tuple[float | None, float | None]:
    """Return coin-btc and coin-eth relative returns."""
    coin_minus_btc = None
    coin_minus_eth = None
    if coin_return is not None and btc_return is not None:
        coin_minus_btc = coin_return - btc_return
    if coin_return is not None and eth_return is not None:
        coin_minus_eth = coin_return - eth_return
    return coin_minus_btc, coin_minus_eth


def calculate_ratio_series(
    coin_rows: Sequence[Any], benchmark_rows: Sequence[Any]
) -> Sequence[float]:
    """Compute pointwise coin/benchmark ratios aligned by timestamp."""
    sorted_coin = _sorted_rows(coin_rows)
    sorted_benchmark = _sorted_rows(benchmark_rows)
    benchmark_by_timestamp = {}
    for row in sorted_benchmark:
        close = _to_float(row.close)
        if close is not None and close != 0:
            benchmark_by_timestamp[row.timestamp] = close

    ratios = []
    for row in sorted_coin:
        coin_close = _to_float(row.close)
        benchmark_close = benchmark_by_timestamp.get(row.timestamp)
        if coin_close is None or coin_close == 0 or benchmark_close is None:
            continue
        ratios.append(coin_close / benchmark_close)
    return tuple(ratios)


def calculate_moving_average(
    values: Sequence[float], window: int
) -> Sequence[float]:
    """Return simple moving average over values."""
    if window <= 0 or len(values) < window:
        return ()
    result = []
    for i in range(window - 1, len(values)):
        window_values = values[i - window + 1 : i + 1]
        result.append(mean(window_values))
    return tuple(result)


def calculate_slope(values: Sequence[float]) -> float:
    """Return OLS slope of values against index positions."""
    n = len(values)
    if n < 2:
        return 0.0
    x_mean = (n - 1) / 2.0
    y_mean = mean(values)
    numerator = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))
    denominator = sum((i - x_mean) ** 2 for i in range(n))
    if denominator == 0:
        return 0.0
    return numerator / denominator


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


def calculate_ratio_trend(
    ratio_series: Sequence[float],
    ma_window: int,
    lookback: int,
) -> RelativeStrengthRatioTrend:
    """Compute trend summary for a coin/BTC ratio series."""
    if len(ratio_series) < lookback or lookback <= 0:
        return RelativeStrengthRatioTrend(
            last_ratio=0.0,
            ma_ratio=0.0,
            slope=0.0,
            trend_score=0.0,
            lookback=lookback,
            has_data=False,
            reason_codes=(PERIOD_DATA_MISSING,),
        )

    recent = ratio_series[-lookback:]
    last_ratio = recent[-1]
    ma = calculate_moving_average(recent, ma_window)
    ma_ratio = ma[-1] if ma else last_ratio
    slope = calculate_slope(recent)
    trend_score = _round_value(normalized_score(slope, -0.05, 0.05), 4) or 0.0

    return RelativeStrengthRatioTrend(
        last_ratio=round(last_ratio, 8),
        ma_ratio=round(ma_ratio, 8),
        slope=round(slope, 8),
        trend_score=trend_score,
        lookback=lookback,
        has_data=True,
        reason_codes=(),
    )


def _extract_metric(
    score: RelativeStrengthScore, metric: str
) -> float | None:
    """Extract a named metric from a score's period returns."""
    match = re.fullmatch(r"([a-zA-Z_]+)_(\d+)d", metric)
    if not match:
        raise ValueError(f"invalid metric: {metric}")
    field_name = match.group(1)
    period_days = int(match.group(2))
    if field_name not in {
        "coin_return",
        "btc_return",
        "eth_return",
        "coin_minus_btc",
        "coin_minus_eth",
    }:
        raise ValueError(f"unsupported metric field: {field_name}")
    for period_return in score.period_returns:
        if period_return.period_days == period_days:
            return getattr(period_return, field_name)
    return None


def calculate_rank_percentiles(
    coins: Sequence[RelativeStrengthScore], metric: str
) -> Mapping[str, float | None]:
    """Compute percentile rank of each coin on the given metric."""
    ranked = []
    for score in coins:
        if score.state in {
            RelativeStrengthState.INSUFFICIENT_DATA,
            RelativeStrengthState.BLOCKED,
        }:
            continue
        value = _extract_metric(score, metric)
        if value is None:
            continue
        ranked.append((score.symbol, value))

    if not ranked:
        return {score.symbol: None for score in coins}

    # Sort by value descending, then symbol ascending for tie-breaking.
    sorted_ranked = sorted(ranked, key=lambda x: (-x[1], x[0]))
    n = len(sorted_ranked)
    result = {}

    # Average-rank tie handling: group identical values, assign average rank.
    i = 0
    while i < n:
        j = i
        while j < n and sorted_ranked[j][1] == sorted_ranked[i][1]:
            j += 1
        # Ranks are 1-indexed from top: i+1 to j.
        average_rank = (i + 1 + j) / 2.0
        percentile = (n - average_rank) / (n - 1) * 100.0 if n > 1 else 100.0
        percentile = round(percentile, 4)
        for k in range(i, j):
            result[sorted_ranked[k][0]] = percentile
        i = j

    # Symbols not ranked receive None.
    for score in coins:
        if score.symbol not in result:
            result[score.symbol] = None
    return result


# ---------------------------------------------------------------------------
# Score / report builders.
# ---------------------------------------------------------------------------

def _determine_base_benchmark(
    symbol: str, eth_present: bool
) -> RelativeStrengthBenchmarkKind:
    """Determine the base benchmark kind for a coin."""
    upper = symbol.upper()
    if upper == "BTC":
        return RelativeStrengthBenchmarkKind.ETH if eth_present else RelativeStrengthBenchmarkKind.NEUTRAL
    if upper == "ETH":
        return RelativeStrengthBenchmarkKind.BTC
    return RelativeStrengthBenchmarkKind.BTC


def _build_data_quality(
    input: RelativeStrengthInput,
    btc_rows: Sequence[Any],
    eth_rows: Sequence[Any] | None,
    config: RelativeStrengthConfig,
    missing_periods: tuple[str, ...],
    reason_codes: tuple[str, ...],
) -> RelativeStrengthDataQuality:
    """Build a data quality record for a coin."""
    expected_rows = config.min_required_rows
    actual_rows = len(input.rows)
    missing_rows = max(0, expected_rows - actual_rows)
    return RelativeStrengthDataQuality(
        expected_rows=expected_rows,
        actual_rows=actual_rows,
        missing_rows=missing_rows,
        missing_periods=missing_periods,
        min_required_rows_met=actual_rows >= expected_rows,
        btc_benchmark_rows=len(btc_rows),
        eth_benchmark_rows=len(eth_rows) if eth_rows is not None else None,
        stale_input_count=0,
        reason_codes=reason_codes,
    )


def _compute_period_returns(
    input: RelativeStrengthInput,
    btc_rows: Sequence[Any],
    eth_rows: Sequence[Any] | None,
    config: RelativeStrengthConfig,
) -> tuple[tuple[RelativeStrengthPeriodReturn, ...], tuple[str, ...], tuple[str, ...]]:
    """Compute period returns and accumulate reason codes."""
    period_returns = []
    reason_codes = []
    missing_periods = []

    for lookback in config.lookback_days:
        coin_return = calculate_period_return(input.rows, lookback)
        btc_return = calculate_period_return(btc_rows, lookback)
        eth_return = calculate_period_return(eth_rows, lookback) if eth_rows is not None else None

        coin_minus_btc, coin_minus_eth = calculate_relative_return(
            coin_return, btc_return, eth_return
        )

        has_data = coin_return is not None and btc_return is not None
        period_reason_codes = []
        if coin_return is None or btc_return is None:
            period_reason_codes.append(PERIOD_DATA_MISSING)
            missing_periods.append(f"{lookback}d")

        period_returns.append(
            RelativeStrengthPeriodReturn(
                period_days=lookback,
                coin_return=_round_value(coin_return, 8),
                btc_return=_round_value(btc_return, 8),
                eth_return=_round_value(eth_return, 8),
                coin_minus_btc=_round_value(coin_minus_btc, 8),
                coin_minus_eth=_round_value(coin_minus_eth, 8),
                has_data=has_data,
                reason_codes=tuple(period_reason_codes),
            )
        )
        reason_codes.extend(period_reason_codes)

    return tuple(period_returns), tuple(missing_periods), tuple(reason_codes)


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

    # Redistribute missing weight proportionally among available weights.
    total = 0.0
    for key, value in available.items():
        adjusted_weight = weights[key] + missing_weight * (weights[key] / available_weight)
        total += value * adjusted_weight
    return total


def _build_sub_scores(
    period_returns: tuple[RelativeStrengthPeriodReturn, ...],
    ratio_trend: RelativeStrengthRatioTrend,
    rank_percentile_30d: float | None,
) -> Mapping[str, float]:
    """Build sub-scores from raw components."""
    sub_scores = {}

    # Period returns.
    for period_return in period_returns:
        days = period_return.period_days
        if period_return.coin_minus_btc is not None:
            sub_scores[f"coin_minus_btc_{days}d"] = normalized_score(
                period_return.coin_minus_btc, -0.30, 0.30
            )
        if period_return.coin_minus_eth is not None:
            sub_scores[f"coin_minus_eth_{days}d"] = normalized_score(
                period_return.coin_minus_eth, -0.30, 0.30
            )

    # Ratio trend.
    sub_scores["ratio_trend"] = ratio_trend.trend_score

    # Rank percentile.
    if rank_percentile_30d is not None:
        sub_scores["rank_percentile_30d"] = rank_percentile_30d

    return {k: round(v, 4) for k, v in sub_scores.items()}


def _decision_for_score(
    score: RelativeStrengthScore, config: RelativeStrengthConfig
) -> RelativeStrengthDecision:
    """Derive decision from score state and thresholds."""
    if score.state == RelativeStrengthState.BLOCKED:
        return RelativeStrengthDecision.BLOCKED
    if score.state == RelativeStrengthState.INSUFFICIENT_DATA:
        return RelativeStrengthDecision.INSUFFICIENT_DATA

    # READY state.
    coin_minus_btc_values = [
        pr.coin_minus_btc
        for pr in score.period_returns
        if pr.coin_minus_btc is not None
    ]

    # BTC/ETH special cases.
    upper = score.symbol.upper()
    if upper == "BTC" and score.base_benchmark == RelativeStrengthBenchmarkKind.NEUTRAL:
        return RelativeStrengthDecision.NEUTRAL

    total_score = score.total_score
    if (
        total_score >= config.outperformer_threshold
        and len(coin_minus_btc_values) == 3
        and all(v > 0 for v in coin_minus_btc_values)
    ):
        return RelativeStrengthDecision.OUTPERFORMER
    if (
        total_score <= config.underperformer_threshold
        and len(coin_minus_btc_values) == 3
        and all(v < 0 for v in coin_minus_btc_values)
    ):
        return RelativeStrengthDecision.UNDERPERFORMER
    return RelativeStrengthDecision.NEUTRAL


def _build_human_note(
    symbol: str,
    decision: RelativeStrengthDecision,
    total_score: float,
    rank_percentile_30d: float | None,
    data_quality: RelativeStrengthDataQuality,
) -> str:
    """Build a human-readable note for a score."""
    if decision == RelativeStrengthDecision.INSUFFICIENT_DATA:
        return (
            f"{symbol} has insufficient data: {data_quality.actual_rows} rows available, "
            f"{data_quality.expected_rows} required."
        )
    if decision == RelativeStrengthDecision.BLOCKED:
        return f"{symbol} is blocked due to unsafe or invalid input."
    if decision == RelativeStrengthDecision.NEUTRAL:
        if symbol.upper() in {"BTC", "ETH"}:
            return f"{symbol} is the benchmark reference; neutral classification."
        return f"{symbol} has a total relative strength score of {total_score:.2f} and is neutral."
    percentile_note = ""
    if rank_percentile_30d is not None:
        percentile_note = f" Ranks in the {rank_percentile_30d:.2f} percentile of the provided universe."
    return (
        f"{symbol} is a {decision.value} with total relative strength score "
        f"{total_score:.2f}.{percentile_note}"
    )


def _build_relative_strength_score(
    input: RelativeStrengthInput,
    btc_rows: Sequence[Any],
    eth_rows: Sequence[Any] | None,
    config: RelativeStrengthConfig,
    rank_percentile_30d: float | None = None,
) -> RelativeStrengthScore:
    """Internal helper to build a score with optional percentile."""
    symbol = input.symbol
    eth_present = eth_rows is not None
    base_benchmark = _determine_base_benchmark(symbol, eth_present)

    # Check for unsafe content.
    if has_unsafe_relative_strength_content(input):
        return RelativeStrengthScore(
            symbol=symbol,
            base_benchmark=base_benchmark,
            state=RelativeStrengthState.BLOCKED,
            decision=RelativeStrengthDecision.BLOCKED,
            total_score=0.0,
            period_returns=(),
            ratio_trend=RelativeStrengthRatioTrend(
                last_ratio=0.0,
                ma_ratio=0.0,
                slope=0.0,
                trend_score=0.0,
                lookback=1,
                has_data=False,
                reason_codes=(UNSAFE_INPUT_CONTENT,),
            ),
            rank_percentile_30d=None,
            sub_scores={},
            data_quality=_build_data_quality(
                input, btc_rows, eth_rows, config, (), (UNSAFE_INPUT_CONTENT,)
            ),
            human_note=f"{symbol} is blocked due to unsafe input content.",
            reason_codes=(UNSAFE_INPUT_CONTENT,),
        )

    # Build period returns.
    period_returns, missing_periods, period_reason_codes = _compute_period_returns(
        input, btc_rows, eth_rows, config
    )

    # Ratio trend.
    ratio_series = calculate_ratio_series(input.rows, btc_rows)
    ratio_trend = calculate_ratio_trend(
        ratio_series, config.ratio_trend_ma_window, config.ratio_trend_lookback
    )

    # Data quality.
    all_reason_codes = list(period_reason_codes)
    if eth_rows is None:
        all_reason_codes.append(ETH_BENCHMARK_MISSING)
    data_quality = _build_data_quality(
        input, btc_rows, eth_rows, config, missing_periods, tuple(all_reason_codes)
    )

    # Determine state.
    has_blocking = False
    has_insufficient = False
    if not input.rows or not btc_rows:
        has_insufficient = True
        if not btc_rows:
            has_blocking = True
    if any(pr.coin_minus_btc is None for pr in period_returns):
        has_insufficient = True
    if data_quality.actual_rows < config.min_required_rows:
        has_insufficient = True
    if not ratio_trend.has_data:
        has_insufficient = True

    if has_blocking:
        state = RelativeStrengthState.BLOCKED
    elif has_insufficient:
        state = RelativeStrengthState.INSUFFICIENT_DATA
    else:
        state = RelativeStrengthState.READY

    if state == RelativeStrengthState.INSUFFICIENT_DATA and config.block_on_missing_data:
        state = RelativeStrengthState.BLOCKED

    # Sub-scores and total score.
    sub_scores = _build_sub_scores(period_returns, ratio_trend, rank_percentile_30d)
    total_score = round(_apply_weights(sub_scores, config.score_weights), 2)
    total_score = max(0.0, min(100.0, total_score))

    # Initial decision (will be recomputed in report if needed).
    initial_score = RelativeStrengthScore(
        symbol=symbol,
        base_benchmark=base_benchmark,
        state=state,
        decision=RelativeStrengthDecision.NEUTRAL,  # placeholder
        total_score=total_score,
        period_returns=period_returns,
        ratio_trend=ratio_trend,
        rank_percentile_30d=rank_percentile_30d,
        sub_scores=sub_scores,
        data_quality=data_quality,
        human_note="",
        reason_codes=tuple(all_reason_codes),
    )

    decision = _decision_for_score(initial_score, config)
    human_note = _build_human_note(
        symbol, decision, total_score, rank_percentile_30d, data_quality
    )

    return dataclasses.replace(
        initial_score,
        decision=decision,
        human_note=human_note,
    )


def build_relative_strength_score(
    input: RelativeStrengthInput,
    btc_rows: Sequence[Any],
    eth_rows: Sequence[Any] | None,
    config: RelativeStrengthConfig,
) -> RelativeStrengthScore:
    """Build a single RelativeStrengthScore.

    rank_percentile_30d is initially None and filled later by the report builder
    using dataclasses.replace(...).
    """
    return _build_relative_strength_score(input, btc_rows, eth_rows, config)


def build_relative_strength_universe_summary(
    scores: Sequence[RelativeStrengthScore],
    config: RelativeStrengthConfig,
) -> RelativeStrengthUniverseSummary:
    """Aggregate scores into a universe summary."""
    total_coins = len(scores)
    outperformer_count = 0
    neutral_count = 0
    underperformer_count = 0
    insufficient_data_count = 0
    blocked_count = 0

    ready_scores = []
    for score in scores:
        if score.decision == RelativeStrengthDecision.OUTPERFORMER:
            outperformer_count += 1
        elif score.decision == RelativeStrengthDecision.NEUTRAL:
            neutral_count += 1
        elif score.decision == RelativeStrengthDecision.UNDERPERFORMER:
            underperformer_count += 1
        elif score.decision == RelativeStrengthDecision.INSUFFICIENT_DATA:
            insufficient_data_count += 1
        elif score.decision == RelativeStrengthDecision.BLOCKED:
            blocked_count += 1
        if score.state == RelativeStrengthState.READY:
            ready_scores.append(score)

    average_total_score = 0.0
    if ready_scores:
        average_total_score = round(
            sum(score.total_score for score in ready_scores) / len(ready_scores), 2
        )

    # Top/bottom performers by deterministic sort: score desc, decision priority asc, symbol asc.
    decision_priority = {
        RelativeStrengthDecision.OUTPERFORMER: 0,
        RelativeStrengthDecision.NEUTRAL: 1,
        RelativeStrengthDecision.UNDERPERFORMER: 2,
        RelativeStrengthDecision.INSUFFICIENT_DATA: 3,
        RelativeStrengthDecision.BLOCKED: 4,
    }
    sorted_scores = sorted(
        scores,
        key=lambda s: (-s.total_score, decision_priority[s.decision], s.symbol),
    )
    top_outperformer = None
    top_underperformer = None
    for score in sorted_scores:
        if top_outperformer is None and score.decision == RelativeStrengthDecision.OUTPERFORMER:
            top_outperformer = score.symbol
        if top_underperformer is None and score.decision == RelativeStrengthDecision.UNDERPERFORMER:
            top_underperformer = score.symbol

    # Worst data quality (highest missing rows).
    worst_data_quality = None
    for score in scores:
        if worst_data_quality is None or score.data_quality.missing_rows > worst_data_quality.missing_rows:
            worst_data_quality = score.data_quality
    if worst_data_quality is None:
        worst_data_quality = RelativeStrengthDataQuality(
            expected_rows=0,
            actual_rows=0,
            missing_rows=0,
            missing_periods=(),
            min_required_rows_met=False,
            btc_benchmark_rows=0,
            eth_benchmark_rows=None,
            stale_input_count=0,
            reason_codes=(),
        )

    summary_narrative = (
        f"Universe of {total_coins} coins: {outperformer_count} outperformers, "
        f"{neutral_count} neutral, {underperformer_count} underperformers, "
        f"{insufficient_data_count} insufficient data, {blocked_count} blocked. "
        f"Average total score (READY only): {average_total_score:.2f}."
    )

    return RelativeStrengthUniverseSummary(
        total_coins=total_coins,
        outperformer_count=outperformer_count,
        neutral_count=neutral_count,
        underperformer_count=underperformer_count,
        insufficient_data_count=insufficient_data_count,
        blocked_count=blocked_count,
        top_outperformer=top_outperformer,
        top_underperformer=top_underperformer,
        average_total_score=average_total_score,
        data_quality=worst_data_quality,
        summary_narrative=summary_narrative,
    )


def build_relative_strength_report(
    *,
    universe: Sequence[RelativeStrengthInput],
    btc_benchmark: Sequence[Any],
    eth_benchmark: Sequence[Any] | None = None,
    config: RelativeStrengthConfig | None = None,
    report_id: str = "latest-relative-strength",
    generated_at: datetime | None = None,
    metadata: Mapping[str, str] | None = None,
) -> RelativeStrengthReport:
    """Build a full deterministic relative strength report."""
    config = config or RelativeStrengthConfig()
    metadata = metadata or {}
    generated_at = generated_at or datetime.now(timezone.utc)

    # Top-level validation / safety checks.
    report_reason_codes = []
    if not isinstance(config, RelativeStrengthConfig):
        return RelativeStrengthReport.blocked(
            report_id=report_id,
            config=RelativeStrengthConfig(),
            reason_codes=(INVALID_CONFIG,),
            generated_at=generated_at,
            metadata=metadata,
        )

    if not btc_benchmark:
        return RelativeStrengthReport.blocked(
            report_id=report_id,
            config=config,
            reason_codes=(MISSING_BTC_BENCHMARK,),
            generated_at=generated_at,
            metadata=metadata,
        )

    for item in universe:
        if has_unsafe_relative_strength_content(item):
            return RelativeStrengthReport.blocked(
                report_id=report_id,
                config=config,
                reason_codes=(UNSAFE_INPUT_CONTENT,),
                generated_at=generated_at,
                metadata=metadata,
            )

    if eth_benchmark is None and config.block_on_missing_eth:
        return RelativeStrengthReport.blocked(
            report_id=report_id,
            config=config,
            reason_codes=(ETH_BENCHMARK_MISSING,),
            generated_at=generated_at,
            metadata=metadata,
        )

    # Build initial scores without percentile.
    initial_scores = []
    for item in universe:
        score = build_relative_strength_score(item, btc_benchmark, eth_benchmark, config)
        initial_scores.append(score)

    # Calculate rank percentiles.
    percentiles = calculate_rank_percentiles(initial_scores, "coin_minus_btc_30d")

    # Build final scores with percentiles and recomputed total scores.
    final_scores = []
    for score in initial_scores:
        percentile = percentiles.get(score.symbol)
        if score.state == RelativeStrengthState.READY and percentile is not None:
            sub_scores = _build_sub_scores(
                score.period_returns, score.ratio_trend, percentile
            )
            total_score = round(_apply_weights(sub_scores, config.score_weights), 2)
            total_score = max(0.0, min(100.0, total_score))
            final_score = dataclasses.replace(
                score,
                rank_percentile_30d=percentile,
                sub_scores=sub_scores,
                total_score=total_score,
            )
            final_score = dataclasses.replace(
                final_score,
                decision=_decision_for_score(final_score, config),
                human_note=_build_human_note(
                    final_score.symbol,
                    _decision_for_score(final_score, config),
                    total_score,
                    percentile,
                    final_score.data_quality,
                ),
            )
            final_scores.append(final_score)
        else:
            final_scores.append(score)

    # Sort final scores deterministically.
    decision_priority = {
        RelativeStrengthDecision.OUTPERFORMER: 0,
        RelativeStrengthDecision.NEUTRAL: 1,
        RelativeStrengthDecision.UNDERPERFORMER: 2,
        RelativeStrengthDecision.INSUFFICIENT_DATA: 3,
        RelativeStrengthDecision.BLOCKED: 4,
    }
    final_scores = sorted(
        final_scores,
        key=lambda s: (-s.total_score, decision_priority[s.decision], s.symbol),
    )
    final_scores = tuple(final_scores)

    universe_summary = build_relative_strength_universe_summary(final_scores, config)

    # Series heads (first N rows only).
    btc_series_head = _sorted_rows(btc_benchmark)[:_HEAD_ROWS]
    eth_series_head = (
        _sorted_rows(eth_benchmark)[:_HEAD_ROWS]
        if eth_benchmark is not None
        else None
    )

    # Advisory reason codes.
    report_reason_codes.extend([
        INPUTS_ALREADY_LOADED,
        BENCHMARKS_PROVIDED_BY_CALLER,
        NO_ACTION_COMMANDS_EMITTED,
        HUMAN_RESEARCH_ONLY,
        NO_NETWORK_CONNECTION,
        NO_DATABASE_CONNECTION,
        NO_FILE_READ_IN_ENGINE,
    ])
    report_reason_codes = tuple(report_reason_codes)

    return RelativeStrengthReport(
        report_id=report_id,
        config=config,
        safety_flags=build_relative_strength_safety_flags(),
        scores=final_scores,
        universe_summary=universe_summary,
        btc_series_head=btc_series_head,
        eth_series_head=eth_series_head,
        generated_at=generated_at,
        reason_codes=report_reason_codes,
        metadata=metadata,
    )
