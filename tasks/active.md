# Active Task

## Current Task

MVP-6 Step 2 — Strategy Contract Engine.

## Status

Not started. Awaiting approval.

MVP-6 Step 1 Strategy Contract Models is complete. 84 new tests. Full suite 806 tests passing.

## Scope

Step 2 allowed work:
- Future files: `src/hunter/strategy_contract/engine.py`, `tests/test_strategy_contract/test_engine.py`.
- `build_strategy_context(...)` — main entry point consuming in-memory FreqtradeBridgeContext.
- `validate_strategy_contract_inputs(...)` — fail-closed validation in priority order.
- `is_stale_bridge_context(...)` — checks FreqtradeBridgeContext age against stale threshold.
- `map_bridge_to_strategy_mode(...)` — maps bridge state/mode to strategy contract state/mode.
- `build_safety_flags(...)` — constructs StrategyContractSafetyFlags from bridge context.
- Deterministic fail-closed reason codes.
- Model-only engine tests.

Step 2 not allowed:
- No writer.
- No JSON output writing.
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

MVP-6 Step 1 — Strategy Contract Models (complete).
- `src/hunter/strategy_contract/__init__.py` created.
- `src/hunter/strategy_contract/models.py` created with 7 model types.
- `tests/test_strategy_contract/test_models.py` created with 84 tests.
- Full suite: 806 tests passing.

## Goal

Implement MVP-6 Strategy Contract Engine as the second step toward the Freqtrade Strategy Contract layer.

## Definition of Done

Step 2 is done when:
- `build_strategy_context()` implements all 14 fail-closed rules from SPEC-007 in priority order.
- All unsafe inputs produce BLOCKED + BLOCK_ALL with descriptive reason codes.
- DRY_RUN_READY + LONG_RESEARCH_ONLY → DRY_RUN_READY + LONG_RESEARCH_ONLY.
- DRY_RUN_READY + SHORT_RESEARCH_ONLY → DRY_RUN_READY + SHORT_RESEARCH_ONLY.
- Engine tests pass.
- Full test suite remains 806+ tests passing.
- No code outside the 2 allowed files.
- No safety constraints violated.

## Next Step After Step 2

MVP-6 Step 3 — Strategy Context Writer.
