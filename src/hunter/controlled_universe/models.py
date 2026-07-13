"""Frozen dataclasses for hunter.controlled_universe package.

MVP-51 — Controlled Universe Bridge Engine.

All dataclasses are frozen. Validation runs in __post_init__.
Inputs are already-loaded local values only; the engine never opens files,
follows paths, validates paths, calls network endpoints, or accesses external
resources.

The Controlled Universe Bridge Engine consumes a macro execution context and a
per-coin portfolio construction report and produces a deterministic, fail-closed
controlled universe list. It is a human-audit / research-support artifact only.
It is not a trading signal, not trade approval, not strategy approval, not
execution approval, not portfolio approval, not universe approval, and not
Freqtrade input. It does not emit action commands, suggest orders, or create
execution instructions.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType

from hunter.execution.models import ExecutionContext, ExecutionState
from hunter.market_state.models import AllowedMode
from hunter.portfolio_construction.models import (
    PortfolioConstructionClassification,
    PortfolioConstructionReport,
    PortfolioConstructionState,
)


CONTROLLED_UNIVERSE_VERSION: str = "0.51.0-dev"


class ControlledUniverseState(Enum):
    """Controlled universe inclusion state for a single pair."""

    INCLUDED = "INCLUDED"
    WATCHLIST = "WATCHLIST"
    EXCLUDED = "EXCLUDED"
    BLOCKED = "BLOCKED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class ControlledUniverseClassification(Enum):
    """Research classification for a controlled universe item."""

    LONG_RESEARCH = "LONG_RESEARCH"
    SHORT_RESEARCH = "SHORT_RESEARCH"
    NEUTRAL_RESEARCH = "NEUTRAL_RESEARCH"
    BLOCKED_BY_MACRO = "BLOCKED_BY_MACRO"
    BLOCKED_BY_PORTFOLIO = "BLOCKED_BY_PORTFOLIO"
    WATCHLIST_RESEARCH = "WATCHLIST_RESEARCH"


# Reason code constants
INVALID_PAIR = "INVALID_PAIR"
DUPLICATE_PAIR_DETECTED = "DUPLICATE_PAIR_DETECTED"
MISSING_EXECUTION_CONTEXT = "MISSING_EXECUTION_CONTEXT"
EXECUTION_BLOCKED = "EXECUTION_BLOCKED"
EXECUTION_UNKNOWN = "EXECUTION_UNKNOWN"
MACRO_MODE_NONE = "MACRO_MODE_NONE"
MACRO_MODE_MISMATCH = "MACRO_MODE_MISMATCH"
TRANSITION_STATE = "TRANSITION_STATE"
MISSING_PORTFOLIO_CONTEXT = "MISSING_PORTFOLIO_CONTEXT"
INVALID_PORTFOLIO_SUMMARY = "INVALID_PORTFOLIO_SUMMARY"
PORTFOLIO_STATE_EXCLUDED = "PORTFOLIO_STATE_EXCLUDED"
PORTFOLIO_STATE_BLOCKED = "PORTFOLIO_STATE_BLOCKED"
PORTFOLIO_STATE_INSUFFICIENT_DATA = "PORTFOLIO_STATE_INSUFFICIENT_DATA"
PORTFOLIO_STATE_WATCHLIST = "PORTFOLIO_STATE_WATCHLIST"
LOW_PORTFOLIO_SCORE = "LOW_PORTFOLIO_SCORE"
MAX_UNIVERSE_PAIRS_EXCEEDED = "MAX_UNIVERSE_PAIRS_EXCEEDED"
PASSED_UNIVERSE_FILTER = "PASSED_UNIVERSE_FILTER"
HUMAN_RESEARCH_ONLY = "HUMAN_RESEARCH_ONLY"
NO_ACTION_COMMANDS_EMITTED = "NO_ACTION_COMMANDS_EMITTED"
NO_FILE_READ_IN_ENGINE = "NO_FILE_READ_IN_ENGINE"
NO_NETWORK_CONNECTION = "NO_NETWORK_CONNECTION"


CONTROLLED_UNIVERSE_BLOCKING_REASON_CODES: frozenset[str] = frozenset(
    {
        INVALID_PAIR,
        DUPLICATE_PAIR_DETECTED,
        MISSING_EXECUTION_CONTEXT,
        EXECUTION_BLOCKED,
        EXECUTION_UNKNOWN,
        MACRO_MODE_NONE,
        TRANSITION_STATE,
        MISSING_PORTFOLIO_CONTEXT,
        INVALID_PORTFOLIO_SUMMARY,
    }
)

CONTROLLED_UNIVERSE_FILTER_REASON_CODES: frozenset[str] = frozenset(
    {
        PORTFOLIO_STATE_EXCLUDED,
        PORTFOLIO_STATE_BLOCKED,
        PORTFOLIO_STATE_INSUFFICIENT_DATA,
        PORTFOLIO_STATE_WATCHLIST,
        LOW_PORTFOLIO_SCORE,
        MAX_UNIVERSE_PAIRS_EXCEEDED,
        MACRO_MODE_MISMATCH,
    }
)

CONTROLLED_UNIVERSE_ADVISORY_REASON_CODES: frozenset[str] = frozenset(
    {
        PASSED_UNIVERSE_FILTER,
        HUMAN_RESEARCH_ONLY,
        NO_ACTION_COMMANDS_EMITTED,
        NO_FILE_READ_IN_ENGINE,
        NO_NETWORK_CONNECTION,
    }
)

CONTROLLED_UNIVERSE_REASON_CODES: frozenset[str] = (
    CONTROLLED_UNIVERSE_BLOCKING_REASON_CODES
    | CONTROLLED_UNIVERSE_FILTER_REASON_CODES
    | CONTROLLED_UNIVERSE_ADVISORY_REASON_CODES
)


FORBIDDEN_CONTROLLED_UNIVERSE_TERMS: frozenset[str] = frozenset(
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
        "position_size",
        "position sizing",
        "position_sizing",
        "order_size",
        "order_sizing",
        "order_sizing",
        "trade_size",
        "trades",
        "trading",
        "trade",
        # Approval / portfolio action terms
        "portfolio_approval",
        "portfolio approval",
        "approve",
        "approval",
        "portfolio_rebalance",
        "portfolio rebalance",
        "rebalance",
        "rebalancing",
        "allocation_for_execution",
        "allocation for execution",
        "execution_ready",
        "execution ready",
        "execution_readiness",
        "universe_approval",
        "universe approval",
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
        "websocket",
        "web_socket",
        "live_data",
        "live data",
        "real_time",
        "realtime",
        "real_time_data",
        "market_data_feed",
        "tick_data",
        # Action commands
        "action_command",
        "action command",
        "emit",
        "signal",
        "signal_generator",
        "take_profit",
        "stop_loss",
        "entry",
        "exit",
        "entry_price",
        "exit_price",
        # Risky real-portfolio wording
        "deploy_capital",
        "deploy capital",
        "capital_allocation",
        "capital allocation",
        "position_management",
        "position management",
        "order_management",
        "order management",
    }
)


# Internal helpers


def _coerce_tuple_strs(value: Sequence[str] | None) -> tuple[str, ...]:
    if value is None:
        return ()
    return tuple(str(item) for item in value)


def _coerce_mapping_strs(value: Mapping[str, str] | None) -> Mapping[str, str]:
    if value is None:
        return MappingProxyType({})
    return MappingProxyType({str(k): str(v) for k, v in value.items()})


def _is_valid_score(value: float | None, name: str = "score") -> None:
    if value is None:
        return
    if not isinstance(value, (int, float)) or math.isinf(value) or math.isnan(value):
        raise ValueError(f"{name} must be a finite float, got {value!r}")
    if not 0.0 <= value <= 100.0:
        raise ValueError(f"{name} must be in [0, 100], got {value!r}")


def _is_valid_pair(value: str | None) -> None:
    if value is None or not isinstance(value, str) or not value.strip():
        raise ValueError("pair must be a non-empty string")


def _has_unsafe_content(value: str) -> bool:
    """Return True if value contains forbidden controlled-universe terms."""
    text = str(value).lower()
    return any(term in text for term in FORBIDDEN_CONTROLLED_UNIVERSE_TERMS)


@dataclass(frozen=True)
class ControlledUniverseConfig:
    """Configuration for the controlled universe bridge engine."""

    max_universe_pairs: int | None = None
    min_portfolio_score: float | None = None
    max_watchlist_pairs: int | None = None
    include_capped: bool = True
    default_mode: AllowedMode = AllowedMode.LONG_ONLY
    require_dry_run: bool = True

    def __post_init__(self) -> None:
        if self.require_dry_run is not True:
            raise ValueError("require_dry_run must be True for MVP-51")
        if self.max_universe_pairs is not None and (
            not isinstance(self.max_universe_pairs, int) or self.max_universe_pairs < 0
        ):
            raise ValueError(
                f"max_universe_pairs must be a non-negative int or None, got {self.max_universe_pairs!r}"
            )
        if self.max_watchlist_pairs is not None and (
            not isinstance(self.max_watchlist_pairs, int) or self.max_watchlist_pairs < 0
        ):
            raise ValueError(
                f"max_watchlist_pairs must be a non-negative int or None, got {self.max_watchlist_pairs!r}"
            )
        if self.min_portfolio_score is not None:
            _is_valid_score(self.min_portfolio_score, "min_portfolio_score")
        if not isinstance(self.default_mode, AllowedMode):
            raise ValueError(f"default_mode must be an AllowedMode, got {self.default_mode!r}")
        if not isinstance(self.include_capped, bool):
            raise ValueError(f"include_capped must be a bool, got {self.include_capped!r}")


@dataclass(frozen=True)
class ControlledUniverseSafetyFlags:
    """Safety flags for the controlled universe report."""

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
    has_duplicate_pair: bool = False
    has_blocked_execution: bool = False
    has_missing_execution_context: bool = False
    has_missing_portfolio_context: bool = False
    has_invalid_portfolio_summary: bool = False
    has_stale_or_invalid_data: bool = False

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
                not self.has_duplicate_pair,
                not self.has_blocked_execution,
                not self.has_missing_execution_context,
                not self.has_missing_portfolio_context,
                not self.has_invalid_portfolio_summary,
                not self.has_stale_or_invalid_data,
            ]
        )

    @property
    def safety_flags_ok(self) -> bool:
        return self.is_safe


@dataclass(frozen=True)
class ControlledUniverseDataQuality:
    """Data quality summary for the controlled universe report."""

    total_inputs: int = 0
    universe_count: int = 0
    watchlist_count: int = 0
    blocked_count: int = 0
    excluded_count: int = 0
    insufficient_data_count: int = 0
    execution_context_valid: bool = False
    portfolio_context_valid: bool = False
    data_quality_score: float = 0.0
    all_counts_consistent: bool = True
    safety_flags_ok: bool = False

    def __post_init__(self) -> None:
        for name, value in (
            ("total_inputs", self.total_inputs),
            ("universe_count", self.universe_count),
            ("watchlist_count", self.watchlist_count),
            ("blocked_count", self.blocked_count),
            ("excluded_count", self.excluded_count),
            ("insufficient_data_count", self.insufficient_data_count),
        ):
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative int, got {value!r}")
        if not isinstance(self.data_quality_score, (int, float)) or math.isinf(
            self.data_quality_score
        ) or math.isnan(self.data_quality_score):
            raise ValueError(
                f"data_quality_score must be a finite number, got {self.data_quality_score!r}"
            )
        if not 0.0 <= self.data_quality_score <= 100.0:
            raise ValueError(
                f"data_quality_score must be in [0, 100], got {self.data_quality_score}"
            )


@dataclass(frozen=True)
class ControlledUniverseItem:
    """A single pair's controlled universe classification."""

    pair: str
    state: ControlledUniverseState
    classification: ControlledUniverseClassification
    reason_codes: tuple[str, ...] = ()
    portfolio_score: float | None = None
    portfolio_state: str | None = None
    capped: bool = False

    def __post_init__(self) -> None:
        _is_valid_pair(self.pair)
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))
        if self.portfolio_score is not None:
            _is_valid_score(self.portfolio_score, "portfolio_score")
        if self.portfolio_state is not None and not isinstance(self.portfolio_state, str):
            raise ValueError(f"portfolio_state must be a string or None, got {self.portfolio_state!r}")


@dataclass(frozen=True)
class ControlledUniverseReport:
    """Top-level controlled universe report."""

    version: str
    generated_at: datetime
    config: ControlledUniverseConfig
    execution_state: str | None
    allowed_mode: str | None
    universe: tuple[str, ...]
    watchlist: tuple[str, ...]
    blocked: tuple[str, ...]
    items: tuple[ControlledUniverseItem, ...]
    data_quality: ControlledUniverseDataQuality
    safety_flags: ControlledUniverseSafetyFlags
    reason_codes: tuple[str, ...]
    metadata: Mapping[str, str] = field(default_factory=dict)
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "universe", tuple(self.universe))
        object.__setattr__(self, "watchlist", tuple(self.watchlist))
        object.__setattr__(self, "blocked", tuple(self.blocked))
        object.__setattr__(self, "items", tuple(self.items))
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))
        object.__setattr__(self, "notes", _coerce_tuple_strs(self.notes))
        for code in self.reason_codes:
            if code not in CONTROLLED_UNIVERSE_REASON_CODES:
                raise ValueError(f"unsupported reason code: {code}")
        # Validate that all pair references in universe/watchlist/blocked exist in items.
        item_pairs = {item.pair for item in self.items}
        for name, pairs in (
            ("universe", self.universe),
            ("watchlist", self.watchlist),
            ("blocked", self.blocked),
        ):
            for pair in pairs:
                if pair not in item_pairs:
                    raise ValueError(f"{name} contains pair {pair!r} not present in items")

    @classmethod
    def fail_closed(
        cls,
        *,
        reason_code: str,
        portfolio_report: PortfolioConstructionReport | None = None,
        execution_context: ExecutionContext | None = None,
        config: ControlledUniverseConfig | None = None,
        generated_at: datetime | None = None,
        metadata: Mapping[str, str] | None = None,
        notes: tuple[str, ...] | None = None,
    ) -> ControlledUniverseReport:
        """Return a fail-closed blocked report."""
        if reason_code not in CONTROLLED_UNIVERSE_REASON_CODES:
            raise ValueError(f"unsupported reason code: {reason_code}")
        config = config or ControlledUniverseConfig()
        execution_state = execution_context.execution_state.value if execution_context else None
        allowed_mode = execution_context.allowed_mode.value if execution_context else None
        safety_flags = ControlledUniverseSafetyFlags(
            has_blocked_execution=(reason_code in (EXECUTION_BLOCKED, EXECUTION_UNKNOWN)),
            has_missing_execution_context=(reason_code == MISSING_EXECUTION_CONTEXT),
            has_missing_portfolio_context=(reason_code == MISSING_PORTFOLIO_CONTEXT),
            has_invalid_portfolio_summary=(reason_code == INVALID_PORTFOLIO_SUMMARY),
            has_stale_or_invalid_data=(reason_code in (TRANSITION_STATE,)),
        )
        data_quality = ControlledUniverseDataQuality(
            total_inputs=len(portfolio_report.scores) if portfolio_report else 0,
            safety_flags_ok=safety_flags.is_safe,
        )
        reason_codes = (reason_code,) + (
            HUMAN_RESEARCH_ONLY,
            NO_ACTION_COMMANDS_EMITTED,
            NO_FILE_READ_IN_ENGINE,
            NO_NETWORK_CONNECTION,
        )
        return cls(
            version=CONTROLLED_UNIVERSE_VERSION,
            generated_at=generated_at or datetime.now(timezone.utc),
            config=config,
            execution_state=execution_state,
            allowed_mode=allowed_mode,
            universe=(),
            watchlist=(),
            blocked=(),
            items=(),
            data_quality=data_quality,
            safety_flags=safety_flags,
            reason_codes=reason_codes,
            metadata=_coerce_mapping_strs(metadata),
            notes=_coerce_tuple_strs(notes)
            or ("Report blocked due to safety/execution violation.",),
        )
