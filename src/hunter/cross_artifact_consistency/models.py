"""Cross-Artifact Consistency Engine models.

This module defines the frozen data model, enums, and safety flags for the
local, deterministic, audit-only Cross-Artifact Consistency Engine (MVP-47).
All references are opaque strings; no filesystem or network behavior is
introduced by this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Mapping


class ConsistencyState(str, Enum):
    """Aggregate state of a consistency report."""

    OK = "OK"
    DEGRADED = "DEGRADED"
    BLOCKED = "BLOCKED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ConsistencySeverity(str, Enum):
    """Severity of a single consistency finding."""

    INFO = "INFO"
    WARNING = "WARNING"
    BLOCKING = "BLOCKING"


class ConsistencyReasonCode(str, Enum):
    """Reason codes used by consistency findings and reports."""

    OK = "OK"
    NO_ARTIFACTS = "NO_ARTIFACTS"
    DUPLICATE_ARTIFACT_ID = "DUPLICATE_ARTIFACT_ID"
    MISSING_UPSTREAM_REFERENCE = "MISSING_UPSTREAM_REFERENCE"
    ORPHAN_DOWNSTREAM_REFERENCE = "ORPHAN_DOWNSTREAM_REFERENCE"
    INCONSISTENT_STATE_TRANSITION = "INCONSISTENT_STATE_TRANSITION"
    MVP_SPEC_MISMATCH = "MVP_SPEC_MISMATCH"
    HASH_LENGTH_MISMATCH = "HASH_LENGTH_MISMATCH"
    DECISION_LOG_QUEUE_MISMATCH = "DECISION_LOG_QUEUE_MISMATCH"
    AUDIT_BUNDLE_EXPORT_MISMATCH = "AUDIT_BUNDLE_EXPORT_MISMATCH"
    VERIFICATION_EXPORT_MISMATCH = "VERIFICATION_EXPORT_MISMATCH"
    STALE_PROJECT_MEMORY = "STALE_PROJECT_MEMORY"
    FORBIDDEN_PHRASE_LEAKAGE = "FORBIDDEN_PHRASE_LEAKAGE"
    MALFORMED_METADATA = "MALFORMED_METADATA"
    UNSUPPORTED_ARTIFACT_KIND = "UNSUPPORTED_ARTIFACT_KIND"
    CONTRADICTORY_METADATA = "CONTRADICTORY_METADATA"


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

DEFAULT_ALLOWED_ARTIFACT_KINDS: tuple[str, ...] = (
    "observation",
    "review_record",
    "review_index",
    "review_search",
    "research_bundle",
    "chronicle",
    "digest",
    "quality_gate",
    "handoff_packet",
    "archive_manifest",
    "release_notes",
    "audit_catalog",
    "audit_closure",
    "audit_snapshot",
    "experiment_ledger",
    "final_audit_pack",
    "remediation_backlog",
    "remediation_evidence",
    "remediation_closure",
    "human_review_queue",
    "human_review_decision_log",
    "decision_log_consistency",
    "audit_bundle",
    "audit_bundle_export",
    "audit_bundle_export_verification",
    "cross_artifact_consistency",
)


@dataclass(frozen=True, slots=True)
class ArtifactRef:
    """Opaque reference to an artifact. Never treated as a filesystem path."""

    ref_id: str
    ref_kind: str
    opaque_value: str
    metadata: Mapping[str, object] | None = None


@dataclass(frozen=True, slots=True)
class ArtifactSummary:
    """Lightweight, caller-provided summary of any artifact family."""

    artifact_id: str
    artifact_kind: str
    artifact_state: str
    mvp: str | None = None
    spec: str | None = None
    produced_by: str | None = None
    opaque_ref: ArtifactRef | None = None
    content_hash: str | None = None
    content_length: int | None = None
    generated_at: datetime | None = None
    upstream_ids: tuple[str, ...] = ()
    downstream_ids: tuple[str, ...] = ()
    decision_ids: tuple[str, ...] = ()
    review_ids: tuple[str, ...] = ()
    report_ids: tuple[str, ...] = ()
    metadata: Mapping[str, object] | None = None


@dataclass(frozen=True, slots=True)
class ConsistencyRule:
    """Named consistency check with a default severity and reason code."""

    rule_id: str
    description: str
    severity: ConsistencySeverity
    reason_code: ConsistencyReasonCode
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class ConsistencyFinding:
    """A single deterministic consistency finding."""

    finding_id: str
    rule_id: str
    artifact_ids: tuple[str, ...]
    severity: ConsistencySeverity
    reason_code: ConsistencyReasonCode
    title: str
    description: str
    evidence: Mapping[str, object] | None = None


@dataclass(frozen=True, slots=True)
class ConsistencyDataQuality:
    """Counters summarizing the consistency run."""

    artifact_count: int = 0
    finding_count: int = 0
    blocking_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    duplicate_id_count: int = 0
    missing_upstream_count: int = 0
    orphan_downstream_count: int = 0
    malformed_metadata_count: int = 0
    unsupported_kind_count: int = 0
    checks_performed: int = 0


@dataclass(frozen=True, slots=True)
class ConsistencySafetyFlags:
    """Safety flags asserting the run remained within audit-only boundaries."""

    audit_only: bool = True
    opaque_refs_only: bool = True
    filesystem_access: bool = False
    network_access: bool = False
    runtime_execution: bool = False
    trading_signal: bool = False


@dataclass(frozen=True, slots=True)
class CrossArtifactConsistencyConfig:
    """Configuration for the consistency engine."""

    strict: bool = True
    allow_empty: bool = True
    check_stale_project_memory: bool = False
    allowed_artifact_kinds: tuple[str, ...] = field(default=DEFAULT_ALLOWED_ARTIFACT_KINDS)
    forbidden_terms: tuple[str, ...] = field(default=DEFAULT_FORBIDDEN_TERMS)


@dataclass(frozen=True, slots=True)
class CrossArtifactConsistencyInput:
    """Top-level input to the consistency engine."""

    artifacts: tuple[ArtifactSummary, ...]
    config: CrossArtifactConsistencyConfig = field(default_factory=CrossArtifactConsistencyConfig)
    metadata: Mapping[str, object] | None = None


@dataclass(frozen=True, slots=True)
class ConsistencyReport:
    """Deterministic aggregate output of the consistency engine."""

    report_id: str
    state: ConsistencyState
    findings: tuple[ConsistencyFinding, ...]
    reason_codes: tuple[ConsistencyReasonCode, ...]
    data_quality: ConsistencyDataQuality
    safety_flags: ConsistencySafetyFlags
    artifacts: tuple[ArtifactSummary, ...]
    metadata: Mapping[str, object] | None = None
