"""Frozen dataclasses for hunter.cross_pack_consistency package.

MVP-36 — Local Research Cross-Pack Consistency Validator.

All dataclasses are frozen. Validation runs in __post_init__. The validator only
accepts caller-provided in-memory declarations and references. It never opens,
follows, traverses, validates, fetches, or executes file references, report
references, or metadata strings. Actual artifact paths, section references,
requirement references, and metadata are provided by the caller or a trusted test
harness; the engine never scans the filesystem, imports arbitrary modules, or
introspects the repository.

The cross-pack consistency report is a human-audit / research artifact only. It
is not a production certification, not a trading readiness assessment, not a
suitability assessment, and not a trading signal or recommendation.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any

CROSS_PACK_CONSISTENCY_VERSION: str = "0.36.0-dev"


class CrossPackConsistencyState(Enum):
    """Normalized state of a cross-pack consistency report."""

    OK = "ok"
    DEGRADED = "degraded"
    BLOCKED = "blocked"
    NOT_APPLICABLE = "not_applicable"


class CrossPackConsistencySeverity(Enum):
    """Severity of a consistency issue."""

    BLOCKING = "blocking"
    ADVISORY = "advisory"
    INFO = "info"


class CrossPackConsistencyIssueType(Enum):
    """Type of consistency issue detected."""

    MISSING_REQUIRED_PACK = "missing_required_pack"
    INCOMPATIBLE_VERSION = "incompatible_version"
    STALE_DECLARATION = "stale_declaration"
    INCOMPATIBLE_STATE_COMBINATION = "incompatible_state_combination"
    CONFLICTING_STATE = "conflicting_state"
    MISSING_EXPECTED_REF = "missing_expected_ref"
    ORPHAN_REF = "orphan_ref"
    MISSING_MANUAL_REVIEW = "missing_manual_review"
    UNKNOWN_UPSTREAM_STATE = "unknown_upstream_state"
    UNSAFE_CONTENT = "unsafe_content"
    DUPLICATE_ID = "duplicate_id"


class CrossPackConsistencyRuleType(Enum):
    """Type of consistency rule to evaluate."""

    REQUIRED_PACK = "required_pack"
    EXPECTED_REF = "expected_ref"
    COMPATIBLE_VERSION = "compatible_version"
    STALE_DECLARATION = "stale_declaration"
    COMPATIBLE_STATE = "compatible_state"
    CONFLICTING_STATE = "conflicting_state"
    MANUAL_REVIEW = "manual_review"
    UNKNOWN_STATE = "unknown_state"


class CrossPackConsistencyReasonCode(Enum):
    """Reason codes for cross-pack consistency results and reports."""

    OK = "ok"
    NOT_APPLICABLE = "not_applicable"
    CONSISTENCY_DEGRADED = "consistency_degraded"
    SAFETY_BLOCKED = "safety_blocked"
    UNSAFE_CONTENT = "unsafe_content"
    FORBIDDEN_TERM_PRESENT = "forbidden_term_present"
    MISSING_REQUIRED_PACK = "missing_required_pack"
    DUPLICATE_PACK_ID = "duplicate_pack_id"
    DUPLICATE_ARTIFACT_ID = "duplicate_artifact_id"
    DUPLICATE_SECTION_ID = "duplicate_section_id"
    DUPLICATE_REQUIREMENT_ID = "duplicate_requirement_id"
    DUPLICATE_STATE_SUBJECT_ID = "duplicate_state_subject_id"
    MISSING_EXPECTED_ARTIFACT_REF = "missing_expected_artifact_ref"
    MISSING_EXPECTED_SECTION_REF = "missing_expected_section_ref"
    MISSING_EXPECTED_REQUIREMENT_REF = "missing_expected_requirement_ref"
    ORPHAN_ARTIFACT_REF = "orphan_artifact_ref"
    ORPHAN_SECTION_REF = "orphan_section_ref"
    ORPHAN_REQUIREMENT_REF = "orphan_requirement_ref"
    INCOMPATIBLE_VERSION = "incompatible_version"
    STALE_PACK_DECLARATION = "stale_pack_declaration"
    INCOMPATIBLE_STATE_COMBINATION = "incompatible_state_combination"
    CONFLICTING_STATE_CLAIM = "conflicting_state_claim"
    MISSING_MANUAL_REVIEW = "missing_manual_review"
    UNKNOWN_UPSTREAM_STATE = "unknown_upstream_state"
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


# String constants for convenient use in reason code tuples and frozensets.
OK = CrossPackConsistencyReasonCode.OK.value
NOT_APPLICABLE_RC = CrossPackConsistencyReasonCode.NOT_APPLICABLE.value
CONSISTENCY_DEGRADED = CrossPackConsistencyReasonCode.CONSISTENCY_DEGRADED.value
SAFETY_BLOCKED = CrossPackConsistencyReasonCode.SAFETY_BLOCKED.value
UNSAFE_CONTENT = CrossPackConsistencyReasonCode.UNSAFE_CONTENT.value
FORBIDDEN_TERM_PRESENT = CrossPackConsistencyReasonCode.FORBIDDEN_TERM_PRESENT.value
MISSING_REQUIRED_PACK = CrossPackConsistencyReasonCode.MISSING_REQUIRED_PACK.value
DUPLICATE_PACK_ID = CrossPackConsistencyReasonCode.DUPLICATE_PACK_ID.value
DUPLICATE_ARTIFACT_ID = CrossPackConsistencyReasonCode.DUPLICATE_ARTIFACT_ID.value
DUPLICATE_SECTION_ID = CrossPackConsistencyReasonCode.DUPLICATE_SECTION_ID.value
DUPLICATE_REQUIREMENT_ID = CrossPackConsistencyReasonCode.DUPLICATE_REQUIREMENT_ID.value
DUPLICATE_STATE_SUBJECT_ID = CrossPackConsistencyReasonCode.DUPLICATE_STATE_SUBJECT_ID.value
MISSING_EXPECTED_ARTIFACT_REF = CrossPackConsistencyReasonCode.MISSING_EXPECTED_ARTIFACT_REF.value
MISSING_EXPECTED_SECTION_REF = CrossPackConsistencyReasonCode.MISSING_EXPECTED_SECTION_REF.value
MISSING_EXPECTED_REQUIREMENT_REF = CrossPackConsistencyReasonCode.MISSING_EXPECTED_REQUIREMENT_REF.value
ORPHAN_ARTIFACT_REF = CrossPackConsistencyReasonCode.ORPHAN_ARTIFACT_REF.value
ORPHAN_SECTION_REF = CrossPackConsistencyReasonCode.ORPHAN_SECTION_REF.value
ORPHAN_REQUIREMENT_REF = CrossPackConsistencyReasonCode.ORPHAN_REQUIREMENT_REF.value
INCOMPATIBLE_VERSION = CrossPackConsistencyReasonCode.INCOMPATIBLE_VERSION.value
STALE_PACK_DECLARATION = CrossPackConsistencyReasonCode.STALE_PACK_DECLARATION.value
INCOMPATIBLE_STATE_COMBINATION = CrossPackConsistencyReasonCode.INCOMPATIBLE_STATE_COMBINATION.value
CONFLICTING_STATE_CLAIM = CrossPackConsistencyReasonCode.CONFLICTING_STATE_CLAIM.value
MISSING_MANUAL_REVIEW = CrossPackConsistencyReasonCode.MISSING_MANUAL_REVIEW.value
UNKNOWN_UPSTREAM_STATE = CrossPackConsistencyReasonCode.UNKNOWN_UPSTREAM_STATE.value
HUMAN_RESEARCH_ONLY = CrossPackConsistencyReasonCode.HUMAN_RESEARCH_ONLY.value
NOT_TRADING_ADVICE = CrossPackConsistencyReasonCode.NOT_TRADING_ADVICE.value
NO_PRODUCTION_READINESS = CrossPackConsistencyReasonCode.NO_PRODUCTION_READINESS.value
NO_FILE_INGESTION = CrossPackConsistencyReasonCode.NO_FILE_INGESTION.value
NO_NETWORK_CONNECTION = CrossPackConsistencyReasonCode.NO_NETWORK_CONNECTION.value
NO_EXCHANGE_CONNECTION = CrossPackConsistencyReasonCode.NO_EXCHANGE_CONNECTION.value
NO_FREQTRADE_INPUT = CrossPackConsistencyReasonCode.NO_FREQTRADE_INPUT.value
NO_SCHEDULER = CrossPackConsistencyReasonCode.NO_SCHEDULER.value
NO_DAEMON = CrossPackConsistencyReasonCode.NO_DAEMON.value
NO_WEB_UI = CrossPackConsistencyReasonCode.NO_WEB_UI.value
NO_DATABASE = CrossPackConsistencyReasonCode.NO_DATABASE.value
NO_ACTION_COMMANDS_EMITTED = CrossPackConsistencyReasonCode.NO_ACTION_COMMANDS_EMITTED.value


FORBIDDEN_CROSS_PACK_CONSISTENCY_TERMS: frozenset[str] = frozenset({
    "production ready",
    "trading ready",
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
    "api key",
    "binance",
    "freqtrade",
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


def _ensure_tuple_of_rules(
    value: Any,
    field_name: str,
) -> tuple[CrossPackConsistencyRule, ...]:
    """Validate and return a tuple of CrossPackConsistencyRule objects."""
    if value is None:
        return ()
    if not isinstance(value, Iterable) or isinstance(value, (str, bytes)):
        raise ValueError(f"{field_name} must be iterable of rules")
    result = tuple(value)
    for item in result:
        if not isinstance(item, CrossPackConsistencyRule):
            raise ValueError(f"{field_name} must contain CrossPackConsistencyRule objects")
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
    declarations: tuple[CrossPackDeclaration, ...],
    artifact_refs: tuple[CrossPackArtifactRef, ...],
    section_refs: tuple[CrossPackSectionRef, ...],
    requirement_refs: tuple[CrossPackRequirementRef, ...],
    state_claims: tuple[CrossPackStateClaim, ...],
    rules: tuple[CrossPackConsistencyRule, ...],
    forbidden_terms: frozenset[str],
) -> tuple[str, ...]:
    """Return offending text-field strings containing forbidden terms."""
    offenders: list[str] = []
    for declaration in declarations:
        for text in (declaration.title, declaration.description):
            if text and _has_forbidden_term(text, forbidden_terms):
                offenders.append(text)
    for ref in artifact_refs:
        for text in (ref.label, ref.message):
            if text and _has_forbidden_term(text, forbidden_terms):
                offenders.append(text)
    for ref in section_refs:
        for text in (ref.label, ref.message):
            if text and _has_forbidden_term(text, forbidden_terms):
                offenders.append(text)
    for ref in requirement_refs:
        for text in (ref.label, ref.message):
            if text and _has_forbidden_term(text, forbidden_terms):
                offenders.append(text)
    for claim in state_claims:
        for text in (claim.message,):
            if text and _has_forbidden_term(text, forbidden_terms):
                offenders.append(text)
    for rule in rules:
        for text in (rule.message,):
            if text and _has_forbidden_term(text, forbidden_terms):
                offenders.append(text)
    return tuple(offenders)


def has_unsafe_cross_pack_consistency_content(
    value: Any,
) -> bool:
    """Return True if value is not a safe string type (bytes, object, etc.)."""
    if value is None:
        return False
    if isinstance(value, str):
        return False
    if isinstance(value, (bool, int, float)):
        return False
    if isinstance(value, (tuple, list)):
        return any(has_unsafe_cross_pack_consistency_content(item) for item in value)
    if isinstance(value, Mapping):
        return any(
            has_unsafe_cross_pack_consistency_content(k)
            or has_unsafe_cross_pack_consistency_content(v)
            for k, v in value.items()
        )
    return True


# ---------------------------------------------------------------------------
# Safety flags
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CrossPackConsistencySafetyFlags:
    """Safety flags confirming the validator stays within local audit boundaries."""

    has_unsafe_content: bool = False
    has_forbidden_terms: bool = False
    no_file_ingestion: bool = True
    no_network_connection: bool = True
    no_exchange_connection: bool = True
    no_freqtrade_input: bool = True
    no_scheduler: bool = True
    no_daemon: bool = True
    no_web_ui: bool = True
    no_database: bool = True
    no_action_commands_emitted: bool = True

    def __post_init__(self) -> None:
        positive_flags = (
            self.no_file_ingestion,
            self.no_network_connection,
            self.no_exchange_connection,
            self.no_freqtrade_input,
            self.no_scheduler,
            self.no_daemon,
            self.no_web_ui,
            self.no_database,
            self.no_action_commands_emitted,
        )
        if not all(positive_flags):
            raise ValueError("baseline safety invariants must be True")

    @property
    def is_safe(self) -> bool:
        """True when the report passes all safety boundary checks."""
        return (
            not self.has_unsafe_content
            and not self.has_forbidden_terms
            and self.no_file_ingestion
            and self.no_network_connection
            and self.no_exchange_connection
            and self.no_freqtrade_input
            and self.no_scheduler
            and self.no_daemon
            and self.no_web_ui
            and self.no_database
            and self.no_action_commands_emitted
        )


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CrossPackDeclaration:
    """A caller-provided declaration of a local audit/research pack."""

    pack_id: str
    version: str
    title: str = ""
    description: str = ""
    declared_state: str = ""
    artifact_ref_ids: tuple[str, ...] = ()
    section_ref_ids: tuple[str, ...] = ()
    requirement_ref_ids: tuple[str, ...] = ()
    upstream_pack_ids: tuple[str, ...] = ()
    generated_at: datetime | None = None
    requires_manual_review: bool = False

    def __post_init__(self) -> None:
        _ensure_non_empty_str(self.pack_id, "pack_id")
        _ensure_str(self.version, "version")
        _ensure_str_with_default(self.title, "title")
        _ensure_str_with_default(self.description, "description")
        _ensure_str_with_default(self.declared_state, "declared_state")
        object.__setattr__(self, "artifact_ref_ids", _ensure_tuple_of_str(self.artifact_ref_ids, "artifact_ref_ids"))
        object.__setattr__(self, "section_ref_ids", _ensure_tuple_of_str(self.section_ref_ids, "section_ref_ids"))
        object.__setattr__(self, "requirement_ref_ids", _ensure_tuple_of_str(self.requirement_ref_ids, "requirement_ref_ids"))
        object.__setattr__(self, "upstream_pack_ids", _ensure_tuple_of_str(self.upstream_pack_ids, "upstream_pack_ids"))
        _ensure_timezone_aware(self.generated_at, "generated_at")
        if not isinstance(self.requires_manual_review, bool):
            raise ValueError("requires_manual_review must be a bool")


@dataclass(frozen=True, slots=True)
class CrossPackArtifactRef:
    """Opaque reference to an artifact produced by a prior pack."""

    ref_id: str
    pack_id: str
    reference: str
    label: str = ""
    message: str = ""
    generated_at: datetime | None = None
    requires_manual_review: bool = False

    def __post_init__(self) -> None:
        _ensure_non_empty_str(self.ref_id, "ref_id")
        _ensure_non_empty_str(self.pack_id, "pack_id")
        _ensure_non_empty_str(self.reference, "reference")
        _ensure_str_with_default(self.label, "label")
        _ensure_str_with_default(self.message, "message")
        _ensure_timezone_aware(self.generated_at, "generated_at")
        if not isinstance(self.requires_manual_review, bool):
            raise ValueError("requires_manual_review must be a bool")


@dataclass(frozen=True, slots=True)
class CrossPackSectionRef:
    """Opaque reference to a section within a prior pack."""

    ref_id: str
    pack_id: str
    reference: str
    label: str = ""
    message: str = ""
    generated_at: datetime | None = None
    requires_manual_review: bool = False

    def __post_init__(self) -> None:
        _ensure_non_empty_str(self.ref_id, "ref_id")
        _ensure_non_empty_str(self.pack_id, "pack_id")
        _ensure_non_empty_str(self.reference, "reference")
        _ensure_str_with_default(self.label, "label")
        _ensure_str_with_default(self.message, "message")
        _ensure_timezone_aware(self.generated_at, "generated_at")
        if not isinstance(self.requires_manual_review, bool):
            raise ValueError("requires_manual_review must be a bool")


@dataclass(frozen=True, slots=True)
class CrossPackRequirementRef:
    """Opaque reference to a requirement declared by a prior pack."""

    ref_id: str
    pack_id: str
    reference: str
    label: str = ""
    message: str = ""
    generated_at: datetime | None = None
    requires_manual_review: bool = False

    def __post_init__(self) -> None:
        _ensure_non_empty_str(self.ref_id, "ref_id")
        _ensure_non_empty_str(self.pack_id, "pack_id")
        _ensure_non_empty_str(self.reference, "reference")
        _ensure_str_with_default(self.label, "label")
        _ensure_str_with_default(self.message, "message")
        _ensure_timezone_aware(self.generated_at, "generated_at")
        if not isinstance(self.requires_manual_review, bool):
            raise ValueError("requires_manual_review must be a bool")


@dataclass(frozen=True, slots=True)
class CrossPackStateClaim:
    """A state claim about a subject from a specific pack."""

    subject_id: str
    state_label: str
    pack_id: str
    message: str = ""

    def __post_init__(self) -> None:
        _ensure_non_empty_str(self.subject_id, "subject_id")
        _ensure_str(self.state_label, "state_label")
        _ensure_non_empty_str(self.pack_id, "pack_id")
        _ensure_str_with_default(self.message, "message")


@dataclass(frozen=True, slots=True)
class CrossPackConsistencyRule:
    """A rule that declares a cross-pack consistency expectation."""

    rule_type: CrossPackConsistencyRuleType
    source_pack_id: str
    target_pack_id: str | None = None
    subject_id: str | None = None
    ref_kind: str | None = None
    ref_id: str | None = None
    expected_version: str | None = None
    expected_state: str | None = None
    forbidden_states: tuple[str, ...] = ()
    severity: CrossPackConsistencySeverity = CrossPackConsistencySeverity.ADVISORY
    message: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.rule_type, CrossPackConsistencyRuleType):
            raise ValueError("rule_type must be a CrossPackConsistencyRuleType")
        _ensure_non_empty_str(self.source_pack_id, "source_pack_id")
        object.__setattr__(self, "target_pack_id", _ensure_str_or_none(self.target_pack_id, "target_pack_id"))
        object.__setattr__(self, "subject_id", _ensure_str_or_none(self.subject_id, "subject_id"))
        object.__setattr__(self, "ref_kind", _ensure_str_or_none(self.ref_kind, "ref_kind"))
        object.__setattr__(self, "ref_id", _ensure_str_or_none(self.ref_id, "ref_id"))
        object.__setattr__(self, "expected_version", _ensure_str_or_none(self.expected_version, "expected_version"))
        object.__setattr__(self, "expected_state", _ensure_str_or_none(self.expected_state, "expected_state"))
        object.__setattr__(self, "forbidden_states", _ensure_tuple_of_str(self.forbidden_states, "forbidden_states"))
        if not isinstance(self.severity, CrossPackConsistencySeverity):
            raise ValueError("severity must be a CrossPackConsistencySeverity")
        _ensure_str_with_default(self.message, "message")


@dataclass(frozen=True, slots=True)
class CrossPackConsistencyIssue:
    """A single cross-pack consistency issue."""

    issue_id: str
    issue_type: CrossPackConsistencyIssueType
    severity: CrossPackConsistencySeverity
    subject_id: str
    source_pack_id: str
    target_pack_id: str = ""
    reason_codes: tuple[CrossPackConsistencyReasonCode, ...] = ()
    message: str = ""

    def __post_init__(self) -> None:
        _ensure_non_empty_str(self.issue_id, "issue_id")
        if not isinstance(self.issue_type, CrossPackConsistencyIssueType):
            raise ValueError("issue_type must be a CrossPackConsistencyIssueType")
        if not isinstance(self.severity, CrossPackConsistencySeverity):
            raise ValueError("severity must be a CrossPackConsistencySeverity")
        _ensure_non_empty_str(self.subject_id, "subject_id")
        _ensure_str_with_default(self.source_pack_id, "source_pack_id")
        _ensure_str_with_default(self.target_pack_id, "target_pack_id")
        object.__setattr__(self, "reason_codes", tuple(self.reason_codes))
        for code in self.reason_codes:
            if not isinstance(code, CrossPackConsistencyReasonCode):
                raise ValueError("reason_codes must contain CrossPackConsistencyReasonCode values")
        _ensure_str_with_default(self.message, "message")


@dataclass(frozen=True, slots=True)
class CrossPackConsistencyConfig:
    """Configuration for the cross-pack consistency validator."""

    project_version: str = ""
    staleness_threshold_seconds: int = 86400
    strict: bool = False
    forbidden_terms: tuple[str, ...] = (
        "production ready",
        "trading ready",
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
        "api key",
        "binance",
        "freqtrade",
    )
    default_json_path: str = "data/cross_pack_consistency/cross_pack_consistency.json"
    default_csv_path: str = "data/cross_pack_consistency/cross_pack_consistency_issues.csv"
    default_markdown_path: str = "reports/cross_pack_consistency/cross_pack_consistency.md"
    required_pack_ids: tuple[str, ...] = ()
    allowed_state_labels: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _ensure_str_with_default(self.project_version, "project_version")
        if not isinstance(self.staleness_threshold_seconds, int) or self.staleness_threshold_seconds < 0:
            raise ValueError("staleness_threshold_seconds must be a non-negative integer")
        if not isinstance(self.strict, bool):
            raise ValueError("strict must be a bool")
        object.__setattr__(self, "forbidden_terms", _ensure_tuple_of_str(self.forbidden_terms, "forbidden_terms"))
        _ensure_non_empty_str(self.default_json_path, "default_json_path")
        _ensure_non_empty_str(self.default_csv_path, "default_csv_path")
        _ensure_non_empty_str(self.default_markdown_path, "default_markdown_path")
        object.__setattr__(self, "required_pack_ids", _ensure_tuple_of_str(self.required_pack_ids, "required_pack_ids"))
        object.__setattr__(self, "allowed_state_labels", _ensure_tuple_of_str(self.allowed_state_labels, "allowed_state_labels"))


@dataclass(frozen=True, slots=True)
class CrossPackConsistencyDataQuality:
    """Data quality summary for the cross-pack consistency report."""

    total_packs: int = 0
    total_artifact_refs: int = 0
    total_section_refs: int = 0
    total_requirement_refs: int = 0
    total_state_claims: int = 0
    total_rules: int = 0
    total_issues: int = 0
    blocking_issue_count: int = 0
    advisory_issue_count: int = 0
    info_issue_count: int = 0
    duplicate_id_count: int = 0
    orphan_ref_count: int = 0
    stale_declaration_count: int = 0
    sections_present: int = 0

    def __post_init__(self) -> None:
        for attr in (
            "total_packs",
            "total_artifact_refs",
            "total_section_refs",
            "total_requirement_refs",
            "total_state_claims",
            "total_rules",
            "total_issues",
            "blocking_issue_count",
            "advisory_issue_count",
            "info_issue_count",
            "duplicate_id_count",
            "orphan_ref_count",
            "stale_declaration_count",
            "sections_present",
        ):
            value = getattr(self, attr)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{attr} must be a non-negative integer")


@dataclass(frozen=True, slots=True)
class CrossPackConsistencyInput:
    """Top-level input for the cross-pack consistency validator."""

    declarations: tuple[CrossPackDeclaration, ...] = ()
    artifact_refs: tuple[CrossPackArtifactRef, ...] = ()
    section_refs: tuple[CrossPackSectionRef, ...] = ()
    requirement_refs: tuple[CrossPackRequirementRef, ...] = ()
    state_claims: tuple[CrossPackStateClaim, ...] = ()
    rules: tuple[CrossPackConsistencyRule, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)
    generated_at: datetime | None = None
    config: CrossPackConsistencyConfig = field(default_factory=CrossPackConsistencyConfig)
    project_version: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "declarations", tuple(self.declarations))
        for declaration in self.declarations:
            if not isinstance(declaration, CrossPackDeclaration):
                raise ValueError("declarations must contain CrossPackDeclaration objects")
        object.__setattr__(self, "artifact_refs", tuple(self.artifact_refs))
        for ref in self.artifact_refs:
            if not isinstance(ref, CrossPackArtifactRef):
                raise ValueError("artifact_refs must contain CrossPackArtifactRef objects")
        object.__setattr__(self, "section_refs", tuple(self.section_refs))
        for ref in self.section_refs:
            if not isinstance(ref, CrossPackSectionRef):
                raise ValueError("section_refs must contain CrossPackSectionRef objects")
        object.__setattr__(self, "requirement_refs", tuple(self.requirement_refs))
        for ref in self.requirement_refs:
            if not isinstance(ref, CrossPackRequirementRef):
                raise ValueError("requirement_refs must contain CrossPackRequirementRef objects")
        object.__setattr__(self, "state_claims", tuple(self.state_claims))
        for claim in self.state_claims:
            if not isinstance(claim, CrossPackStateClaim):
                raise ValueError("state_claims must contain CrossPackStateClaim objects")
        object.__setattr__(self, "rules", _ensure_tuple_of_rules(self.rules, "rules"))
        object.__setattr__(self, "metadata", _coerce_str_mapping(self.metadata))
        _ensure_timezone_aware(self.generated_at, "generated_at")
        if not isinstance(self.config, CrossPackConsistencyConfig):
            raise ValueError("config must be a CrossPackConsistencyConfig")
        _ensure_str_with_default(self.project_version, "project_version")


@dataclass(frozen=True, slots=True)
class CrossPackConsistencyReport:
    """Deterministic cross-pack consistency report."""

    report_id: str
    generated_at: datetime
    state: CrossPackConsistencyState
    project_version: str
    declarations: tuple[CrossPackDeclaration, ...]
    artifact_refs: tuple[CrossPackArtifactRef, ...]
    section_refs: tuple[CrossPackSectionRef, ...]
    requirement_refs: tuple[CrossPackRequirementRef, ...]
    state_claims: tuple[CrossPackStateClaim, ...]
    rules: tuple[CrossPackConsistencyRule, ...]
    issues: tuple[CrossPackConsistencyIssue, ...]
    data_quality: CrossPackConsistencyDataQuality
    safety_flags: CrossPackConsistencySafetyFlags
    reason_codes: tuple[CrossPackConsistencyReasonCode, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)
    notes: str = ""

    def __post_init__(self) -> None:
        _ensure_non_empty_str(self.report_id, "report_id")
        _ensure_timezone_aware(self.generated_at, "generated_at")
        if not isinstance(self.state, CrossPackConsistencyState):
            raise ValueError("state must be a CrossPackConsistencyState")
        _ensure_str_with_default(self.project_version, "project_version")
        for attr in (
            "declarations",
            "artifact_refs",
            "section_refs",
            "requirement_refs",
            "state_claims",
            "rules",
            "issues",
            "reason_codes",
        ):
            value = getattr(self, attr)
            if not isinstance(value, tuple):
                raise ValueError(f"{attr} must be a tuple")
        for code in self.reason_codes:
            if not isinstance(code, CrossPackConsistencyReasonCode):
                raise ValueError("reason_codes must contain CrossPackConsistencyReasonCode values")
        if not isinstance(self.data_quality, CrossPackConsistencyDataQuality):
            raise ValueError("data_quality must be a CrossPackConsistencyDataQuality")
        if not isinstance(self.safety_flags, CrossPackConsistencySafetyFlags):
            raise ValueError("safety_flags must be a CrossPackConsistencySafetyFlags")
        object.__setattr__(self, "metadata", _coerce_str_mapping(self.metadata))
        _ensure_str_with_default(self.notes, "notes")

    @classmethod
    def blocked(
        cls,
        *,
        input: CrossPackConsistencyInput,
        reason_code: CrossPackConsistencyReasonCode = CrossPackConsistencyReasonCode.UNSAFE_CONTENT,
        generated_at: datetime | None = None,
        safety_flags: CrossPackConsistencySafetyFlags | None = None,
        notes: str = "",
    ) -> "CrossPackConsistencyReport":
        """Create a deterministic fail-closed blocked cross-pack consistency report."""
        if generated_at is None:
            generated_at = input.generated_at if input.generated_at is not None else datetime.now(timezone.utc)
        if safety_flags is None:
            if reason_code == CrossPackConsistencyReasonCode.FORBIDDEN_TERM_PRESENT:
                safety_flags = CrossPackConsistencySafetyFlags(has_forbidden_terms=True)
            else:
                safety_flags = CrossPackConsistencySafetyFlags()
        data_quality = CrossPackConsistencyDataQuality(
            total_packs=len(input.declarations),
            total_artifact_refs=len(input.artifact_refs),
            total_section_refs=len(input.section_refs),
            total_requirement_refs=len(input.requirement_refs),
            total_state_claims=len(input.state_claims),
            total_rules=len(input.rules),
        )
        return cls(
            report_id="cross_pack_consistency_blocked",
            state=CrossPackConsistencyState.BLOCKED,
            reason_codes=(
                CrossPackConsistencyReasonCode.SAFETY_BLOCKED,
                reason_code,
            ),
            declarations=tuple(input.declarations),
            artifact_refs=tuple(input.artifact_refs),
            section_refs=tuple(input.section_refs),
            requirement_refs=tuple(input.requirement_refs),
            state_claims=tuple(input.state_claims),
            rules=tuple(input.rules),
            issues=(),
            data_quality=data_quality,
            safety_flags=safety_flags,
            generated_at=generated_at,
            project_version=input.project_version,
            notes=notes,
        )
