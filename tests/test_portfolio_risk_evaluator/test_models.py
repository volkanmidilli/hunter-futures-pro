"""Tests for portfolio risk evaluator models."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType

import pytest

from hunter.portfolio_research_adapter.models import PortfolioAllocation
from hunter.portfolio_risk_evaluator.models import (
    ASSET_COUNT_BELOW_MINIMUM,
    ASSET_WEIGHT_EXCEEDED,
    INVALID_CONFIG,
    PORTFOLIO_RISK_EVALUATOR_VERSION,
    RISK_ACCEPTED,
    PortfolioRiskConfig,
    PortfolioRiskError,
    PortfolioRiskMetrics,
    ValidatedPortfolioRiskContext,
    _quantize,
)


def _make_dt() -> datetime:
    return datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)


def test_version_constant() -> None:
    assert PORTFOLIO_RISK_EVALUATOR_VERSION == "0.58.0-dev"


def test_quantize_rounds_down() -> None:
    assert _quantize(Decimal("0.123456789")) == Decimal("0.12345678")
    assert _quantize(Decimal("1.0")) == Decimal("1.00000000")


def test_config_defaults() -> None:
    config = PortfolioRiskConfig.default()
    assert config.min_asset_count == 2
    assert config.min_asset_weight == Decimal("0.0")
    assert config.max_single_asset_weight == Decimal("0.35")
    assert config.max_total_exposure == Decimal("1.00")
    assert config.max_cluster_exposure == Decimal("0.50")
    assert config.max_hhi == Decimal("0.30")
    assert config.exposure_tolerance == Decimal("0.00000001")
    assert config.output_dir == Path("data/portfolio_risk")
    assert config.report_output_dir == Path("reports/portfolio_risk")
    assert config.json_filename == "latest_risk_validation.json"
    assert config.markdown_filename == "latest_risk_validation.md"
    assert config.metadata == {}


def test_config_accepts_custom_values() -> None:
    config = PortfolioRiskConfig(
        min_asset_count=3,
        min_asset_weight=Decimal("0.01"),
        max_single_asset_weight=Decimal("0.30"),
        max_total_exposure=Decimal("0.95"),
        max_cluster_exposure=Decimal("0.40"),
        max_hhi=Decimal("0.25"),
        exposure_tolerance=Decimal("0.0001"),
        output_dir=Path("custom/data"),
        report_output_dir=Path("custom/reports"),
        json_filename="risk.json",
        markdown_filename="risk.md",
        metadata={"note": "test"},
    )
    assert config.min_asset_count == 3


def test_config_coerces_path_strings() -> None:
    config = PortfolioRiskConfig(output_dir="custom/data", report_output_dir="custom/reports")
    assert isinstance(config.output_dir, Path)
    assert config.output_dir == Path("custom/data")


def test_config_coerces_metadata() -> None:
    config = PortfolioRiskConfig(metadata={"a": {"b": 1}})
    assert isinstance(config.metadata, MappingProxyType)
    assert config.metadata["a"]["b"] == 1


def test_config_rejects_non_decimal_weight_limits() -> None:
    with pytest.raises(ValueError):
        PortfolioRiskConfig(max_single_asset_weight=0.35)  # type: ignore[arg-type]


def test_config_rejects_max_weight_below_min_weight() -> None:
    with pytest.raises(ValueError):
        PortfolioRiskConfig(min_asset_weight=Decimal("0.40"), max_single_asset_weight=Decimal("0.30"))


def test_config_rejects_cluster_exposure_above_total() -> None:
    with pytest.raises(ValueError):
        PortfolioRiskConfig(max_total_exposure=Decimal("0.40"), max_cluster_exposure=Decimal("0.50"))


def test_config_rejects_invalid_min_asset_count() -> None:
    with pytest.raises(ValueError):
        PortfolioRiskConfig(min_asset_count=0)
    with pytest.raises(ValueError):
        PortfolioRiskConfig(min_asset_count="2")  # type: ignore[arg-type]


def test_metrics_defaults_and_validation() -> None:
    metrics = PortfolioRiskMetrics(
        asset_count=2,
        total_exposure=Decimal("0.5"),
        largest_asset_weight=Decimal("0.3"),
        largest_cluster_exposure=Decimal("0.5"),
        hhi=Decimal("0.2"),
        effective_asset_count=Decimal("5.0"),
        cluster_exposure=MappingProxyType({"DEFI": Decimal("0.5")}),
    )
    assert metrics.asset_count == 2


def test_metrics_rejects_negative_values() -> None:
    with pytest.raises(ValueError):
        PortfolioRiskMetrics(
            asset_count=1,
            total_exposure=Decimal("-0.1"),
            largest_asset_weight=Decimal("0.1"),
            largest_cluster_exposure=Decimal("0.1"),
            hhi=Decimal("0.1"),
            effective_asset_count=Decimal("1"),
            cluster_exposure=MappingProxyType({}),
        )


def test_metrics_rejects_hhi_above_one() -> None:
    with pytest.raises(ValueError):
        PortfolioRiskMetrics(
            asset_count=1,
            total_exposure=Decimal("0.1"),
            largest_asset_weight=Decimal("0.1"),
            largest_cluster_exposure=Decimal("0.1"),
            hhi=Decimal("1.1"),
            effective_asset_count=Decimal("1"),
            cluster_exposure=MappingProxyType({}),
        )


def test_validated_context_accepts_accepted() -> None:
    allocation = PortfolioAllocation(
        pair="BTC/USDT",
        weight=Decimal("0.5"),
        cluster="DEFI",
        score=None,
        allocation_reason=RISK_ACCEPTED,
    )
    metrics = PortfolioRiskMetrics(
        asset_count=1,
        total_exposure=Decimal("0.5"),
        largest_asset_weight=Decimal("0.5"),
        largest_cluster_exposure=Decimal("0.5"),
        hhi=Decimal("0.25"),
        effective_asset_count=Decimal("4"),
        cluster_exposure=MappingProxyType({"DEFI": Decimal("0.5")}),
    )
    ctx = ValidatedPortfolioRiskContext(
        version=PORTFOLIO_RISK_EVALUATOR_VERSION,
        source_portfolio_fingerprint="fp1",
        risk_evaluation_fingerprint="fp2",
        evaluated_at=_make_dt(),
        accepted=True,
        risk_gate_open=True,
        mode="LONG",
        validated_allocations=(allocation,),
        metrics=metrics,
        reason_codes=(RISK_ACCEPTED,),
        research_only=True,
        human_approval_required=True,
    )
    assert ctx.accepted
    assert ctx.risk_gate_open
    assert ctx.mode == "LONG"


def test_validated_context_fail_closed_rejects_allocations() -> None:
    allocation = PortfolioAllocation(
        pair="BTC/USDT",
        weight=Decimal("0.5"),
        cluster="DEFI",
        score=None,
        allocation_reason=RISK_ACCEPTED,
    )
    metrics = PortfolioRiskMetrics(
        asset_count=0,
        total_exposure=Decimal("0"),
        largest_asset_weight=Decimal("0"),
        largest_cluster_exposure=Decimal("0"),
        hhi=Decimal("0"),
        effective_asset_count=Decimal("0"),
        cluster_exposure=MappingProxyType({}),
    )
    with pytest.raises(ValueError):
        ValidatedPortfolioRiskContext(
            version=PORTFOLIO_RISK_EVALUATOR_VERSION,
            source_portfolio_fingerprint="fp1",
            risk_evaluation_fingerprint="fp2",
            evaluated_at=_make_dt(),
            accepted=False,
            risk_gate_open=False,
            mode="BLOCK_ALL",
            validated_allocations=(allocation,),
            metrics=metrics,
            reason_codes=(ASSET_COUNT_BELOW_MINIMUM,),
            research_only=True,
            human_approval_required=True,
        )


def test_validated_context_fail_closed_rejects_nonzero_exposure() -> None:
    metrics = PortfolioRiskMetrics(
        asset_count=0,
        total_exposure=Decimal("0.1"),
        largest_asset_weight=Decimal("0"),
        largest_cluster_exposure=Decimal("0"),
        hhi=Decimal("0"),
        effective_asset_count=Decimal("0"),
        cluster_exposure=MappingProxyType({}),
    )
    with pytest.raises(ValueError):
        ValidatedPortfolioRiskContext(
            version=PORTFOLIO_RISK_EVALUATOR_VERSION,
            source_portfolio_fingerprint="fp1",
            risk_evaluation_fingerprint="fp2",
            evaluated_at=_make_dt(),
            accepted=False,
            risk_gate_open=False,
            mode="BLOCK_ALL",
            validated_allocations=(),
            metrics=metrics,
            reason_codes=(ASSET_WEIGHT_EXCEEDED,),
            research_only=True,
            human_approval_required=True,
        )


def test_validated_context_rejects_invalid_mode() -> None:
    metrics = PortfolioRiskMetrics(
        asset_count=0,
        total_exposure=Decimal("0"),
        largest_asset_weight=Decimal("0"),
        largest_cluster_exposure=Decimal("0"),
        hhi=Decimal("0"),
        effective_asset_count=Decimal("0"),
        cluster_exposure=MappingProxyType({}),
    )
    with pytest.raises(ValueError):
        ValidatedPortfolioRiskContext(
            version=PORTFOLIO_RISK_EVALUATOR_VERSION,
            source_portfolio_fingerprint="fp1",
            risk_evaluation_fingerprint="fp2",
            evaluated_at=_make_dt(),
            accepted=False,
            risk_gate_open=False,
            mode="INVALID",  # type: ignore[arg-type]
            validated_allocations=(),
            metrics=metrics,
            reason_codes=(ASSET_COUNT_BELOW_MINIMUM,),
            research_only=True,
            human_approval_required=True,
        )


def test_validated_context_rejects_unsupported_reason_code() -> None:
    metrics = PortfolioRiskMetrics(
        asset_count=0,
        total_exposure=Decimal("0"),
        largest_asset_weight=Decimal("0"),
        largest_cluster_exposure=Decimal("0"),
        hhi=Decimal("0"),
        effective_asset_count=Decimal("0"),
        cluster_exposure=MappingProxyType({}),
    )
    with pytest.raises(ValueError):
        ValidatedPortfolioRiskContext(
            version=PORTFOLIO_RISK_EVALUATOR_VERSION,
            source_portfolio_fingerprint="fp1",
            risk_evaluation_fingerprint="fp2",
            evaluated_at=_make_dt(),
            accepted=False,
            risk_gate_open=False,
            mode="BLOCK_ALL",
            validated_allocations=(),
            metrics=metrics,
            reason_codes=("UNKNOWN_REASON",),
            research_only=True,
            human_approval_required=True,
        )


def test_portfolio_risk_error_carries_reason_code() -> None:
    err = PortfolioRiskError("boom", reason_code=INVALID_CONFIG)
    assert err.reason_code == INVALID_CONFIG
