"""Frozen models and contracts for daily coin universe ranking and native
Freqtrade RemotePairList export (SPEC-074).

The pairlist-export pipeline transforms existing Hunter research outputs
(relative strength, open interest, eligible universe) into a deterministic,
explainable shortlist published as native RemotePairList JSON for Freqtrade
file:/// consumption.

All models are frozen dataclasses.  Safety flags are immutable invariants
(construction with a violating value raises :exc:`ValueError`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Mapping

# ---------------------------------------------------------------------------
# Package version and spec identifier
# ---------------------------------------------------------------------------

PAIRLIST_EXPORT_VERSION: str = "0.1.0"
SPEC_074: str = "SPEC-074"

# ---------------------------------------------------------------------------
# Reason codes
# ---------------------------------------------------------------------------

# Positive (selected) reason codes
REASON_RS_SCORE = "RS_SCORE"
REASON_OI_LIQUIDITY = "OI_LIQUIDITY"
REASON_DATA_SUFFICIENCY = "DATA_SUFFICIENCY"
REASON_LIQUIDITY_SCORE = "LIQUIDITY_SCORE"

# SPEC-075 profile validation
REASON_PROFILE_FIELD_MISMATCH = "PROFILE_FIELD_MISMATCH"
REASON_PROFILE_EVIDENCE_INCOMPLETE = "PROFILE_EVIDENCE_INCOMPLETE"

# Ineligibility / exclusion reason codes
REASON_INELIGIBLE_STABLECOIN = "INELIGIBLE_STABLECOIN"
REASON_INELIGIBLE_LEVERAGED = "INELIGIBLE_LEVERAGED"
REASON_INELIGIBLE_BENCHMARK = "INELIGIBLE_BENCHMARK"
REASON_INVALID_PAIR_FORMAT = "INVALID_PAIR_FORMAT"
REASON_DUPLICATE_PAIR = "DUPLICATE_PAIR"
REASON_INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
REASON_INELIGIBLE_PAIR = "INELIGIBLE_PAIR"
REASON_UNKNOWN_PAIR = "UNKNOWN_PAIR"

# Publish-gate reason codes
REASON_BELOW_MIN_PAIRS = "BELOW_MIN_PAIRS"
REASON_ABOVE_MAX_PAIRS = "ABOVE_MAX_PAIRS"
REASON_EMPTY_UNIVERSE = "EMPTY_UNIVERSE"
REASON_INVALID_OUTPUT_PATH = "INVALID_OUTPUT_PATH"
REASON_WRITE_FAILED = "WRITE_FAILED"
REASON_VALIDATION_FAILED = "VALIDATION_FAILED"

# Canonical frozenset of all reason codes
PAIRLIST_REASON_CODES: frozenset[str] = frozenset(
    {
        REASON_RS_SCORE,
        REASON_OI_LIQUIDITY,
        REASON_DATA_SUFFICIENCY,
        REASON_LIQUIDITY_SCORE,
        REASON_PROFILE_FIELD_MISMATCH,
        REASON_PROFILE_EVIDENCE_INCOMPLETE,
        REASON_INELIGIBLE_STABLECOIN,
        REASON_INELIGIBLE_LEVERAGED,
        REASON_INELIGIBLE_BENCHMARK,
        REASON_INVALID_PAIR_FORMAT,
        REASON_DUPLICATE_PAIR,
        REASON_INSUFFICIENT_EVIDENCE,
        REASON_INELIGIBLE_PAIR,
        REASON_UNKNOWN_PAIR,
        REASON_BELOW_MIN_PAIRS,
        REASON_ABOVE_MAX_PAIRS,
        REASON_EMPTY_UNIVERSE,
        REASON_INVALID_OUTPUT_PATH,
        REASON_WRITE_FAILED,
        REASON_VALIDATION_FAILED,
    }
)

# ---------------------------------------------------------------------------
# Pair format constants
# ---------------------------------------------------------------------------

# A valid USDT-M futures pair matches BASE/QUOTE:SETTLE where
# SETTLE is USDT.  The QUOTE is typically USDT for linear contracts.
_VALID_SETTLE: frozenset[str] = frozenset({"USDT"})

# ---------------------------------------------------------------------------
# Safety flags — immutable invariants
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PairlistExportSafetyFlags:
    """Research-only safety invariants for pairlist export artifacts.

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


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PairlistRankingConfig:
    """Deterministic configuration for daily pairlist ranking and publishing.

    Defaults match the SPEC-074 decisions:
    - Hunter publishes up to 30 candidates.
    - Freqtrade native filters may reduce to ~20.
    - Minimum 5 pairs required for safety.
    - Maximum 50 pairs (reject oversized lists).
    - RemotePairList refresh_period: 3600 seconds.
    """

    min_pairs: int = 5
    target_final_pairs: int = 20
    publish_candidates: int = 30
    max_pairs: int = 50
    refresh_period: int = 3600

    # Paths for atomic publish output.
    pairlist_file: str | None = None
    audit_file: str | None = None
    snapshot_dir: str | None = None

    def __post_init__(self) -> None:
        if self.min_pairs < 1:
            raise ValueError("min_pairs must be >= 1")
        if self.max_pairs < self.min_pairs:
            raise ValueError("max_pairs must be >= min_pairs")
        if self.publish_candidates < self.min_pairs:
            raise ValueError("publish_candidates must be >= min_pairs")
        if self.publish_candidates > self.max_pairs:
            raise ValueError("publish_candidates must be <= max_pairs")
        if self.refresh_period < 60:
            raise ValueError("refresh_period must be >= 60")


# ---------------------------------------------------------------------------
# Core domain models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PairScore:
    """A single pair's quantitative research scores.

    All scores are :class:`Decimal` for precision.  Missing data is
    represented as ``None`` (not zero — see SPEC-072 zero-trade policy).
    """

    pair: str
    rs_score: Decimal | None = None
    oi_score: Decimal | None = None
    data_quality_pct: Decimal | None = None
    rank: int | None = None
    reason_codes: tuple[str, ...] = ()
    liquidity_score: Decimal | None = None


@dataclass(frozen=True)
class RankedPair:
    """A pair with its deterministic rank and selection status."""

    pair: str
    rank: int
    selected: bool
    rs_score: Decimal | None = None
    oi_score: Decimal | None = None
    reason_codes: tuple[str, ...] = ()
    fingerprint: str = ""
    liquidity_score: Decimal | None = None
    data_quality_pct: Decimal | None = None


@dataclass(frozen=True)
class PairlistOutput:
    """The complete output of a pairlist publish operation.

    Contains both the native RemotePairList JSON payload and the
    audit/explain record.  Preservation of the previously published
    artifact is a filesystem-level concern handled by the publisher
    (``*.previous-good`` copies), not a field on this model.
    """

    pairs: tuple[str, ...]
    refresh_period: int
    audit: AuditRecord
    fingerprint: str
    audit_fingerprint: str
    safety_flags: PairlistExportSafetyFlags = field(
        default_factory=PairlistExportSafetyFlags
    )


@dataclass(frozen=True)
class AuditRecord:
    """Machine-readable audit trail for a pairlist publish.

    Records every pair that was considered, whether it was selected or
    rejected, and the deterministic reason codes for each decision.
    """

    as_of_date: str
    universe_total: int
    eligible_count: int
    selected_count: int
    rejected_count: int
    selected: tuple[RankedPair, ...]
    rejected: tuple[RankedPair, ...]
    reason_code_summary: dict[str, int] = field(default_factory=dict)
    fingerprint: str = ""
    research_notice: str = (
        "Research-only artifact. Does not authorize execution, "
        "production deployment, live trading, dry-run trading, "
        "automatic execution, strategy selection, universe selection, "
        "order placement, signal generation, strategy mutation, "
        "universe mutation, or position changes. "
        "Human review is required."
    )
    # SPEC-075 v2 audit fields. Defaults preserve exact SPEC-074 v1 behavior
    # for every caller that does not pass them.
    schema_version: str = "hunter-ranking-input-v1"
    ranking_profile: str = "V1_RS_OI"
    active_score_dimensions: tuple[str, ...] = ("rs", "oi")
    ignored_score_dimensions: tuple[str, ...] = ()
    universe_size_at_scoring: int | None = None
    universe_fingerprint: str | None = None
    oi_available: bool | None = None
    source_metadata: Mapping[str, Any] = field(default_factory=dict)
    per_pair_evidence: Mapping[str, tuple[str, ...]] = field(default_factory=dict)


@dataclass(frozen=True)
class PublishGateResult:
    """Result of the publish-gate validation before atomic write.

    ``allow_publish`` is True only when all checks pass: schema valid,
    pair format valid, no duplicates, count within thresholds, evidence
    complete, audit produced, fingerprints computed.
    """

    allow_publish: bool
    reason_codes: tuple[str, ...]
    pairlist_output: PairlistOutput | None = None
    error_message: str | None = None


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class PairlistExportError(Exception):
    """Base error for the pairlist-export pipeline."""


class PairlistValidationError(PairlistExportError):
    """Schema / format / count validation failure."""


class PairlistRankingError(PairlistExportError):
    """Ranking pipeline failure (missing data, empty universe)."""


class PairlistPublishError(PairlistExportError):
    """Atomic write or snapshot failure."""


class PairlistFingerprintError(PairlistExportError):
    """Fingerprint computation failure."""
