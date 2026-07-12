"""hunter.human_review_audit_bundle_export_verification — MVP-45.

A local, audit-only, read-only verification/replay layer for Human Review Audit
Bundle Export artifacts. The package accepts a caller-provided MVP-44 export
manifest, caller-provided artifact bytes, and optional metadata, then returns a
deterministic verification report without performing any filesystem, network, or
runtime I/O.
"""

from __future__ import annotations

from .engine import verify_human_review_audit_bundle_export
from .models import (
    HUMAN_REVIEW_AUDIT_BUNDLE_EXPORT_VERIFICATION_VERSION,
    HumanReviewAuditBundleExportVerificationConfig,
    HumanReviewAuditBundleExportVerificationDataQuality,
    HumanReviewAuditBundleExportVerificationInput,
    HumanReviewAuditBundleExportVerificationIssue,
    HumanReviewAuditBundleExportVerificationReasonCode,
    HumanReviewAuditBundleExportVerificationReport,
    HumanReviewAuditBundleExportVerificationSafetyFlags,
    HumanReviewAuditBundleExportVerificationSeverity,
    HumanReviewAuditBundleExportVerificationState,
    SAFETY_NOTICE,
    VERIFICATION_KIND,
)
from .writer import (
    NO_AUTHENTICITY_STATEMENT,
    verification_report_to_dict,
    verification_report_to_json,
    verification_report_to_markdown,
)

__all__ = [
    "HUMAN_REVIEW_AUDIT_BUNDLE_EXPORT_VERIFICATION_VERSION",
    "NO_AUTHENTICITY_STATEMENT",
    "SAFETY_NOTICE",
    "VERIFICATION_KIND",
    "verify_human_review_audit_bundle_export",
    "verification_report_to_dict",
    "verification_report_to_json",
    "verification_report_to_markdown",
    "HumanReviewAuditBundleExportVerificationConfig",
    "HumanReviewAuditBundleExportVerificationDataQuality",
    "HumanReviewAuditBundleExportVerificationInput",
    "HumanReviewAuditBundleExportVerificationIssue",
    "HumanReviewAuditBundleExportVerificationReasonCode",
    "HumanReviewAuditBundleExportVerificationReport",
    "HumanReviewAuditBundleExportVerificationSafetyFlags",
    "HumanReviewAuditBundleExportVerificationSeverity",
    "HumanReviewAuditBundleExportVerificationState",
]
