"""Frozen dataclasses for hunter.research_handoff package.

MVP-18 — Local Research Handoff Packet.

All dataclasses are frozen. Validation runs in __post_init__.
File references and metadata strings are local strings only and are never
traversed, opened, followed, validated, or executed.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Any

from hunter.research_quality_gate.models import FORBIDDEN_QUALITY_GATE_TERMS


HANDOFF_VERSION = "1.0"


class HandoffState(Enum):
    """Per-section and overall handoff packet state."""

    READY = "ready"
    WARN = "warn"
    BLOCK = "block"
    UNKNOWN = "unknown"


class HandoffPacketKind(Enum):
    """Deterministic handoff section ordering kind."""

    OBSERVATION = "observation"
    REVIEW = "review"
    INDEX = "index"
    SEARCH = "search"
    BUNDLE = "bundle"
    CHRONICLE = "chronicle"
    DIGEST = "digest"
    QUALITY_GATE = "quality_gate"


HANDOFF_REASON_CODES = (
    "EMPTY_PACKET",
    "INVALID_CONFIG",
    "UNSAFE_CONFIG",
    "MISSING_OBSERVATION",
    "MISSING_REVIEW",
    "MISSING_INDEX",
    "MISSING_SEARCH",
    "MISSING_BUNDLE",
    "MISSING_CHRONICLE",
    "MISSING_DIGEST",
    "MISSING_QUALITY_GATE",
    "BLOCKED_OBSERVATION",
    "BLOCKED_REVIEW",
    "BLOCKED_INDEX",
    "BLOCKED_SEARCH",
    "BLOCKED_BUNDLE",
    "BLOCKED_CHRONICLE",
    "BLOCKED_DIGEST",
    "BLOCKED_QUALITY_GATE",
    "UNKNOWN_OBSERVATION",
    "UNKNOWN_REVIEW",
    "UNKNOWN_INDEX",
    "UNKNOWN_SEARCH",
    "UNKNOWN_BUNDLE",
    "UNKNOWN_CHRONICLE",
    "UNKNOWN_DIGEST",
    "UNKNOWN_QUALITY_GATE",
    "UNSAFE_ARTIFACT_FLAGS",
    "UNRESOLVED_BLOCKERS",
    "STALE_ARTIFACT",
    "UNSAFE_PACKET_CONTENT",
    "HANDOFF_ERROR",
)

HANDOFF_BLOCKING_REASON_CODES = tuple(
    rc for rc in HANDOFF_REASON_CODES if rc not in ("EMPTY_PACKET", "STALE_ARTIFACT")
)

# Superset of FORBIDDEN_QUALITY_GATE_TERMS from SPEC-018.
FORBIDDEN_HANDOFF_TERMS = FORBIDDEN_QUALITY_GATE_TERMS


_VALID_OUTPUT_FORMATS = ("json", "markdown", "both")
_VALID_HANDOFF_STATES = ("READY", "WARN", "BLOCK", "UNKNOWN")
_VALID_QUALITY_GATE_VERDICTS = ("PASS", "WARN", "BLOCK", "UNKNOWN")


def _has_unsafe_handoff_content(text: str) -> bool:
    """Case-insensitive check for forbidden terms.

    Does not open, traverse, validate, follow, or execute file references.
    """
    lower = text.lower()
    return any(term in lower for term in FORBIDDEN_HANDOFF_TERMS)


def _check_unsafe_mapping(mapping: Mapping[str, Any]) -> bool:
    """Return True if any key or string value contains forbidden terms."""
    for key, value in mapping.items():
        if isinstance(key, str) and _has_unsafe_handoff_content(key):
            return True
        if isinstance(value, str) and _has_unsafe_handoff_content(value):
            return True
        if isinstance(value, (tuple, list)):
            for item in value:
                if isinstance(item, str) and _has_unsafe_handoff_content(item):
                    return True
        if isinstance(value, Mapping):
            if _check_unsafe_mapping(value):
                return True
    return False


def _validate_no_unsafe_content(
    text: str | None,
    metadata: Mapping[str, Any] | None,
) -> None:
    """Raise ValueError if text or metadata contain forbidden terms."""
    if text is not None and _has_unsafe_handoff_content(text):
        raise ValueError("UNSAFE_PACKET_CONTENT")
    if metadata is not None and _check_unsafe_mapping(metadata):
        raise ValueError("UNSAFE_PACKET_CONTENT")


def _coerce_tuple_of_str(value: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    """Coerce a tuple or list of items into a tuple of non-empty strings."""
    if isinstance(value, tuple):
        return tuple(str(x) for x in value if x)
    if isinstance(value, list):
        return tuple(str(x) for x in value if x)
    raise ValueError("reason_codes must be a tuple or list of strings")


def _coerce_tuple_of_section_kinds(
    value: tuple[HandoffPacketKind, ...] | list[HandoffPacketKind],
) -> tuple[HandoffPacketKind, ...]:
    """Coerce a tuple or list into a tuple of HandoffPacketKind enum instances."""
    if isinstance(value, (tuple, list)):
        result = []
        for item in value:
            if not isinstance(item, HandoffPacketKind):
                raise ValueError(
                    "required_sections must contain HandoffPacketKind enum instances"
                )
            result.append(item)
        return tuple(result)
    raise ValueError("required_sections must be a tuple or list of HandoffPacketKind")


def _coerce_mapping(value: Mapping[str, Any] | dict[str, Any] | None) -> Mapping[str, Any]:
    """Coerce a mapping into an immutable MappingProxyType."""
    if value is None:
        return MappingProxyType({})
    if isinstance(value, Mapping):
        return MappingProxyType(dict(value))
    raise ValueError("metadata must be a mapping")


@dataclass(frozen=True)
class HandoffConfig:
    """Configuration for handoff packet generation.

    Unsafe flags must remain False. dry_run must remain True.
    """

    version: str = "1.0"
    generated_at: datetime | None = None
    output_format: str = "both"
    dry_run: bool = True
    live_trading_enabled: bool = False
    real_orders_enabled: bool = False
    leverage_enabled: bool = False
    shorting_enabled: bool = False
    block_on_unknown: bool = True
    required_sections: tuple[HandoffPacketKind, ...] = (
        HandoffPacketKind.OBSERVATION,
        HandoffPacketKind.REVIEW,
        HandoffPacketKind.INDEX,
        HandoffPacketKind.SEARCH,
        HandoffPacketKind.BUNDLE,
        HandoffPacketKind.CHRONICLE,
        HandoffPacketKind.DIGEST,
        HandoffPacketKind.QUALITY_GATE,
    )
    max_staleness_minutes: int = 60
    include_handoff_notes: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.version, str) or not self.version.strip():
            raise ValueError("version must be a non-empty string")
        if self.output_format not in _VALID_OUTPUT_FORMATS:
            raise ValueError(
                f"output_format must be one of {_VALID_OUTPUT_FORMATS}"
            )
        if not isinstance(self.dry_run, bool) or not self.dry_run:
            raise ValueError("dry_run must be True")
        for unsafe_attr in (
            "live_trading_enabled",
            "real_orders_enabled",
            "leverage_enabled",
            "shorting_enabled",
        ):
            if getattr(self, unsafe_attr):
                raise ValueError(f"{unsafe_attr} must be False")
        if not isinstance(self.block_on_unknown, bool):
            raise ValueError("block_on_unknown must be a bool")
        object.__setattr__(
            self,
            "required_sections",
            _coerce_tuple_of_section_kinds(self.required_sections),
        )
        if (
            not isinstance(self.max_staleness_minutes, int)
            or self.max_staleness_minutes < 1
        ):
            raise ValueError("max_staleness_minutes must be a positive integer")


@dataclass(frozen=True)
class HandoffSafetyFlags:
    """Safety flags for handoff packet output.

    Unsafe flags default to False. Safe output flags default to True.
    """

    # Runtime safety flags
    dry_run: bool = True
    live_trading_enabled: bool = False
    real_orders_enabled: bool = False
    leverage_enabled: bool = False
    shorting_enabled: bool = False

    # Output safety flags
    handoff_output_is_human_audit_only: bool = True
    handoff_output_not_trading_signal: bool = True
    handoff_output_not_trade_approval: bool = True
    handoff_output_not_execution_readiness: bool = True
    handoff_output_not_strategy_readiness: bool = True
    handoff_output_not_for_execution: bool = True
    handoff_output_not_for_strategy: bool = True
    handoff_output_not_for_freqtrade: bool = True
    handoff_output_not_for_order: bool = True
    handoff_output_not_for_exchange: bool = True

    # Feedback safety flags
    handoff_feedback_into_execution: bool = False
    cross_layer_feedback_into_execution: bool = False

    # Advisory flags
    file_refs_not_traversed: bool = True

    def __post_init__(self) -> None:
        unsafe_flags = (
            self.live_trading_enabled,
            self.real_orders_enabled,
            self.leverage_enabled,
            self.shorting_enabled,
            self.handoff_feedback_into_execution,
            self.cross_layer_feedback_into_execution,
        )
        if any(unsafe_flags):
            raise ValueError("unsafe handoff safety flags are enabled")
        if not self.dry_run:
            raise ValueError("dry_run must be True")
        safe_flags = (
            self.handoff_output_is_human_audit_only,
            self.handoff_output_not_trading_signal,
            self.handoff_output_not_trade_approval,
            self.handoff_output_not_execution_readiness,
            self.handoff_output_not_strategy_readiness,
            self.handoff_output_not_for_execution,
            self.handoff_output_not_for_strategy,
            self.handoff_output_not_for_freqtrade,
            self.handoff_output_not_for_order,
            self.handoff_output_not_for_exchange,
            self.file_refs_not_traversed,
        )
        if not all(safe_flags):
            raise ValueError("safe handoff output flags must be True")


@dataclass(frozen=True)
class HandoffSection:
    """One handoff packet section per artifact category."""

    section_kind: HandoffPacketKind
    title: str = ""
    state: str = "UNKNOWN"
    summary_text: str = ""
    local_reference: str = ""
    reason_codes: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.section_kind, HandoffPacketKind):
            raise ValueError("section_kind must be a HandoffPacketKind enum instance")
        state_upper = self.state.upper()
        if state_upper not in _VALID_HANDOFF_STATES:
            raise ValueError(
                f"state must be one of {_VALID_HANDOFF_STATES}, got {self.state!r}"
            )
        object.__setattr__(self, "state", state_upper)
        object.__setattr__(self, "reason_codes", _coerce_tuple_of_str(self.reason_codes))
        object.__setattr__(self, "metadata", _coerce_mapping(self.metadata))
        _validate_no_unsafe_content(self.summary_text, self.metadata)
        _validate_no_unsafe_content(self.local_reference, None)


@dataclass(frozen=True)
class HandoffSummary:
    """Top-level aggregated handoff packet summary."""

    total_sections: int = 0
    ready_sections: int = 0
    warn_sections: int = 0
    block_sections: int = 0
    unknown_sections: int = 0
    quality_gate_verdict: str = "UNKNOWN"
    handoff_state: str = "UNKNOWN"
    reason_code_counts: Mapping[str, int] = field(default_factory=dict)
    handoff_notes: str = ""

    def __post_init__(self) -> None:
        for int_attr in (
            "total_sections",
            "ready_sections",
            "warn_sections",
            "block_sections",
            "unknown_sections",
        ):
            value = getattr(self, int_attr)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{int_attr} must be a non-negative integer")
        if self.total_sections > 0:
            counted = (
                self.ready_sections
                + self.warn_sections
                + self.block_sections
                + self.unknown_sections
            )
            if counted != self.total_sections:
                raise ValueError(
                    "ready_sections + warn_sections + block_sections + unknown_sections "
                    "must equal total_sections"
                )
        verdict_upper = self.quality_gate_verdict.upper()
        if verdict_upper not in _VALID_QUALITY_GATE_VERDICTS:
            raise ValueError(
                f"quality_gate_verdict must be one of {_VALID_QUALITY_GATE_VERDICTS}, "
                f"got {self.quality_gate_verdict!r}"
            )
        object.__setattr__(self, "quality_gate_verdict", verdict_upper)
        state_upper = self.handoff_state.upper()
        if state_upper not in _VALID_HANDOFF_STATES:
            raise ValueError(
                f"handoff_state must be one of {_VALID_HANDOFF_STATES}, "
                f"got {self.handoff_state!r}"
            )
        object.__setattr__(self, "handoff_state", state_upper)
        if not isinstance(self.reason_code_counts, Mapping):
            raise ValueError("reason_code_counts must be a mapping")
        if not isinstance(self.handoff_notes, str):
            raise ValueError("handoff_notes must be a string")
        _validate_no_unsafe_content(self.handoff_notes, None)


@dataclass(frozen=True)
class HandoffDataQuality:
    """Completeness and blocker metrics."""

    completeness_pct: float = 0.0
    ready_pct: float = 0.0
    missing_count: int = 0
    stale_count: int = 0
    blocked_count: int = 0
    unknown_count: int = 0
    total_sections: int = 0
    reason: str = ""

    def __post_init__(self) -> None:
        for float_attr in ("completeness_pct", "ready_pct"):
            value = getattr(self, float_attr)
            if not isinstance(value, (int, float)):
                raise ValueError(f"{float_attr} must be a number")
            if not (0.0 <= value <= 100.0):
                raise ValueError(f"{float_attr} must be between 0.0 and 100.0")
        for int_attr in (
            "missing_count",
            "stale_count",
            "blocked_count",
            "unknown_count",
            "total_sections",
        ):
            value = getattr(self, int_attr)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{int_attr} must be a non-negative integer")
        if not isinstance(self.reason, str):
            raise ValueError("reason must be a string")
        _validate_no_unsafe_content(self.reason, None)


@dataclass(frozen=True)
class ResearchHandoffPacket:
    """Full handoff packet container."""

    packet_id: str
    generated_at: datetime
    version: str = HANDOFF_VERSION
    handoff_state: HandoffState = field(default_factory=lambda: HandoffState.UNKNOWN)
    sections: tuple[HandoffSection, ...] = ()
    summary: HandoffSummary = field(default_factory=HandoffSummary)
    data_quality: HandoffDataQuality = field(default_factory=HandoffDataQuality)
    safety_flags: HandoffSafetyFlags = field(default_factory=HandoffSafetyFlags)
    config: HandoffConfig = field(default_factory=HandoffConfig)
    reason_codes: tuple[str, ...] = ()
    handoff_notes: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.packet_id, str) or not self.packet_id.strip():
            raise ValueError("packet_id must be a non-empty string")
        if not isinstance(self.version, str) or not self.version.strip():
            raise ValueError("version must be a non-empty string")
        if not isinstance(self.generated_at, datetime) or self.generated_at.tzinfo is None:
            raise ValueError("generated_at must be a timezone-aware datetime")
        if not isinstance(self.handoff_state, HandoffState):
            raise ValueError("handoff_state must be a HandoffState enum instance")
        if not isinstance(self.sections, tuple):
            raise ValueError("sections must be a tuple")
        for section in self.sections:
            if not isinstance(section, HandoffSection):
                raise ValueError("sections must contain HandoffSection instances")
        object.__setattr__(self, "reason_codes", _coerce_tuple_of_str(self.reason_codes))
        if not isinstance(self.handoff_notes, str):
            raise ValueError("handoff_notes must be a string")
        _validate_no_unsafe_content(self.handoff_notes, None)

    @classmethod
    def blocked(cls, reason: str, generated_at: datetime | None = None) -> "ResearchHandoffPacket":
        """Factory for a blocked handoff packet with safe defaults."""
        if generated_at is None:
            generated_at = datetime.now().astimezone().replace(microsecond=0)
        if generated_at.tzinfo is None:
            raise ValueError("generated_at must be timezone-aware")
        return cls(
            packet_id="blocked",
            generated_at=generated_at,
            handoff_state=HandoffState.BLOCK,
            sections=(),
            summary=HandoffSummary(
                total_sections=0,
                block_sections=1,
                handoff_state="BLOCK",
                handoff_notes=f"Handoff packet blocked: {reason}. "
                "This is not trade approval, not execution readiness, "
                "not strategy readiness, not release approval, "
                "and not transaction permission.",
            ),
            data_quality=HandoffDataQuality(
                completeness_pct=0.0,
                blocked_count=1,
                reason=reason,
            ),
            safety_flags=HandoffSafetyFlags(),
            reason_codes=(reason,),
        )
