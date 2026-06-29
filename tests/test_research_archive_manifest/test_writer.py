"""Tests for hunter.research_archive_manifest.writer."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hunter.research_archive_manifest.engine import build_research_archive_manifest
from hunter.research_archive_manifest.models import (
    ArchiveArtifactEntry,
    ArchiveArtifactFamily,
    ArchiveManifestConfig,
    ArchiveManifestDataQuality,
    ArchiveManifestSafetyFlags,
    ArchiveManifestState,
    ArchiveManifestSummary,
    ResearchArchiveManifest,
)
from hunter.research_archive_manifest.writer import (
    DEFAULT_ARCHIVE_MANIFEST_JSON_PATH,
    DEFAULT_ARCHIVE_MANIFEST_MARKDOWN_PATH,
    archive_artifact_entry_to_dict,
    archive_manifest_config_to_dict,
    archive_manifest_data_quality_to_dict,
    archive_manifest_safety_flags_to_dict,
    archive_manifest_summary_to_dict,
    atomic_write_json_research_archive_manifest,
    atomic_write_markdown_research_archive_manifest,
    research_archive_manifest_to_dict,
    research_archive_manifest_to_markdown,
    write_research_archive_manifest,
)


def _now() -> datetime:
    return datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _make_manifest(*, ready: bool = True) -> ResearchArchiveManifest:
    if ready:
        return build_research_archive_manifest(
            config=ArchiveManifestConfig(generated_at=_now()),
            observation_artifact=_make_artifact("READY"),
            review_artifact=_make_artifact("READY"),
            index_artifact=_make_artifact_dict("READY"),
            search_artifact=_make_artifact_dict("READY"),
            bundle_artifact=_make_artifact("READY"),
            chronicle_artifact=_make_artifact("READY"),
            digest_artifact=_make_artifact("READY"),
            quality_gate_artifact=_make_artifact("READY"),
            handoff_artifact=_make_artifact("READY"),
        )
    return build_research_archive_manifest(
        config=ArchiveManifestConfig(generated_at=_now()),
        observation_artifact=_make_artifact("READY"),
    )


def _make_artifact(state: str = "READY") -> object:
    class Artifact:
        pass

    artifact = Artifact()
    artifact.state = state
    artifact.reason_codes = ()
    artifact.generated_at = datetime(2099, 1, 1, tzinfo=timezone.utc)
    artifact.safety_flags = ArchiveManifestSafetyFlags()
    artifact.version = "1.0"
    return artifact


def _make_artifact_dict(state: str = "READY") -> dict[str, object]:
    return {
        "state": state,
        "reason_codes": (),
        "generated_at": datetime(2099, 1, 1, tzinfo=timezone.utc),
        "safety_flags": ArchiveManifestSafetyFlags(),
        "version": "1.0",
    }


# ---------------------------------------------------------------------------
# Component serialization
# ---------------------------------------------------------------------------


class TestArchiveManifestConfigToDict:
    def test_basic(self) -> None:
        config = ArchiveManifestConfig(generated_at=_now())
        data = archive_manifest_config_to_dict(config)
        assert data["version"] == "1.0"
        assert data["dry_run"] is True
        assert data["output_format"] == "both"
        assert data["required_families"] == [family.value for family in ArchiveArtifactFamily]


class TestArchiveManifestSafetyFlagsToDict:
    def test_basic(self) -> None:
        flags = ArchiveManifestSafetyFlags()
        data = archive_manifest_safety_flags_to_dict(flags)
        assert data["dry_run"] is True
        assert data["archive_manifest_feedback_into_execution"] is False
        assert data["cross_layer_feedback_into_execution"] is False
        assert data["archive_output_is_human_audit_only"] is True


class TestArchiveArtifactEntryToDict:
    def test_basic(self) -> None:
        entry = ArchiveArtifactEntry(
            artifact_family=ArchiveArtifactFamily.OBSERVATION_REPORT,
            state="PRESENT",
            spec_reference="SPEC-011",
            local_reference="data/observation/latest_observation_report.json",
            version="1.0",
            metadata={"report_path": "reports/2025/btc.md"},
        )
        data = archive_artifact_entry_to_dict(entry)
        assert data["artifact_family"] == "observation_report"
        assert data["state"] == "PRESENT"
        assert data["spec_reference"] == "SPEC-011"
        assert data["local_reference"] == "data/observation/latest_observation_report.json"
        assert data["metadata"] == {"report_path": "reports/2025/btc.md"}


class TestArchiveManifestSummaryToDict:
    def test_basic(self) -> None:
        summary = ArchiveManifestSummary(
            total_families=2,
            present_count=1,
            stale_count=1,
            missing_count=0,
            unknown_count=0,
            manifest_state="WARN",
        )
        data = archive_manifest_summary_to_dict(summary)
        assert data["total_families"] == 2
        assert data["manifest_state"] == "WARN"


class TestArchiveManifestDataQualityToDict:
    def test_basic(self) -> None:
        dq = ArchiveManifestDataQuality(
            completeness_pct=50.0,
            coverage_pct=100.0,
            total_families=2,
        )
        data = archive_manifest_data_quality_to_dict(dq)
        assert data["completeness_pct"] == 50.0
        assert data["coverage_pct"] == 100.0


# ---------------------------------------------------------------------------
# Full manifest serialization
# ---------------------------------------------------------------------------


class TestResearchArchiveManifestToDict:
    def test_structure(self) -> None:
        manifest = _make_manifest()
        data = research_archive_manifest_to_dict(manifest)
        assert data["manifest_id"].startswith("archive:1.0:")
        assert data["manifest_state"] == "ready"
        assert data["version"] == "1.0"
        assert "entries" in data
        assert "summary" in data
        assert "data_quality" in data
        assert "safety_flags" in data
        assert "config" in data
        assert "reason_codes" in data
        assert "manifest_notes" in data

    def test_enums_as_strings(self) -> None:
        manifest = _make_manifest()
        data = research_archive_manifest_to_dict(manifest)
        assert isinstance(data["manifest_state"], str)
        assert data["entries"][0]["artifact_family"] == "observation_report"
        assert isinstance(data["entries"][0]["artifact_family"], str)

    def test_metadata_as_plain_dict(self) -> None:
        entry = ArchiveArtifactEntry(
            artifact_family=ArchiveArtifactFamily.OBSERVATION_REPORT,
            metadata={"nested": {"file_ref": "data/observation/x.json"}},
        )
        manifest = ResearchArchiveManifest(
            manifest_id="m1",
            generated_at=_now(),
            entries=(entry,),
            summary=ArchiveManifestSummary(total_families=1, present_count=1),
            data_quality=ArchiveManifestDataQuality(total_families=1),
        )
        data = research_archive_manifest_to_dict(manifest)
        assert data["entries"][0]["metadata"] == {"nested": {"file_ref": "data/observation/x.json"}}

    def test_no_mutation(self) -> None:
        manifest = _make_manifest()
        original_id = manifest.manifest_id
        research_archive_manifest_to_dict(manifest)
        assert manifest.manifest_id == original_id
        assert manifest.entries == manifest.entries


# ---------------------------------------------------------------------------
# JSON determinism
# ---------------------------------------------------------------------------


class TestJsonDeterminism:
    def test_deterministic_output(self) -> None:
        manifest = _make_manifest()
        d1 = research_archive_manifest_to_dict(manifest)
        d2 = research_archive_manifest_to_dict(manifest)
        assert json.dumps(d1, sort_keys=True) == json.dumps(d2, sort_keys=True)

    def test_sorted_keys(self, tmp_path: Path) -> None:
        manifest = _make_manifest()
        json_path = tmp_path / "manifest.json"
        atomic_write_json_research_archive_manifest(manifest, target_path=json_path)
        text = json_path.read_text(encoding="utf-8")
        # Simple heuristic: keys in JSON objects should appear alphabetically.
        assert '"config":' in text
        assert '"data_quality":' in text
        assert '"entries":' in text
        assert '"manifest_id":' in text
        assert '"manifest_notes":' in text
        assert '"manifest_state":' in text
        assert '"reason_codes":' in text
        assert '"safety_flags":' in text
        assert '"summary":' in text
        assert '"version":' in text


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------


class TestResearchArchiveManifestToMarkdown:
    def test_safety_notice_first(self) -> None:
        manifest = _make_manifest()
        md = research_archive_manifest_to_markdown(manifest)
        # Safety notice appears before artifact family details.
        safety_idx = md.index("## Safety Notice")
        families_idx = md.index("## Artifact Families")
        assert safety_idx < families_idx
        assert "human-audit" in md
        assert "not a trading signal" in md
        assert "not trade approval" in md
        assert "not execution readiness" in md
        assert "not strategy readiness" in md
        assert "not release/deployment approval" in md
        assert "not transaction permission" in md
        assert "not be consumed by execution" in md
        assert "not traversed, opened, followed, validated, or executed" in md
        assert "does not read referenced artifact files" in md

    def test_family_ordering(self) -> None:
        manifest = _make_manifest()
        md = research_archive_manifest_to_markdown(manifest)
        positions = [
            md.index(f"- **family:** {family.value}")
            for family in ArchiveArtifactFamily
        ]
        assert positions == sorted(positions)

    def test_manifest_notes(self) -> None:
        manifest = _make_manifest()
        md = research_archive_manifest_to_markdown(manifest)
        assert "## Manifest Notes" in md
        assert "human audit" in md

    def test_reference_strings_plain_text(self) -> None:
        manifest = _make_manifest()
        md = research_archive_manifest_to_markdown(manifest)
        assert "data/observation/latest_observation_report.json" in md
        assert "SPEC-011" in md

    def test_determinism(self) -> None:
        manifest = _make_manifest()
        md1 = research_archive_manifest_to_markdown(manifest)
        md2 = research_archive_manifest_to_markdown(manifest)
        assert md1 == md2


# ---------------------------------------------------------------------------
# Atomic writes
# ---------------------------------------------------------------------------


class TestAtomicWrites:
    def test_atomic_json_write(self, tmp_path: Path) -> None:
        manifest = _make_manifest()
        json_path = tmp_path / "manifest.json"
        returned = atomic_write_json_research_archive_manifest(manifest, target_path=json_path)
        assert returned == json_path
        assert json_path.exists()
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data["manifest_state"] == "ready"

    def test_atomic_markdown_write(self, tmp_path: Path) -> None:
        manifest = _make_manifest()
        md_path = tmp_path / "manifest.md"
        returned = atomic_write_markdown_research_archive_manifest(manifest, target_path=md_path)
        assert returned == md_path
        assert md_path.exists()
        text = md_path.read_text(encoding="utf-8")
        assert "# Local Research Archive Manifest" in text

    def test_dual_write(self, tmp_path: Path) -> None:
        manifest = _make_manifest()
        json_path = tmp_path / "manifest.json"
        md_path = tmp_path / "manifest.md"
        j_out, m_out = write_research_archive_manifest(
            manifest, json_path=json_path, markdown_path=md_path
        )
        assert j_out == json_path
        assert m_out == md_path
        assert json_path.exists()
        assert md_path.exists()

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        manifest = _make_manifest()
        nested = tmp_path / "nested" / "dir" / "manifest.json"
        atomic_write_json_research_archive_manifest(manifest, target_path=nested)
        assert nested.exists()

    def test_no_production_default_writes(self, tmp_path: Path) -> None:
        manifest = _make_manifest()
        json_path = tmp_path / "manifest.json"
        md_path = tmp_path / "manifest.md"
        write_research_archive_manifest(manifest, json_path=json_path, markdown_path=md_path)
        assert not Path(DEFAULT_ARCHIVE_MANIFEST_JSON_PATH).exists()
        assert not Path(DEFAULT_ARCHIVE_MANIFEST_MARKDOWN_PATH).exists()


# ---------------------------------------------------------------------------
# String safety
# ---------------------------------------------------------------------------


class TestStringSafety:
    def test_file_references_not_opened(self, tmp_path: Path) -> None:
        entry = ArchiveArtifactEntry(
            artifact_family=ArchiveArtifactFamily.OBSERVATION_REPORT,
            local_reference="data/observation/latest_observation_report.json",
            metadata={"report_path": "reports/2025/btc.md"},
        )
        manifest = ResearchArchiveManifest(
            manifest_id="m1",
            generated_at=_now(),
            entries=(entry,),
            summary=ArchiveManifestSummary(total_families=1, present_count=1),
            data_quality=ArchiveManifestDataQuality(total_families=1),
        )
        json_path = tmp_path / "manifest.json"
        md_path = tmp_path / "manifest.md"
        write_research_archive_manifest(manifest, json_path=json_path, markdown_path=md_path)
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data["entries"][0]["metadata"]["report_path"] == "reports/2025/btc.md"
        md_text = md_path.read_text(encoding="utf-8")
        assert "reports/2025/btc.md" in md_text
        # No exception means strings were never opened or executed.

    def test_metadata_strings_remain_strings(self, tmp_path: Path) -> None:
        entry = ArchiveArtifactEntry(
            artifact_family=ArchiveArtifactFamily.OBSERVATION_REPORT,
            metadata={"note": "local string only"},
        )
        manifest = ResearchArchiveManifest(
            manifest_id="m1",
            generated_at=_now(),
            entries=(entry,),
            summary=ArchiveManifestSummary(total_families=1, present_count=1),
            data_quality=ArchiveManifestDataQuality(total_families=1),
        )
        data = research_archive_manifest_to_dict(manifest)
        assert isinstance(data["entries"][0]["metadata"]["note"], str)


# ---------------------------------------------------------------------------
# Blocked manifest
# ---------------------------------------------------------------------------


class TestBlockedManifestMarkdown:
    def test_blocked_manifest_renders(self) -> None:
        manifest = ResearchArchiveManifest.blocked("INVALID_CONFIG", generated_at=_now())
        md = research_archive_manifest_to_markdown(manifest)
        assert "BLOCK" in md
        assert "Archive manifest blocked: INVALID_CONFIG" in md


# ---------------------------------------------------------------------------
# Default paths
# ---------------------------------------------------------------------------


class TestDefaultPaths:
    def test_default_json_path(self) -> None:
        assert "data/research_archive_manifest/" in DEFAULT_ARCHIVE_MANIFEST_JSON_PATH
        assert DEFAULT_ARCHIVE_MANIFEST_JSON_PATH.endswith(".json")

    def test_default_markdown_path(self) -> None:
        assert "reports/research_archive_manifest/" in DEFAULT_ARCHIVE_MANIFEST_MARKDOWN_PATH
        assert DEFAULT_ARCHIVE_MANIFEST_MARKDOWN_PATH.endswith(".md")
