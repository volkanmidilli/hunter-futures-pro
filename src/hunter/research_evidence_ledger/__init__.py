"""Public API for the research evidence ledger package (MVP-68 / SPEC-069).

Consumes immutable MVP-66 WalkForwardExperimentReport and
MVP-67 ExperimentConfidenceReport to build a research-only cross-experiment
evidence ledger with pre-registration, duplicate detection, drift detection,
family indexing, multiple-testing adjustment, replication analysis,
snapshot chaining, and deterministic fingerprints.
"""

from __future__ import annotations

from hunter.research_evidence_ledger.adjustment import (
    adjust,
    adjust_benjamini_hochberg,
    adjust_bonferroni,
)
from hunter.research_evidence_ledger.drift import DriftDetector
from hunter.research_evidence_ledger.duplicate import DuplicateDetector
from hunter.research_evidence_ledger.engine import EvidenceLedgerEngine
from hunter.research_evidence_ledger.errors import (
    EvidenceLedgerAdjustmentError,
    EvidenceLedgerDriftError,
    EvidenceLedgerDuplicateError,
    EvidenceLedgerError,
    EvidenceLedgerRegistrationError,
    EvidenceLedgerReplicationError,
    EvidenceLedgerSafetyError,
    EvidenceLedgerSnapshotError,
    EvidenceLedgerValidationError,
    EvidenceLedgerWriterError,
)
from hunter.research_evidence_ledger.family import (
    build_experiment_families,
    build_hypothesis_families,
    build_metric_families,
)
from hunter.research_evidence_ledger.fingerprint import (
    adjusted_evidence_fingerprint,
    entry_fingerprint,
    evidence_fingerprint,
    experiment_family_fingerprint,
    hypothesis_family_fingerprint,
    manifest_fingerprint,
    metric_family_fingerprint,
    registration_fingerprint,
    replication_fingerprint,
    report_fingerprint,
    snapshot_fingerprint,
)
from hunter.research_evidence_ledger.models import (
    EVIDENCE_LEDGER_REASON_CODES,
    EVIDENCE_LEDGER_VERSION,
    SPEC_VERSION,
    UNAVAILABLE,
    AdjustedEvidence,
    AdjustmentConfig,
    AdjustmentMethod,
    EvidenceLedgerEntry,
    EvidenceLedgerManifest,
    EvidenceLedgerReport,
    EvidenceLedgerSafetyFlags,
    ExperimentEvidence,
    ExperimentFamily,
    ExperimentRegistration,
    ExperimentStatus,
    HypothesisFamily,
    IndependenceClass,
    LedgerSnapshot,
    MetricFamily,
    ReplicationResult,
    ReplicationState,
)
from hunter.research_evidence_ledger.registration import (
    create_registration,
    update_registration_status,
)
from hunter.research_evidence_ledger.replication import (
    analyze_all_replications,
    analyze_replication,
)
from hunter.research_evidence_ledger.snapshot import (
    build_snapshot,
    verify_snapshot_chain,
)
from hunter.research_evidence_ledger.validator import (
    validate_raw_value,
    validate_registration,
    validate_safety_flags,
)
from hunter.research_evidence_ledger.writer import (
    EvidenceLedgerWriter,
    write_all_evidence_ledger_artifacts,
)

__all__ = [
    "EVIDENCE_LEDGER_VERSION",
    "SPEC_VERSION",
    "UNAVAILABLE",
    "EVIDENCE_LEDGER_REASON_CODES",
    # Enums
    "ExperimentStatus",
    "IndependenceClass",
    "AdjustmentMethod",
    "ReplicationState",
    # Models
    "EvidenceLedgerSafetyFlags",
    "ExperimentRegistration",
    "ExperimentEvidence",
    "EvidenceLedgerEntry",
    "HypothesisFamily",
    "ExperimentFamily",
    "MetricFamily",
    "AdjustmentConfig",
    "AdjustedEvidence",
    "ReplicationResult",
    "LedgerSnapshot",
    "EvidenceLedgerManifest",
    "EvidenceLedgerReport",
    # Errors
    "EvidenceLedgerError",
    "EvidenceLedgerValidationError",
    "EvidenceLedgerSafetyError",
    "EvidenceLedgerDuplicateError",
    "EvidenceLedgerDriftError",
    "EvidenceLedgerAdjustmentError",
    "EvidenceLedgerReplicationError",
    "EvidenceLedgerSnapshotError",
    "EvidenceLedgerWriterError",
    "EvidenceLedgerRegistrationError",
    # Validation
    "validate_registration",
    "validate_safety_flags",
    "validate_raw_value",
    # Registration
    "create_registration",
    "update_registration_status",
    # Duplicate detection
    "DuplicateDetector",
    # Drift detection
    "DriftDetector",
    # Family indexing
    "build_hypothesis_families",
    "build_experiment_families",
    "build_metric_families",
    # Adjustment
    "adjust",
    "adjust_benjamini_hochberg",
    "adjust_bonferroni",
    # Replication
    "analyze_replication",
    "analyze_all_replications",
    # Snapshot
    "build_snapshot",
    "verify_snapshot_chain",
    # Fingerprint
    "registration_fingerprint",
    "evidence_fingerprint",
    "entry_fingerprint",
    "hypothesis_family_fingerprint",
    "experiment_family_fingerprint",
    "metric_family_fingerprint",
    "adjusted_evidence_fingerprint",
    "replication_fingerprint",
    "snapshot_fingerprint",
    "manifest_fingerprint",
    "report_fingerprint",
    # Engine
    "EvidenceLedgerEngine",
    # Writer
    "EvidenceLedgerWriter",
    "write_all_evidence_ledger_artifacts",
]
