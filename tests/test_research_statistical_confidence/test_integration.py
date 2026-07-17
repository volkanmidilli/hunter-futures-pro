"""Integration tests for the statistical confidence pipeline (MVP-67)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from hunter.research_statistical_confidence.engine import (
    run_statistical_confidence,
)
from hunter.research_statistical_confidence.models import (
    BootstrapConfig,
    ConfidenceState,
    RobustnessCriteria,
    StatisticalConfidenceConfig,
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


def _make_fake_mvp66_report() -> WalkForwardExperimentReport:
    """Build a minimal fake MVP-66 report with multiple metrics and regimes."""
    windows_data = [
        # (index, regime, profit_delta, sharpe_delta, winrate_delta)
        (0, MarketRegimeLabel.BULL, Decimal("5.0"), Decimal("0.3"), Decimal("0.05")),
        (1, MarketRegimeLabel.BULL, Decimal("4.5"), Decimal("0.25"), Decimal("0.04")),
        (2, MarketRegimeLabel.BULL, Decimal("6.0"), Decimal("0.35"), Decimal("0.06")),
        (3, MarketRegimeLabel.BULL, Decimal("5.5"), Decimal("0.4"), Decimal("0.03")),
        (4, MarketRegimeLabel.BEAR, Decimal("2.0"), Decimal("0.1"), Decimal("0.01")),
        (5, MarketRegimeLabel.BEAR, Decimal("1.5"), Decimal("0.05"), Decimal("0.00")),
        (6, MarketRegimeLabel.BEAR, Decimal("-1.0"), Decimal("-0.1"), Decimal("-0.02")),
        (7, MarketRegimeLabel.UNKNOWN, Decimal("3.0"), Decimal("0.15"), Decimal("0.02")),
    ]

    windows = []
    for idx, regime, profit, sharpe, winrate in windows_data:
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
            candidate_metrics={
                "total_return_pct": profit + Decimal("1"),
                "sharpe_ratio": sharpe + Decimal("0.1"),
                "win_rate_pct": winrate + Decimal("0.01"),
            },
            baseline_metrics={
                "total_return_pct": Decimal("1"),
                "sharpe_ratio": Decimal("0.1"),
                "win_rate_pct": Decimal("0.01"),
            },
            metric_deltas={
                "total_return_pct": profit,
                "sharpe_ratio": sharpe,
                "win_rate_pct": winrate,
            },
            metric_directions={
                "total_return_pct": MetricDirection.CANDIDATE_HIGHER,
                "sharpe_ratio": MetricDirection.CANDIDATE_HIGHER,
                "win_rate_pct": MetricDirection.CANDIDATE_HIGHER,
            },
            comparison_fingerprint=f"cmp-{idx}",
            candidate_fingerprint=f"c-{idx}",
            baseline_fingerprint=f"b-{idx}",
            fingerprint=f"w-{idx}",
        )
        windows.append(w_result)

    common = WalkForwardCommonConfig(
        strategy_name="TestStrategy",
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


class TestIntegration:
    def test_end_to_end(self) -> None:
        report = _make_fake_mvp66_report()
        config = StatisticalConfidenceConfig(
            minimum_available_window_count=3,
            confidence_level=Decimal("0.95"),
            bootstrap=BootstrapConfig(seed=42, iterations=500),
            robustness=RobustnessCriteria(
                sign_share_threshold=Decimal("0.8"),
                maximum_influence_ratio=Decimal("0.3"),
                confidence_level=Decimal("0.95"),
            ),
        )
        result = run_statistical_confidence(report, config)
        assert result is not None
        assert result.fingerprint is not None
        assert len(result.metric_results) == 3
        assert all(mr.confidence_state is not None for mr in result.metric_results.values())
        assert len(result.regime_results) == 3  # BULL, BEAR, UNKNOWN

    def test_metric_results_all_metrics_present(self) -> None:
        report = _make_fake_mvp66_report()
        config = StatisticalConfidenceConfig(
            minimum_available_window_count=3,
            confidence_level=Decimal("0.95"),
            bootstrap=BootstrapConfig(seed=42, iterations=500),
            robustness=RobustnessCriteria(
                sign_share_threshold=Decimal("0.8"),
                maximum_influence_ratio=Decimal("0.3"),
                confidence_level=Decimal("0.95"),
            ),
        )
        result = run_statistical_confidence(report, config)
        assert "total_return_pct" in result.metric_results
        assert "sharpe_ratio" in result.metric_results
        assert "win_rate_pct" in result.metric_results

    def test_regime_coverage(self) -> None:
        report = _make_fake_mvp66_report()
        config = StatisticalConfidenceConfig(
            minimum_available_window_count=2,
            confidence_level=Decimal("0.95"),
            bootstrap=BootstrapConfig(seed=42, iterations=500),
            robustness=RobustnessCriteria(
                sign_share_threshold=Decimal("0.8"),
                maximum_influence_ratio=Decimal("0.3"),
                confidence_level=Decimal("0.95"),
            ),
        )
        result = run_statistical_confidence(report, config)
        assert MarketRegimeLabel.BULL.value in result.regime_results
        assert MarketRegimeLabel.BEAR.value in result.regime_results
        assert MarketRegimeLabel.UNKNOWN.value in result.regime_results
        bull = result.regime_results[MarketRegimeLabel.BULL.value]
        assert bull.available_count == 4

    def test_with_unavailable_metrics(self) -> None:
        """Test that None metric_deltas are handled."""
        windows = []
        for idx in range(5):
            win = WalkForwardWindow(
                selection_start="20240101",
                selection_end="20240201",
                evaluation_start="20240201",
                evaluation_end="20240301",
                regime_label=MarketRegimeLabel.UNKNOWN,
            )
            delta = Decimal(str(idx + 1)) if idx < 4 else None
            w_result = WalkForwardWindowResult(
                window=win,
                window_index=idx,
                status=WindowStatus.COMPLETED,
                candidate_metrics={"total_return_pct": delta or Decimal("0")},
                baseline_metrics={"total_return_pct": Decimal("0")},
                metric_deltas={"total_return_pct": delta},
                metric_directions={"total_return_pct": MetricDirection.CANDIDATE_HIGHER if delta and delta > 0 else MetricDirection.EQUAL},
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
        report = WalkForwardExperimentReport(
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

        config = StatisticalConfidenceConfig(
            minimum_available_window_count=3,
            confidence_level=Decimal("0.95"),
            bootstrap=BootstrapConfig(seed=42, iterations=500),
            robustness=RobustnessCriteria(
                sign_share_threshold=Decimal("0.8"),
                maximum_influence_ratio=Decimal("0.3"),
                confidence_level=Decimal("0.95"),
            ),
        )
        result = run_statistical_confidence(report, config)
        mr = result.metric_results["total_return_pct"]
        assert mr.available_count == 4
        assert mr.unavailable_count == 1
        assert mr.mean is not None
