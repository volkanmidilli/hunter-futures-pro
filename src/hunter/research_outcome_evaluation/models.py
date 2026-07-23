"""Frozen models and contracts for SPEC-076 ranking outcome evaluation.

Phase A consumes immutable JSON snapshot audit artifacts (SPEC-074/075) and
local 1h Feather price series, resolves every matured cohort member to a
terminal state, and persists deterministic Pair Observation Records and
Snapshot Summary Records.

All models are frozen dataclasses.  Safety flags are immutable invariants
(construction with a violating value raises :exc:`ValueError`), following
the SPEC-074 pattern.  All :class:`Decimal` fields serialize as JSON
strings (Decimal-as-string discipline).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Mapping

# ---------------------------------------------------------------------------
# Package version and spec identifier
# ---------------------------------------------------------------------------

OUTCOME_EVALUATION_VERSION: str = "0.1.0"
SPEC_076: str = "SPEC-076"

# ---------------------------------------------------------------------------
# Horizon registry — extensible without schema migration.
# A horizon token is ``<int>d`` meaning ``<int> * 24`` hours.
# ---------------------------------------------------------------------------

DEFAULT_HORIZONS: tuple[str, ...] = ("1d", "3d", "7d")
_HORIZON_RE = re.compile(r"^(?P<days>[1-9][0-9]*)d$")

TOP_N_CUTS: tuple[int, ...] = (5, 10, 20, 30)

DEFAULT_MIN_WINDOW_COVERAGE: Decimal = Decimal("0.95")

BENCHMARK_PAIR: str = "BTC/USDT:USDT"
BENCHMARK_BASE_SYMBOL: str = "BTC"

# Transient, computed-only state: never persisted.
PENDING_HORIZON: str = "PENDING_HORIZON"

# ---------------------------------------------------------------------------
# Null-reason codes (persisted alongside null values)
# ---------------------------------------------------------------------------

REASON_FIRST_SNAPSHOT = "FIRST_SNAPSHOT"
REASON_ZERO_DENOMINATOR = "ZERO_DENOMINATOR"
REASON_INSUFFICIENT_OBSERVATIONS = "INSUFFICIENT_OBSERVATIONS"
REASON_INVALID_SNAPSHOT = "INVALID_SNAPSHOT"

NULL_REASON_CODES: frozenset[str] = frozenset(
    {REASON_FIRST_SNAPSHOT, REASON_ZERO_DENOMINATOR, REASON_INSUFFICIENT_OBSERVATIONS}
)

# ---------------------------------------------------------------------------
# Terminal states
# ---------------------------------------------------------------------------


class TerminalState(str, Enum):
    """Complete evaluation contract outcome for one cohort member."""

    OUTCOME_AVAILABLE = "OUTCOME_AVAILABLE"
    SNAPSHOT_INVALID = "SNAPSHOT_INVALID"
    OUTCOME_UNAVAILABLE_NO_SOURCE = "OUTCOME_UNAVAILABLE_NO_SOURCE"
    OUTCOME_UNAVAILABLE_GAP = "OUTCOME_UNAVAILABLE_GAP"
    OUTCOME_UNAVAILABLE_INVALID_PRICE = "OUTCOME_UNAVAILABLE_INVALID_PRICE"
    BENCHMARK_UNAVAILABLE = "BENCHMARK_UNAVAILABLE"
    # Schema-reserved: never emitted in Phase A.
    OUTCOME_UNAVAILABLE_DELISTED = "OUTCOME_UNAVAILABLE_DELISTED"


PHASE_A_EMITTED_STATES: frozenset[TerminalState] = frozenset(
    {
        TerminalState.OUTCOME_AVAILABLE,
        TerminalState.SNAPSHOT_INVALID,
        TerminalState.OUTCOME_UNAVAILABLE_NO_SOURCE,
        TerminalState.OUTCOME_UNAVAILABLE_GAP,
        TerminalState.OUTCOME_UNAVAILABLE_INVALID_PRICE,
        TerminalState.BENCHMARK_UNAVAILABLE,
    }
)

# ---------------------------------------------------------------------------
# Horizon helpers
# ---------------------------------------------------------------------------


def parse_horizon_hours(horizon: str) -> int:
    """Return the horizon length in hours for a ``<int>d`` token.

    Raises :exc:`ValueError` for malformed tokens.
    """
    match = _HORIZON_RE.match(horizon)
    if not match:
        raise ValueError(f"invalid horizon token (expected '<int>d'): {horizon!r}")
    return int(match.group("days")) * 24


# ---------------------------------------------------------------------------
# Safety flags — immutable invariants (SPEC-074 pattern)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OutcomeEvaluationSafetyFlags:
    """Research-only safety invariants for outcome-evaluation artifacts.

    All fields default to the mandatory research-only posture.  Construction
    with any other value raises :exc:`ValueError`.
    """

    research_only: bool = True
    execution_approval_granted: bool = False
    production_approval_granted: bool = False
    live_trading_allowed: bool = False
    automatic_execution_allowed: bool = False
    human_approval_required: bool = True

    def __post_init__(self) -> None:
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


RESEARCH_NOTICE: str = (
    "Research-only artifact. Does not authorize execution, "
    "production deployment, live trading, dry-run trading, "
    "automatic execution, strategy selection, universe selection, "
    "order placement, signal generation, strategy mutation, "
    "universe mutation, or position changes. "
    "Human review is required."
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class OutcomeEvaluationConfig:
    """Deterministic configuration for one outcome-evaluation run."""

    horizons: tuple[str, ...] = DEFAULT_HORIZONS
    min_window_coverage: Decimal = DEFAULT_MIN_WINDOW_COVERAGE

    def __post_init__(self) -> None:
        if not self.horizons:
            raise ValueError("horizons must not be empty")
        for horizon in self.horizons:
            parse_horizon_hours(horizon)
        if len(set(self.horizons)) != len(self.horizons):
            raise ValueError("horizons must not contain duplicates")
        if not isinstance(self.min_window_coverage, Decimal):
            raise ValueError("min_window_coverage must be a Decimal")
        if self.min_window_coverage <= Decimal("0") or self.min_window_coverage > Decimal("1"):
            raise ValueError("min_window_coverage must be in (0, 1]")


# ---------------------------------------------------------------------------
# Core record models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PairObservationRecord:
    """Terminal outcome for one (snapshot_date, ranking_profile, horizon, pair).

    Written exactly once at terminal resolution; immutable after creation.
    All ``Decimal`` fields serialize as JSON strings.
    """

    snapshot_date: str
    ranking_profile: str
    outcome_horizon: str
    pair: str
    is_benchmark_pair: bool
    terminal_state: TerminalState
    rank_at_selection: int
    reference_close: Decimal | None = None
    reference_timestamp: str | None = None
    realized_return: Decimal | None = None
    benchmark_return: Decimal | None = None
    benchmark_relative_return: Decimal | None = None
    mae_pct: Decimal | None = None
    mfe_pct: Decimal | None = None
    realized_volatility_pct: Decimal | None = None
    relative_strength_score: Decimal | None = None
    liquidity_score: Decimal | None = None
    coverage_ratio: Decimal | None = None
    window_start: str | None = None
    window_end: str | None = None
    fingerprint: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)
    safety_flags: OutcomeEvaluationSafetyFlags = field(
        default_factory=OutcomeEvaluationSafetyFlags
    )

    def __post_init__(self) -> None:
        if not isinstance(self.terminal_state, TerminalState):
            raise ValueError("terminal_state must be a TerminalState")
        if self.terminal_state is TerminalState.OUTCOME_UNAVAILABLE_DELISTED:
            raise ValueError(
                "OUTCOME_UNAVAILABLE_DELISTED is schema-reserved and never emitted in Phase A"
            )
        if self.terminal_state not in PHASE_A_EMITTED_STATES:
            raise ValueError(f"terminal_state {self.terminal_state} is not a Phase A code")
        if self.terminal_state is TerminalState.OUTCOME_AVAILABLE:
            if self.realized_return is None:
                raise ValueError("OUTCOME_AVAILABLE requires realized_return")
            if self.reference_close is None:
                raise ValueError("OUTCOME_AVAILABLE requires reference_close")
        if self.rank_at_selection < 1:
            raise ValueError("rank_at_selection must be >= 1")


@dataclass(frozen=True)
class SnapshotSummaryRecord:
    """Cohort-level summary per (snapshot_date, ranking_profile, outcome_horizon).

    Metric field names are normalized (unsuffixed) because the record is
    already keyed by ``outcome_horizon``; flattened report metric names add
    the ``_1d`` / ``_3d`` / ``_7d`` suffix at report time.
    """

    snapshot_date: str
    ranking_profile: str
    outcome_horizon: str
    cohort_size: int
    available_count: int
    unavailable_count: int
    days_since_previous_snapshot: int | None = None
    previous_snapshot_reason: str | None = None
    turnover: Decimal | None = None
    turnover_reason: str | None = None
    retention: Decimal | None = None
    retention_reason: str | None = None
    daily_data_availability: Decimal | None = None
    daily_data_availability_reason: str | None = None
    top_5_return_pct: Decimal | None = None
    top_5_available_count: int | None = None
    top_10_return_pct: Decimal | None = None
    top_10_available_count: int | None = None
    top_20_return_pct: Decimal | None = None
    top_20_available_count: int | None = None
    top_30_return_pct: Decimal | None = None
    top_30_available_count: int | None = None
    spearman_rank_return: Decimal | None = None
    spearman_relative_strength_return: Decimal | None = None
    spearman_liquidity_return: Decimal | None = None
    benchmark_relative_return_pct: Decimal | None = None
    mae_pct_mean: Decimal | None = None
    mfe_pct_mean: Decimal | None = None
    realized_volatility_pct_mean: Decimal | None = None
    benchmark_failure_reason: str | None = None
    fingerprint: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)
    safety_flags: OutcomeEvaluationSafetyFlags = field(
        default_factory=OutcomeEvaluationSafetyFlags
    )

    def __post_init__(self) -> None:
        if self.cohort_size < 0:
            raise ValueError("cohort_size must be >= 0")
        if self.available_count < 0 or self.unavailable_count < 0:
            raise ValueError("available_count and unavailable_count must be >= 0")
        if self.available_count + self.unavailable_count != self.cohort_size:
            raise ValueError("available_count + unavailable_count must equal cohort_size")
        for cut in TOP_N_CUTS:
            count = getattr(self, f"top_{cut}_available_count")
            if count is not None and count < 0:
                raise ValueError(f"top_{cut}_available_count must be >= 0")
        for reason in (
            self.previous_snapshot_reason,
            self.turnover_reason,
            self.retention_reason,
            self.daily_data_availability_reason,
        ):
            if reason is not None and reason not in NULL_REASON_CODES:
                raise ValueError(f"unknown null-reason code: {reason}")
        if self.days_since_previous_snapshot is None and self.previous_snapshot_reason is None:
            raise ValueError(
                "days_since_previous_snapshot null requires previous_snapshot_reason"
            )
        if self.turnover is None and self.turnover_reason is None:
            raise ValueError("turnover null requires turnover_reason")
        if self.retention is None and self.retention_reason is None:
            raise ValueError("retention null requires retention_reason")
        if self.daily_data_availability is None and self.daily_data_availability_reason is None:
            raise ValueError(
                "daily_data_availability null requires daily_data_availability_reason"
            )


# ---------------------------------------------------------------------------
# Serialization helpers (Decimal-as-string discipline)
# ---------------------------------------------------------------------------


def _dec(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None


def _safety_payload() -> dict[str, Any]:
    flags = OutcomeEvaluationSafetyFlags()
    return {
        "research_only": flags.research_only,
        "execution_approval_granted": flags.execution_approval_granted,
        "production_approval_granted": flags.production_approval_granted,
        "live_trading_allowed": flags.live_trading_allowed,
        "automatic_execution_allowed": flags.automatic_execution_allowed,
        "human_approval_required": flags.human_approval_required,
    }


def parse_decimal(value: Any) -> Decimal | None:
    """Parse a Decimal-as-string (or numeric) JSON value; ``None`` stays ``None``.

    Raises :exc:`ValueError` for unparseable values.
    """
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"invalid decimal value: {value!r}") from exc


def pair_observation_to_dict(record: PairObservationRecord) -> dict[str, Any]:
    """Serialize a :class:`PairObservationRecord` to a JSON-ready dict."""
    return {
        "snapshot_date": record.snapshot_date,
        "ranking_profile": record.ranking_profile,
        "outcome_horizon": record.outcome_horizon,
        "pair": record.pair,
        "is_benchmark_pair": record.is_benchmark_pair,
        "terminal_state": record.terminal_state.value,
        "rank_at_selection": record.rank_at_selection,
        "reference_close": _dec(record.reference_close),
        "reference_timestamp": record.reference_timestamp,
        "realized_return": _dec(record.realized_return),
        "benchmark_return": _dec(record.benchmark_return),
        "benchmark_relative_return": _dec(record.benchmark_relative_return),
        "mae_pct": _dec(record.mae_pct),
        "mfe_pct": _dec(record.mfe_pct),
        "realized_volatility_pct": _dec(record.realized_volatility_pct),
        "relative_strength_score": _dec(record.relative_strength_score),
        "liquidity_score": _dec(record.liquidity_score),
        "coverage_ratio": _dec(record.coverage_ratio),
        "window_start": record.window_start,
        "window_end": record.window_end,
        "fingerprint": record.fingerprint,
        "metadata": dict(record.metadata),
        "safety_flags": _safety_payload(),
        "_safety_notice": RESEARCH_NOTICE,
    }


def snapshot_summary_to_dict(record: SnapshotSummaryRecord) -> dict[str, Any]:
    """Serialize a :class:`SnapshotSummaryRecord` to a JSON-ready dict."""
    return {
        "snapshot_date": record.snapshot_date,
        "ranking_profile": record.ranking_profile,
        "outcome_horizon": record.outcome_horizon,
        "cohort_size": record.cohort_size,
        "available_count": record.available_count,
        "unavailable_count": record.unavailable_count,
        "days_since_previous_snapshot": record.days_since_previous_snapshot,
        "previous_snapshot_reason": record.previous_snapshot_reason,
        "turnover": _dec(record.turnover),
        "turnover_reason": record.turnover_reason,
        "retention": _dec(record.retention),
        "retention_reason": record.retention_reason,
        "daily_data_availability": _dec(record.daily_data_availability),
        "daily_data_availability_reason": record.daily_data_availability_reason,
        "top_5_return_pct": _dec(record.top_5_return_pct),
        "top_5_available_count": record.top_5_available_count,
        "top_10_return_pct": _dec(record.top_10_return_pct),
        "top_10_available_count": record.top_10_available_count,
        "top_20_return_pct": _dec(record.top_20_return_pct),
        "top_20_available_count": record.top_20_available_count,
        "top_30_return_pct": _dec(record.top_30_return_pct),
        "top_30_available_count": record.top_30_available_count,
        "spearman_rank_return": _dec(record.spearman_rank_return),
        "spearman_relative_strength_return": _dec(record.spearman_relative_strength_return),
        "spearman_liquidity_return": _dec(record.spearman_liquidity_return),
        "benchmark_relative_return_pct": _dec(record.benchmark_relative_return_pct),
        "mae_pct_mean": _dec(record.mae_pct_mean),
        "mfe_pct_mean": _dec(record.mfe_pct_mean),
        "realized_volatility_pct_mean": _dec(record.realized_volatility_pct_mean),
        "benchmark_failure_reason": record.benchmark_failure_reason,
        "fingerprint": record.fingerprint,
        "metadata": dict(record.metadata),
        "safety_flags": _safety_payload(),
        "_safety_notice": RESEARCH_NOTICE,
    }


def snapshot_summary_from_dict(payload: Mapping[str, Any]) -> SnapshotSummaryRecord:
    """Parse a persisted summary dict, tolerating legacy missing fields.

    Missing optional fields are defaulted to ``None`` so that legacy immutable
    summaries can be loaded without recompute or silent zero-fill in report
    output.
    """
    return SnapshotSummaryRecord(
        snapshot_date=payload["snapshot_date"],
        ranking_profile=payload["ranking_profile"],
        outcome_horizon=payload["outcome_horizon"],
        cohort_size=payload["cohort_size"],
        available_count=payload["available_count"],
        unavailable_count=payload["unavailable_count"],
        days_since_previous_snapshot=payload.get("days_since_previous_snapshot"),
        previous_snapshot_reason=payload.get("previous_snapshot_reason"),
        turnover=parse_decimal(payload.get("turnover")),
        turnover_reason=payload.get("turnover_reason"),
        retention=parse_decimal(payload.get("retention")),
        retention_reason=payload.get("retention_reason"),
        daily_data_availability=parse_decimal(payload.get("daily_data_availability")),
        daily_data_availability_reason=payload.get("daily_data_availability_reason"),
        top_5_return_pct=parse_decimal(payload.get("top_5_return_pct")),
        top_5_available_count=payload.get("top_5_available_count"),
        top_10_return_pct=parse_decimal(payload.get("top_10_return_pct")),
        top_10_available_count=payload.get("top_10_available_count"),
        top_20_return_pct=parse_decimal(payload.get("top_20_return_pct")),
        top_20_available_count=payload.get("top_20_available_count"),
        top_30_return_pct=parse_decimal(payload.get("top_30_return_pct")),
        top_30_available_count=payload.get("top_30_available_count"),
        spearman_rank_return=parse_decimal(payload.get("spearman_rank_return")),
        spearman_relative_strength_return=parse_decimal(
            payload.get("spearman_relative_strength_return")
        ),
        spearman_liquidity_return=parse_decimal(payload.get("spearman_liquidity_return")),
        benchmark_relative_return_pct=parse_decimal(payload.get("benchmark_relative_return_pct")),
        mae_pct_mean=parse_decimal(payload.get("mae_pct_mean")),
        mfe_pct_mean=parse_decimal(payload.get("mfe_pct_mean")),
        realized_volatility_pct_mean=parse_decimal(payload.get("realized_volatility_pct_mean")),
        benchmark_failure_reason=payload.get("benchmark_failure_reason"),
        fingerprint=payload.get("fingerprint", ""),
        metadata=dict(payload.get("metadata") or {}),
    )