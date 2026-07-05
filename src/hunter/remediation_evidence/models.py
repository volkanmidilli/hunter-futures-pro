"""Frozen dataclasses for hunter.remediation_evidence package.

MVP-38 — Local Research Remediation Evidence Tracker.

All dataclasses are frozen. Validation runs in __post_init__. The tracker only
accepts caller-provided in-memory declarations and references. It never opens,
follows, traverses, validates, fetches, or executes file references, report
references, or metadata strings. Actual artifact paths, section references,
evidence references, and metadata are provided by the caller or a trusted test
harness; the engine never scans the filesystem, imports arbitrary modules, or
introspects the repository.

Remediation evidence coverage is a human-audit / research artifact only. It is
not a production certification, not a trading readiness assessment, not a
suitability assessment, and not a trading signal or recommendation.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any

from hunter.remediation_backlog.models import RemediationBacklogItemState

REMEDIATION_EVIDENCE_VERSION: str = "0.38.0-dev"


class RemediationEvidenceState(Enum):
    """Aggregate state of a remediation evidence report."""

    OK = "ok"
    DEGRADED = "degraded"
    BLOCKED = "blocked"
    NOT_APPLICABLE = "not_applicable"


class RemediationEvidenceSeverity(Enum):
    """Severity of a remediation evidence issue."""

    BLOCKING = "blocking"
    ADVISORY = "advisory"
    INFO = "info"


class RemediationEvidenceReasonCode(Enum):
    """Reason codes for remediation evidence results and reports."""

    OK = "ok"
    NOT_APPLICABLE = "not_applicable"
    CONSISTENCY_DEGRADED = "consistency_degraded"
    SAFETY_BLOCKED = "safety_blocked"
    UNSAFE_CONTENT = "unsafe_content"
    FORBIDDEN_TERM_PRESENT = "forbidden_term_present"
    DUPLICATE_ID = "duplicate_id"
    DUPLICATE_EVIDENCE = "duplicate_evidence"
    ORPHAN_EVIDENCE = "orphan_evidence"
    ORPHAN_REVIEW = "orphan_review"
    ORPHAN_LINK = "orphan_link"
    CONFLICTING_REVIEW = "conflicting_review"
    STALE_EVIDENCE = "stale_evidence"
    STALE_REVIEW = "stale_review"
    MISSING_EVIDENCE = "missing_evidence"
    MISSING_REVIEW = "missing_review"
    REJECTED_EVIDENCE = "rejected_evidence"
    PENDING_REVIEW_EVIDENCE = "pending_review_evidence"
    BLOCKED_BACKLOG_ITEM = "blocked_backlog_item"
    OPEN_BACKLOG_ITEM = "open_backlog_item"
    ACKNOWLEDGED_BACKLOG_ITEM = "acknowledged_backlog_item"
    DEFERRED_BACKLOG_ITEM = "deferred_backlog_item"
    NOT_APPLICABLE_BACKLOG_ITEM = "not_applicable_backlog_item"


class RemediationEvidenceRecordState(Enum):
    """State of a single evidence record."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    PENDING_REVIEW = "pending_review"
    STALE = "stale"
    DUPLICATE = "duplicate"
    ORPHANED = "orphaned"
    CONFLICTING = "conflicting"
    NOT_APPLICABLE = "not_applicable"


class RemediationEvidenceCoverageState(Enum):
    """Coverage classification for a backlog item."""

    COVERED = "covered"
    PARTIAL = "partial"
    MISSING = "missing"
    REJECTED = "rejected"
    PENDING_REVIEW = "pending_review"
    CONFLICTING = "conflicting"
    STALE = "stale"
    NOT_APPLICABLE = "not_applicable"


class RemediationEvidenceReviewOutcome(Enum):
    """Outcome of a human review of an evidence record."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    PENDING_REVIEW = "pending_review"
    NOT_APPLICABLE = "not_applicable"


class RemediationEvidenceLinkType(Enum):
    """Relationship type between evidence and a backlog item."""

    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    OBSERVES = "observes"


class RemediationEvidenceIssueType(Enum):
    """Type of engine-generated issue."""

    UNSAFE_CONTENT = "unsafe_content"
    DUPLICATE_ID = "duplicate_id"
    DUPLICATE_EVIDENCE = "duplicate_evidence"
    ORPHAN_EVIDENCE = "orphan_evidence"
    ORPHAN_REVIEW = "orphan_review"
    ORPHAN_LINK = "orphan_link"
    CONFLICTING_REVIEW = "conflicting_review"
    STALE_EVIDENCE = "stale_evidence"
    STALE_REVIEW = "stale_review"
    MISSING_EVIDENCE = "missing_evidence"
    MISSING_REVIEW = "missing_review"
    REJECTED_EVIDENCE = "rejected_evidence"
    PENDING_REVIEW_EVIDENCE = "pending_review_evidence"
    BLOCKED_BACKLOG_ITEM = "blocked_backlog_item"
    OPEN_BACKLOG_ITEM = "open_backlog_item"
    ACKNOWLEDGED_BACKLOG_ITEM = "acknowledged_backlog_item"
    DEFERRED_BACKLOG_ITEM = "deferred_backlog_item"
    NOT_APPLICABLE_BACKLOG_ITEM = "not_applicable_backlog_item"


# String constants for convenient use in reason code tuples and frozensets.
OK = RemediationEvidenceReasonCode.OK.value
NOT_APPLICABLE_RC = RemediationEvidenceReasonCode.NOT_APPLICABLE.value
CONSISTENCY_DEGRADED = RemediationEvidenceReasonCode.CONSISTENCY_DEGRADED.value
SAFETY_BLOCKED = RemediationEvidenceReasonCode.SAFETY_BLOCKED.value
UNSAFE_CONTENT = RemediationEvidenceReasonCode.UNSAFE_CONTENT.value
FORBIDDEN_TERM_PRESENT = RemediationEvidenceReasonCode.FORBIDDEN_TERM_PRESENT.value
DUPLICATE_ID = RemediationEvidenceReasonCode.DUPLICATE_ID.value
DUPLICATE_EVIDENCE = RemediationEvidenceReasonCode.DUPLICATE_EVIDENCE.value
ORPHAN_EVIDENCE = RemediationEvidenceReasonCode.ORPHAN_EVIDENCE.value
ORPHAN_REVIEW = RemediationEvidenceReasonCode.ORPHAN_REVIEW.value
ORPHAN_LINK = RemediationEvidenceReasonCode.ORPHAN_LINK.value
CONFLICTING_REVIEW = RemediationEvidenceReasonCode.CONFLICTING_REVIEW.value
STALE_EVIDENCE = RemediationEvidenceReasonCode.STALE_EVIDENCE.value
STALE_REVIEW = RemediationEvidenceReasonCode.STALE_REVIEW.value
MISSING_EVIDENCE = RemediationEvidenceReasonCode.MISSING_EVIDENCE.value
MISSING_REVIEW = RemediationEvidenceReasonCode.MISSING_REVIEW.value
REJECTED_EVIDENCE = RemediationEvidenceReasonCode.REJECTED_EVIDENCE.value
PENDING_REVIEW_EVIDENCE = RemediationEvidenceReasonCode.PENDING_REVIEW_EVIDENCE.value
BLOCKED_BACKLOG_ITEM = RemediationEvidenceReasonCode.BLOCKED_BACKLOG_ITEM.value
OPEN_BACKLOG_ITEM = RemediationEvidenceReasonCode.OPEN_BACKLOG_ITEM.value
ACKNOWLEDGED_BACKLOG_ITEM = RemediationEvidenceReasonCode.ACKNOWLEDGED_BACKLOG_ITEM.value
DEFERRED_BACKLOG_ITEM = RemediationEvidenceReasonCode.DEFERRED_BACKLOG_ITEM.value
NOT_APPLICABLE_BACKLOG_ITEM = RemediationEvidenceReasonCode.NOT_APPLICABLE_BACKLOG_ITEM.value


# Safety: forbidden-term matcher.
#
# Uses case-insensitive substring search against caller-provided metadata and
# all textual fields. All entries MUST be multi-word phrases. Single-word terms
# are intentionally excluded because they produce false positives in benign
# audit text (e.g. "pending approval from security team", "certification body",
# "no recommendation needed", "signal processing", "no signal detected").
FORBIDDEN_REMEDIATION_EVIDENCE_TERMS: frozenset[str] = frozenset({
    "deploy immediately",
    "execute now",
    "run this command",
    "apply patch",
    "production ready",
    "trading ready",
    "live trading",
    "place order",
    "execute order",
    "buy signal",
    "sell signal",
    "hold signal",
    "go live",
    "push to production",
    "infrastructure change",
    "automated remediation",
    "self healing",
    "auto fix",
    "certified safe",
    "approved for deployment",
    "suitable for trading",
    "recommendation to trade",
    "exchange api",
    "binance key",
    "api key",
    "private key",
    "leverage up",
    "short squeeze",
    "margin call",
    "liquidate position",
})


# Validation helpers.


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
    return tuple(str(item) for item in value)


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


def _ensure_bool(value: Any, field_name: str) -> None:
    """Validate that value is a bool."""
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a bool")


# Safety helpers.


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


def has_unsafe_remediation_evidence_content(value: Any) -> bool:
    """Return True if value is not a safe string type (bytes, object, int, etc.)."""
    if value is None:
        return False
    if isinstance(value, str):
        return False
    if isinstance(value, (tuple, list)):
        return any(has_unsafe_remediation_evidence_content(item) for item in value)
    if isinstance(value, Mapping):
        return any(
            has_unsafe_remediation_evidence_content(k)
            or has_unsafe_remediation_evidence_content(v)
            for k, v in value.items()
        )
    return True


# Safety flags.


@dataclass(frozen=True, slots=True)
class RemediationEvidenceSafetyFlags:
    """Safety flags confirming the tracker stays within local audit boundaries."""

    no_executable_actions: bool = True
    no_trading_instructions: bool = True
    no_approval_claims: bool = True
    no_automated_remediation: bool = True
    references_opaque: bool = True
    audit_only: bool = True
    evidence_coverage_not_approval: bool = True
    has_unsafe_content: bool = False
    has_forbidden_terms: bool = False

    def __post_init__(self) -> None:
        positive_flags = (
            self.no_executable_actions,
            self.no_trading_instructions,
            self.no_approval_claims,
            self.no_automated_remediation,
            self.references_opaque,
            self.audit_only,
            self.evidence_coverage_not_approval,
        )
        if not all(positive_flags):
            raise ValueError("baseline safety invariants must be True")

    @property
    def is_safe(self) -> bool:
        """True when the report passes all safety boundary checks."""
        return not self.has_unsafe_content and not self.has_forbidden_terms


# Models.


@dataclass(frozen=True, slots=True)
class RemediationEvidenceConfig:
    """Configuration for the remediation evidence tracker."""

    strict: bool = False
    require_review: bool = False
    require_evidence_for_all: bool = False
    required_backlog_item_ids: tuple[str, ...] = ()
    staleness_threshold_seconds: int = 2_592_000  # 30 days
    forbid_action_terms: bool = True

    def __post_init__(self) -> None:
        _ensure_bool(self.strict, "strict")
        _ensure_bool(self.require_review, "require_review")
        _ensure_bool(self.require_evidence_for_all, "require_evidence_for_all")
        _ensure_bool(self.forbid_action_terms, "forbid_action_terms")
        object.__setattr__(self, "required_backlog_item_ids", _ensure_tuple_of_str(self.required_backlog_item_ids, "required_backlog_item_ids"))
        _ensure_non_negative_int(self.staleness_threshold_seconds, "staleness_threshold_seconds")


@dataclass(frozen=True, slots=True)
class RemediationBacklogItemRef:
    """Opaque reference to a remediation backlog item."""

    backlog_item_id: str = ""
    source_id: str = ""
    finding_id: str = ""
    item_state: RemediationBacklogItemState = RemediationBacklogItemState.OPEN
    severity: str = "advisory"
    priority: str = "none"
    title: str = ""
    description: str = ""
    generated_at: datetime | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _ensure_str_with_default(self.backlog_item_id, "backlog_item_id")
        _ensure_str_with_default(self.source_id, "source_id")
        _ensure_str_with_default(self.finding_id, "finding_id")
        if isinstance(self.item_state, str):
            try:
                object.__setattr__(self, "item_state", RemediationBacklogItemState(self.item_state.lower()))
            except ValueError as exc:
                raise ValueError(f"item_state must be a valid backlog item state: {self.item_state}") from exc
        if not isinstance(self.item_state, RemediationBacklogItemState):
            raise ValueError("item_state must be a RemediationBacklogItemState")
        _ensure_str_with_default(self.severity, "severity")
        _ensure_str_with_default(self.priority, "priority")
        _ensure_str_with_default(self.title, "title")
        _ensure_str_with_default(self.description, "description")
        _ensure_timezone_aware(self.generated_at, "generated_at")
        object.__setattr__(self, "metadata", _coerce_str_mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class RemediationEvidenceRecord:
    """Caller-provided evidence record."""

    evidence_id: str = ""
    backlog_item_id: str = ""
    title: str = ""
    description: str = ""
    evidence_state: RemediationEvidenceRecordState = RemediationEvidenceRecordState.PENDING_REVIEW
    generated_at: datetime | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _ensure_str_with_default(self.evidence_id, "evidence_id")
        _ensure_str_with_default(self.backlog_item_id, "backlog_item_id")
        _ensure_str_with_default(self.title, "title")
        _ensure_str_with_default(self.description, "description")
        if isinstance(self.evidence_state, str):
            try:
                object.__setattr__(self, "evidence_state", RemediationEvidenceRecordState(self.evidence_state.lower()))
            except ValueError as exc:
                raise ValueError(f"evidence_state must be a valid evidence record state: {self.evidence_state}") from exc
        if not isinstance(self.evidence_state, RemediationEvidenceRecordState):
            raise ValueError("evidence_state must be a RemediationEvidenceRecordState")
        _ensure_timezone_aware(self.generated_at, "generated_at")
        object.__setattr__(self, "metadata", _coerce_str_mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class RemediationReviewRecord:
    """Caller-provided human review outcome for an evidence record."""

    review_id: str = ""
    evidence_id: str = ""
    outcome: RemediationEvidenceReviewOutcome = RemediationEvidenceReviewOutcome.PENDING_REVIEW
    reviewer: str = ""
    reviewed_at: datetime | None = None
    generated_at: datetime | None = None
    note: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _ensure_str_with_default(self.review_id, "review_id")
        _ensure_str_with_default(self.evidence_id, "evidence_id")
        if isinstance(self.outcome, str):
            try:
                object.__setattr__(self, "outcome", RemediationEvidenceReviewOutcome(self.outcome.lower()))
            except ValueError as exc:
                raise ValueError(f"outcome must be a valid review outcome: {self.outcome}") from exc
        if not isinstance(self.outcome, RemediationEvidenceReviewOutcome):
            raise ValueError("outcome must be a RemediationEvidenceReviewOutcome")
        _ensure_str_with_default(self.reviewer, "reviewer")
        _ensure_timezone_aware(self.reviewed_at, "reviewed_at")
        _ensure_timezone_aware(self.generated_at, "generated_at")
        _ensure_str_with_default(self.note, "note")
        object.__setattr__(self, "metadata", _coerce_str_mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class RemediationEvidenceLink:
    """Caller-provided link between an evidence record and a backlog item."""

    link_id: str = ""
    evidence_id: str = ""
    backlog_item_id: str = ""
    link_type: RemediationEvidenceLinkType = RemediationEvidenceLinkType.SUPPORTS
    generated_at: datetime | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _ensure_str_with_default(self.link_id, "link_id")
        _ensure_str_with_default(self.evidence_id, "evidence_id")
        _ensure_str_with_default(self.backlog_item_id, "backlog_item_id")
        if isinstance(self.link_type, str):
            try:
                object.__setattr__(self, "link_type", RemediationEvidenceLinkType(self.link_type.lower()))
            except ValueError as exc:
                raise ValueError(f"link_type must be a valid link type: {self.link_type}") from exc
        if not isinstance(self.link_type, RemediationEvidenceLinkType):
            raise ValueError("link_type must be a RemediationEvidenceLinkType")
        _ensure_timezone_aware(self.generated_at, "generated_at")
        object.__setattr__(self, "metadata", _coerce_str_mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class RemediationEvidenceIssue:
    """Engine-generated issue."""

    issue_id: str = ""
    issue_type: RemediationEvidenceIssueType = RemediationEvidenceIssueType.UNSAFE_CONTENT
    severity: RemediationEvidenceSeverity = RemediationEvidenceSeverity.INFO
    reason_codes: tuple[str, ...] = ()
    title: str = ""
    description: str = ""
    evidence_id: str = ""
    backlog_item_id: str = ""
    review_id: str = ""
    link_id: str = ""
    generated_at: datetime | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _ensure_str_with_default(self.issue_id, "issue_id")
        if isinstance(self.issue_type, str):
            try:
                object.__setattr__(self, "issue_type", RemediationEvidenceIssueType(self.issue_type.lower()))
            except ValueError as exc:
                raise ValueError(f"issue_type must be a valid issue type: {self.issue_type}") from exc
        if not isinstance(self.issue_type, RemediationEvidenceIssueType):
            raise ValueError("issue_type must be a RemediationEvidenceIssueType")
        if isinstance(self.severity, str):
            try:
                object.__setattr__(self, "severity", RemediationEvidenceSeverity(self.severity.lower()))
            except ValueError as exc:
                raise ValueError(f"severity must be a valid severity: {self.severity}") from exc
        if not isinstance(self.severity, RemediationEvidenceSeverity):
            raise ValueError("severity must be a RemediationEvidenceSeverity")
        object.__setattr__(self, "reason_codes", tuple(str(code) for code in self.reason_codes))
        _ensure_str_with_default(self.title, "title")
        _ensure_str_with_default(self.description, "description")
        _ensure_str_with_default(self.evidence_id, "evidence_id")
        _ensure_str_with_default(self.backlog_item_id, "backlog_item_id")
        _ensure_str_with_default(self.review_id, "review_id")
        _ensure_str_with_default(self.link_id, "link_id")
        _ensure_timezone_aware(self.generated_at, "generated_at")
        object.__setattr__(self, "metadata", _coerce_str_mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class RemediationEvidenceCoverageResult:
    """Coverage classification per backlog item."""

    coverage_id: str = ""
    backlog_item_id: str = ""
    coverage_state: RemediationEvidenceCoverageState = RemediationEvidenceCoverageState.MISSING
    evidence_ids: tuple[str, ...] = ()
    review_ids: tuple[str, ...] = ()
    severity: RemediationEvidenceSeverity = RemediationEvidenceSeverity.INFO
    reason_codes: tuple[str, ...] = ()
    title: str = ""
    description: str = ""
    generated_at: datetime | None = None

    def __post_init__(self) -> None:
        _ensure_str_with_default(self.coverage_id, "coverage_id")
        _ensure_str_with_default(self.backlog_item_id, "backlog_item_id")
        if isinstance(self.coverage_state, str):
            try:
                object.__setattr__(self, "coverage_state", RemediationEvidenceCoverageState(self.coverage_state.lower()))
            except ValueError as exc:
                raise ValueError(f"coverage_state must be a valid coverage state: {self.coverage_state}") from exc
        if not isinstance(self.coverage_state, RemediationEvidenceCoverageState):
            raise ValueError("coverage_state must be a RemediationEvidenceCoverageState")
        object.__setattr__(self, "evidence_ids", _ensure_tuple_of_str(self.evidence_ids, "evidence_ids"))
        object.__setattr__(self, "review_ids", _ensure_tuple_of_str(self.review_ids, "review_ids"))
        if isinstance(self.severity, str):
            try:
                object.__setattr__(self, "severity", RemediationEvidenceSeverity(self.severity.lower()))
            except ValueError as exc:
                raise ValueError(f"severity must be a valid severity: {self.severity}") from exc
        if not isinstance(self.severity, RemediationEvidenceSeverity):
            raise ValueError("severity must be a RemediationEvidenceSeverity")
        object.__setattr__(self, "reason_codes", tuple(str(code) for code in self.reason_codes))
        _ensure_str_with_default(self.title, "title")
        _ensure_str_with_default(self.description, "description")
        _ensure_timezone_aware(self.generated_at, "generated_at")


@dataclass(frozen=True, slots=True)
class RemediationEvidenceDataQuality:
    """Data quality summary for the remediation evidence report."""

    total_backlog_item_refs: int = 0
    total_evidence_records: int = 0
    total_review_records: int = 0
    total_links: int = 0
    total_issues: int = 0
    total_coverage_results: int = 0
    duplicate_id_count: int = 0
    duplicate_evidence_count: int = 0
    orphan_evidence_count: int = 0
    orphan_review_count: int = 0
    orphan_link_count: int = 0
    conflicting_review_count: int = 0
    stale_evidence_count: int = 0
    stale_review_count: int = 0
    missing_evidence_count: int = 0
    missing_review_count: int = 0
    rejected_evidence_count: int = 0
    pending_review_evidence_count: int = 0
    blocked_backlog_item_count: int = 0
    open_backlog_item_count: int = 0
    unsafe_content_count: int = 0
    forbidden_term_count: int = 0
    sections_present: int = 0

    def __post_init__(self) -> None:
        for attr in (
            "total_backlog_item_refs",
            "total_evidence_records",
            "total_review_records",
            "total_links",
            "total_issues",
            "total_coverage_results",
            "duplicate_id_count",
            "duplicate_evidence_count",
            "orphan_evidence_count",
            "orphan_review_count",
            "orphan_link_count",
            "conflicting_review_count",
            "stale_evidence_count",
            "stale_review_count",
            "missing_evidence_count",
            "missing_review_count",
            "rejected_evidence_count",
            "pending_review_evidence_count",
            "blocked_backlog_item_count",
            "open_backlog_item_count",
            "unsafe_content_count",
            "forbidden_term_count",
            "sections_present",
        ):
            _ensure_non_negative_int(getattr(self, attr), attr)


@dataclass(frozen=True, slots=True)
class RemediationEvidenceInput:
    """Top-level input for the remediation evidence tracker."""

    backlog_item_refs: tuple[RemediationBacklogItemRef, ...] = ()
    evidence_records: tuple[RemediationEvidenceRecord, ...] = ()
    review_records: tuple[RemediationReviewRecord, ...] = ()
    links: tuple[RemediationEvidenceLink, ...] = ()
    config: RemediationEvidenceConfig = field(default_factory=RemediationEvidenceConfig)
    project_version: str = REMEDIATION_EVIDENCE_VERSION
    metadata: Mapping[str, Any] = field(default_factory=dict)
    generated_at: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "backlog_item_refs", _ensure_tuple_of_items(self.backlog_item_refs, RemediationBacklogItemRef, "backlog_item_refs"))
        object.__setattr__(self, "evidence_records", _ensure_tuple_of_items(self.evidence_records, RemediationEvidenceRecord, "evidence_records"))
        object.__setattr__(self, "review_records", _ensure_tuple_of_items(self.review_records, RemediationReviewRecord, "review_records"))
        object.__setattr__(self, "links", _ensure_tuple_of_items(self.links, RemediationEvidenceLink, "links"))
        if not isinstance(self.config, RemediationEvidenceConfig):
            raise ValueError("config must be a RemediationEvidenceConfig")
        _ensure_str_with_default(self.project_version, "project_version")
        object.__setattr__(self, "metadata", _coerce_str_mapping(self.metadata))
        _ensure_timezone_aware(self.generated_at, "generated_at")


@dataclass(frozen=True, slots=True)
class RemediationEvidenceReport:
    """Top-level output for the remediation evidence tracker."""

    report_id: str = ""
    generated_at: datetime | None = None
    state: RemediationEvidenceState = RemediationEvidenceState.NOT_APPLICABLE
    project_version: str = REMEDIATION_EVIDENCE_VERSION
    backlog_item_refs: tuple[RemediationBacklogItemRef, ...] = ()
    evidence_records: tuple[RemediationEvidenceRecord, ...] = ()
    review_records: tuple[RemediationReviewRecord, ...] = ()
    links: tuple[RemediationEvidenceLink, ...] = ()
    issues: tuple[RemediationEvidenceIssue, ...] = ()
    coverage_results: tuple[RemediationEvidenceCoverageResult, ...] = ()
    data_quality: RemediationEvidenceDataQuality = field(default_factory=RemediationEvidenceDataQuality)
    safety_flags: RemediationEvidenceSafetyFlags = field(default_factory=RemediationEvidenceSafetyFlags)
    reason_codes: tuple[RemediationEvidenceReasonCode, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    safety_notice: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        _ensure_str_with_default(self.report_id, "report_id")
        _ensure_timezone_aware(self.generated_at, "generated_at")
        if isinstance(self.state, str):
            try:
                object.__setattr__(self, "state", RemediationEvidenceState(self.state.lower()))
            except ValueError as exc:
                raise ValueError(f"state must be a valid report state: {self.state}") from exc
        if not isinstance(self.state, RemediationEvidenceState):
            raise ValueError("state must be a RemediationEvidenceState")
        _ensure_str_with_default(self.project_version, "project_version")
        for attr in (
            "backlog_item_refs",
            "evidence_records",
            "review_records",
            "links",
            "issues",
            "coverage_results",
            "reason_codes",
        ):
            value = getattr(self, attr)
            if not isinstance(value, tuple):
                raise ValueError(f"{attr} must be a tuple")
        for code in self.reason_codes:
            if not isinstance(code, RemediationEvidenceReasonCode):
                raise ValueError("reason_codes must contain RemediationEvidenceReasonCode values")
        if not isinstance(self.data_quality, RemediationEvidenceDataQuality):
            raise ValueError("data_quality must be a RemediationEvidenceDataQuality")
        if not isinstance(self.safety_flags, RemediationEvidenceSafetyFlags):
            raise ValueError("safety_flags must be a RemediationEvidenceSafetyFlags")
        object.__setattr__(self, "metadata", _coerce_str_mapping(self.metadata))
        _ensure_str_with_default(self.safety_notice, "safety_notice")
        _ensure_str_with_default(self.notes, "notes")

    @classmethod
    def blocked(
        cls,
        *,
        input: "RemediationEvidenceInput",
        reason_code: RemediationEvidenceReasonCode = RemediationEvidenceReasonCode.UNSAFE_CONTENT,
        notes: str = "",
    ) -> "RemediationEvidenceReport":
        """Create a deterministic fail-closed blocked remediation evidence report.

        Echoes caller-provided collections if available; otherwise they are empty
        tuples. Contains a single blocking issue, an empty coverage_results tuple,
        and a safety_notice stating that the report is an audit-only research
        artifact and does not imply approval or readiness. No path or reference is
        opened, traversed, validated, fetched, or executed.
        """
        from datetime import datetime as _datetime
        generated_at = input.generated_at if input.generated_at is not None else _datetime.now(timezone.utc)
        if reason_code == RemediationEvidenceReasonCode.FORBIDDEN_TERM_PRESENT:
            safety_flags = RemediationEvidenceSafetyFlags(has_forbidden_terms=True)
        else:
            safety_flags = RemediationEvidenceSafetyFlags(has_unsafe_content=True)
        data_quality = RemediationEvidenceDataQuality(
            total_backlog_item_refs=len(input.backlog_item_refs),
            total_evidence_records=len(input.evidence_records),
            total_review_records=len(input.review_records),
            total_links=len(input.links),
        )
        return cls(
            report_id="remediation_evidence_blocked",
            state=RemediationEvidenceState.BLOCKED,
            reason_codes=(
                RemediationEvidenceReasonCode.SAFETY_BLOCKED,
                reason_code,
            ),
            backlog_item_refs=tuple(input.backlog_item_refs),
            evidence_records=tuple(input.evidence_records),
            review_records=tuple(input.review_records),
            links=tuple(input.links),
            issues=(
                RemediationEvidenceIssue(
                    issue_type=RemediationEvidenceIssueType.UNSAFE_CONTENT,
                    severity=RemediationEvidenceSeverity.BLOCKING,
                    reason_codes=(reason_code.value,),
                    title="Report blocked",
                    description="Input failed safety validation.",
                ),
            ),
            coverage_results=(),
            data_quality=data_quality,
            safety_flags=safety_flags,
            generated_at=generated_at,
            project_version=input.project_version,
            safety_notice=(
                "This report is a local, audit-only research artifact. "
                "Evidence coverage is for human-audit tracking only and does not imply "
                "approval, certification, production readiness, trading readiness, "
                "recommendation, suitability, or signal validity."
            ),
            notes=notes,
        )

