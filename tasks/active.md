# Active Task

## Current Task

Implement MVP-1 Data Foundation.

## Status

In progress

## Note

SPEC-002 MVP-1 Data Foundation design is complete and reviewed. All 8 review fixes applied. Ready for implementation.

## Previous Task

MVP-0 Project Foundation — Done.

## Goal

Build the data infrastructure that all future engines will depend on, following SPEC-002 design.

## Current Scope

Implement MVP-1 components from SPEC-002:

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
- DataStorage ABC is defined with SQLiteStorage stub
- BinanceFuturesCollector raises NotImplementedError on all methods
- Tests pass for config safety, logging redaction, and storage schema
- All code follows SPEC-002 design without deviation
- No trading logic, Binance connection, or live trading exists

## Next Step After MVP-1

MVP-2 — Market State: Regime Engine and Market Breadth Engine design.
