"""Tests for hunter.relative_strength.models."""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone

import pytest
from types import MappingProxyType

from hunter.relative_strength.models import (
    RELATIVE_STRENGTH_ADVISORY_REASON_CODES,
    RELATIVE_STRENGTH_BLOCKING_REASON_CODES,
    RELATIVE_STRENGTH_INSUFFICIENT_DATA_REASON_CODES,
    RELATIVE_STRENGTH_REASON_CODES,
    OhlcvRow,
    RelativeStrengthBenchmarkKind,
    RelativeStrengthConfig,
    RelativeStrengthDataQuality,
    RelativeStrengthDecision,
    RelativeStrengthInput,
    RelativeStrengthPeriodReturn,
    RelativeStrengthRatioTrend,
    RelativeStrengthReport,
    RelativeStrengthSafetyFlags,
    RelativeStrengthScore,
    RelativeStrengthState,
    RelativeStrengthUniverseSummary,
)


class TestReasonCodeConstants:
    def test_blocking_reason_codes(self) -> None:
        assert "UNSAFE_INPUT_CONTENT" in RELATIVE_STRENGTH_BLOCKING_REASON_CODES
        assert "INVALID_INPUT_DATA" in RELATIVE_STRENGTH_BLOCKING_REASON_CODES
        assert "MISSING_BTC_BENCHMARK" in RELATIVE_STRENGTH_BLOCKING_REASON_CODES

    def test_insufficient_data_reason_codes(self) -> None:
        assert "MIN_ROWS_NOT_MET" in RELATIVE_STRENGTH_INSUFFICIENT_DATA_REASON_CODES
        assert "PERIOD_DATA_MISSING" in RELATIVE_STRENGTH_INSUFFICIENT_DATA_REASON_CODES

    def test_advisory_reason_codes(self) -> None:
        assert "HUMAN_RESEARCH_ONLY" in RELATIVE_STRENGTH_ADVISORY_REASON_CODES
        assert "NO_FILE_READ_IN_ENGINE" in RELATIVE_STRENGTH_ADVISORY_REASON_CODES

    def test_aggregate_reason_codes(self) -> None:
        assert set(RELATIVE_STRENGTH_REASON_CODES) == set(
            RELATIVE_STRENGTH_BLOCKING_REASON_CODES
            + RELATIVE_STRENGTH_INSUFFICIENT_DATA_REASON_CODES
            + RELATIVE_STRENGTH_ADVISORY_REASON_CODES
        )


class TestEnums:
    def test_state_enum(self) -> None:
        assert RelativeStrengthState.READY.value == "ready"
        assert RelativeStrengthState.INSUFFICIENT_DATA.value == "insufficient_data"
        assert RelativeStrengthState.BLOCKED.value == "blocked"

    def test_decision_enum(self) -> None:
        assert RelativeStrengthDecision.OUTPERFORMER.value == "outperformer"
        assert RelativeStrengthDecision.NEUTRAL.value == "neutral"
        assert RelativeStrengthDecision.UNDERPERFORMER.value == "underperformer"
        assert RelativeStrengthDecision.INSUFFICIENT_DATA.value == "insufficient_data"
        assert RelativeStrengthDecision.BLOCKED.value == "blocked"

    def test_benchmark_kind_enum(self) -> None:
        assert RelativeStrengthBenchmarkKind.BTC.value == "btc"
        assert RelativeStrengthBenchmarkKind.ETH.value == "eth"
        assert RelativeStrengthBenchmarkKind.NEUTRAL.value == "neutral"


class TestOhlcvRow:
    def test_valid_construction(self) -> None:
        row = OhlcvRow(timestamp=1, close=100.0)
        assert row.timestamp == 1
        assert row.close == 100.0

    def test_optional_fields(self) -> None:
        row = OhlcvRow(timestamp=1, close=100.0, open=99.0, high=101.0, low=98.0, volume=1000.0)
        assert row.open == 99.0
        assert row.high == 101.0

    def test_invalid_zero_close(self) -> None:
        with pytest.raises(ValueError, match="non-zero"):
            OhlcvRow(timestamp=1, close=0)

    def test_frozen_cannot_mutate(self) -> None:
        row = OhlcvRow(timestamp=1, close=100.0)
        with pytest.raises(dataclasses.FrozenInstanceError):
            row.close = 200.0  # type: ignore[misc]

    def test_decimal_close(self) -> None:
        from decimal import Decimal
        row = OhlcvRow(timestamp=1, close=Decimal("100.5"))
        assert row.close == Decimal("100.5")


class TestRelativeStrengthInput:
    def test_valid_construction(self) -> None:
        row = OhlcvRow(timestamp=1, close=100.0)
        inp = RelativeStrengthInput(symbol="SOL", rows=[row])
        assert inp.symbol == "SOL"
        assert len(inp.rows) == 1
        assert isinstance(inp.rows, tuple)

    def test_empty_symbol(self) -> None:
        row = OhlcvRow(timestamp=1, close=100.0)
        with pytest.raises(ValueError, match="non-empty"):
            RelativeStrengthInput(symbol="", rows=[row])

    def test_empty_rows(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            RelativeStrengthInput(symbol="SOL", rows=[])

    def test_rows_normalized_to_tuple(self) -> None:
        row = OhlcvRow(timestamp=1, close=100.0)
        inp = RelativeStrengthInput(symbol="SOL", rows=[row])
        assert isinstance(inp.rows, tuple)


class TestRelativeStrengthConfig:
    def test_default_config(self) -> None:
        config = RelativeStrengthConfig()
        assert config.lookback_days == (7, 14, 30)
        assert config.min_required_rows == 30
        assert round(sum(config.score_weights.values()), 4) == 1.0

    def test_invalid_weights_sum(self) -> None:
        with pytest.raises(ValueError, match="weight"):
            RelativeStrengthConfig(
                score_weights={
                    "coin_minus_btc_30d": 0.5,
                    "coin_minus_btc_14d": 0.2,
                    "coin_minus_btc_7d": 0.1,
                    "coin_minus_eth_30d": 0.1,
                    "rank_percentile_30d": 0.15,
                    "ratio_trend": 0.10,
                }
            )

    def test_threshold_order(self) -> None:
        with pytest.raises(ValueError, match="exceed"):
            RelativeStrengthConfig(
                outperformer_threshold=40.0, underperformer_threshold=60.0
            )

    def test_lookback_days_positive(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            RelativeStrengthConfig(lookback_days=(0, 14, 30))

    def test_ratio_trend_lookback_positive(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            RelativeStrengthConfig(ratio_trend_lookback=0)


class TestRelativeStrengthSafetyFlags:
    def test_default_flags_fail_closed(self) -> None:
        flags = RelativeStrengthSafetyFlags()
        assert flags.live_trading_enabled is False
        assert flags.real_orders_enabled is False
        assert flags.leverage_enabled is False
        assert flags.shorting_enabled is False
        assert flags.feedback_into_execution is False

    def test_unsafe_flag_raises(self) -> None:
        with pytest.raises(ValueError, match="unsafe relative strength safety flags"):
            RelativeStrengthSafetyFlags(live_trading_enabled=True)

    def test_safe_flags_must_be_true(self) -> None:
        with pytest.raises(ValueError, match="safe relative strength output flags"):
            RelativeStrengthSafetyFlags(output_is_human_research_only=False)


class TestRelativeStrengthPeriodReturn:
    def test_valid_construction(self) -> None:
        pr = RelativeStrengthPeriodReturn(
            period_days=30,
            coin_return=0.10,
            btc_return=0.05,
            eth_return=None,
            coin_minus_btc=0.05,
            coin_minus_eth=None,
            has_data=True,
            reason_codes=(),
        )
        assert pr.period_days == 30
        assert pr.has_data is True

    def test_none_returns(self) -> None:
        pr = RelativeStrengthPeriodReturn(
            period_days=30,
            coin_return=None,
            btc_return=None,
            eth_return=None,
            coin_minus_btc=None,
            coin_minus_eth=None,
            has_data=False,
            reason_codes=(),
        )
        assert pr.coin_return is None
        assert pr.coin_minus_btc is None

    def test_reason_code_validation(self) -> None:
        with pytest.raises(ValueError, match="reason code"):
            RelativeStrengthPeriodReturn(
                period_days=30,
                coin_return=0.0,
                btc_return=0.0,
                eth_return=None,
                coin_minus_btc=0.0,
                coin_minus_eth=None,
                has_data=True,
                reason_codes=("INVALID_CODE",),
            )


class TestRelativeStrengthRatioTrend:
    def test_valid_construction(self) -> None:
        rt = RelativeStrengthRatioTrend(
            last_ratio=1.0,
            ma_ratio=1.0,
            slope=0.01,
            trend_score=65.0,
            lookback=30,
            has_data=True,
            reason_codes=(),
        )
        assert rt.trend_score == 65.0

    def test_trend_score_bounds(self) -> None:
        with pytest.raises(ValueError, match="[0, 100]"):
            RelativeStrengthRatioTrend(
                last_ratio=1.0,
                ma_ratio=1.0,
                slope=0.01,
                trend_score=150.0,
                lookback=30,
                has_data=True,
                reason_codes=(),
            )


class TestRelativeStrengthScore:
    def test_valid_construction(self) -> None:
        score = RelativeStrengthScore(
            symbol="SOL",
            base_benchmark=RelativeStrengthBenchmarkKind.BTC,
            state=RelativeStrengthState.READY,
            decision=RelativeStrengthDecision.OUTPERFORMER,
            total_score=85.0,
            period_returns=(),
            ratio_trend=RelativeStrengthRatioTrend(
                last_ratio=1.0,
                ma_ratio=1.0,
                slope=0.01,
                trend_score=50.0,
                lookback=30,
                has_data=True,
                reason_codes=(),
            ),
            rank_percentile_30d=None,
            sub_scores={"coin_minus_btc_30d": 80.0},
            data_quality=RelativeStrengthDataQuality(
                expected_rows=30,
                actual_rows=35,
                missing_rows=0,
                missing_periods=(),
                min_required_rows_met=True,
                btc_benchmark_rows=35,
                eth_benchmark_rows=35,
                stale_input_count=0,
                reason_codes=(),
            ),
            human_note="test",
            reason_codes=(),
        )
        assert score.symbol == "SOL"
        assert score.total_score == 85.0

    def test_total_score_bounds(self) -> None:
        with pytest.raises(ValueError, match="[0, 100]"):
            RelativeStrengthScore(
                symbol="SOL",
                base_benchmark=RelativeStrengthBenchmarkKind.BTC,
                state=RelativeStrengthState.READY,
                decision=RelativeStrengthDecision.OUTPERFORMER,
                total_score=150.0,
                period_returns=(),
                ratio_trend=RelativeStrengthRatioTrend(
                    last_ratio=1.0,
                    ma_ratio=1.0,
                    slope=0.01,
                    trend_score=50.0,
                    lookback=30,
                    has_data=True,
                    reason_codes=(),
                ),
                rank_percentile_30d=None,
                sub_scores={},
                data_quality=RelativeStrengthDataQuality(
                    expected_rows=30,
                    actual_rows=35,
                    missing_rows=0,
                    missing_periods=(),
                    min_required_rows_met=True,
                    btc_benchmark_rows=35,
                    eth_benchmark_rows=35,
                    stale_input_count=0,
                    reason_codes=(),
                ),
                human_note="test",
                reason_codes=(),
            )

    def test_empty_symbol(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            RelativeStrengthScore(
                symbol="",
                base_benchmark=RelativeStrengthBenchmarkKind.BTC,
                state=RelativeStrengthState.READY,
                decision=RelativeStrengthDecision.NEUTRAL,
                total_score=50.0,
                period_returns=(),
                ratio_trend=RelativeStrengthRatioTrend(
                    last_ratio=1.0,
                    ma_ratio=1.0,
                    slope=0.01,
                    trend_score=50.0,
                    lookback=30,
                    has_data=True,
                    reason_codes=(),
                ),
                rank_percentile_30d=None,
                sub_scores={},
                data_quality=RelativeStrengthDataQuality(
                    expected_rows=30,
                    actual_rows=35,
                    missing_rows=0,
                    missing_periods=(),
                    min_required_rows_met=True,
                    btc_benchmark_rows=35,
                    eth_benchmark_rows=35,
                    stale_input_count=0,
                    reason_codes=(),
                ),
                human_note="test",
                reason_codes=(),
            )


class TestRelativeStrengthDataQuality:
    def test_valid_construction(self) -> None:
        dq = RelativeStrengthDataQuality(
            expected_rows=30,
            actual_rows=35,
            missing_rows=0,
            missing_periods=(),
            min_required_rows_met=True,
            btc_benchmark_rows=35,
            eth_benchmark_rows=35,
            stale_input_count=0,
            reason_codes=(),
        )
        assert dq.actual_rows == 35

    def test_negative_rows(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            RelativeStrengthDataQuality(
                expected_rows=30,
                actual_rows=-1,
                missing_rows=0,
                missing_periods=(),
                min_required_rows_met=True,
                btc_benchmark_rows=35,
                eth_benchmark_rows=35,
                stale_input_count=0,
                reason_codes=(),
            )

    def test_missing_rows_exceeds_expected(self) -> None:
        with pytest.raises(ValueError, match="missing_rows"):
            RelativeStrengthDataQuality(
                expected_rows=30,
                actual_rows=20,
                missing_rows=35,
                missing_periods=(),
                min_required_rows_met=True,
                btc_benchmark_rows=35,
                eth_benchmark_rows=35,
                stale_input_count=0,
                reason_codes=(),
            )


class TestRelativeStrengthUniverseSummary:
    def test_valid_construction(self) -> None:
        summary = RelativeStrengthUniverseSummary(
            total_coins=3,
            outperformer_count=1,
            neutral_count=1,
            underperformer_count=1,
            insufficient_data_count=0,
            blocked_count=0,
            top_outperformer="SOL",
            top_underperformer="DOGE",
            average_total_score=50.0,
            data_quality=RelativeStrengthDataQuality(
                expected_rows=30,
                actual_rows=35,
                missing_rows=0,
                missing_periods=(),
                min_required_rows_met=True,
                btc_benchmark_rows=35,
                eth_benchmark_rows=35,
                stale_input_count=0,
                reason_codes=(),
            ),
            summary_narrative="test",
        )
        assert summary.total_coins == 3

    def test_count_invariant(self) -> None:
        with pytest.raises(ValueError, match="sum"):
            RelativeStrengthUniverseSummary(
                total_coins=3,
                outperformer_count=2,
                neutral_count=2,
                underperformer_count=0,
                insufficient_data_count=0,
                blocked_count=0,
                top_outperformer=None,
                top_underperformer=None,
                average_total_score=50.0,
                data_quality=RelativeStrengthDataQuality(
                    expected_rows=30,
                    actual_rows=35,
                    missing_rows=0,
                    missing_periods=(),
                    min_required_rows_met=True,
                    btc_benchmark_rows=35,
                    eth_benchmark_rows=35,
                    stale_input_count=0,
                    reason_codes=(),
                ),
                summary_narrative="test",
            )


class TestRelativeStrengthReport:
    def test_blocked_factory(self) -> None:
        config = RelativeStrengthConfig()
        report = RelativeStrengthReport.blocked(
            report_id="test",
            config=config,
            reason_codes=("UNSAFE_INPUT_CONTENT",),
            generated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        assert report.kind == "relative_strength_report"
        assert len(report.scores) == 0
        assert report.universe_summary.blocked_count == 0

    def test_blocked_factory_deterministic(self) -> None:
        config = RelativeStrengthConfig()
        generated_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        report1 = RelativeStrengthReport.blocked(
            report_id="test", config=config, reason_codes=("UNSAFE_INPUT_CONTENT",), generated_at=generated_at
        )
        report2 = RelativeStrengthReport.blocked(
            report_id="test", config=config, reason_codes=("UNSAFE_INPUT_CONTENT",), generated_at=generated_at
        )
        assert report1.generated_at == report2.generated_at
        assert report1 == report2

    def test_metadata_normalization(self) -> None:
        config = RelativeStrengthConfig()
        report = RelativeStrengthReport.blocked(
            report_id="test", config=config, reason_codes=("UNSAFE_INPUT_CONTENT",), metadata={"foo": "bar"}
        )
        assert isinstance(report.metadata, MappingProxyType)
        assert report.metadata["foo"] == "bar"
