"""Execution bridge models for Hunter Futures Pro."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List

from hunter.decision.models import DecisionAction, DecisionState
from hunter.market_state.models import AllowedMode, DataQuality, OutputStatus


class ExecutionState(str, Enum):
    """High-level execution readiness.

    ENABLED      — Execution context is valid and research is permitted.
    BLOCKED      — Execution is blocked (fail-closed default).
    DRY_RUN_ONLY — Only dry-run / simulation is permitted.
    UNKNOWN      — Input missing or invalid.
    """

    ENABLED = "ENABLED"
    BLOCKED = "BLOCKED"
    DRY_RUN_ONLY = "DRY_RUN_ONLY"
    UNKNOWN = "UNKNOWN"


class ExecutionMode(str, Enum):
    """Specific execution mode permitted by the bridge.

    LONG_RESEARCH_ONLY  — Long-side research only, no execution.
    SHORT_RESEARCH_ONLY — Short-side research only, no execution.
    BLOCK_ALL           — All execution and research blocked.
    DRY_RUN_ONLY        — Simulation only, no real execution.
    """

    LONG_RESEARCH_ONLY = "LONG_RESEARCH_ONLY"
    SHORT_RESEARCH_ONLY = "SHORT_RESEARCH_ONLY"
    BLOCK_ALL = "BLOCK_ALL"
    DRY_RUN_ONLY = "DRY_RUN_ONLY"


@dataclass(frozen=True)
class ExecutionBridgeConfig:
    """Configuration for Execution Bridge."""

    stale_decision_minutes: int = 120
    dry_run_required: bool = True          # MVP-4: must be True
    live_trading_enabled: bool = False     # MVP-4: must be False
    exchange_connection_enabled: bool = False  # MVP-4: must be False
    freqtrade_enabled: bool = False        # MVP-4: must be False
    allow_long_research: bool = True
    allow_short_research: bool = True
    manual_review_action: ExecutionMode = ExecutionMode.BLOCK_ALL
    unsupported_action: ExecutionMode = ExecutionMode.BLOCK_ALL

    def __post_init__(self) -> None:
        # Validate stale_decision_minutes is positive
        if self.stale_decision_minutes <= 0:
            raise ValueError(
                f"stale_decision_minutes must be positive, got {self.stale_decision_minutes}"
            )
        # MVP-4 safety validations — prevent accidental enabling of live trading
        if not self.dry_run_required:
            raise ValueError("dry_run_required must be True for MVP-4")
        if self.live_trading_enabled:
            raise ValueError("live_trading_enabled must be False for MVP-4")
        if self.exchange_connection_enabled:
            raise ValueError("exchange_connection_enabled must be False for MVP-4")
        if self.freqtrade_enabled:
            raise ValueError("freqtrade_enabled must be False for MVP-4")


@dataclass(frozen=True)
class ExecutionInputRefs:
    """References to consumed decision output."""

    decision_timestamp: str = ""
    decision_source: str = ""


@dataclass(frozen=True)
class ExecutionSafetyFlags:
    """Safety flags for external inspection.

    Every safety-critical field defaults to the most restrictive state.
    """

    dry_run: bool = True
    live_trading_enabled: bool = False
    exchange_connection_enabled: bool = False
    freqtrade_enabled: bool = False
    human_override_required: bool = False
    max_context_age_seconds: int = 300

    def __post_init__(self) -> None:
        # Validate max_context_age_seconds is positive
        if self.max_context_age_seconds <= 0:
            raise ValueError(
                f"max_context_age_seconds must be positive, got {self.max_context_age_seconds}"
            )
        # MVP-4 safety validations
        if not self.dry_run:
            raise ValueError("dry_run must be True for MVP-4")
        if self.live_trading_enabled:
            raise ValueError("live_trading_enabled must be False for MVP-4")
        if self.exchange_connection_enabled:
            raise ValueError("exchange_connection_enabled must be False for MVP-4")
        if self.freqtrade_enabled:
            raise ValueError("freqtrade_enabled must be False for MVP-4")

    def to_dict(self) -> Dict[str, bool | int]:
        """Return safety flags as a dict for JSON serialization."""
        return {
            "dry_run": self.dry_run,
            "live_trading_enabled": self.live_trading_enabled,
            "exchange_connection_enabled": self.exchange_connection_enabled,
            "freqtrade_enabled": self.freqtrade_enabled,
            "human_override_required": self.human_override_required,
            "max_context_age_seconds": self.max_context_age_seconds,
        }


@dataclass(frozen=True)
class ExecutionContext:
    """Safe execution context produced by the bridge.

    Every safety-critical field defaults to the most restrictive state.
    Future MVPs must explicitly override flags — they cannot be enabled by accident.
    """

    timestamp: datetime
    status: OutputStatus
    execution_state: ExecutionState
    execution_mode: ExecutionMode

    # Derived from DecisionOutput
    decision_state: DecisionState
    decision_action: DecisionAction
    allowed_mode: AllowedMode

    # Safety flags — all default to False / most restrictive
    dry_run: bool = True
    live_trading_enabled: bool = False
    exchange_connection_enabled: bool = False
    freqtrade_enabled: bool = False

    # Audit trail
    reason_codes: List[str] = field(default_factory=list)
    input_refs: ExecutionInputRefs = field(default_factory=ExecutionInputRefs)
    data_quality: DataQuality = field(default_factory=DataQuality)

    # Safety flags dict for external inspection
    safety_flags: ExecutionSafetyFlags = field(default_factory=ExecutionSafetyFlags)
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
        data_quality: DataQuality | None = None,
    ) -> ExecutionContext:
        """Create a fail-closed BLOCKED context.

        Used when inputs are missing, stale, invalid, or any safety check fails.
        """
        return cls(
            timestamp=timestamp or datetime.now(timezone.utc),
            status=OutputStatus.INVALID,
            execution_state=ExecutionState.BLOCKED,
            execution_mode=ExecutionMode.BLOCK_ALL,
            decision_state=DecisionState.BLOCK,
            decision_action=DecisionAction.BLOCK_ALL,
            allowed_mode=AllowedMode.NONE,
            dry_run=True,
            live_trading_enabled=False,
            exchange_connection_enabled=False,
            freqtrade_enabled=False,
            reason_codes=reason_codes or ["EXECUTION_BLOCKED_BY_DEFAULT"],
            data_quality=data_quality or DataQuality(),
            safety_flags=ExecutionSafetyFlags(),
            version="1.0",
        )

    def is_blocking(self) -> bool:
        """Return True if this context blocks execution."""
        return (
            self.execution_state in (ExecutionState.BLOCKED, ExecutionState.UNKNOWN)
            or self.execution_mode == ExecutionMode.BLOCK_ALL
            or self.status == OutputStatus.INVALID
        )
