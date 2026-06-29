"""Public API for hunter.research_digest package.

MVP-16 — Local Research Digest / Executive Summary.

The research digest is a human-audit artifact only. It is not a trading signal,
not a trade approval, and must not be consumed by execution, strategy, Freqtrade
shell, order, exchange, or any MVP execution path.
"""

from __future__ import annotations

from hunter.research_digest.engine import (
    build_digest_data_quality,
    build_digest_safety_flags,
    build_digest_section,
    build_digest_summary,
    build_research_digest,
    has_unsafe_digest_content,
)
from hunter.research_digest.models import (
    DIGEST_BLOCKING_REASON_CODES,
    DIGEST_REASON_CODES,
    DIGEST_VERSION,
    FORBIDDEN_DIGEST_TERMS,
    DigestConfig,
    DigestDataQuality,
    DigestSafetyFlags,
    DigestSection,
    DigestSectionKind,
    DigestState,
    DigestSummary,
    ResearchDigest,
)
from hunter.research_digest.writer import (
    DEFAULT_DIGEST_JSON_PATH,
    DEFAULT_DIGEST_MARKDOWN_PATH,
    atomic_write_json_research_digest,
    atomic_write_markdown_research_digest,
    digest_config_to_dict,
    digest_data_quality_to_dict,
    digest_safety_flags_to_dict,
    digest_section_to_dict,
    digest_summary_to_dict,
    research_digest_to_dict,
    research_digest_to_markdown,
    write_research_digest,
)

__all__ = [
    "DEFAULT_DIGEST_JSON_PATH",
    "DEFAULT_DIGEST_MARKDOWN_PATH",
    "DIGEST_BLOCKING_REASON_CODES",
    "DIGEST_REASON_CODES",
    "DIGEST_VERSION",
    "FORBIDDEN_DIGEST_TERMS",
    "DigestConfig",
    "DigestDataQuality",
    "DigestSafetyFlags",
    "DigestSection",
    "DigestSectionKind",
    "DigestState",
    "DigestSummary",
    "ResearchDigest",
    "atomic_write_json_research_digest",
    "atomic_write_markdown_research_digest",
    "build_digest_data_quality",
    "build_digest_safety_flags",
    "build_digest_section",
    "build_digest_summary",
    "build_research_digest",
    "digest_config_to_dict",
    "digest_data_quality_to_dict",
    "digest_safety_flags_to_dict",
    "digest_section_to_dict",
    "digest_summary_to_dict",
    "has_unsafe_digest_content",
    "research_digest_to_dict",
    "research_digest_to_markdown",
    "write_research_digest",
]
