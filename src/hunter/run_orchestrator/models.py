"""Frozen models and enums for hunter.run_orchestrator.

MVP-30 — Local Research Run Orchestrator.

All models are frozen. Validation runs in __post_init__. The orchestrator is a
caller-triggered local coordinator over existing research engines. It never
opens files, follows paths, calls networks, accesses exchanges, starts servers,
schedulers, daemons, or databases, and never emits trading or execution
commands.

All metadata and file-reference strings are opaque local strings. They are
never read, parsed, traversed, validated, fetched, or executed by this package.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from hunter.controlled_universe.models import (
        ControlledUniverseConfig,
        ControlledUniverseReport,
    )
    from hunter.execution.models import ExecutionContext
    from hunter.portfolio_construction.models import PortfolioConstructionReport

RUN_ORCHESTRATOR_VERSION: str = "0.30.0-dev"


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ResearchRunStepKind(Enum):
    """Supported deterministic step kinds for a research run.

    Each value maps to an existing local engine public API. No step kind maps
    to an exchange, network, database, server, scheduler, daemon, or trading
    runtime.
    """

    REPORTING_CLI_SAMPLE = "reporting_cli_sample"
    BACKTEST = "backtest"
    PORTFOLIO_CONSTRUCTION = "portfolio_construction"
    DISCOVERY = "discovery"
    AUDIT_SNAPSHOT_SUMMARY = "audit_snapshot_summary"
    AUDIT_CATALOG_SUMMARY = "audit_catalog_summary"
    AUDIT_CLOSURE_SUMMARY = "audit_closure_summary"
    CONTROLLED_UNIVERSE = "controlled_universe"


class ResearchRunStepState(Enum):
    """Terminal state of a single research run step."""

    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    SKIPPED = "SKIPPED"


class ResearchRunState(Enum):
    """Terminal state of an entire research run."""

    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    PARTIAL = "PARTIAL"


# ---------------------------------------------------------------------------
# Reason codes
# ---------------------------------------------------------------------------

OK = "OK"
RUN_BLOCKED = "RUN_BLOCKED"
STEP_FAILED = "STEP_FAILED"
STEP_BLOCKED = "STEP_BLOCKED"
STEP_SKIPPED = "STEP_SKIPPED"
UNKNOWN_STEP_KIND = "UNKNOWN_STEP_KIND"
UNSUPPORTED_STEP_KIND = "UNSUPPORTED_STEP_KIND"
UNSAFE_RUN_CONTENT = "UNSAFE_RUN_CONTENT"
INVALID_RUN_PLAN = "INVALID_RUN_PLAN"
INVALID_RUN_CONFIG = "INVALID_RUN_CONFIG"
INVALID_OUTPUT_DIR = "INVALID_OUTPUT_DIR"
PATH_TRAVERSAL_DETECTED = "PATH_TRAVERSAL_DETECTED"
NETWORK_REFERENCE_DETECTED = "NETWORK_REFERENCE_DETECTED"
EMPTY_RUN_PLAN = "EMPTY_RUN_PLAN"
EMPTY_RUN_ID = "EMPTY_RUN_ID"
INVALID_STEP_INPUTS = "INVALID_STEP_INPUTS"
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
MISSING_PORTFOLIO_CONTEXT = "MISSING_PORTFOLIO_CONTEXT"
MISSING_EXECUTION_CONTEXT = "MISSING_EXECUTION_CONTEXT"
STALE_INPUT = "STALE_INPUT"
UPSTREAM_STEP_FAILED = "UPSTREAM_STEP_FAILED"
UPSTREAM_STEP_BLOCKED = "UPSTREAM_STEP_BLOCKED"
INVALID_PORTFOLIO_SUMMARY = "INVALID_PORTFOLIO_SUMMARY"
EXECUTION_BLOCKED = "EXECUTION_BLOCKED"
MACRO_MODE_NONE = "MACRO_MODE_NONE"
CONTRADICTORY_INPUT = "CONTRADICTORY_INPUT"
INVALID_CONTROLLED_UNIVERSE_INPUT = "INVALID_CONTROLLED_UNIVERSE_INPUT"

RUN_ORCHESTRATOR_BLOCKING_REASON_CODES: frozenset[str] = frozenset({
    RUN_BLOCKED,
    UNSAFE_RUN_CONTENT,
    INVALID_RUN_PLAN,
    INVALID_RUN_CONFIG,
    INVALID_OUTPUT_DIR,
    PATH_TRAVERSAL_DETECTED,
    NETWORK_REFERENCE_DETECTED,
    EMPTY_RUN_PLAN,
    EMPTY_RUN_ID,
    UNKNOWN_STEP_KIND,
    UNSUPPORTED_STEP_KIND,
    INVALID_STEP_INPUTS,
    MISSING_PORTFOLIO_CONTEXT,
    MISSING_EXECUTION_CONTEXT,
    STALE_INPUT,
    UPSTREAM_STEP_FAILED,
    UPSTREAM_STEP_BLOCKED,
    INVALID_PORTFOLIO_SUMMARY,
    EXECUTION_BLOCKED,
    MACRO_MODE_NONE,
    CONTRADICTORY_INPUT,
    INVALID_CONTROLLED_UNIVERSE_INPUT,
})

RUN_ORCHESTRATOR_STEP_REASON_CODES: frozenset[str] = frozenset({
    OK,
    STEP_FAILED,
    STEP_BLOCKED,
    STEP_SKIPPED,
    UNKNOWN_STEP_KIND,
    UNSUPPORTED_STEP_KIND,
    INVALID_STEP_INPUTS,
    MISSING_PORTFOLIO_CONTEXT,
    MISSING_EXECUTION_CONTEXT,
    STALE_INPUT,
    UPSTREAM_STEP_FAILED,
    UPSTREAM_STEP_BLOCKED,
    INVALID_PORTFOLIO_SUMMARY,
    EXECUTION_BLOCKED,
    MACRO_MODE_NONE,
    CONTRADICTORY_INPUT,
    INVALID_CONTROLLED_UNIVERSE_INPUT,
})

RUN_ORCHESTRATOR_ADVISORY_REASON_CODES: frozenset[str] = frozenset({
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

RUN_ORCHESTRATOR_REASON_CODES: frozenset[str] = (
    RUN_ORCHESTRATOR_BLOCKING_REASON_CODES
    | RUN_ORCHESTRATOR_STEP_REASON_CODES
    | RUN_ORCHESTRATOR_ADVISORY_REASON_CODES
)


# ---------------------------------------------------------------------------
# Forbidden terms — local-string content guard.
# ---------------------------------------------------------------------------


FORBIDDEN_RUN_ORCHESTRATOR_TERMS: frozenset[str] = frozenset({
    # Trading / execution
    "buy",
    "sell",
    "order",
    "orders",
    "trade",
    "trading",
    "position",
    "positions",
    "execute",
    "execution",
    "signal",
    "signals",
    "entry",
    "exit",
    "entry_price",
    "exit_price",
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
    "position_size",
    "position sizing",
    "order_size",
    "order sizing",
    "trade_size",
    "trade sizing",
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
    "live_trading",
    "live trading",
    "market_data_feed",
    "tick_data",
    # Runtime infrastructure / background jobs
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
# Internal helpers
# ---------------------------------------------------------------------------


def _coerce_tuple_strs(values: Sequence[str] | None) -> tuple[str, ...]:
    """Return a deduplicated tuple of strings."""
    if values is None:
        return ()
    seen: set[str] = set()
    result: list[str] = []
    for item in values:
        s = str(item)
        if s not in seen:
            seen.add(s)
            result.append(s)
    return tuple(result)


def _coerce_mapping_strs(
    mapping: Mapping[str, str] | None,
) -> Mapping[str, str]:
    """Return an immutable copy of a string mapping."""
    if mapping is None:
        return MappingProxyType({})
    return MappingProxyType({str(k): str(v) for k, v in mapping.items()})


def _coerce_mapping_any(mapping: Mapping[str, Any] | None) -> Mapping[str, Any]:
    """Return an immutable copy of a mapping with arbitrary values."""
    if mapping is None:
        return MappingProxyType({})
    return MappingProxyType(dict(mapping))


def _utc_now() -> datetime:
    """Return a timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Safety flags
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResearchRunSafetyFlags:
    """Safety invariants for the run orchestrator."""

    no_trading_signal: bool = True
    no_trade_approval: bool = True
    no_strategy_approval: bool = True
    no_execution_approval: bool = True
    no_portfolio_approval: bool = True
    no_universe_approval: bool = True
    no_order_sizing: bool = True
    no_position_sizing: bool = True
    no_leverage: bool = True
    no_shorting: bool = True
    no_action_commands: bool = True
    no_network_connection: bool = True
    no_file_read_in_engine: bool = True
    no_database: bool = True
    no_exchange_connection: bool = True
    no_freqtrade_input: bool = True
    no_scheduler: bool = True
    no_web_ui: bool = True
    no_daemon: bool = True
    no_rest_api: bool = True
    research_only: bool = True
    not_trading_advice: bool = True
    has_failed_step: bool = False
    has_blocked_step: bool = False
    has_invalid_step: bool = False
    has_unsafe_content: bool = False
    has_traversal_attempt: bool = False
    has_network_reference: bool = False

    @property
    def is_safe(self) -> bool:
        """True iff all positive invariants hold and no negative flags are set."""
        fields = self.__dataclass_fields__
        no_flags = [getattr(self, name) for name in fields if name.startswith("no_")]
        not_flags = [getattr(self, name) for name in fields if name.startswith("not_")]
        research_flags = [getattr(self, "research_only", True)]
        has_flags = [getattr(self, name) for name in fields if name.startswith("has_")]
        return (
            all(no_flags)
            and all(not_flags)
            and all(research_flags)
            and not any(has_flags)
        )


# ---------------------------------------------------------------------------
# Data quality
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResearchRunDataQuality:
    """Summary of data quality across the run steps."""

    total_steps: int = 0
    successful_steps: int = 0
    failed_steps: int = 0
    blocked_steps: int = 0
    skipped_steps: int = 0
    controlled_universe_steps: int = 0
    controlled_universe_blocked: int = 0
    controlled_universe_failed: int = 0
    sections_present: tuple[str, ...] = ()
    sections_expected: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Configuration and plan models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResearchRunConfig:
    """Configuration for a research run.

    The output_dir is a local path string. It is treated as an opaque string
    until it is passed to an existing writer module; the orchestrator itself
    validates it only as a string for traversal and network-reference safety.
    """

    output_dir: str = "data/run_orchestrator/latest_run"
    fail_fast: bool = True
    write_artifacts: bool = True
    generated_at: datetime | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)
    project_version: str = RUN_ORCHESTRATOR_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.output_dir, str) or not self.output_dir.strip():
            raise ValueError("output_dir must be a non-empty string")
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))


@dataclass(frozen=True)
class ResearchRunStep:
    """A single deterministic step in a research run plan.

    The inputs mapping is provided by the caller in-memory. The orchestrator does
    not read files, follow paths, or execute references. Each step kind defines
    its own expected input keys, which are documented in the dispatch layer.
    """

    kind: ResearchRunStepKind
    step_id: str = ""
    inputs: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.kind, ResearchRunStepKind):
            raise ValueError("kind must be a ResearchRunStepKind")
        if not isinstance(self.step_id, str):
            raise ValueError("step_id must be a string")
        object.__setattr__(self, "inputs", _coerce_mapping_any(self.inputs))
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))


@dataclass(frozen=True)
class ResearchRunPlan:
    """A deterministic, ordered plan of research run steps."""

    run_id: str
    steps: tuple[ResearchRunStep, ...]
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, str) or not self.run_id.strip():
            raise ValueError("run_id must be a non-empty string")
        if not isinstance(self.steps, tuple):
            object.__setattr__(self, "steps", tuple(self.steps))
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))


@dataclass(frozen=True)
class ControlledUniverseRunInput:
    """Helper bundle for carrying controlled-universe inputs into a run plan.

    This dataclass is used by the plan builder and by callers who prefer a typed
    object over raw `step.inputs` keys. The orchestrator extracts these values and
    places them into the step's `inputs` mapping before dispatch.
    """

    execution_context: "ExecutionContext" | None = None
    portfolio_report: "PortfolioConstructionReport" | None = None
    config: "ControlledUniverseConfig" | None = None
    portfolio_construction_step_id: str | None = None
    portfolio_construction_step_index: int | None = None
    execution_context_step_id: str | None = None

    def __post_init__(self) -> None:
        if self.portfolio_construction_step_index is not None and (
            not isinstance(self.portfolio_construction_step_index, int)
            or self.portfolio_construction_step_index < 0
        ):
            raise ValueError(
                "portfolio_construction_step_index must be a non-negative integer"
            )
        for field_name in (
            "portfolio_construction_step_id",
            "execution_context_step_id",
        ):
            value = getattr(self, field_name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"{field_name} must be a non-empty string when provided")


@dataclass(frozen=True)
class RunInputResolution:
    """Resolved upstream inputs for a CONTROLLED_UNIVERSE step.

    The engine populates this from in-line objects, referenced upstream steps, or
    both, and passes it to the controlled-universe bridge. In-line objects always
    take precedence over step references.
    """

    portfolio_report: "PortfolioConstructionReport" | None = None
    execution_context: "ExecutionContext" | None = None


# ---------------------------------------------------------------------------
# Result models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResearchRunArtifact:
    """Reference to a local output artifact produced by a run step.

    The path is an opaque local string. The orchestrator never opens, follows,
    traverses, or validates it beyond the writer-module call that created it.
    """

    step_index: int
    step_id: str
    kind: str
    path: str
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.step_index, int):
            raise ValueError("step_index must be an int")
        if not isinstance(self.step_id, str):
            raise ValueError("step_id must be a string")
        if not isinstance(self.kind, str) or not self.kind.strip():
            raise ValueError("kind must be a non-empty string")
        if not isinstance(self.path, str) or not self.path.strip():
            raise ValueError("path must be a non-empty string")
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))


@dataclass(frozen=True)
class ResearchRunStepResult:
    """Structured result of a single research run step."""

    step_index: int
    step_id: str
    kind: ResearchRunStepKind
    state: ResearchRunStepState
    reason_codes: tuple[str, ...]
    data: Mapping[str, Any]
    output_paths: tuple[str, ...]
    notes: tuple[str, ...]
    error_message: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.step_index, int):
            raise ValueError("step_index must be an int")
        if not isinstance(self.step_id, str):
            raise ValueError("step_id must be a string")
        if not isinstance(self.kind, ResearchRunStepKind):
            raise ValueError("kind must be a ResearchRunStepKind")
        if not isinstance(self.state, ResearchRunStepState):
            raise ValueError("state must be a ResearchRunStepState")
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))
        object.__setattr__(self, "data", _coerce_mapping_any(self.data))
        object.__setattr__(self, "output_paths", _coerce_tuple_strs(self.output_paths))
        object.__setattr__(self, "notes", _coerce_tuple_strs(self.notes))
        if not isinstance(self.error_message, str):
            raise ValueError("error_message must be a string")


@dataclass(frozen=True)
class ResearchRunResult:
    """Deterministic result of a research run.

    Contains the step results, artifact references, data quality, safety flags,
    and reason codes. All outputs are local research artifacts only.
    """

    run_id: str
    config: ResearchRunConfig
    plan: ResearchRunPlan
    steps: tuple[ResearchRunStepResult, ...]
    artifacts: tuple[ResearchRunArtifact, ...]
    data_quality: ResearchRunDataQuality
    safety_flags: ResearchRunSafetyFlags
    reason_codes: tuple[str, ...]
    generated_at: datetime
    state: ResearchRunState
    metadata: Mapping[str, str]
    notes: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, str) or not self.run_id.strip():
            raise ValueError("run_id must be a non-empty string")
        if not isinstance(self.steps, tuple):
            object.__setattr__(self, "steps", tuple(self.steps))
        if not isinstance(self.artifacts, tuple):
            object.__setattr__(self, "artifacts", tuple(self.artifacts))
        if not isinstance(self.reason_codes, tuple):
            object.__setattr__(self, "reason_codes", tuple(self.reason_codes))
        if not isinstance(self.notes, tuple):
            object.__setattr__(self, "notes", tuple(self.notes))
        if not isinstance(self.generated_at, datetime):
            raise ValueError("generated_at must be a datetime")
        if not isinstance(self.state, ResearchRunState):
            raise ValueError("state must be a ResearchRunState")
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))
