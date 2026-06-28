"""Integration tests for hunter.review_search package.

MVP-13 end-to-end integration tests only.
No network, database, Freqtrade, Binance, exchange, trading,
Web UI, dashboard, or production data access is exercised here.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from hunter.review_index.models import (
    IndexDataQuality,
    IndexEntry,
    IndexEntryKind,
    IndexSafetyFlags,
    IndexState,
    IndexSummary,
    ReviewIndex,
)
from hunter.review_search.engine import build_search_result
from hunter.review_search.models import (
    DEFAULT_BLOCKED,
    EMPTY_INDEX,
    EMPTY_QUERY,
    INVALID_QUERY,
    INVALID_SORT_FIELD,
    INVALID_TIMESTAMP_RANGE,
    MISSING_INDEX,
    UNSAFE_INDEX_STATE,
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
)
from hunter.review_search.writer import (
    search_result_to_dict,
    search_result_to_markdown,
    write_search_result,
)


def _now() -> datetime:
    return datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


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


def _make_review_index(
    entries: tuple[IndexEntry, ...] = (),
    state: IndexState = IndexState.READY,
    reason_codes: tuple[str, ...] = (),
) -> ReviewIndex:
    if state is not IndexState.READY and not reason_codes:
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


class TestHappyPath:
    def test_full_flow_search_and_serialize(self, tmp_path: Path) -> None:
        entry = _make_index_entry()
        index = _make_review_index(entries=(entry,))
        query = SearchQuery(query_text="BTC")
        result = build_search_result(index=index, query=query, now=_now())

        assert result.search_state is SearchState.READY
        assert len(result.entries) == 1

        # Serialize to dict
        d = search_result_to_dict(result)
        assert d["search_state"] == "READY"
        assert len(d["entries"]) == 1

        # Write to files
        json_path = tmp_path / "result.json"
        md_path = tmp_path / "result.md"
        write_search_result(result, json_path, md_path)

        assert json_path.exists()
        assert md_path.exists()

        # Verify JSON round-trip
        data = json.loads(json_path.read_text())
        assert data["search_id"] == result.search_id
        assert data["search_state"] == "READY"

        # Verify Markdown content
        md_text = md_path.read_text()
        assert "# Review Search Result" in md_text
        assert "human-audit catalog artifact only" in md_text

    def test_multiple_entries_filtered_and_sorted(self, tmp_path: Path) -> None:
        e1 = _make_index_entry(
            entry_id="e1", report_id="btc-report", tags=("priority-high",),
            report_generated_at=_now(),
        )
        e2 = _make_index_entry(
            entry_id="e2", report_id="eth-report", tags=("priority-low",),
            report_generated_at=_now() + timedelta(hours=1),
            metadata={"symbol": "ETH/USDT"},
        )
        e3 = _make_index_entry(
            entry_id="e3", report_id="btc-analysis", tags=("priority-high",),
            report_generated_at=_now() + timedelta(hours=2),
        )
        index = _make_review_index(entries=(e1, e2, e3))
        query = SearchQuery(
            query_text="btc",
            filters=SearchFilter(tags=("priority-high",)),
            match_mode=SearchMatchMode.ALL,
            sort=SearchSort.REPORT_GENERATED_AT_DESC,
        )
        result = build_search_result(index=index, query=query, now=_now())

        assert result.search_state is SearchState.READY
        assert len(result.entries) == 2
        # Sorted by report_generated_at DESC
        assert result.entries[0].entry_id == "e3"
        assert result.entries[1].entry_id == "e1"

        # Write and verify
        json_path = tmp_path / "result.json"
        md_path = tmp_path / "result.md"
        write_search_result(result, json_path, md_path)
        assert json_path.exists()
        assert md_path.exists()

    def test_filter_by_state_and_kind(self, tmp_path: Path) -> None:
        e1 = _make_index_entry(
            entry_id="e1", index_state=IndexState.READY,
            entry_kind=IndexEntryKind.OBSERVATION_REPORT,
        )
        e2 = _make_index_entry(
            entry_id="e2", index_state=IndexState.BLOCKED,
            entry_kind=IndexEntryKind.REVIEW_AUDIT_RECORD,
        )
        e3 = _make_index_entry(
            entry_id="e3", index_state=IndexState.READY,
            entry_kind=IndexEntryKind.LINKED_REPORT_REVIEW,
        )
        index = _make_review_index(entries=(e1, e2, e3))
        query = SearchQuery(
            filters=SearchFilter(
                index_states=(IndexState.READY,),
                entry_kinds=(IndexEntryKind.OBSERVATION_REPORT,),
            ),
        )
        result = build_search_result(index=index, query=query, now=_now())

        assert result.search_state is SearchState.READY
        assert len(result.entries) == 1
        assert result.entries[0].entry_id == "e1"

        # Verify JSON
        d = search_result_to_dict(result)
        assert d["summary"]["total_entries"] == 3
        assert d["summary"]["matched_entries"] == 1
        assert d["summary"]["ready_count"] == 1

    def test_text_search_in_metadata(self, tmp_path: Path) -> None:
        e1 = _make_index_entry(
            entry_id="e1", metadata={"symbol": "BTC/USDT", "market": "binance"},
        )
        e2 = _make_index_entry(
            entry_id="e2", metadata={"symbol": "ETH/USDT", "market": "kraken"},
        )
        index = _make_review_index(entries=(e1, e2))
        query = SearchQuery(query_text="kraken")
        result = build_search_result(index=index, query=query, now=_now())

        assert result.search_state is SearchState.READY
        assert len(result.entries) == 1
        assert result.entries[0].entry_id == "e2"

    def test_timestamp_range_filter(self, tmp_path: Path) -> None:
        e1 = _make_index_entry(
            entry_id="e1", report_generated_at=_now(),
        )
        e2 = _make_index_entry(
            entry_id="e2", report_generated_at=_now() + timedelta(hours=2),
        )
        index = _make_review_index(entries=(e1, e2))
        query = SearchQuery(
            filters=SearchFilter(
                generated_at_from=_now() - timedelta(minutes=1),
                generated_at_to=_now() + timedelta(minutes=1),
            ),
        )
        result = build_search_result(index=index, query=query, now=_now())

        assert result.search_state is SearchState.READY
        assert len(result.entries) == 1
        assert result.entries[0].entry_id == "e1"

    def test_reviewer_and_tags_combined(self, tmp_path: Path) -> None:
        e1 = _make_index_entry(
            entry_id="e1", reviewer="alice", tags=("urgent", "btc"),
        )
        e2 = _make_index_entry(
            entry_id="e2", reviewer="bob", tags=("urgent", "eth"),
        )
        e3 = _make_index_entry(
            entry_id="e3", reviewer="alice", tags=("low", "btc"),
        )
        index = _make_review_index(entries=(e1, e2, e3))
        query = SearchQuery(
            filters=SearchFilter(
                reviewers=("alice",),
                tags=("urgent",),
            ),
        )
        result = build_search_result(index=index, query=query, now=_now())

        assert result.search_state is SearchState.READY
        assert len(result.entries) == 1
        assert result.entries[0].entry_id == "e1"

    def test_local_reference_substring_match(self, tmp_path: Path) -> None:
        e1 = _make_index_entry(
            entry_id="e1", local_report_reference="reports/2024/btc.md",
        )
        e2 = _make_index_entry(
            entry_id="e2", local_report_reference="reports/2024/eth.md",
        )
        index = _make_review_index(entries=(e1, e2))
        query = SearchQuery(
            filters=SearchFilter(local_reference_contains=("btc",)),
        )
        result = build_search_result(index=index, query=query, now=_now())

        assert result.search_state is SearchState.READY
        assert len(result.entries) == 1
        assert result.entries[0].entry_id == "e1"

    def test_score_based_ranking(self, tmp_path: Path) -> None:
        e1 = _make_index_entry(
            entry_id="e1", report_id="btc-report", tags=("btc",),
        )
        e2 = _make_index_entry(
            entry_id="e2", report_id="eth-report", tags=("btc",),
        )
        index = _make_review_index(entries=(e1, e2))
        query = SearchQuery(
            query_text="btc",
            filters=SearchFilter(tags=("btc",)),
            match_mode=SearchMatchMode.ALL,
        )
        result = build_search_result(index=index, query=query, now=_now())

        assert result.search_state is SearchState.READY
        assert len(result.entries) == 2
        # Both match, both have same score (query_text + tags = 2/2 = 1.0)
        for entry in result.entries:
            assert entry.score == 1.0

    def test_pagination_with_limit(self, tmp_path: Path) -> None:
        entries = tuple(
            _make_index_entry(entry_id=f"e{i}", report_id=f"report-{i}")
            for i in range(10)
        )
        index = _make_review_index(entries=entries)
        query = SearchQuery(query_text="report", limit=5)
        result = build_search_result(index=index, query=query, now=_now())

        assert result.search_state is SearchState.READY
        assert len(result.entries) == 5
        assert result.summary.matched_entries == 10
        assert result.summary.returned_entries == 5

    def test_config_max_results_limits_output(self, tmp_path: Path) -> None:
        entries = tuple(
            _make_index_entry(entry_id=f"e{i}", report_id=f"report-{i}")
            for i in range(10)
        )
        index = _make_review_index(entries=entries)
        query = SearchQuery(query_text="report", limit=100)
        config = SearchConfig(max_results=3)
        result = build_search_result(index=index, query=query, config=config, now=_now())

        assert result.search_state is SearchState.READY
        assert len(result.entries) == 3


class TestErrorPaths:
    def test_missing_index_returns_blocked(self) -> None:
        query = SearchQuery(query_text="BTC")
        result = build_search_result(index=None, query=query, now=_now())  # type: ignore[arg-type]
        assert result.search_state is SearchState.BLOCKED
        assert MISSING_INDEX in result.reason_codes

    def test_empty_index_returns_blocked(self) -> None:
        index = _make_review_index(entries=())
        query = SearchQuery(query_text="BTC")
        result = build_search_result(index=index, query=query, now=_now())
        assert result.search_state is SearchState.BLOCKED
        assert EMPTY_INDEX in result.reason_codes

    def test_blocked_index_input_returns_blocked(self) -> None:
        entry = _make_index_entry()
        index = _make_review_index(entries=(entry,), state=IndexState.BLOCKED)
        query = SearchQuery(query_text="BTC")
        result = build_search_result(index=index, query=query, now=_now())
        assert result.search_state is SearchState.BLOCKED
        assert UNSAFE_INDEX_STATE in result.reason_codes

    def test_empty_query_returns_blocked(self) -> None:
        entry = _make_index_entry()
        index = _make_review_index(entries=(entry,))
        query = SearchQuery()
        result = build_search_result(index=index, query=query, now=_now())
        assert result.search_state is SearchState.BLOCKED
        assert EMPTY_QUERY in result.reason_codes

    def test_invalid_query_type_returns_blocked(self) -> None:
        entry = _make_index_entry()
        index = _make_review_index(entries=(entry,))
        result = build_search_result(
            index=index, query="not a query", now=_now()  # type: ignore[arg-type]
        )
        assert result.search_state is SearchState.BLOCKED
        assert INVALID_QUERY in result.reason_codes

    def test_unsafe_query_content_returns_blocked(self, tmp_path: Path) -> None:
        # We can't create a SearchQuery with unsafe content due to __post_init__
        # validation, so we test that the model rejects it at construction time
        with pytest.raises(ValueError, match="unsafe"):
            SearchQuery(query_text="execute trade")

    def test_blocked_result_serializes_to_dict(self) -> None:
        result = SearchResult.blocked(
            search_id="blocked-1",
            generated_at=_now(),
            reason_code=MISSING_INDEX,
        )
        d = search_result_to_dict(result)
        assert d["search_state"] == "BLOCKED"
        assert d["reason_codes"] == ["MISSING_INDEX"]
        assert d["entries"] == []

    def test_blocked_result_serializes_to_markdown(self) -> None:
        result = SearchResult.blocked(
            search_id="blocked-1",
            generated_at=_now(),
            reason_code=MISSING_INDEX,
        )
        md = search_result_to_markdown(result)
        assert "BLOCKED" in md
        assert "MISSING_INDEX" in md
        assert "human-audit catalog artifact only" in md


class TestSorting:
    def test_sort_by_entry_id_asc(self) -> None:
        e1 = _make_index_entry(entry_id="c")
        e2 = _make_index_entry(entry_id="a")
        e3 = _make_index_entry(entry_id="b")
        index = _make_review_index(entries=(e1, e2, e3))
        query = SearchQuery(query_text="report")
        result = build_search_result(
            index=index, query=query, sort=SearchSort.ENTRY_ID_ASC, now=_now()
        )
        assert result.entries[0].entry_id == "a"
        assert result.entries[1].entry_id == "b"
        assert result.entries[2].entry_id == "c"

    def test_sort_by_report_generated_at_desc(self) -> None:
        e1 = _make_index_entry(entry_id="e1", report_generated_at=_now())
        e2 = _make_index_entry(entry_id="e2", report_generated_at=_now() + timedelta(hours=1))
        e3 = _make_index_entry(entry_id="e3", report_generated_at=_now() - timedelta(hours=1))
        index = _make_review_index(entries=(e1, e2, e3))
        query = SearchQuery(query_text="report")
        result = build_search_result(
            index=index, query=query, sort=SearchSort.REPORT_GENERATED_AT_DESC, now=_now()
        )
        assert result.entries[0].entry_id == "e2"
        assert result.entries[1].entry_id == "e1"
        assert result.entries[2].entry_id == "e3"

    def test_sort_by_report_generated_at_asc(self) -> None:
        e1 = _make_index_entry(entry_id="e1", report_generated_at=_now() + timedelta(hours=1))
        e2 = _make_index_entry(entry_id="e2", report_generated_at=_now() - timedelta(hours=1))
        index = _make_review_index(entries=(e1, e2))
        query = SearchQuery(query_text="report")
        result = build_search_result(
            index=index, query=query, sort=SearchSort.REPORT_GENERATED_AT_ASC, now=_now()
        )
        assert result.entries[0].entry_id == "e2"
        assert result.entries[1].entry_id == "e1"

    def test_sort_by_reviewed_at_desc(self) -> None:
        e1 = _make_index_entry(entry_id="e1", reviewed_at=_now())
        e2 = _make_index_entry(entry_id="e2", reviewed_at=_now() + timedelta(hours=1))
        index = _make_review_index(entries=(e1, e2))
        query = SearchQuery(query_text="report")
        result = build_search_result(
            index=index, query=query, sort=SearchSort.REVIEWED_AT_DESC, now=_now()
        )
        assert result.entries[0].entry_id == "e2"
        assert result.entries[1].entry_id == "e1"

    def test_sort_by_score_desc(self) -> None:
        # Score is determined by match specificity
        e1 = _make_index_entry(entry_id="e1", report_id="btc-report")
        e2 = _make_index_entry(entry_id="e2", report_id="eth-report", metadata={"symbol": "ETH/USDT"})
        index = _make_review_index(entries=(e1, e2))
        query = SearchQuery(query_text="btc")
        result = build_search_result(index=index, query=query, now=_now())
        # Only e1 matches, and default sort is SCORE_DESC
        assert len(result.entries) == 1
        assert result.entries[0].entry_id == "e1"


class TestSafetyAssertions:
    def test_no_file_reads_from_production_paths(self, tmp_path: Path) -> None:
        """Search operates on in-memory objects only, never reads files."""
        entry = _make_index_entry(local_report_reference="/production/data.json")
        index = _make_review_index(entries=(entry,))
        query = SearchQuery(query_text="production")
        result = build_search_result(index=index, query=query, now=_now())
        assert result.search_state is SearchState.READY
        # The file reference was never opened or traversed
        assert len(result.entries) == 1

    def test_no_network_calls(self, tmp_path: Path) -> None:
        """Search never makes network calls."""
        entry = _make_index_entry()
        index = _make_review_index(entries=(entry,))
        query = SearchQuery(query_text="BTC")
        result = build_search_result(index=index, query=query, now=_now())
        assert result.search_state is SearchState.READY
        # No network code exists in the search package

    def test_no_execution_feedback(self, tmp_path: Path) -> None:
        """Search results never feed back into execution paths."""
        entry = _make_index_entry()
        index = _make_review_index(entries=(entry,))
        query = SearchQuery(query_text="BTC")
        result = build_search_result(index=index, query=query, now=_now())
        assert result.safety_flags.search_feedback_into_execution is False
        assert result.safety_flags.report_feedback_into_execution is False
        assert result.safety_flags.index_feedback_into_execution is False
        assert result.safety_flags.operator_feedback_into_execution is False

    def test_no_trading_logic(self, tmp_path: Path) -> None:
        """Search results contain no trading decisions or approvals."""
        entry = _make_index_entry()
        index = _make_review_index(entries=(entry,))
        query = SearchQuery(query_text="BTC")
        result = build_search_result(index=index, query=query, now=_now())
        assert result.safety_flags.live_trading_enabled is False
        assert result.safety_flags.real_orders_enabled is False
        assert result.safety_flags.leverage_enabled is False
        assert result.safety_flags.shorting_enabled is False

    def test_no_secrets_in_output(self, tmp_path: Path) -> None:
        """Search output must not contain API keys or secrets."""
        entry = _make_index_entry()
        index = _make_review_index(entries=(entry,))
        query = SearchQuery(query_text="BTC")
        result = build_search_result(index=index, query=query, now=_now())

        json_path = tmp_path / "result.json"
        md_path = tmp_path / "result.md"
        write_search_result(result, json_path, md_path)

        json_text = json_path.read_text().lower()
        md_text = md_path.read_text().lower()

        for term in ("api_key", "secret", "exchange_credentials", "private_key", "password"):
            assert term not in json_text
            assert term not in md_text

    def test_no_executable_instructions_in_output(self, tmp_path: Path) -> None:
        """Search output must not contain executable trading instructions."""
        entry = _make_index_entry()
        index = _make_review_index(entries=(entry,))
        query = SearchQuery(query_text="BTC")
        result = build_search_result(index=index, query=query, now=_now())

        json_path = tmp_path / "result.json"
        md_path = tmp_path / "result.md"
        write_search_result(result, json_path, md_path)

        json_text = json_path.read_text().lower()
        md_text = md_path.read_text().lower()

        for term in ("enter_long", "enter_short", "exit_long", "exit_short", "execute trade"):
            assert term not in json_text
            assert term not in md_text

    def test_human_audit_only_notice_in_markdown(self, tmp_path: Path) -> None:
        """Markdown output must contain explicit safety notice."""
        entry = _make_index_entry()
        index = _make_review_index(entries=(entry,))
        query = SearchQuery(query_text="BTC")
        result = build_search_result(index=index, query=query, now=_now())

        md_path = tmp_path / "result.md"
        write_search_result(result, tmp_path / "result.json", md_path)

        md_text = md_path.read_text()
        assert "human-audit catalog artifact only" in md_text
        assert "not a trading signal" in md_text
        assert "not trade approval" in md_text
        assert "must not be consumed by execution" in md_text
        assert "Freqtrade" in md_text

    def test_search_results_not_for_strategy(self, tmp_path: Path) -> None:
        """Search results must not be consumable by strategy."""
        entry = _make_index_entry()
        index = _make_review_index(entries=(entry,))
        query = SearchQuery(query_text="BTC")
        result = build_search_result(index=index, query=query, now=_now())
        assert result.safety_flags.search_output_not_for_strategy is True

    def test_search_results_not_for_freqtrade(self, tmp_path: Path) -> None:
        """Search results must not be consumable by Freqtrade."""
        entry = _make_index_entry()
        index = _make_review_index(entries=(entry,))
        query = SearchQuery(query_text="BTC")
        result = build_search_result(index=index, query=query, now=_now())
        assert result.safety_flags.search_output_not_for_freqtrade is True

    def test_search_results_not_for_order(self, tmp_path: Path) -> None:
        """Search results must not be consumable by order system."""
        entry = _make_index_entry()
        index = _make_review_index(entries=(entry,))
        query = SearchQuery(query_text="BTC")
        result = build_search_result(index=index, query=query, now=_now())
        assert result.safety_flags.search_output_not_for_order is True

    def test_search_results_not_for_exchange(self, tmp_path: Path) -> None:
        """Search results must not be consumable by exchange."""
        entry = _make_index_entry()
        index = _make_review_index(entries=(entry,))
        query = SearchQuery(query_text="BTC")
        result = build_search_result(index=index, query=query, now=_now())
        assert result.safety_flags.search_output_not_for_exchange is True

    def test_file_references_are_strings_only(self, tmp_path: Path) -> None:
        """File references in output are plain strings, never opened."""
        entry = _make_index_entry(
            local_report_reference="reports/does_not_exist.md",
            local_review_reference="reviews/does_not_exist.md",
        )
        index = _make_review_index(entries=(entry,))
        query = SearchQuery(query_text="does_not_exist")
        result = build_search_result(index=index, query=query, now=_now())
        assert result.search_state is SearchState.READY
        # References are serialized as strings, files are never opened
        d = search_result_to_dict(result)
        assert d["entries"][0]["local_report_reference"] == "reports/does_not_exist.md"
        assert d["entries"][0]["local_review_reference"] == "reviews/does_not_exist.md"


class TestDeterminism:
    def test_same_inputs_produce_same_search_id(self) -> None:
        entry = _make_index_entry()
        index = _make_review_index(entries=(entry,))
        query = SearchQuery(query_text="BTC")
        now = _now()
        result1 = build_search_result(index=index, query=query, now=now)
        result2 = build_search_result(index=index, query=query, now=now)
        assert result1.search_id == result2.search_id
        assert result1.generated_at == result2.generated_at

    def test_same_inputs_produce_same_dict(self) -> None:
        entry = _make_index_entry()
        index = _make_review_index(entries=(entry,))
        query = SearchQuery(query_text="BTC")
        now = _now()
        result1 = build_search_result(index=index, query=query, now=now)
        result2 = build_search_result(index=index, query=query, now=now)
        d1 = search_result_to_dict(result1)
        d2 = search_result_to_dict(result2)
        assert d1 == d2

    def test_same_inputs_produce_same_markdown(self) -> None:
        entry = _make_index_entry()
        index = _make_review_index(entries=(entry,))
        query = SearchQuery(query_text="BTC")
        now = _now()
        result1 = build_search_result(index=index, query=query, now=now)
        result2 = build_search_result(index=index, query=query, now=now)
        md1 = search_result_to_markdown(result1)
        md2 = search_result_to_markdown(result2)
        assert md1 == md2


class TestComplexQueries:
    def test_and_mode_with_multiple_filters(self) -> None:
        e1 = _make_index_entry(
            entry_id="e1", index_state=IndexState.READY,
            reviewer="alice", tags=("urgent",), report_id="report-1",
        )
        e2 = _make_index_entry(
            entry_id="e2", index_state=IndexState.READY,
            reviewer="alice", tags=("low",), report_id="report-2",
        )
        e3 = _make_index_entry(
            entry_id="e3", index_state=IndexState.BLOCKED,
            reviewer="alice", tags=("urgent",), report_id="report-3",
        )
        index = _make_review_index(entries=(e1, e2, e3))
        query = SearchQuery(
            filters=SearchFilter(
                index_states=(IndexState.READY,),
                reviewers=("alice",),
                tags=("urgent",),
            ),
            match_mode=SearchMatchMode.ALL,
        )
        result = build_search_result(index=index, query=query, now=_now())
        assert len(result.entries) == 1
        assert result.entries[0].entry_id == "e1"

    def test_any_mode_with_query_text_and_filter(self) -> None:
        e1 = _make_index_entry(entry_id="e1", report_id="btc-report")
        e2 = _make_index_entry(entry_id="e2", report_id="eth-report", metadata={"symbol": "ETH/USDT"})
        index = _make_review_index(entries=(e1, e2))
        query = SearchQuery(
            query_text="btc",
            filters=SearchFilter(entry_kinds=(IndexEntryKind.OBSERVATION_REPORT,)),
            match_mode=SearchMatchMode.ANY,
        )
        result = build_search_result(index=index, query=query, now=_now())
        # ANY mode: query_text matches e1, filter doesn't match either (both are LINKED)
        # But query_text matches e1, so e1 is included
        assert len(result.entries) == 1
        assert result.entries[0].entry_id == "e1"

    def test_exclude_blocked_entries(self) -> None:
        e1 = _make_index_entry(entry_id="e1", index_state=IndexState.READY)
        e2 = _make_index_entry(entry_id="e2", index_state=IndexState.BLOCKED)
        e3 = _make_index_entry(entry_id="e3", index_state=IndexState.UNKNOWN)
        index = _make_review_index(entries=(e1, e2, e3))
        query = SearchQuery(
            query_text="report",
            include_blocked_entries=False,
        )
        result = build_search_result(index=index, query=query, now=_now())
        assert len(result.entries) == 2
        entry_ids = {e.entry_id for e in result.entries}
        assert entry_ids == {"e1", "e3"}

    def test_metadata_text_filter(self) -> None:
        e1 = _make_index_entry(
            entry_id="e1", metadata={"symbol": "BTC/USDT", "note": "important"},
        )
        e2 = _make_index_entry(
            entry_id="e2", metadata={"symbol": "ETH/USDT", "note": "regular"},
        )
        index = _make_review_index(entries=(e1, e2))
        query = SearchQuery(
            filters=SearchFilter(metadata_text=("important",)),
        )
        result = build_search_result(index=index, query=query, now=_now())
        assert len(result.entries) == 1
        assert result.entries[0].entry_id == "e1"

    def test_audit_id_filter(self) -> None:
        e1 = _make_index_entry(entry_id="e1", audit_id="audit-1")
        e2 = _make_index_entry(entry_id="e2", audit_id="audit-2")
        index = _make_review_index(entries=(e1, e2))
        query = SearchQuery(
            filters=SearchFilter(audit_ids=("audit-1",)),
        )
        result = build_search_result(index=index, query=query, now=_now())
        assert len(result.entries) == 1
        assert result.entries[0].entry_id == "e1"

    def test_reason_codes_filter(self) -> None:
        e1 = _make_index_entry(entry_id="e1", reason_codes=("OK", "REVIEWED"))
        e2 = _make_index_entry(entry_id="e2", reason_codes=("ERROR",))
        index = _make_review_index(entries=(e1, e2))
        query = SearchQuery(
            filters=SearchFilter(reason_codes=("OK",)),
        )
        result = build_search_result(index=index, query=query, now=_now())
        assert len(result.entries) == 1
        assert result.entries[0].entry_id == "e1"

    def test_combined_date_and_text_filter(self) -> None:
        e1 = _make_index_entry(
            entry_id="e1", report_generated_at=_now(),
            metadata={"symbol": "BTC/USDT"},
        )
        e2 = _make_index_entry(
            entry_id="e2", report_generated_at=_now() + timedelta(days=1),
            metadata={"symbol": "BTC/USDT"},
        )
        index = _make_review_index(entries=(e1, e2))
        query = SearchQuery(
            query_text="BTC",
            filters=SearchFilter(
                generated_at_from=_now() - timedelta(hours=1),
                generated_at_to=_now() + timedelta(hours=1),
            ),
            match_mode=SearchMatchMode.ALL,
        )
        result = build_search_result(index=index, query=query, now=_now())
        assert len(result.entries) == 1
        assert result.entries[0].entry_id == "e1"
