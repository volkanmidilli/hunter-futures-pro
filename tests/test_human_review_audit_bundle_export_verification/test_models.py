"""Tests for hunter.human_review_audit_bundle_export_verification models."""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from hunter.human_review_audit_bundle_export.models import (
    HumanReviewAuditBundleExportManifest,
    HumanReviewAuditBundleExportSafetyFlags,
    HumanReviewAuditBundleExportState,
)
from hunter.human_review_audit_bundle_export_verification.models import (
    HUMAN_REVIEW_AUDIT_BUNDLE_EXPORT_VERIFICATION_VERSION,
    HumanReviewAuditBundleExportVerificationConfig,
    HumanReviewAuditBundleExportVerificationDataQuality,
    HumanReviewAuditBundleExportVerificationInput,
    HumanReviewAuditBundleExportVerificationIssue,
    HumanReviewAuditBundleExportVerificationReasonCode,
    HumanReviewAuditBundleExportVerificationReport,
    HumanReviewAuditBundleExportVerificationSafetyFlags,
    HumanReviewAuditBundleExportVerificationSeverity,
    HumanReviewAuditBundleExportVerificationState,
)


class TestVerificationEnums:
    def test_state_values(self) -> None:
        assert HumanReviewAuditBundleExportVerificationState.VERIFIED.value == "verified"
        assert HumanReviewAuditBundleExportVerificationState.NOT_APPLICABLE.value == "not_applicable"
        assert HumanReviewAuditBundleExportVerificationState.BLOCKED.value == "blocked"
        assert HumanReviewAuditBundleExportVerificationState.INVALID.value == "invalid"
        assert HumanReviewAuditBundleExportVerificationState.DEGRADED.value == "degraded"

    def test_severity_values(self) -> None:
        assert HumanReviewAuditBundleExportVerificationSeverity.BLOCKING.value == "blocking"
        assert HumanReviewAuditBundleExportVerificationSeverity.ADVISORY.value == "advisory"
        assert HumanReviewAuditBundleExportVerificationSeverity.INFO.value == "info"

    def test_reason_codes(self) -> None:
        assert HumanReviewAuditBundleExportVerificationReasonCode.OK.value == "ok"
        assert HumanReviewAuditBundleExportVerificationReasonCode.HASH_MISMATCH.value == "hash_mismatch"
        assert HumanReviewAuditBundleExportVerificationReasonCode.LENGTH_MISMATCH.value == "length_mismatch"
        assert HumanReviewAuditBundleExportVerificationReasonCode.FORBIDDEN_TERM_PRESENT.value == "forbidden_term_present"

    def test_version_present(self) -> None:
        assert HUMAN_REVIEW_AUDIT_BUNDLE_EXPORT_VERIFICATION_VERSION == "0.45.0-dev"


class TestVerificationConfig:
    def test_defaults(self) -> None:
        cfg = HumanReviewAuditBundleExportVerificationConfig()
        assert cfg.strict is False
        assert cfg.require_safety_notice is True
        assert cfg.verify_text_hash is False
        assert cfg.allow_not_applicable is True

    def test_strict_requires_bool(self) -> None:
        with pytest.raises(TypeError):
            HumanReviewAuditBundleExportVerificationConfig(strict="true")  # type: ignore[arg-type]


class TestVerificationDataQuality:
    def test_defaults_zero(self) -> None:
        dq = HumanReviewAuditBundleExportVerificationDataQuality()
        assert dq.checks_performed == 0
        assert dq.hash_mismatch_count == 0
        assert dq.length_mismatch_count == 0
        assert dq.state_not_verifiable_count == 0
        assert dq.missing_safety_notice_count == 0
        assert dq.forbidden_term_count == 0
        assert dq.blocking_issues == 0
        assert dq.advisory_issues == 0
        assert dq.info_findings == 0

    def test_non_negative_validation(self) -> None:
        with pytest.raises(TypeError):
            HumanReviewAuditBundleExportVerificationDataQuality(checks_performed=-1)


class TestVerificationSafetyFlags:
    def test_defaults_safe(self) -> None:
        flags = HumanReviewAuditBundleExportVerificationSafetyFlags()
        assert flags.is_safe is True
        assert flags.audit_only is True
        assert flags.no_executable_actions is True
        assert flags.no_trading_instructions is True
        assert flags.no_approval_claims is True
        assert flags.references_opaque is True
        assert flags.no_network is True
        assert flags.no_server is True
        assert flags.hash_verified is False
        assert flags.length_verified is False
        assert flags.state_verifiable is False
        assert flags.safety_notice_present is False

    def test_bool_validation(self) -> None:
        with pytest.raises(TypeError):
            HumanReviewAuditBundleExportVerificationSafetyFlags(hash_verified="true")  # type: ignore[arg-type]


class TestVerificationIssue:
    def test_issue_creation(self) -> None:
        issue = HumanReviewAuditBundleExportVerificationIssue(
            issue_id="issue-1",
            issue_type="hash_mismatch",
            severity=HumanReviewAuditBundleExportVerificationSeverity.BLOCKING.value,
            reason_codes=("hash_mismatch",),
            source="hash_verification",
            title="Hash mismatch",
            description="Expected ABC, got DEF.",
        )
        assert issue.issue_id == "issue-1"
        assert issue.issue_type == "hash_mismatch"
        assert issue.reason_codes == ("hash_mismatch",)


class TestVerificationInput:
    def test_input_requires_manifest(self) -> None:
        with pytest.raises(TypeError):
            HumanReviewAuditBundleExportVerificationInput(manifest="not-a-manifest")  # type: ignore[arg-type]

    def test_input_requires_bytes(self) -> None:
        manifest = HumanReviewAuditBundleExportManifest()
        with pytest.raises(TypeError):
            HumanReviewAuditBundleExportVerificationInput(
                manifest=manifest,
                artifact_bytes="not-bytes",  # type: ignore[arg-type]
            )

    def test_input_accepts_defaults(self) -> None:
        manifest = HumanReviewAuditBundleExportManifest()
        inp = HumanReviewAuditBundleExportVerificationInput(manifest=manifest)
        assert inp.artifact_bytes == b""
        assert inp.expected_format == ""
        assert isinstance(inp.config, HumanReviewAuditBundleExportVerificationConfig)


class TestVerificationReport:
    def test_default_state_invalid(self) -> None:
        report = HumanReviewAuditBundleExportVerificationReport()
        assert report.state == HumanReviewAuditBundleExportVerificationState.INVALID

    def test_report_metadata_mapping(self) -> None:
        manifest = HumanReviewAuditBundleExportManifest()
        report = HumanReviewAuditBundleExportVerificationReport(
            manifest_id=manifest.manifest_id,
            metadata={"key": "value"},
        )
        assert isinstance(report.metadata, Mapping)
        assert report.metadata["key"] == "value"
