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

### Safety

- No trading logic exists yet.
- No Binance connection exists yet.
- No Freqtrade integration exists yet.
- No live trading is enabled.
- No API keys or exchange secrets stored in repository.
- `.gitignore` prevents accidental commit of `config/local.yaml`, `.env`, `*.key`, `*.pem`.

### Next

- Implement config Pydantic models and loader with `validate_config()`.
- Implement logging setup with JSON formatter and `RedactingFilter`.
- Implement SQLite schema and `DataStorage` / `SQLiteStorage` stubs.
- Write safety tests for config validation and logging redaction.
