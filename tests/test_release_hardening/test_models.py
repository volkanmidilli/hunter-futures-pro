"""Tests for hunter.release_hardening.models."""

from __future__ import annotations

from datetime import datetime, timezone
from types import MappingProxyType

import pytest

from hunter.release_hardening.models import (
    CompletedAuditPackage,
    PackageDeclaration,
    ReleaseHardeningCheck,
    ReleaseHardeningCheckCategory,
    ReleaseHardeningConfig,
    ReleaseHardeningDataQuality,
    ReleaseHardeningInput,
    ReleaseHardeningReasonCode,
    ReleaseHardeningReport,
    ReleaseHardeningSafetyFlags,
    ReleaseHardeningSeverity,
    ReleaseHardeningState,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


def test_state_enum_values() -> None:
    assert ReleaseHardeningState.PASS.value == "pass"
    assert ReleaseHardeningState.DEGRADED.value == "degraded"
    assert ReleaseHardeningState.BLOCKED.value == "blocked"
    assert ReleaseHardeningState.NOT_APPLICABLE.value == "not_applicable"


def test_reason_code_enum_values() -> None:
    assert ReleaseHardeningReasonCode.OK.value == "ok"
    assert ReleaseHardeningReasonCode.NOT_APPLICABLE.value == "not_applicable"
    assert ReleaseHardeningReasonCode.CONSISTENCY_DEGRADED.value == "consistency_degraded"
    assert ReleaseHardeningReasonCode.SAFETY_BLOCKED.value == "safety_blocked"


def test_severity_enum_values() -> None:
    assert ReleaseHardeningSeverity.ADVISORY.value == "advisory"
    assert ReleaseHardeningSeverity.BLOCKING.value == "blocking"


def test_check_category_enum_values() -> None:
    categories = {c.value for c in ReleaseHardeningCheckCategory}
    expected = {
        "public_exports",
        "writer_defaults",
        "safety_notices",
        "version_consistency",
        "artifact_path_policy",
        "test_artifact_isolation",
        "forbidden_term_policy",
        "markdown_disclaimer_policy",
        "default_path_locality",
        "package_presence",
    }
    assert categories == expected


# ---------------------------------------------------------------------------
# PackageDeclaration
# ---------------------------------------------------------------------------


def test_package_declaration_defaults() -> None:
    pkg = PackageDeclaration(
        package_id="pkg_1",
        package_name="pkg_one",
        module_path="hunter.one",
    )
    assert pkg.expected_public_exports == ()
    assert pkg.actual_public_exports == ()
    assert pkg.expected_modules == (
        "__init__.py",
        "models.py",
        "engine.py",
        "writer.py",
    )
    assert pkg.actual_modules_present == ()
    assert pkg.writer_default_paths == ()
    assert pkg.test_default_paths == ()
    assert pkg.safety_notices == ()
    assert pkg.markdown_disclaimer == ""
    assert pkg.version is None


def test_package_declaration_normalizes_lists() -> None:
    pkg = PackageDeclaration(
        package_id="pkg_1",
        package_name="pkg_one",
        module_path="hunter.one",
        expected_public_exports=["a", "b"],
        actual_public_exports=["a", "b", "c"],
        actual_modules_present=["__init__.py"],
        writer_default_paths=["data/one/output.json"],
        test_default_paths=["tests/one/test.json"],
        safety_notices=["Research only."],
    )
    assert isinstance(pkg.expected_public_exports, tuple)
    assert pkg.expected_public_exports == ("a", "b")
    assert pkg.actual_public_exports == ("a", "b", "c")


def test_package_declaration_rejects_invalid_ids() -> None:
    with pytest.raises(ValueError, match="package_id"):
        PackageDeclaration(package_id="", package_name="x", module_path="y")


# ---------------------------------------------------------------------------
# CompletedAuditPackage
# ---------------------------------------------------------------------------


def test_completed_audit_package_defaults() -> None:
    cap = CompletedAuditPackage(package_id="cap_1", package_name="cap_one")
    assert cap.artifact_paths == ()
    assert cap.metadata == ()


def test_completed_audit_package_validates_metadata() -> None:
    cap = CompletedAuditPackage(
        package_id="cap_1",
        package_name="cap_one",
        metadata=(("key", "value"),),
    )
    assert cap.metadata == (("key", "value"),)
    with pytest.raises(ValueError):
        CompletedAuditPackage(
            package_id="cap_1",
            package_name="cap_one",
            metadata=(("key",),),
        )


# ---------------------------------------------------------------------------
# ReleaseHardeningCheck
# ---------------------------------------------------------------------------


def test_check_requires_valid_category() -> None:
    with pytest.raises(ValueError, match="unsupported category"):
        ReleaseHardeningCheck(
            check_id="x",
            category="unknown",
            description="d",
            required=True,
            severity=ReleaseHardeningSeverity.BLOCKING,
            policy="p",
        )


def test_check_accepts_valid_category() -> None:
    check = ReleaseHardeningCheck(
        check_id="public_exports",
        category=ReleaseHardeningCheckCategory.PUBLIC_EXPORTS.value,
        description="d",
        required=True,
        severity=ReleaseHardeningSeverity.BLOCKING,
        policy="p",
    )
    assert check.required is True
    assert check.severity is ReleaseHardeningSeverity.BLOCKING


# ---------------------------------------------------------------------------
# ReleaseHardeningDataQuality
# ---------------------------------------------------------------------------


def test_data_quality_counts_must_sum() -> None:
    with pytest.raises(ValueError, match="state counts must sum"):
        ReleaseHardeningDataQuality(
            total_checks=3,
            pass_count=2,
            degraded_count=0,
            blocked_count=0,
            not_applicable_count=0,
            package_count=1,
            completed_package_count=0,
        )


# ---------------------------------------------------------------------------
# ReleaseHardeningSafetyFlags
# ---------------------------------------------------------------------------


def test_safety_flags_baseline_invariants() -> None:
    with pytest.raises(ValueError, match="baseline safety invariants"):
        ReleaseHardeningSafetyFlags(research_only=False)


def test_safety_flags_is_safe_reflects_negative_states() -> None:
    safe = ReleaseHardeningSafetyFlags()
    assert safe.is_safe is True
    degraded = ReleaseHardeningSafetyFlags(has_degraded=True)
    assert degraded.is_safe is False


# ---------------------------------------------------------------------------
# ReleaseHardeningInput
# ---------------------------------------------------------------------------


def test_input_validates_naive_datetime() -> None:
    naive = datetime.now()
    with pytest.raises(ValueError, match="timezone-aware"):
        ReleaseHardeningInput(
            packages=(PackageDeclaration("a", "b", "c"),),
            generated_at=naive,
        )


def test_input_normalizes_lists() -> None:
    inp = ReleaseHardeningInput(
        packages=[PackageDeclaration("a", "b", "c")],
        generated_at=datetime.now(timezone.utc),
    )
    assert isinstance(inp.packages, tuple)


# ---------------------------------------------------------------------------
# ReleaseHardeningReport
# ---------------------------------------------------------------------------


def test_blocked_report_is_valid_minimal() -> None:
    inp = ReleaseHardeningInput(packages=(PackageDeclaration("a", "b", "c"),))
    report = ReleaseHardeningReport.blocked(
        input=inp,
        reason_code=ReleaseHardeningReasonCode.DUPLICATE_PACKAGE_ID,
    )
    assert report.state is ReleaseHardeningState.BLOCKED
    assert ReleaseHardeningReasonCode.SAFETY_BLOCKED in report.reason_codes
    assert ReleaseHardeningReasonCode.DUPLICATE_PACKAGE_ID in report.reason_codes
    assert report.checks == ()
    assert report.data_quality.total_checks == 0


# ---------------------------------------------------------------------------
# Frozen dataclasses
# ---------------------------------------------------------------------------


def test_frozen_dataclasses_reject_mutation() -> None:
    pkg = PackageDeclaration("a", "b", "c")
    with pytest.raises(AttributeError):
        pkg.package_id = "d"
