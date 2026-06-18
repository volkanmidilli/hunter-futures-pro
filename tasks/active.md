# Active Task

## Current Task

MVP-5 Step 1 — Freqtrade Bridge Models.

## Status

Ready to start.

## Scope

Implementation of Freqtrade bridge models only:
- Create `src/hunter/freqtrade/models.py`.
- Implement `FreqtradeBridgeState` enum: DISABLED, DRY_RUN_READY, BLOCKED, UNKNOWN.
- Implement `FreqtradeBridgeMode` enum: LONG_RESEARCH_ONLY, SHORT_RESEARCH_ONLY, BLOCK_ALL.
- Implement `FreqtradeBridgeContext` dataclass with 18 fields.
- All fields with correct defaults (version "1.0", dry_run=True, all others False).
- All enum values serializable as lowercase strings.
- Immutable/frozen models with `__post_init__` validation where appropriate.
- Tests: ~50 tests.
- No engine, no writer, no integration tests in this step.

## Not Allowed

- No Binance integration.
- No real Freqtrade runtime integration.
- No live trading.
- No real data fetching.
- No trading execution.
- No strategy class.
- No leverage.
- No shorting.
- No config YAML creation.
- No JSON Schema creation.
- No JSON input reading from files.
- No network calls.
- No API keys.

## Previous Task

MVP-5 Planning — Freqtrade Integration design. SPEC-006 created, reviewed, and polished.
- FreqtradeBridgeState design: DISABLED, DRY_RUN_READY, BLOCKED, UNKNOWN.
- FreqtradeBridgeMode design: LONG_RESEARCH_ONLY, SHORT_RESEARCH_ONLY, BLOCK_ALL.
- FreqtradeBridgeContext with 18 fields, version "1.0", all safety defaults safe.
- 17 fail-closed rules in deterministic priority order.
- Config file designed for future: `configs/freqtrade_bridge.yaml`.
- JSON Schema designed for future: `schemas/freqtrade_bridge_context.schema.json`.
- Mock Freqtrade strategy deferred to MVP-6 or later.
- No code implemented yet.

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
