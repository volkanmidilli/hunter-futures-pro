"""Tests for hunter.open_interest.engine."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from hunter.open_interest.engine import (
    build_open_interest_report,
    build_open_interest_safety_flags,
    build_open_interest_score,
    build_open_interest_universe_summary,
    calculate_oi_change,
    calculate_oi_trend,
    calculate_period_change,
    calculate_price_change,
    classify_funding_context,
    classify_oi_price_positioning,
    has_unsafe_open_interest_content,
    normalized_score,
)
from hunter.open_interest.models import (
    FUNDING_CONTEXT_MISSING,
    INSUFFICIENT_OI_DATA,
    NO_FILE_READ_IN_ENGINE,
    NO_NETWORK_CONNECTION,
    PERIOD_DATA_MISSING,
    UNSAFE_OPEN_INTEREST_CONTENT,
    OpenInterestConfig,
    OpenInterestFundingContext,
    OpenInterestInput,
    OpenInterestObservation,
    OpenInterestPositioning,
    OpenInterestSafetyFlags,
    OpenInterestState,
    OpenInterestTrend,
)


class TestSafetyAndForbiddenTerms:
    def test_build_open_interest_safety_flags(self) -> None:
        flags = build_open_interest_safety_flags()
        assert isinstance(flags, OpenInterestSafetyFlags)
        assert flags.human_research_only is True
        assert flags.network_enabled is False
        assert flags.leverage_enabled is False

    def test_has_unsafe_open_interest_content_string(self) -> None:
        assert has_unsafe_open_interest_content("buy now") is True
        assert has_unsafe_open_interest_content("leverage") is True
        assert has_unsafe_open_interest_content("research only") is False

    def test_has_unsafe_open_interest_content_mapping(self) -> None:
        assert has_unsafe_open_interest_content({"action": "place_order"}) is True
        assert has_unsafe_open_interest_content({"note": "research"}) is False

    def test_has_unsafe_open_interest_content_input_pair(self) -> None:
        rows = [OpenInterestObservation(
            timestamp=datetime(2026, 7, 1, tzinfo=timezone.utc),
            open_interest=1_000_000.0,
            close=100.0,
        )]
        unsafe_input = OpenInterestInput(pair="binance_api", rows=rows)
        assert has_unsafe_open_interest_content(unsafe_input) is True

    def test_has_unsafe_open_interest_content_input_metadata(self) -> None:
        rows = [OpenInterestObservation(
            timestamp=datetime(2026, 7, 1, tzinfo=timezone.utc),
            open_interest=1_000_000.0,
            close=100.0,
        )]
        unsafe_input = OpenInterestInput(pair="BTCUSDT", rows=rows, metadata={"action": "execute"})
        assert has_unsafe_open_interest_content(unsafe_input) is True

    def test_has_unsafe_open_interest_content_observation_metadata(self) -> None:
        obs = OpenInterestObservation(
            timestamp=datetime(2026, 7, 1, tzinfo=timezone.utc),
            open_interest=1_000_000.0,
            close=100.0,
            metadata={"source": "dashboard"},
        )
        assert has_unsafe_open_interest_content(obs) is True

    def test_has_unsafe_open_interest_content_none(self) -> None:
        assert has_unsafe_open_interest_content(None) is False

    def test_has_unsafe_open_interest_content_arbitrary(self) -> None:
        assert has_unsafe_open_interest_content(123) is False
        assert has_unsafe_open_interest_content(["buy"]) is False


class TestPeriodChange:
    def test_calculate_period_change(self) -> None:
        assert calculate_period_change(110.0, 100.0) == 0.1

    def test_calculate_period_change_rounding(self) -> None:
        change = calculate_period_change(100.000000005, 100.0)
        assert change == 0.0  # rounded to 8 decimals

    def test_calculate_period_change_zero_denominator(self) -> None:
        assert calculate_period_change(100.0, 0.0) is None

    def test_calculate_period_change_negative(self) -> None:
        assert calculate_period_change(90.0, 100.0) == -0.1


class TestOiChangeAndPriceChange:
    def _rows(self, n: int) -> list[OpenInterestObservation]:
        return [
            OpenInterestObservation(
                timestamp=datetime(2026, 7, day, tzinfo=timezone.utc),
                open_interest=float(1_000_000 + day * 1000),
                close=float(100 + day),
            )
            for day in range(1, n + 1)
        ]

    def test_calculate_oi_change_sufficient_data(self) -> None:
        rows = self._rows(15)
        change = calculate_oi_change(rows, 7)
        assert change is not None

    def test_calculate_oi_change_insufficient_data(self) -> None:
        rows = self._rows(5)
        assert calculate_oi_change(rows, 7) is None

    def test_calculate_oi_change_zero_period(self) -> None:
        rows = self._rows(5)
        assert calculate_oi_change(rows, 0) is None

    def test_calculate_price_change_sufficient_data(self) -> None:
        rows = self._rows(15)
        change = calculate_price_change(rows, 7)
        assert change is not None

    def test_calculate_price_change_insufficient_data(self) -> None:
        rows = self._rows(5)
        assert calculate_price_change(rows, 7) is None

    def test_sorted_rows_not_mutated(self) -> None:
        rows = self._rows(5)[::-1]  # reverse order
        original_order = [row.timestamp.day for row in rows]
        calculate_oi_change(rows, 1)
        assert [row.timestamp.day for row in rows] == original_order


class TestPositioningClassification:
    def test_price_up_oi_up(self) -> None:
        assert (
            classify_oi_price_positioning(0.02, 0.03, 0.001)
            == OpenInterestPositioning.PRICE_UP_OI_UP
        )

    def test_price_up_oi_down(self) -> None:
        assert (
            classify_oi_price_positioning(-0.02, 0.03, 0.001)
            == OpenInterestPositioning.PRICE_UP_OI_DOWN
        )

    def test_price_down_oi_up(self) -> None:
        assert (
            classify_oi_price_positioning(0.02, -0.03, 0.001)
            == OpenInterestPositioning.PRICE_DOWN_OI_UP
        )

    def test_price_down_oi_down(self) -> None:
        assert (
            classify_oi_price_positioning(-0.02, -0.03, 0.001)
            == OpenInterestPositioning.PRICE_DOWN_OI_DOWN
        )

    def test_mixed(self) -> None:
        assert (
            classify_oi_price_positioning(0.0005, 0.0005, 0.001)
            == OpenInterestPositioning.MIXED
        )

    def test_insufficient_data(self) -> None:
        assert (
            classify_oi_price_positioning(None, 0.03, 0.001)
            == OpenInterestPositioning.INSUFFICIENT_DATA
        )
        assert (
            classify_oi_price_positioning(0.02, None, 0.001)
            == OpenInterestPositioning.INSUFFICIENT_DATA
        )

    def test_exact_threshold(self) -> None:
        # At exactly threshold, not above or below.
        assert (
            classify_oi_price_positioning(0.001, 0.001, 0.001)
            == OpenInterestPositioning.MIXED
        )


class TestTrendClassification:
    def test_expanding(self) -> None:
        assert calculate_oi_trend([0.02, 0.03, 0.04], 0.001) == OpenInterestTrend.EXPANDING

    def test_contracting(self) -> None:
        assert calculate_oi_trend([-0.02, -0.03, -0.04], 0.001) == OpenInterestTrend.CONTRACTING

    def test_flat(self) -> None:
        assert calculate_oi_trend([0.0005, 0.0003, -0.0001], 0.001) == OpenInterestTrend.FLAT

    def test_unstable(self) -> None:
        assert calculate_oi_trend([0.02, -0.02], 0.001) == OpenInterestTrend.UNSTABLE

    def test_insufficient_data(self) -> None:
        assert calculate_oi_trend([0.02], 0.001) == OpenInterestTrend.INSUFFICIENT_DATA
        assert calculate_oi_trend([], 0.001) == OpenInterestTrend.INSUFFICIENT_DATA

    def test_with_none_values(self) -> None:
        assert calculate_oi_trend([0.02, None, 0.03], 0.001) == OpenInterestTrend.EXPANDING

    def test_majority_exactly_half(self) -> None:
        # 2 of 4 expanding, not majority (>50%), so unstable if not flat.
        assert calculate_oi_trend([0.02, 0.02, -0.02, -0.02], 0.001) == OpenInterestTrend.UNSTABLE


class TestFundingContextClassification:
    def test_positive(self) -> None:
        assert classify_funding_context(0.005, (-0.01, 0.01)) == OpenInterestFundingContext.POSITIVE

    def test_negative(self) -> None:
        assert classify_funding_context(-0.005, (-0.01, 0.01)) == OpenInterestFundingContext.NEGATIVE

    def test_neutral(self) -> None:
        assert classify_funding_context(0.0, (-0.01, 0.01)) == OpenInterestFundingContext.NEUTRAL
        assert classify_funding_context(0.003333, (-0.01, 0.01)) == OpenInterestFundingContext.NEUTRAL
        assert classify_funding_context(-0.003333, (-0.01, 0.01)) == OpenInterestFundingContext.NEUTRAL

    def test_missing(self) -> None:
        assert classify_funding_context(None, (-0.01, 0.01)) == OpenInterestFundingContext.MISSING

    def test_bounds_third(self) -> None:
        upper_third = 0.01 / 3
        assert classify_funding_context(upper_third + 0.0001, (-0.01, 0.01)) == OpenInterestFundingContext.POSITIVE
        assert classify_funding_context(-upper_third - 0.0001, (-0.01, 0.01)) == OpenInterestFundingContext.NEGATIVE


class TestNormalizedScore:
    def test_normalized_score(self) -> None:
        assert normalized_score(0.0, -0.30, 0.30) == 50.0
        assert normalized_score(-0.30, -0.30, 0.30) == 0.0
        assert normalized_score(0.30, -0.30, 0.30) == 100.0

    def test_normalized_score_clamp(self) -> None:
        assert normalized_score(-0.50, -0.30, 0.30) == 0.0
        assert normalized_score(0.50, -0.30, 0.30) == 100.0

    def test_normalized_score_none(self) -> None:
        assert normalized_score(None, -0.30, 0.30) == 0.0

    def test_normalized_score_intermediate(self) -> None:
        # 0.15 is 3/4 of the way from -0.30 to 0.30
        assert normalized_score(0.15, -0.30, 0.30) == 75.0


class TestSubScoreMappings:
    def _score_ready(self, pair: str = "BTCUSDT") -> object:
        rows = [
            OpenInterestObservation(
                timestamp=datetime(2026, 7, day, tzinfo=timezone.utc),
                open_interest=float(1_000_000 + day * 10_000),
                close=float(100 + day),
                funding_rate=0.0001,
            )
            for day in range(1, 16)
        ]
        return build_open_interest_score(OpenInterestInput(pair=pair, rows=rows), OpenInterestConfig())

    def test_positioning_sub_scores(self) -> None:
        from hunter.open_interest.engine import _POSITIONING_SCORES
        assert _POSITIONING_SCORES[OpenInterestPositioning.PRICE_UP_OI_UP] == 80.0
        assert _POSITIONING_SCORES[OpenInterestPositioning.PRICE_DOWN_OI_DOWN] == 80.0
        assert _POSITIONING_SCORES[OpenInterestPositioning.PRICE_UP_OI_DOWN] == 60.0
        assert _POSITIONING_SCORES[OpenInterestPositioning.PRICE_DOWN_OI_UP] == 60.0
        assert _POSITIONING_SCORES[OpenInterestPositioning.MIXED] == 40.0
        assert _POSITIONING_SCORES[OpenInterestPositioning.INSUFFICIENT_DATA] == 0.0
        assert _POSITIONING_SCORES[OpenInterestPositioning.BLOCKED] == 0.0

    def test_trend_sub_scores(self) -> None:
        from hunter.open_interest.engine import _TREND_SCORES
        assert _TREND_SCORES[OpenInterestTrend.EXPANDING] == 80.0
        assert _TREND_SCORES[OpenInterestTrend.CONTRACTING] == 80.0
        assert _TREND_SCORES[OpenInterestTrend.FLAT] == 50.0
        assert _TREND_SCORES[OpenInterestTrend.UNSTABLE] == 30.0
        assert _TREND_SCORES[OpenInterestTrend.INSUFFICIENT_DATA] == 0.0
        assert _TREND_SCORES[OpenInterestTrend.BLOCKED] == 0.0

    def test_funding_sub_scores(self) -> None:
        from hunter.open_interest.engine import _FUNDING_SCORES
        assert _FUNDING_SCORES[OpenInterestFundingContext.POSITIVE] == 75.0
        assert _FUNDING_SCORES[OpenInterestFundingContext.NEGATIVE] == 75.0
        assert _FUNDING_SCORES[OpenInterestFundingContext.NEUTRAL] == 50.0
        assert _FUNDING_SCORES[OpenInterestFundingContext.MISSING] == 50.0
        assert _FUNDING_SCORES[OpenInterestFundingContext.BLOCKED] == 0.0

    def test_total_score_range(self) -> None:
        score = self._score_ready()
        assert 0.0 <= score.total_score <= 100.0

    def test_sub_scores_values_in_range(self) -> None:
        score = self._score_ready()
        for value in score.sub_scores.values():
            assert 0.0 <= value <= 100.0

    def test_data_quality_sub_score(self) -> None:
        score = self._score_ready()
        assert "data_quality" in score.sub_scores
        assert score.sub_scores["data_quality"] == 100.0


class TestBuildOpenInterestScore:
    def _rows(self, n: int, start_oi: float = 1_000_000.0, start_close: float = 100.0) -> list[OpenInterestObservation]:
        return [
            OpenInterestObservation(
                timestamp=datetime(2026, 7, day, tzinfo=timezone.utc),
                open_interest=float(start_oi + day * 10_000),
                close=float(start_close + day),
                funding_rate=0.0001,
            )
            for day in range(1, n + 1)
        ]

    def test_ready_state(self) -> None:
        rows = self._rows(15)
        score = build_open_interest_score(
            OpenInterestInput(pair="BTCUSDT", rows=rows),
            OpenInterestConfig(),
        )
        assert score.state == OpenInterestState.READY
        assert score.positioning != OpenInterestPositioning.INSUFFICIENT_DATA
        assert score.positioning != OpenInterestPositioning.BLOCKED
        assert score.total_score > 0.0
        assert score.human_note.startswith("BTCUSDT")
        assert score.data_quality.min_required_rows_met is True
        assert len(score.period_changes) == 4

    def test_insufficient_data_state(self) -> None:
        rows = self._rows(5)
        score = build_open_interest_score(
            OpenInterestInput(pair="BTCUSDT", rows=rows),
            OpenInterestConfig(),
        )
        assert score.state == OpenInterestState.INSUFFICIENT_DATA
        assert score.positioning == OpenInterestPositioning.INSUFFICIENT_DATA
        assert score.trend == OpenInterestTrend.INSUFFICIENT_DATA
        assert score.funding_context == OpenInterestFundingContext.INSUFFICIENT_DATA
        assert score.total_score == 0.0
        assert score.sub_scores == {}
        assert INSUFFICIENT_OI_DATA in score.reason_codes
        assert PERIOD_DATA_MISSING in score.reason_codes

    def test_blocked_state_unsafe_content(self) -> None:
        rows = self._rows(15)
        score = build_open_interest_score(
            OpenInterestInput(pair="BTCUSDT", rows=rows, metadata={"action": "buy"}),
            OpenInterestConfig(),
        )
        assert score.state == OpenInterestState.BLOCKED
        assert score.positioning == OpenInterestPositioning.BLOCKED
        assert score.trend == OpenInterestTrend.BLOCKED
        assert score.funding_context == OpenInterestFundingContext.BLOCKED
        assert score.total_score == 0.0
        assert score.sub_scores == {}
        assert UNSAFE_OPEN_INTEREST_CONTENT in score.reason_codes
        assert score.latest_oi is None
        assert score.latest_price is None

    def test_block_on_missing_data_false(self) -> None:
        rows = self._rows(5)
        score = build_open_interest_score(
            OpenInterestInput(pair="BTCUSDT", rows=rows),
            OpenInterestConfig(block_on_missing_data=False),
        )
        assert score.state == OpenInterestState.INSUFFICIENT_DATA

    def test_block_on_missing_data_true(self) -> None:
        rows = self._rows(5)
        score = build_open_interest_score(
            OpenInterestInput(pair="BTCUSDT", rows=rows),
            OpenInterestConfig(block_on_missing_data=True),
        )
        assert score.state == OpenInterestState.BLOCKED
        assert score.positioning == OpenInterestPositioning.BLOCKED

    def test_input_rows_not_mutated(self) -> None:
        rows = self._rows(5)[::-1]
        original_order = [row.timestamp.day for row in rows]
        build_open_interest_score(
            OpenInterestInput(pair="BTCUSDT", rows=rows),
            OpenInterestConfig(),
        )
        assert [row.timestamp.day for row in rows] == original_order
        assert isinstance(rows, list)

    def test_sorted_rows_used(self) -> None:
        rows = self._rows(15)[::-1]
        score = build_open_interest_score(
            OpenInterestInput(pair="BTCUSDT", rows=rows),
            OpenInterestConfig(),
        )
        # The latest value should be from the latest timestamp (day 15), not first in list.
        assert score.latest_oi == 1_000_000 + 15 * 10_000
        assert score.latest_price == 115.0

    def test_missing_funding_is_informational(self) -> None:
        rows = [
            OpenInterestObservation(
                timestamp=datetime(2026, 7, day, tzinfo=timezone.utc),
                open_interest=float(1_000_000 + day * 10_000),
                close=float(100 + day),
            )
            for day in range(1, 16)
        ]
        score = build_open_interest_score(
            OpenInterestInput(pair="BTCUSDT", rows=rows),
            OpenInterestConfig(),
        )
        assert score.funding_context == OpenInterestFundingContext.MISSING
        assert score.sub_scores["funding_context"] == 50.0
        assert FUNDING_CONTEXT_MISSING in score.reason_codes
        assert score.state == OpenInterestState.READY

    def test_reason_codes_deduplicated(self) -> None:
        # Multiple period changes missing should not duplicate PERIOD_DATA_MISSING.
        rows = self._rows(2)
        score = build_open_interest_score(
            OpenInterestInput(pair="BTCUSDT", rows=rows),
            OpenInterestConfig(),
        )
        assert score.reason_codes.count(PERIOD_DATA_MISSING) == 1
        assert score.reason_codes.count(INSUFFICIENT_OI_DATA) == 1

    def test_period_missing_does_not_force_insufficient_state(self) -> None:
        # 20 rows is enough for min_required_rows=15, but 30d window is missing.
        config = OpenInterestConfig(lookback_periods=(1, 3, 7, 14, 30))
        rows = self._rows(20)
        score = build_open_interest_score(
            OpenInterestInput(pair="BTCUSDT", rows=rows),
            config,
        )
        assert score.state == OpenInterestState.READY
        assert PERIOD_DATA_MISSING in score.reason_codes

    def test_zero_denominator_not_triggered_in_engine(self) -> None:
        # close > 0 is enforced by model, so this tests that period change None is handled.
        change = calculate_period_change(100.0, 0.0)
        assert change is None

    def test_block_on_missing_data_true_insufficient_rows(self) -> None:
        rows = self._rows(5)
        score = build_open_interest_score(
            OpenInterestInput(pair="BTCUSDT", rows=rows),
            OpenInterestConfig(block_on_missing_data=True),
        )
        assert score.state == OpenInterestState.BLOCKED
        assert INSUFFICIENT_OI_DATA in score.reason_codes


class TestBuildOpenInterestUniverseSummary:
    def _rows(self, n: int) -> list[OpenInterestObservation]:
        return [
            OpenInterestObservation(
                timestamp=datetime(2026, 7, day, tzinfo=timezone.utc),
                open_interest=float(1_000_000 + day * 10_000),
                close=float(100 + day),
            )
            for day in range(1, n + 1)
        ]

    def test_count_invariant(self) -> None:
        ready = build_open_interest_score(
            OpenInterestInput(pair="BTCUSDT", rows=self._rows(15)),
            OpenInterestConfig(),
        )
        insufficient = build_open_interest_score(
            OpenInterestInput(pair="ETHUSDT", rows=self._rows(5)),
            OpenInterestConfig(),
        )
        blocked = build_open_interest_score(
            OpenInterestInput(pair="SOLUSDT", rows=self._rows(15), metadata={"action": "buy"}),
            OpenInterestConfig(),
        )
        summary = build_open_interest_universe_summary([ready, insufficient, blocked], OpenInterestConfig())
        assert summary.total_pairs == 3
        assert summary.ready_count == 1
        assert summary.insufficient_data_count == 1
        assert summary.blocked_count == 1
        assert summary.ready_count + summary.insufficient_data_count + summary.blocked_count == 3

    def test_average_total_score_ready_only(self) -> None:
        ready = build_open_interest_score(
            OpenInterestInput(pair="BTCUSDT", rows=self._rows(15)),
            OpenInterestConfig(),
        )
        blocked = build_open_interest_score(
            OpenInterestInput(pair="SOLUSDT", rows=self._rows(15), metadata={"action": "buy"}),
            OpenInterestConfig(),
        )
        summary = build_open_interest_universe_summary([ready, blocked], OpenInterestConfig())
        assert summary.average_total_score == ready.total_score

    def test_no_ready_pairs_average_none(self) -> None:
        insufficient = build_open_interest_score(
            OpenInterestInput(pair="ETHUSDT", rows=self._rows(5)),
            OpenInterestConfig(),
        )
        summary = build_open_interest_universe_summary([insufficient], OpenInterestConfig())
        assert summary.average_total_score is None

    def test_top_expanding_pair(self) -> None:
        expanding_rows = [
            OpenInterestObservation(
                timestamp=datetime(2026, 7, day, tzinfo=timezone.utc),
                open_interest=float(1_000_000 + day * 100_000),
                close=float(100 + day),
            )
            for day in range(1, 16)
        ]
        expanding = build_open_interest_score(
            OpenInterestInput(pair="EXPUSDT", rows=expanding_rows),
            OpenInterestConfig(),
        )
        assert expanding.trend == OpenInterestTrend.EXPANDING
        summary = build_open_interest_universe_summary([expanding], OpenInterestConfig())
        assert summary.top_expanding_pair == "EXPUSDT"
        assert summary.top_contracting_pair is None


class TestBuildOpenInterestReport:
    def _rows(self, n: int, pair: str = "BTCUSDT") -> list[OpenInterestObservation]:
        return [
            OpenInterestObservation(
                timestamp=datetime(2026, 7, day, tzinfo=timezone.utc),
                open_interest=float(1_000_000 + day * 10_000),
                close=float(100 + day),
            )
            for day in range(1, n + 1)
        ]

    def test_report_building(self) -> None:
        universe = [
            OpenInterestInput(pair="BTCUSDT", rows=self._rows(15)),
            OpenInterestInput(pair="ETHUSDT", rows=self._rows(5)),
        ]
        report = build_open_interest_report(
            universe=universe,
            report_id="test-report",
            generated_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        )
        assert report.report_id == "test-report"
        assert report.kind == "open_interest_report"
        assert report.version == "0.25.0-dev"
        assert report.source_spec == "SPEC-026"
        assert len(report.scores) == 2
        assert report.universe_summary.total_pairs == 2

    def test_report_blocked_pair_on_unsafe_input(self) -> None:
        universe = [
            OpenInterestInput(pair="BTCUSDT", rows=self._rows(15), metadata={"action": "buy"}),
        ]
        report = build_open_interest_report(
            universe=universe,
            generated_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        )
        assert len(report.scores) == 1
        assert report.scores[0].state == OpenInterestState.BLOCKED
        assert UNSAFE_OPEN_INTEREST_CONTENT in report.scores[0].reason_codes

    def test_deterministic_ordering(self) -> None:
        ready_rows = self._rows(15)
        insufficient_rows = self._rows(5)
        # ready has higher score, should come before insufficient (state priority).
        # Then blocked. Then by score descending, then pair ascending.
        blocked = OpenInterestInput(pair="AAAUSDT", rows=self._rows(15), metadata={"action": "buy"})
        ready = OpenInterestInput(pair="ZZZUSDT", rows=ready_rows)
        insufficient = OpenInterestInput(pair="BBBUSDT", rows=insufficient_rows)
        report = build_open_interest_report(
            universe=[blocked, insufficient, ready],
            generated_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        )
        assert report.scores[0].state == OpenInterestState.READY
        assert report.scores[0].pair == "ZZZUSDT"
        assert report.scores[1].state == OpenInterestState.INSUFFICIENT_DATA
        assert report.scores[2].state == OpenInterestState.BLOCKED
        assert report.scores[2].pair == "AAAUSDT"

    def test_advisory_reason_codes_present(self) -> None:
        report = build_open_interest_report(
            universe=[OpenInterestInput(pair="BTCUSDT", rows=self._rows(15))],
            generated_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        )
        assert NO_NETWORK_CONNECTION in report.reason_codes
        assert NO_FILE_READ_IN_ENGINE in report.reason_codes

    def test_empty_universe(self) -> None:
        report = build_open_interest_report(
            universe=[],
            generated_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        )
        assert report.universe_summary.total_pairs == 0

    def test_no_pair_is_dropped(self) -> None:
        universe = [
            OpenInterestInput(pair="BTCUSDT", rows=self._rows(15)),
            OpenInterestInput(pair="ETHUSDT", rows=self._rows(5)),
            OpenInterestInput(pair="SOLUSDT", rows=self._rows(15), metadata={"action": "buy"}),
        ]
        report = build_open_interest_report(
            universe=universe,
            generated_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        )
        assert len(report.scores) == 3

    def test_no_inputs_mutated(self) -> None:
        rows = self._rows(15)[::-1]
        original_order = [row.timestamp.day for row in rows]
        inp = OpenInterestInput(pair="BTCUSDT", rows=rows)
        build_open_interest_report(
            universe=[inp],
            generated_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        )
        assert [row.timestamp.day for row in rows] == original_order
        assert isinstance(inp.rows, tuple)

    def test_identical_inputs_produce_identical_outputs(self) -> None:
        universe = [OpenInterestInput(pair="BTCUSDT", rows=self._rows(15))]
        report1 = build_open_interest_report(
            universe=universe,
            generated_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        )
        report2 = build_open_interest_report(
            universe=universe,
            generated_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        )
        assert report1.scores[0].total_score == report2.scores[0].total_score
        assert report1.scores[0].positioning == report2.scores[0].positioning

    def test_config_default(self) -> None:
        universe = [OpenInterestInput(pair="BTCUSDT", rows=self._rows(15))]
        report = build_open_interest_report(universe=universe)
        assert report.config is not None
        assert report.config.lookback_periods == (1, 3, 7, 14)

    def test_report_default_generated_at(self) -> None:
        report = build_open_interest_report(
            universe=[OpenInterestInput(pair="BTCUSDT", rows=self._rows(15))],
        )
        assert report.generated_at.tzinfo is not None

    def test_universe_summary_reason_codes_aggregated(self) -> None:
        universe = [
            OpenInterestInput(pair="BTCUSDT", rows=self._rows(5)),
        ]
        report = build_open_interest_report(
            universe=universe,
            generated_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        )
        assert INSUFFICIENT_OI_DATA in report.universe_summary.reason_codes
        assert PERIOD_DATA_MISSING in report.universe_summary.reason_codes
