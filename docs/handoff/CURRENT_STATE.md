# Current State

## Project

Hunter Futures Pro

## Version

0.7.0-dev

## Current Phase

MVP-7 complete — Freqtrade Dry-Run Strategy Adapter. All 1214 tests pass. Ready for MVP-8 Planning.

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

SPEC-008 Freqtrade Dry-Run Strategy Adapter design is finalized and polished.
- AdapterState, AdapterMode, AdapterSignalIntent, AdapterDecisionContext defined.
- Fail-closed adapter rules, deterministic reason codes, future config/schema/output defined.
- PlantUML component and flow diagrams included.
- 5-step implementation plan defined.

## Next Step

MVP-8 Planning — SPEC-009 Freqtrade Deployable Dry-Run Strategy.
- Design/spec only at this stage. No code implementation yet.
- MVP-8 may only design a future deployable dry-run strategy that consumes `AdapterDecisionContext` safely.
- Not allowed: no Binance integration, no real exchange connection, no API keys, no live trading, no real order execution, no leverage, no shorting.

## Previous State (MVP-7 Complete)

MVP-7 Freqtrade Dry-Run Strategy Adapter is complete and committed. All 1214 tests pass.
- Strategy Adapter Models, Engine, Writer, Integration Tests, Final Review all implemented.
- 63 final review checklist items passed. No issues found.
- No config YAML. No JSON schema. No deployable strategy class. No Freqtrade runtime.
- No Binance. No API keys. No live trading. No real orders. No leverage. No shorting. No entry/exit execution logic.

---
