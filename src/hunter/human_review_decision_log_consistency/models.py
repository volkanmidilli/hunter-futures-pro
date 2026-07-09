"""Frozen dataclasses for hunter.human_review_decision_log_consistency package.

MVP-42 — Local Research Human Review Decision Log Cross-Artifact Consistency.

All dataclasses are frozen. Validation runs in __post_init__. The consistency
layer only accepts caller-provided in-memory reports and references. It never
opens, follows, traverses, validates, fetches, or executes file references,
report references, artifact references, or metadata strings. The engine never
scans the filesystem, imports arbitrary modules, or introspects the repository.

Consistency reports are human-audit / research artifacts only. They are not a
production certification, not a trading readiness assessment, not a suitability
assessment, and not a trading signal or recommendation.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any

HUMAN_REVIEW_DECISION_LOG_CONSISTENCY_VERSION: str = "0.42.0-dev"

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class HumanReviewDecisionLogConsistencyState(Enum):
    """Aggregate state of a cross-artifact consistency report."""

    OK = "ok"
    DEGRADED = "degraded"
    BLOCKED = "blocked"
    NOT_APPLICABLE = "not_applicable"


class HumanReviewDecisionLogConsistencySeverity(Enum):
    """Severity of a consistency issue."""

    BLOCKING = "blocking"
    ADVISORY = "advisory"
    INFO = "info"


class HumanReviewDecisionLogConsistencyIssueType(Enum):
    """Type of engine-generated consistency issue."""

    UNSAFE_CONTENT = "unsafe_content"
    FORBIDDEN_TERM = "forbidden_term"
    MISSING_DECISION_LOG_REF = "missing_decision_log_ref"
    ORPHAN_DECISION_LOG_REF = "orphan_decision_log_ref"
    MISMATCHED_QUEUE_STATE = "mismatched_queue_state"
    MISMATCHED_QUEUE_PRIORITY = "mismatched_queue_priority"
    MISMATCHED_QUEUE_SEVERITY = "mismatched_queue_severity"
    MISMATCHED_QUEUE_REASON_CODES = "mismatched_queue_reason_codes"
    INCONSISTENT_ORPHAN_STATUS = "inconsistent_orphan_status"
    INCONSISTENT_MISSING_STATUS = "inconsistent_missing_status"
    INCONSISTENT_BLOCKED_STATUS = "inconsistent_blocked_status"
    INPUT_BLOCKED = "input_blocked"


class HumanReviewDecisionLogConsistencyReasonCode(Enum):
    """Reason codes for consistency reports."""

    OK = "ok"
    NOT_APPLICABLE = "not_applicable"
    CONSISTENCY_DEGRADED = "consistency_degraded"
    SAFETY_BLOCKED = "safety_blocked"
    UNSAFE_CONTENT = "unsafe_content"
    FORBIDDEN_TERM_PRESENT = "forbidden_term_present"
    INPUT_BLOCKED = "input_blocked"
    MISSING_DECISION_LOG_REF = "missing_decision_log_ref"
    ORPHAN_DECISION_LOG_REF = "orphan_decision_log_ref"
    MISMATCHED_QUEUE_STATE = "mismatched_queue_state"
    MISMATCHED_QUEUE_PRIORITY = "mismatched_queue_priority"
    MISMATCHED_QUEUE_SEVERITY = "mismatched_queue_severity"
    MISMATCHED_QUEUE_REASON_CODES = "mismatched_queue_reason_codes"
    INCONSISTENT_ORPHAN_STATUS = "inconsistent_orphan_status"
    INCONSISTENT_MISSING_STATUS = "inconsistent_missing_status"
    INCONSISTENT_BLOCKED_STATUS = "inconsistent_blocked_status"


class HumanReviewDecisionLogConsistencyLinkType(Enum):
    """Type of caller-provided cross-artifact link."""

    REFERENCES = "references"
    SUPERSEDES = "supersedes"
    DERIVED_FROM = "derived_from"
    RELATED_TO = "related_to"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# String constants for ergonomic public API use
# ---------------------------------------------------------------------------

OK = HumanReviewDecisionLogConsistencyReasonCode.OK.value
NOT_APPLICABLE_RC = HumanReviewDecisionLogConsistencyReasonCode.NOT_APPLICABLE.value
CONSISTENCY_DEGRADED = HumanReviewDecisionLogConsistencyReasonCode.CONSISTENCY_DEGRADED.value
SAFETY_BLOCKED = HumanReviewDecisionLogConsistencyReasonCode.SAFETY_BLOCKED.value
UNSAFE_CONTENT = HumanReviewDecisionLogConsistencyReasonCode.UNSAFE_CONTENT.value
FORBIDDEN_TERM_PRESENT = HumanReviewDecisionLogConsistencyReasonCode.FORBIDDEN_TERM_PRESENT.value
INPUT_BLOCKED = HumanReviewDecisionLogConsistencyReasonCode.INPUT_BLOCKED.value
MISSING_DECISION_LOG_REF = HumanReviewDecisionLogConsistencyReasonCode.MISSING_DECISION_LOG_REF.value
ORPHAN_DECISION_LOG_REF = HumanReviewDecisionLogConsistencyReasonCode.ORPHAN_DECISION_LOG_REF.value
MISMATCHED_QUEUE_STATE = HumanReviewDecisionLogConsistencyReasonCode.MISMATCHED_QUEUE_STATE.value
MISMATCHED_QUEUE_PRIORITY = HumanReviewDecisionLogConsistencyReasonCode.MISMATCHED_QUEUE_PRIORITY.value
MISMATCHED_QUEUE_SEVERITY = HumanReviewDecisionLogConsistencyReasonCode.MISMATCHED_QUEUE_SEVERITY.value
MISMATCHED_QUEUE_REASON_CODES = HumanReviewDecisionLogConsistencyReasonCode.MISMATCHED_QUEUE_REASON_CODES.value
INCONSISTENT_ORPHAN_STATUS = HumanReviewDecisionLogConsistencyReasonCode.INCONSISTENT_ORPHAN_STATUS.value
INCONSISTENT_MISSING_STATUS = HumanReviewDecisionLogConsistencyReasonCode.INCONSISTENT_MISSING_STATUS.value
INCONSISTENT_BLOCKED_STATUS = HumanReviewDecisionLogConsistencyReasonCode.INCONSISTENT_BLOCKED_STATUS.value

# ---------------------------------------------------------------------------
# Forbidden multi-word phrases
# ---------------------------------------------------------------------------

FORBIDDEN_HUMAN_REVIEW_DECISION_LOG_CONSISTENCY_TERMS: frozenset[str] = frozenset({
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
    """Coerce a mapping into an immutable MappingProxyType."""
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


def has_unsafe_human_review_decision_log_consistency_content(value: Any) -> bool:
    """Return True if value is not a safe string type (bytes, object, int, etc.)."""
    if value is None:
        return False
    if isinstance(value, str):
        return False
    if isinstance(value, (tuple, list)):
        return any(has_unsafe_human_review_decision_log_consistency_content(item) for item in value)
    if isinstance(value, Mapping):
        return any(
            has_unsafe_human_review_decision_log_consistency_content(k)
            or has_unsafe_human_review_decision_log_consistency_content(v)
            for k, v in value.items()
        )
    return True


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class HumanReviewDecisionLogConsistencySafetyFlags:
    """Safety flags confirming the consistency layer stays within local audit boundaries."""

    is_safe: bool = True
    audit_only: bool = True
    no_executable_actions: bool = True
    no_trading_instructions: bool = True
    no_approval_claims: bool = True
    references_opaque: bool = True
    has_unsafe_content: bool = False
    has_forbidden_terms: bool = False

    def __post_init__(self) -> None:
        positive_flags = (
            self.audit_only,
            self.no_executable_actions,
            self.no_trading_instructions,
            self.no_approval_claims,
            self.references_opaque,
        )
        if not all(positive_flags):
            raise ValueError("baseline safety invariants must be True")
        _ensure_bool(self.is_safe, "is_safe")
        _ensure_bool(self.has_unsafe_content, "has_unsafe_content")
        _ensure_bool(self.has_forbidden_terms, "has_forbidden_terms")


@dataclass(frozen=True, slots=True)
class HumanReviewDecisionLogConsistencyConfig:
    """Configuration for the cross-artifact consistency layer."""

    require_decision_for_all_queue_entries: bool = False
    queue_entry_states_that_expect_decision: tuple[str, ...] = ("open", "pending_review", "blocked")
    strict: bool = False
    empty_input_is_not_applicable: bool = True
    staleness_threshold_seconds: int = 7 * 24 * 60 * 60
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _ensure_bool(self.require_decision_for_all_queue_entries, "require_decision_for_all_queue_entries")
        object.__setattr__(
            self,
            "queue_entry_states_that_expect_decision",
            _ensure_tuple_of_str(self.queue_entry_states_that_expect_decision, "queue_entry_states_that_expect_decision"),
        )
        _ensure_bool(self.strict, "strict")
        _ensure_bool(self.empty_input_is_not_applicable, "empty_input_is_not_applicable")
        _ensure_non_negative_int(self.staleness_threshold_seconds, "staleness_threshold_seconds")
        object.__setattr__(self, "metadata", _coerce_str_mapping(self.metadata))

    def expects_decision(self, entry_state: str) -> bool:
        """Return True if the given queue entry state expects a decision log ref."""
        normalized = str(entry_state).strip().lower()
        if normalized in ("not_applicable", "suppressed"):
            return False
        return normalized in {str(state).strip().lower() for state in self.queue_entry_states_that_expect_decision}


@dataclass(frozen=True, slots=True)
class HumanReviewDecisionLogConsistencyLink:
    """Caller-provided link between a queue entry and a decision log ref."""

    link_id: str = ""
    queue_entry_id: str = ""
    decision_log_queue_entry_id: str = ""
    link_type: str = "unknown"
    generated_at: datetime | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _ensure_str_with_default(self.link_id, "link_id")
        _ensure_str_with_default(self.queue_entry_id, "queue_entry_id")
        _ensure_str_with_default(self.decision_log_queue_entry_id, "decision_log_queue_entry_id")
        _ensure_str_with_default(self.link_type, "link_type")
        _ensure_timezone_aware(self.generated_at, "generated_at")
        object.__setattr__(self, "metadata", _coerce_str_mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class HumanReviewDecisionLogConsistencyCrossReference:
    """A cross-reference between a queue entry and a decision log queue entry ref."""

    cross_reference_id: str = ""
    queue_entry_id: str = ""
    decision_log_queue_entry_id: str = ""
    queue_entry_state: str = ""
    decision_log_result_state: str = ""
    match_status: str = "matched"
    severity: str = "info"
    reason_codes: tuple[str, ...] = ()
    rationale: str = ""
    generated_at: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "cross_reference_id", _ensure_str_with_default(self.cross_reference_id, "cross_reference_id"))
        object.__setattr__(self, "queue_entry_id", _ensure_str_with_default(self.queue_entry_id, "queue_entry_id"))
        object.__setattr__(self, "decision_log_queue_entry_id", _ensure_str_with_default(self.decision_log_queue_entry_id, "decision_log_queue_entry_id"))
        object.__setattr__(self, "queue_entry_state", _ensure_str_with_default(self.queue_entry_state, "queue_entry_state"))
        object.__setattr__(self, "decision_log_result_state", _ensure_str_with_default(self.decision_log_result_state, "decision_log_result_state"))
        object.__setattr__(self, "match_status", _ensure_str_with_default(self.match_status, "match_status"))
        object.__setattr__(self, "severity", _ensure_str_with_default(self.severity, "severity"))
        object.__setattr__(self, "reason_codes", _ensure_tuple_of_str(self.reason_codes, "reason_codes"))
        object.__setattr__(self, "rationale", _ensure_str_with_default(self.rationale, "rationale"))
        _ensure_timezone_aware(self.generated_at, "generated_at")


@dataclass(frozen=True, slots=True)
class HumanReviewDecisionLogConsistencyIssue:
    """An engine-generated consistency issue."""

    issue_id: str = ""
    issue_type: str = ""
    severity: str = "info"
    reason_codes: tuple[str, ...] = ()
    source_id: str = ""
    target_id: str = ""
    queue_entry_id: str = ""
    decision_log_queue_entry_id: str = ""
    title: str = ""
    description: str = ""
    generated_at: datetime | None = None

    def __post_init__(self) -> None:
        _ensure_str_with_default(self.issue_id, "issue_id")
        _ensure_str_with_default(self.issue_type, "issue_type")
        _ensure_str_with_default(self.severity, "severity")
        object.__setattr__(self, "reason_codes", _ensure_tuple_of_str(self.reason_codes, "reason_codes"))
        _ensure_str_with_default(self.source_id, "source_id")
        _ensure_str_with_default(self.target_id, "target_id")
        _ensure_str_with_default(self.queue_entry_id, "queue_entry_id")
        _ensure_str_with_default(self.decision_log_queue_entry_id, "decision_log_queue_entry_id")
        _ensure_str_with_default(self.title, "title")
        _ensure_str_with_default(self.description, "description")
        _ensure_timezone_aware(self.generated_at, "generated_at")


@dataclass(frozen=True, slots=True)
class HumanReviewDecisionLogConsistencyDataQuality:
    """Summary counts for the consistency report."""

    total_queue_entries: int = 0
    total_decision_log_refs: int = 0
    matched_refs: int = 0
    orphan_queue_entries: int = 0
    orphan_decision_log_refs: int = 0
    mismatched_refs: int = 0
    blocking_issues: int = 0
    advisory_issues: int = 0
    info_findings: int = 0
    unsafe_content_count: int = 0
    forbidden_term_count: int = 0

    def __post_init__(self) -> None:
        _ensure_non_negative_int(self.total_queue_entries, "total_queue_entries")
        _ensure_non_negative_int(self.total_decision_log_refs, "total_decision_log_refs")
        _ensure_non_negative_int(self.matched_refs, "matched_refs")
        _ensure_non_negative_int(self.orphan_queue_entries, "orphan_queue_entries")
        _ensure_non_negative_int(self.orphan_decision_log_refs, "orphan_decision_log_refs")
        _ensure_non_negative_int(self.mismatched_refs, "mismatched_refs")
        _ensure_non_negative_int(self.blocking_issues, "blocking_issues")
        _ensure_non_negative_int(self.advisory_issues, "advisory_issues")
        _ensure_non_negative_int(self.info_findings, "info_findings")
        _ensure_non_negative_int(self.unsafe_content_count, "unsafe_content_count")
        _ensure_non_negative_int(self.forbidden_term_count, "forbidden_term_count")


@dataclass(frozen=True, slots=True)
class HumanReviewDecisionLogConsistencyInput:
    """Input for the cross-artifact consistency engine."""

    queue_report: "HumanReviewQueueReport" = field(default_factory=lambda: _empty_queue_report())
    decision_log_report: "HumanReviewDecisionLogReport" = field(default_factory=lambda: _empty_decision_log_report())
    config: HumanReviewDecisionLogConsistencyConfig = field(
        default_factory=HumanReviewDecisionLogConsistencyConfig
    )
    project_version: str = HUMAN_REVIEW_DECISION_LOG_CONSISTENCY_VERSION
    metadata: Mapping[str, str] = field(default_factory=dict)
    generated_at: datetime | None = None
    links: tuple[HumanReviewDecisionLogConsistencyLink, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "links", _ensure_tuple_of_items(self.links, HumanReviewDecisionLogConsistencyLink, "links"))
        _ensure_str_with_default(self.project_version, "project_version")
        object.__setattr__(self, "metadata", _coerce_str_mapping(self.metadata))
        _ensure_timezone_aware(self.generated_at, "generated_at")


@dataclass(frozen=True, slots=True)
class HumanReviewDecisionLogConsistencyReport:
    """A local, audit-only cross-artifact consistency report."""

    report_id: str = ""
    generated_at: datetime | None = None
    state: HumanReviewDecisionLogConsistencyState = HumanReviewDecisionLogConsistencyState.NOT_APPLICABLE
    project_version: str = HUMAN_REVIEW_DECISION_LOG_CONSISTENCY_VERSION
    queue_report_id: str = ""
    decision_log_report_id: str = ""
    cross_references: tuple[HumanReviewDecisionLogConsistencyCrossReference, ...] = ()
    issues: tuple[HumanReviewDecisionLogConsistencyIssue, ...] = ()
    data_quality: HumanReviewDecisionLogConsistencyDataQuality = field(
        default_factory=HumanReviewDecisionLogConsistencyDataQuality
    )
    safety_flags: HumanReviewDecisionLogConsistencySafetyFlags = field(
        default_factory=HumanReviewDecisionLogConsistencySafetyFlags
    )
    reason_codes: tuple[HumanReviewDecisionLogConsistencyReasonCode, ...] = ()
    safety_notice: str = ""
    metadata: Mapping[str, str] = field(default_factory=dict)
    notes: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.state, HumanReviewDecisionLogConsistencyState):
            raise ValueError("state must be a HumanReviewDecisionLogConsistencyState")
        object.__setattr__(
            self, "cross_references", _ensure_tuple_of_items(self.cross_references, HumanReviewDecisionLogConsistencyCrossReference, "cross_references")
        )
        object.__setattr__(self, "issues", _ensure_tuple_of_items(self.issues, HumanReviewDecisionLogConsistencyIssue, "issues"))
        object.__setattr__(
            self, "reason_codes", _ensure_tuple_of_items(self.reason_codes, HumanReviewDecisionLogConsistencyReasonCode, "reason_codes")
        )
        object.__setattr__(self, "metadata", _coerce_str_mapping(self.metadata))

    @property
    def queue_entry_to_decision_log_refs(self) -> tuple[HumanReviewDecisionLogConsistencyCrossReference, ...]:
        """Matched cross-references."""
        return tuple(cr for cr in self.cross_references if cr.match_status == "matched")

    @property
    def orphan_queue_entries(self) -> tuple[HumanReviewDecisionLogConsistencyCrossReference, ...]:
        """Queue entries with no decision log ref."""
        return tuple(cr for cr in self.cross_references if cr.match_status == "orphan_queue")

    @property
    def orphan_decision_log_refs(self) -> tuple[HumanReviewDecisionLogConsistencyCrossReference, ...]:
        """Decision log refs with no matching queue entry."""
        return tuple(cr for cr in self.cross_references if cr.match_status == "orphan_decision_log")

    @property
    def mismatched_refs(self) -> tuple[HumanReviewDecisionLogConsistencyCrossReference, ...]:
        """Cross-references with mismatch status."""
        return tuple(cr for cr in self.cross_references if cr.match_status == "mismatched")


SAFETY_NOTICE = (
    "This report is a local, audit-only research artifact. "
    "Cross-artifact consistency checks are for human-audit review only and do not imply "
    "approval, certification, production readiness, deployment readiness, trading readiness, "
    "recommendation, suitability assessment, signal validity, task assignment, task completion, "
    "or executable remediation plan."
)


def _empty_queue_report() -> "HumanReviewQueueReport":
    """Return an empty queue report for default input construction."""
    from hunter.human_review_queue.models import HumanReviewQueueReport

    return HumanReviewQueueReport()


def _empty_decision_log_report() -> "HumanReviewDecisionLogReport":
    """Return an empty decision log report for default input construction."""
    from hunter.human_review_decision_log.models import HumanReviewDecisionLogReport

    return HumanReviewDecisionLogReport()
