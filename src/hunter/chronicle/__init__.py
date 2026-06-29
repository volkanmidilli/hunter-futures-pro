"""Public API for hunter.chronicle package.

Local Research Chronicle / Audit Timeline for MVP-15.
"""

from hunter.chronicle.engine import (
    build_chronicle_data_quality,
    build_chronicle_entry_from_bundle,
    build_chronicle_entry_from_index,
    build_chronicle_entry_from_observation,
    build_chronicle_entry_from_review,
    build_chronicle_entry_from_search,
    build_chronicle_summary,
    build_research_chronicle,
    has_unsafe_chronicle_content,
)
from hunter.chronicle.models import (
    CHRONICLE_BLOCKING_REASON_CODES,
    CHRONICLE_REASON_CODES,
    CHRONICLE_TRACKING_REASON_CODES,
    CHRONICLE_VERSION,
    ArtifactType,
    ChronicleDataQuality,
    ChronicleEntry,
    ChronicleSafetyFlags,
    ChronicleSummary,
    FORBIDDEN_CHRONICLE_TERMS,
    ResearchChronicle,
)
from hunter.chronicle.writer import (
    atomic_write_json_research_chronicle,
    atomic_write_markdown_research_chronicle,
    chronicle_data_quality_to_dict,
    chronicle_entry_to_dict,
    chronicle_safety_flags_to_dict,
    chronicle_summary_to_dict,
    research_chronicle_to_dict,
    research_chronicle_to_markdown,
    write_research_chronicle,
)

__all__ = [
    # Models
    "ArtifactType",
    "ChronicleEntry",
    "ChronicleSummary",
    "ChronicleDataQuality",
    "ChronicleSafetyFlags",
    "ResearchChronicle",
    # Constants
    "CHRONICLE_VERSION",
    "CHRONICLE_BLOCKING_REASON_CODES",
    "CHRONICLE_TRACKING_REASON_CODES",
    "CHRONICLE_REASON_CODES",
    "FORBIDDEN_CHRONICLE_TERMS",
    # Engine
    "has_unsafe_chronicle_content",
    "build_chronicle_entry_from_observation",
    "build_chronicle_entry_from_review",
    "build_chronicle_entry_from_index",
    "build_chronicle_entry_from_search",
    "build_chronicle_entry_from_bundle",
    "build_chronicle_summary",
    "build_chronicle_data_quality",
    "build_research_chronicle",
    # Writer
    "research_chronicle_to_dict",
    "research_chronicle_to_markdown",
    "chronicle_entry_to_dict",
    "chronicle_summary_to_dict",
    "chronicle_data_quality_to_dict",
    "chronicle_safety_flags_to_dict",
    "atomic_write_json_research_chronicle",
    "atomic_write_markdown_research_chronicle",
    "write_research_chronicle",
]
