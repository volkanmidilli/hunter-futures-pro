"""Controlled writer/exporter for hunter.human_review_audit_bundle_export.

MVP-44 Step 2 — Local Research Human Review Audit Bundle Export Artifact.

The exporter performs atomic local writes to caller-supplied paths only. It never
opens, follows, traverses, validates, fetches, or executes upstream reference
strings. It reuses the Step 1 planner for safety scanning and path planning.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
from json import dumps
from os import fsync, replace
from pathlib import Path
from typing import Any

from hunter.human_review_audit_bundle_export.engine import (
    _build_body,
    _build_issue_id,
    _build_manifest_id,
    _build_reason_codes,
    build_export_manifest_from_plan,
    plan_human_review_audit_bundle_export,
)
from .models import (
    HumanReviewAuditBundleExportInput,
    HumanReviewAuditBundleExportIssue,
    HumanReviewAuditBundleExportManifest,
    HumanReviewAuditBundleExportPlan,
    HumanReviewAuditBundleExportReasonCode,
    HumanReviewAuditBundleExportSafetyFlags,
    HumanReviewAuditBundleExportSeverity,
    HumanReviewAuditBundleExportState,
)


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def _enum_value(value: Enum) -> str:
    return str(value.value)


def _iso_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat()


def _sorted_str_dict(value: Mapping[str, str]) -> dict[str, str]:
    return {k: str(v) for k, v in sorted(value.items())}


def _issue_to_dict(issue: HumanReviewAuditBundleExportIssue) -> dict[str, Any]:
    return {
        "issue_id": issue.issue_id,
        "issue_type": issue.issue_type,
        "severity": issue.severity,
        "reason_codes": list(issue.reason_codes),
        "source": issue.source,
        "title": issue.title,
        "description": issue.description,
        "generated_at": _iso_datetime(issue.generated_at),
    }


def _safety_flags_to_dict(flags: HumanReviewAuditBundleExportSafetyFlags) -> dict[str, Any]:
    return {
        "is_safe": flags.is_safe,
        "audit_only": flags.audit_only,
        "no_executable_actions": flags.no_executable_actions,
        "no_trading_instructions": flags.no_trading_instructions,
        "no_approval_claims": flags.no_approval_claims,
        "references_opaque": flags.references_opaque,
        "no_network": flags.no_network,
        "no_server": flags.no_server,
        "path_safe": flags.path_safe,
        "hash_verified": flags.hash_verified,
    }


def manifest_to_dict(manifest: HumanReviewAuditBundleExportManifest) -> dict[str, Any]:
    """Return a JSON-compatible ordered dict for the manifest."""
    return {
        "manifest_id": manifest.manifest_id,
        "report_id": manifest.report_id,
        "bundle_report_id": manifest.bundle_report_id,
        "filename": manifest.filename,
        "output_path": manifest.output_path,
        "format": manifest.format,
        "content_hash": manifest.content_hash,
        "content_length": manifest.content_length,
        "state": _enum_value(manifest.state),
        "safety_flags": _safety_flags_to_dict(manifest.safety_flags),
        "reason_codes": [_enum_value(rc) for rc in manifest.reason_codes],
        "issues": [_issue_to_dict(issue) for issue in manifest.issues],
        "metadata": _sorted_str_dict(manifest.metadata),
        "notes": manifest.notes,
    }


def manifest_to_json(
    manifest: HumanReviewAuditBundleExportManifest,
    *,
    indent: int | None = 2,
    ensure_ascii: bool = False,
) -> str:
    """Return a deterministic JSON string for the manifest."""
    return dumps(
        manifest_to_dict(manifest),
        indent=indent,
        ensure_ascii=ensure_ascii,
        sort_keys=False,
        default=str,
    )


# ---------------------------------------------------------------------------
# Path safety helpers
# ---------------------------------------------------------------------------


_URL_SCHEMES = ("file://", "http://", "https://", "ftp://", "ftps://")


def _path_looks_like_url(path: str) -> bool:
    lower = path.lower()
    return any(lower.startswith(scheme) for scheme in _URL_SCHEMES)


def _strict_path_containment(path: Path, directory: Path) -> bool:
    """Return True if path resides directly under directory (no subdirs)."""
    resolved_path = path.resolve()
    resolved_dir = directory.resolve()
    return resolved_path.parent == resolved_dir


# ---------------------------------------------------------------------------
# Manifest builders
# ---------------------------------------------------------------------------


def _copy_safety_flags_with_hash_verified(
    flags: HumanReviewAuditBundleExportSafetyFlags,
    hash_verified: bool,
) -> HumanReviewAuditBundleExportSafetyFlags:
    return HumanReviewAuditBundleExportSafetyFlags(
        is_safe=flags.is_safe,
        audit_only=flags.audit_only,
        no_executable_actions=flags.no_executable_actions,
        no_trading_instructions=flags.no_trading_instructions,
        no_approval_claims=flags.no_approval_claims,
        references_opaque=flags.references_opaque,
        no_network=flags.no_network,
        no_server=flags.no_server,
        path_safe=flags.path_safe,
        hash_verified=hash_verified,
    )


def _written_manifest_from_plan(
    plan: HumanReviewAuditBundleExportPlan,
    hash_verified: bool,
) -> HumanReviewAuditBundleExportManifest:
    """Build a WRITTEN manifest from a verified plan."""
    base = build_export_manifest_from_plan(
        plan,
        state_override=HumanReviewAuditBundleExportState.WRITTEN,
    )
    return HumanReviewAuditBundleExportManifest(
        manifest_id=base.manifest_id,
        report_id=base.report_id,
        bundle_report_id=base.bundle_report_id,
        filename=base.filename,
        output_path=base.output_path,
        format=base.format,
        content_hash=base.content_hash,
        content_length=base.content_length,
        state=base.state,
        safety_flags=_copy_safety_flags_with_hash_verified(base.safety_flags, hash_verified),
        reason_codes=_build_reason_codes(HumanReviewAuditBundleExportState.WRITTEN, plan.issues),
        issues=base.issues,
        metadata=base.metadata,
        notes="Export artifact written and verified.",
    )


def _build_blocked_manifest_from_plan_with_issue(
    plan: HumanReviewAuditBundleExportPlan,
    issue: HumanReviewAuditBundleExportIssue,
) -> HumanReviewAuditBundleExportManifest:
    """Build a BLOCKED manifest from a plan with an additional write-phase issue."""
    new_issues = plan.issues + (issue,)
    new_reason_codes = _build_reason_codes(HumanReviewAuditBundleExportState.BLOCKED, new_issues)
    safety_flags = _copy_safety_flags_with_hash_verified(plan.safety_flags, False)
    manifest_id = _build_manifest_id(
        plan.report_id,
        plan.output_path,
        plan.content_hash,
        plan.generated_at,
    )
    return HumanReviewAuditBundleExportManifest(
        manifest_id=manifest_id,
        report_id=plan.report_id,
        bundle_report_id=plan.bundle_report_id,
        filename=plan.filename,
        output_path=plan.output_path,
        format=plan.format,
        content_hash=plan.content_hash,
        content_length=plan.content_length,
        state=HumanReviewAuditBundleExportState.BLOCKED,
        safety_flags=safety_flags,
        reason_codes=new_reason_codes,
        issues=new_issues,
        metadata=plan.metadata,
        notes="Export blocked during write phase.",
    )


def _build_write_phase_issue(
    issue_type: str,
    title: str,
    description: str,
    reason_code: HumanReviewAuditBundleExportReasonCode,
    generated_at: datetime,
    counter: int,
) -> HumanReviewAuditBundleExportIssue:
    return HumanReviewAuditBundleExportIssue(
        issue_id=_build_issue_id(issue_type, "write_phase", title, counter),
        issue_type=issue_type,
        severity=HumanReviewAuditBundleExportSeverity.BLOCKING.value,
        reason_codes=(reason_code.value,),
        source="write_phase",
        title=title,
        description=description,
        generated_at=generated_at,
    )


# ---------------------------------------------------------------------------
# Atomic write helpers
# ---------------------------------------------------------------------------


def _atomic_write(body_bytes: bytes, tmp_path: Path, output_path: Path) -> None:
    """Write to tmp_path, fsync, then atomically replace output_path."""
    tmp_path.parent.mkdir(parents=True, exist_ok=True)
    with open(tmp_path, "wb") as f:
        f.write(body_bytes)
        f.flush()
        fsync(f.fileno())
    replace(str(tmp_path), str(output_path))


# ---------------------------------------------------------------------------
# Exporter
# ---------------------------------------------------------------------------


def export_human_review_audit_bundle_artifact(
    input: HumanReviewAuditBundleExportInput,  # noqa: A002
) -> HumanReviewAuditBundleExportManifest:
    """Export the audit bundle artifact to a local path.

    The function is pure except for the controlled filesystem write sequence:
      1. Call the Step 1 planner to obtain a safe plan.
      2. If the plan is BLOCKED, return the corresponding BLOCKED manifest.
      3. If the plan is NOT_APPLICABLE, return a NOT_APPLICABLE manifest without writing.
      4. If dry_run is set, return a PLANNED manifest without writing.
      5. Re-validate path containment and URL-like schemes.
      6. Atomically write the body to tmp_path, then move to output_path.
      7. Optionally verify the written hash/length against the plan.
      8. Return a WRITTEN manifest only after verification succeeds.
    """
    plan = plan_human_review_audit_bundle_export(input)

    if plan.state == HumanReviewAuditBundleExportState.BLOCKED:
        return build_export_manifest_from_plan(plan)

    if input.config.dry_run:
        return build_export_manifest_from_plan(plan, state_override=HumanReviewAuditBundleExportState.PLANNED)

    if plan.state == HumanReviewAuditBundleExportState.NOT_APPLICABLE:
        return build_export_manifest_from_plan(plan)

    output_dir = input.output_dir
    tmp_path_dir = input.tmp_path
    output_path = Path(plan.output_path)
    tmp_path = Path(plan.tmp_path)
    generated_at = plan.generated_at
    body = _build_body(input.bundle_report, plan.format)
    body_bytes = body.encode("utf-8")
    counter = len(plan.issues) + 1

    # URL-like scheme rejection.
    if _path_looks_like_url(plan.output_path) or _path_looks_like_url(plan.tmp_path):
        return _build_blocked_manifest_from_plan_with_issue(
            plan,
            _build_write_phase_issue(
                issue_type="url_like_path",
                title="URL-like path detected",
                description="Output or temporary path starts with a URL scheme.",
                reason_code=HumanReviewAuditBundleExportReasonCode.PATH_TRAVERSAL_ATTEMPT,
                generated_at=generated_at,
                counter=counter,
            ),
        )

    # Strict path containment re-check before writing.
    if not _strict_path_containment(output_path, output_dir):
        return _build_blocked_manifest_from_plan_with_issue(
            plan,
            _build_write_phase_issue(
                issue_type="path_traversal_attempt",
                title="Output path escapes caller-supplied directory",
                description=f"Resolved output path {str(output_path)!r} is not under {str(output_dir.resolve())!r}.",
                reason_code=HumanReviewAuditBundleExportReasonCode.PATH_TRAVERSAL_ATTEMPT,
                generated_at=generated_at,
                counter=counter,
            ),
        )
    if not _strict_path_containment(tmp_path, tmp_path_dir):
        return _build_blocked_manifest_from_plan_with_issue(
            plan,
            _build_write_phase_issue(
                issue_type="path_traversal_attempt",
                title="Temporary path escapes caller-supplied directory",
                description=f"Resolved temporary path {str(tmp_path)!r} is not under {str(tmp_path_dir.resolve())!r}.",
                reason_code=HumanReviewAuditBundleExportReasonCode.PATH_TRAVERSAL_ATTEMPT,
                generated_at=generated_at,
                counter=counter,
            ),
        )

    # Output directory must already exist (SPEC: writer does not create it).
    if not output_dir.exists():
        return _build_blocked_manifest_from_plan_with_issue(
            plan,
            _build_write_phase_issue(
                issue_type="output_dir_missing",
                title="Output directory does not exist",
                description=f"Caller-supplied output directory {str(output_dir)!r} does not exist.",
                reason_code=HumanReviewAuditBundleExportReasonCode.PATH_ERROR,
                generated_at=generated_at,
                counter=counter,
            ),
        )

    # Overwrite check at write time (planner checked earlier, but state may have changed).
    if output_path.exists() and not input.config.overwrite:
        return _build_blocked_manifest_from_plan_with_issue(
            plan,
            _build_write_phase_issue(
                issue_type="output_exists",
                title="Output file already exists",
                description=f"Output path {str(output_path)!r} already exists and overwrite is False.",
                reason_code=HumanReviewAuditBundleExportReasonCode.OUTPUT_EXISTS,
                generated_at=generated_at,
                counter=counter,
            ),
        )

    _atomic_write(body_bytes, tmp_path, output_path)

    verify_hash = input.config.verify_hash
    if verify_hash:
        written_bytes = output_path.read_bytes()
        written_hash = sha256(written_bytes).hexdigest()
        if written_hash != plan.content_hash:
            return _build_blocked_manifest_from_plan_with_issue(
                plan,
                _build_write_phase_issue(
                    issue_type="hash_mismatch",
                    title="Hash verification failed",
                    description=f"Expected {plan.content_hash}, got {written_hash}.",
                    reason_code=HumanReviewAuditBundleExportReasonCode.HASH_MISMATCH,
                    generated_at=generated_at,
                    counter=counter,
                ),
            )

    if verify_hash:
        written_length = output_path.stat().st_size
        if written_length != plan.content_length:
            return _build_blocked_manifest_from_plan_with_issue(
                plan,
                _build_write_phase_issue(
                    issue_type="length_mismatch",
                    title="Content length verification failed",
                    description=f"Expected {plan.content_length} bytes, got {written_length}.",
                    reason_code=HumanReviewAuditBundleExportReasonCode.HASH_MISMATCH,
                    generated_at=generated_at,
                    counter=counter,
                ),
            )

    return _written_manifest_from_plan(plan, hash_verified=verify_hash)


__all__ = [
    "export_human_review_audit_bundle_artifact",
    "manifest_to_dict",
    "manifest_to_json",
]
