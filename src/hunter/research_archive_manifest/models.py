"""Frozen dataclasses for hunter.research_archive_manifest package.

MVP-19 — Local Research Archive Manifest.

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


ARCHIVE_MANIFEST_VERSION = "1.0"


class ArchiveManifestState(Enum):
    """Overall archive manifest state."""

    READY = "ready"
    WARN = "warn"
    BLOCK = "block"
    UNKNOWN = "unknown"


class ArchiveArtifactFamily(Enum):
    """Deterministic artifact family ordering."""

    OBSERVATION_REPORT = "observation_report"
    OPERATOR_REVIEW = "operator_review"
    REVIEW_INDEX = "review_index"
    REVIEW_SEARCH = "review_search"
    RESEARCH_BUNDLE = "research_bundle"
    RESEARCH_CHRONICLE = "research_chronicle"
    RESEARCH_DIGEST = "research_digest"
    RESEARCH_QUALITY_GATE = "research_quality_gate"
    RESEARCH_HANDOFF = "research_handoff"


class ArchiveArtifactEntryState(Enum):
    """Per-family inventory entry state."""

    PRESENT = "present"
    STALE = "stale"
    MISSING = "missing"
    UNKNOWN = "unknown"


ARCHIVE_REASON_CODES = (
    "EMPTY_MANIFEST",
    "INVALID_CONFIG",
    "UNSAFE_CONFIG",
    "MISSING_OBSERVATION_REPORT",
    "MISSING_OPERATOR_REVIEW",
    "MISSING_REVIEW_INDEX",
    "MISSING_REVIEW_SEARCH",
    "MISSING_RESEARCH_BUNDLE",
    "MISSING_RESEARCH_CHRONICLE",
    "MISSING_RESEARCH_DIGEST",
    "MISSING_RESEARCH_QUALITY_GATE",
    "MISSING_RESEARCH_HANDOFF",
    "STALE_OBSERVATION_REPORT",
    "STALE_OPERATOR_REVIEW",
    "STALE_REVIEW_INDEX",
    "STALE_REVIEW_SEARCH",
    "STALE_RESEARCH_BUNDLE",
    "STALE_RESEARCH_CHRONICLE",
    "STALE_RESEARCH_DIGEST",
    "STALE_RESEARCH_QUALITY_GATE",
    "STALE_RESEARCH_HANDOFF",
    "UNKNOWN_OBSERVATION_REPORT",
    "UNKNOWN_OPERATOR_REVIEW",
    "UNKNOWN_REVIEW_INDEX",
    "UNKNOWN_REVIEW_SEARCH",
    "UNKNOWN_RESEARCH_BUNDLE",
    "UNKNOWN_RESEARCH_CHRONICLE",
    "UNKNOWN_RESEARCH_DIGEST",
    "UNKNOWN_RESEARCH_QUALITY_GATE",
    "UNKNOWN_RESEARCH_HANDOFF",
    "UNSAFE_ARTIFACT_FLAGS",
    "UNRESOLVED_BLOCKERS",
    "UNSAFE_MANIFEST_CONTENT",
    "ARCHIVE_ERROR",
)

ARCHIVE_BLOCKING_REASON_CODES = tuple(
    rc for rc in ARCHIVE_REASON_CODES if rc != "EMPTY_MANIFEST"
)

# Superset of FORBIDDEN_HANDOFF_TERMS from SPEC-019.
FORBIDDEN_ARCHIVE_MANIFEST_TERMS = frozenset({
    # Credential / secret terms (from SPEC-019)
    "api_key",
    "secret",
    "exchange_credentials",
    "executable_instructions",
    "private_key",
    "password",
    "token",
    "auth",
    # Trading execution terms (from SPEC-019)
    "enter_long",
    "enter_short",
    "exit_long",
    "exit_short",
    "order",
    "position",
    "leverage",
    "margin",
    "liquidation",
    # Additional trading terms (from SPEC-019)
    "live_trade",
    "real_order",
    "market_order",
    "limit_order",
    "position_size",
    # Archive-manifest-specific terms (must not imply deployment/execution readiness)
    "go_live",
    "production_ready",
    "execution_ready",
    "strategy_ready",
})


_FAMILY_LOCAL_REFERENCE = {
    ArchiveArtifactFamily.OBSERVATION_REPORT: "data/observation/latest_observation_report.json",
    ArchiveArtifactFamily.OPERATOR_REVIEW: "data/review/latest_review_audit_record.json",
    ArchiveArtifactFamily.REVIEW_INDEX: "data/review_index/latest_review_index.json",
    ArchiveArtifactFamily.REVIEW_SEARCH: "data/review_search/latest_search_result.json",
    ArchiveArtifactFamily.RESEARCH_BUNDLE: "data/research_bundle/latest_research_bundle.json",
    ArchiveArtifactFamily.RESEARCH_CHRONICLE: "data/chronicle/latest_research_chronicle.json",
    ArchiveArtifactFamily.RESEARCH_DIGEST: "data/research_digest/latest_research_digest.json",
    ArchiveArtifactFamily.RESEARCH_QUALITY_GATE: "data/research_quality_gate/latest_research_quality_gate.json",
    ArchiveArtifactFamily.RESEARCH_HANDOFF: "data/research_handoff/latest_research_handoff_packet.json",
}

_FAMILY_SPEC_REFERENCE = {
    ArchiveArtifactFamily.OBSERVATION_REPORT: "SPEC-011",
    ArchiveArtifactFamily.OPERATOR_REVIEW: "SPEC-012",
    ArchiveArtifactFamily.REVIEW_INDEX: "SPEC-013",
    ArchiveArtifactFamily.REVIEW_SEARCH: "SPEC-014",
    ArchiveArtifactFamily.RESEARCH_BUNDLE: "SPEC-015",
    ArchiveArtifactFamily.RESEARCH_CHRONICLE: "SPEC-016",
    ArchiveArtifactFamily.RESEARCH_DIGEST: "SPEC-017",
    ArchiveArtifactFamily.RESEARCH_QUALITY_GATE: "SPEC-018",
    ArchiveArtifactFamily.RESEARCH_HANDOFF: "SPEC-019",
}

ARCHIVE_FAMILY_INFO: Mapping[ArchiveArtifactFamily, tuple[str, str]] = MappingProxyType(
    {
        family: (_FAMILY_LOCAL_REFERENCE[family], _FAMILY_SPEC_REFERENCE[family])
        for family in ArchiveArtifactFamily
    }
)

_VALID_OUTPUT_FORMATS = ("json", "markdown", "both")
_VALID_MANIFEST_STATES = ("READY", "WARN", "BLOCK", "UNKNOWN")
_VALID_ENTRY_STATES = ("PRESENT", "STALE", "MISSING", "UNKNOWN")


def _has_unsafe_archive_manifest_content(text: str | None) -> bool:
    """Case-insensitive check for forbidden terms.

    Does not open, traverse, validate, follow, or execute file references.
    """
    if not isinstance(text, str):
        return False
    lower = text.lower()
    for term in FORBIDDEN_ARCHIVE_MANIFEST_TERMS:
        if term in lower:
            return True
    return False


def _check_unsafe_mapping(mapping: Mapping[str, Any]) -> bool:
    """Return True if any key or string value contains forbidden terms."""
    for key, value in mapping.items():
        if isinstance(key, str) and _has_unsafe_archive_manifest_content(key):
            return True
        if isinstance(value, str) and _has_unsafe_archive_manifest_content(value):
            return True
        if isinstance(value, (tuple, list)):
            for item in value:
                if isinstance(item, str) and _has_unsafe_archive_manifest_content(item):
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
    if text is not None and _has_unsafe_archive_manifest_content(text):
        raise ValueError("UNSAFE_MANIFEST_CONTENT")
    if metadata is not None and _check_unsafe_mapping(metadata):
        raise ValueError("UNSAFE_MANIFEST_CONTENT")


def _coerce_tuple_of_str(value: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    """Coerce a tuple or list of items into a tuple of non-empty strings."""
    if isinstance(value, tuple):
        return tuple(str(x) for x in value if x)
    if isinstance(value, list):
        return tuple(str(x) for x in value if x)
    raise ValueError("reason_codes must be a tuple or list of strings")


def _coerce_tuple_of_families(
    value: tuple[ArchiveArtifactFamily, ...] | list[ArchiveArtifactFamily],
) -> tuple[ArchiveArtifactFamily, ...]:
    """Coerce a tuple or list into a tuple of ArchiveArtifactFamily enum instances."""
    if isinstance(value, (tuple, list)):
        result = []
        for item in value:
            if not isinstance(item, ArchiveArtifactFamily):
                raise ValueError(
                    "required_families must contain ArchiveArtifactFamily enum instances"
                )
            result.append(item)
        return tuple(result)
    raise ValueError("required_families must be a tuple or list of ArchiveArtifactFamily")


def _coerce_mapping(value: Mapping[str, Any] | dict[str, Any] | None) -> Mapping[str, Any]:
    """Coerce a mapping into an immutable MappingProxyType."""
    if value is None:
        return MappingProxyType({})
    if isinstance(value, Mapping):
        return MappingProxyType(dict(value))
    raise ValueError("metadata must be a mapping")


def _normalize_entry_state(raw: str | None) -> str:
    """Normalize an entry state string to one of the valid values."""
    if raw is None:
        return "UNKNOWN"
    normalized = str(raw).strip().upper()
    if normalized not in _VALID_ENTRY_STATES:
        raise ValueError(
            f"state must be one of {_VALID_ENTRY_STATES}, got {raw!r}"
        )
    return normalized


@dataclass(frozen=True)
class ArchiveManifestConfig:
    """Configuration for archive manifest generation.

    Unsafe flags must remain False. dry_run must remain True.
    """

    version: str = ARCHIVE_MANIFEST_VERSION
    generated_at: datetime | None = None
    output_format: str = "both"
    dry_run: bool = True
    live_trading_enabled: bool = False
    real_orders_enabled: bool = False
    leverage_enabled: bool = False
    shorting_enabled: bool = False
    block_on_unknown: bool = True
    required_families: tuple[ArchiveArtifactFamily, ...] = field(
        default_factory=lambda: tuple(ArchiveArtifactFamily)
    )
    max_staleness_minutes: int = 60
    include_manifest_notes: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.version, str) or not self.version:
            raise ValueError("version must be a non-empty string")
        if self.output_format not in _VALID_OUTPUT_FORMATS:
            raise ValueError(
                f"output_format must be one of {_VALID_OUTPUT_FORMATS}"
            )
        if self.dry_run is not True:
            raise ValueError("dry_run must be True")
        for attr in (
            "live_trading_enabled",
            "real_orders_enabled",
            "leverage_enabled",
            "shorting_enabled",
        ):
            if getattr(self, attr) is not False:
                raise ValueError(f"{attr} must be False")
        if not isinstance(self.block_on_unknown, bool):
            raise ValueError("block_on_unknown must be a bool")
        _coerce_tuple_of_families(self.required_families)
        if not isinstance(self.max_staleness_minutes, int) or self.max_staleness_minutes <= 0:
            raise ValueError("max_staleness_minutes must be a positive integer")


@dataclass(frozen=True)
class ArchiveManifestSafetyFlags:
    """Fail-closed safety flags for archive manifest output."""

    # Runtime safety flags
    dry_run: bool = True
    live_trading_enabled: bool = False
    real_orders_enabled: bool = False
    leverage_enabled: bool = False
    shorting_enabled: bool = False

    # Output safety flags
    archive_output_is_human_audit_only: bool = True
    archive_output_not_trading_signal: bool = True
    archive_output_not_trade_approval: bool = True
    archive_output_not_execution_readiness: bool = True
    archive_output_not_strategy_readiness: bool = True
    archive_output_not_release_approval: bool = True
    archive_output_not_deployment_approval: bool = True
    archive_output_not_transaction_permission: bool = True
    archive_output_not_for_execution: bool = True
    archive_output_not_for_strategy: bool = True
    archive_output_not_for_freqtrade: bool = True
    archive_output_not_for_order: bool = True
    archive_output_not_for_exchange: bool = True

    # Feedback safety flags
    archive_manifest_feedback_into_execution: bool = False
    cross_layer_feedback_into_execution: bool = False

    # Advisory flags
    file_refs_not_traversed: bool = True
    artifact_files_not_read: bool = True

    def __post_init__(self) -> None:
        if self.dry_run is not True:
            raise ValueError("dry_run must be True")
        for attr in (
            "live_trading_enabled",
            "real_orders_enabled",
            "leverage_enabled",
            "shorting_enabled",
            "archive_manifest_feedback_into_execution",
            "cross_layer_feedback_into_execution",
        ):
            if getattr(self, attr) is not False:
                raise ValueError("unsafe archive manifest safety flags are enabled")
        for attr in (
            "archive_output_is_human_audit_only",
            "archive_output_not_trading_signal",
            "archive_output_not_trade_approval",
            "archive_output_not_execution_readiness",
            "archive_output_not_strategy_readiness",
            "archive_output_not_release_approval",
            "archive_output_not_deployment_approval",
            "archive_output_not_transaction_permission",
            "archive_output_not_for_execution",
            "archive_output_not_for_strategy",
            "archive_output_not_for_freqtrade",
            "archive_output_not_for_order",
            "archive_output_not_for_exchange",
            "file_refs_not_traversed",
            "artifact_files_not_read",
        ):
            if getattr(self, attr) is not True:
                raise ValueError("safe archive manifest output flags must be True")


@dataclass(frozen=True)
class ArchiveArtifactEntry:
    """One artifact family entry in the archive manifest."""

    artifact_family: ArchiveArtifactFamily
    title: str = ""
    state: str = "UNKNOWN"
    spec_reference: str = ""
    local_reference: str = ""
    version: str = ""
    generated_at: datetime | None = None
    reason_codes: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if not isinstance(self.artifact_family, ArchiveArtifactFamily):
            raise ValueError("artifact_family must be an ArchiveArtifactFamily")
        object.__setattr__(
            self, "state", _normalize_entry_state(self.state)
        )
        object.__setattr__(
            self, "reason_codes", _coerce_tuple_of_str(self.reason_codes)
        )
        object.__setattr__(
            self, "metadata", _coerce_mapping(self.metadata)
        )
        if self.generated_at is not None and not isinstance(self.generated_at, datetime):
            raise ValueError("generated_at must be a datetime or None")
        if self.generated_at is not None and self.generated_at.tzinfo is None:
            raise ValueError("generated_at must be a timezone-aware datetime or None")
        _validate_no_unsafe_content(self.spec_reference, None)
        _validate_no_unsafe_content(self.local_reference, None)
        _validate_no_unsafe_content(self.version, None)
        _validate_no_unsafe_content(None, self.metadata)


@dataclass(frozen=True)
class ArchiveManifestSummary:
    """Aggregated summary across all artifact families."""

    total_families: int = 0
    present_count: int = 0
    stale_count: int = 0
    missing_count: int = 0
    unknown_count: int = 0
    manifest_state: str = "UNKNOWN"
    reason_code_counts: Mapping[str, int] = field(
        default_factory=lambda: MappingProxyType({})
    )
    manifest_notes: str = ""

    def __post_init__(self) -> None:
        for attr in (
            "total_families",
            "present_count",
            "stale_count",
            "missing_count",
            "unknown_count",
        ):
            value = getattr(self, attr)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{attr} must be a non-negative integer")
        if (
            self.present_count
            + self.stale_count
            + self.missing_count
            + self.unknown_count
            != self.total_families
        ):
            raise ValueError(
                "present_count + stale_count + missing_count + unknown_count must equal total_families"
            )
        if self.manifest_state not in _VALID_MANIFEST_STATES:
            raise ValueError(
                f"manifest_state must be one of {_VALID_MANIFEST_STATES}"
            )
        object.__setattr__(
            self, "reason_code_counts", _coerce_mapping(self.reason_code_counts)
        )
        _validate_no_unsafe_content(self.manifest_notes, None)


@dataclass(frozen=True)
class ArchiveManifestDataQuality:
    """Data-quality metrics for the archive manifest."""

    completeness_pct: float = 0.0
    coverage_pct: float = 0.0
    present_pct: float = 0.0
    missing_count: int = 0
    stale_count: int = 0
    unknown_count: int = 0
    total_families: int = 0
    reason: str = ""

    def __post_init__(self) -> None:
        for attr in ("completeness_pct", "coverage_pct", "present_pct"):
            value = getattr(self, attr)
            if not isinstance(value, (int, float)) or value < 0.0 or value > 100.0:
                raise ValueError(f"{attr} must be between 0.0 and 100.0")
        for attr in ("missing_count", "stale_count", "unknown_count", "total_families"):
            value = getattr(self, attr)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{attr} must be a non-negative integer")
        _validate_no_unsafe_content(self.reason, None)


@dataclass(frozen=True)
class ResearchArchiveManifest:
    """Full archive manifest container."""

    manifest_id: str
    generated_at: datetime
    version: str = ARCHIVE_MANIFEST_VERSION
    manifest_state: ArchiveManifestState = field(
        default_factory=lambda: ArchiveManifestState.UNKNOWN
    )
    entries: tuple[ArchiveArtifactEntry, ...] = ()
    summary: ArchiveManifestSummary = field(
        default_factory=ArchiveManifestSummary
    )
    data_quality: ArchiveManifestDataQuality = field(
        default_factory=ArchiveManifestDataQuality
    )
    safety_flags: ArchiveManifestSafetyFlags = field(
        default_factory=ArchiveManifestSafetyFlags
    )
    config: ArchiveManifestConfig = field(default_factory=ArchiveManifestConfig)
    reason_codes: tuple[str, ...] = ()
    manifest_notes: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.manifest_id, str) or not self.manifest_id:
            raise ValueError("manifest_id must be a non-empty string")
        if not isinstance(self.generated_at, datetime) or self.generated_at.tzinfo is None:
            raise ValueError("generated_at must be a timezone-aware datetime")
        if not isinstance(self.manifest_state, ArchiveManifestState):
            raise ValueError("manifest_state must be an ArchiveManifestState")
        if not isinstance(self.entries, tuple):
            raise ValueError("entries must be a tuple")
        for entry in self.entries:
            if not isinstance(entry, ArchiveArtifactEntry):
                raise ValueError("entries must contain ArchiveArtifactEntry instances")
        object.__setattr__(
            self, "reason_codes", _coerce_tuple_of_str(self.reason_codes)
        )
        _validate_no_unsafe_content(self.manifest_notes, None)

    @classmethod
    def blocked(
        cls,
        reason: str,
        generated_at: datetime,
        *,
        config: ArchiveManifestConfig | None = None,
    ) -> "ResearchArchiveManifest":
        """Factory for a blocked manifest with safe notes."""
        if config is None:
            config = ArchiveManifestConfig()
        safe_note = (
            f"Archive manifest blocked: {reason}. "
            "This manifest is a human-audit inventory artifact only. "
            "It is not a trading signal, not trade approval, not execution readiness, "
            "not strategy readiness, not release/deployment approval, and not transaction permission."
        )
        return cls(
            manifest_id=f"archive:{config.version}:{generated_at.strftime('%Y-%m-%dT%H:%M:%S.%f')}",
            generated_at=generated_at,
            manifest_state=ArchiveManifestState.BLOCK,
            summary=ArchiveManifestSummary(
                manifest_state="BLOCK",
                manifest_notes=safe_note,
            ),
            config=config,
            reason_codes=(reason,),
            manifest_notes=safe_note,
        )
