"""Tests for portfolio risk metrics."""

from __future__ import annotations

from decimal import Decimal

import pytest

from hunter.portfolio_research_adapter.models import PortfolioAllocation
from hunter.portfolio_risk_evaluator.metrics import (
    build_portfolio_risk_metrics,
    calculate_effective_asset_count,
    calculate_hhi,
    calculate_largest_asset_weight,
    calculate_largest_cluster_exposure,
    recalculate_cluster_exposure,
    recalculate_total_exposure,
)


def test_recalculate_total_exposure_empty() -> None:
    assert recalculate_total_exposure(()) == Decimal("0")


def test_recalculate_total_exposure() -> None:
    allocations = (
        PortfolioAllocation("BTC/USDT", Decimal("0.3"), "DEFI", None, "test"),
        PortfolioAllocation("ETH/USDT", Decimal("0.4"), "DEFI", None, "test"),
    )
    assert recalculate_total_exposure(allocations) == Decimal("0.7")


def test_recalculate_total_exposure_quantization() -> None:
    allocations = (
        PortfolioAllocation("BTC/USDT", Decimal("0.333333333"), "DEFI", None, "test"),
    )
    assert recalculate_total_exposure(allocations) == Decimal("0.33333333")


def test_recalculate_cluster_exposure() -> None:
    allocations = (
        PortfolioAllocation("BTC/USDT", Decimal("0.3"), "DEFI", None, "test"),
        PortfolioAllocation("ETH/USDT", Decimal("0.4"), "DEFI", None, "test"),
        PortfolioAllocation("SOL/USDT", Decimal("0.2"), "L1", None, "test"),
    )
    clusters = recalculate_cluster_exposure(allocations)
    assert clusters["DEFI"] == Decimal("0.7")
    assert clusters["L1"] == Decimal("0.2")


def test_calculate_largest_asset_weight() -> None:
    allocations = (
        PortfolioAllocation("BTC/USDT", Decimal("0.3"), "DEFI", None, "test"),
        PortfolioAllocation("ETH/USDT", Decimal("0.5"), "DEFI", None, "test"),
    )
    assert calculate_largest_asset_weight(allocations) == Decimal("0.5")


def test_calculate_largest_asset_weight_empty() -> None:
    assert calculate_largest_asset_weight(()) == Decimal("0")


def test_calculate_largest_cluster_exposure() -> None:
    clusters = {"DEFI": Decimal("0.7"), "L1": Decimal("0.2")}
    assert calculate_largest_cluster_exposure(clusters) == Decimal("0.7")


def test_calculate_largest_cluster_exposure_empty() -> None:
    assert calculate_largest_cluster_exposure({}) == Decimal("0")


def test_calculate_hhi_equal_weights() -> None:
    allocations = (
        PortfolioAllocation("BTC/USDT", Decimal("0.25"), "DEFI", None, "test"),
        PortfolioAllocation("ETH/USDT", Decimal("0.25"), "DEFI", None, "test"),
        PortfolioAllocation("SOL/USDT", Decimal("0.25"), "L1", None, "test"),
        PortfolioAllocation("ADA/USDT", Decimal("0.25"), "L1", None, "test"),
    )
    hhi = calculate_hhi(allocations, Decimal("1.0"))
    assert hhi == Decimal("0.25")


def test_calculate_hhi_single_asset() -> None:
    allocations = (
        PortfolioAllocation("BTC/USDT", Decimal("1.0"), "DEFI", None, "test"),
    )
    hhi = calculate_hhi(allocations, Decimal("1.0"))
    assert hhi == Decimal("1.0")


def test_calculate_hhi_zero_exposure() -> None:
    assert calculate_hhi((), Decimal("0")) == Decimal("0")


def test_calculate_hhi_uses_quantization() -> None:
    allocations = (
        PortfolioAllocation("BTC/USDT", Decimal("0.33333333"), "DEFI", None, "test"),
        PortfolioAllocation("ETH/USDT", Decimal("0.33333333"), "DEFI", None, "test"),
        PortfolioAllocation("SOL/USDT", Decimal("0.33333334"), "L1", None, "test"),
    )
    hhi = calculate_hhi(allocations, Decimal("1.0"))
    assert hhi > Decimal("0")


def test_calculate_effective_asset_count() -> None:
    assert calculate_effective_asset_count(Decimal("0.25")) == Decimal("4")


def test_calculate_effective_asset_count_zero() -> None:
    assert calculate_effective_asset_count(Decimal("0")) == Decimal("0")


def test_build_portfolio_risk_metrics() -> None:
    allocations = (
        PortfolioAllocation("BTC/USDT", Decimal("0.25"), "DEFI", None, "test"),
        PortfolioAllocation("ETH/USDT", Decimal("0.25"), "DEFI", None, "test"),
        PortfolioAllocation("SOL/USDT", Decimal("0.25"), "L1", None, "test"),
        PortfolioAllocation("ADA/USDT", Decimal("0.25"), "L1", None, "test"),
    )
    metrics = build_portfolio_risk_metrics(allocations)
    assert metrics.asset_count == 4
    assert metrics.total_exposure == Decimal("1.0")
    assert metrics.largest_asset_weight == Decimal("0.25")
    assert metrics.largest_cluster_exposure == Decimal("0.5")
    assert metrics.hhi == Decimal("0.25")
    assert metrics.effective_asset_count == Decimal("4")
    assert dict(metrics.cluster_exposure) == {"DEFI": Decimal("0.5"), "L1": Decimal("0.5")}


def test_build_portfolio_risk_metrics_empty() -> None:
    metrics = build_portfolio_risk_metrics(())
    assert metrics.asset_count == 0
    assert metrics.total_exposure == Decimal("0")
    assert metrics.largest_asset_weight == Decimal("0")
    assert metrics.largest_cluster_exposure == Decimal("0")
    assert metrics.hhi == Decimal("0")
    assert metrics.effective_asset_count == Decimal("0")
    assert dict(metrics.cluster_exposure) == {}
