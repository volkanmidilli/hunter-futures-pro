"""Input validation for the research backtest comparison harness (MVP-65 / SPEC-066)."""

from __future__ import annotations

from pathlib import Path

from hunter.research_backtest_comparison.errors import (
    ResearchBacktestComparisonConfigError,
    ResearchBacktestComparisonValidationError,
)
from hunter.research_backtest_comparison.models import (
    BacktestArmInput,
    BacktestComparisonConfig,
)


# Subcommands and modes that are never allowed.
_FORBIDDEN_SUBCOMMANDS: frozenset[str] = frozenset(
    {
        "trade",
        "webserver",
        "hyperopt",
        "hyperopt-list",
        "hyperopt-show",
        "list-strategies",
        "list-timeframes",
        "download-data",
        "plot-dataframe",
        "plot-profit",
        "show-trades",
        "test-pairlist",
        "convert-data",
        "convert-trade-data",
    }
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


def validate_config(
    config: BacktestComparisonConfig | None,
    *,
    permitted_strategy_parent: Path | None = None,
    permitted_data_parent: Path | None = None,
) -> None:
    """Validate the comparison configuration.

    Raises:
        ResearchBacktestComparisonConfigError: on invalid configuration.
    """
    if config is None:
        raise ResearchBacktestComparisonConfigError("config is required")

    if not isinstance(config, BacktestComparisonConfig):
        raise ResearchBacktestComparisonConfigError(
            f"config must be BacktestComparisonConfig, got {config!r}"
        )

    # Strategy path must be a regular file inside permitted parent.
    strategy_path = config.strategy_path
    if not strategy_path.is_absolute():
        raise ResearchBacktestComparisonConfigError(
            f"strategy_path must be absolute: {strategy_path}"
        )
    if not strategy_path.exists() or not strategy_path.is_file():
        raise ResearchBacktestComparisonConfigError(
            f"strategy_path is not a regular file: {strategy_path}"
        )
    if _has_path_traversal(strategy_path):
        raise ResearchBacktestComparisonConfigError(
            f"strategy_path contains path traversal: {strategy_path}"
        )
    if not _is_inside_permitted_parent(strategy_path, permitted_strategy_parent):
        raise ResearchBacktestComparisonConfigError(
            f"strategy_path outside permitted parent: {strategy_path}"
        )

    # Data path must be a directory.
    data_path = config.data_path
    if not data_path.is_absolute():
        raise ResearchBacktestComparisonConfigError(
            f"data_path must be absolute: {data_path}"
        )
    if not data_path.exists() or not data_path.is_dir():
        raise ResearchBacktestComparisonConfigError(
            f"data_path is not a directory: {data_path}"
        )
    if _has_path_traversal(data_path):
        raise ResearchBacktestComparisonConfigError(
            f"data_path contains path traversal: {data_path}"
        )
    if not _is_inside_permitted_parent(data_path, permitted_data_parent):
        raise ResearchBacktestComparisonConfigError(
            f"data_path outside permitted parent: {data_path}"
        )

    # Executable path must be absolute and exist.
    executable_path = config.executable_path
    if not executable_path.is_absolute():
        raise ResearchBacktestComparisonConfigError(
            f"executable_path must be absolute: {executable_path}"
        )
    if not executable_path.exists() or not executable_path.is_file():
        raise ResearchBacktestComparisonConfigError(
            f"executable_path is not a regular file: {executable_path}"
        )

    # Validate simple string fields.
    if not config.timeframe or not config.timeframe.strip():
        raise ResearchBacktestComparisonConfigError("timeframe is required")
    if not config.timerange or not config.timerange.strip():
        raise ResearchBacktestComparisonConfigError("timerange is required")

    # Validate numeric fields.
    if config.balance <= 0:
        raise ResearchBacktestComparisonConfigError("balance must be positive")
    if config.stake <= 0:
        raise ResearchBacktestComparisonConfigError("stake must be positive")
    if config.max_open_trades < 1:
        raise ResearchBacktestComparisonConfigError("max_open_trades must be at least 1")
    if config.fee < 0:
        raise ResearchBacktestComparisonConfigError("fee must be non-negative")


def validate_pairlist(arm_input: BacktestArmInput | None) -> None:
    """Validate a backtest arm input pairlist.

    Raises:
        ResearchBacktestComparisonValidationError: on invalid pairlist.
    """
    if arm_input is None:
        raise ResearchBacktestComparisonValidationError("arm_input is required")
    if not isinstance(arm_input, BacktestArmInput):
        raise ResearchBacktestComparisonValidationError(
            f"arm_input must be BacktestArmInput, got {arm_input!r}"
        )
    if not arm_input.pairlist:
        raise ResearchBacktestComparisonValidationError("pairlist must be non-empty")
    for pair in arm_input.pairlist:
        if not isinstance(pair, str) or not pair.strip():
            raise ResearchBacktestComparisonValidationError(
                f"pairlist contains invalid pair: {pair!r}"
            )
        if any(c in pair for c in _UNSAFE_CHARS):
            raise ResearchBacktestComparisonValidationError(
                f"pair contains unsafe characters: {pair!r}"
            )


def validate_command_args(args: list[str]) -> None:
    """Validate a built command argument list for forbidden subcommands.

    Raises:
        ResearchBacktestComparisonValidationError: on forbidden content.
    """
    if not args:
        raise ResearchBacktestComparisonValidationError("command args must not be empty")
    for token in args:
        if not isinstance(token, str):
            raise ResearchBacktestComparisonValidationError(
                "command args must be strings"
            )
        if any(c in token for c in _UNSAFE_CHARS):
            raise ResearchBacktestComparisonValidationError(
                f"command arg contains unsafe characters: {token!r}"
            )
    if len(args) < 2 or args[1] != "backtesting":
        raise ResearchBacktestComparisonValidationError(
            "only freqtrade backtesting is allowed"
        )
    for token in args:
        if token in _FORBIDDEN_SUBCOMMANDS:
            raise ResearchBacktestComparisonValidationError(
                f"forbidden subcommand: {token}"
            )


def validate_strategy_class_name(strategy_path: str | Path, strategy_name: str) -> None:
    """Validate that the requested strategy class name appears in the source file.

    Raises:
        ResearchBacktestComparisonValidationError: on missing or invalid class name.
    """
    path = Path(strategy_path)
    if not path.exists() or not path.is_file():
        raise ResearchBacktestComparisonValidationError(
            f"strategy_path is not a regular file: {path}"
        )
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ResearchBacktestComparisonValidationError(
            f"failed to read strategy file: {exc}"
        ) from exc

    # Simple lexical check: class definition with the requested name.
    import re

    if not re.search(rf"^class\s+{re.escape(strategy_name)}\b", text, re.MULTILINE):
        raise ResearchBacktestComparisonValidationError(
            f"strategy class {strategy_name!r} not found in {path}"
        )

    if not isinstance(strategy_name, str) or not strategy_name.isidentifier():
        raise ResearchBacktestComparisonValidationError(
            f"strategy_name must be a valid Python identifier: {strategy_name!r}"
        )
