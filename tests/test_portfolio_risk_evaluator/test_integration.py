"""Integration tests for the Portfolio Risk Constraint Evaluator (MVP-58)."""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType

import pytest

from hunter.portfolio_research_adapter.models import (
    PORTFOLIO_RESEARCH_ADAPTER_VERSION,
    PortfolioAllocation,
    PortfolioExclusion,
    PortfolioResearchContext,
)
from hunter.portfolio_risk_evaluator import (
    ASSET_COUNT_BELOW_MINIMUM,
    ASSET_WEIGHT_BELOW_MINIMUM,
    ASSET_WEIGHT_EXCEEDED,
    BLACKLIST_CONFLICT,
    CLUSTER_EXPOSURE_EXCEEDED,
    CLUSTER_EXPOSURE_MISMATCH,
    DUPLICATE_PAIR,
    EMPTY_ALLOCATIONS,
    HHI_EXCEEDED,
    INVALID_ALLOCATION,
    MISSING_CONTEXT,
    PORTFOLIO_RISK_EVALUATOR_VERSION,
    REJECTED_PORTFOLIO_CONTEXT,
    RISK_ACCEPTED,
    TOTAL_EXPOSURE_EXCEEDED,
    TOTAL_EXPOSURE_MISMATCH,
    PortfolioRiskConfig,
    PortfolioRiskError,
    build_portfolio_risk_metrics,
    build_validated_portfolio_risk_context,
    calculate_hhi,
    recalculate_cluster_exposure,
    recalculate_total_exposure,
    validate_portfolio_risk_context,
    write_portfolio_risk_context,
)


def _make_dt() -> datetime:
    return datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)


def _make_context(
    *,
    accepted: bool = True,
    mode: str = "LONG",
    allocations: tuple[PortfolioAllocation, ...] = (),
    total_exposure: Decimal = Decimal("0"),
    cluster_exposure: dict[str, Decimal] | None = None,
    exclusions: tuple[PortfolioExclusion, ...] = (),
) -> PortfolioResearchContext:
    cluster_exposure = cluster_exposure or {}
    effective_mode = "BLOCK_ALL" if not accepted else mode
    return PortfolioResearchContext(
        version=PORTFOLIO_RESEARCH_ADAPTER_VERSION,
        source_context_fingerprint="src-fp",
        portfolio_fingerprint="port-fp",
        generated_at=_make_dt(),
        mode=effective_mode,
        allocation_method="EQUAL_WEIGHT",
        allocations=allocations,
        exclusions=exclusions,
        cluster_exposure=MappingProxyType(cluster_exposure),
        total_exposure=total_exposure,
        accepted=accepted,
        research_only=True,
        human_approval_required=True,
        reason_codes=(),
        metadata={},
    )


def test_public_api_exports() -> None:
    assert PortfolioRiskConfig is not None
    assert build_validated_portfolio_risk_context is not None
    assert validate_portfolio_risk_context is not None
    assert build_portfolio_risk_metrics is not None
    assert write_portfolio_risk_context is not None
    assert PORTFOLIO_RISK_EVALUATOR_VERSION == "0.58.0-dev"


def test_no_freqtrade_imports() -> None:
    import ast
    import inspect
    from hunter.portfolio_risk_evaluator import engine, metrics, validator, writer

    for module in (engine, metrics, validator, writer):
        source = inspect.getsource(module)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "freqtrade" not in alias.name
            elif isinstance(node, ast.ImportFrom):
                assert node.module is None or "freqtrade" not in node.module


def test_accepted_diversified_portfolio() -> None:
    config = PortfolioRiskConfig.default()
    ctx = _make_context(
        allocations=(
            PortfolioAllocation("BTC/USDT", Decimal("0.25"), "DEFI", None, "test"),
            PortfolioAllocation("ETH/USDT", Decimal("0.25"), "DEFI", None, "test"),
            PortfolioAllocation("SOL/USDT", Decimal("0.25"), "L1", None, "test"),
            PortfolioAllocation("ADA/USDT", Decimal("0.25"), "L1", None, "test"),
        ),
        total_exposure=Decimal("1.0"),
        cluster_exposure={"DEFI": Decimal("0.5"), "L1": Decimal("0.5")},
    )
    result = build_validated_portfolio_risk_context(ctx, config, evaluated_at=_make_dt())
    assert result.accepted
    assert result.risk_gate_open
    assert result.mode == "LONG"
    assert RISK_ACCEPTED in result.reason_codes
    assert len(result.validated_allocations) == 4


def test_missing_context() -> None:
    config = PortfolioRiskConfig.default()
    result = build_validated_portfolio_risk_context(None, config, evaluated_at=_make_dt())
    assert not result.accepted
    assert MISSING_CONTEXT in result.reason_codes
    assert result.metrics.total_exposure == Decimal("0")


def test_rejected_context() -> None:
    config = PortfolioRiskConfig.default()
    ctx = _make_context(accepted=False)
    result = build_validated_portfolio_risk_context(ctx, config, evaluated_at=_make_dt())
    assert not result.accepted
    assert REJECTED_PORTFOLIO_CONTEXT in result.reason_codes


def test_block_all_context() -> None:
    config = PortfolioRiskConfig.default()
    ctx = _make_context(mode="BLOCK_ALL")
    result = build_validated_portfolio_risk_context(ctx, config, evaluated_at=_make_dt())
    assert not result.accepted
    assert EMPTY_ALLOCATIONS in result.reason_codes


def test_empty_allocations() -> None:
    config = PortfolioRiskConfig.default()
    ctx = _make_context()
    result = build_validated_portfolio_risk_context(ctx, config, evaluated_at=_make_dt())
    assert not result.accepted
    assert EMPTY_ALLOCATIONS in result.reason_codes


def test_duplicate_pair() -> None:
    config = PortfolioRiskConfig.default()
    ctx = _make_context(
        allocations=(
            PortfolioAllocation("BTC/USDT", Decimal("0.5"), "DEFI", None, "test"),
            PortfolioAllocation("BTC/USDT", Decimal("0.5"), "L1", None, "test"),
        ),
        total_exposure=Decimal("1.0"),
        cluster_exposure={"DEFI": Decimal("0.5"), "L1": Decimal("0.5")},
    )
    result = build_validated_portfolio_risk_context(ctx, config, evaluated_at=_make_dt())
    assert not result.accepted
    assert DUPLICATE_PAIR in result.reason_codes


def test_invalid_pair_format() -> None:
    config = PortfolioRiskConfig.default()
    ctx = _make_context(
        allocations=(PortfolioAllocation("BTCUSDT", Decimal("0.5"), "DEFI", None, "test"),),
        total_exposure=Decimal("0.5"),
        cluster_exposure={"DEFI": Decimal("0.5")},
    )
    result = build_validated_portfolio_risk_context(ctx, config, evaluated_at=_make_dt())
    assert not result.accepted
    assert INVALID_ALLOCATION in result.reason_codes


def test_blacklist_conflict() -> None:
    from hunter.portfolio_research_adapter.models import BLACKLISTED_PAIR

    config = PortfolioRiskConfig.default()
    ctx = _make_context(
        allocations=(PortfolioAllocation("BTC/USDT", Decimal("0.5"), "DEFI", None, "test"),),
        total_exposure=Decimal("0.5"),
        cluster_exposure={"DEFI": Decimal("0.5")},
        exclusions=(PortfolioExclusion("BTC/USDT", BLACKLISTED_PAIR, "blacklisted"),),
    )
    result = build_validated_portfolio_risk_context(ctx, config, evaluated_at=_make_dt())
    assert not result.accepted
    assert BLACKLIST_CONFLICT in result.reason_codes


def test_total_exposure_mismatch() -> None:
    config = PortfolioRiskConfig.default()
    ctx = _make_context(
        allocations=(
            PortfolioAllocation("BTC/USDT", Decimal("0.5"), "DEFI", None, "test"),
            PortfolioAllocation("ETH/USDT", Decimal("0.5"), "DEFI", None, "test"),
        ),
        total_exposure=Decimal("0.9"),
        cluster_exposure={"DEFI": Decimal("1.0")},
    )
    result = build_validated_portfolio_risk_context(ctx, config, evaluated_at=_make_dt())
    assert not result.accepted
    assert TOTAL_EXPOSURE_MISMATCH in result.reason_codes


def test_cluster_exposure_mismatch() -> None:
    config = PortfolioRiskConfig.default()
    ctx = _make_context(
        allocations=(
            PortfolioAllocation("BTC/USDT", Decimal("0.5"), "DEFI", None, "test"),
            PortfolioAllocation("ETH/USDT", Decimal("0.5"), "DEFI", None, "test"),
        ),
        total_exposure=Decimal("1.0"),
        cluster_exposure={"DEFI": Decimal("0.9")},
    )
    result = build_validated_portfolio_risk_context(ctx, config, evaluated_at=_make_dt())
    assert not result.accepted
    assert CLUSTER_EXPOSURE_MISMATCH in result.reason_codes


def test_asset_count_below_minimum() -> None:
    config = PortfolioRiskConfig(min_asset_count=3)
    ctx = _make_context(
        allocations=(
            PortfolioAllocation("BTC/USDT", Decimal("0.5"), "DEFI", None, "test"),
            PortfolioAllocation("ETH/USDT", Decimal("0.5"), "DEFI", None, "test"),
        ),
        total_exposure=Decimal("1.0"),
        cluster_exposure={"DEFI": Decimal("1.0")},
    )
    result = build_validated_portfolio_risk_context(ctx, config, evaluated_at=_make_dt())
    assert not result.accepted
    assert ASSET_COUNT_BELOW_MINIMUM in result.reason_codes


def test_asset_weight_below_minimum() -> None:
    config = PortfolioRiskConfig(min_asset_weight=Decimal("0.30"))
    ctx = _make_context(
        allocations=(
            PortfolioAllocation("BTC/USDT", Decimal("0.5"), "DEFI", None, "test"),
            PortfolioAllocation("ETH/USDT", Decimal("0.2"), "DEFI", None, "test"),
        ),
        total_exposure=Decimal("0.7"),
        cluster_exposure={"DEFI": Decimal("0.7")},
    )
    result = build_validated_portfolio_risk_context(ctx, config, evaluated_at=_make_dt())
    assert not result.accepted
    assert ASSET_WEIGHT_BELOW_MINIMUM in result.reason_codes


def test_asset_weight_exceeded() -> None:
    config = PortfolioRiskConfig(max_single_asset_weight=Decimal("0.30"))
    ctx = _make_context(
        allocations=(
            PortfolioAllocation("BTC/USDT", Decimal("0.5"), "DEFI", None, "test"),
            PortfolioAllocation("ETH/USDT", Decimal("0.5"), "DEFI", None, "test"),
        ),
        total_exposure=Decimal("1.0"),
        cluster_exposure={"DEFI": Decimal("1.0")},
    )
    result = build_validated_portfolio_risk_context(ctx, config, evaluated_at=_make_dt())
    assert not result.accepted
    assert ASSET_WEIGHT_EXCEEDED in result.reason_codes


def test_total_exposure_exceeded() -> None:
    config = PortfolioRiskConfig(max_total_exposure=Decimal("0.80"))
    ctx = _make_context(
        allocations=(
            PortfolioAllocation("BTC/USDT", Decimal("0.5"), "DEFI", None, "test"),
            PortfolioAllocation("ETH/USDT", Decimal("0.5"), "DEFI", None, "test"),
        ),
        total_exposure=Decimal("1.0"),
        cluster_exposure={"DEFI": Decimal("1.0")},
    )
    result = build_validated_portfolio_risk_context(ctx, config, evaluated_at=_make_dt())
    assert not result.accepted
    assert TOTAL_EXPOSURE_EXCEEDED in result.reason_codes


def test_cluster_exposure_exceeded() -> None:
    config = PortfolioRiskConfig(max_cluster_exposure=Decimal("0.40"))
    ctx = _make_context(
        allocations=(
            PortfolioAllocation("BTC/USDT", Decimal("0.3"), "DEFI", None, "test"),
            PortfolioAllocation("ETH/USDT", Decimal("0.3"), "DEFI", None, "test"),
        ),
        total_exposure=Decimal("0.6"),
        cluster_exposure={"DEFI": Decimal("0.6")},
    )
    result = build_validated_portfolio_risk_context(ctx, config, evaluated_at=_make_dt())
    assert not result.accepted
    assert CLUSTER_EXPOSURE_EXCEEDED in result.reason_codes


def test_hhi_exceeded() -> None:
    config = PortfolioRiskConfig(max_hhi=Decimal("0.20"))
    ctx = _make_context(
        allocations=(
            PortfolioAllocation("BTC/USDT", Decimal("0.7"), "DEFI", None, "test"),
            PortfolioAllocation("ETH/USDT", Decimal("0.3"), "DEFI", None, "test"),
        ),
        total_exposure=Decimal("1.0"),
        cluster_exposure={"DEFI": Decimal("1.0")},
    )
    result = build_validated_portfolio_risk_context(ctx, config, evaluated_at=_make_dt())
    assert not result.accepted
    assert HHI_EXCEEDED in result.reason_codes


def test_metrics_recalculate_matches_context() -> None:
    ctx = _make_context(
        allocations=(
            PortfolioAllocation("BTC/USDT", Decimal("0.3"), "DEFI", None, "test"),
            PortfolioAllocation("ETH/USDT", Decimal("0.4"), "DEFI", None, "test"),
            PortfolioAllocation("SOL/USDT", Decimal("0.2"), "L1", None, "test"),
        ),
        total_exposure=Decimal("0.9"),
        cluster_exposure={"DEFI": Decimal("0.7"), "L1": Decimal("0.2")},
    )
    assert recalculate_total_exposure(ctx.allocations) == Decimal("0.9")
    assert recalculate_cluster_exposure(ctx.allocations) == {"DEFI": Decimal("0.7"), "L1": Decimal("0.2")}


def test_hhi_calculation() -> None:
    allocations = (
        PortfolioAllocation("BTC/USDT", Decimal("0.5"), "DEFI", None, "test"),
        PortfolioAllocation("ETH/USDT", Decimal("0.5"), "DEFI", None, "test"),
    )
    assert calculate_hhi(allocations, Decimal("1.0")) == Decimal("0.5")


def test_deterministic_metrics_fingerprint_and_writes() -> None:
    config = PortfolioRiskConfig.default()
    ctx = _make_context(
        allocations=(
            PortfolioAllocation("BTC/USDT", Decimal("0.25"), "DEFI", None, "test"),
            PortfolioAllocation("ETH/USDT", Decimal("0.25"), "DEFI", None, "test"),
            PortfolioAllocation("SOL/USDT", Decimal("0.25"), "L1", None, "test"),
            PortfolioAllocation("ADA/USDT", Decimal("0.25"), "L1", None, "test"),
        ),
        total_exposure=Decimal("1.0"),
        cluster_exposure={"DEFI": Decimal("0.5"), "L1": Decimal("0.5")},
    )
    result1 = build_validated_portfolio_risk_context(ctx, config, evaluated_at=_make_dt())
    result2 = build_validated_portfolio_risk_context(ctx, config, evaluated_at=_make_dt())
    assert result1.risk_evaluation_fingerprint == result2.risk_evaluation_fingerprint
    assert result1.metrics == result2.metrics

    with tempfile.TemporaryDirectory() as tmpdir:
        cfg = PortfolioRiskConfig(
            output_dir=Path(tmpdir) / "data",
            report_output_dir=Path(tmpdir) / "reports",
        )
        json_path1, md_path1 = write_portfolio_risk_context(result1, cfg)
        json_path2, md_path2 = write_portfolio_risk_context(result2, cfg)
        assert json_path1.read_text() == json_path2.read_text()
        assert md_path1.read_text() == md_path2.read_text()
        data = json.loads(json_path1.read_text())
        assert data["accepted"] is True
        assert data["risk_gate_open"] is True


def test_decimal_precision() -> None:
    config = PortfolioRiskConfig.default()
    ctx = _make_context(
        allocations=(
            PortfolioAllocation("BTC/USDT", Decimal("0.250000001"), "DEFI", None, "test"),
            PortfolioAllocation("ETH/USDT", Decimal("0.250000001"), "DEFI", None, "test"),
            PortfolioAllocation("SOL/USDT", Decimal("0.250000001"), "L1", None, "test"),
            PortfolioAllocation("ADA/USDT", Decimal("0.250000001"), "L1", None, "test"),
        ),
        total_exposure=Decimal("1.0"),
        cluster_exposure={"DEFI": Decimal("0.5"), "L1": Decimal("0.5")},
    )
    result = build_validated_portfolio_risk_context(ctx, config, evaluated_at=_make_dt())
    assert result.accepted
    assert result.metrics.total_exposure == Decimal("1.0")


def test_no_mutation_of_inputs() -> None:
    config = PortfolioRiskConfig.default()
    ctx = _make_context(
        allocations=(
            PortfolioAllocation("BTC/USDT", Decimal("0.5"), "DEFI", None, "test"),
            PortfolioAllocation("ETH/USDT", Decimal("0.5"), "DEFI", None, "test"),
        ),
        total_exposure=Decimal("1.0"),
        cluster_exposure={"DEFI": Decimal("1.0")},
    )
    allocations_before = list(ctx.allocations)
    build_validated_portfolio_risk_context(ctx, config, evaluated_at=_make_dt())
    assert list(ctx.allocations) == allocations_before


def test_no_file_reads_in_engine_validator_metrics() -> None:
    import inspect
    from hunter.portfolio_risk_evaluator import engine, metrics, validator

    for module in (engine, metrics, validator):
        source = inspect.getsource(module)
        assert "open(" not in source
        assert "read_text" not in source
        assert "read_bytes" not in source
        assert "Path(" in source or True  # Path construction is allowed


def test_fail_closed_never_produces_accepted() -> None:
    config = PortfolioRiskConfig.default()
    for ctx in (
        None,
        _make_context(accepted=False),
        _make_context(mode="BLOCK_ALL"),
        _make_context(),
    ):
        result = build_validated_portfolio_risk_context(ctx, config, evaluated_at=_make_dt())
        assert not result.accepted
        assert not result.risk_gate_open
        assert result.mode == "BLOCK_ALL"
        assert result.validated_allocations == ()


def test_rejects_naive_datetime() -> None:
    config = PortfolioRiskConfig.default()
    ctx = _make_context(
        allocations=(PortfolioAllocation("BTC/USDT", Decimal("0.5"), "DEFI", None, "test"),),
        total_exposure=Decimal("0.5"),
        cluster_exposure={"DEFI": Decimal("0.5")},
    )
    with pytest.raises(PortfolioRiskError):
        build_validated_portfolio_risk_context(ctx, config, evaluated_at=datetime.utcnow())
