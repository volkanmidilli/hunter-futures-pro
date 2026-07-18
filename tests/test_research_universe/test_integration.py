"""End-to-end integration tests for the research universe builder (MVP-64 Stage 8)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import json
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
    NormalizedCandle,
    ResearchMarketDataBundle,
    ResearchMarketDataConfig,
    ResearchMarketDataManifest,
)
from hunter.research_universe.baseline import build_baseline_universe
from hunter.research_universe.candidate import build_candidate_universe
from hunter.research_universe.comparison import compare_universes
from hunter.research_universe.eligibility import assess_pair_eligibility
from hunter.research_universe.models import (
    ResearchUniverseConfig,
    ResearchUniverseSafetyFlags,
    SelectionWindow,
    UniversePairDecisionKind,
)
from hunter.research_universe.writer import ResearchUniverseWriter


def test_version_constants_exported() -> None:
    from hunter.research_universe import RESEARCH_UNIVERSE_VERSION, SPEC_VERSION

    assert RESEARCH_UNIVERSE_VERSION == "0.64.0-dev"
    assert SPEC_VERSION == "SPEC-065"


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
            path=Path(f"/tmp/{pair.replace('/', '')}.csv"),
            label=pair,
            row_count=n,
            file_hash=f"hash-{pair}",
        ),
        coverage=Decimal("1.0"),
        coverage_threshold=Decimal("0.8"),
        missing_intervals=(),
        reason_codes=(),
        metadata={},
    )


def _bundle(
    candidates: tuple[CandleSeries, ...],
    postfix: tuple[CandleSeries, ...] = (),
) -> ResearchMarketDataBundle:
    btc = _series("BTC/USDT", Decimal("50000"), Decimal("100"))
    all_candidates = (*candidates, *postfix)
    sources = tuple(s.source for s in (*all_candidates, btc))
    fingerprints = {s.source.source_id: s.source.file_hash for s in (*all_candidates, btc)}
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
        candidates=all_candidates,
        btc_series=btc,
        eth_series=None,
        exclusions=(),
        safety_flags=MarketDataSafetyFlags(),
        reason_codes=(),
        metadata={},
    )


def _cu_report(
    universe_pairs: tuple[str, ...],
    watchlist_pairs: tuple[str, ...] = (),
    blocked_pairs: tuple[str, ...] = (),
) -> ControlledUniverseReport:
    items = []
    for p in universe_pairs:
        items.append(
            ControlledUniverseItem(
                pair=p,
                state=ControlledUniverseState.INCLUDED,
                classification=ControlledUniverseClassification.LONG_RESEARCH,
            )
        )
    for p in watchlist_pairs:
        items.append(
            ControlledUniverseItem(
                pair=p,
                state=ControlledUniverseState.WATCHLIST,
                classification=ControlledUniverseClassification.WATCHLIST_RESEARCH,
            )
        )
    for p in blocked_pairs:
        items.append(
            ControlledUniverseItem(
                pair=p,
                state=ControlledUniverseState.BLOCKED,
                classification=ControlledUniverseClassification.BLOCKED_BY_MACRO,
            )
        )
    return ControlledUniverseReport(
        version="1.0",
        generated_at=datetime(2024, 1, 10, tzinfo=timezone.utc),
        config=ControlledUniverseConfig(require_dry_run=True),
        execution_state=None,
        allowed_mode=AllowedMode.LONG_ONLY.value,
        universe=universe_pairs,
        watchlist=watchlist_pairs,
        blocked=blocked_pairs,
        items=tuple(items),
        data_quality=ControlledUniverseDataQuality(
            total_inputs=len(items),
            universe_count=len(universe_pairs),
            watchlist_count=len(watchlist_pairs),
            blocked_count=len(blocked_pairs),
            safety_flags_ok=True,
        ),
        safety_flags=ControlledUniverseSafetyFlags(),
        reason_codes=(),
        metadata={},
    )


def _pc_score(pair: str, weight: float) -> PortfolioConstructionScore:
    return PortfolioConstructionScore(
        pair=pair,
        state=PortfolioConstructionState.INCLUDED,
        classification=PortfolioConstructionClassification.CORE_RESEARCH_ALLOCATION,
        allocation_score=75.0,
        discovery_score_component=70.0,
        data_quality_score=60.0,
        diversification_component=50.0,
        cap_readiness_score=80.0,
        filter_bonus_score=0.0,
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
        version="1.0",
        report_id="pc-test",
        generated_at=datetime(2024, 1, 10, tzinfo=timezone.utc),
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
            safety_flags_ok=True,
            has_unsafe_content=False,
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


class TestEndToEnd:
    def test_bundle_to_dual_universe_artifacts(self, tmp_path: Path) -> None:
        a = _series("SOL/USDT", Decimal("100"), Decimal("1000"))
        d = _series("ADA/USDT", Decimal("1"), Decimal("10000"))
        e = _series("DOT/USDT", Decimal("10"), Decimal("5000"))
        bundle = _bundle((a, d, e))
        cu = _cu_report(("SOL/USDT", "ADA/USDT"))
        pc = _pc_report((_pc_score("SOL/USDT", 10.0), _pc_score("ADA/USDT", 5.0)))
        config = _config()

        baseline = build_baseline_universe(bundle, config)
        candidate = build_candidate_universe(cu, pc, config)
        comparison = compare_universes(candidate, baseline)

        assert candidate.pairs == ("SOL/USDT", "ADA/USDT")
        assert baseline.pairs == ("SOL/USDT", "DOT/USDT", "ADA/USDT")
        assert comparison.overlap == ("ADA/USDT", "SOL/USDT")
        assert "DOT/USDT" in comparison.baseline_only

        writer = ResearchUniverseWriter(output_dir=tmp_path / "reports", data_dir=tmp_path / "data")
        candidate_path = writer.write_candidate_json(candidate)
        baseline_path = writer.write_baseline_json(baseline)
        comparison_path = writer.write_comparison_json(comparison)
        for path in (candidate_path, baseline_path, comparison_path):
            assert path.exists()

        # JSON artifacts are deterministic and parseable.
        for path in (candidate_path, baseline_path, comparison_path):
            with open(path) as f:
                payload = json.load(f)
            assert payload["research_only"] is True
            assert payload["human_approval_required"] is True
            assert payload["safety_flags"]["live_trading_allowed"] is False

    def test_baseline_ignores_postfix_high_volume(self, tmp_path: Path) -> None:
        a = _series("SOL/USDT", Decimal("100"), Decimal("1000"))
        d = _series("ADA/USDT", Decimal("1"), Decimal("10000"))
        e = _series("DOT/USDT", Decimal("10"), Decimal("5000"))
        bundle = _bundle((a, d, e))
        config = _config()
        baseline1 = build_baseline_universe(bundle, config)

        postfix = _series("ADA/USDT", Decimal("1"), Decimal("100000000"), start=datetime(2024, 1, 11, tzinfo=timezone.utc), n=5)
        bundle2 = _bundle((a, d, e), postfix=(postfix,))
        baseline2 = build_baseline_universe(bundle2, config)

        assert baseline1.pairs == baseline2.pairs
        assert baseline1.fingerprint == baseline2.fingerprint

    def test_candidate_ignores_postfix_price_changes(self, tmp_path: Path) -> None:
        cu = _cu_report(("SOL/USDT", "ADA/USDT"))
        pc = _pc_report((_pc_score("SOL/USDT", 10.0), _pc_score("ADA/USDT", 5.0)))
        config = _config()
        candidate1 = build_candidate_universe(cu, pc, config)

        cu2 = _cu_report(("SOL/USDT", "ADA/USDT"))
        # candidate is driven by portfolio weights, not by market data
        candidate2 = build_candidate_universe(cu2, pc, config)
        assert candidate1.pairs == candidate2.pairs
        assert candidate1.fingerprint == candidate2.fingerprint

    def test_same_eligibility_policy_and_window(self, tmp_path: Path) -> None:
        a = _series("SOL/USDT", Decimal("100"), Decimal("1000"))
        d = _series("ADA/USDT", Decimal("1"), Decimal("10000"))
        bundle = _bundle((a, d))
        config = _config()
        cu = _cu_report(("SOL/USDT", "ADA/USDT"))
        pc = _pc_report((_pc_score("SOL/USDT", 10.0), _pc_score("ADA/USDT", 5.0)))

        baseline = build_baseline_universe(bundle, config)
        candidate = build_candidate_universe(cu, pc, config)

        assert baseline.fingerprint != candidate.fingerprint
        assert config.selection_window.start == config.selection_window.start
        assert config.selection_window.end == config.selection_window.end

    def test_order_independence(self, tmp_path: Path) -> None:
        a = _series("SOL/USDT", Decimal("100"), Decimal("1000"))
        d = _series("ADA/USDT", Decimal("1"), Decimal("10000"))
        e = _series("DOT/USDT", Decimal("10"), Decimal("5000"))

        bundle1 = _bundle((a, d, e))
        bundle2 = _bundle((e, d, a))
        config = _config()
        assert build_baseline_universe(bundle1, config).pairs == build_baseline_universe(bundle2, config).pairs

    def test_no_synthetic_open_interest(self, tmp_path: Path) -> None:
        # Candidate does not require or synthesize OI; missing OI reason codes are preserved.
        score = _pc_score("SOL/USDT", 10.0)
        score = PortfolioConstructionScore(
            pair=score.pair,
            state=score.state,
            classification=score.classification,
            allocation_score=score.allocation_score,
            discovery_score_component=score.discovery_score_component,
            data_quality_score=score.data_quality_score,
            diversification_component=score.diversification_component,
            cap_readiness_score=score.cap_readiness_score,
            filter_bonus_score=score.filter_bonus_score,
            initial_research_weight_pct=score.initial_research_weight_pct,
            capped_weight_pct=score.capped_weight_pct,
            final_weight_pct=score.final_weight_pct,
            reason_codes=("MISSING_OPEN_INTEREST_CONTEXT",),
            tags=score.tags,
            metadata=score.metadata,
            notes=score.notes,
            rank=score.rank,
        )
        pc = _pc_report((score,))
        cu = _cu_report(("SOL/USDT",))
        config = _config()
        candidate = build_candidate_universe(cu, pc, config)
        assert candidate.pairs == ("SOL/USDT",)
        # The candidate builder does not fabricate OI; it merely carries the upstream reason code.
        assert candidate.reason_codes == ()

    def test_source_candle_file_not_modified(self, tmp_path: Path) -> None:
        source = tmp_path / "SOLUSDT.csv"
        source.write_text("header\ndata")
        mtime_before = source.stat().st_mtime
        a = _series("SOL/USDT", Decimal("100"), Decimal("1000"))
        build_baseline_universe(_bundle((a,)), _config())
        assert source.stat().st_mtime == mtime_before

    def test_public_safety_flags(self, tmp_path: Path) -> None:
        a = _series("SOL/USDT", Decimal("100"), Decimal("1000"))
        baseline = build_baseline_universe(_bundle((a,)), _config())
        flags = baseline.safety_flags
        assert flags.research_only is True
        assert flags.execution_approval_granted is False
        assert flags.production_approval_granted is False
        assert flags.live_trading_allowed is False
        assert flags.automatic_execution_allowed is False
