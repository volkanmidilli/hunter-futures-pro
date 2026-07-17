# SPEC-066 — Research Universe Backtest Comparison Harness

**Status:** Approved
**MVP:** MVP-65
**Version target:** `v0.65.0-dev`
**Upstream dependencies:** MVP-64 `Dual Universe Builder`

## Background

MVP-64 produces a deterministic `CandidateUniverseResult` and a deterministic `BaselineUniverseResult` over the same selection window and market data. MVP-66 introduces a research-only backtest comparison harness that runs both universes through the same `freqtrade backtesting` configuration, strategy, timeframe, timerange, and execution assumptions, changing only the pairlist. The result is a paired, deterministic, research-only comparison report with canonical metrics, deltas, and fingerprints, suitable for human research review but never for execution approval or live trading.

```text
CandidateUniverseResult ───────► BacktestArmInput(CANDIDATE) ──────┐
                                                                     │
BaselineUniverseResult ─────────► BacktestArmInput(BASELINE) ────────┤
                                                                     ▼
                                                     Fairness Contract / Config
                                                                     │
                                                                     ▼
                                          Candidate workspace ──► Sequential Runner
                                          Baseline workspace  ──► (only `freqtrade backtesting`)
                                                                     │
                                                                     ▼
                                          Result Locator / Versioned Parser
                                                                     │
                                                                     ▼
                                          Paired Comparison / Canonical Metrics
                                                                     │
                                                                     ▼
                                          Deterministic Fingerprints / Writers
                                                                     │
                                                                     ▼
                                          BacktestComparisonReport + JSON/Markdown artifacts
```

## Requirements

### Must Have

- consume `CandidateUniverseResult` and `BaselineUniverseResult` from MVP-64
- deterministic frozen dataclasses for `BacktestComparisonConfig`, `BacktestArmInput`, `BacktestMetrics`, `BacktestRunResult`, `BacktestComparisonResult`, `BacktestFairnessManifest`, `BacktestComparisonManifest`, `BacktestComparisonReport`, and `ResearchBacktestSafetyFlags`
- caller-provided strategy file path and historical data directory path; read-only use with SHA-256 before/after verification
- identical strategy, timeframe, timerange, balance, stake, `max_open_trades`, fee, protections, and execution assumptions for both arms; only the pairlist may differ
- candidate and baseline run sequentially in separate repository-external temporary workspaces; only one subprocess active at a time
- only `freqtrade backtesting` is allowlisted; all other Freqtrade subcommands and modes are rejected
- `shell=False`, argument list only, no shell interpolation
- allowlisted environment (`TZ=UTC` plus a small set of research-safe variables); secret-like keys stripped
- stdout/stderr bounded (2 MiB) and redacted (secrets, absolute paths, PIDs, timestamps)
- fixed command shape: `<freqtrade> backtesting --config <temp> --userdir <temp> --strategy <name> --timeframe <tf> --timerange <tr> --export trades --export-filename <temp>`
- result containment: regular file inside the workspace; reject symlinks and path escapes
- version-aware, strict, Decimal-based parser; never scrape stdout for metrics
- canonical metrics: total return, absolute profit, final balance, max drawdown, Sharpe, Sortino, Calmar, profit factor, win rate, trade count, average trade duration, fees paid; missing metrics are `UNAVAILABLE`, never fabricated
- paired deltas as `candidate - baseline`; interpretations only `CANDIDATE_HIGHER`, `BASELINE_HIGHER`, `EQUAL`, or `UNAVAILABLE`
- zero-trade results are valid but marked as insufficient evidence
- deterministic SHA-256 fingerprints for strategy, data, pairlists, config, command, raw result, run result, comparison, fairness, and report; exclude temp paths, PID, hostname, wall-clock time, stdout/stderr
- atomic deterministic JSON/Markdown writers with silent-overwrite protection and failed-write cleanup
- workspace cleanup on success; optional retain on failure
- all public results carry: `research_only=True`, `execution_approval_granted=False`, `production_approval_granted=False`, `live_trading_allowed=False`, `automatic_execution_allowed=False`, `human_approval_required=True`

### Should Have

- configurable timeout and environment allowlist
- trade sufficiency threshold (e.g., at least one trade for any interpretation)
- structured fake Freqtrade executable for security/integration tests
- determinism tests across different temp paths and input ordering

### Won’t Have

- live or dry-run trading
- exchange/API/network data access or download
- Freqtrade `trade`, `webserver`, `hyperopt`, or any non-backtesting mode
- strategy optimization or mutation
- tracked configuration mutation
- signal/order/position/leverage/entry/exit behavior
- scheduler, database, or persistent queue
- automatic retry
- execution, production, or live-trading approval
- guaranteed-profit conclusion
- `data/` or `reports/` access
- push or remote changes

## Method

### Package Layout

```text
src/hunter/research_backtest_comparison/
├── __init__.py
├── models.py
├── errors.py
├── executable.py
├── validator.py
├── workspace.py
├── config_builder.py
├── fairness.py
├── command_builder.py
├── runner.py
├── result_locator.py
├── parser.py
├── comparison.py
├── fingerprint.py
├── engine.py
├── writer.py
└── redaction.py
```

### Architecture Flow

1. **Validation** — validate executable, strategy path, data path, config, and pairlists.
2. **Fairness Contract** — prove candidate and baseline share identical assumptions except pairlist.
3. **Ephemeral Workspace** — create separate repository-external temp workspaces for each arm.
4. **Canonical Config** — write a deterministic Freqtrade backtesting config with dry-run wallet, stake, fee, static pairlist, and protections.
5. **Allowlisted Command** — build the fixed argument list and verify it contains only `backtesting`.
6. **Sequential Runner** — run candidate, then baseline, each with `subprocess.run(shell=False, env=allowlisted, timeout=...)`.
7. **Strategy Mutation Check** — compare SHA-256 of strategy file before/after each run.
8. **Result Locator** — confirm the export file is a regular file inside the workspace.
9. **Versioned Parser** — parse the structured JSON export file into `BacktestMetrics`.
10. **Comparison** — compute deltas and interpretations for each canonical metric.
11. **Fingerprints** — compute deterministic fingerprints excluding all ephemeral data.
12. **Writer** — atomically write JSON and Markdown artifacts with safety notices.

### Core Rules

- The executable is validated only with `<freqtrade> --version`.
- The strategy is never imported by Hunter; its SHA-256 is checked before and after the run.
- Historical data is an explicit read-only reference; no crawling or download.
- Candidate and baseline use separate repository-external workspaces.
- Config is allowlisted and temporary.
- Environment is allowlisted; secrets are excluded; `TZ=UTC` is forced.
- Result must be a regular file inside the workspace; symlink/path escape is rejected.
- Parser is version-aware, strict, Decimal-based, and never scrapes stdout.
- Delta is `candidate - baseline`.
- Interpretation is only `CANDIDATE_HIGHER`, `BASELINE_HIGHER`, `EQUAL`, or `UNAVAILABLE`.
- Zero-trade is valid but insufficient evidence.
- Fingerprints exclude temp paths, PID, hostname, wall-clock time, stdout/stderr.
- Writers are canonical, deterministic, atomic, redacted, and overwrite-safe.

## Safety Invariants

All public artifacts carry hard-coded research-only flags:

- `research_only=True`
- `execution_approval_granted=False`
- `production_approval_granted=False`
- `live_trading_allowed=False`
- `automatic_execution_allowed=False`
- `human_approval_required=True`
- `no_network_connection=True`
- `no_database_connection=True`
- `no_exchange_connection=True`
- `no_automatic_config_mutation=True`
- `no_action_commands_emitted=True`
- `no_open_interest_synthesis=True`
- `no_remote_changes=True`
- `no_freqtrade_runtime_connection=False` (because this MVP legitimately runs `freqtrade backtesting` as a subprocess)

## Acceptance Criteria

- `python -m pytest tests/test_research_backtest_comparison/` passes.
- Full suite passes with no new failures.
- Forbidden subcommands (`trade`, `webserver`, `hyperopt`) are rejected.
- Shell injection and secret leakage are impossible.
- Strategy mutation between before/after SHA-256 fails closed.
- Result containment rejects symlinks and path escapes.
- Fingerprints are deterministic across different temp paths and input ordering.
- Artifacts are redacted, atomic, and overwrite-safe.
- No `data/` or `reports/` access, no live/dry-run trading, no tracked config/strategy mutation, no push, no remote changes.

## Closure

- Version bumped to `0.65.0-dev` in `VERSION`, `pyproject.toml`, `src/hunter/__init__.py`.
- `docs/MVP_INDEX.md` and `CHANGELOG.md` updated.
- Local annotated tag `v0.65.0-dev` created.
- No push performed.
- No execution, production, live-trading, or automatic-execution approval created.
