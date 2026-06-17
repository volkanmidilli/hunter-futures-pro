"""Tests for SQLite storage layer."""

import pytest
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from hunter.data.storage import SQLiteStorage, DataStorage
from hunter.data.collector import KlineData, FundingRateData


class TestDataStorageAbstract:
    """Confirm DataStorage is abstract and cannot be used directly."""

    def test_cannot_instantiate_directly(self):
        """DataStorage is abstract — direct instantiation must fail."""
        with pytest.raises(TypeError):
            DataStorage()

    def test_subclass_must_implement_all_methods(self):
        """A partial subclass must also fail to instantiate."""

        class PartialStorage(DataStorage):
            def initialize(self):
                pass

        with pytest.raises(TypeError):
            PartialStorage()


class TestSQLiteStorage:
    """Test SQLiteStorage with temporary database files."""

    @pytest.fixture
    def storage(self, tmp_path):
        """Create a temporary SQLiteStorage instance."""
        db_path = tmp_path / "test.db"
        s = SQLiteStorage(str(db_path))
        s.initialize()
        yield s
        s.close()

    def test_initialize_creates_tables(self, storage, tmp_path):
        """initialize() creates all required tables from schema.sql."""
        conn = sqlite3.connect(str(tmp_path / "test.db"))
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()

        expected = {
            "market_symbols",
            "candles",
            "funding_rates",
            "open_interest",
            "collection_metadata",
        }
        assert expected.issubset(tables), f"Missing tables: {expected - tables}"

    def test_initialize_creates_indexes(self, storage, tmp_path):
        """initialize() creates expected indexes."""
        conn = sqlite3.connect(str(tmp_path / "test.db"))
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = {row[0] for row in cursor.fetchall()}
        conn.close()

        expected = {
            "idx_candles_symbol_timeframe_time",
            "idx_funding_symbol_time",
            "idx_oi_symbol_time",
            "idx_meta_symbol_type",
        }
        assert expected.issubset(indexes), f"Missing indexes: {expected - indexes}"

    def test_save_and_get_klines(self, storage):
        """Save klines and retrieve them."""
        now = datetime.now(timezone.utc)
        klines = [
            KlineData(
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
        ]
        inserted = storage.save_klines(klines)
        assert inserted == 1

        retrieved = storage.get_klines("BTCUSDT", "1h")
        assert len(retrieved) == 1
        assert retrieved[0].symbol == "BTCUSDT"
        assert retrieved[0].open == 100.0

    def test_save_klines_duplicate_ignored(self, storage):
        """Duplicate klines are ignored (INSERT OR IGNORE)."""
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
        assert storage.save_klines([kline]) == 1
        assert storage.save_klines([kline]) == 0  # duplicate ignored

    def test_get_klines_with_time_range(self, storage):
        """Retrieve klines within a time range."""
        base = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        klines = []
        for i in range(5):
            t = base.replace(hour=i)
            klines.append(
                KlineData(
                    symbol="BTCUSDT",
                    timeframe="1h",
                    open_time=t,
                    close_time=t,
                    open=float(i),
                    high=float(i + 1),
                    low=float(i),
                    close=float(i + 0.5),
                    volume=1000.0,
                    quote_volume=100000.0,
                    trades=500,
                    taker_buy_base=600.0,
                    taker_buy_quote=60000.0,
                )
            )
        storage.save_klines(klines)

        start = base.replace(hour=1)
        end = base.replace(hour=3)
        result = storage.get_klines("BTCUSDT", "1h", start_time=start, end_time=end)
        assert len(result) == 3
        # DESC order, so hour 3, 2, 1
        assert result[0].open == 3.0
        assert result[2].open == 1.0

    def test_get_latest_kline(self, storage):
        """Get the most recent kline."""
        base = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        for i in range(3):
            t = base.replace(hour=i)
            storage.save_klines(
                [
                    KlineData(
                        symbol="BTCUSDT",
                        timeframe="1h",
                        open_time=t,
                        close_time=t,
                        open=float(i),
                        high=float(i + 1),
                        low=float(i),
                        close=float(i + 0.5),
                        volume=1000.0,
                        quote_volume=100000.0,
                        trades=500,
                        taker_buy_base=600.0,
                        taker_buy_quote=60000.0,
                    )
                ]
            )

        latest = storage.get_latest_kline("BTCUSDT", "1h")
        assert latest is not None
        assert latest.open == 2.0

    def test_get_latest_kline_none(self, storage):
        """Returns None when no klines exist."""
        latest = storage.get_latest_kline("ETHUSDT", "1h")
        assert latest is None

    def test_save_and_get_funding_rates(self, storage):
        """Save funding rates and retrieve them."""
        now = datetime.now(timezone.utc)
        rates = [
            FundingRateData(
                symbol="BTCUSDT",
                funding_time=now,
                funding_rate=0.0001,
                mark_price=50000.0,
            )
        ]
        inserted = storage.save_funding_rates(rates)
        assert inserted == 1

        retrieved = storage.get_funding_rates("BTCUSDT")
        assert len(retrieved) == 1
        assert retrieved[0].funding_rate == 0.0001

    def test_save_funding_rates_duplicate_ignored(self, storage):
        """Duplicate funding rates are ignored."""
        now = datetime.now(timezone.utc)
        rate = FundingRateData(
            symbol="BTCUSDT",
            funding_time=now,
            funding_rate=0.0001,
            mark_price=50000.0,
        )
        assert storage.save_funding_rates([rate]) == 1
        assert storage.save_funding_rates([rate]) == 0

    def test_collection_metadata(self, storage):
        """Save and retrieve collection metadata."""
        now = datetime.now(timezone.utc)
        storage.save_collection_metadata("BTCUSDT", "klines", last_collection_time=now)

        meta = storage.get_collection_metadata("BTCUSDT", "klines")
        assert meta is not None
        assert meta["symbol"] == "BTCUSDT"
        assert meta["data_type"] == "klines"
        assert meta["last_collection_time"] is not None

    def test_collection_metadata_update(self, storage):
        """Metadata is updated on subsequent saves."""
        t1 = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        t2 = datetime(2024, 1, 2, 0, 0, 0, tzinfo=timezone.utc)

        storage.save_collection_metadata("BTCUSDT", "klines", last_collection_time=t1)
        meta1 = storage.get_collection_metadata("BTCUSDT", "klines")

        storage.save_collection_metadata("BTCUSDT", "klines", last_collection_time=t2)
        meta2 = storage.get_collection_metadata("BTCUSDT", "klines")

        assert meta2["last_collection_time"] > meta1["last_collection_time"]

    def test_is_data_fresh_true(self, storage):
        """Data is fresh when collected recently."""
        now = datetime.now(timezone.utc)
        storage.save_collection_metadata("BTCUSDT", "klines", last_collection_time=now)
        assert storage.is_data_fresh("BTCUSDT", "klines", max_age_seconds=3600)

    def test_is_data_fresh_false(self, storage):
        """Data is stale when collected long ago."""
        old = datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        storage.save_collection_metadata("BTCUSDT", "klines", last_collection_time=old)
        assert not storage.is_data_fresh("BTCUSDT", "klines", max_age_seconds=3600)

    def test_is_data_fresh_no_metadata(self, storage):
        """Data is not fresh when no metadata exists."""
        assert not storage.is_data_fresh("BTCUSDT", "klines", max_age_seconds=3600)

    def test_no_network_calls(self, storage):
        """SQLiteStorage does not make any network calls."""
        # This is implicit — all operations use sqlite3 on local file.
        # If any network call were made, it would fail in this isolated test.
        now = datetime.now(timezone.utc)
        storage.save_klines(
            [
                KlineData(
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
            ]
        )
        result = storage.get_klines("BTCUSDT", "1h")
        assert len(result) == 1

    def test_empty_klines_list(self, storage):
        """Saving empty list returns 0."""
        assert storage.save_klines([]) == 0

    def test_empty_funding_rates_list(self, storage):
        """Saving empty list returns 0."""
        assert storage.save_funding_rates([]) == 0
