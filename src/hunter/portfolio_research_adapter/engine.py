"""Portfolio research context engine for the Portfolio Research Adapter (MVP-57).

The engine wires validation, allocation, and constraint enforcement into a single
pure function. It performs no file reads, writes, or clock access beyond the
``generated_at`` value injected by the caller.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from types import MappingProxyType
from typing import TYPE_CHECKING

from hunter.portfolio_research_adapter.allocator import (
    allocate_equal_weight,
    allocate_score_proportional,
    apply_cluster_limits,
    compute_cluster_exposure,
    compute_total_exposure,
)
from hunter.portfolio_research_adapter.models import (
    CLUSTER_LIMIT_APPLIED,
    EMPTY_PORTFOLIO,
    MISSING_CONTEXT,
    PORTFOLIO_ACCEPTED,
    PORTFOLIO_RESEARCH_ADAPTER_VERSION,
    PortfolioAllocation,
    PortfolioExclusion,
    PortfolioResearchConfig,
    PortfolioResearchContext,
    PortfolioResearchError,
)
from hunter.portfolio_research_adapter.validator import (
    validate_cluster_mapping,
    validate_portfolio_research_config,
    validate_portfolio_research_input,
    validate_score_mapping,
)

if TYPE_CHECKING:
    from hunter.strategy_contract_consumer.models import ValidatedStrategyContext


def _coerce_mapping_str_str(
    value: Mapping[str, str] | dict[str, str] | None,
) -> Mapping[str, str]:
    if value is None:
        return MappingProxyType({})
    coerced = {str(k): str(v) for k, v in value.items()}
    return MappingProxyType(coerced)


def _coerce_mapping_str_decimal(
    value: Mapping[str, Decimal] | dict[str, Decimal] | None,
) -> Mapping[str, Decimal]:
    if value is None:
        return MappingProxyType({})
    coerced = {}
    for k, v in value.items():
        if not isinstance(v, Decimal):
            raise PortfolioResearchError(
                f"score_by_pair value must be a Decimal, got {v!r}",
                reason_code="INVALID_CONFIG",
            )
        coerced[str(k)] = v
    return MappingProxyType(coerced)


def _decimal_to_str(value: Decimal) -> str:
    """Return a canonical string for a Decimal value."""
    return str(value)


def _build_canonical_fingerprint_payload(
    strategy_context: ValidatedStrategyContext,
    config: PortfolioResearchConfig,
    allocations: tuple[PortfolioAllocation, ...],
    exclusions: tuple[PortfolioExclusion, ...],
    generated_at: datetime,
) -> dict:
    """Build a deterministic JSON-serializable payload for fingerprinting."""
    return {
        "version": PORTFOLIO_RESEARCH_ADAPTER_VERSION,
        "source_context_fingerprint": strategy_context.source_fingerprint,
        "generated_at": generated_at.isoformat(),
        "mode": strategy_context.mode,
        "allocation_method": config.allocation_method,
        "max_assets": config.max_assets,
        "min_asset_weight": _decimal_to_str(config.min_asset_weight),
        "max_asset_weight": _decimal_to_str(config.max_asset_weight),
        "max_total_exposure": _decimal_to_str(config.max_total_exposure),
        "max_cluster_exposure": _decimal_to_str(config.max_cluster_exposure),
        "allocations": [
            {
                "pair": a.pair,
                "weight": _decimal_to_str(a.weight),
                "cluster": a.cluster,
                "score": _decimal_to_str(a.score) if a.score is not None else None,
                "allocation_reason": a.allocation_reason,
            }
            for a in allocations
        ],
        "exclusions": [
            {
                "pair": e.pair,
                "reason_code": e.reason_code,
                "details": e.details,
            }
            for e in exclusions
        ],
    }


def _compute_portfolio_fingerprint(payload: dict) -> str:
    """Return a deterministic SHA-256 hex digest of the canonical payload."""
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _build_fail_closed_context(
    strategy_context: ValidatedStrategyContext | None,
    config: PortfolioResearchConfig,
    generated_at: datetime,
    reason_codes: tuple[str, ...],
    source_context_fingerprint: str = "",
) -> PortfolioResearchContext:
    """Return a deterministic fail-closed portfolio research context."""
    source_fingerprint = source_context_fingerprint
    if strategy_context is not None:
        source_fingerprint = strategy_context.source_fingerprint
    if not source_fingerprint:
        source_fingerprint = "UNKNOWN"

    # A fail-closed context fingerprint is based on the empty allocation set.
    payload = {
        "version": PORTFOLIO_RESEARCH_ADAPTER_VERSION,
        "source_context_fingerprint": source_fingerprint,
        "generated_at": generated_at.isoformat(),
        "mode": "BLOCK_ALL",
        "allocation_method": config.allocation_method,
        "allocations": [],
        "exclusions": [],
    }
    fingerprint = _compute_portfolio_fingerprint(payload)

    return PortfolioResearchContext(
        version=PORTFOLIO_RESEARCH_ADAPTER_VERSION,
        source_context_fingerprint=source_fingerprint,
        portfolio_fingerprint=fingerprint,
        generated_at=generated_at,
        mode="BLOCK_ALL",
        allocation_method=config.allocation_method,
        allocations=(),
        exclusions=(),
        cluster_exposure=MappingProxyType({}),
        total_exposure=Decimal("0"),
        accepted=False,
        research_only=True,
        human_approval_required=True,
        reason_codes=reason_codes,
        metadata=config.metadata,
    )


def build_portfolio_research_context(
    strategy_context: ValidatedStrategyContext | None,
    config: PortfolioResearchConfig,
    *,
    cluster_by_pair: Mapping[str, str] | dict[str, str] | None = None,
    score_by_pair: Mapping[str, Decimal] | dict[str, Decimal] | None = None,
    generated_at: datetime,
) -> PortfolioResearchContext:
    """Build a deterministic ``PortfolioResearchContext`` from a validated strategy context.

    The function is fail-closed: missing, rejected, blocked, or inconsistent inputs
    produce an empty portfolio with ``accepted=False`` and explicit reason codes.
    """
    validate_portfolio_research_config(config)

    # Validate and freeze caller mappings to avoid downstream mutation.
    cluster_mapping = _coerce_mapping_str_str(cluster_by_pair)
    score_mapping = _coerce_mapping_str_decimal(score_by_pair)

    validate_cluster_mapping(cluster_mapping)

    # Input validation
    is_valid, input_reasons = validate_portfolio_research_input(strategy_context, config)
    if not is_valid:
        return _build_fail_closed_context(
            strategy_context,
            config,
            generated_at,
            tuple(input_reasons),
        )

    assert strategy_context is not None
    assert strategy_context.mode in {"LONG", "SHORT"}

    # Allocation
    if config.allocation_method == "EQUAL_WEIGHT":
        allocations, exclusions = allocate_equal_weight(
            whitelist=strategy_context.whitelist,
            blacklist=strategy_context.blacklist,
            config=config,
            cluster_by_pair=cluster_mapping,
        )
    elif config.allocation_method == "SCORE_PROPORTIONAL":
        # Score mapping validation for the selected candidates.
        allocations, exclusions = allocate_score_proportional(
            whitelist=strategy_context.whitelist,
            blacklist=strategy_context.blacklist,
            config=config,
            score_by_pair=score_mapping,
            cluster_by_pair=cluster_mapping,
        )
    else:
        # Config model already validates the allocation method, so this branch is
        # defensive only.
        return _build_fail_closed_context(
            strategy_context,
            config,
            generated_at,
            ("INVALID_CONFIG",),
        )

    # Apply cluster limits and quantize.
    pre_cluster_exposure = compute_cluster_exposure(allocations)
    allocations = apply_cluster_limits(allocations, config.max_cluster_exposure)
    post_cluster_exposure = compute_cluster_exposure(allocations)

    cluster_limit_applied = any(
        post_cluster_exposure.get(cluster, Decimal("0")) < pre_cluster_exposure.get(cluster, Decimal("0"))
        for cluster in pre_cluster_exposure
    )

    total_exposure = compute_total_exposure(allocations)

    if not allocations:
        final_reasons = list(input_reasons)
        final_reasons.append(EMPTY_PORTFOLIO)
        return _build_fail_closed_context(
            strategy_context,
            config,
            generated_at,
            tuple(final_reasons),
        )

    # Build fingerprint.
    allocations_tuple = tuple(allocations)
    exclusions_tuple = tuple(exclusions)
    payload = _build_canonical_fingerprint_payload(
        strategy_context,
        config,
        allocations_tuple,
        exclusions_tuple,
        generated_at,
    )
    fingerprint = _compute_portfolio_fingerprint(payload)

    reason_codes = [PORTFOLIO_ACCEPTED]
    if cluster_limit_applied:
        reason_codes.append(CLUSTER_LIMIT_APPLIED)

    return PortfolioResearchContext(
        version=PORTFOLIO_RESEARCH_ADAPTER_VERSION,
        source_context_fingerprint=strategy_context.source_fingerprint,
        portfolio_fingerprint=fingerprint,
        generated_at=generated_at,
        mode=strategy_context.mode,
        allocation_method=config.allocation_method,
        allocations=allocations_tuple,
        exclusions=exclusions_tuple,
        cluster_exposure=MappingProxyType(post_cluster_exposure),
        total_exposure=total_exposure,
        accepted=True,
        research_only=True,
        human_approval_required=True,
        reason_codes=tuple(reason_codes),
        metadata=config.metadata,
    )
