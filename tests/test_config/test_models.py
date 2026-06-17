import pytest

from hunter.config.models import (
    CollectionConfig,
    HunterConfig,
    LoggingConfig,
    StorageConfig,
    TradingConfig,
)


class TestTradingConfigDefaults:
    """TradingConfig must have safe defaults."""

    def test_trading_disabled_by_default(self):
        config = TradingConfig()
        assert config.enabled is False

    def test_live_trading_disabled_by_default(self):
        config = TradingConfig()
        assert config.live_enabled is False

    def test_dry_run_enabled_by_default(self):
        config = TradingConfig()
        assert config.dry_run is True

    def test_exchange_none_by_default(self):
        config = TradingConfig()
        assert config.exchange is None

    def test_max_position_size_zero_by_default(self):
        config = TradingConfig()
        assert config.max_position_size == 0.0


class TestCollectionConfigDefaults:
    """CollectionConfig must be disabled in MVP-1."""

    def test_collection_disabled_by_default(self):
        config = CollectionConfig()
        assert config.enabled is False

    def test_default_symbols(self):
        config = CollectionConfig()
        assert config.symbols == ["BTCUSDT", "ETHUSDT"]

    def test_default_timeframes(self):
        config = CollectionConfig()
        assert config.timeframes == ["1h", "4h", "1d"]


class TestStorageConfigDefaults:
    """StorageConfig defaults to SQLite."""

    def test_backend_sqlite_by_default(self):
        config = StorageConfig()
        assert config.backend == "sqlite"

    def test_default_path(self):
        config = StorageConfig()
        assert config.path == "data/hunter.db"


class TestLoggingConfigDefaults:
    """LoggingConfig has safe defaults."""

    def test_level_info_by_default(self):
        config = LoggingConfig()
        assert config.level == "INFO"

    def test_format_text_by_default(self):
        config = LoggingConfig()
        assert config.format == "text"


class TestHunterConfigDefaults:
    """HunterConfig aggregates all sub-configs with safe defaults."""

    def test_trading_disabled(self):
        config = HunterConfig()
        assert config.trading.enabled is False
        assert config.trading.live_enabled is False

    def test_collection_disabled(self):
        config = HunterConfig()
        assert config.collection.enabled is False

    def test_storage_backend_sqlite(self):
        config = HunterConfig()
        assert config.storage.backend == "sqlite"

    def test_logging_level_info(self):
        config = HunterConfig()
        assert config.logging.level == "INFO"

    def test_all_subconfigs_instantiated(self):
        config = HunterConfig()
        assert isinstance(config.trading, TradingConfig)
        assert isinstance(config.collection, CollectionConfig)
        assert isinstance(config.storage, StorageConfig)
        assert isinstance(config.logging, LoggingConfig)
