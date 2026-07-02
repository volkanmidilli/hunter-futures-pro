"""Frozen dataclasses for hunter.open_interest package.

MVP-25 — Open Interest Engine.

All dataclasses are frozen. Validation runs in __post_init__.
Inputs are already-loaded local values only; the engine never opens files,
follows paths, validates paths, calls network endpoints, or accesses external
resources.

The open interest engine is a human-audit / research-support artifact only.
It is not a trading signal, not trade approval, not strategy approval, not
execution approval, not portfolio/universe approval, and not Freqtrade input.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any

OPEN_INTEREST_VERSION = "1.0"


class OpenInterestState(Enum):
    """Overall state of a single open interest score or report."""

    READY = "ready"
    INSUFFICIENT_DATA = "insufficient_data"
    BLOCKED = "blocked"


class OpenInterestPositioning(Enum):
    """Combined price + open interest positioning classification."""

    PRICE_UP_OI_UP = "price_up_oi_up"
    PRICE_UP_OI_DOWN = "price_up_oi_down"
    PRICE_DOWN_OI_UP = "price_down_oi_up"
    PRICE_DOWN_OI_DOWN = "price_down_oi_down"
    MIXED = "mixed"
    INSUFFICIENT_DATA = "insufficient_data"
    BLOCKED = "blocked"


class OpenInterestTrend(Enum):
    """Open interest trend classification across available windows."""

    EXPANDING = "expanding"
    CONTRACTING = "contracting"
    FLAT = "flat"
    UNSTABLE = "unstable"
    INSUFFICIENT_DATA = "insufficient_data"
    BLOCKED = "blocked"


class OpenInterestFundingContext(Enum):
    """Funding-like context classification."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    MISSING = "missing"
    INSUFFICIENT_DATA = "insufficient_data"
    BLOCKED = "blocked"


# ---------------------------------------------------------------------------
# Reason codes — deterministic, priority-ordered constants.
# ---------------------------------------------------------------------------

INVALID_PAIR = "INVALID_PAIR"
INVALID_TIMESTAMP = "INVALID_TIMESTAMP"
INVALID_OPEN_INTEREST = "INVALID_OPEN_INTEREST"
INVALID_PRICE_DATA = "INVALID_PRICE_DATA"
INSUFFICIENT_OI_DATA = "INSUFFICIENT_OI_DATA"
ZERO_DENOMINATOR = "ZERO_DENOMINATOR"
UNSAFE_OPEN_INTEREST_CONTENT = "UNSAFE_OPEN_INTEREST_CONTENT"
BLOCKED_BY_SAFETY_FLAGS = "BLOCKED_BY_SAFETY_FLAGS"

PERIOD_DATA_MISSING = "PERIOD_DATA_MISSING"
FUNDING_CONTEXT_MISSING = "FUNDING_CONTEXT_MISSING"

INPUTS_ALREADY_LOADED = "INPUTS_ALREADY_LOADED"
NO_ACTION_COMMANDS_EMITTED = "NO_ACTION_COMMANDS_EMITTED"
HUMAN_RESEARCH_ONLY = "HUMAN_RESEARCH_ONLY"
NO_NETWORK_CONNECTION = "NO_NETWORK_CONNECTION"
NO_DATABASE_CONNECTION = "NO_DATABASE_CONNECTION"
NO_FILE_READ_IN_ENGINE = "NO_FILE_READ_IN_ENGINE"

OPEN_INTEREST_BLOCKING_REASON_CODES: tuple[str, ...] = (
    INVALID_PAIR,
    INVALID_TIMESTAMP,
    INVALID_OPEN_INTEREST,
    INVALID_PRICE_DATA,
    INSUFFICIENT_OI_DATA,
    ZERO_DENOMINATOR,
    UNSAFE_OPEN_INTEREST_CONTENT,
    BLOCKED_BY_SAFETY_FLAGS,
)

OPEN_INTEREST_INSUFFICIENT_DATA_REASON_CODES: tuple[str, ...] = (
    INSUFFICIENT_OI_DATA,
    PERIOD_DATA_MISSING,
    FUNDING_CONTEXT_MISSING,
)

OPEN_INTEREST_ADVISORY_REASON_CODES: tuple[str, ...] = (
    INPUTS_ALREADY_LOADED,
    NO_ACTION_COMMANDS_EMITTED,
    HUMAN_RESEARCH_ONLY,
    NO_NETWORK_CONNECTION,
    NO_DATABASE_CONNECTION,
    NO_FILE_READ_IN_ENGINE,
)

OPEN_INTEREST_REASON_CODES: tuple[str, ...] = tuple(
    dict.fromkeys(
        OPEN_INTEREST_BLOCKING_REASON_CODES
        + OPEN_INTEREST_INSUFFICIENT_DATA_REASON_CODES
        + OPEN_INTEREST_ADVISORY_REASON_CODES
    ).keys()
)


# ---------------------------------------------------------------------------
# Forbidden terms — matches SPEC-026 list.
# ---------------------------------------------------------------------------

FORBIDDEN_OPEN_INTEREST_TERMS: frozenset[str] = frozenset({
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
        if code not in OPEN_INTEREST_REASON_CODES:
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


def _is_number(value: Any) -> bool:
    """Return True if value is a finite int or float."""
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


# ---------------------------------------------------------------------------
# Model dataclasses.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OpenInterestObservation:
    """A single OI/price observation row."""

    timestamp: datetime
    open_interest: float
    close: float
    funding_rate: float | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # timestamp must be timezone-aware datetime
        if not isinstance(self.timestamp, datetime) or self.timestamp.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        # open_interest must be finite and non-negative
        if not _is_number(self.open_interest) or self.open_interest < 0:
            raise ValueError("open_interest must be finite and >= 0")
        # close must be finite and positive
        if not _is_number(self.close) or self.close <= 0:
            raise ValueError("close must be finite and > 0")
        # funding_rate must be finite if present
        if self.funding_rate is not None and not _is_number(self.funding_rate):
            raise ValueError("funding_rate must be finite if present")
        # metadata is opaque local strings only; coerce to MappingProxyType
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True)
class OpenInterestInput:
    """A single pair with its already-loaded OI observation sequence."""

    pair: str
    rows: Sequence[OpenInterestObservation]
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.pair, str) or not self.pair:
            raise ValueError("pair must be non-empty")
        if not isinstance(self.rows, (tuple, list)):
            raise ValueError("rows must be a tuple or list")
        for row in self.rows:
            if not isinstance(row, OpenInterestObservation):
                raise ValueError("rows must contain OpenInterestObservation values")
        # rows normalized to tuple
        object.__setattr__(self, "rows", tuple(self.rows))
        # metadata copied/immutable; no file/path behavior
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True)
class OpenInterestConfig:
    """Configuration for the open interest engine."""

    lookback_periods: tuple[int, ...] = (1, 3, 7, 14)
    positioning_threshold: float = 0.001
    oi_change_bounds: tuple[float, float] = (-0.30, 0.30)
    price_change_bounds: tuple[float, float] = (-0.20, 0.20)
    funding_rate_bounds: tuple[float, float] = (-0.01, 0.01)
    min_required_rows: int = 15
    block_on_missing_data: bool = False
    score_weights: Mapping[str, float] = field(
        default_factory=lambda: MappingProxyType({
            "oi_7d_change": 0.30,
            "oi_14d_change": 0.20,
            "price_oi_alignment": 0.20,
            "oi_trend_stability": 0.15,
            "funding_context": 0.05,
            "data_quality": 0.10,
        })
    )
    rounding_policy: str = "standard"
    version: str = OPEN_INTEREST_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.version, str) or not self.version:
            raise ValueError("version must be non-empty")
        if any(not isinstance(d, int) or d <= 0 for d in self.lookback_periods):
            raise ValueError("lookback_periods must be positive integers")
        if not _is_number(self.positioning_threshold) or self.positioning_threshold < 0:
            raise ValueError("positioning_threshold must be non-negative")
        if (
            not isinstance(self.oi_change_bounds, (tuple, list))
            or len(self.oi_change_bounds) != 2
            or not all(_is_number(v) for v in self.oi_change_bounds)
            or self.oi_change_bounds[0] >= self.oi_change_bounds[1]
        ):
            raise ValueError("oi_change_bounds must be a tuple of two finite numbers with lower < upper")
        if (
            not isinstance(self.price_change_bounds, (tuple, list))
            or len(self.price_change_bounds) != 2
            or not all(_is_number(v) for v in self.price_change_bounds)
            or self.price_change_bounds[0] >= self.price_change_bounds[1]
        ):
            raise ValueError("price_change_bounds must be a tuple of two finite numbers with lower < upper")
        if (
            not isinstance(self.funding_rate_bounds, (tuple, list))
            or len(self.funding_rate_bounds) != 2
            or not all(_is_number(v) for v in self.funding_rate_bounds)
            or self.funding_rate_bounds[0] >= self.funding_rate_bounds[1]
        ):
            raise ValueError("funding_rate_bounds must be a tuple of two finite numbers with lower < upper")
        if not isinstance(self.min_required_rows, int) or self.min_required_rows < 1:
            raise ValueError("min_required_rows must be at least 1")
        if not isinstance(self.score_weights, Mapping):
            raise ValueError("score_weights must be a mapping")
        if not (-1e-9 <= sum(self.score_weights.values()) - 1.0 <= 1e-9):
            raise ValueError("score_weights must sum to 1.0")
        for key in self.score_weights:
            if not isinstance(key, str) or not key:
                raise ValueError("score_weights keys must be non-empty strings")
        if not isinstance(self.rounding_policy, str) or not self.rounding_policy:
            raise ValueError("rounding_policy must be non-empty")


@dataclass(frozen=True)
class OpenInterestSafetyFlags:
    """Safety invariants for the open interest engine."""

    # Output safety flags (must be True)
    human_research_only: bool = True
    output_is_human_research_only: bool = True
    output_not_trading_signal: bool = True
    output_not_trade_approval: bool = True
    output_not_strategy_approval: bool = True
    output_not_execution_approval: bool = True
    output_not_portfolio_approval: bool = True
    output_not_universe_approval: bool = True
    output_not_freqtrade_input: bool = True
    output_not_order_input: bool = True
    output_not_exchange_input: bool = True
    no_action_commands_emitted: bool = True
    inputs_already_loaded: bool = True
    benchmarks_provided_by_caller: bool = True

    # Capability flags (must be False)
    file_write_enabled: bool = False
    file_read_enabled: bool = False
    network_enabled: bool = False
    database_enabled: bool = False
    event_store_enabled: bool = False
    runtime_registry_enabled: bool = False
    task_runner_enabled: bool = False
    indexer_crawler_enabled: bool = False
    feedback_into_execution: bool = False
    feedback_into_strategy: bool = False
    feedback_into_portfolio: bool = False
    feedback_into_freqtrade: bool = False
    leverage_enabled: bool = False
    shorting_enabled: bool = False
    real_orders_enabled: bool = False
    live_trading_enabled: bool = False

    def __post_init__(self) -> None:
        unsafe_flags = (
            self.file_write_enabled,
            self.file_read_enabled,
            self.network_enabled,
            self.database_enabled,
            self.event_store_enabled,
            self.runtime_registry_enabled,
            self.task_runner_enabled,
            self.indexer_crawler_enabled,
            self.feedback_into_execution,
            self.feedback_into_strategy,
            self.feedback_into_portfolio,
            self.feedback_into_freqtrade,
            self.leverage_enabled,
            self.shorting_enabled,
            self.real_orders_enabled,
            self.live_trading_enabled,
        )
        if any(unsafe_flags):
            raise ValueError("unsafe open interest safety flags are enabled")
        safe_flags = (
            self.human_research_only,
            self.output_is_human_research_only,
            self.output_not_trading_signal,
            self.output_not_trade_approval,
            self.output_not_strategy_approval,
            self.output_not_execution_approval,
            self.output_not_portfolio_approval,
            self.output_not_universe_approval,
            self.output_not_freqtrade_input,
            self.output_not_order_input,
            self.output_not_exchange_input,
            self.no_action_commands_emitted,
            self.inputs_already_loaded,
            self.benchmarks_provided_by_caller,
        )
        if not all(safe_flags):
            raise ValueError("safe open interest output flags must be True")


@dataclass(frozen=True)
class OpenInterestDataQuality:
    """Completeness and quality metrics for one pair or the whole universe."""

    expected_rows: int
    actual_rows: int
    missing_rows: int
    min_required_rows_met: bool
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
        if not isinstance(self.stale_input_count, int) or self.stale_input_count < 0:
            raise ValueError("stale_input_count must be non-negative")
        reason_codes = _ensure_tuple_of_str(self.reason_codes, "reason_codes")
        _validate_reason_codes(reason_codes)
        object.__setattr__(self, "reason_codes", reason_codes)


@dataclass(frozen=True)
class OpenInterestPeriodChange:
    """A single period change for a pair."""

    period: int
    oi_change: float | None
    price_change: float | None
    has_data: bool
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.period, int) or self.period <= 0:
            raise ValueError("period must be a positive integer")
        reason_codes = _ensure_tuple_of_str(self.reason_codes, "reason_codes")
        _validate_reason_codes(reason_codes)
        object.__setattr__(self, "reason_codes", reason_codes)


@dataclass(frozen=True)
class OpenInterestScore:
    """Open interest score for a single pair."""

    pair: str
    state: OpenInterestState
    positioning: OpenInterestPositioning
    trend: OpenInterestTrend
    funding_context: OpenInterestFundingContext
    total_score: float
    period_changes: tuple[OpenInterestPeriodChange, ...]
    latest_oi: float | None
    latest_price: float | None
    latest_funding_rate: float | None
    sub_scores: Mapping[str, float]
    data_quality: OpenInterestDataQuality
    human_note: str
    reason_codes: tuple[str, ...]
    metadata: Mapping[str, str]

    def __post_init__(self) -> None:
        if not isinstance(self.pair, str) or not self.pair:
            raise ValueError("pair must be non-empty")
        if not isinstance(self.total_score, (int, float)) or not (0.0 <= self.total_score <= 100.0):
            raise ValueError("total_score must be in [0, 100]")
        if not isinstance(self.human_note, str):
            raise ValueError("human_note must be a string")
        if not isinstance(self.period_changes, (tuple, list)):
            raise ValueError("period_changes must be a tuple or list")
        for item in self.period_changes:
            if not isinstance(item, OpenInterestPeriodChange):
                raise ValueError("period_changes must contain OpenInterestPeriodChange values")
        period_changes = tuple(self.period_changes)
        sub_scores = _coerce_sub_scores(self.sub_scores)
        for key, value in sub_scores.items():
            if not isinstance(key, str) or not key:
                raise ValueError("sub_scores keys must be non-empty strings")
            if not isinstance(value, (int, float)) or not (0.0 <= value <= 100.0):
                raise ValueError("sub_scores values must be in [0, 100]")
        metadata = _coerce_mapping(self.metadata)
        reason_codes = _ensure_tuple_of_str(self.reason_codes, "reason_codes")
        _validate_reason_codes(reason_codes)
        object.__setattr__(self, "period_changes", period_changes)
        object.__setattr__(self, "sub_scores", sub_scores)
        object.__setattr__(self, "metadata", metadata)
        object.__setattr__(self, "reason_codes", reason_codes)


@dataclass(frozen=True)
class OpenInterestUniverseSummary:
    """Aggregated summary over the scored universe."""

    total_pairs: int
    ready_count: int
    insufficient_data_count: int
    blocked_count: int
    expanding_count: int
    contracting_count: int
    flat_count: int
    unstable_count: int
    price_up_oi_up_count: int
    price_up_oi_down_count: int
    price_down_oi_up_count: int
    price_down_oi_down_count: int
    mixed_count: int
    average_total_score: float | None
    top_expanding_pair: str | None
    top_contracting_pair: str | None
    data_quality: OpenInterestDataQuality
    summary_narrative: str
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        for field_name in (
            "total_pairs",
            "ready_count",
            "insufficient_data_count",
            "blocked_count",
            "expanding_count",
            "contracting_count",
            "flat_count",
            "unstable_count",
            "price_up_oi_up_count",
            "price_up_oi_down_count",
            "price_down_oi_up_count",
            "price_down_oi_down_count",
            "mixed_count",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer")
        if (
            self.ready_count
            + self.insufficient_data_count
            + self.blocked_count
            != self.total_pairs
        ):
            raise ValueError("state counts must sum to total_pairs")
        if self.average_total_score is not None and (
            not isinstance(self.average_total_score, (int, float))
            or not (0.0 <= self.average_total_score <= 100.0)
        ):
            raise ValueError("average_total_score must be in [0, 100] or None")
        if not isinstance(self.summary_narrative, str):
            raise ValueError("summary_narrative must be a string")
        reason_codes = _ensure_tuple_of_str(self.reason_codes, "reason_codes")
        _validate_reason_codes(reason_codes)
        object.__setattr__(self, "reason_codes", reason_codes)


@dataclass(frozen=True)
class OpenInterestReport:
    """Full deterministic open interest report."""

    report_id: str
    kind: str
    version: str
    source_spec: str
    generated_at: datetime
    config: OpenInterestConfig
    safety_flags: OpenInterestSafetyFlags
    scores: tuple[OpenInterestScore, ...]
    universe_summary: OpenInterestUniverseSummary
    reason_codes: tuple[str, ...]
    metadata: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.report_id, str) or not self.report_id:
            raise ValueError("report_id must be non-empty")
        if not isinstance(self.kind, str) or not self.kind:
            raise ValueError("kind must be non-empty")
        if not isinstance(self.version, str) or not self.version:
            raise ValueError("version must be non-empty")
        if not isinstance(self.source_spec, str) or not self.source_spec:
            raise ValueError("source_spec must be non-empty")
        if not isinstance(self.generated_at, datetime) or self.generated_at.tzinfo is None:
            raise ValueError("generated_at must be a timezone-aware datetime")
        if not isinstance(self.scores, (tuple, list)):
            raise ValueError("scores must be a tuple or list")
        for item in self.scores:
            if not isinstance(item, OpenInterestScore):
                raise ValueError("scores must contain OpenInterestScore values")
        scores = tuple(self.scores)
        metadata = _coerce_mapping(self.metadata)
        reason_codes = _ensure_tuple_of_str(self.reason_codes, "reason_codes")
        _validate_reason_codes(reason_codes)
        object.__setattr__(self, "scores", scores)
        object.__setattr__(self, "metadata", metadata)
        object.__setattr__(self, "reason_codes", reason_codes)

    @classmethod
    def blocked(
        cls,
        *,
        reason_code: str,
        report_id: str = "blocked",
        generated_at: datetime | None = None,
        metadata: Mapping[str, str] | None = None,
    ) -> OpenInterestReport:
        """Return a fail-closed BLOCKED report when inputs are unsafe or invalid.

        If `generated_at` is omitted, the current UTC time is used. Tests should pass
        an explicit `generated_at` for deterministic output.
        """
        if reason_code not in OPEN_INTEREST_REASON_CODES:
            raise ValueError(f"unsupported reason code: {reason_code}")
        generated_at = generated_at or datetime.now(timezone.utc)
        empty_summary = OpenInterestUniverseSummary(
            total_pairs=0,
            ready_count=0,
            insufficient_data_count=0,
            blocked_count=0,
            expanding_count=0,
            contracting_count=0,
            flat_count=0,
            unstable_count=0,
            price_up_oi_up_count=0,
            price_up_oi_down_count=0,
            price_down_oi_up_count=0,
            price_down_oi_down_count=0,
            mixed_count=0,
            average_total_score=None,
            top_expanding_pair=None,
            top_contracting_pair=None,
            data_quality=OpenInterestDataQuality(
                expected_rows=0,
                actual_rows=0,
                missing_rows=0,
                min_required_rows_met=False,
                stale_input_count=0,
                reason_codes=(reason_code,),
            ),
            summary_narrative="Report blocked due to unsafe or invalid input. No open interest calculations were performed.",
            reason_codes=(reason_code,),
        )
        return cls(
            report_id=report_id,
            kind="open_interest_report",
            version="0.25.0-dev",
            source_spec="SPEC-026",
            generated_at=generated_at,
            config=OpenInterestConfig(),
            safety_flags=OpenInterestSafetyFlags(),
            scores=(),
            universe_summary=empty_summary,
            reason_codes=(reason_code,),
            metadata=metadata or MappingProxyType({}),
        )
