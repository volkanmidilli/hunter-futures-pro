"""Tests for hunter.research_release_notes.models."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from hunter.research_release_notes.models import (
    FORBIDDEN_RELEASE_NOTES_TERMS,
    RELEASE_NOTES_ARTIFACT_INFO,
    RELEASE_NOTES_BLOCKING_REASON_CODES,
    RELEASE_NOTES_REASON_CODES,
    RELEASE_NOTES_VERSION,
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


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TestReleaseNotesState:
    def test_enum_values(self) -> None:
        assert ReleaseNotesState.READY.value == "ready"
        assert ReleaseNotesState.WARN.value == "warn"
        assert ReleaseNotesState.BLOCK.value == "block"
        assert ReleaseNotesState.UNKNOWN.value == "unknown"


class TestReleaseNotesKind:
    def test_enum_values(self) -> None:
        assert ReleaseNotesKind.RESEARCH_RELEASE_NOTES.value == "research_release_notes"


class TestReleaseNotesSectionKind:
    def test_enum_values(self) -> None:
        assert ReleaseNotesSectionKind.OVERVIEW.value == "overview"
        assert ReleaseNotesSectionKind.VERSION_AND_SCOPE.value == "version_and_scope"
        assert ReleaseNotesSectionKind.ARTIFACT_CHAIN.value == "artifact_chain"
        assert ReleaseNotesSectionKind.COMPLETED_MVPS.value == "completed_mvps"
        assert ReleaseNotesSectionKind.KNOWN_GAPS.value == "known_gaps"
        assert ReleaseNotesSectionKind.SAFETY_BOUNDARIES.value == "safety_boundaries"
        assert ReleaseNotesSectionKind.HUMAN_REVIEW_GUIDE.value == "human_review_guide"
        assert ReleaseNotesSectionKind.APPENDIX_REFERENCES.value == "appendix_references"

    def test_deterministic_order(self) -> None:
        values = [kind.value for kind in ReleaseNotesSectionKind]
        assert values == [
            "overview",
            "version_and_scope",
            "artifact_chain",
            "completed_mvps",
            "known_gaps",
            "safety_boundaries",
            "human_review_guide",
            "appendix_references",
        ]


class TestReleaseNotesChangeSeverity:
    def test_enum_values(self) -> None:
        assert ReleaseNotesChangeSeverity.CRITICAL.value == "critical"
        assert ReleaseNotesChangeSeverity.HIGH.value == "high"
        assert ReleaseNotesChangeSeverity.MEDIUM.value == "medium"
        assert ReleaseNotesChangeSeverity.LOW.value == "low"
        assert ReleaseNotesChangeSeverity.INFO.value == "info"


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestConstants:
    def test_release_notes_version(self) -> None:
        assert RELEASE_NOTES_VERSION == "1.0"

    def test_reason_codes(self) -> None:
        assert len(RELEASE_NOTES_REASON_CODES) == 19
        assert "EMPTY_RELEASE_NOTES" in RELEASE_NOTES_REASON_CODES
        assert "INVALID_CONFIG" in RELEASE_NOTES_REASON_CODES
        assert "UNSAFE_CONFIG" in RELEASE_NOTES_REASON_CODES
        assert "MISSING_OVERVIEW" in RELEASE_NOTES_REASON_CODES
        assert "MISSING_HUMAN_REVIEW_GUIDE" in RELEASE_NOTES_REASON_CODES
        assert "EMPTY_SECTION" in RELEASE_NOTES_REASON_CODES
        assert "INVALID_CHANGE_ITEM" in RELEASE_NOTES_REASON_CODES
        assert "UNSAFE_CHANGE_ITEM_CONTENT" in RELEASE_NOTES_REASON_CODES
        assert "UNSAFE_SECTION_CONTENT" in RELEASE_NOTES_REASON_CODES
        assert "MISSING_SPEC_REFERENCE" in RELEASE_NOTES_REASON_CODES
        assert "UNRESOLVED_BLOCKERS" in RELEASE_NOTES_REASON_CODES
        assert "UNSAFE_RELEASE_NOTES_CONTENT" in RELEASE_NOTES_REASON_CODES
        assert "RELEASE_NOTES_ERROR" in RELEASE_NOTES_REASON_CODES

    def test_blocking_reason_codes(self) -> None:
        assert "EMPTY_RELEASE_NOTES" not in RELEASE_NOTES_BLOCKING_REASON_CODES
        assert "MISSING_OVERVIEW" in RELEASE_NOTES_BLOCKING_REASON_CODES
        assert "EMPTY_SECTION" in RELEASE_NOTES_BLOCKING_REASON_CODES

    def test_artifact_info_has_ten_families(self) -> None:
        assert len(RELEASE_NOTES_ARTIFACT_INFO) == 10
        assert "RESEARCH_ARCHIVE_MANIFEST" in RELEASE_NOTES_ARTIFACT_INFO

    def test_artifact_info_strings_are_not_opened(self) -> None:
        for family, (local_ref, spec_ref) in RELEASE_NOTES_ARTIFACT_INFO.items():
            assert isinstance(local_ref, str)
            assert isinstance(spec_ref, str)
            assert local_ref.endswith(".json")
            assert spec_ref.startswith("SPEC-")


# ---------------------------------------------------------------------------
# ReleaseNotesConfig
# ---------------------------------------------------------------------------


class TestReleaseNotesConfig:
    def test_default_config(self) -> None:
        config = ReleaseNotesConfig()
        assert config.version == RELEASE_NOTES_VERSION
        assert config.output_format == "both"
        assert config.dry_run is True
        assert config.live_trading_enabled is False
        assert config.block_on_unknown is True
        assert len(config.required_sections) == 8

    def test_dry_run_must_be_true(self) -> None:
        with pytest.raises(ValueError, match="dry_run must be True"):
            ReleaseNotesConfig(dry_run=False)

    def test_live_trading_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="live_trading_enabled must be False"):
            ReleaseNotesConfig(live_trading_enabled=True)

    def test_invalid_output_format(self) -> None:
        with pytest.raises(ValueError, match="output_format"):
            ReleaseNotesConfig(output_format="xml")

    def test_required_sections_must_be_enum_instances(self) -> None:
        with pytest.raises(ValueError, match="required_sections"):
            ReleaseNotesConfig(required_sections=("overview",))  # type: ignore[arg-type]

    def test_release_version_validation(self) -> None:
        config = ReleaseNotesConfig(release_version="0.20.0-dev")
        assert config.release_version == "0.20.0-dev"

    def test_release_title_forbidden_term(self) -> None:
        with pytest.raises(ValueError, match="UNSAFE_RELEASE_NOTES_CONTENT"):
            ReleaseNotesConfig(release_title="Ready to go_live")


# ---------------------------------------------------------------------------
# ReleaseNotesSafetyFlags
# ---------------------------------------------------------------------------


class TestReleaseNotesSafetyFlags:
    def test_default_flags(self) -> None:
        flags = ReleaseNotesSafetyFlags()
        assert flags.dry_run is True
        assert flags.live_trading_enabled is False
        assert flags.release_notes_output_is_human_audit_only is True
        assert flags.release_notes_output_not_release_approval is True
        assert flags.release_notes_output_not_deployment_approval is True
        assert flags.release_notes_feedback_into_execution is False
        assert flags.cross_layer_feedback_into_execution is False
        assert flags.file_refs_not_traversed is True
        assert flags.artifact_files_not_read is True
        assert flags.no_action_commands_emitted is True

    def test_feedback_flag_must_be_false(self) -> None:
        with pytest.raises(ValueError, match="unsafe release notes safety flags"):
            ReleaseNotesSafetyFlags(release_notes_feedback_into_execution=True)

    def test_safe_output_flag_must_be_true(self) -> None:
        with pytest.raises(ValueError, match="safe release notes output flags"):
            ReleaseNotesSafetyFlags(release_notes_output_not_trade_approval=False)

    def test_no_action_commands_emitted_must_be_true(self) -> None:
        with pytest.raises(ValueError, match="safe release notes output flags"):
            ReleaseNotesSafetyFlags(no_action_commands_emitted=False)


# ---------------------------------------------------------------------------
# ReleaseNotesChangeItem
# ---------------------------------------------------------------------------


class TestReleaseNotesChangeItem:
    def test_minimal_item(self) -> None:
        item = ReleaseNotesChangeItem(title="Test change")
        assert item.title == "Test change"
        assert item.severity == "INFO"
        assert item.related_references == ()

    def test_change_kind_field(self) -> None:
        item = ReleaseNotesChangeItem(
            title="Test change",
            change_kind="feature",
        )
        assert item.change_kind == "feature"

    def test_severity_normalization(self) -> None:
        item = ReleaseNotesChangeItem(title="Test", severity="high")
        assert item.severity == "HIGH"

    def test_invalid_severity(self) -> None:
        with pytest.raises(ValueError, match="severity"):
            ReleaseNotesChangeItem(title="Test", severity="urgent")

    def test_empty_title(self) -> None:
        with pytest.raises(ValueError, match="title"):
            ReleaseNotesChangeItem(title="")
        with pytest.raises(ValueError, match="title"):
            ReleaseNotesChangeItem(title="   ")

    def test_forbidden_title(self) -> None:
        with pytest.raises(ValueError, match="UNSAFE_RELEASE_NOTES_CONTENT"):
            ReleaseNotesChangeItem(title="Deploy now")

    def test_forbidden_description(self) -> None:
        with pytest.raises(ValueError, match="UNSAFE_RELEASE_NOTES_CONTENT"):
            ReleaseNotesChangeItem(
                title="Test",
                description="Trigger the strategy execution",
            )

    def test_related_references_are_strings_only(self) -> None:
        item = ReleaseNotesChangeItem(
            title="Test",
            related_references=("data/file.json",),
        )
        assert item.related_references == ("data/file.json",)

    def test_frozen(self) -> None:
        item = ReleaseNotesChangeItem(title="Test")
        with pytest.raises(FrozenInstanceError):
            item.title = "Other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ReleaseNotesSection
# ---------------------------------------------------------------------------


class TestReleaseNotesSection:
    def test_default_title(self) -> None:
        section = ReleaseNotesSection(
            section_kind=ReleaseNotesSectionKind.OVERVIEW,
        )
        assert section.title == "Overview"

    def test_custom_title(self) -> None:
        section = ReleaseNotesSection(
            section_kind=ReleaseNotesSectionKind.OVERVIEW,
            title="Custom Overview",
        )
        assert section.title == "Custom Overview"

    def test_forbidden_section_notes(self) -> None:
        with pytest.raises(ValueError, match="UNSAFE_RELEASE_NOTES_CONTENT"):
            ReleaseNotesSection(
                section_kind=ReleaseNotesSectionKind.OVERVIEW,
                section_notes="Deploy this immediately",
            )

    def test_change_items_coerced(self) -> None:
        item = ReleaseNotesChangeItem(title="Test")
        section = ReleaseNotesSection(
            section_kind=ReleaseNotesSectionKind.COMPLETED_MVPS,
            change_items=[item],
        )
        assert len(section.change_items) == 1


# ---------------------------------------------------------------------------
# ReleaseNotesSummary
# ---------------------------------------------------------------------------


class TestReleaseNotesSummary:
    def test_default_summary(self) -> None:
        summary = ReleaseNotesSummary()
        assert summary.total_sections == 0
        assert summary.release_notes_state == "UNKNOWN"

    def test_count_sum_validation(self) -> None:
        with pytest.raises(ValueError, match="must equal total_change_items"):
            ReleaseNotesSummary(
                total_change_items=1,
                info_count=0,
            )

    def test_invalid_state(self) -> None:
        with pytest.raises(ValueError, match="release_notes_state"):
            ReleaseNotesSummary(release_notes_state="invalid")

    def test_forbidden_notes(self) -> None:
        with pytest.raises(ValueError, match="UNSAFE_RELEASE_NOTES_CONTENT"):
            ReleaseNotesSummary(release_notes="Deploy now")


# ---------------------------------------------------------------------------
# ReleaseNotesDataQuality
# ---------------------------------------------------------------------------


class TestReleaseNotesDataQuality:
    def test_default_data_quality(self) -> None:
        dq = ReleaseNotesDataQuality()
        assert dq.completeness_pct == 0.0
        assert dq.total_sections == 0

    def test_pct_range_validation(self) -> None:
        with pytest.raises(ValueError, match="completeness_pct"):
            ReleaseNotesDataQuality(completeness_pct=101.0)

    def test_section_count_validation(self) -> None:
        with pytest.raises(ValueError, match="sections_present"):
            ReleaseNotesDataQuality(
                sections_present=1,
                sections_missing=1,
                total_sections=1,
            )


# ---------------------------------------------------------------------------
# ResearchReleaseNotes
# ---------------------------------------------------------------------------


class TestResearchReleaseNotes:
    def test_default_kind(self) -> None:
        now = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        rn = ResearchReleaseNotes(
            release_notes_id="rn:1",
            generated_at=now,
        )
        assert rn.kind == ReleaseNotesKind.RESEARCH_RELEASE_NOTES
        assert rn.release_notes_state == ReleaseNotesState.UNKNOWN

    def test_document_notes_instead_of_release_notes_field(self) -> None:
        now = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        rn = ResearchReleaseNotes(
            release_notes_id="rn:1",
            generated_at=now,
            document_notes="Safe human audit notes.",
        )
        assert rn.document_notes == "Safe human audit notes."

    def test_empty_id(self) -> None:
        now = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        with pytest.raises(ValueError, match="release_notes_id"):
            ResearchReleaseNotes(release_notes_id="", generated_at=now)

    def test_naive_datetime(self) -> None:
        now = datetime(2025, 1, 1, 12, 0, 0)
        with pytest.raises(ValueError, match="timezone-aware"):
            ResearchReleaseNotes(release_notes_id="rn:1", generated_at=now)

    def test_blocked_factory(self) -> None:
        now = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        rn = ResearchReleaseNotes.blocked("UNSAFE_CONFIG", generated_at=now)
        assert rn.release_notes_state == ReleaseNotesState.BLOCK
        assert rn.summary.release_notes_state == "BLOCK"
        assert "not publish approval" in rn.document_notes
        assert "not execution readiness" in rn.document_notes

    def test_frozen(self) -> None:
        now = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        rn = ResearchReleaseNotes(release_notes_id="rn:1", generated_at=now)
        with pytest.raises(FrozenInstanceError):
            rn.release_version = "x"  # type: ignore[misc]
