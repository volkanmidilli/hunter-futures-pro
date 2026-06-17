# Troubleshooting

## Project

Hunter Futures Pro

## Purpose

This file lists common problems and what to check first.

## Current Phase

MVP-0 — Project foundation

At this phase, most problems are related to missing files, wrong filenames or incomplete documentation.

## Problem: AI agent cannot understand the project

Check that these files exist:

- README.md
- PROJECT.md
- AGENTS.md
- .wrongstack/AGENTS.md
- docs/handoff/CURRENT_STATE.md
- docs/architecture/SYSTEM_OVERVIEW.md
- tasks/backlog.md
- tasks/active.md
- tasks/agent-log.md
- CHANGELOG.md
- VERSION

## Problem: File names are wrong

Linux is case-sensitive.

Correct names:

- README.md
- PROJECT.md
- AGENTS.md
- CHANGELOG.md
- VERSION

Incorrect examples:

- readme.md
- project.md
- agents.md
- version

If filenames are wrong, rename them before continuing.

## Problem: WrongStack starts but does not follow project rules

Check that this file exists:

- .wrongstack/AGENTS.md

Then ask WrongStack to read:

- README.md
- PROJECT.md
- AGENTS.md
- .wrongstack/AGENTS.md
- docs/handoff/CURRENT_STATE.md
- tasks/active.md
- tasks/agent-log.md

## Problem: Agent tries to write trading logic too early

Stop the task.

MVP-0 allows documentation and project foundation only.

The agent must not:

- connect to Binance
- connect to Freqtrade
- create API keys
- write execution logic
- enable live trading

## Problem: Project state is unclear

Open:

- docs/handoff/CURRENT_STATE.md
- tasks/active.md
- tasks/agent-log.md

These files should explain:

- current phase
- current task
- what exists
- what does not exist
- next step

## Problem: Safety rules are missing

Check:

- AGENTS.md
- .wrongstack/AGENTS.md
- docs/operations/RUNBOOK.md
- docs/handoff/CURRENT_STATE.md

Safety rules must clearly say:

- no live trading by default
- no API keys in repository
- missing data blocks execution
- stale data blocks execution
- unknown regime blocks execution

## Emergency Rule

If the problem is unclear, stop and ask for human review.
