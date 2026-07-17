"""Tests for the statistical confidence validator (MVP-67)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from hunter.research_statistical_confidence.models import (
    BootstrapConfig,
    RobustnessCriteria,
    StatisticalConfidenceConfig,
    StatisticalConfidenceSafetyFlags,
)
from hunter.research_statistical_confidence.validator import (
    validate_config,
    validate_source_report,
)
from hunter.research_walk_forward.models import (
    MarketRegimeLabel,
    MetricDirection,
    WalkForwardCommonConfig,
    WalkForwardExperimentPlan,
    WalkForwardExperimentReport,
    WalkForwardManifest,
    WalkForwardMode,
    WalkForwardSafetyFlags,
    WalkForwardWindow,
    WalkForwardWindowResult,
    WindowStatus,
)


def _make_src_report() -> WalkForwardExperimentReport:
    """Build a minimal valid source report."""
    window = WalkForwardWindow(
        selection_start="20240101",
        selection_end="20240201",
        evaluation_start="20240201",
        evaluation_end="20240301",
        regime_label=MarketRegimeLabel.UNKNOWN,
    )
    w_result = WalkForwardWindowResult(
        window=window,
        window_index=0,
        status=WindowStatus.COMPLETED,
        candidate_metrics={"total_return_pct": Decimal("5")},
        baseline_metrics={"total_return_pct": Decimal("3")},
        metric_deltas={"total_return_pct": Decimal("2")},
        metric_directions={"total_return_pct": MetricDirection.CANDIDATE_HIGHER},
        comparison_fingerprint="cmp-fp",
        candidate_fingerprint="c-fp",
        baseline_fingerprint="b-fp",
        fingerprint="w-fp",
    )
    common = WalkForwardCommonConfig(
        strategy_name="Test",
        strategy_path="/tmp/test.py",
        data_path="/tmp/data",
        timeframe="1h",
        balance=Decimal("1000"),
        stake=Decimal("100"),
        max_open_trades=3,
        fee=Decimal("0.001"),
        executable_path="/tmp/freqtrade",
    )
    plan = WalkForwardExperimentPlan(
        mode=WalkForwardMode.ROLLING,
        windows=(window,),
        common=common,
        safety_flags=WalkForwardSafetyFlags(),
        fingerprint="plan-fp",
    )
    manifest = WalkForwardManifest(
        version="0.66.0-dev",
        spec_version="SPEC-067",
        walk_forward_version="0.66.0-dev",
        generated_at=datetime.now(timezone.utc),
        plan_fingerprint="plan-fp",
        overall_aggregate_fingerprint="agg-fp",
        regime_aggregate_fingerprint="reg-fp",
        safety_flags=WalkForwardSafetyFlags(),
    )
    return WalkForwardExperimentReport(
        version="0.66.0-dev",
        spec_version="SPEC-067",
        walk_forward_version="0.66.0-dev",
        plan=plan,
        window_results=(w_result,),
        metric_aggregates={},
        regime_aggregates=(),
        manifest=manifest,
        safety_flags=WalkForwardSafetyFlags(),
        fingerprint="report-fp",
    )


class TestValidateConfig:
    def test_valid_config(self) -> None:
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
        # Should not raise
        validate_config(config)

    def test_none_config(self) -> None:
        with pytest.raises(Exception):
            validate_config(None)

    def test_minimum_too_low(self) -> None:
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
        with pytest.raises(Exception):
            validate_config(config)

    def test_bootstrap_iterations_too_low(self) -> None:
        config = StatisticalConfidenceConfig(
            minimum_available_window_count=3,
            confidence_level=Decimal("0.95"),
            bootstrap=BootstrapConfig(seed=42, iterations=50),
            robustness=RobustnessCriteria(
                sign_share_threshold=Decimal("0.8"),
                maximum_influence_ratio=Decimal("0.3"),
                confidence_level=Decimal("0.95"),
            ),
        )
        with pytest.raises(Exception):
            validate_config(config)

    def test_sign_share_threshold_out_of_range(self) -> None:
        config = StatisticalConfidenceConfig(
            minimum_available_window_count=3,
            confidence_level=Decimal("0.95"),
            bootstrap=BootstrapConfig(seed=42, iterations=1000),
            robustness=RobustnessCriteria(
                sign_share_threshold=Decimal("0.3"),
                maximum_influence_ratio=Decimal("0.3"),
                confidence_level=Decimal("0.95"),
            ),
        )
        with pytest.raises(Exception):
            validate_config(config)

    def test_maximum_influence_ratio_out_of_range(self) -> None:
        config = StatisticalConfidenceConfig(
            minimum_available_window_count=3,
            confidence_level=Decimal("0.95"),
            bootstrap=BootstrapConfig(seed=42, iterations=1000),
            robustness=RobustnessCriteria(
                sign_share_threshold=Decimal("0.8"),
                maximum_influence_ratio=Decimal("1.5"),
                confidence_level=Decimal("0.95"),
            ),
        )
        with pytest.raises(Exception):
            validate_config(config)


class TestValidateSourceReport:
    def test_valid_report(self) -> None:
        report = _make_src_report()
        validate_source_report(report)

    def test_none_report(self) -> None:
        with pytest.raises(Exception):
            validate_source_report(None)

    def test_missing_fingerprint(self) -> None:
        report = _make_src_report()
        # Bypass frozen dataclass to set empty fingerprint
        object.__setattr__(report, "fingerprint", "")
        with pytest.raises(Exception):
            validate_source_report(report)

    def test_research_only_false(self) -> None:
        report = _make_src_report()
        safety_flags = WalkForwardSafetyFlags()
        object.__setattr__(safety_flags, "research_only", False)
        object.__setattr__(report, "safety_flags", safety_flags)
        object.__setattr__(report, "research_only", False)
        with pytest.raises(Exception):
            validate_source_report(report)

    def test_live_trading_allowed(self) -> None:
        report = _make_src_report()
        safety_flags = WalkForwardSafetyFlags()
        object.__setattr__(safety_flags, "live_trading_allowed", True)
        object.__setattr__(report, "safety_flags", safety_flags)
        with pytest.raises(Exception):
            validate_source_report(report)

    def test_automatic_execution_allowed(self) -> None:
        report = _make_src_report()
        safety_flags = WalkForwardSafetyFlags()
        object.__setattr__(safety_flags, "automatic_execution_allowed", True)
        object.__setattr__(report, "safety_flags", safety_flags)
        with pytest.raises(Exception):
            validate_source_report(report)

    def test_execution_approval_granted(self) -> None:
        report = _make_src_report()
        safety_flags = WalkForwardSafetyFlags()
        object.__setattr__(safety_flags, "execution_approval_granted", True)
        object.__setattr__(report, "safety_flags", safety_flags)
        with pytest.raises(Exception):
            validate_source_report(report)
