"""Deterministic SHA-256 fingerprints for research market data (MVP-63 / SPEC-064)."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from hunter.research_market_data.models import (
    CandleSeries,
    ResearchMarketDataConfig,
)


def _canonical_decimal(value: Decimal) -> str:
    """Return a deterministic, non-scientific string for a Decimal."""
    return format(value, "f")


def _canonical_candle_str(candle: Any) -> str:
    """Return a canonical string for a single normalized candle."""
    ts = candle.timestamp.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    return (
        f"{ts}|"
        f"{_canonical_decimal(candle.open)}|"
        f"{_canonical_decimal(candle.high)}|"
        f"{_canonical_decimal(candle.low)}|"
        f"{_canonical_decimal(candle.close)}|"
        f"{_canonical_decimal(candle.volume)}"
    )


def _sha256(value: str) -> str:
    """Return the SHA-256 hex digest of a string."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def series_fingerprint(
    series: CandleSeries,
    schema_version: str,
) -> str:
    """Return the deterministic fingerprint of a ``CandleSeries``."""
    parts = [schema_version, series.pair, series.timeframe]
    for candle in series.candles:
        parts.append(_canonical_candle_str(candle))
    return _sha256("\n".join(parts))


def policy_fingerprint(config: ResearchMarketDataConfig) -> str:
    """Return the deterministic fingerprint of a research market data config."""
    parts = [
        str(config.coverage_threshold),
        str(config.min_required_rows),
        ",".join(str(d) for d in sorted(config.lookback_days)),
        config.required_quote_currency,
        str(config.safety_flags.research_only),
        str(config.safety_flags.execution_approval_granted),
        str(config.safety_flags.production_approval_granted),
        str(config.safety_flags.live_trading_allowed),
        str(config.safety_flags.automatic_execution_allowed),
    ]
    return _sha256("|".join(parts))


def bundle_fingerprint(
    *,
    schema_version: str,
    series_fingerprints: Mapping[str, str],
    btc_fingerprint: str,
    eth_fingerprint: str | None,
    policy_fingerprint: str,
) -> str:
    """Return the deterministic fingerprint of a research market data bundle."""
    parts = [schema_version]
    for pair in sorted(series_fingerprints):
        parts.append(f"{pair}:{series_fingerprints[pair]}")
    parts.append(f"btc:{btc_fingerprint}")
    if eth_fingerprint is not None:
        parts.append(f"eth:{eth_fingerprint}")
    else:
        parts.append("eth:none")
    parts.append(f"policy:{policy_fingerprint}")
    return _sha256("\n".join(parts))
