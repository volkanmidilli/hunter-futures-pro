# Active Task

## Current Task

MVP-5 Planning — Freqtrade Integration design.

## Status

Ready to start.

## Scope

Design-only phase for Freqtrade Integration:
- Define Freqtrade strategy contract that consumes ExecutionContext.
- Design signal generation from execution_state and execution_mode.
- Plan dry-run validation before any live trading enablement.
- Document Freqtrade compatibility requirements.
- No code implementation yet.

## Not Allowed

- No Freqtrade runtime integration.
- No live trading.
- No real data fetching.
- No trading execution.
- No strategy class implementation.
- No Binance integration.

## Previous Task

MVP-4 Execution Bridge — fully complete. All 5 steps finished.
- Step 1: Execution Bridge Models (49 tests)
- Step 2: Execution Bridge Engine (45 tests)
- Step 3: Execution Context Writer (20 tests)
- Step 4: Integration Tests (30 tests)
- Step 5: Final Review and Polish — no issues found
- Full test suite: 538 tests passing
- All 29 review checklist items verified and passing
- No issues found. No fixes applied.
- Version remains 0.4.0-dev
- No Binance integration. No Freqtrade runtime integration. No live trading. No trading logic. No API keys.

## Goal

Design the Freqtrade Integration layer that will consume ExecutionContext from MVP-4 and translate it into Freqtrade-compatible signals, while maintaining all safety constraints.

## Current Scope

MVP-5 Planning only:
- SPEC-006 Freqtrade Integration specification.
- Freqtrade strategy contract design.
- Signal generation mapping from ExecutionContext.
- Dry-run validation workflow design.
- Safety constraint documentation for Freqtrade boundary.
- No code implementation.

## Do Not Do Yet

- Do not implement Freqtrade strategy class.
- Do not implement Freqtrade bot connection.
- Do not enable live trading.
- Do not connect to Binance.
- Do not create API keys.
- Do not write trading execution logic.
- Do not implement actual data collection.

## Definition of Done

MVP-5 planning is done when:
- SPEC-006 exists and is reviewed.
- Freqtrade strategy contract is documented.
- Signal generation mapping is defined.
- Dry-run validation workflow is documented.
- All safety constraints are documented for Freqtrade boundary.
- Review checklist passes.

## Next Step After MVP-5 Planning

MVP-5 Step 1 — Freqtrade Strategy Contract implementation (if approved).
