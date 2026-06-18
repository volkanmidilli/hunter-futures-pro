# Active Task

## Current Task

MVP-8 Planning — SPEC-009 Freqtrade Deployable Dry-Run Strategy.

## Status

Not started. Awaiting approval.

MVP-7 is complete. All 1214 tests pass. Version 0.7.0-dev.
SPEC-008 design is finalized and polished. All MVP-7 implementation complete.

## Scope

MVP-8 must begin with design/spec only, not code.
MVP-8 may only design a future deployable dry-run strategy that consumes AdapterDecisionContext safely.

Next required design document:
- SPEC-009 — Freqtrade Deployable Dry-Run Strategy

Suggested MVP-8 title: Freqtrade Deployable Dry-Run Strategy.

## Not Allowed

- No Binance integration.
- No real exchange connection.
- No API keys.
- No live trading.
- No real order execution.
- No leverage.
- No shorting.

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

- [ ] SPEC-009 created and reviewed.
- [ ] No code implementation yet.
- [ ] Design remains dry-run-only and fail-closed.
- [ ] No unsafe integration designed.

## Next Step

MVP-8 Step 1 — Strategy Adapter Models (if approved).

