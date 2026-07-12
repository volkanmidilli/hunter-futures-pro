"""Tests for the research_audit_health_remediation writer module."""

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
    build_health_remediation_bridge_report,
    remediation_bridge_report_to_csv_text,
    remediation_bridge_report_to_dict,
    remediation_bridge_report_to_json,
    remediation_bridge_report_to_markdown,
    atomic_write_json_remediation_bridge_report,
    atomic_write_csv_remediation_bridge_report,
    atomic_write_markdown_remediation_bridge_report,
    write_remediation_bridge_report,
)


def _sample_report() -> RemediationBridgeReport:
    finding = HealthFinding(
        finding_id="f-1",
        rule_id="BLOCKING_SOURCE_STATE",
        family="research_audit_snapshot",
        artifact_ids=("snap-1",),
        severity=HealthSeverity.BLOCKING,
        reason_code=HealthReasonCode.BLOCKING_SOURCE_STATE,
        title="Blocking",
        description="Source is blocking.",
    )
    health_report = HealthReport(
        report_id="health-report-1",
        state=HealthState.BLOCKED,
        aggregate_score=HealthScore(value=0.0, weight=1.0, contributing_families=()),
        family_rollups=(),
        findings=(finding,),
        reason_code_counts={"BLOCKING_SOURCE_STATE": 1},
        data_quality=HealthDataQuality(finding_count=1, blocking_count=1),
        safety_flags=HealthSafetyFlags(),
    )
    return build_health_remediation_bridge_report(health_report, RemediationBridgeConfig(owner="alice"))


def test_report_to_dict_structure() -> None:
    report = _sample_report()
    data = remediation_bridge_report_to_dict(report)
    assert data["kind"] == "research_audit_health_remediation_bridge_report"
    assert data["version"] == "1.0"
    assert data["report_id"] == report.report_id
    assert data["source_report_id"] == report.source_report_id
    assert data["generated_at"] == report.generated_at
    assert "safety_notice" in data
    assert "priority_notice" in data
    assert "items" in data
    assert "data_quality" in data
    assert "safety_flags" in data


def test_report_to_json_is_valid_json() -> None:
    report = _sample_report()
    text = remediation_bridge_report_to_json(report)
    import json
    data = json.loads(text)
    assert data["report_id"] == report.report_id
    assert len(data["items"]) == 1


def test_report_to_csv_text_has_header_and_row() -> None:
    report = _sample_report()
    text = remediation_bridge_report_to_csv_text(report)
    lines = text.strip().split("\n")
    assert len(lines) == 2
    assert lines[0].startswith("report_id,source_report_id")
    assert "health-report-1" in lines[1]
    assert "alice" in lines[1]


def test_report_to_csv_empty_items() -> None:
    from hunter.research_audit_health_remediation.models import RemediationBridgeDataQuality
    from hunter.remediation_backlog.models import RemediationBacklogSafetyFlags
    empty_report = RemediationBridgeReport(
        report_id="r-empty",
        source_report_id="hr-empty",
        generated_at="2024-01-01T00:00:00+00:00",
        items=(),
        data_quality=RemediationBridgeDataQuality(),
        safety_flags=RemediationBacklogSafetyFlags(),
    )
    text = remediation_bridge_report_to_csv_text(empty_report)
    lines = text.strip().split("\n")
    assert len(lines) == 1


def test_report_to_markdown_contains_safety_notice() -> None:
    report = _sample_report()
    text = remediation_bridge_report_to_markdown(report)
    assert "Research Audit Health Remediation Bridge Report" in text
    assert "human-audit" in text
    assert "not an approval" in text


def test_report_to_markdown_contains_items_table() -> None:
    report = _sample_report()
    text = remediation_bridge_report_to_markdown(report)
    assert "## Backlog Items" in text
    assert "item_id" in text


def test_atomic_write_json(tmp_path: Path) -> None:
    report = _sample_report()
    path = tmp_path / "bridge.json"
    result = atomic_write_json_remediation_bridge_report(report, path)
    assert result == path
    assert path.exists()
    assert "report_id" in path.read_text()


def test_atomic_write_csv(tmp_path: Path) -> None:
    report = _sample_report()
    path = tmp_path / "bridge.csv"
    result = atomic_write_csv_remediation_bridge_report(report, path)
    assert result == path
    assert path.exists()
    assert "health-report-1" in path.read_text()


def test_atomic_write_markdown(tmp_path: Path) -> None:
    report = _sample_report()
    path = tmp_path / "bridge.md"
    result = atomic_write_markdown_remediation_bridge_report(report, path)
    assert result == path
    assert path.exists()
    assert "Backlog Items" in path.read_text()


def test_write_remediation_bridge_report_writes_all_three(tmp_path: Path) -> None:
    report = _sample_report()
    json_path = tmp_path / "bridge.json"
    csv_path = tmp_path / "bridge.csv"
    md_path = tmp_path / "bridge.md"
    write_remediation_bridge_report(report, json_path=json_path, csv_path=csv_path, markdown_path=md_path)
    assert json_path.exists()
    assert csv_path.exists()
    assert md_path.exists()


def test_default_paths_are_under_bridge_directories() -> None:
    from hunter.research_audit_health_remediation.writer import DEFAULT_JSON_PATH, DEFAULT_CSV_PATH, DEFAULT_MD_PATH
    assert "research_audit_health_remediation" in str(DEFAULT_JSON_PATH)
    assert "research_audit_health_remediation" in str(DEFAULT_CSV_PATH)
    assert "research_audit_health_remediation" in str(DEFAULT_MD_PATH)
