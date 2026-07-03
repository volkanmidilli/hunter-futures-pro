"""MVP-28 Local Research Backtesting Engine.

This engine performs a deterministic, in-memory simulation of research
allocation weights against historical price bars. It produces a human-readable
research-only report. It is not a trading signal, not trade approval, not
strategy approval, not execution approval, not portfolio approval, and not
Freqtrade input. No network, exchange, file, database, or runtime dependencies
are used.
"""

from __future__ import annotations

import math
import uuid
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from hunter.backtest.models import (
    BACKTEST_ADVISORY_REASON_CODES,
    BACKTEST_VERSION,
    INVALID_DATE,
    INVALID_PAIR,
    INVALID_PRICE,
    UNSAFE_BACKTEST_CONTENT,
    BacktestAllocationMode,
    BacktestCandidateDecision,
    BacktestCandidateResult,
    BacktestDataQuality,
    BacktestInput,
    BacktestInputKind,
    BacktestPortfolioResult,
    BacktestPortfolioSnapshot,
    BacktestReport,
    BacktestRunConfig,
    BacktestSafetyFlags,
    BacktestState,
    DISCOVERY_BLOCKED,
    EXCLUDED_BY_RESEARCH_CONSTRAINTS,
    HUMAN_RESEARCH_ONLY,
    INSUFFICIENT_PRICE_HISTORY,
    MIN_OBSERVATION_COUNT_NOT_MET,
    MISSING_DECISION_CONTEXT,
    MISSING_PRICE_HISTORY,
    NO_ACTION_COMMANDS_EMITTED,
    NO_FILE_READ_IN_ENGINE,
    NO_NETWORK_CONNECTION,
    NOT_EXECUTION_READY,
    NOT_TRADING_ADVICE,
    WATCHLIST_ZERO_WEIGHT,
    has_unsafe_backtest_content,
)


# Rounding policies
_RAW_DECIMALS = 8
_PERIOD_DECIMALS = 8
_SUB_METRIC_DECIMALS = 4
_PERCENTAGE_DECIMALS = 2


def _round(value: float, decimals: int) -> float:
    return round(value, decimals)


def _is_valid_finite(value: float) -> bool:
    return isinstance(value, (int, float)) and not (math.isinf(value) or math.isnan(value))


def _std_dev(values: Sequence[float]) -> float:
    """Population standard deviation."""
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return math.sqrt(variance)


def _period_returns(closes: Sequence[float]) -> tuple[float, ...]:
    """Compute r_t = close_t / close_{t-1} - 1 for t > 0."""
    if len(closes) < 2:
        return ()
    return tuple(
        _round(closes[i] / closes[i - 1] - 1.0, _PERIOD_DECIMALS)
        for i in range(1, len(closes))
    )


def _total_return_pct(closes: Sequence[float]) -> float:
    if len(closes) < 2:
        return 0.0
    return _round((closes[-1] / closes[0] - 1.0) * 100.0, _PERCENTAGE_DECIMALS)


def _max_drawdown_pct(values: Sequence[float]) -> float:
    """Compute max drawdown percentage from a value series."""
    if not values:
        return 0.0
    peak = values[0]
    max_dd = 0.0
    for value in values:
        if value > peak:
            peak = value
        if peak > 0.0:
            dd = (peak - value) / peak * 100.0
            if dd > max_dd:
                max_dd = dd
    return _round(max_dd, _PERCENTAGE_DECIMALS)


def _volatility_pct(period_returns: Sequence[float], scale_factor: float) -> float:
    if len(period_returns) < 2:
        return 0.0
    std = _std_dev(period_returns)
    return _round(std * math.sqrt(scale_factor) * 100.0, _PERCENTAGE_DECIMALS)


def _win_rate_pct(period_returns: Sequence[float]) -> float:
    if not period_returns:
        return 0.0
    positive = sum(1 for r in period_returns if r > 0.0)
    return _round(positive / len(period_returns) * 100.0, _PERCENTAGE_DECIMALS)


def _sort_bars(bars: Sequence[Any]) -> tuple[Any, ...]:
    return tuple(sorted(bars, key=lambda b: b.timestamp))


def _filter_bars_by_window(
    bars: Sequence[BacktestPriceBar],
    start: datetime | None,
    end: datetime | None,
) -> tuple[BacktestPriceBar, ...]:
    result = list(bars)
    if start is not None:
        result = [b for b in result if b.timestamp >= start]
    if end is not None:
        result = [b for b in result if b.timestamp <= end]
    return tuple(result)


def _valid_price_history(
    bars: Sequence[BacktestPriceBar], min_obs: int
) -> tuple[bool, bool, bool]:
    """Return (has_any_bars, has_enough_bars, all_prices_valid)."""
    has_any = len(bars) > 0
    has_enough = len(bars) >= min_obs
    all_valid = all(
        _is_valid_finite(b.close) and b.close > 0.0 for b in bars
    )
    return has_any, has_enough, all_valid


def _build_safety_flags(
    inputs: Sequence[BacktestInput],
    config: BacktestRunConfig,
) -> tuple[BacktestSafetyFlags, list[str]]:
    """Aggregate safety flags and blocking reason codes from inputs."""
    flags = {
        "has_unsafe_content": False,
        "has_invalid_pair": False,
        "has_invalid_price": False,
        "has_invalid_date": False,
        "has_blocked_context": False,
        "has_missing_required_context": False,
        "has_inconsistent_state": False,
    }
    reason_codes: list[str] = []

    for inp in inputs:
        pair = inp.pair
        if not isinstance(pair, str) or not pair.strip():
            flags["has_invalid_pair"] = True
            if INVALID_PAIR not in reason_codes:
                reason_codes.append(INVALID_PAIR)
            continue

        tags = list(inp.tags) + (list(inp.decision.tags) if inp.decision else [])
        metadata = dict(inp.metadata)
        if inp.decision is not None:
            metadata.update(inp.decision.metadata)
        if has_unsafe_backtest_content(pair, tags, metadata):
            flags["has_unsafe_content"] = True
            if UNSAFE_BACKTEST_CONTENT not in reason_codes:
                reason_codes.append(UNSAFE_BACKTEST_CONTENT)

        # Check invalid dates in price bars
        for bar in inp.price_bars:
            if not isinstance(bar.timestamp, datetime) or bar.timestamp.tzinfo is None:
                flags["has_invalid_date"] = True
                if INVALID_DATE not in reason_codes:
                    reason_codes.append(INVALID_DATE)
            if bar.pair != pair:
                flags["has_inconsistent_state"] = True
                if INVALID_PAIR not in reason_codes:
                    reason_codes.append(INVALID_PAIR)
            if not _is_valid_finite(bar.close) or bar.close <= 0.0:
                flags["has_invalid_price"] = True
                if INVALID_PRICE not in reason_codes:
                    reason_codes.append(INVALID_PRICE)

        decision = inp.decision
        if decision is not None:
            if decision.pair != pair:
                flags["has_inconsistent_state"] = True
                if INVALID_PAIR not in reason_codes:
                    reason_codes.append(INVALID_PAIR)
            # Per-candidate blocked decisions are handled by _classify_candidate;
            # do not block the whole report here.

    safety_flags = BacktestSafetyFlags(**flags)
    return safety_flags, reason_codes


def _state_from_decision(decision: BacktestCandidateDecision | None) -> BacktestState | None:
    """Map a decision state string to a BacktestState if known."""
    if decision is None:
        return None
    mapping = {
        "included": BacktestState.INCLUDED,
        "capped": BacktestState.CAPPED,
        "watchlist": BacktestState.WATCHLIST,
        "excluded": BacktestState.EXCLUDED,
        "insufficient_data": BacktestState.INSUFFICIENT_DATA,
        "blocked": BacktestState.BLOCKED,
    }
    return mapping.get(decision.state.strip().lower())


def _classify_candidate(
    inp: BacktestInput,
    config: BacktestRunConfig,
) -> tuple[BacktestState, list[str], tuple[BacktestPriceBar, ...]]:
    """Determine the backtest state and reason codes for a candidate."""
    reason_codes: list[str] = []
    pair = inp.pair
    decision = inp.decision

    if not isinstance(pair, str) or not pair.strip():
        return BacktestState.BLOCKED, [INVALID_PAIR], ()

    if decision is not None and decision.pair != pair:
        return BacktestState.BLOCKED, [INVALID_PAIR], ()

    tags = list(inp.tags) + (list(decision.tags) if decision else [])
    metadata = dict(inp.metadata)
    if decision is not None:
        metadata.update(decision.metadata)
    if has_unsafe_backtest_content(pair, tags, metadata):
        return BacktestState.BLOCKED, [UNSAFE_BACKTEST_CONTENT], ()

    if decision is None:
        if not config.allow_missing_decision:
            if config.block_on_missing_context:
                return BacktestState.BLOCKED, [MISSING_DECISION_CONTEXT], ()
            return BacktestState.INSUFFICIENT_DATA, [MISSING_DECISION_CONTEXT], ()
        # Treat as active for simulation; classification is empty
        base_state = BacktestState.INCLUDED
    else:
        base_state = _state_from_decision(decision)
    if base_state is None:
        return BacktestState.BLOCKED, [INVALID_PAIR], ()

    if base_state == BacktestState.BLOCKED:
        return BacktestState.BLOCKED, [DISCOVERY_BLOCKED], ()

    # Validate price bars for non-blocked states
    bars = _filter_bars_by_window(inp.price_bars, config.start_timestamp, config.end_timestamp)
    bars = _sort_bars(bars)
    has_any, has_enough, all_valid = _valid_price_history(bars, config.min_observation_count)

    if not all_valid:
        return BacktestState.BLOCKED, [INVALID_PRICE], ()

    if not has_any:
        if base_state == BacktestState.EXCLUDED:
            return BacktestState.EXCLUDED, [EXCLUDED_BY_RESEARCH_CONSTRAINTS], ()
        if base_state == BacktestState.WATCHLIST:
            return BacktestState.WATCHLIST, [WATCHLIST_ZERO_WEIGHT], ()
        if config.block_on_missing_context:
            return BacktestState.BLOCKED, [MISSING_PRICE_HISTORY], ()
        return BacktestState.INSUFFICIENT_DATA, [MISSING_PRICE_HISTORY], ()

    if not has_enough:
        reason_codes.append(INSUFFICIENT_PRICE_HISTORY)
        reason_codes.append(MIN_OBSERVATION_COUNT_NOT_MET)
        return BacktestState.INSUFFICIENT_DATA, reason_codes, bars

    if base_state == BacktestState.EXCLUDED:
        return BacktestState.EXCLUDED, [EXCLUDED_BY_RESEARCH_CONSTRAINTS], bars

    if base_state == BacktestState.WATCHLIST:
        return BacktestState.WATCHLIST, [WATCHLIST_ZERO_WEIGHT], bars

    if base_state in (BacktestState.INCLUDED, BacktestState.CAPPED):
        return base_state, [], bars

    # Default fail-closed for unknown states
    return BacktestState.BLOCKED, [INVALID_PAIR], ()


def _compute_weights(
    active_candidates: Sequence[_CandidateContext],
    config: BacktestRunConfig,
) -> dict[str, float]:
    """Return simulated weights (percent) for active candidates."""
    if not active_candidates:
        return {}

    mode = config.allocation_mode
    weights: dict[str, float] = {}

    if mode == BacktestAllocationMode.EQUAL_WEIGHT:
        weight = 100.0 / len(active_candidates)
        for ctx in active_candidates:
            weights[ctx.pair] = _round(weight, _SUB_METRIC_DECIMALS)
    elif mode == BacktestAllocationMode.RESEARCH_WEIGHT:
        total = sum(
            (ctx.decision.final_weight_pct if ctx.decision else 0.0)
            for ctx in active_candidates
        )
        if total <= 0.0:
            weight = 100.0 / len(active_candidates)
            for ctx in active_candidates:
                weights[ctx.pair] = _round(weight, _SUB_METRIC_DECIMALS)
        else:
            for ctx in active_candidates:
                decision = ctx.decision
                w = (
                    (decision.final_weight_pct / total * 100.0)
                    if decision and total > 0.0
                    else 0.0
                )
                weights[ctx.pair] = _round(w, _SUB_METRIC_DECIMALS)
    elif mode == BacktestAllocationMode.CUSTOM_WEIGHT:
        total = 0.0
        for ctx in active_candidates:
            w = config.custom_weights.get(ctx.pair, 0.0)
            total += w
        for ctx in active_candidates:
            w = config.custom_weights.get(ctx.pair, 0.0)
            if total > 0.0:
                w = w / total * 100.0
            weights[ctx.pair] = _round(w, _SUB_METRIC_DECIMALS)
    else:
        raise ValueError(f"Unsupported allocation mode: {mode}")

    return weights


class _CandidateContext:
    """Internal mutable context for a candidate during simulation."""

    def __init__(
        self,
        inp: BacktestInput,
        state: BacktestState,
        reason_codes: list[str],
        bars: tuple[BacktestPriceBar, ...],
    ) -> None:
        self.inp = inp
        self.pair = inp.pair
        self.decision = inp.decision
        self.state = state
        self.reason_codes = reason_codes
        self.bars = bars
        self.closes = tuple(_round(b.close, _RAW_DECIMALS) for b in bars)
        self.period_returns = _period_returns(self.closes)
        self.simulated_weight = 0.0
        self.missing_data_count = 0


def _build_union_timestamps(
    active_candidates: Sequence[_CandidateContext],
) -> list[datetime]:
    """Return sorted union of timestamps from active candidates."""
    timestamps: set[datetime] = set()
    for ctx in active_candidates:
        for bar in ctx.bars:
            timestamps.add(bar.timestamp)
    return sorted(timestamps)


def _build_equity_curve(
    active_candidates: Sequence[_CandidateContext],
    weights: dict[str, float],
    union_timestamps: list[datetime],
) -> tuple[BacktestPortfolioSnapshot, ...]:
    """Build portfolio equity curve from active candidates."""
    if not union_timestamps:
        return ()

    # Build per-candidate timestamp -> return map
    candidate_returns: dict[str, dict[datetime, float]] = {}
    for ctx in active_candidates:
        mapping: dict[datetime, float] = {}
        for i, bar in enumerate(ctx.bars):
            if i == 0:
                mapping[bar.timestamp] = 0.0
            else:
                prev_close = ctx.closes[i - 1]
                if prev_close > 0.0:
                    mapping[bar.timestamp] = _round(
                        bar.close / prev_close - 1.0, _PERIOD_DECIMALS
                    )
                else:
                    mapping[bar.timestamp] = 0.0
        candidate_returns[ctx.pair] = mapping
        ctx.missing_data_count = len(union_timestamps) - len(mapping)

    equity = 1.0
    snapshots: list[BacktestPortfolioSnapshot] = []
    for ts in union_timestamps:
        weighted_return = 0.0
        active_count = 0
        weight_sum = 0.0
        for ctx in active_candidates:
            w = weights.get(ctx.pair, 0.0) / 100.0
            if w <= 0.0:
                continue
            ret = candidate_returns[ctx.pair].get(ts)
            if ret is not None:
                weighted_return += w * ret
                active_count += 1
                weight_sum += w * 100.0
        equity = equity * (1.0 + weighted_return)
        equity = _round(equity, _RAW_DECIMALS)
        snapshots.append(
            BacktestPortfolioSnapshot(
                timestamp=ts,
                equity=equity,
                weight_sum=_round(weight_sum, _SUB_METRIC_DECIMALS),
                observation_count=active_count,
            )
        )
    return tuple(snapshots)


def _portfolio_period_returns(equity_curve: Sequence[BacktestPortfolioSnapshot]) -> tuple[float, ...]:
    if len(equity_curve) < 2:
        return ()
    return tuple(
        _round(
            equity_curve[i].equity / equity_curve[i - 1].equity - 1.0,
            _PERIOD_DECIMALS,
        )
        for i in range(1, len(equity_curve))
    )


def _candidate_result(
    ctx: _CandidateContext,
    allocation_mode: BacktestAllocationMode,
    volatility_scale_factor: float,
    rank: int | None = None,
) -> BacktestCandidateResult:
    notes: list[str] = []
    if ctx.state in (BacktestState.BLOCKED, BacktestState.INSUFFICIENT_DATA):
        notes.append(f"Candidate {ctx.pair} not simulated: {ctx.state.value}")
    if ctx.state == BacktestState.WATCHLIST:
        notes.append(f"Candidate {ctx.pair} is watchlist; simulated weight is zero.")
    if ctx.state == BacktestState.EXCLUDED:
        notes.append(f"Candidate {ctx.pair} excluded by research constraints.")

    return BacktestCandidateResult(
        pair=ctx.pair,
        state=ctx.state,
        classification=ctx.decision.classification if ctx.decision else "",
        allocation_mode=allocation_mode,
        simulated_weight=_round(ctx.simulated_weight, _SUB_METRIC_DECIMALS),
        total_return_pct=_total_return_pct(ctx.closes),
        max_drawdown_pct=_max_drawdown_pct(ctx.closes),
        volatility_pct=_volatility_pct(ctx.period_returns, volatility_scale_factor),
        win_rate_pct=_win_rate_pct(ctx.period_returns),
        observation_count=len(ctx.bars),
        missing_data_count=ctx.missing_data_count,
        insufficient_data_count=1 if ctx.state == BacktestState.INSUFFICIENT_DATA else 0,
        period_returns=ctx.period_returns,
        reason_codes=tuple(ctx.reason_codes),
        tags=ctx.inp.tags,
        metadata=ctx.inp.metadata,
        notes=tuple(notes),
        rank=rank,
    )


def _sort_candidate_results(
    results: Sequence[BacktestCandidateResult],
) -> tuple[BacktestCandidateResult, ...]:
    """Sort by state priority, then return desc, then drawdown asc, then pair asc."""
    sorted_results = sorted(
        results,
        key=lambda r: (
            {
                BacktestState.INCLUDED: 0,
                BacktestState.CAPPED: 1,
                BacktestState.WATCHLIST: 2,
                BacktestState.EXCLUDED: 3,
                BacktestState.INSUFFICIENT_DATA: 4,
                BacktestState.BLOCKED: 5,
            }[r.state],
            -r.total_return_pct,
            r.max_drawdown_pct,
            r.pair,
        ),
    )
    ranked: list[BacktestCandidateResult] = []
    for i, result in enumerate(sorted_results, start=1):
        ranked.append(
            BacktestCandidateResult(
                pair=result.pair,
                state=result.state,
                classification=result.classification,
                allocation_mode=result.allocation_mode,
                simulated_weight=result.simulated_weight,
                total_return_pct=result.total_return_pct,
                max_drawdown_pct=result.max_drawdown_pct,
                volatility_pct=result.volatility_pct,
                win_rate_pct=result.win_rate_pct,
                observation_count=result.observation_count,
                missing_data_count=result.missing_data_count,
                insufficient_data_count=result.insufficient_data_count,
                period_returns=result.period_returns,
                reason_codes=result.reason_codes,
                tags=result.tags,
                metadata=result.metadata,
                notes=result.notes,
                rank=i,
            )
        )
    return tuple(ranked)


def build_backtest_safety_flags(
    inputs: Sequence[BacktestInput],
    config: BacktestRunConfig,
) -> BacktestSafetyFlags:
    """Build safety flags from inputs and config."""
    flags, _ = _build_safety_flags(inputs, config)
    return flags


def _is_config_valid(config: BacktestRunConfig) -> bool:
    """Return True if config thresholds are valid."""
    if not _is_valid_finite(config.volatility_scale_factor):
        return False
    if config.volatility_scale_factor <= 0.0:
        return False
    if not isinstance(config.min_observation_count, int) or config.min_observation_count < 0:
        return False
    for k, v in config.custom_weights.items():
        if not _is_valid_finite(v) or v < 0.0:
            return False
    if config.start_timestamp is not None and config.start_timestamp.tzinfo is None:
        return False
    if config.end_timestamp is not None and config.end_timestamp.tzinfo is None:
        return False
    if (
        config.start_timestamp is not None
        and config.end_timestamp is not None
        and config.start_timestamp > config.end_timestamp
    ):
        return False
    return True


def build_backtest_report(
    inputs: Sequence[BacktestInput],
    config: BacktestRunConfig,
    *,
    report_id: str | None = None,
    generated_at: datetime | None = None,
    metadata: Mapping[str, str] | None = None,
) -> BacktestReport:
    """Build a deterministic local backtest report.

    The engine never opens files, follows paths, validates paths, calls network
    endpoints, or accesses external resources. Inputs are already-loaded local
    values only.
    """
    # Validate inputs are not mutated; capture tuples
    inputs_tuple = tuple(inputs)

    if not _is_config_valid(config):
        return BacktestReport.blocked(
            reason_code=INVALID_PAIR,
            report_id=report_id or str(uuid.uuid4()),
            generated_at=generated_at or datetime.now(timezone.utc),
            metadata=metadata,
        )

    safety_flags, blocking_reasons = _build_safety_flags(inputs_tuple, config)

    if not safety_flags.is_safe:
        primary_reason = blocking_reasons[0] if blocking_reasons else INVALID_PAIR
        return BacktestReport.blocked(
            reason_code=primary_reason,
            report_id=report_id or str(uuid.uuid4()),
            generated_at=generated_at or datetime.now(timezone.utc),
            metadata=metadata,
        )

    if not inputs_tuple:
        primary_reason = MISSING_PRICE_HISTORY
        return BacktestReport.blocked(
            reason_code=primary_reason,
            report_id=report_id or str(uuid.uuid4()),
            generated_at=generated_at or datetime.now(timezone.utc),
            metadata=metadata,
        )

    # Classify each candidate
    contexts: list[_CandidateContext] = []
    for inp in inputs_tuple:
        state, reason_codes, bars = _classify_candidate(inp, config)
        contexts.append(_CandidateContext(inp, state, reason_codes, bars))

    # Active candidates are INCLUDED/CAPPED with usable price history
    active_candidates = [
        ctx for ctx in contexts
        if ctx.state in (BacktestState.INCLUDED, BacktestState.CAPPED)
    ]

    weights = _compute_weights(active_candidates, config)
    for ctx in contexts:
        if ctx.pair in weights:
            ctx.simulated_weight = weights[ctx.pair]

    union_timestamps = _build_union_timestamps(active_candidates)
    equity_curve = _build_equity_curve(active_candidates, weights, union_timestamps)
    portfolio_period_returns = _portfolio_period_returns(equity_curve)

    candidate_results = [
        _candidate_result(ctx, config.allocation_mode, config.volatility_scale_factor)
        for ctx in contexts
    ]

    # Filter excluded if requested
    if not config.include_excluded_candidates:
        candidate_results = [
            r for r in candidate_results if r.state != BacktestState.EXCLUDED
        ]

    candidate_results = _sort_candidate_results(candidate_results)

    # Portfolio metrics
    equity_values = [s.equity for s in equity_curve]
    portfolio_total_return = _total_return_pct(equity_values) if equity_values else 0.0
    portfolio_max_drawdown = _max_drawdown_pct(equity_values)
    portfolio_volatility = _volatility_pct(
        portfolio_period_returns, config.volatility_scale_factor
    )
    portfolio_win_rate = _win_rate_pct(portfolio_period_returns)

    state_counts = {
        BacktestState.INCLUDED: 0,
        BacktestState.CAPPED: 0,
        BacktestState.WATCHLIST: 0,
        BacktestState.EXCLUDED: 0,
        BacktestState.INSUFFICIENT_DATA: 0,
        BacktestState.BLOCKED: 0,
    }
    for ctx in contexts:
        state_counts[ctx.state] += 1

    missing_data_total = sum(ctx.missing_data_count for ctx in contexts)
    insufficient_count = state_counts[BacktestState.INSUFFICIENT_DATA]
    blocked_count = state_counts[BacktestState.BLOCKED]
    candidate_count = len(inputs_tuple)

    ready_price_history = 0
    missing_price_history = 0
    blocked_decision = 0
    for ctx in contexts:
        has_any, has_enough, all_valid = _valid_price_history(
            ctx.bars, config.min_observation_count
        )
        if ctx.state == BacktestState.BLOCKED:
            blocked_decision += 1
        elif has_enough and all_valid:
            ready_price_history += 1
        else:
            missing_price_history += 1

    data_quality_score = _round(
        (ready_price_history / max(candidate_count, 1)) * 100.0,
        _SUB_METRIC_DECIMALS,
    )

    all_counts_consistent = (
        sum(state_counts.values()) == candidate_count
    )

    data_quality = BacktestDataQuality(
        total_inputs=candidate_count,
        included_count=state_counts[BacktestState.INCLUDED],
        capped_count=state_counts[BacktestState.CAPPED],
        watchlist_count=state_counts[BacktestState.WATCHLIST],
        excluded_count=state_counts[BacktestState.EXCLUDED],
        insufficient_data_count=insufficient_count,
        blocked_count=blocked_count,
        ready_price_history_count=ready_price_history,
        missing_price_history_count=missing_price_history,
        blocked_decision_count=blocked_decision,
        observation_count=len(equity_curve),
        missing_data_count=missing_data_total,
        data_quality_score=data_quality_score,
        all_counts_consistent=all_counts_consistent,
        safety_flags_ok=safety_flags.is_safe,
        has_unsafe_content=safety_flags.has_unsafe_content,
    )

    portfolio_result = BacktestPortfolioResult(
        total_return_pct=portfolio_total_return,
        max_drawdown_pct=portfolio_max_drawdown,
        volatility_pct=portfolio_volatility,
        win_rate_pct=portfolio_win_rate,
        observation_count=len(equity_curve),
        missing_data_count=missing_data_total,
        insufficient_data_count=insufficient_count,
        blocked_count=blocked_count,
        candidate_count=candidate_count,
        equity_curve=equity_curve,
        reason_codes=tuple(blocking_reasons) if blocking_reasons else (),
        metadata={},
    )

    report_reason_codes = list(blocking_reasons)
    report_reason_codes.extend(BACKTEST_ADVISORY_REASON_CODES)
    report_reason_codes = list(dict.fromkeys(report_reason_codes))

    notes = (
        "MVP-28 Local Research Backtesting Engine — human research only.",
        "Simulated weights are research allocations, not orders or positions.",
        "No network, exchange, file, database, or runtime infrastructure used.",
    )

    return BacktestReport(
        version=BACKTEST_VERSION,
        report_id=report_id or str(uuid.uuid4()),
        generated_at=generated_at or datetime.now(timezone.utc),
        inputs=inputs_tuple,
        config=config,
        safety_flags=safety_flags,
        candidate_results=candidate_results,
        portfolio_result=portfolio_result,
        data_quality=data_quality,
        reason_codes=tuple(report_reason_codes),
        metadata=metadata or {},
        notes=notes,
    )
