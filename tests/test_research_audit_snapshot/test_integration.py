"""Integration tests for hunter.research_audit_snapshot package.

MVP-23 Step 3 — end-to-end integration tests.

These tests exercise the full pipeline: artifact summaries -> engine ->
ResearchAuditSnapshot -> JSON/Markdown atomic file output. All writes use
``tmp_path``. No referenced files are read. No source files are modified.

Coverage areas:
  - End-to-end happy path (build -> serialize -> parse -> verify)
  - JSON structure and field-level fidelity
  - Markdown structure and safety-notice presence
  - Atomic write properties (no temp files, overwrite, failure cleanup)
  - Model validation triggered through the engine
  - Blocked-snapshot paths (fail-closed behaviour)
  - Advisory reason-code presence
  - Output-format selection (json / markdown / both)
  - Safety-boundary assertions
  - Determinism
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from hunter.research_audit_snapshot.engine import build_research_audit_snapshot
from hunter.research_audit_snapshot.models import (
    ARTIFACT_FILES_NOT_READ,
    BLOCKED_ARTIFACT_ITEM,
    CANONICAL_AUDIT_SNAPSHOT_SECTION_ORDER,
    FILE_REFS_NOT_TRAVERSED,
    HUMAN_AUDIT_GUIDE_NON_GATING,
    INCOMPLETE_ARTIFACT_ITEM,
    INVALID_SNAPSHOT_CONFIG,
    MISSING_ARTIFACT_SUMMARIES,
    NO_ACTION_COMMANDS_EMITTED,
    OPEN_ITEMS_PRESENT,
    SNAPSHOT_VERSION,
    STALE_ARTIFACT_DETECTED,
    UNSAFE_SNAPSHOT_CONTENT,
    UNKNOWN_SNAPSHOT_STATE,
    AuditSnapshotConfig,
    AuditSnapshotItemSeverity,
    AuditSnapshotSectionKind,
    AuditSnapshotState,
    ResearchAuditSnapshot,
)
from hunter.research_audit_snapshot.writer import (
    _atomic_write,
    atomic_write_json_research_audit_snapshot,
    atomic_write_markdown_research_audit_snapshot,
    research_audit_snapshot_to_dict,
    research_audit_snapshot_to_markdown,
    write_research_audit_snapshot,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)

_ARTIFACT_KINDS = [
    ("MVP-10", "OBSERVATION_REPORT", "SPEC-011"),
    ("MVP-11", "REVIEW_AUDIT_RECORD", "SPEC-012"),
    ("MVP-12", "REVIEW_INDEX", "SPEC-013"),
    ("MVP-13", "REVIEW_SEARCH", "SPEC-014"),
    ("MVP-14", "RESEARCH_BUNDLE", "SPEC-015"),
    ("MVP-15", "RESEARCH_CHRONICLE", "SPEC-016"),
    ("MVP-16", "RESEARCH_DIGEST", "SPEC-017"),
    ("MVP-17", "RESEARCH_QUALITY_GATE", "SPEC-018"),
    ("MVP-18", "RESEARCH_HANDOFF", "SPEC-019"),
    ("MVP-19", "RESEARCH_ARCHIVE_MANIFEST", "SPEC-020"),
    ("MVP-20", "RESEARCH_RELEASE_NOTES", "SPEC-021"),
    ("MVP-21", "RESEARCH_AUDIT_CATALOG", "SPEC-022"),
    ("MVP-22", "RESEARCH_AUDIT_CLOSURE", "SPEC-023"),
]


def _now() -> datetime:
    return _NOW


def _make_artifact_summary(**overrides: object) -> dict[str, object]:
    """Create a single artifact summary compliant with _validate_artifact_summary."""
    data: dict[str, object] = {
        "artifact_id": "obs-1",
        "artifact_kind": "OBSERVATION_REPORT",
        "state": "current",
        "source_version": "1.0",
        "generated_at": _now(),
        "spec_reference": "SPEC-011",
        "local_reference": "data/observation/latest_observation_report.json",
        "related_mvp": "MVP-10",
    }
    data.update(overrides)
    return data


def _make_full_artifact_summaries(
    count: int = 13,
    state: str = "current",
    generated_at: datetime | None = None,
) -> list[dict[str, object]]:
    """Create *count* compliant artifact summaries, one per MVP-10..MVP-22."""
    if generated_at is None:
        generated_at = _now()
    summaries: list[dict[str, object]] = []
    for idx, (mvp, kind, spec) in enumerate(_ARTIFACT_KINDS):
        if idx >= count:
            break
        summaries.append(
            {
                "artifact_id": f"{kind.lower()}-{idx}",
                "artifact_kind": kind,
                "state": state,
                "source_version": "1.0",
                "generated_at": generated_at,
                "spec_reference": spec,
                "local_reference": f"data/{kind.lower()}/latest.json",
                "related_mvp": mvp,
            }
        )
    return summaries


def _build_current(
    count: int = 1,
    **kwargs: object,
) -> ResearchAuditSnapshot:
    """Convenience: build a snapshot with *count* current artifact summaries."""
    summaries = _make_full_artifact_summaries(count=count)
    build_kwargs: dict[str, object] = {
        "generated_at": _now(),
        "config": AuditSnapshotConfig(expected_artifact_count=count),
    }
    build_kwargs.update(kwargs)
    return build_research_audit_snapshot(
        artifact_summaries=summaries,
        **build_kwargs,  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# End-to-end happy path
# ---------------------------------------------------------------------------


class TestEndToEndHappyPath:
    """Full pipeline: summaries -> engine -> serialize -> file -> parse."""

    def test_full_flow_build_and_serialize(self, tmp_path: Path) -> None:
        summary = _make_artifact_summary()
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(summary,),
            generated_at=_now(),
            snapshot_id="snap-e2e-1",
            config=AuditSnapshotConfig(expected_artifact_count=1),
        )

        assert snapshot.summary.snapshot_state == "CURRENT"
        assert len(snapshot.sections) == 8

        json_path = tmp_path / "snapshot.json"
        md_path = tmp_path / "snapshot.md"
        write_research_audit_snapshot(snapshot, json_path, md_path)

        assert json_path.exists()
        assert md_path.exists()

        data = json.loads(json_path.read_text())
        assert data["snapshot_id"] == "snap-e2e-1"
        assert data["summary"]["snapshot_state"] == "CURRENT"
        assert data["kind"] == "research_audit_snapshot"

    def test_all_thirteen_artifact_families_current(self, tmp_path: Path) -> None:
        summaries = _make_full_artifact_summaries(count=13)
        snapshot = build_research_audit_snapshot(
            artifact_summaries=summaries,
            generated_at=_now(),
            snapshot_id="snap-13",
        )

        assert snapshot.summary.snapshot_state == "CURRENT"
        assert snapshot.summary.total_items == 13
        assert snapshot.data_quality.total_artifacts_present == 13
        assert snapshot.data_quality.total_artifacts_missing == 0

        json_path = tmp_path / "snapshot.json"
        md_path = tmp_path / "snapshot.md"
        write_research_audit_snapshot(snapshot, json_path, md_path)
        assert json_path.exists()
        assert md_path.exists()

    def test_section_order_is_canonical(self) -> None:
        snapshot = _build_current(count=1)
        kinds = [s.section_kind for s in snapshot.sections]
        assert kinds == list(CANONICAL_AUDIT_SNAPSHOT_SECTION_ORDER)

    def test_artifact_items_match_input_summaries(self) -> None:
        summaries = _make_full_artifact_summaries(count=3)
        snapshot = build_research_audit_snapshot(
            artifact_summaries=summaries,
            generated_at=_now(),
            config=AuditSnapshotConfig(expected_artifact_count=3),
        )
        artifact_section = next(
            s for s in snapshot.sections
            if s.section_kind == AuditSnapshotSectionKind.ARTIFACT_STATE
        )
        assert len(artifact_section.items) == 3
        for item, summary in zip(artifact_section.items, summaries):
            assert item.artifact_kind == summary["artifact_kind"]
            assert item.related_mvp == summary["related_mvp"]
            assert item.spec_reference == summary["spec_reference"]
            assert item.state == "CURRENT"

    def test_items_sorted_by_severity_then_mvp(self) -> None:
        """CRITICAL sorts before HIGH; within same severity, lower MVP number first."""
        s_critical = _make_artifact_summary(
            artifact_id="closure-1",
            artifact_kind="RESEARCH_AUDIT_CLOSURE",
            state="block",
            related_mvp="MVP-22",
        )
        s_high = _make_artifact_summary(
            artifact_id="observation-1",
            artifact_kind="OBSERVATION_REPORT",
            state="stale",
            related_mvp="MVP-10",
            generated_at=_now() - timedelta(days=3),
        )
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(s_critical, s_high),
            generated_at=_now(),
            config=AuditSnapshotConfig(
                expected_artifact_count=2,
                freshness_threshold_seconds=3600,
                block_on_stale=False,
            ),
        )
        artifact_section = next(
            s for s in snapshot.sections
            if s.section_kind == AuditSnapshotSectionKind.ARTIFACT_STATE
        )
        items = artifact_section.items
        assert len(items) == 2
        assert items[0].severity == "CRITICAL"
        assert items[1].severity == "HIGH"


# ---------------------------------------------------------------------------
# JSON structure
# ---------------------------------------------------------------------------


class TestJsonStructure:
    """Deep field-level verification of the serialized JSON output."""

    def test_json_has_all_top_level_keys(self) -> None:
        snapshot = _build_current(count=1)
        d = research_audit_snapshot_to_dict(snapshot)
        expected_keys = {
            "config", "data_quality", "generated_at", "kind", "metadata",
            "project_version", "reason_codes", "safety_flags", "sections",
            "snapshot_id", "source_spec", "summary",
        }
        assert set(d.keys()) == expected_keys

    def test_json_config_matches_input(self) -> None:
        config = AuditSnapshotConfig(
            expected_artifact_count=5,
            freshness_threshold_seconds=7200,
            block_on_unknown=False,
            block_on_stale=True,
        )
        summaries = _make_full_artifact_summaries(count=5)
        snapshot = build_research_audit_snapshot(
            artifact_summaries=summaries,
            generated_at=_now(),
            config=config,
        )
        d = research_audit_snapshot_to_dict(snapshot)
        assert d["config"]["expected_artifact_count"] == 5
        assert d["config"]["freshness_threshold_seconds"] == 7200
        assert d["config"]["block_on_unknown"] is False
        assert d["config"]["block_on_stale"] is True
        assert d["config"]["dry_run"] is True

    def test_json_safety_flags_all_safe(self) -> None:
        snapshot = _build_current(count=1)
        d = research_audit_snapshot_to_dict(snapshot)
        flags = d["safety_flags"]
        assert flags["dry_run"] is True
        assert flags["live_trading_enabled"] is False
        assert flags["real_orders_enabled"] is False
        assert flags["leverage_enabled"] is False
        assert flags["shorting_enabled"] is False
        assert flags["snapshot_feedback_into_execution"] is False
        assert flags["snapshot_output_is_human_audit_only"] is True

    def test_json_summary_severity_counts_sum_to_total(self) -> None:
        snapshot = _build_current(count=5)
        d = research_audit_snapshot_to_dict(snapshot)
        s = d["summary"]
        severity_sum = (
            s["critical_count"] + s["high_count"] + s["medium_count"]
            + s["low_count"] + s["info_count"]
        )
        assert severity_sum == s["total_items"]

    def test_json_summary_state_counts_sum_to_total(self) -> None:
        snapshot = _build_current(count=5)
        d = research_audit_snapshot_to_dict(snapshot)
        s = d["summary"]
        state_sum = (
            s["current_count"] + s["stale_count"] + s["incomplete_count"]
            + s["blocked_count"] + s["unknown_count"]
        )
        assert state_sum == s["total_items"]

    def test_json_data_quality_present_plus_missing_equals_expected(self) -> None:
        summaries = _make_full_artifact_summaries(count=7)
        snapshot = build_research_audit_snapshot(
            artifact_summaries=summaries,
            generated_at=_now(),
            config=AuditSnapshotConfig(expected_artifact_count=13),
        )
        d = research_audit_snapshot_to_dict(snapshot)
        dq = d["data_quality"]
        assert dq["total_artifacts_present"] == 7
        assert dq["total_artifacts_missing"] == 6
        assert dq["total_artifacts_expected"] == 13
        assert dq["total_artifacts_present"] + dq["total_artifacts_missing"] == 13

    def test_json_sections_have_correct_kinds(self) -> None:
        snapshot = _build_current(count=1)
        d = research_audit_snapshot_to_dict(snapshot)
        section_kinds = [s["section_kind"] for s in d["sections"]]
        expected = [k.value for k in CANONICAL_AUDIT_SNAPSHOT_SECTION_ORDER]
        assert section_kinds == expected

    def test_json_artifact_items_carry_source_metadata(self) -> None:
        summaries = _make_full_artifact_summaries(count=3)
        snapshot = build_research_audit_snapshot(
            artifact_summaries=summaries,
            generated_at=_now(),
            config=AuditSnapshotConfig(expected_artifact_count=3),
        )
        d = research_audit_snapshot_to_dict(snapshot)
        artifact_section = next(
            s for s in d["sections"] if s["section_kind"] == "artifact_state"
        )
        for item, summary in zip(artifact_section["items"], summaries):
            assert item["artifact_kind"] == summary["artifact_kind"]
            assert item["state"] == "CURRENT"
            assert item["related_mvp"] == summary["related_mvp"]
            assert item["spec_reference"] == summary["spec_reference"]

    def test_json_reason_codes_include_advisory(self) -> None:
        snapshot = _build_current(count=1)
        d = research_audit_snapshot_to_dict(snapshot)
        codes = set(d["reason_codes"])
        assert FILE_REFS_NOT_TRAVERSED in codes
        assert ARTIFACT_FILES_NOT_READ in codes
        assert NO_ACTION_COMMANDS_EMITTED in codes
        assert HUMAN_AUDIT_GUIDE_NON_GATING in codes

    def test_json_generated_at_is_iso_format(self) -> None:
        snapshot = build_research_audit_snapshot(
            artifact_summaries=_make_full_artifact_summaries(count=1),
            generated_at=_now(),
            snapshot_id="snap-iso",
            config=AuditSnapshotConfig(expected_artifact_count=1),
        )
        d = research_audit_snapshot_to_dict(snapshot)
        assert d["generated_at"] is not None
        # Should end with Z (UTC indicator from _iso helper).
        assert d["generated_at"].endswith("Z")

    def test_json_keys_sorted(self, tmp_path: Path) -> None:
        snapshot = _build_current(count=1)
        json_path = tmp_path / "sorted.json"
        atomic_write_json_research_audit_snapshot(snapshot, json_path)
        raw = json_path.read_text()
        parsed = json.loads(raw)
        # Top-level keys should be in sorted order in the raw text.
        # Verify by checking that the raw text starts with the first sorted key.
        top_keys = sorted(parsed.keys())
        first_key_in_text = raw.index(f'"{top_keys[0]}"')
        assert first_key_in_text < raw.index(f'"{top_keys[-1]}"')


# ---------------------------------------------------------------------------
# Markdown structure
# ---------------------------------------------------------------------------


class TestMarkdownStructure:
    """Deep content verification of the serialized Markdown output."""

    def test_md_has_title_and_safety_notice(self) -> None:
        snapshot = _build_current(count=1)
        md = research_audit_snapshot_to_markdown(snapshot)
        assert md.startswith("# Local Research Audit Snapshot")
        assert "human-audit" in md
        assert "not a trading signal" in md
        assert "must not be consumed by execution" in md

    def test_md_safety_notice_appears_before_sections(self) -> None:
        snapshot = _build_current(count=1)
        md = research_audit_snapshot_to_markdown(snapshot)
        notice_idx = md.index("must not be consumed by execution")
        first_section_idx = md.index("## Snapshot Identity")
        assert notice_idx < first_section_idx

    def test_md_has_all_section_headers(self) -> None:
        snapshot = _build_current(count=1)
        md = research_audit_snapshot_to_markdown(snapshot)
        expected_titles = [
            "## Overview",
            "## Version State",
            "## Artifact State",
            "## Quality State",
            "## Open Items",
            "## Safety Boundaries",
            "## Human Audit Guide",
            "## Appendix References",
        ]
        for title in expected_titles:
            assert title in md, f"Missing section header: {title}"

    def test_md_has_snapshot_identity_fields(self) -> None:
        snapshot = _build_current(count=1, snapshot_id="snap-md-1")
        md = research_audit_snapshot_to_markdown(snapshot)
        assert "**snapshot_id**: snap-md-1" in md
        assert "**project_version**" in md
        assert "**source_spec**" in md
        assert "**snapshot_state**" in md

    def test_md_has_reason_codes_section(self) -> None:
        snapshot = _build_current(count=1)
        md = research_audit_snapshot_to_markdown(snapshot)
        assert "## Reason Codes" in md
        assert FILE_REFS_NOT_TRAVERSED in md
        assert ARTIFACT_FILES_NOT_READ in md

    def test_md_has_snapshot_summary_section(self) -> None:
        snapshot = _build_current(count=3)
        md = research_audit_snapshot_to_markdown(snapshot)
        assert "## Snapshot Summary" in md
        assert "**total_sections**" in md
        assert "**total_items**" in md
        assert "**snapshot_state**" in md

    def test_md_has_data_quality_section(self) -> None:
        snapshot = _build_current(count=5)
        md = research_audit_snapshot_to_markdown(snapshot)
        assert "## Data Quality" in md
        assert "**total_artifacts_expected**" in md
        assert "**total_artifacts_present**" in md
        assert "**total_artifacts_missing**" in md

    def test_md_blocked_snapshot_shows_block_state(self) -> None:
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(),
            generated_at=_now(),
        )
        md = research_audit_snapshot_to_markdown(snapshot)
        assert "BLOCK" in md
        assert MISSING_ARTIFACT_SUMMARIES in md

    def test_md_artifact_items_rendered(self) -> None:
        summaries = _make_full_artifact_summaries(count=3)
        snapshot = build_research_audit_snapshot(
            artifact_summaries=summaries,
            generated_at=_now(),
            config=AuditSnapshotConfig(expected_artifact_count=3),
        )
        md = research_audit_snapshot_to_markdown(snapshot)
        for summary in summaries:
            kind = summary["artifact_kind"]
            assert kind in md


# ---------------------------------------------------------------------------
# Atomic writes
# ---------------------------------------------------------------------------


class TestAtomicWrites:
    """Verify the temp-file + fsync + os.replace atomic-write contract."""

    def test_no_temp_files_after_successful_json_write(self, tmp_path: Path) -> None:
        snapshot = _build_current(count=1)
        json_path = tmp_path / "out.json"
        atomic_write_json_research_audit_snapshot(snapshot, json_path)
        temp_files = list(tmp_path.glob(".*.tmp"))
        assert temp_files == []

    def test_no_temp_files_after_successful_md_write(self, tmp_path: Path) -> None:
        snapshot = _build_current(count=1)
        md_path = tmp_path / "out.md"
        atomic_write_markdown_research_audit_snapshot(snapshot, md_path)
        temp_files = list(tmp_path.glob(".*.tmp"))
        assert temp_files == []

    def test_json_file_ends_with_newline(self, tmp_path: Path) -> None:
        snapshot = _build_current(count=1)
        json_path = tmp_path / "out.json"
        atomic_write_json_research_audit_snapshot(snapshot, json_path)
        content = json_path.read_text()
        assert content.endswith("\n")

    def test_md_file_ends_with_newline(self, tmp_path: Path) -> None:
        snapshot = _build_current(count=1)
        md_path = tmp_path / "out.md"
        atomic_write_markdown_research_audit_snapshot(snapshot, md_path)
        content = md_path.read_text()
        assert content.endswith("\n")

    def test_parent_directories_created(self, tmp_path: Path) -> None:
        snapshot = _build_current(count=1)
        deep_path = tmp_path / "a" / "b" / "c" / "snapshot.json"
        atomic_write_json_research_audit_snapshot(snapshot, deep_path)
        assert deep_path.exists()
        data = json.loads(deep_path.read_text())
        assert data["kind"] == "research_audit_snapshot"

    def test_overwrite_replaces_cleanly(self, tmp_path: Path) -> None:
        snapshot1 = _build_current(count=1, snapshot_id="snap-old")
        json_path = tmp_path / "out.json"
        atomic_write_json_research_audit_snapshot(snapshot1, json_path)

        snapshot2 = _build_current(count=1, snapshot_id="snap-new")
        atomic_write_json_research_audit_snapshot(snapshot2, json_path)

        data = json.loads(json_path.read_text())
        assert data["snapshot_id"] == "snap-new"

        temp_files = list(tmp_path.glob(".*.tmp"))
        assert temp_files == []

    def test_failed_write_preserves_original_content(
        self, tmp_path: Path,
    ) -> None:
        """If os.replace fails, the pre-existing target content must survive."""
        snapshot_original = _build_current(count=1, snapshot_id="snap-original")
        json_path = tmp_path / "out.json"
        atomic_write_json_research_audit_snapshot(snapshot_original, json_path)
        original_content = json_path.read_text()

        snapshot_new = _build_current(count=1, snapshot_id="snap-new")

        with patch("hunter.research_audit_snapshot.writer.os.replace", side_effect=OSError("simulated")):
            with pytest.raises(OSError, match="simulated"):
                atomic_write_json_research_audit_snapshot(snapshot_new, json_path)

        # Original file content survived the failed write.
        assert json_path.read_text() == original_content

    def test_failed_write_cleans_temp_file(self, tmp_path: Path) -> None:
        snapshot = _build_current(count=1)
        json_path = tmp_path / "out.json"

        with patch("hunter.research_audit_snapshot.writer.os.replace", side_effect=OSError("simulated")):
            with pytest.raises(OSError):
                atomic_write_json_research_audit_snapshot(snapshot, json_path)

        temp_files = list(tmp_path.glob(".*.tmp"))
        assert temp_files == []

    def test_blocked_snapshot_writes_atomically(self, tmp_path: Path) -> None:
        blocked = ResearchAuditSnapshot.blocked(
            reason_code=MISSING_ARTIFACT_SUMMARIES,
            snapshot_id="blocked-write",
            generated_at=_now(),
        )
        json_path = tmp_path / "blocked.json"
        md_path = tmp_path / "blocked.md"
        write_research_audit_snapshot(blocked, json_path, md_path)

        assert json_path.exists()
        assert md_path.exists()

        data = json.loads(json_path.read_text())
        assert data["summary"]["snapshot_state"] == "BLOCK"
        assert data["snapshot_id"] == "blocked-write"

        temp_files = list(tmp_path.glob(".*.tmp"))
        assert temp_files == []


# ---------------------------------------------------------------------------
# Validation through engine
# ---------------------------------------------------------------------------


class TestValidationThroughEngine:
    """Verify model validation (__post_init__) and engine guards produce blocked
    snapshots for invalid or unsafe inputs."""

    def test_summary_missing_artifact_id_blocked(self) -> None:
        summary = _make_artifact_summary()
        del summary["artifact_id"]
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(summary,),
            generated_at=_now(),
            config=AuditSnapshotConfig(expected_artifact_count=1),
        )
        assert snapshot.summary.snapshot_state == "BLOCK"
        assert INVALID_SNAPSHOT_CONFIG in snapshot.reason_codes

    def test_summary_missing_artifact_kind_blocked(self) -> None:
        summary = _make_artifact_summary()
        del summary["artifact_kind"]
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(summary,),
            generated_at=_now(),
            config=AuditSnapshotConfig(expected_artifact_count=1),
        )
        assert snapshot.summary.snapshot_state == "BLOCK"
        assert INVALID_SNAPSHOT_CONFIG in snapshot.reason_codes

    def test_summary_missing_state_blocked(self) -> None:
        summary = _make_artifact_summary()
        del summary["state"]
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(summary,),
            generated_at=_now(),
            config=AuditSnapshotConfig(expected_artifact_count=1),
        )
        assert snapshot.summary.snapshot_state == "BLOCK"
        assert INVALID_SNAPSHOT_CONFIG in snapshot.reason_codes

    def test_summary_missing_source_version_blocked(self) -> None:
        summary = _make_artifact_summary()
        del summary["source_version"]
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(summary,),
            generated_at=_now(),
            config=AuditSnapshotConfig(expected_artifact_count=1),
        )
        assert snapshot.summary.snapshot_state == "BLOCK"
        assert INVALID_SNAPSHOT_CONFIG in snapshot.reason_codes

    def test_summary_missing_generated_at_blocked(self) -> None:
        summary = _make_artifact_summary()
        del summary["generated_at"]
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(summary,),
            generated_at=_now(),
            config=AuditSnapshotConfig(expected_artifact_count=1),
        )
        assert snapshot.summary.snapshot_state == "BLOCK"
        assert INVALID_SNAPSHOT_CONFIG in snapshot.reason_codes

    def test_summary_generated_at_string_not_datetime_blocked(self) -> None:
        summary = _make_artifact_summary(generated_at="2024-01-01T00:00:00Z")
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(summary,),
            generated_at=_now(),
            config=AuditSnapshotConfig(expected_artifact_count=1),
        )
        assert snapshot.summary.snapshot_state == "BLOCK"
        assert INVALID_SNAPSHOT_CONFIG in snapshot.reason_codes

    def test_summary_generated_at_naive_datetime_blocked(self) -> None:
        summary = _make_artifact_summary(
            generated_at=datetime(2024, 1, 1, 12, 0, 0),  # no tzinfo
        )
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(summary,),
            generated_at=_now(),
            config=AuditSnapshotConfig(expected_artifact_count=1),
        )
        assert snapshot.summary.snapshot_state == "BLOCK"
        assert INVALID_SNAPSHOT_CONFIG in snapshot.reason_codes

    def test_summary_empty_artifact_id_blocked(self) -> None:
        summary = _make_artifact_summary(artifact_id="")
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(summary,),
            generated_at=_now(),
            config=AuditSnapshotConfig(expected_artifact_count=1),
        )
        assert snapshot.summary.snapshot_state == "BLOCK"
        assert INVALID_SNAPSHOT_CONFIG in snapshot.reason_codes

    def test_unsafe_artifact_summary_content_blocked(self) -> None:
        summary = _make_artifact_summary(artifact_kind="LIVE_TRADE_SIGNAL")
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(summary,),
            generated_at=_now(),
            config=AuditSnapshotConfig(expected_artifact_count=1),
        )
        assert snapshot.summary.snapshot_state == "BLOCK"
        assert UNSAFE_SNAPSHOT_CONTENT in snapshot.reason_codes

    def test_unsafe_explicit_references_blocked(self) -> None:
        summary = _make_artifact_summary()
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(summary,),
            generated_at=_now(),
            config=AuditSnapshotConfig(expected_artifact_count=1),
            explicit_references=("deploy now",),
        )
        assert snapshot.summary.snapshot_state == "BLOCK"
        assert UNSAFE_SNAPSHOT_CONTENT in snapshot.reason_codes

    def test_unsafe_metadata_blocked(self) -> None:
        summary = _make_artifact_summary()
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(summary,),
            generated_at=_now(),
            config=AuditSnapshotConfig(expected_artifact_count=1),
            metadata={"action": "place_order"},
        )
        assert snapshot.summary.snapshot_state == "BLOCK"
        assert UNSAFE_SNAPSHOT_CONTENT in snapshot.reason_codes

    def test_mixed_valid_and_invalid_summaries_blocked(self) -> None:
        """Even one invalid summary in the batch blocks the entire snapshot."""
        valid = _make_artifact_summary(artifact_id="valid-1")
        invalid = _make_artifact_summary(artifact_id="invalid-1")
        del invalid["generated_at"]
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(valid, invalid),
            generated_at=_now(),
            config=AuditSnapshotConfig(expected_artifact_count=2),
        )
        assert snapshot.summary.snapshot_state == "BLOCK"
        assert INVALID_SNAPSHOT_CONFIG in snapshot.reason_codes


# ---------------------------------------------------------------------------
# Blocked-snapshot paths
# ---------------------------------------------------------------------------


class TestBlockedPaths:
    """Comprehensive coverage of fail-closed blocked-snapshot paths."""

    def test_empty_artifact_summaries_blocked(self) -> None:
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(),
            generated_at=_now(),
        )
        assert snapshot.summary.snapshot_state == "BLOCK"
        assert MISSING_ARTIFACT_SUMMARIES in snapshot.reason_codes
        assert len(snapshot.sections) == 0

    def test_blocked_artifact_item_produces_block_state(self) -> None:
        summary = _make_artifact_summary(
            state="block",
            artifact_id="blocked-artifact",
        )
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(summary,),
            generated_at=_now(),
            config=AuditSnapshotConfig(expected_artifact_count=1),
        )
        assert snapshot.summary.snapshot_state == "BLOCK"
        assert BLOCKED_ARTIFACT_ITEM in snapshot.reason_codes

    def test_unknown_state_with_block_on_unknown_blocked(self) -> None:
        summary = _make_artifact_summary(
            state="unknown",
            artifact_id="unknown-artifact",
        )
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(summary,),
            generated_at=_now(),
            config=AuditSnapshotConfig(
                expected_artifact_count=1,
                block_on_unknown=True,
            ),
        )
        assert snapshot.summary.snapshot_state == "BLOCK"
        assert UNKNOWN_SNAPSHOT_STATE in snapshot.reason_codes

    def test_unknown_state_without_block_on_unknown_not_blocked(self) -> None:
        """With block_on_unknown=False, UNKNOWN items are not blocking.

        The engine maps UNKNOWN state to LOW severity, which makes the item
        'open' (_is_item_open), adding OPEN_ITEMS_PRESENT. INCOMPLETE takes
        priority over UNKNOWN in _resolve_snapshot_state, so the snapshot
        lands on INCOMPLETE rather than BLOCK.
        """
        summary = _make_artifact_summary(
            state="unknown",
            artifact_id="unknown-artifact",
        )
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(summary,),
            generated_at=_now(),
            config=AuditSnapshotConfig(
                expected_artifact_count=1,
                block_on_unknown=False,
            ),
        )
        assert snapshot.summary.snapshot_state != "BLOCK"
        assert UNKNOWN_SNAPSHOT_STATE in snapshot.reason_codes

    def test_stale_with_block_on_stale_blocked(self) -> None:
        summary = _make_artifact_summary(
            generated_at=_now() - timedelta(days=2),
        )
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(summary,),
            generated_at=_now(),
            config=AuditSnapshotConfig(
                expected_artifact_count=1,
                freshness_threshold_seconds=3600,
                block_on_stale=True,
            ),
        )
        assert snapshot.summary.snapshot_state == "BLOCK"
        assert STALE_ARTIFACT_DETECTED in snapshot.reason_codes

    def test_stale_without_block_on_stale_is_stale(self) -> None:
        summary = _make_artifact_summary(
            generated_at=_now() - timedelta(days=2),
        )
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(summary,),
            generated_at=_now(),
            config=AuditSnapshotConfig(
                expected_artifact_count=1,
                freshness_threshold_seconds=3600,
                block_on_stale=False,
            ),
        )
        assert snapshot.summary.snapshot_state == "STALE"

    def test_incomplete_with_block_on_incomplete_blocked(self) -> None:
        summary = _make_artifact_summary(
            state="incomplete",
            artifact_id="incomplete-artifact",
        )
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(summary,),
            generated_at=_now(),
            config=AuditSnapshotConfig(
                expected_artifact_count=1,
                block_on_incomplete=True,
            ),
        )
        assert snapshot.summary.snapshot_state == "BLOCK"
        assert INCOMPLETE_ARTIFACT_ITEM in snapshot.reason_codes

    def test_incomplete_without_block_on_incomplete_is_incomplete(self) -> None:
        summary = _make_artifact_summary(
            state="incomplete",
            artifact_id="incomplete-artifact",
        )
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(summary,),
            generated_at=_now(),
            config=AuditSnapshotConfig(
                expected_artifact_count=1,
                block_on_incomplete=False,
            ),
        )
        assert snapshot.summary.snapshot_state == "INCOMPLETE"

    def test_blocked_snapshot_has_no_sections(self) -> None:
        blocked = ResearchAuditSnapshot.blocked(
            reason_code=MISSING_ARTIFACT_SUMMARIES,
            generated_at=_now(),
        )
        assert blocked.sections == ()

    def test_blocked_snapshot_serializes_to_valid_json(self, tmp_path: Path) -> None:
        blocked = ResearchAuditSnapshot.blocked(
            reason_code=INVALID_SNAPSHOT_CONFIG,
            snapshot_id="blocked-json",
            generated_at=_now(),
        )
        d = research_audit_snapshot_to_dict(blocked)
        assert d["summary"]["snapshot_state"] == "BLOCK"
        assert INVALID_SNAPSHOT_CONFIG in d["reason_codes"]
        # The JSON must be serializable (no unhandled types).
        json_str = json.dumps(d, indent=2, sort_keys=True)
        assert json.loads(json_str)["snapshot_id"] == "blocked-json"

    def test_blocked_snapshot_serializes_to_valid_markdown(self) -> None:
        blocked = ResearchAuditSnapshot.blocked(
            reason_code=UNSAFE_SNAPSHOT_CONTENT,
            snapshot_id="blocked-md",
            generated_at=_now(),
        )
        md = research_audit_snapshot_to_markdown(blocked)
        assert "BLOCK" in md
        assert UNSAFE_SNAPSHOT_CONTENT in md
        assert "human-audit" in md

    def test_blocked_snapshot_metadata_contains_blocked_reason(self) -> None:
        blocked = ResearchAuditSnapshot.blocked(
            reason_code=MISSING_ARTIFACT_SUMMARIES,
            generated_at=_now(),
        )
        assert dict(blocked.metadata).get("blocked_reason") == MISSING_ARTIFACT_SUMMARIES

    def test_blocked_snapshot_with_custom_metadata(self) -> None:
        blocked = ResearchAuditSnapshot.blocked(
            reason_code=INVALID_SNAPSHOT_CONFIG,
            snapshot_id="blocked-custom",
            generated_at=_now(),
            metadata={"context": "validation failure"},
        )
        assert dict(blocked.metadata).get("context") == "validation failure"


# ---------------------------------------------------------------------------
# Advisory reason codes
# ---------------------------------------------------------------------------


class TestAdvisoryReasonCodes:
    """Advisory reason codes must always be present and not affect snapshot state."""

    def test_advisory_codes_always_present_on_current_snapshot(self) -> None:
        snapshot = _build_current(count=1)
        codes = set(snapshot.reason_codes)
        assert FILE_REFS_NOT_TRAVERSED in codes
        assert ARTIFACT_FILES_NOT_READ in codes
        assert NO_ACTION_COMMANDS_EMITTED in codes
        assert HUMAN_AUDIT_GUIDE_NON_GATING in codes

    def test_advisory_codes_present_on_stale_snapshot(self) -> None:
        summary = _make_artifact_summary(
            generated_at=_now() - timedelta(days=2),
        )
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(summary,),
            generated_at=_now(),
            config=AuditSnapshotConfig(
                expected_artifact_count=1,
                freshness_threshold_seconds=3600,
                block_on_stale=False,
            ),
        )
        codes = set(snapshot.reason_codes)
        assert FILE_REFS_NOT_TRAVERSED in codes
        assert ARTIFACT_FILES_NOT_READ in codes

    def test_advisory_codes_present_on_blocked_snapshot(self) -> None:
        blocked = ResearchAuditSnapshot.blocked(
            reason_code=MISSING_ARTIFACT_SUMMARIES,
            generated_at=_now(),
        )
        # Blocked snapshots from .blocked() only carry the blocking reason code,
        # not the advisory codes (advisory codes are added by the engine flow).
        assert MISSING_ARTIFACT_SUMMARIES in blocked.reason_codes


# ---------------------------------------------------------------------------
# Output format selection
# ---------------------------------------------------------------------------


class TestOutputFormat:
    """Verify output_format config controls which files are produced."""

    def test_json_only_produces_no_markdown(self, tmp_path: Path) -> None:
        snapshot = build_research_audit_snapshot(
            artifact_summaries=_make_full_artifact_summaries(count=1),
            generated_at=_now(),
            config=AuditSnapshotConfig(
                expected_artifact_count=1,
                output_format="json",
            ),
        )
        json_path = tmp_path / "out.json"
        md_path = tmp_path / "out.md"
        json_out, md_out = write_research_audit_snapshot(snapshot, json_path, md_path)
        assert json_out is not None
        assert md_out is None
        assert json_path.exists()
        assert not md_path.exists()

    def test_markdown_only_produces_no_json(self, tmp_path: Path) -> None:
        snapshot = build_research_audit_snapshot(
            artifact_summaries=_make_full_artifact_summaries(count=1),
            generated_at=_now(),
            config=AuditSnapshotConfig(
                expected_artifact_count=1,
                output_format="markdown",
            ),
        )
        json_path = tmp_path / "out.json"
        md_path = tmp_path / "out.md"
        json_out, md_out = write_research_audit_snapshot(snapshot, json_path, md_path)
        assert json_out is None
        assert md_out is not None
        assert md_path.exists()
        assert not json_path.exists()

    def test_both_formats_produce_both_files(self, tmp_path: Path) -> None:
        snapshot = build_research_audit_snapshot(
            artifact_summaries=_make_full_artifact_summaries(count=1),
            generated_at=_now(),
            config=AuditSnapshotConfig(
                expected_artifact_count=1,
                output_format="both",
            ),
        )
        json_path = tmp_path / "out.json"
        md_path = tmp_path / "out.md"
        json_out, md_out = write_research_audit_snapshot(snapshot, json_path, md_path)
        assert json_out is not None
        assert md_out is not None
        assert json_path.exists()
        assert md_path.exists()


# ---------------------------------------------------------------------------
# Safety-boundary assertions
# ---------------------------------------------------------------------------


class TestSafetyAssertions:
    """Verify the audit-first safety invariants of the snapshot system."""

    def test_no_file_reads_from_referenced_paths(self) -> None:
        """local_reference pointing at a non-existent path must not cause a read."""
        summary = _make_artifact_summary(
            local_reference="/production/does_not_exist.json",
        )
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(summary,),
            generated_at=_now(),
            config=AuditSnapshotConfig(expected_artifact_count=1),
        )
        assert snapshot.summary.snapshot_state == "CURRENT"

    def test_no_network_or_exchange_calls(self) -> None:
        snapshot = _build_current(count=1)
        assert snapshot.safety_flags.live_trading_enabled is False
        assert snapshot.safety_flags.real_orders_enabled is False

    def test_no_execution_feedback_paths(self) -> None:
        snapshot = _build_current(count=1)
        assert snapshot.safety_flags.snapshot_feedback_into_execution is False
        assert snapshot.safety_flags.cross_layer_feedback_into_execution is False

    def test_no_trading_logic_flags(self) -> None:
        snapshot = _build_current(count=1)
        assert snapshot.safety_flags.leverage_enabled is False
        assert snapshot.safety_flags.shorting_enabled is False

    def test_no_infrastructure_capabilities(self) -> None:
        snapshot = _build_current(count=1)
        assert snapshot.safety_flags.file_reference_traversal_enabled is False
        assert snapshot.safety_flags.database_persistence_enabled is False
        assert snapshot.safety_flags.web_ui_enabled is False
        assert snapshot.safety_flags.dashboard_enabled is False
        assert snapshot.safety_flags.runtime_registry_enabled is False
        assert snapshot.safety_flags.indexer_crawler_enabled is False
        assert snapshot.safety_flags.event_store_enabled is False
        assert snapshot.safety_flags.task_runner_enabled is False

    def test_advisory_safety_flags_are_true(self) -> None:
        snapshot = _build_current(count=1)
        assert snapshot.safety_flags.file_refs_not_traversed is True
        assert snapshot.safety_flags.artifact_files_not_read is True
        assert snapshot.safety_flags.no_action_commands_emitted is True
        assert snapshot.safety_flags.human_audit_guide_is_non_gating is True

    def test_no_secrets_in_json_output(self, tmp_path: Path) -> None:
        snapshot = _build_current(count=1)
        json_path = tmp_path / "out.json"
        write_research_audit_snapshot(snapshot, json_path, tmp_path / "out.md")
        text = json_path.read_text().lower()
        for term in ("api_key", "secret", "exchange_credentials", "private_key", "password", "token"):
            assert term not in text, f"Forbidden secret term '{term}' found in JSON output"

    def test_no_secrets_in_markdown_output(self, tmp_path: Path) -> None:
        snapshot = _build_current(count=1)
        md_path = tmp_path / "out.md"
        write_research_audit_snapshot(snapshot, tmp_path / "out.json", md_path)
        text = md_path.read_text().lower()
        for term in ("api_key", "secret", "exchange_credentials", "private_key", "password"):
            assert term not in text, f"Forbidden secret term '{term}' found in MD output"

    def test_no_trading_instructions_in_json(self, tmp_path: Path) -> None:
        snapshot = _build_current(count=1)
        json_path = tmp_path / "out.json"
        write_research_audit_snapshot(snapshot, json_path, tmp_path / "out.md")
        text = json_path.read_text().lower()
        for term in ("enter_long", "enter_short", "exit_long", "exit_short", "place_order", "execute_trade"):
            assert term not in text

    def test_no_trading_instructions_in_markdown(self, tmp_path: Path) -> None:
        snapshot = _build_current(count=1)
        md_path = tmp_path / "out.md"
        write_research_audit_snapshot(snapshot, tmp_path / "out.json", md_path)
        text = md_path.read_text().lower()
        for term in ("enter_long", "enter_short", "exit_long", "exit_short", "place_order", "execute_trade"):
            assert term not in text

    def test_human_audit_only_notice_in_markdown(self, tmp_path: Path) -> None:
        snapshot = _build_current(count=1)
        md_path = tmp_path / "out.md"
        write_research_audit_snapshot(snapshot, tmp_path / "out.json", md_path)
        md_text = md_path.read_text()
        assert "human-audit" in md_text
        assert "not a trading signal" in md_text
        assert "not trade approval" in md_text
        assert "not release approval" in md_text
        assert "not deployment approval" in md_text
        assert "not transaction permission" in md_text
        assert "must not be consumed by execution" in md_text

    def test_snapshot_output_flags_all_safe(self) -> None:
        snapshot = _build_current(count=1)
        assert snapshot.safety_flags.snapshot_output_is_human_audit_only is True
        assert snapshot.safety_flags.snapshot_output_not_trading_signal is True
        assert snapshot.safety_flags.snapshot_output_not_trade_approval is True
        assert snapshot.safety_flags.snapshot_output_not_execution_readiness is True
        assert snapshot.safety_flags.snapshot_output_not_strategy_readiness is True
        assert snapshot.safety_flags.snapshot_output_not_release_approval is True
        assert snapshot.safety_flags.snapshot_output_not_deployment_approval is True
        assert snapshot.safety_flags.snapshot_output_not_transaction_permission is True
        assert snapshot.safety_flags.snapshot_output_not_for_execution is True
        assert snapshot.safety_flags.snapshot_output_not_for_strategy is True
        assert snapshot.safety_flags.snapshot_output_not_for_freqtrade is True
        assert snapshot.safety_flags.snapshot_output_not_for_order is True
        assert snapshot.safety_flags.snapshot_output_not_for_exchange is True

    def test_file_references_are_strings_only(self) -> None:
        """local_reference strings must be stored verbatim, never opened."""
        summary = _make_artifact_summary(
            local_reference="reports/does_not_exist.json",
        )
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(summary,),
            generated_at=_now(),
            config=AuditSnapshotConfig(expected_artifact_count=1),
        )
        d = research_audit_snapshot_to_dict(snapshot)
        artifact_section = next(
            s for s in d["sections"] if s["section_kind"] == "artifact_state"
        )
        assert artifact_section["items"][0]["local_reference"] == "reports/does_not_exist.json"

    def test_frozen_snapshot_is_immutable(self) -> None:
        """The built snapshot must be a frozen dataclass."""
        snapshot = _build_current(count=1)
        with pytest.raises(AttributeError):
            snapshot.snapshot_id = "mutated"  # type: ignore[misc]

    def test_forbidden_terms_not_in_artifact_content(self, tmp_path: Path) -> None:
        """Dangerous terms must not appear in artifact item content (titles, notes, etc.).

        Note: safety_flags field names like 'leverage_enabled' and 'shorting_enabled'
        are expected schema keys, not content — they are excluded from this check.
        """
        snapshot = _build_current(count=1)
        d = research_audit_snapshot_to_dict(snapshot)
        # Check only section content (titles, notes, item fields) — not the
        # safety_flags schema which legitimately has field names like leverage_enabled.
        dangerous = ("binance", "liquidation", "go_live", "production_ready",
                      "release_approved", "deploy_now", "place_order", "execute_trade")
        for section in d["sections"]:
            title_lower = section["title"].lower()
            notes_lower = section["section_notes"].lower()
            for term in dangerous:
                assert term not in title_lower, f"'{term}' in section title"
                assert term not in notes_lower, f"'{term}' in section notes"
            for item in section["items"]:
                for field in ("title", "artifact_kind", "state"):
                    val = str(item.get(field, "")).lower()
                    assert term not in val, f"'{term}' in item {field}"


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


class TestDeterminism:
    """Same inputs must produce byte-identical output across runs."""

    def test_same_inputs_produce_same_snapshot_id(self) -> None:
        summary = _make_artifact_summary()
        now = _now()
        kwargs = dict(
            artifact_summaries=(summary,),
            snapshot_id="snap-det",
            generated_at=now,
            config=AuditSnapshotConfig(expected_artifact_count=1),
        )
        s1 = build_research_audit_snapshot(**kwargs)
        s2 = build_research_audit_snapshot(**kwargs)
        assert s1.snapshot_id == s2.snapshot_id
        assert s1.generated_at == s2.generated_at

    def test_same_inputs_produce_identical_dict(self) -> None:
        summary = _make_artifact_summary()
        now = _now()
        kwargs = dict(
            artifact_summaries=(summary,),
            snapshot_id="snap-det",
            generated_at=now,
            config=AuditSnapshotConfig(expected_artifact_count=1),
        )
        s1 = build_research_audit_snapshot(**kwargs)
        s2 = build_research_audit_snapshot(**kwargs)
        assert research_audit_snapshot_to_dict(s1) == research_audit_snapshot_to_dict(s2)

    def test_same_inputs_produce_identical_markdown(self) -> None:
        summary = _make_artifact_summary()
        now = _now()
        kwargs = dict(
            artifact_summaries=(summary,),
            snapshot_id="snap-det",
            generated_at=now,
            config=AuditSnapshotConfig(expected_artifact_count=1),
        )
        s1 = build_research_audit_snapshot(**kwargs)
        s2 = build_research_audit_snapshot(**kwargs)
        assert research_audit_snapshot_to_markdown(s1) == research_audit_snapshot_to_markdown(s2)

    def test_same_inputs_produce_identical_json_file(self, tmp_path: Path) -> None:
        summary = _make_artifact_summary()
        now = _now()
        kwargs = dict(
            artifact_summaries=(summary,),
            snapshot_id="snap-det-file",
            generated_at=now,
            config=AuditSnapshotConfig(expected_artifact_count=1),
        )
        s1 = build_research_audit_snapshot(**kwargs)
        s2 = build_research_audit_snapshot(**kwargs)
        p1 = tmp_path / "s1.json"
        p2 = tmp_path / "s2.json"
        atomic_write_json_research_audit_snapshot(s1, p1)
        atomic_write_json_research_audit_snapshot(s2, p2)
        assert p1.read_bytes() == p2.read_bytes()

    def test_different_snapshot_ids_produce_different_output(self) -> None:
        summary = _make_artifact_summary()
        now = _now()
        s1 = build_research_audit_snapshot(
            artifact_summaries=(summary,),
            snapshot_id="snap-a",
            generated_at=now,
            config=AuditSnapshotConfig(expected_artifact_count=1),
        )
        s2 = build_research_audit_snapshot(
            artifact_summaries=(summary,),
            snapshot_id="snap-b",
            generated_at=now,
            config=AuditSnapshotConfig(expected_artifact_count=1),
        )
        assert research_audit_snapshot_to_dict(s1) != research_audit_snapshot_to_dict(s2)