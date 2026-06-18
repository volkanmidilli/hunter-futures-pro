# Active Task

## Current Task

MVP-6 Step 5 — Final Review and Polish.

## Status

Not started. Awaiting approval.

MVP-6 Step 4 Strategy Contract Integration Tests is complete. 45 new tests. Full suite 959 tests passing.

## Scope

Step 5 allowed work:
- Review SPEC-007 compliance: models, engine, writer, integration tests.
- Run full pytest: verify all 959 tests pass.
- Verify fail-closed behavior: all blocked paths produce BLOCKED + BLOCK_ALL.
- Verify writer atomic output behavior: temp-file + os.replace, no partial files.
- Verify no unsafe integration exists.
- Small polish fixes only if verified.

Step 5 not allowed:
- No new features.
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

MVP-6 Step 4 — Strategy Contract Integration Tests (complete).
- `tests/test_strategy_contract/test_integration.py` created with 45 tests.
- Full suite: 959 tests passing.

## Goal

Implement MVP-6 Step 5 Final Review and Polish as the fifth and final step toward the Freqtrade Strategy Contract layer.

## Definition of Done

Step 5 is done when:
- SPEC-007 compliance verified for all components.
- All 959 tests pass.
- Fail-closed behavior verified for all blocked paths.
- Writer atomic output behavior verified.
- No unsafe integration exists.
- Small polish fixes applied if verified.
- Full test suite remains 959+ tests passing.
- No safety constraints violated.

## Next Step After Step 5

MVP-6 is complete. Version bump to 0.6.0-dev.