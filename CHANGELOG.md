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

### Next

- MVP-1 Step 5: Implement SQLite schema and `DataStorage` / `SQLiteStorage` stubs.
- MVP-1 Step 6: Write safety tests for storage schema.
