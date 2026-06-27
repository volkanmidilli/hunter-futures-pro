"""Dry-run strategy models for Hunter Futures Pro."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Tuple


# Reason code constants — deterministic strings for every blocking or allowed decision
MISSING_ADAPTER_DECISION_CONTEXT = "MISSING_ADAPTER_DECISION_CONTEXT"
INVALID_ADAPTER_DECISION_CONTEXT = "INVALID_ADAPTER_DECISION_CONTEXT"
ADAPTER_NOT_DRY_RUN_READY = "ADAPTER_NOT_DRY_RUN_READY"
ADAPTER_MODE_BLOCK_ALL = "ADAPTER_MODE_BLOCK_ALL"
ADAPTER_SIGNAL_BLOCKED = "ADAPTER_SIGNAL_BLOCKED"
DRY_RUN_DISABLED = "DRY_RUN_DISABLED"
LIVE_TRADING_ENABLED = "LIVE_TRADING_ENABLED"
REAL_ORDERS_ENABLED = "REAL_ORDERS_ENABLED"
LEVERAGE_ENABLED = "LEVERAGE_ENABLED"
SHORTING_ENABLED = "SHORTING_ENABLED"
STALE_ADAPTER_DECISION_CONTEXT = "STALE_ADAPTER_DECISION_CONTEXT"
UNSUPPORTED_ADAPTER_MODE = "UNSUPPORTED_ADAPTER_MODE"
UNSUPPORTED_ADAPTER_SIGNAL_INTENT = "UNSUPPORTED_ADAPTER_SIGNAL_INTENT"
LONG_RESEARCH_SIGNAL_EXPOSED = "LONG_RESEARCH_SIGNAL_EXPOSED"
SHORT_RESEARCH_SIGNAL_EXPOSED = "SHORT_RESEARCH_SIGNAL_EXPOSED"
DEFAULT_BLOCK_SIGNAL = "DEFAULT_BLOCK_SIGNAL"
CALCULATION_ERROR = "CALCULATION_ERROR"

REASON_CODES: Tuple[str, ...] = (
    MISSING_ADAPTER_DECISION_CONTEXT,
    INVALID_ADAPTER_DECISION_CONTEXT,
    ADAPTER_NOT_DRY_RUN_READY,
    ADAPTER_MODE_BLOCK_ALL,
    ADAPTER_SIGNAL_BLOCKED,
    DRY_RUN_DISABLED,
    LIVE_TRADING_ENABLED,
    REAL_ORDERS_ENABLED,
    LEVERAGE_ENABLED,
    SHORTING_ENABLED,
    STALE_ADAPTER_DECISION_CONTEXT,
    UNSUPPORTED_ADAPTER_MODE,
    UNSUPPORTED_ADAPTER_SIGNAL_INTENT,
    LONG_RESEARCH_SIGNAL_EXPOSED,
    SHORT_RESEARCH_SIGNAL_EXPOSED,
    DEFAULT_BLOCK_SIGNAL,
    CALCULATION_ERROR,
)


class DryRunStrategyState(str, Enum):
    """Dry-run strategy operational state.

    DISABLED      — Strategy is explicitly disabled (reserved for future use).
    DRY_RUN_READY — Strategy is ready for dry-run research signal exposure only.
    BLOCKED       — Strategy is blocked (fail-closed default).
    UNKNOWN       — Strategy state cannot be determined (treated as blocked).
    """

    DISABLED = "DISABLED"
    DRY_RUN_READY = "DRY_RUN_READY"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"


class DryRunStrategyMode(str, Enum):
    """Dry-run strategy operational mode.

    LONG_RESEARCH_ONLY  — Only long-side research signals are exposed.
    SHORT_RESEARCH_ONLY — Only short-side research signals are exposed.
    BLOCK_ALL           — All strategy signal activity is blocked.
    """

    LONG_RESEARCH_ONLY = "LONG_RESEARCH_ONLY"
    SHORT_RESEARCH_ONLY = "SHORT_RESEARCH_ONLY"
    BLOCK_ALL = "BLOCK_ALL"


class DryRunSignalAction(str, Enum):
    """Signal action exposed by the dry-run strategy.

    EXPOSE_LONG_RESEARCH_SIGNAL  — Expose long-side research signal.
    EXPOSE_SHORT_RESEARCH_SIGNAL — Expose short-side research signal.
    BLOCK_SIGNAL                 — Block all signals (fail-closed default).
    NO_SIGNAL                    — No signal action (reserved for future use).
    """

    EXPOSE_LONG_RESEARCH_SIGNAL = "EXPOSE_LONG_RESEARCH_SIGNAL"
    EXPOSE_SHORT_RESEARCH_SIGNAL = "EXPOSE_SHORT_RESEARCH_SIGNAL"
    BLOCK_SIGNAL = "BLOCK_SIGNAL"
    NO_SIGNAL = "NO_SIGNAL"


@dataclass(frozen=True)
class DryRunStrategyConfig:
    """Configuration for Dry-Run Strategy."""

    stale_adapter_decision_seconds: int = 300
    max_context_age_seconds: int = 300
    dry_run_required: bool = True          # MVP-8: must be True
    live_trading_enabled: bool = False     # MVP-8: must be False
    real_orders_enabled: bool = False      # MVP-8: must be False
    leverage_enabled: bool = False         # MVP-8: must be False
    shorting_enabled: bool = False         # MVP-8: must be False
    freqtrade_runtime_allowed: bool = False  # MVP-8: must be False
    strategy_class_allowed: bool = False   # MVP-8: must be False
    populate_indicators_allowed: bool = False  # MVP-8: must be False
    populate_entry_trend_allowed: bool = False  # MVP-8: must be False
    populate_exit_trend_allowed: bool = False   # MVP-8: must be False
    order_execution_allowed: bool = False  # MVP-8: must be False
    expose_long_research_signal: bool = True
    expose_short_research_signal: bool = True
    unsupported_signal_action: DryRunSignalAction = DryRunSignalAction.BLOCK_SIGNAL

    def __post_init__(self) -> None:
        # Validate positive thresholds
        if self.stale_adapter_decision_seconds <= 0:
            raise ValueError(
                f"stale_adapter_decision_seconds must be positive, got {self.stale_adapter_decision_seconds}"
            )
        if self.max_context_age_seconds <= 0:
            raise ValueError(
                f"max_context_age_seconds must be positive, got {self.max_context_age_seconds}"
            )
        # MVP-8 safety validations — prevent accidental enabling of unsafe features
        if not self.dry_run_required:
            raise ValueError("dry_run_required must be True for MVP-8")
        if self.live_trading_enabled:
            raise ValueError("live_trading_enabled must be False for MVP-8")
        if self.real_orders_enabled:
            raise ValueError("real_orders_enabled must be False for MVP-8")
        if self.leverage_enabled:
            raise ValueError("leverage_enabled must be False for MVP-8")
        if self.shorting_enabled:
            raise ValueError("shorting_enabled must be False for MVP-8")
        if self.freqtrade_runtime_allowed:
            raise ValueError("freqtrade_runtime_allowed must be False for MVP-8")
        if self.strategy_class_allowed:
            raise ValueError("strategy_class_allowed must be False for MVP-8")
        if self.populate_indicators_allowed:
            raise ValueError("populate_indicators_allowed must be False for MVP-8")
        if self.populate_entry_trend_allowed:
            raise ValueError("populate_entry_trend_allowed must be False for MVP-8")
        if self.populate_exit_trend_allowed:
            raise ValueError("populate_exit_trend_allowed must be False for MVP-8")
        if self.order_execution_allowed:
            raise ValueError("order_execution_allowed must be False for MVP-8")
        if self.unsupported_signal_action != DryRunSignalAction.BLOCK_SIGNAL:
            raise ValueError("unsupported_signal_action must be BLOCK_SIGNAL for MVP-8")


@dataclass(frozen=True)
class DryRunStrategyInputRefs:
    """References to consumed adapter decision and dry-run strategy output."""

    adapter_decision: str = "data/strategy_adapter/current_adapter_decision.json"
    dry_run_strategy_runtime: str = "data/freqtrade_strategy/current_dry_run_strategy_runtime.json"

    def __post_init__(self) -> None:
        if not self.adapter_decision or not isinstance(self.adapter_decision, str):
            raise ValueError("adapter_decision must be a non-empty string")
        if not self.dry_run_strategy_runtime or not isinstance(self.dry_run_strategy_runtime, str):
            raise ValueError("dry_run_strategy_runtime must be a non-empty string")


@dataclass(frozen=True)
class DryRunStrategySafetyFlags:
    """Safety flags for external inspection.

    Every safety-critical field defaults to the most restrictive state.
    """

    dry_run: bool = True
    live_trading_enabled: bool = False
    real_orders_enabled: bool = False
    leverage_enabled: bool = False
    shorting_enabled: bool = False
    freqtrade_runtime_allowed: bool = False
    strategy_class_allowed: bool = False
    populate_indicators_allowed: bool = False
    populate_entry_trend_allowed: bool = False
    populate_exit_trend_allowed: bool = False
    order_execution_allowed: bool = False
    max_context_age_seconds: int = 300

    def __post_init__(self) -> None:
        # Validate max_context_age_seconds is positive
        if self.max_context_age_seconds <= 0:
            raise ValueError(
                f"max_context_age_seconds must be positive, got {self.max_context_age_seconds}"
            )
        # MVP-8 safety validations
        if not self.dry_run:
            raise ValueError("dry_run must be True for MVP-8")
        if self.live_trading_enabled:
            raise ValueError("live_trading_enabled must be False for MVP-8")
        if self.real_orders_enabled:
            raise ValueError("real_orders_enabled must be False for MVP-8")
        if self.leverage_enabled:
            raise ValueError("leverage_enabled must be False for MVP-8")
        if self.shorting_enabled:
            raise ValueError("shorting_enabled must be False for MVP-8")
        if self.freqtrade_runtime_allowed:
            raise ValueError("freqtrade_runtime_allowed must be False for MVP-8")
        if self.strategy_class_allowed:
            raise ValueError("strategy_class_allowed must be False for MVP-8")
        if self.populate_indicators_allowed:
            raise ValueError("populate_indicators_allowed must be False for MVP-8")
        if self.populate_entry_trend_allowed:
            raise ValueError("populate_entry_trend_allowed must be False for MVP-8")
        if self.populate_exit_trend_allowed:
            raise ValueError("populate_exit_trend_allowed must be False for MVP-8")
        if self.order_execution_allowed:
            raise ValueError("order_execution_allowed must be False for MVP-8")

    def to_dict(self) -> Dict[str, bool | int]:
        """Return safety flags as a dict for JSON serialization."""
        return {
            "dry_run": self.dry_run,
            "live_trading_enabled": self.live_trading_enabled,
            "real_orders_enabled": self.real_orders_enabled,
            "leverage_enabled": self.leverage_enabled,
            "shorting_enabled": self.shorting_enabled,
            "freqtrade_runtime_allowed": self.freqtrade_runtime_allowed,
            "strategy_class_allowed": self.strategy_class_allowed,
            "populate_indicators_allowed": self.populate_indicators_allowed,
            "populate_entry_trend_allowed": self.populate_entry_trend_allowed,
            "populate_exit_trend_allowed": self.populate_exit_trend_allowed,
            "order_execution_allowed": self.order_execution_allowed,
            "max_context_age_seconds": self.max_context_age_seconds,
        }


@dataclass(frozen=True)
class DryRunStrategyDataQuality:
    """Data quality indicators for dry-run strategy context."""

    adapter_decision_present: bool = False
    adapter_decision_valid: bool = False
    adapter_decision_stale: bool = True
    reason: str = "NOT_EVALUATED"

    def __post_init__(self) -> None:
        if not self.reason or not isinstance(self.reason, str):
            raise ValueError("reason must be a non-empty string")

    def to_dict(self) -> Dict[str, bool | str]:
        """Return data quality as a dict for JSON serialization."""
        return {
            "adapter_decision_present": self.adapter_decision_present,
            "adapter_decision_valid": self.adapter_decision_valid,
            "adapter_decision_stale": self.adapter_decision_stale,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class DryRunStrategyRuntimeContext:
    """Dry-run strategy runtime context produced by the Dry-Run Strategy layer.

    Every safety-critical field defaults to the most restrictive state.
    Future MVPs must explicitly override flags — they cannot be enabled by accident.
    """

    timestamp: datetime
    status: str  # e.g. "BLOCKED", "DRY_RUN_READY"
    strategy_state: DryRunStrategyState
    strategy_mode: DryRunStrategyMode
    signal_action: DryRunSignalAction
    adapter_state: str  # AdapterState value as string
    adapter_mode: str   # AdapterMode value as string
    adapter_signal_intent: str  # AdapterSignalIntent value as string

    # Safety flags — all default to False / most restrictive
    dry_run: bool = True
    live_trading_enabled: bool = False
    real_orders_enabled: bool = False
    leverage_enabled: bool = False
    shorting_enabled: bool = False
    freqtrade_runtime_allowed: bool = False
    strategy_class_allowed: bool = False
    populate_indicators_allowed: bool = False
    populate_entry_trend_allowed: bool = False
    populate_exit_trend_allowed: bool = False
    order_execution_allowed: bool = False

    # Audit trail
    reason_codes: Tuple[str, ...] = field(default_factory=tuple)
    input_refs: DryRunStrategyInputRefs = field(default_factory=DryRunStrategyInputRefs)
    safety_flags: DryRunStrategySafetyFlags = field(default_factory=DryRunStrategySafetyFlags)
    data_quality: DryRunStrategyDataQuality = field(default_factory=DryRunStrategyDataQuality)
    version: str = "1.0"  # Strategy version for backward-compatible contract evolution

    def __post_init__(self) -> None:
        # Validate timestamp is timezone-aware
        if self.timestamp.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        # Validate status is non-empty
        if not self.status or not isinstance(self.status, str):
            raise ValueError("status must be a non-empty string")
        # Validate dry_run is True
        if not self.dry_run:
            raise ValueError("dry_run must be True for MVP-8")
        # Validate unsafe flags are False
        if self.live_trading_enabled:
            raise ValueError("live_trading_enabled must be False for MVP-8")
        if self.real_orders_enabled:
            raise ValueError("real_orders_enabled must be False for MVP-8")
        if self.leverage_enabled:
            raise ValueError("leverage_enabled must be False for MVP-8")
        if self.shorting_enabled:
            raise ValueError("shorting_enabled must be False for MVP-8")
        if self.freqtrade_runtime_allowed:
            raise ValueError("freqtrade_runtime_allowed must be False for MVP-8")
        if self.strategy_class_allowed:
            raise ValueError("strategy_class_allowed must be False for MVP-8")
        if self.populate_indicators_allowed:
            raise ValueError("populate_indicators_allowed must be False for MVP-8")
        if self.populate_entry_trend_allowed:
            raise ValueError("populate_entry_trend_allowed must be False for MVP-8")
        if self.populate_exit_trend_allowed:
            raise ValueError("populate_exit_trend_allowed must be False for MVP-8")
        if self.order_execution_allowed:
            raise ValueError("order_execution_allowed must be False for MVP-8")
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
    ) -> DryRunStrategyRuntimeContext:
        """Create a fail-closed BLOCKED dry-run strategy runtime context.

        Used when inputs are missing, stale, invalid, or any safety check fails.
        """
        if not reason_codes:
            raise ValueError("reason_codes must be non-empty")
        ts = timestamp or datetime.now(timezone.utc)
        reason = reason_codes[0] if reason_codes else "DEFAULT_BLOCK_SIGNAL"
        return cls(
            timestamp=ts,
            status=status,
            strategy_state=DryRunStrategyState.BLOCKED,
            strategy_mode=DryRunStrategyMode.BLOCK_ALL,
            signal_action=DryRunSignalAction.BLOCK_SIGNAL,
            adapter_state="UNKNOWN",
            adapter_mode="BLOCK_ALL",
            adapter_signal_intent="BLOCK_SIGNAL",
            dry_run=True,
            live_trading_enabled=False,
            real_orders_enabled=False,
            leverage_enabled=False,
            shorting_enabled=False,
            freqtrade_runtime_allowed=False,
            strategy_class_allowed=False,
            populate_indicators_allowed=False,
            populate_entry_trend_allowed=False,
            populate_exit_trend_allowed=False,
            order_execution_allowed=False,
            reason_codes=reason_codes,
            input_refs=DryRunStrategyInputRefs(),
            safety_flags=DryRunStrategySafetyFlags(),
            data_quality=DryRunStrategyDataQuality(reason=reason),
            version="1.0",
        )

    def is_blocking(self) -> bool:
        """Return True if this strategy runtime context blocks signal activity."""
        return (
            self.strategy_state in (DryRunStrategyState.BLOCKED, DryRunStrategyState.UNKNOWN)
            or self.strategy_mode == DryRunStrategyMode.BLOCK_ALL
            or self.signal_action in (DryRunSignalAction.BLOCK_SIGNAL, DryRunSignalAction.NO_SIGNAL)
            or self.status == "BLOCKED"
        )
