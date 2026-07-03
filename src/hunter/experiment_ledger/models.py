"""Frozen dataclasses for hunter.experiment_ledger package.

MVP-31 — Local Research Experiment Ledger.

All dataclasses are frozen. Validation runs in __post_init__. The ledger only
accepts caller-provided in-memory inputs and never opens, follows, traverses,
validates, fetches, or executes file references or metadata strings. All
metadata and file-reference strings are opaque local strings only.

The experiment ledger is a human-audit / research artifact only. It is not a
trading signal, not trade approval, not strategy approval, not execution
approval, not portfolio approval, not universe approval, and not Freqtrade
input. It does not emit action commands, suggest orders, or create execution
instructions.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any

EXPERIMENT_LEDGER_VERSION: str = "0.31.0-dev"


class ExperimentState(Enum):
    """Normalized state of an experiment record."""

    INCLUDED = "included"
    EXCLUDED = "excluded"
    BLOCKED = "blocked"
    INSUFFICIENT_DATA = "insufficient_data"


class ExperimentReasonCode(Enum):
    """Reason codes for experiment ledger records and reports."""

    OK = "OK"
    BASELINE_MISSING = "BASELINE_MISSING"
    DUPLICATE_ID = "DUPLICATE_ID"
    UNSAFE_CONTENT = "UNSAFE_CONTENT"
    INVALID_METRICS = "INVALID_METRICS"
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
OK = ExperimentReasonCode.OK.value
BASELINE_MISSING = ExperimentReasonCode.BASELINE_MISSING.value
DUPLICATE_ID = ExperimentReasonCode.DUPLICATE_ID.value
UNSAFE_CONTENT = ExperimentReasonCode.UNSAFE_CONTENT.value
INVALID_METRICS = ExperimentReasonCode.INVALID_METRICS.value
MISSING_REQUIRED_FIELDS = ExperimentReasonCode.MISSING_REQUIRED_FIELDS.value
RESEARCH_ONLY = ExperimentReasonCode.RESEARCH_ONLY.value
NOT_TRADING_ADVICE = ExperimentReasonCode.NOT_TRADING_ADVICE.value
NO_FILE_INGESTION = ExperimentReasonCode.NO_FILE_INGESTION.value
NO_NETWORK_CONNECTION = ExperimentReasonCode.NO_NETWORK_CONNECTION.value
NO_EXCHANGE_CONNECTION = ExperimentReasonCode.NO_EXCHANGE_CONNECTION.value
NO_FREQTRADE_INPUT = ExperimentReasonCode.NO_FREQTRADE_INPUT.value
NO_SCHEDULER = ExperimentReasonCode.NO_SCHEDULER.value
NO_DAEMON = ExperimentReasonCode.NO_DAEMON.value
NO_WEB_UI = ExperimentReasonCode.NO_WEB_UI.value
NO_DATABASE = ExperimentReasonCode.NO_DATABASE.value
NO_ACTION_COMMANDS_EMITTED = ExperimentReasonCode.NO_ACTION_COMMANDS_EMITTED.value
HUMAN_RESEARCH_ONLY = ExperimentReasonCode.HUMAN_RESEARCH_ONLY.value


EXPERIMENT_LEDGER_REASON_CODES: tuple[str, ...] = tuple(
    code.value for code in ExperimentReasonCode
)

EXPERIMENT_LEDGER_BLOCKING_REASON_CODES: frozenset[str] = frozenset({
    UNSAFE_CONTENT,
    INVALID_METRICS,
    MISSING_REQUIRED_FIELDS,
    DUPLICATE_ID,
})

EXPERIMENT_LEDGER_ADVISORY_REASON_CODES: frozenset[str] = frozenset({
    OK,
    BASELINE_MISSING,
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


# Source kinds used for ExperimentRecord.source_kind.
BACKTEST_SOURCE_KIND = "backtest"
RUN_SOURCE_KIND = "run"
METRIC_SNAPSHOT_SOURCE_KIND = "metric_snapshot"


# Comparable metrics extracted from backtest reports and plain metric snapshots.
COMPARABLE_METRICS: tuple[str, ...] = (
    "total_return_pct",
    "max_drawdown_pct",
    "volatility_pct",
    "win_rate_pct",
    "observation_count",
    "missing_data_count",
    "blocked_count",
    "insufficient_data_count",
)


# Metrics extracted from research run results.
RUN_RESULT_METRICS: tuple[str, ...] = (
    "total_steps",
    "successful_steps",
    "failed_steps",
    "blocked_steps",
    "skipped_steps",
)


# Superset of forbidden terms for experiment ledger content. Keep all prior
# safety terms (exchange, trading, execution, network, Freqtrade) plus action
# and approval keywords.
FORBIDDEN_EXPERIMENT_LEDGER_TERMS: frozenset[str] = frozenset({
    # Exchange / network / live data
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
    # Trading / execution
    "buy",
    "buy_now",
    "sell",
    "sell_now",
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
    # Freqtrade
    "freqtrade",
    # Action / approval keywords
    "action_command",
    "action",
    "deploy",
    "execute",
    "start",
    "stop",
    "trigger",
    "approve",
    "approval",
    "go_live",
    "production_ready",
    "execution_ready",
    "strategy_ready",
    "deployment_ready",
    "release_ready",
    "launch_live",
})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ensure_timezone_aware(value: datetime | None, field_name: str) -> datetime | None:
    """Raise ValueError if value is a naive datetime (tzinfo is None)."""
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


def _coerce_metadata(value: Mapping[str, Any] | dict[str, Any] | None) -> Mapping[str, Any]:
    """Coerce a mapping into an immutable MappingProxyType."""
    if value is None:
        return MappingProxyType({})
    if isinstance(value, Mapping):
        return MappingProxyType(dict(value))
    raise ValueError("metadata must be a mapping")


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
    for term in forbidden_terms:
        if term in lower:
            return True
    return False


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


# ---------------------------------------------------------------------------
# Safety flags
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExperimentLedgerSafetyFlags:
    """Safety invariants for the experiment ledger."""

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
    has_unsafe_content: bool = False
    has_invalid_record: bool = False
    has_blocked_record: bool = False
    has_insufficient_data: bool = False
    has_missing_baseline: bool = False

    def __post_init__(self) -> None:
        unsafe_flags = (
            self.no_trading_signal,
            self.no_trade_approval,
            self.no_strategy_approval,
            self.no_execution_approval,
            self.no_portfolio_approval,
            self.no_universe_approval,
            self.no_order_sizing,
            self.no_position_sizing,
            self.no_leverage,
            self.no_shorting,
            self.no_action_commands,
            self.no_network_connection,
            self.no_file_read_in_engine,
            self.no_database,
            self.no_exchange_connection,
            self.no_freqtrade_input,
            self.no_scheduler,
            self.no_web_ui,
            self.no_daemon,
            self.no_rest_api,
            self.research_only,
            self.not_trading_advice,
        )
        if not all(unsafe_flags):
            raise ValueError("baseline safety invariants must be True")
        negative_flags = (
            self.has_unsafe_content,
            self.has_invalid_record,
            self.has_blocked_record,
            self.has_insufficient_data,
            self.has_missing_baseline,
        )
        if any(negative_flags):
            # Negative flags are allowed as data, but is_safe reflects them.
            pass

    @property
    def is_safe(self) -> bool:
        """Return True when all positive invariants hold and all negative flags are False."""
        return (
            self.no_trading_signal
            and self.no_trade_approval
            and self.no_strategy_approval
            and self.no_execution_approval
            and self.no_portfolio_approval
            and self.no_universe_approval
            and self.no_order_sizing
            and self.no_position_sizing
            and self.no_leverage
            and self.no_shorting
            and self.no_action_commands
            and self.no_network_connection
            and self.no_file_read_in_engine
            and self.no_database
            and self.no_exchange_connection
            and self.no_freqtrade_input
            and self.no_scheduler
            and self.no_web_ui
            and self.no_daemon
            and self.no_rest_api
            and self.research_only
            and self.not_trading_advice
            and not self.has_unsafe_content
            and not self.has_invalid_record
            and not self.has_blocked_record
            and not self.has_insufficient_data
            and not self.has_missing_baseline
        )


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExperimentMetricSnapshot:
    """Plain metric record provided by the caller."""

    experiment_id: str
    run_id: str
    name: str
    metrics: Mapping[str, float | int | None]
    tags: tuple[str, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)
    generated_at: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.experiment_id, str) or not self.experiment_id:
            raise ValueError("experiment_id must be a non-empty string")
        if not isinstance(self.run_id, str):
            raise ValueError("run_id must be a string")
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("name must be a non-empty string")
        _ensure_tuple_of_str(self.tags, "tags")
        object.__setattr__(self, "tags", _ensure_tuple_of_str(self.tags, "tags"))
        object.__setattr__(self, "metadata", _coerce_str_mapping(self.metadata))
        _ensure_timezone_aware(self.generated_at, "generated_at")
        if not isinstance(self.metrics, Mapping):
            raise ValueError("metrics must be a mapping")


@dataclass(frozen=True)
class ExperimentLedgerInput:
    """Caller-provided in-memory inputs for the experiment ledger."""

    backtest_reports: tuple[Any, ...] = ()
    run_results: tuple[Any, ...] = ()
    metric_snapshots: tuple[ExperimentMetricSnapshot, ...] = ()
    generated_at: datetime | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "backtest_reports", tuple(self.backtest_reports))
        object.__setattr__(self, "run_results", tuple(self.run_results))
        object.__setattr__(self, "metric_snapshots", tuple(self.metric_snapshots))
        _ensure_timezone_aware(self.generated_at, "generated_at")
        object.__setattr__(self, "metadata", _coerce_str_mapping(self.metadata))


@dataclass(frozen=True)
class ExperimentRecord:
    """Normalized experiment record comparable across source kinds."""

    experiment_id: str
    source_kind: str
    run_id: str
    name: str
    state: ExperimentState
    reason_codes: tuple[str, ...]
    metrics: Mapping[str, float | int | None]
    generated_at: datetime
    tags: tuple[str, ...]
    metadata: Mapping[str, str]
    notes: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.experiment_id, str) or not self.experiment_id:
            raise ValueError("experiment_id must be a non-empty string")
        if not isinstance(self.source_kind, str) or not self.source_kind:
            raise ValueError("source_kind must be a non-empty string")
        if not isinstance(self.run_id, str) or not self.run_id:
            raise ValueError("run_id must be a non-empty string")
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("name must be a non-empty string")
        if not isinstance(self.state, ExperimentState):
            raise ValueError("state must be an ExperimentState")
        _ensure_timezone_aware(self.generated_at, "generated_at")
        object.__setattr__(self, "reason_codes", _ensure_tuple_of_str(self.reason_codes, "reason_codes"))
        object.__setattr__(self, "tags", _ensure_tuple_of_str(self.tags, "tags"))
        object.__setattr__(self, "metadata", _coerce_str_mapping(self.metadata))
        object.__setattr__(self, "notes", _ensure_tuple_of_str(self.notes, "notes"))
        if not isinstance(self.metrics, Mapping):
            raise ValueError("metrics must be a mapping")
        for code in self.reason_codes:
            if code not in EXPERIMENT_LEDGER_REASON_CODES:
                raise ValueError(f"unsupported reason code: {code}")
        if self.state is ExperimentState.BLOCKED and not self.reason_codes:
            raise ValueError("BLOCKED records must have reason_codes")

    @classmethod
    def blocked(
        cls,
        *,
        experiment_id: str = "blocked",
        run_id: str = "blocked",
        name: str = "blocked",
        source_kind: str = "blocked",
        reason_codes: tuple[str, ...] = (MISSING_REQUIRED_FIELDS,),
        generated_at: datetime | None = None,
        metrics: Mapping[str, float | int | None] | None = None,
        tags: tuple[str, ...] = (),
        metadata: Mapping[str, str] | None = None,
        notes: tuple[str, ...] = (),
    ) -> "ExperimentRecord":
        """Create a fail-closed blocked record for audit purposes."""
        if generated_at is None:
            generated_at = datetime.now(timezone.utc)
        return cls(
            experiment_id=experiment_id,
            source_kind=source_kind,
            run_id=run_id,
            name=name,
            state=ExperimentState.BLOCKED,
            reason_codes=reason_codes,
            metrics=metrics if metrics is not None else MappingProxyType({}),
            generated_at=generated_at,
            tags=tags,
            metadata=metadata if metadata is not None else {},
            notes=notes,
        )


@dataclass(frozen=True)
class ExperimentComparisonConfig:
    """Configuration for experiment comparison."""

    baseline_experiment_id: str | None = None
    include_blocked: bool = True
    include_insufficient: bool = True
    primary_metric: str = "total_return_pct"
    generated_at: datetime | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.baseline_experiment_id is not None and (
            not isinstance(self.baseline_experiment_id, str) or not self.baseline_experiment_id
        ):
            raise ValueError("baseline_experiment_id must be a non-empty string or None")
        if not isinstance(self.primary_metric, str) or not self.primary_metric:
            raise ValueError("primary_metric must be a non-empty string")
        _ensure_timezone_aware(self.generated_at, "generated_at")
        object.__setattr__(self, "metadata", _coerce_str_mapping(self.metadata))
        for attr in ("include_blocked", "include_insufficient"):
            if not isinstance(getattr(self, attr), bool):
                raise ValueError(f"{attr} must be a bool")


@dataclass(frozen=True)
class ExperimentComparisonResult:
    """Result of comparing experiment records."""

    config: ExperimentComparisonConfig
    records: tuple[ExperimentRecord, ...]
    ranked_records: tuple[ExperimentRecord, ...]
    baseline_record: ExperimentRecord | None
    deltas: Mapping[str, Mapping[str, float | int | None]]
    summary_metrics: Mapping[str, float | int | None]
    reason_codes: tuple[str, ...]
    notes: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.config, ExperimentComparisonConfig):
            raise ValueError("config must be an ExperimentComparisonConfig")
        if not isinstance(self.records, tuple):
            raise ValueError("records must be a tuple")
        if not isinstance(self.ranked_records, tuple):
            raise ValueError("ranked_records must be a tuple")
        if self.baseline_record is not None and not isinstance(self.baseline_record, ExperimentRecord):
            raise ValueError("baseline_record must be an ExperimentRecord or None")
        if not isinstance(self.deltas, Mapping):
            raise ValueError("deltas must be a mapping")
        if not isinstance(self.summary_metrics, Mapping):
            raise ValueError("summary_metrics must be a mapping")
        object.__setattr__(self, "reason_codes", _ensure_tuple_of_str(self.reason_codes, "reason_codes"))
        object.__setattr__(self, "notes", _ensure_tuple_of_str(self.notes, "notes"))
        for code in self.reason_codes:
            if code not in EXPERIMENT_LEDGER_REASON_CODES:
                raise ValueError(f"unsupported reason code: {code}")


@dataclass(frozen=True)
class ExperimentLedgerDataQuality:
    """Summary data quality for the experiment ledger."""

    total_inputs: int
    normalized_records: int
    blocked_records: int
    insufficient_records: int
    excluded_records: int
    included_records: int
    sections_present: tuple[str, ...]
    sections_expected: tuple[str, ...]
    notes: tuple[str, ...]

    def __post_init__(self) -> None:
        for attr in (
            "total_inputs",
            "normalized_records",
            "blocked_records",
            "insufficient_records",
            "excluded_records",
            "included_records",
        ):
            value = getattr(self, attr)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{attr} must be a non-negative integer")
        if self.normalized_records > self.total_inputs:
            raise ValueError("normalized_records must not exceed total_inputs")
        if self.blocked_records + self.insufficient_records + self.excluded_records + self.included_records > self.normalized_records:
            raise ValueError("state counts must not exceed normalized_records")
        object.__setattr__(self, "sections_present", _ensure_tuple_of_str(self.sections_present, "sections_present"))
        object.__setattr__(self, "sections_expected", _ensure_tuple_of_str(self.sections_expected, "sections_expected"))
        object.__setattr__(self, "notes", _ensure_tuple_of_str(self.notes, "notes"))


@dataclass(frozen=True)
class ExperimentLedgerReport:
    """Top-level experiment ledger report."""

    report_id: str
    version: str
    generated_at: datetime
    input: ExperimentLedgerInput
    comparison: ExperimentComparisonResult
    data_quality: ExperimentLedgerDataQuality
    safety_flags: ExperimentLedgerSafetyFlags
    reason_codes: tuple[str, ...]
    metadata: Mapping[str, str]
    notes: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.report_id, str) or not self.report_id:
            raise ValueError("report_id must be a non-empty string")
        if not isinstance(self.version, str) or not self.version:
            raise ValueError("version must be a non-empty string")
        _ensure_timezone_aware(self.generated_at, "generated_at")
        if not isinstance(self.input, ExperimentLedgerInput):
            raise ValueError("input must be an ExperimentLedgerInput")
        if not isinstance(self.comparison, ExperimentComparisonResult):
            raise ValueError("comparison must be an ExperimentComparisonResult")
        if not isinstance(self.data_quality, ExperimentLedgerDataQuality):
            raise ValueError("data_quality must be an ExperimentLedgerDataQuality")
        if not isinstance(self.safety_flags, ExperimentLedgerSafetyFlags):
            raise ValueError("safety_flags must be an ExperimentLedgerSafetyFlags")
        object.__setattr__(self, "reason_codes", _ensure_tuple_of_str(self.reason_codes, "reason_codes"))
        object.__setattr__(self, "metadata", _coerce_str_mapping(self.metadata))
        object.__setattr__(self, "notes", _ensure_tuple_of_str(self.notes, "notes"))
        for code in self.reason_codes:
            if code not in EXPERIMENT_LEDGER_REASON_CODES:
                raise ValueError(f"unsupported reason code: {code}")

    @classmethod
    def blocked(
        cls,
        *,
        input: ExperimentLedgerInput,
        reason_code: str = UNSAFE_CONTENT,
        report_id: str = "blocked",
        generated_at: datetime | None = None,
        safety_flags: ExperimentLedgerSafetyFlags | None = None,
        metadata: Mapping[str, str] | None = None,
        notes: tuple[str, ...] = (),
    ) -> "ExperimentLedgerReport":
        """Create a deterministic fail-closed blocked ledger report."""
        if reason_code not in EXPERIMENT_LEDGER_REASON_CODES:
            raise ValueError(f"unsupported reason code: {reason_code}")
        if generated_at is None:
            generated_at = datetime.now(timezone.utc)
        if safety_flags is None:
            safety_flags = ExperimentLedgerSafetyFlags()
        if reason_code == UNSAFE_CONTENT:
            safety_flags = ExperimentLedgerSafetyFlags(has_unsafe_content=True)
        config = ExperimentComparisonConfig()
        comparison = ExperimentComparisonResult(
            config=config,
            records=(),
            ranked_records=(),
            baseline_record=None,
            deltas=MappingProxyType({}),
            summary_metrics=MappingProxyType({}),
            reason_codes=(reason_code,),
            notes=notes,
        )
        data_quality = ExperimentLedgerDataQuality(
            total_inputs=0,
            normalized_records=0,
            blocked_records=0,
            insufficient_records=0,
            excluded_records=0,
            included_records=0,
            sections_present=(),
            sections_expected=(),
            notes=notes,
        )
        return cls(
            report_id=report_id,
            version=EXPERIMENT_LEDGER_VERSION,
            generated_at=generated_at,
            input=input,
            comparison=comparison,
            data_quality=data_quality,
            safety_flags=safety_flags,
            reason_codes=(reason_code,),
            metadata=metadata if metadata is not None else {},
            notes=notes,
        )
