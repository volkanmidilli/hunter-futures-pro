"""Shell adapter for Freqtrade Dry-Run Strategy Shell.

Adapter boundary that consumes ShellValidationResult and exposes
research-only metadata safely. No Freqtrade imports, no exchange
connections, no trading logic, no real entry/exit execution.
"""

from __future__ import annotations

from typing import Any

from hunter.freqtrade_shell.models import (
    ShellSignalExposure,
    ShellState,
    ShellValidationResult,
)


# ---------------------------------------------------------------------------
# Research-only column names
# ---------------------------------------------------------------------------

RESEARCH_SIGNAL_COLUMN = "hunter_research_signal"
RESEARCH_REASON_COLUMN = "hunter_research_reason"
RESEARCH_STATE_COLUMN = "hunter_shell_state"
RESEARCH_EXPOSURE_COLUMN = "hunter_signal_exposure"

# Forbidden real trade columns
_FORBIDDEN_COLUMNS = {"enter_long", "enter_short", "exit_long", "exit_short"}


def shell_validation_result_to_metadata(
    result: ShellValidationResult,
) -> dict[str, object]:
    """Serialize a ``ShellValidationResult`` to a deterministic metadata dict.

    Enum fields are serialized to their ``.value`` strings.  The
    ``reason_codes`` tuple is serialized to a list.  The input
    ``result`` is never mutated.

    Args:
        result: The validation result to serialize.

    Returns:
        A JSON-compatible dict with 16 fields.
    """
    return {
        "shell_state": result.shell_state.value,
        "signal_exposure": result.signal_exposure.value,
        "reason_codes": list(result.reason_codes),
        "runtime_version": result.runtime_version,
        "runtime_strategy_state": result.runtime_strategy_state,
        "runtime_strategy_mode": result.runtime_strategy_mode,
        "runtime_signal_action": result.runtime_signal_action,
        "dry_run": result.dry_run,
        "live_trading_enabled": result.live_trading_enabled,
        "real_orders_enabled": result.real_orders_enabled,
        "leverage_enabled": result.leverage_enabled,
        "shorting_enabled": result.shorting_enabled,
        "allow_real_trade_signals": result.allow_real_trade_signals,
        "allow_entry_columns": result.allow_entry_columns,
        "allow_exit_columns": result.allow_exit_columns,
        "version": result.version,
    }


def determine_research_signal(result: ShellValidationResult) -> str:
    """Determine the research signal string from a validation result.

    Args:
        result: The validation result to interpret.

    Returns:
        ``"LONG_RESEARCH"``, ``"SHORT_RESEARCH"``, or ``"NONE"``.
    """
    if result.shell_state is not ShellState.DRY_RUN_READY:
        return "NONE"
    if result.signal_exposure is ShellSignalExposure.EXPOSE_LONG_RESEARCH_METADATA:
        return "LONG_RESEARCH"
    if result.signal_exposure is ShellSignalExposure.EXPOSE_SHORT_RESEARCH_METADATA:
        return "SHORT_RESEARCH"
    return "NONE"


def apply_research_metadata_to_dataframe(
    dataframe: Any,
    result: ShellValidationResult,
) -> Any:
    """Return a **copy** of ``dataframe`` with research-only columns added.

    Never mutates the input dataframe.  Never sets or modifies real
    trade columns (``enter_long``, ``enter_short``, ``exit_long``,
    ``exit_short``).

    Args:
        dataframe: A pandas-like dataframe object with a ``copy()``
            method and item-assignment support.
        result: The validation result driving the metadata values.

    Returns:
        A new dataframe with four research-only columns added.

    Raises:
        ValueError: If the dataframe already contains forbidden trade
            columns.
    """
    # Fail-closed: reject dataframes that already contain real trade columns
    columns = set(getattr(dataframe, "columns", []))
    if columns & _FORBIDDEN_COLUMNS:
        forbidden = sorted(columns & _FORBIDDEN_COLUMNS)
        raise ValueError(
            f"Real trade columns are forbidden in research-only shell: {forbidden}"
        )

    df = dataframe.copy()
    df[RESEARCH_SIGNAL_COLUMN] = determine_research_signal(result)
    df[RESEARCH_REASON_COLUMN] = result.reason_codes[0] if result.reason_codes else "UNKNOWN"
    df[RESEARCH_STATE_COLUMN] = result.shell_state.value
    df[RESEARCH_EXPOSURE_COLUMN] = result.signal_exposure.value
    return df


def assert_no_trade_columns(dataframe: Any) -> None:
    """Raise ``ValueError`` if ``dataframe`` contains real trade columns.

    Args:
        dataframe: A pandas-like dataframe object with a ``columns``
            attribute.

    Raises:
        ValueError: If any of ``enter_long``, ``enter_short``,
            ``exit_long``, or ``exit_short`` are present.
    """
    columns = set(getattr(dataframe, "columns", []))
    forbidden = sorted(columns & _FORBIDDEN_COLUMNS)
    if forbidden:
        raise ValueError(
            f"Real trade columns are forbidden in research-only shell: {forbidden}"
        )


def build_blocked_research_metadata(
    reason: str = "DEFAULT_BLOCKED",
) -> dict[str, object]:
    """Produce fail-closed research metadata for a blocked state.

    Args:
        reason: The blocking reason code or message.  Defaults to
            ``"DEFAULT_BLOCKED"``.

    Returns:
        A dict with four research metadata fields set to blocked values.
    """
    return {
        RESEARCH_SIGNAL_COLUMN: "NONE",
        RESEARCH_REASON_COLUMN: reason,
        RESEARCH_STATE_COLUMN: "BLOCKED",
        RESEARCH_EXPOSURE_COLUMN: "BLOCKED",
    }
