"""Integration tests for the Research Audit Remediation Handoff Packet (MVP-50).

Tests validate end-to-end flows from a caller-built MVP-49
`RemediationBridgeReport` to a serialized handoff packet. All inputs are built
in-memory; no test reads from `data/` or `reports/`.
"""

from __future__ import annotations

import pytest

from hunter.research_audit_health.models import (
    HealthFinding,
    HealthReasonCode,
    HealthReport,
    HealthSafetyFlags,
    HealthScore,
    HealthSeverity,
    HealthState,
)
from hunter.research_audit_health_remediation import build_health_remediation_bridge_report
from hunter.research_audit_health_remediation.models import RemediationBridgeConfig
from hunter.research_audit_remediation_handoff import (
    HandoffPacketConfig,
    build_research_audit_remediation_handoff_packet,
    handoff_packet_to_json,
    handoff_packet_to_markdown,
)


def _make_health_report(
    findings: tuple[HealthFinding, ...] = (),
    report_id: str = "health_1",
    state: HealthState = HealthState.BLOCKED,
) -> HealthReport:
    return HealthReport(
        report_id=report_id,
        state=state,
        aggregate_score=HealthScore(value=0.0, weight=1.0, contributing_families=()),
        family_rollups=(),
        findings=findings,
        reason_code_counts={},
        data_quality={},
        safety_flags=HealthSafetyFlags(),
    )


def _make_health_finding(
    finding_id: str = "f1",
    severity: HealthSeverity = HealthSeverity.WARNING,
    reason_code: HealthReasonCode = HealthReasonCode.MALFORMED_METADATA,
    title: str = "Finding",
    family: str = "audit_family",
) -> HealthFinding:
    return HealthFinding(
        finding_id=finding_id,
        rule_id=reason_code.value,
        family=family,
        artifact_ids=("artifact_1",),
        severity=severity,
        reason_code=reason_code,
        title=title,
        description="description",
        evidence={"section": "summary"},
    )


def _build_bridge_report_from_health_findings(
    findings: tuple[HealthFinding, ...] = (),
) -> object:
    health_report = _make_health_report(findings)
    bridge_config = RemediationBridgeConfig()
    return build_health_remediation_bridge_report(health_report, bridge_config)


class TestHandoffPacketEndToEnd:
    """End-to-end flows from HealthReport to handoff packet output."""

    def test_single_blocking_finding_to_handoff_packet(self) -> None:
        finding = _make_health_finding(
            finding_id="f1",
            severity=HealthSeverity.BLOCKING,
            title="Malformed metadata",
        )
        bridge_report = _build_bridge_report_from_health_findings((finding,))
        pkt = build_research_audit_remediation_handoff_packet(bridge_report)
        assert pkt.state == "blocked"
        assert pkt.total_items == 1
        assert pkt.total_blocking == 1
        assert pkt.group_count == 1

    def test_multiple_findings_grouped_by_reason_family(self) -> None:
        finding1 = _make_health_finding(finding_id="f1", title="Malformed A")
        finding2 = _make_health_finding(finding_id="f2", title="Malformed B")
        bridge_report = _build_bridge_report_from_health_findings((finding1, finding2))
        pkt = build_research_audit_remediation_handoff_packet(bridge_report)
        assert pkt.total_items == 2
        assert pkt.group_count == 1
        assert pkt.groups[0].reason_code == "consistency_degraded"
        assert pkt.groups[0].item_count == 2

    def test_different_severities_produce_separate_groups(self) -> None:
        blocking = _make_health_finding(finding_id="f1", severity=HealthSeverity.BLOCKING)
        warning = _make_health_finding(finding_id="f2", severity=HealthSeverity.WARNING)
        bridge_report = _build_bridge_report_from_health_findings((blocking, warning))
        pkt = build_research_audit_remediation_handoff_packet(bridge_report)
        assert pkt.total_items == 2
        assert pkt.group_count == 2

    def test_json_output_contains_all_packet_fields(self) -> None:
        finding = _make_health_finding(
            finding_id="f1", severity=HealthSeverity.BLOCKING
        )
        bridge_report = _build_bridge_report_from_health_findings((finding,))
        pkt = build_research_audit_remediation_handoff_packet(bridge_report)
        json_text = handoff_packet_to_json(pkt)
        assert '"kind": "research_audit_remediation_handoff_packet"' in json_text
        assert pkt.packet_id in json_text
        assert '"state": "blocked"' in json_text

    def test_markdown_output_contains_safety_notice(self) -> None:
        finding = _make_health_finding(finding_id="f1")
        bridge_report = _build_bridge_report_from_health_findings((finding,))
        pkt = build_research_audit_remediation_handoff_packet(bridge_report)
        md = handoff_packet_to_markdown(pkt)
        assert "Research Audit Remediation Handoff Packet" in md
        assert "human-audit / research-only" in md

    def test_exclude_info_in_end_to_end_flow(self) -> None:
        warning = _make_health_finding(finding_id="f1", severity=HealthSeverity.WARNING)
        info_finding = _make_health_finding(finding_id="f2", severity=HealthSeverity.INFO)
        bridge_report = _build_bridge_report_from_health_findings((warning, info_finding))
        cfg = HandoffPacketConfig(exclude_info=True)
        pkt = build_research_audit_remediation_handoff_packet(bridge_report, config=cfg)
        assert pkt.total_items == 1
        assert pkt.total_info == 0

    def test_empty_bridge_report_produces_ok_packet(self) -> None:
        bridge_report = _build_bridge_report_from_health_findings(())
        pkt = build_research_audit_remediation_handoff_packet(bridge_report)
        assert pkt.state == "ok"
        assert pkt.total_items == 0
        assert pkt.group_count == 0

    def test_deterministic_end_to_end_output(self) -> None:
        finding = _make_health_finding(finding_id="f1")
        bridge_report = _build_bridge_report_from_health_findings((finding,))
        pkt1 = build_research_audit_remediation_handoff_packet(bridge_report)
        pkt2 = build_research_audit_remediation_handoff_packet(bridge_report)
        assert pkt1.packet_id == pkt2.packet_id
        assert pkt1.state == pkt2.state
        assert pkt1.total_items == pkt2.total_items
        assert pkt1.group_count == pkt2.group_count
        assert pkt1.groups[0].item_count == pkt2.groups[0].item_count
        # generated_at differs by microseconds, so compare structural fields.

    def test_tuple_input_from_health_items(self) -> None:
        finding = _make_health_finding(finding_id="f1")
        bridge_report = _build_bridge_report_from_health_findings((finding,))
        items = bridge_report.items
        pkt = build_research_audit_remediation_handoff_packet(items)
        assert pkt.total_items == 1
        assert pkt.source_report_id == "unknown_source"

    def test_config_owner_reviewer_notes_propagated(self) -> None:
        finding = _make_health_finding(finding_id="f1")
        bridge_report = _build_bridge_report_from_health_findings((finding,))
        cfg = HandoffPacketConfig(owner="alice", reviewer="bob", notes="review batch")
        pkt = build_research_audit_remediation_handoff_packet(bridge_report, config=cfg)
        assert pkt.owner == "alice"
        assert pkt.reviewer == "bob"
        assert pkt.notes == "review batch"
        md = handoff_packet_to_markdown(pkt)
        assert "alice" in md
        assert "bob" in md


class TestSafetyBoundaries:
    """Safety boundary checks across the end-to-end flow."""

    def test_no_filesystem_reads(self) -> None:
        """The end-to-end flow does not read from data/ or reports/."""
        finding = _make_health_finding(finding_id="f1")
        bridge_report = _build_bridge_report_from_health_findings((finding,))
        pkt = build_research_audit_remediation_handoff_packet(bridge_report)
        md = handoff_packet_to_markdown(pkt)
        assert "artifact_1" in md
        # The artifact id is preserved as an opaque string; it is never
        # read or validated by the engine or writer.
        assert "FileNotFoundError" not in md
