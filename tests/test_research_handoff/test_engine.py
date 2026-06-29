"""Tests for hunter.research_handoff.engine."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from hunter.research_handoff.engine import (
    build_handoff_data_quality,
    build_handoff_safety_flags,
    build_handoff_section,
    build_handoff_summary,
    build_research_handoff_packet,
    has_unsafe_handoff_content,
)
from hunter.research_handoff.models import (
    FORBIDDEN_HANDOFF_TERMS,
    HandoffConfig,
    HandoffPacketKind,
    HandoffSafetyFlags,
    HandoffState,
    ResearchHandoffPacket,
)


def _now() -> datetime:
    return datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _make_safety_flags(
    *,
    dry_run: bool = True,
    live_trading_enabled: bool = False,
    handoff_feedback_into_execution: bool = False,
) -> HandoffSafetyFlags:
    return HandoffSafetyFlags(
        dry_run=dry_run,
        live_trading_enabled=live_trading_enabled,
        real_orders_enabled=False,
        leverage_enabled=False,
        shorting_enabled=False,
        handoff_feedback_into_execution=handoff_feedback_into_execution,
        cross_layer_feedback_into_execution=False,
    )


def _make_unsafe_safety_flags(unsafe_attr: str = "live_trading_enabled") -> HandoffSafetyFlags:
    """Return a safety flags object with one unsafe flag enabled.

    Bypasses __post_init__ so tests can verify engine detection.
    """
    flags = object.__new__(HandoffSafetyFlags)
    object.__setattr__(flags, "dry_run", True)
    object.__setattr__(flags, "live_trading_enabled", False)
    object.__setattr__(flags, "real_orders_enabled", False)
    object.__setattr__(flags, "leverage_enabled", False)
    object.__setattr__(flags, "shorting_enabled", False)
    object.__setattr__(flags, "handoff_output_is_human_audit_only", True)
    object.__setattr__(flags, "handoff_output_not_trading_signal", True)
    object.__setattr__(flags, "handoff_output_not_trade_approval", True)
    object.__setattr__(flags, "handoff_output_not_execution_readiness", True)
    object.__setattr__(flags, "handoff_output_not_strategy_readiness", True)
    object.__setattr__(flags, "handoff_output_not_for_execution", True)
    object.__setattr__(flags, "handoff_output_not_for_strategy", True)
    object.__setattr__(flags, "handoff_output_not_for_freqtrade", True)
    object.__setattr__(flags, "handoff_output_not_for_order", True)
    object.__setattr__(flags, "handoff_output_not_for_exchange", True)
    object.__setattr__(flags, "handoff_feedback_into_execution", False)
    object.__setattr__(flags, "cross_layer_feedback_into_execution", False)
    object.__setattr__(flags, "file_refs_not_traversed", True)
    object.__setattr__(flags, unsafe_attr, True)
    return flags


def _make_artifact(
    state: str = "READY",
    reason_codes: tuple[str, ...] = (),
    generated_at: datetime | None = None,
    safety_flags: HandoffSafetyFlags | None = None,
    summary_text: str | None = None,
) -> object:
    """Return a simple artifact-like object."""
    if generated_at is None:
        # Default to far future to avoid accidental staleness in tests.
        generated_at = datetime(2099, 1, 1, tzinfo=timezone.utc)
    if safety_flags is None:
        safety_flags = _make_safety_flags()

    class Artifact:
        pass

    artifact = Artifact()
    artifact.state = state
    artifact.reason_codes = reason_codes
    artifact.generated_at = generated_at
    artifact.safety_flags = safety_flags
    if summary_text is not None:
        artifact.summary_text = summary_text
    return artifact


def _make_artifact_dict(
    state: str = "READY",
    reason_codes: tuple[str, ...] = (),
    generated_at: datetime | None = None,
    safety_flags: HandoffSafetyFlags | None = None,
    index_state: str | None = None,
    search_state: str | None = None,
) -> dict[str, object]:
    """Return a dict-based artifact."""
    if generated_at is None:
        # Default to far future to avoid accidental staleness in tests.
        generated_at = datetime(2099, 1, 1, tzinfo=timezone.utc)
    if safety_flags is None:
        safety_flags = _make_safety_flags()
    data: dict[str, object] = {
        "state": state,
        "reason_codes": reason_codes,
        "generated_at": generated_at,
        "safety_flags": safety_flags,
    }
    if index_state is not None:
        data["index_state"] = index_state
    if search_state is not None:
        data["search_state"] = search_state
    return data


# ---------------------------------------------------------------------------
# has_unsafe_handoff_content
# ---------------------------------------------------------------------------


class TestHasUnsafeHandoffContent:
    def test_safe_text(self) -> None:
        assert has_unsafe_handoff_content("normal audit notes") is False

    def test_forbidden_term_api_key(self) -> None:
        assert has_unsafe_handoff_content("contains api_key") is True

    def test_forbidden_term_deploy(self) -> None:
        assert has_unsafe_handoff_content("deploy now") is True

    def test_case_insensitive(self) -> None:
        assert has_unsafe_handoff_content("DEPLOY") is True
        assert has_unsafe_handoff_content("API_KEY") is True

    def test_empty_text(self) -> None:
        assert has_unsafe_handoff_content("") is False
        assert has_unsafe_handoff_content(None) is False

    def test_unsafe_metadata(self) -> None:
        assert has_unsafe_handoff_content(None, {"token": "abc"}) is True

    def test_safe_metadata(self) -> None:
        assert has_unsafe_handoff_content(None, {"path": "/tmp/report.json"}) is False


# ---------------------------------------------------------------------------
# build_handoff_safety_flags
# ---------------------------------------------------------------------------


class TestBuildHandoffSafetyFlags:
    def test_default_config(self) -> None:
        flags = build_handoff_safety_flags(HandoffConfig())
        assert flags.dry_run is True
        assert flags.live_trading_enabled is False
        assert flags.handoff_feedback_into_execution is False

    def test_unsafe_config_rejected(self) -> None:
        with pytest.raises(ValueError, match="dry_run must be True"):
            HandoffConfig(dry_run=False)

    def test_unsafe_config_passed_directly_raises(self) -> None:
        config = object.__new__(HandoffConfig)
        object.__setattr__(config, "version", "1.0")
        object.__setattr__(config, "generated_at", None)
        object.__setattr__(config, "output_format", "both")
        object.__setattr__(config, "dry_run", False)
        object.__setattr__(config, "live_trading_enabled", False)
        object.__setattr__(config, "real_orders_enabled", False)
        object.__setattr__(config, "leverage_enabled", False)
        object.__setattr__(config, "shorting_enabled", False)
        object.__setattr__(config, "block_on_unknown", True)
        object.__setattr__(config, "required_sections", ())
        object.__setattr__(config, "max_staleness_minutes", 60)
        object.__setattr__(config, "include_handoff_notes", True)
        with pytest.raises(ValueError, match="dry_run must be True"):
            build_handoff_safety_flags(config)


# ---------------------------------------------------------------------------
# build_handoff_section
# ---------------------------------------------------------------------------


class TestBuildHandoffSection:
    def test_ready_artifact_ready(self) -> None:
        artifact = _make_artifact(state="READY")
        section = build_handoff_section(
            HandoffPacketKind.OBSERVATION,
            artifact=artifact,
        )
        assert section.state == "READY"
        assert section.section_kind is HandoffPacketKind.OBSERVATION
        assert "data/observation/latest_observation_report.json" in section.local_reference

    def test_ready_artifact_dict_ready(self) -> None:
        artifact = _make_artifact_dict(state="READY")
        section = build_handoff_section(
            HandoffPacketKind.OBSERVATION,
            artifact=artifact,
        )
        assert section.state == "READY"

    def test_blocked_artifact_block(self) -> None:
        artifact = _make_artifact(state="BLOCKED")
        section = build_handoff_section(
            HandoffPacketKind.REVIEW,
            artifact=artifact,
        )
        assert section.state == "BLOCK"
        assert "BLOCKED_REVIEW" in section.reason_codes

    def test_unknown_artifact_block_by_default(self) -> None:
        artifact = _make_artifact(state="UNKNOWN")
        section = build_handoff_section(
            HandoffPacketKind.INDEX,
            artifact=artifact,
        )
        assert section.state == "BLOCK"
        assert "UNKNOWN_INDEX" in section.reason_codes

    def test_unknown_artifact_warn_when_not_blocking(self) -> None:
        artifact = _make_artifact(state="UNKNOWN")
        config = HandoffConfig(block_on_unknown=False)
        section = build_handoff_section(
            HandoffPacketKind.INDEX,
            artifact=artifact,
            config=config,
        )
        assert section.state == "WARN"
        assert "UNKNOWN_INDEX" in section.reason_codes

    def test_disabled_artifact_treated_as_unknown(self) -> None:
        artifact = _make_artifact(state="DISABLED")
        section = build_handoff_section(
            HandoffPacketKind.SEARCH,
            artifact=artifact,
        )
        assert section.state == "BLOCK"
        assert "UNKNOWN_SEARCH" in section.reason_codes

    def test_missing_required_section_block(self) -> None:
        section = build_handoff_section(
            HandoffPacketKind.BUNDLE,
            artifact=None,
        )
        assert section.state == "BLOCK"
        assert "MISSING_BUNDLE" in section.reason_codes

    def test_missing_optional_section_ready(self) -> None:
        config = HandoffConfig(required_sections=())
        section = build_handoff_section(
            HandoffPacketKind.BUNDLE,
            artifact=None,
            config=config,
        )
        assert section.state == "READY"

    def test_unsafe_safety_flags_block(self) -> None:
        flags = _make_unsafe_safety_flags("live_trading_enabled")
        artifact = _make_artifact(state="READY", safety_flags=flags)
        section = build_handoff_section(
            HandoffPacketKind.CHRONICLE,
            artifact=artifact,
        )
        assert section.state == "BLOCK"
        assert "UNSAFE_ARTIFACT_FLAGS" in section.reason_codes

    def test_unresolved_blockers_block(self) -> None:
        artifact = _make_artifact(state="READY", reason_codes=("MISSING_REVIEW",))
        section = build_handoff_section(
            HandoffPacketKind.DIGEST,
            artifact=artifact,
        )
        assert section.state == "BLOCK"
        assert "UNRESOLVED_BLOCKERS" in section.reason_codes

    def test_stale_artifact_warn(self) -> None:
        stale = _now() - timedelta(hours=2)
        artifact = _make_artifact(state="READY", generated_at=stale)
        section = build_handoff_section(
            HandoffPacketKind.OBSERVATION,
            artifact=artifact,
            reference_time=_now(),
        )
        assert section.state == "WARN"
        assert "STALE_ARTIFACT" in section.reason_codes

    def test_index_artifact_state_attribute(self) -> None:
        artifact = _make_artifact_dict(state="READY", index_state="BLOCKED")
        section = build_handoff_section(
            HandoffPacketKind.INDEX,
            artifact=artifact,
        )
        assert section.state == "BLOCK"
        assert "BLOCKED_INDEX" in section.reason_codes

    def test_search_artifact_state_attribute(self) -> None:
        artifact = _make_artifact_dict(state="READY", search_state="READY")
        section = build_handoff_section(
            HandoffPacketKind.SEARCH,
            artifact=artifact,
        )
        assert section.state == "READY"


# ---------------------------------------------------------------------------
# build_handoff_summary
# ---------------------------------------------------------------------------


class TestBuildHandoffSummary:
    def test_empty_sections(self) -> None:
        summary = build_handoff_summary([])
        assert summary.total_sections == 0
        assert summary.handoff_state == "UNKNOWN"

    def test_all_ready(self) -> None:
        sections = [
            build_handoff_section(HandoffPacketKind.OBSERVATION, _make_artifact("READY")),
            build_handoff_section(HandoffPacketKind.REVIEW, _make_artifact("READY")),
        ]
        summary = build_handoff_summary(sections)
        assert summary.total_sections == 2
        assert summary.ready_sections == 2
        assert summary.handoff_state == "READY"
        assert "human audit" in summary.handoff_notes
        assert "not trade approval" in summary.handoff_notes

    def test_warn(self) -> None:
        config = HandoffConfig(block_on_unknown=False)
        sections = [
            build_handoff_section(HandoffPacketKind.OBSERVATION, _make_artifact("READY")),
            build_handoff_section(
                HandoffPacketKind.REVIEW,
                _make_artifact("UNKNOWN"),
                config=config,
            ),
        ]
        summary = build_handoff_summary(sections)
        assert summary.handoff_state == "WARN"
        assert "not execution readiness" in summary.handoff_notes

    def test_block(self) -> None:
        sections = [
            build_handoff_section(HandoffPacketKind.OBSERVATION, _make_artifact("READY")),
            build_handoff_section(HandoffPacketKind.REVIEW, _make_artifact("BLOCKED")),
        ]
        summary = build_handoff_summary(sections)
        assert summary.handoff_state == "BLOCK"
        assert "not strategy readiness" in summary.handoff_notes

    def test_quality_gate_verdict_extraction(self) -> None:
        quality_gate = {"verdict": "PASS"}
        sections = [
            build_handoff_section(HandoffPacketKind.QUALITY_GATE, quality_gate),
        ]
        summary = build_handoff_summary(sections, quality_gate_artifact=quality_gate)
        assert summary.quality_gate_verdict == "PASS"

    def test_quality_gate_verdict_default_unknown(self) -> None:
        sections = [
            build_handoff_section(HandoffPacketKind.OBSERVATION, _make_artifact("READY")),
        ]
        summary = build_handoff_summary(sections)
        assert summary.quality_gate_verdict == "UNKNOWN"


# ---------------------------------------------------------------------------
# build_handoff_data_quality
# ---------------------------------------------------------------------------


class TestBuildHandoffDataQuality:
    def test_empty_sections(self) -> None:
        dq = build_handoff_data_quality([])
        assert dq.completeness_pct == 0.0
        assert dq.total_sections == 0

    def test_completeness(self) -> None:
        sections = [
            build_handoff_section(HandoffPacketKind.OBSERVATION, _make_artifact("READY")),
            build_handoff_section(HandoffPacketKind.REVIEW, _make_artifact("BLOCKED")),
        ]
        dq = build_handoff_data_quality(sections)
        assert dq.completeness_pct == 50.0
        assert dq.ready_pct == 50.0
        assert dq.total_sections == 2


# ---------------------------------------------------------------------------
# build_research_handoff_packet
# ---------------------------------------------------------------------------


class TestBuildResearchHandoffPacket:
    def test_all_ready_ready(self) -> None:
        packet = build_research_handoff_packet(
            config=HandoffConfig(generated_at=_now()),
            observation_artifact=_make_artifact("READY"),
            review_artifact=_make_artifact("READY"),
            index_artifact=_make_artifact_dict(state="READY"),
            search_artifact=_make_artifact_dict(state="READY"),
            bundle_artifact=_make_artifact("READY"),
            chronicle_artifact=_make_artifact("READY"),
            digest_artifact=_make_artifact("READY"),
            quality_gate_artifact=_make_artifact("READY"),
        )
        assert packet.handoff_state is HandoffState.READY
        assert packet.summary.handoff_state == "READY"
        assert packet.summary.ready_sections == 8
        assert "human audit" in packet.handoff_notes
        assert "not trade approval" in packet.handoff_notes
        assert packet.safety_flags.handoff_output_not_execution_readiness is True
        assert packet.safety_flags.handoff_feedback_into_execution is False

    def test_missing_observation_blocked(self) -> None:
        packet = build_research_handoff_packet(
            config=HandoffConfig(generated_at=_now()),
            review_artifact=_make_artifact("READY"),
            index_artifact=_make_artifact_dict(state="READY"),
            search_artifact=_make_artifact_dict(state="READY"),
            bundle_artifact=_make_artifact("READY"),
            chronicle_artifact=_make_artifact("READY"),
            digest_artifact=_make_artifact("READY"),
            quality_gate_artifact=_make_artifact("READY"),
        )
        assert packet.handoff_state is HandoffState.BLOCK
        assert "MISSING_OBSERVATION" in packet.reason_codes

    def test_blocked_digest_blocked(self) -> None:
        packet = build_research_handoff_packet(
            config=HandoffConfig(generated_at=_now()),
            observation_artifact=_make_artifact("READY"),
            review_artifact=_make_artifact("READY"),
            index_artifact=_make_artifact_dict(state="READY"),
            search_artifact=_make_artifact_dict(state="READY"),
            bundle_artifact=_make_artifact("READY"),
            chronicle_artifact=_make_artifact("READY"),
            digest_artifact=_make_artifact("BLOCKED"),
            quality_gate_artifact=_make_artifact("READY"),
        )
        assert packet.handoff_state is HandoffState.BLOCK
        assert "BLOCKED_DIGEST" in packet.reason_codes

    def test_unsafe_config_blocked(self) -> None:
        config = object.__new__(HandoffConfig)
        object.__setattr__(config, "version", "1.0")
        object.__setattr__(config, "generated_at", _now())
        object.__setattr__(config, "output_format", "both")
        object.__setattr__(config, "dry_run", False)
        object.__setattr__(config, "live_trading_enabled", False)
        object.__setattr__(config, "real_orders_enabled", False)
        object.__setattr__(config, "leverage_enabled", False)
        object.__setattr__(config, "shorting_enabled", False)
        object.__setattr__(config, "block_on_unknown", True)
        object.__setattr__(config, "required_sections", ())
        object.__setattr__(config, "max_staleness_minutes", 60)
        object.__setattr__(config, "include_handoff_notes", True)

        packet = build_research_handoff_packet(
            config=config,
            observation_artifact=_make_artifact("READY"),
        )
        assert packet.handoff_state is HandoffState.BLOCK
        assert "UNSAFE_CONFIG" in packet.reason_codes

    def test_empty_packet_blocked(self) -> None:
        packet = build_research_handoff_packet(
            config=HandoffConfig(
                generated_at=_now(),
                required_sections=(),
            ),
        )
        assert packet.handoff_state is HandoffState.BLOCK
        assert "EMPTY_PACKET" in packet.reason_codes

    def test_deterministic_section_ordering(self) -> None:
        packet = build_research_handoff_packet(
            config=HandoffConfig(generated_at=_now()),
            observation_artifact=_make_artifact("READY"),
            review_artifact=_make_artifact("READY"),
            index_artifact=_make_artifact_dict(state="READY"),
            search_artifact=_make_artifact_dict(state="READY"),
            bundle_artifact=_make_artifact("READY"),
            chronicle_artifact=_make_artifact("READY"),
            digest_artifact=_make_artifact("READY"),
            quality_gate_artifact=_make_artifact("READY"),
        )
        kinds = [s.section_kind for s in packet.sections]
        expected = [
            HandoffPacketKind.OBSERVATION,
            HandoffPacketKind.REVIEW,
            HandoffPacketKind.INDEX,
            HandoffPacketKind.SEARCH,
            HandoffPacketKind.BUNDLE,
            HandoffPacketKind.CHRONICLE,
            HandoffPacketKind.DIGEST,
            HandoffPacketKind.QUALITY_GATE,
        ]
        assert kinds == expected

    def test_deterministic_packet_id(self) -> None:
        generated_at = _now()
        packet = build_research_handoff_packet(
            config=HandoffConfig(generated_at=generated_at),
            observation_artifact=_make_artifact("READY"),
        )
        expected = f"handoff:1.0:{generated_at.strftime('%Y-%m-%dT%H:%M:%S.%f')}"
        assert packet.packet_id == expected

    def test_quality_gate_verdict_in_summary(self) -> None:
        quality_gate = {"state": "READY", "verdict": "WARN", "reason_codes": ()}
        packet = build_research_handoff_packet(
            config=HandoffConfig(generated_at=_now()),
            observation_artifact=_make_artifact("READY"),
            review_artifact=_make_artifact("READY"),
            index_artifact=_make_artifact_dict(state="READY"),
            search_artifact=_make_artifact_dict(state="READY"),
            bundle_artifact=_make_artifact("READY"),
            chronicle_artifact=_make_artifact("READY"),
            digest_artifact=_make_artifact("READY"),
            quality_gate_artifact=quality_gate,
        )
        assert packet.summary.quality_gate_verdict == "WARN"

    def test_ready_not_execution_or_strategy_approval(self) -> None:
        packet = build_research_handoff_packet(
            config=HandoffConfig(generated_at=_now()),
            observation_artifact=_make_artifact("READY"),
            review_artifact=_make_artifact("READY"),
            index_artifact=_make_artifact_dict(state="READY"),
            search_artifact=_make_artifact_dict(state="READY"),
            bundle_artifact=_make_artifact("READY"),
            chronicle_artifact=_make_artifact("READY"),
            digest_artifact=_make_artifact("READY"),
            quality_gate_artifact=_make_artifact("READY"),
        )
        assert packet.handoff_state is HandoffState.READY
        assert packet.safety_flags.handoff_output_not_trade_approval is True
        assert packet.safety_flags.handoff_output_not_execution_readiness is True
        assert packet.safety_flags.handoff_output_not_strategy_readiness is True
        assert "not execution readiness" in packet.handoff_notes
        assert "not strategy readiness" in packet.handoff_notes
        assert "not release approval" in packet.handoff_notes


# ---------------------------------------------------------------------------
# Safety invariants
# ---------------------------------------------------------------------------


class TestSafetyInvariants:
    def test_no_execution_feedback(self) -> None:
        packet = build_research_handoff_packet(
            config=HandoffConfig(generated_at=_now()),
            observation_artifact=_make_artifact("READY"),
            review_artifact=_make_artifact("READY"),
            index_artifact=_make_artifact_dict(state="READY"),
            search_artifact=_make_artifact_dict(state="READY"),
            bundle_artifact=_make_artifact("READY"),
            chronicle_artifact=_make_artifact("READY"),
            digest_artifact=_make_artifact("READY"),
            quality_gate_artifact=_make_artifact("READY"),
        )
        assert packet.safety_flags.handoff_feedback_into_execution is False
        assert packet.safety_flags.cross_layer_feedback_into_execution is False

    def test_no_forbidden_terms_in_handoff_notes(self) -> None:
        packet = build_research_handoff_packet(
            config=HandoffConfig(generated_at=_now()),
            observation_artifact=_make_artifact("READY"),
            review_artifact=_make_artifact("READY"),
            index_artifact=_make_artifact_dict(state="READY"),
            search_artifact=_make_artifact_dict(state="READY"),
            bundle_artifact=_make_artifact("READY"),
            chronicle_artifact=_make_artifact("READY"),
            digest_artifact=_make_artifact("READY"),
            quality_gate_artifact=_make_artifact("READY"),
        )
        notes = packet.handoff_notes.lower()
        for term in FORBIDDEN_HANDOFF_TERMS:
            assert term not in notes, term

    def test_file_references_are_strings_only(self) -> None:
        packet = build_research_handoff_packet(
            config=HandoffConfig(generated_at=_now()),
            observation_artifact=_make_artifact("READY"),
        )
        # No exception means file references were never opened or executed.
        assert packet.packet_id.startswith("handoff:1.0:")
        observation_section = next(
            s for s in packet.sections if s.section_kind is HandoffPacketKind.OBSERVATION
        )
        assert "data/observation/" in observation_section.local_reference
