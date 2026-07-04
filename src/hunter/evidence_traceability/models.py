"""Frozen dataclasses for hunter.evidence_traceability package.

MVP-34 — Local Research Evidence Traceability Matrix.

All dataclasses are frozen. Validation runs in __post_init__. The traceability
matrix only accepts caller-provided in-memory declarations and references. It
never opens, follows, traverses, validates, fetches, or executes file references
or metadata strings. Actual artifact paths, section references, and metadata are
provided by the caller or a trusted test harness; the engine never scans the
filesystem, imports arbitrary modules, or introspects the repository.

The evidence traceability matrix is a human-audit / research artifact only. It
is not a production certification, not a trading readiness gate, and not a
trading signal or recommendation.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any

EVIDENCE_TRACEABILITY_VERSION: str = "0.34.0-dev"


class EvidenceTraceabilityState(Enum):
    """Normalized state of a traceability result or report."""

    OK = "ok"
    DEGRADED = "degraded"
    BLOCKED = "blocked"
    NOT_APPLICABLE = "not_applicable"


class EvidenceTraceabilityReasonCode(Enum):
    """Reason codes for traceability results and reports."""

    OK = "ok"
    NOT_APPLICABLE = "not_applicable"
    CONSISTENCY_DEGRADED = "consistency_degraded"
    SAFETY_BLOCKED = "safety_blocked"
    MISSING_REQUIRED_DECLARATION = "missing_required_declaration"
    DUPLICATE_REQUIREMENT_ID = "duplicate_requirement_id"
    DUPLICATE_CHECK_ID = "duplicate_check_id"
    DUPLICATE_ARTIFACT_ID = "duplicate_artifact_id"
    DUPLICATE_SECTION_ID = "duplicate_section_id"
    DUPLICATE_LINK_ID = "duplicate_link_id"
    UNSAFE_CONTENT = "unsafe_content"
    MISSING_COVERAGE = "missing_coverage"
    PARTIAL_COVERAGE = "partial_coverage"
    ORPHAN_CHECK = "orphan_check"
    ORPHAN_ARTIFACT = "orphan_artifact"
    ORPHAN_SECTION = "orphan_section"
    CONFLICTING_LINK = "conflicting_link"
    STALE_EVIDENCE = "stale_evidence"
    MISSING_MANUAL_REVIEW = "missing_manual_review"
    FORBIDDEN_TERM_PRESENT = "forbidden_term_present"
    NOT_TRADING_ADVICE = "not_trading_advice"
    HUMAN_RESEARCH_ONLY = "human_research_only"
    RESEARCH_ONLY = "research_only"
    NO_FILE_INGESTION = "no_file_ingestion"
    NO_NETWORK_CONNECTION = "no_network_connection"
    NO_EXCHANGE_CONNECTION = "no_exchange_connection"
    NO_FREQTRADE_INPUT = "no_freqtrade_input"
    NO_SCHEDULER = "no_scheduler"
    NO_DAEMON = "no_daemon"
    NO_WEB_UI = "no_web_ui"
    NO_DATABASE = "no_database"
    NO_ACTION_COMMANDS_EMITTED = "no_action_commands_emitted"


class EvidenceTraceabilitySeverity(Enum):
    """Fail severity of a traceability check or requirement."""

    ADVISORY = "advisory"
    BLOCKING = "blocking"


class EvidenceTraceabilityLinkType(Enum):
    """Types of directed edges in the traceability graph."""

    COVERED_BY = "covered_by"
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    MANUALLY_REVIEWED = "manually_reviewed"
    DERIVED_FROM = "derived_from"


class EvidenceTraceabilityCoverageState(Enum):
    """Coverage classification for a requirement."""

    COVERED = "covered"
    PARTIAL = "partial"
    MISSING = "missing"
    NOT_APPLICABLE = "not_applicable"


# String constants for convenient use in reason code tuples and frozensets.
OK = EvidenceTraceabilityReasonCode.OK.value
NOT_APPLICABLE_RC = EvidenceTraceabilityReasonCode.NOT_APPLICABLE.value
CONSISTENCY_DEGRADED = EvidenceTraceabilityReasonCode.CONSISTENCY_DEGRADED.value
SAFETY_BLOCKED = EvidenceTraceabilityReasonCode.SAFETY_BLOCKED.value
MISSING_REQUIRED_DECLARATION = (
    EvidenceTraceabilityReasonCode.MISSING_REQUIRED_DECLARATION.value
)
DUPLICATE_REQUIREMENT_ID = EvidenceTraceabilityReasonCode.DUPLICATE_REQUIREMENT_ID.value
DUPLICATE_CHECK_ID = EvidenceTraceabilityReasonCode.DUPLICATE_CHECK_ID.value
DUPLICATE_ARTIFACT_ID = EvidenceTraceabilityReasonCode.DUPLICATE_ARTIFACT_ID.value
DUPLICATE_SECTION_ID = EvidenceTraceabilityReasonCode.DUPLICATE_SECTION_ID.value
DUPLICATE_LINK_ID = EvidenceTraceabilityReasonCode.DUPLICATE_LINK_ID.value
UNSAFE_CONTENT = EvidenceTraceabilityReasonCode.UNSAFE_CONTENT.value
MISSING_COVERAGE = EvidenceTraceabilityReasonCode.MISSING_COVERAGE.value
PARTIAL_COVERAGE = EvidenceTraceabilityReasonCode.PARTIAL_COVERAGE.value
ORPHAN_CHECK = EvidenceTraceabilityReasonCode.ORPHAN_CHECK.value
ORPHAN_ARTIFACT = EvidenceTraceabilityReasonCode.ORPHAN_ARTIFACT.value
ORPHAN_SECTION = EvidenceTraceabilityReasonCode.ORPHAN_SECTION.value
CONFLICTING_LINK = EvidenceTraceabilityReasonCode.CONFLICTING_LINK.value
STALE_EVIDENCE = EvidenceTraceabilityReasonCode.STALE_EVIDENCE.value
MISSING_MANUAL_REVIEW = EvidenceTraceabilityReasonCode.MISSING_MANUAL_REVIEW.value
FORBIDDEN_TERM_PRESENT = EvidenceTraceabilityReasonCode.FORBIDDEN_TERM_PRESENT.value
NOT_TRADING_ADVICE = "not_trading_advice"
NO_FILE_INGESTION = "no_file_ingestion"
NO_NETWORK_CONNECTION = "no_network_connection"
NO_EXCHANGE_CONNECTION = "no_exchange_connection"
NO_FREQTRADE_INPUT = "no_freqtrade_input"
NO_SCHEDULER = "no_scheduler"
NO_DAEMON = "no_daemon"
NO_WEB_UI = "no_web_ui"
NO_DATABASE = "no_database"
NO_ACTION_COMMANDS_EMITTED = "no_action_commands_emitted"

EVIDENCE_TRACEABILITY_REASON_CODES: tuple[str, ...] = tuple(
    code.value for code in EvidenceTraceabilityReasonCode
)

EVIDENCE_TRACEABILITY_BLOCKING_REASON_CODES: frozenset[str] = frozenset({
    UNSAFE_CONTENT,
    FORBIDDEN_TERM_PRESENT,
    MISSING_REQUIRED_DECLARATION,
    DUPLICATE_REQUIREMENT_ID,
    DUPLICATE_CHECK_ID,
    DUPLICATE_ARTIFACT_ID,
    DUPLICATE_SECTION_ID,
    DUPLICATE_LINK_ID,
    CONFLICTING_LINK,
    SAFETY_BLOCKED,
})

EVIDENCE_TRACEABILITY_ADVISORY_REASON_CODES: frozenset[str] = frozenset(
    EVIDENCE_TRACEABILITY_REASON_CODES
) - EVIDENCE_TRACEABILITY_BLOCKING_REASON_CODES

FORBIDDEN_EVIDENCE_TRACEABILITY_TERMS: frozenset[str] = frozenset({
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
                raise ValueError("metadata must be a mapping of strings")
        return MappingProxyType(dict(value))
    raise ValueError("metadata must be a mapping")


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
    requirements: tuple[EvidenceRequirement, ...],
    checks: tuple[EvidenceCheck, ...],
    artifacts: tuple[EvidenceArtifactRef, ...],
    sections: tuple[EvidenceSectionRef, ...],
    links: tuple[EvidenceLink, ...],
    forbidden_terms: frozenset[str],
) -> tuple[str, ...]:
    """Return offending text-field strings containing forbidden terms."""
    offenders: list[str] = []
    for req in requirements:
        for text in (req.title, req.description):
            if text and _has_forbidden_term(text, forbidden_terms):
                offenders.append(text)
    for check in checks:
        for text in (check.title, check.description):
            if text and _has_forbidden_term(text, forbidden_terms):
                offenders.append(text)
    for art in artifacts:
        for text in (art.label, art.message):
            if text and _has_forbidden_term(text, forbidden_terms):
                offenders.append(text)
    for sec in sections:
        for text in (sec.label, sec.message):
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
class EvidenceTraceabilitySafetyFlags:
    """Safety invariants for the evidence traceability matrix."""

    has_blocked: bool = False
    has_degraded: bool = False
    has_conflicting_links: bool = False
    has_missing_coverage: bool = False
    has_stale_evidence: bool = False
    has_missing_manual_review: bool = False
    has_orphan_items: bool = False
    has_forbidden_terms: bool = False
    research_only: bool = True
    not_trading_advice: bool = True
    not_production_certification: bool = True
    not_trading_readiness_gate: bool = True
    no_action_commands: bool = True
    no_network_connection: bool = True
    no_file_read_in_engine: bool = True
    no_database: bool = True
    no_exchange_connection: bool = True
    no_freqtrade_input: bool = True
    no_scheduler: bool = True
    no_web_ui: bool = True
    no_daemon: bool = True

    def __post_init__(self) -> None:
        positive_flags = (
            self.research_only,
            self.not_trading_advice,
            self.not_production_certification,
            self.not_trading_readiness_gate,
            self.no_action_commands,
            self.no_network_connection,
            self.no_file_read_in_engine,
            self.no_database,
            self.no_exchange_connection,
            self.no_freqtrade_input,
            self.no_scheduler,
            self.no_web_ui,
            self.no_daemon,
        )
        if not all(positive_flags):
            raise ValueError("baseline safety invariants must be True")

    @property
    def is_safe(self) -> bool:
        """Return True when all positive invariants hold and all negative flags are False."""
        return (
            self.research_only
            and self.not_trading_advice
            and self.not_production_certification
            and self.not_trading_readiness_gate
            and self.no_action_commands
            and self.no_network_connection
            and self.no_file_read_in_engine
            and self.no_database
            and self.no_exchange_connection
            and self.no_freqtrade_input
            and self.no_scheduler
            and self.no_web_ui
            and self.no_daemon
            and not self.has_blocked
            and not self.has_degraded
            and not self.has_conflicting_links
            and not self.has_missing_coverage
            and not self.has_stale_evidence
            and not self.has_missing_manual_review
            and not self.has_orphan_items
            and not self.has_forbidden_terms
        )


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EvidenceRequirement:
    """Caller-provided requirement node in the traceability graph."""

    requirement_id: str
    description: str = ""
    title: str = ""
    required_link_types: tuple[str, ...] = ()
    severity: EvidenceTraceabilitySeverity = EvidenceTraceabilitySeverity.BLOCKING

    def __post_init__(self) -> None:
        _ensure_non_empty_str(self.requirement_id, "requirement_id")
        _ensure_str_with_default(self.description, "description")
        _ensure_str_with_default(self.title, "title")
        object.__setattr__(
            self, "required_link_types", _ensure_tuple_of_str(self.required_link_types, "required_link_types")
        )
        if not isinstance(self.severity, EvidenceTraceabilitySeverity):
            raise ValueError("severity must be an EvidenceTraceabilitySeverity")


@dataclass(frozen=True)
class EvidenceCheck:
    """Caller-provided check node that may cover one or more requirements."""

    check_id: str
    description: str = ""
    title: str = ""
    covers_requirement_ids: tuple[str, ...] = ()
    severity: EvidenceTraceabilitySeverity = EvidenceTraceabilitySeverity.BLOCKING

    def __post_init__(self) -> None:
        _ensure_non_empty_str(self.check_id, "check_id")
        _ensure_str_with_default(self.description, "description")
        _ensure_str_with_default(self.title, "title")
        object.__setattr__(
            self, "covers_requirement_ids", _ensure_tuple_of_str(self.covers_requirement_ids, "covers_requirement_ids")
        )
        if not isinstance(self.severity, EvidenceTraceabilitySeverity):
            raise ValueError("severity must be an EvidenceTraceabilitySeverity")


@dataclass(frozen=True)
class EvidenceArtifactRef:
    """Caller-provided reference to an already-produced artifact.

    `reference` is an opaque local string; the engine never opens or follows it.
    """

    artifact_id: str
    reference: str
    label: str = ""
    message: str = ""
    generated_at: datetime | None = None
    requires_manual_review: bool = False

    def __post_init__(self) -> None:
        _ensure_non_empty_str(self.artifact_id, "artifact_id")
        _ensure_non_empty_str(self.reference, "reference")
        _ensure_str_with_default(self.label, "label")
        _ensure_str_with_default(self.message, "message")
        _ensure_timezone_aware(self.generated_at, "generated_at")
        if not isinstance(self.requires_manual_review, bool):
            raise ValueError("requires_manual_review must be a bool")


@dataclass(frozen=True)
class EvidenceSectionRef:
    """Caller-provided reference to an already-produced report section.

    `reference` is an opaque local string; the engine never opens or follows it.
    """

    section_id: str
    reference: str
    label: str = ""
    message: str = ""
    generated_at: datetime | None = None
    requires_manual_review: bool = False

    def __post_init__(self) -> None:
        _ensure_non_empty_str(self.section_id, "section_id")
        _ensure_non_empty_str(self.reference, "reference")
        _ensure_str_with_default(self.label, "label")
        _ensure_str_with_default(self.message, "message")
        _ensure_timezone_aware(self.generated_at, "generated_at")
        if not isinstance(self.requires_manual_review, bool):
            raise ValueError("requires_manual_review must be a bool")


@dataclass(frozen=True)
class EvidenceLink:
    """Directed edge between two traceability items."""

    link_id: str
    source_id: str
    target_id: str
    link_type: EvidenceTraceabilityLinkType
    label: str = ""
    message: str = ""
    severity: EvidenceTraceabilitySeverity = EvidenceTraceabilitySeverity.BLOCKING

    def __post_init__(self) -> None:
        _ensure_non_empty_str(self.link_id, "link_id")
        _ensure_non_empty_str(self.source_id, "source_id")
        _ensure_non_empty_str(self.target_id, "target_id")
        if not isinstance(self.link_type, EvidenceTraceabilityLinkType):
            raise ValueError("link_type must be an EvidenceTraceabilityLinkType")
        _ensure_str_with_default(self.label, "label")
        _ensure_str_with_default(self.message, "message")
        if not isinstance(self.severity, EvidenceTraceabilitySeverity):
            raise ValueError("severity must be an EvidenceTraceabilitySeverity")


@dataclass(frozen=True)
class EvidenceTraceabilityResult:
    """Result of running one traceability check against one target."""

    item_id: str
    category: str
    state: EvidenceTraceabilityState
    reason_code: EvidenceTraceabilityReasonCode
    coverage_state: EvidenceTraceabilityCoverageState
    message: str
    evidence: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _ensure_non_empty_str(self.item_id, "item_id")
        _ensure_non_empty_str(self.category, "category")
        _ensure_non_empty_str(self.message, "message")
        if not isinstance(self.state, EvidenceTraceabilityState):
            raise ValueError("state must be an EvidenceTraceabilityState")
        if not isinstance(self.reason_code, EvidenceTraceabilityReasonCode):
            raise ValueError("reason_code must be an EvidenceTraceabilityReasonCode")
        if not isinstance(self.coverage_state, EvidenceTraceabilityCoverageState):
            raise ValueError("coverage_state must be an EvidenceTraceabilityCoverageState")
        object.__setattr__(self, "evidence", _ensure_tuple_of_str(self.evidence, "evidence"))


@dataclass(frozen=True)
class EvidenceTraceabilityDataQuality:
    """Summary data quality for the traceability matrix."""

    total_items: int
    ok_count: int
    degraded_count: int
    blocked_count: int
    not_applicable_count: int
    requirement_count: int
    check_count: int
    artifact_count: int
    section_count: int
    link_count: int
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for attr in (
            "total_items",
            "ok_count",
            "degraded_count",
            "blocked_count",
            "not_applicable_count",
            "requirement_count",
            "check_count",
            "artifact_count",
            "section_count",
            "link_count",
        ):
            value = getattr(self, attr)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{attr} must be a non-negative integer")
        if self.total_items != (
            self.ok_count + self.degraded_count + self.blocked_count + self.not_applicable_count
        ):
            raise ValueError("state counts must sum to total_items")
        object.__setattr__(self, "notes", _ensure_tuple_of_str(self.notes, "notes"))


@dataclass(frozen=True)
class EvidenceTraceabilityConfig:
    """Configuration for the evidence traceability matrix."""

    strict: bool = False
    default_json_path: str = "data/evidence_traceability/evidence_traceability.json"
    default_csv_path: str = "data/evidence_traceability/evidence_traceability_edges.csv"
    default_markdown_path: str = "reports/evidence_traceability/evidence_traceability.md"
    staleness_threshold_seconds: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.strict, bool):
            raise ValueError("strict must be a bool")
        _ensure_non_empty_str(self.default_json_path, "default_json_path")
        _ensure_non_empty_str(self.default_csv_path, "default_csv_path")
        _ensure_non_empty_str(self.default_markdown_path, "default_markdown_path")
        if self.staleness_threshold_seconds is not None and (
            not isinstance(self.staleness_threshold_seconds, int) or self.staleness_threshold_seconds < 0
        ):
            raise ValueError("staleness_threshold_seconds must be a non-negative integer or None")


@dataclass(frozen=True)
class EvidenceTraceabilityInput:
    """Caller-provided in-memory inputs for the traceability matrix."""

    requirements: tuple[EvidenceRequirement, ...] = ()
    checks: tuple[EvidenceCheck, ...] = ()
    artifacts: tuple[EvidenceArtifactRef, ...] = ()
    sections: tuple[EvidenceSectionRef, ...] = ()
    links: tuple[EvidenceLink, ...] = ()
    project_version: str | None = None
    generated_at: datetime | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)
    config: EvidenceTraceabilityConfig = field(default_factory=EvidenceTraceabilityConfig)

    def __post_init__(self) -> None:
        object.__setattr__(self, "requirements", tuple(self.requirements))
        object.__setattr__(self, "checks", tuple(self.checks))
        object.__setattr__(self, "artifacts", tuple(self.artifacts))
        object.__setattr__(self, "sections", tuple(self.sections))
        object.__setattr__(self, "links", tuple(self.links))
        object.__setattr__(self, "project_version", _ensure_str_or_none(self.project_version, "project_version"))
        _ensure_timezone_aware(self.generated_at, "generated_at")
        object.__setattr__(self, "metadata", _coerce_str_mapping(self.metadata))
        if not isinstance(self.config, EvidenceTraceabilityConfig):
            raise ValueError("config must be an EvidenceTraceabilityConfig")
        for req in self.requirements:
            if not isinstance(req, EvidenceRequirement):
                raise ValueError("requirements must contain EvidenceRequirement objects")
        for check in self.checks:
            if not isinstance(check, EvidenceCheck):
                raise ValueError("checks must contain EvidenceCheck objects")
        for art in self.artifacts:
            if not isinstance(art, EvidenceArtifactRef):
                raise ValueError("artifacts must contain EvidenceArtifactRef objects")
        for sec in self.sections:
            if not isinstance(sec, EvidenceSectionRef):
                raise ValueError("sections must contain EvidenceSectionRef objects")
        for link in self.links:
            if not isinstance(link, EvidenceLink):
                raise ValueError("links must contain EvidenceLink objects")


@dataclass(frozen=True)
class EvidenceTraceabilityReport:
    """Top-level evidence traceability matrix report."""

    state: EvidenceTraceabilityState
    reason_codes: tuple[EvidenceTraceabilityReasonCode, ...]
    results: tuple[EvidenceTraceabilityResult, ...]
    links: tuple[EvidenceLink, ...]
    data_quality: EvidenceTraceabilityDataQuality
    safety_flags: EvidenceTraceabilitySafetyFlags
    generated_at: datetime
    project_version: str | None
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.state, EvidenceTraceabilityState):
            raise ValueError("state must be an EvidenceTraceabilityState")
        _ensure_timezone_aware(self.generated_at, "generated_at")
        object.__setattr__(self, "project_version", _ensure_str_or_none(self.project_version, "project_version"))
        if not isinstance(self.results, tuple):
            raise ValueError("results must be a tuple")
        if not isinstance(self.links, tuple):
            raise ValueError("links must be a tuple")
        if not isinstance(self.data_quality, EvidenceTraceabilityDataQuality):
            raise ValueError("data_quality must be an EvidenceTraceabilityDataQuality")
        if not isinstance(self.safety_flags, EvidenceTraceabilitySafetyFlags):
            raise ValueError("safety_flags must be an EvidenceTraceabilitySafetyFlags")
        object.__setattr__(self, "reason_codes", tuple(self.reason_codes))
        for code in self.reason_codes:
            if not isinstance(code, EvidenceTraceabilityReasonCode):
                raise ValueError("reason_codes must contain EvidenceTraceabilityReasonCode values")
        object.__setattr__(self, "notes", _ensure_tuple_of_str(self.notes, "notes"))

    @classmethod
    def blocked(
        cls,
        *,
        input: EvidenceTraceabilityInput,
        reason_code: EvidenceTraceabilityReasonCode = EvidenceTraceabilityReasonCode.UNSAFE_CONTENT,
        generated_at: datetime | None = None,
        safety_flags: EvidenceTraceabilitySafetyFlags | None = None,
        notes: tuple[str, ...] = (),
    ) -> "EvidenceTraceabilityReport":
        """Create a deterministic fail-closed blocked traceability report."""
        if generated_at is None:
            generated_at = input.generated_at if input.generated_at is not None else datetime.now(timezone.utc)
        if safety_flags is None:
            if reason_code in (
                EvidenceTraceabilityReasonCode.UNSAFE_CONTENT,
                EvidenceTraceabilityReasonCode.FORBIDDEN_TERM_PRESENT,
            ):
                safety_flags = EvidenceTraceabilitySafetyFlags(has_forbidden_terms=True)
            else:
                safety_flags = EvidenceTraceabilitySafetyFlags()
        data_quality = EvidenceTraceabilityDataQuality(
            total_items=0,
            ok_count=0,
            degraded_count=0,
            blocked_count=0,
            not_applicable_count=0,
            requirement_count=len(input.requirements),
            check_count=len(input.checks),
            artifact_count=len(input.artifacts),
            section_count=len(input.sections),
            link_count=len(input.links),
            notes=(),
        )
        return cls(
            state=EvidenceTraceabilityState.BLOCKED,
            reason_codes=(
                EvidenceTraceabilityReasonCode.SAFETY_BLOCKED,
                reason_code,
            ),
            results=(),
            links=(),
            data_quality=data_quality,
            safety_flags=safety_flags,
            generated_at=generated_at,
            project_version=input.project_version,
            notes=notes,
        )
