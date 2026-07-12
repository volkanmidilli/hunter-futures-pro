# System Overview

## Project

Hunter Futures Pro

## Purpose

Hunter Futures Pro is an agent-first crypto futures research and execution-control platform.

The system is designed to analyze crypto futures markets and decide whether trading execution should be allowed.

## Documented State

- **Latest tagged functional milestone:** MVP-46 / v0.46.0-dev
- **Current active work:** MVP-47 — Cross-Artifact Consistency Engine (complete, finalization pending)
- **Architecture description:** This document describes the current layered architecture based on the expanded MVP chain, with the original 3-layer model preserved as foundation.

## High-Level Architecture (Original Foundation)

Hunter Futures Pro was originally divided into three main layers:

1. Agent Layer
2. Decision Layer
3. Execution Layer

These remain the foundational layers. The expanded architecture below adds detail to each.

## 1. Agent Layer

The Agent Layer is responsible for project development, documentation, task tracking and future handoff.

Main tool:

- WrongStack

Preferred model/backend:

- Kimi K2.7

Main files:

- README.md
- PROJECT.md
- AGENTS.md
- .wrongstack/AGENTS.md
- ROADMAP.md
- docs/MVP_INDEX.md
- docs/handoff/CURRENT_STATE.md
- tasks/backlog.md
- tasks/active.md
- tasks/agent-log.md
- CHANGELOG.md
- VERSION
- specs/SPEC-*.md

## 2. Decision Layer

The Decision Layer is the brain of Hunter Futures Pro.

Original intended modules (all implemented across the expanded MVP chain):

- Data Foundation (MVP-1)
- Regime Engine (MVP-2)
- Market Breadth Engine (MVP-2)
- Relative Strength Engine (MVP-24)
- Open Interest Engine (MVP-25)
- Discovery Engine (MVP-26)
- Portfolio Engine / Portfolio Construction (MVP-27)
- Decision Gate Engine (MVP-3)
- Backtest Validation Engine (MVP-28)
- Reporting Layer / Reporting CLI (MVP-29)

This layer decides:

- market regime
- coin strength
- futures positioning health
- candidate pairs
- approved pairs
- rejected pairs
- execution allow/block decisions

## 3. Execution Layer

Freqtrade is the execution layer.

Freqtrade should only execute trades when Hunter Futures Pro allows it.

Freqtrade should not be responsible for high-level market decisions.

The Freqtrade integration chain is implemented across MVP-5 through MVP-9 (Freqtrade bridge, strategy contract, strategy adapter, deployable dry-run strategy, and strategy shell). All interaction is currently local, dry-run-only, and research-only.

## Expanded Architecture Layers

The original 3-layer architecture has been expanded to include layered audit and governance subsystems built during the MVP-10 through MVP-47 chain.

### Data / Config Foundation (MVP-0, MVP-1)

- `src/hunter/config/`, `src/hunter/data/`, `src/hunter/core/`
- Configuration, logging, core project bootstrap, data structures.

### Market State, Regime, Breadth (MVP-2)

- `src/hunter/market_state/`, `src/hunter/regime/`, `src/hunter/breadth/`
- Determine overall market regime and breadth. Research-only.

### Decision / Execution Boundary (MVP-3, MVP-4, MVP-5)

- `src/hunter/decision/`, `src/hunter/execution/`, `src/hunter/freqtrade_bridge/`
- Decision gate logic and execution bridge to Freqtrade. Fail-closed.

### Freqtrade Dry-Run Boundary (MVP-6 through MVP-9)

- `src/hunter/strategy_contract/`, `src/hunter/strategy_adapter/`, `src/hunter/dry_run_strategy/`, `src/hunter/freqtrade_shell/`
- Local, dry-run-only Freqtrade-compatible layers. No live trading.

### Local Review / Audit Chain (MVP-10 through MVP-23)

- `src/hunter/observation/`, `src/hunter/review/`, `src/hunter/review_index/`, `src/hunter/review_search/`, `src/hunter/research_bundle/`, `src/hunter/chronicle/`, `src/hunter/research_digest/`, `src/hunter/research_quality_gate/`, `src/hunter/research_handoff/`, `src/hunter/research_archive_manifest/`, `src/hunter/research_release_notes/`, `src/hunter/research_audit_catalog/`, `src/hunter/research_audit_closure/`, `src/hunter/research_audit_snapshot/`
- Human-audit artifacts, indices, search, bundles, chronicles, digests, quality gates, handoff packets, manifests, release notes, audit catalogs, closure reports, and snapshots. All deterministic, local, and audit-only.

### Research Engines (MVP-24 through MVP-28)

- `src/hunter/relative_strength/`, `src/hunter/open_interest/`, `src/hunter/discovery/`, `src/hunter/portfolio_construction/`, `src/hunter/backtest/`
- Quantitative engines for relative strength, open interest, discovery, portfolio construction, and backtesting. Research-only; no execution feedback.

### Reporting / Orchestration / Ledger (MVP-29 through MVP-32)

- `src/hunter/reporting_cli/`, `src/hunter/run_orchestrator/`, `src/hunter/experiment_ledger/`, `src/hunter/final_audit_pack/`
- CLI surface, run orchestration, experiment ledger, final audit pack export. Callable API only; no standalone runner.

### Remediation Chain (MVP-33 through MVP-39)

- `src/hunter/release_hardening/`, `src/hunter/evidence_traceability/`, `src/hunter/audit_scorecard/`, `src/hunter/cross_pack_consistency/`, `src/hunter/remediation_backlog/`, `src/hunter/remediation_evidence/`, `src/hunter/remediation_closure/`
- Release hardening, evidence traceability, scorecards, cross-pack consistency, remediation backlog/evidence/closure. Audit-only.

### Human Review Chain (MVP-40 through MVP-42)

- `src/hunter/human_review_queue/`, `src/hunter/human_review_decision_log/`, `src/hunter/human_review_decision_log_consistency/`
- Human review queue, decision log, and cross-artifact consistency. Deterministic, local, audit-only.

### Audit Bundle / Export / Verification (MVP-43 through MVP-45)

- `src/hunter/human_review_audit_bundle/`, `src/hunter/human_review_audit_bundle_export/`, `src/hunter/human_review_audit_bundle_export_verification/`
- Audit bundle export, export artifact, and verification / replay. Opaque references only; no file traversal.

### Project Memory / Docs Layer (MVP-46)

- `ROADMAP.md`, `docs/MVP_INDEX.md`, `docs/handoff/CURRENT_STATE.md`, `tasks/active.md`, `CHANGELOG.md`, `VERSION`, `pyproject.toml`, `docs/architecture/SYSTEM_OVERVIEW.md`, `docs/operations/*.md`
- Documentation and version metadata realignment. No runtime changes. Tagged `v0.46.0-dev`.

### Cross-Artifact Consistency Engine (MVP-47)

- `src/hunter/cross_artifact_consistency/`
- Pure local audit-only consistency engine over caller-provided in-memory artifact refs, rule definitions, and check results. Determines severity, reason codes, and per-rule/pass/fail status for cross-artifact consistency checks. Not a production release approval system, not a trading signal, not a recommendation, not an execution/portfolio/universe approval gate. Artifact refs are opaque strings and are not opened, traversed, validated, fetched, or executed. No runtime network/exchange/Freqtrade/server behavior. Complete; awaiting finalization review and explicit human `v0.47.0-dev` tag command.

## Safety Behavior

The system should fail closed.

This means:

- missing data blocks execution
- stale data blocks execution
- invalid JSON blocks execution
- unknown regime blocks execution
- unapproved pair blocks execution

## Current Status Summary

The original master plan (MVP-0 through MVP-4) is complete. The repository has expanded to MVP-46 / v0.46.0-dev. MVP-47 Cross-Artifact Consistency Engine is the current active work. All functional code is local, deterministic, and audit-only. Live trading, exchange connections, and Freqtrade runtime execution remain blocked by design.
