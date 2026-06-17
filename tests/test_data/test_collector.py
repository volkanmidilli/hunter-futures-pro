"""Tests for the data collector interface."""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from hunter.data.collector import (
    DataCollector,
    BinanceFuturesCollector,
    KlineData,
    FundingRateData,
    OpenInterestData,
    MarkPriceData,
    Ticker24hData,
)


class TestDataCollectorAbstract:
    """Confirm DataCollector is abstract and cannot be used directly."""

    def test_cannot_instantiate_directly(self):
        """DataCollector is abstract — direct instantiation must fail."""
        with pytest.raises(TypeError):
            DataCollector()

    def test_subclass_must_implement_all_methods(self):
        """A partial subclass must also fail to instantiate."""

        class PartialCollector(DataCollector):
            def get_exchange_info(self):
                return {}

        with pytest.raises(TypeError):
            PartialCollector()


class TestBinanceFuturesCollector:
    """Confirm BinanceFuturesCollector is a skeleton that raises NotImplementedError."""

    def test_exists_and_is_instantiable(self):
        """BinanceFuturesCollector can be instantiated."""
        collector = BinanceFuturesCollector()
        assert isinstance(collector, DataCollector)

    def test_get_exchange_info_raises(self):
        collector = BinanceFuturesCollector()
        with pytest.raises(NotImplementedError):
            collector.get_exchange_info()

    def test_get_klines_raises(self):
        collector = BinanceFuturesCollector()
        with pytest.raises(NotImplementedError):
            collector.get_klines("BTCUSDT", "1h")

    def test_get_funding_rates_raises(self):
        collector = BinanceFuturesCollector()
        with pytest.raises(NotImplementedError):
            collector.get_funding_rates("BTCUSDT")

    def test_get_open_interest_raises(self):
        collector = BinanceFuturesCollector()
        with pytest.raises(NotImplementedError):
            collector.get_open_interest("BTCUSDT")

    def test_get_mark_price_raises(self):
        collector = BinanceFuturesCollector()
        with pytest.raises(NotImplementedError):
            collector.get_mark_price("BTCUSDT")

    def test_get_24h_ticker_raises(self):
        collector = BinanceFuturesCollector()
        with pytest.raises(NotImplementedError):
            collector.get_24h_ticker()

    def test_get_24h_ticker_with_symbol_raises(self):
        collector = BinanceFuturesCollector()
        with pytest.raises(NotImplementedError):
            collector.get_24h_ticker("BTCUSDT")

    def test_no_network_calls(self, monkeypatch):
        """Confirm no HTTP requests are made by any method."""
        import urllib.request

        original_urlopen = urllib.request.urlopen
        calls = []

        def fake_urlopen(*args, **kwargs):
            calls.append(args)
            raise RuntimeError("Network call detected")

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

        collector = BinanceFuturesCollector()
        methods = [
            lambda: collector.get_exchange_info(),
            lambda: collector.get_klines("BTCUSDT", "1h"),
            lambda: collector.get_funding_rates("BTCUSDT"),
            lambda: collector.get_open_interest("BTCUSDT"),
            lambda: collector.get_mark_price("BTCUSDT"),
            lambda: collector.get_24h_ticker(),
            lambda: collector.get_24h_ticker("BTCUSDT"),
        ]

        for method in methods:
            with pytest.raises(NotImplementedError):
                method()

        assert calls == [], f"Unexpected network calls: {calls}"


class TestDataModels:
    """Confirm data models are immutable and well-formed."""

    def test_kline_data_immutable(self):
        now = datetime.now(timezone.utc)
        kline = KlineData(
            symbol="BTCUSDT",
            timeframe="1h",
            open_time=now,
            close_time=now,
            open=100.0,
            high=110.0,
            low=95.0,
            close=105.0,
            volume=1000.0,
            quote_volume=100000.0,
            trades=500,
            taker_buy_base=600.0,
            taker_buy_quote=60000.0,
        )
        assert kline.symbol == "BTCUSDT"
        with pytest.raises(AttributeError):
            kline.symbol = "ETHUSDT"

    def test_funding_rate_data_immutable(self):
        now = datetime.now(timezone.utc)
        fr = FundingRateData(
            symbol="BTCUSDT",
            funding_time=now,
            funding_rate=0.0001,
            mark_price=50000.0,
        )
        with pytest.raises(AttributeError):
            fr.funding_rate = 0.0002

    def test_open_interest_data_immutable(self):
        now = datetime.now(timezone.utc)
        oi = OpenInterestData(
            symbol="BTCUSDT",
            timestamp=now,
            open_interest=10000.0,
            open_interest_value=500000000.0,
        )
        with pytest.raises(AttributeError):
            oi.open_interest = 20000.0

    def test_mark_price_data_immutable(self):
        now = datetime.now(timezone.utc)
        mp = MarkPriceData(
            symbol="BTCUSDT",
            timestamp=now,
            mark_price=50000.0,
            index_price=49900.0,
            estimated_settle_price=50100.0,
            funding_rate=0.0001,
            next_funding_time=now,
        )
        with pytest.raises(AttributeError):
            mp.mark_price = 51000.0

    def test_ticker_24h_data_immutable(self):
        now = datetime.now(timezone.utc)
        ticker = Ticker24hData(
            symbol="BTCUSDT",
            price_change=100.0,
            price_change_percent=0.2,
            weighted_avg_price=50000.0,
            last_price=50100.0,
            last_quantity=1.0,
            open_price=50000.0,
            high_price=51000.0,
            low_price=49000.0,
            volume=10000.0,
            quote_volume=500000000.0,
            open_time=now,
            close_time=now,
            first_trade_id=1,
            last_trade_id=1000,
            trade_count=1000,
        )
        with pytest.raises(AttributeError):
            ticker.last_price = 50200.0
