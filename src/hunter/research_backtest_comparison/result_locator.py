"""Result file containment and validation for the research backtest comparison harness (MVP-65 / SPEC-066)."""

from __future__ import annotations

import json

from pathlib import Path

from hunter.research_backtest_comparison.errors import (
    ResearchBacktestComparisonRunnerError,
)
from hunter.research_backtest_comparison.models import (
    RESULT_CONTAINMENT_FAILURE,
    RESULT_NOT_FOUND,
)

# Freqtrade's pointer filename recording the most recent backtest export
# (see freqtrade.constants.LAST_BT_RESULT_FN).
_LAST_BT_RESULT_FN = ".last_result.json"


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


def locate_latest_backtest_result(
    backtest_results_dir: str | Path,
    workspace: str | Path,
) -> Path:
    """Locate the most recent Freqtrade backtest export inside *backtest_results_dir*.

    Modern Freqtrade ignores ``--export-filename`` for backtesting and instead
    writes a timestamped ``.zip`` into the directory passed via
    ``--backtest-directory``, recording the exact filename in a
    ``.last_result.json`` pointer file (``{"latest_backtest": "<name>.zip"}``).
    This reads that pointer and validates the referenced file exactly as
    :func:`locate_result_file` validates a fixed path: rejects symlinks, path
    escapes, and non-regular files.

    Raises:
        ResearchBacktestComparisonRunnerError: on a missing directory,
            missing/malformed pointer file, or containment failure.
    """
    results_dir = Path(backtest_results_dir).resolve()
    workspace_root = Path(workspace).resolve()

    if not results_dir.exists() or not results_dir.is_dir():
        raise ResearchBacktestComparisonRunnerError(
            f"backtest results directory not found: {results_dir}",
            reason_code=RESULT_NOT_FOUND,
        )

    pointer = results_dir / _LAST_BT_RESULT_FN
    if pointer.is_symlink():
        raise ResearchBacktestComparisonRunnerError(
            f"result pointer file is a symlink: {pointer}",
            reason_code=RESULT_CONTAINMENT_FAILURE,
        )
    if not pointer.exists() or not pointer.is_file():
        raise ResearchBacktestComparisonRunnerError(
            f"result pointer file not found: {pointer}", reason_code=RESULT_NOT_FOUND
        )

    try:
        pointer_data = json.loads(pointer.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ResearchBacktestComparisonRunnerError(
            f"result pointer file is not valid JSON: {exc}",
            reason_code=RESULT_NOT_FOUND,
        ) from exc

    latest_name = pointer_data.get("latest_backtest") if isinstance(pointer_data, dict) else None
    if not isinstance(latest_name, str) or not latest_name.strip():
        raise ResearchBacktestComparisonRunnerError(
            f"result pointer file missing 'latest_backtest': {pointer}",
            reason_code=RESULT_NOT_FOUND,
        )
    # The pointer must name a bare filename inside results_dir — never a path.
    if "/" in latest_name or "\\" in latest_name or latest_name in (".", ".."):
        raise ResearchBacktestComparisonRunnerError(
            f"result pointer filename is not a bare filename: {latest_name!r}",
            reason_code=RESULT_CONTAINMENT_FAILURE,
        )

    return locate_result_file(results_dir / latest_name, workspace_root)
