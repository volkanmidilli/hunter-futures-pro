"""Tests for hunter.review_search.models.

MVP-13 review_search model tests only.
No file I/O, network, database, Freqtrade, Binance, exchange, trading,
Web UI, dashboard, or integration behavior is exercised here.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from types import MappingProxyType

import pytest

from hunter.review_index.models import IndexEntryKind, IndexState
from hunter.review_search.models import (
    DEFAULT_BLOCKED,
    EMPTY_QUERY,
    FORBIDDEN_SEARCH_TERMS,
    INVALID_TIMESTAMP_RANGE,
    MISSING_INDEX,
    MISSING_QUERY,
    REASON_CODES,
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
    UNSAFE_QUERY_CONTENT,
)


def _now() -> datetime:
    return datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _later() -> datetime:
    return _now() + timedelta(hours=1)


def _result_entry(**overrides: object) -> SearchResultEntry:
    data: dict[str, object] = {
        "entry_id": "entry-1",
        "score": 10.0,
        "index_state": IndexState.READY,
        "entry_kind": IndexEntryKind.LINKED_REPORT_REVIEW,
        "report_id": "report-1",
        "audit_id": "audit-1",
        "review_status": "ACCEPTED",
        "reason_codes": ("OK",),
        "tags": ("tag-a",),
        "reviewer": "operator-a",
        "local_report_reference": "reports/review_index/report.md",
        "local_review_reference": "reports/review_index/review.md",
        "report_generated_at": _now(),
        "audit_generated_at": _now(),
        "reviewed_at": _now(),
        "metadata": {"symbol": "BTC/USDT"},
    }
    data.update(overrides)
    return SearchResultEntry(**data)


def _summary(**overrides: object) -> SearchResultSummary:
    data: dict[str, object] = {
        "total_entries": 1,
        "matched_entries": 1,
        "returned_entries": 1,
        "ready_count": 1,
        "blocked_count": 0,
        "unknown_count": 0,
        "reason_counts": {"OK": 1},
    }
    data.update(overrides)
    return SearchResultSummary(**data)


def _ready_result(**overrides: object) -> SearchResult:
    entry = _result_entry()
    data: dict[str, object] = {
        "search_id": "search-1",
        "generated_at": _now(),
        "search_state": SearchState.READY,
        "query": SearchQuery(query_text="BTC"),
        "entries": (entry,),
        "summary": _summary(),
        "reason_codes": (),
        "safety_flags": SearchSafetyFlags(),
        "metadata": {"purpose": "unit-test"},
    }
    data.update(overrides)
    return SearchResult(**data)


class TestEnumsAndReasonCodes:
    def test_search_state_values_are_deterministic(self) -> None:
        assert SearchState.DISABLED.value == "DISABLED"
        assert SearchState.READY.value == "READY"
        assert SearchState.BLOCKED.value == "BLOCKED"
        assert SearchState.UNKNOWN.value == "UNKNOWN"

    def test_sort_values_are_deterministic(self) -> None:
        assert SearchSort.SCORE_DESC.value == "SCORE_DESC"
        assert SearchSort.REPORT_GENERATED_AT_DESC.value == "REPORT_GENERATED_AT_DESC"
        assert SearchSort.REPORT_GENERATED_AT_ASC.value == "REPORT_GENERATED_AT_ASC"
        assert SearchSort.REVIEWED_AT_DESC.value == "REVIEWED_AT_DESC"
        assert SearchSort.ENTRY_ID_ASC.value == "ENTRY_ID_ASC"

    def test_match_mode_values_are_deterministic(self) -> None:
        assert SearchMatchMode.ALL.value == "ALL"
        assert SearchMatchMode.ANY.value == "ANY"

    def test_reason_codes_are_ordered_and_unique(self) -> None:
        assert REASON_CODES[0] == MISSING_INDEX
        assert REASON_CODES[1] == MISSING_QUERY
        assert EMPTY_QUERY in REASON_CODES
        assert INVALID_TIMESTAMP_RANGE in REASON_CODES
        assert UNSAFE_QUERY_CONTENT in REASON_CODES
        assert REASON_CODES[-1] == DEFAULT_BLOCKED
        assert len(REASON_CODES) == len(set(REASON_CODES))

    def test_forbidden_terms_include_secrets_and_trading_actions(self) -> None:
        assert "api_key" in FORBIDDEN_SEARCH_TERMS
        assert "secret" in FORBIDDEN_SEARCH_TERMS
        assert "execute trade" in FORBIDDEN_SEARCH_TERMS
        assert "market order" in FORBIDDEN_SEARCH_TERMS


class TestSearchFilter:
    def test_default_filter_is_empty(self) -> None:
        search_filter = SearchFilter()
        assert search_filter.is_empty is True
        assert search_filter.index_states == ()
        assert search_filter.entry_kinds == ()

    def test_non_empty_filter(self) -> None:
        search_filter = SearchFilter(
            index_states=(IndexState.READY,),
            entry_kinds=(IndexEntryKind.LINKED_REPORT_REVIEW,),
            reason_codes=("OK",),
            reviewers=("operator-a",),
            tags=("tag-a",),
            report_ids=("report-1",),
            audit_ids=("audit-1",),
            local_reference_contains=("reports/review_index",),
            metadata_text=("BTC",),
            generated_at_from=_now(),
            generated_at_to=_later(),
            reviewed_at_from=_now(),
            reviewed_at_to=_later(),
        )
        assert search_filter.is_empty is False

    def test_filter_is_frozen(self) -> None:
        search_filter = SearchFilter()
        with pytest.raises(FrozenInstanceError):
            search_filter.reason_codes = ("X",)  # type: ignore[misc]

    def test_index_states_must_be_tuple(self) -> None:
        with pytest.raises(ValueError, match="index_states"):
            SearchFilter(index_states=[IndexState.READY])  # type: ignore[arg-type]

    def test_index_states_must_contain_index_state(self) -> None:
        with pytest.raises(ValueError, match="IndexState"):
            SearchFilter(index_states=("READY",))  # type: ignore[arg-type]

    def test_entry_kinds_must_contain_entry_kind(self) -> None:
        with pytest.raises(ValueError, match="IndexEntryKind"):
            SearchFilter(entry_kinds=("LINKED_REPORT_REVIEW",))  # type: ignore[arg-type]

    def test_string_filter_fields_must_be_tuples(self) -> None:
        with pytest.raises(ValueError, match="reason_codes"):
            SearchFilter(reason_codes=["OK"])  # type: ignore[arg-type]

    def test_string_filter_values_must_be_non_empty(self) -> None:
        with pytest.raises(ValueError, match="tags"):
            SearchFilter(tags=("",))

    def test_generated_at_must_be_timezone_aware(self) -> None:
        with pytest.raises(ValueError, match="generated_at_from"):
            SearchFilter(generated_at_from=datetime(2024, 1, 1, 12, 0, 0))

    def test_reviewed_at_must_be_timezone_aware(self) -> None:
        with pytest.raises(ValueError, match="reviewed_at_to"):
            SearchFilter(reviewed_at_to=datetime(2024, 1, 1, 12, 0, 0))

    def test_generated_range_must_be_ordered(self) -> None:
        with pytest.raises(ValueError, match="generated_at_from"):
            SearchFilter(generated_at_from=_later(), generated_at_to=_now())

    def test_reviewed_range_must_be_ordered(self) -> None:
        with pytest.raises(ValueError, match="reviewed_at_from"):
            SearchFilter(reviewed_at_from=_later(), reviewed_at_to=_now())

    def test_rejects_unsafe_filter_content(self) -> None:
        with pytest.raises(ValueError, match="unsafe"):
            SearchFilter(metadata_text=("execute trade",))

    def test_local_references_are_strings_only(self) -> None:
        search_filter = SearchFilter(local_reference_contains=("reports/local.md",))
        assert search_filter.local_reference_contains == ("reports/local.md",)


class TestSearchQuery:
    def test_default_query_is_empty(self) -> None:
        query = SearchQuery()
        assert query.is_empty is True
        assert query.query_text == ""
        assert query.filters == SearchFilter()
        assert query.match_mode is SearchMatchMode.ALL
        assert query.sort is SearchSort.SCORE_DESC
        assert query.limit is None
        assert query.include_blocked_entries is True

    def test_non_empty_query_text(self) -> None:
        query = SearchQuery(query_text="BTC")
        assert query.is_empty is False

    def test_non_empty_filter_makes_query_non_empty(self) -> None:
        query = SearchQuery(filters=SearchFilter(tags=("tag-a",)))
        assert query.is_empty is False

    def test_query_is_frozen(self) -> None:
        query = SearchQuery(query_text="BTC")
        with pytest.raises(FrozenInstanceError):
            query.query_text = "ETH"  # type: ignore[misc]

    def test_query_text_must_be_string(self) -> None:
        with pytest.raises(ValueError, match="query_text"):
            SearchQuery(query_text=123)  # type: ignore[arg-type]

    def test_filters_must_be_search_filter(self) -> None:
        with pytest.raises(ValueError, match="filters"):
            SearchQuery(filters={})  # type: ignore[arg-type]

    def test_match_mode_must_be_enum(self) -> None:
        with pytest.raises(ValueError, match="match_mode"):
            SearchQuery(match_mode="ALL")  # type: ignore[arg-type]

    def test_sort_must_be_enum(self) -> None:
        with pytest.raises(ValueError, match="sort"):
            SearchQuery(sort="SCORE_DESC")  # type: ignore[arg-type]

    def test_limit_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="limit"):
            SearchQuery(limit=0)

    def test_rejects_unsafe_query_text(self) -> None:
        with pytest.raises(ValueError, match="unsafe"):
            SearchQuery(query_text="please place order")


class TestSearchConfig:
    def test_safe_defaults(self) -> None:
        config = SearchConfig()
        assert config.max_results == 1000
        assert config.allow_empty_query is False
        assert config.strict_timestamp_validation is True
        assert config.case_sensitive_text_search is False

    def test_config_is_frozen(self) -> None:
        config = SearchConfig()
        with pytest.raises(FrozenInstanceError):
            config.max_results = 10  # type: ignore[misc]

    def test_max_results_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="max_results"):
            SearchConfig(max_results=0)


class TestSearchSafetyFlags:
    def test_safe_defaults(self) -> None:
        flags = SearchSafetyFlags()
        assert flags.dry_run is True
        assert flags.live_trading_enabled is False
        assert flags.real_orders_enabled is False
        assert flags.leverage_enabled is False
        assert flags.shorting_enabled is False
        assert flags.report_feedback_into_execution is False
        assert flags.operator_feedback_into_execution is False
        assert flags.index_feedback_into_execution is False
        assert flags.search_feedback_into_execution is False
        assert flags.file_reference_traversal_enabled is False
        assert flags.database_persistence_enabled is False
        assert flags.web_ui_enabled is False
        assert flags.dashboard_enabled is False

    @pytest.mark.parametrize(
        "field_name",
        (
            "live_trading_enabled",
            "real_orders_enabled",
            "leverage_enabled",
            "shorting_enabled",
            "report_feedback_into_execution",
            "operator_feedback_into_execution",
            "index_feedback_into_execution",
            "search_feedback_into_execution",
            "file_reference_traversal_enabled",
            "database_persistence_enabled",
            "web_ui_enabled",
            "dashboard_enabled",
        ),
    )
    def test_unsafe_flags_are_rejected(self, field_name: str) -> None:
        with pytest.raises(ValueError, match="unsafe"):
            SearchSafetyFlags(**{field_name: True})

    def test_safety_flags_are_frozen(self) -> None:
        flags = SearchSafetyFlags()
        with pytest.raises(FrozenInstanceError):
            flags.dry_run = False  # type: ignore[misc]


class TestSearchResultEntry:
    def test_valid_entry(self) -> None:
        entry = _result_entry()
        assert entry.entry_id == "entry-1"
        assert entry.score == 10.0
        assert entry.index_state is IndexState.READY
        assert entry.entry_kind is IndexEntryKind.LINKED_REPORT_REVIEW
        assert entry.report_id == "report-1"
        assert entry.metadata["symbol"] == "BTC/USDT"
        assert isinstance(entry.metadata, MappingProxyType)

    def test_entry_is_frozen(self) -> None:
        entry = _result_entry()
        with pytest.raises(FrozenInstanceError):
            entry.score = 1.0  # type: ignore[misc]

    def test_metadata_mapping_is_immutable(self) -> None:
        entry = _result_entry(metadata={"a": "b"})
        with pytest.raises(TypeError):
            entry.metadata["a"] = "c"  # type: ignore[index]

    def test_entry_id_required(self) -> None:
        with pytest.raises(ValueError, match="entry_id"):
            _result_entry(entry_id="")

    def test_score_must_be_non_negative(self) -> None:
        with pytest.raises(ValueError, match="score"):
            _result_entry(score=-1.0)

    def test_index_state_must_be_enum(self) -> None:
        with pytest.raises(ValueError, match="index_state"):
            _result_entry(index_state="READY")

    def test_entry_kind_must_be_enum(self) -> None:
        with pytest.raises(ValueError, match="entry_kind"):
            _result_entry(entry_kind="LINKED_REPORT_REVIEW")

    def test_report_id_required(self) -> None:
        with pytest.raises(ValueError, match="report_id"):
            _result_entry(report_id="")

    def test_reason_codes_must_be_tuple(self) -> None:
        with pytest.raises(ValueError, match="reason_codes"):
            _result_entry(reason_codes=["OK"])

    def test_tags_must_be_tuple(self) -> None:
        with pytest.raises(ValueError, match="tags"):
            _result_entry(tags=["tag-a"])

    def test_datetimes_must_be_timezone_aware(self) -> None:
        with pytest.raises(ValueError, match="reviewed_at"):
            _result_entry(reviewed_at=datetime(2024, 1, 1, 12, 0, 0))

    def test_file_references_remain_plain_strings(self) -> None:
        entry = _result_entry(
            local_report_reference="../reports/local.md",
            local_review_reference="../reviews/local.md",
        )
        assert entry.local_report_reference == "../reports/local.md"
        assert entry.local_review_reference == "../reviews/local.md"


class TestSearchResultSummary:
    def test_valid_summary(self) -> None:
        summary = _summary()
        assert summary.total_entries == 1
        assert summary.matched_entries == 1
        assert summary.returned_entries == 1
        assert summary.reason_counts["OK"] == 1
        assert isinstance(summary.reason_counts, MappingProxyType)

    def test_summary_is_frozen(self) -> None:
        summary = _summary()
        with pytest.raises(FrozenInstanceError):
            summary.total_entries = 2  # type: ignore[misc]

    def test_reason_counts_mapping_is_immutable(self) -> None:
        summary = _summary(reason_counts={"OK": 1})
        with pytest.raises(TypeError):
            summary.reason_counts["OK"] = 2  # type: ignore[index]

    @pytest.mark.parametrize(
        "field_name",
        ("total_entries", "matched_entries", "returned_entries", "ready_count", "blocked_count", "unknown_count"),
    )
    def test_counts_must_be_non_negative(self, field_name: str) -> None:
        with pytest.raises(ValueError, match=field_name):
            _summary(**{field_name: -1})

    def test_matched_entries_cannot_exceed_total(self) -> None:
        with pytest.raises(ValueError, match="matched_entries"):
            _summary(total_entries=1, matched_entries=2)

    def test_returned_entries_cannot_exceed_matched(self) -> None:
        with pytest.raises(ValueError, match="returned_entries"):
            _summary(total_entries=2, matched_entries=1, returned_entries=2)

    def test_state_counts_cannot_exceed_returned(self) -> None:
        with pytest.raises(ValueError, match="state counts"):
            _summary(returned_entries=1, ready_count=1, blocked_count=1)

    def test_reason_count_key_must_be_non_empty(self) -> None:
        with pytest.raises(ValueError, match="reason_counts keys"):
            _summary(reason_counts={"": 1})

    def test_reason_count_value_must_be_non_negative(self) -> None:
        with pytest.raises(ValueError, match="reason_counts values"):
            _summary(reason_counts={"OK": -1})


class TestSearchResult:
    def test_ready_result(self) -> None:
        result = _ready_result()
        assert result.search_id == "search-1"
        assert result.search_state is SearchState.READY
        assert len(result.entries) == 1
        assert result.reason_codes == ()
        assert result.metadata["purpose"] == "unit-test"
        assert isinstance(result.metadata, MappingProxyType)

    def test_result_is_frozen(self) -> None:
        result = _ready_result()
        with pytest.raises(FrozenInstanceError):
            result.search_id = "other"  # type: ignore[misc]

    def test_metadata_mapping_is_immutable(self) -> None:
        result = _ready_result(metadata={"a": "b"})
        with pytest.raises(TypeError):
            result.metadata["a"] = "c"  # type: ignore[index]

    def test_search_id_required(self) -> None:
        with pytest.raises(ValueError, match="search_id"):
            _ready_result(search_id="")

    def test_generated_at_must_be_timezone_aware(self) -> None:
        with pytest.raises(ValueError, match="generated_at"):
            _ready_result(generated_at=datetime(2024, 1, 1, 12, 0, 0))

    def test_search_state_must_be_enum(self) -> None:
        with pytest.raises(ValueError, match="search_state"):
            _ready_result(search_state="READY")

    def test_query_must_be_search_query(self) -> None:
        with pytest.raises(ValueError, match="query"):
            _ready_result(query={})

    def test_entries_must_be_tuple(self) -> None:
        with pytest.raises(ValueError, match="entries"):
            _ready_result(entries=[])

    def test_entries_must_contain_result_entries(self) -> None:
        with pytest.raises(ValueError, match="SearchResultEntry"):
            _ready_result(entries=("entry-1",))

    def test_summary_must_be_search_result_summary(self) -> None:
        with pytest.raises(ValueError, match="summary"):
            _ready_result(summary={})

    def test_safety_flags_must_be_search_safety_flags(self) -> None:
        with pytest.raises(ValueError, match="safety_flags"):
            _ready_result(safety_flags={})

    def test_reason_codes_must_be_known(self) -> None:
        with pytest.raises(ValueError, match="unsupported reason code"):
            SearchResult.blocked(search_id="blocked-1", generated_at=_now(), reason_code="NOPE")

    def test_blocked_result_requires_reason_code(self) -> None:
        with pytest.raises(ValueError, match="reason_codes"):
            _ready_result(search_state=SearchState.BLOCKED, reason_codes=())

    def test_ready_result_must_not_have_reason_codes(self) -> None:
        with pytest.raises(ValueError, match="READY"):
            _ready_result(reason_codes=(DEFAULT_BLOCKED,))

    def test_blocked_factory(self) -> None:
        result = SearchResult.blocked(
            search_id="blocked-1",
            generated_at=_now(),
            reason_code=MISSING_INDEX,
            query=SearchQuery(query_text="BTC"),
            metadata={"blocked": True},
        )
        assert result.search_state is SearchState.BLOCKED
        assert result.entries == ()
        assert result.summary == SearchResultSummary()
        assert result.reason_codes == (MISSING_INDEX,)
        assert result.query.query_text == "BTC"
        assert result.metadata["blocked"] is True

    def test_blocked_factory_defaults(self) -> None:
        result = SearchResult.blocked(search_id="blocked-1", generated_at=_now())
        assert result.reason_codes == (DEFAULT_BLOCKED,)
        assert result.query == SearchQuery()
        assert result.safety_flags == SearchSafetyFlags()

    def test_unknown_result_with_reason_code_is_valid(self) -> None:
        result = _ready_result(
            search_state=SearchState.UNKNOWN,
            entries=(),
            summary=SearchResultSummary(),
            reason_codes=(DEFAULT_BLOCKED,),
        )
        assert result.search_state is SearchState.UNKNOWN

    def test_disabled_result_with_reason_code_is_valid(self) -> None:
        result = _ready_result(
            search_state=SearchState.DISABLED,
            entries=(),
            summary=SearchResultSummary(),
            reason_codes=(DEFAULT_BLOCKED,),
        )
        assert result.search_state is SearchState.DISABLED


class TestSafetyNoSideEffects:
    def test_models_do_not_open_file_references(self, tmp_path) -> None:
        missing_file = tmp_path / "does-not-exist.md"
        entry = _result_entry(local_report_reference=str(missing_file))
        assert entry.local_report_reference == str(missing_file)
        assert not missing_file.exists()

    def test_models_do_not_create_files(self, tmp_path) -> None:
        before = set(tmp_path.iterdir())
        SearchFilter(local_reference_contains=(str(tmp_path / "x.md"),))
        SearchQuery(query_text="BTC")
        _result_entry(local_report_reference=str(tmp_path / "x.md"))
        after = set(tmp_path.iterdir())
        assert after == before
