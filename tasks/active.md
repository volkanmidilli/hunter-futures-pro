# Active Task

## Current Task

MVP-11 Step 3 — Review Integration Tests, not started.

## Status

MVP-11 Step 2 complete. SPEC-012 implementation in progress. Version 0.10.0-dev. Full test suite: 2160 tests passing using `pytest --import-mode=importlib`.

MVP-10 is complete. All 1968 tests pass. Version 0.10.0-dev.
SPEC-010 design is approved and fully implemented.
SPEC-011 is approved with notes and polished.
SPEC-012 is approved with notes and polished. MVP-11 Steps 1-2 complete.

## Scope

MVP-11 Step 3 — Review Integration Tests only.
- Do not start Step 3 without human approval.
- Integration test scope: in-process MVP-10 observation report → review record → review audit record → JSON/Markdown output using tmp_path only.
- No model changes unless defect found.
- No engine changes unless defect found.
- No writer changes unless defect found.

### Not Allowed
- No model changes unless defect found.
- No engine changes unless defect found.
- No writer changes unless defect found.
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
- No operator feedback into execution paths.
- No production data reads/writes.

## Previous Task

MVP-11 Step 2 — Review Writer (Complete).
- Files created: `src/hunter/review/writer.py`, `tests/test_review/test_writer.py`.
- File modified: `src/hunter/review/__init__.py`.
- 54 new writer tests. Full suite: 2160 tests passing.
- Implemented: 11 writer functions (9 serialization + 2 atomic writers + combined writer), 2 default path constants, Markdown safety notice.

## Definition of Done

- [x] SPEC-012 approved with notes and polished.
- [x] MVP-11 Step 1 complete: review models and engine implemented.
- [x] MVP-11 Step 2 complete: review writer implemented.
- [x] 138 review model/engine tests pass.
- [x] 54 writer tests pass.
- [x] Full suite 2160 tests pass.
- [ ] MVP-11 Step 3 integration tests implemented (not started).
- [ ] Integration tests pass (not started).
- [ ] No defects found in Steps 1-2.

## Next Step

MVP-11 Step 3 — Review Integration Tests. Requires human approval.
