# Active Task

## Current Task

MVP-6 Step 4 — Integration Tests.

## Status

Not started. Awaiting approval.

MVP-6 Step 3 Strategy Context Writer is complete. 36 new tests. Full suite 914 tests passing.

## Scope

Step 4 allowed work:
- Future file: `tests/test_strategy_contract/test_integration.py`.
- End-to-end engine + writer tests.
- LONG_RESEARCH_ONLY flow.
- SHORT_RESEARCH_ONLY flow.
- BLOCK_ALL flow.
- Stale/missing/invalid/unsafe bridge context flows.
- JSON output verification.
- Atomic write verification.
- Safety absence tests.

Step 4 not allowed:
- No app code changes unless fixing a small verified bug.
- No config YAML.
- No JSON schema.
- No strategy class.
- No Freqtrade runtime.
- No Binance.
- No API keys.
- No live trading.
- No real orders.
- No leverage.
- No shorting.

## Previous Task

MVP-6 Step 3 — Strategy Context Writer (complete).
- `src/hunter/strategy_contract/writer.py` created with 3 writer functions + default path constant.
- `src/hunter/strategy_contract/__init__.py` updated with writer exports.
- `tests/test_strategy_contract/test_writer.py` created with 36 tests.
- Full suite: 914 tests passing.

## Goal

Implement MVP-6 Step 4 Integration Tests as the fourth step toward the Freqtrade Strategy Contract layer.

## Definition of Done

Step 4 is done when:
- Integration tests cover LONG_RESEARCH_ONLY, SHORT_RESEARCH_ONLY, BLOCK_ALL flows.
- Stale/missing/invalid/unsafe bridge context flows are tested.
- JSON output verification tests pass.
- Atomic write verification tests pass.
- Safety absence tests pass.
- Full test suite remains 914+ tests passing.
- No code outside the 1 allowed file.
- No safety constraints violated.

## Next Step After Step 4

MVP-6 Step 5 — Final Review and Polish.
