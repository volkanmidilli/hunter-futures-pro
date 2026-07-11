"""Frozen dataclasses for hunter.human_review_audit_bundle package.

MVP-43 — Local Research Human Review Audit Bundle Export.

All dataclasses are frozen. Validation runs in __post_init__. The bundle layer
only accepts caller-provided in-memory reports and references. It never opens,
follows, traverses, validates, fetches, or executes file references, report
references, artifact references, or metadata strings. The engine never scans
the filesystem, imports arbitrary modules, or introspects the repository.

Audit bundle reports are human-audit / research artifacts only. They are not
a production certification, not a trading readiness assessment, not a
suitability assessment, and not a trading signal or recommendation.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any

from hunter.human_review_decision_log.models import HumanReviewDecisionLogReport
from hunter.human_review_decision_log_consistency.models import (
    HumanReviewDecisionLogConsistencyReport,
)
from hunter.human_review_queue.models import HumanReviewQueueReport

HUMAN_REVIEW_AUDIT_BUNDLE_VERSION: str = "0.43.0-dev"
BUNDLE_KIND: str = "human_review_audit_bundle"

SAFETY_NOTICE = (
    "This bundle is a local, audit-only, human-audit research artifact. "
    "It packages existing local human-review research reports for review only "
    "and does not imply approval, certification, production readiness, "
    "deployment readiness, trading readiness, recommendation, suitability "
    "assessment, signal validity, task assignment, task completion, or "
    "executable remediation plan."
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class HumanReviewAuditBundleState(Enum):
    """Aggregate state of a human review audit bundle report."""

    OK = "ok"
    DEGRADED = "degraded"
    BLOCKED = "blocked"
    NOT_APPLICABLE = "not_applicable"


class HumanReviewAuditBundleSeverity(Enum):
    """Severity of a bundle-level issue."""

    BLOCKING = "blocking"
    ADVISORY = "advisory"
    INFO = "info"


class HumanReviewAuditBundleReasonCode(Enum):
    """Reason codes for bundle-level reports."""

    OK = "ok"
    NOT_APPLICABLE = "not_applicable"
    UPSTREAM_BLOCKED = "upstream_blocked"
    UPSTREAM_DEGRADED = "upstream_degraded"
    UPSTREAM_NOT_APPLICABLE = "upstream_not_applicable"
    EMPTY_INPUT_NOT_APPLICABLE = "empty_input_not_applicable"
    BUNDLE_DEGRADED = "bundle_degraded"
    UNSAFE_CONTENT = "unsafe_content"
    FORBIDDEN_TERM_PRESENT = "forbidden_term_present"
    RESEARCH_ONLY = "research_only"
    HUMAN_AUDIT_ONLY = "human_audit_only"
    NO_EXECUTABLE_ACTIONS = "no_executable_actions"
    NO_TRADING_INSTRUCTIONS = "no_trading_instructions"
    NO_APPROVAL_CLAIMS = "no_approval_claims"
    REFERENCES_OPAQUE = "references_opaque"
    NO_NETWORK = "no_network"
    NO_SERVER = "no_server"
    NO_DATABASE = "no_database"


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class HumanReviewAuditBundleConfig:
    """Configuration for the human review audit bundle engine."""

    carry_forward_upstream_state: bool = True
    empty_input_is_not_applicable: bool = True
    strict: bool = False
    include_upstream_issues: bool = True
    include_derived_summary: bool = True

    def __post_init__(self) -> None:
        _ensure_bool(self.carry_forward_upstream_state, "carry_forward_upstream_state")
        _ensure_bool(self.empty_input_is_not_applicable, "empty_input_is_not_applicable")
        _ensure_bool(self.strict, "strict")
        _ensure_bool(self.include_upstream_issues, "include_upstream_issues")
        _ensure_bool(self.include_derived_summary, "include_derived_summary")


# ---------------------------------------------------------------------------
# Section / Issue / DataQuality / SafetyFlags
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class HumanReviewAuditBundleSection:
    """A normalized bundle section representing one upstream report."""

    section_id: str
    section_kind: str
    upstream_report_id: str
    upstream_state: str
    upstream_reason_codes: tuple[str, ...]
    generated_at: datetime
    summary: Mapping[str, Any]
    metadata: Mapping[str, str]
    notes: str

    def __post_init__(self) -> None:
        _ensure_str_with_default(self.section_id, "section_id")
        _ensure_str_with_default(self.section_kind, "section_kind")
        _ensure_str_with_default(self.upstream_report_id, "upstream_report_id")
        _ensure_str_with_default(self.upstream_state, "upstream_state")
        object.__setattr__(
            self, "upstream_reason_codes", _ensure_tuple_of_str(self.upstream_reason_codes, "upstream_reason_codes")
        )
        _ensure_timezone_aware(self.generated_at, "generated_at")
        object.__setattr__(self, "summary", _coerce_mapping(self.summary, "summary"))
        object.__setattr__(self, "metadata", _coerce_str_mapping(self.metadata))
        _ensure_str_with_default(self.notes, "notes")


@dataclass(frozen=True, slots=True)
class HumanReviewAuditBundleIssue:
    """A bundle-level issue, either carried-forward or engine-generated."""

    issue_id: str
    issue_type: str
    severity: str
    reason_codes: tuple[str, ...]
    source_section_kind: str
    source_id: str
    title: str
    description: str
    generated_at: datetime

    def __post_init__(self) -> None:
        _ensure_str_with_default(self.issue_id, "issue_id")
        _ensure_str_with_default(self.issue_type, "issue_type")
        _ensure_str_with_default(self.severity, "severity")
        object.__setattr__(self, "reason_codes", _ensure_tuple_of_str(self.reason_codes, "reason_codes"))
        _ensure_str_with_default(self.source_section_kind, "source_section_kind")
        _ensure_str_with_default(self.source_id, "source_id")
        _ensure_str_with_default(self.title, "title")
        _ensure_str_with_default(self.description, "description")
        _ensure_timezone_aware(self.generated_at, "generated_at")


@dataclass(frozen=True, slots=True)
class HumanReviewAuditBundleDataQuality:
    """Bundle-level data quality counters."""

    section_count: int = 0
    upstream_issue_count: int = 0
    blocking_issues: int = 0
    advisory_issues: int = 0
    info_findings: int = 0
    queue_entry_count: int = 0
    decision_result_count: int = 0
    consistency_cross_reference_count: int = 0
    unsafe_content_count: int = 0
    forbidden_term_count: int = 0

    def __post_init__(self) -> None:
        _ensure_non_negative_int(self.section_count, "section_count")
        _ensure_non_negative_int(self.upstream_issue_count, "upstream_issue_count")
        _ensure_non_negative_int(self.blocking_issues, "blocking_issues")
        _ensure_non_negative_int(self.advisory_issues, "advisory_issues")
        _ensure_non_negative_int(self.info_findings, "info_findings")
        _ensure_non_negative_int(self.queue_entry_count, "queue_entry_count")
        _ensure_non_negative_int(self.decision_result_count, "decision_result_count")
        _ensure_non_negative_int(self.consistency_cross_reference_count, "consistency_cross_reference_count")
        _ensure_non_negative_int(self.unsafe_content_count, "unsafe_content_count")
        _ensure_non_negative_int(self.forbidden_term_count, "forbidden_term_count")


@dataclass(frozen=True, slots=True)
class HumanReviewAuditBundleSafetyFlags:
    """Safety flags for the bundle report."""

    is_safe: bool = True
    audit_only: bool = True
    no_executable_actions: bool = True
    no_trading_instructions: bool = True
    no_approval_claims: bool = True
    references_opaque: bool = True
    no_network: bool = True
    no_server: bool = True

    def __post_init__(self) -> None:
        _ensure_bool(self.is_safe, "is_safe")
        _ensure_bool(self.audit_only, "audit_only")
        _ensure_bool(self.no_executable_actions, "no_executable_actions")
        _ensure_bool(self.no_trading_instructions, "no_trading_instructions")
        _ensure_bool(self.no_approval_claims, "no_approval_claims")
        _ensure_bool(self.references_opaque, "references_opaque")
        _ensure_bool(self.no_network, "no_network")
        _ensure_bool(self.no_server, "no_server")


# ---------------------------------------------------------------------------
# Input / Report
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class HumanReviewAuditBundleInput:
    """Input for the human review audit bundle engine."""

    queue_report: HumanReviewQueueReport = field(default_factory=lambda: HumanReviewQueueReport())
    decision_log_report: HumanReviewDecisionLogReport = field(
        default_factory=lambda: HumanReviewDecisionLogReport()
    )
    consistency_report: HumanReviewDecisionLogConsistencyReport = field(
        default_factory=lambda: HumanReviewDecisionLogConsistencyReport()
    )
    config: HumanReviewAuditBundleConfig = field(default_factory=HumanReviewAuditBundleConfig)
    project_version: str = HUMAN_REVIEW_AUDIT_BUNDLE_VERSION
    metadata: Mapping[str, str] = field(default_factory=dict)
    generated_at: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.queue_report, HumanReviewQueueReport):
            raise TypeError("queue_report must be a HumanReviewQueueReport")
        if not isinstance(self.decision_log_report, HumanReviewDecisionLogReport):
            raise TypeError("decision_log_report must be a HumanReviewDecisionLogReport")
        if not isinstance(self.consistency_report, HumanReviewDecisionLogConsistencyReport):
            raise TypeError("consistency_report must be a HumanReviewDecisionLogConsistencyReport")
        if not isinstance(self.config, HumanReviewAuditBundleConfig):
            raise TypeError("config must be a HumanReviewAuditBundleConfig")
        _ensure_str_with_default(self.project_version, "project_version")
        object.__setattr__(self, "metadata", _coerce_str_mapping(self.metadata))
        _ensure_timezone_aware(self.generated_at, "generated_at")


@dataclass(frozen=True, slots=True)
class HumanReviewAuditBundleReport:
    """A local, audit-only human review audit bundle report."""

    bundle_id: str = ""
    report_id: str = ""
    generated_at: datetime | None = None
    state: HumanReviewAuditBundleState = HumanReviewAuditBundleState.NOT_APPLICABLE
    project_version: str = HUMAN_REVIEW_AUDIT_BUNDLE_VERSION
    sections: tuple[HumanReviewAuditBundleSection, ...] = ()
    issues: tuple[HumanReviewAuditBundleIssue, ...] = ()
    data_quality: HumanReviewAuditBundleDataQuality = field(
        default_factory=HumanReviewAuditBundleDataQuality
    )
    safety_flags: HumanReviewAuditBundleSafetyFlags = field(
        default_factory=HumanReviewAuditBundleSafetyFlags
    )
    reason_codes: tuple[HumanReviewAuditBundleReasonCode, ...] = ()
    safety_notice: str = SAFETY_NOTICE
    metadata: Mapping[str, str] = field(default_factory=dict)
    notes: str = ""

    def __post_init__(self) -> None:
        _ensure_str_with_default(self.bundle_id, "bundle_id")
        _ensure_str_with_default(self.report_id, "report_id")
        if not isinstance(self.state, HumanReviewAuditBundleState):
            raise ValueError("state must be a HumanReviewAuditBundleState")
        _ensure_str_with_default(self.project_version, "project_version")
        object.__setattr__(self, "sections", _ensure_tuple_of_items(self.sections, HumanReviewAuditBundleSection, "sections"))
        object.__setattr__(self, "issues", _ensure_tuple_of_items(self.issues, HumanReviewAuditBundleIssue, "issues"))
        if not isinstance(self.data_quality, HumanReviewAuditBundleDataQuality):
            raise TypeError("data_quality must be a HumanReviewAuditBundleDataQuality")
        if not isinstance(self.safety_flags, HumanReviewAuditBundleSafetyFlags):
            raise TypeError("safety_flags must be a HumanReviewAuditBundleSafetyFlags")
        object.__setattr__(
            self, "reason_codes", _ensure_tuple_of_items(self.reason_codes, HumanReviewAuditBundleReasonCode, "reason_codes")
        )
        _ensure_str_with_default(self.safety_notice, "safety_notice")
        object.__setattr__(self, "metadata", _coerce_str_mapping(self.metadata))
        _ensure_str_with_default(self.notes, "notes")


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _ensure_bool(value: Any, name: str) -> None:
    if not isinstance(value, bool):
        raise TypeError(f"{name} must be a bool")


def _ensure_str_with_default(value: Any, name: str) -> None:
    if value is None:
        raise ValueError(f"{name} must be a string")
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")


def _ensure_non_negative_int(value: Any, name: str) -> None:
    if not isinstance(value, int):
        raise TypeError(f"{name} must be an int")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")


def _ensure_tuple_of_items(value: Any, item_type: type, name: str) -> tuple[Any, ...]:
    if value is None:
        return ()
    if isinstance(value, item_type):
        return (value,)
    if isinstance(value, Iterable):
        return tuple(value)
    raise TypeError(f"{name} must be an iterable of {item_type.__name__}")


def _ensure_tuple_of_str(value: Any, name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(x) for x in value)


def _coerce_str_mapping(value: Any) -> Mapping[str, str]:
    if value is None:
        return MappingProxyType({})
    return MappingProxyType({str(k): str(v) for k, v in dict(value).items()})


def _coerce_mapping(value: Any, name: str) -> Mapping[str, Any]:
    if value is None:
        return MappingProxyType({})
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    return MappingProxyType({str(k): v for k, v in dict(value).items()})


def _ensure_timezone_aware(value: datetime | None, name: str) -> None:
    if value is None:
        return
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime")
    if value.tzinfo is None:
        raise ValueError(f"{name} must be timezone-aware")
