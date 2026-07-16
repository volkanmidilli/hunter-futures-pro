"""Tests for hunter.research_market_data.writer."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from hunter.research_market_data.engine import build_research_market_data_bundle
from hunter.research_market_data.errors import ResearchMarketDataWriterError
from hunter.research_market_data.models import MarketDataFileSpec
from hunter.research_market_data.writer import (
    ResearchMarketDataBundleWriterError,
    atomic_write_json_research_market_data_bundle,
    atomic_write_markdown_research_market_data_bundle,
    research_market_data_bundle_to_json_text,
    research_market_data_bundle_to_markdown_text,
    write_research_market_data_bundle,
)


def _make_daily_csv(path: Path, n: int = 35) -> None:
    lines = ["date,open,high,low,close,volume"]
    close_price = Decimal("100")
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    for i in range(n):
        high = close_price * Decimal("1.05")
        low = close_price * Decimal("0.95")
        lines.append(
            f"{(start + timedelta(days=i)).strftime('%Y-%m-%dT%H:%M:%S+00:00')},"
            f"{close_price},{high},{low},{close_price},1000"
        )
        close_price = close_price * Decimal("1.001")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.fixture
def sample_bundle(tmp_path: Path) -> object:
    btc_path = tmp_path / "BTCUSDT.csv"
    sol_path = tmp_path / "SOLUSDT.csv"
    _make_daily_csv(btc_path)
    _make_daily_csv(sol_path)
    return build_research_market_data_bundle(
        candidate_specs=[MarketDataFileSpec(path=sol_path, expected_symbol="SOLUSDT")],
        btc_spec=MarketDataFileSpec(path=btc_path, expected_symbol="BTCUSDT"),
        generated_at=datetime(2024, 2, 1, tzinfo=timezone.utc),
    )


class TestSerialization:
    def test_json_text_is_deterministic(self, sample_bundle: object) -> None:
        t1 = research_market_data_bundle_to_json_text(sample_bundle)
        t2 = research_market_data_bundle_to_json_text(sample_bundle)
        assert t1 == t2
        assert "research_only" in t1
        assert "execution_approval_granted" in t1

    def test_markdown_contains_safety_notice(self, sample_bundle: object) -> None:
        text = research_market_data_bundle_to_markdown_text(sample_bundle)
        assert "Research Market Data Bundle" in text
        assert "research-only" in text
        assert "SOL/USDT" in text


class TestWrite:
    def test_write_json_and_markdown(self, sample_bundle: object, tmp_path: Path) -> None:
        json_path = tmp_path / "bundle.json"
        md_path = tmp_path / "bundle.md"
        write_research_market_data_bundle(
            sample_bundle,
            json_path=json_path,
            markdown_path=md_path,
        )
        assert json_path.exists()
        assert md_path.exists()
        assert "bundle" in json_path.read_text(encoding="utf-8")

    def test_no_overwrite_by_default(self, sample_bundle: object, tmp_path: Path) -> None:
        json_path = tmp_path / "bundle.json"
        json_path.write_text("existing", encoding="utf-8")
        with pytest.raises(ResearchMarketDataBundleWriterError) as exc:
            write_research_market_data_bundle(
                sample_bundle,
                json_path=json_path,
                markdown_path=tmp_path / "bundle.md",
            )
        assert "FILE_EXISTS" in exc.value.reason_code

    def test_overwrite_with_flag(self, sample_bundle: object, tmp_path: Path) -> None:
        json_path = tmp_path / "bundle.json"
        md_path = tmp_path / "bundle.md"
        json_path.write_text("existing", encoding="utf-8")
        md_path.write_text("existing", encoding="utf-8")
        write_research_market_data_bundle(
            sample_bundle,
            json_path=json_path,
            markdown_path=md_path,
            overwrite=True,
        )
        assert "bundle" in json_path.read_text(encoding="utf-8")

    def test_atomic_json_write(self, sample_bundle: object, tmp_path: Path) -> None:
        path = tmp_path / "bundle.json"
        atomic_write_json_research_market_data_bundle(sample_bundle, path)
        assert path.exists()

    def test_atomic_markdown_write(self, sample_bundle: object, tmp_path: Path) -> None:
        path = tmp_path / "bundle.md"
        atomic_write_markdown_research_market_data_bundle(sample_bundle, path)
        assert path.exists()
