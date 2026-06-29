"""Integration tests for hunter.chronicle package.

MVP-15 end-to-end integration tests: engine -> writer -> verify.
No network, database, Freqtrade, Binance, exchange, trading,
Web UI, dashboard, or production data access is exercised here.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from hunter.chronicle.engine import (
    build_research_chronicle,
)
from hunter.chronicle.models import (
    ArtifactType,
    ResearchChronicle,
)
from hunter.chronicle.writer import (
    atomic_write_json_research_chronicle,
    atomic_write_markdown_research_chronicle,
    research_chronicle_to_dict,
    research_chronicle_to_markdown,
    write_research_chronicle,
)
from hunter.observation.models import (
    ObservationReport,
    ObservationSafetyFlags,
    ObservationState,
    ObservationWindow,
)
from hunter.review.models import (
    ReviewAuditRecord,
    ReviewAuditSummary,
    ReviewDataQuality,
    ReviewRecord,
    ReviewSafetyFlags,
    ReviewState,
    ReviewStatus,
)


_NOW = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _window() -> ObservationWindow:
    return ObservationWindow(
        started_at=_NOW,
        ended_at=_NOW + timedelta(hours=1),
        observations=(
            {"symbol": "BTC/USDT", "price": 40000.0},
            {"symbol": "ETH/USDT", "price": 2500.0},
        ),
    )


def _observation_report(generated_at: datetime) -> ObservationReport:
    return ObservationReport(
        generated_at=generated_at,
        report_state=ObservationState.READY,
        window=_window(),
        safety_flags=ObservationSafetyFlags(),
        reason_codes=("READY",),
        version="1.0",
    )


def _audit_record(generated_at: datetime) -> ReviewAuditRecord:
    record = ReviewRecord(
        review_id="record-1",
        source_report_id="report-1",
        source_report_version="1.0",
        review_state=ReviewState.READY,
        review_status=ReviewStatus.ACCEPTED,
        reviewer="alice",
        notes="ok",
        tags=(),
        reason_codes=("ACCEPTED",),
        reviewed_at=generated_at,
        safety_flags=ReviewSafetyFlags(
            dry_run=True,
            live_trading_enabled=False,
            real_orders_enabled=False,
            leverage_enabled=False,
            shorting_enabled=False,
            report_feedback_into_execution=False,
            operator_feedback_into_execution=False,
        ),
    )
    summary = ReviewAuditSummary(
        total_reviews=1,
        accepted_count=1,
        rejected_count=0,
        needs_investigation_count=0,
        not_reviewed_count=0,
        blocked_count=0,
        unknown_count=0,
        reason_counts={"ACCEPTED": 1},
    )
    data_quality = ReviewDataQuality(
        total_reports=1,
        valid_reports=1,
        blocked_reports=0,
        unknown_reports=0,
        unsafe_reports=0,
        missing_reports=0,
        invalid_reports=0,
    )
    safety_flags = ReviewSafetyFlags(
        dry_run=True,
        live_trading_enabled=False,
        real_orders_enabled=False,
        leverage_enabled=False,
        shorting_enabled=False,
        report_feedback_into_execution=False,
        operator_feedback_into_execution=False,
    )
    return ReviewAuditRecord(
        audit_id="audit-1",
        generated_at=generated_at,
        audit_state=ReviewState.READY,
        records=(record,),
        summary=summary,
        data_quality=data_quality,
        reason_codes=("READY",),
        safety_flags=safety_flags,
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestHappyPath:
    """End-to-end flows with valid artifacts."""

    def test_full_flow_observation_only(self, tmp_path: Path) -> None:
        report = _observation_report(_NOW)
        chronicle = build_research_chronicle(observations=(report,))

        assert chronicle.chronicle_id != "blocked"
        assert len(chronicle.entries) == 1
        assert chronicle.entries[0].artifact_type is ArtifactType.OBSERVATION

        d = research_chronicle_to_dict(chronicle)
        assert d["chronicle_id"] != "blocked"
        assert len(d["entries"]) == 1
        assert d["entries"][0]["artifact_type"] == "observation"

        json_path = tmp_path / "chronicle.json"
        md_path = tmp_path / "chronicle.md"
        write_research_chronicle(chronicle, json_path, md_path)

        assert json_path.exists()
        assert md_path.exists()

        data = json.loads(json_path.read_text())
        assert data["chronicle_id"] == chronicle.chronicle_id
        assert data["entries"][0]["artifact_type"] == "observation"
        assert data["safety_flags"]["chronicle_output_is_human_audit_only"] is True

        md_text = md_path.read_text()
        assert "human-audit" in md_text.lower()
        assert "not a trading signal" in md_text.lower()

    def test_full_flow_observation_and_review(self, tmp_path: Path) -> None:
        obs_report = _observation_report(_NOW)
        audit_record = _audit_record(_NOW + timedelta(hours=1))
        chronicle = build_research_chronicle(observations=(obs_report,), reviews=(audit_record,))

        assert chronicle.chronicle_id != "blocked"
        assert len(chronicle.entries) == 2
        assert chronicle.entries[0].artifact_type is ArtifactType.OBSERVATION
        assert chronicle.entries[1].artifact_type is ArtifactType.REVIEW
        assert chronicle.entries[0].timestamp <= chronicle.entries[1].timestamp

        json_path = tmp_path / "chronicle.json"
        md_path = tmp_path / "chronicle.md"
        write_research_chronicle(chronicle, json_path, md_path)

        data = json.loads(json_path.read_text())
        assert len(data["entries"]) == 2
        assert data["entries"][0]["artifact_type"] == "observation"
        assert data["entries"][1]["artifact_type"] == "review"

        md_text = md_path.read_text()
        assert "observation" in md_text.lower()
        assert "review" in md_text.lower()

    def test_multiple_observations_sorted(self) -> None:
        t1 = _NOW
        t2 = _NOW + timedelta(hours=1)
        t3 = _NOW + timedelta(hours=2)
        obs1 = _observation_report(t1)
        obs2 = _observation_report(t2)
        obs3 = _observation_report(t3)
        chronicle = build_research_chronicle(observations=(obs3, obs1, obs2))

        assert len(chronicle.entries) == 3
        assert chronicle.entries[0].timestamp == t1
        assert chronicle.entries[1].timestamp == t2
        assert chronicle.entries[2].timestamp == t3
        for entry in chronicle.entries:
            assert entry.entry_id.startswith("observation:")

    def test_same_timestamp_tiebreak_by_type(self) -> None:
        obs_report = _observation_report(_NOW)
        audit_record = _audit_record(_NOW)
        chronicle = build_research_chronicle(observations=(obs_report,), reviews=(audit_record,))

        assert chronicle.entries[0].artifact_type is ArtifactType.OBSERVATION
        assert chronicle.entries[1].artifact_type is ArtifactType.REVIEW

    def test_summary_counts(self) -> None:
        obs_report = _observation_report(_NOW)
        audit_record = _audit_record(_NOW + timedelta(hours=1))
        chronicle = build_research_chronicle(observations=(obs_report,), reviews=(audit_record,))

        summary = chronicle.summary
        assert summary.total_entries == 2
        assert summary.observation_count == 1
        assert summary.review_count == 1
        assert summary.ready_count == 2
        assert summary.blocked_count == 0

        data = research_chronicle_to_dict(chronicle)
        assert data["summary"]["total_entries"] == 2
        assert data["summary"]["observation_count"] == 1
        assert data["summary"]["review_count"] == 1

    def test_data_quality_computed(self) -> None:
        obs_report = _observation_report(_NOW)
        audit_record = _audit_record(_NOW + timedelta(hours=1))
        chronicle = build_research_chronicle(observations=(obs_report,), reviews=(audit_record,))

        dq = chronicle.data_quality
        assert dq.has_observations is True
        assert dq.has_reviews is True
        assert dq.has_index is False
        assert dq.has_search is False
        assert dq.has_bundle is False

        data = research_chronicle_to_dict(chronicle)
        assert data["data_quality"]["has_observations"] is True
        assert data["data_quality"]["has_reviews"] is True


# ---------------------------------------------------------------------------
# Blocked / error paths
# ---------------------------------------------------------------------------


class TestBlockedPaths:
    """Fail-closed and error paths."""

    def test_blocked_on_missing_artifacts(self, tmp_path: Path) -> None:
        chronicle = build_research_chronicle()
        assert chronicle.chronicle_id == "blocked"
        assert chronicle.reason_codes == ("MISSING_ARTIFACTS",)

        json_path = tmp_path / "blocked.json"
        md_path = tmp_path / "blocked.md"
        write_research_chronicle(chronicle, json_path, md_path)
        data = json.loads(json_path.read_text())
        assert data["chronicle_id"] == "blocked"
        assert data["reason_codes"] == ["MISSING_ARTIFACTS"]

    def test_blocked_on_unsafe_observation_dict_notes(self) -> None:
        obs = {"generated_at": _NOW, "version": "1.0", "notes": "enter_long now"}
        chronicle = build_research_chronicle(observations=(obs,))
        assert chronicle.chronicle_id == "blocked"
        assert chronicle.reason_codes == ("UNSAFE_CHRONICLE_CONTENT",)

    def test_blocked_on_unsafe_observation_dict_tags(self) -> None:
        obs = {"generated_at": _NOW, "version": "1.0", "tags": ("leverage",)}
        chronicle = build_research_chronicle(observations=(obs,))
        assert chronicle.chronicle_id == "blocked"
        assert chronicle.reason_codes == ("UNSAFE_CHRONICLE_CONTENT",)

    def test_blocked_on_unsafe_observation_dict_metadata(self) -> None:
        obs = {"generated_at": _NOW, "version": "1.0", "metadata": {"order": "buy"}}
        chronicle = build_research_chronicle(observations=(obs,))
        assert chronicle.chronicle_id == "blocked"
        assert chronicle.reason_codes == ("UNSAFE_CHRONICLE_CONTENT",)

    def test_blocked_on_invalid_observation(self) -> None:
        chronicle = build_research_chronicle(observations=({},))
        assert chronicle.chronicle_id == "blocked"
        assert chronicle.reason_codes == ("INVALID_OBSERVATION",)

    def test_blocked_on_naive_observation(self) -> None:
        obs = {"generated_at": datetime(2025, 1, 1, 12, 0, 0), "version": "1.0"}
        chronicle = build_research_chronicle(observations=(obs,))
        assert chronicle.chronicle_id == "blocked"
        assert chronicle.reason_codes == ("INVALID_OBSERVATION",)

    def test_blocked_on_unsupported_version(self) -> None:
        obs = {"generated_at": _NOW, "version": ""}
        chronicle = build_research_chronicle(observations=(obs,))
        assert chronicle.chronicle_id == "blocked"
        assert chronicle.reason_codes == ("UNSUPPORTED_OBSERVATION_VERSION",)

    def test_blocked_on_invalid_review(self) -> None:
        chronicle = build_research_chronicle(reviews=({},))
        assert chronicle.chronicle_id == "blocked"
        assert chronicle.reason_codes == ("INVALID_REVIEW",)


# ---------------------------------------------------------------------------
# Safety assertions
# ---------------------------------------------------------------------------


class TestSafetyAssertions:
    """Safety invariants in output."""

    def test_safety_flags_in_json(self, tmp_path: Path) -> None:
        obs = _observation_report(_NOW)
        chronicle = build_research_chronicle(observations=(obs,))
        json_path = tmp_path / "chronicle.json"
        atomic_write_json_research_chronicle(chronicle, json_path)
        data = json.loads(json_path.read_text())

        flags = data["safety_flags"]
        assert flags["chronicle_output_is_human_audit_only"] is True
        assert flags["chronicle_output_not_trading_signal"] is True
        assert flags["chronicle_output_not_trade_approval"] is True
        assert flags["chronicle_output_not_for_execution"] is True
        assert flags["chronicle_output_not_for_strategy"] is True
        assert flags["chronicle_output_not_for_freqtrade"] is True
        assert flags["chronicle_output_not_for_order"] is True
        assert flags["chronicle_output_not_for_exchange"] is True
        assert flags["chronicle_feedback_into_execution"] is False
        assert flags["live_trading_enabled"] is False
        assert flags["leverage_enabled"] is False
        assert flags["shorting_enabled"] is False

    def test_markdown_safety_notice(self) -> None:
        obs = _observation_report(_NOW)
        chronicle = build_research_chronicle(observations=(obs,))
        md = research_chronicle_to_markdown(chronicle)

        assert "human-audit timeline artifact only" in md
        assert "not a trading signal" in md
        assert "not trade approval" in md
        assert "must not be consumed by execution" in md
        assert "Freqtrade" in md
        assert "advisory only" in md.lower()
        assert "local strings only" in md.lower()
        assert "not traversed, opened, followed, validated, or executed" in md.lower()

    def test_markdown_no_freqtrade_order_exchange(self) -> None:
        obs = _observation_report(_NOW)
        chronicle = build_research_chronicle(observations=(obs,))
        md = research_chronicle_to_markdown(chronicle)
        assert "Freqtrade" in md
        assert "order" in md.lower()
        assert "exchange" in md.lower()


# ---------------------------------------------------------------------------
# Writer behavior
# ---------------------------------------------------------------------------


class TestWriterBehavior:
    """Writer-specific integration assertions."""

    def test_writer_does_not_read_metadata(self, tmp_path: Path) -> None:
        """Writer serializes metadata dicts; does not read/traverse file paths."""
        obs = {"generated_at": _NOW, "version": "1.0", "summary": {"reference": "reports/observation/some_report.json"}}
        chronicle = build_research_chronicle(observations=(obs,))
        json_path = tmp_path / "chronicle.json"
        md_path = tmp_path / "chronicle.md"
        write_research_chronicle(chronicle, json_path, md_path)

        data = json.loads(json_path.read_text())
        assert data["entries"][0]["metadata"]["reference"] == "reports/observation/some_report.json"
        md = md_path.read_text()
        assert "reports/observation/some_report.json" in md
        assert not (tmp_path / "reports" / "observation" / "some_report.json").exists()

    def test_writer_does_not_execute_trace_ids(self, tmp_path: Path) -> None:
        obs = _observation_report(_NOW)
        chronicle = build_research_chronicle(observations=(obs,))
        json_path = tmp_path / "chronicle.json"
        write_research_chronicle(chronicle, json_path, tmp_path / "chronicle.md")

        data = json.loads(json_path.read_text())
        trace_id = data["entries"][0]["trace_id"]
        assert trace_id.startswith("observation:")
        assert isinstance(trace_id, str)

    def test_deterministic_json_output(self, tmp_path: Path) -> None:
        obs = _observation_report(_NOW)
        chronicle = build_research_chronicle(observations=(obs,))
        json_path = tmp_path / "chronicle.json"
        atomic_write_json_research_chronicle(chronicle, json_path)
        text1 = json_path.read_text()
        atomic_write_json_research_chronicle(chronicle, json_path)
        text2 = json_path.read_text()
        assert text1 == text2

    def test_deterministic_markdown_output(self, tmp_path: Path) -> None:
        obs = _observation_report(_NOW)
        chronicle = build_research_chronicle(observations=(obs,))
        md_path = tmp_path / "chronicle.md"
        atomic_write_markdown_research_chronicle(chronicle, md_path)
        text1 = md_path.read_text()
        atomic_write_markdown_research_chronicle(chronicle, md_path)
        text2 = md_path.read_text()
        assert text1 == text2

    def test_json_sort_keys(self, tmp_path: Path) -> None:
        obs = _observation_report(_NOW)
        chronicle = build_research_chronicle(observations=(obs,))
        json_path = tmp_path / "chronicle.json"
        atomic_write_json_research_chronicle(chronicle, json_path)
        text = json_path.read_text()
        assert '"chronicle_id"' in text
        assert text.index('"chronicle_id"') < text.index('"data_quality"')
        assert text.index('"data_quality"') < text.index('"entries"')

    def test_atomic_json_no_temp_file(self, tmp_path: Path) -> None:
        obs = _observation_report(_NOW)
        chronicle = build_research_chronicle(observations=(obs,))
        json_path = tmp_path / "chronicle.json"
        atomic_write_json_research_chronicle(chronicle, json_path)
        assert not (tmp_path / "chronicle.json.tmp").exists()

    def test_atomic_markdown_no_temp_file(self, tmp_path: Path) -> None:
        obs = _observation_report(_NOW)
        chronicle = build_research_chronicle(observations=(obs,))
        md_path = tmp_path / "chronicle.md"
        atomic_write_markdown_research_chronicle(chronicle, md_path)
        assert not (tmp_path / "chronicle.md.tmp").exists()


# ---------------------------------------------------------------------------
# Trace linkage
# ---------------------------------------------------------------------------


class TestTraceLinkage:
    """Trace linkage advisory behavior."""

    def test_trace_linkage_advisory_only(self) -> None:
        obs = _observation_report(_NOW)
        chronicle = build_research_chronicle(observations=(obs,))
        md = research_chronicle_to_markdown(chronicle)
        assert "advisory only" in md.lower()

    def test_no_automatic_cross_linking(self) -> None:
        obs = _observation_report(_NOW)
        audit_record = _audit_record(_NOW + timedelta(hours=1))
        chronicle = build_research_chronicle(observations=(obs,), reviews=(audit_record,))
        for entry in chronicle.entries:
            assert entry.related_trace_ids == ()

    def test_orphan_zero_without_links(self) -> None:
        obs = _observation_report(_NOW)
        audit_record = _audit_record(_NOW + timedelta(hours=1))
        chronicle = build_research_chronicle(observations=(obs,), reviews=(audit_record,))
        assert chronicle.data_quality.orphan_observation_count == 0
        assert chronicle.data_quality.orphan_review_count == 0


# ---------------------------------------------------------------------------
# Entry details
# ---------------------------------------------------------------------------


class TestEntryDetails:
    """Entry-level serialization details."""

    def test_entry_metadata_from_summary(self) -> None:
        obs = {"generated_at": _NOW, "version": "1.0", "summary": {"key": "value"}}
        chronicle = build_research_chronicle(observations=(obs,))
        data = research_chronicle_to_dict(chronicle)
        assert data["entries"][0]["metadata"] == {"key": "value"}

    def test_entry_count_from_observation_window(self) -> None:
        obs = _observation_report(_NOW)
        chronicle = build_research_chronicle(observations=(obs,))
        assert chronicle.entries[0].entry_count == 2
        data = research_chronicle_to_dict(chronicle)
        assert data["entries"][0]["entry_count"] == 2

    def test_entry_reason_codes(self) -> None:
        obs = {"generated_at": _NOW, "version": "1.0", "reason_codes": ("READY", "ACCEPTED")}
        chronicle = build_research_chronicle(observations=(obs,))
        data = research_chronicle_to_dict(chronicle)
        assert data["entries"][0]["reason_codes"] == ["READY", "ACCEPTED"]

    def test_entry_version(self) -> None:
        obs = {"generated_at": _NOW, "version": "2.0"}
        chronicle = build_research_chronicle(observations=(obs,))
        assert chronicle.entries[0].version == "2.0"
        data = research_chronicle_to_dict(chronicle)
        assert data["entries"][0]["version"] == "2.0"

    def test_entry_trace_id_deterministic(self) -> None:
        obs = _observation_report(_NOW)
        chronicle1 = build_research_chronicle(observations=(obs,))
        chronicle2 = build_research_chronicle(observations=(obs,))
        assert chronicle1.entries[0].trace_id == chronicle2.entries[0].trace_id
        assert chronicle1.entries[0].entry_id == chronicle2.entries[0].entry_id
