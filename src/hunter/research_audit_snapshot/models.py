"""Frozen dataclasses for hunter.research_audit_snapshot package.

MVP-23 — Local Research Audit Snapshot.

All dataclasses are frozen. Validation runs in __post_init__.
File references and metadata strings are local strings only and are never
traversed, opened, followed, validated, or executed.

The research audit snapshot is a human-audit / contractor-handoff artifact
only. It is not release approval, deployment approval, trading signal, trade
approval, execution approval, strategy approval, or transaction permission.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any

SNAPSHOT_VERSION = "1.0"


class AuditSnapshotState(Enum):
    """Overall state of the research audit snapshot."""

    CURRENT = "current"
    STALE = "stale"
    INCOMPLETE = "incomplete"
    BLOCK = "block"
    UNKNOWN = "unknown"


class AuditSnapshotKind(Enum):
    """Kind of audit snapshot."""

    RESEARCH_AUDIT_SNAPSHOT = "research_audit_snapshot"


class AuditSnapshotSectionKind(Enum):
    """Deterministic section ordering for the audit snapshot."""

    OVERVIEW = "overview"
    VERSION_STATE = "version_state"
    ARTIFACT_STATE = "artifact_state"
    QUALITY_STATE = "quality_state"
    OPEN_ITEMS = "open_items"
    SAFETY_BOUNDARIES = "safety_boundaries"
    HUMAN_AUDIT_GUIDE = "human_audit_guide"
    APPENDIX_REFERENCES = "appendix_references"


class AuditSnapshotItemSeverity(Enum):
    """Severity of an artifact state item or open item."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


# Deterministic canonical order for audit snapshot sections.
CANONICAL_AUDIT_SNAPSHOT_SECTION_ORDER: tuple[AuditSnapshotSectionKind, ...] = (
    AuditSnapshotSectionKind.OVERVIEW,
    AuditSnapshotSectionKind.VERSION_STATE,
    AuditSnapshotSectionKind.ARTIFACT_STATE,
    AuditSnapshotSectionKind.QUALITY_STATE,
    AuditSnapshotSectionKind.OPEN_ITEMS,
    AuditSnapshotSectionKind.SAFETY_BOUNDARIES,
    AuditSnapshotSectionKind.HUMAN_AUDIT_GUIDE,
    AuditSnapshotSectionKind.APPENDIX_REFERENCES,
)

# Deterministic severity priority for item ordering (lower = more severe).
# Keys are uppercase because AuditSnapshotItem.severity is normalized to uppercase.
_AUDIT_SNAPSHOT_ITEM_SEVERITY_PRIORITY: dict[str, int] = {
    AuditSnapshotItemSeverity.CRITICAL.name: 0,
    AuditSnapshotItemSeverity.HIGH.name: 1,
    AuditSnapshotItemSeverity.MEDIUM.name: 2,
    AuditSnapshotItemSeverity.LOW.name: 3,
    AuditSnapshotItemSeverity.INFO.name: 4,
}

# Reason codes — deterministic, priority-ordered constants.
UNSAFE_SNAPSHOT_CONTENT = "UNSAFE_SNAPSHOT_CONTENT"
INVALID_SNAPSHOT_CONFIG = "INVALID_SNAPSHOT_CONFIG"
MISSING_REQUIRED_SECTION = "MISSING_REQUIRED_SECTION"
MISSING_ARTIFACT_SUMMARIES = "MISSING_ARTIFACT_SUMMARIES"
BLOCKED_ARTIFACT_ITEM = "BLOCKED_ARTIFACT_ITEM"
STALE_ARTIFACT_DETECTED = "STALE_ARTIFACT_DETECTED"
OPEN_ITEMS_PRESENT = "OPEN_ITEMS_PRESENT"
INCOMPLETE_ARTIFACT_ITEM = "INCOMPLETE_ARTIFACT_ITEM"
UNKNOWN_SNAPSHOT_STATE = "UNKNOWN_SNAPSHOT_STATE"
FILE_REFS_NOT_TRAVERSED = "FILE_REFS_NOT_TRAVERSED"
ARTIFACT_FILES_NOT_READ = "ARTIFACT_FILES_NOT_READ"
NO_ACTION_COMMANDS_EMITTED = "NO_ACTION_COMMANDS_EMITTED"
HUMAN_AUDIT_GUIDE_NON_GATING = "HUMAN_AUDIT_GUIDE_NON_GATING"

AUDIT_SNAPSHOT_REASON_CODES: tuple[str, ...] = (
    UNSAFE_SNAPSHOT_CONTENT,
    INVALID_SNAPSHOT_CONFIG,
    MISSING_REQUIRED_SECTION,
    MISSING_ARTIFACT_SUMMARIES,
    BLOCKED_ARTIFACT_ITEM,
    STALE_ARTIFACT_DETECTED,
    OPEN_ITEMS_PRESENT,
    INCOMPLETE_ARTIFACT_ITEM,
    UNKNOWN_SNAPSHOT_STATE,
    FILE_REFS_NOT_TRAVERSED,
    ARTIFACT_FILES_NOT_READ,
    NO_ACTION_COMMANDS_EMITTED,
    HUMAN_AUDIT_GUIDE_NON_GATING,
)

# Reason codes that always produce BLOCK state.
AUDIT_SNAPSHOT_BLOCKING_REASON_CODES: tuple[str, ...] = (
    UNSAFE_SNAPSHOT_CONTENT,
    INVALID_SNAPSHOT_CONFIG,
    MISSING_REQUIRED_SECTION,
    MISSING_ARTIFACT_SUMMARIES,
    BLOCKED_ARTIFACT_ITEM,
)

# Reason codes that produce INCOMPLETE state unless block_on_incomplete=True.
AUDIT_SNAPSHOT_INCOMPLETE_REASON_CODES: tuple[str, ...] = (
    OPEN_ITEMS_PRESENT,
    INCOMPLETE_ARTIFACT_ITEM,
)

# Reason code that produces STALE state unless block_on_stale=True.
AUDIT_SNAPSHOT_STALE_REASON_CODES: tuple[str, ...] = (
    STALE_ARTIFACT_DETECTED,
)

# Advisory-only reason codes that do not affect snapshot state.
AUDIT_SNAPSHOT_ADVISORY_REASON_CODES: tuple[str, ...] = (
    FILE_REFS_NOT_TRAVERSED,
    ARTIFACT_FILES_NOT_READ,
    NO_ACTION_COMMANDS_EMITTED,
    HUMAN_AUDIT_GUIDE_NON_GATING,
)

# Superset of forbidden terms from prior MVPs plus release/deployment-approval
# and action-command keywords.
FORBIDDEN_SNAPSHOT_TERMS: frozenset[str] = frozenset({
    # Credential / secret terms
    "api_key",
    "apikey",
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
    "live trade",
    "real_order",
    "real order",
    "position_size",
    "execute_trade",
    "execute trade",
    "place_order",
    "place order",
    # Exchange / runtime terms
    "binance",
    # Release/deployment/execution readiness terms
    "go_live",
    "production_ready",
    "execution_ready",
    "strategy_ready",
    "deployment_ready",
    "release_ready",
    "launch_live",
    "release_approved",
    "deploy_now",
    # Approval terms (underscore and space forms)
    "release_approval",
    "release approval",
    "deployment_approval",
    "deployment approval",
    "execution_approval",
    "execution approval",
    "strategy_approval",
    "strategy approval",
    "trade_approval",
    "trade approval",
    "transaction_permission",
    "transaction permission",
    # Action-command keywords
    "deploy",
    "execute",
    "run",
    "start",
    "stop",
    "trigger",
    "submit",
    # Runtime infrastructure terms
    "register_service",
    "discover_artifacts",
    "index_files",
    "crawl_directory",
    "runtime_registry",
    "task_runner",
    "event_store",
    "routing_layer",
    "web_ui",
    "dashboard",
    "database_persistence",
})


def _ensure_timezone_aware(value: datetime, field_name: str) -> datetime:
    """Raise ValueError if value is a naive datetime (tzinfo is None)."""
    if not isinstance(value, datetime):
        raise ValueError(f"{field_name} must be a datetime")
    if value.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value


def _ensure_tuple_of_str(
    value: Iterable[str] | tuple[str, ...] | list[str] | None,
    field_name: str,
) -> tuple[str, ...]:
    """Validate that value is a tuple/list of non-empty strings."""
    if value is None:
        return ()
    if isinstance(value, (tuple, list)):
        for item in value:
            if not isinstance(item, str) or not item:
                raise ValueError(f"{field_name} must contain non-empty strings")
        return tuple(value)
    raise ValueError(f"{field_name} must be a tuple or list of strings")


def _has_forbidden_snapshot_term(text: str) -> bool:
    """Case-insensitive check for forbidden terms in a single string."""
    if not isinstance(text, str):
        return False
    lower = text.lower()
    for term in FORBIDDEN_SNAPSHOT_TERMS:
        if term in lower:
            return True
    return False


def _check_forbidden_mapping(mapping: Mapping[str, Any]) -> bool:
    """Return True if any key or string value in mapping contains forbidden terms."""
    for key, value in mapping.items():
        if isinstance(key, str) and _has_forbidden_snapshot_term(key):
            return True
        if isinstance(value, str) and _has_forbidden_snapshot_term(value):
            return True
        if isinstance(value, (tuple, list)):
            for item in value:
                if isinstance(item, str) and _has_forbidden_snapshot_term(item):
                    return True
        if isinstance(value, Mapping):
            if _check_forbidden_mapping(value):
                return True
    return False


def _check_forbidden_snapshot_content(
    text_fields: tuple[str, ...],
    string_sequences: tuple[str, ...],
    metadata: Mapping[str, Any],
) -> None:
    """Raise ValueError('UNSAFE_SNAPSHOT_CONTENT') if forbidden terms found."""
    for text in text_fields:
        if _has_forbidden_snapshot_term(text):
            raise ValueError("UNSAFE_SNAPSHOT_CONTENT")
    for seq in string_sequences:
        if _has_forbidden_snapshot_term(seq):
            raise ValueError("UNSAFE_SNAPSHOT_CONTENT")
    if _check_forbidden_mapping(metadata):
        raise ValueError("UNSAFE_SNAPSHOT_CONTENT")


def _coerce_metadata(value: Mapping[str, Any] | dict[str, Any] | None) -> Mapping[str, Any]:
    """Coerce a mapping into an immutable MappingProxyType."""
    if value is None:
        return MappingProxyType({})
    if isinstance(value, Mapping):
        return MappingProxyType(dict(value))
    raise ValueError("metadata must be a mapping")


def _extract_mvp_number(related_mvp: str) -> int:
    """Extract trailing integer from strings like 'MVP-23'.

    Returns a large sentinel value for empty or unparseable strings so they
    sort last in deterministic item ordering.
    """
    if not isinstance(related_mvp, str) or not related_mvp:
        return 1_000_000
    digits = "".join(ch for ch in related_mvp if ch.isdigit())
    if not digits:
        return 1_000_000
    return int(digits)


def _order_items(items: Iterable[AuditSnapshotItem]) -> tuple[AuditSnapshotItem, ...]:
    """Order items by (severity_priority, mvp_number, insertion_order)."""
    enumerated = list(enumerate(items))
    enumerated.sort(key=lambda item: (
        _AUDIT_SNAPSHOT_ITEM_SEVERITY_PRIORITY.get(item[1].severity, 999),
        _extract_mvp_number(item[1].related_mvp),
        item[0],
    ))
    return tuple(item[1] for item in enumerated)


@dataclass(frozen=True)
class AuditSnapshotConfig:
    """Configuration for audit snapshot building."""

    version: str = SNAPSHOT_VERSION
    generated_at: datetime | None = None
    output_format: str = "both"
    dry_run: bool = True
    live_trading_enabled: bool = False
    real_orders_enabled: bool = False
    leverage_enabled: bool = False
    shorting_enabled: bool = False
    block_on_unknown: bool = True
    block_on_incomplete: bool = False
    block_on_stale: bool = False
    freshness_threshold_seconds: int = 86400
    expected_artifact_count: int = 13
    required_sections: tuple[AuditSnapshotSectionKind, ...] = (
        AuditSnapshotSectionKind.OVERVIEW,
        AuditSnapshotSectionKind.VERSION_STATE,
        AuditSnapshotSectionKind.ARTIFACT_STATE,
        AuditSnapshotSectionKind.QUALITY_STATE,
        AuditSnapshotSectionKind.OPEN_ITEMS,
        AuditSnapshotSectionKind.SAFETY_BOUNDARIES,
        AuditSnapshotSectionKind.HUMAN_AUDIT_GUIDE,
        AuditSnapshotSectionKind.APPENDIX_REFERENCES,
    )
    include_snapshot_narrative: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.version, str) or not self.version:
            raise ValueError("version must be a non-empty string")
        if self.output_format not in ("json", "markdown", "both"):
            raise ValueError("output_format must be json, markdown, or both")
        if not self.dry_run:
            raise ValueError("dry_run must be True")
        if any((
            self.live_trading_enabled,
            self.real_orders_enabled,
            self.leverage_enabled,
            self.shorting_enabled,
        )):
            raise ValueError("live trading flags must be False")
        if not isinstance(self.block_on_unknown, bool):
            raise ValueError("block_on_unknown must be a bool")
        if not isinstance(self.block_on_incomplete, bool):
            raise ValueError("block_on_incomplete must be a bool")
        if not isinstance(self.block_on_stale, bool):
            raise ValueError("block_on_stale must be a bool")
        if not isinstance(self.freshness_threshold_seconds, int) or self.freshness_threshold_seconds < 0:
            raise ValueError("freshness_threshold_seconds must be a non-negative integer")
        if not isinstance(self.expected_artifact_count, int) or self.expected_artifact_count < 0:
            raise ValueError("expected_artifact_count must be a non-negative integer")
        if not all(isinstance(s, AuditSnapshotSectionKind) for s in self.required_sections):
            raise ValueError("required_sections must be AuditSnapshotSectionKind values")


@dataclass(frozen=True)
class AuditSnapshotSafetyFlags:
    """Safety invariants for the audit snapshot."""

    # Runtime safety flags
    dry_run: bool = True
    live_trading_enabled: bool = False
    real_orders_enabled: bool = False
    leverage_enabled: bool = False
    shorting_enabled: bool = False

    # Output safety flags
    snapshot_output_is_human_audit_only: bool = True
    snapshot_output_not_trading_signal: bool = True
    snapshot_output_not_trade_approval: bool = True
    snapshot_output_not_execution_readiness: bool = True
    snapshot_output_not_strategy_readiness: bool = True
    snapshot_output_not_release_approval: bool = True
    snapshot_output_not_deployment_approval: bool = True
    snapshot_output_not_transaction_permission: bool = True
    snapshot_output_not_for_execution: bool = True
    snapshot_output_not_for_strategy: bool = True
    snapshot_output_not_for_freqtrade: bool = True
    snapshot_output_not_for_order: bool = True
    snapshot_output_not_for_exchange: bool = True

    # Feedback safety flags
    snapshot_feedback_into_execution: bool = False
    cross_layer_feedback_into_execution: bool = False

    # Capability flags
    file_reference_traversal_enabled: bool = False
    database_persistence_enabled: bool = False
    web_ui_enabled: bool = False
    dashboard_enabled: bool = False
    runtime_registry_enabled: bool = False
    indexer_crawler_enabled: bool = False
    event_store_enabled: bool = False
    task_runner_enabled: bool = False

    # Advisory flags
    file_refs_not_traversed: bool = True
    artifact_files_not_read: bool = True
    no_action_commands_emitted: bool = True
    human_audit_guide_is_non_gating: bool = True

    def __post_init__(self) -> None:
        unsafe_flags = (
            self.live_trading_enabled,
            self.real_orders_enabled,
            self.leverage_enabled,
            self.shorting_enabled,
            self.snapshot_feedback_into_execution,
            self.cross_layer_feedback_into_execution,
            self.file_reference_traversal_enabled,
            self.database_persistence_enabled,
            self.web_ui_enabled,
            self.dashboard_enabled,
            self.runtime_registry_enabled,
            self.indexer_crawler_enabled,
            self.event_store_enabled,
            self.task_runner_enabled,
        )
        if any(unsafe_flags):
            raise ValueError("unsafe audit snapshot safety flags are enabled")
        safe_flags = (
            self.snapshot_output_is_human_audit_only,
            self.snapshot_output_not_trading_signal,
            self.snapshot_output_not_trade_approval,
            self.snapshot_output_not_execution_readiness,
            self.snapshot_output_not_strategy_readiness,
            self.snapshot_output_not_release_approval,
            self.snapshot_output_not_deployment_approval,
            self.snapshot_output_not_transaction_permission,
            self.snapshot_output_not_for_execution,
            self.snapshot_output_not_for_strategy,
            self.snapshot_output_not_for_freqtrade,
            self.snapshot_output_not_for_order,
            self.snapshot_output_not_for_exchange,
            self.file_refs_not_traversed,
            self.artifact_files_not_read,
            self.no_action_commands_emitted,
            self.human_audit_guide_is_non_gating,
        )
        if not all(safe_flags):
            raise ValueError("safe audit snapshot output flags must be True")


@dataclass(frozen=True)
class AuditSnapshotItem:
    """One artifact state entry in the audit snapshot."""

    item_id: str
    title: str
    artifact_kind: str = ""
    state: str = "UNKNOWN"
    severity: str = "INFO"
    related_mvp: str = ""
    spec_reference: str = ""
    local_reference: str = ""
    generated_at: datetime | None = None
    reason_codes: tuple[str, ...] = ()
    tags: tuple[str, ...] = field(default_factory=tuple)
    related_references: tuple[str, ...] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if not isinstance(self.item_id, str) or not self.item_id:
            raise ValueError("item_id must be a non-empty string")
        if not isinstance(self.title, str) or not self.title:
            raise ValueError("title must be a non-empty string")
        if not isinstance(self.artifact_kind, str):
            raise ValueError("artifact_kind must be a string")
        if not isinstance(self.state, str) or not self.state:
            raise ValueError("state must be a non-empty string")
        severity_upper = self.severity.upper()
        if severity_upper not in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"):
            raise ValueError(f"unsupported severity: {self.severity}")
        object.__setattr__(self, "severity", severity_upper)
        object.__setattr__(self, "reason_codes", _ensure_tuple_of_str(self.reason_codes, "reason_codes"))
        object.__setattr__(self, "tags", _ensure_tuple_of_str(self.tags, "tags"))
        object.__setattr__(
            self, "related_references", _ensure_tuple_of_str(self.related_references, "related_references")
        )
        object.__setattr__(self, "metadata", _coerce_metadata(self.metadata))
        for code in self.reason_codes:
            if code not in AUDIT_SNAPSHOT_REASON_CODES:
                raise ValueError(f"unsupported reason code: {code}")
        _check_forbidden_snapshot_content(
            (self.title, self.artifact_kind, self.state, self.spec_reference),
            self.related_references,
            self.metadata,
        )


@dataclass(frozen=True)
class AuditSnapshotSection:
    """One section of the audit snapshot."""

    section_kind: AuditSnapshotSectionKind
    title: str
    section_notes: str = ""
    items: tuple[AuditSnapshotItem, ...] = field(default_factory=tuple)
    references: tuple[str, ...] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if not isinstance(self.section_kind, AuditSnapshotSectionKind):
            raise ValueError("section_kind must be AuditSnapshotSectionKind")
        if not isinstance(self.title, str) or not self.title:
            raise ValueError("title must be a non-empty string")
        object.__setattr__(self, "references", _ensure_tuple_of_str(self.references, "references"))
        object.__setattr__(self, "metadata", _coerce_metadata(self.metadata))
        _check_forbidden_snapshot_content(
            (self.title, self.section_notes),
            self.references,
            self.metadata,
        )
        if not isinstance(self.items, tuple):
            raise ValueError("items must be a tuple")
        for item in self.items:
            if not isinstance(item, AuditSnapshotItem):
                raise ValueError("items must contain AuditSnapshotItem values")
        object.__setattr__(self, "items", _order_items(self.items))


@dataclass(frozen=True)
class AuditSnapshotSummary:
    """Aggregated counts and snapshot narrative."""

    total_sections: int = 0
    total_items: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    info_count: int = 0
    current_count: int = 0
    stale_count: int = 0
    incomplete_count: int = 0
    blocked_count: int = 0
    unknown_count: int = 0
    open_item_count: int = 0
    snapshot_state: str = "UNKNOWN"
    reason_code_counts: Mapping[str, int] = field(default_factory=lambda: MappingProxyType({}))
    snapshot_narrative: str = ""

    def __post_init__(self) -> None:
        for field_name in (
            "total_sections", "total_items", "critical_count", "high_count",
            "medium_count", "low_count", "info_count", "current_count",
            "stale_count", "incomplete_count", "blocked_count", "unknown_count",
            "open_item_count",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer")
        severity_sum = (
            self.critical_count + self.high_count + self.medium_count +
            self.low_count + self.info_count
        )
        if severity_sum != self.total_items:
            raise ValueError("severity counts must sum to total_items")
        state_sum = (
            self.current_count + self.stale_count + self.incomplete_count +
            self.blocked_count + self.unknown_count
        )
        if state_sum != self.total_items:
            raise ValueError("state counts must sum to total_items")
        if self.snapshot_state not in ("CURRENT", "STALE", "INCOMPLETE", "BLOCK", "UNKNOWN"):
            raise ValueError("snapshot_state must be CURRENT, STALE, INCOMPLETE, BLOCK, or UNKNOWN")
        _check_forbidden_snapshot_content((self.snapshot_narrative,), (), dict(self.reason_code_counts))
        object.__setattr__(self, "reason_code_counts", MappingProxyType(dict(self.reason_code_counts)))


@dataclass(frozen=True)
class AuditSnapshotDataQuality:
    """Completeness and quality metrics for the audit snapshot."""

    total_artifacts_expected: int = 13  # MVP-10 through MVP-22
    total_artifacts_present: int = 0
    total_artifacts_missing: int = 13  # fail-closed default: all expected artifacts missing
    stale_artifact_count: int = 0
    open_item_count: int = 0
    blocked_item_count: int = 0
    unknown_item_count: int = 0
    incomplete_item_count: int = 0
    sections_expected: int = 8
    sections_present: int = 0
    sections_missing: int = 8  # fail-closed default: all eight sections missing
    reason_codes: tuple[str, ...] = ()
    quality_narrative: str = ""

    def __post_init__(self) -> None:
        for field_name in (
            "total_artifacts_expected", "total_artifacts_present",
            "total_artifacts_missing", "stale_artifact_count", "open_item_count",
            "blocked_item_count", "unknown_item_count", "incomplete_item_count",
            "sections_expected", "sections_present", "sections_missing",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer")
        if self.total_artifacts_present + self.total_artifacts_missing != self.total_artifacts_expected:
            raise ValueError("present + missing must equal expected")
        if self.sections_present + self.sections_missing != self.sections_expected:
            raise ValueError("sections_present + sections_missing must equal sections_expected")
        object.__setattr__(self, "reason_codes", _ensure_tuple_of_str(self.reason_codes, "reason_codes"))
        for code in self.reason_codes:
            if code not in AUDIT_SNAPSHOT_REASON_CODES:
                raise ValueError(f"unsupported reason code: {code}")
        _check_forbidden_snapshot_content((self.quality_narrative,), (), {})


@dataclass(frozen=True)
class ResearchAuditSnapshot:
    """Full deterministic point-in-time audit snapshot."""

    snapshot_id: str  # required positional: no default allowed
    kind: AuditSnapshotKind = AuditSnapshotKind.RESEARCH_AUDIT_SNAPSHOT
    config: AuditSnapshotConfig = field(default_factory=AuditSnapshotConfig)
    safety_flags: AuditSnapshotSafetyFlags = field(default_factory=AuditSnapshotSafetyFlags)
    sections: tuple[AuditSnapshotSection, ...] = field(default_factory=tuple)
    summary: AuditSnapshotSummary = field(default_factory=AuditSnapshotSummary)
    data_quality: AuditSnapshotDataQuality = field(default_factory=AuditSnapshotDataQuality)
    generated_at: datetime | None = None
    project_version: str = "0.23.0-dev"
    source_spec: str = "SPEC-024"
    reason_codes: tuple[str, ...] = field(
        default_factory=lambda: (UNKNOWN_SNAPSHOT_STATE,)
    )
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.snapshot_id, str) or not self.snapshot_id:
            raise ValueError("snapshot_id must be a non-empty string")
        if not isinstance(self.kind, AuditSnapshotKind):
            raise ValueError("kind must be AuditSnapshotKind")
        if not isinstance(self.config, AuditSnapshotConfig):
            raise ValueError("config must be AuditSnapshotConfig")
        if not isinstance(self.safety_flags, AuditSnapshotSafetyFlags):
            raise ValueError("safety_flags must be AuditSnapshotSafetyFlags")
        if not isinstance(self.sections, tuple):
            raise ValueError("sections must be a tuple")
        for section in self.sections:
            if not isinstance(section, AuditSnapshotSection):
                raise ValueError("sections must contain AuditSnapshotSection values")
        if not isinstance(self.summary, AuditSnapshotSummary):
            raise ValueError("summary must be AuditSnapshotSummary")
        if not isinstance(self.data_quality, AuditSnapshotDataQuality):
            raise ValueError("data_quality must be AuditSnapshotDataQuality")
        if self.generated_at is not None:
            _ensure_timezone_aware(self.generated_at, "generated_at")
        if not isinstance(self.project_version, str) or not self.project_version:
            raise ValueError("project_version must be a non-empty string")
        if not isinstance(self.source_spec, str) or not self.source_spec:
            raise ValueError("source_spec must be a non-empty string")
        object.__setattr__(self, "reason_codes", _ensure_tuple_of_str(self.reason_codes, "reason_codes"))
        for code in self.reason_codes:
            if code not in AUDIT_SNAPSHOT_REASON_CODES:
                raise ValueError(f"unsupported reason code: {code}")
        if self.summary.snapshot_state in ("BLOCK", "UNKNOWN") and not self.reason_codes:
            raise ValueError("reason_codes must be non-empty when snapshot_state is BLOCK or UNKNOWN")
        object.__setattr__(self, "metadata", _coerce_metadata(self.metadata))
        _check_forbidden_snapshot_content((self.snapshot_id, self.project_version, self.source_spec), (), self.metadata)

    @classmethod
    def blocked(
        cls,
        *,
        reason_code: str,
        snapshot_id: str = "blocked",
        generated_at: datetime | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> "ResearchAuditSnapshot":
        """Create a deterministic fail-closed blocked audit snapshot.

        Does not read files, traverse references, or emit action commands.
        Constructs its own valid summary and data-quality objects so that
        no model is instantiated with invalid default values.
        """
        if reason_code not in AUDIT_SNAPSHOT_REASON_CODES:
            raise ValueError(f"unsupported reason code: {reason_code}")
        if generated_at is None:
            generated_at = datetime.now(timezone.utc)
        safe_metadata: Mapping[str, Any]
        if metadata is None:
            safe_metadata = MappingProxyType({"blocked_reason": reason_code})
        elif _check_forbidden_mapping(metadata):
            safe_metadata = MappingProxyType({"blocked_reason": reason_code})
        else:
            safe_metadata = metadata
        return cls(
            snapshot_id=snapshot_id,
            kind=AuditSnapshotKind.RESEARCH_AUDIT_SNAPSHOT,
            config=AuditSnapshotConfig(),
            safety_flags=AuditSnapshotSafetyFlags(),
            sections=(),
            summary=AuditSnapshotSummary(
                total_sections=0,
                snapshot_state=AuditSnapshotState.BLOCK.value.upper(),
                reason_code_counts={reason_code: 1},
            ),
            data_quality=AuditSnapshotDataQuality(
                total_artifacts_expected=13,
                total_artifacts_present=0,
                total_artifacts_missing=13,
                sections_expected=8,
                sections_present=0,
                sections_missing=8,
            ),
            generated_at=generated_at,
            project_version="0.23.0-dev",
            source_spec="SPEC-024",
            reason_codes=(reason_code,),
            metadata=safe_metadata,
        )
