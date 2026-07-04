"""Integration tests for hunter.release_hardening package.

MVP-33 — Local Research Release Hardening / Consistency Audit.

These tests exercise the public API end-to-end: build a ReleaseHardeningReport
from caller-provided in-memory declarations, serialize it to JSON/CSV/Markdown,
and verify safety and determinism properties. No filesystem scan, import
introspection, network, exchange, Binance, Freqtrade, live trading, order,
leverage, shorting, database, Web UI, server, or scheduler semantics are used.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hunter.release_hardening import (
    CompletedAuditPackage,
    PackageDeclaration,
    ReleaseHardeningConfig,
    ReleaseHardeningInput,
    ReleaseHardeningReasonCode,
    ReleaseHardeningState,
    atomic_write_csv_release_hardening_report,
    atomic_write_json_release_hardening_report,
    atomic_write_markdown_release_hardening_report,
    build_release_hardening_report,
    release_hardening_report_to_csv_text,
    release_hardening_report_to_dict,
    release_hardening_report_to_json_text,
    release_hardening_report_to_markdown_text,
    write_release_hardening_report,
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
        expected_public_exports=("build_report", "write_report"),
        actual_public_exports=("build_report", "write_report", "__version__"),
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


@pytest.fixture
def completed_package() -> CompletedAuditPackage:
    return CompletedAuditPackage(
        package_id="completed_pkg",
        package_name="Completed Package",
        artifact_paths=("data/completed/output.json", "reports/completed/output.md"),
        metadata=(("source", "test"),),
    )


@pytest.fixture
def pass_input(
    good_package: PackageDeclaration,
    completed_package: CompletedAuditPackage,
    generated_at: datetime,
) -> ReleaseHardeningInput:
    return ReleaseHardeningInput(
        packages=(good_package,),
        completed_packages=(completed_package,),
        project_version="0.33.0-dev",
        generated_at=generated_at,
    )


@pytest.fixture
def pass_report(pass_input: ReleaseHardeningInput) -> object:
    return build_release_hardening_report(pass_input)


# ---------------------------------------------------------------------------
# End-to-end success
# ---------------------------------------------------------------------------


def test_end_to_end_pass_report(
    pass_input: ReleaseHardeningInput, generated_at: datetime
) -> None:
    report = build_release_hardening_report(pass_input)
    assert report.state is ReleaseHardeningState.PASS
    assert report.generated_at == generated_at
    assert report.data_quality.pass_count > 0
    assert report.data_quality.blocked_count == 0
    assert report.safety_flags.is_safe is True

    # All reason codes are present as enums and serialized as strings.
    data = release_hardening_report_to_dict(report)
    assert data["state"] == "pass"
    assert data["generated_at"] == "2026-07-04T12:00:00+00:00"
    assert "checks" in data
    assert "data_quality" in data
    assert "safety_flags" in data

    # Writer-derived report_id is deterministic from generated_at.
    assert data["generated_at"] == "2026-07-04T12:00:00+00:00"


# ---------------------------------------------------------------------------
# Caller-provided actuals
# ---------------------------------------------------------------------------


def test_caller_provided_public_exports_subset_check(generated_at: datetime) -> None:
    pkg = PackageDeclaration(
        package_id="pkg",
        package_name="Pkg",
        module_path="hunter.pkg",
        expected_public_exports=("a", "b"),
        actual_public_exports=("a", "b", "c"),
        expected_modules=("__init__.py",),
        actual_modules_present=("__init__.py",),
        safety_notices=("Research only.",),
        markdown_disclaimer="This is research-only output.",
    )
    inp = ReleaseHardeningInput(packages=(pkg,), generated_at=generated_at)
    report = build_release_hardening_report(inp)
    public = next(r for r in report.checks if r.category == "public_exports")
    assert public.state is ReleaseHardeningState.PASS


def test_caller_provided_package_presence_subset_check(generated_at: datetime) -> None:
    pkg = PackageDeclaration(
        package_id="pkg",
        package_name="Pkg",
        module_path="hunter.pkg",
        expected_modules=("__init__.py", "models.py"),
        actual_modules_present=("__init__.py", "models.py", "engine.py"),
        safety_notices=("Research only.",),
        markdown_disclaimer="This is research-only output.",
    )
    inp = ReleaseHardeningInput(packages=(pkg,), generated_at=generated_at)
    report = build_release_hardening_report(inp)
    presence = next(r for r in report.checks if r.category == "package_presence")
    assert presence.state is ReleaseHardeningState.PASS


def test_caller_provided_test_artifact_isolation_opaque_strings(
    generated_at: datetime,
) -> None:
    pkg = PackageDeclaration(
        package_id="pkg",
        package_name="Pkg",
        module_path="hunter.pkg",
        expected_modules=("__init__.py",),
        actual_modules_present=("__init__.py",),
        writer_default_paths=("data/pkg/output.json",),
        test_default_paths=("tests/pkg/test_output.json",),
        safety_notices=("Research only.",),
        markdown_disclaimer="This is research-only output.",
    )
    inp = ReleaseHardeningInput(packages=(pkg,), generated_at=generated_at)
    report = build_release_hardening_report(inp)
    isolation = next(r for r in report.checks if r.category == "test_artifact_isolation")
    assert isolation.state is ReleaseHardeningState.PASS


# ---------------------------------------------------------------------------
# Empty actual behavior
# ---------------------------------------------------------------------------


def test_empty_advisory_actual_is_not_applicable_and_does_not_block(
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
    isolation = next(r for r in report.checks if r.category == "test_artifact_isolation")
    assert isolation.state is ReleaseHardeningState.NOT_APPLICABLE
    assert report.state is ReleaseHardeningState.PASS


def test_empty_blocking_actual_is_blocked(generated_at: datetime) -> None:
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
    public = next(r for r in report.checks if r.category == "public_exports")
    assert public.state is ReleaseHardeningState.BLOCKED
    assert report.state is ReleaseHardeningState.BLOCKED


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def test_non_strict_aggregation_blocked_over_degraded(generated_at: datetime) -> None:
    pkg = PackageDeclaration(
        package_id="pkg",
        package_name="Pkg",
        module_path="hunter.pkg",
        expected_modules=("__init__.py", "models.py"),
        actual_modules_present=("__init__.py",),
        writer_default_paths=("data/pkg/output.json",),
        test_default_paths=("data/pkg/test_output.json",),  # degraded
        safety_notices=("Research only.",),
        markdown_disclaimer="This is research-only output.",
    )
    inp = ReleaseHardeningInput(packages=(pkg,), generated_at=generated_at)
    report = build_release_hardening_report(inp)
    assert report.state is ReleaseHardeningState.BLOCKED


def test_non_strict_aggregation_degraded_when_no_blocked(generated_at: datetime) -> None:
    pkg = PackageDeclaration(
        package_id="pkg",
        package_name="Pkg",
        module_path="hunter.pkg",
        expected_modules=("__init__.py",),
        actual_modules_present=("__init__.py",),
        writer_default_paths=("data/pkg/output.json",),
        test_default_paths=("data/pkg/test_output.json",),  # degraded
        safety_notices=("Research only.",),
        markdown_disclaimer="This is research-only output.",
    )
    inp = ReleaseHardeningInput(packages=(pkg,), generated_at=generated_at)
    report = build_release_hardening_report(inp)
    assert report.state is ReleaseHardeningState.DEGRADED


def test_strict_aggregation_promotes_degraded_to_blocked(generated_at: datetime) -> None:
    pkg = PackageDeclaration(
        package_id="pkg",
        package_name="Pkg",
        module_path="hunter.pkg",
        expected_modules=("__init__.py",),
        actual_modules_present=("__init__.py",),
        writer_default_paths=("data/pkg/output.json",),
        test_default_paths=("data/pkg/test_output.json",),  # degraded
        safety_notices=("Research only.",),
        markdown_disclaimer="This is research-only output.",
    )
    config = ReleaseHardeningConfig(strict=True)
    inp = ReleaseHardeningInput(
        packages=(pkg,), generated_at=generated_at, config=config
    )
    report = build_release_hardening_report(inp)
    assert report.state is ReleaseHardeningState.BLOCKED
    assert ReleaseHardeningReasonCode.SAFETY_BLOCKED in report.reason_codes


def test_not_applicable_alone_does_not_block(generated_at: datetime) -> None:
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
    isolation = next(r for r in report.checks if r.category == "test_artifact_isolation")
    assert isolation.state is ReleaseHardeningState.NOT_APPLICABLE
    assert report.state is ReleaseHardeningState.PASS


# ---------------------------------------------------------------------------
# Version consistency
# ---------------------------------------------------------------------------


def test_patch_mismatch_degraded(generated_at: datetime) -> None:
    pkg = PackageDeclaration(
        package_id="pkg",
        package_name="Pkg",
        module_path="hunter.pkg",
        expected_modules=("__init__.py",),
        actual_modules_present=("__init__.py",),
        safety_notices=("Research only.",),
        markdown_disclaimer="This is research-only output.",
        version="0.33.0-dev",
    )
    inp = ReleaseHardeningInput(
        packages=(pkg,), project_version="0.33.1-dev", generated_at=generated_at
    )
    report = build_release_hardening_report(inp)
    version = next(r for r in report.checks if r.category == "version_consistency")
    assert version.state is ReleaseHardeningState.DEGRADED
    assert report.state is ReleaseHardeningState.DEGRADED


def test_major_mismatch_blocked(generated_at: datetime) -> None:
    pkg = PackageDeclaration(
        package_id="pkg",
        package_name="Pkg",
        module_path="hunter.pkg",
        expected_modules=("__init__.py",),
        actual_modules_present=("__init__.py",),
        safety_notices=("Research only.",),
        markdown_disclaimer="This is research-only output.",
        version="0.33.0-dev",
    )
    inp = ReleaseHardeningInput(
        packages=(pkg,), project_version="1.33.0-dev", generated_at=generated_at
    )
    report = build_release_hardening_report(inp)
    version = next(r for r in report.checks if r.category == "version_consistency")
    assert version.state is ReleaseHardeningState.BLOCKED
    assert report.state is ReleaseHardeningState.BLOCKED


# ---------------------------------------------------------------------------
# Fail-closed behavior
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
    inp = ReleaseHardeningInput(packages=(pkg, pkg), generated_at=generated_at)
    report = build_release_hardening_report(inp)
    assert report.state is ReleaseHardeningState.BLOCKED
    assert ReleaseHardeningReasonCode.DUPLICATE_PACKAGE_ID in report.reason_codes


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


def test_completed_package_artifact_path_policy_opaque_strings(
    generated_at: datetime,
) -> None:
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
        packages=(pkg,), completed_packages=(completed,), generated_at=generated_at
    )
    report = build_release_hardening_report(inp)
    policy = next(r for r in report.checks if r.category == "artifact_path_policy")
    assert policy.state is ReleaseHardeningState.BLOCKED


# ---------------------------------------------------------------------------
# Writer end-to-end
# ---------------------------------------------------------------------------


def _csv_rows(text: str) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(text))
    return list(reader)


def test_writer_end_to_end_creates_all_artifacts(pass_report: object, tmp_path: Path) -> None:
    json_path = tmp_path / "report.json"
    csv_path = tmp_path / "report.csv"
    md_path = tmp_path / "report.md"
    write_release_hardening_report(
        pass_report, json_path=json_path, csv_path=csv_path, md_path=md_path
    )
    assert json_path.exists()
    assert csv_path.exists()
    assert md_path.exists()

    parsed = json.loads(json_path.read_text())
    assert parsed["state"] == "pass"
    assert "checks" in parsed

    rows = _csv_rows(csv_path.read_text())
    assert rows
    assert "check_id" in rows[0]
    assert "category" in rows[0]

    md = md_path.read_text()
    assert md.startswith("# Release Hardening Report")
    assert "human-audit research artifact" in md
    assert "not trading advice" in md
    assert "not a certification of trading readiness" in md
    assert "## Summary" in md
    assert "## Data Quality" in md
    assert "## Checks by Category" in md
    assert "## Safety Flags" in md


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_end_to_end_determinism(pass_input: ReleaseHardeningInput) -> None:
    r1 = build_release_hardening_report(pass_input)
    r2 = build_release_hardening_report(pass_input)
    assert r1 == r2
    assert release_hardening_report_to_json_text(r1) == release_hardening_report_to_json_text(r2)
    assert release_hardening_report_to_csv_text(r1) == release_hardening_report_to_csv_text(r2)
    assert release_hardening_report_to_markdown_text(r1) == release_hardening_report_to_markdown_text(r2)


# ---------------------------------------------------------------------------
# No mutation
# ---------------------------------------------------------------------------


def test_build_report_does_not_mutate_input(pass_input: ReleaseHardeningInput) -> None:
    original_packages = pass_input.packages
    original_checks = pass_input.checks
    build_release_hardening_report(pass_input)
    assert pass_input.packages is original_packages
    assert pass_input.checks is original_checks


# ---------------------------------------------------------------------------
# Safety boundaries
# ---------------------------------------------------------------------------


def test_outputs_contain_research_only_language(pass_report: object) -> None:
    json_text = release_hardening_report_to_json_text(pass_report)
    md_text = release_hardening_report_to_markdown_text(pass_report)
    assert "human-audit research artifact" in json_text
    assert "human-audit research artifact" in md_text
    assert "not trading advice" in md_text
    assert "not a certification of trading readiness" in md_text


def test_outputs_no_actionable_trading_language(pass_report: object) -> None:
    md_text = release_hardening_report_to_markdown_text(pass_report).lower()
    assert "buy signal" not in md_text
    assert "sell signal" not in md_text
    assert "place orders" not in md_text
    assert "execute orders" not in md_text
    assert "go live" not in md_text
