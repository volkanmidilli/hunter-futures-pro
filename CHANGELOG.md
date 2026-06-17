# Changelog

All important project changes will be recorded in this file.

## 0.1.0 — MVP-0 Project Foundation

### Added

- Initial project README
- Initial PROJECT.md specification
- Main AGENTS.md instructions
- Current project state handoff file
- Task backlog file
- Active task file
- Agent log file

### Project Direction

- Hunter Futures Pro will be developed as an agent-first crypto futures research and execution-control platform.
- WrongStack will be used as the main CLI AI agent.
- Kimi K2.7 will be used as the preferred model/backend.
- Freqtrade will be used only as the execution layer.
- Hunter Futures Pro will be the decision layer.
- Old strategies are benchmarks only.

### Safety

- No trading logic exists yet.
- No Binance connection exists yet.
- No Freqtrade integration exists yet.
- No live trading is enabled.
- No API keys or exchange secrets should be stored in the repository.

### Next

- Review MVP-0 cleanup.
- Commit initial foundation.
- Plan MVP-1 Data Foundation.

## 0.2.0-dev — MVP-1 Data Foundation (In Progress)

### Added

- Python project structure: `src/hunter/` package with `config`, `data`, `core`, `engines` modules
- `pyproject.toml` with project metadata, `pydantic` and `pyyaml` dependencies
- `requirements.txt` and `requirements-dev.txt` with pytest dependencies
- `.gitignore` excluding Python cache, secrets, runtime data, and local config
- `tests/` directory at repo root with `test_config`, `test_data`, `test_core`, `fixtures`
- `__version__ = "0.2.0-dev"` in `src/hunter/__init__.py`

### MVP-1 Step 2 — Config Models and Validation (Complete)

- Pydantic config models: `TradingConfig`, `CollectionConfig`, `StorageConfig`, `LoggingConfig`, `HunterConfig`
- Config loader with safe override hierarchy (YAML file, env var)
- `validate_config()` with fail-closed validation:
  - Raises `ConfigLoadError` if `trading.enabled` is `true`
  - Raises `ConfigLoadError` if `trading.live_enabled` is `true`
  - Raises `ConfigLoadError` if secrets (`api_key`, `api_secret`, `secret_key`, `private_key`) detected
- Safe defaults: `trading.enabled: false`, `trading.live_enabled: false`, `collection.enabled: false`
- Config files: `configs/data.yaml` (safe defaults), `configs/local.example.yaml` (warnings)
- Config directory standard: `configs/` (not `config/`)
- Config tests: 23 tests for safe defaults, validation failures, and YAML loading

### MVP-1 Step 3 — Logging Structure (Complete)

- `src/hunter/core/logging.py` with structured logging components:
  - `JSONFormatter` for JSON log output with timestamp, level, logger, message, correlation_id, context, exception info
  - `RedactingFilter` for recursive secret redaction (api_key, secret, password, token, private_key) in dicts and lists
  - `setup_logging()` with console handler (text or JSON) and rotating file handler (always JSON, 10MB/5 backups)
- `tests/test_core/test_logging.py` with 18 tests for formatting, redaction, and setup behavior
- Log secret redaction applied to file handler only

### Safety

- No trading logic exists yet.
- No Binance connection exists yet.
- No Freqtrade integration exists yet.
- No live trading is enabled.
- No API keys or exchange secrets stored in repository.
- `.gitignore` prevents accidental commit of `configs/local.yaml`, `.env`, `*.key`, `*.pem`.
- Logging redacts secret-like fields from file output.

### MVP-1 Step 4 — Data Collector Interface (Complete)

- `src/hunter/data/collector.py` with abstract `DataCollector` interface:
  - 6 abstract methods: `get_exchange_info()`, `get_klines()`, `get_funding_rates()`, `get_open_interest()`, `get_mark_price()`, `get_24h_ticker()`
- `BinanceFuturesCollector` skeleton class that does NOT connect to Binance
  - All methods raise `NotImplementedError` with message "Binance connection not implemented in MVP-1"
- 5 frozen dataclass data models: `KlineData`, `FundingRateData`, `OpenInterestData`, `MarkPriceData`, `Ticker24hData`
- `tests/test_data/test_collector.py` with 18 tests:
  - `DataCollector` cannot be instantiated directly (abstract)
  - `BinanceFuturesCollector` raises `NotImplementedError` on all methods
  - No network calls are made (verified by monkeypatch)
  - Data models are immutable (`frozen=True`)

### MVP-1 Step 5 — SQLite Storage Layer (Complete)

- `src/hunter/data/schema.sql` with 5 tables:
  - `market_symbols` — Symbol registry with base/quote assets
  - `candles` — OHLCV data with unique constraint on (symbol, timeframe, open_time)
  - `funding_rates` — Funding rate history with unique constraint on (symbol, funding_time)
  - `open_interest` — Open interest snapshots
  - `collection_metadata` — Freshness tracking with upsert support
- Indexes on common query patterns: `idx_candles_symbol_timeframe_time`, `idx_funding_symbol_time`, `idx_oi_symbol_time`, `idx_meta_symbol_type`
- `src/hunter/data/storage.py` with `DataStorage` ABC and `SQLiteStorage` implementation
  - `DataStorage` ABC: 9 abstract methods (`initialize`, `save_klines`, `get_klines`, `get_latest_kline`, `save_funding_rates`, `get_funding_rates`, `save_collection_metadata`, `get_collection_metadata`, `is_data_fresh`)
  - `SQLiteStorage` uses Python standard library `sqlite3` only (no external dependencies)
  - `save_klines()` / `save_funding_rates()` use `INSERT OR IGNORE` for deduplication
  - `is_data_fresh()` checks metadata age against `max_age_seconds`
- `tests/test_data/test_storage.py` with 19 tests using temporary SQLite database files
  - All tests pass, no network calls, no Binance connection, no Freqtrade connection

### MVP-1 Step 6 — Final Safety Tests and MVP-1 Completion (Complete)

- Final review found config loader returning `dict` instead of `HunterConfig` when merging YAML
- Fixed `load_config()` to use `_deep_update()` + `model_validate()` for safe nested merging
- Fixed secret detection to scan merged dict before Pydantic strips extra fields
- Fixed config tests to use `raw_dict` parameter for secret injection
- Fixed missing `import sys` in logging tests
- Fixed `test_sets_log_level` to check root logger level
- Commit `dd3ea99`: config loader bugfix and test fixes
- All 91 tests now pass (0 failures)
- MVP-1 Data Foundation is complete

### Next

- MVP-2 Market State: Regime Engine and Market Breadth Engine design.

## 0.3.0-dev — MVP-2 Market State Design (Complete)

### Added

- `specs/SPEC-003-Market-State-Regime-Breadth.md` with complete MVP-2 design:
  - Regime Engine design with 5 states (BULL, BEAR, SIDEWAYS, TRANSITION, UNKNOWN)
  - Market Breadth Engine design with universe filtering and invalid symbol rules
  - Deterministic scoring formulas (no ML, no optimization, no curve fitting):
    - `btc_trend_score`, `bearish_btc_trend_score`, `eth_trend_score` (0–100)
    - `breadth_confirmation_score` (0–100)
    - `breadth_score` (0–100) with weighted component formula
    - `confidence` (0.0–1.0) = min(primary_score, confirmation_score) / 100
  - EMA slope formula: `ema_slope_pct = ((ema_current - ema_n_candles_ago) / ema_n_candles_ago) * 100`
  - Fail-closed behavior: all bad data → UNKNOWN + NONE + confidence 0
  - Pipeline order: Breadth Engine runs first, Regime Engine consumes breadth output
  - Timeframe-aware stale data: `stale_threshold_candles: 2` with `timeframe_duration` multiplier
  - `configs/market_state.yaml` as single config standard (no separate regime/breadth YAML)
  - JSON Schema design section for future `schemas/regime.schema.json` and `schemas/breadth.schema.json`
  - Test plan for regime, breadth, and safety tests
  - MVP-1 interface references: DataStorage ABC, SQLiteStorage, KlineData, HunterConfig

### Safety

- No trading logic exists yet.
- No Binance connection exists yet.
- No Freqtrade integration exists yet.
- No live trading is enabled.
- No API keys or exchange secrets stored in repository.
- No code implemented yet — design only.

### Next

- MVP-2 implementation planning: Step 1 — Market State Models.
