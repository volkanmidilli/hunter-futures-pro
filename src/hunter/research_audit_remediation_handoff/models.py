"""Data models for the Research Audit Remediation Handoff Packet (MVP-50).

This module defines frozen dataclasses for the deterministic handoff packet
generator. The packet consumes a caller-provided MVP-49 `RemediationBridgeReport`
(or a sequence of `RemediationBacklogItem` summaries) and produces grouped
human-review summaries with metadata and counts. All references remain opaque
strings; the handoff generator never opens, traverses, validates, fetches, or
executes paths or references.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


class HandoffPacketError(Exception):
    """Base exception for the research audit remediation handoff packet."""


@dataclass(frozen=True, slots=True)
class HandoffPacketConfig:
    """Configuration for the handoff packet generator.

    Attributes:
        owner: Optional owner name propagated to the packet.
        reviewer: Optional reviewer name propagated to the packet.
        notes: Optional free-form notes propagated to the packet.
        exclude_info: If True, skip INFO-severity items.
        include_markdown_safety_notice: If True, include the standard
            research-only/audit-only safety notice in Markdown output.
    """

    owner: str | None = None
    reviewer: str | None = None
    notes: str = ""
    exclude_info: bool = False
    include_markdown_safety_notice: bool = True

    def __post_init__(self) -> None:
        if self.owner is not None and (not isinstance(self.owner, str) or not self.owner.strip()):
            raise ValueError("owner must be a non-empty string or None")
        if self.reviewer is not None and (not isinstance(self.reviewer, str) or not self.reviewer.strip()):
            raise ValueError("reviewer must be a non-empty string or None")
        object.__setattr__(self, "owner", self.owner if self.owner is None else self.owner.strip())
        object.__setattr__(self, "reviewer", self.reviewer if self.reviewer is None else self.reviewer.strip())
        object.__setattr__(self, "notes", str(self.notes))
        object.__setattr__(self, "exclude_info", bool(self.exclude_info))
        object.__setattr__(self, "include_markdown_safety_notice", bool(self.include_markdown_safety_notice))


@dataclass(frozen=True, slots=True)
class HandoffPacketGroup:
    """A single group within the handoff packet.

    Attributes:
        group_id: Stable deterministic hash of (severity, priority, item_type,
            reason_code, family).
        severity: Group severity label.
        priority: Group priority label.
        item_type: Group item type label.
        reason_code: Group reason code label.
        family: Group family label (from item metadata or "unknown").
        item_count: Total items in this group.
        blocking_count: Count of BLOCKING-severity items.
        advisory_count: Count of ADVISORY-severity items.
        info_count: Count of INFO-severity items.
        items: Deterministically ordered tuple of item summaries (dicts).
    """

    group_id: str
    severity: str
    priority: str
    item_type: str
    reason_code: str
    family: str
    item_count: int
    blocking_count: int
    advisory_count: int
    info_count: int
    items: tuple[dict[str, Any], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.group_id, str) or not self.group_id:
            raise ValueError("group_id must be a non-empty string")
        object.__setattr__(self, "severity", str(self.severity))
        object.__setattr__(self, "priority", str(self.priority))
        object.__setattr__(self, "item_type", str(self.item_type))
        object.__setattr__(self, "reason_code", str(self.reason_code))
        object.__setattr__(self, "family", str(self.family))
        for attr in ("item_count", "blocking_count", "advisory_count", "info_count"):
            value = getattr(self, attr)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{attr} must be a non-negative integer")
        if not isinstance(self.items, tuple):
            raise ValueError("items must be a tuple")


@dataclass(frozen=True, slots=True)
class HandoffPacketDataQuality:
    """Data-quality counters for the handoff packet.

    Attributes:
        input_items: Number of items received from the caller.
        produced_items: Number of items included in the packet after filtering.
        dropped_info: Number of INFO-severity items excluded by config.
        grouped_items: Number of items placed into groups (should equal
            produced_items).
        safety_flagged_items: Number of safety-flagged items.
        group_count: Number of distinct groups.
    """

    input_items: int = 0
    produced_items: int = 0
    dropped_info: int = 0
    grouped_items: int = 0
    safety_flagged_items: int = 0
    group_count: int = 0

    def __post_init__(self) -> None:
        for attr in (
            "input_items",
            "produced_items",
            "dropped_info",
            "grouped_items",
            "safety_flagged_items",
            "group_count",
        ):
            value = getattr(self, attr)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{attr} must be a non-negative integer")


@dataclass(frozen=True, slots=True)
class HandoffPacketSafetyFlags:
    """Safety flags for the handoff packet.

    Attributes:
        has_forbidden_terms: True if forbidden-term leakage was detected.
        references_opaque: True if all references remained opaque strings
            (always True; the engine never opens refs).
        no_executable_actions: True if no executable actions were emitted
            (always True).
        no_trading_instructions: True if no trading instructions were emitted
            (always True).
        no_approval_claims: True if no approval claims were made (always True).
    """

    has_forbidden_terms: bool = False
    references_opaque: bool = True
    no_executable_actions: bool = True
    no_trading_instructions: bool = True
    no_approval_claims: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "has_forbidden_terms", bool(self.has_forbidden_terms))
        object.__setattr__(self, "references_opaque", bool(self.references_opaque))
        object.__setattr__(self, "no_executable_actions", bool(self.no_executable_actions))
        object.__setattr__(self, "no_trading_instructions", bool(self.no_trading_instructions))
        object.__setattr__(self, "no_approval_claims", bool(self.no_approval_claims))


@dataclass(frozen=True, slots=True)
class HandoffPacket:
    """Deterministic handoff packet output.

    Attributes:
        packet_id: Stable deterministic hash of source_report_id and item hashes.
        source_report_id: Reference ID of the source remediation bridge report.
        generated_at: ISO-8601 timestamp string of packet generation.
        project_version: Project version at generation time.
        owner: Optional owner name.
        reviewer: Optional reviewer name.
        notes: Optional free-form notes.
        total_items: Total items in the packet.
        total_blocking: Count of BLOCKING-severity items.
        total_advisory: Count of ADVISORY-severity items.
        total_info: Count of INFO-severity items.
        group_count: Number of distinct groups.
        state: Packet-level state: "ok", "degraded", or "blocked".
        groups: Deterministically ordered tuple of groups.
        data_quality: Data-quality summary.
        safety_flags: Safety flags summary.
    """

    packet_id: str
    source_report_id: str
    generated_at: str
    project_version: str
    owner: str | None
    reviewer: str | None
    notes: str
    total_items: int
    total_blocking: int
    total_advisory: int
    total_info: int
    group_count: int
    state: str
    groups: tuple[HandoffPacketGroup, ...]
    data_quality: HandoffPacketDataQuality
    safety_flags: HandoffPacketSafetyFlags

    def __post_init__(self) -> None:
        if not isinstance(self.packet_id, str) or not self.packet_id:
            raise ValueError("packet_id must be a non-empty string")
        if not isinstance(self.source_report_id, str) or not self.source_report_id:
            raise ValueError("source_report_id must be a non-empty string")
        if not isinstance(self.generated_at, str) or not self.generated_at:
            raise ValueError("generated_at must be a non-empty ISO-8601 string")
        if not isinstance(self.project_version, str) or not self.project_version:
            raise ValueError("project_version must be a non-empty string")
        if self.owner is not None and (not isinstance(self.owner, str) or not self.owner.strip()):
            raise ValueError("owner must be a non-empty string or None")
        if self.reviewer is not None and (not isinstance(self.reviewer, str) or not self.reviewer.strip()):
            raise ValueError("reviewer must be a non-empty string or None")
        object.__setattr__(self, "notes", str(self.notes))
        for attr in ("total_items", "total_blocking", "total_advisory", "total_info", "group_count"):
            value = getattr(self, attr)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{attr} must be a non-negative integer")
        if self.state not in ("ok", "degraded", "blocked"):
            raise ValueError("state must be 'ok', 'degraded', or 'blocked'")
        if not isinstance(self.groups, tuple):
            raise ValueError("groups must be a tuple")
        if not isinstance(self.data_quality, HandoffPacketDataQuality):
            raise ValueError("data_quality must be a HandoffPacketDataQuality")
        if not isinstance(self.safety_flags, HandoffPacketSafetyFlags):
            raise ValueError("safety_flags must be a HandoffPacketSafetyFlags")
