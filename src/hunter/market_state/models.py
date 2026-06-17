"""Market state models for Regime Engine and Breadth Engine outputs."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import List


class RegimeState(str, Enum):
    """Market regime classification states."""

    BULL = "BULL"
    BEAR = "BEAR"
    SIDEWAYS = "SIDEWAYS"
    TRANSITION = "TRANSITION"
    UNKNOWN = "UNKNOWN"


class RiskState(str, Enum):
    """Risk-on / risk-off classification."""

    RISK_ON = "RISK_ON"
    RISK_OFF = "RISK_OFF"
    NEUTRAL = "NEUTRAL"
    UNKNOWN = "UNKNOWN"


class AllowedMode(str, Enum):
    """Execution modes allowed by the regime."""

    LONG_ONLY = "LONG_ONLY"
    SHORT_ONLY = "SHORT_ONLY"
    NONE = "NONE"


class OutputStatus(str, Enum):
    """Validation status of engine output."""

    VALID = "VALID"
    INVALID = "INVALID"


@dataclass(frozen=True)
class DataQuality:
    """Data quality flags for engine inputs."""

    missing: bool = False
    stale: bool = False
    insufficient_history: bool = False
    insufficient_universe: bool = False

    def is_valid(self) -> bool:
        """Return True if no quality issues are flagged."""
        return not any(
            [self.missing, self.stale, self.insufficient_history, self.insufficient_universe]
        )


@dataclass(frozen=True)
class RegimeOutput:
    """Output from the Regime Engine.

    Fields match SPEC-003 JSON contract.
    """

    timestamp: datetime
    status: OutputStatus
    market_regime: RegimeState
    allowed_mode: AllowedMode
    confidence: float
    risk_state: RiskState
    btc_trend_score: int
    eth_trend_score: int
    breadth_confirmation_score: int
    reason_codes: List[str] = field(default_factory=list)
    data_quality: DataQuality = field(default_factory=DataQuality)

    def __post_init__(self) -> None:
        # Validate confidence range (0.0 to 1.0)
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"confidence must be between 0.0 and 1.0, got {self.confidence}"
            )
        # Validate score ranges (0 to 100)
        for name, value in [
            ("btc_trend_score", self.btc_trend_score),
            ("eth_trend_score", self.eth_trend_score),
            ("breadth_confirmation_score", self.breadth_confirmation_score),
        ]:
            if not 0 <= value <= 100:
                raise ValueError(f"{name} must be between 0 and 100, got {value}")

    @classmethod
    def unknown(
        cls,
        timestamp: datetime | None = None,
        reason_codes: List[str] | None = None,
        data_quality: DataQuality | None = None,
    ) -> RegimeOutput:
        """Create a fail-closed UNKNOWN regime output.

        Used when data is missing, stale, insufficient, or calculation fails.
        """
        return cls(
            timestamp=timestamp or datetime.now(timezone.utc),
            status=OutputStatus.INVALID,
            market_regime=RegimeState.UNKNOWN,
            allowed_mode=AllowedMode.NONE,
            confidence=0.0,
            risk_state=RiskState.UNKNOWN,
            btc_trend_score=0,
            eth_trend_score=0,
            breadth_confirmation_score=0,
            reason_codes=reason_codes or ["UNKNOWN_REGIME_BLOCKS_EXECUTION"],
            data_quality=data_quality or DataQuality(),
        )

    def is_blocking(self) -> bool:
        """Return True if this output blocks execution."""
        return self.allowed_mode == AllowedMode.NONE or self.status == OutputStatus.INVALID


@dataclass(frozen=True)
class BreadthOutput:
    """Output from the Market Breadth Engine.

    Fields match SPEC-003 JSON contract.
    """

    timestamp: datetime
    status: OutputStatus
    breadth_score: int
    market_health: RiskState
    universe_size: int
    valid_symbol_count: int
    invalid_symbol_count: int
    above_ema20_pct: float
    above_ema50_pct: float
    above_ema200_pct: float
    ema20_rising_pct: float
    ema50_rising_pct: float
    advancing_pct: float
    declining_pct: float
    outperforming_btc_7d_pct: float
    outperforming_btc_30d_pct: float
    reason_codes: List[str] = field(default_factory=list)
    data_quality: DataQuality = field(default_factory=DataQuality)

    def __post_init__(self) -> None:
        # Validate breadth_score range (0 to 100)
        if not 0 <= self.breadth_score <= 100:
            raise ValueError(
                f"breadth_score must be between 0 and 100, got {self.breadth_score}"
            )
        # Validate percentage fields (0.0 to 1.0)
        pct_fields = [
            ("above_ema20_pct", self.above_ema20_pct),
            ("above_ema50_pct", self.above_ema50_pct),
            ("above_ema200_pct", self.above_ema200_pct),
            ("ema20_rising_pct", self.ema20_rising_pct),
            ("ema50_rising_pct", self.ema50_rising_pct),
            ("advancing_pct", self.advancing_pct),
            ("declining_pct", self.declining_pct),
            ("outperforming_btc_7d_pct", self.outperforming_btc_7d_pct),
            ("outperforming_btc_30d_pct", self.outperforming_btc_30d_pct),
        ]
        for name, value in pct_fields:
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0.0 and 1.0, got {value}")

    @classmethod
    def invalid(
        cls,
        timestamp: datetime | None = None,
        reason_codes: List[str] | None = None,
        data_quality: DataQuality | None = None,
    ) -> BreadthOutput:
        """Create a fail-closed invalid breadth output.

        Used when universe data is missing, stale, or insufficient.
        """
        return cls(
            timestamp=timestamp or datetime.now(timezone.utc),
            status=OutputStatus.INVALID,
            breadth_score=0,
            market_health=RiskState.UNKNOWN,
            universe_size=0,
            valid_symbol_count=0,
            invalid_symbol_count=0,
            above_ema20_pct=0.0,
            above_ema50_pct=0.0,
            above_ema200_pct=0.0,
            ema20_rising_pct=0.0,
            ema50_rising_pct=0.0,
            advancing_pct=0.0,
            declining_pct=0.0,
            outperforming_btc_7d_pct=0.0,
            outperforming_btc_30d_pct=0.0,
            reason_codes=reason_codes or ["DATA_MISSING", "INSUFFICIENT_UNIVERSE"],
            data_quality=data_quality or DataQuality(),
        )

    def is_valid(self) -> bool:
        """Return True if breadth output is valid and usable."""
        return self.status == OutputStatus.VALID and self.data_quality.is_valid()
