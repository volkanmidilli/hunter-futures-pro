"""Tests for the controlled_universe engine module."""

from datetime import datetime, timezone

import pytest

from hunter.controlled_universe import (
    DUPLICATE_PAIR_DETECTED,
    EXECUTION_BLOCKED,
    EXECUTION_UNKNOWN,
    HUMAN_RESEARCH_ONLY,
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
    AllowedMode,
    ControlledUniverseConfig,
    ControlledUniverseState,
    build_controlled_universe_report,
)
from hunter.decision.models import DecisionAction, DecisionState
from hunter.execution.models import (
    DataQuality,
    ExecutionContext,
    ExecutionMode,
    ExecutionSafetyFlags,
    ExecutionState,
    OutputStatus,
)
from hunter.market_state.models import AllowedMode as MarketAllowedMode
from hunter.portfolio_construction.models import (
    PortfolioConstructionClassification,
    PortfolioConstructionConfig,
    PortfolioConstructionDataQuality,
    PortfolioConstructionReport,
    PortfolioConstructionSafetyFlags,
    PortfolioConstructionScore,
    PortfolioConstructionState,
    PortfolioConstructionUniverseSummary,
)


def _dt() -> datetime:
    return datetime.now(timezone.utc)


def _minimal_safety_flags() -> PortfolioConstructionSafetyFlags:
    return PortfolioConstructionSafetyFlags()


def _minimal_data_quality(
    total_inputs: int = 0,
    included_count: int = 0,
    capped_count: int = 0,
    watchlist_count: int = 0,
    excluded_count: int = 0,
    insufficient_data_count: int = 0,
    blocked_count: int = 0,
) -> PortfolioConstructionDataQuality:
    return PortfolioConstructionDataQuality(
        total_inputs=total_inputs,
        included_count=included_count,
        capped_count=capped_count,
        watchlist_count=watchlist_count,
        excluded_count=excluded_count,
        insufficient_data_count=insufficient_data_count,
        blocked_count=blocked_count,
        ready_context_count=0,
        missing_context_count=0,
        blocked_context_count=0,
        total_final_weight_pct=0.0,
        total_research_weight_pct=100.0,
        data_quality_score=0.0,
        sections_present=0,
        all_sections_present=True,
        all_counts_consistent=True,
        total_weight_within_tolerance=True,
        has_unsafe_content=False,
        safety_flags_ok=True,
    )


def _score(
    pair: str,
    state: PortfolioConstructionState = PortfolioConstructionState.INCLUDED,
    classification: PortfolioConstructionClassification = PortfolioConstructionClassification.CORE_RESEARCH_ALLOCATION,
    allocation_score: float = 80.0,
) -> PortfolioConstructionScore:
    return PortfolioConstructionScore(
        pair=pair,
        state=state,
        classification=classification,
        allocation_score=allocation_score,
        discovery_score_component=0.0,
        data_quality_score=0.0,
        diversification_component=0.0,
        cap_readiness_score=0.0,
        filter_bonus_score=0.0,
        initial_research_weight_pct=0.0,
        capped_weight_pct=0.0,
        final_weight_pct=0.0,
        reason_codes=(),
        tags=(),
        metadata={},
        notes=(),
        rank=None,
    )


def _universe_summary(
    total_candidates: int,
    included_count: int = 0,
    capped_count: int = 0,
    watchlist_count: int = 0,
    excluded_count: int = 0,
    insufficient_data_count: int = 0,
    blocked_count: int = 0,
) -> PortfolioConstructionUniverseSummary:
    return PortfolioConstructionUniverseSummary(
        total_candidates=total_candidates,
        included_count=included_count,
        capped_count=capped_count,
        watchlist_count=watchlist_count,
        excluded_count=excluded_count,
        insufficient_data_count=insufficient_data_count,
        blocked_count=blocked_count,
        core_allocation_count=0,
        satellite_allocation_count=0,
        watchlist_allocation_count=0,
        total_final_weight_pct=0.0,
        top_pair=None,
        notes=(),
    )


def _portfolio_report(*scores: PortfolioConstructionScore) -> PortfolioConstructionReport:
    counts = {
        PortfolioConstructionState.INCLUDED: 0,
        PortfolioConstructionState.CAPPED: 0,
        PortfolioConstructionState.WATCHLIST: 0,
        PortfolioConstructionState.EXCLUDED: 0,
        PortfolioConstructionState.INSUFFICIENT_DATA: 0,
        PortfolioConstructionState.BLOCKED: 0,
    }
    for score in scores:
        counts[score.state] += 1
    total = len(scores)
    return PortfolioConstructionReport(
        version="0.27.0-dev",
        report_id="portfolio-report-1",
        generated_at=_dt(),
        inputs=(),
        config=PortfolioConstructionConfig(),
        safety_flags=_minimal_safety_flags(),
        scores=scores,
        universe_summary=_universe_summary(
            total_candidates=total,
            included_count=counts[PortfolioConstructionState.INCLUDED],
            capped_count=counts[PortfolioConstructionState.CAPPED],
            watchlist_count=counts[PortfolioConstructionState.WATCHLIST],
            excluded_count=counts[PortfolioConstructionState.EXCLUDED],
            insufficient_data_count=counts[PortfolioConstructionState.INSUFFICIENT_DATA],
            blocked_count=counts[PortfolioConstructionState.BLOCKED],
        ),
        data_quality=_minimal_data_quality(
            total_inputs=total,
            included_count=counts[PortfolioConstructionState.INCLUDED],
            capped_count=counts[PortfolioConstructionState.CAPPED],
            watchlist_count=counts[PortfolioConstructionState.WATCHLIST],
            excluded_count=counts[PortfolioConstructionState.EXCLUDED],
            insufficient_data_count=counts[PortfolioConstructionState.INSUFFICIENT_DATA],
            blocked_count=counts[PortfolioConstructionState.BLOCKED],
        ),
        reason_codes=(),
        metadata={},
        notes=(),
    )


def _execution_context(
    execution_state: ExecutionState = ExecutionState.DRY_RUN_ONLY,
    execution_mode: ExecutionMode = ExecutionMode.DRY_RUN_ONLY,
    allowed_mode: MarketAllowedMode = MarketAllowedMode.LONG_ONLY,
    status: OutputStatus = OutputStatus.VALID,
    data_quality: DataQuality | None = None,
) -> ExecutionContext:
    return ExecutionContext(
        timestamp=_dt(),
        status=status,
        execution_state=execution_state,
        execution_mode=execution_mode,
        decision_state=DecisionState.ALLOW,
        decision_action=DecisionAction.ENABLE_LONG_ONLY_RESEARCH,
        allowed_mode=allowed_mode,
        dry_run=True,
        live_trading_enabled=False,
        exchange_connection_enabled=False,
        freqtrade_enabled=False,
        reason_codes=[],
        data_quality=data_quality or DataQuality(),
        safety_flags=ExecutionSafetyFlags(),
        version="1.0",
    )


# ---------------------------------------------------------------------------
# Fail-closed gates
# ---------------------------------------------------------------------------


def test_missing_execution_context_returns_empty_universe() -> None:
    report = _portfolio_report(_score("BTC/USDT"))
    result = build_controlled_universe_report(report, None)
    assert result.universe == ()
    assert MISSING_EXECUTION_CONTEXT in result.reason_codes


def test_missing_portfolio_context_returns_empty_universe() -> None:
    ctx = _execution_context()
    result = build_controlled_universe_report(None, ctx)
    assert result.universe == ()
    assert MISSING_PORTFOLIO_CONTEXT in result.reason_codes


def test_execution_blocked_returns_empty_universe() -> None:
    report = _portfolio_report(_score("BTC/USDT"))
    ctx = _execution_context(execution_state=ExecutionState.BLOCKED)
    result = build_controlled_universe_report(report, ctx)
    assert result.universe == ()
    assert EXECUTION_BLOCKED in result.reason_codes


def test_execution_unknown_returns_empty_universe() -> None:
    report = _portfolio_report(_score("BTC/USDT"))
    ctx = _execution_context(execution_state=ExecutionState.UNKNOWN)
    result = build_controlled_universe_report(report, ctx)
    assert result.universe == ()
    assert EXECUTION_UNKNOWN in result.reason_codes


def test_execution_mode_block_all_returns_empty_universe() -> None:
    report = _portfolio_report(_score("BTC/USDT"))
    ctx = _execution_context(execution_mode=ExecutionMode.BLOCK_ALL)
    result = build_controlled_universe_report(report, ctx)
    assert result.universe == ()
    assert EXECUTION_BLOCKED in result.reason_codes


def test_allowed_mode_none_returns_empty_universe() -> None:
    report = _portfolio_report(_score("BTC/USDT"))
    ctx = _execution_context(allowed_mode=MarketAllowedMode.NONE)
    result = build_controlled_universe_report(report, ctx)
    assert result.universe == ()
    assert MACRO_MODE_NONE in result.reason_codes


def test_invalid_data_quality_returns_empty_universe() -> None:
    report = _portfolio_report(_score("BTC/USDT"))
    ctx = _execution_context(data_quality=DataQuality(missing=True))
    result = build_controlled_universe_report(report, ctx)
    assert result.universe == ()
    assert TRANSITION_STATE in result.reason_codes


def test_invalid_portfolio_summary_returns_empty_universe() -> None:
    score = _score("BTC/USDT", state=PortfolioConstructionState.INCLUDED)
    report = _portfolio_report(score)
    # Create a summary that is internally consistent but mismatches the actual score states.
    bad_summary = _universe_summary(
        total_candidates=1,
        included_count=0,
        capped_count=0,
        watchlist_count=0,
        excluded_count=1,
        insufficient_data_count=0,
        blocked_count=0,
    )
    report = PortfolioConstructionReport(
        version=report.version,
        report_id=report.report_id,
        generated_at=report.generated_at,
        inputs=report.inputs,
        config=report.config,
        safety_flags=report.safety_flags,
        scores=report.scores,
        universe_summary=bad_summary,
        data_quality=report.data_quality,
        reason_codes=report.reason_codes,
        metadata=report.metadata,
        notes=report.notes,
    )
    ctx = _execution_context()
    result = build_controlled_universe_report(report, ctx)
    assert result.universe == ()
    assert INVALID_PORTFOLIO_SUMMARY in result.reason_codes


def test_duplicate_pairs_return_empty_universe() -> None:
    report = _portfolio_report(
        _score("BTC/USDT"),
        _score("  btc/usdt  ", state=PortfolioConstructionState.CAPPED),
    )
    ctx = _execution_context()
    result = build_controlled_universe_report(report, ctx)
    assert result.universe == ()
    assert DUPLICATE_PAIR_DETECTED in result.reason_codes


# ---------------------------------------------------------------------------
# Classification mapping
# ---------------------------------------------------------------------------


def test_included_pair_in_universe() -> None:
    report = _portfolio_report(_score("BTC/USDT"))
    ctx = _execution_context()
    result = build_controlled_universe_report(report, ctx)
    assert result.universe == ("BTC/USDT",)
    assert result.watchlist == ()
    assert result.blocked == ()
    assert PASSED_UNIVERSE_FILTER in result.reason_codes


def test_capped_pair_in_universe_when_include_capped_true() -> None:
    report = _portfolio_report(
        _score("BTC/USDT", state=PortfolioConstructionState.CAPPED)
    )
    ctx = _execution_context()
    result = build_controlled_universe_report(report, ctx)
    assert result.universe == ("BTC/USDT",)
    assert any(item.capped for item in result.items)


def test_excluded_pair_blocked() -> None:
    report = _portfolio_report(
        _score("BTC/USDT", state=PortfolioConstructionState.EXCLUDED)
    )
    ctx = _execution_context()
    result = build_controlled_universe_report(report, ctx)
    assert result.universe == ()
    assert result.blocked == ("BTC/USDT",)
    assert PORTFOLIO_STATE_EXCLUDED in result.reason_codes


def test_blocked_pair_blocked() -> None:
    report = _portfolio_report(
        _score("BTC/USDT", state=PortfolioConstructionState.BLOCKED)
    )
    ctx = _execution_context()
    result = build_controlled_universe_report(report, ctx)
    assert result.universe == ()
    assert PORTFOLIO_STATE_BLOCKED in result.reason_codes


def test_insufficient_data_pair_blocked() -> None:
    report = _portfolio_report(
        _score("BTC/USDT", state=PortfolioConstructionState.INSUFFICIENT_DATA)
    )
    ctx = _execution_context()
    result = build_controlled_universe_report(report, ctx)
    assert result.universe == ()
    assert PORTFOLIO_STATE_INSUFFICIENT_DATA in result.reason_codes


def test_watchlist_pair_in_watchlist() -> None:
    report = _portfolio_report(
        _score("BTC/USDT", state=PortfolioConstructionState.WATCHLIST)
    )
    ctx = _execution_context()
    result = build_controlled_universe_report(report, ctx)
    assert result.universe == ()
    assert result.watchlist == ("BTC/USDT",)
    assert PORTFOLIO_STATE_WATCHLIST in result.reason_codes


def test_all_excluded_with_valid_execution_yields_empty_universe() -> None:
    report = _portfolio_report(
        _score("BTC/USDT", state=PortfolioConstructionState.EXCLUDED),
        _score("ETH/USDT", state=PortfolioConstructionState.EXCLUDED),
    )
    ctx = _execution_context()
    result = build_controlled_universe_report(report, ctx)
    assert result.universe == ()
    assert set(result.blocked) == {"BTC/USDT", "ETH/USDT"}
    assert PORTFOLIO_STATE_EXCLUDED in result.reason_codes


def test_execution_blocked_with_included_pairs_moves_to_blocked() -> None:
    report = _portfolio_report(_score("BTC/USDT"))
    ctx = _execution_context(execution_state=ExecutionState.BLOCKED)
    result = build_controlled_universe_report(report, ctx)
    assert result.universe == ()
    assert EXECUTION_BLOCKED in result.reason_codes


# ---------------------------------------------------------------------------
# Configurable limits
# ---------------------------------------------------------------------------


def test_max_universe_pairs_caps_universe() -> None:
    report = _portfolio_report(
        _score("AAA/USDT", allocation_score=50.0),
        _score("BBB/USDT", allocation_score=90.0),
        _score("CCC/USDT", allocation_score=70.0),
    )
    ctx = _execution_context()
    config = ControlledUniverseConfig(max_universe_pairs=2)
    result = build_controlled_universe_report(report, ctx, config=config)
    assert len(result.universe) == 2
    assert result.universe[0] == "BBB/USDT"
    assert MAX_UNIVERSE_PAIRS_EXCEEDED in result.reason_codes


def test_min_portfolio_score_filters_items() -> None:
    report = _portfolio_report(
        _score("BTC/USDT", allocation_score=80.0),
        _score("ETH/USDT", allocation_score=50.0),
    )
    ctx = _execution_context()
    config = ControlledUniverseConfig(min_portfolio_score=60.0)
    result = build_controlled_universe_report(report, ctx, config=config)
    assert result.universe == ("BTC/USDT",)
    assert LOW_PORTFOLIO_SCORE in result.reason_codes


def test_max_watchlist_pairs_caps_watchlist() -> None:
    report = _portfolio_report(
        _score("BTC/USDT", state=PortfolioConstructionState.WATCHLIST),
        _score("ETH/USDT", state=PortfolioConstructionState.WATCHLIST),
        _score("SOL/USDT", state=PortfolioConstructionState.WATCHLIST),
    )
    ctx = _execution_context()
    config = ControlledUniverseConfig(max_watchlist_pairs=2)
    result = build_controlled_universe_report(report, ctx, config=config)
    assert len(result.watchlist) == 2


# ---------------------------------------------------------------------------
# Direction / macro mode
# ---------------------------------------------------------------------------


def test_short_only_blocks_long_research_candidates() -> None:
    report = _portfolio_report(_score("BTC/USDT"))
    ctx = _execution_context(allowed_mode=MarketAllowedMode.SHORT_ONLY)
    result = build_controlled_universe_report(report, ctx)
    assert result.universe == ()
    assert MACRO_MODE_MISMATCH in result.reason_codes


def test_long_only_allows_long_research_candidates() -> None:
    report = _portfolio_report(_score("BTC/USDT"))
    ctx = _execution_context(allowed_mode=MarketAllowedMode.LONG_ONLY)
    result = build_controlled_universe_report(report, ctx)
    assert result.universe == ("BTC/USDT",)
    assert MACRO_MODE_MISMATCH not in result.reason_codes


# ---------------------------------------------------------------------------
# Safety and determinism
# ---------------------------------------------------------------------------


def test_safety_flags_are_safe_for_valid_inputs() -> None:
    report = _portfolio_report(_score("BTC/USDT"))
    ctx = _execution_context()
    result = build_controlled_universe_report(report, ctx)
    assert result.safety_flags.is_safe is True
    assert HUMAN_RESEARCH_ONLY in result.reason_codes
    assert NO_ACTION_COMMANDS_EMITTED in result.reason_codes
    assert NO_FILE_READ_IN_ENGINE in result.reason_codes
    assert NO_NETWORK_CONNECTION in result.reason_codes


def test_report_is_deterministic() -> None:
    report = _portfolio_report(
        _score("BTC/USDT", allocation_score=80.0),
        _score("ETH/USDT", allocation_score=70.0),
    )
    ctx = _execution_context()
    result1 = build_controlled_universe_report(report, ctx)
    result2 = build_controlled_universe_report(report, ctx)
    assert result1.universe == result2.universe
    assert result1.watchlist == result2.watchlist
    assert result1.blocked == result2.blocked
    assert result1.reason_codes == result2.reason_codes
    assert sorted(result1.items, key=lambda i: i.pair) == sorted(result2.items, key=lambda i: i.pair)
