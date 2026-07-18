"""Frozen models and safety contracts for the research evidence ledger (MVP-68 / SPEC-069)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from types import MappingProxyType
from typing import Any

from hunter.research_statistical_confidence.models import (
    ExperimentConfidenceReport,
)
from hunter.research_walk_forward.models import (
    MarketRegimeLabel,
    MetricDirection,
    WalkForwardExperimentPlan,
    WalkForwardExperimentReport,
)

EVIDENCE_LEDGER_VERSION: str = "0.68.0-dev"
SPEC_VERSION: str = "SPEC-069"

UNAVAILABLE: str = "UNAVAILABLE"

# -----------------------------------------------------------------------------
# Reason codes
# -----------------------------------------------------------------------------

INVALID_REGISTRATION = "INVALID_REGISTRATION"
DUPLICATE_ID = "DUPLICATE_ID"
DUPLICATE_FINGERPRINT = "DUPLICATE_FINGERPRINT"
DUPLICATE_EVIDENCE = "DUPLICATE_EVIDENCE"
RESULT_BEFORE_REGISTRATION = "RESULT_BEFORE_REGISTRATION"
MISSING_REGISTRATION = "MISSING_REGISTRATION"
POST_REGISTRATION_MUTATION = "POST_REGISTRATION_MUTATION"
DRIFT_DETECTED = "DRIFT_DETECTED"
DRIFT_IN_STRATEGY = "DRIFT_IN_STRATEGY"
DRIFT_IN_UNIVERSE_PLAN = "DRIFT_IN_UNIVERSE_PLAN"
DRIFT_IN_TIMEFRAME = "DRIFT_IN_TIMEFRAME"
DRIFT_IN_WALK_FORWARD_PLAN = "DRIFT_IN_WALK_FORWARD_PLAN"
DRIFT_IN_METRIC_FAMILY = "DRIFT_IN_METRIC_FAMILY"
DRIFT_IN_CONFIDENCE_CONFIG = "DRIFT_IN_CONFIDENCE_CONFIG"
DRIFT_IN_REGIME_POLICY = "DRIFT_IN_REGIME_POLICY"
DRIFT_IN_DIRECTION_POLICY = "DRIFT_IN_DIRECTION_POLICY"
REPEATED_HYPOTHESIS = "REPEATED_HYPOTHESIS"
INSUFFICIENT_EVIDENCE_CODE = "INSUFFICIENT_EVIDENCE"
INHERITED_SAFETY_VIOLATION = "INHERITED_SAFETY_VIOLATION"
WRITER_ERROR = "WRITER_ERROR"
OUTPUT_DIR_REJECTED = "OUTPUT_DIR_REJECTED"
SNAPSHOT_CHAIN_BROKEN = "SNAPSHOT_CHAIN_BROKEN"
REPLICATION_INSUFFICIENT = "REPLICATION_INSUFFICIENT"
ADJUSTMENT_INVALID_INPUT = "ADJUSTMENT_INVALID_INPUT"
FINGERPRINT_INPUT_MISMATCH = "FINGERPRINT_INPUT_MISMATCH"

EVIDENCE_LEDGER_REASON_CODES: frozenset[str] = frozenset({
    INVALID_REGISTRATION,
    DUPLICATE_ID,
    DUPLICATE_FINGERPRINT,
    DUPLICATE_EVIDENCE,
    RESULT_BEFORE_REGISTRATION,
    MISSING_REGISTRATION,
    POST_REGISTRATION_MUTATION,
    DRIFT_DETECTED,
    DRIFT_IN_STRATEGY,
    DRIFT_IN_UNIVERSE_PLAN,
    DRIFT_IN_TIMEFRAME,
    DRIFT_IN_WALK_FORWARD_PLAN,
    DRIFT_IN_METRIC_FAMILY,
    DRIFT_IN_CONFIDENCE_CONFIG,
    DRIFT_IN_REGIME_POLICY,
    DRIFT_IN_DIRECTION_POLICY,
    REPEATED_HYPOTHESIS,
    INSUFFICIENT_EVIDENCE_CODE,
    INHERITED_SAFETY_VIOLATION,
    WRITER_ERROR,
    OUTPUT_DIR_REJECTED,
    SNAPSHOT_CHAIN_BROKEN,
    REPLICATION_INSUFFICIENT,
    ADJUSTMENT_INVALID_INPUT,
    FINGERPRINT_INPUT_MISMATCH,
})


# -----------------------------------------------------------------------------
# Enums
# -----------------------------------------------------------------------------


class ExperimentStatus(str, Enum):
    """Status of a registered experiment."""
    REGISTERED = "REGISTERED"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    TIMED_OUT = "TIMED_OUT"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    COMPLETED = "COMPLETED"
    WITHDRAWN = "WITHDRAWN"


class IndependenceClass(str, Enum):
    """Caller-provided independence classification for an experiment."""
    INDEPENDENT = "INDEPENDENT"
    RELATED = "RELATED"
    DERIVED = "DERIVED"
    DUPLICATE = "DUPLICATE"
    UNKNOWN = "UNKNOWN"


class AdjustmentMethod(str, Enum):
    """Multiple-testing adjustment method."""
    BENJAMINI_HOCHBERG = "BENJAMINI_HOCHBERG"
    BONFERRONI = "BONFERRONI"


class ReplicationState(str, Enum):
    """Replication state for an experiment metric within a family."""
    NOT_REPLICATED = "NOT_REPLICATED"
    PARTIALLY_REPLICATED = "PARTIALLY_REPLICATED"
    REPLICATED_CANDIDATE = "REPLICATED_CANDIDATE"
    REPLICATED_BASELINE = "REPLICATED_BASELINE"
    CONFLICTING = "CONFLICTING"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


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


def _coerce_mapping_strs(mapping: dict[str, str] | Any | None) -> Any:
    """Return an immutable string mapping."""
    if mapping is None:
        return MappingProxyType({})
    return MappingProxyType({str(k): str(v) for k, v in dict(mapping).items()})


# -----------------------------------------------------------------------------
# Safety flags
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class EvidenceLedgerSafetyFlags:
    """Mandatory safety invariants for every evidence ledger artifact."""

    research_only: bool = True
    execution_approval_granted: bool = False
    production_approval_granted: bool = False
    live_trading_allowed: bool = False
    automatic_execution_allowed: bool = False
    human_approval_required: bool = True
    no_direct_subprocess: bool = True
    no_network_connection: bool = True
    no_database_connection: bool = True
    no_exchange_connection: bool = True
    no_remote_changes: bool = True
    no_action_commands_emitted: bool = True
    no_strategy_mutation: bool = True
    no_universe_mutation: bool = True
    no_config_mutation: bool = True

    def __post_init__(self) -> None:
        for name in (
            "research_only",
            "execution_approval_granted",
            "production_approval_granted",
            "live_trading_allowed",
            "automatic_execution_allowed",
            "human_approval_required",
            "no_direct_subprocess",
            "no_network_connection",
            "no_database_connection",
            "no_exchange_connection",
            "no_remote_changes",
            "no_action_commands_emitted",
            "no_strategy_mutation",
            "no_universe_mutation",
            "no_config_mutation",
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
        if not self.no_network_connection:
            raise ValueError("no_network_connection must be True")
        if not self.no_strategy_mutation:
            raise ValueError("no_strategy_mutation must be True")
        if not self.no_universe_mutation:
            raise ValueError("no_universe_mutation must be True")
        if not self.no_config_mutation:
            raise ValueError("no_config_mutation must be True")


# -----------------------------------------------------------------------------
# Core models
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class ExperimentRegistration:
    """Explicit pre-registration of a research experiment."""

    experiment_id: str
    hypothesis: str
    strategy_name: str
    universe_plan: str
    timeframe: str
    walk_forward_plan_fingerprint: str
    metric_family: tuple[str, ...]
    independence: IndependenceClass
    status: ExperimentStatus = ExperimentStatus.REGISTERED
    hypothesis_family_id: str = ""
    experiment_family_id: str = ""
    confidence_config_fingerprint: str = ""
    regime_policy: str = ""
    direction_policy: str = ""
    notes: str = ""
    fingerprint: str = ""
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    safety_flags: EvidenceLedgerSafetyFlags = field(default_factory=EvidenceLedgerSafetyFlags)
    reason_codes: tuple[str, ...] = ()
    metadata: Any = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))
        object.__setattr__(self, "metric_family", tuple(dict.fromkeys(sorted(str(v) for v in self.metric_family))))
        if not isinstance(self.experiment_id, str) or not self.experiment_id.strip():
            raise ValueError("experiment_id must be a non-empty string")
        if not isinstance(self.hypothesis, str) or not self.hypothesis.strip():
            raise ValueError("hypothesis must be a non-empty string")
        if not isinstance(self.strategy_name, str) or not self.strategy_name.strip():
            raise ValueError("strategy_name must be a non-empty string")
        if not isinstance(self.universe_plan, str) or not self.universe_plan.strip():
            raise ValueError("universe_plan must be a non-empty string")
        if not isinstance(self.timeframe, str) or not self.timeframe.strip():
            raise ValueError("timeframe must be a non-empty string")
        if not isinstance(self.walk_forward_plan_fingerprint, str) or not self.walk_forward_plan_fingerprint.strip():
            raise ValueError("walk_forward_plan_fingerprint must be a non-empty string")
        if not self.metric_family:
            raise ValueError("metric_family must not be empty")
        if not isinstance(self.independence, IndependenceClass):
            raise ValueError(f"independence must be an IndependenceClass, got {self.independence!r}")
        if not isinstance(self.status, ExperimentStatus):
            raise ValueError(f"status must be an ExperimentStatus, got {self.status!r}")
        if not isinstance(self.safety_flags, EvidenceLedgerSafetyFlags):
            raise ValueError(f"safety_flags must be EvidenceLedgerSafetyFlags, got {self.safety_flags!r}")
        if not isinstance(self.registered_at, datetime) or self.registered_at.tzinfo is None:
            raise ValueError("registered_at must be a timezone-aware datetime")


@dataclass(frozen=True)
class ExperimentEvidence:
    """Evidence from a completed experiment (walk-forward + confidence)."""

    experiment_id: str
    walk_forward_report: WalkForwardExperimentReport | None = None
    confidence_report: ExperimentConfidenceReport | None = None
    evidence_fingerprint: str = ""
    walk_forward_fingerprint: str = ""
    confidence_fingerprint: str = ""
    registration_fingerprint: str = ""
    reason_codes: tuple[str, ...] = ()
    metadata: Any = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))
        if not isinstance(self.experiment_id, str) or not self.experiment_id.strip():
            raise ValueError("experiment_id must be a non-empty string")
        if self.walk_forward_report is not None and not isinstance(self.walk_forward_report, WalkForwardExperimentReport):
            raise ValueError(f"walk_forward_report must be a WalkForwardExperimentReport or None, got {self.walk_forward_report!r}")
        if self.confidence_report is not None and not isinstance(self.confidence_report, ExperimentConfidenceReport):
            raise ValueError(f"confidence_report must be an ExperimentConfidenceReport or None, got {self.confidence_report!r}")


@dataclass(frozen=True)
class EvidenceLedgerEntry:
    """A fully resolved ledger entry combining registration and evidence."""

    registration: ExperimentRegistration
    status: ExperimentStatus
    evidence: ExperimentEvidence | None = None
    fingerprint: str = ""
    reason_codes: tuple[str, ...] = ()
    metadata: Any = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))
        if not isinstance(self.registration, ExperimentRegistration):
            raise ValueError(f"registration must be an ExperimentRegistration, got {self.registration!r}")
        if self.evidence is not None and not isinstance(self.evidence, ExperimentEvidence):
            raise ValueError(f"evidence must be an ExperimentEvidence or None, got {self.evidence!r}")
        if not isinstance(self.status, ExperimentStatus):
            raise ValueError(f"status must be an ExperimentStatus, got {self.status!r}")
        if not isinstance(self.fingerprint, str):
            raise ValueError("fingerprint must be a string")


# -----------------------------------------------------------------------------
# Family models
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class HypothesisFamily:
    """A family of experiments sharing the same hypothesis."""

    hypothesis_family_id: str
    hypothesis: str
    experiment_ids: tuple[str, ...]
    metric_names: tuple[str, ...]
    fingerprint: str = ""
    reason_codes: tuple[str, ...] = ()
    metadata: Any = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))
        if not isinstance(self.hypothesis_family_id, str) or not self.hypothesis_family_id.strip():
            raise ValueError("hypothesis_family_id must be a non-empty string")
        if not isinstance(self.hypothesis, str) or not self.hypothesis.strip():
            raise ValueError("hypothesis must be a non-empty string")
        if not isinstance(self.experiment_ids, tuple):
            raise ValueError("experiment_ids must be a tuple")
        if not isinstance(self.metric_names, tuple):
            raise ValueError("metric_names must be a tuple")


@dataclass(frozen=True)
class ExperimentFamily:
    """A family of experiments sharing the same experiment design."""

    experiment_family_id: str
    strategy_name: str
    universe_plan: str
    timeframe: str
    walk_forward_plan_fingerprint: str
    experiment_ids: tuple[str, ...]
    metric_names: tuple[str, ...]
    fingerprint: str = ""
    reason_codes: tuple[str, ...] = ()
    metadata: Any = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))
        if not isinstance(self.experiment_family_id, str) or not self.experiment_family_id.strip():
            raise ValueError("experiment_family_id must be a non-empty string")
        if not isinstance(self.strategy_name, str) or not self.strategy_name.strip():
            raise ValueError("strategy_name must be a non-empty string")
        if not isinstance(self.universe_plan, str) or not self.universe_plan.strip():
            raise ValueError("universe_plan must be a non-empty string")
        if not isinstance(self.timeframe, str) or not self.timeframe.strip():
            raise ValueError("timeframe must be a non-empty string")
        if not isinstance(self.walk_forward_plan_fingerprint, str) or not self.walk_forward_plan_fingerprint.strip():
            raise ValueError("walk_forward_plan_fingerprint must be a non-empty string")
        if not isinstance(self.experiment_ids, tuple):
            raise ValueError("experiment_ids must be a tuple")
        if not isinstance(self.metric_names, tuple):
            raise ValueError("metric_names must be a tuple")


@dataclass(frozen=True)
class MetricFamily:
    """A family of metric names shared across experiments."""

    metric_names: tuple[str, ...]
    fingerprint: str = ""
    reason_codes: tuple[str, ...] = ()
    metadata: Any = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))
        if not isinstance(self.metric_names, tuple):
            raise ValueError("metric_names must be a tuple")
        if not self.metric_names:
            raise ValueError("metric_names must not be empty")


# -----------------------------------------------------------------------------
# Adjustment models
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class AdjustmentConfig:
    """Configuration for multiple-testing adjustment."""

    method: AdjustmentMethod
    alpha: Decimal
    family_id: str
    family_type: str  # "hypothesis" or "experiment" or "metric"
    family_size: int = 0  # Number of tests in the family; 0 = use raw value count
    reason_codes: tuple[str, ...] = ()
    metadata: Any = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))
        if not isinstance(self.method, AdjustmentMethod):
            raise ValueError(f"method must be an AdjustmentMethod, got {self.method!r}")
        object.__setattr__(self, "alpha", _coerce_decimal(self.alpha))
        if self.alpha is None or self.alpha <= Decimal("0") or self.alpha > Decimal("1"):
            raise ValueError("alpha must be in (0, 1]")
        if not isinstance(self.family_id, str) or not self.family_id.strip():
            raise ValueError("family_id must be a non-empty string")
        if self.family_type not in ("hypothesis", "experiment", "metric"):
            raise ValueError(f"family_type must be hypothesis/experiment/metric, got {self.family_type!r}")
        if not isinstance(self.family_size, int) or self.family_size < 0:
            raise ValueError("family_size must be a non-negative integer")


@dataclass(frozen=True)
class AdjustedEvidence:
    """Raw and multiple-testing-adjusted evidence value for one experiment/metric."""

    experiment_id: str
    metric_name: str
    raw_value: Decimal
    adjusted_value: Decimal
    family_id: str
    family_type: str
    method: AdjustmentMethod
    rank: int
    family_size: int
    alpha: Decimal
    fingerprint: str = ""
    reason_codes: tuple[str, ...] = ()
    metadata: Any = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))
        if not isinstance(self.experiment_id, str) or not self.experiment_id.strip():
            raise ValueError("experiment_id must be a non-empty string")
        if not isinstance(self.metric_name, str) or not self.metric_name.strip():
            raise ValueError("metric_name must be a non-empty string")
        object.__setattr__(self, "raw_value", _coerce_decimal(self.raw_value))
        object.__setattr__(self, "adjusted_value", _coerce_decimal(self.adjusted_value))
        object.__setattr__(self, "alpha", _coerce_decimal(self.alpha))
        if self.raw_value is None:
            raise ValueError("raw_value must not be None")
        if self.adjusted_value is None:
            raise ValueError("adjusted_value must not be None")
        if self.alpha is None:
            raise ValueError("alpha must not be None")
        if not isinstance(self.family_id, str) or not self.family_id.strip():
            raise ValueError("family_id must be a non-empty string")
        if self.family_type not in ("hypothesis", "experiment", "metric"):
            raise ValueError(f"family_type must be hypothesis/experiment/metric, got {self.family_type!r}")
        if not isinstance(self.method, AdjustmentMethod):
            raise ValueError(f"method must be an AdjustmentMethod, got {self.method!r}")
        if not isinstance(self.rank, int) or self.rank < 1:
            raise ValueError("rank must be a positive integer")
        if not isinstance(self.family_size, int) or self.family_size < 1:
            raise ValueError("family_size must be a positive integer")


# -----------------------------------------------------------------------------
# Replication models
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class ReplicationResult:
    """Replication analysis result for one experiment-metric pair in a family."""

    experiment_id: str
    metric_name: str
    family_id: str
    family_type: str
    state: ReplicationState
    candidate_count: int
    baseline_count: int
    independent_count: int
    direction: MetricDirection | None
    fingerprint: str = ""
    reason_codes: tuple[str, ...] = ()
    metadata: Any = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))
        if not isinstance(self.experiment_id, str) or not self.experiment_id.strip():
            raise ValueError("experiment_id must be a non-empty string")
        if not isinstance(self.metric_name, str) or not self.metric_name.strip():
            raise ValueError("metric_name must be a non-empty string")
        if not isinstance(self.family_id, str) or not self.family_id.strip():
            raise ValueError("family_id must be a non-empty string")
        if self.family_type not in ("hypothesis", "experiment", "metric"):
            raise ValueError(f"family_type must be hypothesis/experiment/metric, got {self.family_type!r}")
        if not isinstance(self.state, ReplicationState):
            raise ValueError(f"state must be a ReplicationState, got {self.state!r}")
        if not isinstance(self.candidate_count, int) or self.candidate_count < 0:
            raise ValueError("candidate_count must be a non-negative integer")
        if not isinstance(self.baseline_count, int) or self.baseline_count < 0:
            raise ValueError("baseline_count must be a non-negative integer")
        if not isinstance(self.independent_count, int) or self.independent_count < 0:
            raise ValueError("independent_count must be a non-negative integer")
        if self.direction is not None and not isinstance(self.direction, MetricDirection):
            raise ValueError(f"direction must be a MetricDirection or None, got {self.direction!r}")


# -----------------------------------------------------------------------------
# Snapshot models
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class LedgerSnapshot:
    """An immutable snapshot of the evidence ledger at a point in time."""

    version: str
    spec_version: str
    snapshot_id: str
    previous_snapshot_fingerprint: str
    entry_fingerprints: tuple[str, ...]
    family_fingerprints: tuple[str, ...]
    adjustment_fingerprints: tuple[str, ...]
    replication_fingerprints: tuple[str, ...]
    fingerprint: str = ""
    reason_codes: tuple[str, ...] = ()
    metadata: Any = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))
        if not isinstance(self.version, str) or not self.version.strip():
            raise ValueError("version must be a non-empty string")
        if not isinstance(self.spec_version, str) or not self.spec_version.strip():
            raise ValueError("spec_version must be a non-empty string")
        if not isinstance(self.snapshot_id, str) or not self.snapshot_id.strip():
            raise ValueError("snapshot_id must be a non-empty string")
        if not isinstance(self.previous_snapshot_fingerprint, str):
            raise ValueError("previous_snapshot_fingerprint must be a string")
        if not isinstance(self.entry_fingerprints, tuple):
            raise ValueError("entry_fingerprints must be a tuple")
        if not isinstance(self.family_fingerprints, tuple):
            raise ValueError("family_fingerprints must be a tuple")
        if not isinstance(self.adjustment_fingerprints, tuple):
            raise ValueError("adjustment_fingerprints must be a tuple")
        if not isinstance(self.replication_fingerprints, tuple):
            raise ValueError("replication_fingerprints must be a tuple")


# -----------------------------------------------------------------------------
# Manifest and Report
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class EvidenceLedgerManifest:
    """Lightweight manifest summarizing evidence ledger artifacts."""

    version: str
    spec_version: str
    evidence_ledger_version: str
    generated_at: datetime
    entry_count: int
    family_count: int
    adjustment_count: int
    replication_count: int
    snapshot_fingerprint: str
    overall_fingerprint: str
    safety_flags: EvidenceLedgerSafetyFlags
    reason_codes: tuple[str, ...] = ()
    metadata: Any = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))
        if not isinstance(self.version, str) or not self.version.strip():
            raise ValueError("version must be a non-empty string")
        if not isinstance(self.spec_version, str) or not self.spec_version.strip():
            raise ValueError("spec_version must be a non-empty string")
        if not isinstance(self.evidence_ledger_version, str) or not self.evidence_ledger_version.strip():
            raise ValueError("evidence_ledger_version must be a non-empty string")
        if not isinstance(self.generated_at, datetime) or self.generated_at.tzinfo is None:
            raise ValueError("generated_at must be a timezone-aware datetime")
        if not isinstance(self.entry_count, int) or self.entry_count < 0:
            raise ValueError("entry_count must be a non-negative integer")
        if not isinstance(self.family_count, int) or self.family_count < 0:
            raise ValueError("family_count must be a non-negative integer")
        if not isinstance(self.adjustment_count, int) or self.adjustment_count < 0:
            raise ValueError("adjustment_count must be a non-negative integer")
        if not isinstance(self.replication_count, int) or self.replication_count < 0:
            raise ValueError("replication_count must be a non-negative integer")
        if not isinstance(self.snapshot_fingerprint, str) or not self.snapshot_fingerprint.strip():
            raise ValueError("snapshot_fingerprint must be a non-empty string")
        if not isinstance(self.overall_fingerprint, str) or not self.overall_fingerprint.strip():
            raise ValueError("overall_fingerprint must be a non-empty string")
        if not isinstance(self.safety_flags, EvidenceLedgerSafetyFlags):
            raise ValueError(f"safety_flags must be EvidenceLedgerSafetyFlags, got {self.safety_flags!r}")


@dataclass(frozen=True)
class EvidenceLedgerReport:
    """Top-level evidence ledger report."""

    version: str
    spec_version: str
    evidence_ledger_version: str
    registrations: tuple[ExperimentRegistration, ...]
    entries: tuple[EvidenceLedgerEntry, ...]
    hypothesis_families: tuple[HypothesisFamily, ...]
    experiment_families: tuple[ExperimentFamily, ...]
    metric_families: tuple[MetricFamily, ...]
    adjustments: tuple[AdjustedEvidence, ...]
    replications: tuple[ReplicationResult, ...]
    snapshot: LedgerSnapshot
    manifest: EvidenceLedgerManifest
    safety_flags: EvidenceLedgerSafetyFlags
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
        if not isinstance(self.evidence_ledger_version, str) or not self.evidence_ledger_version.strip():
            raise ValueError("evidence_ledger_version must be a non-empty string")
        if not isinstance(self.fingerprint, str) or not self.fingerprint.strip():
            raise ValueError("fingerprint must be a non-empty string")
        if not isinstance(self.safety_flags, EvidenceLedgerSafetyFlags):
            raise ValueError(f"safety_flags must be EvidenceLedgerSafetyFlags, got {self.safety_flags!r}")
        if not isinstance(self.snapshot, LedgerSnapshot):
            raise ValueError(f"snapshot must be a LedgerSnapshot, got {self.snapshot!r}")
        if not isinstance(self.manifest, EvidenceLedgerManifest):
            raise ValueError(f"manifest must be an EvidenceLedgerManifest, got {self.manifest!r}")
        if not isinstance(self.human_approval_required, bool):
            raise ValueError("human_approval_required must be a boolean")
        if not isinstance(self.research_only, bool):
            raise ValueError("research_only must be a boolean")


# -----------------------------------------------------------------------------
# Error classes
# -----------------------------------------------------------------------------


class EvidenceLedgerError(Exception):
    """Base exception for the evidence ledger package."""

    def __init__(self, message: str, reason_code: str | None = None) -> None:
        super().__init__(message)
        self.reason_code = reason_code


class EvidenceLedgerValidationError(EvidenceLedgerError):
    """Validation failure."""


class EvidenceLedgerSafetyError(EvidenceLedgerError):
    """Safety invariant violation."""


class EvidenceLedgerDuplicateError(EvidenceLedgerError):
    """Duplicate detection failure."""


class EvidenceLedgerDriftError(EvidenceLedgerError):
    """Drift detection failure."""


class EvidenceLedgerAdjustmentError(EvidenceLedgerError):
    """Adjustment computation failure."""


class EvidenceLedgerReplicationError(EvidenceLedgerError):
    """Replication analysis failure."""


class EvidenceLedgerSnapshotError(EvidenceLedgerError):
    """Snapshot chain failure."""


class EvidenceLedgerWriterError(EvidenceLedgerError):
    """Writer failure."""

    def __init__(self, message: str, reason_code: str | None = None) -> None:
        super().__init__(message, reason_code=reason_code)


class EvidenceLedgerRegistrationError(EvidenceLedgerError):
    """Registration failure."""
