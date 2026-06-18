# Active Task

## Current Task

MVP-7 Step 4 — Strategy Adapter Integration Tests.

## Status

Not started. Awaiting approval.

MVP-7 Step 3 is complete. 41 new tests. 1169 total. Version 0.6.0-dev.
SPEC-008 design is finalized and polished. No MVP-7 integration tests implemented yet.

## Scope

Step 4 allowed work:
- `tests/test_strategy_adapter/test_integration.py` — end-to-end integration tests.
- Engine + writer full pipeline tests.
- LONG_RESEARCH_ONLY signal flow tests.
- SHORT_RESEARCH_ONLY signal flow tests.
- BLOCK_SIGNAL flow tests.
- Stale/missing/invalid/unsafe StrategyContext flow tests.
- JSON output verification.
- Atomic/path verification.
- Safety absence tests.

Step 4 not allowed:
- No application code changes unless fixing a small verified bug.
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

MVP-7 Step 3 — Adapter Decision JSON Writer (complete).
- 3 files changed/created: `writer.py`, `__init__.py`, `test_writer.py`.
- `DEFAULT_ADAPTER_DECISION_PATH = data/strategy_adapter/current_adapter_decision.json`.
- `adapter_decision_context_to_dict()` — serializes `AdapterDecisionContext` to JSON-compatible dict.
- `atomic_write_json()` — atomic temp-file write with `os.replace()`, parent directory creation, cleanup on failure.
- `write_adapter_decision_context()` — writes to default path.
- ISO-8601 UTC timestamps, enum strings, signal_intent as string, reason_codes as list, nested dicts, version "1.0".
- 41 writer tests. Full suite: 1169 tests.
- No integration tests, no config YAML, no JSON schema, no deployable strategy class, no Freqtrade runtime, no Binance, no API keys, no live trading, no real orders, no leverage, no shorting, no entry/exit execution logic.

## Definition of Done

- [ ] Integration tests cover all signal flows (LONG, SHORT, BLOCK).
- [ ] Integration tests cover all blocking conditions (stale, missing, invalid, unsafe).
- [ ] JSON output verification tests pass.
- [ ] Atomic/path verification tests pass.
- [ ] Safety absence tests pass.
- [ ] Full test suite passes with 1169+ tests.
- [ ] No code outside `tests/test_strategy_adapter/test_integration.py`.

## Next Step

MVP-7 Step 5 — Final Review and Polish.
