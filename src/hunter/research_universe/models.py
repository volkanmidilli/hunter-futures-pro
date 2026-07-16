"""Frozen models and contracts for the research universe builder (MVP-64 / SPEC-065)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from types import MappingProxyType
from typing import Any

from hunter.discovery.models import (
    DISCOVERY_REASON_CODES,
)
from hunter.portfolio_construction.models import (
    PORTFOLIO_CONSTRUCTION_REASON_CODES,
)
from hunter.controlled_universe.models import (
    CONTROLLED_UNIVERSE_REASON_CODES,
)
from hunter.controlled_universe_export_adapter.models import (
    CONTROLLED_UNIVERSE_EXPORT_REASON_CODES,
)
from hunter.freqtrade_universe_adapter.models import (
    FREQTRADE_UNIVERSE_ADAPTER_REASON_CODES,
)
from hunter.research_market_data.models import (
    RESEARCH_MARKET_DATA_REASON_CODES,
)

RESEARCH_UNIVERSE_VERSION: str = "0.64.0-dev"
SPEC_VERSION: str = "SPEC-065"

# ---------------------------------------------------------------------------
# Reason codes
# ---------------------------------------------------------------------------

INVALID_BUNDLE = "INVALID_BUNDLE"
MISSING_BUNDLE = "MISSING_BUNDLE"
INVALID_SELECTION_WINDOW = "INVALID_SELECTION_WINDOW"
SELECTION_WINDOW_OUT_OF_RANGE = "SELECTION_WINDOW_OUT_OF_RANGE"
INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"
EMPTY_CANDIDATE_UNIVERSE = "EMPTY_CANDIDATE_UNIVERSE"
EMPTY_BASELINE_UNIVERSE = "EMPTY_BASELINE_UNIVERSE"
INELIGIBLE_PAIR = "INELIGIBLE_PAIR"
COVERAGE_BELOW_MIN = "COVERAGE_BELOW_MIN"
STABLECOIN_PAIR_EXCLUDED = "STABLECOIN_PAIR_EXCLUDED"
LEVERAGED_TOKEN_EXCLUDED = "LEVERAGED_TOKEN_EXCLUDED"
BENCHMARK_PAIR_EXCLUDED = "BENCHMARK_PAIR_EXCLUDED"
UNSAFE_SYMBOL_CONTENT = "UNSAFE_SYMBOL_CONTENT"
INVALID_SAFETY_FLAGS = "INVALID_SAFETY_FLAGS"
NO_ACTION_COMMANDS_EMITTED = "NO_ACTION_COMMANDS_EMITTED"
NO_NETWORK_CONNECTION = "NO_NETWORK_CONNECTION"
NO_FILE_READ_IN_ENGINE = "NO_FILE_READ_IN_ENGINE"
NO_DATABASE_CONNECTION = "NO_DATABASE_CONNECTION"
NO_EXCHANGE_CONNECTION = "NO_EXCHANGE_CONNECTION"
NO_FREQTRADE_RUNTIME_CONNECTION = "NO_FREQTRADE_RUNTIME_CONNECTION"
NO_AUTOMATIC_CONFIG_MUTATION = "NO_AUTOMATIC_CONFIG_MUTATION"
NO_OPEN_INTEREST_SYNTHESIS = "NO_OPEN_INTEREST_SYNTHESIS"
HUMAN_RESEARCH_ONLY = "HUMAN_RESEARCH_ONLY"
RESEARCH_ONLY_ARTIFACT = "RESEARCH_ONLY_ARTIFACT"
CANDIDATE_CLASSIFICATION_INCLUDED = "CANDIDATE_CLASSIFICATION_INCLUDED"
BASELINE_VOLUME_RANKED = "BASELINE_VOLUME_RANKED"
DUPLICATE_PAIR_DETECTED = "DUPLICATE_PAIR_DETECTED"
UNKNOWN_DISCOVERY_CLASSIFICATION = "UNKNOWN_DISCOVERY_CLASSIFICATION"

RESEARCH_UNIVERSE_REASON_CODES: frozenset[str] = frozenset(
    {
        INVALID_BUNDLE,
        MISSING_BUNDLE,
        INVALID_SELECTION_WINDOW,
        SELECTION_WINDOW_OUT_OF_RANGE,
        INSUFFICIENT_HISTORY,
        EMPTY_CANDIDATE_UNIVERSE,
        EMPTY_BASELINE_UNIVERSE,
        INELIGIBLE_PAIR,
        COVERAGE_BELOW_MIN,
        STABLECOIN_PAIR_EXCLUDED,
        LEVERAGED_TOKEN_EXCLUDED,
        BENCHMARK_PAIR_EXCLUDED,
        UNSAFE_SYMBOL_CONTENT,
        INVALID_SAFETY_FLAGS,
        NO_ACTION_COMMANDS_EMITTED,
        NO_NETWORK_CONNECTION,
        NO_FILE_READ_IN_ENGINE,
        NO_DATABASE_CONNECTION,
        NO_EXCHANGE_CONNECTION,
        NO_FREQTRADE_RUNTIME_CONNECTION,
        NO_AUTOMATIC_CONFIG_MUTATION,
        NO_OPEN_INTEREST_SYNTHESIS,
        HUMAN_RESEARCH_ONLY,
        RESEARCH_ONLY_ARTIFACT,
        CANDIDATE_CLASSIFICATION_INCLUDED,
        BASELINE_VOLUME_RANKED,
        DUPLICATE_PAIR_DETECTED,
        UNKNOWN_DISCOVERY_CLASSIFICATION,
    }
    | set(RESEARCH_MARKET_DATA_REASON_CODES)
    | set(DISCOVERY_REASON_CODES)
    | set(PORTFOLIO_CONSTRUCTION_REASON_CODES)
    | set(CONTROLLED_UNIVERSE_REASON_CODES)
    | set(CONTROLLED_UNIVERSE_EXPORT_REASON_CODES)
    | set(FREQTRADE_UNIVERSE_ADAPTER_REASON_CODES)
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class UniversePairDecisionKind(str, Enum):
    """Inclusion decision for a single pair in a universe."""

    INCLUDED = "INCLUDED"
    EXCLUDED = "EXCLUDED"


class UniversePairState(str, Enum):
    """Research state of a pair inside a universe."""

    CANDIDATE = "CANDIDATE"
    BASELINE = "BASELINE"
    WATCHLIST = "WATCHLIST"
    EXCLUDED = "EXCLUDED"
    BLOCKED = "BLOCKED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class UniversePairClassification(str, Enum):
    """Classification of a pair in a universe."""

    LONG_RESEARCH = "LONG_RESEARCH"
    SHORT_RESEARCH = "SHORT_RESEARCH"
    NEUTRAL_RESEARCH = "NEUTRAL_RESEARCH"
    WATCHLIST_RESEARCH = "WATCHLIST_RESEARCH"
    BLOCKED_BY_POLICY = "BLOCKED_BY_POLICY"
    BLOCKED_BY_DATA = "BLOCKED_BY_DATA"
    EXCLUDED_BY_POLICY = "EXCLUDED_BY_POLICY"
    EXCLUDED_BY_DATA = "EXCLUDED_BY_DATA"
    BASELINE_VOLUME = "BASELINE_VOLUME"
    UNKNOWN = "UNKNOWN"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _coerce_tuple_strs(values: tuple[str, ...] | list[str] | None) -> tuple[str, ...]:
    """Coerce a sequence to a deduplicated tuple of strings."""
    if values is None:
        return ()
    return tuple(dict.fromkeys(str(v) for v in values))


def _coerce_mapping_strs(
    mapping: dict[str, str] | Any | None,
) -> Any:
    """Return an immutable string mapping."""
    if mapping is None:
        return MappingProxyType({})
    return MappingProxyType({str(k): str(v) for k, v in dict(mapping).items()})


# ---------------------------------------------------------------------------
# Config and window
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SelectionWindow:
    """Explicit UTC selection window for candidate and baseline universes."""

    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if not isinstance(self.start, datetime) or not isinstance(self.end, datetime):
            raise ValueError("start and end must be datetime values")
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError("start and end must be timezone-aware")
        if self.end <= self.start:
            raise ValueError("selection window end must be after start")

    def contains(self, value: datetime) -> bool:
        """Return True if value is within [start, end)."""
        return self.start <= value < self.end

    def __contains__(self, value: datetime) -> bool:
        return self.contains(value)


@dataclass(frozen=True)
class ResearchUniverseSafetyFlags:
    """Mandatory safety invariants for every research universe artifact."""

    research_only: bool = True
    execution_approval_granted: bool = False
    production_approval_granted: bool = False
    live_trading_allowed: bool = False
    automatic_execution_allowed: bool = False
    no_action_commands_emitted: bool = True
    no_network_connection: bool = True
    no_file_read_in_engine: bool = True
    no_database_connection: bool = True
    no_exchange_connection: bool = True
    no_freqtrade_runtime_connection: bool = True
    no_automatic_config_mutation: bool = True
    no_open_interest_synthesis: bool = True
    human_research_only: bool = True

    def __post_init__(self) -> None:
        for name, value in (
            ("research_only", self.research_only),
            ("execution_approval_granted", self.execution_approval_granted),
            ("production_approval_granted", self.production_approval_granted),
            ("live_trading_allowed", self.live_trading_allowed),
            ("automatic_execution_allowed", self.automatic_execution_allowed),
            ("no_action_commands_emitted", self.no_action_commands_emitted),
            ("no_network_connection", self.no_network_connection),
            ("no_file_read_in_engine", self.no_file_read_in_engine),
            ("no_database_connection", self.no_database_connection),
            ("no_exchange_connection", self.no_exchange_connection),
            ("no_freqtrade_runtime_connection", self.no_freqtrade_runtime_connection),
            ("no_automatic_config_mutation", self.no_automatic_config_mutation),
            ("no_open_interest_synthesis", self.no_open_interest_synthesis),
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


@dataclass(frozen=True)
class ResearchUniverseConfig:
    """Configuration for the research universe builder."""

    selection_window: SelectionWindow
    min_coverage_ratio: float = 0.8
    min_baseline_rows: int = 10
    max_candidate_pairs: int | None = None
    max_baseline_pairs: int | None = None
    min_quote_volume: Decimal | None = None
    quote_currency: str = "USDT"
    exclude_stablecoins: bool = True
    exclude_leveraged_tokens: bool = True
    benchmark_pairs: tuple[str, ...] = ("BTC/USDT", "ETH/USDT")
    max_initial_age_seconds: float | None = None
    pair_format: str = "base/quote"

    def __post_init__(self) -> None:
        if not isinstance(self.selection_window, SelectionWindow):
            raise ValueError(
                f"selection_window must be a SelectionWindow, got {self.selection_window!r}"
            )
        if not isinstance(self.min_coverage_ratio, (int, float)) or not 0.0 <= self.min_coverage_ratio <= 1.0:
            raise ValueError(
                f"min_coverage_ratio must be in [0, 1], got {self.min_coverage_ratio!r}"
            )
        if not isinstance(self.min_baseline_rows, int) or self.min_baseline_rows < 1:
            raise ValueError(
                f"min_baseline_rows must be a positive int, got {self.min_baseline_rows!r}"
            )
        if self.max_candidate_pairs is not None and (
            not isinstance(self.max_candidate_pairs, int) or self.max_candidate_pairs < 0
        ):
            raise ValueError(
                f"max_candidate_pairs must be a non-negative int or None, got {self.max_candidate_pairs!r}"
            )
        if self.max_baseline_pairs is not None and (
            not isinstance(self.max_baseline_pairs, int) or self.max_baseline_pairs < 0
        ):
            raise ValueError(
                f"max_baseline_pairs must be a non-negative int or None, got {self.max_baseline_pairs!r}"
            )
        if self.min_quote_volume is not None and not isinstance(self.min_quote_volume, Decimal):
            raise ValueError(
                f"min_quote_volume must be a Decimal or None, got {self.min_quote_volume!r}"
            )
        if not isinstance(self.quote_currency, str) or not self.quote_currency.strip():
            raise ValueError(
                f"quote_currency must be a non-empty string, got {self.quote_currency!r}"
            )
        if not isinstance(self.exclude_stablecoins, bool):
            raise ValueError(
                f"exclude_stablecoins must be a bool, got {self.exclude_stablecoins!r}"
            )
        if not isinstance(self.exclude_leveraged_tokens, bool):
            raise ValueError(
                f"exclude_leveraged_tokens must be a bool, got {self.exclude_leveraged_tokens!r}"
            )
        for pair in self.benchmark_pairs:
            if not isinstance(pair, str) or not pair.strip():
                raise ValueError(
                    f"benchmark_pairs must be non-empty strings, got {pair!r}"
                )
        if self.max_initial_age_seconds is not None and (
            not isinstance(self.max_initial_age_seconds, (int, float))
            or self.max_initial_age_seconds < 0
        ):
            raise ValueError(
                f"max_initial_age_seconds must be a non-negative number or None, got {self.max_initial_age_seconds!r}"
            )
        if self.pair_format not in ("base/quote", "base_quote"):
            raise ValueError(
                f"pair_format must be 'base/quote' or 'base_quote', got {self.pair_format!r}"
            )


# ---------------------------------------------------------------------------
# Per-pair results
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PairEligibilityResult:
    """Common eligibility decision for a candidate or baseline pair."""

    pair: str
    is_eligible: bool
    coverage: float
    source_fingerprint: str
    reason_codes: tuple[str, ...] = ()
    metadata: Any = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.pair, str) or not self.pair.strip():
            raise ValueError("pair must be a non-empty string")
        if not isinstance(self.is_eligible, bool):
            raise ValueError("is_eligible must be a bool")
        if not isinstance(self.coverage, (int, float)) or not 0.0 <= self.coverage <= 1.0:
            raise ValueError(f"coverage must be in [0, 1], got {self.coverage!r}")
        if not isinstance(self.source_fingerprint, str):
            raise ValueError("source_fingerprint must be a string")
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))


@dataclass(frozen=True)
class UniversePairDecision:
    """Explainable inclusion/exclusion decision for a single pair."""

    pair: str
    decision: UniversePairDecisionKind
    state: UniversePairState
    classification: UniversePairClassification
    rank: int
    score: float | None = None
    coverage: float | None = None
    relative_strength_score: float | None = None
    discovery_score: float | None = None
    estimated_quote_volume: Decimal | None = None
    source_fingerprint: str = ""
    reason_codes: tuple[str, ...] = ()
    metadata: Any = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.pair, str) or not self.pair.strip():
            raise ValueError("pair must be a non-empty string")
        if not isinstance(self.rank, int) or self.rank < 0:
            raise ValueError("rank must be a non-negative integer")
        if self.score is not None and (not isinstance(self.score, (int, float)) or self.score < 0.0):
            raise ValueError(f"score must be a non-negative number or None, got {self.score!r}")
        if self.coverage is not None and (
            not isinstance(self.coverage, (int, float)) or not 0.0 <= self.coverage <= 1.0
        ):
            raise ValueError(f"coverage must be in [0, 1] or None, got {self.coverage!r}")
        if self.relative_strength_score is not None and (
            not isinstance(self.relative_strength_score, (int, float))
            or not 0.0 <= self.relative_strength_score <= 100.0
        ):
            raise ValueError(
                f"relative_strength_score must be in [0, 100] or None, got {self.relative_strength_score!r}"
            )
        if self.discovery_score is not None and (
            not isinstance(self.discovery_score, (int, float))
            or not 0.0 <= self.discovery_score <= 100.0
        ):
            raise ValueError(
                f"discovery_score must be in [0, 100] or None, got {self.discovery_score!r}"
            )
        if self.estimated_quote_volume is not None and not isinstance(
            self.estimated_quote_volume, Decimal
        ):
            raise ValueError(
                f"estimated_quote_volume must be a Decimal or None, got {self.estimated_quote_volume!r}"
            )
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))


# ---------------------------------------------------------------------------
# Universe results
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CandidateUniverseResult:
    """Deterministic candidate universe built through the existing research chain."""

    decisions: tuple[UniversePairDecision, ...]
    pairlist: dict[str, Any]
    fingerprint: str
    safety_flags: ResearchUniverseSafetyFlags
    reason_codes: tuple[str, ...]
    metadata: Any = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "decisions", tuple(self.decisions))
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))
        if not isinstance(self.pairlist, dict):
            raise ValueError(f"pairlist must be a dict, got {self.pairlist!r}")
        if not isinstance(self.fingerprint, str) or not self.fingerprint.strip():
            raise ValueError("fingerprint must be a non-empty string")
        if not isinstance(self.safety_flags, ResearchUniverseSafetyFlags):
            raise ValueError(
                f"safety_flags must be ResearchUniverseSafetyFlags, got {self.safety_flags!r}"
            )
        for code in self.reason_codes:
            if code not in RESEARCH_UNIVERSE_REASON_CODES:
                raise ValueError(f"unsupported reason code: {code}")

    @property
    def pairs(self) -> tuple[str, ...]:
        """Included candidate pairs in rank order."""
        return tuple(
            d.pair for d in self.decisions if d.decision == UniversePairDecisionKind.INCLUDED
        )


@dataclass(frozen=True)
class BaselineUniverseResult:
    """Deterministic baseline universe ranked by selection-window quote volume."""

    decisions: tuple[UniversePairDecision, ...]
    pairlist: dict[str, Any]
    fingerprint: str
    safety_flags: ResearchUniverseSafetyFlags
    reason_codes: tuple[str, ...]
    metadata: Any = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "decisions", tuple(self.decisions))
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))
        if not isinstance(self.pairlist, dict):
            raise ValueError(f"pairlist must be a dict, got {self.pairlist!r}")
        if not isinstance(self.fingerprint, str) or not self.fingerprint.strip():
            raise ValueError("fingerprint must be a non-empty string")
        if not isinstance(self.safety_flags, ResearchUniverseSafetyFlags):
            raise ValueError(
                f"safety_flags must be ResearchUniverseSafetyFlags, got {self.safety_flags!r}"
            )
        for code in self.reason_codes:
            if code not in RESEARCH_UNIVERSE_REASON_CODES:
                raise ValueError(f"unsupported reason code: {code}")

    @property
    def pairs(self) -> tuple[str, ...]:
        """Included baseline pairs in rank order."""
        return tuple(
            d.pair for d in self.decisions if d.decision == UniversePairDecisionKind.INCLUDED
        )


@dataclass(frozen=True)
class ResearchUniverseComparison:
    """Comparison between candidate and baseline universes."""

    overlap: tuple[str, ...]
    candidate_only: tuple[str, ...]
    baseline_only: tuple[str, ...]
    union_count: int
    jaccard_similarity: float
    fingerprint: str
    safety_flags: ResearchUniverseSafetyFlags
    reason_codes: tuple[str, ...]
    metadata: Any = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "overlap", tuple(self.overlap))
        object.__setattr__(self, "candidate_only", tuple(self.candidate_only))
        object.__setattr__(self, "baseline_only", tuple(self.baseline_only))
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))
        if not isinstance(self.union_count, int) or self.union_count < 0:
            raise ValueError("union_count must be a non-negative int")
        if not isinstance(self.jaccard_similarity, (int, float)) or not 0.0 <= self.jaccard_similarity <= 1.0:
            raise ValueError(
                f"jaccard_similarity must be in [0, 1], got {self.jaccard_similarity!r}"
            )
        if not isinstance(self.fingerprint, str) or not self.fingerprint.strip():
            raise ValueError("fingerprint must be a non-empty string")
        if not isinstance(self.safety_flags, ResearchUniverseSafetyFlags):
            raise ValueError(
                f"safety_flags must be ResearchUniverseSafetyFlags, got {self.safety_flags!r}"
            )
        for code in self.reason_codes:
            if code not in RESEARCH_UNIVERSE_REASON_CODES:
                raise ValueError(f"unsupported reason code: {code}")


@dataclass(frozen=True)
class ResearchUniverseManifest:
    """Manifest recording inputs, versions, and fingerprints for audit."""

    version: str
    spec_version: str
    research_universe_version: str
    generated_at: datetime
    bundle_fingerprint: str
    policy_fingerprint: str
    selection_window: SelectionWindow
    candidate_fingerprint: str
    baseline_fingerprint: str
    comparison_fingerprint: str
    safety_flags: ResearchUniverseSafetyFlags
    reason_codes: tuple[str, ...]
    metadata: Any = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.generated_at, datetime) or self.generated_at.tzinfo is None:
            raise ValueError("generated_at must be a timezone-aware datetime")
        for name, value in (
            ("bundle_fingerprint", self.bundle_fingerprint),
            ("policy_fingerprint", self.policy_fingerprint),
            ("candidate_fingerprint", self.candidate_fingerprint),
            ("baseline_fingerprint", self.baseline_fingerprint),
            ("comparison_fingerprint", self.comparison_fingerprint),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if not isinstance(self.safety_flags, ResearchUniverseSafetyFlags):
            raise ValueError(
                f"safety_flags must be ResearchUniverseSafetyFlags, got {self.safety_flags!r}"
            )
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))
        for code in self.reason_codes:
            if code not in RESEARCH_UNIVERSE_REASON_CODES:
                raise ValueError(f"unsupported reason code: {code}")


@dataclass(frozen=True)
class ResearchUniverseReport:
    """Top-level dual-universe report."""

    version: str
    spec_version: str
    config: ResearchUniverseConfig
    manifest: ResearchUniverseManifest
    candidate: CandidateUniverseResult
    baseline: BaselineUniverseResult
    comparison: ResearchUniverseComparison
    safety_flags: ResearchUniverseSafetyFlags
    reason_codes: tuple[str, ...]
    fingerprint: str
    human_approval_required: bool = True
    research_only: bool = True
    metadata: Any = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))
        if not isinstance(self.version, str) or not self.version.strip():
            raise ValueError("version must be a non-empty string")
        if not isinstance(self.spec_version, str) or not self.spec_version.strip():
            raise ValueError("spec_version must be a non-empty string")
        if not isinstance(self.fingerprint, str) or not self.fingerprint.strip():
            raise ValueError("fingerprint must be a non-empty string")
        if not isinstance(self.human_approval_required, bool):
            raise ValueError("human_approval_required must be a boolean")
        if not isinstance(self.research_only, bool):
            raise ValueError("research_only must be a boolean")
        if not isinstance(self.safety_flags, ResearchUniverseSafetyFlags):
            raise ValueError(
                f"safety_flags must be ResearchUniverseSafetyFlags, got {self.safety_flags!r}"
            )
        for code in self.reason_codes:
            if code not in RESEARCH_UNIVERSE_REASON_CODES:
                raise ValueError(f"unsupported reason code: {code}")


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ResearchUniverseError(Exception):
    """Base exception for the research universe builder."""


class ResearchUniverseConfigError(ResearchUniverseError):
    """Invalid configuration."""


class ResearchUniverseBundleError(ResearchUniverseError):
    """Invalid or missing research market data bundle."""


class ResearchUniverseValidationError(ResearchUniverseError):
    """Validation failure."""


class ResearchUniverseWriterError(ResearchUniverseError):
    """Writer failure."""

    def __init__(self, message: str, reason_code: str | None = None) -> None:
        super().__init__(message)
        self.reason_code = reason_code
