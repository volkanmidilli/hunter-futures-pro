"""Tests for the statistical confidence engine (MVP-67)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

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
        candidate_metrics={"total_return_pct": delta or Decimal("0")},
        baseline_metrics={"total_return_pct": Decimal("0")},
        metric_deltas={"total_return_pct": delta},
        metric_directions={"total_return_pct": MetricDirection.CANDIDATE_HIGHER if delta and delta > 0 else MetricDirection.BASELINE_HIGHER if delta and delta < 0 else MetricDirection.EQUAL},
        comparison_fingerprint=f"cmp-{index}",
        candidate_fingerprint=f"c-{index}",
        baseline_fingerprint=f"b-{index}",
        fingerprint=f"w-{index}",
    )


def _make_report(
    windows: tuple[WalkForwardWindowResult, ...],
) -> WalkForwardExperimentReport:
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
        window_results=windows,
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


class TestRunStatisticalConfidence:
    def test_full_pipeline(self) -> None:
        windows = (
            _make_window_result(0, delta=Decimal("1")),
            _make_window_result(1, delta=Decimal("2")),
            _make_window_result(2, delta=Decimal("3")),
            _make_window_result(3, delta=Decimal("4")),
            _make_window_result(4, delta=Decimal("5")),
        )
        report = _make_report(windows)
        config = _make_config()
        result = run_statistical_confidence(report, config)
        assert result.version == "0.67.0-dev"
        assert result.source_report_fingerprint == "report-fp"
        assert result.human_approval_required is True
        assert result.research_only is True
        assert result.fingerprint != "placeholder"
        assert len(result.fingerprint) == 64
        assert "total_return_pct" in result.metric_results
        mr = result.metric_results["total_return_pct"]
        assert mr.available_count == 5
        assert mr.mean == Decimal("3")
        assert mr.confidence_state == ConfidenceState.ROBUST_CANDIDATE

    def test_validation_error(self) -> None:
        windows = ()
        report = _make_report(windows)
        config = _make_config()
        with pytest.raises(Exception):
            run_statistical_confidence(report, config)

    def test_safety_flags_in_report(self) -> None:
        windows = (
            _make_window_result(0, delta=Decimal("1")),
            _make_window_result(1, delta=Decimal("2")),
            _make_window_result(2, delta=Decimal("3")),
            _make_window_result(3, delta=Decimal("4")),
            _make_window_result(4, delta=Decimal("5")),
        )
        report = _make_report(windows)
        config = _make_config()
        result = run_statistical_confidence(report, config)
        assert result.safety_flags.live_trading_allowed is False
        assert result.safety_flags.research_only is True
        assert result.safety_flags.human_approval_required is True
        assert result.safety_flags.no_direct_subprocess is True
        assert result.safety_flags.no_network_connection is True
        assert result.safety_flags.no_database_connection is True
        assert result.safety_flags.no_exchange_connection is True

    def test_regime_results(self) -> None:
        windows = (
            _make_window_result(0, regime=MarketRegimeLabel.BULL, delta=Decimal("1")),
            _make_window_result(1, regime=MarketRegimeLabel.BULL, delta=Decimal("2")),
            _make_window_result(2, regime=MarketRegimeLabel.BEAR, delta=Decimal("-1")),
        )
        report = _make_report(windows)
        config = _make_config()
        result = run_statistical_confidence(report, config)
        assert MarketRegimeLabel.BULL.value in result.regime_results
        assert MarketRegimeLabel.BEAR.value in result.regime_results

    def test_fingerprint_deterministic(self) -> None:
        """Same inputs produce the same fingerprint."""
        windows = (
            _make_window_result(0, delta=Decimal("1")),
            _make_window_result(1, delta=Decimal("2")),
            _make_window_result(2, delta=Decimal("3")),
            _make_window_result(3, delta=Decimal("4")),
            _make_window_result(4, delta=Decimal("5")),
        )
        report = _make_report(windows)
        config = _make_config()
        result1 = run_statistical_confidence(report, config)
        result2 = run_statistical_confidence(report, config)
        assert result1.fingerprint == result2.fingerprint
