"""Result file containment and validation for the research backtest comparison harness (MVP-65 / SPEC-066)."""

from __future__ import annotations

from pathlib import Path

from hunter.research_backtest_comparison.errors import (
    ResearchBacktestComparisonRunnerError,
)
from hunter.research_backtest_comparison.models import (
    RESULT_CONTAINMENT_FAILURE,
    RESULT_NOT_FOUND,
)


def locate_result_file(
    expected_path: str | Path,
    workspace: str | Path,
) -> Path:
    """Verify that the expected result file is a regular file inside the workspace.

    Rejects symlinks, path escapes, and missing files.

    Raises:
        ResearchBacktestComparisonRunnerError: on containment failure.
    """
    expected = Path(expected_path).resolve()
    workspace_root = Path(workspace).resolve()

    if not expected.exists():
        raise ResearchBacktestComparisonRunnerError(
            f"result file not found: {expected}", reason_code=RESULT_NOT_FOUND
        )
    if not expected.is_file():
        raise ResearchBacktestComparisonRunnerError(
            f"result path is not a regular file: {expected}",
            reason_code=RESULT_CONTAINMENT_FAILURE,
        )
    if expected.is_symlink():
        raise ResearchBacktestComparisonRunnerError(
            f"result file is a symlink: {expected}",
            reason_code=RESULT_CONTAINMENT_FAILURE,
        )
    try:
        expected.relative_to(workspace_root)
    except ValueError:
        raise ResearchBacktestComparisonRunnerError(
            f"result file escapes workspace: {expected}",
            reason_code=RESULT_CONTAINMENT_FAILURE,
        )

    return expected
