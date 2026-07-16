"""Tests for research_universe baseline builder (MVP-64 Stage 3)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from hunter.research_market_data.models import (
    CandleSeries,
    MarketDataSafetyFlags,
    MarketDataSourceRef,
    NormalizedCandle,
    ResearchMarketDataBundle,
    ResearchMarketDataConfig,
    ResearchMarketDataManifest,
)
from hunter.research_universe.baseline import build_baseline_universe
from hunter.research_universe.models import (
    EMPTY_BASELINE_UNIVERSE,
    ResearchUniverseConfig,
    SelectionWindow,
    UniversePairDecisionKind,
)


def _candle(
    timestamp: datetime,
    close: Decimal = Decimal("100"),
    volume: Decimal = Decimal("1000"),
    pair: str = "SOL/USDT",
) -> NormalizedCandle:
    return NormalizedCandle(
        timestamp=timestamp,
        open=close,
        high=close * Decimal("1.05"),
        low=close * Decimal("0.95"),
        close=close,
        volume=volume,
        pair=pair,
        timeframe="1d",
    )


def _series(
    pair: str = "SOL/USDT",
    close: Decimal = Decimal("100"),
    volume: Decimal = Decimal("1000"),
    start: datetime | None = None,
    n: int = 10,
) -> CandleSeries:
    if start is None:
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    candles = tuple(
        _candle(start + timedelta(days=i), close=close, volume=volume, pair=pair) for i in range(n)
    )
    return CandleSeries(
        pair=pair,
        timeframe="1d",
        candles=candles,
        source=MarketDataSourceRef(
            source_id=pair.replace("/", ""),
            path=Path("/tmp") / f"{pair.replace('/', '')}.csv",
            label=pair,
            row_count=n,
            file_hash="abc",
        ),
        coverage=Decimal("1.0"),
        coverage_threshold=Decimal("0.8"),
        missing_intervals=(),
        reason_codes=(),
        metadata={},
    )


def _bundle(candidates: tuple[CandleSeries, ...]) -> ResearchMarketDataBundle:
    btc = _series("BTC/USDT", Decimal("50000"), Decimal("100"))
    sources = tuple(s.source for s in (*candidates, btc))
    fingerprints = {s.source.source_id: s.source.file_hash for s in (*candidates, btc)}
    return ResearchMarketDataBundle(
        config=ResearchMarketDataConfig(),
        manifest=ResearchMarketDataManifest(
            schema_version="1.0",
            generated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            sources=sources,
            series_fingerprints=fingerprints,
            btc_fingerprint=btc.source.file_hash,
            eth_fingerprint=None,
            policy_fingerprint="policy",
            bundle_fingerprint="bundle",
            safety_flags=MarketDataSafetyFlags(),
            metadata={},
            reason_codes=(),
        ),
        candidates=candidates,
        btc_series=btc,
        eth_series=None,
        exclusions=(),
        safety_flags=MarketDataSafetyFlags(),
        reason_codes=(),
        metadata={},
    )


def _config() -> ResearchUniverseConfig:
    return ResearchUniverseConfig(
        selection_window=SelectionWindow(
            start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end=datetime(2024, 1, 10, tzinfo=timezone.utc),
        ),
        max_baseline_pairs=3,
    )


class TestBaselineBuilder:
    def test_top_volume_pairs_selected(self) -> None:
        a = _series("SOL/USDT", Decimal("100"), Decimal("1000"))  # avg 100k
        b = _series("BTC/USDT", Decimal("50000"), Decimal("100"))  # benchmark -> excluded
        c = _series("ETH/USDT", Decimal("3000"), Decimal("200"))  # benchmark -> excluded
        d = _series("ADA/USDT", Decimal("1"), Decimal("10000"))  # 10k
        e = _series("DOT/USDT", Decimal("10"), Decimal("5000"))  # 50k
        bundle = _bundle((a, b, c, d, e))
        result = build_baseline_universe(bundle, _config())
        # Expected order: SOL, DOT, ADA (BTC/ETH excluded as benchmarks)
        assert result.pairs == ("SOL/USDT", "DOT/USDT", "ADA/USDT")
        assert result.decisions[0].decision == UniversePairDecisionKind.INCLUDED
        assert result.decisions[0].rank == 1
        assert result.fingerprint
        assert len(result.fingerprint) == 64

    def test_empty_baseline_universe(self) -> None:
        # No non-benchmark, non-stable, non-leveraged candidates.
        btc = _series("BTC/USDT", Decimal("50000"), Decimal("100"))
        eth = _series("ETH/USDT", Decimal("3000"), Decimal("200"))
        bundle = _bundle((btc, eth))
        config = _config()
        result = build_baseline_universe(bundle, config)
        assert result.pairs == ()
        assert EMPTY_BASELINE_UNIVERSE in result.reason_codes

    def test_max_baseline_pairs_cap(self) -> None:
        a = _series("AAA/USDT", Decimal("10"), Decimal("10000"))
        b = _series("BBB/USDT", Decimal("9"), Decimal("10000"))
        c = _series("CCC/USDT", Decimal("8"), Decimal("10000"))
        d = _series("DDD/USDT", Decimal("7"), Decimal("10000"))
        bundle = _bundle((a, b, c, d))
        config = _config()
        result = build_baseline_universe(bundle, config)
        assert len(result.pairs) == 3
        assert result.pairs == ("AAA/USDT", "BBB/USDT", "CCC/USDT")

    def test_baseline_excludes_stablecoins_and_leveraged(self) -> None:
        a = _series("SOL/USDT", Decimal("100"), Decimal("1000"))
        stable = _series("USDC/USDT", Decimal("1"), Decimal("100000"))
        lev = _series("ETHUP/USDT", Decimal("10"), Decimal("1000"))
        bundle = _bundle((a, stable, lev))
        config = _config()
        result = build_baseline_universe(bundle, config)
        assert result.pairs == ("SOL/USDT",)
