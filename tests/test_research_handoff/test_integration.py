"""Integration tests for hunter.research_handoff package.

MVP-18 end-to-end integration tests only.
No network, database, Freqtrade, Binance, exchange, trading,
Web UI, dashboard, or production data access is exercised here.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from hunter.research_handoff.engine import build_research_handoff_packet
from hunter.research_handoff.models import (
    HANDOFF_BLOCKING_REASON_CODES,
    HandoffConfig,
    HandoffPacketKind,
    HandoffSafetyFlags,
    HandoffSection,
    HandoffState,
    ResearchHandoffPacket,
)
from hunter.research_handoff.writer import (
    research_handoff_packet_to_dict,
    research_handoff_packet_to_markdown,
    write_research_handoff_packet,
)


def _now() -> datetime:
    return datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _make_safety_flags() -> HandoffSafetyFlags:
    return HandoffSafetyFlags()


@dataclass(frozen=True)
class _Artifact:
    state: str = "READY"
    reason_codes: tuple[str, ...] = ()
    generated_at: datetime | None = None
    safety_flags: HandoffSafetyFlags | None = None
    summary_text: str | None = None
    verdict: str | None = None
    metadata: dict[str, object] | None = None

    def __post_init__(self) -> None:
        if self.generated_at is None:
            object.__setattr__(
                self, "generated_at", datetime(2099, 1, 1, tzinfo=timezone.utc)
            )
        if self.safety_flags is None:
            object.__setattr__(self, "safety_flags", _make_safety_flags())


def _make_artifact(
    state: str = "READY",
    reason_codes: tuple[str, ...] = (),
    generated_at: datetime | None = None,
    safety_flags: HandoffSafetyFlags | None = None,
    summary_text: str | None = None,
    verdict: str | None = None,
    metadata: dict[str, object] | None = None,
) -> dict[str, object]:
    if generated_at is None:
        generated_at = datetime(2099, 1, 1, tzinfo=timezone.utc)
    if safety_flags is None:
        safety_flags = _make_safety_flags()
    data: dict[str, object] = {
        "state": state,
        "reason_codes": reason_codes,
        "generated_at": generated_at,
        "safety_flags": safety_flags,
    }
    if summary_text is not None:
        data["summary_text"] = summary_text
    if verdict is not None:
        data["verdict"] = verdict
    if metadata is not None:
        data["metadata"] = metadata
    return data


class TestHappyPath:
    def test_full_flow_build_serialize_write(self, tmp_path: Path) -> None:
        packet = build_research_handoff_packet(
            config=HandoffConfig(generated_at=_now()),
            observation_artifact=_make_artifact("READY"),
            review_artifact=_make_artifact("READY"),
            index_artifact={
                "index_state": "READY",
                "reason_codes": (),
                "generated_at": _now(),
                "safety_flags": _make_safety_flags(),
            },
            search_artifact={
                "search_state": "READY",
                "reason_codes": (),
                "generated_at": _now(),
                "safety_flags": _make_safety_flags(),
            },
            bundle_artifact=_make_artifact("READY"),
            chronicle_artifact=_make_artifact("READY"),
            digest_artifact=_make_artifact("READY"),
            quality_gate_artifact=_make_artifact("READY", verdict="PASS"),
            reference_time=_now(),
        )

        assert packet.handoff_state is HandoffState.READY
        assert len(packet.sections) == 8

        d = research_handoff_packet_to_dict(packet)
        assert d["handoff_state"] == "ready"
        assert d["summary"]["ready_sections"] == 8

        json_path = tmp_path / "packet.json"
        md_path = tmp_path / "packet.md"
        write_research_handoff_packet(packet, json_path=json_path, markdown_path=md_path)

        assert json_path.exists()
        assert md_path.exists()

        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data["packet_id"] == packet.packet_id
        assert data["handoff_state"] == "ready"

        md_text = md_path.read_text(encoding="utf-8")
        assert "# Research Handoff Packet" in md_text
        assert "human-audit / contractor-handoff artifact only" in md_text

    def test_deterministic_section_ordering(self) -> None:
        packet = build_research_handoff_packet(
            config=HandoffConfig(generated_at=_now()),
            quality_gate_artifact=_make_artifact("READY", verdict="PASS"),
            digest_artifact=_make_artifact("READY"),
            chronicle_artifact=_make_artifact("READY"),
            bundle_artifact=_make_artifact("READY"),
            search_artifact={
                "search_state": "READY",
                "reason_codes": (),
                "generated_at": _now(),
                "safety_flags": _make_safety_flags(),
            },
            index_artifact={
                "index_state": "READY",
                "reason_codes": (),
                "generated_at": _now(),
                "safety_flags": _make_safety_flags(),
            },
            review_artifact=_make_artifact("READY"),
            observation_artifact=_make_artifact("READY"),
            reference_time=_now(),
        )

        kinds = [section.section_kind for section in packet.sections]
        assert kinds == [
            HandoffPacketKind.OBSERVATION,
            HandoffPacketKind.REVIEW,
            HandoffPacketKind.INDEX,
            HandoffPacketKind.SEARCH,
            HandoffPacketKind.BUNDLE,
            HandoffPacketKind.CHRONICLE,
            HandoffPacketKind.DIGEST,
            HandoffPacketKind.QUALITY_GATE,
        ]

        d = research_handoff_packet_to_dict(packet)
        section_kinds = [section["section_kind"] for section in d["sections"]]
        assert section_kinds == [
            "observation",
            "review",
            "index",
            "search",
            "bundle",
            "chronicle",
            "digest",
            "quality_gate",
        ]


class TestVerdictIntegration:
    def test_ready_packet(self) -> None:
        packet = build_research_handoff_packet(
            config=HandoffConfig(generated_at=_now()),
            observation_artifact=_make_artifact("READY"),
            review_artifact=_make_artifact("READY"),
            index_artifact={
                "index_state": "READY",
                "reason_codes": (),
                "generated_at": _now(),
                "safety_flags": _make_safety_flags(),
            },
            search_artifact={
                "search_state": "READY",
                "reason_codes": (),
                "generated_at": _now(),
                "safety_flags": _make_safety_flags(),
            },
            bundle_artifact=_make_artifact("READY"),
            chronicle_artifact=_make_artifact("READY"),
            digest_artifact=_make_artifact("READY"),
            quality_gate_artifact=_make_artifact("READY", verdict="PASS"),
            reference_time=_now(),
        )
        assert packet.handoff_state is HandoffState.READY
        assert packet.summary.ready_sections == 8
        assert packet.summary.block_sections == 0
        assert packet.summary.warn_sections == 0
        assert packet.summary.unknown_sections == 0

    def test_warn_packet_for_stale(self) -> None:
        stale = _now() - timedelta(hours=2)
        packet = build_research_handoff_packet(
            config=HandoffConfig(generated_at=_now(), max_staleness_minutes=60),
            observation_artifact=_make_artifact("READY", generated_at=stale),
            review_artifact=_make_artifact("READY"),
            index_artifact={
                "index_state": "READY",
                "reason_codes": (),
                "generated_at": _now(),
                "safety_flags": _make_safety_flags(),
            },
            search_artifact={
                "search_state": "READY",
                "reason_codes": (),
                "generated_at": _now(),
                "safety_flags": _make_safety_flags(),
            },
            bundle_artifact=_make_artifact("READY"),
            chronicle_artifact=_make_artifact("READY"),
            digest_artifact=_make_artifact("READY"),
            quality_gate_artifact=_make_artifact("READY", verdict="PASS"),
            reference_time=_now(),
        )
        assert packet.handoff_state is HandoffState.WARN
        assert packet.summary.warn_sections >= 1
        assert packet.data_quality.stale_count >= 1
        assert "STALE_ARTIFACT" not in packet.reason_codes

    def test_block_packet_for_blocked_section(self) -> None:
        packet = build_research_handoff_packet(
            config=HandoffConfig(generated_at=_now()),
            observation_artifact=_make_artifact("READY"),
            review_artifact=_make_artifact("READY"),
            index_artifact={
                "index_state": "READY",
                "reason_codes": (),
                "generated_at": _now(),
                "safety_flags": _make_safety_flags(),
            },
            search_artifact={
                "search_state": "READY",
                "reason_codes": (),
                "generated_at": _now(),
                "safety_flags": _make_safety_flags(),
            },
            bundle_artifact=_make_artifact("READY"),
            chronicle_artifact=_make_artifact("READY"),
            digest_artifact=_make_artifact("BLOCKED", reason_codes=("BLOCKED_DIGEST",)),
            quality_gate_artifact=_make_artifact("READY", verdict="PASS"),
            reference_time=_now(),
        )
        assert packet.handoff_state is HandoffState.BLOCK
        assert packet.summary.block_sections >= 1
        assert "BLOCKED_DIGEST" in packet.reason_codes

    def test_block_packet_when_required_missing(self) -> None:
        packet = build_research_handoff_packet(
            config=HandoffConfig(generated_at=_now()),
            observation_artifact=None,
            review_artifact=_make_artifact("READY"),
            index_artifact={
                "index_state": "READY",
                "reason_codes": (),
                "generated_at": _now(),
                "safety_flags": _make_safety_flags(),
            },
            search_artifact={
                "search_state": "READY",
                "reason_codes": (),
                "generated_at": _now(),
                "safety_flags": _make_safety_flags(),
            },
            bundle_artifact=_make_artifact("READY"),
            chronicle_artifact=_make_artifact("READY"),
            digest_artifact=_make_artifact("READY"),
            quality_gate_artifact=_make_artifact("READY", verdict="PASS"),
            reference_time=_now(),
        )
        assert packet.handoff_state is HandoffState.BLOCK
        assert packet.summary.total_sections == 8
        assert packet.summary.block_sections >= 1
        assert "MISSING_OBSERVATION" in packet.reason_codes

    def test_block_packet_for_unresolved_blockers(self) -> None:
        packet = build_research_handoff_packet(
            config=HandoffConfig(generated_at=_now()),
            observation_artifact=_make_artifact(
                "READY", reason_codes=("MISSING_REVIEW",)
            ),
            review_artifact=_make_artifact("READY"),
            index_artifact={
                "index_state": "READY",
                "reason_codes": (),
                "generated_at": _now(),
                "safety_flags": _make_safety_flags(),
            },
            search_artifact={
                "search_state": "READY",
                "reason_codes": (),
                "generated_at": _now(),
                "safety_flags": _make_safety_flags(),
            },
            bundle_artifact=_make_artifact("READY"),
            chronicle_artifact=_make_artifact("READY"),
            digest_artifact=_make_artifact("READY"),
            quality_gate_artifact=_make_artifact("READY", verdict="PASS"),
            reference_time=_now(),
        )
        assert packet.handoff_state is HandoffState.BLOCK
        observation_section = next(
            section
            for section in packet.sections
            if section.section_kind is HandoffPacketKind.OBSERVATION
        )
        assert observation_section.state == "BLOCK"
        assert "UNRESOLVED_BLOCKERS" in observation_section.reason_codes
        assert "UNRESOLVED_BLOCKERS" in packet.reason_codes


class TestQualityGateVerdictExtraction:
    def test_quality_gate_verdict_from_dict(self) -> None:
        packet = build_research_handoff_packet(
            config=HandoffConfig(generated_at=_now()),
            observation_artifact=_make_artifact("READY"),
            quality_gate_artifact={
                "state": "READY",
                "verdict": "PASS",
                "reason_codes": (),
                "generated_at": _now(),
                "safety_flags": _make_safety_flags(),
            },
            reference_time=_now(),
        )
        assert packet.summary.quality_gate_verdict == "PASS"

    def test_quality_gate_verdict_from_object(self) -> None:
        quality_gate = _Artifact(state="READY", verdict="WARN")
        packet = build_research_handoff_packet(
            config=HandoffConfig(generated_at=_now()),
            observation_artifact=_make_artifact("READY"),
            quality_gate_artifact=quality_gate,
            reference_time=_now(),
        )
        assert packet.summary.quality_gate_verdict == "WARN"

    def test_quality_gate_verdict_defaults_unknown(self) -> None:
        packet = build_research_handoff_packet(
            config=HandoffConfig(generated_at=_now()),
            observation_artifact=_make_artifact("READY"),
            quality_gate_artifact=_make_artifact("READY"),
            reference_time=_now(),
        )
        assert packet.summary.quality_gate_verdict == "UNKNOWN"


class TestSummaryAndDataQuality:
    def test_summary_counts(self) -> None:
        packet = build_research_handoff_packet(
            config=HandoffConfig(generated_at=_now()),
            observation_artifact=_make_artifact("READY"),
            review_artifact=_make_artifact("BLOCKED", reason_codes=("BLOCKED_REVIEW",)),
            index_artifact={
                "index_state": "READY",
                "reason_codes": (),
                "generated_at": _now(),
                "safety_flags": _make_safety_flags(),
            },
            search_artifact={
                "search_state": "READY",
                "reason_codes": (),
                "generated_at": _now(),
                "safety_flags": _make_safety_flags(),
            },
            bundle_artifact=_make_artifact("READY"),
            chronicle_artifact=_make_artifact("UNKNOWN"),
            digest_artifact=_make_artifact("READY"),
            quality_gate_artifact=_make_artifact("READY", verdict="PASS"),
            reference_time=_now(),
        )
        # With block_on_unknown=True (default), UNKNOWN required sections become BLOCK.
        assert packet.summary.ready_sections >= 1
        assert packet.summary.block_sections >= 2
        assert packet.summary.total_sections == 8

    def test_data_quality_counts(self) -> None:
        stale = _now() - timedelta(hours=2)
        packet = build_research_handoff_packet(
            config=HandoffConfig(generated_at=_now(), max_staleness_minutes=60),
            observation_artifact=_make_artifact("READY", generated_at=stale),
            review_artifact=_make_artifact("READY"),
            index_artifact={
                "index_state": "READY",
                "reason_codes": (),
                "generated_at": _now(),
                "safety_flags": _make_safety_flags(),
            },
            search_artifact={
                "search_state": "READY",
                "reason_codes": (),
                "generated_at": _now(),
                "safety_flags": _make_safety_flags(),
            },
            bundle_artifact=_make_artifact("READY"),
            chronicle_artifact=_make_artifact("READY"),
            digest_artifact=_make_artifact("READY"),
            quality_gate_artifact=_make_artifact("READY", verdict="PASS"),
            reference_time=_now(),
        )
        assert packet.data_quality.total_sections == 8
        assert packet.data_quality.completeness_pct >= 0.0
        assert packet.data_quality.ready_pct >= 0.0
        assert packet.data_quality.stale_count >= 1


class TestSafetyFlagsAndDisclaimers:
    def test_safety_flags(self) -> None:
        packet = build_research_handoff_packet(
            config=HandoffConfig(generated_at=_now()),
            observation_artifact=_make_artifact("READY"),
            reference_time=_now(),
        )
        assert packet.safety_flags.handoff_feedback_into_execution is False
        assert packet.safety_flags.cross_layer_feedback_into_execution is False
        assert packet.safety_flags.handoff_output_not_trading_signal is True
        assert packet.safety_flags.handoff_output_not_trade_approval is True
        assert packet.safety_flags.handoff_output_not_execution_readiness is True
        assert packet.safety_flags.handoff_output_not_strategy_readiness is True

    def test_disclaimers_in_handoff_notes(self) -> None:
        packet = build_research_handoff_packet(
            config=HandoffConfig(generated_at=_now()),
            observation_artifact=_make_artifact("READY"),
            review_artifact=_make_artifact("READY"),
            index_artifact={
                "index_state": "READY",
                "reason_codes": (),
                "generated_at": _now(),
                "safety_flags": _make_safety_flags(),
            },
            search_artifact={
                "search_state": "READY",
                "reason_codes": (),
                "generated_at": _now(),
                "safety_flags": _make_safety_flags(),
            },
            bundle_artifact=_make_artifact("READY"),
            chronicle_artifact=_make_artifact("READY"),
            digest_artifact=_make_artifact("READY"),
            quality_gate_artifact=_make_artifact("READY", verdict="PASS"),
            reference_time=_now(),
        )
        notes = packet.handoff_notes.lower()
        assert "not trade approval" in notes
        assert "not execution approval" in notes or "not execution readiness" in notes
        assert "not strategy approval" in notes or "not strategy readiness" in notes
        assert "not release approval" in notes
        assert "not transaction permission" in notes


class TestSerializationAndMarkdown:
    def test_dict_round_trip(self) -> None:
        packet = build_research_handoff_packet(
            config=HandoffConfig(generated_at=_now()),
            observation_artifact=_make_artifact("READY"),
            review_artifact=_make_artifact("READY"),
            quality_gate_artifact=_make_artifact("READY", verdict="PASS"),
            reference_time=_now(),
        )
        d = research_handoff_packet_to_dict(packet)
        assert d["packet_id"] == packet.packet_id
        assert d["handoff_state"] == packet.handoff_state.value
        assert d["version"] == packet.version
        assert d["summary"]["total_sections"] == packet.summary.total_sections
        assert d["data_quality"]["total_sections"] == packet.data_quality.total_sections
        assert isinstance(d["reason_codes"], list)
        assert d["handoff_notes"] == packet.handoff_notes
        assert d["safety_flags"]["handoff_feedback_into_execution"] is False

    def test_markdown_safety_notice_before_sections(self) -> None:
        packet = build_research_handoff_packet(
            config=HandoffConfig(generated_at=_now()),
            observation_artifact=_make_artifact("READY"),
            reference_time=_now(),
        )
        md = research_handoff_packet_to_markdown(packet)
        safety_pos = md.find("human-audit / contractor-handoff artifact only")
        sections_pos = md.find("## Sections")
        assert safety_pos < sections_pos

    def test_markdown_fallback_title_for_empty_section_title(self) -> None:
        packet = build_research_handoff_packet(
            config=HandoffConfig(generated_at=_now()),
            observation_artifact=_make_artifact("READY"),
            reference_time=_now(),
        )
        md = research_handoff_packet_to_markdown(packet)
        assert "### Observation" in md


class TestWritesAndMetadataSafety:
    def test_dual_write_using_tmp_path(self, tmp_path: Path) -> None:
        packet = build_research_handoff_packet(
            config=HandoffConfig(generated_at=_now()),
            observation_artifact=_make_artifact("READY"),
            reference_time=_now(),
        )
        json_path = tmp_path / "packet.json"
        md_path = tmp_path / "packet.md"
        write_research_handoff_packet(packet, json_path=json_path, markdown_path=md_path)

        assert json_path.exists()
        assert md_path.exists()
        data = json.loads(json_path.read_text(encoding="utf-8"))
        assert data["packet_id"] == packet.packet_id
        assert "handoff_state" in data

    def test_file_reference_strings_not_opened(self, tmp_path: Path) -> None:
        section = HandoffSection(
            section_kind=HandoffPacketKind.OBSERVATION,
            title="Observation",
            state="READY",
            summary_text="Observation summary",
            local_reference="data/observation/latest_observation_report.json",
            reason_codes=(),
            metadata={
                "report_path": "reports/2025/btc.md",
                "nested": {"file_ref": "data/observation/x.json"},
            },
        )
        packet = ResearchHandoffPacket(
            packet_id="test:metadata",
            generated_at=_now(),
            sections=(section,),
        )

        json_path = tmp_path / "packet.json"
        md_path = tmp_path / "packet.md"
        write_research_handoff_packet(packet, json_path=json_path, markdown_path=md_path)

        data = json.loads(json_path.read_text(encoding="utf-8"))
        observation_section = next(
            section
            for section in data["sections"]
            if section["section_kind"] == "observation"
        )
        assert observation_section["metadata"]["report_path"] == "reports/2025/btc.md"
        assert observation_section["metadata"]["nested"]["file_ref"] == "data/observation/x.json"

        md_text = md_path.read_text(encoding="utf-8")
        assert "reports/2025/btc.md" in md_text
        assert "data/observation/x.json" in md_text

    def test_no_mutation_of_packet(self, tmp_path: Path) -> None:
        packet = build_research_handoff_packet(
            config=HandoffConfig(generated_at=_now()),
            observation_artifact=_make_artifact("READY"),
            reference_time=_now(),
        )
        before = research_handoff_packet_to_dict(packet)
        write_research_handoff_packet(
            packet,
            json_path=tmp_path / "packet.json",
            markdown_path=tmp_path / "packet.md",
        )
        after = research_handoff_packet_to_dict(packet)
        assert before == after

    def test_no_production_default_writes(self, tmp_path: Path) -> None:
        from hunter.research_handoff.writer import (
            DEFAULT_HANDOFF_JSON_PATH,
            DEFAULT_HANDOFF_MARKDOWN_PATH,
        )

        packet = build_research_handoff_packet(
            config=HandoffConfig(generated_at=_now()),
            observation_artifact=_make_artifact("READY"),
            reference_time=_now(),
        )
        json_path = tmp_path / "packet.json"
        md_path = tmp_path / "packet.md"
        write_research_handoff_packet(packet, json_path=json_path, markdown_path=md_path)

        assert str(json_path) != str(DEFAULT_HANDOFF_JSON_PATH)
        assert str(md_path) != str(DEFAULT_HANDOFF_MARKDOWN_PATH)
        assert not DEFAULT_HANDOFF_JSON_PATH.exists()
        assert not DEFAULT_HANDOFF_MARKDOWN_PATH.exists()


class TestFailClosedAndDeterminism:
    def test_fail_closed_empty_packet(self) -> None:
        packet = build_research_handoff_packet(
            config=HandoffConfig(generated_at=_now()),
            reference_time=_now(),
        )
        assert packet.handoff_state in (HandoffState.BLOCK, HandoffState.UNKNOWN)
        assert "EMPTY_PACKET" in packet.reason_codes or "MISSING_OBSERVATION" in packet.reason_codes

    def test_fail_closed_unsafe_config(self) -> None:
        with pytest.raises(ValueError):
            HandoffConfig(generated_at=_now(), live_trading_enabled=True)

    def test_deterministic_packet_id_and_generated_at(self) -> None:
        config = HandoffConfig(generated_at=_now())
        packet1 = build_research_handoff_packet(
            config=config,
            observation_artifact=_make_artifact("READY"),
            reference_time=_now(),
        )
        packet2 = build_research_handoff_packet(
            config=config,
            observation_artifact=_make_artifact("READY"),
            reference_time=_now(),
        )
        assert packet1.packet_id == packet2.packet_id
        assert packet1.generated_at == packet2.generated_at

    def test_no_forbidden_imports(self) -> None:
        import hunter.research_handoff.engine as engine_module
        import hunter.research_handoff.writer as writer_module

        source_engine = engine_module.__file__ or ""
        source_writer = writer_module.__file__ or ""
        assert "freqtrade" not in source_engine.lower()
        assert "binance" not in source_engine.lower()
        assert "requests" not in source_engine.lower()
        assert "freqtrade" not in source_writer.lower()
        assert "binance" not in source_writer.lower()
