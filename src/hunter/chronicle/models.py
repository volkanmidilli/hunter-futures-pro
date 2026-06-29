"""Chronicle models for hunter.chronicle package.

Frozen dataclasses, enums, and constants for the Local Research Chronicle / Audit Timeline.

MVP-15 chronicle is a human-audit-only artifact. It is not a trading signal, not
trade approval, and must not be consumed by execution, strategy, Freqtrade shell,
order, exchange, or any MVP execution path.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ArtifactType(Enum):
    """Artifact type for chronicle entries."""

    OBSERVATION = "observation"
    REVIEW = "review"
    INDEX = "index"
    SEARCH = "search"
    BUNDLE = "bundle"


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CHRONICLE_VERSION = "1.0"


# ---------------------------------------------------------------------------
# Reason codes
# ---------------------------------------------------------------------------

CHRONICLE_BLOCKING_REASON_CODES = (
    "MISSING_ARTIFACTS",              # 1 — no artifacts provided at all
    "INVALID_OBSERVATION",            # 2 — observation missing required fields
    "INVALID_REVIEW",                 # 3 — review missing required fields
    "INVALID_INDEX",                  # 4 — index missing required fields
    "INVALID_SEARCH",                 # 5 — search result missing required fields
    "INVALID_BUNDLE",                 # 6 — bundle missing required fields
    "INVALID_TIMESTAMP",              # 7 — timestamp missing or not timezone-aware
    "MISSING_TRACE_ID",               # 8 — trace_id could not be derived or is absent
    "UNSUPPORTED_OBSERVATION_VERSION",  # 9 — observation version not recognized
    "UNSUPPORTED_REVIEW_VERSION",     # 10 — review version not recognized
    "UNSUPPORTED_INDEX_VERSION",      # 11 — index version not recognized
    "UNSUPPORTED_SEARCH_VERSION",     # 12 — search version not recognized
    "UNSUPPORTED_BUNDLE_VERSION",     # 13 — bundle version not recognized
    "UNSAFE_CHRONICLE_CONTENT",       # 14 — forbidden terms in notes/metadata
    "CHRONICLE_ERROR",                # 15 — catch-all for unexpected errors
)

CHRONICLE_TRACKING_REASON_CODES = (
    "STALE_ARTIFACT",                 # tracked in data_quality, not blocking
    "ORPHAN_OBSERVATION",             # tracked in data_quality, not blocking
    "ORPHAN_REVIEW",                  # tracked in data_quality, not blocking
)

CHRONICLE_REASON_CODES = CHRONICLE_BLOCKING_REASON_CODES + CHRONICLE_TRACKING_REASON_CODES


# ---------------------------------------------------------------------------
# Forbidden content
# ---------------------------------------------------------------------------

FORBIDDEN_CHRONICLE_TERMS = frozenset({
    "enter_long", "enter_short", "exit_long", "exit_short",
    "api_key", "secret", "exchange_credentials", "executable_instructions",
    "order", "position", "leverage", "margin", "liquidation",
    "private_key", "password", "token", "auth",
})


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ChronicleEntry:
    """A single chronicle event for one artifact."""

    entry_id: str
    timestamp: datetime
    artifact_type: ArtifactType
    trace_id: str
    state: str
    version: str
    entry_count: int = 0
    reason_codes: tuple[str, ...] = ()
    actor: str | None = None
    notes: str | None = None
    tags: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    related_trace_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.entry_id, str) or not self.entry_id:
            raise ValueError("entry_id must be a non-empty string")
        if not isinstance(self.timestamp, datetime) or self.timestamp.tzinfo is None:
            raise ValueError("timestamp must be a timezone-aware datetime")
        if not isinstance(self.artifact_type, ArtifactType):
            raise ValueError(f"artifact_type must be an ArtifactType, got {type(self.artifact_type)}")
        if not isinstance(self.trace_id, str) or not self.trace_id:
            raise ValueError("trace_id must be a non-empty string")
        if not isinstance(self.state, str) or not self.state:
            raise ValueError("state must be a non-empty string")
        if not isinstance(self.version, str) or not self.version:
            raise ValueError("version must be a non-empty string")
        if not isinstance(self.entry_count, int) or self.entry_count < 0:
            raise ValueError("entry_count must be >= 0")
        if not isinstance(self.reason_codes, tuple):
            raise ValueError("reason_codes must be a tuple")
        for code in self.reason_codes:
            if not isinstance(code, str) or not code:
                raise ValueError("reason_codes must contain non-empty strings")
        if self.actor is not None and (not isinstance(self.actor, str) or not self.actor):
            raise ValueError("actor must be a non-empty string or None")
        if self.notes is not None and _has_unsafe_chronicle_content(self.notes):
            raise ValueError("notes contains forbidden content")
        if not isinstance(self.tags, tuple):
            raise ValueError("tags must be a tuple")
        for tag in self.tags:
            if not isinstance(tag, str) or not tag:
                raise ValueError("tags must contain non-empty strings")
            if _has_unsafe_chronicle_content(tag):
                raise ValueError("tags contain forbidden content")
        if not isinstance(self.metadata, Mapping):
            raise ValueError("metadata must be a Mapping")
        for key in self.metadata:
            if _has_unsafe_chronicle_content(key):
                raise ValueError(f"metadata key contains forbidden content: {key}")
        if not isinstance(self.related_trace_ids, tuple):
            raise ValueError("related_trace_ids must be a tuple")
        for rtid in self.related_trace_ids:
            if not isinstance(rtid, str) or not rtid:
                raise ValueError("related_trace_ids must contain non-empty strings")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @classmethod
    def blocked(
        cls,
        *,
        entry_id: str = "blocked",
        timestamp: datetime | None = None,
        artifact_type: ArtifactType = ArtifactType.OBSERVATION,
        trace_id: str = "blocked",
        state: str = "BLOCKED",
        version: str = CHRONICLE_VERSION,
        reason_codes: tuple[str, ...] = ("CHRONICLE_ERROR",),
    ) -> "ChronicleEntry":
        """Factory for a blocked chronicle entry."""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        return cls(
            entry_id=entry_id,
            timestamp=timestamp,
            artifact_type=artifact_type,
            trace_id=trace_id,
            state=state,
            version=version,
            reason_codes=reason_codes,
        )


@dataclass(frozen=True)
class ChronicleSummary:
    """Aggregated counts across all chronicle entries."""

    total_entries: int = 0
    observation_count: int = 0
    review_count: int = 0
    index_count: int = 0
    search_count: int = 0
    bundle_count: int = 0
    blocked_count: int = 0
    ready_count: int = 0
    accepted_count: int = 0
    rejected_count: int = 0
    unknown_count: int = 0
    reason_code_counts: Mapping[str, int] = field(default_factory=dict)
    tag_counts: Mapping[str, int] = field(default_factory=dict)
    actor_counts: Mapping[str, int] = field(default_factory=dict)
    timestamp_range: tuple[str, str] | None = None
    daily_counts: Mapping[str, Mapping[str, int]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "total_entries",
            "observation_count",
            "review_count",
            "index_count",
            "search_count",
            "bundle_count",
            "blocked_count",
            "ready_count",
            "accepted_count",
            "rejected_count",
            "unknown_count",
        ):
            if getattr(self, field_name) < 0:
                raise ValueError(f"{field_name} must be >= 0")
        type_sum = (
            self.observation_count
            + self.review_count
            + self.index_count
            + self.search_count
            + self.bundle_count
        )
        if type_sum > self.total_entries:
            raise ValueError("type counts must not exceed total_entries")
        state_sum = self.blocked_count + self.ready_count + self.unknown_count
        if state_sum > self.total_entries:
            raise ValueError("state counts must not exceed total_entries")
        status_sum = self.accepted_count + self.rejected_count
        if status_sum > self.total_entries:
            raise ValueError("status counts (accepted + rejected) must not exceed total_entries")
        for k, v in self.reason_code_counts.items():
            if not isinstance(k, str) or not k:
                raise ValueError("reason_code_counts keys must be non-empty strings")
            if v < 0:
                raise ValueError(f"reason_code_counts value for '{k}' must be >= 0")
        for k, v in self.tag_counts.items():
            if not isinstance(k, str) or not k:
                raise ValueError("tag_counts keys must be non-empty strings")
            if v < 0:
                raise ValueError(f"tag_counts value for '{k}' must be >= 0")
        for k, v in self.actor_counts.items():
            if not isinstance(k, str) or not k:
                raise ValueError("actor_counts keys must be non-empty strings")
            if v < 0:
                raise ValueError(f"actor_counts value for '{k}' must be >= 0")
        if self.timestamp_range is not None:
            if not isinstance(self.timestamp_range, tuple) or len(self.timestamp_range) != 2:
                raise ValueError("timestamp_range must be a tuple of two strings or None")
            for ts in self.timestamp_range:
                if not isinstance(ts, str) or not ts:
                    raise ValueError("timestamp_range values must be non-empty strings")
        for day, day_counts in self.daily_counts.items():
            if not isinstance(day, str) or not day:
                raise ValueError("daily_counts keys must be non-empty strings")
            for k, v in day_counts.items():
                if not isinstance(k, str) or not k:
                    raise ValueError("daily_counts inner keys must be non-empty strings")
                if v < 0:
                    raise ValueError(f"daily_counts value for '{k}' must be >= 0")
        _daily = {k: MappingProxyType(dict(v)) for k, v in self.daily_counts.items()}
        object.__setattr__(self, "reason_code_counts", MappingProxyType(dict(self.reason_code_counts)))
        object.__setattr__(self, "tag_counts", MappingProxyType(dict(self.tag_counts)))
        object.__setattr__(self, "actor_counts", MappingProxyType(dict(self.actor_counts)))
        object.__setattr__(self, "daily_counts", MappingProxyType(dict(_daily)))


@dataclass(frozen=True)
class ChronicleDataQuality:
    """Completeness and quality metrics for the chronicle."""

    has_observations: bool = False
    has_reviews: bool = False
    has_index: bool = False
    has_search: bool = False
    has_bundle: bool = False
    orphan_observation_count: int = 0
    orphan_review_count: int = 0
    trace_completeness_pct: float = 0.0
    gap_count: int = 0
    stale_entry_count: int = 0
    validation_errors: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in ("orphan_observation_count", "orphan_review_count", "gap_count", "stale_entry_count"):
            if getattr(self, field_name) < 0:
                raise ValueError(f"{field_name} must be >= 0")
        if not isinstance(self.trace_completeness_pct, (int, float)):
            raise ValueError("trace_completeness_pct must be a number")
        if self.trace_completeness_pct < 0.0 or self.trace_completeness_pct > 100.0:
            raise ValueError("trace_completeness_pct must be between 0.0 and 100.0")
        if not isinstance(self.validation_errors, tuple):
            raise ValueError("validation_errors must be a tuple")
        for err in self.validation_errors:
            if not isinstance(err, str) or not err:
                raise ValueError("validation_errors must contain non-empty strings")


@dataclass(frozen=True)
class ChronicleSafetyFlags:
    """Safety flags that must remain fail-closed for chronicle artifacts."""

    dry_run: bool = True
    live_trading_enabled: bool = False
    real_orders_enabled: bool = False
    leverage_enabled: bool = False
    shorting_enabled: bool = False
    chronicle_output_is_human_audit_only: bool = True
    chronicle_output_not_trading_signal: bool = True
    chronicle_output_not_trade_approval: bool = True
    chronicle_output_not_for_execution: bool = True
    chronicle_output_not_for_strategy: bool = True
    chronicle_output_not_for_freqtrade: bool = True
    chronicle_output_not_for_order: bool = True
    chronicle_output_not_for_exchange: bool = True
    chronicle_feedback_into_execution: bool = False

    def __post_init__(self) -> None:
        unsafe_flags = (
            self.live_trading_enabled,
            self.real_orders_enabled,
            self.leverage_enabled,
            self.shorting_enabled,
            self.chronicle_feedback_into_execution,
        )
        if any(unsafe_flags):
            raise ValueError("unsafe chronicle safety flags are enabled")
        safe_flags = (
            self.chronicle_output_is_human_audit_only,
            self.chronicle_output_not_trading_signal,
            self.chronicle_output_not_trade_approval,
            self.chronicle_output_not_for_execution,
            self.chronicle_output_not_for_strategy,
            self.chronicle_output_not_for_freqtrade,
            self.chronicle_output_not_for_order,
            self.chronicle_output_not_for_exchange,
        )
        if not all(safe_flags):
            raise ValueError("safe chronicle output flags must be True")


@dataclass(frozen=True)
class ResearchChronicle:
    """Full chronicle container with fail-closed blocked factory."""

    chronicle_id: str
    generated_at: datetime
    version: str = CHRONICLE_VERSION
    entries: tuple[ChronicleEntry, ...] = ()
    summary: ChronicleSummary = field(default_factory=ChronicleSummary)
    data_quality: ChronicleDataQuality = field(default_factory=ChronicleDataQuality)
    safety_flags: ChronicleSafetyFlags = field(default_factory=ChronicleSafetyFlags)
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.chronicle_id, str) or not self.chronicle_id:
            raise ValueError("chronicle_id must be a non-empty string")
        if not isinstance(self.generated_at, datetime) or self.generated_at.tzinfo is None:
            raise ValueError("generated_at must be a timezone-aware datetime")
        if not isinstance(self.entries, tuple):
            raise ValueError("entries must be a tuple")
        for entry in self.entries:
            if not isinstance(entry, ChronicleEntry):
                raise ValueError("entries must contain ChronicleEntry values")
        if not isinstance(self.reason_codes, tuple):
            raise ValueError("reason_codes must be a tuple")
        for code in self.reason_codes:
            if not isinstance(code, str) or not code:
                raise ValueError("reason_codes must contain non-empty strings")

    @classmethod
    def blocked(
        cls,
        reason: str = "CHRONICLE_ERROR",
        chronicle_id: str = "blocked",
        generated_at: datetime | None = None,
    ) -> "ResearchChronicle":
        """Factory for a blocked chronicle."""
        if generated_at is None:
            generated_at = datetime.now(timezone.utc)
        return cls(
            chronicle_id=chronicle_id,
            generated_at=generated_at,
            version=CHRONICLE_VERSION,
            entries=(),
            summary=ChronicleSummary(),
            data_quality=ChronicleDataQuality(),
            safety_flags=ChronicleSafetyFlags(),
            reason_codes=(reason,),
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _has_unsafe_chronicle_content(text: str) -> bool:
    """Return True if text contains forbidden chronicle terms."""
    if not isinstance(text, str):
        return False
    lower = text.lower()
    for term in FORBIDDEN_CHRONICLE_TERMS:
        if term in lower:
            return True
    return False
