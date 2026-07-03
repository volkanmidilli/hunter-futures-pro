"""Frozen dataclasses for hunter.backtest package.

MVP-28 — Local Research Backtesting Engine.

All dataclasses are frozen. Validation runs in __post_init__.
Inputs are already-loaded local values only; the engine never opens files,
follows paths, validates paths, calls network endpoints, or accesses external
resources.

The backtest engine is a human-audit / research-support artifact only. It is
not a trading signal, not trade approval, not strategy approval, not execution
approval, not portfolio approval, and not Freqtrade input. It does not emit
action commands, suggest orders, or create execution instructions.

Research weights and simulated returns produced by this engine are not orders,
not position sizes, not trade sizes, and not execution readiness indicators.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType


BACKTEST_VERSION: str = "0.28.0-dev"


class BacktestState(Enum):
    INCLUDED = "INCLUDED"
    CAPPED = "CAPPED"
    WATCHLIST = "WATCHLIST"
    EXCLUDED = "EXCLUDED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    BLOCKED = "BLOCKED"


class BacktestAllocationMode(Enum):
    EQUAL_WEIGHT = "EQUAL_WEIGHT"
    RESEARCH_WEIGHT = "RESEARCH_WEIGHT"
    CUSTOM_WEIGHT = "CUSTOM_WEIGHT"


class BacktestInputKind(Enum):
    SUMMARY = "SUMMARY"
    MANUAL = "MANUAL"


# Reason code constants
INVALID_PAIR = "INVALID_PAIR"
INVALID_PRICE = "INVALID_PRICE"
INVALID_DATE = "INVALID_DATE"
UNSAFE_BACKTEST_CONTENT = "UNSAFE_BACKTEST_CONTENT"
MISSING_DECISION_CONTEXT = "MISSING_DECISION_CONTEXT"
MISSING_PRICE_HISTORY = "MISSING_PRICE_HISTORY"
INSUFFICIENT_PRICE_HISTORY = "INSUFFICIENT_PRICE_HISTORY"
EXCLUDED_BY_RESEARCH_CONSTRAINTS = "EXCLUDED_BY_RESEARCH_CONSTRAINTS"
WATCHLIST_ZERO_WEIGHT = "WATCHLIST_ZERO_WEIGHT"
MIN_OBSERVATION_COUNT_NOT_MET = "MIN_OBSERVATION_COUNT_NOT_MET"
DISCOVERY_BLOCKED = "DISCOVERY_BLOCKED"
HUMAN_RESEARCH_ONLY = "HUMAN_RESEARCH_ONLY"
NOT_TRADING_ADVICE = "NOT_TRADING_ADVICE"
NOT_EXECUTION_READY = "NOT_EXECUTION_READY"
NO_NETWORK_CONNECTION = "NO_NETWORK_CONNECTION"
NO_FILE_READ_IN_ENGINE = "NO_FILE_READ_IN_ENGINE"
NO_ACTION_COMMANDS_EMITTED = "NO_ACTION_COMMANDS_EMITTED"

BACKTEST_BLOCKING_REASON_CODES: frozenset[str] = frozenset(
    {
        INVALID_PAIR,
        INVALID_PRICE,
        INVALID_DATE,
        UNSAFE_BACKTEST_CONTENT,
        DISCOVERY_BLOCKED,
    }
)

BACKTEST_INSUFFICIENT_DATA_REASON_CODES: frozenset[str] = frozenset(
    {
        MISSING_DECISION_CONTEXT,
        MISSING_PRICE_HISTORY,
        INSUFFICIENT_PRICE_HISTORY,
    }
)

BACKTEST_FILTER_REASON_CODES: frozenset[str] = frozenset(
    {
        EXCLUDED_BY_RESEARCH_CONSTRAINTS,
        WATCHLIST_ZERO_WEIGHT,
        MIN_OBSERVATION_COUNT_NOT_MET,
    }
)

BACKTEST_ADVISORY_REASON_CODES: frozenset[str] = frozenset(
    {
        HUMAN_RESEARCH_ONLY,
        NOT_TRADING_ADVICE,
        NOT_EXECUTION_READY,
        NO_NETWORK_CONNECTION,
        NO_FILE_READ_IN_ENGINE,
        NO_ACTION_COMMANDS_EMITTED,
    }
)

BACKTEST_REASON_CODES: frozenset[str] = (
    BACKTEST_BLOCKING_REASON_CODES
    | BACKTEST_INSUFFICIENT_DATA_REASON_CODES
    | BACKTEST_FILTER_REASON_CODES
    | BACKTEST_ADVISORY_REASON_CODES
)


FORBIDDEN_BACKTEST_TERMS: frozenset[str] = frozenset(
    {
        # Trading / execution terms
        "order",
        "orders",
        "execute",
        "execution",
        "buy",
        "sell",
        "long",
        "short",
        "leverage",
        "margin",
        "liquidation",
        "liquidate",
        "fill",
        "filling",
        "position",
        "positions",
        "position_size",
        "position sizing",
        "position_sizing",
        "order_size",
        "order_sizing",
        "trade_size",
        "trades",
        "trading",
        "trade",
        "signal",
        "signals",
        "signal_generator",
        # Approval / action terms
        "approve",
        "approval",
        "approved",
        "action_command",
        "action command",
        "emit",
        "take_profit",
        "stop_loss",
        "entry",
        "exit",
        "entry_price",
        "exit_price",
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
        # Action commands / deployment terms
        "deploy_capital",
        "deploy capital",
        "capital_allocation",
        "capital allocation",
        "order_management",
        "order management",
    }
)


# Internal helpers


def _round_value(value: float, decimals: int) -> float:
    return round(value, decimals)


def _is_valid_finite_number(value: float | None, name: str = "value") -> None:
    if value is None:
        return
    if not isinstance(value, (int, float)) or math.isinf(value) or math.isnan(value):
        raise ValueError(f"{name} must be a finite number, got {value!r}")


def _is_valid_score(value: float | None, name: str = "score") -> None:
    if value is None:
        return
    if not isinstance(value, (int, float)) or math.isinf(value) or math.isnan(value):
        raise ValueError(f"{name} must be a finite float, got {value!r}")
    if not 0.0 <= value <= 100.0:
        raise ValueError(f"{name} must be in [0, 100], got {value!r}")


def _coerce_tuple_strs(value: Sequence[str] | None) -> tuple[str, ...]:
    if value is None:
        return ()
    seen: set[str] = set()
    result: list[str] = []
    for item in value:
        s = str(item)
        if s not in seen:
            seen.add(s)
            result.append(s)
    return tuple(result)


def _coerce_mapping_strs(value: Mapping[str, str] | None) -> Mapping[str, str]:
    if value is None:
        return MappingProxyType({})
    return MappingProxyType({str(k): str(v) for k, v in value.items()})


def _state_str(value: str | None) -> str:
    return (value or "").strip().lower()


@dataclass(frozen=True)
class BacktestPriceBar:
    """Single price bar for backtest simulation."""

    pair: str
    timestamp: datetime
    close: float
    open: float | None = None
    high: float | None = None
    low: float | None = None
    volume: float | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.pair, str) or not self.pair.strip():
            raise ValueError("pair must be a non-empty string")
        if not isinstance(self.timestamp, datetime):
            raise ValueError("timestamp must be a datetime")
        if self.timestamp.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        _is_valid_finite_number(self.close, "close")
        if self.close <= 0.0:
            raise ValueError("close must be a strictly positive finite number")
        for name, value in (
            ("open", self.open),
            ("high", self.high),
            ("low", self.low),
            ("volume", self.volume),
        ):
            if value is not None:
                _is_valid_finite_number(value, name)
                if value < 0.0:
                    raise ValueError(f"{name} must be non-negative, got {value!r}")
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))


@dataclass(frozen=True)
class BacktestCandidateDecision:
    """Research decision for a candidate from upstream pipeline."""

    pair: str
    state: str
    classification: str
    research_weight_pct: float = 0.0
    final_weight_pct: float = 0.0
    tags: tuple[str, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.pair, str) or not self.pair.strip():
            raise ValueError("pair must be a non-empty string")
        if not isinstance(self.state, str) or not self.state.strip():
            raise ValueError("state must be a non-empty string")
        if not isinstance(self.classification, str):
            raise ValueError("classification must be a string")
        _is_valid_score(self.research_weight_pct, "research_weight_pct")
        _is_valid_score(self.final_weight_pct, "final_weight_pct")
        object.__setattr__(self, "tags", _coerce_tuple_strs(self.tags))
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))


@dataclass(frozen=True)
class BacktestInput:
    """Single pair input for backtest simulation."""

    pair: str
    decision: BacktestCandidateDecision | None = None
    price_bars: tuple[BacktestPriceBar, ...] = ()
    input_kind: BacktestInputKind = BacktestInputKind.SUMMARY
    tags: tuple[str, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.pair, str) or not self.pair.strip():
            raise ValueError("pair must be a non-empty string")
        if self.decision is not None and self.decision.pair != self.pair:
            raise ValueError("decision.pair must match BacktestInput.pair")
        bars = tuple(self.price_bars)
        for bar in bars:
            if bar.pair != self.pair:
                raise ValueError("price_bars[i].pair must match BacktestInput.pair")
        object.__setattr__(self, "price_bars", bars)
        object.__setattr__(self, "tags", _coerce_tuple_strs(self.tags))
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))


@dataclass(frozen=True)
class BacktestRunConfig:
    """Configuration for backtest simulation and metrics."""

    allocation_mode: BacktestAllocationMode = BacktestAllocationMode.RESEARCH_WEIGHT
    include_excluded_candidates: bool = True
    block_on_blocked_context: bool = True
    block_on_missing_context: bool = False
    min_observation_count: int = 2
    allow_missing_decision: bool = False
    custom_weights: Mapping[str, float] = field(default_factory=dict)
    volatility_scale_factor: float = 1.0
    start_timestamp: datetime | None = None
    end_timestamp: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "custom_weights", MappingProxyType(dict(self.custom_weights))
        )
        # Config validation is performed by the engine so invalid configs can
        # produce a fail-closed blocked report instead of raising at import time.


@dataclass(frozen=True)
class BacktestPortfolioSnapshot:
    """Single simulated portfolio equity observation."""

    timestamp: datetime
    equity: float
    weight_sum: float
    observation_count: int
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.timestamp, datetime):
            raise ValueError("timestamp must be a datetime")
        if self.timestamp.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        _is_valid_finite_number(self.equity, "equity")
        _is_valid_finite_number(self.weight_sum, "weight_sum")
        if self.equity < 0.0:
            raise ValueError("equity must be non-negative")
        if self.weight_sum < 0.0:
            raise ValueError("weight_sum must be non-negative")
        if not isinstance(self.observation_count, int) or self.observation_count < 0:
            raise ValueError("observation_count must be a non-negative int")
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))


@dataclass(frozen=True)
class BacktestCandidateResult:
    """Backtest result for a single candidate."""

    pair: str
    state: BacktestState
    classification: str
    allocation_mode: BacktestAllocationMode
    simulated_weight: float
    total_return_pct: float
    max_drawdown_pct: float
    volatility_pct: float
    win_rate_pct: float
    observation_count: int
    missing_data_count: int
    insufficient_data_count: int
    period_returns: tuple[float, ...]
    reason_codes: tuple[str, ...]
    tags: tuple[str, ...]
    metadata: Mapping[str, str]
    notes: tuple[str, ...]
    rank: int | None

    def __post_init__(self) -> None:
        if not isinstance(self.pair, str) or not self.pair.strip():
            raise ValueError("pair must be a non-empty string")
        if not isinstance(self.classification, str):
            raise ValueError("classification must be a string")
        _is_valid_finite_number(self.simulated_weight, "simulated_weight")
        _is_valid_finite_number(self.total_return_pct, "total_return_pct")
        _is_valid_finite_number(self.max_drawdown_pct, "max_drawdown_pct")
        _is_valid_finite_number(self.volatility_pct, "volatility_pct")
        _is_valid_finite_number(self.win_rate_pct, "win_rate_pct")
        for name in ("observation_count", "missing_data_count", "insufficient_data_count"):
            value = getattr(self, name)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative int, got {value!r}")
        for code in self.reason_codes:
            if code not in BACKTEST_REASON_CODES:
                raise ValueError(f"unsupported reason code: {code}")
        object.__setattr__(self, "period_returns", tuple(self.period_returns))
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))
        object.__setattr__(self, "tags", _coerce_tuple_strs(self.tags))
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))
        object.__setattr__(self, "notes", _coerce_tuple_strs(self.notes))


@dataclass(frozen=True)
class BacktestPortfolioResult:
    """Aggregate portfolio-level backtest result."""

    total_return_pct: float
    max_drawdown_pct: float
    volatility_pct: float
    win_rate_pct: float
    observation_count: int
    missing_data_count: int
    insufficient_data_count: int
    blocked_count: int
    candidate_count: int
    equity_curve: tuple[BacktestPortfolioSnapshot, ...]
    reason_codes: tuple[str, ...]
    metadata: Mapping[str, str]

    def __post_init__(self) -> None:
        for name in (
            "total_return_pct",
            "max_drawdown_pct",
            "volatility_pct",
            "win_rate_pct",
        ):
            _is_valid_finite_number(getattr(self, name), name)
        for name in (
            "observation_count",
            "missing_data_count",
            "insufficient_data_count",
            "blocked_count",
            "candidate_count",
        ):
            value = getattr(self, name)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative int, got {value!r}")
        object.__setattr__(self, "equity_curve", tuple(self.equity_curve))
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))


@dataclass(frozen=True)
class BacktestSafetyFlags:
    """Safety flags for the backtest run."""

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

    has_unsafe_content: bool = False
    has_invalid_pair: bool = False
    has_invalid_price: bool = False
    has_invalid_date: bool = False
    has_blocked_context: bool = False
    has_missing_required_context: bool = False
    has_inconsistent_state: bool = False

    @property
    def is_safe(self) -> bool:
        return all(
            [
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
                not self.has_unsafe_content,
                not self.has_invalid_pair,
                not self.has_invalid_price,
                not self.has_invalid_date,
                not self.has_blocked_context,
                not self.has_missing_required_context,
                not self.has_inconsistent_state,
            ]
        )

    @property
    def safety_flags_ok(self) -> bool:
        return self.is_safe


@dataclass(frozen=True)
class BacktestDataQuality:
    """Data quality summary for the backtest report."""

    total_inputs: int
    included_count: int
    capped_count: int
    watchlist_count: int
    excluded_count: int
    insufficient_data_count: int
    blocked_count: int
    ready_price_history_count: int
    missing_price_history_count: int
    blocked_decision_count: int
    observation_count: int
    missing_data_count: int
    data_quality_score: float
    all_counts_consistent: bool
    safety_flags_ok: bool
    has_unsafe_content: bool

    def __post_init__(self) -> None:
        for name, value in (
            ("total_inputs", self.total_inputs),
            ("included_count", self.included_count),
            ("capped_count", self.capped_count),
            ("watchlist_count", self.watchlist_count),
            ("excluded_count", self.excluded_count),
            ("insufficient_data_count", self.insufficient_data_count),
            ("blocked_count", self.blocked_count),
            ("ready_price_history_count", self.ready_price_history_count),
            ("missing_price_history_count", self.missing_price_history_count),
            ("blocked_decision_count", self.blocked_decision_count),
            ("observation_count", self.observation_count),
            ("missing_data_count", self.missing_data_count),
        ):
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative int, got {value!r}")
        state_sum = (
            self.included_count
            + self.capped_count
            + self.watchlist_count
            + self.excluded_count
            + self.insufficient_data_count
            + self.blocked_count
        )
        if state_sum != self.total_inputs:
            raise ValueError(
                f"State counts must sum to total_inputs: {state_sum} != {self.total_inputs}"
            )
        _is_valid_finite_number(self.data_quality_score, "data_quality_score")
        if not 0.0 <= self.data_quality_score <= 100.0:
            raise ValueError(
                f"data_quality_score must be in [0, 100], got {self.data_quality_score}"
            )


@dataclass(frozen=True)
class BacktestReport:
    """Top-level backtest report."""

    version: str
    report_id: str
    generated_at: datetime
    inputs: tuple[BacktestInput, ...]
    config: BacktestRunConfig
    safety_flags: BacktestSafetyFlags
    candidate_results: tuple[BacktestCandidateResult, ...]
    portfolio_result: BacktestPortfolioResult
    data_quality: BacktestDataQuality
    reason_codes: tuple[str, ...]
    metadata: Mapping[str, str]
    notes: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "inputs", tuple(self.inputs))
        object.__setattr__(self, "candidate_results", tuple(self.candidate_results))
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))
        object.__setattr__(self, "notes", _coerce_tuple_strs(self.notes))
        for code in self.reason_codes:
            if code not in BACKTEST_REASON_CODES:
                raise ValueError(f"unsupported reason code: {code}")

    @staticmethod
    def blocked(
        *,
        reason_code: str,
        report_id: str = "blocked",
        generated_at: datetime | None = None,
        metadata: Mapping[str, str] | None = None,
    ) -> BacktestReport:
        """Return a fail-closed blocked report."""
        if reason_code not in BACKTEST_REASON_CODES:
            raise ValueError(f"unsupported reason code: {reason_code}")
        config = BacktestRunConfig()
        return BacktestReport(
            version=BACKTEST_VERSION,
            report_id=report_id,
            generated_at=generated_at or datetime.now(timezone.utc),
            inputs=(),
            config=config,
            safety_flags=BacktestSafetyFlags(
                has_unsafe_content=(reason_code == UNSAFE_BACKTEST_CONTENT),
                has_invalid_pair=(reason_code == INVALID_PAIR),
                has_invalid_price=(reason_code == INVALID_PRICE),
                has_invalid_date=(reason_code == INVALID_DATE),
                has_blocked_context=(reason_code == DISCOVERY_BLOCKED),
                no_network_connection=True,
                no_file_read_in_engine=True,
                no_action_commands=True,
            ),
            candidate_results=(),
            portfolio_result=BacktestPortfolioResult(
                total_return_pct=0.0,
                max_drawdown_pct=0.0,
                volatility_pct=0.0,
                win_rate_pct=0.0,
                observation_count=0,
                missing_data_count=0,
                insufficient_data_count=0,
                blocked_count=0,
                candidate_count=0,
                equity_curve=(),
                reason_codes=(reason_code,),
                metadata=_coerce_mapping_strs(metadata),
            ),
            data_quality=BacktestDataQuality(
                total_inputs=0,
                included_count=0,
                capped_count=0,
                watchlist_count=0,
                excluded_count=0,
                insufficient_data_count=0,
                blocked_count=0,
                ready_price_history_count=0,
                missing_price_history_count=0,
                blocked_decision_count=0,
                observation_count=0,
                missing_data_count=0,
                data_quality_score=0.0,
                all_counts_consistent=True,
                safety_flags_ok=False,
                has_unsafe_content=(reason_code == UNSAFE_BACKTEST_CONTENT),
            ),
            reason_codes=(reason_code,),
            metadata=_coerce_mapping_strs(metadata),
            notes=("Report blocked due to safety/config violation.",),
        )


def has_unsafe_backtest_content(
    pair: str,
    tags: Sequence[str],
    metadata: Mapping[str, str],
    forbidden_terms: frozenset[str] | None = None,
) -> bool:
    """Return True if any local string contains a forbidden term.

    Scans only the pair string, tag strings, and metadata keys/values provided
    by the caller. Metadata/file reference strings are opaque local strings only
    and are never opened, followed, traversed, validated, fetched, executed, or
    resolved.
    """
    terms = forbidden_terms or FORBIDDEN_BACKTEST_TERMS
    text_parts = [pair.lower()]
    text_parts.extend(t.lower() for t in tags)
    for k, v in metadata.items():
        text_parts.append(k.lower())
        text_parts.append(v.lower())
    for part in text_parts:
        for term in terms:
            if term in part:
                return True
    return False
