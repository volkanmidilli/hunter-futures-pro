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
- `src/hunter/cross_artifact_consistency/` — untracked local area

## Index Rules

- If a value is not known from tracked evidence, it is marked `unknown`.
- If a tag is absent but the MVP is committed, it is marked `missing` or `none`.
- MVP-0 and MVP-1 have no `-dev` tag in the current tag list; this is recorded as expected for pre-`v0.8.0-dev` history.
- MVP-46 is a documentation-only realignment step; its status is `SPEC committed; implementation in progress`.
- The original master plan is MVP-0 through MVP-4.
- The expanded chain is MVP-5 through MVP-45.
- `src/hunter/cross_artifact_consistency/` is not mapped because it is untracked and excluded.
- `src/hunter/backtesting`, `src/hunter/engines`, `src/hunter/fitness`, `src/hunter/portfolio`, and `src/hunter/reporting` are listed as legacy or utility packages with no clear spec mapping.

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
| MVP-45 | Human Review Audit Bundle Export Verification / Replay | `SPEC-046` | `v0.45.0-dev` | `human_review_audit_bundle_export_verification` | `test_human_review_audit_bundle_export_verification` | tagged | HEAD / current |
| MVP-46 | Project Memory Realignment | `SPEC-047` | none | `specs/` only | none | SPEC committed; implementation in progress | Documentation-only; no runtime package or tag yet |

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
| `src/hunter/cross_artifact_consistency` | Untracked; excluded from audit. No mapping is attempted. |

## Tag / Version Anomalies

| Anomaly | Evidence | Status |
|---------|----------|--------|
| `v0.32.0-dev` missing | `git tag --list "v0.*-dev"` jumps from `v0.31.0-dev` to `v0.33.0-dev`; MVP-32 finalization commit exists | Recorded; no automatic action |
| `VERSION` file is `0.1.0` | `VERSION` file | To be corrected in MVP-46 Step 3 |
| `pyproject.toml` version is `0.32.0-dev` | `pyproject.toml` line 3 | To be corrected in MVP-46 Step 3 |
| MVP-0 and MVP-1 have no `-dev` tag | `git tag --list "v0.*-dev"` starts at `v0.8.0-dev` | Expected; pre-tag history |
| `v0.23.0-dev` shared by MVP-22 and MVP-23 | Same tag appears on both closure and snapshot commits | Documented; not an error |

## Excluded Local Artifact Areas

The following areas are pre-existing local artifact directories. They are not inspected, traversed, or modified by this project memory realignment effort. All artifact, report, and path references inside them remain opaque strings.

- `data/`
- `reports/`
- `src/hunter/cross_artifact_consistency/` (untracked)

These exclusions are enforced by `specs/SPEC-047-Project-Memory-Realignment.md`.
