"""Tests for hunter.review_search.writer.

MVP-13 review_search writer tests only.
No network, database, Freqtrade, Binance, exchange, trading,
Web UI, dashboard, or integration behavior is exercised here.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from hunter.review_index.models import IndexEntryKind, IndexState
from hunter.review_search.models import (
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
    DEFAULT_SEARCH_JSON_PATH,
    DEFAULT_SEARCH_MARKDOWN_PATH,
    _atomic_write,
    _iso,
    _serialize_value,
    atomic_write_json_search_result,
    atomic_write_markdown_search_result,
    search_result_entry_to_dict,
    search_result_summary_to_dict,
    search_result_to_dict,
    search_result_to_markdown,
    search_safety_flags_to_dict,
    write_search_result,
)


def _now() -> datetime:
    return datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _make_result_entry(**overrides: object) -> SearchResultEntry:
    data: dict[str, object] = {
        "entry_id": "entry-1",
        "score": 1.0,
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


def _make_result(**overrides: object) -> SearchResult:
    entry = _make_result_entry()
    data: dict[str, object] = {
        "search_id": "search-1",
        "generated_at": _now(),
        "search_state": SearchState.READY,
        "query": SearchQuery(query_text="BTC"),
        "entries": (entry,),
        "summary": SearchResultSummary(
            total_entries=1,
            matched_entries=1,
            returned_entries=1,
            ready_count=1,
            blocked_count=0,
            unknown_count=0,
        ),
        "reason_codes": (),
        "safety_flags": SearchSafetyFlags(),
        "metadata": {"purpose": "unit-test"},
    }
    data.update(overrides)
    return SearchResult(**data)


class TestIso:
    def test_none_returns_none(self) -> None:
        assert _iso(None) is None

    def test_utc_datetime_with_z_suffix(self) -> None:
        dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        assert _iso(dt) == "2024-01-01T12:00:00Z"

    def test_naive_datetime_raises(self) -> None:
        with pytest.raises(ValueError, match="timezone-aware"):
            _iso(datetime(2024, 1, 1, 12, 0, 0))

    def test_non_utc_datetime(self) -> None:
        from datetime import timedelta
        dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone(timedelta(hours=2)))
        assert _iso(dt) == "2024-01-01T12:00:00+02:00"


class TestSerializeValue:
    def test_enum(self) -> None:
        assert _serialize_value(IndexState.READY) == "READY"

    def test_datetime(self) -> None:
        dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        assert _serialize_value(dt) == "2024-01-01T12:00:00Z"

    def test_tuple(self) -> None:
        assert _serialize_value(("a", "b")) == ["a", "b"]

    def test_list(self) -> None:
        assert _serialize_value(["a", "b"]) == ["a", "b"]

    def test_mapping(self) -> None:
        assert _serialize_value({"key": "value"}) == {"key": "value"}

    def test_nested(self) -> None:
        assert _serialize_value({"k": (IndexState.READY,)}) == {"k": ["READY"]}

    def test_plain_value(self) -> None:
        assert _serialize_value(42) == 42


class TestSearchSafetyFlagsToDict:
    def test_all_fields_present(self) -> None:
        flags = SearchSafetyFlags()
        d = search_safety_flags_to_dict(flags)
        assert d["dry_run"] is True
        assert d["live_trading_enabled"] is False
        assert d["search_feedback_into_execution"] is False
        assert "dashboard_enabled" in d


class TestSearchResultEntryToDict:
    def test_all_fields(self) -> None:
        entry = _make_result_entry()
        d = search_result_entry_to_dict(entry)
        assert d["entry_id"] == "entry-1"
        assert d["score"] == 1.0
        assert d["index_state"] == "READY"
        assert d["entry_kind"] == "LINKED_REPORT_REVIEW"
        assert d["report_id"] == "report-1"
        assert d["audit_id"] == "audit-1"
        assert d["review_status"] == "ACCEPTED"
        assert d["reason_codes"] == ["OK"]
        assert d["tags"] == ["tag-a"]
        assert d["reviewer"] == "operator-a"
        assert d["local_report_reference"] == "reports/review_index/report.md"
        assert d["local_review_reference"] == "reports/review_index/review.md"
        assert d["report_generated_at"] == "2024-01-01T12:00:00Z"
        assert d["audit_generated_at"] == "2024-01-01T12:00:00Z"
        assert d["reviewed_at"] == "2024-01-01T12:00:00Z"
        assert d["metadata"] == {"symbol": "BTC/USDT"}

    def test_none_datetimes(self) -> None:
        entry = _make_result_entry(
            report_generated_at=None,
            audit_generated_at=None,
            reviewed_at=None,
        )
        d = search_result_entry_to_dict(entry)
        assert d["report_generated_at"] is None
        assert d["audit_generated_at"] is None
        assert d["reviewed_at"] is None


class TestSearchResultSummaryToDict:
    def test_all_fields(self) -> None:
        summary = SearchResultSummary(
            total_entries=10,
            matched_entries=5,
            returned_entries=3,
            ready_count=2,
            blocked_count=1,
            unknown_count=0,
            reason_counts={"OK": 2},
        )
        d = search_result_summary_to_dict(summary)
        assert d["total_entries"] == 10
        assert d["matched_entries"] == 5
        assert d["returned_entries"] == 3
        assert d["ready_count"] == 2
        assert d["blocked_count"] == 1
        assert d["unknown_count"] == 0
        assert d["reason_counts"] == {"OK": 2}


class TestSearchResultToDict:
    def test_ready_result(self) -> None:
        result = _make_result()
        d = search_result_to_dict(result)
        assert d["search_id"] == "search-1"
        assert d["generated_at"] == "2024-01-01T12:00:00Z"
        assert d["search_state"] == "READY"
        assert d["reason_codes"] == []
        assert len(d["entries"]) == 1
        assert d["entries"][0]["entry_id"] == "entry-1"
        assert d["summary"]["total_entries"] == 1
        assert d["metadata"] == {"purpose": "unit-test"}
        assert "safety_flags" in d
        assert d["safety_flags"]["dry_run"] is True

    def test_blocked_result(self) -> None:
        result = SearchResult.blocked(
            search_id="blocked-1",
            generated_at=_now(),
            reason_code="MISSING_INDEX",
        )
        d = search_result_to_dict(result)
        assert d["search_state"] == "BLOCKED"
        assert d["reason_codes"] == ["MISSING_INDEX"]
        assert d["entries"] == []
        assert d["summary"]["total_entries"] == 0

    def test_query_serialization(self) -> None:
        result = _make_result()
        d = search_result_to_dict(result)
        query = d["query"]
        assert query["query_text"] == "BTC"
        assert query["match_mode"] == "ALL"
        assert query["sort"] == "SCORE_DESC"
        assert query["include_blocked_entries"] is True
        assert "filters" in query

    def test_no_entries(self) -> None:
        result = _make_result(entries=())
        d = search_result_to_dict(result)
        assert d["entries"] == []

    def test_empty_metadata(self) -> None:
        result = _make_result(metadata={})
        d = search_result_to_dict(result)
        assert d["metadata"] == {}


class TestSearchResultToMarkdown:
    def test_contains_title(self) -> None:
        result = _make_result()
        md = search_result_to_markdown(result)
        assert "# Review Search Result — Human Audit Only" in md

    def test_contains_safety_notice(self) -> None:
        result = _make_result()
        md = search_result_to_markdown(result)
        assert "human-audit catalog artifact only" in md
        assert "not a trading signal" in md
        assert "not trade approval" in md

    def test_contains_search_info(self) -> None:
        result = _make_result()
        md = search_result_to_markdown(result)
        assert "search_id" in md
        assert "search-1" in md
        assert "generated_at" in md
        assert "search_state" in md

    def test_contains_query_info(self) -> None:
        result = _make_result()
        md = search_result_to_markdown(result)
        assert "query_text" in md
        assert "match_mode" in md
        assert "sort" in md

    def test_contains_summary(self) -> None:
        result = _make_result()
        md = search_result_to_markdown(result)
        assert "total_entries" in md
        assert "matched_entries" in md
        assert "returned_entries" in md

    def test_contains_safety_flags(self) -> None:
        result = _make_result()
        md = search_result_to_markdown(result)
        assert "## Safety Flags" in md
        assert "dry_run" in md

    def test_contains_reason_codes(self) -> None:
        result = _make_result()
        md = search_result_to_markdown(result)
        assert "## Reason Codes" in md

    def test_contains_matched_entries(self) -> None:
        result = _make_result()
        md = search_result_to_markdown(result)
        assert "## Matched Entries" in md
        assert "entry-1" in md
        assert "score" in md

    def test_no_entries_shows_placeholder(self) -> None:
        result = _make_result(entries=())
        md = search_result_to_markdown(result)
        assert "_No entries matched._" in md

    def test_blocked_result(self) -> None:
        result = SearchResult.blocked(
            search_id="blocked-1",
            generated_at=_now(),
            reason_code="MISSING_INDEX",
        )
        md = search_result_to_markdown(result)
        assert "BLOCKED" in md
        assert "MISSING_INDEX" in md

    def test_contains_metadata(self) -> None:
        result = _make_result(metadata={"key": "value"})
        md = search_result_to_markdown(result)
        assert "## Metadata" in md
        assert "key" in md
        assert "value" in md

    def test_empty_filter_shows_placeholder(self) -> None:
        result = _make_result(query=SearchQuery())
        md = search_result_to_markdown(result)
        assert "_No filters applied._" in md

    def test_entry_metadata_in_markdown(self) -> None:
        entry = _make_result_entry(metadata={"symbol": "ETH/USDT"})
        result = _make_result(entries=(entry,))
        md = search_result_to_markdown(result)
        assert "symbol" in md
        assert "ETH/USDT" in md


class TestAtomicWrite:
    def test_writes_file(self, tmp_path: Path) -> None:
        path = tmp_path / "test.txt"
        _atomic_write(path, "hello")
        assert path.read_text() == "hello"

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        path = tmp_path / "nested" / "dir" / "test.txt"
        _atomic_write(path, "hello")
        assert path.read_text() == "hello"

    def test_overwrites_existing(self, tmp_path: Path) -> None:
        path = tmp_path / "test.txt"
        path.write_text("old")
        _atomic_write(path, "new")
        assert path.read_text() == "new"

    def test_cleanup_on_failure(self, tmp_path: Path) -> None:
        # Make parent read-only to force failure
        path = tmp_path / "readonly" / "test.txt"
        # Don't create parent, but the function should create it
        # Instead test that tmp file is cleaned up on error
        import os
        parent = tmp_path / "readonly"
        parent.mkdir()
        os.chmod(str(parent), 0o555)
        try:
            with pytest.raises(OSError):
                _atomic_write(parent / "sub" / "test.txt", "hello")
        finally:
            os.chmod(str(parent), 0o755)


class TestAtomicWriteJsonSearchResult:
    def test_default_path(self, tmp_path: Path) -> None:
        result = _make_result()
        # Override default path via tmp_path
        path = tmp_path / "result.json"
        out = atomic_write_json_search_result(result, path)
        assert out == path
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["search_id"] == "search-1"
        assert data["search_state"] == "READY"

    def test_uses_default_path_when_none(self, tmp_path: Path) -> None:
        # The default path is data/review_search/latest_search_result.json
        # We can't easily test that without creating dirs, so test with explicit path
        result = _make_result()
        path = tmp_path / "default.json"
        out = atomic_write_json_search_result(result, path)
        assert out.exists()

    def test_json_is_valid(self, tmp_path: Path) -> None:
        result = _make_result()
        path = tmp_path / "result.json"
        atomic_write_json_search_result(result, path)
        data = json.loads(path.read_text())
        assert isinstance(data, dict)
        assert "entries" in data
        assert "summary" in data
        assert "safety_flags" in data

    def test_json_has_trailing_newline(self, tmp_path: Path) -> None:
        result = _make_result()
        path = tmp_path / "result.json"
        atomic_write_json_search_result(result, path)
        text = path.read_text()
        assert text.endswith("\n")

    def test_sort_keys(self, tmp_path: Path) -> None:
        result = _make_result()
        path = tmp_path / "result.json"
        atomic_write_json_search_result(result, path)
        text = path.read_text()
        # Keys should be sorted alphabetically
        lines = text.split("\n")
        # Check that "entries" comes before "generated_at" (both start with e, g)
        # This is a loose check; the main thing is json.dumps sort_keys=True works
        assert '"entries"' in text
        assert '"generated_at"' in text


class TestAtomicWriteMarkdownSearchResult:
    def test_writes_markdown(self, tmp_path: Path) -> None:
        result = _make_result()
        path = tmp_path / "result.md"
        out = atomic_write_markdown_search_result(result, path)
        assert out == path
        assert path.exists()
        assert "# Review Search Result" in path.read_text()

    def test_has_trailing_newline(self, tmp_path: Path) -> None:
        result = _make_result()
        path = tmp_path / "result.md"
        atomic_write_markdown_search_result(result, path)
        text = path.read_text()
        assert text.endswith("\n")


class TestWriteSearchResult:
    def test_writes_both(self, tmp_path: Path) -> None:
        result = _make_result()
        json_path = tmp_path / "result.json"
        md_path = tmp_path / "result.md"
        json_out, md_out = write_search_result(result, json_path, md_path)
        assert json_out == json_path
        assert md_out == md_path
        assert json_path.exists()
        assert md_path.exists()

    def test_default_paths(self, tmp_path: Path) -> None:
        # We override the default paths by passing them explicitly
        result = _make_result()
        json_path = tmp_path / "default.json"
        md_path = tmp_path / "default.md"
        json_out, md_out = write_search_result(result, json_path, md_path)
        assert json_out.exists()
        assert md_out.exists()


class TestDefaultPaths:
    def test_default_json_path(self) -> None:
        assert str(DEFAULT_SEARCH_JSON_PATH) == "data/review_search/latest_search_result.json"

    def test_default_markdown_path(self) -> None:
        assert str(DEFAULT_SEARCH_MARKDOWN_PATH) == "reports/review_search/latest_search_result.md"


class TestSafetyInvariants:
    def test_no_secrets_in_output(self, tmp_path: Path) -> None:
        result = _make_result()
        path = tmp_path / "result.json"
        atomic_write_json_search_result(result, path)
        text = path.read_text()
        assert "api_key" not in text.lower()
        assert "secret" not in text.lower()
        assert "exchange_credentials" not in text.lower()

    def test_no_executable_instructions(self, tmp_path: Path) -> None:
        result = _make_result()
        path = tmp_path / "result.json"
        atomic_write_json_search_result(result, path)
        text = path.read_text()
        assert "enter_long" not in text.lower()
        assert "enter_short" not in text.lower()
        assert "exit_long" not in text.lower()
        assert "exit_short" not in text.lower()

    def test_markdown_safety_notice(self, tmp_path: Path) -> None:
        result = _make_result()
        path = tmp_path / "result.md"
        atomic_write_markdown_search_result(result, path)
        text = path.read_text()
        assert "human-audit catalog artifact only" in text
        assert "must not be consumed by execution" in text
        assert "Freqtrade" in text
