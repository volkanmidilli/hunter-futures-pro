# Current State

## Project

Hunter Futures Pro

## Version

0.2.0-dev

## Current Phase

MVP-2 — Market State design complete, implementation planning pending.

## Current Status

MVP-0 foundation is complete and committed.

MVP-1 Data Foundation is complete and committed. All 91 tests pass.

MVP-2 Market State design is complete:
- SPEC-003 exists and is finalized
- Regime Engine design is complete with deterministic scoring formulas
- Market Breadth Engine design is complete with universe filtering and invalid symbol rules
- JSON output contracts are defined with field ranges
- Fail-closed behavior is defined for all failure modes
- Pipeline order is defined: Breadth Engine first, then Regime Engine
- Test plan is defined for regime, breadth, and safety tests
- No MVP-2 code has been implemented yet

MVP-2 Step 1 is complete:
- `src/hunter/market_state/models.py` created with frozen dataclasses
- Enums: RegimeState, RiskState, AllowedMode, OutputStatus
- Models: DataQuality, RegimeOutput, BreadthOutput
- Fail-closed factories: RegimeOutput.unknown(), BreadthOutput.invalid()
- Range validation: confidence 0.0–1.0, scores 0–100, percentages 0.0–1.0
- 37 new tests, all passing
- Full test suite: 128 tests passing

No Regime Engine logic exists yet.

No Breadth Engine logic exists yet.

No indicators exist yet.

No trading logic exists yet.

No Binance connection exists yet.

No Freqtrade integration exists yet.

No live trading is enabled.

MVP-2 implementation has started. Step 1 complete.

## Next Step

MVP-2 Step 2 — Indicator Utilities (EMA, slope, percent change).
