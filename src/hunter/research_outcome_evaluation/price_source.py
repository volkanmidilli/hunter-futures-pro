"""Feather price-series source for SPEC-076 outcome evaluation.

Discovery reuses the existing SPEC-075 contract verbatim
(:func:`hunter.pairlist_export.feather_adapter.discover_feather_files`):
``BASE_USDT_USDT-1h-futures.feather`` under a read-only ``--data-dir``.

Series loading is self-contained (no private SPEC-075 imports) and requires
the full OHLCV column set so MAE/MFE can use intra-window 1h lows/highs.
Per-candle validity follows the SPEC-075 price-validation contract:
``open``/``high``/``low``/``close`` finite and > 0, ``volume`` finite and
>= 0, timestamps unique.  Read-only: source Feather files are never
modified, renamed, or deleted.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pyarrow as pa

from hunter.pairlist_export.feather_adapter import discover_feather_files
from hunter.research_outcome_evaluation.errors import PriceSourceError

REQUIRED_OHLCV_COLUMNS: tuple[str, ...] = ("date", "open", "high", "low", "close", "volume")


@dataclass(frozen=True)
class Candle:
    """One validated hourly candle. ``valid`` follows the SPEC-075 contract."""

    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    valid: bool


@dataclass(frozen=True)
class PriceSeries:
    """A loaded price series: candles sorted ascending by timestamp."""

    pair: str
    candles: tuple[Candle, ...]

    def by_open_time(self) -> dict[datetime, Candle]:
        """Index candles by open time; the last duplicate wins as invalid."""
        result: dict[datetime, Candle] = {}
        for candle in self.candles:
            result[candle.timestamp] = candle
        return result


def build_price_source_map(data_dir: Path) -> dict[str, Path]:
    """Map ``BASE/USDT:USDT`` -> Feather path for every discovered file.

    Includes the BTC benchmark and ETH references separated by SPEC-075
    discovery so a cohort selecting BTC or ETH still resolves its source.
    """
    data_dir = Path(data_dir)
    if not data_dir.is_dir():
        raise PriceSourceError(f"data-dir does not exist or is not a directory: {data_dir}")
    discovery = discover_feather_files(data_dir)
    mapping: dict[str, Path] = {}
    for ref in discovery.included:
        mapping[ref.pair] = ref.path
    for ref in (discovery.btc_ref, discovery.eth_ref):
        if ref is not None:
            mapping[ref.pair] = ref.path
    return mapping


def _is_valid_ohlcv(o: float, h: float, l: float, c: float, v: float) -> bool:  # noqa: E741
    values = (o, h, l, c)
    if not all(math.isfinite(x) and x > 0 for x in values):
        return False
    return math.isfinite(v) and v >= 0


def load_price_series(path: Path, pair: str, now: datetime) -> PriceSeries:
    """Load one Feather file into a validated, time-sorted :class:`PriceSeries`.

    Candles dated after ``now`` are marked invalid (they cannot be completed
    yet).  Duplicate timestamps are marked invalid (first occurrence kept
    valid per SPEC-075 duplicate detection semantics).
    """
    path = Path(path)
    try:
        schema_names = set(pa.ipc.open_file(str(path)).schema.names)
        missing = [c for c in REQUIRED_OHLCV_COLUMNS if c not in schema_names]
        if missing:
            raise PriceSourceError(f"missing required column(s) {missing} in {path}")
        table = pa.ipc.open_file(str(path)).read_all().select(list(REQUIRED_OHLCV_COLUMNS))
    except PriceSourceError:
        raise
    except Exception as exc:
        raise PriceSourceError(f"unreadable feather file: {path}: {exc}") from exc

    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    dates = table.column("date").to_pylist()
    opens = table.column("open").to_pylist()
    highs = table.column("high").to_pylist()
    lows = table.column("low").to_pylist()
    closes = table.column("close").to_pylist()
    volumes = table.column("volume").to_pylist()

    candles: list[Candle] = []
    seen: set[datetime] = set()
    for raw_ts, o, h, l, c, v in zip(dates, opens, highs, lows, closes, volumes):  # noqa: E741
        ts = _normalize_ts(raw_ts)
        duplicate = ts in seen
        seen.add(ts)
        try:
            values = (float(o), float(h), float(l), float(c), float(v))
        except (TypeError, ValueError):
            candles.append(Candle(ts, math.nan, math.nan, math.nan, math.nan, math.nan, False))
            continue
        valid = (
            not duplicate
            and ts <= now
            and _is_valid_ohlcv(*values)
        )
        candles.append(Candle(ts, *values, valid))

    candles.sort(key=lambda candle: candle.timestamp)
    return PriceSeries(pair=pair, candles=tuple(candles))


def _normalize_ts(raw_ts: object) -> datetime:
    if isinstance(raw_ts, datetime):
        ts = raw_ts
        return ts if ts.tzinfo is not None else ts.replace(tzinfo=timezone.utc)
    # Numeric epoch milliseconds (SPEC-075 fallback).
    return datetime.fromtimestamp(float(raw_ts) / 1000.0, tz=timezone.utc)  # type: ignore[arg-type]
