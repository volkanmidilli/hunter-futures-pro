"""Writer tests for the Research Audit Remediation Handoff Packet (MVP-50).

Tests validate deterministic JSON/Markdown serialization and optional atomic
file writers.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from hunter.remediation_backlog.models import (
    RemediationBacklogItem,
    RemediationBacklogItemState,
    RemediationBacklogItemType,
    RemediationBacklogPriority,
    RemediationBacklogReasonCode,
    RemediationBacklogSafetyFlags,
    RemediationBacklogSeverity,
)
from hunter.research_audit_health_remediation.models import (
    RemediationBridgeDataQuality,
    RemediationBridgeReport,
)
from hunter.research_audit_remediation_handoff import (
    HandoffPacketConfig,
    atomic_write_json_handoff_packet,
    atomic_write_markdown_handoff_packet,
    build_research_audit_remediation_handoff_packet,
    handoff_packet_to_dict,
    handoff_packet_to_json,
    handoff_packet_to_markdown,
)
from hunter.research_audit_remediation_handoff.writer import (
    HandoffPacketWriterError,
    _escape_markdown,
)


def _make_item(
    item_id: str = "i1",
    severity: RemediationBacklogSeverity = RemediationBacklogSeverity.ADVISORY,
    priority: RemediationBacklogPriority = RemediationBacklogPriority.P2,
    item_type: RemediationBacklogItemType = RemediationBacklogItemType.MANUAL_REVIEW,
    reason_codes: tuple[RemediationBacklogReasonCode, ...] = (RemediationBacklogReasonCode.CONSISTENCY_DEGRADED,),
    title: str = "test item",
    description: str = "description",
    family: str = "audit_health",
) -> RemediationBacklogItem:
    return RemediationBacklogItem(
        item_id=item_id,
        subject_id=item_id,
        source_id="source_1",
        finding_id="f1",
        item_type=item_type,
        item_state=RemediationBacklogItemState.OPEN,
        severity=severity,
        priority=priority,
        title=title,
        description=description,
        owner="alice",
        reviewer="bob",
        generated_at=datetime(2026, 7, 12, 12, 0, 0, tzinfo=timezone.utc),
        reason_codes=reason_codes,
        metadata={"family": family},
    )


def _make_bridge_report(
    items: tuple[RemediationBacklogItem, ...] = (),
    report_id: str = "bridge_1",
    source_report_id: str = "source_1",
) -> RemediationBridgeReport:
    return RemediationBridgeReport(
        report_id=report_id,
        source_report_id=source_report_id,
        generated_at="2026-07-12T12:00:00+00:00",
        items=items,
        data_quality=RemediationBridgeDataQuality(
            input_findings=len(items),
            produced_items=len(items),
            dropped_info=0,
            duplicates_collapsed=0,
            safety_flagged_items=0,
        ),
        safety_flags=RemediationBacklogSafetyFlags(),
    )


class TestHandoffPacketToDict:
    """Tests for handoff_packet_to_dict."""

    def test_basic_dict(self) -> None:
        item = _make_item()
        report = _make_bridge_report(items=(item,))
        pkt = build_research_audit_remediation_handoff_packet(report)
        data = handoff_packet_to_dict(pkt)
        assert data["kind"] == "research_audit_remediation_handoff_packet"
        assert data["packet_id"] == pkt.packet_id
        assert data["source_report_id"] == "source_1"
        assert data["state"] == "degraded"
        assert data["total_items"] == 1
        assert data["group_count"] == 1
        assert "safety_notice" in data
        assert "priority_notice" in data

    def test_dict_determinism(self) -> None:
        item = _make_item()
        report = _make_bridge_report(items=(item,))
        pkt = build_research_audit_remediation_handoff_packet(report)
        d1 = handoff_packet_to_dict(pkt)
        d2 = handoff_packet_to_dict(pkt)
        assert d1 == d2


class TestHandoffPacketToJson:
    """Tests for handoff_packet_to_json."""

    def test_json_roundtrip(self) -> None:
        item = _make_item()
        report = _make_bridge_report(items=(item,))
        pkt = build_research_audit_remediation_handoff_packet(report)
        json_str = handoff_packet_to_json(pkt)
        assert json_str.startswith("{")
        assert "packet_id" in json_str
        assert "safety_notice" in json_str

    def test_json_determinism(self) -> None:
        item = _make_item()
        report = _make_bridge_report(items=(item,))
        pkt = build_research_audit_remediation_handoff_packet(report)
        s1 = handoff_packet_to_json(pkt)
        s2 = handoff_packet_to_json(pkt)
        assert s1 == s2

    def test_json_indent_none(self) -> None:
        item = _make_item()
        report = _make_bridge_report(items=(item,))
        pkt = build_research_audit_remediation_handoff_packet(report)
        json_str = handoff_packet_to_json(pkt, indent=None)
        assert "\n" not in json_str


class TestHandoffPacketToMarkdown:
    """Tests for handoff_packet_to_markdown."""

    def test_markdown_contains_metadata(self) -> None:
        item = _make_item()
        report = _make_bridge_report(items=(item,))
        pkt = build_research_audit_remediation_handoff_packet(report)
        md = handoff_packet_to_markdown(pkt)
        assert "# Research Audit Remediation Handoff Packet" in md
        assert "## Safety Notice" in md
        assert "## Priority Notice" in md
        assert "## Packet Metadata" in md
        assert "## Summary Counts" in md
        assert "## Groups" in md

    def test_markdown_contains_group_table(self) -> None:
        item = _make_item()
        report = _make_bridge_report(items=(item,))
        pkt = build_research_audit_remediation_handoff_packet(report)
        md = handoff_packet_to_markdown(pkt)
        assert "| item_id | title | severity | priority | item_state |" in md
        assert "i1" in md
        assert "test item" in md

    def test_markdown_safety_warning_for_forbidden_terms(self) -> None:
        item = _make_item(
            title="This is approved for trading",
            description="description",
        )
        report = _make_bridge_report(items=(item,))
        cfg = HandoffPacketConfig(include_markdown_safety_notice=True)
        pkt = build_research_audit_remediation_handoff_packet(report, config=cfg)
        md = handoff_packet_to_markdown(pkt)
        assert "## Safety Warning" in md
        assert "Forbidden readiness/trading terminology" in md

    def test_markdown_escapes_pipe(self) -> None:
        item = _make_item(title="a|b")
        report = _make_bridge_report(items=(item,))
        pkt = build_research_audit_remediation_handoff_packet(report)
        md = handoff_packet_to_markdown(pkt)
        assert "a\\|b" in md


class TestAtomicWriters:
    """Tests for optional atomic file writers."""

    def test_atomic_write_json(self, tmp_path: Path) -> None:
        item = _make_item()
        report = _make_bridge_report(items=(item,))
        pkt = build_research_audit_remediation_handoff_packet(report)
        target = tmp_path / "packet.json"
        path = atomic_write_json_handoff_packet(pkt, target)
        assert path == target
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "packet_id" in content

    def test_atomic_write_markdown(self, tmp_path: Path) -> None:
        item = _make_item()
        report = _make_bridge_report(items=(item,))
        pkt = build_research_audit_remediation_handoff_packet(report)
        target = tmp_path / "packet.md"
        path = atomic_write_markdown_handoff_packet(pkt, target)
        assert path == target
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "# Research Audit Remediation Handoff Packet" in content

    def test_atomic_write_json_default_path(self, tmp_path: Path) -> None:
        item = _make_item()
        report = _make_bridge_report(items=(item,))
        pkt = build_research_audit_remediation_handoff_packet(report)
        original_default = atomic_write_json_handoff_packet.__defaults__
        try:
            # Temporarily override default path for test isolation
            atomic_write_json_handoff_packet.__defaults__ = (tmp_path / "default.json",)
            path = atomic_write_json_handoff_packet(pkt)
            assert path.exists()
        finally:
            atomic_write_json_handoff_packet.__defaults__ = original_default


class TestMarkdownEscape:
    """Tests for Markdown escaping helper."""

    def test_escape_pipe(self) -> None:
        assert _escape_markdown("a|b") == "a\\|b"

    def test_no_change(self) -> None:
        assert _escape_markdown("abc") == "abc"

    def test_handoff_packet_writer_error_importable(self) -> None:
        assert HandoffPacketWriterError is not None
