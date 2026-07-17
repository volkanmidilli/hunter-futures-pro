"""Tests for the walk-forward leakage guard (MVP-66 Stage 3)."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from hunter.research_walk_forward.leakage import (
    validate_no_leakage,
    validate_window_chronology,
)
from hunter.research_walk_forward.models import (
    LEAKAGE,
    INVALID_WINDOW,
    WalkForwardLeakageError,
    WalkForwardWindow,
)


class TestSingleWindowChronology:
    def test_strict_chronology_valid(self) -> None:
        window = WalkForwardWindow(
            selection_start="20240101",
            selection_end="20240201",
            evaluation_start="20240301",
            evaluation_end="20240401",
        )
        validate_window_chronology(window)

    def test_selection_end_equals_eval_start_rejected(self) -> None:
        window = WalkForwardWindow(
            selection_start="20240101",
            selection_end="20240201",
            evaluation_start="20240201",
            evaluation_end="20240301",
        )
        with pytest.raises(WalkForwardLeakageError) as exc_info:
            validate_window_chronology(window)
        assert exc_info.value.reason_code == LEAKAGE

    def test_eval_start_equals_eval_end_rejected(self) -> None:
        window = WalkForwardWindow(
            selection_start="20240101",
            selection_end="20240201",
            evaluation_start="20240301",
            evaluation_end="20240301",
        )
        with pytest.raises(WalkForwardLeakageError) as exc_info:
            validate_window_chronology(window)
        assert exc_info.value.reason_code == LEAKAGE

    def test_selection_start_equals_selection_end_rejected(self) -> None:
        window = WalkForwardWindow(
            selection_start="20240101",
            selection_end="20240101",
            evaluation_start="20240201",
            evaluation_end="20240301",
        )
        with pytest.raises(WalkForwardLeakageError) as exc_info:
            validate_window_chronology(window)
        assert exc_info.value.reason_code == LEAKAGE


class TestCrossWindowLeakage:
    def test_no_leakage_valid(self) -> None:
        windows = (
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
        )
        validate_no_leakage(windows)

    def test_evaluation_overlap_rejected(self) -> None:
        windows = (
            WalkForwardWindow(
                selection_start="20240101",
                selection_end="20240201",
                evaluation_start="20240301",
                evaluation_end="20240501",
            ),
            WalkForwardWindow(
                selection_start="20240501",
                selection_end="20240601",
                evaluation_start="20240401",
                evaluation_end="20240601",
            ),
        )
        with pytest.raises(WalkForwardLeakageError) as exc_info:
            validate_no_leakage(windows)
        assert exc_info.value.reason_code == LEAKAGE

    def test_selection_eval_overlap_rejected(self) -> None:
        windows = (
            WalkForwardWindow(
                selection_start="20240101",
                selection_end="20240201",
                evaluation_start="20240301",
                evaluation_end="20240401",
            ),
            WalkForwardWindow(
                selection_start="20240315",
                selection_end="20240501",
                evaluation_start="20240501",
                evaluation_end="20240601",
            ),
        )
        with pytest.raises(WalkForwardLeakageError) as exc_info:
            validate_no_leakage(windows)
        assert exc_info.value.reason_code == LEAKAGE

    def test_evaluation_not_moving_forward_rejected(self) -> None:
        windows = (
            WalkForwardWindow(
                selection_start="20240101",
                selection_end="20240201",
                evaluation_start="20240301",
                evaluation_end="20240401",
            ),
            WalkForwardWindow(
                selection_start="20240501",
                selection_end="20240601",
                evaluation_start="20240315",
                evaluation_end="20240515",
            ),
        )
        with pytest.raises(WalkForwardLeakageError) as exc_info:
            validate_no_leakage(windows)
        assert exc_info.value.reason_code == LEAKAGE


class TestEmptyWindows:
    def test_empty_windows_rejected(self) -> None:
        with pytest.raises(WalkForwardLeakageError) as exc_info:
            validate_no_leakage(())
        assert exc_info.value.reason_code == INVALID_WINDOW
