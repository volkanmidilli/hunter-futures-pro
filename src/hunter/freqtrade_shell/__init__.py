"""Freqtrade Dry-Run Strategy Shell public API exports.

No Freqtrade imports, no exchange connections, no trading logic.
"""

from __future__ import annotations

from hunter.freqtrade_shell.adapter import (
    RESEARCH_EXPOSURE_COLUMN,
    RESEARCH_REASON_COLUMN,
    RESEARCH_SIGNAL_COLUMN,
    RESEARCH_STATE_COLUMN,
    apply_research_metadata_to_dataframe,
    assert_no_trade_columns,
    build_blocked_research_metadata,
    determine_research_signal,
    shell_validation_result_to_metadata,
)
from hunter.freqtrade_shell.models import (
    DEFAULT_BLOCKED,
    DRY_RUN_DISABLED,
    INVALID_SIGNAL_ACTION,
    INVALID_STRATEGY_STATE,
    LEVERAGE_ENABLED,
    LIVE_TRADING_ENABLED,
    LONG_RESEARCH_METADATA_EXPOSED,
    NOT_DRY_RUN_READY,
    REAL_ORDERS_ENABLED,
    REASON_CODES,
    RUNTIME_JSON_INVALID,
    RUNTIME_JSON_INVALID_TIMESTAMP,
    RUNTIME_JSON_MISSING,
    RUNTIME_JSON_VERSION_MISMATCH,
    SHORTING_ENABLED,
    SHORT_RESEARCH_METADATA_EXPOSED,
    SIGNAL_BLOCKED,
    STALE_RUNTIME_CONTEXT,
    VALIDATION_ERROR,
    ShellRuntimeConfig,
    ShellSignalExposure,
    ShellState,
    ShellValidationResult,
)
from hunter.freqtrade_shell.validator import (
    is_runtime_payload_stale,
    map_signal_action_to_exposure,
    parse_runtime_timestamp,
    validate_runtime_payload,
)

__all__ = [
    # Adapter constants
    "RESEARCH_SIGNAL_COLUMN",
    "RESEARCH_REASON_COLUMN",
    "RESEARCH_STATE_COLUMN",
    "RESEARCH_EXPOSURE_COLUMN",
    # Adapter functions
    "shell_validation_result_to_metadata",
    "determine_research_signal",
    "apply_research_metadata_to_dataframe",
    "assert_no_trade_columns",
    "build_blocked_research_metadata",
    # Enums
    "ShellState",
    "ShellSignalExposure",
    # Models
    "ShellRuntimeConfig",
    "ShellValidationResult",
    # Validator
    "validate_runtime_payload",
    "is_runtime_payload_stale",
    "parse_runtime_timestamp",
    "map_signal_action_to_exposure",
    # Reason codes
    "RUNTIME_JSON_MISSING",
    "RUNTIME_JSON_INVALID",
    "RUNTIME_JSON_VERSION_MISMATCH",
    "RUNTIME_JSON_INVALID_TIMESTAMP",
    "STALE_RUNTIME_CONTEXT",
    "INVALID_STRATEGY_STATE",
    "INVALID_SIGNAL_ACTION",
    "SIGNAL_BLOCKED",
    "NOT_DRY_RUN_READY",
    "DRY_RUN_DISABLED",
    "LIVE_TRADING_ENABLED",
    "REAL_ORDERS_ENABLED",
    "LEVERAGE_ENABLED",
    "SHORTING_ENABLED",
    "LONG_RESEARCH_METADATA_EXPOSED",
    "SHORT_RESEARCH_METADATA_EXPOSED",
    "DEFAULT_BLOCKED",
    "VALIDATION_ERROR",
    "REASON_CODES",
]
