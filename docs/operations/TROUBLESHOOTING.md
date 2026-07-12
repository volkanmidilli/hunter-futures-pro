# Troubleshooting

## Project

Hunter Futures Pro

## Purpose

This file lists common problems and what to check first.

## Current Phase

The original master plan (MVP-0 through MVP-4) is complete. The expanded MVP chain has reached MVP-46 / v0.46.0-dev. Current active work is MVP-47 — Cross-Artifact Consistency Engine (complete, finalization pending).

## Problem: AI agent cannot understand the project

Check that these files exist and are up to date:

- `README.md`
- `PROJECT.md`
- `AGENTS.md`
- `.wrongstack/AGENTS.md`
- `ROADMAP.md`
- `docs/MVP_INDEX.md`
- `docs/handoff/CURRENT_STATE.md`
- `docs/architecture/SYSTEM_OVERVIEW.md`
- `tasks/backlog.md`
- `tasks/active.md`
- `tasks/agent-log.md`
- `CHANGELOG.md`
- `VERSION`

If files are missing or clearly out of date (e.g., VERSION says 0.1.0 but HEAD is at v0.47.0-dev (pending tag)), align them before proceeding.

## Problem: Stale project memory

If `docs/handoff/CURRENT_STATE.md`, `tasks/active.md`, `VERSION`, or `pyproject.toml` do not match the current tagged state:

- Check `git tag --list "v0.*-dev"` for the latest tag.
- Check `git log --oneline -1 --decorate` for HEAD position.
- Check `ROADMAP.md` and `docs/MVP_INDEX.md` for the canonical timeline.
- Update the stale file to match the evidence. This is documentation-only work.

## Problem: Version mismatch

If `VERSION` or `pyproject.toml` version disagrees with the latest `v0.*-dev` tag:

- The version information in these files is stale. Align to the latest tag.
- This is a documentation-only change. No runtime behavior is affected.

## Problem: Missing v0.32.0-dev tag

The tag `v0.32.0-dev` is absent from the tag list even though the MVP-32 finalization commit exists. This is a recorded anomaly.

- Do not create the tag automatically.
- Document the anomaly and proceed.
- A separate human decision is required to create the tag retroactively.

## Problem: Agent drift — wrong active task

If an agent starts work that does not match the current active task in `tasks/active.md`:

- Stop.
- Read `tasks/active.md` and `docs/handoff/CURRENT_STATE.md`.
- Confirm the correct active task before continuing.
- If the active task file is stale, update it to match the current reality.

## Problem: Mismatch between original master plan and expanded MVP chain

The original plan (MVP-0 through MVP-4) is documented in `PROJECT.md`, `README.md`, and `tasks/backlog.md`. The actual repository has expanded well beyond that plan to MVP-47.

- Do not try to force the expanded chain back into the original plan.
- Document both: the original plan as historical context, and the expanded chain as what was actually built.
- See `ROADMAP.md` and `docs/MVP_INDEX.md` for the two-track documentation.

## Problem: Excluded local artifact areas

The directories `data/` and `reports/` are pre-existing local artifact areas. They are excluded from all audit actions and documentation updates.

- Do not inspect, traverse, read, summarize, validate, or modify these directories.
- References to paths inside them are opaque strings only.
- If an agent attempts to access these directories, stop and re-read this policy.

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

- `.wrongstack/AGENTS.md`

Then ask WrongStack to read:

- README.md
- PROJECT.md
- AGENTS.md
- .wrongstack/AGENTS.md
- ROADMAP.md
- docs/MVP_INDEX.md
- docs/handoff/CURRENT_STATE.md
- tasks/active.md
- tasks/agent-log.md

## Problem: Agent tries to write trading/execution logic when not approved

Stop the task.

Agents must not:

- connect to Binance or any exchange
- connect to Freqtrade runtime
- create API keys or secrets
- write execution logic
- enable live trading
- inspect `data/` or `reports/`

The only approved work is documented in the active task file.

## Problem: Project state is unclear

Open:

- `ROADMAP.md`
- `docs/MVP_INDEX.md`
- `docs/handoff/CURRENT_STATE.md`
- `tasks/active.md`
- `tasks/agent-log.md`

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
