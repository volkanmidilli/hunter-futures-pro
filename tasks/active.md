# Active Task

## Current Task

MVP-12 Step 4 — Final MVP-12 validation and version bump, not started.

## Status

MVP-12 Step 3 complete. SPEC-013 implementation in progress. Version 0.11.0-dev. Full test suite: 2450 tests passing, 1 skipped using `pytest --import-mode=importlib`.

MVP-12 Step 1 Review Index Models and Engine is complete.
- `src/hunter/review_index/__init__.py` — public API exports.
- `src/hunter/review_index/models.py` — review index models.
- `src/hunter/review_index/engine.py` — review index engine.
- `tests/test_review_index/__init__.py` — test package init.
- `tests/test_review_index/test_models.py` — 70 model tests.
- `tests/test_review_index/test_engine.py` — 97 engine tests.
- 166 review_index tests passing. 1 skipped INDEX_ERROR edge test.
- Full suite: 2377 tests passing, 1 skipped using `pytest --import-mode=importlib`.
- No writer. No integration tests. No Web UI. No dashboard. No database persistence.

MVP-12 Step 2 — Review Index Writer (Complete).
- `src/hunter/review_index/writer.py` — JSON/Markdown serialization, atomic file writing.
- `src/hunter/review_index/__init__.py` — updated with writer exports.
- `tests/test_review_index/test_writer.py` — 52 writer tests.
- Default JSON path: `data/review_index/latest_review_index.json`.
- Default Markdown path: `reports/review_index/latest_review_index.md`.
- 218 review_index tests total (166 model/engine + 52 writer). 1 skipped INDEX_ERROR edge test.
- Full suite: 2429 tests passing, 1 skipped using `pytest --import-mode=importlib`.
- No integration tests. No Web UI. No dashboard. No database persistence.

MVP-12 Step 3 — Review Index Integration Tests (Complete).
- `tests/test_review_index/test_integration.py` — 21 integration tests.
- `TestBuildReviewIndexToDict` — 9 tests (linked, observation-only, fail-closed missing, invalid, unsafe, mixed ready/blocked, deterministic timestamps, file references as strings, no production paths).
- `TestBuildReviewIndexToMarkdown` — 5 tests (linked entry, fail-closed, mixed entries, file references not opened, no production paths).
- `TestBuildReviewIndexWrite` — 7 tests (JSON+Markdown write, fail-closed write, mixed entries, deterministic JSON, no temp files left, file references not traversed, tmp_path used exclusively).
- 239 review_index tests total (166 model/engine + 52 writer + 21 integration). 1 skipped.
- Full suite: 2450 tests passing, 1 skipped using `pytest --import-mode=importlib`.
- No source changes. No Web UI. No dashboard. No database persistence.

MVP-12 Step 4 — Final MVP-12 validation and version bump, not started.

## Scope

MVP-12 Step 4 — Final validation and version bump only.
- Run full test suite, verify no regressions.
- Update version to 0.12.0 if approved.
- No new features unless a defect is found.

### Allowed
- Version bump.
- Final review and changelog update.

### Not Allowed Until Future SPEC
- No config YAML.
- No JSON schema.
- No Freqtrade strategy class.
- No freqtrade import.
- No Freqtrade runtime connection.
- No Binance.
- No real exchange.
- No API keys.
- No live trading.
- No real orders.
- No leverage.
- No shorting.
- No real entry/exit execution logic.
- No report feedback into execution paths.
- No operator feedback into execution paths.
- No index feedback into execution paths.
- No Web UI.
- No dashboard.
- No database persistence.
- No production data reads/writes.
- File references remain local strings only and must not be traversed/opened/followed/validated/executed.

## Previous Task

MVP-12 Step 3 — Review Index Integration Tests (Complete).
- 21 integration tests pass.
- 239 review_index tests total. 1 skipped.
- Full suite: 2450 tests passing, 1 skipped.
- No source changes.

## Definition of Done

- [x] SPEC-012 approved with notes and polished.
- [x] MVP-11 Step 1 complete: review models and engine implemented.
- [x] MVP-11 Step 2 complete: review writer implemented.
- [x] MVP-11 Step 3 complete: integration tests implemented.
- [x] MVP-11 Step 4 complete: final review passed.
- [x] 138 review model/engine tests pass.
- [x] 54 writer tests pass.
- [x] 83 integration tests pass.
- [x] Full suite 2211 tests pass.
- [x] No defects found.
- [x] Version bumped to 0.11.0-dev.
- [x] SPEC-013 drafted for MVP-12 planning.
- [x] SPEC-013 reviewed and approved.
- [x] MVP-12 Step 1 complete: review index models and engine implemented.
- [x] 70 review index model tests pass.
- [x] 97 review index engine tests pass.
- [x] Full suite 2377 tests pass, 1 skipped.
- [x] MVP-12 Step 2 complete: review index writer implemented.
- [x] 52 review index writer tests pass.
- [x] Full suite 2429 tests pass, 1 skipped.
- [x] MVP-12 Step 3 complete: review index integration tests implemented.
- [x] 21 review index integration tests pass.
- [x] Full suite 2450 tests pass, 1 skipped.
- [ ] MVP-12 Step 4 complete: final validation and version bump.

## Next Step

MVP-12 Step 4 — Final MVP-12 validation and version bump, not started.

Future review index integration tests or operator workflow UI may be considered only in a future SPEC, but is not implemented yet.
