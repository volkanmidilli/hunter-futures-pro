"""Public API for the Research Audit Remediation Handoff Packet (MVP-50).

The handoff packet consumes a caller-provided MVP-49 `RemediationBridgeReport`
(or a sequence of `RemediationBacklogItem` summaries) and produces a
deterministic human-review handoff packet with grouped items, summary counts,
and metadata. It is pure, local, deterministic, and audit-only.
"""

from hunter.research_audit_remediation_handoff.engine import (
    build_research_audit_remediation_handoff_packet,
)
from hunter.research_audit_remediation_handoff.models import (
    HandoffPacket,
    HandoffPacketConfig,
    HandoffPacketDataQuality,
    HandoffPacketError,
    HandoffPacketGroup,
    HandoffPacketSafetyFlags,
)

__all__ = [
    "HandoffPacket",
    "HandoffPacketConfig",
    "HandoffPacketDataQuality",
    "HandoffPacketError",
    "HandoffPacketGroup",
    "HandoffPacketSafetyFlags",
    "build_research_audit_remediation_handoff_packet",
]
