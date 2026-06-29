"""Public API for hunter.research_archive_manifest package.

MVP-19 — Local Research Archive Manifest.

The research archive manifest is a human-audit inventory artifact only. It is not
a trading signal, not trade approval, not execution readiness, not strategy
readiness, not release/deployment approval, not transaction permission, and must
not be consumed by execution, strategy, Freqtrade shell, order, exchange, or any
MVP execution path.
"""

from __future__ import annotations

from hunter.research_archive_manifest.engine import (
    build_archive_artifact_entry,
    build_archive_manifest_data_quality,
    build_archive_manifest_safety_flags,
    build_archive_manifest_summary,
    build_research_archive_manifest,
    has_unsafe_archive_manifest_content,
)
from hunter.research_archive_manifest.writer import (
    DEFAULT_ARCHIVE_MANIFEST_JSON_PATH,
    DEFAULT_ARCHIVE_MANIFEST_MARKDOWN_PATH,
    archive_artifact_entry_to_dict,
    archive_manifest_config_to_dict,
    archive_manifest_data_quality_to_dict,
    archive_manifest_safety_flags_to_dict,
    archive_manifest_summary_to_dict,
    atomic_write_json_research_archive_manifest,
    atomic_write_markdown_research_archive_manifest,
    research_archive_manifest_to_dict,
    research_archive_manifest_to_markdown,
    write_research_archive_manifest,
)
from hunter.research_archive_manifest.models import (
    ARCHIVE_BLOCKING_REASON_CODES,
    ARCHIVE_FAMILY_INFO,
    ARCHIVE_MANIFEST_VERSION,
    ARCHIVE_REASON_CODES,
    FORBIDDEN_ARCHIVE_MANIFEST_TERMS,
    ArchiveArtifactEntry,
    ArchiveArtifactFamily,
    ArchiveManifestConfig,
    ArchiveManifestDataQuality,
    ArchiveManifestSafetyFlags,
    ArchiveManifestState,
    ArchiveManifestSummary,
    ResearchArchiveManifest,
)

__all__ = [
    "ARCHIVE_BLOCKING_REASON_CODES",
    "ARCHIVE_FAMILY_INFO",
    "ARCHIVE_MANIFEST_VERSION",
    "ARCHIVE_REASON_CODES",
    "DEFAULT_ARCHIVE_MANIFEST_JSON_PATH",
    "DEFAULT_ARCHIVE_MANIFEST_MARKDOWN_PATH",
    "FORBIDDEN_ARCHIVE_MANIFEST_TERMS",
    "ArchiveArtifactEntry",
    "ArchiveArtifactFamily",
    "ArchiveManifestConfig",
    "ArchiveManifestDataQuality",
    "ArchiveManifestSafetyFlags",
    "ArchiveManifestState",
    "ArchiveManifestSummary",
    "ResearchArchiveManifest",
    "archive_artifact_entry_to_dict",
    "archive_manifest_config_to_dict",
    "archive_manifest_data_quality_to_dict",
    "archive_manifest_safety_flags_to_dict",
    "archive_manifest_summary_to_dict",
    "atomic_write_json_research_archive_manifest",
    "atomic_write_markdown_research_archive_manifest",
    "build_archive_artifact_entry",
    "build_archive_manifest_data_quality",
    "build_archive_manifest_safety_flags",
    "build_archive_manifest_summary",
    "build_research_archive_manifest",
    "has_unsafe_archive_manifest_content",
    "research_archive_manifest_to_dict",
    "research_archive_manifest_to_markdown",
    "write_research_archive_manifest",
]
