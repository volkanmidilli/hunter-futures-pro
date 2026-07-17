# SPEC-069 — Research Experiment Ledger, Replication and Multiple-Testing Control

**Status:** Approved  
**MVP:** MVP-68  
**Version target:** `v0.68.0-dev`  
**Source package:** `src/hunter/research_evidence_ledger/`  
**Test package:** `tests/test_research_evidence_ledger/`  

## Scope

A research-only ledger, replication, and multiple-testing control system that consumes immutable MVP-66 and MVP-67 evidence, registers experiments explicitly, detects duplicates and drift, builds deterministic family indexes, applies Benjamini-Hochberg and Bonferroni corrections, and reports replication status without producing actionable trading recommendations.

## Input boundary

The package consumes only:

- `WalkForwardExperimentReport` from MVP-66 (immutable)
- `ExperimentConfidenceReport` from MVP-67 (immutable)

No new market data, backtest execution, Freqtrade invocation, or subprocess is used.

## Public models

- `ExperimentRegistration`
- `ExperimentEvidence`
- `EvidenceLedgerEntry`
- `ExperimentStatus` — `REGISTERED`, `EXECUTED`, `FAILED`, `BLOCKED`, `TIMED_OUT`, `INSUFFICIENT_EVIDENCE`, `COMPLETED`, `WITHDRAWN`
- `IndependenceClass` — `INDEPENDENT`, `RELATED`, `DERIVED`, `DUPLICATE`, `UNKNOWN`
- `HypothesisFamily`
- `ExperimentFamily`
- `MetricFamily`
- `AdjustmentConfig`
- `AdjustmentMethod` — `BENJAMINI_HOCHBERG`, `BONFERRONI`
- `AdjustedEvidence`
- `ReplicationResult`
- `ReplicationState` — `NOT_REPLICATED`, `PARTIALLY_REPLICATED`, `REPLICATED_CANDIDATE`, `REPLICATED_BASELINE`, `CONFLICTING`, `INSUFFICIENT_EVIDENCE`
- `LedgerSnapshot`
- `EvidenceLedgerManifest`
- `EvidenceLedgerReport`
- `EvidenceLedgerSafetyFlags`

All models are frozen and carry hard-coded research-only safety flags.

## Registration

- Requires explicit deterministic `experiment_id`, `experiment_family_id`, and `hypothesis_family_id`.
- Records declared metric set, direction policy, strategy reference, universe plan, timeframe, walk-forward plan fingerprint, confidence config fingerprint, regime policy, and independence class.
- Registration fingerprint is deterministic and excludes wall-clock timestamps, display notes, PID, hostname, absolute paths, and insertion order.
- Registration must precede evidence ingestion; post-hoc evidence is never silently treated as pre-registered.
- Updates produce new immutable registrations with new fingerprints; old registrations are never mutated.

## Duplicate detection

Detects:

- duplicate `experiment_id`
- duplicate registration fingerprint
- duplicate walk-forward report fingerprint
- duplicate confidence report fingerprint
- duplicate complete evidence fingerprint
- repeated identical hypotheses under different IDs
- result-before-registration inconsistency
- missing registration
- post-registration mutation (registration fingerprint mismatch)

## Drift detection

Detects drift in:

- strategy reference
- universe plan
- timeframe
- walk-forward plan
- metric family
- confidence config
- regime policy
- direction policy

Drift is never silently accepted.

## Family indexes

Deterministic indexes for:

- experiment family
- hypothesis family
- metric family
- dependency clusters (via `related_experiment_ids` and independence metadata)

Independence must be explicit; no inference is performed.

## Multiple-testing adjustment

### Benjamini-Hochberg FDR

1. Raw evidence values must be in `[0, 1]`.
2. Sort by raw value ascending, then by canonical evidence ID (`experiment_id:metric_name`) for deterministic tie handling.
3. Compute `adjusted = raw_value * family_size / rank` for each rank.
4. Enforce monotonicity from the largest rank backward.
5. Clamp adjusted values to `1`.
6. Restore original input order.
7. Preserve raw values exactly.

### Bonferroni

`adjusted = min(raw_value * family_size, 1)`

### Terminology

Values are referred to as "raw evidence value" and "adjusted evidence value" unless a formal p-value framework has been established.

## Replication

- Replication is computed per metric and hypothesis family.
- Only experiments with `IndependenceClass.INDEPENDENT` are counted by default unless an explicit policy permits dependents.
- Requires explicit minimum independent-experiment count.
- Preserves MVP-67 direction states: candidate-supported, baseline-supported, mixed, unstable, insufficient.
- Replication states are symmetric between candidate and baseline.
- Prohibited labels: `BEST_STRATEGY`, `BEST_UNIVERSE`, `WINNER`, `PROFITABLE`, `GUARANTEED`, `APPROVED`, `READY_FOR_LIVE`, `EXECUTION_ALLOWED`, `PRODUCTION_READY`.
- No composite experiment score or automatic strategy/universe selection.

## Snapshots

- Immutable snapshot chaining with `previous_snapshot_fingerprint` (or `None`).
- Contains ordered registrations, ordered ledger entries, family indexes, adjustment results, and replication results.
- Old snapshots are never mutated.
- Broken previous-snapshot linkage is detected.
- Correction and withdrawal records are appended without deleting historical evidence.

## Fingerprints

Deterministic SHA-256 fingerprints for:

- registration
- experiment evidence
- ledger entry
- experiment family
- hypothesis family
- adjustment result
- replication result
- snapshot
- report
- manifest

Excluded from fingerprint input: absolute paths, temporary paths, wall-clock timestamps, `generated_at`, runtime durations, PID, hostname, object IDs, dictionary insertion order, display notes, file mtime.

## Writer

- Requires explicit `output_dir`; no default.
- Atomic JSON/Markdown writes via temp file + `os.replace`.
- Rejects silent overwrite; supports explicit `overwrite=True`.
- Removes partial files on failure.
- Rejects output under `data/` and `reports/`.
- Redacts paths and secrets.
- Excludes raw runtime logs.
- Markdown includes the mandatory research-only safety notice.
- Output files:
  - `experiment_registrations.json`
  - `evidence_ledger_entries.json`
  - `experiment_family_index.json`
  - `hypothesis_family_index.json`
  - `metric_family_index.json`
  - `multiple_testing_adjustments.json`
  - `replication_results.json`
  - `evidence_ledger_snapshot.json`
  - `evidence_ledger_report.json`
  - `evidence_ledger_report.md`
  - `evidence_ledger_manifest.json`

## Safety invariants

Every public artifact carries:

| Flag | Value |
|------|-------|
| `research_only` | `True` |
| `execution_approval_granted` | `False` |
| `production_approval_granted` | `False` |
| `live_trading_allowed` | `False` |
| `automatic_execution_allowed` | `False` |
| `human_approval_required` | `True` |
| `no_direct_subprocess` | `True` |
| `no_parallel_execution` | `True` |

## No-go behaviors

This package does not:
- invoke subprocesses or call Freqtrade directly;
- run any backtest or trading simulation;
- access exchanges, networks, databases, or market data;
- download or modify data files;
- mutate strategy, configuration, or universe files;
- emit orders, signals, positions, leverage, entries, or exits;
- create scheduler, queue, or persistent runtime;
- inspect or modify `data/` or `reports/`;
- produce composite trading scores or rankings;
- push or modify remote state;
- grant execution, production, live-trading, or automatic-execution approval.

## Approval status

- No execution approval.
- No production approval.
- No live trading approval.
- No automatic execution approval.
- Human approval required before any runtime or production use.
