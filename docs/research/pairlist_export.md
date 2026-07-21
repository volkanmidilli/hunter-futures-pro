# Daily Coin Universe Ranking and Native Freqtrade RemotePairList Export

> **Research only.** This pipeline does not authorize execution, production deployment, live trading, dry-run trading, automatic execution, strategy selection, universe selection, order placement, signal generation, strategy mutation, universe mutation, or position changes. Human review remains required.

## Scope

SPEC-074 (MVP-71, `src/hunter/pairlist_export/`) is the daily operational bridge between Hunter's research outputs and Freqtrade's native `RemotePairList`. Hunter ranks the eligible Binance USDT-M futures universe, gates the shortlist, and publishes it as a `file:///`-consumable JSON artifact plus a separate audit/explain artifact. Freqtrade remains solely responsible for strategy execution, orders, positions, leverage, and entry/exit logic; Hunter is stateless regarding Freqtrade positions and trades.

Hunter does **not**: implement a custom PairList plugin, run an HTTP server, run an hourly safety job, generate trading signals, place orders, manage positions, decide leverage, or duplicate Freqtrade's own inactive-market/delist/spread/age filters. Those are delegated to native Freqtrade filters (`AgeFilter`, `DelistFilter`, `SpreadFilter`, ...) applied after `RemotePairList`.

## Package layout

```text
src/hunter/pairlist_export/
├── models.py               # frozen dataclasses, reason-code catalog, safety flags
├── fingerprint.py           # deterministic, wall-clock-free SHA-256 fingerprinting
├── ranking_adapter.py       # deterministic tie-break ranking over score maps (v1 + v2 profiles)
├── ranking_input_v2.py      # SPEC-075 v2 schema, profile enum, profile-field-mismatch validation
├── feather_models.py        # SPEC-075 Feather reason codes, discovery/evidence dataclasses
├── feather_adapter.py       # SPEC-075 read-only Feather discovery, validation, RS/liquidity/data-quality
├── audit.py                 # audit/explain record builder + renderers (v1 + v2 fields)
├── validator.py             # publish gate + published-artifact validator (v1 + v2)
├── publisher.py             # atomic writer, previous-good preservation, repo-tree guard
├── snapshot.py               # dated, immutable static snapshots
├── deployment_profiles.py   # native-host and container file:/// Freqtrade profiles
├── cli.py                   # universe / coins / pairlist / daily-pairlist commands
└── __init__.py               # public API
```

Dependency direction is a DAG: `models`/`fingerprint` are leaves; `ranking_input_v2` depends on both; `audit` depends on `models`/`fingerprint`/`ranking_input_v2`; `ranking_adapter`/`validator` depend on `audit`+`ranking_input_v2`; `feather_adapter` depends on `feather_models`/`ranking_input_v2`/the existing `relative_strength` engine; `publisher`/`snapshot` are unchanged; `cli` depends on all of the above. No circular imports.

## Reuse boundary

`ranking_adapter.rank_pairs` consumes pre-computed `rs_scores` / `oi_scores` / `data_quality` maps (`dict[str, Decimal | None]`) rather than importing `relative_strength`/`open_interest` engine internals directly. This is a deliberate seam: it reuses those engines' *output* without duplicating their scoring algorithms, and keeps `pairlist_export` decoupled from their internal report shapes. The CLI's ranking-input JSON (below) is the concrete contract at that seam.

**SPEC-075 (`hunter pairlist feather-input` / `from-feather`) closes this gap for one concrete source**: local Freqtrade `BASE_USDT_USDT-1h-futures.feather` files. It reuses `relative_strength.build_relative_strength_report` verbatim (no algorithm reimplementation) by resampling completed hourly candles into daily closes, and adds a new `liquidity` dimension (`close × volume → daily total → 30-day average → log1p → cross-sectional average-rank percentile`) plus a `data_quality` dimension based on expected-1h-slot coverage. Open Interest is still not produced from any local source — `oi_scores` is always `{}` under the resulting `V2_RS_LIQUIDITY` profile (volume/liquidity is never represented as open interest; genuine OI would require a separate, not-yet-built adapter, per SPEC-075's "Could"/"Won't" scope). See `docs/planning/SPEC-075-Freqtrade-Feather-Ranking-Input-Automation.md` for the full spec.

## Ranking-input JSON contract

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

`as_of_date`/`universe_total` in the file are optional; `--as-of` always wins on the CLI, and `universe_total` defaults to `len(eligible_pairs)` only when the key is entirely absent (an explicit `0` is preserved, not silently overridden).

## Ranking tie-break order

1. Primary research rank (RS composite score, descending)
2. Liquidity rank (OI score, descending)
3. Data sufficiency (data-quality percentage, descending)
4. Pair string ascending (deterministic fallback)

Missing scores sort last within their dimension. A pair missing **both** RS and OI is marked `INSUFFICIENT_EVIDENCE` and excluded from selection regardless of rank position. No wall-clock value enters any ranking or audit fingerprint.

## Publish-gate matrix

The gate (`validator.run_publish_gate`) is the single fail-closed checkpoint before any write. All checks are evaluated independently (no short-circuiting), and every reason code triggered is returned:

| Condition | Reason code | Effect |
|---|---|---|
| No pair selected | `EMPTY_UNIVERSE` | reject |
| A selected pair still carries `INSUFFICIENT_EVIDENCE` | `INSUFFICIENT_EVIDENCE` | reject (gate re-validates independently of the ranking adapter's own `selected` flag) |
| A selected pair fails `BASE/USDT:USDT` shape | `INVALID_PAIR_FORMAT` | reject |
| Duplicate pair in the selected set | `DUPLICATE_PAIR` | reject |
| Selected count `< min_pairs` (default 5) | `BELOW_MIN_PAIRS` | reject |
| Selected count `> max_pairs` (default 50) | `ABOVE_MAX_PAIRS` | reject |
| All checks pass | `OK` | `PairlistOutput` built (pairs, refresh_period, audit, fingerprints); publish proceeds |

On rejection, `allow_publish=False` and no write is attempted — the previously published pairlist/audit pair is left completely untouched (rejection happens before the writer is ever invoked).

`validate_published_pairlist` runs the same schema/format/uniqueness (+ threshold, if a config is supplied) checks against an already-written `pairlist.json`, for the `hunter pairlist validate` command and for CI/acceptance use.

## Defaults

```text
min_pairs = 5
target_final_pairs = 20
publish_candidates = 30
max_pairs = 50
refresh_period = 3600
```

Hunter publishes up to `publish_candidates` (default 30) ranked pairs; Freqtrade's native filters are expected to reduce the final whitelist to roughly `target_final_pairs` (default 20), and may legitimately produce fewer. Hunter never pads the list with lower-quality pairs to force an exact count.

## Atomic publish and previous-good preservation

`publisher.publish_pairlist` writes `hunter-pairs.json` and `hunter-pairs-audit.json` via tempfile-in-same-directory → flush → `os.fsync` → `os.replace` → parent-directory `fsync`. Before overwriting, the current live files (if any) are copied to `*.previous-good`. If either live write fails, both files are restored from `*.previous-good` (or removed entirely, if this was the first-ever publish) so the pairlist/audit pair is never left inconsistent — publish is fail-closed. A failure during the previous-good backup step itself is also wrapped and raised as `PairlistPublishError`, never a raw exception.

`publisher.reject_forbidden_output_dir` resolves the target directory (following symlinks) and rejects any path equal to or nested under this repository's `data/` or `reports/` trees, for every publish and snapshot destination.

## Dated static snapshots

Every successful publish also writes an immutable pair: `hunter-pairs-YYYYMMDD.json` and `hunter-pairs-YYYYMMDD-audit.json`. Re-running the same as-of-date with identical content is a no-op success (idempotent). Re-running with *different* content for an already-snapshotted date raises `PairlistPublishError` rather than silently overwriting a historical artifact that backtests may depend on. Historical backtests must replay these static snapshots, not retrospectively rerun dynamic filters.

## CLI reference

```text
hunter universe refresh --input <pairs.json> --output <path>
hunter coins rank --as-of YYYY-MM-DD --input <ranking_input.json> --output <path>
hunter pairlist build --as-of YYYY-MM-DD --input <ranking_input.json> --output-dir <dir> [--snapshot-dir <dir>]
hunter pairlist validate <pairlist.json>
hunter pairlist explain <audit.json>
hunter pairlist deployment-profile --target native|container [--output <path>]
hunter pairlist feather-input --data-dir <dir> --output <path> --as-of YYYY-MM-DD
hunter pairlist from-feather --data-dir <dir> --output-dir <dir> [--snapshot-dir <dir>] --as-of YYYY-MM-DD
hunter daily-pairlist --as-of YYYY-MM-DD --input <ranking_input.json> --output-dir <dir> [--snapshot-dir <dir>]
```

All commands are local-file-only: no network calls, no Binance/exchange access, no Freqtrade process interaction. `universe refresh` canonicalizes (sorts, dedupes, format-checks) a locally supplied pairs file; it does not fetch data from Binance. `hunter.core.cli` routes the `universe`/`coins`/`pairlist`/`daily-pairlist` top-level tokens to this package's CLI; every other command still goes to the pre-existing `reporting_cli`.

## SPEC-075: ranking-input v2 and ranking profiles

`feather-input`/`from-feather` produce (and `rank_pairs_v2`/`run_publish_gate_v2` consume) a v2 ranking-input artifact:

```json
{
  "schema_version": "hunter-ranking-input-v2",
  "ranking_profile": "V2_RS_LIQUIDITY",
  "as_of_date": "2026-07-21",
  "universe_total": 28,
  "eligible_pairs": ["BTC/USDT:USDT"],
  "rs_scores": {"BTC/USDT:USDT": "92.1"},
  "liquidity_scores": {"BTC/USDT:USDT": "88.0"},
  "oi_scores": {},
  "data_quality": {"BTC/USDT:USDT": "100"},
  "source_metadata": {
    "source": "freqtrade-feather", "timeframe": "1h", "rs_lookback_days": 90,
    "liquidity_lookback_days": 30, "oi_available": false,
    "universe_size_at_scoring": 28, "universe_fingerprint": "..."
  }
}
```

A **missing `schema_version`** in any hand-authored or externally supplied ranking-input file always resolves to `V1_RS_OI` — every existing SPEC-074 behavior, test, and tie-break rule is completely unaffected by anything below.

Three ranking profiles are supported (`hunter.pairlist_export.ranking_input_v2.RankingProfile`), each with its own tie-break order and required-evidence rule — one profile applies to the whole artifact and is never switched or downgraded per pair:

| Profile | Tie-break order (after `rs` desc) | Required for every eligible pair |
|---|---|---|
| `V1_RS_OI` (default when `schema_version` is absent) | `oi` desc → `data_quality` desc → `pair` asc | `rs` **or** `oi` (either alone is sufficient) |
| `V2_RS_LIQUIDITY` (feather-adapter default) | `liquidity` desc → `data_quality` desc → `pair` asc | `rs`, `liquidity`, and `data_quality` (all required) |
| `V2_RS_OI_LIQUIDITY` | `oi` desc → `liquidity` desc → `data_quality` desc → `pair` asc | `rs`, genuine `oi`, `liquidity`, and `data_quality` (all required) |

Profile-field rules (`ranking_input_v2.validate_profile_fields`, called by both `rank_pairs_v2` and `RankingProfile`-aware CLI paths) reject a mismatched payload with `PROFILE_FIELD_MISMATCH` instead of silently ignoring the offending field:

- `V2_RS_LIQUIDITY` requires `oi_scores == {}` and `oi_available == false`.
- `oi_available == true` requires at least one populated `oi_scores` entry, and vice versa.
- `V2_RS_OI_LIQUIDITY` requires a genuine (non-null) `oi_scores` entry for every eligible pair.
- Both v2 profiles require a non-null `liquidity_scores`/`rs_scores` entry for every eligible pair.
- `V1_RS_OI` rejects a populated `liquidity_scores` map (v1 payloads have no liquidity dimension at all).

Volume is never represented as open interest: `oi_scores` under `V2_RS_LIQUIDITY` is always `{}`, and the feather adapter never computes or writes to it.

### Feather adapter (`feather_adapter.build_ranking_input_v2_from_feather`)

Reads only local files matching `^(?P<base>[A-Z0-9]+)_USDT_USDT-1h-futures\.feather$` under an operator-supplied `--data-dir` (non-recursive scan). Spot, mark-price, funding-rate, other-timeframe, hidden/temp, symlinked, and malformed files are excluded deterministically (`FILENAME_NOT_MATCHED`, `SYMLINK_REJECTED`, `HIDDEN_OR_TEMP_FILE`, `PATH_ESCAPE_REJECTED`); a file sharing a base symbol or underlying inode with an already-included file is excluded as `DUPLICATE_PAIR_SOURCE`. Only `date`, `close`, `volume` are read; timestamps are normalized to UTC; duplicate/out-of-order timestamps, future candles, non-finite/`<=0` close, and negative volume reject the whole pair's series (`DUPLICATE_CANDLES`, `OUT_OF_ORDER_CANDLES`, `FUTURE_CANDLE`, `INVALID_CLOSE`, `INVALID_VOLUME`). Only completed candles in `[as_of_date - 90d, as_of_date)` are used; a pair with zero candles in that window is `INSUFFICIENT_LOOKBACK`-excluded before ever reaching relative strength.

For eligible pairs, completed hourly candles are resampled to one close per UTC day (the only bridge into `relative_strength.build_relative_strength_report`, called unmodified — the RS engine's own `lookback_days` are row-offsets, so daily-close rows make its unmodified 7/14/30-"day" windows behave correctly against 90 days of hourly source data). `data_quality` is the percentage of the 2160 expected hourly slots (90 × 24) actually present; `liquidity_scores` is the cross-sectional average-rank percentile (ties get identical percentiles) of `log1p(mean(daily close × volume))` over the last 30 window days. A pair is `eligible` only if `rs`, `liquidity`, and `data_quality` are all present — matching `V2_RS_LIQUIDITY`'s required-evidence rule above.

`universe_fingerprint` (in `source_metadata`, and echoed into the v2 audit record) is a deterministic SHA-256 over the sorted eligible-pair list only — no timestamp, PID, hostname, or temp path enters it, so identical `--as-of` + identical Feather content always produce byte-identical `feather-input` output.

## Native and container `file:///` deployment profiles

`deployment_profiles.NATIVE_HOST_PROFILE` and `CONTAINER_PROFILE` (also reachable via `hunter pairlist deployment-profile --target native|container`) are ready-to-merge Freqtrade config fragments:

```json
{
  "exchange": {"pair_blacklist": [".*(UP|DOWN|BULL|BEAR)/USDT:USDT"]},
  "pairlists": [
    {
      "method": "RemotePairList",
      "mode": "whitelist",
      "pairlist_url": "file:///home/freqtrade/user_data/pairlists/hunter-pairs.json",
      "number_assets": 30,
      "refresh_period": 3600,
      "keep_pairlist_on_failure": true,
      "save_to_file": "user_data/pairlists/hunter-pairs-snapshot.json"
    },
    {"method": "AgeFilter", "min_days_listed": 30},
    {"method": "DelistFilter"},
    {"method": "SpreadFilter", "max_spread_ratio": 0.005}
  ]
}
```

The native-host and container profiles are identical except for `pairlist_url`/mount-path convention (`file:///home/freqtrade/user_data/pairlists/hunter-pairs.json` vs. `file:///freqtrade/user_data/pairlists/hunter-pairs.json`), matching how Freqtrade is expected to be deployed relative to Hunter's publish location. Both use only native Freqtrade `pairlists` methods — no custom plugin, no HTTP serving.

`freqtrade test-pairlist` acceptance against a real Freqtrade installation is a deployment-profile/CI/release check, not a daily-publish dependency (daily publishing must not depend on a running Freqtrade installation).

## Refresh cadence

- Hunter ranking: intended to run daily (e.g. 08:05 UTC via an external scheduler — Hunter itself has no scheduler).
- Freqtrade file refresh: hourly, via `refresh_period=3600` in the `RemotePairList` config.
- Freqtrade rereads the same atomically published file; Hunter does not rerank hourly in v1.
