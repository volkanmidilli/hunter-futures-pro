"""Tests for hunter.portfolio_construction.engine."""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from hunter.portfolio_construction import (
    CAPPED_BY_RESEARCH_CONSTRAINTS,
    DISCOVERY_BLOCKED,
    DISCOVERY_INSUFFICIENT_DATA,
    EXCLUDED_BY_RESEARCH_CONSTRAINTS,
    FORBIDDEN_PORTFOLIO_CONSTRUCTION_TERMS,
    HUMAN_RESEARCH_ONLY,
    INCLUDED_BY_RESEARCH_CONSTRAINTS,
    INVALID_DISCOVERY_SCORE,
    INVALID_PAIR,
    LOW_DISCOVERY_SCORE,
    MAX_CANDIDATE_COUNT_EXCEEDED,
    MAX_SINGLE_WEIGHT_CAPPED,
    MISSING_DISCOVERY_CONTEXT,
    NO_ACTION_COMMANDS_EMITTED,
    NO_FILE_READ_IN_ENGINE,
    NO_NETWORK_CONNECTION,
    NOT_PORTFOLIO_APPROVAL,
    NOT_POSITION_SIZING,
    UNSAFE_PORTFOLIO_CONSTRUCTION_CONTENT,
    ZERO_TOTAL_ALLOCATION_SCORE,
    PortfolioConstructionClassification,
    PortfolioConstructionConfig,
    PortfolioConstructionInput,
    PortfolioConstructionInputKind,
    PortfolioConstructionReport,
    PortfolioConstructionSafetyFlags,
    PortfolioConstructionScore,
    PortfolioConstructionState,
    PortfolioDiscoverySummary,
    apply_research_weight_caps,
    build_portfolio_construction_report,
    build_portfolio_construction_safety_flags,
    build_portfolio_construction_score,
    build_portfolio_construction_universe_summary,
    calculate_allocation_score,
    calculate_cap_readiness_score,
    calculate_data_quality_score,
    calculate_discovery_sub_score,
    calculate_diversification_penalty,
    calculate_filter_bonus_score,
    calculate_initial_research_weights,
    classify_portfolio_construction_candidate,
    has_unsafe_portfolio_construction_content,
    normalized_score,
)


_DEFAULT = object()


def _discovery(
    pair: str = "SOL/USDT:USDT",
    *,
    state: str = "CANDIDATE",
    classification: str = "STRONG_RESEARCH_CANDIDATE",
    discovery_score: float | None = 80.0,
    reason_codes: tuple[str, ...] = (),
    tags: tuple[str, ...] = (),
) -> PortfolioDiscoverySummary:
    return PortfolioDiscoverySummary(
        pair=pair,
        state=state,
        classification=classification,
        discovery_score=discovery_score,
        reason_codes=reason_codes,
        tags=tags,
    )


def _input(
    pair: str = "SOL/USDT:USDT",
    *,
    discovery: PortfolioDiscoverySummary | None | object = _DEFAULT,
    tags: tuple[str, ...] = (),
    metadata: dict[str, str] | None = None,
    input_kind: PortfolioConstructionInputKind = PortfolioConstructionInputKind.SUMMARY,
) -> PortfolioConstructionInput:
    if discovery is _DEFAULT:
        discovery = _discovery(pair=pair)
    elif discovery is not None and not isinstance(discovery, PortfolioDiscoverySummary):
        discovery = None
    elif discovery is not None and discovery.pair != pair:
        discovery = dataclasses.replace(discovery, pair=pair)
    return PortfolioConstructionInput(
        pair=pair,
        discovery=discovery,  # type: ignore[arg-type]
        tags=tags,
        metadata=metadata or {},
        input_kind=input_kind,
    )


def _fake_input(
    pair: str,
    *,
    discovery: PortfolioDiscoverySummary | None = None,
    tags: tuple[str, ...] = (),
    metadata: dict[str, str] | None = None,
):
    """Return a non-validated fake input for safety-flag tests."""
    return SimpleNamespace(
        pair=pair,
        input_kind=PortfolioConstructionInputKind.SUMMARY,
        discovery=discovery,
        tags=tags,
        metadata=metadata or {},
    )


class TestSafetyFlags:
    def test_safe_inputs(self) -> None:
        inputs = [_input()]
        flags = build_portfolio_construction_safety_flags(inputs, PortfolioConstructionConfig())
        assert isinstance(flags, PortfolioConstructionSafetyFlags)
        assert flags.is_safe is True

    def test_unsafe_content(self) -> None:
        inputs = [_input(tags=("buy_signal",))]
        flags = build_portfolio_construction_safety_flags(inputs, PortfolioConstructionConfig())
        assert flags.has_unsafe_content is True
        assert flags.is_safe is False

    def test_invalid_pair(self) -> None:
        inputs = [_fake_input("")]
        flags = build_portfolio_construction_safety_flags(inputs, PortfolioConstructionConfig())
        assert flags.has_invalid_pair is True
        assert flags.is_safe is False

    def test_mismatched_pair(self) -> None:
        discovery = _discovery(pair="BTC/USDT:USDT")
        inputs = [_fake_input("SOL/USDT:USDT", discovery=discovery)]
        flags = build_portfolio_construction_safety_flags(inputs, PortfolioConstructionConfig())
        assert flags.has_inconsistent_state is True
        assert flags.is_safe is False

    def test_blocked_context(self) -> None:
        discovery = _discovery(state="BLOCKED", classification="BLOCKED")
        inputs = [_input(discovery=discovery)]
        flags = build_portfolio_construction_safety_flags(inputs, PortfolioConstructionConfig())
        assert flags.has_blocked_context is True
        assert flags.is_safe is False

    def test_missing_required_context(self) -> None:
        inputs = [_input(discovery=None)]
        flags = build_portfolio_construction_safety_flags(inputs, PortfolioConstructionConfig())
        assert flags.has_missing_required_context is True
        assert flags.is_safe is False


class TestUnsafeContentDetection:
    def test_safe_strings(self) -> None:
        assert has_unsafe_portfolio_construction_content("SOL/USDT:USDT", (), {}) is False

    def test_forbidden_term_in_tag(self) -> None:
        assert has_unsafe_portfolio_construction_content("SOL/USDT:USDT", ("buy_signal",), {}) is True

    def test_forbidden_term_in_metadata(self) -> None:
        assert has_unsafe_portfolio_construction_content("SOL/USDT:USDT", (), {"note": "order_size"}) is True

    def test_forbidden_term_in_pair(self) -> None:
        assert has_unsafe_portfolio_construction_content("buy_signal", (), {}) is True

    def test_custom_forbidden_terms(self) -> None:
        assert has_unsafe_portfolio_construction_content(
            "pair", ("custom_term",), {}, forbidden_terms=frozenset({"custom_term"})
        ) is True


class TestNormalizedScore:
    def test_clamps_to_bounds(self) -> None:
        assert normalized_score(-10.0) == 0.0
        assert normalized_score(110.0) == 100.0
        assert normalized_score(50.0) == 50.0

    def test_scales_between_min_max(self) -> None:
        assert normalized_score(5.0, min_value=0.0, max_value=10.0) == 50.0
        assert normalized_score(0.0, min_value=0.0, max_value=10.0) == 0.0
        assert normalized_score(10.0, min_value=0.0, max_value=10.0) == 100.0

    def test_equal_min_max(self) -> None:
        assert normalized_score(5.0, min_value=5.0, max_value=5.0) == 100.0
        assert normalized_score(0.0, min_value=5.0, max_value=5.0) == 0.0


class TestDiscoverySubScore:
    def test_candidate_like(self) -> None:
        discovery = _discovery(state="CANDIDATE", discovery_score=80.0)
        assert calculate_discovery_sub_score(discovery, PortfolioConstructionConfig()) == 80.0

    def test_watchlist_like(self) -> None:
        discovery = _discovery(state="WATCHLIST", classification="WATCHLIST_ONLY", discovery_score=55.0)
        assert calculate_discovery_sub_score(discovery, PortfolioConstructionConfig()) == 55.0

    def test_excluded_or_blocked(self) -> None:
        assert calculate_discovery_sub_score(_discovery(state="EXCLUDED", discovery_score=80.0), PortfolioConstructionConfig()) == 0.0
        assert calculate_discovery_sub_score(_discovery(state="BLOCKED", discovery_score=80.0), PortfolioConstructionConfig()) == 0.0

    def test_missing(self) -> None:
        assert calculate_discovery_sub_score(None, PortfolioConstructionConfig()) == 0.0

    def test_no_score(self) -> None:
        discovery = _discovery(state="CANDIDATE", discovery_score=None)
        assert calculate_discovery_sub_score(discovery, PortfolioConstructionConfig()) == 0.0


class TestDataQualityScore:
    def test_candidate(self) -> None:
        assert calculate_data_quality_score(_discovery(state="CANDIDATE"), PortfolioConstructionConfig()) == 100.0

    def test_watchlist(self) -> None:
        assert calculate_data_quality_score(_discovery(state="WATCHLIST"), PortfolioConstructionConfig()) == 70.0

    def test_insufficient(self) -> None:
        assert calculate_data_quality_score(_discovery(state="INSUFFICIENT_DATA"), PortfolioConstructionConfig()) == 30.0

    def test_blocked_missing(self) -> None:
        assert calculate_data_quality_score(_discovery(state="BLOCKED"), PortfolioConstructionConfig()) == 0.0
        assert calculate_data_quality_score(None, PortfolioConstructionConfig()) == 0.0


class TestDiversificationPenalty:
    def test_no_tags(self) -> None:
        inputs = [_input(tags=()), _input(pair="BTC/USDT:USDT", tags=())]
        assert calculate_diversification_penalty("SOL/USDT:USDT", (), inputs, PortfolioConstructionConfig()) == 100.0

    def test_no_duplicate(self) -> None:
        inputs = [_input(tags=("a",)), _input(pair="BTC/USDT:USDT", tags=("b",))]
        assert calculate_diversification_penalty("SOL/USDT:USDT", ("a",), inputs, PortfolioConstructionConfig()) == 100.0

    def test_duplicate_penalty(self) -> None:
        inputs = [
            _input(tags=("layer1",)),
            _input(pair="BTC/USDT:USDT", tags=("layer1",)),
        ]
        assert calculate_diversification_penalty("SOL/USDT:USDT", ("layer1",), inputs, PortfolioConstructionConfig()) == 50.0

    def test_duplicate_block_config(self) -> None:
        config = PortfolioConstructionConfig(block_duplicate_tags=True)
        inputs = [
            _input(tags=("layer1",)),
            _input(pair="BTC/USDT:USDT", tags=("layer1",)),
        ]
        assert calculate_diversification_penalty("SOL/USDT:USDT", ("layer1",), inputs, config) == 0.0


class TestCapReadinessScore:
    def test_candidate_like(self) -> None:
        inp = _input(discovery=_discovery(state="CANDIDATE", classification="STRONG_RESEARCH_CANDIDATE"))
        assert calculate_cap_readiness_score(inp, PortfolioConstructionConfig()) == 100.0

    def test_watchlist_like(self) -> None:
        inp = _input(discovery=_discovery(state="WATCHLIST", classification="WATCHLIST_ONLY", discovery_score=55.0))
        assert calculate_cap_readiness_score(inp, PortfolioConstructionConfig()) == 50.0

    def test_blocked_insufficient(self) -> None:
        inp = _input(discovery=_discovery(state="BLOCKED", classification="BLOCKED"))
        assert calculate_cap_readiness_score(inp, PortfolioConstructionConfig()) == 0.0

    def test_missing(self) -> None:
        inp = _input(discovery=None)
        assert calculate_cap_readiness_score(inp, PortfolioConstructionConfig()) == 0.0

    def test_independent_of_allocation_score(self) -> None:
        discovery = _discovery(state="CANDIDATE", classification="STRONG_RESEARCH_CANDIDATE", discovery_score=80.0)
        inp = _input(discovery=discovery)
        all_inputs = [inp]
        config = PortfolioConstructionConfig()
        cap_readiness = calculate_cap_readiness_score(inp, config)
        allocation = calculate_allocation_score(inp, all_inputs, config)
        assert cap_readiness == 100.0
        assert allocation is not None


class TestFilterBonusScore:
    def test_candidate_passes(self) -> None:
        discovery = _discovery(state="CANDIDATE", discovery_score=70.0)
        assert calculate_filter_bonus_score(discovery, PortfolioConstructionConfig()) == 100.0

    def test_candidate_fails(self) -> None:
        discovery = _discovery(state="CANDIDATE", discovery_score=50.0)
        assert calculate_filter_bonus_score(discovery, PortfolioConstructionConfig()) == 0.0

    def test_watchlist_passes(self) -> None:
        discovery = _discovery(state="WATCHLIST", classification="WATCHLIST_ONLY", discovery_score=50.0)
        assert calculate_filter_bonus_score(discovery, PortfolioConstructionConfig()) == 50.0

    def test_watchlist_fails(self) -> None:
        discovery = _discovery(state="WATCHLIST", classification="WATCHLIST_ONLY", discovery_score=40.0)
        assert calculate_filter_bonus_score(discovery, PortfolioConstructionConfig()) == 0.0

    def test_blocked(self) -> None:
        discovery = _discovery(state="BLOCKED", classification="BLOCKED", discovery_score=90.0)
        assert calculate_filter_bonus_score(discovery, PortfolioConstructionConfig()) == 0.0


class TestAllocationScore:
    def test_exact_formula(self) -> None:
        discovery = _discovery(state="CANDIDATE", discovery_score=80.0)
        inp = _input(discovery=discovery)
        all_inputs = [inp]
        config = PortfolioConstructionConfig()
        score = calculate_allocation_score(inp, all_inputs, config)
        expected = 91.0
        assert score == pytest.approx(expected, abs=0.01)

    def test_watchlist_formula(self) -> None:
        discovery = _discovery(state="WATCHLIST", classification="WATCHLIST_ONLY", discovery_score=50.0)
        inp = _input(discovery=discovery)
        all_inputs = [inp]
        config = PortfolioConstructionConfig()
        score = calculate_allocation_score(inp, all_inputs, config)
        expected = 60.5
        assert score == pytest.approx(expected, abs=0.01)

    def test_in_bounds(self) -> None:
        inp = _input()
        score = calculate_allocation_score(inp, [inp], PortfolioConstructionConfig())
        assert 0.0 <= score <= 100.0

    def test_one_pass_before_weights(self) -> None:
        inp = _input()
        score = calculate_allocation_score(inp, [inp], PortfolioConstructionConfig())
        assert score >= 0.0


class TestInitialResearchWeights:
    def test_initial_weight_calculation(self) -> None:
        score = PortfolioConstructionScore(
            pair="SOL/USDT:USDT",
            state=PortfolioConstructionState.EXCLUDED,
            classification=PortfolioConstructionClassification.EXCLUDED_BY_CONSTRAINTS,
            allocation_score=80.0,
            discovery_score_component=80.0,
            data_quality_score=100.0,
            diversification_component=100.0,
            cap_readiness_score=100.0,
            filter_bonus_score=100.0,
            initial_research_weight_pct=0.0,
            capped_weight_pct=0.0,
            final_weight_pct=0.0,
            reason_codes=(),
            tags=(),
            metadata={},
            notes=(),
            rank=None,
        )
        scores = calculate_initial_research_weights([score], PortfolioConstructionConfig())
        assert len(scores) == 1
        assert scores[0].initial_research_weight_pct == 100.0

    def test_zero_total_allocation_score(self) -> None:
        score = PortfolioConstructionScore(
            pair="SOL/USDT:USDT",
            state=PortfolioConstructionState.EXCLUDED,
            classification=PortfolioConstructionClassification.EXCLUDED_BY_CONSTRAINTS,
            allocation_score=60.0,
            discovery_score_component=0.0,
            data_quality_score=0.0,
            diversification_component=0.0,
            cap_readiness_score=0.0,
            filter_bonus_score=0.0,
            initial_research_weight_pct=0.0,
            capped_weight_pct=0.0,
            final_weight_pct=0.0,
            reason_codes=(),
            tags=(),
            metadata={},
            notes=(),
            rank=None,
        )
        scores = calculate_initial_research_weights([score], PortfolioConstructionConfig())
        assert scores[0].initial_research_weight_pct == 100.0

    def test_blocked_gets_zero_weight(self) -> None:
        score = PortfolioConstructionScore(
            pair="SOL/USDT:USDT",
            state=PortfolioConstructionState.BLOCKED,
            classification=PortfolioConstructionClassification.BLOCKED,
            allocation_score=90.0,
            discovery_score_component=80.0,
            data_quality_score=100.0,
            diversification_component=100.0,
            cap_readiness_score=100.0,
            filter_bonus_score=100.0,
            initial_research_weight_pct=0.0,
            capped_weight_pct=0.0,
            final_weight_pct=0.0,
            reason_codes=(),
            tags=(),
            metadata={},
            notes=(),
            rank=None,
        )
        scores = calculate_initial_research_weights([score], PortfolioConstructionConfig())
        assert scores[0].initial_research_weight_pct == 0.0


class TestApplyResearchWeightCaps:
    def test_no_cap_needed(self) -> None:
        score = PortfolioConstructionScore(
            pair="SOL/USDT:USDT",
            state=PortfolioConstructionState.EXCLUDED,
            classification=PortfolioConstructionClassification.EXCLUDED_BY_CONSTRAINTS,
            allocation_score=80.0,
            discovery_score_component=80.0,
            data_quality_score=100.0,
            diversification_component=100.0,
            cap_readiness_score=100.0,
            filter_bonus_score=100.0,
            initial_research_weight_pct=20.0,
            capped_weight_pct=0.0,
            final_weight_pct=0.0,
            reason_codes=(),
            tags=(),
            metadata={},
            notes=(),
            rank=None,
        )
        scores = apply_research_weight_caps([score], PortfolioConstructionConfig(max_single_weight_pct=25.0))
        assert scores[0].final_weight_pct == 20.0
        assert scores[0].capped_weight_pct == 0.0

    def test_cap_redistributes(self) -> None:
        s1 = PortfolioConstructionScore(
            pair="A",
            state=PortfolioConstructionState.INCLUDED,
            classification=PortfolioConstructionClassification.CORE_RESEARCH_ALLOCATION,
            allocation_score=90.0,
            discovery_score_component=90.0,
            data_quality_score=100.0,
            diversification_component=100.0,
            cap_readiness_score=100.0,
            filter_bonus_score=100.0,
            initial_research_weight_pct=60.0,
            capped_weight_pct=0.0,
            final_weight_pct=0.0,
            reason_codes=(),
            tags=(),
            metadata={},
            notes=(),
            rank=None,
        )
        s2 = PortfolioConstructionScore(
            pair="B",
            state=PortfolioConstructionState.INCLUDED,
            classification=PortfolioConstructionClassification.SATELLITE_RESEARCH_ALLOCATION,
            allocation_score=60.0,
            discovery_score_component=60.0,
            data_quality_score=100.0,
            diversification_component=100.0,
            cap_readiness_score=100.0,
            filter_bonus_score=100.0,
            initial_research_weight_pct=40.0,
            capped_weight_pct=0.0,
            final_weight_pct=0.0,
            reason_codes=(),
            tags=(),
            metadata={},
            notes=(),
            rank=None,
        )
        scores = apply_research_weight_caps([s1, s2], PortfolioConstructionConfig(max_single_weight_pct=50.0))
        by_pair = {s.pair: s for s in scores}
        assert by_pair["A"].final_weight_pct == 50.0
        assert by_pair["B"].final_weight_pct == 50.0

    def test_capped_weight_non_zero(self) -> None:
        s1 = PortfolioConstructionScore(
            pair="A",
            state=PortfolioConstructionState.INCLUDED,
            classification=PortfolioConstructionClassification.CORE_RESEARCH_ALLOCATION,
            allocation_score=90.0,
            discovery_score_component=90.0,
            data_quality_score=100.0,
            diversification_component=100.0,
            cap_readiness_score=100.0,
            filter_bonus_score=100.0,
            initial_research_weight_pct=60.0,
            capped_weight_pct=0.0,
            final_weight_pct=0.0,
            reason_codes=(),
            tags=(),
            metadata={},
            notes=(),
            rank=None,
        )
        s2 = PortfolioConstructionScore(
            pair="B",
            state=PortfolioConstructionState.INCLUDED,
            classification=PortfolioConstructionClassification.SATELLITE_RESEARCH_ALLOCATION,
            allocation_score=60.0,
            discovery_score_component=60.0,
            data_quality_score=100.0,
            diversification_component=100.0,
            cap_readiness_score=100.0,
            filter_bonus_score=100.0,
            initial_research_weight_pct=40.0,
            capped_weight_pct=0.0,
            final_weight_pct=0.0,
            reason_codes=(),
            tags=(),
            metadata={},
            notes=(),
            rank=None,
        )
        scores = apply_research_weight_caps([s1, s2], PortfolioConstructionConfig(max_single_weight_pct=50.0))
        by_pair = {s.pair: s for s in scores}
        assert by_pair["A"].capped_weight_pct > 0.0


class TestClassification:
    def test_excluded(self) -> None:
        state, classification = classify_portfolio_construction_candidate(40.0, 0.0, False, PortfolioConstructionConfig())
        assert state == PortfolioConstructionState.EXCLUDED
        assert classification == PortfolioConstructionClassification.EXCLUDED_BY_CONSTRAINTS

    def test_watchlist(self) -> None:
        state, classification = classify_portfolio_construction_candidate(50.0, 0.0, False, PortfolioConstructionConfig())
        assert state == PortfolioConstructionState.WATCHLIST
        assert classification == PortfolioConstructionClassification.WATCHLIST_ALLOCATION

    def test_included_satellite(self) -> None:
        state, classification = classify_portfolio_construction_candidate(65.0, 20.0, False, PortfolioConstructionConfig())
        assert state == PortfolioConstructionState.INCLUDED
        assert classification == PortfolioConstructionClassification.SATELLITE_RESEARCH_ALLOCATION

    def test_included_core(self) -> None:
        state, classification = classify_portfolio_construction_candidate(80.0, 25.0, False, PortfolioConstructionConfig())
        assert state == PortfolioConstructionState.INCLUDED
        assert classification == PortfolioConstructionClassification.CORE_RESEARCH_ALLOCATION

    def test_capped(self) -> None:
        state, classification = classify_portfolio_construction_candidate(80.0, 20.0, True, PortfolioConstructionConfig())
        assert state == PortfolioConstructionState.CAPPED
        assert classification == PortfolioConstructionClassification.CORE_RESEARCH_ALLOCATION


class TestBuildPortfolioConstructionScore:
    def test_included_candidate(self) -> None:
        inp = _input()
        score = build_portfolio_construction_score(inp, [inp], PortfolioConstructionConfig())
        assert score.pair == "SOL/USDT:USDT"
        assert score.allocation_score > 0.0
        assert score.state == PortfolioConstructionState.EXCLUDED

    def test_blocked(self) -> None:
        discovery = _discovery(state="BLOCKED", classification="BLOCKED")
        inp = _input(discovery=discovery)
        score = build_portfolio_construction_score(inp, [inp], PortfolioConstructionConfig())
        assert score.state == PortfolioConstructionState.BLOCKED
        assert score.classification == PortfolioConstructionClassification.BLOCKED

    def test_insufficient_data(self) -> None:
        discovery = _discovery(state="INSUFFICIENT_DATA", classification="INSUFFICIENT_DATA")
        inp = _input(discovery=discovery)
        score = build_portfolio_construction_score(inp, [inp], PortfolioConstructionConfig())
        assert score.state == PortfolioConstructionState.INSUFFICIENT_DATA
        assert score.classification == PortfolioConstructionClassification.INSUFFICIENT_DATA

    def test_watchlist(self) -> None:
        discovery = _discovery(state="WATCHLIST", classification="WATCHLIST_ONLY", discovery_score=50.0)
        inp = _input(discovery=discovery)
        score = build_portfolio_construction_score(inp, [inp], PortfolioConstructionConfig())
        assert score.state == PortfolioConstructionState.EXCLUDED
        assert score.allocation_score < 75.0

    def test_no_mutation(self) -> None:
        original = _input(tags=["a", "a"])
        original_tags = original.tags
        build_portfolio_construction_score(original, [original], PortfolioConstructionConfig())
        assert original.tags == original_tags


class TestBuildPortfolioConstructionReport:
    def test_simple_report(self) -> None:
        discovery = _discovery(state="CANDIDATE", discovery_score=80.0)
        inp = _input(discovery=discovery)
        report = build_portfolio_construction_report(inputs=[inp])
        assert report.version == "0.27.0-dev"
        assert len(report.scores) == 1
        assert report.scores[0].state in {PortfolioConstructionState.INCLUDED, PortfolioConstructionState.CAPPED}

    def test_watchlist_zero_weights(self) -> None:
        discovery = _discovery(state="WATCHLIST", classification="WATCHLIST_ONLY", discovery_score=40.0)
        inp = _input(discovery=discovery)
        report = build_portfolio_construction_report(inputs=[inp])
        score = report.scores[0]
        assert score.state == PortfolioConstructionState.WATCHLIST
        assert score.initial_research_weight_pct == 0.0
        assert score.capped_weight_pct == 0.0
        assert score.final_weight_pct == 0.0

    def test_capped_state_post_cap(self) -> None:
        inputs = [
            _input(pair="A", discovery=_discovery(pair="A", state="CANDIDATE", discovery_score=95.0)),
            _input(pair="B", discovery=_discovery(pair="B", state="CANDIDATE", discovery_score=90.0)),
            _input(pair="C", discovery=_discovery(pair="C", state="CANDIDATE", discovery_score=85.0)),
        ]
        report = build_portfolio_construction_report(inputs=inputs, config=PortfolioConstructionConfig(max_single_weight_pct=25.0))
        for score in report.scores:
            if score.final_weight_pct == 25.0 and score.initial_research_weight_pct > 25.0:
                assert score.state == PortfolioConstructionState.CAPPED

    def test_max_candidate_count(self) -> None:
        inputs = [
            _input(pair=f"A{i}", discovery=_discovery(pair=f"A{i}", state="CANDIDATE", discovery_score=score))
            for i, score in enumerate([95.0, 90.0, 85.0, 80.0, 75.0, 70.0, 65.0, 60.0, 55.0, 50.0, 45.0, 40.0])
        ]
        config = PortfolioConstructionConfig(max_candidate_count=5, include_excluded_candidates=True)
        report = build_portfolio_construction_report(inputs=inputs, config=config)
        excluded_by_count = [
            s for s in report.scores
            if s.state == PortfolioConstructionState.EXCLUDED and MAX_CANDIDATE_COUNT_EXCEEDED in s.reason_codes
        ]
        assert len(excluded_by_count) > 0
        in_pool = [s for s in report.scores if s.state in {PortfolioConstructionState.INCLUDED, PortfolioConstructionState.CAPPED}]
        assert len(in_pool) <= 5

    def test_include_excluded_false(self) -> None:
        inputs = [
            _input(pair="A", discovery=_discovery(pair="A", state="CANDIDATE", discovery_score=95.0)),
            _input(pair="B", discovery=_discovery(pair="B", state="EXCLUDED", classification="EXCLUDED_BY_FILTERS", discovery_score=30.0)),
        ]
        config = PortfolioConstructionConfig(include_excluded_candidates=False)
        report = build_portfolio_construction_report(inputs=inputs, config=config)
        assert all(s.state != PortfolioConstructionState.EXCLUDED for s in report.scores)
        assert report.universe_summary.excluded_count == 1

    def test_blocked_and_insufficient_retained(self) -> None:
        inputs = [
            _input(pair="A", discovery=_discovery(pair="A", state="CANDIDATE", discovery_score=80.0)),
            _input(pair="B", discovery=_discovery(pair="B", state="BLOCKED", classification="BLOCKED")),
            _input(pair="C", discovery=_discovery(pair="C", state="INSUFFICIENT_DATA", classification="INSUFFICIENT_DATA")),
        ]
        config = PortfolioConstructionConfig(include_excluded_candidates=False)
        report = build_portfolio_construction_report(inputs=inputs, config=config)
        assert any(s.state == PortfolioConstructionState.BLOCKED for s in report.scores)
        assert any(s.state == PortfolioConstructionState.INSUFFICIENT_DATA for s in report.scores)
        assert report.universe_summary.blocked_count == 1
        assert report.universe_summary.insufficient_data_count == 1
        assert report.universe_summary.total_candidates == 3

    def test_universe_summary_counts_all_inputs(self) -> None:
        inputs = [
            _input(pair="A", discovery=_discovery(pair="A", state="CANDIDATE", discovery_score=80.0)),
            _input(pair="B", discovery=_discovery(pair="B", state="CANDIDATE", discovery_score=30.0)),
        ]
        config = PortfolioConstructionConfig(include_excluded_candidates=False)
        report = build_portfolio_construction_report(inputs=inputs, config=config)
        assert report.universe_summary.total_candidates == 2
        assert report.data_quality.total_inputs == 2

    def test_blocked_precedence(self) -> None:
        inputs = [_input(tags=("buy",))]
        report = build_portfolio_construction_report(inputs=inputs)
        assert report.scores[0].state == PortfolioConstructionState.BLOCKED

    def test_insufficient_data_precedence(self) -> None:
        discovery = _discovery(state="INSUFFICIENT_DATA", classification="INSUFFICIENT_DATA", discovery_score=80.0)
        inp = _input(discovery=discovery)
        report = build_portfolio_construction_report(inputs=[inp])
        assert report.scores[0].state == PortfolioConstructionState.INSUFFICIENT_DATA

    def test_blocked_precedence_over_insufficient(self) -> None:
        config = PortfolioConstructionConfig(block_on_missing_context=True)
        inp = _input(discovery=None)
        report = build_portfolio_construction_report(inputs=[inp], config=config)
        assert report.scores[0].state == PortfolioConstructionState.BLOCKED

    def test_deterministic_ordering(self) -> None:
        inputs = [
            _input(pair="A", discovery=_discovery(pair="A", state="CANDIDATE", discovery_score=80.0)),
            _input(pair="B", discovery=_discovery(pair="B", state="CANDIDATE", discovery_score=90.0)),
            _input(pair="C", discovery=_discovery(pair="C", state="WATCHLIST", classification="WATCHLIST_ONLY", discovery_score=50.0)),
        ]
        report1 = build_portfolio_construction_report(inputs=inputs)
        report2 = build_portfolio_construction_report(inputs=inputs)
        assert [s.pair for s in report1.scores] == [s.pair for s in report2.scores]
        assert report1.scores[0].rank == 1

    def test_rank_assignment(self) -> None:
        inputs = [
            _input(pair="A", discovery=_discovery(pair="A", state="CANDIDATE", discovery_score=80.0)),
            _input(pair="B", discovery=_discovery(pair="B", state="CANDIDATE", discovery_score=90.0)),
        ]
        report = build_portfolio_construction_report(inputs=inputs)
        for idx, score in enumerate(report.scores, start=1):
            assert score.rank == idx

    def test_no_mutation_of_inputs(self) -> None:
        inputs = [
            _input(pair="A", discovery=_discovery(pair="A", state="CANDIDATE", discovery_score=80.0)),
            _input(pair="B", discovery=_discovery(pair="B", state="CANDIDATE", discovery_score=90.0)),
        ]
        original_pairs = [inp.pair for inp in inputs]
        original_tags = [inp.tags for inp in inputs]
        build_portfolio_construction_report(inputs=inputs)
        for inp, pair, tags in zip(inputs, original_pairs, original_tags):
            assert inp.pair == pair
            assert inp.tags == tags

    def test_deterministic_generated_at(self) -> None:
        now = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        inputs = [_input()]
        report = build_portfolio_construction_report(inputs=inputs, generated_at=now)
        assert report.generated_at == now
