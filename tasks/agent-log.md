# Agent Log

This file records important human and AI agent actions.

Every AI agent must update this file after completing a task.

## Entry Format

Each entry should use this format:

Date:
Agent:
Task:
Files changed:
Summary:
Risks:
Next step:

---

## Entries

### 0.1.0 — Foundation Start

Date: 2026-06-17

Agent: Human + ChatGPT + WrongStack

Task: Create initial MVP-0 project foundation.

Files changed:

- README.md
- PROJECT.md
- AGENTS.md
- docs/handoff/CURRENT_STATE.md
- docs/architecture/SYSTEM_OVERVIEW.md
- docs/operations/RUNBOOK.md
- docs/operations/TROUBLESHOOTING.md
- docs/operations/FAILURE_MODES.md
- docs/decisions/ADR-0001-agent-first-project.md
- docs/decisions/ADR-0002-freqtrade-as-execution-layer.md
- docs/decisions/ADR-0003-external-hunter-reference.md
- specs/SPEC-001-Agent-First-Hunter-Futures-Foundation.md
- tasks/backlog.md
- tasks/active.md
- tasks/agent-log.md
- CHANGELOG.md
- VERSION
- .wrongstack/AGENTS.md

Summary:

Initial project direction was clarified.

Hunter Futures Pro will be developed as an agent-first crypto futures research and execution-control platform.

WrongStack will be used as the main CLI AI agent.

Kimi K2.7 will be used as the preferred model/backend.

Freqtrade will be used only as the execution layer.

Old strategies are benchmarks only.

All MVP-0 foundation files were created and reviewed.

Risks:

- Trading logic must not be added yet.
- Binance integration must not be added yet.
- Freqtrade integration must not be added yet.
- Live trading must stay disabled.

Next step:

Review git diff and commit initial foundation.

---

### 0.1.0 — Foundation Commit

Date: 2026-06-17

Agent: WrongStack

Task: Commit initial MVP-0 foundation.

Commit message:

feat: add MVP-0 agent-first project foundation

Files changed:

All MVP-0 foundation files.

Summary:

Initial MVP-0 foundation committed to repository.

Risks:

- Trading logic must not be added yet.
- Binance integration must not be added yet.
- Freqtrade integration must not be added yet.
- Live trading must stay disabled.

Next step:

MVP-1 planning: Data Foundation.
