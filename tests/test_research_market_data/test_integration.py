"""Integration tests for the research market data pipeline (MVP-63 / SPEC-064)."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from hunter.discovery.engine import build_discovery_report
from hunter.discovery.models import DiscoveryConfig, DiscoveryState
from hunter.relative_strength.engine import build_relative_strength_report
from hunter.research_market_data.adapters import (
    build_discovery_input_bundle,
    build_relative_strength_run_inputs,
)
from hunter.research_market_data.engine import build_research_market_data_bundle
from hunter.research_market_data.models import MarketDataFileSpec, MarketDataSafetyFlags
from hunter.research_market_data.writer import write_research_market_data_bundle


def _make_csv(
    path: Path,
    pair: str,
    n: int,
    start: datetime,
    open_price: Decimal,
    daily_return: Decimal,
) -> None:
    lines = ["date,open,high,low,close,volume"]
    close_price = open_price
    for i in range(n):
        high = close_price * Decimal("1.05")
        low = close_price * Decimal("0.95")
        lines.append(
            f"{(start + timedelta(days=i)).strftime('%Y-%m-%dT%H:%M:%S+00:00')},"
            f"{close_price},{high},{low},{close_price},1000"
        )
        close_price = close_price * (Decimal("1") + daily_return)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.fixture
def fixtures(tmp_path: Path) -> dict[str, Path]:
    btc = tmp_path / "BTCUSDT.csv"
    eth = tmp_path / "ETHUSDT.csv"
    sol = tmp_path / "SOLUSDT.csv"
    laggard = tmp_path / "LMTUSDT.csv"
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    _make_csv(btc, "BTC/USDT", 45, start, Decimal("50000"), Decimal("0.001"))
    _make_csv(eth, "ETH/USDT", 45, start, Decimal("3000"), Decimal("0.0015"))
    _make_csv(sol, "SOL/USDT", 45, start, Decimal("20"), Decimal("0.02"))
    _make_csv(laggard, "LMT/USDT", 45, start, Decimal("100"), Decimal("-0.015"))
    return {"btc": btc, "eth": eth, "sol": sol, "laggard": laggard}


class TestCsvToDiscovery:
    def test_full_pipeline_with_eth(self, fixtures: dict[str, Path], tmp_path: Path) -> None:
        bundle = build_research_market_data_bundle(
            candidate_specs=[
                MarketDataFileSpec(path=fixtures["sol"], expected_symbol="SOLUSDT"),
                MarketDataFileSpec(path=fixtures["laggard"], expected_symbol="LMTUSDT"),
            ],
            btc_spec=MarketDataFileSpec(path=fixtures["btc"], expected_symbol="BTCUSDT"),
            eth_spec=MarketDataFileSpec(path=fixtures["eth"], expected_symbol="ETHUSDT"),
            generated_at=datetime(2024, 3, 1, tzinfo=timezone.utc),
        )

        json_path = tmp_path / "bundle.json"
        md_path = tmp_path / "bundle.md"
        write_research_market_data_bundle(bundle, json_path=json_path, markdown_path=md_path)
        assert json_path.exists()
        assert md_path.exists()

        rs_inputs = build_relative_strength_run_inputs(bundle)
        rs_report = build_relative_strength_report(
            universe=rs_inputs.candidates,
            btc_benchmark=rs_inputs.btc,
            eth_benchmark=rs_inputs.eth,
            report_id="mvp63-integration",
            generated_at=datetime(2024, 3, 1, tzinfo=timezone.utc),
            metadata={"test": "true"},
        )
        assert any(score.symbol == "SOL/USDT" for score in rs_report.scores)
        assert all(score.data_quality.min_required_rows_met for score in rs_report.scores)

        discovery_bundle = build_discovery_input_bundle(rs_report)
        discovery_report = build_discovery_report(
            inputs=discovery_bundle.inputs,
            config=DiscoveryConfig(
                require_relative_strength=True,
                require_open_interest=False,
                block_on_missing_context=False,
            ),
            report_id="mvp63-discovery",
            generated_at=datetime(2024, 3, 1, tzinfo=timezone.utc),
        )
        assert discovery_report.safety_flags.no_network_connection is True
        assert discovery_report.safety_flags.no_file_read_in_engine is True
        assert all(c.open_interest is None for c in discovery_report.candidates)
        sol_candidate = next(c for c in discovery_report.candidates if c.pair == "SOL/USDT")
        assert sol_candidate.relative_strength is not None
        assert sol_candidate.relative_strength.state == "ready"

    def test_btc_only_mode(self, fixtures: dict[str, Path], tmp_path: Path) -> None:
        bundle = build_research_market_data_bundle(
            candidate_specs=[MarketDataFileSpec(path=fixtures["sol"], expected_symbol="SOLUSDT")],
            btc_spec=MarketDataFileSpec(path=fixtures["btc"], expected_symbol="BTCUSDT"),
            generated_at=datetime(2024, 3, 1, tzinfo=timezone.utc),
        )
        assert bundle.eth_series is None

        rs_inputs = build_relative_strength_run_inputs(bundle)
        rs_report = build_relative_strength_report(
            universe=rs_inputs.candidates,
            btc_benchmark=rs_inputs.btc,
            eth_benchmark=None,
            report_id="mvp63-btc-only",
            generated_at=datetime(2024, 3, 1, tzinfo=timezone.utc),
        )
        assert rs_report.scores[0].state.value == "ready"

        discovery_bundle = build_discovery_input_bundle(rs_report)
        discovery_report = build_discovery_report(
            inputs=discovery_bundle.inputs,
            config=DiscoveryConfig(
                require_relative_strength=True,
                require_open_interest=False,
                block_on_missing_context=False,
            ),
            report_id="mvp63-discovery-btc-only",
            generated_at=datetime(2024, 3, 1, tzinfo=timezone.utc),
        )
        assert discovery_report.candidates[0].pair == "SOL/USDT"
        assert discovery_report.candidates[0].open_interest is None

    def test_safety_invariants(self, fixtures: dict[str, Path]) -> None:
        bundle = build_research_market_data_bundle(
            candidate_specs=[MarketDataFileSpec(path=fixtures["sol"], expected_symbol="SOLUSDT")],
            btc_spec=MarketDataFileSpec(path=fixtures["btc"], expected_symbol="BTCUSDT"),
            generated_at=datetime(2024, 3, 1, tzinfo=timezone.utc),
        )
        assert bundle.safety_flags.research_only is True
        assert bundle.safety_flags.execution_approval_granted is False
        assert bundle.safety_flags.production_approval_granted is False
        assert bundle.safety_flags.live_trading_allowed is False
        assert bundle.safety_flags.automatic_execution_allowed is False

        rs_inputs = build_relative_strength_run_inputs(bundle)
        rs_report = build_relative_strength_report(
            universe=rs_inputs.candidates,
            btc_benchmark=rs_inputs.btc,
            eth_benchmark=None,
            report_id="mvp63-safety",
            generated_at=datetime(2024, 3, 1, tzinfo=timezone.utc),
        )
        assert rs_report.safety_flags.output_is_human_research_only is True
        assert rs_report.safety_flags.live_trading_enabled is False

    def test_no_open_interest_synthesis(self, fixtures: dict[str, Path]) -> None:
        bundle = build_research_market_data_bundle(
            candidate_specs=[MarketDataFileSpec(path=fixtures["sol"], expected_symbol="SOLUSDT")],
            btc_spec=MarketDataFileSpec(path=fixtures["btc"], expected_symbol="BTCUSDT"),
            eth_spec=MarketDataFileSpec(path=fixtures["eth"], expected_symbol="ETHUSDT"),
            generated_at=datetime(2024, 3, 1, tzinfo=timezone.utc),
        )
        rs_inputs = build_relative_strength_run_inputs(bundle)
        rs_report = build_relative_strength_report(
            universe=rs_inputs.candidates,
            btc_benchmark=rs_inputs.btc,
            eth_benchmark=rs_inputs.eth,
            report_id="mvp63-no-oi",
            generated_at=datetime(2024, 3, 1, tzinfo=timezone.utc),
        )
        discovery_bundle = build_discovery_input_bundle(rs_report)
        assert all(inp.open_interest is None for inp in discovery_bundle.inputs)

    def test_no_default_data_or_reports_input(self, tmp_path: Path) -> None:
        # This test does not create any files under data/ or reports/ and only
        # exercises the public engine with temporary fixtures.
        btc = tmp_path / "BTCUSDT.csv"
        sol = tmp_path / "SOLUSDT.csv"
        _make_csv(btc, "BTC/USDT", 35, datetime(2024, 1, 1, tzinfo=timezone.utc), Decimal("50000"), Decimal("0.001"))
        _make_csv(sol, "SOL/USDT", 35, datetime(2024, 1, 1, tzinfo=timezone.utc), Decimal("20"), Decimal("0.01"))
        bundle = build_research_market_data_bundle(
            candidate_specs=[MarketDataFileSpec(path=sol, expected_symbol="SOLUSDT")],
            btc_spec=MarketDataFileSpec(path=btc, expected_symbol="BTCUSDT"),
            generated_at=datetime(2024, 3, 1, tzinfo=timezone.utc),
        )
        assert bundle.candidates[0].pair == "SOL/USDT"
