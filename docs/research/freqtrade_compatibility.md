# Freqtrade Compatibility

> **Research only.** Compatibility validation does not authorize execution, production deployment, live trading, dry-run trading, automatic execution, strategy selection, universe selection, order placement, signal generation, strategy mutation, universe mutation, or position changes. Human review remains required.

## Scope

The Freqtrade compatibility layer is part of MVP-65 (`src/hunter/research_backtest_comparison/`). It validates that Hunter's deterministic backtest export parser and report builder agree with a real external Freqtrade installation on:

- `freqtrade --version`
- `freqtrade backtesting` export shape
- export schema detection
- parsed metrics

It does **not** perform or authorize any trading, dry-run trading, exchange connectivity, data download, hyperopt, plotting, RPC, webserver, scheduler, database, or queue operation.

## Runtime boundary

- MVP-65 is the sole subprocess boundary in the project. No other package imports `subprocess`.
- Permitted subprocess invocations: `freqtrade --version` and `freqtrade backtesting`.
- Forbidden subcommands: `trade`, `download-data`, `hyperopt`, `webserver`, `install-ui`, `plot-dataframe`, `plot-profit`, `lookahead-analysis`, `recursive-analysis`, `convert-trade-data`, etc. (see `_FORBIDDEN_SUBCOMMANDS` in `validator.py`).
- `subprocess.run` is always invoked with `shell=False` (default), an explicit argument list, a bounded timeout, and an allowlisted environment.
- No retry, no parallelism, no Candidate+Baseline simultaneous execution.

## External inputs

A full compatibility PASS requires both:

1. **Explicit external Freqtrade executable path** (absolute, regular file, executable, no symlink escape).
2. **Explicit external offline historical-data fixture root** (outside the repository `data/` and `reports/` directories).

Neither may be inferred automatically. If either is unavailable:

- Implementation and testing continue with deterministic synthetic fixtures.
- The system does not fabricate a real compatibility result.
- The system reports exactly: `REAL_FREQTRADE_COMPATIBILITY_NOT_EXECUTED`.
- Final Phase B result cannot be full PASS.
- The `v0.71.0-rc.1` tag is not created.

## Executable contract

`validate_executable` requires:

- explicit absolute path
- regular file
- executable permission
- accepted basename or explicit caller policy
- no unsafe symlink escape
- bounded `--version` call (argument list, `shell=False`, allowlisted environment)
- bounded stdout / stderr
- bounded timeout

## Fixture contract

See `docs/research/external_fixture_contract.md`.

## Workspace materialization

- An isolated Freqtrade-compatible workspace is created with an explicit strategy directory.
- The caller-provided strategy is copied into the workspace.
- Source strategy fingerprint is recorded **before** copy.
- Copied strategy fingerprint is recorded in the workspace.
- Source strategy fingerprint is verified **after** execution → no mutation.
- Tracked config is not mutated outside the isolated materialization.

## Runtime config

The Freqtrade runtime config contains only required valid offline-backtesting settings:

- `max_open_trades`, `stake_currency`, `stake_amount`, `tradable_balance_ratio`, `dry_run_wallet`, `fee`
- `timeframe`
- `pairlists` with only `StaticPairList`
- `exchange` with `name`, empty `key`/`secret`/`password`/`wallet`, empty `ccxt_config`/`ccxt_async_config`
- `protections`
- `user_data_dir`, `strategy`, `strategy_path`
- `dry_run=True` (Freqtrade schema key meaning backtest-only mode — NOT live dry-run trading)
- `cancel_open_orders_on_exit=False`
- `unfilledtimeout`, `entry_pricing`, `exit_pricing` (offline static pricing)

Hunter-only safety metadata (`research_only`, `human_approval_required`, `execution_approval_granted`, `production_approval_granted`, `live_trading_allowed`, `automatic_execution_allowed`) is **not** placed inside the Freqtrade config unless they are supported schema keys. It is stored in Hunter compatibility metadata (manifest, report).

No credentials. No remote pairlist plugin. No dynamic pairlist. No network-requiring configuration.

## Export discovery and parser

- Result-schema detection is explicit; the parser identifies the schema ID, strategy result, trades, and summary metrics.
- Missing metrics are distinguished from zero values.
- Multiple / ambiguous strategy results are rejected with `COMPATIBILITY_UNSUPPORTED_EXPORT_SCHEMA`.
- Unsupported schemas are rejected.
- The raw result fingerprint is preserved.
- Fallback metrics are computed from the **configured** starting balance, never a hardcoded starting balance.
- Compatibility with existing deterministic fixture schemas is retained only when unambiguous.
- Golden parser fixtures based on real result shapes are stored with sensitive/path data removed.

## Compatibility states

| State | Meaning |
|---|---|
| `COMPATIBLE` | Real executable ran, Candidate + Baseline both succeeded, both exports discovered, both schemas supported, both reports parsed, strategy/config remained immutable, no forbidden command or network path used. |
| `INCOMPATIBLE` | Real executable ran but produced incompatible exports / schemas / behavior. |
| `NOT_EXECUTED` | No real executable was run (inputs not provided). |
| `BLOCKED_INVALID_FIXTURE` | External fixture rejected (missing files, hash mismatch, path traversal, repo `data/`/`reports/` path). |
| `BLOCKED_INVALID_EXECUTABLE` | External executable rejected (missing, non-executable, symlink escape, version mismatch). |

`COMPATIBLE` is attainable only when both external inputs are provided and every check above passes.

## Supported Freqtrade version

The compatibility layer is designed against the Freqtrade backtesting export shape. When real compatibility is executed, the validated `freqtrade --version` output is recorded in the compatibility manifest. Without a real executable, no version claim is made.

## Current Phase B state

- External Freqtrade executable: **not provided**
- External offline fixture root: **not provided**
- Real compatibility result: `REAL_FREQTRADE_COMPATIBILITY_NOT_EXECUTED`
- Synthetic-fixture deterministic contracts: implemented and tested
- Methodology policies: implemented, tested, and enforced
- External fixture manifest and hash validation: implemented (Phase B.1, v0.70.2-dev)
- Real Freqtrade compatibility: established (Phase B.2, v0.71.0-rc.1) — both Candidate and Baseline no-op strategies ran real `freqtrade backtesting` against a real external Binance futures fixture; both exports parsed via `freqtrade_nested_strategy` schema
- ZIP safety hardening: implemented (v0.71.0-rc.2) — comprehensive ZIP member-level validation for encrypted members, duplicates, path traversal, symlinks, special files, excessive member count, oversized members, excessive total size, ZIP-bomb compression ratios, ambiguous JSON members, and missing expected members. See `export_parser.py:_validate_zip_and_read_member`.
- MVP-71: not started — research target met

## ZIP export safety (v0.71.0-rc.2)

The export parser validates every ZIP member before reading content:

| Check | Reason code |
|---|---|
| Encrypted member | `ZIP_ENCRYPTED_MEMBER` |
| Duplicate member name | `ZIP_DUPLICATE_MEMBER` |
| Absolute path member | `ZIP_ABSOLUTE_PATH` |
| `..` traversal | `ZIP_PATH_TRAVERSAL` |
| Backslash traversal | `ZIP_BACKSLASH_TRAVERSAL` |
| Symlink member (Unix attr) | `ZIP_SYMLINK_MEMBER` |
| Non-regular file member | `ZIP_SPECIAL_FILE_MEMBER` |
| Excessive member count (>32) | `ZIP_EXCESSIVE_MEMBER_COUNT` |
| Oversized member (>16 MiB) | `ZIP_OVERSIZED_MEMBER` |
| Excessive total size (>64 MiB) | `ZIP_EXCESSIVE_TOTAL_SIZE` |
| Suspicious compression (>50:1) | `ZIP_BOMB_SUSPECTED` |
| Missing expected member | `ZIP_MISSING_EXPECTED_MEMBER` |
| Multiple `.json` members | `ZIP_AMBIGUOUS_JSON_MEMBERS` |

The ZIP is never extracted to disk — only `zipfile.ZipFile.read()` is used to read the single validated JSON member.

## Mandatory notice

This artifact is research-only. Real Freqtrade backtesting compatibility, historical-result parsing, methodology policies, confidence intervals, and stability labels do not prove profitability and do not authorize execution, production deployment, live trading, dry-run trading, automatic execution, strategy selection, universe selection, order placement, signal generation, strategy mutation, universe mutation, or position changes. Human review remains required.