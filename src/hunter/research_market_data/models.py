"""Frozen dataclasses for hunter.research_market_data (MVP-63 / SPEC-064).

All models are frozen dataclasses. Validation runs in ``__post_init__``.
The package is read-only, research-only, and does not perform any network,
exchange, Freqtrade, database, scheduler, or trading operation.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from types import MappingProxyType
from typing import Any

from hunter.research_market_data.errors import (
    ResearchMarketDataConfigError,
)

RESEARCH_MARKET_DATA_VERSION = "0.63.0-dev"
SPEC_VERSION = "SPEC-064"

# ---------------------------------------------------------------------------
# Reason codes — deterministic, machine-readable strings.
# ---------------------------------------------------------------------------

INVALID_CONFIG = "INVALID_CONFIG"
INVALID_SAFETY_FLAGS = "INVALID_SAFETY_FLAGS"
INVALID_FILE_PATH = "INVALID_FILE_PATH"
FORBIDDEN_PATH = "FORBIDDEN_PATH"
MISSING_FILE = "MISSING_FILE"
EMPTY_FILE = "EMPTY_FILE"
INVALID_CSV_HEADER = "INVALID_CSV_HEADER"
MISSING_COLUMN = "MISSING_COLUMN"
AMBIGUOUS_COLUMN = "AMBIGUOUS_COLUMN"
TIMESTAMP_PARSE_ERROR = "TIMESTAMP_PARSE_ERROR"
NAIVE_TIMESTAMP = "NAIVE_TIMESTAMP"
NON_UTC_TIMESTAMP = "NON_UTC_TIMESTAMP"
INVALID_NUMERIC = "INVALID_NUMERIC"
NON_FINITE_VALUE = "NON_FINITE_VALUE"
NEGATIVE_OR_ZERO_PRICE = "NEGATIVE_OR_ZERO_PRICE"
NEGATIVE_VOLUME = "NEGATIVE_VOLUME"
INVALID_OHLC_RELATION = "INVALID_OHLC_RELATION"
DUPLICATE_TIMESTAMP = "DUPLICATE_TIMESTAMP"
OUT_OF_ORDER_INPUT = "OUT_OF_ORDER_INPUT"
UNSUPPORTED_TIMEFRAME = "UNSUPPORTED_TIMEFRAME"
INSUFFICIENT_COVERAGE = "INSUFFICIENT_COVERAGE"
GAPS_FOUND = "GAPS_FOUND"
BELOW_MIN_ROWS = "BELOW_MIN_ROWS"
SYMBOL_NORMALIZATION_FAILED = "SYMBOL_NORMALIZATION_FAILED"
UNSUPPORTED_QUOTE_CURRENCY = "UNSUPPORTED_QUOTE_CURRENCY"
UNSAFE_SYMBOL_CONTENT = "UNSAFE_SYMBOL_CONTENT"
LEVERAGED_TOKEN_EXCLUDED = "LEVERAGED_TOKEN_EXCLUDED"
STABLECOIN_PAIR_EXCLUDED = "STABLECOIN_PAIR_EXCLUDED"
BTC_BENCHMARK_MISSING = "BTC_BENCHMARK_MISSING"
ETH_BENCHMARK_MISSING = "ETH_BENCHMARK_MISSING"
ALL_CANDIDATES_EXCLUDED = "ALL_CANDIDATES_EXCLUDED"
BTC_ONLY_MODE = "BTC_ONLY_MODE"
INPUTS_ALREADY_LOADED = "INPUTS_ALREADY_LOADED"
NO_NETWORK_CONNECTION = "NO_NETWORK_CONNECTION"
NO_DATABASE_CONNECTION = "NO_DATABASE_CONNECTION"
NO_FILE_READ_IN_ENGINE = "NO_FILE_READ_IN_ENGINE"
NO_ACTION_COMMANDS_EMITTED = "NO_ACTION_COMMANDS_EMITTED"
HUMAN_RESEARCH_ONLY = "HUMAN_RESEARCH_ONLY"

RESEARCH_MARKET_DATA_REASON_CODES: tuple[str, ...] = (
    INVALID_CONFIG,
    INVALID_SAFETY_FLAGS,
    INVALID_FILE_PATH,
    FORBIDDEN_PATH,
    MISSING_FILE,
    EMPTY_FILE,
    INVALID_CSV_HEADER,
    MISSING_COLUMN,
    AMBIGUOUS_COLUMN,
    TIMESTAMP_PARSE_ERROR,
    NAIVE_TIMESTAMP,
    NON_UTC_TIMESTAMP,
    INVALID_NUMERIC,
    NON_FINITE_VALUE,
    NEGATIVE_OR_ZERO_PRICE,
    NEGATIVE_VOLUME,
    INVALID_OHLC_RELATION,
    DUPLICATE_TIMESTAMP,
    OUT_OF_ORDER_INPUT,
    UNSUPPORTED_TIMEFRAME,
    INSUFFICIENT_COVERAGE,
    GAPS_FOUND,
    BELOW_MIN_ROWS,
    SYMBOL_NORMALIZATION_FAILED,
    UNSUPPORTED_QUOTE_CURRENCY,
    UNSAFE_SYMBOL_CONTENT,
    LEVERAGED_TOKEN_EXCLUDED,
    STABLECOIN_PAIR_EXCLUDED,
    BTC_BENCHMARK_MISSING,
    ETH_BENCHMARK_MISSING,
    ALL_CANDIDATES_EXCLUDED,
    BTC_ONLY_MODE,
    INPUTS_ALREADY_LOADED,
    NO_NETWORK_CONNECTION,
    NO_DATABASE_CONNECTION,
    NO_FILE_READ_IN_ENGINE,
    NO_ACTION_COMMANDS_EMITTED,
    HUMAN_RESEARCH_ONLY,
)


# ---------------------------------------------------------------------------
# Validation helpers.
# ---------------------------------------------------------------------------

def _coerce_tuple_strs(value: Sequence[str] | tuple[str, ...] | None) -> tuple[str, ...]:
    """Coerce a sequence of strings into a tuple of non-empty strings."""
    if value is None:
        return ()
    if isinstance(value, (tuple, list)):
        for item in value:
            if not isinstance(item, str) or not item:
                raise ValueError("reason codes must be non-empty strings")
        return tuple(value)
    raise ValueError("reason codes must be a sequence of strings")


def _coerce_mapping_strs(value: Mapping[str, str] | dict[str, str] | None) -> Mapping[str, str]:
    """Coerce a mapping into an immutable MappingProxyType of strings."""
    if value is None:
        return MappingProxyType({})
    if isinstance(value, Mapping):
        return MappingProxyType({str(k): str(v) for k, v in value.items()})
    raise ValueError("metadata must be a mapping of strings")


def _validate_decimal_range(value: Any, low: Decimal, high: Decimal, name: str) -> Decimal:
    """Validate a Decimal is within an inclusive range."""
    if not isinstance(value, Decimal):
        raise ValueError(f"{name} must be a Decimal")
    if not value.is_finite() or value < low or value > high:
        raise ValueError(f"{name} must be a finite Decimal in [{low}, {high}]")
    return value


# ---------------------------------------------------------------------------
# Safety flags — mandatory research-only invariants.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MarketDataSafetyFlags:
    """Fail-closed safety invariants for every public output."""

    research_only: bool = True
    execution_approval_granted: bool = False
    production_approval_granted: bool = False
    live_trading_allowed: bool = False
    automatic_execution_allowed: bool = False

    def __post_init__(self) -> None:
        if self.research_only is not True:
            raise ValueError("research_only must be True")
        if self.execution_approval_granted is not False:
            raise ValueError("execution_approval_granted must be False")
        if self.production_approval_granted is not False:
            raise ValueError("production_approval_granted must be False")
        if self.live_trading_allowed is not False:
            raise ValueError("live_trading_allowed must be False")
        if self.automatic_execution_allowed is not False:
            raise ValueError("automatic_execution_allowed must be False")


# ---------------------------------------------------------------------------
# Configuration and file contracts.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ResearchMarketDataConfig:
    """Configuration for the research market data loader and bundle builder."""

    coverage_threshold: Decimal = field(default_factory=lambda: Decimal("0.98"))
    min_required_rows: int = 30
    lookback_days: tuple[int, ...] = (7, 14, 30)
    required_quote_currency: str = "USDT"
    max_leading_stablecoins: int = 0
    safety_flags: MarketDataSafetyFlags = field(default_factory=MarketDataSafetyFlags)
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_decimal_range(
            self.coverage_threshold, Decimal("0"), Decimal("1"), "coverage_threshold"
        )
        if not isinstance(self.min_required_rows, int) or self.min_required_rows < 2:
            raise ValueError("min_required_rows must be an integer >= 2")
        if any(not isinstance(d, int) or d <= 0 for d in self.lookback_days):
            raise ValueError("lookback_days must be positive integers")
        if not isinstance(self.required_quote_currency, str) or not self.required_quote_currency:
            raise ValueError("required_quote_currency must be a non-empty string")
        if not isinstance(self.safety_flags, MarketDataSafetyFlags):
            raise ValueError("safety_flags must be a MarketDataSafetyFlags instance")
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))


@dataclass(frozen=True)
class MarketDataFileSpec:
    """Caller-provided description of a single CSV file to load."""

    path: Path
    expected_symbol: str | None = None
    source_label: str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.path, str):
            object.__setattr__(self, "path", Path(self.path))
        if not isinstance(self.path, Path):
            raise ValueError("path must be a Path or string")
        if self.expected_symbol is not None and (
            not isinstance(self.expected_symbol, str) or not self.expected_symbol
        ):
            raise ValueError("expected_symbol must be a non-empty string when provided")
        if self.source_label is not None and (
            not isinstance(self.source_label, str) or not self.source_label
        ):
            raise ValueError("source_label must be a non-empty string when provided")


@dataclass(frozen=True)
class MarketDataSourceRef:
    """Immutable provenance reference for a loaded CSV file."""

    source_id: str
    path: Path
    label: str
    row_count: int
    file_hash: str

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, str) or not self.source_id:
            raise ValueError("source_id must be a non-empty string")
        if not isinstance(self.path, Path):
            raise ValueError("path must be a Path")
        if not isinstance(self.label, str) or not self.label:
            raise ValueError("label must be a non-empty string")
        if not isinstance(self.row_count, int) or self.row_count < 0:
            raise ValueError("row_count must be a non-negative integer")
        if not isinstance(self.file_hash, str) or not self.file_hash:
            raise ValueError("file_hash must be a non-empty string")


# ---------------------------------------------------------------------------
# Raw and normalized candle models.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RawCandleRow:
    """A single raw candle row loaded from a CSV file."""

    source: MarketDataSourceRef
    line_number: int
    timestamp_raw: str
    open_raw: str
    high_raw: str
    low_raw: str
    close_raw: str
    volume_raw: str

    def __post_init__(self) -> None:
        if not isinstance(self.source, MarketDataSourceRef):
            raise ValueError("source must be a MarketDataSourceRef")
        if not isinstance(self.line_number, int) or self.line_number < 1:
            raise ValueError("line_number must be a positive integer")
        for field_name in (
            "timestamp_raw",
            "open_raw",
            "high_raw",
            "low_raw",
            "close_raw",
            "volume_raw",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, str):
                raise ValueError(f"{field_name} must be a string")


@dataclass(frozen=True)
class NormalizedCandle:
    """A single validated, normalized candle."""

    timestamp: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    pair: str
    timeframe: str
    quote_volume: Decimal | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.timestamp, datetime) or self.timestamp.tzinfo is None:
            raise ValueError("timestamp must be a timezone-aware datetime")
        for field_name, must_be_positive in (
            ("open", True),
            ("high", True),
            ("low", True),
            ("close", True),
            ("volume", False),
        ):
            value = getattr(self, field_name)
            if not isinstance(value, Decimal):
                raise ValueError(f"{field_name} must be a Decimal")
            if not value.is_finite():
                raise ValueError(f"{field_name} must be a finite Decimal")
            if value <= Decimal("0") and must_be_positive:
                raise ValueError(f"{field_name} must be positive")
            if value < Decimal("0") and not must_be_positive:
                raise ValueError(f"{field_name} must be non-negative")
        if not isinstance(self.pair, str) or not self.pair:
            raise ValueError("pair must be a non-empty string")
        if not isinstance(self.timeframe, str) or not self.timeframe:
            raise ValueError("timeframe must be a non-empty string")
        if self.high < self.low:
            raise ValueError("high must be >= low")
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("high must be >= max(open, close, low)")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("low must be <= min(open, close, high)")
        if self.quote_volume is not None:
            if not isinstance(self.quote_volume, Decimal) or not self.quote_volume.is_finite():
                raise ValueError("quote_volume must be a finite Decimal")
            if self.quote_volume < Decimal("0"):
                raise ValueError("quote_volume must be non-negative")


@dataclass(frozen=True)
class MissingInterval:
    """A contiguous interval where candles are missing from the expected grid."""

    start: datetime
    end: datetime
    expected_count: int
    actual_count: int
    reason_code: str

    def __post_init__(self) -> None:
        if not isinstance(self.start, datetime) or self.start.tzinfo is None:
            raise ValueError("start must be a timezone-aware datetime")
        if not isinstance(self.end, datetime) or self.end.tzinfo is None:
            raise ValueError("end must be a timezone-aware datetime")
        if self.start > self.end:
            raise ValueError("start must be <= end")
        if not isinstance(self.expected_count, int) or self.expected_count < 0:
            raise ValueError("expected_count must be a non-negative integer")
        if not isinstance(self.actual_count, int) or self.actual_count < 0:
            raise ValueError("actual_count must be a non-negative integer")
        if not isinstance(self.reason_code, str) or not self.reason_code:
            raise ValueError("reason_code must be a non-empty string")


@dataclass(frozen=True)
class CandleSeries:
    """A validated, normalized candle series for a single pair."""

    pair: str
    timeframe: str
    candles: tuple[NormalizedCandle, ...]
    source: MarketDataSourceRef
    coverage: Decimal
    coverage_threshold: Decimal
    missing_intervals: tuple[MissingInterval, ...]
    reason_codes: tuple[str, ...]
    metadata: Mapping[str, str]

    def __post_init__(self) -> None:
        if not isinstance(self.pair, str) or not self.pair:
            raise ValueError("pair must be a non-empty string")
        if not isinstance(self.timeframe, str) or not self.timeframe:
            raise ValueError("timeframe must be a non-empty string")
        if not isinstance(self.source, MarketDataSourceRef):
            raise ValueError("source must be a MarketDataSourceRef")
        _validate_decimal_range(
            self.coverage, Decimal("0"), Decimal("1"), "coverage"
        )
        _validate_decimal_range(
            self.coverage_threshold, Decimal("0"), Decimal("1"), "coverage_threshold"
        )
        if not isinstance(self.candles, tuple):
            raise ValueError("candles must be a tuple")
        for candle in self.candles:
            if not isinstance(candle, NormalizedCandle):
                raise ValueError("candles must contain NormalizedCandle instances")
            if candle.pair != self.pair:
                raise ValueError("candle pair must match series pair")
            if candle.timeframe != self.timeframe:
                raise ValueError("candle timeframe must match series timeframe")
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))

    @property
    def timestamps(self) -> tuple[datetime, ...]:
        """Return the ordered tuple of candle timestamps."""
        return tuple(candle.timestamp for candle in self.candles)


@dataclass(frozen=True)
class ExcludedMarketDataInput:
    """A single market data input that was excluded from the bundle."""

    source: MarketDataSourceRef
    reason_codes: tuple[str, ...]
    message: str

    def __post_init__(self) -> None:
        if not isinstance(self.source, MarketDataSourceRef):
            raise ValueError("source must be a MarketDataSourceRef")
        if not isinstance(self.message, str):
            raise ValueError("message must be a string")
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))


# ---------------------------------------------------------------------------
# Manifest and bundle.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ResearchMarketDataManifest:
    """Immutable provenance manifest for a research market data bundle."""

    schema_version: str
    generated_at: datetime
    sources: tuple[MarketDataSourceRef, ...]
    series_fingerprints: Mapping[str, str]
    btc_fingerprint: str
    eth_fingerprint: str | None
    policy_fingerprint: str
    bundle_fingerprint: str
    safety_flags: MarketDataSafetyFlags
    metadata: Mapping[str, str]
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.schema_version, str) or not self.schema_version:
            raise ValueError("schema_version must be a non-empty string")
        if not isinstance(self.generated_at, datetime) or self.generated_at.tzinfo is None:
            raise ValueError("generated_at must be a timezone-aware datetime")
        if not isinstance(self.sources, tuple):
            raise ValueError("sources must be a tuple")
        for source in self.sources:
            if not isinstance(source, MarketDataSourceRef):
                raise ValueError("sources must contain MarketDataSourceRef instances")
        if not isinstance(self.series_fingerprints, Mapping):
            raise ValueError("series_fingerprints must be a mapping")
        if not isinstance(self.btc_fingerprint, str) or not self.btc_fingerprint:
            raise ValueError("btc_fingerprint must be a non-empty string")
        if self.eth_fingerprint is not None and (
            not isinstance(self.eth_fingerprint, str) or not self.eth_fingerprint
        ):
            raise ValueError("eth_fingerprint must be a non-empty string when provided")
        if not isinstance(self.policy_fingerprint, str) or not self.policy_fingerprint:
            raise ValueError("policy_fingerprint must be a non-empty string")
        if not isinstance(self.bundle_fingerprint, str) or not self.bundle_fingerprint:
            raise ValueError("bundle_fingerprint must be a non-empty string")
        if not isinstance(self.safety_flags, MarketDataSafetyFlags):
            raise ValueError("safety_flags must be a MarketDataSafetyFlags instance")
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))


@dataclass(frozen=True)
class ResearchMarketDataBundle:
    """Immutable, deterministic research market data bundle."""

    config: ResearchMarketDataConfig
    manifest: ResearchMarketDataManifest
    candidates: tuple[CandleSeries, ...]
    btc_series: CandleSeries
    eth_series: CandleSeries | None
    exclusions: tuple[ExcludedMarketDataInput, ...]
    safety_flags: MarketDataSafetyFlags
    reason_codes: tuple[str, ...]
    metadata: Mapping[str, str]

    def __post_init__(self) -> None:
        if not isinstance(self.config, ResearchMarketDataConfig):
            raise ValueError("config must be a ResearchMarketDataConfig")
        if not isinstance(self.manifest, ResearchMarketDataManifest):
            raise ValueError("manifest must be a ResearchMarketDataManifest")
        if not isinstance(self.btc_series, CandleSeries):
            raise ValueError("btc_series must be a CandleSeries")
        if self.eth_series is not None and not isinstance(self.eth_series, CandleSeries):
            raise ValueError("eth_series must be a CandleSeries or None")
        if not isinstance(self.candidates, tuple):
            raise ValueError("candidates must be a tuple")
        for series in self.candidates:
            if not isinstance(series, CandleSeries):
                raise ValueError("candidates must contain CandleSeries instances")
        if not isinstance(self.exclusions, tuple):
            raise ValueError("exclusions must be a tuple")
        for exclusion in self.exclusions:
            if not isinstance(exclusion, ExcludedMarketDataInput):
                raise ValueError("exclusions must contain ExcludedMarketDataInput instances")
        if not isinstance(self.safety_flags, MarketDataSafetyFlags):
            raise ValueError("safety_flags must be a MarketDataSafetyFlags instance")
        object.__setattr__(self, "reason_codes", _coerce_tuple_strs(self.reason_codes))
        object.__setattr__(self, "metadata", _coerce_mapping_strs(self.metadata))


# ---------------------------------------------------------------------------
# Adapter output models.
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RelativeStrengthRunInputs:
    """Inputs ready for the existing Relative Strength engine."""

    candidates: tuple[Any, ...]
    btc: tuple[Any, ...]
    eth: tuple[Any, ...] | None

    def __post_init__(self) -> None:
        if not isinstance(self.candidates, tuple):
            raise ValueError("candidates must be a tuple")
        if not isinstance(self.btc, tuple):
            raise ValueError("btc must be a tuple")
        if self.eth is not None and not isinstance(self.eth, tuple):
            raise ValueError("eth must be a tuple or None")


@dataclass(frozen=True)
class DiscoveryInputBundle:
    """Inputs ready for the existing Discovery engine."""

    inputs: tuple[Any, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.inputs, tuple):
            raise ValueError("inputs must be a tuple")
