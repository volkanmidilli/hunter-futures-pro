# Troubleshooting (User)

> Companion to `docs/reference/CLI_REFERENCE.md` (exact command syntax) and
> `docs/technical/PAIRLIST_PIPELINE.md` (pipeline internals). This is the user-facing troubleshooting guide;
> `docs/operations/TROUBLESHOOTING.md` is a separate, pre-existing, agent/repo-maintenance-oriented document —
> don't confuse the two.

All error text below was reproduced by actually running the commands during validation of commit `08a78d9`.

## `ModuleNotFoundError: No module named 'hunter'`

The package isn't installed in the Python environment you're using. Activate the venv (`source
.venv/bin/activate` / `.venv/bin/activate.fish`) and confirm with `python -c "import hunter;
print(hunter.__version__)"`. If that still fails, run `pip install -e .` from the repo root.

## Fish `activate` Error

Fish needs `activate.fish`, not the bash `activate` script:

```fish
source .venv/bin/activate.fish   # correct
source .venv/bin/activate        # wrong — syntax error in fish
```

## `error: externally-managed-environment`

You're running `pip install` against your system Python (PEP 668 protection), not a venv. Create and
activate a venv first (`python3 -m venv .venv && source .venv/bin/activate`) rather than passing
`--break-system-packages`.

## Editable Install Doesn't Pick Up Changes / Shows Wrong Version

If `pip show hunter-futures-pro` reports an older version than `VERSION`/`hunter.__version__`, the egg-info
metadata is stale (cosmetic — doesn't affect behavior). Re-run `.venv/bin/pip install -e .` to refresh it.
If `hunter` itself resolves to the wrong code, confirm `which hunter` points into your active `.venv/bin/`.

## `Publish gate rejected pairlist: INVALID_PAIR_FORMAT`

A selected pair doesn't match `BASE/USDT:USDT` (uppercase, `USDT` settle currency). Check
`docs/user/INPUT_FORMAT.md` for the exact regex and valid/invalid examples. Nothing was written — the
previous valid pairlist (if any) is untouched.

## `Publish gate rejected pairlist: DUPLICATE_PAIR`

The same pair string appears twice in your `eligible_pairs`. Deduplicate the input (or run `hunter universe
refresh` first, which sorts and dedupes). Nothing was written.

## `Error: no eligible pairs have sufficient evidence (RS and/or OI data)`

Every pair in `eligible_pairs` is missing **both** `rs_scores` and `oi_scores`. This is raised before the
gate even runs (a different code path than the gate-level `INSUFFICIENT_EVIDENCE` reason code — see
`docs/technical/PAIRLIST_PIPELINE.md`). Add at least one score per pair, or reduce `eligible_pairs` to pairs
you actually have data for.

## `Publish gate rejected pairlist: BELOW_MIN_PAIRS`

Fewer than `min_pairs` (default 5) pairs cleared selection. Either supply more eligible pairs with sufficient
evidence, or (with explicit awareness of the safety implication) construct a custom
`PairlistRankingConfig(min_pairs=...)` if calling the library directly rather than the CLI — the CLI itself
always uses the default config. Nothing was written to `--output-dir` on this rejection.

## Previous Output Preserved (this is expected, not a bug)

When a publish is rejected by the gate (any `BELOW_MIN_PAIRS`/`DUPLICATE_PAIR`/`INVALID_PAIR_FORMAT`/
`EMPTY_UNIVERSE`/`INSUFFICIENT_EVIDENCE` reason), the previously published `hunter-pairs.json`/
`hunter-pairs-audit.json` are left completely untouched — rejection happens before any write is attempted.
Freqtrade will keep serving the last good pairlist. This is the intended fail-closed behavior.

## Snapshot Conflict (`Error: snapshot pairlist for <date> already exists with different content`)

You reran the same `--as-of` date with **different** ranking input than the first successful run for that
date. Snapshots are immutable by design — this is intentional, to protect historical backtest data. The
conflict is detected and rejected **before** the live pairlist/audit are touched (verified: they remain
byte-identical to before the run, and no `.previous-good` is created, proving publish never ran). Nothing to
restore — either use a different `--snapshot-dir`, correct `--as-of` to the intended date, or supply the
originally-published content again.

## Permission Denied

```text
PermissionError: [Errno 13] Permission denied: '<output-dir>'
```

This surfaces as a raw Python traceback (not a clean `Error: ...` message) if `--output-dir`/`--snapshot-dir`
isn't writable by the current user — verified by testing against a `chmod 555` directory. Exit code 1. Fix
directory permissions or choose a writable path; no output was written.

## `Error: output-dir must not target the repository data/ tree` (unsafe output path)

`--output-dir` or `--snapshot-dir` resolved to a path equal to or nested under this repository's `data/` or
`reports/` directories. This is enforced deliberately — publish output must go to an operator-chosen
deployment path (e.g. Freqtrade's `user_data/pairlists`), never into those excluded trees. Choose a different
path.

## Freqtrade `file:///` Path Issues

`pairlist_url` in your Freqtrade config must be an absolute `file:///` URL matching wherever Hunter's
`--output-dir` actually is on that machine. A mismatch (e.g. using the container-profile path on a native
host, or vice versa) means Freqtrade silently reads a nonexistent or stale file. Cross-check with `hunter
pairlist deployment-profile --target native|container` and adjust the emitted path if your directory layout
differs from the shown default (`/home/freqtrade/user_data/pairlists/...` for native,
`/freqtrade/user_data/pairlists/...` for container).

## Docker/Container Path Issues

If Freqtrade runs in a container, `--output-dir` must be the **host** side of a bind mount whose **container**
side matches the `file:///...` path in your Freqtrade config (the container profile's default:
`/freqtrade/user_data/pairlists/hunter-pairs.json`). Publishing to a host path that isn't actually mounted
into the container means Freqtrade never sees updates. See `docs/operations/DEPLOYMENT_GUIDE.md`.

## RemotePairList Stale Cache

Freqtrade's `RemotePairList` only rereads the file every `refresh_period` seconds (Hunter's emitted profiles
default to `3600` = hourly) — a fresh publish won't take effect in a running Freqtrade instance until that
interval elapses, or until Freqtrade is restarted. This is Freqtrade's own caching behavior, not something
Hunter controls beyond setting `refresh_period` in the emitted config.

## `freqtrade test-pairlist` Limitations

`freqtrade test-pairlist` needs to query live exchange market data to evaluate filters like `AgeFilter`. It
is a Freqtrade-side, network-dependent acceptance check — not something Hunter's own local, network-free
workflow runs or depends on. Treat a failure there as a Freqtrade/exchange-connectivity question, not a
Hunter pairlist-content question (validate the pairlist content itself with `hunter pairlist validate`
first).

## Interpreting Exit Codes

| Exit code | Meaning | What to do |
|---|---|---|
| `0` | Success | — |
| `1` | Either a handled Hunter error (`Error: ...` on stderr, clean message) or an uncaught Python exception (raw traceback) | Read the message/traceback — both are exit 1, so don't infer error type from the exit code alone |
| `2` | argparse-level usage error — missing/unknown argument or subcommand | Re-check the command syntax against `docs/reference/CLI_REFERENCE.md` |
