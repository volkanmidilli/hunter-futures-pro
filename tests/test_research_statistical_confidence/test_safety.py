"""Security and safety tests for the statistical confidence package (MVP-67)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


class TestNoDirectSubprocess:
    def test_no_subprocess_in_package_files(self) -> None:
        package_path = (
            Path(__file__).parent.parent.parent
            / "src"
            / "hunter"
            / "research_statistical_confidence"
        )
        for file_path in sorted(package_path.glob("*.py")):
            if file_path.name == "__init__.py":
                continue
            source = file_path.read_text()
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import) and any(
                    alias.name == "subprocess" for alias in node.names
                ):
                    pytest.fail(f"subprocess imported in {file_path}")
                if (
                    isinstance(node, ast.ImportFrom)
                    and node.module == "subprocess"
                ):
                    pytest.fail(f"subprocess imported from in {file_path}")

    def test_no_subprocess_in_test_files(self) -> None:
        test_path = (
            Path(__file__).parent
        )
        for file_path in sorted(test_path.glob("*.py")):
            if file_path.name == "__init__.py":
                continue
            source = file_path.read_text()
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import) and any(
                    alias.name == "subprocess" for alias in node.names
                ):
                    pytest.fail(f"subprocess imported in {file_path}")
                if (
                    isinstance(node, ast.ImportFrom)
                    and node.module == "subprocess"
                ):
                    pytest.fail(f"subprocess imported from in {file_path}")


class TestNoDataReportsAccess:
    def test_no_data_path_read(self) -> None:
        """Verify package source does not read from data/ directory."""
        package_path = (
            Path(__file__).parent.parent.parent
            / "src"
            / "hunter"
            / "research_statistical_confidence"
        )
        for file_path in sorted(package_path.glob("*.py")):
            source = file_path.read_text()
            # Check for literal 'data/' or 'reports/' path references
            if '"data/"' in source or "'data/'" in source:
                pytest.fail(f"data/ path reference in {file_path}")
            if '"reports/"' in source or "'reports/'" in source:
                # This is OK for writer to reject, not read
                pass

    def test_writer_rejects_data_reports(self) -> None:
        """Test that writer correctly rejects data/ and reports/ paths."""
        from hunter.research_statistical_confidence.writer import (
            StatisticalConfidenceWriter,
        )
        from hunter.research_statistical_confidence.models import (
            ExperimentConfidenceReport,
            StatisticalConfidenceConfig,
            StatisticalConfidenceManifest,
            StatisticalConfidenceSafetyFlags,
            BootstrapConfig,
            RobustnessCriteria,
            MetricConfidenceResult,
            ConfidenceState,
            RegimeConfidenceResult,
        )
        from hunter.research_walk_forward.models import MarketRegimeLabel
        from datetime import datetime, timezone
        from decimal import Decimal

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
        mr = MetricConfidenceResult(
            metric_name="test",
            available_count=1,
            unavailable_count=0,
            mean=Decimal("1"),
            median=Decimal("1"),
            std_dev=None,
            mad=None,
            min=Decimal("1"),
            max=Decimal("1"),
            q1=Decimal("1"),
            q3=Decimal("1"),
            iqr=Decimal("0"),
            positive_share=Decimal("1"),
            negative_share=Decimal("0"),
            zero_share=Decimal("0"),
            bootstrap_mean_ci=None,
            bootstrap_median_ci=None,
            loo=None,
            confidence_state=ConfidenceState.INSUFFICIENT_EVIDENCE,
        )
        rr = RegimeConfidenceResult(
            regime_label=MarketRegimeLabel.UNKNOWN,
            available_count=1,
            metric_results={"test": mr},
            status_counts={"COMPLETED": 1},
            fingerprint="fp",
        )
        manifest = StatisticalConfidenceManifest(
            version="0.67.0-dev",
            spec_version="SPEC-068",
            statistical_confidence_version="0.67.0-dev",
            generated_at=datetime.now(timezone.utc),
            config_fingerprint="cfg",
            metric_results_fingerprint="mr",
            regime_results_fingerprint="rr",
            overall_fingerprint="ov",
            safety_flags=StatisticalConfidenceSafetyFlags(),
        )
        report = ExperimentConfidenceReport(
            version="0.67.0-dev",
            spec_version="SPEC-068",
            statistical_confidence_version="0.67.0-dev",
            source_report_fingerprint="src",
            config=config,
            metric_results={"test": mr},
            regime_results={"UNKNOWN": rr},
            manifest=manifest,
            safety_flags=StatisticalConfidenceSafetyFlags(),
            fingerprint="fp",
        )
        import tempfile
        from pathlib import Path

        # Test data/ rejection
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp) / "data"
            data_dir.mkdir(exist_ok=True)
            writer = StatisticalConfidenceWriter(output_dir=data_dir)
            with pytest.raises(Exception):
                writer.write_report(report)

        # Test reports/ rejection
        with tempfile.TemporaryDirectory() as tmp:
            reports_dir = Path(tmp) / "reports"
            reports_dir.mkdir(exist_ok=True)
            writer = StatisticalConfidenceWriter(output_dir=reports_dir)
            with pytest.raises(Exception):
                writer.write_report(report)


class TestSafetyFlags:
    def test_all_safety_flags_hardcoded(self) -> None:
        from hunter.research_statistical_confidence.models import (
            StatisticalConfidenceSafetyFlags,
        )
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

    def test_safety_flag_mutations_rejected(self) -> None:
        from hunter.research_statistical_confidence.models import (
            StatisticalConfidenceSafetyFlags,
        )
        with pytest.raises(ValueError):
            StatisticalConfidenceSafetyFlags(research_only=False)
        with pytest.raises(ValueError):
            StatisticalConfidenceSafetyFlags(execution_approval_granted=True)
        with pytest.raises(ValueError):
            StatisticalConfidenceSafetyFlags(production_approval_granted=True)
        with pytest.raises(ValueError):
            StatisticalConfidenceSafetyFlags(live_trading_allowed=True)
        with pytest.raises(ValueError):
            StatisticalConfidenceSafetyFlags(automatic_execution_allowed=True)
        with pytest.raises(ValueError):
            StatisticalConfidenceSafetyFlags(human_approval_required=False)
        with pytest.raises(ValueError):
            StatisticalConfidenceSafetyFlags(no_direct_subprocess=False)
        with pytest.raises(ValueError):
            StatisticalConfidenceSafetyFlags(no_parallel_execution=False)
