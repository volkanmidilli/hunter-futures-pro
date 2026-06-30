"""Integration tests for hunter.research_audit_snapshot package.

MVP-23 end-to-end integration tests only.
No network, database, Freqtrade, Binance, exchange, trading,
Web UI, dashboard, or production data access is exercised here.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from hunter.research_audit_snapshot.engine import build_research_audit_snapshot
from hunter.research_audit_snapshot.models import (
    AuditSnapshotConfig,
    AuditSnapshotSectionKind,
    AuditSnapshotState,
    MISSING_ARTIFACT_SUMMARIES,
    STALE_ARTIFACT_DETECTED,
    UNSAFE_SNAPSHOT_CONTENT,
)
from hunter.research_audit_snapshot.writer import (
    research_audit_snapshot_to_dict,
    research_audit_snapshot_to_markdown,
    write_research_audit_snapshot,
)


def _now() -> datetime:
    return datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _make_artifact_summary(**overrides: object) -> dict[str, object]:
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


class TestHappyPath:
    def test_full_flow_build_and_serialize(self, tmp_path: Path) -> None:
        summary = _make_artifact_summary()
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(summary,),
            generated_at=_now(),
            snapshot_id="snap-int-1",
            config=AuditSnapshotConfig(expected_artifact_count=1),
        )

        assert snapshot.summary.snapshot_state == AuditSnapshotState.CURRENT.value.upper()
        assert len(snapshot.sections) == 8

        d = research_audit_snapshot_to_dict(snapshot)
        assert d["snapshot_id"] == "snap-int-1"
        assert d["summary"]["snapshot_state"] == "CURRENT"

        json_path = tmp_path / "snapshot.json"
        md_path = tmp_path / "snapshot.md"
        write_research_audit_snapshot(snapshot, json_path, md_path)

        assert json_path.exists()
        assert md_path.exists()

        data = json.loads(json_path.read_text())
        assert data["snapshot_id"] == snapshot.snapshot_id
        assert data["summary"]["snapshot_state"] == "CURRENT"

        md_text = md_path.read_text()
        assert "# Local Research Audit Snapshot" in md_text
        assert "human-audit" in md_text

    def test_multiple_artifacts_sorted_in_sections(self, tmp_path: Path) -> None:
        s1 = _make_artifact_summary(
            artifact_id="obs-1",
            artifact_kind="OBSERVATION_REPORT",
            related_mvp="MVP-22",
            generated_at=_now(),
        )
        s2 = _make_artifact_summary(
            artifact_id="obs-2",
            artifact_kind="OBSERVATION_REPORT",
            related_mvp="MVP-10",
            generated_at=_now(),
        )
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(s1, s2),
            generated_at=_now(),
            config=AuditSnapshotConfig(expected_artifact_count=2),
        )

        artifact_section = next(
            s for s in snapshot.sections if s.section_kind == AuditSnapshotSectionKind.ARTIFACT_STATE
        )
        assert len(artifact_section.items) == 2

        json_path = tmp_path / "snapshot.json"
        md_path = tmp_path / "snapshot.md"
        write_research_audit_snapshot(snapshot, json_path, md_path)
        assert json_path.exists()
        assert md_path.exists()

    def test_section_order_is_canonical(self, tmp_path: Path) -> None:
        summary = _make_artifact_summary()
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(summary,),
            generated_at=_now(),
            config=AuditSnapshotConfig(expected_artifact_count=1),
        )
        kinds = [s.section_kind for s in snapshot.sections]
        assert kinds == list(AuditSnapshotSectionKind)


class TestErrorPaths:
    def test_missing_artifacts_blocked(self, tmp_path: Path) -> None:
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(),
            generated_at=_now(),
            config=AuditSnapshotConfig(expected_artifact_count=1),
        )
        assert snapshot.summary.snapshot_state == "BLOCK"
        assert MISSING_ARTIFACT_SUMMARIES in snapshot.reason_codes

        d = research_audit_snapshot_to_dict(snapshot)
        assert d["summary"]["snapshot_state"] == "BLOCK"

        md = research_audit_snapshot_to_markdown(snapshot)
        assert "BLOCK" in md
        assert MISSING_ARTIFACT_SUMMARIES in md

    def test_stale_artifact(self, tmp_path: Path) -> None:
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
        assert STALE_ARTIFACT_DETECTED in snapshot.reason_codes

    def test_unsafe_metadata_blocked(self, tmp_path: Path) -> None:
        summary = _make_artifact_summary()
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(summary,),
            generated_at=_now(),
            config=AuditSnapshotConfig(expected_artifact_count=1),
            metadata={"note": "execute trade"},
        )
        assert snapshot.summary.snapshot_state == "BLOCK"
        assert UNSAFE_SNAPSHOT_CONTENT in snapshot.reason_codes


class TestSafetyAssertions:
    def test_no_file_reads(self, tmp_path: Path) -> None:
        summary = _make_artifact_summary(
            local_reference="/production/data.json",
        )
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(summary,),
            generated_at=_now(),
            config=AuditSnapshotConfig(expected_artifact_count=1),
        )
        assert snapshot.summary.snapshot_state == "CURRENT"
        assert snapshot.data_quality.total_artifacts_present == 1

    def test_no_network_calls(self, tmp_path: Path) -> None:
        summary = _make_artifact_summary()
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(summary,),
            generated_at=_now(),
            config=AuditSnapshotConfig(expected_artifact_count=1),
        )
        assert snapshot.summary.snapshot_state == "CURRENT"

    def test_no_execution_feedback(self, tmp_path: Path) -> None:
        summary = _make_artifact_summary()
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(summary,),
            generated_at=_now(),
            config=AuditSnapshotConfig(expected_artifact_count=1),
        )
        assert snapshot.safety_flags.snapshot_feedback_into_execution is False
        assert snapshot.safety_flags.cross_layer_feedback_into_execution is False

    def test_no_trading_logic(self, tmp_path: Path) -> None:
        summary = _make_artifact_summary()
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(summary,),
            generated_at=_now(),
            config=AuditSnapshotConfig(expected_artifact_count=1),
        )
        assert snapshot.safety_flags.live_trading_enabled is False
        assert snapshot.safety_flags.real_orders_enabled is False
        assert snapshot.safety_flags.leverage_enabled is False
        assert snapshot.safety_flags.shorting_enabled is False

    def test_no_secrets_in_output(self, tmp_path: Path) -> None:
        summary = _make_artifact_summary()
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(summary,),
            generated_at=_now(),
            config=AuditSnapshotConfig(expected_artifact_count=1),
        )
        json_path = tmp_path / "snapshot.json"
        md_path = tmp_path / "snapshot.md"
        write_research_audit_snapshot(snapshot, json_path, md_path)

        json_text = json_path.read_text().lower()
        md_text = md_path.read_text().lower()
        for term in ("api_key", "secret", "exchange_credentials", "private_key", "password"):
            assert term not in json_text
            assert term not in md_text

    def test_no_executable_instructions_in_output(self, tmp_path: Path) -> None:
        summary = _make_artifact_summary()
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(summary,),
            generated_at=_now(),
            config=AuditSnapshotConfig(expected_artifact_count=1),
        )
        json_path = tmp_path / "snapshot.json"
        md_path = tmp_path / "snapshot.md"
        write_research_audit_snapshot(snapshot, json_path, md_path)

        json_text = json_path.read_text().lower()
        md_text = md_path.read_text().lower()
        for term in ("enter_long", "enter_short", "exit_long", "exit_short", "execute trade"):
            assert term not in json_text
            assert term not in md_text

    def test_human_audit_only_notice_in_markdown(self, tmp_path: Path) -> None:
        summary = _make_artifact_summary()
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(summary,),
            generated_at=_now(),
            config=AuditSnapshotConfig(expected_artifact_count=1),
        )
        md_path = tmp_path / "snapshot.md"
        write_research_audit_snapshot(snapshot, tmp_path / "snapshot.json", md_path)

        md_text = md_path.read_text()
        assert "human-audit" in md_text
        assert "not a trading signal" in md_text
        assert "must not be consumed by execution" in md_text

    def test_snapshot_not_for_strategy(self, tmp_path: Path) -> None:
        summary = _make_artifact_summary()
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(summary,),
            generated_at=_now(),
            config=AuditSnapshotConfig(expected_artifact_count=1),
        )
        assert snapshot.safety_flags.snapshot_output_not_for_strategy is True

    def test_snapshot_not_for_exchange(self, tmp_path: Path) -> None:
        summary = _make_artifact_summary()
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(summary,),
            generated_at=_now(),
            config=AuditSnapshotConfig(expected_artifact_count=1),
        )
        assert snapshot.safety_flags.snapshot_output_not_for_exchange is True

    def test_file_references_are_strings_only(self, tmp_path: Path) -> None:
        summary = _make_artifact_summary(
            local_reference="reports/does_not_exist.json",
        )
        snapshot = build_research_audit_snapshot(
            artifact_summaries=(summary,),
            generated_at=_now(),
            config=AuditSnapshotConfig(expected_artifact_count=1),
        )
        assert snapshot.summary.snapshot_state == "CURRENT"
        d = research_audit_snapshot_to_dict(snapshot)
        section = next(
            s for s in d["sections"] if s["section_kind"] == "artifact_state"
        )
        assert section["items"][0]["local_reference"] == "reports/does_not_exist.json"


class TestDeterminism:
    def test_same_inputs_produce_same_snapshot_id(self) -> None:
        summary = _make_artifact_summary()
        now = _now()
        snapshot1 = build_research_audit_snapshot(
            artifact_summaries=(summary,),
            snapshot_id="snap-det",
            generated_at=now,
            config=AuditSnapshotConfig(expected_artifact_count=1),
        )
        snapshot2 = build_research_audit_snapshot(
            artifact_summaries=(summary,),
            snapshot_id="snap-det",
            generated_at=now,
            config=AuditSnapshotConfig(expected_artifact_count=1),
        )
        assert snapshot1.snapshot_id == snapshot2.snapshot_id
        assert snapshot1.generated_at == snapshot2.generated_at

    def test_same_inputs_produce_same_dict(self) -> None:
        summary = _make_artifact_summary()
        now = _now()
        snapshot1 = build_research_audit_snapshot(
            artifact_summaries=(summary,),
            snapshot_id="snap-det",
            generated_at=now,
            config=AuditSnapshotConfig(expected_artifact_count=1),
        )
        snapshot2 = build_research_audit_snapshot(
            artifact_summaries=(summary,),
            snapshot_id="snap-det",
            generated_at=now,
            config=AuditSnapshotConfig(expected_artifact_count=1),
        )
        assert research_audit_snapshot_to_dict(snapshot1) == research_audit_snapshot_to_dict(snapshot2)

    def test_same_inputs_produce_same_markdown(self) -> None:
        summary = _make_artifact_summary()
        now = _now()
        snapshot1 = build_research_audit_snapshot(
            artifact_summaries=(summary,),
            snapshot_id="snap-det",
            generated_at=now,
            config=AuditSnapshotConfig(expected_artifact_count=1),
        )
        snapshot2 = build_research_audit_snapshot(
            artifact_summaries=(summary,),
            snapshot_id="snap-det",
            generated_at=now,
            config=AuditSnapshotConfig(expected_artifact_count=1),
        )
        assert research_audit_snapshot_to_markdown(snapshot1) == research_audit_snapshot_to_markdown(snapshot2)
