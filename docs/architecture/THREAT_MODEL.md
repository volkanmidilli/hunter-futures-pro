# Threat Model — v0.71.0-rc.2

> **Research only.** This threat model describes the security posture of the Hunter Futures Pro v0.71.0-rc.2 framework. It does not authorize execution, production deployment, live trading, dry-run trading, automatic execution, strategy selection, universe selection, order placement, signal generation, strategy mutation, universe mutation, or position changes. Human review remains required.

## 1. Protected Assets

| Asset | Sensitivity | Exposure |
|---|---|---|
| Research pipeline source code | Integrity | File-system access controlled |
| External fixture files (caller-provided) | Integrity, immutability | Read-only, SHA-256 validated |
| Freqtrade backtest exports (ZIP) | Integrity, containment | Validated before parse |
| Safety-flag dataclass invariants | Integrity | Immutable — raises ValueError on violation |
| Allowlisted subprocess environment | Confidentiality | Secret patterns stripped |
| Strategy source fingerprints | Integrity | SHA-256 before/after verification |
| Workspace temporary directories | Confidentiality | Ephemeral, isolated outside repo |
| Git repository history and tags | Integrity, availability | Local-only, no push |

## 2. Trust Boundaries

```
┌──────────────────────────────────────────────────────────────┐
│  Hunter Research Framework (trusted code)                    │
│                                                              │
│  ┌─────────────┐    ┌──────────────┐    ┌─────────────────┐ │
│  │ Fixture      │───▶│ Workspace    │───▶│ Freqtrade       │ │
│  │ Validator    │    │ Materializer │    │ Config Builder  │ │
│  └─────────────┘    └──────────────┘    └─────────────────┘ │
│         │                                       │            │
│         ▼                                       ▼            │
│  ┌─────────────┐                      ┌───────────────────┐ │
│  │ Fixture     │                      │ Backtest Runner   │ │
│  │ Manifest    │                      │ (sole subprocess) │ │
│  └─────────────┘                      └───────────────────┘ │
│                                                │             │
├────────────────────────────────────────────────┤─────────────┤
│                                                ▼             │
│              External Freqtrade Executable                   │
│              (outside trust boundary — validated              │
│              via --version probe before use)                  │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ Freqtrade backtest workspace (ephemeral)                │ │
│  │  ┌──────────────┐   ┌──────────────┐                    │ │
│  │  │ Isolated     │   │ Results dir  │                    │ │
│  │  │ data dir     │   │ (.zip export)│                    │ │
│  │  └──────────────┘   └──────────────┘                    │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ ZIP Export Parser (defense-in-depth validation)         │ │
│  │  → Rejects traversal, symlinks, encrypted, bombs       │ │
│  │  → Reads single validated member (never extracts)      │ │
│  └─────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

**Key boundaries:**
- **External fixture → Hunter:** Untrusted. All fixture files SHA-256 validated against caller-provided manifest. Path containment and symlink rejection enforced.
- **External Freqtrade executable → Hunter:** Untrusted beyond verification probe. Executable name allowed, path contained, symlink rejected. No elevated permissions.
- **Freqtrade workspace → Hunter:** Partially trusted. ZIP exports validated for all known ZIP threats before parsing.
- **Hunter → Network/Exchange:** Disconnected. No network client, no exchange connection, no data download. Source scans verify this.

## 3. External Fixture Trust

- Caller provides immutable fixture root + manifest with per-file SHA-256 hashes.
- Hunter never enumerates undeclared files (strict mode) or tolerates them (non-strict mode).
- SHA-256 verified with bounded reads (64 KiB chunks, 256 MiB max per file).
- Fixture root must not reside under repository `data/` or `reports/`.
- Path traversal (`..`), symlinks, and absolute paths rejected.
- Fixture files are copied (never mutated) into an isolated workspace for Freqtrade.

## 4. Executable Trust

- Executable path: absolute, regular file, executable permissions, no symlink.
- Basename must be `freqtrade` (or `freqtrade.exe`) — explicit policy.
- `--version` probe runs with allowlisted environment, bounded timeout, bounded output.
- Executable not chrooted or sandboxed beyond the above — trusted only to run `freqtrade backtesting`.
- No persistent modification of the system by the executable is expected.

## 5. Subprocess Isolation

- **Sole boundary:** MVP-65 (`research_backtest_comparison/runner.py` + `executable.py`).
- `subprocess.run()` with `shell=False`, argument list, bounded timeout, allowlisted environment.
- Only `freqtrade backtesting` permitted at runtime (validator rejects all other subcommands).
- Candidate and Baseline run sequentially — no parallel subprocesses, no retry.
- Strategy file SHA-256 verified unchanged after execution (mutation detection).

## 6. Allowlisted Environment

- Default allowlist: `TZ`, `PATH`, `HOME`, `USER`, `LANG`, `LC_ALL`, `PYTHONNOUSERSITE`, `PYTHONPATH`, `TERM`, `COLORTERM`.
- Secret patterns stripped: `API_KEY`, `API_SECRET`, `SECRET`, `PASSWORD`, `TOKEN`, `PRIVATE_KEY`, `ACCESS_KEY`, `ACCESS_SECRET`.
- `TZ` forced to UTC for reproducibility.
- Defense-in-depth: keys containing secret-like patterns removed even after allowlist filtering.

## 7. Temporary Workspace Containment

- Workspace created outside the repository tree (default `/tmp`).
- Isolated `userdir/`, `data/`, `backtest_results/`, `config.json`.
- Cleanup on success; retention on failure configurable.
- Result files validated for symlink rejection, path containment, bare filenames only (no directory traversal from `.last_result.json` pointer).

## 8. ZIP Threats

Defense-in-depth ZIP validation in `export_parser._validate_zip_and_read_member`:

| Threat | Mitigation |
|---|---|
| Encrypted ZIP members | `flag_bits & 0x1` check → `ZIP_ENCRYPTED_MEMBER` |
| Duplicate member names | Name set deduplication → `ZIP_DUPLICATE_MEMBER` |
| Absolute-path members | `os.path.isabs()` check → `ZIP_ABSOLUTE_PATH` |
| `..` traversal in names | Split on `/` + `..` detection → `ZIP_PATH_TRAVERSAL` |
| Backslash traversal | `\\` + `..` after normalization → `ZIP_BACKSLASH_TRAVERSAL` |
| Symlink members (Unix attr) | `S_ISLNK(mode)` on external_attr → `ZIP_SYMLINK_MEMBER` |
| Special-file members | `S_ISREG(mode)` check → `ZIP_SPECIAL_FILE_MEMBER` |
| Excessive member count | `len(infos) > 32` → `ZIP_EXCESSIVE_MEMBER_COUNT` |
| Oversized member | `file_size > 16 MiB` → `ZIP_OVERSIZED_MEMBER` |
| Excessive total size | Cumulative `file_size > 64 MiB` → `ZIP_EXCESSIVE_TOTAL_SIZE` |
| ZIP bomb (compression ratio) | `uncompressed / compressed > 50:1` → `ZIP_BOMB_SUSPECTED` |
| Ambiguous JSON members | Exactly one `.json` member → `ZIP_AMBIGUOUS_JSON_MEMBERS` |
| Missing expected member | Expected name in `namelist()` → `ZIP_MISSING_EXPECTED_MEMBER` |

**Never extracts to disk** — uses `ZipFile.read()` only. Reads a single validated member.

## 9. Resource Exhaustion

| Resource | Limit | Mechanism |
|---|---|---|
| Fixture file size | 256 MiB | `_MAX_FIXTURE_FILE_BYTES` in `fixture_validator.py` |
| ZIP member size | 16 MiB | `_ZIP_MAX_SINGLE_MEMBER_BYTES` |
| ZIP total uncompressed | 64 MiB | `_ZIP_MAX_TOTAL_UNCOMPRESSED_BYTES` |
| ZIP member count | 32 | `_ZIP_MAX_MEMBER_COUNT` |
| Subprocess output | 2 MiB | `_MAX_OUTPUT_BYTES` in `runner.py` |
| Subprocess timeout | Configurable | `config.timeout_seconds` |
| Executable probe timeout | 60 s default | `validate_executable(timeout_seconds=...)` |

## 10. Symlink and Path Traversal

- Fixture root: resolved path checked for containment; symlinks in fixture file paths rejected.
- Executable path: symlinks rejected unless `allow_symlink=True` (default `False`).
- ZIP members: path traversal detected via `..`, backslash variants, absolute paths.
- Result file: `.last_result.json` pointer restricted to bare filenames; result file symlinks rejected.
- Workspace result: full `locate_result_file()` containment check with symlink detection before `resolve()`.

## 11. Secret Leakage

- No API keys, exchange secrets, or credentials in the repository.
- Freqtrade config emitted with empty `key`/`secret`/`password`/`wallet`.
- Subprocess environment: secret-like keys stripped even from allowlist.
- Redacted stdout/stderr (pattern-based `redact_text()`).
- No telemetry, no network client, no log upload, no remote reporting.

## 12. Immutable Safety Flags

All safety-flag dataclasses enforce:

```text
research_only=True
execution_approval_granted=False
production_approval_granted=False
live_trading_allowed=False
automatic_execution_allowed=False
human_approval_required=True
```

Construction with a violating value raises `ValueError`. Source scans verify these flags are never toggled.

## 13. Prohibited Trading Paths

Source scans verify:

- No `trade` subcommand construction in `command_builder.py`.
- No `download-data`, `hyperopt`, `webserver`, `install-ui`, `plot-dataframe`, `plot-profit`, `lookahead-analysis`, `recursive-analysis`, `convert-trade-data`.
- No network client (`ccxt`, `requests`, `urllib`, `http.client`, `AsyncClient`, `FTXClient`).
- No retry (`tenacity`, `retry` decorator, `sleep`+loop patterns).
- No parallel execution (`concurrent.futures`, `asyncio.gather`, `multiprocessing.Process`).
- No scheduler (`APScheduler`, `celery`, `schedule`, `cron`).
- No database (`redis`, `psycopg`, `sqlite3.connect`, `BrokerConnection`).
- No queue (`kafka`, `pika`, `amqp`, `stomp`).

## 14. Residual Risks

| Risk | Severity | Mitigation | Residual |
|---|---|---|---|
| Freqtrade executable compromise | High | Executable validated (absolute path, regular file, no symlink, correct basename, --version probe) | Executable runs with current user privileges — no sandbox/jail |
| ZIP parsing vulnerability in Python stdlib | Low | ZIP never extracted; single member read; comprehensive pre-read validation | Python stdlib `zipfile` is assumed correct |
| Temporary workspace data leakage | Low | Ephemeral workspaces outside repo tree; cleanup on success | Failure-retained workspaces persist until manual cleanup |
| Deeply nested ZIP structures | Low | Member name `..` and backslash traversal rejected | Theoretical — no known bypass |
| Resource exhaustion via many small valid ZIPs | Low | Member count capped at 32 per archive | Repeated invocation by caller could cumulatively exhaust — not defended |
| Stale documentation misdirection | Medium | All operational docs updated in v0.71.0-rc.2 | Human operators may not read docs |

## 15. Operator Responsibilities

- Provide genuine, SHA-256-validated external fixture with manifest.
- Provide genuine Freqtrade executable from a trusted source.
- Verify executable version output matches expectations (`freqtrade --version`).
- Never place fixture data under repository `data/` or `reports/`.
- Review all research outputs — the system is research-only and does not authorize any execution.
- Do not interpret zero-trade compatibility results as profitability evidence.
- Do not enable live/dry-run trading based on this framework.
- Keep the repository local — no push, no remote modification.

---

**v0.71.0-rc.2 remains research-only.** Completion does not authorize execution, production deployment, live trading, dry-run trading, automatic execution, strategy selection, universe selection, order placement, signal generation, strategy mutation, universe mutation, or position changes.
