# SPEC-068 — Walk-Forward Statistical Confidence and Stability Evaluation

**Status:** Approved  
**MVP:** MVP-67  
**Version target:** `v0.67.0-dev`  
**Source package:** `src/hunter/research_statistical_confidence/`  
**Test package:** `tests/test_research_statistical_confidence/`  

## Scope

A research-only statistical confidence layer that consumes completed MVP-66 `WalkForwardExperimentReport` objects and evaluates whether candidate-versus-baseline metric deltas are stable under deterministic resampling and robust to removal of individual windows.

MVP-67 does **not** run new backtests, invoke Freqtrade, call subprocesses, read market data, or mutate strategies, configs, universes, signals, orders, positions, leverage, entries, or exits.

## Research question

> Are Candidate-versus-Baseline metric deltas stable under deterministic resampling and robust to removal of individual windows?

## Requirements

### Must Have

- Consume immutable MVP-66 `WalkForwardExperimentReport` evidence.
- Never invoke Freqtrade or subprocess.
- Never inspect or modify `data/` or `reports/`.
- Validate inherited safety invariants.
- Analyze each canonical metric independently.
- Preserve unavailable values; never replace them with zero.
- Require explicit minimum available-window count.
- Produce:
  - sample/unavailable counts
  - mean, median, standard deviation, MAD
  - min, max, q1, q3, IQR
  - positive/negative/zero shares
  - deterministic bootstrap CI for mean and median
  - leave-one-window-out mean/median ranges
  - maximum single-window influence
  - sign stability
  - regime coverage
  - reason codes
- Require explicit bootstrap seed and iteration count.
- Use local deterministic PRNG only.
- Implement percentile intervals explicitly.
- Support explicit confidence level.
- Support leave-one-window-out sensitivity.
- Support caller-provided regime stratification only.
- Use only these confidence states:
  - `INSUFFICIENT_EVIDENCE`
  - `UNSTABLE`
  - `MIXED`
  - `DIRECTIONALLY_STABLE_CANDIDATE`
  - `DIRECTIONALLY_STABLE_BASELINE`
  - `ROBUST_CANDIDATE`
  - `ROBUST_BASELINE`
- Never emit statistically proven, guaranteed, profitable, winner, approved, ready-for-live, execution-allowed, or production-ready claims.
- Do not create a composite trading score.
- Do not rank strategies or select universes.
- Produce deterministic fingerprints for config, per-metric results, regime results, report, and manifest.
- Exclude paths, PID, hostname, timestamps, durations, and insertion order from fingerprints.
- Require explicit output directory.
- Produce deterministic atomic JSON/Markdown.
- Reject output under `data/` and `reports/`.
- Preserve:
  - `research_only=True`
  - `execution_approval_granted=False`
  - `production_approval_granted=False`
  - `live_trading_allowed=False`
  - `automatic_execution_allowed=False`
  - `human_approval_required=True`
- Coordinator is sole Git owner.
- No push or remote changes.
- One active stage only.
- Do not start MVP-68.

### Won't Have

- Backtest execution
- Freqtrade invocation
- Subprocess
- Exchange/network/data access
- Strategy/config/universe mutation
- Regime inference
- Strategy or universe selection
- Composite trading score
- Live/dry-run trading
- Orders/signals/positions/leverage/entry/exit behavior
- Scheduler/database/queue
- Automatic retry
- Production/execution/live approval

## Method

### Package

```text
src/hunter/research_statistical_confidence/
├── models.py
├── errors.py
├── validator.py
├── descriptive.py
├── bootstrap.py
├── sensitivity.py
├── regime.py
├── classification.py
├── fingerprint.py
├── engine.py
├── writer.py
└── __init__.py
```

### Tests

```text
tests/test_research_statistical_confidence/
├── test_models.py
├── test_validator.py
├── test_descriptive.py
├── test_bootstrap.py
├── test_sensitivity.py
├── test_regime.py
├── test_classification.py
├── test_fingerprint.py
├── test_engine.py
├── test_writer.py
├── test_integration.py
├── test_determinism.py
└── test_safety.py
```

### Core Models

- `StatisticalConfidenceConfig`
- `BootstrapConfig`
- `RobustnessCriteria`
- `MetricConfidenceResult`
- `LeaveOneOutResult`
- `BootstrapInterval`
- `RegimeConfidenceResult`
- `ExperimentConfidenceReport`
- `ConfidenceState`

All public models are frozen dataclasses.

### Config Validation

Require:

- minimum counts >= 2
- `0 < confidence_level < 1`
- explicit bounded bootstrap iterations (>= 100)
- explicit integer seed
- `0.5 <= sign_share_threshold <= 1`
- `0 <= maximum_influence_ratio <= 1`

### Deterministic Bootstrap

Use:

```python
rng = random.Random(config.bootstrap_seed)
```

For each iteration, sample `n` deltas with replacement, then calculate mean and median. Percentile interval uses the nearest-rank method with explicit clamped indices.

### Leave-One-Out Sensitivity

For each available window, remove it, recompute mean and median, record direction, calculate influence, and identify the most influential window.

### Classification

```text
available_count below threshold
→ INSUFFICIENT_EVIDENCE

direction conflict or weak sign share
→ MIXED

leave-one-out instability or excessive influence
→ UNSTABLE

stable Candidate direction
→ DIRECTIONALLY_STABLE_CANDIDATE

stable Baseline direction
→ DIRECTIONALLY_STABLE_BASELINE

stable direction + configured CI/influence criteria
→ ROBUST_CANDIDATE or ROBUST_BASELINE
```

Positive delta = Candidate higher; negative delta = Baseline higher. These are descriptive research classifications only.

### Writers

Outputs:

```text
statistical_confidence_config.json
metric_confidence_results.json
regime_confidence_results.json
experiment_confidence_report.json
experiment_confidence_report.md
statistical_confidence_manifest.json
```

Mandatory notice:

```text
This artifact is research-only and summarizes statistical stability
of historical walk-forward comparisons.
Bootstrap intervals, sensitivity results, regime summaries,
and confidence classifications are descriptive research evidence only.
They do not prove profitability and do not authorize execution,
production deployment, live trading, automatic execution,
strategy selection, universe selection, order placement,
signal generation, strategy mutation, universe mutation,
or position changes.
Human review remains required.
```

## Implementation Stages

1. Models, errors, safety contracts
2. Validation and descriptive statistics
3. Deterministic bootstrap
4. Leave-one-out sensitivity
5. Regime stratification
6. Confidence classification
7. Fingerprints
8. Engine and writers
9. Integration, adversarial, regression, full suite
10. Read-only review, docs, version, local tag

## Approval Status

- No execution approval.
- No production approval.
- No live trading approval.
- No automatic execution approval.
- Human approval required before any runtime or production use.
