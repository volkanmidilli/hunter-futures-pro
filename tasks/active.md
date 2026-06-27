# Active Task

## Current Task

MVP-8 Step 3 — Dry-Run Strategy Runtime JSON Writer.

## Status

Not started. Implementation is not started yet.

MVP-8 Step 2 is complete. All 1401 tests pass. Version 0.7.0-dev.
SPEC-009 design is finalized and polished. All MVP-8 Step 2 engine complete.

## Scope

Step 3 future files:
- `src/hunter/dry_run_strategy/writer.py`
- `tests/test_dry_run_strategy/test_writer.py`

Step 3 allowed work:
- `dry_run_strategy_runtime_context_to_dict(...)`
- `atomic_write_json(...)`
- `write_dry_run_strategy_runtime_context(...)`
- JSON serialization tests
- Atomic write tests
- Default output path: `data/freqtrade_strategy/current_dry_run_strategy_runtime.json`

Step 3 not allowed:
- No engine changes unless import/export only.
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
- No integration tests.

## Previous Task

MVP-8 Step 2 — Dry-Run Strategy Runtime Engine (complete).
- `src/hunter/dry_run_strategy/engine.py` — 6 engine functions.
  - `build_dry_run_strategy_runtime_context()` — fail-closed runtime context builder.
  - `validate_dry_run_strategy_inputs()` — 13 priority-ordered blocking checks.
  - `is_stale_adapter_decision_context()` — timestamp validity + age check.
  - `map_adapter_to_strategy_mode()` — adapter mode → strategy mode mapping.
  - `map_adapter_to_signal_action()` — adapter signal intent → strategy signal action mapping.
  - `build_safety_flags()` — safe defaults from config.
  - Allowed mappings: LONG_RESEARCH_ONLY + ALLOW_LONG_RESEARCH_SIGNAL → EXPOSE_LONG_RESEARCH_SIGNAL; SHORT_RESEARCH_ONLY + ALLOW_SHORT_RESEARCH_SIGNAL → EXPOSE_SHORT_RESEARCH_SIGNAL.
  - Unsafe/invalid/stale/unsupported → BLOCK_SIGNAL.
  - 93 engine tests, all passing.
- `src/hunter/dry_run_strategy/__init__.py` — updated with 6 engine function exports.
- Full suite: 1401 tests passing.
- No writer. No integration tests. No config YAML. No JSON schema. No deployable strategy class. No Freqtrade runtime.
- No Binance. No API keys. No live trading. No real orders. No leverage. No shorting. No entry/exit execution logic.

## Definition of Done

- [ ] `dry_run_strategy_runtime_context_to_dict()` serializes all fields to JSON-compatible dict with ISO-8601 timestamps, enum strings, nested dicts.
- [ ] `atomic_write_json()` writes temp file + os.replace with cleanup on failure.
- [ ] `write_dry_run_strategy_runtime_context()` writes to default path with atomic write.
- [ ] Writer tests pass.
- [ ] No integration tests, config YAML, JSON schema, or deployable strategy class created.
- [ ] All safety constraints preserved.

## Next Step

MVP-8 Step 4 — Integration Tests (after Step 3 complete).

