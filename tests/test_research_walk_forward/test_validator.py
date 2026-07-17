"""Tests for walk-forward plan validation (MVP-66 Stage 2)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from hunter.research_walk_forward.models import (
    BACKWARD_WINDOW,
    DUPLICATE_WINDOW,
    EXPANDING_START_DRIFT,
    INVALID_CONTIGUITY,
    OUT_OF_ORDER_WINDOWS,
    ROLLING_DURATION_DRIFT,
    WalkForwardCommonConfig,
    WalkForwardMode,
    WalkForwardValidationError,
    WalkForwardWindow,
)
from hunter.research_walk_forward.planner import build_explicit_plan, build_rolling_plan
from hunter.research_walk_forward.validator import validate_plan, validate_window


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


class TestSingleWindowValidation:
    def test_valid_window(self, tmp_path: Path) -> None:
        window = WalkForwardWindow(
            selection_start="20240101",
            selection_end="20240201",
            evaluation_start="20240301",
            evaluation_end="20240401",
        )
        validate_window(window)

    def test_backward_selection_rejected(self, tmp_path: Path) -> None:
        window = WalkForwardWindow(
            selection_start="20240301",
            selection_end="20240101",
            evaluation_start="20240501",
            evaluation_end="20240601",
        )
        with pytest.raises(WalkForwardValidationError) as exc_info:
            validate_window(window)
        assert exc_info.value.reason_code == BACKWARD_WINDOW

    def test_selection_end_equals_eval_start_rejected(self, tmp_path: Path) -> None:
        window = WalkForwardWindow(
            selection_start="20240101",
            selection_end="20240201",
            evaluation_start="20240201",
            evaluation_end="20240301",
        )
        with pytest.raises(WalkForwardValidationError) as exc_info:
            validate_window(window)
        assert exc_info.value.reason_code == BACKWARD_WINDOW

    def test_backward_evaluation_rejected(self, tmp_path: Path) -> None:
        window = WalkForwardWindow(
            selection_start="20240101",
            selection_end="20240201",
            evaluation_start="20240401",
            evaluation_end="20240301",
        )
        with pytest.raises(WalkForwardValidationError) as exc_info:
            validate_window(window)
        assert exc_info.value.reason_code == BACKWARD_WINDOW


class TestDuplicateRejection:
    def test_duplicate_window_rejected(self, tmp_path: Path) -> None:
        common = _make_common(tmp_path)
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
        plan = build_explicit_plan(common, windows, mode=WalkForwardMode.ROLLING)
        with pytest.raises(WalkForwardValidationError) as exc_info:
            validate_plan(plan)
        assert exc_info.value.reason_code == DUPLICATE_WINDOW


class TestOutOfOrderRejection:
    def test_evaluation_not_moving_forward_rejected(self, tmp_path: Path) -> None:
        common = _make_common(tmp_path)
        windows = [
            WalkForwardWindow(
                selection_start="20240101",
                selection_end="20240201",
                evaluation_start="20240301",
                evaluation_end="20240401",
            ),
            WalkForwardWindow(
                selection_start="20240201",
                selection_end="20240301",
                evaluation_start="20240315",
                evaluation_end="20240415",
            ),
        ]
        plan = build_explicit_plan(common, windows, mode=WalkForwardMode.ROLLING)
        with pytest.raises(WalkForwardValidationError) as exc_info:
            validate_plan(plan)
        assert exc_info.value.reason_code == OUT_OF_ORDER_WINDOWS

    def test_selection_not_moving_forward_rejected(self, tmp_path: Path) -> None:
        common = _make_common(tmp_path)
        windows = [
            WalkForwardWindow(
                selection_start="20240101",
                selection_end="20240201",
                evaluation_start="20240301",
                evaluation_end="20240401",
            ),
            WalkForwardWindow(
                selection_start="20240101",
                selection_end="20240301",
                evaluation_start="20240501",
                evaluation_end="20240601",
            ),
        ]
        plan = build_explicit_plan(common, windows, mode=WalkForwardMode.ROLLING)
        with pytest.raises(WalkForwardValidationError) as exc_info:
            validate_plan(plan)
        assert exc_info.value.reason_code == OUT_OF_ORDER_WINDOWS


class TestContiguousPolicy:
    def test_contiguous_valid(self, tmp_path: Path) -> None:
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
        validate_plan(plan)

    def test_contiguous_policy_violation(self, tmp_path: Path) -> None:
        common = _make_common(tmp_path)
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
            common, windows, mode=WalkForwardMode.ROLLING, contiguous=True
        )
        with pytest.raises(WalkForwardValidationError) as exc_info:
            validate_plan(plan)
        assert exc_info.value.reason_code == INVALID_CONTIGUITY


class TestRollingDurationMismatch:
    def test_rolling_duration_mismatch(self, tmp_path: Path) -> None:
        common = _make_common(tmp_path)
        windows = [
            WalkForwardWindow(
                selection_start="20240101",
                selection_end="20240201",
                evaluation_start="20240301",
                evaluation_end="20240401",
            ),
            WalkForwardWindow(
                selection_start="20240201",
                selection_end="20240315",
                evaluation_start="20240401",
                evaluation_end="20240501",
            ),
        ]
        plan = build_explicit_plan(common, windows, mode=WalkForwardMode.ROLLING)
        with pytest.raises(WalkForwardValidationError) as exc_info:
            validate_plan(plan)
        assert exc_info.value.reason_code == ROLLING_DURATION_DRIFT


class TestExpandingStartMismatch:
    def test_expanding_start_mismatch(self, tmp_path: Path) -> None:
        common = _make_common(tmp_path)
        windows = [
            WalkForwardWindow(
                selection_start="20240101",
                selection_end="20240201",
                evaluation_start="20240501",
                evaluation_end="20240601",
            ),
            WalkForwardWindow(
                selection_start="20240201",
                selection_end="20240301",
                evaluation_start="20240601",
                evaluation_end="20240701",
            ),
        ]
        plan = build_explicit_plan(common, windows, mode=WalkForwardMode.EXPANDING)
        with pytest.raises(WalkForwardValidationError) as exc_info:
            validate_plan(plan)
        assert exc_info.value.reason_code == EXPANDING_START_DRIFT
