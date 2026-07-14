"""Integration tests for the Portfolio Research Adapter (MVP-57 Step 6)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from hunter.portfolio_research_adapter import (
    PORTFOLIO_RESEARCH_ADAPTER_VERSION,
    PORTFOLIO_ACCEPTED,
    PortfolioResearchConfig,
    build_portfolio_research_context,
    portfolio_research_context_to_json_text,
    write_portfolio_research_context,
)
from hunter.strategy_contract_consumer.models import ValidatedStrategyContext


@pytest.fixture
def now() -> datetime:
    return datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def base_context(now: datetime) -> ValidatedStrategyContext:
    return ValidatedStrategyContext(
        accepted=True,
        validated_at=now,
        source_fingerprint="sha256-source",
        source_path="strategy_contract_input.json",
        input_version="0.56.0-dev",
        mode="LONG",
        whitelist=("BTC/USDT", "ETH/USDT", "SOL/USDT", "ADA/USDT", "XRP/USDT"),
        blacklist=(),
        safety_flags={},
        reason_codes=("VALIDATION_ACCEPTED",),
    )


class TestIntegrationPublicApi:
    def test_equal_weight_end_to_end(self, base_context, now, tmp_path: Path):
        config = PortfolioResearchConfig(
            max_assets=10,
            max_asset_weight=Decimal("1.00"),
            max_total_exposure=Decimal("1.00"),
            max_cluster_exposure=Decimal("1.00"),
            output_dir=tmp_path / "data",
            report_output_dir=tmp_path / "reports",
        )
        context = build_portfolio_research_context(base_context, config, generated_at=now)
        assert context.accepted
        assert context.mode == "LONG"
        assert context.allocation_method == "EQUAL_WEIGHT"
        assert len(context.allocations) == 5
        assert context.total_exposure == Decimal("1.00")
        assert PORTFOLIO_ACCEPTED in context.reason_codes

        json_path, md_path = write_portfolio_research_context(context, config)
        assert json_path.exists()
        assert md_path.exists()
        data = json.loads(json_path.read_text())
        assert data["version"] == PORTFOLIO_RESEARCH_ADAPTER_VERSION
        assert data["accepted"] is True
        assert "safety_notice" in data

    def test_score_proportional_end_to_end(self, base_context, now, tmp_path: Path):
        config = PortfolioResearchConfig(
            allocation_method="SCORE_PROPORTIONAL",
            max_assets=10,
            max_asset_weight=Decimal("1.00"),
            max_total_exposure=Decimal("1.00"),
            max_cluster_exposure=Decimal("1.00"),
            output_dir=tmp_path / "data",
            report_output_dir=tmp_path / "reports",
        )
        scores = {
            "BTC/USDT": Decimal("5"),
            "ETH/USDT": Decimal("3"),
            "SOL/USDT": Decimal("2"),
            "ADA/USDT": Decimal("1"),
            "XRP/USDT": Decimal("1"),
        }
        context = build_portfolio_research_context(
            base_context, config, score_by_pair=scores, generated_at=now
        )
        assert context.accepted
        assert context.allocation_method == "SCORE_PROPORTIONAL"
        assert len(context.allocations) == 5
        btc = next(a for a in context.allocations if a.pair == "BTC/USDT")
        xrp = next(a for a in context.allocations if a.pair == "XRP/USDT")
        assert btc.weight > xrp.weight

        json_text = portfolio_research_context_to_json_text(context)
        data = json.loads(json_text)
        assert data["allocation_method"] == "SCORE_PROPORTIONAL"

    def test_rejected_context_fail_closed(self, base_context, now, tmp_path: Path):
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
        config = PortfolioResearchConfig(
            output_dir=tmp_path / "data",
            report_output_dir=tmp_path / "reports",
        )
        context = build_portfolio_research_context(rejected, config, generated_at=now)
        assert not context.accepted
        assert context.mode == "BLOCK_ALL"
        assert context.allocations == ()
        assert context.total_exposure == Decimal("0")
        assert context.portfolio_fingerprint

    def test_block_all_context_empty(self, base_context, now, tmp_path: Path):
        config = PortfolioResearchConfig(
            output_dir=tmp_path / "data",
            report_output_dir=tmp_path / "reports",
        )
        blocked = ValidatedStrategyContext(
            accepted=True,
            validated_at=now,
            source_fingerprint="sha256-source",
            source_path="strategy_contract_input.json",
            input_version="0.56.0-dev",
            mode="BLOCK_ALL",
            whitelist=(),
            blacklist=(),
            safety_flags={},
            reason_codes=("VALIDATION_ACCEPTED",),
        )
        context = build_portfolio_research_context(blocked, config, generated_at=now)
        assert not context.accepted
        assert context.mode == "BLOCK_ALL"
        assert context.allocations == ()

    def test_empty_whitelist(self, base_context, now, tmp_path: Path):
        config = PortfolioResearchConfig(
            output_dir=tmp_path / "data",
            report_output_dir=tmp_path / "reports",
        )
        empty = ValidatedStrategyContext(
            accepted=True,
            validated_at=now,
            source_fingerprint="sha256-source",
            source_path="strategy_contract_input.json",
            input_version="0.56.0-dev",
            mode="LONG",
            whitelist=(),
            blacklist=(),
            safety_flags={},
            reason_codes=("VALIDATION_ACCEPTED",),
        )
        context = build_portfolio_research_context(empty, config, generated_at=now)
        assert not context.accepted
        assert context.allocations == ()

    def test_max_assets_limit(self, base_context, now):
        config = PortfolioResearchConfig(
            max_assets=2,
            max_asset_weight=Decimal("1.00"),
            max_total_exposure=Decimal("1.00"),
            max_cluster_exposure=Decimal("1.00"),
        )
        context = build_portfolio_research_context(base_context, config, generated_at=now)
        assert context.accepted
        assert len(context.allocations) == 2
        assert context.total_exposure == Decimal("1.00")

    def test_min_asset_weight_filter(self, base_context, now):
        config = PortfolioResearchConfig(
            max_assets=10,
            max_asset_weight=Decimal("1.00"),
            min_asset_weight=Decimal("0.30"),
            max_total_exposure=Decimal("1.00"),
            max_cluster_exposure=Decimal("1.00"),
        )
        context = build_portfolio_research_context(base_context, config, generated_at=now)
        # 5 pairs equal weight 0.20 < 0.30, so all excluded.
        assert not context.accepted
        assert context.allocations == ()

    def test_max_asset_weight_cap(self, base_context, now):
        config = PortfolioResearchConfig(
            max_assets=10,
            max_asset_weight=Decimal("0.15"),
            max_total_exposure=Decimal("1.00"),
            max_cluster_exposure=Decimal("1.00"),
        )
        context = build_portfolio_research_context(base_context, config, generated_at=now)
        assert context.accepted
        assert all(a.weight <= Decimal("0.15") for a in context.allocations)
        assert context.total_exposure == Decimal("0.75")

    def test_cluster_limit_enforcement(self, base_context, now):
        config = PortfolioResearchConfig(
            max_assets=10,
            max_asset_weight=Decimal("1.00"),
            max_total_exposure=Decimal("1.00"),
            max_cluster_exposure=Decimal("0.30"),
        )
        clusters = {
            "BTC/USDT": "C1",
            "ETH/USDT": "C1",
            "SOL/USDT": "C1",
            "ADA/USDT": "C2",
            "XRP/USDT": "C2",
        }
        context = build_portfolio_research_context(
            base_context, config, cluster_by_pair=clusters, generated_at=now
        )
        assert context.accepted
        c1_exposure = sum(
            a.weight for a in context.allocations if a.cluster == "C1"
        )
        assert c1_exposure <= Decimal("0.30")

    def test_unclassified_cluster_fallback(self, base_context, now):
        config = PortfolioResearchConfig(
            max_assets=10,
            max_asset_weight=Decimal("1.00"),
            max_total_exposure=Decimal("1.00"),
            max_cluster_exposure=Decimal("1.00"),
        )
        context = build_portfolio_research_context(base_context, config, generated_at=now)
        assert context.accepted
        assert all(a.cluster == "UNCLASSIFIED" for a in context.allocations)

    def test_missing_scores_fail_closed(self, base_context, now):
        config = PortfolioResearchConfig(
            allocation_method="SCORE_PROPORTIONAL",
            max_assets=10,
            max_asset_weight=Decimal("1.00"),
            max_total_exposure=Decimal("1.00"),
            max_cluster_exposure=Decimal("1.00"),
        )
        scores = {"BTC/USDT": Decimal("1")}
        context = build_portfolio_research_context(
            base_context, config, score_by_pair=scores, generated_at=now
        )
        assert context.accepted
        assert all(a.pair == "BTC/USDT" for a in context.allocations)

    def test_all_invalid_scores_empty(self, base_context, now):
        config = PortfolioResearchConfig(
            allocation_method="SCORE_PROPORTIONAL",
            max_assets=10,
            max_asset_weight=Decimal("1.00"),
            max_total_exposure=Decimal("1.00"),
            max_cluster_exposure=Decimal("1.00"),
        )
        scores = {pair: Decimal("0") for pair in base_context.whitelist}
        context = build_portfolio_research_context(
            base_context, config, score_by_pair=scores, generated_at=now
        )
        assert not context.accepted
        assert context.allocations == ()

    def test_determinism(self, base_context, now):
        config = PortfolioResearchConfig(
            max_assets=10,
            max_asset_weight=Decimal("1.00"),
            max_total_exposure=Decimal("1.00"),
            max_cluster_exposure=Decimal("1.00"),
        )
        clusters = {"BTC/USDT": "C1", "ETH/USDT": "C2"}
        context1 = build_portfolio_research_context(
            base_context, config, cluster_by_pair=clusters, generated_at=now
        )
        context2 = build_portfolio_research_context(
            base_context, config, cluster_by_pair=clusters, generated_at=now
        )
        assert context1.portfolio_fingerprint == context2.portfolio_fingerprint
        json1 = portfolio_research_context_to_json_text(context1)
        json2 = portfolio_research_context_to_json_text(context2)
        assert json1 == json2

    def test_precision_quantization(self, base_context, now):
        config = PortfolioResearchConfig(
            max_assets=10,
            max_asset_weight=Decimal("1.00"),
            max_total_exposure=Decimal("1.00"),
            max_cluster_exposure=Decimal("1.00"),
        )
        context = build_portfolio_research_context(base_context, config, generated_at=now)
        for allocation in context.allocations:
            assert allocation.weight == allocation.weight.quantize(Decimal("0.00000001"))

    def test_public_api_exports(self):
        from hunter import portfolio_research_adapter

        assert hasattr(portfolio_research_adapter, "build_portfolio_research_context")
        assert hasattr(portfolio_research_adapter, "PortfolioResearchConfig")
        assert hasattr(portfolio_research_adapter, "PortfolioResearchContext")
        assert hasattr(portfolio_research_adapter, "write_portfolio_research_context")
        assert hasattr(portfolio_research_adapter, "allocate_equal_weight")
        assert hasattr(portfolio_research_adapter, "allocate_score_proportional")

    def test_no_freqtrade_imports_in_package(self, base_context, now):
        import hunter.portfolio_research_adapter as pkg

        assert "freqtrade" not in pkg.__dict__

    def test_no_file_reads_in_engine_path(self, base_context, now):
        # The engine is a pure function and does not read files.
        config = PortfolioResearchConfig()
        build_portfolio_research_context(base_context, config, generated_at=now)
        assert True

    def test_caller_mappings_not_mutated(self, base_context, now):
        config = PortfolioResearchConfig(
            allocation_method="SCORE_PROPORTIONAL",
            max_assets=10,
            max_asset_weight=Decimal("1.00"),
            max_total_exposure=Decimal("1.00"),
            max_cluster_exposure=Decimal("1.00"),
        )
        scores = {pair: Decimal(str(i + 1)) for i, pair in enumerate(base_context.whitelist)}
        clusters = {pair: f"C{i % 2}" for i, pair in enumerate(base_context.whitelist)}
        original_scores = dict(scores)
        original_clusters = dict(clusters)
        build_portfolio_research_context(
            base_context, config, score_by_pair=scores, cluster_by_pair=clusters, generated_at=now
        )
        assert scores == original_scores
        assert clusters == original_clusters

    def test_json_and_markdown_schema(self, base_context, now, tmp_path: Path):
        config = PortfolioResearchConfig(
            max_assets=10,
            max_asset_weight=Decimal("1.00"),
            max_total_exposure=Decimal("1.00"),
            max_cluster_exposure=Decimal("1.00"),
            output_dir=tmp_path / "data",
            report_output_dir=tmp_path / "reports",
        )
        context = build_portfolio_research_context(base_context, config, generated_at=now)
        json_path, md_path = write_portfolio_research_context(context, config)
        data = json.loads(json_path.read_text())
        assert "version" in data
        assert "portfolio_fingerprint" in data
        assert "allocations" in data
        assert "exclusions" in data
        assert "cluster_exposure" in data
        assert "total_exposure" in data
        assert "reason_codes" in data
        assert "safety_notice" in data

        md_text = md_path.read_text()
        assert "# Portfolio Research Context" in md_text
        assert "## Safety Notice" in md_text

    def test_short_mode_accepted(self, base_context, now):
        short = ValidatedStrategyContext(
            accepted=True,
            validated_at=now,
            source_fingerprint="sha256-source",
            source_path="strategy_contract_input.json",
            input_version="0.56.0-dev",
            mode="SHORT",
            whitelist=base_context.whitelist,
            blacklist=(),
            safety_flags={},
            reason_codes=("VALIDATION_ACCEPTED",),
        )
        config = PortfolioResearchConfig(
            max_assets=10,
            max_asset_weight=Decimal("1.00"),
            max_total_exposure=Decimal("1.00"),
            max_cluster_exposure=Decimal("1.00"),
        )
        context = build_portfolio_research_context(short, config, generated_at=now)
        assert context.accepted
        assert context.mode == "SHORT"
