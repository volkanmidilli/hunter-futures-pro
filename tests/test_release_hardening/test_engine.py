"""Tests for hunter.release_hardening.engine."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from hunter.release_hardening.engine import (
    build_release_hardening_report,
    build_release_hardening_safety_flags,
    has_unsafe_release_hardening_content,
)
from hunter.release_hardening.models import (
    CompletedAuditPackage,
    PackageDeclaration,
    ReleaseHardeningCheck,
    ReleaseHardeningCheckCategory,
    ReleaseHardeningConfig,
    ReleaseHardeningInput,
    ReleaseHardeningReasonCode,
    ReleaseHardeningSeverity,
    ReleaseHardeningState,
)


# ---------------------------------------------------------------------------
# Safety helpers
# ---------------------------------------------------------------------------


def test_has_unsafe_content_detects_forbidden_term() -> None:
    assert has_unsafe_release_hardening_content(text="This is production ready.") is True


def test_has_unsafe_content_allows_safe_text() -> None:
    assert (
        has_unsafe_release_hardening_content(
            text="This is research-only output, not trading advice."
        )
        is False
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def generated_at() -> datetime:
    return datetime(2026, 7, 4, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def good_package(generated_at: datetime) -> PackageDeclaration:
    return PackageDeclaration(
        package_id="good_pkg",
        package_name="Good Package",
        module_path="hunter.good",
        expected_public_exports=("build_report",),
        actual_public_exports=("build_report", "__version__"),
        expected_modules=("__init__.py", "models.py", "engine.py", "writer.py"),
        actual_modules_present=("__init__.py", "models.py", "engine.py", "writer.py"),
        writer_default_paths=("data/good/output.json",),
        test_default_paths=("tests/test_good/test_output.json",),
        safety_notices=("Research-only output, not trading advice.",),
        markdown_disclaimer=(
            "This report is a human-audit research artifact. "
            "It is not trading advice and not a certification of trading readiness."
        ),
        version="0.33.0-dev",
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_build_report_passes_with_good_package(
    good_package: PackageDeclaration, generated_at: datetime
) -> None:
    inp = ReleaseHardeningInput(
        packages=(good_package,),
        project_version="0.33.0-dev",
        generated_at=generated_at,
    )
    report = build_release_hardening_report(inp)
    assert report.state is ReleaseHardeningState.PASS
    assert report.generated_at == generated_at
    assert report.data_quality.total_checks > 0
    assert report.data_quality.pass_count > 0
    assert report.data_quality.blocked_count == 0
    assert report.safety_flags.has_blocked is False


# ---------------------------------------------------------------------------
# public_exports
# ---------------------------------------------------------------------------


def test_public_exports_missing_blocked(generated_at: datetime) -> None:
    pkg = PackageDeclaration(
        package_id="pkg",
        package_name="Pkg",
        module_path="hunter.pkg",
        expected_public_exports=("missing",),
        actual_public_exports=("present",),
        expected_modules=("__init__.py",),
        actual_modules_present=("__init__.py",),
        safety_notices=("Research only.",),
        markdown_disclaimer="This is research-only output.",
    )
    inp = ReleaseHardeningInput(packages=(pkg,), generated_at=generated_at)
    report = build_release_hardening_report(inp)
    assert report.state is ReleaseHardeningState.BLOCKED
    assert any(
        r.reason_code is ReleaseHardeningReasonCode.MISSING_PUBLIC_EXPORT
        for r in report.checks
    )


# ---------------------------------------------------------------------------
# package_presence
# ---------------------------------------------------------------------------


def test_package_presence_missing_blocked(generated_at: datetime) -> None:
    pkg = PackageDeclaration(
        package_id="pkg",
        package_name="Pkg",
        module_path="hunter.pkg",
        expected_modules=("__init__.py", "models.py"),
        actual_modules_present=("__init__.py",),
        safety_notices=("Research only.",),
        markdown_disclaimer="This is research-only output.",
    )
    inp = ReleaseHardeningInput(packages=(pkg,), generated_at=generated_at)
    report = build_release_hardening_report(inp)
    assert report.state is ReleaseHardeningState.BLOCKED
    assert any(
        r.reason_code is ReleaseHardeningReasonCode.PACKAGE_NOT_PRESENT
        for r in report.checks
    )


# ---------------------------------------------------------------------------
# test_artifact_isolation
# ---------------------------------------------------------------------------


def test_test_artifact_isolation_flags_bad_path(generated_at: datetime) -> None:
    pkg = PackageDeclaration(
        package_id="pkg",
        package_name="Pkg",
        module_path="hunter.pkg",
        expected_modules=("__init__.py",),
        actual_modules_present=("__init__.py",),
        writer_default_paths=("data/pkg/output.json",),
        test_default_paths=("data/pkg/test_output.json",),  # overlaps with production
        safety_notices=("Research only.",),
        markdown_disclaimer="This is research-only output.",
    )
    inp = ReleaseHardeningInput(packages=(pkg,), generated_at=generated_at)
    report = build_release_hardening_report(inp)
    assert report.state is ReleaseHardeningState.DEGRADED
    assert any(
        r.reason_code is ReleaseHardeningReasonCode.TEST_ARTIFACT_NOT_ISOLATED
        for r in report.checks
    )


def test_test_artifact_isolation_is_advisory(generated_at: datetime) -> None:
    pkg = PackageDeclaration(
        package_id="pkg",
        package_name="Pkg",
        module_path="hunter.pkg",
        expected_modules=("__init__.py",),
        actual_modules_present=("__init__.py",),
        writer_default_paths=("data/pkg/output.json",),
        test_default_paths=("data/pkg/test_output.json",),
        safety_notices=("Research only.",),
        markdown_disclaimer="This is research-only output.",
    )
    inp = ReleaseHardeningInput(packages=(pkg,), generated_at=generated_at)
    report = build_release_hardening_report(inp)
    assert report.state is ReleaseHardeningState.DEGRADED
    # Should not be BLOCKED because test_artifact_isolation is advisory.
    assert not any(
        r.reason_code is ReleaseHardeningReasonCode.SAFETY_BLOCKED
        for r in report.checks
    )


# ---------------------------------------------------------------------------
# Empty actuals
# ---------------------------------------------------------------------------


def test_empty_actual_public_exports_blocking_check_is_blocked(
    generated_at: datetime,
) -> None:
    pkg = PackageDeclaration(
        package_id="pkg",
        package_name="Pkg",
        module_path="hunter.pkg",
        expected_public_exports=("a",),
        actual_public_exports=(),
        expected_modules=("__init__.py",),
        actual_modules_present=("__init__.py",),
        safety_notices=("Research only.",),
        markdown_disclaimer="This is research-only output.",
    )
    inp = ReleaseHardeningInput(packages=(pkg,), generated_at=generated_at)
    report = build_release_hardening_report(inp)
    public_export_result = next(
        r for r in report.checks if r.category == "public_exports"
    )
    assert public_export_result.state is ReleaseHardeningState.BLOCKED


def test_empty_test_paths_advisory_check_is_not_applicable(
    generated_at: datetime,
) -> None:
    pkg = PackageDeclaration(
        package_id="pkg",
        package_name="Pkg",
        module_path="hunter.pkg",
        expected_modules=("__init__.py",),
        actual_modules_present=("__init__.py",),
        writer_default_paths=("data/pkg/output.json",),
        test_default_paths=(),
        safety_notices=("Research only.",),
        markdown_disclaimer="This is research-only output.",
    )
    inp = ReleaseHardeningInput(packages=(pkg,), generated_at=generated_at)
    report = build_release_hardening_report(inp)
    isolation_result = next(
        r for r in report.checks if r.category == "test_artifact_isolation"
    )
    assert isolation_result.state is ReleaseHardeningState.NOT_APPLICABLE


# ---------------------------------------------------------------------------
# version_consistency
# ---------------------------------------------------------------------------


def test_version_patch_mismatch_degraded(
    good_package: PackageDeclaration, generated_at: datetime
) -> None:
    pkg = good_package
    inp = ReleaseHardeningInput(
        packages=(pkg,),
        project_version="0.33.1-dev",
        generated_at=generated_at,
    )
    report = build_release_hardening_report(inp)
    version_result = next(
        r for r in report.checks if r.category == "version_consistency"
    )
    assert version_result.state is ReleaseHardeningState.DEGRADED
    assert version_result.reason_code is ReleaseHardeningReasonCode.VERSION_INCONSISTENT


def test_version_major_mismatch_blocked(
    good_package: PackageDeclaration, generated_at: datetime
) -> None:
    inp = ReleaseHardeningInput(
        packages=(good_package,),
        project_version="1.33.0-dev",
        generated_at=generated_at,
    )
    report = build_release_hardening_report(inp)
    version_result = next(
        r for r in report.checks if r.category == "version_consistency"
    )
    assert version_result.state is ReleaseHardeningState.BLOCKED


def test_version_minor_mismatch_blocked(
    good_package: PackageDeclaration, generated_at: datetime
) -> None:
    inp = ReleaseHardeningInput(
        packages=(good_package,),
        project_version="0.34.0-dev",
        generated_at=generated_at,
    )
    report = build_release_hardening_report(inp)
    version_result = next(
        r for r in report.checks if r.category == "version_consistency"
    )
    assert version_result.state is ReleaseHardeningState.BLOCKED


# ---------------------------------------------------------------------------
# Aggregation and strict mode
# ---------------------------------------------------------------------------


def test_non_strict_mode_preserves_degraded(
    good_package: PackageDeclaration, generated_at: datetime
) -> None:
    inp = ReleaseHardeningInput(
        packages=(good_package,),
        project_version="0.33.1-dev",
        generated_at=generated_at,
        config=ReleaseHardeningConfig(strict=False),
    )
    report = build_release_hardening_report(inp)
    assert report.state is ReleaseHardeningState.DEGRADED
    assert ReleaseHardeningReasonCode.CONSISTENCY_DEGRADED in report.reason_codes


def test_strict_mode_promotes_degraded_to_blocked(
    good_package: PackageDeclaration, generated_at: datetime
) -> None:
    inp = ReleaseHardeningInput(
        packages=(good_package,),
        project_version="0.33.1-dev",
        generated_at=generated_at,
        config=ReleaseHardeningConfig(strict=True),
    )
    report = build_release_hardening_report(inp)
    assert report.state is ReleaseHardeningState.BLOCKED
    assert ReleaseHardeningReasonCode.SAFETY_BLOCKED in report.reason_codes


# ---------------------------------------------------------------------------
# Duplicate IDs and empty input
# ---------------------------------------------------------------------------


def test_duplicate_package_ids_blocked(generated_at: datetime) -> None:
    pkg = PackageDeclaration(
        package_id="dup",
        package_name="Dup",
        module_path="hunter.dup",
        expected_modules=("__init__.py",),
        actual_modules_present=("__init__.py",),
        safety_notices=("Research only.",),
        markdown_disclaimer="This is research-only output.",
    )
    inp = ReleaseHardeningInput(
        packages=(pkg, pkg), generated_at=generated_at
    )
    report = build_release_hardening_report(inp)
    assert report.state is ReleaseHardeningState.BLOCKED
    assert ReleaseHardeningReasonCode.DUPLICATE_PACKAGE_ID in report.reason_codes


def test_duplicate_check_ids_blocked(generated_at: datetime) -> None:
    pkg = PackageDeclaration(
        package_id="pkg",
        package_name="Pkg",
        module_path="hunter.pkg",
        expected_modules=("__init__.py",),
        actual_modules_present=("__init__.py",),
        safety_notices=("Research only.",),
        markdown_disclaimer="This is research-only output.",
    )
    check = ReleaseHardeningCheck(
        check_id="same",
        category=ReleaseHardeningCheckCategory.PUBLIC_EXPORTS.value,
        description="d",
        required=True,
        severity=ReleaseHardeningSeverity.BLOCKING,
        policy="p",
    )
    inp = ReleaseHardeningInput(
        packages=(pkg,),
        checks=(check, check),
        generated_at=generated_at,
    )
    report = build_release_hardening_report(inp)
    assert report.state is ReleaseHardeningState.BLOCKED
    assert ReleaseHardeningReasonCode.DUPLICATE_CHECK_ID in report.reason_codes


def test_empty_packages_blocked(generated_at: datetime) -> None:
    inp = ReleaseHardeningInput(packages=(), generated_at=generated_at)
    report = build_release_hardening_report(inp)
    assert report.state is ReleaseHardeningState.BLOCKED
    assert ReleaseHardeningReasonCode.MISSING_REQUIRED_DECLARATION in report.reason_codes


# ---------------------------------------------------------------------------
# Unsafe content
# ---------------------------------------------------------------------------


def test_unsafe_input_metadata_blocked(generated_at: datetime) -> None:
    pkg = PackageDeclaration(
        package_id="pkg",
        package_name="Pkg",
        module_path="hunter.pkg",
        expected_modules=("__init__.py",),
        actual_modules_present=("__init__.py",),
        safety_notices=("Research only.",),
        markdown_disclaimer="This is research-only output.",
    )
    inp = ReleaseHardeningInput(
        packages=(pkg,),
        generated_at=generated_at,
        metadata={"note": "This is production ready"},
    )
    report = build_release_hardening_report(inp)
    assert report.state is ReleaseHardeningState.BLOCKED
    assert ReleaseHardeningReasonCode.UNSAFE_CONTENT in report.reason_codes


# ---------------------------------------------------------------------------
# Determinism and immutability
# ---------------------------------------------------------------------------


def test_build_report_is_deterministic(
    good_package: PackageDeclaration, generated_at: datetime
) -> None:
    inp = ReleaseHardeningInput(
        packages=(good_package,),
        project_version="0.33.0-dev",
        generated_at=generated_at,
    )
    r1 = build_release_hardening_report(inp)
    r2 = build_release_hardening_report(inp)
    assert r1 == r2


def test_build_report_does_not_mutate_input(
    good_package: PackageDeclaration, generated_at: datetime
) -> None:
    inp = ReleaseHardeningInput(
        packages=(good_package,),
        project_version="0.33.0-dev",
        generated_at=generated_at,
    )
    original_checks = len(inp.checks)
    build_release_hardening_report(inp)
    assert len(inp.packages) == 1
    assert len(inp.checks) == original_checks


# ---------------------------------------------------------------------------
# Completed audit package artifact path policy
# ---------------------------------------------------------------------------


def test_artifact_path_policy_blocks_nonlocal(generated_at: datetime) -> None:
    pkg = PackageDeclaration(
        package_id="pkg",
        package_name="Pkg",
        module_path="hunter.pkg",
        expected_modules=("__init__.py",),
        actual_modules_present=("__init__.py",),
        safety_notices=("Research only.",),
        markdown_disclaimer="This is research-only output.",
    )
    completed = CompletedAuditPackage(
        package_id="cap",
        package_name="Cap",
        artifact_paths=("http://example.com/artifact.json",),
    )
    inp = ReleaseHardeningInput(
        packages=(pkg,),
        completed_packages=(completed,),
        generated_at=generated_at,
    )
    report = build_release_hardening_report(inp)
    assert report.state is ReleaseHardeningState.BLOCKED
    assert any(
        r.reason_code is ReleaseHardeningReasonCode.ARTIFACT_PATH_NOT_LOCAL
        for r in report.checks
    )
