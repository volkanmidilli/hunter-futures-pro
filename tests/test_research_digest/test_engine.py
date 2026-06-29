"""Tests for hunter.research_digest.engine."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from hunter.research_digest.engine import (
    build_digest_data_quality,
    build_digest_safety_flags,
    build_digest_section,
    build_digest_summary,
    build_research_digest,
    has_unsafe_digest_content,
)
from hunter.research_digest.models import (
    DigestConfig,
    DigestSafetyFlags,
    DigestSection,
    DigestSectionKind,
    DigestState,
    FORBIDDEN_DIGEST_TERMS,
    ResearchDigest,
)


# ---------------------------------------------------------------------------
# has_unsafe_digest_content
# ---------------------------------------------------------------------------


class TestHasUnsafeDigestContent:
    def test_safe_text(self) -> None:
        assert has_unsafe_digest_content("normal research notes") is False

    def test_forbidden_term_api_key(self) -> None:
        assert has_unsafe_digest_content("contains api_key") is True

    def test_forbidden_term_private_key(self) -> None:
        assert has_unsafe_digest_content("private_key leaked") is True

    def test_case_insensitive(self) -> None:
        assert has_unsafe_digest_content("ENTER_LONG") is True
        assert has_unsafe_digest_content("API_KEY") is True

    def test_empty_text(self) -> None:
        assert has_unsafe_digest_content("") is False
        assert has_unsafe_digest_content(None) is False

    def test_unsafe_metadata(self) -> None:
        assert has_unsafe_digest_content(None, {"token": "abc"}) is True

    def test_safe_metadata(self) -> None:
        assert has_unsafe_digest_content(None, {"path": "/tmp/report.json"}) is False


# ---------------------------------------------------------------------------
# build_digest_safety_flags
# ---------------------------------------------------------------------------


class TestBuildDigestSafetyFlags:
    def test_default_config(self) -> None:
        flags = build_digest_safety_flags(DigestConfig())
        assert flags.dry_run is True
        assert flags.live_trading_enabled is False
        assert flags.digest_feedback_into_execution is False

    def test_unsafe_config_rejected(self) -> None:
        # DigestConfig itself rejects dry_run=False during construction.
        with pytest.raises(ValueError, match="dry_run must be True"):
            DigestConfig(dry_run=False)

    def test_unsafe_config_passed_directly_raises(self) -> None:
        # Manually construct an unsafe config that bypasses __post_init__.
        config = object.__new__(DigestConfig)
        object.__setattr__(config, "version", "1.0")
        object.__setattr__(config, "generated_at", None)
        object.__setattr__(config, "output_format", "both")
        object.__setattr__(config, "dry_run", False)
        object.__setattr__(config, "live_trading_enabled", False)
        object.__setattr__(config, "real_orders_enabled", False)
        object.__setattr__(config, "leverage_enabled", False)
        object.__setattr__(config, "shorting_enabled", False)
        object.__setattr__(config, "stale_threshold_minutes", 60)
        object.__setattr__(config, "include_next_review_notes", True)
        object.__setattr__(config, "include_safety_flags", True)
        object.__setattr__(config, "include_unresolved_blockers", True)
        object.__setattr__(config, "include_reason_code_summary", True)
        with pytest.raises(ValueError, match="dry_run must be True"):
            build_digest_safety_flags(config)


# ---------------------------------------------------------------------------
# build_digest_section
# ---------------------------------------------------------------------------


class TestBuildDigestSection:
    def test_ready_section(self) -> None:
        section = build_digest_section(
            section_kind=DigestSectionKind.OBSERVATION,
            artifact_state="READY",
            artifact_count=5,
        )
        assert section.state == "READY"
        assert section.count == 5
        assert section.blockers_count == 0

    def test_blocked_section(self) -> None:
        section = build_digest_section(
            section_kind=DigestSectionKind.REVIEW,
            artifact_state="BLOCKED",
            artifact_count=0,
            blocked_count=1,
            reason_codes=("MISSING_REVIEW",),
        )
        assert section.state == "BLOCKED"
        assert section.blockers_count == 1
        assert section.unresolved_blocker_reasons == ("MISSING_REVIEW",)

    def test_missing_section(self) -> None:
        section = build_digest_section(
            section_kind=DigestSectionKind.INDEX,
            artifact_state=None,
            artifact_count=0,
        )
        assert section.state == "UNKNOWN"
        assert section.missing_count == 1
        assert section.blockers_count == 1

    def test_empty_state_string(self) -> None:
        section = build_digest_section(
            section_kind=DigestSectionKind.SEARCH,
            artifact_state="",
            artifact_count=0,
        )
        assert section.state == "UNKNOWN"
        assert section.missing_count == 1

    def test_unsafe_ready_content_becomes_blocked(self) -> None:
        section = build_digest_section(
            section_kind=DigestSectionKind.BUNDLE,
            artifact_state="READY",
            notes="contains api_key",
        )
        assert section.state == "BLOCKED"
        assert "UNSAFE_DIGEST_CONTENT" in section.reason_codes

    def test_invalid_section_kind_raises(self) -> None:
        with pytest.raises(ValueError, match="section_kind must be a DigestSectionKind"):
            build_digest_section(section_kind="observation")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# build_digest_summary
# ---------------------------------------------------------------------------


class TestBuildDigestSummary:
    def test_empty_sections(self) -> None:
        summary = build_digest_summary([])
        assert summary.total_sections == 0
        assert summary.cross_layer_ready is False

    def test_all_ready(self) -> None:
        sections = [
            build_digest_section(DigestSectionKind.OBSERVATION, "READY"),
            build_digest_section(DigestSectionKind.REVIEW, "READY"),
        ]
        summary = build_digest_summary(sections)
        assert summary.total_sections == 2
        assert summary.ready_sections == 2
        assert summary.cross_layer_ready is True
        assert "All layers ready" in summary.next_review_notes

    def test_blocked_sections(self) -> None:
        sections = [
            build_digest_section(DigestSectionKind.OBSERVATION, "READY"),
            build_digest_section(DigestSectionKind.REVIEW, "BLOCKED"),
        ]
        summary = build_digest_summary(sections)
        assert summary.cross_layer_ready is False
        assert "Blocked sections detected: review" in summary.next_review_notes

    def test_missing_sections(self) -> None:
        sections = [
            build_digest_section(DigestSectionKind.OBSERVATION, "READY"),
            build_digest_section(DigestSectionKind.INDEX, None),
        ]
        summary = build_digest_summary(sections)
        assert summary.missing_sections == 1
        assert "Missing sections detected: index" in summary.next_review_notes

    def test_reason_code_counts_sorted(self) -> None:
        sections = [
            build_digest_section(
                DigestSectionKind.OBSERVATION,
                "BLOCKED",
                reason_codes=("MISSING_OBSERVATION",),
            ),
            build_digest_section(
                DigestSectionKind.REVIEW,
                "BLOCKED",
                reason_codes=("MISSING_REVIEW",),
            ),
        ]
        summary = build_digest_summary(sections)
        assert list(summary.reason_code_counts.keys()) == sorted(summary.reason_code_counts.keys())


# ---------------------------------------------------------------------------
# build_digest_data_quality
# ---------------------------------------------------------------------------


class TestBuildDigestDataQuality:
    def test_empty_sections(self) -> None:
        dq = build_digest_data_quality([])
        assert dq.completeness_pct == 0.0
        assert dq.total_sections == 0

    def test_completeness(self) -> None:
        sections = [
            build_digest_section(DigestSectionKind.OBSERVATION, "READY"),
            build_digest_section(DigestSectionKind.REVIEW, "BLOCKED"),
        ]
        dq = build_digest_data_quality(sections)
        assert dq.completeness_pct == 50.0
        assert dq.total_sections == 2

    def test_invalid_count(self) -> None:
        sections = [
            build_digest_section(
                DigestSectionKind.OBSERVATION,
                "BLOCKED",
                reason_codes=("INVALID_OBSERVATION",),
            ),
        ]
        dq = build_digest_data_quality(sections)
        assert dq.invalid_count == 1


# ---------------------------------------------------------------------------
# build_research_digest
# ---------------------------------------------------------------------------


class TestBuildResearchDigest:
    def test_empty_digest_blocked(self) -> None:
        digest = build_research_digest()
        assert digest.state is DigestState.BLOCKED
        assert "EMPTY_DIGEST" in digest.reason_codes
        assert digest.safety_flags.dry_run is True

    def test_all_ready(self) -> None:
        digest = build_research_digest(
            observation_state="READY",
            review_state="READY",
            index_state="READY",
            search_state="READY",
            bundle_state="READY",
            chronicle_state="READY",
            observation_count=10,
            review_count=5,
            index_count=3,
            search_count=2,
            bundle_count=1,
            chronicle_count=1,
        )
        assert digest.state is DigestState.READY
        assert digest.summary.cross_layer_ready is True
        assert len(digest.sections) == 6
        assert digest.sections[0].section_kind is DigestSectionKind.OBSERVATION
        assert digest.sections[-1].section_kind is DigestSectionKind.CHRONICLE

    def test_missing_observation_blocked(self) -> None:
        digest = build_research_digest(
            review_state="READY",
            index_state="READY",
            search_state="READY",
            bundle_state="READY",
            chronicle_state="READY",
        )
        assert digest.state is DigestState.BLOCKED
        assert "MISSING_OBSERVATION" in digest.reason_codes

    def test_invalid_observation_state_blocked(self) -> None:
        digest = build_research_digest(
            observation_state="CORRUPTED",
            review_state="READY",
            index_state="READY",
            search_state="READY",
            bundle_state="READY",
            chronicle_state="READY",
        )
        assert digest.state is DigestState.BLOCKED
        assert "INVALID_OBSERVATION" in digest.reason_codes

    def test_unsafe_config_blocked(self) -> None:
        # dry_run=False is rejected by DigestConfig itself, so we simulate via monkeypatch
        # by constructing an unsafe config manually. Because DigestConfig rejects it,
        # the only way to test build_research_digest's fail-closed behavior is to pass
        # a config that bypasses validation. We use object.__new__ to create one.
        config = object.__new__(DigestConfig)
        object.__setattr__(config, "version", "1.0")
        object.__setattr__(config, "generated_at", None)
        object.__setattr__(config, "output_format", "both")
        object.__setattr__(config, "dry_run", False)
        object.__setattr__(config, "live_trading_enabled", False)
        object.__setattr__(config, "real_orders_enabled", False)
        object.__setattr__(config, "leverage_enabled", False)
        object.__setattr__(config, "shorting_enabled", False)
        object.__setattr__(config, "stale_threshold_minutes", 60)
        object.__setattr__(config, "include_next_review_notes", True)
        object.__setattr__(config, "include_safety_flags", True)
        object.__setattr__(config, "include_unresolved_blockers", True)
        object.__setattr__(config, "include_reason_code_summary", True)

        digest = build_research_digest(
            config=config,
            observation_state="READY",
            review_state="READY",
            index_state="READY",
            search_state="READY",
            bundle_state="READY",
            chronicle_state="READY",
        )
        assert digest.state is DigestState.BLOCKED
        assert "UNSAFE_CONFIG" in digest.reason_codes

    def test_unsafe_next_review_notes_blocked(self) -> None:
        digest = build_research_digest(
            observation_state="READY",
            review_state="READY",
            index_state="READY",
            search_state="READY",
            bundle_state="READY",
            chronicle_state="READY",
            next_review_notes="place order now",
        )
        assert digest.state is DigestState.BLOCKED
        assert "UNSAFE_DIGEST_CONTENT" in digest.reason_codes

    def test_digest_id_is_deterministic(self) -> None:
        generated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        config = DigestConfig(generated_at=generated_at)
        digest = build_research_digest(
            config=config,
            observation_state="READY",
            review_state="READY",
            index_state="READY",
            search_state="READY",
            bundle_state="READY",
            chronicle_state="READY",
        )
        expected = f"digest:1.0:{generated_at.strftime('%Y-%m-%dT%H:%M:%S.%f')}"
        assert digest.digest_id == expected

    def test_reason_codes_collected_from_sections(self) -> None:
        digest = build_research_digest(
            observation_state="BLOCKED",
            observation_reason_codes=("MISSING_OBSERVATION",),
            review_state="READY",
            index_state="READY",
            search_state="READY",
            bundle_state="READY",
            chronicle_state="READY",
        )
        assert digest.state is DigestState.BLOCKED
        assert "MISSING_OBSERVATION" in digest.reason_codes

    def test_blocked_count_with_missing(self) -> None:
        digest = build_research_digest(
            observation_state="READY",
            review_state="READY",
            index_state="READY",
            search_state="READY",
            bundle_state="READY",
            chronicle_state="READY",
        )
        # All sections should be READY with blockers_count == 0
        for section in digest.sections:
            assert section.state == "READY"
            assert section.blockers_count == 0


# ---------------------------------------------------------------------------
# Safety invariants
# ---------------------------------------------------------------------------


class TestSafetyInvariants:
    def test_no_execution_feedback(self) -> None:
        digest = build_research_digest(
            observation_state="READY",
            review_state="READY",
            index_state="READY",
            search_state="READY",
            bundle_state="READY",
            chronicle_state="READY",
        )
        assert digest.safety_flags.digest_feedback_into_execution is False
        assert digest.safety_flags.cross_layer_feedback_into_execution is False

    def test_no_forbidden_terms_in_next_review_notes(self) -> None:
        digest = build_research_digest(
            observation_state="READY",
            review_state="READY",
            index_state="READY",
            search_state="READY",
            bundle_state="READY",
            chronicle_state="READY",
        )
        for term in FORBIDDEN_DIGEST_TERMS:
            assert term.lower() not in digest.summary.next_review_notes.lower()

    def test_file_references_are_strings_only(self) -> None:
        digest = build_research_digest(
            observation_state="READY",
            review_state="READY",
            index_state="READY",
            search_state="READY",
            bundle_state="READY",
            chronicle_state="READY",
        )
        # Sections should not traverse, open, or execute anything.
        for section in digest.sections:
            assert isinstance(section.section_kind.value, str)
            assert isinstance(section.state, str)
