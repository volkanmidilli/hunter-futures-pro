from pydantic import BaseModel, Field
from typing import Literal, List


class TradingConfig(BaseModel):
    """Trading configuration with safe defaults."""

    enabled: bool = False
    live_enabled: bool = False
    dry_run: bool = True
    exchange: str | None = None
    max_position_size: float = 0.0


class CollectionConfig(BaseModel):
    """Data collection configuration."""

    enabled: bool = False
    exchange: str = "binance"
    market_type: Literal["futures", "spot"] = "futures"
    rate_limit_requests_per_minute: int = 1200
    symbols: List[str] = Field(default_factory=lambda: ["BTCUSDT", "ETHUSDT"])
    timeframes: List[str] = Field(default_factory=lambda: ["1h", "4h", "1d"])


class StorageConfig(BaseModel):
    """Storage backend configuration."""

    backend: Literal["sqlite", "parquet"] = "sqlite"
    path: str = "data/hunter.db"
    raw_data_dir: str = "data/raw"
    processed_data_dir: str = "data/processed"


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    format: Literal["json", "text"] = "text"
    log_dir: str = "logs"


class HunterConfig(BaseModel):
    """Top-level configuration for Hunter Futures Pro."""

    trading: TradingConfig = Field(default_factory=TradingConfig)
    collection: CollectionConfig = Field(default_factory=CollectionConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
