"""Tests for hunter.research_market_data.validator."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from hunter.research_market_data.errors import ResearchMarketDataValidationError
from hunter.research_market_data.models import (
    MarketDataSourceRef,
    RawCandleRow,
)
from hunter.research_market_data.validator import (
    _parse_decimal,
    _parse_timestamp,
    build_normalized_candles,
    detect_timeframe,
)


def make_row(
    timestamp_raw: str = "2024-01-01T00:00:00+00:00",
    open_raw: str = "100",
    high_raw: str = "110",
    low_raw: str = "90",
    close_raw: str = "105",
    volume_raw: str = "1000",
    line_number: int = 2,
) -> RawCandleRow:
    source = MarketDataSourceRef(
        source_id="id",
        path=__import__("pathlib").Path("x.csv"),
        label="x",
        row_count=1,
        file_hash="abc",
    )
    return RawCandleRow(
        source=source,
        line_number=line_number,
        timestamp_raw=timestamp_raw,
        open_raw=open_raw,
        high_raw=high_raw,
        low_raw=low_raw,
        close_raw=close_raw,
        volume_raw=volume_raw,
    )


class TestParseTimestamp:
    def test_unix_seconds(self) -> None:
        ts = "1704067200"  # 2024-01-01T00:00:00Z
        dt = _parse_timestamp(ts)
        assert dt == datetime(2024, 1, 1, tzinfo=timezone.utc)

    def test_unix_milliseconds(self) -> None:
        ts = "1704067200000"
        dt = _parse_timestamp(ts)
        assert dt == datetime(2024, 1, 1, tzinfo=timezone.utc)

    def test_iso_utc(self) -> None:
        dt = _parse_timestamp("2024-01-01T00:00:00+00:00")
        assert dt == datetime(2024, 1, 1, tzinfo=timezone.utc)

    def test_iso_offset_normalized_to_utc(self) -> None:
        dt = _parse_timestamp("2024-01-01T03:00:00+03:00")
        assert dt == datetime(2024, 1, 1, tzinfo=timezone.utc)

    def test_naive_datetime_rejected(self) -> None:
        with pytest.raises(ResearchMarketDataValidationError) as exc:
            _parse_timestamp("2024-01-01T00:00:00")
        assert exc.value.reason_code == "NAIVE_TIMESTAMP"

    def test_invalid_timestamp_rejected(self) -> None:
        with pytest.raises(ResearchMarketDataValidationError) as exc:
            _parse_timestamp("not-a-date")
        assert exc.value.reason_code == "TIMESTAMP_PARSE_ERROR"


class TestParseDecimal:
    def test_valid_decimal(self) -> None:
        assert _parse_decimal("123.45", "x") == Decimal("123.45")

    def test_empty_rejected(self) -> None:
        with pytest.raises(ResearchMarketDataValidationError) as exc:
            _parse_decimal("", "x")
        assert exc.value.reason_code == "INVALID_NUMERIC"

    def test_nan_rejected(self) -> None:
        with pytest.raises(ResearchMarketDataValidationError) as exc:
            _parse_decimal("NaN", "x")
        assert exc.value.reason_code == "NON_FINITE_VALUE"

    def test_infinity_rejected(self) -> None:
        with pytest.raises(ResearchMarketDataValidationError) as exc:
            _parse_decimal("Infinity", "x")
        assert exc.value.reason_code == "NON_FINITE_VALUE"


class TestBuildNormalizedCandles:
    def test_basic(self) -> None:
        rows = [make_row("2024-01-01T00:00:00+00:00"), make_row("2024-01-02T00:00:00+00:00")]
        candles = build_normalized_candles(rows, "BTC/USDT")
        assert len(candles) == 2
        assert candles[0].timestamp < candles[1].timestamp
        assert candles[0].pair == "BTC/USDT"
        assert candles[0].quote_volume == Decimal("105000")

    def test_out_of_order_sorted(self) -> None:
        rows = [make_row("2024-01-02T00:00:00+00:00"), make_row("2024-01-01T00:00:00+00:00")]
        candles = build_normalized_candles(rows, "BTC/USDT")
        assert candles[0].timestamp == datetime(2024, 1, 1, tzinfo=timezone.utc)

    def test_duplicate_timestamp_rejected(self) -> None:
        rows = [make_row("2024-01-01T00:00:00+00:00"), make_row("2024-01-01T00:00:00+00:00")]
        with pytest.raises(ResearchMarketDataValidationError) as exc:
            build_normalized_candles(rows, "BTC/USDT")
        assert exc.value.reason_code == "DUPLICATE_TIMESTAMP"

    def test_invalid_ohlc_rejected(self) -> None:
        rows = [make_row(high_raw="95")]
        with pytest.raises(ResearchMarketDataValidationError) as exc:
            build_normalized_candles(rows, "BTC/USDT")
        assert exc.value.reason_code == "INVALID_OHLC_RELATION"

    def test_zero_close_rejected(self) -> None:
        rows = [make_row(close_raw="0")]
        with pytest.raises(ResearchMarketDataValidationError) as exc:
            build_normalized_candles(rows, "BTC/USDT")
        assert exc.value.reason_code == "NEGATIVE_OR_ZERO_PRICE"


class TestDetectTimeframe:
    def test_daily(self) -> None:
        source = make_row().source
        candles = []
        for i in range(3):
            candles.append(
                build_normalized_candles([make_row(f"2024-01-{1 + i:02d}T00:00:00+00:00")], "BTC/USDT")[0]
            )
        assert detect_timeframe(candles) == "1d"

    def test_unknown_single_candle(self) -> None:
        candle = build_normalized_candles([make_row()], "BTC/USDT")[0]
        assert detect_timeframe([candle]) == "unknown"
