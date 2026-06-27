# Active Task

## Current Task

MVP-10 Step 3 -- Observation Integration Tests.

## Status

MVP-10 Step 2 complete. SPEC-011 approved with notes and polished. MVP-10 implementation in progress. Version 0.9.0-dev. Full test suite: 1910 tests passing using `pytest --import-mode=importlib`.

MVP-9 is complete. All 1716 tests pass. Version 0.9.0-dev.
SPEC-010 design is approved and fully implemented.
SPEC-011 is approved with notes and polished.
MVP-10 Step 1 Observation Models and Engine complete. 1852 tests pass.

## Scope

MVP-10 Step 3 -- Observation Integration Tests only.
- Future file:
  - `tests/test_observation/test_integration.py`
- Allowed work:
  - In-process MVP-9 shell metadata to SignalObservation.
  - SignalObservation to ObservationWindow.
  - ObservationWindow to ObservationReport.
  - ObservationReport to JSON/Markdown using `tmp_path` only.
  - Long research observation path.
  - Short research observation path.
  - Blocked/fail-closed paths.
  - Unsafe metadata rejection.
  - Report output verification.
  - No production data reads/writes.
  - No runtime/exchange/network calls.
- Not allowed:
  - No model changes unless strictly necessary.
  - No engine changes unless strictly necessary.
  - No writer changes unless strictly necessary.
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
  - No report feedback into execution paths.
  - No production data reads/writes except `tmp_path`.

## Previous Task

MVP-10 Step 2 -- Observation Report Writer (complete).
- `src/hunter/observation/writer.py` -- 5 writer functions: observation_report_to_dict, observation_report_to_markdown, atomic_write_json_report, atomic_write_markdown_report, write_observation_reports.
- `src/hunter/observation/__init__.py` -- updated with writer exports.
- `tests/test_observation/test_writer.py` -- 58 writer tests.
- Default JSON path: `data/observation/latest_observation_report.json`.
- Default Markdown path: `reports/observation/latest_observation_report.md`.
- Full test suite: 1910 tests passing using `pytest --import-mode=importlib`.
- No integration tests yet.
- No config YAML, no JSON schema, no Freqtrade strategy class, no freqtrade import, no Freqtrade runtime connection, no Binance, no real exchange, no API keys, no live trading, no real orders, no leverage, no shorting, no real entry/exit execution logic, no report feedback into execution paths, no production data reads/writes.

MVP-10 Step 1 -- Observation Models and Engine (complete).
- `src/hunter/observation/__init__.py` -- public API exports.
- `src/hunter/observation/models.py` -- 9 models: ObservationState, ObservationSignal, ReportFormat, ObservationConfig, ObservationSafetyFlags, SignalObservation, ObservationWindow, ObservationDataQuality, ObservationReport.
- `src/hunter/observation/engine.py` -- 5 engine functions: build_signal_observation, build_observation_window, build_observation_report, build_observation_safety_flags, has_unsafe_metadata.
- `tests/test_observation/__init__.py` -- test package init.
- `tests/test_observation/test_models.py` -- 77 model tests.
- `tests/test_observation/test_engine.py` -- 59 engine tests.
- 13 deterministic reason codes + FORBIDDEN_METADATA_KEYS.
- Full test suite: 1852 tests passing using `pytest --import-mode=importlib`.
- No writer. No integration tests.
- No config YAML, no JSON schema, no Freqtrade strategy class, no freqtrade import, no Freqtrade runtime connection, no Binance, no real exchange, no API keys, no live trading, no real orders, no leverage, no shorting, no real entry/exit execution logic, no report feedback into execution paths, no file reads/writes, no production data access.

## Definition of Done

- [x] MVP-9 complete.
- [x] Version bumped to 0.9.0-dev.
- [x] All tests pass (1852+).
- [x] Safety constraints verified.
- [x] Final review verdict: PASS.
- [x] No new features, config, schema, or strategy class created.
- [x] SPEC-011 reviewed and approved.
- [x] MVP-10 Step 1 Observation Models and Engine complete.
- [x] MVP-10 Step 2 Observation Report Writer complete.
- [x] `src/hunter/observation/writer.py` created with:
  - `DEFAULT_OBSERVATION_JSON_REPORT_PATH`
  - `DEFAULT_OBSERVATION_MARKDOWN_REPORT_PATH`
  - `observation_report_to_dict(...)`
  - `observation_report_to_markdown(...)`
  - `atomic_write_json_report(...)`
  - `atomic_write_markdown_report(...)`
  - `write_observation_reports(...)`
- [x] `tests/test_observation/test_writer.py` created with 58 writer tests.
- [x] All writer tests pass.
- [x] Full test suite passes (1910+ tests).
- [x] No model changes.
- [x] No engine changes.
- [x] No integration tests.
- [x] No config YAML.
- [x] No JSON schema.
- [x] No Freqtrade strategy class.
- [x] No freqtrade import.
- [x] No Freqtrade runtime connection.
- [x] No Binance.
- [x] No real exchange connection.
- [x] No API keys.
- [x] No live trading.
- [x] No real orders.
- [x] No leverage.
- [x] No shorting.
- [x] No real entry/exit execution logic.
- [x] No report feedback into execution paths.
- [x] No production data reads/writes except writer output path tests using `tmp_path`.
- [ ] `tests/test_observation/test_integration.py` created with integration tests.
- [ ] All integration tests pass.
- [ ] Full test suite passes (1910+ tests).
- [ ] No model changes unless strictly necessary.
- [ ] No engine changes unless strictly necessary.
- [ ] No writer changes unless strictly necessary.
- [ ] No config YAML.
- [ ] No JSON schema.
- [ ] No Freqtrade strategy class.
- [ ] No freqtrade import.
- [ ] No Freqtrade runtime connection.
- [ ] No Binance.
- [ ] No real exchange connection.
- [ ] No API keys.
- [ ] No live trading.
- [ ] No real orders.
- [ ] No leverage.
- [ ] No shorting.
- [ ] No real entry/exit execution logic.
- [ ] No report feedback into execution paths.
- [ ] No production data reads/writes except `tmp_path`.

## Next Step

MVP-10 Step 3 -- Observation Integration Tests.
- Future file: `tests/test_observation/test_integration.py`.
- Allowed work: in-process observation flow tests, happy paths, blocked paths, writer verification, safety assertions.
- Not allowed: no config YAML, no JSON schema, no Freqtrade strategy class, no freqtrade import, no Freqtrade runtime connection, no Binance, no real exchange, no API keys, no live trading, no real orders, no leverage, no shorting, no real entry/exit execution logic, no report feedback into execution paths, no production data reads/writes except `tmp_path`.
