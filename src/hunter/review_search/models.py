"""Models for the local audit-only review search/query layer.

These models intentionally contain no file I/O, network access, database
persistence, UI, dashboard, exchange, Freqtrade, Binance, live trading, real
orders, leverage, shorting, or real entry/exit logic.

Search results are human-audit artifacts only. They are not trading signals,
not trade approvals, and must not be consumed by execution, strategy,
Freqtrade shell, order, exchange, or any MVP execution path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping

from hunter.review_index.models import IndexEntryKind, IndexState


# ---------------------------------------------------------------------------
# Deterministic fail-closed reason codes
# ---------------------------------------------------------------------------

MISSING_INDEX = "MISSING_INDEX"
MISSING_QUERY = "MISSING_QUERY"
INVALID_INDEX = "INVALID_INDEX"
INVALID_QUERY = "INVALID_QUERY"
EMPTY_QUERY = "EMPTY_QUERY"
EMPTY_INDEX = "EMPTY_INDEX"
INVALID_TIMESTAMP_RANGE = "INVALID_TIMESTAMP_RANGE"
INVALID_SORT_FIELD = "INVALID_SORT_FIELD"
UNSAFE_INDEX_STATE = "UNSAFE_INDEX_STATE"
UNSAFE_QUERY_CONTENT = "UNSAFE_QUERY_CONTENT"
UNSAFE_SAFETY_FLAGS = "UNSAFE_SAFETY_FLAGS"
SEARCH_ERROR = "SEARCH_ERROR"
DEFAULT_BLOCKED = "DEFAULT_BLOCKED"

REASON_CODES: tuple[str, ...] = (
    MISSING_INDEX,
    MISSING_QUERY,
    INVALID_INDEX,
    INVALID_QUERY,
    EMPTY_QUERY,
    EMPTY_INDEX,
    INVALID_TIMESTAMP_RANGE,
    INVALID_SORT_FIELD,
    UNSAFE_INDEX_STATE,
    UNSAFE_QUERY_CONTENT,
    UNSAFE_SAFETY_FLAGS,
    SEARCH_ERROR,
    DEFAULT_BLOCKED,
)

FORBIDDEN_SEARCH_TERMS: tuple[str, ...] = (
    "api_key",
    "secret",
    "exchange_credentials",
    "private_key",
    "password",
    "enter_long",
    "enter_short",
    "exit_long",
    "exit_short",
    "buy now",
    "sell now",
    "execute trade",
    "place order",
    "market order",
    "limit order",
    "stop loss",
    "take profit",
)


class SearchState(Enum):
    """Fail-closed state of a search result."""

    DISABLED = "DISABLED"
    READY = "READY"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"


class SearchSort(Enum):
    """Deterministic search result sort order."""

    SCORE_DESC = "SCORE_DESC"
    REPORT_GENERATED_AT_DESC = "REPORT_GENERATED_AT_DESC"
    REPORT_GENERATED_AT_ASC = "REPORT_GENERATED_AT_ASC"
    REVIEWED_AT_DESC = "REVIEWED_AT_DESC"
    ENTRY_ID_ASC = "ENTRY_ID_ASC"


class SearchMatchMode(Enum):
    """How multiple filter groups are combined."""

    ALL = "ALL"
    ANY = "ANY"


def _ensure_timezone_aware(value: datetime | None, field_name: str) -> None:
    if value is not None and value.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _ensure_tuple_of_str(values: tuple[str, ...], field_name: str) -> None:
    if not isinstance(values, tuple):
        raise ValueError(f"{field_name} must be a tuple[str, ...]")
    for value in values:
        if not isinstance(value, str) or not value:
            raise ValueError(f"{field_name} must contain non-empty strings")


def _ensure_tuple_of_enum(values: tuple[Enum, ...], enum_type: type[Enum], field_name: str) -> None:
    if not isinstance(values, tuple):
        raise ValueError(f"{field_name} must be a tuple")
    for value in values:
        if not isinstance(value, enum_type):
            raise ValueError(f"{field_name} must contain {enum_type.__name__} values")


def _contains_forbidden_search_content(value: Any) -> bool:
    """Return True when search input contains unsafe trading/secret content."""

    if isinstance(value, str):
        lowered = value.lower()
        return any(term in lowered for term in FORBIDDEN_SEARCH_TERMS)
    if isinstance(value, Mapping):
        return any(
            _contains_forbidden_search_content(k) or _contains_forbidden_search_content(v)
            for k, v in value.items()
        )
    if isinstance(value, (tuple, list, set, frozenset)):
        return any(_contains_forbidden_search_content(v) for v in value)
    return False


@dataclass(frozen=True)
class SearchFilter:
    """Filter constraints applied to ReviewIndex entries.

    Local report/review references are matched as plain strings only. This model
    never opens, traverses, follows, validates, or executes file references.
    """

    index_states: tuple[IndexState, ...] = ()
    entry_kinds: tuple[IndexEntryKind, ...] = ()
    reason_codes: tuple[str, ...] = ()
    reviewers: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    report_ids: tuple[str, ...] = ()
    audit_ids: tuple[str, ...] = ()
    local_reference_contains: tuple[str, ...] = ()
    metadata_text: tuple[str, ...] = ()
    generated_at_from: datetime | None = None
    generated_at_to: datetime | None = None
    reviewed_at_from: datetime | None = None
    reviewed_at_to: datetime | None = None

    def __post_init__(self) -> None:
        _ensure_tuple_of_enum(self.index_states, IndexState, "index_states")
        _ensure_tuple_of_enum(self.entry_kinds, IndexEntryKind, "entry_kinds")
        for field_name in (
            "reason_codes",
            "reviewers",
            "tags",
            "report_ids",
            "audit_ids",
            "local_reference_contains",
            "metadata_text",
        ):
            _ensure_tuple_of_str(getattr(self, field_name), field_name)

        _ensure_timezone_aware(self.generated_at_from, "generated_at_from")
        _ensure_timezone_aware(self.generated_at_to, "generated_at_to")
        _ensure_timezone_aware(self.reviewed_at_from, "reviewed_at_from")
        _ensure_timezone_aware(self.reviewed_at_to, "reviewed_at_to")

        if (
            self.generated_at_from is not None
            and self.generated_at_to is not None
            and self.generated_at_from > self.generated_at_to
        ):
            raise ValueError("generated_at_from must be <= generated_at_to")
        if (
            self.reviewed_at_from is not None
            and self.reviewed_at_to is not None
            and self.reviewed_at_from > self.reviewed_at_to
        ):
            raise ValueError("reviewed_at_from must be <= reviewed_at_to")

        if _contains_forbidden_search_content((
            self.reason_codes,
            self.reviewers,
            self.tags,
            self.report_ids,
            self.audit_ids,
            self.local_reference_contains,
            self.metadata_text,
        )):
            raise ValueError("search filter contains unsafe content")

    @property
    def is_empty(self) -> bool:
        return (
            not self.index_states
            and not self.entry_kinds
            and not self.reason_codes
            and not self.reviewers
            and not self.tags
            and not self.report_ids
            and not self.audit_ids
            and not self.local_reference_contains
            and not self.metadata_text
            and self.generated_at_from is None
            and self.generated_at_to is None
            and self.reviewed_at_from is None
            and self.reviewed_at_to is None
        )


@dataclass(frozen=True)
class SearchQuery:
    """Immutable local query over an in-memory ReviewIndex object."""

    query_text: str = ""
    filters: SearchFilter = field(default_factory=SearchFilter)
    match_mode: SearchMatchMode = SearchMatchMode.ALL
    sort: SearchSort = SearchSort.SCORE_DESC
    limit: int | None = None
    include_blocked_entries: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.query_text, str):
            raise ValueError("query_text must be a string")
        if not isinstance(self.filters, SearchFilter):
            raise ValueError("filters must be SearchFilter")
        if not isinstance(self.match_mode, SearchMatchMode):
            raise ValueError("match_mode must be SearchMatchMode")
        if not isinstance(self.sort, SearchSort):
            raise ValueError("sort must be SearchSort")
        if self.limit is not None and self.limit <= 0:
            raise ValueError("limit must be > 0 when provided")
        if _contains_forbidden_search_content(self.query_text):
            raise ValueError("query_text contains unsafe content")

    @property
    def is_empty(self) -> bool:
        return not self.query_text.strip() and self.filters.is_empty


@dataclass(frozen=True)
class SearchConfig:
    """Safe local search configuration."""

    max_results: int = 1000
    allow_empty_query: bool = False
    strict_timestamp_validation: bool = True
    case_sensitive_text_search: bool = False

    def __post_init__(self) -> None:
        if self.max_results <= 0:
            raise ValueError("max_results must be > 0")


@dataclass(frozen=True)
class SearchSafetyFlags:
    """Safety flags that must remain fail-closed for search artifacts."""

    dry_run: bool = True
    live_trading_enabled: bool = False
    real_orders_enabled: bool = False
    leverage_enabled: bool = False
    shorting_enabled: bool = False
    report_feedback_into_execution: bool = False
    operator_feedback_into_execution: bool = False
    index_feedback_into_execution: bool = False
    search_feedback_into_execution: bool = False
    file_reference_traversal_enabled: bool = False
    database_persistence_enabled: bool = False
    web_ui_enabled: bool = False
    dashboard_enabled: bool = False

    def __post_init__(self) -> None:
        unsafe_flags = (
            self.live_trading_enabled,
            self.real_orders_enabled,
            self.leverage_enabled,
            self.shorting_enabled,
            self.report_feedback_into_execution,
            self.operator_feedback_into_execution,
            self.index_feedback_into_execution,
            self.search_feedback_into_execution,
            self.file_reference_traversal_enabled,
            self.database_persistence_enabled,
            self.web_ui_enabled,
            self.dashboard_enabled,
        )
        if any(unsafe_flags):
            raise ValueError("unsafe search safety flags are enabled")


@dataclass(frozen=True)
class SearchResultEntry:
    """Search hit for a ReviewIndex entry."""

    entry_id: str
    score: float
    index_state: IndexState
    entry_kind: IndexEntryKind
    report_id: str
    audit_id: str = ""
    review_status: str = "NOT_REVIEWED"
    reason_codes: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    reviewer: str = ""
    local_report_reference: str = ""
    local_review_reference: str = ""
    report_generated_at: datetime | None = None
    audit_generated_at: datetime | None = None
    reviewed_at: datetime | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.entry_id:
            raise ValueError("entry_id must be non-empty")
        if self.score < 0:
            raise ValueError("score must be >= 0")
        if not isinstance(self.index_state, IndexState):
            raise ValueError("index_state must be IndexState")
        if not isinstance(self.entry_kind, IndexEntryKind):
            raise ValueError("entry_kind must be IndexEntryKind")
        if not self.report_id:
            raise ValueError("report_id must be non-empty")
        _ensure_tuple_of_str(self.reason_codes, "reason_codes")
        _ensure_tuple_of_str(self.tags, "tags")
        _ensure_timezone_aware(self.report_generated_at, "report_generated_at")
        _ensure_timezone_aware(self.audit_generated_at, "audit_generated_at")
        _ensure_timezone_aware(self.reviewed_at, "reviewed_at")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True)
class SearchResultSummary:
    """Aggregate counts for a SearchResult."""

    total_entries: int = 0
    matched_entries: int = 0
    returned_entries: int = 0
    ready_count: int = 0
    blocked_count: int = 0
    unknown_count: int = 0
    reason_counts: Mapping[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "total_entries",
            "matched_entries",
            "returned_entries",
            "ready_count",
            "blocked_count",
            "unknown_count",
        ):
            if getattr(self, field_name) < 0:
                raise ValueError(f"{field_name} must be >= 0")
        if self.matched_entries > self.total_entries:
            raise ValueError("matched_entries must be <= total_entries")
        if self.returned_entries > self.matched_entries:
            raise ValueError("returned_entries must be <= matched_entries")
        state_count = self.ready_count + self.blocked_count + self.unknown_count
        if state_count > self.returned_entries:
            raise ValueError("state counts must be <= returned_entries")
        for code, count in self.reason_counts.items():
            if not isinstance(code, str) or not code:
                raise ValueError("reason_counts keys must be non-empty strings")
            if count < 0:
                raise ValueError("reason_counts values must be >= 0")
        object.__setattr__(self, "reason_counts", MappingProxyType(dict(self.reason_counts)))


@dataclass(frozen=True)
class SearchResult:
    """Fail-closed local search result.

    This object is a human-audit artifact only. It is not a trading signal, not
    trade approval, and must never be consumed by execution, strategy,
    Freqtrade shell, order, exchange, or any MVP execution path.
    """

    search_id: str
    generated_at: datetime
    search_state: SearchState
    query: SearchQuery
    entries: tuple[SearchResultEntry, ...]
    summary: SearchResultSummary
    reason_codes: tuple[str, ...] = ()
    safety_flags: SearchSafetyFlags = field(default_factory=SearchSafetyFlags)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.search_id:
            raise ValueError("search_id must be non-empty")
        _ensure_timezone_aware(self.generated_at, "generated_at")
        if not isinstance(self.search_state, SearchState):
            raise ValueError("search_state must be SearchState")
        if not isinstance(self.query, SearchQuery):
            raise ValueError("query must be SearchQuery")
        if not isinstance(self.entries, tuple):
            raise ValueError("entries must be a tuple")
        for entry in self.entries:
            if not isinstance(entry, SearchResultEntry):
                raise ValueError("entries must contain SearchResultEntry values")
        if not isinstance(self.summary, SearchResultSummary):
            raise ValueError("summary must be SearchResultSummary")
        _ensure_tuple_of_str(self.reason_codes, "reason_codes")
        for code in self.reason_codes:
            if code not in REASON_CODES:
                raise ValueError(f"unsupported reason code: {code}")
        if not isinstance(self.safety_flags, SearchSafetyFlags):
            raise ValueError("safety_flags must be SearchSafetyFlags")
        if self.search_state is not SearchState.READY and not self.reason_codes:
            raise ValueError("reason_codes must be non-empty when search_state is not READY")
        if self.search_state is SearchState.READY and self.reason_codes:
            raise ValueError("READY search results must not have reason_codes")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @classmethod
    def blocked(
        cls,
        *,
        search_id: str,
        generated_at: datetime,
        reason_code: str = DEFAULT_BLOCKED,
        query: SearchQuery | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> "SearchResult":
        """Create a deterministic fail-closed blocked search result."""

        if reason_code not in REASON_CODES:
            raise ValueError(f"unsupported reason code: {reason_code}")
        return cls(
            search_id=search_id,
            generated_at=generated_at,
            search_state=SearchState.BLOCKED,
            query=query or SearchQuery(),
            entries=(),
            summary=SearchResultSummary(),
            reason_codes=(reason_code,),
            safety_flags=SearchSafetyFlags(),
            metadata=metadata or {},
        )
