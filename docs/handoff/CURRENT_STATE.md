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

MVP-2 Step 2 is complete:
- `src/hunter/market_state/indicators.py` created with pure, deterministic functions
- Functions: safe_divide, percent_change, simple_moving_average, exponential_moving_average, ema_slope_pct, is_rising, is_falling, is_flat
- Standard library only — no pandas, no external dependencies
- All functions are stateless, no network, no storage, no trading logic
- 50 new tests, all passing
- Full test suite: 178 tests passing

No Regime Engine logic exists yet.

No Breadth Engine logic exists yet.

No JSON writers exist yet.

No trading logic exists yet.

No Binance connection exists yet.

No Freqtrade integration exists yet.

No live trading is enabled.

MVP-2 implementation has started. Steps 1 and 2 complete.

## Next Step

MVP-2 Step 3 — Regime Engine.
