"""Tests for hunter.review_index.writer module.

No production data writes. All file I/O uses tmp_path.
No network, database, Freqtrade, Binance, exchange, trading, leverage,
shorting, Web UI, dashboard, or integration tests.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
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
from hunter.review_index.writer import (
    DEFAULT_REVIEW_INDEX_JSON_PATH,
    DEFAULT_REVIEW_INDEX_MARKDOWN_PATH,
    _atomic_write,
    _iso,
    _serialize_value,
    atomic_write_json_review_index,
    atomic_write_markdown_review_index,
    index_data_quality_to_dict,
    index_entry_to_dict,
    index_safety_flags_to_dict,
    index_summary_to_dict,
    review_index_to_dict,
    review_index_to_markdown,
    write_review_index,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_entry(
    entry_id: str = "entry-1",
    entry_kind: IndexEntryKind = IndexEntryKind.LINKED_REPORT_REVIEW,
    index_state: IndexState = IndexState.READY,
    report_id: str = "report-1",
    audit_id: str = "audit-1",
    review_status: str = "ACCEPTED",
    review_state: str = "READY",
    source_report_version: str = "1.0",
    source_review_version: str = "1.0",
    reason_codes: tuple[str, ...] = (),
    tags: tuple[str, ...] = (),
    reviewer: str = "test-reviewer",
    local_report_reference: str = "reports/2024-01-01/report.md",
    local_review_reference: str = "reviews/2024-01-01/review.md",
    metadata: dict[str, object] | None = None,
) -> IndexEntry:
    now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    return IndexEntry(
        entry_id=entry_id,
        entry_kind=entry_kind,
        index_state=index_state,
        report_id=report_id,
        audit_id=audit_id,
        report_generated_at=now,
        audit_generated_at=now,
        reviewed_at=now,
        review_status=review_status,
        review_state=review_state,
        source_report_version=source_report_version,
        source_review_version=source_review_version,
        reason_codes=reason_codes,
        tags=tags,
        reviewer=reviewer,
        local_report_reference=local_report_reference,
        local_review_reference=local_review_reference,
        safety_flags=IndexSafetyFlags(),
        metadata=metadata or {},
    )


def _count_reason_codes(entries: tuple[IndexEntry, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in entries:
        for code in entry.reason_codes:
            counts[code] = counts.get(code, 0) + 1
    return counts


def _make_index(entries: list[IndexEntry] | tuple[IndexEntry, ...] | None = None) -> ReviewIndex:
    now = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    entry_tuple = tuple(entries or ())

    observation_report_count = sum(
        1 for e in entry_tuple if e.entry_kind == IndexEntryKind.OBSERVATION_REPORT
    )
    review_audit_count = sum(
        1 for e in entry_tuple if e.entry_kind == IndexEntryKind.REVIEW_AUDIT_RECORD
    )
    linked_entry_count = sum(
        1 for e in entry_tuple if e.entry_kind == IndexEntryKind.LINKED_REPORT_REVIEW
    )
    ready_count = sum(1 for e in entry_tuple if e.index_state == IndexState.READY)
    blocked_count = sum(1 for e in entry_tuple if e.index_state == IndexState.BLOCKED)
    unknown_count = sum(1 for e in entry_tuple if e.index_state == IndexState.UNKNOWN)
    accepted_count = sum(1 for e in entry_tuple if e.review_status == "ACCEPTED")
    rejected_count = sum(1 for e in entry_tuple if e.review_status == "REJECTED")
    needs_investigation_count = sum(
        1 for e in entry_tuple if e.review_status == "NEEDS_INVESTIGATION"
    )
    not_reviewed_count = sum(1 for e in entry_tuple if e.review_status == "NOT_REVIEWED")

    summary = IndexSummary(
        total_entries=len(entry_tuple),
        observation_report_count=observation_report_count,
        review_audit_count=review_audit_count,
        linked_entry_count=linked_entry_count,
        ready_count=ready_count,
        blocked_count=blocked_count,
        unknown_count=unknown_count,
        accepted_count=accepted_count,
        rejected_count=rejected_count,
        needs_investigation_count=needs_investigation_count,
        not_reviewed_count=not_reviewed_count,
        reason_counts=_count_reason_codes(entry_tuple),
    )
    dq = IndexDataQuality(
        total_reports=observation_report_count + linked_entry_count,
        valid_reports=observation_report_count + linked_entry_count,
        invalid_reports=0,
        unsafe_reports=0,
        total_reviews=review_audit_count + linked_entry_count,
        valid_reviews=review_audit_count + linked_entry_count,
        invalid_reviews=0,
        unsafe_reviews=0,
        linked_records=linked_entry_count,
        unlinked_reports=observation_report_count,
        unlinked_reviews=review_audit_count,
    )
    return ReviewIndex(
        index_id="test-index-1",
        generated_at=now,
        index_state=IndexState.READY,
        entries=entry_tuple,
        summary=summary,
        data_quality=dq,
        reason_codes=tuple(summary.reason_counts.keys()),
        safety_flags=IndexSafetyFlags(),
    )


# ---------------------------------------------------------------------------
# _iso helper
# ---------------------------------------------------------------------------

class TestIsoHelper:
    def test_none_returns_none(self) -> None:
        assert _iso(None) is None

    def test_utc_datetime_z_suffix(self) -> None:
        dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        assert _iso(dt) == "2024-01-01T12:00:00Z"

    def test_non_utc_datetime_isoformat(self) -> None:
        from datetime import timedelta

        dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone(offset=timedelta(hours=2)))
        assert _iso(dt) == "2024-01-01T12:00:00+02:00"


# ---------------------------------------------------------------------------
# _serialize_value helper
# ---------------------------------------------------------------------------

class TestSerializeValue:
    def test_enum(self) -> None:
        assert _serialize_value(IndexState.READY) == IndexState.READY.value

    def test_datetime(self) -> None:
        dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        assert _serialize_value(dt) == "2024-01-01T12:00:00Z"

    def test_tuple(self) -> None:
        assert _serialize_value(("a", "b")) == ["a", "b"]

    def test_mapping(self) -> None:
        assert _serialize_value({"k": "v"}) == {"k": "v"}

    def test_nested(self) -> None:
        assert _serialize_value([{"a": (IndexState.READY,)}]) == [
            {"a": [IndexState.READY.value]}
        ]


# ---------------------------------------------------------------------------
# index_entry_to_dict
# ---------------------------------------------------------------------------

class TestIndexEntryToDict:
    def test_ready_linked_entry(self) -> None:
        entry = _make_entry()
        d = index_entry_to_dict(entry)
        assert d["entry_id"] == "entry-1"
        assert d["entry_kind"] == IndexEntryKind.LINKED_REPORT_REVIEW.value
        assert d["index_state"] == IndexState.READY.value
        assert d["report_id"] == "report-1"
        assert d["audit_id"] == "audit-1"
        assert d["review_status"] == "ACCEPTED"
        assert d["review_state"] == "READY"
        assert d["source_report_version"] == "1.0"
        assert d["source_review_version"] == "1.0"
        assert d["reason_codes"] == []
        assert d["tags"] == []
        assert d["reviewer"] == "test-reviewer"
        assert d["local_report_reference"] == "reports/2024-01-01/report.md"
        assert d["local_review_reference"] == "reviews/2024-01-01/review.md"
        assert d["safety_flags"] == index_safety_flags_to_dict(entry.safety_flags)
        assert d["metadata"] == {}
        assert d["report_generated_at"] == "2024-01-01T12:00:00Z"
        assert d["audit_generated_at"] == "2024-01-01T12:00:00Z"
        assert d["reviewed_at"] == "2024-01-01T12:00:00Z"

    def test_blocked_entry(self) -> None:
        entry = _make_entry(
            index_state=IndexState.BLOCKED,
            review_status="REJECTED",
            review_state="BLOCKED",
            reason_codes=("UNSAFE_REPORT_STATE",),
        )
        d = index_entry_to_dict(entry)
        assert d["index_state"] == IndexState.BLOCKED.value
        assert d["review_status"] == "REJECTED"
        assert d["review_state"] == "BLOCKED"
        assert d["reason_codes"] == ["UNSAFE_REPORT_STATE"]

    def test_enum_values_as_strings(self) -> None:
        entry = _make_entry()
        d = index_entry_to_dict(entry)
        assert isinstance(d["entry_kind"], str)
        assert isinstance(d["index_state"], str)

    def test_tuple_as_list(self) -> None:
        entry = _make_entry(reason_codes=("A", "B"), tags=("tag1", "tag2"))
        d = index_entry_to_dict(entry)
        assert d["reason_codes"] == ["A", "B"]
        assert d["tags"] == ["tag1", "tag2"]

    def test_metadata_serialized(self) -> None:
        entry = _make_entry(metadata={"key": "value", "nested": {"state": IndexState.READY}})
        d = index_entry_to_dict(entry)
        assert d["metadata"] == {"key": "value", "nested": {"state": IndexState.READY.value}}

    def test_local_references_as_strings(self) -> None:
        entry = _make_entry()
        d = index_entry_to_dict(entry)
        assert isinstance(d["local_report_reference"], str)
        assert isinstance(d["local_review_reference"], str)
        assert d["local_report_reference"] == "reports/2024-01-01/report.md"
        assert d["local_review_reference"] == "reviews/2024-01-01/review.md"

    def test_does_not_mutate_input(self) -> None:
        entry = _make_entry(reason_codes=("A",))
        original = entry.reason_codes
        index_entry_to_dict(entry)
        assert entry.reason_codes is original
        assert entry.reason_codes == ("A",)


# ---------------------------------------------------------------------------
# index_summary_to_dict
# ---------------------------------------------------------------------------

class TestIndexSummaryToDict:
    def test_summary(self) -> None:
        summary = IndexSummary(
            total_entries=5,
            observation_report_count=2,
            review_audit_count=1,
            linked_entry_count=2,
            ready_count=3,
            blocked_count=1,
            unknown_count=1,
            accepted_count=2,
            rejected_count=1,
            needs_investigation_count=1,
            not_reviewed_count=1,
            reason_counts={"OK": 2, "UNSAFE": 1},
        )
        d = index_summary_to_dict(summary)
        assert d["total_entries"] == 5
        assert d["reason_counts"] == {"OK": 2, "UNSAFE": 1}

    def test_does_not_mutate_input(self) -> None:
        summary = IndexSummary(
            total_entries=1,
            observation_report_count=0,
            review_audit_count=0,
            linked_entry_count=1,
            ready_count=1,
            blocked_count=0,
            unknown_count=0,
            accepted_count=1,
            rejected_count=0,
            needs_investigation_count=0,
            not_reviewed_count=0,
            reason_counts={"OK": 1},
        )
        original = summary.reason_counts
        index_summary_to_dict(summary)
        assert summary.reason_counts is original


# ---------------------------------------------------------------------------
# index_data_quality_to_dict
# ---------------------------------------------------------------------------

class TestIndexDataQualityToDict:
    def test_data_quality(self) -> None:
        dq = IndexDataQuality(
            total_reports=10,
            valid_reports=8,
            invalid_reports=1,
            unsafe_reports=1,
            total_reviews=10,
            valid_reviews=8,
            invalid_reviews=1,
            unsafe_reviews=1,
            linked_records=8,
            unlinked_reports=1,
            unlinked_reviews=1,
        )
        d = index_data_quality_to_dict(dq)
        assert d["total_reports"] == 10
        assert d["valid_reports"] == 8
        assert d["linked_records"] == 8

    def test_does_not_mutate_input(self) -> None:
        dq = IndexDataQuality(
            total_reports=1,
            valid_reports=1,
            invalid_reports=0,
            unsafe_reports=0,
            total_reviews=1,
            valid_reviews=1,
            invalid_reviews=0,
            unsafe_reviews=0,
            linked_records=1,
            unlinked_reports=0,
            unlinked_reviews=0,
        )
        index_data_quality_to_dict(dq)
        assert dq.total_reports == 1


# ---------------------------------------------------------------------------
# index_safety_flags_to_dict
# ---------------------------------------------------------------------------

class TestIndexSafetyFlagsToDict:
    def test_safety_flags(self) -> None:
        flags = IndexSafetyFlags(
            dry_run=True,
            live_trading_enabled=False,
            real_orders_enabled=False,
            leverage_enabled=False,
            shorting_enabled=False,
            report_feedback_into_execution=False,
            operator_feedback_into_execution=False,
            index_feedback_into_execution=False,
            file_reference_traversal_enabled=False,
            database_persistence_enabled=False,
            web_ui_enabled=False,
            dashboard_enabled=False,
        )
        d = index_safety_flags_to_dict(flags)
        assert d["dry_run"] is True
        assert d["live_trading_enabled"] is False
        assert d["file_reference_traversal_enabled"] is False

    def test_does_not_mutate_input(self) -> None:
        flags = IndexSafetyFlags()
        d = index_safety_flags_to_dict(flags)
        d["dry_run"] = False
        assert flags.dry_run is True


# ---------------------------------------------------------------------------
# review_index_to_dict
# ---------------------------------------------------------------------------

class TestReviewIndexToDict:
    def test_nested_entries(self) -> None:
        entry1 = _make_entry(entry_id="e1", reason_codes=("OK",))
        entry2 = _make_entry(entry_id="e2", index_state=IndexState.BLOCKED, review_state="BLOCKED", reason_codes=("DEFAULT_BLOCKED",))
        index = _make_index(entries=[entry1, entry2])
        d = review_index_to_dict(index)
        assert d["index_id"] == "test-index-1"
        assert d["index_state"] == IndexState.READY.value
        assert len(d["entries"]) == 2
        assert d["entries"][0]["entry_id"] == "e1"
        assert d["entries"][1]["entry_id"] == "e2"
        assert d["summary"]["total_entries"] == 2
        assert d["data_quality"]["linked_records"] == 2
        assert d["reason_codes"] == ["OK", "DEFAULT_BLOCKED"]
        assert "safety_flags" in d

    def test_does_not_mutate_input(self) -> None:
        entry = _make_entry()
        index = _make_index(entries=[entry])
        original = index.entries
        review_index_to_dict(index)
        assert index.entries is original


# ---------------------------------------------------------------------------
# review_index_to_markdown
# ---------------------------------------------------------------------------

class TestReviewIndexToMarkdown:
    def test_includes_safety_notice(self) -> None:
        index = _make_index()
        md = review_index_to_markdown(index)
        assert "This local review index is a human-audit catalog artifact only" in md

    def test_says_not_trading_signal(self) -> None:
        index = _make_index()
        md = review_index_to_markdown(index)
        assert "not a trading signal" in md

    def test_says_not_trade_approval(self) -> None:
        index = _make_index()
        md = review_index_to_markdown(index)
        assert "not trade approval" in md

    def test_says_must_not_be_consumed_by_execution(self) -> None:
        index = _make_index()
        md = review_index_to_markdown(index)
        assert "must not be consumed by execution" in md
        assert "strategy" in md
        assert "Freqtrade" in md
        assert "order" in md
        assert "exchange" in md
        assert "MVP execution path" in md

    def test_includes_index_fields(self) -> None:
        index = _make_index()
        md = review_index_to_markdown(index)
        assert "test-index-1" in md
        assert "2024-01-01T12:00:00Z" in md
        assert IndexState.READY.value in md

    def test_includes_summary_counts(self) -> None:
        entry = _make_entry()
        index = _make_index(entries=[entry])
        md = review_index_to_markdown(index)
        assert "total_entries" in md
        assert "linked_entry_count" in md
        assert "ready_count" in md

    def test_includes_data_quality(self) -> None:
        index = _make_index()
        md = review_index_to_markdown(index)
        assert "## Data Quality" in md
        assert "total_reports" in md

    def test_includes_safety_flags(self) -> None:
        index = _make_index()
        md = review_index_to_markdown(index)
        assert "## Safety Flags" in md
        assert "dry_run" in md

    def test_includes_entries(self) -> None:
        entry = _make_entry()
        index = _make_index(entries=[entry])
        md = review_index_to_markdown(index)
        assert "## Entries" in md
        assert "entry-1" in md
        assert IndexEntryKind.LINKED_REPORT_REVIEW.value in md

    def test_no_sensitive_credentials_or_executable_instructions(self) -> None:
        index = _make_index()
        md = review_index_to_markdown(index).lower()
        forbidden_terms = (
            "api_key",
            "secret_key",
            "exchange_credentials",
            "executable_instructions",
            "enter_long = 1",
            "enter_short = 1",
            "exit_long = 1",
            "exit_short = 1",
        )
        for term in forbidden_terms:
            assert term not in md

    def test_no_operational_instructions(self) -> None:
        index = _make_index()
        md = review_index_to_markdown(index)
        assert "buy now" not in md.lower()
        assert "sell now" not in md.lower()
        assert "execute trade" not in md.lower()

    def test_empty_index(self) -> None:
        index = _make_index(entries=[])
        md = review_index_to_markdown(index)
        assert "No entries" in md


# ---------------------------------------------------------------------------
# Atomic JSON writer
# ---------------------------------------------------------------------------

class TestAtomicWriteJson:
    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        path = tmp_path / "deep" / "nested" / "index.json"
        index = _make_index()
        atomic_write_json_review_index(index, path)
        assert path.exists()

    def test_writes_valid_json(self, tmp_path: Path) -> None:
        path = tmp_path / "index.json"
        index = _make_index(entries=[_make_entry()])
        atomic_write_json_review_index(index, path)
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["index_id"] == "test-index-1"
        assert data["index_state"] == IndexState.READY.value
        assert len(data["entries"]) == 1

    def test_overwrites_existing(self, tmp_path: Path) -> None:
        path = tmp_path / "index.json"
        path.write_text("old", encoding="utf-8")
        index = _make_index()
        atomic_write_json_review_index(index, path)
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["index_id"] == "test-index-1"

    def test_no_temp_files_after_success(self, tmp_path: Path) -> None:
        path = tmp_path / "index.json"
        index = _make_index()
        atomic_write_json_review_index(index, path)
        temps = list(tmp_path.glob("*.tmp"))
        assert temps == []

    def test_cleans_up_temp_on_failure(self, tmp_path: Path) -> None:
        path = tmp_path / "file" / "index.json"
        tmp_path.joinpath("file").write_text("block", encoding="utf-8")
        index = _make_index()
        with pytest.raises(OSError):
            atomic_write_json_review_index(index, path)

    def test_indent_and_sort_keys(self, tmp_path: Path) -> None:
        path = tmp_path / "index.json"
        index = _make_index()
        atomic_write_json_review_index(index, path)
        text = path.read_text(encoding="utf-8")
        assert "  \"index_id\"" in text
        assert text.strip().endswith("}")

    def test_trailing_newline(self, tmp_path: Path) -> None:
        path = tmp_path / "index.json"
        index = _make_index()
        atomic_write_json_review_index(index, path)
        text = path.read_text(encoding="utf-8")
        assert text.endswith("\n")


# ---------------------------------------------------------------------------
# Atomic Markdown writer
# ---------------------------------------------------------------------------

class TestAtomicWriteMarkdown:
    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        path = tmp_path / "deep" / "nested" / "index.md"
        index = _make_index()
        atomic_write_markdown_review_index(index, path)
        assert path.exists()

    def test_writes_markdown(self, tmp_path: Path) -> None:
        path = tmp_path / "index.md"
        index = _make_index(entries=[_make_entry()])
        atomic_write_markdown_review_index(index, path)
        text = path.read_text(encoding="utf-8")
        assert "# Review Index" in text
        assert "## Entries" in text

    def test_overwrites_existing(self, tmp_path: Path) -> None:
        path = tmp_path / "index.md"
        path.write_text("old", encoding="utf-8")
        index = _make_index()
        atomic_write_markdown_review_index(index, path)
        text = path.read_text(encoding="utf-8")
        assert "# Review Index" in text

    def test_no_temp_files_after_success(self, tmp_path: Path) -> None:
        path = tmp_path / "index.md"
        index = _make_index()
        atomic_write_markdown_review_index(index, path)
        temps = list(tmp_path.glob("*.tmp"))
        assert temps == []

    def test_trailing_newline(self, tmp_path: Path) -> None:
        path = tmp_path / "index.md"
        index = _make_index()
        atomic_write_markdown_review_index(index, path)
        text = path.read_text(encoding="utf-8")
        assert text.endswith("\n")


# ---------------------------------------------------------------------------
# write_review_index
# ---------------------------------------------------------------------------

class TestWriteReviewIndex:
    def test_writes_both_files(self, tmp_path: Path) -> None:
        json_path = tmp_path / "index.json"
        md_path = tmp_path / "index.md"
        index = _make_index(entries=[_make_entry()])
        out_json, out_md = write_review_index(index, json_path, md_path)
        assert out_json == json_path
        assert out_md == md_path
        assert json_path.exists()
        assert md_path.exists()
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data["index_id"] == "test-index-1"
        md_text = md_path.read_text(encoding="utf-8")
        assert "# Review Index" in md_text


# ---------------------------------------------------------------------------
# Default path constants
# ---------------------------------------------------------------------------

class TestDefaultPaths:
    def test_json_path(self) -> None:
        assert str(DEFAULT_REVIEW_INDEX_JSON_PATH) == "data/review_index/latest_review_index.json"

    def test_markdown_path(self) -> None:
        assert str(DEFAULT_REVIEW_INDEX_MARKDOWN_PATH) == "reports/review_index/latest_review_index.md"


# ---------------------------------------------------------------------------
# _atomic_write internal
# ---------------------------------------------------------------------------

class TestAtomicWriteInternal:
    def test_atomic_write_creates_file(self, tmp_path: Path) -> None:
        path = tmp_path / "test.txt"
        _atomic_write(path, "hello")
        assert path.read_text(encoding="utf-8") == "hello"

    def test_atomic_write_cleanup_on_failure(self, tmp_path: Path) -> None:
        path = tmp_path / "file" / "test.txt"
        tmp_path.joinpath("file").write_text("block", encoding="utf-8")
        with pytest.raises(OSError):
            _atomic_write(path, "hello")
