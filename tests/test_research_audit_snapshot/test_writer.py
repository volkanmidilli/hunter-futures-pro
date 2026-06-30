"""Tests for hunter.research_audit_snapshot.writer.

MVP-23 research_audit_snapshot writer tests only.
No network, database, Freqtrade, Binance, exchange, trading,
Web UI, dashboard, or integration behavior is exercised here.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from hunter.research_audit_snapshot.models import (
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
from hunter.research_audit_snapshot.writer import (
    DEFAULT_AUDIT_SNAPSHOT_JSON_PATH,
    DEFAULT_AUDIT_SNAPSHOT_MARKDOWN_PATH,
    _atomic_write,
    _coerce_path,
    _iso,
    _serialize_value,
    atomic_write_json_research_audit_snapshot,
    atomic_write_markdown_research_audit_snapshot,
    audit_snapshot_config_to_dict,
    audit_snapshot_data_quality_to_dict,
    audit_snapshot_item_to_dict,
    audit_snapshot_safety_flags_to_dict,
    audit_snapshot_section_to_dict,
    audit_snapshot_summary_to_dict,
    research_audit_snapshot_to_dict,
    research_audit_snapshot_to_markdown,
    write_research_audit_snapshot,
)


def _now() -> datetime:
    return datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _make_item(**overrides: object) -> AuditSnapshotItem:
    data: dict[str, object] = {
        "item_id": "item-1",
        "title": "Artifact state",
        "artifact_kind": "OBSERVATION_REPORT",
        "state": "CURRENT",
        "severity": "INFO",
        "related_mvp": "MVP-10",
        "spec_reference": "SPEC-011",
        "local_reference": "data/observation/latest_observation_report.json",
        "generated_at": _now(),
        "reason_codes": ("NO_ACTION_COMMANDS_EMITTED",),
        "tags": ("tag-a",),
        "related_references": ("ref-a",),
        "metadata": {"symbol": "BTC/USDT"},
    }
    data.update(overrides)
    return AuditSnapshotItem(**data)


def _make_section(**overrides: object) -> AuditSnapshotSection:
    data: dict[str, object] = {
        "section_kind": AuditSnapshotSectionKind.ARTIFACT_STATE,
        "title": "Artifact State",
        "section_notes": "Notes",
        "items": (_make_item(),),
        "references": ("ref-1",),
        "metadata": {"section_meta": "value"},
    }
    data.update(overrides)
    return AuditSnapshotSection(**data)


def _make_snapshot(**overrides: object) -> ResearchAuditSnapshot:
    item = _make_item()
    section = _make_section(items=(item,))
    summary = AuditSnapshotSummary(
        total_sections=1,
        total_items=1,
        info_count=1,
        current_count=1,
        snapshot_state="CURRENT",
    )
    data_quality = AuditSnapshotDataQuality(
        total_artifacts_expected=1,
        total_artifacts_present=1,
        total_artifacts_missing=0,
        sections_expected=1,
        sections_present=1,
        sections_missing=0,
    )
    data: dict[str, object] = {
        "snapshot_id": "snap-1",
        "generated_at": _now(),
        "project_version": "0.23.0-dev",
        "source_spec": "SPEC-024",
        "sections": (section,),
        "summary": summary,
        "data_quality": data_quality,
        "metadata": {"purpose": "unit-test"},
    }
    data.update(overrides)
    return ResearchAuditSnapshot(**data)


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
        dt = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone(timedelta(hours=2)))
        assert _iso(dt) == "2024-01-01T12:00:00+02:00"


class TestSerializeValue:
    def test_enum(self) -> None:
        assert _serialize_value(AuditSnapshotState.CURRENT) == "current"

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
        assert _serialize_value({"k": (AuditSnapshotState.CURRENT,)}) == {"k": ["current"]}

    def test_plain_value(self) -> None:
        assert _serialize_value(42) == 42


class TestCoercePath:
    def test_none_returns_default(self) -> None:
        assert _coerce_path(None, DEFAULT_AUDIT_SNAPSHOT_JSON_PATH) == DEFAULT_AUDIT_SNAPSHOT_JSON_PATH

    def test_str_converts_to_path(self) -> None:
        assert _coerce_path("custom.json", DEFAULT_AUDIT_SNAPSHOT_JSON_PATH) == Path("custom.json")

    def test_path_passes_through(self) -> None:
        path = Path("custom.json")
        assert _coerce_path(path, DEFAULT_AUDIT_SNAPSHOT_JSON_PATH) is path


class TestAuditSnapshotConfigToDict:
    def test_all_fields_present(self) -> None:
        config = AuditSnapshotConfig()
        d = audit_snapshot_config_to_dict(config)
        assert d["version"] == "1.0"
        assert d["dry_run"] is True
        assert d["output_format"] == "both"
        assert d["required_sections"] == [kind.value for kind in config.required_sections]


class TestAuditSnapshotSafetyFlagsToDict:
    def test_all_fields_present(self) -> None:
        flags = AuditSnapshotSafetyFlags()
        d = audit_snapshot_safety_flags_to_dict(flags)
        assert d["dry_run"] is True
        assert d["live_trading_enabled"] is False
        assert d["snapshot_output_is_human_audit_only"] is True
        assert d["file_refs_not_traversed"] is True


class TestAuditSnapshotItemToDict:
    def test_all_fields(self) -> None:
        item = _make_item()
        d = audit_snapshot_item_to_dict(item)
        assert d["item_id"] == "item-1"
        assert d["title"] == "Artifact state"
        assert d["artifact_kind"] == "OBSERVATION_REPORT"
        assert d["state"] == "CURRENT"
        assert d["severity"] == "INFO"
        assert d["related_mvp"] == "MVP-10"
        assert d["spec_reference"] == "SPEC-011"
        assert d["local_reference"] == "data/observation/latest_observation_report.json"
        assert d["generated_at"] == "2024-01-01T12:00:00Z"
        assert d["reason_codes"] == ["NO_ACTION_COMMANDS_EMITTED"]
        assert d["tags"] == ["tag-a"]
        assert d["related_references"] == ["ref-a"]
        assert d["metadata"] == {"symbol": "BTC/USDT"}


class TestAuditSnapshotSectionToDict:
    def test_all_fields(self) -> None:
        section = _make_section()
        d = audit_snapshot_section_to_dict(section)
        assert d["section_kind"] == "artifact_state"
        assert d["title"] == "Artifact State"
        assert d["section_notes"] == "Notes"
        assert len(d["items"]) == 1
        assert d["references"] == ["ref-1"]
        assert d["metadata"] == {"section_meta": "value"}


class TestAuditSnapshotSummaryToDict:
    def test_all_fields(self) -> None:
        summary = AuditSnapshotSummary(
            total_sections=2,
            total_items=3,
            critical_count=1,
            high_count=1,
            info_count=1,
            current_count=2,
            stale_count=1,
            snapshot_state="STALE",
            reason_code_counts={"STALE_ARTIFACT_DETECTED": 1},
            snapshot_narrative="narrative",
        )
        d = audit_snapshot_summary_to_dict(summary)
        assert d["total_sections"] == 2
        assert d["total_items"] == 3
        assert d["critical_count"] == 1
        assert d["high_count"] == 1
        assert d["snapshot_state"] == "STALE"
        assert d["reason_code_counts"] == {"STALE_ARTIFACT_DETECTED": 1}
        assert d["snapshot_narrative"] == "narrative"


class TestAuditSnapshotDataQualityToDict:
    def test_all_fields(self) -> None:
        dq = AuditSnapshotDataQuality(
            total_artifacts_expected=13,
            total_artifacts_present=10,
            total_artifacts_missing=3,
            sections_expected=8,
            sections_present=8,
            sections_missing=0,
            reason_codes=("NO_ACTION_COMMANDS_EMITTED",),
            quality_narrative="quality ok",
        )
        d = audit_snapshot_data_quality_to_dict(dq)
        assert d["total_artifacts_expected"] == 13
        assert d["total_artifacts_present"] == 10
        assert d["total_artifacts_missing"] == 3
        assert d["sections_present"] == 8
        assert d["reason_codes"] == ["NO_ACTION_COMMANDS_EMITTED"]
        assert d["quality_narrative"] == "quality ok"


class TestResearchAuditSnapshotToDict:
    def test_ready_snapshot(self) -> None:
        snapshot = _make_snapshot()
        d = research_audit_snapshot_to_dict(snapshot)
        assert d["snapshot_id"] == "snap-1"
        assert d["kind"] == "research_audit_snapshot"
        assert d["generated_at"] == "2024-01-01T12:00:00Z"
        assert d["project_version"] == "0.23.0-dev"
        assert d["source_spec"] == "SPEC-024"
        assert d["config"]["version"] == "1.0"
        assert d["config"]["dry_run"] is True
        assert d["safety_flags"]["snapshot_output_is_human_audit_only"] is True
        assert len(d["sections"]) == 1
        assert d["summary"]["snapshot_state"] == "CURRENT"
        assert d["metadata"] == {"purpose": "unit-test"}

    def test_blocked_snapshot(self) -> None:
        snapshot = ResearchAuditSnapshot.blocked(reason_code="UNSAFE_SNAPSHOT_CONTENT")
        d = research_audit_snapshot_to_dict(snapshot)
        assert d["snapshot_id"] == "blocked"
        assert d["summary"]["snapshot_state"] == "BLOCK"
        assert d["reason_codes"] == ["UNSAFE_SNAPSHOT_CONTENT"]

    def test_no_sections(self) -> None:
        snapshot = _make_snapshot(sections=())
        d = research_audit_snapshot_to_dict(snapshot)
        assert d["sections"] == []


class TestResearchAuditSnapshotToMarkdown:
    def test_contains_title(self) -> None:
        md = research_audit_snapshot_to_markdown(_make_snapshot())
        assert "# Local Research Audit Snapshot — Human Audit Only" in md

    def test_safety_notice_after_title(self) -> None:
        md = research_audit_snapshot_to_markdown(_make_snapshot())
        lines = md.splitlines()
        title_idx = lines.index("# Local Research Audit Snapshot — Human Audit Only")
        assert lines[title_idx + 1] == ""
        assert lines[title_idx + 2].startswith("> ")
        assert "human-audit" in lines[title_idx + 2]

    def test_safety_notice_before_identity(self) -> None:
        md = research_audit_snapshot_to_markdown(_make_snapshot())
        title_idx = md.find("# Local Research Audit Snapshot")
        identity_idx = md.find("## Snapshot Identity")
        notice_idx = md.find("human-audit")
        assert title_idx < notice_idx < identity_idx

    def test_contains_identity(self) -> None:
        md = research_audit_snapshot_to_markdown(_make_snapshot())
        assert "## Snapshot Identity" in md
        assert "snap-1" in md

    def test_contains_summary(self) -> None:
        md = research_audit_snapshot_to_markdown(_make_snapshot())
        assert "## Snapshot Summary" in md
        assert "total_items" in md

    def test_contains_data_quality(self) -> None:
        md = research_audit_snapshot_to_markdown(_make_snapshot())
        assert "## Data Quality" in md
        assert "total_artifacts_expected" in md

    def test_contains_reason_codes(self) -> None:
        md = research_audit_snapshot_to_markdown(_make_snapshot())
        assert "## Reason Codes" in md

    def test_contains_section(self) -> None:
        md = research_audit_snapshot_to_markdown(_make_snapshot())
        assert "## Artifact State" in md
        assert "item-1: Artifact state" in md

    def test_contains_metadata(self) -> None:
        md = research_audit_snapshot_to_markdown(_make_snapshot())
        assert "## Metadata" in md
        assert "purpose" in md

    def test_blocked_snapshot(self) -> None:
        snapshot = ResearchAuditSnapshot.blocked(reason_code="UNSAFE_SNAPSHOT_CONTENT")
        md = research_audit_snapshot_to_markdown(snapshot)
        assert "BLOCK" in md
        assert "UNSAFE_SNAPSHOT_CONTENT" in md


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
        import os

        parent = tmp_path / "readonly"
        parent.mkdir()
        os.chmod(str(parent), 0o555)
        try:
            with pytest.raises(OSError):
                _atomic_write(parent / "sub" / "test.txt", "hello")
        finally:
            os.chmod(str(parent), 0o755)


class TestAtomicWriteJsonResearchAuditSnapshot:
    def test_writes_json(self, tmp_path: Path) -> None:
        snapshot = _make_snapshot()
        path = tmp_path / "snapshot.json"
        out = atomic_write_json_research_audit_snapshot(snapshot, path)
        assert out == path
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["snapshot_id"] == "snap-1"
        assert data["summary"]["snapshot_state"] == "CURRENT"

    def test_default_path(self, tmp_path: Path) -> None:
        snapshot = _make_snapshot()
        original_default = DEFAULT_AUDIT_SNAPSHOT_JSON_PATH
        path = tmp_path / "default.json"
        out = atomic_write_json_research_audit_snapshot(snapshot, path)
        assert out.exists()
        assert str(original_default) == "data/research_audit_snapshot/latest_research_audit_snapshot.json"

    def test_json_has_trailing_newline(self, tmp_path: Path) -> None:
        snapshot = _make_snapshot()
        path = tmp_path / "snapshot.json"
        atomic_write_json_research_audit_snapshot(snapshot, path)
        assert path.read_text().endswith("\n")

    def test_sort_keys(self, tmp_path: Path) -> None:
        snapshot = _make_snapshot()
        path = tmp_path / "snapshot.json"
        atomic_write_json_research_audit_snapshot(snapshot, path)
        text = path.read_text()
        assert '"config"' in text
        assert '"snapshot_id"' in text


class TestAtomicWriteMarkdownResearchAuditSnapshot:
    def test_writes_markdown(self, tmp_path: Path) -> None:
        snapshot = _make_snapshot()
        path = tmp_path / "snapshot.md"
        out = atomic_write_markdown_research_audit_snapshot(snapshot, path)
        assert out == path
        assert path.exists()
        assert "# Local Research Audit Snapshot" in path.read_text()

    def test_has_trailing_newline(self, tmp_path: Path) -> None:
        snapshot = _make_snapshot()
        path = tmp_path / "snapshot.md"
        atomic_write_markdown_research_audit_snapshot(snapshot, path)
        assert path.read_text().endswith("\n")


class TestWriteResearchAuditSnapshot:
    def test_writes_both(self, tmp_path: Path) -> None:
        snapshot = _make_snapshot()
        json_path = tmp_path / "snapshot.json"
        md_path = tmp_path / "snapshot.md"
        json_out, md_out = write_research_audit_snapshot(snapshot, json_path, md_path)
        assert json_out == json_path
        assert md_out == md_path
        assert json_path.exists()
        assert md_path.exists()

    def test_honors_json_output_format(self, tmp_path: Path) -> None:
        snapshot = _make_snapshot(config=AuditSnapshotConfig(output_format="json"))
        json_path = tmp_path / "snapshot.json"
        md_path = tmp_path / "snapshot.md"
        json_out, md_out = write_research_audit_snapshot(snapshot, json_path, md_path)
        assert json_out == json_path
        assert md_out is None
        assert json_path.exists()
        assert not md_path.exists()

    def test_honors_markdown_output_format(self, tmp_path: Path) -> None:
        snapshot = _make_snapshot(config=AuditSnapshotConfig(output_format="markdown"))
        json_path = tmp_path / "snapshot.json"
        md_path = tmp_path / "snapshot.md"
        json_out, md_out = write_research_audit_snapshot(snapshot, json_path, md_path)
        assert json_out is None
        assert md_out == md_path
        assert not json_path.exists()
        assert md_path.exists()


class TestDefaultPaths:
    def test_default_json_path(self) -> None:
        assert str(DEFAULT_AUDIT_SNAPSHOT_JSON_PATH) == "data/research_audit_snapshot/latest_research_audit_snapshot.json"

    def test_default_markdown_path(self) -> None:
        assert str(DEFAULT_AUDIT_SNAPSHOT_MARKDOWN_PATH) == "reports/research_audit_snapshot/latest_research_audit_snapshot.md"


class TestSafetyInvariants:
    def test_no_secrets_in_output(self, tmp_path: Path) -> None:
        snapshot = _make_snapshot()
        path = tmp_path / "snapshot.json"
        atomic_write_json_research_audit_snapshot(snapshot, path)
        text = path.read_text().lower()
        assert "api_key" not in text
        assert "secret" not in text
        assert "exchange_credentials" not in text

    def test_no_executable_instructions(self, tmp_path: Path) -> None:
        snapshot = _make_snapshot()
        path = tmp_path / "snapshot.json"
        atomic_write_json_research_audit_snapshot(snapshot, path)
        text = path.read_text().lower()
        assert "enter_long" not in text
        assert "enter_short" not in text
        assert "exit_long" not in text
        assert "exit_short" not in text

    def test_markdown_safety_notice(self, tmp_path: Path) -> None:
        snapshot = _make_snapshot()
        path = tmp_path / "snapshot.md"
        atomic_write_markdown_research_audit_snapshot(snapshot, path)
        text = path.read_text()
        assert "human-audit" in text
        assert "not a trading signal" in text
        assert "must not be consumed by execution" in text


class TestDictDeterminism:
    def test_same_snapshot_same_dict(self) -> None:
        snapshot1 = _make_snapshot()
        snapshot2 = _make_snapshot()
        assert research_audit_snapshot_to_dict(snapshot1) == research_audit_snapshot_to_dict(snapshot2)
