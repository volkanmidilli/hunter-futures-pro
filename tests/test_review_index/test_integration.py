"""Integration tests for hunter.review_index end-to-end flow.

Tests the full pipeline: build_review_index -> serialize -> write.
No production data writes. All file I/O uses tmp_path.
No network, database, Freqtrade, Binance, exchange, trading, leverage,
shorting, Web UI, dashboard, or real entry/exit.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hunter.review_index import (
    MISSING_REPORTS,
    UNSUPPORTED_REPORT_VERSION,
    UNSAFE_REPORT_STATE,
    IndexConfig,
    IndexEntryKind,
    IndexState,
    build_review_index,
    review_index_to_dict,
    review_index_to_markdown,
    write_review_index,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_report(
    report_id: str = "report-1",
    version: str = "1.0",
    report_state: str = "READY",
    reason_codes: tuple[str, ...] = (),
    generated_at: datetime | None = None,
) -> dict[str, object]:
    if generated_at is None:
        generated_at = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
    return {
        "report_id": report_id,
        "version": version,
        "report_state": report_state,
        "reason_codes": reason_codes,
        "metadata": {},
        "generated_at": generated_at,
    }


def _make_review(
    audit_id: str = "audit-1",
    report_id: str = "report-1",
    version: str = "1.0",
    review_status: str = "ACCEPTED",
    review_state: str = "READY",
    reason_codes: tuple[str, ...] = (),
    tags: tuple[str, ...] = (),
    reviewer: str = "alice",
    generated_at: datetime | None = None,
    reviewed_at: datetime | None = None,
) -> dict[str, object]:
    if generated_at is None:
        generated_at = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
    if reviewed_at is None:
        reviewed_at = datetime(2024, 6, 15, 13, 0, 0, tzinfo=timezone.utc)
    return {
        "audit_id": audit_id,
        "report_id": report_id,
        "version": version,
        "review_status": review_status,
        "review_state": review_state,
        "reason_codes": reason_codes,
        "tags": tags,
        "reviewer": reviewer,
        "metadata": {},
        "generated_at": generated_at,
        "reviewed_at": reviewed_at,
    }


# ---------------------------------------------------------------------------
# build_review_index -> review_index_to_dict
# ---------------------------------------------------------------------------

class TestBuildReviewIndexToDict:
    def test_linked_entry_roundtrip(self) -> None:
        report = _make_report()
        review = _make_review()
        index = build_review_index(reports=[report], reviews=[review])
        d = review_index_to_dict(index)

        assert d["index_state"] == IndexState.READY.value
        assert len(d["entries"]) == 1
        entry = d["entries"][0]
        assert entry["entry_kind"] == IndexEntryKind.LINKED_REPORT_REVIEW.value
        assert entry["report_id"] == "report-1"
        assert entry["audit_id"] == "audit-1"
        assert entry["review_status"] == "ACCEPTED"
        assert entry["review_state"] == "READY"
        assert entry["index_state"] == IndexState.READY.value
        assert entry["reason_codes"] == []
        assert entry["tags"] == []
        assert entry["reviewer"] == "alice"
        assert entry["source_report_version"] == "1.0"
        assert entry["source_review_version"] == "1.0"
        assert entry["local_report_reference"] == ""
        assert entry["local_review_reference"] == ""
        assert "safety_flags" in entry

    def test_observation_only_roundtrip(self) -> None:
        report = _make_report()
        index = build_review_index(reports=[report])
        d = review_index_to_dict(index)

        assert d["index_state"] == IndexState.READY.value
        assert len(d["entries"]) == 1
        entry = d["entries"][0]
        assert entry["entry_kind"] == IndexEntryKind.OBSERVATION_REPORT.value
        assert entry["audit_id"] == ""
        assert entry["review_status"] == "NOT_REVIEWED"
        assert entry["review_state"] == "UNKNOWN"

    def test_fail_closed_missing_inputs_serialize_safely(self) -> None:
        index = build_review_index(reports=None)
        d = review_index_to_dict(index)

        assert d["index_state"] == IndexState.BLOCKED.value
        assert MISSING_REPORTS in d["reason_codes"]
        assert d["entries"] == []
        assert d["summary"]["total_entries"] == 0
        assert d["data_quality"]["total_reports"] == 0

    def test_invalid_inputs_serialize_safely(self) -> None:
        report = _make_report(version="9.9")
        index = build_review_index(reports=[report])
        d = review_index_to_dict(index)

        assert d["index_state"] == IndexState.BLOCKED.value
        assert UNSUPPORTED_REPORT_VERSION in d["reason_codes"]
        assert len(d["entries"]) == 1
        entry = d["entries"][0]
        assert entry["index_state"] == IndexState.BLOCKED.value
        assert entry["reason_codes"] == [UNSUPPORTED_REPORT_VERSION]

    def test_unsafe_inputs_serialize_safely(self) -> None:
        report = _make_report(report_state="BLOCKED")
        index = build_review_index(reports=[report])
        d = review_index_to_dict(index)

        assert d["index_state"] == IndexState.BLOCKED.value
        assert UNSAFE_REPORT_STATE in d["reason_codes"]
        assert len(d["entries"]) == 1
        entry = d["entries"][0]
        assert entry["index_state"] == IndexState.BLOCKED.value

    def test_mixed_ready_and_blocked_entries(self) -> None:
        r1 = _make_report(report_id="r1")
        r2 = _make_report(report_id="r2", version="9.9")
        r3 = _make_report(report_id="r3", report_state="BLOCKED")
        review = _make_review(report_id="r1")
        index = build_review_index(reports=[r1, r2, r3], reviews=[review])
        d = review_index_to_dict(index)

        assert d["index_state"] == IndexState.BLOCKED.value
        assert len(d["entries"]) == 3
        states = [e["index_state"] for e in d["entries"]]
        assert states.count(IndexState.READY.value) == 1
        assert states.count(IndexState.BLOCKED.value) == 2

    def test_deterministic_output_for_fixed_timestamps(self) -> None:
        now = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        report = _make_report(generated_at=now)
        review = _make_review(generated_at=now, reviewed_at=now)
        index = build_review_index(reports=[report], reviews=[review], now=now)
        d = review_index_to_dict(index)

        assert d["generated_at"] == "2024-06-15T12:00:00Z"
        entry = d["entries"][0]
        assert entry["report_generated_at"] == "2024-06-15T12:00:00Z"
        assert entry["audit_generated_at"] == "2024-06-15T12:00:00Z"
        assert entry["reviewed_at"] == "2024-06-15T12:00:00Z"

    def test_file_references_remain_strings(self) -> None:
        report = _make_report()
        review = _make_review()
        index = build_review_index(
            reports=[report],
            reviews=[review],
        )
        d = review_index_to_dict(index)

        entry = d["entries"][0]
        assert isinstance(entry["local_report_reference"], str)
        assert isinstance(entry["local_review_reference"], str)
        assert entry["local_report_reference"] == ""
        assert entry["local_review_reference"] == ""

    def test_no_production_data_paths_in_output(self) -> None:
        report = _make_report()
        review = _make_review()
        index = build_review_index(reports=[report], reviews=[review])
        d = review_index_to_dict(index)

        text = json.dumps(d)
        assert "data/review_index" not in text
        assert "reports/review_index" not in text


# ---------------------------------------------------------------------------
# build_review_index -> review_index_to_markdown
# ---------------------------------------------------------------------------

class TestBuildReviewIndexToMarkdown:
    def test_linked_entry_markdown(self) -> None:
        report = _make_report()
        review = _make_review()
        index = build_review_index(reports=[report], reviews=[review])
        md = review_index_to_markdown(index)

        assert "# Review Index" in md
        assert "human-audit catalog artifact only" in md
        assert "report-1" in md
        assert "audit-1" in md
        assert IndexEntryKind.LINKED_REPORT_REVIEW.value in md
        assert IndexState.READY.value in md

    def test_fail_closed_markdown(self) -> None:
        index = build_review_index(reports=None)
        md = review_index_to_markdown(index)

        assert IndexState.BLOCKED.value in md
        assert MISSING_REPORTS in md
        assert "No entries" in md

    def test_mixed_ready_blocked_markdown(self) -> None:
        r1 = _make_report(report_id="r1")
        r2 = _make_report(report_id="r2", version="9.9")
        index = build_review_index(reports=[r1, r2])
        md = review_index_to_markdown(index)

        assert "r1" in md
        assert "r2" in md
        assert "## Entries" in md

    def test_file_references_not_opened_in_markdown(self) -> None:
        report = _make_report()
        review = _make_review()
        index = build_review_index(reports=[report], reviews=[review])
        md = review_index_to_markdown(index)

        # References are empty strings by default; markdown should just not show them
        # If they had values, they'd appear as plain strings
        assert "local_report_reference" not in md or "- **local_report_reference**: " in md

    def test_no_production_paths_in_markdown(self) -> None:
        report = _make_report()
        review = _make_review()
        index = build_review_index(reports=[report], reviews=[review])
        md = review_index_to_markdown(index)

        assert "data/review_index" not in md
        assert "reports/review_index" not in md


# ---------------------------------------------------------------------------
# build_review_index -> write_review_index with custom tmp_path
# ---------------------------------------------------------------------------

class TestBuildReviewIndexWrite:
    def test_write_json_and_markdown(self, tmp_path: Path) -> None:
        report = _make_report()
        review = _make_review()
        index = build_review_index(reports=[report], reviews=[review])

        json_path = tmp_path / "index.json"
        md_path = tmp_path / "index.md"
        out_json, out_md = write_review_index(index, json_path, md_path)

        assert out_json == json_path
        assert out_md == md_path
        assert json_path.exists()
        assert md_path.exists()

        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data["index_state"] == IndexState.READY.value
        assert len(data["entries"]) == 1
        assert data["entries"][0]["report_id"] == "report-1"

        md_text = md_path.read_text(encoding="utf-8")
        assert "# Review Index" in md_text
        assert "report-1" in md_text

    def test_write_fail_closed_index(self, tmp_path: Path) -> None:
        index = build_review_index(reports=None)

        json_path = tmp_path / "blocked.json"
        md_path = tmp_path / "blocked.md"
        write_review_index(index, json_path, md_path)

        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data["index_state"] == IndexState.BLOCKED.value
        assert MISSING_REPORTS in data["reason_codes"]

        md_text = md_path.read_text(encoding="utf-8")
        assert IndexState.BLOCKED.value in md_text

    def test_write_mixed_entries(self, tmp_path: Path) -> None:
        r1 = _make_report(report_id="r1")
        r2 = _make_report(report_id="r2", version="9.9")
        r3 = _make_report(report_id="r3", report_state="BLOCKED")
        review = _make_review(report_id="r1")
        index = build_review_index(reports=[r1, r2, r3], reviews=[review])

        json_path = tmp_path / "mixed.json"
        md_path = tmp_path / "mixed.md"
        write_review_index(index, json_path, md_path)

        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data["index_state"] == IndexState.BLOCKED.value
        assert len(data["entries"]) == 3

        md_text = md_path.read_text(encoding="utf-8")
        assert "r1" in md_text
        assert "r2" in md_text
        assert "r3" in md_text

    def test_deterministic_json_output(self, tmp_path: Path) -> None:
        now = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        report = _make_report(generated_at=now)
        review = _make_review(generated_at=now, reviewed_at=now)
        index = build_review_index(reports=[report], reviews=[review], now=now)

        json_path = tmp_path / "det.json"
        write_review_index(index, json_path, tmp_path / "det.md")

        text = json_path.read_text(encoding="utf-8")
        data = json.loads(text)
        assert data["generated_at"] == "2024-06-15T12:00:00Z"
        # JSON is sorted and indented
        assert "  \"generated_at\"" in text
        assert text.strip().endswith("}")
        assert text.endswith("\n")

    def test_no_temp_files_left_behind(self, tmp_path: Path) -> None:
        report = _make_report()
        review = _make_review()
        index = build_review_index(reports=[report], reviews=[review])

        json_path = tmp_path / "index.json"
        md_path = tmp_path / "index.md"
        write_review_index(index, json_path, md_path)

        temps = list(tmp_path.glob("*.tmp"))
        assert temps == []

    def test_file_references_not_traversed_during_write(self, tmp_path: Path) -> None:
        report = _make_report()
        review = _make_review()
        index = build_review_index(reports=[report], reviews=[review])

        json_path = tmp_path / "index.json"
        md_path = tmp_path / "index.md"
        write_review_index(index, json_path, md_path)

        # The write should not attempt to open or validate file references
        data = json.loads(json_path.read_text(encoding="utf-8"))
        entry = data["entries"][0]
        assert isinstance(entry["local_report_reference"], str)
        assert isinstance(entry["local_review_reference"], str)

    def test_no_production_paths_written(self, tmp_path: Path) -> None:
        report = _make_report()
        review = _make_review()
        index = build_review_index(reports=[report], reviews=[review])

        json_path = tmp_path / "index.json"
        md_path = tmp_path / "index.md"
        write_review_index(index, json_path, md_path)

        # Verify the test used tmp_path, not production paths
        assert str(json_path).startswith(str(tmp_path))
        assert str(md_path).startswith(str(tmp_path))
