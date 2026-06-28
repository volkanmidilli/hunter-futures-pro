"""Local audit-only review search/query package.

MVP-13 search artifacts are human-audit artifacts only.
They are not trading signals, not trade approvals, and must not be consumed by
execution, strategy, Freqtrade shell, order, exchange, or any MVP execution path.
"""

from .models import (
    DEFAULT_BLOCKED,
    EMPTY_INDEX,
    EMPTY_QUERY,
    FORBIDDEN_SEARCH_TERMS,
    INVALID_INDEX,
    INVALID_QUERY,
    INVALID_TIMESTAMP_RANGE,
    MISSING_INDEX,
    MISSING_QUERY,
    REASON_CODES,
    SEARCH_ERROR,
    UNSAFE_INDEX_STATE,
    UNSAFE_QUERY_CONTENT,
    UNSAFE_SAFETY_FLAGS,
    SearchConfig,
    SearchFilter,
    SearchMatchMode,
    SearchQuery,
    SearchResult,
    SearchResultEntry,
    SearchResultSummary,
    SearchSafetyFlags,
    SearchSort,
    SearchState,
)
from .engine import (
    build_search_result,
    build_search_safety_flags,
    entry_matches_query,
    score_search_entry,
    sort_search_results,
    validate_search_query,
)
from .writer import (
    DEFAULT_SEARCH_JSON_PATH,
    DEFAULT_SEARCH_MARKDOWN_PATH,
    atomic_write_json_search_result,
    atomic_write_markdown_search_result,
    search_result_to_dict,
    search_result_to_markdown,
    write_search_result,
)

__all__ = (
    "DEFAULT_BLOCKED",
    "EMPTY_INDEX",
    "EMPTY_QUERY",
    "FORBIDDEN_SEARCH_TERMS",
    "INVALID_INDEX",
    "INVALID_QUERY",
    "INVALID_TIMESTAMP_RANGE",
    "MISSING_INDEX",
    "MISSING_QUERY",
    "REASON_CODES",
    "SEARCH_ERROR",
    "UNSAFE_INDEX_STATE",
    "UNSAFE_QUERY_CONTENT",
    "UNSAFE_SAFETY_FLAGS",
    "SearchConfig",
    "SearchFilter",
    "SearchMatchMode",
    "SearchQuery",
    "SearchResult",
    "SearchResultEntry",
    "SearchResultSummary",
    "SearchSafetyFlags",
    "SearchSort",
    "SearchState",
    # Engine functions
    "build_search_safety_flags",
    "validate_search_query",
    "entry_matches_query",
    "score_search_entry",
    "sort_search_results",
    "build_search_result",
    # Writer constants
    "DEFAULT_SEARCH_JSON_PATH",
    "DEFAULT_SEARCH_MARKDOWN_PATH",
    # Writer functions
    "search_result_to_dict",
    "search_result_to_markdown",
    "atomic_write_json_search_result",
    "atomic_write_markdown_search_result",
    "write_search_result",
)
