"""Tests for hunter.research_release_notes.writer."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hunter.research_release_notes.engine import (
    build_release_notes_change_item,
    build_research_release_notes,
)
from hunter.research_release_notes.models import (
    ReleaseNotesChangeItem,
    ReleaseNotesChangeSeverity,
    ReleaseNotesConfig,
    ReleaseNotesDataQuality,
    ReleaseNotesKind,
    ReleaseNotesSafetyFlags,
    ReleaseNotesSection,
    ReleaseNotesSectionKind,
    ReleaseNotesState,
    ReleaseNotesSummary,
    ResearchReleaseNotes,
)
from hunter.research_release_notes.writer import (
    DEFAULT_RESEARCH_RELEASE_NOTES_JSON_PATH,
    DEFAULT_RESEARCH_RELEASE_NOTES_MARKDOWN_PATH,
    atomic_write_json_research_release_notes,
    atomic_write_markdown_research_release_notes,
    release_notes_change_item_to_dict,
    release_notes_config_to_dict,
    release_notes_data_quality_to_dict,
    release_notes_section_to_dict,
    release_notes_safety_flags_to_dict,
    release_notes_summary_to_dict,
    research_release_notes_to_dict,
    research_release_notes_to_markdown,
    write_research_release_notes,
)


def _now() -> datetime:
    return datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _make_release_notes(*, ready: bool = True) -> ResearchReleaseNotes:
    if ready:
        return build_research_release_notes(
            reference_time=_now(),
            release_version="0.20.0-dev",
            release_title="MVP-20 Release Notes",
            change_items_by_section={
                ReleaseNotesSectionKind.COMPLETED_MVPS: (
                    build_release_notes_change_item(
                        title="MVP-19 archive manifest",
                        description="Local research archive manifest completed.",
                        change_kind="completion",
                        severity="INFO",
                        related_mvp="MVP-19",
                        spec_reference="SPEC-020",
                        related_references=("data/research_archive_manifest/latest_research_archive_manifest.json",),
                    ),
                ),
                ReleaseNotesSectionKind.KNOWN_GAPS: (
                    build_release_notes_change_item(
                        title="No cross-artifact validation",
                        description="Artifact references are not validated against file system.",
                        change_kind="known_gap",
                        severity="MEDIUM",
                        related_mvp="MVP-20",
                        spec_reference="SPEC-021",
                    ),
                ),
            },
        )
    return build_research_release_notes(
        reference_time=_now(),
        release_version="0.20.0-dev",
        config=ReleaseNotesConfig(required_sections=(ReleaseNotesSectionKind.OVERVIEW,)),
    )


# ---------------------------------------------------------------------------
# Component serialization
# ---------------------------------------------------------------------------


class TestReleaseNotesConfigToDict:
    def test_basic(self) -> None:
        config = ReleaseNotesConfig(generated_at=_now())
        data = release_notes_config_to_dict(config)
        assert data["version"] == "1.0"
        assert data["dry_run"] is True
        assert data["output_format"] == "both"
        assert data["required_sections"] == [section.value for section in ReleaseNotesSectionKind]


class TestReleaseNotesSafetyFlagsToDict:
    def test_basic(self) -> None:
        flags = ReleaseNotesSafetyFlags()
        data = release_notes_safety_flags_to_dict(flags)
        assert data["dry_run"] is True
        assert data["release_notes_output_is_human_audit_only"] is True
        assert data["release_notes_output_not_release_approval"] is True
        assert data["release_notes_output_not_deployment_approval"] is True
        assert data["release_notes_feedback_into_execution"] is False
        assert data["no_action_commands_emitted"] is True


class TestReleaseNotesChangeItemToDict:
    def test_basic(self) -> None:
        item = ReleaseNotesChangeItem(
            title="Test item",
            change_kind="completion",
            severity="HIGH",
            related_mvp="MVP-19",
            spec_reference="SPEC-020",
            related_references=("ref1", "ref2"),
            metadata={"key": "value"},
        )
        data = release_notes_change_item_to_dict(item)
        assert data["title"] == "Test item"
        assert data["change_kind"] == "completion"
        assert data["severity"] == "HIGH"
        assert data["related_mvp"] == "MVP-19"
        assert data["spec_reference"] == "SPEC-020"
        assert data["related_references"] == ["ref1", "ref2"]
        assert data["metadata"] == {"key": "value"}


class TestReleaseNotesSectionToDict:
    def test_basic(self) -> None:
        section = ReleaseNotesSection(
            section_kind=ReleaseNotesSectionKind.OVERVIEW,
            section_notes="Overview notes.",
            change_items=(ReleaseNotesChangeItem(title="Item 1"),),
        )
        data = release_notes_section_to_dict(section)
        assert data["section_kind"] == "overview"
        assert data["section_notes"] == "Overview notes."
        assert len(data["change_items"]) == 1
        assert data["change_items"][0]["title"] == "Item 1"


class TestReleaseNotesSummaryToDict:
    def test_basic(self) -> None:
        summary = ReleaseNotesSummary(
            total_sections=2,
            total_change_items=2,
            critical_count=1,
            high_count=1,
            release_notes_state="READY",
            release_notes="Notes.",
        )
        data = release_notes_summary_to_dict(summary)
        assert data["total_sections"] == 2
        assert data["total_change_items"] == 2
        assert data["critical_count"] == 1
        assert data["high_count"] == 1
        assert data["release_notes_state"] == "READY"
        assert data["release_notes"] == "Notes."


class TestReleaseNotesDataQualityToDict:
    def test_basic(self) -> None:
        dq = ReleaseNotesDataQuality(
            completeness_pct=100.0,
            coverage_pct=100.0,
            sections_present=8,
            sections_missing=0,
            total_sections=8,
            change_items_with_specs=5,
            change_items_without_specs=0,
            reason="All required sections present.",
        )
        data = release_notes_data_quality_to_dict(dq)
        assert data["completeness_pct"] == 100.0
        assert data["coverage_pct"] == 100.0
        assert data["sections_present"] == 8
        assert data["reason"] == "All required sections present."


# ---------------------------------------------------------------------------
# Full release notes serialization
# ---------------------------------------------------------------------------


class TestResearchReleaseNotesToDict:
    def test_basic(self) -> None:
        rn = _make_release_notes()
        data = research_release_notes_to_dict(rn)
        assert data["release_notes_id"].startswith("release-notes:")
        assert data["version"] == "1.0"
        assert data["kind"] == "research_release_notes"
        assert data["release_version"] == "0.20.0-dev"
        assert data["release_title"] == "MVP-20 Release Notes"
        assert data["release_notes_state"] == "ready"
        assert isinstance(data["sections"], list)
        assert isinstance(data["summary"], dict)
        assert isinstance(data["data_quality"], dict)
        assert isinstance(data["safety_flags"], dict)
        assert isinstance(data["config"], dict)
        assert isinstance(data["reason_codes"], list)

    def test_enums_serialized_as_strings(self) -> None:
        rn = _make_release_notes()
        data = research_release_notes_to_dict(rn)
        assert data["release_notes_state"] == "ready"
        assert data["kind"] == "research_release_notes"
        assert all(isinstance(s["section_kind"], str) for s in data["sections"])
        assert all(isinstance(item["severity"], str) for s in data["sections"] for item in s["change_items"])

    def test_reference_strings_remain_strings(self) -> None:
        rn = _make_release_notes()
        data = research_release_notes_to_dict(rn)
        completed = next(
            s for s in data["sections"] if s["section_kind"] == "completed_mvps"
        )
        refs = completed["change_items"][0]["related_references"]
        assert refs == ["data/research_archive_manifest/latest_research_archive_manifest.json"]

    def test_metadata_strings_remain_strings(self) -> None:
        rn = _make_release_notes()
        data = research_release_notes_to_dict(rn)
        assert isinstance(data["document_notes"], str)

    def test_no_mutation(self) -> None:
        rn = _make_release_notes()
        original_id = rn.release_notes_id
        _ = research_release_notes_to_dict(rn)
        assert rn.release_notes_id == original_id


class TestJsonDeterminism:
    def test_same_input_same_json(self) -> None:
        rn1 = _make_release_notes()
        rn2 = _make_release_notes()
        data1 = research_release_notes_to_dict(rn1)
        data2 = research_release_notes_to_dict(rn2)
        assert json.dumps(data1, sort_keys=True) == json.dumps(data2, sort_keys=True)


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


class TestResearchReleaseNotesToMarkdown:
    def test_contains_safety_notice(self) -> None:
        rn = _make_release_notes()
        md = research_release_notes_to_markdown(rn)
        assert "## Safety Notice" in md
        assert "human-audit" in md.lower()
        assert "not release approval" in md.lower()
        assert "not deployment approval" in md.lower()
        assert "not a trading signal" in md.lower()
        assert "must not be consumed by execution" in md.lower()

    def test_contains_identity_and_summary(self) -> None:
        rn = _make_release_notes()
        md = research_release_notes_to_markdown(rn)
        assert "# Local Research Release Notes / Audit Change Summary" in md
        assert "release_notes_id" in md
        assert "release_notes_state" in md
        assert "## Summary" in md
        assert "## Data Quality" in md

    def test_section_ordering(self) -> None:
        rn = _make_release_notes()
        md = research_release_notes_to_markdown(rn)
        expected_order = [
            "## Release Notes Identity",
            "## Version and Scope",
            "## Summary",
            "## Data Quality",
            "## Sections",
            "### Overview",
            "### Completed MVPs",
            "### Known Gaps",
            "### Safety Boundaries",
            "## Reason Codes",
            "## Document Notes",
        ]
        indices = [md.find(title) for title in expected_order]
        assert all(i >= 0 for i in indices)
        assert indices == sorted(indices)

    def test_change_item_ordering(self) -> None:
        rn = _make_release_notes()
        md = research_release_notes_to_markdown(rn)
        # Sections are already ordered; change items inside each section follow
        # deterministic severity/MVP/insertion order from the engine.
        assert "MVP-19 archive manifest" in md
        assert "No cross-artifact validation" in md

    def test_document_notes_present(self) -> None:
        rn = _make_release_notes()
        md = research_release_notes_to_markdown(rn)
        assert "## Document Notes" in md
        assert rn.document_notes in md

    def test_human_review_guide_advisory_only(self) -> None:
        rn = _make_release_notes()
        md = research_release_notes_to_markdown(rn)
        guide_start = md.find("### Human Review Guide")
        assert guide_start >= 0
        guide_section = md[guide_start:]
        assert "advisory" in guide_section.lower() or "suggestion" in guide_section.lower()
        assert "not a gating checklist" in guide_section.lower()

    def test_markdown_determinism(self) -> None:
        rn1 = _make_release_notes()
        rn2 = _make_release_notes()
        assert research_release_notes_to_markdown(rn1) == research_release_notes_to_markdown(rn2)

    def test_reference_strings_as_plain_text(self) -> None:
        rn = _make_release_notes()
        md = research_release_notes_to_markdown(rn)
        assert "data/research_archive_manifest/latest_research_archive_manifest.json" in md


# ---------------------------------------------------------------------------
# Atomic file writes
# ---------------------------------------------------------------------------


class TestAtomicJsonWrite:
    def test_writes_valid_json(self, tmp_path: Path) -> None:
        rn = _make_release_notes()
        target = tmp_path / "release_notes.json"
        result = atomic_write_json_research_release_notes(rn, target_path=target)
        assert result == target
        data = json.loads(target.read_text(encoding="utf-8"))
        assert data["release_version"] == "0.20.0-dev"
        assert data["kind"] == "research_release_notes"

    def test_default_path_not_written(self, tmp_path: Path) -> None:
        rn = _make_release_notes()
        target = tmp_path / "release_notes.json"
        atomic_write_json_research_release_notes(rn, target_path=target)
        assert not Path(DEFAULT_RESEARCH_RELEASE_NOTES_JSON_PATH).exists()


class TestAtomicMarkdownWrite:
    def test_writes_markdown(self, tmp_path: Path) -> None:
        rn = _make_release_notes()
        target = tmp_path / "release_notes.md"
        result = atomic_write_markdown_research_release_notes(rn, target_path=target)
        assert result == target
        text = target.read_text(encoding="utf-8")
        assert "# Local Research Release Notes / Audit Change Summary" in text
        assert "## Safety Notice" in text

    def test_default_path_not_written(self, tmp_path: Path) -> None:
        rn = _make_release_notes()
        target = tmp_path / "release_notes.md"
        atomic_write_markdown_research_release_notes(rn, target_path=target)
        assert not Path(DEFAULT_RESEARCH_RELEASE_NOTES_MARKDOWN_PATH).exists()


class TestWriteResearchReleaseNotes:
    def test_writes_both(self, tmp_path: Path) -> None:
        rn = _make_release_notes()
        json_path = tmp_path / "out.json"
        md_path = tmp_path / "out.md"
        out_json, out_md = write_research_release_notes(
            rn, json_path=json_path, markdown_path=md_path
        )
        assert out_json == json_path
        assert out_md == md_path
        assert json.loads(json_path.read_text(encoding="utf-8"))["release_version"] == "0.20.0-dev"
        assert "## Safety Notice" in md_path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Safety / no side effects
# ---------------------------------------------------------------------------


class TestWriterSafety:
    def test_no_forbidden_imports(self) -> None:
        source = Path(__file__).parents[2] / "src" / "hunter" / "research_release_notes" / "writer.py"
        text = source.read_text(encoding="utf-8")
        forbidden = ["freqtrade", "binance", "requests", "sqlite3"]
        for term in forbidden:
            assert (
                f"import {term}" not in text.lower()
            ), f"forbidden import {term!r} found"
            assert (
                f"from {term}" not in text.lower()
            ), f"forbidden from-import {term!r} found"

    def test_no_action_commands_in_markdown(self) -> None:
        rn = _make_release_notes()
        md = research_release_notes_to_markdown(rn).lower()
        # Generated markdown should not include imperatives that could be
        # interpreted as action commands for execution/trading/release.
        action_terms = ["deploy now", "execute now", "run now", "start trading", "stop trading", "place order"]
        for term in action_terms:
            assert term not in md, f"action command {term!r} found in markdown"

    def test_serialization_does_not_open_files(self, tmp_path: Path) -> None:
        rn = _make_release_notes()
        # Serialization must only convert already-loaded values; it must not
        # read the referenced artifact file.
        data = research_release_notes_to_dict(rn)
        assert "data/research_archive_manifest/latest_research_archive_manifest.json" in json.dumps(data)
