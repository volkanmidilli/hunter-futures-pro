# Active Task

## Current Task

MVP-4 Planning — Execution Bridge / Freqtrade Integration design.

## Status

Pending. Waiting for human approval to begin MVP-4 planning.

## Previous Task

MVP-3 — Decision Layer. Complete. All 5 steps finished, 394 tests passing.

## Goal

Design the Execution Bridge that connects Hunter Futures Pro decision outputs to Freqtrade.
This is a design-only phase — no implementation yet.

## Current Scope

MVP-4 planning only:
- Review PROJECT.md for MVP-4 scope
- Identify integration points between Decision Layer and Freqtrade
- Define signal format and handoff protocol
- Design fail-closed behavior for bridge layer
- Create SPEC-005 if needed

## Do Not Do Yet

- Do not implement Freqtrade integration.
- Do not create Freqtrade strategy files.
- Do not enable live trading.
- Do not connect to Binance.
- Do not create API keys.
- Do not write trading execution logic.
- Do not implement actual data collection.

## Definition of Done

MVP-4 planning is done when:
- Design document exists (SPEC-005 or equivalent)
- Integration points are defined
- Signal format is specified
- Fail-closed behavior is documented
- Safety constraints are preserved

## Next Step After Planning

MVP-4 Step 1 — Execution Bridge Models (after design approval).
