"""Frozen dataclasses for hunter.final_audit_pack package.

MVP-32 — Local Research Final Audit Pack Export.

All dataclasses are frozen. Validation runs in __post_init__. The final audit
pack only accepts caller-provided in-memory inputs and opaque artifact reference
strings. It never opens, follows, traverses, validates, fetches, or executes
metadata or file-reference strings. All metadata and artifact references are
opaque local strings only.

The final audit pack is a human-audit / research artifact only. It is not a
trading signal, not trade approval, not strategy approval, not execution
approval, not portfolio approval, not universe approval, and not a certification
of trading readiness. It does not emit action commands, suggest orders, or create
execution instructions.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any

FINAL_AUDIT_PACK_VERSION: str = "0.32.0-dev"


class FinalAuditPackState(Enum):
    """Normalized state of a final audit pack section."""

    INCLUDED = "included"
    EXCLUDED = "excluded"
    BLOCKED = "blocked"
    INSUFFICIENT_DATA = "insufficient_data"


class FinalAuditPackReasonCode(Enum):
    """Reason codes for final audit pack sections and reports."""

    OK = "OK"
    MISSING_REQUIRED_SECTIONS = "MISSING_REQUIRED_SECTIONS"
    DUPLICATE_SECTION_ID = "DUPLICATE_SECTION_ID"
    UNSAFE_CONTENT = "UNSAFE_CONTENT"
    INVALID_SECTION = "INVALID_SECTION"
    MISSING_REQUIRED_FIELDS = "MISSING_REQUIRED_FIELDS"
    RESEARCH_ONLY = "RESEARCH_ONLY"
    NOT_TRADING_ADVICE = "NOT_TRADING_ADVICE"
    NO_FILE_INGESTION = "NO_FILE_INGESTION"
    NO_NETWORK_CONNECTION = "NO_NETWORK_CONNECTION"
    NO_EXCHANGE_CONNECTION = "NO_EXCHANGE_CONNECTION"
    NO_FREQTRADE_INPUT = "NO_FREQTRADE_INPUT"
    NO_SCHEDULER = "NO_SCHEDULER"
    NO_DAEMON = "NO_DAEMON"
    NO_WEB_UI = "NO_WEB_UI"
    NO_DATABASE = "NO_DATABASE"
    NO_ACTION_COMMANDS_EMITTED = "NO_ACTION_COMMANDS_EMITTED"
    HUMAN_RESEARCH_ONLY = "HUMAN_RESEARCH_ONLY"


# String constants for convenient use in reason code tuples and frozensets.
OK = FinalAuditPackReasonCode.OK.value
MISSING_REQUIRED_SECTIONS = FinalAuditPackReasonCode.MISSING_REQUIRED_SECTIONS.value
DUPLICATE_SECTION_ID = FinalAuditPackReasonCode.DUPLICATE_SECTION_ID.value
UNSAFE_CONTENT = FinalAuditPackReasonCode.UNSAFE_CONTENT.value
INVALID_SECTION = FinalAuditPackReasonCode.INVALID_SECTION.value
MISSING_REQUIRED_FIELDS = FinalAuditPackReasonCode.MISSING_REQUIRED_FIELDS.value
RESEARCH_ONLY = FinalAuditPackReasonCode.RESEARCH_ONLY.value
NOT_TRADING_ADVICE = FinalAuditPackReasonCode.NOT_TRADING_ADVICE.value
NO_FILE_INGESTION = FinalAuditPackReasonCode.NO_FILE_INGESTION.value
NO_NETWORK_CONNECTION = FinalAuditPackReasonCode.NO_NETWORK_CONNECTION.value
NO_EXCHANGE_CONNECTION = FinalAuditPackReasonCode.NO_EXCHANGE_CONNECTION.value
NO_FREQTRADE_INPUT = FinalAuditPackReasonCode.NO_FREQTRADE_INPUT.value
NO_SCHEDULER = FinalAuditPackReasonCode.NO_SCHEDULER.value
NO_DAEMON = FinalAuditPackReasonCode.NO_DAEMON.value
NO_WEB_UI = FinalAuditPackReasonCode.NO_WEB_UI.value
NO_DATABASE = FinalAuditPackReasonCode.NO_DATABASE.value
NO_ACTION_COMMANDS_EMITTED = FinalAuditPackReasonCode.NO_ACTION_COMMANDS_EMITTED.value
HUMAN_RESEARCH_ONLY = FinalAuditPackReasonCode.HUMAN_RESEARCH_ONLY.value

FINAL_AUDIT_PACK_REASON_CODES: tuple[str, ...] = tuple(
    code.value for code in FinalAuditPackReasonCode
)
FINAL_AUDIT_PACK_BLOCKING_REASON_CODES: frozenset[str] = frozenset({
    UNSAFE_CONTENT,
    DUPLICATE_SECTION_ID,
    INVALID_SECTION,
    MISSING_REQUIRED_FIELDS,
})
FINAL_AUDIT_PACK_ADVISORY_REASON_CODES: frozenset[str] = frozenset({
    OK,
    RESEARCH_ONLY,
    NOT_TRADING_ADVICE,
    NO_FILE_INGESTION,
    NO_NETWORK_CONNECTION,
    NO_EXCHANGE_CONNECTION,
    NO_FREQTRADE_INPUT,
    NO_SCHEDULER,
    NO_DAEMON,
    NO_WEB_UI,
    NO_DATABASE,
    NO_ACTION_COMMANDS_EMITTED,
    HUMAN_RESEARCH_ONLY,
})


# Section kinds used by the final audit pack engine.
BACKTEST_SECTION_KIND = "backtest"
RUN_ORCHESTRATOR_SECTION_KIND = "run_orchestrator"
EXPERIMENT_LEDGER_SECTION_KIND = "experiment_ledger"
PORTFOLIO_CONSTRUCTION_SECTION_KIND = "portfolio_construction"
DISCOVERY_SECTION_KIND = "discovery"
REPORTING_CLI_SECTION_KIND = "reporting_cli"

DEFAULT_REQUIRED_SECTION_KINDS: tuple[str, ...] = (
    BACKTEST_SECTION_KIND,
    RUN_ORCHESTRATOR_SECTION_KIND,
    EXPERIMENT_LEDGER_SECTION_KIND,
)
DEFAULT_OPTIONAL_SECTION_KINDS: tuple[str, ...] = (
    DISCOVERY_SECTION_KIND,
    PORTFOLIO_CONSTRUCTION_SECTION_KIND,
    REPORTING_CLI_SECTION_KIND,
)


# Forbidden terms for the final audit pack's own local safety scanner.
# The final audit pack does not import a safety scanner from any other package.
FORBIDDEN_FINAL_AUDIT_PACK_TERMS: frozenset[str] = frozenset({
    # Action / execution
    "buy",
    "sell",
    "order",
    "orders",
    "execute",
    "execution",
    "entry",
    "exit",
    "stop loss",
    "stop_loss",
    "take profit",
    "take_profit",
    "leverage",
    "margin",
    "liquidation",
    "liquidate",
    "fill",
    "filling",
    "short",
    "shorting",
    "position",
    "positions",
    "position_size",
    "position sizing",
    "position_sizing",
    "order_size",
    "order sizing",
    "order_sizing",
    "trade_size",
    "trade sizing",
    "trade_sizing",
    "capital_allocation",
    "capital allocation",
    # Approval / action
    "approve",
    "approval",
    "approved",
    "action_command",
    "action command",
    "emit",
    "rebalance",
    "deploy",
    "deploy_capital",
    "deploy capital",
    "go_live",
    "go live",
    "production_ready",
    "production ready",
    "execution_ready",
    "execution ready",
    "strategy_ready",
    "strategy ready",
    "deployment_ready",
    "deployment ready",
    "release_ready",
    "release ready",
    "launch_live",
    "launch live",
    # Freqtrade
    "freqtrade",
    "freq_trade",
    "freqtrade_strategy",
    "freqtrade_input",
    # Exchange / API / network
    "binance",
    "exchange",
    "api",
    "api_key",
    "apikey",
    "secret",
    "webhook",
    "web_hook",
    "live_data",
    "live data",
    "real_time",
    "realtime",
    "real_time_data",
    "market_data_feed",
    "tick_data",
    # Runtime infrastructure
    "scheduler",
    "cron",
    "daemon",
    "background",
    "job runner",
    "job_runner",
    "task queue",
    "task_queue",
    "worker",
    "server",
    "rest_api",
    "rest api",
    "websocket",
    "web socket",
    "database",
    "dashboard",
    "web_ui",
    "web ui",
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ensure_tuple(
    value: tuple[Any, ...] | Iterable[Any] | None,
    field_name: str,
) -> tuple[Any, ...]:
    """Validate and coerce an iterable to a tuple."""
    if value is None:
        return ()
    if isinstance(value, tuple):
        return value
    if isinstance(value, Iterable):
        return tuple(value)
    raise ValueError(f"{field_name} must be iterable")


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


def _ensure_non_empty_tuple_of_str(
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
    raise ValueError(f"{field_name} must be a tuple or list of non-empty strings")


def _ensure_timezone_aware(
    value: datetime | None,
    field_name: str,
) -> datetime | None:
    """Raise ValueError if value is a naive datetime."""
    if value is None:
        return None
    if not isinstance(value, datetime):
        raise ValueError(f"{field_name} must be a datetime")
    if value.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware")
    return value


def _coerce_metadata(
    value: Mapping[str, Any] | dict[str, Any] | None,
) -> Mapping[str, Any]:
    """Coerce a mapping into an immutable MappingProxyType."""
    if value is None:
        return MappingProxyType({})
    if isinstance(value, Mapping):
        return MappingProxyType(dict(value))
    raise ValueError("metadata must be a mapping")


def _has_forbidden_term(text: str, forbidden_terms: frozenset[str]) -> bool:
    """Case-insensitive substring check for forbidden terms in a single string."""
    if not isinstance(text, str):
        return False
    lower = text.lower()
    return any(term in lower for term in forbidden_terms)


def has_unsafe_final_audit_pack_content(
    text: str | None = None,
    tags: Sequence[str] | None = None,
    forbidden_terms: frozenset[str] | None = None,
) -> bool:
    """Return True if text or tags contain forbidden final audit pack terms.

    Scans only the caller-provided string values. Metadata and artifact
    reference strings remain opaque and are not scanned by this function. The
    final audit pack does not import a safety scanner from any other package.
    """
    terms = forbidden_terms or FORBIDDEN_FINAL_AUDIT_PACK_TERMS
    if text is not None and _has_forbidden_term(text, terms):
        return True
    if tags is not None:
        for tag in tags:
            if isinstance(tag, str) and _has_forbidden_term(tag, terms):
                return True
    return False


# ---------------------------------------------------------------------------
# Safety flags
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FinalAuditPackSafetyFlags:
    """Positive safety invariants and negative safety flags."""

    research_only: bool = True
    not_trading_advice: bool = True
    human_research_only: bool = True
    no_file_ingestion: bool = True
    no_network_connection: bool = True
    no_exchange_connection: bool = True
    no_freqtrade_input: bool = True
    no_scheduler: bool = True
    no_daemon: bool = True
    no_web_ui: bool = True
    no_database: bool = True
    no_action_commands_emitted: bool = True
    has_unsafe_content: bool = False
    has_duplicate_section_id: bool = False
    has_invalid_section: bool = False
    has_missing_required_sections: bool = False
    has_blocked_section: bool = False
    has_insufficient_section: bool = False

    def __post_init__(self) -> None:
        positive_flags = (
            self.research_only,
            self.not_trading_advice,
            self.human_research_only,
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
        """Return True when all positive invariants hold and all negative flags are False."""
        return (
            self.research_only
            and self.not_trading_advice
            and self.human_research_only
            and self.no_file_ingestion
            and self.no_network_connection
            and self.no_exchange_connection
            and self.no_freqtrade_input
            and self.no_scheduler
            and self.no_daemon
            and self.no_web_ui
            and self.no_database
            and self.no_action_commands_emitted
            and not self.has_unsafe_content
            and not self.has_duplicate_section_id
            and not self.has_invalid_section
            and not self.has_missing_required_sections
            and not self.has_blocked_section
            and not self.has_insufficient_section
        )


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FinalAuditPackInput:
    """Caller-provided in-memory reports and opaque artifact references.

    All report fields are tuples of already-loaded in-memory report objects.
    No file reading, path traversal, or remote ingestion is performed by the
    engine. Artifact references are opaque local strings.
    """

    backtest_reports: tuple[Any, ...] = ()
    run_results: tuple[Any, ...] = ()
    experiment_ledger_reports: tuple[Any, ...] = ()
    portfolio_construction_reports: tuple[Any, ...] = ()
    discovery_reports: tuple[Any, ...] = ()
    cli_command_results: tuple[Any, ...] = ()
    artifact_references: tuple[str, ...] = ()
    generated_at: datetime | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "backtest_reports", tuple(self.backtest_reports))
        object.__setattr__(self, "run_results", tuple(self.run_results))
        object.__setattr__(
            self,
            "experiment_ledger_reports",
            tuple(self.experiment_ledger_reports),
        )
        object.__setattr__(
            self,
            "portfolio_construction_reports",
            tuple(self.portfolio_construction_reports),
        )
        object.__setattr__(self, "discovery_reports", tuple(self.discovery_reports))
        object.__setattr__(
            self,
            "cli_command_results",
            tuple(self.cli_command_results),
        )
        object.__setattr__(self, "artifact_references", tuple(self.artifact_references))
        object.__setattr__(self, "tags", _ensure_tuple_of_str(self.tags, "tags"))
        object.__setattr__(self, "metadata", _coerce_metadata(self.metadata))
        _ensure_timezone_aware(self.generated_at, "generated_at")


@dataclass(frozen=True)
class FinalAuditPackArtifact:
    """Opaque local artifact reference. The engine does not open or validate it."""

    kind: str
    reference: str
    display_name: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)
    tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.kind, str) or not self.kind:
            raise ValueError("kind must be a non-empty string")
        if not isinstance(self.reference, str):
            raise ValueError("reference must be a string")
        object.__setattr__(self, "metadata", _coerce_metadata(self.metadata))
        object.__setattr__(self, "tags", _ensure_tuple_of_str(self.tags, "tags"))


@dataclass(frozen=True)
class FinalAuditPackSection:
    """Normalized section from a caller-provided report or report summary.

    `section_id` is the report id, run id, or caller-supplied id. It must be
    unique across all sections. `section_kind` is one of the configured section
    kinds (e.g., 'backtest', 'run_orchestrator', 'experiment_ledger').
    """

    section_id: str
    section_kind: str
    report_id: str = ""
    run_id: str = ""
    name: str = ""
    state: FinalAuditPackState = FinalAuditPackState.INCLUDED
    reason_codes: tuple[str, ...] = ()
    generated_at: datetime | None = None
    tags: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.section_id, str) or not self.section_id:
            raise ValueError("section_id must be a non-empty string")
        if not isinstance(self.section_kind, str) or not self.section_kind:
            raise ValueError("section_kind must be a non-empty string")
        if not isinstance(self.report_id, str):
            raise ValueError("report_id must be a string")
        if not isinstance(self.run_id, str):
            raise ValueError("run_id must be a string")
        if not isinstance(self.name, str):
            raise ValueError("name must be a string")
        if not isinstance(self.state, FinalAuditPackState):
            raise ValueError("state must be a FinalAuditPackState")
        object.__setattr__(self, "reason_codes", _ensure_tuple_of_str(self.reason_codes, "reason_codes"))
        object.__setattr__(self, "tags", _ensure_tuple_of_str(self.tags, "tags"))
        object.__setattr__(self, "metadata", _coerce_metadata(self.metadata))
        _ensure_timezone_aware(self.generated_at, "generated_at")
        for code in self.reason_codes:
            if code not in FINAL_AUDIT_PACK_REASON_CODES:
                raise ValueError(f"unsupported reason code: {code}")
        if self.state is FinalAuditPackState.BLOCKED and not self.reason_codes:
            raise ValueError("BLOCKED sections must have reason_codes")

    @classmethod
    def blocked(
        cls,
        *,
        section_id: str,
        section_kind: str,
        reason_codes: tuple[str, ...],
        report_id: str = "",
        run_id: str = "",
        name: str = "",
        generated_at: datetime | None = None,
        tags: tuple[str, ...] = (),
        metadata: Mapping[str, Any] | None = None,
        notes: tuple[str, ...] = (),
    ) -> "FinalAuditPackSection":
        """Create a fail-closed blocked section."""
        return cls(
            section_id=section_id,
            section_kind=section_kind,
            report_id=report_id,
            run_id=run_id,
            name=name,
            state=FinalAuditPackState.BLOCKED,
            reason_codes=reason_codes,
            generated_at=generated_at,
            tags=tags,
            metadata=metadata,
        )


@dataclass(frozen=True)
class FinalAuditPackConfig:
    """In-memory configuration only. No YAML, JSON schema, or runtime registry."""

    required_section_kinds: tuple[str, ...] = DEFAULT_REQUIRED_SECTION_KINDS
    optional_section_kinds: tuple[str, ...] = DEFAULT_OPTIONAL_SECTION_KINDS
    block_on_missing_required: bool = False
    include_blocked: bool = False
    include_insufficient: bool = False
    generated_at: datetime | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "required_section_kinds",
            _ensure_non_empty_tuple_of_str(self.required_section_kinds, "required_section_kinds"),
        )
        object.__setattr__(
            self,
            "optional_section_kinds",
            _ensure_tuple_of_str(self.optional_section_kinds, "optional_section_kinds"),
        )
        if not isinstance(self.block_on_missing_required, bool):
            raise ValueError("block_on_missing_required must be a bool")
        if not isinstance(self.include_blocked, bool):
            raise ValueError("include_blocked must be a bool")
        if not isinstance(self.include_insufficient, bool):
            raise ValueError("include_insufficient must be a bool")
        object.__setattr__(self, "metadata", _coerce_metadata(self.metadata))
        _ensure_timezone_aware(self.generated_at, "generated_at")


@dataclass(frozen=True)
class FinalAuditPackCompleteness:
    """Completeness/readiness summary for the final audit pack."""

    required_sections_present: int = 0
    required_sections_missing: int = 0
    optional_sections_present: int = 0
    artifact_reference_count: int = 0
    blocked_section_count: int = 0
    insufficient_section_count: int = 0
    safety_notice_present: bool = True
    total_sections: int = 0
    sections_expected: int = 0
    sections_present: int = 0
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for attr in (
            "required_sections_present",
            "required_sections_missing",
            "optional_sections_present",
            "artifact_reference_count",
            "blocked_section_count",
            "insufficient_section_count",
            "total_sections",
            "sections_expected",
            "sections_present",
        ):
            value = getattr(self, attr)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{attr} must be a non-negative integer")
        if self.required_sections_present + self.required_sections_missing > self.sections_expected:
            raise ValueError(
                "required present + missing must not exceed sections_expected"
            )
        if self.optional_sections_present > self.sections_expected:
            raise ValueError("optional_sections_present must not exceed sections_expected")
        object.__setattr__(self, "notes", _ensure_tuple_of_str(self.notes, "notes"))


@dataclass(frozen=True)
class FinalAuditPackDataQuality:
    """Data-quality summary of the final audit pack."""

    total_inputs: int = 0
    normalized_sections: int = 0
    blocked_sections: int = 0
    insufficient_sections: int = 0
    excluded_sections: int = 0
    included_sections: int = 0
    sections_present: int = 0
    sections_expected: int = 0
    artifact_references: int = 0
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for attr in (
            "total_inputs",
            "normalized_sections",
            "blocked_sections",
            "insufficient_sections",
            "excluded_sections",
            "included_sections",
            "sections_present",
            "sections_expected",
            "artifact_references",
        ):
            value = getattr(self, attr)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{attr} must be a non-negative integer")
        if self.normalized_sections > self.total_inputs:
            raise ValueError("normalized_sections must not exceed total_inputs")
        state_sum = (
            self.blocked_sections
            + self.insufficient_sections
            + self.excluded_sections
            + self.included_sections
        )
        if state_sum > self.normalized_sections:
            raise ValueError("state counts must not exceed normalized_sections")
        object.__setattr__(self, "notes", _ensure_tuple_of_str(self.notes, "notes"))


@dataclass(frozen=True)
class FinalAuditPackReport:
    """Final local audit pack export report."""

    report_id: str
    generated_at: datetime
    version: str = FINAL_AUDIT_PACK_VERSION
    sections: tuple[FinalAuditPackSection, ...] = ()
    artifacts: tuple[FinalAuditPackArtifact, ...] = ()
    completeness: FinalAuditPackCompleteness = field(
        default_factory=FinalAuditPackCompleteness
    )
    data_quality: FinalAuditPackDataQuality = field(
        default_factory=FinalAuditPackDataQuality
    )
    safety_flags: FinalAuditPackSafetyFlags = field(
        default_factory=FinalAuditPackSafetyFlags
    )
    reason_codes: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.report_id, str) or not self.report_id:
            raise ValueError("report_id must be a non-empty string")
        if not isinstance(self.version, str) or not self.version:
            raise ValueError("version must be a non-empty string")
        _ensure_timezone_aware(self.generated_at, "generated_at")
        object.__setattr__(self, "sections", tuple(self.sections))
        object.__setattr__(self, "artifacts", tuple(self.artifacts))
        object.__setattr__(self, "reason_codes", _ensure_tuple_of_str(self.reason_codes, "reason_codes"))
        object.__setattr__(self, "metadata", _coerce_metadata(self.metadata))
        object.__setattr__(self, "notes", _ensure_tuple_of_str(self.notes, "notes"))
        for code in self.reason_codes:
            if code not in FINAL_AUDIT_PACK_REASON_CODES:
                raise ValueError(f"unsupported reason code: {code}")

    @classmethod
    def blocked(
        cls,
        *,
        input: FinalAuditPackInput,
        config: FinalAuditPackConfig | None = None,
        reason_code: str = UNSAFE_CONTENT,
        report_id: str = "blocked",
        generated_at: datetime | None = None,
        notes: tuple[str, ...] = (),
    ) -> "FinalAuditPackReport":
        """Create a deterministic fail-closed blocked report."""
        if config is None:
            config = FinalAuditPackConfig()
        if generated_at is None:
            generated_at = datetime.now(timezone.utc)
        if reason_code not in FINAL_AUDIT_PACK_REASON_CODES:
            raise ValueError(f"unsupported reason code: {reason_code}")
        safety_flags = FinalAuditPackSafetyFlags()
        if reason_code == UNSAFE_CONTENT:
            safety_flags = FinalAuditPackSafetyFlags(has_unsafe_content=True)
        elif reason_code == MISSING_REQUIRED_SECTIONS:
            safety_flags = FinalAuditPackSafetyFlags(has_missing_required_sections=True)
        elif reason_code == INVALID_SECTION:
            safety_flags = FinalAuditPackSafetyFlags(has_invalid_section=True)
        return cls(
            report_id=report_id,
            version=FINAL_AUDIT_PACK_VERSION,
            generated_at=generated_at,
            sections=(),
            artifacts=(),
            completeness=FinalAuditPackCompleteness(
                total_sections=0,
                sections_expected=(
                    len(config.required_section_kinds) + len(config.optional_section_kinds)
                ),
                sections_present=0,
            ),
            data_quality=FinalAuditPackDataQuality(
                total_inputs=0,
                normalized_sections=0,
                sections_expected=(
                    len(config.required_section_kinds) + len(config.optional_section_kinds)
                ),
            ),
            safety_flags=safety_flags,
            reason_codes=(reason_code,),
            metadata=input.metadata,
            notes=notes,
        )
