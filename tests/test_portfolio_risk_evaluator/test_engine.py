"""Tests for portfolio risk evaluation engine."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from types import MappingProxyType

import pytest

from hunter.portfolio_research_adapter.models import PortfolioAllocation, PortfolioResearchContext
from hunter.portfolio_risk_evaluator.engine import build_validated_portfolio_risk_context
from hunter.portfolio_risk_evaluator.models import (
    ASSET_COUNT_BELOW_MINIMUM,
    ASSET_WEIGHT_EXCEEDED,
    CLUSTER_EXPOSURE_EXCEEDED,
    EMPTY_ALLOCATIONS,
    HHI_EXCEEDED,
    MISSING_CONTEXT,
    PORTFOLIO_RISK_EVALUATOR_VERSION,
    REJECTED_PORTFOLIO_CONTEXT,
    RISK_ACCEPTED,
    TOTAL_EXPOSURE_EXCEEDED,
    PortfolioRiskConfig,
    PortfolioRiskError,
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
        exclusions=(),
        cluster_exposure=MappingProxyType(cluster_exposure),
        total_exposure=total_exposure,
        accepted=accepted,
        research_only=True,
        human_approval_required=True,
        reason_codes=(),
        metadata={},
    )


def test_build_with_missing_context() -> None:
    config = PortfolioRiskConfig.default()
    result = build_validated_portfolio_risk_context(None, config, evaluated_at=_make_dt())
    assert not result.accepted
    assert not result.risk_gate_open
    assert result.mode == "BLOCK_ALL"
    assert result.validated_allocations == ()
    assert MISSING_CONTEXT in result.reason_codes


def test_build_with_rejected_context() -> None:
    config = PortfolioRiskConfig.default()
    ctx = _make_context(accepted=False)
    result = build_validated_portfolio_risk_context(ctx, config, evaluated_at=_make_dt())
    assert not result.accepted
    assert REJECTED_PORTFOLIO_CONTEXT in result.reason_codes


def test_build_with_block_all_context() -> None:
    config = PortfolioRiskConfig.default()
    ctx = _make_context(mode="BLOCK_ALL")
    result = build_validated_portfolio_risk_context(ctx, config, evaluated_at=_make_dt())
    assert not result.accepted
    assert EMPTY_ALLOCATIONS in result.reason_codes


def test_build_with_empty_allocations() -> None:
    config = PortfolioRiskConfig.default()
    ctx = _make_context()
    result = build_validated_portfolio_risk_context(ctx, config, evaluated_at=_make_dt())
    assert not result.accepted
    assert EMPTY_ALLOCATIONS in result.reason_codes


def test_build_with_asset_count_below_minimum() -> None:
    config = PortfolioRiskConfig(min_asset_count=3)
    ctx = _make_context(
        allocations=(PortfolioAllocation("BTC/USDT", Decimal("0.5"), "DEFI", None, "test"),),
        total_exposure=Decimal("0.5"),
        cluster_exposure={"DEFI": Decimal("0.5")},
    )
    result = build_validated_portfolio_risk_context(ctx, config, evaluated_at=_make_dt())
    assert not result.accepted
    assert ASSET_COUNT_BELOW_MINIMUM in result.reason_codes


def test_build_with_asset_weight_exceeded() -> None:
    config = PortfolioRiskConfig(max_single_asset_weight=Decimal("0.30"))
    ctx = _make_context(
        allocations=(
            PortfolioAllocation("BTC/USDT", Decimal("0.5"), "DEFI", None, "test"),
            PortfolioAllocation("ETH/USDT", Decimal("0.5"), "DEFI", None, "test"),
        ),
        total_exposure=Decimal("1.0"),
        cluster_exposure={"DEFI": Decimal("1.0")},
    )
    result = build_validated_portfolio_risk_context(ctx, config, evaluated_at=_make_dt())
    assert not result.accepted
    assert ASSET_WEIGHT_EXCEEDED in result.reason_codes


def test_build_with_total_exposure_exceeded() -> None:
    config = PortfolioRiskConfig(max_total_exposure=Decimal("0.80"))
    ctx = _make_context(
        allocations=(
            PortfolioAllocation("BTC/USDT", Decimal("0.5"), "DEFI", None, "test"),
            PortfolioAllocation("ETH/USDT", Decimal("0.5"), "DEFI", None, "test"),
        ),
        total_exposure=Decimal("1.0"),
        cluster_exposure={"DEFI": Decimal("1.0")},
    )
    result = build_validated_portfolio_risk_context(ctx, config, evaluated_at=_make_dt())
    assert not result.accepted
    assert TOTAL_EXPOSURE_EXCEEDED in result.reason_codes


def test_build_with_cluster_exposure_exceeded() -> None:
    config = PortfolioRiskConfig(max_cluster_exposure=Decimal("0.40"))
    ctx = _make_context(
        allocations=(
            PortfolioAllocation("BTC/USDT", Decimal("0.3"), "DEFI", None, "test"),
            PortfolioAllocation("ETH/USDT", Decimal("0.3"), "DEFI", None, "test"),
        ),
        total_exposure=Decimal("0.6"),
        cluster_exposure={"DEFI": Decimal("0.6")},
    )
    result = build_validated_portfolio_risk_context(ctx, config, evaluated_at=_make_dt())
    assert not result.accepted
    assert CLUSTER_EXPOSURE_EXCEEDED in result.reason_codes


def test_build_with_hhi_exceeded() -> None:
    config = PortfolioRiskConfig(max_hhi=Decimal("0.20"))
    ctx = _make_context(
        allocations=(
            PortfolioAllocation("BTC/USDT", Decimal("0.7"), "DEFI", None, "test"),
            PortfolioAllocation("ETH/USDT", Decimal("0.3"), "DEFI", None, "test"),
        ),
        total_exposure=Decimal("1.0"),
        cluster_exposure={"DEFI": Decimal("1.0")},
    )
    result = build_validated_portfolio_risk_context(ctx, config, evaluated_at=_make_dt())
    assert not result.accepted
    assert HHI_EXCEEDED in result.reason_codes


def test_build_accepted_diversified_portfolio() -> None:
    config = PortfolioRiskConfig.default()
    ctx = _make_context(
        allocations=(
            PortfolioAllocation("BTC/USDT", Decimal("0.25"), "DEFI", None, "test"),
            PortfolioAllocation("ETH/USDT", Decimal("0.25"), "DEFI", None, "test"),
            PortfolioAllocation("SOL/USDT", Decimal("0.25"), "L1", None, "test"),
            PortfolioAllocation("ADA/USDT", Decimal("0.25"), "L1", None, "test"),
        ),
        total_exposure=Decimal("1.0"),
        cluster_exposure={"DEFI": Decimal("0.5"), "L1": Decimal("0.5")},
    )
    result = build_validated_portfolio_risk_context(ctx, config, evaluated_at=_make_dt())
    assert result.accepted
    assert result.risk_gate_open
    assert result.mode == "LONG"
    assert RISK_ACCEPTED in result.reason_codes
    assert len(result.validated_allocations) == 4
    assert result.metrics.total_exposure == Decimal("1.0")
    assert result.metrics.hhi == Decimal("0.25")
    assert result.source_portfolio_fingerprint == "port-fp"
    assert result.version == PORTFOLIO_RISK_EVALUATOR_VERSION


def test_build_preserves_metadata() -> None:
    config = PortfolioRiskConfig(metadata={"note": "test"})
    ctx = _make_context(
        allocations=(
            PortfolioAllocation("BTC/USDT", Decimal("0.5"), "DEFI", None, "test"),
            PortfolioAllocation("ETH/USDT", Decimal("0.5"), "DEFI", None, "test"),
        ),
        total_exposure=Decimal("1.0"),
        cluster_exposure={"DEFI": Decimal("1.0")},
    )
    result = build_validated_portfolio_risk_context(ctx, config, evaluated_at=_make_dt())
    assert result.metadata["note"] == "test"


def test_build_rejects_naive_evaluated_at() -> None:
    config = PortfolioRiskConfig.default()
    ctx = _make_context(
        allocations=(PortfolioAllocation("BTC/USDT", Decimal("0.5"), "DEFI", None, "test"),),
        total_exposure=Decimal("0.5"),
        cluster_exposure={"DEFI": Decimal("0.5")},
    )
    with pytest.raises(PortfolioRiskError):
        build_validated_portfolio_risk_context(ctx, config, evaluated_at=datetime.utcnow())


def test_build_deterministic_fingerprint() -> None:
    config = PortfolioRiskConfig.default()
    ctx = _make_context(
        allocations=(
            PortfolioAllocation("BTC/USDT", Decimal("0.25"), "DEFI", None, "test"),
            PortfolioAllocation("ETH/USDT", Decimal("0.25"), "DEFI", None, "test"),
            PortfolioAllocation("SOL/USDT", Decimal("0.25"), "L1", None, "test"),
            PortfolioAllocation("ADA/USDT", Decimal("0.25"), "L1", None, "test"),
        ),
        total_exposure=Decimal("1.0"),
        cluster_exposure={"DEFI": Decimal("0.5"), "L1": Decimal("0.5")},
    )
    result1 = build_validated_portfolio_risk_context(ctx, config, evaluated_at=_make_dt())
    result2 = build_validated_portfolio_risk_context(ctx, config, evaluated_at=_make_dt())
    assert result1.risk_evaluation_fingerprint == result2.risk_evaluation_fingerprint
