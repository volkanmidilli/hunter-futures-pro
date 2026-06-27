# Active Task

## Current Task

MVP-8 Step 2 — Dry-Run Strategy Runtime Engine.

## Status

Not started. Implementation is not started yet.

MVP-8 Step 1 is complete. All 1308 tests pass. Version 0.7.0-dev.
SPEC-009 design is finalized and polished. All MVP-8 Step 1 models complete.

## Scope

Step 2 future files:
- `src/hunter/dry_run_strategy/engine.py`
- `tests/test_dry_run_strategy/test_engine.py`

Step 2 allowed work:
- `build_dry_run_strategy_runtime_context(...)`
- `validate_dry_run_strategy_inputs(...)`
- `is_stale_adapter_decision_context(...)`
- `map_adapter_to_strategy_mode(...)`
- `map_adapter_to_signal_action(...)`
- `build_safety_flags(...)`
- Deterministic fail-closed reason codes
- Model-only engine tests

Step 2 not allowed:
- No writer.
- No JSON output writing.
- No integration tests.
- No config YAML.
- No JSON schema.
- No deployable Freqtrade strategy class.
- No Freqtrade runtime connection.
- No Binance.
- No real exchange connection.
- No API keys.
- No live trading.
- No real orders.
- No leverage.
- No shorting.
- No real entry/exit execution logic.

## Not Allowed

- No Binance integration.
- No real exchange connection.
- No API keys.
- No live trading.
- No real order execution.
- No leverage.
- No shorting.
- No real entry/exit execution logic.
- No deployable Freqtrade strategy class.
- No Freqtrade runtime connection.
- No config YAML.
- No JSON schema.
- No writer.
- No JSON output writing.
- No integration tests.

## Previous Task

MVP-8 Step 1 — Dry-Run Strategy Runtime Models (complete).
- `src/hunter/dry_run_strategy/__init__.py` — public API exports.
- `src/hunter/dry_run_strategy/models.py` — 8 model types.
  - `DryRunStrategyState` enum: DISABLED, DRY_RUN_READY, BLOCKED, UNKNOWN.
  - `DryRunStrategyMode` enum: LONG_RESEARCH_ONLY, SHORT_RESEARCH_ONLY, BLOCK_ALL.
  - `DryRunSignalAction` enum: EXPOSE_LONG_RESEARCH_SIGNAL, EXPOSE_SHORT_RESEARCH_SIGNAL, BLOCK_SIGNAL, NO_SIGNAL.
  - `DryRunStrategyConfig` with 17 fields and MVP-8 safety validation.
  - `DryRunStrategyInputRefs` with path validation.
  - `DryRunStrategySafetyFlags` with 12 safety fields and `to_dict()` for JSON serialization.
  - `DryRunStrategyDataQuality` with 4 quality fields and `to_dict()` for JSON serialization.
  - `DryRunStrategyRuntimeContext` with 24 fields, version default "1.0", `blocked()` fail-closed factory, `is_blocking()` method.
  - 17 deterministic reason codes.
  - 94 model tests, all passing.
- `tests/test_dry_run_strategy/__init__.py` — test package.
- `tests/test_dry_run_strategy/test_models.py` — 94 model tests, all passing.
- Full suite: 1308 tests passing.
- No engine. No writer. No integration tests. No config YAML. No JSON schema. No deployable strategy class. No Freqtrade runtime.
- No Binance. No API keys. No live trading. No real orders. No leverage. No shorting. No entry/exit execution logic.

## Definition of Done

- [ ] `build_dry_run_strategy_runtime_context()` implements all fail-closed rules from SPEC-009.
- [ ] `validate_dry_run_strategy_inputs()` returns first blocking reason in priority order.
- [ ] `is_stale_adapter_decision_context()` checks timestamp validity and age.
- [ ] `map_adapter_to_strategy_mode()` maps adapter mode to strategy mode.
- [ ] `map_adapter_to_signal_action()` maps adapter signal intent to strategy signal action.
- [ ] `build_safety_flags()` constructs safety flags from config with safe defaults.
- [ ] Engine tests pass.
- [ ] No writer, integration tests, config YAML, JSON schema, or deployable strategy class created.
- [ ] All safety constraints preserved.

## Next Step

MVP-8 Step 3 — Dry-Run Strategy Runtime JSON Writer (after Step 2 complete).

