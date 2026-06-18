# Active Task

## Current Task

MVP-6 Planning — Freqtrade Strategy Contract design.

## Status

Complete.

MVP-5 Freqtrade Integration Boundary is fully complete with 722 tests passing.

## Scope

Design only. No code implementation.

Next required design document:
- SPEC-007 — Freqtrade Strategy Contract

MVP-6 must begin with design/spec only, not code. The strategy contract defines:
- How a future Freqtrade strategy class reads `data/freqtrade/current_freqtrade_context.json`
- Safety checks the strategy must perform before any trading action
- Enforcement of dry_run, blocked state, and mode restrictions
- Interface between the bridge output and strategy execution

## Not Allowed

- No Binance integration.
- No real Freqtrade runtime integration.
- No live trading.
- No real data fetching.
- No real order execution.
- No leverage.
- No shorting.
- No API keys.
- No strategy class implementation (design only).
- No trading logic implementation (design only).
- No config YAML creation.
- No JSON Schema creation.
- No JSON input reading implementation.
- No network calls.

## Previous Task

MVP-5 — Freqtrade Integration Boundary (complete).

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
