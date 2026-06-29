"""Tests for hunter.research_handoff.models."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from hunter.research_handoff.models import (
    FORBIDDEN_HANDOFF_TERMS,
    HANDOFF_BLOCKING_REASON_CODES,
    HANDOFF_REASON_CODES,
    HANDOFF_VERSION,
    HandoffConfig,
    HandoffDataQuality,
    HandoffPacketKind,
    HandoffSafetyFlags,
    HandoffSection,
    HandoffState,
    HandoffSummary,
    ResearchHandoffPacket,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TestHandoffState:
    def test_enum_values(self) -> None:
        assert HandoffState.READY.value == "ready"
        assert HandoffState.WARN.value == "warn"
        assert HandoffState.BLOCK.value == "block"
        assert HandoffState.UNKNOWN.value == "unknown"


class TestHandoffPacketKind:
    def test_enum_values(self) -> None:
        assert HandoffPacketKind.OBSERVATION.value == "observation"
        assert HandoffPacketKind.REVIEW.value == "review"
        assert HandoffPacketKind.INDEX.value == "index"
        assert HandoffPacketKind.SEARCH.value == "search"
        assert HandoffPacketKind.BUNDLE.value == "bundle"
        assert HandoffPacketKind.CHRONICLE.value == "chronicle"
        assert HandoffPacketKind.DIGEST.value == "digest"
        assert HandoffPacketKind.QUALITY_GATE.value == "quality_gate"

    def test_deterministic_order(self) -> None:
        values = [kind.value for kind in HandoffPacketKind]
        assert values == [
            "observation",
            "review",
            "index",
            "search",
            "bundle",
            "chronicle",
            "digest",
            "quality_gate",
        ]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestConstants:
    def test_handoff_version(self) -> None:
        assert HANDOFF_VERSION == "1.0"

    def test_reason_codes(self) -> None:
        assert len(HANDOFF_REASON_CODES) == 32
        assert "EMPTY_PACKET" in HANDOFF_REASON_CODES
        assert "INVALID_CONFIG" in HANDOFF_REASON_CODES
        assert "UNSAFE_CONFIG" in HANDOFF_REASON_CODES
        assert "MISSING_OBSERVATION" in HANDOFF_REASON_CODES
        assert "BLOCKED_QUALITY_GATE" in HANDOFF_REASON_CODES
        assert "UNKNOWN_QUALITY_GATE" in HANDOFF_REASON_CODES
        assert "UNSAFE_ARTIFACT_FLAGS" in HANDOFF_REASON_CODES
        assert "UNRESOLVED_BLOCKERS" in HANDOFF_REASON_CODES
        assert "STALE_ARTIFACT" in HANDOFF_REASON_CODES
        assert "UNSAFE_PACKET_CONTENT" in HANDOFF_REASON_CODES
        assert "HANDOFF_ERROR" in HANDOFF_REASON_CODES

    def test_blocking_reason_codes(self) -> None:
        assert "EMPTY_PACKET" not in HANDOFF_BLOCKING_REASON_CODES
        assert "STALE_ARTIFACT" not in HANDOFF_BLOCKING_REASON_CODES
        assert "INVALID_CONFIG" in HANDOFF_BLOCKING_REASON_CODES
        assert "MISSING_OBSERVATION" in HANDOFF_BLOCKING_REASON_CODES
        assert "UNRESOLVED_BLOCKERS" in HANDOFF_BLOCKING_REASON_CODES

    def test_forbidden_terms_superset_of_quality_gate(self) -> None:
        from hunter.research_quality_gate.models import FORBIDDEN_QUALITY_GATE_TERMS

        for term in FORBIDDEN_QUALITY_GATE_TERMS:
            assert term in FORBIDDEN_HANDOFF_TERMS, term


# ---------------------------------------------------------------------------
# HandoffConfig
# ---------------------------------------------------------------------------


class TestHandoffConfig:
    def test_default_construction(self) -> None:
        config = HandoffConfig()
        assert config.version == "1.0"
        assert config.output_format == "both"
        assert config.dry_run is True
        assert config.live_trading_enabled is False
        assert config.block_on_unknown is True
        assert config.max_staleness_minutes == 60
        assert len(config.required_sections) == 8

    def test_invalid_version_empty(self) -> None:
        with pytest.raises(ValueError, match="version must be a non-empty string"):
            HandoffConfig(version="")

    def test_invalid_output_format(self) -> None:
        with pytest.raises(ValueError, match="output_format must be one of"):
            HandoffConfig(output_format="xml")

    def test_invalid_dry_run_false(self) -> None:
        with pytest.raises(ValueError, match="dry_run must be True"):
            HandoffConfig(dry_run=False)

    @pytest.mark.parametrize("attr", [
        "live_trading_enabled",
        "real_orders_enabled",
        "leverage_enabled",
        "shorting_enabled",
    ])
    def test_invalid_unsafe_flags_true(self, attr: str) -> None:
        with pytest.raises(ValueError, match=f"{attr} must be False"):
            HandoffConfig(**{attr: True})

    def test_invalid_block_on_unknown_non_bool(self) -> None:
        with pytest.raises(ValueError, match="block_on_unknown must be a bool"):
            HandoffConfig(block_on_unknown="yes")  # type: ignore[arg-type]

    def test_invalid_required_sections(self) -> None:
        with pytest.raises(
            ValueError, match="required_sections must contain HandoffPacketKind"
        ):
            HandoffConfig(required_sections=("observation",))  # type: ignore[arg-type]

    def test_invalid_staleness_zero(self) -> None:
        with pytest.raises(ValueError, match="max_staleness_minutes must be a positive integer"):
            HandoffConfig(max_staleness_minutes=0)

    def test_frozen(self) -> None:
        config = HandoffConfig()
        with pytest.raises(FrozenInstanceError):
            config.dry_run = False


# ---------------------------------------------------------------------------
# HandoffSafetyFlags
# ---------------------------------------------------------------------------


class TestHandoffSafetyFlags:
    def test_default_construction(self) -> None:
        flags = HandoffSafetyFlags()
        assert flags.dry_run is True
        assert flags.live_trading_enabled is False
        assert flags.handoff_output_is_human_audit_only is True
        assert flags.handoff_output_not_execution_readiness is True
        assert flags.handoff_output_not_strategy_readiness is True
        assert flags.handoff_feedback_into_execution is False
        assert flags.cross_layer_feedback_into_execution is False

    def test_unsafe_flag_true_raises(self) -> None:
        with pytest.raises(ValueError, match="unsafe handoff safety flags are enabled"):
            HandoffSafetyFlags(live_trading_enabled=True)
        with pytest.raises(ValueError, match="unsafe handoff safety flags are enabled"):
            HandoffSafetyFlags(handoff_feedback_into_execution=True)

    def test_dry_run_false_raises(self) -> None:
        with pytest.raises(ValueError, match="dry_run must be True"):
            HandoffSafetyFlags(dry_run=False)

    def test_safe_output_flag_false_raises(self) -> None:
        with pytest.raises(ValueError, match="safe handoff output flags must be True"):
            HandoffSafetyFlags(handoff_output_is_human_audit_only=False)

    def test_cross_layer_feedback_into_execution_true_raises(self) -> None:
        with pytest.raises(ValueError, match="unsafe handoff safety flags are enabled"):
            HandoffSafetyFlags(cross_layer_feedback_into_execution=True)

    def test_frozen(self) -> None:
        flags = HandoffSafetyFlags()
        with pytest.raises(FrozenInstanceError):
            flags.dry_run = False


# ---------------------------------------------------------------------------
# HandoffSection
# ---------------------------------------------------------------------------


class TestHandoffSection:
    def test_valid_construction(self) -> None:
        section = HandoffSection(
            section_kind=HandoffPacketKind.OBSERVATION,
            state="READY",
        )
        assert section.section_kind is HandoffPacketKind.OBSERVATION
        assert section.state == "READY"

    def test_state_normalized(self) -> None:
        section = HandoffSection(
            section_kind=HandoffPacketKind.REVIEW,
            state="block",
        )
        assert section.state == "BLOCK"

    def test_invalid_section_kind(self) -> None:
        with pytest.raises(ValueError, match="section_kind must be a HandoffPacketKind"):
            HandoffSection(section_kind="observation")  # type: ignore[arg-type]

    def test_invalid_state(self) -> None:
        with pytest.raises(ValueError, match="state must be one of"):
            HandoffSection(section_kind=HandoffPacketKind.INDEX, state="CORRUPTED")

    def test_unsafe_summary_text_raises(self) -> None:
        with pytest.raises(ValueError, match="UNSAFE_PACKET_CONTENT"):
            HandoffSection(
                section_kind=HandoffPacketKind.BUNDLE,
                summary_text="deploy now",
            )

    def test_unsafe_local_reference_raises(self) -> None:
        with pytest.raises(ValueError, match="UNSAFE_PACKET_CONTENT"):
            HandoffSection(
                section_kind=HandoffPacketKind.OBSERVATION,
                local_reference="path/to/secret",
            )

    def test_file_reference_not_traversed(self) -> None:
        section = HandoffSection(
            section_kind=HandoffPacketKind.OBSERVATION,
            local_reference="data/observation/latest_observation_report.json",
        )
        assert section.local_reference == "data/observation/latest_observation_report.json"


# ---------------------------------------------------------------------------
# HandoffSummary
# ---------------------------------------------------------------------------


class TestHandoffSummary:
    def test_default_construction(self) -> None:
        summary = HandoffSummary()
        assert summary.total_sections == 0
        assert summary.handoff_state == "UNKNOWN"

    def test_valid_construction(self) -> None:
        summary = HandoffSummary(
            total_sections=4,
            ready_sections=2,
            warn_sections=1,
            block_sections=1,
            unknown_sections=0,
            handoff_state="WARN",
            quality_gate_verdict="PASS",
        )
        assert (
            summary.ready_sections
            + summary.warn_sections
            + summary.block_sections
            + summary.unknown_sections
            == summary.total_sections
        )
        assert summary.quality_gate_verdict == "PASS"

    def test_count_mismatch_raises(self) -> None:
        with pytest.raises(ValueError, match=r"ready_sections \+ warn_sections \+ block_sections"):
            HandoffSummary(
                total_sections=4,
                ready_sections=2,
                warn_sections=0,
                block_sections=0,
                unknown_sections=0,
            )

    def test_invalid_handoff_state(self) -> None:
        with pytest.raises(ValueError, match="handoff_state must be one of"):
            HandoffSummary(handoff_state="CORRUPTED")

    def test_invalid_quality_gate_verdict(self) -> None:
        with pytest.raises(ValueError, match="quality_gate_verdict must be one of"):
            HandoffSummary(quality_gate_verdict="CORRUPTED")

    def test_unsafe_handoff_notes_raises(self) -> None:
        with pytest.raises(ValueError, match="UNSAFE_PACKET_CONTENT"):
            HandoffSummary(handoff_notes="go_live now")


# ---------------------------------------------------------------------------
# HandoffDataQuality
# ---------------------------------------------------------------------------


class TestHandoffDataQuality:
    def test_default_construction(self) -> None:
        dq = HandoffDataQuality()
        assert dq.completeness_pct == 0.0
        assert dq.total_sections == 0

    def test_completeness_pct_range(self) -> None:
        with pytest.raises(ValueError, match="completeness_pct must be between"):
            HandoffDataQuality(completeness_pct=101.0)

    def test_ready_pct_range(self) -> None:
        with pytest.raises(ValueError, match="ready_pct must be between"):
            HandoffDataQuality(ready_pct=-1.0)

    def test_unsafe_reason_raises(self) -> None:
        with pytest.raises(ValueError, match="UNSAFE_PACKET_CONTENT"):
            HandoffDataQuality(reason="contains secret")


# ---------------------------------------------------------------------------
# ResearchHandoffPacket
# ---------------------------------------------------------------------------


class TestResearchHandoffPacket:
    def test_valid_construction(self) -> None:
        now = datetime.now(timezone.utc)
        packet = ResearchHandoffPacket(
            packet_id="handoff:1.0:2025-01-01T00:00:00",
            generated_at=now,
            handoff_state=HandoffState.READY,
        )
        assert packet.packet_id == "handoff:1.0:2025-01-01T00:00:00"
        assert packet.generated_at == now
        assert packet.handoff_state is HandoffState.READY

    def test_default_handoff_state(self) -> None:
        now = datetime.now(timezone.utc)
        packet = ResearchHandoffPacket(packet_id="p1", generated_at=now)
        assert packet.handoff_state is HandoffState.UNKNOWN

    def test_invalid_packet_id_empty(self) -> None:
        with pytest.raises(ValueError, match="packet_id must be a non-empty string"):
            ResearchHandoffPacket(packet_id="", generated_at=datetime.now(timezone.utc))

    def test_invalid_generated_at_naive(self) -> None:
        with pytest.raises(ValueError, match="generated_at must be a timezone-aware datetime"):
            ResearchHandoffPacket(packet_id="p1", generated_at=datetime.now())

    def test_invalid_handoff_state_type(self) -> None:
        with pytest.raises(ValueError, match="handoff_state must be a HandoffState"):
            ResearchHandoffPacket(
                packet_id="p1",
                generated_at=datetime.now(timezone.utc),
                handoff_state="READY",  # type: ignore[arg-type]
            )

    def test_blocked_factory(self) -> None:
        now = datetime.now(timezone.utc)
        packet = ResearchHandoffPacket.blocked("INVALID_CONFIG", generated_at=now)
        assert packet.handoff_state is HandoffState.BLOCK
        assert packet.reason_codes == ("INVALID_CONFIG",)
        assert "Handoff packet blocked: INVALID_CONFIG" in packet.summary.handoff_notes
        assert "not trade approval" in packet.summary.handoff_notes
        assert packet.data_quality.blocked_count == 1

    def test_frozen(self) -> None:
        now = datetime.now(timezone.utc)
        packet = ResearchHandoffPacket(packet_id="p1", generated_at=now)
        with pytest.raises(FrozenInstanceError):
            packet.packet_id = "p2"

    def test_unsafe_handoff_notes_raises(self) -> None:
        with pytest.raises(ValueError, match="UNSAFE_PACKET_CONTENT"):
            ResearchHandoffPacket(
                packet_id="p1",
                generated_at=datetime.now(timezone.utc),
                handoff_notes="place order",
            )
