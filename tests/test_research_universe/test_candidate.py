"""Tests for research_universe candidate builder (MVP-64 Stage 4)."""

from __future__ import annotations

from datetime import datetime, timezone
from types import MappingProxyType

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
from hunter.research_universe.candidate import build_candidate_universe
from hunter.research_universe.models import (
    EMPTY_CANDIDATE_UNIVERSE,
    ResearchUniverseConfig,
    SelectionWindow,
    UniversePairDecisionKind,
)


def _cu_config() -> ControlledUniverseConfig:
    return ControlledUniverseConfig(require_dry_run=True)


def _cu_report(
    *,
    universe: tuple[str, ...] = ("SOL/USDT",),
    watchlist: tuple[str, ...] = (),
    blocked: tuple[str, ...] = (),
) -> ControlledUniverseReport:
    items: list[ControlledUniverseItem] = []
    for pair in universe:
        items.append(
            ControlledUniverseItem(
                pair=pair,
                state=ControlledUniverseState.INCLUDED,
                classification=ControlledUniverseClassification.LONG_RESEARCH,
            )
        )
    for pair in watchlist:
        items.append(
            ControlledUniverseItem(
                pair=pair,
                state=ControlledUniverseState.WATCHLIST,
                classification=ControlledUniverseClassification.WATCHLIST_RESEARCH,
            )
        )
    for pair in blocked:
        items.append(
            ControlledUniverseItem(
                pair=pair,
                state=ControlledUniverseState.BLOCKED,
                classification=ControlledUniverseClassification.BLOCKED_BY_MACRO,
            )
        )
    return ControlledUniverseReport(
        version="0.51.0-dev",
        generated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        config=_cu_config(),
        execution_state=None,
        allowed_mode=None,
        universe=universe,
        watchlist=watchlist,
        blocked=blocked,
        items=tuple(items),
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
        metadata=MappingProxyType({}),
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
            safety_flags_ok=True,
            has_unsafe_content=False,
        ),
        reason_codes=(),
        metadata=MappingProxyType({}),
        notes=(),
    )


def _config() -> ResearchUniverseConfig:
    return ResearchUniverseConfig(
        selection_window=SelectionWindow(
            start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end=datetime(2024, 1, 10, tzinfo=timezone.utc),
        )
    )


class TestCandidateBuilder:
    def test_includes_universe_long_research(self) -> None:
        cu = _cu_report(universe=("SOL/USDT", "BTC/USDT"))
        pc = _pc_report((_pc_score("SOL/USDT", 10.0), _pc_score("BTC/USDT", 5.0)))
        result = build_candidate_universe(cu, pc, _config())
        assert result.pairs == ("SOL/USDT", "BTC/USDT")
        assert result.decisions[0].decision == UniversePairDecisionKind.INCLUDED
        assert result.fingerprint
        assert len(result.fingerprint) == 64

    def test_excludes_blocked_and_watchlist(self) -> None:
        cu = _cu_report(
            universe=("SOL/USDT",),
            watchlist=("ADA/USDT",),
            blocked=("DOGE/USDT",),
        )
        pc = _pc_report((_pc_score("SOL/USDT", 10.0),))
        result = build_candidate_universe(cu, pc, _config())
        assert result.pairs == ("SOL/USDT",)
        excluded = {d.pair for d in result.decisions if d.decision == UniversePairDecisionKind.EXCLUDED}
        assert excluded == {"ADA/USDT", "DOGE/USDT"}

    def test_ranks_by_portfolio_weight(self) -> None:
        cu = _cu_report(universe=("AAA/USDT", "BBB/USDT", "CCC/USDT"))
        pc = _pc_report(
            (
                _pc_score("AAA/USDT", 5.0),
                _pc_score("BBB/USDT", 15.0),
                _pc_score("CCC/USDT", 10.0),
            )
        )
        result = build_candidate_universe(cu, pc, _config())
        assert result.pairs == ("BBB/USDT", "CCC/USDT", "AAA/USDT")
        assert result.decisions[0].rank == 1

    def test_no_portfolio_report_uses_alphabetical_rank(self) -> None:
        cu = _cu_report(universe=("ZZZ/USDT", "AAA/USDT"))
        result = build_candidate_universe(cu, None, _config())
        assert result.pairs == ("AAA/USDT", "ZZZ/USDT")

    def test_empty_candidate_universe(self) -> None:
        cu = _cu_report(universe=())
        result = build_candidate_universe(cu, None, _config())
        assert result.pairs == ()
        assert EMPTY_CANDIDATE_UNIVERSE in result.reason_codes

    def test_excludes_non_research_classification(self) -> None:
        item = ControlledUniverseItem(
            pair="SOL/USDT",
            state=ControlledUniverseState.INCLUDED,
            classification=ControlledUniverseClassification.BLOCKED_BY_PORTFOLIO,
        )
        cu = ControlledUniverseReport(
            version="0.51.0-dev",
            generated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            config=_cu_config(),
            execution_state=None,
            allowed_mode=None,
            universe=("SOL/USDT",),
            watchlist=(),
            blocked=(),
            items=(item,),
            data_quality=ControlledUniverseDataQuality(),
            safety_flags=ControlledUniverseSafetyFlags(),
            reason_codes=(),
        )
        result = build_candidate_universe(cu, None, _config())
        assert result.pairs == ()
        assert EMPTY_CANDIDATE_UNIVERSE in result.reason_codes
