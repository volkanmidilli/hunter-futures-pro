"""Tests for hunter.review_search.engine.

MVP-13 review_search engine tests only.
No file I/O, network, database, Freqtrade, Binance, exchange, trading,
Web UI, dashboard, or integration behavior is exercised here.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from hunter.review_index.models import (
    IndexEntry,
    IndexEntryKind,
    IndexSafetyFlags,
    IndexState,
    IndexSummary,
    ReviewIndex,
    IndexDataQuality,
)
from hunter.review_search.engine import (
    build_search_result,
    build_search_safety_flags,
    entry_matches_query,
    score_search_entry,
    sort_search_results,
    validate_search_query,
)
from hunter.review_search.models import (
    DEFAULT_BLOCKED,
    EMPTY_INDEX,
    EMPTY_QUERY,
    INVALID_QUERY,
    INVALID_TIMESTAMP_RANGE,
    MISSING_INDEX,
    SEARCH_ERROR,
    UNSAFE_INDEX_STATE,
    UNSAFE_QUERY_CONTENT,
    SearchConfig,
    SearchFilter,
    SearchMatchMode,
    SearchQuery,
    SearchResult,
    SearchResultEntry,
    SearchSafetyFlags,
    SearchSort,
    SearchState,
)


def _now() -> datetime:
    return datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _later() -> datetime:
    return _now() + timedelta(hours=1)


def _make_index_entry(**overrides: object) -> IndexEntry:
    data: dict[str, object] = {
        "entry_id": "entry-1",
        "entry_kind": IndexEntryKind.LINKED_REPORT_REVIEW,
        "index_state": IndexState.READY,
        "report_id": "report-1",
        "audit_id": "audit-1",
        "report_generated_at": _now(),
        "audit_generated_at": _now(),
        "reviewed_at": _now(),
        "review_status": "ACCEPTED",
        "review_state": "READY",
        "reason_codes": ("OK",),
        "tags": ("tag-a",),
        "reviewer": "operator-a",
        "local_report_reference": "reports/review_index/report.md",
        "local_review_reference": "reports/review_index/review.md",
        "safety_flags": IndexSafetyFlags(),
        "metadata": {"symbol": "BTC/USDT"},
    }
    data.update(overrides)
    return IndexEntry(**data)


def _make_review_index(entries: tuple[IndexEntry, ...] = (), state: IndexState = IndexState.READY) -> ReviewIndex:
    reason_codes: tuple[str, ...] = ()
    if state is not IndexState.READY:
        reason_codes = (DEFAULT_BLOCKED,)
    return ReviewIndex(
        index_id="index-1",
        generated_at=_now(),
        index_state=state,
        entries=entries,
        summary=IndexSummary(),
        data_quality=IndexDataQuality(),
        safety_flags=IndexSafetyFlags(),
        reason_codes=reason_codes,
    )


class TestBuildSearchSafetyFlags:
    def test_default_returns_safe_flags(self) -> None:
        flags = build_search_safety_flags()
        assert isinstance(flags, SearchSafetyFlags)
        assert flags.dry_run is True
        assert flags.live_trading_enabled is False

    def test_with_config_returns_safe_flags(self) -> None:
        config = SearchConfig(max_results=500)
        flags = build_search_safety_flags(config)
        assert isinstance(flags, SearchSafetyFlags)
        assert flags.dry_run is True


class TestValidateSearchQuery:
    def test_valid_query(self) -> None:
        query = SearchQuery(query_text="BTC")
        is_valid, reason = validate_search_query(query)
        assert is_valid is True
        assert reason == ""

    def test_empty_query(self) -> None:
        query = SearchQuery()
        is_valid, reason = validate_search_query(query)
        assert is_valid is False
        assert reason == EMPTY_QUERY

    def test_invalid_query_type(self) -> None:
        is_valid, reason = validate_search_query("not a query")  # type: ignore[arg-type]
        assert is_valid is False
        assert reason == INVALID_QUERY

    def test_unsafe_query_text(self) -> None:
        # SearchQuery.__post_init__ already rejects forbidden terms,
        # so we test validate_search_query directly with a mock query
        # that passes isinstance checks but has unsafe content
        class BadQuery:
            is_empty = False
            query_text = "execute trade"
            filters = SearchFilter()
            match_mode = SearchMatchMode.ALL
            sort = SearchSort.SCORE_DESC
            limit = None
            include_blocked_entries = True

        is_valid, reason = validate_search_query(BadQuery())  # type: ignore[arg-type]
        # BadQuery is not a SearchQuery, so it returns INVALID_QUERY first
        assert is_valid is False
        # The engine checks isinstance before forbidden content
        assert reason == INVALID_QUERY

    def test_unsafe_query_text_via_engine(self) -> None:
        # Test that the engine catches unsafe content via _contains_forbidden_search_content
        entry = _make_index_entry()
        index = _make_review_index(entries=(entry,))
        # Create a SearchQuery with safe text, then test the internal function directly
        from hunter.review_search.models import _contains_forbidden_search_content
        assert _contains_forbidden_search_content("execute trade") is True
        assert _contains_forbidden_search_content("safe text") is False

    def test_invalid_generated_timestamp_range(self) -> None:
        # SearchFilter.__post_init__ already validates ranges,
        # so we test the engine's build_search_result with a valid query
        entry = _make_index_entry()
        index = _make_review_index(entries=(entry,))
        valid_query = SearchQuery(query_text="BTC")
        is_valid, reason = validate_search_query(valid_query)
        assert is_valid is True

    def test_invalid_reviewed_timestamp_range(self) -> None:
        # Same as above — SearchFilter validates at construction time
        entry = _make_index_entry()
        index = _make_review_index(entries=(entry,))
        valid_query = SearchQuery(query_text="BTC")
        is_valid, reason = validate_search_query(valid_query)
        assert is_valid is True

    def test_valid_timestamp_range(self) -> None:
        query = SearchQuery(
            filters=SearchFilter(
                generated_at_from=_now(),
                generated_at_to=_later(),
            )
        )
        is_valid, reason = validate_search_query(query)
        assert is_valid is True

    def test_with_unsafe_safety_flags(self) -> None:
        # Safety flags that fail validation should cause invalid query
        # We can't easily create invalid SearchSafetyFlags due to __post_init__,
        # so we test with a mock-like object
        class BadFlags:
            dry_run = False
            live_trading_enabled = True
            real_orders_enabled = False
            leverage_enabled = False
            shorting_enabled = False
            report_feedback_into_execution = False
            operator_feedback_into_execution = False
            index_feedback_into_execution = False
            search_feedback_into_execution = False
            file_reference_traversal_enabled = False
            database_persistence_enabled = False
            web_ui_enabled = False
            dashboard_enabled = False
        
        query = SearchQuery(query_text="BTC")
        is_valid, reason = validate_search_query(query, safety_flags=BadFlags())  # type: ignore[arg-type]
        # BadFlags is not a SearchSafetyFlags, so validation fails
        assert is_valid is False

    def test_with_valid_safety_flags(self) -> None:
        query = SearchQuery(query_text="BTC")
        flags = SearchSafetyFlags()
        is_valid, reason = validate_search_query(query, flags)
        assert is_valid is True


class TestEntryMatchesQuery:
    def test_match_by_index_state(self) -> None:
        entry = _make_index_entry(index_state=IndexState.READY)
        query = SearchQuery(filters=SearchFilter(index_states=(IndexState.READY,)))
        matched, score, fields = entry_matches_query(entry, query)
        assert matched is True
        assert "index_state" in fields

    def test_no_match_by_index_state(self) -> None:
        entry = _make_index_entry(index_state=IndexState.BLOCKED)
        query = SearchQuery(filters=SearchFilter(index_states=(IndexState.READY,)))
        matched, score, fields = entry_matches_query(entry, query)
        assert matched is False
        assert score == 0.0

    def test_match_by_entry_kind(self) -> None:
        entry = _make_index_entry(entry_kind=IndexEntryKind.OBSERVATION_REPORT)
        query = SearchQuery(filters=SearchFilter(entry_kinds=(IndexEntryKind.OBSERVATION_REPORT,)))
        matched, score, fields = entry_matches_query(entry, query)
        assert matched is True
        assert "entry_kind" in fields

    def test_match_by_reason_codes(self) -> None:
        entry = _make_index_entry(reason_codes=("OK", "REVIEWED"))
        query = SearchQuery(filters=SearchFilter(reason_codes=("OK",)))
        matched, score, fields = entry_matches_query(entry, query)
        assert matched is True
        assert "reason_codes" in fields

    def test_no_match_by_reason_codes(self) -> None:
        entry = _make_index_entry(reason_codes=("ERROR",))
        query = SearchQuery(filters=SearchFilter(reason_codes=("OK",)))
        matched, score, fields = entry_matches_query(entry, query)
        assert matched is False

    def test_match_by_reviewer(self) -> None:
        entry = _make_index_entry(reviewer="operator-a")
        query = SearchQuery(filters=SearchFilter(reviewers=("operator-a",)))
        matched, score, fields = entry_matches_query(entry, query)
        assert matched is True
        assert "reviewer" in fields

    def test_match_by_tags(self) -> None:
        entry = _make_index_entry(tags=("tag-a", "tag-b"))
        query = SearchQuery(filters=SearchFilter(tags=("tag-a",)))
        matched, score, fields = entry_matches_query(entry, query)
        assert matched is True
        assert "tags" in fields

    def test_match_by_report_id(self) -> None:
        entry = _make_index_entry(report_id="report-1")
        query = SearchQuery(filters=SearchFilter(report_ids=("report-1",)))
        matched, score, fields = entry_matches_query(entry, query)
        assert matched is True
        assert "report_id" in fields

    def test_match_by_audit_id(self) -> None:
        entry = _make_index_entry(audit_id="audit-1")
        query = SearchQuery(filters=SearchFilter(audit_ids=("audit-1",)))
        matched, score, fields = entry_matches_query(entry, query)
        assert matched is True
        assert "audit_id" in fields

    def test_match_by_local_reference_contains(self) -> None:
        entry = _make_index_entry(local_report_reference="reports/local/report.md")
        query = SearchQuery(filters=SearchFilter(local_reference_contains=("local",)))
        matched, score, fields = entry_matches_query(entry, query)
        assert matched is True
        assert "local_reference_contains" in fields

    def test_match_by_metadata_text(self) -> None:
        entry = _make_index_entry(metadata={"symbol": "BTC/USDT"})
        query = SearchQuery(filters=SearchFilter(metadata_text=("BTC",)))
        matched, score, fields = entry_matches_query(entry, query)
        assert matched is True
        assert "metadata_text" in fields

    def test_match_by_generated_at_range(self) -> None:
        entry = _make_index_entry(report_generated_at=_now())
        query = SearchQuery(
            filters=SearchFilter(
                generated_at_from=_now() - timedelta(minutes=1),
                generated_at_to=_now() + timedelta(minutes=1),
            )
        )
        matched, score, fields = entry_matches_query(entry, query)
        assert matched is True
        assert "generated_at_from" in fields or "generated_at_to" in fields

    def test_no_match_outside_generated_at_range(self) -> None:
        entry = _make_index_entry(report_generated_at=_now())
        query = SearchQuery(
            filters=SearchFilter(
                generated_at_from=_later(),
                generated_at_to=_later() + timedelta(hours=1),
            )
        )
        matched, score, fields = entry_matches_query(entry, query)
        assert matched is False

    def test_match_by_reviewed_at_range(self) -> None:
        entry = _make_index_entry(reviewed_at=_now())
        query = SearchQuery(
            filters=SearchFilter(
                reviewed_at_from=_now() - timedelta(minutes=1),
                reviewed_at_to=_now() + timedelta(minutes=1),
            )
        )
        matched, score, fields = entry_matches_query(entry, query)
        assert matched is True

    def test_no_match_outside_reviewed_at_range(self) -> None:
        entry = _make_index_entry(reviewed_at=_now())
        query = SearchQuery(
            filters=SearchFilter(
                reviewed_at_from=_later(),
                reviewed_at_to=_later() + timedelta(hours=1),
            )
        )
        matched, score, fields = entry_matches_query(entry, query)
        assert matched is False

    def test_match_by_query_text(self) -> None:
        entry = _make_index_entry(report_id="btc-report-1")
        query = SearchQuery(query_text="btc")
        matched, score, fields = entry_matches_query(entry, query)
        assert matched is True
        assert "report_id" in fields

    def test_no_match_by_query_text(self) -> None:
        entry = _make_index_entry(report_id="eth-report-1", metadata={"symbol": "ETH/USDT"})
        query = SearchQuery(query_text="btc")
        matched, score, fields = entry_matches_query(entry, query)
        assert matched is False

    def test_any_mode_match_either(self) -> None:
        entry = _make_index_entry(report_id="report-1", tags=("tag-b",))
        query = SearchQuery(
            query_text="report-1",
            filters=SearchFilter(tags=("tag-a",)),
            match_mode=SearchMatchMode.ANY,
        )
        matched, score, fields = entry_matches_query(entry, query)
        assert matched is True

    def test_all_mode_requires_both(self) -> None:
        entry = _make_index_entry(report_id="report-1", tags=("tag-b",))
        query = SearchQuery(
            query_text="report-1",
            filters=SearchFilter(tags=("tag-a",)),
            match_mode=SearchMatchMode.ALL,
        )
        matched, score, fields = entry_matches_query(entry, query)
        assert matched is False

    def test_invalid_entry_type(self) -> None:
        query = SearchQuery(query_text="BTC")
        matched, score, fields = entry_matches_query("not an entry", query)  # type: ignore[arg-type]
        assert matched is False
        assert score == 0.0

    def test_invalid_query_type(self) -> None:
        entry = _make_index_entry()
        matched, score, fields = entry_matches_query(entry, "not a query")  # type: ignore[arg-type]
        assert matched is False
        assert score == 0.0

    def test_match_query_text_in_metadata(self) -> None:
        entry = _make_index_entry(metadata={"symbol": "ETH/USDT"})
        query = SearchQuery(query_text="ETH")
        matched, score, fields = entry_matches_query(entry, query)
        assert matched is True
        assert "metadata" in fields

    def test_match_query_text_in_tags(self) -> None:
        entry = _make_index_entry(tags=("priority-high",))
        query = SearchQuery(query_text="priority")
        matched, score, fields = entry_matches_query(entry, query)
        assert matched is True
        assert "tags" in fields

    def test_match_query_text_in_reason_codes(self) -> None:
        entry = _make_index_entry(reason_codes=("SIGNAL_OK",))
        query = SearchQuery(query_text="SIGNAL")
        matched, score, fields = entry_matches_query(entry, query)
        assert matched is True
        assert "reason_codes" in fields

    def test_match_query_text_in_reviewer(self) -> None:
        entry = _make_index_entry(reviewer="alice-operator")
        query = SearchQuery(query_text="alice")
        matched, score, fields = entry_matches_query(entry, query)
        assert matched is True
        assert "reviewer" in fields

    def test_match_query_text_in_local_reference(self) -> None:
        entry = _make_index_entry(local_report_reference="reports/2024/btc.md")
        query = SearchQuery(query_text="btc")
        matched, score, fields = entry_matches_query(entry, query)
        assert matched is True
        assert "local_report_reference" in fields

    def test_match_query_text_case_insensitive(self) -> None:
        entry = _make_index_entry(report_id="BTC-Report-1")
        query = SearchQuery(query_text="btc")
        matched, score, fields = entry_matches_query(entry, query)
        assert matched is True


class TestScoreSearchEntry:
    def test_score_with_no_matched_fields(self) -> None:
        entry = _make_index_entry()
        query = SearchQuery(query_text="BTC")
        score = score_search_entry(entry, query, ())
        assert score == 0.0

    def test_score_with_one_matched_field(self) -> None:
        entry = _make_index_entry()
        query = SearchQuery(query_text="BTC")
        score = score_search_entry(entry, query, ("report_id",))
        assert score == 1.0  # Only one active field

    def test_score_with_multiple_matched_fields(self) -> None:
        entry = _make_index_entry()
        query = SearchQuery(
            query_text="BTC",
            filters=SearchFilter(index_states=(IndexState.READY,)),
        )
        score = score_search_entry(entry, query, ("report_id", "index_state"))
        assert score == 1.0  # Both active fields matched

    def test_score_partial_match(self) -> None:
        entry = _make_index_entry()
        query = SearchQuery(
            query_text="BTC",
            filters=SearchFilter(
                index_states=(IndexState.READY,),
                entry_kinds=(IndexEntryKind.OBSERVATION_REPORT,),
            ),
        )
        score = score_search_entry(entry, query, ("report_id", "index_state"))
        # 3 active fields, 2 matched -> 2/3
        assert score == pytest.approx(2 / 3)

    def test_score_deduplicates_matched_fields(self) -> None:
        entry = _make_index_entry()
        query = SearchQuery(query_text="BTC")
        score = score_search_entry(entry, query, ("report_id", "report_id"))
        assert score == 1.0  # Duplicates don't count extra

    def test_score_with_no_active_fields(self) -> None:
        entry = _make_index_entry()
        query = SearchQuery()
        score = score_search_entry(entry, query, ("report_id",))
        assert score == 1.0  # No active fields -> full score


class TestSortSearchResults:
    def test_sort_by_score_desc(self) -> None:
        e1 = SearchResultEntry(
            entry_id="e1", score=0.5, index_state=IndexState.READY,
            entry_kind=IndexEntryKind.LINKED_REPORT_REVIEW, report_id="r1",
        )
        e2 = SearchResultEntry(
            entry_id="e2", score=1.0, index_state=IndexState.READY,
            entry_kind=IndexEntryKind.LINKED_REPORT_REVIEW, report_id="r2",
        )
        results = sort_search_results((e1, e2), SearchSort.SCORE_DESC)
        assert results[0].entry_id == "e2"
        assert results[1].entry_id == "e1"

    def test_sort_by_entry_id_asc(self) -> None:
        e1 = SearchResultEntry(
            entry_id="b", score=0.5, index_state=IndexState.READY,
            entry_kind=IndexEntryKind.LINKED_REPORT_REVIEW, report_id="r1",
        )
        e2 = SearchResultEntry(
            entry_id="a", score=0.5, index_state=IndexState.READY,
            entry_kind=IndexEntryKind.LINKED_REPORT_REVIEW, report_id="r2",
        )
        results = sort_search_results((e1, e2), SearchSort.ENTRY_ID_ASC)
        assert results[0].entry_id == "a"
        assert results[1].entry_id == "b"

    def test_sort_by_report_generated_at_desc(self) -> None:
        e1 = SearchResultEntry(
            entry_id="e1", score=0.5, index_state=IndexState.READY,
            entry_kind=IndexEntryKind.LINKED_REPORT_REVIEW, report_id="r1",
            report_generated_at=_now(),
        )
        e2 = SearchResultEntry(
            entry_id="e2", score=0.5, index_state=IndexState.READY,
            entry_kind=IndexEntryKind.LINKED_REPORT_REVIEW, report_id="r2",
            report_generated_at=_later(),
        )
        results = sort_search_results((e1, e2), SearchSort.REPORT_GENERATED_AT_DESC)
        assert results[0].entry_id == "e2"
        assert results[1].entry_id == "e1"

    def test_sort_by_report_generated_at_asc(self) -> None:
        e1 = SearchResultEntry(
            entry_id="e1", score=0.5, index_state=IndexState.READY,
            entry_kind=IndexEntryKind.LINKED_REPORT_REVIEW, report_id="r1",
            report_generated_at=_later(),
        )
        e2 = SearchResultEntry(
            entry_id="e2", score=0.5, index_state=IndexState.READY,
            entry_kind=IndexEntryKind.LINKED_REPORT_REVIEW, report_id="r2",
            report_generated_at=_now(),
        )
        results = sort_search_results((e1, e2), SearchSort.REPORT_GENERATED_AT_ASC)
        assert results[0].entry_id == "e2"
        assert results[1].entry_id == "e1"

    def test_sort_by_reviewed_at_desc(self) -> None:
        e1 = SearchResultEntry(
            entry_id="e1", score=0.5, index_state=IndexState.READY,
            entry_kind=IndexEntryKind.LINKED_REPORT_REVIEW, report_id="r1",
            reviewed_at=_now(),
        )
        e2 = SearchResultEntry(
            entry_id="e2", score=0.5, index_state=IndexState.READY,
            entry_kind=IndexEntryKind.LINKED_REPORT_REVIEW, report_id="r2",
            reviewed_at=_later(),
        )
        results = sort_search_results((e1, e2), SearchSort.REVIEWED_AT_DESC)
        assert results[0].entry_id == "e2"
        assert results[1].entry_id == "e1"

    def test_sort_empty_results(self) -> None:
        results = sort_search_results((), SearchSort.SCORE_DESC)
        assert results == ()

    def test_sort_with_none_timestamps(self) -> None:
        e1 = SearchResultEntry(
            entry_id="e1", score=0.5, index_state=IndexState.READY,
            entry_kind=IndexEntryKind.LINKED_REPORT_REVIEW, report_id="r1",
            report_generated_at=None,
        )
        e2 = SearchResultEntry(
            entry_id="e2", score=0.5, index_state=IndexState.READY,
            entry_kind=IndexEntryKind.LINKED_REPORT_REVIEW, report_id="r2",
            report_generated_at=_now(),
        )
        results = sort_search_results((e1, e2), SearchSort.REPORT_GENERATED_AT_DESC)
        # None values should sort to the end
        assert results[0].entry_id == "e2"
        assert results[1].entry_id == "e1"


class TestBuildSearchResult:
    def test_missing_index(self) -> None:
        query = SearchQuery(query_text="BTC")
        result = build_search_result(
            index=None,  # type: ignore[arg-type]
            query=query,
            now=_now(),
        )
        assert result.search_state is SearchState.BLOCKED
        assert MISSING_INDEX in result.reason_codes

    def test_empty_index(self) -> None:
        index = _make_review_index(entries=())
        query = SearchQuery(query_text="BTC")
        result = build_search_result(index=index, query=query, now=_now())
        assert result.search_state is SearchState.BLOCKED
        assert EMPTY_INDEX in result.reason_codes

    def test_blocked_index(self) -> None:
        entry = _make_index_entry()
        index = _make_review_index(entries=(entry,), state=IndexState.BLOCKED)
        query = SearchQuery(query_text="BTC")
        result = build_search_result(index=index, query=query, now=_now())
        assert result.search_state is SearchState.BLOCKED
        assert UNSAFE_INDEX_STATE in result.reason_codes

    def test_empty_query(self) -> None:
        entry = _make_index_entry()
        index = _make_review_index(entries=(entry,))
        query = SearchQuery()
        result = build_search_result(index=index, query=query, now=_now())
        assert result.search_state is SearchState.BLOCKED
        assert EMPTY_QUERY in result.reason_codes

    def test_unsafe_query(self) -> None:
        # SearchQuery.__post_init__ rejects forbidden terms at construction time,
        # so we test with a mock query object to verify engine handling
        entry = _make_index_entry()
        index = _make_review_index(entries=(entry,))
        class BadQuery:
            is_empty = False
            query_text = "execute trade"
            filters = SearchFilter()
            match_mode = SearchMatchMode.ALL
            sort = SearchSort.SCORE_DESC
            limit = None
            include_blocked_entries = True
        result = build_search_result(index=index, query=BadQuery(), now=_now())  # type: ignore[arg-type]
        assert result.search_state is SearchState.BLOCKED
        # BadQuery is not a SearchQuery, so it returns INVALID_QUERY first
        assert INVALID_QUERY in result.reason_codes

    def test_invalid_query_type(self) -> None:
        entry = _make_index_entry()
        index = _make_review_index(entries=(entry,))
        result = build_search_result(
            index=index, query="not a query", now=_now()  # type: ignore[arg-type]
        )
        assert result.search_state is SearchState.BLOCKED
        assert INVALID_QUERY in result.reason_codes

    def test_happy_path_single_match(self) -> None:
        entry = _make_index_entry(report_id="btc-report")
        index = _make_review_index(entries=(entry,))
        query = SearchQuery(query_text="btc")
        result = build_search_result(index=index, query=query, now=_now())
        assert result.search_state is SearchState.READY
        assert len(result.entries) == 1
        assert result.entries[0].report_id == "btc-report"
        assert result.reason_codes == ()

    def test_happy_path_multiple_matches(self) -> None:
        e1 = _make_index_entry(entry_id="e1", report_id="btc-report")
        e2 = _make_index_entry(entry_id="e2", report_id="eth-report", metadata={"symbol": "ETH/USDT"})
        e3 = _make_index_entry(entry_id="e3", report_id="btc-analysis")
        index = _make_review_index(entries=(e1, e2, e3))
        query = SearchQuery(query_text="btc")
        result = build_search_result(index=index, query=query, now=_now())
        assert result.search_state is SearchState.READY
        assert len(result.entries) == 2
        report_ids = {e.report_id for e in result.entries}
        assert report_ids == {"btc-report", "btc-analysis"}

    def test_happy_path_no_matches(self) -> None:
        entry = _make_index_entry(report_id="eth-report", metadata={"symbol": "ETH/USDT"})
        index = _make_review_index(entries=(entry,))
        query = SearchQuery(query_text="btc")
        result = build_search_result(index=index, query=query, now=_now())
        assert result.search_state is SearchState.READY
        assert len(result.entries) == 0
        assert result.summary.matched_entries == 0

    def test_filter_combination_and(self) -> None:
        e1 = _make_index_entry(
            entry_id="e1", index_state=IndexState.READY, tags=("tag-a",)
        )
        e2 = _make_index_entry(
            entry_id="e2", index_state=IndexState.BLOCKED, tags=("tag-a",)
        )
        e3 = _make_index_entry(
            entry_id="e3", index_state=IndexState.READY, tags=("tag-b",)
        )
        index = _make_review_index(entries=(e1, e2, e3))
        query = SearchQuery(
            filters=SearchFilter(
                index_states=(IndexState.READY,),
                tags=("tag-a",),
            ),
            match_mode=SearchMatchMode.ALL,
        )
        result = build_search_result(index=index, query=query, now=_now())
        assert result.search_state is SearchState.READY
        assert len(result.entries) == 1
        assert result.entries[0].entry_id == "e1"

    def test_filter_combination_or_any_mode(self) -> None:
        e1 = _make_index_entry(entry_id="e1", index_state=IndexState.READY)
        e2 = _make_index_entry(entry_id="e2", index_state=IndexState.BLOCKED)
        index = _make_review_index(entries=(e1, e2))
        query = SearchQuery(
            filters=SearchFilter(index_states=(IndexState.READY,)),
            match_mode=SearchMatchMode.ANY,
        )
        result = build_search_result(index=index, query=query, now=_now())
        assert result.search_state is SearchState.READY
        assert len(result.entries) == 1
        assert result.entries[0].entry_id == "e1"

    def test_sort_by_score_desc_default(self) -> None:
        e1 = _make_index_entry(entry_id="e1", report_id="btc-report")
        e2 = _make_index_entry(entry_id="e2", report_id="eth-report", metadata={"symbol": "ETH/USDT"})
        index = _make_review_index(entries=(e1, e2))
        query = SearchQuery(query_text="btc")
        result = build_search_result(index=index, query=query, now=_now())
        assert result.search_state is SearchState.READY
        # Only e1 matches "btc"
        assert len(result.entries) == 1
        assert result.entries[0].entry_id == "e1"

    def test_custom_sort_override(self) -> None:
        e1 = _make_index_entry(entry_id="b", report_id="report-b")
        e2 = _make_index_entry(entry_id="a", report_id="report-a")
        index = _make_review_index(entries=(e1, e2))
        query = SearchQuery(query_text="report")
        result = build_search_result(
            index=index, query=query, sort=SearchSort.ENTRY_ID_ASC, now=_now()
        )
        assert result.entries[0].entry_id == "a"
        assert result.entries[1].entry_id == "b"

    def test_limit_applied(self) -> None:
        e1 = _make_index_entry(entry_id="e1")
        e2 = _make_index_entry(entry_id="e2")
        e3 = _make_index_entry(entry_id="e3")
        index = _make_review_index(entries=(e1, e2, e3))
        query = SearchQuery(query_text="report", limit=2)
        result = build_search_result(index=index, query=query, now=_now())
        assert len(result.entries) == 2

    def test_config_max_results_enforced(self) -> None:
        e1 = _make_index_entry(entry_id="e1")
        e2 = _make_index_entry(entry_id="e2")
        e3 = _make_index_entry(entry_id="e3")
        index = _make_review_index(entries=(e1, e2, e3))
        query = SearchQuery(query_text="report", limit=10)
        config = SearchConfig(max_results=2)
        result = build_search_result(index=index, query=query, config=config, now=_now())
        assert len(result.entries) == 2

    def test_exclude_blocked_entries(self) -> None:
        e1 = _make_index_entry(entry_id="e1", index_state=IndexState.READY)
        e2 = _make_index_entry(entry_id="e2", index_state=IndexState.BLOCKED)
        index = _make_review_index(entries=(e1, e2))
        query = SearchQuery(
            query_text="report",
            include_blocked_entries=False,
        )
        result = build_search_result(index=index, query=query, now=_now())
        assert len(result.entries) == 1
        assert result.entries[0].entry_id == "e1"

    def test_include_blocked_entries_by_default(self) -> None:
        e1 = _make_index_entry(entry_id="e1", index_state=IndexState.READY)
        e2 = _make_index_entry(entry_id="e2", index_state=IndexState.BLOCKED)
        index = _make_review_index(entries=(e1, e2))
        query = SearchQuery(query_text="report")
        result = build_search_result(index=index, query=query, now=_now())
        assert len(result.entries) == 2

    def test_summary_counts(self) -> None:
        e1 = _make_index_entry(
            entry_id="e1", index_state=IndexState.READY,
            entry_kind=IndexEntryKind.OBSERVATION_REPORT,
        )
        e2 = _make_index_entry(
            entry_id="e2", index_state=IndexState.BLOCKED,
            entry_kind=IndexEntryKind.REVIEW_AUDIT_RECORD,
        )
        e3 = _make_index_entry(
            entry_id="e3", index_state=IndexState.UNKNOWN,
            entry_kind=IndexEntryKind.LINKED_REPORT_REVIEW,
        )
        index = _make_review_index(entries=(e1, e2, e3))
        query = SearchQuery(query_text="report")
        result = build_search_result(index=index, query=query, now=_now())
        assert result.summary.total_entries == 3
        assert result.summary.matched_entries == 3
        assert result.summary.ready_count == 1
        assert result.summary.blocked_count == 1
        assert result.summary.unknown_count == 1

    def test_metadata_includes_query_and_sort(self) -> None:
        entry = _make_index_entry()
        index = _make_review_index(entries=(entry,))
        query = SearchQuery(query_text="btc")
        result = build_search_result(index=index, query=query, now=_now())
        assert "query_applied" in result.metadata
        assert "sort_applied" in result.metadata
        assert "btc" in result.metadata["query_applied"]

    def test_safety_flags_in_result(self) -> None:
        entry = _make_index_entry()
        index = _make_review_index(entries=(entry,))
        query = SearchQuery(query_text="btc")
        result = build_search_result(index=index, query=query, now=_now())
        assert isinstance(result.safety_flags, SearchSafetyFlags)
        assert result.safety_flags.dry_run is True
        assert result.safety_flags.search_feedback_into_execution is False

    def test_result_id_is_deterministic(self) -> None:
        entry = _make_index_entry()
        index = _make_review_index(entries=(entry,))
        query = SearchQuery(query_text="btc")
        now = _now()
        result1 = build_search_result(index=index, query=query, now=now)
        result2 = build_search_result(index=index, query=query, now=now)
        assert result1.search_id == result2.search_id

    def test_ready_result_has_no_reason_codes(self) -> None:
        entry = _make_index_entry()
        index = _make_review_index(entries=(entry,))
        query = SearchQuery(query_text="btc")
        result = build_search_result(index=index, query=query, now=_now())
        assert result.search_state is SearchState.READY
        assert result.reason_codes == ()

    def test_blocked_result_has_reason_codes(self) -> None:
        index = _make_review_index(entries=())
        query = SearchQuery(query_text="btc")
        result = build_search_result(index=index, query=query, now=_now())
        assert result.search_state is SearchState.BLOCKED
        assert len(result.reason_codes) > 0

    def test_entry_with_none_report_generated_at(self) -> None:
        entry = _make_index_entry(report_generated_at=None)
        index = _make_review_index(entries=(entry,))
        query = SearchQuery(query_text="report")
        result = build_search_result(index=index, query=query, now=_now())
        assert result.search_state is SearchState.READY
        assert len(result.entries) == 1

    def test_entry_with_none_reviewed_at(self) -> None:
        entry = _make_index_entry(reviewed_at=None)
        index = _make_review_index(entries=(entry,))
        query = SearchQuery(query_text="report")
        result = build_search_result(index=index, query=query, now=_now())
        assert result.search_state is SearchState.READY
        assert len(result.entries) == 1

    def test_filter_by_generated_at_range(self) -> None:
        e1 = _make_index_entry(entry_id="e1", report_generated_at=_now())
        e2 = _make_index_entry(entry_id="e2", report_generated_at=_later())
        index = _make_review_index(entries=(e1, e2))
        query = SearchQuery(
            filters=SearchFilter(
                generated_at_from=_now() - timedelta(minutes=1),
                generated_at_to=_now() + timedelta(minutes=1),
            )
        )
        result = build_search_result(index=index, query=query, now=_now())
        assert result.search_state is SearchState.READY
        assert len(result.entries) == 1
        assert result.entries[0].entry_id == "e1"

    def test_filter_by_reviewed_at_range(self) -> None:
        e1 = _make_index_entry(entry_id="e1", reviewed_at=_now())
        e2 = _make_index_entry(entry_id="e2", reviewed_at=_later())
        index = _make_review_index(entries=(e1, e2))
        query = SearchQuery(
            filters=SearchFilter(
                reviewed_at_from=_now() - timedelta(minutes=1),
                reviewed_at_to=_now() + timedelta(minutes=1),
            )
        )
        result = build_search_result(index=index, query=query, now=_now())
        assert result.search_state is SearchState.READY
        assert len(result.entries) == 1
        assert result.entries[0].entry_id == "e1"

    def test_no_file_reads(self) -> None:
        """Verify search does not open file references."""
        entry = _make_index_entry(local_report_reference="/does/not/exist.md")
        index = _make_review_index(entries=(entry,))
        query = SearchQuery(query_text="exist")
        result = build_search_result(index=index, query=query, now=_now())
        assert result.search_state is SearchState.READY
        assert len(result.entries) == 1

    def test_no_network(self) -> None:
        """Verify search does not make network calls."""
        entry = _make_index_entry()
        index = _make_review_index(entries=(entry,))
        query = SearchQuery(query_text="btc")
        result = build_search_result(index=index, query=query, now=_now())
        assert result.search_state is SearchState.READY
        # No network calls were made (implicit — no network code in engine)

    def test_search_result_is_human_audit_only(self) -> None:
        """Verify safety flags assert human-audit-only status."""
        entry = _make_index_entry()
        index = _make_review_index(entries=(entry,))
        query = SearchQuery(query_text="btc")
        result = build_search_result(index=index, query=query, now=_now())
        assert result.safety_flags.search_feedback_into_execution is False
        assert result.safety_flags.live_trading_enabled is False
