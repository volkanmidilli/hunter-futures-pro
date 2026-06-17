# Agent Log

This file records important human and AI agent actions.

Every AI agent must update this file after completing a task.

## Entry Format

Each entry should use this format:

Date:
Agent:
Task:
Files changed:
Summary:
Risks:
Next step:

---

## Entries

### 0.1.0 — Foundation Start

Date: 2026-06-17

Agent: Human + ChatGPT + WrongStack

Task: Create initial MVP-0 project foundation.

Files changed:

- README.md
- PROJECT.md
- AGENTS.md
- docs/handoff/CURRENT_STATE.md
- docs/architecture/SYSTEM_OVERVIEW.md
- docs/operations/RUNBOOK.md
- docs/operations/TROUBLESHOOTING.md
- docs/operations/FAILURE_MODES.md
- docs/decisions/ADR-0001-agent-first-project.md
- docs/decisions/ADR-0002-freqtrade-as-execution-layer.md
- docs/decisions/ADR-0003-external-hunter-reference.md
- specs/SPEC-001-Agent-First-Hunter-Futures-Foundation.md
- tasks/backlog.md
- tasks/active.md
- tasks/agent-log.md
- CHANGELOG.md
- VERSION
- .wrongstack/AGENTS.md

Summary:

Initial project direction was clarified.

Hunter Futures Pro will be developed as an agent-first crypto futures research and execution-control platform.

WrongStack will be used as the main CLI AI agent.

Kimi K2.7 will be used as the preferred model/backend.

Freqtrade will be used only as the execution layer.

Old strategies are benchmarks only.

All MVP-0 foundation files were created and reviewed.

Risks:

- Trading logic must not be added yet.
- Binance integration must not be added yet.
- Freqtrade integration must not be added yet.
- Live trading must stay disabled.

Next step:

Review git diff and commit initial foundation.

---

### 0.1.0 — Foundation Commit

Date: 2026-06-17

Agent: WrongStack

Task: Commit initial MVP-0 foundation.

Commit message:

feat: add MVP-0 agent-first project foundation

Files changed:

All MVP-0 foundation files.

Summary:

Initial MVP-0 foundation committed to repository.

Risks:

- Trading logic must not be added yet.
- Binance integration must not be added yet.
- Freqtrade integration must not be added yet.
- Live trading must stay disabled.

Next step:

MVP-1 planning: Data Foundation.

---

### 0.2.0-dev — SPEC-002 Review

Date: 2026-06-17

Agent: WrongStack (Director-led multi-agent review)

Task: Review SPEC-002 MVP-1 Data Foundation design.

Files changed:

- specs/SPEC-002-MVP-1-Data-Foundation.md (reviewed and updated)
- docs/handoff/CURRENT_STATE.md (updated)

Summary:

SPEC-002 was reviewed by three internal roles:
- Architect Agent: Confirmed architecture fit, Freqtrade remains execution-only, no trading logic
- Data Engineer Agent: Verified implementability, identified 8 fixes needed
- Review Agent: Confirmed all safety constraints met, no Binance/keys/live trading

All 8 fixes applied:
1. .gitignore specification added
2. Test directory moved to repo root (standard pytest)
3. DataStorage ABC interface defined with SQLite stub
4. validate_config() extracted for testable safety checks
5. Config merge uses safe Pydantic model_copy
6. Missing SQLite index on long_short_ratio added
7. Dependencies specified (pydantic, pyyaml, pytest, etc.)
8. CLI entry point and __version__ export defined

SPEC-002 is now ready for implementation.

Risks:

- Trading logic must not be added yet.
- Binance integration must not be added yet.
- Freqtrade integration must not be added yet.
- Live trading must stay disabled.
- Implementation must follow SPEC-002 design without deviation from safety rules.

Next step:

Begin MVP-1 implementation: create Python project structure from SPEC-002.

---

### 0.2.0-dev — MVP-1 Step 1: Python Project Skeleton

Date: 2026-06-17

Agent: WrongStack

Task: Create MVP-1 Python project skeleton (directories, __init__.py, pyproject.toml, .gitignore).

Files changed:

- src/hunter/__init__.py (updated __version__ to "0.2.0-dev")
- src/hunter/config/__init__.py (created)
- src/hunter/data/__init__.py (created)
- src/hunter/core/__init__.py (created)
- src/hunter/engines/__init__.py (created)
- tests/__init__.py (created)
- tests/test_config/__init__.py (created)
- tests/test_data/__init__.py (created)
- tests/test_core/__init__.py (created)
- tests/fixtures/__init__.py (created)
- pyproject.toml (created with metadata and dependencies)
- requirements.txt (created)
- requirements-dev.txt (created)
- .gitignore (updated per SPEC-002)
- CHANGELOG.md (updated)

Summary:

Created Python project skeleton following SPEC-002 section 1. Package structure includes hunter (config, data, core, engines) and tests at repo root. Dependencies: pydantic>=2.0.0, pyyaml>=6.0, pytest>=7.0.0, pytest-asyncio>=0.21.0. .gitignore excludes secrets, runtime data, and local config. No CLI, no config loader, no logging, no collector, no storage created yet.

Risks:

- Trading logic must not be added yet.
- Binance integration must not be added yet.
- Freqtrade integration must not be added yet.
- Live trading must stay disabled.
- No actual data collection implemented (collection.enabled: false by design).

Next step:

MVP-1 Step 2: Implement config Pydantic models and loader with validate_config().

---

### 0.2.0-dev — MVP-1 Step 2: Config Models and Validation

Date: 2026-06-17

Agent: WrongStack

Task: MVP-1 Step 2 — Config Models and Validation.

Files changed:

- src/hunter/config/models.py (created)
- src/hunter/config/loader.py (created)
- src/hunter/config/__init__.py (updated)
- configs/data.yaml (created)
- configs/local.example.yaml (created)
- tests/test_config/test_models.py (created)
- tests/test_config/test_loader.py (created)

Summary:

Added Pydantic config models, config loader, validate_config(), safe defaults, fail-closed checks, config examples and config tests. Renamed config/ to configs/ to match project standard.

Safety:

- No Binance connection.
- No Freqtrade integration.
- No live trading.
- No API keys.
- trading.enabled and trading.live_enabled fail closed if true.

Next step:

MVP-1 Step 3 — Logging structure.

---

### 0.2.0-dev — MVP-1 Step 6: Final Safety Tests and MVP-1 Completion

Date: 2026-06-17

Agent: WrongStack

Task: MVP-1 Step 6 — Final Safety Tests and MVP-1 Completion.

Commit: dd3ea99

Files changed:

- src/hunter/config/loader.py (fixed load_config to return HunterConfig, fixed secret detection)
- tests/test_config/test_loader.py (fixed secret tests, added TestContainsSecrets)
- tests/test_core/test_logging.py (added import sys, fixed log level test)

Summary:

Final MVP-1 review found config loader and test issues.
Fixed load_config() to return HunterConfig, fixed secret detection tests, fixed logging tests.
Full test suite now passes with 91 tests.
MVP-1 is ready to mark complete.

Safety:

- No Binance connection.
- No Freqtrade integration.
- No HTTP requests.
- No live trading.
- No API keys.
- No trading logic.

Next step:

MVP-2 Market State design.

---

### 0.3.0-dev — SPEC-003 MVP-2 Market State Design

Date: 2026-06-17

Agent: WrongStack

Task: SPEC-003 — MVP-2 Market State Design.

Files changed:

- specs/SPEC-003-Market-State-Regime-Breadth.md (created and refined)
- CHANGELOG.md (updated)
- docs/handoff/CURRENT_STATE.md (updated)
- tasks/active.md (updated)

Summary:

Created and refined SPEC-003 for Regime Engine and Market Breadth Engine.

Added deterministic scoring formulas:
- btc_trend_score = bullish_conditions_met / total_btc_conditions * 100
- bearish_btc_trend_score = bearish_conditions_met / total_btc_conditions * 100
- eth_trend_score (same formula, 0 if ETH missing)
- breadth_confirmation_score = confirming_conditions_met / total_breadth_conditions * 100
- confidence = min(primary_score, confirmation_score) / 100
- breadth_score = weighted sum of 6 percentage metrics, clamped 0-100

Added EMA slope formula: ema_slope_pct = ((ema_current - ema_n_candles_ago) / ema_n_candles_ago) * 100

Added pipeline order: Breadth Engine first, then Regime Engine with breadth age guard.

Added timeframe-aware stale data: stale_threshold_candles: 2 with timeframe_duration multiplier.

Added universe filtering rules (include USDT perpetuals, exclude stablecoins/leveraged tokens/BUSD).

Added invalid symbol definition (7 conditions).

Added configs/market_state.yaml as single config standard.

Added JSON Schema design section for future schema files.

Added MVP-1 interface references (DataStorage ABC, SQLiteStorage, KlineData, HunterConfig).

Added ETH_DATA_UNAVAILABLE to reason codes.

Added recent_return_days: 7 to config.

Safety:

- No code implemented.
- No Binance connection.
- No Freqtrade integration.
- No trading logic.
- No live trading.
- Fail-closed behavior preserved: all bad data → UNKNOWN + NONE + confidence 0.

Next step:

MVP-2 Step 1 — Market State Models.
