# Active Task

## Current Task

MVP-2 Implementation Planning — Market State Models.

## Status

Ready to start.

## Note

MVP-1 Data Foundation is complete. All 91 tests pass.

SPEC-003 MVP-2 Market State design is complete and finalized:
- Regime Engine design with deterministic scoring formulas
- Market Breadth Engine design with universe filtering and invalid symbol rules
- JSON output contracts defined with field ranges
- Fail-closed behavior defined for all failure modes
- Pipeline order defined: Breadth Engine first, then Regime Engine
- Test plan defined for regime, breadth, and safety tests
- No MVP-2 code has been implemented yet

## Previous Task

MVP-1 Data Foundation — Complete.

## Goal

Implement the Market State layer: Regime Engine and Market Breadth Engine, following SPEC-003 design.

## Current Scope

MVP-2 implementation steps (from SPEC-003):

1. Step 1 — Create Market State Models
2. Step 2 — Create Indicator Utilities
3. Step 3 — Create Regime Engine
4. Step 4 — Create Breadth Engine
5. Step 5 — Create JSON Output Writers
6. Step 6 — Create Report Templates
7. Step 7 — Update Project Memory

Immediate next step: Plan MVP-2 Step 1 — Market State Models.

## Do Not Do Yet

- Do not write trading logic.
- Do not connect to Binance.
- Do not connect to Freqtrade.
- Do not create API keys.
- Do not enable live trading.
- Do not create production trading rules.
- Do not implement actual data collection.

## Definition of Done

MVP-2 is done when:

- Regime Engine exists and produces deterministic outputs
- Market Breadth Engine exists and produces deterministic outputs
- JSON outputs can be generated from local/test data
- Fail-closed behavior works for all failure modes
- Tests pass for regime, breadth, indicators, and safety
- No Binance integration exists
- No Freqtrade integration exists
- No trading execution exists

## Next Step After MVP-2

MVP-3 — Strength and Futures Positioning: Relative Strength Engine and Open Interest Engine design.
