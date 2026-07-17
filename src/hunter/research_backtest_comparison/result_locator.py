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

    Rejects **all** symlinks (even when the target is inside the workspace),
    path escapes, non-regular files, and missing files.

    Raises:
        ResearchBacktestComparisonRunnerError: on containment failure.
    """
    # Preserve the original (unresolved) entry so we can detect symlinks
    # before resolve() follows them.
    original = Path(expected_path)
    resolved = original.resolve()
    workspace_root = Path(workspace).resolve()

    # Reject every symlink — regardless of where the target lives.
    # Must check the original entry because resolve() follows the link.
    if original.is_symlink():
        raise ResearchBacktestComparisonRunnerError(
            f"result file is a symlink: {original}",
            reason_code=RESULT_CONTAINMENT_FAILURE,
        )

    if not resolved.exists():
        raise ResearchBacktestComparisonRunnerError(
            f"result file not found: {resolved}", reason_code=RESULT_NOT_FOUND
        )
    if not resolved.is_file():
        raise ResearchBacktestComparisonRunnerError(
            f"result path is not a regular file: {resolved}",
            reason_code=RESULT_CONTAINMENT_FAILURE,
        )
    try:
        resolved.relative_to(workspace_root)
    except ValueError:
        raise ResearchBacktestComparisonRunnerError(
            f"result file escapes workspace: {resolved}",
            reason_code=RESULT_CONTAINMENT_FAILURE,
        )

    return resolved
