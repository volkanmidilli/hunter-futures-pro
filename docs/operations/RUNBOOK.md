# Runbook

## Project

Hunter Futures Pro

## Purpose

This runbook explains how a human or AI agent should operate the project safely.

## Current Phase

v0.71.0-rc.2 — Research-only, deterministic, reproducible quantitative research framework with real Freqtrade backtesting compatibility (Phase B.2 complete). The original master plan (MVP-0 through MVP-4) and expanded MVP chain (MVP-5 through MVP-70) are complete. Phase A (conformance/safety) and Phase B (fixture validation, real compatibility, ZIP safety) are tagged.

No live trading is enabled. No exchange connections are active. MVP-71 not started.

## Safe Startup Checklist

Before doing any work, read these files in this order:

1. `README.md` — project summary
2. `PROJECT.md` — canonical project specification
3. `AGENTS.md` — agent work rules
4. `.wrongstack/AGENTS.md` — WrongStack instructions
5. `ROADMAP.md` — complete project timeline
6. `docs/MVP_INDEX.md` — deterministic MVP-to-package mapping
7. `docs/handoff/CURRENT_STATE.md` — current documented state
8. `docs/architecture/SYSTEM_OVERVIEW.md` — current layered architecture
9. `tasks/active.md` — current active task
10. `tasks/agent-log.md` — recent agent activity

## Working Rules

For every task:

1. Read the current project state from the files above.
2. Confirm the active task matches what you are about to do.
3. Make only the requested change. Do not expand scope.
4. Do not modify `data/` or `reports/`.
5. Do not write trading logic, exchange connections, API calls, or Freqtrade runtime code unless explicitly approved by the master plan.
6. Update documentation if needed after the change.
7. Summarize what changed and suggest the next small step.
8. Use the review-before-commit workflow: read the diff, check for scope creep, then commit.

## Safety Rules

Never:

- enable live trading
- store API keys or exchange secrets in the repository
- connect to Binance or any exchange
- connect to Freqtrade runtime
- create production trading rules
- inspect `data/` or `reports/`
- claim production readiness, trading readiness, approval, certification, recommendation, or suitability

## Future Runtime Safety

When trading-related modules exist or are added, the system must fail closed. This means:

- missing data blocks execution
- stale data blocks execution
- invalid JSON blocks execution
- unknown regime blocks execution
- unapproved pair blocks execution

## Emergency Rule

If an agent is unsure whether an action is safe, it must stop and ask for human confirmation.
