# Current State

## Project

Hunter Futures Pro

## Version

0.3.0-dev

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

MVP-2 Step 3 is complete:
- `src/hunter/market_state/regime.py` created with deterministic Regime Engine
- `RegimeConfig` with frozen defaults
- `calculate_btc_trend_score`, `calculate_bearish_btc_trend_score`, `calculate_eth_trend_score`
- `calculate_breadth_confirmation_score` with optional breadth input
- `classify_regime` with fail-closed behavior (UNKNOWN + NONE + confidence 0 on bad data)
- 37 regime tests, all passing
- Full test suite: 215 tests passing (178 existing + 37 new)

MVP-2 Step 4 is complete:
- `src/hunter/market_state/breadth.py` created with deterministic Market Breadth Engine
- `BreadthConfig` with frozen defaults (min_universe_size, EMA periods, thresholds)
- `filter_valid_symbols` with universe validation (missing, insufficient, invalid excluded)
- `calculate_percent_above_ema` for EMA20/EMA50 breadth metrics
- `calculate_percent_ema_rising` for rising EMA slope percentages
- `calculate_advancing_declining_pct` for market direction percentages
- `calculate_outperforming_btc_pct` for BTC relative performance
- `calculate_breadth_score` with SPEC-003 weighted formula, clamped 0-100
- `calculate_breadth` with fail-closed behavior (INVALID + UNKNOWN + score 0 on bad data)
- 44 breadth tests, all passing
- Full test suite: 259 tests passing (215 existing + 44 new)

MVP-2 Step 5 is complete:
- `src/hunter/market_state/writer.py` created with JSON serialization and atomic output writers
- `regime_to_dict` — Serializes RegimeOutput to JSON-compatible dict with ISO-8601 timestamps, enum strings
- `breadth_to_dict` — Serializes BreadthOutput to JSON-compatible dict matching SPEC-003 contract
- `atomic_write_json` — Atomic temp-file write with os.replace(), parent directory creation, cleanup on failure
- `write_regime_output` — Writes to `data/regime/current_regime.json` by default
- `write_breadth_output` — Writes to `data/breadth/current_breadth.json` by default
- 19 writer tests, all passing
- Full test suite: 278 tests passing (259 existing + 19 new)

No JSON schema validation exists yet.

No storage integration exists yet.

No report templates exist yet.

No trading logic exists yet.

No Binance connection exists yet.

No Freqtrade integration exists yet.

No live trading is enabled.

MVP-3 Decision Layer design is complete:
- SPEC-004 exists and is reviewed (19 checklist items all passed)
- Decision Layer consumes in-memory RegimeOutput and BreadthOutput from MVP-2
- Decision Layer produces data/decision/current_decision.json
- DecisionState enum: ALLOW, BLOCK, REVIEW (reserved for future), UNKNOWN
- DecisionAction enum: ENABLE_LONG_ONLY_RESEARCH, ENABLE_SHORT_ONLY_RESEARCH, BLOCK_ALL, MANUAL_REVIEW
- DecisionOutput model with 14 fields including audit trail (input_refs, data_quality)
- DecisionConfig with frozen defaults: min_regime_confidence: 0.60, stale_input_minutes: 120
- 14 deterministic fail-closed rules in priority order (all block by default)
- configs/decision.yaml design: single config file with threshold controls
- schemas/decision.schema.json design: future validation schema (not implemented yet)
- REVIEW state reserved for future manual-review workflows; default is BLOCK_ALL
- Staleness is output-level (engine output age), not candle-level (handled by MVP-2)
- No MVP-3 code has been implemented yet

No JSON schema validation exists yet.

No storage integration exists yet.

No report templates exist yet.

No trading logic exists yet.

No Binance connection exists yet.

No Freqtrade integration exists yet.

No live trading is enabled.

MVP-3 Step 1 is complete:
- `src/hunter/decision/models.py` created with immutable decision models
- `DecisionState` enum: ALLOW, BLOCK, REVIEW, UNKNOWN
- `DecisionAction` enum: ENABLE_LONG_ONLY_RESEARCH, ENABLE_SHORT_ONLY_RESEARCH, BLOCK_ALL, MANUAL_REVIEW
- `DecisionConfig` with frozen defaults and validation (min_regime_confidence 0.60, stale_input_minutes 120)
- `DecisionInputRefs` for audit trail references to consumed inputs
- `DecisionOutput` with 14 fields, `block_all()` fail-closed factory (BLOCK + BLOCK_ALL + confidence 0.0)
- 32 decision model tests, all passing
- Full test suite: 310 tests passing (278 existing + 32 new)

No Decision Engine exists yet.

No Decision Writer exists yet.

No config YAML exists yet.

No JSON schema validation exists yet.

No storage integration exists yet.

No report templates exist yet.

No trading logic exists yet.

No Binance connection exists yet.

No Freqtrade integration exists yet.

No live trading is enabled.

MVP-3 Step 2 is complete:
- `src/hunter/decision/engine.py` created with fail-closed Decision Engine
- `make_decision()` implements all 14 priority rules from SPEC-004
- `validate_decision_inputs()` checks 8 fail-closed conditions in order
- `is_stale_output()` checks oldest timestamp against stale threshold
- `detect_regime_breadth_conflict()` detects 4 conflict conditions
- `calculate_decision_confidence()` uses min(regime_conf, breadth/100)
- BULL + LONG_ONLY + healthy breadth → ENABLE_LONG_ONLY_RESEARCH
- BEAR + SHORT_ONLY + weak breadth → ENABLE_SHORT_ONLY_RESEARCH
- All other conditions → BLOCK_ALL by default
- Data quality aggregated from both inputs (logical OR)
- Input refs populated with timestamps and source labels
- 50 decision engine tests, all passing
- Full test suite: 360 tests passing (310 existing + 50 new)

Decision Models exist from Step 1.

No Decision Writer exists yet.

No config YAML exists yet.

No JSON reading or writing in Decision Engine.

No JSON schema validation exists yet.

No storage integration exists yet.

No report templates exist yet.

No trading logic exists yet.

No Binance connection exists yet.

No Freqtrade integration exists yet.

No live trading is enabled.

MVP-3 Step 3 is complete:
- `src/hunter/decision/writer.py` created with JSON serialization and atomic output writer
- `decision_to_dict()` serializes all 14 DecisionOutput fields to JSON-compatible dict
- `atomic_write_json()` uses temp-file + os.replace for atomic writes
- `write_decision_output()` writes to `data/decision/current_decision.json` by default
- ISO-8601 timestamps, enum strings, input refs, data quality, reason codes all preserved
- 19 writer tests, all passing
- Full test suite: 379 tests passing (360 existing + 19 new)

Decision Engine exists from Step 2.

Decision Models exist from Step 1.

No config YAML exists yet.

No JSON Schema validation exists yet.

No JSON input reading in Decision Writer.

No storage integration exists yet.

No report templates exist yet.

No trading logic exists yet.

No Binance connection exists yet.

No Freqtrade integration exists yet.

No live trading is enabled.

## Next Step

MVP-3 Step 4 — Integration Tests.
