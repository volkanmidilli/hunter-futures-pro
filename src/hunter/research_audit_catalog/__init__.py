"""Local research audit catalog package.

MVP-21 — Local Research Audit Catalog.

Human-audit / contractor-handoff artifact only. Not release approval, not
deployment approval, not trading signal, not trade approval, not execution
approval, not strategy approval, not transaction permission.
"""

from hunter.research_audit_catalog.engine import (
    build_audit_catalog_data_quality,
    build_audit_catalog_entry,
    build_audit_catalog_safety_flags,
    build_audit_catalog_summary,
    build_research_audit_catalog,
    has_unsafe_audit_catalog_content,
)
from hunter.research_audit_catalog.models import (
    CATALOG_ARTIFACT_KINDS,
    CATALOG_BLOCKING_REASON_CODES,
    CATALOG_NON_BLOCKING_REASON_CODES,
    CATALOG_REASON_CODES,
    CATALOG_VERSION,
    CATALOG_ERROR,
    DEFAULT_BLOCKED,
    DUPLICATE_ARTIFACT_ID,
    EMPTY_CATALOG,
    FORBIDDEN_CATALOG_TERMS,
    INVALID_ARTIFACT,
    INVALID_ARTIFACT_ID,
    INVALID_ARTIFACT_KIND,
    MISSING_ARTIFACTS,
    STALE_ARTIFACT,
    UNSAFE_ARTIFACT_STATE,
    UNSAFE_CATALOG_CONTENT,
    UNSAFE_SAFETY_FLAGS,
    UNSUPPORTED_ARTIFACT_VERSION,
    CatalogArtifactKind,
    CatalogConfig,
    CatalogDataQuality,
    CatalogEntry,
    CatalogSafetyFlags,
    CatalogState,
    CatalogSummary,
    ResearchCatalog,
)
from hunter.research_audit_catalog.writer import (
    DEFAULT_RESEARCH_AUDIT_CATALOG_JSON_PATH,
    DEFAULT_RESEARCH_AUDIT_CATALOG_MARKDOWN_PATH,
    atomic_write_json_research_audit_catalog,
    atomic_write_markdown_research_audit_catalog,
    catalog_config_to_dict,
    catalog_data_quality_to_dict,
    catalog_entry_to_dict,
    catalog_safety_flags_to_dict,
    catalog_summary_to_dict,
    research_audit_catalog_to_dict,
    research_audit_catalog_to_markdown,
    write_research_audit_catalog,
)

__all__ = (
    # Version
    "CATALOG_VERSION",
    # Enums
    "CatalogArtifactKind",
    "CatalogState",
    # Config / safety
    "CatalogConfig",
    "CatalogSafetyFlags",
    # Models
    "CatalogEntry",
    "CatalogSummary",
    "CatalogDataQuality",
    "ResearchCatalog",
    # Reason codes
    "CATALOG_REASON_CODES",
    "CATALOG_BLOCKING_REASON_CODES",
    "CATALOG_NON_BLOCKING_REASON_CODES",
    "MISSING_ARTIFACTS",
    "INVALID_ARTIFACT",
    "INVALID_ARTIFACT_ID",
    "INVALID_ARTIFACT_KIND",
    "UNSUPPORTED_ARTIFACT_VERSION",
    "UNSAFE_ARTIFACT_STATE",
    "UNSAFE_SAFETY_FLAGS",
    "DUPLICATE_ARTIFACT_ID",
    "EMPTY_CATALOG",
    "UNSAFE_CATALOG_CONTENT",
    "STALE_ARTIFACT",
    "CATALOG_ERROR",
    "DEFAULT_BLOCKED",
    # Helpers
    "FORBIDDEN_CATALOG_TERMS",
    "CATALOG_ARTIFACT_KINDS",
    # Engine
    "has_unsafe_audit_catalog_content",
    "build_audit_catalog_safety_flags",
    "build_audit_catalog_entry",
    "build_audit_catalog_summary",
    "build_audit_catalog_data_quality",
    "build_research_audit_catalog",
    # Writer
    "research_audit_catalog_to_dict",
    "research_audit_catalog_to_markdown",
    "atomic_write_json_research_audit_catalog",
    "atomic_write_markdown_research_audit_catalog",
    "write_research_audit_catalog",
    "DEFAULT_RESEARCH_AUDIT_CATALOG_JSON_PATH",
    "DEFAULT_RESEARCH_AUDIT_CATALOG_MARKDOWN_PATH",
    # Serialization helpers
    "catalog_config_to_dict",
    "catalog_safety_flags_to_dict",
    "catalog_entry_to_dict",
    "catalog_summary_to_dict",
    "catalog_data_quality_to_dict",
)
