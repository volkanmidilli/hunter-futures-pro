"""M2 tests: Feather price-series source and terminal-state resolution."""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pyarrow as pa
import pyarrow.feather as feather
import pytest

from hunter.research_outcome_evaluation.models import PENDING_HORIZON, TerminalState
from hunter.research_outcome_evaluation.price_source import (
    PriceSeries,
    build_price_source_map,
    load_price_series,
)
from hunter.research_outcome_evaluation.resolution import (
    compute_window_anchors,
    horizon_elapsed,
    resolve_series,
    transient_state,
)

NOW = datetime(2026, 2, 1, tzinfo=timezone.utc)


def _write_feather(path: Path, rows: list[tuple[datetime, float, float, float, float, float]]) -> None:
    table = pa.table(
        {
            "date": [r[0] for r in rows],
            "open": [r[1] for r in rows],
            "high": [r[2] for r in rows],
            "low": [r[3] for r in rows],
            "close": [r[4] for r in rows],
            "volume": [r[5] for r in rows],
        }
    )
    feather.write_feather(table, str(path))


def _hourly_rows(start: datetime, count: int, base: float = 100.0) -> list[tuple]:
    return [
        (start + timedelta(hours=i), base + i, base + i + 1, base + i - 1, base + i, 10.0)
        for i in range(count)
    ]


# ---------------------------------------------------------------------------
# price_source
# ---------------------------------------------------------------------------


def test_build_price_source_map_includes_btc_and_eth(tmp_path: Path) -> None:
    _write_feather(tmp_path / "BTC_USDT_USDT-1h-futures.feather", _hourly_rows(NOW - timedelta(hours=10), 10))
    _write_feather(tmp_path / "ETH_USDT_USDT-1h-futures.feather", _hourly_rows(NOW - timedelta(hours=10), 10))
    _write_feather(tmp_path / "SOL_USDT_USDT-1h-futures.feather", _hourly_rows(NOW - timedelta(hours=10), 10))
    mapping = build_price_source_map(tmp_path)
    assert mapping["BTC/USDT:USDT"].name == "BTC_USDT_USDT-1h-futures.feather"
    assert mapping["ETH/USDT:USDT"].name == "ETH_USDT_USDT-1h-futures.feather"
    assert mapping["SOL/USDT:USDT"].name == "SOL_USDT_USDT-1h-futures.feather"


def test_build_price_source_map_missing_dir(tmp_path: Path) -> None:
    from hunter.research_outcome_evaluation.errors import PriceSourceError

    with pytest.raises(PriceSourceError):
        build_price_source_map(tmp_path / "missing")


def test_load_price_series_valid(tmp_path: Path) -> None:
    start = NOW - timedelta(hours=5)
    path = tmp_path / "SOL_USDT_USDT-1h-futures.feather"
    _write_feather(path, _hourly_rows(start, 5))
    series = load_price_series(path, "SOL/USDT:USDT", NOW)
    assert len(series.candles) == 5
    assert all(c.valid for c in series.candles)
    assert series.candles[0].timestamp == start
    assert series.candles[-1].timestamp == start + timedelta(hours=4)


def test_load_price_series_marks_invalid_ohlcv(tmp_path: Path) -> None:
    start = NOW - timedelta(hours=3)
    rows = _hourly_rows(start, 3)
    rows[1] = (rows[1][0], -1.0, 1.0, 1.0, 1.0, 1.0)  # invalid open
    path = tmp_path / "SOL_USDT_USDT-1h-futures.feather"
    _write_feather(path, rows)
    series = load_price_series(path, "SOL/USDT:USDT", NOW)
    assert series.candles[0].valid
    assert not series.candles[1].valid
    assert series.candles[2].valid


def test_load_price_series_marks_future_and_duplicates_invalid(tmp_path: Path) -> None:
    start = NOW - timedelta(hours=2)
    rows = _hourly_rows(start, 2)
    rows.append((NOW + timedelta(hours=5), 1.0, 1.0, 1.0, 1.0, 1.0))  # future
    rows.append((start, 1.0, 1.0, 1.0, 1.0, 1.0))  # duplicate of first
    path = tmp_path / "SOL_USDT_USDT-1h-futures.feather"
    _write_feather(path, rows)
    series = load_price_series(path, "SOL/USDT:USDT", NOW)
    future = [c for c in series.candles if c.timestamp > NOW]
    assert future and not future[0].valid
    first_open = [c for c in series.candles if c.timestamp == start]
    assert len(first_open) == 2
    assert sum(1 for c in first_open if c.valid) == 1


def test_load_price_series_missing_column(tmp_path: Path) -> None:
    from hunter.research_outcome_evaluation.errors import PriceSourceError

    table = pa.table({"date": [NOW], "close": [1.0], "volume": [1.0]})
    path = tmp_path / "SOL_USDT_USDT-1h-futures.feather"
    feather.write_feather(table, str(path))
    with pytest.raises(PriceSourceError, match="missing required column"):
        load_price_series(path, "SOL/USDT:USDT", NOW)


# ---------------------------------------------------------------------------
# resolution: anchors and transient state
# ---------------------------------------------------------------------------


def test_window_anchors_1d() -> None:
    anchors = compute_window_anchors("2026-01-10", "1d")
    assert anchors.reference_close_time == datetime(2026, 1, 10, 8, tzinfo=timezone.utc)
    assert anchors.reference_open_time == datetime(2026, 1, 10, 7, tzinfo=timezone.utc)
    assert anchors.endpoint_open_time == datetime(2026, 1, 11, 7, tzinfo=timezone.utc)
    assert anchors.endpoint_close_time == datetime(2026, 1, 11, 8, tzinfo=timezone.utc)
    assert anchors.expected_slots == 24


def test_window_anchors_7d() -> None:
    anchors = compute_window_anchors("2026-01-10", "7d")
    assert anchors.endpoint_close_time == datetime(2026, 1, 17, 8, tzinfo=timezone.utc)
    assert anchors.expected_slots == 168


def test_transient_pending_horizon_never_terminal() -> None:
    anchors = compute_window_anchors("2026-01-10", "1d")
    before = datetime(2026, 1, 11, 7, 59, tzinfo=timezone.utc)
    after = datetime(2026, 1, 11, 8, 0, tzinfo=timezone.utc)
    assert transient_state(anchors, before) == PENDING_HORIZON
    assert transient_state(anchors, after) is None
    assert horizon_elapsed(anchors, after)
    assert not horizon_elapsed(anchors, before)


# ---------------------------------------------------------------------------
# resolution: mandated terminal-state order
# ---------------------------------------------------------------------------


def _series_for(snapshot_day: datetime, hours: int = 200, invalid_slots: tuple[int, ...] = ()) -> PriceSeries:
    """Continuous hourly series covering 2026-01-08 .. +hours from 00:00."""
    start = datetime(2026, 1, 8, tzinfo=timezone.utc)
    candles = []
    for i in range(hours):
        ts = start + timedelta(hours=i)
        valid = i not in invalid_slots
        close = 100.0 + i if valid else -1.0
        candles.append(
            _candle(ts, close, close + 1, close - 1, close, 10.0, valid)
        )
    return PriceSeries(pair="SOL/USDT:USDT", candles=tuple(candles))


def _candle(ts: datetime, o: float, h: float, l: float, c: float, v: float, valid: bool):  # noqa: E741
    from hunter.research_outcome_evaluation.price_source import Candle

    return Candle(timestamp=ts, open=o, high=h, low=l, close=c, volume=v, valid=valid)


def _resolve(series, horizon="1d", coverage=Decimal("0.95")):
    anchors = compute_window_anchors("2026-01-10", horizon)
    num = int(coverage * 10000)
    return resolve_series(
        series=series,
        anchors=anchors,
        min_window_coverage_num=num,
        min_window_coverage_den=10000,
    )


def test_resolve_no_source() -> None:
    result = _resolve(None)
    assert result.terminal_state is TerminalState.OUTCOME_UNAVAILABLE_NO_SOURCE
    assert result.failure_stage == "NO_SOURCE"


def test_resolve_missing_endpoint_candles() -> None:
    # Series ends before the endpoint candle open (2026-01-11 07:00).
    start = datetime(2026, 1, 8, tzinfo=timezone.utc)
    candles = tuple(
        _candle(start + timedelta(hours=i), 100.0, 101.0, 99.0, 100.0, 10.0, True)
        for i in range(24)  # ends 2026-01-08 23:00
    )
    series = PriceSeries(pair="SOL/USDT:USDT", candles=candles)
    result = _resolve(series)
    assert result.terminal_state is TerminalState.OUTCOME_UNAVAILABLE_GAP
    assert result.failure_stage == "ENDPOINT_MISSING"


def test_resolve_invalid_endpoint_price() -> None:
    # Reference candle open = 2026-01-10 07:00 -> index 55 from 2026-01-08 00:00.
    reference_index = 24 * 2 + 7
    series = _series_for(datetime(2026, 1, 8, tzinfo=timezone.utc), invalid_slots=(reference_index,))
    result = _resolve(series)
    assert result.terminal_state is TerminalState.OUTCOME_UNAVAILABLE_INVALID_PRICE
    assert result.failure_stage == "ENDPOINT_INVALID_PRICE"


def test_resolve_coverage_below_threshold() -> None:
    # 1d window = 24 slots; threshold 0.95 -> need >= 23 (ceil semantics:
    # valid * 10000 >= 9500 * 24 -> valid >= 22.8 -> 23). Invalidate 2 slots.
    window_first_index = 24 * 2 + 8  # first window candle 2026-01-10 08:00
    series = _series_for(
        datetime(2026, 1, 8, tzinfo=timezone.utc),
        invalid_slots=(window_first_index, window_first_index + 1),
    )
    result = _resolve(series)
    assert result.terminal_state is TerminalState.OUTCOME_UNAVAILABLE_GAP
    assert result.failure_stage == "COVERAGE_BELOW_THRESHOLD"
    assert result.coverage_ratio_num == 22
    assert result.coverage_ratio_den == 24


def test_resolve_available() -> None:
    series = _series_for(datetime(2026, 1, 8, tzinfo=timezone.utc))
    result = _resolve(series)
    assert result.terminal_state is TerminalState.OUTCOME_AVAILABLE
    assert result.failure_stage is None
    assert result.reference_candle is not None
    assert result.endpoint_candle is not None
    assert result.coverage_ratio_num == 24


def test_resolve_available_with_one_invalid_non_endpoint() -> None:
    # One invalid non-endpoint candle: coverage 23/24 >= 0.95*24=22.8 -> available.
    window_first_index = 24 * 2 + 8
    series = _series_for(
        datetime(2026, 1, 8, tzinfo=timezone.utc),
        invalid_slots=(window_first_index + 5,),
    )
    result = _resolve(series)
    assert result.terminal_state is TerminalState.OUTCOME_AVAILABLE
    assert result.coverage_ratio_num == 23
