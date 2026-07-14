"""Portfolio risk evaluation engine for the Portfolio Risk Constraint Evaluator (MVP-58).

The engine wires structural validation, metrics, and risk-gate checks into a
single pure function. It performs no file reads, writes, or clock access beyond
the ``evaluated_at`` value injected by the caller.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from decimal import Decimal
from types import MappingProxyType
from typing import TYPE_CHECKING

from hunter.portfolio_risk_evaluator.metrics import build_portfolio_risk_metrics
from hunter.portfolio_risk_evaluator.models import (
    ASSET_COUNT_BELOW_MINIMUM,
    ASSET_WEIGHT_BELOW_MINIMUM,
    ASSET_WEIGHT_EXCEEDED,
    CLUSTER_EXPOSURE_EXCEEDED,
    EMPTY_ALLOCATIONS,
    HHI_EXCEEDED,
    MISSING_CONTEXT,
    PORTFOLIO_RISK_EVALUATOR_VERSION,
    REJECTED_PORTFOLIO_CONTEXT,
    RISK_ACCEPTED,
    TOTAL_EXPOSURE_EXCEEDED,
    TOTAL_EXPOSURE_MISMATCH,
    PortfolioRiskConfig,
    PortfolioRiskError,
    PortfolioRiskMetrics,
    ValidatedPortfolioRiskContext,
    _quantize,
)
from hunter.portfolio_risk_evaluator.validator import validate_portfolio_risk_context

if TYPE_CHECKING:
    from hunter.portfolio_research_adapter.models import PortfolioResearchContext


def _decimal_to_str(value: Decimal) -> str:
    """Return a canonical string for a Decimal value."""
    return str(value)


def _build_limits_metadata(config: PortfolioRiskConfig) -> dict[str, object]:
    """Return a JSON-safe dict of configured risk limits."""
    return {
        "min_asset_count": config.min_asset_count,
        "min_asset_weight": str(config.min_asset_weight),
        "max_single_asset_weight": str(config.max_single_asset_weight),
        "max_total_exposure": str(config.max_total_exposure),
        "max_cluster_exposure": str(config.max_cluster_exposure),
        "max_hhi": str(config.max_hhi),
        "exposure_tolerance": str(config.exposure_tolerance),
    }


def _build_canonical_fingerprint_payload(
    source_portfolio_fingerprint: str,
    config: PortfolioRiskConfig,
    metrics: PortfolioRiskMetrics,
    reason_codes: tuple[str, ...],
    evaluated_at: datetime,
) -> dict:
    """Build a deterministic JSON-serializable payload for risk fingerprinting."""
    return {
        "version": PORTFOLIO_RISK_EVALUATOR_VERSION,
        "source_portfolio_fingerprint": source_portfolio_fingerprint,
        "evaluated_at": evaluated_at.isoformat(),
        "metrics": {
            "asset_count": metrics.asset_count,
            "total_exposure": _decimal_to_str(metrics.total_exposure),
            "largest_asset_weight": _decimal_to_str(metrics.largest_asset_weight),
            "largest_cluster_exposure": _decimal_to_str(metrics.largest_cluster_exposure),
            "hhi": _decimal_to_str(metrics.hhi),
            "effective_asset_count": _decimal_to_str(metrics.effective_asset_count),
            "cluster_exposure": {
                cluster: _decimal_to_str(exposure)
                for cluster, exposure in sorted(metrics.cluster_exposure.items())
            },
        },
        "reason_codes": list(reason_codes),
        "config": {
            "min_asset_count": config.min_asset_count,
            "min_asset_weight": _decimal_to_str(config.min_asset_weight),
            "max_single_asset_weight": _decimal_to_str(config.max_single_asset_weight),
            "max_total_exposure": _decimal_to_str(config.max_total_exposure),
            "max_cluster_exposure": _decimal_to_str(config.max_cluster_exposure),
            "max_hhi": _decimal_to_str(config.max_hhi),
            "exposure_tolerance": _decimal_to_str(config.exposure_tolerance),
        },
    }


def _compute_risk_evaluation_fingerprint(payload: dict) -> str:
    """Return a deterministic SHA-256 hex digest of the canonical payload."""
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _build_fail_closed_context(
    portfolio_context: PortfolioResearchContext | None,
    config: PortfolioRiskConfig,
    evaluated_at: datetime,
    reason_codes: tuple[str, ...],
    source_portfolio_fingerprint: str = "",
) -> ValidatedPortfolioRiskContext:
    """Return a deterministic fail-closed risk validation context."""
    source_fingerprint = source_portfolio_fingerprint
    if portfolio_context is not None and hasattr(portfolio_context, "portfolio_fingerprint"):
        source_fingerprint = portfolio_context.portfolio_fingerprint
    if not source_fingerprint:
        source_fingerprint = "UNKNOWN"

    metrics = PortfolioRiskMetrics(
        asset_count=0,
        total_exposure=Decimal("0"),
        largest_asset_weight=Decimal("0"),
        largest_cluster_exposure=Decimal("0"),
        hhi=Decimal("0"),
        effective_asset_count=Decimal("0"),
        cluster_exposure=MappingProxyType({}),
    )

    payload = _build_canonical_fingerprint_payload(
        source_fingerprint,
        config,
        metrics,
        reason_codes,
        evaluated_at,
    )
    fingerprint = _compute_risk_evaluation_fingerprint(payload)

    return ValidatedPortfolioRiskContext(
        version=PORTFOLIO_RISK_EVALUATOR_VERSION,
        source_portfolio_fingerprint=source_fingerprint,
        risk_evaluation_fingerprint=fingerprint,
        evaluated_at=evaluated_at,
        accepted=False,
        risk_gate_open=False,
        mode="BLOCK_ALL",
        validated_allocations=(),
        metrics=metrics,
        reason_codes=reason_codes,
        research_only=True,
        human_approval_required=True,
        metadata=config.metadata,
    )


def _apply_risk_gate(
    allocations: tuple,
    metrics: PortfolioRiskMetrics,
    config: PortfolioRiskConfig,
    structural_reasons: list[str],
) -> tuple[bool, list[str]]:
    """Apply risk limits and return ``(accepted, reason_codes)``.

    ``accepted`` is True only when no structural or limit violation exists.
    """
    reasons = list(structural_reasons)

    if metrics.asset_count < config.min_asset_count:
        reasons.append(ASSET_COUNT_BELOW_MINIMUM)

    for allocation in allocations:
        if allocation.weight < config.min_asset_weight:
            reasons.append(ASSET_WEIGHT_BELOW_MINIMUM)
        if allocation.weight > config.max_single_asset_weight:
            reasons.append(ASSET_WEIGHT_EXCEEDED)

    if metrics.total_exposure > config.max_total_exposure:
        reasons.append(TOTAL_EXPOSURE_EXCEEDED)

    for cluster, exposure in sorted(metrics.cluster_exposure.items()):
        if exposure > config.max_cluster_exposure:
            reasons.append(CLUSTER_EXPOSURE_EXCEEDED)

    if metrics.hhi > config.max_hhi:
        reasons.append(HHI_EXCEEDED)

    return len(reasons) == 0, reasons


def build_validated_portfolio_risk_context(
    portfolio_context: PortfolioResearchContext | None,
    config: PortfolioRiskConfig,
    *,
    evaluated_at: datetime,
) -> ValidatedPortfolioRiskContext:
    """Build a deterministic ``ValidatedPortfolioRiskContext`` from a portfolio context.

    The function is fail-closed: missing, rejected, blocked, or inconsistent
    inputs produce an empty validated allocation set with ``accepted=False``,
    ``risk_gate_open=False``, and explicit reason codes.
    """
    if not isinstance(evaluated_at, datetime) or evaluated_at.tzinfo is None:
        raise PortfolioRiskError(
            "evaluated_at must be a timezone-aware datetime",
            reason_code="INVALID_CONFIG",
        )

    # Initial structural validation.
    is_valid, structural_reasons = validate_portfolio_risk_context(portfolio_context, config)
    if not is_valid:
        # Map early structural reasons to a deterministic fail-closed set.
        fail_reasons: list[str] = []
        if portfolio_context is None:
            fail_reasons.append(MISSING_CONTEXT)
        elif not getattr(portfolio_context, "accepted", False):
            fail_reasons.append(REJECTED_PORTFOLIO_CONTEXT)
        elif getattr(portfolio_context, "mode", None) == "BLOCK_ALL":
            fail_reasons.append(EMPTY_ALLOCATIONS)
        else:
            fail_reasons.extend(structural_reasons)
        return _build_fail_closed_context(
            portfolio_context,
            config,
            evaluated_at,
            tuple(fail_reasons),
        )

    assert portfolio_context is not None
    allocations = portfolio_context.allocations
    source_fingerprint = portfolio_context.portfolio_fingerprint

    metrics = build_portfolio_risk_metrics(allocations)

    # Validate that recalculated total matches recorded total (defensive).
    if abs(metrics.total_exposure - portfolio_context.total_exposure) > config.exposure_tolerance:
        return _build_fail_closed_context(
            portfolio_context,
            config,
            evaluated_at,
            (TOTAL_EXPOSURE_MISMATCH,),
            source_fingerprint,
        )

    accepted, gate_reasons = _apply_risk_gate(allocations, metrics, config, structural_reasons)

    if not accepted:
        return _build_fail_closed_context(
            portfolio_context,
            config,
            evaluated_at,
            tuple(gate_reasons),
            source_fingerprint,
        )

    validated_allocations = tuple(allocations)
    reason_codes = [RISK_ACCEPTED]
    if structural_reasons:
        reason_codes.extend(structural_reasons)

    combined_metadata = dict(config.metadata)
    combined_metadata["limits"] = _build_limits_metadata(config)

    payload = _build_canonical_fingerprint_payload(
        source_fingerprint,
        config,
        metrics,
        tuple(reason_codes),
        evaluated_at,
    )
    fingerprint = _compute_risk_evaluation_fingerprint(payload)

    return ValidatedPortfolioRiskContext(
        version=PORTFOLIO_RISK_EVALUATOR_VERSION,
        source_portfolio_fingerprint=source_fingerprint,
        risk_evaluation_fingerprint=fingerprint,
        evaluated_at=evaluated_at,
        accepted=True,
        risk_gate_open=True,
        mode=portfolio_context.mode,
        validated_allocations=validated_allocations,
        metrics=metrics,
        reason_codes=tuple(reason_codes),
        research_only=True,
        human_approval_required=True,
        metadata=combined_metadata,
    )
