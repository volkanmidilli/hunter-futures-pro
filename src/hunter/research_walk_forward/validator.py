"""Plan and window validation for the walk-forward harness (MVP-66 / SPEC-067)."""

from __future__ import annotations

from hunter.research_walk_forward.models import (
    BACKWARD_WINDOW,
    DUPLICATE_WINDOW,
    EXPANDING_START_DRIFT,
    INVALID_CONTIGUITY,
    INVALID_WINDOW,
    OUT_OF_ORDER_WINDOWS,
    ROLLING_DURATION_DRIFT,
    WalkForwardConfigError,
    WalkForwardExperimentPlan,
    WalkForwardMode,
    WalkForwardValidationError,
    WalkForwardWindow,
)


def _window_sort_key(window: WalkForwardWindow) -> tuple[str, str, str, str]:
    """Sort key that orders windows chronologically."""
    return (window.selection_start, window.selection_end, window.evaluation_start, window.evaluation_end)


def _validate_single_window(window: WalkForwardWindow) -> None:
    """Validate one window's internal chronology."""
    if window.selection_start >= window.selection_end:
        raise WalkForwardValidationError(
            f"selection_start must be < selection_end: {window}",
            reason_code=BACKWARD_WINDOW,
        )
    if window.selection_end >= window.evaluation_start:
        raise WalkForwardValidationError(
            f"selection_end must be < evaluation_start: {window}",
            reason_code=BACKWARD_WINDOW,
        )
    if window.evaluation_start >= window.evaluation_end:
        raise WalkForwardValidationError(
            f"evaluation_start must be < evaluation_end: {window}",
            reason_code=BACKWARD_WINDOW,
        )


def _detect_duplicates(windows: tuple[WalkForwardWindow, ...]) -> None:
    """Reject duplicate windows."""
    seen: set[tuple[str, str, str, str]] = set()
    for window in windows:
        key = (window.selection_start, window.selection_end, window.evaluation_start, window.evaluation_end)
        if key in seen:
            raise WalkForwardValidationError(
                f"Duplicate window: {key}",
                reason_code=DUPLICATE_WINDOW,
            )
        seen.add(key)


def _detect_order_and_leakage(windows: tuple[WalkForwardWindow, ...]) -> None:
    """Reject out-of-order or backward-moving windows."""
    for i in range(1, len(windows)):
        prev = windows[i - 1]
        curr = windows[i]
        if curr.evaluation_start < prev.evaluation_end:
            raise WalkForwardValidationError(
                f"Window {i} evaluation starts before or at previous window evaluation ends: "
                f"{prev.evaluation_end} -> {curr.evaluation_start}",
                reason_code=OUT_OF_ORDER_WINDOWS,
            )
        if curr.selection_start <= prev.selection_start:
            raise WalkForwardValidationError(
                f"Window {i} selection_start does not move forward: "
                f"{prev.selection_start} -> {curr.selection_start}",
                reason_code=OUT_OF_ORDER_WINDOWS,
            )


def _validate_contiguity(windows: tuple[WalkForwardWindow, ...], contiguous: bool) -> None:
    """Validate contiguous evaluation boundaries."""
    if not contiguous:
        return
    for i in range(1, len(windows)):
        prev = windows[i - 1]
        curr = windows[i]
        if curr.evaluation_start != prev.evaluation_end:
            raise WalkForwardValidationError(
                f"Contiguous policy violated between window {i - 1} and {i}: "
                f"previous evaluation_end {prev.evaluation_end} != current evaluation_start {curr.evaluation_start}",
                reason_code=INVALID_CONTIGUITY,
            )


def _validate_mode_constraints(plan: WalkForwardExperimentPlan) -> None:
    """Validate rolling/expanding-specific constraints."""
    if not plan.windows:
        return

    if plan.mode == WalkForwardMode.ROLLING:
        first = plan.windows[0]
        expected_selection_duration = _duration_days(first.selection_start, first.selection_end)
        expected_evaluation_duration = _duration_days(first.evaluation_start, first.evaluation_end)
        for i, window in enumerate(plan.windows):
            selection_duration = _duration_days(window.selection_start, window.selection_end)
            evaluation_duration = _duration_days(window.evaluation_start, window.evaluation_end)
            if selection_duration != expected_selection_duration:
                raise WalkForwardValidationError(
                    f"Rolling selection duration mismatch at window {i}: "
                    f"expected {expected_selection_duration}, got {selection_duration}",
                    reason_code=ROLLING_DURATION_DRIFT,
                )
            if evaluation_duration != expected_evaluation_duration:
                raise WalkForwardValidationError(
                    f"Rolling evaluation duration mismatch at window {i}: "
                    f"expected {expected_evaluation_duration}, got {evaluation_duration}",
                    reason_code=ROLLING_DURATION_DRIFT,
                )

    if plan.mode == WalkForwardMode.EXPANDING:
        first = plan.windows[0]
        expected_start = first.selection_start
        for i, window in enumerate(plan.windows):
            if window.selection_start != expected_start:
                raise WalkForwardValidationError(
                    f"Expanding selection start mismatch at window {i}: "
                    f"expected {expected_start}, got {window.selection_start}",
                    reason_code=EXPANDING_START_DRIFT,
                )


def _duration_days(start: str, end: str) -> int:
    """Return the duration in days between two YYYYMMDD boundaries."""
    from datetime import datetime

    fmt = "%Y%m%d"
    start_dt = datetime.strptime(start, fmt)
    end_dt = datetime.strptime(end, fmt)
    return (end_dt - start_dt).days


def validate_plan(plan: WalkForwardExperimentPlan | None) -> None:
    """Validate the full experiment plan."""
    if plan is None:
        raise WalkForwardConfigError("plan is required", reason_code=INVALID_WINDOW)
    if not isinstance(plan, WalkForwardExperimentPlan):
        raise WalkForwardConfigError(
            f"plan must be a WalkForwardExperimentPlan, got {plan!r}",
            reason_code=INVALID_WINDOW,
        )
    if not plan.windows:
        raise WalkForwardValidationError(
            "plan must contain at least one window", reason_code=INVALID_WINDOW
        )

    for i, window in enumerate(plan.windows):
        try:
            _validate_single_window(window)
        except WalkForwardValidationError as exc:
            raise WalkForwardValidationError(
                f"Window {i}: {exc}", reason_code=exc.reason_code
            ) from exc

    _detect_duplicates(plan.windows)
    _detect_order_and_leakage(plan.windows)
    _validate_contiguity(plan.windows, plan.contiguous)
    _validate_mode_constraints(plan)


def validate_window(window: WalkForwardWindow | None) -> None:
    """Validate a single window."""
    if window is None:
        raise WalkForwardValidationError(
            "window is required", reason_code=INVALID_WINDOW
        )
    if not isinstance(window, WalkForwardWindow):
        raise WalkForwardValidationError(
            f"window must be a WalkForwardWindow, got {window!r}",
            reason_code=INVALID_WINDOW,
        )
    _validate_single_window(window)
