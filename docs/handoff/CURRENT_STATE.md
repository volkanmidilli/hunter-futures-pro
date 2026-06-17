# Current State

## Project

Hunter Futures Pro

## Version

0.2.0-dev

## Current Phase

MVP-1 — Data Foundation (design complete, implementation pending)

## Current Status

MVP-0 foundation is complete and committed.

SPEC-002 MVP-1 Data Foundation design is complete and reviewed. All 8 review fixes applied:
- .gitignore specification added
- DataStorage ABC interface defined
- Missing SQLite index added
- validate_config() extracted for testability
- Config merge uses safe model_copy
- Dependencies specified (pydantic, pyyaml, pytest)
- CLI entry point and __version__ export defined
- Test directory standardized to repo root

The project currently contains documentation and design specifications only.

No trading logic exists yet.

No Binance connection exists yet.

No Freqtrade integration exists yet.

No live trading is enabled.

## Existing Files

- README.md
- PROJECT.md
- AGENTS.md
- .wrongstack/AGENTS.md
- docs/handoff/CURRENT_STATE.md
- docs/architecture/SYSTEM_OVERVIEW.md
- docs/operations/RUNBOOK.md
- docs/operations/TROUBLESHOOTING.md
- docs/operations/FAILURE_MODES.md
- docs/decisions/ADR-0001-agent-first-project.md
- docs/decisions/ADR-0002-freqtrade-as-execution-layer.md
- docs/decisions/ADR-0003-external-hunter-reference.md
- specs/SPEC-001-Agent-First-Hunter-Futures-Foundation.md
- specs/SPEC-002-MVP-1-Data-Foundation.md
- tasks/backlog.md
- tasks/active.md
- tasks/agent-log.md
- CHANGELOG.md
- VERSION

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

MVP-1 planning: Data Foundation.
