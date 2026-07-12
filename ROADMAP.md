# Hunter Futures Pro Roadmap

## Current Position

- **Current MVP:** MVP-45 — Human Review Audit Bundle Export Verification / Replay
- **Current tag:** `v0.45.0-dev`
- **Current branch:** `master`
- **Current SPEC:** `specs/SPEC-046-Human-Review-Audit-Bundle-Export-Verification-Replay.md`
- **Current commit:** `1047ede` (tagged `v0.45.0-dev`)
- **Next active work:** MVP-46 — Project Memory Realignment (`specs/SPEC-047-Project-Memory-Realignment.md`)

The original master plan (MVP-0 through MVP-4) is complete. The repository has expanded well beyond that original plan into a long local research audit / governance / human-review chain that now ends at MVP-45. The next step is to realign project memory files so that future agents can read the repository and understand that the project is at MVP-45, not at MVP-0, MVP-32, or MVP-40 as stale files currently suggest.

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
| MVP-46 | Project memory realignment | SPEC-047 | Documentation-only step to realign stale project memory |

For the full MVP-by-MVP mapping, see `docs/MVP_INDEX.md`.

## MVP Timeline

The repository is tagged from `v0.8.0-dev` through `v0.45.0-dev`, with the following notable gaps:

- `v0.32.0-dev` appears to be missing from the tag list even though the MVP-32 finalization commit exists. This is recorded as an anomaly.
- `v0.23.0-dev` covers both MVP-22 (Audit Closure Report) and MVP-23 (Audit Snapshot).

Current HEAD is `1047ede` with tag `v0.45.0-dev`. The next tag will be `v0.46.0-dev` only after MVP-46 implementation is complete and explicitly approved.

## Drift / Anomalies

Before MVP-46, the project memory files had drifted significantly from the actual repository state:

| Item | Stale value | Actual value | Evidence |
|------|-------------|--------------|----------|
| `VERSION` | `0.1.0` | `0.45.0-dev` | `VERSION` file |
| `pyproject.toml` version | `0.32.0-dev` | `0.45.0-dev` | `pyproject.toml` line 3 |
| `docs/handoff/CURRENT_STATE.md` | MVP-32 current | MVP-45 current | `CURRENT_STATE.md` line 9 |
| `tasks/active.md` | MVP-40 current | MVP-45 current | `tasks/active.md` line 5 |
| `CHANGELOG.md` | ends at MVP-40 | should include MVP-41–45 | `CHANGELOG.md` first sections |
| `docs/architecture/SYSTEM_OVERVIEW.md` | "project is currently in MVP-0" | MVP-45 | `SYSTEM_OVERVIEW.md` line 100 |
| `docs/operations/*.md` | "MVP-0" | MVP-45 | operations docs "Current Phase" sections |
| `tasks/backlog.md` | only MVP-0–4 | should reference expanded chain | `tasks/backlog.md` content |
| `v0.32.0-dev` tag | missing | should exist after MVP-32 | `git tag --list "v0.*-dev"` |

MVP-46 will correct these memory-only issues without changing any functional code.

## Next Step

**Active work:** MVP-46 — Project Memory Realignment (`specs/SPEC-047-Project-Memory-Realignment.md`).

MVP-46 is a documentation-only step. Its deliverables are:

- `ROADMAP.md` (this file)
- `docs/MVP_INDEX.md`
- Updates to `docs/handoff/CURRENT_STATE.md`, `tasks/active.md`, `CHANGELOG.md`, `VERSION`, `pyproject.toml`
- Updates to `docs/architecture/SYSTEM_OVERVIEW.md` and `docs/operations/*.md`
- Optional update to `tasks/agent-log.md`

No new functional MVP should be selected until MVP-46 is complete, because the project memory files are currently too stale to safely guide a new agent.

## Safety Boundaries

- This roadmap is a **human-read-only** artifact.
- It does not create, modify, or execute trading logic, exchange connections, API calls, or Freqtrade behavior.
- It does not claim production readiness, trading readiness, approval, certification, recommendation, or suitability.
- It preserves the original master plan as historical context and does not overwrite it.
- `data/`, `reports/`, and the untracked `src/hunter/cross_artifact_consistency/` directory are excluded local artifact areas; they remain opaque and untouched.
- The missing `v0.32.0-dev` tag is recorded as an anomaly only; no automatic tag creation is performed.
