# Active Task

## Current Task

MVP-7 Step 1 — Strategy Adapter Models.

## Status

Not started. Awaiting approval.

MVP-6 is complete. All 5 steps finished. 959 tests passing. Version 0.6.0-dev.
SPEC-008 design is finalized and polished. No MVP-7 code implemented yet.

## Scope

Step 1 allowed work:
- `src/hunter/strategy_adapter/__init__.py` — public API exports.
- `src/hunter/strategy_adapter/models.py` — model definitions.
- `tests/test_strategy_adapter/__init__.py` — test package.
- `tests/test_strategy_adapter/test_models.py` — model validation tests.

Define:
- `AdapterState` enum: DISABLED, DRY_RUN_READY, BLOCKED, UNKNOWN.
- `AdapterMode` enum: LONG_RESEARCH_ONLY, SHORT_RESEARCH_ONLY, BLOCK_ALL.
- `AdapterSignalIntent` enum: ALLOW_LONG_RESEARCH_SIGNAL, ALLOW_SHORT_RESEARCH_SIGNAL, BLOCK_SIGNAL, NO_SIGNAL.
- `AdapterConfig` with safety validation.
- `AdapterInputRefs` with path validation.
- `AdapterSafetyFlags` with `to_dict()` for JSON serialization.
- `AdapterDataQuality` with `to_dict()` for JSON serialization.
- `AdapterDecisionContext` with 22 fields, version default "1.0", `blocked()` fail-closed factory.
- 15 deterministic reason codes as constants.

Step 1 not allowed:
- No engine.
- No writer.
- No integration tests.
- No config YAML.
- No JSON schema.
- No Freqtrade runtime.
- No deployable strategy class.
- No Binance.
- No API keys.
- No live trading.
- No real orders.
- No leverage.
- No shorting.
- No entry/exit execution logic.

## Previous Task

MVP-7 Planning — SPEC-008 Freqtrade Dry-Run Strategy Adapter design (complete).
- SPEC-008 created, reviewed, polished, and finalized.
- AdapterState, AdapterMode, AdapterSignalIntent, AdapterDecisionContext defined.
- Fail-closed adapter rules, deterministic reason codes, future config/schema/output defined.
- PlantUML component and flow diagrams included.
- 5-step implementation plan defined.
- No code implemented yet.
- No safety constraints violated.

## Goal

Implement MVP-7 Step 1 — Strategy Adapter Models.

## Definition of Done

Step 1 is done when:
- All 8 model types are defined and immutable.
- 15 reason code constants are defined.
- Safety defaults are fail-closed (adapter_state=BLOCKED, adapter_mode=BLOCK_ALL, signal_intent=BLOCK_SIGNAL).
- All model validation tests pass.
- Full test suite: 959+ tests passing.
- No code outside the allowed files.

## Next Step After Step 1

MVP-7 Step 2 — Strategy Adapter Engine (if approved).
