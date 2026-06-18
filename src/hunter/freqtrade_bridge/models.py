"""Freqtrade bridge models for Hunter Futures Pro."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List


class FreqtradeBridgeState(str, Enum):
    """Freqtrade bridge operational state.

    DISABLED      — Bridge is explicitly disabled (reserved for future use).
    DRY_RUN_READY — Bridge is ready for dry-run research only.
    BLOCKED       — Bridge is blocked (fail-closed default).
    UNKNOWN       — Bridge state cannot be determined (treated as blocked).
    """

    DISABLED = "DISABLED"
    DRY_RUN_READY = "DRY_RUN_READY"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"


class FreqtradeBridgeMode(str, Enum):
    """Freqtrade bridge operational mode.

    LONG_RESEARCH_ONLY  — Only long-side research is permitted.
    SHORT_RESEARCH_ONLY — Only short-side research is permitted.
    BLOCK_ALL           — All Freqtrade activity is blocked.
    """

    LONG_RESEARCH_ONLY = "LONG_RESEARCH_ONLY"
    SHORT_RESEARCH_ONLY = "SHORT_RESEARCH_ONLY"
    BLOCK_ALL = "BLOCK_ALL"


@dataclass(frozen=True)
class FreqtradeBridgeConfig:
    """Configuration for Freqtrade Bridge."""

    stale_execution_context_seconds: int = 300
    dry_run_required: bool = True          # MVP-5: must be True
    live_trading_enabled: bool = False     # MVP-5: must be False
    exchange_connection_enabled: bool = False  # MVP-5: must be False
    freqtrade_runtime_enabled: bool = False    # MVP-5: must be False
    strategy_enabled: bool = False         # MVP-5: must be False
    real_orders_enabled: bool = False      # MVP-5: must be False
    leverage_enabled: bool = False         # MVP-5: must be False
    shorting_enabled: bool = False         # MVP-5: must be False
    allow_long_research: bool = True
    allow_short_research: bool = True
    unsupported_mode_action: FreqtradeBridgeMode = FreqtradeBridgeMode.BLOCK_ALL

    def __post_init__(self) -> None:
        # Validate stale_execution_context_seconds is positive
        if self.stale_execution_context_seconds <= 0:
            raise ValueError(
                f"stale_execution_context_seconds must be positive, got {self.stale_execution_context_seconds}"
            )
        # MVP-5 safety validations — prevent accidental enabling of unsafe features
        if not self.dry_run_required:
            raise ValueError("dry_run_required must be True for MVP-5")
        if self.live_trading_enabled:
            raise ValueError("live_trading_enabled must be False for MVP-5")
        if self.exchange_connection_enabled:
            raise ValueError("exchange_connection_enabled must be False for MVP-5")
        if self.freqtrade_runtime_enabled:
            raise ValueError("freqtrade_runtime_enabled must be False for MVP-5")
        if self.strategy_enabled:
            raise ValueError("strategy_enabled must be False for MVP-5")
        if self.real_orders_enabled:
            raise ValueError("real_orders_enabled must be False for MVP-5")
        if self.leverage_enabled:
            raise ValueError("leverage_enabled must be False for MVP-5")
        if self.shorting_enabled:
            raise ValueError("shorting_enabled must be False for MVP-5")


@dataclass(frozen=True)
class FreqtradeBridgeInputRefs:
    """References to consumed execution context."""

    execution_context_timestamp: str = ""
    execution_context_version: str = ""


@dataclass(frozen=True)
class FreqtradeBridgeSafetyFlags:
    """Safety flags for external inspection.

    Every safety-critical field defaults to the most restrictive state.
    """

    dry_run: bool = True
    live_trading_enabled: bool = False
    exchange_connection_enabled: bool = False
    freqtrade_runtime_enabled: bool = False
    strategy_enabled: bool = False
    real_orders_enabled: bool = False
    leverage_enabled: bool = False
    shorting_enabled: bool = False
    human_override_required: bool = False
    max_context_age_seconds: int = 300

    def __post_init__(self) -> None:
        # Validate max_context_age_seconds is positive
        if self.max_context_age_seconds <= 0:
            raise ValueError(
                f"max_context_age_seconds must be positive, got {self.max_context_age_seconds}"
            )
        # MVP-5 safety validations
        if not self.dry_run:
            raise ValueError("dry_run must be True for MVP-5")
        if self.live_trading_enabled:
            raise ValueError("live_trading_enabled must be False for MVP-5")
        if self.exchange_connection_enabled:
            raise ValueError("exchange_connection_enabled must be False for MVP-5")
        if self.freqtrade_runtime_enabled:
            raise ValueError("freqtrade_runtime_enabled must be False for MVP-5")
        if self.strategy_enabled:
            raise ValueError("strategy_enabled must be False for MVP-5")
        if self.real_orders_enabled:
            raise ValueError("real_orders_enabled must be False for MVP-5")
        if self.leverage_enabled:
            raise ValueError("leverage_enabled must be False for MVP-5")
        if self.shorting_enabled:
            raise ValueError("shorting_enabled must be False for MVP-5")

    def to_dict(self) -> Dict[str, bool | int]:
        """Return safety flags as a dict for JSON serialization."""
        return {
            "dry_run": self.dry_run,
            "live_trading_enabled": self.live_trading_enabled,
            "exchange_connection_enabled": self.exchange_connection_enabled,
            "freqtrade_runtime_enabled": self.freqtrade_runtime_enabled,
            "strategy_enabled": self.strategy_enabled,
            "real_orders_enabled": self.real_orders_enabled,
            "leverage_enabled": self.leverage_enabled,
            "shorting_enabled": self.shorting_enabled,
            "human_override_required": self.human_override_required,
            "max_context_age_seconds": self.max_context_age_seconds,
        }


@dataclass(frozen=True)
class FreqtradeBridgeDataQuality:
    """Data quality indicators for Freqtrade bridge context."""

    execution_context_fresh: bool = False
    execution_context_valid: bool = False
    validation_errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, bool | List[str]]:
        """Return data quality as a dict for JSON serialization."""
        return {
            "execution_context_fresh": self.execution_context_fresh,
            "execution_context_valid": self.execution_context_valid,
            "validation_errors": list(self.validation_errors),
        }


@dataclass(frozen=True)
class FreqtradeBridgeContext:
    """Freqtrade bridge context produced by the Freqtrade Integration layer.

    Every safety-critical field defaults to the most restrictive state.
    Future MVPs must explicitly override flags — they cannot be enabled by accident.
    """

    timestamp: datetime
    status: str  # "success" or "blocked"
    bridge_state: FreqtradeBridgeState
    bridge_mode: FreqtradeBridgeMode
    execution_state: str  # ExecutionState value as string
    execution_mode: str   # ExecutionMode value as string

    # Safety flags — all default to False / most restrictive
    dry_run: bool = True
    live_trading_enabled: bool = False
    exchange_connection_enabled: bool = False
    freqtrade_runtime_enabled: bool = False
    strategy_enabled: bool = False
    real_orders_enabled: bool = False
    leverage_enabled: bool = False
    shorting_enabled: bool = False

    # Audit trail
    reason_codes: List[str] = field(default_factory=list)
    input_refs: FreqtradeBridgeInputRefs = field(default_factory=FreqtradeBridgeInputRefs)
    data_quality: FreqtradeBridgeDataQuality = field(default_factory=FreqtradeBridgeDataQuality)

    # Safety flags dict for external inspection
    safety_flags: FreqtradeBridgeSafetyFlags = field(default_factory=FreqtradeBridgeSafetyFlags)
    version: str = "1.0"  # Bridge contract version for backward-compatible evolution

    def __post_init__(self) -> None:
        # Validate version is non-empty
        if not self.version:
            raise ValueError("version must be non-empty")

    @classmethod
    def blocked(
        cls,
        timestamp: datetime | None = None,
        reason_codes: List[str] | None = None,
        data_quality: FreqtradeBridgeDataQuality | None = None,
    ) -> FreqtradeBridgeContext:
        """Create a fail-closed BLOCKED context.

        Used when inputs are missing, stale, invalid, or any safety check fails.
        """
        return cls(
            timestamp=timestamp or datetime.now(timezone.utc),
            status="blocked",
            bridge_state=FreqtradeBridgeState.BLOCKED,
            bridge_mode=FreqtradeBridgeMode.BLOCK_ALL,
            execution_state="unknown",
            execution_mode="unknown",
            dry_run=True,
            live_trading_enabled=False,
            exchange_connection_enabled=False,
            freqtrade_runtime_enabled=False,
            strategy_enabled=False,
            real_orders_enabled=False,
            leverage_enabled=False,
            shorting_enabled=False,
            reason_codes=reason_codes or ["FREQTRADE_BRIDGE_BLOCKED_BY_DEFAULT"],
            data_quality=data_quality or FreqtradeBridgeDataQuality(),
            safety_flags=FreqtradeBridgeSafetyFlags(),
            version="1.0",
        )

    def is_blocking(self) -> bool:
        """Return True if this context blocks Freqtrade activity."""
        return (
            self.bridge_state in (FreqtradeBridgeState.BLOCKED, FreqtradeBridgeState.UNKNOWN)
            or self.bridge_mode == FreqtradeBridgeMode.BLOCK_ALL
            or self.status == "blocked"
        )
