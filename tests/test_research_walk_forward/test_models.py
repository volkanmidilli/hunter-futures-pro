"""Tests for walk-forward models and safety contracts (MVP-66 Stage 1)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from hunter.research_walk_forward.models import (
    SPEC_VERSION,
    UNAVAILABLE,
    WALK_FORWARD_VERSION,
    ConsistencyState,
    ExperimentExecutionPolicy,
    MarketRegimeLabel,
    MetricAggregate,
    MetricDirection,
    RegimeAggregate,
    WalkForwardCommonConfig,
    WalkForwardError,
    WalkForwardExperimentPlan,
    WalkForwardExperimentReport,
    WalkForwardManifest,
    WalkForwardSafetyFlags,
    WalkForwardWindow,
    WalkForwardWindowResult,
    WindowStatus,
)


class TestVersionConstants:
    def test_version_constants(self) -> None:
        assert WALK_FORWARD_VERSION == "0.66.0-dev"
        assert SPEC_VERSION == "SPEC-067"
        assert UNAVAILABLE == "UNAVAILABLE"


class TestWalkForwardSafetyFlags:
    def test_defaults(self) -> None:
        flags = WalkForwardSafetyFlags()
        assert flags.research_only is True
        assert flags.execution_approval_granted is False
        assert flags.production_approval_granted is False
        assert flags.live_trading_allowed is False
        assert flags.automatic_execution_allowed is False
        assert flags.human_approval_required is True
        assert flags.no_parallel_execution is True
        assert flags.no_direct_subprocess is True

    def test_research_only_mutation_rejected(self) -> None:
        with pytest.raises(ValueError):
            WalkForwardSafetyFlags(research_only=False)

    def test_human_approval_required_mutation_rejected(self) -> None:
        with pytest.raises(ValueError):
            WalkForwardSafetyFlags(human_approval_required=False)

    def test_no_parallel_execution_mutation_rejected(self) -> None:
        with pytest.raises(ValueError):
            WalkForwardSafetyFlags(no_parallel_execution=False)

    def test_no_direct_subprocess_mutation_rejected(self) -> None:
        with pytest.raises(ValueError):
            WalkForwardSafetyFlags(no_direct_subprocess=False)

    def test_non_bool_rejected(self) -> None:
        with pytest.raises(ValueError):
            WalkForwardSafetyFlags(research_only="yes")


class TestWalkForwardCommonConfig:
    def _make_config(self, tmp_path: Path) -> WalkForwardCommonConfig:
        return WalkForwardCommonConfig(
            strategy_name="TestStrategy",
            strategy_path=tmp_path / "strategy.py",
            data_path=tmp_path / "data",
            timeframe="1h",
            balance=Decimal("1000"),
            stake=Decimal("100"),
            max_open_trades=3,
            fee=Decimal("0.001"),
            executable_path=tmp_path / "freqtrade",
            timeout_seconds=60,
        )

    def test_valid_config(self, tmp_path: Path) -> None:
        config = self._make_config(tmp_path)
        assert config.strategy_name == "TestStrategy"
        assert config.balance == Decimal("1000")
        assert config.stake == Decimal("100")
        assert config.max_open_trades == 3
        assert isinstance(config.strategy_path, Path)

    def test_negative_balance_rejected(self, tmp_path: Path) -> None:
        from dataclasses import replace

        config = self._make_config(tmp_path)
        with pytest.raises(ValueError):
            replace(config, balance=Decimal("-1"))

    def test_zero_stake_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            WalkForwardCommonConfig(
                strategy_name="TestStrategy",
                strategy_path=tmp_path / "strategy.py",
                data_path=tmp_path / "data",
                timeframe="1h",
                balance=Decimal("1000"),
                stake=Decimal("0"),
                max_open_trades=3,
                fee=Decimal("0.001"),
                executable_path=tmp_path / "freqtrade",
            )

    def test_max_open_trades_zero_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            WalkForwardCommonConfig(
                strategy_name="TestStrategy",
                strategy_path=tmp_path / "strategy.py",
                data_path=tmp_path / "data",
                timeframe="1h",
                balance=Decimal("1000"),
                stake=Decimal("100"),
                max_open_trades=0,
                fee=Decimal("0.001"),
                executable_path=tmp_path / "freqtrade",
            )


class TestWalkForwardWindow:
    def test_valid(self) -> None:
        window = WalkForwardWindow(
            selection_start="20240101",
            selection_end="20240201",
            evaluation_start="20240301",
            evaluation_end="20240401",
            regime_label=MarketRegimeLabel.BULL,
        )
        assert window.selection_start == "20240101"
        assert window.regime_label == MarketRegimeLabel.BULL

    def test_default_regime_unknown(self) -> None:
        window = WalkForwardWindow(
            selection_start="20240101",
            selection_end="20240201",
            evaluation_start="20240301",
            evaluation_end="20240401",
        )
        assert window.regime_label == MarketRegimeLabel.UNKNOWN

    def test_empty_boundary_rejected(self) -> None:
        with pytest.raises(ValueError):
            WalkForwardWindow(
                selection_start="",
                selection_end="20240201",
                evaluation_start="20240301",
                evaluation_end="20240401",
            )

    def test_invalid_regime_label_rejected(self) -> None:
        with pytest.raises(ValueError):
            WalkForwardWindow(
                selection_start="20240101",
                selection_end="20240201",
                evaluation_start="20240301",
                evaluation_end="20240401",
                regime_label="BULL",
            )


class TestWalkForwardWindowResult:
    def _make_result(self) -> WalkForwardWindowResult:
        window = WalkForwardWindow(
            selection_start="20240101",
            selection_end="20240201",
            evaluation_start="20240301",
            evaluation_end="20240401",
        )
        return WalkForwardWindowResult(
            window=window,
            window_index=0,
            status=WindowStatus.COMPLETED,
            candidate_metrics={"total_return_pct": Decimal("10")},
            baseline_metrics={"total_return_pct": Decimal("5")},
            metric_deltas={"total_return_pct": Decimal("5")},
            metric_directions={"total_return_pct": MetricDirection.CANDIDATE_HIGHER},
            comparison_fingerprint="fp-comp",
            candidate_fingerprint="fp-cand",
            baseline_fingerprint="fp-base",
            fingerprint="fp-result",
        )

    def test_valid(self) -> None:
        result = self._make_result()
        assert result.status == WindowStatus.COMPLETED
        assert result.window_index == 0

    def test_negative_window_index_rejected(self) -> None:
        result = self._make_result()
        with pytest.raises(ValueError):
            WalkForwardWindowResult(
                window=result.window,
                window_index=-1,
                status=result.status,
                candidate_metrics=result.candidate_metrics,
                baseline_metrics=result.baseline_metrics,
                metric_deltas=result.metric_deltas,
                metric_directions=result.metric_directions,
                comparison_fingerprint=result.comparison_fingerprint,
                candidate_fingerprint=result.candidate_fingerprint,
                baseline_fingerprint=result.baseline_fingerprint,
                fingerprint=result.fingerprint,
            )


class TestMetricAggregate:
    def test_valid(self) -> None:
        agg = MetricAggregate(
            metric_name="total_return_pct",
            available_count=2,
            unavailable_count=0,
            candidate_higher_count=2,
            baseline_higher_count=0,
            equal_count=0,
            mean=Decimal("5"),
            median=Decimal("5"),
            min=Decimal("5"),
            max=Decimal("5"),
            q1=Decimal("5"),
            q3=Decimal("5"),
            iqr=Decimal("0"),
            positive_delta_share=Decimal("1"),
            negative_delta_share=Decimal("0"),
            zero_delta_share=Decimal("0"),
            consistency_state=ConsistencyState.CONSISTENT_CANDIDATE_HIGHER,
        )
        assert agg.consistency_state == ConsistencyState.CONSISTENT_CANDIDATE_HIGHER

    def test_negative_count_rejected(self) -> None:
        with pytest.raises(ValueError):
            MetricAggregate(
                metric_name="total_return_pct",
                available_count=-1,
                unavailable_count=0,
                candidate_higher_count=0,
                baseline_higher_count=0,
                equal_count=0,
                mean=None,
                median=None,
                min=None,
                max=None,
                q1=None,
                q3=None,
                iqr=None,
                positive_delta_share=Decimal("0"),
                negative_delta_share=Decimal("0"),
                zero_delta_share=Decimal("0"),
                consistency_state=ConsistencyState.EQUAL_OR_UNAVAILABLE,
            )


class TestRegimeAggregate:
    def test_valid(self) -> None:
        agg = RegimeAggregate(
            regime_label=MarketRegimeLabel.BULL,
            window_count=1,
            completed_count=1,
            failed_count=0,
            blocked_count=0,
            timed_out_count=0,
            unsupported_count=0,
            insufficient_count=0,
            metric_aggregates={},
            fingerprint="fp-regime",
        )
        assert agg.regime_label == MarketRegimeLabel.BULL


class TestWalkForwardManifest:
    def test_valid(self, tmp_path: Path) -> None:
        from datetime import datetime, timezone

        manifest = WalkForwardManifest(
            version="0.66.0-dev",
            spec_version="SPEC-067",
            walk_forward_version="0.66.0-dev",
            generated_at=datetime.now(timezone.utc),
            plan_fingerprint="fp-plan",
            overall_aggregate_fingerprint="fp-agg",
            regime_aggregate_fingerprint="fp-regime",
            safety_flags=WalkForwardSafetyFlags(),
            reason_codes=(),
        )
        assert manifest.spec_version == "SPEC-067"


class TestWalkForwardExperimentReport:
    def test_valid(self, tmp_path: Path) -> None:
        from datetime import datetime, timezone
        from hunter.research_walk_forward.models import WalkForwardMode

        common = WalkForwardCommonConfig(
            strategy_name="TestStrategy",
            strategy_path=tmp_path / "strategy.py",
            data_path=tmp_path / "data",
            timeframe="1h",
            balance=Decimal("1000"),
            stake=Decimal("100"),
            max_open_trades=3,
            fee=Decimal("0.001"),
            executable_path=tmp_path / "freqtrade",
        )
        window = WalkForwardWindow(
            selection_start="20240101",
            selection_end="20240201",
            evaluation_start="20240301",
            evaluation_end="20240401",
        )
        plan = WalkForwardExperimentPlan(
            mode=WalkForwardMode.ROLLING,
            windows=(window,),
            common=common,
        )
        result = WalkForwardWindowResult(
            window=window,
            window_index=0,
            status=WindowStatus.COMPLETED,
            candidate_metrics={},
            baseline_metrics={},
            metric_deltas={},
            metric_directions={},
            comparison_fingerprint="fp",
            candidate_fingerprint="fp",
            baseline_fingerprint="fp",
            fingerprint="fp",
        )
        manifest = WalkForwardManifest(
            version="0.66.0-dev",
            spec_version="SPEC-067",
            walk_forward_version="0.66.0-dev",
            generated_at=datetime.now(timezone.utc),
            plan_fingerprint="fp",
            overall_aggregate_fingerprint="fp",
            regime_aggregate_fingerprint="fp",
            safety_flags=WalkForwardSafetyFlags(),
            reason_codes=(),
        )
        report = WalkForwardExperimentReport(
            version="0.66.0-dev",
            spec_version="SPEC-067",
            walk_forward_version="0.66.0-dev",
            plan=plan,
            window_results=(result,),
            metric_aggregates={},
            regime_aggregates=(),
            manifest=manifest,
            safety_flags=WalkForwardSafetyFlags(),
            fingerprint="fp",
        )
        assert report.research_only is True
        assert report.human_approval_required is True


class TestWalkForwardError:
    def test_reason_code(self) -> None:
        err = WalkForwardError("boom", reason_code="X")
        assert err.reason_code == "X"
