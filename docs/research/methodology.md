# Research Methodology Policies

> **Research only.** This document describes statistical and methodological policies for the Hunter Futures Pro research pipeline. Nothing here authorizes execution, production deployment, live trading, dry-run trading, automatic execution, strategy selection, universe selection, order placement, signal generation, strategy mutation, universe mutation, or position changes. Human review remains required.

## Scope

The methodology policies defined here are enforced across:

- `src/hunter/research_walk_forward/`
- `src/hunter/research_statistical_confidence/`
- `src/hunter/research_backtest_comparison/` (zero-trade / evidence-availability)

They do not perform any runtime / network / exchange / database / scheduler / queue operations and do not emit actionable trading signals.

## 1. Zero-Trade and Evidence-Availability Policy

### States

| State | Meaning |
|---|---|
| `AVAILABLE` | Trade count >= `min_trades` AND metric is present. Enters default bootstrap samples. |
| `ZERO_TRADES` | trade_count == 0. Excluded from default samples. |
| `INSUFFICIENT_TRADES` | 0 < trade_count < `min_trades`. Excluded. |
| `ONE_SIDED_ZERO_TRADES` | Exactly one arm produced zero trades. Not silently comparable. Excluded. |
| `MISSING_METRIC` | trade_count unknown (parser did not surface the value) or the metric value itself is absent. Excluded. |
| `PARSER_FAILED` | Parser raised. Excluded. |
| `BLOCKED` | Compatibility / runtime gate blocked execution. Excluded. |
| `TIMED_OUT` | Subprocess timed out. Excluded. |
| `UNSUPPORTED_SCHEMA` | Export schema not recognized. Excluded. |

### Precedence (highest first)

```text
BLOCKED → TIMED_OUT → UNSUPPORTED_SCHEMA → PARSER_FAILED →
ZERO_TRADES → INSUFFICIENT_TRADES → MISSING_METRIC → AVAILABLE
```

### Invariants

- A valid numeric zero return WITH executed trades (`trade_count > 0` and metric value == 0) is `AVAILABLE` evidence — it is a numeric zero, not zero-trade unavailability.
- One-sided zero trades is never silently comparable: `compare_backtest_results` attaches `ONE_SIDED_ZERO_TRADES` plus `NO_TRADES_CANDIDATE` or `NO_TRADES_BASELINE`.
- Unavailable / insufficient values never become numeric zero.
- Only `AVAILABLE` deltas enter default bootstrap / confidence samples.
- Excluded counts and reason codes are preserved on the report.
- `min_trades` is explicit and configurable on `compare_backtest_results(min_trades=...)` (default 1).

### Migration

Pre-Phase B behavior fabricated zero metrics for zero-trade exports. Post-Phase B zero-trade exports surface `NO_TRADES` on `BacktestMetrics` and leave numeric fields `None` (serialized as `UNAVAILABLE`). Downstream consumers must treat `None` as unavailable rather than zero.

## 2. Canonical Quartiles

A single median-of-halves (Tukey's hinges) quartile implementation is shared between `research_walk_forward.aggregation._quartiles` and `research_statistical_confidence.descriptive._quartiles`.

### Behavior

| Input | Q1 | Q3 | IQR |
|---|---|---|---|
| empty | None | None | None |
| singleton (n=1) | value | value | 0 |
| two values (n=2) | min | max | max - min |
| three values (n=3, odd) | median of lower half (inclusive of median) | median of upper half (inclusive of median) | q3 - q1 |
| even count | median of lower half | median of upper half | q3 - q1 |
| odd count | median of lower half (includes median) | median of upper half (includes median) | q3 - q1 |
| repeated values | median-of-halves applied as usual | same | q3 - q1 |
| negatives | works | works | q3 - q1 |
| Decimal values | exact Decimal arithmetic preserved | preserved | preserved |

### Quartile policy / schema version

The `QuartilePolicy` reports a `policy` field of `"QuartilePolicy"` and emits `QUARTILE_MISMATCH` if MVP-66 and MVP-67 disagree for a given delta list. The canonical implementation guarantees they agree.

## 3. Constant-Delta Policy

### Detection

A sample is flagged when:

- **Zero observed dispersion:** all available deltas are identical (`std_dev == 0`). Reason code `ZERO_OBSERVED_DISPERSION`.
- **Insufficient distinct values:** number of distinct delta values < `min_distinct_values_for_bootstrap` (default 2). Reason code `INSUFFICIENT_DISTINCT_VALUES`.

A constant non-zero sample triggers BOTH reason codes (when `min_distinct_values_for_bootstrap >= 2`).

### Classification impact

`classify_metric_confidence` accepts `zero_observed_dispersion` and `insufficient_distinct_values` keyword flags. When either is True:

- The classifier never returns `ROBUST_CANDIDATE` or `ROBUST_BASELINE`, because a constant non-zero sample produces a non-zero *point* bootstrap interval that does not constitute dispersion-based evidence.
- Directional stability is still preserved when sign-share and leave-one-out conditions hold (returns `DIRECTIONALLY_STABLE_CANDIDATE` or `DIRECTIONALLY_STABLE_BASELINE`).

Symmetry: a constant negative sample routes to `DIRECTIONALLY_STABLE_BASELINE`; a constant positive sample routes to `DIRECTIONALLY_STABLE_CANDIDATE`.

### Configuration

`BootstrapConfig.min_distinct_values_for_bootstrap` (default 2) is the explicit threshold. Raise it when more dispersion is required before treating a sample as exchangeable.

## 4. Window Dependence Policy

### States

| Status | Meaning |
|---|---|
| `NON_OVERLAPPING` | No pair of evaluation windows overlaps. Independent-replication claims allowed by default. |
| `OVERLAPPING` | At least one pair of evaluation windows overlaps. Independent-replication claims must exclude overlapping windows. |
| `UNKNOWN` | One or more evaluation boundaries could not be parsed. Conservative interpretation excludes the windows from independent-replication claims. |

### Reported fields

- `status`: one of the three values above.
- `overlapping_eval_pair_count`: number of overlapping evaluation-window pairs.
- `max_overlap_seconds`: maximum overlap duration in seconds across evaluation windows.
- `dependencies`: list of `{window_a, window_b, kind}` records where `kind` is `"selection"` or `"evaluation"`.

### Defaults

- Independent-replication claims exclude overlapping / dependent windows by default.
- The bootstrap writer emits an `## Exchangeability Assumption` section stating that bootstrap intervals assume exchangeable deltas and that overlapping / dependent windows are excluded from independent-replication claims.
- No automatic regime inference.
- No block bootstrap unless explicitly justified and approved separately.

### Boundary parsing

Window boundaries use `YYYYMMDD` strings. `_parse_boundary_date` returns a day ordinal (days since 1970-01-01) and `None` for unparseable strings. `_overlap_seconds` returns `None` if any boundary is unparseable, otherwise returns the closed-interval overlap in seconds (`(min_end - max_start + 1) * 86400`).

## 5. Safety invariants

All methodology artifacts preserve:

```text
research_only=True
execution_approval_granted=False
production_approval_granted=False
live_trading_allowed=False
automatic_execution_allowed=False
human_approval_required=True
```

Construction of any safety-flags dataclass with a violating value raises `ValueError`.

## Mandatory notice

This artifact is research-only. Real Freqtrade backtesting compatibility, historical-result parsing, methodology policies, confidence intervals, and stability labels do not prove profitability and do not authorize execution, production deployment, live trading, dry-run trading, automatic execution, strategy selection, universe selection, order placement, signal generation, strategy mutation, universe mutation, or position changes. Human review remains required.