"""Tests for hunter.human_review_audit_bundle_export_verification engine."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

import pytest

from hunter.human_review_audit_bundle_export.models import (
    HumanReviewAuditBundleExportManifest,
    HumanReviewAuditBundleExportSafetyFlags,
    HumanReviewAuditBundleExportState,
)
from hunter.human_review_audit_bundle_export_verification.engine import (
    ALLOWED_FORMATS,
    FORBIDDEN_VERIFICATION_TERMS,
    _build_report_id,
    _build_verification_id,
    _scan_forbidden_terms,
    verify_human_review_audit_bundle_export,
)
from hunter.human_review_audit_bundle_export_verification.models import (
    HumanReviewAuditBundleExportVerificationConfig,
    HumanReviewAuditBundleExportVerificationInput,
    HumanReviewAuditBundleExportVerificationReasonCode,
    HumanReviewAuditBundleExportVerificationReport,
    HumanReviewAuditBundleExportVerificationSeverity,
    HumanReviewAuditBundleExportVerificationState,
)


def _written_manifest(
    artifact_bytes: bytes,
    state: HumanReviewAuditBundleExportState = HumanReviewAuditBundleExportState.WRITTEN,
    **overrides: Any,
) -> HumanReviewAuditBundleExportManifest:
    """Build a populated manifest for the given artifact bytes."""
    content_hash = sha256(artifact_bytes).hexdigest()
    content_length = len(artifact_bytes)
    defaults = {
        "manifest_id": "manifest-001",
        "report_id": "report-001",
        "bundle_report_id": "bundle-report-001",
        "filename": "artifact.json",
        "output_path": "reports/artifact.json",
        "format": "json",
        "content_hash": content_hash,
        "content_length": content_length,
        "state": state,
        "safety_flags": HumanReviewAuditBundleExportSafetyFlags(
            hash_verified=(state == HumanReviewAuditBundleExportState.WRITTEN),
        ),
    }
    defaults.update(overrides)
    return HumanReviewAuditBundleExportManifest(**defaults)


def _build_artifact_bytes() -> bytes:
    from hunter.human_review_audit_bundle_export.models import SAFETY_NOTICE
    body = {
        "metadata": {"id": "bundle-1"},
        "safety_notice": SAFETY_NOTICE,
        "findings": [],
    }
    return dict_to_json_bytes(body)


def dict_to_json_bytes(data: dict[str, Any]) -> bytes:
    from json import dumps
    return dumps(data, indent=2, sort_keys=True).encode("utf-8")


class TestVerifySuccessful:
    def test_written_matching_bytes_returns_verified(self) -> None:
        artifact_bytes = _build_artifact_bytes()
        manifest = _written_manifest(artifact_bytes)
        inp = HumanReviewAuditBundleExportVerificationInput(
            manifest=manifest,
            artifact_bytes=artifact_bytes,
        )
        report = verify_human_review_audit_bundle_export(inp)
        assert report.state == HumanReviewAuditBundleExportVerificationState.VERIFIED
        assert report.safety_flags.hash_verified is True
        assert report.safety_flags.length_verified is True
        assert report.safety_flags.safety_notice_present is True
        assert HumanReviewAuditBundleExportVerificationReasonCode.OK in report.reason_codes
        assert report.data_quality.checks_performed == 3
        assert report.data_quality.blocking_issues == 0

    def test_hash_verified_false_in_manifest_requires_explicit_verification(self) -> None:
        artifact_bytes = _build_artifact_bytes()
        manifest = _written_manifest(
            artifact_bytes,
            safety_flags=HumanReviewAuditBundleExportSafetyFlags(hash_verified=False),
        )
        inp = HumanReviewAuditBundleExportVerificationInput(
            manifest=manifest,
            artifact_bytes=artifact_bytes,
        )
        report = verify_human_review_audit_bundle_export(inp)
        assert report.state == HumanReviewAuditBundleExportVerificationState.VERIFIED
        assert report.safety_flags.hash_verified is True


class TestHashMismatch:
    def test_hash_mismatch_fail_closed(self) -> None:
        artifact_bytes = _build_artifact_bytes()
        manifest = _written_manifest(artifact_bytes)
        corrupted = bytearray(artifact_bytes)
        corrupted[0] ^= 0xFF  # flip a single byte so only hash changes
        inp = HumanReviewAuditBundleExportVerificationInput(
            manifest=manifest,
            artifact_bytes=bytes(corrupted),
        )
        report = verify_human_review_audit_bundle_export(inp)
        assert report.state == HumanReviewAuditBundleExportVerificationState.BLOCKED
        assert report.data_quality.hash_mismatch_count == 1
        assert report.data_quality.length_mismatch_count == 0
        assert any(
            issue.issue_type == "hash_mismatch"
            for issue in report.issues
        )


class TestLengthMismatch:
    def test_length_mismatch_fail_closed(self) -> None:
        artifact_bytes = _build_artifact_bytes()
        manifest = _written_manifest(artifact_bytes)
        truncated = artifact_bytes[:-1]
        inp = HumanReviewAuditBundleExportVerificationInput(
            manifest=manifest,
            artifact_bytes=truncated,
        )
        report = verify_human_review_audit_bundle_export(inp)
        assert report.state == HumanReviewAuditBundleExportVerificationState.BLOCKED
        assert report.data_quality.length_mismatch_count == 1


class TestMissingArtifactBytes:
    def test_missing_bytes_for_written_fail_closed(self) -> None:
        artifact_bytes = _build_artifact_bytes()
        manifest = _written_manifest(artifact_bytes)
        inp = HumanReviewAuditBundleExportVerificationInput(
            manifest=manifest,
            artifact_bytes=b"",
        )
        report = verify_human_review_audit_bundle_export(inp)
        assert report.state == HumanReviewAuditBundleExportVerificationState.BLOCKED
        assert report.data_quality.length_mismatch_count == 1
        assert report.data_quality.hash_mismatch_count == 1

    def test_no_artifact_not_applicable_when_configured(self) -> None:
        manifest = HumanReviewAuditBundleExportManifest(
            manifest_id="manifest-002",
            report_id="report-002",
            bundle_report_id="bundle-report-002",
            state=HumanReviewAuditBundleExportState.NOT_APPLICABLE,
        )
        inp = HumanReviewAuditBundleExportVerificationInput(
            manifest=manifest,
            artifact_bytes=b"",
            config=HumanReviewAuditBundleExportVerificationConfig(allow_not_applicable=True),
        )
        report = verify_human_review_audit_bundle_export(inp)
        assert report.state == HumanReviewAuditBundleExportVerificationState.NOT_APPLICABLE


class TestStateSemantics:
    def test_planned_not_blindly_verified(self) -> None:
        manifest = HumanReviewAuditBundleExportManifest(
            manifest_id="manifest-003",
            report_id="report-003",
            bundle_report_id="bundle-report-003",
            state=HumanReviewAuditBundleExportState.PLANNED,
        )
        inp = HumanReviewAuditBundleExportVerificationInput(
            manifest=manifest,
            artifact_bytes=b"",
            config=HumanReviewAuditBundleExportVerificationConfig(allow_not_applicable=True),
        )
        report = verify_human_review_audit_bundle_export(inp)
        assert report.state == HumanReviewAuditBundleExportVerificationState.NOT_APPLICABLE

    def test_planned_fail_closed_when_not_applicable_disabled(self) -> None:
        manifest = HumanReviewAuditBundleExportManifest(
            manifest_id="manifest-004",
            report_id="report-004",
            bundle_report_id="bundle-report-004",
            state=HumanReviewAuditBundleExportState.PLANNED,
        )
        inp = HumanReviewAuditBundleExportVerificationInput(
            manifest=manifest,
            artifact_bytes=b"",
            config=HumanReviewAuditBundleExportVerificationConfig(allow_not_applicable=False),
        )
        report = verify_human_review_audit_bundle_export(inp)
        assert report.state == HumanReviewAuditBundleExportVerificationState.BLOCKED

    def test_blocked_manifest_not_verified(self) -> None:
        manifest = HumanReviewAuditBundleExportManifest(
            manifest_id="manifest-005",
            report_id="report-005",
            bundle_report_id="bundle-report-005",
            state=HumanReviewAuditBundleExportState.BLOCKED,
        )
        inp = HumanReviewAuditBundleExportVerificationInput(
            manifest=manifest,
            artifact_bytes=b"anything",
        )
        report = verify_human_review_audit_bundle_export(inp)
        assert report.state == HumanReviewAuditBundleExportVerificationState.BLOCKED
        assert HumanReviewAuditBundleExportVerificationReasonCode.UPSTREAM_BLOCKED in report.reason_codes

    def test_not_applicable_blocked_when_disallowed(self) -> None:
        manifest = HumanReviewAuditBundleExportManifest(
            manifest_id="manifest-006",
            report_id="report-006",
            bundle_report_id="bundle-report-006",
            state=HumanReviewAuditBundleExportState.NOT_APPLICABLE,
        )
        inp = HumanReviewAuditBundleExportVerificationInput(
            manifest=manifest,
            artifact_bytes=b"",
            config=HumanReviewAuditBundleExportVerificationConfig(allow_not_applicable=False),
        )
        report = verify_human_review_audit_bundle_export(inp)
        assert report.state == HumanReviewAuditBundleExportVerificationState.BLOCKED


class TestFormatAndUnsupported:
    def test_unsupported_format_strict_fail_closed(self) -> None:
        artifact_bytes = _build_artifact_bytes()
        manifest = _written_manifest(artifact_bytes)
        inp = HumanReviewAuditBundleExportVerificationInput(
            manifest=manifest,
            artifact_bytes=artifact_bytes,
            expected_format="xml",
            config=HumanReviewAuditBundleExportVerificationConfig(strict=True),
        )
        report = verify_human_review_audit_bundle_export(inp)
        assert report.state == HumanReviewAuditBundleExportVerificationState.BLOCKED
        assert HumanReviewAuditBundleExportVerificationReasonCode.UNSUPPORTED_FORMAT in report.reason_codes

    def test_unsupported_format_advisory_when_not_strict(self) -> None:
        artifact_bytes = _build_artifact_bytes()
        manifest = _written_manifest(artifact_bytes)
        inp = HumanReviewAuditBundleExportVerificationInput(
            manifest=manifest,
            artifact_bytes=artifact_bytes,
            expected_format="xml",
            config=HumanReviewAuditBundleExportVerificationConfig(strict=False),
        )
        report = verify_human_review_audit_bundle_export(inp)
        assert report.state == HumanReviewAuditBundleExportVerificationState.DEGRADED
        assert HumanReviewAuditBundleExportVerificationReasonCode.UNSUPPORTED_FORMAT in report.reason_codes

    def test_expected_format_matches_manifest(self) -> None:
        artifact_bytes = _build_artifact_bytes()
        manifest = _written_manifest(artifact_bytes, format="json")
        inp = HumanReviewAuditBundleExportVerificationInput(
            manifest=manifest,
            artifact_bytes=artifact_bytes,
            expected_format="json",
        )
        report = verify_human_review_audit_bundle_export(inp)
        assert report.state == HumanReviewAuditBundleExportVerificationState.VERIFIED


class TestDeterminism:
    def test_report_id_is_deterministic(self) -> None:
        artifact_bytes = _build_artifact_bytes()
        manifest = _written_manifest(artifact_bytes)
        inp = HumanReviewAuditBundleExportVerificationInput(
            manifest=manifest,
            artifact_bytes=artifact_bytes,
        )
        report1 = verify_human_review_audit_bundle_export(inp)
        report2 = verify_human_review_audit_bundle_export(inp)
        assert report1.report_id == report2.report_id
        assert report1.verification_id == report2.verification_id
        assert report1.issues == report2.issues

    def test_id_changes_with_state(self) -> None:
        artifact_bytes = _build_artifact_bytes()
        manifest = _written_manifest(artifact_bytes)
        generated_at = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        inp_ok = HumanReviewAuditBundleExportVerificationInput(
            manifest=manifest,
            artifact_bytes=artifact_bytes,
            generated_at=generated_at,
        )
        report_ok = verify_human_review_audit_bundle_export(inp_ok)
        report_id = _build_report_id(
            manifest.manifest_id,
            manifest.bundle_report_id,
            manifest.content_hash,
            manifest.content_length,
            generated_at,
        )
        assert report_ok.report_id == report_id
        assert report_ok.state == HumanReviewAuditBundleExportVerificationState.VERIFIED
        corrupted_inp = HumanReviewAuditBundleExportVerificationInput(
            manifest=manifest,
            artifact_bytes=artifact_bytes + b"x",
            generated_at=generated_at,
        )
        report_bad = verify_human_review_audit_bundle_export(corrupted_inp)
        assert report_bad.report_id == report_id
        assert report_bad.verification_id != report_ok.verification_id
        assert report_bad.state == HumanReviewAuditBundleExportVerificationState.BLOCKED

    def test_issue_order_stable(self) -> None:
        artifact_bytes = _build_artifact_bytes()
        manifest = _written_manifest(artifact_bytes)
        corrupted_inp = HumanReviewAuditBundleExportVerificationInput(
            manifest=manifest,
            artifact_bytes=artifact_bytes + b"x",
        )
        report1 = verify_human_review_audit_bundle_export(corrupted_inp)
        report2 = verify_human_review_audit_bundle_export(corrupted_inp)
        assert [i.issue_id for i in report1.issues] == [i.issue_id for i in report2.issues]


class TestDataQuality:
    def test_data_quality_counters(self) -> None:
        artifact_bytes = _build_artifact_bytes()
        manifest = _written_manifest(artifact_bytes)
        corrupted_inp = HumanReviewAuditBundleExportVerificationInput(
            manifest=manifest,
            artifact_bytes=artifact_bytes + b"x",
        )
        report = verify_human_review_audit_bundle_export(corrupted_inp)
        assert report.data_quality.hash_mismatch_count == 1
        assert report.data_quality.length_mismatch_count == 1
        assert report.data_quality.blocking_issues >= 2
        assert report.data_quality.checks_performed == 1  # safety notice check still passed

    def test_verified_data_quality(self) -> None:
        artifact_bytes = _build_artifact_bytes()
        manifest = _written_manifest(artifact_bytes)
        inp = HumanReviewAuditBundleExportVerificationInput(
            manifest=manifest,
            artifact_bytes=artifact_bytes,
        )
        report = verify_human_review_audit_bundle_export(inp)
        assert report.data_quality.checks_performed == 3
        assert report.data_quality.blocking_issues == 0
        assert report.data_quality.advisory_issues == 0


class TestSafetyNotice:
    def test_safety_notice_present(self) -> None:
        artifact_bytes = _build_artifact_bytes()
        manifest = _written_manifest(artifact_bytes)
        inp = HumanReviewAuditBundleExportVerificationInput(
            manifest=manifest,
            artifact_bytes=artifact_bytes,
        )
        report = verify_human_review_audit_bundle_export(inp)
        assert report.safety_flags.safety_notice_present is True

    def test_safety_notice_missing_advisory(self) -> None:
        artifact_bytes = dict_to_json_bytes({"data": "no safety notice"})
        manifest = _written_manifest(artifact_bytes)
        inp = HumanReviewAuditBundleExportVerificationInput(
            manifest=manifest,
            artifact_bytes=artifact_bytes,
        )
        report = verify_human_review_audit_bundle_export(inp)
        assert report.state == HumanReviewAuditBundleExportVerificationState.DEGRADED
        assert report.safety_flags.safety_notice_present is False
        assert report.data_quality.missing_safety_notice_count == 1
        assert HumanReviewAuditBundleExportVerificationReasonCode.SAFETY_NOTICE_MISSING in report.reason_codes

    def test_safety_notice_not_required(self) -> None:
        artifact_bytes = dict_to_json_bytes({"data": "no safety notice"})
        manifest = _written_manifest(artifact_bytes)
        inp = HumanReviewAuditBundleExportVerificationInput(
            manifest=manifest,
            artifact_bytes=artifact_bytes,
            config=HumanReviewAuditBundleExportVerificationConfig(require_safety_notice=False),
        )
        report = verify_human_review_audit_bundle_export(inp)
        assert report.state == HumanReviewAuditBundleExportVerificationState.VERIFIED


class TestOpaqueRefs:
    def test_refs_are_strings_not_resolved(self) -> None:
        artifact_bytes = _build_artifact_bytes()
        manifest = _written_manifest(
            artifact_bytes,
            output_path="reports/secret.json",
        )
        inp = HumanReviewAuditBundleExportVerificationInput(
            manifest=manifest,
            artifact_bytes=artifact_bytes,
        )
        report = verify_human_review_audit_bundle_export(inp)
        assert report.input_summary["report_id"] == "report-001"
        assert report.input_summary["bundle_report_id"] == "bundle-report-001"
        assert report.input_summary["content_hash_prefix"] == manifest.content_hash[:16]
        assert "output_path" not in report.input_summary

    def test_no_filesystem_traversal(self) -> None:
        manifest = HumanReviewAuditBundleExportManifest(
            manifest_id="manifest-007",
            report_id="report-007",
            bundle_report_id="bundle-report-007",
            output_path="/etc/passwd",
            state=HumanReviewAuditBundleExportState.BLOCKED,
        )
        inp = HumanReviewAuditBundleExportVerificationInput(
            manifest=manifest,
            artifact_bytes=b"",
        )
        report = verify_human_review_audit_bundle_export(inp)
        assert report.state == HumanReviewAuditBundleExportVerificationState.BLOCKED


class TestNoFsOrNetwork:
    def test_no_filesystem_writes(self) -> None:
        import os
        artifact_bytes = _build_artifact_bytes()
        manifest = _written_manifest(artifact_bytes)
        inp = HumanReviewAuditBundleExportVerificationInput(
            manifest=manifest,
            artifact_bytes=artifact_bytes,
        )
        verify_human_review_audit_bundle_export(inp)
        # Ensure no side-effect files were created by name in the project root.
        assert not os.path.exists("verification_report.json")
        assert not os.path.exists("verification_output")

    def test_no_network_calls(self) -> None:
        artifact_bytes = _build_artifact_bytes()
        manifest = _written_manifest(artifact_bytes)
        inp = HumanReviewAuditBundleExportVerificationInput(
            manifest=manifest,
            artifact_bytes=artifact_bytes,
        )
        report = verify_human_review_audit_bundle_export(inp)
        assert report.safety_flags.no_network is True


class TestWriterExists:
    def test_writer_module_imported(self) -> None:
        from hunter import human_review_audit_bundle_export_verification
        assert hasattr(human_review_audit_bundle_export_verification, "writer")
        assert hasattr(human_review_audit_bundle_export_verification, "verification_report_to_dict")
        assert hasattr(human_review_audit_bundle_export_verification, "verification_report_to_json")
        assert hasattr(human_review_audit_bundle_export_verification, "verification_report_to_markdown")

    def test_report_does_not_serialize_bytes(self) -> None:
        artifact_bytes = _build_artifact_bytes()
        manifest = _written_manifest(artifact_bytes)
        inp = HumanReviewAuditBundleExportVerificationInput(
            manifest=manifest,
            artifact_bytes=artifact_bytes,
        )
        report = verify_human_review_audit_bundle_export(inp)
        assert not hasattr(report, "artifact_bytes")


class TestForbiddenTerms:
    def test_scan_forbidden_terms_detects_phrase(self) -> None:
        found = _scan_forbidden_terms("Please deploy this patch to production.")
        assert "deploy" in found
        assert "patch" in found

    def test_scan_respects_allowed_negations(self) -> None:
        found = _scan_forbidden_terms(
            "This is not trading and does not imply a recommendation."
        )
        assert "recommend" not in found
        assert "buy" not in found

    def test_forbidden_terms_in_report_override_to_blocked(self, monkeypatch: pytest.MonkeyPatch) -> None:
        artifact_bytes = _build_artifact_bytes()
        manifest = _written_manifest(artifact_bytes)
        inp = HumanReviewAuditBundleExportVerificationInput(
            manifest=manifest,
            artifact_bytes=artifact_bytes,
        )

        original_builder = verify_human_review_audit_bundle_export.__globals__["_build_report_text_for_scan"]

        def evil_builder(report: HumanReviewAuditBundleExportVerificationReport) -> str:
            return "deploy this patch to production"

        monkeypatch.setitem(
            verify_human_review_audit_bundle_export.__globals__,
            "_build_report_text_for_scan",
            evil_builder,
        )
        try:
            report = verify_human_review_audit_bundle_export(inp)
            assert report.state == HumanReviewAuditBundleExportVerificationState.BLOCKED
            assert HumanReviewAuditBundleExportVerificationReasonCode.FORBIDDEN_TERM_PRESENT in report.reason_codes
            assert report.data_quality.forbidden_term_count >= 2
        finally:
            monkeypatch.setitem(
                verify_human_review_audit_bundle_export.__globals__,
                "_build_report_text_for_scan",
                original_builder,
            )

    def test_no_forbidden_terms_in_clean_report(self) -> None:
        artifact_bytes = _build_artifact_bytes()
        manifest = _written_manifest(artifact_bytes)
        inp = HumanReviewAuditBundleExportVerificationInput(
            manifest=manifest,
            artifact_bytes=artifact_bytes,
        )
        report = verify_human_review_audit_bundle_export(inp)
        assert report.state == HumanReviewAuditBundleExportVerificationState.VERIFIED
        assert report.data_quality.forbidden_term_count == 0


class TestMetadataAndValidation:
    def test_missing_manifest_metadata_blocked(self) -> None:
        artifact_bytes = _build_artifact_bytes()
        manifest = _written_manifest(
            artifact_bytes,
            content_hash="",
            content_length=0,
        )
        inp = HumanReviewAuditBundleExportVerificationInput(
            manifest=manifest,
            artifact_bytes=artifact_bytes,
        )
        report = verify_human_review_audit_bundle_export(inp)
        assert report.state == HumanReviewAuditBundleExportVerificationState.BLOCKED
        assert HumanReviewAuditBundleExportVerificationReasonCode.MISSING_MANIFEST_METADATA in report.reason_codes

    def test_metadata_passed_through(self) -> None:
        artifact_bytes = _build_artifact_bytes()
        manifest = _written_manifest(artifact_bytes)
        inp = HumanReviewAuditBundleExportVerificationInput(
            manifest=manifest,
            artifact_bytes=artifact_bytes,
            metadata={"version": "test"},
        )
        report = verify_human_review_audit_bundle_export(inp)
        assert report.metadata["version"] == "test"
