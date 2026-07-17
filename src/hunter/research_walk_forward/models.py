"""Frozen models and safety contracts for walk-forward universe comparison (MVP-66 / SPEC-067)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any

WALK_FORWARD_VERSION: str = "0.66.0-dev"
SPEC_VERSION: str = "SPEC-067"

UNAVAILABLE: str = "UNAVAILABLE"

# -----------------------------------------------------------------------------
# Reason codes
# -----------------------------------------------------------------------------

INVALID_PLAN = "INVALID_PLAN"
INVALID_WINDOW = "INVALID_WINDOW"
LEAKAGE = "LEAKAGE"
DUPLICATE_WINDOW = "DUPLICATE_WINDOW"
OUT_OF_ORDER_WINDOWS = "OUT_OF_ORDER_WINDOWS"
BACKWARD_WINDOW = "BACKWARD_WINDOW"
INVALID_CONTIGUITY = "INVALID_CONTIGUITY"
ROLLING_DURATION_DRIFT = "ROLLING_DURATION_DRIFT"
EXPANDING_START_DRIFT = "EXPANDING_START_DRIFT"
MISSING_METRIC = "MISSING_METRIC"
INSUFFICIENT_TRADES = "INSUFFICIENT_TRADES"
TIMEOUT = "TIMEOUT"
RUNNER_ERROR = "RUNNER_ERROR"
WRITER_ERROR = "WRITER_ERROR"
RESEARCH_ONLY_ARTIFACT = "RESEARCH_ONLY_ARTIFACT"
HUMAN_RESEARCH_ONLY = "HUMAN_RESEARCH_ONLY"
NO_LIVE_TRADING = "NO_LIVE_TRADING"
NO_AUTOMATIC_EXECUTION = "NO_AUTOMATIC_EXECUTION"
NO_REMOTE_CHANGES = "NO_REMOTE_CHANGES"
NO_NETWORK_CONNECTION = "NO_NETWORK_CONNECTION"
NO_DATABASE_CONNECTION = "NO_DATABASE_CONNECTION"
NO_EXCHANGE_CONNECTION = "NO_EXCHANGE_CONNECTION"
NO_ACTION_COMMANDS_EMITTED = "NO_ACTION_COMMANDS_EMITTED"
NO_PARALLEL_EXECUTION = "NO_PARALLEL_EXECUTION"
NO_DIRECT_SUBPROCESS = "NO_DIRECT_SUBPROCESS"
WINDOW_FAILED = "WINDOW_FAILED"
WINDOW_BLOCKED = "WINDOW_BLOCKED"
WINDOW_TIMEOUT = "WINDOW_TIMEOUT"
WINDOW_UNSUPPORTED = "WINDOW_UNSUPPORTED"
WINDOW_INSUFFICIENT = "WINDOW_INSUFFICIENT"
SAFETY_INVARIANT_VIOLATION = "SAFETY_INVARIANT_VIOLATION"

WALK_FORWARD_REASON_CODES: frozenset[str] = frozenset(
    {
        INVALID_PLAN,
        INVALID_WINDOW,
        LEAKAGE,
        DUPLICATE_WINDOW,
        OUT_OF_ORDER_WINDOWS,
        BACKWARD_WINDOW,
        INVALID_CONTIGUITY,
        ROLLING_DURATION_DRIFT,
        EXPANDING_START_DRIFT,
        MISSING_METRIC,
        INSUFFICIENT_TRADES,
        TIMEOUT,
        RUNNER_ERROR,
        WRITER_ERROR,
        RESEARCH_ONLY_ARTIFACT,
        HUMAN_RESEARCH_ONLY,
        NO_LIVE_TRADING,
        NO_AUTOMATIC_EXECUTION,
        NO_REMOTE_CHANGES,
        NO_NETWORK_CONNECTION,
        NO_DATABASE_CONNECTION,
        NO_EXCHANGE_CONNECTION,
        NO_ACTION_COMMANDS_EMITTED,
        NO_PARALLEL_EXECUTION,
        NO_DIRECT_SUBPROCESS,
        WINDOW_FAILED,
        WINDOW_BLOCKED,
        WINDOW_TIMEOUT,
        WINDOW_UNSUPPORTED,
        WINDOW_INSUFFICIENT,
        SAFETY_INVARIANT_VIOLATION,
    }
)


# -----------------------------------------------------------------------------
# Enums
# -----------------------------------------------------------------------------

class WalkForwardMode(str, Enum):
    """Walk-forward selection window mode."""

    ROLLING = "ROLLING"
    EXPANDING = "EXPANDING"


class ExperimentExecutionPolicy(str, Enum):
    """How to handle a failed window."""

    COLLECT_ALL = "COLLECT_ALL"
    FAIL_FAST = "FAIL_FAST"


class MarketRegimeLabel(str, Enum):
    """Caller-provided market regime label."""

    BULL = "BULL"
    BEAR = "BEAR"
    SIDEWAYS = "SIDEWAYS"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    LOW_VOLATILITY = "LOW_VOLATILITY"
    UNKNOWN = "UNKNOWN"


class ConsistencyState(str, Enum):
    """Descriptive consistency of a metric across windows."""

    CONSISTENT_CANDIDATE_HIGHER = "CONSISTENT_CANDIDATE_HIGHER"
    MOSTLY_CANDIDATE_HIGHER = "MOSTLY_CANDIDATE_HIGHER"
    MIXED = "MIXED"
    MOSTLY_BASELINE_HIGHER = "MOSTLY_BASELINE_HIGHER"
    CONSISTENT_BASELINE_HIGHER = "CONSISTENT_BASELINE_HIGHER"
    EQUAL_OR_UNAVAILABLE = "EQUAL_OR_UNAVAILABLE"


class WindowStatus(str, Enum):
    """Terminal status of a walk-forward window."""

    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    TIMED_OUT = "TIMED_OUT"
    UNSUPPORTED = "UNSUPPORTED"
    INSUFFICIENT = "INSUFFICIENT"


class MetricDirection(str, Enum):
    """Direction of a candidate-baseline metric delta."""

    CANDIDATE_HIGHER = "CANDIDATE_HIGHER"
    BASELINE_HIGHER = "BASELINE_HIGHER"
    EQUAL = "EQUAL"
    UNAVAILABLE = "UNAVAILABLE"


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def _coerce_tuple_strs(values: tuple[str, ...] | list[str] | None) -> tuple[str, ...]:
    """Coerce a sequence to a deduplicated tuple of strings."""
    if values is None:
        return ()
    return tuple(dict.fromkeys(str(v) for v in values))


def _coerce_decimal(value: Decimal | str | int | float | None) -> Decimal | None:
    """Coerce a value to Decimal or None."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _coerce_mapping_strs(
    mapping: dict[str, str] | Any | None,
) -> Any:
    """Return an immutable string mapping."""
    if mapping is None:
        return MappingProxyType({})
    return MappingProxyType({str(k): str(v) for k, v in dict(mapping).items()})


# -----------------------------------------------------------------------------
# Safety flags
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class WalkForwardSafetyFlags:
    """Mandatory safety invariants for every walk-forward artifact."""

    research_only: bool = True
    execution_approval_granted: bool = False
    production_approval_granted: bool = False
    live_trading_allowed: bool = False
    automatic_execution_allowed: bool = False
    human_approval_required: bool = True
    no_action_commands_emitted: bool = True
    no_network_connection: bool = True
    no_database_connection: bool = True
    no_exchange_connection: bool = True
    no_remote_changes: bool = True
    no_parallel_execution: bool = True
    no_direct_subprocess: bool = True
    human_research_only: bool = True

    def __post_init__(self) -> None:
        for name, value in (
            ("research_only", self.research_only),
            ("execution_approval_granted", self.execution_approval_granted),
            ("production_approval_granted", self.production_approval_granted),
            ("live_trading_allowed", self.live_trading_allowed),
            ("automatic_execution_allowed", self.automatic_execution_allowed),
            ("human_approval_required", self.human_approval_required),
            ("no_action_commands_emitted", self.no_action_commands_emitted),
            ("no_network_connection", self.no_network_connection),
            ("no_database_connection", self.no_database_connection),
            ("no_exchange_connection", self.no_exchange_connection),
            ("no_remote_changes", self.no_remote_changes),
            ("no_parallel_execution", self.no_parallel_execution),
            ("no_direct_subprocess", self.no_direct_subprocess),
            ("human_research_only", self.human_research_only),
        ):
            if not isinstance(value, bool):
                raise ValueError(f"{name} must be a bool, got {value!r}")
        if not self.research_only:
            raise ValueError("research_only must be True")
        if self.execution_approval_granted:
            raise ValueError("execution_approval_granted must be False")
        if self.production_approval_granted:
            raise ValueError("production_approval_granted must be False")
        if self.live_trading_allowed:
            raise ValueError("live_trading_allowed must be False")
        if self.automatic_execution_allowed:
            raise ValueError("automatic_execution_allowed must be False")
        if not self.human_approval_required:
            raise ValueError("human_approval_required must be True")
        if not self.no_parallel_execution:
            raise ValueError("no_parallel_execution must be True")
        if not self.no_direct_subprocess:
            raise ValueError("no_direct_subprocess must be True")


# -----------------------------------------------------------------------------
# Core configuration
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class WalkForwardWindow:
    """A single selection + evaluation window pair."""

    selection_start: str
    selection_end: str
    evaluation_start: str
    evaluation_end: str
    regime_label: MarketRegimeLabel = MarketRegimeLabel.UNKNOWN
    metadata: Any = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in (
            "selection_start",
            "selection_end",
            "evaluation_start",
            "evaluation_end",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if not isinstance(self.regime_label, MarketRegimeLabel):
            raise ValueError(
                f"regime_label must be a MarketRegimeLabel, got {self.regime_label!r}"
            )
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))


@dataclass(frozen=True)
class WalkForwardCommonConfig:
    """Common configuration held constant across all windows."""

    strategy_name: str
    strategy_path: str | Path
    data_path: str | Path
    timeframe: str
    balance: Decimal
    stake: Decimal
    max_open_trades: int
    fee: Decimal
    executable_path: str | Path
    protections: tuple[str, ...] = ()
    timeout_seconds: int = 300
    env_allowlist: tuple[str, ...] | None = None
    extra_env: dict[str, str] | None = None
    metadata: Any = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "strategy_path", Path(self.strategy_path))
        object.__setattr__(self, "data_path", Path(self.data_path))
        object.__setattr__(self, "executable_path", Path(self.executable_path))
        object.__setattr__(self, "balance", _coerce_decimal(self.balance))
        object.__setattr__(self, "stake", _coerce_decimal(self.stake))
        object.__setattr__(self, "fee", _coerce_decimal(self.fee))
        object.__setattr__(
            self, "protections", _coerce_tuple_strs(self.protections)
        )
        if self.env_allowlist is not None:
            object.__setattr__(
                self, "env_allowlist", _coerce_tuple_strs(self.env_allowlist)
            )
        if self.extra_env is not None:
            object.__setattr__(self, "extra_env", dict(self.extra_env))
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))

        if not isinstance(self.strategy_name, str) or not self.strategy_name.strip():
            raise ValueError("strategy_name must be a non-empty string")
        if not isinstance(self.timeframe, str) or not self.timeframe.strip():
            raise ValueError("timeframe must be a non-empty string")
        if self.balance is None or self.balance <= Decimal("0"):
            raise ValueError("balance must be a positive Decimal")
        if self.stake is None or self.stake <= Decimal("0"):
            raise ValueError("stake must be a positive Decimal")
        if not isinstance(self.max_open_trades, int) or self.max_open_trades < 1:
            raise ValueError("max_open_trades must be a positive integer")
        if self.fee is None or self.fee < Decimal("0"):
            raise ValueError("fee must be a non-negative Decimal")
        if not isinstance(self.timeout_seconds, int) or self.timeout_seconds < 1:
            raise ValueError("timeout_seconds must be a positive integer")


@dataclass(frozen=True)
class WalkForwardExperimentPlan:
    """Deterministic walk-forward experiment plan."""

    mode: WalkForwardMode
    windows: tuple[WalkForwardWindow, ...]
    common: WalkForwardCommonConfig
    contiguous: bool = False
    safety_flags: WalkForwardSafetyFlags = field(default_factory=WalkForwardSafetyFlags)
    fingerprint: str = ""
    reason_codes: tuple[str, ...] = ()
    metadata: Any = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))
        if not isinstance(self.mode, WalkForwardMode):
            raise ValueError(f"mode must be a WalkForwardMode, got {self.mode!r}")
        if not isinstance(self.windows, tuple):
            raise ValueError(f"windows must be a tuple, got {self.windows!r}")
        for window in self.windows:
            if not isinstance(window, WalkForwardWindow):
                raise ValueError(
                    f"windows must contain WalkForwardWindow, got {window!r}"
                )
        if not isinstance(self.common, WalkForwardCommonConfig):
            raise ValueError(
                f"common must be a WalkForwardCommonConfig, got {self.common!r}"
            )
        if not isinstance(self.contiguous, bool):
            raise ValueError("contiguous must be a bool")
        if not isinstance(self.safety_flags, WalkForwardSafetyFlags):
            raise ValueError(
                f"safety_flags must be a WalkForwardSafetyFlags, got {self.safety_flags!r}"
            )
        if not isinstance(self.fingerprint, str):
            raise ValueError("fingerprint must be a string")


# -----------------------------------------------------------------------------
# Window result
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class WalkForwardWindowResult:
    """Result of running one walk-forward window."""

    window: WalkForwardWindow
    window_index: int
    status: WindowStatus
    candidate_metrics: dict[str, Decimal | None]
    baseline_metrics: dict[str, Decimal | None]
    metric_deltas: dict[str, Decimal | None]
    metric_directions: dict[str, MetricDirection]
    comparison_fingerprint: str
    candidate_fingerprint: str
    baseline_fingerprint: str
    fingerprint: str
    reason_codes: tuple[str, ...] = ()
    metadata: Any = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))
        if not isinstance(self.window, WalkForwardWindow):
            raise ValueError(f"window must be a WalkForwardWindow, got {self.window!r}")
        if not isinstance(self.window_index, int) or self.window_index < 0:
            raise ValueError("window_index must be a non-negative integer")
        if not isinstance(self.status, WindowStatus):
            raise ValueError(f"status must be a WindowStatus, got {self.status!r}")
        for name in ("candidate_metrics", "baseline_metrics", "metric_deltas", "metric_directions"):
            value = getattr(self, name)
            if not isinstance(value, dict):
                raise ValueError(f"{name} must be a dict, got {value!r}")
        if not isinstance(self.comparison_fingerprint, str):
            raise ValueError("comparison_fingerprint must be a string")
        if not isinstance(self.candidate_fingerprint, str):
            raise ValueError("candidate_fingerprint must be a string")
        if not isinstance(self.baseline_fingerprint, str):
            raise ValueError("baseline_fingerprint must be a string")
        if not isinstance(self.fingerprint, str) or not self.fingerprint.strip():
            raise ValueError("fingerprint must be a non-empty string")


# -----------------------------------------------------------------------------
# Aggregates
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class MetricAggregate:
    """Aggregated statistics for one canonical metric across windows."""

    metric_name: str
    available_count: int
    unavailable_count: int
    candidate_higher_count: int
    baseline_higher_count: int
    equal_count: int
    mean: Decimal | None
    median: Decimal | None
    min: Decimal | None
    max: Decimal | None
    q1: Decimal | None
    q3: Decimal | None
    iqr: Decimal | None
    positive_delta_share: Decimal
    negative_delta_share: Decimal
    zero_delta_share: Decimal
    consistency_state: ConsistencyState
    reason_codes: tuple[str, ...] = ()
    metadata: Any = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))
        if not isinstance(self.metric_name, str) or not self.metric_name.strip():
            raise ValueError("metric_name must be a non-empty string")
        for name in (
            "available_count",
            "unavailable_count",
            "candidate_higher_count",
            "baseline_higher_count",
            "equal_count",
        ):
            value = getattr(self, name)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        for name in ("mean", "median", "min", "max", "q1", "q3", "iqr"):
            value = getattr(self, name)
            if value is not None and not isinstance(value, Decimal):
                raise ValueError(f"{name} must be a Decimal or None")
        for name in ("positive_delta_share", "negative_delta_share", "zero_delta_share"):
            value = getattr(self, name)
            if not isinstance(value, Decimal):
                raise ValueError(f"{name} must be a Decimal")
        if not isinstance(self.consistency_state, ConsistencyState):
            raise ValueError(
                f"consistency_state must be a ConsistencyState, got {self.consistency_state!r}"
            )


@dataclass(frozen=True)
class RegimeAggregate:
    """Aggregated results for a single caller-provided regime label."""

    regime_label: MarketRegimeLabel
    window_count: int
    completed_count: int
    failed_count: int
    blocked_count: int
    timed_out_count: int
    unsupported_count: int
    insufficient_count: int
    metric_aggregates: dict[str, MetricAggregate]
    fingerprint: str
    reason_codes: tuple[str, ...] = ()
    metadata: Any = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))
        if not isinstance(self.regime_label, MarketRegimeLabel):
            raise ValueError(
                f"regime_label must be a MarketRegimeLabel, got {self.regime_label!r}"
            )
        for name in (
            "window_count",
            "completed_count",
            "failed_count",
            "blocked_count",
            "timed_out_count",
            "unsupported_count",
            "insufficient_count",
        ):
            value = getattr(self, name)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        if not isinstance(self.metric_aggregates, dict):
            raise ValueError("metric_aggregates must be a dict")
        if not isinstance(self.fingerprint, str) or not self.fingerprint.strip():
            raise ValueError("fingerprint must be a non-empty string")


# -----------------------------------------------------------------------------
# Report and manifest
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class WalkForwardManifest:
    """Lightweight manifest summarizing the experiment artifacts."""

    version: str
    spec_version: str
    walk_forward_version: str
    generated_at: datetime
    plan_fingerprint: str
    overall_aggregate_fingerprint: str
    regime_aggregate_fingerprint: str
    safety_flags: WalkForwardSafetyFlags
    reason_codes: tuple[str, ...] = ()
    metadata: Any = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.generated_at, datetime) or self.generated_at.tzinfo is None:
            raise ValueError("generated_at must be a timezone-aware datetime")
        for name, value in (
            ("plan_fingerprint", self.plan_fingerprint),
            ("overall_aggregate_fingerprint", self.overall_aggregate_fingerprint),
            ("regime_aggregate_fingerprint", self.regime_aggregate_fingerprint),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if not isinstance(self.safety_flags, WalkForwardSafetyFlags):
            raise ValueError(
                f"safety_flags must be a WalkForwardSafetyFlags, got {self.safety_flags!r}"
            )
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))


@dataclass(frozen=True)
class WalkForwardExperimentReport:
    """Top-level walk-forward experiment report."""

    version: str
    spec_version: str
    walk_forward_version: str
    plan: WalkForwardExperimentPlan
    window_results: tuple[WalkForwardWindowResult, ...]
    metric_aggregates: dict[str, MetricAggregate]
    regime_aggregates: tuple[RegimeAggregate, ...]
    manifest: WalkForwardManifest
    safety_flags: WalkForwardSafetyFlags
    fingerprint: str
    human_approval_required: bool = True
    research_only: bool = True
    reason_codes: tuple[str, ...] = ()
    metadata: Any = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))
        if not isinstance(self.version, str) or not self.version.strip():
            raise ValueError("version must be a non-empty string")
        if not isinstance(self.spec_version, str) or not self.spec_version.strip():
            raise ValueError("spec_version must be a non-empty string")
        if not isinstance(self.walk_forward_version, str) or not self.walk_forward_version.strip():
            raise ValueError("walk_forward_version must be a non-empty string")
        if not isinstance(self.plan, WalkForwardExperimentPlan):
            raise ValueError(f"plan must be a WalkForwardExperimentPlan, got {self.plan!r}")
        if not isinstance(self.window_results, tuple):
            raise ValueError(f"window_results must be a tuple, got {self.window_results!r}")
        if not isinstance(self.metric_aggregates, dict):
            raise ValueError(f"metric_aggregates must be a dict, got {self.metric_aggregates!r}")
        if not isinstance(self.regime_aggregates, tuple):
            raise ValueError(f"regime_aggregates must be a tuple, got {self.regime_aggregates!r}")
        if not isinstance(self.manifest, WalkForwardManifest):
            raise ValueError(f"manifest must be a WalkForwardManifest, got {self.manifest!r}")
        if not isinstance(self.safety_flags, WalkForwardSafetyFlags):
            raise ValueError(
                f"safety_flags must be a WalkForwardSafetyFlags, got {self.safety_flags!r}"
            )
        if not isinstance(self.fingerprint, str) or not self.fingerprint.strip():
            raise ValueError("fingerprint must be a non-empty string")
        if not isinstance(self.human_approval_required, bool):
            raise ValueError("human_approval_required must be a boolean")
        if not isinstance(self.research_only, bool):
            raise ValueError("research_only must be a boolean")


# -----------------------------------------------------------------------------
# Errors (also mirrored in errors.py for public API)
# -----------------------------------------------------------------------------

class WalkForwardError(Exception):
    """Base exception for the walk-forward experiment harness."""

    def __init__(self, message: str, reason_code: str | None = None) -> None:
        super().__init__(message)
        self.reason_code = reason_code


class WalkForwardConfigError(WalkForwardError):
    """Invalid configuration."""


class WalkForwardValidationError(WalkForwardError):
    """Validation failure."""


class WalkForwardLeakageError(WalkForwardValidationError):
    """Leakage guard violation."""


class WalkForwardRunnerError(WalkForwardError):
    """Window runner failure."""


class WalkForwardWriterError(WalkForwardError):
    """Writer failure."""

    def __init__(self, message: str, reason_code: str | None = None) -> None:
        super().__init__(message, reason_code=reason_code)


class WalkForwardSafetyError(WalkForwardError):
    """Safety invariant violation."""

