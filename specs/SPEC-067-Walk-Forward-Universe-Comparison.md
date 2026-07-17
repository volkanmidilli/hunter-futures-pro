# SPEC-067 — Walk-Forward Universe Comparison and Regime Evaluation

**Status:** Approved  
**MVP:** MVP-66  
**Version target:** `v0.66.0-dev`  
**Source package:** `src/hunter/research_walk_forward/`  
**Test package:** `tests/test_research_walk_forward/`  

## Scope

A research-only walk-forward experiment harness that consumes the MVP-64 dual universe (candidate and baseline pairlists) and runs the MVP-65 `research_backtest_comparison` engine once per window. The harness produces descriptive, deterministic evidence across multiple in-sample/out-of-sample windows, grouped by caller-provided regime labels, without any live or dry-run trading behavior.

## Runtime boundary

- **Only MVP-65 may invoke Freqtrade.** MVP-66 does not contain subprocess code, direct Freqtrade calls, or any execution logic.
- Windows run **sequentially**. No parallel execution path, no thread pool, no asyncio concurrency, no automatic retry.
- No exchange, network, database, scheduler, queue, or live-runtime connection.
- No data download or modification of `data/` or `reports/`.

## Safety invariants

Every public artifact carries these hard-coded safety flags:

| Flag | Value |
|------|-------|
| `research_only` | `True` |
| `execution_approval_granted` | `False` |
| `production_approval_granted` | `False` |
| `live_trading_allowed` | `False` |
| `automatic_execution_allowed` | `False` |
| `human_approval_required` | `True` |
| `no_direct_subprocess` | `True` (in MVP-66) |
| `no_parallel_execution` | `True` (in MVP-66) |

## Plan builder

Two modes are supported:

- **ROLLING**: fixed-size selection and evaluation windows; windows step forward by `step_days`.
- **EXPANDING**: selection window grows from a fixed start; evaluation window is fixed size and steps forward.

Plans are deterministic and require explicit boundaries. The builder supports:
- explicit `List[WalkForwardWindow]` supplied by the caller, or
- parameter-driven generation from `selection_start`, `evaluation_start`, `evaluation_duration_days`, `step_days`, and `count`.

Validation rejects:
- duplicate windows
- out-of-order windows
- backward selection/evaluation ranges
- overlapping evaluation windows
- rolling windows whose duration changes
- expanding windows whose selection start changes
- non-contiguous windows when `contiguous=True`

## Leakage guard

Each window must satisfy strict chronology:

```
selection_start < selection_end < evaluation_start < evaluation_end
```

Across windows:
- evaluation windows must be strictly ordered and non-overlapping;
- selection windows must move forward in time;
- no evaluation window may overlap a selection window of a later window.

## Window runner

The runner calls the MVP-65 engine once per window with the appropriate `timerange` derived from the window's selection/evaluation period. The policy `COLLECT_ALL` runs every window even if some fail; `FAIL_FAST` stops on the first failure. The runner preserves evidence for:
- `COMPLETED`
- `FAILED`
- `BLOCKED`
- `TIMED_OUT`
- `UNSUPPORTED`
- `INSUFFICIENT` (insufficient trades)

## Metric aggregation

All 12 canonical MVP-65 metrics are aggregated:

- `total_return_pct`
- `absolute_profit`
- `final_balance`
- `max_drawdown_pct`
- `sharpe_ratio`
- `sortino_ratio`
- `calmar_ratio`
- `profit_factor`
- `win_rate_pct`
- `trade_count`
- `average_trade_duration_seconds`
- `fees_paid`

For each metric the aggregator computes:

- `available_count` / `unavailable_count`
- `candidate_higher_count` / `baseline_higher_count` / `equal_count`
- `mean` (Decimal)
- `median` (Decimal)
- `min` / `max` (Decimal)
- `q1` / `q3` / `iqr` (explicit median-of-halves quartiles, Decimal)
- `positive_delta_share` / `negative_delta_share` / `zero_delta_share` (Decimal)
- `consistency_state` (descriptive only)

### Consistency states

- `CONSISTENT_CANDIDATE_HIGHER`: 100% of available windows show candidate higher.
- `MOSTLY_CANDIDATE_HIGHER`: ≥70% candidate higher.
- `MIXED`: neither side reaches 70%.
- `MOSTLY_BASELINE_HIGHER`: ≥70% baseline higher.
- `CONSISTENT_BASELINE_HIGHER`: 100% baseline higher.
- `EQUAL_OR_UNAVAILABLE`: no available comparisons.

Missing metrics are treated as unavailable and never fabricated.

## Regime aggregation

Regime labels are caller-provided only. The supported labels are:

- `BULL`
- `BEAR`
- `SIDEWAYS`
- `HIGH_VOLATILITY`
- `LOW_VOLATILITY`
- `UNKNOWN` (default when no label is supplied)

No automatic regime inference is performed. Regime aggregates contain the same metric aggregates as the overall report and status counts per window.

## Fingerprints

Deterministic SHA-256 fingerprints are produced for:

- the plan (`plan_fingerprint`)
- each window result (`window_result_fingerprint`)
- the overall metric aggregates (`overall_aggregate_fingerprint`)
- each regime aggregate (`regime_aggregate_fingerprint`)
- the full regime set (`regime_overall_fingerprint`)
- the manifest (`manifest_fingerprint`)
- the report (`report_fingerprint`)

Fingerprints exclude temporary paths, process ID, hostname, wall-clock time, runtime durations, stdout/stderr, and file modification times.

## Writers

The writer produces:

- `walk_forward_plan.json`
- `walk_forward_window_results.json`
- `walk_forward_metric_aggregates.json`
- `walk_forward_regime_aggregates.json`
- `walk_forward_experiment_report.json`
- `walk_forward_manifest.json`
- `walk_forward_experiment_report.md`

All JSON writes are atomic (`tempfile` + `os.replace`). Silent overwrite is blocked by default; `overwrite=True` is allowed. Failed writes clean up temp files. Paths are redacted in the JSON/Markdown output. Secrets are redacted in Markdown. Outputs under `data/` or `reports/` are rejected.

## Report structure

`WalkForwardExperimentReport` contains:

- plan, window results, metric aggregates, regime aggregates, manifest
- safety flags
- human_approval_required
- research_only
- fingerprint
- version metadata
- mandatory research-only notice

## Approval status

- No execution approval.
- No production approval.
- No live trading approval.
- No automatic execution approval.
- Human approval required before any runtime or production use.

## No-go behaviors

MVP-66 does not:
- invoke subprocesses or call Freqtrade directly;
- run windows in parallel;
- retry failed windows automatically;
- access exchanges, networks, or databases;
- download or modify market data;
- mutate strategy, configuration, or universe files;
- emit orders, signals, positions, leverage, entries, or exits;
- create scheduler, queue, or persistent runtime;
- inspect or modify `data/` or `reports/`;
- push or modify remote state.
