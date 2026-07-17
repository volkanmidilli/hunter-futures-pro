"""Tests for the statistical confidence writer (MVP-67)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal

import pytest

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
from hunter.research_statistical_confidence.writer import (
    StatisticalConfidenceWriter,
    write_all_statistical_confidence_artifacts,
    write_experiment_confidence_report,
)
from hunter.research_walk_forward.models import MarketRegimeLabel


@pytest.fixture
def config() -> StatisticalConfidenceConfig:
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


@pytest.fixture
def report(config: StatisticalConfidenceConfig) -> ExperimentConfidenceReport:
    mr = MetricConfidenceResult(
        metric_name="total_return_pct",
        available_count=5,
        unavailable_count=1,
        mean=Decimal("1.5"),
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
    rr = RegimeConfidenceResult(
        regime_label=MarketRegimeLabel.UNKNOWN,
        available_count=5,
        metric_results={"total_return_pct": mr},
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
        source_report_fingerprint="src-fp",
        config=config,
        metric_results={"total_return_pct": mr},
        regime_results={"UNKNOWN": rr},
        manifest=manifest,
        safety_flags=StatisticalConfidenceSafetyFlags(),
        fingerprint="report-fp",
    )


class TestStatisticalConfidenceWriter:
    def test_mandatory_output_dir(self) -> None:
        with pytest.raises(Exception):
            StatisticalConfidenceWriter()

    def test_empty_output_dir(self) -> None:
        with pytest.raises(Exception):
            StatisticalConfidenceWriter(output_dir="")

    def test_write_config(self, report: ExperimentConfidenceReport, tmp_path) -> None:
        writer = StatisticalConfidenceWriter(output_dir=tmp_path)
        path = writer.write_config(report.config)
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["minimum_available_window_count"] == 3
        assert data["confidence_level"] == "0.95"

    def test_write_metric_results(self, report: ExperimentConfidenceReport, tmp_path) -> None:
        writer = StatisticalConfidenceWriter(output_dir=tmp_path)
        path = writer.write_metric_results(report)
        assert path.exists()
        data = json.loads(path.read_text())
        assert "metric_results" in data
        assert "total_return_pct" in data["metric_results"]

    def test_write_regime_results(self, report: ExperimentConfidenceReport, tmp_path) -> None:
        writer = StatisticalConfidenceWriter(output_dir=tmp_path)
        path = writer.write_regime_results(report)
        assert path.exists()
        data = json.loads(path.read_text())
        assert "regime_results" in data

    def test_write_report(self, report: ExperimentConfidenceReport, tmp_path) -> None:
        writer = StatisticalConfidenceWriter(output_dir=tmp_path)
        path = writer.write_report(report)
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["fingerprint"] == "report-fp"
        assert data["research_only"] is True

    def test_write_manifest(self, report: ExperimentConfidenceReport, tmp_path) -> None:
        writer = StatisticalConfidenceWriter(output_dir=tmp_path)
        path = writer.write_manifest(report)
        assert path.exists()
        data = json.loads(path.read_text())
        assert "overall_fingerprint" in data

    def test_write_markdown(self, report: ExperimentConfidenceReport, tmp_path) -> None:
        writer = StatisticalConfidenceWriter(output_dir=tmp_path)
        path = writer.write_markdown(report)
        assert path.exists()
        text = path.read_text()
        assert "Walk-Forward Statistical Confidence Report" in text
        assert "Research only" in text or "research-only" in text

    def test_silent_overwrite_protection(self, report: ExperimentConfidenceReport, tmp_path) -> None:
        writer = StatisticalConfidenceWriter(output_dir=tmp_path)
        writer.write_report(report)
        with pytest.raises(Exception):
            writer.write_report(report)  # no overwrite=True

    def test_overwrite_ok(self, report: ExperimentConfidenceReport, tmp_path) -> None:
        writer = StatisticalConfidenceWriter(output_dir=tmp_path)
        writer.write_report(report, overwrite=False)
        # Second write succeeds with explicit overwrite
        writer.write_report(report, overwrite=True)

    def test_write_all(self, report: ExperimentConfidenceReport, tmp_path) -> None:
        writer = StatisticalConfidenceWriter(output_dir=tmp_path)
        paths = writer.write_all(report)
        assert len(paths) == 6
        for key, path in paths.items():
            assert path.exists(), f"{key} not written"

    def test_forbidden_data_path(self, report: ExperimentConfidenceReport, tmp_path) -> None:
        writer = StatisticalConfidenceWriter(output_dir=tmp_path)
        forbidden = tmp_path / "data" / "output"
        forbidden.mkdir(parents=True)
        writer2 = StatisticalConfidenceWriter(output_dir=forbidden)
        with pytest.raises(Exception):
            writer2.write_report(report)

    def test_forbidden_reports_path(self, report: ExperimentConfidenceReport, tmp_path) -> None:
        forbidden = tmp_path / "reports" / "output"
        forbidden.mkdir(parents=True)
        writer = StatisticalConfidenceWriter(output_dir=forbidden)
        with pytest.raises(Exception):
            writer.write_report(report)


class TestConvenienceFunctions:
    def test_write_experiment_confidence_report(self, report, tmp_path) -> None:
        paths = write_experiment_confidence_report(report, output_dir=tmp_path)
        assert len(paths) == 2
        assert paths[0].exists()
        assert paths[1].exists()

    def test_write_all_artifacts(self, report, tmp_path) -> None:
        paths = write_all_statistical_confidence_artifacts(report, output_dir=tmp_path)
        assert len(paths) == 6
        assert paths["config"].exists()
        assert paths["metric_results"].exists()
        assert paths["regime_results"].exists()
        assert paths["report"].exists()
        assert paths["manifest"].exists()
        assert paths["markdown"].exists()

    def test_mandatory_output_dir_on_convenience(self, report) -> None:
        with pytest.raises(Exception):
            write_experiment_confidence_report(report)

    def test_json_deterministic(self, report, tmp_path) -> None:
        writer = StatisticalConfidenceWriter(output_dir=tmp_path)
        path = writer.write_report(report, overwrite=False)
        text1 = path.read_text()
        # Clean up and write again with overwrite
        path.unlink()
        path2 = writer.write_report(report)
        text2 = path2.read_text()
        assert text1 == text2
