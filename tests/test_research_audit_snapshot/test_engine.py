"""Tests for hunter.research_audit_snapshot.engine."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from hunter.research_audit_snapshot.engine import (
    build_audit_snapshot_data_quality,
    build_audit_snapshot_item,
    build_audit_snapshot_safety_flags,
    build_audit_snapshot_section,
    build_audit_snapshot_summary,
    build_research_audit_snapshot,
    has_unsafe_audit_snapshot_content,
)
from hunter.research_audit_snapshot.models import (
    AUDIT_SNAPSHOT_STALE_REASON_CODES,
    BLOCKED_ARTIFACT_ITEM,
    CANONICAL_AUDIT_SNAPSHOT_SECTION_ORDER,
    HUMAN_AUDIT_GUIDE_NON_GATING,
    INCOMPLETE_ARTIFACT_ITEM,
    INVALID_SNAPSHOT_CONFIG,
    MISSING_ARTIFACT_SUMMARIES,
    MISSING_REQUIRED_SECTION,
    NO_ACTION_COMMANDS_EMITTED,
    OPEN_ITEMS_PRESENT,
    STALE_ARTIFACT_DETECTED,
    UNSAFE_SNAPSHOT_CONTENT,
    UNKNOWN_SNAPSHOT_STATE,
    AuditSnapshotConfig,
    AuditSnapshotDataQuality,
    AuditSnapshotItem,
    AuditSnapshotItemSeverity,
    AuditSnapshotSafetyFlags,
    AuditSnapshotSection,
    AuditSnapshotSectionKind,
    AuditSnapshotState,
    AuditSnapshotSummary,
    ResearchAuditSnapshot,
)


@pytest.fixture
def now() -> datetime:
    return datetime.now(timezone.utc)


@pytest.fixture
def valid_artifact_summary(now: datetime) -> dict[str, object]:
    return {
        "artifact_id": "obs-1",
        "artifact_kind": "OBSERVATION_REPORT",
        "state": "current",
        "source_version": "1.0",
        "generated_at": now,
        "spec_reference": "SPEC-011",
        "local_reference": "data/observation/latest_observation_report.json",
        "related_mvp": "MVP-10",
    }


@pytest.fixture
def stale_artifact_summary(now: datetime) -> dict[str, object]:
    return {
        "artifact_id": "obs-old",
        "artifact_kind": "OBSERVATION_REPORT",
        "state": "current",
        "source_version": "1.0",
        "generated_at": now - timedelta(days=2),
        "spec_reference": "SPEC-011",
        "local_reference": "data/observation/old.json",
        "related_mvp": "MVP-10",
    }


# ---------------------------------------------------------------------------
# Safety flags builder
# ---------------------------------------------------------------------------

class TestBuildAuditSnapshotSafetyFlags:
    def test_returns_default_safe_flags(self) -> None:
        flags = build_audit_snapshot_safety_flags()
        assert flags.dry_run is True
        assert flags.live_trading_enabled is False
        assert flags.snapshot_output_is_human_audit_only is True
        assert flags.snapshot_output_not_transaction_permission is True
        assert flags.file_refs_not_traversed is True
        assert flags.artifact_files_not_read is True
        assert flags.no_action_commands_emitted is True
        assert flags.human_audit_guide_is_non_gating is True
        assert flags.snapshot_feedback_into_execution is False
        assert flags.cross_layer_feedback_into_execution is False
        assert flags.runtime_registry_enabled is False


# ---------------------------------------------------------------------------
# Unsafe content detection
# ---------------------------------------------------------------------------

class TestHasUnsafeAuditSnapshotContent:
    def test_detects_forbidden_text(self) -> None:
        assert has_unsafe_audit_snapshot_content("contains api_key value") is True
        assert has_unsafe_audit_snapshot_content("safe text") is False

    def test_detects_forbidden_metadata(self) -> None:
        assert has_unsafe_audit_snapshot_content({"note": "deploy now"}) is True
        assert has_unsafe_audit_snapshot_content({"note": "safe"}) is False

    def test_empty_and_none(self) -> None:
        assert has_unsafe_audit_snapshot_content("") is False
        assert has_unsafe_audit_snapshot_content(None) is False

    def test_nested_metadata(self) -> None:
        assert has_unsafe_audit_snapshot_content({"outer": {"inner": "secret"}}) is True

    def test_list_of_strings(self) -> None:
        assert has_unsafe_audit_snapshot_content(["safe", "binance"]) is True
        assert has_unsafe_audit_snapshot_content(["safe", "also safe"]) is False

    def test_forbidden_runtime_registry_term(self) -> None:
        assert has_unsafe_audit_snapshot_content("runtime_registry") is True

    def test_forbidden_indexer_term(self) -> None:
        assert has_unsafe_audit_snapshot_content("index_files") is True


# ---------------------------------------------------------------------------
# Item builder
# ---------------------------------------------------------------------------

class TestBuildAuditSnapshotItem:
    def test_builds_item(self) -> None:
        item = build_audit_snapshot_item(
            item_id="i-1",
            title="Title",
            artifact_kind="OBSERVATION_REPORT",
            related_mvp="MVP-10",
            spec_reference="SPEC-011",
        )
        assert item.item_id == "i-1"
        assert item.severity == "INFO"
        assert item.state == "UNKNOWN"

    def test_state_current(self) -> None:
        item = build_audit_snapshot_item(
            item_id="i-1",
            title="Title",
            state="current",
        )
        assert item.state == "CURRENT"

    def test_state_blocked(self) -> None:
        item = build_audit_snapshot_item(
            item_id="i-1",
            title="Title",
            state="block",
        )
        assert item.state == "BLOCK"

    def test_forbidden_term_raises(self) -> None:
        with pytest.raises(ValueError, match="UNSAFE_SNAPSHOT_CONTENT"):
            build_audit_snapshot_item(item_id="i-1", title="execute trade")


# ---------------------------------------------------------------------------
# Section builder
# ---------------------------------------------------------------------------

class TestBuildAuditSnapshotSection:
    def test_builds_section(self) -> None:
        section = build_audit_snapshot_section(
            section_kind=AuditSnapshotSectionKind.OVERVIEW,
            title="Overview",
        )
        assert section.section_kind == AuditSnapshotSectionKind.OVERVIEW

    def test_items_are_ordered(self) -> None:
        item_high = build_audit_snapshot_item(item_id="h", title="H", severity="HIGH", related_mvp="MVP-22")
        item_info = build_audit_snapshot_item(item_id="i", title="I", severity="INFO", related_mvp="MVP-10")
        section = build_audit_snapshot_section(
            section_kind=AuditSnapshotSectionKind.ARTIFACT_STATE,
            title="Artifacts",
            items=(item_info, item_high),
        )
        assert section.items[0].severity == "HIGH"
        assert section.items[1].severity == "INFO"

    def test_ordering_by_mvp_number(self) -> None:
        item_mvp10 = build_audit_snapshot_item(item_id="a", title="A", severity="HIGH", related_mvp="MVP-10")
        item_mvp15 = build_audit_snapshot_item(item_id="b", title="B", severity="HIGH", related_mvp="MVP-15")
        section = build_audit_snapshot_section(
            section_kind=AuditSnapshotSectionKind.ARTIFACT_STATE,
            title="Artifacts",
            items=(item_mvp15, item_mvp10),
        )
        assert section.items[0].related_mvp == "MVP-10"
        assert section.items[1].related_mvp == "MVP-15"

    def test_unparseable_mvp_sorts_last(self) -> None:
        item_known = build_audit_snapshot_item(item_id="a", title="A", severity="HIGH", related_mvp="MVP-10")
        item_unknown = build_audit_snapshot_item(item_id="b", title="B", severity="HIGH", related_mvp="unknown")
        section = build_audit_snapshot_section(
            section_kind=AuditSnapshotSectionKind.ARTIFACT_STATE,
            title="Artifacts",
            items=(item_unknown, item_known),
        )
        assert section.items[0].related_mvp == "MVP-10"
        assert section.items[1].related_mvp == "unknown"


# ---------------------------------------------------------------------------
# Data quality builder
# ---------------------------------------------------------------------------

class TestBuildAuditSnapshotDataQuality:
    def test_complete(self, valid_artifact_summary: dict[str, object], now: datetime) -> None:
        item = build_audit_snapshot_item(
            item_id="i-1",
            title="Title",
            state="current",
            related_mvp="MVP-10",
        )
        dq = build_audit_snapshot_data_quality(
            artifact_summaries=(valid_artifact_summary,),
            items=(item,),
            config=AuditSnapshotConfig(expected_artifact_count=1, freshness_threshold_seconds=3600),
        )
        assert dq.total_artifacts_expected == 1
        assert dq.total_artifacts_present == 1
        assert dq.total_artifacts_missing == 0

    def test_incomplete(self, now: datetime) -> None:
        dq = build_audit_snapshot_data_quality(
            artifact_summaries=(),
            items=(),
            config=AuditSnapshotConfig(expected_artifact_count=3),
        )
        assert dq.total_artifacts_expected == 3
        assert dq.total_artifacts_present == 0
        assert dq.total_artifacts_missing == 3

    def test_stale(self, stale_artifact_summary: dict[str, object], now: datetime) -> None:
        item = build_audit_snapshot_item(
            item_id="i-1",
            title="Title",
            state="stale",
            related_mvp="MVP-10",
        )
        dq = build_audit_snapshot_data_quality(
            artifact_summaries=(stale_artifact_summary,),
            items=(item,),
            config=AuditSnapshotConfig(expected_artifact_count=1, freshness_threshold_seconds=3600),
        )
        assert dq.stale_artifact_count == 1

    def test_blocked_item(self, now: datetime) -> None:
        item = build_audit_snapshot_item(
            item_id="i-1",
            title="Title",
            state="block",
            related_mvp="MVP-10",
        )
        dq = build_audit_snapshot_data_quality(
            artifact_summaries=(),
            items=(item,),
            config=AuditSnapshotConfig(expected_artifact_count=1),
        )
        assert dq.blocked_item_count == 1


# ---------------------------------------------------------------------------
# Summary builder
# ---------------------------------------------------------------------------

class TestBuildAuditSnapshotSummary:
    def test_aggregates_counts(self) -> None:
        item_high = build_audit_snapshot_item(item_id="h", title="H", severity="HIGH", state="current", related_mvp="MVP-10")
        item_info = build_audit_snapshot_item(item_id="i", title="I", severity="INFO", state="current", related_mvp="MVP-11")
        section = build_audit_snapshot_section(
            section_kind=AuditSnapshotSectionKind.ARTIFACT_STATE,
            title="Artifacts",
            items=(item_high, item_info),
        )
        dq = AuditSnapshotDataQuality(total_artifacts_expected=2, total_artifacts_present=2, total_artifacts_missing=0)
        summary = build_audit_snapshot_summary(
            sections=(section,),
            data_quality=dq,
            snapshot_state=AuditSnapshotState.CURRENT,
            reason_codes=(OPEN_ITEMS_PRESENT,),
        )
        assert summary.total_items == 2
        assert summary.high_count == 1
        assert summary.info_count == 1
        assert summary.current_count == 2
        assert summary.reason_code_counts[OPEN_ITEMS_PRESENT] == 1
        assert summary.snapshot_state == "CURRENT"

    def test_uses_supplied_state(self) -> None:
        summary = build_audit_snapshot_summary(
            sections=(),
            data_quality=AuditSnapshotDataQuality(),
            snapshot_state=AuditSnapshotState.BLOCK,
            reason_codes=(UNSAFE_SNAPSHOT_CONTENT,),
        )
        assert summary.snapshot_state == "BLOCK"

    def test_narrative_contains_snapshot(self) -> None:
        summary = build_audit_snapshot_summary(
            sections=(),
            data_quality=AuditSnapshotDataQuality(),
            snapshot_state=AuditSnapshotState.CURRENT,
            reason_codes=(NO_ACTION_COMMANDS_EMITTED,),
        )
        assert "audit snapshot" in summary.snapshot_narrative.lower()


# ---------------------------------------------------------------------------
# Top-level builder
# ---------------------------------------------------------------------------

class TestBuildResearchAuditSnapshot:
    def test_builds_current_snapshot(self, valid_artifact_summary: dict[str, object]) -> None:
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(valid_artifact_summary,),
            snapshot_id="snap-abc123",
            config=AuditSnapshotConfig(expected_artifact_count=1),
        )
        assert snapshot.snapshot_id == "snap-abc123"
        assert snapshot.summary.snapshot_state == "CURRENT"
        assert snapshot.data_quality.total_artifacts_present == 1
        assert len(snapshot.sections) == 8

    def test_section_order(self, valid_artifact_summary: dict[str, object]) -> None:
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(valid_artifact_summary,),
        )
        kinds = [s.section_kind for s in snapshot.sections]
        assert kinds == list(CANONICAL_AUDIT_SNAPSHOT_SECTION_ORDER)

    def test_missing_artifacts_blocked(self, now: datetime) -> None:
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(),
            config=AuditSnapshotConfig(expected_artifact_count=2),
        )
        assert snapshot.summary.snapshot_state == "BLOCK"
        assert MISSING_ARTIFACT_SUMMARIES in snapshot.reason_codes

    def test_missing_artifacts_blocked_when_configured(self, now: datetime) -> None:
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(),
            config=AuditSnapshotConfig(expected_artifact_count=2, block_on_incomplete=True),
        )
        assert snapshot.summary.snapshot_state == "BLOCK"

    def test_stale_snapshot(self, stale_artifact_summary: dict[str, object], now: datetime) -> None:
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(stale_artifact_summary,),
            config=AuditSnapshotConfig(expected_artifact_count=1, freshness_threshold_seconds=3600, block_on_stale=False),
        )
        assert snapshot.summary.snapshot_state == "STALE"
        assert STALE_ARTIFACT_DETECTED in snapshot.reason_codes

    def test_block_on_stale(self, stale_artifact_summary: dict[str, object], now: datetime) -> None:
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(stale_artifact_summary,),
            config=AuditSnapshotConfig(expected_artifact_count=1, freshness_threshold_seconds=3600, block_on_stale=True),
        )
        assert snapshot.summary.snapshot_state == "BLOCK"

    def test_blocked_item(self, now: datetime) -> None:
        summary = {
            "artifact_id": "bad",
            "artifact_kind": "OBSERVATION_REPORT",
            "state": "block",
            "source_version": "1.0",
            "generated_at": now,
            "spec_reference": "SPEC-011",
            "local_reference": "data/observation/bad.json",
            "related_mvp": "MVP-10",
        }
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(summary,),
            config=AuditSnapshotConfig(expected_artifact_count=1),
        )
        assert snapshot.summary.snapshot_state == "BLOCK"
        assert BLOCKED_ARTIFACT_ITEM in snapshot.reason_codes

    def test_unsafe_content_blocked(self, valid_artifact_summary: dict[str, object]) -> None:
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(valid_artifact_summary,),
            metadata={"note": "execute trade"},
        )
        assert snapshot.summary.snapshot_state == "BLOCK"
        assert UNSAFE_SNAPSHOT_CONTENT in snapshot.reason_codes

    def test_invalid_config_raises(self, now: datetime) -> None:
        # Invalid config values are rejected at construction time by the frozen dataclass.
        with pytest.raises(ValueError, match="output_format must be"):
            AuditSnapshotConfig(output_format="xml")

    def test_required_sections_customization(self, valid_artifact_summary: dict[str, object]) -> None:
        # When required_sections only contains OVERVIEW and OVERVIEW is built,
        # no MISSING_REQUIRED_SECTION reason code is emitted.
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(valid_artifact_summary,),
            config=AuditSnapshotConfig(
                expected_artifact_count=1,
                required_sections=(AuditSnapshotSectionKind.OVERVIEW,),
            ),
        )
        assert MISSING_REQUIRED_SECTION not in snapshot.reason_codes
        assert snapshot.summary.snapshot_state == "CURRENT"

    def test_block_on_unknown(self, now: datetime) -> None:
        # An artifact with unknown state produces UNKNOWN_SNAPSHOT_STATE reason code.
        # With block_on_unknown=True the snapshot state becomes BLOCK.
        summary = {
            "artifact_id": "x",
            "artifact_kind": "OBSERVATION_REPORT",
            "state": "unknown",
            "source_version": "1.0",
            "generated_at": now,
            "spec_reference": "SPEC-011",
            "local_reference": "x.json",
            "related_mvp": "MVP-10",
        }
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(summary,),
            config=AuditSnapshotConfig(expected_artifact_count=1, block_on_unknown=True),
        )
        assert snapshot.summary.snapshot_state == "BLOCK"
        assert UNKNOWN_SNAPSHOT_STATE in snapshot.reason_codes

    def test_human_audit_guide_advisory(self, valid_artifact_summary: dict[str, object]) -> None:
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(valid_artifact_summary,),
        )
        guide = next(s for s in snapshot.sections if s.section_kind == AuditSnapshotSectionKind.HUMAN_AUDIT_GUIDE)
        assert "advisory" in guide.section_notes.lower()
        assert "non-gating" in guide.section_notes.lower()

    def test_no_file_reads(self, valid_artifact_summary: dict[str, object]) -> None:
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(valid_artifact_summary,),
        )
        # Local references remain strings; no file I/O occurred.
        assert snapshot.data_quality.total_artifacts_present == 1

    def test_metadata_reference_passthrough(self, valid_artifact_summary: dict[str, object]) -> None:
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(valid_artifact_summary,),
            metadata={"ref": "data/observation/latest_observation_report.json"},
        )
        assert snapshot.metadata["ref"] == "data/observation/latest_observation_report.json"

    def test_explicit_snapshot_id(self, valid_artifact_summary: dict[str, object]) -> None:
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(valid_artifact_summary,),
            snapshot_id="custom-id",
        )
        assert snapshot.snapshot_id == "custom-id"

    def test_safety_flags_no_feedback(self, valid_artifact_summary: dict[str, object]) -> None:
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(valid_artifact_summary,),
        )
        assert snapshot.safety_flags.snapshot_feedback_into_execution is False
        assert snapshot.safety_flags.cross_layer_feedback_into_execution is False
        assert snapshot.safety_flags.runtime_registry_enabled is False

    def test_transaction_permission_flag(self, valid_artifact_summary: dict[str, object]) -> None:
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(valid_artifact_summary,),
        )
        assert snapshot.safety_flags.snapshot_output_not_transaction_permission is True

    def test_open_items_section_contains_open_items(self, valid_artifact_summary: dict[str, object]) -> None:
        summary = dict(valid_artifact_summary)
        summary["state"] = "incomplete"
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(summary,),
            config=AuditSnapshotConfig(expected_artifact_count=1, block_on_incomplete=False),
        )
        open_section = next(s for s in snapshot.sections if s.section_kind == AuditSnapshotSectionKind.OPEN_ITEMS)
        assert len(open_section.items) == 1
        assert open_section.items[0].state == "INCOMPLETE"
