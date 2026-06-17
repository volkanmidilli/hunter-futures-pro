# Hunter Futures Pro

Hunter Futures Pro is an agent-first crypto futures research, validation and execution-control platform.

It is designed to be developed and operated with WrongStack as the primary CLI AI agent.

## Core Mission

Find the right futures pairs, in the right market regime, with the right relative strength, healthy futures positioning, acceptable risk, and then allow Freqtrade to execute only when conditions are valid.

## Key Principles

- WrongStack is the main development and project orchestration agent.
- Kimi K2.7 is the preferred model backend.
- Freqtrade is only the execution layer.
- Hunter Futures Pro is the decision layer.
- No live trading by default.
- Every decision must have a score, reason and rejection code.
- Every project phase must be documented for future AI handoff.
- Old strategies are benchmarks only, not architectural constraints.

## Initial Scope

MVP-0 focuses on:

- repository foundation
- documentation memory system
- agent workflow files
- safety-first project rules
- initial architecture specification

MVP-1 will add:

- data foundation
- regime engine
- breadth engine

## Project Memory Files

AI agents must read these files first:

1. `AGENTS.md`
2. `.wrongstack/AGENTS.md`
3. `PROJECT.md`
4. `docs/handoff/CURRENT_STATE.md`
5. `specs/SPEC-001-Agent-First-Hunter-Futures-Foundation.md`
6. `tasks/active.md`
7. `tasks/agent-log.md`

## Safety

This project must not enable live trading unless explicitly approved by the human operator.

Missing data, stale regime files, invalid JSON, unknown universe or failed validation must block new entries.
