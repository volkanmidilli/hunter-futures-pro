# Active Task

## Current Task

MVP-6 Step 1 — Strategy Contract Models.

## Status

Not started. Awaiting approval.

MVP-5 Freqtrade Integration Boundary is fully complete with 722 tests passing.
SPEC-007 Freqtrade Strategy Contract design is finalized and polished.

## Scope

Step 1 allowed work:
- Future files: `src/hunter/strategy_contract/__init__.py`, `src/hunter/strategy_contract/models.py`, `tests/test_strategy_contract/test_models.py`.
- Define: StrategyContractState, StrategyContractMode, StrategyContractConfig, StrategyContractInputRefs, StrategyContractSafetyFlags, StrategyContractDataQuality, StrategyContext.
- Model validation tests.

Step 1 not allowed:
- No engine.
- No writer.
- No integration tests.
- No config YAML.
- No JSON schema.
- No Freqtrade runtime.
- No strategy class.
- No Binance.
- No API keys.
- No live trading.
- No real orders.
- No leverage.
- No shorting.

## Previous Task

MVP-5 — Freqtrade Integration Boundary (complete).

## Goal

Implement MVP-6 Strategy Contract Models as the first step toward the Freqtrade Strategy Contract layer.

## Definition of Done

Step 1 is done when:
- All 7 model types are defined and immutable.
- StrategyContext has fail-closed defaults (BLOCKED + BLOCK_ALL + dry_run=True + version "1.0").
- Model validation tests pass.
- Full test suite remains 722+ tests passing.
- No code outside the 3 allowed files.
- No safety constraints violated.

## Next Step After Step 1

MVP-6 Step 2 — Strategy Contract Engine.
