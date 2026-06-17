# Runbook

## Project

Hunter Futures Pro

## Purpose

This runbook explains how a human or AI agent should operate the project safely.

## Current Phase

MVP-0 — Project foundation

At this phase, the project only contains documentation and project memory files.

No trading logic exists yet.

## Safe Startup Checklist

Before doing any work, read:

1. README.md
2. PROJECT.md
3. AGENTS.md
4. .wrongstack/AGENTS.md
5. docs/handoff/CURRENT_STATE.md
6. docs/architecture/SYSTEM_OVERVIEW.md
7. tasks/active.md
8. tasks/agent-log.md

## WrongStack Startup

Open the project folder.

Start WrongStack from the project root.

WrongStack must first review the project files.

WrongStack must not write trading logic during MVP-0.

## Working Rules

For every task:

1. Read the current project state.
2. Confirm the current phase.
3. Make only the requested change.
4. Update documentation if needed.
5. Update tasks/agent-log.md.
6. Summarize what changed.
7. Suggest the next small step.

## Safety Rules

Never:

- enable live trading
- store API keys
- store exchange secrets
- connect to Binance during MVP-0
- connect to Freqtrade during MVP-0
- create production trading rules during MVP-0

## Future Runtime Safety

When trading-related modules exist, the system must fail closed.

This means:

- missing data blocks execution
- stale data blocks execution
- invalid JSON blocks execution
- unknown regime blocks execution
- unapproved pair blocks execution

## Emergency Rule

If an agent is unsure whether an action is safe, it must stop and ask for human confirmation.
