"""Engine tests for the Research Audit Remediation Handoff Packet (MVP-50).

Tests validate grouping, state derivation, summary counts, forbidden-term
scanning, and deterministic output ordering.
"""

from __future__ import annotations

from datetime import datetime, timezone

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
    HandoffPacket,
    HandoffPacketConfig,
    HandoffPacketError,
    build_research_audit_remediation_handoff_packet,
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
        subject_id=f"sub_{item_id}",
        source_id=f"src_{item_id}",
        finding_id=f"finding_{item_id}",
        item_type=item_type,
        item_state=RemediationBacklogItemState.OPEN,
        severity=severity,
        priority=priority,
        title=title,
        description=description,
        reason_codes=reason_codes,
        metadata={"family": family},
    )


def _make_bridge_report(
    items: tuple[RemediationBacklogItem, ...],
    report_id: str = "bridge_1",
) -> RemediationBridgeReport:
    return RemediationBridgeReport(
        report_id=report_id,
        source_report_id="health_1",
        generated_at="2026-07-12T00:00:00+00:00",
        items=items,
        data_quality=RemediationBridgeDataQuality(),
        safety_flags=RemediationBacklogSafetyFlags(),
    )


class TestBuildHandoffPacket:
    """Tests for build_research_audit_remediation_handoff_packet."""

    def test_empty_items(self) -> None:
        report = _make_bridge_report(items=())
        pkt = build_research_audit_remediation_handoff_packet(report)
        assert pkt.total_items == 0
        assert pkt.state == "ok"
        assert pkt.group_count == 0
        assert pkt.data_quality.input_items == 0

    def test_single_item_blocking(self) -> None:
        item = _make_item(
            item_id="i1",
            severity=RemediationBacklogSeverity.BLOCKING,
            priority=RemediationBacklogPriority.P0,
        )
        report = _make_bridge_report(items=(item,))
        pkt = build_research_audit_remediation_handoff_packet(report)
        assert pkt.total_items == 1
        assert pkt.total_blocking == 1
        assert pkt.total_advisory == 0
        assert pkt.total_info == 0
        assert pkt.state == "blocked"
        assert pkt.group_count == 1

    def test_single_item_advisory(self) -> None:
        item = _make_item(
            item_id="i1",
            severity=RemediationBacklogSeverity.ADVISORY,
            priority=RemediationBacklogPriority.P1,
        )
        report = _make_bridge_report(items=(item,))
        pkt = build_research_audit_remediation_handoff_packet(report)
        assert pkt.total_items == 1
        assert pkt.total_blocking == 0
        assert pkt.total_advisory == 1
        assert pkt.total_info == 0
        assert pkt.state == "degraded"
        assert pkt.group_count == 1

    def test_single_item_info(self) -> None:
        item = _make_item(
            item_id="i1",
            severity=RemediationBacklogSeverity.INFO,
            priority=RemediationBacklogPriority.NONE,
        )
        report = _make_bridge_report(items=(item,))
        pkt = build_research_audit_remediation_handoff_packet(report)
        assert pkt.total_items == 1
        assert pkt.total_info == 1
        assert pkt.state == "ok"
        assert pkt.group_count == 1

    def test_mixed_items_blocking_dominates_state(self) -> None:
        items = (
            _make_item("i1", RemediationBacklogSeverity.BLOCKING, RemediationBacklogPriority.P0),
            _make_item("i2", RemediationBacklogSeverity.ADVISORY, RemediationBacklogPriority.P1),
            _make_item("i3", RemediationBacklogSeverity.INFO, RemediationBacklogPriority.NONE),
        )
        report = _make_bridge_report(items=items)
        pkt = build_research_audit_remediation_handoff_packet(report)
        assert pkt.total_items == 3
        assert pkt.total_blocking == 1
        assert pkt.total_advisory == 1
        assert pkt.total_info == 1
        assert pkt.state == "blocked"

    def test_multiple_groups(self) -> None:
        items = (
            _make_item(
                "i1",
                RemediationBacklogSeverity.BLOCKING,
                RemediationBacklogPriority.P0,
                family="audit_health",
            ),
            _make_item(
                "i2",
                RemediationBacklogSeverity.ADVISORY,
                RemediationBacklogPriority.P1,
                reason_codes=(RemediationBacklogReasonCode.SAFETY_BLOCKED,),
                family="remediation_backlog",
            ),
        )
        report = _make_bridge_report(items=items)
        pkt = build_research_audit_remediation_handoff_packet(report)
        assert pkt.total_items == 2
        assert pkt.group_count == 2
        assert pkt.state == "blocked"

    def test_reason_codes_sorted_tuple_join(self) -> None:
        """Multiple reason codes are joined in sorted order for grouping."""
        item = _make_item(
            "i1",
            RemediationBacklogSeverity.ADVISORY,
            RemediationBacklogPriority.P1,
            reason_codes=(
                RemediationBacklogReasonCode.ORPHAN_FINDING_REF,
                RemediationBacklogReasonCode.MISSING_OWNER,
                RemediationBacklogReasonCode.CONSISTENCY_DEGRADED,
            ),
            family="audit_health",
        )
        report = _make_bridge_report(items=(item,))
        pkt = build_research_audit_remediation_handoff_packet(report)
        assert pkt.group_count == 1
        group = pkt.groups[0]
        assert group.reason_code == "consistency_degraded+missing_owner+orphan_finding_ref"
        assert group.item_count == 1

    def test_empty_reason_codes_group_to_unknown(self) -> None:
        """Empty reason_codes tuple maps to 'unknown' group reason code."""
        item = _make_item(
            "i1",
            RemediationBacklogSeverity.ADVISORY,
            RemediationBacklogPriority.P1,
            reason_codes=(),
            family="audit_health",
        )
        report = _make_bridge_report(items=(item,))
        pkt = build_research_audit_remediation_handoff_packet(report)
        assert pkt.group_count == 1
        group = pkt.groups[0]
        assert group.reason_code == "unknown"
        assert group.item_count == 1

    def test_deterministic_output(self) -> None:
        """Two identical inputs produce identical packets (except generated_at)."""
        items = (
            _make_item("i1", RemediationBacklogSeverity.BLOCKING, RemediationBacklogPriority.P0),
            _make_item("i2", RemediationBacklogSeverity.ADVISORY, RemediationBacklogPriority.P1),
        )
        report = _make_bridge_report(items=items)
        pkt1 = build_research_audit_remediation_handoff_packet(report)
        pkt2 = build_research_audit_remediation_handoff_packet(report)
        # packet_id, groups, counts should match
        assert pkt1.packet_id == pkt2.packet_id
        assert pkt1.total_items == pkt2.total_items
        assert pkt1.group_count == pkt2.group_count
        assert pkt1.state == pkt2.state
        # group IDs and structures should match
        for g1, g2 in zip(pkt1.groups, pkt2.groups):
            assert g1.group_id == g2.group_id
            assert g1.item_count == g2.item_count

    def test_forbidden_term_scanning_blocked(self) -> None:
        item = _make_item(
            item_id="i1",
            severity=RemediationBacklogSeverity.ADVISORY,
            title="This is approved for trading",
        )
        report = _make_bridge_report(items=(item,))
        pkt = build_research_audit_remediation_handoff_packet(report)
        assert pkt.safety_flags.has_forbidden_terms is True
        assert pkt.data_quality.safety_flagged_items == 1

    def test_forbidden_term_scanning_clean(self) -> None:
        item = _make_item(
            item_id="i1",
            severity=RemediationBacklogSeverity.ADVISORY,
            title="Review finding X for consistency",
        )
        report = _make_bridge_report(items=(item,))
        pkt = build_research_audit_remediation_handoff_packet(report)
        assert pkt.safety_flags.has_forbidden_terms is False
        assert pkt.data_quality.safety_flagged_items == 0

    def test_exclude_info(self) -> None:
        items = (
            _make_item("i1", RemediationBacklogSeverity.BLOCKING, RemediationBacklogPriority.P0),
            _make_item("i2", RemediationBacklogSeverity.INFO, RemediationBacklogPriority.NONE),
        )
        report = _make_bridge_report(items=items)
        cfg = HandoffPacketConfig(exclude_info=True)
        pkt = build_research_audit_remediation_handoff_packet(report, config=cfg)
        assert pkt.total_items == 1
        assert pkt.total_blocking == 1
        assert pkt.total_info == 0
        assert pkt.data_quality.dropped_info == 1

    def test_owner_reviewer_from_config(self) -> None:
        item = _make_item("i1", RemediationBacklogSeverity.INFO)
        report = _make_bridge_report(items=(item,))
        cfg = HandoffPacketConfig(owner="alice", reviewer="bob")
        pkt = build_research_audit_remediation_handoff_packet(report, config=cfg)
        assert pkt.owner == "alice"
        assert pkt.reviewer == "bob"

    def test_tuple_input(self) -> None:
        """Can pass a tuple of items directly instead of a bridge report."""
        items = (
            _make_item("i1", RemediationBacklogSeverity.ADVISORY),
            _make_item("i2", RemediationBacklogSeverity.INFO),
        )
        pkt = build_research_audit_remediation_handoff_packet(items)
        assert pkt.total_items == 2
        assert pkt.source_report_id == "unknown_source"
        assert pkt.state == "degraded"

    def test_invalid_input(self) -> None:
        with pytest.raises(HandoffPacketError):
            build_research_audit_remediation_handoff_packet("invalid")  # type: ignore[arg-type]
