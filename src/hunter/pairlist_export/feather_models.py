"""Frozen models, reason codes, and errors for the Freqtrade Feather
ranking-input adapter (SPEC-075).

All models describe already-loaded, already-validated local data. Nothing in
this module opens a network connection, talks to an exchange, or mutates any
source file. Discovery and validation are read-only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Mapping

from hunter.pairlist_export.models import PairlistExportError

# ---------------------------------------------------------------------------
# Discovery reason codes.
# ---------------------------------------------------------------------------

FILENAME_NOT_MATCHED = "FILENAME_NOT_MATCHED"
SYMLINK_REJECTED = "SYMLINK_REJECTED"
HIDDEN_OR_TEMP_FILE = "HIDDEN_OR_TEMP_FILE"
PATH_ESCAPE_REJECTED = "PATH_ESCAPE_REJECTED"
DUPLICATE_PAIR_SOURCE = "DUPLICATE_PAIR_SOURCE"
NOT_A_FILE = "NOT_A_FILE"

# ---------------------------------------------------------------------------
# Schema / value / timestamp validation reason codes.
# ---------------------------------------------------------------------------

MISSING_COLUMN = "MISSING_COLUMN"
UNREADABLE_FEATHER_FILE = "UNREADABLE_FEATHER_FILE"
INVALID_TIMESTAMP = "INVALID_TIMESTAMP"
DUPLICATE_CANDLES = "DUPLICATE_CANDLES"
OUT_OF_ORDER_CANDLES = "OUT_OF_ORDER_CANDLES"
INVALID_CLOSE = "INVALID_CLOSE"
INVALID_VOLUME = "INVALID_VOLUME"
FUTURE_CANDLE = "FUTURE_CANDLE"
INSUFFICIENT_LOOKBACK = "INSUFFICIENT_LOOKBACK"

# ---------------------------------------------------------------------------
# Data-quality reason codes (per-pair, over the 90-day window).
# ---------------------------------------------------------------------------

DATA_COMPLETE = "DATA_COMPLETE"
DATA_GAPS_PRESENT = "DATA_GAPS_PRESENT"

# ---------------------------------------------------------------------------
# Universe / benchmark reason codes.
# ---------------------------------------------------------------------------

BTC_BENCHMARK_MISSING = "BTC_BENCHMARK_MISSING"

FEATHER_REASON_CODES: frozenset[str] = frozenset(
    {
        FILENAME_NOT_MATCHED,
        SYMLINK_REJECTED,
        HIDDEN_OR_TEMP_FILE,
        PATH_ESCAPE_REJECTED,
        DUPLICATE_PAIR_SOURCE,
        NOT_A_FILE,
        MISSING_COLUMN,
        UNREADABLE_FEATHER_FILE,
        INVALID_TIMESTAMP,
        DUPLICATE_CANDLES,
        OUT_OF_ORDER_CANDLES,
        INVALID_CLOSE,
        INVALID_VOLUME,
        FUTURE_CANDLE,
        INSUFFICIENT_LOOKBACK,
        DATA_COMPLETE,
        DATA_GAPS_PRESENT,
        BTC_BENCHMARK_MISSING,
    }
)

REQUIRED_FEATHER_COLUMNS: tuple[str, ...] = ("date", "close", "volume")

# `BASE_USDT_USDT-1h-futures.feather` exactly -- no spot, mark, funding-rate,
# other-timeframe, or decorated variants match.
FEATHER_FILENAME_PATTERN = r"^(?P<base>[A-Z0-9]+)_USDT_USDT-1h-futures\.feather$"


# ---------------------------------------------------------------------------
# Errors.
# ---------------------------------------------------------------------------


class FeatherAdapterError(PairlistExportError):
    """Base error for the Feather ranking-input adapter."""


class FeatherDiscoveryError(FeatherAdapterError):
    """Raised for fatal discovery-time failures (e.g. missing data-dir)."""


class FeatherValidationError(FeatherAdapterError):
    """Raised for fatal validation-time failures."""


# ---------------------------------------------------------------------------
# Discovery models.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FeatherFileRef:
    """A single discovered, filename-validated, path-contained Feather file."""

    path: Path
    base_symbol: str
    pair: str


@dataclass(frozen=True)
class FeatherExclusion:
    """A file or pair excluded at discovery or validation time."""

    path: Path
    reason_codes: tuple[str, ...]
    message: str


@dataclass(frozen=True)
class FeatherDiscoveryResult:
    """Result of scanning a data directory for `*-1h-futures.feather` files."""

    included: tuple[FeatherFileRef, ...]
    excluded: tuple[FeatherExclusion, ...]
    btc_ref: FeatherFileRef | None
    eth_ref: FeatherFileRef | None


# ---------------------------------------------------------------------------
# Per-pair evidence (used for both ranking-input construction and audit).
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FeatherPairEvidence:
    """Validated, windowed evidence for a single candidate pair."""

    pair: str
    path: Path
    included: bool
    rows_in_window: int
    expected_slots: int
    data_quality_pct: Decimal | None
    liquidity_raw: float | None
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class FeatherRunMetadata:
    """Non-semantic provenance metadata for a Feather ranking-input run."""

    source: str
    timeframe: str
    rs_lookback_days: int
    liquidity_lookback_days: int
    oi_available: bool
    universe_size_at_scoring: int
    universe_fingerprint: str
    extra: Mapping[str, str] = field(default_factory=dict)
