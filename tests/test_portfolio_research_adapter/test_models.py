"""Tests for portfolio_research_adapter models (MVP-57 Step 1)."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from hunter.portfolio_research_adapter.models import (
    BELOW_MIN_WEIGHT,
    BLACKLISTED_PAIR,
    BLOCK_ALL_CONTEXT,
    CLUSTER_LIMIT_APPLIED,
    CONTRADICTORY_CONTEXT,
    EMPTY_PORTFOLIO,
    EMPTY_WHITELIST,
    INVALID_CONFIG,
    INVALID_PAIR,
    INVALID_SCORE,
    MAX_ASSETS_EXCEEDED,
    MISSING_CONTEXT,
    MISSING_SCORE,
    PORTFOLIO_ACCEPTED,
    PORTFOLIO_RESEARCH_ADAPTER_VERSION,
    PORTFOLIO_RESEARCH_REASON_CODES,
    REJECTED_CONTEXT,
    PortfolioAllocation,
    PortfolioExclusion,
    PortfolioResearchConfig,
    PortfolioResearchContext,
    PortfolioResearchError,
)


def test_version_constant():
    assert PORTFOLIO_RESEARCH_ADAPTER_VERSION == "0.57.0-dev"
    assert isinstance(PORTFOLIO_RESEARCH_REASON_CODES, frozenset)
    assert PORTFOLIO_RESEARCH_REASON_CODES == {
        MISSING_CONTEXT,
        REJECTED_CONTEXT,
        BLOCK_ALL_CONTEXT,
        EMPTY_WHITELIST,
        INVALID_CONFIG,
        INVALID_PAIR,
        BLACKLISTED_PAIR,
        MISSING_SCORE,
        INVALID_SCORE,
        BELOW_MIN_WEIGHT,
        MAX_ASSETS_EXCEEDED,
        CLUSTER_LIMIT_APPLIED,
        EMPTY_PORTFOLIO,
        CONTRADICTORY_CONTEXT,
        PORTFOLIO_ACCEPTED,
    }


class TestPortfolioResearchConfig:
    def test_default_config(self):
        config = PortfolioResearchConfig.default()
        assert config.allocation_method == "EQUAL_WEIGHT"
        assert config.max_assets == 10
        assert config.min_asset_weight == Decimal("0")
        assert config.max_asset_weight == Decimal("0.20")
        assert config.max_total_exposure == Decimal("1.00")
        assert config.max_cluster_exposure == Decimal("0.40")
        assert config.output_dir == Path("data/portfolio_research")
        assert config.report_output_dir == Path("reports/portfolio_research")
        assert config.json_filename == "latest_portfolio.json"
        assert config.markdown_filename == "latest_portfolio.md"
        assert config.metadata == {}

    def test_config_immutability(self):
        config = PortfolioResearchConfig.default()
        with pytest.raises(AttributeError):
            config.max_assets = 5

    def test_config_custom_values(self):
        config = PortfolioResearchConfig(
            allocation_method="SCORE_PROPORTIONAL",
            max_assets=5,
            min_asset_weight=Decimal("0.01"),
            max_asset_weight=Decimal("0.30"),
            max_total_exposure=Decimal("0.90"),
            max_cluster_exposure=Decimal("0.25"),
            output_dir=Path("custom/data"),
            report_output_dir=Path("custom/reports"),
            json_filename="portfolio.json",
            markdown_filename="portfolio.md",
            metadata={"note": "ok"},
        )
        assert config.allocation_method == "SCORE_PROPORTIONAL"
        assert config.max_assets == 5

    @pytest.mark.parametrize(
        "kwargs,expected_error",
        [
            ({"allocation_method": "INVALID"}, "allocation_method"),
            ({"max_assets": 0}, "max_assets"),
            ({"max_assets": -1}, "max_assets"),
            ({"max_assets": "five"}, "max_assets"),
            ({"min_asset_weight": Decimal("-0.01")}, "min_asset_weight"),
            ({"max_asset_weight": Decimal("0")}, "max_asset_weight"),
            ({"max_asset_weight": Decimal("1.1")}, "max_asset_weight"),
            ({"max_total_exposure": Decimal("0")}, "max_total_exposure"),
            ({"max_cluster_exposure": Decimal("1.1")}, "max_cluster_exposure"),
            ({"max_asset_weight": Decimal("0.01"), "min_asset_weight": Decimal("0.02")}, "max_asset_weight"),
            ({"max_cluster_exposure": Decimal("0.50"), "max_total_exposure": Decimal("0.40")}, "max_cluster_exposure"),
            ({"json_filename": ""}, "json_filename"),
            ({"markdown_filename": "  "}, "markdown_filename"),
        ],
    )
    def test_config_validation(self, kwargs, expected_error):
        defaults = {}
        defaults.update(kwargs)
        with pytest.raises(ValueError, match=expected_error):
            PortfolioResearchConfig(**defaults)

    def test_config_metadata_immutable(self):
        config = PortfolioResearchConfig(metadata={"a": [1, 2]})
        assert config.metadata["a"] == [1, 2]
        with pytest.raises(TypeError):
            config.metadata["a"] = [3]

    def test_config_accepts_string_path(self):
        config = PortfolioResearchConfig(output_dir="data/alt", report_output_dir="reports/alt")
        assert config.output_dir == Path("data/alt")
        assert config.report_output_dir == Path("reports/alt")


class TestPortfolioAllocation:
    def test_default_allocation(self):
        allocation = PortfolioAllocation(
            pair="BTC/USDT",
            weight=Decimal("0.10"),
            cluster="C1",
            score=Decimal("0.5"),
            allocation_reason="EQUAL_WEIGHT",
        )
        assert allocation.pair == "BTC/USDT"
        assert allocation.cluster == "C1"
        assert allocation.score == Decimal("0.5")

    def test_cluster_normalization(self):
        allocation = PortfolioAllocation(
            pair="BTC/USDT",
            weight=Decimal("0.10"),
            cluster="  c1  ",
            score=None,
            allocation_reason="EQUAL_WEIGHT",
        )
        assert allocation.cluster == "C1"

    def test_cluster_unclassified(self):
        allocation = PortfolioAllocation(
            pair="BTC/USDT",
            weight=Decimal("0.10"),
            cluster="  ",
            score=None,
            allocation_reason="EQUAL_WEIGHT",
        )
        assert allocation.cluster == "UNCLASSIFIED"

    @pytest.mark.parametrize(
        "kwargs,expected_error",
        [
            ({"pair": ""}, "pair"),
            ({"weight": Decimal("-0.01")}, "weight"),
            ({"weight": Decimal("1.1")}, "weight"),
            ({"allocation_reason": ""}, "allocation_reason"),
            ({"score": "bad"}, "score"),
        ],
    )
    def test_allocation_validation(self, kwargs, expected_error):
        defaults = {
            "pair": "BTC/USDT",
            "weight": Decimal("0.10"),
            "cluster": "C1",
            "score": None,
            "allocation_reason": "EQUAL_WEIGHT",
        }
        defaults.update(kwargs)
        with pytest.raises(ValueError, match=expected_error):
            PortfolioAllocation(**defaults)

    def test_allocation_immutability(self):
        allocation = PortfolioAllocation(
            pair="BTC/USDT",
            weight=Decimal("0.10"),
            cluster="C1",
            score=None,
            allocation_reason="EQUAL_WEIGHT",
        )
        with pytest.raises(AttributeError):
            allocation.weight = Decimal("0.20")


class TestPortfolioExclusion:
    def test_exclusion(self):
        exclusion = PortfolioExclusion(
            pair="BTC/USDT", reason_code=BLACKLISTED_PAIR, details="pair in blacklist"
        )
        assert exclusion.pair == "BTC/USDT"
        assert exclusion.reason_code == BLACKLISTED_PAIR

    def test_invalid_reason_code(self):
        with pytest.raises(ValueError, match="unsupported reason code"):
            PortfolioExclusion(pair="BTC/USDT", reason_code="UNKNOWN", details="")

    def test_exclusion_validation(self):
        with pytest.raises(ValueError, match="pair"):
            PortfolioExclusion(pair="", reason_code=BLACKLISTED_PAIR, details="")


class TestPortfolioResearchContext:
    def test_accepted_context(self):
        now = datetime.now(timezone.utc)
        allocation = PortfolioAllocation(
            pair="BTC/USDT",
            weight=Decimal("0.10"),
            cluster="C1",
            score=None,
            allocation_reason="EQUAL_WEIGHT",
        )
        context = PortfolioResearchContext(
            version=PORTFOLIO_RESEARCH_ADAPTER_VERSION,
            source_context_fingerprint="sha256-source",
            portfolio_fingerprint="sha256-portfolio",
            generated_at=now,
            mode="LONG",
            allocation_method="EQUAL_WEIGHT",
            allocations=(allocation,),
            exclusions=(),
            cluster_exposure={"C1": Decimal("0.10")},
            total_exposure=Decimal("0.10"),
            accepted=True,
            research_only=True,
            human_approval_required=True,
            reason_codes=(PORTFOLIO_ACCEPTED,),
        )
        assert context.accepted
        assert context.research_only
        assert context.human_approval_required

    def test_rejected_context(self):
        now = datetime.now(timezone.utc)
        context = PortfolioResearchContext(
            version=PORTFOLIO_RESEARCH_ADAPTER_VERSION,
            source_context_fingerprint="sha256-source",
            portfolio_fingerprint="sha256-empty",
            generated_at=now,
            mode="BLOCK_ALL",
            allocation_method="EQUAL_WEIGHT",
            allocations=(),
            exclusions=(),
            cluster_exposure={},
            total_exposure=Decimal("0"),
            accepted=False,
            research_only=True,
            human_approval_required=True,
            reason_codes=(MISSING_CONTEXT,),
        )
        assert not context.accepted
        assert context.mode == "BLOCK_ALL"

    def test_rejected_context_must_be_empty(self):
        now = datetime.now(timezone.utc)
        allocation = PortfolioAllocation(
            pair="BTC/USDT",
            weight=Decimal("0.10"),
            cluster="C1",
            score=None,
            allocation_reason="EQUAL_WEIGHT",
        )
        with pytest.raises(ValueError, match="rejected result must have empty allocations"):
            PortfolioResearchContext(
                version=PORTFOLIO_RESEARCH_ADAPTER_VERSION,
                source_context_fingerprint="sha256-source",
                portfolio_fingerprint="sha256-portfolio",
                generated_at=now,
                mode="BLOCK_ALL",
                allocation_method="EQUAL_WEIGHT",
                allocations=(allocation,),
                exclusions=(),
                cluster_exposure={},
                total_exposure=Decimal("0"),
                accepted=False,
                research_only=True,
                human_approval_required=True,
                reason_codes=(MISSING_CONTEXT,),
            )

    def test_rejected_context_must_block_all(self):
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="rejected result must have mode='BLOCK_ALL'"):
            PortfolioResearchContext(
                version=PORTFOLIO_RESEARCH_ADAPTER_VERSION,
                source_context_fingerprint="sha256-source",
                portfolio_fingerprint="sha256-empty",
                generated_at=now,
                mode="LONG",
                allocation_method="EQUAL_WEIGHT",
                allocations=(),
                exclusions=(),
                cluster_exposure={},
                total_exposure=Decimal("0"),
                accepted=False,
                research_only=True,
                human_approval_required=True,
                reason_codes=(MISSING_CONTEXT,),
            )

    def test_rejected_context_zero_exposure(self):
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="total_exposure=0"):
            PortfolioResearchContext(
                version=PORTFOLIO_RESEARCH_ADAPTER_VERSION,
                source_context_fingerprint="sha256-source",
                portfolio_fingerprint="sha256-empty",
                generated_at=now,
                mode="BLOCK_ALL",
                allocation_method="EQUAL_WEIGHT",
                allocations=(),
                exclusions=(),
                cluster_exposure={},
                total_exposure=Decimal("0.10"),
                accepted=False,
                research_only=True,
                human_approval_required=True,
                reason_codes=(MISSING_CONTEXT,),
            )

    def test_safety_flags_must_be_true(self):
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="research_only and human_approval_required"):
            PortfolioResearchContext(
                version=PORTFOLIO_RESEARCH_ADAPTER_VERSION,
                source_context_fingerprint="sha256-source",
                portfolio_fingerprint="sha256-empty",
                generated_at=now,
                mode="BLOCK_ALL",
                allocation_method="EQUAL_WEIGHT",
                allocations=(),
                exclusions=(),
                cluster_exposure={},
                total_exposure=Decimal("0"),
                accepted=False,
                research_only=False,
                human_approval_required=True,
                reason_codes=(MISSING_CONTEXT,),
            )

    def test_invalid_reason_code(self):
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="unsupported reason code"):
            PortfolioResearchContext(
                version=PORTFOLIO_RESEARCH_ADAPTER_VERSION,
                source_context_fingerprint="sha256-source",
                portfolio_fingerprint="sha256-empty",
                generated_at=now,
                mode="BLOCK_ALL",
                allocation_method="EQUAL_WEIGHT",
                allocations=(),
                exclusions=(),
                cluster_exposure={},
                total_exposure=Decimal("0"),
                accepted=False,
                research_only=True,
                human_approval_required=True,
                reason_codes=("UNKNOWN",),
            )

    def test_cluster_exposure_validation(self):
        now = datetime.now(timezone.utc)
        with pytest.raises(ValueError, match="cluster keys"):
            PortfolioResearchContext(
                version=PORTFOLIO_RESEARCH_ADAPTER_VERSION,
                source_context_fingerprint="sha256-source",
                portfolio_fingerprint="sha256-empty",
                generated_at=now,
                mode="BLOCK_ALL",
                allocation_method="EQUAL_WEIGHT",
                allocations=(),
                exclusions=(),
                cluster_exposure={"": Decimal("0")},
                total_exposure=Decimal("0"),
                accepted=False,
                research_only=True,
                human_approval_required=True,
                reason_codes=(MISSING_CONTEXT,),
            )

    def test_context_immutability(self):
        now = datetime.now(timezone.utc)
        context = PortfolioResearchContext(
            version=PORTFOLIO_RESEARCH_ADAPTER_VERSION,
            source_context_fingerprint="sha256-source",
            portfolio_fingerprint="sha256-empty",
            generated_at=now,
            mode="BLOCK_ALL",
            allocation_method="EQUAL_WEIGHT",
            allocations=(),
            exclusions=(),
            cluster_exposure={},
            total_exposure=Decimal("0"),
            accepted=False,
            research_only=True,
            human_approval_required=True,
            reason_codes=(MISSING_CONTEXT,),
        )
        with pytest.raises(AttributeError):
            context.accepted = True


class TestPortfolioResearchError:
    def test_error_reason_code(self):
        error = PortfolioResearchError("boom", reason_code=INVALID_CONFIG)
        assert str(error) == "boom"
        assert error.reason_code == INVALID_CONFIG

    def test_error_without_reason_code(self):
        error = PortfolioResearchError("boom")
        assert error.reason_code is None
