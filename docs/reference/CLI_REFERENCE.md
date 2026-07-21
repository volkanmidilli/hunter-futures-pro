# CLI Reference

> **Research only.** Every command below is local-file-only: no network calls, no exchange access, no
> Freqtrade process interaction. This document only lists commands and behavior actually observed by running
> the `hunter` CLI at commit `08a78d9` and revalidated after the Stage 3 unified-help remediation, version
> `0.72.0-dev`.

## `hunter --help` / `hunter -h` / `hunter` (no args)

**Verified, fixed.** `src/hunter/core/cli.py::main` now special-cases `-h`/`--help`/no-args before the
per-group dispatch: `hunter --help` and `hunter -h` print one unified top-level help (reporting_cli's own
help text, reused verbatim, plus an appended pairlist-export command summary) and exit `0`. Bare `hunter`
(no arguments) prints the same unified help to stderr alongside `Error: No command provided.` and exits `2`
(conventional argparse-style "missing required subcommand" behavior). All other routing is unchanged:
`hunter <group> --help` for `universe`/`coins`/`pairlist`/`daily-pairlist` still goes to
`pairlist_export.cli`'s own real parser; every other command still goes to `reporting_cli`.

Verified output of `hunter --help`:

```text
This Local Research Reporting CLI is a human-audit / research-only tool. [...]

Usage: python -m hunter.reporting_cli <command> [options]

Commands:
  version                 Print the project version.
  safety-summary          Print the research-only safety summary.
  list-artifacts          List default artifact paths as opaque strings.
  validate-artifact-paths <path>...
                          Validate that local path strings are safe.
  render-sample           Write deterministic sample reports to --output-dir.

Options:
  -h, --help              Show this help message and exit.
  --format <FORMAT>       Output format for safety-summary: text, json, markdown.
  --output-dir <PATH>     Output directory for render-sample.
  --dry-run               For render-sample: report paths without writing.

Pairlist-export commands (SPEC-074):
  universe refresh             Canonicalize a local universe file.
  coins rank                   Rank eligible pairs deterministically.
  pairlist build                Rank, gate, publish, and snapshot.
  pairlist validate             Validate a published pairlist JSON.
  pairlist explain              Render an audit JSON as human-readable text.
  pairlist deployment-profile   Emit a native/container Freqtrade RemotePairList profile.
  pairlist feather-input         Build a SPEC-075 v2 ranking-input from local 1h-futures Feather files.
  pairlist from-feather          Feather files -> ranking input -> rank, gate, publish, and snapshot.
  daily-pairlist                Rank, gate, publish, and snapshot (single cron-friendly command).

Run `hunter <group> --help` (e.g. `hunter pairlist build --help`) for full per-command options.
```

Exit codes: `hunter --help` / `hunter -h` → 0. `hunter` (no args) → 2.

## `hunter version`

Prints the package version and exits 0.

```text
$ hunter version
hunter-futures-pro 0.72.0-dev
```

No options. No output file.

## `hunter safety-summary`

Prints the research-only banner plus a machine-checkable safety-flag summary (all booleans `True`/`False`
verified against actual current output). Exit 0.

```text
$ hunter safety-summary
[...banner...]
has_invalid_path: False
has_network_reference: False
has_traversal_attempt: False
has_unsafe_content: False
no_action_commands: True
no_daemon: True
no_database: True
no_exchange_connection: True
no_execution_approval: True
no_file_read_in_engine: True
no_freqtrade_input: True
no_leverage: True
no_network_connection: True
no_order_sizing: True
no_portfolio_approval: True
no_position_sizing: True
no_rest_api: True
no_scheduler: True
no_shorting: True
no_strategy_approval: True
no_trade_approval: True
no_trading_signal: True
no_universe_approval: True
no_web_ui: True
not_trading_advice: True
research_only: True
```

Options: `--format {text,json,markdown}` (verified in `reporting_cli` help text; not independently exercised
in this pass beyond the default `text` format shown above).

## `hunter universe refresh`

```text
usage: hunter universe refresh [-h] --input INPUT --output OUTPUT
```

Canonicalizes (sorts, dedupes, validates format of) a locally supplied pairs file. Does **not** fetch data
from Binance or any network source.

- **Required**: `--input <path>` (JSON: either `{"pairs": [...]}` or a bare `[...]` list of pair strings),
  `--output <path>`.
- **Output**: `{"pairs": [<sorted, deduped>]}` written atomically to `--output`.
- **Exit codes**: `0` on success. `2` with `Error: unsupported universe input shape: <path>` if the input is
  neither an object with `pairs` nor a bare list. `2` with `Error: invalid pair format in universe input:
  [...]` if any pair fails the `BASE/USDT:USDT` shape.

## `hunter coins rank`

```text
usage: hunter coins rank [-h] --as-of AS_OF --input INPUT --output OUTPUT
```

Ranks eligible pairs deterministically (no gate, no publish, no snapshot) — a dry preview of the ranking
step. See `docs/user/INPUT_FORMAT.md` for the `--input` ranking-input JSON contract.

- **Required**: `--as-of YYYY-MM-DD`, `--input <ranking_input.json>`, `--output <path>`.
- **Output**: JSON with `as_of_date`, `universe_total`, `ranked: [{pair, rank, selected, rs_score, oi_score,
  reason_codes, fingerprint}, ...]`, written atomically.
- **Verified example**: `hunter coins rank --as-of 2026-07-21 --input ranking_input.json --output
  ranked.json` → `Wrote 8 ranked pairs to ranked.json`, exit 0.
- **Exit codes**: `0` on success. `1` with `Error: no eligible pairs have sufficient evidence (RS and/or OI
  data)` (a raw `PairlistRankingError` message, caught by `main()`) if every pair is missing both RS and OI.
  `1` with `Error: ranking input contains a non-numeric score: ...` if a score value can't parse as
  `Decimal`. **Uncaught exceptions** (`FileNotFoundError` for a missing `--input`, `json.JSONDecodeError` for
  malformed JSON) print a raw Python traceback and exit `1` — verified directly; these are not wrapped in a
  clean `Error: ...` message. See `docs/user/TROUBLESHOOTING.md`.

## `hunter pairlist build`

```text
usage: hunter pairlist build [-h] --as-of AS_OF --input INPUT
                             --output-dir OUTPUT_DIR
                             [--snapshot-dir SNAPSHOT_DIR]
```

Ranks, gates, atomically publishes, and snapshots. Equivalent to `hunter daily-pairlist` (both dispatch to
the same `_build_and_publish` function).

- **Required**: `--as-of YYYY-MM-DD`, `--input <ranking_input.json>`, `--output-dir <dir>`.
- **Optional**: `--snapshot-dir <dir>` (defaults to `--output-dir` if omitted).
- **Output files** (in `--output-dir`): `hunter-pairs.json` (native RemotePairList), `hunter-pairs-audit.json`
  (audit/explain), plus `hunter-pairs.json.previous-good` / `hunter-pairs-audit.json.previous-good` if a prior
  publish existed. In `--snapshot-dir`: `hunter-pairs-YYYYMMDD.json` / `hunter-pairs-YYYYMMDD-audit.json`.
- **Verified example**: 8-pair synthetic fixture → `Published 8 pairs:` followed by the four output paths,
  exit 0.
- **Exit codes**: `0` on success. `1` with `Publish gate rejected pairlist: <REASON_CODE[, REASON_CODE...]>`
  on any gate rejection (`BELOW_MIN_PAIRS`, `DUPLICATE_PAIR`, `INVALID_PAIR_FORMAT`, `EMPTY_UNIVERSE`,
  `INSUFFICIENT_EVIDENCE` at the gate level) — **no write occurs**. `1` with a raw `PairlistRankingError`
  message if *no* candidate has sufficient evidence at all (pre-gate). `1` with `Error: output-dir must not
  target the repository data/ tree: <path>` (or `reports/`) if `--output-dir`/`--snapshot-dir` targets a
  forbidden path. `1` with `Error: snapshot pairlist for <date> already exists with different content: <path>`
  if the snapshot conflicts — the snapshot is now validated/written **before** the live pairlist, so this
  rejection leaves the live pairlist/audit completely untouched (see
  `docs/technical/PAIRLIST_PIPELINE.md`).

## `hunter daily-pairlist`

```text
usage: hunter daily-pairlist [-h] --as-of AS_OF --input INPUT
                             --output-dir OUTPUT_DIR
                             [--snapshot-dir SNAPSHOT_DIR]
```

Identical behavior, options, outputs, and exit codes to `hunter pairlist build` — described by its own
`--help` as "single cron-friendly command." Intended as the one command an external scheduler (cron/systemd
timer) invokes daily; Hunter has no built-in scheduler (see `docs/operations/DAILY_OPERATIONS.md`).

## `hunter pairlist validate`

```text
usage: hunter pairlist validate [-h] pairlist_file
```

Validates an already-published (or externally supplied) RemotePairList JSON against schema, pair-format,
uniqueness, and threshold rules (`PairlistRankingConfig()` defaults — thresholds are always applied, not
optional at the CLI level).

- **Positional**: `pairlist_file` (path).
- **Output**: prints `valid: True|False` and `reason_codes: <comma-joined or "OK">` to stdout.
- **Verified examples**: valid 8-pair file → `valid: True` / `reason_codes: OK`, exit 0. Hand-built 60-pair
  file → `valid: False` / `reason_codes: ABOVE_MAX_PAIRS`, exit 1. Malformed JSON → uncaught
  `json.JSONDecodeError` traceback, exit 1 (not a clean `valid: False` message).
- **Exit codes**: `0` if valid, `1` if invalid (including uncaught parse errors).

## `hunter pairlist explain`

```text
usage: hunter pairlist explain [-h] audit_file
```

Renders an audit JSON as human-readable text (universe/eligible/selected/rejected counts, reason-code
summary, per-pair selected/rejected lines with rank and reason codes, and the fixed research notice).

- **Positional**: `audit_file` (path).
- **Verified example output** (against the smoke-test fixture):

```text
Pairlist audit -- as-of 2026-07-21
Universe: 8 total, 8 eligible
Selected: 8  Rejected: 0

Reason code summary:
  DATA_SUFFICIENCY: 8
  OI_LIQUIDITY: 8
  RS_SCORE: 7

Research-only artifact. Does not authorize execution, production deployment, live trading, dry-run trading,
automatic execution, strategy selection, universe selection, order placement, signal generation, strategy
mutation, universe mutation, or position changes. Human review is required.
```

- **Exit codes**: `0` always on successful read (no validation performed — this is a renderer, not a
  validator). Malformed input JSON → uncaught traceback, exit 1.

## `hunter pairlist deployment-profile`

```text
usage: hunter pairlist deployment-profile [-h] --target {container,native}
                                          [--output OUTPUT]
```

Emits a native-host or container Freqtrade `RemotePairList` config fragment.

- **Required**: `--target native|container`.
- **Optional**: `--output <path>` (writes atomically; if omitted, prints to stdout).
- **Verified**: both targets produce identical JSON except `pairlist_url`
  (`file:///home/freqtrade/user_data/pairlists/hunter-pairs.json` for `native`,
  `file:///freqtrade/user_data/pairlists/hunter-pairs.json` for `container`). Full fragment shape and
  filter chain: `docs/technical/PAIRLIST_PIPELINE.md` §"Native Freqtrade Filters".
- **Exit codes**: `0` on success. `2` with `Error: unknown deployment target: <target>` (unreachable via the
  CLI itself since `--target` is `choices`-constrained by argparse, which would instead print its own usage
  error and exit 2 before reaching this code path).

## `hunter pairlist feather-input` (SPEC-075)

```text
usage: hunter pairlist feather-input [-h] --data-dir DATA_DIR --output OUTPUT
                                     --as-of AS_OF
```

Reads only local `BASE_USDT_USDT-1h-futures.feather` files under `--data-dir` (no network, no exchange
access, no writes to the source directory) and writes a `schema_version: hunter-ranking-input-v2` /
`ranking_profile: V2_RS_LIQUIDITY` ranking-input JSON. Reuses the existing relative-strength engine
unchanged for the RS dimension; liquidity is `close × volume → daily total → 30-day average → log1p →
cross-sectional average-rank percentile`; `oi_scores` is always `{}` and `oi_available` is always `false`
under this profile. A missing `BTC_USDT_USDT-1h-futures.feather` benchmark file is a hard error (relative
strength cannot be computed without it).

- **Required**: `--data-dir <dir>`, `--output <path>`, `--as-of YYYY-MM-DD`.
- **Verified example** (synthetic 90-day fixtures, BTC + 5 candidates): `Wrote ranking-input
  hunter-ranking-input-v2 (V2_RS_LIQUIDITY, 5 eligible pairs) to <output>`, exit 0.
- **Exit codes**: `0` on success. `1` with `Error: <message>` if no BTC benchmark file is found, or any
  other `FeatherAdapterError`/`RankingInputV2Error` (e.g. a directory that does not exist).

## `hunter pairlist from-feather` (SPEC-075)

```text
usage: hunter pairlist from-feather [-h] --data-dir DATA_DIR
                                    --output-dir OUTPUT_DIR
                                    [--snapshot-dir SNAPSHOT_DIR]
                                    --as-of AS_OF
```

Runs `feather-input`'s exact same Feather-adapter implementation, then the existing SPEC-074 profile-aware
rank/gate/publish/snapshot pipeline (`rank_pairs_v2` → `run_publish_gate_v2` → `publish_pairlist` →
`write_snapshot`) — nothing about the publish/snapshot mechanics differs from `hunter pairlist build`.

- **Required**: `--data-dir <dir>`, `--output-dir <dir>`, `--as-of YYYY-MM-DD`.
- **Optional**: `--snapshot-dir <dir>` (defaults to `--output-dir`).
- **Verified example** (synthetic 90-day fixtures, BTC + 5 candidates): `Published 5 pairs
  (V2_RS_LIQUIDITY):` followed by the four output paths, exit 0. A single-candidate fixture (BTC + 1) fails
  the default `min_pairs=5` gate with `Publish gate rejected pairlist: BELOW_MIN_PAIRS`, exit 1 — the
  ranking-input itself still generates successfully via `feather-input` for the same fixture.
- **Audit fields** (`hunter-pairs-audit.json`): includes the v1 fields plus `schema_version:
  "hunter-ranking-input-v2"`, `ranking_profile: "V2_RS_LIQUIDITY"`, `active_score_dimensions: ["rs",
  "liquidity"]`, `ignored_score_dimensions: []`, `universe_size_at_scoring`, `universe_fingerprint`,
  `oi_available: false`, `source_metadata`, and `per_pair_evidence`.
- **Exit codes**: same family as `hunter pairlist build` (`BELOW_MIN_PAIRS`, `ABOVE_MAX_PAIRS`,
  `DUPLICATE_PAIR`, `INVALID_PAIR_FORMAT`, `EMPTY_UNIVERSE`), plus `PROFILE_FIELD_MISMATCH` if the
  underlying ranking-input violates its own declared profile's field rules.

## Invalid Command / Argument Behavior (verified)

| Input | Output | Exit |
|---|---|---|
| `hunter notacommand` | `Unknown command: notacommand` | 2 |
| `hunter pairlist` (no action) | argparse usage + `hunter pairlist: error: the following arguments are required: action` | 2 |
| `hunter pairlist badaction` | argparse usage + `hunter pairlist: error: argument action: invalid choice: 'badaction' (choose from 'build', 'validate', 'explain', 'deployment-profile', 'feather-input', 'from-feather')` | 2 |
| `hunter coins` (no action) | argparse usage + `hunter coins: error: the following arguments are required: action` | 2 |
| `hunter daily-pairlist` (missing required flags) | argparse usage + `hunter daily-pairlist: error: the following arguments are required: --as-of, --input, --output-dir` | 2 |
| `hunter` (no args) | unified top-level help (stderr) + `Error: No command provided.` | 2 |

## Exit Code Summary

| Code | Meaning |
|---|---|
| `0` | Success (or, for `pairlist validate`, "structurally parsed and reported" even if `valid: False` is not the case here — validate returns 1 when invalid) |
| `1` | Handled application error (`PairlistExportError` subclass with a clean message) **or** an uncaught Python exception (raw traceback) — both currently produce exit 1; distinguish by output shape, not exit code |
| `2` | argparse-level usage error (missing/invalid arguments, unknown command) |
