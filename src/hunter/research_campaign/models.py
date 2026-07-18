"""Frozen models and safety contracts for the research campaign compiler and batch orchestrator (MVP-69/MVP-70 / SPEC-070)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any

from hunter.research_evidence_ledger.models import (
    EvidenceLedgerEntry,
    LedgerSnapshot as EvidenceLedgerSnapshot,
    ExperimentRegistration,
    IndependenceClass,
)
from hunter.research_statistical_confidence.models import (
    ExperimentConfidenceReport,
    StatisticalConfidenceConfig,
)
from hunter.research_walk_forward.models import (
    MarketRegimeLabel,
    WalkForwardCommonConfig,
    WalkForwardExperimentPlan,
    WalkForwardExperimentReport,
)

RESEARCH_CAMPAIGN_VERSION: str = "0.70.0-dev"
SPEC_VERSION: str = "SPEC-070"

UNAVAILABLE: str = "UNAVAILABLE"

# ---------------------------------------------------------------------------
# Reason codes
# ---------------------------------------------------------------------------

INVALID_DEFINITION = "INVALID_DEFINITION"
EMPTY_PARAMETER_SET = "EMPTY_PARAMETER_SET"
MUTABLE_PARAMETER_SET = "MUTABLE_PARAMETER_SET"
NON_CANONICAL_PARAMETER_SET = "NON_CANONICAL_PARAMETER_SET"
CONTRADICTORY_FILTER_RULES = "CONTRADICTORY_FILTER_RULES"
INVALID_FILTER_RULE = "INVALID_FILTER_RULE"
DUPLICATE_LOGICAL_EXPERIMENT = "DUPLICATE_LOGICAL_EXPERIMENT"
ZERO_EXPERIMENT_CAMPAIGN = "ZERO_EXPERIMENT_CAMPAIGN"
MAX_EXPERIMENT_COUNT_EXCEEDED = "MAX_EXPERIMENT_COUNT_EXCEEDED"
INVALID_MAX_EXPERIMENT_COUNT = "INVALID_MAX_EXPERIMENT_COUNT"
MISSING_REGISTRATION = "MISSING_REGISTRATION"
REGISTRATION_DRIFT = "REGISTRATION_DRIFT"
EXPERIMENT_FINGERPRINT_MISMATCH = "EXPERIMENT_FINGERPRINT_MISMATCH"
RESUME_FINGERPRINT_MISMATCH = "RESUME_FINGERPRINT_MISMATCH"
STALE_RESUME_EVIDENCE = "STALE_RESUME_EVIDENCE"
EXECUTION_POLICY_VIOLATION = "EXECUTION_POLICY_VIOLATION"
RUNNER_ERROR = "RUNNER_ERROR"
WRITER_ERROR = "WRITER_ERROR"
OUTPUT_DIR_REJECTED = "OUTPUT_DIR_REJECTED"
SILENT_OVERWRITE_BLOCKED = "SILENT_OVERWRITE_BLOCKED"
INHERITED_SAFETY_VIOLATION = "INHERITED_SAFETY_VIOLATION"
COMPILATION_ONLY_MODE = "COMPILATION_ONLY_MODE"
STOPPED_BY_POLICY = "STOPPED_BY_POLICY"
INVALID_RESUME_POLICY = "INVALID_RESUME_POLICY"
MISSING_WALK_FORWARD_EVIDENCE = "MISSING_WALK_FORWARD_EVIDENCE"
MISSING_CONFIDENCE_EVIDENCE = "MISSING_CONFIDENCE_EVIDENCE"

RESEARCH_CAMPAIGN_REASON_CODES: frozenset[str] = frozenset({
    INVALID_DEFINITION,
    EMPTY_PARAMETER_SET,
    MUTABLE_PARAMETER_SET,
    NON_CANONICAL_PARAMETER_SET,
    CONTRADICTORY_FILTER_RULES,
    INVALID_FILTER_RULE,
    DUPLICATE_LOGICAL_EXPERIMENT,
    ZERO_EXPERIMENT_CAMPAIGN,
    MAX_EXPERIMENT_COUNT_EXCEEDED,
    INVALID_MAX_EXPERIMENT_COUNT,
    MISSING_REGISTRATION,
    REGISTRATION_DRIFT,
    EXPERIMENT_FINGERPRINT_MISMATCH,
    RESUME_FINGERPRINT_MISMATCH,
    STALE_RESUME_EVIDENCE,
    EXECUTION_POLICY_VIOLATION,
    RUNNER_ERROR,
    WRITER_ERROR,
    OUTPUT_DIR_REJECTED,
    SILENT_OVERWRITE_BLOCKED,
    INHERITED_SAFETY_VIOLATION,
    COMPILATION_ONLY_MODE,
    STOPPED_BY_POLICY,
    INVALID_RESUME_POLICY,
    MISSING_WALK_FORWARD_EVIDENCE,
    MISSING_CONFIDENCE_EVIDENCE,
})

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class FilterOperator(str, Enum):
    """Declarative, immutable filter operator."""

    EQUALS = "EQUALS"
    NOT_EQUALS = "NOT_EQUALS"
    IN = "IN"
    NOT_IN = "NOT_IN"
    PREFIX = "PREFIX"
    MATCH_ALL = "MATCH_ALL"


class CampaignExecutionPolicy(str, Enum):
    """How the batch runner handles failures during campaign execution."""

    COLLECT_ALL = "COLLECT_ALL"
    FAIL_FAST = "FAIL_FAST"
    STOP_AFTER_N_FAILURES = "STOP_AFTER_N_FAILURES"


class ResumePolicy(str, Enum):
    """How to handle stale or missing prior evidence on resume."""

    REUSE = "REUSE"
    RERUN = "RERUN"
    BLOCK = "BLOCK"


class CampaignStatus(str, Enum):
    """Overall status of a campaign execution."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    STOPPED = "STOPPED"


class ExperimentOutcome(str, Enum):
    """Terminal outcome of a single compiled experiment attempt."""

    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    TIMED_OUT = "TIMED_OUT"
    UNSUPPORTED = "UNSUPPORTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    WITHDRAWN = "WITHDRAWN"
    SKIPPED_BY_POLICY = "SKIPPED_BY_POLICY"
    STALE_RESUME_EVIDENCE = "STALE_RESUME_EVIDENCE"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Safety flags
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ResearchCampaignSafetyFlags:
    """Mandatory safety invariants for every research campaign artifact."""

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
            "no_action_commands_emitted",
            "no_network_connection",
            "no_database_connection",
            "no_exchange_connection",
            "no_remote_changes",
            "no_parallel_execution",
            "no_direct_subprocess",
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
        if not self.no_parallel_execution:
            raise ValueError("no_parallel_execution must be True")


# ---------------------------------------------------------------------------
# Reference objects (explicit, caller-provided parameters)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StrategyReference:
    """Reference to a strategy for a campaign parameter."""

    strategy_name: str
    strategy_path: str | Path
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.strategy_name, str) or not self.strategy_name.strip():
            raise ValueError("strategy_name must be a non-empty string")
        object.__setattr__(self, "strategy_path", str(Path(self.strategy_path)))


@dataclass(frozen=True)
class HistoricalDataReference:
    """Reference to a historical dataset for a campaign parameter."""

    data_id: str
    data_path: str | Path
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.data_id, str) or not self.data_id.strip():
            raise ValueError("data_id must be a non-empty string")
        object.__setattr__(self, "data_path", str(Path(self.data_path)))


@dataclass(frozen=True)
class UniversePlanReference:
    """Reference to a Candidate/Baseline universe plan for a campaign parameter."""

    universe_plan_id: str
    universe_plan_path: str | Path
    candidate_pairlist: tuple[str, ...]
    baseline_pairlist: tuple[str, ...]
    candidate_universe_fingerprint: str
    baseline_universe_fingerprint: str
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.universe_plan_id, str) or not self.universe_plan_id.strip():
            raise ValueError("universe_plan_id must be a non-empty string")
        object.__setattr__(self, "universe_plan_path", str(Path(self.universe_plan_path)))
        object.__setattr__(self, "candidate_pairlist", _coerce_tuple_strs(self.candidate_pairlist))
        object.__setattr__(self, "baseline_pairlist", _coerce_tuple_strs(self.baseline_pairlist))
        if not isinstance(self.candidate_universe_fingerprint, str) or not self.candidate_universe_fingerprint.strip():
            raise ValueError("candidate_universe_fingerprint must be a non-empty string")
        if not isinstance(self.baseline_universe_fingerprint, str) or not self.baseline_universe_fingerprint.strip():
            raise ValueError("baseline_universe_fingerprint must be a non-empty string")


@dataclass(frozen=True)
class WalkForwardTemplateReference:
    """Reference to a walk-forward template for a campaign parameter."""

    template_id: str
    mode: str
    windows: tuple[Any, ...]
    contiguous: bool = False
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.template_id, str) or not self.template_id.strip():
            raise ValueError("template_id must be a non-empty string")
        if not isinstance(self.mode, str) or not self.mode.strip():
            raise ValueError("mode must be a non-empty string")
        if not isinstance(self.windows, tuple):
            raise ValueError("windows must be a tuple")


@dataclass(frozen=True)
class StatisticalConfidenceConfigReference:
    """Reference to a statistical confidence configuration for a campaign parameter."""

    config_id: str
    config: StatisticalConfidenceConfig
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.config_id, str) or not self.config_id.strip():
            raise ValueError("config_id must be a non-empty string")
        if not isinstance(self.config, StatisticalConfidenceConfig):
            raise ValueError(f"config must be a StatisticalConfidenceConfig, got {self.config!r}")


@dataclass(frozen=True)
class FamilyReference:
    """Reference to an experiment, hypothesis, or metric family."""

    family_id: str
    family_type: str
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.family_id, str) or not self.family_id.strip():
            raise ValueError("family_id must be a non-empty string")
        if not isinstance(self.family_type, str) or not self.family_type.strip():
            raise ValueError("family_type must be a non-empty string")


@dataclass(frozen=True)
class MetricFamilyScope:
    """Scope of metrics included in an experiment."""

    metric_names: tuple[str, ...]
    direction_policy: str = "ANY"

    def __post_init__(self) -> None:
        object.__setattr__(self, "metric_names", _coerce_tuple_strs(self.metric_names))
        if not isinstance(self.direction_policy, str) or not self.direction_policy.strip():
            raise ValueError("direction_policy must be a non-empty string")


@dataclass(frozen=True)
class RegimePolicy:
    """Regime-label policy for an experiment."""

    regime_label: MarketRegimeLabel | str
    required: bool = False
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if isinstance(self.regime_label, str):
            object.__setattr__(self, "regime_label", MarketRegimeLabel(self.regime_label))
        elif not isinstance(self.regime_label, MarketRegimeLabel):
            raise ValueError(f"regime_label must be a MarketRegimeLabel or str, got {self.regime_label!r}")


@dataclass(frozen=True)
class IndependenceMetadata:
    """Independence classification and related metadata for an experiment."""

    independence_class: IndependenceClass | str
    source_experiment_ids: tuple[str, ...] = ()
    notes: str = ""
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if isinstance(self.independence_class, str):
            object.__setattr__(self, "independence_class", IndependenceClass(self.independence_class))
        elif not isinstance(self.independence_class, IndependenceClass):
            raise ValueError(f"independence_class must be an IndependenceClass or str, got {self.independence_class!r}")
        object.__setattr__(self, "source_experiment_ids", _coerce_tuple_strs(self.source_experiment_ids))


# ---------------------------------------------------------------------------
# Campaign parameter set and filter rules
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CampaignFilterRule:
    """Declarative include/exclude rule for a campaign parameter."""

    field: str
    operator: FilterOperator | str
    value: Any
    action: str  # "include" or "exclude"

    def __post_init__(self) -> None:
        if not isinstance(self.field, str) or not self.field.strip():
            raise ValueError("field must be a non-empty string")
        if isinstance(self.operator, str):
            object.__setattr__(self, "operator", FilterOperator(self.operator))
        elif not isinstance(self.operator, FilterOperator):
            raise ValueError(f"operator must be a FilterOperator or str, got {self.operator!r}")
        if self.action not in ("include", "exclude"):
            raise ValueError(f"action must be 'include' or 'exclude', got {self.action!r}")
        if self.operator in (FilterOperator.IN, FilterOperator.NOT_IN) and not isinstance(self.value, tuple):
            raise ValueError(f"operator {self.operator.value} requires a tuple value")


@dataclass(frozen=True)
class CampaignParameterSet:
    """Explicit set of parameter values for campaign compilation."""

    common_config: WalkForwardCommonConfig
    strategies: tuple[StrategyReference, ...]
    timeframes: tuple[str, ...]
    historical_data: tuple[HistoricalDataReference, ...]
    universe_plans: tuple[UniversePlanReference, ...]
    walk_forward_templates: tuple[WalkForwardTemplateReference, ...]
    confidence_configs: tuple[StatisticalConfidenceConfigReference, ...]
    experiment_families: tuple[FamilyReference, ...]
    hypothesis_families: tuple[FamilyReference, ...]
    metric_families: tuple[MetricFamilyScope, ...]
    independence_metadata: tuple[IndependenceMetadata, ...]
    regime_policies: tuple[RegimePolicy, ...]
    include_rules: tuple[CampaignFilterRule, ...] = ()
    exclude_rules: tuple[CampaignFilterRule, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.common_config, WalkForwardCommonConfig):
            raise ValueError(f"common_config must be a WalkForwardCommonConfig, got {self.common_config!r}")
        # All sequences must be tuples (immutable / canonical)
        for name, value in (
            ("strategies", self.strategies),
            ("timeframes", self.timeframes),
            ("historical_data", self.historical_data),
            ("universe_plans", self.universe_plans),
            ("walk_forward_templates", self.walk_forward_templates),
            ("confidence_configs", self.confidence_configs),
            ("experiment_families", self.experiment_families),
            ("hypothesis_families", self.hypothesis_families),
            ("metric_families", self.metric_families),
            ("independence_metadata", self.independence_metadata),
            ("regime_policies", self.regime_policies),
            ("include_rules", self.include_rules),
            ("exclude_rules", self.exclude_rules),
        ):
            if not isinstance(value, tuple):
                raise ValueError(f"{name} must be a tuple, got {type(value).__name__}")
        # Non-empty check for all parameter sets
        for name, value in (
            ("strategies", self.strategies),
            ("timeframes", self.timeframes),
            ("historical_data", self.historical_data),
            ("universe_plans", self.universe_plans),
            ("walk_forward_templates", self.walk_forward_templates),
            ("confidence_configs", self.confidence_configs),
            ("experiment_families", self.experiment_families),
            ("hypothesis_families", self.hypothesis_families),
            ("metric_families", self.metric_families),
            ("independence_metadata", self.independence_metadata),
            ("regime_policies", self.regime_policies),
        ):
            if len(value) == 0:
                raise ValueError(f"{name} must not be empty")


# ---------------------------------------------------------------------------
# Output policy
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CampaignOutputPolicy:
    """Policy for where and how campaign artifacts are written."""

    output_dir: str | Path
    overwrite: bool = False
    write_checkpoints: bool = True
    checkpoint_version_policy: str = "SEQUENTIAL"

    def __post_init__(self) -> None:
        object.__setattr__(self, "output_dir", str(Path(self.output_dir)))
        if not isinstance(self.overwrite, bool):
            raise ValueError("overwrite must be a bool")
        if not isinstance(self.write_checkpoints, bool):
            raise ValueError("write_checkpoints must be a bool")
        if self.checkpoint_version_policy not in ("SEQUENTIAL", "REPLACE"):
            raise ValueError("checkpoint_version_policy must be 'SEQUENTIAL' or 'REPLACE'")


# ---------------------------------------------------------------------------
# Campaign definition
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ResearchCampaignDefinition:
    """Explicit, immutable campaign definition."""

    campaign_id: str
    campaign_schema_version: str
    parameters: CampaignParameterSet
    max_experiment_count: int
    execution_policy: CampaignExecutionPolicy | str
    stop_after_n_failures: int | None = None
    resume_policy: ResumePolicy | str = ResumePolicy.RERUN
    output_policy: CampaignOutputPolicy | None = None
    safety_flags: ResearchCampaignSafetyFlags = field(default_factory=ResearchCampaignSafetyFlags)
    reason_codes: tuple[str, ...] = ()
    metadata: Any = field(default_factory=dict)
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.campaign_id, str) or not self.campaign_id.strip():
            raise ValueError("campaign_id must be a non-empty string")
        if not isinstance(self.campaign_schema_version, str) or not self.campaign_schema_version.strip():
            raise ValueError("campaign_schema_version must be a non-empty string")
        if not isinstance(self.parameters, CampaignParameterSet):
            raise ValueError(f"parameters must be a CampaignParameterSet, got {self.parameters!r}")
        if not isinstance(self.max_experiment_count, int) or self.max_experiment_count < 1:
            from hunter.research_campaign.errors import ResearchCampaignDefinitionError
            raise ResearchCampaignDefinitionError("max_experiment_count must be a positive integer")
        if isinstance(self.execution_policy, str):
            object.__setattr__(self, "execution_policy", CampaignExecutionPolicy(self.execution_policy))
        elif not isinstance(self.execution_policy, CampaignExecutionPolicy):
            raise ValueError(f"execution_policy must be a CampaignExecutionPolicy or str, got {self.execution_policy!r}")
        if self.execution_policy == CampaignExecutionPolicy.STOP_AFTER_N_FAILURES:
            if not isinstance(self.stop_after_n_failures, int) or self.stop_after_n_failures < 1:
                raise ValueError("stop_after_n_failures must be a positive integer for STOP_AFTER_N_FAILURES policy")
        else:
            if self.stop_after_n_failures is not None:
                raise ValueError("stop_after_n_failures must be None unless execution_policy is STOP_AFTER_N_FAILURES")
        if isinstance(self.resume_policy, str):
            object.__setattr__(self, "resume_policy", ResumePolicy(self.resume_policy))
        elif not isinstance(self.resume_policy, ResumePolicy):
            raise ValueError(f"resume_policy must be a ResumePolicy or str, got {self.resume_policy!r}")
        if self.output_policy is not None and not isinstance(self.output_policy, CampaignOutputPolicy):
            raise ValueError(f"output_policy must be a CampaignOutputPolicy or None, got {self.output_policy!r}")
        if not isinstance(self.safety_flags, ResearchCampaignSafetyFlags):
            raise ValueError(f"safety_flags must be a ResearchCampaignSafetyFlags, got {self.safety_flags!r}")
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))


# ---------------------------------------------------------------------------
# Compiled experiment and campaign
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CompiledExperiment:
    """A single compiled experiment in the campaign matrix."""

    experiment_id: str
    campaign_id: str
    strategy: StrategyReference
    timeframe: str
    historical_data: HistoricalDataReference
    universe_plan: UniversePlanReference
    walk_forward_template: WalkForwardTemplateReference
    confidence_config: StatisticalConfidenceConfigReference
    experiment_family: FamilyReference
    hypothesis_family: FamilyReference
    metric_family: MetricFamilyScope
    independence: IndependenceMetadata
    regime_policy: RegimePolicy
    walk_forward_plan: WalkForwardExperimentPlan
    fingerprint: str = ""
    registration_fingerprint: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.experiment_id, str) or not self.experiment_id.strip():
            raise ValueError("experiment_id must be a non-empty string")
        if not isinstance(self.campaign_id, str) or not self.campaign_id.strip():
            raise ValueError("campaign_id must be a non-empty string")


@dataclass(frozen=True)
class CompiledCampaign:
    """Immutable compiled campaign matrix."""

    campaign: ResearchCampaignDefinition
    experiments: tuple[CompiledExperiment, ...]
    experiment_count: int
    excluded_count: int
    fingerprint: str
    compile_timestamp: datetime
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))
        if not isinstance(self.compile_timestamp, datetime):
            raise ValueError("compile_timestamp must be a datetime")
        if self.experiment_count != len(self.experiments):
            raise ValueError("experiment_count must match len(experiments)")


# ---------------------------------------------------------------------------
# Pre-registration and execution manifest
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CampaignRegistrationSet:
    """Immutable pre-registration records for a compiled campaign."""

    campaign: CompiledCampaign
    registrations: tuple[ExperimentRegistration, ...]
    registration_by_experiment_id: MappingProxyType = field(default_factory=dict)
    fingerprint: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.registration_by_experiment_id, MappingProxyType):
            object.__setattr__(
                self,
                "registration_by_experiment_id",
                MappingProxyType(dict(self.registration_by_experiment_id)),
            )


@dataclass(frozen=True)
class CampaignExecutionManifest:
    """Execution manifest describing the campaign and its registrations."""

    campaign_definition: ResearchCampaignDefinition
    compiled_campaign: CompiledCampaign
    registration_set: CampaignRegistrationSet
    fingerprint: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))


# ---------------------------------------------------------------------------
# Execution records and checkpoints
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ExperimentEvidence:
    """Evidence gathered for a single experiment attempt."""

    walk_forward_report: WalkForwardExperimentReport | None = None
    confidence_report: ExperimentConfidenceReport | None = None
    ledger_entry: EvidenceLedgerEntry | None = None
    ledger_snapshot: EvidenceLedgerSnapshot | None = None
    walk_forward_report_fingerprint: str = ""
    confidence_report_fingerprint: str = ""
    ledger_entry_fingerprint: str = ""
    ledger_snapshot_fingerprint: str = ""


@dataclass(frozen=True)
class ExperimentExecutionRecord:
    """Immutable record of one compiled experiment attempt."""

    experiment_id: str
    campaign_id: str
    experiment_fingerprint: str
    registration_fingerprint: str
    outcome: ExperimentOutcome | str
    started_at: datetime
    completed_at: datetime
    evidence: ExperimentEvidence
    reason_codes: tuple[str, ...]
    notes: str = ""

    def __post_init__(self) -> None:
        if isinstance(self.outcome, str):
            object.__setattr__(self, "outcome", ExperimentOutcome(self.outcome))
        elif not isinstance(self.outcome, ExperimentOutcome):
            raise ValueError(f"outcome must be an ExperimentOutcome or str, got {self.outcome!r}")
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))


@dataclass(frozen=True)
class CampaignCheckpoint:
    """Atomic checkpoint manifest written after each experiment attempt."""

    checkpoint_id: str
    campaign_id: str
    checkpoint_index: int
    experiment_records: tuple[ExperimentExecutionRecord, ...]
    status: CampaignStatus | str
    fingerprint: str = ""
    previous_checkpoint_fingerprint: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if isinstance(self.status, str):
            object.__setattr__(self, "status", CampaignStatus(self.status))
        elif not isinstance(self.status, CampaignStatus):
            raise ValueError(f"status must be a CampaignStatus or str, got {self.status!r}")
        if not isinstance(self.previous_checkpoint_fingerprint, str):
            raise ValueError(
                f"previous_checkpoint_fingerprint must be a string, got {self.previous_checkpoint_fingerprint!r}"
            )
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))


# ---------------------------------------------------------------------------
# Resume manifest
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PriorExperimentEvidence:
    """Prior evidence for a single experiment, stored in a resume manifest."""

    experiment_id: str
    experiment_fingerprint: str
    registration_fingerprint: str
    strategy_reference_fingerprint: str
    historical_data_reference_fingerprint: str
    universe_plan_reference_fingerprint: str
    walk_forward_template_reference_fingerprint: str
    confidence_config_reference_fingerprint: str
    walk_forward_report_fingerprint: str
    confidence_report_fingerprint: str
    ledger_entry_fingerprint: str
    inherited_safety_invariants: ResearchCampaignSafetyFlags
    outcome: ExperimentOutcome | str
    evidence: ExperimentEvidence | None = None
    ledger_snapshot_fingerprint: str = ""

    def __post_init__(self) -> None:
        if isinstance(self.outcome, str):
            object.__setattr__(self, "outcome", ExperimentOutcome(self.outcome))
        elif not isinstance(self.outcome, ExperimentOutcome):
            raise ValueError(f"outcome must be an ExperimentOutcome or str, got {self.outcome!r}")


@dataclass(frozen=True)
class CampaignResumeManifest:
    """Immutable manifest used for deterministic resume."""

    campaign_fingerprint: str
    prior_evidence: tuple[PriorExperimentEvidence, ...]
    resume_policy: ResumePolicy | str = ResumePolicy.RERUN
    fingerprint: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if isinstance(self.resume_policy, str):
            object.__setattr__(self, "resume_policy", ResumePolicy(self.resume_policy))
        elif not isinstance(self.resume_policy, ResumePolicy):
            raise ValueError(f"resume_policy must be a ResumePolicy or str, got {self.resume_policy!r}")
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))


# ---------------------------------------------------------------------------
# Summaries and dossier
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CampaignStatusSummary:
    """Summary of campaign execution outcomes."""

    total: int
    completed: int
    failed: int
    blocked: int
    timed_out: int
    unsupported: int
    insufficient_evidence: int
    withdrawn: int
    skipped_by_policy: int
    stale_resume_evidence: int
    fingerprint: str = ""


@dataclass(frozen=True)
class CampaignEvidenceSummary:
    """Summary of MVP-66/67/68 evidence coverage."""

    walk_forward_attempted: int
    walk_forward_completed: int
    confidence_attempted: int
    confidence_completed: int
    ledger_entries: int
    ledger_snapshots: int
    fingerprint: str = ""


@dataclass(frozen=True)
class CampaignDossier:
    """Final deterministic dossier for a research campaign."""

    campaign_id: str
    campaign_fingerprint: str
    compiled_campaign_fingerprint: str
    status_summary: CampaignStatusSummary
    evidence_summary: CampaignEvidenceSummary
    execution_records: tuple[ExperimentExecutionRecord, ...]
    safety_flags: ResearchCampaignSafetyFlags
    fingerprint: str = ""
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))


@dataclass(frozen=True)
class CampaignArtifactManifest:
    """Manifest of all written campaign artifacts."""

    campaign_id: str
    artifact_paths: tuple[str, ...]
    dossier_fingerprint: str
    fingerprint: str = ""
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
