"""Tests for SPEC-072 Stage 6 (evidence availability) and Stage 7
(constant-delta blocks ROBUST_* classification)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from hunter.research_backtest_comparison.models import (
    EVIDENCE_AVAILABLE,
    EVIDENCE_BLOCKED,
    EVIDENCE_INSUFFICIENT_TRADES,
    EVIDENCE_MISSING_METRIC,
    EVIDENCE_PARSER_FAILED,
    EVIDENCE_TIMED_OUT,
    EVIDENCE_UNSUPPORTED_SCHEMA,
    EVIDENCE_ZERO_TRADES,
    EvidenceAvailability,
    classify_evidence_availability,
)
from hunter.research_statistical_confidence.classification import (
    classify_metric_confidence,
)
from hunter.research_statistical_confidence.models import (
    INSUFFICIENT_DISTINCT_VALUES,
    ROBUSTNESS_PASSED,
    ZERO_OBSERVED_DISPERSION,
    BootstrapConfig,
    BootstrapInterval,
    ConfidenceState,
    LeaveOneOutResult,
    MetricDirection,
    RobustnessCriteria,
    StatisticalConfidenceConfig,
)
from hunter.research_walk_forward.models import MetricDirection as _WFMetricDirection


# ---------------------------------------------------------------------------
# Evidence availability precedence ladder
# ---------------------------------------------------------------------------


class TestClassifyEvidenceAvailability:
    def _base_kwargs(self) -> dict:
        return dict(
            trade_count=5,
            min_trades=1,
            has_metric=True,
            parser_failed=False,
            blocked=False,
            timed_out=False,
            unsupported_schema=False,
        )

    def test_available_when_all_pass(self) -> None:
        result = classify_evidence_availability(**self._base_kwargs())
        assert result == EvidenceAvailability.AVAILABLE
        assert result.value == EVIDENCE_AVAILABLE

    def test_blocked_takes_precedence(self) -> None:
        result = classify_evidence_availability(
            **{**self._base_kwargs(), "blocked": True, "timed_out": True,
               "unsupported_schema": True, "parser_failed": True}
        )
        assert result == EvidenceAvailability.BLOCKED
        assert result.value == EVIDENCE_BLOCKED

    def test_timed_out_second_precedence(self) -> None:
        result = classify_evidence_availability(
            **{**self._base_kwargs(), "timed_out": True,
               "unsupported_schema": True, "parser_failed": True}
        )
        assert result == EvidenceAvailability.TIMED_OUT
        assert result.value == EVIDENCE_TIMED_OUT

    def test_unsupported_schema_third_precedence(self) -> None:
        result = classify_evidence_availability(
            **{**self._base_kwargs(), "unsupported_schema": True,
               "parser_failed": True}
        )
        assert result == EvidenceAvailability.UNSUPPORTED_SCHEMA
        assert result.value == EVIDENCE_UNSUPPORTED_SCHEMA

    def test_parser_failed_fourth_precedence(self) -> None:
        result = classify_evidence_availability(
            **{**self._base_kwargs(), "parser_failed": True}
        )
        assert result == EvidenceAvailability.PARSER_FAILED
        assert result.value == EVIDENCE_PARSER_FAILED

    def test_zero_trades_below_min_trades(self) -> None:
        # trade_count == 0 -> ZERO_TRADES (not INSUFFICIENT_TRADES)
        result = classify_evidence_availability(
            **{**self._base_kwargs(), "trade_count": 0}
        )
        assert result == EvidenceAvailability.ZERO_TRADES
        assert result.value == EVIDENCE_ZERO_TRADES

    def test_insufficient_trades(self) -> None:
        result = classify_evidence_availability(
            **{**self._base_kwargs(), "trade_count": 1, "min_trades": 5}
        )
        assert result == EvidenceAvailability.INSUFFICIENT_TRADES
        assert result.value == EVIDENCE_INSUFFICIENT_TRADES

    def test_missing_metric_when_trade_count_is_none(self) -> None:
        result = classify_evidence_availability(
            **{**self._base_kwargs(), "trade_count": None}
        )
        assert result == EvidenceAvailability.MISSING_METRIC
        assert result.value == EVIDENCE_MISSING_METRIC

    def test_missing_metric_when_has_metric_false(self) -> None:
        result = classify_evidence_availability(
            **{**self._base_kwargs(), "has_metric": False}
        )
        assert result == EvidenceAvailability.MISSING_METRIC

    def test_valid_numeric_zero_with_trades_is_available(self) -> None:
        # trade_count > 0 with a numeric-zero metric is AVAILABLE evidence,
        # NOT zero-trade unavailability.
        result = classify_evidence_availability(
            trade_count=5,
            min_trades=1,
            has_metric=True,  # metric value may be 0; we only care presence
        )
        assert result == EvidenceAvailability.AVAILABLE


# ---------------------------------------------------------------------------
# Constant-delta / insufficient-distinct blocks ROBUST_* classification
# ---------------------------------------------------------------------------


def _make_config() -> StatisticalConfidenceConfig:
    return StatisticalConfidenceConfig(
        minimum_available_window_count=2,
        confidence_level=Decimal("0.95"),
        bootstrap=BootstrapConfig(seed=42, iterations=100, min_distinct_values_for_bootstrap=2),
        robustness=RobustnessCriteria(
            sign_share_threshold=Decimal("0.6"),
            maximum_influence_ratio=Decimal("2.0"),
            confidence_level=Decimal("0.95"),
        ),
    )


def _make_loo() -> LeaveOneOutResult:
    return LeaveOneOutResult(
        mean_range=Decimal("0"),
        median_range=Decimal("0"),
        max_influence_window_index=0,
        max_influence_ratio=Decimal("1.0"),
        directions=(_WFMetricDirection.CANDIDATE_HIGHER,) * 3,
        sign_stable=True,
        reason_codes=(),
    )


class TestConstantDeltaBlocksRobust:
    def test_constant_nonzero_blocks_robust_candidate(self) -> None:
        # 3 deltas all = +0.5 => std_dev == 0, all-positive, bootstrap CI is
        # the point (0.5, 0.5) which excludes zero. Without the
        # zero_observed_dispersion guard this would return ROBUST_CANDIDATE.
        config = _make_config()
        mean_ci = BootstrapInterval(
            lower=Decimal("0.5"), upper=Decimal("0.5"),
            confidence_level=Decimal("0.95"),
        )
        state, codes = classify_metric_confidence(
            available_count=3,
            positive_share=Decimal("1.0"),
            negative_share=Decimal("0"),
            loo=_make_loo(),
            mean_ci=mean_ci,
            median_ci=None,
            config=config,
            zero_observed_dispersion=True,
        )
        assert state != ConfidenceState.ROBUST_CANDIDATE
        assert state != ConfidenceState.ROBUST_BASELINE
        # Directional stability preserved (sign_share + LOO both pass)
        assert state == ConfidenceState.DIRECTIONALLY_STABLE_CANDIDATE
        assert ZERO_OBSERVED_DISPERSION in codes
        assert ROBUSTNESS_PASSED not in codes

    def test_insufficient_distinct_values_blocks_robust(self) -> None:
        config = _make_config()
        mean_ci = BootstrapInterval(
            lower=Decimal("0.5"), upper=Decimal("0.5"),
            confidence_level=Decimal("0.95"),
        )
        state, codes = classify_metric_confidence(
            available_count=3,
            positive_share=Decimal("1.0"),
            negative_share=Decimal("0"),
            loo=_make_loo(),
            mean_ci=mean_ci,
            median_ci=None,
            config=config,
            insufficient_distinct_values=True,
        )
        assert state != ConfidenceState.ROBUST_CANDIDATE
        assert state != ConfidenceState.ROBUST_BASELINE
        assert INSUFFICIENT_DISTINCT_VALUES in codes

    def test_without_dispersion_flags_robust_still_attained(self) -> None:
        # Sanity check: when dispersion is sufficient, ROBUST_CANDIDATE still
        # attainable (i.e. the new flags are additive, not a wholesale block).
        config = _make_config()
        mean_ci = BootstrapInterval(
            lower=Decimal("0.5"), upper=Decimal("1.5"),
            confidence_level=Decimal("0.95"),
        )
        state, codes = classify_metric_confidence(
            available_count=3,
            positive_share=Decimal("1.0"),
            negative_share=Decimal("0"),
            loo=_make_loo(),
            mean_ci=mean_ci,
            median_ci=None,
            config=config,
        )
        assert state == ConfidenceState.ROBUST_CANDIDATE
        assert ROBUSTNESS_PASSED in codes

    def test_both_flags_present_both_reason_codes(self) -> None:
        config = _make_config()
        mean_ci = BootstrapInterval(
            lower=Decimal("0.5"), upper=Decimal("0.5"),
            confidence_level=Decimal("0.95"),
        )
        _, codes = classify_metric_confidence(
            available_count=3,
            positive_share=Decimal("1.0"),
            negative_share=Decimal("0"),
            loo=_make_loo(),
            mean_ci=mean_ci,
            median_ci=None,
            config=config,
            zero_observed_dispersion=True,
            insufficient_distinct_values=True,
        )
        assert ZERO_OBSERVED_DISPERSION in codes
        assert INSUFFICIENT_DISTINCT_VALUES in codes

    def test_classification_is_symmetric_for_baseline_direction(self) -> None:
        # all-negative constant sample -> DIRECTIONALLY_STABLE_BASELINE
        config = _make_config()
        mean_ci = BootstrapInterval(
            lower=Decimal("-1.5"), upper=Decimal("-1.5"),
            confidence_level=Decimal("0.95"),
        )
        state, codes = classify_metric_confidence(
            available_count=3,
            positive_share=Decimal("0"),
            negative_share=Decimal("1.0"),
            loo=_make_loo(),
            mean_ci=mean_ci,
            median_ci=None,
            config=config,
            zero_observed_dispersion=True,
        )
        assert state == ConfidenceState.DIRECTIONALLY_STABLE_BASELINE
        assert ZERO_OBSERVED_DISPERSION in codes
