"""Tests for research decision gate validators."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import MappingProxyType, SimpleNamespace
from typing import Any

import pytest

from hunter.controlled_universe.models import (
    ControlledUniverseConfig,
    ControlledUniverseDataQuality,
    ControlledUniverseReport,
    ControlledUniverseSafetyFlags,
)
from hunter.portfolio_risk_evaluator.models import (
    PortfolioRiskConfig,
    PortfolioRiskMetrics,
    ValidatedPortfolioRiskContext,
)
from hunter.portfolio_research_adapter.models import PortfolioAllocation
from hunter.research_decision_gate.models import (
    IGNORE,
    INVALID_STRATEGY_CONTRACT,
    INVALID_TIMESTAMP,
    MISSING_HUMAN_APPROVAL_FLAG,
    MISSING_REQUIRED_FINGERPRINT,
    MISSING_RISK_CONTEXT,
    MISSING_UNIVERSE_REPORT,
    REQUIRE,
    REJECTED_RISK_CONTEXT,
    REJECTED_UNIVERSE_REPORT,
    RISK_GATE_CLOSED,
    STALE_RISK_CONTEXT,
    STALE_UNIVERSE_REPORT,
    UNSAFE_RESEARCH_FLAG,
    UNSAFE_STRATEGY_CONTRACT,
    ResearchDecisionGateConfig,
)
from hunter.research_decision_gate.validator import (
    validate_evaluated_at,
    validate_required_inputs,
    validate_risk_context,
    validate_strategy_contract_input,
    validate_universe_report,
)


def _make_dt(offset: int = 0) -> datetime:
    return datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc) + timedelta(seconds=offset)


def _make_risk_context(
    *,
    accepted: bool = True,
    risk_gate_open: bool = True,
    mode: str = "LONG",
    evaluated_at: datetime | None = None,
    source_portfolio_fingerprint: str = "port-fp",
    risk_evaluation_fingerprint: str = "risk-fp",
    research_only: bool = True,
    human_approval_required: bool = True,
) -> ValidatedPortfolioRiskContext:
    return ValidatedPortfolioRiskContext(
        version="0.58.0-dev",
        source_portfolio_fingerprint=source_portfolio_fingerprint,
        risk_evaluation_fingerprint=risk_evaluation_fingerprint,
        evaluated_at=evaluated_at or _make_dt(),
        accepted=accepted,
        risk_gate_open=risk_gate_open,
        mode=mode,
        validated_allocations=(),
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
        research_only=research_only,
        human_approval_required=human_approval_required,
    )


def _make_fake_risk_context(**kwargs: Any) -> Any:
    defaults = {
        "accepted": True,
        "risk_gate_open": True,
        "mode": "LONG",
        "research_only": True,
        "human_approval_required": True,
        "source_portfolio_fingerprint": "port-fp",
        "risk_evaluation_fingerprint": "risk-fp",
        "evaluated_at": _make_dt(),
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _make_universe_report(
    *,
    generated_at: datetime | None = None,
    safety_flags_ok: bool = True,
) -> ControlledUniverseReport:
    safety_flags = ControlledUniverseSafetyFlags()
    if not safety_flags_ok:
        safety_flags = ControlledUniverseSafetyFlags(has_invalid_pair=True)
    return ControlledUniverseReport(
        version="0.51.0-dev",
        generated_at=generated_at or _make_dt(),
        config=ControlledUniverseConfig(),
        execution_state=None,
        allowed_mode=None,
        universe=(),
        watchlist=(),
        blocked=(),
        items=(),
        data_quality=ControlledUniverseDataQuality(safety_flags_ok=safety_flags_ok),
        safety_flags=safety_flags,
        reason_codes=(),
    )


def test_validate_evaluated_at_accepts_valid() -> None:
    config = ResearchDecisionGateConfig.default()
    assert validate_evaluated_at(_make_dt(), config) == ()


def test_validate_evaluated_at_rejects_naive() -> None:
    config = ResearchDecisionGateConfig.default()
    assert validate_evaluated_at(datetime(2026, 7, 14, 12, 0, 0), config) == (INVALID_TIMESTAMP,)


def test_validate_evaluated_at_rejects_far_future() -> None:
    config = ResearchDecisionGateConfig(allowed_future_skew_seconds=0)
    far_future = datetime.now(timezone.utc) + timedelta(seconds=5)
    assert validate_evaluated_at(far_future, config) == (INVALID_TIMESTAMP,)


def test_validate_risk_context_missing() -> None:
    config = ResearchDecisionGateConfig.default()
    assert validate_risk_context(None, config, _make_dt()) == (MISSING_RISK_CONTEXT,)


def test_validate_risk_context_accepted() -> None:
    config = ResearchDecisionGateConfig.default()
    ctx = _make_risk_context()
    assert validate_risk_context(ctx, config, _make_dt()) == ()


def test_validate_risk_context_rejected() -> None:
    config = ResearchDecisionGateConfig.default()
    ctx = _make_risk_context(accepted=False, risk_gate_open=False, mode="BLOCK_ALL")
    reasons = validate_risk_context(ctx, config, _make_dt())
    assert REJECTED_RISK_CONTEXT in reasons
    assert RISK_GATE_CLOSED in reasons


def test_validate_risk_context_unsafe_flags() -> None:
    config = ResearchDecisionGateConfig.default()
    ctx = _make_fake_risk_context(research_only=False, human_approval_required=False)
    reasons = validate_risk_context(ctx, config, _make_dt())
    assert UNSAFE_RESEARCH_FLAG in reasons
    assert MISSING_HUMAN_APPROVAL_FLAG in reasons


def test_validate_risk_context_missing_fingerprint() -> None:
    config = ResearchDecisionGateConfig.default()
    ctx = _make_fake_risk_context(
        source_portfolio_fingerprint="",
        risk_evaluation_fingerprint="",
    )
    assert validate_risk_context(ctx, config, _make_dt()) == (MISSING_REQUIRED_FINGERPRINT,)


def test_validate_risk_context_stale() -> None:
    config = ResearchDecisionGateConfig(max_risk_context_age_seconds=60)
    old = _make_dt(-120)
    ctx = _make_risk_context(evaluated_at=old)
    assert validate_risk_context(ctx, config, _make_dt()) == (STALE_RISK_CONTEXT,)


def test_validate_universe_report_missing() -> None:
    config = ResearchDecisionGateConfig.default()
    assert validate_universe_report(None, config, _make_dt()) == (MISSING_UNIVERSE_REPORT,)


def test_validate_universe_report_accepted() -> None:
    config = ResearchDecisionGateConfig.default()
    report = _make_universe_report()
    assert validate_universe_report(report, config, _make_dt()) == ()


def test_validate_universe_report_rejected() -> None:
    config = ResearchDecisionGateConfig.default()
    report = _make_universe_report(safety_flags_ok=False)
    assert validate_universe_report(report, config, _make_dt()) == (REJECTED_UNIVERSE_REPORT,)


def test_validate_universe_report_stale() -> None:
    config = ResearchDecisionGateConfig(max_universe_age_seconds=60)
    report = _make_universe_report(generated_at=_make_dt(-120))
    assert validate_universe_report(report, config, _make_dt()) == (STALE_UNIVERSE_REPORT,)


def test_validate_strategy_contract_ignore() -> None:
    config = ResearchDecisionGateConfig(strategy_contract_policy=IGNORE)
    assert validate_strategy_contract_input(None, config) == ()
    assert validate_strategy_contract_input({"research_only": False}, config) == ()


def test_validate_strategy_contract_missing() -> None:
    config = ResearchDecisionGateConfig()
    assert validate_strategy_contract_input(None, config) == ()


def test_validate_strategy_contract_invalid_type() -> None:
    config = ResearchDecisionGateConfig()
    assert validate_strategy_contract_input("not-a-mapping", config) == (INVALID_STRATEGY_CONTRACT,)


def test_validate_strategy_contract_unsafe() -> None:
    config = ResearchDecisionGateConfig()
    assert validate_strategy_contract_input(
        {"research_only": True, "human_approval_required": True, "live_trading_allowed": True},
        config,
    ) == (UNSAFE_STRATEGY_CONTRACT,)


def test_validate_strategy_contract_accepted() -> None:
    config = ResearchDecisionGateConfig()
    assert validate_strategy_contract_input(
        {"research_only": True, "human_approval_required": True},
        config,
    ) == ()


def test_validate_required_inputs_collects_reasons() -> None:
    config = ResearchDecisionGateConfig.default()
    reasons = validate_required_inputs(None, None, config, _make_dt())
    assert MISSING_RISK_CONTEXT in reasons
    assert MISSING_UNIVERSE_REPORT in reasons
