# Active Task

## Current Task

MVP-8 Step 5 — Final Review.

## Status

Not started. Review is not started yet.

MVP-8 Step 4 is complete. All 1491 tests pass. Version 0.7.0-dev.
SPEC-009 design is finalized and polished. All MVP-8 Step 4 integration tests complete.

## Scope

Step 5 action:
- Review only, no implementation unless a defect is found.

Step 5 allowed work:
- Review SPEC-009 against implementation.
- Review models, engine, writer, integration tests.
- Run full test suite.
- Check git status.
- Verify safety constraints.
- Produce final review verdict.

Step 5 not allowed:
- No new features.
- No config YAML.
- No JSON schema.
- No deployable Freqtrade strategy class.
- No Freqtrade runtime connection.
- No Binance.
- No real exchange connection.
- No API keys.
- No live trading.
- No real orders.
- No leverage.
- No shorting.
- No real entry/exit execution logic.

## Not Allowed

- No Binance integration.
- No real exchange connection.
- No API keys.
- No live trading.
- No real order execution.
- No leverage.
- No shorting.
- No real entry/exit execution logic.
- No deployable Freqtrade strategy class.
- No Freqtrade runtime connection.
- No config YAML.
- No JSON schema.
- No new features unless a defect is found.

## Previous Task

MVP-8 Step 4 — Dry-Run Strategy Runtime Integration Tests (complete).
- `tests/test_dry_run_strategy/test_integration.py` — 48 integration tests, all passing.
  - Long research happy path: DRY_RUN_READY + LONG_RESEARCH_ONLY + ALLOW_LONG_RESEARCH_SIGNAL → EXPOSE_LONG_RESEARCH_SIGNAL, JSON round-trip verified.
  - Short research happy path: DRY_RUN_READY + SHORT_RESEARCH_ONLY + ALLOW_SHORT_RESEARCH_SIGNAL → EXPOSE_SHORT_RESEARCH_SIGNAL, JSON round-trip verified.
  - Missing adapter decision context: None input → MISSING_ADAPTER_DECISION_CONTEXT, BLOCK_SIGNAL.
  - Invalid adapter decision context: missing attrs → INVALID_ADAPTER_DECISION_CONTEXT, BLOCK_SIGNAL.
  - Adapter BLOCKED state → ADAPTER_NOT_DRY_RUN_READY, BLOCK_SIGNAL.
  - Adapter UNKNOWN state → ADAPTER_NOT_DRY_RUN_READY, BLOCK_SIGNAL.
  - Adapter DISABLED state → ADAPTER_NOT_DRY_RUN_READY, BLOCK_SIGNAL.
  - Adapter BLOCK_ALL mode → ADAPTER_MODE_BLOCK_ALL, BLOCK_SIGNAL.
  - Adapter BLOCK_SIGNAL intent → ADAPTER_SIGNAL_BLOCKED, BLOCK_SIGNAL.
  - dry_run false → DRY_RUN_DISABLED, BLOCK_SIGNAL.
  - live_trading_enabled true → LIVE_TRADING_ENABLED, BLOCK_SIGNAL.
  - real_orders_enabled true → REAL_ORDERS_ENABLED, BLOCK_SIGNAL.
  - leverage_enabled true → LEVERAGE_ENABLED, BLOCK_SIGNAL.
  - shorting_enabled true → SHORTING_ENABLED, BLOCK_SIGNAL.
  - Stale adapter decision context → STALE_ADAPTER_DECISION_CONTEXT, BLOCK_SIGNAL.
  - Unsupported adapter mode → UNSUPPORTED_ADAPTER_MODE, BLOCK_SIGNAL.
  - Unsupported signal intent → UNSUPPORTED_ADAPTER_SIGNAL_INTENT, BLOCK_SIGNAL.
  - Writer integration: parent directory creation, valid JSON with deterministic top-level keys, safety flags verification, blocked context JSON output.
  - Safety integration assertions: no production data path writes, no network calls, no Freqtrade runtime, no Binance, no real exchange, no API keys, no live trading, no leverage, no shorting, no real entry/exit execution logic.
- Full suite: 1491 tests passing.
- No model changes, no engine changes, no writer changes, no __init__.py changes.
- No config YAML, no JSON schema, no deployable Freqtrade strategy class, no Freqtrade runtime connection, no Binance, no real exchange connection, no API keys, no live trading, no real orders, no leverage, no shorting, no real entry/exit execution logic.

## Definition of Done

- [ ] SPEC-009 reviewed against implementation.
- [ ] Models reviewed.
- [ ] Engine reviewed.
- [ ] Writer reviewed.
- [ ] Integration tests reviewed.
- [ ] Full test suite passes.
- [ ] Safety constraints verified.
- [ ] Final review verdict produced.
- [ ] No new features, config, schema, or strategy class created.
- [ ] All safety constraints preserved.

## Next Step

MVP-8 complete — commit and tag version 0.8.0-dev (after Step 5 review).

