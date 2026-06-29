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

__all__ = [
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
    "build_digest_data_quality",
    "build_digest_safety_flags",
    "build_digest_section",
    "build_digest_summary",
    "build_research_digest",
    "has_unsafe_digest_content",
]
