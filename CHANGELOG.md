# Changelog

All important project changes will be recorded in this file.

## 0.1.0 — MVP-0 Project Foundation

### Added

- Initial project README
- Initial PROJECT.md specification
- Main AGENTS.md instructions
- Current project state handoff file
- Task backlog file
- Active task file
- Agent log file

### Project Direction

- Hunter Futures Pro will be developed as an agent-first crypto futures research and execution-control platform.
- WrongStack will be used as the main CLI AI agent.
- Kimi K2.7 will be used as the preferred model/backend.
- Freqtrade will be used only as the execution layer.
- Hunter Futures Pro will be the decision layer.
- Old strategies are benchmarks only.

### Safety

- No trading logic exists yet.
- No Binance connection exists yet.
- No Freqtrade integration exists yet.
- No live trading is enabled.
- No API keys or exchange secrets should be stored in the repository.

### Next

- Review MVP-0 cleanup.
- Commit initial foundation.
- Plan MVP-1 Data Foundation.

## 0.2.0-dev — MVP-1 Data Foundation (In Progress)

### Added

- Python project structure: `src/hunter/` package with `config`, `data`, `core`, `engines` modules
- `pyproject.toml` with project metadata, `pydantic` and `pyyaml` dependencies
- `requirements.txt` and `requirements-dev.txt` with pytest dependencies
- `.gitignore` excluding Python cache, secrets, runtime data, and local config
- `tests/` directory at repo root with `test_config`, `test_data`, `test_core`, `fixtures`
- `__version__ = "0.2.0-dev"` in `src/hunter/__init__.py`

### MVP-1 Step 2 — Config Models and Validation (Complete)

- Pydantic config models: `TradingConfig`, `CollectionConfig`, `StorageConfig`, `LoggingConfig`, `HunterConfig`
- Config loader with safe override hierarchy (YAML file, env var)
- `validate_config()` with fail-closed validation:
  - Raises `ConfigLoadError` if `trading.enabled` is `true`
  - Raises `ConfigLoadError` if `trading.live_enabled` is `true`
  - Raises `ConfigLoadError` if secrets (`api_key`, `api_secret`, `secret_key`, `private_key`) detected
- Safe defaults: `trading.enabled: false`, `trading.live_enabled: false`, `collection.enabled: false`
- Config files: `configs/data.yaml` (safe defaults), `configs/local.example.yaml` (warnings)
- Config directory standard: `configs/` (not `config/`)
- Config tests: 23 tests for safe defaults, validation failures, and YAML loading

### MVP-1 Step 3 — Logging Structure (Complete)

- `src/hunter/core/logging.py` with structured logging components:
  - `JSONFormatter` for JSON log output with timestamp, level, logger, message, correlation_id, context, exception info
  - `RedactingFilter` for recursive secret redaction (api_key, secret, password, token, private_key) in dicts and lists
  - `setup_logging()` with console handler (text or JSON) and rotating file handler (always JSON, 10MB/5 backups)
- `tests/test_core/test_logging.py` with 18 tests for formatting, redaction, and setup behavior
- Log secret redaction applied to file handler only

### Safety

- No trading logic exists yet.
- No Binance connection exists yet.
- No Freqtrade integration exists yet.
- No live trading is enabled.
- No API keys or exchange secrets stored in repository.
- `.gitignore` prevents accidental commit of `configs/local.yaml`, `.env`, `*.key`, `*.pem`.
- Logging redacts secret-like fields from file output.

### MVP-1 Step 4 — Data Collector Interface (Complete)

- `src/hunter/data/collector.py` with abstract `DataCollector` interface:
  - 6 abstract methods: `get_exchange_info()`, `get_klines()`, `get_funding_rates()`, `get_open_interest()`, `get_mark_price()`, `get_24h_ticker()`
- `BinanceFuturesCollector` skeleton class that does NOT connect to Binance
  - All methods raise `NotImplementedError` with message "Binance connection not implemented in MVP-1"
- 5 frozen dataclass data models: `KlineData`, `FundingRateData`, `OpenInterestData`, `MarkPriceData`, `Ticker24hData`
- `tests/test_data/test_collector.py` with 18 tests:
  - `DataCollector` cannot be instantiated directly (abstract)
  - `BinanceFuturesCollector` raises `NotImplementedError` on all methods
  - No network calls are made (verified by monkeypatch)
  - Data models are immutable (`frozen=True`)

### MVP-1 Step 5 — SQLite Storage Layer (Complete)

- `src/hunter/data/schema.sql` with 5 tables:
  - `market_symbols` — Symbol registry with base/quote assets
  - `candles` — OHLCV data with unique constraint on (symbol, timeframe, open_time)
  - `funding_rates` — Funding rate history with unique constraint on (symbol, funding_time)
  - `open_interest` — Open interest snapshots
  - `collection_metadata` — Freshness tracking with upsert support
- Indexes on common query patterns: `idx_candles_symbol_timeframe_time`, `idx_funding_symbol_time`, `idx_oi_symbol_time`, `idx_meta_symbol_type`
- `src/hunter/data/storage.py` with `DataStorage` ABC and `SQLiteStorage` implementation
  - `DataStorage` ABC: 9 abstract methods (`initialize`, `save_klines`, `get_klines`, `get_latest_kline`, `save_funding_rates`, `get_funding_rates`, `save_collection_metadata`, `get_collection_metadata`, `is_data_fresh`)
  - `SQLiteStorage` uses Python standard library `sqlite3` only (no external dependencies)
  - `save_klines()` / `save_funding_rates()` use `INSERT OR IGNORE` for deduplication
  - `is_data_fresh()` checks metadata age against `max_age_seconds`
- `tests/test_data/test_storage.py` with 19 tests using temporary SQLite database files
  - All tests pass, no network calls, no Binance connection, no Freqtrade connection

### MVP-1 Step 6 — Final Safety Tests and MVP-1 Completion (Complete)

- Final review found config loader returning `dict` instead of `HunterConfig` when merging YAML
- Fixed `load_config()` to use `_deep_update()` + `model_validate()` for safe nested merging
- Fixed secret detection to scan merged dict before Pydantic strips extra fields
- Fixed config tests to use `raw_dict` parameter for secret injection
- Fixed missing `import sys` in logging tests
- Fixed `test_sets_log_level` to check root logger level
- Commit `dd3ea99`: config loader bugfix and test fixes
- All 91 tests now pass (0 failures)
- MVP-1 Data Foundation is complete

### Next

- MVP-2 Market State: Regime Engine and Market Breadth Engine design.

## 0.3.0-dev — MVP-2 Market State Design (Complete)

### Added

- `specs/SPEC-003-Market-State-Regime-Breadth.md` with complete MVP-2 design:
  - Regime Engine design with 5 states (BULL, BEAR, SIDEWAYS, TRANSITION, UNKNOWN)
  - Market Breadth Engine design with universe filtering and invalid symbol rules
  - Deterministic scoring formulas (no ML, no optimization, no curve fitting):
    - `btc_trend_score`, `bearish_btc_trend_score`, `eth_trend_score` (0–100)
    - `breadth_confirmation_score` (0–100)
    - `breadth_score` (0–100) with weighted component formula
    - `confidence` (0.0–1.0) = min(primary_score, confirmation_score) / 100
  - EMA slope formula: `ema_slope_pct = ((ema_current - ema_n_candles_ago) / ema_n_candles_ago) * 100`
  - Fail-closed behavior: all bad data → UNKNOWN + NONE + confidence 0
  - Pipeline order: Breadth Engine runs first, Regime Engine consumes breadth output
  - Timeframe-aware stale data: `stale_threshold_candles: 2` with `timeframe_duration` multiplier
  - `configs/market_state.yaml` as single config standard (no separate regime/breadth YAML)
  - JSON Schema design section for future `schemas/regime.schema.json` and `schemas/breadth.schema.json`
  - Test plan for regime, breadth, and safety tests
  - MVP-1 interface references: DataStorage ABC, SQLiteStorage, KlineData, HunterConfig

### Safety

- No trading logic exists yet.
- No Binance connection exists yet.
- No Freqtrade integration exists yet.
- No live trading is enabled.
- No API keys or exchange secrets stored in repository.
- No code implemented yet — design only.

### Next

- MVP-2 implementation planning: Step 1 — Market State Models.

### MVP-2 Step 1 — Market State Models (Complete)

- `src/hunter/market_state/__init__.py` created
- `src/hunter/market_state/models.py` created with frozen dataclasses:
  - Enums: `RegimeState` (BULL, BEAR, SIDEWAYS, TRANSITION, UNKNOWN)
  - Enums: `RiskState` (RISK_ON, RISK_OFF, NEUTRAL, UNKNOWN)
  - Enums: `AllowedMode` (LONG_ONLY, SHORT_ONLY, NONE)
  - Enums: `OutputStatus` (VALID, INVALID)
  - `DataQuality` — immutable flags for missing, stale, insufficient_history, insufficient_universe
  - `RegimeOutput` — frozen output model with `__post_init__` validation:
    - confidence range: 0.0–1.0
    - score ranges: 0–100
    - `RegimeOutput.unknown()` fail-closed factory: UNKNOWN + NONE + confidence 0
  - `BreadthOutput` — frozen output model with `__post_init__` validation:
    - breadth_score range: 0–100
    - percentage fields range: 0.0–1.0
    - `BreadthOutput.invalid()` fail-closed factory: INVALID + UNKNOWN health + score 0
- `tests/test_market_state/__init__.py` created
- `tests/test_market_state/test_models.py` with 37 tests:
  - Enum value verification
  - Valid creation with boundary values
  - Validation failures (out-of-range confidence, scores, percentages)
  - Fail-closed factory defaults and custom overrides
  - Immutability (frozen dataclass)
- Full test suite: 128 tests passing (91 existing + 37 new)

### Safety

- No trading logic exists yet.
- No Binance connection exists yet.
- No Freqtrade integration exists yet.
- No live trading is enabled.
- No API keys or exchange secrets stored in repository.
- No Regime Engine logic exists yet.
- No Breadth Engine logic exists yet.
- No indicators exist yet.

### MVP-2 Step 2 — Indicator Utilities (Complete)

- `src/hunter/market_state/indicators.py` created with pure, deterministic functions:
  - `safe_divide(numerator, denominator, default)` — division with zero-safe fallback
  - `percent_change(current, previous, default)` — percentage change with zero-safe fallback
  - `simple_moving_average(values, period)` — SMA with sliding window; returns empty list if insufficient data
  - `exponential_moving_average(values, period)` — EMA with standard multiplier formula; returns empty list if insufficient data
  - `ema_slope_pct(ema_values, lookback)` — EMA slope percentage matching SPEC-003 formula exactly
  - `is_rising(slope_pct, threshold_pct)` — slope > threshold
  - `is_falling(slope_pct, threshold_pct)` — slope < -threshold
  - `is_flat(slope_pct, threshold_pct)` — abs(slope) <= threshold
- Standard library only — no pandas, no external dependencies
- All functions are stateless, no network, no storage, no trading logic
- `tests/test_market_state/test_indicators.py` with 50 tests:
  - Safe divide: normal, zero denominator, custom default, negatives, floats
  - Percent change: normal, negative, zero previous, no change, double
  - SMA: basic, period 1, insufficient data, exact period, invalid period, empty values, large values
  - EMA: basic, period 1, insufficient data, exact period, invalid period, empty values, known values
  - EMA slope: rising, falling, flat, lookback 1, lookback 5 (SPEC default), zero denominator, insufficient data, invalid lookback
  - Slope direction: rising/falling/flat at and around thresholds, combined state checks
  - Safety: no network imports, no trading terms in module source
- Full test suite: 178 tests passing (128 existing + 50 new)

### Safety

- No trading logic exists yet.
- No Binance connection exists yet.
- No Freqtrade integration exists yet.
- No live trading is enabled.
- No API keys or exchange secrets stored in repository.
- No Regime Engine logic exists yet.
- No Breadth Engine logic exists yet.
- No JSON writers exist yet.

### MVP-2 Step 3 — Regime Engine (Complete)

- `src/hunter/market_state/regime.py` created with deterministic Regime Engine:
  - `RegimeConfig` — frozen dataclass with all SPEC-003 defaults (ema periods, thresholds, lookbacks)
  - `calculate_btc_trend_score(btc_closes, config)` — bullish conditions / total * 100, 0–100
  - `calculate_bearish_btc_trend_score(btc_closes, config)` — bearish conditions / total * 100, 0–100
  - `calculate_eth_trend_score(eth_closes, config)` — optional ETH confirmation, returns 0 + `ETH_DATA_UNAVAILABLE` if missing
  - `calculate_breadth_confirmation_score(...)` — optional breadth confirmation based on regime direction
  - `classify_regime(...)` — main classifier with fail-closed behavior:
    - Missing BTC candles → `UNKNOWN` + `NONE` + confidence 0
    - Insufficient BTC history → `UNKNOWN` + `NONE` + confidence 0
    - Invalid candle values (≤0) → `UNKNOWN` + `NONE` + confidence 0
    - Bull detected → `BULL` + `LONG_ONLY` + confidence from confirmation
    - Bear detected → `BEAR` + `SHORT_ONLY` + confidence from confirmation
    - Weak trend → `SIDEWAYS` + `NONE`
    - Low confidence (<0.6) → `TRANSITION` + `NONE`
  - Uses `ema_slope_pct` from indicators.py (matches SPEC-003 formula exactly)
  - No ML, no optimization, no curve fitting
- `tests/test_market_state/test_regime.py` with 37 tests:
  - RegimeConfig defaults and custom values
  - BTC trend score: bullish high, bearish low, flat medium, missing, insufficient, invalid, range
  - Bearish BTC trend score: bearish high, bullish low, missing
  - ETH trend score: None unavailable, bullish, missing
  - Breadth confirmation: bull confirmation, bear confirmation, None returns zero, no confirmation
  - Fail-closed: missing BTC, insufficient history, invalid values, calculation error blocks
  - Regime detection: bull, bear, sideways, transition with ETH, bull with breadth, confidence range, allowed mode NONE when invalid
  - Reason codes: bull, bear, unknown all have non-empty reason codes
  - Safety: no network imports, no trading terms, no Binance, no Freqtrade
- Full test suite: 215 tests passing (178 existing + 37 new)

### Safety

- No trading logic exists yet.
- No Binance connection exists yet.
- No Freqtrade integration exists yet.
- No live trading is enabled.
- No API keys or exchange secrets stored in repository.
- No Breadth Engine logic exists yet.
- No JSON writers exist yet.

### MVP-2 Step 4 — Breadth Engine (Complete)

- `src/hunter/market_state/breadth.py` created with deterministic Market Breadth Engine:
  - `BreadthConfig` — frozen dataclass with all SPEC-003 defaults (min_universe_size, EMA periods, thresholds, lookbacks)
  - `filter_valid_symbols(universe_candles, config)` — validates symbols per SPEC-003 rules:
    - Exclude missing candles, insufficient history, close ≤ 0, negative volume, calculation failures
    - Returns (valid_symbols, invalid_count, reason_codes)
  - `calculate_percent_above_ema(valid_candles, ema_period)` — percentage of symbols with close > EMA
  - `calculate_percent_ema_rising(valid_candles, ema_period, lookback, threshold)` — percentage with rising EMA slope
  - `calculate_advancing_declining_pct(valid_candles)` — advancing vs declining percentages (flat excluded)
  - `calculate_outperforming_btc_pct(valid_candles, btc_closes, lookback_days)` — percentage outperforming BTC return
  - `calculate_breadth_score(...)` — weighted formula per SPEC-003, clamped 0–100:
    - above_ema20_pct * 25 + above_ema50_pct * 20 + ema20_rising_pct * 20 + ema50_rising_pct * 15 + advancing_pct * 10 + outperforming_btc_7d_pct * 10
  - `calculate_breadth(universe_candles, btc_closes, ...)` — main breadth function with fail-closed behavior:
    - Missing universe → `INVALID` + `UNKNOWN` health + score 0
    - Missing BTC → `INVALID` + `UNKNOWN` health + score 0
    - Insufficient universe (< min_universe_size) → `INVALID` + `UNKNOWN` health + score 0
    - Invalid BTC values → `INVALID` + `UNKNOWN` health + score 0
    - Valid data → `VALID` + market health (RISK_ON/RISK_OFF/NEUTRAL) + breadth_score 0–100
  - Uses `exponential_moving_average`, `ema_slope_pct`, `percent_change` from indicators.py
  - No ML, no optimization, no curve fitting
- `tests/test_market_state/test_breadth.py` with 44 tests:
  - BreadthConfig defaults, custom values, frozen immutability
  - filter_valid_symbols: all valid, missing excluded, insufficient excluded, invalid price excluded, negative excluded
  - calculate_percent_above_ema: all above, none above, half above, empty
  - calculate_percent_ema_rising: all rising, none rising, empty
  - calculate_advancing_declining_pct: all advancing, all declining, mixed, empty, flat excluded
  - calculate_outperforming_btc_pct: all outperform, none outperform, half, empty, missing BTC, insufficient BTC
  - calculate_breadth_score: max 100, min 0, mixed, clamped above 100, clamped below 0, deterministic
  - calculate_breadth: missing universe, missing BTC, insufficient universe, invalid BTC, valid calculation, score range, reason codes, risk_on, risk_off, invalid symbols counted
  - Safety: no network calls, no trading logic
- Full test suite: 259 tests passing (215 existing + 44 new)

### Safety

- No trading logic exists yet.
- No Binance connection exists yet.
- No Freqtrade integration exists yet.
- No live trading is enabled.
- No API keys or exchange secrets stored in repository.
- No JSON writers exist yet.
- No schema files exist yet.

### MVP-2 Step 5 — JSON Output Writers (Complete)

- `src/hunter/market_state/writer.py` created with JSON serialization and atomic output writers:
  - `regime_to_dict(output)` — Serializes `RegimeOutput` to JSON-compatible dict:
    - ISO-8601 timestamps with Z suffix (e.g., `2026-06-17T12:00:00Z`)
    - Enum values serialized as strings (e.g., `BULL`, `LONG_ONLY`, `VALID`)
    - `DataQuality` and `reason_codes` preserved
  - `breadth_to_dict(output)` — Serializes `BreadthOutput` to JSON-compatible dict:
    - Same timestamp and enum serialization as regime
    - All percentage fields and counts preserved
  - `atomic_write_json(data, target_path)` — Atomic file write:
    - Writes to temp file in same directory first
    - Uses `os.replace()` for atomic rename
    - Creates parent directories if missing
    - Cleans up temp file on failure (no partial output)
    - Uses `fsync` for durability
  - `write_regime_output(output, target_path)` — Writes to `data/regime/current_regime.json` by default
  - `write_breadth_output(output, target_path)` — Writes to `data/breadth/current_breadth.json` by default
  - Output matches SPEC-003 JSON contract exactly
- `tests/test_market_state/test_writer.py` with 19 tests:
  - regime_to_dict: valid regime, unknown regime, ISO-8601 format, naive datetime, enum strings, data quality, reason codes
  - breadth_to_dict: valid breadth, invalid breadth
  - atomic_write_json: writes file, creates directories, no partial on failure, unicode encoding
  - write_regime_output: default path, parent directories
  - write_breadth_output: default path, parent directories
  - Safety: no network calls, no trading logic
- Full test suite: 278 tests passing (259 existing + 19 new)

### Safety

- No trading logic exists yet.
- No Binance connection exists yet.
- No Freqtrade integration exists yet.
- No live trading is enabled.
- No API keys or exchange secrets stored in repository.
- No JSON schema validation exists yet.
- No storage integration exists yet.
- No report templates exist yet.

### MVP-2 Complete

MVP-2 Market State implementation is fully complete. All 6 steps finished:
- Step 1: Market State Models (37 tests)
- Step 2: Indicator Utilities (50 tests)
- Step 3: Regime Engine (37 tests)
- Step 4: Breadth Engine (44 tests)
- Step 5: JSON Output Writers (19 tests)
- Step 6: Final review and polish
- Version bumped to 0.3.0-dev
- Full test suite: 278 tests passing

### SPEC-004 — Decision Layer Design (Complete)

- SPEC-004 exists and is reviewed (19 checklist items all passed)
- Decision Layer consumes in-memory `RegimeOutput` and `BreadthOutput` from MVP-2
- Decision Layer produces `data/decision/current_decision.json`
- `DecisionState` enum designed: `ALLOW`, `BLOCK`, `REVIEW` (reserved for future), `UNKNOWN`
- `DecisionAction` enum designed: `ENABLE_LONG_ONLY_RESEARCH`, `ENABLE_SHORT_ONLY_RESEARCH`, `BLOCK_ALL`, `MANUAL_REVIEW`
- `DecisionOutput` model with 14 fields including audit trail (`input_refs`, `data_quality`)
- `DecisionConfig` with frozen defaults: `min_regime_confidence: 0.60`, `stale_input_minutes: 120`
- 14 deterministic fail-closed rules in priority order (all block by default)
- `configs/decision.yaml` design: single config file with threshold controls
- `schemas/decision.schema.json` design: future validation schema (not implemented yet)
- `REVIEW` state reserved for future manual-review workflows; default is `BLOCK_ALL`
- Staleness is output-level (engine output age), not candle-level (handled by MVP-2)
- No MVP-3 code has been implemented yet
- No Binance integration
- No Freqtrade integration
- No trading logic
- No live trading

### MVP-3 Step 1 — Decision Models (Complete)

- `src/hunter/decision/__init__.py` created
- `src/hunter/decision/models.py` created with frozen dataclasses:
  - Enums: `DecisionState` (ALLOW, BLOCK, REVIEW, UNKNOWN)
  - Enums: `DecisionAction` (ENABLE_LONG_ONLY_RESEARCH, ENABLE_SHORT_ONLY_RESEARCH, BLOCK_ALL, MANUAL_REVIEW)
  - `DecisionConfig` — frozen dataclass with `__post_init__` validation:
    - min_regime_confidence: 0.60 (range 0.0–1.0)
    - min_breadth_score_for_long: 60 (range 0–100)
    - max_breadth_score_for_short: 40 (range 0–100)
    - stale_input_minutes: 120 (positive integer)
    - transition_action: BLOCK_ALL, conflict_action: BLOCK_ALL
  - `DecisionInputRefs` — frozen dataclass for audit trail references to consumed inputs
  - `DecisionOutput` — frozen output model with `__post_init__` validation:
    - confidence range: 0.0–1.0
    - regime_confidence range: 0.0–1.0
    - breadth_score range: 0–100
    - `DecisionOutput.block_all()` fail-closed factory: BLOCK + BLOCK_ALL + confidence 0.0
- `tests/test_decision/test_models.py` with 32 tests:
  - Enum value verification
  - DecisionConfig defaults, custom values, and boundary validation
  - Valid DecisionOutput creation with all 14 fields
  - Validation failures (out-of-range confidence, regime_confidence, breadth_score)
  - Fail-closed factory defaults and custom overrides
  - Immutability (frozen dataclass)
- Full test suite: 310 tests passing (278 existing + 32 new)

### Safety

- No trading logic exists yet.
- No Binance connection exists yet.
- No Freqtrade integration exists yet.
- No live trading is enabled.
- No API keys or exchange secrets stored in repository.
- No Decision Engine logic exists yet.
- No Decision Writer exists yet.
- No config YAML exists yet.

### MVP-3 Step 2 — Decision Engine (Complete)

- `src/hunter/decision/engine.py` created with deterministic fail-closed Decision Engine:
  - `make_decision(regime_output, breadth_output, config)` — main entry point implementing all 14 priority rules from SPEC-004
  - `validate_decision_inputs(regime, breadth, config)` — fail-closed validation in priority order:
    - Missing RegimeOutput → BLOCK_ALL (MISSING_REGIME)
    - Missing BreadthOutput → BLOCK_ALL (MISSING_BREADTH)
    - Invalid RegimeOutput status → BLOCK_ALL (INVALID_REGIME)
    - Invalid BreadthOutput status → BLOCK_ALL (INVALID_BREADTH)
    - UNKNOWN regime → BLOCK_ALL (UNKNOWN_REGIME)
    - allowed_mode NONE → BLOCK_ALL (ALLOWED_MODE_NONE)
    - Low regime confidence → BLOCK_ALL (LOW_REGIME_CONFIDENCE)
    - Stale inputs → BLOCK_ALL (STALE_INPUT)
  - `is_stale_output(regime, breadth, stale_input_minutes)` — checks oldest timestamp against threshold
  - `detect_regime_breadth_conflict(regime, breadth)` — detects 4 conflict conditions per SPEC-004:
    - BULL + RISK_OFF, BEAR + RISK_ON, BULL + score < 50, BEAR + score > 50
  - `calculate_decision_confidence(regime, breadth)` — min(regime_confidence, breadth_score / 100)
  - Decision rules (after all fail-closed checks pass):
    - BULL + LONG_ONLY + breadth_score >= min_breadth_score_for_long → ALLOW + ENABLE_LONG_ONLY_RESEARCH
    - BEAR + SHORT_ONLY + breadth_score <= max_breadth_score_for_short → ALLOW + ENABLE_SHORT_ONLY_RESEARCH
    - SIDEWAYS → BLOCK_ALL (SIDEWAYS_NO_DIRECTION)
    - TRANSITION → BLOCK_ALL (TRANSITION_UNCERTAIN) or custom transition_action
    - Conflicts → BLOCK_ALL (CONFLICTING_SIGNALS) or custom conflict_action
    - Default → BLOCK_ALL (DEFAULT_BLOCK)
  - Data quality aggregation: logical OR of RegimeOutput and BreadthOutput data_quality flags
  - Input refs populated with timestamps and source labels for audit trail
- `tests/test_decision/test_engine.py` with 50 tests:
  - validate_decision_inputs: missing regime, missing breadth, invalid status, UNKNOWN, NONE mode, low confidence, stale, valid, data quality aggregation
  - is_stale_output: fresh, old regime, old breadth, uses oldest timestamp
  - detect_conflict: bull+risk_off, bear+risk_on, bull+low_score, bear+high_score, no conflict cases
  - calculate_confidence: high/high, low/high, high/low, perfect, zero
  - make_decision fail-closed: all 8 fail-closed conditions produce BLOCK_ALL
  - make_decision allow: bull+healthy_breadth allows long, bear+weak_breadth allows short
  - make_decision special: sideways blocks, transition blocks, custom actions, conflicts, default block, input refs, confidence calculation
  - Safety: no network calls, no trading execution logic
- Full test suite: 360 tests passing (310 existing + 50 new)

### Safety

- No trading logic exists yet.
- No Binance connection exists yet.
- No Freqtrade integration exists yet.
- No live trading is enabled.
- No API keys or exchange secrets stored in repository.
- No Decision Writer exists yet.
- No config YAML exists yet.
- No JSON reading or writing in Decision Engine.

### MVP-3 Step 3 — Decision Writer (Complete)

- `src/hunter/decision/writer.py` created with JSON serialization and atomic output writer:
  - `decision_to_dict(output)` — Serializes `DecisionOutput` to JSON-compatible dict:
    - ISO-8601 timestamps with Z suffix (e.g., `2026-06-17T12:00:00Z`)
    - Enum values serialized as strings (e.g., `ALLOW`, `BLOCK_ALL`, `LONG_ONLY`)
    - `DecisionInputRefs` with regime/breadth timestamps and source labels
    - `DataQuality` with all 4 boolean flags
    - `reason_codes` preserved as list
  - `atomic_write_json(data, target_path)` — Atomic file write:
    - Writes to temp file in same directory first
    - Uses `os.replace()` for atomic rename
    - Creates parent directories if missing
    - Cleans up temp file on failure (no partial output)
    - Uses `fsync` for durability
  - `write_decision_output(output, target_path)` — Writes to `data/decision/current_decision.json` by default
  - Output matches SPEC-004 JSON contract exactly
- `tests/test_decision/test_writer.py` with 19 tests:
  - decision_to_dict: valid decision, block decision, ISO-8601 format, naive datetime, enum strings, input refs, data quality, reason codes, JSON roundtrip
  - atomic_write_json: writes file, creates directories, no partial on failure, unicode encoding
  - write_decision_output: default path, parent directories, default path constant, invalid path fails
  - Safety: no network calls, no trading logic
- Full test suite: 379 tests passing (360 existing + 19 new)

### Safety

- No trading logic exists yet.
- No Binance connection exists yet.
- No Freqtrade integration exists yet.
- No live trading is enabled.
- No API keys or exchange secrets stored in repository.
- No config YAML exists yet.
- No JSON schema validation exists yet.
- No JSON input reading in Decision Writer.

### MVP-3 Step 4 — Integration Tests (Complete)

- `tests/test_decision/test_integration.py` created with 15 end-to-end tests:
  - `test_bull_long_healthy_full_pipeline` — BULL + LONG_ONLY + healthy breadth → ENABLE_LONG_ONLY_RESEARCH, JSON written and verified
  - `test_bear_short_weak_full_pipeline` — BEAR + SHORT_ONLY + weak breadth → ENABLE_SHORT_ONLY_RESEARCH, JSON written and verified
  - `test_unknown_regime_blocks_pipeline` — UNKNOWN regime → BLOCK_ALL, JSON verified
  - `test_invalid_breadth_blocks_pipeline` — INVALID breadth → BLOCK_ALL, JSON verified
  - `test_sideways_blocks_pipeline` — SIDEWAYS → BLOCK_ALL, JSON verified
  - `test_transition_blocks_pipeline` — TRANSITION → BLOCK_ALL, JSON verified
  - `test_stale_regime_blocks_pipeline` — stale regime → BLOCK_ALL, JSON verified
  - `test_stale_breadth_blocks_pipeline` — stale breadth → BLOCK_ALL, JSON verified
  - `test_conflict_blocks_pipeline` — conflicting signals → BLOCK_ALL, JSON verified
  - `test_json_contains_all_expected_fields` — all 14 SPEC-004 fields present in JSON output
  - `test_enum_values_are_strings_in_json` — all enum values serialized as strings
  - `test_no_default_production_path_used` — tests use tmp_path, not production data/decision path
  - Safety: no network calls, no trading execution logic, no JSON input reading
- Full test suite: 394 tests passing (379 existing + 15 new)

### Safety

- No trading logic exists yet.
- No Binance connection exists yet.
- No Freqtrade integration exists yet.
- No live trading is enabled.
- No API keys or exchange secrets stored in repository.
- No config YAML exists yet.
- No JSON schema validation exists yet.
- No JSON input reading in integration tests.

### MVP-3 Complete

MVP-3 Decision Layer implementation is fully complete. All 5 steps finished:
- Step 1: Decision Models (32 tests)
- Step 2: Decision Engine (50 tests)
- Step 3: Decision Writer (19 tests)
- Step 4: Integration Tests (15 tests)
- Step 5: Final review and polish
- Version: 0.3.0-dev
- Full test suite: 394 tests passing

### Next

- MVP-4 planning (Execution Bridge / Freqtrade Integration) — design only, no implementation yet.
- Commit current state.
- Review PROJECT.md for MVP-4 scope.
