"""hunter.human_review_audit_bundle — MVP-43.

A local, audit-only Human Review Audit Bundle Export layer. The package
accepts caller-provided Human Review Queue, Decision Log, and Consistency
reports and produces a deterministic, normalized bundle report without
opening or following any reference strings.
"""

from .engine import build_human_review_audit_bundle
from .writer import (
    bundle_report_to_dict,
    bundle_report_to_json,
    bundle_report_to_markdown,
)
from .models import (
    BUNDLE_KIND,
    HUMAN_REVIEW_AUDIT_BUNDLE_VERSION,
    SAFETY_NOTICE,
    HumanReviewAuditBundleConfig,
    HumanReviewAuditBundleDataQuality,
    HumanReviewAuditBundleInput,
    HumanReviewAuditBundleIssue,
    HumanReviewAuditBundleReasonCode,
    HumanReviewAuditBundleReport,
    HumanReviewAuditBundleSafetyFlags,
    HumanReviewAuditBundleSection,
    HumanReviewAuditBundleSeverity,
    HumanReviewAuditBundleState,
)

__all__ = [
    "BUNDLE_KIND",
    "HUMAN_REVIEW_AUDIT_BUNDLE_VERSION",
    "SAFETY_NOTICE",
    "build_human_review_audit_bundle",
    "bundle_report_to_dict",
    "bundle_report_to_json",
    "bundle_report_to_markdown",
    "HumanReviewAuditBundleConfig",
    "HumanReviewAuditBundleDataQuality",
    "HumanReviewAuditBundleInput",
    "HumanReviewAuditBundleIssue",
    "HumanReviewAuditBundleReasonCode",
    "HumanReviewAuditBundleReport",
    "HumanReviewAuditBundleSafetyFlags",
    "HumanReviewAuditBundleSection",
    "HumanReviewAuditBundleSeverity",
    "HumanReviewAuditBundleState",
]
