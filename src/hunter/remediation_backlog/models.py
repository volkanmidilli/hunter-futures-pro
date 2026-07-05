"""Frozen dataclasses for hunter.remediation_backlog package.

MVP-37 — Local Research Remediation Backlog Planner.

All dataclasses are frozen. Validation runs in __post_init__. The planner only
accepts caller-provided in-memory declarations and references. It never opens,
follows, traverses, validates, fetches, or executes file references, report
references, or metadata strings. Actual artifact paths, section references,
finding references, and metadata are provided by the caller or a trusted test
harness; the engine never scans the filesystem, imports arbitrary modules, or
introspects the repository.

The remediation backlog is a human-audit / research artifact only. It is not a
production certification, not a trading readiness assessment, not a suitability
assessment, and not a trading signal or recommendation. It never emits
executable remediation actions, shell commands, code patches, or infrastructure
changes.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any

REMEDIATION_BACKLOG_VERSION: str = "0.37.0-dev"


class RemediationBacklogState(Enum):
    """Aggregate state of a remediation backlog report."""

    OK = "ok"
    DEGRADED = "degraded"
    BLOCKED = "blocked"
    NOT_APPLICABLE = "not_applicable"


class RemediationBacklogSeverity(Enum):
    """Severity of a backlog item."""

    BLOCKING = "blocking"
    ADVISORY = "advisory"
    INFO = "info"


class RemediationBacklogPriority(Enum):
    """Priority for human review ordering only."""

    P0 = "p0"
    P1 = "p1"
    P2 = "p2"
    P3 = "p3"
    NONE = "none"


class RemediationBacklogItemState(Enum):
    """State of a single remediation backlog item."""

    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    BLOCKED = "blocked"
    DEFERRED = "deferred"
    DUPLICATE = "duplicate"
    CONFLICTING = "conflicting"
    NOT_APPLICABLE = "not_applicable"


class RemediationBacklogItemType(Enum):
    """Type of backlog item / engine-generated issue."""

    MANUAL_REVIEW = "manual_review"
    MISSING_REF = "missing_ref"
    STALE_REF = "stale_ref"
    ORPHAN_REF = "orphan_ref"
    CONFLICTING_STATE = "conflicting_state"
    INCOMPATIBLE_VERSION = "incompatible_version"
    INCOMPATIBLE_STATE = "incompatible_state"
    UNSAFE_CONTENT = "unsafe_content"
    DUPLICATE_ITEM = "duplicate_item"
    DUPLICATE_ID = "duplicate_id"
    DEPENDENCY_CYCLE = "dependency_cycle"
    MISSING_OWNER = "missing_owner"
    MISSING_REVIEWER = "missing_reviewer"
    MISSING_MANUAL_REVIEW = "missing_manual_review"
    REQUIRED_SOURCE = "required_source"
    UNKNOWN_STATE = "unknown_state"
    ACKNOWLEDGED_ITEM = "acknowledged_item"


class RemediationBacklogReasonCode(Enum):
    """Reason codes for remediation backlog results and reports."""

    OK = "ok"
    NOT_APPLICABLE = "not_applicable"
    CONSISTENCY_DEGRADED = "consistency_degraded"
    SAFETY_BLOCKED = "safety_blocked"
    UNSAFE_CONTENT = "unsafe_content"
    FORBIDDEN_TERM_PRESENT = "forbidden_term_present"
    MISSING_REQUIRED_SOURCE = "missing_required_source"
    ORPHAN_FINDING_REF = "orphan_finding_ref"
    ORPHAN_DEPENDENCY = "orphan_dependency"
    DEPENDENCY_CYCLE = "dependency_cycle"
    CONFLICTING_ITEM_STATE = "conflicting_item_state"
    DUPLICATE_ID = "duplicate_id"
    DUPLICATE_ITEM = "duplicate_item"
    STALE_SOURCE_REF = "stale_source_ref"
    STALE_FINDING_REF = "stale_finding_ref"
    MISSING_OWNER = "missing_owner"
    MISSING_REVIEWER = "missing_reviewer"
    MISSING_MANUAL_REVIEW = "missing_manual_review"
    ACKNOWLEDGED_ITEM = "acknowledged_item"


# String constants for convenient use in reason code tuples and frozensets.
OK = RemediationBacklogReasonCode.OK.value
NOT_APPLICABLE_RC = RemediationBacklogReasonCode.NOT_APPLICABLE.value
CONSISTENCY_DEGRADED = RemediationBacklogReasonCode.CONSISTENCY_DEGRADED.value
SAFETY_BLOCKED = RemediationBacklogReasonCode.SAFETY_BLOCKED.value
UNSAFE_CONTENT = RemediationBacklogReasonCode.UNSAFE_CONTENT.value
FORBIDDEN_TERM_PRESENT = RemediationBacklogReasonCode.FORBIDDEN_TERM_PRESENT.value
MISSING_REQUIRED_SOURCE = RemediationBacklogReasonCode.MISSING_REQUIRED_SOURCE.value
ORPHAN_FINDING_REF = RemediationBacklogReasonCode.ORPHAN_FINDING_REF.value
ORPHAN_DEPENDENCY = RemediationBacklogReasonCode.ORPHAN_DEPENDENCY.value
DEPENDENCY_CYCLE = RemediationBacklogReasonCode.DEPENDENCY_CYCLE.value
CONFLICTING_ITEM_STATE = RemediationBacklogReasonCode.CONFLICTING_ITEM_STATE.value
DUPLICATE_ID = RemediationBacklogReasonCode.DUPLICATE_ID.value
DUPLICATE_ITEM = RemediationBacklogReasonCode.DUPLICATE_ITEM.value
STALE_SOURCE_REF = RemediationBacklogReasonCode.STALE_SOURCE_REF.value
STALE_FINDING_REF = RemediationBacklogReasonCode.STALE_FINDING_REF.value
MISSING_OWNER = RemediationBacklogReasonCode.MISSING_OWNER.value
MISSING_REVIEWER = RemediationBacklogReasonCode.MISSING_REVIEWER.value
MISSING_MANUAL_REVIEW = RemediationBacklogReasonCode.MISSING_MANUAL_REVIEW.value
ACKNOWLEDGED_ITEM = RemediationBacklogReasonCode.ACKNOWLEDGED_ITEM.value


class RemediationDependencyType(Enum):
    """Relationship between two backlog items."""

    BLOCKS = "blocks"
    DEPENDS_ON = "depends_on"
    RELATED_TO = "related_to"


# Forbidden-term matcher uses case-insensitive substring search against
# caller-provided metadata and all textual fields in refs/items/dependencies.
# All entries MUST be multi-word phrases. Single-word terms are intentionally
# excluded because they produce false positives in benign audit text (e.g.
# "pending approval from security team", "certification body", "no recommendation
# needed", "signal processing", "no signal detected"). Phrases that express an
# unsafe intent are included instead.
FORBIDDEN_REMEDIATION_BACKLOG_TERMS: frozenset[str] = frozenset({
    "actionable recommendation",
    "actionable signal",
    "approved for production",
    "approved for release",
    "approved for trading",
    "automated remediation",
    "auto fix",
    "auto patch",
    "buy now",
    "buy signal",
    "certified for production",
    "certified for trading",
    "deploy immediately",
    "deploy now",
    "execute orders",
    "execute remediation",
    "go long",
    "go short",
    "hold signal",
    "investment recommendation",
    "investment suitability",
    "live trade",
    "live trading",
    "place orders",
    "production certification",
    "production ready",
    "production readiness",
    "sell now",
    "sell signal",
    "suitable for production",
    "suitable for trading",
    "trade recommendation",
    "trade signal",
    "trading certification",
    "trading ready",
    "trading readiness",
    "trading suitability",
})


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _ensure_non_empty_str(value: Any, field_name: str) -> str:
    """Validate that value is a non-empty string."""
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _ensure_str(value: Any, field_name: str) -> str:
    """Validate that value is a string."""
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    return value


def _ensure_str_or_none(value: Any | None, field_name: str) -> str | None:
    """Validate that value is a non-empty string or None."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string or None")
    if not value:
        return None
    return value


def _ensure_str_with_default(value: Any | None, field_name: str) -> str:
    """Validate that value is a string, returning empty string if None."""
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    return value


def _ensure_tuple_of_str(value: Any, field_name: str) -> tuple[str, ...]:
    """Validate and return a tuple of strings."""
    if value is None:
        return ()
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
        raise ValueError(f"{field_name} must be iterable of strings")
    result = tuple(str(item) for item in value)
    return result


def _ensure_tuple_of_items(
    value: Any,
    cls: type,
    field_name: str,
) -> tuple[Any, ...]:
    """Validate and return a tuple of model objects."""
    if value is None:
        return ()
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
        raise ValueError(f"{field_name} must be iterable of {cls.__name__} objects")
    result = tuple(value)
    for item in result:
        if not isinstance(item, cls):
            raise ValueError(f"{field_name} must contain {cls.__name__} objects")
    return result


def _coerce_str_mapping(value: Mapping[str, Any] | dict[str, Any] | None) -> Mapping[str, Any]:
    """Coerce a mapping into an immutable MappingProxyType.

    Values are not validated as strings here so the engine can detect unsafe
    content; keys must be strings for deterministic iteration.
    """
    if value is None:
        return MappingProxyType({})
    if isinstance(value, Mapping):
        for key in value.keys():
            if not isinstance(key, str):
                raise ValueError("metadata keys must be strings")
        return MappingProxyType(dict(value))
    raise ValueError("metadata must be a mapping")


def _ensure_timezone_aware(value: datetime | None, field_name: str) -> None:
    """Validate that datetime is timezone-aware if not None."""
    if value is not None and value.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware if provided")


def _ensure_non_negative_int(value: Any, field_name: str) -> None:
    """Validate that value is a non-negative integer."""
    if not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")


# ---------------------------------------------------------------------------
# Safety helpers
# ---------------------------------------------------------------------------


def _has_forbidden_term(text: str, forbidden_terms: frozenset[str]) -> bool:
    """Case-insensitive substring check for forbidden terms in a single string."""
    if not isinstance(text, str):
        return False
    lower = text.lower()
    return any(term in lower for term in forbidden_terms)


def _check_forbidden_mapping(
    mapping: Mapping[str, Any], forbidden_terms: frozenset[str]
) -> bool:
    """Return True if any key or string value in mapping contains forbidden terms."""
    for key, value in mapping.items():
        if isinstance(key, str) and _has_forbidden_term(key, forbidden_terms):
            return True
        if isinstance(value, str) and _has_forbidden_term(value, forbidden_terms):
            return True
        if isinstance(value, (tuple, list)):
            for item in value:
                if isinstance(item, str) and _has_forbidden_term(item, forbidden_terms):
                    return True
        if isinstance(value, Mapping):
            if _check_forbidden_mapping(value, forbidden_terms):
                return True
    return False


def has_unsafe_remediation_backlog_content(value: Any) -> bool:
    """Return True if value is not a safe string type (bytes, object, int, etc.)."""
    if value is None:
        return False
    if isinstance(value, str):
        return False
    if isinstance(value, (tuple, list)):
        return any(has_unsafe_remediation_backlog_content(item) for item in value)
    if isinstance(value, Mapping):
        return any(
            has_unsafe_remediation_backlog_content(k)
            or has_unsafe_remediation_backlog_content(v)
            for k, v in value.items()
        )
    return True


# ---------------------------------------------------------------------------
# Safety flags
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RemediationBacklogSafetyFlags:
    """Safety flags confirming the planner stays within local audit boundaries."""

    no_executable_actions: bool = True
    no_trading_instructions: bool = True
    no_approval_claims: bool = True
    no_automated_remediation: bool = True
    references_opaque: bool = True
    has_unsafe_content: bool = False
    has_forbidden_terms: bool = False
    feedback_into_execution: bool = False

    def __post_init__(self) -> None:
        positive_flags = (
            self.no_executable_actions,
            self.no_trading_instructions,
            self.no_approval_claims,
            self.no_automated_remediation,
            self.references_opaque,
        )
        if not all(positive_flags):
            raise ValueError("baseline safety invariants must be True")

    @property
    def is_safe(self) -> bool:
        """True when the report passes all safety boundary checks."""
        return (
            not self.has_unsafe_content
            and not self.has_forbidden_terms
            and not self.feedback_into_execution
        )


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RemediationBacklogConfig:
    """Configuration for the remediation backlog planner."""

    strict: bool = False
    require_owner: bool = False
    require_reviewer: bool = False
    require_manual_review: bool = False
    staleness_threshold_seconds: int = 86400
    allowed_item_states: tuple[str, ...] = ()
    required_source_ids: tuple[str, ...] = ()
    default_json_path: str = "data/remediation_backlog/remediation_backlog.json"
    default_csv_path: str = "data/remediation_backlog/remediation_backlog_items.csv"
    default_markdown_path: str = "reports/remediation_backlog/remediation_backlog.md"

    def __post_init__(self) -> None:
        if not isinstance(self.strict, bool):
            raise ValueError("strict must be a bool")
        if not isinstance(self.require_owner, bool):
            raise ValueError("require_owner must be a bool")
        if not isinstance(self.require_reviewer, bool):
            raise ValueError("require_reviewer must be a bool")
        if not isinstance(self.require_manual_review, bool):
            raise ValueError("require_manual_review must be a bool")
        _ensure_non_negative_int(self.staleness_threshold_seconds, "staleness_threshold_seconds")
        object.__setattr__(self, "allowed_item_states", _ensure_tuple_of_str(self.allowed_item_states, "allowed_item_states"))
        object.__setattr__(self, "required_source_ids", _ensure_tuple_of_str(self.required_source_ids, "required_source_ids"))
        _ensure_non_empty_str(self.default_json_path, "default_json_path")
        _ensure_non_empty_str(self.default_csv_path, "default_csv_path")
        _ensure_non_empty_str(self.default_markdown_path, "default_markdown_path")


@dataclass(frozen=True, slots=True)
class RemediationSourceRef:
    """A caller-provided reference to a source audit artifact/report."""

    source_id: str
    source_type: str = ""
    reference: str = ""  # opaque path/report/artifact string
    label: str = ""
    generated_at: datetime | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _ensure_non_empty_str(self.source_id, "source_id")
        _ensure_str_with_default(self.source_type, "source_type")
        _ensure_str_with_default(self.reference, "reference")
        _ensure_str_with_default(self.label, "label")
        _ensure_timezone_aware(self.generated_at, "generated_at")
        object.__setattr__(self, "metadata", _coerce_str_mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class RemediationFindingRef:
    """A caller-provided reference to a finding/issue within a source."""

    finding_id: str
    source_id: str = ""
    reference: str = ""  # opaque path/report/artifact string
    label: str = ""
    generated_at: datetime | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _ensure_non_empty_str(self.finding_id, "finding_id")
        _ensure_str_with_default(self.source_id, "source_id")
        _ensure_str_with_default(self.reference, "reference")
        _ensure_str_with_default(self.label, "label")
        _ensure_timezone_aware(self.generated_at, "generated_at")
        object.__setattr__(self, "metadata", _coerce_str_mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class RemediationDependency:
    """A relationship between two backlog items."""

    dependency_id: str
    source_item_id: str
    target_item_id: str
    dependency_type: RemediationDependencyType = RemediationDependencyType.RELATED_TO
    generated_at: datetime | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _ensure_non_empty_str(self.dependency_id, "dependency_id")
        _ensure_non_empty_str(self.source_item_id, "source_item_id")
        _ensure_non_empty_str(self.target_item_id, "target_item_id")
        if not isinstance(self.dependency_type, RemediationDependencyType):
            raise ValueError("dependency_type must be a RemediationDependencyType")
        _ensure_timezone_aware(self.generated_at, "generated_at")
        object.__setattr__(self, "metadata", _coerce_str_mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class RemediationAcknowledgement:
    """A human acknowledgement that reclassifies a backlog item."""

    acknowledgement_id: str
    item_id: str
    acknowledged_by: str | None = None
    acknowledged_at: datetime | None = None
    note: str = ""
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _ensure_non_empty_str(self.acknowledgement_id, "acknowledgement_id")
        _ensure_non_empty_str(self.item_id, "item_id")
        object.__setattr__(self, "acknowledged_by", _ensure_str_or_none(self.acknowledged_by, "acknowledged_by"))
        _ensure_timezone_aware(self.acknowledged_at, "acknowledged_at")
        _ensure_str_with_default(self.note, "note")
        object.__setattr__(self, "metadata", _coerce_str_mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class RemediationBacklogItem:
    """A single remediation backlog item or engine-generated issue."""

    item_id: str | None = None
    subject_id: str | None = None
    source_id: str | None = None
    finding_id: str | None = None
    item_type: RemediationBacklogItemType = RemediationBacklogItemType.MANUAL_REVIEW
    item_state: RemediationBacklogItemState = RemediationBacklogItemState.OPEN
    severity: RemediationBacklogSeverity = RemediationBacklogSeverity.ADVISORY
    priority: RemediationBacklogPriority = RemediationBacklogPriority.NONE
    title: str = ""
    description: str = ""
    owner: str | None = None
    reviewer: str | None = None
    generated_at: datetime | None = None
    reason_codes: tuple[RemediationBacklogReasonCode, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "item_id", _ensure_str_or_none(self.item_id, "item_id"))
        object.__setattr__(self, "subject_id", _ensure_str_or_none(self.subject_id, "subject_id"))
        object.__setattr__(self, "source_id", _ensure_str_or_none(self.source_id, "source_id"))
        object.__setattr__(self, "finding_id", _ensure_str_or_none(self.finding_id, "finding_id"))
        if not isinstance(self.item_type, RemediationBacklogItemType):
            raise ValueError("item_type must be a RemediationBacklogItemType")
        if not isinstance(self.item_state, RemediationBacklogItemState):
            raise ValueError("item_state must be a RemediationBacklogItemState")
        if not isinstance(self.severity, RemediationBacklogSeverity):
            raise ValueError("severity must be a RemediationBacklogSeverity")
        if not isinstance(self.priority, RemediationBacklogPriority):
            raise ValueError("priority must be a RemediationBacklogPriority")
        _ensure_str_with_default(self.title, "title")
        _ensure_str_with_default(self.description, "description")
        object.__setattr__(self, "owner", _ensure_str_or_none(self.owner, "owner"))
        object.__setattr__(self, "reviewer", _ensure_str_or_none(self.reviewer, "reviewer"))
        _ensure_timezone_aware(self.generated_at, "generated_at")
        object.__setattr__(self, "reason_codes", tuple(self.reason_codes))
        for code in self.reason_codes:
            if not isinstance(code, RemediationBacklogReasonCode):
                raise ValueError("reason_codes must contain RemediationBacklogReasonCode values")
        object.__setattr__(self, "metadata", _coerce_str_mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class RemediationBacklogDataQuality:
    """Data quality summary for the remediation backlog report."""

    total_sources: int = 0
    total_findings: int = 0
    total_backlog_items: int = 0
    total_dependencies: int = 0
    total_acknowledgements: int = 0
    total_issues: int = 0
    duplicate_id_count: int = 0
    duplicate_item_count: int = 0
    orphan_finding_count: int = 0
    orphan_dependency_count: int = 0
    cycle_count: int = 0
    conflicting_item_count: int = 0
    stale_source_count: int = 0
    stale_finding_count: int = 0
    missing_owner_count: int = 0
    missing_reviewer_count: int = 0
    missing_manual_review_count: int = 0
    unsafe_content_count: int = 0
    forbidden_term_count: int = 0
    sections_present: int = 0

    def __post_init__(self) -> None:
        for attr in (
            "total_sources",
            "total_findings",
            "total_backlog_items",
            "total_dependencies",
            "total_acknowledgements",
            "total_issues",
            "duplicate_id_count",
            "duplicate_item_count",
            "orphan_finding_count",
            "orphan_dependency_count",
            "cycle_count",
            "conflicting_item_count",
            "stale_source_count",
            "stale_finding_count",
            "missing_owner_count",
            "missing_reviewer_count",
            "missing_manual_review_count",
            "unsafe_content_count",
            "forbidden_term_count",
            "sections_present",
        ):
            _ensure_non_negative_int(getattr(self, attr), attr)


@dataclass(frozen=True, slots=True)
class RemediationBacklogInput:
    """Top-level input for the remediation backlog planner."""

    source_refs: tuple[RemediationSourceRef, ...] = ()
    finding_refs: tuple[RemediationFindingRef, ...] = ()
    backlog_items: tuple[RemediationBacklogItem, ...] = ()
    dependencies: tuple[RemediationDependency, ...] = ()
    acknowledgements: tuple[RemediationAcknowledgement, ...] = ()
    config: RemediationBacklogConfig = field(default_factory=RemediationBacklogConfig)
    metadata: Mapping[str, str] = field(default_factory=dict)
    generated_at: datetime | None = None
    project_version: str = REMEDIATION_BACKLOG_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_refs", _ensure_tuple_of_items(self.source_refs, RemediationSourceRef, "source_refs"))
        object.__setattr__(self, "finding_refs", _ensure_tuple_of_items(self.finding_refs, RemediationFindingRef, "finding_refs"))
        object.__setattr__(self, "backlog_items", _ensure_tuple_of_items(self.backlog_items, RemediationBacklogItem, "backlog_items"))
        object.__setattr__(self, "dependencies", _ensure_tuple_of_items(self.dependencies, RemediationDependency, "dependencies"))
        object.__setattr__(self, "acknowledgements", _ensure_tuple_of_items(self.acknowledgements, RemediationAcknowledgement, "acknowledgements"))
        if not isinstance(self.config, RemediationBacklogConfig):
            raise ValueError("config must be a RemediationBacklogConfig")
        object.__setattr__(self, "metadata", _coerce_str_mapping(self.metadata))
        _ensure_timezone_aware(self.generated_at, "generated_at")
        _ensure_str_with_default(self.project_version, "project_version")


@dataclass(frozen=True, slots=True)
class RemediationBacklogReport:
    """Deterministic remediation backlog report."""

    report_id: str
    generated_at: datetime
    state: RemediationBacklogState
    project_version: str
    source_refs: tuple[RemediationSourceRef, ...]
    finding_refs: tuple[RemediationFindingRef, ...]
    backlog_items: tuple[RemediationBacklogItem, ...]
    dependencies: tuple[RemediationDependency, ...]
    acknowledgements: tuple[RemediationAcknowledgement, ...]
    issues: tuple[RemediationBacklogItem, ...]
    data_quality: RemediationBacklogDataQuality
    safety_flags: RemediationBacklogSafetyFlags
    reason_codes: tuple[RemediationBacklogReasonCode, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)
    safety_notice: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        _ensure_non_empty_str(self.report_id, "report_id")
        _ensure_timezone_aware(self.generated_at, "generated_at")
        if not isinstance(self.state, RemediationBacklogState):
            raise ValueError("state must be a RemediationBacklogState")
        _ensure_str_with_default(self.project_version, "project_version")
        for attr in (
            "source_refs",
            "finding_refs",
            "backlog_items",
            "dependencies",
            "acknowledgements",
            "issues",
            "reason_codes",
        ):
            value = getattr(self, attr)
            if not isinstance(value, tuple):
                raise ValueError(f"{attr} must be a tuple")
        for code in self.reason_codes:
            if not isinstance(code, RemediationBacklogReasonCode):
                raise ValueError("reason_codes must contain RemediationBacklogReasonCode values")
        if not isinstance(self.data_quality, RemediationBacklogDataQuality):
            raise ValueError("data_quality must be a RemediationBacklogDataQuality")
        if not isinstance(self.safety_flags, RemediationBacklogSafetyFlags):
            raise ValueError("safety_flags must be a RemediationBacklogSafetyFlags")
        object.__setattr__(self, "metadata", _coerce_str_mapping(self.metadata))
        _ensure_str_with_default(self.safety_notice, "safety_notice")
        _ensure_str_with_default(self.notes, "notes")

    @classmethod
    def blocked(
        cls,
        *,
        input: RemediationBacklogInput,
        reason_code: RemediationBacklogReasonCode = RemediationBacklogReasonCode.UNSAFE_CONTENT,
        generated_at: datetime | None = None,
        safety_flags: RemediationBacklogSafetyFlags | None = None,
        notes: str = "",
    ) -> "RemediationBacklogReport":
        """Create a deterministic fail-closed blocked remediation backlog report."""
        if generated_at is None:
            generated_at = input.generated_at if input.generated_at is not None else datetime.now(timezone.utc)
        if safety_flags is None:
            if reason_code == RemediationBacklogReasonCode.FORBIDDEN_TERM_PRESENT:
                safety_flags = RemediationBacklogSafetyFlags(has_forbidden_terms=True)
            else:
                safety_flags = RemediationBacklogSafetyFlags(has_unsafe_content=True)
        data_quality = RemediationBacklogDataQuality(
            total_sources=len(input.source_refs),
            total_findings=len(input.finding_refs),
            total_backlog_items=len(input.backlog_items),
            total_dependencies=len(input.dependencies),
            total_acknowledgements=len(input.acknowledgements),
        )
        return cls(
            report_id="remediation_backlog_blocked",
            state=RemediationBacklogState.BLOCKED,
            reason_codes=(
                RemediationBacklogReasonCode.SAFETY_BLOCKED,
                reason_code,
            ),
            source_refs=tuple(input.source_refs),
            finding_refs=tuple(input.finding_refs),
            backlog_items=tuple(input.backlog_items),
            dependencies=tuple(input.dependencies),
            acknowledgements=tuple(input.acknowledgements),
            issues=(),
            data_quality=data_quality,
            safety_flags=safety_flags,
            generated_at=generated_at,
            project_version=input.project_version,
            safety_notice="",
            notes=notes,
        )
