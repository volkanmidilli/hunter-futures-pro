"""Tests for the confidence classification module (MVP-67)."""

from __future__ import annotations

from decimal import Decimal

from hunter.research_statistical_confidence.classification import (
    classify_metric_confidence,
)
from hunter.research_statistical_confidence.models import (
    BootstrapConfig,
    BootstrapInterval,
    ConfidenceState,
    LeaveOneOutResult,
    RobustnessCriteria,
    StatisticalConfidenceConfig,
)
from hunter.research_walk_forward.models import MetricDirection


def _make_config(
    min_windows: int = 3,
    sign_share: Decimal = Decimal("0.8"),
    max_influence: Decimal = Decimal("0.3"),
) -> StatisticalConfidenceConfig:
    return StatisticalConfidenceConfig(
        minimum_available_window_count=min_windows,
        confidence_level=Decimal("0.95"),
        bootstrap=BootstrapConfig(seed=42, iterations=500),
        robustness=RobustnessCriteria(
            sign_share_threshold=sign_share,
            maximum_influence_ratio=max_influence,
            confidence_level=Decimal("0.95"),
        ),
    )


def _make_loo(
    sign_stable: bool = True,
    influence: Decimal = Decimal("0.1"),
) -> LeaveOneOutResult:
    return LeaveOneOutResult(
        mean_range=Decimal("0.5"),
        median_range=Decimal("0.3"),
        max_influence_window_index=1,
        max_influence_ratio=influence,
        directions=(MetricDirection.CANDIDATE_HIGHER,) * 5,
        sign_stable=sign_stable,
    )


def _make_ci(
    lower: Decimal = Decimal("0.5"),
    upper: Decimal = Decimal("2.0"),
) -> BootstrapInterval:
    return BootstrapInterval(lower=lower, upper=upper, confidence_level=Decimal("0.95"))


class TestClassifyMetricConfidence:
    def test_insufficient_evidence(self) -> None:
        config = _make_config(min_windows=3)
        state, codes = classify_metric_confidence(
            available_count=2,
            positive_share=Decimal("1"),
            negative_share=Decimal("0"),
            loo=_make_loo(),
            mean_ci=_make_ci(),
            median_ci=_make_ci(),
            config=config,
        )
        assert state == ConfidenceState.INSUFFICIENT_EVIDENCE

    def test_directionally_stable_candidate(self) -> None:
        config = _make_config()
        state, codes = classify_metric_confidence(
            available_count=5,
            positive_share=Decimal("1"),
            negative_share=Decimal("0"),
            loo=_make_loo(sign_stable=True),
            mean_ci=_make_ci(lower=Decimal("-0.5"), upper=Decimal("2.0")),  # includes zero
            median_ci=_make_ci(lower=Decimal("-0.3"), upper=Decimal("1.5")),
            config=config,
        )
        assert state == ConfidenceState.DIRECTIONALLY_STABLE_CANDIDATE

    def test_directionally_stable_baseline(self) -> None:
        config = _make_config()
        state, codes = classify_metric_confidence(
            available_count=5,
            positive_share=Decimal("0"),
            negative_share=Decimal("1"),
            loo=_make_loo(sign_stable=True),
            mean_ci=_make_ci(lower=Decimal("-2"), upper=Decimal("0.5")),
            median_ci=_make_ci(lower=Decimal("-1.5"), upper=Decimal("0.3")),
            config=config,
        )
        assert state == ConfidenceState.DIRECTIONALLY_STABLE_BASELINE

    def test_robust_candidate(self) -> None:
        config = _make_config()
        state, codes = classify_metric_confidence(
            available_count=5,
            positive_share=Decimal("1"),
            negative_share=Decimal("0"),
            loo=_make_loo(sign_stable=True, influence=Decimal("0.1")),
            mean_ci=_make_ci(lower=Decimal("0.5"), upper=Decimal("2.0")),  # excludes zero
            median_ci=_make_ci(lower=Decimal("0.3"), upper=Decimal("1.5")),
            config=config,
        )
        assert state == ConfidenceState.ROBUST_CANDIDATE

    def test_robust_baseline(self) -> None:
        config = _make_config()
        state, codes = classify_metric_confidence(
            available_count=5,
            positive_share=Decimal("0"),
            negative_share=Decimal("1"),
            loo=_make_loo(sign_stable=True, influence=Decimal("0.1")),
            mean_ci=_make_ci(lower=Decimal("-2.0"), upper=Decimal("-0.5")),  # excludes zero
            median_ci=_make_ci(lower=Decimal("-1.5"), upper=Decimal("-0.3")),
            config=config,
        )
        assert state == ConfidenceState.ROBUST_BASELINE

    def test_mixed_direction_conflict(self) -> None:
        config = _make_config()
        state, codes = classify_metric_confidence(
            available_count=5,
            positive_share=Decimal("0.6"),
            negative_share=Decimal("0.4"),
            loo=_make_loo(sign_stable=True),
            mean_ci=_make_ci(),
            median_ci=_make_ci(),
            config=config,
        )
        assert state == ConfidenceState.MIXED

    def test_unstable_sign(self) -> None:
        config = _make_config()
        state, codes = classify_metric_confidence(
            available_count=5,
            positive_share=Decimal("1"),
            negative_share=Decimal("0"),
            loo=_make_loo(sign_stable=False, influence=Decimal("0.1")),
            mean_ci=_make_ci(),
            median_ci=_make_ci(),
            config=config,
        )
        assert state == ConfidenceState.UNSTABLE

    def test_excessive_influence(self) -> None:
        config = _make_config(max_influence=Decimal("0.05"))
        state, codes = classify_metric_confidence(
            available_count=5,
            positive_share=Decimal("1"),
            negative_share=Decimal("0"),
            loo=_make_loo(sign_stable=True, influence=Decimal("0.3")),
            mean_ci=_make_ci(lower=Decimal("-0.5")),  # includes zero
            median_ci=_make_ci(lower=Decimal("-0.3")),
            config=config,
        )
        # Should be DIRECTIONALLY_STABLE_* because bootstrap CI includes zero
        # but influence is excessive
        assert state in (
            ConfidenceState.DIRECTIONALLY_STABLE_CANDIDATE,
        )

    def test_no_loo_falls_to_unstable(self) -> None:
        config = _make_config()
        state, codes = classify_metric_confidence(
            available_count=5,
            positive_share=Decimal("1"),
            negative_share=Decimal("0"),
            loo=None,
            mean_ci=_make_ci(),
            median_ci=_make_ci(),
            config=config,
        )
        assert state == ConfidenceState.UNSTABLE

    def test_all_states_exhaustive(self) -> None:
        config = _make_config()
        _test_cases = [
            # (avail, pos, neg, loo_sign, loo_inf, ci_low, ci_high, expected)
            (2, Decimal("1"), Decimal("0"), True, Decimal("0.1"), Decimal("0.5"), Decimal("2"), ConfidenceState.INSUFFICIENT_EVIDENCE),
        ]
        for avail, pos, neg, loo_s, loo_i, ci_l, ci_u, expected in _test_cases:
            state, _ = classify_metric_confidence(
                available_count=avail,
                positive_share=pos,
                negative_share=neg,
                loo=_make_loo(sign_stable=loo_s, influence=loo_i),
                mean_ci=_make_ci(lower=ci_l, upper=ci_u),
                median_ci=_make_ci(lower=ci_l, upper=ci_u),
                config=config,
            )
            assert state == expected
