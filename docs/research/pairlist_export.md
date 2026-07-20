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
├── ranking_adapter.py       # deterministic tie-break ranking over score maps
├── audit.py                 # audit/explain record builder + renderers
├── validator.py             # publish gate + published-artifact validator
├── publisher.py             # atomic writer, previous-good preservation, repo-tree guard
├── snapshot.py               # dated, immutable static snapshots
├── deployment_profiles.py   # native-host and container file:/// Freqtrade profiles
├── cli.py                   # universe / coins / pairlist / daily-pairlist commands
└── __init__.py               # public API
```

Dependency direction is a DAG: `models`/`fingerprint` are leaves; `audit` depends on both; `validator`/`publisher` depend on `audit`; `snapshot` depends on `publisher`+`audit`; `cli` depends on all of the above. No circular imports.

## Reuse boundary

`ranking_adapter.rank_pairs` consumes pre-computed `rs_scores` / `oi_scores` / `data_quality` maps (`dict[str, Decimal | None]`) rather than importing `relative_strength`/`open_interest` engine internals directly. This is a deliberate seam: it reuses those engines' *output* without duplicating their scoring algorithms, and keeps `pairlist_export` decoupled from their internal report shapes. The CLI's ranking-input JSON (below) is the concrete contract at that seam. Producing that JSON from live `relative_strength`/`open_interest`/`research_universe` reports is a separate, not-yet-built glue step — out of SPEC-074's implement-only scope, since it doesn't touch ranking, gating, publishing, or CLI wiring.

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
hunter daily-pairlist --as-of YYYY-MM-DD --input <ranking_input.json> --output-dir <dir> [--snapshot-dir <dir>]
```

All commands are local-file-only: no network calls, no Binance/exchange access, no Freqtrade process interaction. `universe refresh` canonicalizes (sorts, dedupes, format-checks) a locally supplied pairs file; it does not fetch data from Binance. `hunter.core.cli` routes the `universe`/`coins`/`pairlist`/`daily-pairlist` top-level tokens to this package's CLI; every other command still goes to the pre-existing `reporting_cli`.

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
