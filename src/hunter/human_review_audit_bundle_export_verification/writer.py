"""Pure writer for hunter.human_review_audit_bundle_export_verification.

MVP-45 Step 2 — Deterministic serialization of verification reports to dict,
JSON text, and Markdown text. No filesystem writes; all functions return
in-memory content only.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from enum import Enum
from json import dumps
from typing import Any

from .models import (
    HUMAN_REVIEW_AUDIT_BUNDLE_EXPORT_VERIFICATION_VERSION,
    SAFETY_NOTICE,
    VERIFICATION_KIND,
    HumanReviewAuditBundleExportVerificationConfig,
    HumanReviewAuditBundleExportVerificationDataQuality,
    HumanReviewAuditBundleExportVerificationIssue,
    HumanReviewAuditBundleExportVerificationReport,
    HumanReviewAuditBundleExportVerificationSafetyFlags,
)

# ---------------------------------------------------------------------------
# No-authenticity statement
# ---------------------------------------------------------------------------

# Carefully crafted to survive the engine's forbidden-term scanner.
# Negation phrases in ALLOWED_NEGATION_TERMS ("audit-only", "does not imply",
# "no recommendation") cause the scanner to strip the entire sentence,
# removing the negated forbidden terms.
NO_AUTHENTICITY_STATEMENT: str = (
    "This verification is a local, audit-only replay of byte and metadata "
    "consistency only. "
    "It does not imply authenticity, tamper-proofing, legal validity, "
    "production readiness, trading readiness, or suitability for any purpose. "
    "It provides no recommendation, no approval, and no certification."
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


def _issue_to_dict(
    issue: HumanReviewAuditBundleExportVerificationIssue,
) -> dict[str, Any]:
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


def _config_to_dict(
    config: HumanReviewAuditBundleExportVerificationConfig,
) -> dict[str, bool]:
    return {
        "strict": config.strict,
        "require_safety_notice": config.require_safety_notice,
        "verify_text_hash": config.verify_text_hash,
        "allow_not_applicable": config.allow_not_applicable,
    }


def _data_quality_to_dict(
    dq: HumanReviewAuditBundleExportVerificationDataQuality,
) -> dict[str, int]:
    return {
        "checks_performed": dq.checks_performed,
        "hash_mismatch_count": dq.hash_mismatch_count,
        "length_mismatch_count": dq.length_mismatch_count,
        "state_not_verifiable_count": dq.state_not_verifiable_count,
        "missing_safety_notice_count": dq.missing_safety_notice_count,
        "forbidden_term_count": dq.forbidden_term_count,
        "blocking_issues": dq.blocking_issues,
        "advisory_issues": dq.advisory_issues,
        "info_findings": dq.info_findings,
    }


def _safety_flags_to_dict(
    flags: HumanReviewAuditBundleExportVerificationSafetyFlags,
) -> dict[str, bool]:
    return {
        "is_safe": flags.is_safe,
        "audit_only": flags.audit_only,
        "no_executable_actions": flags.no_executable_actions,
        "no_trading_instructions": flags.no_trading_instructions,
        "no_approval_claims": flags.no_approval_claims,
        "references_opaque": flags.references_opaque,
        "no_network": flags.no_network,
        "no_server": flags.no_server,
        "hash_verified": flags.hash_verified,
        "length_verified": flags.length_verified,
        "state_verifiable": flags.state_verifiable,
        "safety_notice_present": flags.safety_notice_present,
    }


# ---------------------------------------------------------------------------
# Dict serialization
# ---------------------------------------------------------------------------


def verification_report_to_dict(
    report: HumanReviewAuditBundleExportVerificationReport,
) -> dict[str, Any]:
    """Serialize a verification report to a deterministic JSON-compatible dict.

    The output contains no raw artifact bytes and no resolved filesystem paths.
    All IDs and refs are opaque strings. Field order is stable.
    """
    return {
        "kind": VERIFICATION_KIND,
        "version": HUMAN_REVIEW_AUDIT_BUNDLE_EXPORT_VERIFICATION_VERSION,
        "safety_notice": SAFETY_NOTICE,
        "no_authenticity_statement": NO_AUTHENTICITY_STATEMENT,
        "verification_id": report.verification_id,
        "report_id": report.report_id,
        "manifest_id": report.manifest_id,
        "bundle_report_id": report.bundle_report_id,
        "generated_at": _iso_datetime(report.generated_at),
        "state": report.state.value,
        "config": _config_to_dict(report.config),
        "input_summary": _sorted_str_dict(report.input_summary),
        "data_quality": _data_quality_to_dict(report.data_quality),
        "safety_flags": _safety_flags_to_dict(report.safety_flags),
        "reason_codes": [_enum_value(rc) for rc in report.reason_codes],
        "issues": [_issue_to_dict(issue) for issue in report.issues],
        "metadata": _sorted_str_dict(report.metadata),
        "notes": report.notes,
    }


# ---------------------------------------------------------------------------
# JSON text serialization
# ---------------------------------------------------------------------------


def verification_report_to_json(
    report: HumanReviewAuditBundleExportVerificationReport,
) -> str:
    """Serialize a verification report to a deterministic JSON string.

    Uses sort_keys=True and ensure_ascii=True for stable, portable output.
    """
    return dumps(
        verification_report_to_dict(report),
        indent=2,
        ensure_ascii=True,
        sort_keys=True,
    )


# ---------------------------------------------------------------------------
# Markdown text serialization
# ---------------------------------------------------------------------------


def _md_escape(value: str) -> str:
    """Escape pipe characters for safe use in Markdown table cells."""
    return value.replace("|", "\\|")


def _md_bool(value: bool) -> str:
    return "true" if value else "false"


def verification_report_to_markdown(
    report: HumanReviewAuditBundleExportVerificationReport,
) -> str:
    """Serialize a verification report to a deterministic Markdown string.

    The safety notice and no-authenticity statement appear at the top.
    No raw bytes, resolved paths, shell commands, or executable content
    is included.
    """
    lines: list[str] = []
    lines.append("# Human Review Audit Bundle Export Verification")
    lines.append("")
    lines.append(f"> {SAFETY_NOTICE}")
    lines.append("")
    lines.append(f"> {NO_AUTHENTICITY_STATEMENT}")
    lines.append("")

    # --- Summary ---
    lines.append("## Summary")
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("|-------|-------|")
    lines.append(f"| Verification ID | `{_md_escape(report.verification_id)}` |")
    lines.append(f"| Report ID | `{_md_escape(report.report_id)}` |")
    lines.append(f"| Manifest ID | `{_md_escape(report.manifest_id)}` |")
    lines.append(f"| Bundle Report ID | `{_md_escape(report.bundle_report_id)}` |")
    lines.append(f"| Generated At | {_iso_datetime(report.generated_at) or 'N/A'} |")
    lines.append(f"| State | {report.state.value} |")
    lines.append("")

    # --- Reason Codes ---
    lines.append("## Reason Codes")
    lines.append("")
    if report.reason_codes:
        for idx, rc in enumerate(report.reason_codes, 1):
            lines.append(f"{idx}. `{_enum_value(rc)}`")
    else:
        lines.append("No reason codes.")
    lines.append("")

    # --- Data Quality ---
    dq = report.data_quality
    lines.append("## Data Quality")
    lines.append("")
    lines.append("| Counter | Value |")
    lines.append("|---------|-------|")
    lines.append(f"| Checks Performed | {dq.checks_performed} |")
    lines.append(f"| Hash Mismatch Count | {dq.hash_mismatch_count} |")
    lines.append(f"| Length Mismatch Count | {dq.length_mismatch_count} |")
    lines.append(f"| State Not Verifiable Count | {dq.state_not_verifiable_count} |")
    lines.append(f"| Missing Safety Notice Count | {dq.missing_safety_notice_count} |")
    lines.append(f"| Forbidden Term Count | {dq.forbidden_term_count} |")
    lines.append(f"| Blocking Issues | {dq.blocking_issues} |")
    lines.append(f"| Advisory Issues | {dq.advisory_issues} |")
    lines.append(f"| Info Findings | {dq.info_findings} |")
    lines.append("")

    # --- Safety Flags ---
    sf = report.safety_flags
    lines.append("## Safety Flags")
    lines.append("")
    lines.append("| Flag | Value |")
    lines.append("|------|-------|")
    lines.append(f"| Is Safe | {_md_bool(sf.is_safe)} |")
    lines.append(f"| Audit Only | {_md_bool(sf.audit_only)} |")
    lines.append(f"| No Executable Actions | {_md_bool(sf.no_executable_actions)} |")
    lines.append(f"| No Trading Instructions | {_md_bool(sf.no_trading_instructions)} |")
    lines.append(f"| No Approval Claims | {_md_bool(sf.no_approval_claims)} |")
    lines.append(f"| References Opaque | {_md_bool(sf.references_opaque)} |")
    lines.append(f"| No Network | {_md_bool(sf.no_network)} |")
    lines.append(f"| No Server | {_md_bool(sf.no_server)} |")
    lines.append(f"| Hash Verified | {_md_bool(sf.hash_verified)} |")
    lines.append(f"| Length Verified | {_md_bool(sf.length_verified)} |")
    lines.append(f"| State Verifiable | {_md_bool(sf.state_verifiable)} |")
    lines.append(f"| Safety Notice Present | {_md_bool(sf.safety_notice_present)} |")
    lines.append("")

    # --- Configuration ---
    cfg = report.config
    lines.append("## Configuration")
    lines.append("")
    lines.append("| Setting | Value |")
    lines.append("|---------|-------|")
    lines.append(f"| Strict | {_md_bool(cfg.strict)} |")
    lines.append(f"| Require Safety Notice | {_md_bool(cfg.require_safety_notice)} |")
    lines.append(f"| Verify Text Hash | {_md_bool(cfg.verify_text_hash)} |")
    lines.append(f"| Allow Not Applicable | {_md_bool(cfg.allow_not_applicable)} |")
    lines.append("")

    # --- Input Summary ---
    lines.append("## Input Summary")
    lines.append("")
    if report.input_summary:
        lines.append("| Key | Value |")
        lines.append("|-----|-------|")
        for key, value in sorted(report.input_summary.items()):
            lines.append(f"| {_md_escape(key)} | {_md_escape(str(value))} |")
    else:
        lines.append("No input summary.")
    lines.append("")

    # --- Issues ---
    lines.append("## Issues")
    lines.append("")
    if report.issues:
        for issue in report.issues:
            lines.append(f"### {_md_escape(issue.title)}")
            lines.append("")
            lines.append(f"- **Issue ID**: `{_md_escape(issue.issue_id)}`")
            lines.append(f"- **Type**: {issue.issue_type}")
            lines.append(f"- **Severity**: {issue.severity}")
            lines.append(f"- **Source**: {issue.source}")
            lines.append(f"- **Reason Codes**: {', '.join(issue.reason_codes) if issue.reason_codes else 'N/A'}")
            lines.append(f"- **Generated At**: {_iso_datetime(issue.generated_at) or 'N/A'}")
            lines.append(f"- **Description**: {_md_escape(issue.description)}")
            lines.append("")
    else:
        lines.append("No issues found.")
        lines.append("")

    # --- Metadata ---
    lines.append("## Metadata")
    lines.append("")
    if report.metadata:
        lines.append("| Key | Value |")
        lines.append("|-----|-------|")
        for key, value in sorted(report.metadata.items()):
            lines.append(f"| {_md_escape(key)} | {_md_escape(str(value))} |")
    else:
        lines.append("No metadata.")
    lines.append("")

    # --- Notes ---
    lines.append("## Notes")
    lines.append("")
    lines.append(report.notes)
    lines.append("")

    # --- Footer ---
    lines.append("---")
    lines.append("")
    lines.append(
        f"*Generated by `{VERIFICATION_KIND}` "
        f"v{HUMAN_REVIEW_AUDIT_BUNDLE_EXPORT_VERIFICATION_VERSION}*"
    )

    return "\n".join(lines)
