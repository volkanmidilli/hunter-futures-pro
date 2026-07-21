# Daily Operations (Pairlist Publishing)

> **Research only.** Hunter has no built-in scheduler, daemon, or server (verified: zero matches for
> `APScheduler|celery|schedule|cron` as actual imports anywhere in `src/hunter/`; string literal `"cron"`
> hits found elsewhere are forbidden-keyword denylist entries, not scheduling code). Everything in this
> document assumes an operator-configured external trigger.

## Recommended Cadence

Per `CLAUDE_SPEC-074_Guardrails.md`: Hunter ranking is intended to run **daily at 08:05 UTC**; Freqtrade
rereads the published file on its own `refresh_period` (default hourly, set in the deployment profile).
Nothing in Hunter enforces this cadence — it's a recommendation for your external scheduler, not a runtime
constraint.

## No Built-In Scheduler — Documentation-Only Examples

The following are illustrative starting points, not tested or endorsed configurations — adapt paths, users,
and environment to your deployment.

**cron** (`crontab -e`):

```cron
5 8 * * * /path/to/.venv/bin/hunter daily-pairlist --as-of $(date -u +\%Y-\%m-\%d) \
  --input /path/to/ranking_input.json \
  --output-dir /srv/freqtrade/user_data/pairlists \
  --snapshot-dir /srv/hunter/snapshots \
  >> /var/log/hunter/daily-pairlist.log 2>&1
```

**systemd timer** (`hunter-daily-pairlist.timer` + `.service`):

```ini
# hunter-daily-pairlist.timer
[Unit]
Description=Hunter daily pairlist publish

[Timer]
OnCalendar=*-*-* 08:05:00 UTC
Persistent=true

[Install]
WantedBy=timers.target
```

```ini
# hunter-daily-pairlist.service
[Unit]
Description=Hunter daily pairlist publish

[Service]
Type=oneshot
User=hunter
ExecStart=/path/to/.venv/bin/hunter daily-pairlist --as-of %Y-%m-%d \
  --input /path/to/ranking_input.json \
  --output-dir /srv/freqtrade/user_data/pairlists \
  --snapshot-dir /srv/hunter/snapshots
```

(systemd doesn't expand `%Y-%m-%d` — wrap the `ExecStart` in a small script that computes `--as-of` from
`date -u +%Y-%m-%d` before invoking `hunter`.)

## Pre-Run Checks

1. Confirm today's ranking-input JSON exists and is fresh (whatever process produces it upstream of Hunter —
   out of Hunter's own scope, see `docs/architecture/SYSTEM_ARCHITECTURE.md` §2).
2. Confirm `--output-dir`/`--snapshot-dir` are writable and are **not** under this repository's `data/` or
   `reports/` trees (Hunter rejects those unconditionally regardless of what you intend).
3. If rerunning a date you've already published today, confirm the input hasn't changed unless you intend
   that — see the snapshot-conflict caveat in `docs/technical/PAIRLIST_PIPELINE.md`.

## Run

```bash
hunter daily-pairlist --as-of $(date -u +%Y-%m-%d) \
  --input /path/to/ranking_input.json \
  --output-dir /srv/freqtrade/user_data/pairlists \
  --snapshot-dir /srv/hunter/snapshots
```

Check the exit code (`0` = published; non-zero = rejected or errored — see
`docs/reference/CLI_REFERENCE.md`'s exit-code table).

## Validate

```bash
hunter pairlist validate /srv/freqtrade/user_data/pairlists/hunter-pairs.json
```

Confirm `valid: True` before considering the run complete.

## Explain

```bash
hunter pairlist explain /srv/freqtrade/user_data/pairlists/hunter-pairs-audit.json
```

Review selected/rejected pairs and reason codes as the human-review step — every audit record states human
review is required.

## Publish (already done by `daily-pairlist`)

`daily-pairlist` ranks, gates, publishes, and snapshots in one call — there is no separate "publish" step to
run afterward. `hunter pairlist build` is the equivalent lower-level command if you want to invoke the same
sequence under a different subcommand name (both call the same internal function).

## Confirm Freqtrade Refresh

Freqtrade rereads `pairlist_url` on its own `refresh_period` (default 3600s in Hunter's emitted profiles) —
no explicit "notify Freqtrade" step exists or is needed. If you need to confirm sooner, restart Freqtrade or
reduce `refresh_period` in its config. `keep_pairlist_on_failure: true` means Freqtrade keeps its last good
whitelist if it can't read/parse the file — check Freqtrade's own logs if you suspect a stale read.

## Inspect Final Pair Count

Freqtrade's actual trading whitelist (after `AgeFilter`/`DelistFilter`/`SpreadFilter` reduce Hunter's
published list) is visible via Freqtrade's own tooling (its logs, or `freqtrade test-pairlist` — network-
dependent, see `docs/user/TROUBLESHOOTING.md`), not via any Hunter command. Hunter's own `hunter-pairs.json`
shows what it *published* (up to 30 by default), not what Freqtrade ultimately trades (target ~20, may be
fewer).

## Incident Escalation

If a daily run fails unexpectedly (non-zero exit, unhandled traceback, or output that doesn't match
`docs/reference/CLI_REFERENCE.md`'s documented behavior):

1. Do not retry blindly — read the error output first (`docs/user/TROUBLESHOOTING.md`).
2. Any non-zero exit from `hunter pairlist build`/`daily-pairlist` (gate rejection, snapshot conflict, or
   malformed input) leaves the previously published `hunter-pairs.json`/`hunter-pairs-audit.json`
   untouched — verified for every documented failure mode (`docs/technical/PAIRLIST_PIPELINE.md`). No
   restore is needed for those cases.
3. Escalate to a human reviewer before manually editing any published artifact — these are audit records as
   well as operational files.
