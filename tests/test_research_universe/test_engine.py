"""Integration tests for research_universe engine (MVP-64 Stage 5/6/7)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from hunter.controlled_universe.models import (
    AllowedMode,
    ControlledUniverseClassification,
    ControlledUniverseConfig,
    ControlledUniverseDataQuality,
    ControlledUniverseItem,
    ControlledUniverseReport,
    ControlledUniverseSafetyFlags,
    ControlledUniverseState,
)
from hunter.portfolio_construction.models import (
    PortfolioConstructionClassification,
    PortfolioConstructionConfig,
    PortfolioConstructionDataQuality,
    PortfolioConstructionReport,
    PortfolioConstructionSafetyFlags,
    PortfolioConstructionScore,
    PortfolioConstructionState,
    PortfolioConstructionUniverseSummary,
)
from hunter.research_market_data.models import (
    CandleSeries,
    MarketDataSafetyFlags,
    MarketDataSourceRef,
    MissingInterval,
    NormalizedCandle,
    ResearchMarketDataBundle,
    ResearchMarketDataConfig,
    ResearchMarketDataManifest,
)
from hunter.research_universe.engine import build_research_universe_report
from hunter.research_universe.errors import ResearchUniverseValidationError
from hunter.research_universe.models import (
    ResearchUniverseConfig,
    SelectionWindow,
)
from hunter.research_universe.writer import write_research_universe_report


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
            bundle_fingerprint="bundle-fp",
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


def _cu_config() -> ControlledUniverseConfig:
    return ControlledUniverseConfig(require_dry_run=True)


def _cu_report(universe: tuple[str, ...]) -> ControlledUniverseReport:
    items = tuple(
        ControlledUniverseItem(
            pair=p,
            state=ControlledUniverseState.INCLUDED,
            classification=ControlledUniverseClassification.LONG_RESEARCH,
        )
        for p in universe
    )
    return ControlledUniverseReport(
        version="0.51.0-dev",
        generated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        config=_cu_config(),
        execution_state=None,
        allowed_mode=None,
        universe=universe,
        watchlist=(),
        blocked=(),
        items=items,
        data_quality=ControlledUniverseDataQuality(),
        safety_flags=ControlledUniverseSafetyFlags(),
        reason_codes=(),
    )


def _pc_score(pair: str, weight: float) -> PortfolioConstructionScore:
    return PortfolioConstructionScore(
        pair=pair,
        state=PortfolioConstructionState.INCLUDED,
        classification=PortfolioConstructionClassification.CORE_RESEARCH_ALLOCATION,
        allocation_score=80.0,
        discovery_score_component=60.0,
        data_quality_score=90.0,
        diversification_component=70.0,
        cap_readiness_score=80.0,
        filter_bonus_score=50.0,
        initial_research_weight_pct=weight,
        capped_weight_pct=weight,
        final_weight_pct=weight,
        reason_codes=(),
        tags=(),
        metadata={},
        notes=(),
        rank=1,
    )


def _pc_report(scores: tuple[PortfolioConstructionScore, ...]) -> PortfolioConstructionReport:
    return PortfolioConstructionReport(
        version="0.57.0-dev",
        report_id="test",
        generated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        inputs=(),
        config=PortfolioConstructionConfig(),
        safety_flags=PortfolioConstructionSafetyFlags(),
        scores=scores,
        universe_summary=PortfolioConstructionUniverseSummary(
            total_candidates=len(scores),
            included_count=len(scores),
            capped_count=0,
            watchlist_count=0,
            excluded_count=0,
            insufficient_data_count=0,
            blocked_count=0,
            core_allocation_count=len(scores),
            satellite_allocation_count=0,
            watchlist_allocation_count=0,
            total_final_weight_pct=sum(s.final_weight_pct for s in scores),
            top_pair=scores[0].pair if scores else None,
            notes=(),
        ),
        data_quality=PortfolioConstructionDataQuality(
            total_inputs=0,
            included_count=0,
            capped_count=0,
            watchlist_count=0,
            excluded_count=0,
            insufficient_data_count=0,
            blocked_count=0,
            ready_context_count=0,
            missing_context_count=0,
            blocked_context_count=0,
            total_final_weight_pct=0.0,
            total_research_weight_pct=0.0,
            data_quality_score=0.0,
            sections_present=0,
            all_sections_present=True,
            all_counts_consistent=True,
            total_weight_within_tolerance=True,
            has_unsafe_content=False,
            safety_flags_ok=True,
        ),
        reason_codes=(),
        metadata={},
        notes=(),
    )


def _config() -> ResearchUniverseConfig:
    return ResearchUniverseConfig(
        selection_window=SelectionWindow(
            start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end=datetime(2024, 1, 10, tzinfo=timezone.utc),
        ),
        max_baseline_pairs=3,
    )


class TestEngine:
    def test_build_report(self, tmp_path) -> None:
        a = _series("SOL/USDT", Decimal("100"), Decimal("1000"))
        d = _series("ADA/USDT", Decimal("1"), Decimal("10000"))
        e = _series("DOT/USDT", Decimal("10"), Decimal("5000"))
        bundle = _bundle((a, d, e))
        cu = _cu_report(("SOL/USDT", "ADA/USDT"))
        pc = _pc_report((_pc_score("SOL/USDT", 10.0), _pc_score("ADA/USDT", 5.0)))
        config = _config()
        report = build_research_universe_report(
            bundle=bundle,
            controlled_report=cu,
            portfolio_report=pc,
            config=config,
        )
        assert report.version == "0.64.0-dev"
        assert report.spec_version == "SPEC-065"
        assert report.fingerprint
        assert report.human_approval_required is True
        assert report.research_only is True
        assert report.manifest.bundle_fingerprint == "bundle-fp"
        assert report.candidate.pairs == ("SOL/USDT", "ADA/USDT")
        assert set(report.baseline.pairs) == {"SOL/USDT", "ADA/USDT", "DOT/USDT"}
        assert report.comparison.overlap

    def test_missing_inputs_raises(self) -> None:
        with pytest.raises(ResearchUniverseValidationError):
            build_research_universe_report(
                bundle=None,
                controlled_report=None,
                portfolio_report=None,
                config=_config(),
            )

    def test_writer_roundtrip(self, tmp_path) -> None:
        a = _series("SOL/USDT", Decimal("100"), Decimal("1000"))
        bundle = _bundle((a,))
        cu = _cu_report(("SOL/USDT",))
        pc = _pc_report((_pc_score("SOL/USDT", 10.0),))
        config = _config()
        report = build_research_universe_report(
            bundle=bundle,
            controlled_report=cu,
            portfolio_report=pc,
            config=config,
        )
        report_path, manifest_path = write_research_universe_report(
            report,
            output_dir=tmp_path / "reports",
            data_dir=tmp_path / "data",
        )
        assert report_path.exists()
        assert manifest_path.exists()
        assert report.fingerprint in report_path.name
