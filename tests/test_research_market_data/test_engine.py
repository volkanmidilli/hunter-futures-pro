"""Tests for hunter.research_market_data.engine."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from hunter.research_market_data.engine import build_research_market_data_bundle
from hunter.research_market_data.errors import ResearchMarketDataBundleError
from hunter.research_market_data.models import (
    BTC_BENCHMARK_MISSING,
    ETH_BENCHMARK_MISSING,
    ResearchMarketDataConfig,
    MarketDataFileSpec,
)


def write_csv(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def make_daily_csv(
    path: Path,
    pair: str,
    start: datetime,
    n: int,
    open: Decimal = Decimal("100"),
    daily_return: Decimal = Decimal("0.001"),
) -> None:
    lines = ["date,open,high,low,close,volume"]
    close_price = open
    for i in range(n):
        high = close_price * Decimal("1.05")
        low = close_price * Decimal("0.95")
        lines.append(
            f"{(start + timedelta(days=i)).strftime('%Y-%m-%dT%H:%M:%S+00:00')},"
            f"{close_price},{high},{low},{close_price},1000"
        )
        close_price = close_price * (Decimal("1") + daily_return)
    write_csv(path, lines)


class TestBuildBundle:
    def test_successful_bundle(self, tmp_path: Path) -> None:
        btc_path = tmp_path / "BTCUSDT.csv"
        sol_path = tmp_path / "SOLUSDT.csv"
        make_daily_csv(btc_path, "BTC/USDT", datetime(2024, 1, 1, tzinfo=timezone.utc), 35)
        make_daily_csv(
            sol_path,
            "SOL/USDT",
            datetime(2024, 1, 1, tzinfo=timezone.utc),
            35,
            open=Decimal("10"),
            daily_return=Decimal("0.02"),
        )
        bundle = build_research_market_data_bundle(
            candidate_specs=[MarketDataFileSpec(path=sol_path, expected_symbol="SOLUSDT")],
            btc_spec=MarketDataFileSpec(path=btc_path, expected_symbol="BTCUSDT"),
            generated_at=datetime(2024, 2, 1, tzinfo=timezone.utc),
        )
        assert bundle.btc_series.pair == "BTC/USDT"
        assert len(bundle.candidates) == 1
        assert bundle.candidates[0].pair == "SOL/USDT"
        assert bundle.eth_series is None
        assert ETH_BENCHMARK_MISSING in bundle.reason_codes
        assert bundle.manifest.bundle_fingerprint

    def test_missing_btc_fails(self, tmp_path: Path) -> None:
        sol_path = tmp_path / "SOLUSDT.csv"
        missing_btc = tmp_path / "BTCUSDT.csv"
        make_daily_csv(sol_path, "SOL/USDT", datetime(2024, 1, 1, tzinfo=timezone.utc), 35)
        with pytest.raises(ResearchMarketDataBundleError) as exc:
            build_research_market_data_bundle(
                candidate_specs=[MarketDataFileSpec(path=sol_path, expected_symbol="SOLUSDT")],
                btc_spec=MarketDataFileSpec(path=missing_btc, expected_symbol="BTCUSDT"),
            )
        assert exc.value.reason_code == BTC_BENCHMARK_MISSING

    def test_invalid_candidate_excluded(self, tmp_path: Path) -> None:
        btc_path = tmp_path / "BTCUSDT.csv"
        sol_path = tmp_path / "SOLUSDT.csv"
        bad_path = tmp_path / "BADUSDT.csv"
        make_daily_csv(btc_path, "BTC/USDT", datetime(2024, 1, 1, tzinfo=timezone.utc), 35)
        make_daily_csv(sol_path, "SOL/USDT", datetime(2024, 1, 1, tzinfo=timezone.utc), 35)
        # Bad CSV has a zero close, which is invalid.
        write_csv(bad_path, [
            "date,open,high,low,close,volume",
            "2024-01-01T00:00:00+00:00,1,2,1,0,100",
        ])
        bundle = build_research_market_data_bundle(
            candidate_specs=[
                MarketDataFileSpec(path=sol_path, expected_symbol="SOLUSDT"),
                MarketDataFileSpec(path=bad_path, expected_symbol="BADUSDT"),
            ],
            btc_spec=MarketDataFileSpec(path=btc_path, expected_symbol="BTCUSDT"),
            generated_at=datetime(2024, 2, 1, tzinfo=timezone.utc),
        )
        assert len(bundle.candidates) == 1
        assert bundle.candidates[0].pair == "SOL/USDT"
        assert len(bundle.exclusions) == 1

    def test_eth_optional(self, tmp_path: Path) -> None:
        btc_path = tmp_path / "BTCUSDT.csv"
        eth_path = tmp_path / "ETHUSDT.csv"
        sol_path = tmp_path / "SOLUSDT.csv"
        make_daily_csv(btc_path, "BTC/USDT", datetime(2024, 1, 1, tzinfo=timezone.utc), 35)
        make_daily_csv(eth_path, "ETH/USDT", datetime(2024, 1, 1, tzinfo=timezone.utc), 35)
        make_daily_csv(sol_path, "SOL/USDT", datetime(2024, 1, 1, tzinfo=timezone.utc), 35)
        bundle = build_research_market_data_bundle(
            candidate_specs=[MarketDataFileSpec(path=sol_path, expected_symbol="SOLUSDT")],
            btc_spec=MarketDataFileSpec(path=btc_path, expected_symbol="BTCUSDT"),
            eth_spec=MarketDataFileSpec(path=eth_path, expected_symbol="ETHUSDT"),
            generated_at=datetime(2024, 2, 1, tzinfo=timezone.utc),
        )
        assert bundle.eth_series is not None
        assert bundle.eth_series.pair == "ETH/USDT"
        assert ETH_BENCHMARK_MISSING not in bundle.reason_codes

    def test_all_candidates_excluded_fails(self, tmp_path: Path) -> None:
        btc_path = tmp_path / "BTCUSDT.csv"
        bad_path = tmp_path / "BADUSDT.csv"
        make_daily_csv(btc_path, "BTC/USDT", datetime(2024, 1, 1, tzinfo=timezone.utc), 35)
        write_csv(bad_path, [
            "date,open,high,low,close,volume",
            "2024-01-01T00:00:00+00:00,1,2,1,0,100",
        ])
        with pytest.raises(ResearchMarketDataBundleError) as exc:
            build_research_market_data_bundle(
                candidate_specs=[MarketDataFileSpec(path=bad_path, expected_symbol="BADUSDT")],
                btc_spec=MarketDataFileSpec(path=btc_path, expected_symbol="BTCUSDT"),
            )
        assert exc.value.reason_code == "ALL_CANDIDATES_EXCLUDED"

    def test_deterministic_fingerprint(self, tmp_path: Path) -> None:
        btc_path = tmp_path / "BTCUSDT.csv"
        sol_path = tmp_path / "SOLUSDT.csv"
        make_daily_csv(btc_path, "BTC/USDT", datetime(2024, 1, 1, tzinfo=timezone.utc), 35)
        make_daily_csv(sol_path, "SOL/USDT", datetime(2024, 1, 1, tzinfo=timezone.utc), 35)
        bundle1 = build_research_market_data_bundle(
            candidate_specs=[MarketDataFileSpec(path=sol_path, expected_symbol="SOLUSDT")],
            btc_spec=MarketDataFileSpec(path=btc_path, expected_symbol="BTCUSDT"),
            generated_at=datetime(2024, 2, 1, tzinfo=timezone.utc),
        )
        bundle2 = build_research_market_data_bundle(
            candidate_specs=[MarketDataFileSpec(path=sol_path, expected_symbol="SOLUSDT")],
            btc_spec=MarketDataFileSpec(path=btc_path, expected_symbol="BTCUSDT"),
            generated_at=datetime(2024, 2, 1, tzinfo=timezone.utc),
        )
        assert bundle1.manifest.bundle_fingerprint == bundle2.manifest.bundle_fingerprint
        assert bundle1.manifest.series_fingerprints == bundle2.manifest.series_fingerprints
