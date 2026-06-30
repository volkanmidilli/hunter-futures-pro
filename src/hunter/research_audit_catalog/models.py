"""Frozen dataclasses for hunter.research_audit_catalog package.

MVP-21 — Local Research Audit Catalog.

All dataclasses are frozen. Validation runs in __post_init__.
File references and metadata strings are local strings only and are never
traversed, opened, followed, validated, or executed.

The audit catalog is a human-audit / contractor-handoff artifact only.
It is not release approval, deployment approval, trading signal, trade
approval, execution approval, strategy approval, or transaction permission.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any


CATALOG_VERSION = "1.0"


class CatalogState(Enum):
    """State of a catalog entry or the overall catalog."""

    DISABLED = "DISABLED"
    READY = "READY"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"


class CatalogArtifactKind(Enum):
    """Which research layer produced this artifact."""

    OBSERVATION_REPORT = "OBSERVATION_REPORT"          # MVP-10
    OPERATOR_REVIEW = "OPERATOR_REVIEW"                # MVP-11
    REVIEW_INDEX = "REVIEW_INDEX"                      # MVP-12
    REVIEW_SEARCH = "REVIEW_SEARCH"                    # MVP-13
    RESEARCH_BUNDLE = "RESEARCH_BUNDLE"                # MVP-14
    RESEARCH_CHRONICLE = "RESEARCH_CHRONICLE"          # MVP-15
    RESEARCH_DIGEST = "RESEARCH_DIGEST"                # MVP-16
    RESEARCH_QUALITY_GATE = "RESEARCH_QUALITY_GATE"    # MVP-17
    RESEARCH_HANDOFF = "RESEARCH_HANDOFF"              # MVP-18
    RESEARCH_ARCHIVE_MANIFEST = "RESEARCH_ARCHIVE_MANIFEST"  # MVP-19
    RESEARCH_RELEASE_NOTES = "RESEARCH_RELEASE_NOTES"  # MVP-20


# Deterministic canonical order for MVP-10 through MVP-20 artifact layers.
CATALOG_ARTIFACT_KINDS: tuple[CatalogArtifactKind, ...] = tuple(CatalogArtifactKind)


MISSING_ARTIFACTS = "MISSING_ARTIFACTS"
INVALID_ARTIFACT = "INVALID_ARTIFACT"
INVALID_ARTIFACT_ID = "INVALID_ARTIFACT_ID"
INVALID_ARTIFACT_KIND = "INVALID_ARTIFACT_KIND"
UNSUPPORTED_ARTIFACT_VERSION = "UNSUPPORTED_ARTIFACT_VERSION"
UNSAFE_ARTIFACT_STATE = "UNSAFE_ARTIFACT_STATE"
UNSAFE_SAFETY_FLAGS = "UNSAFE_SAFETY_FLAGS"
DUPLICATE_ARTIFACT_ID = "DUPLICATE_ARTIFACT_ID"
EMPTY_CATALOG = "EMPTY_CATALOG"
UNSAFE_CATALOG_CONTENT = "UNSAFE_CATALOG_CONTENT"
STALE_ARTIFACT = "STALE_ARTIFACT"
CATALOG_ERROR = "CATALOG_ERROR"
DEFAULT_BLOCKED = "DEFAULT_BLOCKED"

CATALOG_REASON_CODES: tuple[str, ...] = (
    MISSING_ARTIFACTS,
    INVALID_ARTIFACT,
    INVALID_ARTIFACT_ID,
    INVALID_ARTIFACT_KIND,
    UNSUPPORTED_ARTIFACT_VERSION,
    UNSAFE_ARTIFACT_STATE,
    UNSAFE_SAFETY_FLAGS,
    DUPLICATE_ARTIFACT_ID,
    EMPTY_CATALOG,
    UNSAFE_CATALOG_CONTENT,
    STALE_ARTIFACT,
    CATALOG_ERROR,
    DEFAULT_BLOCKED,
)

CATALOG_NON_BLOCKING_REASON_CODES: tuple[str, ...] = (STALE_ARTIFACT,)
CATALOG_BLOCKING_REASON_CODES: tuple[str, ...] = tuple(
    rc for rc in CATALOG_REASON_CODES if rc not in CATALOG_NON_BLOCKING_REASON_CODES
)


# Superset of forbidden terms from prior MVPs plus release/deployment-approval
# and action-command keywords. Generated safety notices are not subjected to
# this check; it applies only to caller-provided content.
FORBIDDEN_CATALOG_TERMS: frozenset[str] = frozenset({
    # Credential / secret terms
    "api_key",
    "secret",
    "exchange_credentials",
    "executable_instructions",
    "operational_instructions",
    "private_key",
    "password",
    "token",
    "auth",
    # Trading execution terms
    "enter_long",
    "enter_short",
    "exit_long",
    "exit_short",
    "buy_now",
    "sell_now",
    "execute_trade",
    "place_order",
    "market_order",
    "limit_order",
    "stop_loss",
    "take_profit",
    "order",
    "position",
    "leverage",
    "shorting",
    "margin",
    "liquidation",
    "live_trade",
    "real_order",
    "position_size",
    # Exchange / runtime terms
    "binance",
    # Release/deployment/execution readiness terms (must not imply approval)
    "go_live",
    "production_ready",
    "execution_ready",
    "strategy_ready",
    "deployment_ready",
    "release_ready",
    "launch_live",
    # Action-command keywords (must not emit action commands)
    "deploy",
    "execute",
    "run",
    "start",
    "stop",
    "trigger",
})


_CATALOG_ARTIFACT_SPEC_REFERENCE: dict[CatalogArtifactKind, str] = {
    CatalogArtifactKind.OBSERVATION_REPORT: "SPEC-011",
    CatalogArtifactKind.OPERATOR_REVIEW: "SPEC-012",
    CatalogArtifactKind.REVIEW_INDEX: "SPEC-013",
    CatalogArtifactKind.REVIEW_SEARCH: "SPEC-014",
    CatalogArtifactKind.RESEARCH_BUNDLE: "SPEC-015",
    CatalogArtifactKind.RESEARCH_CHRONICLE: "SPEC-016",
    CatalogArtifactKind.RESEARCH_DIGEST: "SPEC-017",
    CatalogArtifactKind.RESEARCH_QUALITY_GATE: "SPEC-018",
    CatalogArtifactKind.RESEARCH_HANDOFF: "SPEC-019",
    CatalogArtifactKind.RESEARCH_ARCHIVE_MANIFEST: "SPEC-020",
    CatalogArtifactKind.RESEARCH_RELEASE_NOTES: "SPEC-021",
}

CATALOG_ARTIFACT_SPEC_REFERENCE: Mapping[CatalogArtifactKind, str] = MappingProxyType(
    _CATALOG_ARTIFACT_SPEC_REFERENCE
)


def _ensure_timezone_aware(value: datetime | None, field_name: str) -> datetime | None:
    """Raise ValueError if value is a naive datetime (tzinfo is None).

    Returns value unchanged when it is timezone-aware or None.
    """
    if value is None:
        return None
    if not isinstance(value, datetime):
        raise ValueError(f"{field_name} must be a datetime")
    if value.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value


def _ensure_tuple_of_str(
    value: Iterable[str] | tuple[str, ...] | list[str] | None,
    field_name: str,
) -> tuple[str, ...]:
    """Validate that value is a tuple/list of non-empty strings.

    Raises ValueError if any element is not a non-empty string.
    Returns a validated tuple.
    """
    if value is None:
        return ()
    if isinstance(value, (tuple, list)):
        for item in value:
            if not isinstance(item, str) or not item:
                raise ValueError(f"{field_name} must contain non-empty strings")
        return tuple(value)
    raise ValueError(f"{field_name} must be a tuple or list of strings")


def _has_forbidden_catalog_term(text: str) -> bool:
    """Case-insensitive check for forbidden terms in a single string."""
    if not isinstance(text, str):
        return False
    lower = text.lower()
    for term in FORBIDDEN_CATALOG_TERMS:
        if term in lower:
            return True
    return False


def _check_forbidden_mapping(mapping: Mapping[str, Any]) -> bool:
    """Return True if any key or string value in mapping contains forbidden terms."""
    for key, value in mapping.items():
        if isinstance(key, str) and _has_forbidden_catalog_term(key):
            return True
        if isinstance(value, str) and _has_forbidden_catalog_term(value):
            return True
        if isinstance(value, (tuple, list)):
            for item in value:
                if isinstance(item, str) and _has_forbidden_catalog_term(item):
                    return True
        if isinstance(value, Mapping):
            if _check_forbidden_mapping(value):
                return True
    return False


def _check_forbidden_catalog_content(
    text_fields: tuple[str, ...],
    tags: tuple[str, ...],
    metadata: Mapping[str, Any],
) -> None:
    """Check all text fields, tags, and metadata keys for forbidden terms.

    Uses FORBIDDEN_CATALOG_TERMS for case-insensitive substring matching.
    Raises ValueError if any forbidden term is found.
    """
    for text in text_fields:
        if _has_forbidden_catalog_term(text):
            raise ValueError("UNSAFE_CATALOG_CONTENT")
    for tag in tags:
        if _has_forbidden_catalog_term(tag):
            raise ValueError("UNSAFE_CATALOG_CONTENT")
    if _check_forbidden_mapping(metadata):
        raise ValueError("UNSAFE_CATALOG_CONTENT")


def _coerce_metadata(value: Mapping[str, Any] | dict[str, Any] | None) -> Mapping[str, Any]:
    """Coerce a mapping into an immutable MappingProxyType."""
    if value is None:
        return MappingProxyType({})
    if isinstance(value, Mapping):
        return MappingProxyType(dict(value))
    raise ValueError("metadata must be a mapping")


@dataclass(frozen=True)
class CatalogConfig:
    """Configuration for catalog building."""

    catalog_version: str = CATALOG_VERSION
    stale_threshold_seconds: int = 86400  # 24 hours
    block_on_empty: bool = True
    block_on_duplicate_ids: bool = True
    block_on_unsafe_content: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.catalog_version, str) or not self.catalog_version:
            raise ValueError("catalog_version must be a non-empty string")
        if not isinstance(self.stale_threshold_seconds, int) or self.stale_threshold_seconds <= 0:
            raise ValueError("stale_threshold_seconds must be a positive integer")
        for attr in ("block_on_empty", "block_on_duplicate_ids", "block_on_unsafe_content"):
            if not isinstance(getattr(self, attr), bool):
                raise ValueError(f"{attr} must be a bool")


@dataclass(frozen=True)
class CatalogSafetyFlags:
    """Safety invariants for the catalog."""

    dry_run: bool = True
    live_trading_enabled: bool = False
    real_orders_enabled: bool = False
    leverage_enabled: bool = False
    shorting_enabled: bool = False

    report_feedback_into_execution: bool = False
    operator_feedback_into_execution: bool = False
    index_feedback_into_execution: bool = False
    search_feedback_into_execution: bool = False
    bundle_feedback_into_execution: bool = False
    chronicle_feedback_into_execution: bool = False
    digest_feedback_into_execution: bool = False
    quality_gate_feedback_into_execution: bool = False
    handoff_feedback_into_execution: bool = False
    archive_manifest_feedback_into_execution: bool = False
    release_notes_feedback_into_execution: bool = False
    catalog_feedback_into_execution: bool = False

    file_reference_traversal_enabled: bool = False
    database_persistence_enabled: bool = False
    web_ui_enabled: bool = False
    dashboard_enabled: bool = False
    runtime_registry_enabled: bool = False
    indexer_crawler_enabled: bool = False

    # Catalog output is human-audit only — these must be True
    catalog_output_is_human_audit_only: bool = True
    catalog_output_not_trading_signal: bool = True
    catalog_output_not_trade_approval: bool = True
    catalog_output_not_release_approval: bool = True
    catalog_output_not_deployment_approval: bool = True
    catalog_output_not_execution_approval: bool = True
    catalog_output_not_strategy_approval: bool = True
    catalog_output_not_transaction_permission: bool = True
    catalog_output_not_for_execution: bool = True
    catalog_output_not_for_strategy: bool = True
    catalog_output_not_for_freqtrade: bool = True
    catalog_output_not_for_order: bool = True
    catalog_output_not_for_exchange: bool = True

    file_refs_not_traversed: bool = True
    artifact_files_not_read: bool = True
    no_action_commands_emitted: bool = True

    def __post_init__(self) -> None:
        unsafe_flags = (
            self.live_trading_enabled,
            self.real_orders_enabled,
            self.leverage_enabled,
            self.shorting_enabled,
            self.report_feedback_into_execution,
            self.operator_feedback_into_execution,
            self.index_feedback_into_execution,
            self.search_feedback_into_execution,
            self.bundle_feedback_into_execution,
            self.chronicle_feedback_into_execution,
            self.digest_feedback_into_execution,
            self.quality_gate_feedback_into_execution,
            self.handoff_feedback_into_execution,
            self.archive_manifest_feedback_into_execution,
            self.release_notes_feedback_into_execution,
            self.catalog_feedback_into_execution,
            self.file_reference_traversal_enabled,
            self.database_persistence_enabled,
            self.web_ui_enabled,
            self.dashboard_enabled,
            self.runtime_registry_enabled,
            self.indexer_crawler_enabled,
        )
        if any(unsafe_flags):
            raise ValueError("unsafe catalog safety flags are enabled")
        safe_flags = (
            self.catalog_output_is_human_audit_only,
            self.catalog_output_not_trading_signal,
            self.catalog_output_not_trade_approval,
            self.catalog_output_not_release_approval,
            self.catalog_output_not_deployment_approval,
            self.catalog_output_not_execution_approval,
            self.catalog_output_not_strategy_approval,
            self.catalog_output_not_transaction_permission,
            self.catalog_output_not_for_execution,
            self.catalog_output_not_for_strategy,
            self.catalog_output_not_for_freqtrade,
            self.catalog_output_not_for_order,
            self.catalog_output_not_for_exchange,
            self.file_refs_not_traversed,
            self.artifact_files_not_read,
            self.no_action_commands_emitted,
        )
        if not all(safe_flags):
            raise ValueError("safe catalog output flags must be True")


@dataclass(frozen=True)
class CatalogEntry:
    """Catalog entry for a single research artifact."""

    entry_id: str                         # deterministic, derived from artifact_id + artifact_kind
    artifact_id: str                      # source artifact's own ID
    artifact_kind: CatalogArtifactKind    # which layer produced this artifact
    catalog_state: CatalogState           # READY / BLOCKED / UNKNOWN / DISABLED
    source_version: str                   # artifact format version (e.g. "1.0")
    generated_at: datetime                # when the source artifact was generated
    title: str = ""                       # human-readable label for browsing
    spec_reference: str = ""              # e.g. "SPEC-011"
    local_reference: str = ""             # opaque path string — never traversed
    reason_codes: tuple[str, ...] = ()    # from source artifact
    tags: tuple[str, ...] = ()           # from source artifact
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if not isinstance(self.entry_id, str) or not self.entry_id:
            raise ValueError("entry_id must be a non-empty string")
        if not isinstance(self.artifact_id, str) or not self.artifact_id:
            raise ValueError("artifact_id must be a non-empty string")
        if not isinstance(self.artifact_kind, CatalogArtifactKind):
            raise ValueError("artifact_kind must be CatalogArtifactKind")
        if not isinstance(self.catalog_state, CatalogState):
            raise ValueError("catalog_state must be CatalogState")
        if not isinstance(self.source_version, str) or not self.source_version:
            raise ValueError("source_version must be a non-empty string")
        _ensure_timezone_aware(self.generated_at, "generated_at")
        object.__setattr__(self, "reason_codes", _ensure_tuple_of_str(self.reason_codes, "reason_codes"))
        object.__setattr__(self, "tags", _ensure_tuple_of_str(self.tags, "tags"))
        object.__setattr__(self, "metadata", _coerce_metadata(self.metadata))
        # Forbidden content check on all text fields
        _check_forbidden_catalog_content((
            self.title, self.spec_reference, self.local_reference,
        ), self.tags, self.metadata)
        if self.catalog_state is not CatalogState.READY and not self.reason_codes:
            raise ValueError("reason_codes must be non-empty when catalog_state is not READY")

    @classmethod
    def blocked(
        cls,
        *,
        entry_id: str = "blocked",
        artifact_id: str = "blocked",
        artifact_kind: CatalogArtifactKind,
        reason_codes: tuple[str, ...] = (DEFAULT_BLOCKED,),
        generated_at: datetime | None = None,
    ) -> "CatalogEntry":
        """Create a blocked catalog entry for audit purposes only."""
        if generated_at is None:
            generated_at = datetime.now(timezone.utc)
        return cls(
            entry_id=entry_id,
            artifact_id=artifact_id,
            artifact_kind=artifact_kind,
            catalog_state=CatalogState.BLOCKED,
            source_version="blocked",
            generated_at=generated_at,
            reason_codes=reason_codes,
        )


@dataclass(frozen=True)
class CatalogSummary:
    """Aggregate counts across all catalog entries."""

    total_entries: int = 0
    ready_count: int = 0
    blocked_count: int = 0
    unknown_count: int = 0
    disabled_count: int = 0
    # Per-kind counts
    kind_counts: Mapping[CatalogArtifactKind, int] = field(default_factory=lambda: MappingProxyType({}))
    # Per-state counts (redundant with state fields above, but explicit for audit)
    reason_counts: Mapping[str, int] = field(default_factory=lambda: MappingProxyType({}))
    # Source layer coverage
    layers_covered: int = 0        # how many of 11 layers have >= 1 entry
    layers_missing: int = 0        # how many of 11 layers have 0 entries
    duplicate_id_count: int = 0    # entries with duplicate entry_id
    stale_entry_count: int = 0     # entries older than threshold

    def __post_init__(self) -> None:
        for attr in ("total_entries", "ready_count", "blocked_count", "unknown_count", "disabled_count"):
            value = getattr(self, attr)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{attr} must be a non-negative integer")
        state_sum = self.ready_count + self.blocked_count + self.unknown_count + self.disabled_count
        if state_sum > self.total_entries:
            raise ValueError("state counts must not exceed total_entries")
        for k, v in self.kind_counts.items():
            if not isinstance(k, CatalogArtifactKind):
                raise ValueError("kind_counts keys must be CatalogArtifactKind")
            if not isinstance(v, int) or v < 0:
                raise ValueError("kind_counts values must be non-negative integers")
        for k, v in self.reason_counts.items():
            if not isinstance(v, int) or v < 0:
                raise ValueError(f"reason_counts[{k}] must be a non-negative integer")
        if not isinstance(self.layers_covered, int) or self.layers_covered < 0:
            raise ValueError("layers_covered must be a non-negative integer")
        if not isinstance(self.layers_missing, int) or self.layers_missing < 0:
            raise ValueError("layers_missing must be a non-negative integer")
        if self.layers_covered + self.layers_missing != len(CatalogArtifactKind):
            raise ValueError("layers_covered + layers_missing must equal total layer count")
        if not isinstance(self.duplicate_id_count, int) or self.duplicate_id_count < 0:
            raise ValueError("duplicate_id_count must be a non-negative integer")
        if not isinstance(self.stale_entry_count, int) or self.stale_entry_count < 0:
            raise ValueError("stale_entry_count must be a non-negative integer")
        object.__setattr__(self, "kind_counts", MappingProxyType(dict(self.kind_counts)))
        object.__setattr__(self, "reason_counts", MappingProxyType(dict(self.reason_counts)))


@dataclass(frozen=True)
class CatalogDataQuality:
    """Completeness and quality metrics for the catalog."""

    total_artifacts: int = 0
    valid_entries: int = 0
    blocked_entries: int = 0
    stale_entries: int = 0
    duplicate_artifact_ids: tuple[str, ...] = ()    # entry_ids appearing more than once (blocking)
    cross_kind_overlap_ids: tuple[str, ...] = ()     # artifact_ids appearing across different kinds (advisory)
    missing_layer_kinds: tuple[str, ...] = ()        # CatalogArtifactKind values with zero entries
    covered_layer_kinds: tuple[str, ...] = ()         # CatalogArtifactKind values with >= 1 entry
    validation_errors: tuple[str, ...] = ()           # any validation errors encountered
    has_duplicates: bool = False                      # True if duplicate entry_ids exist
    has_cross_kind_overlap: bool = False              # True if cross-kind artifact_id overlap exists (advisory)
    has_missing_layers: bool = False
    has_stale_entries: bool = False

    def __post_init__(self) -> None:
        for attr in ("total_artifacts", "valid_entries", "blocked_entries", "stale_entries"):
            value = getattr(self, attr)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{attr} must be a non-negative integer")
        if self.valid_entries + self.blocked_entries > self.total_artifacts:
            raise ValueError("entry category counts must not exceed total_artifacts")
        object.__setattr__(self, "duplicate_artifact_ids", _ensure_tuple_of_str(self.duplicate_artifact_ids, "duplicate_artifact_ids"))
        object.__setattr__(self, "cross_kind_overlap_ids", _ensure_tuple_of_str(self.cross_kind_overlap_ids, "cross_kind_overlap_ids"))
        object.__setattr__(self, "missing_layer_kinds", _ensure_tuple_of_str(self.missing_layer_kinds, "missing_layer_kinds"))
        object.__setattr__(self, "covered_layer_kinds", _ensure_tuple_of_str(self.covered_layer_kinds, "covered_layer_kinds"))
        object.__setattr__(self, "validation_errors", _ensure_tuple_of_str(self.validation_errors, "validation_errors"))


@dataclass(frozen=True)
class ResearchCatalog:
    """Full catalog container with fail-closed blocked factory."""

    catalog_id: str                     # UUID or deterministic hash
    generated_at: datetime              # catalog generation timestamp
    catalog_state: CatalogState
    entries: tuple[CatalogEntry, ...]   # all catalog entries, deterministically ordered
    summary: CatalogSummary             # aggregated counts
    data_quality: CatalogDataQuality    # completeness metrics
    safety_flags: CatalogSafetyFlags    # safety invariants
    reason_codes: tuple[str, ...]       # all reason codes from catalog build
    version: str = CATALOG_VERSION     # catalog format version

    def __post_init__(self) -> None:
        if not isinstance(self.catalog_id, str) or not self.catalog_id:
            raise ValueError("catalog_id must be a non-empty string")
        _ensure_timezone_aware(self.generated_at, "generated_at")
        if not isinstance(self.catalog_state, CatalogState):
            raise ValueError("catalog_state must be CatalogState")
        if not isinstance(self.entries, tuple):
            raise ValueError("entries must be a tuple")
        for entry in self.entries:
            if not isinstance(entry, CatalogEntry):
                raise ValueError("entries must contain CatalogEntry values")
        if not isinstance(self.summary, CatalogSummary):
            raise ValueError("summary must be CatalogSummary")
        if not isinstance(self.data_quality, CatalogDataQuality):
            raise ValueError("data_quality must be CatalogDataQuality")
        if not isinstance(self.safety_flags, CatalogSafetyFlags):
            raise ValueError("safety_flags must be CatalogSafetyFlags")
        object.__setattr__(self, "reason_codes", _ensure_tuple_of_str(self.reason_codes, "reason_codes"))
        for code in self.reason_codes:
            if code not in CATALOG_REASON_CODES:
                raise ValueError(f"unsupported reason code: {code}")
        if self.catalog_state is not CatalogState.READY and not self.reason_codes:
            raise ValueError("reason_codes must be non-empty when catalog_state is not READY")
        if self.catalog_state is CatalogState.READY and self.reason_codes:
            raise ValueError("READY catalogs must not have reason_codes")

    @classmethod
    def blocked(
        cls,
        *,
        catalog_id: str = "blocked",
        generated_at: datetime | None = None,
        reason_code: str = DEFAULT_BLOCKED,
        safety_flags: CatalogSafetyFlags | None = None,
    ) -> "ResearchCatalog":
        """Create a deterministic fail-closed blocked catalog.

        Must not call ``CatalogSummary()`` with defaults — the
        ``layers_covered + layers_missing`` invariant requires the sum to
        equal ``len(CatalogArtifactKind)``. A blocked catalog has zero
        covered layers, so all 11 layers must be marked missing.
        """
        if reason_code not in CATALOG_REASON_CODES:
            raise ValueError(f"unsupported reason code: {reason_code}")
        if generated_at is None:
            generated_at = datetime.now(timezone.utc)
        if safety_flags is None:
            safety_flags = CatalogSafetyFlags()
        return cls(
            catalog_id=catalog_id,
            generated_at=generated_at,
            catalog_state=CatalogState.BLOCKED,
            entries=(),
            summary=CatalogSummary(
                layers_missing=len(CatalogArtifactKind),
            ),
            data_quality=CatalogDataQuality(),
            safety_flags=safety_flags,
            reason_codes=(reason_code,),
        )
