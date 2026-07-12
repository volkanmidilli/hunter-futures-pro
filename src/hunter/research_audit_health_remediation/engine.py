"""Engine for the Research Audit Health Remediation Bridge (MVP-49).

The bridge consumes a caller-provided MVP-48 `HealthReport` and produces
MVP-38 `RemediationBacklogItem` entries. It is pure, local, deterministic, and
audit-only. It does not perform remediation, emit actions, or claim approval.
All references remain opaque strings.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import is_dataclass
from datetime import datetime, timezone
from hashlib import sha256
from json import dumps
from typing import Any

from hunter.remediation_backlog.models import (
    FORBIDDEN_REMEDIATION_BACKLOG_TERMS,
    RemediationBacklogItem,
    RemediationBacklogItemState,
    RemediationBacklogItemType,
    RemediationBacklogPriority,
    RemediationBacklogReasonCode,
    RemediationBacklogSafetyFlags,
    RemediationBacklogSeverity,
)
from hunter.research_audit_health.models import HealthFinding, HealthReasonCode, HealthReport, HealthSeverity

from .mapping import (
    DEFAULT_PRIORITY_ORDER,
    DEFAULT_REASON_TO_ITEM_TYPE,
    DEFAULT_REASON_TO_REASON_CODE,
    DEFAULT_SEVERITY_TO_BACKLOG_SEVERITY,
    DEFAULT_SEVERITY_TO_PRIORITY,
)
from .models import RemediationBridgeConfig, RemediationBridgeDataQuality, RemediationBridgeError, RemediationBridgeReport


_MAX_TITLE_MESSAGE_LEN = 60


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _ensure_str(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    return value


def _ensure_str_or_none(value: Any | None, field_name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string or None")
    if not value.strip():
        return None
    return value.strip()


def _coerce_str(value: Any) -> str:
    """Coerce a value to a deterministic string for metadata."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (bool, int, float)):
        return str(value)
    if isinstance(value, (tuple, list)):
        return ",".join(_coerce_str(v) for v in value)
    if isinstance(value, Mapping):
        return ",".join(f"{k}={_coerce_str(v)}" for k, v in sorted(value.items()))
    if is_dataclass(value) and not isinstance(value, type):
        return dumps(
            {field: _coerce_str(getattr(value, field)) for field in value.__dataclass_fields__},
            sort_keys=True,
            separators=(",", ":"),
        )
    return str(value)


# ---------------------------------------------------------------------------
# Mapping helpers
# ---------------------------------------------------------------------------


def _artifact_id_from_finding(finding: HealthFinding) -> str:
    """Return the first artifact_id from a finding or 'none' if empty."""
    return finding.artifact_ids[0] if finding.artifact_ids else "none"


def _resolve_item_type(finding: HealthFinding, config: RemediationBridgeConfig) -> RemediationBacklogItemType:
    reason_value = finding.reason_code.value
    if reason_value in config.reason_to_item_type:
        override = config.reason_to_item_type[reason_value]
        try:
            return RemediationBacklogItemType(override)
        except ValueError as exc:
            raise RemediationBridgeError(f"invalid reason_to_item_type override: {override!r}") from exc
    if reason_value in DEFAULT_REASON_TO_ITEM_TYPE:
        return DEFAULT_REASON_TO_ITEM_TYPE[reason_value]
    return RemediationBacklogItemType.MANUAL_REVIEW


def _resolve_reason_code(finding: HealthFinding) -> RemediationBacklogReasonCode:
    reason_value = finding.reason_code.value
    if reason_value in DEFAULT_REASON_TO_REASON_CODE:
        return DEFAULT_REASON_TO_REASON_CODE[reason_value]
    return RemediationBacklogReasonCode.CONSISTENCY_DEGRADED


def _resolve_severity(finding: HealthFinding) -> RemediationBacklogSeverity:
    severity_value = finding.severity.value
    if severity_value in DEFAULT_SEVERITY_TO_BACKLOG_SEVERITY:
        return DEFAULT_SEVERITY_TO_BACKLOG_SEVERITY[severity_value]
    return RemediationBacklogSeverity.ADVISORY


def _resolve_priority(finding: HealthFinding, config: RemediationBridgeConfig) -> RemediationBacklogPriority:
    severity_value = finding.severity.value
    if severity_value in config.severity_to_priority:
        override = config.severity_to_priority[severity_value]
        try:
            return RemediationBacklogPriority(override)
        except ValueError as exc:
            raise RemediationBridgeError(f"invalid severity_to_priority override: {override!r}") from exc
    if severity_value in DEFAULT_SEVERITY_TO_PRIORITY:
        return RemediationBacklogPriority(DEFAULT_SEVERITY_TO_PRIORITY[severity_value])
    return RemediationBacklogPriority.NONE


def _build_item_id(
    report_id: str,
    finding: HealthFinding,
    reason_code: RemediationBacklogReasonCode,
    severity: RemediationBacklogSeverity,
) -> str:
    """Return a deterministic item_id from sorted fields of the finding."""
    artifact_id = _artifact_id_from_finding(finding)
    payload = {
        "report_id": report_id,
        "finding_id": finding.finding_id,
        "family": finding.family,
        "artifact_id": artifact_id,
        "reason_code": reason_code.value,
        "severity": severity.value,
    }
    canonical = dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(canonical.encode("utf-8")).hexdigest()[:16]


def _build_item_title(finding: HealthFinding, reason_code: RemediationBacklogReasonCode) -> str:
    artifact_id = _artifact_id_from_finding(finding)
    short_message = finding.description[:_MAX_TITLE_MESSAGE_LEN]
    return f"[{reason_code.name.upper()}] {finding.family}/{artifact_id}: {short_message}"


def _build_item_metadata(finding: HealthFinding) -> Mapping[str, str]:
    """Convert finding evidence and identifiers into string metadata."""
    metadata: dict[str, str] = {
        "family": finding.family,
        "artifact_id": _artifact_id_from_finding(finding),
        "finding_id": finding.finding_id,
        "rule_id": finding.rule_id,
    }
    if finding.evidence is not None:
        for key, value in finding.evidence.items():
            metadata[str(key)] = _coerce_str(value)
    return metadata


def _map_finding_to_item(
    finding: HealthFinding,
    report_id: str,
    config: RemediationBridgeConfig,
    generated_at: datetime,
) -> RemediationBacklogItem | None:
    """Map a single HealthFinding to a RemediationBacklogItem, or None if skipped."""
    if finding.reason_code == HealthReasonCode.OK:
        return None
    if config.exclude_info and finding.severity == HealthSeverity.INFO:
        return None

    item_type = _resolve_item_type(finding, config)
    reason_code = _resolve_reason_code(finding)
    severity = _resolve_severity(finding)
    priority = _resolve_priority(finding, config)
    item_id = _build_item_id(report_id, finding, reason_code, severity)
    title = _build_item_title(finding, reason_code)
    metadata = _build_item_metadata(finding)

    source_id = _artifact_id_from_finding(finding)
    if source_id == "none":
        source_id = finding.family

    return RemediationBacklogItem(
        item_id=item_id,
        subject_id=finding.family,
        source_id=source_id,
        finding_id=finding.finding_id,
        item_type=item_type,
        item_state=RemediationBacklogItemState.OPEN,
        severity=severity,
        priority=priority,
        title=title,
        description=finding.description,
        owner=config.owner,
        reviewer=config.reviewer,
        generated_at=generated_at,
        reason_codes=(reason_code,),
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


def _deduplicate_items(
    items: tuple[RemediationBacklogItem, ...],
) -> tuple[tuple[RemediationBacklogItem, ...], int]:
    """Collapse items with the same item_id. BLOCKING severity wins; otherwise sorted order."""
    by_id: dict[str, list[RemediationBacklogItem]] = {}
    for item in items:
        by_id.setdefault(item.item_id or "", []).append(item)

    deduplicated: list[RemediationBacklogItem] = []
    duplicates_collapsed = 0
    for item_id, group in sorted(by_id.items()):
        if len(group) == 1:
            deduplicated.append(group[0])
            continue
        duplicates_collapsed += len(group) - 1
        blocking = [item for item in group if item.severity == RemediationBacklogSeverity.BLOCKING]
        if blocking:
            chosen = min(blocking, key=lambda item: (DEFAULT_PRIORITY_ORDER.get(item.priority.value, 4), item.title))
        else:
            chosen = min(group, key=lambda item: (DEFAULT_PRIORITY_ORDER.get(item.priority.value, 4), item.title))
        deduplicated.append(chosen)

    return tuple(sorted(deduplicated, key=lambda item: item.item_id or "")), duplicates_collapsed


# ---------------------------------------------------------------------------
# Forbidden-term scanning
# ---------------------------------------------------------------------------


def _has_forbidden_term(text: str) -> bool:
    if not isinstance(text, str):
        return False
    lower = text.lower()
    return any(term in lower for term in FORBIDDEN_REMEDIATION_BACKLOG_TERMS)


def _scan_forbidden_terms(items: tuple[RemediationBacklogItem, ...]) -> tuple[bool, RemediationBacklogItem | None]:
    """Return (has_leakage, safety_item)."""
    for item in items:
        if _has_forbidden_term(item.title) or _has_forbidden_term(item.description):
            return True, _safety_item_for_forbidden_terms(item.generated_at)
        for value in item.metadata.values():
            if _has_forbidden_term(value):
                return True, _safety_item_for_forbidden_terms(item.generated_at)
    return False, None


def _safety_item_for_forbidden_terms(generated_at: datetime | None) -> RemediationBacklogItem:
    return RemediationBacklogItem(
        item_id="health_remediation_forbidden_terms",
        subject_id="bridge",
        source_id="bridge",
        item_type=RemediationBacklogItemType.UNSAFE_CONTENT,
        item_state=RemediationBacklogItemState.OPEN,
        severity=RemediationBacklogSeverity.BLOCKING,
        priority=RemediationBacklogPriority.P0,
        title="[FORBIDDEN_TERM_PRESENT] bridge: generated backlog item contains forbidden term",
        description="A generated remediation backlog item contained a forbidden readiness/trading phrase. Human review required.",
        generated_at=generated_at,
        reason_codes=(RemediationBacklogReasonCode.FORBIDDEN_TERM_PRESENT,),
        metadata={"source": "bridge_forbidden_term_scan"},
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_health_remediation_bridge_report(
    report: HealthReport,
    config: RemediationBridgeConfig | None = None,
) -> RemediationBridgeReport:
    """Convert a HealthReport into a deterministic RemediationBridgeReport.

    The bridge is local, audit-only, and fail-closed. It does not perform
    remediation, emit actions, or claim approval. All references remain opaque.
    """
    if config is None:
        config = RemediationBridgeConfig()
    if not isinstance(report, HealthReport):
        raise RemediationBridgeError("report must be a HealthReport")
    if not isinstance(config, RemediationBridgeConfig):
        raise RemediationBridgeError("config must be a RemediationBridgeConfig")

    generated_at = datetime.now(timezone.utc)
    generated_at_iso = generated_at.strftime("%Y-%m-%dT%H:%M:%S+00:00")

    items: list[RemediationBacklogItem] = []
    dropped_info = 0
    for finding in report.findings:
        if finding.severity == HealthSeverity.INFO and config.exclude_info:
            dropped_info += 1
            continue
        item = _map_finding_to_item(finding, report.report_id, config, generated_at)
        if item is not None:
            items.append(item)

    deduplicated_items, duplicates_collapsed = _deduplicate_items(tuple(items))
    has_forbidden_terms, safety_item = _scan_forbidden_terms(deduplicated_items)

    safety_flags = RemediationBacklogSafetyFlags(has_forbidden_terms=has_forbidden_terms)
    safety_flagged_items = 0
    if has_forbidden_terms and safety_item is not None:
        deduplicated_items = deduplicated_items + (safety_item,)
        safety_flagged_items = 1

    report_id = _build_report_id(report.report_id, deduplicated_items)

    data_quality = RemediationBridgeDataQuality(
        input_findings=len(report.findings),
        produced_items=len(deduplicated_items),
        dropped_info=dropped_info,
        duplicates_collapsed=duplicates_collapsed,
        safety_flagged_items=safety_flagged_items,
    )

    return RemediationBridgeReport(
        report_id=report_id,
        source_report_id=report.report_id,
        generated_at=generated_at_iso,
        items=deduplicated_items,
        data_quality=data_quality,
        safety_flags=safety_flags,
    )


def _build_report_id(source_report_id: str, items: tuple[RemediationBacklogItem, ...]) -> str:
    """Return a deterministic bridge report_id from the source report and sorted item IDs."""
    payload = {
        "source_report_id": source_report_id,
        "item_ids": sorted(item.item_id for item in items),
    }
    canonical = dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return f"health_remediation_bridge_{sha256(canonical.encode('utf-8')).hexdigest()[:16]}"
