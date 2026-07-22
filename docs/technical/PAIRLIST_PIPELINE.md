# Pairlist Pipeline (SPEC-074 / MVP-71)

> **Research only.** This pipeline does not authorize execution, production deployment, live trading,
> dry-run trading, automatic execution, strategy selection, universe selection, order placement, signal
> generation, strategy mutation, universe mutation, or position changes. Human review remains required.

Verified against `src/hunter/pairlist_export/*.py`, revalidated after the Stage 2 transactional-publish
remediation. This document supersedes nothing in `docs/research/pairlist_export.md` (which remains accurate
and more implementation-detailed); it restructures the same verified facts around the pipeline stages, plus
the snapshot-before-publish ordering fix (§"Snapshot-Before-Publish Ordering") not yet reflected elsewhere.

## Ranking-Input Contract

```json
{
  "as_of_date": "2026-07-21",
  "universe_total": 412,
  "eligible_pairs": ["BTC/USDT:USDT", "ETH/USDT:USDT"],
  "rs_scores": {"BTC/USDT:USDT": "88.1", "ETH/USDT:USDT": null},
  "oi_scores": {"BTC/USDT:USDT": "70.0", "ETH/USDT:USDT": "65.0"},
  "data_quality": {"BTC/USDT:USDT": "100"}
}
```

`as_of_date`/`universe_total` in the file are optional; the CLI's `--as-of` flag always wins, and
`universe_total` defaults to `len(eligible_pairs)` only when the key is entirely absent (an explicit `0` is
preserved). Full field-by-field contract, types, and invalid-input error messages: `docs/user/INPUT_FORMAT.md`
(verified by direct CLI testing, not just source reading).

## Ranking-Input v2 Schema (SPEC-075)

```json
{
  "schema_version": "hunter-ranking-input-v2",
  "ranking_profile": "V2_RS_LIQUIDITY",
  "as_of_date": "2026-07-21",
  "universe_total": 5,
  "eligible_pairs": ["BTC/USDT:USDT", "ETH/USDT:USDT"],
  "rs_scores": {"BTC/USDT:USDT": "88.1", "ETH/USDT:USDT": "60.0"},
  "liquidity_scores": {"BTC/USDT:USDT": "88.0", "ETH/USDT:USDT": "50.0"},
  "oi_scores": {},
  "data_quality": {"BTC/USDT:USDT": "100", "ETH/USDT:USDT": "90"},
  "source_metadata": {
    "source": "freqtrade-feather",
    "timeframe": "1h",
    "rs_lookback_days": 90,
    "liquidity_lookback_days": 30,
    "oi_available": false,
    "universe_size_at_scoring": 5,
    "universe_fingerprint": "..."
  }
}
```

Profiles: `V1_RS_OI` (schema-less SPEC-074 behavior), `V2_RS_LIQUIDITY` (requires RS, liquidity, data_quality
for every eligible pair; `oi_scores` must be empty, `oi_available=false`), and `V2_RS_OI_LIQUIDITY`
(additionally requires genuine OI for every eligible pair). Profile-field mismatches are rejected with
`PROFILE_FIELD_MISMATCH`; missing required `data_quality` under a v2 profile is rejected with
`PROFILE_EVIDENCE_INCOMPLETE`.

## Ranking Algorithm and Tie-Breaks

`ranking_adapter.rank_pairs` (verified, `ranking_adapter.py:31-155`):

1. For each eligible pair, look up `rs_score`, `oi_score`, `data_quality_pct`. Tag reason codes
   (`REASON_RS_SCORE`, `REASON_OI_LIQUIDITY`, `REASON_DATA_SUFFICIENCY`) for each dimension present; tag
   `REASON_INSUFFICIENT_EVIDENCE` if **both** RS and OI are missing.
2. Sort by compound key `(-rs_score, -oi_score, -data_quality_pct, pair_string)` — missing values substitute
   `Decimal("-Infinity")` so they sort last within their dimension; pair string is the deterministic
   final tie-break (ascending).
3. Assign `rank = index + 1`. Mark `selected=True` for the top `publish_candidates` (default 30) pairs that
   are **not** `INSUFFICIENT_EVIDENCE`.
4. Compute a per-pair fingerprint (`fingerprint.compute_pair_fingerprint`) over `{pair, rank, rs_score,
   oi_score, data_quality_pct, reason_codes}`.
5. **If zero candidates have sufficient evidence** (every pair missing both RS and OI), `rank_pairs` raises
   `PairlistRankingError` directly — this happens *before* the publish gate runs at all, and is a distinct
   failure path from gate rejection (see below).

## Thresholds (SPEC-074 defaults)

```text
min_pairs = 5
target_final_pairs = 20
publish_candidates = 30
max_pairs = 50
refresh_period = 3600
```

`PairlistRankingConfig.__post_init__` enforces `min_pairs >= 1`, `max_pairs >= min_pairs`,
`min_pairs <= publish_candidates <= max_pairs`, `refresh_period >= 60` — so a config that could produce
`ABOVE_MAX_PAIRS` through normal ranking (`publish_candidates > max_pairs`) cannot even be constructed. In
practice `ABOVE_MAX_PAIRS` is reachable only via `validate_published_pairlist` against an externally supplied
(e.g. hand-edited or third-party) pairlist JSON — verified: `hunter pairlist validate` against a synthetic
60-pair native JSON returned `valid: False` / `reason_codes: ABOVE_MAX_PAIRS` (exit 1).

## Selection and Rejection Reason Codes

Full closed set (`models.py::PAIRLIST_REASON_CODES`):

| Reason code | Meaning | Where raised |
|---|---|---|
| `RS_SCORE` | Pair has a relative-strength score | ranking (positive) |
| `OI_LIQUIDITY` | Pair has an open-interest score | ranking (positive) |
| `DATA_SUFFICIENCY` | Pair has a data-quality score | ranking (positive) |
| `INELIGIBLE_STABLECOIN` / `INELIGIBLE_LEVERAGED` / `INELIGIBLE_BENCHMARK` / `INELIGIBLE_PAIR` / `UNKNOWN_PAIR` | Reserved eligibility-exclusion codes | defined in `models.py`; **not currently raised** by `ranking_adapter.py` or `validator.py` — no code path in this version sets them (verified by grep; see Findings, Informational) |
| `INVALID_PAIR_FORMAT` | Selected pair fails `^[A-Z0-9]{2,20}/USDT:USDT$` | gate, validator |
| `DUPLICATE_PAIR` | Selected pair appears more than once | gate, validator |
| `INSUFFICIENT_EVIDENCE` | A *selected* pair still lacks both RS and OI (gate's own independent re-check — does not merely trust the ranking adapter's `selected` flag) | gate |
| `BELOW_MIN_PAIRS` | Selected count `< min_pairs` | gate, validator (if config supplied) |
| `ABOVE_MAX_PAIRS` | Selected count `> max_pairs` | gate, validator (if config supplied) |
| `EMPTY_UNIVERSE` | Zero pairs selected | gate, validator |
| `INVALID_OUTPUT_PATH` | Reserved for output-path validation | defined but not raised as a *reason code* — the actual forbidden-path check raises `PairlistPublishError` with a plain message, not this code |
| `WRITE_FAILED` | Reserved for write-failure signaling | defined but not raised as a reason code — write failures raise `PairlistPublishError` directly |
| `VALIDATION_FAILED` | Schema/type validation failure in `validate_published_pairlist` | validator |

**All gate checks accumulate** — `run_publish_gate` never short-circuits, so a single rejected publish can
report multiple simultaneous reason codes (e.g. `BELOW_MIN_PAIRS, INVALID_PAIR_FORMAT` together).

## Publish Gate

`validator.run_publish_gate` (verified, `validator.py:52-142`) is the single fail-closed checkpoint between
ranking and I/O. It performs no I/O itself. On any triggered reason code, `allow_publish=False` and
`pairlist_output=None` — **no write is attempted**, so a gate rejection never touches the previously
published files. Only when every check passes does it build the `AuditRecord`, compute fingerprints, and
return a `PairlistOutput` for the caller to publish.

## Atomic Write Sequence

`publisher.publish_pairlist` (verified, `publisher.py:87-151`):

1. `reject_forbidden_output_dir(output_dir)` — resolve and reject if under repo `data/`/`reports/`.
2. If live `hunter-pairs.json`/`hunter-pairs-audit.json` already exist, copy their current content to
   `*.previous-good` (via `atomic_write_text`, so the backup itself is crash-safe).
3. Write the new `hunter-pairs.json` and `hunter-pairs-audit.json` via `atomic_write_text`: tempfile in the
   same directory → `write` → `flush` → `os.fsync(fd)` → `os.replace()` → `os.fsync()` the parent directory.
4. **On any exception during step 3**, restore both files from `*.previous-good` (or delete them if this was
   the first-ever publish), then re-raise as `PairlistPublishError`.

This makes `publish_pairlist` itself fail-closed and previous-good-preserving **in isolation**.

## Snapshot-Before-Publish Ordering (transactional consistency)

`cli.py::_build_and_publish` validates/commits the snapshot **before** the live publish:

```python
snapshot_paths = write_snapshot(output, snapshot_dir)   # step A — validated/committed first
pairlist_path, audit_path = publish_pairlist(output, output_dir)  # step B — only runs if A succeeded
```

`write_snapshot` does not depend on `publish_pairlist` having run, and is a no-op for an identical
same-date rerun — so this ordering means a same-date-different-content snapshot conflict is rejected with
exit `1` **before either the live `hunter-pairs.json` or `hunter-pairs-audit.json` is touched**, exactly
like any other publish-gate rejection. `*.previous-good` is never created for a conflict rejection, which is
itself proof `publish_pairlist` was never invoked. Verified live (reproduced the conflict scenario twice,
before and after the fix) and covered by
`tests/test_pairlist_export/test_transactional_publish.py` (snapshot-conflict-before-publish, live
pairlist/audit unchanged, no orphan temp files, identical-rerun idempotency, and a partial-failure-rollback
case exercising `publish_pairlist`'s own previous-good restore after a conflict-free snapshot succeeds).

One accepted trade-off of this ordering: if the snapshot step succeeds but the live publish step then fails
for an unrelated reason (e.g. a filesystem error), a dated snapshot can exist for a date whose live publish
never completed. The live-artifact consistency guarantee this fix protects (`publisher.py`'s module
docstring: "a failed publish never leaves a partial or inconsistent artifact live") holds for the live
pairlist/audit in all failure modes; only the newer, narrower snapshot-ahead-of-live edge case remains, and
it is far less severe than the original defect (an unpublished snapshot record, not a corrupted live
artifact).

## Audit Contract

`audit.build_audit_record` / `audit_record_to_dict` (verified, `audit.py`) produce a JSON object with
`as_of_date`, `universe_total`, `eligible_count`, `selected_count`, `rejected_count`, `selected[]`,
`rejected[]` (each a `{pair, rank, selected, rs_score, oi_score, reason_codes[], fingerprint}` record —
scores serialized as strings, never floats), `reason_code_summary` (a `Counter` dict), `fingerprint`, and a
fixed `research_notice` string. This is a **separate JSON file** (`hunter-pairs-audit.json`) from the native
pairlist JSON, by design (module docstring: "kept as a JSON contract fully separate from the native
RemotePairList JSON payload").

**SPEC-075 v2 audit fields** (present with v1-safe defaults for schema-less inputs):
`schema_version` (`hunter-ranking-input-v1` or `-v2`), `ranking_profile`,
`active_score_dimensions` (exact ordered tuple per profile: `("rs", "oi")` for `V1_RS_OI`;
`("rs", "liquidity", "data_quality")` for `V2_RS_LIQUIDITY`;
`("rs", "oi", "liquidity", "data_quality")` for `V2_RS_OI_LIQUIDITY`),
`ignored_score_dimensions` (always `()`), `universe_size_at_scoring`, `universe_fingerprint`,
`oi_available`, `source_metadata` (source, timeframe, lookbacks, fingerprint), and `per_pair_evidence`.
Selected v2 pairs additionally serialize `liquidity_score` and `data_quality_pct` when non-`None`.

## Static Snapshots

`snapshot.write_snapshot` writes `hunter-pairs-YYYYMMDD.json` / `hunter-pairs-YYYYMMDD-audit.json` per
successful publish. Re-running with **identical** content for an already-snapshotted date is a no-op success
(idempotent). Re-running with **different** content raises `PairlistPublishError` (see the gap above for the
interaction with `publish_pairlist`). Snapshot destination is also checked by
`reject_forbidden_output_dir`.

## RemotePairList Contract

Live pairlist JSON (`hunter-pairs.json`):

```json
{"pairs": ["BTC/USDT:USDT", "ETH/USDT:USDT", "..."], "refresh_period": 3600}
```

Verified minimal, exactly `{pairs: list[str], refresh_period: int}` — no extra fields, no metadata, no
timestamps. `validate_published_pairlist` checks this exact shape plus pair-format/uniqueness/threshold rules.

## Native Freqtrade Filters (applied after RemotePairList, outside Hunter)

`deployment_profiles.py`'s emitted config chains `RemotePairList` → `AgeFilter(min_days_listed=30)` →
`DelistFilter` → `SpreadFilter(max_spread_ratio=0.005)`, plus a static
`pair_blacklist: [".*(UP|DOWN|BULL|BEAR)/USDT:USDT"]`. These run natively inside Freqtrade — Hunter neither
implements nor duplicates this filtering logic (verified: zero `class.*PairList` matches anywhere in `src/`).

## Backtest Snapshot Policy

Per `docs/research/pairlist_export.md` and confirmed by `snapshot.py`'s immutability behavior: historical
backtests must replay the preserved dated snapshot for the relevant date, not retrospectively rerun the
current dynamic ranking/filters. This is enforced structurally (snapshots cannot silently change), not by a
separate backtest-time check.

## Manual Verification (commands actually run during this validation pass)

All against a synthetic fixture in a scratch directory outside `data/`/`reports/` — see the validation
report's Manual End-to-End Smoke Test section for full output. Summary of verified behaviors:

| Scenario | Command | Result |
|---|---|---|
| Golden path | `coins rank` → `pairlist build` → `validate` → `explain` | All exit 0; audit explains selection reasons |
| Idempotent rerun | `pairlist build` twice, same input/date | Identical output, identical fingerprint, snapshot no-op |
| Below minimum | 2 eligible pairs, `min_pairs=5` | `BELOW_MIN_PAIRS`, exit 1, no write |
| Duplicate pair | Same pair listed twice | `DUPLICATE_PAIR`, exit 1, no write |
| Invalid pair format | `"BTCUSDT"` (no `/USDT:USDT` suffix) | `INVALID_PAIR_FORMAT`, exit 1, no write |
| Insufficient evidence | Empty `rs_scores`/`oi_scores` | `PairlistRankingError` raised pre-gate, exit 1, no write |
| Excessive count | 60-pair externally supplied JSON via `pairlist validate` | `ABOVE_MAX_PAIRS`, exit 1 |
| Forbidden output dir | `--output-dir <repo>/data/pairlists` | Rejected before any write, exit 1 |
| Snapshot conflict | Same `as_of_date`, different content, second run | `PairlistPublishError` before any live write; live pairlist/audit confirmed byte-identical to before the run, no `.previous-good` created |
