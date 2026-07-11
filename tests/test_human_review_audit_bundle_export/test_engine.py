"""Tests for hunter.human_review_audit_bundle_export planner."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from hunter.human_review_audit_bundle import (
    HumanReviewAuditBundleReport,
    HumanReviewAuditBundleState,
)
from hunter.human_review_audit_bundle_export import (
    HumanReviewAuditBundleExportConfig,
    HumanReviewAuditBundleExportInput,
    HumanReviewAuditBundleExportReasonCode,
    HumanReviewAuditBundleExportSafetyFlags,
    HumanReviewAuditBundleExportSeverity,
    HumanReviewAuditBundleExportState,
    build_export_manifest_from_plan,
    plan_human_review_audit_bundle_export,
)
from hunter.human_review_audit_bundle_export.engine import (
    _resolve_output_path,
    _resolve_tmp_path,
    _validate_filename,
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


@pytest.fixture
def make_input(
    now: datetime,
    bundle_report: HumanReviewAuditBundleReport,
) -> Any:
    """Return a factory for HumanReviewAuditBundleExportInput."""

    def _factory(
        output_dir: Path,
        tmp_path: Path,
        format: str = "json",
        overwrite: bool = False,
        strict: bool = False,
        safety_scan: bool = True,
        dry_run: bool = False,
        metadata: dict[str, str] | None = None,
    ) -> HumanReviewAuditBundleExportInput:
        return HumanReviewAuditBundleExportInput(
            bundle_report=bundle_report,
            output_dir=output_dir,
            tmp_path=tmp_path,
            config=HumanReviewAuditBundleExportConfig(
                format=format,
                overwrite=overwrite,
                strict=strict,
                safety_scan=safety_scan,
                dry_run=dry_run,
            ),
            generated_at=now,
            metadata=metadata or {},
        )

    return _factory


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_valid_json_plan(tmp_path: Path, make_input: Any) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    tmp_dir = tmp_path / "tmp"
    tmp_dir.mkdir()

    input_obj = make_input(output_dir=output_dir, tmp_path=tmp_dir, format="json")
    plan = plan_human_review_audit_bundle_export(input_obj)

    assert plan.state == HumanReviewAuditBundleExportState.PLANNED
    assert plan.format == "json"
    assert plan.filename.endswith(".json")
    assert plan.content_hash
    assert plan.content_length > 0
    assert plan.output_path.startswith(str(output_dir))
    assert plan.tmp_path.startswith(str(tmp_dir))
    assert plan.safety_flags.is_safe is True
    assert plan.safety_flags.path_safe is True
    assert plan.safety_flags.hash_verified is False
    assert HumanReviewAuditBundleExportReasonCode.PLANNED in plan.reason_codes
    assert HumanReviewAuditBundleExportReasonCode.RESEARCH_ONLY in plan.reason_codes
    assert not plan.issues


def test_valid_markdown_plan(tmp_path: Path, make_input: Any) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    tmp_dir = tmp_path / "tmp"
    tmp_dir.mkdir()

    input_obj = make_input(output_dir=output_dir, tmp_path=tmp_dir, format="markdown")
    plan = plan_human_review_audit_bundle_export(input_obj)

    assert plan.state == HumanReviewAuditBundleExportState.PLANNED
    assert plan.format == "markdown"
    assert plan.filename.endswith(".md")
    assert plan.content_length > 0
    assert plan.safety_flags.is_safe is True


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_deterministic_filename(tmp_path: Path, make_input: Any) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    tmp_dir = tmp_path / "tmp"
    tmp_dir.mkdir()

    input1 = make_input(output_dir=output_dir, tmp_path=tmp_dir)
    input2 = make_input(output_dir=output_dir, tmp_path=tmp_dir)
    plan1 = plan_human_review_audit_bundle_export(input1)
    plan2 = plan_human_review_audit_bundle_export(input2)

    assert plan1.filename == plan2.filename
    assert plan1.report_id == plan2.report_id
    assert plan1.plan_id == plan2.plan_id
    assert plan1.content_hash == plan2.content_hash


def test_deterministic_plan_and_manifest_ids(tmp_path: Path, make_input: Any) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    tmp_dir = tmp_path / "tmp"
    tmp_dir.mkdir()

    input1 = make_input(output_dir=output_dir, tmp_path=tmp_dir)
    input2 = make_input(output_dir=output_dir, tmp_path=tmp_dir)
    plan1 = plan_human_review_audit_bundle_export(input1)
    plan2 = plan_human_review_audit_bundle_export(input2)
    manifest1 = build_export_manifest_from_plan(plan1)
    manifest2 = build_export_manifest_from_plan(plan2)

    assert plan1.plan_id == plan2.plan_id
    assert plan1.report_id == plan2.report_id
    assert manifest1.manifest_id == manifest2.manifest_id
    assert manifest1.report_id == manifest2.report_id


def test_content_hash_deterministic(tmp_path: Path, make_input: Any) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    tmp_dir = tmp_path / "tmp"
    tmp_dir.mkdir()

    input1 = make_input(output_dir=output_dir, tmp_path=tmp_dir)
    input2 = make_input(output_dir=output_dir, tmp_path=tmp_dir)
    plan1 = plan_human_review_audit_bundle_export(input1)
    plan2 = plan_human_review_audit_bundle_export(input2)

    assert plan1.content_hash == plan2.content_hash
    assert plan1.content_length == plan2.content_length


# ---------------------------------------------------------------------------
# Path safety
# ---------------------------------------------------------------------------


def test_invalid_filename_blocked() -> None:
    ok, reason = _validate_filename("../../etc/passwd.json")
    assert ok is False
    assert "parent traversal" in reason or "allowlist" in reason or "path separator" in reason


def test_absolute_filename_blocked() -> None:
    ok, reason = _validate_filename("/tmp/hra-bundle-export-abc123.json")
    assert ok is False
    assert "path separator" in reason


def test_parent_traversal_filename_blocked() -> None:
    ok, reason = _validate_filename("hra-bundle-export-abc123..json")
    assert ok is False
    assert "parent traversal" in reason


def test_output_dir_containment(tmp_path: Path) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    filename = "hra-bundle-export-abc123.json"
    path_str, issue = _resolve_output_path(output_dir, filename)
    assert path_str is not None
    assert issue is None
    assert Path(path_str).parent == output_dir.resolve()


def test_output_dir_traversal(tmp_path: Path) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    filename = "../other.json"
    path_str, issue = _resolve_output_path(output_dir, filename)
    assert path_str is None
    assert issue is not None
    assert issue.issue_type == "path_traversal_attempt"


def test_output_dir_missing_blocked(tmp_path: Path, make_input: Any) -> None:
    output_dir = tmp_path / "missing"
    tmp_dir = tmp_path / "tmp"
    tmp_dir.mkdir()

    input_obj = make_input(output_dir=output_dir, tmp_path=tmp_dir)
    plan = plan_human_review_audit_bundle_export(input_obj)

    assert plan.state == HumanReviewAuditBundleExportState.BLOCKED
    assert any(
        HumanReviewAuditBundleExportReasonCode.PATH_ERROR.value in i.reason_codes
        for i in plan.issues
    )
    assert plan.safety_flags.path_safe is False


def test_output_exists_blocked(tmp_path: Path, make_input: Any) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    tmp_dir = tmp_path / "tmp"
    tmp_dir.mkdir()

    # First plan to learn the filename.
    input1 = make_input(output_dir=output_dir, tmp_path=tmp_dir, overwrite=False)
    plan1 = plan_human_review_audit_bundle_export(input1)

    # Create the file the planner expects to write.
    output_path = Path(plan1.output_path)
    output_path.write_text("existing")

    input2 = make_input(output_dir=output_dir, tmp_path=tmp_dir, overwrite=False)
    plan2 = plan_human_review_audit_bundle_export(input2)

    assert plan2.state == HumanReviewAuditBundleExportState.BLOCKED
    assert any(
        HumanReviewAuditBundleExportReasonCode.OUTPUT_EXISTS.value in i.reason_codes
        for i in plan2.issues
    )


def test_output_exists_allowed_with_overwrite(tmp_path: Path, make_input: Any) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    tmp_dir = tmp_path / "tmp"
    tmp_dir.mkdir()

    input1 = make_input(output_dir=output_dir, tmp_path=tmp_dir, overwrite=True)
    plan1 = plan_human_review_audit_bundle_export(input1)
    output_path = Path(plan1.output_path)
    output_path.write_text("existing")

    input2 = make_input(output_dir=output_dir, tmp_path=tmp_dir, overwrite=True)
    plan2 = plan_human_review_audit_bundle_export(input2)

    assert plan2.state == HumanReviewAuditBundleExportState.PLANNED


# ---------------------------------------------------------------------------
# Safety scanner
# ---------------------------------------------------------------------------


def test_forbidden_phrase_blocked(tmp_path: Path, now: datetime, make_input: Any) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    tmp_dir = tmp_path / "tmp"
    tmp_dir.mkdir()

    # A bundle report whose notes contain a forbidden phrase outside the
    # safety notice will trigger the scanner.
    bad_report = HumanReviewAuditBundleReport(
        bundle_id="bundle-bad",
        report_id="bundle-report-bad",
        generated_at=now,
        state=HumanReviewAuditBundleState.OK,
        project_version="0.43.0-dev",
        notes="Please apply patch to fix this.",
    )
    input_obj = HumanReviewAuditBundleExportInput(
        bundle_report=bad_report,
        output_dir=output_dir,
        tmp_path=tmp_dir,
        generated_at=now,
    )
    plan = plan_human_review_audit_bundle_export(input_obj)

    assert plan.state == HumanReviewAuditBundleExportState.BLOCKED
    assert plan.safety_flags.is_safe is False
    assert any(
        HumanReviewAuditBundleExportReasonCode.FORBIDDEN_TERM_PRESENT.value in i.reason_codes
        for i in plan.issues
    )


def test_safety_scan_disabled_allows_forbidden_phrase(tmp_path: Path, now: datetime, make_input: Any) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    tmp_dir = tmp_path / "tmp"
    tmp_dir.mkdir()

    bad_report = HumanReviewAuditBundleReport(
        bundle_id="bundle-bad",
        report_id="bundle-report-bad",
        generated_at=now,
        state=HumanReviewAuditBundleState.OK,
        project_version="0.43.0-dev",
        notes="Please apply patch to fix this.",
    )
    input_obj = HumanReviewAuditBundleExportInput(
        bundle_report=bad_report,
        output_dir=output_dir,
        tmp_path=tmp_dir,
        config=HumanReviewAuditBundleExportConfig(safety_scan=False),
        generated_at=now,
    )
    plan = plan_human_review_audit_bundle_export(input_obj)

    assert plan.state == HumanReviewAuditBundleExportState.PLANNED
    assert plan.safety_flags.is_safe is True


# ---------------------------------------------------------------------------
# Upstream state carry-forward
# ---------------------------------------------------------------------------


def test_upstream_blocked_blocked(tmp_path: Path, now: datetime, make_input: Any) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    tmp_dir = tmp_path / "tmp"
    tmp_dir.mkdir()

    blocked_report = HumanReviewAuditBundleReport(
        bundle_id="bundle-blocked",
        report_id="bundle-report-blocked",
        generated_at=now,
        state=HumanReviewAuditBundleState.BLOCKED,
        project_version="0.43.0-dev",
    )
    input_obj = HumanReviewAuditBundleExportInput(
        bundle_report=blocked_report,
        output_dir=output_dir,
        tmp_path=tmp_dir,
        generated_at=now,
    )
    plan = plan_human_review_audit_bundle_export(input_obj)

    assert plan.state == HumanReviewAuditBundleExportState.BLOCKED
    assert any(
        HumanReviewAuditBundleExportReasonCode.UPSTREAM_BLOCKED.value in i.reason_codes
        for i in plan.issues
    )


def test_upstream_degraded_non_strict_planned(tmp_path: Path, now: datetime, make_input: Any) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    tmp_dir = tmp_path / "tmp"
    tmp_dir.mkdir()

    degraded_report = HumanReviewAuditBundleReport(
        bundle_id="bundle-degraded",
        report_id="bundle-report-degraded",
        generated_at=now,
        state=HumanReviewAuditBundleState.DEGRADED,
        project_version="0.43.0-dev",
    )
    input_obj = HumanReviewAuditBundleExportInput(
        bundle_report=degraded_report,
        output_dir=output_dir,
        tmp_path=tmp_dir,
        generated_at=now,
    )
    plan = plan_human_review_audit_bundle_export(input_obj)

    assert plan.state == HumanReviewAuditBundleExportState.PLANNED
    assert any(
        i.severity == HumanReviewAuditBundleExportSeverity.ADVISORY.value
        for i in plan.issues
    )


def test_upstream_degraded_strict_blocked(tmp_path: Path, now: datetime, make_input: Any) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    tmp_dir = tmp_path / "tmp"
    tmp_dir.mkdir()

    degraded_report = HumanReviewAuditBundleReport(
        bundle_id="bundle-degraded",
        report_id="bundle-report-degraded",
        generated_at=now,
        state=HumanReviewAuditBundleState.DEGRADED,
        project_version="0.43.0-dev",
    )
    input_obj = HumanReviewAuditBundleExportInput(
        bundle_report=degraded_report,
        output_dir=output_dir,
        tmp_path=tmp_dir,
        config=HumanReviewAuditBundleExportConfig(strict=True),
        generated_at=now,
    )
    plan = plan_human_review_audit_bundle_export(input_obj)

    assert plan.state == HumanReviewAuditBundleExportState.BLOCKED


def test_upstream_not_applicable(tmp_path: Path, now: datetime, make_input: Any) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    tmp_dir = tmp_path / "tmp"
    tmp_dir.mkdir()

    na_report = HumanReviewAuditBundleReport(
        bundle_id="bundle-na",
        report_id="bundle-report-na",
        generated_at=now,
        state=HumanReviewAuditBundleState.NOT_APPLICABLE,
        project_version="0.43.0-dev",
    )
    input_obj = HumanReviewAuditBundleExportInput(
        bundle_report=na_report,
        output_dir=output_dir,
        tmp_path=tmp_dir,
        generated_at=now,
    )
    plan = plan_human_review_audit_bundle_export(input_obj)

    assert plan.state == HumanReviewAuditBundleExportState.NOT_APPLICABLE
    assert any(
        HumanReviewAuditBundleExportReasonCode.UPSTREAM_NOT_APPLICABLE.value in i.reason_codes
        for i in plan.issues
    )


# ---------------------------------------------------------------------------
# Invalid format
# ---------------------------------------------------------------------------


def test_invalid_format_blocked(tmp_path: Path, make_input: Any) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    tmp_dir = tmp_path / "tmp"
    tmp_dir.mkdir()

    input_obj = make_input(output_dir=output_dir, tmp_path=tmp_dir, format="csv")
    plan = plan_human_review_audit_bundle_export(input_obj)

    assert plan.state == HumanReviewAuditBundleExportState.BLOCKED
    assert any(
        HumanReviewAuditBundleExportReasonCode.INVALID_FORMAT.value in i.reason_codes
        for i in plan.issues
    )


# ---------------------------------------------------------------------------
# No filesystem writes / no network
# ---------------------------------------------------------------------------


def test_no_filesystem_writes(tmp_path: Path, make_input: Any, monkeypatch: Any) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    tmp_dir = tmp_path / "tmp"
    tmp_dir.mkdir()

    import builtins

    original_open = builtins.open
    open_calls: list[tuple[Any, ...]] = []

    def patched_open(*args: Any, **kwargs: Any) -> Any:
        open_calls.append((args, kwargs))
        return original_open(*args, **kwargs)

    monkeypatch.setattr(builtins, "open", patched_open)

    input_obj = make_input(output_dir=output_dir, tmp_path=tmp_dir)
    plan = plan_human_review_audit_bundle_export(input_obj)
    build_export_manifest_from_plan(plan)

    assert open_calls == [], f"Planner unexpectedly opened files: {open_calls}"


# ---------------------------------------------------------------------------
# Opaque refs
# ---------------------------------------------------------------------------


def test_opaque_refs_not_opened_or_followed(tmp_path: Path, make_input: Any) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    tmp_dir = tmp_path / "tmp"
    tmp_dir.mkdir()

    input_obj = make_input(output_dir=output_dir, tmp_path=tmp_dir)
    plan = plan_human_review_audit_bundle_export(input_obj)

    # The plan carries the upstream bundle ID as an opaque string and does not
    # open or traverse it.
    assert plan.bundle_report_id == "bundle-abc123"
    assert "file://" not in plan.output_path
    assert "http://" not in plan.output_path
    assert "https://" not in plan.output_path


# ---------------------------------------------------------------------------
# Input not mutated
# ---------------------------------------------------------------------------


def test_input_not_mutated(tmp_path: Path, make_input: Any) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    tmp_dir = tmp_path / "tmp"
    tmp_dir.mkdir()

    input_obj = make_input(output_dir=output_dir, tmp_path=tmp_dir)
    original_id = id(input_obj.bundle_report)
    plan = plan_human_review_audit_bundle_export(input_obj)
    assert id(input_obj.bundle_report) == original_id
    assert plan.bundle_report_id == input_obj.bundle_report.bundle_id
