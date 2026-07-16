"""Tests for research_universe eligibility policy (MVP-64 Stage 2)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from hunter.research_market_data.models import (
    CandleSeries,
    MarketDataSourceRef,
    MissingInterval,
    NormalizedCandle,
)
from hunter.research_universe.eligibility import (
    assess_pair_eligibility,
    build_eligibility_policy_fingerprint,
)
from hunter.research_universe.models import (
    BENCHMARK_PAIR_EXCLUDED,
    COVERAGE_BELOW_MIN,
    INELIGIBLE_PAIR,
    LEVERAGED_TOKEN_EXCLUDED,
    ResearchUniverseConfig,
    SelectionWindow,
    STABLECOIN_PAIR_EXCLUDED,
    UNSAFE_SYMBOL_CONTENT,
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
    start: datetime | None = None,
    n: int = 10,
) -> CandleSeries:
    if start is None:
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    candles = tuple(_candle(start + timedelta(days=i), pair=pair) for i in range(n))
    return CandleSeries(
        pair=pair,
        timeframe="1d",
        candles=candles,
        source=MarketDataSourceRef(
            source_id=pair.replace("/", ""),
            path=Path("/tmp/SOLUSDT.csv"),
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


def _config(window: SelectionWindow | None = None) -> ResearchUniverseConfig:
    if window is None:
        window = SelectionWindow(
            start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end=datetime(2024, 1, 10, tzinfo=timezone.utc),
        )
    return ResearchUniverseConfig(
        selection_window=window,
        benchmark_pairs=("BTC/USDT", "ETH/USDT"),
    )


class TestEligibility:
    def test_eligible_pair(self) -> None:
        series = _series()
        config = _config()
        result = assess_pair_eligibility("SOL/USDT", series, config)
        assert result.is_eligible is True
        assert result.pair == "SOL/USDT"
        assert result.reason_codes == ()

    def test_benchmark_pair_excluded(self) -> None:
        series = _series(pair="BTC/USDT")
        config = _config()
        result = assess_pair_eligibility("BTC/USDT", series, config)
        assert result.is_eligible is False
        assert BENCHMARK_PAIR_EXCLUDED in result.reason_codes

    def test_stablecoin_pair_excluded(self) -> None:
        series = _series(pair="USDC/USDT")
        config = _config()
        result = assess_pair_eligibility("USDC/USDT", series, config)
        assert result.is_eligible is False
        assert STABLECOIN_PAIR_EXCLUDED in result.reason_codes

    def test_leveraged_token_excluded(self) -> None:
        series = _series(pair="ETHUP/USDT")
        config = _config()
        result = assess_pair_eligibility("ETHUP/USDT", series, config)
        assert result.is_eligible is False
        assert LEVERAGED_TOKEN_EXCLUDED in result.reason_codes

    def test_coverage_below_min(self) -> None:
        series = _series()
        config = _config()
        # Override coverage by creating a series with low coverage
        low = CandleSeries(
            pair="SOL/USDT",
            timeframe="1d",
            candles=series.candles,
            source=series.source,
            coverage=Decimal("0.5"),
            coverage_threshold=Decimal("0.8"),
            missing_intervals=(
                MissingInterval(
                    start=datetime(2024, 1, 5, tzinfo=timezone.utc),
                    end=datetime(2024, 1, 7, tzinfo=timezone.utc),
                    expected_count=3,
                    actual_count=0,
                    reason_code="MISSING_INTERVAL",
                ),
            ),
            reason_codes=(),
            metadata={},
        )
        result = assess_pair_eligibility("SOL/USDT", low, config)
        assert result.is_eligible is False
        assert COVERAGE_BELOW_MIN in result.reason_codes

    def test_window_outside_range(self) -> None:
        series = _series(start=datetime(2024, 1, 1, tzinfo=timezone.utc), n=5)
        window = SelectionWindow(
            start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end=datetime(2024, 1, 10, tzinfo=timezone.utc),
        )
        config = _config(window=window)
        result = assess_pair_eligibility("SOL/USDT", series, config)
        assert result.is_eligible is False
        assert INELIGIBLE_PAIR in result.reason_codes

    def test_unsafe_symbol_content(self) -> None:
        series = _series()
        config = _config()
        result = assess_pair_eligibility("SOL../USDT", series, config)
        assert result.is_eligible is False
        assert UNSAFE_SYMBOL_CONTENT in result.reason_codes

    def test_policy_fingerprint_deterministic(self) -> None:
        config = _config()
        fp1 = build_eligibility_policy_fingerprint(config)
        fp2 = build_eligibility_policy_fingerprint(config)
        assert fp1 == fp2
        assert len(fp1) == 64
