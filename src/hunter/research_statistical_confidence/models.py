"""Frozen models and safety contracts for walk-forward statistical confidence (MVP-67 / SPEC-068)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from types import MappingProxyType
from typing import Any

from hunter.research_walk_forward.models import MarketRegimeLabel, MetricDirection

STATISTICAL_CONFIDENCE_VERSION: str = "0.67.0-dev"
SPEC_VERSION: str = "SPEC-068"

UNAVAILABLE: str = "UNAVAILABLE"

# -----------------------------------------------------------------------------
# Reason codes
# -----------------------------------------------------------------------------

INVALID_CONFIG = "INVALID_CONFIG"
INSUFFICIENT_EVIDENCE_CODE = "INSUFFICIENT_EVIDENCE"
MISSING_SOURCE_FINGERPRINT = "MISSING_SOURCE_FINGERPRINT"
INHERITED_SAFETY_VIOLATION = "INHERITED_SAFETY_VIOLATION"
DIRECTION_CONFLICT_CODE = "DIRECTION_CONFLICT"
UNSTABLE_SIGN_CODE = "UNSTABLE_SIGN"
EXCESSIVE_INFLUENCE = "EXCESSIVE_INFLUENCE"
NO_BOOTSTRAP = "NO_BOOTSTRAP"
BOOTSTRAP_FAILED = "BOOTSTRAP_FAILED"
ROBUSTNESS_PASSED = "ROBUSTNESS_PASSED"
BOOTSTRAP_CONFIDENCE_EXCLUDES_ZERO = "BOOTSTRAP_CONFIDENCE_EXCLUDES_ZERO"
BOOTSTRAP_CONFIDENCE_INCLUDES_ZERO = "BOOTSTRAP_CONFIDENCE_INCLUDES_ZERO"
SIGN_STABLE = "SIGN_STABLE"
INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
INSUFFICIENT_SIGN_SHARE = "INSUFFICIENT_SIGN_SHARE"
CONSISTENT_DIRECTION = "CONSISTENT_DIRECTION"
ROBUSTNESS_FAILED = "ROBUSTNESS_FAILED"
NO_TRADES_BOTH_ARMS = "NO_TRADES_BOTH_ARMS"
NO_TRADES_CANDIDATE = "NO_TRADES_CANDIDATE"
NO_TRADES_BASELINE = "NO_TRADES_BASELINE"
ZERO_OBSERVED_DISPERSION = "ZERO_OBSERVED_DISPERSION"
INSUFFICIENT_DISTINCT_VALUES = "INSUFFICIENT_DISTINCT_VALUES"
OVERLAPPING_WINDOWS = "OVERLAPPING_WINDOWS"
NON_OVERLAPPING = "NON_OVERLAPPING"
OVERLAPPING = "OVERLAPPING"
UNKNOWN_DEPENDENCE = "UNKNOWN_DEPENDENCE"

STATISTICAL_CONFIDENCE_REASON_CODES: frozenset[str] = frozenset({
    INVALID_CONFIG,
    INSUFFICIENT_EVIDENCE_CODE,
    MISSING_SOURCE_FINGERPRINT,
    INHERITED_SAFETY_VIOLATION,
    DIRECTION_CONFLICT_CODE,
    UNSTABLE_SIGN_CODE,
    EXCESSIVE_INFLUENCE,
    NO_BOOTSTRAP,
    BOOTSTRAP_FAILED,
    ROBUSTNESS_PASSED,
    BOOTSTRAP_CONFIDENCE_EXCLUDES_ZERO,
    BOOTSTRAP_CONFIDENCE_INCLUDES_ZERO,
    SIGN_STABLE,
    INSUFFICIENT_DATA,
    CONSISTENT_DIRECTION,
    INSUFFICIENT_SIGN_SHARE,
    ROBUSTNESS_FAILED,
    NO_TRADES_BOTH_ARMS,
    NO_TRADES_CANDIDATE,
    NO_TRADES_BASELINE,
    ZERO_OBSERVED_DISPERSION,
    INSUFFICIENT_DISTINCT_VALUES,
    OVERLAPPING_WINDOWS,
    NON_OVERLAPPING,
    OVERLAPPING,
    UNKNOWN_DEPENDENCE,
})

# -----------------------------------------------------------------------------
# Enums
# -----------------------------------------------------------------------------


class ConfidenceState(str, Enum):
    """Descriptive statistical confidence state for a metric."""
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    UNSTABLE = "UNSTABLE"
    MIXED = "MIXED"
    DIRECTIONALLY_STABLE_CANDIDATE = "DIRECTIONALLY_STABLE_CANDIDATE"
    DIRECTIONALLY_STABLE_BASELINE = "DIRECTIONALLY_STABLE_BASELINE"
    ROBUST_CANDIDATE = "ROBUST_CANDIDATE"
    ROBUST_BASELINE = "ROBUST_BASELINE"


class DependenceStatus(str, Enum):
    """Window-overlap dependence status for walk-forward experiments.

    - NON_OVERLAPPING: no pair of evaluation windows overlaps.
    - OVERLAPPING: at least one pair of evaluation windows overlaps.
    - UNKNOWN: insufficient or unparseable boundary information.
    """

    NON_OVERLAPPING = "NON_OVERLAPPING"
    OVERLAPPING = "OVERLAPPING"
    UNKNOWN = "UNKNOWN"


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
class StatisticalConfidenceSafetyFlags:
    """Mandatory safety invariants for every statistical confidence artifact."""

    research_only: bool = True
    execution_approval_granted: bool = False
    production_approval_granted: bool = False
    live_trading_allowed: bool = False
    automatic_execution_allowed: bool = False
    human_approval_required: bool = True
    no_direct_subprocess: bool = True
    no_parallel_execution: bool = True
    no_network_connection: bool = True
    no_database_connection: bool = True
    no_exchange_connection: bool = True
    no_remote_changes: bool = True
    no_action_commands_emitted: bool = True

    def __post_init__(self) -> None:
        for name in (
            "research_only",
            "execution_approval_granted",
            "production_approval_granted",
            "live_trading_allowed",
            "automatic_execution_allowed",
            "human_approval_required",
            "no_direct_subprocess",
            "no_parallel_execution",
            "no_network_connection",
            "no_database_connection",
            "no_exchange_connection",
            "no_remote_changes",
            "no_action_commands_emitted",
        ):
            value = getattr(self, name)
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
        if not self.no_direct_subprocess:
            raise ValueError("no_direct_subprocess must be True")
        if not self.no_parallel_execution:
            raise ValueError("no_parallel_execution must be True")


# -----------------------------------------------------------------------------
# Configuration models
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class BootstrapConfig:
    """Configuration for deterministic bootstrap resampling.

    Attributes:
        seed: Deterministic seed for the bootstrap PRNG.
        iterations: Number of bootstrap resamples to draw.
        min_distinct_values_for_bootstrap: Minimum number of distinct sample
            values required for the bootstrap exchangeability assumption.
            Samples with fewer distinct values are flagged with
            ``INSUFFICIENT_DISTINCT_VALUES`` and are not eligible for
            ``ROBUST_CANDIDATE`` / ``ROBUST_BASELINE`` classification.
            Defaults to 2 (any constant non-zero sample is flagged).
    """

    seed: int
    iterations: int
    min_distinct_values_for_bootstrap: int = 2

    def __post_init__(self) -> None:
        if not isinstance(self.seed, int):
            raise ValueError(f"seed must be an int, got {self.seed!r}")
        if not isinstance(self.iterations, int) or self.iterations < 1:
            raise ValueError(f"iterations must be a positive int, got {self.iterations}")
        if (
            not isinstance(self.min_distinct_values_for_bootstrap, int)
            or self.min_distinct_values_for_bootstrap < 1
        ):
            raise ValueError(
                "min_distinct_values_for_bootstrap must be a positive int (>=1)"
            )


@dataclass(frozen=True)
class RobustnessCriteria:
    """Criteria for determining robustness of a metric direction."""

    sign_share_threshold: Decimal
    maximum_influence_ratio: Decimal
    confidence_level: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(self, "sign_share_threshold", _coerce_decimal(self.sign_share_threshold))
        object.__setattr__(self, "maximum_influence_ratio", _coerce_decimal(self.maximum_influence_ratio))
        object.__setattr__(self, "confidence_level", _coerce_decimal(self.confidence_level))


@dataclass(frozen=True)
class StatisticalConfidenceConfig:
    """Top-level configuration for statistical confidence evaluation."""

    minimum_available_window_count: int
    confidence_level: Decimal
    bootstrap: BootstrapConfig
    robustness: RobustnessCriteria

    def __post_init__(self) -> None:
        object.__setattr__(self, "confidence_level", _coerce_decimal(self.confidence_level))
        if not isinstance(self.minimum_available_window_count, int):
            raise ValueError("minimum_available_window_count must be an int")
        if not isinstance(self.bootstrap, BootstrapConfig):
            raise ValueError(f"bootstrap must be a BootstrapConfig, got {self.bootstrap!r}")
        if not isinstance(self.robustness, RobustnessCriteria):
            raise ValueError(f"robustness must be a RobustnessCriteria, got {self.robustness!r}")


# -----------------------------------------------------------------------------
# Result models
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class BootstrapInterval:
    """A percentile bootstrap confidence interval for a statistic."""

    lower: Decimal
    upper: Decimal
    confidence_level: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(self, "lower", _coerce_decimal(self.lower))
        object.__setattr__(self, "upper", _coerce_decimal(self.upper))
        object.__setattr__(self, "confidence_level", _coerce_decimal(self.confidence_level))


@dataclass(frozen=True)
class LeaveOneOutResult:
    """Results from leave-one-window-out sensitivity analysis."""

    mean_range: Decimal
    median_range: Decimal
    max_influence_window_index: int
    max_influence_ratio: Decimal
    directions: tuple[MetricDirection, ...]
    sign_stable: bool
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "mean_range", _coerce_decimal(self.mean_range))
        object.__setattr__(self, "median_range", _coerce_decimal(self.median_range))
        object.__setattr__(self, "max_influence_ratio", _coerce_decimal(self.max_influence_ratio))
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))
        if not isinstance(self.max_influence_window_index, int) or self.max_influence_window_index < 0:
            raise ValueError("max_influence_window_index must be a non-negative integer")
        if not isinstance(self.directions, tuple):
            raise ValueError("directions must be a tuple")
        for d in self.directions:
            if not isinstance(d, MetricDirection):
                raise ValueError(f"direction must be MetricDirection, got {d!r}")
        if not isinstance(self.sign_stable, bool):
            raise ValueError("sign_stable must be a bool")


@dataclass(frozen=True)
class MetricConfidenceResult:
    """Statistical confidence result for a single canonical metric."""

    metric_name: str
    available_count: int
    unavailable_count: int
    mean: Decimal | None
    median: Decimal | None
    std_dev: Decimal | None
    mad: Decimal | None
    min: Decimal | None
    max: Decimal | None
    q1: Decimal | None
    q3: Decimal | None
    iqr: Decimal | None
    positive_share: Decimal
    negative_share: Decimal
    zero_share: Decimal
    bootstrap_mean_ci: BootstrapInterval | None
    bootstrap_median_ci: BootstrapInterval | None
    loo: LeaveOneOutResult | None
    confidence_state: ConfidenceState
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))
        names_int = ("available_count", "unavailable_count")
        for name in names_int:
            value = getattr(self, name)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        names_dec = ("mean", "median", "std_dev", "mad", "min", "max", "q1", "q3", "iqr")
        for name in names_dec:
            value = getattr(self, name)
            if value is not None and not isinstance(value, Decimal):
                raise ValueError(f"{name} must be a Decimal or None")
        for name in ("positive_share", "negative_share", "zero_share"):
            value = getattr(self, name)
            if not isinstance(value, Decimal):
                raise ValueError(f"{name} must be a Decimal")
        if not isinstance(self.confidence_state, ConfidenceState):
            raise ValueError(f"confidence_state must be a ConfidenceState, got {self.confidence_state!r}")
        if not isinstance(self.metric_name, str) or not self.metric_name.strip():
            raise ValueError("metric_name must be a non-empty string")


@dataclass(frozen=True)
class RegimeConfidenceResult:
    """Statistical confidence results stratified by a caller-provided regime."""

    regime_label: MarketRegimeLabel
    available_count: int
    metric_results: dict[str, MetricConfidenceResult]
    status_counts: dict[str, int]
    fingerprint: str
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))
        if not isinstance(self.regime_label, MarketRegimeLabel):
            raise ValueError(f"regime_label must be a MarketRegimeLabel, got {self.regime_label!r}")
        if not isinstance(self.available_count, int) or self.available_count < 0:
            raise ValueError("available_count must be a non-negative integer")
        if not isinstance(self.metric_results, dict):
            raise ValueError("metric_results must be a dict")
        if not isinstance(self.status_counts, dict):
            raise ValueError("status_counts must be a dict")
        if not isinstance(self.fingerprint, str) or not self.fingerprint.strip():
            raise ValueError("fingerprint must be a non-empty string")


# -----------------------------------------------------------------------------
# Manifest and Report
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class StatisticalConfidenceManifest:
    """Lightweight manifest summarizing statistical confidence artifacts."""

    version: str
    spec_version: str
    statistical_confidence_version: str
    generated_at: datetime
    config_fingerprint: str
    metric_results_fingerprint: str
    regime_results_fingerprint: str
    overall_fingerprint: str
    safety_flags: StatisticalConfidenceSafetyFlags
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.generated_at, datetime) or self.generated_at.tzinfo is None:
            raise ValueError("generated_at must be a timezone-aware datetime")
        for name in ("config_fingerprint", "metric_results_fingerprint", "regime_results_fingerprint", "overall_fingerprint"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if not isinstance(self.safety_flags, StatisticalConfidenceSafetyFlags):
            raise ValueError(f"safety_flags must be a StatisticalConfidenceSafetyFlags, got {self.safety_flags!r}")
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))


@dataclass(frozen=True)
class ExperimentConfidenceReport:
    """Top-level statistical confidence report for a walk-forward experiment."""

    version: str
    spec_version: str
    statistical_confidence_version: str
    source_report_fingerprint: str
    config: StatisticalConfidenceConfig
    metric_results: dict[str, MetricConfidenceResult]
    regime_results: dict[str, RegimeConfidenceResult]
    manifest: StatisticalConfidenceManifest
    safety_flags: StatisticalConfidenceSafetyFlags
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
        if not isinstance(self.statistical_confidence_version, str) or not self.statistical_confidence_version.strip():
            raise ValueError("statistical_confidence_version must be a non-empty string")
        if not isinstance(self.source_report_fingerprint, str) or not self.source_report_fingerprint.strip():
            raise ValueError("source_report_fingerprint must be a non-empty string")
        if not isinstance(self.config, StatisticalConfidenceConfig):
            raise ValueError(f"config must be a StatisticalConfidenceConfig, got {self.config!r}")
        if not isinstance(self.metric_results, dict):
            raise ValueError("metric_results must be a dict")
        if not isinstance(self.regime_results, dict):
            raise ValueError("regime_results must be a dict")
        if not isinstance(self.manifest, StatisticalConfidenceManifest):
            raise ValueError(f"manifest must be a StatisticalConfidenceManifest, got {self.manifest!r}")
        if not isinstance(self.safety_flags, StatisticalConfidenceSafetyFlags):
            raise ValueError(f"safety_flags must be a StatisticalConfidenceSafetyFlags, got {self.safety_flags!r}")
        if not isinstance(self.fingerprint, str) or not self.fingerprint.strip():
            raise ValueError("fingerprint must be a non-empty string")
        if not isinstance(self.human_approval_required, bool):
            raise ValueError("human_approval_required must be a boolean")
        if not isinstance(self.research_only, bool):
            raise ValueError("research_only must be a boolean")


# -----------------------------------------------------------------------------
# Error classes
# -----------------------------------------------------------------------------


class StatisticalConfidenceError(Exception):
    """Base exception for the statistical confidence package."""

    def __init__(self, message: str, reason_code: str | None = None) -> None:
        super().__init__(message)
        self.reason_code = reason_code


class StatisticalConfidenceValidationError(StatisticalConfidenceError):
    """Validation failure."""


class StatisticalConfidenceSafetyError(StatisticalConfidenceError):
    """Safety invariant violation."""


class StatisticalConfidenceWriterError(StatisticalConfidenceError):
    """Writer failure."""

    def __init__(self, message: str, reason_code: str | None = None) -> None:
        super().__init__(message, reason_code=reason_code)
