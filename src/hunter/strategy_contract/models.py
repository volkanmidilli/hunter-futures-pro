"""Strategy contract models for Hunter Futures Pro."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Tuple


# Reason code constants — deterministic strings for every blocking or allowed decision
MISSING_BRIDGE_CONTEXT = "MISSING_BRIDGE_CONTEXT"
INVALID_BRIDGE_CONTEXT = "INVALID_BRIDGE_CONTEXT"
BRIDGE_NOT_DRY_RUN_READY = "BRIDGE_NOT_DRY_RUN_READY"
BRIDGE_MODE_BLOCK_ALL = "BRIDGE_MODE_BLOCK_ALL"
DRY_RUN_DISABLED = "DRY_RUN_DISABLED"
LIVE_TRADING_ENABLED = "LIVE_TRADING_ENABLED"
REAL_ORDERS_ENABLED = "REAL_ORDERS_ENABLED"
LEVERAGE_ENABLED = "LEVERAGE_ENABLED"
SHORTING_ENABLED = "SHORTING_ENABLED"
STALE_BRIDGE_CONTEXT = "STALE_BRIDGE_CONTEXT"
UNSUPPORTED_BRIDGE_MODE = "UNSUPPORTED_BRIDGE_MODE"
LONG_RESEARCH_ALLOWED = "LONG_RESEARCH_ALLOWED"
SHORT_RESEARCH_ALLOWED = "SHORT_RESEARCH_ALLOWED"
DEFAULT_BLOCK_ALL = "DEFAULT_BLOCK_ALL"
CALCULATION_ERROR = "CALCULATION_ERROR"

REASON_CODES: Tuple[str, ...] = (
    MISSING_BRIDGE_CONTEXT,
    INVALID_BRIDGE_CONTEXT,
    BRIDGE_NOT_DRY_RUN_READY,
    BRIDGE_MODE_BLOCK_ALL,
    DRY_RUN_DISABLED,
    LIVE_TRADING_ENABLED,
    REAL_ORDERS_ENABLED,
    LEVERAGE_ENABLED,
    SHORTING_ENABLED,
    STALE_BRIDGE_CONTEXT,
    UNSUPPORTED_BRIDGE_MODE,
    LONG_RESEARCH_ALLOWED,
    SHORT_RESEARCH_ALLOWED,
    DEFAULT_BLOCK_ALL,
    CALCULATION_ERROR,
)


class StrategyContractState(str, Enum):
    """Strategy contract operational state.

    DISABLED      — Contract is explicitly disabled (reserved for future use).
    DRY_RUN_READY — Contract is ready for dry-run research only.
    BLOCKED       — Contract is blocked (fail-closed default).
    UNKNOWN       — Contract state cannot be determined (treated as blocked).
    """

    DISABLED = "DISABLED"
    DRY_RUN_READY = "DRY_RUN_READY"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"


class StrategyContractMode(str, Enum):
    """Strategy contract operational mode.

    LONG_RESEARCH_ONLY  — Only long-side research is permitted.
    SHORT_RESEARCH_ONLY — Only short-side research is permitted.
    BLOCK_ALL           — All strategy activity is blocked.
    """

    LONG_RESEARCH_ONLY = "LONG_RESEARCH_ONLY"
    SHORT_RESEARCH_ONLY = "SHORT_RESEARCH_ONLY"
    BLOCK_ALL = "BLOCK_ALL"


@dataclass(frozen=True)
class StrategyContractConfig:
    """Configuration for Strategy Contract."""

    stale_bridge_context_seconds: int = 300
    max_context_age_seconds: int = 300
    dry_run_required: bool = True          # MVP-6: must be True
    live_trading_enabled: bool = False     # MVP-6: must be False
    real_orders_enabled: bool = False      # MVP-6: must be False
    leverage_enabled: bool = False         # MVP-6: must be False
    shorting_enabled: bool = False         # MVP-6: must be False
    strategy_runtime_allowed: bool = False  # MVP-6: must be False
    entry_signals_allowed: bool = False    # MVP-6: must be False
    exit_signals_allowed: bool = False     # MVP-6: must be False
    allow_long_research: bool = True
    allow_short_research: bool = True
    unsupported_mode_action: StrategyContractMode = StrategyContractMode.BLOCK_ALL

    def __post_init__(self) -> None:
        # Validate positive thresholds
        if self.stale_bridge_context_seconds <= 0:
            raise ValueError(
                f"stale_bridge_context_seconds must be positive, got {self.stale_bridge_context_seconds}"
            )
        if self.max_context_age_seconds <= 0:
            raise ValueError(
                f"max_context_age_seconds must be positive, got {self.max_context_age_seconds}"
            )
        # MVP-6 safety validations — prevent accidental enabling of unsafe features
        if not self.dry_run_required:
            raise ValueError("dry_run_required must be True for MVP-6")
        if self.live_trading_enabled:
            raise ValueError("live_trading_enabled must be False for MVP-6")
        if self.real_orders_enabled:
            raise ValueError("real_orders_enabled must be False for MVP-6")
        if self.leverage_enabled:
            raise ValueError("leverage_enabled must be False for MVP-6")
        if self.shorting_enabled:
            raise ValueError("shorting_enabled must be False for MVP-6")
        if self.strategy_runtime_allowed:
            raise ValueError("strategy_runtime_allowed must be False for MVP-6")
        if self.entry_signals_allowed:
            raise ValueError("entry_signals_allowed must be False for MVP-6")
        if self.exit_signals_allowed:
            raise ValueError("exit_signals_allowed must be False for MVP-6")
        if self.unsupported_mode_action != StrategyContractMode.BLOCK_ALL:
            raise ValueError("unsupported_mode_action must be BLOCK_ALL for MVP-6")


@dataclass(frozen=True)
class StrategyContractInputRefs:
    """References to consumed Freqtrade bridge context and strategy output."""

    freqtrade_bridge_context: str = "data/freqtrade/current_freqtrade_context.json"
    strategy_context: str = "data/strategy/current_strategy_context.json"

    def __post_init__(self) -> None:
        if not self.freqtrade_bridge_context or not isinstance(self.freqtrade_bridge_context, str):
            raise ValueError("freqtrade_bridge_context must be a non-empty string")
        if not self.strategy_context or not isinstance(self.strategy_context, str):
            raise ValueError("strategy_context must be a non-empty string")


@dataclass(frozen=True)
class StrategyContractSafetyFlags:
    """Safety flags for external inspection.

    Every safety-critical field defaults to the most restrictive state.
    """

    dry_run: bool = True
    live_trading_enabled: bool = False
    real_orders_enabled: bool = False
    leverage_enabled: bool = False
    shorting_enabled: bool = False
    strategy_runtime_allowed: bool = False
    entry_signals_allowed: bool = False
    exit_signals_allowed: bool = False
    max_context_age_seconds: int = 300

    def __post_init__(self) -> None:
        # Validate max_context_age_seconds is positive
        if self.max_context_age_seconds <= 0:
            raise ValueError(
                f"max_context_age_seconds must be positive, got {self.max_context_age_seconds}"
            )
        # MVP-6 safety validations
        if not self.dry_run:
            raise ValueError("dry_run must be True for MVP-6")
        if self.live_trading_enabled:
            raise ValueError("live_trading_enabled must be False for MVP-6")
        if self.real_orders_enabled:
            raise ValueError("real_orders_enabled must be False for MVP-6")
        if self.leverage_enabled:
            raise ValueError("leverage_enabled must be False for MVP-6")
        if self.shorting_enabled:
            raise ValueError("shorting_enabled must be False for MVP-6")
        if self.strategy_runtime_allowed:
            raise ValueError("strategy_runtime_allowed must be False for MVP-6")
        if self.entry_signals_allowed:
            raise ValueError("entry_signals_allowed must be False for MVP-6")
        if self.exit_signals_allowed:
            raise ValueError("exit_signals_allowed must be False for MVP-6")

    def to_dict(self) -> Dict[str, bool | int]:
        """Return safety flags as a dict for JSON serialization."""
        return {
            "dry_run": self.dry_run,
            "live_trading_enabled": self.live_trading_enabled,
            "real_orders_enabled": self.real_orders_enabled,
            "leverage_enabled": self.leverage_enabled,
            "shorting_enabled": self.shorting_enabled,
            "strategy_runtime_allowed": self.strategy_runtime_allowed,
            "entry_signals_allowed": self.entry_signals_allowed,
            "exit_signals_allowed": self.exit_signals_allowed,
            "max_context_age_seconds": self.max_context_age_seconds,
        }


@dataclass(frozen=True)
class StrategyContractDataQuality:
    """Data quality indicators for strategy contract context."""

    bridge_context_present: bool = False
    bridge_context_valid: bool = False
    bridge_context_stale: bool = True
    reason: str = "NOT_EVALUATED"

    def __post_init__(self) -> None:
        if not self.reason or not isinstance(self.reason, str):
            raise ValueError("reason must be a non-empty string")

    def to_dict(self) -> Dict[str, bool | str]:
        """Return data quality as a dict for JSON serialization."""
        return {
            "bridge_context_present": self.bridge_context_present,
            "bridge_context_valid": self.bridge_context_valid,
            "bridge_context_stale": self.bridge_context_stale,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class StrategyContext:
    """Strategy context produced by the Strategy Contract layer.

    Every safety-critical field defaults to the most restrictive state.
    Future MVPs must explicitly override flags — they cannot be enabled by accident.
    """

    timestamp: datetime
    status: str  # e.g. "BLOCKED", "DRY_RUN_READY"
    contract_state: StrategyContractState
    contract_mode: StrategyContractMode
    bridge_state: str  # FreqtradeBridgeState value as string
    bridge_mode: str   # FreqtradeBridgeMode value as string

    # Safety flags — all default to False / most restrictive
    dry_run: bool = True
    live_trading_enabled: bool = False
    real_orders_enabled: bool = False
    leverage_enabled: bool = False
    shorting_enabled: bool = False
    strategy_runtime_allowed: bool = False
    entry_signals_allowed: bool = False
    exit_signals_allowed: bool = False

    # Audit trail
    reason_codes: Tuple[str, ...] = field(default_factory=tuple)
    input_refs: StrategyContractInputRefs = field(default_factory=StrategyContractInputRefs)
    safety_flags: StrategyContractSafetyFlags = field(default_factory=StrategyContractSafetyFlags)
    data_quality: StrategyContractDataQuality = field(default_factory=StrategyContractDataQuality)
    version: str = "1.0"  # Contract version for backward-compatible evolution

    def __post_init__(self) -> None:
        # Validate timestamp is timezone-aware
        if self.timestamp.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        # Validate status is non-empty
        if not self.status or not isinstance(self.status, str):
            raise ValueError("status must be a non-empty string")
        # Validate dry_run is True
        if not self.dry_run:
            raise ValueError("dry_run must be True for MVP-6")
        # Validate unsafe flags are False
        if self.live_trading_enabled:
            raise ValueError("live_trading_enabled must be False for MVP-6")
        if self.real_orders_enabled:
            raise ValueError("real_orders_enabled must be False for MVP-6")
        if self.leverage_enabled:
            raise ValueError("leverage_enabled must be False for MVP-6")
        if self.shorting_enabled:
            raise ValueError("shorting_enabled must be False for MVP-6")
        if self.strategy_runtime_allowed:
            raise ValueError("strategy_runtime_allowed must be False for MVP-6")
        if self.entry_signals_allowed:
            raise ValueError("entry_signals_allowed must be False for MVP-6")
        if self.exit_signals_allowed:
            raise ValueError("exit_signals_allowed must be False for MVP-6")
        # Validate reason_codes is non-empty
        if not self.reason_codes:
            raise ValueError("reason_codes must be non-empty")
        # Validate version is non-empty
        if not self.version or not isinstance(self.version, str):
            raise ValueError("version must be a non-empty string")

    @classmethod
    def blocked(
        cls,
        reason_codes: Tuple[str, ...],
        status: str = "BLOCKED",
        timestamp: datetime | None = None,
    ) -> StrategyContext:
        """Create a fail-closed BLOCKED context.

        Used when inputs are missing, stale, invalid, or any safety check fails.
        """
        if not reason_codes:
            raise ValueError("reason_codes must be non-empty")
        ts = timestamp or datetime.now(timezone.utc)
        reason = reason_codes[0] if reason_codes else "DEFAULT_BLOCK_ALL"
        return cls(
            timestamp=ts,
            status=status,
            contract_state=StrategyContractState.BLOCKED,
            contract_mode=StrategyContractMode.BLOCK_ALL,
            bridge_state="UNKNOWN",
            bridge_mode="BLOCK_ALL",
            dry_run=True,
            live_trading_enabled=False,
            real_orders_enabled=False,
            leverage_enabled=False,
            shorting_enabled=False,
            strategy_runtime_allowed=False,
            entry_signals_allowed=False,
            exit_signals_allowed=False,
            reason_codes=reason_codes,
            input_refs=StrategyContractInputRefs(),
            safety_flags=StrategyContractSafetyFlags(),
            data_quality=StrategyContractDataQuality(reason=reason),
            version="1.0",
        )

    def is_blocking(self) -> bool:
        """Return True if this context blocks strategy activity."""
        return (
            self.contract_state in (StrategyContractState.BLOCKED, StrategyContractState.UNKNOWN)
            or self.contract_mode == StrategyContractMode.BLOCK_ALL
            or self.status == "BLOCKED"
        )
