"""Research Audit Aggregate Health Report models.

This module defines the frozen data model, enums, reason codes, and safety
flags for the local, deterministic, audit-only Research Audit Aggregate Health
Report engine (MVP-48). All references are opaque strings; no filesystem or
network behavior is introduced by this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Mapping


class HealthState(str, Enum):
    """Aggregate health state of the research audit landscape."""

    OK = "OK"
    DEGRADED = "DEGRADED"
    BLOCKED = "BLOCKED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class HealthSeverity(str, Enum):
    """Severity of a single health finding."""

    INFO = "INFO"
    WARNING = "WARNING"
    BLOCKING = "BLOCKING"


class HealthReasonCode(str, Enum):
    """Reason codes used by health findings and reports."""

    OK = "OK"
    NO_ARTIFACTS = "NO_ARTIFACTS"
    DUPLICATE_ARTIFACT_ID = "DUPLICATE_ARTIFACT_ID"
    MALFORMED_METADATA = "MALFORMED_METADATA"
    UNSUPPORTED_ARTIFACT_FAMILY = "UNSUPPORTED_ARTIFACT_FAMILY"
    MISSING_REQUIRED_FAMILY = "MISSING_REQUIRED_FAMILY"
    BLOCKING_SOURCE_STATE = "BLOCKING_SOURCE_STATE"
    DEGRADED_SOURCE_STATE = "DEGRADED_SOURCE_STATE"
    STALE_SOURCE_STATE = "STALE_SOURCE_STATE"
    INCONSISTENT_SCORE_INPUT = "INCONSISTENT_SCORE_INPUT"
    CONTRADICTORY_METADATA = "CONTRADICTORY_METADATA"
    FORBIDDEN_PHRASE_LEAKAGE = "FORBIDDEN_PHRASE_LEAKAGE"


DEFAULT_FORBIDDEN_TERMS: tuple[str, ...] = (
    "production readiness",
    "trading readiness",
    "live trading",
    "production approval",
    "trading approval",
    "execution approval",
    "certification",
    "recommendation",
    "suitability",
    "deploy to production",
    "place order",
    "submit order",
    "buy signal",
    "sell signal",
    "long signal",
    "short signal",
)

DEFAULT_ALLOWED_FAMILIES: tuple[str, ...] = (
    "research_audit_snapshot",
    "research_audit_catalog",
    "research_release_notes",
    "research_audit_closure",
    "research_quality_gate",
    "human_review_queue",
    "human_review_decision_log",
    "human_review_audit_bundle",
    "human_review_audit_bundle_export",
    "human_review_audit_bundle_export_verification",
    "cross_artifact_consistency",
    "project_memory_status",
)

DEFAULT_REQUIRED_FAMILIES: tuple[str, ...] = ()

DEFAULT_SEVERITY_PENALTIES: Mapping[HealthSeverity, int] = {
    HealthSeverity.INFO: 1,
    HealthSeverity.WARNING: 25,
    HealthSeverity.BLOCKING: 100,
}

DEFAULT_SEVERITY_WEIGHTS: Mapping[HealthSeverity, int] = {
    HealthSeverity.INFO: 1,
    HealthSeverity.WARNING: 3,
    HealthSeverity.BLOCKING: 10,
}


@dataclass(frozen=True, slots=True)
class HealthArtifactSummary:
    """Caller-provided summary of one artifact from a research audit family.

    The `artifact_id` and `ref` are opaque strings. The engine never opens,
    traverses, validates, fetches, or executes them.
    """

    artifact_id: str
    family: str
    source_state: str
    score: float | None = None
    mvp: str | None = None
    spec: str | None = None
    produced_by: str | None = None
    generated_at: datetime | None = None
    ref: str | None = None
    metadata: Mapping[str, object] | None = None

    def __post_init__(self) -> None:
        # Validate that score is a finite number if present and bounded later.
        if self.score is not None and not isinstance(self.score, (int, float)):
            raise TypeError(f"score must be a number or None, got {type(self.score)}")
        if self.score is not None and (self.score < 0 or self.score > 100):
            raise ValueError(f"score must be between 0 and 100, got {self.score}")


@dataclass(frozen=True, slots=True)
class HealthConfig:
    """Configuration for the aggregate health engine."""

    strict: bool = True
    allow_empty: bool = True
    allowed_families: tuple[str, ...] = field(default=DEFAULT_ALLOWED_FAMILIES)
    required_families: tuple[str, ...] = field(default=DEFAULT_REQUIRED_FAMILIES)
    forbidden_terms: tuple[str, ...] = field(default=DEFAULT_FORBIDDEN_TERMS)
    severity_penalties: Mapping[HealthSeverity, int] = field(
        default_factory=lambda: DEFAULT_SEVERITY_PENALTIES.copy()
    )
    severity_weights: Mapping[HealthSeverity, int] = field(
        default_factory=lambda: DEFAULT_SEVERITY_WEIGHTS.copy()
    )
    degraded_threshold: int = 75

    def __post_init__(self) -> None:
        # Validate that penalties and weights cover all severities.
        for severity in HealthSeverity:
            if severity not in self.severity_penalties:
                raise ValueError(f"missing penalty for severity {severity}")
            if severity not in self.severity_weights:
                raise ValueError(f"missing weight for severity {severity}")


@dataclass(frozen=True, slots=True)
class HealthInput:
    """Top-level input to the aggregate health engine."""

    summaries: tuple[HealthArtifactSummary, ...]
    config: HealthConfig = field(default_factory=HealthConfig)
    metadata: Mapping[str, object] | None = None


@dataclass(frozen=True, slots=True)
class HealthFinding:
    """A single deterministic aggregate health finding."""

    finding_id: str
    rule_id: str
    family: str
    artifact_ids: tuple[str, ...]
    severity: HealthSeverity
    reason_code: HealthReasonCode
    title: str
    description: str
    evidence: Mapping[str, object] | None = None


@dataclass(frozen=True, slots=True)
class HealthScore:
    """Numeric aggregate health score with a deterministic breakdown."""

    value: float
    weight: float
    contributing_families: tuple[str, ...]
    breakdown: Mapping[str, object] | None = None


@dataclass(frozen=True, slots=True)
class HealthFamilyRollup:
    """Per-family health summary produced by the engine."""

    family: str
    state: HealthState
    score: HealthScore
    finding_count: int
    reason_code_counts: Mapping[str, int]
    summary: str


@dataclass(frozen=True, slots=True)
class HealthDataQuality:
    """Counters summarizing the health evaluation run."""

    summary_count: int = 0
    family_count: int = 0
    finding_count: int = 0
    blocking_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    reason_code_counts: Mapping[str, int] | None = None
    checks_performed: int = 0
    skipped_count: int = 0


@dataclass(frozen=True, slots=True)
class HealthSafetyFlags:
    """Safety flags asserting the run remained within audit-only boundaries."""

    audit_only: bool = True
    opaque_refs_only: bool = True
    filesystem_access: bool = False
    network_access: bool = False
    runtime_execution: bool = False
    trading_signal: bool = False


@dataclass(frozen=True, slots=True)
class HealthReport:
    """Deterministic aggregate output of the health engine."""

    report_id: str
    state: HealthState
    aggregate_score: HealthScore
    family_rollups: tuple[HealthFamilyRollup, ...]
    findings: tuple[HealthFinding, ...]
    reason_code_counts: Mapping[str, int]
    data_quality: HealthDataQuality
    safety_flags: HealthSafetyFlags
    metadata: Mapping[str, object] | None = None
