"""Tests for hunter.chronicle.writer."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hunter.chronicle.models import (
    ArtifactType,
    ChronicleDataQuality,
    ChronicleEntry,
    ChronicleSafetyFlags,
    ChronicleSummary,
    ResearchChronicle,
)
from hunter.chronicle.writer import (
    DEFAULT_CHRONICLE_JSON_PATH,
    DEFAULT_CHRONICLE_MARKDOWN_PATH,
    _atomic_write,
    _iso,
    _serialize_value,
    atomic_write_json_research_chronicle,
    atomic_write_markdown_research_chronicle,
    chronicle_data_quality_to_dict,
    chronicle_entry_to_dict,
    chronicle_safety_flags_to_dict,
    chronicle_summary_to_dict,
    research_chronicle_to_dict,
    research_chronicle_to_markdown,
    write_research_chronicle,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class TestIso:
    """Tests for _iso helper."""

    def test_aware_datetime(self) -> None:
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        assert _iso(dt) == "2025-01-01T12:00:00+00:00"

    def test_naive_datetime_raises(self) -> None:
        with pytest.raises(ValueError, match="timezone-aware"):
            _iso(datetime(2025, 1, 1, 12, 0, 0))

    def test_non_utc_offset(self) -> None:
        from datetime import timedelta
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone(timedelta(hours=5)))
        assert _iso(dt) == "2025-01-01T07:00:00+00:00"


class TestSerializeValue:
    """Tests for _serialize_value helper."""

    def test_enum(self) -> None:
        assert _serialize_value(ArtifactType.OBSERVATION) == "observation"

    def test_datetime(self) -> None:
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        assert _serialize_value(dt) == "2025-01-01T12:00:00+00:00"

    def test_tuple(self) -> None:
        assert _serialize_value(("a", "b")) == ["a", "b"]

    def test_list(self) -> None:
        assert _serialize_value(["x", "y"]) == ["x", "y"]

    def test_mapping(self) -> None:
        assert _serialize_value({"k": "v"}) == {"k": "v"}

    def test_nested(self) -> None:
        data = {"a": (ArtifactType.REVIEW, datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc))}
        result = _serialize_value(data)
        assert result == {"a": ["review", "2025-01-01T12:00:00+00:00"]}

    def test_primitive(self) -> None:
        assert _serialize_value(42) == 42
        assert _serialize_value("hello") == "hello"
        assert _serialize_value(True) is True


# ---------------------------------------------------------------------------
# Dict serialization
# ---------------------------------------------------------------------------


class TestChronicleSafetyFlagsToDict:
    """Tests for chronicle_safety_flags_to_dict."""

    def test_all_fields_present(self) -> None:
        flags = ChronicleSafetyFlags()
        d = chronicle_safety_flags_to_dict(flags)
        assert d["dry_run"] is True
        assert d["live_trading_enabled"] is False
        assert d["leverage_enabled"] is False
        assert d["shorting_enabled"] is False
        assert d["chronicle_output_is_human_audit_only"] is True
        assert d["chronicle_output_not_trading_signal"] is True
        assert d["chronicle_output_not_trade_approval"] is True
        assert d["chronicle_output_not_for_execution"] is True
        assert d["chronicle_output_not_for_strategy"] is True
        assert d["chronicle_output_not_for_freqtrade"] is True
        assert d["chronicle_output_not_for_order"] is True
        assert d["chronicle_output_not_for_exchange"] is True
        assert d["chronicle_feedback_into_execution"] is False

    def test_key_count(self) -> None:
        flags = ChronicleSafetyFlags()
        d = chronicle_safety_flags_to_dict(flags)
        assert len(d) == 14


class TestChronicleEntryToDict:
    """Tests for chronicle_entry_to_dict."""

    def test_full_entry(self) -> None:
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        entry = ChronicleEntry(
            entry_id="obs:e1:ts",
            timestamp=dt,
            artifact_type=ArtifactType.OBSERVATION,
            trace_id="trace-a",
            state="READY",
            version="1.0",
            entry_count=5,
            reason_codes=("READY", "ACCEPTED"),
            actor="alice",
            notes="looks good",
            tags=("tag1", "tag2"),
            metadata={"source": "test"},
            related_trace_ids=("trace-b",),
        )
        d = chronicle_entry_to_dict(entry)
        assert d["entry_id"] == "obs:e1:ts"
        assert d["timestamp"] == "2025-01-01T12:00:00+00:00"
        assert d["artifact_type"] == "observation"
        assert d["trace_id"] == "trace-a"
        assert d["state"] == "READY"
        assert d["version"] == "1.0"
        assert d["entry_count"] == 5
        assert d["reason_codes"] == ["READY", "ACCEPTED"]
        assert d["actor"] == "alice"
        assert d["notes"] == "looks good"
        assert d["tags"] == ["tag1", "tag2"]
        assert d["metadata"] == {"source": "test"}
        assert d["related_trace_ids"] == ["trace-b"]

    def test_minimal_entry(self) -> None:
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        entry = ChronicleEntry(
            entry_id="obs:e1:ts",
            timestamp=dt,
            artifact_type=ArtifactType.OBSERVATION,
            trace_id="trace-a",
            state="READY",
            version="1.0",
        )
        d = chronicle_entry_to_dict(entry)
        assert d["entry_count"] == 0
        assert d["reason_codes"] == []
        assert d["actor"] is None
        assert d["notes"] is None
        assert d["tags"] == []
        assert d["metadata"] == {}
        assert d["related_trace_ids"] == []


class TestChronicleSummaryToDict:
    """Tests for chronicle_summary_to_dict."""

    def test_full_summary(self) -> None:
        summary = ChronicleSummary(
            total_entries=10,
            observation_count=3,
            review_count=2,
            index_count=1,
            search_count=2,
            bundle_count=2,
            blocked_count=1,
            ready_count=8,
            accepted_count=5,
            rejected_count=2,
            unknown_count=1,
            reason_code_counts={"READY": 8, "BLOCKED": 1},
            tag_counts={"tag1": 3, "tag2": 2},
            actor_counts={"alice": 5, "bob": 3},
            timestamp_range=("2025-01-01T12:00:00+00:00", "2025-01-02T12:00:00+00:00"),
            daily_counts={"2025-01-01": {"observation": 3, "review": 2}},
        )
        d = chronicle_summary_to_dict(summary)
        assert d["total_entries"] == 10
        assert d["observation_count"] == 3
        assert d["reason_code_counts"] == {"READY": 8, "BLOCKED": 1}
        assert d["tag_counts"] == {"tag1": 3, "tag2": 2}
        assert d["actor_counts"] == {"alice": 5, "bob": 3}
        assert d["timestamp_range"] == ("2025-01-01T12:00:00+00:00", "2025-01-02T12:00:00+00:00")
        assert d["daily_counts"] == {"2025-01-01": {"observation": 3, "review": 2}}

    def test_empty_summary(self) -> None:
        summary = ChronicleSummary()
        d = chronicle_summary_to_dict(summary)
        assert d["total_entries"] == 0
        assert d["reason_code_counts"] == {}
        assert d["tag_counts"] == {}
        assert d["actor_counts"] == {}
        assert d["timestamp_range"] is None
        assert d["daily_counts"] == {}


class TestChronicleDataQualityToDict:
    """Tests for chronicle_data_quality_to_dict."""

    def test_full_data_quality(self) -> None:
        dq = ChronicleDataQuality(
            has_observations=True,
            has_reviews=True,
            has_index=True,
            has_search=True,
            has_bundle=True,
            orphan_observation_count=1,
            orphan_review_count=2,
            trace_completeness_pct=50.0,
            gap_count=1,
            stale_entry_count=3,
            validation_errors=("err1", "err2"),
        )
        d = chronicle_data_quality_to_dict(dq)
        assert d["has_observations"] is True
        assert d["has_reviews"] is True
        assert d["has_index"] is True
        assert d["has_search"] is True
        assert d["has_bundle"] is True
        assert d["orphan_observation_count"] == 1
        assert d["orphan_review_count"] == 2
        assert d["trace_completeness_pct"] == 50.0
        assert d["gap_count"] == 1
        assert d["stale_entry_count"] == 3
        assert d["validation_errors"] == ["err1", "err2"]

    def test_empty_data_quality(self) -> None:
        dq = ChronicleDataQuality()
        d = chronicle_data_quality_to_dict(dq)
        assert d["has_observations"] is False
        assert d["validation_errors"] == []


class TestResearchChronicleToDict:
    """Tests for research_chronicle_to_dict."""

    def test_empty_chronicle(self) -> None:
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        chronicle = ResearchChronicle(
            chronicle_id="chronicle-1",
            generated_at=dt,
            version="1.0",
            entries=(),
            summary=ChronicleSummary(),
            data_quality=ChronicleDataQuality(),
            safety_flags=ChronicleSafetyFlags(),
            reason_codes=(),
        )
        d = research_chronicle_to_dict(chronicle)
        assert d["chronicle_id"] == "chronicle-1"
        assert d["generated_at"] == "2025-01-01T12:00:00+00:00"
        assert d["version"] == "1.0"
        assert d["entries"] == []
        assert d["reason_codes"] == []
        assert d["summary"]["total_entries"] == 0
        assert d["data_quality"]["has_observations"] is False
        assert d["safety_flags"]["dry_run"] is True

    def test_with_entries(self) -> None:
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        entry = ChronicleEntry(
            entry_id="obs:e1:ts",
            timestamp=dt,
            artifact_type=ArtifactType.OBSERVATION,
            trace_id="trace-a",
            state="READY",
            version="1.0",
        )
        chronicle = ResearchChronicle(
            chronicle_id="chronicle-1",
            generated_at=dt,
            entries=(entry,),
            reason_codes=("READY",),
        )
        d = research_chronicle_to_dict(chronicle)
        assert len(d["entries"]) == 1
        assert d["entries"][0]["artifact_type"] == "observation"
        assert d["reason_codes"] == ["READY"]

    def test_json_roundtrip(self) -> None:
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        chronicle = ResearchChronicle(
            chronicle_id="chronicle-1",
            generated_at=dt,
            entries=(
                ChronicleEntry(
                    entry_id="obs:e1:ts",
                    timestamp=dt,
                    artifact_type=ArtifactType.OBSERVATION,
                    trace_id="trace-a",
                    state="READY",
                    version="1.0",
                ),
            ),
            reason_codes=("READY",),
        )
        d = research_chronicle_to_dict(chronicle)
        json_str = json.dumps(d, indent=2, sort_keys=True)
        parsed = json.loads(json_str)
        assert parsed["chronicle_id"] == "chronicle-1"
        assert parsed["entries"][0]["artifact_type"] == "observation"

    def test_blocked_chronicle(self) -> None:
        chronicle = ResearchChronicle.blocked("MISSING_ARTIFACTS")
        d = research_chronicle_to_dict(chronicle)
        assert d["chronicle_id"] == "blocked"
        assert d["reason_codes"] == ["MISSING_ARTIFACTS"]
        assert d["entries"] == []

    def test_all_safety_flags_included(self) -> None:
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        chronicle = ResearchChronicle(
            chronicle_id="chronicle-1",
            generated_at=dt,
        )
        d = research_chronicle_to_dict(chronicle)
        flags = d["safety_flags"]
        assert "chronicle_output_is_human_audit_only" in flags
        assert "chronicle_output_not_trading_signal" in flags
        assert "chronicle_output_not_trade_approval" in flags
        assert "chronicle_output_not_for_execution" in flags
        assert "chronicle_output_not_for_strategy" in flags
        assert "chronicle_output_not_for_freqtrade" in flags
        assert "chronicle_output_not_for_order" in flags
        assert "chronicle_output_not_for_exchange" in flags
        assert "chronicle_feedback_into_execution" in flags


# ---------------------------------------------------------------------------
# Markdown serialization
# ---------------------------------------------------------------------------


class TestResearchChronicleToMarkdown:
    """Tests for research_chronicle_to_markdown."""

    def _make_chronicle(self) -> ResearchChronicle:
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        entry = ChronicleEntry(
            entry_id="obs:e1:ts",
            timestamp=dt,
            artifact_type=ArtifactType.OBSERVATION,
            trace_id="trace-a",
            state="READY",
            version="1.0",
            entry_count=5,
            reason_codes=("READY",),
            metadata={"source": "test"},
            related_trace_ids=("trace-b",),
        )
        return ResearchChronicle(
            chronicle_id="chronicle-1",
            generated_at=dt,
            entries=(entry,),
            summary=ChronicleSummary(
                total_entries=1,
                observation_count=1,
                ready_count=1,
            ),
            data_quality=ChronicleDataQuality(
                has_observations=True,
            ),
            safety_flags=ChronicleSafetyFlags(),
            reason_codes=("READY",),
        )

    def test_contains_safety_notice(self) -> None:
        md = research_chronicle_to_markdown(self._make_chronicle())
        assert "human-audit timeline artifact only" in md
        assert "not a trading signal" in md
        assert "not trade approval" in md

    def test_contains_required_safety_statements(self) -> None:
        md = research_chronicle_to_markdown(self._make_chronicle())
        assert "must not be consumed by execution" in md
        assert "Freqtrade" in md
        assert "order" in md
        assert "exchange" in md
        assert "Trace linkage is **advisory only**" in md
        assert "File references" in md
        assert "not traversed, opened, followed, validated, or executed" in md

    def test_contains_chronicle_info(self) -> None:
        md = research_chronicle_to_markdown(self._make_chronicle())
        assert "chronicle-1" in md
        assert "2025-01-01T12:00:00+00:00" in md
        assert "1.0" in md

    def test_contains_entry_details(self) -> None:
        md = research_chronicle_to_markdown(self._make_chronicle())
        assert "obs:e1:ts" in md
        assert "observation" in md
        assert "trace-a" in md
        assert "READY" in md
        assert "trace-b" in md
        assert "source" in md
        assert "test" in md

    def test_contains_summary(self) -> None:
        md = research_chronicle_to_markdown(self._make_chronicle())
        assert "total_entries" in md
        assert "observation_count" in md
        assert "ready_count" in md

    def test_contains_data_quality(self) -> None:
        md = research_chronicle_to_markdown(self._make_chronicle())
        assert "has_observations" in md
        assert "orphan_observation_count" in md

    def test_contains_safety_flags(self) -> None:
        md = research_chronicle_to_markdown(self._make_chronicle())
        assert "dry_run" in md
        assert "live_trading_enabled" in md
        assert "chronicle_output_is_human_audit_only" in md

    def test_contains_reason_codes(self) -> None:
        md = research_chronicle_to_markdown(self._make_chronicle())
        assert "READY" in md

    def test_empty_chronicle(self) -> None:
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        chronicle = ResearchChronicle(
            chronicle_id="chronicle-1",
            generated_at=dt,
        )
        md = research_chronicle_to_markdown(chronicle)
        assert "_No chronicle entries._" in md
        assert "human-audit timeline artifact only" in md

    def test_blocked_chronicle(self) -> None:
        chronicle = ResearchChronicle.blocked("MISSING_ARTIFACTS")
        md = research_chronicle_to_markdown(chronicle)
        assert "blocked" in md
        assert "MISSING_ARTIFACTS" in md

    def test_no_trading_signal(self) -> None:
        md = research_chronicle_to_markdown(self._make_chronicle())
        assert "not a trading signal" in md

    def test_no_trade_approval(self) -> None:
        md = research_chronicle_to_markdown(self._make_chronicle())
        assert "not trade approval" in md

    def test_no_execution(self) -> None:
        md = research_chronicle_to_markdown(self._make_chronicle())
        assert "consumed by execution" in md.lower()

    def test_no_freqtrade(self) -> None:
        md = research_chronicle_to_markdown(self._make_chronicle())
        assert "Freqtrade" in md

    def test_no_order(self) -> None:
        md = research_chronicle_to_markdown(self._make_chronicle())
        assert "order" in md.lower()

    def test_no_exchange(self) -> None:
        md = research_chronicle_to_markdown(self._make_chronicle())
        assert "exchange" in md.lower()

    def test_trace_linkage_advisory(self) -> None:
        md = research_chronicle_to_markdown(self._make_chronicle())
        assert "advisory only" in md.lower()

    def test_file_references_strings_only(self) -> None:
        md = research_chronicle_to_markdown(self._make_chronicle())
        assert "local strings only" in md.lower()


# ---------------------------------------------------------------------------
# Atomic writes
# ---------------------------------------------------------------------------


class TestAtomicWrite:
    """Tests for _atomic_write helper."""

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        target = tmp_path / "nested" / "chronicle.json"
        _atomic_write(target, "content")
        assert target.read_text() == "content"

    def test_overwrites_existing(self, tmp_path: Path) -> None:
        target = tmp_path / "chronicle.json"
        target.write_text("old")
        _atomic_write(target, "new")
        assert target.read_text() == "new"

    def test_bytes_content(self, tmp_path: Path) -> None:
        target = tmp_path / "chronicle.bin"
        _atomic_write(target, b"binary")
        assert target.read_bytes() == b"binary"

    def test_cleans_up_temp_on_error(self, tmp_path: Path) -> None:
        target = tmp_path / "readonly" / "chronicle.json"
        target.parent.mkdir()
        target.parent.chmod(0o555)
        try:
            with pytest.raises(Exception):
                _atomic_write(target, "content")
        finally:
            target.parent.chmod(0o755)


class TestAtomicWriteJsonResearchChronicle:
    """Tests for atomic_write_json_research_chronicle."""

    def test_default_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import os
        monkeypatch.chdir(tmp_path)
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        chronicle = ResearchChronicle(
            chronicle_id="chronicle-1",
            generated_at=dt,
        )
        result = atomic_write_json_research_chronicle(chronicle)
        assert result == DEFAULT_CHRONICLE_JSON_PATH
        assert result.exists()

    def test_custom_path(self, tmp_path: Path) -> None:
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        chronicle = ResearchChronicle(
            chronicle_id="chronicle-1",
            generated_at=dt,
        )
        target = tmp_path / "chronicle.json"
        result = atomic_write_json_research_chronicle(chronicle, target)
        assert result == target
        assert target.exists()
        data = json.loads(target.read_text())
        assert data["chronicle_id"] == "chronicle-1"

    def test_valid_json(self, tmp_path: Path) -> None:
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        entry = ChronicleEntry(
            entry_id="obs:e1:ts",
            timestamp=dt,
            artifact_type=ArtifactType.OBSERVATION,
            trace_id="trace-a",
            state="READY",
            version="1.0",
        )
        chronicle = ResearchChronicle(
            chronicle_id="chronicle-1",
            generated_at=dt,
            entries=(entry,),
            reason_codes=("READY",),
        )
        target = tmp_path / "chronicle.json"
        atomic_write_json_research_chronicle(chronicle, target)
        data = json.loads(target.read_text())
        assert data["entries"][0]["artifact_type"] == "observation"
        assert data["reason_codes"] == ["READY"]

    def test_sort_keys(self, tmp_path: Path) -> None:
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        chronicle = ResearchChronicle(
            chronicle_id="chronicle-1",
            generated_at=dt,
        )
        target = tmp_path / "chronicle.json"
        atomic_write_json_research_chronicle(chronicle, target)
        text = target.read_text()
        assert '"chronicle_id"' in text
        assert '"generated_at"' in text

    def test_no_temp_file_left(self, tmp_path: Path) -> None:
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        chronicle = ResearchChronicle(
            chronicle_id="chronicle-1",
            generated_at=dt,
        )
        target = tmp_path / "chronicle.json"
        atomic_write_json_research_chronicle(chronicle, target)
        assert not (tmp_path / "chronicle.json.tmp").exists()


class TestAtomicWriteMarkdownResearchChronicle:
    """Tests for atomic_write_markdown_research_chronicle."""

    def test_custom_path(self, tmp_path: Path) -> None:
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        chronicle = ResearchChronicle(
            chronicle_id="chronicle-1",
            generated_at=dt,
        )
        target = tmp_path / "chronicle.md"
        result = atomic_write_markdown_research_chronicle(chronicle, target)
        assert result == target
        assert target.exists()
        assert "human-audit" in target.read_text()

    def test_contains_safety_notice(self, tmp_path: Path) -> None:
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        chronicle = ResearchChronicle(
            chronicle_id="chronicle-1",
            generated_at=dt,
        )
        target = tmp_path / "chronicle.md"
        atomic_write_markdown_research_chronicle(chronicle, target)
        text = target.read_text()
        assert "human-audit timeline artifact only" in text
        assert "not a trading signal" in text
        assert "not trade approval" in text

    def test_no_temp_file_left(self, tmp_path: Path) -> None:
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        chronicle = ResearchChronicle(
            chronicle_id="chronicle-1",
            generated_at=dt,
        )
        target = tmp_path / "chronicle.md"
        atomic_write_markdown_research_chronicle(chronicle, target)
        assert not (tmp_path / "chronicle.md.tmp").exists()


class TestWriteResearchChronicle:
    """Tests for write_research_chronicle."""

    def test_returns_both_paths(self, tmp_path: Path) -> None:
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        chronicle = ResearchChronicle(
            chronicle_id="chronicle-1",
            generated_at=dt,
        )
        json_path = tmp_path / "out.json"
        md_path = tmp_path / "out.md"
        json_result, md_result = write_research_chronicle(chronicle, json_path, md_path)
        assert json_result == json_path
        assert md_result == md_path

    def test_both_files_exist(self, tmp_path: Path) -> None:
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        chronicle = ResearchChronicle(
            chronicle_id="chronicle-1",
            generated_at=dt,
        )
        json_path = tmp_path / "out.json"
        md_path = tmp_path / "out.md"
        write_research_chronicle(chronicle, json_path, md_path)
        assert json_path.exists()
        assert md_path.exists()

    def test_json_content(self, tmp_path: Path) -> None:
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        chronicle = ResearchChronicle(
            chronicle_id="chronicle-1",
            generated_at=dt,
        )
        json_path = tmp_path / "out.json"
        md_path = tmp_path / "out.md"
        write_research_chronicle(chronicle, json_path, md_path)
        data = json.loads(json_path.read_text())
        assert data["chronicle_id"] == "chronicle-1"

    def test_markdown_content(self, tmp_path: Path) -> None:
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        chronicle = ResearchChronicle(
            chronicle_id="chronicle-1",
            generated_at=dt,
        )
        json_path = tmp_path / "out.json"
        md_path = tmp_path / "out.md"
        write_research_chronicle(chronicle, json_path, md_path)
        text = md_path.read_text()
        assert "human-audit" in text
        assert "chronicle-1" in text

    def test_default_paths(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import os
        monkeypatch.chdir(tmp_path)
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        chronicle = ResearchChronicle(
            chronicle_id="chronicle-1",
            generated_at=dt,
        )
        json_result, md_result = write_research_chronicle(chronicle)
        assert json_result == DEFAULT_CHRONICLE_JSON_PATH
        assert md_result == DEFAULT_CHRONICLE_MARKDOWN_PATH
        assert json_result.exists()
        assert md_result.exists()

    def test_with_entries(self, tmp_path: Path) -> None:
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        entry = ChronicleEntry(
            entry_id="obs:e1:ts",
            timestamp=dt,
            artifact_type=ArtifactType.OBSERVATION,
            trace_id="trace-a",
            state="READY",
            version="1.0",
        )
        chronicle = ResearchChronicle(
            chronicle_id="chronicle-1",
            generated_at=dt,
            entries=(entry,),
            reason_codes=("READY",),
        )
        json_path = tmp_path / "out.json"
        md_path = tmp_path / "out.md"
        write_research_chronicle(chronicle, json_path, md_path)
        data = json.loads(json_path.read_text())
        assert len(data["entries"]) == 1
        md = md_path.read_text()
        assert "obs:e1:ts" in md

    def test_writer_does_not_read_metadata(self, tmp_path: Path) -> None:
        """Writer serializes metadata as strings; does not read/traverse them."""
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        entry = ChronicleEntry(
            entry_id="obs:e1:ts",
            timestamp=dt,
            artifact_type=ArtifactType.OBSERVATION,
            trace_id="trace-a",
            state="READY",
            version="1.0",
            metadata={"reference": "some/path/to/file.json"},
        )
        chronicle = ResearchChronicle(
            chronicle_id="chronicle-1",
            generated_at=dt,
            entries=(entry,),
        )
        json_path = tmp_path / "out.json"
        md_path = tmp_path / "out.md"
        write_research_chronicle(chronicle, json_path, md_path)
        data = json.loads(json_path.read_text())
        assert data["entries"][0]["metadata"]["reference"] == "some/path/to/file.json"
        md = md_path.read_text()
        assert "some/path/to/file.json" in md

    def test_safety_flags_included(self, tmp_path: Path) -> None:
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        chronicle = ResearchChronicle(
            chronicle_id="chronicle-1",
            generated_at=dt,
        )
        json_path = tmp_path / "out.json"
        md_path = tmp_path / "out.md"
        write_research_chronicle(chronicle, json_path, md_path)
        data = json.loads(json_path.read_text())
        assert data["safety_flags"]["chronicle_output_is_human_audit_only"] is True
        assert data["safety_flags"]["chronicle_output_not_for_execution"] is True
        assert data["safety_flags"]["chronicle_feedback_into_execution"] is False
        md = md_path.read_text()
        assert "chronicle_output_is_human_audit_only" in md
        assert "chronicle_feedback_into_execution" in md
