# Current State

## Project

Hunter Futures Pro

## Version

0.7.0-dev

## Current Phase

MVP-8 planning / SPEC-009 complete. Step 1 Dry-Run Strategy Runtime Models complete. Step 2 Dry-Run Strategy Runtime Engine complete. Next step is MVP-8 Step 3 — Dry-Run Strategy Runtime JSON Writer. No writer, no integration tests, no config YAML, no JSON schema, no deployable Freqtrade strategy class, no Freqtrade runtime connection, no Binance, no real exchange connection, no API keys, no live trading, no real orders, no leverage, no shorting, no real entry/exit execution logic.

## Current Status

MVP-0 foundation is complete and committed.

MVP-1 Data Foundation is complete and committed. All 91 tests pass.

MVP-2 Market State is complete and committed. All 278 tests pass.
- Market State Models, Indicator Utilities, Regime Engine, Breadth Engine, JSON Output Writers all implemented.
- No Binance integration. No Freqtrade integration. No live trading.

MVP-3 Decision Layer is complete and committed. All 394 tests pass.
- Decision Models, Decision Engine, Decision Writer, Integration Tests all implemented.
- No Binance integration. No Freqtrade integration. No live trading. No JSON input reading.

MVP-4 Execution Bridge is complete and committed. All 538 tests pass.
- Execution Bridge Models, Engine, Writer, Integration Tests, Final Review all implemented.
- No Binance integration. No Freqtrade runtime integration. No live trading. No trading logic. No API keys.

MVP-5 Freqtrade Integration is complete and committed. All 722 tests pass.
- Freqtrade Bridge Models, Engine, Writer, Integration Tests, Final Review all implemented.
- No Binance integration. No real Freqtrade runtime integration. No live trading. No trading logic. No API keys.

MVP-6 Freqtrade Strategy Contract is complete and committed. All 959 tests pass.
- Strategy Contract Models, Engine, Writer, Integration Tests, Final Review all implemented.
- No Binance integration. No real Freqtrade runtime integration. No live trading. No trading logic. No API keys.

MVP-7 Freqtrade Dry-Run Strategy Adapter is complete and committed. All 1214 tests pass.
- Strategy Adapter Models, Engine, Writer, Integration Tests, Final Review all implemented.
- `src/hunter/strategy_adapter/models.py` — 8 model types + 15 reason codes.
- `src/hunter/strategy_adapter/engine.py` — 6 engine functions.
- `src/hunter/strategy_adapter/writer.py` — 3 writer functions + default path constant.
- `tests/test_strategy_adapter/test_models.py` — 94 model tests.
- `tests/test_strategy_adapter/test_engine.py` — 75 engine tests.
- `tests/test_strategy_adapter/test_writer.py` — 41 writer tests.
- `tests/test_strategy_adapter/test_integration.py` — 45 integration tests.
- `DEFAULT_ADAPTER_DECISION_PATH = data/strategy_adapter/current_adapter_decision.json`.
- Adapter produces dry-run-only fail-closed `AdapterDecisionContext` for future Freqtrade-facing consumers.
- No config YAML exists. No JSON schema exists. No deployable Freqtrade strategy class exists.
- No Binance integration. No real Freqtrade runtime integration. No API keys. No live trading. No real orders. No leverage. No shorting. No entry/exit execution logic.

SPEC-009 Freqtrade Deployable Dry-Run Strategy design is finalized and polished.
- `DryRunStrategyState`, `DryRunStrategyMode`, `DryRunSignalAction`, `DryRunStrategyRuntimeContext` defined.
- Fail-closed deployable dry-run strategy rules, deterministic reason codes, future config/schema/output defined.
- PlantUML component and runtime flow diagrams included.
- 5-step implementation plan defined.
- MVP-8 Step 1 Dry-Run Strategy Runtime Models complete.
- `dry_run_strategy` package now exists with models and engine.
- `tests/test_dry_run_strategy/test_models.py` exists with 94 tests.
- MVP-8 Step 2 Dry-Run Strategy Runtime Engine complete.
- `src/hunter/dry_run_strategy/engine.py` exists with 6 engine functions.
- `tests/test_dry_run_strategy/test_engine.py` exists with 93 tests.
- Full test suite: 1401 tests passing.

## Next Step

MVP-8 Step 3 — Dry-Run Strategy Runtime JSON Writer.
- Future files: `src/hunter/dry_run_strategy/writer.py`, `tests/test_dry_run_strategy/test_writer.py`.
- Allowed: `dry_run_strategy_runtime_context_to_dict()`, `atomic_write_json()`, `write_dry_run_strategy_runtime_context()`, JSON serialization tests, atomic write tests, default output path `data/freqtrade_strategy/current_dry_run_strategy_runtime.json`.
- Not allowed: no engine changes unless import/export only, no integration tests, no config YAML, no JSON schema, no deployable Freqtrade strategy class, no Freqtrade runtime connection, no Binance, no real exchange connection, no API keys, no live trading, no real orders, no leverage, no shorting, no real entry/exit execution logic.

## Previous State (MVP-7 Complete)

MVP-7 Freqtrade Dry-Run Strategy Adapter is complete and committed. All 1214 tests pass.
- Strategy Adapter Models, Engine, Writer, Integration Tests, Final Review all implemented.
- 63 final review checklist items passed. No issues found.
- No config YAML. No JSON schema. No deployable strategy class. No Freqtrade runtime.
- No Binance. No API keys. No live trading. No real orders. No leverage. No shorting. No entry/exit execution logic.

---
