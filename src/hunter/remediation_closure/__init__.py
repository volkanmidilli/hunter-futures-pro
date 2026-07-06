"""MVP-39 — Local Research Remediation Closure Register."""

from __future__ import annotations

from hunter.remediation_closure.engine import build_remediation_closure_report
from hunter.remediation_closure.models import (
    FORBIDDEN_REMEDIATION_CLOSURE_TERMS,
    REMEDIATION_CLOSURE_VERSION,
    RemediationClosureBacklogItemRef,
    RemediationClosureConfig,
    RemediationClosureDataQuality,
    RemediationClosureDeclaration,
    RemediationClosureEligibilityState,
    RemediationClosureEvidenceSummary,
    RemediationClosureInput,
    RemediationClosureIssue,
    RemediationClosureIssueType,
    RemediationClosureLink,
    RemediationClosureLinkType,
    RemediationClosureReasonCode,
    RemediationClosureRecordState,
    RemediationClosureReport,
    RemediationClosureResult,
    RemediationClosureReviewOutcome,
    RemediationClosureReviewRecord,
    RemediationClosureSafetyFlags,
    RemediationClosureSeverity,
    RemediationClosureState,
    has_unsafe_remediation_closure_content,
)

# Conditional writer imports; writer.py is added in MVP-39 Step 2.
from pathlib import Path
import importlib.util

_writer_path = Path(__file__).with_name("writer.py")
if _writer_path.exists():
    from hunter.remediation_closure.writer import (
        DEFAULT_CSV_PATH,
        DEFAULT_JSON_PATH,
        DEFAULT_MD_PATH,
        atomic_write_csv_remediation_closure_report,
        atomic_write_json_remediation_closure_report,
        atomic_write_markdown_remediation_closure_report,
        remediation_closure_report_to_csv_text,
        remediation_closure_report_to_dict,
        remediation_closure_report_to_json_text,
        remediation_closure_report_to_markdown_text,
        write_remediation_closure_report,
    )

__all__ = [
    "FORBIDDEN_REMEDIATION_CLOSURE_TERMS",
    "REMEDIATION_CLOSURE_VERSION",
    "RemediationClosureBacklogItemRef",
    "RemediationClosureConfig",
    "RemediationClosureDataQuality",
    "RemediationClosureDeclaration",
    "RemediationClosureEligibilityState",
    "RemediationClosureEvidenceSummary",
    "RemediationClosureInput",
    "RemediationClosureIssue",
    "RemediationClosureIssueType",
    "RemediationClosureLink",
    "RemediationClosureLinkType",
    "RemediationClosureReasonCode",
    "RemediationClosureRecordState",
    "RemediationClosureReport",
    "RemediationClosureResult",
    "RemediationClosureReviewOutcome",
    "RemediationClosureReviewRecord",
    "RemediationClosureSafetyFlags",
    "RemediationClosureSeverity",
    "RemediationClosureState",
    "build_remediation_closure_report",
    "has_unsafe_remediation_closure_content",
]

if _writer_path.exists():
    __all__.extend([
        "DEFAULT_CSV_PATH",
        "DEFAULT_JSON_PATH",
        "DEFAULT_MD_PATH",
        "atomic_write_csv_remediation_closure_report",
        "atomic_write_json_remediation_closure_report",
        "atomic_write_markdown_remediation_closure_report",
        "remediation_closure_report_to_csv_text",
        "remediation_closure_report_to_dict",
        "remediation_closure_report_to_json_text",
        "remediation_closure_report_to_markdown_text",
        "write_remediation_closure_report",
    ])
