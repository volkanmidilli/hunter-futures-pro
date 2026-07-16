"""Tests for hunter.research_market_data.aligner."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from hunter.research_market_data.aligner import (
    align_candidate,
    build_candle_series,
)
from hunter.research_market_data.models import (
    BELOW_MIN_ROWS,
    CandleSeries,
    GAPS_FOUND,
    INSUFFICIENT_COVERAGE,
    MarketDataSourceRef,
    NormalizedCandle,
    ResearchMarketDataConfig,
)


def make_source(row_count: int = 1) -> MarketDataSourceRef:
    return MarketDataSourceRef(
        source_id="id",
        path=Path("x.csv"),
        label="x",
        row_count=row_count,
        file_hash="abc",
    )


def make_candle(
    timestamp: datetime,
    open: Decimal = Decimal("100"),
    high: Decimal = Decimal("110"),
    low: Decimal = Decimal("90"),
    close: Decimal = Decimal("105"),
    volume: Decimal = Decimal("1000"),
    pair: str = "BTC/USDT",
) -> NormalizedCandle:
    return NormalizedCandle(
        timestamp=timestamp,
        open=open,
        high=high,
        low=low,
        close=close,
        volume=volume,
        pair=pair,
        timeframe="1d",
    )


def make_series(
    candles: list[NormalizedCandle],
    pair: str = "BTC/USDT",
    config: ResearchMarketDataConfig | None = None,
) -> CandleSeries:
    return build_candle_series(
        source=make_source(len(candles)),
        candles=candles,
        config=config or ResearchMarketDataConfig(),
        pair=pair,
    )


class TestBuildCandleSeries:
    def test_daily_coverage(self) -> None:
        candles = [
            make_candle(datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(days=i))
            for i in range(30)
        ]
        series = make_series(candles, pair="BTC/USDT")
        assert series.timeframe == "1d"
        assert series.coverage == Decimal("1.0")
        assert series.candles[0].timeframe == "1d"

    def test_gap_detected(self) -> None:
        candles = [
            make_candle(datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(days=i))
            for i in [0, 1, 2, 4, 5]
        ]
        series = make_series(candles, pair="BTC/USDT")
        assert GAPS_FOUND in series.reason_codes
        assert len(series.missing_intervals) == 1
        assert series.coverage < Decimal("1.0")

    def test_insufficient_coverage(self) -> None:
        config = ResearchMarketDataConfig(min_required_rows=2, coverage_threshold=Decimal("0.99"))
        candles = [
            make_candle(datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(days=i))
            for i in [0, 1, 2, 4, 5]
        ]
        series = make_series(candles, pair="BTC/USDT", config=config)
        assert INSUFFICIENT_COVERAGE in series.reason_codes

    def test_below_min_rows(self) -> None:
        config = ResearchMarketDataConfig(min_required_rows=50)
        candles = [
            make_candle(datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(days=i))
            for i in range(10)
        ]
        series = make_series(candles, pair="BTC/USDT", config=config)
        assert BELOW_MIN_ROWS in series.reason_codes


class TestAlignCandidate:
    def test_common_timestamps(self) -> None:
        btc_candles = [
            make_candle(datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(days=i), pair="BTC/USDT")
            for i in range(30)
        ]
        cand_candles = [
            make_candle(datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(days=i), pair="ETH/USDT")
            for i in range(30)
        ]
        btc = make_series(btc_candles, pair="BTC/USDT")
        cand = make_series(cand_candles, pair="ETH/USDT")
        aligned = align_candidate(cand, btc, None, ResearchMarketDataConfig())
        assert aligned is not None
        assert len(aligned.candles) == 30
        assert aligned.candles[0].timeframe == "1d"

    def test_excludes_on_mismatch(self) -> None:
        btc_candles = [
            make_candle(datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(days=i), pair="BTC/USDT")
            for i in range(30)
        ]
        cand_candles = [
            make_candle(datetime(2024, 2, 1, tzinfo=timezone.utc) + timedelta(days=i), pair="ETH/USDT")
            for i in range(30)
        ]
        btc = make_series(btc_candles, pair="BTC/USDT")
        cand = make_series(cand_candles, pair="ETH/USDT")
        aligned = align_candidate(cand, btc, None, ResearchMarketDataConfig())
        assert aligned is None

    def test_eth_intersection(self) -> None:
        btc_candles = [
            make_candle(datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(days=i), pair="BTC/USDT")
            for i in range(30)
        ]
        eth_candles = [
            make_candle(datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(days=i), pair="ETH/USDT")
            for i in range(30)
        ]
        cand_candles = [
            make_candle(datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(days=i), pair="SOL/USDT")
            for i in range(30)
        ]
        btc = make_series(btc_candles, pair="BTC/USDT")
        eth = make_series(eth_candles, pair="ETH/USDT")
        cand = make_series(cand_candles, pair="SOL/USDT")
        aligned = align_candidate(cand, btc, eth, ResearchMarketDataConfig())
        assert aligned is not None
        assert len(aligned.candles) == 30
