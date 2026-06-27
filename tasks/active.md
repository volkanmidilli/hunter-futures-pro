# Active Task

## Current Task

MVP-9 Step 2 — Shell Adapter Boundary.

## Status

MVP-9 Step 1 complete. SPEC-010 approved. MVP-9 implementation in progress.

MVP-8 is complete. All 1491 tests pass. Version 0.8.0-dev.
SPEC-009 design is finalized and fully implemented.
SPEC-010 is approved for MVP-9 implementation.
MVP-9 Step 1 Shell Models and Validator complete. 1613 tests pass.

## Scope

MVP-9 Step 2 only. Do not start Step 3 until human approval.

## Allowed (Step 2)

- `src/hunter/freqtrade_shell/adapter.py` — adapter boundary only.
- `tests/test_freqtrade_shell/test_adapter.py` — adapter tests.
- No freqtrade import.
- No real IStrategy dependency.
- Expose research-only metadata/columns only.
- Never set `enter_long`, `enter_short`, `exit_long`, `exit_short`.
- Consume `ShellValidationResult`.
- Fail closed on BLOCKED/UNKNOWN/DISABLED/invalid result.

## Not Allowed (Step 2)

- No real Freqtrade strategy class.
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

MVP-9 Step 1 — Shell Models and Validator (complete).
- `src/hunter/freqtrade_shell/__init__.py` — public API exports.
- `src/hunter/freqtrade_shell/models.py` — ShellState, ShellSignalExposure, ShellRuntimeConfig, ShellValidationResult, 18 reason codes.
- `src/hunter/freqtrade_shell/validator.py` — validate_runtime_payload, is_runtime_payload_stale, parse_runtime_timestamp, map_signal_action_to_exposure.
- `tests/test_freqtrade_shell/test_models.py` — 94 model tests.
- `tests/test_freqtrade_shell/test_validator.py` — 28 validator tests.
- Full test suite: 1613 tests passing (1491 existing + 122 new).
- No adapter.py, no Freqtrade strategy class, no freqtrade import, no config YAML, no JSON schema, no Freqtrade runtime connection, no Binance, no real exchange, no API keys, no live trading, no real orders, no leverage, no shorting, no real entry/exit execution logic.

## Definition of Done

- [ ] `adapter.py` created with adapter boundary functions.
- [ ] `test_adapter.py` created with comprehensive adapter tests.
- [ ] All tests pass.
- [ ] No freqtrade import.
- [ ] No real IStrategy dependency.
- [ ] Research-only metadata/columns only.
- [ ] Never set enter/exit columns.
- [ ] Fail closed on BLOCKED/UNKNOWN/DISABLED/invalid.
- [ ] Full test suite passes (1613+ tests).

## Next Step

Human review of SPEC-010. After approval, MVP-9 Step 1 — Shell Models and Validator.

