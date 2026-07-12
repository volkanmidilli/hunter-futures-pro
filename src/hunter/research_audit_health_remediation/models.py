"""Data models for the Research Audit Health Remediation Bridge (MVP-49).

This module defines frozen dataclasses for the deterministic bridge between
MVP-48 `HealthReport` findings and MVP-38 `RemediationBacklogItem` entries.
All references remain opaque strings; the bridge never opens, traverses,
validates, fetches, or executes paths or references.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from hunter.remediation_backlog.models import RemediationBacklogItem, RemediationBacklogSafetyFlags


class RemediationBridgeError(Exception):
    """Base exception for the research audit health remediation bridge."""


@dataclass(frozen=True, slots=True)
class RemediationBridgeConfig:
    """Configuration for mapping health findings to remediation backlog items."""

    strict: bool = False
    owner: str | None = None
    reviewer: str | None = None
    exclude_info: bool = False
    severity_to_priority: Mapping[str, str] = field(default_factory=dict)
    reason_to_item_type: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "strict", bool(self.strict))
        object.__setattr__(self, "exclude_info", bool(self.exclude_info))
        if self.owner is not None and (not isinstance(self.owner, str) or not self.owner.strip()):
            raise ValueError("owner must be a non-empty string or None")
        if self.reviewer is not None and (not isinstance(self.reviewer, str) or not self.reviewer.strip()):
            raise ValueError("reviewer must be a non-empty string or None")
        object.__setattr__(self, "owner", self.owner if self.owner is None else self.owner.strip())
        object.__setattr__(self, "reviewer", self.reviewer if self.reviewer is None else self.reviewer.strip())
        object.__setattr__(
            self,
            "severity_to_priority",
            _coerce_str_mapping(self.severity_to_priority),
        )
        object.__setattr__(
            self,
            "reason_to_item_type",
            _coerce_str_mapping(self.reason_to_item_type),
        )


@dataclass(frozen=True, slots=True)
class RemediationBridgeDataQuality:
    """Counters summarizing the bridge run."""

    input_findings: int = 0
    produced_items: int = 0
    dropped_info: int = 0
    duplicates_collapsed: int = 0
    safety_flagged_items: int = 0

    def __post_init__(self) -> None:
        for attr in (
            "input_findings",
            "produced_items",
            "dropped_info",
            "duplicates_collapsed",
            "safety_flagged_items",
        ):
            value = getattr(self, attr)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{attr} must be a non-negative integer")


@dataclass(frozen=True, slots=True)
class RemediationBridgeReport:
    """Deterministic output of the health remediation bridge."""

    report_id: str
    source_report_id: str
    generated_at: str
    items: tuple[RemediationBacklogItem, ...]
    data_quality: RemediationBridgeDataQuality
    safety_flags: RemediationBacklogSafetyFlags

    def __post_init__(self) -> None:
        if not isinstance(self.report_id, str) or not self.report_id:
            raise ValueError("report_id must be a non-empty string")
        if not isinstance(self.source_report_id, str) or not self.source_report_id:
            raise ValueError("source_report_id must be a non-empty string")
        if not isinstance(self.generated_at, str) or not self.generated_at:
            raise ValueError("generated_at must be a non-empty ISO-8601 string")
        if not isinstance(self.items, tuple):
            raise ValueError("items must be a tuple")
        if not isinstance(self.data_quality, RemediationBridgeDataQuality):
            raise ValueError("data_quality must be a RemediationBridgeDataQuality")
        if not isinstance(self.safety_flags, RemediationBacklogSafetyFlags):
            raise ValueError("safety_flags must be a RemediationBacklogSafetyFlags")


def _coerce_str_mapping(value: Mapping[str, Any] | dict[str, Any] | None) -> Mapping[str, str]:
    """Coerce a mapping into an immutable MappingProxyType with string values."""
    from types import MappingProxyType

    if value is None:
        return MappingProxyType({})
    if not isinstance(value, Mapping):
        raise ValueError("override mapping must be a Mapping[str, str]")
    result: dict[str, str] = {}
    for key, val in value.items():
        if not isinstance(key, str):
            raise ValueError("override mapping keys must be strings")
        if not isinstance(val, str):
            raise ValueError("override mapping values must be strings")
        result[key] = val
    return MappingProxyType(result)
