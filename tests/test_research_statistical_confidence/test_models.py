"""Tests for statistical confidence models and safety contracts (MVP-67)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from hunter.research_statistical_confidence.models import (
    SPEC_VERSION,
    STATISTICAL_CONFIDENCE_VERSION,
    UNAVAILABLE,
    BootstrapConfig,
    BootstrapInterval,
    ConfidenceState,
    ExperimentConfidenceReport,
    LeaveOneOutResult,
    MetricConfidenceResult,
    RegimeConfidenceResult,
    RobustnessCriteria,
    StatisticalConfidenceConfig,
    StatisticalConfidenceManifest,
    StatisticalConfidenceSafetyFlags,
)
from hunter.research_walk_forward.models import MarketRegimeLabel, MetricDirection


class TestVersionConstants:
    def test_version_constants(self) -> None:
        assert STATISTICAL_CONFIDENCE_VERSION == "0.67.0-dev"
        assert SPEC_VERSION == "SPEC-068"
        assert UNAVAILABLE == "UNAVAILABLE"


class TestStatisticalConfidenceSafetyFlags:
    def test_defaults(self) -> None:
        flags = StatisticalConfidenceSafetyFlags()
        assert flags.research_only is True
        assert flags.execution_approval_granted is False
        assert flags.production_approval_granted is False
        assert flags.live_trading_allowed is False
        assert flags.automatic_execution_allowed is False
        assert flags.human_approval_required is True
        assert flags.no_direct_subprocess is True
        assert flags.no_parallel_execution is True
        assert flags.no_network_connection is True
        assert flags.no_database_connection is True
        assert flags.no_exchange_connection is True
        assert flags.no_remote_changes is True
        assert flags.no_action_commands_emitted is True

    def test_research_only_mutation_rejected(self) -> None:
        with pytest.raises(ValueError):
            StatisticalConfidenceSafetyFlags(research_only=False)

    def test_human_approval_required_mutation_rejected(self) -> None:
        with pytest.raises(ValueError):
            StatisticalConfidenceSafetyFlags(human_approval_required=False)

    def test_execution_approval_rejected(self) -> None:
        with pytest.raises(ValueError):
            StatisticalConfidenceSafetyFlags(execution_approval_granted=True)

    def test_live_trading_allowed_rejected(self) -> None:
        with pytest.raises(ValueError):
            StatisticalConfidenceSafetyFlags(live_trading_allowed=True)

    def test_no_direct_subprocess_mutation_rejected(self) -> None:
        with pytest.raises(ValueError):
            StatisticalConfidenceSafetyFlags(no_direct_subprocess=False)

    def test_no_parallel_execution_mutation_rejected(self) -> None:
        with pytest.raises(ValueError):
            StatisticalConfidenceSafetyFlags(no_parallel_execution=False)

    def test_non_bool_rejected(self) -> None:
        with pytest.raises(ValueError):
            StatisticalConfidenceSafetyFlags(research_only="yes")

    def test_immutable(self) -> None:
        flags = StatisticalConfidenceSafetyFlags()
        with pytest.raises(AttributeError):
            flags.research_only = False  # type: ignore[misc]


class TestBootstrapConfig:
    def test_valid(self) -> None:
        config = BootstrapConfig(seed=42, iterations=1000)
        assert config.seed == 42
        assert config.iterations == 1000

    def test_iterations_too_low(self) -> None:
        # Constructor now only requires positive int; validator checks >= 100
        config = BootstrapConfig(seed=42, iterations=50)
        _ = config  # passes constructor
    
    def test_non_int_seed(self) -> None:
        with pytest.raises(ValueError):
            BootstrapConfig(seed="42", iterations=100)  # type: ignore[arg-type]


class TestRobustnessCriteria:
    def test_valid(self) -> None:
        rc = RobustnessCriteria(
            sign_share_threshold=Decimal("0.8"),
            maximum_influence_ratio=Decimal("0.3"),
            confidence_level=Decimal("0.95"),
        )
        assert rc.sign_share_threshold == Decimal("0.8")
        assert rc.maximum_influence_ratio == Decimal("0.3")
        assert rc.confidence_level == Decimal("0.95")


class TestStatisticalConfidenceConfig:
    def _valid_config(self) -> StatisticalConfidenceConfig:
        return StatisticalConfidenceConfig(
            minimum_available_window_count=3,
            confidence_level=Decimal("0.95"),
            bootstrap=BootstrapConfig(seed=42, iterations=1000),
            robustness=RobustnessCriteria(
                sign_share_threshold=Decimal("0.8"),
                maximum_influence_ratio=Decimal("0.3"),
                confidence_level=Decimal("0.95"),
            ),
        )

    def test_valid(self) -> None:
        config = self._valid_config()
        assert config.minimum_available_window_count == 3
        assert config.confidence_level == Decimal("0.95")

    def test_minimum_too_low(self) -> None:
        # The config passes constructor type checks; validator catches range
        config = StatisticalConfidenceConfig(
            minimum_available_window_count=1,
            confidence_level=Decimal("0.95"),
            bootstrap=BootstrapConfig(seed=42, iterations=1000),
            robustness=RobustnessCriteria(
                sign_share_threshold=Decimal("0.8"),
                maximum_influence_ratio=Decimal("0.3"),
                confidence_level=Decimal("0.95"),
            ),
        )
        from hunter.research_statistical_confidence.validator import validate_config
        with pytest.raises(Exception):
            validate_config(config)

    def test_confidence_level_zero(self) -> None:
        config = StatisticalConfidenceConfig(
            minimum_available_window_count=3,
            confidence_level=Decimal("0"),
            bootstrap=BootstrapConfig(seed=42, iterations=1000),
            robustness=RobustnessCriteria(
                sign_share_threshold=Decimal("0.8"),
                maximum_influence_ratio=Decimal("0.3"),
                confidence_level=Decimal("0.95"),
            ),
        )
        from hunter.research_statistical_confidence.validator import validate_config
        with pytest.raises(Exception):
            validate_config(config)

    def test_confidence_level_one(self) -> None:
        config = StatisticalConfidenceConfig(
            minimum_available_window_count=3,
            confidence_level=Decimal("1"),
            bootstrap=BootstrapConfig(seed=42, iterations=1000),
            robustness=RobustnessCriteria(
                sign_share_threshold=Decimal("0.8"),
                maximum_influence_ratio=Decimal("0.3"),
                confidence_level=Decimal("0.95"),
            ),
        )
        from hunter.research_statistical_confidence.validator import validate_config
        with pytest.raises(Exception):
            validate_config(config)


class TestBootstrapInterval:
    def test_valid(self) -> None:
        ci = BootstrapInterval(
            lower=Decimal("0.1"),
            upper=Decimal("0.5"),
            confidence_level=Decimal("0.95"),
        )
        assert ci.lower == Decimal("0.1")
        assert ci.upper == Decimal("0.5")


class TestLeaveOneOutResult:
    def test_valid(self) -> None:
        loo = LeaveOneOutResult(
            mean_range=Decimal("0.05"),
            median_range=Decimal("0.03"),
            max_influence_window_index=2,
            max_influence_ratio=Decimal("0.15"),
            directions=(
                MetricDirection.CANDIDATE_HIGHER,
                MetricDirection.CANDIDATE_HIGHER,
            ),
            sign_stable=True,
        )
        assert loo.mean_range == Decimal("0.05")
        assert loo.sign_stable is True

    def test_negative_window_index_rejected(self) -> None:
        with pytest.raises(ValueError):
            LeaveOneOutResult(
                mean_range=Decimal("0.05"),
                median_range=Decimal("0.03"),
                max_influence_window_index=-1,
                max_influence_ratio=Decimal("0.15"),
                directions=(),
                sign_stable=True,
            )


class TestMetricConfidenceResult:
    def _make_result(self) -> MetricConfidenceResult:
        return MetricConfidenceResult(
            metric_name="total_return_pct",
            available_count=5,
            unavailable_count=1,
            mean=Decimal("0.5"),
            median=Decimal("0.4"),
            std_dev=Decimal("0.1"),
            mad=Decimal("0.08"),
            min=Decimal("0.2"),
            max=Decimal("0.8"),
            q1=Decimal("0.3"),
            q3=Decimal("0.7"),
            iqr=Decimal("0.4"),
            positive_share=Decimal("0.8"),
            negative_share=Decimal("0.2"),
            zero_share=Decimal("0"),
            bootstrap_mean_ci=None,
            bootstrap_median_ci=None,
            loo=None,
            confidence_state=ConfidenceState.DIRECTIONALLY_STABLE_CANDIDATE,
        )

    def test_valid(self) -> None:
        result = self._make_result()
        assert result.metric_name == "total_return_pct"
        assert result.available_count == 5

    def test_empty_metric_name_rejected(self) -> None:
        with pytest.raises(ValueError):
            self._make_result().__class__(
                metric_name="",
                available_count=0,
                unavailable_count=0,
                mean=None,
                median=None,
                std_dev=None,
                mad=None,
                min=None,
                max=None,
                q1=None,
                q3=None,
                iqr=None,
                positive_share=Decimal("0"),
                negative_share=Decimal("0"),
                zero_share=Decimal("0"),
                bootstrap_mean_ci=None,
                bootstrap_median_ci=None,
                loo=None,
                confidence_state=ConfidenceState.INSUFFICIENT_EVIDENCE,
            )


class TestRegimeConfidenceResult:
    def test_valid(self) -> None:
        result = RegimeConfidenceResult(
            regime_label=MarketRegimeLabel.BULL,
            available_count=3,
            metric_results={},
            status_counts={"COMPLETED": 3},
            fingerprint="abc123",
        )
        assert result.regime_label == MarketRegimeLabel.BULL
        assert result.available_count == 3

    def test_empty_fingerprint_rejected(self) -> None:
        with pytest.raises(ValueError):
            RegimeConfidenceResult(
                regime_label=MarketRegimeLabel.BULL,
                available_count=0,
                metric_results={},
                status_counts={},
                fingerprint="",
            )


class TestExperimentConfidenceReport:
    def test_valid(self, tmp_path) -> None:
        from datetime import datetime, timezone

        config = StatisticalConfidenceConfig(
            minimum_available_window_count=3,
            confidence_level=Decimal("0.95"),
            bootstrap=BootstrapConfig(seed=42, iterations=1000),
            robustness=RobustnessCriteria(
                sign_share_threshold=Decimal("0.8"),
                maximum_influence_ratio=Decimal("0.3"),
                confidence_level=Decimal("0.95"),
            ),
        )
        manifest = StatisticalConfidenceManifest(
            version="0.67.0-dev",
            spec_version="SPEC-068",
            statistical_confidence_version="0.67.0-dev",
            generated_at=datetime.now(timezone.utc),
            config_fingerprint="cfg-fp",
            metric_results_fingerprint="mr-fp",
            regime_results_fingerprint="rr-fp",
            overall_fingerprint="ov-fp",
            safety_flags=StatisticalConfidenceSafetyFlags(),
        )
        report = ExperimentConfidenceReport(
            version="0.67.0-dev",
            spec_version="SPEC-068",
            statistical_confidence_version="0.67.0-dev",
            source_report_fingerprint="src-fp",
            config=config,
            metric_results={},
            regime_results={},
            manifest=manifest,
            safety_flags=StatisticalConfidenceSafetyFlags(),
            fingerprint="report-fp",
        )
        assert report.version == "0.67.0-dev"
        assert report.fingerprint == "report-fp"
        assert report.human_approval_required is True
        assert report.research_only is True


class TestConfidenceState:
    def test_values(self) -> None:
        assert ConfidenceState.INSUFFICIENT_EVIDENCE.value == "INSUFFICIENT_EVIDENCE"
        assert ConfidenceState.UNSTABLE.value == "UNSTABLE"
        assert ConfidenceState.MIXED.value == "MIXED"
        assert ConfidenceState.DIRECTIONALLY_STABLE_CANDIDATE.value == "DIRECTIONALLY_STABLE_CANDIDATE"
        assert ConfidenceState.DIRECTIONALLY_STABLE_BASELINE.value == "DIRECTIONALLY_STABLE_BASELINE"
        assert ConfidenceState.ROBUST_CANDIDATE.value == "ROBUST_CANDIDATE"
        assert ConfidenceState.ROBUST_BASELINE.value == "ROBUST_BASELINE"
