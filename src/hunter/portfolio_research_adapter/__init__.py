"""Public API for the Portfolio Construction Research Adapter (MVP-57).

The adapter consumes a `ValidatedStrategyContext` and produces a deterministic,
research-only, human-approval-required `PortfolioResearchContext` with rule-based
portfolio allocations and exclusions.

All outputs are explicitly marked as research-only and require human approval
before any downstream use. The adapter is fail-closed and never integrates with
Freqtrade runtime, exchanges, databases, schedulers, or live trading systems.
"""

from __future__ import annotations

from hunter.portfolio_research_adapter.models import (
    BELOW_MIN_WEIGHT,
    BLACKLISTED_PAIR,
    BLOCK_ALL_CONTEXT,
    CLUSTER_LIMIT_APPLIED,
    CONTRADICTORY_CONTEXT,
    EMPTY_PORTFOLIO,
    EMPTY_WHITELIST,
    INVALID_CONFIG,
    INVALID_PAIR,
    INVALID_SCORE,
    MAX_ASSETS_EXCEEDED,
    MISSING_CONTEXT,
    MISSING_SCORE,
    PORTFOLIO_ACCEPTED,
    PORTFOLIO_RESEARCH_ADAPTER_VERSION,
    PORTFOLIO_RESEARCH_REASON_CODES,
    REJECTED_CONTEXT,
    PortfolioAllocation,
    PortfolioExclusion,
    PortfolioResearchConfig,
    PortfolioResearchContext,
    PortfolioResearchError,
)
from hunter.portfolio_research_adapter.validator import (
    check_blacklist_exclusion,
    validate_cluster_mapping,
    validate_portfolio_research_config,
    validate_portfolio_research_input,
    validate_score_mapping,
)

__all__ = [
    # Version
    "PORTFOLIO_RESEARCH_ADAPTER_VERSION",
    # Reason codes
    "MISSING_CONTEXT",
    "REJECTED_CONTEXT",
    "BLOCK_ALL_CONTEXT",
    "EMPTY_WHITELIST",
    "INVALID_CONFIG",
    "INVALID_PAIR",
    "BLACKLISTED_PAIR",
    "MISSING_SCORE",
    "INVALID_SCORE",
    "BELOW_MIN_WEIGHT",
    "MAX_ASSETS_EXCEEDED",
    "CLUSTER_LIMIT_APPLIED",
    "EMPTY_PORTFOLIO",
    "CONTRADICTORY_CONTEXT",
    "PORTFOLIO_ACCEPTED",
    "PORTFOLIO_RESEARCH_REASON_CODES",
    # Models
    "PortfolioResearchConfig",
    "PortfolioAllocation",
    "PortfolioExclusion",
    "PortfolioResearchContext",
    "PortfolioResearchError",
    # Validator
    "validate_portfolio_research_config",
    "validate_portfolio_research_input",
    "validate_cluster_mapping",
    "validate_score_mapping",
    "check_blacklist_exclusion",
]
