"""Tests for regime aggregation (MVP-66 Stage 6)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from hunter.research_walk_forward.models import (
    MarketRegimeLabel,
    MetricAggregate,
    WindowStatus,
)
from hunter.research_walk_forward.regime import (
    build_regime_aggregate,
    group_results_by_regime,
)
from hunter.research_walk_forward.aggregation import aggregate_metrics
from tests.test_research_walk_forward.test_aggregation import _make_window


class TestRegimeGrouping:
    def test_group_by_caller_provided_labels(self) -> None:
        windows = (
            _make_window(0, Decimal("10"), Decimal("5"), MarketRegimeLabel.BULL),
            _make_window(1, Decimal("12"), Decimal("6"), MarketRegimeLabel.BULL),
            _make_window(2, Decimal("8"), Decimal("4"), MarketRegimeLabel.BEAR),
        )
        groups = group_results_by_regime(windows)
        assert MarketRegimeLabel.BULL in groups
        assert MarketRegimeLabel.BEAR in groups
        assert len(groups[MarketRegimeLabel.BULL]) == 2
        assert len(groups[MarketRegimeLabel.BEAR]) == 1

    def test_unknown_regime_default(self) -> None:
        windows = (
            _make_window(0, Decimal("10"), Decimal("5")),
        )
        groups = group_results_by_regime(windows)
        assert MarketRegimeLabel.UNKNOWN in groups
        assert len(groups[MarketRegimeLabel.UNKNOWN]) == 1

    def test_deterministic_regime_ordering(self) -> None:
        windows = (
            _make_window(0, Decimal("10"), Decimal("5"), MarketRegimeLabel.BEAR),
            _make_window(1, Decimal("12"), Decimal("6"), MarketRegimeLabel.BULL),
        )
        groups = group_results_by_regime(windows)
        labels = sorted(groups.keys(), key=lambda x: x.value)
        assert labels[0] == MarketRegimeLabel.BEAR
        assert labels[1] == MarketRegimeLabel.BULL


class TestRegimeAggregate:
    def test_preserve_failed_status(self) -> None:
        from hunter.research_walk_forward.models import WalkForwardWindow, WalkForwardWindowResult, MetricDirection

        window = WalkForwardWindow(
            selection_start="20240101",
            selection_end="20240201",
            evaluation_start="20240301",
            evaluation_end="20240401",
            regime_label=MarketRegimeLabel.BULL,
        )
        result = WalkForwardWindowResult(
            window=window,
            window_index=0,
            status=WindowStatus.FAILED,
            candidate_metrics={},
            baseline_metrics={},
            metric_deltas={},
            metric_directions={},
            comparison_fingerprint="fp-comp",
            candidate_fingerprint="fp-cand",
            baseline_fingerprint="fp-base",
            fingerprint="fp-result",
            reason_codes=("WINDOW_FAILED",),
        )
        agg = build_regime_aggregate(MarketRegimeLabel.BULL, (result,), "fp")
        assert agg.failed_count == 1
        assert agg.completed_count == 0
        assert agg.insufficient_count == 0

    def test_preserve_timed_out_status(self) -> None:
        from hunter.research_walk_forward.models import WalkForwardWindow, WalkForwardWindowResult, MetricDirection

        window = WalkForwardWindow(
            selection_start="20240101",
            selection_end="20240201",
            evaluation_start="20240301",
            evaluation_end="20240401",
            regime_label=MarketRegimeLabel.BULL,
        )
        result = WalkForwardWindowResult(
            window=window,
            window_index=0,
            status=WindowStatus.TIMED_OUT,
            candidate_metrics={},
            baseline_metrics={},
            metric_deltas={},
            metric_directions={},
            comparison_fingerprint="fp-comp",
            candidate_fingerprint="fp-cand",
            baseline_fingerprint="fp-base",
            fingerprint="fp-result",
            reason_codes=("TIMEOUT",),
        )
        agg = build_regime_aggregate(MarketRegimeLabel.BULL, (result,), "fp")
        assert agg.timed_out_count == 1

    def test_preserve_insufficient_status(self) -> None:
        from hunter.research_walk_forward.models import WalkForwardWindow, WalkForwardWindowResult, MetricDirection

        window = WalkForwardWindow(
            selection_start="20240101",
            selection_end="20240201",
            evaluation_start="20240301",
            evaluation_end="20240401",
            regime_label=MarketRegimeLabel.BULL,
        )
        result = WalkForwardWindowResult(
            window=window,
            window_index=0,
            status=WindowStatus.INSUFFICIENT,
            candidate_metrics={},
            baseline_metrics={},
            metric_deltas={},
            metric_directions={},
            comparison_fingerprint="fp-comp",
            candidate_fingerprint="fp-cand",
            baseline_fingerprint="fp-base",
            fingerprint="fp-result",
            reason_codes=("INSUFFICIENT_TRADES",),
        )
        agg = build_regime_aggregate(MarketRegimeLabel.BULL, (result,), "fp")
        assert agg.insufficient_count == 1

    def test_regime_metric_aggregates(self) -> None:
        windows = (
            _make_window(0, Decimal("10"), Decimal("5"), MarketRegimeLabel.BULL),
            _make_window(1, Decimal("12"), Decimal("6"), MarketRegimeLabel.BULL),
        )
        agg = build_regime_aggregate(
            MarketRegimeLabel.BULL, windows, "fp"
        )
        assert "total_return_pct" in agg.metric_aggregates
        assert agg.metric_aggregates["total_return_pct"].available_count == 2
