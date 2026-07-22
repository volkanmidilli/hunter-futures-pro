# Deployment Guide (Pairlist Publishing)

> **Research only.** This guide covers deploying Hunter's pairlist-publishing output for Freqtrade to
> consume. It does not cover, authorize, or configure live trading, dry-run trading, or Freqtrade execution
> itself — those remain entirely Freqtrade's and the operator's responsibility.

Verified against commit `58aeb20`, version `0.72.0-dev`, `src/hunter/pairlist_export/deployment_profiles.py`.

## Native Host Deployment

Use when Hunter and Freqtrade run as processes on the same host filesystem.

```bash
hunter pairlist deployment-profile --target native --output freqtrade-hunter-fragment.json
```

Emits (verified exact output):

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

Merge this into your Freqtrade `config.json` (or `user_data/config.json`). **Adjust `pairlist_url`** to the
actual absolute path where Hunter publishes `hunter-pairs.json` on this host — the emitted default
(`/home/freqtrade/user_data/pairlists/hunter-pairs.json`) assumes a specific user/layout; change it to match
your `--output-dir`.

## Container Deployment

Use when Freqtrade runs in a container and Hunter publishes into a bind-mounted volume.

```bash
hunter pairlist deployment-profile --target container --output freqtrade-hunter-fragment.json
```

Same fragment, except `pairlist_url` is `file:///freqtrade/user_data/pairlists/hunter-pairs.json` — the
**in-container** path. Set up the bind mount so Hunter's `--output-dir` (a host path) maps to
`/freqtrade/user_data/pairlists` inside the container, e.g. in `docker-compose.yml`:

```yaml
services:
  freqtrade:
    volumes:
      - /srv/hunter/pairlists:/freqtrade/user_data/pairlists:ro
```

Hunter itself runs **outside** the container (it has no network/exchange dependency, so it doesn't need to
run inside Freqtrade's environment) and writes to `/srv/hunter/pairlists` on the host.

## Feather Input Root (SPEC-075)

If using `hunter pairlist feather-input` / `from-feather`, Hunter needs read access to the local Freqtrade
Feather data root (e.g. `user_data/data/binance/futures`). The directory must contain `*-1h-futures.feather`
files and be readable by the Hunter process. **Read-only permission is sufficient and recommended** — Hunter
never modifies source Feather files (verified via SHA-256 before/after in tests). Do not point `--data-dir`
at this repository's `data/` or `reports/` trees; use the actual Freqtrade user-data directory or a dedicated
mirror.

The pairlist output mapping is unchanged: `--output-dir` still controls where `hunter-pairs.json` and
`hunter-pairs-audit.json` are published, and the `file:///` `pairlist_url` must match that host/container
path exactly (see the summary table below).

## Directory Ownership and Permissions

- The pairlist output directory must be writable by whatever user/process runs `hunter pairlist build` /
  `daily-pairlist`, and readable by whatever user/process runs Freqtrade (they may differ, especially in the
  container case — mount read-only into the container as shown above, since Freqtrade only reads).
- Never point `--output-dir` or `--snapshot-dir` at this repository's `data/` or `reports/` trees — Hunter
  rejects this unconditionally (`reject_forbidden_output_dir`). Use a dedicated deployment path such as
  Freqtrade's `user_data/pairlists`, entirely outside this repo.
- Snapshot storage (`--snapshot-dir`) can be the same directory as `--output-dir` (the CLI default when
  `--snapshot-dir` is omitted) or a separate archival location — separating them lets you retain snapshot
  history independently of the live pairlist's lifecycle/backups.

## `file:///` Path Mapping Summary

| Deployment | Host path (Hunter writes here) | `pairlist_url` (Freqtrade reads here) |
|---|---|---|
| Native | e.g. `/home/freqtrade/user_data/pairlists/hunter-pairs.json` | `file:///home/freqtrade/user_data/pairlists/hunter-pairs.json` (must match exactly) |
| Container | Host path bind-mounted to `/freqtrade/user_data/pairlists` | `file:///freqtrade/user_data/pairlists/hunter-pairs.json` (container-side path) |

## Freqtrade Config Fragment

See the JSON blocks above — merge `exchange.pair_blacklist` (extend, don't replace, any existing blacklist)
and the `pairlists` array into your Freqtrade config. The `RemotePairList` entry must be first in the
`pairlists` array (Freqtrade applies filters in list order); `AgeFilter`/`DelistFilter`/`SpreadFilter` should
follow it, as emitted.

## Acceptance Checklist

1. `hunter pairlist deployment-profile --target <native|container>` — emits without error.
2. `hunter pairlist build ...` against real (or realistic synthetic) research input — publishes successfully.
3. `hunter pairlist validate <output-dir>/hunter-pairs.json` — reports `valid: True`.
4. Freqtrade config merged, `pairlist_url` verified to match the actual publish path exactly (a mismatch
   fails silently from Hunter's side — Freqtrade just won't find the file).
5. **Optional, network-dependent**: `freqtrade test-pairlist -c <config>` — Freqtrade's own acceptance check.
   This requires live exchange market-data access (for `AgeFilter`/`DelistFilter` evaluation) and was **not
   executed** as part of this repository's automated/local validation for that reason — run it manually,
   deliberately, when you're ready for that network step, per `docs/user/TROUBLESHOOTING.md`.
6. Confirm directory permissions per the section above on both the publish side and the Freqtrade-read side.

## Rollback Strategy

See `docs/operations/RECOVERY_AND_ROLLBACK.md` for the full procedure. Summary: every publish preserves
`*.previous-good` copies automatically; dated snapshots in `--snapshot-dir` provide point-in-time history.
Freqtrade's own `keep_pairlist_on_failure: true` (included in both emitted profiles) means Freqtrade itself
keeps serving its last successfully loaded whitelist if a `RemotePairList` fetch/parse fails — an
additional layer of protection independent of Hunter's own previous-good mechanism.
