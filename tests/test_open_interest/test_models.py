"""Tests for hunter.open_interest.models."""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from types import MappingProxyType

import pytest

from hunter.open_interest.models import (
    BLOCKED_BY_SAFETY_FLAGS,
    FORBIDDEN_OPEN_INTEREST_TERMS,
    FUNDING_CONTEXT_MISSING,
    HUMAN_RESEARCH_ONLY,
    INPUTS_ALREADY_LOADED,
    INSUFFICIENT_OI_DATA,
    INVALID_OPEN_INTEREST,
    INVALID_PAIR,
    INVALID_PRICE_DATA,
    INVALID_TIMESTAMP,
    NO_ACTION_COMMANDS_EMITTED,
    NO_DATABASE_CONNECTION,
    NO_FILE_READ_IN_ENGINE,
    NO_NETWORK_CONNECTION,
    OPEN_INTEREST_ADVISORY_REASON_CODES,
    OPEN_INTEREST_BLOCKING_REASON_CODES,
    OPEN_INTEREST_INSUFFICIENT_DATA_REASON_CODES,
    OPEN_INTEREST_REASON_CODES,
    OPEN_INTEREST_VERSION,
    PERIOD_DATA_MISSING,
    UNSAFE_OPEN_INTEREST_CONTENT,
    ZERO_DENOMINATOR,
    OpenInterestConfig,
    OpenInterestDataQuality,
    OpenInterestFundingContext,
    OpenInterestInput,
    OpenInterestObservation,
    OpenInterestPeriodChange,
    OpenInterestPositioning,
    OpenInterestReport,
    OpenInterestSafetyFlags,
    OpenInterestScore,
    OpenInterestState,
    OpenInterestTrend,
    OpenInterestUniverseSummary,
)


class TestVersionAndReasonCodes:
    def test_open_interest_version(self) -> None:
        assert OPEN_INTEREST_VERSION == "1.0"

    def test_blocking_reason_codes(self) -> None:
        assert UNSAFE_OPEN_INTEREST_CONTENT in OPEN_INTEREST_BLOCKING_REASON_CODES
        assert INVALID_PAIR in OPEN_INTEREST_BLOCKING_REASON_CODES
        assert INVALID_TIMESTAMP in OPEN_INTEREST_BLOCKING_REASON_CODES
        assert INVALID_OPEN_INTEREST in OPEN_INTEREST_BLOCKING_REASON_CODES
        assert INVALID_PRICE_DATA in OPEN_INTEREST_BLOCKING_REASON_CODES
        assert INSUFFICIENT_OI_DATA in OPEN_INTEREST_BLOCKING_REASON_CODES
        assert ZERO_DENOMINATOR in OPEN_INTEREST_BLOCKING_REASON_CODES
        assert BLOCKED_BY_SAFETY_FLAGS in OPEN_INTEREST_BLOCKING_REASON_CODES

    def test_insufficient_data_reason_codes(self) -> None:
        assert INSUFFICIENT_OI_DATA in OPEN_INTEREST_INSUFFICIENT_DATA_REASON_CODES
        assert PERIOD_DATA_MISSING in OPEN_INTEREST_INSUFFICIENT_DATA_REASON_CODES
        assert FUNDING_CONTEXT_MISSING in OPEN_INTEREST_INSUFFICIENT_DATA_REASON_CODES

    def test_advisory_reason_codes(self) -> None:
        assert INPUTS_ALREADY_LOADED in OPEN_INTEREST_ADVISORY_REASON_CODES
        assert NO_ACTION_COMMANDS_EMITTED in OPEN_INTEREST_ADVISORY_REASON_CODES
        assert HUMAN_RESEARCH_ONLY in OPEN_INTEREST_ADVISORY_REASON_CODES
        assert NO_NETWORK_CONNECTION in OPEN_INTEREST_ADVISORY_REASON_CODES
        assert NO_DATABASE_CONNECTION in OPEN_INTEREST_ADVISORY_REASON_CODES
        assert NO_FILE_READ_IN_ENGINE in OPEN_INTEREST_ADVISORY_REASON_CODES

    def test_aggregate_reason_codes_deduplicated(self) -> None:
        # INSUFFICIENT_OI_DATA appears in both blocking and insufficient partitions.
        assert set(OPEN_INTEREST_REASON_CODES) == set(
            OPEN_INTEREST_BLOCKING_REASON_CODES
            + OPEN_INTEREST_INSUFFICIENT_DATA_REASON_CODES
            + OPEN_INTEREST_ADVISORY_REASON_CODES
        )
        # No duplicates in the aggregate tuple.
        assert len(OPEN_INTEREST_REASON_CODES) == len(set(OPEN_INTEREST_REASON_CODES))
        # Deterministic order: blocking first, then insufficient, then advisory.
        assert OPEN_INTEREST_REASON_CODES[0] == OPEN_INTEREST_BLOCKING_REASON_CODES[0]
        # INSUFFICIENT_OI_DATA appears only once, at the blocking position.
        indices = [i for i, code in enumerate(OPEN_INTEREST_REASON_CODES) if code == INSUFFICIENT_OI_DATA]
        assert len(indices) == 1
        assert indices[0] == OPEN_INTEREST_BLOCKING_REASON_CODES.index(INSUFFICIENT_OI_DATA)

    def test_reason_code_validation(self) -> None:
        # OpenInterestReport.blocked validates the reason code.
        with pytest.raises(ValueError, match="unsupported reason code"):
            OpenInterestReport.blocked(reason_code="NOT_A_REAL_CODE")


class TestEnums:
    def test_state_enum(self) -> None:
        assert OpenInterestState.READY.value == "ready"
        assert OpenInterestState.INSUFFICIENT_DATA.value == "insufficient_data"
        assert OpenInterestState.BLOCKED.value == "blocked"

    def test_positioning_enum(self) -> None:
        assert OpenInterestPositioning.PRICE_UP_OI_UP.value == "price_up_oi_up"
        assert OpenInterestPositioning.PRICE_UP_OI_DOWN.value == "price_up_oi_down"
        assert OpenInterestPositioning.PRICE_DOWN_OI_UP.value == "price_down_oi_up"
        assert OpenInterestPositioning.PRICE_DOWN_OI_DOWN.value == "price_down_oi_down"
        assert OpenInterestPositioning.MIXED.value == "mixed"
        assert OpenInterestPositioning.INSUFFICIENT_DATA.value == "insufficient_data"
        assert OpenInterestPositioning.BLOCKED.value == "blocked"

    def test_trend_enum(self) -> None:
        assert OpenInterestTrend.EXPANDING.value == "expanding"
        assert OpenInterestTrend.CONTRACTING.value == "contracting"
        assert OpenInterestTrend.FLAT.value == "flat"
        assert OpenInterestTrend.UNSTABLE.value == "unstable"
        assert OpenInterestTrend.INSUFFICIENT_DATA.value == "insufficient_data"
        assert OpenInterestTrend.BLOCKED.value == "blocked"

    def test_funding_context_enum(self) -> None:
        assert OpenInterestFundingContext.POSITIVE.value == "positive"
        assert OpenInterestFundingContext.NEGATIVE.value == "negative"
        assert OpenInterestFundingContext.NEUTRAL.value == "neutral"
        assert OpenInterestFundingContext.MISSING.value == "missing"
        assert OpenInterestFundingContext.INSUFFICIENT_DATA.value == "insufficient_data"
        assert OpenInterestFundingContext.BLOCKED.value == "blocked"


class TestForbiddenTerms:
    def test_forbidden_terms_populated(self) -> None:
        assert "binance" in FORBIDDEN_OPEN_INTEREST_TERMS
        assert "exchange_api" in FORBIDDEN_OPEN_INTEREST_TERMS
        assert "leverage" in FORBIDDEN_OPEN_INTEREST_TERMS
        assert "shorting" in FORBIDDEN_OPEN_INTEREST_TERMS
        assert "buy" in FORBIDDEN_OPEN_INTEREST_TERMS
        assert "sell" in FORBIDDEN_OPEN_INTEREST_TERMS
        assert "api_key" in FORBIDDEN_OPEN_INTEREST_TERMS
        assert "database" in FORBIDDEN_OPEN_INTEREST_TERMS

    def test_forbidden_terms_frozenset(self) -> None:
        assert isinstance(FORBIDDEN_OPEN_INTEREST_TERMS, frozenset)
        assert all(isinstance(term, str) for term in FORBIDDEN_OPEN_INTEREST_TERMS)


class TestOpenInterestObservation:
    def _make_dt(self, day: int = 1) -> datetime:
        return datetime(2026, 7, day, tzinfo=timezone.utc)

    def test_valid_construction(self) -> None:
        obs = OpenInterestObservation(
            timestamp=self._make_dt(),
            open_interest=1_000_000.0,
            close=100.0,
        )
        assert obs.timestamp == self._make_dt()
        assert obs.open_interest == 1_000_000.0
        assert obs.close == 100.0
        assert obs.funding_rate is None
        assert obs.metadata == {}

    def test_with_funding_rate(self) -> None:
        obs = OpenInterestObservation(
            timestamp=self._make_dt(),
            open_interest=1_000_000.0,
            close=100.0,
            funding_rate=0.0001,
        )
        assert obs.funding_rate == 0.0001

    def test_metadata_is_mapping_proxy(self) -> None:
        obs = OpenInterestObservation(
            timestamp=self._make_dt(),
            open_interest=1_000_000.0,
            close=100.0,
            metadata={"source": "test"},
        )
        assert isinstance(obs.metadata, MappingProxyType)

    def test_invalid_naive_timestamp(self) -> None:
        with pytest.raises(ValueError, match="timezone-aware"):
            OpenInterestObservation(
                timestamp=datetime(2026, 7, 1),
                open_interest=1_000_000.0,
                close=100.0,
            )

    def test_invalid_open_interest_negative(self) -> None:
        with pytest.raises(ValueError, match="open_interest"):
            OpenInterestObservation(
                timestamp=self._make_dt(),
                open_interest=-1.0,
                close=100.0,
            )

    def test_invalid_open_interest_non_finite(self) -> None:
        with pytest.raises(ValueError, match="open_interest"):
            OpenInterestObservation(
                timestamp=self._make_dt(),
                open_interest=float("inf"),
                close=100.0,
            )

    def test_invalid_close_zero(self) -> None:
        with pytest.raises(ValueError, match="close"):
            OpenInterestObservation(
                timestamp=self._make_dt(),
                open_interest=1_000_000.0,
                close=0.0,
            )

    def test_invalid_close_negative(self) -> None:
        with pytest.raises(ValueError, match="close"):
            OpenInterestObservation(
                timestamp=self._make_dt(),
                open_interest=1_000_000.0,
                close=-5.0,
            )

    def test_invalid_close_non_finite(self) -> None:
        with pytest.raises(ValueError, match="close"):
            OpenInterestObservation(
                timestamp=self._make_dt(),
                open_interest=1_000_000.0,
                close=float("nan"),
            )

    def test_invalid_funding_rate_non_finite(self) -> None:
        with pytest.raises(ValueError, match="funding_rate"):
            OpenInterestObservation(
                timestamp=self._make_dt(),
                open_interest=1_000_000.0,
                close=100.0,
                funding_rate=float("inf"),
            )

    def test_frozen_cannot_mutate(self) -> None:
        obs = OpenInterestObservation(
            timestamp=self._make_dt(),
            open_interest=1_000_000.0,
            close=100.0,
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            obs.close = 200.0  # type: ignore[misc]

    def test_non_numeric_open_interest(self) -> None:
        with pytest.raises(ValueError, match="open_interest"):
            OpenInterestObservation(
                timestamp=self._make_dt(),
                open_interest="not a number",  # type: ignore[arg-type]
                close=100.0,
            )

    def test_non_numeric_close(self) -> None:
        with pytest.raises(ValueError, match="close"):
            OpenInterestObservation(
                timestamp=self._make_dt(),
                open_interest=1_000_000.0,
                close="not a number",  # type: ignore[arg-type]
            )

    def test_boolean_values_rejected(self) -> None:
        with pytest.raises(ValueError, match="open_interest"):
            OpenInterestObservation(
                timestamp=self._make_dt(),
                open_interest=True,  # type: ignore[arg-type]
                close=100.0,
            )


class TestOpenInterestInput:
    def _obs(self, day: int = 1, close: float = 100.0) -> OpenInterestObservation:
        return OpenInterestObservation(
            timestamp=datetime(2026, 7, day, tzinfo=timezone.utc),
            open_interest=1_000_000.0,
            close=close,
        )

    def test_valid_construction(self) -> None:
        inp = OpenInterestInput(pair="BTCUSDT", rows=[self._obs()])
        assert inp.pair == "BTCUSDT"
        assert len(inp.rows) == 1
        assert isinstance(inp.rows, tuple)

    def test_empty_pair(self) -> None:
        with pytest.raises(ValueError, match="pair"):
            OpenInterestInput(pair="", rows=[self._obs()])

    def test_rows_normalized_to_tuple(self) -> None:
        inp = OpenInterestInput(pair="BTCUSDT", rows=[self._obs()])
        assert isinstance(inp.rows, tuple)

    def test_metadata_is_mapping_proxy(self) -> None:
        inp = OpenInterestInput(pair="BTCUSDT", rows=[self._obs()], metadata={"a": "b"})
        assert isinstance(inp.metadata, MappingProxyType)

    def test_invalid_rows_type(self) -> None:
        with pytest.raises(ValueError, match="rows"):
            OpenInterestInput(pair="BTCUSDT", rows="not a sequence")  # type: ignore[arg-type]

    def test_invalid_row_element(self) -> None:
        with pytest.raises(ValueError, match="rows"):
            OpenInterestInput(pair="BTCUSDT", rows=[self._obs(), "not an obs"])  # type: ignore[list-item]


class TestOpenInterestConfig:
    def test_default_config(self) -> None:
        config = OpenInterestConfig()
        assert config.lookback_periods == (1, 3, 7, 14)
        assert config.positioning_threshold == 0.001
        assert config.oi_change_bounds == (-0.30, 0.30)
        assert config.price_change_bounds == (-0.20, 0.20)
        assert config.funding_rate_bounds == (-0.01, 0.01)
        assert config.min_required_rows == 15
        assert config.block_on_missing_data is False
        assert round(sum(config.score_weights.values()), 9) == 1.0
        assert config.rounding_policy == "standard"
        assert config.version == "1.0"

    def test_weight_validation(self) -> None:
        with pytest.raises(ValueError, match="score_weights"):
            OpenInterestConfig(score_weights={"oi_7d_change": 0.5})

    def test_weight_keys_non_empty(self) -> None:
        with pytest.raises(ValueError, match="score_weights"):
            OpenInterestConfig(score_weights={"": 1.0})

    def test_lookback_periods_positive(self) -> None:
        with pytest.raises(ValueError, match="lookback_periods"):
            OpenInterestConfig(lookback_periods=(0, 3, 7, 14))

    def test_bounds_validation(self) -> None:
        with pytest.raises(ValueError, match="oi_change_bounds"):
            OpenInterestConfig(oi_change_bounds=(0.30, -0.30))
        with pytest.raises(ValueError, match="price_change_bounds"):
            OpenInterestConfig(price_change_bounds=(0.20, -0.20))
        with pytest.raises(ValueError, match="funding_rate_bounds"):
            OpenInterestConfig(funding_rate_bounds=(0.01, -0.01))

    def test_min_required_rows_at_least_one(self) -> None:
        with pytest.raises(ValueError, match="min_required_rows"):
            OpenInterestConfig(min_required_rows=0)

    def test_positioning_threshold_non_negative(self) -> None:
        with pytest.raises(ValueError, match="positioning_threshold"):
            OpenInterestConfig(positioning_threshold=-0.001)

    def test_non_numeric_bounds_rejected(self) -> None:
        with pytest.raises(ValueError, match="oi_change_bounds"):
            OpenInterestConfig(oi_change_bounds=("-0.30", 0.30))  # type: ignore[arg-type]


class TestOpenInterestSafetyFlags:
    def test_default_flags_fail_closed(self) -> None:
        flags = OpenInterestSafetyFlags()
        assert flags.human_research_only is True
        assert flags.output_is_human_research_only is True
        assert flags.output_not_trading_signal is True
        assert flags.output_not_trade_approval is True
        assert flags.output_not_strategy_approval is True
        assert flags.output_not_execution_approval is True
        assert flags.output_not_portfolio_approval is True
        assert flags.output_not_universe_approval is True
        assert flags.output_not_freqtrade_input is True
        assert flags.output_not_order_input is True
        assert flags.output_not_exchange_input is True
        assert flags.no_action_commands_emitted is True
        assert flags.inputs_already_loaded is True
        assert flags.benchmarks_provided_by_caller is True

        assert flags.file_write_enabled is False
        assert flags.file_read_enabled is False
        assert flags.network_enabled is False
        assert flags.database_enabled is False
        assert flags.event_store_enabled is False
        assert flags.runtime_registry_enabled is False
        assert flags.task_runner_enabled is False
        assert flags.indexer_crawler_enabled is False
        assert flags.feedback_into_execution is False
        assert flags.feedback_into_strategy is False
        assert flags.feedback_into_portfolio is False
        assert flags.feedback_into_freqtrade is False
        assert flags.leverage_enabled is False
        assert flags.shorting_enabled is False
        assert flags.real_orders_enabled is False
        assert flags.live_trading_enabled is False

    def test_unsafe_flag_raises(self) -> None:
        unsafe_flags = [
            "file_write_enabled",
            "file_read_enabled",
            "network_enabled",
            "database_enabled",
            "event_store_enabled",
            "runtime_registry_enabled",
            "task_runner_enabled",
            "indexer_crawler_enabled",
            "feedback_into_execution",
            "feedback_into_strategy",
            "feedback_into_portfolio",
            "feedback_into_freqtrade",
            "leverage_enabled",
            "shorting_enabled",
            "real_orders_enabled",
            "live_trading_enabled",
        ]
        for flag_name in unsafe_flags:
            with pytest.raises(ValueError, match="unsafe open interest safety flags"):
                OpenInterestSafetyFlags(**{flag_name: True})

    def test_safe_flags_must_be_true(self) -> None:
        safe_flags = [
            "human_research_only",
            "output_is_human_research_only",
            "output_not_trading_signal",
            "output_not_trade_approval",
            "output_not_strategy_approval",
            "output_not_execution_approval",
            "output_not_portfolio_approval",
            "output_not_universe_approval",
            "output_not_freqtrade_input",
            "output_not_order_input",
            "output_not_exchange_input",
            "no_action_commands_emitted",
            "inputs_already_loaded",
            "benchmarks_provided_by_caller",
        ]
        for flag_name in safe_flags:
            with pytest.raises(ValueError, match="safe open interest output flags"):
                OpenInterestSafetyFlags(**{flag_name: False})


class TestOpenInterestDataQuality:
    def test_valid_construction(self) -> None:
        dq = OpenInterestDataQuality(
            expected_rows=15,
            actual_rows=10,
            missing_rows=5,
            min_required_rows_met=False,
            stale_input_count=0,
            reason_codes=(INSUFFICIENT_OI_DATA,),
        )
        assert dq.expected_rows == 15
        assert dq.missing_rows == 5

    def test_missing_rows_cannot_exceed_expected(self) -> None:
        with pytest.raises(ValueError, match="missing_rows"):
            OpenInterestDataQuality(
                expected_rows=10,
                actual_rows=1,
                missing_rows=15,
                min_required_rows_met=False,
                stale_input_count=0,
                reason_codes=(),
            )

    def test_negative_counts_rejected(self) -> None:
        with pytest.raises(ValueError, match="expected_rows"):
            OpenInterestDataQuality(
                expected_rows=-1,
                actual_rows=0,
                missing_rows=0,
                min_required_rows_met=False,
                stale_input_count=0,
                reason_codes=(),
            )

    def test_invalid_reason_code_rejected(self) -> None:
        with pytest.raises(ValueError, match="unsupported reason code"):
            OpenInterestDataQuality(
                expected_rows=15,
                actual_rows=10,
                missing_rows=5,
                min_required_rows_met=False,
                stale_input_count=0,
                reason_codes=("NOT_A_CODE",),
            )


class TestOpenInterestPeriodChange:
    def test_valid_construction(self) -> None:
        pc = OpenInterestPeriodChange(
            period=7,
            oi_change=0.05,
            price_change=0.03,
            has_data=True,
            reason_codes=(),
        )
        assert pc.period == 7
        assert pc.has_data is True

    def test_invalid_period(self) -> None:
        with pytest.raises(ValueError, match="period"):
            OpenInterestPeriodChange(
                period=0,
                oi_change=None,
                price_change=None,
                has_data=False,
                reason_codes=(),
            )


class TestOpenInterestScore:
    def _obs(self, day: int = 1, close: float = 100.0) -> OpenInterestObservation:
        return OpenInterestObservation(
            timestamp=datetime(2026, 7, day, tzinfo=timezone.utc),
            open_interest=1_000_000.0,
            close=close,
        )

    def _dq(self, **kwargs: object) -> OpenInterestDataQuality:
        defaults = {
            "expected_rows": 15,
            "actual_rows": 15,
            "missing_rows": 0,
            "min_required_rows_met": True,
            "stale_input_count": 0,
            "reason_codes": (),
        }
        defaults.update(kwargs)
        return OpenInterestDataQuality(**defaults)  # type: ignore[arg-type]

    def test_valid_construction(self) -> None:
        score = OpenInterestScore(
            pair="BTCUSDT",
            state=OpenInterestState.READY,
            positioning=OpenInterestPositioning.PRICE_UP_OI_UP,
            trend=OpenInterestTrend.EXPANDING,
            funding_context=OpenInterestFundingContext.NEUTRAL,
            total_score=75.0,
            period_changes=(),
            latest_oi=1_000_000.0,
            latest_price=100.0,
            latest_funding_rate=None,
            sub_scores={"price_oi_alignment": 80.0},
            data_quality=self._dq(),
            human_note="test",
            reason_codes=(),
            metadata={},
        )
        assert score.pair == "BTCUSDT"
        assert score.total_score == 75.0

    def test_total_score_out_of_range(self) -> None:
        with pytest.raises(ValueError, match="total_score"):
            OpenInterestScore(
                pair="BTCUSDT",
                state=OpenInterestState.READY,
                positioning=OpenInterestPositioning.PRICE_UP_OI_UP,
                trend=OpenInterestTrend.EXPANDING,
                funding_context=OpenInterestFundingContext.NEUTRAL,
                total_score=101.0,
                period_changes=(),
                latest_oi=None,
                latest_price=None,
                latest_funding_rate=None,
                sub_scores={},
                data_quality=self._dq(),
                human_note="test",
                reason_codes=(),
                metadata={},
            )

    def test_sub_scores_validation(self) -> None:
        with pytest.raises(ValueError, match="sub_scores"):
            OpenInterestScore(
                pair="BTCUSDT",
                state=OpenInterestState.READY,
                positioning=OpenInterestPositioning.PRICE_UP_OI_UP,
                trend=OpenInterestTrend.EXPANDING,
                funding_context=OpenInterestFundingContext.NEUTRAL,
                total_score=75.0,
                period_changes=(),
                latest_oi=None,
                latest_price=None,
                latest_funding_rate=None,
                sub_scores={"": 50.0},
                data_quality=self._dq(),
                human_note="test",
                reason_codes=(),
                metadata={},
            )

    def test_invalid_reason_code_rejected(self) -> None:
        with pytest.raises(ValueError, match="unsupported reason code"):
            OpenInterestScore(
                pair="BTCUSDT",
                state=OpenInterestState.READY,
                positioning=OpenInterestPositioning.PRICE_UP_OI_UP,
                trend=OpenInterestTrend.EXPANDING,
                funding_context=OpenInterestFundingContext.NEUTRAL,
                total_score=75.0,
                period_changes=(),
                latest_oi=None,
                latest_price=None,
                latest_funding_rate=None,
                sub_scores={},
                data_quality=self._dq(),
                human_note="test",
                reason_codes=("NOT_A_CODE",),
                metadata={},
            )


class TestOpenInterestUniverseSummary:
    def _dq(self) -> OpenInterestDataQuality:
        return OpenInterestDataQuality(
            expected_rows=15,
            actual_rows=0,
            missing_rows=15,
            min_required_rows_met=False,
            stale_input_count=0,
            reason_codes=(),
        )

    def test_valid_construction(self) -> None:
        summary = OpenInterestUniverseSummary(
            total_pairs=3,
            ready_count=2,
            insufficient_data_count=1,
            blocked_count=0,
            expanding_count=1,
            contracting_count=0,
            flat_count=1,
            unstable_count=0,
            price_up_oi_up_count=1,
            price_up_oi_down_count=0,
            price_down_oi_up_count=0,
            price_down_oi_down_count=0,
            mixed_count=1,
            average_total_score=50.0,
            top_expanding_pair="BTCUSDT",
            top_contracting_pair=None,
            data_quality=self._dq(),
            summary_narrative="test",
            reason_codes=(),
        )
        assert summary.total_pairs == 3

    def test_state_counts_must_sum(self) -> None:
        with pytest.raises(ValueError, match="state counts"):
            OpenInterestUniverseSummary(
                total_pairs=3,
                ready_count=2,
                insufficient_data_count=2,
                blocked_count=0,
                expanding_count=0,
                contracting_count=0,
                flat_count=0,
                unstable_count=0,
                price_up_oi_up_count=0,
                price_up_oi_down_count=0,
                price_down_oi_up_count=0,
                price_down_oi_down_count=0,
                mixed_count=0,
                average_total_score=None,
                top_expanding_pair=None,
                top_contracting_pair=None,
                data_quality=self._dq(),
                summary_narrative="test",
                reason_codes=(),
            )

    def test_average_total_score_out_of_range(self) -> None:
        with pytest.raises(ValueError, match="average_total_score"):
            OpenInterestUniverseSummary(
                total_pairs=1,
                ready_count=1,
                insufficient_data_count=0,
                blocked_count=0,
                expanding_count=0,
                contracting_count=0,
                flat_count=0,
                unstable_count=0,
                price_up_oi_up_count=0,
                price_up_oi_down_count=0,
                price_down_oi_up_count=0,
                price_down_oi_down_count=0,
                mixed_count=0,
                average_total_score=150.0,
                top_expanding_pair=None,
                top_contracting_pair=None,
                data_quality=self._dq(),
                summary_narrative="test",
                reason_codes=(),
            )


class TestOpenInterestReport:
    def _dq(self) -> OpenInterestDataQuality:
        return OpenInterestDataQuality(
            expected_rows=15,
            actual_rows=0,
            missing_rows=15,
            min_required_rows_met=False,
            stale_input_count=0,
            reason_codes=(),
        )

    def _summary(self) -> OpenInterestUniverseSummary:
        return OpenInterestUniverseSummary(
            total_pairs=0,
            ready_count=0,
            insufficient_data_count=0,
            blocked_count=0,
            expanding_count=0,
            contracting_count=0,
            flat_count=0,
            unstable_count=0,
            price_up_oi_up_count=0,
            price_up_oi_down_count=0,
            price_down_oi_up_count=0,
            price_down_oi_down_count=0,
            mixed_count=0,
            average_total_score=None,
            top_expanding_pair=None,
            top_contracting_pair=None,
            data_quality=self._dq(),
            summary_narrative="blocked",
            reason_codes=(),
        )

    def _valid_report(self) -> OpenInterestReport:
        return OpenInterestReport(
            report_id="test",
            kind="open_interest_report",
            version="0.25.0-dev",
            source_spec="SPEC-026",
            generated_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
            config=OpenInterestConfig(),
            safety_flags=OpenInterestSafetyFlags(),
            scores=(),
            universe_summary=self._summary(),
            reason_codes=(HUMAN_RESEARCH_ONLY,),
            metadata={},
        )

    def test_valid_construction(self) -> None:
        report = self._valid_report()
        assert report.report_id == "test"
        assert report.kind == "open_interest_report"

    def test_naive_generated_at_rejected(self) -> None:
        with pytest.raises(ValueError, match="generated_at"):
            OpenInterestReport(
                report_id="test",
                kind="open_interest_report",
                version="0.25.0-dev",
                source_spec="SPEC-026",
                generated_at=datetime(2026, 7, 1),
                config=OpenInterestConfig(),
                safety_flags=OpenInterestSafetyFlags(),
                scores=(),
                universe_summary=self._summary(),
                reason_codes=(HUMAN_RESEARCH_ONLY,),
                metadata={},
            )

    def test_blocked_factory(self) -> None:
        report = OpenInterestReport.blocked(
            reason_code=UNSAFE_OPEN_INTEREST_CONTENT,
            report_id="blocked-report",
            generated_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        )
        assert report.report_id == "blocked-report"
        assert report.kind == "open_interest_report"
        assert report.version == "0.25.0-dev"
        assert report.source_spec == "SPEC-026"
        assert report.scores == ()
        assert report.universe_summary.total_pairs == 0
        assert report.universe_summary.blocked_count == 0  # blocked factory has no pairs
        assert report.reason_codes == (UNSAFE_OPEN_INTEREST_CONTENT,)
        assert report.safety_flags.human_research_only is True

    def test_blocked_factory_default_generated_at(self) -> None:
        report = OpenInterestReport.blocked(reason_code=UNSAFE_OPEN_INTEREST_CONTENT)
        assert report.report_id == "blocked"
        assert report.generated_at.tzinfo is not None

    def test_blocked_factory_invalid_reason_code(self) -> None:
        with pytest.raises(ValueError, match="unsupported reason code"):
            OpenInterestReport.blocked(reason_code="NOT_A_CODE")

    def test_frozen_cannot_mutate(self) -> None:
        report = self._valid_report()
        with pytest.raises(dataclasses.FrozenInstanceError):
            report.report_id = "changed"  # type: ignore[misc]
