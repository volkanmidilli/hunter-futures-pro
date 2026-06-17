# Active Task

## Current Task

MVP-3 Planning — Decision Layer (SPEC-004).

## Status

MVP-2 is complete. All 278 tests pass. Version 0.3.0-dev.

## Previous Task

MVP-2 Market State — Complete.

## Goal

Design the Decision Layer: how market state signals (regime, breadth) are translated into execution-ready decisions without trading logic. This is the bridge between Market State (MVP-2) and Execution (MVP-4).

## Current Scope

MVP-3 design only (no code yet):
- SPEC-004 — Decision Layer design document
- Signal aggregation from regime + breadth outputs
- Decision contract (what Freqtrade would consume)
- Risk constraints (position sizing limits, not execution)
- Fail-closed behavior when signals are invalid

## Do Not Do Yet

- Do not write trading logic.
- Do not connect to Binance.
- Do not connect to Freqtrade.
- Do not create API keys.
- Do not enable live trading.
- Do not create production trading rules.
- Do not implement actual data collection.
- Do not implement MVP-3 code until SPEC-004 is approved.

## Definition of Done

MVP-3 design is done when:
- SPEC-004 exists and is reviewed
- Decision contract is defined (JSON output for execution layer)
- Risk constraints are defined (max position, not execution logic)
- Fail-closed behavior is defined
- No trading execution logic exists
- No Freqtrade integration exists
- No live trading is enabled

## Next Step After MVP-3

MVP-4 — Execution Integration (Freqtrade bridge, still no live trading).
