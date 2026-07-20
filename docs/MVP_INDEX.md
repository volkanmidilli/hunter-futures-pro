# MVP Index

This file is a deterministic, evidence-based index mapping each MVP to its specification, tag, source package, test package, and status. It is derived only from tracked repository files, specs, and git metadata.

## Evidence Sources

The index was built from the following tracked sources only:

- `specs/SPEC-001.md` through `specs/SPEC-047.md`
- `git tag --list "v0.*-dev"`
- `git log --oneline --decorate`
- `ROADMAP.md`
- Tracked `src/hunter/<package>/` directory names
- Tracked `tests/test_<package>/` directory names
- `PROJECT.md`, `README.md`, `tasks/backlog.md`, `tasks/active.md`
- `VERSION`, `pyproject.toml`, `CHANGELOG.md`

Excluded from evidence:

- `data/` — opaque local artifact area
- `reports/` — opaque local artifact area

## Index Rules

- If a value is not known from tracked evidence, it is marked `unknown`.
- If a tag is absent but the MVP is committed, it is marked `missing` or `none`.
- MVP-0 and MVP-1 have no `-dev` tag in the current tag list; this is recorded as expected for pre-`v0.8.0-dev` history.
- MVP-46 is a documentation-only realignment step; its status is `tagged` at `v0.46.0-dev`.
- The original master plan is MVP-0 through MVP-4.
- The expanded chain is MVP-5 through MVP-58.
- MVP-47 is complete and tagged at `v0.47.0-dev`.
- MVP-48 is complete and tagged at `v0.48.0-dev` (commit `779692f`).
- MVP-49 is complete and tagged `v0.49.0-dev` at `eff7c93`.
- `src/hunter/cross_artifact_consistency/` is tracked and mapped to MVP-47.
- `src/hunter/research_audit_health/` is tracked and mapped to MVP-48.
- `src/hunter/research_audit_health_remediation/` is tracked and mapped to MVP-49.
- `src/hunter/research_audit_remediation_handoff/` is tracked and mapped to MVP-50.
- `src/hunter/backtesting`, `src/hunter/engines`, `src/hunter/fitness`, `src/hunter/portfolio`, and `src/hunter/reporting` are listed as legacy or utility packages with no clear spec mapping.
- `SPEC-050` exists for MVP-49 Research Audit Health Remediation Bridge. Tagged `v0.49.0-dev` at `eff7c93`.
- `SPEC-051` exists for MVP-50 Research Audit Remediation Handoff Packet. Tagged `v0.50.0-dev` at `64004c3`.
- `SPEC-052` exists for MVP-51 Controlled Universe Bridge Engine. Tagged `v0.51.0-dev` at `a75de79`.
- `SPEC-053` exists for MVP-52 End-to-End Research Run Orchestrator v2. Complete; tagged `v0.52.0-dev` at `0c65e20`.
- `SPEC-054` exists for MVP-53 Controlled Universe Export Adapter. Complete; tagged `v0.53.0-dev` (local-only; no push).
- `SPEC-055` exists for MVP-54 Operational One-Call Coin-Discovery Pipeline Runner. Complete; tagged `v0.54.0-dev` at `c7ef130` (local-only; no push).
- `SPEC-056` exists for MVP-55 Freqtrade Universe Consumption Adapter. Complete; tagged `v0.55.0-dev` at `8f9730a2` (local-only; no push).
- `SPEC-057` exists for MVP-56 Strategy Contract Consumption Adapter. Complete; tagged `v0.56.0-dev` at `238e387` (local-only; no push).
- `SPEC-058` exists for MVP-57 Portfolio Construction Research Adapter. Complete; tagged `v0.57.0-dev` at `2d68a75` (local-only; no push).
- `SPEC-059` exists for MVP-58 Portfolio Risk Constraint Evaluator. Complete; tag pending at `v0.58.0-dev` (local-only; no push).
- `SPEC-060` exists for MVP-59 Research Decision Gate Engine. Complete; tagged `v0.59.0-dev` at `8d00af3` (local-only; no push).
- `SPEC-061` exists for MVP-60 Human Review Decision Registry. Complete; tagged `v0.60.0-dev` (local-only; no push).
- `SPEC-062` exists for MVP-61 Governance Decision Summary Aggregator. Complete; tag pending at `v0.61.0-dev` (local-only; no push).
- `SPEC-063` exists for MVP-62 Research Governance Handoff Package Builder. Complete; tagged `v0.62.0-dev` (local-only; no push).
- `SPEC-064` exists for MVP-63 Research Market Data CSV Loader and Adapter. Complete; tag pending at `v0.63.0-dev` (local-only; no push).
- `SPEC-065` exists for MVP-64 Dual Universe Builder. Complete; tagged `v0.64.0-dev` (local-only; no push).
- `SPEC-066` exists for MVP-65 Research Universe Backtest Comparison Harness. Complete; tagged `v0.65.0-dev` at `7278e04` (local-only; no push).
- `SPEC-067` exists for MVP-66 Walk-Forward Universe Comparison and Regime Evaluation. Complete; tagged `v0.66.0-dev` at `7c85533` (local-only; no push).
- `SPEC-068` exists for MVP-67 Walk-Forward Statistical Confidence and Stability Evaluation. Complete; tagged `v0.67.0-dev` at `201044a` (local-only; no push).
- `SPEC-069` exists for MVP-68 Research Experiment Ledger, Replication and Multiple-Testing Control. Complete; tagged `v0.68.0-dev` at `3fb2819` (local-only; no push). Patch `v0.68.1-dev` adds writer silent-overwrite protection and failed-write cleanup.
- `SPEC-070` exists for MVP-69 Research Campaign Compiler and MVP-70 Research Campaign Batch Orchestrator. Complete; tagged `v0.70.0-dev` (local-only; no push). MVP-69 tagged `v0.69.0-dev` at `e826936`.

## MVP Index Table

| MVP | Title | SPEC | Tag | Source Package(s) | Test Package(s) | Status | Notes / Anomalies |
|-----|-------|------|-----|-------------------|-----------------|--------|-------------------|
| MVP-0 | Project Foundation | `SPEC-001` | none | `core`, `config` | `test_core`, `test_config` | committed | No `-dev` tag; pre-tag history |
| MVP-1 | Data Foundation | `SPEC-002` | none | `data`, `config` | `test_data`, `test_config` | committed | No `-dev` tag; pre-tag history |
| MVP-2 | Market State / Regime & Breadth | `SPEC-003` | `v0.3.0-dev` | `market_state`, `regime`, `breadth` | `test_market_state` | tagged | Inferred from commit history |
| MVP-3 | Decision Layer | `SPEC-004` | `v0.4.0-dev` | `decision` | `test_decision` | tagged | Inferred from commit history |
| MVP-4 | Execution Bridge / Freqtrade Integration | `SPEC-005` | `v0.5.0-dev` | `execution` | `test_execution` | tagged | Inferred from commit history |
| MVP-5 | Freqtrade Integration | `SPEC-006` | `v0.6.0-dev` | `freqtrade_bridge` | `test_freqtrade_bridge` | tagged | Inferred from commit history |
| MVP-6 | Freqtrade Strategy Contract | `SPEC-007` | `v0.7.0-dev` | `strategy_contract` | `test_strategy_contract` | tagged | Inferred from commit history |
| MVP-7 | Freqtrade Dry-Run Strategy Adapter | `SPEC-008` | `v0.8.0-dev` | `strategy_adapter` | `test_strategy_adapter` | tagged | First tag in current tag list |
| MVP-8 | Freqtrade Deployable Dry-Run Strategy | `SPEC-009` | `v0.9.0-dev` | `dry_run_strategy` | `test_dry_run_strategy` | tagged | — |
| MVP-9 | Freqtrade Dry-Run Strategy Shell | `SPEC-010` | `v0.10.0-dev` | `freqtrade_shell` | `test_freqtrade_shell` | tagged | — |
| MVP-10 | Dry-Run Research Observation Reports | `SPEC-011` | `v0.11.0-dev` | `observation` | `test_observation` | tagged | — |
| MVP-11 | Operator Review Workflow | `SPEC-012` | `v0.12.0-dev` | `review` | `test_review` | tagged | — |
| MVP-12 | Local Review Index | `SPEC-013` | `v0.13.0-dev` | `review_index` | `test_review_index` | tagged | — |
| MVP-13 | Local Review Search / Query Layer | `SPEC-014` | `v0.14.0-dev` | `review_search` | `test_review_search` | tagged | — |
| MVP-14 | Local Research Bundle / Evidence Pack | `SPEC-015` | `v0.15.0-dev` | `research_bundle` | `test_research_bundle` | tagged | — |
| MVP-15 | Local Research Chronicle / Audit Timeline | `SPEC-016` | `v0.16.0-dev` | `chronicle` | `test_chronicle` | tagged | — |
| MVP-16 | Local Research Digest / Executive Summary | `SPEC-017` | `v0.17.0-dev` | `research_digest` | `test_research_digest` | tagged | — |
| MVP-17 | Local Research Quality Gate / Audit Readiness | `SPEC-018` | `v0.18.0-dev` | `research_quality_gate` | `test_research_quality_gate` | tagged | — |
| MVP-18 | Local Research Handoff Packet | `SPEC-019` | `v0.19.0-dev` | `research_handoff` | `test_research_handoff` | tagged | — |
| MVP-19 | Local Research Archive Manifest | `SPEC-020` | `v0.20.0-dev` | `research_archive_manifest` | `test_research_archive_manifest` | tagged | — |
| MVP-20 | Local Research Release Notes / Audit Change Summary | `SPEC-021` | `v0.21.0-dev` | `research_release_notes` | `test_research_release_notes` | tagged | — |
| MVP-21 | Local Research Audit Catalog | `SPEC-022` | `v0.22.0-dev` | `research_audit_catalog` | `test_research_audit_catalog` | tagged | — |
| MVP-22 | Local Research Audit Closure Report | `SPEC-023` | `v0.23.0-dev` | `research_audit_closure` | `test_research_audit_closure` | tagged | Same tag as MVP-23 |
| MVP-23 | Local Research Audit Snapshot | `SPEC-024` | `v0.23.0-dev` | `research_audit_snapshot` | `test_research_audit_snapshot` | tagged | Same tag as MVP-22 |
| MVP-24 | Relative Strength Engine | `SPEC-025` | `v0.24.0-dev` | `relative_strength` | `test_relative_strength` | tagged | — |
| MVP-25 | Open Interest Engine | `SPEC-026` | `v0.25.0-dev` | `open_interest` | `test_open_interest` | tagged | — |
| MVP-26 | Discovery Engine | `SPEC-027` | `v0.26.0-dev` | `discovery` | `test_discovery` | tagged | — |
| MVP-27 | Portfolio Construction Engine | `SPEC-028` | `v0.27.0-dev` | `portfolio_construction` | `test_portfolio_construction` | tagged | — |
| MVP-28 | Local Research Backtesting Engine | `SPEC-029` | `v0.28.0-dev` | `backtest` | `test_backtest` | tagged | — |
| MVP-29 | Local Research Reporting CLI | `SPEC-030` | `v0.29.0-dev` | `reporting_cli` | `test_reporting_cli` | tagged | — |
| MVP-30 | Local Research Run Orchestrator | `SPEC-031` | `v0.30.0-dev` | `run_orchestrator` | `test_run_orchestrator` | tagged | — |
| MVP-31 | Local Research Experiment Ledger | `SPEC-032` | `v0.31.0-dev` | `experiment_ledger` | `test_experiment_ledger` | tagged | — |
| MVP-32 | Local Research Final Audit Pack Export | `SPEC-033` | `missing` | `final_audit_pack` | `test_final_audit_pack` | committed | `v0.32.0-dev` tag missing; commit exists |
| MVP-33 | Local Research Release Hardening Consistency Audit | `SPEC-034` | `v0.33.0-dev` | `release_hardening` | `test_release_hardening` | tagged | — |
| MVP-34 | Local Research Evidence Traceability Matrix | `SPEC-035` | `v0.34.0-dev` | `evidence_traceability` | `test_evidence_traceability` | tagged | — |
| MVP-35 | Local Research Audit Readiness Scorecard | `SPEC-036` | `v0.35.0-dev` | `audit_scorecard` | `test_audit_scorecard` | tagged | — |
| MVP-36 | Local Research Cross-Pack Consistency Validator | `SPEC-037` | `v0.36.0-dev` | `cross_pack_consistency` | `test_cross_pack_consistency` | tagged | — |
| MVP-37 | Local Research Remediation Backlog Planner | `SPEC-038` | `v0.37.0-dev` | `remediation_backlog` | `test_remediation_backlog` | tagged | — |
| MVP-38 | Local Research Remediation Evidence Tracker | `SPEC-039` | `v0.38.0-dev` | `remediation_evidence` | `test_remediation_evidence` | tagged | — |
| MVP-39 | Local Research Remediation Closure Register | `SPEC-040` | `v0.39.0-dev` | `remediation_closure` | `test_remediation_closure` | tagged | — |
| MVP-40 | Local Research Human Review Queue | `SPEC-041` | `v0.40.0-dev` | `human_review_queue` | `test_human_review_queue` | tagged | — |
| MVP-41 | Local Research Human Review Decision Log | `SPEC-042` | `v0.41.0-dev` | `human_review_decision_log` | `test_human_review_decision_log` | tagged | — |
| MVP-42 | Human Review Decision Log Cross-Artifact Consistency | `SPEC-043` | `v0.42.0-dev` | `human_review_decision_log_consistency` | `test_human_review_decision_log_consistency` | tagged | — |
| MVP-43 | Human Review Audit Bundle Export | `SPEC-044` | `v0.43.0-dev` | `human_review_audit_bundle` | `test_human_review_audit_bundle` | tagged | — |
| MVP-44 | Human Review Audit Bundle Export Artifact | `SPEC-045` | `v0.44.0-dev` | `human_review_audit_bundle_export` | `test_human_review_audit_bundle_export` | tagged | — |
| MVP-45 | Human Review Audit Bundle Export Verification / Replay | `SPEC-046` | `v0.45.0-dev` | `human_review_audit_bundle_export_verification` | `test_human_review_audit_bundle_export_verification` | tagged | — |
| MVP-46 | Project Memory Realignment | `SPEC-047` | `v0.46.0-dev` | `specs/`, docs only | none | tagged | Documentation-only realignment; tag at `b3ea2a4` |
| MVP-47 | Cross-Artifact Consistency Engine | `SPEC-048` | `v0.47.0-dev` | `cross_artifact_consistency` | `test_cross_artifact_consistency` | tagged | Tagged at `6103b95` |
| MVP-48 | Research Audit Aggregate Health Report | `SPEC-049` | `v0.48.0-dev` | `research_audit_health` | `test_research_audit_health` | tagged | Tagged at `779692f` |
| MVP-49 | Research Audit Health Remediation Bridge | `SPEC-050` | `v0.49.0-dev` | `research_audit_health_remediation` | `test_research_audit_health_remediation` | tagged | Tagged at `eff7c93` |
| MVP-50 | Research Audit Remediation Handoff Packet | `SPEC-051` | `v0.50.0-dev` | `research_audit_remediation_handoff` | `test_research_audit_remediation_handoff` | tagged | Tagged at `64004c3` |
| MVP-51 | Controlled Universe Bridge Engine | `SPEC-052` | `v0.51.0-dev` | `controlled_universe` | `test_controlled_universe` | tagged | Tagged at `a75de79` |
| MVP-52 | End-to-End Research Run Orchestrator v2 | `SPEC-053` | `v0.52.0-dev` | `run_orchestrator` | `test_run_orchestrator` | tagged | Tagged at `0c65e20`; no push |
| MVP-53 | Controlled Universe Export Adapter | `SPEC-054` | `v0.53.0-dev` | `controlled_universe_export_adapter` | `test_controlled_universe_export_adapter` | tagged | Tagged `v0.53.0-dev` (local-only; no push) |
| MVP-55 | Freqtrade Universe Consumption Adapter | `SPEC-056` | `v0.55.0-dev` | `freqtrade_universe_adapter` | `test_freqtrade_universe_adapter` | tagged | Tagged `v0.55.0-dev` at `8f9730a2` (local-only; no push) |
| MVP-56 | Strategy Contract Consumption Adapter | `SPEC-057` | `v0.56.0-dev` | `strategy_contract_consumer` | `test_strategy_contract_consumer` | tagged | Tagged `v0.56.0-dev` at `238e387` (local-only; no push) |
| MVP-57 | Portfolio Construction Research Adapter | `SPEC-058` | `v0.57.0-dev` | `portfolio_research_adapter` | `test_portfolio_research_adapter` | tagged | Tagged `v0.57.0-dev` at `2d68a75` (local-only; no push) |
| MVP-61 | Governance Decision Summary Aggregator | `SPEC-062` | `v0.61.0-dev` | `governance_summary` | `test_governance_summary` | tagged | Tag pending; local-only; no push |
| MVP-60 | Human Review Decision Registry | `SPEC-061` | `v0.60.0-dev` | `human_review_registry` | `test_human_review_registry` | tagged | Tagged `v0.60.0-dev` (local-only; no push) |
| MVP-59 | Research Decision Gate Engine | `SPEC-060` | `v0.59.0-dev` | `research_decision_gate` | `test_research_decision_gate` | tagged | Tagged `v0.59.0-dev` at `8d00af3` (local-only; no push) |
| MVP-58 | Portfolio Risk Constraint Evaluator | `SPEC-059` | `v0.58.0-dev` | `portfolio_risk_evaluator` | `test_portfolio_risk_evaluator` | tagged | Tagged `v0.58.0-dev` at `8578fe4` (local-only; no push) |
| MVP-54 | Operational One-Call Coin-Discovery Pipeline Runner | `SPEC-055` | `v0.54.0-dev` | `coin_discovery_pipeline` | `test_coin_discovery_pipeline` | tagged | Tagged `v0.54.0-dev` at `c7ef130` (local-only; no push) |
| MVP-62 | Research Governance Handoff Package Builder | `SPEC-063` | `v0.62.0-dev` | `governance_handoff` | `test_governance_handoff` | tagged | Tagged `v0.62.0-dev` (local-only; no push) |
| MVP-63 | Research Market Data CSV Loader and Adapter | `SPEC-064` | `v0.63.0-dev` | `research_market_data` | `test_research_market_data` | tagged | Tagged `v0.63.0-dev` (local-only; no push) |
| MVP-64 | Dual Universe Builder | `SPEC-065` | `v0.64.0-dev` | `research_universe` | `test_research_universe` | tagged | Tagged `v0.64.0-dev` (local-only; no push) |
| MVP-65 | Research Universe Backtest Comparison Harness | `SPEC-066` | `v0.65.0-dev` | `research_backtest_comparison` | `test_research_backtest_comparison` | tagged | Tagged `v0.65.0-dev` at `7278e04` (local-only; no push) |
| MVP-66 | Walk-Forward Universe Comparison and Regime Evaluation | `SPEC-067` | `v0.66.0-dev` | `research_walk_forward` | `test_research_walk_forward` | tagged | Tagged `v0.66.0-dev` at `7c85533` (local-only; no push) |
| MVP-67 | Walk-Forward Statistical Confidence and Stability Evaluation | `SPEC-068` | `v0.67.0-dev` | `research_statistical_confidence` | `test_research_statistical_confidence` | tagged | Tagged `v0.67.0-dev` at `201044a` (local-only; no push) |
| MVP-68 | Research Experiment Ledger, Replication and Multiple-Testing Control | `SPEC-069` | `v0.68.0-dev` | `research_evidence_ledger` | `test_research_evidence_ledger` | tagged | Tagged `v0.68.0-dev` at `3fb2819`; patch `v0.68.1-dev` adds writer overwrite protection (local-only; no push) |
| MVP-69 | Research Campaign Compiler | `SPEC-070` | `v0.69.0-dev` | `research_campaign` | `test_research_campaign` | tagged | Cartesian-product compilation, filters, deterministic fingerprints |
| MVP-70 | Research Campaign Batch Orchestrator | `SPEC-070` | `v0.70.0-dev` | `research_campaign` | `test_research_campaign` | tagged | Sequential runner, resume/reuse, checkpoints, dossier writer |

## Phase Index

| Phase | Spec | Version | Status | Notes |
|---|---|---|---|---|
| Phase A | `SPEC-047`–`SPEC-070` | `v0.70.1-dev` | tagged | Research Pipeline Conformance and Safety Closure. Tagged `v0.70.1-dev` at `0303dcd` (local-only; no push). Closed conformance, safety, writer, resume, ledger-integrity, and checkpoint defects across MVP-63 through MVP-70. |
| Phase B.1 | `SPEC-073` | `v0.70.2-dev` | tagged | External Fixture Manifest and Hash Validation. `ExternalFixtureManifest` / `FixtureFileRecord`, bounded SHA-256 verification, strict/non-strict undeclared-file policy, deterministic fingerprinting. Tagged `v0.70.2-dev` (local-only; no push). |
| Phase B.2 | `SPEC-072` | `v0.71.0-rc.1` | tagged — COMPATIBLE | Real Freqtrade Compatibility. Real external fixture (BTC/USDT:USDT futures, 5m, binance) downloaded via `freqtrade download-data`; two compatibility-only no-op strategies (`HunterCompatibilityCandidate`, `HunterCompatibilityBaseline`) added; two verified MVP-65 defects fixed (hardcoded fake exchange name, unwired fixture data path) plus additional defects found while reaching a real compatible run against the installed Freqtrade build (deprecated `protections` key, numeric-string config fields, Binance-futures ticker-pricing validation, `--export-filename`→`--backtest-directory`/zip export format, futures stake-currency parsing, OHLCV data format). Both Candidate and Baseline ran real `freqtrade backtesting` and real exports parsed (`EXECUTED_PASS`, zero trades — plumbing only, no profitability claim). Full suite 10,233 passed, 2 skipped, 9 warnings. Tagged `v0.71.0-rc.1` (local-only; no push). |
| MVP-71 | (not started) | — | not started | Not started by Phase B policy. |

## Package Mapping

### Legacy / utility packages with no clear spec mapping

These packages exist in the tree but are not mapped to a specific MVP in the spec chain:

| Package | Notes |
|---------|-------|
| `src/hunter/backtesting` | Legacy or alternate backtesting name; no matching spec. |
| `src/hunter/engines` | Shared engine utilities or legacy module; no clear spec mapping. |
| `src/hunter/fitness` | Possibly strategy fitness; no matching spec. |
| `src/hunter/portfolio` | Legacy portfolio module; current portfolio work is in `portfolio_construction`. |
| `src/hunter/reporting` | Reporting utilities; no matching spec. |

### Excluded / untracked package

| Package | Notes |
|---------|-------|
| (none) | All known tracked packages are mapped. |

## Tag / Version Anomalies

| Anomaly | Evidence | Status |
|---------|----------|--------|
| `v0.32.0-dev` missing | `git tag --list "v0.*-dev"` jumps from `v0.31.0-dev` to `v0.33.0-dev`; MVP-32 finalization commit exists | Recorded; no automatic action |
| `v0.47.0-dev` now applied | MVP-47 complete; tag at `6103b95` | Resolved |
| MVP-0 and MVP-1 have no `-dev` tag | `git tag --list "v0.*-dev"` starts at `v0.8.0-dev` | Expected; pre-tag history |
| `v0.23.0-dev` shared by MVP-22 and MVP-23 | Same tag appears on both closure and snapshot commits | Documented; not an error |

## Excluded Local Artifact Areas

The following areas are pre-existing local artifact directories. They are not inspected, traversed, or modified by autonomous workflow steps. All artifact, report, and path references inside them remain opaque strings.

- `data/`
- `reports/`

`src/hunter/cross_artifact_consistency/` is no longer excluded; it is a tracked source package mapped to MVP-47.

These exclusions are enforced by the active workflow safety rules.
