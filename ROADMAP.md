# Hunter Futures Pro Roadmap

## Current Position

- **Current MVP:** MVP-47 — Cross-Artifact Consistency Engine (complete, tagged)
- **Current tag:** `v0.47.0-dev` at commit `6103b95`
- **Current branch:** `master`
- **Current SPEC:** `specs/SPEC-048-Cross-Artifact-Consistency-Engine.md`
- **Current HEAD:** `9925a2b` — post-tag context sync (1 commit ahead of `v0.47.0-dev`)
- **Latest tagged commit:** `6103b95` (`v0.47.0-dev`)
- **Next active work:** MVP-48 selection and planning — candidate direction is Research Audit Aggregate Health Report; no `SPEC-049` exists yet

The original master plan (MVP-0 through MVP-4) is complete. The repository has expanded well beyond that original plan into a long local research audit / governance / human-review chain that now ends at MVP-47. The project memory files have been realigned to reflect the actual MVP-47 state. No new runtime work should proceed without a new SPEC.

## Original Master Plan

This is the **historical** plan captured in `PROJECT.md`, `README.md`, and `tasks/backlog.md`. It is preserved here for context; the project has since expanded beyond it.

| Stage | MVP | Title | Scope |
|-------|-----|-------|-------|
| 0 | MVP-0 | Project Foundation | Repository, documentation, agent workflow, safety rules, architecture specification |
| 1 | MVP-1 | Data Foundation | Python project structure, config, logging, data collection planning, SQLite schema planning |
| 2 | MVP-2 | Market State | Regime Engine, Market Breadth Engine, JSON output, daily report |
| 3 | MVP-3 | Strength and Futures Positioning | Relative Strength, Open Interest, scoring rules, rejection codes |
| 4 | MVP-4 | Execution Control | Portfolio Engine, Decision Gate Engine, Freqtrade read-only integration, safe fallback rules |

`PROJECT.md` also listed 12 intended main modules:

1. Data Foundation
2. Regime Engine
3. Market Breadth Engine
4. Relative Strength Engine
5. Open Interest Engine
6. Discovery Engine
7. Portfolio Engine
8. Decision Gate Engine
9. Backtest Validation Engine
10. Reporting Layer
11. Freqtrade Execution Layer
12. Agent Memory Layer

All 12 modules are implemented across the expanded MVP chain, though not necessarily in the order originally implied. For example, Relative Strength and Open Interest were implemented much later (MVP-24 and MVP-25) after an extensive local research audit chain was built first.

## Expanded MVP Chain

The expanded chain grew beyond the original plan. It is documented here as a historical record of what was actually built, not as a rewrite of the original master plan.

| MVP Range | Theme | Specs | Notes |
|-----------|-------|-------|-------|
| MVP-5 – MVP-9 | Freqtrade execution contract chain | SPEC-006 – SPEC-010 | Freqtrade integration, strategy contract, adapter, deployable dry-run strategy, shell |
| MVP-10 – MVP-23 | Local research audit / review chain | SPEC-011 – SPEC-024 | Observation, review, review index, search, bundle, chronicle, digest, quality gate, handoff, archive manifest, release notes, audit catalog, closure, snapshot |
| MVP-24 – MVP-28 | Quantitative research engines | SPEC-025 – SPEC-029 | Relative Strength, Open Interest, Discovery, Portfolio Construction, Backtesting |
| MVP-29 – MVP-32 | Reporting / orchestration / ledger | SPEC-030 – SPEC-033 | Reporting CLI, Run Orchestrator, Experiment Ledger, Final Audit Pack |
| MVP-33 – MVP-39 | Remediation / release-hardening chain | SPEC-034 – SPEC-040 | Release hardening, evidence traceability, scorecard, cross-pack consistency, remediation backlog/evidence/closure |
| MVP-40 – MVP-42 | Human review chain | SPEC-041 – SPEC-043 | Human review queue, decision log, cross-artifact consistency |
| MVP-43 – MVP-45 | Audit bundle / export / verification | SPEC-044 – SPEC-046 | Audit bundle export, export artifact, verification/replay |
| MVP-46 | Project memory realignment | SPEC-047 | Documentation-only step to realign stale project memory; tagged `v0.46.0-dev` |
| MVP-47 | Cross-artifact consistency engine | SPEC-048 | Pure local audit-only consistency engine over caller-provided artifact refs and rules; tagged `v0.47.0-dev` |

For the full MVP-by-MVP mapping, see `docs/MVP_INDEX.md`.

## MVP Timeline

The repository is tagged from `v0.8.0-dev` through `v0.47.0-dev`, with the following notable gaps:

- `v0.32.0-dev` appears to be missing from the tag list even though the MVP-32 finalization commit exists. This is recorded as an anomaly.
- `v0.23.0-dev` covers both MVP-22 (Audit Closure Report) and MVP-23 (Audit Snapshot).

Current HEAD is `9925a2b` (post-tag context sync), one commit ahead of `v0.47.0-dev` at `6103b95`. The next step is MVP-48 selection and planning; no `SPEC-049` exists yet.

## Drift / Anomalies

Before MVP-46, the project memory files had drifted significantly from the actual repository state. MVP-46 corrected those memory-only issues without changing any functional code. The current state is now aligned with MVP-47.

| Item | Stale value | Actual value | Evidence |
|------|-------------|--------------|----------|
| `VERSION` | `0.1.0` | `0.47.0-dev` | `VERSION` file |
| `pyproject.toml` version | `0.32.0-dev` | `0.47.0-dev` | `pyproject.toml` line 3 |
| `docs/handoff/CURRENT_STATE.md` | MVP-32 current | MVP-47 current | `CURRENT_STATE.md` line 9 |
| `tasks/active.md` | MVP-40 current | MVP-47 current | `tasks/active.md` line 5 |
| `CHANGELOG.md` | ends at MVP-40 | includes MVP-47 | `CHANGELOG.md` first sections |
| `docs/architecture/SYSTEM_OVERVIEW.md` | "project is currently in MVP-0" | MVP-47 | `SYSTEM_OVERVIEW.md` line 100 |
| `docs/operations/*.md` | "MVP-0" | MVP-47 | operations docs "Current Phase" sections |
| `tasks/backlog.md` | only MVP-0–4 | should reference expanded chain | `tasks/backlog.md` content |
| `v0.32.0-dev` tag | missing | should exist after MVP-32 | `git tag --list "v0.*-dev"` |
| `v0.47.0-dev` tag | was previously missing | tagged at `6103b95` | `git tag --list "v0.*-dev"` |

## Next Step

**Active work:** MVP-48 selection and planning.

MVP-47 is complete and tagged `v0.47.0-dev` at `6103b95`. Current HEAD is `9925a2b`, one commit ahead of `v0.47.0-dev` due to the post-tag context sync.

No `SPEC-049` exists yet. Candidate direction for MVP-48 is **Research Audit Aggregate Health Report**. A new SPEC must be drafted and approved before any implementation starts.

Deliverables for MVP-48 planning:
- Select and approve MVP-48 direction and SPEC-049 title.
- Update memory docs when planning begins.
- No source code or tests until a SPEC is approved.

## Safety Boundaries

- This roadmap is a **human-read-only** artifact.
- It does not create, modify, or execute trading logic, exchange connections, API calls, or Freqtrade behavior.
- It does not claim production readiness, trading readiness, approval, certification, recommendation, or suitability.
- It preserves the original master plan as historical context and does not overwrite it.
- `data/` and `reports/` are excluded local artifact areas; they remain opaque and untouched.
- `src/hunter/cross_artifact_consistency/` is a tracked source package mapped to MVP-47; it is not excluded.
- The missing `v0.32.0-dev` tag is recorded as an anomaly only; no automatic tag creation is performed. The `v0.47.0-dev` tag is applied at `6103b95`.
