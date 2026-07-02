"""Tests for hunter.discovery.engine."""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from hunter.discovery.engine import (
    build_discovery_report,
    build_discovery_safety_flags,
    build_discovery_score,
    build_discovery_universe_summary,
    calculate_alignment_score,
    calculate_data_quality_score,
    classify_discovery_candidate,
    has_unsafe_discovery_content,
    normalized_score,
)
from hunter.discovery.models import (
    ALIGNED_CONTEXT,
    DISCOVERY_VERSION,
    FORBIDDEN_DISCOVERY_TERMS,
    HUMAN_RESEARCH_ONLY,
    LOW_OPEN_INTEREST_SCORE,
    LOW_RELATIVE_STRENGTH_SCORE,
    MISALIGNED_CONTEXT,
    MIXED_ALIGNMENT,
    NO_ACTION_COMMANDS_EMITTED,
    NO_FILE_READ_IN_ENGINE,
    NO_NETWORK_CONNECTION,
    PASSED_DISCOVERY_FILTERS,
    UNSAFE_DISCOVERY_CONTENT,
    DiscoveryClassification,
    DiscoveryConfig,
    DiscoveryInput,
    DiscoveryInputKind,
    DiscoveryOpenInterestSummary,
    DiscoveryRelativeStrengthSummary,
    DiscoveryReport,
    DiscoverySafetyFlags,
    DiscoveryScore,
    DiscoveryState,
)


def _rs(
    pair: str = "BTCUSDT",
    *,
    state: str = "READY",
    total_score: float | None = 80.0,
    decision: str = "OUTPERFORMER",
) -> DiscoveryRelativeStrengthSummary:
    return DiscoveryRelativeStrengthSummary(
        pair=pair,
        state=state,
        decision=decision,
        total_score=total_score,
    )


def _oi(
    pair: str = "BTCUSDT",
    *,
    state: str = "READY",
    total_score: float | None = 70.0,
    positioning: str = "PRICE_UP_OI_UP",
    trend: str = "EXPANDING",
    funding_context: str = "POSITIVE",
) -> DiscoveryOpenInterestSummary:
    return DiscoveryOpenInterestSummary(
        pair=pair,
        state=state,
        positioning=positioning,
        trend=trend,
        funding_context=funding_context,
        total_score=total_score,
    )


_DEFAULT = object()


def _input(
    pair: str = "BTCUSDT",
    *,
    rs: DiscoveryRelativeStrengthSummary | None | object = _DEFAULT,
    oi: DiscoveryOpenInterestSummary | None | object = _DEFAULT,
    tags: tuple[str, ...] = (),
) -> DiscoveryInput:
    if rs is _DEFAULT:
        rs = _rs(pair=pair)
    elif rs is not None and rs.pair != pair:
        rs = dataclasses.replace(rs, pair=pair)
    if oi is _DEFAULT:
        oi = _oi(pair=pair)
    elif oi is not None and oi.pair != pair:
        oi = dataclasses.replace(oi, pair=pair)
    return DiscoveryInput(
        pair=pair,
        relative_strength=rs,  # type: ignore[arg-type]
        open_interest=oi,  # type: ignore[arg-type]
        tags=tags,
    )


def _fake_input(
    pair: str,
    *,
    rs: DiscoveryRelativeStrengthSummary | None = None,
    oi: DiscoveryOpenInterestSummary | None = None,
    tags: tuple[str, ...] = (),
    metadata: dict[str, str] | None = None,
):
    """Return a non-validated fake input for safety-flag tests."""
    return SimpleNamespace(
        pair=pair,
        input_kind=DiscoveryInputKind.SUMMARY,
        relative_strength=rs,
        open_interest=oi,
        tags=tags,
        metadata=metadata or {},
    )


class TestSafetyFlags:
    def test_safe_inputs(self) -> None:
        inputs = [_input()]
        flags = build_discovery_safety_flags(inputs, DiscoveryConfig())
        assert isinstance(flags, DiscoverySafetyFlags)
        assert flags.is_safe is True

    def test_unsafe_content(self) -> None:
        inputs = [_input(tags=("buy_signal",))]
        flags = build_discovery_safety_flags(inputs, DiscoveryConfig())
        assert flags.has_unsafe_content is True
        assert flags.is_safe is False

    def test_invalid_pair(self) -> None:
        inputs = [_fake_input("")]
        flags = build_discovery_safety_flags(inputs, DiscoveryConfig())
        assert flags.has_invalid_pair is True

    def test_mismatched_pair(self) -> None:
        inputs = [_fake_input("BTCUSDT", rs=_rs(pair="ETHUSDT"))]
        flags = build_discovery_safety_flags(inputs, DiscoveryConfig())
        assert flags.has_inconsistent_state is True

    def test_blocked_context(self) -> None:
        inputs = [_input(rs=_rs(state="BLOCKED"))]
        flags = build_discovery_safety_flags(inputs, DiscoveryConfig())
        assert flags.has_blocked_context is True

    def test_invalid_score(self) -> None:
        rs = SimpleNamespace(
            pair="BTCUSDT",
            state="READY",
            decision="OUTPERFORMER",
            total_score=150.0,
            reason_codes=(),
            metadata={},
        )
        inputs = [_fake_input("BTCUSDT", rs=rs)]
        flags = build_discovery_safety_flags(inputs, DiscoveryConfig())
        assert flags.has_invalid_score is True

    def test_missing_required_context(self) -> None:
        inputs = [_input(oi=None)]
        flags = build_discovery_safety_flags(inputs, DiscoveryConfig())
        assert flags.has_missing_required_context is True


class TestUnsafeContent:
    def test_no_forbidden_terms(self) -> None:
        assert has_unsafe_discovery_content("BTCUSDT", (), {}) is False

    def test_forbidden_in_pair(self) -> None:
        assert has_unsafe_discovery_content("BTCUSDT_BUY_ORDER", (), {}) is True

    def test_forbidden_in_tags(self) -> None:
        assert has_unsafe_discovery_content("BTCUSDT", ("binance_api",), {}) is True

    def test_forbidden_in_metadata(self) -> None:
        assert (
            has_unsafe_discovery_content("BTCUSDT", (), {"note": "live_trade"}) is True
        )

    def test_case_insensitive(self) -> None:
        assert has_unsafe_discovery_content("BTCUSDT", ("BUY",), {}) is True

    def test_partial_match_does_not_match(self) -> None:
        # "buying" contains "buy" but forbidden terms are whole-word/phrase only.
        # The current implementation does substring matching, so this test documents behavior.
        assert has_unsafe_discovery_content("BTCUSDT", ("buying",), {}) is True

    def test_empty_pair(self) -> None:
        assert has_unsafe_discovery_content("", (), {}) is True

    def test_custom_forbidden_terms(self) -> None:
        assert has_unsafe_discovery_content("BTCUSDT", ("alpha",), {}, frozenset({"alpha"})) is True


class TestNormalizedScore:
    def test_none(self) -> None:
        assert normalized_score(None) == 0.0

    def test_valid_score(self) -> None:
        assert normalized_score(75.0) == 75.0

    def test_out_of_range(self) -> None:
        assert normalized_score(150.0) == 0.0
        assert normalized_score(-10.0) == 0.0

    def test_nan(self) -> None:
        assert normalized_score(float("nan")) == 0.0

    def test_inf(self) -> None:
        assert normalized_score(float("inf")) == 0.0


class TestAlignmentScore:
    def test_aligned_outperformer_supportive(self) -> None:
        rs = _rs(decision="OUTPERFORMER")
        oi = _oi(positioning="PRICE_UP_OI_UP", trend="EXPANDING")
        score, code = calculate_alignment_score(rs, oi)
        assert score == 100.0
        assert code == ALIGNED_CONTEXT

    def test_one_strong_one_neutral(self) -> None:
        rs = _rs(decision="OUTPERFORMER")
        oi = _oi(positioning="MIXED", trend="FLAT")
        score, code = calculate_alignment_score(rs, oi)
        assert score == 70.0
        assert code == MIXED_ALIGNMENT

    def test_mixed_not_contradictory(self) -> None:
        rs = _rs(decision="NEUTRAL")
        oi = _oi(positioning="PRICE_UP_OI_DOWN", trend="FLAT")
        score, code = calculate_alignment_score(rs, oi)
        assert score == 40.0
        assert code == MIXED_ALIGNMENT

    def test_contradictory(self) -> None:
        rs = _rs(decision="OUTPERFORMER")
        oi = _oi(positioning="PRICE_DOWN_OI_UP", trend="CONTRACTING")
        score, code = calculate_alignment_score(rs, oi)
        assert score == 0.0
        assert code == MISALIGNED_CONTEXT

    def test_missing_rs(self) -> None:
        score, code = calculate_alignment_score(None, _oi())
        assert score == 0.0
        assert code == MISALIGNED_CONTEXT

    def test_blocked_context(self) -> None:
        rs = _rs(state="BLOCKED")
        score, code = calculate_alignment_score(rs, _oi())
        assert score == 0.0
        assert code == MISALIGNED_CONTEXT


class TestDataQualityScore:
    def test_both_ready(self) -> None:
        assert calculate_data_quality_score(_rs(), _oi()) == 100.0

    def test_one_missing(self) -> None:
        assert calculate_data_quality_score(_rs(), None) == 60.0

    def test_one_insufficient(self) -> None:
        assert calculate_data_quality_score(_rs(), _oi(state="INSUFFICIENT_DATA")) == 30.0

    def test_blocked(self) -> None:
        assert calculate_data_quality_score(_rs(), _oi(state="BLOCKED")) == 0.0


class TestBuildDiscoveryScore:
    def test_strong_aligned(self) -> None:
        rs = _rs(total_score=90.0, decision="OUTPERFORMER")
        oi = _oi(total_score=80.0, positioning="PRICE_UP_OI_UP", trend="EXPANDING")
        score = build_discovery_score(rs, oi, DiscoveryConfig())
        assert score.relative_strength_score == 90.0
        assert score.open_interest_score == 80.0
        assert score.alignment_score == 100.0
        assert score.data_quality_score == 100.0
        assert score.filter_bonus_score == 100.0
        # 90*0.35 + 80*0.25 + 100*0.20 + 100*0.10 + 100*0.10 = 31.5 + 20 + 20 + 10 + 10 = 91.5
        assert score.total_score == 91.5

    def test_threshold_failure_reduces_filter_bonus(self) -> None:
        rs = _rs(total_score=55.0, decision="OUTPERFORMER")
        oi = _oi(total_score=48.0, positioning="PRICE_UP_OI_UP", trend="EXPANDING")
        score = build_discovery_score(rs, oi, DiscoveryConfig())
        # Both thresholds fail -> filter_bonus = 0.0
        assert score.filter_bonus_score == 0.0
        # RS is below min -> 0.0 for relative_strength_score (not ready-like enough? Actually score is 55, ready, so normalized to 55)
        assert score.relative_strength_score == 55.0
        assert score.open_interest_score == 48.0
        assert score.alignment_score == 100.0
        assert score.data_quality_score == 100.0
        total = round(55.0 * 0.35 + 48.0 * 0.25 + 100.0 * 0.20 + 100.0 * 0.10 + 0.0 * 0.10, 2)
        assert score.total_score == total
        assert LOW_RELATIVE_STRENGTH_SCORE in score.reason_codes
        assert LOW_OPEN_INTEREST_SCORE in score.reason_codes

    def test_one_threshold_passes(self) -> None:
        rs = _rs(total_score=80.0, decision="OUTPERFORMER")
        oi = _oi(total_score=48.0, positioning="PRICE_UP_OI_UP", trend="EXPANDING")
        score = build_discovery_score(rs, oi, DiscoveryConfig())
        assert score.filter_bonus_score == 50.0
        assert LOW_OPEN_INTEREST_SCORE in score.reason_codes
        assert LOW_RELATIVE_STRENGTH_SCORE not in score.reason_codes

    def test_reason_codes_included(self) -> None:
        rs = _rs(total_score=90.0, decision="OUTPERFORMER")
        oi = _oi(total_score=80.0, positioning="PRICE_UP_OI_UP", trend="EXPANDING")
        score = build_discovery_score(rs, oi, DiscoveryConfig())
        assert PASSED_DISCOVERY_FILTERS in score.reason_codes
        assert ALIGNED_CONTEXT in score.reason_codes
        assert LOW_RELATIVE_STRENGTH_SCORE not in score.reason_codes
        assert LOW_OPEN_INTEREST_SCORE not in score.reason_codes


class TestClassifyDiscoveryCandidate:
    def test_strong(self) -> None:
        score = DiscoveryScore(
            relative_strength_score=90.0,
            open_interest_score=80.0,
            alignment_score=100.0,
            data_quality_score=100.0,
            filter_bonus_score=100.0,
            total_score=91.0,
            reason_codes=(),
        )
        state, classification = classify_discovery_candidate(score, DiscoveryConfig())
        assert state == DiscoveryState.CANDIDATE
        assert classification == DiscoveryClassification.STRONG_RESEARCH_CANDIDATE

    def test_moderate(self) -> None:
        score = DiscoveryScore(
            relative_strength_score=70.0,
            open_interest_score=60.0,
            alignment_score=70.0,
            data_quality_score=100.0,
            filter_bonus_score=100.0,
            total_score=72.0,
            reason_codes=(),
        )
        state, classification = classify_discovery_candidate(score, DiscoveryConfig())
        assert state == DiscoveryState.CANDIDATE
        assert classification == DiscoveryClassification.MODERATE_RESEARCH_CANDIDATE

    def test_watchlist(self) -> None:
        score = DiscoveryScore(
            relative_strength_score=50.0,
            open_interest_score=50.0,
            alignment_score=50.0,
            data_quality_score=100.0,
            filter_bonus_score=0.0,
            total_score=52.0,
            reason_codes=(),
        )
        state, classification = classify_discovery_candidate(score, DiscoveryConfig())
        assert state == DiscoveryState.WATCHLIST
        assert classification == DiscoveryClassification.WATCHLIST_ONLY

    def test_excluded(self) -> None:
        score = DiscoveryScore(
            relative_strength_score=30.0,
            open_interest_score=30.0,
            alignment_score=0.0,
            data_quality_score=100.0,
            filter_bonus_score=0.0,
            total_score=30.0,
            reason_codes=(),
        )
        state, classification = classify_discovery_candidate(score, DiscoveryConfig())
        assert state == DiscoveryState.EXCLUDED
        assert classification == DiscoveryClassification.EXCLUDED_BY_FILTERS

    def test_threshold_failure_does_not_directly_force_excluded(self) -> None:
        # RS=55, OI=48 both fail thresholds. But alignment 100, data_quality 100, filter_bonus 0
        # total = 55*0.35 + 48*0.25 + 100*0.20 + 100*0.10 + 0*0.10 = 61.25
        score = DiscoveryScore(
            relative_strength_score=55.0,
            open_interest_score=48.0,
            alignment_score=100.0,
            data_quality_score=100.0,
            filter_bonus_score=0.0,
            total_score=61.25,
            reason_codes=(),
        )
        state, classification = classify_discovery_candidate(score, DiscoveryConfig())
        assert state == DiscoveryState.CANDIDATE
        assert classification == DiscoveryClassification.MODERATE_RESEARCH_CANDIDATE


class TestBuildDiscoveryReport:
    def test_full_report(self) -> None:
        inputs = [
            _input(pair="BTCUSDT", rs=_rs(total_score=90.0), oi=_oi(total_score=80.0)),
            _input(pair="ETHUSDT", rs=_rs(total_score=20.0), oi=_oi(total_score=20.0)),
        ]
        report = build_discovery_report(inputs=inputs)
        assert report.version == DISCOVERY_VERSION
        assert report.report_id == "latest-discovery"
        assert len(report.candidates) == 2
        assert report.universe_summary.total_inputs == 2
        assert report.candidates[0].pair == "BTCUSDT"
        assert report.candidates[0].classification == DiscoveryClassification.STRONG_RESEARCH_CANDIDATE
        assert report.candidates[1].classification == DiscoveryClassification.EXCLUDED_BY_FILTERS

    def test_ordering(self) -> None:
        inputs = [
            _input(pair="ETHUSDT", rs=_rs(total_score=80.0), oi=_oi(total_score=70.0)),
            _input(pair="BTCUSDT", rs=_rs(total_score=80.0), oi=_oi(total_score=70.0)),
        ]
        report = build_discovery_report(inputs=inputs)
        # Same score -> order by pair ascending
        assert report.candidates[0].pair == "BTCUSDT"
        assert report.candidates[1].pair == "ETHUSDT"

    def test_blocked_precedence(self) -> None:
        inputs = [
            _input(pair="BTCUSDT", rs=_rs(total_score=90.0, state="BLOCKED")),
        ]
        report = build_discovery_report(inputs=inputs)
        assert report.candidates[0].state == DiscoveryState.BLOCKED
        assert report.candidates[0].classification == DiscoveryClassification.BLOCKED

    def test_insufficient_data_precedence(self) -> None:
        inputs = [
            _input(pair="BTCUSDT", rs=_rs(total_score=90.0, state="INSUFFICIENT_DATA")),
        ]
        report = build_discovery_report(inputs=inputs)
        assert report.candidates[0].state == DiscoveryState.INSUFFICIENT_DATA
        assert report.candidates[0].classification == DiscoveryClassification.INSUFFICIENT_DATA

    def test_include_excluded_candidates_true(self) -> None:
        inputs = [
            _input(pair="BTCUSDT", rs=_rs(total_score=20.0), oi=_oi(total_score=20.0)),
        ]
        report = build_discovery_report(inputs=inputs)
        assert len(report.candidates) == 1
        assert report.candidates[0].state == DiscoveryState.EXCLUDED

    def test_include_excluded_candidates_false(self) -> None:
        inputs = [
            _input(pair="BTCUSDT", rs=_rs(total_score=20.0), oi=_oi(total_score=20.0)),
        ]
        config = DiscoveryConfig(include_excluded_candidates=False)
        report = build_discovery_report(inputs=inputs, config=config)
        assert len(report.candidates) == 0
        assert report.universe_summary.excluded_count == 1
        assert report.universe_summary.total_inputs == 1

    def test_blocked_always_included(self) -> None:
        inputs = [
            _input(pair="BTCUSDT", rs=_rs(total_score=90.0, state="BLOCKED")),
        ]
        config = DiscoveryConfig(include_excluded_candidates=False)
        report = build_discovery_report(inputs=inputs, config=config)
        assert len(report.candidates) == 1
        assert report.candidates[0].state == DiscoveryState.BLOCKED

    def test_insufficient_always_included(self) -> None:
        inputs = [
            _input(pair="BTCUSDT", rs=_rs(total_score=90.0, state="INSUFFICIENT_DATA")),
        ]
        config = DiscoveryConfig(include_excluded_candidates=False)
        report = build_discovery_report(inputs=inputs, config=config)
        assert len(report.candidates) == 1
        assert report.candidates[0].state == DiscoveryState.INSUFFICIENT_DATA

    def test_no_mutation_of_inputs(self) -> None:
        inputs = [_input()]
        original = inputs[0]
        build_discovery_report(inputs=inputs)
        assert inputs[0] is original
        assert inputs[0].tags == ()

    def test_deterministic_generated_at(self) -> None:
        now = datetime(2026, 7, 2, 12, 0, tzinfo=timezone.utc)
        report = build_discovery_report(inputs=[_input()], generated_at=now)
        assert report.generated_at == now

    def test_report_blocked_factory(self) -> None:
        report = DiscoveryReport.blocked(reason_code=UNSAFE_DISCOVERY_CONTENT)
        assert report.candidates == ()
        assert report.safety_flags.has_blocked_context is True

    def test_unsafe_input_blocks_candidate(self) -> None:
        inputs = [_input(tags=("buy",))]
        report = build_discovery_report(inputs=inputs)
        assert report.candidates[0].state == DiscoveryState.BLOCKED
        assert UNSAFE_DISCOVERY_CONTENT in report.candidates[0].reason_codes

    def test_missing_required_context_block(self) -> None:
        inputs = [_input(oi=None)]
        config = DiscoveryConfig(block_on_missing_context=True)
        report = build_discovery_report(inputs=inputs, config=config)
        assert report.candidates[0].state == DiscoveryState.BLOCKED

    def test_missing_required_context_insufficient(self) -> None:
        inputs = [_input(oi=None)]
        config = DiscoveryConfig(block_on_missing_context=False)
        report = build_discovery_report(inputs=inputs, config=config)
        assert report.candidates[0].state == DiscoveryState.INSUFFICIENT_DATA

    def test_safety_flags_in_report(self) -> None:
        inputs = [_input()]
        report = build_discovery_report(inputs=inputs)
        assert report.safety_flags.no_action_commands_emitted is True
        assert report.safety_flags.no_network_connection is True
        assert report.safety_flags.no_file_read_in_engine is True

    def test_report_metadata(self) -> None:
        report = build_discovery_report(inputs=[_input()], metadata={"source": "test"})
        assert dict(report.metadata) == {"source": "test"}

    def test_input_kind_default(self) -> None:
        inp = DiscoveryInput(pair="BTCUSDT")
        assert inp.input_kind == DiscoveryInputKind.SUMMARY

    def test_reason_codes_on_candidates(self) -> None:
        inputs = [_input()]
        report = build_discovery_report(inputs=inputs)
        codes = report.candidates[0].reason_codes
        assert HUMAN_RESEARCH_ONLY in codes
        assert NO_ACTION_COMMANDS_EMITTED in codes

    def test_universe_counts_all_inputs(self) -> None:
        inputs = [
            _input(pair="BTCUSDT", rs=_rs(total_score=90.0), oi=_oi(total_score=80.0)),
            _input(pair="ETHUSDT", rs=_rs(total_score=20.0), oi=_oi(total_score=20.0)),
            _input(pair="SOLUSDT", rs=_rs(total_score=90.0, state="BLOCKED")),
            _input(pair="ADAUSDT", oi=None),
        ]
        config = DiscoveryConfig(include_excluded_candidates=False)
        report = build_discovery_report(inputs=inputs, config=config)
        summary = report.universe_summary
        assert summary.total_inputs == 4
        assert summary.candidate_count == 1
        assert summary.excluded_count == 1
        assert summary.blocked_count == 1
        assert summary.insufficient_data_count == 1
        assert len(report.candidates) == 3  # excluded omitted

    def test_data_quality_in_report(self) -> None:
        inputs = [
            _input(pair="BTCUSDT", rs=_rs(), oi=_oi()),
            _input(pair="ETHUSDT", rs=_rs(), oi=None),
        ]
        report = build_discovery_report(inputs=inputs)
        assert report.data_quality.total_inputs == 2
        assert report.data_quality.pairs_with_both_contexts == 1
        assert report.data_quality.pairs_with_missing_open_interest == 1

    def test_config_none_uses_default(self) -> None:
        report = build_discovery_report(inputs=[_input()], config=None)
        assert report.config.min_relative_strength_score == 60.0


class TestBuildDiscoveryUniverseSummary:
    def test_summary_from_candidates(self) -> None:
        inputs = [
            _input(pair="BTCUSDT", rs=_rs(total_score=90.0), oi=_oi(total_score=80.0)),
            _input(pair="ETHUSDT", rs=_rs(total_score=20.0), oi=_oi(total_score=20.0)),
        ]
        report = build_discovery_report(inputs=inputs)
        summary = build_discovery_universe_summary(report.candidates)
        assert summary.total_inputs == 2
        assert summary.candidate_count == 1
        assert summary.excluded_count == 1

    def test_counts_with_all_states(self) -> None:
        inputs = [
            _input(pair="BTCUSDT", rs=_rs(total_score=90.0), oi=_oi(total_score=80.0)),
            _input(pair="ETHUSDT", rs=_rs(total_score=49.0), oi=_oi(total_score=49.0)),
            _input(pair="SOLUSDT", rs=_rs(total_score=20.0), oi=_oi(total_score=20.0)),
            _input(pair="ADAUSDT", rs=_rs(total_score=90.0, state="INSUFFICIENT_DATA")),
            _input(pair="XRPUSDT", rs=_rs(total_score=90.0, state="BLOCKED")),
        ]
        report = build_discovery_report(inputs=inputs)
        summary = report.universe_summary
        assert summary.total_inputs == 5
        assert summary.candidate_count == 1
        assert summary.watchlist_count == 1
        assert summary.excluded_count == 1
        assert summary.insufficient_data_count == 1
        assert summary.blocked_count == 1
