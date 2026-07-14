"""Tests for portfolio_research_adapter writer (MVP-57 Step 5)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from hunter.portfolio_research_adapter.models import (
    PORTFOLIO_RESEARCH_ADAPTER_VERSION,
    PortfolioAllocation,
    PortfolioResearchConfig,
    PortfolioResearchContext,
)
from hunter.portfolio_research_adapter.writer import (
    PortfolioResearchWriterError,
    atomic_write_json_portfolio_research_context,
    atomic_write_markdown_portfolio_research_context,
    portfolio_research_context_to_dict,
    portfolio_research_context_to_json_text,
    portfolio_research_context_to_markdown_text,
    write_portfolio_research_context,
)


@pytest.fixture
def now() -> datetime:
    return datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def accepted_context(now: datetime) -> PortfolioResearchContext:
    allocation = PortfolioAllocation(
        pair="BTC/USDT",
        weight=Decimal("0.20"),
        cluster="C1",
        score=Decimal("1.5"),
        allocation_reason="EQUAL_WEIGHT",
    )
    return PortfolioResearchContext(
        version=PORTFOLIO_RESEARCH_ADAPTER_VERSION,
        source_context_fingerprint="sha256-source",
        portfolio_fingerprint="sha256-portfolio",
        generated_at=now,
        mode="LONG",
        allocation_method="EQUAL_WEIGHT",
        allocations=(allocation,),
        exclusions=(),
        cluster_exposure={"C1": Decimal("0.20")},
        total_exposure=Decimal("0.20"),
        accepted=True,
        research_only=True,
        human_approval_required=True,
        reason_codes=("PORTFOLIO_ACCEPTED",),
    )


@pytest.fixture
def tmp_writer_paths(tmp_path: Path) -> tuple[Path, Path]:
    return tmp_path / "portfolio.json", tmp_path / "portfolio.md"


class TestToDict:
    def test_dict_keys(self, accepted_context):
        data = portfolio_research_context_to_dict(accepted_context)
        assert data["version"] == PORTFOLIO_RESEARCH_ADAPTER_VERSION
        assert data["source_context_fingerprint"] == "sha256-source"
        assert data["portfolio_fingerprint"] == "sha256-portfolio"
        assert data["mode"] == "LONG"
        assert data["allocation_method"] == "EQUAL_WEIGHT"
        assert data["accepted"] is True
        assert data["research_only"] is True
        assert data["human_approval_required"] is True
        assert data["total_exposure"] == "0.20"
        assert "allocations" in data
        assert "exclusions" in data
        assert "cluster_exposure" in data
        assert "reason_codes" in data
        assert "metadata" in data
        assert "safety_notice" in data

    def test_allocation_dict(self, accepted_context):
        data = portfolio_research_context_to_dict(accepted_context)
        allocation = data["allocations"][0]
        assert allocation["pair"] == "BTC/USDT"
        assert allocation["weight"] == "0.20"
        assert allocation["cluster"] == "C1"
        assert allocation["score"] == "1.5"
        assert allocation["allocation_reason"] == "EQUAL_WEIGHT"


class TestToJsonText:
    def test_json_round_trip(self, accepted_context):
        text = portfolio_research_context_to_json_text(accepted_context)
        data = json.loads(text)
        assert data["version"] == PORTFOLIO_RESEARCH_ADAPTER_VERSION
        assert data["accepted"] is True
        assert data["safety_notice"]

    def test_json_determinism(self, accepted_context):
        text1 = portfolio_research_context_to_json_text(accepted_context)
        text2 = portfolio_research_context_to_json_text(accepted_context)
        assert text1 == text2


class TestToMarkdownText:
    def test_markdown_contains_sections(self, accepted_context):
        text = portfolio_research_context_to_markdown_text(accepted_context)
        assert "# Portfolio Research Context" in text
        assert "## Safety Notice" in text
        assert "## Allocations" in text
        assert "## Exclusions" in text
        assert "## Cluster Exposure" in text
        assert "## Reason Codes" in text
        assert "BTC/USDT" in text

    def test_markdown_with_paths(self, accepted_context):
        text = portfolio_research_context_to_markdown_text(
            accepted_context,
            json_path=Path("data/portfolio.json"),
            markdown_path=Path("reports/portfolio.md"),
        )
        assert "data/portfolio.json" in text
        assert "reports/portfolio.md" in text


class TestAtomicWrites:
    def test_write_json(self, accepted_context, tmp_writer_paths):
        json_path, _ = tmp_writer_paths
        path = atomic_write_json_portfolio_research_context(accepted_context, json_path)
        assert path == json_path
        data = json.loads(json_path.read_text())
        assert data["accepted"] is True

    def test_write_markdown(self, accepted_context, tmp_writer_paths):
        _, md_path = tmp_writer_paths
        path = atomic_write_markdown_portfolio_research_context(accepted_context, md_path)
        assert path == md_path
        assert "Portfolio Research Context" in md_path.read_text()

    def test_write_both(self, accepted_context, tmp_path: Path):
        config = PortfolioResearchConfig(
            output_dir=tmp_path / "data",
            report_output_dir=tmp_path / "reports",
            json_filename="portfolio.json",
            markdown_filename="portfolio.md",
        )
        json_path, md_path = write_portfolio_research_context(accepted_context, config)
        assert json_path.exists()
        assert md_path.exists()
        assert json.loads(json_path.read_text())["accepted"] is True
        assert "## Safety Notice" in md_path.read_text()

    def test_default_paths(self, accepted_context, tmp_path: Path):
        config = PortfolioResearchConfig(
            output_dir=tmp_path / "data",
            report_output_dir=tmp_path / "reports",
        )
        json_path, md_path = write_portfolio_research_context(accepted_context, config)
        assert json_path.name == "latest_portfolio.json"
        assert md_path.name == "latest_portfolio.md"


class TestDeterminism:
    def test_writer_determinism(self, accepted_context):
        json1 = portfolio_research_context_to_json_text(accepted_context)
        json2 = portfolio_research_context_to_json_text(accepted_context)
        md1 = portfolio_research_context_to_markdown_text(accepted_context)
        md2 = portfolio_research_context_to_markdown_text(accepted_context)
        assert json1 == json2
        assert md1 == md2


class TestRejectedContext:
    def test_rejected_context_markdown(self, now):
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
            reason_codes=("MISSING_CONTEXT",),
        )
        data = portfolio_research_context_to_dict(context)
        assert data["accepted"] is False
        assert data["allocations"] == []
        text = portfolio_research_context_to_markdown_text(context)
        assert "BLOCK_ALL" in text
        assert "_No allocations._" in text
