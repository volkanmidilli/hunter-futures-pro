"""Tests for hunter.research_handoff.writer."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hunter.research_handoff.engine import build_research_handoff_packet
from hunter.research_handoff.models import (
    HandoffConfig,
    HandoffDataQuality,
    HandoffPacketKind,
    HandoffSafetyFlags,
    HandoffSection,
    HandoffState,
    HandoffSummary,
    ResearchHandoffPacket,
)
from hunter.research_handoff.writer import (
    DEFAULT_HANDOFF_JSON_PATH,
    DEFAULT_HANDOFF_MARKDOWN_PATH,
    atomic_write_json_research_handoff_packet,
    atomic_write_markdown_research_handoff_packet,
    handoff_config_to_dict,
    handoff_data_quality_to_dict,
    handoff_safety_flags_to_dict,
    handoff_section_to_dict,
    handoff_summary_to_dict,
    research_handoff_packet_to_dict,
    research_handoff_packet_to_markdown,
    write_research_handoff_packet,
)


def _now() -> datetime:
    return datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _make_artifact(state: str = "READY", verdict: str | None = None) -> dict[str, object]:
    artifact: dict[str, object] = {
        "state": state,
        "reason_codes": (),
        "generated_at": _now(),
        "safety_flags": HandoffSafetyFlags(),
    }
    if verdict is not None:
        artifact["verdict"] = verdict
    return artifact


def _make_packet(
    handoff_state: HandoffState = HandoffState.READY,
    sections: tuple[HandoffSection, ...] = (),
    reason_codes: tuple[str, ...] = (),
    handoff_notes: str = "",
) -> ResearchHandoffPacket:
    if not handoff_notes:
        if handoff_state is HandoffState.READY:
            handoff_notes = (
                "All required artifact categories are present and ready. Handoff packet "
                "is complete for human audit and contractor handoff. This is not trade "
                "approval, not execution readiness, not strategy readiness, not "
                "release approval, and not transaction permission."
            )
        elif handoff_state is HandoffState.BLOCK:
            handoff_notes = (
                "Handoff packet is not ready for human handoff. Resolve blockers before "
                "handoff. This is not trade approval, not execution readiness, not "
                "strategy readiness, not release approval, and not transaction permission."
            )
        else:
            handoff_notes = "Insufficient information."

    summary = HandoffSummary(
        total_sections=len(sections),
        ready_sections=sum(1 for s in sections if s.state == "READY"),
        warn_sections=sum(1 for s in sections if s.state == "WARN"),
        block_sections=sum(1 for s in sections if s.state == "BLOCK"),
        unknown_sections=sum(1 for s in sections if s.state == "UNKNOWN"),
        handoff_state=handoff_state.value,
        handoff_notes=handoff_notes,
    )
    data_quality = HandoffDataQuality(
        completeness_pct=100.0 if handoff_state is HandoffState.READY else 0.0,
        ready_pct=100.0 if handoff_state is HandoffState.READY else 0.0,
        total_sections=len(sections),
    )
    return ResearchHandoffPacket(
        packet_id="handoff:1.0:2025-01-01T12:00:00",
        generated_at=_now(),
        version="1.0",
        handoff_state=handoff_state,
        sections=sections,
        summary=summary,
        data_quality=data_quality,
        safety_flags=HandoffSafetyFlags(),
        config=HandoffConfig(generated_at=_now()),
        reason_codes=reason_codes,
        handoff_notes=handoff_notes,
    )


# ---------------------------------------------------------------------------
# Dict serialization
# ---------------------------------------------------------------------------


class TestHandoffSafetyFlagsToDict:
    def test_all_fields_present(self) -> None:
        flags = HandoffSafetyFlags()
        data = handoff_safety_flags_to_dict(flags)
        assert data["dry_run"] is True
        assert data["live_trading_enabled"] is False
        assert data["handoff_output_is_human_audit_only"] is True
        assert data["handoff_output_not_trade_approval"] is True
        assert data["handoff_output_not_execution_readiness"] is True
        assert data["handoff_output_not_strategy_readiness"] is True
        assert data["handoff_feedback_into_execution"] is False
        assert data["cross_layer_feedback_into_execution"] is False
        assert data["file_refs_not_traversed"] is True


class TestHandoffConfigToDict:
    def test_fields(self) -> None:
        config = HandoffConfig(generated_at=_now())
        data = handoff_config_to_dict(config)
        assert data["version"] == "1.0"
        assert data["generated_at"] == "2025-01-01T12:00:00+00:00"
        assert data["output_format"] == "both"
        assert data["dry_run"] is True
        assert data["block_on_unknown"] is True
        assert data["max_staleness_minutes"] == 60
        assert data["required_sections"] == [
            "observation",
            "review",
            "index",
            "search",
            "bundle",
            "chronicle",
            "digest",
            "quality_gate",
        ]


class TestHandoffSectionToDict:
    def test_ready_section(self) -> None:
        section = HandoffSection(
            section_kind=HandoffPacketKind.OBSERVATION,
            state="READY",
            summary_text="observation ready",
            local_reference="data/observation/latest_observation_report.json",
            metadata={"artifact_type": "observation"},
        )
        data = handoff_section_to_dict(section)
        assert data["section_kind"] == "observation"
        assert data["state"] == "READY"
        assert data["summary_text"] == "observation ready"
        assert data["local_reference"] == "data/observation/latest_observation_report.json"
        assert data["reason_codes"] == []
        assert data["metadata"] == {"artifact_type": "observation"}


class TestHandoffSummaryToDict:
    def test_summary(self) -> None:
        summary = HandoffSummary(
            total_sections=2,
            ready_sections=1,
            warn_sections=1,
            handoff_state="WARN",
            handoff_notes="Review warnings.",
        )
        data = handoff_summary_to_dict(summary)
        assert data["total_sections"] == 2
        assert data["ready_sections"] == 1
        assert data["warn_sections"] == 1
        assert data["handoff_state"] == "WARN"
        assert data["handoff_notes"] == "Review warnings."


class TestHandoffDataQualityToDict:
    def test_data_quality(self) -> None:
        dq = HandoffDataQuality(
            completeness_pct=75.0,
            ready_pct=50.0,
            missing_count=1,
            total_sections=4,
            reason="partial",
        )
        data = handoff_data_quality_to_dict(dq)
        assert data["completeness_pct"] == 75.0
        assert data["ready_pct"] == 50.0
        assert data["missing_count"] == 1
        assert data["total_sections"] == 4
        assert data["reason"] == "partial"


class TestResearchHandoffPacketToDict:
    def test_ready_packet(self) -> None:
        packet = _make_packet(HandoffState.READY)
        data = research_handoff_packet_to_dict(packet)
        assert data["packet_id"] == "handoff:1.0:2025-01-01T12:00:00"
        assert data["handoff_state"] == "ready"
        assert data["version"] == "1.0"
        assert "generated_at" in data
        assert "sections" in data
        assert "summary" in data
        assert "data_quality" in data
        assert "safety_flags" in data
        assert "config" in data
        assert "reason_codes" in data
        assert "handoff_notes" in data
        assert data["safety_flags"]["handoff_output_not_execution_readiness"] is True
        assert data["safety_flags"]["handoff_output_not_strategy_readiness"] is True

    def test_blocked_packet(self) -> None:
        section = HandoffSection(
            section_kind=HandoffPacketKind.OBSERVATION,
            state="BLOCK",
            reason_codes=("BLOCKED_OBSERVATION",),
        )
        packet = _make_packet(
            HandoffState.BLOCK,
            sections=(section,),
            reason_codes=("BLOCKED_OBSERVATION",),
        )
        data = research_handoff_packet_to_dict(packet)
        assert data["handoff_state"] == "block"
        assert data["sections"][0]["section_kind"] == "observation"
        assert data["sections"][0]["state"] == "BLOCK"
        assert data["sections"][0]["reason_codes"] == ["BLOCKED_OBSERVATION"]

    def test_metadata_not_traversed(self) -> None:
        section = HandoffSection(
            section_kind=HandoffPacketKind.DIGEST,
            state="READY",
            metadata={
                "report_path": "reports/2025/btc.md",
                "nested": {"file_ref": "data/observation/x.json"},
            },
        )
        packet = _make_packet(HandoffState.READY, sections=(section,))
        data = research_handoff_packet_to_dict(packet)
        assert data["sections"][0]["metadata"]["report_path"] == "reports/2025/btc.md"
        assert data["sections"][0]["metadata"]["nested"]["file_ref"] == "data/observation/x.json"

    def test_json_safe_determinism(self) -> None:
        packet1 = _make_packet(HandoffState.READY)
        packet2 = _make_packet(HandoffState.READY)
        text1 = json.dumps(research_handoff_packet_to_dict(packet1), sort_keys=True)
        text2 = json.dumps(research_handoff_packet_to_dict(packet2), sort_keys=True)
        assert text1 == text2


# ---------------------------------------------------------------------------
# Markdown serialization
# ---------------------------------------------------------------------------


class TestResearchHandoffPacketToMarkdown:
    def test_contains_safety_notice(self) -> None:
        packet = _make_packet(HandoffState.READY)
        md = research_handoff_packet_to_markdown(packet)
        assert "human-audit / contractor-handoff artifact only" in md
        assert "not a trading signal" in md
        assert "not trade approval" in md
        assert "not execution approval" in md
        assert "not strategy approval" in md
        assert "not release approval" in md
        assert "not transaction permission" in md

    def test_contains_packet_info(self) -> None:
        packet = _make_packet(HandoffState.READY)
        md = research_handoff_packet_to_markdown(packet)
        assert "handoff:1.0:2025-01-01T12:00:00" in md
        assert "2025-01-01T12:00:00+00:00" in md
        assert "ready" in md.lower()

    def test_contains_sections_table(self) -> None:
        section = HandoffSection(
            section_kind=HandoffPacketKind.OBSERVATION,
            state="READY",
            summary_text="ready",
            local_reference="data/observation/latest_observation_report.json",
        )
        packet = _make_packet(HandoffState.READY, sections=(section,))
        md = research_handoff_packet_to_markdown(packet)
        assert "observation" in md
        assert "READY" in md
        assert "ready" in md
        assert "data/observation/latest_observation_report.json" in md

    def test_contains_summary(self) -> None:
        section = HandoffSection(HandoffPacketKind.OBSERVATION, state="READY")
        packet = _make_packet(HandoffState.READY, sections=(section,))
        md = research_handoff_packet_to_markdown(packet)
        assert "total_sections" in md
        assert "ready_sections" in md

    def test_contains_data_quality(self) -> None:
        packet = _make_packet(HandoffState.READY)
        md = research_handoff_packet_to_markdown(packet)
        assert "completeness_pct" in md
        assert "ready_pct" in md

    def test_contains_safety_flags(self) -> None:
        packet = _make_packet(HandoffState.READY)
        md = research_handoff_packet_to_markdown(packet)
        assert "handoff_output_not_trade_approval" in md
        assert "handoff_output_not_execution_readiness" in md

    def test_contains_handoff_notes(self) -> None:
        packet = _make_packet(HandoffState.READY)
        md = research_handoff_packet_to_markdown(packet)
        assert "human audit" in md
        assert "not trade approval" in md
        assert "not execution readiness" in md

    def test_blocked_digest_markdown(self) -> None:
        section = HandoffSection(
            section_kind=HandoffPacketKind.DIGEST,
            state="BLOCK",
            reason_codes=("BLOCKED_DIGEST",),
        )
        packet = _make_packet(
            HandoffState.BLOCK,
            sections=(section,),
            reason_codes=("BLOCKED_DIGEST",),
        )
        md = research_handoff_packet_to_markdown(packet)
        assert "block" in md.lower()
        assert "BLOCKED_DIGEST" in md
        assert "not execution approval" in md

    def test_section_ordering(self) -> None:
        sections = (
            HandoffSection(HandoffPacketKind.QUALITY_GATE, state="READY"),
            HandoffSection(HandoffPacketKind.OBSERVATION, state="READY"),
            HandoffSection(HandoffPacketKind.DIGEST, state="READY"),
        )
        packet = _make_packet(HandoffState.READY, sections=sections)
        md = research_handoff_packet_to_markdown(packet)
        # Find detail headings in the Sections region.
        sections_region = md.split("## Sections")[-1]
        obs_pos = sections_region.find("### Observation")
        digest_pos = sections_region.find("### Digest")
        quality_pos = sections_region.find("### Quality Gate")
        assert 0 < obs_pos < digest_pos < quality_pos


# ---------------------------------------------------------------------------
# Atomic writes
# ---------------------------------------------------------------------------


class TestAtomicWriteJsonResearchHandoffPacket:
    def test_writes_json(self, tmp_path: Path) -> None:
        packet = _make_packet(HandoffState.READY)
        target = tmp_path / "packet.json"
        path = atomic_write_json_research_handoff_packet(packet, target_path=target)
        assert path == target
        assert target.exists()
        data = json.loads(target.read_text(encoding="utf-8"))
        assert data["packet_id"] == packet.packet_id
        assert data["handoff_state"] == "ready"
        assert data["safety_flags"]["handoff_output_is_human_audit_only"] is True

    def test_default_path(self) -> None:
        assert DEFAULT_HANDOFF_JSON_PATH == Path(
            "data/research_handoff/latest_research_handoff_packet.json"
        )


class TestAtomicWriteMarkdownResearchHandoffPacket:
    def test_writes_markdown(self, tmp_path: Path) -> None:
        packet = _make_packet(HandoffState.READY)
        target = tmp_path / "packet.md"
        path = atomic_write_markdown_research_handoff_packet(packet, target_path=target)
        assert path == target
        assert target.exists()
        text = target.read_text(encoding="utf-8")
        assert "# Research Handoff Packet" in text
        assert "human-audit / contractor-handoff artifact only" in text

    def test_default_path(self) -> None:
        assert DEFAULT_HANDOFF_MARKDOWN_PATH == Path(
            "reports/research_handoff/latest_research_handoff_packet.md"
        )


class TestWriteResearchHandoffPacket:
    def test_writes_both(self, tmp_path: Path) -> None:
        packet = _make_packet(HandoffState.READY)
        json_out, md_out = write_research_handoff_packet(
            packet,
            json_path=tmp_path / "packet.json",
            markdown_path=tmp_path / "packet.md",
        )
        assert json_out.exists()
        assert md_out.exists()
        data = json.loads(json_out.read_text(encoding="utf-8"))
        assert data["handoff_state"] == "ready"
        md_text = md_out.read_text(encoding="utf-8")
        assert "human-audit / contractor-handoff artifact only" in md_text


# ---------------------------------------------------------------------------
# Determinism and safety
# ---------------------------------------------------------------------------


class TestDeterminismAndSafety:
    def test_json_sorted_keys(self, tmp_path: Path) -> None:
        packet = _make_packet(HandoffState.READY)
        path1 = tmp_path / "packet1.json"
        path2 = tmp_path / "packet2.json"
        atomic_write_json_research_handoff_packet(packet, target_path=path1)
        atomic_write_json_research_handoff_packet(packet, target_path=path2)
        text1 = path1.read_text(encoding="utf-8")
        text2 = path2.read_text(encoding="utf-8")
        assert text1 == text2
        data1 = research_handoff_packet_to_dict(packet)
        data2 = research_handoff_packet_to_dict(packet)
        assert list(data1.keys()) == list(data2.keys())

    def test_no_forbidden_terms_in_markdown(self) -> None:
        from hunter.research_handoff.models import FORBIDDEN_HANDOFF_TERMS

        packet = _make_packet(HandoffState.READY)
        md = research_handoff_packet_to_markdown(packet)
        prose = md.split("## Safety Flags")[0].lower()
        for term in FORBIDDEN_HANDOFF_TERMS:
            assert term not in prose, term

    def test_metadata_strings_not_traversed(self, tmp_path: Path) -> None:
        section = HandoffSection(
            section_kind=HandoffPacketKind.DIGEST,
            state="READY",
            metadata={"report_path": "reports/2025/btc.md"},
        )
        packet = _make_packet(HandoffState.READY, sections=(section,))
        json_path = tmp_path / "packet.json"
        md_path = tmp_path / "packet.md"
        write_research_handoff_packet(packet, json_path=json_path, markdown_path=md_path)
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data["sections"][0]["metadata"]["report_path"] == "reports/2025/btc.md"
        md_text = md_path.read_text(encoding="utf-8")
        assert "reports/2025/btc.md" in md_text

    def test_packet_not_mutated(self) -> None:
        packet = _make_packet(HandoffState.READY)
        before = research_handoff_packet_to_dict(packet)
        research_handoff_packet_to_markdown(packet)
        research_handoff_packet_to_dict(packet)
        after = research_handoff_packet_to_dict(packet)
        assert before == after

    def test_no_production_path_writes_in_tests(self, tmp_path: Path) -> None:
        packet = _make_packet(HandoffState.READY)
        json_out, md_out = write_research_handoff_packet(
            packet,
            json_path=tmp_path / "packet.json",
            markdown_path=tmp_path / "packet.md",
        )
        assert str(json_out).startswith(str(tmp_path))
        assert str(md_out).startswith(str(tmp_path))
