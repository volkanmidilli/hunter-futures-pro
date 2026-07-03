"""Tests for hunter.backtest.models."""

from __future__ import annotations

from datetime import datetime, timezone
from types import MappingProxyType

import pytest

from hunter.backtest import (
    FORBIDDEN_BACKTEST_TERMS,
    UNSAFE_BACKTEST_CONTENT,
    BacktestAllocationMode,
    BacktestCandidateDecision,
    BacktestCandidateResult,
    BacktestDataQuality,
    BacktestInput,
    BacktestInputKind,
    BacktestPortfolioResult,
    BacktestPortfolioSnapshot,
    BacktestPriceBar,
    BacktestReport,
    BacktestRunConfig,
    BacktestSafetyFlags,
    BacktestState,
    build_backtest_report,
    has_unsafe_backtest_content,
)


@pytest.fixture
def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def make_bar(
    pair: str = "SOL/USDT:USDT",
    timestamp: datetime | None = None,
    close: float = 100.0,
) -> BacktestPriceBar:
    return BacktestPriceBar(
        pair=pair,
        timestamp=timestamp or datetime(2024, 1, 1, tzinfo=timezone.utc),
        close=close,
    )


class TestBacktestPriceBar:
    def test_valid_bar(self, utcnow: datetime) -> None:
        bar = BacktestPriceBar(
            pair="BTC/USDT:USDT",
            timestamp=utcnow,
            close=50000.0,
            open=50000.0,
            high=51000.0,
            low=49000.0,
            volume=1000.0,
        )
        assert bar.pair == "BTC/USDT:USDT"
        assert bar.close == 50000.0
        assert bar.timestamp.tzinfo is not None

    def test_close_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="close must be a strictly positive"):
            BacktestPriceBar(
                pair="BTC/USDT:USDT",
                timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
                close=0.0,
            )

    def test_close_negative_rejected(self) -> None:
        with pytest.raises(ValueError, match="close must be a strictly positive"):
            BacktestPriceBar(
                pair="BTC/USDT:USDT",
                timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
                close=-1.0,
            )

    def test_timestamp_must_be_timezone_aware(self) -> None:
        with pytest.raises(ValueError, match="timezone-aware"):
            BacktestPriceBar(
                pair="BTC/USDT:USDT",
                timestamp=datetime(2024, 1, 1),
                close=100.0,
            )

    def test_metadata_is_immutable_mapping(self) -> None:
        bar = BacktestPriceBar(
            pair="BTC/USDT:USDT",
            timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            close=100.0,
            metadata={"note": "hello"},
        )
        assert isinstance(bar.metadata, MappingProxyType)


class TestBacktestCandidateDecision:
    def test_valid_decision(self) -> None:
        d = BacktestCandidateDecision(
            pair="BTC/USDT:USDT",
            state="INCLUDED",
            classification="CORE_RESEARCH_ALLOCATION",
            final_weight_pct=25.0,
        )
        assert d.pair == "BTC/USDT:USDT"
        assert d.state == "INCLUDED"
        assert d.final_weight_pct == 25.0

    def test_weight_pct_bounds(self) -> None:
        with pytest.raises(ValueError, match="research_weight_pct"):
            BacktestCandidateDecision(
                pair="BTC/USDT:USDT",
                state="INCLUDED",
                classification="X",
                research_weight_pct=101.0,
            )


class TestBacktestInput:
    def test_valid_input(self, utcnow: datetime) -> None:
        decision = BacktestCandidateDecision(
            pair="BTC/USDT:USDT",
            state="INCLUDED",
            classification="X",
        )
        bar = make_bar(pair="BTC/USDT:USDT", timestamp=utcnow)
        inp = BacktestInput(
            pair="BTC/USDT:USDT",
            decision=decision,
            price_bars=(bar,),
            input_kind=BacktestInputKind.SUMMARY,
        )
        assert inp.decision == decision
        assert inp.price_bars == (bar,)

    def test_pair_mismatch_decision(self) -> None:
        decision = BacktestCandidateDecision(
            pair="BTC/USDT:USDT",
            state="INCLUDED",
            classification="X",
        )
        with pytest.raises(ValueError, match="decision.pair must match"):
            BacktestInput(pair="ETH/USDT:USDT", decision=decision)

    def test_pair_mismatch_price_bars(self) -> None:
        bar = make_bar(pair="BTC/USDT:USDT")
        with pytest.raises(ValueError, match=r"price_bars\[i\]\.pair must match"):
            BacktestInput(pair="ETH/USDT:USDT", price_bars=(bar,))


class TestBacktestRunConfig:
    def test_default_config(self) -> None:
        cfg = BacktestRunConfig()
        assert cfg.allocation_mode == BacktestAllocationMode.RESEARCH_WEIGHT
        assert cfg.volatility_scale_factor == 1.0
        assert cfg.min_observation_count == 2

    def test_volatility_scale_factor_must_be_positive(self) -> None:
        cfg = BacktestRunConfig(volatility_scale_factor=0.0)
        report = build_backtest_report([], cfg)
        assert report.portfolio_result.candidate_count == 0
        assert report.data_quality.safety_flags_ok is False

    def test_volatility_scale_factor_must_be_finite(self) -> None:
        cfg = BacktestRunConfig(volatility_scale_factor=float("inf"))
        report = build_backtest_report([], cfg)
        assert report.portfolio_result.candidate_count == 0
        assert report.data_quality.safety_flags_ok is False

    def test_custom_weights_non_negative(self) -> None:
        cfg = BacktestRunConfig(custom_weights={"BTC/USDT:USDT": -1.0})
        report = build_backtest_report([], cfg)
        assert report.portfolio_result.candidate_count == 0
        assert report.data_quality.safety_flags_ok is False

    def test_start_after_end_rejected(self) -> None:
        start = datetime(2024, 1, 2, tzinfo=timezone.utc)
        end = datetime(2024, 1, 1, tzinfo=timezone.utc)
        cfg = BacktestRunConfig(start_timestamp=start, end_timestamp=end)
        report = build_backtest_report([], cfg)
        assert report.portfolio_result.candidate_count == 0
        assert report.data_quality.safety_flags_ok is False

    def test_naive_datetimes_rejected(self) -> None:
        cfg = BacktestRunConfig(start_timestamp=datetime(2024, 1, 1))
        report = build_backtest_report([], cfg)
        assert report.portfolio_result.candidate_count == 0
        assert report.data_quality.safety_flags_ok is False


class TestBacktestCandidateResult:
    def test_reason_code_validation(self) -> None:
        with pytest.raises(ValueError, match="unsupported reason code"):
            BacktestCandidateResult(
                pair="BTC/USDT:USDT",
                state=BacktestState.INCLUDED,
                classification="X",
                allocation_mode=BacktestAllocationMode.RESEARCH_WEIGHT,
                simulated_weight=0.0,
                total_return_pct=0.0,
                max_drawdown_pct=0.0,
                volatility_pct=0.0,
                win_rate_pct=0.0,
                observation_count=0,
                missing_data_count=0,
                insufficient_data_count=0,
                period_returns=(),
                reason_codes=("INVALID_CODE",),
                tags=(),
                metadata={},
                notes=(),
                rank=None,
            )

    def test_total_return_pct_can_be_negative(self) -> None:
        result = BacktestCandidateResult(
            pair="BTC/USDT:USDT",
            state=BacktestState.INCLUDED,
            classification="X",
            allocation_mode=BacktestAllocationMode.RESEARCH_WEIGHT,
            simulated_weight=0.0,
            total_return_pct=-10.0,
            max_drawdown_pct=0.0,
            volatility_pct=0.0,
            win_rate_pct=0.0,
            observation_count=0,
            missing_data_count=0,
            insufficient_data_count=0,
            period_returns=(),
            reason_codes=(),
            tags=(),
            metadata={},
            notes=(),
            rank=None,
        )
        assert result.total_return_pct == -10.0


class TestBacktestDataQuality:
    def test_counts_must_sum_to_total_inputs(self) -> None:
        with pytest.raises(ValueError, match="State counts must sum to total_inputs"):
            BacktestDataQuality(
                total_inputs=3,
                included_count=1,
                capped_count=1,
                watchlist_count=0,
                excluded_count=0,
                insufficient_data_count=0,
                blocked_count=0,
                ready_price_history_count=0,
                missing_price_history_count=0,
                blocked_decision_count=0,
                observation_count=0,
                missing_data_count=0,
                data_quality_score=0.0,
                all_counts_consistent=True,
                safety_flags_ok=True,
                has_unsafe_content=False,
            )

    def test_data_quality_score_bounds(self) -> None:
        with pytest.raises(ValueError, match="data_quality_score must be in"):
            BacktestDataQuality(
                total_inputs=1,
                included_count=1,
                capped_count=0,
                watchlist_count=0,
                excluded_count=0,
                insufficient_data_count=0,
                blocked_count=0,
                ready_price_history_count=1,
                missing_price_history_count=0,
                blocked_decision_count=0,
                observation_count=1,
                missing_data_count=0,
                data_quality_score=101.0,
                all_counts_consistent=True,
                safety_flags_ok=True,
                has_unsafe_content=False,
            )


class TestBacktestSafetyFlags:
    def test_is_safe_when_all_true_and_no_has_flags(self) -> None:
        flags = BacktestSafetyFlags()
        assert flags.is_safe is True
        assert flags.safety_flags_ok is True

    def test_unsafe_content_breaks_is_safe(self) -> None:
        flags = BacktestSafetyFlags(has_unsafe_content=True)
        assert flags.is_safe is False

    def test_invalid_pair_breaks_is_safe(self) -> None:
        flags = BacktestSafetyFlags(has_invalid_pair=True)
        assert flags.is_safe is False


class TestForbiddenTerms:
    def test_forbidden_terms_is_frozenset(self) -> None:
        assert isinstance(FORBIDDEN_BACKTEST_TERMS, frozenset)
        assert "order" in FORBIDDEN_BACKTEST_TERMS
        assert "binance" in FORBIDDEN_BACKTEST_TERMS

    def test_has_unsafe_backtest_content_detects_trading_term(self) -> None:
        assert has_unsafe_backtest_content("buy_signal", [], {}) is True

    def test_has_unsafe_backtest_content_detects_metadata_term(self) -> None:
        assert (
            has_unsafe_backtest_content(
                "PAIR", [], {"note": "this is a trade signal"}
            )
            is True
        )

    def test_safe_content_returns_false(self) -> None:
        assert has_unsafe_backtest_content("PAIR", [], {"note": "research"}) is False

    def test_case_insensitive(self) -> None:
        assert has_unsafe_backtest_content("BUY", [], {}) is True

    def test_custom_forbidden_terms(self) -> None:
        assert has_unsafe_backtest_content("xyz", [], {}, frozenset({"xyz"})) is True


class TestBacktestReportBlocked:
    def test_blocked_report(self) -> None:
        report = BacktestReport.blocked(reason_code=UNSAFE_BACKTEST_CONTENT)
        assert report.version == "0.28.0-dev"
        assert report.candidate_results == ()
        assert report.portfolio_result.candidate_count == 0
        assert report.data_quality.safety_flags_ok is False
        assert report.safety_flags.has_unsafe_content is True

    def test_blocked_report_invalid_reason_code(self) -> None:
        with pytest.raises(ValueError, match="unsupported reason code"):
            BacktestReport.blocked(reason_code="INVALID_CODE")
