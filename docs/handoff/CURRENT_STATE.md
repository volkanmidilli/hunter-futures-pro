# Current State

Hunter Futures Pro

## Version

0.50.0-dev

## Current Phase

The functional MVP chain now runs through **MVP-50 / v0.50.0-dev**, which is complete and pending tag. SPEC-051 was committed at the end of the MVP-50 implementation cycle. The latest tag is `v0.49.0-dev` at `eff7c93`; the next tag `v0.50.0-dev` is pending at the next commit/tag step. The next required action is **MVP-51 selection and planning**; no SPEC-052 exists yet.

## Background

### Original Master Plan (Historical)

The original plan captured in `PROJECT.md`, `README.md`, and `tasks/backlog.md` defined a focused progression:

- MVP-0 — Project Foundation
- MVP-1 — Data Foundation
- MVP-2 — Market State (Regime Engine, Market Breadth Engine)
- MVP-3 — Strength and Futures Positioning (Relative Strength, Open Interest)
- MVP-4 — Execution Control (Portfolio Engine, Decision Gate Engine, Freqtrade integration)

`PROJECT.md` listed 12 intended main modules: Data Foundation, Regime Engine, Market Breadth Engine, Relative Strength Engine, Open Interest Engine, Discovery Engine, Portfolio Engine, Decision Gate Engine, Backtest Validation Engine, Reporting Layer, Freqtrade Execution Layer, and Agent Memory Layer. All 12 modules are implemented across the expanded MVP chain.

### Expanded MVP Chain

The repository now contains 48 specs (SPEC-001 through SPEC-048). MVPs beyond the original plan:

- MVP-5 through MVP-9: Freqtrade execution contract chain
- MVP-10 through MVP-23: Local research audit / review chain
- MVP-24 through MVP-28: Quantitative research engines
- MVP-29 through MVP-32: Reporting / orchestration / ledger
- MVP-33 through MVP-39: Remediation / release-hardening chain
- MVP-40 through MVP-42: Human review chain
- MVP-43 through MVP-45: Audit bundle / export / verification
- MVP-46: Project Memory Realignment (documentation-only, complete)
- MVP-47: Cross-Artifact Consistency Engine (complete, tagged v0.47.0-dev)
- MVP-48: Research Audit Aggregate Health Report (complete, tagged v0.48.0-dev)
- MVP-49: Research Audit Health Remediation Bridge (complete, tagged v0.49.0-dev at eff7c93)

For the full MVP-by-MVP mapping, see `ROADMAP.md` and `docs/MVP_INDEX.md`.

## Current Status

MVP-49 — Research Audit Health Remediation Bridge is complete and tagged `v0.49.0-dev` at `eff7c93`. Finalization committed at `eff7c93`. SPEC-050 at `6806aa9`; implementation at `1a4c7b2`.

- SPEC-050: `specs/SPEC-050-Research-Audit-Health-Remediation-Bridge.md` — committed at `6806aa9`.
- `src/hunter/research_audit_health_remediation/__init__.py` — public API exports for models, engine, writer, and default paths.
- `src/hunter/research_audit_health_remediation/models.py` — frozen dataclasses (`RemediationBridgeConfig`, `RemediationBridgeDataQuality`, `RemediationBridgeReport`), reason codes, and validation.
- `src/hunter/research_audit_health_remediation/mapping.py` — default severity, priority, item-type, and reason-code mapping tables.
- `src/hunter/research_audit_health_remediation/engine.py` — pure local deterministic bridge engine with finding-to-item mapping, stable item IDs, deduplication, forbidden-term scanning, and data-quality counters.
- `src/hunter/research_audit_health_remediation/writer.py` — deterministic dict/JSON/CSV/Markdown serialization and atomic writes.
- `tests/test_research_audit_health_remediation/test_models.py` — model tests.
- `tests/test_research_audit_health_remediation/test_engine.py` — engine tests.
- `tests/test_research_audit_health_remediation/test_writer.py` — writer tests.
- `tests/test_research_audit_health_remediation/test_integration.py` — integration tests.
- 60 research_audit_health_remediation tests total.
- Full suite: 7680 tests passing, 1 skipped using `pytest -q` (default import mode).
- Safety: local, call-triggered, audit-only bridge engine over caller-provided in-memory `HealthReport` findings; not a production release approval system, not a certification of trading readiness, not a trading signal, not a recommendation, not a strategy selector, and not an execution/portfolio/universe approval gate; artifact refs and paths are opaque strings and are never opened, traversed, validated, fetched, or executed; no `data/` or `reports/` inspection; no Freqtrade input, no Binance/exchange/API/live data, no order/execution/action commands, no leverage/shorting, no feedback into execution/strategy/portfolio paths; no scheduler, daemon, background job runner, server, REST API, database, Web UI, or dashboard introduced.
- Current supported entry: `build_health_remediation_bridge_report(report, config)` public API; writer helpers available for dict/JSON/CSV/Markdown strings and optional atomic file writes.
- Latest implementation commit: `1a4c7b2`; SPEC commit: `6806aa9`; Step 4 finalization commit: `eff7c93`.
- Tag: `v0.49.0-dev` at `eff7c93`.
- Next phase: MVP-50 selection and planning.

MVP-48 — Research Audit Aggregate Health Report is complete and tagged v0.48.0-dev at commit `779692f`.

- SPEC-049: `specs/SPEC-049-Research-Audit-Aggregate-Health-Report.md` — implemented.
- `src/hunter/research_audit_health/__init__.py` — public API exports for models, engine, writer, reason codes, safety constants, and default allowed families.
- `src/hunter/research_audit_health/models.py` — frozen dataclasses, enums, reason codes, data-quality counters, and forbidden-term guard.
- `src/hunter/research_audit_health/engine.py` — pure local aggregate health engine with deterministic scoring, findings, and safety flags.
- `src/hunter/research_audit_health/writer.py` — deterministic dict/JSON/Markdown serialization and forbidden-phrase output guard.
- `tests/test_research_audit_health/test_models.py` — model tests.
- `tests/test_research_audit_health/test_engine.py` — engine tests.
- `tests/test_research_audit_health/test_writer.py` — writer tests.
- `tests/test_research_audit_health/test_integration.py` — integration tests.
- 79 research_audit_health tests total.
- Full suite: 7620 tests passing, 1 skipped using `pytest --import-mode=importlib`.
- Safety: local, call-triggered, audit-only aggregate health engine over caller-provided in-memory artifact summaries, metadata, and opaque refs; not a production release approval system, not a certification of trading readiness, not a trading signal, not a recommendation, not a strategy selector, and not an execution/portfolio/universe approval gate; refs and paths are opaque strings and are never opened, traversed, validated, fetched, or executed; no `data/` or `reports/` inspection; no Freqtrade input, no Binance/exchange/API/live data, no order/execution/action commands, no leverage/shorting, no feedback into execution/strategy/portfolio paths; no scheduler, daemon, background job runner, server, REST API, database, Web UI, or dashboard introduced.
- Current supported entry: `evaluate_research_audit_health(input, config)` public API; callable only from local code/tests, no standalone runner added.
- [SUPERSEDED — MVP-49 is complete; see above.]

MVP-47 — Cross-Artifact Consistency Engine is complete and tagged v0.47.0-dev at commit `6103b95`.

Latest tagged commit: `779692f` (tag: v0.48.0-dev).
Latest MVP-48 commits:
- `ec463ff` Add MVP-48 research audit health report spec
- `779692f` Implement MVP-48 research audit health report
- SPEC-048: `specs/SPEC-048-Cross-Artifact-Consistency-Engine.md` — implemented.
- `src/hunter/cross_artifact_consistency/__init__.py` — public API exports for models, engine, writer, reason codes, safety constants, and default artifact paths.
- `src/hunter/cross_artifact_consistency/models.py` — frozen dataclasses (`CrossArtifactConsistencyInput`, `ConsistencyCheck`, `ConsistencyCheckResult`, `ArtifactRef`, `ConsistencyRule`, `ConsistencyReport`, `ConsistencyReportConfig`, `CrossArtifactConsistency`), enums (`ConsistencyCheckState`, `ConsistencySeverity`, `ConsistencyReasonCode`), reason codes, check kinds, and forbidden-content guard.
- `src/hunter/cross_artifact_consistency/engine.py` — pure local cross-artifact consistency engine with input validation, rule normalization, per-rule checks, severity aggregation, reason-code assignment, and report building.
- `src/hunter/cross_artifact_consistency/writer.py` — deterministic JSON/Markdown serialization and atomic writes for `CrossArtifactConsistencyReport`.
- `tests/test_cross_artifact_consistency/test_models.py` — model tests.
- `tests/test_cross_artifact_consistency/test_engine.py` — engine tests.
- `tests/test_cross_artifact_consistency/test_writer.py` — writer tests.
- `tests/test_cross_artifact_consistency/test_integration.py` — integration tests.
- 86 cross_artifact_consistency tests total.
- Full suite: 7620 tests passing, 1 skipped using `pytest --import-mode=importlib`.
- Safety: local, call-triggered, audit-only consistency engine over caller-provided in-memory artifact refs, rule definitions, and check results; not a production release approval system, not a certification of trading readiness, not a trading signal, not a recommendation, not a strategy selector, and not an execution/portfolio/universe approval gate; artifact refs are opaque strings and are not opened, traversed, validated, fetched, or executed; no Freqtrade input, no Binance/exchange/API/live data, no order/execution/action commands, no leverage/shorting, no feedback into execution/strategy/portfolio paths; no scheduler, daemon, background job runner, server, REST API, database, Web UI, or dashboard introduced.
- Current supported entry: `build_cross_artifact_consistency_report(input, config)` public API; callable only from local code/tests, no standalone runner added.
- Next phase: MVP-48 selection and planning. No SPEC exists yet.

MVP-31 — Local Research Experiment Ledger is complete.
- SPEC-032: `specs/SPEC-032-Local-Research-Experiment-Ledger.md` — implemented.
- `src/hunter/experiment_ledger/__init__.py` — public API exports for models, engine, writer, reason codes, and safety constants.
- `src/hunter/experiment_ledger/models.py` — frozen dataclasses, enums, reason codes, and forbidden-term guard.
- `src/hunter/experiment_ledger/engine.py` — pure local experiment ledger engine with deterministic normalization, comparison, baseline deltas, ranking, and data quality.
- `src/hunter/experiment_ledger/writer.py` — deterministic JSON/CSV/Markdown serialization and atomic writes for `ExperimentLedgerReport`.
- `tests/test_experiment_ledger/test_models.py` — model tests.
- `tests/test_experiment_ledger/test_engine.py` — engine tests.
- `tests/test_experiment_ledger/test_writer.py` — writer tests.
- `tests/test_experiment_ledger/test_integration.py` — integration tests.
- 138 experiment_ledger tests total.
- Full suite: 5629 tests passing, 1 skipped using `pytest --import-mode=importlib`.
- Safety: local, call-triggered, audit-only normalizer; no scheduler, daemon, background job runner, server, REST API, database, Web UI, or dashboard; no Freqtrade input, no Binance/exchange/API/live data, no order/execution/action commands, no leverage/shorting, no feedback into execution/strategy/portfolio paths; rankings are audit-review ordering only, not recommendations or signals; file references and metadata strings not traversed/opened/followed/validated/executed.
- Current supported entry: `build_experiment_ledger_report(input, config)` public API; callable only from local code/tests, no standalone runner added.
- Next phase: not started; requires human direction.

MVP-30 — Local Research Run Orchestrator is complete.
- SPEC-031: `specs/SPEC-031-Local-Research-Run-Orchestrator.md` — implemented.
- `src/hunter/run_orchestrator/__init__.py` — public API exports for models, engine, writer, reason codes, and safety constants.
- `src/hunter/run_orchestrator/models.py` — frozen dataclasses, enums, reason codes, and forbidden-term guard.
- `src/hunter/run_orchestrator/engine.py` — pure call-triggered orchestration engine with plan validation, fail-closed dispatch, deterministic aggregation, safety flags, and reason codes.
- `src/hunter/run_orchestrator/writer.py` — deterministic JSON/CSV/Markdown serialization and atomic writes for `ResearchRunResult`.
- `tests/test_run_orchestrator/test_models.py` — model tests.
- `tests/test_run_orchestrator/test_engine.py` — engine tests.
- `tests/test_run_orchestrator/test_writer.py` — writer tests.
- `tests/test_run_orchestrator/test_integration.py` — integration tests.
- 86 run_orchestrator tests total.
- Full suite: 5491 tests passing, 1 skipped using `pytest --import-mode=importlib`.
- Safety: local, call-triggered, audit-only coordinator; no scheduler, daemon, background job runner, server, REST API, database, Web UI, or dashboard; no Freqtrade input, no Binance/exchange/API/live data, no order/execution/action commands, no leverage/shorting, no feedback into execution/strategy/portfolio paths; file references and metadata strings not traversed/opened/followed/validated/executed.
- Current supported entry: `build_research_run_result(plan, config)` public API; callable only from local code/tests, no standalone runner added.
- Next phase: not started; requires human direction.

MVP-29 — Local Research Reporting CLI is complete.
- SPEC-030: `specs/SPEC-030-Local-Research-Reporting-CLI.md` — implemented.
- `src/hunter/reporting_cli/__init__.py` — public API exports including `main`, command runners, constants, and models.
- `src/hunter/reporting_cli/models.py` — frozen dataclasses, enums, `REPORTING_CLI_REASON_CODES`, `CLIExitCode`, `CLIOutputFormat`, `CLICommandKind`, `CLISafetyFlags`, `CLIArtifactSummary`, `CLIInvocation`, `CLICommandResult`.
- `src/hunter/reporting_cli/commands.py` — pure deterministic command functions: `run_version_command`, `run_safety_summary_command`, `run_list_artifacts_command`, `run_validate_artifact_paths_command`, `run_render_sample_command`, `dispatch_command`.
- `src/hunter/reporting_cli/cli.py` — thin callable entry wrapper `main(argv)` with argument parsing, help text, and exit-code dispatch.
- `tests/test_reporting_cli/test_models.py` — model tests.
- `tests/test_reporting_cli/test_commands.py` — command tests.
- `tests/test_reporting_cli/test_cli.py` — CLI entry tests.
- `tests/test_reporting_cli/test_integration.py` — integration tests.
- 106 reporting_cli tests total.
- Full suite: 5405 tests passing, 1 skipped using `pytest --import-mode=importlib`.
- Safety: human-audit / research-only artifact only, not a trading signal, not trade approval, not strategy approval, not execution approval, not portfolio approval, not universe approval, and not Freqtrade input; no Freqtrade input, no Binance/exchange/API/live data, no order/execution/action commands, no leverage/shorting, no feedback into execution/strategy/portfolio paths, file references and metadata strings not traversed/opened/followed/validated/executed, commands do not read input files.
- Current supported entry: callable `main(argv)` API; no `__main__.py` or console script entry has been added.
- Commands supported: `version`, `safety-summary`, `list-artifacts`, `validate-artifact-paths`, `render-sample`.
- Output formats: `TEXT`, `JSON`, `MARKDOWN` (for `safety-summary`).
- Default outputs (render-sample): `data/reporting_cli/samples/`.
- Next phase: not started; requires human direction.

MVP-28 — Local Research Backtesting Engine is complete. [SUPERSEDED]
- SPEC-029: `specs/SPEC-029-Local-Research-Backtesting-Engine.md` — implemented.
- `src/hunter/backtest/__init__.py` — public API exports including engine and writer functions and constants.
- `src/hunter/backtest/models.py` — frozen dataclasses, enums, reason-code partitions, `FORBIDDEN_BACKTEST_TERMS`, `BacktestState`, `BacktestAllocationMode`, `BacktestInputKind`, `BacktestPriceBar`, `BacktestCandidateDecision`, `BacktestInput`, `BacktestRunConfig`, `BacktestPortfolioSnapshot`, `BacktestCandidateResult`, `BacktestPortfolioResult`, `BacktestDataQuality`, `BacktestSafetyFlags`, `BacktestReport`.
- `src/hunter/backtest/engine.py` — pure local backtest engine: safety flags, forbidden-content detection, config validation, candidate classification, period returns, candidate-level metrics, simulated weights for `EQUAL_WEIGHT`/`RESEARCH_WEIGHT`/`CUSTOM_WEIGHT`, portfolio equity curve from union of included/capped timestamps with no carry-forward, missing bars contributing zero, portfolio-level metrics from equity curve, data quality, and fail-closed report construction.
- `src/hunter/backtest/writer.py` — deterministic JSON, CSV, Markdown serialization and atomic writers.
- `tests/test_backtest/test_models.py` — model tests.
- `tests/test_backtest/test_engine.py` — engine tests.
- `tests/test_backtest/test_writer.py` — writer tests.
- `tests/test_backtest/test_integration.py` — integration tests.
- 121 backtest tests total.
- Full suite: 5299 tests passing, 1 skipped using `pytest --import-mode=importlib`.
- Safety: human-audit / research-only artifact only, not a trading signal, not trade approval, not strategy approval, not execution approval, not portfolio approval, and not Freqtrade input; no Freqtrade input, no Binance/exchange/API/live data, no order/execution/action commands, no leverage/shorting, no feedback into execution/strategy/portfolio paths, file references and metadata strings not traversed/opened/followed/validated/executed, writer does not read input files.
- Default outputs:
  - `data/backtest/latest_backtest_report.json`
  - `data/backtest/latest_backtest_results.csv`
  - `reports/backtest/latest_backtest_report.md`
- Next phase: not started; requires human direction.

MVP-27 — Portfolio Construction Engine is complete. [SUPERSEDED]
- SPEC-028: `specs/SPEC-028-Portfolio-Construction-Engine.md` — implemented.
- `src/hunter/portfolio_construction/__init__.py` — public API exports including engine and writer functions and constants.
- `src/hunter/portfolio_construction/models.py` — frozen dataclasses, enums, reason-code partitions, `FORBIDDEN_PORTFOLIO_CONSTRUCTION_TERMS`, `PortfolioConstructionConfig`, `PortfolioConstructionSafetyFlags`, `PortfolioConstructionState`, `PortfolioConstructionClassification`, `PortfolioConstructionInputKind`, `PortfolioDiscoverySummary`, `PortfolioConstructionInput`, `PortfolioConstructionScore`, `PortfolioConstructionDataQuality`, `PortfolioConstructionUniverseSummary`, `PortfolioConstructionReport`.
- `src/hunter/portfolio_construction/engine.py` — pure local portfolio construction engine: safety flags, forbidden-content detection, discovery sub-scoring, data quality, diversification, cap readiness, filter bonus, allocation score, initial research weights, weight caps with redistribution, classification, universe summary, and fail-closed report construction.
- `src/hunter/portfolio_construction/writer.py` — deterministic JSON, CSV, Markdown serialization and atomic writers.
- `tests/test_portfolio_construction/test_models.py` — model tests.
- `tests/test_portfolio_construction/test_engine.py` — engine tests.
- `tests/test_portfolio_construction/test_writer.py` — writer tests.
- `tests/test_portfolio_construction/test_integration.py` — integration tests.
- 158 portfolio_construction tests total.
- Full suite: 5178 tests passing, 1 skipped using `pytest --import-mode=importlib`.
- Safety: human-audit / research-only artifact only, not a trading signal, not trade approval, not strategy approval, not execution approval, not portfolio/universe approval, and not position sizing; no Freqtrade input, no Binance/exchange/API/live data, no order/execution/action commands, no leverage/shorting, no feedback into execution/strategy/portfolio paths, file references and metadata strings not traversed/opened/followed/validated/executed, writer does not read input files.
- Default outputs:
  - `data/portfolio_construction/latest_portfolio_construction_report.json`
  - `data/portfolio_construction/latest_portfolio_construction_allocations.csv`
  - `reports/portfolio_construction/latest_portfolio_construction_report.md`
- Next phase: not started; requires human direction.

MVP-26 — Discovery Engine is complete.
- SPEC-027: `specs/SPEC-027-Discovery-Engine.md` — implemented.
- `src/hunter/discovery/__init__.py` — public API exports including engine and writer functions.
- `src/hunter/discovery/models.py` — frozen dataclasses, enums, reason-code partitions, `FORBIDDEN_DISCOVERY_TERMS`, `DiscoveryConfig`, `DiscoverySafetyFlags`, `DiscoveryState`, `DiscoveryClassification`, `DiscoveryInputKind`, `DiscoveryRelativeStrengthSummary`, `DiscoveryOpenInterestSummary`, `DiscoveryInput`, `DiscoveryScore`, `DiscoveryUniverseSummary`, `DiscoveryDataQuality`, `DiscoveryCandidate`, `DiscoveryReport`.
- `src/hunter/discovery/engine.py` — pure local combination engine: aggregates already-loaded Relative Strength and Open Interest summaries, computes alignment, data quality, filter bonus, and weighted 0–100 discovery score, classifies candidates, builds universe summary, and constructs safety flags.
- `src/hunter/discovery/writer.py` — deterministic JSON, CSV, Markdown serialization and atomic writers.
- `tests/test_discovery/test_models.py` — model tests.
- `tests/test_discovery/test_engine.py` — engine tests.
- `tests/test_discovery/test_writer.py` — writer tests.
- `tests/test_discovery/test_integration.py` — integration tests.
- 185 discovery tests total.
- Full suite: 5020 tests passing, 1 skipped using `pytest --import-mode=importlib`.
- Safety: human-audit / research-only artifact only, not a trading signal, not trade approval, not strategy approval, not execution approval, not portfolio/universe approval, no Freqtrade input, no Binance/exchange/API/live data, no order/execution/action commands, no leverage/shorting, no feedback into execution/strategy/portfolio paths, file references and metadata strings not traversed/opened/followed/validated/executed, writer does not read input files.
- Default outputs:
  - `data/discovery/latest_discovery_report.json`
  - `data/discovery/latest_discovery_candidates.csv`
  - `reports/discovery/latest_discovery_report.md`
- Next step: Portfolio Construction planning only; implementation not started.

MVP-25 — Open Interest Engine is complete.
- SPEC-026: `specs/SPEC-026-Open-Interest-Engine.md` — implemented.
- `src/hunter/open_interest/__init__.py` — public API exports.
- `src/hunter/open_interest/models.py` — frozen dataclasses, enums, reason-code partitions, `FORBIDDEN_OPEN_INTEREST_TERMS`, `OpenInterestConfig`, `OpenInterestSafetyFlags`, `OpenInterestState`, `OpenInterestPositioning`, `OpenInterestTrend`, `OpenInterestFundingContext`, `OpenInterestObservation`, `OpenInterestInput`, `OpenInterestPeriodChange`, `OpenInterestScore`, `OpenInterestDataQuality`, `OpenInterestUniverseSummary`, `OpenInterestReport`.
- `src/hunter/open_interest/engine.py` — pure local computation engine: OI and price period changes, OI/price positioning classification, OI trend classification, optional caller-provided funding context, weighted 0–100 research score, universe summary, and safety-flag construction.
- `src/hunter/open_interest/writer.py` — deterministic JSON, CSV, Markdown serialization and atomic writers.
- `tests/test_open_interest/test_models.py` — model tests.
- `tests/test_open_interest/test_engine.py` — engine tests.
- `tests/test_open_interest/test_writer.py` — writer tests.
- `tests/test_open_interest/test_integration.py` — integration tests.
- 207 open_interest tests total.
- Full suite: 4835 tests passing, 1 skipped using `pytest --import-mode=importlib`.
- Safety: human-audit / research-only artifact only, not a trading signal, not trade approval, not strategy approval, not execution approval, not portfolio/universe approval, no Freqtrade input, no Binance/exchange/API/live data, no order/execution/action commands, no leverage/shorting, no feedback into execution/strategy/portfolio paths, file references and metadata strings not traversed/opened/followed/validated/executed, writer does not read input files.
- Default outputs:
  - `data/open_interest/latest_open_interest_report.json`
  - `data/open_interest/latest_open_interest_scores.csv`
  - `reports/open_interest/latest_open_interest_report.md`
- Next step: Discovery Engine planning only; implementation not started.

MVP-24 — Relative Strength Engine is complete and committed.
- SPEC-025: `specs/SPEC-025-Relative-Strength-Engine.md` — implemented.
- `src/hunter/relative_strength/__init__.py` — public API exports.
- `src/hunter/relative_strength/models.py` — frozen dataclasses, enums, reason codes, forbidden relative strength content detection, `RelativeStrengthConfig`, `RelativeStrengthSafetyFlags`, `RelativeStrengthState`, `RelativeStrengthDecision`, `RelativeStrengthBenchmarkKind`, `RelativeStrengthInput`, `OhlcvRow`, `RelativeStrengthPeriodReturn`, `RelativeStrengthRatioTrend`, `RelativeStrengthScore`, `RelativeStrengthDataQuality`, `RelativeStrengthUniverseSummary`, `RelativeStrengthReport`.
- `src/hunter/relative_strength/engine.py` — pure local computation engine: period returns, relative returns vs BTC/ETH, Coin/BTC ratio series and ratio trend, rank percentiles with deterministic tie-breaking, weighted total score, universe summary, and safety-flag construction.
- `src/hunter/relative_strength/writer.py` — deterministic JSON, CSV, Markdown serialization and atomic writers.
- `tests/test_relative_strength/test_models.py` — model tests.
- `tests/test_relative_strength/test_engine.py` — engine tests.
- `tests/test_relative_strength/test_writer.py` — writer tests.
- `tests/test_relative_strength/test_integration.py` — integration tests.
- 129 relative_strength tests total.
- Safety: human-audit / research-only artifact only, not a trading signal, not trade approval, not strategy approval, not execution approval, not portfolio/universe approval, no Freqtrade input, no Binance/exchange/API/live data, no order/execution/action commands, no leverage/shorting, no feedback into execution/strategy/portfolio paths, file references and metadata strings not traversed/opened/followed/validated/executed, writer does not read input files.
- Default outputs:
  - `data/relative_strength/latest_relative_strength_scores.json`
  - `data/relative_strength/latest_relative_strength_scores.csv`
  - `reports/relative_strength/latest_relative_strength_report.md`

MVP-23 — Local Research Audit Snapshot is complete and committed.
- SPEC-024: `specs/SPEC-024-Local-Research-Audit-Snapshot.md` — approved with minor notes.
- `src/hunter/research_audit_snapshot/__init__.py` — public API exports.
- `src/hunter/research_audit_snapshot/models.py` — frozen snapshot dataclasses, enums, reason codes, forbidden snapshot content detection, `AuditSnapshotConfig`, `AuditSnapshotSafetyFlags`, `AuditSnapshotSectionKind`, `AuditSnapshotItemSeverity`, `AuditSnapshotItem`, `AuditSnapshotSection`, `AuditSnapshotSummary`, `AuditSnapshotDataQuality`, `ResearchAuditSnapshot`.
- `src/hunter/research_audit_snapshot/engine.py` — in-memory snapshot engine functions: `has_unsafe_audit_snapshot_content`, `build_audit_snapshot_safety_flags`, `build_audit_snapshot_item`, `build_audit_snapshot_section`, `build_audit_snapshot_summary`, `build_audit_snapshot_data_quality`, `build_research_audit_snapshot`.
- `src/hunter/research_audit_snapshot/writer.py` — JSON/Markdown serialization, atomic file writing.
- `tests/test_research_audit_snapshot/test_models.py` — 60 model tests.
- `tests/test_research_audit_snapshot/test_engine.py` — 41 engine tests.
- `tests/test_research_audit_snapshot/test_writer.py` — 52 writer tests.
- `tests/test_research_audit_snapshot/test_integration.py` — 85 integration tests.
- 238 research_audit_snapshot tests total.
- Full suite: 4499 tests passing, 1 skipped using `pytest --import-mode=importlib`.
- Whole MVP-23 review: APPROVED WITH MINOR NOTES. No critical issues found.
- Safety: human-audit / contractor-handoff artifact only, not release approval, not deployment approval, not execution readiness, not strategy readiness, not trading signal, not trade approval, not transaction permission, not a runtime registry/indexer/crawler/scheduler/routing/dashboard/database/API/event-store/task-runner, no feedback into execution/strategy/Freqtrade/order/exchange paths, no Binance/exchange/API keys/live trading/real orders/leverage/shorting, file references and metadata strings not traversed/opened/followed/validated/executed, referenced artifact files not read, human audit guide advisory-only and non-gating, no action commands emitted, no release/deployment checklist semantics.
- Non-blocking minor note: `data_quality.sections_present` currently reports `0` and `sections_missing` reports `8` for successful snapshots because `build_audit_snapshot_data_quality` does not receive the section list in its SPEC-024 signature. Fail-closed and SPEC-compliant; future cleanup may refine the metric.

MVP-0 foundation is complete and committed.

MVP-1 Data Foundation is complete and committed. All 91 tests pass.

MVP-2 Market State is complete and committed. All 278 tests pass.
- Market State Models, Indicator Utilities, Regime Engine, Breadth Engine, JSON Output Writers all implemented.
- No Binance integration. No Freqtrade integration. No live trading.

MVP-3 Decision Layer is complete and committed. All 394 tests pass.
- Decision Models, Decision Engine, Decision Writer, Integration Tests all implemented.
- No Binance integration. No Freqtrade integration. No live trading. No JSON input reading.

MVP-4 Execution Bridge is complete and committed. All 538 tests pass.
- Execution Bridge Models, Engine, Writer, Integration Tests, Final Review all implemented.
- No Binance integration. No Freqtrade runtime integration. No live trading. No trading logic. No API keys.

MVP-5 Freqtrade Integration is complete and committed. All 722 tests pass.
- Freqtrade Bridge Models, Engine, Writer, Integration Tests, Final Review all implemented.
- No Binance integration. No real Freqtrade runtime integration. No live trading. No trading logic. No API keys.

MVP-6 Freqtrade Strategy Contract is complete and committed. All 959 tests pass.
- Strategy Contract Models, Engine, Writer, Integration Tests, Final Review all implemented.
- No Binance integration. No real Freqtrade runtime integration. No live trading. No trading logic. No API keys.

MVP-7 Freqtrade Dry-Run Strategy Adapter is complete and committed. All 1214 tests pass.
- Strategy Adapter Models, Engine, Writer, Integration Tests, Final Review all implemented.
- `src/hunter/strategy_adapter/models.py` — 8 model types + 15 reason codes.
- `src/hunter/strategy_adapter/engine.py` — 6 engine functions.
- `src/hunter/strategy_adapter/writer.py` — 3 writer functions + default path constant.
- `tests/test_strategy_adapter/test_models.py` — 94 model tests.
- `tests/test_strategy_adapter/test_engine.py` — 75 engine tests.
- `tests/test_strategy_adapter/test_writer.py` — 41 writer tests.
- `tests/test_strategy_adapter/test_integration.py` — 45 integration tests.
- `DEFAULT_ADAPTER_DECISION_PATH = data/strategy_adapter/current_adapter_decision.json`.
- Adapter produces dry-run-only fail-closed `AdapterDecisionContext` for future Freqtrade-facing consumers.
- No config YAML exists. No JSON schema exists. No deployable Freqtrade strategy class exists.
- No Binance integration. No real Freqtrade runtime integration. No API keys. No live trading. No real orders. No leverage. No shorting. No entry/exit execution logic.

SPEC-009 Freqtrade Deployable Dry-Run Strategy design is finalized and polished.
- `DryRunStrategyState`, `DryRunStrategyMode`, `DryRunSignalAction`, `DryRunStrategyRuntimeContext` defined.
- Fail-closed deployable dry-run strategy rules, deterministic reason codes, future config/schema/output defined.
- PlantUML component and runtime flow diagrams included.
- 5-step implementation plan defined.
- MVP-8 Step 1 Dry-Run Strategy Runtime Models complete.
- `dry_run_strategy` package now exists with models, engine, writer, and integration tests.
- `tests/test_dry_run_strategy/test_models.py` exists with 94 tests.
- MVP-8 Step 2 Dry-Run Strategy Runtime Engine complete.
- `src/hunter/dry_run_strategy/engine.py` exists with 6 engine functions.
- `tests/test_dry_run_strategy/test_engine.py` exists with 93 tests.
- MVP-8 Step 3 Dry-Run Strategy Runtime JSON Writer complete.
- `src/hunter/dry_run_strategy/writer.py` exists with 3 writer functions + default path constant.
- `tests/test_dry_run_strategy/test_writer.py` exists with 42 tests.
- MVP-8 Step 4 Dry-Run Strategy Runtime Integration Tests complete.
- `tests/test_dry_run_strategy/test_integration.py` exists with 48 tests.
- MVP-8 Step 5 Final Review complete. Verdict: PASS. No defects found.
- `DEFAULT_DRY_RUN_STRATEGY_RUNTIME_PATH = data/freqtrade_strategy/current_dry_run_strategy_runtime.json`.
- Full test suite: 1491 tests passing.

SPEC-010 Freqtrade Dry-Run Strategy Shell design is approved.
- `specs/SPEC-010-Freqtrade-Dry-Run-Strategy-Shell.md` approved.
- Designs a Freqtrade-compatible dry-run strategy shell consuming MVP-8 runtime JSON.
- Key safety clarifications: research-only signal exposure (metadata/columns only, no real trade signals), `populate_entry_trend` never sets `enter_long`/`enter_short`, `populate_exit_trend` never sets `exit_long`/`exit_short`, Freqtrade compatibility is interface boundary only, shell must not bypass MVP-5/MVP-6/MVP-7/MVP-8 safety contexts.
- MVP-9 Step 1 Shell Models and Validator complete.
- MVP-9 Step 2 Shell Adapter Boundary complete.
- MVP-9 Step 3 Shell Integration Tests complete.
- MVP-9 Step 4 Final Review complete. Verdict: PASS. No defects found.
- No Freqtrade strategy class. No freqtrade import.

SPEC-011 Freqtrade Dry-Run Research Observation Reports design is approved with notes and polished.
- `specs/SPEC-011-Dry-Run-Research-Observation-Reports.md` approved (729 lines).
- Designs a dry-run research observation/reporting layer consuming MVP-9 shell metadata.
- Produces local JSON/Markdown reports for human review only.
- Key safety clarifications: reports are human-review artifacts only (not trading signals), must never be consumed by execution/strategy/shell/order layers, must not feed back into any MVP layer, fail-closed observations produce safe audit output only, missing/invalid inputs summarized as BLOCKED/UNKNOWN, reports must not contain API keys/secrets/credentials/executable trading instructions.
- MVP-10 Step 1 Observation Models and Engine complete.
- `src/hunter/observation/__init__.py` — public API exports.
- `src/hunter/observation/models.py` — 9 models: ObservationState, ObservationSignal, ReportFormat, ObservationConfig, ObservationSafetyFlags, SignalObservation, ObservationWindow, ObservationDataQuality, ObservationReport.
- `src/hunter/observation/engine.py` — 5 engine functions: build_signal_observation, build_observation_window, build_observation_report, build_observation_safety_flags, has_unsafe_metadata.
- `tests/test_observation/test_models.py` — 77 model tests.
- `tests/test_observation/test_engine.py` — 59 engine tests.
- 13 deterministic reason codes + FORBIDDEN_METADATA_KEYS.
- MVP-10 Step 2 Observation Report Writer complete.
- `src/hunter/observation/writer.py` — 5 writer functions: observation_report_to_dict, observation_report_to_markdown, atomic_write_json_report, atomic_write_markdown_report, write_observation_reports.
- `src/hunter/observation/__init__.py` — updated with writer exports.
- `tests/test_observation/test_writer.py` — 58 writer tests.
- Default JSON path: `data/observation/latest_observation_report.json`.
- Default Markdown path: `reports/observation/latest_observation_report.md`.
- MVP-10 Step 3 Observation Integration Tests complete.
- `tests/test_observation/test_integration.py` — 58 integration tests.
- Full test suite: 1968 tests passing using `pytest --import-mode=importlib`.
- No models, engine, writer, or `__init__.py` changes.
- No integration tests yet. → now complete with integration tests.
- No Freqtrade strategy class. No freqtrade import. No Freqtrade runtime connection. No Binance. No real exchange. No API keys. No live trading. No real orders. No leverage. No shorting. No real entry/exit execution logic. No report feedback into execution paths. No production data reads/writes.

MVP-12 — Review Index is complete and committed.
- `src/hunter/review_index/models.py` — frozen index dataclasses, enums, reason codes, forbidden index content detection.
- `src/hunter/review_index/engine.py` — in-memory review index engine functions.
- `src/hunter/review_index/writer.py` — JSON/Markdown serialization, atomic file writing.
- `src/hunter/review_index/__init__.py` — updated with writer exports.
- `tests/test_review_index/test_models.py` — 70 model tests.
- `tests/test_review_index/test_engine.py` — 97 engine tests.
- `tests/test_review_index/test_writer.py` — 52 writer tests.
- `tests/test_review_index/test_integration.py` — 21 integration tests.
- 239 review_index tests total. 1 skipped.
- Full suite: 2450 tests passing, 1 skipped.

MVP-13 — Review Search / Query Layer is complete and committed.
- `src/hunter/review_search/models.py` — frozen search dataclasses, 12 reason codes, 8 search output safety flags, forbidden search content detection.
- `src/hunter/review_search/engine.py` — 6 engine functions: build_search_safety_flags, validate_search_query, entry_matches_query, score_search_entry, sort_search_results, build_search_result.
- `src/hunter/review_search/writer.py` — JSON/Markdown serialization, atomic file writing.
- `src/hunter/review_search/__init__.py` — updated with engine and writer exports.
- `tests/test_review_search/test_models.py` — 92 model tests.
- `tests/test_review_search/test_engine.py` — 82 engine tests.
- `tests/test_review_search/test_writer.py` — 51 writer tests.
- `tests/test_review_search/test_integration.py` — 45 integration tests.
- 278 review_search tests total. 1 skipped.
- Full suite: 2728 tests passing, 1 skipped using `pytest --import-mode=importlib`.
- Search results are human-audit artifacts only. Not trading signals. Not trade approvals.
- No file reads, no network, no Freqtrade, no Binance, no exchange, no API keys, no live trading, no real orders, no leverage, no shorting, no entry/exit execution logic.
- No report/operator/index/search feedback into execution paths.
- File references remain strings only, never traversed, opened, followed, validated, or executed.

MVP-14 — Local Research Bundle / Evidence Pack is complete and committed.
- SPEC-015: `specs/SPEC-015-Local-Research-Bundle-Evidence-Pack.md` — approved with no critical issues.
- `src/hunter/research_bundle/models.py` — frozen bundle dataclasses, enums, 12 reason codes, 22 forbidden terms, 8 bundle output safety flags, 13 unsafe safety flags.
- `src/hunter/research_bundle/engine.py` — 7 engine functions: build_bundle_safety_flags, has_unsafe_bundle_content, validate_bundle_item, build_bundle_item, build_bundle_summary, build_bundle_data_quality, build_research_bundle.
- `src/hunter/research_bundle/writer.py` — JSON/Markdown serialization, atomic file writing.
- `src/hunter/research_bundle/__init__.py` — updated with engine and writer exports.
- `tests/test_research_bundle/test_models.py` — 54 model tests.
- `tests/test_research_bundle/test_engine.py` — 58 engine tests.
- `tests/test_research_bundle/test_writer.py` — 49 writer tests.
- `tests/test_research_bundle/test_integration.py` — 33 integration tests.
- 194 research_bundle tests total. 1 skipped.
- Full suite: 2922 tests passing, 1 skipped using `pytest --import-mode=importlib`.
- Z.ai Step 3 review: APPROVED. Engine `human_note_count` fix validated — counts items with non-empty notes (not just HUMAN_NOTE kind), aligning with SPEC-015 semantic definition.
- Safety: human-audit only, no execution feedback, no trading signals, no file reference traversal.

MVP-15 — Local Research Chronicle / Audit Timeline is complete and committed.
- SPEC-016: `specs/SPEC-016-Local-Research-Chronicle-Audit-Timeline.md` — approved with notes and polished.
- `src/hunter/chronicle/__init__.py` — public API exports.
- `src/hunter/chronicle/models.py` — frozen chronicle dataclasses, enums, 12 reason codes, forbidden chronicle content detection, ArtifactType, ChronicleEntry, ChronicleSummary, ChronicleDataQuality, ChronicleSafetyFlags, ResearchChronicle.
- `src/hunter/chronicle/engine.py` — in-memory chronicle engine functions: has_unsafe_chronicle_content, build_chronicle_safety_flags, build_chronicle_entry_* builders, build_chronicle_summary, build_chronicle_data_quality, build_research_chronicle.
- `src/hunter/chronicle/writer.py` — JSON/Markdown serialization, atomic file writing.
- `src/hunter/chronicle/__init__.py` — updated with writer exports.
- `tests/test_chronicle/test_models.py` — model tests.
- `tests/test_chronicle/test_engine.py` — engine tests.
- `tests/test_chronicle/test_writer.py` — writer tests.
- `tests/test_chronicle/test_integration.py` — integration tests.
- 239 chronicle tests total. 1 skipped.
- Full suite: 3161 tests passing, 1 skipped using `pytest --import-mode=importlib`.
- Z.ai Step 3 review: APPROVED. No critical issues found.
- Safety: human-audit only, no execution feedback, no trading signals, trace linkage advisory only, no file reference traversal, no chronicle feedback into execution paths.

MVP-17 — Local Research Quality Gate / Audit Readiness is complete and committed.
- SPEC-018: `specs/SPEC-018-Local-Research-Quality-Gate-Audit-Readiness.md` — approved with one minor source defect found and fixed before Step 4.
- `src/hunter/research_quality_gate/__init__.py` — public API exports.
- `src/hunter/research_quality_gate/models.py` — frozen quality gate dataclasses, enums, 29 reason codes, forbidden quality gate content detection, QualityGateConfig, QualityGateSafetyFlags, QualityGateCheck, QualityGateCheckKind, QualityGateSummary, QualityGateDataQuality, ResearchQualityGate.
- `src/hunter/research_quality_gate/engine.py` — in-memory quality gate engine functions: has_unsafe_quality_gate_content, build_quality_gate_safety_flags, build_quality_gate_check, build_quality_gate_summary, build_quality_gate_data_quality, build_research_quality_gate.
- `src/hunter/research_quality_gate/writer.py` — JSON/Markdown serialization, atomic file writing.
- `src/hunter/research_quality_gate/__init__.py` — updated with writer exports.
- `tests/test_research_quality_gate/test_models.py` — model tests.
- `tests/test_research_quality_gate/test_engine.py` — engine tests.
- `tests/test_research_quality_gate/test_writer.py` — writer tests.
- `tests/test_research_quality_gate/test_integration.py` — 31 integration tests.
- 152 research_quality_gate tests total.
- Full suite: 3454 tests passing, 1 skipped using `pytest --import-mode=importlib`.
- Z.ai Step 3 review: APPROVED. Source defect `_is_blocking_reason` not treating `UNRESOLVED_BLOCKERS` as blocking was identified and fixed before Step 4. `engine._is_blocking_reason` now aligns with canonical `QUALITY_GATE_BLOCKING_REASON_CODES`; `UNRESOLVED_BLOCKERS` is included in gate-level `ResearchQualityGate.reason_codes`; `STALE_ARTIFACT` remains non-blocking per SPEC-018 §3.3.
- Safety: human-audit only, no execution feedback, no trading signals, not execution readiness, not strategy readiness, not release/deployment approval, not transaction permission, no file reference traversal, no quality gate feedback into execution paths.

MVP-18 — Local Research Handoff Packet is complete and committed.
- SPEC-019: `specs/SPEC-019-Local-Research-Handoff-Packet.md` — approved with no critical issues.
- `src/hunter/research_handoff/__init__.py` — public API exports.
- `src/hunter/research_handoff/models.py` — frozen handoff dataclasses, enums, 32 reason codes, forbidden handoff content detection, HandoffConfig, HandoffSafetyFlags, HandoffPacketKind, HandoffState, HandoffSection, HandoffSummary, HandoffDataQuality, ResearchHandoffPacket.
- `src/hunter/research_handoff/engine.py` — in-memory handoff engine functions: has_unsafe_handoff_content, build_handoff_safety_flags, build_handoff_section, build_handoff_summary, build_handoff_data_quality, build_research_handoff_packet.
- `src/hunter/research_handoff/writer.py` — JSON/Markdown serialization, atomic file writing.
- `src/hunter/research_handoff/__init__.py` — updated with writer exports.
- `tests/test_research_handoff/test_models.py` — model tests.
- `tests/test_research_handoff/test_engine.py` — engine tests.
- `tests/test_research_handoff/test_writer.py` — writer tests.
- `tests/test_research_handoff/test_integration.py` — 25 integration tests.
- 146 research_handoff tests total.
- Full suite: 3600 tests passing, 1 skipped using `pytest --import-mode=importlib`.
- Z.ai Step 3 review: APPROVED. No critical issues found.
- Safety: human-audit / contractor-handoff artifact only, no execution feedback, no trading signals, not execution readiness, not strategy readiness, not release/deployment approval, not transaction permission, no file reference traversal, no handoff feedback into execution paths, no report/operator/index/search/bundle/chronicle/digest/quality-gate/handoff feedback into execution paths.

MVP-21 — Local Research Audit Catalog is complete and committed.
- SPEC-022: `specs/SPEC-022-Local-Research-Audit-Catalog.md` — approved with no critical issues.
- `src/hunter/research_audit_catalog/__init__.py` — public API exports.
- `src/hunter/research_audit_catalog/models.py` — frozen catalog dataclasses, enums, 13 reason codes, forbidden catalog content detection, CatalogArtifactKind, CatalogState, CatalogConfig, CatalogSafetyFlags, CatalogEntry, CatalogSummary, CatalogDataQuality, ResearchCatalog.
- `src/hunter/research_audit_catalog/engine.py` — in-memory catalog engine functions: has_unsafe_audit_catalog_content, build_audit_catalog_safety_flags, build_audit_catalog_entry, build_audit_catalog_summary, build_audit_catalog_data_quality, build_research_audit_catalog.
- `src/hunter/research_audit_catalog/writer.py` — JSON/Markdown serialization, atomic file writing.
- `src/hunter/research_audit_catalog/__init__.py` — updated with writer exports.
- `tests/test_research_audit_catalog/test_models.py` — model tests.
- `tests/test_research_audit_catalog/test_engine.py` — engine tests.
- `tests/test_research_audit_catalog/test_writer.py` — writer tests.
- `tests/test_research_audit_catalog/test_integration.py` — 28 integration tests (after Step 3.1 cleanup).
- 157 research_audit_catalog tests total.
- Full suite: 4078 tests passing, 1 skipped using `pytest --import-mode=importlib`.
- Z.ai Step 3 review: APPROVED with minor notes. No critical issues found.
- Step 3.1 cleanup: canonical spec_reference mapping, all-11-layer coverage test, removed unused imports.
- Safety: human-audit / contractor-handoff artifact only, not release approval, not deployment approval, not trading signal, not trade approval, not execution approval, not strategy approval, not transaction permission, referenced artifact files are not read, file references and metadata strings are not traversed/opened/followed/validated/executed, human audit guide advisory-only and not gating, no action commands emitted, no release/deployment checklist semantics, no audit-catalog feedback into execution paths, no report/operator/index/search/bundle/chronicle/digest/quality-gate/handoff/archive-manifest/release-notes/audit-catalog feedback into execution paths. Not a runtime registry, indexer, crawler, scheduler, routing layer, dashboard, database, API, event store, or task runner.
- Future cleanup backlog (non-blocking): review `EMPTY_CATALOG` reason code reachability in engine vs SPEC-022 §3.5.

MVP-20 — Local Research Release Notes / Audit Change Summary is complete and committed.
- SPEC-021: `specs/SPEC-021-Local-Research-Release-Notes-Audit-Change-Summary.md` — approved with no critical issues.
- `src/hunter/research_release_notes/__init__.py` — public API exports.
- `src/hunter/research_release_notes/models.py` — frozen release notes dataclasses, enums, reason codes, forbidden release notes content detection, ReleaseNotesConfig, ReleaseNotesSafetyFlags, ReleaseNotesSectionKind, ReleaseNotesChangeSeverity, ReleaseNotesState, ReleaseNotesChangeItem, ReleaseNotesSection, ReleaseNotesSummary, ReleaseNotesDataQuality, ResearchReleaseNotes.
- `src/hunter/research_release_notes/engine.py` — in-memory release notes engine functions: has_unsafe_release_notes_content, build_release_notes_safety_flags, build_release_notes_change_item, build_release_notes_section, build_release_notes_summary, build_release_notes_data_quality, build_research_release_notes.
- `src/hunter/research_release_notes/writer.py` — JSON/Markdown serialization, atomic file writing.
- `src/hunter/research_release_notes/__init__.py` — updated with writer exports.
- `tests/test_research_release_notes/test_models.py` — model tests.
- `tests/test_research_release_notes/test_engine.py` — engine tests.
- `tests/test_research_release_notes/test_writer.py` — writer tests.
- `tests/test_research_release_notes/test_integration.py` — 46 integration tests.
- 157 research_release_notes tests total.
- Full suite: 3921 tests passing, 1 skipped using `pytest --import-mode=importlib`.
- Z.ai Step 3 review: APPROVED. No critical issues found.
- Safety: human-audit / contractor-handoff artifact only, not release approval, not deployment approval, not publish approval, no execution feedback, no trading signals, not execution readiness, not strategy readiness, not transaction permission, referenced artifact files are not read, file references and metadata strings are not traversed/opened/followed/validated/executed, human review guide advisory-only and not gating, no action commands emitted, no release/deployment checklist semantics, no release-notes feedback into execution paths, no report/operator/index/search/bundle/chronicle/digest/quality-gate/handoff/archive-manifest/release-notes feedback into execution paths.

MVP-19 — Local Research Archive Manifest is complete and committed.
- SPEC-020: `specs/SPEC-020-Local-Research-Archive-Manifest.md` — approved with no critical issues.
- `src/hunter/research_archive_manifest/__init__.py` — public API exports.
- `src/hunter/research_archive_manifest/models.py` — frozen archive manifest dataclasses, enums, 34 reason codes, forbidden archive manifest content detection, ArchiveManifestConfig, ArchiveManifestSafetyFlags, ArchiveArtifactFamily, ArchiveManifestState, ArchiveArtifactEntry, ArchiveManifestSummary, ArchiveManifestDataQuality, ResearchArchiveManifest.
- `src/hunter/research_archive_manifest/engine.py` — in-memory archive manifest engine functions: has_unsafe_archive_manifest_content, build_archive_manifest_safety_flags, build_archive_artifact_entry, build_archive_manifest_summary, build_archive_manifest_data_quality, build_research_archive_manifest.
- `src/hunter/research_archive_manifest/writer.py` — JSON/Markdown serialization, atomic file writing.
- `src/hunter/research_archive_manifest/__init__.py` — updated with writer exports.
- `tests/test_research_archive_manifest/test_models.py` — model tests.
- `tests/test_research_archive_manifest/test_engine.py` — engine tests.
- `tests/test_research_archive_manifest/test_writer.py` — writer tests.
- `tests/test_research_archive_manifest/test_integration.py` — 42 integration tests.
- 164 research_archive_manifest tests total.
- Full suite: 3764 tests passing, 1 skipped using `pytest --import-mode=importlib`.
- Z.ai Step 3 review: APPROVED. No critical issues found.
- Safety: human-audit inventory artifact only, no execution feedback, no trading signals, not execution readiness, not strategy readiness, not release/deployment approval, not transaction permission, referenced artifact files are not read, file references and metadata strings are not traversed/opened/followed/validated/executed, no archive manifest feedback into execution paths, no report/operator/index/search/bundle/chronicle/digest/quality-gate/handoff/archive-manifest feedback into execution paths.

MVP-16 — Local Research Digest / Executive Summary is complete and committed.
- SPEC-017: `specs/SPEC-017-Local-Research-Digest-Executive-Summary.md` — approved with no critical issues.
- `src/hunter/research_digest/__init__.py` — public API exports.
- `src/hunter/research_digest/models.py` — frozen digest dataclasses, enums, 17 reason codes, forbidden digest content detection, DigestConfig, DigestSafetyFlags, DigestSection, DigestSectionKind, DigestSummary, DigestDataQuality, ResearchDigest.
- `src/hunter/research_digest/engine.py` — in-memory digest engine functions: has_unsafe_digest_content, build_digest_safety_flags, build_digest_section, build_digest_summary, build_digest_data_quality, build_research_digest.
- `src/hunter/research_digest/writer.py` — JSON/Markdown serialization, atomic file writing.
- `src/hunter/research_digest/__init__.py` — updated with writer exports.
- `tests/test_research_digest/test_models.py` — model tests.
- `tests/test_research_digest/test_engine.py` — engine tests.
- `tests/test_research_digest/test_writer.py` — writer tests.
- `tests/test_research_digest/test_integration.py` — 26 integration tests.
- 141 research_digest tests total. 1 skipped.
- Full suite: 3302 tests passing, 1 skipped using `pytest --import-mode=importlib`.
- Z.ai Step 3 review: APPROVED. No critical issues found.
- Safety: human-audit only, no execution feedback, no trading signals, no recommendation engine, no action-command generator, no file reference traversal, no digest feedback into execution paths.

MVP-22 — Local Research Audit Closure Report is complete and committed.
- SPEC-023: `specs/SPEC-023-Local-Research-Audit-Closure-Report.md` — approved with minor notes. No critical issues found.
- `src/hunter/research_audit_closure/__init__.py` — public API exports.
- `src/hunter/research_audit_closure/models.py` — frozen closure dataclasses, enums, reason codes, forbidden closure content detection, AuditClosureConfig, AuditClosureSafetyFlags, AuditClosureSectionKind, AuditClosureFindingSeverity, AuditClosureState, AuditClosureKind, AuditClosureFinding, AuditClosureSection, AuditClosureSummary, AuditClosureDataQuality, ResearchAuditClosureReport.
- `src/hunter/research_audit_closure/engine.py` — in-memory closure engine functions: has_unsafe_audit_closure_content, build_audit_closure_safety_flags, build_audit_closure_finding, build_audit_closure_section, build_audit_closure_summary, build_audit_closure_data_quality, build_research_audit_closure_report.
- `src/hunter/research_audit_closure/writer.py` — JSON/Markdown serialization, atomic file writing.
- `tests/test_research_audit_closure/test_models.py` — model tests.
- `tests/test_research_audit_closure/test_engine.py` — engine tests.
- `tests/test_research_audit_closure/test_writer.py` — writer tests.
- `tests/test_research_audit_closure/test_integration.py` — 42 integration tests (after Step 3.1 cleanup).
- 183 research_audit_closure tests total.
- Full suite: 4261 tests passing, 1 skipped using `pytest --import-mode=importlib`.
- Z.ai Step 3 review: APPROVED with minor notes. No critical issues found.
- Step 3.1 cleanup completed: fixed checklist assertion, added unsafe backlog notes coverage, added unsafe references coverage, added INCOMPLETE state coverage, expanded safety flag assertions.
- Safety: human-audit / contractor-handoff artifact only, not release approval, not deployment approval, not trading signal, not trade approval, not execution approval, not strategy approval, not transaction permission, no audit-closure feedback into execution paths, no report/operator/index/search/bundle/chronicle/digest/quality-gate/handoff/archive-manifest/release-notes/audit-catalog/audit-closure feedback into execution paths, referenced artifact files are not read, file references and metadata strings are not traversed/opened/followed/validated/executed, human archival guide is advisory-only and not gating, no action commands emitted, no release/deployment checklist semantics, no Web UI, no dashboard, no database persistence, no Freqtrade/Binance/exchange/live/leverage/shorting, not a runtime registry/indexer/crawler/scheduler/routing/dashboard/database/API/event-store/task-runner.

## Next Step

MVP-49 — Research Audit Health Remediation Bridge is complete and tagged `v0.49.0-dev` at `eff7c93`. SPEC-050 at `6806aa9`; implementation at `1a4c7b2`; Step 4 finalization at `eff7c93`.

1. Begin MVP-50 selection and planning. No SPEC-051 exists yet.

### Backlog (Non-Blocking)
- Review `research_audit_snapshot` `data_quality.sections_present` / `sections_missing` reporting so successful snapshots correctly reflect the number of sections present (8) versus missing (0). Current behavior is fail-closed (0 / 8) and SPEC-compliant because `build_audit_snapshot_data_quality` does not receive the section list in its SPEC-024 signature.
- Review `EMPTY_CATALOG` reason code reachability in `research_audit_catalog/engine.py` vs SPEC-022 §3.5. Current behavior is fail-closed (`MISSING_ARTIFACTS` when `block_on_empty=True`, READY empty when `block_on_empty=False`); `EMPTY_CATALOG` is defined but not emitted.

### Not Allowed Until Future SPEC
- No config YAML.
- No JSON schema.
- No Freqtrade strategy class.
- No freqtrade import.
- No Freqtrade runtime connection.
- No Binance.
- No real exchange.
- No API keys.
- No live trading.
- No real orders.
- No leverage.
- No shorting.
- No real entry/exit execution logic.
- No report feedback into execution paths.
- No operator feedback into execution paths.
- No index feedback into execution paths.
- No search feedback into execution paths.
- No bundle feedback into execution paths.
- No chronicle feedback into execution paths.
- No digest feedback into execution paths.
- No quality gate feedback into execution paths.
- No handoff feedback into execution paths.
- No archive manifest feedback into execution paths.
- No release-notes feedback into execution paths.
- No audit-catalog feedback into execution paths.
- No Web UI.
- No dashboard.
- No database persistence.
- No production data reads/writes.

---

## Previous State (MVP-12 Complete)

MVP-12 — Review Index is complete and committed. All 239 tests pass (1 skipped).
- Review Index Models, Engine, Writer, Integration Tests all implemented.
- No config YAML. No JSON schema. No deployable strategy class. No Freqtrade runtime.
- No Binance. No API keys. No live trading. No real orders. No leverage. No shorting. No entry/exit execution logic.
- File references are local strings only and are not traversed, opened, followed, validated, or executed.

---
