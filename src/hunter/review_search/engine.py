"""Search engine for hunter.review_search package.

In-memory functions for validating queries, matching index entries, scoring,
sorting, and building search results. No file I/O, no network, no database.

Search results are human-audit artifacts only. They are not trading signals,
not trade approvals, and must not be consumed by execution, strategy,
Freqtrade shell, order, exchange, or any MVP execution path.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from hunter.review_index.models import IndexEntry, IndexEntryKind, IndexState, ReviewIndex

from .models import (
    DEFAULT_BLOCKED,
    EMPTY_INDEX,
    EMPTY_QUERY,
    INVALID_QUERY,
    INVALID_SORT_FIELD,
    INVALID_TIMESTAMP_RANGE,
    MISSING_INDEX,
    SEARCH_ERROR,
    UNSAFE_QUERY_CONTENT,
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
    _contains_forbidden_search_content,
)


# ---------------------------------------------------------------------------
# Safety flags builder
# ---------------------------------------------------------------------------

def build_search_safety_flags(config: SearchConfig | None = None) -> SearchSafetyFlags:
    """Convert config into search safety flags.

    Always returns safe defaults; config only customizes within safe bounds.
    """
    if config is None:
        return SearchSafetyFlags()
    # SearchConfig only contains safe values by validation; return defaults.
    return SearchSafetyFlags()


# ---------------------------------------------------------------------------
# Query validation
# ---------------------------------------------------------------------------

def validate_search_query(
    query: SearchQuery,
    safety_flags: SearchSafetyFlags | None = None,
) -> tuple[bool, str]:
    """Validate query and return (is_valid, reason_code).

    Checks:
    - At least one filter field is non-None (or query_text is non-empty).
    - Timestamp ranges are valid (after <= before).
    - No forbidden terms in string fields.
    - All string fields are safe (no execution instructions, no API keys).
    """
    if not isinstance(query, SearchQuery):
        return False, INVALID_QUERY

    # Empty query check
    if query.is_empty:
        return False, EMPTY_QUERY

    # Forbidden content check on query_text
    if _contains_forbidden_search_content(query.query_text):
        return False, UNSAFE_QUERY_CONTENT

    # Timestamp range validation via filter
    filters = query.filters
    if (
        filters.generated_at_from is not None
        and filters.generated_at_to is not None
        and filters.generated_at_from > filters.generated_at_to
    ):
        return False, INVALID_TIMESTAMP_RANGE
    if (
        filters.reviewed_at_from is not None
        and filters.reviewed_at_to is not None
        and filters.reviewed_at_from > filters.reviewed_at_to
    ):
        return False, INVALID_TIMESTAMP_RANGE

    # Safety flags validation
    if safety_flags is not None:
        try:
            if not isinstance(safety_flags, SearchSafetyFlags):
                return False, INVALID_QUERY
            # Re-instantiate to trigger __post_init__ validation
            SearchSafetyFlags(**{
                f.name: getattr(safety_flags, f.name)
                for f in safety_flags.__dataclass_fields__.values()
            })
        except ValueError:
            return False, INVALID_QUERY

    return True, ""


# ---------------------------------------------------------------------------
# Entry matching
# ---------------------------------------------------------------------------

def _match_filter(entry: IndexEntry, filters: SearchFilter) -> tuple[bool, tuple[str, ...]]:
    """Check if an index entry matches the filter constraints.

    Returns (matched, matched_fields).
    All non-empty filter fields are ANDed together.
    """
    matched_fields: list[str] = []

    if filters.index_states and entry.index_state not in filters.index_states:
        return False, ()
    if filters.index_states:
        matched_fields.append("index_state")

    if filters.entry_kinds and entry.entry_kind not in filters.entry_kinds:
        return False, ()
    if filters.entry_kinds:
        matched_fields.append("entry_kind")

    if filters.reason_codes:
        if not any(rc in entry.reason_codes for rc in filters.reason_codes):
            return False, ()
        matched_fields.append("reason_codes")

    if filters.reviewers:
        if entry.reviewer not in filters.reviewers:
            return False, ()
        matched_fields.append("reviewer")

    if filters.tags:
        if not any(tag in entry.tags for tag in filters.tags):
            return False, ()
        matched_fields.append("tags")

    if filters.report_ids:
        if entry.report_id not in filters.report_ids:
            return False, ()
        matched_fields.append("report_id")

    if filters.audit_ids:
        if entry.audit_id not in filters.audit_ids:
            return False, ()
        matched_fields.append("audit_id")

    if filters.local_reference_contains:
        found = False
        for ref in filters.local_reference_contains:
            lower_ref = ref.lower()
            if (
                lower_ref in entry.local_report_reference.lower()
                or lower_ref in entry.local_review_reference.lower()
            ):
                found = True
                break
        if not found:
            return False, ()
        matched_fields.append("local_reference_contains")

    if filters.metadata_text:
        found = False
        for term in filters.metadata_text:
            lower_term = term.lower()
            for key, value in entry.metadata.items():
                if lower_term in key.lower() or lower_term in str(value).lower():
                    found = True
                    break
            if found:
                break
        if not found:
            return False, ()
        matched_fields.append("metadata_text")

    if filters.generated_at_from is not None:
        if entry.report_generated_at is None or entry.report_generated_at < filters.generated_at_from:
            return False, ()
        matched_fields.append("generated_at_from")

    if filters.generated_at_to is not None:
        if entry.report_generated_at is None or entry.report_generated_at > filters.generated_at_to:
            return False, ()
        matched_fields.append("generated_at_to")

    if filters.reviewed_at_from is not None:
        if entry.reviewed_at is None or entry.reviewed_at < filters.reviewed_at_from:
            return False, ()
        matched_fields.append("reviewed_at_from")

    if filters.reviewed_at_to is not None:
        if entry.reviewed_at is None or entry.reviewed_at > filters.reviewed_at_to:
            return False, ()
        matched_fields.append("reviewed_at_to")

    return True, tuple(matched_fields)


def _match_query_text(entry: IndexEntry, query_text: str) -> tuple[bool, tuple[str, ...]]:
    """Check if query_text matches any field in the entry (substring, case-insensitive)."""
    if not query_text.strip():
        return True, ()

    lower_text = query_text.lower()
    matched_fields: list[str] = []

    # Check various string fields
    if lower_text in entry.entry_id.lower():
        matched_fields.append("entry_id")
    if lower_text in entry.report_id.lower():
        matched_fields.append("report_id")
    if entry.audit_id and lower_text in entry.audit_id.lower():
        matched_fields.append("audit_id")
    if entry.reviewer and lower_text in entry.reviewer.lower():
        matched_fields.append("reviewer")
    if entry.local_report_reference and lower_text in entry.local_report_reference.lower():
        matched_fields.append("local_report_reference")
    if entry.local_review_reference and lower_text in entry.local_review_reference.lower():
        matched_fields.append("local_review_reference")
    if entry.review_status and lower_text in entry.review_status.lower():
        matched_fields.append("review_status")
    if entry.review_state and lower_text in entry.review_state.lower():
        matched_fields.append("review_state")

    # Check tags
    for tag in entry.tags:
        if lower_text in tag.lower():
            matched_fields.append("tags")
            break

    # Check reason_codes
    for rc in entry.reason_codes:
        if lower_text in rc.lower():
            matched_fields.append("reason_codes")
            break

    # Check metadata
    for key, value in entry.metadata.items():
        if lower_text in key.lower() or lower_text in str(value).lower():
            matched_fields.append("metadata")
            break

    if matched_fields:
        return True, tuple(matched_fields)
    return False, ()


def entry_matches_query(
    entry: IndexEntry,
    query: SearchQuery,
) -> tuple[bool, float, tuple[str, ...]]:
    """Check if an index entry matches the query.

    Returns (matched, score, matched_fields).
    Score is a simple relevance metric (0.0-1.0) based on field match count.
    """
    if not isinstance(entry, IndexEntry):
        return False, 0.0, ()
    if not isinstance(query, SearchQuery):
        return False, 0.0, ()

    # Filter matching
    filter_matched, filter_fields = _match_filter(entry, query.filters)

    # Query text matching
    text_matched, text_fields = _match_query_text(entry, query.query_text)

    if query.match_mode is SearchMatchMode.ALL:
        if not filter_matched:
            return False, 0.0, ()
        # For ALL mode: query_text is optional; if present, must also match
        if query.query_text.strip() and not text_matched:
            return False, 0.0, ()
    else:  # ANY mode
        if not filter_matched and not text_matched:
            return False, 0.0, ()
        # If query_text is empty, filter must match
        if not query.query_text.strip() and not filter_matched:
            return False, 0.0, ()

    all_fields = filter_fields + text_fields
    score = score_search_entry(entry, query, all_fields)
    return True, score, tuple(all_fields)


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def score_search_entry(
    entry: IndexEntry,
    query: SearchQuery,
    matched_fields: tuple[str, ...],
) -> float:
    """Compute a simple relevance score for a matched entry.

    Score = matched_field_count / total_active_query_field_count.
    Higher score = more specific match.
    """
    if not matched_fields:
        return 0.0

    # Count total active query fields
    total_active = 0
    filters = query.filters

    if filters.index_states:
        total_active += 1
    if filters.entry_kinds:
        total_active += 1
    if filters.reason_codes:
        total_active += 1
    if filters.reviewers:
        total_active += 1
    if filters.tags:
        total_active += 1
    if filters.report_ids:
        total_active += 1
    if filters.audit_ids:
        total_active += 1
    if filters.local_reference_contains:
        total_active += 1
    if filters.metadata_text:
        total_active += 1
    if filters.generated_at_from is not None:
        total_active += 1
    if filters.generated_at_to is not None:
        total_active += 1
    if filters.reviewed_at_from is not None:
        total_active += 1
    if filters.reviewed_at_to is not None:
        total_active += 1
    if query.query_text.strip():
        total_active += 1

    if total_active == 0:
        return 1.0

    # Deduplicate matched fields for counting
    unique_matched = len(set(matched_fields))
    score = unique_matched / total_active
    return min(score, 1.0)


# ---------------------------------------------------------------------------
# Sorting
# ---------------------------------------------------------------------------

def sort_search_results(
    results: tuple[SearchResultEntry, ...],
    sort: SearchSort,
) -> tuple[SearchResultEntry, ...]:
    """Sort search results by the specified sort order."""
    if not results:
        return ()

    def _sort_key(entry: SearchResultEntry) -> Any:
        if sort is SearchSort.SCORE_DESC:
            return (-entry.score, entry.entry_id)
        if sort is SearchSort.REPORT_GENERATED_AT_DESC:
            # None values sort to the end
            ts = entry.report_generated_at
            return (ts is None, -(ts.timestamp() if ts else 0), entry.entry_id)
        if sort is SearchSort.REPORT_GENERATED_AT_ASC:
            ts = entry.report_generated_at
            return (ts is None, ts.timestamp() if ts else 0, entry.entry_id)
        if sort is SearchSort.REVIEWED_AT_DESC:
            ts = entry.reviewed_at
            return (ts is None, -(ts.timestamp() if ts else 0), entry.entry_id)
        if sort is SearchSort.ENTRY_ID_ASC:
            return entry.entry_id
        # Default fallback
        return (-entry.score, entry.entry_id)

    sorted_list = sorted(results, key=_sort_key)
    return tuple(sorted_list)


# ---------------------------------------------------------------------------
# Result builder
# ---------------------------------------------------------------------------

def build_search_result(
    index: ReviewIndex,
    query: SearchQuery,
    sort: SearchSort | None = None,
    config: SearchConfig | None = None,
    now: datetime | None = None,
) -> SearchResult:
    """Build full SearchResult from ReviewIndex and query.

    Fail-closed: invalid/missing/unsafe input returns blocked result.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    # Priority 1: MISSING_INDEX
    if index is None:
        return SearchResult.blocked(
            search_id="blocked",
            generated_at=now,
            reason_code=MISSING_INDEX,
            query=query if isinstance(query, SearchQuery) else None,
        )

    # Priority 2: EMPTY_INDEX
    if not index.entries:
        return SearchResult.blocked(
            search_id="blocked",
            generated_at=now,
            reason_code=EMPTY_INDEX,
            query=query if isinstance(query, SearchQuery) else None,
        )

    # Priority 3: INDEX_STATE_BLOCKED (unsafe index state)
    if index.index_state is IndexState.BLOCKED:
        from .models import UNSAFE_INDEX_STATE
        return SearchResult.blocked(
            search_id="blocked",
            generated_at=now,
            reason_code=UNSAFE_INDEX_STATE,
            query=query if isinstance(query, SearchQuery) else None,
        )

    # Validate query
    if not isinstance(query, SearchQuery):
        return SearchResult.blocked(
            search_id="blocked",
            generated_at=now,
            reason_code=INVALID_QUERY,
        )

    safety_flags = build_search_safety_flags(config)
    is_valid, reason = validate_search_query(query, safety_flags)
    if not is_valid:
        return SearchResult.blocked(
            search_id="blocked",
            generated_at=now,
            reason_code=reason,
            query=query,
        )

    # Determine effective sort
    effective_sort = sort if sort is not None else query.sort

    # Match entries
    matched: list[SearchResultEntry] = []
    for entry in index.entries:
        # Skip blocked entries if not included
        if not query.include_blocked_entries and entry.index_state is IndexState.BLOCKED:
            continue

        is_match, score, matched_fields = entry_matches_query(entry, query)
        if is_match:
            result_entry = SearchResultEntry(
                entry_id=entry.entry_id,
                score=score,
                index_state=entry.index_state,
                entry_kind=entry.entry_kind,
                report_id=entry.report_id,
                audit_id=entry.audit_id,
                review_status=entry.review_status,
                reason_codes=entry.reason_codes,
                tags=entry.tags,
                reviewer=entry.reviewer,
                local_report_reference=entry.local_report_reference,
                local_review_reference=entry.local_review_reference,
                report_generated_at=entry.report_generated_at,
                audit_generated_at=entry.audit_generated_at,
                reviewed_at=entry.reviewed_at,
                metadata=dict(entry.metadata) if entry.metadata else {},
            )
            matched.append(result_entry)

    # Sort results
    if effective_sort is not None and isinstance(effective_sort, SearchSort):
        sorted_results = sort_search_results(tuple(matched), effective_sort)
    else:
        sorted_results = tuple(matched)

    # Apply limit
    limit = query.limit
    if config is not None and config.max_results > 0:
        # config.max_results is an upper bound
        limit = limit if limit is not None else config.max_results
        if limit > config.max_results:
            limit = config.max_results
    if limit is not None:
        sorted_results = sorted_results[:limit]

    # Build summary counts
    total_scanned = len(index.entries)
    ready_count = sum(1 for e in sorted_results if e.index_state is IndexState.READY)
    blocked_count = sum(1 for e in sorted_results if e.index_state is IndexState.BLOCKED)
    unknown_count = sum(1 for e in sorted_results if e.index_state is IndexState.UNKNOWN)

    observation_report_count = sum(
        1 for e in sorted_results if e.entry_kind is IndexEntryKind.OBSERVATION_REPORT
    )
    review_audit_count = sum(
        1 for e in sorted_results if e.entry_kind is IndexEntryKind.REVIEW_AUDIT_RECORD
    )
    linked_entry_count = sum(
        1 for e in sorted_results if e.entry_kind is IndexEntryKind.LINKED_REPORT_REVIEW
    )

    summary = SearchResultSummary(
        total_entries=total_scanned,
        matched_entries=len(matched),
        returned_entries=len(sorted_results),
        ready_count=ready_count,
        blocked_count=blocked_count,
        unknown_count=unknown_count,
        reason_counts={},
    )

    query_desc = _build_query_description(query)
    sort_desc = effective_sort.value if effective_sort is not None else "default"

    # Build metadata with query/sort descriptions for audit
    metadata: dict[str, Any] = {
        "query_applied": query_desc,
        "sort_applied": sort_desc,
        "observation_report_count": observation_report_count,
        "review_audit_count": review_audit_count,
        "linked_entry_count": linked_entry_count,
    }

    return SearchResult(
        search_id=f"search-{index.index_id}-{now.isoformat()}",
        generated_at=now,
        search_state=SearchState.READY,
        query=query,
        entries=sorted_results,
        summary=summary,
        reason_codes=(),
        safety_flags=safety_flags,
        metadata=metadata,
    )


def _build_query_description(query: SearchQuery) -> str:
    """Build a human-readable description of the applied query."""
    parts: list[str] = []
    if query.query_text.strip():
        parts.append(f'text:"{query.query_text}"')
    filters = query.filters
    if filters.index_states:
        parts.append(f"index_state:{[s.value for s in filters.index_states]}")
    if filters.entry_kinds:
        parts.append(f"entry_kind:{[k.value for k in filters.entry_kinds]}")
    if filters.reason_codes:
        parts.append(f"reason_codes:{list(filters.reason_codes)}")
    if filters.reviewers:
        parts.append(f"reviewers:{list(filters.reviewers)}")
    if filters.tags:
        parts.append(f"tags:{list(filters.tags)}")
    if filters.report_ids:
        parts.append(f"report_ids:{list(filters.report_ids)}")
    if filters.audit_ids:
        parts.append(f"audit_ids:{list(filters.audit_ids)}")
    if filters.local_reference_contains:
        parts.append(f"local_reference:{list(filters.local_reference_contains)}")
    if filters.metadata_text:
        parts.append(f"metadata:{list(filters.metadata_text)}")
    if filters.generated_at_from is not None:
        parts.append(f"generated_at_from:{filters.generated_at_from.isoformat()}")
    if filters.generated_at_to is not None:
        parts.append(f"generated_at_to:{filters.generated_at_to.isoformat()}")
    if filters.reviewed_at_from is not None:
        parts.append(f"reviewed_at_from:{filters.reviewed_at_from.isoformat()}")
    if filters.reviewed_at_to is not None:
        parts.append(f"reviewed_at_to:{filters.reviewed_at_to.isoformat()}")
    if not parts:
        return "empty"
    return "; ".join(parts)
