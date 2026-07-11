"""Tests for hunter.human_review_audit_bundle_export models."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from hunter.human_review_audit_bundle import (
    HumanReviewAuditBundleReport,
    HumanReviewAuditBundleState,
)
from hunter.human_review_audit_bundle_export import (
    HumanReviewAuditBundleExportConfig,
    HumanReviewAuditBundleExportInput,
    HumanReviewAuditBundleExportIssue,
    HumanReviewAuditBundleExportManifest,
    HumanReviewAuditBundleExportPlan,
    HumanReviewAuditBundleExportReasonCode,
    HumanReviewAuditBundleExportSafetyFlags,
    HumanReviewAuditBundleExportSeverity,
    HumanReviewAuditBundleExportState,
    SAFETY_NOTICE,
)


NOW = datetime(2026, 7, 11, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def now() -> datetime:
    return NOW


@pytest.fixture
def bundle_report(now: datetime) -> HumanReviewAuditBundleReport:
    return HumanReviewAuditBundleReport(
        bundle_id="bundle-abc123",
        report_id="bundle-report-abc123",
        generated_at=now,
        state=HumanReviewAuditBundleState.OK,
        project_version="0.43.0-dev",
    )


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def test_config_defaults() -> None:
    config = HumanReviewAuditBundleExportConfig()
    assert config.strict is False
    assert config.overwrite is False
    assert config.format == "json"
    assert config.safety_scan is True
    assert config.verify_hash is True
    assert config.dry_run is False


def test_config_invalid_format_stored_not_rejected_by_config() -> None:
    # The planner enforces the format allowlist; the model stores the value.
    config = HumanReviewAuditBundleExportConfig(format="csv")
    assert config.format == "csv"


def test_config_non_bool_strict() -> None:
    with pytest.raises(TypeError, match="strict must be a bool"):
        HumanReviewAuditBundleExportConfig(strict="yes")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------


def test_input_accepts_path_strings(now: datetime, bundle_report: HumanReviewAuditBundleReport) -> None:
    input_obj = HumanReviewAuditBundleExportInput(
        bundle_report=bundle_report,
        output_dir="/tmp/output",
        tmp_path="/tmp/tmp",
        generated_at=now,
    )
    assert isinstance(input_obj.output_dir, Path)
    assert isinstance(input_obj.tmp_path, Path)
    assert input_obj.output_dir == Path("/tmp/output")
    assert input_obj.tmp_path == Path("/tmp/tmp")


def test_input_rejects_invalid_bundle_report() -> None:
    with pytest.raises(TypeError, match="bundle_report must be a HumanReviewAuditBundleReport"):
        HumanReviewAuditBundleExportInput(
            bundle_report="not-a-report",  # type: ignore[arg-type]
            output_dir="/tmp/output",
            tmp_path="/tmp/tmp",
        )


def test_input_rejects_naive_datetime(now: datetime, bundle_report: HumanReviewAuditBundleReport) -> None:
    naive = now.replace(tzinfo=None)
    with pytest.raises(ValueError, match="generated_at must be timezone-aware"):
        HumanReviewAuditBundleExportInput(
            bundle_report=bundle_report,
            output_dir="/tmp/output",
            tmp_path="/tmp/tmp",
            generated_at=naive,
        )


# ---------------------------------------------------------------------------
# Issue / SafetyFlags
# ---------------------------------------------------------------------------


def test_issue_validation() -> None:
    issue = HumanReviewAuditBundleExportIssue(
        issue_id="i-1",
        issue_type="test",
        severity=HumanReviewAuditBundleExportSeverity.BLOCKING.value,
        reason_codes=("test",),
        source="safety_scan",
        title="Test issue",
        description="A test issue.",
        generated_at=NOW,
    )
    assert issue.issue_id == "i-1"
    assert issue.severity == "blocking"


def test_safety_flags_defaults() -> None:
    flags = HumanReviewAuditBundleExportSafetyFlags()
    assert flags.is_safe is True
    assert flags.audit_only is True
    assert flags.path_safe is True
    assert flags.hash_verified is True


def test_safety_flags_non_bool() -> None:
    with pytest.raises(TypeError, match="path_safe must be a bool"):
        HumanReviewAuditBundleExportSafetyFlags(path_safe="yes")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Plan / Manifest
# ---------------------------------------------------------------------------


def test_plan_defaults() -> None:
    plan = HumanReviewAuditBundleExportPlan()
    assert plan.state == HumanReviewAuditBundleExportState.PLANNED
    assert plan.content_length == 0


def test_plan_validation_invalid_state() -> None:
    with pytest.raises(TypeError, match="state must be a HumanReviewAuditBundleExportState"):
        HumanReviewAuditBundleExportPlan(state="planned")  # type: ignore[arg-type]


def test_plan_validation_negative_content_length() -> None:
    with pytest.raises(ValueError, match="content_length must be non-negative"):
        HumanReviewAuditBundleExportPlan(content_length=-1)


def test_manifest_defaults() -> None:
    manifest = HumanReviewAuditBundleExportManifest()
    assert manifest.state == HumanReviewAuditBundleExportState.PLANNED


# ---------------------------------------------------------------------------
# Safety notice
# ---------------------------------------------------------------------------


def test_safety_notice_present() -> None:
    assert "audit-only" in SAFETY_NOTICE.lower()
    assert "does not imply" in SAFETY_NOTICE.lower()
    assert "production readiness" in SAFETY_NOTICE.lower()
