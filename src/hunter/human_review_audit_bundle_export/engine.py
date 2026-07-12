"""Pure planner for hunter.human_review_audit_bundle_export.

MVP-44 — Local Research Human Review Audit Bundle Export Artifact.

The planner is deterministic, does not touch the filesystem, and never opens,
follows, traverses, validates, fetches, or executes any reference string. It
accepts a caller-provided in-memory bundle report and explicit local output
and temporary directories, then produces a deterministic export plan. In Step 1
no file is written; the writer/exporter is added in Step 2.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from json import dumps
from pathlib import Path
from typing import Any

from hunter.human_review_audit_bundle import (
    SAFETY_NOTICE as BUNDLE_SAFETY_NOTICE,
    HumanReviewAuditBundleReport,
    HumanReviewAuditBundleState,
    bundle_report_to_json,
    bundle_report_to_markdown,
)

from .models import (
    EXPORT_KIND,
    HUMAN_REVIEW_AUDIT_BUNDLE_EXPORT_VERSION,
    MANIFEST_KIND,
    HumanReviewAuditBundleExportConfig,
    HumanReviewAuditBundleExportIssue,
    HumanReviewAuditBundleExportManifest,
    HumanReviewAuditBundleExportPlan,
    HumanReviewAuditBundleExportReasonCode,
    HumanReviewAuditBundleExportSafetyFlags,
    HumanReviewAuditBundleExportSeverity,
    HumanReviewAuditBundleExportState,
    SAFETY_NOTICE,
)


# ---------------------------------------------------------------------------
# Forbidden / allowed phrase lists
# ---------------------------------------------------------------------------

# Forbidden action phrases that must not appear in generated artifact bodies
# outside of the explicit safety notice or safety-flag field names.
_FORBIDDEN_ACTION_PHRASES: tuple[str, ...] = (
    "shell command",
    "run this command",
    "execute now",
    "execute order",
    "apply patch",
    "deploy immediately",
    "push to production",
    "release to production",
    "infrastructure change",
    "automated remediation",
    "executable remediation",
    "auto fix",
    "self healing",
    "place order",
    "buy signal",
    "sell signal",
    "hold signal",
    "live trading",
    "go live",
    "trading ready",
    "ready for trading",
    "recommendation to trade",
    "suitable for trading",
    "approved for deployment",
    "approved for production",
    "production ready",
    "certified safe",
    "decision approved",
    "decision certified",
    "binance key",
    "api key",
    "private key",
    "exchange api",
    "leverage up",
    "short squeeze",
    "margin call",
    "liquidate position",
    "close and trade",
    "close now",
    "task assignment",
    "task complete",
    "task completed",
    "auto assign",
    "create ticket",
    "open jira",
    "send email",
    "notify team",
)


# Allowed negation phrases and field names that may legitimately appear in
# artifact bodies (safety notices and JSON/Markdown safety-flag fields).
_ALLOWED_NEGATION_PHRASES: tuple[str, ...] = (
    "does not imply",
    "is not a",
    "not a production",
    "not a trading",
    "does not",
    "no_executable_actions",
    "no_trading_instructions",
    "no_approval_claims",
    "no_automated_remediation",
    "no_automatic_assignment",
    "no_task_completion_claims",
    "references_opaque",
    "no_network",
    "no_server",
    "audit_only",
    "human_audit_only",
    "research_only",
)


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------

_SEVERITY_PRECEDENCE: dict[str, int] = {
    HumanReviewAuditBundleExportSeverity.INFO.value: 1,
    HumanReviewAuditBundleExportSeverity.ADVISORY.value: 2,
    HumanReviewAuditBundleExportSeverity.BLOCKING.value: 3,
}


def _severity_precedence(severity: str) -> int:
    return _SEVERITY_PRECEDENCE.get(severity.lower(), 0)


# ---------------------------------------------------------------------------
# Deterministic ID helpers
# ---------------------------------------------------------------------------


def _canonical_datetime(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.astimezone(timezone.utc).isoformat()


def _canonical_json(payload: dict[str, Any]) -> str:
    return dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _sha256_prefix(payload: dict[str, Any], length: int) -> str:
    return sha256(_canonical_json(payload).encode("utf-8")).hexdigest()[:length]


def _build_filename(
    bundle_report_id: str,
    generated_at: datetime,
    format: str,
    metadata: dict[str, str],
) -> str:
    """Return a deterministic export filename."""
    ext = "md" if format == "markdown" else "json"
    payload = {
        "kind": EXPORT_KIND,
        "bundle_report_id": str(bundle_report_id).strip(),
        "generated_at": _canonical_datetime(generated_at),
        "format": format,
        "metadata": dict(sorted(metadata.items())),
    }
    return f"hra-bundle-export-{_sha256_prefix(payload, 24)}.{ext}"


def _build_report_id(
    bundle_report_id: str,
    generated_at: datetime,
    format: str,
    filename: str,
    content_hash: str,
) -> str:
    """Return a deterministic report_id for the export plan/manifest."""
    payload = {
        "kind": EXPORT_KIND,
        "bundle_report_id": str(bundle_report_id).strip(),
        "generated_at": _canonical_datetime(generated_at),
        "format": format,
        "filename": str(filename).strip(),
        "content_hash": str(content_hash).strip(),
    }
    return f"hra-bundle-export-report-{_sha256_prefix(payload, 16)}"


def _build_plan_id(
    bundle_report_id: str,
    generated_at: datetime,
    format: str,
    filename: str,
    content_hash: str,
) -> str:
    """Return a deterministic plan_id."""
    return _build_report_id(bundle_report_id, generated_at, format, filename, content_hash)


def _build_manifest_id(
    report_id: str,
    output_path: str,
    content_hash: str,
    generated_at: datetime,
) -> str:
    """Return a deterministic manifest_id."""
    payload = {
        "kind": MANIFEST_KIND,
        "report_id": str(report_id).strip(),
        "output_path": str(output_path).strip(),
        "content_hash": str(content_hash).strip(),
        "generated_at": _canonical_datetime(generated_at),
    }
    return f"hra-bundle-export-manifest-{_sha256_prefix(payload, 16)}"


def _build_issue_id(
    issue_type: str,
    source: str,
    title: str,
    counter: int,
) -> str:
    """Return a deterministic issue_id."""
    payload = {
        "kind": "export_issue",
        "issue_type": str(issue_type).strip(),
        "source": str(source).strip(),
        "title": str(title).strip(),
        "counter": counter,
    }
    return f"export-issue-{_sha256_prefix(payload, 16)}"


# ---------------------------------------------------------------------------
# Artifact body and hash
# ---------------------------------------------------------------------------


def _build_body(bundle_report: HumanReviewAuditBundleReport, format: str) -> str:
    """Return the artifact body using the MVP-43 writer."""
    if format == "markdown":
        return bundle_report_to_markdown(bundle_report)
    return bundle_report_to_json(bundle_report)


def _content_hash(body: str) -> str:
    """Return SHA-256 hex digest of the artifact body bytes."""
    return sha256(body.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Safety scanner
# ---------------------------------------------------------------------------


def _artifact_body_without_safety(output: str) -> str:
    """Return the artifact body with safety notices and allowed phrases removed."""
    body = output.replace(BUNDLE_SAFETY_NOTICE, "")
    body = body.replace(SAFETY_NOTICE, "")
    for allowed in _ALLOWED_NEGATION_PHRASES:
        body = body.replace(allowed, "")
    return body


def _forbidden_phrases_found(output: str) -> list[str]:
    """Return any forbidden action phrases found outside allowed contexts."""
    body = _artifact_body_without_safety(output).lower()
    return [phrase for phrase in _FORBIDDEN_ACTION_PHRASES if phrase in body]


# ---------------------------------------------------------------------------
# Path safety
# ---------------------------------------------------------------------------


def _validate_filename(filename: str) -> tuple[bool, str]:
    """Return (ok, reason) for the deterministic filename."""
    if not filename:
        return False, "filename is empty"
    if "/" in filename or "\\" in filename or ":" in filename:
        return False, "filename contains path separator"
    if ".." in filename:
        return False, "filename contains parent traversal"
    if not filename.startswith("hra-bundle-export-"):
        return False, "filename does not match allowlist prefix"
    parts = filename.rsplit(".", 1)
    if len(parts) != 2 or parts[1] not in {"json", "md", "markdown"}:
        return False, "filename extension not in allowlist"
    return True, ""


def _resolve_output_path(
    output_dir: Path,
    filename: str,
    generated_at: datetime,
) -> tuple[str | None, HumanReviewAuditBundleExportIssue | None]:
    """Resolve and validate the output path."""
    output_dir_resolved = output_dir.resolve()
    output_path = (output_dir_resolved / filename).resolve()
    if output_path.parent != output_dir_resolved:
        return None, HumanReviewAuditBundleExportIssue(
            issue_id=_build_issue_id(
                "path_traversal_attempt",
                "path_safety",
                "Output path escapes caller-supplied directory",
                1,
            ),
            issue_type="path_traversal_attempt",
            severity=HumanReviewAuditBundleExportSeverity.BLOCKING.value,
            reason_codes=(HumanReviewAuditBundleExportReasonCode.PATH_TRAVERSAL_ATTEMPT.value,),
            source="path_safety",
            title="Output path escapes caller-supplied directory",
            description=f"Resolved output path {str(output_path)!r} is not under {str(output_dir_resolved)!r}.",
            generated_at=generated_at,
        )
    return str(output_path), None


def _resolve_tmp_path(
    tmp_path_dir: Path,
    filename: str,
    generated_at: datetime,
) -> tuple[str | None, HumanReviewAuditBundleExportIssue | None]:
    """Resolve and validate the temporary path."""
    tmp_path_dir_resolved = tmp_path_dir.resolve()
    tmp_filename = f"{filename}.tmp"
    tmp_path = (tmp_path_dir_resolved / tmp_filename).resolve()
    if tmp_path.parent != tmp_path_dir_resolved:
        return None, HumanReviewAuditBundleExportIssue(
            issue_id=_build_issue_id(
                "path_traversal_attempt",
                "path_safety",
                "Temporary path escapes caller-supplied directory",
                2,
            ),
            issue_type="path_traversal_attempt",
            severity=HumanReviewAuditBundleExportSeverity.BLOCKING.value,
            reason_codes=(HumanReviewAuditBundleExportReasonCode.PATH_TRAVERSAL_ATTEMPT.value,),
            source="path_safety",
            title="Temporary path escapes caller-supplied directory",
            description=f"Resolved temporary path {str(tmp_path)!r} is not under {str(tmp_path_dir_resolved)!r}.",
            generated_at=generated_at,
        )
    return str(tmp_path), None


# ---------------------------------------------------------------------------
# Issue building
# ---------------------------------------------------------------------------


def _build_issue(
    issue_type: str,
    severity: str,
    reason_codes: tuple[str, ...],
    source: str,
    title: str,
    description: str,
    counter: int,
    generated_at: datetime,
) -> HumanReviewAuditBundleExportIssue:
    return HumanReviewAuditBundleExportIssue(
        issue_id=_build_issue_id(issue_type, source, title, counter),
        issue_type=issue_type,
        severity=severity,
        reason_codes=reason_codes,
        source=source,
        title=title,
        description=description,
        generated_at=generated_at,
    )


# ---------------------------------------------------------------------------
# Reason codes and safety flags
# ---------------------------------------------------------------------------


def _build_reason_codes(
    state: HumanReviewAuditBundleExportState,
    issues: tuple[HumanReviewAuditBundleExportIssue, ...],
) -> tuple[HumanReviewAuditBundleExportReasonCode, ...]:
    codes: set[HumanReviewAuditBundleExportReasonCode] = {
        HumanReviewAuditBundleExportReasonCode.RESEARCH_ONLY,
        HumanReviewAuditBundleExportReasonCode.HUMAN_AUDIT_ONLY,
        HumanReviewAuditBundleExportReasonCode.NO_EXECUTABLE_ACTIONS,
        HumanReviewAuditBundleExportReasonCode.NO_TRADING_INSTRUCTIONS,
        HumanReviewAuditBundleExportReasonCode.NO_APPROVAL_CLAIMS,
        HumanReviewAuditBundleExportReasonCode.REFERENCES_OPAQUE,
        HumanReviewAuditBundleExportReasonCode.NO_NETWORK,
        HumanReviewAuditBundleExportReasonCode.NO_SERVER,
        HumanReviewAuditBundleExportReasonCode.NO_DATABASE,
    }

    if state == HumanReviewAuditBundleExportState.PLANNED:
        codes.add(HumanReviewAuditBundleExportReasonCode.PLANNED)
    elif state == HumanReviewAuditBundleExportState.WRITTEN:
        codes.add(HumanReviewAuditBundleExportReasonCode.WRITTEN)
    elif state == HumanReviewAuditBundleExportState.NOT_APPLICABLE:
        codes.add(HumanReviewAuditBundleExportReasonCode.NOT_APPLICABLE)
    elif state in (
        HumanReviewAuditBundleExportState.BLOCKED,
    ):
        codes.add(HumanReviewAuditBundleExportReasonCode.BLOCKED)

    for issue in issues:
        for rc in issue.reason_codes:
            if rc == HumanReviewAuditBundleExportReasonCode.FORBIDDEN_TERM_PRESENT.value:
                codes.add(HumanReviewAuditBundleExportReasonCode.FORBIDDEN_TERM_PRESENT)
            elif rc == HumanReviewAuditBundleExportReasonCode.PATH_TRAVERSAL_ATTEMPT.value:
                codes.add(HumanReviewAuditBundleExportReasonCode.PATH_TRAVERSAL_ATTEMPT)
            elif rc == HumanReviewAuditBundleExportReasonCode.UNSAFE_CONTENT.value:
                codes.add(HumanReviewAuditBundleExportReasonCode.UNSAFE_CONTENT)
            elif rc == HumanReviewAuditBundleExportReasonCode.UPSTREAM_BLOCKED.value:
                codes.add(HumanReviewAuditBundleExportReasonCode.UPSTREAM_BLOCKED)
            elif rc == HumanReviewAuditBundleExportReasonCode.UPSTREAM_DEGRADED.value:
                codes.add(HumanReviewAuditBundleExportReasonCode.UPSTREAM_DEGRADED)
            elif rc == HumanReviewAuditBundleExportReasonCode.UPSTREAM_NOT_APPLICABLE.value:
                codes.add(HumanReviewAuditBundleExportReasonCode.UPSTREAM_NOT_APPLICABLE)
            elif rc == HumanReviewAuditBundleExportReasonCode.OUTPUT_EXISTS.value:
                codes.add(HumanReviewAuditBundleExportReasonCode.OUTPUT_EXISTS)
            elif rc == HumanReviewAuditBundleExportReasonCode.PATH_ERROR.value:
                codes.add(HumanReviewAuditBundleExportReasonCode.PATH_ERROR)
            elif rc == HumanReviewAuditBundleExportReasonCode.HASH_MISMATCH.value:
                codes.add(HumanReviewAuditBundleExportReasonCode.HASH_MISMATCH)
            elif rc == HumanReviewAuditBundleExportReasonCode.INVALID_FORMAT.value:
                codes.add(HumanReviewAuditBundleExportReasonCode.INVALID_FORMAT)

    return tuple(sorted(codes, key=lambda c: c.value))


def _build_safety_flags(
    is_safe: bool,
    path_safe: bool,
    hash_verified: bool,
) -> HumanReviewAuditBundleExportSafetyFlags:
    return HumanReviewAuditBundleExportSafetyFlags(
        is_safe=is_safe,
        audit_only=True,
        no_executable_actions=True,
        no_trading_instructions=True,
        no_approval_claims=True,
        references_opaque=True,
        no_network=True,
        no_server=True,
        path_safe=path_safe,
        hash_verified=hash_verified,
    )


# ---------------------------------------------------------------------------
# Aggregate state
# ---------------------------------------------------------------------------


def _aggregate_state(
    issues: tuple[HumanReviewAuditBundleExportIssue, ...],
    upstream_bundle_state: HumanReviewAuditBundleState | None,
    strict: bool,
) -> HumanReviewAuditBundleExportState:
    """Compute the export state from issues and upstream bundle state."""
    max_precedence = 0
    for issue in issues:
        max_precedence = max(max_precedence, _severity_precedence(issue.severity))

    if upstream_bundle_state == HumanReviewAuditBundleState.BLOCKED:
        max_precedence = max(max_precedence, _severity_precedence(HumanReviewAuditBundleExportSeverity.BLOCKING.value))
    elif upstream_bundle_state == HumanReviewAuditBundleState.DEGRADED:
        max_precedence = max(max_precedence, _severity_precedence(HumanReviewAuditBundleExportSeverity.ADVISORY.value))
    elif upstream_bundle_state == HumanReviewAuditBundleState.NOT_APPLICABLE:
        max_precedence = max(max_precedence, _severity_precedence(HumanReviewAuditBundleExportSeverity.INFO.value))

    if max_precedence == _severity_precedence(HumanReviewAuditBundleExportSeverity.BLOCKING.value):
        return HumanReviewAuditBundleExportState.BLOCKED
    if max_precedence == _severity_precedence(HumanReviewAuditBundleExportSeverity.ADVISORY.value):
        if strict:
            return HumanReviewAuditBundleExportState.BLOCKED
        return HumanReviewAuditBundleExportState.PLANNED
    if max_precedence == _severity_precedence(HumanReviewAuditBundleExportSeverity.INFO.value):
        if upstream_bundle_state == HumanReviewAuditBundleState.NOT_APPLICABLE:
            return HumanReviewAuditBundleExportState.NOT_APPLICABLE
        return HumanReviewAuditBundleExportState.PLANNED

    return HumanReviewAuditBundleExportState.PLANNED


# ---------------------------------------------------------------------------
# Main planner entry point
# ---------------------------------------------------------------------------


def plan_human_review_audit_bundle_export(
    input: HumanReviewAuditBundleExportInput,  # noqa: A002 — matches SPEC API name
) -> HumanReviewAuditBundleExportPlan:
    """Build a deterministic, file-write-free audit bundle export plan.

    The planner accepts a caller-provided in-memory bundle report and explicit
    local output/temporary directories. It produces an export plan without
    writing files, opening refs, or performing network/trading/execution
    actions. It is fail-closed: any invalid format, path traversal, unsafe
    content, or upstream BLOCKED state results in a BLOCKED plan.
    """
    config = input.config
    bundle_report = input.bundle_report
    generated_at = _resolve_generated_at(input.generated_at, bundle_report.generated_at)
    output_dir = input.output_dir
    tmp_path_dir = input.tmp_path
    metadata = dict(input.metadata)

    issues: list[HumanReviewAuditBundleExportIssue] = []
    is_safe = True
    path_safe = True
    hash_verified = False  # Verified only after a future write step.
    notes = ""

    # Validate format.
    format_valid = True
    format_value = config.format
    try:
        if format_value not in {"json", "markdown"}:
            format_valid = False
    except Exception:  # pragma: no cover — defensive
        format_valid = False

    if not format_valid:
        issue = _build_issue(
            issue_type="invalid_format",
            severity=HumanReviewAuditBundleExportSeverity.BLOCKING.value,
            reason_codes=(HumanReviewAuditBundleExportReasonCode.INVALID_FORMAT.value,),
            source="path_safety",
            title="Invalid export format",
            description=f"Export format {format_value!r} is not in the allowlist.",
            counter=len(issues) + 1,
            generated_at=generated_at,
        )
        issues.append(issue)
        state = HumanReviewAuditBundleExportState.BLOCKED
        safety_flags = _build_safety_flags(is_safe=False, path_safe=False, hash_verified=False)
        reason_codes = _build_reason_codes(state, tuple(issues))
        return _build_blocked_plan(
            input=input,
            generated_at=generated_at,
            state=state,
            issues=tuple(issues),
            safety_flags=safety_flags,
            reason_codes=reason_codes,
            notes="Invalid export format.",
        )

    # Build artifact body and compute hash.
    body = _build_body(bundle_report, format_value)
    content_hash = _content_hash(body)
    content_length = len(body.encode("utf-8"))

    # Safety scanner.
    if config.safety_scan:
        found = _forbidden_phrases_found(body)
        if found:
            is_safe = False
            issue = _build_issue(
                issue_type="forbidden_term_present",
                severity=HumanReviewAuditBundleExportSeverity.BLOCKING.value,
                reason_codes=(HumanReviewAuditBundleExportReasonCode.FORBIDDEN_TERM_PRESENT.value,),
                source="safety_scan",
                title="Forbidden term present in artifact body",
                description=f"Found forbidden phrases: {', '.join(found)}.",
                counter=len(issues) + 1,
                generated_at=generated_at,
            )
            issues.append(issue)

    # Deterministic filename.
    filename = _build_filename(
        bundle_report.bundle_id,
        generated_at,
        format_value,
        metadata,
    )
    filename_ok, filename_reason = _validate_filename(filename)
    if not filename_ok:
        path_safe = False
        issue = _build_issue(
            issue_type="invalid_filename",
            severity=HumanReviewAuditBundleExportSeverity.BLOCKING.value,
            reason_codes=(HumanReviewAuditBundleExportReasonCode.PATH_TRAVERSAL_ATTEMPT.value,),
            source="path_safety",
            title="Generated filename is invalid",
            description=filename_reason,
            counter=len(issues) + 1,
            generated_at=generated_at,
        )
        issues.append(issue)

    # Resolve paths.
    output_path_str: str | None = None
    tmp_path_str: str | None = None
    if filename_ok:
        output_path_str, output_issue = _resolve_output_path(output_dir, filename, generated_at)
        if output_issue is not None:
            path_safe = False
            issues.append(output_issue)
        tmp_path_str, tmp_issue = _resolve_tmp_path(tmp_path_dir, filename, generated_at)
        if tmp_issue is not None:
            path_safe = False
            issues.append(tmp_issue)

    # Output directory existence check (planner only — no creation).
    if not output_dir.exists():
        path_safe = False
        issue = _build_issue(
            issue_type="output_dir_missing",
            severity=HumanReviewAuditBundleExportSeverity.BLOCKING.value,
            reason_codes=(HumanReviewAuditBundleExportReasonCode.PATH_ERROR.value,),
            source="path_safety",
            title="Output directory does not exist",
            description=f"Caller-supplied output directory {str(output_dir)!r} does not exist.",
            counter=len(issues) + 1,
            generated_at=generated_at,
        )
        issues.append(issue)

    # Overwrite check.
    if output_path_str and not config.overwrite and Path(output_path_str).exists():
        issue = _build_issue(
            issue_type="output_exists",
            severity=HumanReviewAuditBundleExportSeverity.BLOCKING.value,
            reason_codes=(HumanReviewAuditBundleExportReasonCode.OUTPUT_EXISTS.value,),
            source="path_safety",
            title="Output file already exists",
            description=f"Output path {output_path_str!r} already exists and overwrite is False.",
            counter=len(issues) + 1,
            generated_at=generated_at,
        )
        issues.append(issue)

    # Upstream bundle state carry-forward.
    upstream_state = bundle_report.state
    if upstream_state == HumanReviewAuditBundleState.BLOCKED:
        issue = _build_issue(
            issue_type="upstream_blocked",
            severity=HumanReviewAuditBundleExportSeverity.BLOCKING.value,
            reason_codes=(HumanReviewAuditBundleExportReasonCode.UPSTREAM_BLOCKED.value,),
            source="upstream",
            title="Upstream bundle report is BLOCKED",
            description=f"Upstream bundle report {bundle_report.bundle_id!r} has aggregate state blocked.",
            counter=len(issues) + 1,
            generated_at=generated_at,
        )
        issues.append(issue)
    elif upstream_state == HumanReviewAuditBundleState.DEGRADED:
        severity = (
            HumanReviewAuditBundleExportSeverity.BLOCKING.value
            if config.strict
            else HumanReviewAuditBundleExportSeverity.ADVISORY.value
        )
        issue = _build_issue(
            issue_type="upstream_degraded",
            severity=severity,
            reason_codes=(HumanReviewAuditBundleExportReasonCode.UPSTREAM_DEGRADED.value,),
            source="upstream",
            title="Upstream bundle report is DEGRADED",
            description=f"Upstream bundle report {bundle_report.bundle_id!r} has aggregate state degraded.",
            counter=len(issues) + 1,
            generated_at=generated_at,
        )
        issues.append(issue)
    elif upstream_state == HumanReviewAuditBundleState.NOT_APPLICABLE:
        issue = _build_issue(
            issue_type="upstream_not_applicable",
            severity=HumanReviewAuditBundleExportSeverity.INFO.value,
            reason_codes=(HumanReviewAuditBundleExportReasonCode.UPSTREAM_NOT_APPLICABLE.value,),
            source="upstream",
            title="Upstream bundle report is NOT_APPLICABLE",
            description=f"Upstream bundle report {bundle_report.bundle_id!r} has aggregate state not_applicable.",
            counter=len(issues) + 1,
            generated_at=generated_at,
        )
        issues.append(issue)

    # Aggregate state.
    issues_tuple = tuple(issues)
    state = _aggregate_state(issues_tuple, upstream_state, config.strict)

    if state == HumanReviewAuditBundleExportState.BLOCKED:
        notes = "Export plan is blocked due to safety, path, or upstream issues."
    elif state == HumanReviewAuditBundleExportState.NOT_APPLICABLE:
        notes = "Upstream bundle report is not applicable."
    else:
        notes = "Export plan is ready for controlled local write."

    safety_flags = _build_safety_flags(is_safe, path_safe, hash_verified)
    reason_codes = _build_reason_codes(state, issues_tuple)

    report_id = _build_report_id(
        bundle_report.bundle_id,
        generated_at,
        format_value,
        filename,
        content_hash,
    )
    plan_id = _build_plan_id(
        bundle_report.bundle_id,
        generated_at,
        format_value,
        filename,
        content_hash,
    )

    output_path_str = output_path_str or ""
    tmp_path_str = tmp_path_str or ""

    return HumanReviewAuditBundleExportPlan(
        plan_id=plan_id,
        report_id=report_id,
        bundle_report_id=bundle_report.bundle_id,
        filename=filename,
        output_path=output_path_str,
        tmp_path=tmp_path_str,
        format=format_value,
        content_hash=content_hash,
        content_length=content_length,
        generated_at=generated_at,
        state=state,
        safety_flags=safety_flags,
        reason_codes=reason_codes,
        issues=issues_tuple,
        metadata=metadata,
        notes=notes,
    )


def build_export_manifest_from_plan(
    plan: HumanReviewAuditBundleExportPlan,
    state_override: HumanReviewAuditBundleExportState | None = None,
) -> HumanReviewAuditBundleExportManifest:
    """Build a deterministic export manifest from a plan.

    In Step 1 no file is written, so the manifest state is derived from the
    plan (typically PLANNED, BLOCKED, or NOT_APPLICABLE). The manifest ID is
    deterministic and includes the output path, content hash, and timestamp.
    """
    state = state_override if state_override is not None else plan.state
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
        state=state,
        safety_flags=plan.safety_flags,
        reason_codes=plan.reason_codes,
        issues=plan.issues,
        metadata=plan.metadata,
        notes=plan.notes,
    )


def _build_blocked_plan(
    input: HumanReviewAuditBundleExportInput,  # noqa: A002
    generated_at: datetime,
    state: HumanReviewAuditBundleExportState,
    issues: tuple[HumanReviewAuditBundleExportIssue, ...],
    safety_flags: HumanReviewAuditBundleExportSafetyFlags,
    reason_codes: tuple[HumanReviewAuditBundleExportReasonCode, ...],
    notes: str,
) -> HumanReviewAuditBundleExportPlan:
    """Return a minimal BLOCKED plan when early validation fails."""
    bundle_report = input.bundle_report
    format_value = input.config.format
    metadata = dict(input.metadata)
    filename = _build_filename(
        bundle_report.bundle_id,
        generated_at,
        format_value,
        metadata,
    )
    content_hash = _content_hash("")
    report_id = _build_report_id(
        bundle_report.bundle_id,
        generated_at,
        format_value,
        filename,
        content_hash,
    )
    plan_id = report_id
    output_path_str, _ = _resolve_output_path(input.output_dir, filename, generated_at)
    tmp_path_str, _ = _resolve_tmp_path(input.tmp_path, filename, generated_at)
    return HumanReviewAuditBundleExportPlan(
        plan_id=plan_id,
        report_id=report_id,
        bundle_report_id=bundle_report.bundle_id,
        filename=filename,
        output_path=output_path_str or "",
        tmp_path=tmp_path_str or "",
        format=format_value,
        content_hash=content_hash,
        content_length=0,
        generated_at=generated_at,
        state=state,
        safety_flags=safety_flags,
        reason_codes=reason_codes,
        issues=issues,
        metadata=metadata,
        notes=notes,
    )


def _resolve_generated_at(
    input_generated_at: datetime | None,
    bundle_generated_at: datetime | None,
) -> datetime:
    """Return the most specific available generated_at timestamp."""
    if input_generated_at is not None:
        return input_generated_at
    if bundle_generated_at is not None:
        return bundle_generated_at
    return datetime.now(timezone.utc)
