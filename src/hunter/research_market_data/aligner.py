"""Coverage, gap, and benchmark alignment for research market data (MVP-63 / SPEC-064)."""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from datetime import datetime, timedelta
from decimal import Decimal

from hunter.research_market_data.models import (
    BELOW_MIN_ROWS,
    CandleSeries,
    GAPS_FOUND,
    INSUFFICIENT_COVERAGE,
    MarketDataSourceRef,
    MissingInterval,
    NormalizedCandle,
    ResearchMarketDataConfig,
)
from hunter.research_market_data.validator import detect_timeframe


def _timeframe_to_seconds(timeframe: str) -> int:
    """Return the approximate candle interval in seconds for a canonical timeframe."""
    if timeframe == "unknown":
        return 0
    mapping: dict[str, int] = {
        "1m": 60,
        "5m": 300,
        "15m": 900,
        "30m": 1800,
        "1h": 3600,
        "4h": 14400,
        "8h": 28800,
        "12h": 43200,
        "1d": 86400,
        "1w": 604800,
    }
    if timeframe in mapping:
        return mapping[timeframe]
    if timeframe.endswith("s"):
        try:
            return int(timeframe[:-1])
        except ValueError:
            return 0
    return 0


def _compute_coverage_and_gaps(
    candles: Sequence[NormalizedCandle],
    timeframe: str,
) -> tuple[Decimal, tuple[MissingInterval, ...]]:
    """Compute coverage and contiguous missing intervals for a sorted series."""
    if len(candles) < 2:
        return Decimal("1.0"), ()

    interval = _timeframe_to_seconds(timeframe)
    if interval <= 0:
        return Decimal("1.0"), ()

    timestamps = sorted(candle.timestamp for candle in candles)
    min_ts = timestamps[0]
    max_ts = timestamps[-1]
    expected_count = int((max_ts - min_ts).total_seconds() // interval) + 1
    if expected_count <= 0:
        return Decimal("1.0"), ()

    actual_set = set(timestamps)
    missing_intervals: list[MissingInterval] = []
    gap_start: datetime | None = None
    gap_expected = 0
    gap_actual = 0

    for i in range(expected_count):
        expected_ts = min_ts + timedelta(seconds=i * interval)
        if expected_ts in actual_set:
            if gap_start is not None:
                missing_intervals.append(
                    MissingInterval(
                        start=gap_start,
                        end=expected_ts - timedelta(seconds=interval),
                        expected_count=gap_expected,
                        actual_count=gap_actual,
                        reason_code=GAPS_FOUND,
                    )
                )
                gap_start = None
                gap_expected = 0
                gap_actual = 0
        else:
            if gap_start is None:
                gap_start = expected_ts
            gap_expected += 1
            gap_actual = 0

    if gap_start is not None:
        missing_intervals.append(
            MissingInterval(
                start=gap_start,
                end=max_ts,
                expected_count=gap_expected,
                actual_count=gap_actual,
                reason_code=GAPS_FOUND,
            )
        )

    coverage = Decimal(len(candles)) / Decimal(expected_count)
    return coverage, tuple(missing_intervals)


def _with_timeframe(
    candles: Sequence[NormalizedCandle], timeframe: str
) -> tuple[NormalizedCandle, ...]:
    """Return candles with their ``timeframe`` field set to the series timeframe."""
    return tuple(
        dataclasses.replace(candle, timeframe=timeframe) for candle in candles
    )


def build_candle_series(
    source: MarketDataSourceRef,
    candles: Sequence[NormalizedCandle],
    config: ResearchMarketDataConfig,
    pair: str,
) -> CandleSeries:
    """Build a validated ``CandleSeries`` with coverage and gap analysis."""
    sorted_candles = sorted(candles, key=lambda c: c.timestamp)
    timeframe = detect_timeframe(sorted_candles)
    coverage, missing_intervals = _compute_coverage_and_gaps(sorted_candles, timeframe)
    reason_codes: list[str] = []
    if missing_intervals:
        reason_codes.append(GAPS_FOUND)
    if coverage < config.coverage_threshold:
        reason_codes.append(INSUFFICIENT_COVERAGE)
    if len(sorted_candles) < config.min_required_rows:
        reason_codes.append(BELOW_MIN_ROWS)

    normalized_candles = _with_timeframe(sorted_candles, timeframe)
    return CandleSeries(
        pair=pair,
        timeframe=timeframe,
        candles=normalized_candles,
        source=source,
        coverage=coverage,
        coverage_threshold=config.coverage_threshold,
        missing_intervals=missing_intervals,
        reason_codes=tuple(reason_codes),
        metadata={},
    )


def align_candidate(
    candidate: CandleSeries,
    btc: CandleSeries,
    eth: CandleSeries | None,
    config: ResearchMarketDataConfig,
) -> CandleSeries | None:
    """Return a candidate series filtered to the common timestamp intersection.

    Returns ``None`` if the aligned history does not satisfy the configured
    minimum row requirement or coverage threshold.
    """
    common = set(btc.timestamps)
    common &= set(candidate.timestamps)
    if eth is not None:
        common &= set(eth.timestamps)
    if not common:
        return None

    sorted_common = sorted(common)
    filtered = tuple(c for c in candidate.candles if c.timestamp in common)
    if len(filtered) < config.min_required_rows:
        return None

    timeframe = detect_timeframe(filtered)
    coverage, missing_intervals = _compute_coverage_and_gaps(filtered, timeframe)
    if coverage < config.coverage_threshold:
        return None

    normalized_candles = _with_timeframe(filtered, timeframe)
    return CandleSeries(
        pair=candidate.pair,
        timeframe=timeframe,
        candles=normalized_candles,
        source=candidate.source,
        coverage=coverage,
        coverage_threshold=config.coverage_threshold,
        missing_intervals=missing_intervals,
        reason_codes=candidate.reason_codes,
        metadata={**candidate.metadata, "aligned_to_btc": "true"},
    )


def align_benchmark(
    benchmark: CandleSeries,
    common_timestamps: set[datetime],
) -> CandleSeries:
    """Return a benchmark series filtered to the given common timestamps."""
    filtered = tuple(c for c in benchmark.candles if c.timestamp in common_timestamps)
    timeframe = detect_timeframe(filtered)
    coverage, missing_intervals = _compute_coverage_and_gaps(filtered, timeframe)
    normalized_candles = _with_timeframe(filtered, timeframe)
    return CandleSeries(
        pair=benchmark.pair,
        timeframe=timeframe,
        candles=normalized_candles,
        source=benchmark.source,
        coverage=coverage,
        coverage_threshold=benchmark.coverage_threshold,
        missing_intervals=missing_intervals,
        reason_codes=benchmark.reason_codes,
        metadata={**benchmark.metadata, "aligned": "true"},
    )
