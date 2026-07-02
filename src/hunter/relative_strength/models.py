"""Frozen dataclasses for hunter.relative_strength package.

MVP-24 — Relative Strength Engine.

All dataclasses are frozen. Validation runs in __post_init__.
Inputs are already-loaded local values only; the engine never opens files,
follows paths, validates paths, calls network endpoints, or accesses external
resources.

The relative strength engine is a human-audit / research-support artifact only.
It is not a trading signal, not trade approval, not strategy approval, not
execution approval, not portfolio/universe approval, and not Freqtrade input.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from types import MappingProxyType
from typing import Any

RELATIVE_STRENGTH_VERSION = "1.0"


class RelativeStrengthState(Enum):
    """Overall state of a single relative strength score or report."""

    READY = "ready"
    INSUFFICIENT_DATA = "insufficient_data"
    BLOCKED = "blocked"


class RelativeStrengthDecision(Enum):
    """Research-only decision classification for a single coin."""

    OUTPERFORMER = "outperformer"
    NEUTRAL = "neutral"
    UNDERPERFORMER = "underperformer"
    INSUFFICIENT_DATA = "insufficient_data"
    BLOCKED = "blocked"


class RelativeStrengthBenchmarkKind(Enum):
    """Benchmark used for a relative comparison."""

    BTC = "btc"
    ETH = "eth"
    NEUTRAL = "neutral"


# ---------------------------------------------------------------------------
# Reason codes — deterministic, priority-ordered constants.
# ---------------------------------------------------------------------------

UNSAFE_INPUT_CONTENT = "UNSAFE_INPUT_CONTENT"
INVALID_INPUT_DATA = "INVALID_INPUT_DATA"
INVALID_CONFIG = "INVALID_CONFIG"
MISSING_BTC_BENCHMARK = "MISSING_BTC_BENCHMARK"
INSUFFICIENT_COIN_DATA = "INSUFFICIENT_COIN_DATA"
FORBIDDEN_TRADING_SEMANTICS = "FORBIDDEN_TRADING_SEMANTICS"

ETH_BENCHMARK_MISSING = "ETH_BENCHMARK_MISSING"
STALE_INPUT_DATA = "STALE_INPUT_DATA"
MIN_ROWS_NOT_MET = "MIN_ROWS_NOT_MET"
PERIOD_DATA_MISSING = "PERIOD_DATA_MISSING"

INPUTS_ALREADY_LOADED = "INPUTS_ALREADY_LOADED"
BENCHMARKS_PROVIDED_BY_CALLER = "BENCHMARKS_PROVIDED_BY_CALLER"
NO_ACTION_COMMANDS_EMITTED = "NO_ACTION_COMMANDS_EMITTED"
HUMAN_RESEARCH_ONLY = "HUMAN_RESEARCH_ONLY"
NO_NETWORK_CONNECTION = "NO_NETWORK_CONNECTION"
NO_DATABASE_CONNECTION = "NO_DATABASE_CONNECTION"
NO_FILE_READ_IN_ENGINE = "NO_FILE_READ_IN_ENGINE"

RELATIVE_STRENGTH_BLOCKING_REASON_CODES: tuple[str, ...] = (
    UNSAFE_INPUT_CONTENT,
    INVALID_INPUT_DATA,
    INVALID_CONFIG,
    MISSING_BTC_BENCHMARK,
    INSUFFICIENT_COIN_DATA,
    FORBIDDEN_TRADING_SEMANTICS,
)

RELATIVE_STRENGTH_INSUFFICIENT_DATA_REASON_CODES: tuple[str, ...] = (
    ETH_BENCHMARK_MISSING,
    STALE_INPUT_DATA,
    MIN_ROWS_NOT_MET,
    PERIOD_DATA_MISSING,
)

RELATIVE_STRENGTH_ADVISORY_REASON_CODES: tuple[str, ...] = (
    INPUTS_ALREADY_LOADED,
    BENCHMARKS_PROVIDED_BY_CALLER,
    NO_ACTION_COMMANDS_EMITTED,
    HUMAN_RESEARCH_ONLY,
    NO_NETWORK_CONNECTION,
    NO_DATABASE_CONNECTION,
    NO_FILE_READ_IN_ENGINE,
)

RELATIVE_STRENGTH_REASON_CODES: tuple[str, ...] = (
    RELATIVE_STRENGTH_BLOCKING_REASON_CODES
    + RELATIVE_STRENGTH_INSUFFICIENT_DATA_REASON_CODES
    + RELATIVE_STRENGTH_ADVISORY_REASON_CODES
)


# ---------------------------------------------------------------------------
# Forbidden terms — matches SPEC-025 list.
# ---------------------------------------------------------------------------

FORBIDDEN_RELATIVE_STRENGTH_TERMS: frozenset[str] = frozenset({
    "live_trade",
    "real_order",
    "leverage",
    "shorting",
    "execute",
    "place_order",
    "buy",
    "sell",
    "enter_long",
    "enter_short",
    "exit_long",
    "exit_short",
    "portfolio_approval",
    "universe_approval",
    "strategy_approval",
    "execution_approval",
    "trade_approval",
    "go_live",
    "production_ready",
    "binance",
    "exchange_api",
    "api_key",
    "secret",
    "deploy",
    "trigger",
    "submit",
    "task_runner",
    "event_store",
    "database",
    "web_ui",
    "dashboard",
})


# ---------------------------------------------------------------------------
# Simple helper functions (no forward class references).
# ---------------------------------------------------------------------------

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


def _validate_reason_codes(reason_codes: tuple[str, ...]) -> None:
    """Validate every reason code is supported."""
    for code in reason_codes:
        if code not in RELATIVE_STRENGTH_REASON_CODES:
            raise ValueError(f"unsupported reason code: {code}")


def _coerce_mapping(value: Mapping[str, Any] | dict[str, Any] | None) -> Mapping[str, Any]:
    """Coerce a mapping into an immutable MappingProxyType."""
    if value is None:
        return MappingProxyType({})
    if isinstance(value, Mapping):
        return MappingProxyType(dict(value))
    raise ValueError("value must be a mapping")


def _coerce_sub_scores(value: Mapping[str, float] | dict[str, float] | None) -> Mapping[str, float]:
    """Coerce sub-scores into an immutable MappingProxyType."""
    if value is None:
        return MappingProxyType({})
    if isinstance(value, Mapping):
        return MappingProxyType(dict(value))
    raise ValueError("sub_scores must be a mapping")


# ---------------------------------------------------------------------------
# Model dataclasses.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OhlcvRow:
    """A single OHLCV-like row for relative-strength input."""

    timestamp: datetime | int
    close: float | Decimal
    open: float | Decimal | None = None
    high: float | Decimal | None = None
    low: float | Decimal | None = None
    volume: float | Decimal | None = None

    def __post_init__(self) -> None:
        if self.close is None:
            raise ValueError("OhlcvRow.close must not be None")
        if self.close == 0:
            raise ValueError("OhlcvRow.close must be non-zero")


def _ensure_tuple_of_ohlcv(
    value: Sequence[OhlcvRow] | None,
    field_name: str,
) -> tuple[OhlcvRow, ...]:
    """Validate and coerce a sequence of OhlcvRow into a tuple."""
    if value is None:
        return ()
    if isinstance(value, (tuple, list)):
        for item in value:
            if not isinstance(item, OhlcvRow):
                raise ValueError(f"{field_name} must contain OhlcvRow values")
        return tuple(value)
    raise ValueError(f"{field_name} must be a tuple or list of OhlcvRow")


@dataclass(frozen=True)
class RelativeStrengthInput:
    """A single coin/pair with its already-loaded OHLCV sequence."""

    symbol: str
    rows: Sequence[OhlcvRow]

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, str) or not self.symbol:
            raise ValueError("symbol must be non-empty")
        rows = _ensure_tuple_of_ohlcv(self.rows, "rows")
        if not rows:
            raise ValueError("rows must be non-empty")
        object.__setattr__(self, "rows", rows)


@dataclass(frozen=True)
class RelativeStrengthConfig:
    """Configuration for the relative strength engine."""

    version: str = RELATIVE_STRENGTH_VERSION
    lookback_days: tuple[int, ...] = (7, 14, 30)
    min_required_rows: int = 30
    score_weights: Mapping[str, float] = field(
        default_factory=lambda: MappingProxyType({
            "coin_minus_btc_30d": 0.35,
            "coin_minus_btc_14d": 0.20,
            "coin_minus_btc_7d": 0.10,
            "coin_minus_eth_30d": 0.10,
            "rank_percentile_30d": 0.15,
            "ratio_trend": 0.10,
        })
    )
    outperformer_threshold: float = 65.0
    underperformer_threshold: float = 35.0
    rank_percentile_window: int = 30
    ratio_trend_lookback: int = 30
    ratio_trend_ma_window: int = 7
    rounding_policy: str = "default"
    block_on_missing_eth: bool = False
    block_on_missing_data: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.version, str) or not self.version:
            raise ValueError("version must be non-empty")
        if any(not isinstance(d, int) or d <= 0 for d in self.lookback_days):
            raise ValueError("lookback_days must be positive integers")
        if not isinstance(self.min_required_rows, int) or self.min_required_rows < 2:
            raise ValueError("min_required_rows must be at least 2")
        if not isinstance(self.score_weights, Mapping):
            raise ValueError("score_weights must be a mapping")
        if not (0.999 <= sum(self.score_weights.values()) <= 1.001):
            raise ValueError("score_weights must sum to 1.0")
        if not (0.0 <= self.outperformer_threshold <= 100.0):
            raise ValueError("outperformer_threshold must be in [0, 100]")
        if not (0.0 <= self.underperformer_threshold <= 100.0):
            raise ValueError("underperformer_threshold must be in [0, 100]")
        if self.outperformer_threshold <= self.underperformer_threshold:
            raise ValueError("outperformer_threshold must exceed underperformer_threshold")
        if not isinstance(self.rank_percentile_window, int) or self.rank_percentile_window <= 0:
            raise ValueError("rank_percentile_window must be a positive integer")
        if not isinstance(self.ratio_trend_lookback, int) or self.ratio_trend_lookback <= 0:
            raise ValueError("ratio_trend_lookback must be a positive integer")
        if not isinstance(self.ratio_trend_ma_window, int) or self.ratio_trend_ma_window <= 0:
            raise ValueError("ratio_trend_ma_window must be a positive integer")


@dataclass(frozen=True)
class RelativeStrengthSafetyFlags:
    """Safety invariants for the relative strength engine."""

    # Runtime safety flags
    live_trading_enabled: bool = False
    real_orders_enabled: bool = False
    leverage_enabled: bool = False
    shorting_enabled: bool = False

    # Output safety flags
    output_is_human_research_only: bool = True
    output_not_trading_signal: bool = True
    output_not_trade_approval: bool = True
    output_not_strategy_approval: bool = True
    output_not_execution_approval: bool = True
    output_not_portfolio_approval: bool = True
    output_not_freqtrade_input: bool = True
    output_not_order_input: bool = True
    output_not_exchange_input: bool = True
    output_not_universe_approval: bool = True

    # Feedback safety flags
    feedback_into_execution: bool = False
    feedback_into_strategy: bool = False
    feedback_into_freqtrade: bool = False
    feedback_into_portfolio: bool = False

    # Capability flags
    network_enabled: bool = False
    database_enabled: bool = False
    file_read_enabled: bool = False
    file_write_enabled: bool = True
    runtime_registry_enabled: bool = False
    indexer_crawler_enabled: bool = False
    event_store_enabled: bool = False
    task_runner_enabled: bool = False

    # Advisory flags
    inputs_already_loaded: bool = True
    no_action_commands_emitted: bool = True
    benchmarks_provided_by_caller: bool = True
    human_research_only: bool = True

    def __post_init__(self) -> None:
        unsafe_flags = (
            self.live_trading_enabled,
            self.real_orders_enabled,
            self.leverage_enabled,
            self.shorting_enabled,
            self.feedback_into_execution,
            self.feedback_into_strategy,
            self.feedback_into_freqtrade,
            self.feedback_into_portfolio,
            self.network_enabled,
            self.database_enabled,
            self.file_read_enabled,
            self.runtime_registry_enabled,
            self.indexer_crawler_enabled,
            self.event_store_enabled,
            self.task_runner_enabled,
        )
        if any(unsafe_flags):
            raise ValueError("unsafe relative strength safety flags are enabled")
        safe_flags = (
            self.output_is_human_research_only,
            self.output_not_trading_signal,
            self.output_not_trade_approval,
            self.output_not_strategy_approval,
            self.output_not_execution_approval,
            self.output_not_portfolio_approval,
            self.output_not_freqtrade_input,
            self.output_not_order_input,
            self.output_not_exchange_input,
            self.output_not_universe_approval,
            self.inputs_already_loaded,
            self.no_action_commands_emitted,
            self.benchmarks_provided_by_caller,
            self.human_research_only,
        )
        if not all(safe_flags):
            raise ValueError("safe relative strength output flags must be True")


@dataclass(frozen=True)
class RelativeStrengthDataQuality:
    """Completeness and quality metrics for one coin or the whole universe."""

    expected_rows: int
    actual_rows: int
    missing_rows: int
    missing_periods: tuple[str, ...]
    min_required_rows_met: bool
    btc_benchmark_rows: int
    eth_benchmark_rows: int | None
    stale_input_count: int
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.expected_rows, int) or self.expected_rows < 0:
            raise ValueError("expected_rows must be non-negative")
        if not isinstance(self.actual_rows, int) or self.actual_rows < 0:
            raise ValueError("actual_rows must be non-negative")
        if not isinstance(self.missing_rows, int) or self.missing_rows < 0:
            raise ValueError("missing_rows must be non-negative")
        if self.missing_rows > self.expected_rows:
            raise ValueError("missing_rows cannot exceed expected_rows")
        if not isinstance(self.btc_benchmark_rows, int) or self.btc_benchmark_rows < 0:
            raise ValueError("btc_benchmark_rows must be non-negative")
        if self.eth_benchmark_rows is not None and (
            not isinstance(self.eth_benchmark_rows, int) or self.eth_benchmark_rows < 0
        ):
            raise ValueError("eth_benchmark_rows must be non-negative or None")
        if not isinstance(self.stale_input_count, int) or self.stale_input_count < 0:
            raise ValueError("stale_input_count must be non-negative")
        missing_periods = _ensure_tuple_of_str(self.missing_periods, "missing_periods")
        reason_codes = _ensure_tuple_of_str(self.reason_codes, "reason_codes")
        _validate_reason_codes(reason_codes)
        object.__setattr__(self, "missing_periods", missing_periods)
        object.__setattr__(self, "reason_codes", reason_codes)


@dataclass(frozen=True)
class RelativeStrengthPeriodReturn:
    """A single period return for a coin and its benchmarks."""

    period_days: int
    coin_return: float | None
    btc_return: float | None
    eth_return: float | None
    coin_minus_btc: float | None
    coin_minus_eth: float | None
    has_data: bool
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.period_days, int) or self.period_days <= 0:
            raise ValueError("period_days must be a positive integer")
        reason_codes = _ensure_tuple_of_str(self.reason_codes, "reason_codes")
        _validate_reason_codes(reason_codes)
        object.__setattr__(self, "reason_codes", reason_codes)


def _ensure_tuple_of_period_returns(
    value: Sequence[RelativeStrengthPeriodReturn] | None,
    field_name: str,
) -> tuple[RelativeStrengthPeriodReturn, ...]:
    """Validate and coerce a sequence of RelativeStrengthPeriodReturn."""
    if value is None:
        return ()
    if isinstance(value, (tuple, list)):
        for item in value:
            if not isinstance(item, RelativeStrengthPeriodReturn):
                raise ValueError(
                    f"{field_name} must contain RelativeStrengthPeriodReturn values"
                )
        return tuple(value)
    raise ValueError(
        f"{field_name} must be a tuple or list of RelativeStrengthPeriodReturn"
    )


@dataclass(frozen=True)
class RelativeStrengthRatioTrend:
    """Trend summary for a coin/BTC ratio series."""

    last_ratio: float
    ma_ratio: float
    slope: float
    trend_score: float
    lookback: int
    has_data: bool
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.lookback, int) or self.lookback <= 0:
            raise ValueError("lookback must be a positive integer")
        if not isinstance(self.trend_score, (int, float)) or not (0.0 <= self.trend_score <= 100.0):
            raise ValueError("trend_score must be in [0, 100]")
        reason_codes = _ensure_tuple_of_str(self.reason_codes, "reason_codes")
        _validate_reason_codes(reason_codes)
        object.__setattr__(self, "reason_codes", reason_codes)


@dataclass(frozen=True)
class RelativeStrengthScore:
    """Relative strength score for a single coin."""

    symbol: str
    base_benchmark: RelativeStrengthBenchmarkKind
    state: RelativeStrengthState
    decision: RelativeStrengthDecision
    total_score: float
    period_returns: tuple[RelativeStrengthPeriodReturn, ...]
    ratio_trend: RelativeStrengthRatioTrend
    rank_percentile_30d: float | None
    sub_scores: Mapping[str, float]
    data_quality: RelativeStrengthDataQuality
    human_note: str
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.symbol, str) or not self.symbol:
            raise ValueError("symbol must be non-empty")
        if not isinstance(self.total_score, (int, float)) or not (0.0 <= self.total_score <= 100.0):
            raise ValueError("total_score must be in [0, 100]")
        if not isinstance(self.human_note, str):
            raise ValueError("human_note must be a string")
        period_returns = _ensure_tuple_of_period_returns(self.period_returns, "period_returns")
        sub_scores = _coerce_sub_scores(self.sub_scores)
        for key, value in sub_scores.items():
            if not isinstance(key, str) or not key:
                raise ValueError("sub_scores keys must be non-empty strings")
            if not isinstance(value, (int, float)) or not (0.0 <= value <= 100.0):
                raise ValueError("sub_scores values must be in [0, 100]")
        reason_codes = _ensure_tuple_of_str(self.reason_codes, "reason_codes")
        _validate_reason_codes(reason_codes)
        object.__setattr__(self, "period_returns", period_returns)
        object.__setattr__(self, "sub_scores", sub_scores)
        object.__setattr__(self, "reason_codes", reason_codes)


@dataclass(frozen=True)
class RelativeStrengthUniverseSummary:
    """Aggregated summary over the scored universe."""

    total_coins: int
    outperformer_count: int
    neutral_count: int
    underperformer_count: int
    insufficient_data_count: int
    blocked_count: int
    top_outperformer: str | None
    top_underperformer: str | None
    average_total_score: float
    data_quality: RelativeStrengthDataQuality
    summary_narrative: str

    def __post_init__(self) -> None:
        for field_name in (
            "total_coins",
            "outperformer_count",
            "neutral_count",
            "underperformer_count",
            "insufficient_data_count",
            "blocked_count",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer")
        if (
            self.outperformer_count
            + self.neutral_count
            + self.underperformer_count
            + self.insufficient_data_count
            + self.blocked_count
            != self.total_coins
        ):
            raise ValueError("decision counts must sum to total_coins")
        if not isinstance(self.average_total_score, (int, float)) or not (
            0.0 <= self.average_total_score <= 100.0
        ):
            raise ValueError("average_total_score must be in [0, 100]")
        if not isinstance(self.summary_narrative, str):
            raise ValueError("summary_narrative must be a string")


@dataclass(frozen=True)
class RelativeStrengthReport:
    """Full deterministic relative strength report."""

    report_id: str
    config: RelativeStrengthConfig
    safety_flags: RelativeStrengthSafetyFlags
    scores: tuple[RelativeStrengthScore, ...]
    universe_summary: RelativeStrengthUniverseSummary
    btc_series_head: tuple[OhlcvRow, ...]
    eth_series_head: tuple[OhlcvRow, ...] | None
    generated_at: datetime
    reason_codes: tuple[str, ...]
    metadata: Mapping[str, Any]
    kind: str = "relative_strength_report"
    version: str = "0.24.0-dev"
    source_spec: str = "SPEC-025"

    def __post_init__(self) -> None:
        if not isinstance(self.report_id, str) or not self.report_id:
            raise ValueError("report_id must be non-empty")
        if not isinstance(self.kind, str) or not self.kind:
            raise ValueError("kind must be non-empty")
        if not isinstance(self.source_spec, str) or not self.source_spec:
            raise ValueError("source_spec must be non-empty")
        if not isinstance(self.version, str) or not self.version:
            raise ValueError("version must be non-empty")
        if self.generated_at is not None and (
            not isinstance(self.generated_at, datetime) or self.generated_at.tzinfo is None
        ):
            raise ValueError("generated_at must be a timezone-aware datetime")
        scores = _ensure_tuple_of_scores(self.scores, "scores")
        btc_series_head = _ensure_tuple_of_ohlcv(self.btc_series_head, "btc_series_head")
        eth_series_head = (
            _ensure_tuple_of_ohlcv(self.eth_series_head, "eth_series_head")
            if self.eth_series_head is not None
            else None
        )
        metadata = _coerce_mapping(self.metadata)
        reason_codes = _ensure_tuple_of_str(self.reason_codes, "reason_codes")
        _validate_reason_codes(reason_codes)
        object.__setattr__(self, "scores", scores)
        object.__setattr__(self, "btc_series_head", btc_series_head)
        object.__setattr__(self, "eth_series_head", eth_series_head)
        object.__setattr__(self, "metadata", metadata)
        object.__setattr__(self, "reason_codes", reason_codes)

    @classmethod
    def blocked(
        cls,
        *,
        report_id: str,
        config: RelativeStrengthConfig,
        reason_codes: tuple[str, ...],
        generated_at: datetime | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> RelativeStrengthReport:
        """Return a fail-closed BLOCKED report when inputs are unsafe or invalid.

        If `generated_at` is omitted, the current UTC time is used. Tests should pass
        an explicit `generated_at` for deterministic output.
        """
        empty_summary = RelativeStrengthUniverseSummary(
            total_coins=0,
            outperformer_count=0,
            neutral_count=0,
            underperformer_count=0,
            insufficient_data_count=0,
            blocked_count=0,
            top_outperformer=None,
            top_underperformer=None,
            average_total_score=0.0,
            data_quality=RelativeStrengthDataQuality(
                expected_rows=0,
                actual_rows=0,
                missing_rows=0,
                missing_periods=(),
                min_required_rows_met=False,
                btc_benchmark_rows=0,
                eth_benchmark_rows=None,
                stale_input_count=0,
                reason_codes=reason_codes,
            ),
            summary_narrative="Report blocked due to unsafe or invalid input. No relative strength calculations were performed.",
        )
        return cls(
            report_id=report_id,
            config=config,
            safety_flags=RelativeStrengthSafetyFlags(),
            scores=(),
            universe_summary=empty_summary,
            btc_series_head=(),
            eth_series_head=None,
            generated_at=generated_at or datetime.now(timezone.utc),
            version="0.24.0-dev",
            source_spec="SPEC-025",
            reason_codes=reason_codes,
            metadata=metadata or MappingProxyType({}),
        )


def _ensure_tuple_of_scores(
    value: Sequence[RelativeStrengthScore] | None,
    field_name: str,
) -> tuple[RelativeStrengthScore, ...]:
    """Validate and coerce a sequence of RelativeStrengthScore."""
    if value is None:
        return ()
    if isinstance(value, (tuple, list)):
        for item in value:
            if not isinstance(item, RelativeStrengthScore):
                raise ValueError(
                    f"{field_name} must contain RelativeStrengthScore values"
                )
        return tuple(value)
    raise ValueError(
        f"{field_name} must be a tuple or list of RelativeStrengthScore"
    )
