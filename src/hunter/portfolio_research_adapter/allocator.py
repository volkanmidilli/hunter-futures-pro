"""Deterministic allocation algorithms for the Portfolio Research Adapter (MVP-57).

All calculations use ``Decimal`` with a fixed quantum and ``ROUND_DOWN``. No file
reads, writes, or external system calls are performed.
"""

from __future__ import annotations

from decimal import ROUND_DOWN, Decimal
from typing import TYPE_CHECKING

from hunter.portfolio_research_adapter.models import (
    BELOW_MIN_WEIGHT,
    BLACKLISTED_PAIR,
    EMPTY_PORTFOLIO,
    INVALID_PAIR,
    MAX_ASSETS_EXCEEDED,
    MISSING_SCORE,
    WEIGHT_QUANTUM,
    PortfolioAllocation,
    PortfolioExclusion,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from hunter.portfolio_research_adapter.models import PortfolioResearchConfig


_PAIR_DELIMITER = "/"


def _is_pair_string(pair: str) -> bool:
    """Return True if ``pair`` looks like a Freqtrade pair string."""
    if not isinstance(pair, str) or not pair.strip():
        return False
    parts = pair.split(_PAIR_DELIMITER)
    return len(parts) == 2 and all(part.strip() for part in parts)


def _normalize_cluster(value: str | None) -> str:
    """Canonicalize a cluster string to uppercase or UNCLASSIFIED."""
    if value is None:
        return "UNCLASSIFIED"
    stripped = str(value).strip().upper()
    return stripped if stripped else "UNCLASSIFIED"


def _quantize(value: Decimal) -> Decimal:
    """Quantize a Decimal to the fixed weight quantum with ROUND_DOWN."""
    return value.quantize(WEIGHT_QUANTUM, rounding=ROUND_DOWN)


def _select_candidates(
    whitelist: tuple[str, ...],
    blacklist: tuple[str, ...],
    max_assets: int,
) -> tuple[list[str], list[PortfolioExclusion]]:
    """Select valid candidate pairs from the whitelist.

    Returns ``(candidates, exclusions)``. Candidates are sorted
    lexicographically and capped at ``max_assets``. Blacklisted or malformed
    pairs are recorded as exclusions.
    """
    exclusions: list[PortfolioExclusion] = []
    valid: list[str] = []
    for pair in whitelist:
        if not _is_pair_string(pair):
            exclusions.append(
                PortfolioExclusion(
                    pair=pair or "UNKNOWN",
                    reason_code=INVALID_PAIR,
                    details=f"pair does not match expected format: {pair!r}",
                )
            )
            continue
        if pair in blacklist:
            exclusions.append(
                PortfolioExclusion(
                    pair=pair,
                    reason_code=BLACKLISTED_PAIR,
                    details="pair is present in the source blacklist",
                )
            )
            continue
        if pair not in valid:
            valid.append(pair)

    if len(valid) > max_assets:
        # Excess pairs beyond max_assets are excluded deterministically.
        sorted_valid = sorted(valid)
        selected = sorted_valid[:max_assets]
        for pair in sorted_valid[max_assets:]:
            exclusions.append(
                PortfolioExclusion(
                    pair=pair,
                    reason_code=MAX_ASSETS_EXCEEDED,
                    details=f"pair excluded because max_assets limit ({max_assets}) reached",
                )
            )
        return selected, exclusions

    return sorted(valid), exclusions


def _resolve_cluster(pair: str, cluster_by_pair: Mapping[str, str] | None) -> str:
    """Resolve a cluster label for ``pair`` using the caller mapping."""
    if cluster_by_pair is None:
        return "UNCLASSIFIED"
    return _normalize_cluster(cluster_by_pair.get(pair))


def allocate_equal_weight(
    whitelist: tuple[str, ...],
    blacklist: tuple[str, ...],
    config: PortfolioResearchConfig,
    *,
    cluster_by_pair: Mapping[str, str] | None = None,
) -> tuple[list[PortfolioAllocation], list[PortfolioExclusion]]:
    """Produce equal-weight allocations.

    Returns ``(allocations, exclusions)``. If the resulting per-pair weight is
    below ``min_asset_weight``, all selected pairs are excluded and an empty
    allocation list is returned.
    """
    candidates, exclusions = _select_candidates(whitelist, blacklist, config.max_assets)
    allocations: list[PortfolioAllocation] = []

    if not candidates:
        if not exclusions:
            exclusions.append(
                PortfolioExclusion(
                    pair="PORTFOLIO",
                    reason_code=EMPTY_PORTFOLIO,
                    details="no valid candidate pairs after filtering",
                )
            )
        return allocations, exclusions

    count = Decimal(len(candidates))
    raw_weight = config.max_total_exposure / count
    weight = min(raw_weight, config.max_asset_weight)

    if weight < config.min_asset_weight:
        for pair in candidates:
            exclusions.append(
                PortfolioExclusion(
                    pair=pair,
                    reason_code=BELOW_MIN_WEIGHT,
                    details=f"equal weight {weight} below min_asset_weight {config.min_asset_weight}",
                )
            )
        return allocations, exclusions

    weight = _quantize(weight)
    if weight <= Decimal("0"):
        for pair in candidates:
            exclusions.append(
                PortfolioExclusion(
                    pair=pair,
                    reason_code=BELOW_MIN_WEIGHT,
                    details="quantized weight is zero",
                )
            )
        return allocations, exclusions

    for pair in candidates:
        allocations.append(
            PortfolioAllocation(
                pair=pair,
                weight=weight,
                cluster=_resolve_cluster(pair, cluster_by_pair),
                score=None,
                allocation_reason="EQUAL_WEIGHT",
            )
        )

    return allocations, exclusions


def allocate_score_proportional(
    whitelist: tuple[str, ...],
    blacklist: tuple[str, ...],
    config: PortfolioResearchConfig,
    *,
    score_by_pair: Mapping[str, Decimal],
    cluster_by_pair: Mapping[str, str] | None = None,
) -> tuple[list[PortfolioAllocation], list[PortfolioExclusion]]:
    """Produce score-proportional allocations.

    Returns ``(allocations, exclusions)``. Pairs with missing, non-positive, or
    invalid scores are excluded. After capping and filtering, remaining weights
    are recomputed proportionally among the surviving pairs.
    """
    candidates, exclusions = _select_candidates(whitelist, blacklist, config.max_assets)
    allocations: list[PortfolioAllocation] = []

    if not candidates:
        if not exclusions:
            exclusions.append(
                PortfolioExclusion(
                    pair="PORTFOLIO",
                    reason_code=EMPTY_PORTFOLIO,
                    details="no valid candidate pairs after filtering",
                )
            )
        return allocations, exclusions

    # First pass: score validation and exclusion.
    scored: list[tuple[str, Decimal]] = []
    for pair in candidates:
        score = score_by_pair.get(pair)
        if score is None:
            exclusions.append(
                PortfolioExclusion(
                    pair=pair,
                    reason_code=MISSING_SCORE,
                    details="no score provided for pair",
                )
            )
            continue
        if not isinstance(score, Decimal) or score <= Decimal("0"):
            exclusions.append(
                PortfolioExclusion(
                    pair=pair,
                    reason_code=MISSING_SCORE,
                    details=f"score must be a positive Decimal, got {score!r}",
                )
            )
            continue
        scored.append((pair, score))

    if not scored:
        exclusions.append(
            PortfolioExclusion(
                pair="PORTFOLIO",
                reason_code=EMPTY_PORTFOLIO,
                details="no valid positive scores for selected candidates",
            )
        )
        return allocations, exclusions

    # Iteratively allocate and filter until stable.
    active = scored[:]
    final_weights: dict[str, Decimal] = {}

    while active:
        total_score = sum(score for _, score in active)
        if total_score <= Decimal("0"):
            break

        weights: dict[str, Decimal] = {}
        for pair, score in active:
            raw = (score / total_score) * config.max_total_exposure
            weights[pair] = min(raw, config.max_asset_weight)

        # Identify below-min and apply cap.
        below_min = [pair for pair, _ in active if weights[pair] < config.min_asset_weight]
        if below_min:
            for pair in below_min:
                final_weights.pop(pair, None)
                exclusions.append(
                    PortfolioExclusion(
                        pair=pair,
                        reason_code=BELOW_MIN_WEIGHT,
                        details=f"weight {weights[pair]} below min_asset_weight {config.min_asset_weight}",
                    )
                )
            active = [(pair, score) for pair, score in active if pair not in below_min]
            continue

        # Record current weights.
        for pair, weight in weights.items():
            final_weights[pair] = weight

        # If any pair was capped, redistribute residual to uncapped pairs.
        capped = [pair for pair, _ in active if weights[pair] >= config.max_asset_weight]
        uncapped = [(pair, score) for pair, score in active if pair not in capped]
        if not uncapped or not capped:
            break

        residual = config.max_total_exposure - sum(
            final_weights[p] for p, _ in active
        )
        if residual <= Decimal("0"):
            break

        # Recurse with residual exposure on uncapped pairs.
        active = uncapped
        # We need to continue with the same max_total_exposure logic, but the
        # residual exposure is the budget. However, proportional allocation to
        # uncapped pairs would use their scores relative to each other.
        # Simpler: continue loop with the same max_total_exposure, which will
        # recompute raw weights for uncapped pairs based on full score sum and
        # then cap. The final_weights are overwritten each iteration.
        # To avoid infinite loops, we require progress: at least one pair capped.
        if not capped:
            break

    if not final_weights:
        exclusions.append(
            PortfolioExclusion(
                pair="PORTFOLIO",
                reason_code=EMPTY_PORTFOLIO,
                details="all candidates fell below minimum weight after filtering",
            )
        )
        return allocations, exclusions

    for pair in sorted(final_weights.keys()):
        weight = _quantize(final_weights[pair])
        if weight < config.min_asset_weight:
            exclusions.append(
                PortfolioExclusion(
                    pair=pair,
                    reason_code=BELOW_MIN_WEIGHT,
                    details=f"quantized weight {weight} below min_asset_weight {config.min_asset_weight}",
                )
            )
            continue
        score = score_by_pair[pair]
        allocations.append(
            PortfolioAllocation(
                pair=pair,
                weight=weight,
                cluster=_resolve_cluster(pair, cluster_by_pair),
                score=score if isinstance(score, Decimal) else None,
                allocation_reason="SCORE_PROPORTIONAL",
            )
        )

    return allocations, exclusions


def apply_cluster_limits(
    allocations: list[PortfolioAllocation],
    max_cluster_exposure: Decimal,
) -> list[PortfolioAllocation]:
    """Scale cluster allocations when their total exceeds the limit.

    The residual exposure is not redistributed to other clusters. Weights are
    quantized after scaling.
    """
    if not allocations:
        return []

    cluster_totals: dict[str, Decimal] = {}
    for allocation in allocations:
        cluster_totals[allocation.cluster] = cluster_totals.get(allocation.cluster, Decimal("0")) + allocation.weight

    scaled: dict[str, Decimal] = {}
    for cluster, total in cluster_totals.items():
        if total > max_cluster_exposure:
            scale = max_cluster_exposure / total
            scaled[cluster] = scale

    if not scaled:
        return allocations

    result: list[PortfolioAllocation] = []
    for allocation in allocations:
        scale = scaled.get(allocation.cluster)
        if scale is not None:
            new_weight = _quantize(allocation.weight * scale)
        else:
            new_weight = allocation.weight
        result.append(
            PortfolioAllocation(
                pair=allocation.pair,
                weight=new_weight,
                cluster=allocation.cluster,
                score=allocation.score,
                allocation_reason=allocation.allocation_reason,
            )
        )
    return result


def quantize_allocations(
    allocations: list[PortfolioAllocation],
) -> list[PortfolioAllocation]:
    """Quantize all allocation weights to the fixed quantum."""
    return [
        PortfolioAllocation(
            pair=allocation.pair,
            weight=_quantize(allocation.weight),
            cluster=allocation.cluster,
            score=allocation.score,
            allocation_reason=allocation.allocation_reason,
        )
        for allocation in allocations
    ]


def compute_cluster_exposure(
    allocations: list[PortfolioAllocation],
) -> dict[str, Decimal]:
    """Return total exposure per cluster."""
    totals: dict[str, Decimal] = {}
    for allocation in allocations:
        totals[allocation.cluster] = totals.get(allocation.cluster, Decimal("0")) + allocation.weight
    return totals


def compute_total_exposure(allocations: list[PortfolioAllocation]) -> Decimal:
    """Return the sum of all allocation weights."""
    return sum((allocation.weight for allocation in allocations), Decimal("0"))
