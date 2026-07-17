"""Tests for walk-forward plan builders (MVP-66 Stage 2)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from hunter.research_walk_forward.models import (
    MarketRegimeLabel,
    WalkForwardCommonConfig,
    WalkForwardMode,
)
from hunter.research_walk_forward.planner import (
    build_rolling_plan,
    build_expanding_plan,
    build_explicit_plan,
)


def _make_common(tmp_path: Path) -> WalkForwardCommonConfig:
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


class TestRollingPlanner:
    def test_rolling_plan(self, tmp_path: Path) -> None:
        common = _make_common(tmp_path)
        plan = build_rolling_plan(
            common,
            selection_start="20240101",
            selection_end="20240201",
            evaluation_start="20240301",
            evaluation_end="20240401",
            step_days=31,
            count=3,
            contiguous=True,
        )
        assert plan.mode == WalkForwardMode.ROLLING
        assert len(plan.windows) == 3
        assert plan.windows[0].selection_start == "20240101"
        assert plan.windows[1].selection_start == "20240201"
        assert plan.contiguous is True

    def test_rolling_duration_constant(self, tmp_path: Path) -> None:
        common = _make_common(tmp_path)
        plan = build_rolling_plan(
            common,
            selection_start="20240101",
            selection_end="20240201",
            evaluation_start="20240301",
            evaluation_end="20240401",
            step_days=31,
            count=3,
        )
        for window in plan.windows:
            from datetime import datetime
            fmt = "%Y%m%d"
            sel_duration = (datetime.strptime(window.selection_end, fmt) - datetime.strptime(window.selection_start, fmt)).days
            eval_duration = (datetime.strptime(window.evaluation_end, fmt) - datetime.strptime(window.evaluation_start, fmt)).days
            assert sel_duration == 31
            assert eval_duration == 31

    def test_rolling_contiguous_evaluations(self, tmp_path: Path) -> None:
        common = _make_common(tmp_path)
        plan = build_rolling_plan(
            common,
            selection_start="20240101",
            selection_end="20240201",
            evaluation_start="20240301",
            evaluation_end="20240401",
            step_days=31,
            count=3,
            contiguous=True,
        )
        for i in range(1, len(plan.windows)):
            assert plan.windows[i].evaluation_start == plan.windows[i - 1].evaluation_end


class TestExpandingPlanner:
    def test_expanding_plan(self, tmp_path: Path) -> None:
        common = _make_common(tmp_path)
        plan = build_expanding_plan(
            common,
            selection_start="20240101",
            selection_end="20240201",
            evaluation_start="20240701",
            evaluation_end="20240801",
            step_days=31,
            count=3,
            contiguous=True,
        )
        assert plan.mode == WalkForwardMode.EXPANDING
        assert len(plan.windows) == 3
        assert all(w.selection_start == "20240101" for w in plan.windows)
        assert plan.windows[2].selection_end > plan.windows[0].selection_end

    def test_expanding_start_constant(self, tmp_path: Path) -> None:
        common = _make_common(tmp_path)
        plan = build_expanding_plan(
            common,
            selection_start="20240101",
            selection_end="20240201",
            evaluation_start="20240701",
            evaluation_end="20240801",
            step_days=31,
            count=3,
        )
        for window in plan.windows:
            assert window.selection_start == "20240101"


class TestExplicitPlanner:
    def test_explicit_plan(self, tmp_path: Path) -> None:
        common = _make_common(tmp_path)
        from hunter.research_walk_forward.models import WalkForwardWindow

        windows = [
            WalkForwardWindow(
                selection_start="20240101",
                selection_end="20240201",
                evaluation_start="20240301",
                evaluation_end="20240401",
            ),
            WalkForwardWindow(
                selection_start="20240501",
                selection_end="20240601",
                evaluation_start="20240701",
                evaluation_end="20240801",
            ),
        ]
        plan = build_explicit_plan(
            common, windows, mode=WalkForwardMode.ROLLING, contiguous=False
        )
        assert len(plan.windows) == 2
        assert plan.contiguous is False

    def test_explicit_duplicate_rejected(self, tmp_path: Path) -> None:
        common = _make_common(tmp_path)
        from hunter.research_walk_forward.models import WalkForwardWindow
        from hunter.research_walk_forward.validator import validate_plan
        from hunter.research_walk_forward.models import WalkForwardValidationError

        windows = [
            WalkForwardWindow(
                selection_start="20240101",
                selection_end="20240201",
                evaluation_start="20240301",
                evaluation_end="20240401",
            ),
            WalkForwardWindow(
                selection_start="20240101",
                selection_end="20240201",
                evaluation_start="20240301",
                evaluation_end="20240401",
            ),
        ]
        plan = build_explicit_plan(common, windows)
        with pytest.raises(WalkForwardValidationError):
            validate_plan(plan)


class TestPlannerRegimeLabels:
    def test_rolling_regime_labels(self, tmp_path: Path) -> None:
        common = _make_common(tmp_path)
        plan = build_rolling_plan(
            common,
            selection_start="20240101",
            selection_end="20240201",
            evaluation_start="20240301",
            evaluation_end="20240401",
            step_days=31,
            count=2,
            regime_labels=[MarketRegimeLabel.BULL, MarketRegimeLabel.BEAR],
        )
        assert plan.windows[0].regime_label == MarketRegimeLabel.BULL
        assert plan.windows[1].regime_label == MarketRegimeLabel.BEAR

    def test_unknown_default_label(self, tmp_path: Path) -> None:
        common = _make_common(tmp_path)
        plan = build_rolling_plan(
            common,
            selection_start="20240101",
            selection_end="20240201",
            evaluation_start="20240301",
            evaluation_end="20240401",
            step_days=31,
            count=1,
        )
        assert plan.windows[0].regime_label == MarketRegimeLabel.UNKNOWN

    def test_short_regime_labels_default_unknown(self, tmp_path: Path) -> None:
        common = _make_common(tmp_path)
        plan = build_rolling_plan(
            common,
            selection_start="20240101",
            selection_end="20240201",
            evaluation_start="20240301",
            evaluation_end="20240401",
            step_days=31,
            count=2,
            regime_labels=[MarketRegimeLabel.BULL],
        )
        assert plan.windows[0].regime_label == MarketRegimeLabel.BULL
        assert plan.windows[1].regime_label == MarketRegimeLabel.UNKNOWN
