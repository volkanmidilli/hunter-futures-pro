"""Tests for hunter.discovery.models."""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from types import MappingProxyType

import pytest

from hunter.discovery.models import (
    ALIGNED_CONTEXT,
    DISCOVERY_ADVISORY_REASON_CODES,
    DISCOVERY_BLOCKING_REASON_CODES,
    DISCOVERY_FILTER_REASON_CODES,
    DISCOVERY_INSUFFICIENT_DATA_REASON_CODES,
    DISCOVERY_REASON_CODES,
    DISCOVERY_VERSION,
    FORBIDDEN_DISCOVERY_TERMS,
    HUMAN_RESEARCH_ONLY,
    INVALID_DISCOVERY_SCORE,
    INVALID_PAIR,
    LOW_OPEN_INTEREST_SCORE,
    LOW_RELATIVE_STRENGTH_SCORE,
    MISALIGNED_CONTEXT,
    MISSING_OPEN_INTEREST_CONTEXT,
    MISSING_RELATIVE_STRENGTH_CONTEXT,
    MIXED_ALIGNMENT,
    NO_ACTION_COMMANDS_EMITTED,
    NO_FILE_READ_IN_ENGINE,
    NO_NETWORK_CONNECTION,
    OPEN_INTEREST_BLOCKED,
    OPEN_INTEREST_INSUFFICIENT_DATA,
    PASSED_DISCOVERY_FILTERS,
    RELATIVE_STRENGTH_BLOCKED,
    RELATIVE_STRENGTH_INSUFFICIENT_DATA,
    UNSAFE_DISCOVERY_CONTENT,
    DiscoveryCandidate,
    DiscoveryClassification,
    DiscoveryConfig,
    DiscoveryDataQuality,
    DiscoveryInput,
    DiscoveryInputKind,
    DiscoveryOpenInterestSummary,
    DiscoveryRelativeStrengthSummary,
    DiscoveryReport,
    DiscoverySafetyFlags,
    DiscoveryScore,
    DiscoveryState,
    DiscoveryUniverseSummary,
)


class TestVersionAndReasonCodes:
    def test_discovery_version(self) -> None:
        assert DISCOVERY_VERSION == "0.26.0-dev"

    def test_blocking_reason_codes(self) -> None:
        assert INVALID_PAIR in DISCOVERY_BLOCKING_REASON_CODES
        assert INVALID_DISCOVERY_SCORE in DISCOVERY_BLOCKING_REASON_CODES
        assert UNSAFE_DISCOVERY_CONTENT in DISCOVERY_BLOCKING_REASON_CODES
        assert RELATIVE_STRENGTH_BLOCKED in DISCOVERY_BLOCKING_REASON_CODES
        assert OPEN_INTEREST_BLOCKED in DISCOVERY_BLOCKING_REASON_CODES

    def test_insufficient_data_reason_codes(self) -> None:
        assert MISSING_RELATIVE_STRENGTH_CONTEXT in DISCOVERY_INSUFFICIENT_DATA_REASON_CODES
        assert MISSING_OPEN_INTEREST_CONTEXT in DISCOVERY_INSUFFICIENT_DATA_REASON_CODES
        assert RELATIVE_STRENGTH_INSUFFICIENT_DATA in DISCOVERY_INSUFFICIENT_DATA_REASON_CODES
        assert OPEN_INTEREST_INSUFFICIENT_DATA in DISCOVERY_INSUFFICIENT_DATA_REASON_CODES

    def test_filter_reason_codes(self) -> None:
        assert LOW_RELATIVE_STRENGTH_SCORE in DISCOVERY_FILTER_REASON_CODES
        assert LOW_OPEN_INTEREST_SCORE in DISCOVERY_FILTER_REASON_CODES
        assert MISALIGNED_CONTEXT in DISCOVERY_FILTER_REASON_CODES
        assert PASSED_DISCOVERY_FILTERS in DISCOVERY_FILTER_REASON_CODES

    def test_advisory_reason_codes(self) -> None:
        assert HUMAN_RESEARCH_ONLY in DISCOVERY_ADVISORY_REASON_CODES
        assert NO_NETWORK_CONNECTION in DISCOVERY_ADVISORY_REASON_CODES
        assert NO_FILE_READ_IN_ENGINE in DISCOVERY_ADVISORY_REASON_CODES
        assert NO_ACTION_COMMANDS_EMITTED in DISCOVERY_ADVISORY_REASON_CODES
        assert ALIGNED_CONTEXT in DISCOVERY_ADVISORY_REASON_CODES
        assert MIXED_ALIGNMENT in DISCOVERY_ADVISORY_REASON_CODES

    def test_aggregate_reason_codes(self) -> None:
        assert set(DISCOVERY_REASON_CODES) == set(
            DISCOVERY_BLOCKING_REASON_CODES
            | DISCOVERY_INSUFFICIENT_DATA_REASON_CODES
            | DISCOVERY_FILTER_REASON_CODES
            | DISCOVERY_ADVISORY_REASON_CODES
        )
        assert DISCOVERY_REASON_CODES.issuperset(DISCOVERY_ADVISORY_REASON_CODES)
        assert ALIGNED_CONTEXT in DISCOVERY_REASON_CODES
        assert MIXED_ALIGNMENT in DISCOVERY_REASON_CODES

    def test_reason_code_validation_in_report(self) -> None:
        with pytest.raises(ValueError, match="unsupported reason code"):
            DiscoveryReport.blocked(reason_code="NOT_REAL")

    def test_forbidden_terms_are_lowercase(self) -> None:
        for term in FORBIDDEN_DISCOVERY_TERMS:
            assert term == term.lower()


class TestEnums:
    def test_state_enum(self) -> None:
        assert DiscoveryState.CANDIDATE.value == "CANDIDATE"
        assert DiscoveryState.WATCHLIST.value == "WATCHLIST"
        assert DiscoveryState.EXCLUDED.value == "EXCLUDED"
        assert DiscoveryState.INSUFFICIENT_DATA.value == "INSUFFICIENT_DATA"
        assert DiscoveryState.BLOCKED.value == "BLOCKED"

    def test_classification_enum(self) -> None:
        assert DiscoveryClassification.STRONG_RESEARCH_CANDIDATE.value == "STRONG_RESEARCH_CANDIDATE"
        assert DiscoveryClassification.MODERATE_RESEARCH_CANDIDATE.value == "MODERATE_RESEARCH_CANDIDATE"
        assert DiscoveryClassification.WATCHLIST_ONLY.value == "WATCHLIST_ONLY"
        assert DiscoveryClassification.EXCLUDED_BY_FILTERS.value == "EXCLUDED_BY_FILTERS"
        assert DiscoveryClassification.INSUFFICIENT_DATA.value == "INSUFFICIENT_DATA"
        assert DiscoveryClassification.BLOCKED.value == "BLOCKED"

    def test_input_kind_enum(self) -> None:
        assert DiscoveryInputKind.SUMMARY.value == "SUMMARY"
        assert DiscoveryInputKind.RELATIVE_STRENGTH.value == "RELATIVE_STRENGTH"
        assert DiscoveryInputKind.OPEN_INTEREST.value == "OPEN_INTEREST"


class TestDiscoveryConfig:
    def test_default_config(self) -> None:
        config = DiscoveryConfig()
        assert config.min_relative_strength_score == 60.0
        assert config.min_open_interest_score == 50.0
        assert config.strong_candidate_score == 75.0
        assert config.moderate_candidate_score == 60.0
        assert config.watchlist_score == 45.0
        assert dict(config.score_weights) == {
            "relative_strength_score": 0.35,
            "open_interest_score": 0.25,
            "alignment_score": 0.20,
            "data_quality_score": 0.10,
            "filter_bonus_score": 0.10,
        }

    def test_weights_must_sum_to_one(self) -> None:
        with pytest.raises(ValueError, match="must sum to 1.0"):
            DiscoveryConfig(
                score_weights={
                    "relative_strength_score": 0.35,
                    "open_interest_score": 0.25,
                    "alignment_score": 0.20,
                    "data_quality_score": 0.10,
                    "filter_bonus_score": 0.11,
                }
            )

    def test_weights_must_have_exact_keys(self) -> None:
        with pytest.raises(ValueError, match="score_weights must have exactly"):
            DiscoveryConfig(
                score_weights={
                    "relative_strength_score": 0.35,
                    "open_interest_score": 0.25,
                    "alignment_score": 0.20,
                    "data_quality_score": 0.10,
                }
            )

    def test_weights_out_of_range(self) -> None:
        with pytest.raises(ValueError, match="must be in"):
            DiscoveryConfig(
                score_weights={
                    "relative_strength_score": 1.35,
                    "open_interest_score": 0.0,
                    "alignment_score": 0.0,
                    "data_quality_score": 0.0,
                    "filter_bonus_score": -0.35,
                }
            )

    def test_thresholds_must_be_ordered(self) -> None:
        with pytest.raises(ValueError, match="strong_candidate_score >="):
            DiscoveryConfig(
                strong_candidate_score=50.0,
                moderate_candidate_score=60.0,
                watchlist_score=45.0,
            )

    def test_config_is_frozen(self) -> None:
        config = DiscoveryConfig()
        with pytest.raises(dataclasses.FrozenInstanceError):
            config.min_relative_strength_score = 0.0

    def test_score_weights_immutable(self) -> None:
        config = DiscoveryConfig()
        with pytest.raises(TypeError):
            config.score_weights["relative_strength_score"] = 0.5


class TestDiscoverySafetyFlags:
    def test_is_safe_all_false(self) -> None:
        flags = DiscoverySafetyFlags()
        assert flags.is_safe is True

    def test_is_safe_unsafe_content(self) -> None:
        flags = DiscoverySafetyFlags(has_unsafe_content=True)
        assert flags.is_safe is False

    def test_is_safe_invalid_pair(self) -> None:
        flags = DiscoverySafetyFlags(has_invalid_pair=True)
        assert flags.is_safe is False

    def test_is_safe_invalid_score(self) -> None:
        flags = DiscoverySafetyFlags(has_invalid_score=True)
        assert flags.is_safe is False

    def test_is_safe_blocked_context(self) -> None:
        flags = DiscoverySafetyFlags(has_blocked_context=True)
        assert flags.is_safe is False

    def test_is_safe_missing_context(self) -> None:
        flags = DiscoverySafetyFlags(has_missing_required_context=True)
        assert flags.is_safe is False

    def test_is_safe_inconsistent_state(self) -> None:
        flags = DiscoverySafetyFlags(has_inconsistent_state=True)
        assert flags.is_safe is False


class TestDiscoveryRelativeStrengthSummary:
    def test_valid_summary(self) -> None:
        summary = DiscoveryRelativeStrengthSummary(
            pair="BTCUSDT",
            state="READY",
            decision="OUTPERFORMER",
            total_score=80.0,
            rank_percentile_30d=70.0,
            reason_codes=("RS_REASON",),
            metadata={"source": "rs_engine"},
        )
        assert summary.pair == "BTCUSDT"
        assert summary.total_score == 80.0
        assert summary.reason_codes == ("RS_REASON",)
        assert isinstance(summary.metadata, MappingProxyType)

    def test_invalid_pair(self) -> None:
        with pytest.raises(ValueError, match="pair must be a non-empty string"):
            DiscoveryRelativeStrengthSummary(
                pair="",
                state="READY",
                decision="OUTPERFORMER",
                total_score=80.0,
            )

    def test_invalid_score(self) -> None:
        with pytest.raises(ValueError, match="total_score must be in"):
            DiscoveryRelativeStrengthSummary(
                pair="BTCUSDT",
                state="READY",
                decision="OUTPERFORMER",
                total_score=150.0,
            )

    def test_reason_codes_normalized(self) -> None:
        summary = DiscoveryRelativeStrengthSummary(
            pair="BTCUSDT",
            state="READY",
            decision="OUTPERFORMER",
            total_score=80.0,
            reason_codes=["A", "A", "B"],
        )
        assert summary.reason_codes == ("A", "B")


class TestDiscoveryOpenInterestSummary:
    def test_valid_summary(self) -> None:
        summary = DiscoveryOpenInterestSummary(
            pair="BTCUSDT",
            state="READY",
            positioning="PRICE_UP_OI_UP",
            trend="EXPANDING",
            funding_context="POSITIVE",
            total_score=70.0,
            reason_codes=("OI_REASON",),
            metadata={"source": "oi_engine"},
        )
        assert summary.pair == "BTCUSDT"
        assert summary.total_score == 70.0
        assert isinstance(summary.metadata, MappingProxyType)

    def test_invalid_pair(self) -> None:
        with pytest.raises(ValueError, match="pair must be a non-empty string"):
            DiscoveryOpenInterestSummary(
                pair="",
                state="READY",
                positioning="PRICE_UP_OI_UP",
                trend="EXPANDING",
                funding_context="POSITIVE",
                total_score=70.0,
            )

    def test_invalid_score(self) -> None:
        with pytest.raises(ValueError, match="total_score must be in"):
            DiscoveryOpenInterestSummary(
                pair="BTCUSDT",
                state="READY",
                positioning="PRICE_UP_OI_UP",
                trend="EXPANDING",
                funding_context="POSITIVE",
                total_score=-10.0,
            )


class TestDiscoveryInput:
    def test_valid_input(self) -> None:
        rs = DiscoveryRelativeStrengthSummary(
            pair="BTCUSDT", state="READY", decision="OUTPERFORMER", total_score=80.0
        )
        oi = DiscoveryOpenInterestSummary(
            pair="BTCUSDT",
            state="READY",
            positioning="PRICE_UP_OI_UP",
            trend="EXPANDING",
            funding_context="POSITIVE",
            total_score=70.0,
        )
        inp = DiscoveryInput(
            pair="BTCUSDT",
            relative_strength=rs,
            open_interest=oi,
            tags=["tag1", "tag1", "tag2"],
            metadata={"key": "value"},
        )
        assert inp.pair == "BTCUSDT"
        assert inp.input_kind == DiscoveryInputKind.SUMMARY
        assert inp.tags == ("tag1", "tag2")
        assert inp.relative_strength == rs
        assert inp.open_interest == oi

    def test_default_input_kind(self) -> None:
        inp = DiscoveryInput(pair="BTCUSDT")
        assert inp.input_kind == DiscoveryInputKind.SUMMARY

    def test_mismatched_relative_strength_pair(self) -> None:
        rs = DiscoveryRelativeStrengthSummary(
            pair="ETHUSDT", state="READY", decision="OUTPERFORMER", total_score=80.0
        )
        with pytest.raises(ValueError, match="relative_strength.pair must match"):
            DiscoveryInput(pair="BTCUSDT", relative_strength=rs)

    def test_mismatched_open_interest_pair(self) -> None:
        oi = DiscoveryOpenInterestSummary(
            pair="ETHUSDT",
            state="READY",
            positioning="PRICE_UP_OI_UP",
            trend="EXPANDING",
            funding_context="POSITIVE",
            total_score=70.0,
        )
        with pytest.raises(ValueError, match="open_interest.pair must match"):
            DiscoveryInput(pair="BTCUSDT", open_interest=oi)

    def test_invalid_pair(self) -> None:
        with pytest.raises(ValueError, match="pair must be a non-empty string"):
            DiscoveryInput(pair="")


class TestDiscoveryScore:
    def test_valid_score(self) -> None:
        score = DiscoveryScore(
            relative_strength_score=80.0,
            open_interest_score=70.0,
            alignment_score=100.0,
            data_quality_score=100.0,
            filter_bonus_score=100.0,
            total_score=85.0,
            reason_codes=("RS", "OI"),
        )
        assert score.total_score == 85.0

    def test_invalid_subscore(self) -> None:
        with pytest.raises(ValueError, match="relative_strength_score must be in"):
            DiscoveryScore(
                relative_strength_score=101.0,
                open_interest_score=70.0,
                alignment_score=100.0,
                data_quality_score=100.0,
                filter_bonus_score=100.0,
                total_score=85.0,
                reason_codes=(),
            )


class TestDiscoveryUniverseSummary:
    def test_valid_summary(self) -> None:
        summary = DiscoveryUniverseSummary(
            total_inputs=5,
            candidate_count=1,
            watchlist_count=1,
            excluded_count=1,
            insufficient_data_count=1,
            blocked_count=1,
            ready_context_count=2,
            missing_context_count=1,
            blocked_context_count=1,
        )
        assert summary.total_inputs == 5

    def test_counts_must_sum(self) -> None:
        with pytest.raises(ValueError, match="State counts must sum"):
            DiscoveryUniverseSummary(
                total_inputs=5,
                candidate_count=2,
                watchlist_count=1,
                excluded_count=1,
                insufficient_data_count=1,
                blocked_count=1,
                ready_context_count=0,
                missing_context_count=0,
                blocked_context_count=0,
            )

    def test_negative_counts_rejected(self) -> None:
        with pytest.raises(ValueError, match="must be non-negative ints"):
            DiscoveryUniverseSummary(
                total_inputs=1,
                candidate_count=-1,
                watchlist_count=0,
                excluded_count=0,
                insufficient_data_count=0,
                blocked_count=2,
                ready_context_count=0,
                missing_context_count=0,
                blocked_context_count=0,
            )


class TestDiscoveryDataQuality:
    def test_valid_data_quality(self) -> None:
        dq = DiscoveryDataQuality(
            total_inputs=10,
            pairs_with_both_contexts=5,
            pairs_with_missing_relative_strength=2,
            pairs_with_missing_open_interest=2,
            pairs_with_blocked_context=1,
            pairs_with_insufficient_context=1,
            reason_codes=("MISSING",),
        )
        assert dq.total_inputs == 10

    def test_negative_count_rejected(self) -> None:
        with pytest.raises(ValueError, match="must be a non-negative int"):
            DiscoveryDataQuality(
                total_inputs=10,
                pairs_with_both_contexts=-1,
                pairs_with_missing_relative_strength=0,
                pairs_with_missing_open_interest=0,
                pairs_with_blocked_context=0,
                pairs_with_insufficient_context=0,
                reason_codes=(),
            )


class TestDiscoveryReport:
    def test_blocked_factory(self) -> None:
        report = DiscoveryReport.blocked(reason_code=UNSAFE_DISCOVERY_CONTENT)
        assert report.report_id == "blocked"
        assert report.version == DISCOVERY_VERSION
        assert report.candidates == ()
        assert report.universe_summary.total_inputs == 0
        assert report.data_quality.total_inputs == 0
        assert UNSAFE_DISCOVERY_CONTENT in report.reason_codes
        assert report.safety_flags.has_blocked_context is True

    def test_blocked_factory_with_metadata(self) -> None:
        now = datetime.now(timezone.utc)
        report = DiscoveryReport.blocked(
            reason_code=INVALID_PAIR,
            report_id="custom-blocked",
            generated_at=now,
            metadata={"source": "test"},
        )
        assert report.report_id == "custom-blocked"
        assert report.generated_at == now
        assert dict(report.metadata) == {"source": "test"}

    def test_report_reason_code_validation(self) -> None:
        with pytest.raises(ValueError, match="unsupported reason code"):
            DiscoveryReport.blocked(reason_code="NOT_REAL")

    def test_report_is_frozen(self) -> None:
        report = DiscoveryReport.blocked(reason_code=UNSAFE_DISCOVERY_CONTENT)
        with pytest.raises(dataclasses.FrozenInstanceError):
            report.report_id = "changed"


import dataclasses
