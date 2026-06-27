# Active Task

## Current Task

MVP-10 Step 2 -- Observation Report Writer.

## Status

MVP-10 Step 1 complete. SPEC-011 approved with notes and polished. MVP-10 implementation in progress. Version 0.9.0-dev. Full test suite: 1852 tests passing using `pytest --import-mode=importlib`.

MVP-9 is complete. All 1716 tests pass. Version 0.9.0-dev.
SPEC-010 design is approved and fully implemented.
SPEC-011 is approved with notes and polished.
MVP-10 Step 1 Observation Models and Engine complete. 1852 tests pass.

## Scope

MVP-10 Step 2 -- Observation Report Writer only.
- Future files:
  - `src/hunter/observation/writer.py`
  - `tests/test_observation/test_writer.py`
- Allowed work:
  - `observation_report_to_dict(...)`
  - `observation_report_to_markdown(...)`
  - `atomic_write_json_report(...)`
  - `atomic_write_markdown_report(...)`
  - `write_observation_reports(...)`
  - Local report writer tests
  - Default JSON path: `data/observation/latest_observation_report.json`
  - Default Markdown path: `reports/observation/latest_observation_report.md`
- Not allowed:
  - No model changes unless strictly necessary.
  - No engine changes unless strictly necessary.
  - No integration tests.
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
  - No production data reads/writes except writer output path tests using `tmp_path`.

## Previous Task

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
- [ ] `src/hunter/observation/writer.py` created with:
  - `DEFAULT_OBSERVATION_REPORT_JSON_PATH`
  - `DEFAULT_OBSERVATION_REPORT_MARKDOWN_PATH`
  - `observation_report_to_dict(...)`
  - `observation_report_to_markdown(...)`
  - `atomic_write_json_report(...)`
  - `atomic_write_markdown_report(...)`
  - `write_observation_reports(...)`
- [ ] `tests/test_observation/test_writer.py` created with writer tests.
- [ ] All writer tests pass.
- [ ] Full test suite passes (1852+ tests).
- [ ] No model changes unless strictly necessary.
- [ ] No engine changes unless strictly necessary.
- [ ] No integration tests.
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
- [ ] No production data reads/writes except writer output path tests using `tmp_path`.

## Next Step

MVP-10 Step 3 -- Observation Integration Tests.
- Future file: `tests/test_observation/test_integration.py`.
- Allowed work: in-process observation flow tests, happy paths, blocked paths, writer verification, safety assertions.
- Not allowed: no config YAML, no JSON schema, no Freqtrade strategy class, no freqtrade import, no Freqtrade runtime connection, no Binance, no real exchange, no API keys, no live trading, no real orders, no leverage, no shorting, no real entry/exit execution logic, no report feedback into execution paths, no production data reads/writes except `tmp_path`.
