"""Index models for hunter.review_index package.

Frozen dataclasses, enums, and constants for the Local Review Index layer.
All models are immutable and validated at construction time.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class IndexState(Enum):
    """Index state — mirrors ReviewState for consistency."""

    DISABLED = "DISABLED"
    READY = "READY"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"


class IndexEntryKind(Enum):
    """Kind of catalog entry."""

    OBSERVATION_REPORT = "OBSERVATION_REPORT"
    REVIEW_AUDIT_RECORD = "REVIEW_AUDIT_RECORD"
    LINKED_REPORT_REVIEW = "LINKED_REPORT_REVIEW"


class IndexOutputFormat(Enum):
    """Supported output formats for the index."""

    JSON = "JSON"
    MARKDOWN = "MARKDOWN"


# ---------------------------------------------------------------------------
# Reason codes (deterministic, priority-ordered)
# ---------------------------------------------------------------------------

MISSING_REPORTS = "MISSING_REPORTS"
MISSING_REVIEWS = "MISSING_REVIEWS"
INVALID_REPORT = "INVALID_REPORT"
INVALID_REVIEW = "INVALID_REVIEW"
UNSUPPORTED_REPORT_VERSION = "UNSUPPORTED_REPORT_VERSION"
UNSUPPORTED_REVIEW_VERSION = "UNSUPPORTED_REVIEW_VERSION"
UNSAFE_REPORT_STATE = "UNSAFE_REPORT_STATE"
UNSAFE_REVIEW_STATE = "UNSAFE_REVIEW_STATE"
UNSAFE_SAFETY_FLAGS = "UNSAFE_SAFETY_FLAGS"
UNSAFE_INDEX_CONTENT = "UNSAFE_INDEX_CONTENT"
EMPTY_INDEX = "EMPTY_INDEX"
INDEX_ERROR = "INDEX_ERROR"
DEFAULT_BLOCKED = "DEFAULT_BLOCKED"

REASON_CODES: tuple[str, ...] = (
    MISSING_REPORTS,
    MISSING_REVIEWS,
    INVALID_REPORT,
    INVALID_REVIEW,
    UNSUPPORTED_REPORT_VERSION,
    UNSUPPORTED_REVIEW_VERSION,
    UNSAFE_REPORT_STATE,
    UNSAFE_REVIEW_STATE,
    UNSAFE_SAFETY_FLAGS,
    UNSAFE_INDEX_CONTENT,
    EMPTY_INDEX,
    INDEX_ERROR,
    DEFAULT_BLOCKED,
)

# ---------------------------------------------------------------------------
# Forbidden index content
# ---------------------------------------------------------------------------

FORBIDDEN_INDEX_TERMS: frozenset[str] = frozenset({
    "api_key",
    "secret",
    "exchange_credentials",
    "executable_instructions",
    "operational_instructions",
    "enter_long",
    "enter_short",
    "exit_long",
    "exit_short",
    "order",
    "leverage",
    "shorting",
    "binance",
    "exchange",
})


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class IndexConfig:
    """Configuration for index building."""

    observation_report_version: str = "1.0"
    review_audit_version: str = "1.0"
    enable_json_output: bool = True
    enable_markdown_output: bool = True
    dry_run: bool = True
    live_trading_enabled: bool = False
    real_orders_enabled: bool = False
    leverage_enabled: bool = False
    shorting_enabled: bool = False
    allow_report_feedback_into_execution: bool = False
    allow_operator_feedback_into_execution: bool = False
    allow_index_feedback_into_execution: bool = False
    allow_file_reference_traversal: bool = False
    allow_database_persistence: bool = False
    allow_web_ui: bool = False
    allow_dashboard: bool = False

    def __post_init__(self) -> None:
        if not self.observation_report_version:
            raise ValueError("observation_report_version must be non-empty")
        if not self.review_audit_version:
            raise ValueError("review_audit_version must be non-empty")
        if not self.enable_json_output and not self.enable_markdown_output:
            raise ValueError("at least one output format must be enabled")
        if not self.dry_run:
            raise ValueError("dry_run must be True")
        if self.live_trading_enabled:
            raise ValueError("live_trading_enabled must be False")
        if self.real_orders_enabled:
            raise ValueError("real_orders_enabled must be False")
        if self.leverage_enabled:
            raise ValueError("leverage_enabled must be False")
        if self.shorting_enabled:
            raise ValueError("shorting_enabled must be False")
        if self.allow_report_feedback_into_execution:
            raise ValueError("allow_report_feedback_into_execution must be False")
        if self.allow_operator_feedback_into_execution:
            raise ValueError("allow_operator_feedback_into_execution must be False")
        if self.allow_index_feedback_into_execution:
            raise ValueError("allow_index_feedback_into_execution must be False")
        if self.allow_file_reference_traversal:
            raise ValueError("allow_file_reference_traversal must be False")
        if self.allow_database_persistence:
            raise ValueError("allow_database_persistence must be False")
        if self.allow_web_ui:
            raise ValueError("allow_web_ui must be False")
        if self.allow_dashboard:
            raise ValueError("allow_dashboard must be False")


@dataclass(frozen=True)
class IndexSafetyFlags:
    """Safety invariants for the index."""

    dry_run: bool = True
    live_trading_enabled: bool = False
    real_orders_enabled: bool = False
    leverage_enabled: bool = False
    shorting_enabled: bool = False
    report_feedback_into_execution: bool = False
    operator_feedback_into_execution: bool = False
    index_feedback_into_execution: bool = False
    file_reference_traversal_enabled: bool = False
    database_persistence_enabled: bool = False
    web_ui_enabled: bool = False
    dashboard_enabled: bool = False

    def __post_init__(self) -> None:
        if not self.dry_run:
            raise ValueError("dry_run must be True")
        if self.live_trading_enabled:
            raise ValueError("live_trading_enabled must be False")
        if self.real_orders_enabled:
            raise ValueError("real_orders_enabled must be False")
        if self.leverage_enabled:
            raise ValueError("leverage_enabled must be False")
        if self.shorting_enabled:
            raise ValueError("shorting_enabled must be False")
        if self.report_feedback_into_execution:
            raise ValueError("report_feedback_into_execution must be False")
        if self.operator_feedback_into_execution:
            raise ValueError("operator_feedback_into_execution must be False")
        if self.index_feedback_into_execution:
            raise ValueError("index_feedback_into_execution must be False")
        if self.file_reference_traversal_enabled:
            raise ValueError("file_reference_traversal_enabled must be False")
        if self.database_persistence_enabled:
            raise ValueError("database_persistence_enabled must be False")
        if self.web_ui_enabled:
            raise ValueError("web_ui_enabled must be False")
        if self.dashboard_enabled:
            raise ValueError("dashboard_enabled must be False")


@dataclass(frozen=True)
class IndexEntry:
    """Single catalog entry for a report + optional review."""

    entry_id: str
    entry_kind: IndexEntryKind
    index_state: IndexState
    report_id: str
    audit_id: str = ""
    report_generated_at: datetime | None = None
    audit_generated_at: datetime | None = None
    reviewed_at: datetime | None = None
    review_status: str = "NOT_REVIEWED"
    review_state: str = "UNKNOWN"
    source_report_version: str = ""
    source_review_version: str = ""
    reason_codes: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    reviewer: str = ""
    local_report_reference: str = ""
    local_review_reference: str = ""
    safety_flags: IndexSafetyFlags = field(default_factory=IndexSafetyFlags)
    metadata: Mapping[str, Any] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if not self.entry_id:
            raise ValueError("entry_id must be non-empty")
        if not isinstance(self.entry_kind, IndexEntryKind):
            raise ValueError(f"entry_kind must be IndexEntryKind, got {type(self.entry_kind)}")
        if not isinstance(self.index_state, IndexState):
            raise ValueError(f"index_state must be IndexState, got {type(self.index_state)}")
        if not self.report_id:
            raise ValueError("report_id must be non-empty")
        if self.report_generated_at is not None and self.report_generated_at.tzinfo is None:
            raise ValueError("report_generated_at must be timezone-aware")
        if self.audit_generated_at is not None and self.audit_generated_at.tzinfo is None:
            raise ValueError("audit_generated_at must be timezone-aware")
        if self.reviewed_at is not None and self.reviewed_at.tzinfo is None:
            raise ValueError("reviewed_at must be timezone-aware")
        if self.review_status not in ("NOT_REVIEWED", "REVIEWED", "ACCEPTED", "REJECTED", "NEEDS_INVESTIGATION"):
            raise ValueError(f"invalid review_status: {self.review_status}")
        if self.review_state not in ("DISABLED", "READY", "BLOCKED", "UNKNOWN"):
            raise ValueError(f"invalid review_state: {self.review_state}")
        if self.index_state is not IndexState.READY and not self.reason_codes:
            raise ValueError("reason_codes must be non-empty when index_state is not READY")
        # Forbidden content check
        _check_forbidden(self.tags, "tags")
        _check_forbidden((self.reviewer,), "reviewer")
        _check_forbidden((self.local_report_reference, self.local_review_reference), "references")
        _check_forbidden_keys(self.metadata, "metadata")

    @classmethod
    def blocked(
        cls,
        *,
        entry_id: str = "blocked",
        report_id: str = "blocked",
        reason_codes: tuple[str, ...] = (DEFAULT_BLOCKED,),
        safety_flags: IndexSafetyFlags | None = None,
    ) -> "IndexEntry":
        """Create a blocked index entry for audit/catalog purposes only."""
        if safety_flags is None:
            safety_flags = IndexSafetyFlags()
        return cls(
            entry_id=entry_id,
            entry_kind=IndexEntryKind.LINKED_REPORT_REVIEW,
            index_state=IndexState.BLOCKED,
            report_id=report_id,
            audit_id="",
            report_generated_at=None,
            audit_generated_at=None,
            reviewed_at=None,
            review_status="NOT_REVIEWED",
            review_state="UNKNOWN",
            source_report_version="",
            source_review_version="",
            reason_codes=reason_codes,
            tags=(),
            reviewer="",
            local_report_reference="",
            local_review_reference="",
            safety_flags=safety_flags,
            metadata={},
        )


@dataclass(frozen=True)
class IndexSummary:
    """Aggregated counts across all index entries."""

    total_entries: int = 0
    observation_report_count: int = 0
    review_audit_count: int = 0
    linked_entry_count: int = 0
    ready_count: int = 0
    blocked_count: int = 0
    unknown_count: int = 0
    accepted_count: int = 0
    rejected_count: int = 0
    needs_investigation_count: int = 0
    not_reviewed_count: int = 0
    reason_counts: Mapping[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.total_entries < 0:
            raise ValueError("total_entries must be >= 0")
        if self.observation_report_count < 0:
            raise ValueError("observation_report_count must be >= 0")
        if self.review_audit_count < 0:
            raise ValueError("review_audit_count must be >= 0")
        if self.linked_entry_count < 0:
            raise ValueError("linked_entry_count must be >= 0")
        if self.ready_count < 0:
            raise ValueError("ready_count must be >= 0")
        if self.blocked_count < 0:
            raise ValueError("blocked_count must be >= 0")
        if self.unknown_count < 0:
            raise ValueError("unknown_count must be >= 0")
        if self.accepted_count < 0:
            raise ValueError("accepted_count must be >= 0")
        if self.rejected_count < 0:
            raise ValueError("rejected_count must be >= 0")
        if self.needs_investigation_count < 0:
            raise ValueError("needs_investigation_count must be >= 0")
        if self.not_reviewed_count < 0:
            raise ValueError("not_reviewed_count must be >= 0")
        # Category counts must not exceed total
        category_sum = (
            self.observation_report_count
            + self.review_audit_count
            + self.linked_entry_count
        )
        if category_sum > self.total_entries:
            raise ValueError("category counts must not exceed total_entries")
        status_sum = (
            self.accepted_count
            + self.rejected_count
            + self.needs_investigation_count
            + self.not_reviewed_count
        )
        if status_sum > self.total_entries:
            raise ValueError("status counts must not exceed total_entries")
        state_sum = (
            self.ready_count
            + self.blocked_count
            + self.unknown_count
        )
        if state_sum > self.total_entries:
            raise ValueError("state counts must not exceed total_entries")
        for k, v in self.reason_counts.items():
            if v < 0:
                raise ValueError(f"reason_counts[{k}] must be >= 0")


@dataclass(frozen=True)
class IndexDataQuality:
    """Completeness and quality metrics for the index."""

    total_reports: int = 0
    valid_reports: int = 0
    invalid_reports: int = 0
    unsafe_reports: int = 0
    total_reviews: int = 0
    valid_reviews: int = 0
    invalid_reviews: int = 0
    unsafe_reviews: int = 0
    linked_records: int = 0
    unlinked_reports: int = 0
    unlinked_reviews: int = 0

    def __post_init__(self) -> None:
        if self.total_reports < 0:
            raise ValueError("total_reports must be >= 0")
        if self.valid_reports < 0:
            raise ValueError("valid_reports must be >= 0")
        if self.invalid_reports < 0:
            raise ValueError("invalid_reports must be >= 0")
        if self.unsafe_reports < 0:
            raise ValueError("unsafe_reports must be >= 0")
        if self.total_reviews < 0:
            raise ValueError("total_reviews must be >= 0")
        if self.valid_reviews < 0:
            raise ValueError("valid_reviews must be >= 0")
        if self.invalid_reviews < 0:
            raise ValueError("invalid_reviews must be >= 0")
        if self.unsafe_reviews < 0:
            raise ValueError("unsafe_reviews must be >= 0")
        if self.linked_records < 0:
            raise ValueError("linked_records must be >= 0")
        if self.unlinked_reports < 0:
            raise ValueError("unlinked_reports must be >= 0")
        if self.unlinked_reviews < 0:
            raise ValueError("unlinked_reviews must be >= 0")
        if self.valid_reports + self.invalid_reports + self.unsafe_reports > self.total_reports:
            raise ValueError("report category counts must not exceed total_reports")
        if self.valid_reviews + self.invalid_reviews + self.unsafe_reviews > self.total_reviews:
            raise ValueError("review category counts must not exceed total_reviews")


@dataclass(frozen=True)
class ReviewIndex:
    """Full index container with fail-closed blocked factory."""

    index_id: str
    generated_at: datetime
    index_state: IndexState
    entries: tuple[IndexEntry, ...]
    summary: IndexSummary
    data_quality: IndexDataQuality
    safety_flags: IndexSafetyFlags
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.index_id:
            raise ValueError("index_id must be non-empty")
        if self.generated_at.tzinfo is None:
            raise ValueError("generated_at must be timezone-aware")
        if not isinstance(self.index_state, IndexState):
            raise ValueError(f"index_state must be IndexState, got {type(self.index_state)}")
        if self.index_state is not IndexState.READY and not self.reason_codes:
            raise ValueError("reason_codes must be non-empty when index_state is not READY")

    @classmethod
    def blocked(
        cls,
        *,
        index_id: str = "blocked",
        generated_at: datetime | None = None,
        reason_codes: tuple[str, ...] = (DEFAULT_BLOCKED,),
        safety_flags: IndexSafetyFlags | None = None,
    ) -> "ReviewIndex":
        """Create a blocked review index for audit/catalog purposes only."""
        if generated_at is None:
            generated_at = datetime.now(timezone.utc)
        if safety_flags is None:
            safety_flags = IndexSafetyFlags()
        return cls(
            index_id=index_id,
            generated_at=generated_at,
            index_state=IndexState.BLOCKED,
            entries=(),
            summary=IndexSummary(),
            data_quality=IndexDataQuality(),
            safety_flags=safety_flags,
            reason_codes=reason_codes,
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _check_forbidden(items: tuple[str, ...], field_name: str) -> None:
    """Check for forbidden terms in string fields."""
    for item in items:
        if not item:
            continue
        lower = item.lower()
        for term in FORBIDDEN_INDEX_TERMS:
            if term in lower:
                raise ValueError(
                    f"forbidden term '{term}' found in {field_name}: {item!r}"
                )


def _check_forbidden_keys(mapping: Mapping[str, Any], field_name: str) -> None:
    """Check for forbidden terms in mapping keys."""
    for key in mapping:
        lower = key.lower()
        for term in FORBIDDEN_INDEX_TERMS:
            if term in lower:
                raise ValueError(
                    f"forbidden term '{term}' found in {field_name} key: {key!r}"
                )
