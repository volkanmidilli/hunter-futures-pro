"""Tests for portfolio_research_adapter allocator (MVP-57 Step 3)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from hunter.portfolio_research_adapter.models import (
    BELOW_MIN_WEIGHT,
    BLACKLISTED_PAIR,
    EMPTY_PORTFOLIO,
    INVALID_PAIR,
    MAX_ASSETS_EXCEEDED,
    MISSING_SCORE,
    PortfolioAllocation,
    PortfolioResearchConfig,
)
from hunter.portfolio_research_adapter.allocator import (
    allocate_equal_weight,
    allocate_score_proportional,
    apply_cluster_limits,
    compute_cluster_exposure,
    compute_total_exposure,
    quantize_allocations,
)


@pytest.fixture
def default_config() -> PortfolioResearchConfig:
    return PortfolioResearchConfig.default()


class TestAllocateEqualWeight:
    def test_basic_equal_weight(self, default_config: PortfolioResearchConfig):
        config = PortfolioResearchConfig(
            max_assets=10,
            max_total_exposure=Decimal("1.00"),
            max_asset_weight=Decimal("0.50"),
        )
        allocations, exclusions = allocate_equal_weight(
            whitelist=("BTC/USDT", "ETH/USDT"),
            blacklist=(),
            config=config,
        )
        assert len(allocations) == 2
        assert allocations[0].weight == Decimal("0.50")
        assert allocations[1].weight == Decimal("0.50")
        assert allocations[0].allocation_reason == "EQUAL_WEIGHT"
        assert allocations[0].score is None
        assert exclusions == []

    def test_blacklist_exclusion(self, default_config: PortfolioResearchConfig):
        config = PortfolioResearchConfig(
            max_assets=10,
            max_total_exposure=Decimal("1.00"),
            max_asset_weight=Decimal("1.00"),
        )
        allocations, exclusions = allocate_equal_weight(
            whitelist=("BTC/USDT", "ETH/USDT"),
            blacklist=("BTC/USDT",),
            config=config,
        )
        assert len(allocations) == 1
        assert allocations[0].pair == "ETH/USDT"
        assert allocations[0].weight == Decimal("1.00")
        assert any(e.reason_code == BLACKLISTED_PAIR for e in exclusions)

    def test_max_assets_cap(self, default_config: PortfolioResearchConfig):
        config = PortfolioResearchConfig(
            max_assets=2,
            max_total_exposure=Decimal("1.00"),
            max_asset_weight=Decimal("0.50"),
        )
        whitelist = ("BTC/USDT", "ETH/USDT", "SOL/USDT", "ADA/USDT")
        allocations, exclusions = allocate_equal_weight(
            whitelist=whitelist,
            blacklist=(),
            config=config,
        )
        assert len(allocations) == 2
        assert all(a.pair in whitelist for a in allocations)
        assert any(e.reason_code == MAX_ASSETS_EXCEEDED for e in exclusions)

    def test_max_asset_weight_cap(self, default_config: PortfolioResearchConfig):
        config = PortfolioResearchConfig(
            max_assets=10,
            max_total_exposure=Decimal("1.00"),
            max_asset_weight=Decimal("0.05"),
        )
        whitelist = ("BTC/USDT", "ETH/USDT", "SOL/USDT")
        allocations, exclusions = allocate_equal_weight(
            whitelist=whitelist,
            blacklist=(),
            config=config,
        )
        # All pairs are capped at 0.05; total exposure is 0.15.
        assert all(a.weight == Decimal("0.05") for a in allocations)
        assert compute_total_exposure(allocations) == Decimal("0.15")
        assert exclusions == []

    def test_min_asset_weight_empty(self, default_config: PortfolioResearchConfig):
        config = PortfolioResearchConfig(
            max_assets=10,
            max_total_exposure=Decimal("1.00"),
            min_asset_weight=Decimal("0.20"),
            max_asset_weight=Decimal("0.20"),
        )
        whitelist = ("BTC/USDT", "ETH/USDT", "SOL/USDT", "ADA/USDT", "XRP/USDT")
        allocations, exclusions = allocate_equal_weight(
            whitelist=whitelist,
            blacklist=(),
            config=config,
        )
        # 5 pairs would give 0.20 each, which equals max and min. Allowed.
        assert len(allocations) == 5
        assert all(a.weight == Decimal("0.20") for a in allocations)

    def test_below_min_asset_weight_excludes_all(self, default_config: PortfolioResearchConfig):
        config = PortfolioResearchConfig(
            max_assets=100,
            max_total_exposure=Decimal("1.00"),
            min_asset_weight=Decimal("0.10"),
            max_asset_weight=Decimal("0.20"),
        )
        whitelist = (
            "BTC/USDT",
            "ETH/USDT",
            "SOL/USDT",
            "ADA/USDT",
            "XRP/USDT",
            "DOT/USDT",
            "LINK/USDT",
            "LTC/USDT",
            "BCH/USDT",
            "UNI/USDT",
            "AVAX/USDT",
        )
        allocations, exclusions = allocate_equal_weight(
            whitelist=whitelist,
            blacklist=(),
            config=config,
        )
        # 11 selected gives 0.0909 < 0.10, so all excluded.
        assert allocations == []
        assert any(e.reason_code == BELOW_MIN_WEIGHT for e in exclusions)

    def test_invalid_pair_excluded(self, default_config: PortfolioResearchConfig):
        allocations, exclusions = allocate_equal_weight(
            whitelist=("BTC/USDT", "invalid"),
            blacklist=(),
            config=default_config,
        )
        assert all(a.pair == "BTC/USDT" for a in allocations)
        assert any(e.reason_code == INVALID_PAIR for e in exclusions)

    def test_empty_whitelist(self, default_config: PortfolioResearchConfig):
        allocations, exclusions = allocate_equal_weight(
            whitelist=(),
            blacklist=(),
            config=default_config,
        )
        assert allocations == []
        assert any(e.reason_code == EMPTY_PORTFOLIO for e in exclusions)

    def test_deterministic_ordering(self, default_config: PortfolioResearchConfig):
        whitelist = ("SOL/USDT", "BTC/USDT", "ETH/USDT")
        allocations1, _ = allocate_equal_weight(
            whitelist=whitelist,
            blacklist=(),
            config=default_config,
        )
        allocations2, _ = allocate_equal_weight(
            whitelist=("ETH/USDT", "BTC/USDT", "SOL/USDT"),
            blacklist=(),
            config=default_config,
        )
        assert [a.pair for a in allocations1] == [a.pair for a in allocations2]
        assert [a.weight for a in allocations1] == [a.weight for a in allocations2]

    def test_cluster_resolution(self, default_config: PortfolioResearchConfig):
        allocations, _ = allocate_equal_weight(
            whitelist=("BTC/USDT", "ETH/USDT"),
            blacklist=(),
            config=default_config,
            cluster_by_pair={"BTC/USDT": " Layer1 ", "ETH/USDT": ""},
        )
        assert allocations[0].cluster == "LAYER1"
        assert allocations[1].cluster == "UNCLASSIFIED"


class TestAllocateScoreProportional:
    def test_basic_score_proportional(self, default_config: PortfolioResearchConfig):
        config = PortfolioResearchConfig(
            max_assets=10,
            max_total_exposure=Decimal("1.00"),
            max_asset_weight=Decimal("1.00"),
        )
        scores = {"BTC/USDT": Decimal("1"), "ETH/USDT": Decimal("2")}
        allocations, exclusions = allocate_score_proportional(
            whitelist=("BTC/USDT", "ETH/USDT"),
            blacklist=(),
            config=config,
            score_by_pair=scores,
        )
        assert len(allocations) == 2
        total = compute_total_exposure(allocations)
        assert total <= Decimal("1.00")
        btc = next(a for a in allocations if a.pair == "BTC/USDT")
        eth = next(a for a in allocations if a.pair == "ETH/USDT")
        assert btc.weight < eth.weight
        assert btc.score == Decimal("1")
        assert eth.score == Decimal("2")

    def test_max_asset_weight_cap_score(self, default_config: PortfolioResearchConfig):
        scores = {"BTC/USDT": Decimal("9"), "ETH/USDT": Decimal("1")}
        config = PortfolioResearchConfig(
            max_assets=10,
            max_total_exposure=Decimal("1.00"),
            max_asset_weight=Decimal("0.20"),
        )
        allocations, exclusions = allocate_score_proportional(
            whitelist=("BTC/USDT", "ETH/USDT"),
            blacklist=(),
            config=config,
            score_by_pair=scores,
        )
        btc = next(a for a in allocations if a.pair == "BTC/USDT")
        assert btc.weight <= Decimal("0.20")
        total = compute_total_exposure(allocations)
        assert total <= Decimal("1.00")

    def test_missing_score_exclusion(self, default_config: PortfolioResearchConfig):
        scores = {"BTC/USDT": Decimal("1")}
        allocations, exclusions = allocate_score_proportional(
            whitelist=("BTC/USDT", "ETH/USDT"),
            blacklist=(),
            config=default_config,
            score_by_pair=scores,
        )
        assert all(a.pair == "BTC/USDT" for a in allocations)
        assert any(e.reason_code == MISSING_SCORE for e in exclusions)

    def test_invalid_score_exclusion(self, default_config: PortfolioResearchConfig):
        scores = {"BTC/USDT": Decimal("1"), "ETH/USDT": Decimal("-1")}
        allocations, exclusions = allocate_score_proportional(
            whitelist=("BTC/USDT", "ETH/USDT"),
            blacklist=(),
            config=default_config,
            score_by_pair=scores,
        )
        assert all(a.pair == "BTC/USDT" for a in allocations)
        assert any(e.reason_code == MISSING_SCORE for e in exclusions)

    def test_all_scores_invalid_empty(self, default_config: PortfolioResearchConfig):
        scores = {"BTC/USDT": Decimal("0"), "ETH/USDT": Decimal("-1")}
        allocations, exclusions = allocate_score_proportional(
            whitelist=("BTC/USDT", "ETH/USDT"),
            blacklist=(),
            config=default_config,
            score_by_pair=scores,
        )
        assert allocations == []
        assert any(e.reason_code == EMPTY_PORTFOLIO for e in exclusions)

    def test_below_min_weight_exclusion(self, default_config: PortfolioResearchConfig):
        scores = {
            "BTC/USDT": Decimal("1"),
            "ETH/USDT": Decimal("1"),
            "SOL/USDT": Decimal("1"),
        }
        config = PortfolioResearchConfig(
            max_assets=10,
            max_total_exposure=Decimal("1.00"),
            min_asset_weight=Decimal("0.40"),
            max_asset_weight=Decimal("0.50"),
        )
        allocations, exclusions = allocate_score_proportional(
            whitelist=("BTC/USDT", "ETH/USDT", "SOL/USDT"),
            blacklist=(),
            config=config,
            score_by_pair=scores,
        )
        assert allocations == []
        assert any(e.reason_code == BELOW_MIN_WEIGHT for e in exclusions)

    def test_deterministic_tie_break(self, default_config: PortfolioResearchConfig):
        scores = {"BTC/USDT": Decimal("1"), "ETH/USDT": Decimal("1"), "SOL/USDT": Decimal("1")}
        config = PortfolioResearchConfig(
            max_assets=2,
            max_total_exposure=Decimal("1.00"),
            max_asset_weight=Decimal("0.50"),
        )
        allocations, _ = allocate_score_proportional(
            whitelist=("BTC/USDT", "ETH/USDT", "SOL/USDT"),
            blacklist=(),
            config=config,
            score_by_pair=scores,
        )
        assert [a.pair for a in allocations] == ["BTC/USDT", "ETH/USDT"]


class TestApplyClusterLimits:
    def test_cluster_limit_scales(self):
        allocations = [
            PortfolioAllocation("BTC/USDT", Decimal("0.30"), "C1", None, "EQUAL_WEIGHT"),
            PortfolioAllocation("ETH/USDT", Decimal("0.30"), "C1", None, "EQUAL_WEIGHT"),
            PortfolioAllocation("SOL/USDT", Decimal("0.20"), "C2", None, "EQUAL_WEIGHT"),
        ]
        scaled = apply_cluster_limits(allocations, Decimal("0.40"))
        c1 = [a for a in scaled if a.cluster == "C1"]
        assert sum(a.weight for a in c1) <= Decimal("0.40")
        assert sum(a.weight for a in scaled) <= Decimal("0.80")

    def test_no_cluster_limit_needed(self):
        allocations = [
            PortfolioAllocation("BTC/USDT", Decimal("0.10"), "C1", None, "EQUAL_WEIGHT"),
            PortfolioAllocation("ETH/USDT", Decimal("0.10"), "C1", None, "EQUAL_WEIGHT"),
        ]
        scaled = apply_cluster_limits(allocations, Decimal("0.40"))
        assert scaled == allocations

    def test_empty_allocations(self):
        assert apply_cluster_limits([], Decimal("0.40")) == []


class TestQuantizeAllocations:
    def test_quantize(self):
        allocations = [
            PortfolioAllocation("BTC/USDT", Decimal("0.3333333333"), "C1", None, "EQUAL_WEIGHT"),
        ]
        quantized = quantize_allocations(allocations)
        assert quantized[0].weight == Decimal("0.33333333")


class TestComputeExposures:
    def test_total_exposure(self):
        allocations = [
            PortfolioAllocation("BTC/USDT", Decimal("0.10"), "C1", None, "EQUAL_WEIGHT"),
            PortfolioAllocation("ETH/USDT", Decimal("0.20"), "C1", None, "EQUAL_WEIGHT"),
        ]
        assert compute_total_exposure(allocations) == Decimal("0.30")

    def test_cluster_exposure(self):
        allocations = [
            PortfolioAllocation("BTC/USDT", Decimal("0.10"), "C1", None, "EQUAL_WEIGHT"),
            PortfolioAllocation("ETH/USDT", Decimal("0.20"), "C2", None, "EQUAL_WEIGHT"),
        ]
        assert compute_cluster_exposure(allocations) == {"C1": Decimal("0.10"), "C2": Decimal("0.20")}
