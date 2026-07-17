"""Leakage guard for walk-forward windows (MVP-66 / SPEC-067)."""

from __future__ import annotations

from datetime import datetime

from hunter.research_walk_forward.models import (
    LEAKAGE,
    INVALID_WINDOW,
    WalkForwardLeakageError,
    WalkForwardWindow,
)


_DATE_FORMAT = "%Y%m%d"


def _parse_date(value: str) -> datetime:
    """Parse a YYYYMMDD boundary string."""
    try:
        return datetime.strptime(value, _DATE_FORMAT)
    except ValueError as exc:
        raise ValueError(f"Invalid date boundary {value!r}: {exc}") from exc


def validate_window_chronology(window: WalkForwardWindow) -> None:
    """Validate strict single-window chronology.

    Requires: selection_start < selection_end < evaluation_start < evaluation_end.
    """
    sel_start = _parse_date(window.selection_start)
    sel_end = _parse_date(window.selection_end)
    eval_start = _parse_date(window.evaluation_start)
    eval_end = _parse_date(window.evaluation_end)

    if not (sel_start < sel_end < eval_start < eval_end):
        raise WalkForwardLeakageError(
            f"Window chronology violation: selection_start < selection_end < "
            f"evaluation_start < evaluation_end required; got "
            f"{window.selection_start} < {window.selection_end} < "
            f"{window.evaluation_start} < {window.evaluation_end}",
            reason_code=LEAKAGE,
        )


def validate_no_leakage(windows: tuple[WalkForwardWindow, ...]) -> None:
    """Validate that no data leaks across windows.

    Checks:
    - Each window satisfies strict chronology.
    - Evaluation windows are strictly ordered and non-overlapping.
    - No selection window overlaps with any evaluation window of another window.
    - All windows move forward in time.
    """
    if not windows:
        raise WalkForwardLeakageError(
            "No windows provided", reason_code=INVALID_WINDOW
        )

    for i, window in enumerate(windows):
        try:
            validate_window_chronology(window)
        except WalkForwardLeakageError as exc:
            raise WalkForwardLeakageError(
                f"Window {i}: {exc}", reason_code=exc.reason_code
            ) from exc

    for i in range(1, len(windows)):
        prev = windows[i - 1]
        curr = windows[i]
        # Evaluation windows must not overlap and must move forward.
        if _parse_date(curr.evaluation_start) < _parse_date(prev.evaluation_end):
            raise WalkForwardLeakageError(
                f"Leakage: window {i} evaluation [{curr.evaluation_start}, {curr.evaluation_end}] "
                f"overlaps previous evaluation [{prev.evaluation_start}, {prev.evaluation_end}]",
                reason_code=LEAKAGE,
            )
        # Selection windows must move forward.
        if _parse_date(curr.selection_start) <= _parse_date(prev.selection_start):
            raise WalkForwardLeakageError(
                f"Leakage: window {i} selection does not move forward "
                f"({prev.selection_start} -> {curr.selection_start})",
                reason_code=LEAKAGE,
            )

