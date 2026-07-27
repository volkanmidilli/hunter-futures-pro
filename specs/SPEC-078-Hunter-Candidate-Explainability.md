# SPEC-078 — Hunter Candidate Explainability

## Background

Hunter (SPEC-074/075) ranks eligible pairs deterministically, applies a fail-closed publish gate, and
publishes the top `target_final_pairs` pairs as a native Freqtrade `RemotePairList`. The published
audit (`hunter-pairs-audit.json`) records the selected/rejected sets, but operators have no direct
way to ask: **why was pair X selected or not selected by the latest run?**

SPEC-078 adds a candidate explainability layer: every selection run records, per candidate pair, the
real stage decisions of the pipeline, and a new `hunter explain <SYMBOL>` CLI answers from those
recorded artifacts. The command never recomputes selection decisions and never invents criteria —
every stage status, metric, threshold, and reason code is taken from the pipeline component that
owns that criterion.

## Requirements

### Must

- Provide `hunter explain BTC`, `hunter explain BTC/USDT:USDT`, `hunter explain ETH --json`.
- Normalize short symbols to the Binance USDT perpetual Freqtrade form (`BTC` → `BTC/USDT:USDT`);
  reject invalid or unsafe symbols fail-closed (exit 2).
- Record one immutable `CandidateExplanationRecord` per ranked candidate per run, with ordered
  `CandidateStageDecision` entries (stage identity, execution order, PASS/FAIL/SKIP/UNKNOWN, observed
  metrics, thresholds actually applied, reason codes).
- Record a run manifest per run and maintain an atomic `latest.json` pointer that only a successful
  (gate-passed, published) run advances. A failed or incomplete run must never replace the latest
  successful run.
- Write all artifacts atomically (tempfile + flush + fsync + `os.replace`), outside Git-tracked
  source, under `explainability/runs/<run_id>/{manifest.json,candidates/<PAIR>.json}`.
- Fail closed on missing information with explicit states: `NO_SUCCESSFUL_RUN`, `NOT_IN_UNIVERSE`,
  `NOT_RECORDED`, `ARTIFACT_INVALID`. Never infer missing values; render them as `UNKNOWN` /
  `NOT_RECORDED`.
- Reuse the pipeline's existing reason codes (`INSUFFICIENT_EVIDENCE`, `PROFILE_EVIDENCE_INCOMPLETE`,
  gate codes, ...) wherever they exist; introduce new codes only for states the pipeline has no code
  for (`OUTSIDE_TARGET_FINAL_PAIRS`, `PUBLISH_BLOCKED`, and the lookup states above).
- `--json` must emit the canonical structured record (inside a small lookup envelope) — the same
  model the human output is rendered from — suitable for a future read-only dashboard/API.
- Not change candidate eligibility, scores, ranking, pair ordering, selected pairs, published pairs,
  existing output artifacts, or research behavior. Recording failures are warn-only and never change
  pipeline exit codes.

### Must not

- Recompute or re-derive selection decisions at explain time.
- Maintain a second centralized list of Hunter criteria.
- Inspect, modify, migrate, or depend on the repository `data/` or `reports/` trees.
- Implement dashboards, web APIs, `--run-id`, `--date`, historical comparisons, score recomputation,
  or new ranking criteria (MVP scope is latest-successful-run lookup only).

## Design

### Where each real pipeline criterion is recorded

| Stage | Owning component | What is recorded |
|---|---|---|
| `universe` | ranking input consumed by `rank_pairs`/`rank_pairs_v2` | `universe_total`, `eligible_count` |
| `data_quality` | ranking input data-quality map (+ `RankedPair.data_quality_pct` under v2) | observed `data_quality_pct`; `required` per profile (`PROFILE_ACTIVE_DIMENSIONS`); real codes `DATA_SUFFICIENCY` / `PROFILE_EVIDENCE_INCOMPLETE` |
| `liquidity` | `rank_pairs` (OI, v1) / `rank_pairs_v2` (OI/liquidity per profile) | observed `oi_score`/`liquidity_score`; required-ness per profile; real codes `OI_LIQUIDITY` / `LIQUIDITY_SCORE` |
| `relative_strength` | `rank_pairs`/`rank_pairs_v2` RS dimension | observed `rs_score`; required-ness per profile; real code `RS_SCORE` |
| `ranking` | `ranking_adapter` selection decision + `PairlistRankingConfig.target_final_pairs` | `rank`, `selected`, cutoff; real codes `INSUFFICIENT_EVIDENCE` / `PROFILE_EVIDENCE_INCOMPLETE` or new `OUTSIDE_TARGET_FINAL_PAIRS` |
| `publish` | `run_publish_gate`/`run_publish_gate_v2` + `publish_pairlist` outcome | PASS for published selected pairs; SKIP for non-selected; FAIL with `PUBLISH_BLOCKED` + the gate's real rejection codes |

### Components (`src/hunter/explainability/`)

- `models.py` — frozen `CandidateStageDecision`, `CandidateExplanationRecord`,
  `ExplainabilityRunManifest` (MappingProxyType coercion, deterministic `to_dict`/`from_dict`).
- `recorder.py` — `PairlistRunObservation` (the real pipeline outputs) → manifest + records. Pure,
  no I/O, deterministic run id (`<as_of>__<profile>__<digest12>` over ranked-pair fingerprints).
- `storage.py` — atomic writes reusing `atomic_write_text`/`reject_forbidden_output_dir`; snapshot
  immutability semantics (`completed_at`-insensitive comparison); `latest.json` pointer discipline.
- `service.py` — symbol normalization and fail-closed latest-run lookup.
- `formatter.py` — human rendering (UNKNOWN/NOT_RECORDED for missing values) and JSON envelope.
- `cli.py` — `hunter explain <SYMBOL> [--json] [--explainability-dir <dir>]`; exit codes
  0 (explained, incl. NOT_IN_UNIVERSE) / 1 (NO_SUCCESSFUL_RUN, NOT_RECORDED, ARTIFACT_INVALID) /
  2 (invalid or unsafe symbol, usage).

### Integration points

- `hunter pairlist build` / `hunter daily-pairlist` (`_build_and_publish`) and
  `hunter pairlist from-feather` record a run after the gate (rejected runs: artifacts persisted,
  pointer untouched) and after successful publish (pointer advanced). Recording is wrapped
  warn-only; it cannot change pipeline behavior.
- `hunter.core.cli` routes the `explain` token to the explainability CLI.
- Artifact root resolution: `--explainability-dir` > `HUNTER_EXPLAINABILITY_DIR` >
  `<repo>/explainability/` (Git-ignored).

### Known limitations

- The current pipeline has no single composite per-pair score (ranking is a deterministic compound
  sort key), so `final_score` is always `null` and rendered `UNKNOWN`; `score_components` carries the
  real per-dimension scores.
- Only the latest successful run is queryable (MVP). Rejected runs persist artifacts but are not
  reachable via the CLI pointer.
- The pipeline has no distinct "safety filter" stage beyond the publish gate; `FAILED_LIQUIDITY` /
  `FAILED_SAFETY_FILTER` have no owning component today and are therefore not emitted — the real
  evidence codes are used instead.
- `hunter coins rank` (rank-only, no publish) does not record explainability artifacts in the MVP.

## Provenance and legacy runs (2026-07-27 amendment)

Pre-SPEC-078 production runs have no runtime explainability records. To make them explainable
without ever rerunning ranking or inventing criteria:

- `hunter explain import --pairlist <hunter-pairs.json> [--audit <hunter-pairs-audit.json>]
  [--notes "..."]` migrates a *real* published pairlist/audit into the store. Every value comes from
  the source artifacts; anything they did not record (data-quality values, the exact
  `target_final_pairs` threshold) stays UNKNOWN and is stated in `reconstruction_notes`.
- Migrated runs and records carry `provenance_type=RECONSTRUCTED`, `source_run_id`,
  `source_artifact_paths`, and `reconstruction_notes`. Runtime-recorded runs carry
  `provenance_type=ORIGINAL`. Artifacts written before provenance tracking deserialize as
  RECONSTRUCTED (fail-closed — never an implied original).
- Without an audit artifact the run imports with `decision_records_complete=False`; every lookup
  fails closed with `LEGACY_RUN_INCOMPLETE` instead of guessing universe membership.
- Pointer policy: the default resolution always prefers the latest ORIGINAL successful run — a
  RECONSTRUCTED import never replaces an ORIGINAL pointer. Among reconstructed runs, only a strictly
  newer production publish (by `as_of_date`) advances the pointer, so a reconstructed historical run
  is never silently preferred over a newer production publish. Any future instrumented pipeline run
  automatically supersedes all imports.
- Human and JSON output display `PROVENANCE` / `provenance_type` so reconstructed records can never
  be mistaken for original production records.

## Acceptance criteria

1. `hunter explain BTC` after a successful build renders the real run id, selection/publish status,
   rank, target, final reason, and ordered stage decisions — no guessed fields.
2. `hunter explain ETH` reveals the true outcome (not in universe / insufficient evidence / outside
   cutoff / publish blocked) exactly as the pipeline decided it.
3. `hunter explain BTC --json` emits the canonical record inside the lookup envelope.
4. A gate-rejected run never replaces the latest-successful-run pointer.
5. All writes atomic; corrupt artifacts resolve to `ARTIFACT_INVALID`.
6. Published pairlist, audit, snapshots, ranking, and exit codes are byte-identical with
   explainability enabled or disabled (regression-tested).
