# Active Task

## Current Task

MVP-8 Step 1 — Dry-Run Strategy Runtime Models.

## Status

Not started. Implementation is not started yet.

MVP-7 is complete. All 1214 tests pass. Version 0.7.0-dev.
SPEC-009 design is finalized and polished. All MVP-7 implementation complete.

## Scope

Step 1 future files:
- `src/hunter/dry_run_strategy/__init__.py`
- `src/hunter/dry_run_strategy/models.py`
- `tests/test_dry_run_strategy/__init__.py`
- `tests/test_dry_run_strategy/test_models.py`

Step 1 allowed work:
- `DryRunStrategyState` enum
- `DryRunStrategyMode` enum
- `DryRunSignalAction` enum
- `DryRunStrategyConfig`
- `DryRunStrategyInputRefs`
- `DryRunStrategySafetyFlags`
- `DryRunStrategyDataQuality`
- `DryRunStrategyRuntimeContext`
- Deterministic reason codes
- Model validation tests

Step 1 not allowed:
- No engine.
- No writer.
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

## Previous Task

MVP-7 — Freqtrade Dry-Run Strategy Adapter (complete).
- Step 1 Strategy Adapter Models: 94 tests.
- Step 2 Strategy Adapter Engine: 75 tests.
- Step 3 Adapter Decision JSON Writer: 41 tests.
- Step 4 Integration Tests: 45 tests.
- Step 5 Final Review: 63 checklist items passed. No issues.
- Full suite: 1214 tests passing.
- No config YAML. No JSON schema. No deployable strategy class. No Freqtrade runtime.
- No Binance. No API keys. No live trading. No real orders. No leverage. No shorting. No entry/exit execution logic.

## Definition of Done

- [ ] `DryRunStrategyState`, `DryRunStrategyMode`, `DryRunSignalAction` enums defined.
- [ ] `DryRunStrategyConfig`, `DryRunStrategyInputRefs`, `DryRunStrategySafetyFlags`, `DryRunStrategyDataQuality`, `DryRunStrategyRuntimeContext` models defined.
- [ ] Deterministic reason codes defined.
- [ ] Model validation tests pass.
- [ ] No engine, writer, or integration tests created.
- [ ] No config YAML created.
- [ ] No JSON schema created.
- [ ] No deployable Freqtrade strategy class created.
- [ ] All safety constraints preserved.

## Next Step

MVP-8 Step 2 — Dry-Run Strategy Runtime Engine (after Step 1 complete).

