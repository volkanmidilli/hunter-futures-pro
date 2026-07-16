"""Tests for hunter.research_market_data.adapters."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from hunter.discovery.models import (
    DiscoveryConfig,
    DiscoveryInputKind,
    DiscoveryRelativeStrengthSummary,
)
from hunter.discovery.engine import build_discovery_report
from hunter.relative_strength.engine import build_relative_strength_report
from hunter.relative_strength.models import RelativeStrengthInput
from hunter.research_market_data.models import MarketDataSafetyFlags
from hunter.research_market_data.adapters import (
    build_discovery_input_bundle,
    build_relative_strength_run_inputs,
    candle_series_to_ohlcv_rows,
    discovery_summaries_to_inputs,
    relative_strength_report_to_discovery_summaries,
)
from hunter.research_market_data.aligner import build_candle_series
from hunter.research_market_data.models import (
    CandleSeries,
    MarketDataSourceRef,
    NormalizedCandle,
    ResearchMarketDataBundle,
    ResearchMarketDataConfig,
    ResearchMarketDataManifest,
)
from hunter.research_market_data.validator import build_normalized_candles


def make_source(path: Path, row_count: int = 1) -> MarketDataSourceRef:
    return MarketDataSourceRef(
        source_id=f"{path.name}:hash",
        path=path,
        label=path.name,
        row_count=row_count,
        file_hash="hash",
    )


def make_candles(
    pair: str,
    start: datetime,
    n: int,
    open: Decimal = Decimal("100"),
    daily_return: Decimal = Decimal("0.001"),
) -> tuple[NormalizedCandle, ...]:
    candles = []
    close = open
    for i in range(n):
        high = close * Decimal("1.05")
        low = close * Decimal("0.95")
        candle = NormalizedCandle(
            timestamp=start + timedelta(days=i),
            open=close,
            high=high,
            low=low,
            close=close,
            volume=Decimal("1000"),
            pair=pair,
            timeframe="1d",
        )
        candles.append(candle)
        close = close * (Decimal("1") + daily_return)
    return tuple(candles)


class TestCandleSeriesToOhlcvRows:
    def test_conversion(self, tmp_path: Path) -> None:
        candles = make_candles("BTC/USDT", datetime(2024, 1, 1, tzinfo=timezone.utc), 3)
        series = build_candle_series(
            source=make_source(tmp_path / "x.csv", 3),
            candles=candles,
            config=ResearchMarketDataConfig(),
            pair="BTC/USDT",
        )
        rows = candle_series_to_ohlcv_rows(series)
        assert len(rows) == 3
        assert rows[0].close == Decimal("100")
        assert rows[0].timestamp == datetime(2024, 1, 1, tzinfo=timezone.utc)


class TestBuildRelativeStrengthRunInputs:
    def test_from_bundle(self, tmp_path: Path) -> None:
        btc_candles = make_candles("BTC/USDT", datetime(2024, 1, 1, tzinfo=timezone.utc), 35)
        cand_candles = make_candles(
            "SOL/USDT",
            datetime(2024, 1, 1, tzinfo=timezone.utc),
            35,
            open=Decimal("10"),
            daily_return=Decimal("0.02"),
        )
        btc = build_candle_series(
            source=make_source(tmp_path / "btc.csv", 35),
            candles=btc_candles,
            config=ResearchMarketDataConfig(),
            pair="BTC/USDT",
        )
        cand = build_candle_series(
            source=make_source(tmp_path / "sol.csv", 35),
            candles=cand_candles,
            config=ResearchMarketDataConfig(),
            pair="SOL/USDT",
        )
        manifest = ResearchMarketDataManifest(
            schema_version="0.63.0-dev",
            generated_at=datetime.now(timezone.utc),
            sources=(btc.source, cand.source),
            series_fingerprints={"BTC/USDT": "btc-fp", "SOL/USDT": "sol-fp"},
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
            candidates=(cand,),
            btc_series=btc,
            eth_series=None,
            exclusions=(),
            safety_flags=MarketDataSafetyFlags(),
            reason_codes=(),
            metadata={},
        )
        inputs = build_relative_strength_run_inputs(bundle)
        assert len(inputs.candidates) == 1
        assert inputs.candidates[0].symbol == "SOL/USDT"
        assert len(inputs.btc) == 35
        assert inputs.eth is None


class TestRelativeStrengthReportToDiscoverySummaries:
    def test_mapping(self, tmp_path: Path) -> None:
        btc_candles = make_candles("BTC/USDT", datetime(2024, 1, 1, tzinfo=timezone.utc), 35)
        cand_candles = make_candles(
            "SOL/USDT",
            datetime(2024, 1, 1, tzinfo=timezone.utc),
            35,
            open=Decimal("10"),
            daily_return=Decimal("0.02"),
        )
        btc = build_candle_series(
            source=make_source(tmp_path / "btc.csv", 35),
            candles=btc_candles,
            config=ResearchMarketDataConfig(),
            pair="BTC/USDT",
        )
        cand = build_candle_series(
            source=make_source(tmp_path / "sol.csv", 35),
            candles=cand_candles,
            config=ResearchMarketDataConfig(),
            pair="SOL/USDT",
        )
        rs_report = build_relative_strength_report(
            universe=[RelativeStrengthInput(
                symbol=cand.pair,
                rows=candle_series_to_ohlcv_rows(cand),
            )],
            btc_benchmark=candle_series_to_ohlcv_rows(btc),
            report_id="test-rs",
            generated_at=datetime(2024, 2, 1, tzinfo=timezone.utc),
            metadata={},
        )
        summaries = relative_strength_report_to_discovery_summaries(rs_report)
        assert len(summaries) == 1
        assert summaries[0].pair == "SOL/USDT"
        assert summaries[0].state == "ready"
        assert summaries[0].total_score is not None


class TestDiscoverySummariesToInputs:
    def test_oi_is_none(self) -> None:
        summary = DiscoveryRelativeStrengthSummary(
            pair="SOL/USDT",
            state="ready",
            decision="outperformer",
            total_score=80.0,
        )
        inputs = discovery_summaries_to_inputs([summary])
        assert len(inputs) == 1
        assert inputs[0].pair == "SOL/USDT"
        assert inputs[0].open_interest is None
        assert inputs[0].input_kind == DiscoveryInputKind.SUMMARY


class TestDiscoveryInputBundle:
    def test_end_to_end_without_oi(self, tmp_path: Path) -> None:
        btc_candles = make_candles("BTC/USDT", datetime(2024, 1, 1, tzinfo=timezone.utc), 35)
        cand_candles = make_candles(
            "SOL/USDT",
            datetime(2024, 1, 1, tzinfo=timezone.utc),
            35,
            open=Decimal("10"),
            daily_return=Decimal("0.02"),
        )
        btc = build_candle_series(
            source=make_source(tmp_path / "btc.csv", 35),
            candles=btc_candles,
            config=ResearchMarketDataConfig(),
            pair="BTC/USDT",
        )
        cand = build_candle_series(
            source=make_source(tmp_path / "sol.csv", 35),
            candles=cand_candles,
            config=ResearchMarketDataConfig(),
            pair="SOL/USDT",
        )
        rs_report = build_relative_strength_report(
            universe=[RelativeStrengthInput(
                symbol=cand.pair,
                rows=candle_series_to_ohlcv_rows(cand),
            )],
            btc_benchmark=candle_series_to_ohlcv_rows(btc),
            report_id="test-rs",
            generated_at=datetime(2024, 2, 1, tzinfo=timezone.utc),
            metadata={},
        )
        bundle = build_discovery_input_bundle(rs_report)
        assert len(bundle.inputs) == 1
        inputs = bundle.inputs
        discovery_report = build_discovery_report(
            inputs=inputs,
            config=DiscoveryConfig(require_relative_strength=True, require_open_interest=False, block_on_missing_context=False),
            report_id="test-discovery",
            generated_at=datetime(2024, 2, 1, tzinfo=timezone.utc),
            metadata={},
        )
        assert len(discovery_report.candidates) == 1
        assert discovery_report.candidates[0].pair == "SOL/USDT"
        assert discovery_report.data_quality.pairs_with_missing_open_interest == 1
