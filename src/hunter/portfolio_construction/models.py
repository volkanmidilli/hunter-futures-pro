"""Frozen dataclasses for hunter.portfolio_construction package.

MVP-27 — Portfolio Construction Engine.

All dataclasses are frozen. Validation runs in __post_init__.
Inputs are already-loaded local values only; the engine never opens files,
follows paths, validates paths, calls network endpoints, or accesses external
resources.

The portfolio construction engine is a human-audit / research-support artifact
only. It is not a trading signal, not trade approval, not strategy approval,
not execution approval, not portfolio approval, and not Freqtrade input. It does
not emit action commands, suggest orders, or create execution instructions.

Research weights produced by this engine are not orders, not position sizes,
not trade sizes, and not execution readiness indicators.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType


PORTFOLIO_CONSTRUCTION_VERSION: str = "0.27.0-dev"


class PortfolioConstructionState(Enum):
    INCLUDED = "INCLUDED"
    CAPPED = "CAPPED"
    WATCHLIST = "WATCHLIST"
    EXCLUDED = "EXCLUDED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    BLOCKED = "BLOCKED"


class PortfolioConstructionClassification(Enum):
    CORE_RESEARCH_ALLOCATION = "CORE_RESEARCH_ALLOCATION"
    SATELLITE_RESEARCH_ALLOCATION = "SATELLITE_RESEARCH_ALLOCATION"
    WATCHLIST_ALLOCATION = "WATCHLIST_ALLOCATION"
    EXCLUDED_BY_CONSTRAINTS = "EXCLUDED_BY_CONSTRAINTS"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    BLOCKED = "BLOCKED"


class PortfolioConstructionInputKind(Enum):
    SUMMARY = "SUMMARY"
    MANUAL = "MANUAL"
    RISK_CONTEXT = "RISK_CONTEXT"


# Reason code constants
INVALID_PAIR = "INVALID_PAIR"
INVALID_DISCOVERY_SCORE = "INVALID_DISCOVERY_SCORE"
INVALID_RESEARCH_WEIGHT = "INVALID_RESEARCH_WEIGHT"
UNSAFE_PORTFOLIO_CONSTRUCTION_CONTENT = "UNSAFE_PORTFOLIO_CONSTRUCTION_CONTENT"
MISSING_DISCOVERY_CONTEXT = "MISSING_DISCOVERY_CONTEXT"
DISCOVERY_BLOCKED = "DISCOVERY_BLOCKED"
DISCOVERY_INSUFFICIENT_DATA = "DISCOVERY_INSUFFICIENT_DATA"
LOW_DISCOVERY_SCORE = "LOW_DISCOVERY_SCORE"
MAX_CANDIDATE_COUNT_EXCEEDED = "MAX_CANDIDATE_COUNT_EXCEEDED"
MAX_SINGLE_WEIGHT_CAPPED = "MAX_SINGLE_WEIGHT_CAPPED"
ZERO_TOTAL_ALLOCATION_SCORE = "ZERO_TOTAL_ALLOCATION_SCORE"
INCLUDED_BY_RESEARCH_CONSTRAINTS = "INCLUDED_BY_RESEARCH_CONSTRAINTS"
CAPPED_BY_RESEARCH_CONSTRAINTS = "CAPPED_BY_RESEARCH_CONSTRAINTS"
EXCLUDED_BY_RESEARCH_CONSTRAINTS = "EXCLUDED_BY_RESEARCH_CONSTRAINTS"
HUMAN_RESEARCH_ONLY = "HUMAN_RESEARCH_ONLY"
NOT_PORTFOLIO_APPROVAL = "NOT_PORTFOLIO_APPROVAL"
NOT_POSITION_SIZING = "NOT_POSITION_SIZING"
NO_NETWORK_CONNECTION = "NO_NETWORK_CONNECTION"
NO_FILE_READ_IN_ENGINE = "NO_FILE_READ_IN_ENGINE"
NO_ACTION_COMMANDS_EMITTED = "NO_ACTION_COMMANDS_EMITTED"

PORTFOLIO_CONSTRUCTION_BLOCKING_REASON_CODES: frozenset[str] = frozenset(
    {
        INVALID_PAIR,
        INVALID_DISCOVERY_SCORE,
        INVALID_RESEARCH_WEIGHT,
        UNSAFE_PORTFOLIO_CONSTRUCTION_CONTENT,
        DISCOVERY_BLOCKED,
    }
)

PORTFOLIO_CONSTRUCTION_INSUFFICIENT_DATA_REASON_CODES: frozenset[str] = frozenset(
    {
        MISSING_DISCOVERY_CONTEXT,
        DISCOVERY_INSUFFICIENT_DATA,
    }
)

PORTFOLIO_CONSTRUCTION_FILTER_REASON_CODES: frozenset[str] = frozenset(
    {
        LOW_DISCOVERY_SCORE,
        MAX_CANDIDATE_COUNT_EXCEEDED,
        MAX_SINGLE_WEIGHT_CAPPED,
        ZERO_TOTAL_ALLOCATION_SCORE,
        INCLUDED_BY_RESEARCH_CONSTRAINTS,
        CAPPED_BY_RESEARCH_CONSTRAINTS,
        EXCLUDED_BY_RESEARCH_CONSTRAINTS,
    }
)

PORTFOLIO_CONSTRUCTION_ADVISORY_REASON_CODES: frozenset[str] = frozenset(
    {
        HUMAN_RESEARCH_ONLY,
        NOT_PORTFOLIO_APPROVAL,
        NOT_POSITION_SIZING,
        NO_NETWORK_CONNECTION,
        NO_FILE_READ_IN_ENGINE,
        NO_ACTION_COMMANDS_EMITTED,
    }
)

PORTFOLIO_CONSTRUCTION_REASON_CODES: frozenset[str] = (
    PORTFOLIO_CONSTRUCTION_BLOCKING_REASON_CODES
    | PORTFOLIO_CONSTRUCTION_INSUFFICIENT_DATA_REASON_CODES
    | PORTFOLIO_CONSTRUCTION_FILTER_REASON_CODES
    | PORTFOLIO_CONSTRUCTION_ADVISORY_REASON_CODES
)


FORBIDDEN_PORTFOLIO_CONSTRUCTION_TERMS: frozenset[str] = frozenset(
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


def _round_value(value: float, decimals: int) -> float:
    return round(value, decimals)


def _is_valid_score(value: float | None, name: str = "score") -> None:
    if value is None:
        return
    if not isinstance(value, (int, float)) or math.isinf(value) or math.isnan(value):
        raise ValueError(f"{name} must be a finite float, got {value!r}")
    if not 0.0 <= value <= 100.0:
        raise ValueError(f"{name} must be in [0, 100], got {value!r}")


def _is_valid_finite_number(value: float | None, name: str = "value") -> None:
    if value is None:
        return
    if not isinstance(value, (int, float)) or math.isinf(value) or math.isnan(value):
        raise ValueError(f"{name} must be a finite number, got {value!r}")


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


def _validate_thresholds(config: PortfolioConstructionConfig) -> None:
    """Validate config thresholds and caps."""
    for name, value in (
        ("min_discovery_score", config.min_discovery_score),
        ("watchlist_score", config.watchlist_score),
        ("core_allocation_score", config.core_allocation_score),
        ("satellite_allocation_score", config.satellite_allocation_score),
        ("max_single_weight_pct", config.max_single_weight_pct),
        ("total_research_weight_pct", config.total_research_weight_pct),
    ):
        _is_valid_finite_number(value, name)
    if not 0.0 <= config.min_discovery_score <= 100.0:
        raise ValueError("min_discovery_score must be in [0, 100]")
    if not 0.0 <= config.watchlist_score <= 100.0:
        raise ValueError("watchlist_score must be in [0, 100]")
    if not 0.0 <= config.core_allocation_score <= 100.0:
        raise ValueError("core_allocation_score must be in [0, 100]")
    if not 0.0 <= config.satellite_allocation_score <= 100.0:
        raise ValueError("satellite_allocation_score must be in [0, 100]")
    if not (
        config.core_allocation_score
        > config.satellite_allocation_score
        > config.watchlist_score
    ):
        raise ValueError(
            "core_allocation_score > satellite_allocation_score > watchlist_score must hold"
        )
    if not isinstance(config.max_candidate_count, int) or config.max_candidate_count < 0:
        raise ValueError("max_candidate_count must be a non-negative int")
    if not 0.0 <= config.max_single_weight_pct <= 100.0:
        raise ValueError("max_single_weight_pct must be in [0, 100]")
    if not 0.0 < config.total_research_weight_pct <= 100.0:
        raise ValueError("total_research_weight_pct must be in (0, 100]")

    # score_weights validation
    required_keys = {
        "discovery_score_component",
        "data_quality_score",
        "diversification_component",
        "cap_readiness_score",
        "filter_bonus_score",
    }
    if set(config.score_weights.keys()) != required_keys:
        raise ValueError(f"score_weights must have exactly the keys {required_keys}")
    for name, weight in config.score_weights.items():
        if not isinstance(weight, (int, float)) or math.isinf(weight) or math.isnan(weight):
            raise ValueError(f"score_weights['{name}'] must be a finite number")
        if weight < 0.0:
            raise ValueError(f"score_weights['{name}'] must be non-negative")
    total = sum(config.score_weights.values())
    if abs(total - 1.0) > 1e-9:
        raise ValueError(f"score_weights must sum to 1.0, got {total}")


@dataclass(frozen=True)
class PortfolioDiscoverySummary:
    """Discovery context summary passed into portfolio construction."""

    pair: str
    state: str
    classification: str
    discovery_score: float | None
    reason_codes: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.pair, str) or not self.pair.strip():
            raise ValueError("pair must be a non-empty string")
        _is_valid_score(self.discovery_score, "discovery_score")
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))
        object.__setattr__(self, "tags", _coerce_tuple_strs(self.tags))
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))


@dataclass(frozen=True)
class PortfolioConstructionInput:
    """Single pair input for portfolio construction."""

    pair: str
    discovery: PortfolioDiscoverySummary | None = None
    input_kind: PortfolioConstructionInputKind = PortfolioConstructionInputKind.SUMMARY
    tags: tuple[str, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.pair, str) or not self.pair.strip():
            raise ValueError("pair must be a non-empty string")
        if self.discovery is not None and self.discovery.pair != self.pair:
            raise ValueError("discovery.pair must match PortfolioConstructionInput.pair")
        object.__setattr__(self, "tags", _coerce_tuple_strs(self.tags))
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))


@dataclass(frozen=True)
class PortfolioConstructionConfig:
    """Configuration for portfolio construction scoring and weights."""

    require_discovery_context: bool = True
    block_on_blocked_context: bool = True
    block_on_missing_context: bool = False
    include_excluded_candidates: bool = True
    block_duplicate_tags: bool = False
    min_discovery_score: float = 60.0
    watchlist_score: float = 45.0
    core_allocation_score: float = 75.0
    satellite_allocation_score: float = 60.0
    max_candidate_count: int = 10
    max_single_weight_pct: float = 20.0
    total_research_weight_pct: float = 100.0
    score_weights: Mapping[str, float] = field(
        default_factory=lambda: {
            "discovery_score_component": 0.45,
            "data_quality_score": 0.15,
            "diversification_component": 0.15,
            "cap_readiness_score": 0.15,
            "filter_bonus_score": 0.10,
        }
    )

    def __post_init__(self) -> None:
        # Preserve numeric values for score_weights; do not coerce to strings.
        object.__setattr__(self, "score_weights", MappingProxyType(dict(self.score_weights)))
        _validate_thresholds(self)


@dataclass(frozen=True)
class PortfolioConstructionSafetyFlags:
    """Safety flags that must all hold for the engine to produce a report."""

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
    has_invalid_score: bool = False
    has_blocked_context: bool = False
    has_missing_required_context: bool = False
    has_inconsistent_state: bool = False
    has_duplicate_tags: bool = False

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
                not self.has_invalid_score,
                not self.has_blocked_context,
                not self.has_missing_required_context,
                not self.has_inconsistent_state,
                not self.has_duplicate_tags,
            ]
        )

    @property
    def safety_flags_ok(self) -> bool:
        return self.is_safe


@dataclass(frozen=True)
class PortfolioConstructionDataQuality:
    """Data quality summary for the portfolio construction report."""

    total_inputs: int
    included_count: int
    capped_count: int
    watchlist_count: int
    excluded_count: int
    insufficient_data_count: int
    blocked_count: int
    ready_context_count: int
    missing_context_count: int
    blocked_context_count: int
    total_final_weight_pct: float
    total_research_weight_pct: float
    data_quality_score: float
    sections_present: int
    all_sections_present: bool
    all_counts_consistent: bool
    total_weight_within_tolerance: bool
    has_unsafe_content: bool
    safety_flags_ok: bool
    stale: bool = False

    def __post_init__(self) -> None:
        for name, value in (
            ("total_inputs", self.total_inputs),
            ("included_count", self.included_count),
            ("capped_count", self.capped_count),
            ("watchlist_count", self.watchlist_count),
            ("excluded_count", self.excluded_count),
            ("insufficient_data_count", self.insufficient_data_count),
            ("blocked_count", self.blocked_count),
            ("ready_context_count", self.ready_context_count),
            ("missing_context_count", self.missing_context_count),
            ("blocked_context_count", self.blocked_context_count),
            ("sections_present", self.sections_present),
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
        for name, value in (
            ("total_final_weight_pct", self.total_final_weight_pct),
            ("total_research_weight_pct", self.total_research_weight_pct),
            ("data_quality_score", self.data_quality_score),
        ):
            _is_valid_finite_number(value, name)
        if not 0.0 <= self.total_final_weight_pct <= self.total_research_weight_pct + 1e-9:
            raise ValueError(
                f"total_final_weight_pct must be in [0, total_research_weight_pct], "
                f"got {self.total_final_weight_pct}"
            )
        if not 0.0 <= self.data_quality_score <= 100.0:
            raise ValueError(
                f"data_quality_score must be in [0, 100], got {self.data_quality_score}"
            )


@dataclass(frozen=True)
class PortfolioConstructionScore:
    """A single scored portfolio construction candidate."""

    pair: str
    state: PortfolioConstructionState
    classification: PortfolioConstructionClassification
    allocation_score: float
    discovery_score_component: float
    data_quality_score: float
    diversification_component: float
    cap_readiness_score: float
    filter_bonus_score: float
    initial_research_weight_pct: float
    capped_weight_pct: float
    final_weight_pct: float
    reason_codes: tuple[str, ...]
    tags: tuple[str, ...]
    metadata: Mapping[str, str]
    notes: tuple[str, ...]
    rank: int | None

    def __post_init__(self) -> None:
        for name in (
            "allocation_score",
            "discovery_score_component",
            "data_quality_score",
            "diversification_component",
            "cap_readiness_score",
            "filter_bonus_score",
        ):
            _is_valid_score(getattr(self, name), name)
        for name in (
            "initial_research_weight_pct",
            "capped_weight_pct",
            "final_weight_pct",
        ):
            value = getattr(self, name)
            _is_valid_finite_number(value, name)
            if value < 0.0 or value > 100.0 + 1e-9:
                raise ValueError(f"{name} must be in [0, 100], got {value!r}")
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))
        object.__setattr__(self, "tags", _coerce_tuple_strs(self.tags))
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))
        object.__setattr__(self, "notes", _coerce_tuple_strs(self.notes))


@dataclass(frozen=True)
class PortfolioConstructionUniverseSummary:
    """Summary counts over the portfolio construction universe."""

    total_candidates: int
    included_count: int
    capped_count: int
    watchlist_count: int
    excluded_count: int
    insufficient_data_count: int
    blocked_count: int
    core_allocation_count: int
    satellite_allocation_count: int
    watchlist_allocation_count: int
    total_final_weight_pct: float
    top_pair: str | None
    notes: tuple[str, ...]

    def __post_init__(self) -> None:
        for name, value in (
            ("total_candidates", self.total_candidates),
            ("included_count", self.included_count),
            ("capped_count", self.capped_count),
            ("watchlist_count", self.watchlist_count),
            ("excluded_count", self.excluded_count),
            ("insufficient_data_count", self.insufficient_data_count),
            ("blocked_count", self.blocked_count),
            ("core_allocation_count", self.core_allocation_count),
            ("satellite_allocation_count", self.satellite_allocation_count),
            ("watchlist_allocation_count", self.watchlist_allocation_count),
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
        if state_sum != self.total_candidates:
            raise ValueError(
                f"State counts must sum to total_candidates: {state_sum} != {self.total_candidates}"
            )
        _is_valid_finite_number(self.total_final_weight_pct, "total_final_weight_pct")
        if self.total_final_weight_pct < 0.0 or self.total_final_weight_pct > 100.0 + 1e-9:
            raise ValueError(
                f"total_final_weight_pct must be in [0, 100], got {self.total_final_weight_pct}"
            )
        object.__setattr__(self, "notes", _coerce_tuple_strs(self.notes))


@dataclass(frozen=True)
class PortfolioConstructionReport:
    """Top-level portfolio construction report."""

    version: str
    report_id: str
    generated_at: datetime
    inputs: tuple[PortfolioConstructionInput, ...]
    config: PortfolioConstructionConfig
    safety_flags: PortfolioConstructionSafetyFlags
    scores: tuple[PortfolioConstructionScore, ...]
    universe_summary: PortfolioConstructionUniverseSummary
    data_quality: PortfolioConstructionDataQuality
    reason_codes: tuple[str, ...]
    metadata: Mapping[str, str]
    notes: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "inputs", tuple(self.inputs))
        object.__setattr__(self, "scores", tuple(self.scores))
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))
        object.__setattr__(self, "notes", _coerce_tuple_strs(self.notes))
        for code in self.reason_codes:
            if code not in PORTFOLIO_CONSTRUCTION_REASON_CODES:
                raise ValueError(f"unsupported reason code: {code}")

    @staticmethod
    def blocked(
        *,
        reason_code: str,
        report_id: str = "blocked",
        generated_at: datetime | None = None,
        metadata: Mapping[str, str] | None = None,
    ) -> PortfolioConstructionReport:
        """Return a fail-closed blocked report."""
        if reason_code not in PORTFOLIO_CONSTRUCTION_REASON_CODES:
            raise ValueError(f"unsupported reason code: {reason_code}")
        config = PortfolioConstructionConfig()
        total_research_weight_pct = config.total_research_weight_pct
        return PortfolioConstructionReport(
            version=PORTFOLIO_CONSTRUCTION_VERSION,
            report_id=report_id,
            generated_at=generated_at or datetime.now(timezone.utc),
            inputs=(),
            config=config,
            safety_flags=PortfolioConstructionSafetyFlags(
                has_unsafe_content=(reason_code == UNSAFE_PORTFOLIO_CONSTRUCTION_CONTENT),
                has_invalid_pair=(reason_code == INVALID_PAIR),
                has_invalid_score=(reason_code == INVALID_DISCOVERY_SCORE),
                has_blocked_context=(reason_code == DISCOVERY_BLOCKED),
                no_network_connection=True,
                no_file_read_in_engine=True,
                no_action_commands=True,
            ),
            scores=(),
            universe_summary=PortfolioConstructionUniverseSummary(
                total_candidates=0,
                included_count=0,
                capped_count=0,
                watchlist_count=0,
                excluded_count=0,
                insufficient_data_count=0,
                blocked_count=0,
                core_allocation_count=0,
                satellite_allocation_count=0,
                watchlist_allocation_count=0,
                total_final_weight_pct=0.0,
                top_pair=None,
                notes=(),
            ),
            data_quality=PortfolioConstructionDataQuality(
                total_inputs=0,
                included_count=0,
                capped_count=0,
                watchlist_count=0,
                excluded_count=0,
                insufficient_data_count=0,
                blocked_count=0,
                ready_context_count=0,
                missing_context_count=0,
                blocked_context_count=0,
                total_final_weight_pct=0.0,
                total_research_weight_pct=total_research_weight_pct,
                data_quality_score=0.0,
                sections_present=0,
                all_sections_present=False,
                all_counts_consistent=True,
                total_weight_within_tolerance=True,
                has_unsafe_content=(reason_code == UNSAFE_PORTFOLIO_CONSTRUCTION_CONTENT),
                safety_flags_ok=False,
            ),
            reason_codes=(reason_code,),
            metadata=_coerce_mapping_strs(metadata),
            notes=("Report blocked due to safety/config violation.",),
        )
