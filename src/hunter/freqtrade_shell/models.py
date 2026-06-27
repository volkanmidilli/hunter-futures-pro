"""Shell models for Freqtrade Dry-Run Strategy Shell.

No Freqtrade imports, no exchange connections, no trading logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ShellState(str, Enum):
    """Shell lifecycle states."""

    DISABLED = "DISABLED"
    DRY_RUN_READY = "DRY_RUN_READY"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"


class ShellSignalExposure(str, Enum):
    """Research-only signal exposure modes."""

    EXPOSE_LONG_RESEARCH_METADATA = "EXPOSE_LONG_RESEARCH_METADATA"
    EXPOSE_SHORT_RESEARCH_METADATA = "EXPOSE_SHORT_RESEARCH_METADATA"
    NO_RESEARCH_SIGNAL = "NO_RESEARCH_SIGNAL"
    BLOCKED = "BLOCKED"


# ---------------------------------------------------------------------------
# Reason codes
# ---------------------------------------------------------------------------

RUNTIME_JSON_MISSING = "RUNTIME_JSON_MISSING"
RUNTIME_JSON_INVALID = "RUNTIME_JSON_INVALID"
RUNTIME_JSON_VERSION_MISMATCH = "RUNTIME_JSON_VERSION_MISMATCH"
RUNTIME_JSON_INVALID_TIMESTAMP = "RUNTIME_JSON_INVALID_TIMESTAMP"
STALE_RUNTIME_CONTEXT = "STALE_RUNTIME_CONTEXT"
INVALID_STRATEGY_STATE = "INVALID_STRATEGY_STATE"
INVALID_SIGNAL_ACTION = "INVALID_SIGNAL_ACTION"
SIGNAL_BLOCKED = "SIGNAL_BLOCKED"
NOT_DRY_RUN_READY = "NOT_DRY_RUN_READY"
DRY_RUN_DISABLED = "DRY_RUN_DISABLED"
LIVE_TRADING_ENABLED = "LIVE_TRADING_ENABLED"
REAL_ORDERS_ENABLED = "REAL_ORDERS_ENABLED"
LEVERAGE_ENABLED = "LEVERAGE_ENABLED"
SHORTING_ENABLED = "SHORTING_ENABLED"
LONG_RESEARCH_METADATA_EXPOSED = "LONG_RESEARCH_METADATA_EXPOSED"
SHORT_RESEARCH_METADATA_EXPOSED = "SHORT_RESEARCH_METADATA_EXPOSED"
DEFAULT_BLOCKED = "DEFAULT_BLOCKED"
VALIDATION_ERROR = "VALIDATION_ERROR"

REASON_CODES = (
    RUNTIME_JSON_MISSING,
    RUNTIME_JSON_INVALID,
    RUNTIME_JSON_VERSION_MISMATCH,
    RUNTIME_JSON_INVALID_TIMESTAMP,
    STALE_RUNTIME_CONTEXT,
    INVALID_STRATEGY_STATE,
    INVALID_SIGNAL_ACTION,
    SIGNAL_BLOCKED,
    NOT_DRY_RUN_READY,
    DRY_RUN_DISABLED,
    LIVE_TRADING_ENABLED,
    REAL_ORDERS_ENABLED,
    LEVERAGE_ENABLED,
    SHORTING_ENABLED,
    LONG_RESEARCH_METADATA_EXPOSED,
    SHORT_RESEARCH_METADATA_EXPOSED,
    DEFAULT_BLOCKED,
    VALIDATION_ERROR,
)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ShellRuntimeConfig:
    """Shell runtime configuration with fail-closed defaults.

    All unsafe/execution/runtime flags default to False.
    """

    runtime_json_path: str = "data/freqtrade_strategy/current_dry_run_strategy_runtime.json"
    max_runtime_age_seconds: int = 300
    dry_run_required: bool = True
    allow_research_metadata: bool = True
    allow_real_trade_signals: bool = False
    allow_entry_columns: bool = False
    allow_exit_columns: bool = False
    allow_freqtrade_runtime_connection: bool = False
    allow_binance_connection: bool = False
    allow_real_exchange_connection: bool = False
    allow_api_keys: bool = False
    allow_live_trading: bool = False
    allow_real_orders: bool = False
    allow_leverage: bool = False
    allow_shorting: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.runtime_json_path, str) or not self.runtime_json_path:
            raise ValueError("runtime_json_path must be a non-empty string")
        if not isinstance(self.max_runtime_age_seconds, int) or self.max_runtime_age_seconds <= 0:
            raise ValueError("max_runtime_age_seconds must be > 0")
        if self.dry_run_required is not True:
            raise ValueError("dry_run_required must be True")
        unsafe_flags = [
            ("allow_real_trade_signals", self.allow_real_trade_signals),
            ("allow_entry_columns", self.allow_entry_columns),
            ("allow_exit_columns", self.allow_exit_columns),
            ("allow_freqtrade_runtime_connection", self.allow_freqtrade_runtime_connection),
            ("allow_binance_connection", self.allow_binance_connection),
            ("allow_real_exchange_connection", self.allow_real_exchange_connection),
            ("allow_api_keys", self.allow_api_keys),
            ("allow_live_trading", self.allow_live_trading),
            ("allow_real_orders", self.allow_real_orders),
            ("allow_leverage", self.allow_leverage),
            ("allow_shorting", self.allow_shorting),
        ]
        for name, value in unsafe_flags:
            if value is not False:
                raise ValueError(f"{name} must be False")


# ---------------------------------------------------------------------------
# Validation result
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ShellValidationResult:
    """Result of validating a runtime JSON payload.

    Frozen and immutable. Use ``blocked()`` factory for fail-closed defaults.
    """

    timestamp: datetime
    shell_state: ShellState
    signal_exposure: ShellSignalExposure
    reason_codes: tuple[str, ...]
    runtime_json_present: bool
    runtime_json_valid: bool
    runtime_json_stale: bool
    runtime_version: str
    runtime_strategy_state: str
    runtime_strategy_mode: str
    runtime_signal_action: str
    dry_run: bool
    live_trading_enabled: bool
    real_orders_enabled: bool
    leverage_enabled: bool
    shorting_enabled: bool
    allow_real_trade_signals: bool
    allow_entry_columns: bool
    allow_exit_columns: bool
    version: str = "1.0"

    def __post_init__(self) -> None:
        if not isinstance(self.timestamp, datetime) or self.timestamp.tzinfo is None:
            raise ValueError("timestamp must be a timezone-aware datetime")
        if not isinstance(self.reason_codes, tuple) or len(self.reason_codes) == 0:
            raise ValueError("reason_codes must be a non-empty tuple")
        if self.shell_state is ShellState.DRY_RUN_READY:
            allowed = (
                ShellSignalExposure.EXPOSE_LONG_RESEARCH_METADATA,
                ShellSignalExposure.EXPOSE_SHORT_RESEARCH_METADATA,
            )
            if self.signal_exposure not in allowed:
                raise ValueError(
                    "signal_exposure must be EXPOSE_LONG_RESEARCH_METADATA or "
                    "EXPOSE_SHORT_RESEARCH_METADATA when shell_state is DRY_RUN_READY"
                )
        for name in ("allow_real_trade_signals", "allow_entry_columns", "allow_exit_columns"):
            if getattr(self, name) is not False:
                raise ValueError(f"{name} must be False")
        for name in ("live_trading_enabled", "real_orders_enabled", "leverage_enabled", "shorting_enabled"):
            if getattr(self, name) is not False:
                raise ValueError(f"{name} must be False")
        if not isinstance(self.version, str) or not self.version:
            raise ValueError("version must be a non-empty string")

    @classmethod
    def blocked(
        cls,
        reason_codes: tuple[str, ...],
        timestamp: datetime | None = None,
    ) -> "ShellValidationResult":
        """Fail-closed factory: produce a BLOCKED result."""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        return cls(
            timestamp=timestamp,
            shell_state=ShellState.BLOCKED,
            signal_exposure=ShellSignalExposure.BLOCKED,
            reason_codes=reason_codes,
            runtime_json_present=False,
            runtime_json_valid=False,
            runtime_json_stale=True,
            runtime_version="UNKNOWN",
            runtime_strategy_state="UNKNOWN",
            runtime_strategy_mode="BLOCK_ALL",
            runtime_signal_action="BLOCK_SIGNAL",
            dry_run=True,
            live_trading_enabled=False,
            real_orders_enabled=False,
            leverage_enabled=False,
            shorting_enabled=False,
            allow_real_trade_signals=False,
            allow_entry_columns=False,
            allow_exit_columns=False,
            version="1.0",
        )
