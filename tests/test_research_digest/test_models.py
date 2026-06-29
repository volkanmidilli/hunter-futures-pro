"""Tests for hunter.research_digest.models."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from hunter.research_digest.models import (
    DIGEST_BLOCKING_REASON_CODES,
    DIGEST_REASON_CODES,
    DIGEST_VERSION,
    FORBIDDEN_DIGEST_TERMS,
    DigestConfig,
    DigestDataQuality,
    DigestSafetyFlags,
    DigestSection,
    DigestSectionKind,
    DigestState,
    DigestSummary,
    ResearchDigest,
)


# ---------------------------------------------------------------------------
# DigestState
# ---------------------------------------------------------------------------


class TestDigestState:
    def test_enum_values(self) -> None:
        assert DigestState.DISABLED.value == "disabled"
        assert DigestState.READY.value == "ready"
        assert DigestState.BLOCKED.value == "blocked"
        assert DigestState.UNKNOWN.value == "unknown"


# ---------------------------------------------------------------------------
# DigestSectionKind
# ---------------------------------------------------------------------------


class TestDigestSectionKind:
    def test_enum_values(self) -> None:
        assert DigestSectionKind.OBSERVATION.value == "observation"
        assert DigestSectionKind.REVIEW.value == "review"
        assert DigestSectionKind.INDEX.value == "index"
        assert DigestSectionKind.SEARCH.value == "search"
        assert DigestSectionKind.BUNDLE.value == "bundle"
        assert DigestSectionKind.CHRONICLE.value == "chronicle"

    def test_deterministic_order(self) -> None:
        values = [kind.value for kind in DigestSectionKind]
        assert values == ["observation", "review", "index", "search", "bundle", "chronicle"]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestConstants:
    def test_digest_version(self) -> None:
        assert DIGEST_VERSION == "1.0"

    def test_reason_codes(self) -> None:
        assert len(DIGEST_REASON_CODES) == 17
        assert "EMPTY_DIGEST" in DIGEST_REASON_CODES
        assert "INVALID_OBSERVATION" in DIGEST_REASON_CODES
        assert "INVALID_CHRONICLE" in DIGEST_REASON_CODES
        assert "UNSAFE_DIGEST_CONTENT" in DIGEST_REASON_CODES
        assert "DIGEST_ERROR" in DIGEST_REASON_CODES

    def test_blocking_reason_codes(self) -> None:
        assert "EMPTY_DIGEST" not in DIGEST_BLOCKING_REASON_CODES
        assert "INVALID_CONFIG" in DIGEST_BLOCKING_REASON_CODES
        assert "UNSAFE_CONFIG" in DIGEST_BLOCKING_REASON_CODES
        assert "MISSING_OBSERVATION" in DIGEST_BLOCKING_REASON_CODES

    def test_forbidden_terms_superset_of_chronicle(self) -> None:
        chronicle_terms = {
            "enter_long",
            "enter_short",
            "exit_long",
            "exit_short",
            "api_key",
            "secret",
            "exchange_credentials",
            "executable_instructions",
            "order",
            "position",
            "leverage",
            "margin",
            "liquidation",
            "private_key",
            "password",
            "token",
            "auth",
        }
        for term in chronicle_terms:
            assert term in FORBIDDEN_DIGEST_TERMS, term

    def test_forbidden_terms_digest_specific(self) -> None:
        for term in ("live_trade", "real_order", "market_order", "limit_order", "position_size"):
            assert term in FORBIDDEN_DIGEST_TERMS


# ---------------------------------------------------------------------------
# DigestConfig
# ---------------------------------------------------------------------------


class TestDigestConfig:
    def test_default_construction(self) -> None:
        config = DigestConfig()
        assert config.version == "1.0"
        assert config.output_format == "both"
        assert config.dry_run is True
        assert config.live_trading_enabled is False
        assert config.stale_threshold_minutes == 60

    def test_invalid_version_empty(self) -> None:
        with pytest.raises(ValueError, match="version must be a non-empty string"):
            DigestConfig(version="")

    def test_invalid_output_format(self) -> None:
        with pytest.raises(ValueError, match="output_format must be one of"):
            DigestConfig(output_format="xml")

    def test_invalid_dry_run_false(self) -> None:
        with pytest.raises(ValueError, match="dry_run must be True"):
            DigestConfig(dry_run=False)

    @pytest.mark.parametrize("attr", [
        "live_trading_enabled",
        "real_orders_enabled",
        "leverage_enabled",
        "shorting_enabled",
    ])
    def test_invalid_unsafe_flags_true(self, attr: str) -> None:
        with pytest.raises(ValueError, match=f"{attr} must be False"):
            DigestConfig(**{attr: True})

    def test_invalid_stale_threshold_zero(self) -> None:
        with pytest.raises(ValueError, match="stale_threshold_minutes must be a positive integer"):
            DigestConfig(stale_threshold_minutes=0)

    def test_frozen(self) -> None:
        config = DigestConfig()
        with pytest.raises(FrozenInstanceError):
            config.dry_run = False


# ---------------------------------------------------------------------------
# DigestSafetyFlags
# ---------------------------------------------------------------------------


class TestDigestSafetyFlags:
    def test_default_construction(self) -> None:
        flags = DigestSafetyFlags()
        assert flags.dry_run is True
        assert flags.live_trading_enabled is False
        assert flags.digest_output_is_human_audit_only is True
        assert flags.digest_feedback_into_execution is False
        assert flags.cross_layer_feedback_into_execution is False

    def test_unsafe_flag_true_raises(self) -> None:
        with pytest.raises(ValueError, match="unsafe digest safety flags are enabled"):
            DigestSafetyFlags(live_trading_enabled=True)
        with pytest.raises(ValueError, match="unsafe digest safety flags are enabled"):
            DigestSafetyFlags(digest_feedback_into_execution=True)

    def test_dry_run_false_raises(self) -> None:
        with pytest.raises(ValueError, match="dry_run must be True"):
            DigestSafetyFlags(dry_run=False)

    def test_safe_output_flag_false_raises(self) -> None:
        with pytest.raises(ValueError, match="safe digest output flags must be True"):
            DigestSafetyFlags(digest_output_is_human_audit_only=False)

    def test_cross_layer_feedback_into_execution_true_raises(self) -> None:
        with pytest.raises(ValueError, match="unsafe digest safety flags are enabled"):
            DigestSafetyFlags(cross_layer_feedback_into_execution=True)

    def test_frozen(self) -> None:
        flags = DigestSafetyFlags()
        with pytest.raises(FrozenInstanceError):
            flags.dry_run = False


# ---------------------------------------------------------------------------
# DigestSection
# ---------------------------------------------------------------------------


class TestDigestSection:
    def test_valid_construction(self) -> None:
        section = DigestSection(
            section_kind=DigestSectionKind.OBSERVATION,
            state="READY",
            count=5,
        )
        assert section.section_kind is DigestSectionKind.OBSERVATION
        assert section.state == "READY"
        assert section.count == 5

    def test_invalid_section_kind(self) -> None:
        with pytest.raises(ValueError, match="section_kind must be a DigestSectionKind"):
            DigestSection(section_kind="observation")  # type: ignore[arg-type]

    @pytest.mark.parametrize("state", ["READY", "ready", "Ready"])
    def test_state_normalized(self, state: str) -> None:
        section = DigestSection(section_kind=DigestSectionKind.REVIEW, state=state)
        assert section.state == "READY"

    def test_invalid_state(self) -> None:
        with pytest.raises(ValueError, match="state must be one of"):
            DigestSection(section_kind=DigestSectionKind.INDEX, state="CORRUPTED")

    def test_negative_count_raises(self) -> None:
        with pytest.raises(ValueError, match="count must be a non-negative integer"):
            DigestSection(section_kind=DigestSectionKind.SEARCH, count=-1)

    def test_notes_allowed_without_validation(self) -> None:
        # DigestSection itself does not validate forbidden terms; engine blocks.
        section = DigestSection(
            section_kind=DigestSectionKind.BUNDLE,
            notes="contains api_key value",
        )
        assert section.notes == "contains api_key value"

    def test_file_reference_not_traversed(self) -> None:
        section = DigestSection(
            section_kind=DigestSectionKind.OBSERVATION,
            metadata={"path": "/tmp/report.json"},
        )
        assert section.metadata["path"] == "/tmp/report.json"


# ---------------------------------------------------------------------------
# DigestSummary
# ---------------------------------------------------------------------------


class TestDigestSummary:
    def test_default_construction(self) -> None:
        summary = DigestSummary()
        assert summary.total_sections == 0
        assert summary.cross_layer_ready is False

    def test_valid_construction(self) -> None:
        summary = DigestSummary(
            total_sections=6,
            ready_sections=4,
            blocked_sections=2,
            missing_sections=1,
            total_artifacts=42,
        )
        assert summary.ready_sections + summary.blocked_sections == summary.total_sections
        assert summary.missing_sections <= summary.total_sections

    def test_overlap_allowed(self) -> None:
        summary = DigestSummary(
            total_sections=6,
            ready_sections=4,
            blocked_sections=2,
            missing_sections=2,
        )
        assert summary.ready_sections + summary.blocked_sections == 6
        assert summary.missing_sections == 2

    def test_ready_plus_blocked_exceeds_total_raises(self) -> None:
        with pytest.raises(ValueError, match=r"ready_sections \+ blocked_sections must be <= total_sections"):
            DigestSummary(total_sections=6, ready_sections=4, blocked_sections=3)

    def test_missing_exceeds_total_raises(self) -> None:
        with pytest.raises(ValueError, match="missing_sections must be <= total_sections"):
            DigestSummary(total_sections=6, missing_sections=7)

    def test_unresolved_blockers_exceed_total_raises(self) -> None:
        with pytest.raises(ValueError, match="unresolved_blockers must be <= total_blockers"):
            DigestSummary(total_blockers=1, unresolved_blockers=2)

    def test_unsafe_next_review_notes_raises(self) -> None:
        with pytest.raises(ValueError, match="UNSAFE_DIGEST_CONTENT"):
            DigestSummary(next_review_notes="enter_long now")


# ---------------------------------------------------------------------------
# DigestDataQuality
# ---------------------------------------------------------------------------


class TestDigestDataQuality:
    def test_default_construction(self) -> None:
        dq = DigestDataQuality()
        assert dq.completeness_pct == 0.0
        assert dq.total_sections == 0

    def test_completeness_pct_range(self) -> None:
        with pytest.raises(ValueError, match="completeness_pct must be between"):
            DigestDataQuality(completeness_pct=101.0)

    def test_unsafe_reason_raises(self) -> None:
        with pytest.raises(ValueError, match="UNSAFE_DIGEST_CONTENT"):
            DigestDataQuality(reason="contains secret")


# ---------------------------------------------------------------------------
# ResearchDigest
# ---------------------------------------------------------------------------


class TestResearchDigest:
    def test_valid_construction(self) -> None:
        now = datetime.now(timezone.utc)
        digest = ResearchDigest(
            digest_id="digest:1.0:2025-01-01T00:00:00",
            generated_at=now,
            state=DigestState.READY,
        )
        assert digest.digest_id == "digest:1.0:2025-01-01T00:00:00"
        assert digest.generated_at == now
        assert digest.state is DigestState.READY

    def test_default_state(self) -> None:
        now = datetime.now(timezone.utc)
        digest = ResearchDigest(digest_id="d1", generated_at=now)
        assert digest.state is DigestState.UNKNOWN

    def test_invalid_digest_id_empty(self) -> None:
        with pytest.raises(ValueError, match="digest_id must be a non-empty string"):
            ResearchDigest(digest_id="", generated_at=datetime.now(timezone.utc))

    def test_invalid_generated_at_naive(self) -> None:
        with pytest.raises(ValueError, match="generated_at must be a timezone-aware datetime"):
            ResearchDigest(digest_id="d1", generated_at=datetime.now())

    def test_invalid_state_type(self) -> None:
        with pytest.raises(ValueError, match="state must be a DigestState"):
            ResearchDigest(
                digest_id="d1",
                generated_at=datetime.now(timezone.utc),
                state="READY",  # type: ignore[arg-type]
            )

    def test_blocked_factory(self) -> None:
        now = datetime.now(timezone.utc)
        digest = ResearchDigest.blocked("EMPTY_DIGEST", generated_at=now)
        assert digest.state is DigestState.BLOCKED
        assert digest.reason_codes == ("EMPTY_DIGEST",)
        assert "Digest blocked: EMPTY_DIGEST" in digest.summary.next_review_notes
        assert digest.data_quality.blocked_count == 1

    def test_frozen(self) -> None:
        now = datetime.now(timezone.utc)
        digest = ResearchDigest(digest_id="d1", generated_at=now)
        with pytest.raises(FrozenInstanceError):
            digest.digest_id = "d2"

    def test_unsafe_next_review_notes_raises(self) -> None:
        with pytest.raises(ValueError, match="UNSAFE_DIGEST_CONTENT"):
            ResearchDigest(
                digest_id="d1",
                generated_at=datetime.now(timezone.utc),
                next_review_notes="place order",
            )
