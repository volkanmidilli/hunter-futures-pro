"""Tests for hunter.human_review_audit_bundle_export_verification writer."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from json import loads
from typing import Any

import pytest

from hunter.human_review_audit_bundle_export.models import (
    HumanReviewAuditBundleExportManifest,
    HumanReviewAuditBundleExportSafetyFlags,
    HumanReviewAuditBundleExportState,
)
from hunter.human_review_audit_bundle_export_verification.engine import (
    _scan_forbidden_terms,
    verify_human_review_audit_bundle_export,
)
from hunter.human_review_audit_bundle_export_verification.models import (
    HumanReviewAuditBundleExportVerificationConfig,
    HumanReviewAuditBundleExportVerificationInput,
    HumanReviewAuditBundleExportVerificationReport,
    HumanReviewAuditBundleExportVerificationState,
)
from hunter.human_review_audit_bundle_export_verification.writer import (
    NO_AUTHENTICITY_STATEMENT,
    SAFETY_NOTICE,
    VERIFICATION_KIND,
    verification_report_to_dict,
    verification_report_to_json,
    verification_report_to_markdown,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_artifact_bytes() -> bytes:
    from hunter.human_review_audit_bundle_export.models import SAFETY_NOTICE as EXPORT_SN
    from json import dumps
    body = {
        "metadata": {"id": "bundle-1"},
        "safety_notice": EXPORT_SN,
        "findings": [],
    }
    return dumps(body, indent=2, sort_keys=True).encode("utf-8")


def _written_manifest(
    artifact_bytes: bytes,
    state: HumanReviewAuditBundleExportState = HumanReviewAuditBundleExportState.WRITTEN,
    **overrides: Any,
) -> HumanReviewAuditBundleExportManifest:
    content_hash = sha256(artifact_bytes).hexdigest()
    defaults: dict[str, Any] = {
        "manifest_id": "manifest-001",
        "report_id": "report-001",
        "bundle_report_id": "bundle-report-001",
        "filename": "artifact.json",
        "output_path": "reports/artifact.json",
        "format": "json",
        "content_hash": content_hash,
        "content_length": len(artifact_bytes),
        "state": state,
        "safety_flags": HumanReviewAuditBundleExportSafetyFlags(
            hash_verified=(state == HumanReviewAuditBundleExportState.WRITTEN),
        ),
    }
    defaults.update(overrides)
    return HumanReviewAuditBundleExportManifest(**defaults)


def _verified_report() -> HumanReviewAuditBundleExportVerificationReport:
    artifact_bytes = _build_artifact_bytes()
    manifest = _written_manifest(artifact_bytes)
    inp = HumanReviewAuditBundleExportVerificationInput(
        manifest=manifest,
        artifact_bytes=artifact_bytes,
        metadata={"version": "test"},
    )
    return verify_human_review_audit_bundle_export(inp)


def _blocked_report() -> HumanReviewAuditBundleExportVerificationReport:
    artifact_bytes = _build_artifact_bytes()
    manifest = _written_manifest(artifact_bytes)
    corrupted = bytearray(artifact_bytes)
    corrupted[0] ^= 0xFF
    inp = HumanReviewAuditBundleExportVerificationInput(
        manifest=manifest,
        artifact_bytes=bytes(corrupted),
    )
    return verify_human_review_audit_bundle_export(inp)


def _not_applicable_report() -> HumanReviewAuditBundleExportVerificationReport:
    manifest = HumanReviewAuditBundleExportManifest(
        manifest_id="manifest-na",
        report_id="report-na",
        bundle_report_id="bundle-na",
        state=HumanReviewAuditBundleExportState.NOT_APPLICABLE,
    )
    inp = HumanReviewAuditBundleExportVerificationInput(
        manifest=manifest,
        artifact_bytes=b"",
        config=HumanReviewAuditBundleExportVerificationConfig(allow_not_applicable=True),
    )
    return verify_human_review_audit_bundle_export(inp)


def _degraded_report() -> HumanReviewAuditBundleExportVerificationReport:
    from json import dumps
    artifact_bytes = dumps({"data": "no safety notice"}).encode("utf-8")
    manifest = _written_manifest(artifact_bytes)
    inp = HumanReviewAuditBundleExportVerificationInput(
        manifest=manifest,
        artifact_bytes=artifact_bytes,
    )
    return verify_human_review_audit_bundle_export(inp)


# ---------------------------------------------------------------------------
# Dict serialization tests
# ---------------------------------------------------------------------------


class TestVerificationReportToDict:
    def test_dict_has_required_top_level_fields(self) -> None:
        d = verification_report_to_dict(_verified_report())
        expected_keys = {
            "kind", "version", "safety_notice", "no_authenticity_statement",
            "verification_id", "report_id", "manifest_id", "bundle_report_id",
            "generated_at", "state", "config", "input_summary",
            "data_quality", "safety_flags", "reason_codes", "issues",
            "metadata", "notes",
        }
        assert set(d.keys()) == expected_keys

    def test_dict_kind_and_version(self) -> None:
        d = verification_report_to_dict(_verified_report())
        assert d["kind"] == VERIFICATION_KIND
        assert d["version"] == "0.45.0-dev"

    def test_dict_safety_notice_present(self) -> None:
        d = verification_report_to_dict(_verified_report())
        assert d["safety_notice"] == SAFETY_NOTICE

    def test_dict_no_authenticity_statement_present(self) -> None:
        d = verification_report_to_dict(_verified_report())
        assert d["no_authenticity_statement"] == NO_AUTHENTICITY_STATEMENT

    def test_dict_state_verified(self) -> None:
        d = verification_report_to_dict(_verified_report())
        assert d["state"] == "verified"

    def test_dict_state_blocked(self) -> None:
        d = verification_report_to_dict(_blocked_report())
        assert d["state"] == "blocked"

    def test_dict_state_not_applicable(self) -> None:
        d = verification_report_to_dict(_not_applicable_report())
        assert d["state"] == "not_applicable"

    def test_dict_state_degraded(self) -> None:
        d = verification_report_to_dict(_degraded_report())
        assert d["state"] == "degraded"

    def test_dict_metadata_sorted(self) -> None:
        d = verification_report_to_dict(_verified_report())
        keys = list(d["metadata"].keys())
        assert keys == sorted(keys)

    def test_dict_input_summary_sorted(self) -> None:
        d = verification_report_to_dict(_verified_report())
        keys = list(d["input_summary"].keys())
        assert keys == sorted(keys)

    def test_dict_issues_serialized(self) -> None:
        d = verification_report_to_dict(_blocked_report())
        assert len(d["issues"]) >= 1
        issue = d["issues"][0]
        assert "issue_id" in issue
        assert "issue_type" in issue
        assert "severity" in issue
        assert "reason_codes" in issue
        assert "source" in issue
        assert "title" in issue
        assert "description" in issue
        assert "generated_at" in issue

    def test_dict_empty_issues(self) -> None:
        d = verification_report_to_dict(_verified_report())
        assert d["issues"] == []

    def test_dict_reason_codes_list(self) -> None:
        d = verification_report_to_dict(_verified_report())
        assert isinstance(d["reason_codes"], list)
        assert "ok" in d["reason_codes"]

    def test_dict_config_fields(self) -> None:
        d = verification_report_to_dict(_verified_report())
        cfg = d["config"]
        assert set(cfg.keys()) == {"strict", "require_safety_notice", "verify_text_hash", "allow_not_applicable"}

    def test_dict_data_quality_fields(self) -> None:
        d = verification_report_to_dict(_verified_report())
        dq = d["data_quality"]
        expected = {
            "checks_performed", "hash_mismatch_count", "length_mismatch_count",
            "state_not_verifiable_count", "missing_safety_notice_count",
            "forbidden_term_count", "blocking_issues", "advisory_issues", "info_findings",
        }
        assert set(dq.keys()) == expected

    def test_dict_safety_flags_fields(self) -> None:
        d = verification_report_to_dict(_verified_report())
        sf = d["safety_flags"]
        expected = {
            "is_safe", "audit_only", "no_executable_actions",
            "no_trading_instructions", "no_approval_claims",
            "references_opaque", "no_network", "no_server",
            "hash_verified", "length_verified",
            "state_verifiable", "safety_notice_present",
        }
        assert set(sf.keys()) == expected

    def test_dict_deterministic(self) -> None:
        d1 = verification_report_to_dict(_verified_report())
        d2 = verification_report_to_dict(_verified_report())
        assert d1 == d2

    def test_dict_no_raw_bytes(self) -> None:
        d = verification_report_to_dict(_verified_report())
        serialized = repr(d)
        assert "artifact_bytes" not in serialized
        # Check no actual byte content leaked
        assert "b'" not in serialized

    def test_dict_no_resolved_paths(self) -> None:
        d = verification_report_to_dict(_verified_report())
        serialized = repr(d)
        assert "output_path" not in serialized
        assert "reports/artifact.json" not in serialized


# ---------------------------------------------------------------------------
# JSON serialization tests
# ---------------------------------------------------------------------------


class TestVerificationReportToJson:
    def test_json_is_valid_json(self) -> None:
        j = verification_report_to_json(_verified_report())
        parsed = loads(j)
        assert parsed["state"] == "verified"

    def test_json_deterministic(self) -> None:
        j1 = verification_report_to_json(_verified_report())
        j2 = verification_report_to_json(_verified_report())
        assert j1 == j2

    def test_json_sorted_keys(self) -> None:
        j = verification_report_to_json(_verified_report())
        # Top-level keys should be alphabetically sorted in the JSON output.
        # Verify by checking that "config" appears before "version".
        idx_config = j.index('"config"')
        idx_version = j.index('"version"')
        assert idx_config < idx_version

    def test_json_no_raw_bytes(self) -> None:
        j = verification_report_to_json(_verified_report())
        assert "artifact_bytes" not in j

    def test_json_blocked_state(self) -> None:
        j = verification_report_to_json(_blocked_report())
        parsed = loads(j)
        assert parsed["state"] == "blocked"
        assert len(parsed["issues"]) >= 1

    def test_json_not_applicable_state(self) -> None:
        j = verification_report_to_json(_not_applicable_report())
        parsed = loads(j)
        assert parsed["state"] == "not_applicable"

    def test_json_degraded_state(self) -> None:
        j = verification_report_to_json(_degraded_report())
        parsed = loads(j)
        assert parsed["state"] == "degraded"


# ---------------------------------------------------------------------------
# Markdown serialization tests
# ---------------------------------------------------------------------------


class TestVerificationReportToMarkdown:
    def test_markdown_has_title(self) -> None:
        md = verification_report_to_markdown(_verified_report())
        assert md.startswith("# Human Review Audit Bundle Export Verification")

    def test_markdown_has_safety_notice(self) -> None:
        md = verification_report_to_markdown(_verified_report())
        assert SAFETY_NOTICE in md

    def test_markdown_has_no_authenticity_statement(self) -> None:
        md = verification_report_to_markdown(_verified_report())
        assert NO_AUTHENTICITY_STATEMENT in md

    def test_markdown_has_summary_section(self) -> None:
        md = verification_report_to_markdown(_verified_report())
        assert "## Summary" in md
        assert "verified" in md

    def test_markdown_has_reason_codes(self) -> None:
        md = verification_report_to_markdown(_verified_report())
        assert "## Reason Codes" in md

    def test_markdown_has_data_quality(self) -> None:
        md = verification_report_to_markdown(_verified_report())
        assert "## Data Quality" in md
        assert "## Safety Flags" in md

    def test_markdown_has_config(self) -> None:
        md = verification_report_to_markdown(_verified_report())
        assert "## Configuration" in md

    def test_markdown_has_input_summary(self) -> None:
        md = verification_report_to_markdown(_verified_report())
        assert "## Input Summary" in md

    def test_markdown_has_issues_section(self) -> None:
        md = verification_report_to_markdown(_verified_report())
        assert "## Issues" in md

    def test_markdown_no_issues_found(self) -> None:
        md = verification_report_to_markdown(_verified_report())
        assert "No issues found." in md

    def test_markdown_with_issues(self) -> None:
        md = verification_report_to_markdown(_blocked_report())
        assert "### " in md
        assert "hash_mismatch" in md.lower() or "Hash" in md

    def test_markdown_has_metadata(self) -> None:
        md = verification_report_to_markdown(_verified_report())
        assert "## Metadata" in md

    def test_markdown_has_notes(self) -> None:
        md = verification_report_to_markdown(_verified_report())
        assert "## Notes" in md

    def test_markdown_has_footer(self) -> None:
        md = verification_report_to_markdown(_verified_report())
        assert "---" in md
        assert VERIFICATION_KIND in md

    def test_markdown_deterministic(self) -> None:
        md1 = verification_report_to_markdown(_verified_report())
        md2 = verification_report_to_markdown(_verified_report())
        assert md1 == md2

    def test_markdown_blocked_state(self) -> None:
        md = verification_report_to_markdown(_blocked_report())
        assert "blocked" in md

    def test_markdown_not_applicable_state(self) -> None:
        md = verification_report_to_markdown(_not_applicable_report())
        assert "not_applicable" in md

    def test_markdown_degraded_state(self) -> None:
        md = verification_report_to_markdown(_degraded_report())
        assert "degraded" in md

    def test_markdown_no_raw_bytes(self) -> None:
        md = verification_report_to_markdown(_verified_report())
        assert "artifact_bytes" not in md

    def test_markdown_no_resolved_paths(self) -> None:
        md = verification_report_to_markdown(_verified_report())
        assert "reports/artifact.json" not in md


# ---------------------------------------------------------------------------
# Forbidden phrase scan tests
# ---------------------------------------------------------------------------


class TestForbiddenPhrases:
    def test_json_no_forbidden_terms(self) -> None:
        j = verification_report_to_json(_verified_report())
        found = _scan_forbidden_terms(j)
        assert found == [], f"Forbidden terms in JSON: {found}"

    def test_markdown_no_forbidden_terms_verified(self) -> None:
        md = verification_report_to_markdown(_verified_report())
        found = _scan_forbidden_terms(md)
        assert found == [], f"Forbidden terms in Markdown (verified): {found}"

    def test_markdown_no_forbidden_terms_blocked(self) -> None:
        md = verification_report_to_markdown(_blocked_report())
        found = _scan_forbidden_terms(md)
        assert found == [], f"Forbidden terms in Markdown (blocked): {found}"

    def test_markdown_no_forbidden_terms_not_applicable(self) -> None:
        md = verification_report_to_markdown(_not_applicable_report())
        found = _scan_forbidden_terms(md)
        assert found == [], f"Forbidden terms in Markdown (na): {found}"

    def test_markdown_no_forbidden_terms_degraded(self) -> None:
        md = verification_report_to_markdown(_degraded_report())
        found = _scan_forbidden_terms(md)
        assert found == [], f"Forbidden terms in Markdown (degraded): {found}"

    def test_dict_no_forbidden_terms(self) -> None:
        from json import dumps as _dumps
        d = verification_report_to_dict(_verified_report())
        # Serialize to string and scan
        text = _dumps(d, ensure_ascii=True, sort_keys=True)
        found = _scan_forbidden_terms(text)
        assert found == [], f"Forbidden terms in dict JSON: {found}"


# ---------------------------------------------------------------------------
# Opaque refs tests
# ---------------------------------------------------------------------------


class TestOpaqueRefs:
    def test_dict_refs_are_strings(self) -> None:
        d = verification_report_to_dict(_verified_report())
        assert isinstance(d["verification_id"], str)
        assert isinstance(d["report_id"], str)
        assert isinstance(d["manifest_id"], str)
        assert isinstance(d["bundle_report_id"], str)

    def test_dict_no_output_path(self) -> None:
        d = verification_report_to_dict(_verified_report())
        assert "output_path" not in d
        assert "tmp_path" not in d

    def test_dict_input_summary_refs_are_strings(self) -> None:
        d = verification_report_to_dict(_verified_report())
        for v in d["input_summary"].values():
            assert isinstance(v, str)

    def test_markdown_refs_are_backtick_quoted(self) -> None:
        md = verification_report_to_markdown(_verified_report())
        report = _verified_report()
        assert f"`{report.verification_id}`" in md
        assert f"`{report.report_id}`" in md


# ---------------------------------------------------------------------------
# No filesystem/network behavior tests
# ---------------------------------------------------------------------------


class TestNoIOBehavior:
    def test_writer_creates_no_files(self) -> None:
        import os
        report = _verified_report()
        verification_report_to_dict(report)
        verification_report_to_json(report)
        verification_report_to_markdown(report)
        assert not os.path.exists("verification_report.json")
        assert not os.path.exists("verification_report.md")
        assert not os.path.exists("verification_output")

    def test_no_writer_fs_imports(self) -> None:
        from hunter.human_review_audit_bundle_export_verification import writer
        import inspect
        source = inspect.getsource(writer)
        # No pathlib, os.path, open(), subprocess, socket, etc.
        forbidden_imports = [
            "from pathlib",
            "import pathlib",
            "from os",
            "import os",
            "import subprocess",
            "from subprocess",
            "import socket",
            "from socket",
        ]
        for imp in forbidden_imports:
            assert imp not in source, f"Forbidden import '{imp}' found in writer source"


# ---------------------------------------------------------------------------
# Cross-output consistency tests
# ---------------------------------------------------------------------------


class TestCrossOutputConsistency:
    def test_json_matches_dict(self) -> None:
        report = _verified_report()
        d = verification_report_to_dict(report)
        j = verification_report_to_json(report)
        parsed = loads(j)
        assert d == parsed

    def test_markdown_contains_key_fields_from_report(self) -> None:
        report = _verified_report()
        md = verification_report_to_markdown(report)
        assert report.verification_id in md
        assert report.report_id in md
        assert report.state.value in md

    def test_all_outputs_deterministic_for_same_report(self) -> None:
        report = _verified_report()
        d1 = verification_report_to_dict(report)
        j1 = verification_report_to_json(report)
        md1 = verification_report_to_markdown(report)
        d2 = verification_report_to_dict(report)
        j2 = verification_report_to_json(report)
        md2 = verification_report_to_markdown(report)
        assert d1 == d2
        assert j1 == j2
        assert md1 == md2


# ---------------------------------------------------------------------------
# Issue serialization tests
# ---------------------------------------------------------------------------


class TestIssueSerialization:
    def test_hash_mismatch_issue_in_dict(self) -> None:
        d = verification_report_to_dict(_blocked_report())
        hash_issues = [i for i in d["issues"] if i["issue_type"] == "hash_mismatch"]
        assert len(hash_issues) >= 1
        assert hash_issues[0]["severity"] == "blocking"

    def test_hash_mismatch_issue_in_markdown(self) -> None:
        md = verification_report_to_markdown(_blocked_report())
        assert "hash_mismatch" in md or "Hash" in md

    def test_issue_order_stable(self) -> None:
        d1 = verification_report_to_dict(_blocked_report())
        d2 = verification_report_to_dict(_blocked_report())
        ids1 = [i["issue_id"] for i in d1["issues"]]
        ids2 = [i["issue_id"] for i in d2["issues"]]
        assert ids1 == ids2

    def test_empty_issues_in_dict(self) -> None:
        d = verification_report_to_dict(_verified_report())
        assert d["issues"] == []

    def test_empty_issues_in_markdown(self) -> None:
        md = verification_report_to_markdown(_verified_report())
        assert "No issues found." in md


# ---------------------------------------------------------------------------
# Round-trip determinism via engine
# ---------------------------------------------------------------------------


class TestRoundTripDeterminism:
    def test_verified_report_id_stable_across_serializations(self) -> None:
        report = _verified_report()
        d = verification_report_to_dict(report)
        j = verification_report_to_json(report)
        parsed = loads(j)
        assert d["verification_id"] == parsed["verification_id"]
        assert d["verification_id"] == report.verification_id

    def test_different_reports_different_ids(self) -> None:
        d_verified = verification_report_to_dict(_verified_report())
        d_blocked = verification_report_to_dict(_blocked_report())
        assert d_verified["verification_id"] != d_blocked["verification_id"]
