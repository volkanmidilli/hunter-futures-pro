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

### Safety

- No trading logic exists yet.
- No Binance connection exists yet.
- No Freqtrade integration exists yet.
- No live trading is enabled.
- No API keys or exchange secrets stored in repository.
- `.gitignore` prevents accidental commit of `configs/local.yaml`, `.env`, `*.key`, `*.pem`.

### Next

- MVP-1 Step 3: Implement logging setup with JSON formatter and `RedactingFilter`.
- MVP-1 Step 4: Implement data collector interface (ABC only).
- MVP-1 Step 5: Implement SQLite schema and `DataStorage` / `SQLiteStorage` stubs.
- MVP-1 Step 6: Write safety tests for logging redaction and storage schema.
