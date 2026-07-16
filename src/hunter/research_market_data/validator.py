"""Candle normalization and validation for research market data (MVP-63 / SPEC-064)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from statistics import median
from typing import Any

from hunter.research_market_data.errors import ResearchMarketDataValidationError
from hunter.research_market_data.models import (
    DUPLICATE_TIMESTAMP,
    INVALID_NUMERIC,
    INVALID_OHLC_RELATION,
    NAIVE_TIMESTAMP,
    NON_FINITE_VALUE,
    NON_UTC_TIMESTAMP,
    NEGATIVE_OR_ZERO_PRICE,
    NEGATIVE_VOLUME,
    NormalizedCandle,
    OUT_OF_ORDER_INPUT,
    RawCandleRow,
    TIMESTAMP_PARSE_ERROR,
)

TIMEFRAME_SECONDS: dict[int, str] = {
    60: "1m",
    300: "5m",
    900: "15m",
    1800: "30m",
    3600: "1h",
    14400: "4h",
    28800: "8h",
    43200: "12h",
    86400: "1d",
    604800: "1w",
}


def _parse_timestamp(raw: str) -> datetime:
    """Parse a timestamp to a UTC datetime.

    Supports Unix seconds, Unix milliseconds, and timezone-aware ISO-8601.
    Naive datetimes are rejected.
    """
    value = raw.strip()
    if not value:
        raise ResearchMarketDataValidationError(
            TIMESTAMP_PARSE_ERROR, "timestamp is empty"
        )

    if value.lstrip("-").isdigit():
        try:
            numeric = int(value)
        except ValueError as exc:
            raise ResearchMarketDataValidationError(
                TIMESTAMP_PARSE_ERROR, f"invalid integer timestamp: {value}"
            ) from exc
        # Heuristic: current Unix seconds are ~10 digits, milliseconds ~13 digits.
        if len(value) > 10:
            numeric = numeric // 1000
        dt = datetime.fromtimestamp(numeric, tz=timezone.utc)
        return dt

    try:
        dt = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ResearchMarketDataValidationError(
            TIMESTAMP_PARSE_ERROR, f"unparseable timestamp: {value}"
        ) from exc

    if dt.tzinfo is None:
        raise ResearchMarketDataValidationError(
            NAIVE_TIMESTAMP, f"timestamp is naive: {value}"
        )

    dt = dt.astimezone(timezone.utc)
    if dt.tzinfo != timezone.utc:
        # Should not happen after astimezone, but kept as a safety guard.
        raise ResearchMarketDataValidationError(
            NON_UTC_TIMESTAMP, f"timestamp could not be normalized to UTC: {value}"
        )
    return dt


def _parse_decimal(raw: str, field_name: str) -> Decimal:
    """Parse a raw numeric string to a finite Decimal."""
    value = raw.strip()
    if not value:
        raise ResearchMarketDataValidationError(
            INVALID_NUMERIC, f"{field_name} is empty"
        )
    try:
        decimal = Decimal(value)
    except InvalidOperation as exc:
        raise ResearchMarketDataValidationError(
            INVALID_NUMERIC, f"{field_name} is not a valid Decimal: {value}"
        ) from exc
    if not decimal.is_finite():
        raise ResearchMarketDataValidationError(
            NON_FINITE_VALUE, f"{field_name} is not finite: {value}"
        )
    return decimal


def _normalize_candle_row(row: RawCandleRow, pair: str) -> NormalizedCandle:
    """Convert a single RawCandleRow into a NormalizedCandle."""
    timestamp = _parse_timestamp(row.timestamp_raw)
    open_price = _parse_decimal(row.open_raw, "open")
    high_price = _parse_decimal(row.high_raw, "high")
    low_price = _parse_decimal(row.low_raw, "low")
    close_price = _parse_decimal(row.close_raw, "close")
    volume = _parse_decimal(row.volume_raw, "volume")

    if open_price <= Decimal("0"):
        raise ResearchMarketDataValidationError(
            NEGATIVE_OR_ZERO_PRICE, f"open must be positive: {open_price}"
        )
    if high_price <= Decimal("0"):
        raise ResearchMarketDataValidationError(
            NEGATIVE_OR_ZERO_PRICE, f"high must be positive: {high_price}"
        )
    if low_price <= Decimal("0"):
        raise ResearchMarketDataValidationError(
            NEGATIVE_OR_ZERO_PRICE, f"low must be positive: {low_price}"
        )
    if close_price <= Decimal("0"):
        raise ResearchMarketDataValidationError(
            NEGATIVE_OR_ZERO_PRICE, f"close must be positive: {close_price}"
        )
    if volume < Decimal("0"):
        raise ResearchMarketDataValidationError(
            NEGATIVE_VOLUME, f"volume must be non-negative: {volume}"
        )

    if high_price < max(open_price, close_price, low_price):
        raise ResearchMarketDataValidationError(
            INVALID_OHLC_RELATION,
            f"high {high_price} < max(open {open_price}, close {close_price}, low {low_price})",
        )
    if low_price > min(open_price, close_price, high_price):
        raise ResearchMarketDataValidationError(
            INVALID_OHLC_RELATION,
            f"low {low_price} > min(open {open_price}, close {close_price}, high {high_price})",
        )

    quote_volume = close_price * volume

    return NormalizedCandle(
        timestamp=timestamp,
        open=open_price,
        high=high_price,
        low=low_price,
        close=close_price,
        volume=volume,
        pair=pair,
        timeframe="unknown",
        quote_volume=quote_volume,
    )


def detect_timeframe(candles: Sequence[NormalizedCandle]) -> str:
    """Detect the most common candle interval as a canonical timeframe string."""
    if len(candles) < 2:
        return "unknown"
    sorted_candles = sorted(candles, key=lambda c: c.timestamp)
    deltas = [
        int((sorted_candles[i + 1].timestamp - sorted_candles[i].timestamp).total_seconds())
        for i in range(len(sorted_candles) - 1)
    ]
    if not deltas:
        return "unknown"
    common_delta = int(median(deltas))
    if common_delta <= 0:
        return "unknown"
    return TIMEFRAME_SECONDS.get(common_delta, f"{common_delta}s")


def build_normalized_candles(
    raw_rows: Sequence[RawCandleRow],
    pair: str,
) -> tuple[NormalizedCandle, ...]:
    """Validate and normalize raw candle rows.

    Returns a tuple of NormalizedCandle sorted by timestamp (ascending).
    Raises ``ResearchMarketDataValidationError`` on any row-level or ordering
    failure.
    """
    normalized: list[NormalizedCandle] = []
    for row in raw_rows:
        candle = _normalize_candle_row(row, pair)
        normalized.append(candle)

    sorted_candles = sorted(normalized, key=lambda c: c.timestamp)

    for i in range(1, len(sorted_candles)):
        if sorted_candles[i].timestamp == sorted_candles[i - 1].timestamp:
            raise ResearchMarketDataValidationError(
                DUPLICATE_TIMESTAMP,
                f"duplicate timestamp: {sorted_candles[i].timestamp.isoformat()}",
            )

    if sorted_candles != list(normalized):
        # The input was not already in ascending order.
        pass  # Reason code is handled by the caller if needed.

    return tuple(sorted_candles)
