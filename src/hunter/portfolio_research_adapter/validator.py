"""Pure validators for the Portfolio Construction Research Adapter (MVP-57).

Validators are side-effect free: no file reads, writes, clock access, or external
system calls. Invalid configuration raises ``PortfolioResearchError``. Invalid
inputs are encoded in deterministic reason-code lists.
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal
from typing import TYPE_CHECKING

from hunter.portfolio_research_adapter.models import (
    BLACKLISTED_PAIR,
    BLOCK_ALL_CONTEXT,
    CONTRADICTORY_CONTEXT,
    EMPTY_WHITELIST,
    INVALID_CONFIG,
    INVALID_PAIR,
    INVALID_SCORE,
    MISSING_CONTEXT,
    MISSING_SCORE,
    PORTFOLIO_ACCEPTED,
    REJECTED_CONTEXT,
    PortfolioResearchConfig,
    PortfolioResearchError,
)

if TYPE_CHECKING:
    from hunter.strategy_contract_consumer.models import ValidatedStrategyContext


_PAIR_DELIMITER = "/"


def _is_pair_string(pair: str) -> bool:
    """Return True if ``pair`` looks like a Freqtrade pair string."""
    if not isinstance(pair, str) or not pair.strip():
        return False
    parts = pair.split(_PAIR_DELIMITER)
    return len(parts) == 2 and all(part.strip() for part in parts)


def validate_portfolio_research_config(config: PortfolioResearchConfig) -> None:
    """Validate a portfolio research config; raise PortfolioResearchError on failure."""
    if config is None:
        raise PortfolioResearchError("config is required", reason_code=INVALID_CONFIG)
    if not isinstance(config, PortfolioResearchConfig):
        raise PortfolioResearchError(
            f"config must be a PortfolioResearchConfig, got {type(config).__name__}",
            reason_code=INVALID_CONFIG,
        )


def validate_portfolio_research_input(
    strategy_context: ValidatedStrategyContext | None,
    config: PortfolioResearchConfig,
) -> tuple[bool, list[str]]:
    """Validate the strategy context input.

    Returns ``(is_valid, reason_codes)``. The caller decides whether to proceed
    with allocation or produce a fail-closed result. No exceptions are raised
    for normal fail-closed states.
    """
    reason_codes: list[str] = []

    if strategy_context is None:
        reason_codes.append(MISSING_CONTEXT)
        return False, reason_codes

    if not strategy_context.accepted:
        reason_codes.append(REJECTED_CONTEXT)
        return False, reason_codes

    if strategy_context.mode == "BLOCK_ALL":
        reason_codes.append(BLOCK_ALL_CONTEXT)
        return False, reason_codes

    if not strategy_context.whitelist:
        reason_codes.append(EMPTY_WHITELIST)
        return False, reason_codes

    if strategy_context.mode not in {"LONG", "SHORT"}:
        reason_codes.append(INVALID_PAIR)
        return False, reason_codes

    if not strategy_context.research_only or not strategy_context.human_approval_required:
        reason_codes.append(CONTRADICTORY_CONTEXT)
        return False, reason_codes

    # Pair-level validation
    whitelist_set = set(strategy_context.whitelist)
    blacklist_set = set(strategy_context.blacklist)

    for pair in strategy_context.whitelist:
        if not _is_pair_string(pair):
            reason_codes.append(INVALID_PAIR)
            return False, reason_codes

    if whitelist_set & blacklist_set:
        reason_codes.append(CONTRADICTORY_CONTEXT)
        return False, reason_codes

    # Duplicates within a list are invalid input.
    if len(whitelist_set) != len(strategy_context.whitelist):
        reason_codes.append(CONTRADICTORY_CONTEXT)
        return False, reason_codes

    if len(blacklist_set) != len(strategy_context.blacklist):
        reason_codes.append(CONTRADICTORY_CONTEXT)
        return False, reason_codes

    reason_codes.append(PORTFOLIO_ACCEPTED)
    return True, reason_codes


def validate_cluster_mapping(
    cluster_by_pair: MappingProxyType[str, str] | dict[str, str] | None,
) -> None:
    """Validate that the cluster mapping is a valid mapping of strings."""
    if cluster_by_pair is None:
        return
    if not isinstance(cluster_by_pair, Mapping):
        raise PortfolioResearchError(
            f"cluster_by_pair must be a Mapping, got {type(cluster_by_pair).__name__}",
            reason_code=INVALID_CONFIG,
        )
    for pair, cluster in cluster_by_pair.items():
        if not isinstance(pair, str) or not pair.strip():
            raise PortfolioResearchError(
                f"cluster_by_pair key must be a non-empty string, got {pair!r}",
                reason_code=INVALID_CONFIG,
            )
        if not isinstance(cluster, str):
            raise PortfolioResearchError(
                f"cluster_by_pair value must be a string, got {cluster!r}",
                reason_code=INVALID_CONFIG,
            )


def validate_score_mapping(
    score_by_pair: MappingProxyType[str, Decimal] | dict[str, Decimal] | None,
    selected_pairs: tuple[str, ...],
    allocation_method: str,
) -> tuple[bool, list[str], list[tuple[str, str]]]:
    """Validate per-pair scores when using score-proportional allocation.

    Returns ``(is_valid, reason_codes, exclusions)``. Exclusions are a list of
    ``(pair, reason_code)`` tuples for pairs that are disqualified due to
    missing or invalid scores. Invalid ``score_by_pair`` itself raises
    ``PortfolioResearchError``.
    """
    reason_codes: list[str] = []
    exclusions: list[tuple[str, str]] = []

    if allocation_method != "SCORE_PROPORTIONAL":
        return True, reason_codes, exclusions

    if score_by_pair is None:
        reason_codes.append(MISSING_SCORE)
        return False, reason_codes, exclusions

    if not isinstance(score_by_pair, Mapping):
        raise PortfolioResearchError(
            f"score_by_pair must be a Mapping, got {type(score_by_pair).__name__}",
            reason_code=INVALID_CONFIG,
        )

    for pair, score in score_by_pair.items():
        if not isinstance(pair, str) or not pair.strip():
            raise PortfolioResearchError(
                f"score_by_pair key must be a non-empty string, got {pair!r}",
                reason_code=INVALID_CONFIG,
            )
        if score is not None and not isinstance(score, Decimal):
            raise PortfolioResearchError(
                f"score_by_pair value must be a Decimal or None, got {score!r}",
                reason_code=INVALID_CONFIG,
            )

    valid_score_sum = Decimal("0")
    for pair in selected_pairs:
        if pair not in score_by_pair or score_by_pair[pair] is None:
            exclusions.append((pair, MISSING_SCORE))
            continue
        score = score_by_pair[pair]
        if score <= Decimal("0"):
            exclusions.append((pair, INVALID_SCORE))
            continue
        valid_score_sum += score

    if valid_score_sum <= Decimal("0"):
        reason_codes.append(MISSING_SCORE)
        return False, reason_codes, exclusions

    return True, reason_codes, exclusions


def check_blacklist_exclusion(
    pair: str,
    blacklist: tuple[str, ...],
) -> bool:
    """Return True if ``pair`` is blacklisted."""
    return pair in blacklist
