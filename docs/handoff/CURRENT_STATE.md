# Current State

## Project

Hunter Futures Pro

## Version

0.2.0-dev

## Current Phase

MVP-1 — Data Foundation (design complete, implementation pending)

## Current Status

MVP-0 foundation is complete and committed.

MVP-1 Step 1 (Python Project Skeleton) is complete and committed.

MVP-1 Step 2 (Config Models and Validation) is complete and committed:
- Pydantic config models: TradingConfig, CollectionConfig, StorageConfig, LoggingConfig, HunterConfig
- Config loader with safe override hierarchy (YAML file, env var)
- validate_config() with fail-closed validation (trading.enabled, trading.live_enabled, secrets)
- Safe defaults: trading.enabled: false, trading.live_enabled: false, collection.enabled: false
- Config files: configs/data.yaml (safe defaults), configs/local.example.yaml (warnings)
- Config directory standard: configs/ (not config/)
- Config tests: 23 tests for safe defaults, validation failures, and YAML loading

The project currently contains documentation, design specifications, and config implementation only.

No trading logic exists yet.

No Binance connection exists yet.

No Freqtrade integration exists yet.

No live trading is enabled.

MVP-1 Step 3 (Logging Structure) is complete and committed:
- src/hunter/core/logging.py with JSONFormatter, RedactingFilter, setup_logging()
- JSONFormatter outputs structured JSON with timestamp, level, logger, message, correlation_id, context, exception info
- RedactingFilter recursively redacts secrets (api_key, secret, password, token, private_key) in dicts and lists
- setup_logging() with console handler (text or JSON) and rotating file handler (always JSON, 10MB/5 backups)
- tests/test_core/test_logging.py with 18 tests for formatting, redaction, and setup behavior
- Log secret redaction applied to file handler only

No data collector exists yet.

No storage layer exists yet.

No CLI exists yet.

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

MVP-1 Step 4 — Data collector interface.
