# Active Task

## Current Task

MVP-7 Step 3 — Adapter Decision JSON Writer.

## Status

Not started. Awaiting approval.

MVP-7 Step 2 is complete. 75 new tests. 1128 total. Version 0.6.0-dev.
SPEC-008 design is finalized and polished. No MVP-7 writer implemented yet.

## Scope

Step 3 allowed work:
- `src/hunter/strategy_adapter/writer.py` — writer functions.
- `src/hunter/strategy_adapter/__init__.py` — updated exports.
- `tests/test_strategy_adapter/test_writer.py` — writer tests.

Define:
- `adapter_decision_context_to_dict(...)` — serializes `AdapterDecisionContext` to JSON-compatible dict.
- `atomic_write_json(...)` — atomic temp-file write with `os.replace()`, parent directory creation, cleanup on failure.
- `write_adapter_decision_context(...)` — writes to `data/strategy_adapter/current_adapter_decision.json` by default.
- `DEFAULT_ADAPTER_DECISION_PATH` — default output path constant.

Step 3 not allowed:
- No engine changes (unless import/export only).
- No integration tests.
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

## Previous Task

MVP-7 Step 2 — Strategy Adapter Engine (complete).
- 3 files changed/created: `engine.py`, `__init__.py`, `test_engine.py`.
- 6 engine functions: `build_adapter_decision_context`, `validate_adapter_inputs`, `is_stale_strategy_context`, `map_strategy_to_adapter_mode`, `map_strategy_to_signal_intent`, `build_safety_flags`.
- Deterministic fail-closed validation with first blocking reason only.
- Allowed mappings: `LONG_RESEARCH_ONLY` → `ALLOW_LONG_RESEARCH_SIGNAL`, `SHORT_RESEARCH_ONLY` → `ALLOW_SHORT_RESEARCH_SIGNAL`.
- Blocking mappings: all unsafe/invalid/stale/unsupported → `BLOCK_SIGNAL`.
- 75 engine tests, all passing.
- Full suite: 1128 tests passing.

## Goal

Implement MVP-7 Step 3 — Adapter Decision JSON Writer.

## Definition of Done

Step 3 is done when:
- All 3 writer functions are defined.
- JSON serialization uses ISO-8601 UTC timestamps with Z suffix, enum string values, reason_codes as list, nested dicts.
- Atomic temp-file + `os.replace` writes are implemented.
- Default output path is `data/strategy_adapter/current_adapter_decision.json`.
- All writer tests pass.
- Full test suite: 1128+ tests passing.
- No code outside the allowed files.

## Next Step After Step 3

MVP-7 Step 4 — Strategy Adapter Integration Tests (if approved).
