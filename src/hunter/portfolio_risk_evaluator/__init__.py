"""Public API for the Portfolio Risk Constraint Evaluator (MVP-58).

The evaluator consumes a ``PortfolioResearchContext`` and produces a
deterministic, research-only, human-approval-required
``ValidatedPortfolioRiskContext`` that validates static portfolio structure and
exposure risks.

All outputs are explicitly marked as research-only and require human approval
before any downstream use. The evaluator is fail-closed and never integrates
with Freqtrade runtime, exchanges, databases, schedulers, or live trading
systems.
"""

from __future__ import annotations

from hunter.portfolio_risk_evaluator.models import (
    ASSET_COUNT_BELOW_MINIMUM,
    ASSET_WEIGHT_BELOW_MINIMUM,
    ASSET_WEIGHT_EXCEEDED,
    BLACKLIST_CONFLICT,
    BLOCK_ALL_CONTEXT,
    CLUSTER_EXPOSURE_EXCEEDED,
    CLUSTER_EXPOSURE_MISMATCH,
    CONTRADICTORY_CONTEXT,
    DUPLICATE_PAIR,
    EMPTY_ALLOCATIONS,
    HHI_EXCEEDED,
    INVALID_ALLOCATION,
    INVALID_CONFIG,
    INVALID_WEIGHT,
    MISSING_CONTEXT,
    PORTFOLIO_RISK_EVALUATOR_VERSION,
    PORTFOLIO_RISK_REASON_CODES,
    REJECTED_PORTFOLIO_CONTEXT,
    RISK_ACCEPTED,
    TOTAL_EXPOSURE_EXCEEDED,
    TOTAL_EXPOSURE_MISMATCH,
    PortfolioRiskConfig,
    PortfolioRiskError,
    PortfolioRiskMetrics,
    ValidatedPortfolioRiskContext,
)

from hunter.portfolio_risk_evaluator.engine import build_validated_portfolio_risk_context
from hunter.portfolio_risk_evaluator.metrics import (
    build_portfolio_risk_metrics,
    calculate_effective_asset_count,
    calculate_hhi,
    calculate_largest_asset_weight,
    calculate_largest_cluster_exposure,
    recalculate_cluster_exposure,
    recalculate_total_exposure,
)
from hunter.portfolio_risk_evaluator.validator import (
    validate_portfolio_risk_config,
    validate_portfolio_risk_context,
)
from hunter.portfolio_risk_evaluator.writer import (
    PortfolioRiskWriterError,
    atomic_write_json_portfolio_risk_context,
    atomic_write_markdown_portfolio_risk_context,
    portfolio_risk_context_to_dict,
    portfolio_risk_context_to_json_text,
    portfolio_risk_context_to_markdown_text,
    write_portfolio_risk_context,
)

__all__ = [
    # Version
    "PORTFOLIO_RISK_EVALUATOR_VERSION",
    # Reason codes
    "MISSING_CONTEXT",
    "REJECTED_PORTFOLIO_CONTEXT",
    "BLOCK_ALL_CONTEXT",
    "EMPTY_ALLOCATIONS",
    "INVALID_CONFIG",
    "INVALID_ALLOCATION",
    "INVALID_WEIGHT",
    "DUPLICATE_PAIR",
    "BLACKLIST_CONFLICT",
    "TOTAL_EXPOSURE_MISMATCH",
    "TOTAL_EXPOSURE_EXCEEDED",
    "ASSET_COUNT_BELOW_MINIMUM",
    "ASSET_WEIGHT_BELOW_MINIMUM",
    "ASSET_WEIGHT_EXCEEDED",
    "CLUSTER_EXPOSURE_MISMATCH",
    "CLUSTER_EXPOSURE_EXCEEDED",
    "HHI_EXCEEDED",
    "CONTRADICTORY_CONTEXT",
    "RISK_ACCEPTED",
    "PORTFOLIO_RISK_REASON_CODES",
    # Models
    "PortfolioRiskConfig",
    "PortfolioRiskMetrics",
    "ValidatedPortfolioRiskContext",
    "PortfolioRiskError",
    # Validator
    "validate_portfolio_risk_config",
    "validate_portfolio_risk_context",
    # Metrics
    "recalculate_total_exposure",
    "recalculate_cluster_exposure",
    "calculate_hhi",
    "calculate_effective_asset_count",
    "calculate_largest_asset_weight",
    "calculate_largest_cluster_exposure",
    "build_portfolio_risk_metrics",
    # Engine
    "build_validated_portfolio_risk_context",
    # Writer
    "PortfolioRiskWriterError",
    "portfolio_risk_context_to_dict",
    "portfolio_risk_context_to_json_text",
    "portfolio_risk_context_to_markdown_text",
    "write_portfolio_risk_context",
    "atomic_write_json_portfolio_risk_context",
    "atomic_write_markdown_portfolio_risk_context",
]
