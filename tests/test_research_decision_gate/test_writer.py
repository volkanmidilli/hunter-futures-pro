"""Tests for the research decision gate writer."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType
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
from hunter.research_decision_gate import (
    NO_GO,
    ResearchDecisionGateConfig,
    ResearchDecisionGateReport,
    build_research_decision_gate_report,
    research_decision_gate_report_to_dict,
    research_decision_gate_report_to_json_text,
    research_decision_gate_report_to_markdown_text,
    write_research_decision_gate_report,
    atomic_write_json_research_decision_gate_report,
    atomic_write_markdown_research_decision_gate_report,
)


def _make_report(tmp_path: Path, *, decision: str = NO_GO) -> ResearchDecisionGateReport:
    config = ResearchDecisionGateConfig(
        output_dir=tmp_path / "data",
        report_output_dir=tmp_path / "reports",
        strategy_contract_policy="IGNORE",
    )
    risk = ValidatedPortfolioRiskContext(
        version="0.58.0-dev",
        source_portfolio_fingerprint="port-fp",
        risk_evaluation_fingerprint="risk-fp",
        evaluated_at=datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc),
        accepted=False,
        risk_gate_open=False,
        mode="BLOCK_ALL",
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
    universe = ControlledUniverseReport(
        version="0.51.0-dev",
        generated_at=datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc),
        config=ControlledUniverseConfig(),
        execution_state="DRY_RUN",
        allowed_mode="LONG_ONLY",
        universe=(),
        watchlist=(),
        blocked=(),
        items=(),
        data_quality=ControlledUniverseDataQuality(
            total_inputs=0,
            safety_flags_ok=True,
            all_counts_consistent=True,
            data_quality_score=100.0,
            execution_context_valid=True,
            portfolio_context_valid=True,
        ),
        safety_flags=ControlledUniverseSafetyFlags(),
        reason_codes=(),
        metadata={},
    )
    return build_research_decision_gate_report(
        risk, universe, config, evaluated_at=datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)
    )


def test_report_to_dict_contains_required_fields(tmp_path: Path) -> None:
    report = _make_report(tmp_path)
    data = research_decision_gate_report_to_dict(report)
    assert data["version"] == report.version
    assert data["decision"] == report.decision
    assert data["decision_fingerprint"] == report.decision_fingerprint
    assert data["research_only"] is True
    assert data["human_approval_required"] is True
    assert "safety_notice" in data
    assert data["risk_context_summary"]["source_name"] == "risk_context"
    assert data["universe_summary"]["source_name"] == "controlled_universe"
    assert data["strategy_contract_summary"]["source_name"] == "strategy_contract"


def test_report_to_json_text_is_valid_json(tmp_path: Path) -> None:
    report = _make_report(tmp_path)
    text = research_decision_gate_report_to_json_text(report)
    parsed = json.loads(text)
    assert parsed["decision"] == report.decision
    assert parsed["decision_fingerprint"] == report.decision_fingerprint


def test_report_to_markdown_text_contains_sections(tmp_path: Path) -> None:
    report = _make_report(tmp_path)
    text = research_decision_gate_report_to_markdown_text(report)
    assert "# Research Decision Gate Report" in text
    assert "## Safety Notice" in text
    assert "## Source Summaries" in text
    assert "## Blocking Reason Codes" in text
    assert "## Review Reason Codes" in text
    assert "## Safety Flags" in text
    assert report.decision in text
    assert report.decision_fingerprint in text


def test_write_report_creates_files(tmp_path: Path) -> None:
    config = ResearchDecisionGateConfig(
        output_dir=tmp_path / "data",
        report_output_dir=tmp_path / "reports",
        strategy_contract_policy="IGNORE",
    )
    report = _make_report(tmp_path)
    json_path, md_path = write_research_decision_gate_report(report, config)
    assert json_path.exists()
    assert md_path.exists()
    parsed = json.loads(json_path.read_text(encoding="utf-8"))
    assert parsed["decision"] == report.decision


def test_atomic_json_writer(tmp_path: Path) -> None:
    report = _make_report(tmp_path)
    path = tmp_path / "custom.json"
    result = atomic_write_json_research_decision_gate_report(report, path)
    assert result == path
    assert path.exists()


def test_atomic_markdown_writer(tmp_path: Path) -> None:
    report = _make_report(tmp_path)
    path = tmp_path / "custom.md"
    result = atomic_write_markdown_research_decision_gate_report(report, path)
    assert result == path
    assert path.exists()


def test_report_to_dict_no_input_mutation(tmp_path: Path) -> None:
    report = _make_report(tmp_path)
    metadata: dict[str, Any] = {"limits": {"max_total_exposure": "1.0"}}
    report_with_meta = build_research_decision_gate_report(
        report.risk_context_summary,  # type: ignore[arg-type]
        None,
        ResearchDecisionGateConfig(strategy_contract_policy="IGNORE"),
        evaluated_at=report.evaluated_at,
        metadata=metadata,
    )
    original = {"limits": {"max_total_exposure": "1.0"}}
    research_decision_gate_report_to_dict(report_with_meta)
    assert metadata == original
