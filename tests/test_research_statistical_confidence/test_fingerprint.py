"""Tests for the deterministic fingerprint module (MVP-67)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from hunter.research_statistical_confidence.fingerprint import (
    config_fingerprint,
    metric_results_fingerprint,
    regime_results_fingerprint,
    report_fingerprint,
    safety_flags_fingerprint,
)
from hunter.research_statistical_confidence.models import (
    BootstrapConfig,
    BootstrapInterval,
    ConfidenceState,
    ExperimentConfidenceReport,
    MetricConfidenceResult,
    RegimeConfidenceResult,
    RobustnessCriteria,
    StatisticalConfidenceConfig,
    StatisticalConfidenceManifest,
    StatisticalConfidenceSafetyFlags,
)
from hunter.research_walk_forward.models import MarketRegimeLabel, MetricDirection


class TestConfigFingerprint:
    def test_deterministic(self) -> None:
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
        fp1 = config_fingerprint(config)
        fp2 = config_fingerprint(config)
        assert fp1 == fp2
        assert len(fp1) == 64  # SHA-256 hex

    def test_different_configs_differ(self) -> None:
        config1 = StatisticalConfidenceConfig(
            minimum_available_window_count=3,
            confidence_level=Decimal("0.95"),
            bootstrap=BootstrapConfig(seed=42, iterations=1000),
            robustness=RobustnessCriteria(
                sign_share_threshold=Decimal("0.8"),
                maximum_influence_ratio=Decimal("0.3"),
                confidence_level=Decimal("0.95"),
            ),
        )
        config2 = StatisticalConfidenceConfig(
            minimum_available_window_count=5,
            confidence_level=Decimal("0.95"),
            bootstrap=BootstrapConfig(seed=42, iterations=1000),
            robustness=RobustnessCriteria(
                sign_share_threshold=Decimal("0.8"),
                maximum_influence_ratio=Decimal("0.3"),
                confidence_level=Decimal("0.95"),
            ),
        )
        assert config_fingerprint(config1) != config_fingerprint(config2)


class TestSafetyFlagsFingerprint:
    def test_deterministic(self) -> None:
        flags = StatisticalConfidenceSafetyFlags()
        fp1 = safety_flags_fingerprint(flags)
        fp2 = safety_flags_fingerprint(flags)
        assert fp1 == fp2


class TestMetricResultsFingerprint:
    def test_deterministic(self) -> None:
        mr = _make_metric_result()
        fp1 = metric_results_fingerprint({"ret": mr})
        fp2 = metric_results_fingerprint({"ret": mr})
        assert fp1 == fp2

    def test_different_results_differ(self) -> None:
        mr1 = _make_metric_result(mean=Decimal("2"))
        mr2 = _make_metric_result(mean=Decimal("3"))
        fp1 = metric_results_fingerprint({"ret": mr1})
        fp2 = metric_results_fingerprint({"ret": mr2})
        assert fp1 != fp2


class TestReportFingerprint:
    def test_deterministic(self) -> None:
        report = _make_report()
        fp1 = report_fingerprint(report)
        fp2 = report_fingerprint(report)
        assert fp1 == fp2

    def test_source_fingerprint_included(self) -> None:
        report1 = _make_report(source_fp="src-fp-1")
        report2 = _make_report(source_fp="src-fp-2")
        fp1 = report_fingerprint(report1)
        fp2 = report_fingerprint(report2)
        assert fp1 != fp2

    def test_different_configs_differ(self) -> None:
        report1 = _make_report()
        report2 = _make_report()
        # Change metric result
        mr2 = _make_metric_result(mean=Decimal("99"))
        from dataclasses import replace
        report2 = replace(report2, metric_results={"ret": mr2})
        fp1 = report_fingerprint(report1)
        fp2 = report_fingerprint(report2)
        assert fp1 != fp2


def _make_metric_result(
    mean: Decimal | None = Decimal("1.5"),
) -> MetricConfidenceResult:
    return MetricConfidenceResult(
        metric_name="total_return_pct",
        available_count=5,
        unavailable_count=1,
        mean=mean,
        median=Decimal("1.5"),
        std_dev=Decimal("0.5"),
        mad=Decimal("0.4"),
        min=Decimal("0.5"),
        max=Decimal("2.5"),
        q1=Decimal("1.0"),
        q3=Decimal("2.0"),
        iqr=Decimal("1.0"),
        positive_share=Decimal("0.8"),
        negative_share=Decimal("0.2"),
        zero_share=Decimal("0"),
        bootstrap_mean_ci=BootstrapInterval(
            lower=Decimal("0.5"), upper=Decimal("2.0"), confidence_level=Decimal("0.95")
        ),
        bootstrap_median_ci=BootstrapInterval(
            lower=Decimal("0.5"), upper=Decimal("2.0"), confidence_level=Decimal("0.95")
        ),
        loo=None,
        confidence_state=ConfidenceState.DIRECTIONALLY_STABLE_CANDIDATE,
    )


def _make_report(
    source_fp: str = "source-fp",
) -> ExperimentConfidenceReport:
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
    mr = _make_metric_result()
    rr = RegimeConfidenceResult(
        regime_label=MarketRegimeLabel.UNKNOWN,
        available_count=5,
        metric_results={"ret": mr},
        status_counts={"COMPLETED": 5},
        fingerprint="regime-fp",
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
    return ExperimentConfidenceReport(
        version="0.67.0-dev",
        spec_version="SPEC-068",
        statistical_confidence_version="0.67.0-dev",
        source_report_fingerprint=source_fp,
        config=config,
        metric_results={"ret": mr},
        regime_results={"UNKNOWN": rr},
        manifest=manifest,
        safety_flags=StatisticalConfidenceSafetyFlags(),
        fingerprint="placeholder",
    )
