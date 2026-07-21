"""Synthetic Feather fixture builders for SPEC-075 tests.

Not a test module itself (no ``test_`` prefix, not collected by pytest).
Every builder writes exactly the schema real Freqtrade 1h-futures Feather
files use: ``date`` (tz-aware UTC datetime64), ``open/high/low/close/volume``
(float64) -- verified against a real Freqtrade-produced fixture at
``freqtrade strategy/freqtrade_src/tests/testdata/futures/XRP_USDT_USDT-1h-futures.feather``.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

HOUR = timedelta(hours=1)


def hourly_range(as_of: date, days_back: int, days_forward_exclusive: int = 0) -> list[datetime]:
    """Return hourly UTC timestamps covering ``[as_of - days_back, as_of + days_forward_exclusive)``."""
    start = datetime.combine(as_of - timedelta(days=days_back), datetime.min.time(), tzinfo=timezone.utc)
    end = datetime.combine(as_of + timedelta(days=days_forward_exclusive), datetime.min.time(), tzinfo=timezone.utc)
    out = []
    cur = start
    while cur < end:
        out.append(cur)
        cur += HOUR
    return out


def build_dataframe(
    timestamps: list[datetime],
    *,
    base_close: float = 100.0,
    base_volume: float = 1000.0,
    close_step: float = 0.0,
) -> pd.DataFrame:
    """Build a synthetic OHLCV dataframe with deterministic, gently-varying values."""
    closes = [base_close + close_step * i for i in range(len(timestamps))]
    return pd.DataFrame(
        {
            "date": pd.to_datetime(pd.Series(timestamps), utc=True),
            "open": closes,
            "high": [c * 1.001 for c in closes],
            "low": [c * 0.999 for c in closes],
            "close": closes,
            "volume": [base_volume for _ in timestamps],
        }
    )


def write_feather(data_dir: Path, base_symbol: str, df: pd.DataFrame) -> Path:
    """Write ``df`` as ``{base_symbol}_USDT_USDT-1h-futures.feather`` under ``data_dir``."""
    path = data_dir / f"{base_symbol}_USDT_USDT-1h-futures.feather"
    df.reset_index(drop=True).to_feather(path)
    return path


def write_full_history_pair(
    data_dir: Path,
    base_symbol: str,
    as_of: date,
    *,
    base_close: float = 100.0,
    base_volume: float = 1000.0,
    close_step: float = 0.0,
    days_back: int = 90,
) -> Path:
    """Write a pair with full completed hourly coverage over ``[as_of - days_back, as_of)``."""
    timestamps = hourly_range(as_of, days_back)
    df = build_dataframe(timestamps, base_close=base_close, base_volume=base_volume, close_step=close_step)
    return write_feather(data_dir, base_symbol, df)
