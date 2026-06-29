"""Frozen dataclasses for hunter.research_quality_gate package.

MVP-17 — Local Research Quality Gate / Audit Readiness.

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


QUALITY_GATE_VERSION = "1.0"


class QualityGateState(Enum):
    """Per-check quality gate state."""

    PASS = "pass"
    WARN = "warn"
    BLOCK = "block"
    UNKNOWN = "unknown"


class QualityGateVerdict(Enum):
    """Overall quality gate verdict."""

    PASS = "pass"
    WARN = "warn"
    BLOCK = "block"
    UNKNOWN = "unknown"


class QualityGateCheckKind(Enum):
    """Deterministic quality gate check ordering kind."""

    OBSERVATION = "observation"
    REVIEW = "review"
    INDEX = "index"
    SEARCH = "search"
    BUNDLE = "bundle"
    CHRONICLE = "chronicle"
    DIGEST = "digest"
    CROSS_CUTTING = "cross_cutting"


QUALITY_GATE_REASON_CODES = (
    "EMPTY_GATE",
    "INVALID_CONFIG",
    "UNSAFE_CONFIG",
    "MISSING_OBSERVATION",
    "MISSING_REVIEW",
    "MISSING_INDEX",
    "MISSING_SEARCH",
    "MISSING_BUNDLE",
    "MISSING_CHRONICLE",
    "MISSING_DIGEST",
    "BLOCKED_OBSERVATION",
    "BLOCKED_REVIEW",
    "BLOCKED_INDEX",
    "BLOCKED_SEARCH",
    "BLOCKED_BUNDLE",
    "BLOCKED_CHRONICLE",
    "BLOCKED_DIGEST",
    "UNKNOWN_OBSERVATION",
    "UNKNOWN_REVIEW",
    "UNKNOWN_INDEX",
    "UNKNOWN_SEARCH",
    "UNKNOWN_BUNDLE",
    "UNKNOWN_CHRONICLE",
    "UNKNOWN_DIGEST",
    "UNSAFE_ARTIFACT_FLAGS",
    "UNRESOLVED_BLOCKERS",
    "STALE_ARTIFACT",
    "UNSAFE_GATE_CONTENT",
    "QUALITY_GATE_ERROR",
)

QUALITY_GATE_BLOCKING_REASON_CODES = tuple(
    rc for rc in QUALITY_GATE_REASON_CODES if rc not in ("EMPTY_GATE",)
)

# Superset of FORBIDDEN_DIGEST_TERMS from SPEC-017.
FORBIDDEN_QUALITY_GATE_TERMS = frozenset({
    # Credential / secret terms (from SPEC-017)
    "api_key",
    "secret",
    "exchange_credentials",
    "executable_instructions",
    "private_key",
    "password",
    "token",
    "auth",
    # Trading execution terms (from SPEC-017)
    "enter_long",
    "enter_short",
    "exit_long",
    "exit_short",
    "order",
    "position",
    "leverage",
    "margin",
    "liquidation",
    # Additional trading terms (from SPEC-017)
    "live_trade",
    "real_order",
    "market_order",
    "limit_order",
    "position_size",
    # Quality-gate-specific terms (must not imply deployment/execution readiness)
    "deploy",
    "go_live",
    "production_ready",
    "execution_ready",
    "strategy_ready",
})

_VALID_OUTPUT_FORMATS = ("json", "markdown", "both")
_VALID_QUALITY_GATE_STATES = ("PASS", "WARN", "BLOCK", "UNKNOWN")
_VALID_QUALITY_GATE_VERDICTS = ("PASS", "WARN", "BLOCK", "UNKNOWN")


def _has_unsafe_quality_gate_content(text: str) -> bool:
    """Case-insensitive check for forbidden terms.

    Does not open, traverse, validate, follow, or execute file references.
    """
    lower = text.lower()
    for term in FORBIDDEN_QUALITY_GATE_TERMS:
        if term in lower:
            return True
    return False


def _check_unsafe_mapping(mapping: Mapping[str, Any]) -> bool:
    """Return True if any key or string value contains forbidden terms."""
    for key, value in mapping.items():
        if isinstance(key, str) and _has_unsafe_quality_gate_content(key):
            return True
        if isinstance(value, str) and _has_unsafe_quality_gate_content(value):
            return True
        if isinstance(value, (tuple, list)):
            for item in value:
                if isinstance(item, str) and _has_unsafe_quality_gate_content(item):
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
    if notes is not None and _has_unsafe_quality_gate_content(notes):
        raise ValueError("UNSAFE_GATE_CONTENT")
    if metadata is not None and _check_unsafe_mapping(metadata):
        raise ValueError("UNSAFE_GATE_CONTENT")


def _coerce_tuple_of_str(value: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    """Coerce a tuple or list of items into a tuple of non-empty strings."""
    if isinstance(value, tuple):
        return tuple(str(x) for x in value if x)
    if isinstance(value, list):
        return tuple(str(x) for x in value if x)
    raise ValueError("reason_codes must be a tuple or list of strings")


def _coerce_tuple_of_check_kinds(
    value: tuple[QualityGateCheckKind, ...] | list[QualityGateCheckKind],
) -> tuple[QualityGateCheckKind, ...]:
    """Coerce a tuple or list into a tuple of QualityGateCheckKind enum instances."""
    if isinstance(value, (tuple, list)):
        result = []
        for item in value:
            if not isinstance(item, QualityGateCheckKind):
                raise ValueError(
                    "required_artifact_kinds must contain QualityGateCheckKind enum instances"
                )
            result.append(item)
        return tuple(result)
    raise ValueError("required_artifact_kinds must be a tuple or list of QualityGateCheckKind")


def _coerce_mapping(value: Mapping[str, Any] | dict[str, Any] | None) -> Mapping[str, Any]:
    """Coerce a mapping into an immutable MappingProxyType."""
    if value is None:
        return MappingProxyType({})
    if isinstance(value, Mapping):
        return MappingProxyType(dict(value))
    raise ValueError("metadata must be a mapping")


@dataclass(frozen=True)
class QualityGateConfig:
    """Configuration for quality gate generation.

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
    required_artifact_kinds: tuple[QualityGateCheckKind, ...] = (
        QualityGateCheckKind.OBSERVATION,
        QualityGateCheckKind.REVIEW,
        QualityGateCheckKind.INDEX,
        QualityGateCheckKind.SEARCH,
        QualityGateCheckKind.BUNDLE,
        QualityGateCheckKind.CHRONICLE,
        QualityGateCheckKind.DIGEST,
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
            "required_artifact_kinds",
            _coerce_tuple_of_check_kinds(self.required_artifact_kinds),
        )
        if not isinstance(self.max_staleness_minutes, int) or self.max_staleness_minutes < 1:
            raise ValueError("max_staleness_minutes must be a positive integer")


@dataclass(frozen=True)
class QualityGateSafetyFlags:
    """Safety flags for quality gate output.

    Mirrors the DigestSafetyFlags pattern from SPEC-017.
    Unsafe flags default to False. Safe output flags default to True.
    """

    # Runtime safety flags
    dry_run: bool = True
    live_trading_enabled: bool = False
    real_orders_enabled: bool = False
    leverage_enabled: bool = False
    shorting_enabled: bool = False

    # Output safety flags
    quality_gate_output_is_human_audit_only: bool = True
    quality_gate_output_not_trading_signal: bool = True
    quality_gate_output_not_trade_approval: bool = True
    quality_gate_output_not_execution_readiness: bool = True
    quality_gate_output_not_strategy_readiness: bool = True
    quality_gate_output_not_for_execution: bool = True
    quality_gate_output_not_for_strategy: bool = True
    quality_gate_output_not_for_freqtrade: bool = True
    quality_gate_output_not_for_order: bool = True
    quality_gate_output_not_for_exchange: bool = True

    # Feedback safety flags
    quality_gate_feedback_into_execution: bool = False
    cross_layer_feedback_into_execution: bool = False

    # Advisory flags
    file_refs_not_traversed: bool = True

    def __post_init__(self) -> None:
        unsafe_flags = (
            self.live_trading_enabled,
            self.real_orders_enabled,
            self.leverage_enabled,
            self.shorting_enabled,
            self.quality_gate_feedback_into_execution,
            self.cross_layer_feedback_into_execution,
        )
        if any(unsafe_flags):
            raise ValueError("unsafe quality gate safety flags are enabled")
        if not self.dry_run:
            raise ValueError("dry_run must be True")
        safe_flags = (
            self.quality_gate_output_is_human_audit_only,
            self.quality_gate_output_not_trading_signal,
            self.quality_gate_output_not_trade_approval,
            self.quality_gate_output_not_execution_readiness,
            self.quality_gate_output_not_strategy_readiness,
            self.quality_gate_output_not_for_execution,
            self.quality_gate_output_not_for_strategy,
            self.quality_gate_output_not_for_freqtrade,
            self.quality_gate_output_not_for_order,
            self.quality_gate_output_not_for_exchange,
            self.file_refs_not_traversed,
        )
        if not all(safe_flags):
            raise ValueError("safe quality gate output flags must be True")


@dataclass(frozen=True)
class QualityGateCheck:
    """One audit-readiness check per artifact category or cross-cutting concern."""

    check_kind: QualityGateCheckKind
    state: str = "UNKNOWN"
    reason_codes: tuple[str, ...] = ()
    notes: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.check_kind, QualityGateCheckKind):
            raise ValueError("check_kind must be a QualityGateCheckKind enum instance")
        state_upper = self.state.upper()
        if state_upper not in _VALID_QUALITY_GATE_STATES:
            raise ValueError(
                f"state must be one of {_VALID_QUALITY_GATE_STATES}, got {self.state!r}"
            )
        object.__setattr__(self, "state", state_upper)
        object.__setattr__(self, "reason_codes", _coerce_tuple_of_str(self.reason_codes))
        object.__setattr__(self, "metadata", _coerce_mapping(self.metadata))
        _validate_no_unsafe_content(self.notes, self.metadata)


@dataclass(frozen=True)
class QualityGateSummary:
    """Top-level aggregated quality gate summary."""

    total_checks: int = 0
    pass_checks: int = 0
    warn_checks: int = 0
    block_checks: int = 0
    unknown_checks: int = 0
    total_artifacts: int = 0
    total_blockers: int = 0
    unresolved_blockers: int = 0
    verdict: str = "UNKNOWN"
    reason_code_counts: Mapping[str, int] = field(default_factory=dict)
    handoff_notes: str = ""

    def __post_init__(self) -> None:
        for int_attr in (
            "total_checks",
            "pass_checks",
            "warn_checks",
            "block_checks",
            "unknown_checks",
            "total_artifacts",
            "total_blockers",
            "unresolved_blockers",
        ):
            value = getattr(self, int_attr)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{int_attr} must be a non-negative integer")
        if self.total_checks > 0:
            counted = self.pass_checks + self.warn_checks + self.block_checks + self.unknown_checks
            if counted != self.total_checks:
                raise ValueError(
                    "pass_checks + warn_checks + block_checks + unknown_checks must equal total_checks"
                )
        verdict_upper = self.verdict.upper()
        if verdict_upper not in _VALID_QUALITY_GATE_VERDICTS:
            raise ValueError(
                f"verdict must be one of {_VALID_QUALITY_GATE_VERDICTS}, got {self.verdict!r}"
            )
        object.__setattr__(self, "verdict", verdict_upper)
        if not isinstance(self.reason_code_counts, Mapping):
            raise ValueError("reason_code_counts must be a mapping")
        if not isinstance(self.handoff_notes, str):
            raise ValueError("handoff_notes must be a string")
        _validate_no_unsafe_content(self.handoff_notes, None)


@dataclass(frozen=True)
class QualityGateDataQuality:
    """Completeness and blocker metrics."""

    completeness_pct: float = 0.0
    ready_pct: float = 0.0
    missing_count: int = 0
    stale_count: int = 0
    blocked_count: int = 0
    unknown_count: int = 0
    total_checks: int = 0
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
            "total_checks",
        ):
            value = getattr(self, int_attr)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{int_attr} must be a non-negative integer")
        if not isinstance(self.reason, str):
            raise ValueError("reason must be a string")
        _validate_no_unsafe_content(self.reason, None)


@dataclass(frozen=True)
class ResearchQualityGate:
    """Full quality gate container."""

    gate_id: str
    generated_at: datetime
    version: str = QUALITY_GATE_VERSION
    verdict: QualityGateVerdict = field(default_factory=lambda: QualityGateVerdict.UNKNOWN)
    checks: tuple[QualityGateCheck, ...] = ()
    summary: QualityGateSummary = field(default_factory=QualityGateSummary)
    data_quality: QualityGateDataQuality = field(default_factory=QualityGateDataQuality)
    safety_flags: QualityGateSafetyFlags = field(default_factory=QualityGateSafetyFlags)
    config: QualityGateConfig = field(default_factory=QualityGateConfig)
    reason_codes: tuple[str, ...] = ()
    handoff_notes: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.gate_id, str) or not self.gate_id.strip():
            raise ValueError("gate_id must be a non-empty string")
        if not isinstance(self.version, str) or not self.version.strip():
            raise ValueError("version must be a non-empty string")
        if not isinstance(self.generated_at, datetime) or self.generated_at.tzinfo is None:
            raise ValueError("generated_at must be a timezone-aware datetime")
        if not isinstance(self.verdict, QualityGateVerdict):
            raise ValueError("verdict must be a QualityGateVerdict enum instance")
        if not isinstance(self.checks, tuple):
            raise ValueError("checks must be a tuple")
        for check in self.checks:
            if not isinstance(check, QualityGateCheck):
                raise ValueError("checks must contain QualityGateCheck instances")
        object.__setattr__(self, "reason_codes", _coerce_tuple_of_str(self.reason_codes))
        if not isinstance(self.handoff_notes, str):
            raise ValueError("handoff_notes must be a string")
        _validate_no_unsafe_content(self.handoff_notes, None)

    @classmethod
    def blocked(cls, reason: str, generated_at: datetime | None = None) -> "ResearchQualityGate":
        """Factory for a blocked quality gate with safe defaults."""
        if generated_at is None:
            generated_at = datetime.now().astimezone().replace(microsecond=0)
        if generated_at.tzinfo is None:
            raise ValueError("generated_at must be timezone-aware")
        return cls(
            gate_id="blocked",
            generated_at=generated_at,
            verdict=QualityGateVerdict.BLOCK,
            checks=(),
            summary=QualityGateSummary(
                total_checks=0,
                block_checks=1,
                verdict="BLOCK",
                handoff_notes=f"Quality gate blocked: {reason}. "
                "This is not trade approval, execution approval, or strategy approval.",
            ),
            data_quality=QualityGateDataQuality(
                completeness_pct=0.0,
                blocked_count=1,
                reason=reason,
            ),
            safety_flags=QualityGateSafetyFlags(),
            reason_codes=(reason,),
        )
