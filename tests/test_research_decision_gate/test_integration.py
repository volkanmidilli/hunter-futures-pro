"""Integration tests for the Research Decision Gate Engine (MVP-59)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType

import pytest

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
from hunter.research_decision_gate import (
    GO,
    NEEDS_REVIEW,
    NO_GO,
    ResearchDecisionGateConfig,
    ResearchDecisionGateError,
    ResearchDecisionGateReport,
    build_research_decision_gate_report,
    write_research_decision_gate_report,
)


def _dt(offset: int = 0) -> datetime:
    return datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc) + timedelta(seconds=offset)


def _risk_context(
    *,
    accepted: bool = True,
    risk_gate_open: bool = True,
    mode: str = "LONG",
    evaluated_at: datetime | None = None,
) -> ValidatedPortfolioRiskContext:
    return ValidatedPortfolioRiskContext(
        version="0.58.0-dev",
        source_portfolio_fingerprint="port-fp",
        risk_evaluation_fingerprint="risk-fp",
        evaluated_at=evaluated_at or _dt(),
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
        research_only=True,
        human_approval_required=True,
        metadata={},
    )


def _universe_report(
    *,
    safety_flags_ok: bool = True,
    generated_at: datetime | None = None,
) -> ControlledUniverseReport:
    return ControlledUniverseReport(
        version="0.51.0-dev",
        generated_at=generated_at or _dt(),
        config=ControlledUniverseConfig(),
        execution_state="DRY_RUN",
        allowed_mode="LONG_ONLY",
        universe=(),
        watchlist=(),
        blocked=(),
        items=(),
        data_quality=ControlledUniverseDataQuality(
            total_inputs=0,
            safety_flags_ok=safety_flags_ok,
            all_counts_consistent=True,
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


def test_end_to_end_clean_inputs_go(tmp_path: Path) -> None:
    config = ResearchDecisionGateConfig(
        output_dir=tmp_path / "data",
        report_output_dir=tmp_path / "reports",
        strategy_contract_policy="IGNORE",
    )
    risk = _risk_context()
    universe = _universe_report()
    report = build_research_decision_gate_report(
        risk, universe, config, evaluated_at=_dt()
    )
    assert report.decision == GO
    json_path, md_path = write_research_decision_gate_report(report, config)
    assert json_path.exists() and md_path.exists()
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["decision"] == GO
    assert data["research_only"] is True
    assert data["human_approval_required"] is True


def test_end_to_end_missing_inputs_no_go(tmp_path: Path) -> None:
    config = ResearchDecisionGateConfig(
        output_dir=tmp_path / "data",
        report_output_dir=tmp_path / "reports",
        strategy_contract_policy="IGNORE",
    )
    report = build_research_decision_gate_report(
        None, None, config, evaluated_at=_dt()
    )
    assert report.decision == NO_GO
    assert report.risk_context_summary.present is False
    assert report.universe_summary.present is False


def test_end_to_end_stale_inputs_no_go(tmp_path: Path) -> None:
    config = ResearchDecisionGateConfig(
        output_dir=tmp_path / "data",
        report_output_dir=tmp_path / "reports",
        strategy_contract_policy="IGNORE",
    )
    old = _dt(-config.max_risk_context_age_seconds - 1)
    risk = _risk_context(evaluated_at=old)
    universe = _universe_report(generated_at=old)
    report = build_research_decision_gate_report(
        risk, universe, config, evaluated_at=_dt()
    )
    assert report.decision == NO_GO
    assert report.blocking_reason_codes


def test_end_to_end_allow_with_review_missing_contract(tmp_path: Path) -> None:
    config = ResearchDecisionGateConfig(
        output_dir=tmp_path / "data",
        report_output_dir=tmp_path / "reports",
        strategy_contract_policy="ALLOW_WITH_REVIEW",
    )
    risk = _risk_context()
    universe = _universe_report()
    report = build_research_decision_gate_report(
        risk, universe, config, evaluated_at=_dt()
    )
    assert report.decision == NEEDS_REVIEW


def test_end_to_end_required_contract_missing_no_go(tmp_path: Path) -> None:
    config = ResearchDecisionGateConfig(
        output_dir=tmp_path / "data",
        report_output_dir=tmp_path / "reports",
        strategy_contract_policy="REQUIRE",
    )
    risk = _risk_context()
    universe = _universe_report()
    report = build_research_decision_gate_report(
        risk, universe, config, evaluated_at=_dt()
    )
    assert report.decision == NO_GO


def test_end_to_end_fingerprint_determinism(tmp_path: Path) -> None:
    config = ResearchDecisionGateConfig(
        output_dir=tmp_path / "data",
        report_output_dir=tmp_path / "reports",
        strategy_contract_policy="IGNORE",
    )
    risk = _risk_context()
    universe = _universe_report()
    r1 = build_research_decision_gate_report(
        risk, universe, config, evaluated_at=_dt()
    )
    r2 = build_research_decision_gate_report(
        risk, universe, config, evaluated_at=_dt()
    )
    assert r1.decision_fingerprint == r2.decision_fingerprint


def test_end_to_end_report_is_research_only(tmp_path: Path) -> None:
    config = ResearchDecisionGateConfig(
        output_dir=tmp_path / "data",
        report_output_dir=tmp_path / "reports",
        strategy_contract_policy="IGNORE",
    )
    risk = _risk_context()
    universe = _universe_report()
    report = build_research_decision_gate_report(
        risk, universe, config, evaluated_at=_dt()
    )
    assert report.research_only is True
    assert report.human_approval_required is True
    for key, value in report.safety_flags.items():
        assert isinstance(key, str)
        assert isinstance(value, bool)


def test_end_to_end_invalid_config_raises() -> None:
    with pytest.raises(ResearchDecisionGateError):
        build_research_decision_gate_report(
            None, None, object(), evaluated_at=_dt()  # type: ignore[arg-type]
        )
