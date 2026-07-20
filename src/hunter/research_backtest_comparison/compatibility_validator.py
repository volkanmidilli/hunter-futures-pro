"""External resource validation for real Freqtrade compatibility (SPEC-072)."""

from __future__ import annotations

from pathlib import Path

from hunter.research_backtest_comparison.errors import (
    ResearchBacktestComparisonValidationError,
)
from hunter.research_backtest_comparison.executable import validate_executable
from hunter.research_backtest_comparison.models import (
    COMPATIBILITY_INVALID_EXTERNAL_FIXTURE,
    COMPATIBILITY_NOT_EXECUTED,
    REAL_FREQTRADE_COMPATIBILITY_NOT_EXECUTED,
    CompatibilityStatus,
    FreqtradeCompatibilityInput,
    FreqtradeExecutableInfo,
)


# Characters that are not safe in CLI arguments.
_UNSAFE_CHARS: frozenset[str] = frozenset({";", "&", "|", "`", "$", "\n", "\r"})


def _has_path_traversal(path: Path) -> bool:
    """Return True if the path attempts to escape its root."""
    try:
        path.resolve()
    except OSError:
        return True
    return ".." in path.parts


def _is_inside_permitted_parent(path: Path, permitted_parent: Path | None = None) -> bool:
    """Return True if the path is absolute and inside a permitted parent."""
    if not path.is_absolute():
        return False
    if permitted_parent is not None:
        try:
            path.resolve().relative_to(permitted_parent.resolve())
        except ValueError:
            return False
    return True


def validate_external_resources(
    input: FreqtradeCompatibilityInput | None,
    *,
    permitted_strategy_parent: Path | None = None,
    permitted_data_parent: Path | None = None,
) -> tuple[CompatibilityStatus, FreqtradeExecutableInfo | None, tuple[str, ...]]:
    """Validate caller-provided external resources for a compatibility smoke test.

    Returns a compatibility status, executable info, and reason codes. If any
    external resource is missing, the status is INVALID_EXTERNAL_FIXTURE and the
    reason code REAL_FREQTRADE_COMPATIBILITY_NOT_EXECUTED is included.

    This function does not access the repository ``data/`` or ``reports/``
    directories; it only inspects the caller-provided absolute paths.
    """
    if input is None:
        return (
            CompatibilityStatus.INVALID_EXTERNAL_FIXTURE,
            None,
            (COMPATIBILITY_INVALID_EXTERNAL_FIXTURE, REAL_FREQTRADE_COMPATIBILITY_NOT_EXECUTED),
        )

    if not isinstance(input, FreqtradeCompatibilityInput):
        raise ResearchBacktestComparisonValidationError(
            f"input must be FreqtradeCompatibilityInput, got {input!r}"
        )

    reason_codes: list[str] = []
    status = CompatibilityStatus.NOT_EXECUTED

    # Executable must be an absolute, existing, executable file.
    executable_path = input.executable_path
    if not executable_path.is_absolute():
        reason_codes.append(COMPATIBILITY_INVALID_EXTERNAL_FIXTURE)
        reason_codes.append(REAL_FREQTRADE_COMPATIBILITY_NOT_EXECUTED)
        return (
            CompatibilityStatus.INVALID_EXTERNAL_FIXTURE,
            None,
            tuple(reason_codes),
        )
    if not executable_path.exists() or not executable_path.is_file():
        reason_codes.append(COMPATIBILITY_INVALID_EXTERNAL_FIXTURE)
        reason_codes.append(REAL_FREQTRADE_COMPATIBILITY_NOT_EXECUTED)
        return (
            CompatibilityStatus.INVALID_EXTERNAL_FIXTURE,
            None,
            tuple(reason_codes),
        )

    # Strategy path must be a regular file inside permitted parent.
    strategy_path = input.strategy_path
    if not strategy_path.is_absolute():
        reason_codes.append(COMPATIBILITY_INVALID_EXTERNAL_FIXTURE)
    elif not strategy_path.exists() or not strategy_path.is_file():
        reason_codes.append(COMPATIBILITY_INVALID_EXTERNAL_FIXTURE)
    elif _has_path_traversal(strategy_path):
        reason_codes.append(COMPATIBILITY_INVALID_EXTERNAL_FIXTURE)
    elif not _is_inside_permitted_parent(strategy_path, permitted_strategy_parent):
        reason_codes.append(COMPATIBILITY_INVALID_EXTERNAL_FIXTURE)

    # Data path must be a directory.
    data_path = input.data_path
    if not data_path.is_absolute():
        reason_codes.append(COMPATIBILITY_INVALID_EXTERNAL_FIXTURE)
    elif not data_path.exists() or not data_path.is_dir():
        reason_codes.append(COMPATIBILITY_INVALID_EXTERNAL_FIXTURE)
    elif _has_path_traversal(data_path):
        reason_codes.append(COMPATIBILITY_INVALID_EXTERNAL_FIXTURE)
    elif not _is_inside_permitted_parent(data_path, permitted_data_parent):
        reason_codes.append(COMPATIBILITY_INVALID_EXTERNAL_FIXTURE)

    # Output directory must be absolute and not under forbidden repo paths.
    output_dir = input.output_dir
    if not output_dir.is_absolute():
        reason_codes.append(COMPATIBILITY_INVALID_EXTERNAL_FIXTURE)
    elif _has_path_traversal(output_dir):
        reason_codes.append(COMPATIBILITY_INVALID_EXTERNAL_FIXTURE)

    # Pairs must be safe strings.
    for pair in input.pairs:
        if not isinstance(pair, str) or not pair.strip():
            reason_codes.append(COMPATIBILITY_INVALID_EXTERNAL_FIXTURE)
        elif any(c in pair for c in _UNSAFE_CHARS):
            reason_codes.append(COMPATIBILITY_INVALID_EXTERNAL_FIXTURE)

    if reason_codes:
        reason_codes.append(REAL_FREQTRADE_COMPATIBILITY_NOT_EXECUTED)
        return (
            CompatibilityStatus.INVALID_EXTERNAL_FIXTURE,
            None,
            tuple(reason_codes),
        )

    # Validate executable by running ``freqtrade --version``.
    executable_info = validate_executable(
        executable_path,
        timeout_seconds=input.timeout_seconds,
    )
    if not executable_info.is_valid:
        reason_codes.append(COMPATIBILITY_INVALID_EXTERNAL_FIXTURE)
        reason_codes.append(REAL_FREQTRADE_COMPATIBILITY_NOT_EXECUTED)
        return (
            CompatibilityStatus.INVALID_EXTERNAL_FIXTURE,
            executable_info,
            tuple(reason_codes),
        )

    status = CompatibilityStatus.NOT_EXECUTED
    return status, executable_info, tuple(reason_codes)
