# AGENTS.md

This file explains how any AI agent should work on Hunter Futures Pro.

## Project Identity

Hunter Futures Pro is an agent-first crypto futures research and execution-control platform.

The project uses:

- WrongStack as the main CLI AI agent
- Kimi K2.7 as the preferred model/backend
- Freqtrade only as the execution layer

Hunter Futures Pro is the decision layer.

Freqtrade is not the brain of the system.

## Main Direction

This project is not tied to any old trading strategy.

Old strategies are allowed only as benchmarks.

The project must be built step by step.

Every important project decision must be written into repository files.

A future AI agent should be able to understand the project without reading old chat history.

## Required Reading Order

Before changing anything, every AI agent must read:

1. README.md
2. PROJECT.md
3. AGENTS.md
4. docs/handoff/CURRENT_STATE.md
5. tasks/active.md
6. tasks/agent-log.md

If one of these files is missing, the agent must report it before continuing.

## Agent Rules

Every AI agent must:

- work from the current project phase
- make small and reviewable changes
- update documentation after important changes
- update tasks/agent-log.md after work
- explain what changed
- explain what should happen next
- keep the project understandable for future AI agents

## Safety Rules

Do not:

- enable live trading by default
- add API keys
- add exchange secrets
- add private keys
- commit credentials
- approve real production trading pairs automatically
- remove safety checks
- bypass stale data checks
- make Freqtrade execute trades without Hunter approval

## Trading Safety Policy

Missing data must block execution.

Stale data must block execution.

Unknown market regime must block execution.

Invalid Hunter output must block execution.

Every allowed or blocked decision must have a clear reason.

## Development Workflow

For every task:

1. Read the required context files.
2. Understand the current phase.
3. Make only the requested change.
4. Update documentation if needed.
5. Update tasks/agent-log.md.
6. Summarize the result.
7. Suggest the next small step.

## Autonomous MVP Workflow

When continuing work on an MVP:

1. Read the current state:
   - `ROADMAP.md`
   - `docs/MVP_INDEX.md`
   - `docs/handoff/CURRENT_STATE.md`
   - `tasks/active.md`
   - The latest approved SPEC for the current MVP

2. Determine:
   - Current MVP and step
   - Last known commit
   - Allowed files
   - Required tests

3. Implement only the current step. Do not expand scope.

4. Run focused tests for the step, then run the full test suite before reporting completion.

5. Self-review against the SPEC and the boundaries listed below.

6. Fix blockers and rerun tests. If a blocker cannot be resolved within scope, stop and report.

7. Stop before commit.

8. Stop before tag.

9. Produce a final report with files changed, summary, boundary, and residual deviations.

### Commit and Tag Policy

- Never commit automatically.
- Never tag automatically.
- The human must provide the exact commit or tag command.

### Autonomous Safety Rules

- Do not inspect or traverse `data/` or `reports/`.
- Do not connect to exchanges, APIs, networks, or Freqtrade runtime.
- Do not start Web UIs, servers, databases, schedulers, or daemons.
- Do not emit trading signals or action commands.
- Do not make production-readiness, trading-readiness, approval, certification, recommendation, or suitability claims.
- Keep artifact refs as opaque strings; do not open, follow, validate, or execute them.

## Current MVP Context

- Completed MVP: MVP-57 Portfolio Construction Research Adapter
- Active MVP: None; next MVP not selected
- SPEC: `specs/SPEC-058-Portfolio-Construction-Research-Adapter.md` — approved during MVP-57 cycle
- Implementation (Steps 1–6: models, validator, allocator, engine, writer, integration tests, docs/version finalization): committed during MVP-57 cycle
- Tagged `v0.57.0-dev` pending (local-only; no push)
- Latest tag: `v0.56.0-dev` (MVP-56 tagged); `v0.57.0-dev` pending
- Tag policy: never tag automatically; the human must provide the exact tag or commit command.
- Safety: autonomous workflow only touches docs/version/task memory in finalization steps; no runtime code changes, no tests changed, no data/reports inspection, no trading/API/Freqtrade/server/database/scheduler changes, no production-readiness, trading-readiness, approval, certification, recommendation, or suitability claims.
