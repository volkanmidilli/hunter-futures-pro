"""Frozen dataclasses for hunter.research_audit_closure package.

MVP-22 — Local Research Audit Closure Report.

All dataclasses are frozen. Validation runs in __post_init__.
File references and metadata strings are local strings only and are never
traversed, opened, followed, validated, or executed.

The research audit closure report is a human-audit / contractor-handoff
artifact only. It is not release approval, deployment approval, trading
signal, trade approval, execution approval, strategy approval, or transaction
permission.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any

CLOSURE_VERSION = "1.0"


class AuditClosureState(Enum):
    """Overall state of the research audit closure report."""

    READY = "ready"
    INCOMPLETE = "incomplete"
    BLOCK = "block"
    UNKNOWN = "unknown"


class AuditClosureKind(Enum):
    """Kind of closure report."""

    RESEARCH_AUDIT_CLOSURE = "research_audit_closure"


class AuditClosureSectionKind(Enum):
    """Deterministic section ordering for the closure report."""

    OVERVIEW = "overview"
    CYCLE_SCOPE = "cycle_scope"
    COMPLETED_ARTIFACTS = "completed_artifacts"
    OPEN_FINDINGS = "open_findings"
    BACKLOG_NOTES = "backlog_notes"
    SAFETY_BOUNDARIES = "safety_boundaries"
    HUMAN_ARCHIVAL_GUIDE = "human_archival_guide"
    APPENDIX_REFERENCES = "appendix_references"


class AuditClosureFindingSeverity(Enum):
    """Severity of an open finding."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


# Deterministic canonical order for closure report sections.
AUDIT_CLOSURE_SECTION_KINDS: tuple[AuditClosureSectionKind, ...] = (
    AuditClosureSectionKind.OVERVIEW,
    AuditClosureSectionKind.CYCLE_SCOPE,
    AuditClosureSectionKind.COMPLETED_ARTIFACTS,
    AuditClosureSectionKind.OPEN_FINDINGS,
    AuditClosureSectionKind.BACKLOG_NOTES,
    AuditClosureSectionKind.SAFETY_BOUNDARIES,
    AuditClosureSectionKind.HUMAN_ARCHIVAL_GUIDE,
    AuditClosureSectionKind.APPENDIX_REFERENCES,
)

# Deterministic severity priority for finding ordering (lower = more severe).
# Keys are uppercase because AuditClosureFinding.severity is normalized to uppercase.
_AUDIT_CLOSURE_FINDING_SEVERITY_PRIORITY: dict[str, int] = {
    AuditClosureFindingSeverity.CRITICAL.name: 0,
    AuditClosureFindingSeverity.HIGH.name: 1,
    AuditClosureFindingSeverity.MEDIUM.name: 2,
    AuditClosureFindingSeverity.LOW.name: 3,
    AuditClosureFindingSeverity.INFO.name: 4,
}

# Reason codes — deterministic, priority-ordered tuple.
MISSING_ARTIFACTS = "MISSING_ARTIFACTS"
INVALID_ARTIFACT_SUMMARY = "INVALID_ARTIFACT_SUMMARY"
INVALID_CLOSURE_CONFIG = "INVALID_CLOSURE_CONFIG"
UNSAFE_CLOSURE_CONFIG = "UNSAFE_CLOSURE_CONFIG"
MISSING_REQUIRED_SECTION = "MISSING_REQUIRED_SECTION"
EMPTY_COMPLETED_ARTIFACTS = "EMPTY_COMPLETED_ARTIFACTS"
UNRESOLVED_BLOCKERS = "UNRESOLVED_BLOCKERS"
UNSAFE_CLOSURE_CONTENT = "UNSAFE_CLOSURE_CONTENT"
INCOMPLETE_ARTIFACT_CHAIN = "INCOMPLETE_ARTIFACT_CHAIN"
OPEN_FINDINGS_REMAIN = "OPEN_FINDINGS_REMAIN"
BACKLOG_NOTES_REMAIN = "BACKLOG_NOTES_REMAIN"
SECTION_BUILD_ERROR = "SECTION_BUILD_ERROR"
SUMMARY_BUILD_ERROR = "SUMMARY_BUILD_ERROR"
DATA_QUALITY_ERROR = "DATA_QUALITY_ERROR"
CLOSURE_ERROR = "CLOSURE_ERROR"
UNKNOWN_CLOSURE_STATE = "UNKNOWN_CLOSURE_STATE"
DEFAULT_BLOCKED = "DEFAULT_BLOCKED"

AUDIT_CLOSURE_REASON_CODES: tuple[str, ...] = (
    MISSING_ARTIFACTS,
    INVALID_ARTIFACT_SUMMARY,
    INVALID_CLOSURE_CONFIG,
    UNSAFE_CLOSURE_CONFIG,
    MISSING_REQUIRED_SECTION,
    EMPTY_COMPLETED_ARTIFACTS,
    UNRESOLVED_BLOCKERS,
    UNSAFE_CLOSURE_CONTENT,
    INCOMPLETE_ARTIFACT_CHAIN,
    OPEN_FINDINGS_REMAIN,
    BACKLOG_NOTES_REMAIN,
    SECTION_BUILD_ERROR,
    SUMMARY_BUILD_ERROR,
    DATA_QUALITY_ERROR,
    CLOSURE_ERROR,
    UNKNOWN_CLOSURE_STATE,
    DEFAULT_BLOCKED,
)

AUDIT_CLOSURE_BLOCKING_REASON_CODES: tuple[str, ...] = (
    MISSING_ARTIFACTS,
    INVALID_ARTIFACT_SUMMARY,
    INVALID_CLOSURE_CONFIG,
    UNSAFE_CLOSURE_CONFIG,
    UNSAFE_CLOSURE_CONTENT,
    SECTION_BUILD_ERROR,
    SUMMARY_BUILD_ERROR,
    DATA_QUALITY_ERROR,
    CLOSURE_ERROR,
    DEFAULT_BLOCKED,
)

AUDIT_CLOSURE_INCOMPLETE_REASON_CODES: tuple[str, ...] = (
    MISSING_REQUIRED_SECTION,
    EMPTY_COMPLETED_ARTIFACTS,
    UNRESOLVED_BLOCKERS,
    INCOMPLETE_ARTIFACT_CHAIN,
)

AUDIT_CLOSURE_NON_BLOCKING_REASON_CODES: tuple[str, ...] = (
    OPEN_FINDINGS_REMAIN,
    BACKLOG_NOTES_REMAIN,
)

# Superset of forbidden terms from prior MVPs plus release/deployment-approval
# and action-command keywords.
FORBIDDEN_CLOSURE_TERMS: frozenset[str] = frozenset({
    # Credential / secret terms
    "api_key",
    "secret",
    "exchange_credentials",
    "executable_instructions",
    "operational_instructions",
    "private_key",
    "password",
    "token",
    "auth",
    # Trading execution terms
    "enter_long",
    "enter_short",
    "exit_long",
    "exit_short",
    "buy_now",
    "sell_now",
    "execute_trade",
    "place_order",
    "market_order",
    "limit_order",
    "stop_loss",
    "take_profit",
    "order",
    "position",
    "leverage",
    "shorting",
    "margin",
    "liquidation",
    "live_trade",
    "real_order",
    "position_size",
    # Exchange / runtime terms
    "binance",
    # Release/deployment/execution readiness terms (must not imply approval)
    "go_live",
    "production_ready",
    "execution_ready",
    "strategy_ready",
    "deployment_ready",
    "release_ready",
    "launch_live",
    "release_approved",
    "deploy_now",
    # Action-command keywords (must not emit action commands)
    "deploy",
    "execute",
    "run",
    "start",
    "stop",
    "trigger",
})


def _ensure_timezone_aware(value: datetime, field_name: str) -> datetime:
    """Raise ValueError if value is a naive datetime (tzinfo is None)."""
    if not isinstance(value, datetime):
        raise ValueError(f"{field_name} must be a datetime")
    if value.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value


def _ensure_tuple_of_str(
    value: Iterable[str] | tuple[str, ...] | list[str] | None,
    field_name: str,
) -> tuple[str, ...]:
    """Validate that value is a tuple/list of non-empty strings."""
    if value is None:
        return ()
    if isinstance(value, (tuple, list)):
        for item in value:
            if not isinstance(item, str) or not item:
                raise ValueError(f"{field_name} must contain non-empty strings")
        return tuple(value)
    raise ValueError(f"{field_name} must be a tuple or list of strings")


def _has_forbidden_closure_term(text: str) -> bool:
    """Case-insensitive check for forbidden terms in a single string."""
    if not isinstance(text, str):
        return False
    lower = text.lower()
    for term in FORBIDDEN_CLOSURE_TERMS:
        if term in lower:
            return True
    return False


def _check_forbidden_mapping(mapping: Mapping[str, Any]) -> bool:
    """Return True if any key or string value in mapping contains forbidden terms."""
    for key, value in mapping.items():
        if isinstance(key, str) and _has_forbidden_closure_term(key):
            return True
        if isinstance(value, str) and _has_forbidden_closure_term(value):
            return True
        if isinstance(value, (tuple, list)):
            for item in value:
                if isinstance(item, str) and _has_forbidden_closure_term(item):
                    return True
        if isinstance(value, Mapping):
            if _check_forbidden_mapping(value):
                return True
    return False


def _check_forbidden_closure_content(
    text_fields: tuple[str, ...],
    string_sequences: tuple[str, ...],
    metadata: Mapping[str, Any],
) -> None:
    """Check all text fields, string sequences, and metadata keys for forbidden terms."""
    for text in text_fields:
        if _has_forbidden_closure_term(text):
            raise ValueError("UNSAFE_CLOSURE_CONTENT")
    for seq in string_sequences:
        if _has_forbidden_closure_term(seq):
            raise ValueError("UNSAFE_CLOSURE_CONTENT")
    if _check_forbidden_mapping(metadata):
        raise ValueError("UNSAFE_CLOSURE_CONTENT")


def _coerce_metadata(value: Mapping[str, Any] | dict[str, Any] | None) -> Mapping[str, Any]:
    """Coerce a mapping into an immutable MappingProxyType."""
    if value is None:
        return MappingProxyType({})
    if isinstance(value, Mapping):
        return MappingProxyType(dict(value))
    raise ValueError("metadata must be a mapping")


def _extract_mvp_number(related_mvp: str) -> int:
    """Extract trailing integer from strings like 'MVP-22'.

    Returns a large sentinel value for empty or unparseable strings so they
    sort last in deterministic finding ordering.
    """
    if not isinstance(related_mvp, str) or not related_mvp:
        return 1_000_000
    digits = "".join(ch for ch in related_mvp if ch.isdigit())
    if not digits:
        return 1_000_000
    return int(digits)


def _order_findings(findings: Iterable[AuditClosureFinding]) -> tuple[AuditClosureFinding, ...]:
    """Order findings by (severity_priority, mvp_number, insertion_order)."""
    enumerated = list(enumerate(findings))
    enumerated.sort(key=lambda item: (
        _AUDIT_CLOSURE_FINDING_SEVERITY_PRIORITY.get(item[1].severity, 999),
        _extract_mvp_number(item[1].related_mvp),
        item[0],
    ))
    return tuple(item[1] for item in enumerated)


@dataclass(frozen=True)
class AuditClosureConfig:
    """Configuration for closure report building."""

    version: str = CLOSURE_VERSION
    generated_at: datetime | None = None
    output_format: str = "both"
    dry_run: bool = True
    live_trading_enabled: bool = False
    real_orders_enabled: bool = False
    leverage_enabled: bool = False
    shorting_enabled: bool = False
    block_on_unknown: bool = True
    block_on_incomplete: bool = False
    expected_artifact_count: int = 12
    required_sections: tuple[AuditClosureSectionKind, ...] = (
        AuditClosureSectionKind.OVERVIEW,
        AuditClosureSectionKind.CYCLE_SCOPE,
        AuditClosureSectionKind.COMPLETED_ARTIFACTS,
        AuditClosureSectionKind.OPEN_FINDINGS,
        AuditClosureSectionKind.BACKLOG_NOTES,
        AuditClosureSectionKind.SAFETY_BOUNDARIES,
        AuditClosureSectionKind.HUMAN_ARCHIVAL_GUIDE,
        AuditClosureSectionKind.APPENDIX_REFERENCES,
    )
    include_closure_narrative: bool = True

    def __post_init__(self) -> None:
        if not isinstance(self.version, str) or not self.version:
            raise ValueError("version must be a non-empty string")
        if self.output_format not in ("json", "markdown", "both"):
            raise ValueError("output_format must be json, markdown, or both")
        if not self.dry_run:
            raise ValueError("dry_run must be True")
        if any((
            self.live_trading_enabled,
            self.real_orders_enabled,
            self.leverage_enabled,
            self.shorting_enabled,
        )):
            raise ValueError("live trading flags must be False")
        if not isinstance(self.expected_artifact_count, int) or self.expected_artifact_count < 0:
            raise ValueError("expected_artifact_count must be a non-negative integer")
        if not all(isinstance(s, AuditClosureSectionKind) for s in self.required_sections):
            raise ValueError("required_sections must be AuditClosureSectionKind values")


@dataclass(frozen=True)
class AuditClosureSafetyFlags:
    """Safety invariants for the closure report."""

    # Runtime safety flags
    dry_run: bool = True
    live_trading_enabled: bool = False
    real_orders_enabled: bool = False
    leverage_enabled: bool = False
    shorting_enabled: bool = False

    # Output safety flags
    closure_output_is_human_audit_only: bool = True
    closure_output_not_trading_signal: bool = True
    closure_output_not_trade_approval: bool = True
    closure_output_not_execution_readiness: bool = True
    closure_output_not_strategy_readiness: bool = True
    closure_output_not_release_approval: bool = True
    closure_output_not_deployment_approval: bool = True
    closure_output_not_transaction_permission: bool = True
    closure_output_not_for_execution: bool = True
    closure_output_not_for_strategy: bool = True
    closure_output_not_for_freqtrade: bool = True
    closure_output_not_for_order: bool = True
    closure_output_not_for_exchange: bool = True

    # Feedback safety flags
    closure_feedback_into_execution: bool = False
    cross_layer_feedback_into_execution: bool = False

    # Capability flags
    file_reference_traversal_enabled: bool = False
    database_persistence_enabled: bool = False
    web_ui_enabled: bool = False
    dashboard_enabled: bool = False
    runtime_registry_enabled: bool = False
    indexer_crawler_enabled: bool = False
    event_store_enabled: bool = False
    task_runner_enabled: bool = False

    # Advisory flags
    file_refs_not_traversed: bool = True
    artifact_files_not_read: bool = True
    no_action_commands_emitted: bool = True
    human_archival_guide_is_non_gating: bool = True

    def __post_init__(self) -> None:
        unsafe_flags = (
            self.live_trading_enabled,
            self.real_orders_enabled,
            self.leverage_enabled,
            self.shorting_enabled,
            self.closure_feedback_into_execution,
            self.cross_layer_feedback_into_execution,
            self.file_reference_traversal_enabled,
            self.database_persistence_enabled,
            self.web_ui_enabled,
            self.dashboard_enabled,
            self.runtime_registry_enabled,
            self.indexer_crawler_enabled,
            self.event_store_enabled,
            self.task_runner_enabled,
        )
        if any(unsafe_flags):
            raise ValueError("unsafe closure safety flags are enabled")
        safe_flags = (
            self.closure_output_is_human_audit_only,
            self.closure_output_not_trading_signal,
            self.closure_output_not_trade_approval,
            self.closure_output_not_execution_readiness,
            self.closure_output_not_strategy_readiness,
            self.closure_output_not_release_approval,
            self.closure_output_not_deployment_approval,
            self.closure_output_not_transaction_permission,
            self.closure_output_not_for_execution,
            self.closure_output_not_for_strategy,
            self.closure_output_not_for_freqtrade,
            self.closure_output_not_for_order,
            self.closure_output_not_for_exchange,
            self.file_refs_not_traversed,
            self.artifact_files_not_read,
            self.no_action_commands_emitted,
            self.human_archival_guide_is_non_gating,
        )
        if not all(safe_flags):
            raise ValueError("safe closure output flags must be True")


@dataclass(frozen=True)
class AuditClosureFinding:
    """One open finding in the closure report."""

    finding_id: str
    title: str
    severity: str = "INFO"
    description: str = ""
    related_mvp: str = ""
    spec_reference: str = ""
    related_references: tuple[str, ...] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if not isinstance(self.finding_id, str) or not self.finding_id:
            raise ValueError("finding_id must be a non-empty string")
        if not isinstance(self.title, str) or not self.title:
            raise ValueError("title must be a non-empty string")
        severity_upper = self.severity.upper()
        if severity_upper not in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"):
            raise ValueError(f"unsupported severity: {self.severity}")
        object.__setattr__(self, "severity", severity_upper)
        object.__setattr__(
            self, "related_references", _ensure_tuple_of_str(self.related_references, "related_references")
        )
        object.__setattr__(self, "metadata", _coerce_metadata(self.metadata))
        _check_forbidden_closure_content(
            (self.title, self.description, self.spec_reference),
            self.related_references,
            self.metadata,
        )


@dataclass(frozen=True)
class AuditClosureSection:
    """One section of the closure report."""

    section_kind: AuditClosureSectionKind
    title: str
    section_notes: str = ""
    findings: tuple[AuditClosureFinding, ...] = field(default_factory=tuple)
    completed_artifacts: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    backlog_notes: tuple[str, ...] = field(default_factory=tuple)
    references: tuple[str, ...] = field(default_factory=tuple)
    metadata: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    def __post_init__(self) -> None:
        if not isinstance(self.section_kind, AuditClosureSectionKind):
            raise ValueError("section_kind must be AuditClosureSectionKind")
        if not isinstance(self.title, str) or not self.title:
            raise ValueError("title must be a non-empty string")
        object.__setattr__(self, "backlog_notes", _ensure_tuple_of_str(self.backlog_notes, "backlog_notes"))
        object.__setattr__(self, "references", _ensure_tuple_of_str(self.references, "references"))
        object.__setattr__(self, "metadata", _coerce_metadata(self.metadata))
        _check_forbidden_closure_content(
            (self.title, self.section_notes),
            self.references,
            self.metadata,
        )
        if not isinstance(self.findings, tuple):
            raise ValueError("findings must be a tuple")
        for finding in self.findings:
            if not isinstance(finding, AuditClosureFinding):
                raise ValueError("findings must contain AuditClosureFinding values")
        object.__setattr__(self, "findings", _order_findings(self.findings))
        if not isinstance(self.completed_artifacts, tuple):
            raise ValueError("completed_artifacts must be a tuple")
        for artifact in self.completed_artifacts:
            if not isinstance(artifact, Mapping):
                raise ValueError("completed_artifacts must contain mapping values")


@dataclass(frozen=True)
class AuditClosureSummary:
    """Aggregated counts and closure narrative."""

    total_sections: int = 0
    total_findings: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    info_count: int = 0
    completed_artifact_count: int = 0
    open_finding_count: int = 0
    backlog_note_count: int = 0
    closure_state: str = "UNKNOWN"
    reason_code_counts: Mapping[str, int] = field(default_factory=lambda: MappingProxyType({}))
    closure_narrative: str = ""

    def __post_init__(self) -> None:
        for field_name in (
            "total_sections", "total_findings", "critical_count",
            "high_count", "medium_count", "low_count", "info_count",
            "completed_artifact_count", "open_finding_count", "backlog_note_count",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer")
        severity_sum = (
            self.critical_count + self.high_count + self.medium_count +
            self.low_count + self.info_count
        )
        if severity_sum != self.total_findings:
            raise ValueError("severity counts must sum to total_findings")
        if self.closure_state not in ("READY", "INCOMPLETE", "BLOCK", "UNKNOWN"):
            raise ValueError("closure_state must be READY, INCOMPLETE, BLOCK, or UNKNOWN")
        _check_forbidden_closure_content((self.closure_narrative,), (), dict(self.reason_code_counts))
        object.__setattr__(self, "reason_code_counts", MappingProxyType(dict(self.reason_code_counts)))


@dataclass(frozen=True)
class AuditClosureDataQuality:
    """Completeness and quality metrics for the closure report."""

    total_artifacts_expected: int = 12  # MVP-10 through MVP-21
    artifacts_present: int = 0
    artifacts_missing: int = 12  # fail-closed default: all expected artifacts missing
    sections_present: int = 0
    sections_missing: int = 8  # fail-closed default: all eight sections missing
    total_findings: int = 0
    unresolved_blocker_count: int = 0
    unresolved_warning_count: int = 0
    backlog_note_count: int = 0
    completeness_pct: float = 0.0
    coverage_pct: float = 0.0
    reason: str = ""

    def __post_init__(self) -> None:
        for field_name in (
            "total_artifacts_expected", "artifacts_present", "artifacts_missing",
            "sections_present", "sections_missing", "total_findings",
            "unresolved_blocker_count", "unresolved_warning_count", "backlog_note_count",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer")
        if self.artifacts_present + self.artifacts_missing != self.total_artifacts_expected:
            raise ValueError("artifacts_present + artifacts_missing must equal total_artifacts_expected")
        if self.sections_present + self.sections_missing != len(AUDIT_CLOSURE_SECTION_KINDS):
            raise ValueError("sections_present + sections_missing must equal total section count")
        for pct_field in ("completeness_pct", "coverage_pct"):
            value = getattr(self, pct_field)
            if not isinstance(value, (int, float)):
                raise ValueError(f"{pct_field} must be a number")
            if value < 0.0 or value > 100.0:
                raise ValueError(f"{pct_field} must be between 0.0 and 100.0")
        _check_forbidden_closure_content((self.reason,), (), {})


@dataclass(frozen=True)
class ResearchAuditClosureReport:
    """Full research audit closure report container."""

    closure_id: str
    generated_at: datetime
    version: str = CLOSURE_VERSION
    closure_kind: AuditClosureKind = field(
        default_factory=lambda: AuditClosureKind.RESEARCH_AUDIT_CLOSURE
    )
    closure_state: AuditClosureState = field(
        default_factory=lambda: AuditClosureState.UNKNOWN
    )
    sections: tuple[AuditClosureSection, ...] = field(default_factory=tuple)
    summary: AuditClosureSummary = field(default_factory=AuditClosureSummary)
    data_quality: AuditClosureDataQuality = field(
        default_factory=AuditClosureDataQuality
    )
    safety_flags: AuditClosureSafetyFlags = field(
        default_factory=AuditClosureSafetyFlags
    )
    config: AuditClosureConfig = field(default_factory=AuditClosureConfig)
    reason_codes: tuple[str, ...] = field(
        default_factory=lambda: (UNKNOWN_CLOSURE_STATE,)
    )
    closure_narrative: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.closure_id, str) or not self.closure_id:
            raise ValueError("closure_id must be a non-empty string")
        _ensure_timezone_aware(self.generated_at, "generated_at")
        if not isinstance(self.version, str) or not self.version:
            raise ValueError("version must be a non-empty string")
        if not isinstance(self.closure_kind, AuditClosureKind):
            raise ValueError("closure_kind must be AuditClosureKind")
        if not isinstance(self.closure_state, AuditClosureState):
            raise ValueError("closure_state must be AuditClosureState")
        for section in self.sections:
            if not isinstance(section, AuditClosureSection):
                raise ValueError("sections must contain AuditClosureSection values")
        if not isinstance(self.summary, AuditClosureSummary):
            raise ValueError("summary must be AuditClosureSummary")
        if not isinstance(self.data_quality, AuditClosureDataQuality):
            raise ValueError("data_quality must be AuditClosureDataQuality")
        if not isinstance(self.safety_flags, AuditClosureSafetyFlags):
            raise ValueError("safety_flags must be AuditClosureSafetyFlags")
        if not isinstance(self.config, AuditClosureConfig):
            raise ValueError("config must be AuditClosureConfig")
        object.__setattr__(self, "reason_codes", _ensure_tuple_of_str(self.reason_codes, "reason_codes"))
        for code in self.reason_codes:
            if code not in AUDIT_CLOSURE_REASON_CODES:
                raise ValueError(f"unsupported reason code: {code}")
        _check_forbidden_closure_content((self.closure_narrative,), (), {})
        if self.closure_state in (AuditClosureState.BLOCK, AuditClosureState.UNKNOWN) and not self.reason_codes:
            raise ValueError("reason_codes must be non-empty when closure_state is BLOCK or UNKNOWN")

    @classmethod
    def blocked(
        cls,
        *,
        closure_id: str = "blocked",
        generated_at: datetime | None = None,
        reason_code: str = DEFAULT_BLOCKED,
        safety_flags: AuditClosureSafetyFlags | None = None,
    ) -> "ResearchAuditClosureReport":
        """Create a deterministic fail-closed blocked closure report.

        Does not read files, traverse references, or emit action commands.
        Constructs its own valid summary and data-quality objects so that
        no model is instantiated with invalid default values.
        """
        if reason_code not in AUDIT_CLOSURE_REASON_CODES:
            raise ValueError(f"unsupported reason code: {reason_code}")
        if generated_at is None:
            generated_at = datetime.now(timezone.utc)
        if safety_flags is None:
            safety_flags = AuditClosureSafetyFlags()
        return cls(
            closure_id=closure_id,
            generated_at=generated_at,
            closure_state=AuditClosureState.BLOCK,
            sections=(),
            summary=AuditClosureSummary(
                total_sections=0,
                closure_state=AuditClosureState.BLOCK.value.upper(),
                reason_code_counts={reason_code: 1},
            ),
            data_quality=AuditClosureDataQuality(
                total_artifacts_expected=12,
                artifacts_present=0,
                artifacts_missing=12,
                sections_present=0,
                sections_missing=8,
            ),
            safety_flags=safety_flags,
            reason_codes=(reason_code,),
            closure_narrative="Closure report is blocked for audit purposes only.",
        )
