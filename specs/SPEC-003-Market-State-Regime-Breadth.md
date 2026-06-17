# SPEC-003-Market-State-Regime-Breadth

## Background

MVP-0 created the agent-first project foundation.

MVP-1 created the Data Foundation.

MVP-1 includes:

- Python project structure
- config models and validation
- logging with redaction
- data collector interface
- BinanceFuturesCollector skeleton
- local SQLite storage layer
- tests

MVP-2 will design the Market State layer.

The Market State layer will include:

1. Regime Engine
2. Market Breadth Engine

This phase designs market-state logic only.

No real Binance integration exists yet.

No Freqtrade integration exists yet.

No trading logic exists yet.

No live trading is enabled.

The Regime Engine and Market Breadth Engine will later use local data structures and storage created in MVP-1.

MVP-2 engines should read local data through:

- DataStorage ABC (from MVP-1)
- SQLiteStorage (from MVP-1)
- KlineData model (from MVP-1)
- HunterConfig / config loader (from MVP-1)

## Requirements

### Must Have

- Design Regime Engine.
- Design Market Breadth Engine.
- Define input data contracts.
- Define output JSON contracts.
- Define validation rules.
- Define stale data behavior.
- Define missing data behavior.
- Define reason codes.
- Define test plan.
- Preserve fail-closed safety.
- Keep live trading disabled.

### Should Have

- Use simple scoring formulas.
- Keep thresholds config-driven.
- Produce deterministic outputs.
- Include report output format.
- Include explainable decisions.
- Include confidence score.
- Include reason codes in all outputs.

### Could Have

- Add markdown daily report design.
- Add CSV debug output design.
- Add regime confidence score details.
- Add breadth debug metrics.
- Add future ADX and ATR placeholders.

### Won't Have

- No live trading.
- No Freqtrade integration.
- No Binance API integration.
- No real data fetching.
- No portfolio approval.
- No order execution.
- No strategy implementation.
- No production trading decisions.

## Method

MVP-2 will design two market state components:

Market State Layer:

- Regime Engine
- Market Breadth Engine

The output of this layer will be used later by future decision modules.

MVP-2 must not approve trades.

MVP-2 must not create execution logic.

MVP-2 must fail closed when data is missing, stale or insufficient.

---

## 1. Regime Engine

### Purpose

Classify the current crypto market state.

Supported regime states:

- BULL
- BEAR
- SIDEWAYS
- TRANSITION
- UNKNOWN

### Inputs

Required input:

- BTC candles

Optional input:

- ETH candles
- breadth summary
- volatility metrics
- ADX placeholder
- ATR percentage placeholder

### Minimum Candle Requirements

The engine should require enough historical candles to calculate:

- EMA20
- EMA50
- EMA200 if enabled later
- EMA slope
- recent returns

If history is insufficient, output must be:

- market_regime = UNKNOWN
- allowed_mode = NONE
- confidence = low

### Suggested Metrics

BTC trend metrics:

- close vs EMA20
- close vs EMA50
- EMA20 slope
- EMA50 slope
- recent return
- volatility placeholder
- ADX placeholder

ETH confirmation metrics:

- ETH close vs EMA20
- ETH EMA20 slope
- ETH recent return

Breadth confirmation metrics:

- breadth_score
- percent above EMA20
- percent above EMA50
- advancing percentage
- outperforming BTC percentage

### Scoring Formulas

All scores are deterministic. No ML. No optimization. No curve fitting.

**btc_trend_score** (0–100):

```
btc_trend_score = bullish_conditions_met / total_btc_conditions * 100
```

Where `total_btc_conditions` is the count of all BTC trend conditions evaluated (close vs EMA20, close vs EMA50, EMA20 slope, EMA50 slope, recent return direction). `bullish_conditions_met` is the count of conditions that signal bullish.

For bearish assessment:

```
bearish_btc_trend_score = bearish_conditions_met / total_btc_conditions * 100
```

**eth_trend_score** (0–100):

Same formula applied to ETH conditions. If ETH data is missing, `eth_trend_score = 0` and the reason code `ETH_DATA_UNAVAILABLE` is added.

**breadth_confirmation_score** (0–100):

```
breadth_confirmation_score = confirming_conditions_met / total_breadth_conditions * 100
```

Where confirming conditions depend on regime direction. For bull: breadth_score > risk_on_threshold, majority_above_ema20, advancing_pct > 0.5. For bear: breadth_score < risk_off_threshold, majority_below_ema20, declining_pct > 0.5.

**confidence** (0.0–1.0):

```
confidence = min(primary_score, confirmation_score) / 100
```

Where `primary_score` is the regime-direction score (btc_trend_score or bearish_btc_trend_score) and `confirmation_score` is the supporting score (eth_trend_score or breadth_confirmation_score). If no confirmation is available, `confidence = primary_score / 100`.

**breadth_score** (0–100):

```
breadth_score =
  above_ema20_pct       * 25
  + above_ema50_pct     * 20
  + ema20_rising_pct    * 20
  + ema50_rising_pct    * 15
  + advancing_pct       * 10
  + outperforming_btc_7d_pct * 10
```

All percentages are 0.0–1.0. The result is clamped to 0–100.

### Initial Regime Logic

Bull candidate:

- BTC close > EMA20
- BTC close > EMA50
- BTC EMA20 rising
- BTC EMA50 rising
- breadth confirms risk-on if available

Bear candidate:

- BTC close < EMA20
- BTC close < EMA50
- BTC EMA20 falling
- BTC EMA50 falling
- breadth confirms risk-off if available

Sideways candidate:

- BTC close near EMA20 or EMA50
- EMA slopes are flat
- breadth is mixed
- trend confidence is low

Transition candidate:

- BTC trend changing
- EMA structure mixed
- breadth improving or deteriorating
- confidence medium

Unknown:

- data missing
- data stale
- data invalid
- insufficient history
- calculation error

### EMA Slope Formula

```
ema_slope_pct = ((ema_current - ema_n_candles_ago) / ema_n_candles_ago) * 100
```

Where `ema_n_candles_ago` is the EMA value at `t - slope_lookback` candles.

**Rising:** `ema_slope_pct > slope_threshold_pct`

**Falling:** `ema_slope_pct < -slope_threshold_pct`

**Flat:** `abs(ema_slope_pct) <= slope_threshold_pct`

Default `slope_lookback`: 5 candles.
Default `slope_threshold_pct`: 0.5.

Slope direction is used in regime logic and breadth metrics (percent with EMA rising).

### Output File

data/regime/current_regime.json

### Output JSON Contract

Example valid output:

{
  "timestamp": "2026-06-17T00:00:00Z",
  "status": "valid",
  "market_regime": "BULL",
  "allowed_mode": "LONG_ONLY",
  "confidence": 0.82,
  "risk_state": "RISK_ON",
  "btc_trend_score": 85,
  "eth_trend_score": 74,
  "breadth_confirmation_score": 68,
  "reason_codes": [
    "BTC_CLOSE_ABOVE_EMA20",
    "BTC_CLOSE_ABOVE_EMA50",
    "BTC_EMA20_RISING",
    "BREADTH_CONFIRMS_RISK_ON"
  ],
  "data_quality": {
    "missing": false,
    "stale": false,
    "insufficient_history": false
  }
}

**Field ranges:**

- `confidence`: 0.0 to 1.0
- `btc_trend_score`, `eth_trend_score`, `breadth_confirmation_score`: 0 to 100
- `reason_codes`: non-empty array for valid outputs

### Fail-Closed Output Example

{
  "timestamp": "2026-06-17T00:00:00Z",
  "status": "invalid",
  "market_regime": "UNKNOWN",
  "allowed_mode": "NONE",
  "confidence": 0.0,
  "risk_state": "UNKNOWN",
  "btc_trend_score": 0,
  "eth_trend_score": 0,
  "breadth_confirmation_score": 0,
  "reason_codes": [
    "DATA_MISSING",
    "UNKNOWN_REGIME_BLOCKS_EXECUTION"
  ],
  "data_quality": {
    "missing": true,
    "stale": false,
    "insufficient_history": true
  }
}

---

## 2. Market Breadth Engine

### Purpose

Measure whether crypto market strength is broad or narrow.

The Breadth Engine should help answer:

- Is the market broadly strong?
- Is BTC rising alone?
- Are altcoins participating?
- Are most futures pairs above trend?
- Are coins outperforming BTC?

### Inputs

Required input:

- universe candles
- BTC candles

Optional input:

- ETH candles
- symbol metadata
- quote volume filters
- stablecoin dominance placeholder
- BTC dominance placeholder

### Universe

Initial design universe:

Binance Futures USDT perpetual universe

Because real Binance integration does not exist yet, MVP-2 design assumes data is read from local storage or test fixtures.

### Universe Filtering Rules

**Include:**

- USDT perpetual futures symbols
- Active trading status (if metadata available)
- Sufficient local candle history for EMA calculation
- Quote volume above `min_quote_volume` if metadata is available

**Exclude:**

- Stablecoin-only pairs (e.g., USDT/USDC, BUSD/USDT)
- Leveraged tokens if present (symbols containing UP, DOWN, BULL, BEAR)
- BUSD quote pairs
- Symbols with missing required candles
- Symbols with zero or negative close price
- Symbols with zero volume in last N candles
- Symbols with calculation failures

### Invalid Symbol Definition

A symbol is invalid if any of the following is true:

- Required candles are missing
- History is insufficient for EMA calculation
- Latest candle is stale (see stale data rules)
- Close price <= 0
- Volume < 0
- Required timeframe is missing
- Calculation fails (e.g., division by zero, NaN)

Invalid symbols are counted in `invalid_symbol_count` and excluded from percentage calculations.

### Suggested Metrics

Breadth metrics:

- percent above EMA20
- percent above EMA50
- percent above EMA200
- percent with EMA20 rising
- percent with EMA50 rising
- advancing percentage
- declining percentage
- average recent return
- outperforming BTC 7d percentage
- outperforming BTC 30d percentage

### Output File

data/breadth/current_breadth.json

### Output JSON Contract

Example valid output:

{
  "timestamp": "2026-06-17T00:00:00Z",
  "status": "valid",
  "breadth_score": 72,
  "market_health": "RISK_ON",
  "universe_size": 120,
  "valid_symbol_count": 115,
  "invalid_symbol_count": 5,
  "above_ema20_pct": 0.68,
  "above_ema50_pct": 0.55,
  "above_ema200_pct": 0.41,
  "ema20_rising_pct": 0.63,
  "ema50_rising_pct": 0.52,
  "advancing_pct": 0.61,
  "declining_pct": 0.39,
  "outperforming_btc_7d_pct": 0.46,
  "outperforming_btc_30d_pct": 0.34,
  "reason_codes": [
    "MAJORITY_ABOVE_EMA20",
    "EMA20_RISING_BREADTH_POSITIVE",
    "ALT_PARTICIPATION_MODERATE"
  ],
  "data_quality": {
    "missing": false,
    "stale": false,
    "insufficient_universe": false
  }
}

**Field ranges:**

- `breadth_score`: 0 to 100
- Percentage fields (`above_ema20_pct`, etc.): 0.0 to 1.0
- `reason_codes`: non-empty array for valid outputs

### Fail-Closed Output Example

{
  "timestamp": "2026-06-17T00:00:00Z",
  "status": "invalid",
  "breadth_score": 0,
  "market_health": "UNKNOWN",
  "universe_size": 0,
  "valid_symbol_count": 0,
  "invalid_symbol_count": 0,
  "above_ema20_pct": 0.0,
  "above_ema50_pct": 0.0,
  "above_ema200_pct": 0.0,
  "ema20_rising_pct": 0.0,
  "ema50_rising_pct": 0.0,
  "advancing_pct": 0.0,
  "declining_pct": 0.0,
  "outperforming_btc_7d_pct": 0.0,
  "outperforming_btc_30d_pct": 0.0,
  "reason_codes": [
    "DATA_MISSING",
    "INSUFFICIENT_UNIVERSE"
  ],
  "data_quality": {
    "missing": true,
    "stale": false,
    "insufficient_universe": true
  }
}

---

## 3. Reason Codes

Reason codes must be deterministic and machine-readable.

### Data Quality Reason Codes

- DATA_MISSING
- DATA_STALE
- DATA_INVALID
- INSUFFICIENT_HISTORY
- INSUFFICIENT_UNIVERSE
- CALCULATION_ERROR

### Regime Reason Codes

- BTC_CLOSE_ABOVE_EMA20
- BTC_CLOSE_ABOVE_EMA50
- BTC_CLOSE_BELOW_EMA20
- BTC_CLOSE_BELOW_EMA50
- BTC_EMA20_RISING
- BTC_EMA50_RISING
- BTC_EMA20_FALLING
- BTC_EMA50_FALLING
- BTC_TREND_UP
- BTC_TREND_DOWN
- BTC_TREND_MIXED
- SIDEWAYS_STRUCTURE
- TRANSITION_STRUCTURE
- UNKNOWN_REGIME_BLOCKS_EXECUTION

### Breadth Reason Codes

- BREADTH_CONFIRMS_RISK_ON
- BREADTH_CONFIRMS_RISK_OFF
- BREADTH_MIXED
- MAJORITY_ABOVE_EMA20
- MAJORITY_BELOW_EMA20
- MAJORITY_ABOVE_EMA50
- MAJORITY_BELOW_EMA50
- ALT_PARTICIPATION_STRONG
- ALT_PARTICIPATION_MODERATE
- ALT_PARTICIPATION_WEAK

---

## 4. Fail-Closed Rules

The system must fail closed.

If data is missing:

- status = invalid
- market_regime = UNKNOWN
- allowed_mode = NONE
- confidence = 0

If data is stale:

- status = invalid
- market_regime = UNKNOWN
- allowed_mode = NONE
- confidence = 0

If history is insufficient:

- status = invalid
- market_regime = UNKNOWN
- allowed_mode = NONE
- confidence = 0

If calculation fails:

- status = invalid
- market_regime = UNKNOWN
- allowed_mode = NONE
- confidence = 0

Future execution systems must treat allowed_mode = NONE as a hard block.

---

## 5. Config Design

Future MVP-2 config files may include:

- configs/market_state.yaml

Use one config file for MVP-2. Do not create separate regime.yaml and breadth.yaml unless later justified.

### Regime Config

Example settings:

- ema_fast_period: 20
- ema_slow_period: 50
- ema_long_period: 200
- slope_lookback: 5
- slope_threshold_pct: 0.5
- stale_threshold_candles: 2
- max_breadth_age_minutes: 120
- min_history_candles: 200
- bull_score_threshold: 70
- bear_score_threshold: 70
- transition_score_threshold: 50

### Breadth Config

Example settings:

- min_universe_size: 20
- ema_fast_period: 20
- ema_slow_period: 50
- ema_long_period: 200
- outperform_btc_short_days: 7
- outperform_btc_long_days: 30
- stale_threshold_candles: 2
- risk_on_threshold: 65
- risk_off_threshold: 35
- min_quote_volume: 1000000

### Stale Data Definition

Data is stale when:

```
now - latest_candle_close_time > timeframe_duration * stale_threshold_candles
```

Where `timeframe_duration` is the candle interval in minutes (e.g., 60 for 1h, 240 for 4h).

Default `stale_threshold_candles`: 2.

This makes stale checks timeframe-aware. Two missing 1h candles = 120 minutes. Two missing 4h candles = 480 minutes.

Breadth data consumed by the Regime Engine must also be fresh. Maximum age:

- `max_breadth_age_minutes`: 120 (default)

If breadth output is older than this, the Regime Engine treats it as unavailable.

Thresholds must be config-driven.

Hardcoded thresholds should be avoided.

---

## 6. Report Design

Future reports:

- reports/daily/regime_report.md
- reports/daily/breadth_report.md

### Regime Report Should Include

- timestamp
- market regime
- allowed mode
- confidence
- risk state
- BTC trend score
- ETH trend score
- breadth confirmation score
- reason codes
- data quality status

### Breadth Report Should Include

- timestamp
- breadth score
- market health
- universe size
- valid symbol count
- invalid symbol count
- percent above EMA20
- percent above EMA50
- percent above EMA200
- advancing percentage
- declining percentage
- outperforming BTC percentages
- reason codes
- data quality status

---

## 7. Test Plan

### Regime Engine Tests

Test cases:

- missing BTC candles returns UNKNOWN
- stale BTC candles returns UNKNOWN
- insufficient history returns UNKNOWN
- bull regime is detected
- bear regime is detected
- sideways regime is detected
- transition regime is detected
- reason codes are included
- output JSON schema is valid
- allowed_mode is NONE when invalid

### Breadth Engine Tests

Test cases:

- missing universe returns invalid breadth
- insufficient universe returns invalid breadth
- stale universe data returns invalid breadth
- percent above EMA20 is calculated correctly
- percent above EMA50 is calculated correctly
- advancing and declining percentages are calculated correctly
- outperforming BTC percentage is calculated correctly
- reason codes are included
- output JSON schema is valid

### Safety Tests

Test cases:

- no Binance API calls
- no Freqtrade imports
- no trading logic
- invalid state blocks future execution
- stale data blocks future execution
- missing data blocks future execution

---

## 8. Pipeline Order

MVP-2 engines run in this order:

1. Validate local candle data (check missing, stale, insufficient)
2. Run Breadth Engine first
3. Write `data/breadth/current_breadth.json`
4. Run Regime Engine
5. Regime Engine may consume latest breadth output if valid and fresh (within `max_breadth_age_minutes`)
6. Write `data/regime/current_regime.json`

Breadth must complete before Regime. Regime does not block on breadth if breadth is invalid, but will have lower confidence.

---

## 9. JSON Schema Design

Do not create schema files yet. Future implementation should create:

- `schemas/regime.schema.json`
- `schemas/breadth.schema.json`

Schemas must validate:

- required fields present
- enum values for `market_regime`, `allowed_mode`, `risk_state`, `market_health`, `status`
- numeric ranges:
  - `confidence`: 0.0 to 1.0
  - `btc_trend_score`, `eth_trend_score`, `breadth_confirmation_score`, `breadth_score`: 0 to 100
  - percentage fields: 0.0 to 1.0
- `reason_codes` is an array of strings, non-empty for valid outputs
- `data_quality` object with required boolean fields

---

## Implementation

MVP-2 should be implemented later in small steps.

### Step 0 — Apply SPEC-003 Fixes and Re-Review

Before any code is written:

1. Apply the fixes listed in this specification update
2. Re-review SPEC-003 for completeness
3. Only then begin MVP-2 implementation planning

### Step 1 — Create Market State Models

Future files:

- src/hunter/market_state/models.py
- tests/test_market_state/test_models.py

### Step 2 — Create Indicator Utilities

Future files:

- src/hunter/market_state/indicators.py
- tests/test_market_state/test_indicators.py

Initial indicators:

- simple moving average if needed
- exponential moving average
- slope calculation
- percent change
- safe division

### Step 3 — Create Regime Engine

Future files:

- src/hunter/market_state/regime.py
- tests/test_market_state/test_regime.py

### Step 4 — Create Breadth Engine

Future files:

- src/hunter/market_state/breadth.py
- tests/test_market_state/test_breadth.py

### Step 5 — Create JSON Output Writers

Future files:

- src/hunter/market_state/output.py
- tests/test_market_state/test_output.py

### Step 6 — Create Report Templates

Future files:

- reports/daily/

### Step 7 — Update Project Memory

Update:

- docs/handoff/CURRENT_STATE.md
- tasks/backlog.md
- tasks/active.md
- tasks/agent-log.md
- CHANGELOG.md

## Milestones

### 0.3.0-dev — MVP-2 Design

Complete when:

- SPEC-003 exists
- Regime Engine design is complete
- Market Breadth Engine design is complete
- JSON output contracts are defined
- fail-closed behavior is defined
- test plan is defined
- no code has been implemented

### 0.3.0 — MVP-2 Implementation

Complete when:

- Regime Engine exists
- Market Breadth Engine exists
- JSON outputs can be generated from local/test data
- fail-closed behavior works
- tests pass
- no Binance integration exists
- no Freqtrade integration exists
- no trading execution exists

## Gathering Results

MVP-2 succeeds if a future AI agent can answer:

- What is the Regime Engine?
- What is the Market Breadth Engine?
- What inputs are required?
- What output JSON files are produced?
- What happens when BTC data is missing?
- What happens when data is stale?
- What reason codes are used?
- Does invalid state block future execution?
- Is live trading enabled?
- Is Binance integration enabled?
- Is Freqtrade integration enabled?

Expected answers:

- Live trading: no.
- Binance integration: no.
- Freqtrade integration: no.
- Invalid state blocks future execution: yes.
