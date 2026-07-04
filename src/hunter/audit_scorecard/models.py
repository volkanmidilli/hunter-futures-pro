"""Frozen dataclasses for hunter.audit_scorecard package.

MVP-35 — Local Research Audit Readiness Scorecard.

All dataclasses are frozen. Validation runs in __post_init__. The scorecard only
accepts caller-provided in-memory declarations and references. It never opens,
follows, traverses, validates, fetches, or executes file references, report
references, or metadata strings. Actual artifact paths, section references, and
metadata are provided by the caller or a trusted test harness; the engine never
scans the filesystem, imports arbitrary modules, or introspects the repository.

The audit readiness scorecard is a human-audit / research artifact only. It is
not a production certification, not a certification of trading readiness, not a
trading signal, and not a recommendation. "Readiness" means only a human audit
review completeness snapshot for local research artifacts.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any

AUDIT_SCORECARD_VERSION: str = "0.35.0-dev"


class AuditScorecardState(Enum):
    """Normalized state of an audit scorecard report."""

    OK = "ok"
    DEGRADED = "degraded"
    BLOCKED = "blocked"
    NOT_APPLICABLE = "not_applicable"


class AuditScorecardReasonCode(Enum):
    """Reason codes for audit scorecard results and reports."""

    OK = "ok"
    NOT_APPLICABLE = "not_applicable"
    UNSAFE_CONTENT = "unsafe_content"
    FORBIDDEN_TERM_PRESENT = "forbidden_term_present"
    MISSING_REQUIRED_DIMENSION = "missing_required_dimension"
    DUPLICATE_DIMENSION_ID = "duplicate_dimension_id"
    DUPLICATE_EVIDENCE_ID = "duplicate_evidence_id"
    DUPLICATE_FINDING_ID = "duplicate_finding_id"
    DUPLICATE_LINK_ID = "duplicate_link_id"
    MISSING_SUPPORTING_EVIDENCE = "missing_supporting_evidence"
    STALE_EVIDENCE = "stale_evidence"
    MISSING_MANUAL_REVIEW = "missing_manual_review"
    CONFLICTING_FINDING = "conflicting_finding"
    CONFLICTING_LINK = "conflicting_link"
    ORPHAN_EVIDENCE = "orphan_evidence"
    ORPHAN_LINK = "orphan_link"
    UPSTREAM_DEGRADED = "upstream_degraded"
    UPSTREAM_BLOCKED = "upstream_blocked"
    UNKNOWN_UPSTREAM_STATE = "unknown_upstream_state"
    SAFETY_BLOCKED = "safety_blocked"
    CONSISTENCY_DEGRADED = "consistency_degraded"
    HUMAN_RESEARCH_ONLY = "human_research_only"
    NOT_TRADING_ADVICE = "not_trading_advice"
    NO_PRODUCTION_READINESS = "no_production_readiness"
    NO_FILE_INGESTION = "no_file_ingestion"
    NO_NETWORK_CONNECTION = "no_network_connection"
    NO_EXCHANGE_CONNECTION = "no_exchange_connection"
    NO_FREQTRADE_INPUT = "no_freqtrade_input"
    NO_SCHEDULER = "no_scheduler"
    NO_DAEMON = "no_daemon"
    NO_WEB_UI = "no_web_ui"
    NO_DATABASE = "no_database"
    NO_ACTION_COMMANDS_EMITTED = "no_action_commands_emitted"


class AuditScorecardSeverity(Enum):
    """Fail severity of a scorecard dimension or finding."""

    ADVISORY = "advisory"
    BLOCKING = "blocking"


class AuditScorecardDimensionState(Enum):
    """Coverage/completeness classification for a scorecard dimension."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    MISSING = "missing"
    BLOCKED = "blocked"
    DEGRADED = "degraded"
    NOT_APPLICABLE = "not_applicable"


class AuditScorecardLinkType(Enum):
    """Types of directed edges in the scorecard graph."""

    COVERS = "covers"
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    MANUALLY_REVIEWED = "manually_reviewed"
    DERIVED_FROM = "derived_from"


# String constants for convenient use in reason code tuples and frozensets.
OK = AuditScorecardReasonCode.OK.value
NOT_APPLICABLE_RC = AuditScorecardReasonCode.NOT_APPLICABLE.value
UNSAFE_CONTENT = AuditScorecardReasonCode.UNSAFE_CONTENT.value
FORBIDDEN_TERM_PRESENT = AuditScorecardReasonCode.FORBIDDEN_TERM_PRESENT.value
MISSING_REQUIRED_DIMENSION = AuditScorecardReasonCode.MISSING_REQUIRED_DIMENSION.value
DUPLICATE_DIMENSION_ID = AuditScorecardReasonCode.DUPLICATE_DIMENSION_ID.value
DUPLICATE_EVIDENCE_ID = AuditScorecardReasonCode.DUPLICATE_EVIDENCE_ID.value
DUPLICATE_FINDING_ID = AuditScorecardReasonCode.DUPLICATE_FINDING_ID.value
DUPLICATE_LINK_ID = AuditScorecardReasonCode.DUPLICATE_LINK_ID.value
MISSING_SUPPORTING_EVIDENCE = AuditScorecardReasonCode.MISSING_SUPPORTING_EVIDENCE.value
STALE_EVIDENCE = AuditScorecardReasonCode.STALE_EVIDENCE.value
MISSING_MANUAL_REVIEW = AuditScorecardReasonCode.MISSING_MANUAL_REVIEW.value
CONFLICTING_FINDING = AuditScorecardReasonCode.CONFLICTING_FINDING.value
CONFLICTING_LINK = AuditScorecardReasonCode.CONFLICTING_LINK.value
ORPHAN_EVIDENCE = AuditScorecardReasonCode.ORPHAN_EVIDENCE.value
ORPHAN_LINK = AuditScorecardReasonCode.ORPHAN_LINK.value
UPSTREAM_DEGRADED = AuditScorecardReasonCode.UPSTREAM_DEGRADED.value
UPSTREAM_BLOCKED = AuditScorecardReasonCode.UPSTREAM_BLOCKED.value
UNKNOWN_UPSTREAM_STATE = AuditScorecardReasonCode.UNKNOWN_UPSTREAM_STATE.value
SAFETY_BLOCKED = AuditScorecardReasonCode.SAFETY_BLOCKED.value
CONSISTENCY_DEGRADED = AuditScorecardReasonCode.CONSISTENCY_DEGRADED.value
HUMAN_RESEARCH_ONLY = AuditScorecardReasonCode.HUMAN_RESEARCH_ONLY.value
NOT_TRADING_ADVICE = AuditScorecardReasonCode.NOT_TRADING_ADVICE.value
NO_PRODUCTION_READINESS = AuditScorecardReasonCode.NO_PRODUCTION_READINESS.value
NO_FILE_INGESTION = AuditScorecardReasonCode.NO_FILE_INGESTION.value
NO_NETWORK_CONNECTION = AuditScorecardReasonCode.NO_NETWORK_CONNECTION.value
NO_EXCHANGE_CONNECTION = AuditScorecardReasonCode.NO_EXCHANGE_CONNECTION.value
NO_FREQTRADE_INPUT = AuditScorecardReasonCode.NO_FREQTRADE_INPUT.value
NO_SCHEDULER = AuditScorecardReasonCode.NO_SCHEDULER.value
NO_DAEMON = AuditScorecardReasonCode.NO_DAEMON.value
NO_WEB_UI = AuditScorecardReasonCode.NO_WEB_UI.value
NO_DATABASE = AuditScorecardReasonCode.NO_DATABASE.value
NO_ACTION_COMMANDS_EMITTED = AuditScorecardReasonCode.NO_ACTION_COMMANDS_EMITTED.value

AUDIT_SCORECARD_REASON_CODES: tuple[str, ...] = tuple(
    code.value for code in AuditScorecardReasonCode
)

AUDIT_SCORECARD_BLOCKING_REASON_CODES: frozenset[str] = frozenset({
    UNSAFE_CONTENT,
    FORBIDDEN_TERM_PRESENT,
    MISSING_REQUIRED_DIMENSION,
    DUPLICATE_DIMENSION_ID,
    DUPLICATE_EVIDENCE_ID,
    DUPLICATE_FINDING_ID,
    DUPLICATE_LINK_ID,
    CONFLICTING_FINDING,
    CONFLICTING_LINK,
    UPSTREAM_BLOCKED,
    SAFETY_BLOCKED,
})

AUDIT_SCORECARD_ADVISORY_REASON_CODES: frozenset[str] = frozenset(
    AUDIT_SCORECARD_REASON_CODES
) - AUDIT_SCORECARD_BLOCKING_REASON_CODES

FORBIDDEN_AUDIT_SCORECARD_TERMS: frozenset[str] = frozenset({
    "production ready",
    "live trading",
    "trade approval",
    "execute orders",
    "place orders",
    "buy signal",
    "sell signal",
    "go long",
    "go short",
    "certified",
    "production_ready",
    "live_trade",
    "real_order",
    "action_command",
    "go_live",
    "launch_live",
    "release_ready",
    "deployment_ready",
    "execution_ready",
    "strategy_ready",
    "buy",
    "sell",
    "order",
    "orders",
    "position",
    "positions",
    "leverage",
    "shorting",
    "short",
    "margin",
    "liquidation",
    "fill",
    "slippage",
    "fee",
    "market_order",
    "limit_order",
    "stop_loss",
    "take_profit",
    "execute_trade",
    "place_order",
    "live_trade",
    "real_order",
    "position_size",
    "trade_size",
    "freqtrade",
    "binance",
    "exchange",
    "api_key",
    "secret",
    "token",
    "password",
    "private_key",
    "webhook",
    "url",
    "http",
    "https",
    "ws",
    "wss",
    "deploy",
    "execute",
    "start",
    "stop",
    "trigger",
    "approve",
    "approval",
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ensure_timezone_aware(value: datetime | None, field_name: str) -> datetime | None:
    """Raise ValueError if value is a naive datetime."""
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
    """Validate that value is a tuple/list of strings."""
    if value is None:
        return ()
    if isinstance(value, (tuple, list)):
        for item in value:
            if not isinstance(item, str):
                raise ValueError(f"{field_name} must contain strings")
        return tuple(value)
    raise ValueError(f"{field_name} must be a tuple or list of strings")


def _ensure_non_empty_str(value: Any | None, field_name: str) -> str:
    """Validate that value is a non-empty string."""
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")
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


def _coerce_str_mapping(value: Mapping[str, str] | dict[str, str] | None) -> Mapping[str, str]:
    """Coerce a string mapping into an immutable MappingProxyType."""
    if value is None:
        return MappingProxyType({})
    if isinstance(value, Mapping):
        for key, val in value.items():
            if not isinstance(key, str) or not isinstance(val, str):
                raise ValueError("mapping must contain string keys and values")
        return MappingProxyType(dict(value))
    raise ValueError("mapping must be a Mapping[str, str]")


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


def _has_forbidden_terms_in_text_fields(
    *,
    dimensions: tuple[AuditScorecardDimension, ...],
    evidence_refs: tuple[AuditScorecardEvidenceRef, ...],
    findings: tuple[AuditScorecardFinding, ...],
    links: tuple[AuditScorecardLink, ...],
    forbidden_terms: frozenset[str],
) -> tuple[str, ...]:
    """Return offending text-field strings containing forbidden terms."""
    offenders: list[str] = []
    for dim in dimensions:
        for text in (dim.title, dim.description):
            if text and _has_forbidden_term(text, forbidden_terms):
                offenders.append(text)
    for ref in evidence_refs:
        for text in (ref.label, ref.message):
            if text and _has_forbidden_term(text, forbidden_terms):
                offenders.append(text)
    for finding in findings:
        for text in (finding.message,):
            if text and _has_forbidden_term(text, forbidden_terms):
                offenders.append(text)
    for link in links:
        for text in (link.label, link.message):
            if text and _has_forbidden_term(text, forbidden_terms):
                offenders.append(text)
    return tuple(offenders)


# ---------------------------------------------------------------------------
# Safety flags
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AuditScorecardSafetyFlags:
    """Safety invariants for the audit readiness scorecard."""

    research_only: bool = True
    not_trading_advice: bool = True
    no_production_readiness: bool = True
    no_file_ingestion: bool = True
    no_network_connection: bool = True
    no_exchange_connection: bool = True
    no_freqtrade_input: bool = True
    no_scheduler: bool = True
    no_daemon: bool = True
    no_web_ui: bool = True
    no_database: bool = True
    no_action_commands: bool = True
    has_blocked: bool = False
    has_degraded: bool = False
    has_conflicting_findings: bool = False
    has_conflicting_links: bool = False
    has_stale_evidence: bool = False
    has_missing_manual_review: bool = False
    has_orphan_evidence: bool = False
    has_orphan_links: bool = False
    has_forbidden_terms: bool = False

    def __post_init__(self) -> None:
        positive_flags = (
            self.research_only,
            self.not_trading_advice,
            self.no_production_readiness,
            self.no_file_ingestion,
            self.no_network_connection,
            self.no_exchange_connection,
            self.no_freqtrade_input,
            self.no_scheduler,
            self.no_daemon,
            self.no_web_ui,
            self.no_database,
            self.no_action_commands,
        )
        if not all(positive_flags):
            raise ValueError("baseline safety invariants must be True")

    @property
    def is_safe(self) -> bool:
        """Return True when all positive invariants hold and all negative flags are False."""
        return (
            self.research_only
            and self.not_trading_advice
            and self.no_production_readiness
            and self.no_file_ingestion
            and self.no_network_connection
            and self.no_exchange_connection
            and self.no_freqtrade_input
            and self.no_scheduler
            and self.no_daemon
            and self.no_web_ui
            and self.no_database
            and self.no_action_commands
            and not self.has_blocked
            and not self.has_degraded
            and not self.has_conflicting_findings
            and not self.has_conflicting_links
            and not self.has_stale_evidence
            and not self.has_missing_manual_review
            and not self.has_orphan_evidence
            and not self.has_orphan_links
            and not self.has_forbidden_terms
        )


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AuditScorecardConfig:
    """Configuration for the audit readiness scorecard."""

    strict: bool = False
    generated_at: datetime | None = None
    default_json_path: str = "data/audit_scorecard/audit_scorecard.json"
    default_csv_path: str = "data/audit_scorecard/audit_scorecard_dimensions.csv"
    default_markdown_path: str = "reports/audit_scorecard/audit_scorecard.md"
    staleness_threshold_seconds: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.strict, bool):
            raise ValueError("strict must be a bool")
        _ensure_timezone_aware(self.generated_at, "generated_at")
        _ensure_non_empty_str(self.default_json_path, "default_json_path")
        _ensure_non_empty_str(self.default_csv_path, "default_csv_path")
        _ensure_non_empty_str(self.default_markdown_path, "default_markdown_path")
        if self.staleness_threshold_seconds is not None and (
            not isinstance(self.staleness_threshold_seconds, int) or self.staleness_threshold_seconds < 0
        ):
            raise ValueError("staleness_threshold_seconds must be a non-negative integer or None")


@dataclass(frozen=True)
class AuditScorecardEvidenceRef:
    """Caller-provided reference to an already-produced artifact or report.

    `reference` is an opaque local string; the engine never opens or follows it.
    """

    evidence_id: str
    reference: str
    label: str = ""
    message: str = ""
    generated_at: datetime | None = None
    requires_manual_review: bool = False

    def __post_init__(self) -> None:
        _ensure_non_empty_str(self.evidence_id, "evidence_id")
        _ensure_non_empty_str(self.reference, "reference")
        _ensure_str_with_default(self.label, "label")
        _ensure_str_with_default(self.message, "message")
        _ensure_timezone_aware(self.generated_at, "generated_at")
        if not isinstance(self.requires_manual_review, bool):
            raise ValueError("requires_manual_review must be a bool")


@dataclass(frozen=True)
class AuditScorecardFinding:
    """A specific issue found during scorecard evaluation.

    `dimension_id` is the dimension this finding relates to; it may be an empty
    string for global findings such as orphan links or orphan evidence refs.
    """

    finding_id: str
    dimension_id: str
    severity: AuditScorecardSeverity
    reason_code: AuditScorecardReasonCode
    message: str = ""
    evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _ensure_non_empty_str(self.finding_id, "finding_id")
        _ensure_str_with_default(self.dimension_id, "dimension_id")
        if not isinstance(self.severity, AuditScorecardSeverity):
            raise ValueError("severity must be an AuditScorecardSeverity")
        if not isinstance(self.reason_code, AuditScorecardReasonCode):
            raise ValueError("reason_code must be an AuditScorecardReasonCode")
        _ensure_str_with_default(self.message, "message")
        object.__setattr__(self, "evidence", _ensure_tuple_of_str(self.evidence, "evidence"))


@dataclass(frozen=True)
class AuditScorecardLink:
    """Directed edge between two scorecard items."""

    link_id: str
    source_id: str
    target_id: str
    link_type: AuditScorecardLinkType
    label: str = ""
    message: str = ""

    def __post_init__(self) -> None:
        _ensure_non_empty_str(self.link_id, "link_id")
        _ensure_non_empty_str(self.source_id, "source_id")
        _ensure_non_empty_str(self.target_id, "target_id")
        if not isinstance(self.link_type, AuditScorecardLinkType):
            raise ValueError("link_type must be an AuditScorecardLinkType")
        _ensure_str_with_default(self.label, "label")
        _ensure_str_with_default(self.message, "message")


@dataclass(frozen=True)
class AuditScorecardDimension:
    """Caller-provided dimension node in the scorecard."""

    dimension_id: str
    title: str
    description: str
    severity: AuditScorecardSeverity = AuditScorecardSeverity.BLOCKING
    required: bool = True
    not_applicable: bool = False
    requires_manual_review: bool = False
    upstream_package_ids: tuple[str, ...] = ()
    upstream_report_ids: tuple[str, ...] = ()
    expected_evidence_count: int | None = None
    required_link_types: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _ensure_non_empty_str(self.dimension_id, "dimension_id")
        _ensure_str_with_default(self.title, "title")
        _ensure_str_with_default(self.description, "description")
        if not isinstance(self.severity, AuditScorecardSeverity):
            raise ValueError("severity must be an AuditScorecardSeverity")
        if not isinstance(self.required, bool):
            raise ValueError("required must be a bool")
        if not isinstance(self.not_applicable, bool):
            raise ValueError("not_applicable must be a bool")
        if not isinstance(self.requires_manual_review, bool):
            raise ValueError("requires_manual_review must be a bool")
        object.__setattr__(
            self, "upstream_package_ids", _ensure_tuple_of_str(self.upstream_package_ids, "upstream_package_ids")
        )
        object.__setattr__(
            self, "upstream_report_ids", _ensure_tuple_of_str(self.upstream_report_ids, "upstream_report_ids")
        )
        if self.expected_evidence_count is not None and (
            not isinstance(self.expected_evidence_count, int) or self.expected_evidence_count < 0
        ):
            raise ValueError("expected_evidence_count must be a non-negative integer or None")
        object.__setattr__(
            self, "required_link_types", _ensure_tuple_of_str(self.required_link_types, "required_link_types")
        )


@dataclass(frozen=True, slots=True)
class AuditScorecardDimensionResult:
    """Per-dimension classification result produced by the engine.

    The writer reads these directly; it does not recompute classification.
    Dimensions with no findings still receive a COMPLETE, NOT_APPLICABLE, or
    other deterministic state row.
    """

    dimension_id: str
    dimension_state: AuditScorecardDimensionState
    severity: AuditScorecardSeverity
    completeness_percent: int
    evidence_count: int
    finding_count: int
    reason_codes: tuple[str, ...] = ()
    message: str = ""

    def __post_init__(self) -> None:
        _ensure_non_empty_str(self.dimension_id, "dimension_id")
        if not isinstance(self.dimension_state, AuditScorecardDimensionState):
            raise ValueError("dimension_state must be an AuditScorecardDimensionState")
        if not isinstance(self.severity, AuditScorecardSeverity):
            raise ValueError("severity must be an AuditScorecardSeverity")
        if not isinstance(self.completeness_percent, int) or not (0 <= self.completeness_percent <= 100):
            raise ValueError("completeness_percent must be an integer between 0 and 100")
        if not isinstance(self.evidence_count, int) or self.evidence_count < 0:
            raise ValueError("evidence_count must be a non-negative integer")
        if not isinstance(self.finding_count, int) or self.finding_count < 0:
            raise ValueError("finding_count must be a non-negative integer")
        object.__setattr__(self, "reason_codes", _ensure_tuple_of_str(self.reason_codes, "reason_codes"))
        _ensure_str_with_default(self.message, "message")


@dataclass(frozen=True)
class AuditScorecardInput:
    """Caller-provided in-memory inputs for the audit scorecard."""

    dimensions: tuple[AuditScorecardDimension, ...]
    evidence_refs: tuple[AuditScorecardEvidenceRef, ...] = ()
    findings: tuple[AuditScorecardFinding, ...] = ()
    links: tuple[AuditScorecardLink, ...] = ()
    upstream_states: Mapping[str, str] = field(default_factory=dict)
    metadata: Mapping[str, str] = field(default_factory=dict)
    project_version: str = ""
    generated_at: datetime | None = None
    config: AuditScorecardConfig = field(default_factory=AuditScorecardConfig)

    def __post_init__(self) -> None:
        object.__setattr__(self, "dimensions", tuple(self.dimensions))
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))
        object.__setattr__(self, "findings", tuple(self.findings))
        object.__setattr__(self, "links", tuple(self.links))
        object.__setattr__(self, "upstream_states", _coerce_str_mapping(self.upstream_states))
        object.__setattr__(self, "metadata", _coerce_str_mapping(self.metadata))
        object.__setattr__(self, "project_version", _ensure_str_or_none(self.project_version, "project_version"))
        _ensure_timezone_aware(self.generated_at, "generated_at")
        if not isinstance(self.config, AuditScorecardConfig):
            raise ValueError("config must be an AuditScorecardConfig")
        for dim in self.dimensions:
            if not isinstance(dim, AuditScorecardDimension):
                raise ValueError("dimensions must contain AuditScorecardDimension objects")
        for ref in self.evidence_refs:
            if not isinstance(ref, AuditScorecardEvidenceRef):
                raise ValueError("evidence_refs must contain AuditScorecardEvidenceRef objects")
        for finding in self.findings:
            if not isinstance(finding, AuditScorecardFinding):
                raise ValueError("findings must contain AuditScorecardFinding objects")
        for link in self.links:
            if not isinstance(link, AuditScorecardLink):
                raise ValueError("links must contain AuditScorecardLink objects")


@dataclass(frozen=True)
class AuditScorecardDataQuality:
    """Summary data quality for the audit scorecard."""

    dimension_count: int
    evidence_count: int
    finding_count: int
    link_count: int
    sections_present: int
    state_distribution: Mapping[str, int]
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for attr in ("dimension_count", "evidence_count", "finding_count", "link_count", "sections_present"):
            value = getattr(self, attr)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{attr} must be a non-negative integer")
        if not isinstance(self.state_distribution, Mapping):
            raise ValueError("state_distribution must be a mapping")
        for key, val in self.state_distribution.items():
            if not isinstance(key, str) or not isinstance(val, int):
                raise ValueError("state_distribution must contain string keys and integer values")
        object.__setattr__(self, "notes", _ensure_tuple_of_str(self.notes, "notes"))


@dataclass(frozen=True)
class AuditScorecardReport:
    """Top-level audit readiness scorecard report."""

    report_id: str
    state: AuditScorecardState
    reason_codes: tuple[AuditScorecardReasonCode, ...]
    dimensions: tuple[AuditScorecardDimension, ...]
    dimension_results: tuple[AuditScorecardDimensionResult, ...]
    evidence_refs: tuple[AuditScorecardEvidenceRef, ...]
    findings: tuple[AuditScorecardFinding, ...]
    links: tuple[AuditScorecardLink, ...]
    data_quality: AuditScorecardDataQuality
    safety_flags: AuditScorecardSafetyFlags
    generated_at: datetime
    project_version: str | None
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.report_id, str) or not self.report_id:
            raise ValueError("report_id must be a non-empty string")
        if not isinstance(self.state, AuditScorecardState):
            raise ValueError("state must be an AuditScorecardState")
        _ensure_timezone_aware(self.generated_at, "generated_at")
        object.__setattr__(self, "project_version", _ensure_str_or_none(self.project_version, "project_version"))
        if not isinstance(self.dimensions, tuple):
            raise ValueError("dimensions must be a tuple")
        if not isinstance(self.dimension_results, tuple):
            raise ValueError("dimension_results must be a tuple")
        if not isinstance(self.evidence_refs, tuple):
            raise ValueError("evidence_refs must be a tuple")
        if not isinstance(self.findings, tuple):
            raise ValueError("findings must be a tuple")
        if not isinstance(self.links, tuple):
            raise ValueError("links must be a tuple")
        if not isinstance(self.data_quality, AuditScorecardDataQuality):
            raise ValueError("data_quality must be an AuditScorecardDataQuality")
        if not isinstance(self.safety_flags, AuditScorecardSafetyFlags):
            raise ValueError("safety_flags must be an AuditScorecardSafetyFlags")
        object.__setattr__(self, "reason_codes", tuple(self.reason_codes))
        for code in self.reason_codes:
            if not isinstance(code, AuditScorecardReasonCode):
                raise ValueError("reason_codes must contain AuditScorecardReasonCode values")
        object.__setattr__(self, "notes", _ensure_tuple_of_str(self.notes, "notes"))

    @classmethod
    def blocked(
        cls,
        *,
        input: AuditScorecardInput,
        reason_code: AuditScorecardReasonCode = AuditScorecardReasonCode.UNSAFE_CONTENT,
        generated_at: datetime | None = None,
        safety_flags: AuditScorecardSafetyFlags | None = None,
        notes: tuple[str, ...] = (),
    ) -> "AuditScorecardReport":
        """Create a deterministic fail-closed blocked audit scorecard report."""
        if generated_at is None:
            generated_at = input.generated_at if input.generated_at is not None else datetime.now(timezone.utc)
        if safety_flags is None:
            if reason_code in (
                AuditScorecardReasonCode.UNSAFE_CONTENT,
                AuditScorecardReasonCode.FORBIDDEN_TERM_PRESENT,
            ):
                safety_flags = AuditScorecardSafetyFlags(has_forbidden_terms=True)
            else:
                safety_flags = AuditScorecardSafetyFlags()
        data_quality = AuditScorecardDataQuality(
            dimension_count=len(input.dimensions),
            evidence_count=len(input.evidence_refs),
            finding_count=len(input.findings),
            link_count=len(input.links),
            sections_present=0,
            state_distribution={},
            notes=(),
        )
        return cls(
            report_id="audit_scorecard_blocked",
            state=AuditScorecardState.BLOCKED,
            reason_codes=(
                AuditScorecardReasonCode.SAFETY_BLOCKED,
                reason_code,
            ),
            dimensions=tuple(input.dimensions),
            dimension_results=(),
            evidence_refs=tuple(input.evidence_refs),
            findings=tuple(input.findings),
            links=tuple(input.links),
            data_quality=data_quality,
            safety_flags=safety_flags,
            generated_at=generated_at,
            project_version=input.project_version,
            notes=notes,
        )
