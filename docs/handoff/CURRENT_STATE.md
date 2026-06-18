# Current State

## Project

Hunter Futures Pro

## Version

0.4.0-dev

## Current Phase

MVP-5 — Freqtrade Integration Step 1 complete. Freqtrade bridge models implemented. 62 tests passing. Ready for MVP-5 Step 2.

## Current Status

MVP-0 foundation is complete and committed.

MVP-1 Data Foundation is complete and committed. All 91 tests pass.

MVP-2 Market State is complete and committed. All 278 tests pass.
- Market State Models, Indicator Utilities, Regime Engine, Breadth Engine, JSON Output Writers all implemented.
- No Binance integration. No Freqtrade integration. No live trading.

MVP-3 Decision Layer is complete and committed. All 394 tests pass.
- Decision Models, Decision Engine, Decision Writer, Integration Tests all implemented.
- No Binance integration. No Freqtrade integration. No live trading. No JSON input reading.

MVP-4 Execution Bridge is complete and committed. All 538 tests pass.
- Execution Bridge Models, Engine, Writer, Integration Tests, Final Review all implemented.
- No Binance integration. No Freqtrade runtime integration. No live trading. No trading logic. No API keys.

MVP-5 Freqtrade Integration Step 1 is complete:
- `src/hunter/freqtrade_bridge/models.py` created with immutable Freqtrade bridge models.
- `src/hunter/freqtrade_bridge/__init__.py` created with public API exports.
- FreqtradeBridgeState enum: DISABLED, DRY_RUN_READY, BLOCKED, UNKNOWN.
- FreqtradeBridgeMode enum: LONG_RESEARCH_ONLY, SHORT_RESEARCH_ONLY, BLOCK_ALL.
- FreqtradeBridgeConfig with 12 fields and MVP-5 safety validation.
- FreqtradeBridgeInputRefs for execution context audit trail references.
- FreqtradeBridgeSafetyFlags with 10 safety fields and `to_dict()` for JSON serialization.
- FreqtradeBridgeDataQuality with freshness, validity, validation errors, and `to_dict()`.
- FreqtradeBridgeContext with 18 fields, version default "1.0", fail-closed by default.
- FreqtradeBridgeContext.blocked() factory producing BLOCKED + BLOCK_ALL + dry_run=True + version "1.0".
- All models frozen/immutable with `__post_init__` validation.
- 62 Freqtrade bridge model tests, all passing.
- Full test suite: 600 tests passing.
- No Freqtrade Bridge Engine exists yet.
- No Freqtrade Bridge Writer exists yet.
- No config YAML exists yet.
- No JSON Schema validation exists yet.
- No ExecutionContext JSON reading exists.
- No Binance integration exists.
- No real Freqtrade runtime integration exists.
- No strategy class exists.
- No trading logic exists (no pairlist, order, stake, leverage, stoploss, ROI, entry, exit).
- No live trading exists.
- No leverage.
- No shorting.
- No API keys.

## Next Step

MVP-5 Step 2 — Freqtrade Bridge Engine.

---

## Previous State (MVP-4)

MVP-4 Execution Bridge is complete and committed. All 538 tests pass.
- Execution Bridge Models, Engine, Writer, Integration Tests, Final Review all implemented.
- No Binance integration. No Freqtrade runtime integration. No live trading. No trading logic. No API keys.

MVP-4 Execution Bridge Step 1 is complete:

MVP-1 Data Foundation is complete and committed. All 91 tests pass.

MVP-2 Market State is complete and committed. All 278 tests pass.
- Market State Models, Indicator Utilities, Regime Engine, Breadth Engine, JSON Output Writers all implemented.
- No Binance integration. No Freqtrade integration. No live trading.

MVP-3 Decision Layer is complete and committed. All 394 tests pass.
- Decision Models, Decision Engine, Decision Writer, Integration Tests all implemented.
- No Binance integration. No Freqtrade integration. No live trading. No JSON input reading.

MVP-4 Execution Bridge Step 1 is complete:
- `src/hunter/execution/models.py` created with immutable execution bridge models.
- ExecutionState enum: ENABLED, BLOCKED, DRY_RUN_ONLY, UNKNOWN.
- ExecutionMode enum: LONG_RESEARCH_ONLY, SHORT_RESEARCH_ONLY, BLOCK_ALL, DRY_RUN_ONLY.
- ExecutionBridgeConfig with MVP-4 safety validation (dry_run_required=True, live_trading_enabled=False, etc.).
- ExecutionInputRefs for audit trail references to decision output.
- ExecutionSafetyFlags with human_override_required (default false) and max_context_age_seconds (default 300).
- ExecutionContext with version field default "1.0" for backward-compatible contract evolution.
- ExecutionContext.blocked() fail-closed factory producing BLOCKED + BLOCK_ALL + dry_run True + version "1.0".
- All models frozen/immutable with __post_init__ validation.
- 49 execution model tests, all passing.
- Full test suite: 443 tests passing.
- No Execution Bridge Engine exists yet.
- No Execution Writer exists yet.
- No config YAML exists yet.
- No JSON Schema validation exists yet.
- No DecisionOutput JSON reading exists.
- No Binance integration exists.
- No Freqtrade runtime integration exists.
- No trading logic exists.
- No live trading exists.
- No API keys exist.

MVP-4 Execution Bridge Step 2 is complete:
- `src/hunter/execution/engine.py` created with deterministic execution bridge engine.
- `build_execution_context()` — main entry point implementing all 15 fail-closed rules from SPEC-005 in priority order.
- `validate_execution_inputs()` — validates DecisionOutput against all safety constraints.
- `is_stale_decision()` — checks DecisionOutput age against stale_decision_minutes threshold.
- `map_decision_to_execution_mode()` — maps DecisionAction to ExecutionMode.
- `build_safety_flags()` — constructs ExecutionSafetyFlags with all defaults safe.
- All successful paths produce DRY_RUN_ONLY (ENABLED reserved for future).
- All blocked paths produce BLOCKED + BLOCK_ALL + dry_run=True.
- Missing/invalid/stale/unsafe inputs all block by default.
- input_refs populated with decision timestamp and source on successful paths.
- 45 execution engine tests, all passing.
- Full test suite: 488 tests passing.
- No Execution Writer exists yet.
- No config YAML exists yet.
- No JSON Schema validation exists yet.
- No DecisionOutput JSON reading exists.
- No Binance integration exists.
- No Freqtrade runtime integration exists.
- No trading logic exists.
- No live trading exists.
- No API keys exist.

MVP-4 Execution Bridge Step 4 is complete:
- `tests/test_execution/test_integration.py` created with 30 end-to-end integration tests.
- Full pipeline: DecisionOutput -> build_execution_context() -> write_execution_context() -> JSON verification.
- Long-only research enable scenario (ENABLE_LONG_ONLY_RESEARCH -> DRY_RUN_ONLY + LONG_RESEARCH_ONLY).
- Short-only research enable scenario (ENABLE_SHORT_ONLY_RESEARCH -> DRY_RUN_ONLY + SHORT_RESEARCH_ONLY).
- Block scenarios: BLOCK_ALL, MANUAL_REVIEW, stale, missing, invalid, blocked decision state.
- Unsafe config rejection tests: dry_run=False, live_trading=True, exchange=True, freqtrade=True all raise ValueError.
- JSON output verification: all 18 fields, enum strings, safety_flags, version "1.0", ISO-8601 timestamps.
- Atomic write tests with tmp_path, nested directory creation, no production path usage.
- Safety tests: no network, no trading logic, no JSON input reading, no Freqtrade runtime, all flags safe.
- 30 integration tests, all passing.
- Full test suite: 538 tests passing (508 existing + 30 new).
- No application code modified.
- No config YAML created.
- No JSON Schema files created.
- No DecisionOutput JSON reading used.
- No Freqtrade strategy class created.
- No trading execution logic added.
- No Binance integration.
- No live trading enabled.

MVP-4 Execution Bridge is fully complete. All 5 steps finished:
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

## Next Step

MVP-5 planning (Freqtrade Integration) — design only, no implementation yet.
- Define Freqtrade strategy contract that consumes ExecutionContext.
- Design signal generation from execution_state and execution_mode.
- Plan dry-run validation before any live trading enablement.
- No Freqtrade runtime integration in MVP-5 planning.
- No live trading enablement.
- No Binance integration.


## Current Status

MVP-0 foundation is complete and committed.

MVP-1 Data Foundation is complete and committed. All 91 tests pass.

MVP-2 Market State is complete and committed. All 278 tests pass.
- Market State Models, Indicator Utilities, Regime Engine, Breadth Engine, JSON Output Writers all implemented.
- No Binance integration. No Freqtrade integration. No live trading.

MVP-3 Decision Layer is complete and committed. All 394 tests pass.
- Decision Models, Decision Engine, Decision Writer, Integration Tests all implemented.
- No Binance integration. No Freqtrade integration. No live trading. No JSON input reading.

MVP-4 Execution Bridge design is complete and reviewed:
- SPEC-005 exists and is finalized.
- Execution Bridge consumes in-memory DecisionOutput from MVP-3.
- Future input path: data/decision/current_decision.json.
- Output path: data/execution/current_execution_context.json.
- ExecutionState enum: ENABLED, BLOCKED, DRY_RUN_ONLY, UNKNOWN.
- ExecutionMode enum: LONG_RESEARCH_ONLY, SHORT_RESEARCH_ONLY, BLOCK_ALL, DRY_RUN_ONLY.
- ExecutionContext version field default "1.0" for backward-compatible evolution.
- max_context_age_seconds default 300 as consumer-side stale guard.
- human_override_required default false, reserved for future.
- Fail-closed by default: all bad inputs produce BLOCKED + BLOCK_ALL.
- Dry-run only: all successful paths produce DRY_RUN_ONLY, ENABLED reserved for future.
- 15 priority-ordered fail-closed rules defined.
- Config file design: configs/execution_bridge.yaml (single file).
- JSON Schema design: schemas/execution_context.schema.json (future work only).
- Freqtrade compatibility contract documented for future MVP-5+.
- All 27 review checklist items passed.
- No MVP-4 code has been implemented yet.
- No Binance integration exists.
- No Freqtrade runtime integration exists.
- No trading logic exists.
- No live trading exists.
- No API keys exist.

## Next Step

MVP-4 Step 1 — Execution Bridge Models.
- Create ExecutionState, ExecutionMode, ExecutionBridgeConfig, ExecutionContext enums and dataclasses.
- Add __post_init__ validation for safety flags.
- Add ExecutionContext.blocked() fail-closed factory.
- Create tests/test_execution_bridge/test_models.py with model tests.
- Target: 25+ tests, all passing.

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

MVP-3 Step 4 is complete:
- `tests/test_decision/test_integration.py` created with 15 end-to-end tests
- Full pipeline: RegimeOutput + BreadthOutput -> make_decision() -> write_decision_output() -> JSON verification
- Long-only research enable scenario (BULL + LONG_ONLY + healthy breadth)
- Short-only research enable scenario (BEAR + SHORT_ONLY + weak breadth)
- Fail-closed block scenarios: UNKNOWN, INVALID, SIDEWAYS, TRANSITION, stale, conflict
- JSON output verification: all 14 fields, enum strings, input refs, data quality
- Tests use tmp_path, not production data/decision path
- 15 integration tests, all passing
- Full test suite: 394 tests passing (379 existing + 15 new)

Decision Models exist from Step 1.

Decision Engine exists from Step 2.

Decision Writer exists from Step 3.

No config YAML exists yet.

No JSON Schema validation exists yet.

No JSON input reading in integration tests.

No storage integration exists yet.

No report templates exist yet.

No trading logic exists yet.

No Binance connection exists yet.

No Freqtrade integration exists yet.

No live trading is enabled.

MVP-3 Step 5 is complete:
- Final review passed with no issues found
- All 20 checklist items verified and passing
- No fixes applied
- Version remains 0.3.0-dev

MVP-3 Decision Layer is fully complete. All 5 steps finished:
- Step 1: Decision Models (32 tests)
- Step 2: Decision Engine (50 tests)
- Step 3: Decision Writer (19 tests)
- Step 4: Integration Tests (15 tests)
- Step 5: Final review and polish
- Full test suite: 394 tests passing

## Next Step

MVP-4 planning (Execution Bridge / Freqtrade Integration) — design only, no implementation yet.
