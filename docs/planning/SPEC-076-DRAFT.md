# SPEC-076-Ranking-Outcome-Evaluation-and-Calibration

**Status:** Planning Draft  
**MVP:** MVP-76 (unassigned)  
**Version target:** TBD  
**Source package:** `src/hunter/research_outcome_evaluation/`  
**Test package:** `tests/test_research_outcome_evaluation/`  

## Background

Hunter Futures Pro produces daily ranking snapshots via `pairlist from-feather` (SPEC-074/075). Each snapshot is an immutable JSON audit artifact containing a ranked selection of candidate pairs with relative strength and liquidity scores. To date, there is no systematic evaluation of whether the ranking profile produces positive outcomes after selection.

SPEC-076 defines a Phase A research-only evaluation layer that answers: *"For each matured (snapshot_date, ranking_profile, outcome_horizon) cohort, what were the realized outcomes for the selected pairs?"* Phase A is strictly selected-only, descriptive-only for overlapping cohorts, and never changes weights, parameters, algorithms, execution behavior, snapshots, Feather data, network sources, or scheduling.

## Requirements

### Must Have

1. Consume immutable snapshot audit artifacts (JSON) as the only cohort-membership source.
2. Evaluate selected pairs only; Phase A is selected-only.
3. Support 1d, 3d, and 7d outcome horizons; horizons are extensible without schema migration.
4. Use the snapshot reference close (last completed 1h candle at or before snapshot_date 08:00 UTC) as the entry anchor.
5. Resolve every matured cohort member to a terminal state in the same evaluation run; no matured cohort member may be skipped.
6. Emit these Phase A terminal codes: `OUTCOME_AVAILABLE`, `SNAPSHOT_INVALID`, `OUTCOME_UNAVAILABLE_NO_SOURCE`, `OUTCOME_UNAVAILABLE_GAP`, `OUTCOME_UNAVAILABLE_INVALID_PRICE`, `BENCHMARK_UNAVAILABLE`. Reserve `OUTCOME_UNAVAILABLE_DELISTED` in the schema and never emit it in Phase A.
7. Apply this resolution order:
   - Before horizon elapsed: compute transient `PENDING_HORIZON` only and never persist it.
   - After horizon elapsed, evaluate in order:
     1. Invalid snapshot → `SNAPSHOT_INVALID`
     2. Missing pair price source → `OUTCOME_UNAVAILABLE_NO_SOURCE`
     3. Missing required endpoint candles → `OUTCOME_UNAVAILABLE_GAP`
     4. Endpoint candles fail SPEC-075 price validation → `OUTCOME_UNAVAILABLE_INVALID_PRICE`
     5. Valid intra-window coverage below `min_window_coverage` → `OUTCOME_UNAVAILABLE_GAP`
     6. Benchmark validation fails → `BENCHMARK_UNAVAILABLE`
     7. Otherwise → `OUTCOME_AVAILABLE`
8. Produce Pair Observation Records exactly once at terminal resolution; records are immutable after creation.
9. Produce Snapshot Summary Records per (snapshot_date, ranking_profile, outcome_horizon).
10. Compute horizon-specific metrics with explicit `_1d` / `_3d` / `_7d` suffixes on flattened report metric names:
    - Top-N returns: `top_5_return_pct_1d/_3d/_7d`, `top_10_return_pct_1d/_3d/_7d`, `top_20_return_pct_1d/_3d/_7d`, `top_30_return_pct_1d/_3d/_7d`
    - Spearman correlations: `spearman_rank_return_1d/_3d/_7d`, `spearman_relative_strength_return_1d/_3d/_7d`, `spearman_liquidity_return_1d/_3d/_7d`
    - Benchmark-relative returns: `benchmark_relative_return_pct_1d/_3d/_7d`
    - Maximum Adverse Excursion: `mae_pct_1d/_3d/_7d`
    - Maximum Favorable Excursion: `mfe_pct_1d/_3d/_7d`
    - Realized volatility: `realized_volatility_pct_1d/_3d/_7d`
11. Enforce `min_window_coverage` (default 0.95); coverage below threshold resolves to `OUTCOME_UNAVAILABLE_GAP`.
12. Handle the BTC benchmark special case: `is_benchmark_pair = true`, `benchmark_return = realized_return`, `benchmark_relative_return = 0`; exclude BTC only during benchmark-relative aggregation.
13. Use descriptive-only statistical output for overlapping cohorts; no inferential pipeline for dependent observations.
14. Apply a calibration gate requiring at least 30 matured cohorts per horizon (60 recommended).
15. Enforce fail-closed statistical behavior; no observation is silently discarded.
16. Persist atomically using SPEC-074 discipline (temporary file, fsync, atomic rename).
17. Maintain append-only storage through deterministic immutable artifacts; existing-file behavior follows snapshot immutability semantics (identical content is a no-op, differing content is rejected).
18. Provide CLI commands `hunter outcome evaluate` and `hunter outcome report` with distinct `--snapshot-dir` (read-only JSON snapshots), `--data-dir` (read-only Feather prices), and `--store-dir` (append-only evaluation output).
19. Enforce no network access, no scheduler changes, no execution integration, no Freqtrade invocation.

### Should Have

1. Report turnover, retention, and daily data-availability values duplicated identically across horizon summaries for reporting convenience.
2. Handle first-snapshot turnover and retention as null with reason `FIRST_SNAPSHOT`.
3. Store benchmark failure diagnostics (`benchmark_failure_reason`) in the summary.
4. Retain `benchmark_return` diagnostically when computable, even if the pair has another terminal unavailable state.

### Could Have

1. Configurable `min_window_coverage` (default 0.95).
2. `OUTCOME_UNAVAILABLE_DELISTED` schema reservation (never emitted in Phase A).

### Won't Have (Phase A)

1. Inferential statistical analysis for overlapping cohorts (bootstrap CIs, LOO robustness, confidence states, significance claims).
2. Regime calculation, labeling, or stratification.
3. Automatic calibration, parameter changes, or weight changes.
4. Delisting heuristics; missing data must never be inferred as delisting.
5. Historical recomputation or rebuilding of evaluation facts.
6. Network access, scheduler changes, or database connections.
7. Execution integration, Freqtrade invocation, live trading, or dry-run trading.
8. Composite trading score or strategy/universe selection.
9. Subprocess invocation or parallel execution.
10. Selected-versus-rejected comparison, full-universe evaluation, explicit delisting detection, regime-aware evaluation, dependency-aware inference, block/cluster bootstrap, calibration recommendation generation, and explicit historical rebuild tooling (deferred to Phase B).

## Method

### Cohort Data Model

- **Cohort-membership source:** Immutable JSON snapshot audit artifacts produced by the pairlist snapshot workflow (SPEC-074/075). Historical rankings are never recomputed.
- **Price source:** Feather files containing 1h pair and benchmark price series. Feather is used only for price series; snapshots are read from `--snapshot-dir`.
- **Phase A scope:** Selected pairs only.
- **Horizons:** Ship as 1d, 3d, 7d and are extensible without schema migration. Horizon durations are +24h, +72h, +168h from the snapshot reference close, not calendar-day boundaries.
- **Snapshot reference close:** The last completed 1h candle at or before snapshot_date 08:00 UTC. Reference anchors derive only from snapshot_date.
- **Cohort key:** (snapshot_date, ranking_profile, outcome_horizon).
- **Immutability:** Snapshots are the only cohort-membership source; late Feather additions do not rewrite historical evaluation facts.

### Outcome Resolution

- **PENDING_HORIZON:** Computed transiently and never persisted.
- **Phase A terminal codes:** `OUTCOME_AVAILABLE`, `SNAPSHOT_INVALID`, `OUTCOME_UNAVAILABLE_NO_SOURCE`, `OUTCOME_UNAVAILABLE_GAP`, `OUTCOME_UNAVAILABLE_INVALID_PRICE`, `BENCHMARK_UNAVAILABLE`.
- **Schema reservation:** `OUTCOME_UNAVAILABLE_DELISTED` is reserved and never emitted in Phase A.
- **Resolution order:**
  - Before horizon elapsed: compute transient `PENDING_HORIZON` only and never persist it.
  - After horizon elapsed, evaluate in order:
    1. Invalid snapshot → `SNAPSHOT_INVALID`
    2. Missing pair price source → `OUTCOME_UNAVAILABLE_NO_SOURCE`
    3. Missing required endpoint candles → `OUTCOME_UNAVAILABLE_GAP`
    4. Endpoint candles fail SPEC-075 price validation → `OUTCOME_UNAVAILABLE_INVALID_PRICE`
    5. Valid intra-window coverage below `min_window_coverage` → `OUTCOME_UNAVAILABLE_GAP`
    6. Benchmark validation fails → `BENCHMARK_UNAVAILABLE`
    7. Otherwise → `OUTCOME_AVAILABLE`
- **Coverage rules:** `min_window_coverage` defaults to 0.95 and is configurable. Invalid non-endpoint candles count as missing for coverage. Coverage below threshold resolves to `OUTCOME_UNAVAILABLE_GAP`.
- **Atomic cohort resolution:** Once a horizon has elapsed, every cohort member resolves to a terminal state in the same evaluation run; no member is skipped.
- **Immutability:** Evaluation records are immutable after creation; late Feather additions do not rewrite historical evaluation facts.
- **Contract completeness:** Outcome status represents the complete evaluation contract, not merely pair-price availability. No observation is silently discarded.

### Benchmark Contract

- **Benchmark:** BTC/USDT:USDT using the same reference anchor, endpoints, validation contract, and coverage threshold as pair evaluation.
- **Discovery:** Benchmark price series is discovered via the existing SPEC-075 price-source discovery contract.
- **Shared validation:** Benchmark validation is performed once per snapshot/profile/horizon evaluation and shared by all cohort members.
- **Benchmark failure:** A pair that passes its own checks but whose benchmark fails resolves to `BENCHMARK_UNAVAILABLE`.
- **BTC special case (mandatory):** When BTC is selected: `is_benchmark_pair = true`, `benchmark_return = realized_return`, `benchmark_relative_return = 0`. BTC exclusion occurs only during benchmark-relative aggregation.
- **Sign convention:** `benchmark_relative_return = pair_return - benchmark_return`; positive means the selected pair outperformed BTC. This intentionally matches the existing statistical confidence engine's positive-delta direction convention (S3).
- **Diagnostics:** `benchmark_failure_reason` may be stored in the summary. `benchmark_return` may be retained diagnostically when computable, even if the pair has another terminal unavailable state.

### Metrics

- **Horizon identity:** Flattened report metric names carry explicit `_1d` / `_3d` / `_7d` suffixes. Inside Snapshot Summary Records already keyed by `outcome_horizon`, normalized field names may remain unsuffixed. Cross-horizon aggregation under one logical metric identity is prohibited (S2).
- **Top-N returns:** `top_5_return_pct`, `top_10_return_pct`, `top_20_return_pct`, `top_30_return_pct` for each horizon, flattened as `top_N_return_pct_1d/_3d/_7d`.
- **Spearman correlations (S1):** Cross-sectional per matured (snapshot_date, ranking_profile, outcome_horizon) using **all** `OUTCOME_AVAILABLE` pair observations in that cohort:
  - `spearman_rank_return` — Spearman(rank_at_selection, realized_return)
  - `spearman_relative_strength_return` — Spearman(relative_strength_score, realized_return)
  - `spearman_liquidity_return` — Spearman(liquidity_score, realized_return)
  - Rank and scores come from the immutable JSON snapshot audit artifact; returns from terminal Pair Observation Records.
  - Spearman is computed over all `OUTCOME_AVAILABLE` observations in the cohort, never Top-N-only.
  - Overlap between daily cohorts does not affect the within-cohort Spearman calculation; aggregation of Spearman values across overlapping cohorts is descriptive-only.
- **Benchmark-relative returns:** `benchmark_relative_return_pct` per horizon.
- **MAE/MFE:** Calculated separately per horizon (entry = snapshot reference close; MAE uses intra-window 1h lows; MFE uses intra-window 1h highs).
- **Realized volatility:** Population standard deviation of valid intra-window 1h log returns, expressed as a percentage and not annualized. Invalid candles are excluded as missing; coverage is checked before calculation. Fewer than two valid returns produces no metric value and follows the applicable terminal/availability contract.
- **Separation:** Horizon-dependent metrics are computed separately per horizon.

### Statistical Confidence

Phase A reuses only the existing descriptive methodology implemented by `research_statistical_confidence` (MVP-67 / SPEC-068). It does not publish confidence classification for overlapping cohorts and does not invoke `run_statistical_confidence` for those observations.

**Scope:** Descriptive point estimates only for metrics whose dependency-aware support is not confirmed by code and tests. Inferential output (bootstrap CIs, LOO robustness, confidence states, significance claims) is not produced for overlapping cohorts.

**Source of truth:** Direct inspection of `src/hunter/research_statistical_confidence/` and `tests/test_research_statistical_confidence/` (see `docs/planning/SPEC-076-STATCONF-FINDINGS.md`). Every capability/limitation claim traces to that findings document.

**Capabilities confirmed by code:**

- Per-metric descriptive statistics (mean, median, std dev, MAD, quartiles, sign shares) over per-window metric deltas (`descriptive.py`).
- Deterministic percentile bootstrap CIs for mean and median (`bootstrap.py`).
- Leave-one-window-out sensitivity (`sensitivity.py`).
- Regime-stratified results via caller-provided `regime_label` (`regime.py`).
- Window dependence detection (`WindowDependencePolicy`) flags overlapping evaluation windows (`methodology.py`).

**Limitation confirmed by code:**

- `run_statistical_confidence` does not consume or adjust its statistical methods based on `DependenceStatus`. The core bootstrap and LOO treat all windows as independent samples. No cluster-aware, block-bootstrap, or HAC/Newey-West methods exist.

**Fail-closed rules applied:**

- For overlapping 1d/3d/7d cohorts, only descriptive point estimates (mean, median, sign shares, availability counts) are emitted.
- The descriptive schema does not contain bootstrap intervals, leave-one-out results, confidence_state, significance claims, or null placeholders for unsupported inferential fields.
- For Top-N returns, benchmark-relative returns, and Spearman values, an adapter pre-computes per-cohort descriptive point estimates using the existing descriptive methodology; no inferential pipeline is invoked.
- No new statistical engine is introduced in Phase A.
- Phase A performs no regime labeling, calculation, or stratification; `compute_regime_results` is not called (S5).

### Calibration Gate

- **Eligibility:** At least 30 matured cohorts per horizon (60 recommended).
- **Dependency:** Calibration eligibility depends on matured cohort count, never elapsed calendar time.
- **Phase A boundary:** Phase A never changes weights, parameters, algorithms, execution behavior, snapshots, Feather data, network sources, or scheduling.

### CLI

- **Commands:** `hunter outcome evaluate` and `hunter outcome report`.
- **Style:** Follow the existing from-feather command style (`hunter pairlist from-feather`).
- **Separation:** Evaluation and reporting are separate commands.
- **Selection:** Explicit `--as-of` range or `--all-matured`.
- **Snapshot input:** `--snapshot-dir` (read-only immutable JSON snapshot audit source).
- **Price input:** `--data-dir` (read-only Feather price source).
- **Storage output:** `--store-dir` (append-only evaluation output store).
- **Boundaries:** No network access; no execution behavior; no scheduler mutation.

### Persistence

- **Atomic discipline:** SPEC-074 atomic persistence discipline is reused (temporary file, fsync, atomic rename).
- **Append-only:** Storage is append-only through deterministic immutable artifacts.
- **Existing-file behavior:** Follows snapshot immutability semantics — identical content is a no-op, differing content is rejected.
- **Pair Observation Records:** Written exactly once at terminal resolution.
- **Snapshot Summary Records:** Written per (snapshot_date, ranking_profile, outcome_horizon).
- **Storage layout:** Under `--store-dir/` use `observations/` for Pair Observation Records and `summaries/` for Snapshot Summary Records.
- **Immutability:** Evaluation records are immutable after creation.

## Implementation Decisions

These decisions are closed for Phase A implementation.

| Decision | Resolution |
|---|---|
| Source package | `src/hunter/research_outcome_evaluation/` |
| Test package | `tests/test_research_outcome_evaluation/` |
| CLI dispatch | Separate `outcome_cli_main` dispatch path in `src/hunter/core/cli.py` |
| Modeling | Frozen dataclasses with explicit validators |
| Snapshot schema fields | Must be verified from existing snapshot reader/writer models before implementation; do not infer field names from Feather |
| Storage layout | `--store-dir/observations/` and `--store-dir/summaries/` |
| Spearman scope | Computed over all `OUTCOME_AVAILABLE` observations in the matured cohort, never Top-N-only |
| Benchmark discovery | Via existing SPEC-075 price-source discovery contract |
| Previous snapshot `D_prev` | Immediately preceding available valid immutable snapshot for the same `ranking_profile` ordered by `snapshot_date` |
| `FIRST_SNAPSHOT` | No earlier valid immutable snapshot exists for the same `ranking_profile` (source-based, not evaluation-store-based) |
| Summary field | `days_since_previous_snapshot` |
| Turnover | `1 - \|S_current ∩ S_previous\| / \|S_current\|` |
| Retention | `\|S_current ∩ S_previous\| / \|S_previous\|` |
| Zero denominator | Persist `null` with an explicit reason code |

**Phase 0 inspection findings (verified from code, not inferred):** The immutable snapshot audit artifact is `hunter-pairs-YYYYMMDD-audit.json`, written by `write_snapshot` (`src/hunter/pairlist_export/snapshot.py`) via `audit_record_to_dict` (`src/hunter/pairlist_export/audit.py:118-146`). Verified top-level keys: `as_of_date` (`YYYY-MM-DD`), `ranking_profile` (str, e.g. `V1_RS_OI` / `V2_RS_LIQUIDITY`), `schema_version`, `selected`, `rejected`, `fingerprint`. Verified per-pair keys inside `selected` entries (`_pair_to_dict`, `audit.py:101-115`): `pair` (str), `rank` (int — the rank-at-selection source), `selected` (bool), `rs_score` (Decimal serialized as JSON string, or `null` — the relative-strength-score source), `liquidity_score` (Decimal-as-string, key present only when non-null — the liquidity-score source), `oi_score` (string or null), `reason_codes` (list of str), `fingerprint` (str), and optional `data_quality_pct`. The SPEC-075 Feather price-source discovery contract is verified in `src/hunter/pairlist_export/feather_models.py:83`: filename regex `^(?P<base>[A-Z0-9]+)_USDT_USDT-1h-futures\.feather$`, non-recursive scan of the supplied data directory with symlink/hidden/temp/path-escape rejection, required columns `("date", "close", "volume")` (`feather_models.py:79`), pair form `{base}/USDT:USDT`, and the benchmark file `BTC_USDT_USDT-1h-futures.feather` (base symbol `BTC`).

## Implementation

### Step 1 — Module and CLI placement

- Create `src/hunter/research_outcome_evaluation/`.
- Create `tests/test_research_outcome_evaluation/`.
- Add `outcome` command group to `src/hunter/core/cli.py` as a separate `outcome_cli_main` dispatch path.

### Step 2 — Schemas and validation models

Define frozen dataclass schemas:

- `PairObservationRecord`: snapshot_date, ranking_profile, outcome_horizon, pair, is_benchmark_pair, reference_close, reference_timestamp, terminal_state, realized_return, benchmark_return, benchmark_relative_return, mae_pct, mfe_pct, realized_volatility_pct, rank_at_selection, relative_strength_score, liquidity_score, coverage_ratio, window_start, window_end, fingerprint, metadata.
- `SnapshotSummaryRecord`: snapshot_date, ranking_profile, outcome_horizon, cohort_size, available_count, unavailable_count, days_since_previous_snapshot, turnover, retention, daily_data_availability, top_5_return_pct, top_10_return_pct, top_20_return_pct, top_30_return_pct, spearman_rank_return, spearman_relative_strength_return, spearman_liquidity_return, benchmark_relative_return_pct, mae_pct_mean, mfe_pct_mean, realized_volatility_pct_mean, benchmark_failure_reason, fingerprint, metadata.
- `TerminalState` enum: `OUTCOME_AVAILABLE`, `SNAPSHOT_INVALID`, `OUTCOME_UNAVAILABLE_NO_SOURCE`, `OUTCOME_UNAVAILABLE_GAP`, `OUTCOME_UNAVAILABLE_INVALID_PRICE`, `BENCHMARK_UNAVAILABLE`, `OUTCOME_UNAVAILABLE_DELISTED` (reserved).
- Validation models for coverage thresholds, horizon values, terminal-state transitions, and snapshot field verification.

### Step 3 — Deterministic identifiers and fingerprints

- `snapshot_id` = SHA-256 of (snapshot_date, ranking_profile).
- `observation_id` = SHA-256 of (snapshot_id, pair, outcome_horizon).
- `summary_id` = SHA-256 of (snapshot_date, ranking_profile, outcome_horizon).
- Fingerprints exclude paths, timestamps, hostnames, and insertion order.

### Step 4 — Evaluation ordering

1. Read immutable JSON snapshot audit artifacts from `--snapshot-dir`.
2. Validate snapshot structure; invalid snapshots resolve all members to `SNAPSHOT_INVALID`.
3. Group by (snapshot_date, ranking_profile).
4. For each (snapshot_date, ranking_profile, outcome_horizon) where the horizon has elapsed:
   a. Load required pair and benchmark 1h Feather series from `--data-dir`.
   b. Resolve terminal states for all cohort members in the mandated order.
   c. Compute per-pair metrics.
   d. Compute cohort-level metrics (Top-5/10/20/30 means, Spearman over all `OUTCOME_AVAILABLE` observations, etc.).
   e. Compute turnover, retention, and `days_since_previous_snapshot` from `D_prev`.
   f. Write Pair Observation Records exactly once.
   g. Write Snapshot Summary Record exactly once.

### Step 5 — Terminal-state resolution

Implement the mandated resolution order:

- Before horizon elapsed: transient `PENDING_HORIZON` only.
- After horizon elapsed:
  1. Snapshot validation failure → `SNAPSHOT_INVALID`
  2. Missing Feather price source for pair → `OUTCOME_UNAVAILABLE_NO_SOURCE`
  3. Missing required endpoint candles → `OUTCOME_UNAVAILABLE_GAP`
  4. Endpoint candles fail SPEC-075 validation → `OUTCOME_UNAVAILABLE_INVALID_PRICE`
  5. Coverage below `min_window_coverage` → `OUTCOME_UNAVAILABLE_GAP`
  6. Benchmark validation fails → `BENCHMARK_UNAVAILABLE`
  7. Otherwise → `OUTCOME_AVAILABLE`

No matured cohort member is skipped.

### Step 6 — Metrics computation

- Top-N returns for N ∈ {5, 10, 20, 30} per horizon.
- Spearman(rank, return), Spearman(relative_strength_score, return), Spearman(liquidity_score, return) over all `OUTCOME_AVAILABLE` observations.
- Benchmark-relative returns, MAE, MFE, and realized volatility per horizon.
- Realized volatility: population std dev of valid intra-window 1h log returns, percentage, not annualized.

### Step 7 — Summary generation

- `days_since_previous_snapshot`, turnover, retention computed from `D_prev`.
- `FIRST_SNAPSHOT` when no `D_prev` exists.
- Turnover/retention/availability duplicated identically across horizon summaries for reporting convenience.
- Zero denominator → `null` with explicit reason code.

### Step 8 — CLI integration

- Implement `hunter outcome evaluate` with `--as-of` / `--all-matured`, `--snapshot-dir`, `--data-dir`, `--store-dir`.
- Implement `hunter outcome report` with same selection options plus output formatting.
- Follow existing from-feather command style and argparse patterns.

### Step 9 — Reporting

- Emit deterministic JSON and Markdown artifacts.
- Include safety flags and mandatory research-only notice.
- Reject output under `data/` and `reports/`.

### Step 10 — Tests

- Unit tests for schemas and validation models.
- Unit tests for terminal-state resolution (all seven emitted codes plus reserved `DELISTED`).
- Unit tests for metric computation (Top-5/10/20/30, Spearman over full cohort, MAE/MFE, volatility, benchmark-relative).
- Unit tests for summary generation (turnover, retention, first-snapshot handling, zero denominator).
- Integration tests for end-to-end evaluation with synthetic JSON snapshots and Feather prices.
- Determinism tests (same inputs produce same fingerprints and outputs).
- Immutability tests (existing files are not rewritten; identical content is a no-op).
- Safety tests (no subprocess, no network, no data/reports access).
- CLI smoke tests validating `--snapshot-dir`, `--data-dir`, and `--store-dir` are distinct and read-only/write-only as expected.

### Step 11 — Documentation changes

- Update `docs/MVP_INDEX.md` with SPEC-076 entry.
- Update `docs/technical/TESTING_GUIDE.md` with new test package instructions.
- Update `docs/planning/` with final approved spec (replacing this draft when approved).

## Phase B Outlook

The following are explicitly deferred to a future Phase B and do not exist in Phase A:

- Selected-versus-rejected comparison.
- Full-universe evaluation.
- Explicit delisting detection from an authoritative source.
- Regime-aware evaluation tied to SPEC-078.
- Dependency-aware inference for overlapping cohorts.
- Block bootstrap, cluster bootstrap, HAC/Newey-West, or equivalent dependency-aware methods.
- Confidence classification (`INSUFFICIENT_EVIDENCE`, `UNSTABLE`, `MIXED`, `DIRECTIONALLY_STABLE_*`, `ROBUST_*`) for any observation set until independence or dependency-aware treatment is demonstrated by implementation and tests.
- Explicit historical rebuild tooling.
- Calibration recommendation generation (automatic weight/parameter changes).

## Milestones

- **M1 — Data model and schemas:** `PairObservationRecord`, `SnapshotSummaryRecord`, `TerminalState` enum, and validation models are defined with frozen dataclasses. Validated by schema unit tests.
- **M2 — Outcome resolution engine:** Terminal-state resolution logic handles all mandated codes (`OUTCOME_AVAILABLE`, `SNAPSHOT_INVALID`, `OUTCOME_UNAVAILABLE_NO_SOURCE`, `OUTCOME_UNAVAILABLE_GAP`, `OUTCOME_UNAVAILABLE_INVALID_PRICE`, `BENCHMARK_UNAVAILABLE`, reserved `OUTCOME_UNAVAILABLE_DELISTED`). Validated by resolution unit tests.
- **M3 — Metrics computation:** Top-5/10/20/30 returns, Spearman over all `OUTCOME_AVAILABLE` observations, MAE/MFE, realized volatility, and benchmark-relative returns compute correctly. Validated by metric unit tests.
- **M4 — Summary generation:** Snapshot Summary Records include `days_since_previous_snapshot`, turnover, retention, availability, and horizon-specific aggregates. Validated by summary unit tests.
- **M5 — CLI integration:** `hunter outcome evaluate` and `hunter outcome report` execute with distinct `--snapshot-dir`, `--data-dir`, and `--store-dir`. Validated by CLI smoke tests.
- **M6 — End-to-end integration:** Full pipeline from JSON snapshot + Feather prices to persisted records with deterministic fingerprints. Validated by integration and determinism tests.

## Gathering Results

- **Correctness checks:** All unit tests pass for schemas, resolution, metrics, summary generation, and CLI.
- **Terminal-state coverage:** Every mandated Phase A terminal code (`OUTCOME_AVAILABLE`, `SNAPSHOT_INVALID`, `OUTCOME_UNAVAILABLE_NO_SOURCE`, `OUTCOME_UNAVAILABLE_GAP`, `OUTCOME_UNAVAILABLE_INVALID_PRICE`, `BENCHMARK_UNAVAILABLE`) plus reserved `OUTCOME_UNAVAILABLE_DELISTED` is exercised by tests; no matured cohort member is skipped.
- **Snapshot/price separation:** `--snapshot-dir` contains only JSON snapshot audit artifacts; `--data-dir` contains only Feather price series; `--store-dir` is append-only output.
- **Determinism and immutability checks:** Same inputs produce identical fingerprints and outputs; existing files are never rewritten (identical content is a no-op, differing content is rejected).
- **Data-availability monitoring:** Coverage ratios, gap detection, and `OUTCOME_UNAVAILABLE_NO_SOURCE` are logged and reported per cohort.
- **Matured-cohort counts:** Count of matured cohorts per horizon is tracked and reported.
- **Descriptive metric monitoring:** Mean/median of Top-5/10/20/30 returns, Spearman values, and benchmark-relative returns are monitored across snapshots.
- **Calibration-gate evaluation:** Eligibility status (30+ matured cohorts per horizon) is evaluated and reported; gate status is explicit.
- **Post-production acceptance criteria:**
  - No observation is silently discarded.
  - All terminal states resolve correctly for every matured cohort member.
  - Atomic persistence is verified (no partial writes).
  - Append-only behavior is verified (no rewriting of historical evaluation facts).
  - No network access, subprocess invocation, or scheduler mutation occurs.
  - All safety flags are preserved (`research_only=True`, `human_approval_required=True`).