"""Models for the Portfolio Risk Constraint Evaluator (MVP-58).

The evaluator consumes a ``PortfolioResearchContext`` and produces an immutable,
research-only, human-approval-required risk validation context. It does not use
historical prices, volatility, correlation, covariance, drawdown, VaR/CVaR, or
any trading runtime behavior.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import ROUND_DOWN, Decimal
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from hunter.portfolio_research_adapter.models import PortfolioAllocation

PORTFOLIO_RISK_EVALUATOR_VERSION: str = "0.58.0-dev"

RISK_QUANTUM = Decimal("0.00000001")

# Reason codes — deterministic strings for every blocking or allowed decision
MISSING_CONTEXT = "MISSING_CONTEXT"
REJECTED_PORTFOLIO_CONTEXT = "REJECTED_PORTFOLIO_CONTEXT"
BLOCK_ALL_CONTEXT = "BLOCK_ALL_CONTEXT"
EMPTY_ALLOCATIONS = "EMPTY_ALLOCATIONS"
INVALID_CONFIG = "INVALID_CONFIG"
INVALID_ALLOCATION = "INVALID_ALLOCATION"
INVALID_WEIGHT = "INVALID_WEIGHT"
DUPLICATE_PAIR = "DUPLICATE_PAIR"
BLACKLIST_CONFLICT = "BLACKLIST_CONFLICT"
TOTAL_EXPOSURE_MISMATCH = "TOTAL_EXPOSURE_MISMATCH"
TOTAL_EXPOSURE_EXCEEDED = "TOTAL_EXPOSURE_EXCEEDED"
ASSET_COUNT_BELOW_MINIMUM = "ASSET_COUNT_BELOW_MINIMUM"
ASSET_WEIGHT_BELOW_MINIMUM = "ASSET_WEIGHT_BELOW_MINIMUM"
ASSET_WEIGHT_EXCEEDED = "ASSET_WEIGHT_EXCEEDED"
CLUSTER_EXPOSURE_MISMATCH = "CLUSTER_EXPOSURE_MISMATCH"
CLUSTER_EXPOSURE_EXCEEDED = "CLUSTER_EXPOSURE_EXCEEDED"
HHI_EXCEEDED = "HHI_EXCEEDED"
CONTRADICTORY_CONTEXT = "CONTRADICTORY_CONTEXT"
RISK_ACCEPTED = "RISK_ACCEPTED"

PORTFOLIO_RISK_REASON_CODES: frozenset[str] = frozenset(
    {
        MISSING_CONTEXT,
        REJECTED_PORTFOLIO_CONTEXT,
        BLOCK_ALL_CONTEXT,
        EMPTY_ALLOCATIONS,
        INVALID_CONFIG,
        INVALID_ALLOCATION,
        INVALID_WEIGHT,
        DUPLICATE_PAIR,
        BLACKLIST_CONFLICT,
        TOTAL_EXPOSURE_MISMATCH,
        TOTAL_EXPOSURE_EXCEEDED,
        ASSET_COUNT_BELOW_MINIMUM,
        ASSET_WEIGHT_BELOW_MINIMUM,
        ASSET_WEIGHT_EXCEEDED,
        CLUSTER_EXPOSURE_MISMATCH,
        CLUSTER_EXPOSURE_EXCEEDED,
        HHI_EXCEEDED,
        CONTRADICTORY_CONTEXT,
        RISK_ACCEPTED,
    }
)

_MODES: frozenset[str] = frozenset({"LONG", "SHORT", "BLOCK_ALL"})

DEFAULT_MIN_ASSET_COUNT: int = 2
DEFAULT_MIN_ASSET_WEIGHT: Decimal = Decimal("0.0")
DEFAULT_MAX_SINGLE_ASSET_WEIGHT: Decimal = Decimal("0.35")
DEFAULT_MAX_TOTAL_EXPOSURE: Decimal = Decimal("1.00")
DEFAULT_MAX_CLUSTER_EXPOSURE: Decimal = Decimal("0.50")
DEFAULT_MAX_HHI: Decimal = Decimal("0.30")
DEFAULT_EXPOSURE_TOLERANCE: Decimal = Decimal("0.00000001")
DEFAULT_OUTPUT_DIR: Path = Path("data/portfolio_risk")
DEFAULT_REPORT_OUTPUT_DIR: Path = Path("reports/portfolio_risk")
DEFAULT_JSON_FILENAME: str = "latest_risk_validation.json"
DEFAULT_MARKDOWN_FILENAME: str = "latest_risk_validation.md"


class PortfolioRiskError(Exception):
    """Base exception for the portfolio risk evaluator.

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


def _quantize(value: Decimal) -> Decimal:
    """Quantize a Decimal value to the fixed risk quantum with ROUND_DOWN."""
    return value.quantize(RISK_QUANTUM, rounding=ROUND_DOWN)


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


def _validate_positive_int(name: str, value: int) -> None:
    if not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be a positive integer, got {value!r}")


@dataclass(frozen=True)
class PortfolioRiskConfig:
    """Configuration for the portfolio risk constraint evaluator."""

    min_asset_count: int = DEFAULT_MIN_ASSET_COUNT
    min_asset_weight: Decimal = DEFAULT_MIN_ASSET_WEIGHT
    max_single_asset_weight: Decimal = DEFAULT_MAX_SINGLE_ASSET_WEIGHT
    max_total_exposure: Decimal = DEFAULT_MAX_TOTAL_EXPOSURE
    max_cluster_exposure: Decimal = DEFAULT_MAX_CLUSTER_EXPOSURE
    max_hhi: Decimal = DEFAULT_MAX_HHI
    exposure_tolerance: Decimal = DEFAULT_EXPOSURE_TOLERANCE
    output_dir: Path = DEFAULT_OUTPUT_DIR
    report_output_dir: Path = DEFAULT_REPORT_OUTPUT_DIR
    json_filename: str = DEFAULT_JSON_FILENAME
    markdown_filename: str = DEFAULT_MARKDOWN_FILENAME
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _validate_positive_int("min_asset_count", self.min_asset_count)
        _validate_decimal("min_asset_weight", self.min_asset_weight, min_inclusive=Decimal("0"), max_inclusive=Decimal("1"))
        _validate_decimal("max_single_asset_weight", self.max_single_asset_weight, min_exclusive=Decimal("0"), max_inclusive=Decimal("1"))
        _validate_decimal("max_total_exposure", self.max_total_exposure, min_exclusive=Decimal("0"), max_inclusive=Decimal("1"))
        _validate_decimal("max_cluster_exposure", self.max_cluster_exposure, min_exclusive=Decimal("0"), max_inclusive=Decimal("1"))
        _validate_decimal("max_hhi", self.max_hhi, min_inclusive=Decimal("0"), max_inclusive=Decimal("1"))
        _validate_decimal("exposure_tolerance", self.exposure_tolerance, min_inclusive=Decimal("0"), max_inclusive=Decimal("1"))
        if self.max_single_asset_weight < self.min_asset_weight:
            raise ValueError(
                f"max_single_asset_weight ({self.max_single_asset_weight}) must be >= min_asset_weight ({self.min_asset_weight})"
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
    def default(cls) -> "PortfolioRiskConfig":
        """Return the default research-only risk evaluator configuration."""
        return cls()


@dataclass(frozen=True)
class PortfolioRiskMetrics:
    """Deterministic risk metrics derived from a portfolio research context."""

    asset_count: int
    total_exposure: Decimal
    largest_asset_weight: Decimal
    largest_cluster_exposure: Decimal
    hhi: Decimal
    effective_asset_count: Decimal
    cluster_exposure: Mapping[str, Decimal]

    def __post_init__(self) -> None:
        if not isinstance(self.asset_count, int) or self.asset_count < 0:
            raise ValueError(f"asset_count must be a non-negative integer, got {self.asset_count!r}")
        for name, value in (
            ("total_exposure", self.total_exposure),
            ("largest_asset_weight", self.largest_asset_weight),
            ("largest_cluster_exposure", self.largest_cluster_exposure),
            ("hhi", self.hhi),
            ("effective_asset_count", self.effective_asset_count),
        ):
            if not isinstance(value, Decimal):
                raise ValueError(f"{name} must be a Decimal, got {value!r}")
            if value < Decimal("0"):
                raise ValueError(f"{name} must be non-negative, got {value}")
        if self.hhi > Decimal("1"):
            raise ValueError(f"hhi must be at most 1, got {self.hhi}")
        if not isinstance(self.cluster_exposure, Mapping):
            raise ValueError(f"cluster_exposure must be a Mapping, got {self.cluster_exposure!r}")
        for cluster, exposure in self.cluster_exposure.items():
            if not isinstance(cluster, str) or not cluster.strip():
                raise ValueError(f"cluster keys must be non-empty strings, got {cluster!r}")
            if not isinstance(exposure, Decimal):
                raise ValueError(f"cluster exposures must be Decimals, got {exposure!r}")


@dataclass(frozen=True)
class ValidatedPortfolioRiskContext:
    """Immutable risk validation result produced by the evaluator.

    Every safety-critical field defaults to the most restrictive state. A result
    with ``accepted=False`` is always fail-closed: ``risk_gate_open=False``,
    ``mode='BLOCK_ALL'`` and ``validated_allocations`` is empty.
    """

    version: str
    source_portfolio_fingerprint: str
    risk_evaluation_fingerprint: str
    evaluated_at: datetime
    accepted: bool
    risk_gate_open: bool
    mode: str
    validated_allocations: tuple[PortfolioAllocation, ...]
    metrics: PortfolioRiskMetrics
    reason_codes: tuple[str, ...]
    research_only: bool
    human_approval_required: bool
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.version, str) or not self.version.strip():
            raise ValueError(f"version must be a non-empty string, got {self.version!r}")
        if not isinstance(self.source_portfolio_fingerprint, str) or not self.source_portfolio_fingerprint.strip():
            raise ValueError(
                f"source_portfolio_fingerprint must be a non-empty string, got {self.source_portfolio_fingerprint!r}"
            )
        if not isinstance(self.risk_evaluation_fingerprint, str) or not self.risk_evaluation_fingerprint.strip():
            raise ValueError(
                f"risk_evaluation_fingerprint must be a non-empty string, got {self.risk_evaluation_fingerprint!r}"
            )
        if not isinstance(self.evaluated_at, datetime) or self.evaluated_at.tzinfo is None:
            raise ValueError(
                f"evaluated_at must be a timezone-aware datetime, got {self.evaluated_at!r}"
            )
        if not isinstance(self.mode, str) or self.mode not in _MODES:
            raise ValueError(f"mode must be one of {_MODES}, got {self.mode!r}")
        if not isinstance(self.validated_allocations, tuple):
            object.__setattr__(self, "validated_allocations", tuple(self.validated_allocations))
        if not isinstance(self.reason_codes, tuple):
            object.__setattr__(self, "reason_codes", tuple(self.reason_codes))
        for code in self.reason_codes:
            if code not in PORTFOLIO_RISK_REASON_CODES:
                raise ValueError(f"unsupported reason code: {code!r}")
        for name, value in (
            ("accepted", self.accepted),
            ("risk_gate_open", self.risk_gate_open),
            ("research_only", self.research_only),
            ("human_approval_required", self.human_approval_required),
        ):
            if not isinstance(value, bool):
                raise ValueError(f"{name} must be a bool, got {value!r}")
        if not self.research_only or not self.human_approval_required:
            raise ValueError("research_only and human_approval_required must both be True")
        if not self.accepted:
            if self.mode != "BLOCK_ALL":
                raise ValueError(
                    f"a rejected result must have mode='BLOCK_ALL', got {self.mode!r}"
                )
            if self.risk_gate_open:
                raise ValueError(
                    "a rejected result must have risk_gate_open=False"
                )
            if self.validated_allocations:
                raise ValueError(
                    f"a rejected result must have empty allocations, got {self.validated_allocations!r}"
                )
            if self.metrics.total_exposure != Decimal("0"):
                raise ValueError(
                    f"a rejected result must have total_exposure=0, got {self.metrics.total_exposure}"
                )
        object.__setattr__(self, "metadata", _coerce_json_mapping(self.metadata))
