# Active Task

## Current Task

MVP-7 Step 5 — Final Review and Polish.

## Status

Not started. Awaiting approval.

MVP-7 Step 4 is complete. 45 new tests. 1214 total. Version 0.6.0-dev.
SPEC-008 design is finalized and polished. All MVP-7 integration tests implemented.

## Scope

Step 5 allowed work:
- Review SPEC-008 compliance.
- Run full pytest.
- Verify models, engine, writer, integration tests.
- Verify fail-closed behavior.
- Verify writer atomic output behavior.
- Verify no unsafe integration exists.
- Small polish fixes only if verified.

Step 5 not allowed:
- No new features.
- No config YAML.
- No JSON schema.
- No deployable strategy class.
- No Freqtrade runtime.
- No Binance.
- No API keys.
- No live trading.
- No real orders.
- No leverage.
- No shorting.
- No entry/exit execution logic.

## Previous Task

MVP-7 Step 4 — Strategy Adapter Integration Tests (complete).
- 1 file created: `tests/test_strategy_adapter/test_integration.py`.
- 45 integration tests. Full suite: 1214 tests.
- Integration coverage: allowed LONG_RESEARCH_ONLY and SHORT_RESEARCH_ONLY signal flows; blocked missing, BLOCKED, UNKNOWN, DISABLED strategy contract states; blocked BLOCK_ALL strategy contract mode; blocked stale StrategyContext; blocked unsafe flags (dry_run false, live_trading_enabled true, real_orders_enabled true, leverage_enabled true, shorting_enabled true); JSON output verification; atomic/path verification; safety absence checks.
- No application code changed. No config YAML, no JSON schema, no deployable strategy class, no Freqtrade runtime, no Binance, no API keys, no live trading, no real orders, no leverage, no shorting, no entry/exit execution logic.

## Definition of Done

- [ ] SPEC-008 compliance verified.
- [ ] Full test suite passes with 1214+ tests.
- [ ] Fail-closed behavior verified.
- [ ] Writer atomic output behavior verified.
- [ ] No unsafe integration found.
- [ ] No new features added.

## Next Step

MVP-7 complete. Version bump to 0.7.0-dev. MVP-8 planning.
