"""Frozen dataclasses for hunter.discovery package.

MVP-26 — Discovery Engine.

All dataclasses are frozen. Validation runs in __post_init__.
Inputs are already-loaded local values only; the engine never opens files,
follows paths, validates paths, calls network endpoints, or accesses external
resources.

The discovery engine is a human-audit / research-support artifact only. It is
not a trading signal, not trade approval, not strategy approval, not execution
approval, not portfolio/universe approval, and not Freqtrade input. It does not
emit action commands, suggest orders, or create execution instructions.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import Any

DISCOVERY_VERSION = "0.26.0-dev"


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class DiscoveryState(Enum):
    """State of a discovery candidate."""

    CANDIDATE = "CANDIDATE"
    WATCHLIST = "WATCHLIST"
    EXCLUDED = "EXCLUDED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    BLOCKED = "BLOCKED"


class DiscoveryClassification(Enum):
    """Detailed classification of a discovery candidate."""

    STRONG_RESEARCH_CANDIDATE = "STRONG_RESEARCH_CANDIDATE"
    MODERATE_RESEARCH_CANDIDATE = "MODERATE_RESEARCH_CANDIDATE"
    WATCHLIST_ONLY = "WATCHLIST_ONLY"
    EXCLUDED_BY_FILTERS = "EXCLUDED_BY_FILTERS"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    BLOCKED = "BLOCKED"


class DiscoveryInputKind(Enum):
    """Kind of discovery input payload."""

    SUMMARY = "SUMMARY"
    RELATIVE_STRENGTH = "RELATIVE_STRENGTH"
    OPEN_INTEREST = "OPEN_INTEREST"


# ---------------------------------------------------------------------------
# Reason codes — deterministic, partitioned constants.
# ---------------------------------------------------------------------------


INVALID_PAIR = "INVALID_PAIR"
INVALID_DISCOVERY_SCORE = "INVALID_DISCOVERY_SCORE"
UNSAFE_DISCOVERY_CONTENT = "UNSAFE_DISCOVERY_CONTENT"
RELATIVE_STRENGTH_BLOCKED = "RELATIVE_STRENGTH_BLOCKED"
OPEN_INTEREST_BLOCKED = "OPEN_INTEREST_BLOCKED"

MISSING_RELATIVE_STRENGTH_CONTEXT = "MISSING_RELATIVE_STRENGTH_CONTEXT"
MISSING_OPEN_INTEREST_CONTEXT = "MISSING_OPEN_INTEREST_CONTEXT"
RELATIVE_STRENGTH_INSUFFICIENT_DATA = "RELATIVE_STRENGTH_INSUFFICIENT_DATA"
OPEN_INTEREST_INSUFFICIENT_DATA = "OPEN_INTEREST_INSUFFICIENT_DATA"

LOW_RELATIVE_STRENGTH_SCORE = "LOW_RELATIVE_STRENGTH_SCORE"
LOW_OPEN_INTEREST_SCORE = "LOW_OPEN_INTEREST_SCORE"
MISALIGNED_CONTEXT = "MISALIGNED_CONTEXT"
PASSED_DISCOVERY_FILTERS = "PASSED_DISCOVERY_FILTERS"

HUMAN_RESEARCH_ONLY = "HUMAN_RESEARCH_ONLY"
NO_NETWORK_CONNECTION = "NO_NETWORK_CONNECTION"
NO_FILE_READ_IN_ENGINE = "NO_FILE_READ_IN_ENGINE"
NO_ACTION_COMMANDS_EMITTED = "NO_ACTION_COMMANDS_EMITTED"
ALIGNED_CONTEXT = "ALIGNED_CONTEXT"
MIXED_ALIGNMENT = "MIXED_ALIGNMENT"


DISCOVERY_BLOCKING_REASON_CODES: frozenset[str] = frozenset(
    {
        INVALID_PAIR,
        INVALID_DISCOVERY_SCORE,
        UNSAFE_DISCOVERY_CONTENT,
        RELATIVE_STRENGTH_BLOCKED,
        OPEN_INTEREST_BLOCKED,
    }
)

DISCOVERY_INSUFFICIENT_DATA_REASON_CODES: frozenset[str] = frozenset(
    {
        MISSING_RELATIVE_STRENGTH_CONTEXT,
        MISSING_OPEN_INTEREST_CONTEXT,
        RELATIVE_STRENGTH_INSUFFICIENT_DATA,
        OPEN_INTEREST_INSUFFICIENT_DATA,
    }
)

DISCOVERY_FILTER_REASON_CODES: frozenset[str] = frozenset(
    {
        LOW_RELATIVE_STRENGTH_SCORE,
        LOW_OPEN_INTEREST_SCORE,
        MISALIGNED_CONTEXT,
        PASSED_DISCOVERY_FILTERS,
    }
)

DISCOVERY_ADVISORY_REASON_CODES: frozenset[str] = frozenset(
    {
        HUMAN_RESEARCH_ONLY,
        NO_NETWORK_CONNECTION,
        NO_FILE_READ_IN_ENGINE,
        NO_ACTION_COMMANDS_EMITTED,
        ALIGNED_CONTEXT,
        MIXED_ALIGNMENT,
    }
)

DISCOVERY_REASON_CODES: frozenset[str] = (
    DISCOVERY_BLOCKING_REASON_CODES
    | DISCOVERY_INSUFFICIENT_DATA_REASON_CODES
    | DISCOVERY_FILTER_REASON_CODES
    | DISCOVERY_ADVISORY_REASON_CODES
)


# ---------------------------------------------------------------------------
# Forbidden terms — local-string content guard.
# ---------------------------------------------------------------------------


FORBIDDEN_DISCOVERY_TERMS: frozenset[str] = frozenset(
    {
        "buy",
        "sell",
        "order",
        "trade",
        "trading",
        "position",
        "execute",
        "execution",
        "signal",
        "entry",
        "exit",
        "stop loss",
        "take profit",
        "leverage",
        "freqtrade",
        "strategy",
        "hyperopt",
        "backtest",
        "exchange",
        "binance",
        "api",
        "api key",
        "live",
        "real-time",
        "websocket",
        "candle",
        "action",
        "command",
        "instruction",
    }
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _coerce_tuple_strs(values: Sequence[str] | None) -> tuple[str, ...]:
    """Return a deduplicated tuple of strings."""
    if values is None:
        return ()
    return tuple(dict.fromkeys(str(v) for v in values))


def _coerce_mapping_strs(
    mapping: Mapping[str, str] | None,
) -> Mapping[str, str]:
    """Return an immutable copy of a string mapping."""
    if mapping is None:
        return MappingProxyType({})
    return MappingProxyType({str(k): str(v) for k, v in mapping.items()})


def _validate_score(value: float | None, name: str) -> None:
    """Validate a score field is None or finite in [0, 100]."""
    if value is None:
        return
    if not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite float or None, got {value!r}")
    if not 0.0 <= value <= 100.0:
        raise ValueError(f"{name} must be in [0.0, 100.0], got {value!r}")


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DiscoveryConfig:
    """Configuration for discovery scoring and classification."""

    require_relative_strength: bool = True
    require_open_interest: bool = True
    block_on_blocked_context: bool = True
    block_on_missing_context: bool = False
    include_excluded_candidates: bool = True
    min_relative_strength_score: float = 60.0
    min_open_interest_score: float = 50.0
    strong_candidate_score: float = 75.0
    moderate_candidate_score: float = 60.0
    watchlist_score: float = 45.0
    score_weights: Mapping[str, float] = field(
        default_factory=lambda: {
            "relative_strength_score": 0.35,
            "open_interest_score": 0.25,
            "alignment_score": 0.20,
            "data_quality_score": 0.10,
            "filter_bonus_score": 0.10,
        }
    )

    def __post_init__(self) -> None:
        _validate_score(self.min_relative_strength_score, "min_relative_strength_score")
        _validate_score(self.min_open_interest_score, "min_open_interest_score")
        _validate_score(self.strong_candidate_score, "strong_candidate_score")
        _validate_score(self.moderate_candidate_score, "moderate_candidate_score")
        _validate_score(self.watchlist_score, "watchlist_score")

        if not (
            self.strong_candidate_score
            >= self.moderate_candidate_score
            >= self.watchlist_score
        ):
            raise ValueError(
                "strong_candidate_score >= moderate_candidate_score >= watchlist_score"
            )

        weights = dict(self.score_weights)
        expected_keys = {
            "relative_strength_score",
            "open_interest_score",
            "alignment_score",
            "data_quality_score",
            "filter_bonus_score",
        }
        if set(weights.keys()) != expected_keys:
            raise ValueError(f"score_weights must have exactly {expected_keys}")

        total = 0.0
        for key in expected_keys:
            weight = weights[key]
            if not isinstance(weight, (int, float)) or not math.isfinite(weight):
                raise ValueError(f"weight {key} must be a finite float")
            if not 0.0 <= weight <= 1.0:
                raise ValueError(f"weight {key} must be in [0.0, 1.0]")
            total += weight
        if abs(total - 1.0) > 1e-9:
            raise ValueError(f"score_weights must sum to 1.0, got {total}")

        object.__setattr__(
            self, "score_weights", MappingProxyType({k: weights[k] for k in expected_keys})
        )


@dataclass(frozen=True)
class DiscoverySafetyFlags:
    """Safety flags describing the discovery process and its output."""

    has_unsafe_content: bool = False
    has_invalid_pair: bool = False
    has_invalid_score: bool = False
    has_blocked_context: bool = False
    has_missing_required_context: bool = False
    has_inconsistent_state: bool = False
    no_action_commands_emitted: bool = True
    no_network_connection: bool = True
    no_file_read_in_engine: bool = True

    @property
    def is_safe(self) -> bool:
        return not any(
            [
                self.has_unsafe_content,
                self.has_invalid_pair,
                self.has_invalid_score,
                self.has_blocked_context,
                self.has_missing_required_context,
                self.has_inconsistent_state,
            ]
        )


@dataclass(frozen=True)
class DiscoveryRelativeStrengthSummary:
    """Summary of relative-strength context for a single pair."""

    pair: str
    state: str
    decision: str
    total_score: float | None
    rank_percentile_30d: float | None = None
    reason_codes: tuple[str, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.pair, str) or not self.pair.strip():
            raise ValueError("pair must be a non-empty string")
        _validate_score(self.total_score, "total_score")
        _validate_score(self.rank_percentile_30d, "rank_percentile_30d")
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))


@dataclass(frozen=True)
class DiscoveryOpenInterestSummary:
    """Summary of open-interest context for a single pair."""

    pair: str
    state: str
    positioning: str
    trend: str
    funding_context: str
    total_score: float | None
    reason_codes: tuple[str, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.pair, str) or not self.pair.strip():
            raise ValueError("pair must be a non-empty string")
        _validate_score(self.total_score, "total_score")
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))


@dataclass(frozen=True)
class DiscoveryInput:
    """Single pair input for discovery scoring."""

    pair: str
    input_kind: DiscoveryInputKind = DiscoveryInputKind.SUMMARY
    relative_strength: DiscoveryRelativeStrengthSummary | None = None
    open_interest: DiscoveryOpenInterestSummary | None = None
    tags: tuple[str, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.pair, str) or not self.pair.strip():
            raise ValueError("pair must be a non-empty string")
        if self.relative_strength is not None and self.relative_strength.pair != self.pair:
            raise ValueError(
                "relative_strength.pair must match DiscoveryInput.pair"
            )
        if self.open_interest is not None and self.open_interest.pair != self.pair:
            raise ValueError("open_interest.pair must match DiscoveryInput.pair")
        object.__setattr__(self, "tags", _coerce_tuple_strs(self.tags))
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))


@dataclass(frozen=True)
class DiscoveryScore:
    """Composite discovery score with sub-scores."""

    relative_strength_score: float
    open_interest_score: float
    alignment_score: float
    data_quality_score: float
    filter_bonus_score: float
    total_score: float
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        for name in (
            "relative_strength_score",
            "open_interest_score",
            "alignment_score",
            "data_quality_score",
            "filter_bonus_score",
            "total_score",
        ):
            _validate_score(getattr(self, name), name)
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))


@dataclass(frozen=True)
class DiscoveryUniverseSummary:
    """Summary counts over the discovery universe."""

    total_inputs: int
    candidate_count: int
    watchlist_count: int
    excluded_count: int
    insufficient_data_count: int
    blocked_count: int
    ready_context_count: int
    missing_context_count: int
    blocked_context_count: int

    def __post_init__(self) -> None:
        counts = [
            self.total_inputs,
            self.candidate_count,
            self.watchlist_count,
            self.excluded_count,
            self.insufficient_data_count,
            self.blocked_count,
            self.ready_context_count,
            self.missing_context_count,
            self.blocked_context_count,
        ]
        for value in counts:
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"Universe counts must be non-negative ints, got {value!r}")
        if (
            self.candidate_count
            + self.watchlist_count
            + self.excluded_count
            + self.insufficient_data_count
            + self.blocked_count
            != self.total_inputs
        ):
            raise ValueError("State counts must sum to total_inputs")


@dataclass(frozen=True)
class DiscoveryDataQuality:
    """Data quality summary for the discovery run."""

    total_inputs: int
    pairs_with_both_contexts: int
    pairs_with_missing_relative_strength: int
    pairs_with_missing_open_interest: int
    pairs_with_blocked_context: int
    pairs_with_insufficient_context: int
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        for name, value in (
            ("total_inputs", self.total_inputs),
            ("pairs_with_both_contexts", self.pairs_with_both_contexts),
            ("pairs_with_missing_relative_strength", self.pairs_with_missing_relative_strength),
            ("pairs_with_missing_open_interest", self.pairs_with_missing_open_interest),
            ("pairs_with_blocked_context", self.pairs_with_blocked_context),
            ("pairs_with_insufficient_context", self.pairs_with_insufficient_context),
        ):
            if not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative int, got {value!r}")
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))


@dataclass(frozen=True)
class DiscoveryCandidate:
    """A single scored discovery candidate."""

    pair: str
    state: DiscoveryState
    classification: DiscoveryClassification
    score: DiscoveryScore
    relative_strength: DiscoveryRelativeStrengthSummary | None
    open_interest: DiscoveryOpenInterestSummary | None
    reason_codes: tuple[str, ...]
    tags: tuple[str, ...]
    metadata: Mapping[str, str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))
        object.__setattr__(self, "tags", _coerce_tuple_strs(self.tags))
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))


@dataclass(frozen=True)
class DiscoveryReport:
    """Top-level discovery report."""

    report_id: str
    version: str
    generated_at: datetime
    config: DiscoveryConfig
    inputs: tuple[DiscoveryInput, ...]
    candidates: tuple[DiscoveryCandidate, ...]
    universe_summary: DiscoveryUniverseSummary
    data_quality: DiscoveryDataQuality
    safety_flags: DiscoverySafetyFlags
    reason_codes: tuple[str, ...]
    metadata: Mapping[str, str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "inputs", tuple(self.inputs))
        object.__setattr__(self, "candidates", tuple(self.candidates))
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))
        for code in self.reason_codes:
            if code not in DISCOVERY_REASON_CODES:
                raise ValueError(f"unsupported reason code: {code}")

    @classmethod
    def blocked(
        cls,
        *,
        reason_code: str,
        report_id: str = "blocked",
        generated_at: datetime | None = None,
        metadata: Mapping[str, str] | None = None,
    ) -> "DiscoveryReport":
        """Return a fail-closed blocked report."""
        if reason_code not in DISCOVERY_REASON_CODES:
            raise ValueError(f"unsupported reason code: {reason_code}")
        config = DiscoveryConfig()
        return cls(
            report_id=report_id,
            version=DISCOVERY_VERSION,
            generated_at=generated_at or datetime.now(timezone.utc),
            config=config,
            inputs=(),
            candidates=(),
            universe_summary=DiscoveryUniverseSummary(
                total_inputs=0,
                candidate_count=0,
                watchlist_count=0,
                excluded_count=0,
                insufficient_data_count=0,
                blocked_count=0,
                ready_context_count=0,
                missing_context_count=0,
                blocked_context_count=0,
            ),
            data_quality=DiscoveryDataQuality(
                total_inputs=0,
                pairs_with_both_contexts=0,
                pairs_with_missing_relative_strength=0,
                pairs_with_missing_open_interest=0,
                pairs_with_blocked_context=0,
                pairs_with_insufficient_context=0,
                reason_codes=(reason_code,),
            ),
            safety_flags=DiscoverySafetyFlags(
                has_blocked_context=True,
                no_action_commands_emitted=True,
                no_network_connection=True,
                no_file_read_in_engine=True,
            ),
            reason_codes=(reason_code,),
            metadata=_coerce_mapping_strs(metadata),
        )
