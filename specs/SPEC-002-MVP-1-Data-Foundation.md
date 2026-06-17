# SPEC-002 — MVP-1 Data Foundation

## Background

Hunter Futures Pro is an agent-first crypto futures research and execution-control platform. MVP-0 established the project foundation with documentation, agent memory files, and safety rules. MVP-1 builds the data foundation that all future engines will depend on.

## Goal

Design the data infrastructure without implementing trading logic, exchange connections, or live trading capabilities.

## Constraints

- No trading logic.
- No Binance connection yet (design only, no API calls).
- No Freqtrade integration yet.
- No API keys stored in the repository.
- No live trading enabled.
- All designs must be documented for future AI agents.

---

## 1. Python Project Structure

### Directory Layout

```
hunter-futures-pro/
├── .wrongstack/
│   └── AGENTS.md
├── docs/
│   ├── architecture/
│   ├── decisions/
│   ├── handoff/
│   └── operations/
├── specs/
├── tasks/
├── src/
│   ├── hunter/                    # Main package
│   │   ├── __init__.py           # Package init with __version__
│   │   ├── config/               # Configuration management
│   │   │   ├── __init__.py
│   │   │   ├── loader.py         # Config loading and validation
│   │   │   └── models.py         # Pydantic config schemas
│   │   ├── data/                 # Data collection and storage
│   │   │   ├── __init__.py
│   │   │   ├── collector.py      # Data collector interface
│   │   │   ├── storage.py        # SQLite storage layer
│   │   │   └── schema.py         # Database schema definitions
│   │   ├── core/                 # Core utilities
│   │   │   ├── __init__.py
│   │   │   ├── logging.py        # Structured logging setup
│   │   │   ├── exceptions.py     # Custom exceptions
│   │   │   └── cli.py            # CLI entry point
│   │   └── engines/              # Future analysis engines (MVP-2+)
│   │       ├── __init__.py
│   │       ├── regime.py         # Placeholder: Regime Engine
│   │       ├── breadth.py        # Placeholder: Market Breadth Engine
│   │       ├── strength.py       # Placeholder: Relative Strength Engine
│   │       ├── open_interest.py  # Placeholder: Open Interest Engine
│   │       └── gate.py           # Placeholder: Decision Gate Engine
├── tests/                        # Tests at repo root (standard pytest)
│   ├── __init__.py
│   ├── conftest.py              # Shared fixtures
│   ├── test_config/
│   ├── test_data/
│   └── test_core/
├── scripts/                      # Development and utility scripts
│   └── setup_db.py               # Database initialization
├── data/                         # Runtime data directory (gitignored)
│   ├── raw/                      # Raw collected data
│   ├── processed/                # Processed/transformed data
│   └── regime/                   # Regime output files (future)
├── config/                       # Configuration files
│   ├── default.yaml              # Default configuration
│   └── local.yaml                # Local overrides (gitignored)
├── logs/                         # Log output directory (gitignored)
├── pyproject.toml                # Python project metadata
├── requirements.txt              # Production dependencies
├── requirements-dev.txt          # Development dependencies
└── .gitignore                    # Git ignore rules (see below)
```

### .gitignore Specification

The repository must exclude runtime data, secrets, and local config:

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
*.egg-info/
dist/
build/

# Secrets and local config
config/local.yaml
.env
*.key
*.pem
*.secret

# Runtime data and logs
data/
logs/
*.db
*.sqlite
*.sqlite3

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db
```

### Package Design Principles

- `hunter` is the top-level package namespace.
- Each module has a clear responsibility boundary.
- Engines are placeholders in MVP-1 — they will be implemented in MVP-2+.
- Data layer is abstracted so the collector and storage can be tested independently.
- Configuration is environment-aware with safe defaults.

---

## 2. Config Structure

### Requirements

- Environment-aware (dev, test, prod — but prod trading is disabled by policy).
- Type-safe validation using Pydantic.
- No secrets in config files — secrets loaded from environment variables.
- Sensible defaults that are safe (dry-run, no live trading).
- Override hierarchy: defaults < config file < environment variables < CLI args.

### Config Files

**`config/default.yaml`** — Safe defaults, committed to repository:

```yaml
app:
  name: "Hunter Futures Pro"
  version: "0.2.0"
  env: "dev"
  log_level: "INFO"

trading:
  enabled: false           # Live trading disabled by default
  dry_run: true            # Always dry-run unless explicitly changed
  exchange: null           # No exchange connected in MVP-1
  max_position_size: 0.0   # Zero position size as safe default

data:
  storage_path: "data/hunter.db"
  raw_data_dir: "data/raw"
  processed_data_dir: "data/processed"
  default_timeframe: "1h"
  history_lookback_days: 90

collection:
  enabled: false           # Data collection disabled in MVP-1 (design only)
  exchange: "binance"
  market_type: "futures"
  rate_limit_requests_per_minute: 1200
  symbols:
    - "BTCUSDT"
    - "ETHUSDT"
  timeframes:
    - "1h"
    - "4h"
    - "1d"
```

**`config/local.yaml`** — Local overrides, gitignored:

```yaml
# Local overrides — never commit this file
# Copy from local.yaml.example and customize
```

**`config/local.yaml.example`** — Template showing safe overrides. **Never commit local.yaml:**

```yaml
# Example local configuration
# Copy to local.yaml and customize
# WARNING: local.yaml is gitignored. Never commit it.

app:
  log_level: "DEBUG"

trading:
  # NEVER set enabled: true without explicit human approval
  enabled: false
  dry_run: true
```

### Pydantic Models

```python
# src/hunter/config/models.py
from pydantic import BaseModel, Field
from typing import Literal, List

class AppConfig(BaseModel):
    name: str = "Hunter Futures Pro"
    version: str = "0.2.0"
    env: Literal["dev", "test", "prod"] = "dev"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

class TradingConfig(BaseModel):
    enabled: bool = False          # Safe default: disabled
    dry_run: bool = True           # Safe default: dry-run
    exchange: str | None = None
    max_position_size: float = 0.0

class DataConfig(BaseModel):
    storage_path: str = "data/hunter.db"
    raw_data_dir: str = "data/raw"
    processed_data_dir: str = "data/processed"
    default_timeframe: str = "1h"
    history_lookback_days: int = 90

class CollectionConfig(BaseModel):
    enabled: bool = False          # Safe default: disabled in MVP-1
    exchange: str = "binance"
    market_type: Literal["futures", "spot"] = "futures"
    rate_limit_requests_per_minute: int = 1200
    symbols: List[str] = Field(default_factory=lambda: ["BTCUSDT", "ETHUSDT"])
    timeframes: List[str] = Field(default_factory=lambda: ["1h", "4h", "1d"])

class HunterConfig(BaseModel):
    app: AppConfig = Field(default_factory=AppConfig)
    trading: TradingConfig = Field(default_factory=TradingConfig)
    data: DataConfig = Field(default_factory=DataConfig)
    collection: CollectionConfig = Field(default_factory=CollectionConfig)
```

### Config Loader

```python
# src/hunter/config/loader.py
import os
import yaml
from pathlib import Path
from .models import HunterConfig

CONFIG_DIR = Path("config")

class ConfigLoadError(Exception):
    pass

def validate_config(config: HunterConfig) -> None:
    """Validate config safety constraints. Raises ConfigLoadError if unsafe."""
    if config.trading.enabled:
        raise ConfigLoadError(
            "Trading is not allowed in MVP-1. "
            "Set trading.enabled to false or wait for a future MVP."
        )

def load_config(config_path: str | None = None) -> HunterConfig:
    """Load configuration with safe override hierarchy."""
    # Start with defaults (Pydantic defaults)
    config = HunterConfig()
    
    # Load default.yaml if exists
    default_path = CONFIG_DIR / "default.yaml"
    if default_path.exists():
        with open(default_path) as f:
            default_data = yaml.safe_load(f)
        config = HunterConfig(**default_data)
    
    # Load local.yaml if exists (gitignored, local overrides)
    local_path = CONFIG_DIR / "local.yaml"
    if local_path.exists():
        with open(local_path) as f:
            local_data = yaml.safe_load(f)
        # Merge local overrides using Pydantic model_copy for safe nested updates
        config = config.model_copy(update=local_data)
    
    # Override from environment variables
    if env_config := os.getenv("HUNTER_CONFIG"):
        env_data = yaml.safe_load(env_config)
        config = config.model_copy(update=env_data)
    
    # Safety validation
    validate_config(config)
    
    return config
```

---

## 3. Logging Structure

### Requirements

- Structured JSON logging for machine parsing.
- Human-readable format for development.
- Log rotation to prevent disk fill.
- No secrets or API keys in logs.
- Correlation IDs for tracing requests across components.

### Log Levels

| Level | Usage |
|-------|-------|
| DEBUG | Development detail, data inspection |
| INFO | Normal operation, data collection events |
| WARNING | Recoverable issues, stale data warnings |
| ERROR | Failures that need attention |
| CRITICAL | Safety violations, unauthorized trading attempts |

### Log Format

**Development (console):**
```
2026-06-17 14:32:10 [INFO] hunter.data.collector: Fetching BTCUSDT 1h klines
```

**Production (JSON):**
```json
{
  "timestamp": "2026-06-17T14:32:10.123Z",
  "level": "INFO",
  "logger": "hunter.data.collector",
  "message": "Fetching BTCUSDT 1h klines",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "context": {
    "symbol": "BTCUSDT",
    "timeframe": "1h",
    "request_id": "req-123"
  }
}
```

### Implementation

```python
# src/hunter/core/logging.py
import logging
import json
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict

class JSONFormatter(logging.Formatter):
    """JSON log formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add correlation ID if available
        if hasattr(record, "correlation_id"):
            log_data["correlation_id"] = record.correlation_id
        
        # Add extra context if available
        if hasattr(record, "context"):
            log_data["context"] = record.context
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data)

class RedactingFilter(logging.Filter):
    """Filter that redacts sensitive values from log records."""
    
    SENSITIVE_KEYS = {"api_key", "secret", "password", "token", "private_key"}
    
    def filter(self, record: logging.LogRecord) -> bool:
        # Redact sensitive keys from any dict context
        if hasattr(record, "context") and isinstance(record.context, dict):
            record.context = {
                k: "[REDACTED]" if k.lower() in self.SENSITIVE_KEYS else v
                for k, v in record.context.items()
            }
        return True

def setup_logging(
    log_level: str = "INFO",
    log_dir: str = "logs",
    json_format: bool = False,
) -> None:
    """Configure structured logging."""
    from logging.handlers import RotatingFileHandler
    
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    
    handlers: list[logging.Handler] = []
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    if json_format:
        console_handler.setFormatter(JSONFormatter())
    else:
        console_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
            )
        )
    handlers.append(console_handler)
    
    # File handler with rotation
    file_handler = RotatingFileHandler(
        f"{log_dir}/hunter.log",
        maxBytes=10_000_000,  # 10MB
        backupCount=5,
    )
    file_handler.setFormatter(JSONFormatter())
    file_handler.addFilter(RedactingFilter())
    handlers.append(file_handler)
    
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        handlers=handlers,
        force=True,
    )
```

### Data Storage Layer Interface

The storage layer is abstracted for testability and future backend swaps:

```python
# src/hunter/data/storage.py
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional
from .collector import KlineData, FundingRateData

class DataStorage(ABC):
    """Abstract base class for data storage backends."""
    
    @abstractmethod
    def save_klines(self, klines: List[KlineData]) -> int:
        """Save klines. Returns number of records inserted."""
        pass
    
    @abstractmethod
    def get_klines(
        self,
        symbol: str,
        timeframe: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000,
    ) -> List[KlineData]:
        """Retrieve klines for a symbol and timeframe."""
        pass
    
    @abstractmethod
    def get_latest_kline(self, symbol: str, timeframe: str) -> Optional[KlineData]:
        """Get the most recent kline for a symbol and timeframe."""
        pass
    
    @abstractmethod
    def save_funding_rates(self, rates: List[FundingRateData]) -> int:
        """Save funding rates. Returns number of records inserted."""
        pass
    
    @abstractmethod
    def get_funding_rates(
        self,
        symbol: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000,
    ) -> List[FundingRateData]:
        """Retrieve funding rates for a symbol."""
        pass
    
    @abstractmethod
    def get_collection_metadata(self, symbol: str, data_type: str) -> Optional[dict]:
        """Get metadata for a symbol and data type."""
        pass
    
    @abstractmethod
    def update_collection_metadata(self, symbol: str, data_type: str, **kwargs) -> None:
        """Update metadata for a symbol and data type."""
        pass
    
    @abstractmethod
    def is_data_fresh(self, symbol: str, data_type: str, max_age_seconds: int = 3600) -> bool:
        """Check if data is fresh (within max_age_seconds)."""
        pass

class SQLiteStorage(DataStorage):
    """SQLite implementation of DataStorage."""
    
    def __init__(self, db_path: str = "data/hunter.db"):
        self.db_path = db_path
        self._init_schema()
    
    def _init_schema(self) -> None:
        """Initialize database schema from schema.py."""
        # Implementation loads schema.sql and executes
        pass
    
    # ... implementations of all abstract methods ...
```

---

## 4. Binance Futures Data Collector Plan

### Design Only — No Connection in MVP-1

This section defines the collector interface and planned data flow. The actual Binance API connection will be implemented in a future MVP.

### Collector Interface

```python
# src/hunter/data/collector.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

@dataclass
class KlineData:
    """OHLCV kline data structure."""
    symbol: str
    timeframe: str
    open_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float
    trades: int
    taker_buy_base_volume: float
    taker_buy_quote_volume: float

@dataclass
class FundingRateData:
    """Funding rate data structure."""
    symbol: str
    funding_time: datetime
    funding_rate: float
    mark_price: float

class DataCollector(ABC):
    """Abstract base class for data collectors."""
    
    @abstractmethod
    def fetch_klines(
        self,
        symbol: str,
        timeframe: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000,
    ) -> List[KlineData]:
        """Fetch OHLCV klines for a symbol."""
        pass
    
    @abstractmethod
    def fetch_funding_rates(
        self,
        symbol: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000,
    ) -> List[FundingRateData]:
        """Fetch funding rates for a symbol."""
        pass
    
    @abstractmethod
    def fetch_open_interest(
        self,
        symbol: str,
        timeframe: str = "1h",
    ) -> float:
        """Fetch current open interest for a symbol."""
        pass
    
    @abstractmethod
    def get_available_symbols(self) -> List[str]:
        """Get list of available futures symbols."""
        pass

class BinanceFuturesCollector(DataCollector):
    """Binance Futures data collector — NOT IMPLEMENTED in MVP-1."""
    
    def __init__(self, api_key: str | None = None, api_secret: str | None = None):
        # Store API credentials securely (not in config files)
        self._api_key = api_key
        self._api_secret = api_secret
        self._client = None  # Will be initialized in future MVP
    
    def fetch_klines(self, symbol, timeframe, start_time=None, end_time=None, limit=1000):
        raise NotImplementedError("Binance connection not available in MVP-1")
    
    def fetch_funding_rates(self, symbol, start_time=None, end_time=None, limit=1000):
        raise NotImplementedError("Binance connection not available in MVP-1")
    
    def fetch_open_interest(self, symbol, timeframe="1h"):
        raise NotImplementedError("Binance connection not available in MVP-1")
    
    def get_available_symbols(self):
        raise NotImplementedError("Binance connection not available in MVP-1")
```

### Data Flow Design

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Binance API    │────▶│  Data Collector │────▶│  Validation     │
│  (Future MVP)   │     │  (Interface)    │     │  Layer          │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                        │
                                                        ▼
                                               ┌─────────────────┐
                                               │  SQLite Storage │
                                               │  (hunter.db)    │
                                               └─────────────────┘
                                                        │
                                                        ▼
                                               ┌─────────────────┐
                                               │  Analysis       │
                                               │  Engines        │
                                               │  (MVP-2+)       │
                                               └─────────────────┘
```

### Data Types to Collect (Future)

| Data Type | Source | Frequency | Storage |
|-----------|--------|-----------|---------|
| OHLCV Klines | Binance Futures | Per timeframe | SQLite + Parquet |
| Funding Rates | Binance Futures | Every 8 hours | SQLite |
| Open Interest | Binance Futures | Hourly | SQLite |
| Long/Short Ratio | Binance Futures | Hourly | SQLite |
| Liquidation Data | Binance Futures | Real-time | SQLite (recent) |

---

## 5. SQLite Schema Plan

### Database Design

Single SQLite database: `data/hunter.db`

Tables:

```sql
-- Market data: OHLCV klines
CREATE TABLE klines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    open_time INTEGER NOT NULL,  -- Unix timestamp in milliseconds
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume REAL NOT NULL,
    quote_volume REAL NOT NULL,
    trades INTEGER NOT NULL,
    taker_buy_base_volume REAL NOT NULL,
    taker_buy_quote_volume REAL NOT NULL,
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now') * 1000),
    UNIQUE(symbol, timeframe, open_time)
);

CREATE INDEX idx_klines_symbol_timeframe ON klines(symbol, timeframe, open_time);

-- Funding rates
CREATE TABLE funding_rates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    funding_time INTEGER NOT NULL,
    funding_rate REAL NOT NULL,
    mark_price REAL,
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now') * 1000),
    UNIQUE(symbol, funding_time)
);

CREATE INDEX idx_funding_symbol_time ON funding_rates(symbol, funding_time);

-- Open interest snapshots
CREATE TABLE open_interest (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    open_interest REAL NOT NULL,
    open_interest_value REAL,  -- In quote asset
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now') * 1000),
    UNIQUE(symbol, timestamp)
);

CREATE INDEX idx_oi_symbol_time ON open_interest(symbol, timestamp);

-- Long/short ratio
CREATE TABLE long_short_ratio (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timestamp INTEGER NOT NULL,
    long_account_ratio REAL NOT NULL,
    short_account_ratio REAL NOT NULL,
    long_short_ratio REAL NOT NULL,
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now') * 1000),
    UNIQUE(symbol, timestamp)
);

CREATE INDEX idx_ls_ratio_symbol_time ON long_short_ratio(symbol, timestamp);

-- System state / regime snapshots (MVP-2+)
CREATE TABLE regime_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    regime TEXT NOT NULL,  -- e.g., 'bullish', 'bearish', 'neutral', 'unknown'
    confidence REAL NOT NULL,
    indicators TEXT,  -- JSON blob of indicator values
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now') * 1000)
);

-- Decision log (MVP-4+)
CREATE TABLE decision_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp INTEGER NOT NULL,
    symbol TEXT,
    decision TEXT NOT NULL,  -- 'allow', 'block', 'hold'
    reason TEXT NOT NULL,
    score REAL,
    regime TEXT,
    metadata TEXT,  -- JSON blob
    created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now') * 1000)
);

CREATE INDEX idx_decisions_timestamp ON decision_log(timestamp);

-- Data collection metadata
CREATE TABLE collection_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    data_type TEXT NOT NULL,  -- 'klines', 'funding', 'open_interest', etc.
    last_collection_time INTEGER,
    last_record_time INTEGER,
    record_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'active',  -- 'active', 'paused', 'error'
    error_message TEXT,
    updated_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now') * 1000),
    UNIQUE(symbol, data_type)
);
```

### Schema Design Principles

- Timestamps stored as Unix milliseconds for consistency with Binance API.
- `UNIQUE` constraints prevent duplicate data.
- Indexes on common query patterns (symbol + time).
- JSON blobs for flexible indicator/metadata storage.
- `created_at` for audit trail.
- `collection_metadata` table tracks data freshness for stale data checks.

---

## 6. Test Structure

### Framework

- **pytest** as the test runner.
- **pytest-asyncio** for async test support.
- **factory-boy** or custom factories for test data generation.
- **tmp_path** fixture for temporary database files.

### Directory Structure

```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures and configuration
├── test_config/
│   ├── __init__.py
│   ├── test_loader.py       # Config loading tests
│   └── test_models.py       # Pydantic model validation tests
├── test_data/
│   ├── __init__.py
│   ├── test_storage.py      # SQLite storage tests
│   ├── test_schema.py       # Schema validation tests
│   └── test_collector.py    # Collector interface tests (mocked)
├── test_core/
│   ├── __init__.py
│   ├── test_logging.py      # Logging setup and redaction tests
│   └── test_exceptions.py   # Exception handling tests
└── fixtures/
    ├── __init__.py
    ├── sample_config.yaml   # Sample config for tests
    └── sample_klines.csv    # Sample kline data for tests
```

### Key Test Patterns

```python
# src/tests/conftest.py
import pytest
from pathlib import Path
from hunter.config.models import HunterConfig
from hunter.config.loader import load_config

@pytest.fixture
def temp_db(tmp_path):
    """Create a temporary database path."""
    return tmp_path / "test.db"

@pytest.fixture
def sample_config():
    """Create a sample configuration for testing."""
    return HunterConfig(
        app={"name": "Test Hunter", "env": "test"},
        trading={"enabled": False, "dry_run": True},
        data={"storage_path": ":memory:"},
    )

@pytest.fixture
def mock_collector():
    """Create a mock data collector for testing."""
    from unittest.mock import MagicMock
    collector = MagicMock()
    collector.fetch_klines.return_value = []
    collector.get_available_symbols.return_value = ["BTCUSDT", "ETHUSDT"]
    return collector
```

### Safety Tests (Critical)

```python
# src/tests/test_config/test_safety.py
import pytest
from hunter.config.loader import load_config, ConfigLoadError
from hunter.config.models import HunterConfig

def test_trading_enabled_raises_error():
    """Trading must not be enabled in MVP-1."""
    config = HunterConfig()
    config.trading.enabled = True
    
    with pytest.raises(ConfigLoadError, match="Trading is not allowed"):
        validate_config(config)

def test_default_config_is_safe():
    """Default config must have trading disabled."""
    config = HunterConfig()
    assert config.trading.enabled is False
    assert config.trading.dry_run is True
    assert config.collection.enabled is False
```

---

## Dependencies

### Production Dependencies

```
pydantic>=2.0.0
pyyaml>=6.0
```

### Development Dependencies

```
pytest>=7.0.0
pytest-asyncio>=0.21.0
factory-boy>=3.3.0
```

### pyproject.toml Metadata

```toml
[project]
name = "hunter-futures-pro"
version = "0.2.0"
description = "Agent-first crypto futures research and execution-control platform"
requires-python = ">=3.11"
dependencies = [
    "pydantic>=2.0.0",
    "pyyaml>=6.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "factory-boy>=3.3.0",
]

[project.scripts]
hunter = "hunter.core.cli:main"
```

---

## CLI Entry Point

```python
# src/hunter/core/cli.py
import argparse
import sys
from pathlib import Path

from ..config.loader import load_config, ConfigLoadError
from ..core.logging import setup_logging

def main() -> int:
    """Main CLI entry point for Hunter Futures Pro."""
    parser = argparse.ArgumentParser(description="Hunter Futures Pro")
    parser.add_argument(
        "--config", "-c",
        type=str,
        help="Path to config file (overrides default)"
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level"
    )
    parser.add_argument(
        "--json-logs",
        action="store_true",
        help="Output logs in JSON format"
    )
    
    args = parser.parse_args()
    
    try:
        config = load_config(args.config)
    except ConfigLoadError as e:
        print(f"Config error: {e}", file=sys.stderr)
        return 1
    
    setup_logging(
        log_level=args.log_level,
        log_dir=config.data.raw_data_dir.replace("raw", "logs"),
        json_format=args.json_logs,
    )
    
    print(f"Hunter Futures Pro {config.app.version}")
    print(f"Environment: {config.app.env}")
    print(f"Trading enabled: {config.trading.enabled}")
    print(f"Data collection enabled: {config.collection.enabled}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

---

## Package Version Export

```python
# src/hunter/__init__.py
"""Hunter Futures Pro - Agent-first crypto futures research platform."""

__version__ = "0.2.0"
```

---

## Safety Checklist

| Item | Status | Notes |
|------|--------|-------|
| Trading disabled by default | ✅ | `trading.enabled: false` in default config |
| Dry-run by default | ✅ | `trading.dry_run: true` |
| No API keys in repository | ✅ | Secrets loaded from env vars only |
| Collection disabled in MVP-1 | ✅ | `collection.enabled: false` |
| Config validation blocks trading | ✅ | `ConfigLoadError` if `trading.enabled` is true |
| Log redaction for secrets | ✅ | `RedactingFilter` removes sensitive keys |
| No live trading in any config | ✅ | All configs default to disabled |
| SQLite schema has no trading execution tables | ✅ | Only data storage and decision logging |

---

## Next Steps

1. Implement Python project structure (create directories and `__init__.py` files).
2. Implement config loader and Pydantic models.
3. Implement logging setup with redaction.
4. Implement SQLite schema and storage layer.
5. Implement collector interface with mock/test implementation.
6. Write tests for all components.
7. Update `docs/handoff/CURRENT_STATE.md` when MVP-1 implementation begins.

---

## Version

0.2.0-dev (MVP-1 Design)
