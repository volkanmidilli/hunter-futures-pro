"""Tests for hunter.portfolio_construction.models."""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from types import MappingProxyType

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
    INVALID_RESEARCH_WEIGHT,
    LOW_DISCOVERY_SCORE,
    MAX_CANDIDATE_COUNT_EXCEEDED,
    MAX_SINGLE_WEIGHT_CAPPED,
    MISSING_DISCOVERY_CONTEXT,
    NO_ACTION_COMMANDS_EMITTED,
    NO_FILE_READ_IN_ENGINE,
    NO_NETWORK_CONNECTION,
    NOT_PORTFOLIO_APPROVAL,
    NOT_POSITION_SIZING,
    PORTFOLIO_CONSTRUCTION_ADVISORY_REASON_CODES,
    PORTFOLIO_CONSTRUCTION_BLOCKING_REASON_CODES,
    PORTFOLIO_CONSTRUCTION_FILTER_REASON_CODES,
    PORTFOLIO_CONSTRUCTION_INSUFFICIENT_DATA_REASON_CODES,
    PORTFOLIO_CONSTRUCTION_REASON_CODES,
    PORTFOLIO_CONSTRUCTION_VERSION,
    UNSAFE_PORTFOLIO_CONSTRUCTION_CONTENT,
    ZERO_TOTAL_ALLOCATION_SCORE,
    PortfolioConstructionClassification,
    PortfolioConstructionConfig,
    PortfolioConstructionDataQuality,
    PortfolioConstructionInput,
    PortfolioConstructionInputKind,
    PortfolioConstructionReport,
    PortfolioConstructionSafetyFlags,
    PortfolioConstructionScore,
    PortfolioConstructionState,
    PortfolioConstructionUniverseSummary,
    PortfolioDiscoverySummary,
)


class TestVersionAndReasonCodes:
    def test_portfolio_construction_version(self) -> None:
        assert PORTFOLIO_CONSTRUCTION_VERSION == "0.27.0-dev"

    def test_blocking_reason_codes(self) -> None:
        assert INVALID_PAIR in PORTFOLIO_CONSTRUCTION_BLOCKING_REASON_CODES
        assert INVALID_DISCOVERY_SCORE in PORTFOLIO_CONSTRUCTION_BLOCKING_REASON_CODES
        assert INVALID_RESEARCH_WEIGHT in PORTFOLIO_CONSTRUCTION_BLOCKING_REASON_CODES
        assert UNSAFE_PORTFOLIO_CONSTRUCTION_CONTENT in PORTFOLIO_CONSTRUCTION_BLOCKING_REASON_CODES
        assert DISCOVERY_BLOCKED in PORTFOLIO_CONSTRUCTION_BLOCKING_REASON_CODES

    def test_insufficient_data_reason_codes(self) -> None:
        assert MISSING_DISCOVERY_CONTEXT in PORTFOLIO_CONSTRUCTION_INSUFFICIENT_DATA_REASON_CODES
        assert DISCOVERY_INSUFFICIENT_DATA in PORTFOLIO_CONSTRUCTION_INSUFFICIENT_DATA_REASON_CODES

    def test_filter_reason_codes(self) -> None:
        assert LOW_DISCOVERY_SCORE in PORTFOLIO_CONSTRUCTION_FILTER_REASON_CODES
        assert MAX_CANDIDATE_COUNT_EXCEEDED in PORTFOLIO_CONSTRUCTION_FILTER_REASON_CODES
        assert MAX_SINGLE_WEIGHT_CAPPED in PORTFOLIO_CONSTRUCTION_FILTER_REASON_CODES
        assert ZERO_TOTAL_ALLOCATION_SCORE in PORTFOLIO_CONSTRUCTION_FILTER_REASON_CODES
        assert INCLUDED_BY_RESEARCH_CONSTRAINTS in PORTFOLIO_CONSTRUCTION_FILTER_REASON_CODES
        assert CAPPED_BY_RESEARCH_CONSTRAINTS in PORTFOLIO_CONSTRUCTION_FILTER_REASON_CODES
        assert EXCLUDED_BY_RESEARCH_CONSTRAINTS in PORTFOLIO_CONSTRUCTION_FILTER_REASON_CODES

    def test_advisory_reason_codes(self) -> None:
        assert HUMAN_RESEARCH_ONLY in PORTFOLIO_CONSTRUCTION_ADVISORY_REASON_CODES
        assert NOT_PORTFOLIO_APPROVAL in PORTFOLIO_CONSTRUCTION_ADVISORY_REASON_CODES
        assert NOT_POSITION_SIZING in PORTFOLIO_CONSTRUCTION_ADVISORY_REASON_CODES
        assert NO_NETWORK_CONNECTION in PORTFOLIO_CONSTRUCTION_ADVISORY_REASON_CODES
        assert NO_FILE_READ_IN_ENGINE in PORTFOLIO_CONSTRUCTION_ADVISORY_REASON_CODES
        assert NO_ACTION_COMMANDS_EMITTED in PORTFOLIO_CONSTRUCTION_ADVISORY_REASON_CODES

    def test_aggregate_reason_codes(self) -> None:
        assert (
            set(PORTFOLIO_CONSTRUCTION_REASON_CODES)
            == set(
                PORTFOLIO_CONSTRUCTION_BLOCKING_REASON_CODES
                | PORTFOLIO_CONSTRUCTION_INSUFFICIENT_DATA_REASON_CODES
                | PORTFOLIO_CONSTRUCTION_FILTER_REASON_CODES
                | PORTFOLIO_CONSTRUCTION_ADVISORY_REASON_CODES
            )
        )
        assert PORTFOLIO_CONSTRUCTION_REASON_CODES.issuperset(
            PORTFOLIO_CONSTRUCTION_ADVISORY_REASON_CODES
        )

    def test_reason_code_validation_in_report(self) -> None:
        with pytest.raises(ValueError, match="unsupported reason code"):
            PortfolioConstructionReport.blocked(reason_code="NOT_REAL")

    def test_forbidden_terms_are_lowercase(self) -> None:
        for term in FORBIDDEN_PORTFOLIO_CONSTRUCTION_TERMS:
            assert term == term.lower()


class TestEnums:
    def test_state_enum(self) -> None:
        assert PortfolioConstructionState.INCLUDED.value == "INCLUDED"
        assert PortfolioConstructionState.CAPPED.value == "CAPPED"
        assert PortfolioConstructionState.WATCHLIST.value == "WATCHLIST"
        assert PortfolioConstructionState.EXCLUDED.value == "EXCLUDED"
        assert PortfolioConstructionState.INSUFFICIENT_DATA.value == "INSUFFICIENT_DATA"
        assert PortfolioConstructionState.BLOCKED.value == "BLOCKED"

    def test_classification_enum(self) -> None:
        assert PortfolioConstructionClassification.CORE_RESEARCH_ALLOCATION.value == "CORE_RESEARCH_ALLOCATION"
        assert PortfolioConstructionClassification.SATELLITE_RESEARCH_ALLOCATION.value == "SATELLITE_RESEARCH_ALLOCATION"
        assert PortfolioConstructionClassification.WATCHLIST_ALLOCATION.value == "WATCHLIST_ALLOCATION"
        assert PortfolioConstructionClassification.EXCLUDED_BY_CONSTRAINTS.value == "EXCLUDED_BY_CONSTRAINTS"
        assert PortfolioConstructionClassification.INSUFFICIENT_DATA.value == "INSUFFICIENT_DATA"
        assert PortfolioConstructionClassification.BLOCKED.value == "BLOCKED"

    def test_input_kind_enum(self) -> None:
        assert PortfolioConstructionInputKind.SUMMARY.value == "SUMMARY"
        assert PortfolioConstructionInputKind.MANUAL.value == "MANUAL"
        assert PortfolioConstructionInputKind.RISK_CONTEXT.value == "RISK_CONTEXT"


class TestPortfolioConstructionConfig:
    def test_default_config(self) -> None:
        config = PortfolioConstructionConfig()
        assert config.min_discovery_score == 60.0
        assert config.watchlist_score == 45.0
        assert config.core_allocation_score == 75.0
        assert config.satellite_allocation_score == 60.0
        assert config.max_candidate_count == 10
        assert config.max_single_weight_pct == 20.0
        assert config.total_research_weight_pct == 100.0
        assert dict(config.score_weights) == {
            "discovery_score_component": 0.45,
            "data_quality_score": 0.15,
            "diversification_component": 0.15,
            "cap_readiness_score": 0.15,
            "filter_bonus_score": 0.10,
        }

    def test_weights_must_sum_to_one(self) -> None:
        with pytest.raises(ValueError, match="must sum to 1.0"):
            PortfolioConstructionConfig(
                score_weights={
                    "discovery_score_component": 0.45,
                    "data_quality_score": 0.15,
                    "diversification_component": 0.15,
                    "cap_readiness_score": 0.15,
                    "filter_bonus_score": 0.11,
                }
            )

    def test_weights_must_have_exact_keys(self) -> None:
        with pytest.raises(ValueError, match="score_weights must have exactly"):
            PortfolioConstructionConfig(
                score_weights={
                    "discovery_score_component": 0.45,
                    "data_quality_score": 0.15,
                    "diversification_component": 0.15,
                    "cap_readiness_score": 0.25,
                }
            )

    def test_weights_out_of_range(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            PortfolioConstructionConfig(
                score_weights={
                    "discovery_score_component": 1.45,
                    "data_quality_score": 0.0,
                    "diversification_component": 0.0,
                    "cap_readiness_score": 0.0,
                    "filter_bonus_score": -0.45,
                }
            )

    def test_thresholds_must_be_ordered(self) -> None:
        with pytest.raises(ValueError, match="core_allocation_score >"):
            PortfolioConstructionConfig(
                core_allocation_score=50.0,
                satellite_allocation_score=60.0,
                watchlist_score=45.0,
            )

    def test_thresholds_in_bounds(self) -> None:
        with pytest.raises(ValueError, match="min_discovery_score must be in"):
            PortfolioConstructionConfig(min_discovery_score=-1.0)
        with pytest.raises(ValueError, match="total_research_weight_pct must be in"):
            PortfolioConstructionConfig(total_research_weight_pct=0.0)
        with pytest.raises(ValueError, match="max_single_weight_pct must be in"):
            PortfolioConstructionConfig(max_single_weight_pct=101.0)
        with pytest.raises(ValueError, match="max_candidate_count must be a non-negative"):
            PortfolioConstructionConfig(max_candidate_count=-1)

    def test_config_is_frozen(self) -> None:
        config = PortfolioConstructionConfig()
        with pytest.raises(dataclasses.FrozenInstanceError):
            config.min_discovery_score = 0.0

    def test_score_weights_immutable(self) -> None:
        config = PortfolioConstructionConfig()
        with pytest.raises(TypeError):
            config.score_weights["discovery_score_component"] = 0.5


class TestPortfolioConstructionSafetyFlags:
    def test_is_safe_all_true(self) -> None:
        flags = PortfolioConstructionSafetyFlags()
        assert flags.is_safe is True
        assert flags.safety_flags_ok is True

    def test_is_safe_unsafe_content(self) -> None:
        flags = PortfolioConstructionSafetyFlags(has_unsafe_content=True)
        assert flags.is_safe is False

    def test_is_safe_invalid_pair(self) -> None:
        flags = PortfolioConstructionSafetyFlags(has_invalid_pair=True)
        assert flags.is_safe is False

    def test_is_safe_invalid_score(self) -> None:
        flags = PortfolioConstructionSafetyFlags(has_invalid_score=True)
        assert flags.is_safe is False

    def test_is_safe_blocked_context(self) -> None:
        flags = PortfolioConstructionSafetyFlags(has_blocked_context=True)
        assert flags.is_safe is False

    def test_is_safe_missing_context(self) -> None:
        flags = PortfolioConstructionSafetyFlags(has_missing_required_context=True)
        assert flags.is_safe is False

    def test_is_safe_inconsistent_state(self) -> None:
        flags = PortfolioConstructionSafetyFlags(has_inconsistent_state=True)
        assert flags.is_safe is False

    def test_is_safe_required_flag_false(self) -> None:
        flags = PortfolioConstructionSafetyFlags(no_network_connection=False)
        assert flags.is_safe is False


class TestPortfolioDiscoverySummary:
    def test_valid_summary(self) -> None:
        summary = PortfolioDiscoverySummary(
            pair="SOL/USDT:USDT",
            state="CANDIDATE",
            classification="STRONG_RESEARCH_CANDIDATE",
            discovery_score=80.0,
            reason_codes=("RS",),
            tags=("layer1",),
            metadata={"source": "discovery"},
        )
        assert summary.pair == "SOL/USDT:USDT"
        assert summary.discovery_score == 80.0
        assert summary.reason_codes == ("RS",)
        assert summary.tags == ("layer1",)
        assert isinstance(summary.metadata, MappingProxyType)

    def test_invalid_pair(self) -> None:
        with pytest.raises(ValueError, match="pair must be a non-empty string"):
            PortfolioDiscoverySummary(
                pair="",
                state="CANDIDATE",
                classification="STRONG_RESEARCH_CANDIDATE",
                discovery_score=80.0,
            )

    def test_invalid_discovery_score(self) -> None:
        with pytest.raises(ValueError, match="discovery_score must be in"):
            PortfolioDiscoverySummary(
                pair="SOL/USDT:USDT",
                state="CANDIDATE",
                classification="STRONG_RESEARCH_CANDIDATE",
                discovery_score=150.0,
            )

    def test_reason_codes_and_tags_normalized(self) -> None:
        summary = PortfolioDiscoverySummary(
            pair="SOL/USDT:USDT",
            state="CANDIDATE",
            classification="STRONG_RESEARCH_CANDIDATE",
            discovery_score=80.0,
            reason_codes=["A", "A", "B"],
            tags=["x", "x", "y"],
        )
        assert summary.reason_codes == ("A", "B")
        assert summary.tags == ("x", "y")


class TestPortfolioConstructionInput:
    def test_valid_input(self) -> None:
        discovery = PortfolioDiscoverySummary(
            pair="SOL/USDT:USDT",
            state="CANDIDATE",
            classification="STRONG_RESEARCH_CANDIDATE",
            discovery_score=80.0,
        )
        inp = PortfolioConstructionInput(
            pair="SOL/USDT:USDT",
            discovery=discovery,
            tags=["tag1", "tag1", "tag2"],
            metadata={"key": "value"},
        )
        assert inp.pair == "SOL/USDT:USDT"
        assert inp.input_kind == PortfolioConstructionInputKind.SUMMARY
        assert inp.tags == ("tag1", "tag2")
        assert inp.discovery == discovery
        assert isinstance(inp.metadata, MappingProxyType)

    def test_default_input_kind(self) -> None:
        inp = PortfolioConstructionInput(pair="SOL/USDT:USDT")
        assert inp.input_kind == PortfolioConstructionInputKind.SUMMARY
        assert inp.discovery is None

    def test_mismatched_pair(self) -> None:
        discovery = PortfolioDiscoverySummary(
            pair="BTC/USDT:USDT",
            state="CANDIDATE",
            classification="STRONG_RESEARCH_CANDIDATE",
            discovery_score=80.0,
        )
        with pytest.raises(ValueError, match="discovery.pair must match"):
            PortfolioConstructionInput(pair="SOL/USDT:USDT", discovery=discovery)

    def test_invalid_pair(self) -> None:
        with pytest.raises(ValueError, match="pair must be a non-empty string"):
            PortfolioConstructionInput(pair="")

    def test_tags_normalized(self) -> None:
        inp = PortfolioConstructionInput(pair="SOL/USDT:USDT", tags=["a", "a", "b"])
        assert inp.tags == ("a", "b")


class TestPortfolioConstructionScore:
    def test_valid_score(self) -> None:
        score = PortfolioConstructionScore(
            pair="SOL/USDT:USDT",
            state=PortfolioConstructionState.INCLUDED,
            classification=PortfolioConstructionClassification.CORE_RESEARCH_ALLOCATION,
            allocation_score=85.0,
            discovery_score_component=80.0,
            data_quality_score=100.0,
            diversification_component=100.0,
            cap_readiness_score=100.0,
            filter_bonus_score=100.0,
            initial_research_weight_pct=20.0,
            capped_weight_pct=0.0,
            final_weight_pct=20.0,
            reason_codes=(INCLUDED_BY_RESEARCH_CONSTRAINTS,),
            tags=(),
            metadata={},
            notes=(),
            rank=1,
        )
        assert score.allocation_score == 85.0

    def test_invalid_subscore(self) -> None:
        with pytest.raises(ValueError, match="allocation_score must be in"):
            PortfolioConstructionScore(
                pair="SOL/USDT:USDT",
                state=PortfolioConstructionState.INCLUDED,
                classification=PortfolioConstructionClassification.CORE_RESEARCH_ALLOCATION,
                allocation_score=101.0,
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

    def test_invalid_weight(self) -> None:
        with pytest.raises(ValueError, match="final_weight_pct must be in"):
            PortfolioConstructionScore(
                pair="SOL/USDT:USDT",
                state=PortfolioConstructionState.INCLUDED,
                classification=PortfolioConstructionClassification.CORE_RESEARCH_ALLOCATION,
                allocation_score=85.0,
                discovery_score_component=80.0,
                data_quality_score=100.0,
                diversification_component=100.0,
                cap_readiness_score=100.0,
                filter_bonus_score=100.0,
                initial_research_weight_pct=0.0,
                capped_weight_pct=0.0,
                final_weight_pct=101.0,
                reason_codes=(),
                tags=(),
                metadata={},
                notes=(),
                rank=None,
            )


class TestPortfolioConstructionUniverseSummary:
    def test_valid_summary(self) -> None:
        summary = PortfolioConstructionUniverseSummary(
            total_candidates=6,
            included_count=1,
            capped_count=1,
            watchlist_count=1,
            excluded_count=1,
            insufficient_data_count=1,
            blocked_count=1,
            core_allocation_count=1,
            satellite_allocation_count=1,
            watchlist_allocation_count=1,
            total_final_weight_pct=40.0,
            top_pair="SOL/USDT:USDT",
            notes=(),
        )
        assert summary.total_candidates == 6

    def test_counts_must_sum(self) -> None:
        with pytest.raises(ValueError, match="State counts must sum"):
            PortfolioConstructionUniverseSummary(
                total_candidates=5,
                included_count=2,
                capped_count=1,
                watchlist_count=1,
                excluded_count=1,
                insufficient_data_count=1,
                blocked_count=1,
                core_allocation_count=1,
                satellite_allocation_count=1,
                watchlist_allocation_count=1,
                total_final_weight_pct=0.0,
                top_pair=None,
                notes=(),
            )

    def test_negative_counts_rejected(self) -> None:
        with pytest.raises(ValueError, match="must be a non-negative int"):
            PortfolioConstructionUniverseSummary(
                total_candidates=1,
                included_count=-1,
                capped_count=0,
                watchlist_count=0,
                excluded_count=0,
                insufficient_data_count=0,
                blocked_count=2,
                core_allocation_count=0,
                satellite_allocation_count=0,
                watchlist_allocation_count=0,
                total_final_weight_pct=0.0,
                top_pair=None,
                notes=(),
            )

    def test_total_final_weight_out_of_bounds(self) -> None:
        with pytest.raises(ValueError, match="total_final_weight_pct must be in"):
            PortfolioConstructionUniverseSummary(
                total_candidates=1,
                included_count=1,
                capped_count=0,
                watchlist_count=0,
                excluded_count=0,
                insufficient_data_count=0,
                blocked_count=0,
                core_allocation_count=1,
                satellite_allocation_count=0,
                watchlist_allocation_count=0,
                total_final_weight_pct=101.0,
                top_pair=None,
                notes=(),
            )


class TestPortfolioConstructionDataQuality:
    def test_valid_data_quality(self) -> None:
        dq = PortfolioConstructionDataQuality(
            total_inputs=10,
            included_count=2,
            capped_count=1,
            watchlist_count=2,
            excluded_count=3,
            insufficient_data_count=1,
            blocked_count=1,
            ready_context_count=8,
            missing_context_count=1,
            blocked_context_count=1,
            total_final_weight_pct=60.0,
            total_research_weight_pct=100.0,
            data_quality_score=80.0,
            sections_present=5,
            all_sections_present=True,
            all_counts_consistent=True,
            total_weight_within_tolerance=True,
            has_unsafe_content=False,
            safety_flags_ok=True,
        )
        assert dq.total_inputs == 10

    def test_counts_must_sum(self) -> None:
        with pytest.raises(ValueError, match="State counts must sum"):
            PortfolioConstructionDataQuality(
                total_inputs=5,
                included_count=2,
                capped_count=1,
                watchlist_count=1,
                excluded_count=1,
                insufficient_data_count=1,
                blocked_count=1,
                ready_context_count=0,
                missing_context_count=0,
                blocked_context_count=0,
                total_final_weight_pct=0.0,
                total_research_weight_pct=100.0,
                data_quality_score=0.0,
                sections_present=0,
                all_sections_present=False,
                all_counts_consistent=True,
                total_weight_within_tolerance=True,
                has_unsafe_content=False,
                safety_flags_ok=True,
            )

    def test_negative_count_rejected(self) -> None:
        with pytest.raises(ValueError, match="must be a non-negative int"):
            PortfolioConstructionDataQuality(
                total_inputs=1,
                included_count=-1,
                capped_count=0,
                watchlist_count=0,
                excluded_count=0,
                insufficient_data_count=0,
                blocked_count=2,
                ready_context_count=0,
                missing_context_count=0,
                blocked_context_count=0,
                total_final_weight_pct=0.0,
                total_research_weight_pct=100.0,
                data_quality_score=0.0,
                sections_present=0,
                all_sections_present=False,
                all_counts_consistent=True,
                total_weight_within_tolerance=True,
                has_unsafe_content=False,
                safety_flags_ok=True,
            )

    def test_total_final_weight_out_of_bounds(self) -> None:
        with pytest.raises(ValueError, match="total_final_weight_pct must be in"):
            PortfolioConstructionDataQuality(
                total_inputs=1,
                included_count=1,
                capped_count=0,
                watchlist_count=0,
                excluded_count=0,
                insufficient_data_count=0,
                blocked_count=0,
                ready_context_count=1,
                missing_context_count=0,
                blocked_context_count=0,
                total_final_weight_pct=101.0,
                total_research_weight_pct=100.0,
                data_quality_score=100.0,
                sections_present=5,
                all_sections_present=True,
                all_counts_consistent=True,
                total_weight_within_tolerance=True,
                has_unsafe_content=False,
                safety_flags_ok=True,
            )

    def test_data_quality_score_out_of_bounds(self) -> None:
        with pytest.raises(ValueError, match="data_quality_score must be in"):
            PortfolioConstructionDataQuality(
                total_inputs=1,
                included_count=1,
                capped_count=0,
                watchlist_count=0,
                excluded_count=0,
                insufficient_data_count=0,
                blocked_count=0,
                ready_context_count=1,
                missing_context_count=0,
                blocked_context_count=0,
                total_final_weight_pct=0.0,
                total_research_weight_pct=100.0,
                data_quality_score=101.0,
                sections_present=5,
                all_sections_present=True,
                all_counts_consistent=True,
                total_weight_within_tolerance=True,
                has_unsafe_content=False,
                safety_flags_ok=True,
            )


class TestPortfolioConstructionReport:
    def test_blocked_factory(self) -> None:
        report = PortfolioConstructionReport.blocked(
            reason_code=UNSAFE_PORTFOLIO_CONSTRUCTION_CONTENT
        )
        assert report.report_id == "blocked"
        assert report.version == PORTFOLIO_CONSTRUCTION_VERSION
        assert report.scores == ()
        assert report.inputs == ()
        assert UNSAFE_PORTFOLIO_CONSTRUCTION_CONTENT in report.reason_codes
        assert report.safety_flags.has_unsafe_content is True
        assert report.safety_flags.is_safe is False
        assert report.data_quality.has_unsafe_content is True
        assert report.data_quality.safety_flags_ok is False
        assert report.data_quality.total_inputs == 0

    def test_blocked_factory_with_metadata(self) -> None:
        now = datetime.now(timezone.utc)
        report = PortfolioConstructionReport.blocked(
            reason_code=INVALID_PAIR,
            report_id="custom-blocked",
            generated_at=now,
            metadata={"source": "test"},
        )
        assert report.report_id == "custom-blocked"
        assert report.generated_at == now
        assert dict(report.metadata) == {"source": "test"}

    def test_blocked_factory_invalid_reason_code(self) -> None:
        with pytest.raises(ValueError, match="unsupported reason code"):
            PortfolioConstructionReport.blocked(reason_code="FAKE")

    def test_report_is_frozen(self) -> None:
        report = PortfolioConstructionReport.blocked(
            reason_code=UNSAFE_PORTFOLIO_CONSTRUCTION_CONTENT
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            report.report_id = "changed"
