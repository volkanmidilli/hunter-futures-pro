"""Tests for hunter.research_market_data.models."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from hunter.research_market_data.models import (
    CandleSeries,
    MarketDataFileSpec,
    MarketDataSafetyFlags,
    MarketDataSourceRef,
    MissingInterval,
    NormalizedCandle,
    RawCandleRow,
    ResearchMarketDataBundle,
    ResearchMarketDataConfig,
    ResearchMarketDataManifest,
)


class TestMarketDataSafetyFlags:
    def test_defaults_are_research_only(self) -> None:
        flags = MarketDataSafetyFlags()
        assert flags.research_only is True
        assert flags.execution_approval_granted is False
        assert flags.production_approval_granted is False
        assert flags.live_trading_allowed is False
        assert flags.automatic_execution_allowed is False

    @pytest.mark.parametrize(
        "field_name,value",
        [
            ("research_only", False),
            ("execution_approval_granted", True),
            ("production_approval_granted", True),
            ("live_trading_allowed", True),
            ("automatic_execution_allowed", True),
        ],
    )
    def test_invalid_safety_flag_raises(self, field_name: str, value: bool) -> None:
        with pytest.raises(ValueError, match=field_name):
            MarketDataSafetyFlags(**{field_name: value})


class TestResearchMarketDataConfig:
    def test_defaults(self) -> None:
        config = ResearchMarketDataConfig()
        assert config.coverage_threshold == Decimal("0.98")
        assert config.min_required_rows == 30
        assert config.lookback_days == (7, 14, 30)
        assert config.required_quote_currency == "USDT"

    def test_coverage_threshold_must_be_decimal_between_zero_and_one(self) -> None:
        with pytest.raises(ValueError):
            ResearchMarketDataConfig(coverage_threshold=Decimal("1.5"))
        with pytest.raises(ValueError):
            ResearchMarketDataConfig(coverage_threshold=Decimal("-0.1"))

    def test_min_required_rows_at_least_two(self) -> None:
        with pytest.raises(ValueError):
            ResearchMarketDataConfig(min_required_rows=1)
        with pytest.raises(ValueError):
            ResearchMarketDataConfig(min_required_rows=0)

    def test_lookback_days_positive(self) -> None:
        with pytest.raises(ValueError):
            ResearchMarketDataConfig(lookback_days=(0, 14, 30))


class TestMarketDataFileSpec:
    def test_path_string_coerced(self) -> None:
        spec = MarketDataFileSpec(path="tests/fixtures/sample.csv")
        assert isinstance(spec.path, Path)

    def test_expected_symbol_validation(self) -> None:
        with pytest.raises(ValueError):
            MarketDataFileSpec(path="x.csv", expected_symbol="")


class TestMarketDataSourceRef:
    def test_basic(self) -> None:
        ref = MarketDataSourceRef(
            source_id="id-1",
            path=Path("x.csv"),
            label="x",
            row_count=10,
            file_hash="abc",
        )
        assert ref.row_count == 10


class TestRawCandleRow:
    def test_basic(self) -> None:
        source = MarketDataSourceRef(
            source_id="id-1",
            path=Path("x.csv"),
            label="x",
            row_count=10,
            file_hash="abc",
        )
        row = RawCandleRow(
            source=source,
            line_number=2,
            timestamp_raw="2024-01-01",
            open_raw="1",
            high_raw="2",
            low_raw="3",
            close_raw="4",
            volume_raw="5",
        )
        assert row.line_number == 2


class TestNormalizedCandle:
    def test_basic(self) -> None:
        candle = NormalizedCandle(
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            open=Decimal("1"),
            high=Decimal("2"),
            low=Decimal("1"),
            close=Decimal("1.5"),
            volume=Decimal("100"),
            pair="BTC/USDT",
            timeframe="1d",
        )
        assert candle.close == Decimal("1.5")

    def test_rejects_naive_timestamp(self) -> None:
        with pytest.raises(ValueError, match="timezone-aware"):
            NormalizedCandle(
                timestamp=datetime(2024, 1, 1),
                open=Decimal("1"),
                high=Decimal("2"),
                low=Decimal("1"),
                close=Decimal("1.5"),
                volume=Decimal("100"),
                pair="BTC/USDT",
                timeframe="1d",
            )

    def test_rejects_zero_price(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            NormalizedCandle(
                timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
                open=Decimal("0"),
                high=Decimal("2"),
                low=Decimal("1"),
                close=Decimal("1.5"),
                volume=Decimal("100"),
                pair="BTC/USDT",
                timeframe="1d",
            )

    def test_rejects_invalid_high_low(self) -> None:
        with pytest.raises(ValueError, match="high"):
            NormalizedCandle(
                timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
                open=Decimal("1"),
                high=Decimal("0.5"),
                low=Decimal("1"),
                close=Decimal("1.5"),
                volume=Decimal("100"),
                pair="BTC/USDT",
                timeframe="1d",
            )


class TestCandleSeries:
    def test_pair_mismatch(self) -> None:
        source = MarketDataSourceRef(
            source_id="id-1",
            path=Path("x.csv"),
            label="x",
            row_count=1,
            file_hash="abc",
        )
        candle = NormalizedCandle(
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            open=Decimal("1"),
            high=Decimal("2"),
            low=Decimal("1"),
            close=Decimal("1.5"),
            volume=Decimal("100"),
            pair="BTC/USDT",
            timeframe="1d",
        )
        with pytest.raises(ValueError, match="pair"):
            CandleSeries(
                pair="ETH/USDT",
                timeframe="1d",
                candles=(candle,),
                source=source,
                coverage=Decimal("1"),
                coverage_threshold=Decimal("0.98"),
                missing_intervals=(),
                reason_codes=(),
                metadata={},
            )


class TestMissingInterval:
    def test_basic(self) -> None:
        mi = MissingInterval(
            start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end=datetime(2024, 1, 2, tzinfo=timezone.utc),
            expected_count=2,
            actual_count=1,
            reason_code="GAPS_FOUND",
        )
        assert mi.expected_count == 2


class TestManifestAndBundle:
    def test_manifest_basic(self) -> None:
        source = MarketDataSourceRef(
            source_id="id-1",
            path=Path("x.csv"),
            label="x",
            row_count=1,
            file_hash="abc",
        )
        candle = NormalizedCandle(
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            open=Decimal("1"),
            high=Decimal("2"),
            low=Decimal("1"),
            close=Decimal("1.5"),
            volume=Decimal("100"),
            pair="BTC/USDT",
            timeframe="1d",
        )
        series = CandleSeries(
            pair="BTC/USDT",
            timeframe="1d",
            candles=(candle,),
            source=source,
            coverage=Decimal("1"),
            coverage_threshold=Decimal("0.98"),
            missing_intervals=(),
            reason_codes=(),
            metadata={},
        )
        manifest = ResearchMarketDataManifest(
            schema_version="0.63.0-dev",
            generated_at=datetime.now(timezone.utc),
            sources=(source,),
            series_fingerprints={"BTC/USDT": "fp"},
            btc_fingerprint="btc-fp",
            eth_fingerprint=None,
            policy_fingerprint="policy-fp",
            bundle_fingerprint="bundle-fp",
            safety_flags=MarketDataSafetyFlags(),
            metadata={},
            reason_codes=(),
        )
        bundle = ResearchMarketDataBundle(
            config=ResearchMarketDataConfig(),
            manifest=manifest,
            candidates=(series,),
            btc_series=series,
            eth_series=None,
            exclusions=(),
            safety_flags=MarketDataSafetyFlags(),
            reason_codes=(),
            metadata={},
        )
        assert bundle.btc_series.pair == "BTC/USDT"
