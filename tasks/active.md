# Active Task

## Current Task

MVP-9 Step 3 — Shell Integration Tests.

## Status

MVP-9 Step 2 complete. SPEC-010 approved. MVP-9 implementation in progress.

MVP-8 is complete. All 1491 tests pass. Version 0.8.0-dev.
SPEC-009 design is finalized and fully implemented.
SPEC-010 is approved for MVP-9 implementation.
MVP-9 Step 1 Shell Models and Validator complete. 1613 tests pass.
MVP-9 Step 2 Shell Adapter Boundary complete. 1654 tests pass.

## Scope

MVP-9 Step 3 only. Do not start Step 4 until human approval.

## Allowed (Step 3)

- `tests/test_freqtrade_shell/test_integration.py` — integration tests only.
- In-process payload validation to `ShellValidationResult`.
- `ShellValidationResult` to research metadata.
- Research metadata applied to dataframe-like object.
- Long research happy path.
- Short research happy path.
- Blocked/fail-closed paths.
- Forbidden trade columns rejected.
- No production data writes.
- No runtime/exchange/network calls.

## Not Allowed (Step 3)

- No model changes unless strictly necessary for test compatibility.
- No validator changes unless strictly necessary for test compatibility.
- No adapter changes unless strictly necessary for test compatibility.
- No real Freqtrade strategy class.
- No freqtrade import.
- No config YAML.
- No JSON schema.
- No Freqtrade runtime connection.
- No Binance.
- No real exchange connection.
- No API keys.
- No live trading.
- No real orders.
- No leverage.
- No shorting.
- No real entry/exit execution logic.

## Previous Task

MVP-9 Step 2 — Shell Adapter Boundary (complete).
- `src/hunter/freqtrade_shell/adapter.py` — 5 adapter functions + 4 research column constants.
- `src/hunter/freqtrade_shell/__init__.py` — updated with adapter constants and function exports.
- `tests/test_freqtrade_shell/test_adapter.py` — 41 adapter tests.
- Research-only metadata: adds only `hunter_*` columns, never sets `enter_long`/`enter_short`/`exit_long`/`exit_short`, rejects forbidden trade columns.
- Full test suite: 1654 tests passing (1613 existing + 41 new) using `pytest --import-mode=importlib`.
- No model changes, no validator changes, no Freqtrade import, no Freqtrade strategy class, no config YAML, no JSON schema, no Freqtrade runtime connection, no Binance, no real exchange, no API keys, no live trading, no real orders, no leverage, no shorting, no real entry/exit execution logic.

## Definition of Done

- [ ] `test_integration.py` created with comprehensive integration tests.
- [ ] All tests pass.
- [ ] No model changes unless strictly necessary.
- [ ] No validator changes unless strictly necessary.
- [ ] No adapter changes unless strictly necessary.
- [ ] No freqtrade import.
- [ ] No real Freqtrade strategy class.
- [ ] Research-only metadata/columns only.
- [ ] Never set enter/exit columns.
- [ ] Fail closed on BLOCKED/UNKNOWN/DISABLED/invalid.
- [ ] Full test suite passes (1654+ tests).

## Next Step

MVP-9 Step 4 — Final Review.

