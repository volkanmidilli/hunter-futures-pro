"""Terminal-state resolution for SPEC-076 outcome evaluation (M2).

Implements the mandated resolution order.  ``PENDING_HORIZON`` is computed
transiently and never persisted.  After the horizon has elapsed, every
cohort member resolves in one run, in this exact order:

1. Invalid snapshot -> ``SNAPSHOT_INVALID`` (snapshot-level, engine).
2. Missing pair price source -> ``OUTCOME_UNAVAILABLE_NO_SOURCE``.
3. Missing required endpoint candles -> ``OUTCOME_UNAVAILABLE_GAP``.
4. Endpoint candles fail SPEC-075 price validation ->
   ``OUTCOME_UNAVAILABLE_INVALID_PRICE``.
5. Valid intra-window coverage below ``min_window_coverage`` ->
   ``OUTCOME_UNAVAILABLE_GAP``.
6. Benchmark validation fails -> ``BENCHMARK_UNAVAILABLE``.
7. Otherwise -> ``OUTCOME_AVAILABLE``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

from hunter.research_outcome_evaluation.models import (
    PENDING_HORIZON,
    TerminalState,
    parse_horizon_hours,
)
from hunter.research_outcome_evaluation.price_source import Candle, PriceSeries

# Snapshot reference anchor: 08:00 UTC on snapshot_date.
REFERENCE_HOUR_UTC = 8


@dataclass(frozen=True)
class WindowAnchors:
    """Deterministic window anchors derived only from snapshot_date + horizon.

    ``reference_close_time`` is the close time of the reference candle
    (snapshot_date 08:00 UTC); the reference candle opens one hour earlier.
    ``endpoint_open_time`` is the open time of the endpoint candle, which
    closes at ``reference_close_time + horizon_hours``.
    """

    reference_open_time: datetime
    reference_close_time: datetime
    endpoint_open_time: datetime
    endpoint_close_time: datetime
    expected_slots: int


def compute_window_anchors(snapshot_date: str, outcome_horizon: str) -> WindowAnchors:
    """Derive deterministic window anchors from snapshot_date and horizon."""
    from datetime import date

    day = date.fromisoformat(snapshot_date)
    reference_close = datetime.combine(day, time(REFERENCE_HOUR_UTC, 0), tzinfo=timezone.utc)
    hours = parse_horizon_hours(outcome_horizon)
    return WindowAnchors(
        reference_open_time=reference_close - timedelta(hours=1),
        reference_close_time=reference_close,
        endpoint_open_time=reference_close - timedelta(hours=1) + timedelta(hours=hours),
        endpoint_close_time=reference_close + timedelta(hours=hours),
        expected_slots=hours,
    )


def horizon_elapsed(anchors: WindowAnchors, now: datetime) -> bool:
    """True when the horizon has elapsed: endpoint candle close <= now."""
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return anchors.endpoint_close_time <= now


def transient_state(anchors: WindowAnchors, now: datetime) -> str | None:
    """Return ``PENDING_HORIZON`` when the horizon has not elapsed, else None.

    The result is transient: callers must never persist it.
    """
    return None if horizon_elapsed(anchors, now) else PENDING_HORIZON


@dataclass(frozen=True)
class PairEvaluation:
    """Resolved evaluation inputs for one cohort member (pre-metrics)."""

    terminal_state: TerminalState
    anchors: WindowAnchors
    series: PriceSeries | None
    reference_candle: Candle | None
    endpoint_candle: Candle | None
    coverage_ratio_num: int
    coverage_ratio_den: int
    failure_stage: str | None


def resolve_series(
    *,
    series: PriceSeries | None,
    anchors: WindowAnchors,
    min_window_coverage_num: int,
    min_window_coverage_den: int,
) -> PairEvaluation:
    """Resolve one price series against the mandated order (steps 2-5, 7).

    ``series=None`` represents a missing price source (step 2).  The
    benchmark gate (step 6) is applied by the engine, not here.
    """
    if series is None:
        return PairEvaluation(
            terminal_state=TerminalState.OUTCOME_UNAVAILABLE_NO_SOURCE,
            anchors=anchors,
            series=None,
            reference_candle=None,
            endpoint_candle=None,
            coverage_ratio_num=0,
            coverage_ratio_den=anchors.expected_slots,
            failure_stage="NO_SOURCE",
        )

    by_open = series.by_open_time()
    reference = by_open.get(anchors.reference_open_time)
    endpoint = by_open.get(anchors.endpoint_open_time)

    # Step 3: required endpoint candles must exist.
    if reference is None or endpoint is None:
        return PairEvaluation(
            terminal_state=TerminalState.OUTCOME_UNAVAILABLE_GAP,
            anchors=anchors,
            series=series,
            reference_candle=reference,
            endpoint_candle=endpoint,
            coverage_ratio_num=0,
            coverage_ratio_den=anchors.expected_slots,
            failure_stage="ENDPOINT_MISSING",
        )

    # Step 4: endpoint candles must pass SPEC-075 price validation.
    if not reference.valid or not endpoint.valid:
        return PairEvaluation(
            terminal_state=TerminalState.OUTCOME_UNAVAILABLE_INVALID_PRICE,
            anchors=anchors,
            series=series,
            reference_candle=reference,
            endpoint_candle=endpoint,
            coverage_ratio_num=0,
            coverage_ratio_den=anchors.expected_slots,
            failure_stage="ENDPOINT_INVALID_PRICE",
        )

    # Step 5: coverage of valid intra-window candles (endpoint inclusive).
    valid_in_window = 0
    for slot in range(1, anchors.expected_slots + 1):
        open_time = anchors.reference_open_time + timedelta(hours=slot)
        candle = by_open.get(open_time)
        if candle is not None and candle.valid:
            valid_in_window += 1

    if valid_in_window * min_window_coverage_den < min_window_coverage_num * anchors.expected_slots:
        return PairEvaluation(
            terminal_state=TerminalState.OUTCOME_UNAVAILABLE_GAP,
            anchors=anchors,
            series=series,
            reference_candle=reference,
            endpoint_candle=endpoint,
            coverage_ratio_num=valid_in_window,
            coverage_ratio_den=anchors.expected_slots,
            failure_stage="COVERAGE_BELOW_THRESHOLD",
        )

    # Step 7 (benchmark gate applied by the engine when needed).
    return PairEvaluation(
        terminal_state=TerminalState.OUTCOME_AVAILABLE,
        anchors=anchors,
        series=series,
        reference_candle=reference,
        endpoint_candle=endpoint,
        coverage_ratio_num=valid_in_window,
        coverage_ratio_den=anchors.expected_slots,
        failure_stage=None,
    )


def load_pair_series(
    pair: str,
    price_map: dict[str, Path],
    loader: object,
    now: datetime,
) -> PriceSeries | None:
    """Load the price series for ``pair``; ``None`` when no source exists.

    ``loader`` is the injected ``load_price_series`` callable so tests can
    substitute a fake without touching the filesystem.
    """
    path = price_map.get(pair)
    if path is None:
        return None
    assert callable(loader)
    return loader(path, pair, now)  # type: ignore[operator]
