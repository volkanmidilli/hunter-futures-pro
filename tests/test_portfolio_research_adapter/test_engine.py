"""Tests for portfolio_research_adapter engine (MVP-57 Step 4)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from types import MappingProxyType

import pytest

from hunter.portfolio_research_adapter.models import (
    BLOCK_ALL_CONTEXT,
    CLUSTER_LIMIT_APPLIED,
    EMPTY_PORTFOLIO,
    EMPTY_WHITELIST,
    MISSING_CONTEXT,
    PORTFOLIO_ACCEPTED,
    PortfolioResearchConfig,
    PortfolioResearchContext,
    PortfolioResearchError,
)
from hunter.portfolio_research_adapter.engine import (
    build_portfolio_research_context,
    _compute_portfolio_fingerprint,
)
from hunter.strategy_contract_consumer.models import ValidatedStrategyContext


@pytest.fixture
def now() -> datetime:
    return datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def accepted_context(now: datetime) -> ValidatedStrategyContext:
    return ValidatedStrategyContext(
        accepted=True,
        validated_at=now,
        source_fingerprint="sha256-source",
        source_path="strategy_contract_input.json",
        input_version="0.56.0-dev",
        mode="LONG",
        whitelist=("BTC/USDT", "ETH/USDT", "SOL/USDT"),
        blacklist=(),
        safety_flags={},
        reason_codes=("VALIDATION_ACCEPTED",),
    )


@pytest.fixture
def default_config() -> PortfolioResearchConfig:
    return PortfolioResearchConfig.default()


class TestBuildPortfolioResearchContext:
    def test_accepted_equal_weight(self, accepted_context, default_config, now):
        clusters = {"BTC/USDT": "C1", "ETH/USDT": "C2", "SOL/USDT": "C3"}
        context = build_portfolio_research_context(
            accepted_context, default_config, cluster_by_pair=clusters, generated_at=now
        )
        assert isinstance(context, PortfolioResearchContext)
        assert context.accepted
        assert context.mode == "LONG"
        assert context.allocation_method == "EQUAL_WEIGHT"
        assert len(context.allocations) == 3
        assert context.total_exposure == Decimal("0.60")
        assert context.portfolio_fingerprint
        assert context.source_context_fingerprint == "sha256-source"
        assert PORTFOLIO_ACCEPTED in context.reason_codes
        assert CLUSTER_LIMIT_APPLIED not in context.reason_codes

    def test_missing_context(self, default_config, now):
        context = build_portfolio_research_context(
            None, default_config, generated_at=now
        )
        assert not context.accepted
        assert context.mode == "BLOCK_ALL"
        assert context.allocations == ()
        assert context.total_exposure == Decimal("0")
        assert MISSING_CONTEXT in context.reason_codes

    def test_rejected_context(self, accepted_context, default_config, now):
        rejected = ValidatedStrategyContext(
            accepted=False,
            validated_at=now,
            source_fingerprint="sha256-source",
            source_path="strategy_contract_input.json",
            input_version="0.56.0-dev",
            mode="BLOCK_ALL",
            whitelist=(),
            blacklist=(),
            safety_flags={},
            reason_codes=("MISSING_INPUT",),
        )
        context = build_portfolio_research_context(
            rejected, default_config, generated_at=now
        )
        assert not context.accepted
        assert context.mode == "BLOCK_ALL"
        assert context.allocations == ()

    def test_block_all_context(self, accepted_context, default_config, now):
        blocked = _replace(accepted_context, mode="BLOCK_ALL", whitelist=())
        context = build_portfolio_research_context(
            blocked, default_config, generated_at=now
        )
        assert not context.accepted
        assert BLOCK_ALL_CONTEXT in context.reason_codes

    def test_empty_whitelist(self, accepted_context, default_config, now):
        empty = _replace(accepted_context, whitelist=())
        context = build_portfolio_research_context(
            empty, default_config, generated_at=now
        )
        assert not context.accepted
        assert EMPTY_WHITELIST in context.reason_codes

    def test_score_proportional(self, accepted_context, now):
        config = PortfolioResearchConfig(
            allocation_method="SCORE_PROPORTIONAL",
            max_assets=10,
            max_asset_weight=Decimal("1.00"),
            max_total_exposure=Decimal("1.00"),
            max_cluster_exposure=Decimal("1.00"),
        )
        scores = {
            "BTC/USDT": Decimal("1"),
            "ETH/USDT": Decimal("2"),
            "SOL/USDT": Decimal("3"),
        }
        context = build_portfolio_research_context(
            accepted_context, config, score_by_pair=scores, generated_at=now
        )
        assert context.accepted
        assert context.allocation_method == "SCORE_PROPORTIONAL"
        assert len(context.allocations) == 3
        sol = next(a for a in context.allocations if a.pair == "SOL/USDT")
        btc = next(a for a in context.allocations if a.pair == "BTC/USDT")
        assert sol.weight > btc.weight
        assert context.total_exposure <= Decimal("1.00")
        assert context.total_exposure > Decimal("0.99")

    def test_cluster_limits_applied(self, accepted_context, now):
        config = PortfolioResearchConfig(
            max_assets=10,
            max_asset_weight=Decimal("1.00"),
            max_total_exposure=Decimal("1.00"),
            max_cluster_exposure=Decimal("0.30"),
        )
        clusters = {"BTC/USDT": "C1", "ETH/USDT": "C1", "SOL/USDT": "C2"}
        context = build_portfolio_research_context(
            accepted_context, config, cluster_by_pair=clusters, generated_at=now
        )
        assert context.accepted
        c1_exposure = sum(
            a.weight for a in context.allocations if a.cluster == "C1"
        )
        assert c1_exposure <= Decimal("0.30")
        assert CLUSTER_LIMIT_APPLIED in context.reason_codes

    def test_cluster_exposure_mapping(self, accepted_context, now):
        config = PortfolioResearchConfig(
            max_assets=10,
            max_asset_weight=Decimal("1.00"),
            max_total_exposure=Decimal("1.00"),
            max_cluster_exposure=Decimal("0.40"),
        )
        clusters = {"BTC/USDT": "C1", "ETH/USDT": "C1", "SOL/USDT": "C2"}
        context = build_portfolio_research_context(
            accepted_context, config, cluster_by_pair=clusters, generated_at=now
        )
        assert isinstance(context.cluster_exposure, MappingProxyType)
        assert "C1" in context.cluster_exposure
        assert "C2" in context.cluster_exposure

    def test_contradictory_whitelist_blacklist(self, accepted_context, now):
        config = PortfolioResearchConfig(
            max_assets=10,
            max_asset_weight=Decimal("1.00"),
            max_total_exposure=Decimal("1.00"),
        )
        blocked = _replace(accepted_context, blacklist=("BTC/USDT",))
        context = build_portfolio_research_context(
            blocked, config, generated_at=now
        )
        assert not context.accepted

    def test_empty_after_filters(self, accepted_context, now):
        config = PortfolioResearchConfig(
            max_assets=10,
            max_asset_weight=Decimal("1.00"),
            max_total_exposure=Decimal("1.00"),
            min_asset_weight=Decimal("0.60"),
        )
        context = build_portfolio_research_context(
            accepted_context, config, generated_at=now
        )
        assert not context.accepted
        assert EMPTY_PORTFOLIO in context.reason_codes

    def test_determinism(self, accepted_context, default_config, now):
        clusters = {"BTC/USDT": "C1", "ETH/USDT": "C2", "SOL/USDT": "C3"}
        context1 = build_portfolio_research_context(
            accepted_context, default_config, cluster_by_pair=clusters, generated_at=now
        )
        context2 = build_portfolio_research_context(
            accepted_context, default_config, cluster_by_pair=clusters, generated_at=now
        )
        assert context1.portfolio_fingerprint == context2.portfolio_fingerprint
        assert [a.pair for a in context1.allocations] == [a.pair for a in context2.allocations]
        assert [a.weight for a in context1.allocations] == [a.weight for a in context2.allocations]

    def test_invalid_config(self, accepted_context, now):
        with pytest.raises(PortfolioResearchError):
            build_portfolio_research_context(accepted_context, None, generated_at=now)

    def test_metadata_propagation(self, accepted_context, now):
        config = PortfolioResearchConfig(metadata={"note": "ok"})
        clusters = {"BTC/USDT": "C1", "ETH/USDT": "C2", "SOL/USDT": "C3"}
        context = build_portfolio_research_context(
            accepted_context, config, cluster_by_pair=clusters, generated_at=now
        )
        assert context.metadata["note"] == "ok"

    def test_fingerprint_changes_with_allocations(self, accepted_context, now):
        config1 = PortfolioResearchConfig(
            max_assets=10,
            max_asset_weight=Decimal("1.00"),
            max_total_exposure=Decimal("1.00"),
            max_cluster_exposure=Decimal("1.00"),
        )
        config2 = PortfolioResearchConfig(
            max_assets=10,
            max_asset_weight=Decimal("0.50"),
            max_total_exposure=Decimal("1.00"),
            max_cluster_exposure=Decimal("1.00"),
        )
        context1 = build_portfolio_research_context(
            accepted_context, config1, generated_at=now
        )
        context2 = build_portfolio_research_context(
            accepted_context, config2, generated_at=now
        )
        assert context1.portfolio_fingerprint != context2.portfolio_fingerprint

    def test_mapping_not_mutated(self, accepted_context, now):
        scores = {"BTC/USDT": Decimal("1"), "ETH/USDT": Decimal("2")}
        clusters = {"BTC/USDT": "C1", "ETH/USDT": "C2", "SOL/USDT": "C3"}
        config = PortfolioResearchConfig(
            allocation_method="SCORE_PROPORTIONAL",
            max_assets=10,
            max_asset_weight=Decimal("1.00"),
            max_total_exposure=Decimal("1.00"),
            max_cluster_exposure=Decimal("1.00"),
        )
        build_portfolio_research_context(
            accepted_context,
            config,
            score_by_pair=scores,
            cluster_by_pair=clusters,
            generated_at=now,
        )
        assert "BTC/USDT" in scores
        assert "ETH/USDT" in scores
        assert "BTC/USDT" in clusters


class TestFingerprint:
    def test_fingerprint_determinism(self, accepted_context, now):
        config = PortfolioResearchConfig(
            max_assets=10,
            max_asset_weight=Decimal("1.00"),
            max_total_exposure=Decimal("1.00"),
        )
        context = build_portfolio_research_context(
            accepted_context, config, generated_at=now
        )
        fp1 = context.portfolio_fingerprint
        fp2 = context.portfolio_fingerprint
        assert fp1 == fp2
        assert len(fp1) == 64


def _replace(context: ValidatedStrategyContext, **kwargs) -> ValidatedStrategyContext:
    return ValidatedStrategyContext(
        accepted=kwargs.get("accepted", context.accepted),
        validated_at=context.validated_at,
        source_fingerprint=context.source_fingerprint,
        source_path=context.source_path,
        input_version=context.input_version,
        mode=kwargs.get("mode", context.mode),
        whitelist=kwargs.get("whitelist", context.whitelist),
        blacklist=kwargs.get("blacklist", context.blacklist),
        safety_flags=kwargs.get("safety_flags", context.safety_flags),
        reason_codes=kwargs.get("reason_codes", context.reason_codes),
    )
