"""Tests for portfolio risk structural validator."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from types import MappingProxyType

import pytest

from hunter.portfolio_research_adapter.models import PortfolioAllocation, PortfolioResearchContext
from hunter.portfolio_risk_evaluator.models import (
    BLACKLIST_CONFLICT,
    BLOCK_ALL_CONTEXT,
    CLUSTER_EXPOSURE_MISMATCH,
    CONTRADICTORY_CONTEXT,
    DUPLICATE_PAIR,
    EMPTY_ALLOCATIONS,
    INVALID_ALLOCATION,
    INVALID_CONFIG,
    INVALID_WEIGHT,
    MISSING_CONTEXT,
    REJECTED_PORTFOLIO_CONTEXT,
    TOTAL_EXPOSURE_MISMATCH,
    PortfolioRiskConfig,
    PortfolioRiskError,
    PortfolioRiskMetrics,
)
from hunter.portfolio_risk_evaluator.metrics import (
    recalculate_cluster_exposure,
    recalculate_total_exposure,
)
from hunter.portfolio_risk_evaluator.validator import (
    _is_canonical_pair,
    validate_portfolio_risk_config,
    validate_portfolio_risk_context,
)


def _make_dt() -> datetime:
    return datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)


def _make_context(
    *,
    accepted: bool = True,
    mode: str = "LONG",
    allocations: tuple[PortfolioAllocation, ...] = (),
    total_exposure: Decimal = Decimal("0"),
    cluster_exposure: dict[str, Decimal] | None = None,
    exclusions: tuple = (),
) -> PortfolioResearchContext:
    cluster_exposure = cluster_exposure or {}
    effective_mode = "BLOCK_ALL" if not accepted else mode
    return PortfolioResearchContext(
        version="0.57.0-dev",
        source_context_fingerprint="src-fp",
        portfolio_fingerprint="port-fp",
        generated_at=_make_dt(),
        mode=effective_mode,
        allocation_method="EQUAL_WEIGHT",
        allocations=allocations,
        exclusions=exclusions,
        cluster_exposure=MappingProxyType(cluster_exposure),
        total_exposure=total_exposure,
        accepted=accepted,
        research_only=True,
        human_approval_required=True,
        reason_codes=(),
        metadata={},
    )


class _FakeContext:
    """Minimal stand-in for PortfolioResearchContext to test invalid modes."""

    def __init__(self, mode: str = "INVALID") -> None:
        self.accepted = True
        self.mode = mode
        self.research_only = True
        self.human_approval_required = True
        self.allocations = (PortfolioAllocation("BTC/USDT", Decimal("0.5"), "DEFI", None, "test"),)
        self.exclusions = ()
        self.total_exposure = Decimal("0.5")
        self.cluster_exposure = MappingProxyType({"DEFI": Decimal("0.5")})


class _FakeAllocation:
    """Minimal stand-in for PortfolioAllocation to test invalid weights."""

    def __init__(self, pair: str, weight: object, cluster: str) -> None:
        self.pair = pair
        self.weight = weight
        self.cluster = cluster


def test_is_canonical_pair() -> None:
    assert _is_canonical_pair("BTC/USDT")
    assert not _is_canonical_pair("BTCUSDT")
    assert not _is_canonical_pair("BTC/")
    assert not _is_canonical_pair("/USDT")
    assert not _is_canonical_pair("")


def test_validate_config_accepts_default() -> None:
    validate_portfolio_risk_config(PortfolioRiskConfig.default())


def test_validate_config_rejects_bad_type() -> None:
    with pytest.raises(PortfolioRiskError):
        validate_portfolio_risk_config("bad")  # type: ignore[arg-type]


def test_validate_context_missing() -> None:
    is_valid, reasons = validate_portfolio_risk_context(None, PortfolioRiskConfig.default())
    assert not is_valid
    assert MISSING_CONTEXT in reasons


def test_validate_context_rejected() -> None:
    ctx = _make_context(accepted=False)
    is_valid, reasons = validate_portfolio_risk_context(ctx, PortfolioRiskConfig.default())
    assert not is_valid
    assert REJECTED_PORTFOLIO_CONTEXT in reasons


def test_validate_context_block_all() -> None:
    ctx = _make_context(mode="BLOCK_ALL")
    is_valid, reasons = validate_portfolio_risk_context(ctx, PortfolioRiskConfig.default())
    assert not is_valid
    assert BLOCK_ALL_CONTEXT in reasons


def test_validate_context_empty_allocations() -> None:
    ctx = _make_context()
    is_valid, reasons = validate_portfolio_risk_context(ctx, PortfolioRiskConfig.default())
    assert not is_valid
    assert EMPTY_ALLOCATIONS in reasons


def test_validate_context_invalid_mode() -> None:
    ctx = _FakeContext()
    is_valid, reasons = validate_portfolio_risk_context(ctx, PortfolioRiskConfig.default())  # type: ignore[arg-type]
    assert not is_valid
    assert CONTRADICTORY_CONTEXT in reasons


def test_validate_context_duplicate_pair() -> None:
    ctx = _make_context(
        allocations=(
            PortfolioAllocation("BTC/USDT", Decimal("0.3"), "DEFI", None, "test"),
            PortfolioAllocation("BTC/USDT", Decimal("0.2"), "DEFI", None, "test"),
        ),
        total_exposure=Decimal("0.5"),
        cluster_exposure={"DEFI": Decimal("0.5")},
    )
    is_valid, reasons = validate_portfolio_risk_context(ctx, PortfolioRiskConfig.default())
    assert not is_valid
    assert DUPLICATE_PAIR in reasons


def test_validate_context_invalid_pair_format() -> None:
    ctx = _make_context(
        allocations=(PortfolioAllocation("BTCUSDT", Decimal("0.5"), "DEFI", None, "test"),),
        total_exposure=Decimal("0.5"),
        cluster_exposure={"DEFI": Decimal("0.5")},
    )
    is_valid, reasons = validate_portfolio_risk_context(ctx, PortfolioRiskConfig.default())
    assert not is_valid
    assert INVALID_ALLOCATION in reasons


def test_validate_context_invalid_weight() -> None:
    ctx = _FakeContext(mode="LONG")
    ctx.allocations = (_FakeAllocation("BTC/USDT", Decimal("-0.1"), "DEFI"),)
    is_valid, reasons = validate_portfolio_risk_context(ctx, PortfolioRiskConfig.default())  # type: ignore[arg-type]
    assert not is_valid
    assert INVALID_WEIGHT in reasons


def test_validate_context_blacklist_conflict() -> None:
    from hunter.portfolio_research_adapter.models import PortfolioExclusion, BLACKLISTED_PAIR

    ctx = _make_context(
        allocations=(PortfolioAllocation("BTC/USDT", Decimal("0.5"), "DEFI", None, "test"),),
        total_exposure=Decimal("0.5"),
        cluster_exposure={"DEFI": Decimal("0.5")},
        exclusions=(PortfolioExclusion("BTC/USDT", BLACKLISTED_PAIR, "blacklisted"),),
    )
    is_valid, reasons = validate_portfolio_risk_context(ctx, PortfolioRiskConfig.default())
    assert not is_valid
    assert BLACKLIST_CONFLICT in reasons


def test_validate_context_total_exposure_mismatch() -> None:
    ctx = _make_context(
        allocations=(PortfolioAllocation("BTC/USDT", Decimal("0.5"), "DEFI", None, "test"),),
        total_exposure=Decimal("0.51"),
        cluster_exposure={"DEFI": Decimal("0.5")},
    )
    is_valid, reasons = validate_portfolio_risk_context(ctx, PortfolioRiskConfig.default())
    assert not is_valid
    assert TOTAL_EXPOSURE_MISMATCH in reasons


def test_validate_context_cluster_exposure_mismatch() -> None:
    ctx = _make_context(
        allocations=(PortfolioAllocation("BTC/USDT", Decimal("0.5"), "DEFI", None, "test"),),
        total_exposure=Decimal("0.5"),
        cluster_exposure={"DEFI": Decimal("0.51")},
    )
    is_valid, reasons = validate_portfolio_risk_context(ctx, PortfolioRiskConfig.default())
    assert not is_valid
    assert CLUSTER_EXPOSURE_MISMATCH in reasons


def test_validate_context_valid() -> None:
    ctx = _make_context(
        allocations=(
            PortfolioAllocation("BTC/USDT", Decimal("0.5"), "DEFI", None, "test"),
            PortfolioAllocation("ETH/USDT", Decimal("0.5"), "DEFI", None, "test"),
        ),
        total_exposure=Decimal("1.0"),
        cluster_exposure={"DEFI": Decimal("1.0")},
    )
    is_valid, reasons = validate_portfolio_risk_context(ctx, PortfolioRiskConfig.default())
    assert is_valid
    assert not reasons


def test_recalculate_total_exposure() -> None:
    allocations = (
        PortfolioAllocation("BTC/USDT", Decimal("0.3"), "DEFI", None, "test"),
        PortfolioAllocation("ETH/USDT", Decimal("0.4"), "DEFI", None, "test"),
    )
    assert recalculate_total_exposure(allocations) == Decimal("0.7")


def test_recalculate_cluster_exposure() -> None:
    allocations = (
        PortfolioAllocation("BTC/USDT", Decimal("0.3"), "DEFI", None, "test"),
        PortfolioAllocation("ETH/USDT", Decimal("0.4"), "DEFI", None, "test"),
        PortfolioAllocation("SOL/USDT", Decimal("0.2"), "L1", None, "test"),
    )
    clusters = recalculate_cluster_exposure(allocations)
    assert clusters["DEFI"] == Decimal("0.7")
    assert clusters["L1"] == Decimal("0.2")
