"""Deterministic walk-forward plan builders (MVP-66 / SPEC-067)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from hunter.research_walk_forward.models import (
    MarketRegimeLabel,
    WalkForwardCommonConfig,
    WalkForwardExperimentPlan,
    WalkForwardMode,
    WalkForwardSafetyFlags,
    WalkForwardWindow,
)

_DATE_FORMAT = "%Y%m%d"


def _parse_date(value: str) -> datetime:
    """Parse a YYYYMMDD boundary string."""
    try:
        return datetime.strptime(value, _DATE_FORMAT)
    except ValueError as exc:
        raise ValueError(f"Invalid date boundary {value!r}: {exc}") from exc


def _format_date(value: datetime) -> str:
    """Format a datetime as YYYYMMDD."""
    return value.strftime(_DATE_FORMAT)


def _build_windows_from_explicit(
    windows: list[WalkForwardWindow],
) -> tuple[WalkForwardWindow, ...]:
    """Return explicit windows as a tuple; validation is handled by the validator."""
    return tuple(windows)


def build_explicit_plan(
    common: WalkForwardCommonConfig,
    windows: list[WalkForwardWindow],
    mode: WalkForwardMode = WalkForwardMode.ROLLING,
    contiguous: bool = False,
    metadata: Any | None = None,
) -> WalkForwardExperimentPlan:
    """Build a plan from explicit caller-provided windows."""
    if not windows:
        raise ValueError("windows must be non-empty")
    return WalkForwardExperimentPlan(
        mode=mode,
        windows=_build_windows_from_explicit(windows),
        common=common,
        contiguous=contiguous,
        safety_flags=WalkForwardSafetyFlags(),
        metadata=metadata,
    )


def build_rolling_plan(
    common: WalkForwardCommonConfig,
    *,
    selection_start: str,
    selection_end: str,
    evaluation_start: str,
    evaluation_end: str,
    step_days: int,
    count: int,
    contiguous: bool = True,
    regime_labels: list[MarketRegimeLabel] | None = None,
    metadata: Any | None = None,
) -> WalkForwardExperimentPlan:
    """Build a rolling walk-forward plan with fixed-duration windows."""
    if count < 1:
        raise ValueError("count must be at least 1")
    if step_days < 1:
        raise ValueError("step_days must be at least 1")

    sel_start = _parse_date(selection_start)
    sel_end = _parse_date(selection_end)
    eval_start = _parse_date(evaluation_start)
    eval_end = _parse_date(evaluation_end)

    expected_selection_duration = (sel_end - sel_start).days
    expected_evaluation_duration = (eval_end - eval_start).days
    if expected_selection_duration < 1:
        raise ValueError("selection duration must be at least 1 day")
    if expected_evaluation_duration < 1:
        raise ValueError("evaluation duration must be at least 1 day")

    step = timedelta(days=step_days)
    windows: list[WalkForwardWindow] = []
    for i in range(count):
        window_sel_start = sel_start + i * step
        window_sel_end = sel_end + i * step
        window_eval_start = eval_start + i * step
        window_eval_end = eval_end + i * step

        actual_selection_duration = (window_sel_end - window_sel_start).days
        actual_evaluation_duration = (window_eval_end - window_eval_start).days
        if actual_selection_duration != expected_selection_duration:
            raise ValueError(
                f"Rolling selection duration drift at window {i}: "
                f"expected {expected_selection_duration}, got {actual_selection_duration}"
            )
        if actual_evaluation_duration != expected_evaluation_duration:
            raise ValueError(
                f"Rolling evaluation duration drift at window {i}: "
                f"expected {expected_evaluation_duration}, got {actual_evaluation_duration}"
            )

        label = MarketRegimeLabel.UNKNOWN
        if regime_labels and i < len(regime_labels):
            label = regime_labels[i]

        windows.append(
            WalkForwardWindow(
                selection_start=_format_date(window_sel_start),
                selection_end=_format_date(window_sel_end),
                evaluation_start=_format_date(window_eval_start),
                evaluation_end=_format_date(window_eval_end),
                regime_label=label,
            )
        )

    return WalkForwardExperimentPlan(
        mode=WalkForwardMode.ROLLING,
        windows=tuple(windows),
        common=common,
        contiguous=contiguous,
        safety_flags=WalkForwardSafetyFlags(),
        metadata=metadata,
    )


def build_expanding_plan(
    common: WalkForwardCommonConfig,
    *,
    selection_start: str,
    selection_end: str,
    evaluation_start: str,
    evaluation_end: str,
    step_days: int,
    count: int,
    contiguous: bool = True,
    regime_labels: list[MarketRegimeLabel] | None = None,
    metadata: Any | None = None,
) -> WalkForwardExperimentPlan:
    """Build an expanding walk-forward plan with a fixed selection start."""
    if count < 1:
        raise ValueError("count must be at least 1")
    if step_days < 1:
        raise ValueError("step_days must be at least 1")

    sel_start = _parse_date(selection_start)
    sel_end = _parse_date(selection_end)
    eval_start = _parse_date(evaluation_start)
    eval_end = _parse_date(evaluation_end)

    expected_evaluation_duration = (eval_end - eval_start).days
    if expected_evaluation_duration < 1:
        raise ValueError("evaluation duration must be at least 1 day")

    step = timedelta(days=step_days)
    windows: list[WalkForwardWindow] = []
    for i in range(count):
        window_sel_start = sel_start
        window_sel_end = sel_end + i * step
        window_eval_start = eval_start + i * step
        window_eval_end = eval_end + i * step

        if window_sel_start != sel_start:
            raise ValueError(
                f"Expanding selection start drift at window {i}: "
                f"expected {selection_start}, got {_format_date(window_sel_start)}"
            )

        actual_evaluation_duration = (window_eval_end - window_eval_start).days
        if actual_evaluation_duration != expected_evaluation_duration:
            raise ValueError(
                f"Expanding evaluation duration drift at window {i}: "
                f"expected {expected_evaluation_duration}, got {actual_evaluation_duration}"
            )

        label = MarketRegimeLabel.UNKNOWN
        if regime_labels and i < len(regime_labels):
            label = regime_labels[i]

        windows.append(
            WalkForwardWindow(
                selection_start=_format_date(window_sel_start),
                selection_end=_format_date(window_sel_end),
                evaluation_start=_format_date(window_eval_start),
                evaluation_end=_format_date(window_eval_end),
                regime_label=label,
            )
        )

    return WalkForwardExperimentPlan(
        mode=WalkForwardMode.EXPANDING,
        windows=tuple(windows),
        common=common,
        contiguous=contiguous,
        safety_flags=WalkForwardSafetyFlags(),
        metadata=metadata,
    )
