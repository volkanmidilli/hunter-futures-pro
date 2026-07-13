"""Controlled Universe Bridge Engine.

MVP-51 — Controlled Universe Bridge Engine.

The engine consumes a macro execution context and a per-coin portfolio
construction report and produces a deterministic, fail-closed controlled
universe report. All functions are pure and operate on in-memory inputs.
No file I/O, network calls, database access, or external resources are used.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from hunter.execution.models import ExecutionContext, ExecutionMode, ExecutionState
from hunter.market_state.models import AllowedMode, OutputStatus
from hunter.portfolio_construction.models import (
    PortfolioConstructionClassification,
    PortfolioConstructionReport,
    PortfolioConstructionScore,
    PortfolioConstructionState,
)

from hunter.controlled_universe.models import (
    CONTROLLED_UNIVERSE_VERSION,
    DUPLICATE_PAIR_DETECTED,
    EXECUTION_BLOCKED,
    EXECUTION_UNKNOWN,
    HUMAN_RESEARCH_ONLY,
    INVALID_PAIR,
    INVALID_PORTFOLIO_SUMMARY,
    LOW_PORTFOLIO_SCORE,
    MACRO_MODE_MISMATCH,
    MACRO_MODE_NONE,
    MAX_UNIVERSE_PAIRS_EXCEEDED,
    MISSING_EXECUTION_CONTEXT,
    MISSING_PORTFOLIO_CONTEXT,
    NO_ACTION_COMMANDS_EMITTED,
    NO_FILE_READ_IN_ENGINE,
    NO_NETWORK_CONNECTION,
    PASSED_UNIVERSE_FILTER,
    PORTFOLIO_STATE_BLOCKED,
    PORTFOLIO_STATE_EXCLUDED,
    PORTFOLIO_STATE_INSUFFICIENT_DATA,
    PORTFOLIO_STATE_WATCHLIST,
    TRANSITION_STATE,
    ControlledUniverseClassification,
    ControlledUniverseConfig,
    ControlledUniverseDataQuality,
    ControlledUniverseItem,
    ControlledUniverseReport,
    ControlledUniverseSafetyFlags,
    ControlledUniverseState,
    _has_unsafe_content,
    _is_valid_pair,
)

if TYPE_CHECKING:
    from collections.abc import Sequence


# ---------------------------------------------------------------------------
# Classification helpers
# ---------------------------------------------------------------------------


def _normalize_pair(pair: str) -> str:
    """Normalize pair string for comparison."""
    return pair.strip().upper()


def _portfolio_state_to_universe_state(
    portfolio_state: PortfolioConstructionState,
) -> ControlledUniverseState:
    """Map a portfolio construction state to a controlled universe state."""
    mapping = {
        PortfolioConstructionState.INCLUDED: ControlledUniverseState.INCLUDED,
        PortfolioConstructionState.CAPPED: ControlledUniverseState.INCLUDED,
        PortfolioConstructionState.WATCHLIST: ControlledUniverseState.WATCHLIST,
        PortfolioConstructionState.EXCLUDED: ControlledUniverseState.EXCLUDED,
        PortfolioConstructionState.INSUFFICIENT_DATA: ControlledUniverseState.INSUFFICIENT_DATA,
        PortfolioConstructionState.BLOCKED: ControlledUniverseState.BLOCKED,
    }
    return mapping[portfolio_state]


def _portfolio_classification_to_universe_classification(
    portfolio_classification: PortfolioConstructionClassification,
) -> ControlledUniverseClassification:
    """Map portfolio construction classification to controlled universe classification."""
    mapping = {
        PortfolioConstructionClassification.CORE_RESEARCH_ALLOCATION: ControlledUniverseClassification.LONG_RESEARCH,
        PortfolioConstructionClassification.SATELLITE_RESEARCH_ALLOCATION: ControlledUniverseClassification.LONG_RESEARCH,
        PortfolioConstructionClassification.WATCHLIST_ALLOCATION: ControlledUniverseClassification.WATCHLIST_RESEARCH,
        PortfolioConstructionClassification.EXCLUDED_BY_CONSTRAINTS: ControlledUniverseClassification.BLOCKED_BY_PORTFOLIO,
        PortfolioConstructionClassification.INSUFFICIENT_DATA: ControlledUniverseClassification.BLOCKED_BY_PORTFOLIO,
        PortfolioConstructionClassification.BLOCKED: ControlledUniverseClassification.BLOCKED_BY_PORTFOLIO,
    }
    return mapping[portfolio_classification]


def _is_blocked_by_direction(
    classification: ControlledUniverseClassification,
    allowed_mode: AllowedMode,
) -> bool:
    """Return True if the research direction conflicts with the allowed mode."""
    if allowed_mode == AllowedMode.NONE:
        return True
    if allowed_mode == AllowedMode.LONG_ONLY:
        return classification == ControlledUniverseClassification.SHORT_RESEARCH
    if allowed_mode == AllowedMode.SHORT_ONLY:
        return classification == ControlledUniverseClassification.LONG_RESEARCH
    return False


def _classify_controlled_universe_item(
    score: PortfolioConstructionScore,
    allowed_mode: AllowedMode,
    config: ControlledUniverseConfig,
) -> tuple[ControlledUniverseState, ControlledUniverseClassification, tuple[str, ...], bool]:
    """Classify a single portfolio score into controlled universe state/class/reasons.

    Returns (state, classification, reason_codes, capped).
    """
    # Start from portfolio state mapping.
    portfolio_state = score.state
    state = _portfolio_state_to_universe_state(portfolio_state)
    classification = _portfolio_classification_to_universe_classification(score.classification)
    capped = portfolio_state == PortfolioConstructionState.CAPPED

    reason_codes: list[str] = []

    # Direction / macro mode mismatch.
    if _is_blocked_by_direction(classification, allowed_mode):
        if allowed_mode == AllowedMode.NONE:
            state = ControlledUniverseState.BLOCKED
            classification = ControlledUniverseClassification.BLOCKED_BY_MACRO
            reason_codes.append(MACRO_MODE_NONE)
        else:
            state = ControlledUniverseState.BLOCKED
            classification = ControlledUniverseClassification.BLOCKED_BY_MACRO
            reason_codes.append(MACRO_MODE_MISMATCH)
        return state, classification, tuple(reason_codes), capped

    # Portfolio-state-specific reason codes.
    if state == ControlledUniverseState.BLOCKED:
        reason_codes.append(PORTFOLIO_STATE_BLOCKED)
    elif state == ControlledUniverseState.EXCLUDED:
        reason_codes.append(PORTFOLIO_STATE_EXCLUDED)
    elif state == ControlledUniverseState.INSUFFICIENT_DATA:
        reason_codes.append(PORTFOLIO_STATE_INSUFFICIENT_DATA)
    elif state == ControlledUniverseState.WATCHLIST:
        reason_codes.append(PORTFOLIO_STATE_WATCHLIST)
    elif state == ControlledUniverseState.INCLUDED:
        # Capped items are still included if include_capped is True; note cap.
        if capped:
            reason_codes.append(PASSED_UNIVERSE_FILTER)
        else:
            reason_codes.append(PASSED_UNIVERSE_FILTER)

    # Minimum score threshold.
    if (
        config.min_portfolio_score is not None
        and score.allocation_score is not None
        and score.allocation_score < config.min_portfolio_score
    ):
        state = ControlledUniverseState.BLOCKED
        reason_codes.append(LOW_PORTFOLIO_SCORE)

    return state, classification, tuple(reason_codes), capped


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


def _validate_inputs(
    portfolio_report: PortfolioConstructionReport | None,
    execution_context: ExecutionContext | None,
    config: ControlledUniverseConfig | None,
) -> ControlledUniverseConfig:
    """Validate input types and return a concrete config."""
    if execution_context is not None and not isinstance(execution_context, ExecutionContext):
        raise TypeError(
            f"execution_context must be an ExecutionContext or None, got {type(execution_context).__name__}"
        )
    if portfolio_report is not None and not isinstance(portfolio_report, PortfolioConstructionReport):
        raise TypeError(
            f"portfolio_report must be a PortfolioConstructionReport or None, got {type(portfolio_report).__name__}"
        )
    if config is not None and not isinstance(config, ControlledUniverseConfig):
        raise TypeError(
            f"config must be a ControlledUniverseConfig or None, got {type(config).__name__}"
        )
    return config or ControlledUniverseConfig()


def _detect_duplicate_pairs(scores: Sequence[PortfolioConstructionScore]) -> bool:
    """Return True if normalized pair identifiers are duplicated."""
    seen: set[str] = set()
    for score in scores:
        normalized = _normalize_pair(score.pair)
        if normalized in seen:
            return True
        seen.add(normalized)
    return False


def _validate_portfolio_summary(report: PortfolioConstructionReport) -> bool:
    """Return True if the portfolio summary counts are consistent with scores."""
    summary = report.universe_summary
    counts = {
        PortfolioConstructionState.INCLUDED: summary.included_count,
        PortfolioConstructionState.CAPPED: summary.capped_count,
        PortfolioConstructionState.WATCHLIST: summary.watchlist_count,
        PortfolioConstructionState.EXCLUDED: summary.excluded_count,
        PortfolioConstructionState.INSUFFICIENT_DATA: summary.insufficient_data_count,
        PortfolioConstructionState.BLOCKED: summary.blocked_count,
    }
    actual_counts: dict[PortfolioConstructionState, int] = {
        state: 0 for state in PortfolioConstructionState
    }
    for score in report.scores:
        actual_counts[score.state] = actual_counts.get(score.state, 0) + 1

    return counts == actual_counts


def _execution_context_blocks_universe(execution_context: ExecutionContext) -> str | None:
    """Return a blocking reason code if execution context should fail closed, else None."""
    if execution_context is None:
        return MISSING_EXECUTION_CONTEXT
    if execution_context.status == OutputStatus.INVALID:
        if execution_context.execution_state == ExecutionState.BLOCKED:
            return EXECUTION_BLOCKED
        if execution_context.execution_state == ExecutionState.UNKNOWN:
            return EXECUTION_UNKNOWN
        # Any other invalid status is treated as blocked by execution.
        return EXECUTION_BLOCKED
    if execution_context.execution_state not in (
        ExecutionState.DRY_RUN_ONLY,
        ExecutionState.ENABLED,
    ):
        if execution_context.execution_state == ExecutionState.BLOCKED:
            return EXECUTION_BLOCKED
        if execution_context.execution_state == ExecutionState.UNKNOWN:
            return EXECUTION_UNKNOWN
        return EXECUTION_BLOCKED
    if execution_context.execution_mode == ExecutionMode.BLOCK_ALL:
        return EXECUTION_BLOCKED
    if execution_context.allowed_mode == AllowedMode.NONE:
        return MACRO_MODE_NONE
    return None


def _data_quality_blocks_universe(
    execution_context: ExecutionContext | None,
    portfolio_report: PortfolioConstructionReport | None,
) -> str | None:
    """Return a blocking reason code if data quality fails closed, else None."""
    if execution_context is None or execution_context.data_quality is None:
        return MISSING_EXECUTION_CONTEXT
    if not execution_context.data_quality.is_valid():
        return TRANSITION_STATE
    if portfolio_report is None or portfolio_report.data_quality is None:
        return MISSING_PORTFOLIO_CONTEXT
    if portfolio_report.safety_flags is None or not portfolio_report.safety_flags.is_safe:
        return INVALID_PORTFOLIO_SUMMARY
    if not portfolio_report.data_quality.all_counts_consistent:
        return INVALID_PORTFOLIO_SUMMARY
    return None


# ---------------------------------------------------------------------------
# Safety / data quality builders
# ---------------------------------------------------------------------------


def build_controlled_universe_safety_flags(
    *,
    blocked_reason: str | None = None,
    has_duplicate_pair: bool = False,
    has_invalid_pair: bool = False,
    portfolio_report: PortfolioConstructionReport | None = None,
) -> ControlledUniverseSafetyFlags:
    """Build controlled universe safety flags from inputs and outcome."""
    has_blocked_execution = blocked_reason in (EXECUTION_BLOCKED, EXECUTION_UNKNOWN, MACRO_MODE_NONE)
    has_missing_execution_context = blocked_reason == MISSING_EXECUTION_CONTEXT
    has_missing_portfolio_context = blocked_reason in (MISSING_PORTFOLIO_CONTEXT,)
    has_invalid_portfolio_summary = blocked_reason == INVALID_PORTFOLIO_SUMMARY
    has_stale_or_invalid_data = blocked_reason == TRANSITION_STATE

    has_unsafe = False
    if portfolio_report is not None:
        for score in portfolio_report.scores:
            if _has_unsafe_content(score.pair):
                has_unsafe = True
                break
            for note in score.notes:
                if _has_unsafe_content(note):
                    has_unsafe = True
                    break
            for tag in score.tags:
                if _has_unsafe_content(tag):
                    has_unsafe = True
                    break

    return ControlledUniverseSafetyFlags(
        has_unsafe_content=has_unsafe,
        has_invalid_pair=has_invalid_pair,
        has_duplicate_pair=has_duplicate_pair,
        has_blocked_execution=has_blocked_execution,
        has_missing_execution_context=has_missing_execution_context,
        has_missing_portfolio_context=has_missing_portfolio_context,
        has_invalid_portfolio_summary=has_invalid_portfolio_summary,
        has_stale_or_invalid_data=has_stale_or_invalid_data,
    )


def build_controlled_universe_data_quality(
    *,
    items: tuple[ControlledUniverseItem, ...],
    execution_context_valid: bool,
    portfolio_context_valid: bool,
    total_inputs: int,
) -> ControlledUniverseDataQuality:
    """Build controlled universe data quality from classified items."""
    universe_count = sum(1 for item in items if item.state == ControlledUniverseState.INCLUDED)
    watchlist_count = sum(1 for item in items if item.state == ControlledUniverseState.WATCHLIST)
    blocked_count = sum(1 for item in items if item.state == ControlledUniverseState.BLOCKED)
    excluded_count = sum(1 for item in items if item.state == ControlledUniverseState.EXCLUDED)
    insufficient_data_count = sum(
        1 for item in items if item.state == ControlledUniverseState.INSUFFICIENT_DATA
    )

    safety_flags_ok = execution_context_valid and portfolio_context_valid
    data_quality_score = 0.0
    if total_inputs > 0 and safety_flags_ok:
        data_quality_score = (universe_count / total_inputs) * 100.0

    all_counts_consistent = (
        universe_count + watchlist_count + blocked_count + excluded_count + insufficient_data_count
    ) == len(items)

    return ControlledUniverseDataQuality(
        total_inputs=total_inputs,
        universe_count=universe_count,
        watchlist_count=watchlist_count,
        blocked_count=blocked_count,
        excluded_count=excluded_count,
        insufficient_data_count=insufficient_data_count,
        execution_context_valid=execution_context_valid,
        portfolio_context_valid=portfolio_context_valid,
        data_quality_score=data_quality_score,
        all_counts_consistent=all_counts_consistent,
        safety_flags_ok=safety_flags_ok,
    )


# ---------------------------------------------------------------------------
# Primary engine
# ---------------------------------------------------------------------------


def build_controlled_universe_report(
    portfolio_report: PortfolioConstructionReport | None,
    execution_context: ExecutionContext | None,
    config: ControlledUniverseConfig | None = None,
) -> ControlledUniverseReport:
    """Build a deterministic, fail-closed controlled universe report."""
    config = _validate_inputs(portfolio_report, execution_context, config)
    generated_at = datetime.now(timezone.utc)

    # 1. Missing execution context.
    if execution_context is None:
        return ControlledUniverseReport.fail_closed(
            reason_code=MISSING_EXECUTION_CONTEXT,
            portfolio_report=portfolio_report,
            execution_context=None,
            config=config,
            generated_at=generated_at,
        )

    # 2. Missing portfolio context.
    if portfolio_report is None:
        return ControlledUniverseReport.fail_closed(
            reason_code=MISSING_PORTFOLIO_CONTEXT,
            portfolio_report=None,
            execution_context=execution_context,
            config=config,
            generated_at=generated_at,
        )

    # 3. Invalid pair detection.
    has_invalid_pair = False
    for score in portfolio_report.scores:
        try:
            _is_valid_pair(score.pair)
        except ValueError:
            has_invalid_pair = True
            break
    if has_invalid_pair:
        safety_flags = build_controlled_universe_safety_flags(
            blocked_reason=INVALID_PAIR,
            has_invalid_pair=True,
            portfolio_report=portfolio_report,
        )
        data_quality = build_controlled_universe_data_quality(
            items=(),
            execution_context_valid=False,
            portfolio_context_valid=False,
            total_inputs=len(portfolio_report.scores),
        )
        return ControlledUniverseReport(
            version=CONTROLLED_UNIVERSE_VERSION,
            generated_at=generated_at,
            config=config,
            execution_state=execution_context.execution_state.value,
            allowed_mode=execution_context.allowed_mode.value,
            universe=(),
            watchlist=(),
            blocked=(),
            items=(),
            data_quality=data_quality,
            safety_flags=safety_flags,
            reason_codes=(INVALID_PAIR, HUMAN_RESEARCH_ONLY, NO_ACTION_COMMANDS_EMITTED, NO_FILE_READ_IN_ENGINE, NO_NETWORK_CONNECTION),
        )

    # 4. Duplicate normalized pair detection.
    if _detect_duplicate_pairs(portfolio_report.scores):
        safety_flags = build_controlled_universe_safety_flags(
            blocked_reason=DUPLICATE_PAIR_DETECTED,
            has_duplicate_pair=True,
            portfolio_report=portfolio_report,
        )
        data_quality = build_controlled_universe_data_quality(
            items=(),
            execution_context_valid=False,
            portfolio_context_valid=False,
            total_inputs=len(portfolio_report.scores),
        )
        return ControlledUniverseReport(
            version=CONTROLLED_UNIVERSE_VERSION,
            generated_at=generated_at,
            config=config,
            execution_state=execution_context.execution_state.value,
            allowed_mode=execution_context.allowed_mode.value,
            universe=(),
            watchlist=(),
            blocked=(),
            items=(),
            data_quality=data_quality,
            safety_flags=safety_flags,
            reason_codes=(DUPLICATE_PAIR_DETECTED, HUMAN_RESEARCH_ONLY, NO_ACTION_COMMANDS_EMITTED, NO_FILE_READ_IN_ENGINE, NO_NETWORK_CONNECTION),
        )

    # 5. Execution state / macro gate.
    blocked_reason = _execution_context_blocks_universe(execution_context)
    if blocked_reason:
        return ControlledUniverseReport.fail_closed(
            reason_code=blocked_reason,
            portfolio_report=portfolio_report,
            execution_context=execution_context,
            config=config,
            generated_at=generated_at,
        )

    # 6. Freshness / data quality validation.
    dq_reason = _data_quality_blocks_universe(execution_context, portfolio_report)
    if dq_reason:
        return ControlledUniverseReport.fail_closed(
            reason_code=dq_reason,
            portfolio_report=portfolio_report,
            execution_context=execution_context,
            config=config,
            generated_at=generated_at,
        )

    # 7. Portfolio summary consistency.
    if not _validate_portfolio_summary(portfolio_report):
        return ControlledUniverseReport.fail_closed(
            reason_code=INVALID_PORTFOLIO_SUMMARY,
            portfolio_report=portfolio_report,
            execution_context=execution_context,
            config=config,
            generated_at=generated_at,
        )

    allowed_mode = execution_context.allowed_mode

    # 8. Classify each portfolio score.
    classified_items: list[ControlledUniverseItem] = []
    for score in portfolio_report.scores:
        state, classification, item_reasons, capped = _classify_controlled_universe_item(
            score, allowed_mode, config
        )
        item = ControlledUniverseItem(
            pair=score.pair,
            state=state,
            classification=classification,
            reason_codes=item_reasons,
            portfolio_score=score.allocation_score,
            portfolio_state=score.state.value,
            capped=capped,
        )
        classified_items.append(item)

    # 9. Apply universe cap deterministically (higher score first, then pair asc).
    universe_items = [
        item for item in classified_items if item.state == ControlledUniverseState.INCLUDED
    ]
    universe_items.sort(key=lambda item: (-(item.portfolio_score or 0.0), item.pair))

    if config.max_universe_pairs is not None:
        kept = universe_items[: config.max_universe_pairs]
        dropped = universe_items[config.max_universe_pairs :]
        for item in dropped:
            idx = classified_items.index(item)
            new_item = ControlledUniverseItem(
                pair=item.pair,
                state=ControlledUniverseState.BLOCKED,
                classification=ControlledUniverseClassification.BLOCKED_BY_PORTFOLIO,
                reason_codes=(MAX_UNIVERSE_PAIRS_EXCEEDED,),
                portfolio_score=item.portfolio_score,
                portfolio_state=item.portfolio_state,
                capped=item.capped,
            )
            classified_items[idx] = new_item
        universe_items = kept

    universe = tuple(item.pair for item in universe_items)
    watchlist_items = [
        item for item in classified_items if item.state == ControlledUniverseState.WATCHLIST
    ]
    watchlist_items.sort(key=lambda item: (-(item.portfolio_score or 0.0), item.pair))
    if config.max_watchlist_pairs is not None:
        watchlist_items = watchlist_items[: config.max_watchlist_pairs]
    watchlist = tuple(item.pair for item in watchlist_items)
    blocked = tuple(
        item.pair
        for item in classified_items
        if item.state in (ControlledUniverseState.BLOCKED, ControlledUniverseState.EXCLUDED, ControlledUniverseState.INSUFFICIENT_DATA)
    )

    # 10. Build safety flags and data quality.
    safety_flags = build_controlled_universe_safety_flags(
        portfolio_report=portfolio_report,
    )
    data_quality = build_controlled_universe_data_quality(
        items=tuple(classified_items),
        execution_context_valid=True,
        portfolio_context_valid=True,
        total_inputs=len(portfolio_report.scores),
    )

    # 11. Aggregate reason codes (distinct, ordered by encounter then sorted).
    distinct_reasons: set[str] = {
        HUMAN_RESEARCH_ONLY,
        NO_ACTION_COMMANDS_EMITTED,
        NO_FILE_READ_IN_ENGINE,
        NO_NETWORK_CONNECTION,
    }
    for item in classified_items:
        for code in item.reason_codes:
            distinct_reasons.add(code)
    reason_codes = tuple(sorted(distinct_reasons))

    return ControlledUniverseReport(
        version=CONTROLLED_UNIVERSE_VERSION,
        generated_at=generated_at,
        config=config,
        execution_state=execution_context.execution_state.value,
        allowed_mode=execution_context.allowed_mode.value,
        universe=universe,
        watchlist=watchlist,
        blocked=blocked,
        items=tuple(classified_items),
        data_quality=data_quality,
        safety_flags=safety_flags,
        reason_codes=reason_codes,
        notes=(
            "Controlled universe is a research-only artifact. Not a trading signal, "
            "not execution approval, not strategy approval, not portfolio approval, "
            "and not universe approval.",
        ),
    )


# Convenience alias matching the public API naming in the spec.
classify_controlled_universe_item = _classify_controlled_universe_item
