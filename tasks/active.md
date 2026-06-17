# Active Task

## Current Task

MVP-4 Step 1 — Execution Bridge Models.

## Status

Ready to start.

## Scope

Implementation of execution bridge models only:
- Create ExecutionState, ExecutionMode, ExecutionBridgeConfig, ExecutionContext enums and dataclasses.
- Add __post_init__ validation for safety flags.
- Add ExecutionContext.blocked() fail-closed factory.
- Create tests/test_execution_bridge/test_models.py with model tests.
- Target: 25+ tests, all passing.

## Not Allowed

- No Binance integration.
- No Freqtrade runtime integration.
- No live trading.
- No real data fetching.
- No trading execution.
- No strategy class.

## Previous Task

MVP-4 Planning — Execution Bridge / Freqtrade Integration design. Complete. SPEC-005 created and reviewed. All 27 checklist items passed.

## Goal

Implement the Execution Bridge models that define the safe contract layer between Hunter Futures Pro Decision Layer and future Freqtrade execution.

## Current Scope

MVP-4 Step 1 only:
- ExecutionState enum (ENABLED, BLOCKED, DRY_RUN_ONLY, UNKNOWN).
- ExecutionMode enum (LONG_RESEARCH_ONLY, SHORT_RESEARCH_ONLY, BLOCK_ALL, DRY_RUN_ONLY).
- ExecutionBridgeConfig with safety validation.
- ExecutionContext with version field, safety flags, audit trail.
- ExecutionContext.blocked() fail-closed factory.
- Model tests: 25+ tests.

## Do Not Do Yet

- Do not implement Execution Bridge Engine (Step 2).
- Do not implement Execution Context Writer (Step 3).
- Do not implement integration tests (Step 4).
- Do not implement Freqtrade integration.
- Do not create Freqtrade strategy files.
- Do not enable live trading.
- Do not connect to Binance.
- Do not create API keys.
- Do not write trading execution logic.
- Do not implement actual data collection.

## Definition of Done

Step 1 is done when:
- All models exist and are frozen/immutable.
- ExecutionBridgeConfig validates safety defaults and raises on violation.
- ExecutionContext.blocked() produces correct fail-closed defaults.
- 25+ model tests pass.
- Full test suite passes.

## Next Step After Step 1

MVP-4 Step 2 — Execution Bridge Engine.
