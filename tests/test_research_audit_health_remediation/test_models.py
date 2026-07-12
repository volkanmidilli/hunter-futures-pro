"""Tests for the research_audit_health_remediation models module."""

import pytest

from hunter.research_audit_health_remediation.models import (
    RemediationBridgeConfig,
    RemediationBridgeDataQuality,
    RemediationBridgeError,
    RemediationBridgeReport,
)
from hunter.remediation_backlog.models import RemediationBacklogSafetyFlags


def test_remediation_bridge_config_defaults() -> None:
    config = RemediationBridgeConfig()
    assert config.strict is False
    assert config.owner is None
    assert config.reviewer is None
    assert config.exclude_info is False
    assert dict(config.severity_to_priority) == {}
    assert dict(config.reason_to_item_type) == {}


def test_remediation_bridge_config_with_owner_reviewer() -> None:
    config = RemediationBridgeConfig(owner="alice", reviewer="bob")
    assert config.owner == "alice"
    assert config.reviewer == "bob"


def test_remediation_bridge_config_strips_whitespace() -> None:
    config = RemediationBridgeConfig(owner="  alice  ", reviewer="  bob  ")
    assert config.owner == "alice"
    assert config.reviewer == "bob"


def test_remediation_bridge_config_invalid_owner() -> None:
    with pytest.raises(ValueError):
        RemediationBridgeConfig(owner="")
    with pytest.raises(ValueError):
        RemediationBridgeConfig(owner="   ")


def test_remediation_bridge_config_invalid_reviewer() -> None:
    with pytest.raises(ValueError):
        RemediationBridgeConfig(reviewer="")
    with pytest.raises(ValueError):
        RemediationBridgeConfig(reviewer="   ")


def test_remediation_bridge_config_overrides() -> None:
    config = RemediationBridgeConfig(
        severity_to_priority={"BLOCKING": "P2"},
        reason_to_item_type={"NO_ARTIFACTS": "MISSING_REF"},
    )
    assert config.severity_to_priority["BLOCKING"] == "P2"
    assert config.reason_to_item_type["NO_ARTIFACTS"] == "MISSING_REF"


def test_remediation_bridge_config_override_values_must_be_strings() -> None:
    with pytest.raises(ValueError):
        RemediationBridgeConfig(severity_to_priority={"BLOCKING": 1})
    with pytest.raises(ValueError):
        RemediationBridgeConfig(reason_to_item_type={"NO_ARTIFACTS": 1})


def test_remediation_bridge_config_frozen() -> None:
    config = RemediationBridgeConfig()
    with pytest.raises(AttributeError):
        config.strict = True  # type: ignore[misc]


def test_remediation_bridge_data_quality_defaults() -> None:
    dq = RemediationBridgeDataQuality()
    assert dq.input_findings == 0
    assert dq.produced_items == 0
    assert dq.dropped_info == 0
    assert dq.duplicates_collapsed == 0
    assert dq.safety_flagged_items == 0


def test_remediation_bridge_data_quality_validation() -> None:
    with pytest.raises(ValueError):
        RemediationBridgeDataQuality(input_findings=-1)
    with pytest.raises(ValueError):
        RemediationBridgeDataQuality(produced_items="bad")  # type: ignore[arg-type]


def test_remediation_bridge_report_defaults() -> None:
    report = RemediationBridgeReport(
        report_id="r-1",
        source_report_id="hr-1",
        generated_at="2024-01-01T00:00:00+00:00",
        items=(),
        data_quality=RemediationBridgeDataQuality(),
        safety_flags=RemediationBacklogSafetyFlags(),
    )
    assert report.report_id == "r-1"
    assert report.source_report_id == "hr-1"
    assert report.items == ()


def test_remediation_bridge_report_validation() -> None:
    with pytest.raises(ValueError):
        RemediationBridgeReport(
            report_id="",
            source_report_id="hr-1",
            generated_at="2024-01-01T00:00:00+00:00",
            items=(),
            data_quality=RemediationBridgeDataQuality(),
            safety_flags=RemediationBacklogSafetyFlags(),
        )
    with pytest.raises(ValueError):
        RemediationBridgeReport(
            report_id="r-1",
            source_report_id="",
            generated_at="2024-01-01T00:00:00+00:00",
            items=(),
            data_quality=RemediationBridgeDataQuality(),
            safety_flags=RemediationBacklogSafetyFlags(),
        )
    with pytest.raises(ValueError):
        RemediationBridgeReport(
            report_id="r-1",
            source_report_id="hr-1",
            generated_at="",
            items=(),
            data_quality=RemediationBridgeDataQuality(),
            safety_flags=RemediationBacklogSafetyFlags(),
        )
    with pytest.raises(ValueError):
        RemediationBridgeReport(
            report_id="r-1",
            source_report_id="hr-1",
            generated_at="2024-01-01T00:00:00+00:00",
            items=(),
            data_quality={},  # type: ignore[arg-type]
            safety_flags=RemediationBacklogSafetyFlags(),
        )
    with pytest.raises(ValueError):
        RemediationBridgeReport(
            report_id="r-1",
            source_report_id="hr-1",
            generated_at="2024-01-01T00:00:00+00:00",
            items=(),
            data_quality=RemediationBridgeDataQuality(),
            safety_flags={},  # type: ignore[arg-type]
        )


def test_remediation_bridge_report_items_must_be_tuple() -> None:
    with pytest.raises(ValueError):
        RemediationBridgeReport(
            report_id="r-1",
            source_report_id="hr-1",
            generated_at="2024-01-01T00:00:00+00:00",
            items=[],  # type: ignore[arg-type]
            data_quality=RemediationBridgeDataQuality(),
            safety_flags=RemediationBacklogSafetyFlags(),
        )
