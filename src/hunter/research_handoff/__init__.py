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
from hunter.research_handoff.writer import (
    DEFAULT_HANDOFF_JSON_PATH,
    DEFAULT_HANDOFF_MARKDOWN_PATH,
    atomic_write_json_research_handoff_packet,
    atomic_write_markdown_research_handoff_packet,
    handoff_config_to_dict,
    handoff_data_quality_to_dict,
    handoff_safety_flags_to_dict,
    handoff_section_to_dict,
    handoff_summary_to_dict,
    research_handoff_packet_to_dict,
    research_handoff_packet_to_markdown,
    write_research_handoff_packet,
)

__all__ = [
    "DEFAULT_HANDOFF_JSON_PATH",
    "DEFAULT_HANDOFF_MARKDOWN_PATH",
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
    "atomic_write_json_research_handoff_packet",
    "atomic_write_markdown_research_handoff_packet",
    "build_handoff_data_quality",
    "build_handoff_safety_flags",
    "build_handoff_section",
    "build_handoff_summary",
    "build_research_handoff_packet",
    "handoff_config_to_dict",
    "handoff_data_quality_to_dict",
    "handoff_safety_flags_to_dict",
    "handoff_section_to_dict",
    "handoff_summary_to_dict",
    "has_unsafe_handoff_content",
    "research_handoff_packet_to_dict",
    "research_handoff_packet_to_markdown",
    "write_research_handoff_packet",
]
