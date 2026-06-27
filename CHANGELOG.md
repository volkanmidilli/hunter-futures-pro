# Changelog

All important project changes will be recorded in this file.

## MVP-8 — Freqtrade Deployable Dry-Run Strategy (Planning)

### Added

- SPEC-009 Freqtrade Deployable Dry-Run Strategy design finalized.
  - `DryRunStrategyState` enum: DISABLED, DRY_RUN_READY, BLOCKED, UNKNOWN.
  - `DryRunStrategyMode` enum: LONG_RESEARCH_ONLY, SHORT_RESEARCH_ONLY, BLOCK_ALL.
  - `DryRunSignalAction` enum: EXPOSE_LONG_RESEARCH_SIGNAL, EXPOSE_SHORT_RESEARCH_SIGNAL, BLOCK_SIGNAL, NO_SIGNAL.
  - `DryRunStrategyRuntimeContext` with 22 fields including adapter_state, adapter_mode, adapter_signal_intent, dry_run, live_trading_enabled, real_orders_enabled, leverage_enabled, shorting_enabled, freqtrade_runtime_allowed, strategy_class_allowed, populate_indicators_allowed, populate_entry_trend_allowed, populate_exit_trend_allowed, order_execution_allowed.
  - Fail-closed deployable dry-run strategy rules: 12 blocking + 2 allowed + 1 fallback in deterministic priority order.
  - Deterministic reason codes: MISSING_ADAPTER_DECISION_CONTEXT, INVALID_ADAPTER_DECISION_CONTEXT, ADAPTER_NOT_DRY_RUN_READY, ADAPTER_MODE_BLOCK_ALL, ADAPTER_SIGNAL_BLOCKED, DRY_RUN_DISABLED, LIVE_TRADING_ENABLED, REAL_ORDERS_ENABLED, LEVERAGE_ENABLED, SHORTING_ENABLED, STALE_ADAPTER_DECISION_CONTEXT, UNSUPPORTED_ADAPTER_MODE, UNSUPPORTED_ADAPTER_SIGNAL_INTENT, LONG_RESEARCH_SIGNAL_EXPOSED, SHORT_RESEARCH_SIGNAL_EXPOSED, DEFAULT_BLOCK_SIGNAL, CALCULATION_ERROR.
  - Future config design: `configs/dry_run_strategy.yaml` (design-only, not created).
  - Future output: `data/freqtrade_strategy/current_dry_run_strategy_runtime.json` (design-only, not created).
  - Future schema: `schemas/dry_run_strategy_runtime.schema.json` (design-only, not created).
  - PlantUML component and runtime flow diagrams included.
  - 5-step implementation plan defined: Models, Engine, Writer, Integration Tests, Final Review.
- MVP-8 Step 1 — Dry-Run Strategy Runtime Models complete.
  - `src/hunter/dry_run_strategy/__init__.py` — public API exports.
  - `src/hunter/dry_run_strategy/models.py` — Dry-Run Strategy Models (Step 1).
    - `DryRunStrategyState` enum: DISABLED, DRY_RUN_READY, BLOCKED, UNKNOWN.
    - `DryRunStrategyMode` enum: LONG_RESEARCH_ONLY, SHORT_RESEARCH_ONLY, BLOCK_ALL.
    - `DryRunSignalAction` enum: EXPOSE_LONG_RESEARCH_SIGNAL, EXPOSE_SHORT_RESEARCH_SIGNAL, BLOCK_SIGNAL, NO_SIGNAL.
    - `DryRunStrategyConfig` with 17 fields and MVP-8 safety validation.
    - `DryRunStrategyInputRefs` with path validation.
    - `DryRunStrategySafetyFlags` with 12 safety fields and `to_dict()` for JSON serialization.
    - `DryRunStrategyDataQuality` with 4 quality fields and `to_dict()` for JSON serialization.
    - `DryRunStrategyRuntimeContext` with 24 fields, version default "1.0", `blocked()` fail-closed factory, `is_blocking()` method.
    - 17 deterministic reason codes: MISSING_ADAPTER_DECISION_CONTEXT, INVALID_ADAPTER_DECISION_CONTEXT, ADAPTER_NOT_DRY_RUN_READY, ADAPTER_MODE_BLOCK_ALL, ADAPTER_SIGNAL_BLOCKED, DRY_RUN_DISABLED, LIVE_TRADING_ENABLED, REAL_ORDERS_ENABLED, LEVERAGE_ENABLED, SHORTING_ENABLED, STALE_ADAPTER_DECISION_CONTEXT, UNSUPPORTED_ADAPTER_MODE, UNSUPPORTED_ADAPTER_SIGNAL_INTENT, LONG_RESEARCH_SIGNAL_EXPOSED, SHORT_RESEARCH_SIGNAL_EXPOSED, DEFAULT_BLOCK_SIGNAL, CALCULATION_ERROR.
    - All models frozen/immutable with `__post_init__` validation.
    - 94 dry-run strategy model tests, all passing.
  - `tests/test_dry_run_strategy/__init__.py` — test package.
  - `tests/test_dry_run_strategy/test_models.py` — 94 model tests, all passing.
  - Full test suite: 1308 tests passing (1214 existing + 94 new).
  - No engine, no writer, no integration tests, no config YAML, no JSON schema, no deployable Freqtrade strategy class, no Freqtrade runtime connection, no Binance, no real exchange connection, no API keys, no live trading, no real orders, no leverage, no shorting, no real entry/exit execution logic.
- MVP-8 Step 2 — Dry-Run Strategy Runtime Engine complete.
  - `src/hunter/dry_run_strategy/engine.py` — Dry-Run Strategy Engine (Step 2).
    - `build_dry_run_strategy_runtime_context()` — fail-closed runtime context builder with deterministic validation.
    - `validate_dry_run_strategy_inputs()` — 13 priority-ordered blocking checks, returns first blocking reason only.
    - `is_stale_adapter_decision_context()` — timestamp validity + age check.
    - `map_adapter_to_strategy_mode()` — adapter mode → strategy mode mapping.
    - `map_adapter_to_signal_action()` — adapter signal intent → strategy signal action mapping.
    - `build_safety_flags()` — safe defaults from config.
    - Allowed mappings:
      - `LONG_RESEARCH_ONLY` + `ALLOW_LONG_RESEARCH_SIGNAL` → `EXPOSE_LONG_RESEARCH_SIGNAL`
      - `SHORT_RESEARCH_ONLY` + `ALLOW_SHORT_RESEARCH_SIGNAL` → `EXPOSE_SHORT_RESEARCH_SIGNAL`
    - Unsafe/invalid/stale/unsupported → `BLOCK_SIGNAL`.
  - `src/hunter/dry_run_strategy/__init__.py` — updated with 6 engine function exports.
  - `tests/test_dry_run_strategy/test_engine.py` — 93 engine tests, all passing.
  - Full test suite: 1401 tests passing (1308 existing + 93 new).
  - No writer, no integration tests, no config YAML, no JSON schema, no deployable Freqtrade strategy class, no Freqtrade runtime connection, no Binance, no real exchange connection, no API keys, no live trading, no real orders, no leverage, no shorting, no real entry/exit execution logic.
- MVP-8 Step 3 — Dry-Run Strategy Runtime JSON Writer complete.
  - `src/hunter/dry_run_strategy/writer.py` — Dry-Run Strategy Writer (Step 3).
    - `DEFAULT_DRY_RUN_STRATEGY_RUNTIME_PATH = data/freqtrade_strategy/current_dry_run_strategy_runtime.json`.
    - `dry_run_strategy_runtime_context_to_dict()` — deterministic JSON-safe serialization:
      - ISO-8601 timestamps with Z suffix.
      - Enum values as `.value` strings.
      - Tuple `reason_codes` as list.
      - Nested `input_refs`, `safety_flags`, `data_quality` as dicts.
    - `atomic_write_json()` — atomic write:
      - Parent directories created if missing.
      - Temp file in same directory.
      - `fsync` for durability.
      - `os.replace` for atomic rename.
      - Temp cleanup on failure.
      - Sorted, indented UTF-8 JSON with trailing newline.
    - `write_dry_run_strategy_runtime_context()` — default path or custom path, converts + writes atomically.
  - `src/hunter/dry_run_strategy/__init__.py` — updated with 4 writer exports.
  - `tests/test_dry_run_strategy/test_writer.py` — 42 writer tests, all passing.
  - Full test suite: 1443 tests passing (1401 existing + 42 new).
  - No engine changes, no model changes, no integration tests, no config YAML, no JSON schema, no deployable Freqtrade strategy class, no Freqtrade runtime connection, no Binance, no real exchange connection, no API keys, no live trading, no real orders, no leverage, no shorting, no real entry/exit execution logic.
- MVP-8 Step 4 — Dry-Run Strategy Runtime Integration Tests complete.
  - `tests/test_dry_run_strategy/test_integration.py` — 48 integration tests, all passing.
    - Long research happy path: DRY_RUN_READY + LONG_RESEARCH_ONLY + ALLOW_LONG_RESEARCH_SIGNAL → EXPOSE_LONG_RESEARCH_SIGNAL, JSON round-trip verified.
    - Short research happy path: DRY_RUN_READY + SHORT_RESEARCH_ONLY + ALLOW_SHORT_RESEARCH_SIGNAL → EXPOSE_SHORT_RESEARCH_SIGNAL, JSON round-trip verified.
    - Missing adapter decision context: None input → MISSING_ADAPTER_DECISION_CONTEXT, BLOCK_SIGNAL.
    - Invalid adapter decision context: missing attrs → INVALID_ADAPTER_DECISION_CONTEXT, BLOCK_SIGNAL.
    - Adapter BLOCKED state → ADAPTER_NOT_DRY_RUN_READY, BLOCK_SIGNAL.
    - Adapter UNKNOWN state → ADAPTER_NOT_DRY_RUN_READY, BLOCK_SIGNAL.
    - Adapter DISABLED state → ADAPTER_NOT_DRY_RUN_READY, BLOCK_SIGNAL.
    - Adapter BLOCK_ALL mode → ADAPTER_MODE_BLOCK_ALL, BLOCK_SIGNAL.
    - Adapter BLOCK_SIGNAL intent → ADAPTER_SIGNAL_BLOCKED, BLOCK_SIGNAL.
    - dry_run false → DRY_RUN_DISABLED, BLOCK_SIGNAL.
    - live_trading_enabled true → LIVE_TRADING_ENABLED, BLOCK_SIGNAL.
    - real_orders_enabled true → REAL_ORDERS_ENABLED, BLOCK_SIGNAL.
    - leverage_enabled true → LEVERAGE_ENABLED, BLOCK_SIGNAL.
    - shorting_enabled true → SHORTING_ENABLED, BLOCK_SIGNAL.
    - Stale adapter decision context → STALE_ADAPTER_DECISION_CONTEXT, BLOCK_SIGNAL.
    - Unsupported adapter mode → UNSUPPORTED_ADAPTER_MODE, BLOCK_SIGNAL.
    - Unsupported signal intent → UNSUPPORTED_ADAPTER_SIGNAL_INTENT, BLOCK_SIGNAL.
    - Writer integration: parent directory creation, valid JSON with deterministic top-level keys, safety flags verification, blocked context JSON output.
    - Safety integration assertions: no production data path writes, no network calls, no Freqtrade runtime, no Binance, no real exchange, no API keys, no live trading, no leverage, no shorting, no real entry/exit execution logic.
  - Full test suite: 1491 tests passing (1443 existing + 48 new).
  - No model changes, no engine changes, no writer changes, no __init__.py changes.
  - No config YAML, no JSON schema, no deployable Freqtrade strategy class, no Freqtrade runtime connection, no Binance, no real exchange connection, no API keys, no live trading, no real orders, no leverage, no shorting, no real entry/exit execution logic.
- MVP-8 remains design-first; implementation has not started.
- Full test suite: 1214 tests passing.

## MVP-8 — Freqtrade Deployable Dry-Run Strategy (Complete)

### Added

- MVP-8 complete — SPEC-009 Freqtrade Deployable Dry-Run Strategy implemented.
  - Version 0.8.0-dev.
  - `src/hunter/dry_run_strategy/` package with models, engine, writer, and tests.
  - `src/hunter/dry_run_strategy/__init__.py` — public API exports (8 models + 6 engine functions + 4 writer functions + 17 reason codes).
  - `src/hunter/dry_run_strategy/models.py` — Dry-Run Strategy Runtime Models.
    - `DryRunStrategyState` enum: DISABLED, DRY_RUN_READY, BLOCKED, UNKNOWN.
    - `DryRunStrategyMode` enum: LONG_RESEARCH_ONLY, SHORT_RESEARCH_ONLY, BLOCK_ALL.
    - `DryRunSignalAction` enum: EXPOSE_LONG_RESEARCH_SIGNAL, EXPOSE_SHORT_RESEARCH_SIGNAL, BLOCK_SIGNAL, NO_SIGNAL.
    - `DryRunStrategyConfig` with 17 fields and MVP-8 safety validation (dry_run=True, all unsafe flags=False).
    - `DryRunStrategyInputRefs` with path validation.
    - `DryRunStrategySafetyFlags` with 12 safety fields and `to_dict()` for JSON serialization.
    - `DryRunStrategyDataQuality` with 4 quality fields and `to_dict()` for JSON serialization.
    - `DryRunStrategyRuntimeContext` with 24 fields, version default "1.0", `blocked()` fail-closed factory, `is_blocking()` method.
    - 17 deterministic reason codes: MISSING_ADAPTER_DECISION_CONTEXT, INVALID_ADAPTER_DECISION_CONTEXT, ADAPTER_NOT_DRY_RUN_READY, ADAPTER_MODE_BLOCK_ALL, ADAPTER_SIGNAL_BLOCKED, DRY_RUN_DISABLED, LIVE_TRADING_ENABLED, REAL_ORDERS_ENABLED, LEVERAGE_ENABLED, SHORTING_ENABLED, STALE_ADAPTER_DECISION_CONTEXT, UNSUPPORTED_ADAPTER_MODE, UNSUPPORTED_ADAPTER_SIGNAL_INTENT, LONG_RESEARCH_SIGNAL_EXPOSED, SHORT_RESEARCH_SIGNAL_EXPOSED, DEFAULT_BLOCK_SIGNAL, CALCULATION_ERROR.
    - All models frozen/immutable with `__post_init__` validation.
  - `src/hunter/dry_run_strategy/engine.py` — Dry-Run Strategy Runtime Engine.
    - `build_dry_run_strategy_runtime_context()` — fail-closed runtime context builder with deterministic validation.
    - `validate_dry_run_strategy_inputs()` — 13 priority-ordered blocking checks, returns first blocking reason only.
    - `is_stale_adapter_decision_context()` — timestamp validity + age check.
    - `map_adapter_to_strategy_mode()` — adapter mode → strategy mode mapping.
    - `map_adapter_to_signal_action()` — adapter signal intent → strategy signal action mapping.
    - `build_safety_flags()` — safe defaults from config.
    - Allowed mappings: LONG_RESEARCH_ONLY + ALLOW_LONG_RESEARCH_SIGNAL → EXPOSE_LONG_RESEARCH_SIGNAL; SHORT_RESEARCH_ONLY + ALLOW_SHORT_RESEARCH_SIGNAL → EXPOSE_SHORT_RESEARCH_SIGNAL.
    - Unsafe/invalid/stale/unsupported → BLOCK_SIGNAL.
  - `src/hunter/dry_run_strategy/writer.py` — Dry-Run Strategy Runtime JSON Writer.
    - `DEFAULT_DRY_RUN_STRATEGY_RUNTIME_PATH = data/freqtrade_strategy/current_dry_run_strategy_runtime.json`.
    - `dry_run_strategy_runtime_context_to_dict()` — deterministic JSON-safe serialization with ISO-8601 timestamps, enum values, tuple→list, nested dicts.
    - `atomic_write_json()` — atomic temp-file write with parent directory creation, fsync, os.replace, cleanup on failure.
    - `write_dry_run_strategy_runtime_context()` — default path or custom path, converts + writes atomically.
  - `tests/test_dry_run_strategy/__init__.py` — test package.
  - `tests/test_dry_run_strategy/test_models.py` — 94 model tests, all passing.
  - `tests/test_dry_run_strategy/test_engine.py` — 93 engine tests, all passing.
  - `tests/test_dry_run_strategy/test_writer.py` — 42 writer tests, all passing.
  - `tests/test_dry_run_strategy/test_integration.py` — 48 integration tests, all passing.
  - 277 MVP-8 tests total. Full test suite: 1491 tests passing.
  - Final review verdict: PASS. No defects found.
  - No config YAML. No JSON schema. No deployable Freqtrade strategy class. No Freqtrade runtime connection. No Binance. No real exchange. No API keys. No live trading. No real orders. No leverage. No shorting. No real entry/exit execution logic.

### Safety

- No Binance integration.
- No real exchange connection.
- No real Freqtrade runtime connection.
- No API keys.
- No live trading.
- No real orders.
- No leverage.
- No shorting.
- No real entry/exit execution logic.
- No deployable Freqtrade strategy class created.
- No config YAML created.
- No JSON schema created.

### Next

- MVP-8 Step 1 — Dry-Run Strategy Runtime Models.

## MVP-7 — Freqtrade Dry-Run Strategy Adapter (Complete)

### Added

- `src/hunter/strategy_adapter/__init__.py` — public API exports (Step 1).
- `src/hunter/strategy_adapter/models.py` — Strategy Adapter Models (Step 1).
  - `AdapterState` enum: DISABLED, DRY_RUN_READY, BLOCKED, UNKNOWN.
  - `AdapterMode` enum: LONG_RESEARCH_ONLY, SHORT_RESEARCH_ONLY, BLOCK_ALL.
  - `AdapterSignalIntent` enum: ALLOW_LONG_RESEARCH_SIGNAL, ALLOW_SHORT_RESEARCH_SIGNAL, BLOCK_SIGNAL, NO_SIGNAL.
  - `AdapterConfig` with MVP-7 safety validation (dry_run_required=True, all unsafe flags False, all runtime/execution flags False).
  - `AdapterInputRefs` for audit trail references to strategy context and adapter decision.
  - `AdapterSafetyFlags` with 12 fields including adapter_runtime_allowed, freqtrade_runtime_allowed, strategy_class_allowed, entry_signal_allowed, exit_signal_allowed, order_execution_allowed (all default False).
  - `AdapterDataQuality` with strategy_context_present, strategy_context_valid, strategy_context_stale, reason.
  - `AdapterDecisionContext` with 22 fields including signal_intent, strategy_contract_state, strategy_contract_mode, adapter_runtime_allowed, freqtrade_runtime_allowed, strategy_class_allowed, entry_signal_allowed, exit_signal_allowed, order_execution_allowed.
  - `AdapterDecisionContext.blocked()` fail-closed factory producing BLOCKED + BLOCK_ALL + BLOCK_SIGNAL + version "1.0".
  - 15 deterministic reason codes: MISSING_STRATEGY_CONTEXT, INVALID_STRATEGY_CONTEXT, STRATEGY_CONTRACT_NOT_DRY_RUN_READY, STRATEGY_CONTRACT_MODE_BLOCK_ALL, DRY_RUN_DISABLED, LIVE_TRADING_ENABLED, REAL_ORDERS_ENABLED, LEVERAGE_ENABLED, SHORTING_ENABLED, STALE_STRATEGY_CONTEXT, UNSUPPORTED_STRATEGY_MODE, LONG_RESEARCH_SIGNAL_ALLOWED, SHORT_RESEARCH_SIGNAL_ALLOWED, DEFAULT_BLOCK_SIGNAL, CALCULATION_ERROR.
  - All models frozen/immutable with `__post_init__` validation.
  - 94 strategy adapter model tests, all passing.

- `src/hunter/strategy_adapter/engine.py` — Strategy Adapter Engine (Step 2).
  - `build_adapter_decision_context()` — main entry point implementing all 11 fail-closed adapter rules + 2 allowed + 1 fallback from SPEC-008 in priority order.
  - `validate_adapter_inputs()` — deterministic priority-ordered validation, returns first blocking reason only.
  - `is_stale_strategy_context()` — checks timestamp validity (missing/naive/None → stale) and age against threshold.
  - `map_strategy_to_adapter_mode()` — maps `StrategyContractMode` → `AdapterMode`.
  - `map_strategy_to_signal_intent()` — maps `StrategyContractMode` → `AdapterSignalIntent`.
  - `build_safety_flags()` — constructs `AdapterSafetyFlags` from config with safe defaults.
  - Allowed mappings: LONG_RESEARCH_ONLY → ALLOW_LONG_RESEARCH_SIGNAL, SHORT_RESEARCH_ONLY → ALLOW_SHORT_RESEARCH_SIGNAL.
  - Blocking mappings: all unsafe/invalid/stale/unsupported → BLOCK_SIGNAL.
  - 75 strategy adapter engine tests, all passing.

- `src/hunter/strategy_adapter/writer.py` — Adapter Decision JSON Writer (Step 3).
  - `adapter_decision_context_to_dict()` — serializes all 22 `AdapterDecisionContext` fields to JSON-compatible dict.
  - `atomic_write_json()` — atomic temp-file write with `os.replace()`, parent directory creation, cleanup on failure.
  - `write_adapter_decision_context()` — writes to `data/strategy_adapter/current_adapter_decision.json` by default.
  - `DEFAULT_ADAPTER_DECISION_PATH = data/strategy_adapter/current_adapter_decision.json`.
  - ISO-8601 UTC timestamps ending with Z, enum string values, signal_intent as string, reason_codes as list, nested dicts, version "1.0".
  - 41 writer tests, all passing.

- `tests/test_strategy_adapter/test_integration.py` — Integration Tests (Step 4).
  - 45 end-to-end integration tests.
  - Full pipeline: StrategyContext → build_adapter_decision_context() → write_adapter_decision_context() → JSON verification.
  - Allowed LONG_RESEARCH_ONLY signal flow (DRY_RUN_READY → ALLOW_LONG_RESEARCH_SIGNAL).
  - Allowed SHORT_RESEARCH_ONLY signal flow (DRY_RUN_READY → ALLOW_SHORT_RESEARCH_SIGNAL).
  - Blocked signal flows: missing, BLOCKED, UNKNOWN, DISABLED strategy contract states; BLOCK_ALL strategy contract mode; stale StrategyContext; unsafe flags (dry_run false, live_trading_enabled true, real_orders_enabled true, leverage_enabled true, shorting_enabled true).
  - JSON output verification: all 22 fields, enum strings, signal_intent, reason_codes, safety_flags, data_quality, version "1.0", ISO-8601 timestamps.
  - Atomic write tests with tmp_path, nested directory creation, no production path usage.
  - Safety tests: no network, no trading logic, no JSON input reading, no Freqtrade runtime, no Binance, all flags safe.

- SPEC-008 Freqtrade Dry-Run Strategy Adapter design finalized and polished.
  - AdapterState, AdapterMode, AdapterSignalIntent, AdapterDecisionContext defined.
  - Fail-closed adapter rules, deterministic reason codes, future config/schema/output defined.
  - PlantUML component and flow diagrams included.
  - 5-step implementation plan defined.

- MVP-7 Step 5 — Final Review and Polish complete.
  - 63 final review checklist items passed.
  - No issues found. No fixes applied.
  - Full test suite: 1214 tests passing.
  - Adapter remains dry-run-only and fail-closed.
  - No Binance integration. No real Freqtrade runtime integration. No deployable strategy class.
  - No config YAML. No JSON schema. No API keys. No live trading. No real orders. No leverage. No shorting. No entry/exit execution logic.

### Changed

- `src/hunter/__init__.py` — version bumped to `0.7.0-dev`.


### Added

- `src/hunter/execution/models.py` — Execution Bridge Models (Step 1).
  - `ExecutionState` enum: ENABLED, BLOCKED, DRY_RUN_ONLY, UNKNOWN.
  - `ExecutionMode` enum: LONG_RESEARCH_ONLY, SHORT_RESEARCH_ONLY, BLOCK_ALL, DRY_RUN_ONLY.
  - `ExecutionBridgeConfig` with MVP-4 safety validation (dry_run_required=True, live_trading_enabled=False, etc.).
  - `ExecutionInputRefs` for audit trail references to decision output.
  - `ExecutionSafetyFlags` with human_override_required (default false) and max_context_age_seconds (default 300).
  - `ExecutionContext` with version field default "1.0" for backward-compatible contract evolution.
  - `ExecutionContext.blocked()` fail-closed factory producing BLOCKED + BLOCK_ALL + dry_run True + version "1.0".
  - All models frozen/immutable with __post_init__ validation.
  - 49 execution model tests, all passing.

- `src/hunter/execution/engine.py` — Execution Bridge Engine (Step 2).
  - `build_execution_context()` — main entry point implementing all 15 fail-closed rules from SPEC-005 in priority order.
  - `validate_execution_inputs()` — validates DecisionOutput against all safety constraints.
  - `is_stale_decision()` — checks DecisionOutput age against stale_decision_minutes threshold.
  - `map_decision_to_execution_mode()` — maps DecisionAction to ExecutionMode.
  - `build_safety_flags()` — constructs ExecutionSafetyFlags with all defaults safe.
  - All successful paths produce DRY_RUN_ONLY (ENABLED reserved for future).
  - All blocked paths produce BLOCKED + BLOCK_ALL + dry_run=True.
  - Missing/invalid/stale/unsafe inputs all block by default.
  - input_refs populated with decision timestamp and source on successful paths.
  - 45 execution engine tests, all passing.

- `src/hunter/execution/writer.py` — Execution Context Writer (Step 3).
  - `execution_context_to_dict()` — serializes all 14 ExecutionContext fields to JSON-compatible dict.
  - `atomic_write_json()` — atomic temp-file write with os.replace(), parent directory creation, cleanup on failure.
  - `write_execution_context()` — writes to `data/execution/current_execution_context.json` by default.
  - ISO-8601 timestamp serialization, enum string serialization.
  - safety_flags, input_refs, data_quality, version all preserved in JSON output.
  - 20 execution writer tests, all passing.

- `tests/test_execution/test_integration.py` — Integration Tests (Step 4).
  - 30 end-to-end integration tests.
  - Full pipeline: DecisionOutput → build_execution_context() → write_execution_context() → JSON verification.
  - Long-only research enable scenario (ENABLE_LONG_ONLY_RESEARCH → DRY_RUN_ONLY + LONG_RESEARCH_ONLY).
  - Short-only research enable scenario (ENABLE_SHORT_ONLY_RESEARCH → DRY_RUN_ONLY + SHORT_RESEARCH_ONLY).
  - Block scenarios: BLOCK_ALL, MANUAL_REVIEW, stale, missing, invalid, blocked decision state.
  - Unsafe config rejection tests: dry_run=False, live_trading=True, exchange=True, freqtrade=True all raise ValueError.
  - JSON output verification: all 18 fields, enum strings, safety_flags, version "1.0", ISO-8601 timestamps.
  - Atomic write tests with tmp_path, nested directory creation, no production path usage.
  - Safety tests: no network, no trading logic, no JSON input reading, no Freqtrade runtime, all flags safe.

- Final Review and Polish (Step 5).
  - All 29 review checklist items verified and passing.
  - No issues found. No fixes applied.
  - Full test suite: 538 tests passing.

### Safety

- No application code modified during integration tests or review.
- No config YAML created for execution bridge.
- No JSON Schema files created.
- No DecisionOutput JSON reading used.
- No Freqtrade strategy class created.
- No trading execution logic added.
- No Binance integration.
- No live trading enabled.
- No network calls.
- All safety flags remain False or safe (dry_run=True).
- All blocked paths produce BLOCKED + BLOCK_ALL.
- ENABLED state exists in enum but is never emitted by MVP-4.

### Next

- MVP-5 Planning — Freqtrade Integration design.

## 0.4.0-dev — MVP-5 Planning — Freqtrade Integration Design (Complete)

### Added

- `specs/SPEC-006-Freqtrade-Integration.md` — Freqtrade Integration specification (design-only, no code).
  - Consumes in-memory `ExecutionContext` from MVP-4.
  - Future input reference: `data/execution/current_execution_context.json`.
  - Outputs: `data/freqtrade/current_freqtrade_context.json`.
  - Dry-run only: the only non-blocked state is `DRY_RUN_READY`.
  - Fail-closed `BLOCK_ALL` by default for all unsafe inputs.
  - `FreqtradeBridgeState` enum design: DISABLED, DRY_RUN_READY, BLOCKED, UNKNOWN.
  - `FreqtradeBridgeMode` enum design: LONG_RESEARCH_ONLY, SHORT_RESEARCH_ONLY, BLOCK_ALL.
  - `FreqtradeBridgeContext` with 18 fields including version default `"1.0"`.
  - 17 fail-closed rules in deterministic priority order.
  - `configs/freqtrade_bridge.yaml` future design only (not created in MVP-5).
  - `schemas/freqtrade_bridge_context.schema.json` future design only (not created in MVP-5).
  - Mock Freqtrade strategy deferred to MVP-6 or later.
  - No code implemented yet.

### Safety

- No code implemented for Freqtrade Integration.
- No Binance integration.
- No real Freqtrade runtime integration.
- No strategy class.
- No trading logic (pairlist, order, stake, leverage, stoploss, ROI, entry, exit).
- No live trading.
- No leverage.
- No shorting.
- No API keys.
- No network calls.

### Next

- MVP-5 Step 1 — Freqtrade Bridge Models.

## 0.4.0-dev — MVP-5 Step 1 — Freqtrade Bridge Models (Complete)

### Added

- `src/hunter/freqtrade_bridge/models.py` — Freqtrade Bridge Models.
  - `FreqtradeBridgeState` enum: DISABLED, DRY_RUN_READY, BLOCKED, UNKNOWN.
  - `FreqtradeBridgeMode` enum: LONG_RESEARCH_ONLY, SHORT_RESEARCH_ONLY, BLOCK_ALL.
  - `FreqtradeBridgeConfig` with 12 fields and MVP-5 safety validation.
  - `FreqtradeBridgeInputRefs` for execution context audit trail references.
  - `FreqtradeBridgeSafetyFlags` with 10 safety fields and `to_dict()` for JSON serialization.
  - `FreqtradeBridgeDataQuality` with freshness, validity, validation errors, and `to_dict()`.
  - `FreqtradeBridgeContext` with 18 fields, version default `"1.0"`, fail-closed by default.
  - `FreqtradeBridgeContext.blocked()` factory producing BLOCKED + BLOCK_ALL + dry_run=True + version `"1.0"`.
  - All models frozen/immutable with `__post_init__` validation.
  - 62 Freqtrade bridge model tests, all passing.
  - Full test suite: 600 tests passing.

### Safety

- No Freqtrade Bridge Engine exists yet.
- No Freqtrade Bridge Writer exists yet.
- No config YAML created.
- No JSON Schema files created.
- No ExecutionContext JSON reading.
- No Binance integration.
- No real Freqtrade runtime integration.
- No strategy class.
- No trading logic (pairlist, order, stake, leverage, stoploss, ROI, entry, exit).
- No live trading.
- No leverage.
- No shorting.
- No API keys.
- No network calls.

### Next

- MVP-5 Step 2 — Freqtrade Bridge Engine.

## 0.4.0-dev — MVP-5 Step 2 — Freqtrade Bridge Engine (Complete)

### Added

- `src/hunter/freqtrade_bridge/engine.py` — Freqtrade Bridge Engine.
  - `build_freqtrade_bridge_context()` — main entry point consuming in-memory `ExecutionContext`.
  - `validate_freqtrade_bridge_inputs()` — 12 fail-closed rules in priority order.
  - `is_stale_execution_context()` — checks ExecutionContext age against stale threshold.
  - `map_execution_to_bridge_mode()` — maps ExecutionMode to FreqtradeBridgeState/Mode.
  - `build_safety_flags()` — constructs FreqtradeBridgeSafetyFlags from ExecutionContext.
  - All unsafe inputs produce BLOCKED + BLOCK_ALL with descriptive reason codes.
  - DRY_RUN_ONLY + LONG_RESEARCH_ONLY → DRY_RUN_READY + LONG_RESEARCH_ONLY.
  - DRY_RUN_ONLY + SHORT_RESEARCH_ONLY → DRY_RUN_READY + SHORT_RESEARCH_ONLY.
  - BLOCK_ALL → BLOCKED + BLOCK_ALL.
  - UNKNOWN → BLOCKED + BLOCK_ALL.
  - Checks both ExecutionContext direct fields and nested safety_flags for safety.
  - 57 Freqtrade bridge engine tests, all passing.
  - Full test suite: 657 tests passing.

### Safety

- No Freqtrade Bridge Writer exists yet.
- No config YAML created.
- No JSON Schema files created.
- No ExecutionContext JSON reading.
- No Binance integration.
- No real Freqtrade runtime integration.
- No strategy class.
- No trading logic (pairlist, order, stake, leverage, stoploss, ROI, entry, exit).
- No live trading.
- No leverage.
- No shorting.
- No API keys.
- No network calls.
- No JSON reading or writing.

### Next

- MVP-5 Step 3 — Freqtrade Bridge Writer.

## 0.4.0-dev — MVP-5 Step 3 — Freqtrade Bridge Writer (Complete)

### Added

- `src/hunter/freqtrade_bridge/writer.py` — Freqtrade Bridge Writer.
  - `freqtrade_bridge_context_to_dict()` — serializes all 18 FreqtradeBridgeContext fields to JSON-compatible dict.
  - `atomic_write_json()` — atomic temp-file write with `os.replace()`, parent directory creation, cleanup on failure.
  - `write_freqtrade_bridge_context()` — writes to `data/freqtrade/current_freqtrade_context.json` by default.
  - ISO-8601 timestamp serialization with `Z` suffix.
  - Enum string serialization via `.value`.
  - `safety_flags` serialization via `to_dict()` with all 10 fields.
  - `data_quality` serialization via `to_dict()` with freshness, validity, validation errors.
  - `input_refs` nested dict with `execution_context_timestamp` and `execution_context_version`.
  - `version` always `"1.0"`.
  - `reason_codes` list of strings.
  - 25 Freqtrade bridge writer tests, all passing.
  - Full test suite: 682 tests passing.

### MVP-5 Step 4 — Freqtrade Bridge Integration Tests

- `tests/test_freqtrade_bridge/test_integration.py` — 40 integration tests.
  - End-to-end flow: ExecutionContext → `build_freqtrade_bridge_context()` → `write_freqtrade_bridge_context()`.
  - Long research dry-run-ready scenario: DRY_RUN_ONLY + LONG_RESEARCH_ONLY → DRY_RUN_READY + LONG_RESEARCH_ONLY.
  - Short research dry-run-ready scenario: DRY_RUN_ONLY + SHORT_RESEARCH_ONLY → DRY_RUN_READY + SHORT_RESEARCH_ONLY.
  - Fail-closed blocked scenarios: BLOCK_ALL, stale, missing, blocked state, dry_run false, live trading true, exchange true, freqtrade enabled true, dry_run_only mode.
  - JSON output verification: all 18 fields present, enum values as strings, version "1.0", ISO-8601 timestamps, safety_flags with all 10 fields, input_refs, data_quality, reason_codes.
  - Atomic write and path tests: no temp files left, nested directory creation, no production path used, overwrite existing file.
  - Safety checks: no network, no trading logic, no Freqtrade runtime, no strategy, no leverage, no shorting, no live trading, no real orders, no exchange, no freqtrade runtime, dry_run always true, no JSON input reading.
  - 40 integration tests, all passing.
  - Full test suite: 722 tests passing.
  - No config YAML created.
  - No JSON Schema created.
  - No ExecutionContext JSON reading used.
  - No Freqtrade strategy class created.
  - No Binance integration.
  - No real Freqtrade runtime integration.
  - No trading execution logic.
  - No live trading enabled.
  - No leverage enabled.
  - No shorting enabled.
  - No API keys.
  - No network calls.
  - Next step: MVP-5 Step 5 — Final Review and Polish.

### MVP-5 Complete — Freqtrade Integration Boundary

- SPEC-007 Freqtrade Strategy Contract design finalized and polished.
  - Strategy contract states, modes, StrategyContext, fail-closed rules, reason codes defined.
  - Future config design: `configs/strategy_contract.yaml`.
  - Future schema design: `schemas/strategy_context.schema.json`.
  - PlantUML component and flow diagrams included.
  - Implementation split into 5 steps: Models, Engine, Writer, Integration Tests, Final Review.
  - No MVP-6 code implemented yet.
  - Full test suite: 722 tests passing.
- MVP-6 Step 1 — Strategy Contract Models complete.
  - `src/hunter/strategy_contract/__init__.py` — public API exports.
  - `src/hunter/strategy_contract/models.py` — 7 model types.
    - `StrategyContractState` enum: DISABLED, DRY_RUN_READY, BLOCKED, UNKNOWN.
    - `StrategyContractMode` enum: LONG_RESEARCH_ONLY, SHORT_RESEARCH_ONLY, BLOCK_ALL.
    - `StrategyContractConfig` with 14 fields and MVP-6 safety validation.
    - `StrategyContractInputRefs` with path validation.
    - `StrategyContractSafetyFlags` with 9 safety fields and `to_dict()` for JSON serialization.
    - `StrategyContractDataQuality` with 4 quality fields and `to_dict()` for JSON serialization.
    - `StrategyContext` with 18 fields, version default "1.0", `blocked()` fail-closed factory, `is_blocking()` method.
  - 15 deterministic reason codes: MISSING_BRIDGE_CONTEXT, INVALID_BRIDGE_CONTEXT, BRIDGE_NOT_DRY_RUN_READY, BRIDGE_MODE_BLOCK_ALL, DRY_RUN_DISABLED, LIVE_TRADING_ENABLED, REAL_ORDERS_ENABLED, LEVERAGE_ENABLED, SHORTING_ENABLED, STALE_BRIDGE_CONTEXT, UNSUPPORTED_BRIDGE_MODE, LONG_RESEARCH_ALLOWED, SHORT_RESEARCH_ALLOWED, DEFAULT_BLOCK_ALL, CALCULATION_ERROR.
  - `tests/test_strategy_contract/__init__.py` — test package.
  - `tests/test_strategy_contract/test_models.py` — 84 model tests, all passing.
  - Full test suite: 806 tests passing (722 existing + 84 new).
  - No engine, no writer, no integration tests, no config YAML, no JSON schema, no strategy class, no Freqtrade runtime, no Binance, no API keys, no live trading, no real orders, no leverage, no shorting.
- MVP-6 Step 2 — Strategy Contract Engine complete.
  - `src/hunter/strategy_contract/engine.py` — 5 engine functions.
    - `build_strategy_context(...)` — main entry point, implements 14 fail-closed rules.
    - `validate_strategy_contract_inputs(...)` — deterministic priority-ordered validation, returns first blocking reason only.
    - `is_stale_bridge_context(...)` — checks timestamp validity and age against threshold.
    - `map_bridge_to_strategy_mode(...)` — maps bridge mode to strategy contract mode.
    - `build_safety_flags(...)` — constructs safety flags from config with safe defaults.
  - `src/hunter/strategy_contract/__init__.py` — updated exports.
  - `tests/test_strategy_contract/test_engine.py` — 72 engine tests, all passing.
  - Allowed mappings: LONG_RESEARCH_ONLY → LONG_RESEARCH_ONLY, SHORT_RESEARCH_ONLY → SHORT_RESEARCH_ONLY.
  - Blocking mappings: unsafe/invalid/stale/unsupported → BLOCK_ALL.
  - Full test suite: 878 tests passing (806 existing + 72 new).
  - No writer, no integration tests, no config YAML, no JSON schema, no strategy class, no Freqtrade runtime, no Binance, no API keys, no live trading, no real orders, no leverage, no shorting.
- MVP-6 Step 3 — Strategy Context Writer complete.
  - `src/hunter/strategy_contract/writer.py` — 3 writer functions + default path constant.
    - `DEFAULT_STRATEGY_CONTEXT_PATH = data/strategy/current_strategy_context.json`.
    - `strategy_context_to_dict(...)` — serializes StrategyContext to JSON-compatible dict.
    - `atomic_write_json(...)` — temp-file + os.replace atomic write, auto cleanup on failure.
    - `write_strategy_context(...)` — entry point, writes to default or custom path.
  - `src/hunter/strategy_contract/__init__.py` — updated exports.
  - `tests/test_strategy_contract/test_writer.py` — 36 writer tests, all passing.
  - JSON serialization: ISO-8601 UTC timestamps ending with Z, enum string values, reason_codes as list, nested input_refs/safety_flags/data_quality as dicts, version "1.0".
  - Full test suite: 914 tests passing (878 existing + 36 new).
  - No integration tests, no config YAML, no JSON schema, no strategy class, no Freqtrade runtime, no Binance, no API keys, no live trading, no real orders, no leverage, no shorting.
- MVP-6 Step 4 — Strategy Contract Integration Tests complete.
  - `tests/test_strategy_contract/test_integration.py` — 45 integration tests, all passing.
  - Integration coverage:
    - Allowed flows: LONG_RESEARCH_ONLY, SHORT_RESEARCH_ONLY (full pipeline engine + writer + JSON verification).
    - Blocked flows: missing bridge context, BLOCKED bridge state, UNKNOWN bridge state, DISABLED bridge state, BLOCK_ALL bridge mode, stale bridge context.
    - Unsafe flags blocked: dry_run false, live_trading_enabled true, real_orders_enabled true, leverage_enabled true, shorting_enabled true.
    - JSON output verification: ISO-8601 timestamps, enum strings, reason_codes list, input_refs/safety_flags/data_quality dicts, version "1.0", blocked vs allowed reason codes.
    - Atomic/path verification: custom tmp_path, nested directory creation, overwrite existing file, no temp files left, default path constant.
    - Safety absence checks: no config YAML, no JSON schema, no strategy class, no Freqtrade runtime, no Binance, no API keys, no live trading, no real orders, no leverage, no shorting, no entry/exit logic, no trading fields.
  - Full test suite: 959 tests passing (914 existing + 45 new).
  - No application code changed.
  - No config YAML, no JSON schema, no strategy class, no Freqtrade runtime, no Binance, no API keys, no live trading, no real orders, no leverage, no shorting.
- MVP-6 Step 4 — Strategy Contract Integration Tests complete.
  - `tests/test_strategy_contract/test_integration.py` — 45 integration tests, all passing.
  - Integration coverage:
    - Allowed flows: LONG_RESEARCH_ONLY, SHORT_RESEARCH_ONLY (full pipeline engine + writer + JSON verification).
    - Blocked flows: missing bridge context, BLOCKED bridge state, UNKNOWN bridge state, DISABLED bridge state, BLOCK_ALL bridge mode, stale bridge context.
    - Unsafe flags blocked: dry_run false, live_trading_enabled true, real_orders_enabled true, leverage_enabled true, shorting_enabled true.
    - JSON output verification: ISO-8601 timestamps, enum strings, reason_codes list, input_refs/safety_flags/data_quality dicts, version "1.0", blocked vs allowed reason codes.
    - Atomic/path verification: custom tmp_path, nested directory creation, overwrite existing file, no temp files left, default path constant.
    - Safety absence checks: no config YAML, no JSON schema, no strategy class, no Freqtrade runtime, no Binance, no API keys, no live trading, no real orders, no leverage, no shorting, no entry/exit logic, no trading fields.
  - Full test suite: 959 tests passing (914 existing + 45 new).
  - No application code changed.
  - No config YAML, no JSON schema, no strategy class, no Freqtrade runtime, no Binance, no API keys, no live trading, no real orders, no leverage, no shorting.
- MVP-6 Step 5 — Final Review and Polish complete.
  - All 60 final review checklist items passed.
  - No issues found. No fixes applied.
  - Version bumped to 0.6.0-dev.
- SPEC-008 Freqtrade Dry-Run Strategy Adapter design finalized and polished.
  - AdapterState enum: DISABLED, DRY_RUN_READY, BLOCKED, UNKNOWN.
  - AdapterMode enum: LONG_RESEARCH_ONLY, SHORT_RESEARCH_ONLY, BLOCK_ALL.
  - AdapterSignalIntent enum: ALLOW_LONG_RESEARCH_SIGNAL, ALLOW_SHORT_RESEARCH_SIGNAL, BLOCK_SIGNAL, NO_SIGNAL.
  - AdapterDecisionContext with 22 fields including adapter_runtime_allowed, freqtrade_runtime_allowed, strategy_class_allowed, entry_signal_allowed, exit_signal_allowed, order_execution_allowed.
  - 15 deterministic reason codes: MISSING_STRATEGY_CONTEXT, INVALID_STRATEGY_CONTEXT, STRATEGY_CONTRACT_NOT_DRY_RUN_READY, STRATEGY_CONTRACT_MODE_BLOCK_ALL, DRY_RUN_DISABLED, LIVE_TRADING_ENABLED, REAL_ORDERS_ENABLED, LEVERAGE_ENABLED, SHORTING_ENABLED, STALE_STRATEGY_CONTEXT, UNSUPPORTED_STRATEGY_MODE, LONG_RESEARCH_SIGNAL_ALLOWED, SHORT_RESEARCH_SIGNAL_ALLOWED, DEFAULT_BLOCK_SIGNAL, CALCULATION_ERROR.
  - Fail-closed adapter rules: 11 blocking + 2 allowed + 1 fallback.
  - Future config design: `configs/strategy_adapter.yaml`.
  - Future output: `data/strategy_adapter/current_adapter_decision.json`.
  - Future schema: `schemas/strategy_adapter_decision.schema.json`.
  - PlantUML component and adapter flow diagrams included.
  - Implementation split into 5 steps: Models, Engine, Writer, Integration Tests, Final Review.
  - No MVP-7 code implemented yet.
  - Full test suite: 959 tests passing.
- MVP-7 Step 1 — Strategy Adapter Models complete.
  - `src/hunter/strategy_adapter/__init__.py` — public API exports.
  - `src/hunter/strategy_adapter/models.py` — 8 model types.
    - `AdapterState` enum: DISABLED, DRY_RUN_READY, BLOCKED, UNKNOWN.
    - `AdapterMode` enum: LONG_RESEARCH_ONLY, SHORT_RESEARCH_ONLY, BLOCK_ALL.
    - `AdapterSignalIntent` enum: ALLOW_LONG_RESEARCH_SIGNAL, ALLOW_SHORT_RESEARCH_SIGNAL, BLOCK_SIGNAL, NO_SIGNAL.
    - `AdapterConfig` with 17 fields and MVP-7 safety validation.
    - `AdapterInputRefs` with path validation.
    - `AdapterSafetyFlags` with 12 safety fields and `to_dict()` for JSON serialization.
    - `AdapterDataQuality` with 4 quality fields and `to_dict()` for JSON serialization.
    - `AdapterDecisionContext` with 22 fields, version default "1.0", `blocked()` fail-closed factory, `is_blocking()` method.
  - 15 deterministic reason codes: MISSING_STRATEGY_CONTEXT, INVALID_STRATEGY_CONTEXT, STRATEGY_CONTRACT_NOT_DRY_RUN_READY, STRATEGY_CONTRACT_MODE_BLOCK_ALL, DRY_RUN_DISABLED, LIVE_TRADING_ENABLED, REAL_ORDERS_ENABLED, LEVERAGE_ENABLED, SHORTING_ENABLED, STALE_STRATEGY_CONTEXT, UNSUPPORTED_STRATEGY_MODE, LONG_RESEARCH_SIGNAL_ALLOWED, SHORT_RESEARCH_SIGNAL_ALLOWED, DEFAULT_BLOCK_SIGNAL, CALCULATION_ERROR.
  - `tests/test_strategy_adapter/__init__.py` — test package.
  - `tests/test_strategy_adapter/test_models.py` — 94 model tests, all passing.
  - Full test suite: 1053 tests passing (959 existing + 94 new).
  - No engine, no writer, no integration tests, no config YAML, no JSON schema, no deployable strategy class, no Freqtrade runtime, no Binance, no API keys, no live trading, no real orders, no leverage, no shorting, no entry/exit execution logic.
- MVP-7 Step 2 — Strategy Adapter Engine complete.
  - `src/hunter/strategy_adapter/engine.py` — 6 engine functions.
    - `build_adapter_decision_context(...)` — main entry point implementing all 11 fail-closed adapter rules + 2 allowed + 1 fallback.
    - `validate_adapter_inputs(...)` — deterministic priority-ordered validation, returns first blocking reason only.
    - `is_stale_strategy_context(...)` — checks timestamp validity (missing/naive/None → stale) and age against threshold.
    - `map_strategy_to_adapter_mode(...)` — maps `StrategyContractMode` → `AdapterMode`.
    - `map_strategy_to_signal_intent(...)` — maps `StrategyContractMode` → `AdapterSignalIntent`.
    - `build_safety_flags(...)` — constructs `AdapterSafetyFlags` from config with safe defaults.
  - Allowed mappings: `LONG_RESEARCH_ONLY` → `ALLOW_LONG_RESEARCH_SIGNAL`, `SHORT_RESEARCH_ONLY` → `ALLOW_SHORT_RESEARCH_SIGNAL`.
  - Blocking mappings: all unsafe/invalid/stale/unsupported → `BLOCK_SIGNAL`.
  - `src/hunter/strategy_adapter/__init__.py` — updated exports.
  - `tests/test_strategy_adapter/test_engine.py` — 75 engine tests, all passing.
  - Full test suite: 1128 tests passing (1053 existing + 75 new).
  - No writer, no integration tests, no config YAML, no JSON schema, no deployable strategy class, no Freqtrade runtime, no Binance, no API keys, no live trading, no real orders, no leverage, no shorting, no entry/exit execution logic.

- MVP-7 Step 4 — Strategy Adapter Integration Tests (Complete).
  - `tests/test_strategy_adapter/test_integration.py` — 45 integration tests, all passing.
  - Integration coverage: allowed LONG_RESEARCH_ONLY and SHORT_RESEARCH_ONLY signal flows; blocked missing, BLOCKED, UNKNOWN, DISABLED strategy contract states; blocked BLOCK_ALL strategy contract mode; blocked stale StrategyContext; blocked unsafe flags (dry_run false, live_trading_enabled true, real_orders_enabled true, leverage_enabled true, shorting_enabled true); JSON output verification; atomic/path verification; safety absence checks.
  - Full test suite: 1214 tests passing (1169 existing + 45 new).
  - No application code changed. No config YAML. No JSON schema. No deployable strategy class. No Freqtrade runtime. No Binance. No API keys. No live trading. No real orders. No leverage. No shorting. No entry/exit execution logic.

- MVP-7 Step 3 — Adapter Decision JSON Writer (Complete).
  - `src/hunter/strategy_adapter/writer.py` — writer functions.
  - `src/hunter/strategy_adapter/__init__.py` — updated exports.
  - `tests/test_strategy_adapter/test_writer.py` — 41 writer tests, all passing.
  - `DEFAULT_ADAPTER_DECISION_PATH = data/strategy_adapter/current_adapter_decision.json`.
  - `adapter_decision_context_to_dict()` — serializes `AdapterDecisionContext` to JSON-compatible dict.
  - `atomic_write_json()` — atomic temp-file write with `os.replace()`, parent directory creation, cleanup on failure.
  - `write_adapter_decision_context()` — writes to `data/strategy_adapter/current_adapter_decision.json` by default.
  - ISO-8601 UTC timestamp serialization ending with `Z`.
  - Enum string serialization: `adapter_state`, `adapter_mode`, `signal_intent`.
  - `reason_codes` serialized as `list[str]`.
  - Nested `input_refs`, `safety_flags`, `data_quality` serialized as dicts.
  - `version` is `"1.0"`.
  - Full test suite: 1169 tests passing (1128 existing + 41 new).
  - No integration tests yet. No config YAML. No JSON schema. No deployable strategy class. No Freqtrade runtime. No Binance. No API keys. No live trading. No real orders. No leverage. No shorting. No entry/exit execution logic.

- MVP-6 — Freqtrade Strategy Contract complete.
  - SPEC-007 finalized and polished.
  - Strategy contract produces dry-run-only fail-closed StrategyContext for future strategy-facing consumers.
  - Default output path: `data/strategy/current_strategy_context.json`.
  - Full test suite: 959 tests passing.
  - No Binance integration.
  - No real Freqtrade runtime integration.
  - No strategy class.
  - No config YAML.
  - No JSON schema.
  - No API keys.
  - No live trading.
  - No real orders.
  - No leverage.
  - No shorting.
- SPEC-006 Freqtrade Integration design complete and reviewed.
- Step 1 Freqtrade Bridge Models complete: `src/hunter/freqtrade_bridge/models.py` with 62 tests.
- Step 2 Freqtrade Bridge Engine complete: `src/hunter/freqtrade_bridge/engine.py` with 57 tests.
- Step 3 Freqtrade Bridge Writer complete: `src/hunter/freqtrade_bridge/writer.py` with 25 tests.
- Step 4 Integration Tests complete: `tests/test_freqtrade_bridge/test_integration.py` with 40 tests.
- Step 5 Final Review complete: all 35 checklist items verified, no issues found, no fixes required.
- Full test suite: 722 tests passing.
- Output path: `data/freqtrade/current_freqtrade_context.json`.
- Dry-run only: all outputs have `dry_run=True` and `live_trading_enabled=False`.
- Fail-closed: all unsafe inputs produce `BLOCKED` + `BLOCK_ALL`.
- No Binance integration.
- No real Freqtrade runtime integration.
- No strategy class.
- No trading logic (pairlist, order, stake, leverage, stoploss, ROI, entry, exit).
- No live trading.
- No leverage.
- No shorting.
- No API keys.
- No network calls.
- Next step: MVP-6 Planning — Freqtrade Strategy Contract design.

### Safety

- No config YAML created.
- No JSON Schema files created.
- No ExecutionContext JSON reading.
- No Binance integration.
- No real Freqtrade runtime integration.
- No strategy class.
- No trading logic (pairlist, order, stake, leverage, stoploss, ROI, entry, exit).
- No live trading.
- No leverage.
- No shorting.
- No API keys.
- No network calls.
- No JSON input reading.

### Next

- MVP-5 Step 4 — Integration Tests.

## 0.4.0-dev — MVP-4 Step 4 — Integration Tests (Complete)

### Added

- `tests/test_execution/test_integration.py` created with 30 end-to-end integration tests.
- Full pipeline: DecisionOutput → `build_execution_context()` → `write_execution_context()` → JSON verification.
- Long-only research enable scenario (`ENABLE_LONG_ONLY_RESEARCH` → `DRY_RUN_ONLY` + `LONG_RESEARCH_ONLY`).
- Short-only research enable scenario (`ENABLE_SHORT_ONLY_RESEARCH` → `DRY_RUN_ONLY` + `SHORT_RESEARCH_ONLY`).
- Block scenarios: `BLOCK_ALL`, `MANUAL_REVIEW`, stale, missing, invalid, blocked decision state.
- Unsafe config rejection tests: `dry_run=False`, `live_trading=True`, `exchange=True`, `freqtrade=True` all raise `ValueError`.
- JSON output verification: all 18 fields, enum strings, `safety_flags`, version `"1.0"`, ISO-8601 timestamps.
- Atomic write tests with `tmp_path`, nested directory creation, no production path usage.
- Safety tests: no network, no trading logic, no JSON input reading, no Freqtrade runtime, all flags safe.
- 30 integration tests, all passing.
- Full test suite: 538 tests passing (508 existing + 30 new).

### Safety

- No application code modified.
- No config YAML created.
- No JSON Schema files created.
- No DecisionOutput JSON reading used.
- No Freqtrade strategy class created.
- No trading execution logic added.
- No Binance integration.
- No live trading enabled.
- No network calls.
- All safety flags remain `False` or safe (`dry_run=True`).

### Next

- MVP-4 Step 5 — Final Review and Polish.

## 0.4.0-dev — MVP-4 Step 3 — Execution Context Writer (Complete)

### Added

- `src/hunter/execution/writer.py` created with JSON serialization and atomic output writer.
- `execution_context_to_dict()` — serializes all 14 ExecutionContext fields to JSON-compatible dict.
- `atomic_write_json()` — atomic temp-file write with `os.replace()`, parent directory creation, cleanup on failure.
- `write_execution_context()` — writes to `data/execution/current_execution_context.json` by default.
- ISO-8601 timestamp serialization with Z suffix.
- Enum string serialization for all enum fields.
- `input_refs` serialized as nested dict with `decision_timestamp` and `decision_source`.
- `safety_flags` serialized as nested dict with all 6 safety fields.
- `data_quality` serialized as nested dict with all 4 quality flags.
- `version` field preserved for backward-compatible contract evolution.
- 20 execution writer tests, all passing.
- Full test suite: 508 tests passing.

### Safety

- No Binance integration.
- No Freqtrade runtime integration.
- No strategy class.
- No trading logic.
- No live trading.
- No API keys.
- No network calls.
- No JSON input reading.
- Atomic writes prevent partial output on failure.

### Next

- MVP-4 Step 4 — Integration Tests.

## 0.4.0-dev — MVP-4 Step 2 — Execution Bridge Engine (Complete)

### Added

- `src/hunter/execution/engine.py` created with deterministic execution bridge engine.
- `build_execution_context()` — main entry point implementing all 15 fail-closed rules from SPEC-005 in priority order.
- `validate_execution_inputs()` — validates DecisionOutput against all safety constraints.
- `is_stale_decision()` — checks DecisionOutput age against `stale_decision_minutes` threshold.
- `map_decision_to_execution_mode()` — maps DecisionAction to ExecutionMode.
- `build_safety_flags()` — constructs ExecutionSafetyFlags with all defaults safe.
- All successful paths produce `DRY_RUN_ONLY` (ENABLED reserved for future).
- All blocked paths produce `BLOCKED` + `BLOCK_ALL` + `dry_run=True`.
- Missing/invalid/stale/unsafe inputs all block by default.
- `input_refs` populated with decision timestamp and source on successful paths.
- 45 execution engine tests, all passing.
- Full test suite: 488 tests passing.

### Safety

- No Binance integration.
- No Freqtrade runtime integration.
- No strategy class.
- No trading logic.
- No live trading.
- No API keys.
- No network calls.
- No JSON reading or writing.
- No exchange connection.
- No order execution.

### Next

- MVP-4 Step 3 — Execution Bridge Writer.

## 0.4.0-dev — MVP-4 Step 1 — Execution Bridge Models (Complete)

### Added

- `src/hunter/execution/models.py` created with immutable execution bridge models.
- `ExecutionState` enum: ENABLED, BLOCKED, DRY_RUN_ONLY, UNKNOWN.
- `ExecutionMode` enum: LONG_RESEARCH_ONLY, SHORT_RESEARCH_ONLY, BLOCK_ALL, DRY_RUN_ONLY.
- `ExecutionBridgeConfig` with MVP-4 safety validation (dry_run_required=True, live_trading_enabled=False, etc.).
- `ExecutionInputRefs` for audit trail references to decision output.
- `ExecutionSafetyFlags` with `human_override_required` (default false) and `max_context_age_seconds` (default 300).
- `ExecutionContext` with `version` field default `"1.0"` for backward-compatible contract evolution.
- `ExecutionContext.blocked()` fail-closed factory producing BLOCKED + BLOCK_ALL + dry_run True + version "1.0".
- All models frozen/immutable with `__post_init__` validation.
- 49 execution model tests, all passing.
- Full test suite: 443 tests passing.

### Safety

- No Binance integration.
- No Freqtrade runtime integration.
- No strategy class.
- No trading logic.
- No live trading.
- No API keys.
- No network calls.
- No JSON reading or writing.

### Next

- MVP-4 Step 2 — Execution Bridge Engine.

## 0.4.0-dev — MVP-4 Execution Bridge (Design Complete)

### Added

- SPEC-005 — Execution Bridge / Freqtrade Integration design document created and reviewed.
- Execution Bridge consumes in-memory `DecisionOutput` from MVP-3.
- Future input path documented: `data/decision/current_decision.json`.
- Output path defined: `data/execution/current_execution_context.json`.
- `ExecutionState` enum design: ENABLED, BLOCKED, DRY_RUN_ONLY, UNKNOWN.
- `ExecutionMode` enum design: LONG_RESEARCH_ONLY, SHORT_RESEARCH_ONLY, BLOCK_ALL, DRY_RUN_ONLY.
- `ExecutionContext` model design with `version` field default `"1.0"` for backward-compatible contract evolution.
- `max_context_age_seconds` default `300` documented as consumer-side stale rejection guard.
- `human_override_required` default `false` documented as reserved for future DRY_RUN_ONLY → ENABLED transitions.
- Fail-closed by default: all bad inputs produce BLOCKED + BLOCK_ALL.
- Dry-run only: all successful paths produce DRY_RUN_ONLY, ENABLED reserved for future.
- 15 priority-ordered fail-closed rules defined.
- Config file design: `configs/execution_bridge.yaml` (single file, no sprawl).
- JSON Schema design: `schemas/execution_context.schema.json` (future work only, not implemented yet).
- Freqtrade compatibility contract documented for future MVP-5+ implementation.
- All 27 review checklist items passed.

### Safety

- No code implemented yet.
- No Binance integration.
- No Freqtrade runtime integration.
- No strategy class.
- No trading logic.
- No live trading.
- No API keys.
- No real data fetching.

### Next

- MVP-4 Step 2 — Execution Bridge Engine.

## 0.4.0-dev — MVP-4 Step 1 — Execution Bridge Models (Complete)

### Added

- `src/hunter/execution/models.py` created with immutable execution bridge models.
- `ExecutionState` enum: ENABLED, BLOCKED, DRY_RUN_ONLY, UNKNOWN.
- `ExecutionMode` enum: LONG_RESEARCH_ONLY, SHORT_RESEARCH_ONLY, BLOCK_ALL, DRY_RUN_ONLY.
- `ExecutionBridgeConfig` with MVP-4 safety validation (dry_run_required=True, live_trading_enabled=False, etc.).
- `ExecutionInputRefs` for audit trail references to decision output.
- `ExecutionSafetyFlags` with `human_override_required` (default false) and `max_context_age_seconds` (default 300).
- `ExecutionContext` with `version` field default `"1.0"` for backward-compatible contract evolution.
- `ExecutionContext.blocked()` fail-closed factory producing BLOCKED + BLOCK_ALL + dry_run True + version "1.0".
- All models frozen/immutable with `__post_init__` validation.
- 49 execution model tests, all passing.
- Full test suite: 443 tests passing.

### Safety

- No Binance integration.
- No Freqtrade runtime integration.
- No strategy class.
- No trading logic.
- No live trading.
- No API keys.
- No network calls.
- No JSON reading or writing.

### Next

- MVP-4 Step 2 — Execution Bridge Engine.

## 0.3.0-dev — MVP-3 Decision Layer (Complete)

### Added

- SPEC-004 — Decision Layer design document created, clarified, and reviewed.
- Decision Models: `DecisionState`, `DecisionAction`, `DecisionConfig`, `DecisionInputRefs`, `DecisionOutput` with `block_all()` fail-closed factory.
- Decision Engine: `make_decision()` with 14 priority-ordered fail-closed rules.
- Decision Writer: `decision_to_dict()`, `atomic_write_json()`, `write_decision_output()` with atomic temp-file writes.
- Integration tests: DecisionOutput → make_decision → write_decision_output end-to-end pipeline.
- Default output: `BLOCK` + `BLOCK_ALL` + confidence `0.0` on all bad inputs.
- Allow cases: `BULL` + `LONG_ONLY` + healthy breadth → `ENABLE_LONG_ONLY_RESEARCH`; `BEAR` + `SHORT_ONLY` + weak breadth → `ENABLE_SHORT_ONLY_RESEARCH`.
- All other states (`SIDEWAYS`, `TRANSITION`, conflict, stale) → `BLOCK_ALL`.
- `REVIEW` state reserved for future, never emitted by default.
- Config file design: `configs/decision.yaml` (single file).
- JSON Schema design: `schemas/decision.schema.json` (future work only).
- All 20 review checklist items passed.
- Full test suite: 394 tests passing.

### Safety

- No Binance integration.
- No Freqtrade integration.
- No trading logic.
- No live trading.
- No API keys.
- No network calls.
- No JSON input reading.

### Next

- MVP-4 Execution Bridge design and implementation.

## 0.2.0-dev — MVP-2 Market State (Complete)

### Added

- SPEC-003 — Market State Regime & Breadth design document created, reviewed, and finalized with all fixes applied.
- Market State Models: `RegimeState`, `RiskState`, `AllowedMode`, `OutputStatus`, `DataQuality`, `RegimeOutput`, `BreadthOutput` with `invalid()` fail-closed factories.
- Indicator Utilities: `safe_divide`, `percent_change`, `simple_moving_average`, `exponential_moving_average`, `ema_slope_pct`, `is_rising`, `is_falling`, `is_flat` — pure standard-library functions.
- Regime Engine: deterministic `btc_trend_score`, `bearish_btc_trend_score`, `eth_trend_score`, `breadth_confirmation_score`, `classify_regime()` with fail-closed `UNKNOWN` + `NONE` behavior.
- Breadth Engine: deterministic `breadth_score` with weighted formula, universe filtering, invalid symbol exclusion.
- JSON Output Writers: `regime_to_dict()`, `breadth_to_dict()`, `atomic_write_json()`, `write_regime_output()`, `write_breadth_output()` with atomic temp-file writes and ISO-8601 timestamps.
- All 17 review checklist items passed.
- Full test suite: 278 tests passing.

### Safety

- No Binance integration.
- No Freqtrade integration.
- No trading logic.
- No live trading.
- No API keys.
- No network calls.
- No storage integration.

### Next

- MVP-3 Decision Layer design and implementation.

## 0.1.0-dev — MVP-1 Data Foundation (Complete)

### Added

- Python project structure: `src/hunter/` package with `config`, `data`, `core`, `engines` modules.
- `pyproject.toml` with project metadata, `pydantic` and `pyyaml` dependencies.
- `requirements.txt` and `requirements-dev.txt` with pytest dependencies.
- `.gitignore` excluding Python cache, secrets, runtime data, and local config.
- `tests/` directory at repo root with `test_config`, `test_data`, `test_core`, `fixtures`.
- `__version__ = "0.2.0-dev"` in `src/hunter/__init__.py`.
- SQLiteStorage implementation with `DataStorage` ABC.
- Config models with Pydantic validation.
- Logging setup with structlog and JSON output.
- Test fixtures for config and data layers.
- Full test suite: 91 tests passing.

### Safety

- No trading logic exists yet.
- No Binance connection exists yet.
- No Freqtrade integration exists yet.
- No live trading is enabled.
- No API keys or exchange secrets should be stored in the repository.

### Next

- MVP-2 Market State design and implementation.

## 0.0.0 — MVP-0 Project Foundation (Complete)

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

### MVP-1 Step 5 — SQLite Storage Layer (Complete)

- `src/hunter/data/schema.sql` with 5 tables:
  - `market_symbols` — Symbol registry with base/quote assets
  - `candles` — OHLCV data with unique constraint on (symbol, timeframe, open_time)
  - `funding_rates` — Funding rate history with unique constraint on (symbol, funding_time)
  - `open_interest` — Open interest snapshots
  - `collection_metadata` — Freshness tracking with upsert support
- Indexes on common query patterns: `idx_candles_symbol_timeframe_time`, `idx_funding_symbol_time`, `idx_oi_symbol_time`, `idx_meta_symbol_type`
- `src/hunter/data/storage.py` with `DataStorage` ABC and `SQLiteStorage` implementation
  - `DataStorage` ABC: 9 abstract methods (`initialize`, `save_klines`, `get_klines`, `get_latest_kline`, `save_funding_rates`, `get_funding_rates`, `save_collection_metadata`, `get_collection_metadata`, `is_data_fresh`)
  - `SQLiteStorage` uses Python standard library `sqlite3` only (no external dependencies)
  - `save_klines()` / `save_funding_rates()` use `INSERT OR IGNORE` for deduplication
  - `is_data_fresh()` checks metadata age against `max_age_seconds`
- `tests/test_data/test_storage.py` with 19 tests using temporary SQLite database files
  - All tests pass, no network calls, no Binance connection, no Freqtrade connection

### MVP-1 Step 6 — Final Safety Tests and MVP-1 Completion (Complete)

- Final review found config loader returning `dict` instead of `HunterConfig` when merging YAML
- Fixed `load_config()` to use `_deep_update()` + `model_validate()` for safe nested merging
- Fixed secret detection to scan merged dict before Pydantic strips extra fields
- Fixed config tests to use `raw_dict` parameter for secret injection
- Fixed missing `import sys` in logging tests
- Fixed `test_sets_log_level` to check root logger level
- Commit `dd3ea99`: config loader bugfix and test fixes
- All 91 tests now pass (0 failures)
- MVP-1 Data Foundation is complete

### Next

- MVP-2 Market State: Regime Engine and Market Breadth Engine design.

## 0.3.0-dev — MVP-2 Market State Design (Complete)

### Added

- `specs/SPEC-003-Market-State-Regime-Breadth.md` with complete MVP-2 design:
  - Regime Engine design with 5 states (BULL, BEAR, SIDEWAYS, TRANSITION, UNKNOWN)
  - Market Breadth Engine design with universe filtering and invalid symbol rules
  - Deterministic scoring formulas (no ML, no optimization, no curve fitting):
    - `btc_trend_score`, `bearish_btc_trend_score`, `eth_trend_score` (0–100)
    - `breadth_confirmation_score` (0–100)
    - `breadth_score` (0–100) with weighted component formula
    - `confidence` (0.0–1.0) = min(primary_score, confirmation_score) / 100
  - EMA slope formula: `ema_slope_pct = ((ema_current - ema_n_candles_ago) / ema_n_candles_ago) * 100`
  - Fail-closed behavior: all bad data → UNKNOWN + NONE + confidence 0
  - Pipeline order: Breadth Engine runs first, Regime Engine consumes breadth output
  - Timeframe-aware stale data: `stale_threshold_candles: 2` with `timeframe_duration` multiplier
  - `configs/market_state.yaml` as single config standard (no separate regime/breadth YAML)
  - JSON Schema design section for future `schemas/regime.schema.json` and `schemas/breadth.schema.json`
  - Test plan for regime, breadth, and safety tests
  - MVP-1 interface references: DataStorage ABC, SQLiteStorage, KlineData, HunterConfig

### Safety

- No trading logic exists yet.
- No Binance connection exists yet.
- No Freqtrade integration exists yet.
- No live trading is enabled.
- No API keys or exchange secrets stored in repository.
- No code implemented yet — design only.

### Next

- MVP-2 implementation planning: Step 1 — Market State Models.

### MVP-2 Step 1 — Market State Models (Complete)

- `src/hunter/market_state/__init__.py` created
- `src/hunter/market_state/models.py` created with frozen dataclasses:
  - Enums: `RegimeState` (BULL, BEAR, SIDEWAYS, TRANSITION, UNKNOWN)
  - Enums: `RiskState` (RISK_ON, RISK_OFF, NEUTRAL, UNKNOWN)
  - Enums: `AllowedMode` (LONG_ONLY, SHORT_ONLY, NONE)
  - Enums: `OutputStatus` (VALID, INVALID)
  - `DataQuality` — immutable flags for missing, stale, insufficient_history, insufficient_universe
  - `RegimeOutput` — frozen output model with `__post_init__` validation:
    - confidence range: 0.0–1.0
    - score ranges: 0–100
    - `RegimeOutput.unknown()` fail-closed factory: UNKNOWN + NONE + confidence 0
  - `BreadthOutput` — frozen output model with `__post_init__` validation:
    - breadth_score range: 0–100
    - percentage fields range: 0.0–1.0
    - `BreadthOutput.invalid()` fail-closed factory: INVALID + UNKNOWN health + score 0
- `tests/test_market_state/__init__.py` created
- `tests/test_market_state/test_models.py` with 37 tests:
  - Enum value verification
  - Valid creation with boundary values
  - Validation failures (out-of-range confidence, scores, percentages)
  - Fail-closed factory defaults and custom overrides
  - Immutability (frozen dataclass)
- Full test suite: 128 tests passing (91 existing + 37 new)

### Safety

- No trading logic exists yet.
- No Binance connection exists yet.
- No Freqtrade integration exists yet.
- No live trading is enabled.
- No API keys or exchange secrets stored in repository.
- No Regime Engine logic exists yet.
- No Breadth Engine logic exists yet.
- No indicators exist yet.

### MVP-2 Step 2 — Indicator Utilities (Complete)

- `src/hunter/market_state/indicators.py` created with pure, deterministic functions:
  - `safe_divide(numerator, denominator, default)` — division with zero-safe fallback
  - `percent_change(current, previous, default)` — percentage change with zero-safe fallback
  - `simple_moving_average(values, period)` — SMA with sliding window; returns empty list if insufficient data
  - `exponential_moving_average(values, period)` — EMA with standard multiplier formula; returns empty list if insufficient data
  - `ema_slope_pct(ema_values, lookback)` — EMA slope percentage matching SPEC-003 formula exactly
  - `is_rising(slope_pct, threshold_pct)` — slope > threshold
  - `is_falling(slope_pct, threshold_pct)` — slope < -threshold
  - `is_flat(slope_pct, threshold_pct)` — abs(slope) <= threshold
- Standard library only — no pandas, no external dependencies
- All functions are stateless, no network, no storage, no trading logic
- `tests/test_market_state/test_indicators.py` with 50 tests:
  - Safe divide: normal, zero denominator, custom default, negatives, floats
  - Percent change: normal, negative, zero previous, no change, double
  - SMA: basic, period 1, insufficient data, exact period, invalid period, empty values, large values
  - EMA: basic, period 1, insufficient data, exact period, invalid period, empty values, known values
  - EMA slope: rising, falling, flat, lookback 1, lookback 5 (SPEC default), zero denominator, insufficient data, invalid lookback
  - Slope direction: rising/falling/flat at and around thresholds, combined state checks
  - Safety: no network imports, no trading terms in module source
- Full test suite: 178 tests passing (128 existing + 50 new)

### Safety

- No trading logic exists yet.
- No Binance connection exists yet.
- No Freqtrade integration exists yet.
- No live trading is enabled.
- No API keys or exchange secrets stored in repository.
- No Regime Engine logic exists yet.
- No Breadth Engine logic exists yet.
- No JSON writers exist yet.

### MVP-2 Step 3 — Regime Engine (Complete)

- `src/hunter/market_state/regime.py` created with deterministic Regime Engine:
  - `RegimeConfig` — frozen dataclass with all SPEC-003 defaults (ema periods, thresholds, lookbacks)
  - `calculate_btc_trend_score(btc_closes, config)` — bullish conditions / total * 100, 0–100
  - `calculate_bearish_btc_trend_score(btc_closes, config)` — bearish conditions / total * 100, 0–100
  - `calculate_eth_trend_score(eth_closes, config)` — optional ETH confirmation, returns 0 + `ETH_DATA_UNAVAILABLE` if missing
  - `calculate_breadth_confirmation_score(...)` — optional breadth confirmation based on regime direction
  - `classify_regime(...)` — main classifier with fail-closed behavior:
    - Missing BTC candles → `UNKNOWN` + `NONE` + confidence 0
    - Insufficient BTC history → `UNKNOWN` + `NONE` + confidence 0
    - Invalid candle values (≤0) → `UNKNOWN` + `NONE` + confidence 0
    - Bull detected → `BULL` + `LONG_ONLY` + confidence from confirmation
    - Bear detected → `BEAR` + `SHORT_ONLY` + confidence from confirmation
    - Weak trend → `SIDEWAYS` + `NONE`
    - Low confidence (<0.6) → `TRANSITION` + `NONE`
  - Uses `ema_slope_pct` from indicators.py (matches SPEC-003 formula exactly)
  - No ML, no optimization, no curve fitting
- `tests/test_market_state/test_regime.py` with 37 tests:
  - RegimeConfig defaults and custom values
  - BTC trend score: bullish high, bearish low, flat medium, missing, insufficient, invalid, range
  - Bearish BTC trend score: bearish high, bullish low, missing
  - ETH trend score: None unavailable, bullish, missing
  - Breadth confirmation: bull confirmation, bear confirmation, None returns zero, no confirmation
  - Fail-closed: missing BTC, insufficient history, invalid values, calculation error blocks
  - Regime detection: bull, bear, sideways, transition with ETH, bull with breadth, confidence range, allowed mode NONE when invalid
  - Reason codes: bull, bear, unknown all have non-empty reason codes
  - Safety: no network imports, no trading terms, no Binance, no Freqtrade
- Full test suite: 215 tests passing (178 existing + 37 new)

### Safety

- No trading logic exists yet.
- No Binance connection exists yet.
- No Freqtrade integration exists yet.
- No live trading is enabled.
- No API keys or exchange secrets stored in repository.
- No Breadth Engine logic exists yet.
- No JSON writers exist yet.

### MVP-2 Step 4 — Breadth Engine (Complete)

- `src/hunter/market_state/breadth.py` created with deterministic Market Breadth Engine:
  - `BreadthConfig` — frozen dataclass with all SPEC-003 defaults (min_universe_size, EMA periods, thresholds, lookbacks)
  - `filter_valid_symbols(universe_candles, config)` — validates symbols per SPEC-003 rules:
    - Exclude missing candles, insufficient history, close ≤ 0, negative volume, calculation failures
    - Returns (valid_symbols, invalid_count, reason_codes)
  - `calculate_percent_above_ema(valid_candles, ema_period)` — percentage of symbols with close > EMA
  - `calculate_percent_ema_rising(valid_candles, ema_period, lookback, threshold)` — percentage with rising EMA slope
  - `calculate_advancing_declining_pct(valid_candles)` — advancing vs declining percentages (flat excluded)
  - `calculate_outperforming_btc_pct(valid_candles, btc_closes, lookback_days)` — percentage outperforming BTC return
  - `calculate_breadth_score(...)` — weighted formula per SPEC-003, clamped 0–100:
    - above_ema20_pct * 25 + above_ema50_pct * 20 + ema20_rising_pct * 20 + ema50_rising_pct * 15 + advancing_pct * 10 + outperforming_btc_7d_pct * 10
  - `calculate_breadth(universe_candles, btc_closes, ...)` — main breadth function with fail-closed behavior:
    - Missing universe → `INVALID` + `UNKNOWN` health + score 0
    - Missing BTC → `INVALID` + `UNKNOWN` health + score 0
    - Insufficient universe (< min_universe_size) → `INVALID` + `UNKNOWN` health + score 0
    - Invalid BTC values → `INVALID` + `UNKNOWN` health + score 0
    - Valid data → `VALID` + market health (RISK_ON/RISK_OFF/NEUTRAL) + breadth_score 0–100
  - Uses `exponential_moving_average`, `ema_slope_pct`, `percent_change` from indicators.py
  - No ML, no optimization, no curve fitting
- `tests/test_market_state/test_breadth.py` with 44 tests:
  - BreadthConfig defaults, custom values, frozen immutability
  - filter_valid_symbols: all valid, missing excluded, insufficient excluded, invalid price excluded, negative excluded
  - calculate_percent_above_ema: all above, none above, half above, empty
  - calculate_percent_ema_rising: all rising, none rising, empty
  - calculate_advancing_declining_pct: all advancing, all declining, mixed, empty, flat excluded
  - calculate_outperforming_btc_pct: all outperform, none outperform, half, empty, missing BTC, insufficient BTC
  - calculate_breadth_score: max 100, min 0, mixed, clamped above 100, clamped below 0, deterministic
  - calculate_breadth: missing universe, missing BTC, insufficient universe, invalid BTC, valid calculation, score range, reason codes, risk_on, risk_off, invalid symbols counted
  - Safety: no network calls, no trading logic
- Full test suite: 259 tests passing (215 existing + 44 new)

### Safety

- No trading logic exists yet.
- No Binance connection exists yet.
- No Freqtrade integration exists yet.
- No live trading is enabled.
- No API keys or exchange secrets stored in repository.
- No JSON writers exist yet.
- No schema files exist yet.

### MVP-2 Step 5 — JSON Output Writers (Complete)

- `src/hunter/market_state/writer.py` created with JSON serialization and atomic output writers:
  - `regime_to_dict(output)` — Serializes `RegimeOutput` to JSON-compatible dict:
    - ISO-8601 timestamps with Z suffix (e.g., `2026-06-17T12:00:00Z`)
    - Enum values serialized as strings (e.g., `BULL`, `LONG_ONLY`, `VALID`)
    - `DataQuality` and `reason_codes` preserved
  - `breadth_to_dict(output)` — Serializes `BreadthOutput` to JSON-compatible dict:
    - Same timestamp and enum serialization as regime
    - All percentage fields and counts preserved
  - `atomic_write_json(data, target_path)` — Atomic file write:
    - Writes to temp file in same directory first
    - Uses `os.replace()` for atomic rename
    - Creates parent directories if missing
    - Cleans up temp file on failure (no partial output)
    - Uses `fsync` for durability
  - `write_regime_output(output, target_path)` — Writes to `data/regime/current_regime.json` by default
  - `write_breadth_output(output, target_path)` — Writes to `data/breadth/current_breadth.json` by default
  - Output matches SPEC-003 JSON contract exactly
- `tests/test_market_state/test_writer.py` with 19 tests:
  - regime_to_dict: valid regime, unknown regime, ISO-8601 format, naive datetime, enum strings, data quality, reason codes
  - breadth_to_dict: valid breadth, invalid breadth
  - atomic_write_json: writes file, creates directories, no partial on failure, unicode encoding
  - write_regime_output: default path, parent directories
  - write_breadth_output: default path, parent directories
  - Safety: no network calls, no trading logic
- Full test suite: 278 tests passing (259 existing + 19 new)

### Safety

- No trading logic exists yet.
- No Binance connection exists yet.
- No Freqtrade integration exists yet.
- No live trading is enabled.
- No API keys or exchange secrets stored in repository.
- No JSON schema validation exists yet.
- No storage integration exists yet.
- No report templates exist yet.

### MVP-2 Complete

MVP-2 Market State implementation is fully complete. All 6 steps finished:
- Step 1: Market State Models (37 tests)
- Step 2: Indicator Utilities (50 tests)
- Step 3: Regime Engine (37 tests)
- Step 4: Breadth Engine (44 tests)
- Step 5: JSON Output Writers (19 tests)
- Step 6: Final review and polish
- Version bumped to 0.3.0-dev
- Full test suite: 278 tests passing

### SPEC-004 — Decision Layer Design (Complete)

- SPEC-004 exists and is reviewed (19 checklist items all passed)
- Decision Layer consumes in-memory `RegimeOutput` and `BreadthOutput` from MVP-2
- Decision Layer produces `data/decision/current_decision.json`
- `DecisionState` enum designed: `ALLOW`, `BLOCK`, `REVIEW` (reserved for future), `UNKNOWN`
- `DecisionAction` enum designed: `ENABLE_LONG_ONLY_RESEARCH`, `ENABLE_SHORT_ONLY_RESEARCH`, `BLOCK_ALL`, `MANUAL_REVIEW`
- `DecisionOutput` model with 14 fields including audit trail (`input_refs`, `data_quality`)
- `DecisionConfig` with frozen defaults: `min_regime_confidence: 0.60`, `stale_input_minutes: 120`
- 14 deterministic fail-closed rules in priority order (all block by default)
- `configs/decision.yaml` design: single config file with threshold controls
- `schemas/decision.schema.json` design: future validation schema (not implemented yet)
- `REVIEW` state reserved for future manual-review workflows; default is `BLOCK_ALL`
- Staleness is output-level (engine output age), not candle-level (handled by MVP-2)
- No MVP-3 code has been implemented yet
- No Binance integration
- No Freqtrade integration
- No trading logic
- No live trading

### MVP-3 Step 1 — Decision Models (Complete)

- `src/hunter/decision/__init__.py` created
- `src/hunter/decision/models.py` created with frozen dataclasses:
  - Enums: `DecisionState` (ALLOW, BLOCK, REVIEW, UNKNOWN)
  - Enums: `DecisionAction` (ENABLE_LONG_ONLY_RESEARCH, ENABLE_SHORT_ONLY_RESEARCH, BLOCK_ALL, MANUAL_REVIEW)
  - `DecisionConfig` — frozen dataclass with `__post_init__` validation:
    - min_regime_confidence: 0.60 (range 0.0–1.0)
    - min_breadth_score_for_long: 60 (range 0–100)
    - max_breadth_score_for_short: 40 (range 0–100)
    - stale_input_minutes: 120 (positive integer)
    - transition_action: BLOCK_ALL, conflict_action: BLOCK_ALL
  - `DecisionInputRefs` — frozen dataclass for audit trail references to consumed inputs
  - `DecisionOutput` — frozen output model with `__post_init__` validation:
    - confidence range: 0.0–1.0
    - regime_confidence range: 0.0–1.0
    - breadth_score range: 0–100
    - `DecisionOutput.block_all()` fail-closed factory: BLOCK + BLOCK_ALL + confidence 0.0
- `tests/test_decision/test_models.py` with 32 tests:
  - Enum value verification
  - DecisionConfig defaults, custom values, and boundary validation
  - Valid DecisionOutput creation with all 14 fields
  - Validation failures (out-of-range confidence, regime_confidence, breadth_score)
  - Fail-closed factory defaults and custom overrides
  - Immutability (frozen dataclass)
- Full test suite: 310 tests passing (278 existing + 32 new)

### Safety

- No trading logic exists yet.
- No Binance connection exists yet.
- No Freqtrade integration exists yet.
- No live trading is enabled.
- No API keys or exchange secrets stored in repository.
- No Decision Engine logic exists yet.
- No Decision Writer exists yet.
- No config YAML exists yet.

### MVP-3 Step 2 — Decision Engine (Complete)

- `src/hunter/decision/engine.py` created with deterministic fail-closed Decision Engine:
  - `make_decision(regime_output, breadth_output, config)` — main entry point implementing all 14 priority rules from SPEC-004
  - `validate_decision_inputs(regime, breadth, config)` — fail-closed validation in priority order:
    - Missing RegimeOutput → BLOCK_ALL (MISSING_REGIME)
    - Missing BreadthOutput → BLOCK_ALL (MISSING_BREADTH)
    - Invalid RegimeOutput status → BLOCK_ALL (INVALID_REGIME)
    - Invalid BreadthOutput status → BLOCK_ALL (INVALID_BREADTH)
    - UNKNOWN regime → BLOCK_ALL (UNKNOWN_REGIME)
    - allowed_mode NONE → BLOCK_ALL (ALLOWED_MODE_NONE)
    - Low regime confidence → BLOCK_ALL (LOW_REGIME_CONFIDENCE)
    - Stale inputs → BLOCK_ALL (STALE_INPUT)
  - `is_stale_output(regime, breadth, stale_input_minutes)` — checks oldest timestamp against threshold
  - `detect_regime_breadth_conflict(regime, breadth)` — detects 4 conflict conditions per SPEC-004:
    - BULL + RISK_OFF, BEAR + RISK_ON, BULL + score < 50, BEAR + score > 50
  - `calculate_decision_confidence(regime, breadth)` — min(regime_confidence, breadth_score / 100)
  - Decision rules (after all fail-closed checks pass):
    - BULL + LONG_ONLY + breadth_score >= min_breadth_score_for_long → ALLOW + ENABLE_LONG_ONLY_RESEARCH
    - BEAR + SHORT_ONLY + breadth_score <= max_breadth_score_for_short → ALLOW + ENABLE_SHORT_ONLY_RESEARCH
    - SIDEWAYS → BLOCK_ALL (SIDEWAYS_NO_DIRECTION)
    - TRANSITION → BLOCK_ALL (TRANSITION_UNCERTAIN) or custom transition_action
    - Conflicts → BLOCK_ALL (CONFLICTING_SIGNALS) or custom conflict_action
    - Default → BLOCK_ALL (DEFAULT_BLOCK)
  - Data quality aggregation: logical OR of RegimeOutput and BreadthOutput data_quality flags
  - Input refs populated with timestamps and source labels for audit trail
- `tests/test_decision/test_engine.py` with 50 tests:
  - validate_decision_inputs: missing regime, missing breadth, invalid status, UNKNOWN, NONE mode, low confidence, stale, valid, data quality aggregation
  - is_stale_output: fresh, old regime, old breadth, uses oldest timestamp
  - detect_conflict: bull+risk_off, bear+risk_on, bull+low_score, bear+high_score, no conflict cases
  - calculate_confidence: high/high, low/high, high/low, perfect, zero
  - make_decision fail-closed: all 8 fail-closed conditions produce BLOCK_ALL
  - make_decision allow: bull+healthy_breadth allows long, bear+weak_breadth allows short
  - make_decision special: sideways blocks, transition blocks, custom actions, conflicts, default block, input refs, confidence calculation
  - Safety: no network calls, no trading execution logic
- Full test suite: 360 tests passing (310 existing + 50 new)

### Safety

- No trading logic exists yet.
- No Binance connection exists yet.
- No Freqtrade integration exists yet.
- No live trading is enabled.
- No API keys or exchange secrets stored in repository.
- No Decision Writer exists yet.
- No config YAML exists yet.
- No JSON reading or writing in Decision Engine.

### MVP-3 Step 3 — Decision Writer (Complete)

- `src/hunter/decision/writer.py` created with JSON serialization and atomic output writer:
  - `decision_to_dict(output)` — Serializes `DecisionOutput` to JSON-compatible dict:
    - ISO-8601 timestamps with Z suffix (e.g., `2026-06-17T12:00:00Z`)
    - Enum values serialized as strings (e.g., `ALLOW`, `BLOCK_ALL`, `LONG_ONLY`)
    - `DecisionInputRefs` with regime/breadth timestamps and source labels
    - `DataQuality` with all 4 boolean flags
    - `reason_codes` preserved as list
  - `atomic_write_json(data, target_path)` — Atomic file write:
    - Writes to temp file in same directory first
    - Uses `os.replace()` for atomic rename
    - Creates parent directories if missing
    - Cleans up temp file on failure (no partial output)
    - Uses `fsync` for durability
  - `write_decision_output(output, target_path)` — Writes to `data/decision/current_decision.json` by default
  - Output matches SPEC-004 JSON contract exactly
- `tests/test_decision/test_writer.py` with 19 tests:
  - decision_to_dict: valid decision, block decision, ISO-8601 format, naive datetime, enum strings, input refs, data quality, reason codes, JSON roundtrip
  - atomic_write_json: writes file, creates directories, no partial on failure, unicode encoding
  - write_decision_output: default path, parent directories, default path constant, invalid path fails
  - Safety: no network calls, no trading logic
- Full test suite: 379 tests passing (360 existing + 19 new)

### Safety

- No trading logic exists yet.
- No Binance connection exists yet.
- No Freqtrade integration exists yet.
- No live trading is enabled.
- No API keys or exchange secrets stored in repository.
- No config YAML exists yet.
- No JSON schema validation exists yet.
- No JSON input reading in Decision Writer.

### MVP-3 Step 4 — Integration Tests (Complete)

- `tests/test_decision/test_integration.py` created with 15 end-to-end tests:
  - `test_bull_long_healthy_full_pipeline` — BULL + LONG_ONLY + healthy breadth → ENABLE_LONG_ONLY_RESEARCH, JSON written and verified
  - `test_bear_short_weak_full_pipeline` — BEAR + SHORT_ONLY + weak breadth → ENABLE_SHORT_ONLY_RESEARCH, JSON written and verified
  - `test_unknown_regime_blocks_pipeline` — UNKNOWN regime → BLOCK_ALL, JSON verified
  - `test_invalid_breadth_blocks_pipeline` — INVALID breadth → BLOCK_ALL, JSON verified
  - `test_sideways_blocks_pipeline` — SIDEWAYS → BLOCK_ALL, JSON verified
  - `test_transition_blocks_pipeline` — TRANSITION → BLOCK_ALL, JSON verified
  - `test_stale_regime_blocks_pipeline` — stale regime → BLOCK_ALL, JSON verified
  - `test_stale_breadth_blocks_pipeline` — stale breadth → BLOCK_ALL, JSON verified
  - `test_conflict_blocks_pipeline` — conflicting signals → BLOCK_ALL, JSON verified
  - `test_json_contains_all_expected_fields` — all 14 SPEC-004 fields present in JSON output
  - `test_enum_values_are_strings_in_json` — all enum values serialized as strings
  - `test_no_default_production_path_used` — tests use tmp_path, not production data/decision path
  - Safety: no network calls, no trading execution logic, no JSON input reading
- Full test suite: 394 tests passing (379 existing + 15 new)

### Safety

- No trading logic exists yet.
- No Binance connection exists yet.
- No Freqtrade integration exists yet.
- No live trading is enabled.
- No API keys or exchange secrets stored in repository.
- No config YAML exists yet.
- No JSON schema validation exists yet.
- No JSON input reading in integration tests.

### MVP-3 Complete

MVP-3 Decision Layer implementation is fully complete. All 5 steps finished:
- Step 1: Decision Models (32 tests)
- Step 2: Decision Engine (50 tests)
- Step 3: Decision Writer (19 tests)
- Step 4: Integration Tests (15 tests)
- Step 5: Final review and polish
- Version: 0.3.0-dev
- Full test suite: 394 tests passing

### Next

- MVP-4 planning (Execution Bridge / Freqtrade Integration) — design only, no implementation yet.
- Commit current state.
- Review PROJECT.md for MVP-4 scope.
