# Active Task

## Current Task

MVP-8 Step 4 — Dry-Run Strategy Runtime Integration Tests.

## Status

Not started. Implementation is not started yet.

MVP-8 Step 3 is complete. All 1443 tests pass. Version 0.7.0-dev.
SPEC-009 design is finalized and polished. All MVP-8 Step 3 writer complete.

## Scope

Step 4 future file:
- `tests/test_dry_run_strategy/test_integration.py`

Step 4 allowed work:
- End-to-end dry-run strategy runtime context build from AdapterDecisionContext.
- Allowed long research signal path.
- Allowed short research signal path.
- Blocked/fail-closed paths.
- Writer output verification using tmp_path only.
- No production data writes except tmp_path tests.
- No runtime/exchange/network calls.

Step 4 not allowed:
- No model changes unless strictly necessary for test compatibility.
- No engine changes unless strictly necessary for test compatibility.
- No writer changes unless strictly necessary for test compatibility.
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
- No model changes unless strictly necessary.
- No engine changes unless strictly necessary.
- No writer changes unless strictly necessary.

## Previous Task

MVP-8 Step 3 — Dry-Run Strategy Runtime JSON Writer (complete).
- `src/hunter/dry_run_strategy/writer.py` — 3 writer functions + default path constant.
  - `DEFAULT_DRY_RUN_STRATEGY_RUNTIME_PATH = data/freqtrade_strategy/current_dry_run_strategy_runtime.json`.
  - `dry_run_strategy_runtime_context_to_dict()` — deterministic JSON-safe serialization with ISO-8601 timestamps, enum values, tuple→list, nested dicts.
  - `atomic_write_json()` — atomic temp-file write with parent directory creation, fsync, os.replace, cleanup on failure.
  - `write_dry_run_strategy_runtime_context()` — default path or custom path, converts + writes atomically.
  - 42 writer tests, all passing.
- `src/hunter/dry_run_strategy/__init__.py` — updated with 4 writer exports.
- Full suite: 1443 tests passing.
- No integration tests. No config YAML. No JSON schema. No deployable strategy class. No Freqtrade runtime.
- No Binance. No API keys. No live trading. No real orders. No leverage. No shorting. No entry/exit execution logic.

## Definition of Done

- [ ] End-to-end dry-run strategy runtime context build from AdapterDecisionContext passes.
- [ ] Allowed long research signal path verified.
- [ ] Allowed short research signal path verified.
- [ ] Blocked/fail-closed paths verified.
- [ ] Writer output verification using tmp_path passes.
- [ ] No production data writes except tmp_path tests.
- [ ] No model/engine/writer changes unless strictly necessary.
- [ ] Integration tests pass.
- [ ] No config YAML, JSON schema, or deployable strategy class created.
- [ ] All safety constraints preserved.

## Next Step

MVP-8 Step 5 — Final Review (after Step 4 complete).

