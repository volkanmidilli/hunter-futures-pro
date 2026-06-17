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

## Current Phase

MVP-0 — Project foundation.

No trading logic should be implemented in this phase.

No Binance connection should be implemented in this phase.

No Freqtrade integration should be implemented in this phase.
