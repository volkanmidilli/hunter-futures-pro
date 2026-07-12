"""Engine for the Research Audit Remediation Handoff Packet (MVP-50).

The handoff engine consumes a caller-provided MVP-49 `RemediationBridgeReport`
(or a sequence of `RemediationBacklogItem` summaries) and produces a
deterministic `HandoffPacket` with grouped items, summary counts, and metadata.
It is pure, local, deterministic, and audit-only. It does not perform
remediation, emit actions, or claim approval. All references remain opaque
strings.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import is_dataclass
from datetime import datetime, timezone
from hashlib import sha256
from json import dumps
from typing import Any

from hunter.remediation_backlog.models import (
    FORBIDDEN_REMEDIATION_BACKLOG_TERMS,
    RemediationBacklogItem,
    RemediationBacklogItemState,
    RemediationBacklogPriority,
    RemediationBacklogSeverity,
)
from hunter.research_audit_health_remediation.models import RemediationBridgeReport

from .models import (
    HandoffPacket,
    HandoffPacketConfig,
    HandoffPacketDataQuality,
    HandoffPacketError,
    HandoffPacketGroup,
    HandoffPacketSafetyFlags,
)

_HANDOFF_PACKET_VERSION: str = "0.50.0-dev"

# ---------------------------------------------------------------------------
# Value helpers
# ---------------------------------------------------------------------------


def _coerce_str(value: Any) -> str:
    """Coerce a value to a deterministic string for hashing and metadata."""
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


def _make_stable_id(*parts: str) -> str:
    """Produce a stable hex hash from sorted deterministic parts."""
    raw = "|".join(sorted(_coerce_str(p) for p in parts))
    return sha256(raw.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Item extraction helpers
# ---------------------------------------------------------------------------


def _item_summary(item: RemediationBacklogItem) -> dict[str, Any]:
    """Extract a deterministic dict summary from a RemediationBacklogItem."""
    return {
        "item_id": item.item_id or "",
        "subject_id": item.subject_id or "",
        "source_id": item.source_id or "",
        "finding_id": item.finding_id or "",
        "item_type": item.item_type.value if item.item_type else "",
        "item_state": item.item_state.value if item.item_state else "",
        "severity": item.severity.value if item.severity else "",
        "priority": item.priority.value if item.priority else "",
        "title": item.title or "",
        "description": item.description or "",
        "owner": item.owner or "",
        "reviewer": item.reviewer or "",
        "reason_codes": [rc.value for rc in item.reason_codes] if item.reason_codes else [],
        "generated_at": str(item.generated_at) if item.generated_at else "",
        "metadata": dict(item.metadata) if item.metadata else {},
    }


def _extract_items(
    report_or_items: RemediationBridgeReport | tuple[RemediationBacklogItem, ...],
) -> tuple[RemediationBacklogItem, ...]:
    """Extract the RemediationBacklogItem tuple from the input."""
    if isinstance(report_or_items, RemediationBridgeReport):
        return report_or_items.items
    if isinstance(report_or_items, tuple):
        return report_or_items
    raise HandoffPacketError(
        "Input must be a RemediationBridgeReport or a tuple of RemediationBacklogItem"
    )


def _extract_source_report_id(report_or_items: RemediationBridgeReport | tuple[RemediationBacklogItem, ...]) -> str:
    """Extract the source report ID or a fallback."""
    if isinstance(report_or_items, RemediationBridgeReport):
        return report_or_items.source_report_id
    return "unknown_source"


# ---------------------------------------------------------------------------
# Severity/priority ordering
# ---------------------------------------------------------------------------

_SEVERITY_ORDER: dict[str, int] = {
    "blocking": 0,
    "advisory": 1,
    "info": 2,
}

_PRIORITY_ORDER: dict[str, int] = {
    "p0": 0,
    "p1": 1,
    "p2": 2,
    "p3": 3,
    "none": 4,
}


def _severity_sort_key(item: RemediationBacklogItem) -> tuple[int, int, str]:
    """Sort key: (priority_order, severity_order, item_id)."""
    sev = item.severity.value if item.severity else "info"
    pri = item.priority.value if item.priority else "none"
    return (
        _PRIORITY_ORDER.get(pri, 99),
        _SEVERITY_ORDER.get(sev, 99),
        item.item_id or "",
    )


# ---------------------------------------------------------------------------
# Forbidden-term scanning
# ---------------------------------------------------------------------------


def _contains_forbidden_term(text: str) -> bool:
    """Check if any string contains a forbidden readiness/trading term."""
    lower = text.lower()
    for term in FORBIDDEN_REMEDIATION_BACKLOG_TERMS:
        if term.lower() in lower:
            return True
    return False


def _scan_for_forbidden_terms(
    items: tuple[RemediationBacklogItem, ...],
) -> bool:
    """Scan all item summaries for forbidden terms. Returns True if any found."""
    for item in items:
        if _contains_forbidden_term(item.title or ""):
            return True
        if _contains_forbidden_term(item.description or ""):
            return True
        for val in (item.metadata or {}).values():
            if isinstance(val, str) and _contains_forbidden_term(val):
                return True
    return False


# ---------------------------------------------------------------------------
# Main engine function
# ---------------------------------------------------------------------------


def build_research_audit_remediation_handoff_packet(
    report_or_items: RemediationBridgeReport | tuple[RemediationBacklogItem, ...],
    config: HandoffPacketConfig | None = None,
) -> HandoffPacket:
    """Build a deterministic handoff packet from the remediation bridge output.

    Args:
        report_or_items: A RemediationBridgeReport or a tuple of
            RemediationBacklogItem summaries.
        config: Optional configuration. Defaults to HandoffPacketConfig().

    Returns:
        A HandoffPacket with grouped items, summary counts, and metadata.

    Raises:
        HandoffPacketError: If the input is invalid.
    """
    if config is None:
        config = HandoffPacketConfig()

    # Extract items
    all_items = _extract_items(report_or_items)
    source_report_id = _extract_source_report_id(report_or_items)
    input_count = len(all_items)

    # Sort items deterministically by (priority, severity, item_id)
    sorted_items = tuple(sorted(all_items, key=_severity_sort_key))

    # Filter INFO items if configured
    if config.exclude_info:
        filtered_items = tuple(
            item for item in sorted_items
            if item.severity != RemediationBacklogSeverity.INFO
        )
    else:
        filtered_items = sorted_items

    dropped_info = input_count - len(filtered_items)
    produced_count = len(filtered_items)

    # Scan for forbidden terms
    has_forbidden = _scan_for_forbidden_terms(filtered_items)

    # Group items by (severity, priority, item_type, joined_reason_codes, family)
    groups: dict[str, list[RemediationBacklogItem]] = {}
    for item in filtered_items:
        severity = item.severity.value if item.severity else "unknown"
        priority = item.priority.value if item.priority else "none"
        item_type = item.item_type.value if item.item_type else "unknown"
        reason_codes = item.reason_codes if item.reason_codes else ()
        reason_code_key = "+".join(sorted(rc.value for rc in reason_codes)) if reason_codes else "unknown"
        family = item.metadata.get("family", "") if item.metadata else ""
        if not family:
            family = "unknown"

        group_key = f"{severity}|{priority}|{item_type}|{reason_code_key}|{family}"
        if group_key not in groups:
            groups[group_key] = []
        groups[group_key].append(item)

    # Build HandoffPacketGroup objects
    packet_groups: list[HandoffPacketGroup] = []
    total_blocking = 0
    total_advisory = 0
    total_info = 0

    for group_key in sorted(groups.keys()):
        grp_items = groups[group_key]
        parts = group_key.split("|")
        severity_val = parts[0]
        priority_val = parts[1]
        item_type_val = parts[2]
        reason_code_val = parts[3]
        family_val = parts[4]

        blocking_count = sum(
            1 for i in grp_items
            if i.severity == RemediationBacklogSeverity.BLOCKING
        )
        advisory_count = sum(
            1 for i in grp_items
            if i.severity == RemediationBacklogSeverity.ADVISORY
        )
        info_count = sum(
            1 for i in grp_items
            if i.severity == RemediationBacklogSeverity.INFO
        )

        total_blocking += blocking_count
        total_advisory += advisory_count
        total_info += info_count

        # Sort items within group by (priority, severity, item_id)
        sorted_grp_items = sorted(grp_items, key=_severity_sort_key)
        summaries = tuple(_item_summary(i) for i in sorted_grp_items)

        group_id = _make_stable_id(group_key)
        group = HandoffPacketGroup(
            group_id=group_id,
            severity=severity_val,
            priority=priority_val,
            item_type=item_type_val,
            reason_code=reason_code_val,
            family=family_val,
            item_count=len(grp_items),
            blocking_count=blocking_count,
            advisory_count=advisory_count,
            info_count=info_count,
            items=summaries,
        )
        packet_groups.append(group)

    # Derive packet state
    if total_blocking > 0:
        state = "blocked"
    elif total_advisory > 0:
        state = "degraded"
    else:
        state = "ok"

    # Build packet ID
    group_ids = sorted(g.group_id for g in packet_groups)
    packet_id = _make_stable_id(source_report_id, *group_ids)

    # Data quality
    dq = HandoffPacketDataQuality(
        input_items=input_count,
        produced_items=produced_count,
        dropped_info=dropped_info,
        grouped_items=sum(g.item_count for g in packet_groups),
        safety_flagged_items=1 if has_forbidden else 0,
        group_count=len(packet_groups),
    )

    # Safety flags
    safety = HandoffPacketSafetyFlags(
        has_forbidden_terms=has_forbidden,
    )

    now = datetime.now(timezone.utc).isoformat()

    packet = HandoffPacket(
        packet_id=packet_id,
        source_report_id=source_report_id,
        generated_at=now,
        project_version=_HANDOFF_PACKET_VERSION,
        owner=config.owner,
        reviewer=config.reviewer,
        notes=config.notes,
        total_items=produced_count,
        total_blocking=total_blocking,
        total_advisory=total_advisory,
        total_info=total_info,
        group_count=len(packet_groups),
        state=state,
        groups=tuple(packet_groups),
        data_quality=dq,
        safety_flags=safety,
    )

    return packet
