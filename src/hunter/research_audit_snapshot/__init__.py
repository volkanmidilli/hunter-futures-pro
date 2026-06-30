"""Local research audit snapshot package.

MVP-23 — Local Research Audit Snapshot.

Human-audit / contractor-handoff artifact only. Not release approval, not
deployment approval, not trading signal, not trade approval, not execution
approval, not strategy approval, not transaction permission.
"""

from hunter.research_audit_snapshot.engine import (
    build_audit_snapshot_data_quality,
    build_audit_snapshot_item,
    build_audit_snapshot_safety_flags,
    build_audit_snapshot_section,
    build_audit_snapshot_summary,
    build_research_audit_snapshot,
    has_unsafe_audit_snapshot_content,
)
from hunter.research_audit_snapshot.models import (
    AUDIT_SNAPSHOT_ADVISORY_REASON_CODES,
    AUDIT_SNAPSHOT_BLOCKING_REASON_CODES,
    AUDIT_SNAPSHOT_INCOMPLETE_REASON_CODES,
    AUDIT_SNAPSHOT_REASON_CODES,
    AUDIT_SNAPSHOT_STALE_REASON_CODES,
    BLOCKED_ARTIFACT_ITEM,
    CANONICAL_AUDIT_SNAPSHOT_SECTION_ORDER,
    FILE_REFS_NOT_TRAVERSED,
    FORBIDDEN_SNAPSHOT_TERMS,
    HUMAN_AUDIT_GUIDE_NON_GATING,
    INCOMPLETE_ARTIFACT_ITEM,
    INVALID_SNAPSHOT_CONFIG,
    MISSING_ARTIFACT_SUMMARIES,
    MISSING_REQUIRED_SECTION,
    NO_ACTION_COMMANDS_EMITTED,
    OPEN_ITEMS_PRESENT,
    ARTIFACT_FILES_NOT_READ,
    SNAPSHOT_VERSION,
    STALE_ARTIFACT_DETECTED,
    UNSAFE_SNAPSHOT_CONTENT,
    UNKNOWN_SNAPSHOT_STATE,
    AuditSnapshotConfig,
    AuditSnapshotDataQuality,
    AuditSnapshotItem,
    AuditSnapshotItemSeverity,
    AuditSnapshotKind,
    AuditSnapshotSafetyFlags,
    AuditSnapshotSection,
    AuditSnapshotSectionKind,
    AuditSnapshotState,
    AuditSnapshotSummary,
    ResearchAuditSnapshot,
)
from hunter.research_audit_snapshot.writer import (
    DEFAULT_AUDIT_SNAPSHOT_JSON_PATH,
    DEFAULT_AUDIT_SNAPSHOT_MARKDOWN_PATH,
    _atomic_write,
    _coerce_path,
    _iso,
    _serialize_value,
    _severity_value,
    _state_value,
    atomic_write_json_research_audit_snapshot,
    atomic_write_markdown_research_audit_snapshot,
    audit_snapshot_config_to_dict,
    audit_snapshot_data_quality_to_dict,
    audit_snapshot_item_to_dict,
    audit_snapshot_safety_flags_to_dict,
    audit_snapshot_section_to_dict,
    audit_snapshot_summary_to_dict,
    research_audit_snapshot_to_dict,
    research_audit_snapshot_to_markdown,
    write_research_audit_snapshot,
)

__all__ = (
    # Version
    "SNAPSHOT_VERSION",
    # Enums
    "AuditSnapshotState",
    "AuditSnapshotKind",
    "AuditSnapshotSectionKind",
    "AuditSnapshotItemSeverity",
    # Constants
    "CANONICAL_AUDIT_SNAPSHOT_SECTION_ORDER",
    # Config / safety
    "AuditSnapshotConfig",
    "AuditSnapshotSafetyFlags",
    # Models
    "AuditSnapshotItem",
    "AuditSnapshotSection",
    "AuditSnapshotSummary",
    "AuditSnapshotDataQuality",
    "ResearchAuditSnapshot",
    # Reason codes
    "AUDIT_SNAPSHOT_REASON_CODES",
    "AUDIT_SNAPSHOT_BLOCKING_REASON_CODES",
    "AUDIT_SNAPSHOT_INCOMPLETE_REASON_CODES",
    "AUDIT_SNAPSHOT_STALE_REASON_CODES",
    "AUDIT_SNAPSHOT_ADVISORY_REASON_CODES",
    "UNSAFE_SNAPSHOT_CONTENT",
    "INVALID_SNAPSHOT_CONFIG",
    "MISSING_REQUIRED_SECTION",
    "MISSING_ARTIFACT_SUMMARIES",
    "BLOCKED_ARTIFACT_ITEM",
    "STALE_ARTIFACT_DETECTED",
    "OPEN_ITEMS_PRESENT",
    "INCOMPLETE_ARTIFACT_ITEM",
    "UNKNOWN_SNAPSHOT_STATE",
    "FILE_REFS_NOT_TRAVERSED",
    "ARTIFACT_FILES_NOT_READ",
    "NO_ACTION_COMMANDS_EMITTED",
    "HUMAN_AUDIT_GUIDE_NON_GATING",
    # Helpers
    "FORBIDDEN_SNAPSHOT_TERMS",
    # Engine
    "has_unsafe_audit_snapshot_content",
    "build_audit_snapshot_safety_flags",
    "build_audit_snapshot_item",
    "build_audit_snapshot_section",
    "build_audit_snapshot_summary",
    "build_audit_snapshot_data_quality",
    "build_research_audit_snapshot",
    # Writer defaults
    "DEFAULT_AUDIT_SNAPSHOT_JSON_PATH",
    "DEFAULT_AUDIT_SNAPSHOT_MARKDOWN_PATH",
    # Writer helpers
    "_atomic_write",
    "_coerce_path",
    "_iso",
    "_serialize_value",
    "_severity_value",
    "_state_value",
    # Writer serialization
    "audit_snapshot_config_to_dict",
    "audit_snapshot_safety_flags_to_dict",
    "audit_snapshot_item_to_dict",
    "audit_snapshot_section_to_dict",
    "audit_snapshot_summary_to_dict",
    "audit_snapshot_data_quality_to_dict",
    "research_audit_snapshot_to_dict",
    "research_audit_snapshot_to_markdown",
    # Writer I/O
    "atomic_write_json_research_audit_snapshot",
    "atomic_write_markdown_research_audit_snapshot",
    "write_research_audit_snapshot",
)
