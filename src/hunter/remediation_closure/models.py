"""Frozen dataclasses for hunter.remediation_closure package.

MVP-39 — Local Research Remediation Closure Register.

All dataclasses are frozen. Validation runs in __post_init__. The register only
accepts caller-provided in-memory declarations and references. It never opens,
follows, traverses, validates, fetches, or executes file references, report
references, or metadata strings. Actual artifact paths, section references,
closure references, and metadata are provided by the caller or a trusted test
harness; the engine never scans the filesystem, imports arbitrary modules, or
introspects the repository.

Remediation closure records are human-audit / research artifacts only. They are
not a production certification, not a trading readiness assessment, not a
suitability assessment, and not a trading signal or recommendation.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any

from hunter.remediation_backlog.models import RemediationBacklogItemState

REMEDIATION_CLOSURE_VERSION: str = "0.39.0-dev"


class RemediationClosureState(Enum):
    """Aggregate state of a remediation closure report."""

    OK = "ok"
    DEGRADED = "degraded"
    BLOCKED = "blocked"
    NOT_APPLICABLE = "not_applicable"


class RemediationClosureSeverity(Enum):
    """Severity of a remediation closure issue."""

    BLOCKING = "blocking"
    ADVISORY = "advisory"
    INFO = "info"


class RemediationClosureReasonCode(Enum):
    """Reason codes for remediation closure results and reports."""

    OK = "ok"
    NOT_APPLICABLE = "not_applicable"
    CONSISTENCY_DEGRADED = "consistency_degraded"
    SAFETY_BLOCKED = "safety_blocked"
    UNSAFE_CONTENT = "unsafe_content"
    FORBIDDEN_TERM_PRESENT = "forbidden_term_present"
    DUPLICATE_ID = "duplicate_id"
    ORPHAN_EVIDENCE = "orphan_evidence"
    ORPHAN_CLOSURE = "orphan_closure"
    ORPHAN_REVIEW = "orphan_review"
    ORPHAN_LINK = "orphan_link"
    CONFLICTING_CLOSURE = "conflicting_closure"
    CONFLICTING_REVIEW = "conflicting_review"
    STALE_EVIDENCE = "stale_evidence"
    STALE_CLOSURE = "stale_closure"
    STALE_REVIEW = "stale_review"
    MISSING_EVIDENCE = "missing_evidence"
    MISSING_REVIEW = "missing_review"
    MISSING_CLOSURE_METADATA = "missing_closure_metadata"
    REJECTED_REVIEW = "rejected_review"
    PENDING_REVIEW = "pending_review"
    DISPUTED_REVIEW = "disputed_review"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"
    BLOCKED_BACKLOG_ITEM = "blocked_backlog_item"
    OPEN_BACKLOG_ITEM = "open_backlog_item"
    CONFLICTING_BACKLOG_ITEM = "conflicting_backlog_item"
    ACKNOWLEDGED_BACKLOG_ITEM = "acknowledged_backlog_item"
    DEFERRED_BACKLOG_ITEM = "deferred_backlog_item"
    NOT_APPLICABLE_BACKLOG_ITEM = "not_applicable_backlog_item"
    CLOSURE_RECORDED = "closure_recorded"


class RemediationClosureRecordState(Enum):
    """State of a single closure record."""

    CLOSED_RECORDED = "closed_recorded"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    PENDING_REVIEW = "pending_review"
    REJECTED = "rejected"
    DISPUTED = "disputed"
    STALE = "stale"
    DUPLICATE = "duplicate"
    ORPHANED = "orphaned"
    NOT_APPLICABLE = "not_applicable"


class RemediationClosureEligibilityState(Enum):
    """Eligibility classification for a closure record."""

    ELIGIBLE = "eligible"
    PARTIAL = "partial"
    INELIGIBLE = "ineligible"
    PENDING_REVIEW = "pending_review"
    DISPUTED = "disputed"
    STALE = "stale"
    NOT_APPLICABLE = "not_applicable"


class RemediationClosureReviewOutcome(Enum):
    """Outcome of a human review of a closure declaration."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    PENDING = "pending"
    DISPUTED = "disputed"
    NOT_REQUIRED = "not_required"
    NOT_APPLICABLE = "not_applicable"


class RemediationClosureLinkType(Enum):
    """Relationship type between closure, evidence, and backlog item."""

    CLOSURE_EVIDENCE = "closure_evidence"
    CLOSURE_BACKLOG = "closure_backlog"
    EVIDENCE_BACKLOG = "evidence_backlog"


class RemediationClosureIssueType(Enum):
    """Type of engine-generated issue."""

    UNSAFE_CONTENT = "unsafe_content"
    DUPLICATE_ID = "duplicate_id"
    ORPHAN_EVIDENCE = "orphan_evidence"
    ORPHAN_CLOSURE = "orphan_closure"
    ORPHAN_REVIEW = "orphan_review"
    ORPHAN_LINK = "orphan_link"
    CONFLICTING_CLOSURE = "conflicting_closure"
    CONFLICTING_REVIEW = "conflicting_review"
    STALE_EVIDENCE = "stale_evidence"
    STALE_CLOSURE = "stale_closure"
    STALE_REVIEW = "stale_review"
    MISSING_EVIDENCE = "missing_evidence"
    MISSING_REVIEW = "missing_review"
    MISSING_CLOSURE_METADATA = "missing_closure_metadata"
    REJECTED_REVIEW = "rejected_review"
    PENDING_REVIEW = "pending_review"
    DISPUTED_REVIEW = "disputed_review"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"
    BLOCKED_BACKLOG_ITEM = "blocked_backlog_item"
    OPEN_BACKLOG_ITEM = "open_backlog_item"
    CONFLICTING_BACKLOG_ITEM = "conflicting_backlog_item"
    ACKNOWLEDGED_BACKLOG_ITEM = "acknowledged_backlog_item"
    DEFERRED_BACKLOG_ITEM = "deferred_backlog_item"
    NOT_APPLICABLE_BACKLOG_ITEM = "not_applicable_backlog_item"


# String constants for convenient use in reason code tuples and frozensets.
OK = RemediationClosureReasonCode.OK.value
NOT_APPLICABLE_RC = RemediationClosureReasonCode.NOT_APPLICABLE.value
CONSISTENCY_DEGRADED = RemediationClosureReasonCode.CONSISTENCY_DEGRADED.value
SAFETY_BLOCKED = RemediationClosureReasonCode.SAFETY_BLOCKED.value
UNSAFE_CONTENT = RemediationClosureReasonCode.UNSAFE_CONTENT.value
FORBIDDEN_TERM_PRESENT = RemediationClosureReasonCode.FORBIDDEN_TERM_PRESENT.value
DUPLICATE_ID = RemediationClosureReasonCode.DUPLICATE_ID.value
ORPHAN_EVIDENCE = RemediationClosureReasonCode.ORPHAN_EVIDENCE.value
ORPHAN_CLOSURE = RemediationClosureReasonCode.ORPHAN_CLOSURE.value
ORPHAN_REVIEW = RemediationClosureReasonCode.ORPHAN_REVIEW.value
ORPHAN_LINK = RemediationClosureReasonCode.ORPHAN_LINK.value
CONFLICTING_CLOSURE = RemediationClosureReasonCode.CONFLICTING_CLOSURE.value
CONFLICTING_REVIEW = RemediationClosureReasonCode.CONFLICTING_REVIEW.value
STALE_EVIDENCE = RemediationClosureReasonCode.STALE_EVIDENCE.value
STALE_CLOSURE = RemediationClosureReasonCode.STALE_CLOSURE.value
STALE_REVIEW = RemediationClosureReasonCode.STALE_REVIEW.value
MISSING_EVIDENCE = RemediationClosureReasonCode.MISSING_EVIDENCE.value
MISSING_REVIEW = RemediationClosureReasonCode.MISSING_REVIEW.value
MISSING_CLOSURE_METADATA = RemediationClosureReasonCode.MISSING_CLOSURE_METADATA.value
REJECTED_REVIEW = RemediationClosureReasonCode.REJECTED_REVIEW.value
PENDING_REVIEW = RemediationClosureReasonCode.PENDING_REVIEW.value
DISPUTED_REVIEW = RemediationClosureReasonCode.DISPUTED_REVIEW.value
MANUAL_REVIEW_REQUIRED = RemediationClosureReasonCode.MANUAL_REVIEW_REQUIRED.value
BLOCKED_BACKLOG_ITEM = RemediationClosureReasonCode.BLOCKED_BACKLOG_ITEM.value
OPEN_BACKLOG_ITEM = RemediationClosureReasonCode.OPEN_BACKLOG_ITEM.value
CONFLICTING_BACKLOG_ITEM = RemediationClosureReasonCode.CONFLICTING_BACKLOG_ITEM.value
ACKNOWLEDGED_BACKLOG_ITEM = RemediationClosureReasonCode.ACKNOWLEDGED_BACKLOG_ITEM.value
DEFERRED_BACKLOG_ITEM = RemediationClosureReasonCode.DEFERRED_BACKLOG_ITEM.value
NOT_APPLICABLE_BACKLOG_ITEM = RemediationClosureReasonCode.NOT_APPLICABLE_BACKLOG_ITEM.value
CLOSURE_RECORDED = RemediationClosureReasonCode.CLOSURE_RECORDED.value


# Safety: forbidden-term matcher.
#
# Uses case-insensitive substring search against caller-provided metadata and
# all textual fields. All entries MUST be multi-word phrases. Single-word terms
# are intentionally excluded because they produce false positives in benign
# audit text (e.g. "pending approval from security team", "certification body",
# "no recommendation needed", "signal processing", "no signal detected").
FORBIDDEN_REMEDIATION_CLOSURE_TERMS: frozenset[str] = frozenset({
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
    "close and trade",
    "close now",
    "release to production",
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


def has_unsafe_remediation_closure_content(value: Any) -> bool:
    """Return True if value is not a safe string type (bytes, object, int, etc.)."""
    if value is None:
        return False
    if isinstance(value, str):
        return False
    if isinstance(value, (tuple, list)):
        return any(has_unsafe_remediation_closure_content(item) for item in value)
    if isinstance(value, Mapping):
        return any(
            has_unsafe_remediation_closure_content(k)
            or has_unsafe_remediation_closure_content(v)
            for k, v in value.items()
        )
    return True


# Safety flags.


@dataclass(frozen=True, slots=True)
class RemediationClosureSafetyFlags:
    """Safety flags confirming the register stays within local audit boundaries."""

    no_executable_actions: bool = True
    no_trading_instructions: bool = True
    no_approval_claims: bool = True
    no_automated_remediation: bool = True
    references_opaque: bool = True
    audit_only: bool = True
    closure_recorded_not_approval: bool = True
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
            self.closure_recorded_not_approval,
        )
        if not all(positive_flags):
            raise ValueError("baseline safety invariants must be True")

    @property
    def is_safe(self) -> bool:
        """True when the report passes all safety boundary checks."""
        return not self.has_unsafe_content and not self.has_forbidden_terms


# Models.


@dataclass(frozen=True, slots=True)
class RemediationClosureConfig:
    """Configuration for the remediation closure register."""

    strict: bool = False
    require_review: bool = False
    require_closure_for_all: bool = False
    require_evidence_for_closure: bool = True
    required_backlog_item_ids: tuple[str, ...] = ()
    staleness_threshold_seconds: int = 2_592_000  # 30 days
    forbid_action_terms: bool = True
    require_closure_metadata: bool = False

    def __post_init__(self) -> None:
        _ensure_bool(self.strict, "strict")
        _ensure_bool(self.require_review, "require_review")
        _ensure_bool(self.require_closure_for_all, "require_closure_for_all")
        _ensure_bool(self.require_evidence_for_closure, "require_evidence_for_closure")
        _ensure_bool(self.forbid_action_terms, "forbid_action_terms")
        _ensure_bool(self.require_closure_metadata, "require_closure_metadata")
        object.__setattr__(self, "required_backlog_item_ids", _ensure_tuple_of_str(self.required_backlog_item_ids, "required_backlog_item_ids"))
        _ensure_non_negative_int(self.staleness_threshold_seconds, "staleness_threshold_seconds")


@dataclass(frozen=True, slots=True)
class RemediationClosureBacklogItemRef:
    """Opaque reference to a remediation backlog item."""

    backlog_item_id: str = ""
    source_id: str = ""
    finding_id: str = ""
    item_state: str = "open"
    severity: str = "advisory"
    priority: str = "none"
    title: str = ""
    description: str = ""
    generated_at: datetime | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _ensure_str_with_default(self.backlog_item_id, "backlog_item_id")
        _ensure_str_with_default(self.source_id, "source_id")
        _ensure_str_with_default(self.finding_id, "finding_id")
        object.__setattr__(self, "item_state", _ensure_str_with_default(self.item_state, "item_state").lower())
        _ensure_str_with_default(self.severity, "severity")
        _ensure_str_with_default(self.priority, "priority")
        _ensure_str_with_default(self.title, "title")
        _ensure_str_with_default(self.description, "description")
        _ensure_timezone_aware(self.generated_at, "generated_at")
        object.__setattr__(self, "metadata", _coerce_str_mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class RemediationClosureEvidenceSummary:
    """Caller-provided summary of evidence coverage for a backlog item."""

    evidence_summary_id: str = ""
    backlog_item_id: str = ""
    coverage_state: str = "missing"
    evidence_ids: tuple[str, ...] = ()
    review_ids: tuple[str, ...] = ()
    generated_at: datetime | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _ensure_str_with_default(self.evidence_summary_id, "evidence_summary_id")
        _ensure_str_with_default(self.backlog_item_id, "backlog_item_id")
        _ensure_str_with_default(self.coverage_state, "coverage_state")
        object.__setattr__(self, "evidence_ids", _ensure_tuple_of_str(self.evidence_ids, "evidence_ids"))
        object.__setattr__(self, "review_ids", _ensure_tuple_of_str(self.review_ids, "review_ids"))
        _ensure_timezone_aware(self.generated_at, "generated_at")
        object.__setattr__(self, "metadata", _coerce_str_mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class RemediationClosureDeclaration:
    """Caller-provided closure declaration for a backlog item."""

    closure_id: str = ""
    backlog_item_id: str = ""
    evidence_summary_id: str = ""
    declared_by: str = ""
    reviewed_by: str = ""
    closed_at: datetime | None = None
    rationale: str = ""
    evidence_link: str = ""
    generated_at: datetime | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _ensure_str_with_default(self.closure_id, "closure_id")
        _ensure_str_with_default(self.backlog_item_id, "backlog_item_id")
        _ensure_str_with_default(self.evidence_summary_id, "evidence_summary_id")
        _ensure_str_with_default(self.declared_by, "declared_by")
        _ensure_str_with_default(self.reviewed_by, "reviewed_by")
        _ensure_timezone_aware(self.closed_at, "closed_at")
        _ensure_str_with_default(self.rationale, "rationale")
        _ensure_str_with_default(self.evidence_link, "evidence_link")
        _ensure_timezone_aware(self.generated_at, "generated_at")
        object.__setattr__(self, "metadata", _coerce_str_mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class RemediationClosureReviewRecord:
    """Caller-provided human review of a closure declaration."""

    review_id: str = ""
    closure_id: str = ""
    outcome: str = "pending"
    reviewer: str = ""
    reviewed_at: datetime | None = None
    generated_at: datetime | None = None
    note: str = ""
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _ensure_str_with_default(self.review_id, "review_id")
        _ensure_str_with_default(self.closure_id, "closure_id")
        _ensure_str_with_default(self.outcome, "outcome")
        _ensure_str_with_default(self.reviewer, "reviewer")
        _ensure_timezone_aware(self.reviewed_at, "reviewed_at")
        _ensure_timezone_aware(self.generated_at, "generated_at")
        _ensure_str_with_default(self.note, "note")
        object.__setattr__(self, "metadata", _coerce_str_mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class RemediationClosureLink:
    """Caller-provided link between closure, evidence, and backlog item."""

    link_id: str = ""
    closure_id: str = ""
    evidence_summary_id: str = ""
    backlog_item_id: str = ""
    link_type: str = "closure_evidence"
    generated_at: datetime | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _ensure_str_with_default(self.link_id, "link_id")
        _ensure_str_with_default(self.closure_id, "closure_id")
        _ensure_str_with_default(self.evidence_summary_id, "evidence_summary_id")
        _ensure_str_with_default(self.backlog_item_id, "backlog_item_id")
        _ensure_str_with_default(self.link_type, "link_type")
        _ensure_timezone_aware(self.generated_at, "generated_at")
        object.__setattr__(self, "metadata", _coerce_str_mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class RemediationClosureIssue:
    """Engine-generated issue."""

    issue_id: str = ""
    issue_type: RemediationClosureIssueType = RemediationClosureIssueType.UNSAFE_CONTENT
    severity: RemediationClosureSeverity = RemediationClosureSeverity.INFO
    reason_codes: tuple[str, ...] = ()
    title: str = ""
    description: str = ""
    backlog_item_id: str = ""
    closure_id: str = ""
    evidence_summary_id: str = ""
    review_id: str = ""
    link_id: str = ""
    generated_at: datetime | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _ensure_str_with_default(self.issue_id, "issue_id")
        if isinstance(self.issue_type, str):
            try:
                object.__setattr__(self, "issue_type", RemediationClosureIssueType(self.issue_type.lower()))
            except ValueError as exc:
                raise ValueError(f"issue_type must be a valid issue type: {self.issue_type}") from exc
        if not isinstance(self.issue_type, RemediationClosureIssueType):
            raise ValueError("issue_type must be a RemediationClosureIssueType")
        if isinstance(self.severity, str):
            try:
                object.__setattr__(self, "severity", RemediationClosureSeverity(self.severity.lower()))
            except ValueError as exc:
                raise ValueError(f"severity must be a valid severity: {self.severity}") from exc
        if not isinstance(self.severity, RemediationClosureSeverity):
            raise ValueError("severity must be a RemediationClosureSeverity")
        object.__setattr__(self, "reason_codes", tuple(str(code) for code in self.reason_codes))
        _ensure_str_with_default(self.title, "title")
        _ensure_str_with_default(self.description, "description")
        _ensure_str_with_default(self.backlog_item_id, "backlog_item_id")
        _ensure_str_with_default(self.closure_id, "closure_id")
        _ensure_str_with_default(self.evidence_summary_id, "evidence_summary_id")
        _ensure_str_with_default(self.review_id, "review_id")
        _ensure_str_with_default(self.link_id, "link_id")
        _ensure_timezone_aware(self.generated_at, "generated_at")
        object.__setattr__(self, "metadata", _coerce_str_mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class RemediationClosureResult:
    """Closure classification per backlog item."""

    closure_result_id: str = ""
    backlog_item_id: str = ""
    closure_id: str = ""
    record_state: str = "not_applicable"
    eligibility_state: str = "not_applicable"
    review_outcome: str = "not_required"
    severity: str = "info"
    reason_codes: tuple[str, ...] = ()
    title: str = ""
    description: str = ""
    generated_at: datetime | None = None

    def __post_init__(self) -> None:
        _ensure_str_with_default(self.closure_result_id, "closure_result_id")
        _ensure_str_with_default(self.backlog_item_id, "backlog_item_id")
        _ensure_str_with_default(self.closure_id, "closure_id")
        if isinstance(self.record_state, str):
            try:
                object.__setattr__(self, "record_state", RemediationClosureRecordState(self.record_state.lower()))
            except ValueError as exc:
                raise ValueError(f"record_state must be a valid closure record state: {self.record_state}") from exc
        if not isinstance(self.record_state, RemediationClosureRecordState):
            raise ValueError("record_state must be a RemediationClosureRecordState")
        if isinstance(self.eligibility_state, str):
            try:
                object.__setattr__(self, "eligibility_state", RemediationClosureEligibilityState(self.eligibility_state.lower()))
            except ValueError as exc:
                raise ValueError(f"eligibility_state must be a valid eligibility state: {self.eligibility_state}") from exc
        if not isinstance(self.eligibility_state, RemediationClosureEligibilityState):
            raise ValueError("eligibility_state must be a RemediationClosureEligibilityState")
        if isinstance(self.review_outcome, str):
            try:
                object.__setattr__(self, "review_outcome", RemediationClosureReviewOutcome(self.review_outcome.lower()))
            except ValueError as exc:
                raise ValueError(f"review_outcome must be a valid review outcome: {self.review_outcome}") from exc
        if not isinstance(self.review_outcome, RemediationClosureReviewOutcome):
            raise ValueError("review_outcome must be a RemediationClosureReviewOutcome")
        if isinstance(self.severity, str):
            try:
                object.__setattr__(self, "severity", RemediationClosureSeverity(self.severity.lower()))
            except ValueError as exc:
                raise ValueError(f"severity must be a valid severity: {self.severity}") from exc
        if not isinstance(self.severity, RemediationClosureSeverity):
            raise ValueError("severity must be a RemediationClosureSeverity")
        object.__setattr__(self, "reason_codes", tuple(str(code) for code in self.reason_codes))
        _ensure_str_with_default(self.title, "title")
        _ensure_str_with_default(self.description, "description")
        _ensure_timezone_aware(self.generated_at, "generated_at")


@dataclass(frozen=True, slots=True)
class RemediationClosureDataQuality:
    """Data quality summary for the closure register."""

    total_backlog_item_refs: int = 0
    total_evidence_summaries: int = 0
    total_closure_declarations: int = 0
    total_review_records: int = 0
    total_links: int = 0
    total_issues: int = 0
    total_closure_results: int = 0
    duplicate_id_count: int = 0
    orphan_evidence_count: int = 0
    orphan_closure_count: int = 0
    orphan_review_count: int = 0
    orphan_link_count: int = 0
    conflicting_closure_count: int = 0
    conflicting_review_count: int = 0
    stale_evidence_count: int = 0
    stale_closure_count: int = 0
    stale_review_count: int = 0
    missing_evidence_count: int = 0
    missing_review_count: int = 0
    missing_closure_metadata_count: int = 0
    rejected_review_count: int = 0
    pending_review_count: int = 0
    disputed_review_count: int = 0
    manual_review_required_count: int = 0
    blocked_backlog_item_count: int = 0
    open_backlog_item_count: int = 0
    conflicting_backlog_item_count: int = 0
    acknowledged_backlog_item_count: int = 0
    deferred_backlog_item_count: int = 0
    not_applicable_backlog_item_count: int = 0
    unsafe_content_count: int = 0
    forbidden_term_count: int = 0
    sections_present: int = 0

    def __post_init__(self) -> None:
        for attr in (
            "total_backlog_item_refs",
            "total_evidence_summaries",
            "total_closure_declarations",
            "total_review_records",
            "total_links",
            "total_issues",
            "total_closure_results",
            "duplicate_id_count",
            "orphan_evidence_count",
            "orphan_closure_count",
            "orphan_review_count",
            "orphan_link_count",
            "conflicting_closure_count",
            "conflicting_review_count",
            "stale_evidence_count",
            "stale_closure_count",
            "stale_review_count",
            "missing_evidence_count",
            "missing_review_count",
            "missing_closure_metadata_count",
            "rejected_review_count",
            "pending_review_count",
            "disputed_review_count",
            "manual_review_required_count",
            "blocked_backlog_item_count",
            "open_backlog_item_count",
            "conflicting_backlog_item_count",
            "acknowledged_backlog_item_count",
            "deferred_backlog_item_count",
            "not_applicable_backlog_item_count",
            "unsafe_content_count",
            "forbidden_term_count",
            "sections_present",
        ):
            _ensure_non_negative_int(getattr(self, attr), attr)

@dataclass(frozen=True, slots=True)
class RemediationClosureInput:
    """Top-level input for the closure register."""

    backlog_item_refs: tuple[RemediationClosureBacklogItemRef, ...] = ()
    evidence_summaries: tuple[RemediationClosureEvidenceSummary, ...] = ()
    closure_declarations: tuple[RemediationClosureDeclaration, ...] = ()
    review_records: tuple[RemediationClosureReviewRecord, ...] = ()
    links: tuple[RemediationClosureLink, ...] = ()
    config: RemediationClosureConfig = field(default_factory=RemediationClosureConfig)
    project_version: str = REMEDIATION_CLOSURE_VERSION
    metadata: Mapping[str, str] = field(default_factory=dict)
    generated_at: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "backlog_item_refs", _ensure_tuple_of_items(self.backlog_item_refs, RemediationClosureBacklogItemRef, "backlog_item_refs"))
        object.__setattr__(self, "evidence_summaries", _ensure_tuple_of_items(self.evidence_summaries, RemediationClosureEvidenceSummary, "evidence_summaries"))
        object.__setattr__(self, "closure_declarations", _ensure_tuple_of_items(self.closure_declarations, RemediationClosureDeclaration, "closure_declarations"))
        object.__setattr__(self, "review_records", _ensure_tuple_of_items(self.review_records, RemediationClosureReviewRecord, "review_records"))
        object.__setattr__(self, "links", _ensure_tuple_of_items(self.links, RemediationClosureLink, "links"))
        if not isinstance(self.config, RemediationClosureConfig):
            raise ValueError("config must be a RemediationClosureConfig")
        _ensure_str_with_default(self.project_version, "project_version")
        object.__setattr__(self, "metadata", _coerce_str_mapping(self.metadata))
        _ensure_timezone_aware(self.generated_at, "generated_at")


@dataclass(frozen=True, slots=True)
class RemediationClosureReport:
    """Top-level output for the closure register."""

    report_id: str = ""
    generated_at: datetime | None = None
    state: RemediationClosureState = RemediationClosureState.NOT_APPLICABLE
    project_version: str = REMEDIATION_CLOSURE_VERSION
    backlog_item_refs: tuple[RemediationClosureBacklogItemRef, ...] = ()
    evidence_summaries: tuple[RemediationClosureEvidenceSummary, ...] = ()
    closure_declarations: tuple[RemediationClosureDeclaration, ...] = ()
    review_records: tuple[RemediationClosureReviewRecord, ...] = ()
    links: tuple[RemediationClosureLink, ...] = ()
    issues: tuple[RemediationClosureIssue, ...] = ()
    closure_results: tuple[RemediationClosureResult, ...] = ()
    data_quality: RemediationClosureDataQuality = field(default_factory=RemediationClosureDataQuality)
    safety_flags: RemediationClosureSafetyFlags = field(default_factory=RemediationClosureSafetyFlags)
    reason_codes: tuple[RemediationClosureReasonCode, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)
    safety_notice: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        _ensure_str_with_default(self.report_id, "report_id")
        _ensure_timezone_aware(self.generated_at, "generated_at")
        if isinstance(self.state, str):
            try:
                object.__setattr__(self, "state", RemediationClosureState(self.state.lower()))
            except ValueError as exc:
                raise ValueError(f"state must be a valid report state: {self.state}") from exc
        if not isinstance(self.state, RemediationClosureState):
            raise ValueError("state must be a RemediationClosureState")
        _ensure_str_with_default(self.project_version, "project_version")
        for attr in (
            "backlog_item_refs",
            "evidence_summaries",
            "closure_declarations",
            "review_records",
            "links",
            "issues",
            "closure_results",
            "reason_codes",
        ):
            value = getattr(self, attr)
            if not isinstance(value, tuple):
                raise ValueError(f"{attr} must be a tuple")
        for code in self.reason_codes:
            if not isinstance(code, RemediationClosureReasonCode):
                raise ValueError("reason_codes must contain RemediationClosureReasonCode values")
        if not isinstance(self.data_quality, RemediationClosureDataQuality):
            raise ValueError("data_quality must be a RemediationClosureDataQuality")
        if not isinstance(self.safety_flags, RemediationClosureSafetyFlags):
            raise ValueError("safety_flags must be a RemediationClosureSafetyFlags")
        object.__setattr__(self, "metadata", _coerce_str_mapping(self.metadata))
        _ensure_str_with_default(self.safety_notice, "safety_notice")
        _ensure_str_with_default(self.notes, "notes")

    @classmethod
    def blocked(
        cls,
        *,
        input: "RemediationClosureInput",
        reason_code: RemediationClosureReasonCode = RemediationClosureReasonCode.UNSAFE_CONTENT,
        notes: str = "",
    ) -> "RemediationClosureReport":
        """Create a deterministic fail-closed blocked closure register report.

        Echoes caller-provided collections if available; otherwise they are empty
        tuples. Contains a single blocking issue, an empty closure_results tuple,
        and a safety_notice stating that the report is an audit-only research
        artifact and does not imply approval or readiness. No path or reference is
        opened, traversed, validated, fetched, or executed.
        """
        from datetime import datetime as _datetime
        generated_at = input.generated_at if input.generated_at is not None else _datetime.now(timezone.utc)
        if reason_code == RemediationClosureReasonCode.FORBIDDEN_TERM_PRESENT:
            safety_flags = RemediationClosureSafetyFlags(has_forbidden_terms=True)
        else:
            safety_flags = RemediationClosureSafetyFlags(has_unsafe_content=True)
        data_quality = RemediationClosureDataQuality(
            total_backlog_item_refs=len(input.backlog_item_refs),
            total_evidence_summaries=len(input.evidence_summaries),
            total_closure_declarations=len(input.closure_declarations),
            total_review_records=len(input.review_records),
            total_links=len(input.links),
        )
        return cls(
            report_id="remediation_closure_blocked",
            state=RemediationClosureState.BLOCKED,
            reason_codes=(
                RemediationClosureReasonCode.SAFETY_BLOCKED,
                reason_code,
            ),
            backlog_item_refs=tuple(input.backlog_item_refs),
            evidence_summaries=tuple(input.evidence_summaries),
            closure_declarations=tuple(input.closure_declarations),
            review_records=tuple(input.review_records),
            links=tuple(input.links),
            issues=(
                RemediationClosureIssue(
                    issue_type=RemediationClosureIssueType.UNSAFE_CONTENT,
                    severity=RemediationClosureSeverity.BLOCKING,
                    reason_codes=(reason_code.value,),
                    title="Report blocked",
                    description="Input failed safety validation.",
                ),
            ),
            closure_results=(),
            data_quality=data_quality,
            safety_flags=safety_flags,
            generated_at=generated_at,
            project_version=input.project_version,
            safety_notice=(
                "This report is a local, audit-only research artifact. "
                "Closure recorded is for human-audit tracking only and does not imply "
                "approval, certification, production readiness, trading readiness, "
                "recommendation, suitability, or signal validity."
            ),
            notes=notes,
        )
