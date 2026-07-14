"""Deterministic risk metrics for the Portfolio Risk Constraint Evaluator (MVP-58).

All calculations use ``Decimal`` with a fixed quantum and ``ROUND_DOWN``. No file
reads, writes, or clock access occurs here.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from types import MappingProxyType
from typing import TYPE_CHECKING

from hunter.portfolio_risk_evaluator.models import PortfolioRiskMetrics, _quantize

if TYPE_CHECKING:
    from hunter.portfolio_research_adapter.models import PortfolioAllocation


def recalculate_total_exposure(
    allocations: Sequence[PortfolioAllocation],
) -> Decimal:
    """Return the quantized sum of allocation weights."""
    return _quantize(
        sum((allocation.weight for allocation in allocations), Decimal("0"))
    )


def recalculate_cluster_exposure(
    allocations: Sequence[PortfolioAllocation],
) -> dict[str, Decimal]:
    """Return a quantized cluster exposure map."""
    cluster_exposure: dict[str, Decimal] = {}
    for allocation in allocations:
        cluster = allocation.cluster
        cluster_exposure[cluster] = _quantize(
            cluster_exposure.get(cluster, Decimal("0")) + allocation.weight
        )
    return cluster_exposure


def calculate_largest_asset_weight(
    allocations: Sequence[PortfolioAllocation],
) -> Decimal:
    """Return the largest individual asset weight, or zero if empty."""
    if not allocations:
        return Decimal("0")
    return _quantize(max(allocation.weight for allocation in allocations))


def calculate_largest_cluster_exposure(
    cluster_exposure: MappingProxyType[str, Decimal] | dict[str, Decimal],
) -> Decimal:
    """Return the largest cluster exposure, or zero if empty."""
    if not cluster_exposure:
        return Decimal("0")
    return _quantize(max(cluster_exposure.values()))


def calculate_hhi(
    allocations: Sequence[PortfolioAllocation],
    total_exposure: Decimal,
) -> Decimal:
    """Return the normalized-weight Herfindahl-Hirschman Index.

    HHI is ``sum((weight / total_exposure) ** 2)``. If ``total_exposure`` is
    zero, HHI is zero.
    """
    if total_exposure <= Decimal("0") or not allocations:
        return Decimal("0")
    hhi = Decimal("0")
    for allocation in allocations:
        normalized = _quantize(allocation.weight / total_exposure)
        hhi = _quantize(hhi + normalized * normalized)
    return _quantize(hhi)


def calculate_effective_asset_count(
    hhi: Decimal,
) -> Decimal:
    """Return the effective number of assets, ``1 / HHI``.

    If ``hhi`` is zero, returns zero.
    """
    if hhi <= Decimal("0"):
        return Decimal("0")
    return _quantize(Decimal("1") / hhi)


def build_portfolio_risk_metrics(
    allocations: Sequence[PortfolioAllocation],
) -> PortfolioRiskMetrics:
    """Build a deterministic ``PortfolioRiskMetrics`` from allocations."""
    total_exposure = recalculate_total_exposure(allocations)
    cluster_exposure = recalculate_cluster_exposure(allocations)
    largest_asset_weight = calculate_largest_asset_weight(allocations)
    largest_cluster_exposure = calculate_largest_cluster_exposure(cluster_exposure)
    hhi = calculate_hhi(allocations, total_exposure)
    effective_asset_count = calculate_effective_asset_count(hhi)

    return PortfolioRiskMetrics(
        asset_count=len(allocations),
        total_exposure=total_exposure,
        largest_asset_weight=largest_asset_weight,
        largest_cluster_exposure=largest_cluster_exposure,
        hhi=hhi,
        effective_asset_count=effective_asset_count,
        cluster_exposure=MappingProxyType(cluster_exposure),
    )
