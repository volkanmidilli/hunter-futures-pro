"""Tests for portfolio risk writer."""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType

import pytest

from hunter.portfolio_research_adapter.models import PortfolioAllocation
from hunter.portfolio_risk_evaluator.engine import build_validated_portfolio_risk_context
from hunter.portfolio_risk_evaluator.models import (
    PORTFOLIO_RISK_EVALUATOR_VERSION,
    RISK_ACCEPTED,
    PortfolioRiskConfig,
    PortfolioRiskMetrics,
    ValidatedPortfolioRiskContext,
)
from hunter.portfolio_research_adapter.models import PortfolioResearchContext
from hunter.portfolio_risk_evaluator.writer import (
    PortfolioRiskWriterError,
    atomic_write_json_portfolio_risk_context,
    atomic_write_markdown_portfolio_risk_context,
    portfolio_risk_context_to_dict,
    portfolio_risk_context_to_json_text,
    portfolio_risk_context_to_markdown_text,
    write_portfolio_risk_context,
)


def _make_dt() -> datetime:
    return datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)


def _make_accepted_context() -> ValidatedPortfolioRiskContext:
    config = PortfolioRiskConfig.default()
    ctx = PortfolioResearchContext(
        version="0.57.0-dev",
        source_context_fingerprint="src-fp",
        portfolio_fingerprint="port-fp",
        generated_at=_make_dt(),
        mode="LONG",
        allocation_method="EQUAL_WEIGHT",
        allocations=(
            PortfolioAllocation("BTC/USDT", Decimal("0.25"), "DEFI", None, "test"),
            PortfolioAllocation("ETH/USDT", Decimal("0.25"), "DEFI", None, "test"),
            PortfolioAllocation("SOL/USDT", Decimal("0.25"), "L1", None, "test"),
            PortfolioAllocation("ADA/USDT", Decimal("0.25"), "L1", None, "test"),
        ),
        exclusions=(),
        cluster_exposure=MappingProxyType({"DEFI": Decimal("0.5"), "L1": Decimal("0.5")}),
        total_exposure=Decimal("1.0"),
        accepted=True,
        research_only=True,
        human_approval_required=True,
        reason_codes=(),
        metadata={},
    )
    return build_validated_portfolio_risk_context(ctx, config, evaluated_at=_make_dt())


def test_context_to_dict_structure() -> None:
    context = _make_accepted_context()
    data = portfolio_risk_context_to_dict(context)
    assert data["version"] == PORTFOLIO_RISK_EVALUATOR_VERSION
    assert data["source_portfolio_fingerprint"] == "port-fp"
    assert data["accepted"] is True
    assert data["risk_gate_open"] is True
    assert data["mode"] == "LONG"
    assert "safety_notice" in data
    assert data["reason_codes"] == [RISK_ACCEPTED]


def test_context_to_json_text_is_deterministic() -> None:
    context = _make_accepted_context()
    text1 = portfolio_risk_context_to_json_text(context)
    text2 = portfolio_risk_context_to_json_text(context)
    assert text1 == text2
    data = json.loads(text1)
    assert data["accepted"] is True


def test_context_to_markdown_text_contains_key_sections() -> None:
    context = _make_accepted_context()
    text = portfolio_risk_context_to_markdown_text(context)
    assert "# Portfolio Risk Validation Context" in text
    assert "## Validated Allocations" in text
    assert "BTC/USDT" in text
    assert "## Configured Limits" in text
    assert "## Safety Notice" in text


def test_atomic_write_json() -> None:
    context = _make_accepted_context()
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "risk.json"
        result = atomic_write_json_portfolio_risk_context(context, path)
        assert result == path
        assert path.exists()
        data = json.loads(path.read_text())
        assert data["accepted"] is True


def test_atomic_write_markdown() -> None:
    context = _make_accepted_context()
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "risk.md"
        result = atomic_write_markdown_portfolio_risk_context(context, path)
        assert result == path
        assert path.exists()
        text = path.read_text()
        assert "# Portfolio Risk Validation Context" in text


def test_write_portfolio_risk_context() -> None:
    context = _make_accepted_context()
    with tempfile.TemporaryDirectory() as tmpdir:
        config = PortfolioRiskConfig(
            output_dir=Path(tmpdir) / "data",
            report_output_dir=Path(tmpdir) / "reports",
        )
        json_path, md_path = write_portfolio_risk_context(context, config)
        assert json_path.exists()
        assert md_path.exists()
        assert json.loads(json_path.read_text())["accepted"] is True
        assert "# Portfolio Risk Validation Context" in md_path.read_text()


def test_atomic_write_cleans_up_temp_on_failure(tmp_path: Path) -> None:
    context = _make_accepted_context()
    path = tmp_path / "readonly" / "risk.json"
    path.parent.mkdir(parents=True)
    path.parent.chmod(0o555)
    try:
        with pytest.raises(PortfolioRiskWriterError):
            atomic_write_json_portfolio_risk_context(context, path)
        assert not (path.parent / "risk.json.tmp").exists()
    finally:
        path.parent.chmod(0o755)
