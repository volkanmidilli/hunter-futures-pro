"""Frozen dataclasses for hunter.human_review_queue package.

MVP-40 — Local Research Human Review Queue.

All dataclasses are frozen. Validation runs in __post_init__. The queue only
accepts caller-provided in-memory records and references. It never opens,
follows, traverses, validates, fetches, or executes file references, report
references, artifact references, or metadata strings. The engine never scans
the filesystem, imports arbitrary modules, or introspects the repository.

Human review queue entries are human-audit / research artifacts only. They are
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

HUMAN_REVIEW_QUEUE_VERSION: str = "0.40.0-dev"


class HumanReviewQueueState(Enum):
    """Aggregate state of a human review queue report."""

    OK = "ok"
    DEGRADED = "degraded"
    BLOCKED = "blocked"
    NOT_APPLICABLE = "not_applicable"


class HumanReviewQueueSeverity(Enum):
    """Severity of a human review queue issue or entry."""

    BLOCKING = "blocking"
    ADVISORY = "advisory"
    INFO = "info"


class HumanReviewQueueReasonCode(Enum):
    """Reason codes for human review queue entries and reports."""

    OK = "ok"
    NOT_APPLICABLE = "not_applicable"
    CONSISTENCY_DEGRADED = "consistency_degraded"
    SAFETY_BLOCKED = "safety_blocked"
    UNSAFE_CONTENT = "unsafe_content"
    FORBIDDEN_TERM_PRESENT = "forbidden_term_present"
    DUPLICATE_SOURCE_ID = "duplicate_source_id"
    DUPLICATE_QUEUE_ENTRY = "duplicate_queue_entry"
    ORPHAN_RELATED_RECORD = "orphan_related_record"
    STALE_SOURCE_RECORD = "stale_source_record"
    BLOCKING_SEVERITY = "blocking_severity"
    ADVISORY_SEVERITY = "advisory_severity"
    INFO_SEVERITY = "info_severity"
    DISPUTED_STATE = "disputed_state"
    PENDING_REVIEW_STATE = "pending_review_state"
    MISSING_EVIDENCE = "missing_evidence"
    MISSING_REVIEW = "missing_review"
    MISSING_CLOSURE_METADATA = "missing_closure_metadata"
    MANUAL_REVIEW_REQUIRED = "manual_review_required"


class HumanReviewQueueEntryState(Enum):
    """State of a single human review queue entry."""

    QUEUED = "queued"
    BLOCKED = "blocked"
    PENDING_REVIEW = "pending_review"
    STALE = "stale"
    DISPUTED = "disputed"
    DUPLICATE = "duplicate"
    ORPHANED = "orphaned"
    ACKNOWLEDGED = "acknowledged"
    DEFERRED = "deferred"
    NOT_APPLICABLE = "not_applicable"
    SUPPRESSED = "suppressed"


class HumanReviewQueuePriority(Enum):
    """Priority of a human review queue entry."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class HumanReviewQueueSourceKind(Enum):
    """Source kind for a human review source record."""

    BACKLOG_ITEM = "backlog_item"
    EVIDENCE_RECORD = "evidence_record"
    CLOSURE_RECORD = "closure_record"
    ISSUE = "issue"
    REPORT_SUMMARY = "report_summary"
    MANUAL_NOTE = "manual_note"


class HumanReviewQueueDecisionHint(Enum):
    """Non-executable decision hint for a human review queue entry."""

    REVIEW_REQUIRED = "review_required"
    REVIEW_OPTIONAL = "review_optional"
    ALREADY_ACKNOWLEDGED = "already_acknowledged"
    DEFERRED_FOR_LATER_AUDIT = "deferred_for_later_audit"
    NOT_APPLICABLE_FOR_AUDIT = "not_applicable_for_audit"
    SUPPRESSED_BY_CONFIG = "suppressed_by_config"


class HumanReviewQueueIssueType(Enum):
    """Type of engine-generated issue."""

    UNSAFE_CONTENT = "unsafe_content"
    FORBIDDEN_TERM = "forbidden_term"
    DUPLICATE_SOURCE_ID = "duplicate_source_id"
    DUPLICATE_QUEUE_ENTRY = "duplicate_queue_entry"
    ORPHAN_RELATED_RECORD = "orphan_related_record"
    STALE_SOURCE_RECORD = "stale_source_record"
    BLOCKING_SEVERITY = "blocking_severity"
    ADVISORY_SEVERITY = "advisory_severity"
    INFO_SEVERITY = "info_severity"
    DISPUTED_STATE = "disputed_state"
    PENDING_REVIEW_STATE = "pending_review_state"
    MISSING_EVIDENCE = "missing_evidence"
    MISSING_REVIEW = "missing_review"
    MISSING_CLOSURE_METADATA = "missing_closure_metadata"


# String constants for ergonomic public API use.
OK = HumanReviewQueueReasonCode.OK.value
NOT_APPLICABLE_RC = HumanReviewQueueReasonCode.NOT_APPLICABLE.value
CONSISTENCY_DEGRADED = HumanReviewQueueReasonCode.CONSISTENCY_DEGRADED.value
SAFETY_BLOCKED = HumanReviewQueueReasonCode.SAFETY_BLOCKED.value
UNSAFE_CONTENT = HumanReviewQueueReasonCode.UNSAFE_CONTENT.value
FORBIDDEN_TERM_PRESENT = HumanReviewQueueReasonCode.FORBIDDEN_TERM_PRESENT.value
DUPLICATE_SOURCE_ID = HumanReviewQueueReasonCode.DUPLICATE_SOURCE_ID.value
DUPLICATE_QUEUE_ENTRY = HumanReviewQueueReasonCode.DUPLICATE_QUEUE_ENTRY.value
ORPHAN_RELATED_RECORD = HumanReviewQueueReasonCode.ORPHAN_RELATED_RECORD.value
STALE_SOURCE_RECORD = HumanReviewQueueReasonCode.STALE_SOURCE_RECORD.value
BLOCKING_SEVERITY = HumanReviewQueueReasonCode.BLOCKING_SEVERITY.value
ADVISORY_SEVERITY = HumanReviewQueueReasonCode.ADVISORY_SEVERITY.value
INFO_SEVERITY = HumanReviewQueueReasonCode.INFO_SEVERITY.value
DISPUTED_STATE = HumanReviewQueueReasonCode.DISPUTED_STATE.value
PENDING_REVIEW_STATE = HumanReviewQueueReasonCode.PENDING_REVIEW_STATE.value
MISSING_EVIDENCE = HumanReviewQueueReasonCode.MISSING_EVIDENCE.value
MISSING_REVIEW = HumanReviewQueueReasonCode.MISSING_REVIEW.value
MISSING_CLOSURE_METADATA = HumanReviewQueueReasonCode.MISSING_CLOSURE_METADATA.value
MANUAL_REVIEW_REQUIRED = HumanReviewQueueReasonCode.MANUAL_REVIEW_REQUIRED.value

# Multi-word forbidden phrases only.
#
# Uses case-insensitive substring search against caller-provided metadata and
# all textual fields. All entries MUST be multi-word phrases. Single-word terms
# are intentionally excluded because they produce false positives in benign
# audit text (e.g. "pending approval from security team", "certification body",
# "no recommendation needed", "signal processing", "no signal detected",
# "assign a reviewer", "manual note for audit").
FORBIDDEN_HUMAN_REVIEW_QUEUE_TERMS: frozenset[str] = frozenset({
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
})


# Validation helpers.


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


def has_unsafe_human_review_queue_content(value: Any) -> bool:
    """Return True if value is not a safe string type (bytes, object, int, etc.)."""
    if value is None:
        return False
    if isinstance(value, str):
        return False
    if isinstance(value, (tuple, list)):
        return any(has_unsafe_human_review_queue_content(item) for item in value)
    if isinstance(value, Mapping):
        return any(
            has_unsafe_human_review_queue_content(k)
            or has_unsafe_human_review_queue_content(v)
            for k, v in value.items()
        )
    return True


@dataclass(frozen=True, slots=True)
class HumanReviewQueueSafetyFlags:
    """Safety flags confirming the queue stays within local audit boundaries."""

    no_executable_actions: bool = True
    no_trading_instructions: bool = True
    no_approval_claims: bool = True
    no_automated_remediation: bool = True
    no_automatic_assignment: bool = True
    references_opaque: bool = True
    audit_only: bool = True
    queued_not_approval: bool = True
    has_unsafe_content: bool = False
    has_forbidden_terms: bool = False

    def __post_init__(self) -> None:
        positive_flags = (
            self.no_executable_actions,
            self.no_trading_instructions,
            self.no_approval_claims,
            self.no_automated_remediation,
            self.no_automatic_assignment,
            self.references_opaque,
            self.audit_only,
            self.queued_not_approval,
        )
        if not all(positive_flags):
            raise ValueError("baseline safety invariants must be True")

    @property
    def is_safe(self) -> bool:
        """True when the report passes all safety boundary checks."""
        return not self.has_unsafe_content and not self.has_forbidden_terms


@dataclass(frozen=True, slots=True)
class HumanReviewQueueConfig:
    """Configuration for the human review queue."""

    strict: bool = False
    include_advisory: bool = True
    include_stale: bool = True
    include_manual_notes: bool = True
    suppress_acknowledged: bool = False
    staleness_threshold_seconds: int = 2_592_000  # 30 days
    forbid_action_terms: bool = True

    def __post_init__(self) -> None:
        _ensure_bool(self.strict, "strict")
        _ensure_bool(self.include_advisory, "include_advisory")
        _ensure_bool(self.include_stale, "include_stale")
        _ensure_bool(self.include_manual_notes, "include_manual_notes")
        _ensure_bool(self.suppress_acknowledged, "suppress_acknowledged")
        _ensure_bool(self.forbid_action_terms, "forbid_action_terms")
        _ensure_non_negative_int(self.staleness_threshold_seconds, "staleness_threshold_seconds")


@dataclass(frozen=True, slots=True)
class HumanReviewSourceRecord:
    """Caller-provided source record for human review queue processing."""

    source_id: str = ""
    source_kind: str = ""  # backlog_item, evidence_record, closure_record, issue, report_summary, manual_note
    record_id: str = ""
    related_record_ids: tuple[str, ...] = ()
    title: str = ""
    description: str = ""
    state: str = ""  # open, blocked, acknowledged, deferred, not_applicable, conflicting, pending_review, disputed, etc.
    severity: str = ""  # blocking, advisory, info
    reason_codes: tuple[str, ...] = ()
    owner: str = ""
    reviewer: str = ""
    generated_at: datetime | None = None
    artifact_ref: str = ""  # opaque reference string
    report_ref: str = ""  # opaque reference string
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _ensure_str_with_default(self.source_id, "source_id")
        _ensure_str_with_default(self.source_kind, "source_kind")
        _ensure_str_with_default(self.record_id, "record_id")
        object.__setattr__(self, "related_record_ids", _ensure_tuple_of_str(self.related_record_ids, "related_record_ids"))
        _ensure_str_with_default(self.title, "title")
        _ensure_str_with_default(self.description, "description")
        _ensure_str_with_default(self.state, "state")
        _ensure_str_with_default(self.severity, "severity")
        object.__setattr__(self, "reason_codes", _ensure_tuple_of_str(self.reason_codes, "reason_codes"))
        _ensure_str_with_default(self.owner, "owner")
        _ensure_str_with_default(self.reviewer, "reviewer")
        _ensure_timezone_aware(self.generated_at, "generated_at")
        _ensure_str_with_default(self.artifact_ref, "artifact_ref")
        _ensure_str_with_default(self.report_ref, "report_ref")
        object.__setattr__(self, "metadata", _coerce_str_mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class HumanReviewQueueEntry:
    """A single human review queue entry."""

    queue_entry_id: str = ""
    source_id: str = ""
    source_kind: str = ""
    record_id: str = ""
    entry_state: str = "queued"
    priority: str = "info"
    decision_hint: str = "review_required"
    severity: str = "info"
    reason_codes: tuple[str, ...] = ()
    title: str = ""
    description: str = ""
    generated_at: datetime | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _ensure_str_with_default(self.queue_entry_id, "queue_entry_id")
        _ensure_str_with_default(self.source_id, "source_id")
        _ensure_str_with_default(self.source_kind, "source_kind")
        _ensure_str_with_default(self.record_id, "record_id")
        _ensure_str_with_default(self.entry_state, "entry_state")
        _ensure_str_with_default(self.priority, "priority")
        _ensure_str_with_default(self.decision_hint, "decision_hint")
        _ensure_str_with_default(self.severity, "severity")
        object.__setattr__(self, "reason_codes", _ensure_tuple_of_str(self.reason_codes, "reason_codes"))
        _ensure_str_with_default(self.title, "title")
        _ensure_str_with_default(self.description, "description")
        _ensure_timezone_aware(self.generated_at, "generated_at")
        object.__setattr__(self, "metadata", _coerce_str_mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class HumanReviewQueueIssue:
    """An engine-generated issue detected while building the queue."""

    issue_id: str = ""
    issue_type: str = ""
    severity: str = "info"
    reason_codes: tuple[str, ...] = ()
    title: str = ""
    description: str = ""
    source_id: str = ""
    record_id: str = ""
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
        _ensure_str_with_default(self.record_id, "record_id")
        _ensure_timezone_aware(self.generated_at, "generated_at")
        object.__setattr__(self, "metadata", _coerce_str_mapping(self.metadata))


@dataclass(frozen=True, slots=True)
class HumanReviewQueueDataQuality:
    """Summary counts for the human review queue report."""

    total_source_records: int = 0
    total_queue_entries: int = 0
    total_issues: int = 0
    duplicate_source_id_count: int = 0
    duplicate_queue_entry_count: int = 0
    orphan_related_record_count: int = 0
    stale_source_record_count: int = 0
    unsafe_content_count: int = 0
    forbidden_term_count: int = 0
    blocking_count: int = 0
    advisory_count: int = 0
    info_count: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    info_priority_count: int = 0
    sections_present: int = 0

    def __post_init__(self) -> None:
        _ensure_non_negative_int(self.total_source_records, "total_source_records")
        _ensure_non_negative_int(self.total_queue_entries, "total_queue_entries")
        _ensure_non_negative_int(self.total_issues, "total_issues")
        _ensure_non_negative_int(self.duplicate_source_id_count, "duplicate_source_id_count")
        _ensure_non_negative_int(self.duplicate_queue_entry_count, "duplicate_queue_entry_count")
        _ensure_non_negative_int(self.orphan_related_record_count, "orphan_related_record_count")
        _ensure_non_negative_int(self.stale_source_record_count, "stale_source_record_count")
        _ensure_non_negative_int(self.unsafe_content_count, "unsafe_content_count")
        _ensure_non_negative_int(self.forbidden_term_count, "forbidden_term_count")
        _ensure_non_negative_int(self.blocking_count, "blocking_count")
        _ensure_non_negative_int(self.advisory_count, "advisory_count")
        _ensure_non_negative_int(self.info_count, "info_count")
        _ensure_non_negative_int(self.critical_count, "critical_count")
        _ensure_non_negative_int(self.high_count, "high_count")
        _ensure_non_negative_int(self.medium_count, "medium_count")
        _ensure_non_negative_int(self.low_count, "low_count")
        _ensure_non_negative_int(self.info_priority_count, "info_priority_count")
        _ensure_non_negative_int(self.sections_present, "sections_present")


@dataclass(frozen=True, slots=True)
class HumanReviewQueueInput:
    """Input for the human review queue engine."""

    source_records: tuple[HumanReviewSourceRecord, ...] = ()
    config: HumanReviewQueueConfig = field(default_factory=HumanReviewQueueConfig)
    project_version: str = HUMAN_REVIEW_QUEUE_VERSION
    metadata: Mapping[str, str] = field(default_factory=dict)
    generated_at: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "source_records", _ensure_tuple_of_items(self.source_records, HumanReviewSourceRecord, "source_records")
        )
        _ensure_str_with_default(self.project_version, "project_version")
        object.__setattr__(self, "metadata", _coerce_str_mapping(self.metadata))
        _ensure_timezone_aware(self.generated_at, "generated_at")


@dataclass(frozen=True, slots=True)
class HumanReviewQueueReport:
    """A local, audit-only human review queue report."""

    report_id: str = ""
    generated_at: datetime | None = None
    state: HumanReviewQueueState = HumanReviewQueueState.NOT_APPLICABLE
    project_version: str = HUMAN_REVIEW_QUEUE_VERSION
    source_records: tuple[HumanReviewSourceRecord, ...] = ()
    queue_entries: tuple[HumanReviewQueueEntry, ...] = ()
    issues: tuple[HumanReviewQueueIssue, ...] = ()
    data_quality: HumanReviewQueueDataQuality = field(default_factory=HumanReviewQueueDataQuality)
    safety_flags: HumanReviewQueueSafetyFlags = field(default_factory=HumanReviewQueueSafetyFlags)
    reason_codes: tuple[HumanReviewQueueReasonCode, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)
    safety_notice: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.state, HumanReviewQueueState):
            raise ValueError("state must be a HumanReviewQueueState")
        object.__setattr__(
            self, "source_records", _ensure_tuple_of_items(self.source_records, HumanReviewSourceRecord, "source_records")
        )
        object.__setattr__(
            self, "queue_entries", _ensure_tuple_of_items(self.queue_entries, HumanReviewQueueEntry, "queue_entries")
        )
        object.__setattr__(self, "issues", _ensure_tuple_of_items(self.issues, HumanReviewQueueIssue, "issues"))
        object.__setattr__(self, "reason_codes", _ensure_tuple_of_items(self.reason_codes, HumanReviewQueueReasonCode, "reason_codes"))
        object.__setattr__(self, "metadata", _coerce_str_mapping(self.metadata))

    @classmethod
    def blocked(
        cls,
        *,
        input: "HumanReviewQueueInput",
        reason_code: HumanReviewQueueReasonCode = HumanReviewQueueReasonCode.UNSAFE_CONTENT,
        notes: str = "",
    ) -> "HumanReviewQueueReport":
        """Return a minimal blocked report with safety flags set."""
        generated_at = input.generated_at if input.generated_at is not None else datetime.now(timezone.utc)
        safety_flags = HumanReviewQueueSafetyFlags(
            has_unsafe_content=reason_code == HumanReviewQueueReasonCode.UNSAFE_CONTENT,
            has_forbidden_terms=reason_code == HumanReviewQueueReasonCode.FORBIDDEN_TERM_PRESENT,
        )
        return cls(
            report_id=_build_report_id(input, generated_at),
            generated_at=generated_at,
            state=HumanReviewQueueState.BLOCKED,
            project_version=input.project_version,
            source_records=input.source_records,
            queue_entries=(),
            issues=(),
            data_quality=HumanReviewQueueDataQuality(
                total_source_records=len(input.source_records),
                unsafe_content_count=1 if reason_code == HumanReviewQueueReasonCode.UNSAFE_CONTENT else 0,
                forbidden_term_count=1 if reason_code == HumanReviewQueueReasonCode.FORBIDDEN_TERM_PRESENT else 0,
            ),
            safety_flags=safety_flags,
            reason_codes=(reason_code,),
            metadata=input.metadata,
            safety_notice=SAFETY_NOTICE,
            notes=notes,
        )


SAFETY_NOTICE = (
    "This report is a local, audit-only research artifact. "
    "Queued-for-review is for human-audit tracking only and does not imply "
    "approval, certification, production readiness, trading readiness, "
    "recommendation, suitability, signal validity, task assignment, or "
    "executable remediation plan."
)


def _build_report_id(input: HumanReviewQueueInput, generated_at: datetime) -> str:
    """Build a deterministic report_id from sorted source IDs and metadata."""
    from json import dumps
    from hashlib import sha256

    payload = {
        "source_ids": sorted(set(str(record.source_id) for record in input.source_records)),
        "project_version": input.project_version,
        "generated_at": generated_at.isoformat(),
    }
    canonical = dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return sha256(canonical.encode("utf-8")).hexdigest()
