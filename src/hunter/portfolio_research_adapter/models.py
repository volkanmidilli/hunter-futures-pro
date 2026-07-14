"""Models for the Portfolio Construction Research Adapter (MVP-57).

The adapter consumes a `ValidatedStrategyContext` and produces an immutable,
research-only, human-approval-required portfolio research context. It does not
integrate with Freqtrade runtime, exchanges, databases, schedulers, or live
trading systems, and never emits action commands.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import ROUND_DOWN, Decimal
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

PORTFOLIO_RESEARCH_ADAPTER_VERSION: str = "0.57.0-dev"

WEIGHT_QUANTUM = Decimal("0.00000001")

# Reason codes — deterministic strings for every blocking or allowed decision
MISSING_CONTEXT = "MISSING_CONTEXT"
REJECTED_CONTEXT = "REJECTED_CONTEXT"
BLOCK_ALL_CONTEXT = "BLOCK_ALL_CONTEXT"
EMPTY_WHITELIST = "EMPTY_WHITELIST"
INVALID_CONFIG = "INVALID_CONFIG"
INVALID_PAIR = "INVALID_PAIR"
BLACKLISTED_PAIR = "BLACKLISTED_PAIR"
MISSING_SCORE = "MISSING_SCORE"
INVALID_SCORE = "INVALID_SCORE"
BELOW_MIN_WEIGHT = "BELOW_MIN_WEIGHT"
MAX_ASSETS_EXCEEDED = "MAX_ASSETS_EXCEEDED"
CLUSTER_LIMIT_APPLIED = "CLUSTER_LIMIT_APPLIED"
EMPTY_PORTFOLIO = "EMPTY_PORTFOLIO"
CONTRADICTORY_CONTEXT = "CONTRADICTORY_CONTEXT"
PORTFOLIO_ACCEPTED = "PORTFOLIO_ACCEPTED"

PORTFOLIO_RESEARCH_REASON_CODES: frozenset[str] = frozenset(
    {
        MISSING_CONTEXT,
        REJECTED_CONTEXT,
        BLOCK_ALL_CONTEXT,
        EMPTY_WHITELIST,
        INVALID_CONFIG,
        INVALID_PAIR,
        BLACKLISTED_PAIR,
        MISSING_SCORE,
        INVALID_SCORE,
        BELOW_MIN_WEIGHT,
        MAX_ASSETS_EXCEEDED,
        CLUSTER_LIMIT_APPLIED,
        EMPTY_PORTFOLIO,
        CONTRADICTORY_CONTEXT,
        PORTFOLIO_ACCEPTED,
    }
)

_ALLOCATION_METHODS: frozenset[str] = frozenset({"EQUAL_WEIGHT", "SCORE_PROPORTIONAL"})
_MODES: frozenset[str] = frozenset({"LONG", "SHORT", "BLOCK_ALL"})

DEFAULT_ALLOCATION_METHOD: str = "EQUAL_WEIGHT"
DEFAULT_MAX_ASSETS: int = 10
DEFAULT_MIN_ASSET_WEIGHT: Decimal = Decimal("0.0")
DEFAULT_MAX_ASSET_WEIGHT: Decimal = Decimal("0.20")
DEFAULT_MAX_TOTAL_EXPOSURE: Decimal = Decimal("1.00")
DEFAULT_MAX_CLUSTER_EXPOSURE: Decimal = Decimal("0.40")
DEFAULT_OUTPUT_DIR: Path = Path("data/portfolio_research")
DEFAULT_REPORT_OUTPUT_DIR: Path = Path("reports/portfolio_research")
DEFAULT_JSON_FILENAME: str = "latest_portfolio.json"
DEFAULT_MARKDOWN_FILENAME: str = "latest_portfolio.md"
DEFAULT_UNCLASSIFIED_CLUSTER: str = "UNCLASSIFIED"


class PortfolioResearchError(Exception):
    """Base exception for the portfolio research adapter.

    Raised for invalid configuration or invalid input. Not raised for normal
    fail-closed states, which are encoded in result reason codes.
    """

    def __init__(self, *args: Any, reason_code: str | None = None) -> None:
        super().__init__(*args)
        self.reason_code = reason_code


def _coerce_json_value(value: Any) -> Any:
    """Recursively copy a JSON-compatible value.

    Allowed scalar types: ``str``, ``bool``, ``int``, ``float``, ``None``.
    Allowed containers: ``list``, ``tuple``, ``dict`` and other ``Mapping`` values.
    Other types are rejected with ``TypeError``.
    """
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, (list, tuple)):
        return [_coerce_json_value(item) for item in value]
    if isinstance(value, (dict, Mapping)):
        return {str(k): _coerce_json_value(v) for k, v in value.items()}
    raise TypeError(f"value is not JSON-compatible: {value!r}")


def _coerce_json_mapping(
    value: Mapping[str, object] | dict[str, object] | None,
) -> Mapping[str, object]:
    """Coerce a mapping to an immutable deep copy with JSON-compatible values."""
    if value is None:
        return MappingProxyType({})
    coerced = {str(k): _coerce_json_value(v) for k, v in value.items()}
    return MappingProxyType(coerced)


def _quantize_weight(value: Decimal) -> Decimal:
    """Quantize a Decimal weight to the fixed quantum with ROUND_DOWN."""
    return value.quantize(WEIGHT_QUANTUM, rounding=ROUND_DOWN)


def _validate_decimal(
    name: str,
    value: Decimal,
    *,
    min_exclusive: Decimal | None = None,
    min_inclusive: Decimal | None = None,
    max_inclusive: Decimal | None = None,
) -> None:
    if not isinstance(value, Decimal):
        raise ValueError(f"{name} must be a Decimal, got {value!r}")
    if min_exclusive is not None and value <= min_exclusive:
        raise ValueError(f"{name} must be greater than {min_exclusive}, got {value}")
    if min_inclusive is not None and value < min_inclusive:
        raise ValueError(f"{name} must be at least {min_inclusive}, got {value}")
    if max_inclusive is not None and value > max_inclusive:
        raise ValueError(f"{name} must be at most {max_inclusive}, got {value}")


def _normalize_cluster(value: str | None) -> str:
    """Canonicalize a cluster string to uppercase or UNCLASSIFIED."""
    if value is None:
        return DEFAULT_UNCLASSIFIED_CLUSTER
    stripped = str(value).strip().upper()
    return stripped if stripped else DEFAULT_UNCLASSIFIED_CLUSTER


@dataclass(frozen=True)
class PortfolioResearchConfig:
    """Configuration for the portfolio construction research adapter."""

    allocation_method: str = DEFAULT_ALLOCATION_METHOD
    max_assets: int = DEFAULT_MAX_ASSETS
    min_asset_weight: Decimal = DEFAULT_MIN_ASSET_WEIGHT
    max_asset_weight: Decimal = DEFAULT_MAX_ASSET_WEIGHT
    max_total_exposure: Decimal = DEFAULT_MAX_TOTAL_EXPOSURE
    max_cluster_exposure: Decimal = DEFAULT_MAX_CLUSTER_EXPOSURE
    output_dir: Path = DEFAULT_OUTPUT_DIR
    report_output_dir: Path = DEFAULT_REPORT_OUTPUT_DIR
    json_filename: str = DEFAULT_JSON_FILENAME
    markdown_filename: str = DEFAULT_MARKDOWN_FILENAME
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.allocation_method, str) or self.allocation_method not in _ALLOCATION_METHODS:
            raise ValueError(
                f"allocation_method must be one of {_ALLOCATION_METHODS}, got {self.allocation_method!r}"
            )
        if not isinstance(self.max_assets, int) or self.max_assets < 1:
            raise ValueError(f"max_assets must be a positive integer, got {self.max_assets!r}")
        _validate_decimal("min_asset_weight", self.min_asset_weight, min_inclusive=Decimal("0"), max_inclusive=Decimal("1"))
        _validate_decimal("max_asset_weight", self.max_asset_weight, min_exclusive=Decimal("0"), max_inclusive=Decimal("1"))
        _validate_decimal("max_total_exposure", self.max_total_exposure, min_exclusive=Decimal("0"), max_inclusive=Decimal("1"))
        _validate_decimal("max_cluster_exposure", self.max_cluster_exposure, min_exclusive=Decimal("0"), max_inclusive=Decimal("1"))
        if self.max_asset_weight < self.min_asset_weight:
            raise ValueError(
                f"max_asset_weight ({self.max_asset_weight}) must be >= min_asset_weight ({self.min_asset_weight})"
            )
        if self.max_cluster_exposure > self.max_total_exposure:
            raise ValueError(
                f"max_cluster_exposure ({self.max_cluster_exposure}) must be <= max_total_exposure ({self.max_total_exposure})"
            )
        if not isinstance(self.output_dir, Path):
            object.__setattr__(self, "output_dir", Path(str(self.output_dir)))
        if not isinstance(self.report_output_dir, Path):
            object.__setattr__(self, "report_output_dir", Path(str(self.report_output_dir)))
        for name, value in (
            ("json_filename", self.json_filename),
            ("markdown_filename", self.markdown_filename),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string, got {value!r}")
        object.__setattr__(self, "metadata", _coerce_json_mapping(self.metadata))

    @classmethod
    def default(cls) -> "PortfolioResearchConfig":
        """Return the default research-only adapter configuration."""
        return cls()


@dataclass(frozen=True)
class PortfolioAllocation:
    """One allocation entry inside a portfolio research context."""

    pair: str
    weight: Decimal
    cluster: str
    score: Decimal | None
    allocation_reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.pair, str) or not self.pair.strip():
            raise ValueError(f"pair must be a non-empty string, got {self.pair!r}")
        _validate_decimal("weight", self.weight, min_inclusive=Decimal("0"), max_inclusive=Decimal("1"))
        object.__setattr__(self, "cluster", _normalize_cluster(self.cluster))
        if self.score is not None and not isinstance(self.score, Decimal):
            raise ValueError(f"score must be a Decimal or None, got {self.score!r}")
        if not isinstance(self.allocation_reason, str) or not self.allocation_reason.strip():
            raise ValueError(
                f"allocation_reason must be a non-empty string, got {self.allocation_reason!r}"
            )


@dataclass(frozen=True)
class PortfolioExclusion:
    """One exclusion entry inside a portfolio research context."""

    pair: str
    reason_code: str
    details: str

    def __post_init__(self) -> None:
        if not isinstance(self.pair, str) or not self.pair.strip():
            raise ValueError(f"pair must be a non-empty string, got {self.pair!r}")
        if not isinstance(self.reason_code, str) or not self.reason_code.strip():
            raise ValueError(f"reason_code must be a non-empty string, got {self.reason_code!r}")
        if self.reason_code not in PORTFOLIO_RESEARCH_REASON_CODES:
            raise ValueError(f"unsupported reason code: {self.reason_code!r}")
        if not isinstance(self.details, str):
            raise ValueError(f"details must be a string, got {self.details!r}")


@dataclass(frozen=True)
class PortfolioResearchContext:
    """Immutable portfolio research result produced by the adapter.

    Every safety-critical field defaults to the most restrictive state. A result
    with ``accepted=False`` is always fail-closed: mode is ``BLOCK_ALL`` and
    allocations are empty.
    """

    version: str
    source_context_fingerprint: str
    portfolio_fingerprint: str
    generated_at: datetime
    mode: str
    allocation_method: str
    allocations: tuple[PortfolioAllocation, ...]
    exclusions: tuple[PortfolioExclusion, ...]
    cluster_exposure: Mapping[str, Decimal]
    total_exposure: Decimal
    accepted: bool
    research_only: bool
    human_approval_required: bool
    reason_codes: tuple[str, ...]
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.version, str) or not self.version.strip():
            raise ValueError(f"version must be a non-empty string, got {self.version!r}")
        if not isinstance(self.source_context_fingerprint, str) or not self.source_context_fingerprint.strip():
            raise ValueError(
                f"source_context_fingerprint must be a non-empty string, got {self.source_context_fingerprint!r}"
            )
        if not isinstance(self.portfolio_fingerprint, str) or not self.portfolio_fingerprint.strip():
            raise ValueError(
                f"portfolio_fingerprint must be a non-empty string, got {self.portfolio_fingerprint!r}"
            )
        if not isinstance(self.generated_at, datetime) or self.generated_at.tzinfo is None:
            raise ValueError(
                f"generated_at must be a timezone-aware datetime, got {self.generated_at!r}"
            )
        if not isinstance(self.mode, str) or self.mode not in _MODES:
            raise ValueError(f"mode must be one of {_MODES}, got {self.mode!r}")
        if not isinstance(self.allocation_method, str) or self.allocation_method not in _ALLOCATION_METHODS:
            raise ValueError(
                f"allocation_method must be one of {_ALLOCATION_METHODS}, got {self.allocation_method!r}"
            )
        for name, value in (
            ("allocations", self.allocations),
            ("exclusions", self.exclusions),
            ("reason_codes", self.reason_codes),
        ):
            if not isinstance(value, tuple):
                object.__setattr__(self, name, tuple(value))
        if not isinstance(self.cluster_exposure, Mapping):
            raise ValueError(f"cluster_exposure must be a Mapping, got {self.cluster_exposure!r}")
        for cluster, exposure in self.cluster_exposure.items():
            if not isinstance(cluster, str) or not cluster.strip():
                raise ValueError(f"cluster keys must be non-empty strings, got {cluster!r}")
            if not isinstance(exposure, Decimal):
                raise ValueError(f"cluster exposures must be Decimals, got {exposure!r}")
        _validate_decimal("total_exposure", self.total_exposure, min_inclusive=Decimal("0"), max_inclusive=Decimal("1"))
        if not isinstance(self.accepted, bool):
            raise ValueError(f"accepted must be a bool, got {self.accepted!r}")
        for name, value in (
            ("research_only", self.research_only),
            ("human_approval_required", self.human_approval_required),
        ):
            if not isinstance(value, bool):
                raise ValueError(f"{name} must be a bool, got {value!r}")
        if not self.research_only or not self.human_approval_required:
            raise ValueError("research_only and human_approval_required must both be True")
        for code in self.reason_codes:
            if code not in PORTFOLIO_RESEARCH_REASON_CODES:
                raise ValueError(f"unsupported reason code: {code}")
        if not self.accepted:
            if self.mode != "BLOCK_ALL":
                raise ValueError(
                    f"a rejected result must have mode='BLOCK_ALL', got {self.mode!r}"
                )
            if self.allocations:
                raise ValueError(
                    f"a rejected result must have empty allocations, got {self.allocations!r}"
                )
            if self.total_exposure != Decimal("0"):
                raise ValueError(
                    f"a rejected result must have total_exposure=0, got {self.total_exposure}"
                )
        object.__setattr__(self, "metadata", _coerce_json_mapping(self.metadata))
