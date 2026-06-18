# Current State

## Project

Hunter Futures Pro

## Version

0.6.0-dev

## Current Phase

MVP-7 Step 3 — Adapter Decision JSON Writer complete. 41 new tests. 1169 total. Ready for Step 4.

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

MVP-7 Step 2 — Strategy Adapter Engine is complete. All 75 new tests pass. 1128 total.
- `src/hunter/strategy_adapter/engine.py` — 6 engine functions.
- `src/hunter/strategy_adapter/__init__.py` — updated exports.
- `tests/test_strategy_adapter/test_engine.py` — 75 engine tests.
- Strategy adapter engine produces dry-run-only fail-closed AdapterDecisionContext for future Freqtrade-facing consumers.
- No writer yet. No integration tests yet.
- No config YAML. No JSON schema. No deployable strategy class. No Freqtrade runtime.
- No Binance. No API keys. No live trading. No real orders. No leverage. No shorting.

MVP-7 Step 3 — Adapter Decision JSON Writer is complete. All 41 new tests pass. 1169 total.
- `src/hunter/strategy_adapter/writer.py` — 3 writer functions + default path constant.
- `src/hunter/strategy_adapter/__init__.py` — updated exports.
- `tests/test_strategy_adapter/test_writer.py` — 41 writer tests.
- `DEFAULT_ADAPTER_DECISION_PATH = data/strategy_adapter/current_adapter_decision.json`.
- `adapter_decision_context_to_dict()` — serializes `AdapterDecisionContext` to JSON-compatible dict.
- `atomic_write_json()` — atomic temp-file write with `os.replace()`, parent directory creation, cleanup on failure.
- `write_adapter_decision_context()` — writes to default path.
- ISO-8601 UTC timestamps, enum strings, signal_intent as string, reason_codes as list, nested dicts, version "1.0".
- No integration tests yet. No config YAML. No JSON schema. No deployable strategy class. No Freqtrade runtime.
- No Binance. No API keys. No live trading. No real orders. No leverage. No shorting. No entry/exit execution logic.

SPEC-008 Freqtrade Dry-Run Strategy Adapter design is finalized and polished.
- AdapterState, AdapterMode, AdapterSignalIntent, AdapterDecisionContext defined.
- Fail-closed adapter rules, deterministic reason codes, future config/schema/output defined.
- PlantUML component and flow diagrams included.
- 5-step implementation plan defined.
- Full test suite: 1169 tests passing.

## Next Step

MVP-7 Step 4 — Strategy Adapter Integration Tests.
- Future file: `tests/test_strategy_adapter/test_integration.py`.
- End-to-end engine + writer tests.
- LONG_RESEARCH_ONLY signal flow.
- SHORT_RESEARCH_ONLY signal flow.
- BLOCK_SIGNAL flow.
- Stale/missing/invalid/unsafe StrategyContext flows.
- JSON output verification.
- Atomic/path verification.
- Safety absence tests.
- No application code changes unless fixing a small verified bug.
- No config YAML. No JSON schema. No deployable strategy class. No Freqtrade runtime.
- No Binance. No API keys. No live trading. No real orders. No leverage. No shorting. No entry/exit execution logic.

---

## Previous State (MVP-7 Step 3 Complete)

MVP-7 Step 3 — Adapter Decision JSON Writer is complete. All 41 new tests pass. 1169 total.
- `src/hunter/strategy_adapter/writer.py` — 3 writer functions + default path constant.
- `src/hunter/strategy_adapter/__init__.py` — updated exports.
- `tests/test_strategy_adapter/test_writer.py` — 41 writer tests.
- `DEFAULT_ADAPTER_DECISION_PATH = data/strategy_adapter/current_adapter_decision.json`.
- `adapter_decision_context_to_dict()` — serializes `AdapterDecisionContext` to JSON-compatible dict.
- `atomic_write_json()` — atomic temp-file write with `os.replace()`, parent directory creation, cleanup on failure.
- `write_adapter_decision_context()` — writes to default path.
- ISO-8601 UTC timestamps, enum strings, signal_intent as string, reason_codes as list, nested dicts, version "1.0".
- No integration tests yet. No config YAML. No JSON schema. No deployable strategy class. No Freqtrade runtime.
- No Binance. No API keys. No live trading. No real orders. No leverage. No shorting. No entry/exit execution logic.

MVP-7 Step 2 — Strategy Adapter Engine is complete. 75 new tests. 1128 total.
- `src/hunter/strategy_adapter/engine.py` — 6 engine functions.
  - `build_adapter_decision_context(...)` — main entry point implementing all 11 fail-closed adapter rules + 2 allowed + 1 fallback.
  - `validate_adapter_inputs(...)` — deterministic priority-ordered validation, returns first blocking reason only.
  - `is_stale_strategy_context(...)` — checks timestamp validity (missing/naive/None → stale) and age against threshold.
  - `map_strategy_to_adapter_mode(...)` — maps `StrategyContractMode` → `AdapterMode`.
  - `map_strategy_to_signal_intent(...)` — maps `StrategyContractMode` → `AdapterSignalIntent`.
  - `build_safety_flags(...)` — constructs `AdapterSafetyFlags` from config with safe defaults.
- `src/hunter/strategy_adapter/__init__.py` — updated exports.
- `tests/test_strategy_adapter/test_engine.py` — 75 engine tests.
- Allowed mappings: `LONG_RESEARCH_ONLY` → `ALLOW_LONG_RESEARCH_SIGNAL`, `SHORT_RESEARCH_ONLY` → `ALLOW_SHORT_RESEARCH_SIGNAL`.
- Blocking mappings: all unsafe/invalid/stale/unsupported → `BLOCK_SIGNAL`.
- No writer yet. No integration tests yet.
- No config YAML. No JSON schema. No deployable strategy class. No Freqtrade runtime.
- No Binance. No API keys. No live trading. No real orders. No leverage. No shorting.
- No entry/exit execution logic.
