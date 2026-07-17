"""Determinism tests for the statistical confidence package (MVP-67)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from hunter.research_statistical_confidence.engine import (
    run_statistical_confidence,
)
from hunter.research_statistical_confidence.fingerprint import (
    config_fingerprint,
    metric_results_fingerprint,
    regime_results_fingerprint,
    report_fingerprint,
)
from hunter.research_statistical_confidence.models import (
    BootstrapConfig,
    RobustnessCriteria,
    StatisticalConfidenceConfig,
)
from hunter.research_statistical_confidence.writer import (
    StatisticalConfidenceWriter,
    write_all_statistical_confidence_artifacts,
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


def _make_report() -> WalkForwardExperimentReport:
    """Build a deterministic test report."""
    windows_data = [
        (0, MarketRegimeLabel.BULL, Decimal("1.0")),
        (1, MarketRegimeLabel.BULL, Decimal("2.0")),
        (2, MarketRegimeLabel.BULL, Decimal("3.0")),
        (3, MarketRegimeLabel.BEAR, Decimal("-0.5")),
        (4, MarketRegimeLabel.BEAR, Decimal("-1.0")),
    ]
    windows = []
    for idx, regime, delta in windows_data:
        win = WalkForwardWindow(
            selection_start="20240101",
            selection_end="20240201",
            evaluation_start="20240201",
            evaluation_end="20240301",
            regime_label=regime,
        )
        w_result = WalkForwardWindowResult(
            window=win,
            window_index=idx,
            status=WindowStatus.COMPLETED,
            candidate_metrics={"total_return_pct": delta + Decimal("1")},
            baseline_metrics={"total_return_pct": Decimal("1")},
            metric_deltas={"total_return_pct": delta},
            metric_directions={"total_return_pct": MetricDirection.CANDIDATE_HIGHER if delta > 0 else MetricDirection.BASELINE_HIGHER},
            comparison_fingerprint=f"cmp-{idx}",
            candidate_fingerprint=f"c-{idx}",
            baseline_fingerprint=f"b-{idx}",
            fingerprint=f"w-{idx}",
        )
        windows.append(w_result)

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
        windows=tuple(w.window for w in windows),
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
        window_results=tuple(windows),
        metric_aggregates={},
        regime_aggregates=(),
        manifest=manifest,
        safety_flags=WalkForwardSafetyFlags(),
        fingerprint="report-fp",
    )


def _make_config() -> StatisticalConfidenceConfig:
    return StatisticalConfidenceConfig(
        minimum_available_window_count=3,
        confidence_level=Decimal("0.95"),
        bootstrap=BootstrapConfig(seed=42, iterations=500),
        robustness=RobustnessCriteria(
            sign_share_threshold=Decimal("0.8"),
            maximum_influence_ratio=Decimal("0.3"),
            confidence_level=Decimal("0.95"),
        ),
    )


class TestDeterminism:
    def test_same_inputs_same_report_fingerprint(self) -> None:
        report = _make_report()
        config = _make_config()
        result1 = run_statistical_confidence(report, config)
        result2 = run_statistical_confidence(report, config)
        assert result1.fingerprint == result2.fingerprint
        assert result1.source_report_fingerprint == result2.source_report_fingerprint
        assert result1.manifest.overall_fingerprint == result2.manifest.overall_fingerprint

    def test_same_inputs_same_artifacts(self, tmp_path) -> None:
        report = _make_report()
        config = _make_config()
        result1 = run_statistical_confidence(report, config)
        result2 = run_statistical_confidence(report, config)

        out1 = tmp_path / "out1"
        out2 = tmp_path / "out2"
        paths1 = write_all_statistical_confidence_artifacts(result1, output_dir=out1)
        paths2 = write_all_statistical_confidence_artifacts(result2, output_dir=out2)

        for key in ("config", "metric_results", "regime_results", "markdown"):
            text1 = paths1[key].read_text()
            text2 = paths2[key].read_text()
            assert text1 == text2, f"{key} differs between runs"

    def test_different_windows_different_fingerprint(self) -> None:
        report1 = _make_report()
        # Create a slightly different report
        report2_data = [
            (0, MarketRegimeLabel.BULL, Decimal("1.5")),
            (1, MarketRegimeLabel.BULL, Decimal("2.0")),
            (2, MarketRegimeLabel.BULL, Decimal("3.0")),
            (3, MarketRegimeLabel.BEAR, Decimal("-0.5")),
            (4, MarketRegimeLabel.BEAR, Decimal("-1.0")),
        ]
        windows = []
        for idx, regime, delta in report2_data:
            win = WalkForwardWindow(
                selection_start="20240101",
                selection_end="20240201",
                evaluation_start="20240201",
                evaluation_end="20240301",
                regime_label=regime,
            )
            w_result = WalkForwardWindowResult(
                window=win,
                window_index=idx,
                status=WindowStatus.COMPLETED,
                candidate_metrics={"total_return_pct": delta + Decimal("1")},
                baseline_metrics={"total_return_pct": Decimal("1")},
                metric_deltas={"total_return_pct": delta},
                metric_directions={"total_return_pct": MetricDirection.CANDIDATE_HIGHER},
                comparison_fingerprint=f"cmp-{idx}",
                candidate_fingerprint=f"c-{idx}",
                baseline_fingerprint=f"b-{idx}",
                fingerprint=f"w-{idx}",
            )
            windows.append(w_result)

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
            windows=tuple(w.window for w in windows),
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
        report2 = WalkForwardExperimentReport(
            version="0.66.0-dev",
            spec_version="SPEC-067",
            walk_forward_version="0.66.0-dev",
            plan=plan,
            window_results=tuple(windows),
            metric_aggregates={},
            regime_aggregates=(),
            manifest=manifest,
            safety_flags=WalkForwardSafetyFlags(),
            fingerprint="report-fp2",
        )

        config = _make_config()
        result1 = run_statistical_confidence(report1, config)
        result2 = run_statistical_confidence(report2, config)
        assert result1.fingerprint != result2.fingerprint

    def test_fingerprint_functions_deterministic(self) -> None:
        config = _make_config()
        fp1 = config_fingerprint(config)
        fp2 = config_fingerprint(config)
        assert fp1 == fp2
