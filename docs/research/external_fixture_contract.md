# External Offline Fixture Contract

> **Research only.** The fixture contract does not authorize execution, production deployment, live trading, dry-run trading, automatic execution, strategy selection, universe selection, order placement, signal generation, strategy mutation, universe mutation, or position changes. Human review remains required.

## Purpose

An external offline fixture is a caller-provided, immutable historical-data bundle used by MVP-65 to validate that Hunter's deterministic backtest export parser agrees with a real Freqtrade installation. The fixture is **never** mutated, **never** enumerated beyond its declared files, and **never** read from the repository `data/` or `reports/` directories.

## Required manifest fields

The caller-provided fixture manifest (`ExternalFixtureManifest`) must include:

| Field | Type | Notes |
|---|---|---|
| `fixture_schema_version` | string | Schema identifier for the manifest itself. |
| `exchange` | string | Exchange identifier (e.g. `binance`, `okx`). |
| `trading_mode` | string | Spot / futures / margin. |
| `timeframe` | string | Freqtrade timeframe (e.g. `1h`, `5m`). |
| `pairs` | tuple[str, ...] | Pair list (e.g. `BTC/USDT:USDT`). |
| `timerange` | string | Freqtrade timerange string (e.g. `20240101-20240601`). |
| `candle_files` | tuple[FixtureFileRecord, ...] | One record per declared candle file. Paths are relative to the fixture root. |
| `expected_strategy_class` | string | Strategy class name the fixture is intended to run. |
| `provenance_note` | string | Free-form provenance / license / source citation. |

### `FixtureFileRecord`

| Field | Type | Notes |
|---|---|---|
| `relative_path` | str | Path relative to the fixture root. Must not contain `..`. |
| `sha256` | str | SHA-256 of the file content. |
| `size_bytes` | int | File size in bytes. |

## Invariants

1. **No mutation.** The fixture is never modified, renamed, moved, or deleted.
2. **No unrelated enumeration.** Only the declared `candle_files` are read. The validator does not list unrelated directories.
3. **Every declared file is verified.** Each `FixtureFileRecord` is opened, hashed (SHA-256), and compared with the declared `sha256`. Missing files or hash mismatches reject the fixture with `BLOCKED_INVALID_FIXTURE`.
4. **No repository `data/` or `reports/` paths.** The fixture root must be located outside the repository `data/` and `reports/` directories. Paths under either are rejected.
5. **No path traversal.** `..` in any `relative_path` is rejected. Symlink escapes are rejected.
6. **Copy into isolated workspace only.** Only the required content (declared candle files + caller strategy) is copied into the isolated Freqtrade workspace. Originals remain untouched.
7. **No network access.** Fixture validation copies bytes from disk; no network, exchange, or download operation is invoked.
8. **No retry, no parallelism.** Validation is sequential and does not retry on failure.

## Rejection reason codes

| Reason code | Trigger |
|---|---|
| `INVALID_EXTERNAL_FIXTURE` | Any fixture-validation failure (missing manifest, missing file, hash mismatch, path traversal, repo `data/`/`reports/` path). |
| `REAL_FREQTRADE_COMPATIBILITY_NOT_EXECUTED` | The compatibility smoke test did not execute because the fixture (or executable) was rejected / not provided. |

## Compatibility execution config

`CompatibilityExecutionConfig` ties together:

- the validated `ExternalFreqtradeExecutable`
- the validated `ExternalFixtureManifest`
- the caller-provided strategy path / name
- starting balance, stake, max open trades, fee, protections
- bounded timeout, allowlisted environment

`CompatibilityState` tracks the pipeline through:

```text
EXECUTABLE_VALIDATED → FIXTURE_VALIDATED → WORKSPACE_READY →
CONFIG_BUILT → STRATEGY_MATERIALIZED → CANDIDATE_EXECUTED →
CANDIDATE_PARSED → BASELINE_EXECUTED → BASELINE_PARSED →
IMMUTABILITY_VERIFIED → COMPATIBLE
```

`CompatibilityEvidence` records every fingerprint (executable, config, strategy before / after, candidate result, baseline result, raw exports, parsed reports) and the Freqtrade version string.

> **Note:** The dataclasses and state machine above (`ExternalFreqtradeExecutable`, `ExternalFixtureManifest`, `FixtureFileRecord`, `CompatibilityExecutionConfig`, `CompatibilityState`, `CompatibilityEvidence`) are **contract specifications** describing the intended fixture-validation pipeline. As of this Phase B Stage 10 closure, the implemented compatibility layer provides basic external-resource path validation (`validate_external_resources` in `compatibility_validator.py`) and the `FreqtradeCompatibilityInput` dataclass, but the full manifest model with per-file SHA-256 candle-file hash verification has **not** been implemented yet. The contract above documents the target design for when a real external fixture is supplied.

## Current Phase B state

- External offline fixture root: **not provided**
- External-resource path validation (`validate_external_resources`): implemented and tested
- Full fixture manifest with per-file SHA-256 candle-file hash verification: **not implemented** — documented contract only; deferred until an external fixture root is supplied
- Real-fixture validation: deferred until an external fixture root is supplied
- Compatibility result: `REAL_FREQTRADE_COMPATIBILITY_NOT_EXECUTED`

## Mandatory notice

This artifact is research-only. Real Freqtrade backtesting compatibility, historical-result parsing, methodology policies, confidence intervals, and stability labels do not prove profitability and do not authorize execution, production deployment, live trading, dry-run trading, automatic execution, strategy selection, universe selection, order placement, signal generation, strategy mutation, universe mutation, or position changes. Human review remains required.