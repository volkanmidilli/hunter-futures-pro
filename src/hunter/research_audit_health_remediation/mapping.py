"""Default mapping tables for the Research Audit Health Remediation Bridge.

The bridge maps MVP-48 `HealthReasonCode` and `HealthSeverity` values to the
MVP-38 `RemediationBacklogItemType`, `RemediationBacklogReasonCode`,
`RemediationBacklogSeverity`, and `RemediationBacklogPriority` enums. The
defaults are fail-closed: most findings become human-review backlog items with
`CONSISTENCY_DEGRADED` reason codes; missing-family or missing-artifact findings
become `MISSING_REF` items; forbidden-phrase leakage becomes `UNSAFE_CONTENT`.
"""

from __future__ import annotations

from hunter.remediation_backlog.models import (
    RemediationBacklogItemType,
    RemediationBacklogPriority,
    RemediationBacklogReasonCode,
    RemediationBacklogSeverity,
)
from hunter.research_audit_health.models import HealthReasonCode, HealthSeverity


DEFAULT_SEVERITY_TO_PRIORITY: dict[str, str] = {
    HealthSeverity.BLOCKING.value: RemediationBacklogPriority.P0.value,
    HealthSeverity.WARNING.value: RemediationBacklogPriority.P1.value,
    HealthSeverity.INFO.value: RemediationBacklogPriority.P3.value,
}

DEFAULT_SEVERITY_TO_BACKLOG_SEVERITY: dict[str, RemediationBacklogSeverity] = {
    HealthSeverity.BLOCKING.value: RemediationBacklogSeverity.BLOCKING,
    HealthSeverity.WARNING.value: RemediationBacklogSeverity.ADVISORY,
    HealthSeverity.INFO.value: RemediationBacklogSeverity.INFO,
}

DEFAULT_REASON_TO_ITEM_TYPE: dict[str, RemediationBacklogItemType] = {
    HealthReasonCode.NO_ARTIFACTS.value: RemediationBacklogItemType.MISSING_REF,
    HealthReasonCode.DUPLICATE_ARTIFACT_ID.value: RemediationBacklogItemType.MANUAL_REVIEW,
    HealthReasonCode.MALFORMED_METADATA.value: RemediationBacklogItemType.MANUAL_REVIEW,
    HealthReasonCode.UNSUPPORTED_ARTIFACT_FAMILY.value: RemediationBacklogItemType.MANUAL_REVIEW,
    HealthReasonCode.MISSING_REQUIRED_FAMILY.value: RemediationBacklogItemType.MISSING_REF,
    HealthReasonCode.BLOCKING_SOURCE_STATE.value: RemediationBacklogItemType.MANUAL_REVIEW,
    HealthReasonCode.DEGRADED_SOURCE_STATE.value: RemediationBacklogItemType.MANUAL_REVIEW,
    HealthReasonCode.STALE_SOURCE_STATE.value: RemediationBacklogItemType.STALE_REF,
    HealthReasonCode.INCONSISTENT_SCORE_INPUT.value: RemediationBacklogItemType.MANUAL_REVIEW,
    HealthReasonCode.CONTRADICTORY_METADATA.value: RemediationBacklogItemType.MANUAL_REVIEW,
    HealthReasonCode.FORBIDDEN_PHRASE_LEAKAGE.value: RemediationBacklogItemType.UNSAFE_CONTENT,
}

DEFAULT_REASON_TO_REASON_CODE: dict[str, RemediationBacklogReasonCode] = {
    HealthReasonCode.OK.value: RemediationBacklogReasonCode.OK,
    HealthReasonCode.NO_ARTIFACTS.value: RemediationBacklogReasonCode.MISSING_REQUIRED_SOURCE,
    HealthReasonCode.DUPLICATE_ARTIFACT_ID.value: RemediationBacklogReasonCode.CONSISTENCY_DEGRADED,
    HealthReasonCode.MALFORMED_METADATA.value: RemediationBacklogReasonCode.CONSISTENCY_DEGRADED,
    HealthReasonCode.UNSUPPORTED_ARTIFACT_FAMILY.value: RemediationBacklogReasonCode.CONSISTENCY_DEGRADED,
    HealthReasonCode.MISSING_REQUIRED_FAMILY.value: RemediationBacklogReasonCode.MISSING_REQUIRED_SOURCE,
    HealthReasonCode.BLOCKING_SOURCE_STATE.value: RemediationBacklogReasonCode.SAFETY_BLOCKED,
    HealthReasonCode.DEGRADED_SOURCE_STATE.value: RemediationBacklogReasonCode.CONSISTENCY_DEGRADED,
    HealthReasonCode.STALE_SOURCE_STATE.value: RemediationBacklogReasonCode.STALE_SOURCE_REF,
    HealthReasonCode.INCONSISTENT_SCORE_INPUT.value: RemediationBacklogReasonCode.CONSISTENCY_DEGRADED,
    HealthReasonCode.CONTRADICTORY_METADATA.value: RemediationBacklogReasonCode.CONSISTENCY_DEGRADED,
    HealthReasonCode.FORBIDDEN_PHRASE_LEAKAGE.value: RemediationBacklogReasonCode.FORBIDDEN_TERM_PRESENT,
}


DEFAULT_PRIORITY_ORDER: dict[str, int] = {
    RemediationBacklogPriority.P0.value: 0,
    RemediationBacklogPriority.P1.value: 1,
    RemediationBacklogPriority.P2.value: 2,
    RemediationBacklogPriority.P3.value: 3,
    RemediationBacklogPriority.NONE.value: 4,
}
