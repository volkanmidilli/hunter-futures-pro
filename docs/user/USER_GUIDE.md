# User Guide

> **Research only.** No profitability guarantee. Hunter does not authorize execution, production deployment,
> live trading, dry-run trading, automatic execution, strategy selection, universe selection, order
> placement, signal generation, strategy mutation, universe mutation, or position changes. Human review
> remains required for every publish.

Verified against commit `08a78d9`, version `0.72.0-dev`.

## What Hunter Does

Hunter takes a research report you (or your own pipeline) already produced — which Binance USDT-M futures
pairs are eligible, and how strong their relative-strength and open-interest scores are — and turns it into:

1. A **ranked, deterministic shortlist**, up to 30 pairs by default.
2. A **published pairlist file** Freqtrade can read natively (`RemotePairList`, `file:///` transport).
3. A **plain-language and machine-readable explanation** of every selected and rejected pair.
4. An **immutable dated snapshot** of each day's publish, for backtests that need to replay history exactly.

## What Hunter Does Not Do

- It does not connect to Binance, any exchange, or any network service (verified: no `requests`/`httpx`/
  `aiohttp`/`socket`/websocket-library imports anywhere in `src/hunter/pairlist_export/`).
- It does not compute relative-strength or open-interest scores itself — you supply those as input.
- It does not place orders, manage positions, or decide leverage.
- It does not run a scheduler — the "daily at 08:05 UTC" cadence is something *you* configure via cron or a
  systemd timer (`docs/operations/DAILY_OPERATIONS.md`); Hunter has no built-in daemon.
- It does not implement a custom Freqtrade plugin or run an HTTP server — Freqtrade's own native
  `RemotePairList` method reads the file Hunter writes.
- It does not guarantee profitability, suitability, or trading readiness of anything it publishes.

## How Coins Are Evaluated

Every eligible pair you list gets ranked by:

1. Relative-strength score (higher is better)
2. Open-interest / liquidity score (higher is better, used as a tie-break)
3. Data-quality percentage (higher is better, second tie-break)
4. Pair name, alphabetically (final deterministic tie-break — guarantees no ties ever occur)

A pair missing **both** RS and OI data is excluded regardless of where it would otherwise rank — Hunter marks
it `INSUFFICIENT_EVIDENCE` rather than guessing. This ranking is fully deterministic: running it twice on the
same input always produces the same order and the same cryptographic fingerprint (verified during this
validation by running an identical `pairlist build` twice and diffing the output byte-for-byte).

## How Selected and Rejected Pairs Are Explained

Every publish writes two separate files: the pairlist itself (just pair names and a refresh interval — what
Freqtrade actually reads) and a separate **audit file** recording, for every pair considered, whether it was
selected or rejected and exactly why (a machine-readable reason code like `RS_SCORE`, `BELOW_MIN_PAIRS`,
`INVALID_PAIR_FORMAT`, etc. — full catalog in `docs/technical/PAIRLIST_PIPELINE.md`). Run `hunter pairlist
explain <audit-file>` to read it as plain text.

## Why Hunter Publishes 30 Candidates

By default, Hunter publishes up to `publish_candidates = 30` ranked pairs — deliberately more than the
`target_final_pairs = 20` you'll likely end up trading. This headroom exists because Freqtrade's own native
filters (age, delisting, spread) run *after* Hunter's list and will legitimately remove some pairs. Hunter
does not try to guess which 20 will survive those filters, and it never pads the list with lower-quality
pairs just to hit an exact count.

## Why Freqtrade May End With Fewer Pairs

Freqtrade applies `AgeFilter` (pair must be listed at least 30 days), `DelistFilter` (drop delisted pairs),
and `SpreadFilter` (max 0.5% spread) after consuming Hunter's `RemotePairList`, plus a static blacklist for
leveraged-token tickers (`UP`/`DOWN`/`BULL`/`BEAR`). A pair Hunter ranked highly can still be dropped at this
stage — that is expected, native Freqtrade behavior, not a Hunter defect.

## Daily Workflow

1. Produce (or receive) today's ranking-input JSON — see `docs/user/INPUT_FORMAT.md`.
2. Run `hunter daily-pairlist --as-of <today> --input <ranking_input.json> --output-dir <deploy-dir>
   --snapshot-dir <snapshot-dir>` (one command: ranks, gates, publishes, snapshots).
3. Check the exit code. `0` means published; non-zero means the prior valid pairlist and audit were left
   completely untouched (verified, including for a same-date snapshot conflict — see
   `docs/technical/PAIRLIST_PIPELINE.md`).
4. Optionally run `hunter pairlist validate`/`explain` to review before trusting the publish.
5. Freqtrade rereads the published file on its own `refresh_period` (default hourly) — no action needed on
   your side to "push" it to Freqtrade.

Full operational detail, including a cron/systemd example: `docs/operations/DAILY_OPERATIONS.md`.

## Generated Files

| File | Where | What it is |
|---|---|---|
| `hunter-pairs.json` | `--output-dir` | Live pairlist Freqtrade's `RemotePairList` reads |
| `hunter-pairs-audit.json` | `--output-dir` | Live audit/explain record |
| `hunter-pairs.json.previous-good` | `--output-dir` | Prior valid pairlist, kept automatically |
| `hunter-pairs-audit.json.previous-good` | `--output-dir` | Prior valid audit record |
| `hunter-pairs-YYYYMMDD.json` | `--snapshot-dir` | Immutable per-day snapshot of the pairlist |
| `hunter-pairs-YYYYMMDD-audit.json` | `--snapshot-dir` | Immutable per-day snapshot of the audit |

## Audit Report

The audit JSON records, for every considered pair: rank, selected/rejected, RS/OI scores, reason codes, and a
per-pair fingerprint. It always ends with a fixed research-only notice. Treat it as your primary evidence
trail for "why did Hunter pick these pairs today" — not the pairlist file itself, which intentionally carries
no explanatory metadata (Freqtrade doesn't need it).

## Static Snapshots

Every successful publish also writes an immutable, dated copy. If you rerun the same date with identical
input, that's a safe no-op. If you rerun the same date with *different* input, Hunter refuses to silently
overwrite history: the snapshot conflict is detected before the live pairlist is touched, so both the live
pairlist and the existing dated snapshot remain exactly as they were — see
`docs/operations/RECOVERY_AND_ROLLBACK.md` for the full recovery reference.

## Human Review

Every audit record and CLI safety-summary output states plainly: this is a research-only artifact and does
not authorize execution, trading, or any position change. Treat every publish as something a human reviews
(via `pairlist explain`) before trusting it operationally — Hunter's own defaults assume this
(`human_approval_required=True` is an immutable safety flag; construction with any other value raises an
error).

## Integrating With Native Freqtrade RemotePairList

Hunter emits ready-to-merge config fragments via `hunter pairlist deployment-profile --target
native|container`. Both use Freqtrade's own `RemotePairList` method — no custom plugin.

### Native-Host Path

Use `--target native` when Hunter and Freqtrade run on the same machine's filesystem. The emitted
`pairlist_url` is `file:///home/freqtrade/user_data/pairlists/hunter-pairs.json` — adjust the path to match
where you actually point `--output-dir`.

### Docker/Container Path

Use `--target container` when Freqtrade runs in a container and Hunter publishes into a volume bind-mounted
into it. The emitted `pairlist_url` is `file:///freqtrade/user_data/pairlists/hunter-pairs.json` — the
in-container mount path, not the host path. See `docs/operations/DEPLOYMENT_GUIDE.md` for the bind-mount
example.

## Safe Operational Examples

```bash
# Preview ranking without publishing
hunter coins rank --as-of 2026-07-21 --input input.json --output ranked.json

# Full daily publish
hunter daily-pairlist --as-of 2026-07-21 --input input.json \
  --output-dir /srv/freqtrade/user_data/pairlists \
  --snapshot-dir /srv/hunter/snapshots

# Sanity-check what's currently live
hunter pairlist validate /srv/freqtrade/user_data/pairlists/hunter-pairs.json
hunter pairlist explain /srv/freqtrade/user_data/pairlists/hunter-pairs-audit.json
```

## Limitations

- Hunter does not compute RS/OI scores itself — the glue from raw market data to the ranking-input JSON is
  not (yet) an automated CLI step; you must produce that JSON yourself or via your own tooling.
- The reserved eligibility reason codes (`INELIGIBLE_STABLECOIN`, `INELIGIBLE_LEVERAGED`,
  `INELIGIBLE_BENCHMARK`) are defined but not currently raised by any code path in this version — eligibility
  filtering for those categories is not yet implemented; supply an already-eligible `eligible_pairs` list.

## No Profitability Guarantee

Nothing Hunter produces is investment advice, a trading signal, or evidence of future profitability. Every
audit record says so explicitly. Review every publish yourself before treating it as anything beyond
research output.
