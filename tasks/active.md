# Active Task

## Current Task

MVP-7 Step 2 — Strategy Adapter Engine.

## Status

Not started. Awaiting approval.

MVP-7 Step 1 is complete. 94 new tests. 1053 total. Version 0.6.0-dev.
SPEC-008 design is finalized and polished. No MVP-7 engine implemented yet.

## Scope

Step 2 allowed work:
- `src/hunter/strategy_adapter/engine.py` — engine functions.
- `tests/test_strategy_adapter/test_engine.py` — engine tests.

Define:
- `build_adapter_decision(...)` — main entry point, implements all fail-closed adapter rules.
- `validate_adapter_inputs(...)` — deterministic priority-ordered validation, returns first blocking reason.
- `is_stale_strategy_context(...)` — checks timestamp validity and age against threshold.
- `map_strategy_to_adapter_mode(...)` — maps strategy contract mode to adapter mode.
- `map_strategy_to_signal_intent(...)` — maps strategy contract mode to signal intent.
- `build_safety_flags(...)` — constructs safety flags from config with safe defaults.

Step 2 not allowed:
- No writer.
- No JSON output writing.
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

MVP-7 Step 1 — Strategy Adapter Models (complete).
- 4 files created: `__init__.py`, `models.py`, `tests/__init__.py`, `test_models.py`.
- 8 model types: AdapterState, AdapterMode, AdapterSignalIntent, AdapterConfig, AdapterInputRefs, AdapterSafetyFlags, AdapterDataQuality, AdapterDecisionContext.
- 15 deterministic reason codes.
- `blocked()` factory, `is_blocking()` method, fail-closed defaults.
- 94 model tests, all passing.
- Full suite: 1053 tests passing.

## Goal

Implement MVP-7 Step 2 — Strategy Adapter Engine.

## Definition of Done

Step 2 is done when:
- All 6 engine functions are defined and deterministic.
- Fail-closed rules are implemented in priority order.
- Allowed mappings: LONG_RESEARCH_ONLY → ALLOW_LONG_RESEARCH_SIGNAL, SHORT_RESEARCH_ONLY → ALLOW_SHORT_RESEARCH_SIGNAL.
- Blocking mappings: all unsafe/invalid/stale/unsupported → BLOCK_SIGNAL.
- All engine tests pass.
- Full test suite: 1053+ tests passing.
- No code outside the allowed files.

## Next Step After Step 2

MVP-7 Step 3 — Adapter Decision JSON Writer (if approved).
