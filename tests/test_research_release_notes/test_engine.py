"""Tests for hunter.research_release_notes.engine."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from hunter.research_release_notes.engine import (
    build_release_notes_change_item,
    build_release_notes_data_quality,
    build_release_notes_safety_flags,
    build_release_notes_section,
    build_release_notes_summary,
    build_research_release_notes,
    has_unsafe_release_notes_content,
)
from hunter.research_release_notes.models import (
    FORBIDDEN_RELEASE_NOTES_TERMS,
    RELEASE_NOTES_ARTIFACT_INFO,
    RELEASE_NOTES_BLOCKING_REASON_CODES,
    RELEASE_NOTES_REASON_CODES,
    RELEASE_NOTES_VERSION,
    ReleaseNotesChangeItem,
    ReleaseNotesChangeSeverity,
    ReleaseNotesConfig,
    ReleaseNotesSafetyFlags,
    ReleaseNotesSection,
    ReleaseNotesSectionKind,
    ReleaseNotesState,
    ResearchReleaseNotes,
)


def _now() -> datetime:
    return datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _make_config(**kwargs: object) -> ReleaseNotesConfig:
    return ReleaseNotesConfig(**kwargs)


# ---------------------------------------------------------------------------
# has_unsafe_release_notes_content
# ---------------------------------------------------------------------------


class TestHasUnsafeReleaseNotesContent:
    def test_detects_forbidden_term(self) -> None:
        assert has_unsafe_release_notes_content("Deploy now") is True

    def test_detects_action_command_term(self) -> None:
        assert has_unsafe_release_notes_content("Trigger the build") is True

    def test_detects_trading_term(self) -> None:
        assert has_unsafe_release_notes_content("Place an order") is True

    def test_safe_text(self) -> None:
        assert has_unsafe_release_notes_content("Human audit only") is False

    def test_detects_in_metadata(self) -> None:
        assert has_unsafe_release_notes_content(None, {"note": "deploy"}) is True

    def test_reference_strings_are_not_unsafe(self) -> None:
        assert (
            has_unsafe_release_notes_content("data/observation/latest_observation_report.json")
            is False
        )


# ---------------------------------------------------------------------------
# build_release_notes_safety_flags
# ---------------------------------------------------------------------------


class TestBuildReleaseNotesSafetyFlags:
    def test_default_flags_from_config(self) -> None:
        config = ReleaseNotesConfig()
        flags = build_release_notes_safety_flags(config)
        assert flags.dry_run is True
        assert flags.release_notes_feedback_into_execution is False
        assert flags.no_action_commands_emitted is True


# ---------------------------------------------------------------------------
# build_release_notes_change_item
# ---------------------------------------------------------------------------


class TestBuildReleaseNotesChangeItem:
    def test_minimal(self) -> None:
        item = build_release_notes_change_item(title="Test change")
        assert item.title == "Test change"
        assert item.severity == "INFO"

    def test_all_fields(self) -> None:
        item = build_release_notes_change_item(
            title="Test",
            description="Description",
            change_kind="feature",
            severity=ReleaseNotesChangeSeverity.HIGH,
            related_mvp="MVP-15",
            spec_reference="SPEC-016",
            related_references=("data/file.json",),
            metadata={"key": "value"},
        )
        assert item.change_kind == "feature"
        assert item.severity == "HIGH"
        assert item.spec_reference == "SPEC-016"
        assert item.related_references == ("data/file.json",)

    def test_forbidden_title(self) -> None:
        with pytest.raises(ValueError, match="UNSAFE_RELEASE_NOTES_CONTENT"):
            build_release_notes_change_item(title="Run the strategy")


# ---------------------------------------------------------------------------
# build_release_notes_section
# ---------------------------------------------------------------------------


class TestBuildReleaseNotesSection:
    def test_sorts_by_severity(self) -> None:
        items = (
            build_release_notes_change_item(title="Info item", severity="INFO"),
            build_release_notes_change_item(title="Critical item", severity="CRITICAL"),
            build_release_notes_change_item(title="High item", severity="HIGH"),
        )
        section = build_release_notes_section(
            ReleaseNotesSectionKind.KNOWN_GAPS,
            change_items=items,
        )
        titles = [item.title for item in section.change_items]
        assert titles == ["Critical item", "High item", "Info item"]

    def test_sorts_by_mvp_number(self) -> None:
        items = (
            build_release_notes_change_item(title="MVP-15", related_mvp="MVP-15"),
            build_release_notes_change_item(title="MVP-10", related_mvp="MVP-10"),
            build_release_notes_change_item(title="MVP-20", related_mvp="MVP-20"),
        )
        section = build_release_notes_section(
            ReleaseNotesSectionKind.COMPLETED_MVPS,
            change_items=items,
        )
        titles = [item.title for item in section.change_items]
        assert titles == ["MVP-10", "MVP-15", "MVP-20"]

    def test_sorts_by_severity_then_mvp(self) -> None:
        items = (
            build_release_notes_change_item(title="Info MVP-20", severity="INFO", related_mvp="MVP-20"),
            build_release_notes_change_item(title="High MVP-15", severity="HIGH", related_mvp="MVP-15"),
            build_release_notes_change_item(title="Info MVP-10", severity="INFO", related_mvp="MVP-10"),
        )
        section = build_release_notes_section(
            ReleaseNotesSectionKind.COMPLETED_MVPS,
            change_items=items,
        )
        titles = [item.title for item in section.change_items]
        assert titles == ["High MVP-15", "Info MVP-10", "Info MVP-20"]

    def test_deterministic_insertion_order_tie_break(self) -> None:
        items = (
            build_release_notes_change_item(title="First", related_mvp="MVP-15"),
            build_release_notes_change_item(title="Second", related_mvp="MVP-15"),
        )
        section = build_release_notes_section(
            ReleaseNotesSectionKind.COMPLETED_MVPS,
            change_items=items,
        )
        titles = [item.title for item in section.change_items]
        assert titles == ["First", "Second"]


# ---------------------------------------------------------------------------
# build_release_notes_summary
# ---------------------------------------------------------------------------


class TestBuildReleaseNotesSummary:
    def test_ready_state(self) -> None:
        section = ReleaseNotesSection(
            section_kind=ReleaseNotesSectionKind.OVERVIEW,
            section_notes="Overview notes.",
            change_items=(
                ReleaseNotesChangeItem(title="Item 1"),
            ),
        )
        config = ReleaseNotesConfig(required_sections=(ReleaseNotesSectionKind.OVERVIEW,))
        summary = build_release_notes_summary((section,), config=config)
        assert summary.release_notes_state == "READY"
        assert summary.total_sections == 1
        assert summary.total_change_items == 1
        assert summary.info_count == 1

    def test_warn_for_empty_required_section(self) -> None:
        section = ReleaseNotesSection(
            section_kind=ReleaseNotesSectionKind.OVERVIEW,
        )
        config = ReleaseNotesConfig(required_sections=(ReleaseNotesSectionKind.OVERVIEW,))
        summary = build_release_notes_summary((section,), config=config)
        assert summary.release_notes_state == "WARN"
        assert "EMPTY_SECTION" in summary.reason_code_counts

    def test_block_for_missing_required_section(self) -> None:
        section = ReleaseNotesSection(
            section_kind=ReleaseNotesSectionKind.OVERVIEW,
            section_notes="Overview notes.",
        )
        config = ReleaseNotesConfig(
            required_sections=(
                ReleaseNotesSectionKind.OVERVIEW,
                ReleaseNotesSectionKind.COMPLETED_MVPS,
            )
        )
        summary = build_release_notes_summary((section,), config=config)
        assert summary.release_notes_state == "BLOCK"

    def test_severity_counts(self) -> None:
        section = ReleaseNotesSection(
            section_kind=ReleaseNotesSectionKind.KNOWN_GAPS,
            change_items=(
                ReleaseNotesChangeItem(title="Critical", severity="CRITICAL"),
                ReleaseNotesChangeItem(title="High", severity="HIGH"),
                ReleaseNotesChangeItem(title="Info", severity="INFO"),
            ),
        )
        summary = build_release_notes_summary((section,))
        assert summary.critical_count == 1
        assert summary.high_count == 1
        assert summary.info_count == 1
        assert summary.total_change_items == 3


# ---------------------------------------------------------------------------
# build_release_notes_data_quality
# ---------------------------------------------------------------------------


class TestBuildReleaseNotesDataQuality:
    def test_complete_coverage(self) -> None:
        section = ReleaseNotesSection(
            section_kind=ReleaseNotesSectionKind.COMPLETED_MVPS,
            change_items=(
                ReleaseNotesChangeItem(title="MVP-15", spec_reference="SPEC-016"),
                ReleaseNotesChangeItem(title="MVP-16", spec_reference="SPEC-017"),
            ),
        )
        config = ReleaseNotesConfig(required_sections=(ReleaseNotesSectionKind.COMPLETED_MVPS,))
        dq = build_release_notes_data_quality((section,), config=config)
        assert dq.completeness_pct == 100.0
        assert dq.coverage_pct == 100.0
        assert dq.sections_present == 1
        assert dq.sections_missing == 0

    def test_missing_sections(self) -> None:
        config = ReleaseNotesConfig(
            required_sections=(
                ReleaseNotesSectionKind.COMPLETED_MVPS,
                ReleaseNotesSectionKind.KNOWN_GAPS,
            )
        )
        section = ReleaseNotesSection(
            section_kind=ReleaseNotesSectionKind.COMPLETED_MVPS,
            change_items=(ReleaseNotesChangeItem(title="MVP-15"),),
        )
        dq = build_release_notes_data_quality((section,), config=config)
        assert dq.sections_present == 1
        assert dq.sections_missing == 1
        assert dq.completeness_pct == 50.0
        assert dq.change_items_without_specs == 1


# ---------------------------------------------------------------------------
# build_research_release_notes
# ---------------------------------------------------------------------------


class TestBuildResearchReleaseNotes:
    def test_default_build(self) -> None:
        rn = build_research_release_notes(reference_time=_now())
        # Default config requires all sections; COMPLETED_MVPS and KNOWN_GAPS
        # are not auto-populated, so the release notes are blocked.
        assert rn.release_notes_state == ReleaseNotesState.BLOCK
        assert len(rn.sections) == 6
        section_kinds = [s.section_kind for s in rn.sections]
        assert ReleaseNotesSectionKind.COMPLETED_MVPS not in section_kinds
        assert ReleaseNotesSectionKind.KNOWN_GAPS not in section_kinds
        assert "MISSING_COMPLETED_MVPS" in rn.reason_codes
        assert "MISSING_KNOWN_GAPS" in rn.reason_codes

    def test_ready_when_all_required_sections_have_content(self) -> None:
        rn = build_research_release_notes(
            reference_time=_now(),
            change_items_by_section={
                ReleaseNotesSectionKind.COMPLETED_MVPS: (
                    build_release_notes_change_item(
                        title="MVP-19 complete",
                        related_mvp="MVP-19",
                        spec_reference="SPEC-020",
                    ),
                ),
                ReleaseNotesSectionKind.KNOWN_GAPS: (
                    build_release_notes_change_item(
                        title="No known gaps",
                        related_mvp="MVP-20",
                        spec_reference="SPEC-021",
                    ),
                ),
            },
        )
        assert rn.release_notes_state == ReleaseNotesState.READY
        assert rn.summary.release_notes_state == "READY"

    def test_block_for_missing_required_section(self) -> None:
        config = ReleaseNotesConfig(
            required_sections=(
                ReleaseNotesSectionKind.OVERVIEW,
                ReleaseNotesSectionKind.COMPLETED_MVPS,
            )
        )
        rn = build_research_release_notes(
            reference_time=_now(),
            config=config,
            change_items_by_section={
                ReleaseNotesSectionKind.OVERVIEW: (
                    build_release_notes_change_item(title="Overview item"),
                ),
            },
        )
        assert rn.release_notes_state == ReleaseNotesState.BLOCK
        assert "MISSING_COMPLETED_MVPS" in rn.reason_codes

    def test_block_for_unsafe_config(self) -> None:
        # Bypass __post_init__ to simulate an unsafe config reaching the engine.
        unsafe_config = object.__new__(ReleaseNotesConfig)
        object.__setattr__(unsafe_config, "version", RELEASE_NOTES_VERSION)
        object.__setattr__(unsafe_config, "generated_at", None)
        object.__setattr__(unsafe_config, "output_format", "both")
        object.__setattr__(unsafe_config, "dry_run", False)
        object.__setattr__(unsafe_config, "live_trading_enabled", False)
        object.__setattr__(unsafe_config, "real_orders_enabled", False)
        object.__setattr__(unsafe_config, "leverage_enabled", False)
        object.__setattr__(unsafe_config, "shorting_enabled", False)
        object.__setattr__(unsafe_config, "block_on_unknown", True)
        object.__setattr__(unsafe_config, "release_version", "")
        object.__setattr__(unsafe_config, "release_title", "")
        object.__setattr__(unsafe_config, "required_sections", tuple(ReleaseNotesSectionKind))
        object.__setattr__(unsafe_config, "include_release_notes", True)
        rn = build_research_release_notes(
            reference_time=_now(),
            config=unsafe_config,
        )
        assert rn.release_notes_state == ReleaseNotesState.BLOCK
        assert "UNSAFE_CONFIG" in rn.reason_codes

    def test_block_for_unsafe_release_title(self) -> None:
        rn = build_research_release_notes(
            reference_time=_now(),
            release_title="Deploy now",
        )
        assert rn.release_notes_state == ReleaseNotesState.BLOCK
        assert "UNSAFE_RELEASE_NOTES_CONTENT" in rn.reason_codes

    def test_block_for_unsafe_section_notes(self) -> None:
        rn = build_research_release_notes(
            reference_time=_now(),
            section_notes={
                ReleaseNotesSectionKind.OVERVIEW: "Run the strategy",
            },
        )
        assert rn.release_notes_state == ReleaseNotesState.BLOCK
        assert "UNSAFE_SECTION_CONTENT" in rn.reason_codes

    def test_block_for_unresolved_blockers_in_artifact(self) -> None:
        artifact = SimpleNamespace(
            reason_codes=["MISSING_OBSERVATION_REPORT"],
        )
        rn = build_research_release_notes(
            reference_time=_now(),
            input_artifacts={"manifest": artifact},
        )
        assert rn.release_notes_state == ReleaseNotesState.BLOCK
        assert "UNRESOLVED_BLOCKERS" in rn.reason_codes

    def test_block_for_unsafe_safety_flags_in_artifact(self) -> None:
        flags = SimpleNamespace(live_trading_enabled=True)
        artifact = SimpleNamespace(safety_flags=flags)
        rn = build_research_release_notes(
            reference_time=_now(),
            input_artifacts={"manifest": artifact},
        )
        assert rn.release_notes_state == ReleaseNotesState.BLOCK

    def test_empty_release_notes(self) -> None:
        config = ReleaseNotesConfig(required_sections=())
        rn = build_research_release_notes(
            reference_time=_now(),
            config=config,
            change_items_by_section={},
        )
        assert rn.release_notes_state == ReleaseNotesState.BLOCK
        assert "EMPTY_RELEASE_NOTES" in rn.reason_codes

    def test_release_version_and_title(self) -> None:
        rn = build_research_release_notes(
            reference_time=_now(),
            release_version="0.20.0-dev",
            release_title="MVP-20 Release Notes",
            change_items_by_section={
                ReleaseNotesSectionKind.COMPLETED_MVPS: (
                    build_release_notes_change_item(title="MVP-19 complete"),
                ),
                ReleaseNotesSectionKind.KNOWN_GAPS: (
                    build_release_notes_change_item(title="No gaps"),
                ),
            },
        )
        assert rn.release_version == "0.20.0-dev"
        assert rn.release_title == "MVP-20 Release Notes"

    def test_deterministic_section_order(self) -> None:
        rn = build_research_release_notes(
            reference_time=_now(),
            change_items_by_section={
                ReleaseNotesSectionKind.KNOWN_GAPS: (
                    build_release_notes_change_item(title="Gap"),
                ),
                ReleaseNotesSectionKind.COMPLETED_MVPS: (
                    build_release_notes_change_item(title="Done"),
                ),
            },
        )
        section_kinds = [s.section_kind for s in rn.sections]
        assert section_kinds == list(ReleaseNotesSectionKind)

    def test_artifact_chain_reference_strings_are_strings(self) -> None:
        rn = build_research_release_notes(reference_time=_now())
        chain = next(
            s for s in rn.sections if s.section_kind == ReleaseNotesSectionKind.ARTIFACT_CHAIN
        )
        assert len(chain.change_items) == 10
        for item in chain.change_items:
            assert len(item.related_references) == 1
            assert isinstance(item.related_references[0], str)
            assert item.related_references[0].endswith(".json")

    def test_human_review_guide_is_advisory(self) -> None:
        rn = build_research_release_notes(reference_time=_now())
        guide = next(
            s for s in rn.sections if s.section_kind == ReleaseNotesSectionKind.HUMAN_REVIEW_GUIDE
        )
        assert guide.title == "Human Review Guide"
        assert "advisory" in guide.section_notes.lower()
        assert "not a gating checklist" in guide.section_notes.lower()

    def test_no_forbidden_imports(self) -> None:
        import hunter.research_release_notes.engine as engine_module
        import hunter.research_release_notes.models as models_module

        source_engine = Path(engine_module.__file__).read_text()
        source_models = Path(models_module.__file__).read_text()
        forbidden = [
            "import freqtrade",
            "from freqtrade",
            "import binance",
            "from binance",
            "import requests",
            "from requests",
            "import sqlite3",
            "from sqlite3",
        ]
        for term in forbidden:
            assert term not in source_engine, f"forbidden import in engine: {term}"
            assert term not in source_models, f"forbidden import in models: {term}"

    def test_release_notes_not_approval(self) -> None:
        rn = build_research_release_notes(
            reference_time=_now(),
            change_items_by_section={
                ReleaseNotesSectionKind.COMPLETED_MVPS: (
                    build_release_notes_change_item(title="MVP-19"),
                ),
                ReleaseNotesSectionKind.KNOWN_GAPS: (
                    build_release_notes_change_item(title="No gaps"),
                ),
            },
        )
        assert rn.safety_flags.release_notes_output_not_release_approval is True
        assert rn.safety_flags.release_notes_output_not_deployment_approval is True
        assert rn.safety_flags.release_notes_feedback_into_execution is False

    def test_file_refs_not_traversed(self) -> None:
        rn = build_research_release_notes(reference_time=_now())
        assert rn.safety_flags.file_refs_not_traversed is True
        assert rn.safety_flags.artifact_files_not_read is True
