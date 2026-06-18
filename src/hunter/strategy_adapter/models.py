"""Strategy adapter models for Hunter Futures Pro."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Tuple


# Reason code constants — deterministic strings for every blocking or allowed decision
MISSING_STRATEGY_CONTEXT = "MISSING_STRATEGY_CONTEXT"
INVALID_STRATEGY_CONTEXT = "INVALID_STRATEGY_CONTEXT"
STRATEGY_CONTRACT_NOT_DRY_RUN_READY = "STRATEGY_CONTRACT_NOT_DRY_RUN_READY"
STRATEGY_CONTRACT_MODE_BLOCK_ALL = "STRATEGY_CONTRACT_MODE_BLOCK_ALL"
DRY_RUN_DISABLED = "DRY_RUN_DISABLED"
LIVE_TRADING_ENABLED = "LIVE_TRADING_ENABLED"
REAL_ORDERS_ENABLED = "REAL_ORDERS_ENABLED"
LEVERAGE_ENABLED = "LEVERAGE_ENABLED"
SHORTING_ENABLED = "SHORTING_ENABLED"
STALE_STRATEGY_CONTEXT = "STALE_STRATEGY_CONTEXT"
UNSUPPORTED_STRATEGY_MODE = "UNSUPPORTED_STRATEGY_MODE"
LONG_RESEARCH_SIGNAL_ALLOWED = "LONG_RESEARCH_SIGNAL_ALLOWED"
SHORT_RESEARCH_SIGNAL_ALLOWED = "SHORT_RESEARCH_SIGNAL_ALLOWED"
DEFAULT_BLOCK_SIGNAL = "DEFAULT_BLOCK_SIGNAL"
CALCULATION_ERROR = "CALCULATION_ERROR"

REASON_CODES: Tuple[str, ...] = (
    MISSING_STRATEGY_CONTEXT,
    INVALID_STRATEGY_CONTEXT,
    STRATEGY_CONTRACT_NOT_DRY_RUN_READY,
    STRATEGY_CONTRACT_MODE_BLOCK_ALL,
    DRY_RUN_DISABLED,
    LIVE_TRADING_ENABLED,
    REAL_ORDERS_ENABLED,
    LEVERAGE_ENABLED,
    SHORTING_ENABLED,
    STALE_STRATEGY_CONTEXT,
    UNSUPPORTED_STRATEGY_MODE,
    LONG_RESEARCH_SIGNAL_ALLOWED,
    SHORT_RESEARCH_SIGNAL_ALLOWED,
    DEFAULT_BLOCK_SIGNAL,
    CALCULATION_ERROR,
)


class AdapterState(str, Enum):
    """Strategy adapter operational state.

    DISABLED      — Adapter is explicitly disabled (reserved for future use).
    DRY_RUN_READY — Adapter is ready for dry-run research signal gating only.
    BLOCKED       — Adapter is blocked (fail-closed default).
    UNKNOWN       — Adapter state cannot be determined (treated as blocked).
    """

    DISABLED = "DISABLED"
    DRY_RUN_READY = "DRY_RUN_READY"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"


class AdapterMode(str, Enum):
    """Strategy adapter operational mode.

    LONG_RESEARCH_ONLY  — Only long-side research signals are permitted.
    SHORT_RESEARCH_ONLY — Only short-side research signals are permitted.
    BLOCK_ALL           — All adapter signal activity is blocked.
    """

    LONG_RESEARCH_ONLY = "LONG_RESEARCH_ONLY"
    SHORT_RESEARCH_ONLY = "SHORT_RESEARCH_ONLY"
    BLOCK_ALL = "BLOCK_ALL"


class AdapterSignalIntent(str, Enum):
    """Signal intent produced by the strategy adapter.

    ALLOW_LONG_RESEARCH_SIGNAL  — Permit long-side research signal gating.
    ALLOW_SHORT_RESEARCH_SIGNAL — Permit short-side research signal gating.
    BLOCK_SIGNAL                — Block all signals (fail-closed default).
    NO_SIGNAL                   — No signal intent (reserved for future use).
    """

    ALLOW_LONG_RESEARCH_SIGNAL = "ALLOW_LONG_RESEARCH_SIGNAL"
    ALLOW_SHORT_RESEARCH_SIGNAL = "ALLOW_SHORT_RESEARCH_SIGNAL"
    BLOCK_SIGNAL = "BLOCK_SIGNAL"
    NO_SIGNAL = "NO_SIGNAL"


@dataclass(frozen=True)
class AdapterConfig:
    """Configuration for Strategy Adapter."""

    stale_strategy_context_seconds: int = 300
    max_context_age_seconds: int = 300
    dry_run_required: bool = True          # MVP-7: must be True
    live_trading_enabled: bool = False     # MVP-7: must be False
    real_orders_enabled: bool = False      # MVP-7: must be False
    leverage_enabled: bool = False         # MVP-7: must be False
    shorting_enabled: bool = False         # MVP-7: must be False
    adapter_runtime_allowed: bool = False  # MVP-7: must be False
    freqtrade_runtime_allowed: bool = False  # MVP-7: must be False
    strategy_class_allowed: bool = False   # MVP-7: must be False
    entry_signal_allowed: bool = False     # MVP-7: must be False
    exit_signal_allowed: bool = False      # MVP-7: must be False
    order_execution_allowed: bool = False  # MVP-7: must be False
    allow_long_research_signal: bool = True
    allow_short_research_signal: bool = True
    unsupported_mode_action: AdapterSignalIntent = AdapterSignalIntent.BLOCK_SIGNAL

    def __post_init__(self) -> None:
        # Validate positive thresholds
        if self.stale_strategy_context_seconds <= 0:
            raise ValueError(
                f"stale_strategy_context_seconds must be positive, got {self.stale_strategy_context_seconds}"
            )
        if self.max_context_age_seconds <= 0:
            raise ValueError(
                f"max_context_age_seconds must be positive, got {self.max_context_age_seconds}"
            )
        # MVP-7 safety validations — prevent accidental enabling of unsafe features
        if not self.dry_run_required:
            raise ValueError("dry_run_required must be True for MVP-7")
        if self.live_trading_enabled:
            raise ValueError("live_trading_enabled must be False for MVP-7")
        if self.real_orders_enabled:
            raise ValueError("real_orders_enabled must be False for MVP-7")
        if self.leverage_enabled:
            raise ValueError("leverage_enabled must be False for MVP-7")
        if self.shorting_enabled:
            raise ValueError("shorting_enabled must be False for MVP-7")
        if self.adapter_runtime_allowed:
            raise ValueError("adapter_runtime_allowed must be False for MVP-7")
        if self.freqtrade_runtime_allowed:
            raise ValueError("freqtrade_runtime_allowed must be False for MVP-7")
        if self.strategy_class_allowed:
            raise ValueError("strategy_class_allowed must be False for MVP-7")
        if self.entry_signal_allowed:
            raise ValueError("entry_signal_allowed must be False for MVP-7")
        if self.exit_signal_allowed:
            raise ValueError("exit_signal_allowed must be False for MVP-7")
        if self.order_execution_allowed:
            raise ValueError("order_execution_allowed must be False for MVP-7")
        if self.unsupported_mode_action != AdapterSignalIntent.BLOCK_SIGNAL:
            raise ValueError("unsupported_mode_action must be BLOCK_SIGNAL for MVP-7")


@dataclass(frozen=True)
class AdapterInputRefs:
    """References to consumed strategy context and adapter output."""

    strategy_context: str = "data/strategy/current_strategy_context.json"
    adapter_decision: str = "data/strategy_adapter/current_adapter_decision.json"

    def __post_init__(self) -> None:
        if not self.strategy_context or not isinstance(self.strategy_context, str):
            raise ValueError("strategy_context must be a non-empty string")
        if not self.adapter_decision or not isinstance(self.adapter_decision, str):
            raise ValueError("adapter_decision must be a non-empty string")


@dataclass(frozen=True)
class AdapterSafetyFlags:
    """Safety flags for external inspection.

    Every safety-critical field defaults to the most restrictive state.
    """

    dry_run: bool = True
    live_trading_enabled: bool = False
    real_orders_enabled: bool = False
    leverage_enabled: bool = False
    shorting_enabled: bool = False
    adapter_runtime_allowed: bool = False
    freqtrade_runtime_allowed: bool = False
    strategy_class_allowed: bool = False
    entry_signal_allowed: bool = False
    exit_signal_allowed: bool = False
    order_execution_allowed: bool = False
    max_context_age_seconds: int = 300

    def __post_init__(self) -> None:
        # Validate max_context_age_seconds is positive
        if self.max_context_age_seconds <= 0:
            raise ValueError(
                f"max_context_age_seconds must be positive, got {self.max_context_age_seconds}"
            )
        # MVP-7 safety validations
        if not self.dry_run:
            raise ValueError("dry_run must be True for MVP-7")
        if self.live_trading_enabled:
            raise ValueError("live_trading_enabled must be False for MVP-7")
        if self.real_orders_enabled:
            raise ValueError("real_orders_enabled must be False for MVP-7")
        if self.leverage_enabled:
            raise ValueError("leverage_enabled must be False for MVP-7")
        if self.shorting_enabled:
            raise ValueError("shorting_enabled must be False for MVP-7")
        if self.adapter_runtime_allowed:
            raise ValueError("adapter_runtime_allowed must be False for MVP-7")
        if self.freqtrade_runtime_allowed:
            raise ValueError("freqtrade_runtime_allowed must be False for MVP-7")
        if self.strategy_class_allowed:
            raise ValueError("strategy_class_allowed must be False for MVP-7")
        if self.entry_signal_allowed:
            raise ValueError("entry_signal_allowed must be False for MVP-7")
        if self.exit_signal_allowed:
            raise ValueError("exit_signal_allowed must be False for MVP-7")
        if self.order_execution_allowed:
            raise ValueError("order_execution_allowed must be False for MVP-7")

    def to_dict(self) -> Dict[str, bool | int]:
        """Return safety flags as a dict for JSON serialization."""
        return {
            "dry_run": self.dry_run,
            "live_trading_enabled": self.live_trading_enabled,
            "real_orders_enabled": self.real_orders_enabled,
            "leverage_enabled": self.leverage_enabled,
            "shorting_enabled": self.shorting_enabled,
            "adapter_runtime_allowed": self.adapter_runtime_allowed,
            "freqtrade_runtime_allowed": self.freqtrade_runtime_allowed,
            "strategy_class_allowed": self.strategy_class_allowed,
            "entry_signal_allowed": self.entry_signal_allowed,
            "exit_signal_allowed": self.exit_signal_allowed,
            "order_execution_allowed": self.order_execution_allowed,
            "max_context_age_seconds": self.max_context_age_seconds,
        }


@dataclass(frozen=True)
class AdapterDataQuality:
    """Data quality indicators for strategy adapter context."""

    strategy_context_present: bool = False
    strategy_context_valid: bool = False
    strategy_context_stale: bool = True
    reason: str = "NOT_EVALUATED"

    def __post_init__(self) -> None:
        if not self.reason or not isinstance(self.reason, str):
            raise ValueError("reason must be a non-empty string")

    def to_dict(self) -> Dict[str, bool | str]:
        """Return data quality as a dict for JSON serialization."""
        return {
            "strategy_context_present": self.strategy_context_present,
            "strategy_context_valid": self.strategy_context_valid,
            "strategy_context_stale": self.strategy_context_stale,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class AdapterDecisionContext:
    """Adapter decision context produced by the Strategy Adapter layer.

    Every safety-critical field defaults to the most restrictive state.
    Future MVPs must explicitly override flags — they cannot be enabled by accident.
    """

    timestamp: datetime
    status: str  # e.g. "BLOCKED", "DRY_RUN_READY"
    adapter_state: AdapterState
    adapter_mode: AdapterMode
    signal_intent: AdapterSignalIntent
    strategy_contract_state: str  # StrategyContractState value as string
    strategy_contract_mode: str   # StrategyContractMode value as string

    # Safety flags — all default to False / most restrictive
    dry_run: bool = True
    live_trading_enabled: bool = False
    real_orders_enabled: bool = False
    leverage_enabled: bool = False
    shorting_enabled: bool = False
    adapter_runtime_allowed: bool = False
    freqtrade_runtime_allowed: bool = False
    strategy_class_allowed: bool = False
    entry_signal_allowed: bool = False
    exit_signal_allowed: bool = False
    order_execution_allowed: bool = False

    # Audit trail
    reason_codes: Tuple[str, ...] = field(default_factory=tuple)
    input_refs: AdapterInputRefs = field(default_factory=AdapterInputRefs)
    safety_flags: AdapterSafetyFlags = field(default_factory=AdapterSafetyFlags)
    data_quality: AdapterDataQuality = field(default_factory=AdapterDataQuality)
    version: str = "1.0"  # Adapter version for backward-compatible contract evolution

    def __post_init__(self) -> None:
        # Validate timestamp is timezone-aware
        if self.timestamp.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        # Validate status is non-empty
        if not self.status or not isinstance(self.status, str):
            raise ValueError("status must be a non-empty string")
        # Validate dry_run is True
        if not self.dry_run:
            raise ValueError("dry_run must be True for MVP-7")
        # Validate unsafe flags are False
        if self.live_trading_enabled:
            raise ValueError("live_trading_enabled must be False for MVP-7")
        if self.real_orders_enabled:
            raise ValueError("real_orders_enabled must be False for MVP-7")
        if self.leverage_enabled:
            raise ValueError("leverage_enabled must be False for MVP-7")
        if self.shorting_enabled:
            raise ValueError("shorting_enabled must be False for MVP-7")
        if self.adapter_runtime_allowed:
            raise ValueError("adapter_runtime_allowed must be False for MVP-7")
        if self.freqtrade_runtime_allowed:
            raise ValueError("freqtrade_runtime_allowed must be False for MVP-7")
        if self.strategy_class_allowed:
            raise ValueError("strategy_class_allowed must be False for MVP-7")
        if self.entry_signal_allowed:
            raise ValueError("entry_signal_allowed must be False for MVP-7")
        if self.exit_signal_allowed:
            raise ValueError("exit_signal_allowed must be False for MVP-7")
        if self.order_execution_allowed:
            raise ValueError("order_execution_allowed must be False for MVP-7")
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
    ) -> AdapterDecisionContext:
        """Create a fail-closed BLOCKED adapter decision.

        Used when inputs are missing, stale, invalid, or any safety check fails.
        """
        if not reason_codes:
            raise ValueError("reason_codes must be non-empty")
        ts = timestamp or datetime.now(timezone.utc)
        reason = reason_codes[0] if reason_codes else "DEFAULT_BLOCK_SIGNAL"
        return cls(
            timestamp=ts,
            status=status,
            adapter_state=AdapterState.BLOCKED,
            adapter_mode=AdapterMode.BLOCK_ALL,
            signal_intent=AdapterSignalIntent.BLOCK_SIGNAL,
            strategy_contract_state="UNKNOWN",
            strategy_contract_mode="BLOCK_ALL",
            dry_run=True,
            live_trading_enabled=False,
            real_orders_enabled=False,
            leverage_enabled=False,
            shorting_enabled=False,
            adapter_runtime_allowed=False,
            freqtrade_runtime_allowed=False,
            strategy_class_allowed=False,
            entry_signal_allowed=False,
            exit_signal_allowed=False,
            order_execution_allowed=False,
            reason_codes=reason_codes,
            input_refs=AdapterInputRefs(),
            safety_flags=AdapterSafetyFlags(),
            data_quality=AdapterDataQuality(reason=reason),
            version="1.0",
        )

    def is_blocking(self) -> bool:
        """Return True if this adapter decision blocks signal activity."""
        return (
            self.adapter_state in (AdapterState.BLOCKED, AdapterState.UNKNOWN)
            or self.adapter_mode == AdapterMode.BLOCK_ALL
            or self.signal_intent in (AdapterSignalIntent.BLOCK_SIGNAL, AdapterSignalIntent.NO_SIGNAL)
            or self.status == "BLOCKED"
        )
