# ADR-0001 — Agent-First Project Direction

## Status

Accepted

## Context

Hunter Futures Pro will be developed with AI agents as a central part of the workflow.

The main development agent will be WrongStack.

Kimi K2.7 will be used as the preferred model/backend.

The project must be understandable by future AI agents without relying on old chat history.

This means important project context must live inside repository files.

## Decision

Hunter Futures Pro will be an agent-first project.

All important context, decisions, tasks and safety rules must be documented in the repository.

Required project memory files include:

- README.md
- PROJECT.md
- AGENTS.md
- .wrongstack/AGENTS.md
- docs/handoff/CURRENT_STATE.md
- docs/architecture/SYSTEM_OVERVIEW.md
- docs/operations/RUNBOOK.md
- docs/operations/TROUBLESHOOTING.md
- docs/operations/FAILURE_MODES.md
- tasks/backlog.md
- tasks/active.md
- tasks/agent-log.md
- CHANGELOG.md
- VERSION

## Consequences

Future AI agents should be able to understand:

- what the project is
- what phase the project is in
- what has been decided
- what must not be done
- what should happen next

Every major task should update the project memory files.

No important project decision should exist only in chat history.

## Safety Notes

Agent-first does not mean fully autonomous live trading.

WrongStack may help build, review and document the project.

WrongStack must not enable live trading unless the human operator explicitly approves it.
