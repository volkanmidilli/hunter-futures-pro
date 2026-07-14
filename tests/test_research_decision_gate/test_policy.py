"""Tests for research decision gate policy functions."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import MappingProxyType, SimpleNamespace

from hunter.controlled_universe.models import (
    ControlledUniverseConfig,
    ControlledUniverseDataQuality,
    ControlledUniverseReport,
    ControlledUniverseSafetyFlags,
)
from hunter.portfolio_risk_evaluator.models import (
    PortfolioRiskMetrics,
    ValidatedPortfolioRiskContext,
)
from hunter.portfolio_research_adapter.models import PortfolioAllocation
from hunter.research_decision_gate.models import (
    ALLOW_WITH_REVIEW,
    CONTRADICTORY_INPUTS,
    DECISION_GO,
    DECISION_NEEDS_REVIEW,
    DECISION_NO_GO,
    IGNORE,
    INCOMPLETE_PROVENANCE,
    MISSING_STRATEGY_CONTRACT,
    OPTIONAL_STRATEGY_CONTRACT_MISSING,
    REQUIRE,
    STRATEGY_CONTRACT_MODE_MISMATCH,
    STRATEGY_CONTRACT_SCOPE_MISMATCH,
    UNKNOWN_NON_BLOCKING_FIELD,
    UPSTREAM_REVIEW_REQUIRED,
    ResearchDecisionGateConfig,
)
from hunter.research_decision_gate.policy import (
    build_canonical_safety_flags,
    classify_reason_codes,
    decision_reason_code,
    detect_contradictions,
    detect_review_conditions,
    evaluate_strategy_contract_policy,
    resolve_decision,
)


def _make_dt(offset: int = 0) -> datetime:
    return datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc) + timedelta(seconds=offset)


def _make_risk_context(**kwargs: object) -> ValidatedPortfolioRiskContext:
    defaults = {
        "version": "0.58.0-dev",
        "source_portfolio_fingerprint": "port-fp",
        "risk_evaluation_fingerprint": "risk-fp",
        "evaluated_at": _make_dt(),
        "accepted": True,
        "risk_gate_open": True,
        "mode": "LONG",
        "validated_allocations": (),
        "metrics": PortfolioRiskMetrics(
            asset_count=0,
            total_exposure=Decimal("0"),
            largest_asset_weight=Decimal("0"),
            largest_cluster_exposure=Decimal("0"),
            hhi=Decimal("0"),
            effective_asset_count=Decimal("0"),
            cluster_exposure=MappingProxyType({}),
        ),
        "reason_codes": (),
        "research_only": True,
        "human_approval_required": True,
    }
    defaults.update(kwargs)
    return ValidatedPortfolioRiskContext(**defaults)  # type: ignore[arg-type]


def _make_universe_report(**kwargs: object) -> ControlledUniverseReport:
    defaults = {
        "version": "0.51.0-dev",
        "generated_at": _make_dt(),
        "config": ControlledUniverseConfig(),
        "execution_state": None,
        "allowed_mode": None,
        "universe": (),
        "watchlist": (),
        "blocked": (),
        "items": (),
        "data_quality": ControlledUniverseDataQuality(),
        "safety_flags": ControlledUniverseSafetyFlags(),
        "reason_codes": (),
    }
    defaults.update(kwargs)
    return ControlledUniverseReport(**defaults)  # type: ignore[arg-type]


def test_canonical_safety_flags() -> None:
    flags = build_canonical_safety_flags()
    assert flags["research_only"] is True
    assert flags["human_approval_required"] is True
    assert flags["automatic_execution_allowed"] is False
    assert flags["runtime_config_mutation_allowed"] is False
    assert flags["live_trading_allowed"] is False


def test_classify_reason_codes() -> None:
    blocking, review = classify_reason_codes(
        ["MISSING_RISK_CONTEXT", "OPTIONAL_STRATEGY_CONTRACT_MISSING", "MISSING_RISK_CONTEXT"]
    )
    assert blocking == ("MISSING_RISK_CONTEXT",)
    assert review == ("OPTIONAL_STRATEGY_CONTRACT_MISSING",)


def test_resolve_decision_priority() -> None:
    assert resolve_decision(["MISSING_RISK_CONTEXT"], ["OPTIONAL_STRATEGY_CONTRACT_MISSING"]) == "NO_GO"
    assert resolve_decision((), ["OPTIONAL_STRATEGY_CONTRACT_MISSING"]) == "NEEDS_REVIEW"
    assert resolve_decision((), ()) == "GO"


def test_decision_reason_code() -> None:
    assert decision_reason_code("GO") == DECISION_GO
    assert decision_reason_code("NO_GO") == DECISION_NO_GO
    assert decision_reason_code("NEEDS_REVIEW") == DECISION_NEEDS_REVIEW


def test_evaluate_strategy_contract_ignore() -> None:
    config = ResearchDecisionGateConfig(strategy_contract_policy=IGNORE)
    blocking, review = evaluate_strategy_contract_policy(None, config)
    assert blocking == ()
    assert review == ()


def test_evaluate_strategy_contract_allow_with_review_missing() -> None:
    config = ResearchDecisionGateConfig(strategy_contract_policy=ALLOW_WITH_REVIEW)
    blocking, review = evaluate_strategy_contract_policy(None, config)
    assert blocking == ()
    assert review == (OPTIONAL_STRATEGY_CONTRACT_MISSING,)


def test_evaluate_strategy_contract_require_missing() -> None:
    config = ResearchDecisionGateConfig(strategy_contract_policy=REQUIRE)
    blocking, review = evaluate_strategy_contract_policy(None, config)
    assert blocking == (MISSING_STRATEGY_CONTRACT,)
    assert review == ()


def test_evaluate_strategy_contract_unsafe() -> None:
    config = ResearchDecisionGateConfig()
    blocking, review = evaluate_strategy_contract_policy(
        {"research_only": True, "human_approval_required": False},
        config,
    )
    assert blocking != ()
    assert review == ()


def test_evaluate_strategy_contract_mode_mismatch() -> None:
    config = ResearchDecisionGateConfig()
    blocking, review = evaluate_strategy_contract_policy(
        {"research_only": True, "human_approval_required": True, "mode": "UNKNOWN"},
        config,
    )
    assert blocking == ()
    assert STRATEGY_CONTRACT_MODE_MISMATCH in review


def test_evaluate_strategy_contract_scope_mismatch() -> None:
    config = ResearchDecisionGateConfig()
    blocking, review = evaluate_strategy_contract_policy(
        {"research_only": True, "human_approval_required": True, "scope": "execution"},
        config,
    )
    assert blocking == ()
    assert STRATEGY_CONTRACT_SCOPE_MISMATCH in review


def test_evaluate_strategy_contract_unknown_field() -> None:
    config = ResearchDecisionGateConfig()
    blocking, review = evaluate_strategy_contract_policy(
        {"research_only": True, "human_approval_required": True, "unknown": 1},
        config,
    )
    assert blocking == ()
    assert UNKNOWN_NON_BLOCKING_FIELD in review


def test_detect_contradictions_mode_mismatch() -> None:
    risk = _make_risk_context(mode="LONG")
    universe = _make_universe_report(allowed_mode="SHORT_ONLY")
    assert detect_contradictions(risk, universe) == (CONTRADICTORY_INPUTS,)


def test_detect_contradictions_blocked_pair() -> None:
    alloc = PortfolioAllocation("BTC/USDT", Decimal("0.5"), "DEFI", None, "test")
    risk = _make_risk_context(validated_allocations=(alloc,))
    universe = SimpleNamespace(blocked=("BTC/USDT",), allowed_mode=None)
    assert detect_contradictions(risk, universe) == (CONTRADICTORY_INPUTS,)


def test_detect_contradictions_none_inputs() -> None:
    assert detect_contradictions(None, None) == ()


def test_detect_review_conditions_upstream_review() -> None:
    risk = _make_risk_context(accepted=False, mode="BLOCK_ALL", risk_gate_open=False)
    review = detect_review_conditions(risk, None, None)
    assert UPSTREAM_REVIEW_REQUIRED in review


def test_detect_review_conditions_watchlist() -> None:
    universe = SimpleNamespace(watchlist=("BTC/USDT",), data_quality=SimpleNamespace(all_counts_consistent=True))
    review = detect_review_conditions(None, universe, None)
    assert UPSTREAM_REVIEW_REQUIRED in review


def test_detect_review_conditions_incomplete_provenance() -> None:
    risk = SimpleNamespace(
        accepted=True,
        mode="LONG",
        source_portfolio_fingerprint="",
        risk_evaluation_fingerprint="",
    )
    review = detect_review_conditions(risk, None, None)
    assert INCOMPLETE_PROVENANCE in review
