"""Frozen dataclasses for hunter.research_digest package.

MVP-16 — Local Research Digest / Executive Summary.

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


DIGEST_VERSION = "1.0"


class DigestState(Enum):
    """Top-level and section-level digest state."""

    DISABLED = "disabled"
    READY = "ready"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class DigestSectionKind(Enum):
    """Deterministic section ordering kind."""

    OBSERVATION = "observation"
    REVIEW = "review"
    INDEX = "index"
    SEARCH = "search"
    BUNDLE = "bundle"
    CHRONICLE = "chronicle"


DIGEST_REASON_CODES = (
    "EMPTY_DIGEST",
    "INVALID_CONFIG",
    "UNSAFE_CONFIG",
    "MISSING_OBSERVATION",
    "MISSING_REVIEW",
    "MISSING_INDEX",
    "MISSING_SEARCH",
    "MISSING_BUNDLE",
    "MISSING_CHRONICLE",
    "INVALID_OBSERVATION",
    "INVALID_REVIEW",
    "INVALID_INDEX",
    "INVALID_SEARCH",
    "INVALID_BUNDLE",
    "INVALID_CHRONICLE",
    "UNSAFE_DIGEST_CONTENT",
    "DIGEST_ERROR",
)

DIGEST_BLOCKING_REASON_CODES = tuple(
    rc for rc in DIGEST_REASON_CODES if rc not in ("EMPTY_DIGEST",)
)

# Superset of FORBIDDEN_CHRONICLE_TERMS from SPEC-016.
FORBIDDEN_DIGEST_TERMS = frozenset({
    # Credential / secret terms (from SPEC-016)
    "api_key",
    "secret",
    "exchange_credentials",
    "executable_instructions",
    "private_key",
    "password",
    "token",
    "auth",
    # Trading execution terms (from SPEC-016)
    "enter_long",
    "enter_short",
    "exit_long",
    "exit_short",
    "order",
    "position",
    "leverage",
    "margin",
    "liquidation",
    # Additional trading terms (digest-specific)
    "live_trade",
    "real_order",
    "market_order",
    "limit_order",
    "position_size",
})

_VALID_OUTPUT_FORMATS = ("json", "markdown", "both")
_VALID_SECTION_KIND_VALUES = tuple(k.value for k in DigestSectionKind)
_VALID_SECTION_STATES = ("DISABLED", "READY", "BLOCKED", "UNKNOWN")


def _has_unsafe_digest_content(text: str) -> bool:
    """Case-insensitive check for forbidden terms.

    Does not open, traverse, validate, follow, or execute file references.
    """
    lower = text.lower()
    for term in FORBIDDEN_DIGEST_TERMS:
        if term in lower:
            return True
    return False


def _check_unsafe_mapping(mapping: Mapping[str, Any]) -> bool:
    """Return True if any key or string value contains forbidden terms."""
    for key, value in mapping.items():
        if isinstance(key, str) and _has_unsafe_digest_content(key):
            return True
        if isinstance(value, str) and _has_unsafe_digest_content(value):
            return True
        if isinstance(value, (tuple, list)):
            for item in value:
                if isinstance(item, str) and _has_unsafe_digest_content(item):
                    return True
        if isinstance(value, Mapping):
            if _check_unsafe_mapping(value):
                return True
    return False


def _validate_no_unsafe_content(
    notes: str | None,
    metadata: Mapping[str, Any] | None,
) -> None:
    """Raise ValueError if notes or metadata contain forbidden terms."""
    if notes is not None and _has_unsafe_digest_content(notes):
        raise ValueError("UNSAFE_DIGEST_CONTENT")
    if metadata is not None and _check_unsafe_mapping(metadata):
        raise ValueError("UNSAFE_DIGEST_CONTENT")


def _coerce_tuple_of_str(value: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    """Coerce a tuple or list of items into a tuple of non-empty strings."""
    if isinstance(value, tuple):
        return tuple(str(x) for x in value if x)
    if isinstance(value, list):
        return tuple(str(x) for x in value if x)
    raise ValueError("reason_codes must be a tuple or list of strings")


def _coerce_mapping(value: Mapping[str, Any] | dict[str, Any] | None) -> Mapping[str, Any]:
    """Coerce a mapping into an immutable MappingProxyType."""
    if value is None:
        return MappingProxyType({})
    if isinstance(value, Mapping):
        return MappingProxyType(dict(value))
    raise ValueError("metadata must be a mapping")


@dataclass(frozen=True)
class DigestConfig:
    """Configuration for digest generation.

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
    stale_threshold_minutes: int = 60
    include_next_review_notes: bool = True
    include_safety_flags: bool = True
    include_unresolved_blockers: bool = True
    include_reason_code_summary: bool = True

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
        if not isinstance(self.stale_threshold_minutes, int) or self.stale_threshold_minutes < 1:
            raise ValueError("stale_threshold_minutes must be a positive integer")


@dataclass(frozen=True)
class DigestSafetyFlags:
    """Safety flags for digest output.

    Mirrors the ChronicleSafetyFlags pattern from SPEC-016.
    Unsafe flags default to False. Safe output flags default to True.
    """

    # Runtime safety flags
    dry_run: bool = True
    live_trading_enabled: bool = False
    real_orders_enabled: bool = False
    leverage_enabled: bool = False
    shorting_enabled: bool = False

    # Output safety flags
    digest_output_is_human_audit_only: bool = True
    digest_output_not_trading_signal: bool = True
    digest_output_not_trade_approval: bool = True
    digest_output_not_for_execution: bool = True
    digest_output_not_for_strategy: bool = True
    digest_output_not_for_freqtrade: bool = True
    digest_output_not_for_order: bool = True
    digest_output_not_for_exchange: bool = True

    # Feedback safety flags
    digest_feedback_into_execution: bool = False
    cross_layer_feedback_into_execution: bool = False

    # Advisory flags
    trace_linkage_advisory_only: bool = True
    file_refs_not_traversed: bool = True

    def __post_init__(self) -> None:
        unsafe_flags = (
            self.live_trading_enabled,
            self.real_orders_enabled,
            self.leverage_enabled,
            self.shorting_enabled,
            self.digest_feedback_into_execution,
            self.cross_layer_feedback_into_execution,
        )
        if any(unsafe_flags):
            raise ValueError("unsafe digest safety flags are enabled")
        if not self.dry_run:
            raise ValueError("dry_run must be True")
        safe_flags = (
            self.digest_output_is_human_audit_only,
            self.digest_output_not_trading_signal,
            self.digest_output_not_trade_approval,
            self.digest_output_not_for_execution,
            self.digest_output_not_for_strategy,
            self.digest_output_not_for_freqtrade,
            self.digest_output_not_for_order,
            self.digest_output_not_for_exchange,
            self.trace_linkage_advisory_only,
            self.file_refs_not_traversed,
        )
        if not all(safe_flags):
            raise ValueError("safe digest output flags must be True")


@dataclass(frozen=True)
class DigestSection:
    """One summary section per artifact type."""

    section_kind: DigestSectionKind
    state: str = "UNKNOWN"
    count: int = 0
    blocked_count: int = 0
    ready_count: int = 0
    missing_count: int = 0
    reason_codes: tuple[str, ...] = ()
    blockers_count: int = 0
    unresolved_blocker_reasons: tuple[str, ...] = ()
    notes: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.section_kind, DigestSectionKind):
            raise ValueError("section_kind must be a DigestSectionKind enum instance")
        state_upper = self.state.upper()
        if state_upper not in _VALID_SECTION_STATES:
            raise ValueError(
                f"state must be one of {_VALID_SECTION_STATES}, got {self.state!r}"
            )
        object.__setattr__(self, "state", state_upper)
        for int_attr in ("count", "blocked_count", "ready_count", "missing_count", "blockers_count"):
            value = getattr(self, int_attr)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{int_attr} must be a non-negative integer")
        object.__setattr__(self, "reason_codes", _coerce_tuple_of_str(self.reason_codes))
        object.__setattr__(
            self, "unresolved_blocker_reasons", _coerce_tuple_of_str(self.unresolved_blocker_reasons)
        )
        object.__setattr__(self, "metadata", _coerce_mapping(self.metadata))
        # Unsafe content is checked by engine functions; DigestSection itself
        # only stores validated or intentionally blocked content.


@dataclass(frozen=True)
class DigestSummary:
    """Top-level aggregated digest summary."""

    total_sections: int = 0
    ready_sections: int = 0
    blocked_sections: int = 0
    missing_sections: int = 0
    total_artifacts: int = 0
    total_blockers: int = 0
    unresolved_blockers: int = 0
    reason_code_counts: Mapping[str, int] = field(default_factory=dict)
    cross_layer_ready: bool = False
    next_review_notes: str = ""

    def __post_init__(self) -> None:
        for int_attr in (
            "total_sections",
            "ready_sections",
            "blocked_sections",
            "missing_sections",
            "total_artifacts",
            "total_blockers",
            "unresolved_blockers",
        ):
            value = getattr(self, int_attr)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{int_attr} must be a non-negative integer")
        if self.total_sections > 0 and self.ready_sections + self.blocked_sections > self.total_sections:
            raise ValueError("ready_sections + blocked_sections must be <= total_sections")
        if self.missing_sections > self.total_sections:
            raise ValueError("missing_sections must be <= total_sections")
        if self.unresolved_blockers > self.total_blockers:
            raise ValueError("unresolved_blockers must be <= total_blockers")
        if not isinstance(self.reason_code_counts, Mapping):
            raise ValueError("reason_code_counts must be a mapping")
        if not isinstance(self.cross_layer_ready, bool):
            raise ValueError("cross_layer_ready must be a bool")
        if not isinstance(self.next_review_notes, str):
            raise ValueError("next_review_notes must be a string")
        _validate_no_unsafe_content(self.next_review_notes, None)


@dataclass(frozen=True)
class DigestDataQuality:
    """Completeness and blocker metrics."""

    completeness_pct: float = 0.0
    missing_count: int = 0
    stale_count: int = 0
    invalid_count: int = 0
    blocked_count: int = 0
    total_sections: int = 0
    reason: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.completeness_pct, (int, float)):
            raise ValueError("completeness_pct must be a number")
        if not (0.0 <= self.completeness_pct <= 100.0):
            raise ValueError("completeness_pct must be between 0.0 and 100.0")
        for int_attr in ("missing_count", "stale_count", "invalid_count", "blocked_count", "total_sections"):
            value = getattr(self, int_attr)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{int_attr} must be a non-negative integer")
        if not isinstance(self.reason, str):
            raise ValueError("reason must be a string")
        _validate_no_unsafe_content(self.reason, None)


@dataclass(frozen=True)
class ResearchDigest:
    """Full digest container."""

    digest_id: str
    generated_at: datetime
    version: str = DIGEST_VERSION
    state: DigestState = field(default_factory=lambda: DigestState.UNKNOWN)
    sections: tuple[DigestSection, ...] = ()
    summary: DigestSummary = field(default_factory=DigestSummary)
    data_quality: DigestDataQuality = field(default_factory=DigestDataQuality)
    safety_flags: DigestSafetyFlags = field(default_factory=DigestSafetyFlags)
    config: DigestConfig = field(default_factory=DigestConfig)
    reason_codes: tuple[str, ...] = ()
    next_review_notes: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.digest_id, str) or not self.digest_id.strip():
            raise ValueError("digest_id must be a non-empty string")
        if not isinstance(self.version, str) or not self.version.strip():
            raise ValueError("version must be a non-empty string")
        if not isinstance(self.generated_at, datetime) or self.generated_at.tzinfo is None:
            raise ValueError("generated_at must be a timezone-aware datetime")
        if not isinstance(self.state, DigestState):
            raise ValueError("state must be a DigestState enum instance")
        if not isinstance(self.sections, tuple):
            raise ValueError("sections must be a tuple")
        for section in self.sections:
            if not isinstance(section, DigestSection):
                raise ValueError("sections must contain DigestSection instances")
        object.__setattr__(self, "reason_codes", _coerce_tuple_of_str(self.reason_codes))
        if not isinstance(self.next_review_notes, str):
            raise ValueError("next_review_notes must be a string")
        _validate_no_unsafe_content(self.next_review_notes, None)

    @classmethod
    def blocked(cls, reason: str, generated_at: datetime | None = None) -> "ResearchDigest":
        """Factory for a blocked digest with safe defaults."""
        if generated_at is None:
            generated_at = datetime.now().astimezone().replace(microsecond=0)
        if generated_at.tzinfo is None:
            raise ValueError("generated_at must be timezone-aware")
        return cls(
            digest_id="blocked",
            generated_at=generated_at,
            state=DigestState.BLOCKED,
            sections=(),
            summary=DigestSummary(
                total_sections=0,
                blocked_sections=1,
                next_review_notes=f"Digest blocked: {reason}",
            ),
            data_quality=DigestDataQuality(
                completeness_pct=0.0,
                blocked_count=1,
                reason=reason,
            ),
            safety_flags=DigestSafetyFlags(),
            reason_codes=(reason,),
        )
