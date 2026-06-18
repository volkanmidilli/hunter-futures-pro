# Current State

## Project

Hunter Futures Pro

## Version

0.6.0-dev

## Current Phase

MVP-7 planning — SPEC-008 Freqtrade Dry-Run Strategy Adapter design finalized. Ready for MVP-7 Step 1.

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

SPEC-008 Freqtrade Dry-Run Strategy Adapter design is finalized and polished.
- AdapterState, AdapterMode, AdapterSignalIntent, AdapterDecisionContext defined.
- Fail-closed adapter rules, deterministic reason codes, future config/schema/output defined.
- PlantUML component and flow diagrams included.
- 5-step implementation plan defined.
- No MVP-7 implementation exists yet.
- No strategy_adapter package exists yet.
- Full test suite: 959 tests passing.

## Next Step

MVP-7 Step 1 — Strategy Adapter Models.
- Future files: `src/hunter/strategy_adapter/__init__.py`, `src/hunter/strategy_adapter/models.py`, `tests/test_strategy_adapter/__init__.py`, `tests/test_strategy_adapter/test_models.py`.
- Define: AdapterState, AdapterMode, AdapterSignalIntent, AdapterConfig, AdapterInputRefs, AdapterSafetyFlags, AdapterDataQuality, AdapterDecisionContext.
- Implementation not started yet. Awaiting approval.
- No Binance integration.
- No real Freqtrade runtime.
- No deployable strategy class.
- No API keys.
- No live trading.
- No real orders.
- No leverage.
- No shorting.

---

## Previous State (MVP-6 Complete + SPEC-008 Design)

MVP-6 — Freqtrade Strategy Contract is complete. All 5 steps finished. 959 tests passing.
- `src/hunter/strategy_contract/__init__.py` — public API exports.
- `src/hunter/strategy_contract/models.py` — 7 model types + 15 reason codes.
- `src/hunter/strategy_contract/engine.py` — 5 engine functions.
- `src/hunter/strategy_contract/writer.py` — 3 writer functions + default path constant.
- `tests/test_strategy_contract/test_models.py` — 84 model tests.
- `tests/test_strategy_contract/test_engine.py` — 72 engine tests.
- `tests/test_strategy_contract/test_writer.py` — 36 writer tests.
- `tests/test_strategy_contract/test_integration.py` — 45 integration tests.
- Strategy contract produces dry-run-only fail-closed StrategyContext for future strategy-facing consumers.
- Default output path: `data/strategy/current_strategy_context.json`.
- No config YAML exists.
- No JSON schema exists.
- No Freqtrade strategy class exists.
- No Binance integration exists.
- No real Freqtrade runtime integration exists.
- No API keys.
- No live trading.
- No real orders.
- No leverage.
- No shorting.
