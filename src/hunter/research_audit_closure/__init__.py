"""Local research audit closure report package.

MVP-22 — Local Research Audit Closure Report.

Human-audit / contractor-handoff artifact only. Not release approval, not
deployment approval, not trading signal, not trade approval, not execution
approval, not strategy approval, not transaction permission.
"""

from hunter.research_audit_closure.engine import (
    build_audit_closure_data_quality,
    build_audit_closure_finding,
    build_audit_closure_safety_flags,
    build_audit_closure_section,
    build_audit_closure_summary,
    build_research_audit_closure_report,
    has_unsafe_audit_closure_content,
)
from hunter.research_audit_closure.writer import (
    DEFAULT_RESEARCH_AUDIT_CLOSURE_JSON_PATH,
    DEFAULT_RESEARCH_AUDIT_CLOSURE_MARKDOWN_PATH,
    atomic_write_json_research_audit_closure_report,
    atomic_write_markdown_research_audit_closure_report,
    audit_closure_config_to_dict,
    audit_closure_data_quality_to_dict,
    audit_closure_finding_to_dict,
    audit_closure_safety_flags_to_dict,
    audit_closure_section_to_dict,
    audit_closure_summary_to_dict,
    research_audit_closure_report_to_dict,
    research_audit_closure_report_to_markdown,
    write_research_audit_closure_report,
)
from hunter.research_audit_closure.models import (
    AUDIT_CLOSURE_BLOCKING_REASON_CODES,
    AUDIT_CLOSURE_INCOMPLETE_REASON_CODES,
    AUDIT_CLOSURE_NON_BLOCKING_REASON_CODES,
    AUDIT_CLOSURE_REASON_CODES,
    AUDIT_CLOSURE_SECTION_KINDS,
    BACKLOG_NOTES_REMAIN,
    CLOSURE_VERSION,
    DEFAULT_BLOCKED,
    EMPTY_COMPLETED_ARTIFACTS,
    FORBIDDEN_CLOSURE_TERMS,
    INCOMPLETE_ARTIFACT_CHAIN,
    INVALID_ARTIFACT_SUMMARY,
    INVALID_CLOSURE_CONFIG,
    MISSING_ARTIFACTS,
    MISSING_REQUIRED_SECTION,
    OPEN_FINDINGS_REMAIN,
    SECTION_BUILD_ERROR,
    SUMMARY_BUILD_ERROR,
    UNSAFE_CLOSURE_CONFIG,
    UNSAFE_CLOSURE_CONTENT,
    UNRESOLVED_BLOCKERS,
    UNKNOWN_CLOSURE_STATE,
    AuditClosureConfig,
    AuditClosureDataQuality,
    AuditClosureFinding,
    AuditClosureFindingSeverity,
    AuditClosureKind,
    AuditClosureSafetyFlags,
    AuditClosureSection,
    AuditClosureSectionKind,
    AuditClosureState,
    AuditClosureSummary,
    ResearchAuditClosureReport,
)

__all__ = (
    # Version
    "CLOSURE_VERSION",
    # Enums
    "AuditClosureState",
    "AuditClosureKind",
    "AuditClosureSectionKind",
    "AuditClosureFindingSeverity",
    # Constants
    "AUDIT_CLOSURE_SECTION_KINDS",
    # Config / safety
    "AuditClosureConfig",
    "AuditClosureSafetyFlags",
    # Models
    "AuditClosureFinding",
    "AuditClosureSection",
    "AuditClosureSummary",
    "AuditClosureDataQuality",
    "ResearchAuditClosureReport",
    # Reason codes
    "AUDIT_CLOSURE_REASON_CODES",
    "AUDIT_CLOSURE_BLOCKING_REASON_CODES",
    "AUDIT_CLOSURE_INCOMPLETE_REASON_CODES",
    "AUDIT_CLOSURE_NON_BLOCKING_REASON_CODES",
    "MISSING_ARTIFACTS",
    "INVALID_ARTIFACT_SUMMARY",
    "INVALID_CLOSURE_CONFIG",
    "UNSAFE_CLOSURE_CONFIG",
    "MISSING_REQUIRED_SECTION",
    "EMPTY_COMPLETED_ARTIFACTS",
    "UNRESOLVED_BLOCKERS",
    "UNSAFE_CLOSURE_CONTENT",
    "INCOMPLETE_ARTIFACT_CHAIN",
    "OPEN_FINDINGS_REMAIN",
    "BACKLOG_NOTES_REMAIN",
    "SECTION_BUILD_ERROR",
    "SUMMARY_BUILD_ERROR",
    "UNKNOWN_CLOSURE_STATE",
    "DEFAULT_BLOCKED",
    # Helpers
    "FORBIDDEN_CLOSURE_TERMS",
    # Engine
    "has_unsafe_audit_closure_content",
    "build_audit_closure_safety_flags",
    "build_audit_closure_finding",
    "build_audit_closure_section",
    "build_audit_closure_summary",
    "build_audit_closure_data_quality",
    "build_research_audit_closure_report",
    # Writer
    "DEFAULT_RESEARCH_AUDIT_CLOSURE_JSON_PATH",
    "DEFAULT_RESEARCH_AUDIT_CLOSURE_MARKDOWN_PATH",
    "atomic_write_json_research_audit_closure_report",
    "atomic_write_markdown_research_audit_closure_report",
    "audit_closure_config_to_dict",
    "audit_closure_data_quality_to_dict",
    "audit_closure_finding_to_dict",
    "audit_closure_safety_flags_to_dict",
    "audit_closure_section_to_dict",
    "audit_closure_summary_to_dict",
    "research_audit_closure_report_to_dict",
    "research_audit_closure_report_to_markdown",
    "write_research_audit_closure_report",
)
