"""Structural validation for the Portfolio Risk Constraint Evaluator (MVP-58).

All validators are pure functions: they perform no file reads, writes, or clock
access. They return a deterministic list of reason codes and a boolean
validity flag.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from typing import TYPE_CHECKING

from hunter.portfolio_research_adapter.models import PortfolioResearchContext

from hunter.portfolio_risk_evaluator.metrics import (
    recalculate_cluster_exposure,
    recalculate_total_exposure,
)
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
    _quantize,
)

if TYPE_CHECKING:
    from hunter.portfolio_research_adapter.models import PortfolioAllocation


def _is_canonical_pair(pair: str) -> bool:
    """Return True if the pair string looks like canonical BASE/QUOTE."""
    if not pair or "/" not in pair:
        return False
    parts = pair.split("/")
    return len(parts) == 2 and all(part.strip() for part in parts)


def _validate_allocations_structural(
    allocations: Sequence[PortfolioAllocation],
) -> tuple[bool, list[str]]:
    """Validate allocation list for duplicates, canonical pairs, and finite weights."""
    reasons: list[str] = []
    seen: set[str] = set()

    if not allocations:
        reasons.append(EMPTY_ALLOCATIONS)
        return False, reasons

    for allocation in allocations:
        if not _is_canonical_pair(allocation.pair):
            reasons.append(INVALID_ALLOCATION)
        if not isinstance(allocation.weight, Decimal):
            reasons.append(INVALID_WEIGHT)
            continue
        if not allocation.weight.is_finite() or allocation.weight <= Decimal("0"):
            reasons.append(INVALID_WEIGHT)
        if allocation.pair in seen:
            reasons.append(DUPLICATE_PAIR)
        else:
            seen.add(allocation.pair)

    return len(reasons) == 0, reasons


def validate_portfolio_risk_config(config: PortfolioRiskConfig) -> None:
    """Validate a risk config; raise ``PortfolioRiskError`` on problems.

    The dataclass ``__post_init__`` already validates most fields; this function
    provides an explicit validation entry point for callers.
    """
    if not isinstance(config, PortfolioRiskConfig):
        raise PortfolioRiskError(
            f"config must be a PortfolioRiskConfig, got {config!r}",
            reason_code=INVALID_CONFIG,
        )


def validate_portfolio_risk_context(
    portfolio_context: PortfolioResearchContext | None,
    config: PortfolioRiskConfig,
) -> tuple[bool, list[str]]:
    """Validate a portfolio research context for risk evaluation.

    Returns ``(is_valid, reason_codes)``. Does not mutate inputs.
    """
    reasons: list[str] = []

    validate_portfolio_risk_config(config)

    if portfolio_context is None:
        reasons.append(MISSING_CONTEXT)
        return False, reasons

    # Duck-type check for the required context attributes.
    required_attrs = (
        "accepted", "mode", "research_only", "human_approval_required",
        "allocations", "exclusions", "total_exposure", "cluster_exposure",
    )
    missing = [attr for attr in required_attrs if not hasattr(portfolio_context, attr)]
    if missing:
        reasons.append(INVALID_ALLOCATION)
        return False, reasons

    if not portfolio_context.accepted:
        reasons.append(REJECTED_PORTFOLIO_CONTEXT)
        return False, reasons

    if portfolio_context.mode == "BLOCK_ALL":
        reasons.append(BLOCK_ALL_CONTEXT)
        return False, reasons

    if portfolio_context.mode not in {"LONG", "SHORT"}:
        reasons.append(CONTRADICTORY_CONTEXT)
        return False, reasons

    # Safety invariants from the source context.
    if not portfolio_context.research_only or not portfolio_context.human_approval_required:
        reasons.append(CONTRADICTORY_CONTEXT)
        return False, reasons

    allocations = portfolio_context.allocations

    structural_ok, structural_reasons = _validate_allocations_structural(allocations)
    reasons.extend(structural_reasons)
    if not structural_ok:
        return False, reasons

    # Blacklist conflict: no allocated pair may also appear in exclusions.
    excluded_pairs = {exclusion.pair for exclusion in portfolio_context.exclusions}
    for allocation in allocations:
        if allocation.pair in excluded_pairs:
            reasons.append(BLACKLIST_CONFLICT)
            break

    # Recalculate total exposure and compare to recorded total within tolerance.
    recalculated_total = recalculate_total_exposure(allocations)
    tolerance = config.exposure_tolerance
    if abs(recalculated_total - portfolio_context.total_exposure) > tolerance:
        reasons.append(TOTAL_EXPOSURE_MISMATCH)

    # Recalculate cluster exposure and compare to recorded map.
    recalculated_clusters = recalculate_cluster_exposure(allocations)
    recorded_clusters = dict(portfolio_context.cluster_exposure)
    all_clusters = set(recalculated_clusters.keys()) | set(recorded_clusters.keys())
    for cluster in sorted(all_clusters):
        recorded = recorded_clusters.get(cluster, Decimal("0"))
        recalculated = recalculated_clusters.get(cluster, Decimal("0"))
        if abs(recalculated - recorded) > tolerance:
            reasons.append(CLUSTER_EXPOSURE_MISMATCH)
            break

    return len(reasons) == 0, reasons
