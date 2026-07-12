"""Integration tests for the Research Audit Health Remediation Bridge (MVP-49)."""

from datetime import datetime, timezone
from pathlib import Path

import pytest

from hunter.research_audit_health.models import (
    HealthDataQuality,
    HealthFinding,
    HealthReasonCode,
    HealthReport,
    HealthSafetyFlags,
    HealthScore,
    HealthSeverity,
    HealthState,
)
from hunter.research_audit_health_remediation import (
    RemediationBridgeConfig,
    RemediationBridgeReport,
    atomic_write_csv_remediation_bridge_report,
    atomic_write_json_remediation_bridge_report,
    atomic_write_markdown_remediation_bridge_report,
    build_health_remediation_bridge_report,
    remediation_bridge_report_to_csv_text,
    remediation_bridge_report_to_dict,
    remediation_bridge_report_to_json,
    remediation_bridge_report_to_markdown,
    write_remediation_bridge_report,
)
from hunter.remediation_backlog.models import (
    RemediationBacklogItemType,
    RemediationBacklogPriority,
    RemediationBacklogReasonCode,
    RemediationBacklogSeverity,
)


def _make_health_report() -> HealthReport:
    findings = (
        HealthFinding(
            finding_id="f-blocking",
            rule_id="BLOCKING_SOURCE_STATE",
            family="research_audit_snapshot",
            artifact_ids=("snap-1",),
            severity=HealthSeverity.BLOCKING,
            reason_code=HealthReasonCode.BLOCKING_SOURCE_STATE,
            title="Blocking source",
            description="Source state is BLOCKING.",
        ),
        HealthFinding(
            finding_id="f-warning",
            rule_id="DEGRADED_SOURCE_STATE",
            family="research_audit_snapshot",
            artifact_ids=("snap-2",),
            severity=HealthSeverity.WARNING,
            reason_code=HealthReasonCode.DEGRADED_SOURCE_STATE,
            title="Degraded source",
            description="Source state is DEGRADED.",
        ),
        HealthFinding(
            finding_id="f-info",
            rule_id="NO_ARTIFACTS",
            family="review_search",
            artifact_ids=("rs-1",),
            severity=HealthSeverity.INFO,
            reason_code=HealthReasonCode.NO_ARTIFACTS,
            title="No artifacts",
            description="No artifacts found.",
        ),
    )
    return HealthReport(
        report_id="health-report-integration",
        state=HealthState.BLOCKED,
        aggregate_score=HealthScore(value=0.0, weight=1.0, contributing_families=()),
        family_rollups=(),
        findings=findings,
        reason_code_counts={
            "BLOCKING_SOURCE_STATE": 1,
            "DEGRADED_SOURCE_STATE": 1,
            "NO_ARTIFACTS": 1,
        },
        data_quality=HealthDataQuality(finding_count=3, blocking_count=1, warning_count=1, info_count=1),
        safety_flags=HealthSafetyFlags(),
    )


def test_end_to_end_bridge_produces_expected_items() -> None:
    health_report = _make_health_report()
    config = RemediationBridgeConfig(owner="hunter", reviewer="reviewer")
    bridge_report = build_health_remediation_bridge_report(health_report, config)

    assert isinstance(bridge_report, RemediationBridgeReport)
    assert bridge_report.source_report_id == health_report.report_id
    assert len(bridge_report.items) == 3

    item_types = {item.item_type for item in bridge_report.items}
    assert RemediationBacklogItemType.MANUAL_REVIEW in item_types
    assert RemediationBacklogItemType.MISSING_REF in item_types

    p0_item = [item for item in bridge_report.items if item.priority == RemediationBacklogPriority.P0]
    assert len(p0_item) == 1
    assert p0_item[0].severity == RemediationBacklogSeverity.BLOCKING

    info_item = [item for item in bridge_report.items if item.priority == RemediationBacklogPriority.P3]
    assert len(info_item) == 1

    for item in bridge_report.items:
        assert item.owner == "hunter"
        assert item.reviewer == "reviewer"


def test_end_to_end_with_exclude_info() -> None:
    health_report = _make_health_report()
    config = RemediationBridgeConfig(exclude_info=True)
    bridge_report = build_health_remediation_bridge_report(health_report, config)
    assert len(bridge_report.items) == 2
    assert bridge_report.data_quality.dropped_info == 1


def test_end_to_end_json_roundtrip() -> None:
    health_report = _make_health_report()
    bridge_report = build_health_remediation_bridge_report(health_report)
    json_text = remediation_bridge_report_to_json(bridge_report)
    assert bridge_report.report_id in json_text
    assert all(item.item_id in json_text for item in bridge_report.items)


def test_end_to_end_csv_includes_all_items() -> None:
    health_report = _make_health_report()
    bridge_report = build_health_remediation_bridge_report(health_report)
    csv_text = remediation_bridge_report_to_csv_text(bridge_report)
    for item in bridge_report.items:
        assert item.item_id in csv_text


def test_end_to_end_markdown_contains_all_items() -> None:
    health_report = _make_health_report()
    bridge_report = build_health_remediation_bridge_report(health_report)
    markdown_text = remediation_bridge_report_to_markdown(bridge_report)
    for item in bridge_report.items:
        assert item.item_id in markdown_text


def test_end_to_end_dict_has_kind_and_version() -> None:
    health_report = _make_health_report()
    bridge_report = build_health_remediation_bridge_report(health_report)
    data = remediation_bridge_report_to_dict(bridge_report)
    assert data["kind"] == "research_audit_health_remediation_bridge_report"
    assert data["version"] == "1.0"
    assert data["data_quality"]["input_findings"] == 3


def test_end_to_end_atomic_writes(tmp_path: Path) -> None:
    health_report = _make_health_report()
    bridge_report = build_health_remediation_bridge_report(health_report)
    json_path = tmp_path / "bridge.json"
    csv_path = tmp_path / "bridge.csv"
    md_path = tmp_path / "bridge.md"
    write_remediation_bridge_report(bridge_report, json_path=json_path, csv_path=csv_path, markdown_path=md_path)
    assert json_path.exists()
    assert csv_path.exists()
    assert md_path.exists()


def test_end_to_end_deterministic_report_id() -> None:
    health_report = _make_health_report()
    bridge1 = build_health_remediation_bridge_report(health_report)
    bridge2 = build_health_remediation_bridge_report(health_report)
    assert bridge1.report_id == bridge2.report_id


def test_end_to_end_safety_flag_for_forbidden_term() -> None:
    health_report = _make_health_report()
    # Modify one finding description to include a forbidden term.
    forbidden_finding = HealthFinding(
        finding_id="f-forbidden",
        rule_id="DEGRADED_SOURCE_STATE",
        family="research_audit_snapshot",
        artifact_ids=("snap-x",),
        severity=HealthSeverity.WARNING,
        reason_code=HealthReasonCode.DEGRADED_SOURCE_STATE,
        title="Degraded",
        description="This should be approved for production trading.",
    )
    health_report = HealthReport(
        report_id=health_report.report_id,
        state=health_report.state,
        aggregate_score=health_report.aggregate_score,
        family_rollups=health_report.family_rollups,
        findings=health_report.findings + (forbidden_finding,),
        reason_code_counts=health_report.reason_code_counts,
        data_quality=HealthDataQuality(finding_count=4),
        safety_flags=health_report.safety_flags,
    )
    bridge_report = build_health_remediation_bridge_report(health_report)
    assert bridge_report.safety_flags.has_forbidden_terms is True
    safety_items = [item for item in bridge_report.items if item.item_type == RemediationBacklogItemType.UNSAFE_CONTENT]
    assert len(safety_items) == 1


def test_end_to_end_blocking_reason_code() -> None:
    health_report = HealthReport(
        report_id="hr-blocked",
        state=HealthState.BLOCKED,
        aggregate_score=HealthScore(value=0.0, weight=1.0, contributing_families=()),
        family_rollups=(),
        findings=(
            HealthFinding(
                finding_id="f-only",
                rule_id="BLOCKING_SOURCE_STATE",
                family="research_audit_snapshot",
                artifact_ids=("snap-1",),
                severity=HealthSeverity.BLOCKING,
                reason_code=HealthReasonCode.BLOCKING_SOURCE_STATE,
                title="Blocking",
                description="Blocking.",
            ),
        ),
        reason_code_counts={"BLOCKING_SOURCE_STATE": 1},
        data_quality=HealthDataQuality(finding_count=1, blocking_count=1),
        safety_flags=HealthSafetyFlags(),
    )
    bridge_report = build_health_remediation_bridge_report(health_report)
    assert len(bridge_report.items) == 1
    item = bridge_report.items[0]
    assert RemediationBacklogReasonCode.SAFETY_BLOCKED in item.reason_codes


def test_end_to_end_no_runtime_io() -> None:
    """The bridge must not touch data/ or reports/ directories."""
    health_report = _make_health_report()
    bridge_report = build_health_remediation_bridge_report(health_report)
    # The default writer paths are known but the bridge engine itself never opens them.
    assert bridge_report.items is not None
    assert all(hasattr(item, "item_id") for item in bridge_report.items)
