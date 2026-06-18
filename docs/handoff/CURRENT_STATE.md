# Current State

## Project

Hunter Futures Pro

## Version

0.6.0-dev

## Current Phase

MVP-7 Step 1 — Strategy Adapter Models complete. 94 new tests. 1053 total. Ready for Step 2.

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

MVP-7 Step 1 — Strategy Adapter Models is complete. All 94 new tests pass. 1053 total.
- `src/hunter/strategy_adapter/__init__.py` — public API exports.
- `src/hunter/strategy_adapter/models.py` — 8 model types + 15 reason codes.
- `tests/test_strategy_adapter/test_models.py` — 94 model tests.
- No engine yet. No writer yet. No integration tests yet.
- No config YAML. No JSON schema. No deployable strategy class. No Freqtrade runtime.
- No Binance. No API keys. No live trading. No real orders. No leverage. No shorting.

SPEC-008 Freqtrade Dry-Run Strategy Adapter design is finalized and polished.
- AdapterState, AdapterMode, AdapterSignalIntent, AdapterDecisionContext defined.
- Fail-closed adapter rules, deterministic reason codes, future config/schema/output defined.
- PlantUML component and flow diagrams included.
- 5-step implementation plan defined.
- Full test suite: 1053 tests passing.

## Next Step

MVP-7 Step 2 — Strategy Adapter Engine.
- Future files: `src/hunter/strategy_adapter/engine.py`, `tests/test_strategy_adapter/test_engine.py`.
- Define: `build_adapter_decision(...)`, `validate_adapter_inputs(...)`, `is_stale_strategy_context(...)`, `map_strategy_to_adapter_mode(...)`, `map_strategy_to_signal_intent(...)`, `build_safety_flags(...)`.
- Implementation not started yet. Awaiting approval.
- No writer yet.
- No integration tests yet.
- No config YAML.
- No JSON schema.
- No deployable strategy class.
- No Freqtrade runtime.
- No Binance.
- No API keys.
- No live trading.
- No real orders.
- No leverage.
- No shorting.
- No entry/exit execution logic.

---

## Previous State (MVP-7 Step 1 Complete)

MVP-7 Step 1 — Strategy Adapter Models is complete. 94 new tests. 1053 total.
- `src/hunter/strategy_adapter/__init__.py` — public API exports.
- `src/hunter/strategy_adapter/models.py` — 8 model types + 15 reason codes.
- `tests/test_strategy_adapter/__init__.py` — test package.
- `tests/test_strategy_adapter/test_models.py` — 94 model tests.
- Adapter produces dry-run-only fail-closed AdapterDecisionContext for future Freqtrade-facing consumers.
- Default output path: `data/strategy_adapter/current_adapter_decision.json` (future).
- No config YAML exists.
- No JSON schema exists.
- No deployable strategy class exists.
- No Binance integration exists.
- No real Freqtrade runtime integration exists.
- No API keys.
- No live trading.
- No real orders.
- No leverage.
- No shorting.
- No entry/exit execution logic.
