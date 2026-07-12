"""Tests for hunter.human_review_audit_bundle_export writer."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any

import pytest

from hunter.human_review_audit_bundle import (
    HumanReviewAuditBundleReport,
    HumanReviewAuditBundleState,
    SAFETY_NOTICE as BUNDLE_SAFETY_NOTICE,
)
from hunter.human_review_audit_bundle_export import (
    HumanReviewAuditBundleExportConfig,
    HumanReviewAuditBundleExportInput,
    HumanReviewAuditBundleExportManifest,
    HumanReviewAuditBundleExportReasonCode,
    HumanReviewAuditBundleExportState,
    SAFETY_NOTICE,
    export_human_review_audit_bundle_artifact,
    manifest_to_dict,
    manifest_to_json,
    plan_human_review_audit_bundle_export,
)
from hunter.human_review_audit_bundle_export.engine import (
    _ALLOWED_NEGATION_PHRASES,
    _FORBIDDEN_ACTION_PHRASES,
)
from hunter.human_review_audit_bundle_export.writer import (
    _atomic_write,
    _path_looks_like_url,
    export_human_review_audit_bundle_artifact,
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
        verify_hash: bool = True,
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
                verify_hash=verify_hash,
                dry_run=dry_run,
            ),
            generated_at=now,
            metadata=metadata or {},
        )

    return _factory


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def test_manifest_to_dict_shape(make_input: Any, tmp_path: Path) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    tmp_dir = tmp_path / "tmp"
    tmp_dir.mkdir()
    input_obj = make_input(output_dir=output_dir, tmp_path=tmp_dir)
    plan = plan_human_review_audit_bundle_export(input_obj)
    manifest = HumanReviewAuditBundleExportManifest(
        manifest_id="m-1",
        report_id=plan.report_id,
        bundle_report_id=plan.bundle_report_id,
        filename=plan.filename,
        output_path=plan.output_path,
        format=plan.format,
        content_hash=plan.content_hash,
        content_length=plan.content_length,
        state=HumanReviewAuditBundleExportState.WRITTEN,
        safety_flags=plan.safety_flags,
        reason_codes=plan.reason_codes,
        issues=plan.issues,
        metadata=plan.metadata,
        notes="test",
    )
    d = manifest_to_dict(manifest)
    assert d["manifest_id"] == "m-1"
    assert d["report_id"] == plan.report_id
    assert d["bundle_report_id"] == plan.bundle_report_id
    assert d["filename"] == plan.filename
    assert d["output_path"] == plan.output_path
    assert d["format"] == plan.format
    assert d["content_hash"] == plan.content_hash
    assert d["content_length"] == plan.content_length
    assert d["state"] == "written"
    assert d["safety_flags"]["is_safe"] is True
    assert d["reason_codes"] == [rc.value for rc in plan.reason_codes]
    assert d["issues"] == []
    assert d["metadata"] == {}
    assert d["notes"] == "test"


def test_manifest_to_json_deterministic(make_input: Any, tmp_path: Path) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    tmp_dir = tmp_path / "tmp"
    tmp_dir.mkdir()
    input_obj = make_input(output_dir=output_dir, tmp_path=tmp_dir)
    plan = plan_human_review_audit_bundle_export(input_obj)
    manifest = HumanReviewAuditBundleExportManifest(
        manifest_id="m-1",
        report_id=plan.report_id,
        bundle_report_id=plan.bundle_report_id,
        filename=plan.filename,
        output_path=plan.output_path,
        format=plan.format,
        content_hash=plan.content_hash,
        content_length=plan.content_length,
        state=HumanReviewAuditBundleExportState.WRITTEN,
        safety_flags=plan.safety_flags,
        reason_codes=plan.reason_codes,
        issues=plan.issues,
        metadata=plan.metadata,
        notes="test",
    )
    json1 = manifest_to_json(manifest)
    json2 = manifest_to_json(manifest)
    assert json1 == json2


# ---------------------------------------------------------------------------
# Atomic write and export success
# ---------------------------------------------------------------------------


def test_export_artifact_json_success(make_input: Any, tmp_path: Path) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    tmp_dir = tmp_path / "tmp"
    tmp_dir.mkdir()
    input_obj = make_input(output_dir=output_dir, tmp_path=tmp_dir, format="json")
    plan = plan_human_review_audit_bundle_export(input_obj)

    manifest = export_human_review_audit_bundle_artifact(input_obj)

    assert manifest.state == HumanReviewAuditBundleExportState.WRITTEN
    assert manifest.safety_flags.hash_verified is True
    assert manifest.content_hash == plan.content_hash
    assert manifest.content_length == plan.content_length
    assert manifest.output_path == plan.output_path
    assert HumanReviewAuditBundleExportReasonCode.WRITTEN in manifest.reason_codes
    assert HumanReviewAuditBundleExportReasonCode.RESEARCH_ONLY in manifest.reason_codes
    output_file = Path(manifest.output_path)
    assert output_file.exists()
    written_bytes = output_file.read_bytes()
    assert sha256(written_bytes).hexdigest() == plan.content_hash
    assert len(written_bytes) == plan.content_length


def test_export_artifact_markdown_success(make_input: Any, tmp_path: Path) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    tmp_dir = tmp_path / "tmp"
    tmp_dir.mkdir()
    input_obj = make_input(output_dir=output_dir, tmp_path=tmp_dir, format="markdown")
    plan = plan_human_review_audit_bundle_export(input_obj)

    manifest = export_human_review_audit_bundle_artifact(input_obj)

    assert manifest.state == HumanReviewAuditBundleExportState.WRITTEN
    assert manifest.safety_flags.hash_verified is True
    assert manifest.format == "markdown"
    assert manifest.content_hash == plan.content_hash
    output_file = Path(manifest.output_path)
    assert output_file.exists()
    body = output_file.read_text()
    assert body
    assert "bundle-abc123" in body


# ---------------------------------------------------------------------------
# Dry run / blocked / no-write paths
# ---------------------------------------------------------------------------


def test_export_artifact_dry_run_no_write(make_input: Any, tmp_path: Path) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    tmp_dir = tmp_path / "tmp"
    tmp_dir.mkdir()
    input_obj = make_input(output_dir=output_dir, tmp_path=tmp_dir, dry_run=True)

    manifest = export_human_review_audit_bundle_artifact(input_obj)

    assert manifest.state == HumanReviewAuditBundleExportState.PLANNED
    assert manifest.safety_flags.hash_verified is False
    assert not (output_dir / input_obj.filename).exists() if hasattr(input_obj, "filename") else True
    assert list(output_dir.iterdir()) == []


def test_export_artifact_blocked_plan_no_write(make_input: Any, tmp_path: Path) -> None:
    output_dir = tmp_path / "output"
    tmp_dir = tmp_path / "tmp"
    tmp_dir.mkdir()
    # Output dir missing -> planner blocks.
    input_obj = make_input(output_dir=output_dir, tmp_path=tmp_dir)

    manifest = export_human_review_audit_bundle_artifact(input_obj)

    assert manifest.state == HumanReviewAuditBundleExportState.BLOCKED
    assert HumanReviewAuditBundleExportReasonCode.PATH_ERROR in manifest.reason_codes
    assert not output_dir.exists()


def test_export_artifact_upstream_blocked_no_write(
    make_input: Any,
    tmp_path: Path,
    bundle_report: HumanReviewAuditBundleReport,
    now: datetime,
) -> None:
    blocked_report = HumanReviewAuditBundleReport(
        bundle_id=bundle_report.bundle_id,
        report_id=bundle_report.report_id,
        generated_at=now,
        state=HumanReviewAuditBundleState.BLOCKED,
        project_version="0.43.0-dev",
    )
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    tmp_dir = tmp_path / "tmp"
    tmp_dir.mkdir()
    input_obj = HumanReviewAuditBundleExportInput(
        bundle_report=blocked_report,
        output_dir=output_dir,
        tmp_path=tmp_dir,
        config=HumanReviewAuditBundleExportConfig(),
        generated_at=now,
    )

    manifest = export_human_review_audit_bundle_artifact(input_obj)

    assert manifest.state == HumanReviewAuditBundleExportState.BLOCKED
    assert HumanReviewAuditBundleExportReasonCode.UPSTREAM_BLOCKED in manifest.reason_codes
    assert list(output_dir.iterdir()) == []


def test_export_artifact_not_applicable_no_write(
    make_input: Any,
    tmp_path: Path,
    bundle_report: HumanReviewAuditBundleReport,
    now: datetime,
) -> None:
    na_report = HumanReviewAuditBundleReport(
        bundle_id=bundle_report.bundle_id,
        report_id=bundle_report.report_id,
        generated_at=now,
        state=HumanReviewAuditBundleState.NOT_APPLICABLE,
        project_version="0.43.0-dev",
    )
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    tmp_dir = tmp_path / "tmp"
    tmp_dir.mkdir()
    input_obj = HumanReviewAuditBundleExportInput(
        bundle_report=na_report,
        output_dir=output_dir,
        tmp_path=tmp_dir,
        config=HumanReviewAuditBundleExportConfig(),
        generated_at=now,
    )

    manifest = export_human_review_audit_bundle_artifact(input_obj)

    assert manifest.state == HumanReviewAuditBundleExportState.NOT_APPLICABLE
    assert HumanReviewAuditBundleExportReasonCode.NOT_APPLICABLE in manifest.reason_codes


# ---------------------------------------------------------------------------
# Hash verification and tampering
# ---------------------------------------------------------------------------


def test_export_artifact_hash_verification_disabled(make_input: Any, tmp_path: Path) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    tmp_dir = tmp_path / "tmp"
    tmp_dir.mkdir()
    input_obj = make_input(output_dir=output_dir, tmp_path=tmp_dir, verify_hash=False)

    manifest = export_human_review_audit_bundle_artifact(input_obj)

    assert manifest.state == HumanReviewAuditBundleExportState.WRITTEN
    assert manifest.safety_flags.hash_verified is False
    output_file = Path(manifest.output_path)
    assert output_file.exists()


def test_export_artifact_hash_mismatch_blocked(
    make_input: Any,
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    tmp_dir = tmp_path / "tmp"
    tmp_dir.mkdir()
    input_obj = make_input(output_dir=output_dir, tmp_path=tmp_dir)

    def _tampered_atomic_write(body_bytes: bytes, tmp_path: Path, output_path: Path) -> None:
        _atomic_write(b"tampered-content", tmp_path, output_path)

    monkeypatch.setattr(
        "hunter.human_review_audit_bundle_export.writer._atomic_write",
        _tampered_atomic_write,
    )

    manifest = export_human_review_audit_bundle_artifact(input_obj)

    assert manifest.state == HumanReviewAuditBundleExportState.BLOCKED
    assert HumanReviewAuditBundleExportReasonCode.HASH_MISMATCH in manifest.reason_codes
    assert any(issue.issue_type == "hash_mismatch" for issue in manifest.issues)
    output_file = Path(manifest.output_path)
    assert output_file.read_bytes() == b"tampered-content"


def test_export_artifact_truncated_file_blocked(
    make_input: Any,
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    tmp_dir = tmp_path / "tmp"
    tmp_dir.mkdir()
    input_obj = make_input(output_dir=output_dir, tmp_path=tmp_dir)
    plan = plan_human_review_audit_bundle_export(input_obj)

    def _truncated_atomic_write(body_bytes: bytes, tmp_path: Path, output_path: Path) -> None:
        # Write the correct body but then truncate one byte; hash verification must catch this.
        _atomic_write(body_bytes, tmp_path, output_path)
        output_path.write_bytes(output_path.read_bytes()[:-1])

    monkeypatch.setattr(
        "hunter.human_review_audit_bundle_export.writer._atomic_write",
        _truncated_atomic_write,
    )

    manifest = export_human_review_audit_bundle_artifact(input_obj)

    assert manifest.state == HumanReviewAuditBundleExportState.BLOCKED
    assert manifest.content_hash == plan.content_hash
    assert HumanReviewAuditBundleExportReasonCode.HASH_MISMATCH in manifest.reason_codes
    assert any(issue.issue_type in ("hash_mismatch", "length_mismatch") for issue in manifest.issues)


# ---------------------------------------------------------------------------
# Overwrite behavior
# ---------------------------------------------------------------------------


def test_export_artifact_overwrite_denied(make_input: Any, tmp_path: Path) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    tmp_dir = tmp_path / "tmp"
    tmp_dir.mkdir()
    input_obj = make_input(output_dir=output_dir, tmp_path=tmp_dir, overwrite=False)

    # First write succeeds.
    manifest1 = export_human_review_audit_bundle_artifact(input_obj)
    assert manifest1.state == HumanReviewAuditBundleExportState.WRITTEN

    # Second write without overwrite should block.
    manifest2 = export_human_review_audit_bundle_artifact(input_obj)
    assert manifest2.state == HumanReviewAuditBundleExportState.BLOCKED
    assert HumanReviewAuditBundleExportReasonCode.OUTPUT_EXISTS in manifest2.reason_codes


def test_export_artifact_overwrite_allowed(make_input: Any, tmp_path: Path) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    tmp_dir = tmp_path / "tmp"
    tmp_dir.mkdir()
    input_obj = make_input(output_dir=output_dir, tmp_path=tmp_dir, overwrite=True)

    manifest1 = export_human_review_audit_bundle_artifact(input_obj)
    assert manifest1.state == HumanReviewAuditBundleExportState.WRITTEN

    manifest2 = export_human_review_audit_bundle_artifact(input_obj)
    assert manifest2.state == HumanReviewAuditBundleExportState.WRITTEN
    assert Path(manifest2.output_path).exists()


# ---------------------------------------------------------------------------
# Path safety
# ---------------------------------------------------------------------------


def test_export_artifact_path_traversal_blocked(
    make_input: Any,
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    tmp_dir = tmp_path / "tmp"
    tmp_dir.mkdir()
    input_obj = make_input(output_dir=output_dir, tmp_path=tmp_dir)

    monkeypatch.setattr(
        "hunter.human_review_audit_bundle_export.writer._build_body",
        lambda _report, _format: "body",
    )
    monkeypatch.setattr(
        "hunter.human_review_audit_bundle_export.engine._build_filename",
        lambda _bundle_id, _generated_at, _format, _metadata: "../other.json",
    )

    manifest = export_human_review_audit_bundle_artifact(input_obj)

    assert manifest.state == HumanReviewAuditBundleExportState.BLOCKED
    assert HumanReviewAuditBundleExportReasonCode.PATH_TRAVERSAL_ATTEMPT in manifest.reason_codes
    output_file = Path(output_dir) / "../other.json"
    assert not output_file.exists()


def test_export_artifact_url_like_path_blocked(
    make_input: Any,
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    tmp_dir = tmp_path / "tmp"
    tmp_dir.mkdir()
    input_obj = make_input(output_dir=output_dir, tmp_path=tmp_dir)

    monkeypatch.setattr(
        "hunter.human_review_audit_bundle_export.engine._build_filename",
        lambda _bundle_id, _generated_at, _format, _metadata: "http://example.com/test.json",
    )

    manifest = export_human_review_audit_bundle_artifact(input_obj)

    assert manifest.state == HumanReviewAuditBundleExportState.BLOCKED


def test_path_looks_like_url() -> None:
    assert _path_looks_like_url("http://example.com/test.json") is True
    assert _path_looks_like_url("https://example.com/test.json") is True
    assert _path_looks_like_url("file:///etc/passwd") is True
    assert _path_looks_like_url("test.json") is False


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_export_artifact_deterministic_manifest(make_input: Any, tmp_path: Path) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    tmp_dir = tmp_path / "tmp"
    tmp_dir.mkdir()
    input_obj = make_input(output_dir=output_dir, tmp_path=tmp_dir)

    manifest1 = export_human_review_audit_bundle_artifact(input_obj)
    output_path1 = Path(manifest1.output_path)
    body1 = output_path1.read_text()

    manifest2 = export_human_review_audit_bundle_artifact(input_obj)
    output_path2 = Path(manifest2.output_path)
    body2 = output_path2.read_text()

    assert manifest1.content_hash == manifest2.content_hash
    assert manifest1.manifest_id == manifest2.manifest_id
    assert manifest1.content_length == manifest2.content_length
    assert body1 == body2


# ---------------------------------------------------------------------------
# Safety boundaries in generated artifact body
# ---------------------------------------------------------------------------


def test_generated_artifact_body_no_forbidden_phrases(make_input: Any, tmp_path: Path) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    tmp_dir = tmp_path / "tmp"
    tmp_dir.mkdir()
    input_obj = make_input(output_dir=output_dir, tmp_path=tmp_dir)

    manifest = export_human_review_audit_bundle_artifact(input_obj)
    output_file = Path(manifest.output_path)
    body = output_file.read_text()
    body_without_safety = body
    for text in (BUNDLE_SAFETY_NOTICE, SAFETY_NOTICE):
        body_without_safety = body_without_safety.replace(text, "")
    for allowed in _ALLOWED_NEGATION_PHRASES:
        body_without_safety = body_without_safety.replace(allowed, "")
    body_lower = body_without_safety.lower()
    for phrase in _FORBIDDEN_ACTION_PHRASES:
        assert phrase not in body_lower, f"forbidden phrase found: {phrase}"


# ---------------------------------------------------------------------------
# No writes outside tmp_path
# ---------------------------------------------------------------------------


def test_export_artifact_no_writes_outside_tmp_path(make_input: Any, tmp_path: Path) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    tmp_dir = tmp_path / "tmp"
    tmp_dir.mkdir()
    input_obj = make_input(output_dir=output_dir, tmp_path=tmp_dir)

    before = set(tmp_path.rglob("*"))
    export_human_review_audit_bundle_artifact(input_obj)
    after = set(tmp_path.rglob("*"))

    created = after - before
    assert len(created) == 1
    created_file = next(iter(created))
    assert created_file.is_file()
    assert created_file.parent == output_dir


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def test_public_exports() -> None:
    from hunter.human_review_audit_bundle_export import (
        export_human_review_audit_bundle_artifact,
        manifest_to_dict,
        manifest_to_json,
    )

    assert callable(export_human_review_audit_bundle_artifact)
    assert callable(manifest_to_dict)
    assert callable(manifest_to_json)


# ---------------------------------------------------------------------------
# No runtime/server/network/trading behavior
# ---------------------------------------------------------------------------


def test_export_artifact_no_network_or_runtime_behavior(
    make_input: Any,
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    tmp_dir = tmp_path / "tmp"
    tmp_dir.mkdir()
    input_obj = make_input(output_dir=output_dir, tmp_path=tmp_dir)

    # Any socket or network attempt should fail the test.
    def _fail_socket(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("network call attempted")

    monkeypatch.setattr("socket.socket", _fail_socket)
    monkeypatch.setattr("urllib.request.urlopen", _fail_socket)

    manifest = export_human_review_audit_bundle_artifact(input_obj)
    assert manifest.state == HumanReviewAuditBundleExportState.WRITTEN
