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
    RELEASE_NOTES_BLOCKING_REASON_CODES,
    RELEASE_NOTES_REASON_CODES,
    RELEASE_NOTES_VERSION,
    RELEASE_NOTES_ARTIFACT_INFO,
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

__all__ = [
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
    "build_release_notes_change_item",
    "build_release_notes_data_quality",
    "build_release_notes_safety_flags",
    "build_release_notes_section",
    "build_release_notes_summary",
    "build_research_release_notes",
    "has_unsafe_release_notes_content",
]
