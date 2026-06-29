"""Public API for hunter.research_release_notes package.

MVP-20 — Local Research Release Notes / Audit Change Summary.

The research release notes / audit change summary is a human-audit /
contractor-handoff artifact only. It is not release approval, not deployment
approval, not a trading signal, not trade approval, not execution readiness,
not strategy readiness, not transaction permission, and must not be consumed by
execution, strategy, Freqtrade shell, order, exchange, or any MVP execution
path.
"""

from __future__ import annotations

from hunter.research_release_notes.engine import (
    build_release_notes_change_item,
    build_release_notes_data_quality,
    build_release_notes_safety_flags,
    build_release_notes_section,
    build_release_notes_summary,
    build_research_release_notes,
    has_unsafe_release_notes_content,
)
from hunter.research_release_notes.models import (
    FORBIDDEN_RELEASE_NOTES_TERMS,
    RELEASE_NOTES_ARTIFACT_INFO,
    RELEASE_NOTES_BLOCKING_REASON_CODES,
    RELEASE_NOTES_REASON_CODES,
    RELEASE_NOTES_VERSION,
    ReleaseNotesChangeItem,
    ReleaseNotesChangeSeverity,
    ReleaseNotesConfig,
    ReleaseNotesDataQuality,
    ReleaseNotesKind,
    ReleaseNotesSafetyFlags,
    ReleaseNotesSection,
    ReleaseNotesSectionKind,
    ReleaseNotesState,
    ReleaseNotesSummary,
    ResearchReleaseNotes,
)
from hunter.research_release_notes.writer import (
    DEFAULT_RESEARCH_RELEASE_NOTES_JSON_PATH,
    DEFAULT_RESEARCH_RELEASE_NOTES_MARKDOWN_PATH,
    atomic_write_json_research_release_notes,
    atomic_write_markdown_research_release_notes,
    release_notes_change_item_to_dict,
    release_notes_config_to_dict,
    release_notes_data_quality_to_dict,
    release_notes_section_to_dict,
    release_notes_safety_flags_to_dict,
    release_notes_summary_to_dict,
    research_release_notes_to_dict,
    research_release_notes_to_markdown,
    write_research_release_notes,
)

__all__ = [
    "DEFAULT_RESEARCH_RELEASE_NOTES_JSON_PATH",
    "DEFAULT_RESEARCH_RELEASE_NOTES_MARKDOWN_PATH",
    "FORBIDDEN_RELEASE_NOTES_TERMS",
    "RELEASE_NOTES_ARTIFACT_INFO",
    "RELEASE_NOTES_BLOCKING_REASON_CODES",
    "RELEASE_NOTES_REASON_CODES",
    "RELEASE_NOTES_VERSION",
    "ReleaseNotesChangeItem",
    "ReleaseNotesChangeSeverity",
    "ReleaseNotesConfig",
    "ReleaseNotesDataQuality",
    "ReleaseNotesKind",
    "ReleaseNotesSafetyFlags",
    "ReleaseNotesSection",
    "ReleaseNotesSectionKind",
    "ReleaseNotesState",
    "ReleaseNotesSummary",
    "ResearchReleaseNotes",
    "atomic_write_json_research_release_notes",
    "atomic_write_markdown_research_release_notes",
    "build_release_notes_change_item",
    "build_release_notes_data_quality",
    "build_release_notes_safety_flags",
    "build_release_notes_section",
    "build_release_notes_summary",
    "build_research_release_notes",
    "has_unsafe_release_notes_content",
    "release_notes_change_item_to_dict",
    "release_notes_config_to_dict",
    "release_notes_data_quality_to_dict",
    "release_notes_section_to_dict",
    "release_notes_safety_flags_to_dict",
    "release_notes_summary_to_dict",
    "research_release_notes_to_dict",
    "research_release_notes_to_markdown",
    "write_research_release_notes",
]
