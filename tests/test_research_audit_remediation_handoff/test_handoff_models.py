"""Model tests for the Research Audit Remediation Handoff Packet (MVP-50).

Tests validate frozen dataclass construction, validation in __post_init__, and
error cases for all models.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from hunter.research_audit_remediation_handoff import (
    HandoffPacket,
    HandoffPacketConfig,
    HandoffPacketDataQuality,
    HandoffPacketError,
    HandoffPacketGroup,
    HandoffPacketSafetyFlags,
)


class TestHandoffPacketConfig:
    """Tests for HandoffPacketConfig."""

    def test_default_config(self) -> None:
        cfg = HandoffPacketConfig()
        assert cfg.owner is None
        assert cfg.reviewer is None
        assert cfg.notes == ""
        assert cfg.exclude_info is False
        assert cfg.include_markdown_safety_notice is True

    def test_config_with_values(self) -> None:
        cfg = HandoffPacketConfig(
            owner="alice",
            reviewer="bob",
            notes="Review this batch",
            exclude_info=True,
            include_markdown_safety_notice=False,
        )
        assert cfg.owner == "alice"
        assert cfg.reviewer == "bob"
        assert cfg.notes == "Review this batch"
        assert cfg.exclude_info is True
        assert cfg.include_markdown_safety_notice is False

    def test_config_owner_reviewer_strip(self) -> None:
        cfg = HandoffPacketConfig(owner="  alice  ", reviewer="  bob  ")
        assert cfg.owner == "alice"
        assert cfg.reviewer == "bob"

    def test_config_invalid_owner(self) -> None:
        with pytest.raises(ValueError):
            HandoffPacketConfig(owner="")

    def test_config_invalid_reviewer(self) -> None:
        with pytest.raises(ValueError):
            HandoffPacketConfig(reviewer="   ")


class TestHandoffPacketGroup:
    """Tests for HandoffPacketGroup."""

    def test_valid_group(self) -> None:
        grp = HandoffPacketGroup(
            group_id="abc123",
            severity="blocking",
            priority="p0",
            item_type="manual_review",
            reason_code="consistency_degraded",
            family="audit_health",
            item_count=3,
            blocking_count=2,
            advisory_count=1,
            info_count=0,
            items=(
                {"item_id": "i1", "title": "test"},
                {"item_id": "i2", "title": "test2"},
            ),
        )
        assert grp.group_id == "abc123"
        assert grp.item_count == 3
        assert grp.blocking_count == 2
        assert len(grp.items) == 2

    def test_empty_group_id(self) -> None:
        with pytest.raises(ValueError):
            HandoffPacketGroup(
                group_id="",
                severity="info",
                priority="none",
                item_type="manual_review",
                reason_code="ok",
                family="unknown",
                item_count=0,
                blocking_count=0,
                advisory_count=0,
                info_count=0,
                items=(),
            )

    def test_negative_count(self) -> None:
        with pytest.raises(ValueError):
            HandoffPacketGroup(
                group_id="g1",
                severity="info",
                priority="none",
                item_type="manual_review",
                reason_code="ok",
                family="unknown",
                item_count=-1,
                blocking_count=0,
                advisory_count=0,
                info_count=0,
                items=(),
            )

    def test_items_not_tuple(self) -> None:
        with pytest.raises(ValueError):
            HandoffPacketGroup(
                group_id="g1",
                severity="info",
                priority="none",
                item_type="manual_review",
                reason_code="ok",
                family="unknown",
                item_count=0,
                blocking_count=0,
                advisory_count=0,
                info_count=0,
                items=[],  # type: ignore[arg-type]
            )


class TestHandoffPacketDataQuality:
    """Tests for HandoffPacketDataQuality."""

    def test_default_dq(self) -> None:
        dq = HandoffPacketDataQuality()
        assert dq.input_items == 0
        assert dq.produced_items == 0
        assert dq.dropped_info == 0
        assert dq.grouped_items == 0
        assert dq.safety_flagged_items == 0
        assert dq.group_count == 0

    def test_dq_with_values(self) -> None:
        dq = HandoffPacketDataQuality(
            input_items=10,
            produced_items=8,
            dropped_info=2,
            grouped_items=8,
            safety_flagged_items=1,
            group_count=3,
        )
        assert dq.input_items == 10
        assert dq.group_count == 3

    def test_negative_input(self) -> None:
        with pytest.raises(ValueError):
            HandoffPacketDataQuality(input_items=-1)


class TestHandoffPacketSafetyFlags:
    """Tests for HandoffPacketSafetyFlags."""

    def test_default_safety(self) -> None:
        sf = HandoffPacketSafetyFlags()
        assert sf.has_forbidden_terms is False
        assert sf.references_opaque is True
        assert sf.no_executable_actions is True
        assert sf.no_trading_instructions is True
        assert sf.no_approval_claims is True

    def test_safety_with_forbidden(self) -> None:
        sf = HandoffPacketSafetyFlags(has_forbidden_terms=True)
        assert sf.has_forbidden_terms is True


class TestHandoffPacket:
    """Tests for HandoffPacket."""

    def make_valid_packet(self) -> HandoffPacket:
        dq = HandoffPacketDataQuality()
        sf = HandoffPacketSafetyFlags()
        grp = HandoffPacketGroup(
            group_id="g1",
            severity="info",
            priority="none",
            item_type="manual_review",
            reason_code="ok",
            family="unknown",
            item_count=0,
            blocking_count=0,
            advisory_count=0,
            info_count=0,
            items=(),
        )
        return HandoffPacket(
            packet_id="pkt1",
            source_report_id="src1",
            generated_at="2026-07-12T00:00:00+00:00",
            project_version="0.50.0-dev",
            owner=None,
            reviewer=None,
            notes="",
            total_items=0,
            total_blocking=0,
            total_advisory=0,
            total_info=0,
            group_count=1,
            state="ok",
            groups=(grp,),
            data_quality=dq,
            safety_flags=sf,
        )

    def test_valid_packet(self) -> None:
        pkt = self.make_valid_packet()
        assert pkt.packet_id == "pkt1"
        assert pkt.state == "ok"
        assert pkt.group_count == 1

    def test_empty_packet_id(self) -> None:
        with pytest.raises(ValueError):
            p = self.make_valid_packet()
            HandoffPacket(
                packet_id="",
                source_report_id=p.source_report_id,
                generated_at=p.generated_at,
                project_version=p.project_version,
                owner=p.owner,
                reviewer=p.reviewer,
                notes=p.notes,
                total_items=p.total_items,
                total_blocking=p.total_blocking,
                total_advisory=p.total_advisory,
                total_info=p.total_info,
                group_count=p.group_count,
                state=p.state,
                groups=p.groups,
                data_quality=p.data_quality,
                safety_flags=p.safety_flags,
            )

    def test_empty_source_report_id(self) -> None:
        with pytest.raises(ValueError):
            p = self.make_valid_packet()
            HandoffPacket(
                packet_id=p.packet_id,
                source_report_id="",
                generated_at=p.generated_at,
                project_version=p.project_version,
                owner=p.owner,
                reviewer=p.reviewer,
                notes=p.notes,
                total_items=p.total_items,
                total_blocking=p.total_blocking,
                total_advisory=p.total_advisory,
                total_info=p.total_info,
                group_count=p.group_count,
                state=p.state,
                groups=p.groups,
                data_quality=p.data_quality,
                safety_flags=p.safety_flags,
            )

    def test_invalid_state(self) -> None:
        with pytest.raises(ValueError):
            p = self.make_valid_packet()
            HandoffPacket(
                packet_id=p.packet_id,
                source_report_id=p.source_report_id,
                generated_at=p.generated_at,
                project_version=p.project_version,
                owner=p.owner,
                reviewer=p.reviewer,
                notes=p.notes,
                total_items=p.total_items,
                total_blocking=p.total_blocking,
                total_advisory=p.total_advisory,
                total_info=p.total_info,
                group_count=p.group_count,
                state="invalid",
                groups=p.groups,
                data_quality=p.data_quality,
                safety_flags=p.safety_flags,
            )

    def test_negative_total(self) -> None:
        with pytest.raises(ValueError):
            p = self.make_valid_packet()
            HandoffPacket(
                packet_id=p.packet_id,
                source_report_id=p.source_report_id,
                generated_at=p.generated_at,
                project_version=p.project_version,
                owner=p.owner,
                reviewer=p.reviewer,
                notes=p.notes,
                total_items=-1,
                total_blocking=p.total_blocking,
                total_advisory=p.total_advisory,
                total_info=p.total_info,
                group_count=p.group_count,
                state=p.state,
                groups=p.groups,
                data_quality=p.data_quality,
                safety_flags=p.safety_flags,
            )

    def test_owner_reviewer_not_none(self) -> None:
        p = self.make_valid_packet()
        pkt = HandoffPacket(
            packet_id=p.packet_id,
            source_report_id=p.source_report_id,
            generated_at=p.generated_at,
            project_version=p.project_version,
            owner="alice",
            reviewer="bob",
            notes=p.notes,
            total_items=p.total_items,
            total_blocking=p.total_blocking,
            total_advisory=p.total_advisory,
            total_info=p.total_info,
            group_count=p.group_count,
            state=p.state,
            groups=p.groups,
            data_quality=p.data_quality,
            safety_flags=p.safety_flags,
        )
        assert pkt.owner == "alice"
        assert pkt.reviewer == "bob"
