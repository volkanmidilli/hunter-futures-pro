"""Tests for the regime stratification module (MVP-67)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from hunter.research_statistical_confidence.models import (
    BootstrapConfig,
    ConfidenceState,
    RobustnessCriteria,
    StatisticalConfidenceConfig,
)
from hunter.research_statistical_confidence.regime import (
    _status_counts,
    compute_regime_metric_results,
    compute_regime_results,
)
from hunter.research_walk_forward.models import (
    WalkForwardMode,
    MarketRegimeLabel,
    MetricDirection,
    WalkForwardCommonConfig,
    WalkForwardExperimentPlan,
    WalkForwardExperimentReport,
    WalkForwardManifest,
    WalkForwardSafetyFlags,
    WalkForwardWindow,
    WalkForwardWindowResult,
    WindowStatus,
)


def _make_window_result(
    index: int,
    regime: MarketRegimeLabel = MarketRegimeLabel.UNKNOWN,
    delta: Decimal | None = Decimal("1"),
    status: WindowStatus = WindowStatus.COMPLETED,
) -> WalkForwardWindowResult:
    window = WalkForwardWindow(
        selection_start="20240101",
        selection_end="20240201",
        evaluation_start="20240201",
        evaluation_end="20240301",
        regime_label=regime,
    )
    return WalkForwardWindowResult(
        window=window,
        window_index=index,
        status=status,
        candidate_metrics={"total_return_pct": delta},
        baseline_metrics={"total_return_pct": Decimal("0")},
        metric_deltas={"total_return_pct": delta},
        metric_directions={"total_return_pct": MetricDirection.CANDIDATE_HIGHER if delta and delta > 0 else MetricDirection.BASELINE_HIGHER},
        comparison_fingerprint=f"cmp-{index}",
        candidate_fingerprint=f"c-{index}",
        baseline_fingerprint=f"b-{index}",
        fingerprint=f"w-{index}",
    )


def _make_config() -> StatisticalConfidenceConfig:
    return StatisticalConfidenceConfig(
        minimum_available_window_count=2,
        confidence_level=Decimal("0.95"),
        bootstrap=BootstrapConfig(seed=42, iterations=500),
        robustness=RobustnessCriteria(
            sign_share_threshold=Decimal("0.8"),
            maximum_influence_ratio=Decimal("0.3"),
            confidence_level=Decimal("0.95"),
        ),
    )


class TestStatusCounts:
    def test_basic(self) -> None:
        windows = (
            _make_window_result(0, status=WindowStatus.COMPLETED),
            _make_window_result(1, status=WindowStatus.FAILED),
            _make_window_result(2, status=WindowStatus.COMPLETED),
        )
        counts = _status_counts(windows)
        assert counts[WindowStatus.COMPLETED.value] == 2
        assert counts[WindowStatus.FAILED.value] == 1


class TestComputeRegimeMetricResults:
    def test_single_metric(self) -> None:
        windows = (
            _make_window_result(0, delta=Decimal("1")),
            _make_window_result(1, delta=Decimal("2")),
            _make_window_result(2, delta=Decimal("3")),
        )
        config = _make_config()
        result = compute_regime_metric_results(windows, "total_return_pct", config)
        assert result.metric_name == "total_return_pct"
        assert result.available_count == 3
        assert result.mean == Decimal("2")
        assert result.positive_share == Decimal("1")
        assert result.confidence_state == ConfidenceState.ROBUST_CANDIDATE

    def test_with_nones(self) -> None:
        windows = (
            _make_window_result(0, delta=Decimal("1")),
            _make_window_result(1, delta=None),
            _make_window_result(2, delta=Decimal("2")),
        )
        config = _make_config()
        result = compute_regime_metric_results(windows, "total_return_pct", config)
        assert result.available_count == 2
        assert result.unavailable_count == 1


class TestComputeRegimeResults:
    def test_single_regime(self) -> None:
        report = _make_report_with_windows([
            (0, MarketRegimeLabel.BULL, Decimal("1")),
            (1, MarketRegimeLabel.BULL, Decimal("2")),
            (2, MarketRegimeLabel.BULL, Decimal("3")),
        ])
        config = _make_config()
        results = compute_regime_results(report, config)
        assert MarketRegimeLabel.BULL.value in results
        rr = results[MarketRegimeLabel.BULL.value]
        assert rr.regime_label == MarketRegimeLabel.BULL
        assert rr.available_count > 0

    def test_multiple_regimes(self) -> None:
        report = _make_report_with_windows([
            (0, MarketRegimeLabel.BULL, Decimal("1")),
            (1, MarketRegimeLabel.BEAR, Decimal("-1")),
            (2, MarketRegimeLabel.BULL, Decimal("2")),
        ])
        config = _make_config()
        results = compute_regime_results(report, config)
        assert MarketRegimeLabel.BULL.value in results
        assert MarketRegimeLabel.BEAR.value in results

    def test_unknown_regime_default(self) -> None:
        report = _make_report_with_windows([
            (0, MarketRegimeLabel.UNKNOWN, Decimal("1")),
            (1, MarketRegimeLabel.UNKNOWN, Decimal("2")),
        ])
        config = _make_config()
        results = compute_regime_results(report, config)
        assert MarketRegimeLabel.UNKNOWN.value in results


def _make_report_with_windows(
    specs: list[tuple[int, MarketRegimeLabel, Decimal | None]],
) -> WalkForwardExperimentReport:
    windows = []
    for idx, regime, delta in specs:
        windows.append(_make_window_result(idx, regime, delta))
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
