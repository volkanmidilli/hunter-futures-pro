# Active Task

## Current Task

MVP-6 Step 3 — Strategy Context Writer.

## Status

Not started. Awaiting approval.

MVP-6 Step 2 Strategy Contract Engine is complete. 72 new tests. Full suite 878 tests passing.

## Scope

Step 3 allowed work:
- Future files: `src/hunter/strategy_contract/writer.py`, `tests/test_strategy_contract/test_writer.py`.
- `strategy_context_to_dict(...)` — converts StrategyContext to JSON-serializable dict.
- `atomic_write_json(...)` — temp-file + os.replace atomic write pattern.
- `write_strategy_context(...)` — writes StrategyContext to JSON output path.
- JSON serialization tests.
- Atomic write tests.
- Default output path: `data/strategy/current_strategy_context.json`.

Step 3 not allowed:
- No engine changes unless import/export only.
- No integration tests.
- No config YAML.
- No JSON schema.
- No strategy class.
- No Freqtrade runtime.
- No Binance.
- No API keys.
- No live trading.
- No real orders.
- No leverage.
- No shorting.

## Previous Task

MVP-6 Step 2 — Strategy Contract Engine (complete).
- `src/hunter/strategy_contract/engine.py` created with 5 engine functions.
- `src/hunter/strategy_contract/__init__.py` updated with engine exports.
- `tests/test_strategy_contract/test_engine.py` created with 72 tests.
- Full suite: 878 tests passing.

## Goal

Implement MVP-6 Strategy Context Writer as the third step toward the Freqtrade Strategy Contract layer.

## Definition of Done

Step 3 is done when:
- `strategy_context_to_dict()` produces ISO-8601 timestamps, enum strings, nested dicts for input_refs/safety_flags/data_quality.
- `atomic_write_json()` uses temp-file + os.replace with automatic cleanup on failure.
- `write_strategy_context()` writes to `data/strategy/current_strategy_context.json` by default.
- Writer tests pass.
- Full test suite remains 878+ tests passing.
- No code outside the 2 allowed files.
- No safety constraints violated.

## Next Step After Step 3

MVP-6 Step 4 — Integration Tests.
