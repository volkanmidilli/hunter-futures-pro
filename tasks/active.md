# Active Task

## Current Task

MVP-10 planning — not started.

## Status

MVP-9 complete. SPEC-010 complete. Version 0.9.0-dev. Full test suite: 1716 tests passing using `pytest --import-mode=importlib`. Final review verdict: PASS. No defects found.

MVP-8 is complete. All 1491 tests pass. Version 0.8.0-dev.
SPEC-009 design is finalized and fully implemented.
SPEC-010 is approved for MVP-9 implementation.
MVP-9 Step 1 Shell Models and Validator complete. 1613 tests pass.
MVP-9 Step 2 Shell Adapter Boundary complete. 1654 tests pass.
MVP-9 Step 3 Shell Integration Tests complete. 1716 tests pass.
MVP-9 Step 4 Final Review complete. Verdict: PASS. No defects found.

## Scope

MVP-10 planning not started. Do not start without human approval and a SPEC document.

## Not Allowed (until future SPEC)

- No config YAML.
- No JSON schema.
- No Freqtrade strategy class.
- No freqtrade import.
- No Freqtrade runtime connection.
- No Binance.
- No real exchange connection.
- No API keys.
- No live trading.
- No real orders.
- No leverage.
- No shorting.
- No real entry/exit execution logic.
- No production data reads/writes.

## Previous Task

MVP-9 Completion — SPEC-010 Freqtrade Dry-Run Strategy Shell (complete).
- `src/hunter/freqtrade_shell/__init__.py` — public API exports.
- `src/hunter/freqtrade_shell/models.py` — ShellState, ShellSignalExposure, ShellRuntimeConfig, ShellValidationResult, 18 reason codes.
- `src/hunter/freqtrade_shell/validator.py` — validate_runtime_payload, is_runtime_payload_stale, parse_runtime_timestamp, map_signal_action_to_exposure.
- `src/hunter/freqtrade_shell/adapter.py` — 5 adapter functions + 4 research column constants.
- `tests/test_freqtrade_shell/test_models.py` — 94 model tests.
- `tests/test_freqtrade_shell/test_validator.py` — 28 validator tests.
- `tests/test_freqtrade_shell/test_adapter.py` — 41 adapter tests.
- `tests/test_freqtrade_shell/test_integration.py` — 62 integration tests.
- Full test suite: 1716 tests passing using `pytest --import-mode=importlib`.
- No config YAML, no JSON schema, no Freqtrade strategy class, no freqtrade import, no Freqtrade runtime connection, no Binance, no real exchange, no API keys, no live trading, no real orders, no leverage, no shorting, no real entry/exit execution logic, no production data reads/writes.

## Definition of Done

- [ ] MVP-9 complete.
- [ ] Version bumped to 0.9.0-dev.
- [ ] All tests pass (1716+).
- [ ] Safety constraints verified.
- [ ] Final review verdict: PASS.
- [ ] No new features, config, schema, or strategy class created.

## Next Step

MVP-10 planning — requires human approval and new SPEC document.

