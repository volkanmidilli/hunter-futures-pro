"""Decision layer models for Hunter Futures Pro."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List

from hunter.market_state.models import (
    AllowedMode,
    DataQuality,
    OutputStatus,
    RegimeState,
    RiskState,
)


class DecisionState(str, Enum):
    """High-level decision outcome.

    ALLOW  — Research/execution is permitted.
    BLOCK  — Research/execution is blocked (fail-closed default).
    REVIEW — Manual review required. Reserved for future workflows;
             MVP-3 default config never uses REVIEW automatically.
    UNKNOWN — Input data is missing or invalid.
    """

    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    REVIEW = "REVIEW"
    UNKNOWN = "UNKNOWN"


class DecisionAction(str, Enum):
    """Specific action to take based on decision."""

    ENABLE_LONG_ONLY_RESEARCH = "ENABLE_LONG_ONLY_RESEARCH"
    ENABLE_SHORT_ONLY_RESEARCH = "ENABLE_SHORT_ONLY_RESEARCH"
    BLOCK_ALL = "BLOCK_ALL"
    MANUAL_REVIEW = "MANUAL_REVIEW"


@dataclass(frozen=True)
class DecisionConfig:
    """Configuration for Decision Layer."""

    min_regime_confidence: float = 0.60
    min_breadth_score_for_long: int = 60
    max_breadth_score_for_short: int = 40
    stale_input_minutes: int = 120
    transition_action: DecisionAction = DecisionAction.BLOCK_ALL
    conflict_action: DecisionAction = DecisionAction.BLOCK_ALL

    def __post_init__(self) -> None:
        # Validate confidence range (0.0 to 1.0)
        if not 0.0 <= self.min_regime_confidence <= 1.0:
            raise ValueError(
                f"min_regime_confidence must be between 0.0 and 1.0, got {self.min_regime_confidence}"
            )
        # Validate breadth score ranges (0 to 100)
        for name, value in [
            ("min_breadth_score_for_long", self.min_breadth_score_for_long),
            ("max_breadth_score_for_short", self.max_breadth_score_for_short),
        ]:
            if not 0 <= value <= 100:
                raise ValueError(f"{name} must be between 0 and 100, got {value}")
        # Validate stale_input_minutes is positive
        if self.stale_input_minutes <= 0:
            raise ValueError(
                f"stale_input_minutes must be positive, got {self.stale_input_minutes}"
            )


@dataclass(frozen=True)
class DecisionInputRefs:
    """References to consumed engine outputs."""

    regime_timestamp: str = ""
    breadth_timestamp: str = ""
    regime_source: str = ""
    breadth_source: str = ""


@dataclass(frozen=True)
class DecisionOutput:
    """Decision Layer output with full audit trail."""

    timestamp: datetime
    status: OutputStatus
    decision_state: DecisionState
    decision_action: DecisionAction

    # Derived from RegimeOutput
    allowed_mode: AllowedMode
    market_regime: RegimeState
    risk_state: RiskState
    confidence: float
    regime_confidence: float

    # Derived from BreadthOutput
    breadth_score: int
    market_health: RiskState

    # Audit trail
    reason_codes: List[str] = field(default_factory=list)
    input_refs: DecisionInputRefs = field(default_factory=DecisionInputRefs)
    data_quality: DataQuality = field(default_factory=DataQuality)

    def __post_init__(self) -> None:
        # Validate confidence range (0.0 to 1.0)
        for name, value in [
            ("confidence", self.confidence),
            ("regime_confidence", self.regime_confidence),
        ]:
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0.0 and 1.0, got {value}")
        # Validate breadth_score range (0 to 100)
        if not 0 <= self.breadth_score <= 100:
            raise ValueError(
                f"breadth_score must be between 0 and 100, got {self.breadth_score}"
            )

    @classmethod
    def block_all(
        cls,
        timestamp: datetime | None = None,
        reason_codes: List[str] | None = None,
        data_quality: DataQuality | None = None,
    ) -> DecisionOutput:
        """Create a fail-closed BLOCK output.

        Used when inputs are missing, stale, invalid, or ambiguous.
        """
        return cls(
            timestamp=timestamp or datetime.now(timezone.utc),
            status=OutputStatus.INVALID,
            decision_state=DecisionState.BLOCK,
            decision_action=DecisionAction.BLOCK_ALL,
            allowed_mode=AllowedMode.NONE,
            market_regime=RegimeState.UNKNOWN,
            risk_state=RiskState.UNKNOWN,
            confidence=0.0,
            regime_confidence=0.0,
            breadth_score=0,
            market_health=RiskState.UNKNOWN,
            reason_codes=reason_codes or ["DECISION_BLOCKED_BY_DEFAULT"],
            data_quality=data_quality or DataQuality(),
        )

    def is_blocking(self) -> bool:
        """Return True if this decision blocks execution."""
        return (
            self.decision_state in (DecisionState.BLOCK, DecisionState.UNKNOWN)
            or self.allowed_mode == AllowedMode.NONE
            or self.status == OutputStatus.INVALID
        )
