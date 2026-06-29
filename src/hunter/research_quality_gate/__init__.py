"""Public API for hunter.research_quality_gate package.

MVP-17 — Local Research Quality Gate / Audit Readiness.

The research quality gate is a human-audit artifact only. It is not a trading
signal, not trade approval, not execution readiness, not strategy readiness,
and must not be consumed by execution, strategy, Freqtrade shell, order,
exchange, or any MVP execution path.
"""

from __future__ import annotations

from hunter.research_quality_gate.engine import (
    build_quality_gate_check,
    build_quality_gate_data_quality,
    build_quality_gate_safety_flags,
    build_quality_gate_summary,
    build_research_quality_gate,
    has_unsafe_quality_gate_content,
)
from hunter.research_quality_gate.models import (
    FORBIDDEN_QUALITY_GATE_TERMS,
    QUALITY_GATE_BLOCKING_REASON_CODES,
    QUALITY_GATE_REASON_CODES,
    QUALITY_GATE_VERSION,
    QualityGateCheck,
    QualityGateCheckKind,
    QualityGateConfig,
    QualityGateDataQuality,
    QualityGateSafetyFlags,
    QualityGateState,
    QualityGateSummary,
    QualityGateVerdict,
    ResearchQualityGate,
)

__all__ = [
    "FORBIDDEN_QUALITY_GATE_TERMS",
    "QUALITY_GATE_BLOCKING_REASON_CODES",
    "QUALITY_GATE_REASON_CODES",
    "QUALITY_GATE_VERSION",
    "QualityGateCheck",
    "QualityGateCheckKind",
    "QualityGateConfig",
    "QualityGateDataQuality",
    "QualityGateSafetyFlags",
    "QualityGateState",
    "QualityGateSummary",
    "QualityGateVerdict",
    "ResearchQualityGate",
    "build_quality_gate_check",
    "build_quality_gate_data_quality",
    "build_quality_gate_safety_flags",
    "build_quality_gate_summary",
    "build_research_quality_gate",
    "has_unsafe_quality_gate_content",
]
