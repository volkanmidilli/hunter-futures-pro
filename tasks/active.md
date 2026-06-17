# Active Task

## Current Task

MVP-1 Data Foundation — Complete.

## Status

Done.

## Note

All 91 tests pass.

MVP-1 implementation is complete:
- Python project structure exists and is importable
- Config loads with safe defaults and validates trading is disabled
- Logging outputs structured JSON with secret redaction
- SQLite schema is creatable and testable
- DataStorage ABC is defined with SQLiteStorage implementation
- BinanceFuturesCollector raises NotImplementedError on all methods
- All code follows SPEC-002 design without deviation
- No trading logic, Binance connection, or live trading exists

## Previous Task

MVP-0 Project Foundation — Done.

## Goal

Build the data infrastructure that all future engines will depend on, following SPEC-002 design.

## Current Scope

MVP-1 components implemented:

1. Python project structure (directories, __init__.py, pyproject.toml)
2. Config structure (Pydantic models, loader, validation)
3. Logging structure (JSON formatter, redaction, rotation)
4. Data collector interface (ABC, not connected to Binance)
5. SQLite storage layer (schema, DataStorage ABC, SQLiteStorage)
6. Test structure (pytest, fixtures, safety tests)

## Do Not Do Yet

- Do not write trading logic.
- Do not connect to Binance.
- Do not connect to Freqtrade.
- Do not create API keys.
- Do not enable live trading.
- Do not create production trading rules.
- Do not implement actual data collection (design only, collection.enabled: false).

## Definition of Done

MVP-1 is done when:

- Python project structure exists and is importable
- Config loads with safe defaults and validates trading is disabled
- Logging outputs structured JSON with secret redaction
- SQLite schema is creatable and testable
- DataStorage ABC is defined with SQLiteStorage implementation
- BinanceFuturesCollector raises NotImplementedError on all methods
- Tests pass for config safety, logging redaction, and storage schema
- All code follows SPEC-002 design without deviation
- No trading logic, Binance connection, or live trading exists

## Next Step After MVP-1

MVP-2 — Market State: Regime Engine and Market Breadth Engine design.
