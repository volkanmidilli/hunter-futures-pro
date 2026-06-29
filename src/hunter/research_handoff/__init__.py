"""Public API for hunter.research_handoff package.

MVP-18 — Local Research Handoff Packet.

The research handoff packet is a human-audit artifact only. It is not a trading
signal, not trade approval, not execution readiness, not strategy readiness,
not release/deployment approval, not transaction permission, and must not be
consumed by execution, strategy, Freqtrade shell, order, exchange, or any MVP
execution path.
"""

from __future__ import annotations

from hunter.research_handoff.engine import (
    build_handoff_data_quality,
    build_handoff_safety_flags,
    build_handoff_section,
    build_handoff_summary,
    build_research_handoff_packet,
    has_unsafe_handoff_content,
)
from hunter.research_handoff.models import (
    FORBIDDEN_HANDOFF_TERMS,
    HANDOFF_BLOCKING_REASON_CODES,
    HANDOFF_REASON_CODES,
    HANDOFF_VERSION,
    HandoffConfig,
    HandoffDataQuality,
    HandoffPacketKind,
    HandoffSafetyFlags,
    HandoffSection,
    HandoffState,
    HandoffSummary,
    ResearchHandoffPacket,
)

__all__ = [
    "FORBIDDEN_HANDOFF_TERMS",
    "HANDOFF_BLOCKING_REASON_CODES",
    "HANDOFF_REASON_CODES",
    "HANDOFF_VERSION",
    "HandoffConfig",
    "HandoffDataQuality",
    "HandoffPacketKind",
    "HandoffSafetyFlags",
    "HandoffSection",
    "HandoffState",
    "HandoffSummary",
    "ResearchHandoffPacket",
    "build_handoff_data_quality",
    "build_handoff_safety_flags",
    "build_handoff_section",
    "build_handoff_summary",
    "build_research_handoff_packet",
    "has_unsafe_handoff_content",
]
