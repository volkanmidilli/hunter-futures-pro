"""Observation models for MVP-10 Dry-Run Research Observation & Reports.

Implements the dataclasses and enums defined in SPEC-011.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ObservationState(str, Enum):
    """State of an observation or report."""

    DISABLED = "DISABLED"
    READY = "READY"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"


class ObservationSignal(str, Enum):
    """Research signal type."""

    LONG_RESEARCH = "LONG_RESEARCH"
    SHORT_RESEARCH = "SHORT_RESEARCH"
    NONE = "NONE"


class ReportFormat(str, Enum):
    """Report output format."""

    JSON = "JSON"
    MARKDOWN = "MARKDOWN"


# ---------------------------------------------------------------------------
# Reason code constants
# ---------------------------------------------------------------------------

MISSING_INPUT = "MISSING_INPUT"
INVALID_INPUT = "INVALID_INPUT"
UNSUPPORTED_INPUT_VERSION = "UNSUPPORTED_INPUT_VERSION"
DRY_RUN_DISABLED = "DRY_RUN_DISABLED"
LIVE_TRADING_ENABLED = "LIVE_TRADING_ENABLED"
REAL_ORDERS_ENABLED = "REAL_ORDERS_ENABLED"
LEVERAGE_ENABLED = "LEVERAGE_ENABLED"
SHORTING_ENABLED = "SHORTING_ENABLED"
EMPTY_OBSERVATION_WINDOW = "EMPTY_OBSERVATION_WINDOW"
UNSAFE_METADATA = "UNSAFE_METADATA"
REPORT_GENERATION_BLOCKED = "REPORT_GENERATION_BLOCKED"
OBSERVATION_ERROR = "OBSERVATION_ERROR"
DEFAULT_BLOCKED = "DEFAULT_BLOCKED"

REASON_CODES: tuple[str, ...] = (
    MISSING_INPUT,
    INVALID_INPUT,
    UNSUPPORTED_INPUT_VERSION,
    DRY_RUN_DISABLED,
    LIVE_TRADING_ENABLED,
    REAL_ORDERS_ENABLED,
    LEVERAGE_ENABLED,
    SHORTING_ENABLED,
    EMPTY_OBSERVATION_WINDOW,
    UNSAFE_METADATA,
    REPORT_GENERATION_BLOCKED,
    OBSERVATION_ERROR,
    DEFAULT_BLOCKED,
)

# ---------------------------------------------------------------------------
# Forbidden metadata keys
# ---------------------------------------------------------------------------

FORBIDDEN_METADATA_KEYS: frozenset[str] = frozenset(
    {
        "enter_long",
        "enter_short",
        "exit_long",
        "exit_short",
        "api_key",
        "secret",
        "exchange_credentials",
        "executable_instructions",
    }
)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ObservationConfig:
    """Configuration for the observation layer."""

    input_version: str = "1.0"
    max_observation_age_seconds: int = 300
    allow_json_report: bool = True
    allow_markdown_report: bool = True
    allow_execution_feedback: bool = False
    allow_network_calls: bool = False
    allow_database_persistence: bool = False
    allow_realtime_streaming: bool = False
    allow_api_keys: bool = False
    allow_live_trading: bool = False
    allow_real_orders: bool = False
    allow_leverage: bool = False
    allow_shorting: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.input_version, str) or not self.input_version:
            raise ValueError("input_version must be a non-empty string")
        if not isinstance(self.max_observation_age_seconds, int) or self.max_observation_age_seconds <= 0:
            raise ValueError("max_observation_age_seconds must be > 0")
        if not self.allow_json_report and not self.allow_markdown_report:
            raise ValueError("at least one report format must be allowed")
        unsafe_flags = [
            ("allow_execution_feedback", self.allow_execution_feedback),
            ("allow_network_calls", self.allow_network_calls),
            ("allow_database_persistence", self.allow_database_persistence),
            ("allow_realtime_streaming", self.allow_realtime_streaming),
            ("allow_api_keys", self.allow_api_keys),
            ("allow_live_trading", self.allow_live_trading),
            ("allow_real_orders", self.allow_real_orders),
            ("allow_leverage", self.allow_leverage),
            ("allow_shorting", self.allow_shorting),
        ]
        for name, value in unsafe_flags:
            if value is not False:
                raise ValueError(f"{name} must remain False")


@dataclass(frozen=True)
class ObservationSafetyFlags:
    """Safety flags for an observation or report."""

    dry_run: bool = True
    live_trading_enabled: bool = False
    real_orders_enabled: bool = False
    leverage_enabled: bool = False
    shorting_enabled: bool = False
    execution_feedback_allowed: bool = False
    network_calls_allowed: bool = False
    database_persistence_allowed: bool = False
    realtime_streaming_allowed: bool = False
    api_keys_allowed: bool = False

    def __post_init__(self) -> None:
        if self.dry_run is not True:
            raise ValueError("dry_run must be True")
        unsafe_flags = [
            ("live_trading_enabled", self.live_trading_enabled),
            ("real_orders_enabled", self.real_orders_enabled),
            ("leverage_enabled", self.leverage_enabled),
            ("shorting_enabled", self.shorting_enabled),
            ("execution_feedback_allowed", self.execution_feedback_allowed),
            ("network_calls_allowed", self.network_calls_allowed),
            ("database_persistence_allowed", self.database_persistence_allowed),
            ("realtime_streaming_allowed", self.realtime_streaming_allowed),
            ("api_keys_allowed", self.api_keys_allowed),
        ]
        for name, value in unsafe_flags:
            if value is not False:
                raise ValueError(f"{name} must remain False")


@dataclass(frozen=True)
class SignalObservation:
    """A single point-in-time observation of a research signal."""

    timestamp: datetime
    observation_state: ObservationState
    signal: ObservationSignal
    source_shell_state: str
    source_signal_exposure: str
    reason_codes: tuple[str, ...]
    metadata: dict[str, Any] = field(default_factory=dict)
    safety_flags: ObservationSafetyFlags = field(default_factory=ObservationSafetyFlags)
    version: str = "1.0"

    def __post_init__(self) -> None:
        if not isinstance(self.timestamp, datetime) or self.timestamp.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        if not isinstance(self.source_shell_state, str) or not self.source_shell_state:
            raise ValueError("source_shell_state must be a non-empty string")
        if not isinstance(self.source_signal_exposure, str) or not self.source_signal_exposure:
            raise ValueError("source_signal_exposure must be a non-empty string")
        if not isinstance(self.reason_codes, tuple) or len(self.reason_codes) == 0:
            raise ValueError("reason_codes must be a non-empty tuple")
        if not isinstance(self.version, str) or not self.version:
            raise ValueError("version must be a non-empty string")
        if self.observation_state != ObservationState.READY and self.signal != ObservationSignal.NONE:
            raise ValueError("if observation_state is not READY, signal must be NONE")
        _validate_metadata(self.metadata)

    @classmethod
    def blocked(
        cls,
        reason_codes: tuple[str, ...],
        timestamp: datetime | None = None,
    ) -> "SignalObservation":
        """Factory for a blocked observation."""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        return cls(
            timestamp=timestamp,
            observation_state=ObservationState.BLOCKED,
            signal=ObservationSignal.NONE,
            source_shell_state="UNKNOWN",
            source_signal_exposure="BLOCKED",
            reason_codes=reason_codes,
            metadata={},
            safety_flags=ObservationSafetyFlags(),
            version="1.0",
        )


@dataclass(frozen=True)
class ObservationWindow:
    """A time-bucketed summary of multiple observations."""

    started_at: datetime
    ended_at: datetime
    observations: tuple[SignalObservation, ...]
    window_id: str = "default"

    def __post_init__(self) -> None:
        if not isinstance(self.started_at, datetime) or self.started_at.tzinfo is None:
            raise ValueError("started_at must be timezone-aware")
        if not isinstance(self.ended_at, datetime) or self.ended_at.tzinfo is None:
            raise ValueError("ended_at must be timezone-aware")
        if self.ended_at < self.started_at:
            raise ValueError("ended_at must be >= started_at")
        if not isinstance(self.window_id, str) or not self.window_id:
            raise ValueError("window_id must be a non-empty string")


@dataclass(frozen=True)
class ObservationDataQuality:
    """Data quality metrics for an observation report."""

    input_present: bool = False
    input_valid: bool = False
    input_version_supported: bool = False
    observation_count: int = 0
    blocked_count: int = 0
    unknown_count: int = 0
    reason: str = "NOT_EVALUATED"

    def __post_init__(self) -> None:
        if not isinstance(self.observation_count, int) or self.observation_count < 0:
            raise ValueError("observation_count must be >= 0")
        if not isinstance(self.blocked_count, int) or self.blocked_count < 0:
            raise ValueError("blocked_count must be >= 0")
        if not isinstance(self.unknown_count, int) or self.unknown_count < 0:
            raise ValueError("unknown_count must be >= 0")
        if not isinstance(self.reason, str) or not self.reason:
            raise ValueError("reason must be a non-empty string")


@dataclass(frozen=True)
class ObservationReport:
    """Complete report containing all observations and summaries."""

    generated_at: datetime
    report_state: ObservationState
    window: ObservationWindow
    summary: dict[str, Any] = field(default_factory=dict)
    data_quality: ObservationDataQuality = field(default_factory=ObservationDataQuality)
    safety_flags: ObservationSafetyFlags = field(default_factory=ObservationSafetyFlags)
    report_formats: tuple[ReportFormat, ...] = (ReportFormat.JSON, ReportFormat.MARKDOWN)
    reason_codes: tuple[str, ...] = (DEFAULT_BLOCKED,)
    version: str = "1.0"

    def __post_init__(self) -> None:
        if not isinstance(self.generated_at, datetime) or self.generated_at.tzinfo is None:
            raise ValueError("generated_at must be timezone-aware")
        if not isinstance(self.report_formats, tuple) or len(self.report_formats) == 0:
            raise ValueError("report_formats must be a non-empty tuple")
        if not isinstance(self.reason_codes, tuple) or len(self.reason_codes) == 0:
            raise ValueError("reason_codes must be a non-empty tuple")
        if not isinstance(self.version, str) or not self.version:
            raise ValueError("version must be a non-empty string")

    @classmethod
    def blocked(
        cls,
        reason_codes: tuple[str, ...],
        window: ObservationWindow | None = None,
        generated_at: datetime | None = None,
    ) -> "ObservationReport":
        """Factory for a blocked report."""
        if generated_at is None:
            generated_at = datetime.now(timezone.utc)
        if window is None:
            window = ObservationWindow(
                started_at=generated_at,
                ended_at=generated_at,
                observations=(),
            )
        return cls(
            generated_at=generated_at,
            report_state=ObservationState.BLOCKED,
            window=window,
            summary={},
            data_quality=ObservationDataQuality(
                input_present=False,
                input_valid=False,
                input_version_supported=False,
                observation_count=0,
                blocked_count=0,
                unknown_count=0,
                reason=reason_codes[0] if reason_codes else DEFAULT_BLOCKED,
            ),
            safety_flags=ObservationSafetyFlags(),
            report_formats=(ReportFormat.JSON, ReportFormat.MARKDOWN),
            reason_codes=reason_codes,
            version="1.0",
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validate_metadata(metadata: dict[str, Any]) -> None:
    """Validate that metadata does not contain forbidden keys."""
    if not isinstance(metadata, dict):
        raise ValueError("metadata must be a dict")
    for key in metadata:
        if key in FORBIDDEN_METADATA_KEYS:
            raise ValueError(f"metadata contains forbidden key: {key}")
