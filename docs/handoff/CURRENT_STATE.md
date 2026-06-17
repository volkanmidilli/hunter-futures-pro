# Current State

## Project

Hunter Futures Pro

## Version

0.1.0

## Current Phase

MVP-0 — Project foundation

## Current Status

The project foundation is being created.

The project currently contains basic documentation only.

No trading logic exists yet.

No Binance connection exists yet.

No Freqtrade integration exists yet.

No live trading is enabled.

## Existing Files

- README.md
- PROJECT.md
- AGENTS.md
- docs/handoff/CURRENT_STATE.md

## Main Project Direction

Hunter Futures Pro is an agent-first crypto futures research and execution-control platform.

WrongStack will be used as the main CLI AI agent.

Kimi K2.7 will be used as the preferred model/backend.

Freqtrade will be used only as the execution layer.

Hunter Futures Pro will be the decision layer.

## Important Decisions

- The project is not tied to any old trading strategy.
- Old strategies are benchmarks only.
- Freqtrade is not the brain of the system.
- Hunter Futures Pro decides whether execution should be allowed.
- Every important decision must be documented.
- Future AI agents must be able to understand the project from repository files.

## What Does Not Exist Yet

- Python project structure
- data collector
- Binance Futures integration
- regime engine
- market breadth engine
- relative strength engine
- open interest engine
- discovery engine
- portfolio engine
- decision gate engine
- reporting layer
- Freqtrade execution guard
- tests

## Safety Status

Live trading is disabled by policy.

No API keys should be stored in this repository.

No exchange secrets should be stored in this repository.

Missing data should block execution in future trading logic.

Stale data should block execution in future trading logic.

Unknown market regime should block execution in future trading logic.

## Next Step

Finalize MVP-0 cleanup, review git diff, then commit initial foundation.
