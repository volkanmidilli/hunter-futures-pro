"""Frozen models and contracts for the research backtest comparison harness (MVP-65 / SPEC-066)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any

RESEARCH_BACKTEST_COMPARISON_VERSION: str = "0.65.0-dev"
SPEC_VERSION: str = "SPEC-066"

UNAVAILABLE: str = "UNAVAILABLE"

# ---------------------------------------------------------------------------
# Reason codes
# ---------------------------------------------------------------------------

INVALID_STRATEGY_PATH = "INVALID_STRATEGY_PATH"
INVALID_DATA_PATH = "INVALID_DATA_PATH"
EMPTY_PAIRLIST = "EMPTY_PAIRLIST"
STRATEGY_MUTATION_DETECTED = "STRATEGY_MUTATION_DETECTED"
FORBIDDEN_SUBCOMMAND = "FORBIDDEN_SUBCOMMAND"
SHELL_INJECTION_DETECTED = "SHELL_INJECTION_DETECTED"
SECRET_IN_ENV = "SECRET_IN_ENV"
TIMEOUT = "TIMEOUT"
NONZERO_EXIT = "NONZERO_EXIT"
RESULT_CONTAINMENT_FAILURE = "RESULT_CONTAINMENT_FAILURE"
RESULT_NOT_FOUND = "RESULT_NOT_FOUND"
PARSER_VERSION_MISMATCH = "PARSER_VERSION_MISMATCH"
MISSING_METRIC = "MISSING_METRIC"
PARSER_ERROR = "PARSER_ERROR"
INVALID_EXECUTABLE = "INVALID_EXECUTABLE"
INVALID_TIMEFRAME = "INVALID_TIMEFRAME"
INVALID_TIMERANGE = "INVALID_TIMERANGE"
INVALID_BALANCE = "INVALID_BALANCE"
INVALID_STAKE = "INVALID_STAKE"
INVALID_MAX_OPEN_TRADES = "INVALID_MAX_OPEN_TRADES"
INVALID_FEE = "INVALID_FEE"
INVALID_PROTECTIONS = "INVALID_PROTECTIONS"
CONFIG_BUILD_ERROR = "CONFIG_BUILD_ERROR"
FAIRNESS_VIOLATION = "FAIRNESS_VIOLATION"
COMMAND_BUILD_ERROR = "COMMAND_BUILD_ERROR"
RUNNER_ERROR = "RUNNER_ERROR"
WRITER_ERROR = "WRITER_ERROR"
RESEARCH_ONLY_ARTIFACT = "RESEARCH_ONLY_ARTIFACT"
HUMAN_RESEARCH_ONLY = "HUMAN_RESEARCH_ONLY"
NO_LIVE_TRADING = "NO_LIVE_TRADING"
NO_AUTOMATIC_EXECUTION = "NO_AUTOMATIC_EXECUTION"
NO_REMOTE_CHANGES = "NO_REMOTE_CHANGES"
NO_NETWORK_CONNECTION = "NO_NETWORK_CONNECTION"
NO_DATABASE_CONNECTION = "NO_DATABASE_CONNECTION"
NO_EXCHANGE_CONNECTION = "NO_EXCHANGE_CONNECTION"
NO_AUTOMATIC_CONFIG_MUTATION = "NO_AUTOMATIC_CONFIG_MUTATION"
NO_ACTION_COMMANDS_EMITTED = "NO_ACTION_COMMANDS_EMITTED"
NO_OPEN_INTEREST_SYNTHESIS = "NO_OPEN_INTEREST_SYNTHESIS"
INSUFFICIENT_TRADES = "INSUFFICIENT_TRADES"

RESEARCH_BACKTEST_COMPARISON_REASON_CODES: frozenset[str] = frozenset(
    {
        INVALID_STRATEGY_PATH,
        INVALID_DATA_PATH,
        EMPTY_PAIRLIST,
        STRATEGY_MUTATION_DETECTED,
        FORBIDDEN_SUBCOMMAND,
        SHELL_INJECTION_DETECTED,
        SECRET_IN_ENV,
        TIMEOUT,
        NONZERO_EXIT,
        RESULT_CONTAINMENT_FAILURE,
        RESULT_NOT_FOUND,
        PARSER_VERSION_MISMATCH,
        MISSING_METRIC,
        PARSER_ERROR,
        INVALID_EXECUTABLE,
        INVALID_TIMEFRAME,
        INVALID_TIMERANGE,
        INVALID_BALANCE,
        INVALID_STAKE,
        INVALID_MAX_OPEN_TRADES,
        INVALID_FEE,
        INVALID_PROTECTIONS,
        CONFIG_BUILD_ERROR,
        FAIRNESS_VIOLATION,
        COMMAND_BUILD_ERROR,
        RUNNER_ERROR,
        WRITER_ERROR,
        RESEARCH_ONLY_ARTIFACT,
        HUMAN_RESEARCH_ONLY,
        NO_LIVE_TRADING,
        NO_AUTOMATIC_EXECUTION,
        NO_REMOTE_CHANGES,
        NO_NETWORK_CONNECTION,
        NO_DATABASE_CONNECTION,
        NO_EXCHANGE_CONNECTION,
        NO_AUTOMATIC_CONFIG_MUTATION,
        NO_ACTION_COMMANDS_EMITTED,
        NO_OPEN_INTEREST_SYNTHESIS,
        INSUFFICIENT_TRADES,
    }
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class MetricInterpretation(str, Enum):
    """Descriptive interpretation of a metric delta."""

    CANDIDATE_HIGHER = "CANDIDATE_HIGHER"
    BASELINE_HIGHER = "BASELINE_HIGHER"
    EQUAL = "EQUAL"
    UNAVAILABLE = "UNAVAILABLE"


class BacktestArmLabel(str, Enum):
    """Label for a backtest arm."""

    CANDIDATE = "CANDIDATE"
    BASELINE = "BASELINE"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _coerce_tuple_strs(values: tuple[str, ...] | list[str] | None) -> tuple[str, ...]:
    """Coerce a sequence to a deduplicated tuple of strings."""
    if values is None:
        return ()
    return tuple(dict.fromkeys(str(v) for v in values))


def _coerce_decimal(value: Decimal | str | int | float | None) -> Decimal | None:
    """Coerce a value to Decimal or None."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _coerce_mapping_strs(
    mapping: dict[str, str] | Any | None,
) -> Any:
    """Return an immutable string mapping."""
    if mapping is None:
        return MappingProxyType({})
    return MappingProxyType({str(k): str(v) for k, v in dict(mapping).items()})


# ---------------------------------------------------------------------------
# Safety flags
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResearchBacktestSafetyFlags:
    """Mandatory safety invariants for every backtest comparison artifact.

    NOTE: no_freqtrade_runtime_connection is intentionally NOT enforced as True
    because this MVP legitimately runs ``freqtrade backtesting`` as a subprocess.
    """

    research_only: bool = True
    execution_approval_granted: bool = False
    production_approval_granted: bool = False
    live_trading_allowed: bool = False
    automatic_execution_allowed: bool = False
    human_approval_required: bool = True
    no_action_commands_emitted: bool = True
    no_network_connection: bool = True
    no_database_connection: bool = True
    no_exchange_connection: bool = True
    no_automatic_config_mutation: bool = True
    no_open_interest_synthesis: bool = True
    no_remote_changes: bool = True
    no_freqtrade_runtime_connection: bool = False
    human_research_only: bool = True

    def __post_init__(self) -> None:
        for name, value in (
            ("research_only", self.research_only),
            ("execution_approval_granted", self.execution_approval_granted),
            ("production_approval_granted", self.production_approval_granted),
            ("live_trading_allowed", self.live_trading_allowed),
            ("automatic_execution_allowed", self.automatic_execution_allowed),
            ("human_approval_required", self.human_approval_required),
            ("no_action_commands_emitted", self.no_action_commands_emitted),
            ("no_network_connection", self.no_network_connection),
            ("no_database_connection", self.no_database_connection),
            ("no_exchange_connection", self.no_exchange_connection),
            ("no_automatic_config_mutation", self.no_automatic_config_mutation),
            ("no_open_interest_synthesis", self.no_open_interest_synthesis),
            ("no_remote_changes", self.no_remote_changes),
            ("no_freqtrade_runtime_connection", self.no_freqtrade_runtime_connection),
            ("human_research_only", self.human_research_only),
        ):
            if not isinstance(value, bool):
                raise ValueError(f"{name} must be a bool, got {value!r}")
        if not self.research_only:
            raise ValueError("research_only must be True")
        if self.execution_approval_granted:
            raise ValueError("execution_approval_granted must be False")
        if self.production_approval_granted:
            raise ValueError("production_approval_granted must be False")
        if self.live_trading_allowed:
            raise ValueError("live_trading_allowed must be False")
        if self.automatic_execution_allowed:
            raise ValueError("automatic_execution_allowed must be False")
        if not self.human_approval_required:
            raise ValueError("human_approval_required must be True")


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BacktestComparisonConfig:
    """Configuration for the research backtest comparison harness."""

    strategy_name: str
    strategy_path: str | Path
    data_path: str | Path
    timeframe: str
    timerange: str
    balance: Decimal
    stake: Decimal
    max_open_trades: int
    fee: Decimal
    executable_path: str | Path
    timeout_seconds: int = 300
    output_dir: str | Path = "reports/research_backtest_comparison"
    data_dir: str | Path = "data/research_backtest_comparison"
    protections: tuple[str, ...] = ()
    retain_workspace_on_failure: bool = True
    env_allowlist: tuple[str, ...] | None = None
    extra_env: dict[str, str] | None = None
    metadata: Any = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "strategy_path", Path(self.strategy_path))
        object.__setattr__(self, "data_path", Path(self.data_path))
        object.__setattr__(self, "executable_path", Path(self.executable_path))
        object.__setattr__(self, "output_dir", Path(self.output_dir))
        object.__setattr__(self, "data_dir", Path(self.data_dir))
        object.__setattr__(self, "balance", _coerce_decimal(self.balance))
        object.__setattr__(self, "stake", _coerce_decimal(self.stake))
        object.__setattr__(self, "fee", _coerce_decimal(self.fee))
        object.__setattr__(
            self, "protections", _coerce_tuple_strs(self.protections)
        )
        if self.env_allowlist is not None:
            object.__setattr__(
                self, "env_allowlist", _coerce_tuple_strs(self.env_allowlist)
            )
        if self.extra_env is not None:
            object.__setattr__(self, "extra_env", dict(self.extra_env))
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))

        if not isinstance(self.strategy_name, str) or not self.strategy_name.strip():
            raise ValueError("strategy_name must be a non-empty string")
        if not isinstance(self.timeframe, str) or not self.timeframe.strip():
            raise ValueError("timeframe must be a non-empty string")
        if not isinstance(self.timerange, str) or not self.timerange.strip():
            raise ValueError("timerange must be a non-empty string")
        if self.balance is None or self.balance <= Decimal("0"):
            raise ValueError("balance must be a positive Decimal")
        if self.stake is None or self.stake <= Decimal("0"):
            raise ValueError("stake must be a positive Decimal")
        if not isinstance(self.max_open_trades, int) or self.max_open_trades < 1:
            raise ValueError("max_open_trades must be a positive integer")
        if self.fee is None or self.fee < Decimal("0"):
            raise ValueError("fee must be a non-negative Decimal")
        if not isinstance(self.timeout_seconds, int) or self.timeout_seconds < 1:
            raise ValueError("timeout_seconds must be a positive integer")


# ---------------------------------------------------------------------------
# Arm inputs and results
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BacktestArmInput:
    """Input for a single backtest arm (candidate or baseline)."""

    pairlist: tuple[str, ...]
    label: BacktestArmLabel
    universe_fingerprint: str
    metadata: Any = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "pairlist", _coerce_tuple_strs(self.pairlist))
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))
        if not isinstance(self.label, BacktestArmLabel):
            raise ValueError(
                f"label must be a BacktestArmLabel, got {self.label!r}"
            )
        if not isinstance(self.universe_fingerprint, str) or not self.universe_fingerprint.strip():
            raise ValueError("universe_fingerprint must be a non-empty string")
        if not self.pairlist:
            raise ValueError("pairlist must be non-empty")


@dataclass(frozen=True)
class FreqtradeExecutableInfo:
    """Validated Freqtrade executable metadata."""

    path: Path
    version: str
    is_valid: bool
    reason_codes: tuple[str, ...] = ()
    metadata: Any = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "path", Path(self.path))
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))
        if not isinstance(self.version, str):
            raise ValueError("version must be a string")
        if not isinstance(self.is_valid, bool):
            raise ValueError("is_valid must be a bool")


@dataclass(frozen=True)
class BacktestMetrics:
    """Canonical metrics parsed from a Freqtrade backtest export.

    All monetary/ratio fields are Decimal or None. Missing values are represented
    internally as None and serialized as UNAVAILABLE.
    """

    total_return_pct: Decimal | None = None
    absolute_profit: Decimal | None = None
    final_balance: Decimal | None = None
    max_drawdown_pct: Decimal | None = None
    sharpe_ratio: Decimal | None = None
    sortino_ratio: Decimal | None = None
    calmar_ratio: Decimal | None = None
    profit_factor: Decimal | None = None
    win_rate_pct: Decimal | None = None
    trade_count: int = 0
    avg_trade_duration: Decimal | None = None  # minutes
    fees_paid: Decimal | None = None
    parser_version: str = RESEARCH_BACKTEST_COMPARISON_VERSION
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "total_return_pct",
            "absolute_profit",
            "final_balance",
            "max_drawdown_pct",
            "sharpe_ratio",
            "sortino_ratio",
            "calmar_ratio",
            "profit_factor",
            "win_rate_pct",
            "avg_trade_duration",
            "fees_paid",
        ):
            value = getattr(self, name)
            coerced = _coerce_decimal(value)
            object.__setattr__(self, name, coerced)
        if not isinstance(self.trade_count, int) or self.trade_count < 0:
            raise ValueError("trade_count must be a non-negative integer")
        if not isinstance(self.parser_version, str) or not self.parser_version.strip():
            raise ValueError("parser_version must be a non-empty string")
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))


@dataclass(frozen=True)
class BacktestRunResult:
    """Result of running one backtest arm."""

    label: BacktestArmLabel
    success: bool
    metrics: BacktestMetrics
    stdout: str
    stderr: str
    exit_code: int
    workspace: Path
    result_file: Path | None
    command: tuple[str, ...]
    command_fingerprint: str
    strategy_sha_before: str
    strategy_sha_after: str
    fingerprint: str
    pairlist: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()
    metadata: Any = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "workspace", Path(self.workspace))
        if self.result_file is not None:
            object.__setattr__(self, "result_file", Path(self.result_file))
        object.__setattr__(self, "command", _coerce_tuple_strs(self.command))
        object.__setattr__(self, "pairlist", _coerce_tuple_strs(self.pairlist))
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))
        if not isinstance(self.label, BacktestArmLabel):
            raise ValueError(f"label must be a BacktestArmLabel, got {self.label!r}")
        if not isinstance(self.success, bool):
            raise ValueError("success must be a bool")
        if not isinstance(self.stdout, str):
            raise ValueError("stdout must be a string")
        if not isinstance(self.stderr, str):
            raise ValueError("stderr must be a string")
        if not isinstance(self.exit_code, int):
            raise ValueError("exit_code must be an int")
        if not isinstance(self.command_fingerprint, str) or not self.command_fingerprint.strip():
            raise ValueError("command_fingerprint must be a non-empty string")
        if not isinstance(self.strategy_sha_before, str) or not self.strategy_sha_before.strip():
            raise ValueError("strategy_sha_before must be a non-empty string")
        if not isinstance(self.strategy_sha_after, str):
            raise ValueError("strategy_sha_after must be a string")
        if not isinstance(self.fingerprint, str) or not self.fingerprint.strip():
            raise ValueError("fingerprint must be a non-empty string")
        if not isinstance(self.metrics, BacktestMetrics):
            raise ValueError(f"metrics must be BacktestMetrics, got {self.metrics!r}")


# ---------------------------------------------------------------------------
# Comparison and report
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BacktestComparisonResult:
    """Paired comparison between candidate and baseline backtest arms."""

    candidate: BacktestRunResult
    baseline: BacktestRunResult
    metric_deltas: dict[str, Decimal | None]
    interpretations: dict[str, MetricInterpretation]
    comparison_fingerprint: str
    trade_sufficiency: bool
    reason_codes: tuple[str, ...] = ()
    metadata: Any = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))
        if not isinstance(self.candidate, BacktestRunResult):
            raise ValueError(f"candidate must be BacktestRunResult, got {self.candidate!r}")
        if not isinstance(self.baseline, BacktestRunResult):
            raise ValueError(f"baseline must be BacktestRunResult, got {self.baseline!r}")
        if not isinstance(self.metric_deltas, dict):
            raise ValueError(f"metric_deltas must be a dict, got {self.metric_deltas!r}")
        if not isinstance(self.interpretations, dict):
            raise ValueError(f"interpretations must be a dict, got {self.interpretations!r}")
        if not isinstance(self.comparison_fingerprint, str) or not self.comparison_fingerprint.strip():
            raise ValueError("comparison_fingerprint must be a non-empty string")
        if not isinstance(self.trade_sufficiency, bool):
            raise ValueError("trade_sufficiency must be a bool")


@dataclass(frozen=True)
class BacktestFairnessManifest:
    """Fairness contract: candidate and baseline share identical assumptions."""

    strategy_name: str
    strategy_fingerprint: str
    data_fingerprint: str
    timeframe: str
    timerange: str
    balance: Decimal
    stake: Decimal
    max_open_trades: int
    fee: Decimal
    protections: tuple[str, ...]
    assumptions_equal: bool
    pairlist_only_difference: tuple[str, tuple[str, ...], tuple[str, ...]]
    fairness_fingerprint: str
    reason_codes: tuple[str, ...] = ()
    metadata: Any = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "protections", _coerce_tuple_strs(self.protections))
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))
        if not isinstance(self.strategy_fingerprint, str) or not self.strategy_fingerprint.strip():
            raise ValueError("strategy_fingerprint must be a non-empty string")
        if not isinstance(self.data_fingerprint, str) or not self.data_fingerprint.strip():
            raise ValueError("data_fingerprint must be a non-empty string")
        if not isinstance(self.fairness_fingerprint, str) or not self.fairness_fingerprint.strip():
            raise ValueError("fairness_fingerprint must be a non-empty string")
        if not isinstance(self.assumptions_equal, bool):
            raise ValueError("assumptions_equal must be a bool")


@dataclass(frozen=True)
class BacktestComparisonManifest:
    """Manifest recording inputs, versions, and fingerprints for audit."""

    version: str
    spec_version: str
    research_backtest_comparison_version: str
    generated_at: datetime
    config_fingerprint: str
    strategy_fingerprint: str
    candidate_pairlist_fingerprint: str
    baseline_pairlist_fingerprint: str
    candidate_result_fingerprint: str
    baseline_result_fingerprint: str
    comparison_fingerprint: str
    safety_flags: ResearchBacktestSafetyFlags
    reason_codes: tuple[str, ...]
    metadata: Any = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.generated_at, datetime) or self.generated_at.tzinfo is None:
            raise ValueError("generated_at must be a timezone-aware datetime")
        for name, value in (
            ("config_fingerprint", self.config_fingerprint),
            ("strategy_fingerprint", self.strategy_fingerprint),
            ("candidate_pairlist_fingerprint", self.candidate_pairlist_fingerprint),
            ("baseline_pairlist_fingerprint", self.baseline_pairlist_fingerprint),
            ("candidate_result_fingerprint", self.candidate_result_fingerprint),
            ("baseline_result_fingerprint", self.baseline_result_fingerprint),
            ("comparison_fingerprint", self.comparison_fingerprint),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if not isinstance(self.safety_flags, ResearchBacktestSafetyFlags):
            raise ValueError(
                f"safety_flags must be ResearchBacktestSafetyFlags, got {self.safety_flags!r}"
            )
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))


@dataclass(frozen=True)
class BacktestComparisonReport:
    """Top-level paired backtest comparison report."""

    version: str
    spec_version: str
    research_backtest_comparison_version: str
    config: BacktestComparisonConfig
    manifest: BacktestComparisonManifest
    candidate: BacktestRunResult
    baseline: BacktestRunResult
    comparison: BacktestComparisonResult
    fairness: BacktestFairnessManifest
    safety_flags: ResearchBacktestSafetyFlags
    fingerprint: str
    human_approval_required: bool = True
    research_only: bool = True
    reason_codes: tuple[str, ...] = ()
    metadata: Any = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))
        if not isinstance(self.version, str) or not self.version.strip():
            raise ValueError("version must be a non-empty string")
        if not isinstance(self.spec_version, str) or not self.spec_version.strip():
            raise ValueError("spec_version must be a non-empty string")
        if not isinstance(self.research_backtest_comparison_version, str) or not self.research_backtest_comparison_version.strip():
            raise ValueError("research_backtest_comparison_version must be a non-empty string")
        if not isinstance(self.fingerprint, str) or not self.fingerprint.strip():
            raise ValueError("fingerprint must be a non-empty string")
        if not isinstance(self.human_approval_required, bool):
            raise ValueError("human_approval_required must be a boolean")
        if not isinstance(self.research_only, bool):
            raise ValueError("research_only must be a boolean")
        if not isinstance(self.safety_flags, ResearchBacktestSafetyFlags):
            raise ValueError(
                f"safety_flags must be ResearchBacktestSafetyFlags, got {self.safety_flags!r}"
            )
        if not isinstance(self.manifest, BacktestComparisonManifest):
            raise ValueError(f"manifest must be BacktestComparisonManifest, got {self.manifest!r}")
        if not isinstance(self.candidate, BacktestRunResult):
            raise ValueError(f"candidate must be BacktestRunResult, got {self.candidate!r}")
        if not isinstance(self.baseline, BacktestRunResult):
            raise ValueError(f"baseline must be BacktestRunResult, got {self.baseline!r}")
        if not isinstance(self.comparison, BacktestComparisonResult):
            raise ValueError(f"comparison must be BacktestComparisonResult, got {self.comparison!r}")
        if not isinstance(self.fairness, BacktestFairnessManifest):
            raise ValueError(f"fairness must be BacktestFairnessManifest, got {self.fairness!r}")


# ---------------------------------------------------------------------------
# Errors (also mirrored in errors.py for public API)
# ---------------------------------------------------------------------------


class ResearchBacktestComparisonError(Exception):
    """Base exception for the research backtest comparison harness."""

    def __init__(self, message: str, reason_code: str | None = None) -> None:
        super().__init__(message)
        self.reason_code = reason_code


class ResearchBacktestComparisonConfigError(ResearchBacktestComparisonError):
    """Invalid configuration."""


class ResearchBacktestComparisonValidationError(ResearchBacktestComparisonError):
    """Validation failure."""


class ResearchBacktestComparisonExecutableError(ResearchBacktestComparisonError):
    """Executable validation/execution failure."""


class ResearchBacktestComparisonFairnessError(ResearchBacktestComparisonError):
    """Fairness contract violation."""


class ResearchBacktestComparisonRunnerError(ResearchBacktestComparisonError):
    """Subprocess runner failure."""


class ResearchBacktestComparisonParserError(ResearchBacktestComparisonError):
    """Parser/version failure."""


class ResearchBacktestComparisonWriterError(ResearchBacktestComparisonError):
    """Writer failure."""

    def __init__(self, message: str, reason_code: str | None = None) -> None:
        super().__init__(message, reason_code=reason_code)

