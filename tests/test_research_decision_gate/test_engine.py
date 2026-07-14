"""Tests for the research decision gate engine."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import MappingProxyType, SimpleNamespace
from typing import Any

import pytest

from hunter.controlled_universe.models import (
    ControlledUniverseConfig,
    ControlledUniverseDataQuality,
    ControlledUniverseItem,
    ControlledUniverseReport,
    ControlledUniverseSafetyFlags,
    ControlledUniverseState,
)
from hunter.portfolio_risk_evaluator.models import (
    PortfolioRiskConfig,
    PortfolioRiskMetrics,
    ValidatedPortfolioRiskContext,
)
from hunter.research_decision_gate import (
    GO,
    MISSING_RISK_CONTEXT,
    MISSING_STRATEGY_CONTRACT,
    MISSING_UNIVERSE_REPORT,
    NEEDS_REVIEW,
    NO_GO,
    OPTIONAL_STRATEGY_CONTRACT_MISSING,
    REJECTED_RISK_CONTEXT,
    REJECTED_UNIVERSE_REPORT,
    RISK_GATE_CLOSED,
    STALE_RISK_CONTEXT,
    STALE_UNIVERSE_REPORT,
    UNSAFE_STRATEGY_CONTRACT,
    UPSTREAM_REVIEW_REQUIRED,
    ResearchDecisionGateConfig,
    ResearchDecisionGateReport,
    build_research_decision_gate_report,
)


def _make_dt(offset: int = 0) -> datetime:
    return datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc) + timedelta(seconds=offset)


def _make_risk_context(
    *,
    accepted: bool = True,
    risk_gate_open: bool = True,
    mode: str = "LONG",
    validated_allocations: tuple[Any, ...] = (),
    evaluated_at: datetime | None = None,
) -> ValidatedPortfolioRiskContext:
    return ValidatedPortfolioRiskContext(
        version="0.58.0-dev",
        source_portfolio_fingerprint="port-fp",
        risk_evaluation_fingerprint="risk-fp",
        evaluated_at=evaluated_at or _make_dt(),
        accepted=accepted,
        risk_gate_open=risk_gate_open,
        mode=mode,
        validated_allocations=validated_allocations,
        metrics=PortfolioRiskMetrics(
            asset_count=0,
            total_exposure=Decimal("0"),
            largest_asset_weight=Decimal("0"),
            largest_cluster_exposure=Decimal("0"),
            hhi=Decimal("0"),
            effective_asset_count=Decimal("0"),
            cluster_exposure=MappingProxyType({}),
        ),
        reason_codes=(),
        research_only=True,
        human_approval_required=True,
        metadata={},
    )


def _make_universe_report(
    *,
    safety_flags_ok: bool = True,
    watchlist: tuple[str, ...] = (),
    blocked: tuple[str, ...] = (),
    generated_at: datetime | None = None,
) -> ControlledUniverseReport:
    universe = ()
    items: list[ControlledUniverseItem] = []
    for pair in universe:
        items.append(
            ControlledUniverseItem(
                pair=pair,
                state=ControlledUniverseState.INCLUDED,
                classification=None,  # type: ignore[arg-type]
            )
        )
    for pair in watchlist:
        items.append(
            ControlledUniverseItem(
                pair=pair,
                state=ControlledUniverseState.WATCHLIST,
                classification=None,  # type: ignore[arg-type]
            )
        )
    for pair in blocked:
        items.append(
            ControlledUniverseItem(
                pair=pair,
                state=ControlledUniverseState.BLOCKED,
                classification=None,  # type: ignore[arg-type]
            )
        )
    return ControlledUniverseReport(
        version="0.51.0-dev",
        generated_at=generated_at or _make_dt(),
        config=ControlledUniverseConfig(),
        execution_state="DRY_RUN",
        allowed_mode="LONG_ONLY",
        universe=universe,
        watchlist=watchlist,
        blocked=blocked,
        items=tuple(items),
        data_quality=ControlledUniverseDataQuality(
            total_inputs=0,
            universe_count=len(universe),
            watchlist_count=len(watchlist),
            blocked_count=len(blocked),
            all_counts_consistent=True,
            safety_flags_ok=safety_flags_ok,
            data_quality_score=100.0,
            execution_context_valid=True,
            portfolio_context_valid=True,
        ),
        safety_flags=ControlledUniverseSafetyFlags(
            has_stale_or_invalid_data=not safety_flags_ok,
        ),
        reason_codes=(),
        metadata={},
    )


def test_build_returns_go_for_clean_inputs() -> None:
    config = ResearchDecisionGateConfig(
        strategy_contract_policy="IGNORE",
    )
    risk = _make_risk_context()
    universe = _make_universe_report()
    result = build_research_decision_gate_report(
        risk, universe, config, evaluated_at=_make_dt()
    )
    assert isinstance(result, ResearchDecisionGateReport)
    assert result.decision == GO
    assert result.research_only is True
    assert result.human_approval_required is True
    assert result.blocking_reason_codes == ()
    assert result.review_reason_codes == ()


def test_build_no_go_when_missing_risk_context() -> None:
    config = ResearchDecisionGateConfig.default()
    universe = _make_universe_report()
    result = build_research_decision_gate_report(
        None, universe, config, evaluated_at=_make_dt()
    )
    assert result.decision == NO_GO
    assert MISSING_RISK_CONTEXT in result.blocking_reason_codes


def test_build_no_go_when_missing_universe_report() -> None:
    config = ResearchDecisionGateConfig.default()
    risk = _make_risk_context()
    result = build_research_decision_gate_report(
        risk, None, config, evaluated_at=_make_dt()
    )
    assert result.decision == NO_GO
    assert MISSING_UNIVERSE_REPORT in result.blocking_reason_codes


def test_build_no_go_when_risk_context_rejected() -> None:
    config = ResearchDecisionGateConfig.default()
    risk = _make_risk_context(accepted=False, risk_gate_open=False, mode="BLOCK_ALL")
    universe = _make_universe_report()
    result = build_research_decision_gate_report(
        risk, universe, config, evaluated_at=_make_dt()
    )
    assert result.decision == NO_GO
    assert REJECTED_RISK_CONTEXT in result.blocking_reason_codes
    assert RISK_GATE_CLOSED in result.blocking_reason_codes


def test_build_no_go_when_universe_unsafe() -> None:
    config = ResearchDecisionGateConfig.default()
    risk = _make_risk_context()
    universe = _make_universe_report(safety_flags_ok=False)
    result = build_research_decision_gate_report(
        risk, universe, config, evaluated_at=_make_dt()
    )
    assert result.decision == NO_GO
    assert REJECTED_UNIVERSE_REPORT in result.blocking_reason_codes


def test_build_no_go_when_stale_inputs() -> None:
    config = ResearchDecisionGateConfig.default()
    old = _make_dt(-config.max_risk_context_age_seconds - 1)
    risk = _make_risk_context(evaluated_at=old)
    universe = _make_universe_report(generated_at=old)
    result = build_research_decision_gate_report(
        risk, universe, config, evaluated_at=_make_dt()
    )
    assert result.decision == NO_GO
    assert STALE_RISK_CONTEXT in result.blocking_reason_codes
    assert STALE_UNIVERSE_REPORT in result.blocking_reason_codes


def test_build_needs_review_with_watchlist() -> None:
    config = ResearchDecisionGateConfig.default()
    risk = _make_risk_context()
    universe = _make_universe_report(watchlist=("BTC/USDT",))
    result = build_research_decision_gate_report(
        risk, universe, config, evaluated_at=_make_dt()
    )
    assert result.decision == NEEDS_REVIEW
    assert UPSTREAM_REVIEW_REQUIRED in result.review_reason_codes


def test_build_no_go_with_unsafe_strategy_contract() -> None:
    config = ResearchDecisionGateConfig.default()
    risk = _make_risk_context()
    universe = _make_universe_report()
    contract = {"research_only": True, "human_approval_required": True, "live_trading_allowed": True}
    result = build_research_decision_gate_report(
        risk, universe, config, strategy_contract_input=contract, evaluated_at=_make_dt()
    )
    assert result.decision == NO_GO
    assert UNSAFE_STRATEGY_CONTRACT in result.blocking_reason_codes


def test_build_needs_review_when_strategy_contract_missing_allow() -> None:
    config = ResearchDecisionGateConfig.default()
    config = ResearchDecisionGateConfig(
        output_dir=config.output_dir,
        strategy_contract_policy="ALLOW_WITH_REVIEW",
    )
    risk = _make_risk_context()
    universe = _make_universe_report()
    result = build_research_decision_gate_report(
        risk, universe, config, evaluated_at=_make_dt()
    )
    assert result.decision == NEEDS_REVIEW
    assert OPTIONAL_STRATEGY_CONTRACT_MISSING in result.review_reason_codes


def test_build_no_go_when_strategy_contract_required_missing() -> None:
    config = ResearchDecisionGateConfig.default()
    config = ResearchDecisionGateConfig(
        output_dir=config.output_dir,
        strategy_contract_policy="REQUIRE",
    )
    risk = _make_risk_context()
    universe = _make_universe_report()
    result = build_research_decision_gate_report(
        risk, universe, config, evaluated_at=_make_dt()
    )
    assert result.decision == NO_GO
    assert MISSING_STRATEGY_CONTRACT in result.blocking_reason_codes


def test_build_fingerprint_is_deterministic() -> None:
    config = ResearchDecisionGateConfig.default()
    risk = _make_risk_context()
    universe = _make_universe_report()
    r1 = build_research_decision_gate_report(
        risk, universe, config, evaluated_at=_make_dt()
    )
    r2 = build_research_decision_gate_report(
        risk, universe, config, evaluated_at=_make_dt()
    )
    assert r1.decision_fingerprint == r2.decision_fingerprint
    assert len(r1.decision_fingerprint) == 64


def test_build_source_summaries_are_populated() -> None:
    config = ResearchDecisionGateConfig.default()
    risk = _make_risk_context()
    universe = _make_universe_report()
    result = build_research_decision_gate_report(
        risk, universe, config, evaluated_at=_make_dt()
    )
    assert result.risk_context_summary.present is True
    assert result.risk_context_summary.accepted is True
    assert result.risk_context_summary.fingerprint == "risk-fp"
    assert result.universe_summary.present is True
    assert result.universe_summary.accepted is True
    assert result.strategy_contract_summary.present is False


def test_build_rejects_naive_evaluated_at() -> None:
    config = ResearchDecisionGateConfig.default()
    risk = _make_risk_context()
    universe = _make_universe_report()
    with pytest.raises(ValueError, match="evaluated_at"):
        build_research_decision_gate_report(
            risk, universe, config, evaluated_at=datetime(2026, 7, 14, 12, 0, 0)
        )


def test_build_rejects_non_datetime_evaluated_at() -> None:
    config = ResearchDecisionGateConfig.default()
    risk = _make_risk_context()
    universe = _make_universe_report()
    with pytest.raises(ValueError, match="evaluated_at"):
        build_research_decision_gate_report(
            risk, universe, config, evaluated_at="now"  # type: ignore[arg-type]
        )


def test_build_no_mutation_of_inputs() -> None:
    config = ResearchDecisionGateConfig.default()
    risk = _make_risk_context()
    universe = _make_universe_report()
    contract: dict[str, Any] = {"research_only": True, "human_approval_required": True}
    build_research_decision_gate_report(
        risk, universe, config, strategy_contract_input=contract, evaluated_at=_make_dt()
    )
    assert contract == {"research_only": True, "human_approval_required": True}
