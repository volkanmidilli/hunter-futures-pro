"""Public API for hunter.evidence_traceability package.

MVP-34 — Local Research Evidence Traceability Matrix.

All exports are deterministic, local, and audit-only. They do not connect to
exchanges, networks, databases, or external services, and do not emit trading or
execution commands. The matrix runs only when called by local code or tests; it is
not a scheduler, daemon, server, or background job runner.
"""

from __future__ import annotations

from hunter.evidence_traceability.engine import (
    build_evidence_traceability_report,
    has_unsafe_evidence_traceability_content,
)
from hunter.evidence_traceability.models import (
    CONSISTENCY_DEGRADED,
    FORBIDDEN_EVIDENCE_TRACEABILITY_TERMS,
    NO_ACTION_COMMANDS_EMITTED,
    NO_DAEMON,
    NO_DATABASE,
    NO_EXCHANGE_CONNECTION,
    NO_FILE_INGESTION,
    NO_FREQTRADE_INPUT,
    NO_NETWORK_CONNECTION,
    NO_SCHEDULER,
    NO_WEB_UI,
    NOT_APPLICABLE_RC,
    NOT_TRADING_ADVICE,
    OK,
    SAFETY_BLOCKED,
    EvidenceArtifactRef,
    EvidenceCheck,
    EvidenceLink,
    EvidenceRequirement,
    EvidenceSectionRef,
    EvidenceTraceabilityConfig,
    EvidenceTraceabilityCoverageState,
    EvidenceTraceabilityDataQuality,
    EvidenceTraceabilityInput,
    EvidenceTraceabilityLinkType,
    EvidenceTraceabilityReasonCode,
    EvidenceTraceabilityReport,
    EvidenceTraceabilityResult,
    EvidenceTraceabilitySafetyFlags,
    EvidenceTraceabilitySeverity,
    EvidenceTraceabilityState,
)

__all__ = [
    "CONSISTENCY_DEGRADED",
    "FORBIDDEN_EVIDENCE_TRACEABILITY_TERMS",
    "NO_ACTION_COMMANDS_EMITTED",
    "NO_DAEMON",
    "NO_DATABASE",
    "NO_EXCHANGE_CONNECTION",
    "NO_FILE_INGESTION",
    "NO_FREQTRADE_INPUT",
    "NO_NETWORK_CONNECTION",
    "NO_SCHEDULER",
    "NO_WEB_UI",
    "NOT_APPLICABLE_RC",
    "NOT_TRADING_ADVICE",
    "OK",
    "SAFETY_BLOCKED",
    "EvidenceArtifactRef",
    "EvidenceCheck",
    "EvidenceLink",
    "EvidenceRequirement",
    "EvidenceSectionRef",
    "EvidenceTraceabilityConfig",
    "EvidenceTraceabilityCoverageState",
    "EvidenceTraceabilityDataQuality",
    "EvidenceTraceabilityInput",
    "EvidenceTraceabilityLinkType",
    "EvidenceTraceabilityReasonCode",
    "EvidenceTraceabilityReport",
    "EvidenceTraceabilityResult",
    "EvidenceTraceabilitySafetyFlags",
    "EvidenceTraceabilitySeverity",
    "EvidenceTraceabilityState",
    "build_evidence_traceability_report",
    "has_unsafe_evidence_traceability_content",
]
