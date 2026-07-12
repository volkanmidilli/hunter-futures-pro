"""Pure deterministic verification engine for hunter.human_review_audit_bundle_export_verification.

MVP-45 Step 1 — Read-only verification/replay of MVP-44 audit bundle export
artifacts. No filesystem, network, or runtime I/O is performed.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from hashlib import sha256
from json import dumps, loads
from typing import Any

from hunter.human_review_audit_bundle_export.models import (
    SAFETY_NOTICE as EXPORT_SAFETY_NOTICE,
    HumanReviewAuditBundleExportManifest,
    HumanReviewAuditBundleExportState,
)

from .models import (
    HUMAN_REVIEW_AUDIT_BUNDLE_EXPORT_VERIFICATION_VERSION,
    SAFETY_NOTICE,
    VERIFICATION_KIND,
    HumanReviewAuditBundleExportVerificationConfig,
    HumanReviewAuditBundleExportVerificationDataQuality,
    HumanReviewAuditBundleExportVerificationIssue,
    HumanReviewAuditBundleExportVerificationReasonCode,
    HumanReviewAuditBundleExportVerificationReport,
    HumanReviewAuditBundleExportVerificationSafetyFlags,
    HumanReviewAuditBundleExportVerificationSeverity,
    HumanReviewAuditBundleExportVerificationState,
)


# ---------------------------------------------------------------------------
# Safety scanner constants
# ---------------------------------------------------------------------------


ALLOWED_FORMATS: tuple[str, ...] = ("json", "markdown", "")

FORBIDDEN_VERIFICATION_TERMS: tuple[str, ...] = (
    "shell",
    "bash",
    "sh -c",
    "rm -rf",
    "chmod",
    "chown",
    "sudo",
    "curl",
    "wget",
    "eval(",
    "exec(",
    "system(",
    "subprocess",
    "patch",
    "apply patch",
    "deploy",
    "deployment",
    "infrastructure",
    "terraform",
    "ansible",
    "kubernetes",
    "kubectl",
    "remediate",
    "remediation",
    "auto-fix",
    "autofix",
    "fix automatically",
    "buy",
    "sell",
    "long position",
    "short position",
    "leverage",
    "margin",
    "place order",
    "execute trade",
    "api key",
    "apikey",
    "secret key",
    "binance",
    "coinbase",
    "kraken",
    "freqtrade",
    "approved",
    "certified",
    "production ready",
    "production-ready",
    "trading ready",
    "trading-ready",
    "recommend",
    "recommendation",
    "should buy",
    "should sell",
    "suitable",
    "suitability",
    "signal validity",
    "buy signal",
    "sell signal",
    "actionable signal",
)

ALLOWED_NEGATION_TERMS: tuple[str, ...] = (
    "not trading",
    "no trading",
    "audit-only",
    "human review",
    "not production-ready",
    "not production ready",
    "not trading-ready",
    "not trading ready",
    "does not imply",
    "not approved",
    "not certified",
    "not suitable",
    "no recommendation",
    "no signal",
)


# ---------------------------------------------------------------------------
# Canonical helpers
# ---------------------------------------------------------------------------


def _canonical_json(value: Any) -> str:
    """Return a deterministic canonical JSON string for hashing."""
    return dumps(
        value,
        indent=None,
        ensure_ascii=True,
        sort_keys=True,
        default=str,
    )


def _iso_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Deterministic ID helpers
# ---------------------------------------------------------------------------


def _build_issue_id(
    issue_type: str,
    source: str,
    title: str,
    counter: int,
) -> str:
    payload = {
        "issue_type": issue_type,
        "source": source,
        "title": title,
        "counter": counter,
    }
    digest = sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return f"export-verification-issue-{digest[:16]}"


def _build_report_id(
    manifest_id: str,
    bundle_report_id: str,
    content_hash: str,
    content_length: int,
    generated_at: datetime,
) -> str:
    payload = {
        "kind": VERIFICATION_KIND,
        "manifest_id": manifest_id,
        "bundle_report_id": bundle_report_id,
        "content_hash": content_hash,
        "content_length": content_length,
        "generated_at": _iso_datetime(generated_at),
    }
    digest = sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return f"export-verification-report-{digest[:16]}"


def _build_verification_id(
    report_id: str,
    manifest_id: str,
    state: HumanReviewAuditBundleExportVerificationState,
    content_hash: str,
    content_length: int,
    generated_at: datetime,
) -> str:
    payload = {
        "kind": VERIFICATION_KIND,
        "report_id": report_id,
        "manifest_id": manifest_id,
        "state": state.value,
        "content_hash": content_hash,
        "content_length": content_length,
        "generated_at": _iso_datetime(generated_at),
    }
    digest = sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return f"export-verification-{digest[:16]}"


# ---------------------------------------------------------------------------
# Safety scanner
# ---------------------------------------------------------------------------


def _scan_forbidden_terms(text: str) -> list[str]:
    """Return any forbidden terms found in the generated text.

    The verification and export safety notices are trusted, negation-only boilerplate
    and are removed before scanning. Remaining negation contexts (e.g. "does not
    imply ...") are stripped to the end of their sentence so negated forbidden words
    do not produce false positives.
    """
    lowered = text.lower()
    # Remove trusted safety notices; they are intentionally full of negated
    # forbidden terms.
    lowered = lowered.replace(SAFETY_NOTICE.lower(), "")
    lowered = lowered.replace(EXPORT_SAFETY_NOTICE.lower(), "")
    # Remove negation contexts up to sentence boundaries.
    for negation in ALLOWED_NEGATION_TERMS:
        lowered = _strip_negation_context(lowered, negation)
    found: list[str] = []
    for term in FORBIDDEN_VERIFICATION_TERMS:
        if term.lower() in lowered:
            found.append(term)
    return found


def _strip_negation_context(text: str, negation: str) -> str:
    """Remove the negation phrase and the rest of the sentence it appears in."""
    lowered_negation = negation.lower()
    result_parts: list[str] = []
    i = 0
    while i < len(text):
        idx = text.find(lowered_negation, i)
        if idx == -1:
            result_parts.append(text[i:])
            break
        result_parts.append(text[i:idx])
        end = idx + len(lowered_negation)
        while end < len(text) and text[end] not in ".!?\n":
            end += 1
        if end < len(text):
            end += 1
        i = end
    return "".join(result_parts)


# ---------------------------------------------------------------------------
# Format classification
# ---------------------------------------------------------------------------


def _classify_format(artifact_bytes: bytes) -> str:
    """Classify the artifact body format from bytes only, without executing content.

    Returns "json", "markdown", or "unknown". Classification is advisory.
    """
    try:
        text = artifact_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return "unknown"
    stripped = text.strip()
    if not stripped:
        return "unknown"
    try:
        loads(stripped)
        return "json"
    except ValueError:
        pass
    if stripped.startswith("#") or "## " in stripped or stripped.startswith("---"):
        return "markdown"
    return "unknown"


# ---------------------------------------------------------------------------
# Issue builders
# ---------------------------------------------------------------------------


def _build_issue(
    issue_type: str,
    severity: HumanReviewAuditBundleExportVerificationSeverity,
    reason_code: HumanReviewAuditBundleExportVerificationReasonCode,
    source: str,
    title: str,
    description: str,
    generated_at: datetime,
    counter: int,
) -> HumanReviewAuditBundleExportVerificationIssue:
    return HumanReviewAuditBundleExportVerificationIssue(
        issue_id=_build_issue_id(issue_type, source, title, counter),
        issue_type=issue_type,
        severity=severity.value,
        reason_codes=(reason_code.value,),
        source=source,
        title=title,
        description=description,
        generated_at=generated_at,
    )


# ---------------------------------------------------------------------------
# Input validation and summary
# ---------------------------------------------------------------------------


def _resolve_generated_at(
    input_value: datetime | None,
    manifest: HumanReviewAuditBundleExportManifest,
) -> datetime:
    """Resolve a deterministic generated_at timestamp.

    Prefer caller-provided value, then the manifest generated_at if it exists,
    then a fixed epoch sentinel. Never use time-now.
    """
    if input_value is not None:
        return input_value.astimezone(timezone.utc)
    if hasattr(manifest, "generated_at") and manifest.generated_at is not None:
        return manifest.generated_at.astimezone(timezone.utc)
    return datetime(1970, 1, 1, tzinfo=timezone.utc)


def _build_input_summary(
    manifest: HumanReviewAuditBundleExportManifest,
    expected_format: str,
) -> Mapping[str, str]:
    """Build a summary of opaque inputs with no raw bytes or resolved paths."""
    return {
        "manifest_id": manifest.manifest_id,
        "report_id": manifest.report_id,
        "bundle_report_id": manifest.bundle_report_id,
        "state": manifest.state.value,
        "format": manifest.format,
        "expected_format": expected_format,
        "content_hash_prefix": manifest.content_hash[:16] if manifest.content_hash else "",
        "content_length": str(manifest.content_length),
    }


def _validate_manifest_metadata(
    manifest: HumanReviewAuditBundleExportManifest,
    generated_at: datetime,
    counter: int,
) -> tuple[list[HumanReviewAuditBundleExportVerificationIssue], int]:
    """Validate required manifest fields are present and non-empty."""
    issues: list[HumanReviewAuditBundleExportVerificationIssue] = []
    missing: list[str] = []
    if not manifest.manifest_id:
        missing.append("manifest_id")
    if not manifest.report_id:
        missing.append("report_id")
    if not manifest.bundle_report_id:
        missing.append("bundle_report_id")
    if manifest.state == HumanReviewAuditBundleExportState.WRITTEN:
        if not manifest.content_hash:
            missing.append("content_hash")
        if manifest.content_length == 0:
            missing.append("content_length")
    if missing:
        issues.append(
            _build_issue(
                issue_type="missing_manifest_metadata",
                severity=HumanReviewAuditBundleExportVerificationSeverity.BLOCKING,
                reason_code=HumanReviewAuditBundleExportVerificationReasonCode.MISSING_MANIFEST_METADATA,
                source="manifest_metadata",
                title="Missing required manifest metadata",
                description=f"Missing fields: {', '.join(missing)}.",
                generated_at=generated_at,
                counter=counter,
            )
        )
    return issues, counter + 1


# ---------------------------------------------------------------------------
# Hash/length/safety checks
# ---------------------------------------------------------------------------


def _check_hash(
    artifact_bytes: bytes,
    manifest: HumanReviewAuditBundleExportManifest,
    generated_at: datetime,
    counter: int,
) -> tuple[list[HumanReviewAuditBundleExportVerificationIssue], int, bool]:
    """Recompute SHA-256 and compare to manifest.content_hash."""
    issues: list[HumanReviewAuditBundleExportVerificationIssue] = []
    expected = manifest.content_hash
    if not expected:
        return issues, counter, False
    actual = sha256(artifact_bytes).hexdigest()
    if actual != expected:
        issues.append(
            _build_issue(
                issue_type="hash_mismatch",
                severity=HumanReviewAuditBundleExportVerificationSeverity.BLOCKING,
                reason_code=HumanReviewAuditBundleExportVerificationReasonCode.HASH_MISMATCH,
                source="hash_verification",
                title="Artifact SHA-256 does not match manifest",
                description=f"Expected {expected}, got {actual}.",
                generated_at=generated_at,
                counter=counter,
            )
        )
        return issues, counter + 1, False
    return issues, counter, True


def _check_length(
    artifact_bytes: bytes,
    manifest: HumanReviewAuditBundleExportManifest,
    generated_at: datetime,
    counter: int,
) -> tuple[list[HumanReviewAuditBundleExportVerificationIssue], int, bool]:
    """Compare len(artifact_bytes) to manifest.content_length."""
    issues: list[HumanReviewAuditBundleExportVerificationIssue] = []
    expected = manifest.content_length
    actual = len(artifact_bytes)
    if actual != expected:
        issues.append(
            _build_issue(
                issue_type="length_mismatch",
                severity=HumanReviewAuditBundleExportVerificationSeverity.BLOCKING,
                reason_code=HumanReviewAuditBundleExportVerificationReasonCode.LENGTH_MISMATCH,
                source="length_verification",
                title="Artifact length does not match manifest",
                description=f"Expected {expected} bytes, got {actual}.",
                generated_at=generated_at,
                counter=counter,
            )
        )
        return issues, counter + 1, False
    return issues, counter, True


def _check_safety_notice(
    artifact_bytes: bytes,
    generated_at: datetime,
    counter: int,
) -> tuple[list[HumanReviewAuditBundleExportVerificationIssue], int, bool]:
    """Check that the MVP-44 export safety notice is present in the body."""
    issues: list[HumanReviewAuditBundleExportVerificationIssue] = []
    try:
        text = artifact_bytes.decode("utf-8")
    except UnicodeDecodeError:
        issues.append(
            _build_issue(
                issue_type="safety_notice_missing",
                severity=HumanReviewAuditBundleExportVerificationSeverity.ADVISORY,
                reason_code=HumanReviewAuditBundleExportVerificationReasonCode.SAFETY_NOTICE_MISSING,
                source="safety_notice",
                title="Safety notice could not be checked",
                description="Artifact bytes are not valid UTF-8; safety notice presence is indeterminate.",
                generated_at=generated_at,
                counter=counter,
            )
        )
        return issues, counter + 1, False
    if EXPORT_SAFETY_NOTICE in text:
        return issues, counter, True
    issues.append(
        _build_issue(
            issue_type="safety_notice_missing",
            severity=HumanReviewAuditBundleExportVerificationSeverity.ADVISORY,
            reason_code=HumanReviewAuditBundleExportVerificationReasonCode.SAFETY_NOTICE_MISSING,
            source="safety_notice",
            title="Safety notice missing from artifact body",
            description="The expected MVP-44 safety notice phrase was not found in the artifact body.",
            generated_at=generated_at,
            counter=counter,
        )
    )
    return issues, counter + 1, False


# ---------------------------------------------------------------------------
# Aggregate state and safety flags
# ---------------------------------------------------------------------------


def _determine_state(
    issues: tuple[HumanReviewAuditBundleExportVerificationIssue, ...],
    strict: bool,
    initial_state: HumanReviewAuditBundleExportVerificationState,
) -> HumanReviewAuditBundleExportVerificationState:
    """Determine final verification state from issues and config."""
    if initial_state in (
        HumanReviewAuditBundleExportVerificationState.BLOCKED,
        HumanReviewAuditBundleExportVerificationState.INVALID,
        HumanReviewAuditBundleExportVerificationState.NOT_APPLICABLE,
    ):
        return initial_state
    blocking = sum(
        1 for issue in issues
        if issue.severity == HumanReviewAuditBundleExportVerificationSeverity.BLOCKING.value
    )
    advisory = sum(
        1 for issue in issues
        if issue.severity == HumanReviewAuditBundleExportVerificationSeverity.ADVISORY.value
    )
    if blocking > 0:
        return HumanReviewAuditBundleExportVerificationState.BLOCKED
    if strict and advisory > 0:
        return HumanReviewAuditBundleExportVerificationState.BLOCKED
    if advisory > 0:
        return HumanReviewAuditBundleExportVerificationState.DEGRADED
    return HumanReviewAuditBundleExportVerificationState.VERIFIED


def _build_reason_codes(
    state: HumanReviewAuditBundleExportVerificationState,
    issues: tuple[HumanReviewAuditBundleExportVerificationIssue, ...],
) -> tuple[HumanReviewAuditBundleExportVerificationReasonCode, ...]:
    """Build reason codes from the final state and issue reason codes."""
    codes: list[HumanReviewAuditBundleExportVerificationReasonCode] = []
    if state == HumanReviewAuditBundleExportVerificationState.VERIFIED:
        codes.append(HumanReviewAuditBundleExportVerificationReasonCode.OK)
    elif state == HumanReviewAuditBundleExportVerificationState.NOT_APPLICABLE:
        codes.append(HumanReviewAuditBundleExportVerificationReasonCode.NOT_APPLICABLE)
    for issue in issues:
        for rc_str in issue.reason_codes:
            try:
                rc = HumanReviewAuditBundleExportVerificationReasonCode(rc_str)
            except ValueError:
                continue
            if rc not in codes:
                codes.append(rc)
    return tuple(codes)


def _build_data_quality(
    issues: tuple[HumanReviewAuditBundleExportVerificationIssue, ...],
    hash_mismatch: bool,
    length_mismatch: bool,
    state_not_verifiable: bool,
    missing_safety_notice: bool,
    forbidden_term_count: int,
    checks_performed: int,
) -> HumanReviewAuditBundleExportVerificationDataQuality:
    blocking = sum(
        1 for i in issues
        if i.severity == HumanReviewAuditBundleExportVerificationSeverity.BLOCKING.value
    )
    advisory = sum(
        1 for i in issues
        if i.severity == HumanReviewAuditBundleExportVerificationSeverity.ADVISORY.value
    )
    info = sum(
        1 for i in issues
        if i.severity == HumanReviewAuditBundleExportVerificationSeverity.INFO.value
    )
    return HumanReviewAuditBundleExportVerificationDataQuality(
        checks_performed=checks_performed,
        hash_mismatch_count=int(hash_mismatch),
        length_mismatch_count=int(length_mismatch),
        state_not_verifiable_count=int(state_not_verifiable),
        missing_safety_notice_count=int(missing_safety_notice),
        forbidden_term_count=forbidden_term_count,
        blocking_issues=blocking,
        advisory_issues=advisory,
        info_findings=info,
    )


def _build_safety_flags(
    issues: tuple[HumanReviewAuditBundleExportVerificationIssue, ...],
    hash_verified: bool,
    length_verified: bool,
    state_verifiable: bool,
    safety_notice_present: bool,
) -> HumanReviewAuditBundleExportVerificationSafetyFlags:
    blocking = any(
        i.severity == HumanReviewAuditBundleExportVerificationSeverity.BLOCKING.value
        for i in issues
    )
    return HumanReviewAuditBundleExportVerificationSafetyFlags(
        is_safe=not blocking,
        audit_only=True,
        no_executable_actions=True,
        no_trading_instructions=True,
        no_approval_claims=True,
        references_opaque=True,
        no_network=True,
        no_server=True,
        hash_verified=hash_verified,
        length_verified=length_verified,
        state_verifiable=state_verifiable,
        safety_notice_present=safety_notice_present,
    )


# ---------------------------------------------------------------------------
# Generated report text builder (for internal safety scan only)
# ---------------------------------------------------------------------------


def _build_report_text_for_scan(
    report: HumanReviewAuditBundleExportVerificationReport,
) -> str:
    """Build a minimal deterministic text representation for forbidden-phrase scanning.

    This is a Step-1 internal helper. Step-2 writer functions will produce the
    public serialization; the engine will then scan the writer output.
    """
    parts = [
        SAFETY_NOTICE,
        f"State: {report.state.value}",
        f"verification_id: {report.verification_id}",
        f"report_id: {report.report_id}",
        f"manifest_id: {report.manifest_id}",
        f"bundle_report_id: {report.bundle_report_id}",
        f"notes: {report.notes}",
    ]
    for key, value in sorted(report.input_summary.items()):
        parts.append(f"input_summary.{key}: {value}")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Main engine
# ---------------------------------------------------------------------------


def verify_human_review_audit_bundle_export(
    input: HumanReviewAuditBundleExportVerificationInput,  # noqa: A002
) -> HumanReviewAuditBundleExportVerificationReport:
    """Verify caller-provided artifact bytes against an MVP-44 export manifest.

    The function is pure and performs no I/O. It returns a deterministic
    verification report for the same inputs.
    """
    manifest = input.manifest
    config = input.config
    generated_at = _resolve_generated_at(input.generated_at, manifest)
    input_summary = _build_input_summary(manifest, input.expected_format)
    issues: list[HumanReviewAuditBundleExportVerificationIssue] = []
    counter = 1

    # Validate manifest metadata.
    metadata_issues, counter = _validate_manifest_metadata(manifest, generated_at, counter)
    issues.extend(metadata_issues)

    # Handle manifest states that do not represent a written artifact.
    if manifest.state == HumanReviewAuditBundleExportState.BLOCKED:
        issues.append(
            _build_issue(
                issue_type="upstream_blocked",
                severity=HumanReviewAuditBundleExportVerificationSeverity.BLOCKING,
                reason_code=HumanReviewAuditBundleExportVerificationReasonCode.UPSTREAM_BLOCKED,
                source="manifest_state",
                title="Manifest state is BLOCKED",
                description="The upstream export manifest is BLOCKED; no artifact can be verified.",
                generated_at=generated_at,
                counter=counter,
            )
        )
        counter += 1
        state = HumanReviewAuditBundleExportVerificationState.BLOCKED
    elif manifest.state == HumanReviewAuditBundleExportState.NOT_APPLICABLE:
        if config.allow_not_applicable:
            state = HumanReviewAuditBundleExportVerificationState.NOT_APPLICABLE
        else:
            issues.append(
                _build_issue(
                    issue_type="state_not_verifiable",
                    severity=HumanReviewAuditBundleExportVerificationSeverity.BLOCKING,
                    reason_code=HumanReviewAuditBundleExportVerificationReasonCode.STATE_NOT_VERIFIABLE,
                    source="manifest_state",
                    title="Manifest state is NOT_APPLICABLE and allow_not_applicable is False",
                    description="The manifest has no expected artifact and allow_not_applicable is disabled.",
                    generated_at=generated_at,
                    counter=counter,
                )
            )
            counter += 1
            state = HumanReviewAuditBundleExportVerificationState.BLOCKED
    elif manifest.state == HumanReviewAuditBundleExportState.PLANNED:
        if config.allow_not_applicable:
            state = HumanReviewAuditBundleExportVerificationState.NOT_APPLICABLE
        else:
            issues.append(
                _build_issue(
                    issue_type="state_not_verifiable",
                    severity=HumanReviewAuditBundleExportVerificationSeverity.BLOCKING,
                    reason_code=HumanReviewAuditBundleExportVerificationReasonCode.STATE_NOT_VERIFIABLE,
                    source="manifest_state",
                    title="Manifest state is PLANNED and allow_not_applicable is False",
                    description="PLANNED manifests have no written artifact and allow_not_applicable is disabled.",
                    generated_at=generated_at,
                    counter=counter,
                )
            )
            counter += 1
            state = HumanReviewAuditBundleExportVerificationState.BLOCKED
    elif manifest.state != HumanReviewAuditBundleExportState.WRITTEN:
        issues.append(
            _build_issue(
                issue_type="state_not_verifiable",
                severity=HumanReviewAuditBundleExportVerificationSeverity.BLOCKING,
                reason_code=HumanReviewAuditBundleExportVerificationReasonCode.STATE_NOT_VERIFIABLE,
                source="manifest_state",
                title="Manifest state is not verifiable",
                description=f"Unexpected manifest state {manifest.state.value!r}.",
                generated_at=generated_at,
                counter=counter,
            )
        )
        counter += 1
        state = HumanReviewAuditBundleExportVerificationState.INVALID
    else:
        state = HumanReviewAuditBundleExportVerificationState.VERIFIED

    # Format pre-check for expected_format.
    if input.expected_format and input.expected_format not in ALLOWED_FORMATS:
        severity = (
            HumanReviewAuditBundleExportVerificationSeverity.BLOCKING
            if config.strict
            else HumanReviewAuditBundleExportVerificationSeverity.ADVISORY
        )
        issues.append(
            _build_issue(
                issue_type="unsupported_format",
                severity=severity,
                reason_code=HumanReviewAuditBundleExportVerificationReasonCode.UNSUPPORTED_FORMAT,
                source="expected_format",
                title="Unsupported expected format",
                description=f"Expected format {input.expected_format!r} is not in the allowlist {ALLOWED_FORMATS}.",
                generated_at=generated_at,
                counter=counter,
            )
        )
        counter += 1

    # Perform byte-level checks only for WRITTEN manifests.
    hash_verified = False
    length_verified = False
    safety_notice_present = False
    checks_performed = 0
    if state == HumanReviewAuditBundleExportVerificationState.VERIFIED:
        hash_issues, counter, hash_verified = _check_hash(
            input.artifact_bytes, manifest, generated_at, counter
        )
        issues.extend(hash_issues)
        if hash_verified:
            checks_performed += 1

        length_issues, counter, length_verified = _check_length(
            input.artifact_bytes, manifest, generated_at, counter
        )
        issues.extend(length_issues)
        if length_verified:
            checks_performed += 1

        if config.require_safety_notice:
            safety_issues, counter, safety_notice_present = _check_safety_notice(
                input.artifact_bytes, generated_at, counter
            )
            issues.extend(safety_issues)
            if safety_notice_present:
                checks_performed += 1

    # Classify format from bytes for the report, advisory only.
    _classify_format(input.artifact_bytes)

    # Determine final state from issues.
    final_state = _determine_state(tuple(issues), config.strict, state)

    # Compute deterministic IDs.
    report_id = _build_report_id(
        manifest.manifest_id,
        manifest.bundle_report_id,
        manifest.content_hash,
        manifest.content_length,
        generated_at,
    )
    verification_id = _build_verification_id(
        report_id,
        manifest.manifest_id,
        final_state,
        manifest.content_hash,
        manifest.content_length,
        generated_at,
    )

    # Build notes based on final state.
    if final_state == HumanReviewAuditBundleExportVerificationState.VERIFIED:
        notes = "Verification succeeded: byte hash and length match the manifest."
    elif final_state == HumanReviewAuditBundleExportVerificationState.NOT_APPLICABLE:
        notes = "No artifact expected for the manifest state; verification is not applicable."
    elif final_state == HumanReviewAuditBundleExportVerificationState.BLOCKED:
        notes = "Verification blocked: inconsistent bytes, metadata, or unsafe manifest state."
    elif final_state == HumanReviewAuditBundleExportVerificationState.INVALID:
        notes = "Verification invalid: malformed input or unsupported manifest state."
    elif final_state == HumanReviewAuditBundleExportVerificationState.DEGRADED:
        notes = "Verification degraded: advisory-only gaps found."
    else:
        notes = "Verification completed."

    # Build report (pre-forbidden-scan).
    hash_mismatch = any(i.issue_type == "hash_mismatch" for i in issues)
    length_mismatch = any(i.issue_type == "length_mismatch" for i in issues)
    state_not_verifiable = (
        final_state in (
            HumanReviewAuditBundleExportVerificationState.BLOCKED,
            HumanReviewAuditBundleExportVerificationState.INVALID,
        )
        and manifest.state != HumanReviewAuditBundleExportState.WRITTEN
        and not config.allow_not_applicable
    )
    missing_safety_notice = (
        not safety_notice_present
        and config.require_safety_notice
        and manifest.state == HumanReviewAuditBundleExportState.WRITTEN
    )

    report = HumanReviewAuditBundleExportVerificationReport(
        verification_id=verification_id,
        report_id=report_id,
        manifest_id=manifest.manifest_id,
        bundle_report_id=manifest.bundle_report_id,
        generated_at=generated_at,
        state=final_state,
        config=config,
        input_summary=input_summary,
        data_quality=_build_data_quality(
            issues=tuple(issues),
            hash_mismatch=hash_mismatch,
            length_mismatch=length_mismatch,
            state_not_verifiable=state_not_verifiable,
            missing_safety_notice=missing_safety_notice,
            forbidden_term_count=0,
            checks_performed=checks_performed,
        ),
        safety_flags=_build_safety_flags(
            issues=tuple(issues),
            hash_verified=hash_verified,
            length_verified=length_verified,
            state_verifiable=manifest.state == HumanReviewAuditBundleExportState.WRITTEN,
            safety_notice_present=safety_notice_present,
        ),
        reason_codes=_build_reason_codes(final_state, tuple(issues)),
        issues=tuple(issues),
        metadata=input.metadata,
        notes=notes,
    )

    # Scan generated report text for forbidden phrases.
    report_text = _build_report_text_for_scan(report)
    forbidden = _scan_forbidden_terms(report_text)
    if forbidden:
        forbidden_issue = _build_issue(
            issue_type="forbidden_term_present",
            severity=HumanReviewAuditBundleExportVerificationSeverity.BLOCKING,
            reason_code=HumanReviewAuditBundleExportVerificationReasonCode.FORBIDDEN_TERM_PRESENT,
            source="generated_report_text",
            title="Generated verification report contains forbidden terms",
            description=f"Forbidden terms found: {', '.join(forbidden)}.",
            generated_at=generated_at,
            counter=counter,
        )
        issues.append(forbidden_issue)
        final_state = HumanReviewAuditBundleExportVerificationState.BLOCKED
        verification_id = _build_verification_id(
            report_id,
            manifest.manifest_id,
            final_state,
            manifest.content_hash,
            manifest.content_length,
            generated_at,
        )
        object.__setattr__(report, "verification_id", verification_id)
        object.__setattr__(report, "state", final_state)
        object.__setattr__(report, "reason_codes", _build_reason_codes(final_state, tuple(issues)))
        object.__setattr__(report, "issues", tuple(issues))
        object.__setattr__(report, "notes", "Verification blocked: generated report contains forbidden language.")
        object.__setattr__(
            report,
            "data_quality",
            _build_data_quality(
                issues=tuple(issues),
                hash_mismatch=hash_mismatch,
                length_mismatch=length_mismatch,
                state_not_verifiable=state_not_verifiable,
                missing_safety_notice=missing_safety_notice,
                forbidden_term_count=len(forbidden),
                checks_performed=checks_performed,
            ),
        )
        object.__setattr__(report, "safety_flags", _build_safety_flags(
            issues=tuple(issues),
            hash_verified=hash_verified,
            length_verified=length_verified,
            state_verifiable=manifest.state == HumanReviewAuditBundleExportState.WRITTEN,
            safety_notice_present=safety_notice_present,
        ))

    return report
