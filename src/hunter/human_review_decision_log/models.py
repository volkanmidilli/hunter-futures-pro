"""Frozen dataclasses for hunter.human_review_decision_log package.

MVP-41 — Local Research Human Review Decision Log.

All dataclasses are frozen. Validation runs in __post_init__. The decision log
only accepts caller-provided in-memory records and references. It never opens,
follows, traverses, validates, fetches, or executes file references, report
references, artifact references, or metadata strings. The engine never scans
the filesystem, imports arbitrary modules, or introspects the repository.

Decision records are human-audit / research artifacts only. They are not a
production certification, not a trading readiness assessment, not a suitability
assessment, and not a trading signal or recommendation.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
from json import dumps
from types import MappingProxyType
from typing import Any

HUMAN_REVIEW_DECISION_LOG_VERSION: str = "0.41.0-dev"

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class HumanReviewDecisionLogState(Enum):
    """Aggregate state of a human review decision log report."""

    OK = "ok"
    DEGRADED = "degraded"
    BLOCKED = "blocked"
    NOT_APPLICABLE = "not_applicable"

class HumanReviewDecisionSeverity(Enum):
    """Severity of a decision log issue."""

    BLOCKING = "blocking"
    ADVISORY = "advisory"
    INFO = "info"

class HumanReviewDecisionState(Enum):
    """State of a single decision result for a queue entry."""

    LOGGED = "logged"
    MISSING = "missing"
    INCOMPLETE = "incomplete"
    PENDING_REVIEW = "pending_review"
    REJECTED = "rejected"
    DISPUTED = "disputed"
    STALE = "stale"
    DUPLICATE = "duplicate"
    ORPHANED = "orphaned"
    SUPERSEDED = "superseded"
    NOT_APPLICABLE = "not_applicable"
    BLOCKED = "blocked"

class HumanReviewDecisionOutcome(Enum):
    """Caller-provided outcome of a human review decision."""

    ACCEPTED_FOR_AUDIT_LOG = "accepted_for_audit_log"
    REJECTED_FOR_AUDIT_LOG = "rejected_for_audit_log"
    NEEDS_MORE_REVIEW = "needs_more_review"
    DISPUTED = "disputed"
    DEFERRED = "deferred"
    NOT_APPLICABLE = "not_applicable"
    SUPERSEDED = "superseded"
    UNKNOWN = "unknown"

class HumanReviewDecisionValidity(Enum):
    """Validity assessment of a decision for audit log purposes."""

    VALID_FOR_AUDIT_LOG = "valid_for_audit_log"
    INVALID_FOR_AUDIT_LOG = "invalid_for_audit_log"
    PARTIAL = "partial"
    PENDING_REVIEW = "pending_review"
    DISPUTED = "disputed"
    STALE = "stale"
    NOT_APPLICABLE = "not_applicable"

class HumanReviewDecisionLinkType(Enum):
    """Type of a caller-provided link between decisions or records."""

    REFERENCES = "references"
    SUPERSEDES = "supersedes"
    DERIVED_FROM = "derived_from"
    RELATED_TO = "related_to"
    UNKNOWN = "unknown"

class HumanReviewDecisionIssueType(Enum):
    """Type of engine-generated issue."""

    UNSAFE_CONTENT = "unsafe_content"
    FORBIDDEN_TERM = "forbidden_term"
    DUPLICATE_QUEUE_ENTRY_ID = "duplicate_queue_entry_id"
    DUPLICATE_DECISION_ID = "duplicate_decision_id"
    DUPLICATE_LINK_ID = "duplicate_link_id"
    SEMANTIC_DUPLICATE_DECISION = "semantic_duplicate_decision"
    ORPHAN_DECISION = "orphan_decision"
    ORPHAN_LINK = "orphan_link"
    MISSING_DECISION = "missing_decision"
    CONFLICTING_DECISION = "conflicting_decision"
    CONFLICTING_OUTCOME = "conflicting_outcome"
    STALE_QUEUE_ENTRY = "stale_queue_entry"
    STALE_DECISION = "stale_decision"
    MISSING_REVIEWER = "missing_reviewer"
    MISSING_DECIDED_AT = "missing_decided_at"
    MISSING_RATIONALE = "missing_rationale"
    MISSING_OUTCOME = "missing_outcome"
    MISSING_QUEUE_ENTRY_ID = "missing_queue_entry_id"
    OUTCOME_MISMATCH = "outcome_mismatch"

class HumanReviewDecisionReasonCode(Enum):
    """Reason codes for decision log entries and reports."""

    OK = "ok"
    NOT_APPLICABLE = "not_applicable"
    DECISION_LOGGED = "decision_logged"
    CONSISTENCY_DEGRADED = "consistency_degraded"
    SAFETY_BLOCKED = "safety_blocked"
    UNSAFE_CONTENT = "unsafe_content"
    FORBIDDEN_TERM_PRESENT = "forbidden_term_present"
    INVALID_INPUT_DATA = "invalid_input_data"
    DUPLICATE_QUEUE_ENTRY_ID = "duplicate_queue_entry_id"
    DUPLICATE_DECISION_ID = "duplicate_decision_id"
    DUPLICATE_LINK_ID = "duplicate_link_id"
    SEMANTIC_DUPLICATE_DECISION = "semantic_duplicate_decision"
    ORPHAN_DECISION = "orphan_decision"
    ORPHAN_LINK = "orphan_link"
    MISSING_DECISION = "missing_decision"
    CONFLICTING_DECISION = "conflicting_decision"
    CONFLICTING_OUTCOME = "conflicting_outcome"
    STALE_QUEUE_ENTRY = "stale_queue_entry"
    STALE_DECISION = "stale_decision"
    MISSING_REVIEWER = "missing_reviewer"
    MISSING_DECIDED_AT = "missing_decided_at"
    MISSING_RATIONALE = "missing_rationale"
    MISSING_OUTCOME = "missing_outcome"
    MISSING_QUEUE_ENTRY_ID = "missing_queue_entry_id"
    OUTCOME_MISMATCH = "outcome_mismatch"
    ADVISORY_FINDING = "advisory_finding"
    INFO_FINDING = "info_finding"
    BLOCKING_FINDING = "blocking_finding"

# ---------------------------------------------------------------------------
# String constants for ergonomic public API use
# ---------------------------------------------------------------------------

OK = HumanReviewDecisionReasonCode.OK.value
NOT_APPLICABLE_RC = HumanReviewDecisionReasonCode.NOT_APPLICABLE.value
DECISION_LOGGED = HumanReviewDecisionReasonCode.DECISION_LOGGED.value
CONSISTENCY_DEGRADED = HumanReviewDecisionReasonCode.CONSISTENCY_DEGRADED.value
SAFETY_BLOCKED = HumanReviewDecisionReasonCode.SAFETY_BLOCKED.value
UNSAFE_CONTENT = HumanReviewDecisionReasonCode.UNSAFE_CONTENT.value
FORBIDDEN_TERM_PRESENT = HumanReviewDecisionReasonCode.FORBIDDEN_TERM_PRESENT.value
INVALID_INPUT_DATA = HumanReviewDecisionReasonCode.INVALID_INPUT_DATA.value
DUPLICATE_QUEUE_ENTRY_ID = HumanReviewDecisionReasonCode.DUPLICATE_QUEUE_ENTRY_ID.value
DUPLICATE_DECISION_ID = HumanReviewDecisionReasonCode.DUPLICATE_DECISION_ID.value
DUPLICATE_LINK_ID = HumanReviewDecisionReasonCode.DUPLICATE_LINK_ID.value
SEMANTIC_DUPLICATE_DECISION = HumanReviewDecisionReasonCode.SEMANTIC_DUPLICATE_DECISION.value
ORPHAN_DECISION = HumanReviewDecisionReasonCode.ORPHAN_DECISION.value
ORPHAN_LINK = HumanReviewDecisionReasonCode.ORPHAN_LINK.value
MISSING_DECISION = HumanReviewDecisionReasonCode.MISSING_DECISION.value
CONFLICTING_DECISION = HumanReviewDecisionReasonCode.CONFLICTING_DECISION.value
CONFLICTING_OUTCOME = HumanReviewDecisionReasonCode.CONFLICTING_OUTCOME.value
STALE_QUEUE_ENTRY = HumanReviewDecisionReasonCode.STALE_QUEUE_ENTRY.value
STALE_DECISION = HumanReviewDecisionReasonCode.STALE_DECISION.value
MISSING_REVIEWER = HumanReviewDecisionReasonCode.MISSING_REVIEWER.value
MISSING_DECIDED_AT = HumanReviewDecisionReasonCode.MISSING_DECIDED_AT.value
MISSING_RATIONALE = HumanReviewDecisionReasonCode.MISSING_RATIONALE.value
MISSING_OUTCOME = HumanReviewDecisionReasonCode.MISSING_OUTCOME.value
MISSING_QUEUE_ENTRY_ID = HumanReviewDecisionReasonCode.MISSING_QUEUE_ENTRY_ID.value
OUTCOME_MISMATCH = HumanReviewDecisionReasonCode.OUTCOME_MISMATCH.value
ADVISORY_FINDING = HumanReviewDecisionReasonCode.ADVISORY_FINDING.value
INFO_FINDING = HumanReviewDecisionReasonCode.INFO_FINDING.value
BLOCKING_FINDING = HumanReviewDecisionReasonCode.BLOCKING_FINDING.value

# ---------------------------------------------------------------------------
# Forbidden multi-word phrases
# ---------------------------------------------------------------------------

# Multi-word forbidden phrases only.
#
# Uses case-insensitive substring search against caller-provided metadata and
# all textual fields. All entries MUST be multi-word phrases. Single-word terms
# are intentionally excluded because they produce false positives in benign
# audit text (e.g. "pending approval from security team", "certification body",
# "no recommendation needed", "signal processing", "no signal detected",
# "assign a reviewer", "manual note for audit", "task queue", "task note").
FORBIDDEN_HUMAN_REVIEW_DECISION_TERMS: frozenset[str] = frozenset({
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
    "assign to",
    "create ticket",
    "open jira",
    "send email",
    "notify team",
    "auto assign",
    "task assignment",
    "task complete",
    "task completed",
    "decision approved",
    "decision certified",
    "ready for trading",
    "approved for production",
})

# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _ensure_str(value: Any, field_name: str) -> str:
    """Validate that value is a string."""
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
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

def has_unsafe_human_review_decision_content(value: Any) -> bool:
    """Return True if value is not a safe string type (bytes, object, int, etc.)."""
    if value is None:
        return False
    if isinstance(value, str):
        return False
    if isinstance(value, (tuple, list)):
        return any(has_unsafe_human_review_decision_content(item) for item in value)
    if isinstance(value, Mapping):
        return any(
            has_unsafe_human_review_decision_content(k)
            or has_unsafe_human_review_decision_content(v)
            for k, v in value.items()
        )
    return True

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class HumanReviewDecisionLogSafetyFlags:
    """Safety flags confirming the decision log stays within local audit boundaries."""

    no_executable_actions: bool = True
    no_trading_instructions: bool = True
    no_approval_claims: bool = True
    no_automated_remediation: bool = True
    no_automatic_assignment: bool = True
    no_task_completion_claims: bool = True
    references_opaque: bool = True
    audit_only: bool = True
    decision_logged_not_approval: bool = True
    has_unsafe_content: bool = False
    has_forbidden_terms: bool = False

    def __post_init__(self) -> None:
        positive_flags = (
            self.no_executable_actions,
            self.no_trading_instructions,
            self.no_approval_claims,
            self.no_automated_remediation,
            self.no_automatic_assignment,
            self.no_task_completion_claims,
            self.references_opaque,
            self.audit_only,
            self.decision_logged_not_approval,
        )
        if not all(positive_flags):
            raise ValueError("baseline safety invariants must be True")
        _ensure_bool(self.has_unsafe_content, "has_unsafe_content")
        _ensure_bool(self.has_forbidden_terms, "has_forbidden_terms")

    @property
    def is_safe(self) -> bool:
        """True when the report passes all safety boundary checks."""
        return not self.has_unsafe_content and not self.has_forbidden_terms


@dataclass(frozen=True, slots=True)
class HumanReviewDecisionLogConfig:
    """Configuration for the human review decision log."""

    strict: bool = False
    require_decision_for_all: bool = True
    forbid_action_terms: bool = True
    staleness_threshold_seconds: int = 2_592_000  # 30 days
    empty_input_is_not_applicable: bool = True
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _ensure_bool(self.strict, "strict")
        _ensure_bool(self.require_decision_for_all, "require_decision_for_all")
        _ensure_bool(self.forbid_action_terms, "forbid_action_terms")
        _ensure_bool(self.empty_input_is_not_applicable, "empty_input_is_not_applicable")
        _ensure_non_negative_int(self.staleness_threshold_seconds, "staleness_threshold_seconds")
        object.__setattr__(self, "metadata", _coerce_str_mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class HumanReviewQueueEntryRef:
    """Caller-provided queue entry reference for decision log processing."""

    queue_entry_id: str = ""
    source_id: str = ""
    source_kind: str = ""
    record_id: str = ""
    entry_state: str = ""
    priority: str = ""
    severity: str = ""
    reason_codes: tuple[str, ...] = ()
    generated_at: datetime | None = None
    artifact_ref: str = ""  # opaque reference string
    report_ref: str = ""  # opaque reference string
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _ensure_str_with_default(self.queue_entry_id, "queue_entry_id")
        _ensure_str_with_default(self.source_id, "source_id")
        _ensure_str_with_default(self.source_kind, "source_kind")
        _ensure_str_with_default(self.record_id, "record_id")
        _ensure_str_with_default(self.entry_state, "entry_state")
        _ensure_str_with_default(self.priority, "priority")
        _ensure_str_with_default(self.severity, "severity")
        object.__setattr__(self, "reason_codes", _ensure_tuple_of_str(self.reason_codes, "reason_codes"))
        _ensure_timezone_aware(self.generated_at, "generated_at")
        _ensure_str_with_default(self.artifact_ref, "artifact_ref")
        _ensure_str_with_default(self.report_ref, "report_ref")
        object.__setattr__(self, "metadata", _coerce_str_mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class HumanReviewDecisionRecord:
    """Caller-provided human review decision record."""

    decision_id: str = ""
    queue_entry_id: str = ""
    reviewer: str = ""
    decided_at: datetime | None = None
    outcome: str = "unknown"  # HumanReviewDecisionOutcome
    rationale: str = ""
    reason_codes: tuple[str, ...] = ()
    generated_at: datetime | None = None
    artifact_ref: str = ""  # opaque reference string
    report_ref: str = ""  # opaque reference string
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _ensure_str_with_default(self.decision_id, "decision_id")
        _ensure_str_with_default(self.queue_entry_id, "queue_entry_id")
        _ensure_str_with_default(self.reviewer, "reviewer")
        _ensure_timezone_aware(self.decided_at, "decided_at")
        _ensure_str_with_default(self.outcome, "outcome")
        _ensure_str_with_default(self.rationale, "rationale")
        object.__setattr__(self, "reason_codes", _ensure_tuple_of_str(self.reason_codes, "reason_codes"))
        _ensure_timezone_aware(self.generated_at, "generated_at")
        _ensure_str_with_default(self.artifact_ref, "artifact_ref")
        _ensure_str_with_default(self.report_ref, "report_ref")
        object.__setattr__(self, "metadata", _coerce_str_mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class HumanReviewDecisionLink:
    """Caller-provided link between decisions or records."""

    link_id: str = ""
    source_id: str = ""
    target_id: str = ""
    link_type: str = "unknown"  # HumanReviewDecisionLinkType
    generated_at: datetime | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _ensure_str_with_default(self.link_id, "link_id")
        _ensure_str_with_default(self.source_id, "source_id")
        _ensure_str_with_default(self.target_id, "target_id")
        _ensure_str_with_default(self.link_type, "link_type")
        _ensure_timezone_aware(self.generated_at, "generated_at")
        object.__setattr__(self, "metadata", _coerce_str_mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class HumanReviewDecisionIssue:
    """An engine-generated issue detected while building the decision log."""

    issue_id: str = ""
    issue_type: str = ""
    severity: str = "info"
    reason_codes: tuple[str, ...] = ()
    title: str = ""
    description: str = ""
    source_id: str = ""
    target_id: str = ""
    decision_id: str = ""
    queue_entry_id: str = ""
    generated_at: datetime | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _ensure_str_with_default(self.issue_id, "issue_id")
        _ensure_str_with_default(self.issue_type, "issue_type")
        _ensure_str_with_default(self.severity, "severity")
        object.__setattr__(self, "reason_codes", _ensure_tuple_of_str(self.reason_codes, "reason_codes"))
        _ensure_str_with_default(self.title, "title")
        _ensure_str_with_default(self.description, "description")
        _ensure_str_with_default(self.source_id, "source_id")
        _ensure_str_with_default(self.target_id, "target_id")
        _ensure_str_with_default(self.decision_id, "decision_id")
        _ensure_str_with_default(self.queue_entry_id, "queue_entry_id")
        _ensure_timezone_aware(self.generated_at, "generated_at")
        object.__setattr__(self, "metadata", _coerce_str_mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class HumanReviewDecisionResult:
    """A single decision result for a queue entry."""

    decision_result_id: str = ""
    queue_entry_id: str = ""
    decision_ids: tuple[str, ...] = ()
    decision_state: str = "missing"  # HumanReviewDecisionState
    decision_outcome: str = "unknown"  # HumanReviewDecisionOutcome
    decision_validity: str = "invalid_for_audit_log"  # HumanReviewDecisionValidity
    severity: str = "info"  # HumanReviewDecisionSeverity
    reason_codes: tuple[str, ...] = ()
    reviewer: str = ""
    decided_at: datetime | None = None
    rationale: str = ""
    generated_at: datetime | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _ensure_str_with_default(self.decision_result_id, "decision_result_id")
        _ensure_str_with_default(self.queue_entry_id, "queue_entry_id")
        object.__setattr__(self, "decision_ids", _ensure_tuple_of_str(self.decision_ids, "decision_ids"))
        _ensure_str_with_default(self.decision_state, "decision_state")
        _ensure_str_with_default(self.decision_outcome, "decision_outcome")
        _ensure_str_with_default(self.decision_validity, "decision_validity")
        _ensure_str_with_default(self.severity, "severity")
        object.__setattr__(self, "reason_codes", _ensure_tuple_of_str(self.reason_codes, "reason_codes"))
        _ensure_str_with_default(self.reviewer, "reviewer")
        _ensure_timezone_aware(self.decided_at, "decided_at")
        _ensure_str_with_default(self.rationale, "rationale")
        _ensure_timezone_aware(self.generated_at, "generated_at")
        object.__setattr__(self, "metadata", _coerce_str_mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class HumanReviewDecisionLogDataQuality:
    """Summary counts for the decision log report."""

    total_queue_entry_refs: int = 0
    total_decision_records: int = 0
    total_links: int = 0
    total_issues: int = 0
    total_decision_results: int = 0
    duplicate_queue_entry_id_count: int = 0
    duplicate_decision_id_count: int = 0
    duplicate_link_id_count: int = 0
    semantic_duplicate_decision_count: int = 0
    orphan_decision_count: int = 0
    orphan_link_count: int = 0
    missing_decision_count: int = 0
    conflicting_decision_count: int = 0
    conflicting_outcome_count: int = 0
    stale_queue_entry_count: int = 0
    stale_decision_count: int = 0
    missing_reviewer_count: int = 0
    missing_decided_at_count: int = 0
    missing_rationale_count: int = 0
    missing_outcome_count: int = 0
    missing_queue_entry_id_count: int = 0
    outcome_mismatch_count: int = 0
    unsafe_content_count: int = 0
    forbidden_term_count: int = 0
    blocking_count: int = 0
    advisory_count: int = 0
    info_count: int = 0
    logged_count: int = 0
    pending_review_count: int = 0
    rejected_count: int = 0
    disputed_count: int = 0
    stale_count: int = 0
    duplicate_count: int = 0
    orphaned_count: int = 0
    superseded_count: int = 0
    not_applicable_count: int = 0
    incomplete_count: int = 0
    missing_count: int = 0
    blocked_count: int = 0

    def __post_init__(self) -> None:
        _ensure_non_negative_int(self.total_queue_entry_refs, "total_queue_entry_refs")
        _ensure_non_negative_int(self.total_decision_records, "total_decision_records")
        _ensure_non_negative_int(self.total_links, "total_links")
        _ensure_non_negative_int(self.total_issues, "total_issues")
        _ensure_non_negative_int(self.total_decision_results, "total_decision_results")
        _ensure_non_negative_int(self.duplicate_queue_entry_id_count, "duplicate_queue_entry_id_count")
        _ensure_non_negative_int(self.duplicate_decision_id_count, "duplicate_decision_id_count")
        _ensure_non_negative_int(self.duplicate_link_id_count, "duplicate_link_id_count")
        _ensure_non_negative_int(self.semantic_duplicate_decision_count, "semantic_duplicate_decision_count")
        _ensure_non_negative_int(self.orphan_decision_count, "orphan_decision_count")
        _ensure_non_negative_int(self.orphan_link_count, "orphan_link_count")
        _ensure_non_negative_int(self.missing_decision_count, "missing_decision_count")
        _ensure_non_negative_int(self.conflicting_decision_count, "conflicting_decision_count")
        _ensure_non_negative_int(self.conflicting_outcome_count, "conflicting_outcome_count")
        _ensure_non_negative_int(self.stale_queue_entry_count, "stale_queue_entry_count")
        _ensure_non_negative_int(self.stale_decision_count, "stale_decision_count")
        _ensure_non_negative_int(self.missing_reviewer_count, "missing_reviewer_count")
        _ensure_non_negative_int(self.missing_decided_at_count, "missing_decided_at_count")
        _ensure_non_negative_int(self.missing_rationale_count, "missing_rationale_count")
        _ensure_non_negative_int(self.missing_outcome_count, "missing_outcome_count")
        _ensure_non_negative_int(self.missing_queue_entry_id_count, "missing_queue_entry_id_count")
        _ensure_non_negative_int(self.outcome_mismatch_count, "outcome_mismatch_count")
        _ensure_non_negative_int(self.unsafe_content_count, "unsafe_content_count")
        _ensure_non_negative_int(self.forbidden_term_count, "forbidden_term_count")
        _ensure_non_negative_int(self.blocking_count, "blocking_count")
        _ensure_non_negative_int(self.advisory_count, "advisory_count")
        _ensure_non_negative_int(self.info_count, "info_count")
        _ensure_non_negative_int(self.logged_count, "logged_count")
        _ensure_non_negative_int(self.pending_review_count, "pending_review_count")
        _ensure_non_negative_int(self.rejected_count, "rejected_count")
        _ensure_non_negative_int(self.disputed_count, "disputed_count")
        _ensure_non_negative_int(self.stale_count, "stale_count")
        _ensure_non_negative_int(self.duplicate_count, "duplicate_count")
        _ensure_non_negative_int(self.orphaned_count, "orphaned_count")
        _ensure_non_negative_int(self.superseded_count, "superseded_count")
        _ensure_non_negative_int(self.not_applicable_count, "not_applicable_count")
        _ensure_non_negative_int(self.incomplete_count, "incomplete_count")
        _ensure_non_negative_int(self.missing_count, "missing_count")
        _ensure_non_negative_int(self.blocked_count, "blocked_count")


@dataclass(frozen=True, slots=True)
class HumanReviewDecisionLogInput:
    """Input for the human review decision log engine."""

    queue_entry_refs: tuple[HumanReviewQueueEntryRef, ...] = ()
    decision_records: tuple[HumanReviewDecisionRecord, ...] = ()
    links: tuple[HumanReviewDecisionLink, ...] = ()
    config: HumanReviewDecisionLogConfig = field(default_factory=HumanReviewDecisionLogConfig)
    project_version: str = HUMAN_REVIEW_DECISION_LOG_VERSION
    metadata: Mapping[str, str] = field(default_factory=dict)
    generated_at: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "queue_entry_refs",
            _ensure_tuple_of_items(self.queue_entry_refs, HumanReviewQueueEntryRef, "queue_entry_refs"),
        )
        object.__setattr__(
            self,
            "decision_records",
            _ensure_tuple_of_items(self.decision_records, HumanReviewDecisionRecord, "decision_records"),
        )
        object.__setattr__(
            self,
            "links",
            _ensure_tuple_of_items(self.links, HumanReviewDecisionLink, "links"),
        )
        _ensure_str_with_default(self.project_version, "project_version")
        object.__setattr__(self, "metadata", _coerce_str_mapping(self.metadata))
        _ensure_timezone_aware(self.generated_at, "generated_at")


SAFETY_NOTICE = (
    "This report is a local, audit-only research artifact. "
    "Decision logged is for human-audit tracking only and does not imply "
    "approval, certification, production readiness, deployment readiness, "
    "trading readiness, recommendation, suitability assessment, signal "
    "validity, task assignment, task completion, or executable remediation plan."
)


def _blocked_report_id(
    input: "HumanReviewDecisionLogInput",
    generated_at: datetime,
    reason_code: HumanReviewDecisionReasonCode,
    notes: str,
) -> str:
    """Return a deterministic, non-empty report_id for blocked reports."""
    queue_entry_ids = sorted(
        {str(ref.queue_entry_id).strip() for ref in input.queue_entry_refs if ref.queue_entry_id}
    )
    decision_ids = sorted(
        {str(rec.decision_id).strip() for rec in input.decision_records if rec.decision_id}
    )
    link_ids = sorted(
        {str(lnk.link_id).strip() for lnk in input.links if lnk.link_id}
    )
    payload = {
        "state": HumanReviewDecisionLogState.BLOCKED.value,
        "project_version": input.project_version,
        "generated_at": generated_at.isoformat(),
        "reason_code": reason_code.value,
        "notes": notes,
        "queue_entry_ids": queue_entry_ids,
        "decision_ids": decision_ids,
        "link_ids": link_ids,
    }
    digest = sha256(
        dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()
    return f"blocked-human-review-decision-log-{digest[:16]}"


@dataclass(frozen=True, slots=True)
class HumanReviewDecisionLogReport:
    """A local, audit-only human review decision log report."""

    report_id: str = ""
    generated_at: datetime | None = None
    state: HumanReviewDecisionLogState = HumanReviewDecisionLogState.NOT_APPLICABLE
    project_version: str = HUMAN_REVIEW_DECISION_LOG_VERSION
    queue_entry_refs: tuple[HumanReviewQueueEntryRef, ...] = ()
    decision_records: tuple[HumanReviewDecisionRecord, ...] = ()
    links: tuple[HumanReviewDecisionLink, ...] = ()
    issues: tuple[HumanReviewDecisionIssue, ...] = ()
    decision_results: tuple[HumanReviewDecisionResult, ...] = ()
    data_quality: HumanReviewDecisionLogDataQuality = field(default_factory=HumanReviewDecisionLogDataQuality)
    safety_flags: HumanReviewDecisionLogSafetyFlags = field(default_factory=HumanReviewDecisionLogSafetyFlags)
    reason_codes: tuple[HumanReviewDecisionReasonCode, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)
    safety_notice: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.state, HumanReviewDecisionLogState):
            raise ValueError("state must be a HumanReviewDecisionLogState")
        object.__setattr__(
            self,
            "queue_entry_refs",
            _ensure_tuple_of_items(self.queue_entry_refs, HumanReviewQueueEntryRef, "queue_entry_refs"),
        )
        object.__setattr__(
            self,
            "decision_records",
            _ensure_tuple_of_items(self.decision_records, HumanReviewDecisionRecord, "decision_records"),
        )
        object.__setattr__(
            self,
            "links",
            _ensure_tuple_of_items(self.links, HumanReviewDecisionLink, "links"),
        )
        object.__setattr__(
            self,
            "issues",
            _ensure_tuple_of_items(self.issues, HumanReviewDecisionIssue, "issues"),
        )
        object.__setattr__(
            self,
            "decision_results",
            _ensure_tuple_of_items(self.decision_results, HumanReviewDecisionResult, "decision_results"),
        )
        object.__setattr__(
            self,
            "reason_codes",
            _ensure_tuple_of_items(self.reason_codes, HumanReviewDecisionReasonCode, "reason_codes"),
        )
        object.__setattr__(self, "metadata", _coerce_str_mapping(self.metadata))

    @classmethod
    def blocked(
        cls,
        *,
        input: "HumanReviewDecisionLogInput",
        reason_code: HumanReviewDecisionReasonCode = HumanReviewDecisionReasonCode.UNSAFE_CONTENT,
        notes: str = "",
    ) -> "HumanReviewDecisionLogReport":
        """Return a minimal blocked report with safety flags set."""
        generated_at = input.generated_at if input.generated_at is not None else datetime.now(timezone.utc)
        safety_flags = HumanReviewDecisionLogSafetyFlags(
            has_unsafe_content=reason_code == HumanReviewDecisionReasonCode.UNSAFE_CONTENT,
            has_forbidden_terms=reason_code == HumanReviewDecisionReasonCode.FORBIDDEN_TERM_PRESENT,
        )
        return cls(
            report_id=_blocked_report_id(input, generated_at, reason_code, notes),
            generated_at=generated_at,
            state=HumanReviewDecisionLogState.BLOCKED,
            project_version=input.project_version,
            queue_entry_refs=input.queue_entry_refs,
            decision_records=input.decision_records,
            links=input.links,
            issues=(),
            decision_results=(),
            data_quality=HumanReviewDecisionLogDataQuality(
                total_queue_entry_refs=len(input.queue_entry_refs),
                total_decision_records=len(input.decision_records),
                total_links=len(input.links),
                unsafe_content_count=1 if reason_code == HumanReviewDecisionReasonCode.UNSAFE_CONTENT else 0,
                forbidden_term_count=1 if reason_code == HumanReviewDecisionReasonCode.FORBIDDEN_TERM_PRESENT else 0,
            ),
            safety_flags=safety_flags,
            reason_codes=(reason_code,),
            metadata=input.metadata,
            safety_notice=SAFETY_NOTICE,
            notes=notes,
        )

